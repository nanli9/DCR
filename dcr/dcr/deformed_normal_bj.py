"""Deformed contact normal via F⁻ᵀ push-forward (Barbič & James 2008).

Principled alternative to the patch-fit heuristic in `deformed_normal.py`.
At a contact point `x_c` on the elastic body's surface, the deformed
normal is

    n' = normalize(F⁻ᵀ · n_rest),       (Barbič & James 2008 §4.1)

where F = I + ∇u(x_c, q) is the deformation gradient of the modal
displacement field at x_c. For a linear tet T = {X₀, X₁, X₂, X₃} with
FEM shape functions N_i and shape-function gradients ∇N_i ∈ R³
(constant within T):

    u_i(q) = Φ_full(X_i) · q                      (modal disp at vertex i)
    ∇u(x_c, q) = Σ_{i=0..3} u_i(q) ⊗ ∇N_i         (3×3, constant in T)
    F = I + ∇u                                    (deformation gradient)

Relationship to the patch-fit heuristic (foundation §17): to first
order in ‖q‖, F ≈ I + ∇u and F⁻ᵀ ≈ I − (∇u)ᵀ, so unnormalized
    F⁻ᵀ · n_rest ≈ n_rest − ∇(u · n_rest) = n_rest − ∇^{3D}(u · n_rest).
The patch fit subtracts only the *surface-tangent* part of that
gradient (it samples u·n at the 3 surface vertices and plane-fits in
the tangent frame). Decomposing ∇^{3D}(u·n) = ∇_tan + ∂(u·n)/∂n · n:
the ∂(u·n)/∂n part is in the n direction and is absorbed by post-
normalization, BUT the **tangent-plane projection of ∇N_D ⊗ u_D**
(where D is the interior tet vertex) is missed entirely by the patch
fit because its shape function vanishes on the surface triangle. So:

  - At q = 0, both methods return n_rest exactly.
  - For q ≠ 0, the angular discrepancy is O(‖q‖) — strictly linear —
    with coefficient set by the interior vertex's modal weight.

This is why the F⁻ᵀ method is a meaningful upgrade rather than a
re-derivation of the same first-order result. The empirical scaling
is pinned in tests/stageDV/test_deformed_normal_methods.py.

Other differences from the patch fit:
  1. *analytical* FEM shape-function gradients vs 3-vertex FD,
  2. uses current q (not a peak from q_history),
  3. no θ_max clamp needed in the small-deformation regime (kept for
     API symmetry).

Reference:
    Jernej Barbič and Doug L. James. "Six-DoF Haptic Rendering of
    Contact Between Geometrically Complex Reduced Deformable Models."
    IEEE Transactions on Haptics 1(1):39–52, 2008. §4.1.
    PDF: reference/BarbicJames-2008-IEEE-TOH.pdf

# DEVIATION: this module is the principled F⁻ᵀ method derived in
# foundation §17. The patch-fit heuristic in `deformed_normal.py`
# remains available and is the default (selected by
# PassiveDCRCoupler.deformed_normal_method).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh
from ..modal.modal_analysis import ModalAnalysis
from ..modal.passive_inject import _closest_point_on_triangle
from .deformed_normal import clamp_normal_angle


# ----------------------------------------------------------------------
# Precomputed cache — built once at PassiveDCRCoupler.__post_init__
# ----------------------------------------------------------------------

@dataclass
class BarbicJamesCache:
    """Precomputed structures for the F⁻ᵀ deformed-normal method
    (Barbič & James 2008 §4.1; foundation §17).

    Built once at PassiveDCRCoupler.__post_init__ when
    deformed_normal_method == "barbic_james". All arrays use the
    *original tet mesh's* vertex indexing (the same one
    ModalAnalysis.fem.mesh.tets uses), not the surface-local indexing.

    Attributes:
        tri_to_tet: (n_surface_tris,) int — for each surface triangle,
            the index of the unique tet that contains its 3 vertices as
            three of its 4 vertices.
        tet_grad_N: (n_tets, 4, 3) float — per-tet linear shape-function
            gradient ∇N_i ∈ R³ for each of the 4 nodes. Constant within
            a tet (constant-strain element). Derived inline from the
            inverse Jacobian (matches `dcr/fem/element.py:strain_displacement_matrix`).
        tet_vertex_indices: (n_tets, 4) int — copy of `mesh.tets`, kept
            so we don't have to keep a reference to the FEM model.
        U_full: (3 * n_vertices, n_modes) float — full-volume modal
            basis, with rows for constrained DOFs zero-padded. Needed
            to read the modal displacement at any of the 4 tet vertices
            including the interior one (the surface basis `U_surf` only
            covers surface vertices and is missing the interior row).
    """
    tri_to_tet: NDArray[np.int32]
    tet_grad_N: NDArray[np.float64]
    tet_vertex_indices: NDArray[np.int32]
    U_full: NDArray[np.float64]


# ----------------------------------------------------------------------
# Cache construction
# ----------------------------------------------------------------------

def _tet_grad_N(verts: NDArray[np.float64]) -> NDArray[np.float64]:
    """Linear-tet shape-function gradients ∇N_i ∈ R³ for the 4 nodes.

    Inlined from `dcr/fem/element.py:strain_displacement_matrix` (the
    Voigt-form B matrix there packs the same ∇N values into rows). Kept
    inline so this module doesn't depend on Voigt-ordering details.

    Args:
        verts: (4, 3) tet vertex positions [X₀; X₁; X₂; X₃].

    Returns:
        dN: (4, 3) — dN[i] = ∇N_i ∈ R³ for node i.

    Note: Σᵢ ∇N_i = 0 (partition-of-unity property for a linear simplex).
    """
    v0, v1, v2, v3 = verts
    # Jacobian columns = edge vectors from v0 (matches element.py).
    J = np.column_stack([v1 - v0, v2 - v0, v3 - v0])  # (3, 3)
    inv_J = np.linalg.inv(J)
    dN = np.zeros((4, 3), dtype=np.float64)
    dN[1] = inv_J[0]
    dN[2] = inv_J[1]
    dN[3] = inv_J[2]
    dN[0] = -(dN[1] + dN[2] + dN[3])  # N_0 = 1 - N_1 - N_2 - N_3
    return dN


def _build_tri_to_tet(
    surface: TriMesh, mesh_tets: NDArray[np.int32], num_vertices: int,
) -> NDArray[np.int32]:
    """For each surface triangle, find the unique tet whose 4 vertices
    contain the triangle's 3 vertices.

    Uses a vertex→tet adjacency list, then intersects the 3 sets per
    face. O(n_tets + n_faces · max_adjacency); sub-second for realistic
    meshes. Asserts uniqueness at build time (surface faces of a
    well-formed tet mesh are owned by exactly one tet).

    Args:
        surface: TriMesh whose faces use the original mesh's vertex
            indexing (`TetMesh.extract_surface()` guarantees this).
        mesh_tets: (n_tets, 4) original tet connectivity.
        num_vertices: total number of mesh vertices.

    Returns:
        tri_to_tet: (n_surface_tris,) int — owning tet index for each
            surface triangle.

    Raises:
        AssertionError: if any surface triangle is not owned by exactly
            one tet (indicates a non-manifold or degenerate mesh).
    """
    vert_to_tets: list[set[int]] = [set() for _ in range(num_vertices)]
    n_tets = mesh_tets.shape[0]
    for ti in range(n_tets):
        for v_idx in mesh_tets[ti]:
            vert_to_tets[int(v_idx)].add(ti)

    n_faces = surface.faces.shape[0]
    tri_to_tet = np.zeros(n_faces, dtype=np.int32)
    for fi in range(n_faces):
        v0, v1, v2 = (int(x) for x in surface.faces[fi])
        common = vert_to_tets[v0] & vert_to_tets[v1] & vert_to_tets[v2]
        if len(common) != 1:
            raise AssertionError(
                f"surface face {fi} (verts {v0},{v1},{v2}) is owned by "
                f"{len(common)} tets, expected exactly 1. The tet mesh may "
                f"be non-manifold or the surface extraction inconsistent.")
        tri_to_tet[fi] = next(iter(common))
    return tri_to_tet


def build_barbic_james_cache(
    modal: ModalAnalysis, surface: TriMesh,
) -> BarbicJamesCache:
    """Precompute the structures needed for `compute_deformed_normal_barbic_james`.

    One-time cost at coupler init. Subsequent runtime cost per contact
    is O(4 · n_modes) flops for the F assembly plus one 3×3 solve.

    Args:
        modal: the elastic body's ModalAnalysis (provides the FEM model,
            its tet mesh, and the reduced modal basis U).
        surface: the surface TriMesh extracted from the same tet mesh
            (typically `modal.fem.mesh.extract_surface()`).

    Returns:
        A populated BarbicJamesCache.
    """
    fem = modal.fem
    mesh = fem.mesh
    tets = mesh.tets

    # 1. Per-tet shape-function gradients (constant within each tet).
    n_tets = mesh.num_tets
    tet_grad_N = np.zeros((n_tets, 4, 3), dtype=np.float64)
    for ti in range(n_tets):
        tet_grad_N[ti] = _tet_grad_N(mesh.vertices[tets[ti]])

    # 2. Full-volume modal basis. modal.U is in free-DOF space; we
    #    scatter it back to full DOFs with zeros at constrained rows
    #    (modal displacement at fixed verts is correctly zero).
    n_modes = modal.U.shape[1]
    U_full = np.zeros((fem.n_full_dofs, n_modes), dtype=np.float64)
    U_full[fem.free_dofs, :] = modal.U

    # 3. Surface triangle → owning tet.
    tri_to_tet = _build_tri_to_tet(
        surface, tets, num_vertices=mesh.num_vertices)

    return BarbicJamesCache(
        tri_to_tet=tri_to_tet,
        tet_grad_N=tet_grad_N,
        tet_vertex_indices=tets.copy(),
        U_full=U_full,
    )


# ----------------------------------------------------------------------
# Runtime entry point
# ----------------------------------------------------------------------

def compute_deformed_normal_barbic_james(
    contact_point: NDArray[np.float64],
    push_dir: NDArray[np.float64],
    q: NDArray[np.float64],
    surface: TriMesh,
    cache: BarbicJamesCache,
    theta_max: float,
) -> tuple[NDArray[np.float64], float, int]:
    """Deformed contact normal n' via F⁻ᵀ push-forward (foundation §17).

    Pipeline:
      1. Find the closest surface triangle to `contact_point`.
      2. Look up the unique tet T that owns that triangle.
      3. Assemble F = I + Σ_{i=0..3} u_i(q) ⊗ ∇N_i where u_i = Φ(X_i)·q
         is the modal displacement at the i-th tet vertex (paid from
         the precomputed `cache.U_full`).
      4. n' = normalize(F⁻ᵀ · n_rest), with n_rest = `push_dir`.
      5. Clamp the angle between n_rest and n' to `theta_max` (shared
         helper from the patch-fit module).

    Args:
        contact_point: (3,) world-space contact point.
        push_dir: (3,) un-deformed contact normal (unit vector), already
            oriented FROM elastic TO body. Treated as n_rest.
        q: (n_modes,) *current* modal state. Note: unlike the patch-fit
            method which uses a peak snapshot from q_history, this method
            uses the current configuration (consistent with Barbič &
            James 2008's haptic-rate continuous evaluation).
        surface: TriMesh whose faces use the original tet mesh's vertex
            indexing — same instance passed to `build_barbic_james_cache`.
        cache: precomputed BarbicJamesCache.
        theta_max: clamp on |angle(push_dir, n')| in radians. Kept for
            API symmetry with the patch-fit method; in practice F⁻ᵀ is
            well-behaved for small ‖q‖ and the clamp rarely triggers.

    Returns:
        (n_prime, theta, best_tri):
            n_prime: (3,) unit deformed normal.
            theta: angle in radians between n_prime and push_dir
                (post-clamp).
            best_tri: index of the chosen surface triangle (diagnostic).
    """
    verts = surface.vertices
    faces = surface.faces

    # Step 1: closest surface triangle (brute-force; matches patch_fit).
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

    # Step 2: look up owning tet.
    ti = int(cache.tri_to_tet[best_tri])
    tet_verts = cache.tet_vertex_indices[ti]   # (4,)
    grad_N = cache.tet_grad_N[ti]              # (4, 3)

    # Step 3: F = I + Σ_k u_k ⊗ ∇N_k.
    #   ∂u_j / ∂x_i at the contact point = Σ_k (∇N_k)_i · (u_k)_j
    #   = (Σ_k u_k ⊗ ∇N_k)_{j,i}
    # where np.outer(a, b)_{j,i} = a[j] * b[i], so np.outer(u_k, ∇N_k)
    # gives exactly the right matrix.
    F = np.eye(3, dtype=np.float64)
    for k in range(4):
        v_idx = int(tet_verts[k])
        Phi_k = cache.U_full[3 * v_idx : 3 * v_idx + 3, :]  # (3, n_modes)
        u_k = Phi_k @ q                                      # (3,)
        F += np.outer(u_k, grad_N[k])

    # Step 4: n' = normalize(F^{-T} · n_rest). Solve F^T x = n_rest.
    try:
        n_raw = np.linalg.solve(F.T, push_dir)
    except np.linalg.LinAlgError:
        # F nearly singular (extreme deformation) — fall back to rest normal.
        return push_dir.copy(), 0.0, best_tri
    n_norm = float(np.linalg.norm(n_raw))
    if n_norm < 1e-12:
        return push_dir.copy(), 0.0, best_tri
    n_prime = n_raw / n_norm

    # Step 5: optional clamp (shared with patch_fit).
    n_clamped, theta = clamp_normal_angle(push_dir, n_prime, theta_max)
    return n_clamped, theta, best_tri
