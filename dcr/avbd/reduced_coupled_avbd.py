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
as the "k+½ corrector" warm-starting iter k+1.

The support's modal amplitude q is a DYNAMIC second-order DOF (q, q̇) — the
finalized two-way constraint of `two_band_coupling.html` ("Approach B").
Each backward-Euler substep (size h = h_substep) minimizes the single
incremental potential over (z, q); the modal block carries inertia and
damping:
    H_q = 1/h²·M_q + 1/h·D_q + K_q + Σ_j k_j U_y,j U_y,jᵀ
    g_q = 1/h²·M_q(q − q̃) + 1/h·D_q(q − qⁿ) + K_q q − Σ_j U_y,j f_j
with predictor q̃ = qⁿ + h q̇ⁿ (+ h² M_q⁻¹ f_q^grav, = 0 for the fixed
support) and the velocity update q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h after the substep.
The cross-block −ρ J_x U_yᵀ and the per-body Schur reduction are unchanged
from the static coupler — the dynamic terms are diagonal additions to H_q.
Two-way and passive BY CONSTRUCTION (one shared multiplier f_j carries both
directions; backward Euler is dissipative) — no q_s/q_d split, no IIR
resonator, no high-pass, no η/reservoir governor (all removed).

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


def _geom_stiffness_diag_batch(n: NDArray[np.float64],
                               r: NDArray[np.float64]) -> NDArray[np.float64]:
    """Vectorized version of _geom_stiffness_diag over a batch of r vectors.

    Args:
        n: contact normal, shape (3,) — fixed across the batch.
        r: per-row offset-rotated vectors, shape (n_rows, 3).
    Returns:
        g_diag stacked, shape (n_rows, 3).

    The math is bit-identical to calling _geom_stiffness_diag(n, r[i]) per row;
    only the Python-loop dispatch overhead is eliminated.
    """
    n_dot_r = r @ n   # (n_rows,)
    out = np.empty_like(r)
    for c in range(3):
        col = np.empty_like(r)   # (n_rows, 3)
        for i_ in range(3):
            if i_ == c:
                col[:, i_] = n[i_] * r[:, c] - n_dot_r
            else:
                col[:, i_] = 0.5 * (n[i_] * r[:, c] + r[:, i_] * n[c])
        out[:, c] = np.linalg.norm(col, axis=1)
    return out


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

    # ---- Static / dynamic split (drift-fix v1, 2026-06-08) ----------------
    # # DEVIATION (foundation §15): the paper's Eq. 10 evolves a single q via
    # the IIR resonator and feeds U_y·q directly into the contact anchor.
    # That path is non-passive at finite iteration counts under unilateral
    # contact — zero-mean q oscillation rectifies into +∞ probe drift through
    # the one-sided constraint (variant table in
    # ~/.claude/plans/you-are-working-in-fizzy-waffle.md). We split
    #     q = q_s + q_d
    # with q_s the algebraic static-sag coordinate (solved coupled with x in
    # the AVBD iteration, baseline H_q = K_q) and q_d the dynamic IIR
    # oscillator forced by a high-passed F_dyn. ONLY q_s enters the contact
    # anchor and H_xq cross block — q_d is rendered only. Verified end-to-end
    # on the canonical steel × 5 kg × iter=4 × sub=4 scene: legacy +108 mm
    # probe drift → split −0.12 mm settle.

    # EMA time constant (s) for the high-pass that drives q_d. The forcing
    # on q_d each substep is
    #     F_q_dyn = F_q_total − F_q_static_lp
    #     F_q_static_lp ← (1-α)·F_q_static_lp + α·F_q_total,
    #         α = 1 − exp(−h/τ)
    # τ ≈ 50 ms ⇒ ~3 Hz corner, well below the lowest typical mode but above
    # the substep frequency, so a step change in resting load is absorbed
    # into q_s without spuriously ringing q_d.
    modal_static_lp_tau: float = 0.05

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

    # Contact-anchor refresh cadence (rocking-limit-cycle fix).
    # The contact anchor y = floor_y_rest + U_y·q_s sets the support-surface
    # height under each resting body's corners. When True (legacy) it is
    # rewritten after EVERY AVBD iteration from the still-evolving q_s; on a
    # cantilever support (large modal slope under the contact) the per-iteration
    # q_s ripple hands the body's corners DIFFERENT anchor heights → a spurious
    # net torque → a sustained ROCKING limit cycle (undamped, because the body
    # couples to the algebraic q_s, not the damped ring q_d — so modal damping
    # can't touch it). Worst on the ledge boulder; flat/simply-supported
    # supports (truck/dinner) are unaffected.
    # When False the anchor is seeded ONCE per substep (substep_begin) from the
    # committed q_s and HELD FIXED through the iteration loop: the contact solve
    # sees a stable surface, so the per-iteration ripple can no longer pump
    # rotation. q_s still updates inside the Schur block every iteration
    # (the Δx↔Δq cross-coupling is untouched); only the contact's surface
    # reference is staggered by ≤1 substep. At rest q_s is constant, so the
    # equilibrium sag — and every flat-support scene — is unchanged.
    # # DEVIATION (foundation §15): staggered (Gauss–Seidel) anchor update vs
    # the monolithic per-iteration refresh; dissipates the rock without adding
    # a knob, mass/damping term, or host round-trip (it drops a kernel launch).
    refresh_anchor_each_iter: bool = False

    # Contact-anchor static low-pass (collision angular-kick + rock fix).
    # The contact anchor y = floor_y_rest + U_y·q_s followed the FULL q_s, which
    # tracks the INSTANTANEOUS contact force — so an impact force spike spikes
    # q_s, jumps the support surface under a body's corners, and kicks it (a
    # tilted drop measured ~600× the rigid-floor |ω|; the ledge boulder rocks).
    # The static/dynamic split intends q_s = SMOOTH static sag and q_d = damped
    # ring (render-only); this routes only the LOW-PASSED (static) q_s into the
    # contact anchor, so the impact/contact transient goes to q_d instead of
    # kicking the body. The EMA time-constant REUSES `modal_static_lp_tau`
    # (no new knob). At rest the EMA → q_s, so the equilibrium sag — and every
    # flat-support scene — is unchanged. False = legacy (anchor follows q_s).
    # # DEVIATION (foundation §15): static-sag low-pass of the contact reference;
    # no equation/mass/damping change, no host round-trip.
    # DEPRECATED no-op: the dynamic constraint REQUIRES the bodies to see the
    # full ringing q (the static low-pass would filter the very ring that
    # drives the two-way kick — two_band_coupling.html). Kept only so legacy
    # constructor kwargs / diag scripts don't error; it has no effect.
    anchor_static_lowpass: bool = False

    # Two-way counterfactual control (two_band_coupling.html — "Measured: the
    # constraint really does couple both ways"). When True, hold q̇ ≡ 0: the
    # predictor carries NO ring (q̃ = qⁿ) and the velocity update is skipped.
    # This is the `SplitOneWay` control that "deletes exactly that inertia
    # term" — energy then flows only rigid→support and the bystander cargo
    # gets ~0 kick. Default False = the full dynamic two-way constraint.
    freeze_qdot: bool = False

    # Body↔body stacks. The (z,q) contact (two_band_coupling.html) models
    # body↔SUPPORT only — it has no body↔body term. Box↔box stacking is owned
    # by the host AVBD self-collision solver. A tracked body that rests on
    # ANOTHER tracked body must therefore NOT be claimed/overwritten by the
    # coupler: otherwise the coupler's support-projection discards the solver's
    # box-box resolution and the stack telescopes onto the support plane. When
    # True (default), such stacked bodies are dropped from coupler ownership
    # each substep and left entirely to the solver. CPU path only (the device
    # path keeps its own substep_begin — same follow-up as the XPBD friction).
    exclude_stacked_from_coupler: bool = True
    last_n_excluded_stacked: int = 0
    # Route A (`cosolve_stacked_q`) — REMOVED from the AVBD coupler. It used to
    # split a body↔body pile (the GROUNDED base TAGGED in `_stacked_set` and kept
    # coupler-owned so it rode the modal ring, the UPPER bodies dropped). That
    # made the coupler more than a faithful body↔support solve, so it was removed:
    # the AVBD coupler is now a pure monolithic body↔support Schur, and stacked
    # piles are dropped WHOLE to the host box-box solver (see substep_begin_hook).
    # The flag is retained as an inert no-op only so the XPBD subclass override
    # and the viser knob still bind to a real field; the AVBD coupler never reads
    # it and `_stacked_set` stays empty.
    cosolve_stacked_q: bool = False          # inert on AVBD (Route A removed)
    _stacked_set: set = field(default_factory=set)   # always empty on AVBD now

    # Body mass cache (filled at attach by world).
    body_mass: dict[int, float] = field(default_factory=dict)

    # ---- fem_rigid cargo (Stage 3) ---------------------------------------
    # Per-tracked-body elastic modes a∈R^k coupled at the body's FLOOR
    # contact corners through the SAME dynamic modal block as the support
    # (two_band_coupling.html), assembled into ONE AUGMENTED global modal
    # vector  Q = [q_support(r); a_b(k_b); ...]  with BLOCK-DIAGONAL
    # M_q/K_q/D_q. The per-body 6×6 rigid Schur blocks are UNCHANGED; the
    # only generalization is the per-row modal gradient, which gains the
    # co-rotated cube term  G_a = n̂ᵀ·R·Φ_c  (FEMRigidModalBody.point_jac_tan
    # modal columns = R·Φ_c) in that body's a-columns. The cube's corner
    # flex (R·Φ_c·â)_y folds into the contact anchor (staggered, exactly like
    # the support's q̂), so the C/force computation is byte-identical to the
    # pure-rigid path. Empty `cargo` ⇒ pure-rigid cargo: the existing CPU /
    # device paths run verbatim (the Stage-1 parity stays bit-exact).
    cargo: dict = field(default_factory=dict)          # body_idx -> FEMRigidModalBody
    cargo_a: dict = field(default_factory=dict)         # body_idx -> (k,)  modal amp
    cargo_adot: dict = field(default_factory=dict)      # body_idx -> (k,)  modal vel
    cargo_a_prev: dict = field(default_factory=dict)    # body_idx -> (k,)  aⁿ snapshot
    cargo_a_hat: dict = field(default_factory=dict)     # body_idx -> (k,)  predictor â
    # Per-cargo-row caches (rebuilt each substep): nearest-corner modal block
    # and the co-rotated y-gradient G_a = n̂ᵀ·R·Φ_c FROZEN at substep begin
    # (the support's frozen-U_y staggering, per cube — so the CPU reference and
    # the device k_eval_cargo agree: both compute G_a once per substep).
    _row_cargo_modal: dict = field(default_factory=dict)  # row -> (3,k) Φ_c
    _row_cargo_Ga: dict = field(default_factory=dict)     # row -> (k,) frozen G_a
    # Augmented layout: support occupies [0:r]; cargo body b -> (start, k).
    _cargo_off: dict = field(default_factory=dict)
    _Q_dim: int = 0
    last_cargo_modal_KE: float = 0.0
    last_cargo_modal_PE: float = 0.0

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

    # Static-within-substep warp state, pulled once in substep_begin_hook
    # and reused across all AVBD iterations of that substep. None until
    # the first substep_begin_hook fires.
    _mass_np:            NDArray[np.float64] | None = None
    _inertia_local_np:   NDArray[np.float64] | None = None
    _x_inertial_np:      NDArray[np.float64] | None = None
    _q_inertial_np:      NDArray[np.float64] | None = None

    # P4: vectorized anchor-update stack, built once per substep.
    # _tracked_rows_arr   — (n_tracked,)   int row indices into c_world_anchor
    # _U_y_stack          — (n_tracked, r) per-row basis y-vectors stacked
    # _floor_y_rest_arr   — (n_tracked,)   rest floor heights
    # _v_lift_arr         — (n_tracked,)   per-row upward lift velocity
    # Allows `anchor[idx, 1] = floor_y + U_y_stack @ q + h * v_lift`
    # as a single matvec + scatter, replacing a Python for over rows.
    _tracked_rows_arr:   NDArray[np.int64]   | None = None
    _U_y_stack:          NDArray[np.float64] | None = None
    _floor_y_rest_arr:   NDArray[np.float64] | None = None
    _v_lift_arr:         NDArray[np.float64] | None = None

    # P1: per-body row-array caches, built once per substep, used by
    # iteration_hook to replace the inner `for row in rows_on_body`
    # Python loop with batched matmuls.
    #   _row_idx_by_body[b]:  (n_rows_b,)     row indices into the *_np arrays
    #   _row_off_by_body[b]:  (n_rows_b, 3)   corner offsets in body frame
    #   _row_U_y_by_body[b]:  (n_rows_b, r)   basis y-vectors per row
    _row_idx_by_body: dict[int, NDArray[np.int64]] = field(default_factory=dict)
    _row_off_by_body: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_U_y_by_body: dict[int, NDArray[np.float64]] = field(default_factory=dict)

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

    # ---- Static / dynamic split diagnostics ----
    # Populated by `_substep_end_split`. All inert in legacy mode.
    last_q_s_norm:        float = 0.0
    last_q_d_norm:        float = 0.0
    last_qdot_d_norm:     float = 0.0
    last_F_q_total_norm:  float = 0.0
    last_F_q_static_norm: float = 0.0
    last_F_q_dyn_norm:    float = 0.0
    last_passivity_violations: int = 0
    # Modal-load accumulator (Σ U_y·(-f) across bodies during the FINAL
    # iteration of the substep). Read by `_substep_end_split` to drive the
    # high-pass + q_d step. Reset to zeros at the start of each iteration
    # in `_iteration_split` (synthetic-basis size = r at attach time).
    _last_F_q_contact: NDArray[np.float64] | None = None
    # Previous-substep total modal mechanical energy E = ½q̇ᵀM_qq̇ + ½qᵀK_qq,
    # for the (logged, not enforced) backward-Euler passivity certificate.
    _E_modal_prev: float | None = None
    # Defensive counter: incremented if any code path calls
    # `_apply_dcr_velocities` on a body the coupler tracks. In
    # --mode coupled_iir_modal this MUST stay 0 (Test 5). The old
    # DCR post-kick path is the ablation; counter is non-zero only
    # in --mode old_dcr_postkick (which doesn't attach this coupler).
    dcr_postkick_calls: int = 0

    # ---- GPU device-residency (see reduced_coupled_kernels.py) -----------
    # When True and the solver runs on CUDA, `iteration_hook` becomes a
    # SINGLE device-kernel launch operating on the solver's device arrays in
    # place — no `.numpy()`, no `.assign()`, no host sync — eliminating the
    # ~16 per-step GPU pipeline drains the numpy path forces. substep_begin /
    # substep_end stay on host (they fire once per substep, outside the
    # CUDA-graph-captured region) but upload q_s + the per-substep row caches
    # to the device and read q_s / F_q back once per substep. The numpy path
    # is preserved verbatim and used whenever device_resident is False or the
    # solver is on CPU (CLAUDE.md rule 6: reference path first).
    device_resident: bool = False
    _device_ready: bool = False
    _dbuf: dict = field(default_factory=dict)
    _hbuf: dict = field(default_factory=dict)
    _dev_n_b: int = 0
    _dev_n_tracked: int = 0
    _dev_total_rows: int = 0
    _k_eps_tiled: object = None       # per-r cooperative-Cholesky solve kernel
    _eps_block_dim: int = 32          # one warp suffices for the r×r tile solve

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # GPU device-residency (full: substep_begin / iteration / substep_end
    # all run on-device; topology is uploaded ONCE; the only host readback
    # is once per macro-step for the render/HUD). See reduced_coupled_kernels.
    # ------------------------------------------------------------------
    def add_cargo(self, body_idx: int, body) -> None:
        """Register a fem_rigid cargo body's elastic modes for two-way modal
        coupling at its FLOOR contact corners (Stage 3). `body` is a
        `dcr.avbd.cargo.fem_rigid.FEMRigidModalBody`; its `a` modal amplitude
        becomes a block of the augmented dynamic modal vector Q. Must be a
        tracked body (its FLOOR rows already couple to the support q)."""
        b = int(body_idx)
        k = int(body.k)
        self.cargo[b] = body
        self.cargo_a[b] = np.zeros(k, dtype=np.float64)
        self.cargo_adot[b] = np.zeros(k, dtype=np.float64)
        self.cargo_a_prev[b] = np.zeros(k, dtype=np.float64)
        self.cargo_a_hat[b] = np.zeros(k, dtype=np.float64)

    def _use_device(self, solver) -> bool:
        """True when the device-resident path should run for this solver.

        Both cargo materials are on-device: fem_rigid (LINEAR modes, K_q block)
        and abd (NONLINEAR V⊥ via k_cargo_internal). The augmented modal kernels
        grow row_U_y to R = r + Σk and k_eval_cargo fills the co-rotated cargo
        gradient. The numpy path stays the parity oracle (CLAUDE.md rule 6)."""
        return bool(self.device_resident
                    and str(solver.device).startswith("cuda"))

    def _ensure_device_buffers(self, solver) -> None:
        """Allocate the pre-sized device buffers once. Sized to scene capacity
        (n tracked bodies, total solver rows, r modes) so they never
        reallocate. Sets `solver.hooks_device_resident` so the per-hook drains
        are dropped and the iteration loop is CUDA-graph-captured."""
        import warp as wp
        from .reduced_coupled_kernels import vec3d, mat33d

        dev = solver.device
        r = int(self.rs.r)
        is_cuda = str(dev).startswith("cuda")
        max_b = max(1, len(self.tracked_body_indices))
        cap_rows = max(1, len(solver._rows))
        n_grid_pts = int(self.rs.U_points.shape[0])
        self._dev_cap_rows = cap_rows
        self._dev_max_b = max_b
        f64 = wp.float64
        d = self._dbuf

        # ---- AUGMENTED modal layout (Stage 3): Q = [q_support(r); a_b(k); ...]
        # with block-diagonal M_q/K_q/D_q. cargo-empty ⇒ R == r and these are
        # exactly the support matrices, so support-only scenes are unchanged.
        self._cargo_off.clear()
        R_tot = r
        k_max = 1
        for b in sorted(self.cargo.keys()):
            k = int(self.cargo[b].k)
            self._cargo_off[b] = (R_tot, k)
            R_tot += k
            k_max = max(k_max, k)
        self._Q_dim = R_tot
        self._dev_R = R_tot
        self._dev_kmax = k_max
        Mq_a = np.zeros((R_tot, R_tot), dtype=np.float64)
        Kq_a = np.zeros((R_tot, R_tot), dtype=np.float64)
        Dq_a = np.zeros((R_tot, R_tot), dtype=np.float64)
        Mq_a[:r, :r] = self.rs.Mq
        Kq_a[:r, :r] = self.rs.Kq
        Dq_a[:r, :r] = self.rs.Dq
        for b, (s, k) in self._cargo_off.items():
            body = self.cargo[b]
            Mq_a[s:s + k, s:s + k] = body.Mq_block
            Kq_a[s:s + k, s:s + k] = body.Kq_block
            Dq_a[s:s + k, s:s + k] = body.Dq_block

        # ---- modal constants (uploaded once) ----
        d["Kq"] = wp.array(Kq_a, dtype=f64, device=dev)
        d["Mq"] = wp.array(Mq_a, dtype=f64, device=dev)
        d["Dq"] = wp.array(Dq_a, dtype=f64, device=dev)
        d["grid_Uy"] = wp.array(
            self.rs.U_points[:, 1, :].astype(np.float64), dtype=f64,
            device=dev)
        # ---- resident DYNAMIC modal state (q, q̇) + per-substep predictor ----
        # The single second-order DOF of the finalized two-way constraint
        # (two_band_coupling.html). q̇ carries the ring across substeps; q_prev
        # = qⁿ snapshot, q_hat = predictor q̃. No q_s/q_d split, no IIR/EMA
        # buffers (eigen_omega/zeta/Mq_diag/q_free/S_h_diag/... all removed).
        # Augmented modal state/scratch are sized to R_tot (= r when no cargo).
        d["q"]      = wp.zeros(R_tot, dtype=f64, device=dev)
        d["qdot"]   = wp.zeros(R_tot, dtype=f64, device=dev)
        d["q_prev"] = wp.zeros(R_tot, dtype=f64, device=dev)
        d["q_hat"]  = wp.zeros(R_tot, dtype=f64, device=dev)
        # ---- iteration scratch ----
        d["Hq"] = wp.zeros((R_tot, R_tot), dtype=f64, device=dev)
        d["S"] = wp.zeros((R_tot, R_tot), dtype=f64, device=dev)
        d["gq"] = wp.zeros(R_tot, dtype=f64, device=dev)
        d["Fq"] = wp.zeros(R_tot, dtype=f64, device=dev)
        d["rhs"] = wp.zeros(R_tot, dtype=f64, device=dev)
        d["dq"] = wp.zeros(R_tot, dtype=f64, device=dev)
        d["diag"] = wp.zeros(8, dtype=f64, device=dev)
        d["counts"] = wp.zeros(3, dtype=int, device=dev)  # [n_b, n_tracked, tot]
        # ---- topology (uploaded once in _upload_topology_once) ----
        d["body_ids"] = wp.zeros(max_b, dtype=int, device=dev)
        d["body_row_start"] = wp.zeros(max_b + 1, dtype=int, device=dev)
        d["row_index"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_body"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_off"] = wp.zeros(cap_rows, dtype=vec3d, device=dev)
        d["row_U_y"] = wp.zeros((cap_rows, R_tot), dtype=f64, device=dev)
        d["rowdata"] = wp.zeros((cap_rows, 8), dtype=f64, device=dev)
        d["floor_y_rest"] = wp.zeros(cap_rows, dtype=f64, device=dev)
        # ---- cargo topology (fem_rigid): per-row Q-offset (−1 if not cargo),
        # mode count, and the nearest-corner co-rotation modal block Φ_c. ----
        d["row_cargo_off"] = wp.full(cap_rows, -1, dtype=int, device=dev)
        d["row_cargo_k"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_cargo_corot"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_corner_modal"] = wp.zeros(
            (cap_rows, 3, k_max), dtype=f64, device=dev)
        # ---- nonlinear (abd V⊥) cargo: per-affine-body Q-offset + κ_v. ----
        affine_offs, affine_kappas = [], []
        for b, (s, k) in self._cargo_off.items():
            body = self.cargo[b]
            if getattr(body, "has_nonlinear_internal", False):
                affine_offs.append(int(s))
                affine_kappas.append(float(body.kappa_v))
        self._dev_n_affine = len(affine_offs)
        d["affine_off"] = wp.array(
            np.array(affine_offs or [0], dtype=np.int32), dtype=int, device=dev)
        d["affine_kappa"] = wp.array(
            np.array(affine_kappas or [0.0], dtype=np.float64),
            dtype=f64, device=dev)
        # ---- per-body block-inverse + cross scratch ----
        d["b_TL"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_TR"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_BL"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_BR"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_gx0"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["b_gx1"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["b_hg0"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["b_hg1"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["Hmb_top"] = wp.zeros((max_b, R_tot), dtype=vec3d, device=dev)
        d["Hmb_bot"] = wp.zeros((max_b, R_tot), dtype=vec3d, device=dev)
        d["M"] = wp.zeros((max_b, 6, R_tot), dtype=f64, device=dev)
        d["rho_score"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["b_dxn"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["b_dthn"] = wp.zeros(max_b, dtype=f64, device=dev)

        # Cached scalars.
        self._dev_inv_dt2 = 1.0 / (float(self.h_substep) ** 2)
        self._dev_inv_dt = 1.0 / float(self.h_substep)
        self._dev_rho_clip = float(self.rho_clip)
        self._dev_eps_base = (self.eps_baseline
                              * float(np.trace(Kq_a)) / max(R_tot, 1))
        self._dev_eps_cross = float(self.eps_cross_factor)
        self._dev_r = r
        self._dev_n_grid_pts = n_grid_pts

        # Block-cooperative Cholesky solver for the r×r SPD Schur system. This
        # replaces the single-thread GE k_eps_solve (the profiled hot spot) on
        # CUDA. The tile API is GPU-only, so non-CUDA falls back to k_eps_solve.
        # Generated per-r (tile shapes are compile-time) and warmed here OUTSIDE
        # any graph-capture region so the first real launch (which IS captured)
        # never triggers a kernel compile inside capture.
        self._k_eps_tiled = None
        self._eps_block_dim = 64
        if is_cuda:
            from .reduced_coupled_kernels import make_k_eps_solve_tiled
            self._k_eps_tiled = make_k_eps_solve_tiled(R_tot)
            # Warmup: S/rhs are freshly zeroed ⇒ solves ε·I·dq = 0 ⇒ dq = 0,
            # q_s unchanged (still zero). Forces an out-of-capture compile.
            wp.launch_tiled(
                self._k_eps_tiled, dim=[1], device=dev,
                block_dim=int(self._eps_block_dim), inputs=[
                    d["counts"], d["rho_score"], wp.float64(self._dev_eps_base),
                    wp.float64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"],
                    d["q"], d["diag"]])
            wp.synchronize_device(dev)
        self._dev_h_sub = float(self.h_substep)
        # substeps per macro step (for once-per-step host readback).
        n_sub = int(round(self.h_macro / self.h_substep)) if self.h_substep > 0 \
            else 1
        self._dev_n_sub = max(1, n_sub)

    def _upload_topology_once(self, solver) -> None:
        """One-time host row identification + upload of the (constant) tracked
        FLOOR-row topology, in body-grouped CSR order. The tracked-row set,
        body map and body-frame offsets are static for the shelf, so this runs
        once; the moving basis U_y is recomputed on-device each substep by
        `k_eval_basis`. Also seeds resident q_s/q_d/q̇_d from rs."""
        import warp as wp
        FLOOR = FLOOR_CONTACT_6DOF
        off_a_np = solver.c_off_a.numpy()
        body_a_np = solver.c_body_a.numpy()
        anchor_np = solver.c_world_anchor.numpy()

        rows_per_body: dict[int, list[int]] = {}
        for i, row in enumerate(solver._rows):
            if row.type != FLOOR:
                continue
            ba = int(body_a_np[i])
            if ba not in self.tracked_body_indices:
                continue
            rows_per_body.setdefault(ba, []).append(i)
            if i not in self.rs.floor_y_rest:
                self.rs.floor_y_rest[i] = float(anchor_np[i, 1])

        bodies = list(rows_per_body.keys())
        n_b = len(bodies)
        cap_rows = self._dev_cap_rows
        max_b = self._dev_max_b
        body_ids = np.zeros(max_b, dtype=np.int32)
        body_row_start = np.zeros(max_b + 1, dtype=np.int32)
        row_index = np.zeros(cap_rows, dtype=np.int32)
        row_body = np.zeros(cap_rows, dtype=np.int32)
        row_off = np.zeros((cap_rows, 3), dtype=np.float64)
        floor_y = np.zeros(cap_rows, dtype=np.float64)
        # fem_rigid cargo per-row topology (−1 / 0 / zeros for non-cargo rows).
        k_max = int(self._dev_kmax)
        row_cargo_off = np.full(cap_rows, -1, dtype=np.int32)
        row_cargo_k = np.zeros(cap_rows, dtype=np.int32)
        row_cargo_corot = np.zeros(cap_rows, dtype=np.int32)
        row_corner_modal = np.zeros((cap_rows, 3, k_max), dtype=np.float64)
        start = 0
        ordered_rows: list[int] = []
        for t, b in enumerate(bodies):
            body_ids[t] = b
            body_row_start[t] = start
            cargo_body = self.cargo.get(b)
            for i in rows_per_body[b]:
                row_index[start] = i
                row_body[start] = b
                row_off[start] = off_a_np[i].astype(np.float64)
                floor_y[start] = self.rs.floor_y_rest[i]
                if cargo_body is not None:
                    off_q, k = self._cargo_off[b]
                    cid = int(np.argmin(np.linalg.norm(
                        cargo_body.corner_body - row_off[start], axis=1)))
                    row_cargo_off[start] = off_q
                    row_cargo_k[start] = k
                    row_cargo_corot[start] = int(
                        getattr(cargo_body, "corotate", True))
                    row_corner_modal[start, :, :k] = cargo_body.corner_modal[cid]
                ordered_rows.append(i)
                start += 1
        body_row_start[n_b] = start
        total = start

        self._dev_n_b = n_b
        self._dev_n_tracked = total
        self._dev_total_rows = total
        self.rs.tracked_row_indices = ordered_rows
        self.last_n_tracked_rows = total

        d = self._dbuf
        d["counts"].assign(np.array([n_b, total, total], dtype=np.int32))
        d["body_ids"].assign(body_ids)
        d["body_row_start"].assign(body_row_start)
        d["row_index"].assign(row_index)
        d["row_body"].assign(row_body)
        d["row_off"].assign(row_off)
        d["floor_y_rest"].assign(floor_y)
        d["row_cargo_off"].assign(row_cargo_off)
        d["row_cargo_k"].assign(row_cargo_k)
        d["row_cargo_corot"].assign(row_cargo_corot)
        d["row_corner_modal"].assign(row_corner_modal)
        # Seed the resident AUGMENTED modal state Q = [q_support; a_cargo...]
        # from the host truth (zeros at sim start, or carried on a mid-run
        # switch). The support block, then each cargo body's a/ȧ block.
        R_tot = int(self._dev_R)
        q0 = np.zeros(R_tot, dtype=np.float64)
        qdot0 = np.zeros(R_tot, dtype=np.float64)
        q0[:self.rs.r] = self.rs.q
        qdot0[:self.rs.r] = self.rs.qdot
        for b, (s, k) in self._cargo_off.items():
            q0[s:s + k] = self.cargo_a[b]
            qdot0[s:s + k] = self.cargo_adot[b]
        d["q"].assign(q0)
        d["qdot"].assign(qdot0)

    def _substep_begin_device(self, solver) -> None:
        """Device substep_begin (two_band_coupling.html): (one-time) identify
        rows + alloc + upload; then per substep recompute U_y, form the
        inertial predictor (snapshot qⁿ, q̃ = qⁿ + h q̇ⁿ), and seed the contact
        anchor from the FULL q̃ — all on-device, launch-only."""
        import warp as wp
        from . import reduced_coupled_kernels as K
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
        # Support basis U_y at the (moving) contact corners → row_U_y[:, 0:r].
        wp.launch(K.k_eval_basis, dim=cap_rows, device=dev, inputs=[
            solver.x, solver.q, d["counts"], r, d["row_index"], d["row_body"],
            d["row_off"], d["grid_Uy"], int(self.n_grid_x), int(self.n_grid_z),
            f64(self.shelf_length), f64(self.shelf_width), d["row_U_y"]])
        # fem_rigid cargo co-rotated modal gradient → row_U_y[:, r:R] = −G_a
        # (frozen for the substep). Skipped (no-op) when no cargo is registered.
        if self.cargo:
            wp.launch(K.k_eval_cargo, dim=cap_rows, device=dev, inputs=[
                solver.q, d["counts"], r, Rt, d["row_body"],
                d["row_cargo_off"], d["row_cargo_k"], d["row_cargo_corot"],
                d["row_corner_modal"], d["row_U_y"]])
        # Inertial predictor over the AUGMENTED Q: snapshot Qⁿ = Q, Q̃ = Qⁿ +
        # h·Q̇ⁿ (carries the support ring AND each cube's modal ring; f_q^grav =
        # 0). Frozen control passes h = 0 ⇒ Q̃ = Qⁿ (no ring).
        h_pred = 0.0 if self.freeze_qdot else self._dev_h_sub
        wp.launch(K.k_predict, dim=Rt, device=dev, inputs=[
            Rt, f64(h_pred), d["q"], d["qdot"], d["q_prev"], d["q_hat"]])
        # Seed the contact anchor from the FULL predictor Q̃: with row_U_y =
        # [+U_y | −G_a] and Q̃ = [q̂ | â], k_anchor yields floor + U_y·q̂ −
        # G_a·â (deformed support surface minus the cube's corner flex).
        wp.launch(K.k_anchor, dim=cap_rows, device=dev, inputs=[
            Rt, d["counts"], d["row_index"], d["row_U_y"], d["floor_y_rest"],
            d["q_hat"], d["diag"], solver.c_world_anchor])

    def _iteration_device(self, solver) -> None:
        """One coupled Schur iteration as a sequence of parallel device-kernel
        launches (no host round-trip — the whole point). Launch order encodes
        the data dependencies on the stream. Mirrors iteration_hook's math."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        d = self._dbuf
        dev = solver.device
        # All modal-dimension kernels operate on the AUGMENTED Q (size R = r +
        # Σ cargo k). For support-only scenes R == r, so this is unchanged.
        r = int(self._dev_R)
        cap_rows = int(self._dev_cap_rows)
        max_b = int(self._dev_max_b)
        f64 = wp.float64

        # 1. per-row contact forces.
        wp.launch(K.k_rowforce, dim=cap_rows, device=dev, inputs=[
            solver.x, solver.q, solver.c_world_anchor, solver.c_lambda,
            solver.c_penalty, solver.c_fmin, solver.c_fmax, solver.c_alpha_C0,
            solver.c_stiffness, d["counts"], d["row_index"], d["row_body"],
            d["row_off"], f64(self._dev_rho_clip), d["rowdata"]])
        # 2. dynamic modal Hessian + gradient (parallel, deterministic). The
        #    1/h²·M_q and 1/h·D_q terms make q a second-order DOF
        #    (two_band_coupling.html). g_q uses the predictor q̃ (q_hat) and
        #    substep-start qⁿ (q_prev).
        wp.launch(K.k_hq, dim=(r, r), device=dev, inputs=[
            r, d["counts"], d["Mq"], d["Kq"], d["Dq"],
            f64(self._dev_inv_dt2), f64(self._dev_inv_dt),
            d["row_U_y"], d["rowdata"], d["Hq"]])
        wp.launch(K.k_g, dim=r, device=dev, inputs=[
            r, d["counts"], d["Mq"], d["Kq"], d["Dq"],
            f64(self._dev_inv_dt2), f64(self._dev_inv_dt),
            d["q"], d["q_hat"], d["q_prev"], d["row_U_y"], d["rowdata"],
            d["gq"], d["Fq"]])
        # 2b. nonlinear abd V⊥ grad/Hess ADDED to the cargo block (after k_hq/k_g
        #     wrote the inertia+contact part; before k_schur/k_rhs read them).
        if self._dev_n_affine > 0:
            wp.launch(K.k_cargo_internal, dim=self._dev_n_affine, device=dev,
                      inputs=[self._dev_n_affine, d["affine_off"],
                              d["affine_kappa"], d["q"], d["gq"], d["Hq"]])
        # 3. per-body H_x assembly + block inverse (scalar/3×3 part, dim=max_b)
        #    and the r-way cross-coupling block M (dim=(max_b, r)).
        wp.launch(K.k_body, dim=max_b, device=dev, inputs=[
            solver.x, solver.q, solver.mass, solver.inertia_local,
            solver.x_inertial, solver.q_inertial, d["counts"],
            d["body_ids"], d["body_row_start"], d["rowdata"],
            f64(self._dev_inv_dt2), d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"],
            d["b_gx0"], d["b_gx1"], d["b_hg0"], d["b_hg1"], d["rho_score"]])
        wp.launch(K.k_body_cross, dim=(max_b, r), device=dev, inputs=[
            solver.mass, r, d["counts"], d["body_ids"], d["body_row_start"],
            d["row_U_y"], d["rowdata"], d["M"]])
        # 4. Hoist H_x⁻¹·M[:,b] (per body,mode), then Schur reduce + rhs.
        wp.launch(K.k_hmb, dim=(max_b, r), device=dev, inputs=[
            r, d["counts"], d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"],
            d["M"], d["Hmb_top"], d["Hmb_bot"]])
        wp.launch(K.k_schur, dim=(r, r), device=dev, inputs=[
            r, d["counts"], d["Hq"], d["M"], d["Hmb_top"], d["Hmb_bot"],
            d["S"]])
        wp.launch(K.k_rhs, dim=r, device=dev, inputs=[
            r, d["counts"], d["gq"], d["b_hg0"], d["b_hg1"], d["M"],
            d["rhs"]])
        # 5. ε-regularize + r×r solve + q update. Block-cooperative Cholesky
        # (tile API) when available — replaces the single-thread GE that the
        # profiler flagged as the dominant cost; falls back to k_eps_solve on
        # CPU / when the tiled kernel is unavailable.
        if self._k_eps_tiled is not None:
            wp.launch_tiled(
                self._k_eps_tiled, dim=[1], device=dev,
                block_dim=self._eps_block_dim, inputs=[
                    d["counts"], d["rho_score"], f64(self._dev_eps_base),
                    f64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"],
                    d["q"], d["diag"]])
        else:
            wp.launch(K.k_eps_solve, dim=1, device=dev, inputs=[
                r, d["counts"], d["rho_score"], f64(self._dev_eps_base),
                f64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"], d["q"],
                d["diag"]])
        # 6. back-substitute body deltas + diagnostics + anchor refresh.
        wp.launch(K.k_backsub, dim=max_b, device=dev, inputs=[
            solver.x, solver.q, solver.mass, r, d["counts"], d["body_ids"],
            d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"], d["b_gx0"], d["b_gx1"],
            d["M"], d["dq"], d["diag"], d["b_dxn"], d["b_dthn"]])
        wp.launch(K.k_reduce_diag, dim=1, device=dev, inputs=[
            d["counts"], d["b_dxn"], d["b_dthn"], d["diag"]])
        # Anchor refresh from the updated full q: only when monolithic
        # (legacy). Staggered mode keeps the substep_begin q̃ seed fixed
        # through the iteration loop to kill the rocking limit cycle (the
        # Δx↔Δq cross block still transmits q within the substep).
        if self.refresh_anchor_each_iter:
            wp.launch(K.k_anchor, dim=cap_rows, device=dev, inputs=[
                r, d["counts"], d["row_index"], d["row_U_y"],
                d["floor_y_rest"], d["q"], d["diag"], solver.c_world_anchor])
        self.last_n_iter_solves += 1

    def _substep_end_device(self, solver) -> None:
        """Device substep_end (two_band_coupling.html — "After the step"):
        commit q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h on-device. That single finite-difference
        IS the ring-carrying mechanism (it feeds the next substep's predictor).
        Host readback happens only ONCE per macro-step (last substep) for the
        render/HUD."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        if not self._device_ready or self._dev_n_b == 0:
            self._substep_index += 1
            return
        d = self._dbuf
        dev = solver.device
        Rt = int(self._dev_R)
        f64 = wp.float64
        # Augmented modal velocity update: Q̇ = (Q − Qⁿ)/h (support ring AND
        # each cube's modal ring). Frozen control skips it (Q̇ stays 0 — the
        # two-way counterfactual).
        if not self.freeze_qdot:
            wp.launch(K.k_qdot, dim=Rt, device=dev, inputs=[
                Rt, f64(self._dev_inv_dt), d["q"], d["q_prev"], d["qdot"]])

        # Once-per-macro-step host readback for render/HUD (the only host
        # round-trip; substep boundaries are otherwise device-only). Also when
        # log_substeps is on, sync every substep so the log is per-substep.
        is_last = (self._substep_index % self._dev_n_sub) == (
            self._dev_n_sub - 1)
        if is_last or self.log_substeps:
            self._sync_device_to_host(solver)
        self._substep_index += 1

    def _sync_device_to_host(self, solver) -> None:
        """Pull the resident dynamic modal state (q, q̇) + diagnostics to host
        and recompute the host-side logged scalars (norms, deflection, energy,
        passivity). This is the ONLY host round-trip — once per macro-step."""
        d = self._dbuf
        r = int(self.rs.r)
        Q = d["q"].numpy().astype(np.float64).copy()
        Qdot = d["qdot"].numpy().astype(np.float64).copy()
        # Split the augmented Q back: support [0:r] ⊕ each cargo a-block.
        self.rs.q = Q[:r].copy()
        self.rs.qdot = Qdot[:r].copy()
        self.last_cargo_modal_KE = 0.0
        self.last_cargo_modal_PE = 0.0
        for b, (s, k) in self._cargo_off.items():
            body = self.cargo[b]
            self.cargo_a[b] = Q[s:s + k].copy()
            self.cargo_adot[b] = Qdot[s:s + k].copy()
            adot = self.cargo_adot[b]
            self.last_cargo_modal_KE += 0.5 * float(adot @ (body.Mq_block @ adot))
            if body.has_nonlinear_internal:
                self.last_cargo_modal_PE += float(body.internal_energy(self.cargo_a[b]))
            else:
                self.last_cargo_modal_PE += 0.5 * float(
                    self.cargo_a[b] @ (body.omega2 * self.cargo_a[b]))
        self._last_F_q_contact = d["Fq"].numpy().astype(np.float64)[:r].copy()
        diag = d["diag"].numpy()
        self.last_max_dx_norm = float(diag[0])
        self.last_max_dtheta_norm = float(diag[1])
        self.last_dq_norm = float(diag[2])

        Mq, Kq, Dq = self.rs.Mq, self.rs.Kq, self.rs.Dq
        self.last_q_s_norm = float(np.linalg.norm(self.rs.q))
        self.last_q_d_norm = 0.0
        self.last_qdot_d_norm = float(np.linalg.norm(self.rs.qdot))
        self.last_F_q_total_norm = float(np.linalg.norm(self._last_F_q_contact))
        self.last_F_q_static_norm = 0.0
        self.last_F_q_dyn_norm = self.last_F_q_total_norm
        self.last_q_norm = self.last_q_s_norm
        self.last_qdot_norm = self.last_qdot_d_norm
        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, self.rs.q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
        # Total modal mechanical energy + backward-Euler passivity certificate
        # (two_band_coupling.html "Passive for free"): E = ½q̇ᵀM_qq̇ + ½qᵀK_qq
        # may rise only up to the contact work |h·F_qᵀq̇|. Logged, not governed.
        self.last_modal_KE = 0.5 * float(self.rs.qdot @ (Mq @ self.rs.qdot))
        self.last_modal_PE = 0.5 * float(self.rs.q @ (Kq @ self.rs.q))
        self.last_damp_power = float(self.rs.qdot @ (Dq @ self.rs.qdot))
        E_now = self.last_modal_KE + self.last_modal_PE
        W_bound = abs(float(self.h_substep)
                      * float(self._last_F_q_contact @ self.rs.qdot))
        if (self._E_modal_prev is not None
                and E_now > self._E_modal_prev + W_bound + 1e-9):
            self.last_passivity_violations += 1
        self._E_modal_prev = E_now
        rows = self.rs.tracked_row_indices
        if rows:
            lam = solver.c_lambda.numpy()
            self.last_contact_lambda_max = float(np.max(np.abs(lam[rows])))

    def _stacked_body_indices(self, solver) -> set[int]:
        """Tracked bodies in a body↔body contact pile, to drop from coupler
        ownership. The (z,q) contact models body↔support only
        (two_band_coupling.html) — it has no body↔body term — so any tracked
        body that is also touching ANOTHER tracked body (a stack or a toppled
        pile) belongs to the host AVBD self-collision solver. If the coupler
        kept it, its support-projection would discard the solver's box-box
        resolution and the pile would telescope onto the support plane.

        Whole-pile rule: BOTH members of every touching pair are dropped. (An
        earlier base/upper split that kept the stack base coupler-owned — so the
        stack still felt the support ring — only held for short STATIC stacks;
        a toppling pile then penetrated, and on AVBD the base's load-blind
        support-projection fought the box-box load. Whole-pile is the robust
        choice.) Single bodies resting directly on the support touch no other
        tracked body and stay coupler-owned, keeping their modal coupling.

        Per-body world AABBs come from the FLOOR-row corner offsets (8 box
        corners). A pair (a, b) is "touching" when their xz footprints overlap
        and their y-ranges overlap/abut within `tol`.
        """
        bodies = list(self._rows_per_body.keys())
        if len(bodies) < 2:
            return set()
        P = solver.positions()
        Q = solver.orientations()
        aabb: dict[int, tuple[NDArray, NDArray]] = {}
        for b in bodies:
            offs = np.stack([self._row_off_a[i]
                             for i in self._rows_per_body[b]], axis=0)
            R = _quat_xyzw_to_R(Q[b].astype(np.float64))
            corners = offs @ R.T + P[b].astype(np.float64)
            aabb[b] = (corners.min(axis=0), corners.max(axis=0))
        tol = 0.02   # vertical contact tolerance [m]
        excl: set[int] = set()
        for ia in range(len(bodies)):
            a = bodies[ia]
            amin, amax = aabb[a]
            for ib in range(ia + 1, len(bodies)):
                b = bodies[ib]
                bmin, bmax = aabb[b]
                if amin[0] > bmax[0] or amax[0] < bmin[0]:    # strict x overlap
                    continue
                if amin[2] > bmax[2] or amax[2] < bmin[2]:    # strict z overlap
                    continue
                # y-ranges overlap or abut (one rests on / piles on the other)
                if (amin[1] <= bmax[1] + tol) and (bmin[1] <= amax[1] + tol):
                    excl.add(a)
                    excl.add(b)
        # Never drop a cargo (deformable impactor) body: it carries its own
        # augmented modal block and the iteration_hook cargo loop indexes
        # _lam_a / cargo_a by its body index, so excluding it (e.g. when the
        # impactor lands on/against a bystander) would KeyError. The impactor is
        # the active modal driver — it must stay coupler-owned regardless.
        excl -= set(self.cargo.keys())
        return excl

    def substep_begin_hook(self, solver) -> None:
        """Dynamic-constraint substep_begin (two_band_coupling.html).

        Snapshot qⁿ = q, form the inertial predictor q̃ that carries the
        ring history q̇ⁿ, and seed the contact anchor from the FULL q̃ (the
        deformed surface y_rest + U_y·q̃ the bodies rest on — no static
        low-pass, no split). One backward-Euler substep of size h_substep.
        """
        # Full GPU-resident path: all substep_begin work runs on-device (basis
        # eval, predictor, anchor seed). The numpy body below is the reference
        # (CLAUDE.md rule 6); CPU / device_resident off use it.
        if self._use_device(solver):
            self._substep_begin_device(solver)
            return

        # 1. Snapshot qⁿ and form the inertial predictor (two_band_coupling
        #    "Inertial predictors"):  q̃ = qⁿ + h q̇ⁿ + h² M_q⁻¹ f_q^grav.
        #    The predictor carries q̇ⁿ — NOT zeroed — which is the whole point
        #    of the dynamic constraint (the ring persists across substeps).
        #    # DEVIATION (two_band_coupling.html): f_q^grav = Uᵀf_grav = 0 for
        #    the fixed support — its modes are zero-mean about the undeformed
        #    rest slab (the sag is produced by the contact load at equilibrium,
        #    not modal self-weight), so q̃ = qⁿ + h q̇ⁿ.
        h = float(self.h_substep)
        h_pred = 0.0 if self.freeze_qdot else h   # frozen control: q̃ = qⁿ
        self.rs.q_prev_macro = self.rs.q.copy()
        self.rs.q_hat = self.rs.q + h_pred * self.rs.qdot

        # Allocate the F_q_contact diagnostic accumulator (one-shot).
        r = self.rs.r
        if (self._last_F_q_contact is None
                or self._last_F_q_contact.shape[0] != r):
            self._last_F_q_contact = np.zeros(r, dtype=np.float64)

        # 4. Pull substep-static body state (same as legacy).
        anchor_np = solver.c_world_anchor.numpy().copy()
        off_a_np = solver.c_off_a.numpy().copy()
        body_a_np = solver.c_body_a.numpy()
        # mass/inertia/inertial are consumed ONLY by the numpy iteration_hook.
        # In the device-resident path the kernels read solver.mass /
        # solver.inertia_local / solver.x_inertial / solver.q_inertial
        # directly on-device, so skip these 4 host syncs once it is active.
        if not (self._use_device(solver) and self._device_ready):
            self._mass_np          = solver.mass.numpy()
            self._inertia_local_np = solver.inertia_local.numpy()
            self._x_inertial_np    = solver.x_inertial.numpy()
            self._q_inertial_np    = solver.q_inertial.numpy()

        # 5. Row caching — identical to legacy (geometry-only).
        self._U_at_row.clear()
        self._row_body_a.clear()
        self._row_off_a.clear()
        self._row_floor_y_rest.clear()
        self._rows_per_body.clear()
        self._row_idx_by_body.clear()
        self._row_off_by_body.clear()
        self._row_U_y_by_body.clear()
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

        # Body↔body-stacked tracked bodies: the (z,q) contact has no body↔body
        # term (two_band_coupling.html), so the host solver must own a stack's
        # rigid pose (its box-box keeps the pile intact). The WHOLE pile is
        # pose-excluded AND dropped from `tracked`; it rests on the host box-box
        # over the static slab. (The Route-A `cosolve_stacked_q` grounded/upper
        # split — which kept the grounded base coupler-owned so the pile rode the
        # modal ring — was removed to keep the AVBD coupler a faithful
        # body↔support-only monolithic Schur. `_stacked_set` stays empty.)
        self._stacked_set = set()
        if self.exclude_stacked_from_coupler and len(self._rows_per_body) > 1:
            stacked = self._stacked_body_indices(solver)
            self.last_n_excluded_stacked = len(stacked)
            if stacked:
                for b in stacked:
                    self._rows_per_body.pop(b, None)
                tracked = [i for i in tracked
                           if self._row_body_a[i] not in stacked]
        else:
            self.last_n_excluded_stacked = 0

        self.rs.tracked_row_indices = tracked
        self.last_n_tracked_rows = len(tracked)
        self.last_n_iter_solves = 0
        self.last_iter_dq_norms = []
        self._dev_n_b = 0   # device path no-ops until caches uploaded below

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

        for body_idx, rows_on_body in self._rows_per_body.items():
            self._row_idx_by_body[body_idx] = np.asarray(
                rows_on_body, dtype=np.int64)
            self._row_off_by_body[body_idx] = np.stack(
                [self._row_off_a[i] for i in rows_on_body], axis=0)
            self._row_U_y_by_body[body_idx] = np.stack(
                [self._U_at_row[i][1] for i in rows_on_body], axis=0)

        # 6. P4 stacks for vectorised anchor write.
        n_tracked = len(tracked)
        self._tracked_rows_arr = np.asarray(tracked, dtype=np.int64)
        self._U_y_stack = np.stack(
            [self._U_at_row[i][1] for i in tracked], axis=0)
        self._floor_y_rest_arr = np.fromiter(
            (self._row_floor_y_rest[i] for i in tracked),
            dtype=np.float64, count=n_tracked)
        self._v_lift_arr = np.zeros(n_tracked, dtype=np.float64)

        # 7. Seed anchors from the FULL inertial predictor q̃ (the deformed
        #    surface y_rest + U_y·q̃ — sag AND ring, one curve). The dynamic
        #    constraint REQUIRES the bodies to see the full ringing q so the
        #    mode's inertia can push them back; the old static low-pass would
        #    filter exactly the ring that drives the two-way kick, so it is
        #    removed (two_band_coupling.html — "cubes ride the FULL dynamic
        #    surface").
        anchor_new = anchor_np.copy()
        dy_all = self._U_y_stack @ self.rs.q_hat
        anchor_new[self._tracked_rows_arr, 1] = (
            self._floor_y_rest_arr + dy_all)

        # fem_rigid cargo: form the per-body modal predictor â and fold the
        # co-rotated corner flex (R·Φ_c·â)_y into the contact anchor so the
        # gap stays  C = corner_rigid_y − (floor + U_y·q̂ − G_a·â)
        #            = (deformed cube corner) − (deformed support surface).
        # This mirrors the support's staggered q̂ seed exactly (the live a
        # still updates through the augmented Schur block each iteration).
        if self.cargo:
            self._setup_cargo_substep(solver, orientations, anchor_new)

        solver.c_world_anchor.assign(anchor_new.astype(np.float32))

    def _setup_cargo_substep(self, solver, orientations, anchor_new) -> None:
        """Build the augmented-Q layout, the cargo modal predictors, and the
        co-rotated corner-flex anchor offset for the current substep. See
        `add_cargo` / the iteration_hook augmented path (two_band_coupling.html)."""
        h = float(self.h_substep)
        h_pred = 0.0 if self.freeze_qdot else h   # frozen control: â = aⁿ

        # Augmented modal layout: support [0:r], then each cargo body's k modes.
        self._cargo_off.clear()
        off = int(self.rs.r)
        for b in sorted(self.cargo.keys()):
            k = int(self.cargo[b].k)
            self._cargo_off[b] = (off, k)
            off += k
        self._Q_dim = off

        # Inertial predictor per cargo body: snapshot aⁿ, â = aⁿ + h·ȧⁿ.
        # # DEVIATION (two_band_coupling.html): the elastic modes are
        # M-orthogonal to the 3 rigid translation modes, so Φᵀ(uniform
        # gravity) ≈ 0 — the modal self-weight forcing f_q^grav vanishes,
        # exactly as for the fixed support. Hence â = aⁿ + h·ȧⁿ (no h² term).
        for b in self.cargo:
            a = self.cargo_a[b]
            self.cargo_a_prev[b] = a.copy()
            self.cargo_a_hat[b] = a + h_pred * self.cargo_adot[b]

        # Per cargo row: nearest cube corner's modal block Φ_c (3,k), the
        # co-rotated y-gradient G_a = n̂ᵀ·R·Φ_c (frozen at substep begin), and
        # the corner flex G_a·â subtracted from the anchor.
        self._row_cargo_modal.clear()
        self._row_cargo_Ga.clear()
        for row in self.rs.tracked_row_indices:
            ba = self._row_body_a[row]
            body = self.cargo.get(ba)
            if body is None:
                continue
            off_b = self._row_off_a[row]
            cid = int(np.argmin(
                np.linalg.norm(body.corner_body - off_b, axis=1)))
            Phi_c = body.corner_modal[cid]                  # (3, k)
            self._row_cargo_modal[row] = Phi_c
            if getattr(body, "corotate", True):
                R = _quat_xyzw_to_R(orientations[ba].astype(np.float64))
                G_a = R[1, :] @ Phi_c                        # co-rotated y-row
            else:
                G_a = Phi_c[1, :].copy()                     # world-fixed (fem)
            self._row_cargo_Ga[row] = G_a
            anchor_new[row, 1] -= float(G_a @ self.cargo_a_hat[ba])

    def iteration_hook(self, solver, iter_idx: int) -> None:
        """Schur solve over q_s (drift-fix v1).

        # DEVIATION (foundation §15, plan ~/.claude/plans/...fizzy-waffle):
        the Schur variable is the algebraic static-sag coordinate q_s.
        Baseline H_{q_s} = K_q (no IIR predictor — q_s has no dynamics).
        Identical per-body contact assembly + cross-coupling as the
        legacy path, just on q_s. q_d is NOT in any block of this
        iteration; it evolves once per substep in `_substep_end_split`
        forced by the high-passed F_q_total accumulated below.
        """
        rows = self.rs.tracked_row_indices
        if not rows:
            return

        # Device-resident path: one warp launch, no host round-trip. The
        # numpy body below is the reference (CLAUDE.md rule 6) and runs on
        # CPU / when device_resident is False.
        if self._use_device(solver) and self._device_ready:
            if self._dev_n_b > 0:
                self._iteration_device(solver)
            return

        # fem_rigid cargo present ⇒ augmented-Q Schur (support q ⊕ per-body
        # elastic a). The pure-rigid CPU body below stays byte-identical.
        if self.cargo:
            self._iteration_hook_augmented(solver, iter_idx)
            return

        lam_np = solver.c_lambda.numpy()
        pen_np = solver.c_penalty.numpy()
        fmin_np = solver.c_fmin.numpy()
        fmax_np = solver.c_fmax.numpy()
        alpha_C0_np = solver.c_alpha_C0.numpy()
        stiff_np = solver.c_stiffness.numpy()
        anchor_np = solver.c_world_anchor.numpy().copy()
        positions_np = solver.x.numpy().copy()
        orientations_np = solver.q.numpy().copy()
        mass_np          = self._mass_np
        inertia_local_np = self._inertia_local_np
        x_inertial_np    = self._x_inertial_np
        q_inertial_np    = self._q_inertial_np

        h = float(self.h_substep)
        inv_dt2 = 1.0 / (h * h)
        inv_dt = 1.0 / h
        r = self.rs.r
        Mq, Kq, Dq = self.rs.Mq, self.rs.Kq, self.rs.Dq

        # Dynamic two-way modal block (two_band_coupling.html — "The Newton /
        # Schur block — only H_q gains two terms"). The support's modal
        # amplitude is a SECOND-ORDER DOF (q, q̇); one backward-Euler substep
        # of size h = h_substep:
        #   H_q = 1/h²·M_q + 1/h·D_q + K_q + Σ_j k_j U_y,j U_y,jᵀ
        #   g_q = 1/h²·M_q(q − q̃) + 1/h·D_q(q − qⁿ) + K_q q − Σ_j U_y,j f_j
        # with predictor q̃ = qⁿ + h q̇ⁿ + h² M_q⁻¹ f_q^grav (set in
        # substep_begin) and qⁿ = q at substep start (`q_prev_macro`).
        # The contact terms (− Σ U_y f, + Σ k U_y U_yᵀ) are added below in the
        # per-body row walk, identically to the quasi-static path.
        # # DEVIATION (two_band_coupling.html "Honest boundary"): the damping
        # gradient is the IMPLICIT 1/h·D_q(q−qⁿ) (consistent with the 1/h·D_q
        # Hessian and the Ė = −q̇ᵀD_qq̇ ≤ 0 passivity proof) — NOT the older
        # support-only explicit form D_q·q̇ⁿ at reduced_support_solve.py:368,
        # whose D_q/h Hessian term is only a regulariser. Both share the same
        # Hessian; this form is the finalized, passive one.
        q = self.rs.q
        q_hat = self.rs.q_hat
        q_prev = self.rs.q_prev_macro
        H_q = inv_dt2 * Mq + inv_dt * Dq + Kq
        g_q = (inv_dt2 * (Mq @ (q - q_hat))
               + inv_dt * (Dq @ (q - q_prev))
               + Kq @ q)

        # Reset the modal-load accumulator at the START of every
        # iteration. Only the LAST iteration's value persists into
        # `_substep_end_split` and drives the EMA + q_d step.
        if (self._last_F_q_contact is None
                or self._last_F_q_contact.shape[0] != r):
            self._last_F_q_contact = np.zeros(r, dtype=np.float64)
        else:
            self._last_F_q_contact[:] = 0.0

        per_body_Hx_inv: dict[int, NDArray[np.float64]] = {}
        per_body_gx:     dict[int, NDArray[np.float64]] = {}
        per_body_cross:  dict[int, NDArray[np.float64]] = {}

        max_rho2_over_m = 0.0
        rho_hits = 0

        n_hat_const = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        rho_clip = self.rho_clip

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

            A = m * inv_dt2 * np.eye(3)
            D = I_world * inv_dt2
            B = np.zeros((3, 3), dtype=np.float64)

            r_lin = m * inv_dt2 * (x_curr - x_iner)
            dq_iner = _quat_xyzw_mul(q_xyzw, _quat_xyzw_inv(q_iner))
            dtheta_iner = _quat_xyzw_to_rotvec(dq_iner)
            r_ang = I_world @ (dtheta_iner * inv_dt2)

            cross_body = np.zeros((6, r), dtype=np.float64)

            row_idx_arr = self._row_idx_by_body[body_idx]
            off_arr     = self._row_off_by_body[body_idx]
            U_y_arr     = self._row_U_y_by_body[body_idx]
            n_rows_b    = row_idx_arr.shape[0]

            r_self_w_arr = off_arr @ R.T
            j_lin_arr = np.broadcast_to(
                n_hat_const, (n_rows_b, 3))
            j_ang_arr = np.empty((n_rows_b, 3), dtype=np.float64)
            j_ang_arr[:, 0] = -r_self_w_arr[:, 2]
            j_ang_arr[:, 1] = 0.0
            j_ang_arr[:, 2] =  r_self_w_arr[:, 0]

            C_arr        = (x_curr[1] + r_self_w_arr[:, 1]
                            - anchor_np[row_idx_arr, 1])
            s_stiff_arr  = stiff_np[row_idx_arr]
            hard_arr     = np.isinf(s_stiff_arr)
            C_arr        = np.where(
                hard_arr, C_arr - alpha_C0_np[row_idx_arr], C_arr)
            lam_eff_arr  = np.where(
                hard_arr, lam_np[row_idx_arr], 0.0)
            rho_arr      = pen_np[row_idx_arr]
            rho_used_arr = np.minimum(rho_arr, rho_clip)
            rho_hits    += int(np.sum(rho_arr >= rho_clip))

            f_lo_arr     = fmin_np[row_idx_arr]
            f_hi_arr     = fmax_np[row_idx_arr]
            lam_plus_arr = rho_used_arr * C_arr + lam_eff_arr
            f_arr        = np.clip(lam_plus_arr, f_lo_arr, f_hi_arr)

            abs_C_arr     = np.abs(C_arr)
            below_mask    = (lam_plus_arr < f_lo_arr) & (abs_C_arr > 1.0e-12)
            above_mask    = (lam_plus_arr > f_hi_arr) & (abs_C_arr > 1.0e-12)
            safe_abs_C    = np.maximum(abs_C_arr, 1.0e-12)
            k_for_lhs_arr = rho_used_arr.copy()
            k_for_lhs_arr = np.where(
                below_mask,
                np.abs(f_lo_arr - lam_plus_arr) / safe_abs_C,
                k_for_lhs_arr)
            k_for_lhs_arr = np.where(
                above_mask,
                np.abs(f_hi_arr - lam_plus_arr) / safe_abs_C,
                k_for_lhs_arr)

            k_col      = k_for_lhs_arr[:, None]
            k_U_y      = k_col * U_y_arr

            # Modal-side contributions to g_{q_s} and H_{q_s}.
            #   g_{q_s} -= U_y · f          (J_{q_s}^T · f gradient)
            #   H_{q_s} += ρ · U_y U_y^T    (AL Hessian)
            g_q = g_q - (U_y_arr.T @ f_arr)
            H_q = H_q + (U_y_arr.T @ k_U_y)

            # Accumulate Σ U_y · f for the substep-end F_q_total.
            # This is the modal-frame projection of the actual contact
            # force at the current iteration's state; the LAST iteration
            # writes the value `_substep_end_split` reads.
            self._last_F_q_contact += U_y_arr.T @ f_arr

            k_j_lin    = k_col * j_lin_arr
            k_j_ang    = k_col * j_ang_arr

            A = A + j_lin_arr.T @ k_j_lin
            B = B + j_ang_arr.T @ k_j_lin
            D = D + j_ang_arr.T @ k_j_ang

            f_mag_arr  = np.abs(f_arr)
            geom_mask  = f_mag_arr > 0.0
            if np.any(geom_mask):
                g_diag_batch = _geom_stiffness_diag_batch(
                    n_hat_const, r_self_w_arr)
                weights = (f_mag_arr * geom_mask)[:, None]
                D = D + np.diag((g_diag_batch * weights).sum(axis=0))

            r_lin = r_lin + j_lin_arr.T @ f_arr
            r_ang = r_ang + j_ang_arr.T @ f_arr

            # Cross block H_{x q_s} = ρ J_x · J_{q_s}^T = −ρ J_x · U_y^T.
            cross_body[:3, :] += j_lin_arr.T @ k_U_y
            cross_body[3:, :] += j_ang_arr.T @ k_U_y

            j_ang_sq_arr = (j_ang_arr * j_ang_arr).sum(axis=1)
            jjsum_arr    = 1.0 + j_ang_sq_arr
            row_score    = (rho_used_arr ** 2) * jjsum_arr / max(m, 1e-12)
            if n_rows_b > 0:
                max_rho2_over_m = max(max_rho2_over_m,
                                      float(row_score.max()))

            H_x = np.block([
                [A,           B.T],
                [B,           D  ],
            ])
            g_x = np.concatenate([r_lin, r_ang])

            H_x_reg = H_x + 1e-12 * np.eye(6)
            try:
                H_x_inv = np.linalg.inv(H_x_reg)
            except np.linalg.LinAlgError:
                continue
            per_body_Hx_inv[body_idx] = H_x_inv
            per_body_gx[body_idx] = g_x
            per_body_cross[body_idx] = -cross_body

        # Schur reduce over q_s.
        rhs_q = -g_q
        S = H_q.copy()
        for body_idx in per_body_Hx_inv:
            M = per_body_cross[body_idx]
            Hxi = per_body_Hx_inv[body_idx]
            gxi = per_body_gx[body_idx]
            Hxi_M = Hxi @ M
            S = S - M.T @ Hxi_M
            rhs_q = rhs_q + M.T @ Hxi @ gxi

        eps = max(
            self.eps_baseline * (float(np.trace(Kq)) / max(r, 1)),
            self.eps_cross_factor * max_rho2_over_m,
        )
        S_reg = S + eps * np.eye(r)
        try:
            dq = np.linalg.solve(S_reg, rhs_q)
        except np.linalg.LinAlgError:
            return

        if self.diagnostic_mode:
            try:
                cond = float(np.linalg.cond(S_reg))
            except Exception:
                cond = float('inf')
            self.last_Schur_condition_estimate = min(cond, 1e16)

        # Apply Δq to the dynamic modal coordinate, then back-substitute
        # for the body deltas through the cross block.
        q_new = self.rs.q + dq
        self.rs.q = q_new

        max_dx = 0.0
        max_dtheta = 0.0
        x_out = positions_np.copy()
        q_out = orientations_np.copy()
        for body_idx, Hxi in per_body_Hx_inv.items():
            M = per_body_cross[body_idx]
            gxi = per_body_gx[body_idx]
            rhs6 = -(gxi + M @ dq)
            delta = Hxi @ rhs6
            d_x = delta[:3]
            d_theta = delta[3:]
            x_out[body_idx] = (positions_np[body_idx]
                               + delta[:3].astype(np.float32))
            dq_quat = _quat_xyzw_from_rotvec(delta[3:])
            new_q = _quat_xyzw_mul(dq_quat, q_out[body_idx].astype(np.float64))
            n = float(np.linalg.norm(new_q))
            if n > 1e-12:
                new_q = new_q / n
            q_out[body_idx] = new_q.astype(np.float32)
            max_dx = max(max_dx, float(np.linalg.norm(d_x)))
            max_dtheta = max(max_dtheta, float(np.linalg.norm(d_theta)))

        solver.x.assign(x_out)
        solver.q.assign(q_out)

        # Refresh anchors with the updated FULL q (the deformed surface the
        # bodies rest on, y_rest + U_y·q). Only in monolithic mode; the
        # staggered default holds the substep_begin q̃ seed through the
        # iteration loop to kill the rocking limit cycle (the Δx↔Δq cross
        # block still transmits q within the substep). See
        # `refresh_anchor_each_iter`.
        if self.refresh_anchor_each_iter:
            anchor_out = anchor_np.copy()
            dy_all = self._U_y_stack @ q_new
            anchor_out[self._tracked_rows_arr, 1] = (
                self._floor_y_rest_arr + dy_all)
            solver.c_world_anchor.assign(anchor_out.astype(np.float32))

        self.last_max_dx_norm = max_dx
        self.last_max_dtheta_norm = max_dtheta
        self.last_dq_norm = float(np.linalg.norm(dq))
        self.last_n_iter_solves += 1
        self.last_iter_dq_norms.append(self.last_dq_norm)
        self.last_rho_clip_hits = rho_hits

    def _iteration_hook_augmented(self, solver, iter_idx: int) -> None:
        """One coupled Schur iteration over the AUGMENTED modal vector
        Q = [q_support(r); a_b(k_b); ...] (two_band_coupling.html, generalized
        to moving cargo). Identical math to `iteration_hook`'s pure-rigid CPU
        body, with three additions for each cargo body's FLOOR rows:

          C unchanged (the cube's corner flex is already in the anchor);
          per-row modal gradient grows from −U_y (support) to also carry the
          co-rotated cube term G_a = n̂ᵀ·R·Φ_c (FEMRigidModalBody, modal cols
          = R·Φ_c) in that body's a-columns; the dynamic modal block is
          block-diagonal (support M_q/K_q/D_q ⊕ per-cube I/Ω²/D_modal).

        # DEVIATION (plan §3 "solved in its per-body block"): the cube modes
        # are eliminated as a GLOBAL block (augmented Q), not folded into the
        # per-body 6×6. The two orderings are exact block-Gaussian re-orderings
        # of the SAME monolithic Newton system ⇒ identical converged Δ; this
        # one reuses the existing Schur machinery (per-body blocks unchanged).
        """
        rows = self.rs.tracked_row_indices

        lam_np = solver.c_lambda.numpy()
        pen_np = solver.c_penalty.numpy()
        fmin_np = solver.c_fmin.numpy()
        fmax_np = solver.c_fmax.numpy()
        alpha_C0_np = solver.c_alpha_C0.numpy()
        stiff_np = solver.c_stiffness.numpy()
        anchor_np = solver.c_world_anchor.numpy().copy()
        positions_np = solver.x.numpy().copy()
        orientations_np = solver.q.numpy().copy()
        mass_np          = self._mass_np
        inertia_local_np = self._inertia_local_np
        x_inertial_np    = self._x_inertial_np
        q_inertial_np    = self._q_inertial_np

        h = float(self.h_substep)
        inv_dt2 = 1.0 / (h * h)
        inv_dt = 1.0 / h
        r = self.rs.r
        R_dim = int(self._Q_dim)

        # Augmented block-diagonal dynamic modal block (support ⊕ per-cube).
        Mq_a = np.zeros((R_dim, R_dim), dtype=np.float64)
        Kq_a = np.zeros((R_dim, R_dim), dtype=np.float64)
        Dq_a = np.zeros((R_dim, R_dim), dtype=np.float64)
        Mq_a[:r, :r] = self.rs.Mq
        Kq_a[:r, :r] = self.rs.Kq
        Dq_a[:r, :r] = self.rs.Dq
        Q      = np.zeros(R_dim, dtype=np.float64)
        Q_hat  = np.zeros(R_dim, dtype=np.float64)
        Q_prev = np.zeros(R_dim, dtype=np.float64)
        Q[:r], Q_hat[:r], Q_prev[:r] = (
            self.rs.q, self.rs.q_hat, self.rs.q_prev_macro)
        for b, (s, k) in self._cargo_off.items():
            body = self.cargo[b]
            # Uniform cargo blocks: fem_rigid → (I, diag(ω²), D_modal); abd →
            # (M_F, 0, α₀M_F) with the elastic in the NONLINEAR V⊥ added below.
            Mq_a[s:s + k, s:s + k] = body.Mq_block
            Kq_a[s:s + k, s:s + k] = body.Kq_block
            Dq_a[s:s + k, s:s + k] = body.Dq_block
            Q[s:s + k]      = self.cargo_a[b]
            Q_hat[s:s + k]  = self.cargo_a_hat[b]
            Q_prev[s:s + k] = self.cargo_a_prev[b]

        # H_Q = 1/h²M_q + 1/h D_q + K_q ;  g_Q = 1/h²M_q(Q−Q̂)+1/h D_q(Q−Qⁿ)+K_q Q
        H_Q = inv_dt2 * Mq_a + inv_dt * Dq_a + Kq_a
        g_Q = (inv_dt2 * (Mq_a @ (Q - Q_hat))
               + inv_dt * (Dq_a @ (Q - Q_prev))
               + Kq_a @ Q)

        # Nonlinear elastic (abd V⊥, ABD Eq. 6–8): add the per-body internal
        # grad/Hess at the live deformation d. Re-linearized each iteration (the
        # affine internal is genuinely nonlinear). fem_rigid is linear ⇒ no-op.
        for b, (s, k) in self._cargo_off.items():
            body = self.cargo[b]
            if body.has_nonlinear_internal:
                d = self.cargo_a[b]
                g_Q[s:s + k] += body.internal_grad_d(d)
                H_Q[s:s + k, s:s + k] += body.internal_hess_d(d)

        if (self._last_F_q_contact is None
                or self._last_F_q_contact.shape[0] != r):
            self._last_F_q_contact = np.zeros(r, dtype=np.float64)
        else:
            self._last_F_q_contact[:] = 0.0

        per_body_Hx_inv: dict[int, NDArray[np.float64]] = {}
        per_body_gx:     dict[int, NDArray[np.float64]] = {}
        per_body_cross:  dict[int, NDArray[np.float64]] = {}

        max_rho2_over_m = 0.0
        rho_hits = 0
        n_hat_const = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        rho_clip = self.rho_clip

        for body_idx, rows_on_body in self._rows_per_body.items():
            m = float(mass_np[body_idx])
            if m <= 0.0 or not np.isfinite(m):
                continue
            q_xyzw = orientations_np[body_idx].astype(np.float64)
            x_curr = positions_np[body_idx].astype(np.float64)
            x_iner = x_inertial_np[body_idx].astype(np.float64)
            q_iner = q_inertial_np[body_idx].astype(np.float64)

            Rb = _quat_xyzw_to_R(q_xyzw)
            I_local = inertia_local_np[body_idx].astype(np.float64)
            I_world = Rb @ I_local @ Rb.T

            A = m * inv_dt2 * np.eye(3)
            D = I_world * inv_dt2
            B = np.zeros((3, 3), dtype=np.float64)

            r_lin = m * inv_dt2 * (x_curr - x_iner)
            dq_iner = _quat_xyzw_mul(q_xyzw, _quat_xyzw_inv(q_iner))
            dtheta_iner = _quat_xyzw_to_rotvec(dq_iner)
            r_ang = I_world @ (dtheta_iner * inv_dt2)

            cross_body = np.zeros((6, R_dim), dtype=np.float64)

            row_idx_arr = self._row_idx_by_body[body_idx]
            off_arr     = self._row_off_by_body[body_idx]
            U_y_arr     = self._row_U_y_by_body[body_idx]
            n_rows_b    = row_idx_arr.shape[0]

            r_self_w_arr = off_arr @ Rb.T
            j_lin_arr = np.broadcast_to(n_hat_const, (n_rows_b, 3))
            j_ang_arr = np.empty((n_rows_b, 3), dtype=np.float64)
            j_ang_arr[:, 0] = -r_self_w_arr[:, 2]
            j_ang_arr[:, 1] = 0.0
            j_ang_arr[:, 2] =  r_self_w_arr[:, 0]

            C_arr        = (x_curr[1] + r_self_w_arr[:, 1]
                            - anchor_np[row_idx_arr, 1])
            s_stiff_arr  = stiff_np[row_idx_arr]
            hard_arr     = np.isinf(s_stiff_arr)
            C_arr        = np.where(
                hard_arr, C_arr - alpha_C0_np[row_idx_arr], C_arr)
            lam_eff_arr  = np.where(hard_arr, lam_np[row_idx_arr], 0.0)
            rho_arr      = pen_np[row_idx_arr]
            rho_used_arr = np.minimum(rho_arr, rho_clip)
            rho_hits    += int(np.sum(rho_arr >= rho_clip))

            f_lo_arr     = fmin_np[row_idx_arr]
            f_hi_arr     = fmax_np[row_idx_arr]
            lam_plus_arr = rho_used_arr * C_arr + lam_eff_arr
            f_arr        = np.clip(lam_plus_arr, f_lo_arr, f_hi_arr)

            abs_C_arr     = np.abs(C_arr)
            below_mask    = (lam_plus_arr < f_lo_arr) & (abs_C_arr > 1.0e-12)
            above_mask    = (lam_plus_arr > f_hi_arr) & (abs_C_arr > 1.0e-12)
            safe_abs_C    = np.maximum(abs_C_arr, 1.0e-12)
            k_for_lhs_arr = rho_used_arr.copy()
            k_for_lhs_arr = np.where(
                below_mask,
                np.abs(f_lo_arr - lam_plus_arr) / safe_abs_C, k_for_lhs_arr)
            k_for_lhs_arr = np.where(
                above_mask,
                np.abs(f_hi_arr - lam_plus_arr) / safe_abs_C, k_for_lhs_arr)

            k_col      = k_for_lhs_arr[:, None]
            k_j_lin    = k_col * j_lin_arr
            k_j_ang    = k_col * j_ang_arr

            A = A + j_lin_arr.T @ k_j_lin
            B = B + j_ang_arr.T @ k_j_lin
            D = D + j_ang_arr.T @ k_j_ang

            f_mag_arr  = np.abs(f_arr)
            geom_mask  = f_mag_arr > 0.0
            if np.any(geom_mask):
                g_diag_batch = _geom_stiffness_diag_batch(
                    n_hat_const, r_self_w_arr)
                weights = (f_mag_arr * geom_mask)[:, None]
                D = D + np.diag((g_diag_batch * weights).sum(axis=0))

            r_lin = r_lin + j_lin_arr.T @ f_arr
            r_ang = r_ang + j_ang_arr.T @ f_arr

            # Augmented per-row modal gradient G_row (n_rows_b, R_dim):
            #   support cols [0:r] = −U_y  (∂C/∂q_support, raising surface)
            #   cargo  cols [s:s+k] = +G_a = n̂ᵀ·R·Φ_c  (∂C/∂a, corner flex)
            G_rows = np.zeros((n_rows_b, R_dim), dtype=np.float64)
            G_rows[:, :r] = -U_y_arr
            cargo_off = self._cargo_off.get(body_idx)
            if cargo_off is not None:
                s, kk = cargo_off
                # G_a frozen at substep begin (parity with device k_eval_cargo).
                G_a_arr = np.stack(
                    [self._row_cargo_Ga[int(i)] for i in row_idx_arr])    # (n,k)
                G_rows[:, s:s + kk] = G_a_arr

            k_G = k_col * G_rows
            g_Q = g_Q + (G_rows.T @ f_arr)
            H_Q = H_Q + (G_rows.T @ k_G)

            # Support-only modal load diagnostic (back-compat): Σ U_y·f.
            self._last_F_q_contact += U_y_arr.T @ f_arr

            cross_body[:3, :] += j_lin_arr.T @ k_G
            cross_body[3:, :] += j_ang_arr.T @ k_G

            j_ang_sq_arr = (j_ang_arr * j_ang_arr).sum(axis=1)
            jjsum_arr    = 1.0 + j_ang_sq_arr
            row_score    = (rho_used_arr ** 2) * jjsum_arr / max(m, 1e-12)
            if n_rows_b > 0:
                max_rho2_over_m = max(max_rho2_over_m, float(row_score.max()))

            H_x = np.block([[A, B.T], [B, D]])
            g_x = np.concatenate([r_lin, r_ang])
            H_x_reg = H_x + 1e-12 * np.eye(6)
            try:
                H_x_inv = np.linalg.inv(H_x_reg)
            except np.linalg.LinAlgError:
                continue
            per_body_Hx_inv[body_idx] = H_x_inv
            per_body_gx[body_idx] = g_x
            # G_row already carries the support −U_y sign, so the cross block
            # is used directly (no global negate — see iteration_hook note).
            per_body_cross[body_idx] = cross_body

        # Schur reduce over the augmented Q.
        rhs_Q = -g_Q
        S = H_Q.copy()
        for body_idx in per_body_Hx_inv:
            Mblk = per_body_cross[body_idx]
            Hxi = per_body_Hx_inv[body_idx]
            gxi = per_body_gx[body_idx]
            S = S - Mblk.T @ (Hxi @ Mblk)
            rhs_Q = rhs_Q + Mblk.T @ (Hxi @ gxi)

        eps = max(
            self.eps_baseline * (float(np.trace(Kq_a)) / max(R_dim, 1)),
            self.eps_cross_factor * max_rho2_over_m,
        )
        S_reg = S + eps * np.eye(R_dim)
        try:
            dQ = np.linalg.solve(S_reg, rhs_Q)
        except np.linalg.LinAlgError:
            return

        if self.diagnostic_mode:
            try:
                cond = float(np.linalg.cond(S_reg))
            except Exception:
                cond = float('inf')
            self.last_Schur_condition_estimate = min(cond, 1e16)

        # Apply ΔQ: support q ⊕ each cargo a.
        self.rs.q = self.rs.q + dQ[:r]
        for b, (s, k) in self._cargo_off.items():
            self.cargo_a[b] = self.cargo_a[b] + dQ[s:s + k]

        max_dx = 0.0
        max_dtheta = 0.0
        x_out = positions_np.copy()
        q_out = orientations_np.copy()
        for body_idx, Hxi in per_body_Hx_inv.items():
            Mblk = per_body_cross[body_idx]
            gxi = per_body_gx[body_idx]
            delta = Hxi @ (-(gxi + Mblk @ dQ))
            x_out[body_idx] = (positions_np[body_idx]
                               + delta[:3].astype(np.float32))
            dq_quat = _quat_xyzw_from_rotvec(delta[3:])
            new_q = _quat_xyzw_mul(dq_quat, q_out[body_idx].astype(np.float64))
            n = float(np.linalg.norm(new_q))
            if n > 1e-12:
                new_q = new_q / n
            q_out[body_idx] = new_q.astype(np.float32)
            max_dx = max(max_dx, float(np.linalg.norm(delta[:3])))
            max_dtheta = max(max_dtheta, float(np.linalg.norm(delta[3:])))

        solver.x.assign(x_out)
        solver.q.assign(q_out)

        if self.refresh_anchor_each_iter:
            anchor_out = anchor_np.copy()
            dy_all = self._U_y_stack @ self.rs.q
            anchor_out[self._tracked_rows_arr, 1] = (
                self._floor_y_rest_arr + dy_all)
            # re-fold cargo corner flex (live a) for the monolithic variant.
            for row, Phi_c in self._row_cargo_modal.items():
                ba = self._row_body_a[row]
                Rb = _quat_xyzw_to_R(q_out[ba].astype(np.float64))
                anchor_out[row, 1] -= float((Rb[1, :] @ Phi_c) @ self.cargo_a[ba])
            solver.c_world_anchor.assign(anchor_out.astype(np.float32))

        self.last_max_dx_norm = max_dx
        self.last_max_dtheta_norm = max_dtheta
        self.last_dq_norm = float(np.linalg.norm(dQ[:r]))
        self.last_n_iter_solves += 1
        self.last_iter_dq_norms.append(float(np.linalg.norm(dQ)))
        self.last_rho_clip_hits = rho_hits

    def substep_end_hook(self, solver) -> None:
        """Commit the dynamic modal velocity and log diagnostics
        (two_band_coupling.html — "After the step: q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h").

        The converged q already carries the full sag+ring (the iteration
        solved the coupled (z, q) block); here we just finite-difference the
        new velocity from the substep's q delta, which feeds the next
        substep's predictor q̃ — that is the entire ring-carrying mechanism.
        No EMA, no IIR, no separate q_d. Passivity is automatic (backward
        Euler), so the per-substep energy is logged, not governed.
        """
        # Full GPU-resident path: qdot update + diagnostics run on-device;
        # host readback is once per macro-step (render/HUD). The numpy body
        # below is the reference (CLAUDE.md rule 6).
        if self._use_device(solver):
            self.last_n_iter_solves = int(solver.iterations) + (
                1 if getattr(solver, "post_stabilize", False) else 0)
            self._substep_end_device(solver)
            return

        h = float(self.h_substep)
        Mq, Kq, Dq = self.rs.Mq, self.rs.Kq, self.rs.Dq

        # Modal velocity update: q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h. The frozen control
        # holds q̇ ≡ 0 (no ring carried — the two-way counterfactual).
        if not self.freeze_qdot:
            self.rs.qdot = (self.rs.q - self.rs.q_prev_macro) / h

        # fem_rigid cargo: commit each cube's modal velocity ȧⁿ⁺¹ = (aⁿ⁺¹−aⁿ)/h
        # (same finite-difference ring-carrying mechanism, per cube) and log
        # the total cargo modal energy E_cargo = Σ_b (½ȧᵀȧ + ½aᵀΩ²a).
        self.last_cargo_modal_KE = 0.0
        self.last_cargo_modal_PE = 0.0
        for b, body in self.cargo.items():
            if not self.freeze_qdot:
                self.cargo_adot[b] = (
                    self.cargo_a[b] - self.cargo_a_prev[b]) / h
            adot = self.cargo_adot[b]
            a = self.cargo_a[b]
            # KE = ½ȧᵀ M_F ȧ (M_F = I for mass-normalized modes); PE is the
            # body's elastic energy (linear ½aᵀΩ²a or the nonlinear V⊥).
            self.last_cargo_modal_KE += 0.5 * float(adot @ (body.Mq_block @ adot))
            if body.has_nonlinear_internal:
                self.last_cargo_modal_PE += float(body.internal_energy(a))
            else:
                self.last_cargo_modal_PE += 0.5 * float(a @ (body.omega2 * a))

        # F_q_total = Σ U_y·f (the modal projection of the contact load) was
        # accumulated in the final iteration — kept as a diagnostic only.
        if self._last_F_q_contact is None:
            F_q_total = np.zeros(self.rs.r, dtype=np.float64)
        else:
            F_q_total = self._last_F_q_contact.copy()

        # Passivity certificate — total modal mechanical energy
        # E = ½q̇ᵀM_q q̇ + ½qᵀK_q q. Backward Euler is dissipative, so absent
        # contact forcing E is monotone non-increasing; with forcing it may
        # rise but only up to the contact work. Logged, not enforced (no
        # governor — passivity is structural). A violation here means E rose
        # by more than the substep contact work |h·F_qᵀq̇|.
        E_now = (0.5 * float(self.rs.qdot @ (Mq @ self.rs.qdot))
                 + 0.5 * float(self.rs.q @ (Kq @ self.rs.q)))
        W_bound = abs(h * float(F_q_total @ self.rs.qdot))
        if (self._E_modal_prev is not None
                and E_now > self._E_modal_prev + W_bound + 1e-12):
            self.last_passivity_violations += 1
        self._E_modal_prev = E_now

        # Diagnostics on the single dynamic (q, q̇).
        self.last_q_s_norm        = float(np.linalg.norm(self.rs.q))
        self.last_q_d_norm        = 0.0
        self.last_qdot_d_norm     = float(np.linalg.norm(self.rs.qdot))
        self.last_F_q_total_norm  = float(np.linalg.norm(F_q_total))
        self.last_F_q_static_norm = 0.0
        self.last_F_q_dyn_norm    = float(np.linalg.norm(F_q_total))
        self.last_q_norm    = float(np.linalg.norm(self.rs.q))
        self.last_qdot_norm = self.last_qdot_d_norm

        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, self.rs.q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
        else:
            self.last_max_support_deflection = 0.0

        # Modal energy diagnostics on the full (q, q̇).
        self.last_modal_KE = 0.5 * float(self.rs.qdot @ (Mq @ self.rs.qdot))
        self.last_modal_PE = 0.5 * float(self.rs.q @ (Kq @ self.rs.q))
        self.last_damp_power = float(self.rs.qdot @ (Dq @ self.rs.qdot))
        self.last_q_acc_norm = 0.0

        # Track λ across tracked rows (back-compat with legacy diagnostics).
        rows_tr = self.rs.tracked_row_indices
        if rows_tr:
            lam_np_end = solver.c_lambda.numpy()
            self.last_contact_lambda_max = float(
                np.max(np.abs(lam_np_end[rows_tr])))
        else:
            self.last_contact_lambda_max = 0.0

        # Substep-resolution log.
        if self.log_substeps:
            self.substep_log.append({
                "substep_index": int(self._substep_index),
                "t_substep_s":   float(self._substep_index * h),
                "q_norm_m":      self.last_q_norm,
                "qdot_norm":     self.last_qdot_norm,
                "q_acc_norm":    self.last_q_acc_norm,
                "KE_modal_J":    self.last_modal_KE,
                "PE_modal_J":    self.last_modal_PE,
                "E_modal_J":     E_now,
                "P_damp_W":      self.last_damp_power,
                "contact_lambda_max": self.last_contact_lambda_max,
                "max_support_deflection_m": self.last_max_support_deflection,
                "n_iter_solves": int(self.last_n_iter_solves),
                "F_q_total_norm":  self.last_F_q_total_norm,
            })
        self._substep_index += 1

        # Contact residual (max penetration over tracked rows).
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



