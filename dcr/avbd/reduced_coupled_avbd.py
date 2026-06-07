"""Reduced-Coordinate Coupled AVBD — Python-side monolithic primal coupler.

This is the true coupled extension of the AVBD solver to reduced-coordinate
support deformation. Unlike `reduced_support_solve.ReducedSupportCoupler`
(which solves an independent r×r q-block per AVBD iteration — block-
coordinate descent), this coupler assembles the full monolithic primal
Newton block over rigid + reduced variables, including the cross-coupling
term ρ·J_x·J_q^T, and applies the Schur-eliminated [Δx; Δq] update inside
`iteration_hook`.

Math (Plan §1 — `/Users/nan/.claude/plans/you-are-working-in-fizzy-waffle.md`):

For each tracked body i, summed over its FLOOR_CONTACT rows j:

  [ H_x,i                  ρ·J_x,i·J_q,i^T ] [Δx_i]     [ -g_x,i ]
  [       H_x,2           ρ·J_x,2·J_q,2^T ] [Δx_2]  =  [ -g_x,2 ]
  [              ...             ...      ] [ ...]     [   ...  ]
  [ ρ·J_q,1·J_x,1^T  ρ·J_q,2·J_x,2^T  H_q ] [ Δq ]     [  -g_q  ]

Reduce by block-Gaussian elimination (H_x is per-body 6×6 — cheap to invert):

  S      = H_q − Σ_i (ρ J_q,i J_x,i^T)·H_x,i⁻¹·(ρ J_x,i J_q,i^T)            (r×r)
  rhs_q  = -g_q + Σ_i (ρ J_q,i J_x,i^T)·H_x,i⁻¹·g_x,i                       (r,)
  Δq     = (S + ε·I)⁻¹·rhs_q
  Δx_i   = -H_x,i⁻¹·(g_x,i + ρ J_x,i J_q,i^T · Δq)

The hook fires AFTER AVBD's per-iter primal+dual round, treating the update
as the "k+½ corrector" warm-starting iter k+1. q is quasi-static — no
M_q·qdot, no D_q·qdot, only K_q·q. `qdot` is held at zero.

# DEVIATION (Plan §1, quasi-static q): the user's spec lists E_kin,q as
# optional. We omit M_q/h² and D_q/h to keep H_q = K_q + Σ ρ J_q J_q^T,
# which is unambiguously the static-rest Hessian. This is intentional;
# adding dynamics is a later step.

# DEVIATION (anchor restoration vs static-only): unlike
# `reduced_support_solve.ReducedSupportCoupler` which restores anchors to
# rest in substep_end_hook, we leave anchors at floor_y_rest + U_y·q after
# the substep so the dual_update's C(x,q) on the next substep starts from
# the deformed state. The substep_begin_hook re-seeds anchors from current
# q anyway, so the only difference is what the OUT-of-substep state looks
# like (matters for cross-substep contact extraction).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .reduced_support import ReducedSupport, evaluate_basis_at_point
from .reduced_support_solve import _quat_rotate_xyzw
from ..modal.exact_resonator import dynamic_compliance_step_precompute


FLOOR_CONTACT_6DOF = 0

# Numerical floor for the passive-quadratic helper.
_PASSIVE_EPS_TINY = 1e-18


def _solve_passive_alpha(a: float, b: float, E_max: float) -> float:
    """Largest α ∈ [0, 1] satisfying  α·b + ½·α²·a  ≤  E_max.

    Foundation §6 / §15: the modal energy increment under uniform
    scaling of an implied impulse is quadratic in α. Same algebra as
    `dcr/modal/passive_inject.py:passive_alpha`, but operating on the
    (a, b, E_max) triple already computed by the caller — this keeps
    the cap arithmetic local to the coupler.

    Edge cases:
    - `a ≤ 0` (no quadratic coupling): degenerate, return α=0
      (any non-trivial cap would require negating direction).
    - Full kick (α=1) already fits: return 1.
    - `E_max < 0`: budget exhausted, return 0.
    """
    if a < _PASSIVE_EPS_TINY:
        return 0.0
    dE_full = b + 0.5 * a
    if dE_full <= E_max:
        return 1.0
    if E_max < 0.0:
        return 0.0
    discr = b * b + 2.0 * a * E_max
    if discr < 0.0:
        return 0.0
    alpha_star = (-b + float(np.sqrt(max(0.0, discr)))) / a
    return float(np.clip(alpha_star, 0.0, 1.0))


def _quat_xyzw_to_R(q_xyzw: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotation matrix from (x, y, z, w) quaternion. Pure numpy."""
    qx, qy, qz, qw = (float(q_xyzw[0]), float(q_xyzw[1]),
                      float(q_xyzw[2]), float(q_xyzw[3]))
    xx = qx * qx; yy = qy * qy; zz = qz * qz
    xy = qx * qy; xz = qx * qz; yz = qy * qz
    wx = qw * qx; wy = qw * qy; wz = qw * qz
    R = np.array([
        [1.0 - 2.0 * (yy + zz),       2.0 * (xy - wz),       2.0 * (xz + wy)],
        [      2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz),       2.0 * (yz - wx)],
        [      2.0 * (xz - wy),       2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ], dtype=np.float64)
    return R


def _quat_xyzw_from_rotvec(rv: NDArray[np.float64]) -> NDArray[np.float64]:
    """exp_q convention used by the AVBD kernel (kernels_6dof.quat_from_rotvec).
    The kernel uses half-angle: q = (sin(θ/2)·n̂, cos(θ/2)).
    """
    theta = float(np.linalg.norm(rv))
    if theta < 1e-12:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    half = 0.5 * theta
    s = np.sin(half) / theta
    return np.array([rv[0] * s, rv[1] * s, rv[2] * s, np.cos(half)],
                    dtype=np.float64)


def _quat_xyzw_mul(a: NDArray[np.float64],
                   b: NDArray[np.float64]) -> NDArray[np.float64]:
    ax, ay, az, aw = a[0], a[1], a[2], a[3]
    bx, by, bz, bw = b[0], b[1], b[2], b[3]
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], dtype=np.float64)


def _quat_xyzw_inv(q: NDArray[np.float64]) -> NDArray[np.float64]:
    n2 = float(q @ q)
    if n2 < 1e-30:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    return np.array([-q[0] / n2, -q[1] / n2, -q[2] / n2, q[3] / n2],
                    dtype=np.float64)


