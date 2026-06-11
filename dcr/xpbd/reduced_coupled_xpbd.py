"""Reduced-Coordinate Coupled XPBD — Python-side monolithic primal coupler.

The XPBD sibling of `dcr.avbd.reduced_coupled_avbd.ReducedCoupledAVBDCoupler`.
Same constraint formulation (proposal §2.1, `docs/proposal_modal_response_as_constraint.md`):
the modal amplitude `q` is a constrained co-DOF carrying its own column
`J_q = −Φ(x_s)` in the contact gap, and the same multiplier that satisfies
non-penetration loads the modal coordinate through `J_q`. The math is the
same; only the host solver and the per-iteration stiffness mapping change.

Math (one tracked corner contact at row j on body b):

  g_j(z_b, q_s) = corner_y(z_b) − (support_y_rest + U_y(corner_j) · q_s) − δ_shell
  J_x,j  = [n; r×n]                     (rigid Jacobian; n = +y)
  J_q,j  = −U_y(corner_j)               (modal Jacobian — the new object)

The monolithic primal Newton block over all tracked bodies + the shared `q_s`:

  [ H_x,1                       ρ·J_x,1·J_q,1^T ] [Δx_1]   [ -g_x,1 ]
  [         H_x,2               ρ·J_x,2·J_q,2^T ] [Δx_2] = [ -g_x,2 ]
  [               ⋱                  ⋮          ] [ ⋮  ]   [   ⋮    ]
  [ ρ·J_q,1·J_x,1^T  …          H_q              ] [ Δq ]   [  -g_q  ]

Schur-eliminate the per-body 6×6 blocks; solve r×r for Δq_s; back-substitute Δx.

# DEVIATION (XPBD-vs-AVBD penalty source): AVBD's `ρ` is the augmented-
# Lagrangian penalty (escalates over iterations toward PENALTY_MAX = 1e9).
# XPBD's effective stiffness is `1/(α + h²/W)` per constraint — for HARD
# contact (`α = 0`) it equals `1/(h²/W) = W/h²` where `W = J·M⁻¹·J^T`.
# Here we use a fixed `contact_stiffness` matching AVBD's ACTUAL escalated
# `ρ` (~1e6 in these scenes), NOT its 1e9 clip — see the field docstring:
# matching the clip over-stiffens and kills the static-sag coupling. XPBD's
# per-substep λ reset is automatic (no augmented Lagrangian carries across
# iterations).

# DEVIATION (foundation §15, drift-fix v1): inherits AVBD's static/dynamic
# split. `q = q_s + q_d`. Only `q_s` enters the contact gap; `q_d` is the
# render-only dynamic ring, advanced once per substep through the exact
# damped-oscillator step (DCR paper Eq. 7–8) forced by the high-passed
# `F_q_dyn = F_q_total − F_q_static_lp`. See the AVBD coupler's module
# docstring for the full reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..avbd.reduced_support import ReducedSupport, evaluate_basis_at_point
from ..avbd.reduced_support_solve import _quat_rotate_xyzw
from ..modal.exact_resonator import (
    dynamic_compliance_step_precompute,
    exact_modal_step_precompute,
)


def _quat_xyzw_to_R(q_xyzw: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotation matrix from (x, y, z, w) quaternion."""
    qx, qy, qz, qw = (float(q_xyzw[0]), float(q_xyzw[1]),
                      float(q_xyzw[2]), float(q_xyzw[3]))
    xx = qx * qx; yy = qy * qy; zz = qz * qz
    xy = qx * qy; xz = qx * qz; yz = qy * qz
    wx = qw * qx; wy = qw * qy; wz = qw * qz
    return np.array([
        [1.0 - 2.0 * (yy + zz),       2.0 * (xy - wz),       2.0 * (xz + wy)],
        [      2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz),       2.0 * (yz - wx)],
        [      2.0 * (xz - wy),       2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ], dtype=np.float64)


def _quat_xyzw_from_rotvec(rv: NDArray[np.float64]) -> NDArray[np.float64]:
    """Half-angle quat exp: q = (sin(θ/2)·n̂, cos(θ/2)). Matches the XPBD
    `quat_integrate` convention up to sign."""
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


def _geom_stiffness_diag_batch(n: NDArray[np.float64],
                               r: NDArray[np.float64]) -> NDArray[np.float64]:
    """AVBD Eq. 17 column-norm geometric-stiffness diagonal, batched. Same
    formula as `dcr.avbd.reduced_coupled_avbd._geom_stiffness_diag_batch`."""
    n_dot_r = r @ n   # (n_rows,)
    out = np.empty_like(r)
    for c in range(3):
        col = np.empty_like(r)
        for i_ in range(3):
            if i_ == c:
                col[:, i_] = n[i_] * r[:, c] - n_dot_r
            else:
                col[:, i_] = 0.5 * (n[i_] * r[:, c] + r[:, i_] * n[c])
        out[:, c] = np.linalg.norm(col, axis=1)
    return out


# Box-corner offsets in body frame (sign pattern matches xpbd3d kernels_6dof.box_corner).
_BOX_CORNER_SIGNS = np.array([
    [-1, -1, -1],
    [ 1, -1, -1],
    [-1,  1, -1],
    [ 1,  1, -1],
    [-1, -1,  1],
    [ 1, -1,  1],
    [-1,  1,  1],
    [ 1,  1,  1],
], dtype=np.float64)


