"""Contact-compatible null-space projection for the DCR patch kick.

Implements `prompts/dcr_patch_kick_nullspace_projection_fix.md` §6-9 in
impulse space — mathematically equivalent to the doc's 6D M-metric
formulation but composes cleanly with the existing impulse-space
passivity (`patch_passive_scaling`) and dissipativity (back-reaction
γ guard) machinery.

# DEVIATION (DCR paper §9 single-centroid patch kick): the §9 formulation
# applies the modal velocity as a point impulse at the patch CENTROID.
# For a thin body in flat resting contact the lever × tangential impulse
# becomes torque (Δω = I⁻¹·(r̄ × λ)) the body cannot resist — visible as
# fork roll/pitch on the dinner_table scene. This module zeroes the
# DIFFERENTIAL normal velocity across patch sample points, the right
# resting-contact constraint, while preserving DCR energy transfer.
# Foundation §15 passivity bound is preserved because the K_body-metric
# projection is energy-non-increasing.

Math: per fix-doc §6, the constraint that all patch sample points share
the patch's mean normal velocity is

    nᵀ · (J_i − J̄) · Δu = 0  for each sample i,

where Δu = [Δv_lin; Δω] is the body's generalized velocity increment.
Expanded:  nᵀ · (Δω × Δr_i) = Δω · (n × Δr_i) where Δr_i = r_i − r_mean.

For a centroid-applied point impulse λ, Δu = L·λ with

    L = [  I/m          ]   (3×3, top)
        [I⁻¹ · [r̄]_×  ]   (3×3, bottom)

so the constraint pulls back to D_λ · λ = 0 with D_λ = D · L (K × 3).
The K_body-metric projection of λ onto the null-space is closed form:

    λ_proj = λ − K_inv · D_λᵀ · (D_λ · K_inv · D_λᵀ + ε·I)⁻¹ · D_λ · λ.

Energy-preservation: ½·λᵀ·K_body·λ is exactly the rigid-body kinetic-
energy increment under impulse λ at lever r̄, and the projection is
non-increasing in this metric. The §9.6 passivity scaling then operates
on the projected λ as before.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..rigid.body import Shape, ShapeType


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _skew(v: NDArray[np.float64]) -> NDArray[np.float64]:
    """3x3 skew matrix such that `[v]_× · a = v × a`."""
    vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
    return np.array([
        [0.0, -vz,  vy],
        [ vz, 0.0, -vx],
        [-vy,  vx, 0.0],
    ], dtype=np.float64)


def _K_body(
    mass: float,
    r_bar: NDArray[np.float64],
    inertia_world_inv: NDArray[np.float64],
) -> NDArray[np.float64]:
    """3x3 contact-point effective-mass matrix `K = (1/m)·I + [r̄]_× · I⁻¹ · [r̄]_×ᵀ`."""
    R = _skew(r_bar)
    return (1.0 / mass) * np.eye(3) + R @ inertia_world_inv @ R.T


def _impulse_to_du_map(
    mass: float,
    r_bar: NDArray[np.float64],
    inertia_world_inv: NDArray[np.float64],
) -> NDArray[np.float64]:
    """6x3 mapping `L: λ ↦ Δu = [Δv_lin; Δω]` for a centroid point impulse."""
    L = np.zeros((6, 3), dtype=np.float64)
    L[0:3, :] = (1.0 / mass) * np.eye(3)
    L[3:6, :] = inertia_world_inv @ _skew(r_bar)
    return L


# ---------------------------------------------------------------------- #
# Projection
# ---------------------------------------------------------------------- #


def project_patch_impulse_contact_compatible(
    lam: NDArray[np.float64],
    *,
    patch_points: NDArray[np.float64],
    r_bar: NDArray[np.float64],
    com_world: NDArray[np.float64],
    normal: NDArray[np.float64],
    tangents: tuple[NDArray[np.float64], NDArray[np.float64]] | None,
    mass: float,
    inertia_world_inv: NDArray[np.float64],
    tangent_weight: float = 0.25,
    eps: float = 1e-7,
) -> tuple[NDArray[np.float64], float]:
    """K_body-metric impulse-space projection (fix-doc §6-9, foundation §15).

    Returns `(lam_proj, rho)` with rho = `√(λ_projᵀ·K·λ_proj / λᵀ·K·λ)` —
    the energy-retention ratio in K_body-metric. rho ≈ 1 means the raw
    kick was already contact-compatible; rho « 1 means most of the kick
    was spurious twist that the projection removed.
    """
    N = int(patch_points.shape[0])
    if N < 2:
        return lam.copy(), 1.0

    n = np.asarray(normal, dtype=np.float64)
    n_mag = float(np.linalg.norm(n))
    if n_mag < 1e-30:
        return lam.copy(), 1.0
    n = n / n_mag

    # Differential lever Δr_i = r_i − r_mean for the sample points (the
    # constraint depends only on the DIFFERENCE, not on the absolute COM
    # offset — see fix-doc §5-§6).
    levers = patch_points - com_world  # (N, 3)
    lever_mean = levers.mean(axis=0)
    dr = levers - lever_mean           # (N, 3)

    # Constraint rows in 6D velocity space:
    #   row · Δu = Δω · (axis × Δr_i)
    # with axis ∈ {n, √w_t · t_1, √w_t · t_2}. Linear part is zero (the
    # I block of J_i − J̄ vanishes); only the angular part carries the
    # constraint.
    rows: list[NDArray[np.float64]] = []
    for i in range(N):
        row = np.zeros(6, dtype=np.float64)
        row[3:6] = np.cross(n, dr[i])
        rows.append(row)
    if tangents is not None:
        t1_raw, t2_raw = tangents
        t1 = np.asarray(t1_raw, dtype=np.float64)
        t2 = np.asarray(t2_raw, dtype=np.float64)
        t1 = t1 / max(float(np.linalg.norm(t1)), 1e-30)
        t2 = t2 / max(float(np.linalg.norm(t2)), 1e-30)
        wt = float(np.sqrt(max(0.0, tangent_weight)))
        for t in (t1, t2):
            for i in range(N):
                row = np.zeros(6, dtype=np.float64)
                row[3:6] = wt * np.cross(t, dr[i])
                rows.append(row)
    D = np.stack(rows, axis=0)  # (K, 6)

    # Pull back to impulse coordinates via L.
    L = _impulse_to_du_map(mass, r_bar, inertia_world_inv)  # (6, 3)
    D_lam = D @ L                                            # (K, 3)

    # K_body-metric closed-form projection on the impulse.
    K = _K_body(mass, r_bar, inertia_world_inv)  # (3, 3)
    K_inv = np.linalg.inv(K)
    A = D_lam @ K_inv @ D_lam.T + eps * np.eye(D_lam.shape[0])
    b = D_lam @ lam
    correction = K_inv @ D_lam.T @ np.linalg.solve(A, b)
    lam_proj = lam - correction

    # Retention ratio in K_body-metric (= √(2·ΔKE_post / 2·ΔKE_pre)).
    e_pre = float(lam @ K @ lam)
    e_post = float(lam_proj @ K @ lam_proj)
    if e_pre <= 1e-30:
        rho = 1.0
    else:
        rho = float(np.sqrt(max(0.0, e_post) / e_pre))
    return lam_proj, rho


# ---------------------------------------------------------------------- #
# 6D velocity-increment projection (fix-doc §4-8, preserves yaw)
# ---------------------------------------------------------------------- #


def project_du_contact_compatible(
    du_raw: NDArray[np.float64],
    *,
    patch_points: NDArray[np.float64],
    com_world: NDArray[np.float64],
    normal: NDArray[np.float64],
    tangents: tuple[NDArray[np.float64], NDArray[np.float64]] | None,
    mass: float,
    inertia_world: NDArray[np.float64],
    tangent_weight: float = 0.25,
    eps: float = 1e-7,
) -> tuple[NDArray[np.float64], float]:
    """M-metric 6D null-space projection on the velocity increment.

    Constraint (fix-doc §6): `nᵀ · (J_i − J̄) · Δu = 0` for each sample i.
    Expanded: `n · (Δω × Δr_i) = Δω · (n × Δr_i) = 0`. The constraint
    rows D have zero linear block and `(n × Δr_i)` in the angular block,
    so the projection ONLY modifies the angular part — the linear
    velocity increment Δv is preserved exactly. This is the
    important advantage over the impulse-space form: a thin body can
    still receive both LINEAR push (any direction) AND YAW (rotation
    about n), since yaw lies in the constraint null-space. Only
    roll/pitch — which lift one end of the patch out of contact — get
    suppressed.

    Mass-metric projection:
        Δu_proj = Δu_raw − M⁻¹ · Dᵀ · (D · M⁻¹ · Dᵀ + ε·I)⁻¹ · D · Δu_raw,
    with M = diag(m·I, I_world). Energy non-increasing in ½·ΔuᵀMΔu.

    Args:
        du_raw: (6,) [Δv_lin (3); Δω (3)] velocity increment to project.
        patch_points: (N, 3) world-space sample points (≥3).
        com_world: (3,) body COM in world frame.
        normal: (3,) unit contact normal.
        tangents: optional (t1, t2) for tangent rows; suppresses yaw.
        mass: receiver body mass.
        inertia_world: (3, 3) world-frame inertia tensor.
        tangent_weight: w_t in fix-doc §7.
        eps: Tikhonov regulariser.

    Returns:
        (du_proj, rho) where rho = √(Δu_projᵀ M Δu_proj / Δu_rawᵀ M Δu_raw).
    """
    N = int(patch_points.shape[0])
    if N < 2:
        return du_raw.copy(), 1.0

    n = np.asarray(normal, dtype=np.float64)
    n_mag = float(np.linalg.norm(n))
    if n_mag < 1e-30:
        return du_raw.copy(), 1.0
    n = n / n_mag

    levers = patch_points - com_world  # (N, 3)
    lever_mean = levers.mean(axis=0)
    dr = levers - lever_mean           # (N, 3)

    rows: list[NDArray[np.float64]] = []
    for i in range(N):
        row = np.zeros(6, dtype=np.float64)
        row[3:6] = np.cross(n, dr[i])
        rows.append(row)
    if tangents is not None:
        t1_raw, t2_raw = tangents
        t1 = np.asarray(t1_raw, dtype=np.float64)
        t2 = np.asarray(t2_raw, dtype=np.float64)
        t1 = t1 / max(float(np.linalg.norm(t1)), 1e-30)
        t2 = t2 / max(float(np.linalg.norm(t2)), 1e-30)
        wt = float(np.sqrt(max(0.0, tangent_weight)))
        for t in (t1, t2):
            for i in range(N):
                row = np.zeros(6, dtype=np.float64)
                row[3:6] = wt * np.cross(t, dr[i])
                rows.append(row)
    D = np.stack(rows, axis=0)  # (K, 6)

    # M_inv = diag((1/m) I, I_inv).
    I_inv = np.linalg.inv(inertia_world)
    M_inv = np.zeros((6, 6), dtype=np.float64)
    M_inv[0:3, 0:3] = (1.0 / mass) * np.eye(3)
    M_inv[3:6, 3:6] = I_inv

    A = D @ M_inv @ D.T + eps * np.eye(D.shape[0])  # (K, K)
    b = D @ du_raw                                   # (K,)
    correction = M_inv @ D.T @ np.linalg.solve(A, b)
    du_proj = du_raw - correction

    # Retention ratio in M-metric.
    M = np.zeros((6, 6), dtype=np.float64)
    M[0:3, 0:3] = mass * np.eye(3)
    M[3:6, 3:6] = inertia_world
    e_pre = float(du_raw @ M @ du_raw)
    e_post = float(du_proj @ M @ du_proj)
    if e_pre <= 1e-30:
        rho = 1.0
    else:
        rho = float(np.sqrt(max(0.0, e_post) / e_pre))
    return du_proj, rho


# ---------------------------------------------------------------------- #
# Gating (fix-doc §11)
# ---------------------------------------------------------------------- #


def should_project_patch(
    body_shape: Shape,
    rotation_matrix: NDArray[np.float64],
    n_contact_points: int,
    v_p_at_centroid: NDArray[np.float64],
    normal: NDArray[np.float64],
    *,
    thin_ratio: float = 0.25,
    v_n_thresh: float = 0.05,
    v_t_thresh: float = 0.10,
    use_tangent_rows: bool = False,
) -> tuple[bool, bool]:
    """Gate per fix-doc §11. Returns (project, tangent_for_this_patch).

    Orientation-aware: projects the contact normal into the body frame
    (R^T·n) and uses the half-extent along the dominant body axis as
    `h_normal`. The other two half-extents give `h_lat`. The thin-body
    rule is `h_normal / max(h_lat) < thin_ratio`. This keeps the gate
    correct under body rotation — a fork rolled onto its side stops
    counting as "thin", and a tall pillar is excluded regardless of
    which face touches the surface.
    """
    if body_shape.kind is not ShapeType.BOX:
        return False, False
    # N=2 is a line / edge contact — the constraint becomes rank-1 (rolls
    # perpendicular to the line are still suppressed; the parallel-to-
    # line roll is allowed, which is the legitimate edge-tipping mode).
    # Bailing at N<3 (fix-doc §11) leaks angular kicks during transient
    # corner-lift events on the dinner_table scene.
    if n_contact_points < 2:
        return False, False
    half = np.asarray(body_shape.half_extents, dtype=np.float64)
    if half.shape != (3,):
        return False, False
    n_world = np.asarray(normal, dtype=np.float64)
    n_mag = float(np.linalg.norm(n_world))
    if n_mag < 1e-30:
        return False, False
    n_world = n_world / n_mag
    n_body = rotation_matrix.T @ n_world
    k = int(np.argmax(np.abs(n_body)))
    h_n = float(half[k])
    h_lat = float(max(half[(k + 1) % 3], half[(k + 2) % 3]))
    if h_lat <= 0.0:
        return False, False
    if h_n / h_lat >= thin_ratio:
        return False, False
    v = np.asarray(v_p_at_centroid, dtype=np.float64)
    v_n = float(abs(v @ n_world))
    if v_n > v_n_thresh:
        return False, False
    if use_tangent_rows:
        v_t_vec = v - (v @ n_world) * n_world
        v_t = float(np.linalg.norm(v_t_vec))
        return True, (v_t <= v_t_thresh)
    return True, False
