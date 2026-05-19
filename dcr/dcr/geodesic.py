"""Geodesic distance via the heat method (Crane, Weischedel, Wardetzky 2013).

Steps:
    1. Build cotan Laplacian L and lumped mass M on the surface triangle mesh.
    2. Solve heat equation: (M - t L) u = δ_source  for short time t.
    3. Normalized gradient: X = -∇u / |∇u| per face.
    4. Solve Poisson: L φ = ∇·X.
    5. Shift so min(φ) = 0.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from ..geom.mesh import TriMesh


def cotan_laplacian(mesh: TriMesh) -> tuple[sp.csr_matrix, sp.dia_matrix]:
    """Build the cotan Laplacian L and lumped mass M for a triangle mesh.

    L is negative semi-definite (L_{ii} = -sum_j L_{ij} for j≠i, L_{ij} ≥ 0
    for adjacent vertices).

    Returns:
        L: (n, n) cotan Laplacian (sparse CSR).
        M: (n, n) lumped mass diagonal (sparse DIA).
    """
    V = mesh.vertices
    F = mesh.faces
    n = V.shape[0]
    nf = F.shape[0]

    rows, cols, vals = [], [], []
    areas = np.zeros(n, dtype=np.float64)

    for fi in range(nf):
        i, j, k = F[fi]
        vi, vj, vk = V[i], V[j], V[k]

        # Edge vectors.
        eij = vj - vi
        eik = vk - vi
        ejk = vk - vj

        # Triangle area (for mass).
        area = 0.5 * np.linalg.norm(np.cross(eij, eik))
        if area < 1e-30:
            continue

        # Cotan weights for each edge: cot(angle opposite to edge) / 2.
        # Opposite to edge ij → angle at k: cot(∠k) = dot(eki, ekj) / |cross(eki, ekj)|
        def _cot(a: NDArray, b: NDArray) -> float:
            cross_mag = np.linalg.norm(np.cross(a, b))
            if cross_mag < 1e-30:
                return 0.0
            return np.dot(a, b) / cross_mag

        cot_k = _cot(vi - vk, vj - vk)  # opposite edge ij
        cot_i = _cot(vj - vi, vk - vi)  # opposite edge jk
        cot_j = _cot(vi - vj, vk - vj)  # opposite edge ik

        # Off-diagonal: L_{ij} = (cot_k) / 2  (weight for edge ij)
        for (a, b, w) in [(i, j, cot_k), (j, k, cot_i), (i, k, cot_j)]:
            w2 = w * 0.5
            rows.extend([a, b])
            cols.extend([b, a])
            vals.extend([w2, w2])

        # Lumped mass: area / 3 per vertex.
        areas[i] += area / 3.0
        areas[j] += area / 3.0
        areas[k] += area / 3.0

    L_off = sp.coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsr()
    # Diagonal: L_{ii} = -sum of off-diagonal entries in row i.
    diag_vals = -np.array(L_off.sum(axis=1)).ravel()
    L = L_off + sp.diags(diag_vals, format="csr")
    M = sp.diags(areas, format="dia")

    return L, M


def _compact_mesh(mesh: TriMesh) -> tuple[TriMesh, NDArray[np.int32], NDArray[np.int32]]:
    """Compact a surface mesh to only include vertices referenced by faces.

    Returns:
        compact: TriMesh with only used vertices and remapped faces.
        old_to_new: (n_old,) mapping from original vertex idx → compact idx (-1 if unused).
        new_to_old: (n_new,) mapping from compact idx → original vertex idx.
    """
    used = np.unique(mesh.faces.ravel())
    old_to_new = np.full(mesh.vertices.shape[0], -1, dtype=np.int32)
    old_to_new[used] = np.arange(len(used), dtype=np.int32)
    new_to_old = used.astype(np.int32)
    new_verts = mesh.vertices[used]
    new_faces = old_to_new[mesh.faces]
    return TriMesh(new_verts, new_faces), old_to_new, new_to_old


def heat_geodesic(
    mesh: TriMesh,
    source_vertex: int,
) -> NDArray[np.float64]:
    """Compute geodesic distances from source_vertex using the heat method.

    Args:
        mesh: Surface triangle mesh (may have unused vertices).
        source_vertex: Index of the source vertex (in original mesh).

    Returns:
        dist: (n_original,) geodesic distance from source to each vertex.
              Unused vertices get distance inf.
    """
    # Compact mesh to avoid singular matrices from unused vertices.
    compact, old_to_new, new_to_old = _compact_mesh(mesh)
    source_compact = old_to_new[source_vertex]
    if source_compact < 0:
        # Source vertex not on surface.
        dist = np.full(mesh.vertices.shape[0], np.inf)
        return dist

    V = compact.vertices
    F = compact.faces
    n = V.shape[0]

    L, M = cotan_laplacian(compact)

    # Step 1: heat diffusion time.
    # t = mean_edge_length^2 (recommended by Crane et al.)
    edges = np.concatenate([
        V[F[:, 1]] - V[F[:, 0]],
        V[F[:, 2]] - V[F[:, 1]],
        V[F[:, 0]] - V[F[:, 2]],
    ])
    mean_edge = np.mean(np.linalg.norm(edges, axis=1))
    t = mean_edge ** 2

    # Step 2: solve (M - tL) u = δ_source.
    A_heat = M - t * L
    rhs = np.zeros(n, dtype=np.float64)
    rhs[source_compact] = 1.0
    u = spla.spsolve(A_heat.tocsc(), rhs)

    # Clamp to avoid negative/zero values in gradient.
    u = np.maximum(u, 1e-30)

    # Step 3: compute normalized gradient X = -∇u / |∇u| per face.
    # ∇u on a triangle = (1 / 2A) * sum_i u_i * (n × e_i), where e_i is the
    # edge opposite vertex i and n is the face normal.
    nf = F.shape[0]
    X = np.zeros((nf, 3), dtype=np.float64)

    for fi in range(nf):
        i, j, k = F[fi]
        vi, vj, vk = V[i], V[j], V[k]
        face_normal = np.cross(vj - vi, vk - vi)
        area2 = np.linalg.norm(face_normal)
        if area2 < 1e-30:
            continue
        face_normal /= area2  # unit normal

        # Edges opposite to each vertex.
        e_i = vk - vj  # opposite vertex i
        e_j = vi - vk  # opposite vertex j
        e_k = vj - vi  # opposite vertex k

        grad_u = (u[i] * np.cross(face_normal, e_i) +
                  u[j] * np.cross(face_normal, e_j) +
                  u[k] * np.cross(face_normal, e_k)) / area2

        grad_mag = np.linalg.norm(grad_u)
        if grad_mag > 1e-30:
            X[fi] = -grad_u / grad_mag

    # Step 4: solve Poisson L φ = ∇·X (integrated divergence).
    # Integrated divergence at vertex i: sum over incident faces of
    #   (1/2) * dot(cot_j * (v_k - v_i) + cot_k * (v_j - v_i), X_f)
    div = np.zeros(n, dtype=np.float64)

    for fi in range(nf):
        i, j, k = F[fi]
        vi, vj, vk = V[i], V[j], V[k]

        def _cot(a: NDArray, b: NDArray) -> float:
            cross_mag = np.linalg.norm(np.cross(a, b))
            if cross_mag < 1e-30:
                return 0.0
            return np.dot(a, b) / cross_mag

        cot_k = _cot(vi - vk, vj - vk)
        cot_i = _cot(vj - vi, vk - vi)
        cot_j = _cot(vi - vj, vk - vj)

        Xf = X[fi]
        # Contribution to each vertex.
        div[i] += 0.5 * (cot_j * np.dot(vk - vi, Xf) + cot_k * np.dot(vj - vi, Xf))
        div[j] += 0.5 * (cot_k * np.dot(vi - vj, Xf) + cot_i * np.dot(vk - vj, Xf))
        div[k] += 0.5 * (cot_i * np.dot(vj - vk, Xf) + cot_j * np.dot(vi - vk, Xf))

    # L is singular (constant in null-space). Pin one vertex to make it PD.
    # Use anchored Poisson: replace row/col 0 with identity.
    L_anchored = L.tolil()
    L_anchored[0, :] = 0
    L_anchored[:, 0] = 0
    L_anchored[0, 0] = 1.0
    div[0] = 0.0
    L_anchored = L_anchored.tocsc()

    phi = spla.spsolve(L_anchored, div)

    # Step 5: shift so source = 0.
    phi -= phi[source_compact]
    phi = np.abs(phi)  # ensure non-negative

    # Map back to original vertex indices.
    dist = np.full(mesh.vertices.shape[0], np.inf, dtype=np.float64)
    dist[new_to_old] = phi
    return dist


def heat_geodesic_cached(
    mesh: TriMesh,
    cache: dict[int, NDArray[np.float64]],
    source_vertex: int,
) -> NDArray[np.float64]:
    """Compute or retrieve cached geodesic distances (paper §4.5)."""
    if source_vertex not in cache:
        cache[source_vertex] = heat_geodesic(mesh, source_vertex)
    return cache[source_vertex]
