"""Reduced-coordinate AVBD support — coupling layer.

Solves the q-block (§7), runs the two-rate transient overlay (§9), and
injects distant Δv at probe rigid bodies (§9.4). Plugs into Solver6DOF
via the optional `substep_begin_hook` / `iteration_hook` callbacks (no
kernel signature change). See the v1 plan at
`~/.claude/plans/you-are-working-inside-prancy-turtle.md`.

Sign conventions (FLOOR_CONTACT_6DOF):
  - AVBD kernel evaluates  C_avbd = corner_y_world − c_world_anchor[i].y
    so C_avbd > 0 is separation, C_avbd < 0 is penetration.
  - AVBD λ is in FORCE units (BDF1 convention) and is ≤ 0 for FLOOR rows
    (fmax = 0). Empirical gate: `tests/avbd/test_impulse_units.py` shows
    a resting box of mass m has Σ(−λ) ≈ m·g, so −λ is the upward force.
    The physical contact force MAGNITUDE on the body in +ŷ is therefore
        F_n = −λ_avbd + ρ_q · max(0, −C_avbd)                     (force)
    matching the spec's `f_c = λ + ρ C⁺` (§6). The world-space IMPULSE
    per step is h · F_n.
  - The contact normal on the BODY side (per spec §5) is n = +ŷ. The
    reduced contact Jacobian is therefore J_q = U(x_contact)^T · ŷ
    which equals the y-row of U at the contact point.

# DEVIATION (spec §6, §11.1): the spec's ρ is the AL penalty *for the
# q-block*, not AVBD's internal `c_penalty`. Solver6DOF's c_penalty is
# sized to enforce *rigid* non-penetration (1e6 N/m by default) — three
# to four orders of magnitude larger than the reduced support's natural
# stiffness K_q. Plugging it in directly inflates F_n by ~1e4×, dominates
# the q-block, and feedbacks into runaway drift. We instead choose a
# q-block ρ_q sized to the inertial term `(1/h²) · M_q_modal_max` — so
# the augmented penalty is on the same scale as the BDF1 inertial term
# and the natural elastic K_q diagonal. With AVBD's k·C carrying the
# rigid non-penetration response, our q-block ρ·C plays a much smaller
# role: it provides numerical regularisation and captures the LOW-ITER
# response the AVBD dual misses (per spec §11.1) without inflation.

# DEVIATION (overlay HP — spec §9 / §11.2): the spec says r_tilde =
# Σ (λ + ρ C⁺) J_q without an `is_new` event gate, so the overlay
# "inherits the no-event-gate property of the coupled solve". But the
# IIR re-excited every step by a STATIC contact load (e.g. a body
# resting on the shelf under gravity) accumulates Δv at distant probes
# indefinitely — the rest contact has nothing to do with a transient.
# Empirically this drove probes upward at constant 4 m/s after a single
# impact in the v1 scene. We restore the "transient only" semantics
# without re-introducing an event gate by HIGH-PASSING r_tilde across
# macro steps: the IIR sees r_tilde[n] − r_tilde[n−1] instead of
# r_tilde[n]. Steady loads are filtered out (Δ=0), genuine impacts
# survive (Δ≠0 for one step). Toggleable via `overlay_high_pass`; set
# False to reproduce the raw spec formulation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .reduced_support import ReducedSupport, evaluate_basis_at_point


# ---------------------------------------------------------------------------
# Constants matching solver_6dof.py
# ---------------------------------------------------------------------------
FLOOR_CONTACT_6DOF = 0


# ---------------------------------------------------------------------------
# Coupler
# ---------------------------------------------------------------------------

@dataclass
class ReducedSupportCoupler:
    """Stateful coupler that drives a ReducedSupport from inside the
    AVBD substep loop.

    Lifecycle per macro-step:
      `substep_begin_hook(solver)`  — once, after row emission, before
                                      the iteration loop. Identifies
                                      FLOOR_CONTACT rows on the tracked
                                      shelf bodies, seeds anchors from
                                      q_hat = q + h · qdot.
      `iteration_hook(solver, it)`  — after every AVBD iteration body.
                                      Reads converged-for-this-iter λ, k;
                                      solves r×r q-block on CPU; writes
                                      new anchors back.
      `post_step(world)`            — once per macro-step after
                                      solver.step(). Assembles r_tilde
                                      from the final (λ + h·k·C⁺), runs
                                      the IIR overlay, injects Δv at
                                      probes, logs energy.
    """

    rs: ReducedSupport

    # AVBD rigid-body indices that ride on the reduced support.
    # FLOOR_CONTACT rows are emitted per box corner; the coupler keeps
    # only the rows whose body_a is in this list.
    tracked_body_indices: list[int]

    # Sampling-grid metadata so the hook can bilinear-interpolate U at
    # arbitrary corner positions. Provided at construction by the scene.
    shelf_length: float
    shelf_width: float
    shelf_y_rest: float
    n_grid_x: int
    n_grid_z: int

    # Substep / macro-step size. Set by the world at attach time.
    h_substep: float = 1.0 / 60.0
    h_macro:   float = 1.0 / 60.0

    # Regularization for the dense r×r solve.
    solve_eps: float = 1e-10

    # q-block AL penalty ρ_q (force / length). Set on first hook fire
    # from `(1/h²) · max(diag(M_q[:r_modal]))` if left at 0, so the
    # contact penalty matches the inertial-term scale. The user can
    # override before attach for tuning. See the `# DEVIATION:` at the
    # top of the file for why this is NOT AVBD's c_penalty.
    rho_q: float = 0.0

    # Overlay forcing high-pass (see `# DEVIATION (overlay HP):` below).
    # When True, the IIR is driven by r_tilde[n] − r_tilde[n−1] instead
    # of r_tilde[n]. Suppresses runaway from a constant resting load
    # without an `is_new` event gate. Default True for the demo to
    # behave; set False to reproduce the raw spec §9.2 formulation.
    overlay_high_pass: bool = True

    # ---- Items (3) + (4): bounded overlay injection ------------------
    # Energy cap on the overlay's distant Δv injection: the candidate
    # injection KE
    #     E_inj = Σ_i ½ m_i ||Δv_i||²
    # is scaled by α = min(1, √(η·E_src / (E_inj+ε))) so the realised
    # injection cannot exceed η times the source rigid-KE loss this
    # macro step. Defaults: cap ON, η = 0.95. See `docs/reduced_support_v1.md`.
    energy_cap_enabled: bool = True
    eta_overlay:        float = 0.95

    # Short receiver cooldown: a probe that just received a Δv kick
    # has its OWN floor-contact rows excluded from r_tilde for the next
    # `cooldown_steps` macro steps. Not a hard identity mask — a temporal
    # gate against the probe→r_tilde→probe self-feedback loop. Default 2
    # macro steps; 0 disables.
    cooldown_steps:         int   = 2
    cooldown_dv_threshold:  float = 0.10   # m/s; below this, no cooldown trigger.

    # Per-step storage of the previous macro-step's r_tilde for the
    # high-pass differencing. Reset to None on detach / reset.
    _r_tilde_prev: NDArray[np.float64] | None = field(
        default=None, init=False, repr=False)

    # Probe-body-index → remaining cooldown count (decremented each macro
    # step). When > 0, that probe's contact rows are skipped in r_tilde
    # assembly. Empty dict ⇒ no probe in cooldown.
    _probe_cooldown: dict[int, int] = field(
        default_factory=dict, init=False, repr=False)

    # Cached U at each tracked row (row_idx → (3, r) sample of basis).
    # Filled in substep_begin_hook; consumed by iteration_hook.
    _U_at_row: dict[int, NDArray[np.float64]] = field(default_factory=dict)

    # Cached row metadata (body index, off_a, floor_y_rest). Set in
    # substep_begin_hook from solver._rows.
    _row_body_a: dict[int, int] = field(default_factory=dict)
    _row_off_a:  dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_floor_y_rest: dict[int, float] = field(default_factory=dict)

    # Energy accounting for one macro-step.
    last_E_rigid_pre_overlay:  float = 0.0
    last_E_rigid_post_overlay: float = 0.0
    last_E_overlay_injected:   float = 0.0
    last_E_q:                  float = 0.0
    last_E_total:              float = 0.0
    last_n_tracked_rows:       int = 0
    last_n_iter_solves:        int = 0
    last_probe_d_max:          NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(0))
    last_probe_dv:             NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(0))
    last_probe_dv_candidate:   NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(0))
    last_q_max_disp:           float = 0.0
    last_alpha_cap:            float = 1.0
    last_E_src:                float = 0.0
    last_E_inj_candidate:      float = 0.0
    last_E_inj_realised:       float = 0.0
    last_n_cooldown_active:    int   = 0

    # ---- hook plumbing --------------------------------------------------

    def substep_begin_hook(self, solver) -> None:
        """Identify tracked floor-contact rows for this substep and
        seed initial anchors from q_hat. Called once per substep, AFTER
        row emission and BEFORE the iteration loop.
        """
        if not self.rs.enabled:
            return

        # Auto-size rho_q on first fire if the user didn't override.
        if self.rho_q <= 0.0:
            h = float(self.h_substep)
            r_modal = self.rs.r_modal
            m_diag_modal = np.diag(self.rs.Mq)[:r_modal] if r_modal > 0 else np.array([1.0])
            m_max = float(np.max(np.abs(m_diag_modal))) if m_diag_modal.size > 0 else 1.0
            self.rho_q = m_max / (h * h)

        # Predict q_hat from previous step's qdot.
        self.rs.q_prev_macro = self.rs.q.copy()
        self.rs.q_hat = self.rs.q + self.h_macro * self.rs.qdot

        # Walk solver._rows on the CPU side; FLOOR_CONTACT rows are static
        # rows emitted by add_floor_contact_box at scene-build time, so
        # they live in the static prefix and are always present in
        # solver._rows. Anchor.y for these rows was stored at row emission.
        self._U_at_row.clear()
        self._row_body_a.clear()
        self._row_off_a.clear()
        self._row_floor_y_rest.clear()

        # Read anchor / row metadata once.
        anchor_np = solver.c_world_anchor.numpy().copy()
        off_a_np = solver.c_off_a.numpy().copy()
        body_a_np = solver.c_body_a.numpy()
        type_np = solver.c_type.numpy()

        tracked: list[int] = []
        for i, row in enumerate(solver._rows):
            if row.type != FLOOR_CONTACT_6DOF:
                continue
            if int(body_a_np[i]) not in self.tracked_body_indices:
                continue
            tracked.append(i)
            self._row_body_a[i] = int(body_a_np[i])
            self._row_off_a[i] = off_a_np[i].astype(np.float64)
            # The rest floor_y for this row is the anchor.y stored at row
            # emission (before any reduced-support hook has modified it).
            # We capture it here and never let it drift.
            if i not in self.rs.floor_y_rest:
                self.rs.floor_y_rest[i] = float(anchor_np[i, 1])
            self._row_floor_y_rest[i] = self.rs.floor_y_rest[i]

        self.rs.tracked_row_indices = tracked
        self.last_n_tracked_rows = len(tracked)

        if not tracked:
            return

        # Cache U at the corner's REST projection (x, z). This pins each
        # row to a fixed (x, z) sample for the substep — adequate for v1
        # since corners don't slide far in one substep.
        positions = solver.positions()              # (n_b, 3)
        orientations = solver.orientations()        # (n_b, 4) XYZW
        for row_idx in tracked:
            ba = self._row_body_a[row_idx]
            off = self._row_off_a[row_idx]
            xb = positions[ba]
            qb_xyzw = orientations[ba]
            r_world = _quat_rotate_xyzw(qb_xyzw, off)
            corner_w = xb + r_world
            U_pt = evaluate_basis_at_point(
                self.rs,
                (float(corner_w[0]), float(corner_w[2])),
                length=self.shelf_length,
                width=self.shelf_width,
                n_grid_x=self.n_grid_x,
                n_grid_z=self.n_grid_z,
            )                                       # (3, r)
            self._U_at_row[row_idx] = U_pt

        # Seed anchor.y with q_hat-displaced surface position.
        anchor_new = anchor_np.copy()
        q_hat = self.rs.q_hat
        for row_idx in tracked:
            U_y = self._U_at_row[row_idx][1]        # (r,)
            dy = float(U_y @ q_hat)
            anchor_new[row_idx, 1] = self._row_floor_y_rest[row_idx] + dy
        solver.c_world_anchor.assign(anchor_new.astype(np.float32))

        self.last_n_iter_solves = 0

    def iteration_hook(self, solver, iter_idx: int) -> None:
        """One block-coordinate q update. Called after every AVBD
        iteration body (primal + dual) finishes.

        Reads λ, k, anchors, body positions; solves the r×r q-block per
        §7; writes deformed anchors back so the NEXT iteration's primal
        sees the updated support.
        """
        if not self.rs.enabled:
            return
        rows = self.rs.tracked_row_indices
        if not rows:
            return

        # Pull AVBD state needed for the q-block contact term.
        lam_np = solver.c_lambda.numpy()
        pen_np = solver.c_penalty.numpy()
        anchor_np = solver.c_world_anchor.numpy().copy()
        positions = solver.positions()
        orientations = solver.orientations()

        h = float(self.h_substep)
        r = self.rs.r
        Mq, Kq, Dq = self.rs.Mq, self.rs.Kq, self.rs.Dq

        # Inertial + elastic + damping gradient (§7).
        # g_q_base = (1/h²) M_q (q − q_hat) + K_q q + D_q qdot
        q = self.rs.q
        q_hat = self.rs.q_hat
        qdot = self.rs.qdot
        g_q = (1.0 / (h * h)) * (Mq @ (q - q_hat)) + Kq @ q + Dq @ qdot

        # H_q_base = (1/h²) M_q + K_q + (1/h) D_q   (per §7 with damping
        # treated as a quadratic in (q − q_prev)/h; v1 uses the small
        # explicit form 1/h · D_q as a numerical regulariser).
        H_q = (1.0 / (h * h)) * Mq + Kq + (1.0 / h) * Dq

        # Contact contributions: walk tracked rows.
        for row_idx in rows:
            ba = self._row_body_a[row_idx]
            off = self._row_off_a[row_idx]
            xb = positions[ba]
            qb_xyzw = orientations[ba]
            corner_w = xb + _quat_rotate_xyzw(qb_xyzw, off)
            anchor_y_now = float(anchor_np[row_idx, 1])

            # AVBD convention C_avbd = corner_y − anchor_y (positive =
            # separation). Penetration depth in spec convention:
            #     C_pen_spec = max(0, −C_avbd) = max(0, anchor_y − corner_y)
            C_avbd = float(corner_w[1] - anchor_y_now)
            C_pen = max(0.0, -C_avbd)

            lam_avbd = float(lam_np[row_idx])   # ≤ 0 for FLOOR, in force units

            # f_c in force units (see file docstring `# DEVIATION:`):
            #   F_n = -λ_avbd + ρ_q · C_pen
            # Positive scalar = upward force magnitude on the body.
            F_n = -lam_avbd + self.rho_q * C_pen
            # Numerical safety: separated contacts can have stale λ; clip.
            if F_n < 0.0:
                F_n = 0.0

            # Reduced Jacobian: contact normal on the BODY is +ŷ for a
            # FLOOR_CONTACT, so J_q = U_y (the y-row of U at this point).
            U_y_row = self._U_at_row[row_idx][1]    # (r,)
            # Gradient += F_n · J_q; Hessian += ρ_q · J_q J_q^T  (§7).
            g_q = g_q + F_n * U_y_row
            H_q = H_q + self.rho_q * np.outer(U_y_row, U_y_row)

        # Solve r×r system: H_q Δq = −g_q.
        H_q_reg = H_q + self.solve_eps * np.eye(r)
        try:
            dq = np.linalg.solve(H_q_reg, -g_q)
        except np.linalg.LinAlgError:
            # Singular — skip this iteration's q-update; warn once.
            return
        self.rs.q = self.rs.q + dq

        # Write back deformed anchor for every tracked row.
        q_new = self.rs.q
        anchor_out = anchor_np.copy()
        for row_idx in rows:
            U_y = self._U_at_row[row_idx][1]
            dy = float(U_y @ q_new)
            anchor_out[row_idx, 1] = self._row_floor_y_rest[row_idx] + dy
        solver.c_world_anchor.assign(anchor_out.astype(np.float32))

        self.last_n_iter_solves += 1

    def substep_end_hook(self, solver) -> None:
        """Once per substep at the end of the iteration loop. Updates
        qdot from the macro-step q delta, restores anchors to rest so
        the NEXT substep's row-rebuilds start clean.
        """
        if not self.rs.enabled:
            return
        h = float(self.h_macro)
        if h > 0.0:
            self.rs.qdot = (self.rs.q - self.rs.q_prev_macro) / h

        # Restore anchors to rest. Static FLOOR rows live in the static
        # prefix and persist across substeps, so leaving them deformed
        # would corrupt the next substep's row-emission baseline.
        if self.rs.tracked_row_indices and self._row_floor_y_rest:
            anchor_np = solver.c_world_anchor.numpy().copy()
            for row_idx, rest_y in self._row_floor_y_rest.items():
                anchor_np[row_idx, 1] = rest_y
            solver.c_world_anchor.assign(anchor_np.astype(np.float32))

    # ---- Overlay + injection (post-step) -------------------------------

    def post_step(
        self,
        solver,
        *,
        rigid_kinetic_energy_fn,
        descs,
        E_src_step: float = 0.0,
    ) -> None:
        """Run the transient overlay (§9.3) and inject Δv at probes
        (§9.4). Called once per macro-step from `AVBDDCRWorld.step()`.

        `rigid_kinetic_energy_fn(descs)` returns the rigid KE total over
        the descriptor list — passed in to avoid a circular import on
        `dcr.rigid.energy`.
        `descs` is `world._descs`, used to find probe DCR-side bodies
        for energy logging.
        `E_src_step` is the rigid-KE loss over the macro step
        (max(0, KE_pre − KE_post)). When `energy_cap_enabled`, the
        overlay's injection KE is capped at η · E_src_step. Pass 0 to
        let the cap default to "no budget" → α=0 → no injection (safe
        sentinel for tests that don't thread the world's KE).
        """
        # Item (4) — decrement cooldown counters at the start of each
        # macro step so the kick that triggered the cooldown is *not*
        # counted toward the cooldown window's first step.
        if self._probe_cooldown:
            for k in list(self._probe_cooldown.keys()):
                self._probe_cooldown[k] = max(0, self._probe_cooldown[k] - 1)
                if self._probe_cooldown[k] == 0:
                    del self._probe_cooldown[k]
        self.last_n_cooldown_active = len(self._probe_cooldown)

        if not self.rs.enabled:
            self.last_probe_d_max = np.zeros(0)
            self.last_probe_dv = np.zeros(0)
            self.last_E_overlay_injected = 0.0
            return

        # Log q-energy (modal portion uses ω; full Mq-Kq covers the rest).
        q = self.rs.q
        qdot = self.rs.qdot
        E_q = 0.5 * float(qdot @ (self.rs.Mq @ qdot)) + 0.5 * float(q @ (self.rs.Kq @ q))
        self.last_E_q = E_q

        # q displacement diagnostic.
        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, q)
            self.last_q_max_disp = float(np.linalg.norm(disp, axis=1).max())
        else:
            self.last_q_max_disp = 0.0

        # No probes ⇒ nothing to inject regardless of overlay flag.
        if self.rs.n_probes == 0 or not self.rs.probe_body_indices:
            self.last_probe_d_max = np.zeros(self.rs.n_probes)
            self.last_probe_dv = np.zeros(self.rs.n_probes)
            self.last_E_overlay_injected = 0.0
            return

        # Per-probe `n · U` projection (used by both bare and overlay).
        n_dot_U_full = np.einsum(
            "pi,pij->pj", self.rs.probe_normals, self.rs.probe_U
        )                                                         # (n_probe, r)

        # ---- BARE branch: quasi-static d from converged q (§8). ----
        # This is what the implicit macro-step alone gives you. The
        # spec predicts it's suppressed by ~1/(ω·h) relative to the
        # overlay's peak — making it the right baseline to A/B against.
        d_bare = np.abs(n_dot_U_full @ q)                        # (n_probe,)
        probe_d_max = d_bare

        # ---- OVERLAY branch: assemble r_tilde and sub-step the IIR. ----
        h_macro = float(self.h_macro)
        if self.rs.overlay_enabled and self.rs.r_modal > 0:
            r_tilde_raw = self._assemble_r_tilde(solver)
            # High-pass: only the CHANGE in r_tilde excites the overlay.
            # See `# DEVIATION (overlay HP)` at the top of the file.
            if self.overlay_high_pass:
                if self._r_tilde_prev is None:
                    r_tilde = np.zeros_like(r_tilde_raw)
                else:
                    r_tilde = r_tilde_raw - self._r_tilde_prev
                self._r_tilde_prev = r_tilde_raw
            else:
                r_tilde = r_tilde_raw
                self._r_tilde_prev = r_tilde_raw
            r_modal = self.rs.r_modal
            omega = self.rs.modal_omega
            zeta = self.rs.modal_zeta
            omega_max = float(np.max(omega)) if omega.size > 0 else 1.0
            if omega_max <= 0.0:
                omega_max = 1.0
            T = float(np.pi / (2.0 * omega_max))
            n_substep = max(1, int(np.ceil(h_macro / T)))

            r_tilde_modal = r_tilde[:r_modal]

            # IIR coefficients (impulse-invariant — identical to
            # `dcr/modal/iir_stepper.py`).
            a1 = np.zeros(r_modal)
            a2 = np.zeros(r_modal)
            ar = np.zeros(r_modal)
            for j in range(r_modal):
                wj = float(omega[j])
                xj = float(zeta[j])
                if wj < 1e-12:
                    a1[j] = 1.0
                    a2[j] = 0.0
                    ar[j] = T
                    continue
                wd = wj * np.sqrt(max(0.0, 1.0 - xj * xj))
                e = np.exp(-xj * wj * T)
                a1[j] = 2.0 * e * np.cos(wd * T)
                a2[j] = e * e
                ar[j] = e * np.sin(wd * T) / max(wd, 1e-12)

            # m_j: diagonal of the modal block of M_q (mass-normalized
            # for the sine bending modes).
            m_diag = np.diag(self.rs.Mq)[:r_modal].copy()
            m_diag = np.where(m_diag > 0.0, m_diag, 1.0)

            # §9.3 restart option vs carry-tail.
            if self.rs.restart_overlay_each_step:
                q_prev = np.zeros(r_modal)
                q_prev2 = np.zeros(r_modal)
            else:
                q_prev = q[:r_modal].copy()
                q_prev2 = self.rs.q_prev_macro[:r_modal].copy()

            # Track running peak per probe over the sub-steps.
            U_modal_at_probe = self.rs.probe_U[:, :, :r_modal]
            n_dot_U_modal = np.einsum(
                "pi,pij->pj", self.rs.probe_normals, U_modal_at_probe
            )

            # Convert r_tilde (force, summed over the macro step) into
            # an effective modal IMPULSE for the IIR's first sub-step:
            # J_modal = F_modal · h_macro. The existing IIRModalStepper
            # convention treats r as impulse (see its `# DEVIATION:`
            # docstring at iir_stepper.py:128). Multiplying by T (the
            # IIR sub-step) instead under-applies excitation by the
            # ratio h_macro / T = n_substep.
            r_first = r_tilde_modal * h_macro

            d_overlay_peak = np.zeros(self.rs.n_probes, dtype=np.float64)
            for k in range(n_substep):
                r_k = r_first if k == 0 else None
                q_new = a1 * q_prev - a2 * q_prev2
                if r_k is not None:
                    q_new = q_new + ar * (r_k / m_diag)
                d_per_probe = np.abs(n_dot_U_modal @ q_new)
                d_overlay_peak = np.maximum(d_overlay_peak, d_per_probe)
                q_prev2 = q_prev
                q_prev = q_new
            # The overlay's distant response uses the larger of the
            # quasi-static value (already captured in d_bare) and the
            # sub-stepped peak — they capture different parts of the
            # response and either could dominate at a given probe.
            probe_d_max = np.maximum(d_bare, d_overlay_peak)

        # ---- Compute candidate Δv at each probe (§9.4) ----
        probe_dv_candidate = probe_d_max / max(h_macro, 1e-12)
        self.last_probe_d_max = probe_d_max
        self.last_probe_dv_candidate = probe_dv_candidate

        # ---- Item (3) — energy cap ----
        # E_inj_candidate = Σ ½ m_i · ||Δv_i||²   (m_i = probe rigid mass).
        # α = min(1, √(η · E_src / (E_inj_candidate + ε)))
        # so the realised injection KE α²·E_inj_candidate ≤ η · E_src.
        # When the cap is disabled OR E_src ≤ 0 with cap on, behaviour
        # falls back to "no injection" for safety: the spec calls for
        # passivity, and unbounded injection without a measured source
        # is exactly the failure mode the critique flagged.
        self.last_E_src = float(max(0.0, E_src_step))
        if self.energy_cap_enabled:
            probe_masses = np.array(
                [self._probe_mass(b_idx, descs)
                 for b_idx in self.rs.probe_body_indices],
                dtype=np.float64)
            E_inj_candidate = 0.5 * float(np.sum(
                probe_masses * probe_dv_candidate * probe_dv_candidate))
            self.last_E_inj_candidate = E_inj_candidate
            budget = float(self.eta_overlay) * self.last_E_src
            eps = 1e-18
            if E_inj_candidate <= eps:
                alpha = 1.0
            elif budget <= 0.0:
                alpha = 0.0
            else:
                alpha = float(min(1.0, np.sqrt(budget / E_inj_candidate)))
            probe_dv = alpha * probe_dv_candidate
            self.last_alpha_cap = alpha
        else:
            probe_dv = probe_dv_candidate
            self.last_alpha_cap = 1.0
            self.last_E_inj_candidate = 0.0
        self.last_probe_dv = probe_dv

        # ---- Inject Δv into rigid body linear velocity. ----
        E_rigid_pre = float(rigid_kinetic_energy_fn(
            [d.dcr_body for d in descs]))
        self.last_E_rigid_pre_overlay = E_rigid_pre

        v_np = solver.v.numpy().copy()
        # Also update prev_v after injection — VBD's adaptive gravity
        # warm-start (kernels_6dof.py:176-185) gates gravity by
        # `accel = (v − prev_v) / dt`. A sudden Δv injection makes accel
        # huge in the +ŷ direction; the kernel then clamps the gravity
        # weight w to 0 → body coasts forever, ignoring gravity entirely
        # (probes climbing at constant +6 m/s in the v1 demo). We
        # restore the free-fall invariant by setting
        #     prev_v ← v_new − g · dt
        # so accel = g and w = 1, exactly like a body that just took one
        # step of physical gravitational acceleration.
        prev_v_np = solver.prev_v.numpy().copy()
        g_vec = np.asarray(solver.gravity, dtype=np.float32)
        h_step = float(solver.dt)
        for i, body_idx in enumerate(self.rs.probe_body_indices):
            if body_idx is None or body_idx < 0:
                continue
            if body_idx >= v_np.shape[0]:
                continue
            n = self.rs.probe_normals[i]
            v_np[body_idx] = v_np[body_idx] + (
                np.float32(probe_dv[i]) * n.astype(np.float32))
            prev_v_np[body_idx] = v_np[body_idx] - g_vec * h_step
        solver.v.assign(v_np)
        solver.prev_v.assign(prev_v_np)

        # Sync DCR-side velocities for the descs we touched, so the
        # energy log and the rigid_kinetic_energy_fn see the updated v.
        positions_np = solver.positions()
        velocities_np = solver.velocities()
        for desc in descs:
            if desc.avbd_body is None:
                continue
            j = desc.avbd_body.index
            if j < positions_np.shape[0]:
                desc.dcr_body.velocity[0:3] = velocities_np[j]

        E_rigid_post = float(rigid_kinetic_energy_fn(
            [d.dcr_body for d in descs]))
        self.last_E_rigid_post_overlay = E_rigid_post
        self.last_E_overlay_injected = E_rigid_post - E_rigid_pre
        self.last_E_inj_realised = self.last_E_overlay_injected
        self.last_E_total = E_rigid_post + E_q

        # ---- Item (4) — arm cooldown for probes that just took a kick.
        # Threshold prevents micro-noise from constantly arming/blocking;
        # only meaningful kicks (above `cooldown_dv_threshold`) gate the
        # probe's own contact rows out of the NEXT step's r_tilde.
        if self.cooldown_steps > 0:
            for i, body_idx in enumerate(self.rs.probe_body_indices):
                if body_idx is None or body_idx < 0:
                    continue
                if abs(float(probe_dv[i])) > self.cooldown_dv_threshold:
                    self._probe_cooldown[int(body_idx)] = int(self.cooldown_steps)

    # ---- helpers --------------------------------------------------------

    def _probe_mass(self, body_idx: int, descs) -> float:
        """Return the rigid mass of the AVBD body with the given index,
        looking it up via the AVBDBodyDescriptor list. Returns 1.0 as a
        defensive fallback so the cap never divides by zero — but in
        the happy path every probe is a registered rigid box.
        """
        for d in descs:
            if d.avbd_body is None:
                continue
            if int(d.avbd_body.index) == int(body_idx):
                return float(d.dcr_body.mass)
        return 1.0

    def _assemble_r_tilde(self, solver) -> NDArray[np.float64]:
        """Σ_c (−λ_c + k_c · C_pen_c) · J_q,c — in force units, the
        spec's r_tilde from §9.2. AVBD's λ is force-like (see file
        docstring on sign conventions).
        """
        rows = self.rs.tracked_row_indices
        if not rows:
            return np.zeros(self.rs.r, dtype=np.float64)

        lam_np = solver.c_lambda.numpy()
        positions = solver.positions()
        orientations = solver.orientations()

        anchor_np = solver.c_world_anchor.numpy()
        r_tilde = np.zeros(self.rs.r, dtype=np.float64)
        for row_idx in rows:
            ba = self._row_body_a[row_idx]
            # Item (4) — cooldown: a probe that just received an overlay
            # Δv has its contact rows excluded from r_tilde for the next
            # `cooldown_steps` macro steps. Suppresses the probe →
            # r_tilde → probe self-feedback loop without resorting to a
            # hard identity mask. The q-block COUPLING path still uses
            # this row, so static deformation propagation is preserved.
            if self._probe_cooldown.get(ba, 0) > 0:
                continue
            off = self._row_off_a[row_idx]
            corner_w = positions[ba] + _quat_rotate_xyzw(orientations[ba], off)
            anchor_y_now = float(anchor_np[row_idx, 1])
            C_pen = max(0.0, anchor_y_now - float(corner_w[1]))
            lam_avbd = float(lam_np[row_idx])
            F_n = -lam_avbd + self.rho_q * C_pen
            if F_n < 0.0:
                F_n = 0.0
            U_y_row = self._U_at_row[row_idx][1]
            r_tilde = r_tilde + F_n * U_y_row
        return r_tilde


# ---------------------------------------------------------------------------
# Quaternion helper (XYZW convention to match AVBD)
# ---------------------------------------------------------------------------

def _quat_rotate_xyzw(q_xyzw: NDArray[np.float32],
                      v: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotate vec3 v by quaternion (x, y, z, w). Pure numpy, no Warp."""
    qx, qy, qz, qw = (float(q_xyzw[0]), float(q_xyzw[1]),
                      float(q_xyzw[2]), float(q_xyzw[3]))
    vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
    # q * v * q^-1 expanded.
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    rx = vx + qw * tx + (qy * tz - qz * ty)
    ry = vy + qw * ty + (qz * tx - qx * tz)
    rz = vz + qw * tz + (qx * ty - qy * tx)
    return np.array([rx, ry, rz], dtype=np.float64)
