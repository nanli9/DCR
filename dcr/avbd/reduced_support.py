"""Reduced-coordinate deformable support — data layer.

Implements the data structures and synthetic basis builders described in
`prompts/reduced_coordinate_avbd_support_dcr_extension.md` §2, §3, §13. The
support is represented by reduced coordinates q ∈ R^r with rest geometry
x_s^0 + U(x_s^0) q. v1 carries a synthetic plate-bending + Gaussian-bump
basis so the experiment can be run without a full FEM pipeline.

State and solve helpers live in `reduced_support_solve.py`; this file
intentionally has no dependency on Solver6DOF so it can be unit-tested in
pure numpy. See the v1 plan at
`~/.claude/plans/you-are-working-inside-prancy-turtle.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class ReducedSupport:
    """Per-§2 representation of a reduced deformable support.

    Coordinates `q ∈ R^r` with deformed surface

        x_s(q) = x_s^0 + U(x_s^0) q                                 (§2)

    The first `r_modal` columns of U are vibration-like modes with explicit
    frequencies `modal_omega`. The remaining columns are static / patch
    modes (local compliance only) and are excluded from the transient
    overlay (`IIRModalStepper` step) because they have no well-defined
    oscillator frequency.
    """

    # ---- Geometry of the support surface ---------------------------------
    # x_s^0 at sampled surface points + outward unit normal at rest.
    point_positions_rest: NDArray[np.float64]   # (n_pts, 3)
    point_normals_rest:   NDArray[np.float64]   # (n_pts, 3)

    # ---- Basis U sampled at those points --------------------------------
    # U_points[k, :, j] is the 3-vector displacement of surface sample k
    # under unit amplitude of mode j. r = U_points.shape[2].
    U_points: NDArray[np.float64]               # (n_pts, 3, r)

    # ---- Reduced matrices (general dense — works for enriched bases) ----
    Mq: NDArray[np.float64]                     # (r, r) reduced mass
    Kq: NDArray[np.float64]                     # (r, r) reduced stiffness
    Dq: NDArray[np.float64]                     # (r, r) reduced damping

    # ---- State (q, qdot, predictor q_hat, snapshot for finite-diff) -----
    q:        NDArray[np.float64]               # (r,)
    qdot:     NDArray[np.float64]               # (r,)
    q_prev_macro: NDArray[np.float64]           # (r,) at macro-step start
    q_hat:    NDArray[np.float64]               # (r,) predicted

    # ---- Modal sub-block info for the transient overlay (§9) ------------
    # The first `r_modal` columns of U_points are oscillator modes; the
    # remaining columns are static/patch modes with no ω. Only the modal
    # sub-block feeds IIRModalStepper.
    r_modal:      int
    modal_omega:  NDArray[np.float64]           # (r_modal,)  ω_j
    modal_zeta:   NDArray[np.float64]           # (r_modal,)  ξ_j damping ratios

    # ---- Probe / observation points for distant response (§9.4) ---------
    probe_points:        NDArray[np.float64]    # (n_probe, 3)
    probe_normals:       NDArray[np.float64]    # (n_probe, 3)
    probe_U:             NDArray[np.float64]    # (n_probe, 3, r)
    probe_body_indices:  list[int]              # AVBD body idx per probe (Δv target)

    # ---- Anchor binding: rest floor-y per AVBD floor-contact row --------
    # Populated by the solve module when it walks solver._rows the first
    # time. The hook reads floor_y_rest[row_idx] back during anchor reset.
    floor_y_rest: dict[int, float] = field(default_factory=dict)

    # ---- Per-step tracking (rebuilt by the hook at substep start) -------
    tracked_row_indices:  list[int] = field(default_factory=list)
    tracked_row_to_pt:    dict[int, int] = field(default_factory=dict)

    # ---- Eigenbasis projection (spec §16) -------------------------------
    # When `is_eigenbasis = True`, the reduced coordinates `q` ARE the true
    # vibration modes (M̂ = I, K̂ = Ω²). Then `eigen_omegas[i]² = K̂[i,i]`
    # and `eigen_zetas[i] = D̂[i,i] / (2·ω_i)` decouple per-mode, and the
    # IIR coupler can use the closed-form per-mode resonator instead of a
    # dense matrix exponential. `eigen_V` is the (r, r) generalized
    # eigenvector matrix s.t. `q_synthetic = eigen_V · q_eigen`. Length-r
    # variants of `modal_omega`/`modal_zeta` (the old r_modal-length ones
    # stay for v1 BCD back-compat).
    is_eigenbasis:  bool = False
    eigen_V:        NDArray[np.float64] | None = None   # (r, r) or None
    eigen_omegas:   NDArray[np.float64] | None = None   # (r,)   or None
    eigen_zetas:    NDArray[np.float64] | None = None   # (r,)   or None

    # ---- Flags ----------------------------------------------------------
    enabled: bool = True
    overlay_enabled: bool = True
    restart_overlay_each_step: bool = True

    # ---- Static / dynamic split state (used by ReducedCoupledAVBDCoupler).
    #
    # # DEVIATION (foundation §15 / drift-fix v1, 2026-06-08):
    # the paper's Eq. 10 evolves a single q via the IIR resonator and feeds
    # U_y·q directly into the contact anchor. That is non-passive at finite
    # iteration counts under unilateral contact (position-level ratchet —
    # zero-mean q oscillation produces +∞ probe drift). We split:
    #     q = q_s + q_d
    # q_s is the algebraic static-sag coordinate (solved coupled with x in
    # the AVBD iteration, baseline H_q = K_q), used in the contact anchor.
    # q_d is the dynamic IIR oscillator forced by a high-passed modal load
    # (F_dyn = F_total − low_pass(F_total)), used only in the visual surface.
    # q_d NEVER enters the contact constraint nor H_xq, so the ratchet cannot
    # form. See plan ~/.claude/plans/you-are-working-in-fizzy-waffle.md and
    # the diagnostic variant table that locates the bug.
    q_s:                NDArray[np.float64] | None = None   # (r,)
    q_d:                NDArray[np.float64] | None = None   # (r,)
    qdot_d:             NDArray[np.float64] | None = None   # (r,)
    q_d_prev_macro:     NDArray[np.float64] | None = None   # (r,) snapshot
    qdot_d_prev_macro:  NDArray[np.float64] | None = None   # (r,) snapshot
    F_q_static_lp:      NDArray[np.float64] | None = None   # (r,) EMA LP

    def __post_init__(self) -> None:
        """Allocate the static/dynamic-split scratch arrays if the caller
        didn't (the common case — only the canonical state vectors q/qdot
        are required positional fields)."""
        n = int(self.q.shape[0])
        if self.q_s is None:
            self.q_s = np.zeros(n, dtype=np.float64)
        if self.q_d is None:
            self.q_d = np.zeros(n, dtype=np.float64)
        if self.qdot_d is None:
            self.qdot_d = np.zeros(n, dtype=np.float64)
        if self.q_d_prev_macro is None:
            self.q_d_prev_macro = np.zeros(n, dtype=np.float64)
        if self.qdot_d_prev_macro is None:
            self.qdot_d_prev_macro = np.zeros(n, dtype=np.float64)
        if self.F_q_static_lp is None:
            self.F_q_static_lp = np.zeros(n, dtype=np.float64)

    @property
    def r(self) -> int:
        """Total number of reduced coordinates."""
        return int(self.q.shape[0])

    @property
    def n_points(self) -> int:
        return int(self.point_positions_rest.shape[0])

    @property
    def n_probes(self) -> int:
        return int(self.probe_points.shape[0])

    def sync_total_from_split(self) -> None:
        """In `static_dynamic_split` mode the coupler owns q_s and q_d, and
        the canonical `q` field is a mirror `q_s + q_d` (similarly for
        `qdot` = `qdot_d`, since q_s is algebraic with no velocity).
        Downstream callers (viser surface render, HUD `last_q_norm`, the
        `last_max_support_deflection` diagnostic) read `rs.q` directly,
        so the coupler must call this after every iteration_hook /
        substep_end_hook commit to keep the views consistent."""
        np.copyto(self.q, self.q_s + self.q_d)
        np.copyto(self.qdot, self.qdot_d)

    def reset_state(self) -> None:
        """Zero q, qdot, q_hat and the static/dynamic-split scratch
        arrays. Useful between scenes / for repeated runs."""
        self.q[:] = 0.0
        self.qdot[:] = 0.0
        self.q_prev_macro[:] = 0.0
        self.q_hat[:] = 0.0
        # Split-mode state (no-op in legacy mode but cheap and consistent).
        self.q_s[:] = 0.0
        self.q_d[:] = 0.0
        self.qdot_d[:] = 0.0
        self.q_d_prev_macro[:] = 0.0
        self.qdot_d_prev_macro[:] = 0.0
        self.F_q_static_lp[:] = 0.0


# ---------------------------------------------------------------------------
# Synthetic plate-bending basis
# ---------------------------------------------------------------------------
#
# The v1 spec (§13, §18) allows a synthetic basis for the shelf experiment.
# We build:
#
#   (a) `n_modes_global` clamped-beam bending modes: each mode is a
#       sin((nπ/L) (x+L/2)) profile in the long axis, constant in the short
#       axis. y-displacement only (the support deforms vertically). Per
#       mass-uniform Euler-Bernoulli beam, ω_n = (nπ/L)² sqrt(D/μ).
#
#   (b) `n_local_per_zone` Gaussian-bump static modes at each contact zone
#       center. These give local compliance the smooth bending modes miss
#       (§13 J_q ≈ 0 issue); they have no well-defined ω so the overlay
#       skips them.
#
# All modes act only in +y (the bending direction). U_points[:, 0, :] = 0
# and U_points[:, 2, :] = 0 — only the y-row is populated. This keeps the
# basis tiny and the J_q = U^T n inner-product clean (n = ŷ on a floor
# contact ⇒ J_q is just the y-row of U).
#
# Material defaults are picked so ω·h is large for h = 1/120 s — Section 8
# of the spec predicts the bare coupled solve will underestimate the
# transient peak by roughly that factor, which is exactly what the
# overlay-vs-no-overlay A/B is meant to demonstrate.


def _place_contact_zones(
    length: float,
    n_zones: int,
    requested: list[tuple[float, float]] | None,
) -> list[tuple[float, float]]:
    """Deterministic, deduplicated bump-center placement.

    Uses the caller's requested centers first (they're the actual
    contact zones the basis must be expressive at), then pads with a
    uniform sweep across [-0.45 L, 0.45 L] at z=0. Snaps to 6 sig.
    figs for dedup; keeps inserting until either `n_zones` distinct
    positions are collected or the candidate sweep is exhausted, in
    which case the last position is replicated to fill out (cosmetic
    fallback — should never trigger in practice).
    """
    zones: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()

    def _try_add(x: float, z: float) -> None:
        key = (round(float(x), 6), round(float(z), 6))
        if key not in seen:
            seen.add(key)
            zones.append((float(x), float(z)))

    if requested:
        for (xc, zc) in requested:
            _try_add(xc, zc)
            if len(zones) >= n_zones:
                break

    if len(zones) < n_zones:
        extra_needed = n_zones - len(zones)
        # Generate a generous sweep so dedup against `requested` can
        # discard collisions without running out.
        n_candidates = max(3 * extra_needed + 1, n_zones * 3)
        sweep = np.linspace(-length * 0.45, length * 0.45, n_candidates)
        for x in sweep:
            _try_add(float(x), 0.0)
            if len(zones) >= n_zones:
                break

    zones = zones[:n_zones]
    while len(zones) < n_zones:
        zones.append(zones[-1])
    return zones


def make_synthetic_modal_basis_for_shelf(
    *,
    length: float,
    width: float,
    thickness: float = 0.005,
    youngs: float = 2.0e11,
    density: float = 7850.0,
    poisson: float = 0.30,
    n_modes_global: int = 8,
    n_modes_local: int = 8,
    contact_zone_centers: list[tuple[float, float]] | None = None,
    contact_zone_sigma: float = 0.03,
    n_grid_x: int = 21,
    n_grid_z: int = 11,
    y_rest: float = 0.0,
    rayleigh_alpha0: float = 0.0,
    rayleigh_alpha1: float = 5.0e-6,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = False,
) -> tuple[
    NDArray[np.float64],   # point_positions_rest (n_pts, 3)
    NDArray[np.float64],   # point_normals_rest   (n_pts, 3)
    NDArray[np.float64],   # U_points             (n_pts, 3, r)
    NDArray[np.float64],   # Mq                   (r, r)
    NDArray[np.float64],   # Kq                   (r, r)
    NDArray[np.float64],   # Dq                   (r, r)
    int,                   # r_modal (first r_modal columns are oscillators)
    NDArray[np.float64],   # modal_omega          (r_modal,)
    NDArray[np.float64],   # modal_zeta           (r_modal,)
    list[tuple[float, float]],   # bump_zones    (for probe basis eval)
    bool,                  # is_eigenbasis
    NDArray[np.float64],   # eigen_V              (r, r)  — I if not projected
    NDArray[np.float64],   # eigen_omegas         (r,)
    NDArray[np.float64],   # eigen_zetas          (r,)
]:
    """Build a deterministic plate-bending + Gaussian-bump basis (§13).

    The shelf occupies the rectangle [-L/2, L/2] × [-W/2, W/2] in the
    (x, z) plane at height y = `y_rest`. Bending modes are 1D
    clamped-beam sin profiles in x (constant in z). Static bump modes are
    isotropic Gaussians centered at `contact_zone_centers`.

    Mass and stiffness matrices are computed by midpoint quadrature over
    the (n_grid_x × n_grid_z) sample grid. The bending modes use
    Euler-Bernoulli beam theory (D = E h^3 / (12 (1 − ν²))) for the
    diagonal of K_q, which is exact for the analytic profile; the bump
    modes' K_q diagonal is estimated as ω_bump² m_bump with a stiff
    placeholder ω. Off-diagonals are computed numerically.

    Returns the raw constructor arguments for `ReducedSupport`.
    """
    if contact_zone_centers is None:
        contact_zone_centers = [(0.0, 0.0)]

    L = float(length)
    W = float(width)
    h_t = float(thickness)
    E = float(youngs)
    nu = float(poisson)
    rho = float(density)

    # Plate flexural rigidity (per-unit-width Euler-Bernoulli analog).
    D_flex = E * h_t ** 3 / (12.0 * (1.0 - nu * nu))
    mu_area = rho * h_t   # mass per unit area

    # Surface sample grid.
    xs = np.linspace(-L / 2.0, L / 2.0, n_grid_x)
    zs = np.linspace(-W / 2.0, W / 2.0, n_grid_z)
    XX, ZZ = np.meshgrid(xs, zs, indexing="ij")
    n_pts = n_grid_x * n_grid_z
    pos = np.zeros((n_pts, 3), dtype=np.float64)
    pos[:, 0] = XX.ravel()
    pos[:, 1] = y_rest
    pos[:, 2] = ZZ.ravel()
    normals = np.zeros_like(pos)
    normals[:, 1] = 1.0  # outward normal +ŷ everywhere

    # ---- Bending mode shapes (clamped-clamped beam in x, flat in z) ----
    # Shape: phi_n(x) = sin(n π (x + L/2) / L). Mass-normalized so
    # ∫ phi_n² μ_area · W dx ≈ μ_area · W · L / 2  (for a sine on [0, L]).
    # We work with the raw sin and let the quadrature compute M_q below.
    omega_global = np.zeros(n_modes_global, dtype=np.float64)
    bending_y_grid = np.zeros((n_pts, n_modes_global), dtype=np.float64)
    for n in range(n_modes_global):
        kx = (n + 1) * np.pi / L
        phi = np.sin(kx * (pos[:, 0] + L / 2.0))
        # Free in z → constant in z. (Hold dependence flat for v1.)
        bending_y_grid[:, n] = phi
        omega_global[n] = kx * kx * np.sqrt(D_flex / mu_area)  # ω_n

    # ---- Local Gaussian-bump shapes ----
    bump_y_grid = np.zeros((n_pts, n_modes_local), dtype=np.float64)
    bump_zones: list[tuple[float, float]] = []
    if n_modes_local > 0:
        bump_zones = _place_contact_zones(L, n_modes_local, contact_zone_centers)
        sigma = float(contact_zone_sigma)
        sigma2 = sigma * sigma
        for j, (xc, zc) in enumerate(bump_zones):
            r2 = (pos[:, 0] - xc) ** 2 + (pos[:, 2] - zc) ** 2
            bump_y_grid[:, j] = np.exp(-0.5 * r2 / sigma2)

    # Stack into a single basis: [global (oscillators), local (static)].
    r_modal = int(n_modes_global)
    r_total = int(n_modes_global + n_modes_local)
    U_y_grid = np.zeros((n_pts, r_total), dtype=np.float64)
    U_y_grid[:, :n_modes_global] = bending_y_grid
    if n_modes_local > 0:
        U_y_grid[:, n_modes_global:] = bump_y_grid

    # Quadrature weights for midpoint rule over the grid.
    dx = L / n_grid_x
    dz = W / n_grid_z
    dA = dx * dz
    weights = np.full(n_pts, dA, dtype=np.float64)

    # Reduced matrices by direct numerical inner product.
    # M_q[i,j] = ∫∫ Φ_i Φ_j μ_area dA ≈ Σ_p w_p · Φ_i(p) · Φ_j(p) · μ_area
    Mq = (U_y_grid.T * (weights * mu_area)) @ U_y_grid
    Mq = 0.5 * (Mq + Mq.T)   # numerical symmetrization

    # K_q for the global bending modes is diagonal with entries
    #   K_nn = m_nn · ω_n²   (Euler-Bernoulli, analytic)
    # For the bump modes we put a stiff but finite placeholder, and we
    # compute off-diagonals numerically by quadrature with a smoothed-
    # second-derivative approximation. For v1 we use a much simpler form:
    # K_q = block_diag(K_bend, K_bump) with K_bump = κ · M_q[bump,bump],
    # where κ = ω_bump² is a tunable stiffness chosen so the bump modes
    # respond stiffly and are dominated by global modes at low frequency.
    Kq = np.zeros_like(Mq)
    # Bending block.
    for n in range(n_modes_global):
        Kq[n, n] = Mq[n, n] * (omega_global[n] ** 2)
    # Bump block: κ · M_bump,bump (high stiffness, no oscillation in v1).
    if n_modes_local > 0:
        # Pick the bump stiffness so its "frequency" is well above the
        # macro time step → quasi-static behavior. 10× the highest
        # bending ω is more than enough.
        omega_bump = 10.0 * float(omega_global.max())
        kappa = omega_bump ** 2
        Kq[n_modes_global:, n_modes_global:] = (
            kappa * Mq[n_modes_global:, n_modes_global:])
    Kq = 0.5 * (Kq + Kq.T)

    # Rayleigh damping: D = α₀ M + α₁ K (§15).
    Dq = rayleigh_alpha0 * Mq + rayleigh_alpha1 * Kq

    # Modal impedance scaling (demo knob).
    #   (Mq, Kq, Dq) ← (Mq, Kq, Dq) / s   where s = 1/g
    # ω_i = √(Kq[i,i] / Mq[i,i]) is exactly invariant (uniform divide
    # cancels). ζ_i = Dq[i,i] / (2·√(Kq[i,i]·Mq[i,i])) is also invariant.
    # Only the displacement-compliance S_h and velocity-gain T_h scale
    # by g = 1/s. See tests/avbd/test_modal_impedance_scaling.py.
    if modal_impedance_scale != 1.0:
        inv_s = 1.0 / float(modal_impedance_scale)
        Mq = Mq * inv_s
        Kq = Kq * inv_s
        Dq = Dq * inv_s
    # Modal damping scaling (independent knob): scales Dq only, so ζ
    # scales linearly while ω is unchanged.
    if modal_damping_scale != 1.0:
        Dq = Dq * float(modal_damping_scale)

    # ξ_j for the modal oscillators.
    zeta = np.zeros(r_modal, dtype=np.float64)
    for j in range(r_modal):
        if omega_global[j] > 1e-12:
            zeta[j] = 0.5 * (rayleigh_alpha0 / omega_global[j]
                             + rayleigh_alpha1 * omega_global[j])
    if modal_damping_scale != 1.0:
        zeta = zeta * float(modal_damping_scale)
    zeta = np.clip(zeta, 0.0, 0.9999)

    # ---- Eigenbasis projection (foundation §16 of the eigenbasis
    # spec). Solve K_q V = M_q V Ω² with V^T M_q V = I, then transform
    # U_y_grid, M_q, K_q, D_q into the eigen-coordinates. Each reduced
    # coordinate becomes an independent damped oscillator. The
    # synthetic basis is preserved when to_eigenbasis=False so the
    # legacy path is bit-exact.
    if to_eigenbasis:
        from scipy.linalg import eigh
        Mq_sym = 0.5 * (Mq + Mq.T)
        Kq_sym = 0.5 * (Kq + Kq.T)
        evals, V = eigh(Kq_sym, Mq_sym)
        omega_sq_full = np.maximum(evals, 0.0)
        eigen_omegas = np.sqrt(omega_sq_full)
        # Project the surface basis into eigen-coords:  Û = U · V.
        U_y_grid = U_y_grid @ V
        # Replace dense matrices with their diagonal eigen forms.
        Mq_proj = np.eye(r_total)
        Kq_proj = np.diag(omega_sq_full)
        # Rayleigh damping closed form (spec §5):
        #   D̂_i = α₀ + α₁ · ω_i²  ⇒  ζ_i = (α₀/ω_i + α₁·ω_i)/2
        damp_diag = (rayleigh_alpha0
                     + rayleigh_alpha1 * omega_sq_full)
        # Modal impedance scale was ALREADY applied to (Mq, Kq, Dq)
        # uniformly above (one-shot divide by s = 1/modal_impedance_scale).
        # That uniform scale survives projection: V^T (Mq/s) V = I/s,
        # V^T (Kq/s) V = Ω²/s. So bake it in here.
        s = (1.0 / float(modal_impedance_scale)
             if modal_impedance_scale != 1.0 else 1.0)
        Mq_proj = Mq_proj * s
        Kq_proj = Kq_proj * s
        damp_diag = damp_diag * s
        # Modal damping scale (already applied as a one-shot * scale on
        # Dq above; the diagonal damp_diag matches the same intent).
        if modal_damping_scale != 1.0:
            damp_diag = damp_diag * float(modal_damping_scale)
        Dq_proj = np.diag(damp_diag)
        # Re-derive zetas in the eigen basis (all r modes now).
        eigen_zetas = np.zeros(r_total, dtype=np.float64)
        for i in range(r_total):
            if eigen_omegas[i] > 1e-12:
                # ζ_i = D̂_i / (2 · m̂_i · ω_i) with m̂_i = 1 after impedance scale.
                eigen_zetas[i] = damp_diag[i] / (2.0 * Mq_proj[i, i] * eigen_omegas[i])
        eigen_zetas = np.clip(eigen_zetas, 0.0, 0.9999)
        # Sanity: V^T M_q V ≈ I/s.
        ortho_err = np.linalg.norm(V.T @ Mq_sym @ V - np.eye(r_total))
        if ortho_err > 1e-7:
            raise RuntimeError(
                f"Eigenbasis projection failed mass-orthonormality "
                f"check: ‖V^T M_q V − I‖ = {ortho_err:.3e}")
        Mq = Mq_proj
        Kq = Kq_proj
        Dq = Dq_proj
        is_eigenbasis = True
        eigen_V = V
    else:
        is_eigenbasis = False
        eigen_V = np.eye(r_total)
        # In the synthetic basis the per-mode ω/ζ are only well-defined
        # for the first r_modal columns. Pad with zeros for the rest so
        # the dataclass field has consistent shape (r,).
        eigen_omegas = np.zeros(r_total, dtype=np.float64)
        eigen_omegas[:r_modal] = omega_global
        eigen_zetas = np.zeros(r_total, dtype=np.float64)
        eigen_zetas[:r_modal] = zeta

    # U_points: (n_pts, 3, r). Only the y-row is populated.
    U_points = np.zeros((n_pts, 3, r_total), dtype=np.float64)
    U_points[:, 1, :] = U_y_grid

    return (pos, normals, U_points, Mq, Kq, Dq,
            r_modal, omega_global, zeta, bump_zones,
            is_eigenbasis, eigen_V, eigen_omegas, eigen_zetas)


def make_debug_reduced_shelf_support(
    *,
    length: float = 0.30,
    width: float = 0.15,
    thickness: float = 0.005,
    youngs: float = 2.0e11,
    density: float = 7850.0,
    poisson: float = 0.30,
    n_modes_global: int = 8,
    n_modes_local: int = 8,
    contact_zone_centers: list[tuple[float, float]] | None = None,
    probe_xz: list[tuple[float, float]] | None = None,
    y_rest: float = 0.0,
    overlay_enabled: bool = True,
    restart_overlay_each_step: bool = True,
    rayleigh_alpha0: float = 0.0,
    rayleigh_alpha1: float = 5.0e-6,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = False,
) -> ReducedSupport:
    """Convenience: synthetic shelf + probe placement → ReducedSupport.

    `probe_xz` are (x, z) locations on the shelf where distant rigid
    bodies will be parked. Their AVBD body indices are filled in later
    by the scene script (set `rs.probe_body_indices` after `add_box`).
    """
    (pos, normals, U_points, Mq, Kq, Dq,
     r_modal, omega, zeta, bump_zones,
     is_eigenbasis, eigen_V, eigen_omegas, eigen_zetas
     ) = make_synthetic_modal_basis_for_shelf(
        length=length, width=width, thickness=thickness,
        youngs=youngs, density=density, poisson=poisson,
        n_modes_global=n_modes_global, n_modes_local=n_modes_local,
        contact_zone_centers=contact_zone_centers, y_rest=y_rest,
        rayleigh_alpha0=rayleigh_alpha0, rayleigh_alpha1=rayleigh_alpha1,
        modal_impedance_scale=modal_impedance_scale,
        modal_damping_scale=modal_damping_scale,
        to_eigenbasis=to_eigenbasis,
    )
    r_total = U_points.shape[2]

    if probe_xz is None:
        probe_xz = [
            (-0.40 * length, 0.0),
            (+0.40 * length, 0.0),
        ]
    probe_points = np.zeros((len(probe_xz), 3), dtype=np.float64)
    probe_normals = np.zeros_like(probe_points)
    probe_U = np.zeros((len(probe_xz), 3, r_total), dtype=np.float64)
    for i, (xp, zp) in enumerate(probe_xz):
        probe_points[i, 0] = xp
        probe_points[i, 1] = y_rest
        probe_points[i, 2] = zp
        probe_normals[i, 1] = 1.0
        # Evaluate U at the probe point by analytic formula (same shapes
        # as the grid). Reuse the same bending / bump definitions.
        for n in range(n_modes_global):
            kx = (n + 1) * np.pi / length
            probe_U[i, 1, n] = np.sin(kx * (xp + length / 2.0))
        # Use the SAME zone list the basis builder did (already deduped
        # and padded). This keeps probe_U analytically consistent with
        # U_points so the overlay's d_max matches what the q-block sees.
        if n_modes_local > 0:
            sigma = 0.03
            for j, (xc, zc) in enumerate(bump_zones):
                r2 = (xp - xc) ** 2 + (zp - zc) ** 2
                probe_U[i, 1, n_modes_global + j] = np.exp(-0.5 * r2 / (sigma * sigma))

    # probe_U above was built in the SYNTHETIC basis. If the support is
    # in the eigenbasis, project it through V too:  Û_probe = Φ_probe·V.
    # That keeps overlay/jump-gain diagnostics that read U_y·q invariant
    # under the basis change (foundation §7 of the eigenbasis spec).
    if is_eigenbasis:
        probe_U[:, 1, :] = probe_U[:, 1, :] @ eigen_V

    rs = ReducedSupport(
        point_positions_rest=pos,
        point_normals_rest=normals,
        U_points=U_points,
        Mq=Mq, Kq=Kq, Dq=Dq,
        q=np.zeros(r_total, dtype=np.float64),
        qdot=np.zeros(r_total, dtype=np.float64),
        q_prev_macro=np.zeros(r_total, dtype=np.float64),
        q_hat=np.zeros(r_total, dtype=np.float64),
        r_modal=r_modal,
        modal_omega=omega,
        modal_zeta=zeta,
        probe_points=probe_points,
        probe_normals=probe_normals,
        probe_U=probe_U,
        probe_body_indices=[],   # caller fills this after add_box
        is_eigenbasis=is_eigenbasis,
        eigen_V=eigen_V,
        eigen_omegas=eigen_omegas,
        eigen_zetas=eigen_zetas,
        overlay_enabled=overlay_enabled,
        restart_overlay_each_step=restart_overlay_each_step,
    )
    return rs


# ---------------------------------------------------------------------------
# Basis evaluation at arbitrary points (linear interpolation on the grid)
# ---------------------------------------------------------------------------

def evaluate_basis_at_point(
    rs: ReducedSupport,
    point_xz: tuple[float, float],
    *,
    length: float,
    width: float,
    n_grid_x: int,
    n_grid_z: int,
) -> NDArray[np.float64]:
    """Evaluate U at a world (x, z) using bilinear interpolation on the
    sample grid the basis was built from. Returns (3, r). Caller passes
    in the grid metadata explicitly so this remains stateless.

    Used by the iteration hook to look up `U_y(x_contact)` when a contact
    sits between sample points. The shelf scene currently parks contact
    corners at integer multiples of the grid spacing so this falls back
    to a vertex evaluation in practice, but bilinear is the right default.
    """
    x, z = float(point_xz[0]), float(point_xz[1])
    # Map (x, z) to grid index space.
    fx = (x + length / 2.0) / length * (n_grid_x - 1)
    fz = (z + width / 2.0) / width * (n_grid_z - 1)
    ix = int(np.clip(np.floor(fx), 0, n_grid_x - 2))
    iz = int(np.clip(np.floor(fz), 0, n_grid_z - 2))
    tx = float(np.clip(fx - ix, 0.0, 1.0))
    tz = float(np.clip(fz - iz, 0.0, 1.0))

    def _idx(i: int, k: int) -> int:
        return i * n_grid_z + k

    u00 = rs.U_points[_idx(ix, iz)]
    u10 = rs.U_points[_idx(ix + 1, iz)]
    u01 = rs.U_points[_idx(ix, iz + 1)]
    u11 = rs.U_points[_idx(ix + 1, iz + 1)]
    return ((1 - tx) * (1 - tz) * u00 + tx * (1 - tz) * u10
            + (1 - tx) * tz * u01 + tx * tz * u11)
