"""Deformed contact-normal primitive (shared by tilt coupler + Version B).

Computes an approximated *deformed* contact normal n' from the modal
displacement field at the contact point. Extracted from the tilt-coupler
pipeline so both TiltDCRCoupler and the energy-prescribed point-impulse
mode (passive_dcr.py, dcr_velocity_mode="energy_prescribed_point_impulse")
can share the same primitive.

Pipeline (matches the original tilt-coupler steps 3-7):
  1. Find the closest surface triangle to the contact point.
  2. Evaluate the modal basis at the contact point; project along push_dir;
     pick the peak substep q_peak from q_history.
  3. Sample normal displacement at the 3 triangle vertices.
  4. Fit slopes (s1, s2) in the tangent frame via patch fit.
  5. n' = clamp_tilt(normalize(n - s1*t1 - s2*t2), theta_max).

# DEVIATION (foundation §15): the foundation document is silent on the
# deformed-normal approximation -- this is a numerical heuristic from the
# tilt coupler. The energy-prescribed point-impulse mode uses it as the
# direction `u` for its true point impulse. The math of the point impulse
# itself (J, k, ΔKE) is exact given u; only u carries this approximation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh
from ..modal.passive_inject import _closest_point_on_triangle, eval_basis_at_point


# ----------------------------------------------------------------------
# Per-triangle precomputed frames (shared cache)
# ----------------------------------------------------------------------

@dataclass
class SurfaceTangentFrames:
    """Per-face normals + orthonormal tangent vectors for a surface mesh.

    Precomputed once at construction time. Holds three (n_faces, 3) arrays
    keyed by triangle index.
    """
    surface: TriMesh
    tri_normals: NDArray[np.float64] = field(init=False, repr=False)
    tri_tangent_t1: NDArray[np.float64] = field(init=False, repr=False)
    tri_tangent_t2: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        verts = self.surface.vertices
        faces = self.surface.faces
        n_faces = faces.shape[0]
        self.tri_normals = np.zeros((n_faces, 3), dtype=np.float64)
        self.tri_tangent_t1 = np.zeros((n_faces, 3), dtype=np.float64)
        self.tri_tangent_t2 = np.zeros((n_faces, 3), dtype=np.float64)
        for fi in range(n_faces):
            v0 = verts[faces[fi, 0]]
            v1 = verts[faces[fi, 1]]
            v2 = verts[faces[fi, 2]]
            cross = np.cross(v1 - v0, v2 - v0)
            length = np.linalg.norm(cross)
            if length < 1e-14:
                self.tri_normals[fi] = np.array([0.0, 1.0, 0.0])
            else:
                self.tri_normals[fi] = cross / length
            t1, t2 = compute_triangle_tangent_frame(
                v0, v1, v2, self.tri_normals[fi])
            self.tri_tangent_t1[fi] = t1
            self.tri_tangent_t2[fi] = t2


# ----------------------------------------------------------------------
# Pure helpers (unchanged behavior from tilt_dcr.py)
# ----------------------------------------------------------------------

def compute_triangle_tangent_frame(
    v0: NDArray[np.float64],
    v1: NDArray[np.float64],
    v2: NDArray[np.float64],
    n: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Orthonormal tangent frame (t1, t2) for a triangle on its plane.

    t1 = projection of edge (v0->v1) onto the tangent plane, normalized.
    t2 = n x t1.
    """
    e1 = v1 - v0
    e1_t = e1 - np.dot(e1, n) * n
    len_e1 = np.linalg.norm(e1_t)
    if len_e1 < 1e-12:
        if abs(n[0]) < 0.9:
            t1 = np.cross(n, np.array([1.0, 0.0, 0.0]))
        else:
            t1 = np.cross(n, np.array([0.0, 1.0, 0.0]))
        t1 /= np.linalg.norm(t1)
    else:
        t1 = e1_t / len_e1
    t2 = np.cross(n, t1)
    len_t2 = np.linalg.norm(t2)
    if len_t2 < 1e-12:
        return t1, np.zeros(3)
    t2 /= len_t2
    return t1, t2


def compute_patch_fit_slopes(
    w0: float, w1: float, w2: float,
    v0: NDArray[np.float64], v1: NDArray[np.float64], v2: NDArray[np.float64],
    t1: NDArray[np.float64], t2: NDArray[np.float64],
) -> tuple[float, float]:
    """Slopes (s1, s2) of a plane fit through (vi, wi) in the (t1, t2) frame."""
    d1 = v1 - v0
    d2 = v2 - v0
    A = np.array([
        [np.dot(d1, t1), np.dot(d1, t2)],
        [np.dot(d2, t1), np.dot(d2, t2)],
    ])
    b = np.array([w1 - w0, w2 - w0])
    det = A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0]
    if abs(det) < 1e-18:
        return 0.0, 0.0
    s1 = (A[1, 1] * b[0] - A[0, 1] * b[1]) / det
    s2 = (A[0, 0] * b[1] - A[1, 0] * b[0]) / det
    return float(s1), float(s2)


