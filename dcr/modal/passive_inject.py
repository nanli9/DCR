"""Passive modal energy injection (Stages E1-E3).

Foundation §4 (projection), §6 (alpha cap), §7 (kick),
§15 (core inequality: dE_modal <= eta * dE_rigid_loss).
See passive_energy_injection_implementation_prompt.md E1-E3.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh
from ..dcr.modal_dcr import _closest_point_on_triangle


def eval_basis_at_point(
    point: NDArray[np.float64],
    surface: TriMesh,
    U_surf: NDArray[np.float64],
    surface_vertex_indices: NDArray[np.int32],
    vert_to_surf_idx: NDArray[np.int32],
) -> NDArray[np.float64]:
    """Evaluate the modal basis Phi(x_c) at a world point (foundation §4).

    Locates the closest surface triangle, computes barycentric weights,
    and interpolates the surface-restricted mode basis U_surf.

    Args:
        point: (3,) world-space contact point on the elastic surface.
        surface: Surface triangle mesh.
        U_surf: (3*n_surf, n_modes) surface-restricted eigenvector matrix.
        surface_vertex_indices: (n_surf,) global vertex indices of surface nodes.
        vert_to_surf_idx: (n_verts,) maps global vertex → surface index (-1 if not surface).

    Returns:
        Phi_x: (3, n_modes) modal basis evaluated at the contact point.
    """
    verts = surface.vertices
    faces = surface.faces
    n_modes = U_surf.shape[1]

    # Find closest triangle (brute force, fine for small meshes).
    best_dist = np.inf
    best_tri = 0
    best_bary = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])

    for fi in range(faces.shape[0]):
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

    for k in range(3):
        vert_global = face[k]
        surf_idx = vert_to_surf_idx[vert_global]
        if surf_idx < 0:
            continue  # Fixed boundary node
        row_start = 3 * surf_idx
        U_i = U_surf[row_start:row_start + 3, :]  # (3, n_modes)
        Phi_x += best_bary[k] * U_i

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
