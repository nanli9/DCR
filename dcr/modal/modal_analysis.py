"""Modal analysis: generalized eigenproblem + reduced system.

Implements the modal decomposition from paper §3 (Eqs. 6–8):
    K ψ_i = ω_i² M ψ_i                        (Eq. 6)
    M_q q̈ + D_q q̇ + K_q q = U^T f             (Eq. 7)
    q̈_i + 2ξ_i ω_i q̇_i + ω_i² q_i = r_i      (Eq. 8)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from ..fem.fem_model import FEMModel


@dataclass
class ModalAnalysis:
    """Modal decomposition of a linear FEM model.

    Solves the generalized eigenproblem K ψ = ω² M ψ (Eq. 6),
    mass-normalizes the eigenvectors, and builds the reduced
    system matrices (Eq. 7).

    Attributes:
        fem: The underlying FEM model (with BCs already applied).
        num_modes: Number of modes to compute.
    """

    fem: FEMModel
    num_modes: int = 20

    # Computed fields.
    eigenvalues: NDArray[np.float64] = field(init=False, repr=False)
    frequencies: NDArray[np.float64] = field(init=False, repr=False)
    U: NDArray[np.float64] = field(init=False, repr=False)
    M_q: NDArray[np.float64] = field(init=False, repr=False)
    K_q: NDArray[np.float64] = field(init=False, repr=False)
    D_q: NDArray[np.float64] = field(init=False, repr=False)

    # Surface reduction (§3.6).
    surface_vertex_indices: NDArray[np.int32] = field(init=False, repr=False)
    U_surf: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._solve_eigenproblem()
        self._build_reduced_matrices()
        self._build_surface_mapping()

    # ------------------------------------------------------------------
    # 3.2  Generalized eigenproblem  (Eq. 6)
    # ------------------------------------------------------------------
    def _solve_eigenproblem(self) -> None:
        """Solve K ψ_i = ω_i² M ψ_i for the lowest *num_modes* modes.

        Uses shift-invert near σ=0 to target the smallest eigenvalues.
        Eigenvectors are mass-normalized so that ψ_i^T M ψ_i = 1.
        """
        K = self.fem.K.tocsc()
        M = self.fem.M.tocsc()

        # eigsh with sigma=0, which='LM' does shift-invert → smallest eigenvalues.
        eigenvalues, eigvecs = spla.eigsh(
            K, k=self.num_modes, M=M, sigma=0.0, which="LM",
        )

        # Sort by ascending eigenvalue (ascending frequency).
        order = np.argsort(eigenvalues)
        eigenvalues = eigenvalues[order]
        eigvecs = eigvecs[:, order]

        # Clamp any tiny negative eigenvalues to zero (numerical noise).
        eigenvalues = np.maximum(eigenvalues, 0.0)

        # Mass-normalize: scale each ψ_i so that ψ_i^T M ψ_i = 1.
        for i in range(self.num_modes):
            psi = eigvecs[:, i]
            norm = np.sqrt(psi @ (M @ psi))
            eigvecs[:, i] = psi / norm

        self.eigenvalues = eigenvalues                     # ω_i²
        self.frequencies = np.sqrt(eigenvalues)            # ω_i [rad/s]

        # U ∈ R^{n_free_dofs × m}: columns are mass-normalized eigenvectors.
        # This is in the *reduced* (free-DOF) space.
        self.U = eigvecs

    # ------------------------------------------------------------------
    # 3.4  Reduced matrices  (Eq. 7)
    # ------------------------------------------------------------------
    def _build_reduced_matrices(self) -> None:
        """Compute M_q, K_q, D_q in the modal basis (Eq. 7).

        With mass-normalized eigenvectors:
            M_q = U^T M U ≈ I
            K_q = U^T K U ≈ diag(ω_i²)
            D_q = U^T D U   (diagonal for Rayleigh damping)
        """
        M = self.fem.M
        K = self.fem.K
        D = self.fem.damping_matrix

        self.M_q = self.U.T @ (M @ self.U)
        self.K_q = self.U.T @ (K @ self.U)
        self.D_q = self.U.T @ (D @ self.U)

    # ------------------------------------------------------------------
    # 3.6  Surface reduction
    # ------------------------------------------------------------------
    def _build_surface_mapping(self) -> None:
        """Extract surface-vertex rows from U for contact response (§3.6).

        Only surface displacements matter for DCR. We store U_surf ∈ R^{3 n_surf × m}
        and the mapping from surface vertex index to the full mesh vertex index.
        """
        surface = self.fem.mesh.extract_surface()
        # Unique surface vertex indices (in the original mesh).
        surf_verts = np.unique(surface.faces.ravel())

        # Map surface vertex indices to free-DOF row indices in U.
        # Each vertex v has DOFs [3v, 3v+1, 3v+2] in the full system.
        # We need the indices of those DOFs in the free-DOF array.
        free_set = set(self.fem.free_dofs.tolist())
        # Build a mapping: full_dof → index in free_dofs array.
        full_to_free = np.full(self.fem.n_full_dofs, -1, dtype=np.int32)
        full_to_free[self.fem.free_dofs] = np.arange(len(self.fem.free_dofs), dtype=np.int32)

        surf_free_rows = []
        valid_surf_verts = []
        for v in surf_verts:
            dofs = [3 * v, 3 * v + 1, 3 * v + 2]
            free_idx = full_to_free[dofs]
            if np.all(free_idx >= 0):
                surf_free_rows.extend(free_idx.tolist())
                valid_surf_verts.append(v)

        self.surface_vertex_indices = np.array(valid_surf_verts, dtype=np.int32)
        surf_free_rows = np.array(surf_free_rows, dtype=np.int32)
        self.U_surf = self.U[surf_free_rows, :]  # (3 * n_surf_free, m)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def expand_to_full(self, u_free: NDArray[np.float64]) -> NDArray[np.float64]:
        """Expand a free-DOF vector back to the full 3n DOF space (fixed DOFs = 0)."""
        u_full = np.zeros(self.fem.n_full_dofs, dtype=np.float64)
        u_full[self.fem.free_dofs] = u_free
        return u_full

    def mode_displacement(self, mode_index: int) -> NDArray[np.float64]:
        """Full-DOF displacement for mode *mode_index* (unit modal amplitude).

        Returns:
            u_full: (3n,) displacement vector with fixed DOFs = 0.
        """
        return self.expand_to_full(self.U[:, mode_index])

    def modal_force(self, f_free: NDArray[np.float64]) -> NDArray[np.float64]:
        """Project a free-DOF force vector into modal coordinates: r = U^T f (Eq. 7)."""
        return self.U.T @ f_free
