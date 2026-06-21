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
    # ---- tangential (Coulomb) friction (Macklin et al. 2020 §3.5) ----
    # Per-body μ for the FLOOR contact (combined coefficient = the contacting
    # body's friction, set at attach). XPBD position-based friction clamps the
    # tangent multiplier to the cone |λ_t| ≤ μ λ_n each sweep.
    body_friction: dict = field(default_factory=dict, repr=False)  # body -> μ
    _lam_t: dict = field(default_factory=dict, repr=False)         # row -> λ_t
    _p0: dict = field(default_factory=dict, repr=False)  # row -> corner@substep-begin (3,)
    # ---- Route A on XPBD: OFF by default (honest limitation) -----------------
    # The grounded-stacked two-way q-load (see iteration_hook §3) is wired here
    # and works in isolation, but the XPBD primal's modal ring is ~4× livelier
    # than AVBD's (single-body reaction 33 mm vs 4.5 mm at the same scene), so a
    # TALL vertical pile (e.g. the truck's 4-high lumber) telescopes while riding
    # it, and the per-sweep Gauss–Seidel q-load is caught between over-driving
    # (runaway) and over-damping. The AVBD primal solves the modal block
    # implicitly (regularized Schur) and is stable, so Route A defaults ON there.
    # On XPBD it defaults OFF (stacks use the stable static-slab fallback). A
    # robust XPBD path — a regularized/implicit modal load, or the device q-DOF —
    # is a documented follow-up (CLAUDE.md rule 6).
    cosolve_stacked_q: bool = False
    # Per grounded-stacked body: its FLOOR rows' (row, U_y, floor_y, off) for the
    # q-only projection, and the per-row compressive multiplier λ. The host owns
    # these bodies' rigid pose; the coupler only loads/drains q from their
    # contact. Populated in substep_begin from the parent's `_stacked_set` tag.
    _stacked_rows: dict = field(default_factory=dict, repr=False)
    _lam_cs: dict = field(default_factory=dict, repr=False)     # row -> λ (≥0)

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
        # Tangential friction: reset λ_t and snapshot each corner's world
        # position at the START of the substep (the pre-predictor committed
        # pose x_initial / q_initial, written by predict_inertial_6dof just
        # before this hook). Friction opposes the tangential slide accumulated
        # from here, so the snapshot must precede the inertial drift.
        self._lam_t = {row: 0.0 for row in rows}
        self._p0 = {}
        x_init = solver.x_initial.numpy()
        q_init = solver.q_initial.numpy()
        # Bodies the coupler OWNS this substep = those whose FLOOR contact went
        # active (λ_c > 0). Only these get their rigid pose/velocity written back
        # to the solver (see `_write_rigid_and_anchor` / `_commit_rigid_velocity`)
        # — separated / body-on-body stacked bodies are left to the solver's own
        # box-box primal, matching how the AVBD coupler only writes the bodies in
        # `per_body_Hx_inv`. Writing ALL tracked bodies (the previous behavior)
        # clobbered the solver's box-box resolution for stacked bystanders (e.g.
        # ledge pillars), forcing them to the free-flight predictor → blow-up.
        self._active_bodies: set[int] = set()

        # frozen per-body rigid predictor + geometry (one substep linearization)
        self._xb.clear()
        self._qb.clear()
        self._b_invm.clear()
        self._b_Iinv.clear()
        self._b_rows.clear()
        # Route A: grounded-stacked bodies (tagged in `_stacked_set` by the
        # parent gate) are owned by the HOST for pose; the coupler only adds
        # their FLOOR contact's two-way modal load to q (see iteration_hook).
        # Collect their per-row geometry separately (no friction / no frozen
        # pose — q-only) and reset their q-load multipliers.
        self._stacked_rows = {}
        self._lam_cs = {}
        n_hat = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        for b, rows_on_body in self._rows_per_body.items():
            if b in self._stacked_set:
                srows = []
                for row in rows_on_body:
                    srows.append((int(row),
                                  self._U_at_row[row][1].astype(np.float64),
                                  float(self._row_floor_y_rest[row]),
                                  self._row_off_a[row].astype(np.float64)))
                    self._lam_cs[int(row)] = 0.0
                self._stacked_rows[b] = srows
                continue
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
                # Store the LOCAL corner offset; the world lever arm r_self_w and
                # the angular Jacobian j_ang are recomputed from the LIVE qb each
                # projection in `iteration_hook` (see the DEVIATION there).
                off = self._row_off_a[row].astype(np.float64)
                U_y = self._U_at_row[row][1].astype(np.float64)        # (r,)
                G_a = self._row_cargo_Ga.get(row)                       # (k,) | None
                if G_a is not None:
                    G_a = np.asarray(G_a, dtype=np.float64)
                # corner world pos at substep start (pre-predictor) for friction
                self._p0[int(row)] = (
                    x_init[b].astype(np.float64)
                    + _quat_xyzw_to_R(q_init[b].astype(np.float64)) @ off)
                rdata.append((int(row), off, U_y, G_a,
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
            mu = float(self.body_friction.get(b, 0.5))   # Coulomb μ
            for (row, off, U_y, G_a, floor_y) in rdata:
                # DEVIATION (XPBD rigid positional constraint, Macklin et al.
                # "Detailed Rigid Body Simulation with XPBD" 2020): recompute the
                # corner world lever arm r_self_w = R(qb)·off and the angular
                # Jacobian j_ang from the LIVE projected orientation qb every
                # sweep, NOT the substep-begin freeze. With a frozen j_ang the
                # rotational correction applied to qb never feeds back into the
                # re-evaluated gap C, so serial Gauss–Seidel over a resting box's
                # corners pumps angular momentum unboundedly (a flat resting body
                # spun up to |ω|≈185 rad/s). The translation Jacobian n̂=e_y is
                # constant; only the corner geometry is re-linearized.
                Rb = _quat_xyzw_to_R(qb)
                r_self_w = Rb @ off
                j_ang = np.array([-r_self_w[2], 0.0, r_self_w[0]],
                                 dtype=np.float64)
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
                if new > 0.0:
                    self._active_bodies.add(b)     # coupler owns this body's pose
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

                # --- tangential Coulomb friction (XPBD position-based) ---------
                # DEVIATION (paper Eq. 10 forced-IIR carries NO friction; the
                # XPBD coupler was likewise frictionless, so contacting bodies
                # slid freely and never shed spin). Restore the tangent term
                # per Macklin et al. 2020 "Detailed Rigid Body Simulation with
                # XPBD" §3.5: oppose the corner's tangential slide accumulated
                # since the substep-begin pose, with a separate multiplier λ_t
                # clamped to the Coulomb cone |λ_t| ≤ μ·λ_n. The support contact
                # point is treated as tangentially fixed (its modes are
                # vertical-dominant), so friction couples ONLY the rigid 6-DOF
                # (translation + spin), not the support q or cargo a.
                # NOTE: CPU reference path only; the GPU device path
                # (`_iteration_device`) does not yet carry friction — follow-up.
                lam_n = self._lam_c[row]
                if mu <= 0.0 or lam_n <= 0.0:
                    continue
                r_w = _quat_xyzw_to_R(qb) @ off    # live corner lever arm
                dx = (xb + r_w) - self._p0[row]
                dx[1] = 0.0                        # strip the normal (n̂ = e_y)
                tmag = float(np.linalg.norm(dx))
                if tmag < 1e-12:
                    continue
                t_hat = dx / tmag                  # tangent slide direction
                j_t = np.cross(r_w, t_hat)         # angular Jacobian ∂(t̂·p)/∂θ
                w_t = invm + float(j_t @ (Iinv @ j_t))
                # hard static-friction target C_t = tmag → 0 (compliance α_t = 0)
                dlam_t = -tmag / max(w_t, 1e-300)
                bound = mu * lam_n                 # Coulomb cone
                new_t = min(bound, max(-bound, self._lam_t[row] + dlam_t))
                dlam_t = new_t - self._lam_t[row]
                self._lam_t[row] = new_t
                xb += (invm * dlam_t) * t_hat      # n̂-orthogonal translation
                dtheta_t = (Iinv @ j_t) * dlam_t
                nq = _quat_xyzw_mul(_quat_xyzw_from_rotvec(dtheta_t), qb)
                nn = float(np.linalg.norm(nq))
                if nn > 1e-12:
                    qb[:] = nq / nn

        # --- (3) Route A: two-way modal load from GROUNDED-STACKED bodies ----
        # DEVIATION (two_band_coupling.html: body↔SUPPORT only, no body↔body
        # term — a stack cannot be a coupler DOF). The host owns a grounded
        # stack's rigid pose (its box-box keeps the pile intact and rides it on
        # the modal anchor), and here we close the two-way loop: the stack's
        # FLOOR contact, evaluated against the host's LIVE pose, loads q exactly
        # like an owned body's contact — but we update ONLY q (the body is
        # host-owned, held fixed for this projection). This makes the coupling
        # passive (the stack pressing the ringing surface drains q), unlike the
        # one-way anchor-include which injects energy and telescopes. The base
        # then feels the ring through the HOST FLOOR contact against the
        # coupler-written anchor, and the host box-box transmits it up the pile.
        # Block Gauss–Seidel: q sees the host pose frozen for this sub-step.
        if self._stacked_rows:
            x_host = solver.x.numpy()
            q_host = solver.q.numpy()
            for b, srows in self._stacked_rows.items():
                xb_h = x_host[b].astype(np.float64)
                Rb_h = _quat_xyzw_to_R(q_host[b].astype(np.float64))
                m = float(self._mass_np[b])
                if m <= 0.0 or not np.isfinite(m):
                    continue
                invm = 1.0 / m
                I_local = self._inertia_local_np[b].astype(np.float64)
                Iinv = np.linalg.inv(Rb_h @ I_local @ Rb_h.T + 1e-12 * np.eye(3))
                for (row, U_y, floor_y, off) in srows:
                    r_self_w = Rb_h @ off
                    corner_y = xb_h[1] + float(r_self_w[1])
                    surf = floor_y + float(U_y @ q)
                    C = corner_y - surf
                    lam = self._lam_cs[row]
                    if C >= 0.0 and lam == 0.0:
                        continue              # separated, inactive
                    # FULL coupled inverse mass — the SAME w an owned body would
                    # see (rigid + support modal). Holding the body fixed for the
                    # q-only update (w = U_yᵀM_q⁻¹U_y alone) dumps ALL the
                    # near-rigid contact compliance into q and the per-sweep
                    # Gauss–Seidel over-drives the ring into a runaway (react→8 m).
                    # Sharing the impulse with the body's inverse mass damps dlam
                    # to the physical value; we then apply only the q part (the
                    # body is host-owned — the host's own FLOOR contact moves it).
                    j_ang = np.array([-r_self_w[2], 0.0, r_self_w[0]],
                                     dtype=np.float64)
                    w = (invm + float(j_ang @ (Iinv @ j_ang))
                         + float(np.sum(U_y * U_y * wq)))
                    if w <= 0.0:
                        continue
                    dlam = (-C - at_c * lam) / (w + at_c)
                    new = lam + dlam
                    if new < 0.0:
                        new = 0.0             # compressive only (λ ≥ 0)
                    dlam = new - lam
                    self._lam_cs[row] = new
                    q += (-U_y * wq) * dlam   # load/drain the modal surface

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
        # Only write the bodies the coupler owns (active FLOOR contact). Others
        # keep the solver's box-box primal pose (see `_active_bodies`).
        for b in self._active_bodies:
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
            for (row, _off, _Uy, G_a, _fy) in rdata:
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
        # Per-body owned-this-substep flag (FLOOR contact went active): only these
        # bodies get their pose/velocity written back (mirrors `_active_bodies`).
        d["x_active"] = wp.zeros(max_b, dtype=int, device=dev)
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
                          d["x_xb"], d["x_qb"], d["x_invm"], d["x_Iinv"],
                          d["x_active"]])
        wp.launch(KX.k_xpbd_begin_row, dim=cap_rows, device=dev, inputs=[
            d["counts"], d["x_lamc"]])
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
            d["row_off"], d["x_invm"], d["x_Iinv"],
            d["Mq"], f64(self._dev_at_c), d["x_xb"], d["x_qb"], d["q"],
            d["x_lamc"], d["x_active"]])
        wp.launch(KX.k_xpbd_write_rigid, dim=max_b, device=dev, inputs=[
            d["counts"], d["body_ids"], d["x_xb"], d["x_qb"], d["x_active"],
            solver.x, solver.q])
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
            d["counts"], d["body_ids"], d["x_xb"], d["x_qb"], d["x_active"],
            solver.x_initial, solver.q_initial, f64(self._dev_inv_dt),
            solver.v, solver.omega])
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
        if not self._active_bodies:
            return
        from .reduced_coupled_avbd import _quat_xyzw_inv, _quat_xyzw_to_rotvec
        h = float(self.h_substep)
        x_init = solver.x_initial.numpy()
        q_init = solver.q_initial.numpy()
        v = solver.v.numpy().copy()
        omega = solver.omega.numpy().copy()
        # Only the coupler-owned (active FLOOR contact) bodies get their velocity
        # from the XPBD pose; the rest keep the solver's box-box velocity.
        for b in self._active_bodies:
            v[b] = ((self._xb[b] - x_init[b].astype(np.float64)) / h).astype(np.float32)
            dq = _quat_xyzw_mul(self._qb[b], _quat_xyzw_inv(q_init[b].astype(np.float64)))
            omega[b] = (_quat_xyzw_to_rotvec(dq) / h).astype(np.float32)
        solver.v.assign(v)
        solver.omega.assign(omega)