@dataclass
class ReducedCoupledXPBDCoupler:
    """Monolithic Python-side coupled primal coupler for the XPBD 6-DOF
    rigid solver + reduced deformable support. See module docstring.

    Lifecycle per substep:
      substep_begin_hook  — re-identify active per-corner contact rows for
                            the tracked bodies, cache `U_y` at each row's
                            current corner (x, z), seed contact anchors via
                            the static-sag `q_s` (low-passed).
      iteration_hook(it)  — assemble the per-body Hessian + cross-coupling
                            block, Schur-reduce to an r×r solve for Δq_s,
                            back-substitute Δx_b. Applied AFTER XPBD's own
                            constraint sweep so the update warm-starts the
                            next iteration.
      substep_end_hook    — EMA high-pass on the accumulated `F_q_total`,
                            exact-resonator step on `(q_d, q̇_d)`, then
                            sync `rs.q = q_s + q_d` for downstream readers.

    The XPBD-vs-AVBD differences are confined to:
      * `contact_stiffness` is a fixed scalar (XPBD has no AL escalation).
      * The body's "inertial frame" is snapshotted from `solver.x / solver.q`
        at substep_begin (which is post-`integrate_bodies`), playing the
        same role as AVBD's `x_inertial / q_inertial`.
      * There is no per-row dual `λ_eff` carried into the iteration — XPBD's
        per-substep `λ` reset means the AL dual term vanishes.
    """

    rs: ReducedSupport

    # Body indices (into the XPBD solver) that rest on the deformable shelf.
    tracked_body_indices: list[int]

    # Shelf metadata (the bilinear-interp grid for U at arbitrary corner xz).
    shelf_length: float
    shelf_width: float
    shelf_y_rest: float
    n_grid_x: int
    n_grid_z: int

    h_substep: float = 1.0 / 60.0
    h_macro:   float = 1.0 / 60.0

    # Active-contact margin: a corner counts as in contact if its y is within
    # `contact_active_margin` of the deformable surface y at substep-begin.
    # Must comfortably exceed one substep's gravity drop (½·g·h² ≈ 0.34 mm at
    # h=1/240 s) PLUS the body's swept motion this substep, otherwise corners
    # about to LAND in the upcoming substep aren't tracked and the impact
    # transient never sources the modal ring. 2 mm is a generous default;
    # AVBD's broad phase emits floor rows by AABB overlap so it doesn't have
    # an equivalent knob to compare against.
    contact_active_margin: float = 2.0e-3

    # EMA time constant (s) for the high-pass driving q_d. Mirrors AVBD.
    modal_static_lp_tau: float = 0.05

    # Constant effective stiffness per active contact row, replacing AVBD's
    # AL `ρ`. XPBD-natively `α → 0` is the hard-contact limit (≈ 1e9).
    #
    # FIX (verified 2026-06-10): the old default 1e8 (set to "match AVBD's
    # rho_clip = 1e9") killed the static-sag coupling. AVBD's `ρ` ESCALATES
    # but in these scenes only reaches ~1e6 — it never approaches the 1e9
    # clip. The Schur regulariser below scales as `eps_cross_factor·ρ²/m`, so
    # a fixed ρ=1e8 makes ε ≈ 1e10, which SWAMPS the true Schur scale (~K_q ~
    # 1e4–1e7) and divides Δq_s by ~1e10 → `q_s` collapses to ~1e-8 (measured
    # ‖q_s‖_rest = 1.25e-8, vs analytic static sag 1.84e-3 — coupling dead).
    # Matching AVBD's ACTUAL escalated ρ (~1e6, NOT its clip) puts ε back in
    # line with the Schur scale: ‖q_s‖_rest = 1.30e-3 = 0.71× analytic,
    # IDENTICAL to AVBD's 0.71×. Validated stable + finite across all four
    # scenes (dinner/truck/shelf/ledge) with body rest positions unchanged.
    # See docs/proposal_modal_response_as_constraint.md §3.3.
    contact_stiffness: float = 1.0e6

    # Solver regulariser auto-scaled inside iteration_hook so that
    #   ε = max(eps_baseline · trace(K_q)/r,
    #           eps_cross_factor · max_b ρ²·||J_x,b||²/m_b)
    # keeps the Schur matrix well-conditioned. Same recipe as AVBD.
    eps_baseline: float = 1.0e-8
    eps_cross_factor: float = 1.0e-6

    # When True, populate `last_Schur_condition_estimate` per iteration.
    diagnostic_mode: bool = False

    # Contact-anchor static low-pass (proposal §3.1 — rock/slide/spin fix).
    # Routes only the LOW-PASSED static-sag component of `q_s` into the
    # contact reference, so an impact spike in q_s does not jump the surface
    # under a body and kick it. Reuses `modal_static_lp_tau`. The anchor is
    # also held fixed across iterations within a substep (staggered/G-S
    # update), removing the rocking limit cycle for cantilever supports.
    anchor_static_lowpass: bool = True
    _q_s_anchor_lp: NDArray[np.float64] | None = None

    # Whether the contact anchor tracks the dynamic ring q_d in addition to the
    # static sag q_s. False (default) ⇒ anchor on q_s ONLY, exactly like the
    # AVBD coupler: bodies rest on the static-sag surface and the q_d ring is
    # render-only, so resting bodies stay still. True ⇒ anchor on q_s + q_d so
    # bodies visibly ride the ringing surface (the original demo behavior; it
    # makes the coupling vivid but couples every resting body to the modal ring,
    # which reads as "everything vibrates"). See substep_begin_hook.
    anchor_includes_q_d: bool = False

    # ---- IIR exact-resonator workspace ----
    q_free:      NDArray[np.float64] | None = None
    qdot_free:   NDArray[np.float64] | None = None
    S_h:         NDArray[np.float64] | None = None
    T_h:         NDArray[np.float64] | None = None
    S_h_inv:     NDArray[np.float64] | None = None
    S_h_diag:     NDArray[np.float64] | None = None
    S_h_inv_diag: NDArray[np.float64] | None = None
    T_h_diag:     NDArray[np.float64] | None = None

    # ---- Substep logging ----
    log_substeps: bool = False
    substep_log: list[dict] = field(default_factory=list)
    _substep_index: int = 0

    # ---- Per-substep caches (rebuilt in substep_begin_hook) ----
    # Snapshot of the post-`integrate_bodies` predictor state — plays the
    # role of AVBD's x_inertial / q_inertial.
    _x_predicted: NDArray[np.float64] | None = None
    _q_predicted: NDArray[np.float64] | None = None
    _mass_np:    NDArray[np.float64] | None = None
    _invI_local_np: NDArray[np.float64] | None = None
    _he_np:      NDArray[np.float64] | None = None
    # Per-tracked-row caches.
    _U_at_row: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_body: dict[int, int] = field(default_factory=dict)
    _row_off:  dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_rest_y: dict[int, float] = field(default_factory=dict)
    _row_anchor_y: dict[int, float] = field(default_factory=dict)
    _rows_per_body: dict[int, list[int]] = field(default_factory=dict)
    # Per-body batched arrays for vectorised assembly.
    _row_idx_by_body: dict[int, NDArray[np.int64]] = field(default_factory=dict)
    _row_off_by_body: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_U_y_by_body: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _row_anchor_by_body: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    # Flat tracked-row arrays for downstream diagnostics.
    _tracked_rows_arr:   NDArray[np.int64]   | None = None
    _U_y_stack:          NDArray[np.float64] | None = None
    _floor_y_rest_arr:   NDArray[np.float64] | None = None

    # ---- Static/dynamic split accumulators ----
    _last_F_q_contact: NDArray[np.float64] | None = None
    _E_q_d_substep_begin: float = 0.0
    _first_substep_split: bool = True
    # Short-tau EMA of F_q_total to kill the substep-frequency BOUNCE noise.
    # XPBD's position-based contact derives velocity from `(x − x_prev)/h`,
    # which makes the catching body bounce slightly each substep. The
    # bounce leaks into the per-substep f_body_y as a square-wave signal
    # at the substep rate (~240 Hz). This EMA (tau ≈ 4–8 substeps) low-
    # passes the contact-force signal at a frequency above any structural
    # mode the modal basis can represent, so genuine impact transients
    # (~10 ms) pass through unaffected. AVBD doesn't need this because its
    # AL dual converges within the substep to the true contact force.
    _F_q_total_smooth: NDArray[np.float64] | None = None

    # Per-active-row AL dual accumulator. XPBD has no augmented Lagrangian.
    # For the monolithic Schur primal the dual update would be a no-op (the
    # Schur drives C → 0 in one iter, leaving the AL ascent nothing to
    # absorb), so we DON'T grow λ_eff here — the contact force is recovered
    # post-Δx from the body's momentum deficit relative to the predictor.
    # The dict is retained for any future hybrid scheme.
    _lambda_per_row: dict[int, float] = field(default_factory=dict)

    # ---- Diagnostics (mirrors the AVBD coupler's surface) ----
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
    last_modal_KE: float = 0.0
    last_modal_PE: float = 0.0
    last_damp_power: float = 0.0
    last_q_s_norm:        float = 0.0
    last_q_d_norm:        float = 0.0
    last_qdot_d_norm:     float = 0.0
    last_F_q_total_norm:  float = 0.0
    last_F_q_static_norm: float = 0.0
    last_F_q_dyn_norm:    float = 0.0
    last_passivity_violations: int = 0
    last_min_S_h: float = 0.0
    last_max_S_h: float = 0.0

    # ---- GPU device residency (mirrors the AVBD coupler) -------------------
    # When True AND the solver is on CUDA AND the basis is eigen, the three
    # hooks run fully on-device (see reduced_coupled_xpbd_kernels). Topology is
    # uploaded once; the only host round-trip is one readback per macro-step
    # (post_step_hook) for the render/HUD. The numpy path above stays the
    # parity reference (CLAUDE.md rule 6) and runs on CPU or when disabled.
    device_resident: bool = True
    _device_ready: bool = False
    _dbuf: dict = field(default_factory=dict)
    _k_eps_tiled: object = None
    _eps_block_dim: int = 32
    _dev_n_b: int = 0

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------
    def substep_begin_hook(self, solver) -> None:
        """Snapshot the post-predictor body state, run the IIR precompute on
        the dynamic ring `(q_d, q̇_d)`, identify active contact corners on
        each tracked body, cache `U_y` per row, low-pass `q_s` into the
        contact reference. Mirrors `ReducedCoupledAVBDCoupler.substep_begin_hook`.
        """
        if self._use_device(solver):
            self._substep_begin_device(solver)
            return
        # 1. Snapshot dynamic state for the passivity log.
        self.rs.q_d_prev_macro    = self.rs.q_d.copy()
        self.rs.qdot_d_prev_macro = self.rs.qdot_d.copy()
        Mq_ = self.rs.Mq
        Kq_ = self.rs.Kq
        self._E_q_d_substep_begin = (
            0.5 * float(self.rs.qdot_d @ (Mq_ @ self.rs.qdot_d))
          + 0.5 * float(self.rs.q_d   @ (Kq_ @ self.rs.q_d)))

        # 2. IIR precompute on (q_d, qdot_d).
        if getattr(self.rs, "is_eigenbasis", False):
            mass_diag = np.diag(self.rs.Mq)
            (q_d_free, qdot_d_free, S_diag, T_diag
             ) = exact_modal_step_precompute(
                self.rs.q_d, self.rs.qdot_d,
                self.rs.eigen_omegas, self.rs.eigen_zetas,
                mass_diag, self.h_substep)
            S_h_inv_diag = 1.0 / S_diag
            self.S_h     = np.diag(S_diag)
            self.T_h     = np.diag(T_diag)
            self.S_h_inv = np.diag(S_h_inv_diag)
            self.S_h_diag     = S_diag
            self.S_h_inv_diag = S_h_inv_diag
            self.T_h_diag     = T_diag
            self.last_min_S_h = float(S_diag.min())
            self.last_max_S_h = float(S_diag.max())
        else:
            (q_d_free, qdot_d_free, S_h, T_h
             ) = dynamic_compliance_step_precompute(
                self.rs.q_d, self.rs.qdot_d,
                self.rs.Mq, self.rs.Kq, self.rs.Dq,
                self.h_substep)
            self.S_h     = S_h
            self.T_h     = T_h
            self.S_h_inv = np.linalg.inv(S_h)
            self.S_h_diag = self.S_h_inv_diag = self.T_h_diag = None
            diag_S = np.diag(S_h)
            self.last_min_S_h = float(diag_S.min())
            self.last_max_S_h = float(diag_S.max())
        self.q_free    = q_d_free
        self.qdot_free = qdot_d_free

        r = self.rs.r
        if (self._last_F_q_contact is None
                or self._last_F_q_contact.shape[0] != r):
            self._last_F_q_contact = np.zeros(r, dtype=np.float64)

        # 3. Snapshot the body state. XPBD ran `integrate_bodies` immediately
        # before this hook, so `solver.x / solver.q` are the inertial
        # predictor — exactly what AVBD calls x_inertial / q_inertial.
        self._x_predicted = solver.x.numpy().astype(np.float64).copy()
        self._q_predicted = solver.q.numpy().astype(np.float64).copy()
        self._mass_np    = np.where(
            solver.inv_mass.numpy() > 0.0,
            1.0 / np.maximum(solver.inv_mass.numpy(), 1.0e-30),
            0.0,
        ).astype(np.float64)
        # Body-frame diagonal inertia (inverse of `inv_I`).
        invI = solver.inv_I.numpy().astype(np.float64)
        I_body_diag = np.where(invI > 0.0, 1.0 / np.maximum(invI, 1.0e-30), 0.0)
        self._invI_local_np = invI
        self._I_local_np = I_body_diag
        self._he_np = solver.he.numpy().astype(np.float64)

        # 4. Identify active contact rows. One "row" per (body, corner) where
        # the world corner-y sits within `contact_active_margin` of the
        # deformable surface y = shelf_y_rest + U_y(corner_xz) · q_s.
        self._U_at_row.clear()
        self._row_body.clear()
        self._row_off.clear()
        self._row_rest_y.clear()
        self._row_anchor_y.clear()
        self._rows_per_body.clear()
        self._row_idx_by_body.clear()
        self._row_off_by_body.clear()
        self._row_U_y_by_body.clear()
        self._row_anchor_by_body.clear()

        # Anchor reference uses the FULL modal coordinate `q = q_s + q_d`
        # (not just the static-sag q_s). Rationale: with K_q ≈ 1e12 in the
        # synthetic shelf basis, q_s is in the 1e-7 range under realistic
        # loads — invisible — and bodies stay perfectly still even when the
        # render-only q_d is ringing the shelf surface by mm. Including q_d
        # in the anchor means the contact constraint TRACKS the visible
        # deformation, so the bodies bounce/tilt as the shelf bends.
        # # DEVIATION (foundation §15): this breaks the static/dynamic
        # split's drift-prevention property (the split was added so q_d
        # ringing doesn't rectify into +∞ probe drift via the one-sided
        # constraint). For demo scenes where you SEE the response, the
        # coupling visibility outweighs the drift risk; for production /
        # long-run simulations, revert to q_s-only.
        # AVBD-parity default: anchor on q_s only (q_d ring stays render-only).
        if self.anchor_includes_q_d:
            q_total = self.rs.q_s + self.rs.q_d
        else:
            q_total = self.rs.q_s.copy()
        lp_tau = self.modal_static_lp_tau if self.anchor_static_lowpass else 0.0
        if lp_tau > 0.0:
            if (self._q_s_anchor_lp is None
                    or self._q_s_anchor_lp.shape[0] != r):
                self._q_s_anchor_lp = q_total.copy()
            a_lp = min(1.0, float(self.h_substep) / lp_tau)
            self._q_s_anchor_lp += a_lp * (q_total - self._q_s_anchor_lp)
            q_s_anchor = self._q_s_anchor_lp
        else:
            q_s_anchor = q_total

        # Synthesise per-corner rows. Row index is a coupler-private id —
        # unlike AVBD's solver._rows, XPBD has no per-row scratch.
        tracked: list[int] = []
        row_id = 0
        for body_idx in self.tracked_body_indices:
            if self._mass_np[body_idx] <= 0.0:
                continue
            x_b = self._x_predicted[body_idx]
            q_b = self._q_predicted[body_idx]
            R = _quat_xyzw_to_R(q_b)
            he = self._he_np[body_idx]
            for c in range(8):
                off = _BOX_CORNER_SIGNS[c] * he
                corner_w = x_b + R @ off
                # U_y at this corner's (x, z), and the current anchor y.
                U_pt = evaluate_basis_at_point(
                    self.rs,
                    (float(corner_w[0]), float(corner_w[2])),
                    length=self.shelf_length,
                    width=self.shelf_width,
                    n_grid_x=self.n_grid_x,
                    n_grid_z=self.n_grid_z,
                )
                U_y = U_pt[1]
                anchor_y = self.shelf_y_rest + float(U_y @ q_s_anchor)
                gap = float(corner_w[1]) - anchor_y
                if gap > self.contact_active_margin:
                    continue
                self._row_body[row_id]   = body_idx
                self._row_off[row_id]    = off.copy()
                self._row_rest_y[row_id] = self.shelf_y_rest
                self._row_anchor_y[row_id] = anchor_y
                self._U_at_row[row_id]   = U_pt
                self._rows_per_body.setdefault(body_idx, []).append(row_id)
                tracked.append(row_id)
                row_id += 1

        self.rs.tracked_row_indices = tracked
        self.last_n_tracked_rows = len(tracked)
        self.last_n_iter_solves = 0
        # Reset AL dual per active row (no warm-start across substeps).
        self._lambda_per_row = {row_id: 0.0 for row_id in tracked}

        # Per-body batched stacks for the iteration_hook hot loop.
        for body_idx, rows_on_body in self._rows_per_body.items():
            self._row_idx_by_body[body_idx] = np.asarray(
                rows_on_body, dtype=np.int64)
            self._row_off_by_body[body_idx] = np.stack(
                [self._row_off[i] for i in rows_on_body], axis=0)
            self._row_U_y_by_body[body_idx] = np.stack(
                [self._U_at_row[i][1] for i in rows_on_body], axis=0)
            self._row_anchor_by_body[body_idx] = np.asarray(
                [self._row_anchor_y[i] for i in rows_on_body],
                dtype=np.float64)

        if tracked:
            self._tracked_rows_arr = np.asarray(tracked, dtype=np.int64)
            self._U_y_stack = np.stack(
                [self._U_at_row[i][1] for i in tracked], axis=0)
            self._floor_y_rest_arr = np.fromiter(
                (self._row_rest_y[i] for i in tracked),
                dtype=np.float64, count=len(tracked))

    def iteration_hook(self, solver, iter_idx: int) -> None:
        """One coupled Schur step over the rigid bodies + static-sag `q_s`.

        Builds the same monolithic block as `ReducedCoupledAVBDCoupler.iteration_hook`
        with `ρ ← contact_stiffness` (XPBD has no AL escalation), Schur-
        eliminates the per-body 6×6 blocks (each rank-6 dense), solves r×r
        for Δq_s, back-substitutes Δx_b and applies in place to `solver.x`
        / `solver.q` and to `rs.q_s`.
        """
        if self._use_device(solver):
            self._iteration_device(solver, iter_idx)
            return
        rows = self.rs.tracked_row_indices
        if not rows:
            return

        x_curr_all = solver.x.numpy().astype(np.float64).copy()
        q_curr_all = solver.q.numpy().astype(np.float64).copy()

        h = float(self.h_substep)
        inv_dt2 = 1.0 / (h * h)
        r = self.rs.r
        Kq = self.rs.Kq
        rho = float(self.contact_stiffness)

        # Baseline H_{q_s} / g_{q_s} — algebraic (no IIR predictor).
        H_q = Kq.copy()
        g_q = Kq @ self.rs.q_s

        # F_q_total accumulator: reset only the FIRST time around. The
        # actual per-iter rewrite is in the post-assign block (after the
        # dual update); only that one feeds substep_end.
        if (self._last_F_q_contact is None
                or self._last_F_q_contact.shape[0] != r):
            self._last_F_q_contact = np.zeros(r, dtype=np.float64)

        per_body_Hx_inv: dict[int, NDArray[np.float64]] = {}
        per_body_gx:     dict[int, NDArray[np.float64]] = {}
        per_body_cross:  dict[int, NDArray[np.float64]] = {}

        max_rho2_over_m = 0.0

        n_hat_const = np.array([0.0, 1.0, 0.0], dtype=np.float64)

        for body_idx, rows_on_body in self._rows_per_body.items():
            m = float(self._mass_np[body_idx])
            if m <= 0.0 or not np.isfinite(m):
                continue
            q_xyzw = q_curr_all[body_idx]
            x_curr = x_curr_all[body_idx]
            x_iner = self._x_predicted[body_idx]
            q_iner = self._q_predicted[body_idx]

            R = _quat_xyzw_to_R(q_xyzw)
            I_local_diag = self._I_local_np[body_idx]
            # World-frame inertia: R · diag(I_local) · R^T.
            I_world = R @ np.diag(I_local_diag) @ R.T

            # Kinetic prior — pulls the body back to the post-predictor state.
            A = m * inv_dt2 * np.eye(3)
            D = I_world * inv_dt2
            B = np.zeros((3, 3), dtype=np.float64)

            r_lin = m * inv_dt2 * (x_curr - x_iner)
            # Orientation kinetic-prior residual: dq = q_curr · q_iner⁻¹,
            # converted to rotvec.
            q_iner_inv = np.array([-q_iner[0], -q_iner[1], -q_iner[2], q_iner[3]],
                                  dtype=np.float64)
            n2 = float(q_iner @ q_iner)
            if n2 > 1e-30:
                q_iner_inv = q_iner_inv / n2
            dq_iner = _quat_xyzw_mul(q_xyzw, q_iner_inv)
            s_norm = float(np.linalg.norm(dq_iner[:3]))
            if s_norm < 1e-12:
                dtheta_iner = np.zeros(3, dtype=np.float64)
            else:
                w = float(np.clip(dq_iner[3], -1.0, 1.0))
                theta = 2.0 * np.arctan2(s_norm, w)
                dtheta_iner = dq_iner[:3] * (theta / s_norm)
            r_ang = I_world @ (dtheta_iner * inv_dt2)

            cross_body = np.zeros((6, r), dtype=np.float64)

            row_idx_arr = self._row_idx_by_body[body_idx]
            off_arr     = self._row_off_by_body[body_idx]
            U_y_arr     = self._row_U_y_by_body[body_idx]
            anchor_arr  = self._row_anchor_by_body[body_idx]
            n_rows_b    = row_idx_arr.shape[0]

            # Jacobians per row: J_x = [n; r×n], J_q = -U_y.
            r_self_w_arr = off_arr @ R.T   # body-frame off rotated to world
            j_lin_arr = np.broadcast_to(n_hat_const, (n_rows_b, 3))
            j_ang_arr = np.empty((n_rows_b, 3), dtype=np.float64)
            j_ang_arr[:, 0] = -r_self_w_arr[:, 2]
            j_ang_arr[:, 1] = 0.0
            j_ang_arr[:, 2] =  r_self_w_arr[:, 0]

            # Contact gap (AVBD convention: C = corner_y − anchor_y, so
            # C > 0 = separated, C < 0 = penetrating). Anchor is frozen at
            # the substep-begin value (staggered/G-S refresh — see
            # `anchor_static_lowpass` notes).
            C_arr = (x_curr[1] + r_self_w_arr[:, 1] - anchor_arr)
            # Penalty force per row. Clamped to ≤ 0 for floor contact.
            # The "phantom dual" λ_eff is the body's gravity weight
            # distributed across active rows — this stands in for the AL
            # dual ascent that AVBD has but XPBD doesn't. Without it the
            # modal-side `g_q -= U_y·f` collapses to 0 at convergence
            # (Schur drives C → 0), so the modal block sees no static load
            # and q_s ≈ 0 — bodies don't follow the deforming shelf at all.
            grav_y = -9.81
            lam_eff_grav = m * grav_y / float(n_rows_b)   # ≤ 0
            lam_plus_arr = rho * C_arr + lam_eff_grav
            f_arr = np.minimum(lam_plus_arr, 0.0)

            k_col      = (rho * np.ones(n_rows_b))[:, None]
            k_j_lin    = k_col * j_lin_arr
            k_j_ang    = k_col * j_ang_arr
            k_U_y      = k_col * U_y_arr

            A = A + j_lin_arr.T @ k_j_lin
            B = B + j_ang_arr.T @ k_j_lin
            D = D + j_ang_arr.T @ k_j_ang

            f_mag_arr = np.abs(f_arr)
            geom_mask = f_mag_arr > 0.0
            if np.any(geom_mask):
                g_diag_batch = _geom_stiffness_diag_batch(
                    n_hat_const, r_self_w_arr)
                weights = (f_mag_arr * geom_mask)[:, None]
                D = D + np.diag((g_diag_batch * weights).sum(axis=0))

            r_lin = r_lin + j_lin_arr.T @ f_arr
            r_ang = r_ang + j_ang_arr.T @ f_arr

            # Modal-side contributions.
            #   g_{q_s} −= U_y · f          (J_{q_s}^T · f = -U_y · f, sign in g)
            #   H_{q_s} += ρ · U_y U_y^T
            g_q = g_q - U_y_arr.T @ f_arr
            H_q = H_q + U_y_arr.T @ k_U_y

            # F_q_total is accumulated AFTER the Δx back-sub (using the
            # freshly-updated dual) — see the post-assign block below.

            # Cross block H_{x q_s} = -ρ · J_x · U_y^T.
            cross_body[:3, :] += j_lin_arr.T @ k_U_y
            cross_body[3:, :] += j_ang_arr.T @ k_U_y

            j_ang_sq_arr = (j_ang_arr * j_ang_arr).sum(axis=1)
            jjsum_arr    = 1.0 + j_ang_sq_arr
            row_score    = (rho ** 2) * jjsum_arr / max(m, 1e-12)
            if n_rows_b > 0:
                max_rho2_over_m = max(max_rho2_over_m,
                                      float(row_score.max()))

            H_x = np.block([[A, B.T], [B, D]])
            g_x = np.concatenate([r_lin, r_ang])

            H_x_reg = H_x + 1e-12 * np.eye(6)
            try:
                H_x_inv = np.linalg.inv(H_x_reg)
            except np.linalg.LinAlgError:
                continue
            per_body_Hx_inv[body_idx] = H_x_inv
            per_body_gx[body_idx] = g_x
            per_body_cross[body_idx] = -cross_body   # H_xq = -ρ J_x U_y^T

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

        # Apply Δq_s and back-substitute Δx for each tracked body.
        self.rs.q_s = self.rs.q_s + dq

        max_dx = 0.0
        max_dtheta = 0.0
        x_out = x_curr_all.copy()
        q_out = q_curr_all.copy()
        for body_idx, Hxi in per_body_Hx_inv.items():
            M = per_body_cross[body_idx]
            gxi = per_body_gx[body_idx]
            rhs6 = -(gxi + M @ dq)
            delta = Hxi @ rhs6
            d_x = delta[:3]
            d_theta = delta[3:]
            x_out[body_idx] = x_curr_all[body_idx] + d_x
            dq_quat = _quat_xyzw_from_rotvec(d_theta)
            new_q = _quat_xyzw_mul(dq_quat, q_curr_all[body_idx])
            n = float(np.linalg.norm(new_q))
            if n > 1e-12:
                new_q = new_q / n
            q_out[body_idx] = new_q
            max_dx = max(max_dx, float(np.linalg.norm(d_x)))
            max_dtheta = max(max_dtheta, float(np.linalg.norm(d_theta)))

        # XPBD stores `x` as wp.vec3 (float32) and `q` as wp.quat (float32).
        import warp as wp  # local import — warp may be unavailable in some envs
        solver.x.assign(x_out.astype(np.float32))
        solver.q.assign(q_out.astype(np.float32))

        # Implicit-force recovery for F_q_total. The Schur primal drives C
        # → 0 in one iteration, so AVBD's `f = ρ·C + λ_eff` collapses to 0
        # at convergence and the AL dual update has nothing to absorb. The
        # ACTUAL contact force at convergence is recoverable from the
        # body's momentum-deficit-from-predictor: equilibrium means
        # `M/h²·(x_final − x_iner) + j_lin·f_body = 0`, so the contact
        # gradient is `f_body_y = −M/h²·(x_final − x_iner)_y` (≤ 0 by AVBD
        # convention for a body pushed UP). Distribute uniformly across the
        # active corners on the body (the AVBD per-row weighting reduces to
        # this when all active rows have equal ρ·||J||²).
        self._last_F_q_contact[:] = 0.0
        for body_idx, rows_on_body in self._rows_per_body.items():
            if body_idx not in per_body_Hx_inv:
                continue
            row_idx_arr = self._row_idx_by_body[body_idx]
            U_y_arr     = self._row_U_y_by_body[body_idx]
            n_rows_b = row_idx_arr.shape[0]
            if n_rows_b == 0:
                continue
            m = float(self._mass_np[body_idx])
            dy_body = float(x_out[body_idx, 1]
                            - self._x_predicted[body_idx][1])
            f_body_y = -m * inv_dt2 * dy_body          # ≤ 0 for upward push
            f_per_row = f_body_y / float(n_rows_b)
            self._last_F_q_contact += f_per_row * U_y_arr.sum(axis=0)

        self.last_max_dx_norm = max_dx
        self.last_max_dtheta_norm = max_dtheta
        self.last_dq_norm = float(np.linalg.norm(dq))
        self.last_n_iter_solves += 1

    def substep_end_hook(self, solver) -> None:
        """Apply the high-passed modal load to `q_d`, sync `rs.q = q_s + q_d`,
        log passivity. Bit-identical to AVBD's substep_end except for the
        absence of the AL `λ` tracking diagnostic."""
        if self._use_device(solver):
            self._substep_end_device(solver)
            return
        h = float(self.h_substep)
        Mq = self.rs.Mq
        Kq = self.rs.Kq

        if self._last_F_q_contact is None:
            F_q_total_raw = np.zeros(self.rs.r, dtype=np.float64)
        else:
            F_q_total_raw = self._last_F_q_contact.copy()

        # Short-tau EMA to filter substep-bounce noise (see
        # `_F_q_total_smooth` comment). 2 substeps of smoothing is enough
        # to kill the bounce-frequency square-wave; longer attenuates the
        # impact spike. On the first substep latch fully.
        tau_short = max(2.0 * h, 1.0e-3)
        a_short = min(1.0, h / tau_short)
        if (self._F_q_total_smooth is None
                or self._F_q_total_smooth.shape[0] != self.rs.r):
            self._F_q_total_smooth = F_q_total_raw.copy()
        else:
            self._F_q_total_smooth += a_short * (F_q_total_raw
                                                 - self._F_q_total_smooth)
        F_q_total = self._F_q_total_smooth

        tau = float(self.modal_static_lp_tau)
        if self._first_substep_split:
            alpha_ema = 1.0
            self._first_substep_split = False
        else:
            alpha_ema = 1.0 - float(np.exp(-h / max(tau, 1e-9)))
        self.rs.F_q_static_lp = (
            (1.0 - alpha_ema) * self.rs.F_q_static_lp
          + alpha_ema * F_q_total)
        F_q_dyn = F_q_total - self.rs.F_q_static_lp

        # V2-A: when the velocity band owns the body↔ring exchange, it is the
        # SOLE excitation channel — zero the legacy F_q_dyn forcing so the ring
        # is driven only by the band's momentum-conserving Δq̇_d impulses (no
        # double-excitation). q_d/q̇_d then ride the free damped IIR between
        # impulses. See dcr/dcr/impulse_port.py:enable_substep_band.
        if getattr(self, "band_owns_excitation", False):
            F_q_dyn = np.zeros_like(F_q_dyn)

        if (self.q_free is not None and self.qdot_free is not None
                and self.S_h is not None and self.T_h is not None):
            if self.S_h_diag is not None:
                self.rs.q_d    = self.q_free    + self.S_h_diag * F_q_dyn
                self.rs.qdot_d = self.qdot_free + self.T_h_diag * F_q_dyn
            else:
                self.rs.q_d    = self.q_free    + self.S_h @ F_q_dyn
                self.rs.qdot_d = self.qdot_free + self.T_h @ F_q_dyn
        else:
            self.rs.q_d[:]    = 0.0
            self.rs.qdot_d[:] = 0.0

        # Passivity check (logged, not enforced).
        dE_q_d = ((0.5 * float(self.rs.qdot_d @ (Mq @ self.rs.qdot_d))
                 + 0.5 * float(self.rs.q_d   @ (Kq @ self.rs.q_d)))
                 - self._E_q_d_substep_begin)
        W_q_d_bound = abs(h * float(F_q_dyn @ self.rs.qdot_d))
        if dE_q_d > W_q_d_bound + 1e-12:
            self.last_passivity_violations += 1

        self.rs.sync_total_from_split()

        self.last_q_s_norm        = float(np.linalg.norm(self.rs.q_s))
        self.last_q_d_norm        = float(np.linalg.norm(self.rs.q_d))
        self.last_qdot_d_norm     = float(np.linalg.norm(self.rs.qdot_d))
        self.last_F_q_total_norm  = float(np.linalg.norm(F_q_total))
        self.last_F_q_static_norm = float(np.linalg.norm(self.rs.F_q_static_lp))
        self.last_F_q_dyn_norm    = float(np.linalg.norm(F_q_dyn))
        self.last_q_norm    = float(np.linalg.norm(self.rs.q))
        self.last_qdot_norm = self.last_qdot_d_norm

        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, self.rs.q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
        else:
            self.last_max_support_deflection = 0.0

        self.last_modal_KE = 0.5 * float(
            self.rs.qdot_d @ (Mq @ self.rs.qdot_d))
        self.last_modal_PE = 0.5 * float(
            self.rs.q_d @ (Kq @ self.rs.q_d))
        self.last_damp_power = float(
            self.rs.qdot_d @ (self.rs.Dq @ self.rs.qdot_d))

        if self.log_substeps:
            self.substep_log.append({
                "substep_index": int(self._substep_index),
                "t_substep_s":   float(self._substep_index * h),
                "q_norm_m":      self.last_q_norm,
                "qdot_norm":     self.last_qdot_norm,
                "KE_modal_J":    self.last_modal_KE,
                "PE_modal_J":    self.last_modal_PE,
                "P_damp_W":      self.last_damp_power,
                "max_support_deflection_m": self.last_max_support_deflection,
                "n_iter_solves": int(self.last_n_iter_solves),
                "q_s_norm":        self.last_q_s_norm,
                "q_d_norm":        self.last_q_d_norm,
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
        x_curr_all = solver.x.numpy().astype(np.float64)
        q_curr_all = solver.q.numpy().astype(np.float64)
        max_pen = 0.0
        for row_id in rows:
            body_idx = self._row_body[row_id]
            off = self._row_off[row_id]
            anchor_y = self._row_anchor_y[row_id]
            R = _quat_xyzw_to_R(q_curr_all[body_idx])
            corner_y = float(x_curr_all[body_idx, 1] + (R @ off)[1])
            C = corner_y - anchor_y
            if C < 0.0:
                max_pen = max(max_pen, -C)
        self.last_contact_residual = max_pen

    # ======================================================================
    # GPU device-resident path (mirrors ReducedCoupledAVBDCoupler). Topology
    # uploaded ONCE; begin / iteration / end run as on-device kernel launches
    # so the whole substep loop is CUDA-graph-capturable; one host readback
    # per macro-step (post_step_hook) feeds the render/HUD.
    # ======================================================================
    def _use_device(self, solver) -> bool:
        """True when the device-resident path should run. Requires CUDA + the
        eigen basis (the device IIR is the eigen exact-resonator)."""
        return bool(self.device_resident
                    and str(solver.device).startswith("cuda")
                    and getattr(self.rs, "is_eigenbasis", False))

    def _ensure_device_buffers(self, solver) -> None:
        """Allocate scene-capacity device buffers and upload the (static)
        per-corner topology ONCE. cap_rows = 8·n_tracked (all corners are
        candidate rows; per-substep gap-gating flips row_active on-device).
        Sets solver.hooks_device_resident so the solver captures the substep
        loop into a CUDA graph."""
        import warp as wp
        from .reduced_coupled_xpbd_kernels import (
            vec3d, mat33d, make_k_eps_solve_tiled)

        dev = solver.device
        f64 = wp.float64
        r = int(self.rs.r)

        inv_mass_np = solver.inv_mass.numpy().astype(np.float64)
        n_bodies = int(inv_mass_np.shape[0])
        mass_full = np.where(inv_mass_np > 0.0,
                             1.0 / np.maximum(inv_mass_np, 1e-30), 0.0)
        inv_I_np = solver.inv_I.numpy().astype(np.float64)
        I_local_full = np.where(inv_I_np > 0.0,
                                1.0 / np.maximum(inv_I_np, 1e-30), 0.0)
        he_np = solver.he.numpy().astype(np.float64)

        tracked = [int(b) for b in self.tracked_body_indices
                   if mass_full[int(b)] > 0.0]
        n_b = len(tracked)
        max_b = max(1, n_b)
        cap_rows = max(1, 8 * n_b)
        self._dev_n_b = n_b
        self._dev_max_b = max_b
        self._dev_cap_rows = cap_rows
        self._dev_r = r

        d = self._dbuf
        # ---- constants (uploaded once) ----
        d["Kq"] = wp.array(self.rs.Kq.astype(np.float64), dtype=f64, device=dev)
        d["Mq"] = wp.array(self.rs.Mq.astype(np.float64), dtype=f64, device=dev)
        d["Mq_diag"] = wp.array(np.diag(self.rs.Mq).astype(np.float64),
                                dtype=f64, device=dev)
        d["eigen_omega"] = wp.array(
            np.asarray(self.rs.eigen_omegas, np.float64), dtype=f64, device=dev)
        d["eigen_zeta"] = wp.array(
            np.asarray(self.rs.eigen_zetas, np.float64), dtype=f64, device=dev)
        d["grid_Uy"] = wp.array(
            self.rs.U_points[:, 1, :].astype(np.float64), dtype=f64, device=dev)
        d["mass"] = wp.array(mass_full.astype(np.float32), dtype=float,
                             device=dev)
        I_mats = np.zeros((n_bodies, 3, 3), np.float32)
        for b in range(n_bodies):
            I_mats[b] = np.diag(I_local_full[b]).astype(np.float32)
        # k_body reads inertia_local as float32 wp.mat33 (then upcasts).
        d["inertia_local"] = wp.array(I_mats, dtype=wp.mat33, device=dev)
        # ---- resident modal state (persists across steps) ----
        for nm in ("q_s", "q_d", "qdot_d", "q_s_anchor_lp", "F_q_static_lp",
                   "F_q_total_smooth", "q_free", "qdot_free", "S_h_diag",
                   "T_h_diag", "F_q_dyn", "q_total", "qdot_total",
                   "gq", "Fq", "rhs", "dq"):
            d[nm] = wp.zeros(r, dtype=f64, device=dev)
        d["Hq"] = wp.zeros((r, r), dtype=f64, device=dev)
        d["S"] = wp.zeros((r, r), dtype=f64, device=dev)
        d["diag"] = wp.zeros(8, dtype=f64, device=dev)
        d["escal"] = wp.zeros(4, dtype=f64, device=dev)
        d["first_substep"] = wp.ones(1, dtype=int, device=dev)
        d["pass_counter"] = wp.zeros(1, dtype=int, device=dev)
        d["counts"] = wp.zeros(3, dtype=int, device=dev)
        # ---- predictor snapshot (full body arrays) ----
        d["x_pred"] = wp.zeros(n_bodies, dtype=wp.vec3, device=dev)
        d["q_pred"] = wp.zeros(n_bodies, dtype=wp.quat, device=dev)
        # ---- topology (uploaded once) ----
        d["body_ids"] = wp.zeros(max_b, dtype=int, device=dev)
        d["body_row_start"] = wp.zeros(max_b + 1, dtype=int, device=dev)
        d["row_index"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_body"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_body_slot"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["row_off"] = wp.zeros(cap_rows, dtype=vec3d, device=dev)
        d["row_U_y"] = wp.zeros((cap_rows, r), dtype=f64, device=dev)
        d["row_anchor_y"] = wp.zeros(cap_rows, dtype=f64, device=dev)
        d["row_active"] = wp.zeros(cap_rows, dtype=int, device=dev)
        d["rowdata"] = wp.zeros((cap_rows, 8), dtype=f64, device=dev)
        d["n_active"] = wp.zeros(max_b, dtype=int, device=dev)
        d["f_per_row"] = wp.zeros(max_b, dtype=f64, device=dev)
        # ---- per-body block scratch ----
        for nm in ("b_TL", "b_TR", "b_BL", "b_BR"):
            d[nm] = wp.zeros(max_b, dtype=mat33d, device=dev)
        for nm in ("b_gx0", "b_gx1", "b_hg0", "b_hg1"):
            d[nm] = wp.zeros(max_b, dtype=vec3d, device=dev)
        d["Hmb_top"] = wp.zeros((max_b, r), dtype=vec3d, device=dev)
        d["Hmb_bot"] = wp.zeros((max_b, r), dtype=vec3d, device=dev)
        d["M"] = wp.zeros((max_b, 6, r), dtype=f64, device=dev)
        d["rho_score"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["b_dxn"] = wp.zeros(max_b, dtype=f64, device=dev)
        d["b_dthn"] = wp.zeros(max_b, dtype=f64, device=dev)
        # ---- V2-B: device-resident velocity band (shared k_velocity_band) ----
        # XPBD's gap-gated d["row_active"] IS the band's per-corner gate (only
        # corners within contact_active_margin participate), so no extra array.
        d["v_band"] = wp.zeros(n_bodies, dtype=vec3d, device=dev)
        d["omega_band"] = wp.zeros(n_bodies, dtype=vec3d, device=dev)
        d["reservoir"] = wp.zeros(1, dtype=f64, device=dev)        # persistent R
        d["band_diag"] = wp.zeros(4, dtype=f64, device=dev)        # n,maxλ,clamps
        # Device-resident contact friction (k_contact_friction) — standalone
        # tangential Coulomb pass; reuses the band's CSR topology + row_active.
        d["v_fric"] = wp.zeros(n_bodies, dtype=vec3d, device=dev)
        d["omega_fric"] = wp.zeros(n_bodies, dtype=vec3d, device=dev)
        d["fric_diag"] = wp.zeros(2, dtype=f64, device=dev)        # n_corners,maxλ

        # Build + upload the per-corner CSR topology.
        body_ids = np.zeros(max_b, np.int32)
        body_row_start = np.zeros(max_b + 1, np.int32)
        row_body = np.zeros(cap_rows, np.int32)
        row_body_slot = np.zeros(cap_rows, np.int32)
        row_index = np.arange(cap_rows, dtype=np.int32)
        row_off = np.zeros((cap_rows, 3), np.float64)
        start = 0
        for t, b in enumerate(tracked):
            body_ids[t] = b
            body_row_start[t] = start
            he = he_np[b]
            for c in range(8):
                row_body[start] = b
                row_body_slot[start] = t
                row_off[start] = _BOX_CORNER_SIGNS[c] * he
                start += 1
        body_row_start[n_b] = start
        total = start
        d["counts"].assign(np.array([n_b, total, total], np.int32))
        d["body_ids"].assign(body_ids)
        d["body_row_start"].assign(body_row_start)
        d["row_index"].assign(row_index)
        d["row_body"].assign(row_body)
        d["row_body_slot"].assign(row_body_slot)
        d["row_off"].assign(row_off)
        # Seed resident modal state from rs (zeros at sim start).
        d["q_s"].assign(self.rs.q_s.astype(np.float64))
        d["q_d"].assign(self.rs.q_d.astype(np.float64))
        d["qdot_d"].assign(self.rs.qdot_d.astype(np.float64))
        d["F_q_static_lp"].assign(self.rs.F_q_static_lp.astype(np.float64))
        _qd_w = 1.0 if self.anchor_includes_q_d else 0.0
        d["q_s_anchor_lp"].assign(
            (self.rs.q_s + _qd_w * self.rs.q_d).astype(np.float64))
        d["F_q_total_smooth"].assign(self.rs.q_s.astype(np.float64) * 0.0)

        # Cached scalars.
        self._dev_inv_dt2 = 1.0 / (float(self.h_substep) ** 2)
        self._dev_h_sub = float(self.h_substep)
        self._dev_tau = float(self.modal_static_lp_tau)
        self._dev_grav_y = -9.81
        self._dev_eps_base = (self.eps_baseline
                              * float(np.trace(self.rs.Kq)) / max(r, 1))
        self._dev_eps_cross = float(self.eps_cross_factor)
        n_sub = int(round(self.h_macro / self.h_substep)) \
            if self.h_substep > 0 else 1
        self._dev_n_sub = max(1, n_sub)
        # Per-substep passivity / max-norm diagnostics are pure logging — gate
        # their kernels off by default (each is a launch-latency-bound dim=1/r
        # kernel run 8–32×/step). Enable via log_substeps / diagnostic_mode.
        self._dev_diag = bool(self.log_substeps or self.diagnostic_mode)
        self._dev_n_iter = int(getattr(solver, "iterations", 1))

        # Block-cooperative Cholesky for the r×r SPD Schur solve (replaces the
        # single-thread GE on CUDA). Generated per-r and WARMED here, outside
        # any capture region, so the first captured launch never compiles.
        self._k_eps_tiled = make_k_eps_solve_tiled(r)
        wp.launch_tiled(
            self._k_eps_tiled, dim=[1], device=dev,
            block_dim=int(self._eps_block_dim), inputs=[
                d["counts"], d["rho_score"], f64(self._dev_eps_base),
                f64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"],
                d["q_s"], d["diag"]])
        wp.synchronize_device(dev)

    def _substep_begin_device(self, solver) -> None:
        """Device substep_begin: snapshot the predictor, modal-energy reference,
        eigen IIR precompute, anchor low-pass of (q_s + q_d), and basis-eval +
        gap-gate — all on-device."""
        import warp as wp
        from . import reduced_coupled_xpbd_kernels as KX
        from ..avbd import reduced_coupled_kernels as K
        if not self._device_ready:
            self._ensure_device_buffers(solver)
            solver.hooks_device_resident = True
            self._device_ready = True
        if self._dev_n_b == 0:
            return
        d = self._dbuf
        dev = solver.device
        r = int(self._dev_r)
        cap = int(self._dev_cap_rows)
        max_b = int(self._dev_max_b)
        f64 = wp.float64
        # Snapshot the post-integrate predictor state (x_inertial / q_inertial).
        wp.copy(d["x_pred"], solver.x)
        wp.copy(d["q_pred"], solver.q)
        # Modal-energy reference for the passivity log (diagnostic only).
        if self._dev_diag:
            wp.launch(K.k_modal_energy, dim=1, device=dev, inputs=[
                r, d["q_d"], d["qdot_d"], d["Mq"], d["Kq"], d["escal"], int(0)])
        # Eigen exact-resonator precompute on (q_d, q̇_d).
        wp.launch(K.k_iir_precompute, dim=r, device=dev, inputs=[
            r, d["q_d"], d["qdot_d"], d["eigen_omega"], d["eigen_zeta"],
            d["Mq_diag"], f64(self._dev_h_sub), d["q_free"], d["qdot_free"],
            d["S_h_diag"], d["T_h_diag"]])
        # Anchor reference: EMA low-pass of (q_s + q_d). a_lp = 1 ⇒ no smoothing
        # (anchor tracks q_total exactly), matching the numpy no-LP branch.
        lp_tau = self.modal_static_lp_tau if self.anchor_static_lowpass else 0.0
        a_lp = min(1.0, float(self.h_substep) / lp_tau) if lp_tau > 0.0 else 1.0
        qd_w = 1.0 if self.anchor_includes_q_d else 0.0
        wp.launch(KX.k_anchor_lp_xpbd, dim=r, device=dev, inputs=[
            r, d["q_s"], d["q_d"], f64(qd_w), f64(a_lp), d["first_substep"],
            d["q_s_anchor_lp"]])
        # Basis eval at the (predictor) corners, freeze anchor, gap-gate active.
        wp.launch(KX.k_eval_and_gate, dim=cap, device=dev, inputs=[
            d["x_pred"], d["q_pred"], d["counts"], r, d["row_body"],
            d["row_off"], d["grid_Uy"], int(self.n_grid_x), int(self.n_grid_z),
            f64(self.shelf_length), f64(self.shelf_width),
            f64(self.shelf_y_rest), d["q_s_anchor_lp"],
            f64(self.contact_active_margin), d["row_U_y"], d["row_anchor_y"],
            d["row_active"]])
        wp.launch(KX.k_count_active, dim=max_b, device=dev, inputs=[
            d["counts"], d["body_row_start"], d["row_active"], d["n_active"]])

    def _iteration_device(self, solver, iter_idx: int = 0) -> None:
        """One coupled Schur iteration as on-device kernel launches (no host
        round-trip). Mirrors iteration_hook; the Schur core kernels are the
        shared AVBD ones, the contact-force adapter is XPBD-specific."""
        import warp as wp
        from . import reduced_coupled_xpbd_kernels as KX
        from ..avbd import reduced_coupled_kernels as K
        if not self._device_ready or self._dev_n_b == 0:
            return
        d = self._dbuf
        dev = solver.device
        r = int(self._dev_r)
        cap = int(self._dev_cap_rows)
        max_b = int(self._dev_max_b)
        f64 = wp.float64
        # 1. per-row XPBD contact force (fixed ρ + gravity phantom dual).
        wp.launch(KX.k_rowforce_xpbd, dim=cap, device=dev, inputs=[
            solver.x, solver.q, d["mass"], d["counts"], d["row_index"],
            d["row_body"], d["row_body_slot"], d["row_off"], d["row_anchor_y"],
            d["row_active"], d["n_active"], f64(self.contact_stiffness),
            f64(self._dev_grav_y), d["rowdata"]])
        # 2. modal Hessian + gradient (shared AVBD kernels). k_g's Fq output is
        #    the penalty sum — IGNORED here; the IIR drive is the momentum
        #    deficit computed in step 7, which overwrites d["Fq"].
        wp.launch(K.k_hq, dim=(r, r), device=dev, inputs=[
            r, d["counts"], d["Kq"], d["row_U_y"], d["rowdata"], d["Hq"]])
        wp.launch(K.k_g, dim=r, device=dev, inputs=[
            r, d["counts"], d["Kq"], d["q_s"], d["row_U_y"], d["rowdata"],
            d["gq"], d["Fq"]])
        # 3. per-body H_x assembly + block inverse, and the cross block M.
        wp.launch(K.k_body, dim=max_b, device=dev, inputs=[
            solver.x, solver.q, d["mass"], d["inertia_local"], d["x_pred"],
            d["q_pred"], d["counts"], d["body_ids"], d["body_row_start"],
            d["rowdata"], f64(self._dev_inv_dt2), d["b_TL"], d["b_TR"],
            d["b_BL"], d["b_BR"], d["b_gx0"], d["b_gx1"], d["b_hg0"],
            d["b_hg1"], d["rho_score"]])
        wp.launch(K.k_body_cross, dim=(max_b, r), device=dev, inputs=[
            d["mass"], r, d["counts"], d["body_ids"], d["body_row_start"],
            d["row_U_y"], d["rowdata"], d["M"]])
        # 4. Schur reduce + rhs.
        wp.launch(K.k_hmb, dim=(max_b, r), device=dev, inputs=[
            r, d["counts"], d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"],
            d["M"], d["Hmb_top"], d["Hmb_bot"]])
        wp.launch(K.k_schur, dim=(r, r), device=dev, inputs=[
            r, d["counts"], d["Hq"], d["M"], d["Hmb_top"], d["Hmb_bot"],
            d["S"]])
        wp.launch(K.k_rhs, dim=r, device=dev, inputs=[
            r, d["counts"], d["gq"], d["b_hg0"], d["b_hg1"], d["M"], d["rhs"]])
        # 5. ε-regularize + r×r cooperative-Cholesky solve + q_s update.
        wp.launch_tiled(
            self._k_eps_tiled, dim=[1], device=dev,
            block_dim=int(self._eps_block_dim), inputs=[
                d["counts"], d["rho_score"], f64(self._dev_eps_base),
                f64(self._dev_eps_cross), d["S"], d["rhs"], d["dq"], d["q_s"],
                d["diag"]])
        # 6. back-substitute body deltas + max-norm diagnostics.
        wp.launch(K.k_backsub, dim=max_b, device=dev, inputs=[
            solver.x, solver.q, d["mass"], r, d["counts"], d["body_ids"],
            d["b_TL"], d["b_TR"], d["b_BL"], d["b_BR"], d["b_gx0"], d["b_gx1"],
            d["M"], d["dq"], d["diag"], d["b_dxn"], d["b_dthn"]])
        if self._dev_diag:
            wp.launch(K.k_reduce_diag, dim=1, device=dev, inputs=[
                d["counts"], d["b_dxn"], d["b_dthn"], d["diag"]])
        # 7. momentum-deficit modal load (the IIR drive). Only the LAST
        #    iteration's value reaches substep_end, so compute it once on the
        #    final iteration — identical result, skips it on iters 0..n-2.
        if iter_idx >= self._dev_n_iter - 1:
            wp.launch(KX.k_body_fdef, dim=max_b, device=dev, inputs=[
                solver.x, d["x_pred"], d["mass"], d["counts"], d["body_ids"],
                d["n_active"], f64(self._dev_inv_dt2), d["f_per_row"]])
            wp.launch(KX.k_fq_momentum, dim=r, device=dev, inputs=[
                r, d["counts"], d["body_row_start"], d["row_active"],
                d["row_U_y"], d["f_per_row"], d["Fq"]])

    def _substep_end_device(self, solver) -> None:
        """Device substep_end: short-τ EMA + static/dynamic split + exact-
        resonator force of q_d, passivity log, and q = q_s + q_d sync — all
        on-device. The host readback is deferred to post_step_hook (outside the
        captured region)."""
        import warp as wp
        from . import reduced_coupled_xpbd_kernels as KX
        from ..avbd import reduced_coupled_kernels as K
        if not self._device_ready or self._dev_n_b == 0:
            self._substep_index += 1
            return
        d = self._dbuf
        dev = solver.device
        r = int(self._dev_r)
        f64 = wp.float64
        band_owns = 1 if getattr(self, "band_owns_excitation", False) else 0
        wp.launch(KX.k_iir_apply_xpbd, dim=r, device=dev, inputs=[
            r, d["Fq"], d["F_q_total_smooth"], d["F_q_static_lp"],
            d["q_free"], d["qdot_free"], d["S_h_diag"], d["T_h_diag"],
            d["first_substep"], f64(self._dev_h_sub), f64(self._dev_tau),
            int(band_owns), d["q_d"], d["qdot_d"], d["F_q_dyn"]])
        if self._dev_diag:
            # Passivity log (also clears the first-substep flag).
            wp.launch(K.k_passivity, dim=1, device=dev, inputs=[
                r, d["q_d"], d["qdot_d"], d["Mq"], d["Kq"], d["F_q_dyn"],
                d["escal"], f64(self._dev_h_sub), d["first_substep"],
                d["pass_counter"]])
        else:
            # Cheap dedicated first-substep clear when passivity is gated off.
            wp.launch(KX.k_clear_first, dim=1, device=dev,
                      inputs=[d["first_substep"]])
        wp.launch(K.k_sync_total, dim=r, device=dev, inputs=[
            r, d["q_s"], d["q_d"], d["qdot_d"], d["q_total"], d["qdot_total"]])
        # V2-B: device-resident velocity band (shared kernel). XPBD passes its
        # device mass/inertia (inverted from inv_mass/inv_I) and gap-gated
        # row_active. Sole body↔ring channel; on-device (no host round-trip).
        if band_owns:
            wp.launch(K.k_velocity_band, dim=1, device=dev, inputs=[
                solver.x, solver.q, solver.v, solver.omega,
                d["mass"], d["inertia_local"],
                d["counts"], d["body_ids"], d["row_body"], d["row_off"],
                d["row_U_y"], d["row_active"], d["q_s"], d["qdot_d"], r,
                f64(self.shelf_y_rest),
                f64(getattr(self, "_band_margin", 5.0e-3)),
                f64(getattr(self, "_band_eta", 1.0)),
                f64(getattr(self, "_band_e", 0.0)),
                f64(1.0e-9), f64(1.0e-12),
                d["v_band"], d["omega_band"], d["reservoir"], d["band_diag"]])
        # Device-resident contact friction: standalone tangential Coulomb pass,
        # runs band-on AND band-off (independent of band_owns). Launched after
        # the band so it damps the band's per-corner angular kick. Stays on-
        # device (no host round-trip), inside the captured graph.
        if getattr(self, "friction_on_device", False):
            wp.launch(K.k_contact_friction, dim=1, device=dev, inputs=[
                solver.x, solver.q, solver.v, solver.omega,
                d["mass"], d["inertia_local"],
                d["counts"], d["body_ids"], d["row_body"], d["row_off"],
                d["row_U_y"], d["row_active"], d["q_s"], r,
                f64(self.shelf_y_rest),
                f64(getattr(self, "_fric_margin", 5.0e-3)),
                f64(getattr(self, "_fric_mu", 0.4)),
                f64(getattr(self, "_fric_h", 1.0 / 120.0)),
                f64(9.81), f64(1.0e-9),
                d["v_fric"], d["omega_fric"], d["fric_diag"]])
        self._substep_index += 1

    def post_step_hook(self, solver) -> None:
        """Fires once per solver.step(), OUTSIDE the captured region. Pulls the
        resident modal state to host for the render/HUD."""
        if not self._use_device(solver) or not self._device_ready:
            return
        if self._dev_n_b == 0:
            return
        d = self._dbuf
        # Minimal render/HUD readback: q_s + q_d (→ rs.q for the support mesh).
        # qdot_d / F_q_static_lp / Fq stay device-resident (the sim never needs
        # them on host); only pull them when diagnostics are on.
        self.rs.q_s = d["q_s"].numpy().astype(np.float64).copy()
        self.rs.q_d = d["q_d"].numpy().astype(np.float64).copy()
        self.rs.sync_total_from_split()
        self.last_q_s_norm = float(np.linalg.norm(self.rs.q_s))
        self.last_q_d_norm = float(np.linalg.norm(self.rs.q_d))
        self.last_q_norm = float(np.linalg.norm(self.rs.q))
        # V2-B: the device band mutates qdot_d + the reservoir every substep, so
        # pull them for the HUD/tests regardless of the diagnostics gate.
        if getattr(self, "band_owns_excitation", False) and "reservoir" in d:
            self.rs.qdot_d = d["qdot_d"].numpy().astype(np.float64).copy()
            self.rs.sync_total_from_split()
            self._modal_reservoir = float(d["reservoir"].numpy()[0])
            bd = d["band_diag"].numpy()
            self.last_band_impulses = int(bd[0])
            self.last_band_max_lambda = float(bd[1])
            self.last_band_clamps = int(bd[2])
            self.last_qdot_d_norm = float(np.linalg.norm(self.rs.qdot_d))
        if not self._dev_diag:
            return
        self.rs.qdot_d = d["qdot_d"].numpy().astype(np.float64).copy()
        self.rs.F_q_static_lp = d["F_q_static_lp"].numpy().astype(
            np.float64).copy()
        self._last_F_q_contact = d["Fq"].numpy().astype(np.float64).copy()
        diag = d["diag"].numpy()
        self.last_max_dx_norm = float(diag[0])
        self.last_max_dtheta_norm = float(diag[1])
        self.last_dq_norm = float(diag[2])
        self.last_passivity_violations = int(d["pass_counter"].numpy()[0])
        self.last_qdot_d_norm = float(np.linalg.norm(self.rs.qdot_d))
        self.last_qdot_norm = self.last_qdot_d_norm
        if self.rs.U_points.shape[0] > 0:
            disp = np.einsum("kij,j->ki", self.rs.U_points, self.rs.q)
            self.last_max_support_deflection = float(
                np.linalg.norm(disp, axis=1).max())