def _quat_xyzw_to_rotvec(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Inverse of _quat_xyzw_from_rotvec. Half-angle convention."""
    s_norm = float(np.linalg.norm(q[:3]))
    if s_norm < 1e-12:
        return np.zeros(3, dtype=np.float64)
    w = float(np.clip(q[3], -1.0, 1.0))
    theta = 2.0 * np.arctan2(s_norm, w)
    return q[:3] * (theta / s_norm)


def _geom_stiffness_diag(n: NDArray[np.float64],
                         r: NDArray[np.float64]) -> NDArray[np.float64]:
    """Mirror of kernels_6dof.geom_stiffness_diag — AVBD Eq 17 column-norm.
    Symmetric PD; added to the angular block scaled by |f|.
    """
    nr = float(n @ r)
    cols = np.zeros(3, dtype=np.float64)
    for c in range(3):
        col = np.zeros(3, dtype=np.float64)
        for i_ in range(3):
            if i_ == c:
                col[i_] = n[i_] * r[c] - nr
            else:
                col[i_] = 0.5 * (n[i_] * r[c] + r[i_] * n[c])
        cols[c] = float(np.linalg.norm(col))
    return cols


@dataclass
class ReducedCoupledAVBDCoupler:
    """Monolithic Python-side coupled primal coupler for AVBD + reduced
    support. See module docstring for math.

    Lifecycle per macro-step:
      substep_begin_hook  — re-identify tracked FLOOR rows for this substep,
                            cache U at each row's rest projection, seed
                            anchors with current q (no predictor — quasi-
                            static).
      iteration_hook(it)  — for every iteration body (primal + dual), build
                            and solve the monolithic block, apply Δq and
                            Δx_i to body state + q.
      substep_end_hook    — final state snapshot for diagnostics; nothing
                            else (no qdot update, anchors stay deformed).
    """

    rs: ReducedSupport

    # AVBD body indices on the shelf (their FLOOR_CONTACT_6DOF rows
    # participate in the coupled solve).
    tracked_body_indices: list[int]

    # Grid metadata for bilinear-interp of U at arbitrary corner (x, z).
    shelf_length: float
    shelf_width: float
    shelf_y_rest: float
    n_grid_x: int
    n_grid_z: int

    h_substep: float = 1.0 / 60.0
    h_macro:   float = 1.0 / 60.0

    # ---- q dynamics --------------------------------------------------------
    # When True the coupler integrates the full second-order modal ODE
    # (M_q q̈ + D_q q̇ + K_q q = -Σ f_j · U_y) via BDF1 inside the coupled
    # primal — q has inertia, can overshoot, and rings at the modal
    # frequencies until D_q damps it out. The distant probes feel this
    # ringing through their FLOOR anchors `floor_y_rest + U_y·q` and the
    # AVBD contact response (no Δv injection — the transient propagates
    # purely through the AL coupling).
    #
    # When False the q-block is quasi-static (no M_q, no D_q): every
    # iteration q jumps to the algebraic equilibrium K_q⁻¹·F. Useful as
    # a reference for proving the static fixed point; not what you want
    # for a real-time demo.
    #
    # Default True — this is the natural physical extension of the
    # quasi-static prototype and matches the same time discretization
    # the static-only BCD coupler uses (h_substep-based BDF1).
    dynamic_q: bool = True

    # Modal integrator choice:
    #   "iir"  — Exact damped-oscillator response per substep (paper Eq. 10
    #            in state-space form). Closed-form q_free, qdot_free, S(h),
    #            T(h) precomputed once per substep from (ω_i, ζ_i, m_i, h).
    #            ZERO discretization error in the modal ODE under the
    #            constant-F-over-h assumption. q stays a primal AVBD
    #            variable; AVBD's Newton loop converges the coupled
    #            (x, q) state. After convergence, the implied per-mode
    #            force F_i = (q_{n+1,i} − q_free_i) / S_i(h) is used to
    #            update qdot = qdot_free + T(h)·F. Default.
    #   "bdf1" — Backward Euler. L-stable. ζ_num ≈ ω·h/2 per substep
    #            annihilates lightly damped vibrations. Kept for the
    #            ablation table (--mode coupled_modal_bdf1).
    q_integrator: str = "iir"

    # Effective ρ per row is clamped at this value before entering the
    # cross-coupling block; AVBD's escalation pushes ρ → PENALTY_MAX = 1e9
    # which would blow up the Schur correction. Warn-on-hit. NOTE:
    # AVBD's PENALTY_MIN for FLOOR rows is 1e6, so anything ≤ 1e6 makes
    # rho_clip identically equal to the row floor — useless. Default 1e9
    # = PENALTY_MAX; below that, clip is informational.
    rho_clip: float = 1.0e9

    # Solver regulariser auto-scaled inside iteration_hook so that
    #   ε = max(eps_baseline · trace(K_q)/r,
    #           eps_cross_factor · max_i ρ²·||J_x,i||²/m_i)
    # keeps S well-conditioned.
    eps_baseline: float = 1.0e-8
    eps_cross_factor: float = 1.0e-6

    # When True, populate `last_Schur_condition_estimate` per iteration via
    # `np.linalg.cond(S_reg)`. r×r cond is O(r³); for small r this is cheap
    # but uncapped. Default off so the production hook doesn't pay the cost.
    # Tests that assert on cond MUST set this to True at attach time.
    diagnostic_mode: bool = False

    # Body mass cache (filled at attach by world).
    body_mass: dict[int, float] = field(default_factory=dict)

    # ---- IIR exact-resonator workspace ----
    # Populated by substep_begin_hook when q_integrator == "iir" (default).
    #   q_free, qdot_free  — analytical free-decay response of each mode
    #                        over the substep (no contact force).
    #   S_h, T_h           — full (r×r) displacement compliance and
    #                        velocity force gain over the substep. Dense
    #                        because Mq/Kq/Dq are not in the eigenbasis
    #                        for the synthetic plate-bending + bump basis.
    #   S_h_inv            — cached r×r inverse of S_h; enters H_q.
    #   last_modal_F       — implied per-mode force at substep end,
    #                        F = S_h⁻¹ · (q_{n+1} − q_free).
    # All None until the first substep_begin_hook fires.
    q_free:      NDArray[np.float64] | None = None
    qdot_free:   NDArray[np.float64] | None = None
    S_h:         NDArray[np.float64] | None = None
    T_h:         NDArray[np.float64] | None = None
    S_h_inv:     NDArray[np.float64] | None = None
    last_modal_F: NDArray[np.float64] | None = None

    # ---- Substep-resolution logging ----
    # When True, every substep_end_hook pushes a dict snapshot to
    # `substep_log`. This is what's needed to see the impact transient
    # (~ms timescale) that's gone by the first per-frame sample. Off by
    # default — frames-only logging is enough for steady-state work.
    log_substeps: bool = False
    substep_log: list[dict] = field(default_factory=list)
    # Monotonic substep counter across all macro steps.
    _substep_index: int = 0

    # Reused row caches across iterations within a substep.
    _U_at_row: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_body_a: dict[int, int] = field(default_factory=dict)
    _row_off_a:  dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_floor_y_rest: dict[int, float] = field(default_factory=dict)
    _rows_per_body: dict[int, list[int]] = field(default_factory=dict)

    # Instrumentation (asserted by tests).
    last_q_norm: float = 0.0
    last_qdot_norm: float = 0.0
    last_max_support_deflection: float = 0.0
    last_contact_residual: float = 0.0
    last_Schur_condition_estimate: float = 0.0
    last_n_iter_solves: int = 0
    last_max_dx_norm: float = 0.0
    last_max_dtheta_norm: float = 0.0
    last_dq_norm: float = 0.0
    last_n_tracked_rows: int = 0
    last_rho_clip_hits: int = 0
    cum_overlay_events_fired: int = 0
    last_overlay_events_fired: int = 0
    # Per-iter dq history (last substep, last iteration body).
    last_iter_dq_norms: list[float] = field(default_factory=list)
    # Energy diagnostics (populated in substep_end_hook):
    #   KE  = ½ qdot^T M_q qdot           (modal kinetic)
    #   PE  = ½  q  ^T K_q  q             (modal potential)
    #   P_d =     qdot^T D_q qdot ≥ 0     (instantaneous damping power)
    last_modal_KE: float = 0.0
    last_modal_PE: float = 0.0
    last_damp_power: float = 0.0
    # Max |λ| over tracked rows at end of last iteration. Used to
    # disambiguate "creep due to BDF1 over-damping" (flat λ with rising
    # q) from "AL under-convergence" (ramping λ tracking q).
    last_contact_lambda_max: float = 0.0
    # |q̈| at end of last substep. Unused since Newmark removal; kept
    # for backwards-compat with the substep_log schema.
    last_q_acc_norm: float = 0.0
    # IIR diagnostics — min/max S_i(h) over the last substep.
    last_min_S_h: float = 0.0
    last_max_S_h: float = 0.0
    # Defensive counter: incremented if any code path calls
    # `_apply_dcr_velocities` on a body the coupler tracks. In
    # --mode coupled_iir_modal this MUST stay 0 (Test 5). The old
    # DCR post-kick path is the ablation; counter is non-zero only
    # in --mode old_dcr_postkick (which doesn't attach this coupler).
    dcr_postkick_calls: int = 0

    # ---- Passive energy cap (demo knob) ----
    # When `modal_energy_cap_fraction = η` is set, the IIR branch in
    # substep_end_hook clamps the implied modal force F = S_h⁻¹·(q − q_free)
    # so that ΔE_q ≤ η · max(ΔE_rigid_loss, 0) per substep. Disabled by
    # default (None). Engaging it under high `--support-response-gain`
    # introduces a one-substep constraint relaxation; documented as
    # demo-only. See plan §"Energy cap (knob 3)" and foundation §15.
    modal_energy_cap_fraction: float | None = None
    last_alpha_cap: float = 1.0
    cap_engagements: int = 0
    last_dE_modal: float = 0.0
    last_dE_rigid_loss: float = 0.0
    # Internal substep-start snapshots for the cap math.
    _E_q_substep_begin: float = 0.0
    _E_rigid_substep_begin: float = 0.0

    # ---- Artistic jump gain (demo knob II) ----
    # Velocity-derived contact-gap bias. At each tracked FLOOR row r:
    #   v_s    = U_y(corner_r) · qdot                          (modal surface vel.)
    #   v_bar  = one-pole low-pass of v_s, τ = modal_jump_filter_tau
    #   v_lift = min(γ · max(v_s − v_bar, 0), v_max)
    # then  anchor_y_r ← floor_y_rest + U_y·q + h_sub · v_lift_r
    # which the AVBD primal sees as a raised floor → upward push on the
    # body through the existing contact multiplier (no post-fix Δv). The
    # high-pass rejects sustained sag; only transients amplify.
    # γ = 1 is a strict no-op (the per-row computation block is skipped).
    modal_jump_gain:       float = 1.0
    modal_jump_max_height: float = 0.01      # m → v_max ≈ 0.443 m/s
    modal_jump_filter_tau: float = 0.03      # s
    # Persistent low-pass state keyed by (body_idx, offset μm-quantized).
    _jump_v_bar: dict = field(default_factory=dict)
    # Per-row v_lift cache, cleared each substep_begin; consumed by both
    # anchor-write sites within the substep.
    _jump_v_lift: dict = field(default_factory=dict)
    # Diagnostics.
    last_max_v_lift: float = 0.0
    last_max_v_hp:   float = 0.0
    jump_engagements: int = 0

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if self.q_integrator not in ("iir", "bdf1"):
            raise ValueError(
                f"q_integrator must be 'iir' or 'bdf1', got "
                f"{self.q_integrator!r}.")

    def _rigid_KE_tracked(self, solver) -> float:
        """Σ_b ½·m_b·|v_b|² + ½·ω_b^T·I_world_b·ω_b over tracked bodies.

        Used by the passive energy cap to budget per-substep modal
        injection. Reads AVBD-finalised state, so the value is v_n at
        substep_begin (kernel hasn't run yet) and v_{n+1} at substep_end
        (finalize_and_cap_6dof writes solver.v BEFORE the end hook).
        """
        if not self.tracked_body_indices:
            return 0.0
        mass_np  = solver.mass.numpy()
        v_np     = solver.v.numpy()
        omega_np = solver.omega.numpy()
        q_np     = solver.q.numpy()
        I_loc    = solver.inertia_local.numpy()
        E = 0.0
        for b in self.tracked_body_indices:
            m = float(mass_np[b])
            if m <= 0.0 or not np.isfinite(m):
                continue
            v = v_np[b].astype(np.float64)
            w = omega_np[b].astype(np.float64)
            R = _quat_xyzw_to_R(q_np[b].astype(np.float64))
            Iw = R @ I_loc[b].astype(np.float64) @ R.T
            E += 0.5 * m * float(v @ v) + 0.5 * float(w @ (Iw @ w))
        return E

    def substep_begin_hook(self, solver) -> None:
        """Walk solver._rows, identify FLOOR rows on tracked bodies,
        cache row metadata and U_y at the corner's rest projection,
        seed anchors at floor_y_rest + U_y·q_hat (BDF1 predictor when
        dynamic_q is True, q itself when quasi-static).
        """
        if not self.rs.enabled:
            return

        # Snapshot q at substep start for the BDF1 qdot update at
        # substep_end_hook AND for the implicit-damping gradient
        # qdot_{n+1} = (q − q_n)/h inside iteration_hook.
        #
        # NOTE on naming: the field is called `q_prev_macro` on the
        # ReducedSupport struct (legacy from the static-only BCD
        # coupler that snapshotted per-macro-step). Here we overwrite
        # it at every substep_begin_hook, so its semantics is
        # "q at the start of the *current* substep" — i.e. q_n.
        self.rs.q_prev_macro = self.rs.q.copy()

        # Substep-start energy snapshots for the passive energy cap.
        # Computed unconditionally (cheap) so diagnostics stay consistent
        # whether the cap is engaged or not.
        Mq_ = self.rs.Mq
        Kq_ = self.rs.Kq
        qn = self.rs.q
        qdn = self.rs.qdot
        self._E_q_substep_begin = (
            0.5 * float(qdn @ (Mq_ @ qdn))
            + 0.5 * float(qn @ (Kq_ @ qn)))
        self._E_rigid_substep_begin = self._rigid_KE_tracked(solver)

        if self.dynamic_q:
            if self.q_integrator == "iir":
                # Precompute the full r×r exact damped-oscillator
                # response over this substep (paper Eq. 10 in
                # state-space matrix-exponential form). Handles
                # non-diagonal Mq/Kq/Dq natively.
                q_free, qdot_free, S_h, T_h = (
                    dynamic_compliance_step_precompute(
                        self.rs.q, self.rs.qdot,
                        self.rs.Mq, self.rs.Kq, self.rs.Dq,
                        self.h_substep))
                # S_h is r×r dense; invert once per substep, cache.
                S_h_inv = np.linalg.inv(S_h)
                self.q_free   = q_free
                self.qdot_free = qdot_free
                self.S_h      = S_h
                self.T_h      = T_h
                self.S_h_inv  = S_h_inv
                diag_S = np.diag(S_h)
                self.last_min_S_h = float(diag_S.min())
                self.last_max_S_h = float(diag_S.max())
                # Warm-start the Newton iterations from the free response.
                self.rs.q       = q_free.copy()
                self.rs.q_hat   = q_free.copy()
            else:  # bdf1
                self.rs.q_hat = self.rs.q + self.h_substep * self.rs.qdot
        else:
            self.rs.q_hat = self.rs.q.copy()

        anchor_np = solver.c_world_anchor.numpy().copy()
        off_a_np = solver.c_off_a.numpy().copy()
        body_a_np = solver.c_body_a.numpy()
        type_np = solver.c_type.numpy()

        self._U_at_row.clear()
        self._row_body_a.clear()
        self._row_off_a.clear()
        self._row_floor_y_rest.clear()
        self._rows_per_body.clear()
        tracked: list[int] = []

        for i, row in enumerate(solver._rows):
            if row.type != FLOOR_CONTACT_6DOF:
                continue
            ba = int(body_a_np[i])
            if ba not in self.tracked_body_indices:
                continue
            tracked.append(i)
            self._row_body_a[i] = ba
            self._row_off_a[i] = off_a_np[i].astype(np.float64)
            if i not in self.rs.floor_y_rest:
                self.rs.floor_y_rest[i] = float(anchor_np[i, 1])
            self._row_floor_y_rest[i] = self.rs.floor_y_rest[i]
            self._rows_per_body.setdefault(ba, []).append(i)

        self.rs.tracked_row_indices = tracked
        self.last_n_tracked_rows = len(tracked)
        self.last_n_iter_solves = 0
        self.last_iter_dq_norms = []

        if not tracked:
            return

        positions = solver.positions()
        orientations = solver.orientations()
        for row_idx in tracked:
            ba = self._row_body_a[row_idx]
            off = self._row_off_a[row_idx]
            qb_xyzw = orientations[ba]
            r_world = _quat_rotate_xyzw(qb_xyzw, off)
            corner_w = positions[ba] + r_world
            U_pt = evaluate_basis_at_point(
                self.rs,
                (float(corner_w[0]), float(corner_w[2])),
                length=self.shelf_length,
                width=self.shelf_width,
                n_grid_x=self.n_grid_x,
                n_grid_z=self.n_grid_z,
            )
            self._U_at_row[row_idx] = U_pt

        # Artistic jump-gain: compute per-row upward lift velocity.
        # No-op when γ = 1.0 (regression-safe default).
        self._jump_v_lift.clear()
        any_lift = False
        if self.modal_jump_gain != 1.0 and self.q_integrator == "iir":
            h_sub = float(self.h_substep)
            tau = float(self.modal_jump_filter_tau)
            alpha = h_sub / (tau + h_sub) if (tau + h_sub) > 0.0 else 1.0
            gamma = float(self.modal_jump_gain)
            v_max = float(np.sqrt(
                2.0 * 9.81 * max(self.modal_jump_max_height, 0.0)))
            qdot = self.rs.qdot
            max_v_lift = 0.0
            max_v_hp = 0.0
            for row_idx in tracked:
                ba = self._row_body_a[row_idx]
                off = self._row_off_a[row_idx]
                off_key = (
                    int(ba),
                    int(round(float(off[0]) * 1e6)),
                    int(round(float(off[1]) * 1e6)),
                    int(round(float(off[2]) * 1e6)))
                U_y = self._U_at_row[row_idx][1]
                v_s = float(U_y @ qdot)
                v_bar_prev = self._jump_v_bar.get(off_key, 0.0)
                v_bar = (1.0 - alpha) * v_bar_prev + alpha * v_s
                self._jump_v_bar[off_key] = v_bar
                v_hp = v_s - v_bar
                v_up = v_hp if v_hp > 0.0 else 0.0
                v_lift = gamma * v_up
                if v_lift > v_max:
                    v_lift = v_max
                if v_lift > 0.0:
                    self._jump_v_lift[row_idx] = v_lift
                    any_lift = True
                if v_lift > max_v_lift:
                    max_v_lift = v_lift
                if v_hp > max_v_hp:
                    max_v_hp = v_hp
            self.last_max_v_lift = float(max_v_lift)
            self.last_max_v_hp = float(max_v_hp)
            if any_lift:
                self.jump_engagements += 1
        else:
            self.last_max_v_lift = 0.0
            self.last_max_v_hp = 0.0

        # Seed anchors using the predictor (q_hat = q + h·qdot when
        # dynamic, q itself when quasi-static). AVBD's primal sees this
        # anchor as the "predicted" support position; subsequent
        # iteration_hook calls advance q toward the AL minimum and
        # rewrite the anchor each iter.
        anchor_new = anchor_np.copy()
        q_seed = self.rs.q_hat
        h_sub_for_anchor = float(self.h_substep)
        for row_idx in tracked:
            U_y = self._U_at_row[row_idx][1]
            dy = float(U_y @ q_seed)
            v_lift = self._jump_v_lift.get(row_idx, 0.0)
            anchor_new[row_idx, 1] = (
                self._row_floor_y_rest[row_idx] + dy
                + h_sub_for_anchor * v_lift)
        solver.c_world_anchor.assign(anchor_new.astype(np.float32))

    def iteration_hook(self, solver, iter_idx: int) -> None:
        """The monolithic Schur solve. See module docstring.
        Applies Δq to self.rs.q AND Δx_i to each tracked body's state.
        """
        if not self.rs.enabled:
            return
        rows = self.rs.tracked_row_indices
        if not rows:
            return

        # Pull state once per iteration.
        lam_np = solver.c_lambda.numpy()
        pen_np = solver.c_penalty.numpy()
        fmin_np = solver.c_fmin.numpy()
        fmax_np = solver.c_fmax.numpy()
        alpha_C0_np = solver.c_alpha_C0.numpy()
        stiff_np = solver.c_stiffness.numpy()
        anchor_np = solver.c_world_anchor.numpy().copy()
        positions_np = solver.x.numpy().copy()
        orientations_np = solver.q.numpy().copy()      # (n_b, 4) XYZW
        mass_np = solver.mass.numpy()
        inertia_local_np = solver.inertia_local.numpy()
        x_inertial_np = solver.x_inertial.numpy()
        q_inertial_np = solver.q_inertial.numpy()

        h = float(self.h_substep)
        inv_dt2 = 1.0 / (h * h)
        r = self.rs.r
        Kq = self.rs.Kq
        Mq = self.rs.Mq
        Dq = self.rs.Dq

        # Reset per-iter accumulators — modal-side baseline H_q / g_q.
        # Quasi-static (dynamic_q=False):
        #     H_q = K_q ,                 g_q = K_q·q
        # Dynamic + BDF1:
        #     H_q = M_q/h² + K_q + D_q/h ,
        #     g_q = M_q/h² · (q − q_hat) + K_q·q + D_q · (q − q_n)/h
        # Dynamic + IIR (exact resonator, paper Eq. 10):
        #     H_q^modal = diag(1 / S_i(h)) ,
        #     g_q^modal = (q − q_free) / S
        # where S_i(h), q_free are precomputed in substep_begin_hook.
        # The IIR branch is fully decoupled per mode at the modal-only
        # level (diagonal H_q baseline). Contact contributions add the
        # rank-k update Σ_j ρ_j · U_y,j ⊗ U_y,j the same way for all
        # three branches.
        if self.dynamic_q:
            if self.q_integrator == "iir":
                # Defensive: substep_begin_hook should have populated
                # these. If not, treat as quasi-static fallback.
                if self.S_h_inv is None or self.q_free is None:
                    H_q = Kq.copy()
                    g_q = Kq @ self.rs.q
                else:
                    H_q = self.S_h_inv.copy()
                    g_q = self.S_h_inv @ (self.rs.q - self.q_free)
            else:  # bdf1
                # # DEVIATION (audit-fix): qdot in g_q is the implicit
                # (q_{n+1} − q_n)/h to match H_q = M/h² + K + D/h.
                qdot_implicit = (self.rs.q - self.rs.q_prev_macro) / h
                H_q = inv_dt2 * Mq + Kq + (1.0 / h) * Dq
                g_q = (inv_dt2 * (Mq @ (self.rs.q - self.rs.q_hat))
                       + Kq @ self.rs.q
                       + Dq @ qdot_implicit)
        else:
            H_q = Kq.copy()
            g_q = Kq @ self.rs.q

        per_body_Hx_inv: dict[int, NDArray[np.float64]] = {}
        per_body_gx:     dict[int, NDArray[np.float64]] = {}
        per_body_cross:  dict[int, NDArray[np.float64]] = {}  # 6 x r

        max_rho2_over_m = 0.0
        rho_hits = 0

        # Build per-body 6×6 H_x + 6-vec g_x + 6×r cross.
        for body_idx, rows_on_body in self._rows_per_body.items():
            m = float(mass_np[body_idx])
            if m <= 0.0 or not np.isfinite(m):
                continue
            q_xyzw = orientations_np[body_idx].astype(np.float64)
            x_curr = positions_np[body_idx].astype(np.float64)
            x_iner = x_inertial_np[body_idx].astype(np.float64)
            q_iner = q_inertial_np[body_idx].astype(np.float64)

            R = _quat_xyzw_to_R(q_xyzw)
            I_local = inertia_local_np[body_idx].astype(np.float64)
            I_world = R @ I_local @ R.T

            # Inertial part.
            A = m * inv_dt2 * np.eye(3)
            D = I_world * inv_dt2
            B = np.zeros((3, 3), dtype=np.float64)

            r_lin = m * inv_dt2 * (x_curr - x_iner)
            # World-frame inertial Δθ: q ⊗ q_iner^-1 → rotvec.
            dq_iner = _quat_xyzw_mul(q_xyzw, _quat_xyzw_inv(q_iner))
            dtheta_iner = _quat_xyzw_to_rotvec(dq_iner)
            r_ang = I_world @ (dtheta_iner * inv_dt2)

            cross_body = np.zeros((6, r), dtype=np.float64)

            for row_idx in rows_on_body:
                off = self._row_off_a[row_idx]
                r_self_w = R @ off
                n_hat = np.array([0.0, 1.0, 0.0], dtype=np.float64)
                j_lin = n_hat
                j_ang = np.cross(r_self_w, n_hat)

                C = (x_curr[1] + r_self_w[1]) - float(anchor_np[row_idx, 1])
                s_stiff = float(stiff_np[row_idx])
                hard = np.isinf(s_stiff)
                if hard:
                    C = C - float(alpha_C0_np[row_idx])

                lam_eff = float(lam_np[row_idx]) if hard else 0.0
                rho = float(pen_np[row_idx])
                # Clamp the per-row penalty entering the cross block so
                # the Schur correction (~ρ²) stays bounded.
                rho_used = min(rho, self.rho_clip)
                if rho >= self.rho_clip:
                    rho_hits += 1

                f_lo = float(fmin_np[row_idx])
                f_hi = float(fmax_np[row_idx])
                lam_plus = rho_used * C + lam_eff
                f = float(np.clip(lam_plus, f_lo, f_hi))

                # Eq.14 LHS rescale (mirror kernels_6dof.py:541-547).
                k_for_lhs = rho_used
                abs_C = abs(C)
                if abs_C > 1.0e-12:
                    if lam_plus < f_lo:
                        k_for_lhs = abs(f_lo - lam_plus) / abs_C
                    elif lam_plus > f_hi:
                        k_for_lhs = abs(f_hi - lam_plus) / abs_C

                # LHS outer-product accumulations.
                A = A + k_for_lhs * np.outer(j_lin, j_lin)
                B = B + k_for_lhs * np.outer(j_ang, j_lin)
                D = D + k_for_lhs * np.outer(j_ang, j_ang)

                # Geometric stiffness on D (only if f≠0).
                f_mag = abs(f)
                if f_mag > 0.0:
                    g_diag = _geom_stiffness_diag(n_hat, r_self_w) * f_mag
                    D = D + np.diag(g_diag)

                # RHS gradient contributions.
                r_lin = r_lin + j_lin * f
                r_ang = r_ang + j_ang * f

                # Reduced Jacobian and q-side contributions.
                U_y_row = self._U_at_row[row_idx][1]
                # Note: ∂C/∂q = −U_y_row (anchor moves DOWN by U_y·q).
                # In our convention C = corner_y − anchor_y, so the q
                # gradient enters g_q with a MINUS sign on f times the
                # contact jacobian dC/dq = -U_y_row. With g_q being the
                # AL gradient w.r.t. q, the contact term is +f · (dC/dq)·
                # which yields g_q += -f·U_y_row. But the existing
                # static-only coupler uses g_q += F_n·U_y_row where
                # F_n = -lam + ρ·C+ — that's because dC/dq carries a
                # sign flip absorbed into the F_n definition. We follow
                # the explicit convention: g_q -= f · U_y_row to be
                # self-consistent with the AVBD kernel's f sign.
                # FLOOR rows have fmax = 0 → f ≤ 0 (compressive). The
                # support is pushed DOWN by a downward-pointing q.
                g_q = g_q - f * U_y_row
                H_q = H_q + k_for_lhs * np.outer(U_y_row, U_y_row)

                # Cross block: cross_body[:3,:] += k_for_lhs · j_lin · U_y^T
                #              cross_body[3:,:] += k_for_lhs · j_ang · U_y^T
                # The sign: ∂²L/∂x∂q = -ρ · J_x · U_y^T (since dC/dx = J_x,
                # dC/dq = -U_y_row). In the [Δx;Δq] block, the off-diag
                # entry is -ρ J_x U_y^T. We accumulate the magnitude and
                # apply the sign at the global block assembly.
                cross_body[:3, :] += k_for_lhs * np.outer(j_lin, U_y_row)
                cross_body[3:, :] += k_for_lhs * np.outer(j_ang, U_y_row)

                max_rho2_over_m = max(
                    max_rho2_over_m,
                    (rho_used ** 2) * float(j_lin @ j_lin + j_ang @ j_ang) / max(m, 1e-12),
                )

            # Assemble per-body 6×6 H_x and 6-vec g_x.
            H_x = np.block([
                [A,           B.T],
                [B,           D  ],
            ])
            g_x = np.concatenate([r_lin, r_ang])

            # Regularise H_x with a tiny ε for numerical safety.
            H_x_reg = H_x + 1e-12 * np.eye(6)
            try:
                H_x_inv = np.linalg.inv(H_x_reg)
            except np.linalg.LinAlgError:
                continue
            per_body_Hx_inv[body_idx] = H_x_inv
            per_body_gx[body_idx] = g_x
            # Cross block enters the global system with a MINUS sign per
            # the AL convention above.
            per_body_cross[body_idx] = -cross_body

        # ---- Schur assembly over q ----
        # S = H_q − Σ cross^T · H_x_inv · cross
        # rhs_q = -g_q + Σ cross^T · H_x_inv · g_x
        # (We write the cross block as M = -ρ J_x U_y^T; M.T M removes
        #  the sign so S has the same form regardless.)
        rhs_q = -g_q
        S = H_q.copy()
        for body_idx in per_body_Hx_inv:
            M = per_body_cross[body_idx]              # (6, r)  (signed)
            Hxi = per_body_Hx_inv[body_idx]           # (6, 6)
            gxi = per_body_gx[body_idx]               # (6,)
            # H_x_inv · M  (6 x r)
            Hxi_M = Hxi @ M
            S = S - M.T @ Hxi_M
            rhs_q = rhs_q + M.T @ Hxi @ gxi

        # ε regulariser auto-scaled to keep S PD.
        eps = max(
            self.eps_baseline * (float(np.trace(Kq)) / max(r, 1)),
            self.eps_cross_factor * max_rho2_over_m,
        )
        S_reg = S + eps * np.eye(r)

        # Schur solve.
        try:
            dq = np.linalg.solve(S_reg, rhs_q)
        except np.linalg.LinAlgError:
            return

        # Track conditioning (cheap-ish r×r) — gated since cond(r×r) is
        # O(r³) and we don't want to pay it in production. Tests opt in
        # by setting `coupler.diagnostic_mode = True`.
        if self.diagnostic_mode:
            try:
                cond = float(np.linalg.cond(S_reg))
            except Exception:
                cond = float('inf')
            self.last_Schur_condition_estimate = min(cond, 1e16)

        # Apply Δq.
        q_new = self.rs.q + dq
        self.rs.q = q_new

        # Back-substitute for each tracked body.
        max_dx = 0.0
        max_dtheta = 0.0
        x_out = positions_np.copy()
        q_out = orientations_np.copy()
        for body_idx, Hxi in per_body_Hx_inv.items():
            M = per_body_cross[body_idx]              # (6, r)
            gxi = per_body_gx[body_idx]
            # H_x · Δ[x;θ] = -(g_x + M · Δq)
            rhs6 = -(gxi + M @ dq)
            delta = Hxi @ rhs6                        # (6,)
            d_x = delta[:3]
            d_theta = delta[3:]
            # Apply: kernel does x ← x − d_x and q ← exp_q(−d_theta)⊗q.
            # We computed delta = -Hxi·(g+M·dq) — that's the AVBD Δ on
            # the LHS, which the kernel SUBTRACTS. So we add delta (NOT
            # subtract) to match: x_new = x_curr − (kernel's d_x) where
            # kernel's d_x = -delta_x, so x_new = x_curr + delta[:3]?
            # Mirror the kernel directly: x ← x − d_x where d_x is the
            # solution of [A B^T;B D][d_x;d_theta] = [r_lin; r_ang] with
            # POSITIVE r_lin/r_ang. Our g_x = r_lin/r_ang (positive). Our
            # Δ from Schur is the solution of H_x·Δ = −(g_x + M·dq), i.e.
            # Δ = -H_x_inv·(g_x + ρ·J_x·J_q^T·dq). The kernel's d_x is
            # +H_x_inv·g_x (positive) and updates x ← x − d_x. So our Δ
            # = -kernel_dx, and we should update x ← x − (−Δ) = x + Δ ...
            # but cross-coupling already enters Δ. The net rule: apply
            # x ← x − (−Δ_lin) = x + Δ_lin = x_curr + delta[:3].
            # (See test_double_update_consistency for confirmation.)
            x_out[body_idx] = (positions_np[body_idx]
                               + delta[:3].astype(np.float32))
            # Orientation: kernel does q ← exp_q(−d_theta)⊗q where d_theta
            # is the positive-Schur soln. Our Δ_theta = -d_theta, so we
            # apply q ← exp_q(Δ_theta) ⊗ q with rotvec = delta[3:].
            dq_quat = _quat_xyzw_from_rotvec(delta[3:])
            new_q = _quat_xyzw_mul(dq_quat, q_out[body_idx].astype(np.float64))
            n = float(np.linalg.norm(new_q))
            if n > 1e-12:
                new_q = new_q / n
            q_out[body_idx] = new_q.astype(np.float32)
            max_dx = max(max_dx, float(np.linalg.norm(d_x)))
            max_dtheta = max(max_dtheta, float(np.linalg.norm(d_theta)))

        # Write back state.
        solver.x.assign(x_out)
        solver.q.assign(q_out)

        # Update anchors to reflect new q (for next iter's dual + primal).
        anchor_out = anchor_np.copy()
        h_sub_for_anchor = float(self.h_substep)
        for row_idx in rows:
            U_y = self._U_at_row[row_idx][1]
            dy = float(U_y @ q_new)
            v_lift = self._jump_v_lift.get(row_idx, 0.0)
            anchor_out[row_idx, 1] = (
                self._row_floor_y_rest[row_idx] + dy
                + h_sub_for_anchor * v_lift)
        solver.c_world_anchor.assign(anchor_out.astype(np.float32))

        self.last_max_dx_norm = max_dx
        self.last_max_dtheta_norm = max_dtheta
        self.last_dq_norm = float(np.linalg.norm(dq))
        self.last_n_iter_solves += 1
        self.last_iter_dq_norms.append(self.last_dq_norm)
        self.last_rho_clip_hits = rho_hits

    def substep_end_hook(self, solver) -> None:
        """Finalise the substep: advance qdot from the substep's q delta
        (BDF1) and compute diagnostics. Anchors stay deformed across
        substeps (the next substep_begin_hook re-seeds them anyway).
        """
        if not self.rs.enabled:
            return

        # Advance qdot.
        # IIR:  F_i = (q_{n+1,i} − q_free_i) / S_i(h)
        #       qdot_{n+1} = qdot_free + T(h)·F
        #       (NO finite-difference fallback: the velocity is the
        #        analytical response under the implied substep force.)
        # BDF1: qdot_{n+1} = (q − q_n) / h
        # Quasi-static: qdot ≡ 0 (algebraic equilibrium each step).
        h = float(self.h_substep)
        if self.dynamic_q and h > 0.0:
            if self.q_integrator == "iir":
                if (self.q_free is not None and self.qdot_free is not None
                        and self.S_h_inv is not None
                        and self.T_h is not None):
                    # Implied modal force from this substep's q result.
                    F_full = self.S_h_inv @ (self.rs.q - self.q_free)
                    qdot_full = self.qdot_free + self.T_h @ F_full
                    q_full = self.rs.q.copy()
                    alpha = 1.0
                    Mq = self.rs.Mq
                    Kq = self.rs.Kq

                    if self.modal_energy_cap_fraction is not None:
                        # Passive energy cap (foundation §15):
                        #   ΔE_q(α) ≤ η · max(ΔE_rigid_loss, 0)
                        # E_q(α) = ½(qdot_free + α·Δqdot)^T Mq (...)
                        #        + ½(q_free   + α·Δq   )^T Kq (...)
                        # Subtract E_q^old → α·b + ½·α²·a + dE_base.
                        E_rigid_end = self._rigid_KE_tracked(solver)
                        dE_rigid_loss = (
                            self._E_rigid_substep_begin - E_rigid_end)
                        E_budget = (
                            float(self.modal_energy_cap_fraction)
                            * max(dE_rigid_loss, 0.0))
                        dq    = q_full    - self.q_free
                        dqdot = qdot_full - self.qdot_free
                        a_quad = (float(dqdot @ (Mq @ dqdot))
                                  + float(dq @ (Kq @ dq)))
                        b_lin = (
                            float(self.qdot_free @ (Mq @ dqdot))
                            + float(self.q_free   @ (Kq @ dq)))
                        E_q_free = (
                            0.5 * float(self.qdot_free @ (Mq @ self.qdot_free))
                            + 0.5 * float(self.q_free   @ (Kq @ self.q_free)))
                        dE_base = E_q_free - self._E_q_substep_begin
                        # DEVIATION (foundation §15): the cap clips the
                        # implied modal F uniformly. The rigid state
                        # advanced under the unscaled F, so a clamped α
                        # introduces a small one-substep constraint
                        # inconsistency restored on the next substep.
                        # Demo-only at high --support-response-gain.
                        alpha = _solve_passive_alpha(
                            a_quad, b_lin, E_budget - dE_base)
                        self.last_dE_rigid_loss = float(dE_rigid_loss)
                    else:
                        self.last_dE_rigid_loss = 0.0

                    if alpha < 1.0 - 1e-12:
                        self.rs.q = (self.q_free
                                     + alpha * (q_full - self.q_free))
                        self.rs.qdot = (self.qdot_free
                                        + alpha * (qdot_full - self.qdot_free))
                        self.last_modal_F = alpha * F_full
                        self.cap_engagements += 1
                    else:
                        self.rs.q = q_full
                        self.rs.qdot = qdot_full
                        self.last_modal_F = F_full
                    self.last_alpha_cap = float(alpha)
                    # ΔE_modal under the (possibly clamped) final state.
                    self.last_dE_modal = (
                        0.5 * float(self.rs.qdot @ (Mq @ self.rs.qdot))
                        + 0.5 * float(self.rs.q   @ (Kq @ self.rs.q))
                        - self._E_q_substep_begin)
                else:
                    # Pre-warm fallback (first substep before precompute).
                    self.rs.qdot[:] = 0.0
                    self.last_modal_F = np.zeros_like(self.rs.q)
                    self.last_alpha_cap = 1.0
                    self.last_dE_modal = 0.0
                    self.last_dE_rigid_loss = 0.0
            else:  # bdf1
                self.rs.qdot = (self.rs.q - self.rs.q_prev_macro) / h
        else:
            self.rs.qdot[:] = 0.0

        # |q|, |qdot| and max surface deflection from final q.
        q = self.rs.q
        self.last_q_norm = float(np.linalg.norm(q))
        self.last_qdot_norm = float(np.linalg.norm(self.rs.qdot))
        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
        else:
            self.last_max_support_deflection = 0.0

        # Modal energy diagnostics — used by V4 (passivity test) and the
        # energy_budget figure.
        #   KE_q  = ½ qdot^T M_q qdot     (kinetic, ≥ 0 since M_q PD)
        #   PE_q  = ½ q   ^T K_q  q       (potential, ≥ 0 since K_q PD)
        #   P_d   =   qdot^T D_q qdot     (damping power, ≥ 0 since D_q PSD)
        Mq = self.rs.Mq
        Kq = self.rs.Kq
        Dq = self.rs.Dq
        qdot = self.rs.qdot
        self.last_modal_KE = 0.5 * float(qdot @ (Mq @ qdot))
        self.last_modal_PE = 0.5 * float(q @ (Kq @ q))
        self.last_damp_power = float(qdot @ (Dq @ qdot))
        # |q̈| was Newmark-specific; held at 0 after the Newmark
        # removal. Kept in the substep_log schema for backwards-compat.
        self.last_q_acc_norm = 0.0
        # Track λ across tracked rows. AVBD's dual update bumps λ
        # toward `λ + ρ·C` each iteration; if the AL is converged C ≈ 0
        # so λ stabilises. A ramping λ that tracks q indicates AL
        # under-convergence (need more iterations or stronger ρ).
        rows_tr = self.rs.tracked_row_indices
        if rows_tr:
            lam_np_end = solver.c_lambda.numpy()
            self.last_contact_lambda_max = float(
                np.max(np.abs(lam_np_end[rows_tr])))
        else:
            self.last_contact_lambda_max = 0.0

        # Substep-resolution log entry. Cheap (single dict / arrays);
        # opt-in via `log_substeps`. Used by the energy logger to see
        # the impact transient that frame-rate sampling misses.
        if self.log_substeps:
            self.substep_log.append({
                "substep_index": int(self._substep_index),
                "t_substep_s":   float(self._substep_index * h),
                "q_norm_m":      self.last_q_norm,
                "qdot_norm":     self.last_qdot_norm,
                "q_acc_norm":    self.last_q_acc_norm,
                "KE_modal_J":    self.last_modal_KE,
                "PE_modal_J":    self.last_modal_PE,
                "P_damp_W":      self.last_damp_power,
                "contact_lambda_max": self.last_contact_lambda_max,
                "max_support_deflection_m": self.last_max_support_deflection,
                "n_iter_solves": int(self.last_n_iter_solves),
            })
        self._substep_index += 1

        # Contact residual: max PENETRATION over tracked rows (max(0, -C)).
        # `add_floor_contact_box` emits one row per box corner — top corners
        # have C ≈ +full_height and would dominate a |C| max. We care only
        # about *penetration* (C < 0 in the kernel sign), which is the
        # AL feasibility error.
        rows = self.rs.tracked_row_indices
        if not rows:
            self.last_contact_residual = 0.0
            return
        positions = solver.positions()
        orientations = solver.orientations()
        anchor_np = solver.c_world_anchor.numpy()
        max_pen = 0.0
        for row_idx in rows:
            ba = self._row_body_a[row_idx]
            off = self._row_off_a[row_idx]
            r_world = _quat_rotate_xyzw(orientations[ba], off)
            corner_y = float(positions[ba, 1] + r_world[1])
            anchor_y = float(anchor_np[row_idx, 1])
            C = corner_y - anchor_y
            if C < 0.0:
                max_pen = max(max_pen, -C)
        self.last_contact_residual = max_pen
