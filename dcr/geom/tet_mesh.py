"""Tetrahedral mesh data structures, procedural generators, and surface extraction."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray

from .mesh import TriMesh


@dataclass
class TetMesh:
    """Tetrahedral volume mesh.

    Attributes:
        vertices: (n, 3) float64 vertex positions.
        tets: (t, 4) int32 tetrahedron vertex indices.
    """

    vertices: NDArray[np.float64]
    tets: NDArray[np.int32]

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices, dtype=np.float64)
        self.tets = np.asarray(self.tets, dtype=np.int32)

    @property
    def num_vertices(self) -> int:
        return self.vertices.shape[0]

    @property
    def num_tets(self) -> int:
        return self.tets.shape[0]

    def extract_surface(self) -> TriMesh:
        """Extract surface triangles (faces shared by exactly one tet).

        Each tet contributes 4 faces.  A face on the surface appears exactly
        once across all tets; interior faces appear twice (shared by two tets).
        """
        # 4 faces per tet, each defined by 3 of the 4 vertices.
        # Face opposite vertex i is the triangle of the other 3.
        face_local = np.array([[1, 2, 3],
                                [0, 3, 2],
                                [0, 1, 3],
                                [0, 2, 1]], dtype=np.int32)
        n_tets = self.tets.shape[0]
        # Gather all faces: (4*n_tets, 3)
        all_faces = self.tets[:, face_local].reshape(-1, 3)
        # Sort vertex indices within each face for canonical form.
        sorted_faces = np.sort(all_faces, axis=1)
        # Find unique faces and their counts.
        _, inverse, counts = np.unique(
            sorted_faces, axis=0, return_inverse=True, return_counts=True
        )
        # Surface faces appear exactly once.
        surface_mask = counts[inverse] == 1
        surface_faces = all_faces[surface_mask]
        return TriMesh(self.vertices.copy(), surface_faces)


def make_beam_tet_mesh(
    length: float = 1.0,
    width: float = 0.1,
    height: float = 0.1,
    nx: int = 10,
    ny: int = 2,
    nz: int = 2,
) -> TetMesh:
    """Axis-aligned beam along +X, centered at the origin.

    Uses the alternating 5-tet hex decomposition (see ``_make_box_tet_mesh``).

    Args:
        length: Extent in X.
        width:  Extent in Y.
        height: Extent in Z.
        nx, ny, nz: Number of hex cells in each direction.
    """
    return _make_box_tet_mesh(length, width, height, nx, ny, nz)


def make_block_tet_mesh(
    size: float = 0.2,
    nx: int = 3,
    ny: int = 3,
    nz: int = 3,
) -> TetMesh:
    """Small cube centered at the origin."""
    return _make_box_tet_mesh(size, size, size, nx, ny, nz)


def make_slab_tet_mesh(
    length: float = 1.0,
    width: float = 0.6,
    height: float = 0.05,
    nx: int = 10,
    ny: int = 6,
    nz: int = 1,
) -> TetMesh:
    """Thin table-like slab centered at the origin."""
    return _make_box_tet_mesh(length, width, height, nx, ny, nz)


def _make_box_tet_mesh(
    lx: float, ly: float, lz: float,
    nx: int, ny: int, nz: int,
) -> TetMesh:
    """Build a regular hex grid and split each hex into 5 tets.

    Uses the alternating "red-black" 5-tet decomposition for face-compatible
    tiling.  Adjacent hexes (differing parity of i+j+k) use mirrored
    decompositions so shared quad faces split along the same diagonal.

    Vertex grid has (nx+1)*(ny+1)*(nz+1) nodes.
    The mesh is centered at the origin.
    """
    # Vertex grid
    xs = np.linspace(-lx / 2, lx / 2, nx + 1)
    ys = np.linspace(-ly / 2, ly / 2, ny + 1)
    zs = np.linspace(-lz / 2, lz / 2, nz + 1)
    gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
    vertices = np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])

    sy = (nz + 1)
    sx = (ny + 1) * sy

    # Hex vertex ordering:
    #   v0=(i,j,k)     v1=(i+1,j,k)   v2=(i+1,j+1,k)   v3=(i,j+1,k)
    #   v4=(i,j,k+1)   v5=(i+1,j,k+1) v6=(i+1,j+1,k+1) v7=(i,j+1,k+1)
    #
    # Type A (even parity, diagonal v0-v6):
    #   [0,1,2,5], [0,2,3,7], [0,4,5,7], [2,5,6,7], [0,2,5,7]
    # Type B (odd parity, diagonal v1-v7):
    #   [0,1,3,4], [1,2,3,6], [1,4,5,6], [3,4,6,7], [1,3,4,6]
    type_a = np.array([[0,1,2,5], [0,2,3,7], [0,4,5,7], [2,5,6,7], [0,2,5,7]])
    type_b = np.array([[0,1,3,4], [1,2,3,6], [1,4,5,6], [3,4,6,7], [1,3,4,6]])

    # Vectorized: build all hex corner indices at once.
    ii, jj, kk = np.mgrid[0:nx, 0:ny, 0:nz]
    ii = ii.ravel(); jj = jj.ravel(); kk = kk.ravel()
    n_hex = len(ii)

    # 8 hex corners as global vertex ids: (n_hex, 8)
    v = np.empty((n_hex, 8), dtype=np.int32)
    v[:, 0] = ii * sx + jj * sy + kk
    v[:, 1] = (ii + 1) * sx + jj * sy + kk
    v[:, 2] = (ii + 1) * sx + (jj + 1) * sy + kk
    v[:, 3] = ii * sx + (jj + 1) * sy + kk
    v[:, 4] = ii * sx + jj * sy + (kk + 1)
    v[:, 5] = (ii + 1) * sx + jj * sy + (kk + 1)
    v[:, 6] = (ii + 1) * sx + (jj + 1) * sy + (kk + 1)
    v[:, 7] = ii * sx + (jj + 1) * sy + (kk + 1)

    parity = (ii + jj + kk) % 2  # 0 → type A, 1 → type B
    mask_a = parity == 0
    mask_b = ~mask_a

    # Gather tets for each type, then concatenate.
    tets_a = v[mask_a][:, type_a].reshape(-1, 4)  # (n_a * 5, 4)
    tets_b = v[mask_b][:, type_b].reshape(-1, 4)  # (n_b * 5, 4)
    tets = np.concatenate([tets_a, tets_b], axis=0).astype(np.int32)

    return TetMesh(vertices, tets)