def clamp_normal_angle(
    n_rest: NDArray[np.float64],
    n_target: NDArray[np.float64],
    theta_max: float,
) -> tuple[NDArray[np.float64], float]:
    """Clamp `n_target` to be within `theta_max` radians of `n_rest`.

    If the angle θ = arccos(n_rest · n_target) exceeds `theta_max`, slerp
    (linearly here — small-angle approx) toward `n_target` by the fraction
    `theta_max / θ` and renormalize. Otherwise return `n_target` unchanged.

    Both inputs should be unit vectors; the output is unit by construction.
    Shared between the patch-fit and Barbič-James deformed-normal methods.
    """
    cos_theta = float(np.clip(np.dot(n_rest, n_target), -1.0, 1.0))
    theta = float(np.arccos(cos_theta))
    if theta > theta_max and theta > 1e-12:
        frac = theta_max / theta
        n_clamped = n_rest + frac * (n_target - n_rest)
        n_clamped /= np.linalg.norm(n_clamped)
        return n_clamped, theta_max
    return n_target, theta


def compute_tilted_normal(
    n: NDArray[np.float64],
    s1: float, s2: float,
    t1: NDArray[np.float64], t2: NDArray[np.float64],
    theta_max: float,
) -> tuple[NDArray[np.float64], float]:
    """n' = clamp_to_theta_max(normalize(n - s1*t1 - s2*t2))."""
    n_raw = n - s1 * t1 - s2 * t2
    length = np.linalg.norm(n_raw)
    if length < 1e-12:
        return n.copy(), 0.0
    n_tilt = n_raw / length
    return clamp_normal_angle(n, n_tilt, theta_max)


# ----------------------------------------------------------------------
# Top-level entry point used by callers (tilt + energy-prescribed B)
# ----------------------------------------------------------------------

def compute_deformed_normal(
    contact_point: NDArray[np.float64],
    push_dir: NDArray[np.float64],
    q_history: NDArray[np.float64],
    modal_U_surf: NDArray[np.float64],
    surface_vertex_indices: NDArray[np.int32],
    surface: TriMesh,
    vert_to_surf_idx: NDArray[np.int32],
    tangent_frames: SurfaceTangentFrames,
    theta_max: float,
) -> tuple[NDArray[np.float64], float, int]:
    """Approximated deformed contact normal n' at `contact_point`.

    Args:
        contact_point: (3,) world-space contact point.
        push_dir: (3,) unit normal already oriented FROM elastic TO body.
        q_history: (n_substeps, n_modes) transient modal trajectory.
        modal_U_surf: (3*n_surf_verts, n_modes) surface modal basis.
        surface_vertex_indices: (n_surf_verts,) global→surface mapping.
        surface: TriMesh of the elastic body's surface.
        vert_to_surf_idx: inverse mapping (max_vert,), -1 if not on surface.
        tangent_frames: precomputed per-face frames (shared cache).
        theta_max: clamp for the tilt angle (radians).

    Returns:
        (n_tilt, theta, best_tri): the deformed unit normal, the tilt angle
        in radians, and the index of the chosen triangle (diagnostic).

    When the modal contribution along push_dir is below noise floor
    (n_tilt == push_dir), theta is 0 and the caller may choose to fall
    back to the un-deformed normal.
    """
    verts = surface.vertices
    faces = surface.faces

    # Step 1: closest triangle.
    best_dist = np.inf
    best_tri = 0
    for fi in range(faces.shape[0]):
        v0 = verts[faces[fi, 0]]
        v1 = verts[faces[fi, 1]]
        v2 = verts[faces[fi, 2]]
        cp, _ = _closest_point_on_triangle(contact_point, v0, v1, v2)
        d = float(np.linalg.norm(contact_point - cp))
        if d < best_dist:
            best_dist = d
            best_tri = fi

    face = faces[best_tri]
    v0 = verts[face[0]]
    v1 = verts[face[1]]
    v2 = verts[face[2]]
    tri_n = tangent_frames.tri_normals[best_tri]
    t1 = tangent_frames.tri_tangent_t1[best_tri]
    t2 = tangent_frames.tri_tangent_t2[best_tri]

    # Step 2: peak q from q_history along push_dir projection.
    Phi_x = eval_basis_at_point(
        contact_point, surface, modal_U_surf,
        surface_vertex_indices, vert_to_surf_idx,
    )
    nPhi = push_dir @ Phi_x
    d_all = q_history @ nPhi
    if d_all.size == 0:
        return push_dir.copy(), 0.0, best_tri
    k_peak = int(np.argmax(np.abs(d_all)))
    q_peak = q_history[k_peak]

    # Step 3: sample normal displacement at the 3 triangle vertices.
    w_vals = [0.0, 0.0, 0.0]
    for k in range(3):
        vert_global = face[k]
        surf_idx = vert_to_surf_idx[vert_global]
        if surf_idx < 0:
            w_vals[k] = 0.0
        else:
            row_start = 3 * surf_idx
            U_i = modal_U_surf[row_start:row_start + 3, :]
            u_vertex = U_i @ q_peak
            w_vals[k] = float(np.dot(tri_n, u_vertex))

    # Step 4: slopes via patch fit.
    s1, s2 = compute_patch_fit_slopes(
        w_vals[0], w_vals[1], w_vals[2], v0, v1, v2, t1, t2)

    # Step 5: tilted normal (clamped).
    n_tilt, theta = compute_tilted_normal(
        push_dir, s1, s2, t1, t2, theta_max)
    return n_tilt, theta, best_tri
