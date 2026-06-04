"""Passive modal energy injection (Stages E1-E3).

Foundation §4 (projection), §6 (alpha cap), §7 (kick),
§15 (core inequality: dE_modal <= eta * dE_rigid_loss).
See passive_energy_injection_implementation_prompt.md E1-E3.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh


def _closest_point_on_triangle(
    p: NDArray[np.float64],
    v0: NDArray[np.float64],
    v1: NDArray[np.float64],
    v2: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Closest point on triangle (v0, v1, v2) to point p.

    Returns (closest_point, barycentric_coords).
    Uses the Voronoi region method (Real-Time Collision Detection, §5.1.5).
    Duplicated from dcr.dcr.modal_dcr to avoid circular imports.
    """
    ab = v1 - v0
    ac = v2 - v0
    ap = p - v0

    d1 = np.dot(ab, ap)
    d2 = np.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return v0.copy(), np.array([1.0, 0.0, 0.0])

    bp = p - v1
    d3 = np.dot(ab, bp)
    d4 = np.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return v1.copy(), np.array([0.0, 1.0, 0.0])

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return v0 + v * ab, np.array([1.0 - v, v, 0.0])

    cp = p - v2
    d5 = np.dot(ab, cp)
    d6 = np.dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return v2.copy(), np.array([0.0, 0.0, 1.0])

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return v0 + w * ac, np.array([1.0 - w, 0.0, w])

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return v1 + w * (v2 - v1), np.array([0.0, 1.0 - w, w])

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return v0 + v * ab + w * ac, np.array([1.0 - v - w, v, w])


def _get_or_build_tri_kdtree(surface: TriMesh):
    """Lazily build (and cache on the TriMesh) a scipy.cKDTree over
    triangle centroids. Replaces the O(n_tri) brute-force scan in
    eval_basis_at_point with an O(log n_tri) query.

    Cached attribute names:
        surface._tri_kdtree    : cKDTree (None if scipy is missing)
        surface._tri_centroids : (n_tri, 3) cached centroid array
    """
    cached = getattr(surface, "_tri_kdtree", None)
    if cached is not None:
        return cached, surface._tri_centroids
    try:
        from scipy.spatial import cKDTree  # noqa: WPS433
    except Exception:
        surface._tri_kdtree = False  # poison marker
        surface._tri_centroids = None
        return False, None
    verts = surface.vertices
    faces = surface.faces
    centroids = (
        verts[faces[:, 0]] + verts[faces[:, 1]] + verts[faces[:, 2]]
    ) / 3.0
    tree = cKDTree(centroids)
    surface._tri_kdtree = tree
    surface._tri_centroids = centroids
    return tree, centroids


def eval_basis_at_point(
    point: NDArray[np.float64],
    surface: TriMesh,
    U_surf: NDArray[np.float64],
    surface_vertex_indices: NDArray[np.int32],
    vert_to_surf_idx: NDArray[np.int32],
    k_candidates: int = 8,
) -> NDArray[np.float64]:
    """Evaluate the modal basis Phi(x_c) at a world point (foundation §4).

    Locates the closest surface triangle, computes barycentric weights,
    and interpolates the surface-restricted mode basis U_surf.

    Uses a cKDTree over triangle centroids (lazily built on `surface`)
    to narrow the search to the `k_candidates` nearest triangles, then
    runs the exact Voronoi-region closest-point computation on each.
    For typical slab meshes (~hundreds of triangles) this cuts the
    inner loop from O(n_tri) to O(k) per call.

    Args:
        point: (3,) world-space contact point on the elastic surface.
        surface: Surface triangle mesh.
        U_surf: (3*n_surf, n_modes) surface-restricted eigenvector matrix.
        surface_vertex_indices: (n_surf,) global vertex indices of surface nodes.
        vert_to_surf_idx: (n_verts,) maps global vertex → surface index (-1 if not surface).
        k_candidates: How many nearest-centroid candidate triangles to
            check with the exact closest-point routine. 8 is enough for
            structured tet-slab meshes; raise if the mesh has slivers.

    Returns:
        Phi_x: (3, n_modes) modal basis evaluated at the contact point.
    """
    verts = surface.vertices
    faces = surface.faces
    n_modes = U_surf.shape[1]

    tree, _ = _get_or_build_tri_kdtree(surface)
    if tree is False:
        # scipy unavailable — fall back to brute force.
        candidate_tris = range(faces.shape[0])
    else:
        k = min(k_candidates, faces.shape[0])
        _, idxs = tree.query(point, k=k)
        candidate_tris = np.atleast_1d(idxs)

    best_dist = np.inf
    best_tri = 0
    best_bary = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])
    for fi in candidate_tris:
        fi = int(fi)
        v0, v1, v2 = verts[faces[fi, 0]], verts[faces[fi, 1]], verts[faces[fi, 2]]
        cp, bary = _closest_point_on_triangle(point, v0, v1, v2)
        d = np.linalg.norm(point - cp)
        if d < best_dist:
            best_dist = d
            best_tri = fi
            best_bary = bary

    # Interpolate mode basis at the contact point.
    face = faces[best_tri]
    Phi_x = np.zeros((3, n_modes), dtype=np.float64)

    for k_v in range(3):
        vert_global = face[k_v]
        surf_idx = vert_to_surf_idx[vert_global]
        if surf_idx < 0:
            continue  # Fixed boundary node
        row_start = 3 * surf_idx
        U_i = U_surf[row_start:row_start + 3, :]  # (3, n_modes)
        Phi_x += best_bary[k_v] * U_i

    return Phi_x


