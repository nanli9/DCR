"""FEMModel: assembled FEM system with boundary conditions and static solve.

Implements the model equation (paper Eq. 5):
    M ü + D u̇ + K u = f
with Rayleigh damping D = α₀ M + α₁ K.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from ..geom.tet_mesh import TetMesh
from .material import Material
from .assembly import assemble_global_matrices


@dataclass
class FEMModel:
    """Linear FEM model for a single elastic body.

    The body is meshed as tetrahedra and assembled into global M, K.
    Fixed (Dirichlet) boundary conditions are applied by removing
    the corresponding rows/columns to form the constrained system.

    Attributes:
        mesh: Tetrahedral mesh.
        material: Material properties.
        fixed_nodes: Indices of nodes with zero-displacement BCs.
        alpha0: Rayleigh damping mass coefficient.
        alpha1: Rayleigh damping stiffness coefficient.
    """

    mesh: TetMesh
    material: Material
    fixed_nodes: NDArray[np.int32] = field(default_factory=lambda: np.array([], dtype=np.int32))
    alpha0: float = 0.0
    alpha1: float = 0.0

    # Assembled (full, unconstrained) matrices.
    M_full: sp.csr_matrix = field(init=False, repr=False)
    K_full: sp.csr_matrix = field(init=False, repr=False)

    # Constrained (BC-reduced) matrices.
    M: sp.csr_matrix = field(init=False, repr=False)
    K: sp.csr_matrix = field(init=False, repr=False)

    # DOF bookkeeping.
    n_full_dofs: int = field(init=False)
    free_dofs: NDArray[np.int32] = field(init=False, repr=False)
    fixed_dofs: NDArray[np.int32] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.n_full_dofs = 3 * self.mesh.num_vertices

        # Assemble unconstrained matrices.
        self.M_full, self.K_full = assemble_global_matrices(self.mesh, self.material)

        # Determine free / fixed DOFs.
        self.fixed_nodes = np.asarray(self.fixed_nodes, dtype=np.int32)
        if self.fixed_nodes.size > 0:
            self.fixed_dofs = np.sort(np.concatenate([
                3 * self.fixed_nodes,
                3 * self.fixed_nodes + 1,
                3 * self.fixed_nodes + 2,
            ])).astype(np.int32)
        else:
            self.fixed_dofs = np.array([], dtype=np.int32)
        all_dofs = np.arange(self.n_full_dofs, dtype=np.int32)
        self.free_dofs = np.setdiff1d(all_dofs, self.fixed_dofs).astype(np.int32)

        # Constrained matrices: remove fixed DOF rows/cols.
        self.M = self._reduce(self.M_full)
        self.K = self._reduce(self.K_full)

    def _reduce(self, A: sp.spmatrix) -> sp.csr_matrix:
        """Extract the free-DOF sub-block of a sparse matrix."""
        return A.tocsr()[self.free_dofs][:, self.free_dofs].tocsr()

    @property
    def damping_matrix(self) -> sp.csr_matrix:
        """Rayleigh damping: D = α₀ M + α₁ K (paper Eq. 5)."""
        return self.alpha0 * self.M + self.alpha1 * self.K

    def gravity_load(self, g: float = -9.81) -> NDArray[np.float64]:
        """Consistent gravity load vector f (full DOFs), then reduced to free DOFs.

        For lumped mass, f_i = m_i * g_vec.  We apply gravity in -Y.
        """
        f_full = np.zeros(self.n_full_dofs, dtype=np.float64)
        # Lumped mass diagonal → per-DOF masses.
        m_diag = self.M_full.diagonal()
        # Gravity acts in the Y direction (DOF index 1, 4, 7, ...).
        f_full[1::3] = m_diag[1::3] * g
        return f_full[self.free_dofs]

    def static_solve(self, f_free: NDArray[np.float64]) -> NDArray[np.float64]:
        """Solve K u = f for the free DOFs.

        Args:
            f_free: Force vector on free DOFs.

        Returns:
            u_full: Displacement vector for ALL DOFs (fixed DOFs = 0).
        """
        u_free = spla.spsolve(self.K.tocsc(), f_free)
        u_full = np.zeros(self.n_full_dofs, dtype=np.float64)
        u_full[self.free_dofs] = u_free
        return u_full

    def total_mass(self) -> float:
        """Total mass (sum of lumped mass diagonal / 3, since each node has 3 identical entries)."""
        return self.M_full.diagonal().sum() / 3.0
