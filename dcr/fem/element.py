"""Linear (constant-strain) tetrahedral element matrices.

Each tet has 4 nodes with 3 DOFs each → 12 DOFs per element.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def tet_volume(v0: NDArray, v1: NDArray, v2: NDArray, v3: NDArray) -> float:
    """Signed volume of a tetrahedron: V = (1/6) det([v1-v0, v2-v0, v3-v0])."""
    J = np.column_stack([v1 - v0, v2 - v0, v3 - v0])  # (3, 3)
    return np.linalg.det(J) / 6.0


def strain_displacement_matrix(
    v0: NDArray, v1: NDArray, v2: NDArray, v3: NDArray,
) -> tuple[NDArray[np.float64], float]:
    """Strain-displacement matrix B (6×12) for a linear tet.

    The shape-function gradients are constant over the element, so B is
    constant too (constant-strain element).

    Returns:
        B: (6, 12) strain-displacement matrix.
        vol: Absolute volume of the tetrahedron.
    """
    # Jacobian of the isoparametric mapping: columns = edge vectors from v0.
    J = np.column_stack([v1 - v0, v2 - v0, v3 - v0])  # (3, 3)
    det_J = np.linalg.det(J)
    vol = abs(det_J) / 6.0

    # Shape function gradients in physical coords.
    # dN/dx for nodes 1,2,3 = inv(J)^T rows correspond to each node.
    # Actually: [dN1/dx dN2/dx dN3/dx] = inv(J), where N_i are the
    # non-constant shape functions (associated with v1, v2, v3).
    # N_0 = 1 - N_1 - N_2 - N_3, so dN_0/dx = -sum of the others.
    inv_J = np.linalg.inv(J)  # (3, 3)
    # inv_J[i, :] = gradient of shape function for node (i+1) w.r.t. (x,y,z).
    dN = np.zeros((4, 3), dtype=np.float64)
    dN[1] = inv_J[0]
    dN[2] = inv_J[1]
    dN[3] = inv_J[2]
    dN[0] = -(dN[1] + dN[2] + dN[3])

    # Assemble B = [B_0, B_1, B_2, B_3], each B_i is (6, 3).
    # Voigt ordering: [ε_xx, ε_yy, ε_zz, γ_xy, γ_yz, γ_xz]
    B = np.zeros((6, 12), dtype=np.float64)
    for i in range(4):
        dx, dy, dz = dN[i]
        col = 3 * i
        B[0, col]     = dx   # ε_xx
        B[1, col + 1] = dy   # ε_yy
        B[2, col + 2] = dz   # ε_zz
        B[3, col]     = dy   # γ_xy
        B[3, col + 1] = dx
        B[4, col + 1] = dz   # γ_yz
        B[4, col + 2] = dy
        B[5, col]     = dz   # γ_xz
        B[5, col + 2] = dx

    return B, vol


def element_stiffness(
    B: NDArray[np.float64],
    D: NDArray[np.float64],
    vol: float,
) -> NDArray[np.float64]:
    """Element stiffness matrix K_e = V_e B^T D B.  Shape: (12, 12)."""
    return vol * (B.T @ D @ B)


def element_mass_lumped(vol: float, rho: float) -> NDArray[np.float64]:
    """Lumped element mass matrix: M_e = (ρ V_e / 4) I_{12}.

    Total tet mass ρ V_e split equally among 4 nodes, 3 DOFs each.
    """
    return (rho * vol / 4.0) * np.eye(12, dtype=np.float64)