def project_impulse(
    Phi_x: NDArray[np.float64],
    j: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Project a contact impulse onto the modal basis (foundation §4).

    s_c = Phi(x_c)^T j

    # DEVIATION from paper Eq. 9: projects the full impulse vector j (normal +
    # tangential), not just n_c * lambda_N. The result is a modal velocity kick
    # (not a modal force), because mass-normalized modes give M_q = I
    # (foundation §15).

    Args:
        Phi_x: (3, n_modes) modal basis at contact point.
        j: (3,) impulse vector in world frame (normal + tangential components).

    Returns:
        s_c: (n_modes,) modal velocity kick vector.
    """
    return Phi_x.T @ j


def aggregate_kicks(
    kick_list: list[NDArray[np.float64]],
) -> NDArray[np.float64]:
    """Aggregate modal kicks from multiple contacts (foundation §8).

    s_total = sum_k Phi(x_k)^T j_k

    Per elastic body — do not mix s_total across bodies.

    Args:
        kick_list: List of s_c vectors, each (n_modes,).

    Returns:
        s_total: (n_modes,) aggregated modal velocity kick.
    """
    if not kick_list:
        return np.zeros(0, dtype=np.float64)
    return np.sum(kick_list, axis=0)


# ---- Stage E2: passive scaling coefficient α (foundation §6) ----

_EPS_TINY = 1e-18  # Numerical floor for division (default parameter table)


def passive_alpha(
    s: NDArray[np.float64],
    qdot: NDArray[np.float64],
    E_max: float,
) -> float:
    """Passive scaling coefficient (foundation §6, core eq. §15).

    Given the raw modal kick s and current modal velocity qdot, find the
    largest alpha in [0, 1] such that

        dE_modal(alpha) = alpha * b + 0.5 * alpha^2 * a  <=  E_max

    where a = s^T s, b = qdot^T s.

    Edge cases (foundation §6, implementation prompt E2.2):
    - a = 0 (zero impulse): alpha = 0.
    - E_max = 0, dE_full <= 0 (dissipative kick): alpha = 1.
    - b < 0, |b| > 0.5*a: dE_full < 0 → alpha = 1 regardless of E_max.

    Args:
        s: (n_modes,) raw modal velocity kick vector.
        qdot: (n_modes,) current modal velocity.
        E_max: Maximum allowed energy increase (eta * E_loss >= 0).

    Returns:
        alpha: Scaling coefficient in [0, 1].
    """
    a = float(np.dot(s, s))
    b = float(np.dot(qdot, s))

    if a < _EPS_TINY:
        # Zero impulse → no kick.
        return 0.0

    dE_full = b + 0.5 * a  # dE_modal(alpha=1)

    if dE_full <= E_max:
        # Full kick fits in budget (includes dissipative case dE_full < 0).
        return 1.0

    # Quadratic cap: solve alpha*b + 0.5*alpha^2*a = E_max for positive root.
    discr = b * b + 2.0 * a * E_max
    if discr < 0.0:
        # Can happen only if E_max < 0, which shouldn't occur by construction.
        return 0.0

    alpha_star = (-b + np.sqrt(max(0.0, discr))) / a
    return float(np.clip(alpha_star, 0.0, 1.0))


def prescribed_alpha(
    s: NDArray[np.float64],
    qdot: NDArray[np.float64],
    E_target: float,
    alpha_max: float = 100.0,
) -> float:
    """Energy-PRESCRIBED scaling coefficient (foundation §6/§15).

    Where passive_alpha BOUNDS the injection (α ∈ [0, 1], scale down only),
    this TARGETS it: return the α ≥ 0 making

        dE_modal(alpha) = alpha * b + 0.5 * alpha^2 * a = E_target,
            a = s^T s,  b = qdot^T s

    i.e. scale the kick DIRECTION s up OR down so the deposited modal energy is
    exactly E_target (clamped to [0, alpha_max]). This decouples the injected
    MAGNITUDE (from the energy budget E_target) from the raw kick magnitude ‖s‖,
    which a soft low-iteration solve makes tiny and iteration-sensitive, while
    keeping s's DIRECTION (the modal/spectral distribution set by the contact
    geometry).

    # DEVIATION (foundation §15): this treats the passivity inequality
    # dE_modal <= eta * E_rigid_loss as a TARGET, not a ceiling — it synthesizes
    # modal energy the literal contact impulse did not carry, re-sharpening the
    # smeared low-iteration impulse. Global passivity is still enforced upstream:
    # E_target is a fraction of the available budget (η·E_loss, accumulated in the
    # impact reservoir), and the realized dE is debited from that budget, so
    # Σ E_inj ≤ η·Σ E_loss still holds. The injected magnitude is no longer the
    # impulse's literal modal projection (foundation §14: do not overclaim).

    Args:
        s: (n_modes,) raw modal velocity kick; only its direction is kept.
        qdot: (n_modes,) current modal velocity.
        E_target: Modal energy to inject (>= 0; = mu * available budget).
        alpha_max: Upper clamp guarding against amplifying a near-zero (noisy)
            direction into a large kick.

    Returns:
        alpha: Scaling coefficient in [0, alpha_max].
    """
    a = float(np.dot(s, s))
    b = float(np.dot(qdot, s))
    if a < _EPS_TINY or E_target <= 0.0:
        return 0.0
    # Positive root of alpha*b + 0.5*alpha^2*a = E_target (>= 0 for E_target >= 0).
    discr = b * b + 2.0 * a * E_target
    alpha_star = (-b + np.sqrt(max(0.0, discr))) / a
    return float(np.clip(alpha_star, 0.0, alpha_max))
