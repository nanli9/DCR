"""XPBD realization of the dynamic two-way modal contact constraint
(AVBD-Native port, Stage 6).

`reduced_coupled_avbd.py` solves the coupled (rigid 6-DOF ⊕ augmented modal Q)
contact block by a per-iteration **Schur–Newton** primal (Augmented Vertex Block
Descent). This module solves the SAME incremental potential with the **XPBD**
primal — Extended Position-Based Dynamics (Macklin et al. 2016): every elastic
force and the unilateral contact are compliant constraints projected
Gauss–Seidel inside one substep, with the modal Rayleigh damping `D_q` applied
through Macklin's damped compliant-constraint update (§3.5). The CPU parity
oracle is `dcr/twobody/position_based.py:XPBDDynamicSystem` (its math is not
changed); this re-expresses that oracle in the AVBD-Native solver idiom so the
cube rides the GPU solver's real per-corner FLOOR collision (the Path-A
no-penetration benefit) while the modal coupling is solved by XPBD.

Design (mirrors `ReducedCoupledAVBDCoupler` — the validated monolithic coupler —
swapping ONLY the per-iteration primal):

  * substep_begin / substep_end / the per-substep caches (frozen U_y, the
    co-rotated cargo gradient G_a, the augmented-Q layout, the contact anchor,
    the modal-velocity commit + energy/passivity diagnostics) are INHERITED
    verbatim. They are the shared backward-Euler machinery; only the iteration
    primal differs.
  * `iteration_hook` is one Gauss–Seidel sweep of compliant constraints:
      1. per-mode modal elastic constraints C_i = q_i / a_i (support q and each
         cargo a) with compliance α_i = 1/K_q[i,i] and the damped update;
      2. the abd nonlinear V⊥ orthogonality constraints (cargo `elastic_constraints`);
      3. the unilateral FLOOR contact per tracked corner, C = gap ≥ 0, compliance
         α_c = 1/k_contact, multiplier clamped compressive (λ_c ≥ 0), coupling the
         cube rigid 6-DOF + cube modal a + support modal q through one shared
         multiplier (the structural two-way loop).
    The XPBD multipliers (λ_q, λ_a, λ_c) reset each substep and accumulate
    across the sweeps (one sweep per AVBD-Native solver iteration).

The coupler OWNS the tracked bodies' rigid pose (it projects them from the
inertial predictor) and the modal state; the solver owns the inertial predictor,
the per-corner FLOOR-row emission (collision detection) and the untracked bodies.

Material support (matches the `XPBDDynamicSystem` oracle exactly):
  * `fem` (translation+modal) and `fem_rigid` (co-rotated rigid frame ⊕ modal):
    fully supported — the LINEAR modal stiffness is an exact diagonal compliant
    constraint and the modal Rayleigh damping rings it down through the Macklin
    damped update, so the two-way loop is stable + passive.
  * `abd` (nonlinear quartic V⊥): the oracle's own note — "ABD's mass-proportional
    damping is not wired through the per-constraint damp term here, so the AVBD
    path is the one exercised for ABD". The V⊥ is a stiff (~255 Hz at the cube's
    κ_v) NONLINEAR constraint; Gauss–Seidel cannot dissipate it in the substep's
    sweep budget, so abd-XPBD is NOT long-run stable here (it projects fine for a
    few steps — enough for CPU↔GPU parity — but the affine deformation accumulates
    over a sustained contact). **abd uses the AVBD path** (`reduced_coupled_avbd`),
    which solves the stiff V⊥ implicitly. This is honest per CLAUDE.md rule 8 and
    consistent with the oracle.

# DEVIATION (two_band_coupling.html — monolithic vs staggered solver): the rigid
# Jacobian (R, j_ang, the co-rotated G_a, U_y) is FROZEN at substep begin (the
# same staggering the AVBD coupler uses), so each substep's contact is the
# linearized two-way constraint; the modal q / a and the rigid translation are
# the live DOFs the sweep projects. Order within a constraint colour is
# DOF-independent (each modal constraint touches its own DOF), so the CPU
# sequential sweep == the GPU colour-parallel sweep ⇒ exact parity; the FLOOR
# contacts share q and are projected serially on both CPU and GPU.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .reduced_coupled_avbd import (
    ReducedCoupledAVBDCoupler,
    _quat_xyzw_to_R,
    _quat_xyzw_from_rotvec,
    _quat_xyzw_mul,
)


@dataclass
class ReducedCoupledXPBDCoupler(ReducedCoupledAVBDCoupler):
    """XPBD coupled primal coupler (see module docstring). Subclasses the AVBD
    coupler to reuse its substep machinery; overrides only the iteration primal.
    """

    # Unilateral-contact compliance α_c = 1/k_contact (Macklin 2016: α̃ = α/h²).
    # The support modes carry their own K_q compliance; the contact is the stiff
    # near-rigid constraint that resolves penetration and loads the modes. Small
    # ⇒ near-hard contact. Tuned so the cube settles with < a few mm penetration.
    xpbd_contact_compliance: float = 1.0e-8

    # Number of Gauss–Seidel sweeps per substep = the solver's iteration count
    # (set at attach time). Each `iteration_hook` call is ONE sweep.
    # ---- per-substep XPBD state (reset in substep_begin) ----
    _lam_q: NDArray[np.float64] | None = field(default=None, repr=False)
    _lam_a: dict = field(default_factory=dict, repr=False)
    _lam_c: dict = field(default_factory=dict, repr=False)
    # frozen per-body rigid carried state + geometry
    _xb: dict = field(default_factory=dict, repr=False)        # body -> (3,) world COM
    _qb: dict = field(default_factory=dict, repr=False)        # body -> (4,) xyzw
    _b_invm: dict = field(default_factory=dict, repr=False)    # body -> 1/m
    _b_Iinv: dict = field(default_factory=dict, repr=False)    # body -> (3,3) Iworld^-1
    _b_rows: dict = field(default_factory=dict, repr=False)    # body -> list of row tuples
    _cargo_Minv: dict = field(default_factory=dict, repr=False)  # body -> (k,k) inv(M_q)
    # support modal diagonals (eigenbasis ⇒ Mq/Kq/Dq diagonal)
    _Mq_d: NDArray[np.float64] | None = field(default=None, repr=False)
    _Kq_d: NDArray[np.float64] | None = field(default=None, repr=False)
    _Dq_d: NDArray[np.float64] | None = field(default=None, repr=False)
    _wq: NDArray[np.float64] | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # substep_begin: inherit the AVBD caches, then seed the XPBD predictor
    # start + reset the compliant-constraint multipliers.
    # ------------------------------------------------------------------
    def substep_begin_hook(self, solver) -> None:
        super().substep_begin_hook(solver)
        if self._use_device(solver):
            # device path resets its own buffers (see _substep_begin_device).
            return
        rows = self.rs.tracked_row_indices
        if not rows:
            return

        # XPBD starts at the inertial predictor and projects it (Macklin 2016):
        # the modal q / a start at q̃ = qⁿ + h q̇ⁿ (the AVBD predictor super()
        # stored), the rigid at the solver's free-flight predictor x_inertial.
        self.rs.q = self.rs.q_hat.copy()
        for b in self.cargo:
            self.cargo_a[b] = self.cargo_a_hat[b].copy()

        r = int(self.rs.r)
        self._Mq_d = np.diag(self.rs.Mq).astype(np.float64).copy()
        self._Kq_d = np.diag(self.rs.Kq).astype(np.float64).copy()
        self._Dq_d = np.diag(self.rs.Dq).astype(np.float64).copy()
        self._wq = np.where(self._Mq_d > 0.0, 1.0 / np.maximum(self._Mq_d, 1e-300), 0.0)

        # reset multipliers (XPBD resets per substep, accumulates over sweeps)
        self._lam_q = np.zeros(r, dtype=np.float64)
        self._lam_a = {}
        self._lam_c = {row: 0.0 for row in rows}
        self._cargo_Minv = {}

        # frozen per-body rigid predictor + geometry (one substep linearization)
        self._xb.clear()
        self._qb.clear()
        self._b_invm.clear()
        self._b_Iinv.clear()
        self._b_rows.clear()
        n_hat = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        for b, rows_on_body in self._rows_per_body.items():
            m = float(self._mass_np[b])
            if m <= 0.0 or not np.isfinite(m):
                continue
            qx = self._q_inertial_np[b].astype(np.float64).copy()
            Rb = _quat_xyzw_to_R(qx)
            self._xb[b] = self._x_inertial_np[b].astype(np.float64).copy()
            self._qb[b] = qx
            self._b_invm[b] = 1.0 / m
            I_local = self._inertia_local_np[b].astype(np.float64)
            I_world = Rb @ I_local @ Rb.T
            self._b_Iinv[b] = np.linalg.inv(I_world + 1e-12 * np.eye(3))
            body = self.cargo.get(b)
            if body is not None:
                self._lam_a[b] = np.zeros(int(body.k), dtype=np.float64)
                Mqb = np.asarray(body.Mq_block, dtype=np.float64)
                self._cargo_Minv[b] = np.linalg.inv(Mqb)
            rdata = []
            for row in rows_on_body:
                off = self._row_off_a[row].astype(np.float64)
                r_self_w = Rb @ off
                j_ang = np.array([-r_self_w[2], 0.0, r_self_w[0]], dtype=np.float64)
                U_y = self._U_at_row[row][1].astype(np.float64)        # (r,)
                G_a = self._row_cargo_Ga.get(row)                       # (k,) | None
                if G_a is not None:
                    G_a = np.asarray(G_a, dtype=np.float64)
                rdata.append((int(row), r_self_w, j_ang, U_y, G_a,
                              float(self._row_floor_y_rest[row])))
            self._b_rows[b] = rdata

    # ------------------------------------------------------------------
    # iteration_hook: one Gauss–Seidel sweep of compliant constraints.
    # ------------------------------------------------------------------
    def iteration_hook(self, solver, iter_idx: int) -> None:
        rows = self.rs.tracked_row_indices
        if not rows:
            return
        if self._use_device(solver) and self._device_ready:
            if self._dev_n_b > 0:
                self._iteration_device(solver)
            return

        h = float(self.h_substep)
        inv_h2 = 1.0 / (h * h)
        r = int(self.rs.r)
        q = self.rs.q
        qn = self.rs.q_prev_macro
        Kq, Mq_d, Dq, wq = self._Kq_d, self._Mq_d, self._Dq_d, self._wq

        # --- (1) modal elastic constraints: support q (per-mode, independent) ---
        # C_i = q_i, stiffness K_q[i,i] ⇒ α_i = 1/K_q[i,i]; damped compliant
        # update (Macklin §3.5) with the modal Rayleigh damping D_q[i,i].
        for i in range(r):
            ki = Kq[i]
            if ki <= 0.0:
                continue
            alpha = 1.0 / ki
            at = alpha * inv_h2
            w = wq[i]
            damp = Dq[i]
            gamma = at * (damp * alpha) * h if damp > 0.0 else 0.0
            Cdot = q[i] - qn[i]
            denom = (1.0 + gamma) * w + at
            dlam = (-q[i] - at * self._lam_q[i] - gamma * Cdot) / denom
            self._lam_q[i] += dlam
            q[i] += w * dlam

        # --- (1b) modal elastic constraints: each cargo a ---
        for b, body in self.cargo.items():
            a = self.cargo_a[b]
            an = self.cargo_a_prev[b]
            lam_a = self._lam_a[b]
            if body.has_nonlinear_internal:
                # abd V⊥ — nonlinear, re-linearized each projection; dense M_F^-1.
                Minv = self._cargo_Minv[b]
                for kc, (C, grad, alpha, damp) in enumerate(body.elastic_constraints(a)):
                    if alpha <= 0.0:
                        continue
                    at = alpha * inv_h2
                    Mg = Minv @ grad
                    w = float(grad @ Mg)
                    gamma = at * (damp * alpha) * h if damp > 0.0 else 0.0
                    Cdot = float(grad @ (a - an))
                    denom = (1.0 + gamma) * w + at
                    dlam = (-C - at * lam_a[kc] - gamma * Cdot) / denom
                    lam_a[kc] += dlam
                    a += Mg * dlam
            else:
                Kqb = np.diag(np.asarray(body.Kq_block, dtype=np.float64))
                Mqb = np.diag(np.asarray(body.Mq_block, dtype=np.float64))
                Dqb = np.diag(np.asarray(body.Dq_block, dtype=np.float64))
                for i in range(int(body.k)):
                    ki = Kqb[i]
                    if ki <= 0.0:
                        continue
                    alpha = 1.0 / ki
                    at = alpha * inv_h2
                    w = 1.0 / Mqb[i] if Mqb[i] > 0.0 else 0.0
                    damp = Dqb[i]
                    gamma = at * (damp * alpha) * h if damp > 0.0 else 0.0
                    Cdot = a[i] - an[i]
                    denom = (1.0 + gamma) * w + at
                    dlam = (-a[i] - at * lam_a[i] - gamma * Cdot) / denom
                    lam_a[i] += dlam
                    a[i] += w * dlam

        # --- (2) unilateral FLOOR contact (per corner, serial — all share q) ---
        alpha_c = float(self.xpbd_contact_compliance)
        at_c = alpha_c * inv_h2
        for b, rdata in self._b_rows.items():
            invm = self._b_invm[b]
            Iinv = self._b_Iinv[b]
            xb = self._xb[b]
            qb = self._qb[b]
            body = self.cargo.get(b)
            a = self.cargo_a[b] if body is not None else None
            Minv_a = self._cargo_Minv.get(b)
            for (row, r_self_w, j_ang, U_y, G_a, floor_y) in rdata:
                corner_y = xb[1] + r_self_w[1]
                surf = floor_y + float(U_y @ q)
                flex = float(G_a @ a) if G_a is not None else 0.0
                C = corner_y - surf + flex
                lam = self._lam_c[row]
                if C >= 0.0 and lam == 0.0:
                    continue                       # separated, inactive
                # generalized inverse mass w = ∇Cᵀ M⁻¹ ∇C over the coupled DOFs:
                #   rigid  : n̂ᵀ(1/m I)n̂ + j_angᵀ I_world⁻¹ j_ang
                #   support: U_yᵀ M_q⁻¹ U_y   (∂C/∂q = −U_y)
                #   cargo  : G_aᵀ M_a⁻¹ G_a   (∂C/∂a = +G_a)
                w = invm + float(j_ang @ (Iinv @ j_ang))
                w += float(np.sum(U_y * U_y * wq))
                MgG = None
                if G_a is not None:
                    MgG = Minv_a @ G_a
                    w += float(G_a @ MgG)
                dlam = (-C - at_c * lam) / (w + at_c)
                new = lam + dlam
                if new < 0.0:
                    new = 0.0                      # compressive only (λ_c ≥ 0)
                dlam = new - lam
                self._lam_c[row] = new
                # apply Δz = M⁻¹ ∇C dlam
                xb[1] += invm * dlam               # n̂ = e_y
                dtheta = (Iinv @ j_ang) * dlam
                new_q = _quat_xyzw_mul(_quat_xyzw_from_rotvec(dtheta), qb)
                nrm = float(np.linalg.norm(new_q))
                if nrm > 1e-12:
                    new_q = new_q / nrm
                qb[:] = new_q
                q += (-U_y * wq) * dlam            # support modal (∂C/∂q = −U_y)
                if G_a is not None:
                    a += MgG * dlam                # cargo modal (∂C/∂a = +G_a)

        # write the projected rigid pose back + refresh the modal anchor for the
        # solver's next iteration / the substep_end penetration diagnostic.
        self._write_rigid_and_anchor(solver, q)
        self.last_n_iter_solves += 1

    def _write_rigid_and_anchor(self, solver, q) -> None:
        """Push the XPBD-projected tracked-body poses to solver.x / solver.q and
        rewrite the contact anchor from the live modal surface
        floor + U_y·q − G_a·a (so the solver's overwritten FLOOR primal and the
        substep_end residual both see the deformed two-way surface)."""
        x_out = solver.x.numpy().copy()
        q_out = solver.q.numpy().copy()
        for b in self._xb:
            x_out[b] = self._xb[b].astype(np.float32)
            q_out[b] = self._qb[b].astype(np.float32)
        solver.x.assign(x_out)
        solver.q.assign(q_out)
        if not self._tracked_rows_arr.size:
            return
        anchor = solver.c_world_anchor.numpy().copy()
        dy = self._U_y_stack @ q
        anchor[self._tracked_rows_arr, 1] = self._floor_y_rest_arr + dy
        for b, rdata in self._b_rows.items():
            body = self.cargo.get(b)
            if body is None:
                continue
            a = self.cargo_a[b]
            for (row, _rw, _ja, _Uy, G_a, _fy) in rdata:
                if G_a is not None:
                    anchor[row, 1] -= float(G_a @ a)
        solver.c_world_anchor.assign(anchor.astype(np.float32))

    # ------------------------------------------------------------------
    # substep_end: own the tracked-body rigid velocity from the XPBD pose, then
    # inherit the modal-velocity commit + energy/passivity diagnostics.
    # ------------------------------------------------------------------
    def substep_end_hook(self, solver) -> None:
        if self._use_device(solver):
            super().substep_end_hook(solver)
            return
        self._commit_rigid_velocity(solver)
        super().substep_end_hook(solver)

    # ==================================================================
    # GPU-resident device path (mirrors the CPU reference launch-for-launch;
    # reuses the AVBD augmented-Q device buffers + geometry/predictor kernels).
    # ==================================================================
    _dev_at_c: float = 0.0

    def _ensure_device_buffers(self, solver) -> None:
        super()._ensure_device_buffers(solver)
        import warp as wp
        from .reduced_coupled_kernels import vec3d, vec4d, mat33d
        dev = solver.device
        f64 = wp.float64
        max_b = int(self._dev_max_b)
        cap_rows = int(self._dev_cap_rows)
        R = int(self._dev_R)
        d = self._dbuf
        d["x_xb"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["x_qb"] = wp.zeros(max_b, dtype=vec4d, device=dev)
        d["x_invm"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["x_Iinv"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["x_rsw"] = wp.zeros(cap_rows, dtype=vec3d, device=dev)
        d["x_ja0"] = wp.zeros(cap_rows, dtype=f64, device=dev)
        d["x_ja2"] = wp.zeros(cap_rows, dtype=f64, device=dev)
        d["x_lamc"] = wp.zeros(cap_rows, dtype=f64, device=dev)
        d["x_lamq"] = wp.zeros(R, dtype=f64, device=dev)
        d["x_rowtbody"] = wp.zeros(cap_rows, dtype=int, device=dev)
        self._dev_at_c = float(self.xpbd_contact_compliance) * self._dev_inv_dt2

    def _upload_topology_once(self, solver) -> None:
        super()._upload_topology_once(solver)
        d = self._dbuf
        body_ids = d["body_ids"].numpy()
        row_body = d["row_body"].numpy()
        n_b = int(self._dev_n_b)
        total = int(self._dev_total_rows)
        inv = {int(body_ids[t]): t for t in range(n_b)}
        rowtb = np.zeros(int(self._dev_cap_rows), dtype=np.int32)
        for rr in range(total):
            rowtb[rr] = inv.get(int(row_body[rr]), 0)
        d["x_rowtbody"].assign(rowtb)

    def _substep_begin_device(self, solver) -> None:
        """Device substep_begin: AVBD geometry/predictor kernels + freeze the
        rigid predictor pose / per-row Jacobian + reset the XPBD multipliers +
        seed the working modal state at q̃ (launch-only, outside the graph)."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        from . import reduced_coupled_xpbd_kernels as KX
        if not self._device_ready:
            self._ensure_device_buffers(solver)
            self._upload_topology_once(solver)
            solver.hooks_device_resident = True
            self._device_ready = True
        if self._dev_n_b == 0:
            return
        d = self._dbuf
        dev = solver.device
        r = int(self._dev_r)
        Rt = int(self._dev_R)
        cap_rows = int(self._dev_cap_rows)
        f64 = wp.float64
        # moving basis U_y (+ co-rotated cargo cols −G_a) → augmented row_U_y.
        wp.launch(K.k_eval_basis, dim=cap_rows, device=dev, inputs=[
            solver.x, solver.q, d["counts"], r, d["row_index"], d["row_body"],
            d["row_off"], d["grid_Uy"], int(self.n_grid_x), int(self.n_grid_z),
            f64(self.shelf_length), f64(self.shelf_width), d["row_U_y"]])
        if self.cargo:
            wp.launch(K.k_eval_cargo, dim=cap_rows, device=dev, inputs=[
                solver.q, d["counts"], r, Rt, d["row_body"], d["row_cargo_off"],
                d["row_cargo_k"], d["row_cargo_corot"], d["row_corner_modal"],
                d["row_U_y"]])
        # predictor q̃ = qⁿ + h·q̇ⁿ ; snapshot qⁿ.
        h_pred = 0.0 if self.freeze_qdot else self._dev_h_sub
        wp.launch(K.k_predict, dim=Rt, device=dev, inputs=[
            Rt, f64(h_pred), d["q"], d["qdot"], d["q_prev"], d["q_hat"]])
        # XPBD start: q ← q̃, reset λ_q.
        wp.launch(KX.k_xpbd_seed_modal, dim=Rt, device=dev, inputs=[
            d["q"], d["q_hat"], d["x_lamq"]])
        # freeze rigid predictor pose, inverse mass / inertia, per-row Jacobian.
        wp.launch(KX.k_xpbd_begin_body, dim=int(self._dev_max_b), device=dev,
                  inputs=[d["counts"], d["body_ids"], solver.x_inertial,
                          solver.q_inertial, solver.mass, solver.inertia_local,
                          d["x_xb"], d["x_qb"], d["x_invm"], d["x_Iinv"]])
        wp.launch(KX.k_xpbd_begin_row, dim=cap_rows, device=dev, inputs=[
            d["counts"], d["x_rowtbody"], d["row_off"], d["x_qb"],
            d["x_rsw"], d["x_ja0"], d["x_ja2"], d["x_lamc"]])
        # seed the contact anchor from the modal surface (q = q̃).
        wp.launch(K.k_anchor, dim=cap_rows, device=dev, inputs=[
            Rt, d["counts"], d["row_index"], d["row_U_y"], d["floor_y_rest"],
            d["q"], d["diag"], solver.c_world_anchor])

    def _iteration_device(self, solver) -> None:
        """One XPBD Gauss–Seidel sweep on-device: modal elastic (parallel) →
        unilateral FLOOR contact (serial) → write rigid pose + refresh anchor."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        from . import reduced_coupled_xpbd_kernels as KX
        d = self._dbuf
        dev = solver.device
        Rt = int(self._dev_R)
        cap_rows = int(self._dev_cap_rows)
        max_b = int(self._dev_max_b)
        f64 = wp.float64
        wp.launch(KX.k_xpbd_elastic, dim=Rt, device=dev, inputs=[
            Rt, d["Mq"], d["Kq"], d["Dq"], f64(self._dev_inv_dt2),
            f64(self._dev_h_sub), d["q"], d["q_prev"], d["x_lamq"]])
        wp.launch(KX.k_xpbd_contact, dim=1, device=dev, inputs=[
            d["counts"], Rt, d["x_rowtbody"], d["row_U_y"], d["floor_y_rest"],
            d["x_rsw"], d["x_ja0"], d["x_ja2"], d["x_invm"], d["x_Iinv"],
            d["Mq"], f64(self._dev_at_c), d["x_xb"], d["x_qb"], d["q"],
            d["x_lamc"]])
        wp.launch(KX.k_xpbd_write_rigid, dim=max_b, device=dev, inputs=[
            d["counts"], d["body_ids"], d["x_xb"], d["x_qb"], solver.x,
            solver.q])
        wp.launch(K.k_anchor, dim=cap_rows, device=dev, inputs=[
            Rt, d["counts"], d["row_index"], d["row_U_y"], d["floor_y_rest"],
            d["q"], d["diag"], solver.c_world_anchor])
        self.last_n_iter_solves += 1

    def _substep_end_device(self, solver) -> None:
        """Device substep_end: modal velocity q̇ = (q−qⁿ)/h + the coupler-owned
        rigid velocity; host readback once per macro-step (render/HUD)."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        from . import reduced_coupled_xpbd_kernels as KX
        if not self._device_ready or self._dev_n_b == 0:
            self._substep_index += 1
            return
        d = self._dbuf
        dev = solver.device
        Rt = int(self._dev_R)
        max_b = int(self._dev_max_b)
        f64 = wp.float64
        if not self.freeze_qdot:
            wp.launch(K.k_qdot, dim=Rt, device=dev, inputs=[
                Rt, f64(self._dev_inv_dt), d["q"], d["q_prev"], d["qdot"]])
        wp.launch(KX.k_xpbd_rigid_vel, dim=max_b, device=dev, inputs=[
            d["counts"], d["body_ids"], d["x_xb"], d["x_qb"], solver.x_initial,
            solver.q_initial, f64(self._dev_inv_dt), solver.v, solver.omega])
        is_last = (self._substep_index % self._dev_n_sub) == (
            self._dev_n_sub - 1)
        if is_last or self.log_substeps:
            self._sync_device_to_host(solver)
        self._substep_index += 1

    def _commit_rigid_velocity(self, solver) -> None:
        """v = (x − xⁿ)/h, ω = log(q ⊗ qⁿ⁻¹)/h for the coupler-owned tracked
        bodies (XPBD velocity update; the solver's finalize used its own primal
        pose, which this overrides so the next predictor carries the contact-
        resolved velocity)."""
        if not self._xb:
            return
        from .reduced_coupled_avbd import _quat_xyzw_inv, _quat_xyzw_to_rotvec
        h = float(self.h_substep)
        x_init = solver.x_initial.numpy()
        q_init = solver.q_initial.numpy()
        v = solver.v.numpy().copy()
        omega = solver.omega.numpy().copy()
        for b in self._xb:
            v[b] = ((self._xb[b] - x_init[b].astype(np.float64)) / h).astype(np.float32)
            dq = _quat_xyzw_mul(self._qb[b], _quat_xyzw_inv(q_init[b].astype(np.float64)))
            omega[b] = (_quat_xyzw_to_rotvec(dq) / h).astype(np.float32)
        solver.v.assign(v)
        solver.omega.assign(omega)
