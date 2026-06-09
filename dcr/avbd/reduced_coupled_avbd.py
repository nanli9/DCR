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
from ..modal.exact_resonator import (
    dynamic_compliance_step_precompute,
    exact_modal_step_precompute,
)


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

    # Body mass cache (filled at attach by world).
    body_mass: dict[int, float] = field(default_factory=dict)

    # ---- IIR exact-resonator workspace ----
    # Populated by substep_begin_hook for the q_d dynamic-component step.
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
    # Eigenbasis fast-path: diagonal aliases of S_h, S_h_inv, T_h as
    # length-r vectors. Set in substep_begin_hook when rs.is_eigenbasis;
    # None on the synthetic path. Used in iteration_hook and
    # substep_end_hook to replace dense r×r matvec with elementwise ops.
    S_h_diag:     NDArray[np.float64] | None = None
    S_h_inv_diag: NDArray[np.float64] | None = None
    T_h_diag:     NDArray[np.float64] | None = None

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
    # Substep-start q_d energy snapshot (for the passivity log).
    _E_q_d_substep_begin: float = 0.0
    # First-substep flag: drives `α = 1` in the EMA on the very first
    # substep so F_q_static_lp jumps to F_q_total instead of starting at
    # zero and dumping the full static load into q_d.
    _first_substep_split: bool = True
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
    _eps_block_dim: int = 64

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # GPU device-residency (full: substep_begin / iteration / substep_end
    # all run on-device; topology is uploaded ONCE; the only host readback
    # is once per macro-step for the render/HUD). See reduced_coupled_kernels.
    # ------------------------------------------------------------------
    def _use_device(self, solver) -> bool:
        """True when the device-resident path should run for this solver."""
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

        # ---- modal constants (uploaded once) ----
        d["Kq"] = wp.array(self.rs.Kq.astype(np.float64), dtype=f64, device=dev)
        d["Mq"] = wp.array(self.rs.Mq.astype(np.float64), dtype=f64, device=dev)
        d["Dq"] = wp.array(self.rs.Dq.astype(np.float64), dtype=f64, device=dev)
        d["Mq_diag"] = wp.array(np.diag(self.rs.Mq).astype(np.float64),
                                dtype=f64, device=dev)
        d["eigen_omega"] = wp.array(
            np.asarray(self.rs.eigen_omegas, dtype=np.float64), dtype=f64,
            device=dev)
        d["eigen_zeta"] = wp.array(
            np.asarray(self.rs.eigen_zetas, dtype=np.float64), dtype=f64,
            device=dev)
        d["grid_Uy"] = wp.array(
            self.rs.U_points[:, 1, :].astype(np.float64), dtype=f64,
            device=dev)
        # ---- resident modal state ----
        d["q_s"] = wp.zeros(r, dtype=f64, device=dev)
        d["q_d"] = wp.zeros(r, dtype=f64, device=dev)
        d["qdot_d"] = wp.zeros(r, dtype=f64, device=dev)
        d["F_q_static_lp"] = wp.zeros(r, dtype=f64, device=dev)
        d["q_free"] = wp.zeros(r, dtype=f64, device=dev)
        d["qdot_free"] = wp.zeros(r, dtype=f64, device=dev)
        d["S_h_diag"] = wp.zeros(r, dtype=f64, device=dev)
        d["T_h_diag"] = wp.zeros(r, dtype=f64, device=dev)
        d["F_q_dyn"] = wp.zeros(r, dtype=f64, device=dev)
        d["q_total"] = wp.zeros(r, dtype=f64, device=dev)
        d["qdot_total"] = wp.zeros(r, dtype=f64, device=dev)
        d["escal"] = wp.zeros(4, dtype=f64, device=dev)        # [0]=E_q_d_begin
        d["first_substep"] = wp.ones(1, dtype=int, device=dev)
        d["pass_counter"] = wp.zeros(1, dtype=int, device=dev)
        # ---- iteration scratch ----
        d["Hq"] = wp.zeros((r, r), dtype=f64, device=dev)
        d["S"] = wp.zeros((r, r), dtype=f64, device=dev)
        d["gq"] = wp.zeros(r, dtype=f64, device=dev)
        d["Fq"] = wp.zeros(r, dtype=f64, device=dev)
        d["rhs"] = wp.zeros(r, dtype=f64, device=dev)
        d["dq"] = wp.zeros(r, dtype=f64, device=dev)
        d["diag"] = wp.zeros(8, dtype=f64, device=dev)
        d["counts"] = wp.zeros(3, dtype=int, device=dev)  # [n_b, n_tracked, tot]
        # ---- topology (uploaded once in _upload_topology_once) ----
        d["body_ids"] = wp.zeros(max_b, dtype=int, device=dev)
        d["body_row_start"] = wp.zeros(max_b + 1, dtype=int, device=dev)
        d["row_index"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_body"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_off"] = wp.zeros(cap_rows, dtype=vec3d, device=dev)
        d["row_U_y"] = wp.zeros((cap_rows, r), dtype=f64, device=dev)
        d["rowdata"] = wp.zeros((cap_rows, 8), dtype=f64, device=dev)
        d["floor_y_rest"] = wp.zeros(cap_rows, dtype=f64, device=dev)
        # ---- per-body block-inverse + cross scratch ----
        d["b_TL"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_TR"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_BL"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_BR"] = wp.zeros(max_b, dtype=mat33d, device=dev)
        d["b_gx0"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["b_gx1"] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["M"] = wp.zeros((max_b, 6, r), dtype=f64, device=dev)
        d["rho_score"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["b_dxn"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["b_dthn"] = wp.zeros(max_b, dtype=f64, device=dev)

        # Cached scalars.
        self._dev_inv_dt2 = 1.0 / (float(self.h_substep) ** 2)
        self._dev_rho_clip = float(self.rho_clip)
        self._dev_eps_base = (self.eps_baseline
                              * float(np.trace(self.rs.Kq)) / max(r, 1))
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
            self._k_eps_tiled = make_k_eps_solve_tiled(r)
            # Warmup: S/rhs are freshly zeroed ⇒ solves ε·I·dq = 0 ⇒ dq = 0,
            # q_s unchanged (still zero). Forces an out-of-capture compile.
            wp.launch_tiled(
                self._k_eps_tiled, dim=[1], device=dev,
                block_dim=self._eps_block_dim, inputs=[
                    d["counts"], d["rho_score"], wp.float64(self._dev_eps_base),
                    wp.float64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"],
                    d["q_s"], d["diag"]])
            wp.synchronize_device(dev)
        self._dev_h_sub = float(self.h_substep)
        self._dev_tau = float(self.modal_static_lp_tau)
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
        start = 0
        ordered_rows: list[int] = []
        for t, b in enumerate(bodies):
            body_ids[t] = b
            body_row_start[t] = start
            for i in rows_per_body[b]:
                row_index[start] = i
                row_body[start] = b
                row_off[start] = off_a_np[i].astype(np.float64)
                floor_y[start] = self.rs.floor_y_rest[i]
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
        # Seed resident modal state from the host truth (zeros at sim start, or
        # whatever the coupler/rs carry on a mid-run switch).
        d["q_s"].assign(self.rs.q_s.astype(np.float64))
        d["q_d"].assign(self.rs.q_d.astype(np.float64))
        d["qdot_d"].assign(self.rs.qdot_d.astype(np.float64))
        d["F_q_static_lp"].assign(self.rs.F_q_static_lp.astype(np.float64))

    def _substep_begin_device(self, solver) -> None:
        """Device substep_begin: (one-time) identify rows + alloc + upload;
        then per substep recompute U_y, snapshot modal energy, run the eigen
        IIR precompute, and seed the contact anchor from q_s — all on-device."""
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
        cap_rows = int(self._dev_cap_rows)
        f64 = wp.float64
        # Recompute basis U_y at the (moving) contact corners.
        wp.launch(K.k_eval_basis, dim=cap_rows, device=dev, inputs=[
            solver.x, solver.q, d["counts"], r, d["row_index"], d["row_body"],
            d["row_off"], d["grid_Uy"], int(self.n_grid_x), int(self.n_grid_z),
            f64(self.shelf_length), f64(self.shelf_width), d["row_U_y"]])
        # Snapshot q_d modal energy (passivity reference).
        wp.launch(K.k_modal_energy, dim=1, device=dev, inputs=[
            r, d["q_d"], d["qdot_d"], d["Mq"], d["Kq"], d["escal"], int(0)])
        # Eigen exact-resonator precompute on (q_d, q̇_d).
        wp.launch(K.k_iir_precompute, dim=r, device=dev, inputs=[
            r, d["q_d"], d["qdot_d"], d["eigen_omega"], d["eigen_zeta"],
            d["Mq_diag"], f64(self._dev_h_sub), d["q_free"], d["qdot_free"],
            d["S_h_diag"], d["T_h_diag"]])
        # Seed anchors from q_s (k_anchor; diag[3]==0 in the normal case).
        wp.launch(K.k_anchor, dim=cap_rows, device=dev, inputs=[
            r, d["counts"], d["row_index"], d["row_U_y"], d["floor_y_rest"],
            d["q_s"], d["diag"], solver.c_world_anchor])

    def _iteration_device(self, solver) -> None:
        """One coupled Schur iteration as a sequence of parallel device-kernel
        launches (no host round-trip — the whole point). Launch order encodes
        the data dependencies on the stream. Mirrors iteration_hook's math."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        d = self._dbuf
        dev = solver.device
        r = int(self._dev_r)
        cap_rows = int(self._dev_cap_rows)
        max_b = int(self._dev_max_b)
        f64 = wp.float64

        # 1. per-row contact forces.
        wp.launch(K.k_rowforce, dim=cap_rows, device=dev, inputs=[
            solver.x, solver.q, solver.c_world_anchor, solver.c_lambda,
            solver.c_penalty, solver.c_fmin, solver.c_fmax, solver.c_alpha_C0,
            solver.c_stiffness, d["counts"], d["row_index"], d["row_body"],
            d["row_off"], f64(self._dev_rho_clip), d["rowdata"]])
        # 2. modal Hessian + gradient (parallel, deterministic).
        wp.launch(K.k_hq, dim=(r, r), device=dev, inputs=[
            r, d["counts"], d["Kq"], d["row_U_y"], d["rowdata"], d["Hq"]])
        wp.launch(K.k_g, dim=r, device=dev, inputs=[
            r, d["counts"], d["Kq"], d["q_s"], d["row_U_y"], d["rowdata"],
            d["gq"], d["Fq"]])
        # 3. per-body H_x assembly + block inverse.
        wp.launch(K.k_body, dim=max_b, device=dev, inputs=[
            solver.x, solver.q, solver.mass, solver.inertia_local,
            solver.x_inertial, solver.q_inertial, r, d["counts"],
            d["body_ids"], d["body_row_start"], d["row_U_y"], d["rowdata"],
            f64(self._dev_inv_dt2), d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"],
            d["b_gx0"], d["b_gx1"], d["M"], d["rho_score"]])
        # 4. Schur reduce + rhs.
        wp.launch(K.k_schur, dim=(r, r), device=dev, inputs=[
            r, d["counts"], d["Hq"], d["b_TL"], d["b_TR"], d["b_BL"],
            d["b_BR"], d["M"], d["S"]])
        wp.launch(K.k_rhs, dim=r, device=dev, inputs=[
            r, d["counts"], d["gq"], d["b_TL"], d["b_TR"], d["b_BL"],
            d["b_BR"], d["b_gx0"], d["b_gx1"], d["M"], d["rhs"]])
        # 5. ε-regularize + r×r solve + q_s update. Block-cooperative Cholesky
        # (tile API) when available — replaces the single-thread GE that the
        # profiler flagged as the dominant cost; falls back to k_eps_solve on
        # CPU / when the tiled kernel is unavailable.
        if self._k_eps_tiled is not None:
            wp.launch_tiled(
                self._k_eps_tiled, dim=[1], device=dev,
                block_dim=self._eps_block_dim, inputs=[
                    d["counts"], d["rho_score"], f64(self._dev_eps_base),
                    f64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"],
                    d["q_s"], d["diag"]])
        else:
            wp.launch(K.k_eps_solve, dim=1, device=dev, inputs=[
                r, d["counts"], d["rho_score"], f64(self._dev_eps_base),
                f64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"], d["q_s"],
                d["diag"]])
        # 6. back-substitute body deltas + diagnostics + anchor refresh.
        wp.launch(K.k_backsub, dim=max_b, device=dev, inputs=[
            solver.x, solver.q, solver.mass, r, d["counts"], d["body_ids"],
            d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"], d["b_gx0"], d["b_gx1"],
            d["M"], d["dq"], d["diag"], d["b_dxn"], d["b_dthn"]])
        wp.launch(K.k_reduce_diag, dim=1, device=dev, inputs=[
            d["counts"], d["b_dxn"], d["b_dthn"], d["diag"]])
        wp.launch(K.k_anchor, dim=cap_rows, device=dev, inputs=[
            r, d["counts"], d["row_index"], d["row_U_y"],
            d["floor_y_rest"], d["q_s"], d["diag"], solver.c_world_anchor])
        self.last_n_iter_solves += 1

    def _substep_end_device(self, solver) -> None:
        """Device substep_end: EMA high-pass + eigen-IIR force of q_d, passivity
        log, and q = q_s + q_d sync — all on-device. Host readback happens only
        ONCE per macro-step (on the last substep) for the render/HUD."""
        import warp as wp
        from . import reduced_coupled_kernels as K
        if not self._device_ready or self._dev_n_b == 0:
            self._substep_index += 1
            return
        d = self._dbuf
        dev = solver.device
        r = int(self._dev_r)
        f64 = wp.float64
        # EMA high-pass + force q_d/q̇_d through the exact resonator.
        wp.launch(K.k_iir_apply, dim=r, device=dev, inputs=[
            r, d["Fq"], d["F_q_static_lp"], d["q_free"], d["qdot_free"],
            d["S_h_diag"], d["T_h_diag"], d["first_substep"],
            f64(self._dev_h_sub), f64(self._dev_tau),
            d["q_d"], d["qdot_d"], d["F_q_dyn"]])
        # Passivity log (per substep) + clear the first-substep EMA flag.
        wp.launch(K.k_passivity, dim=1, device=dev, inputs=[
            r, d["q_d"], d["qdot_d"], d["Mq"], d["Kq"], d["F_q_dyn"],
            d["escal"], f64(self._dev_h_sub), d["first_substep"],
            d["pass_counter"]])
        # q = q_s + q_d ; q̇ = q̇_d.
        wp.launch(K.k_sync_total, dim=r, device=dev, inputs=[
            r, d["q_s"], d["q_d"], d["qdot_d"], d["q_total"], d["qdot_total"]])

        # Once-per-macro-step host readback for render/HUD (the only host
        # round-trip; substep boundaries are otherwise device-only). Also when
        # log_substeps is on, sync every substep so the log is per-substep.
        is_last = (self._substep_index % self._dev_n_sub) == (
            self._dev_n_sub - 1)
        if is_last or self.log_substeps:
            self._sync_device_to_host(solver)
        self._substep_index += 1

    def _sync_device_to_host(self, solver) -> None:
        """Pull resident modal state + diagnostics to host and recompute the
        host-side logged scalars (norms, deflection, residual). Once per step."""
        d = self._dbuf
        self.rs.q_s = d["q_s"].numpy().astype(np.float64).copy()
        self.rs.q_d = d["q_d"].numpy().astype(np.float64).copy()
        self.rs.qdot_d = d["qdot_d"].numpy().astype(np.float64).copy()
        self.rs.F_q_static_lp = d["F_q_static_lp"].numpy().astype(
            np.float64).copy()
        self._last_F_q_contact = d["Fq"].numpy().astype(np.float64).copy()
        F_q_dyn = d["F_q_dyn"].numpy().astype(np.float64)
        self.rs.sync_total_from_split()
        diag = d["diag"].numpy()
        self.last_max_dx_norm = float(diag[0])
        self.last_max_dtheta_norm = float(diag[1])
        self.last_dq_norm = float(diag[2])
        self.last_passivity_violations = int(d["pass_counter"].numpy()[0])

        Mq, Kq, Dq = self.rs.Mq, self.rs.Kq, self.rs.Dq
        self.last_q_s_norm = float(np.linalg.norm(self.rs.q_s))
        self.last_q_d_norm = float(np.linalg.norm(self.rs.q_d))
        self.last_qdot_d_norm = float(np.linalg.norm(self.rs.qdot_d))
        self.last_F_q_total_norm = float(np.linalg.norm(self._last_F_q_contact))
        self.last_F_q_static_norm = float(np.linalg.norm(self.rs.F_q_static_lp))
        self.last_F_q_dyn_norm = float(np.linalg.norm(F_q_dyn))
        self.last_q_norm = float(np.linalg.norm(self.rs.q))
        self.last_qdot_norm = self.last_qdot_d_norm
        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, self.rs.q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
        self.last_modal_KE = 0.5 * float(self.rs.qdot_d @ (Mq @ self.rs.qdot_d))
        self.last_modal_PE = 0.5 * float(self.rs.q_d @ (Kq @ self.rs.q_d))
        self.last_damp_power = float(self.rs.qdot_d @ (Dq @ self.rs.qdot_d))
        rows = self.rs.tracked_row_indices
        if rows:
            lam = solver.c_lambda.numpy()
            self.last_contact_lambda_max = float(np.max(np.abs(lam[rows])))

    def substep_begin_hook(self, solver) -> None:
        """Static / dynamic split substep_begin (drift-fix v1).

        # DEVIATION (foundation §15, plan ~/.claude/plans/...fizzy-waffle):
        the anchor is seeded from `rs.q_s` (algebraic static-sag coord)
        instead of `q_hat = q_free` (oscillating IIR predictor). The IIR
        precompute runs on (q_d, qdot_d), not (q, qdot), and only sets up
        the q_d evolution that fires in substep_end. Removing the dynamic
        component from the contact anchor closes the position-level
        rectification loop that produced the +108 mm drift.
        """
        # Full GPU-resident path: all substep_begin work runs on-device (basis
        # eval, energy snapshot, eigen IIR precompute, anchor seed). The numpy
        # body below is the reference (CLAUDE.md rule 6); CPU / device_resident
        # off use it.
        if self._use_device(solver):
            self._substep_begin_device(solver)
            return

        # 1. Snapshot dynamic state for the passivity log + EMA wake-up.
        self.rs.q_d_prev_macro    = self.rs.q_d.copy()
        self.rs.qdot_d_prev_macro = self.rs.qdot_d.copy()

        # 2. q_d energy snapshot (q_s is quasi-static, no kinetic term).
        Mq_ = self.rs.Mq
        Kq_ = self.rs.Kq
        qd0 = self.rs.qdot_d
        qn0 = self.rs.q_d
        self._E_q_d_substep_begin = (
            0.5 * float(qd0 @ (Mq_ @ qd0))
          + 0.5 * float(qn0 @ (Kq_ @ qn0)))

        # 3. IIR precompute on (q_d, qdot_d). Same eigenbasis / dense
        # branching as the legacy IIR path, fed with the DYNAMIC state.
        if getattr(self.rs, "is_eigenbasis", False):
            mass_diag = np.diag(self.rs.Mq)
            (q_d_free, qdot_d_free, S_diag, T_diag
             ) = exact_modal_step_precompute(
                self.rs.q_d, self.rs.qdot_d,
                self.rs.eigen_omegas, self.rs.eigen_zetas,
                mass_diag, self.h_substep)
            S_h_inv_diag = 1.0 / S_diag
            S_h     = np.diag(S_diag)
            T_h     = np.diag(T_diag)
            S_h_inv = np.diag(S_h_inv_diag)
            self.last_min_S_h = float(S_diag.min())
            self.last_max_S_h = float(S_diag.max())
            self.S_h_diag     = S_diag
            self.S_h_inv_diag = S_h_inv_diag
            self.T_h_diag     = T_diag
        else:
            q_d_free, qdot_d_free, S_h, T_h = (
                dynamic_compliance_step_precompute(
                    self.rs.q_d, self.rs.qdot_d,
                    self.rs.Mq, self.rs.Kq, self.rs.Dq,
                    self.h_substep))
            S_h_inv = np.linalg.inv(S_h)
            diag_S = np.diag(S_h)
            self.last_min_S_h = float(diag_S.min())
            self.last_max_S_h = float(diag_S.max())
            self.S_h_diag     = None
            self.S_h_inv_diag = None
            self.T_h_diag     = None
        self.q_free    = q_d_free
        self.qdot_free = qdot_d_free
        self.S_h       = S_h
        self.T_h       = T_h
        self.S_h_inv   = S_h_inv
        # DO NOT overwrite rs.q_d with q_d_free — q_d stays at its prev
        # value during the iteration loop, and is committed in
        # _substep_end_split using the converged F_q_dyn.

        # Allocate the F_q_contact accumulator (one-shot at first use).
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

        # 7. Seed anchors using q_s ONLY. No q_free, no q_d, no v_lift.
        anchor_new = anchor_np.copy()
        dy_all = self._U_y_stack @ self.rs.q_s
        anchor_new[self._tracked_rows_arr, 1] = (
            self._floor_y_rest_arr + dy_all)
        solver.c_world_anchor.assign(anchor_new.astype(np.float32))

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
        r = self.rs.r
        Kq = self.rs.Kq

        # Baseline H_{q_s} / g_{q_s} — algebraic (no IIR predictor).
        # At convergence: K_q · q_s = Σ U_y · f  (the modal equilibrium
        # under the contact load).
        H_q = Kq.copy()
        g_q = Kq @ self.rs.q_s

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
            k_j_lin    = k_col * j_lin_arr
            k_j_ang    = k_col * j_ang_arr
            k_U_y      = k_col * U_y_arr

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

            # Modal-side contributions to g_{q_s} and H_{q_s}.
            #   g_{q_s} -= U_y · f          (J_{q_s}^T · f gradient)
            #   H_{q_s} += ρ · U_y U_y^T    (AL Hessian)
            g_q = g_q - U_y_arr.T @ f_arr
            H_q = H_q + U_y_arr.T @ k_U_y

            # Accumulate Σ U_y · f for the substep-end F_q_total.
            # This is the modal-frame projection of the actual contact
            # force at the current iteration's state; the LAST iteration
            # writes the value `_substep_end_split` reads.
            self._last_F_q_contact += U_y_arr.T @ f_arr

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

        # Apply Δq_s and back-substitute for body deltas.
        q_s_new = self.rs.q_s + dq
        self.rs.q_s = q_s_new

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

        # Refresh anchors with q_s_new — NO v_lift term in split mode.
        anchor_out = anchor_np.copy()
        dy_all = self._U_y_stack @ q_s_new
        anchor_out[self._tracked_rows_arr, 1] = (
            self._floor_y_rest_arr + dy_all)
        solver.c_world_anchor.assign(anchor_out.astype(np.float32))

        self.last_max_dx_norm = max_dx
        self.last_max_dtheta_norm = max_dtheta
        self.last_dq_norm = float(np.linalg.norm(dq))
        self.last_n_iter_solves += 1
        self.last_iter_dq_norms.append(self.last_dq_norm)
        self.last_rho_clip_hits = rho_hits

    def substep_end_hook(self, solver) -> None:
        """Apply the high-passed modal load to q_d, sync `rs.q` for
        back-compat, log passivity (drift-fix v1).

        # DEVIATION (foundation §15, plan ~/.claude/plans/...fizzy-waffle):
        the implied force in the legacy IIR commit was
            F_implied = S_h^{-1}·(q_solved − q_free)
        which converts AVBD's per-iteration q residual into a modal velocity
        kick via T_h. That route makes q_d non-passive whenever the AL hasn't
        fully converged. Here we replace the implied F with the FILTERED
        actual contact load:
            F_q_dyn = F_q_total − F_q_static_lp
        where F_q_total = Σ U_y · f was accumulated during the final
        iteration of `_iteration_split` and F_q_static_lp is the EMA
        low-pass thereof. The static component flows through q_s (algebraic,
        already absorbed into the anchor each iter); only the high-passed
        residue forces q_d. Resting load → F_q_dyn = 0 → q_d homogeneous,
        decays through Rayleigh damping. Impact transient → F_q_dyn ≠ 0
        briefly → q_d rings.
        """
        # Full GPU-resident path: EMA + eigen-IIR q_d step + passivity + sync
        # all run on-device; host readback is once per macro-step (render/HUD).
        # The numpy body below is the reference (CLAUDE.md rule 6).
        if self._use_device(solver):
            self.last_n_iter_solves = int(solver.iterations) + (
                1 if getattr(solver, "post_stabilize", False) else 0)
            self._substep_end_device(solver)
            return

        h = float(self.h_substep)
        Mq = self.rs.Mq
        Kq = self.rs.Kq

        # F_q_total = Σ U_y · f as accumulated in the FINAL iteration of
        # _iteration_split. Defensive: if no rows were tracked or the
        # accumulator was never sized, treat as zero.
        if self._last_F_q_contact is None:
            F_q_total = np.zeros(self.rs.r, dtype=np.float64)
        else:
            F_q_total = self._last_F_q_contact.copy()

        # EMA update of F_q_static_lp. Frame-rate-aware α; one-shot
        # init (α=1) on the very first substep so the LP latches to
        # F_q_total instead of starting at zero (which would dump the
        # static load into q_d and produce a spurious wake-up ring).
        tau = float(self.modal_static_lp_tau)
        if getattr(self, "_first_substep_split", True):
            alpha_ema = 1.0
            self._first_substep_split = False
        else:
            alpha_ema = 1.0 - float(np.exp(-h / max(tau, 1e-9)))
        self.rs.F_q_static_lp = (
            (1.0 - alpha_ema) * self.rs.F_q_static_lp
          + alpha_ema * F_q_total)
        F_q_dyn = F_q_total - self.rs.F_q_static_lp

        # Apply F_q_dyn through the IIR precompute prepared at substep_begin.
        # q_d_new   = q_d_free   + S_h · F_q_dyn
        # qdot_d_new = qdot_d_free + T_h · F_q_dyn
        if (self.q_free is not None and self.qdot_free is not None
                and self.S_h is not None and self.T_h is not None):
            if self.S_h_diag is not None:
                q_d_new    = self.q_free    + self.S_h_diag * F_q_dyn
                qdot_d_new = self.qdot_free + self.T_h_diag * F_q_dyn
            else:
                q_d_new    = self.q_free    + self.S_h @ F_q_dyn
                qdot_d_new = self.qdot_free + self.T_h @ F_q_dyn
            self.rs.q_d    = q_d_new
            self.rs.qdot_d = qdot_d_new
        else:
            # Pre-warm fallback (first substep before any precompute).
            self.rs.q_d[:]    = 0.0
            self.rs.qdot_d[:] = 0.0

        # Passivity log — does q_d energy change exceed the work upper
        # bound h · F_q_dyn^T · qdot_d? Logged, NOT enforced (the
        # passivity bound is asymptotic; iteration-noise can briefly
        # violate it without affecting long-run stability).
        dE_q_d = ((0.5 * float(self.rs.qdot_d @ (Mq @ self.rs.qdot_d))
                 + 0.5 * float(self.rs.q_d   @ (Kq @ self.rs.q_d)))
                 - self._E_q_d_substep_begin)
        W_q_d_bound = abs(h * float(F_q_dyn @ self.rs.qdot_d))
        if dE_q_d > W_q_d_bound + 1e-12:
            self.last_passivity_violations += 1

        # Sync the canonical (q, qdot) views for downstream callers
        # (viser surface render, HUD readouts, the last_max_support_deflection
        # diagnostic). In split mode, q_s and q_d are the truth.
        self.rs.sync_total_from_split()

        # Diagnostics.
        self.last_q_s_norm        = float(np.linalg.norm(self.rs.q_s))
        self.last_q_d_norm        = float(np.linalg.norm(self.rs.q_d))
        self.last_qdot_d_norm     = float(np.linalg.norm(self.rs.qdot_d))
        self.last_F_q_total_norm  = float(np.linalg.norm(F_q_total))
        self.last_F_q_static_norm = float(np.linalg.norm(self.rs.F_q_static_lp))
        self.last_F_q_dyn_norm    = float(np.linalg.norm(F_q_dyn))
        self.last_q_norm    = float(np.linalg.norm(self.rs.q))
        self.last_qdot_norm = self.last_qdot_d_norm

        # max_support_deflection on the full visual q (q_s + q_d).
        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, self.rs.q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
        else:
            self.last_max_support_deflection = 0.0

        # Modal energy diagnostics — on q_d only (q_s has no kinetic).
        self.last_modal_KE = 0.5 * float(
            self.rs.qdot_d @ (Mq @ self.rs.qdot_d))
        self.last_modal_PE = 0.5 * float(
            self.rs.q_d @ (Kq @ self.rs.q_d))
        self.last_damp_power = float(
            self.rs.qdot_d @ (self.rs.Dq @ self.rs.qdot_d))
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
                "P_damp_W":      self.last_damp_power,
                "contact_lambda_max": self.last_contact_lambda_max,
                "max_support_deflection_m": self.last_max_support_deflection,
                "n_iter_solves": int(self.last_n_iter_solves),
                # split-mode extras
                "q_s_norm":      self.last_q_s_norm,
                "q_d_norm":      self.last_q_d_norm,
                "F_q_total_norm":  self.last_F_q_total_norm,
                "F_q_static_norm": self.last_F_q_static_norm,
                "F_q_dyn_norm":    self.last_F_q_dyn_norm,
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



