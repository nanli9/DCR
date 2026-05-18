"""Global sparse assembly of FEM mass and stiffness matrices.

Fully vectorized: all element B matrices and K_e are computed in batch
using numpy broadcasting, then scattered into a single COO → CSR build.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
import scipy.sparse as sp

from ..geom.tet_mesh import TetMesh
from .material import Material


def _compute_all_element_matrices(
    mesh: TetMesh,
    D: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Vectorized computation of B and K_e for every tet.

    Args:
        mesh: Tetrahedral mesh.
        D: (6, 6) constitutive matrix.

    Returns:
        K_all: (n_tets, 12, 12) element stiffness matrices.
        vols:  (n_tets,) absolute element volumes.
    """
    # Gather vertex positions for all tets: (n_tets, 4, 3)
    coords = mesh.vertices[mesh.tets]
    v0 = coords[:, 0, :]  # (n_tets, 3)
    v1 = coords[:, 1, :]
    v2 = coords[:, 2, :]
    v3 = coords[:, 3, :]

    # Jacobians: J[:, :, col] = edge vectors from v0.  Shape: (n_tets, 3, 3)
    J = np.stack([v1 - v0, v2 - v0, v3 - v0], axis=-1)  # (n, 3, 3)

    # Determinants and volumes.
    det_J = np.linalg.det(J)  # (n_tets,)
    vols = np.abs(det_J) / 6.0

    # Inverse Jacobians: (n_tets, 3, 3)
    inv_J = np.linalg.inv(J)

    # Shape function gradients dN: (n_tets, 4, 3)
    dN = np.zeros((mesh.num_tets, 4, 3), dtype=np.float64)
    dN[:, 1, :] = inv_J[:, 0, :]  # row 0 of inv(J)
    dN[:, 2, :] = inv_J[:, 1, :]
    dN[:, 3, :] = inv_J[:, 2, :]
    dN[:, 0, :] = -(dN[:, 1, :] + dN[:, 2, :] + dN[:, 3, :])

    # Build B matrices: (n_tets, 6, 12)
    n = mesh.num_tets
    B = np.zeros((n, 6, 12), dtype=np.float64)
    for i in range(4):
        c = 3 * i
        dx = dN[:, i, 0]  # (n_tets,)
        dy = dN[:, i, 1]
        dz = dN[:, i, 2]
        B[:, 0, c] = dx
        B[:, 1, c + 1] = dy
        B[:, 2, c + 2] = dz
        B[:, 3, c] = dy
        B[:, 3, c + 1] = dx
        B[:, 4, c + 1] = dz
        B[:, 4, c + 2] = dy
        B[:, 5, c] = dz
        B[:, 5, c + 2] = dx

    # K_e = vol * B^T D B for each element.
    # D @ B: (n, 6, 12);  B^T @ (D @ B): (n, 12, 12)
    DB = np.einsum("ij,njk->nik", D, B)          # (n, 6, 12)
    K_all = np.einsum("nji,njk->nik", B, DB)     # (n, 12, 12)
    K_all *= vols[:, None, None]

    return K_all, vols


def assemble_global_matrices(
    mesh: TetMesh,
    material: Material,
) -> tuple[sp.csr_matrix, sp.csr_matrix]:
    """Assemble global mass M and stiffness K as sparse CSR matrices.

    Both are R^{3n x 3n} where n = number of vertices.

    Returns:
        M: Global lumped mass matrix (diagonal, CSR).
        K: Global stiffness matrix (CSR).
    """
    n_dofs = 3 * mesh.num_vertices
    D = material.constitutive_matrix()

    K_all, vols = _compute_all_element_matrices(mesh, D)

    # --- DOF index arrays for scatter ---
    # For each tet, the 12 DOFs are [3*v0, 3*v0+1, 3*v0+2, 3*v1, ...].
    # tets: (n_tets, 4) → dofs: (n_tets, 12)
    tet_dofs = np.empty((mesh.num_tets, 12), dtype=np.int32)
    for i in range(4):
        tet_dofs[:, 3 * i] = 3 * mesh.tets[:, i]
        tet_dofs[:, 3 * i + 1] = 3 * mesh.tets[:, i] + 1
        tet_dofs[:, 3 * i + 2] = 3 * mesh.tets[:, i] + 2

    # COO indices: for each element, 12x12 block → 144 entries.
    # rows[e, a, b] = tet_dofs[e, a],  cols[e, a, b] = tet_dofs[e, b]
    row_idx = np.repeat(tet_dofs, 12, axis=1)             # (n_tets, 144)
    col_idx = np.tile(tet_dofs, (1, 12))                   # WRONG shape, fix below
    # Correct tiling: each of the 12 dofs repeated as a block of 12.
    col_idx = np.tile(tet_dofs, 12).reshape(mesh.num_tets, 144)

    K = sp.csr_matrix(
        (K_all.ravel(), (row_idx.ravel(), col_idx.ravel())),
        shape=(n_dofs, n_dofs),
    )
    # Force exact symmetry.
    K = (K + K.T) * 0.5

    # --- Lumped mass: ρ V_e / 4 per node per tet ---
    m_per_tet = material.rho * vols / 4.0  # (n_tets,)
    m_diag = np.zeros(n_dofs, dtype=np.float64)
    np.add.at(m_diag, tet_dofs, m_per_tet[:, None])

    M = sp.diags(m_diag, format="csr")

    return M, K
