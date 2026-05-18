"""Mesh data structures and procedural generators."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class TriMesh:
    """Triangle surface mesh.

    Attributes:
        vertices: (n, 3) float64 vertex positions.
        faces: (f, 3) int32 triangle indices.
    """
    vertices: NDArray[np.float64]
    faces: NDArray[np.int32]

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices, dtype=np.float64)
        self.faces = np.asarray(self.faces, dtype=np.int32)


def make_box(half_extents: tuple[float, float, float] = (0.5, 0.5, 0.5),
             center: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> TriMesh:
    """Axis-aligned box with 8 vertices and 12 triangles."""
    hx, hy, hz = half_extents
    cx, cy, cz = center
    verts = np.array([
        [cx - hx, cy - hy, cz - hz],
        [cx + hx, cy - hy, cz - hz],
        [cx + hx, cy + hy, cz - hz],
        [cx - hx, cy + hy, cz - hz],
        [cx - hx, cy - hy, cz + hz],
        [cx + hx, cy - hy, cz + hz],
        [cx + hx, cy + hy, cz + hz],
        [cx - hx, cy + hy, cz + hz],
    ], dtype=np.float64)
    # Two triangles per face, CCW winding when viewed from outside.
    faces = np.array([
        # -Z face
        [0, 2, 1], [0, 3, 2],
        # +Z face
        [4, 5, 6], [4, 6, 7],
        # -Y face
        [0, 1, 5], [0, 5, 4],
        # +Y face
        [2, 3, 7], [2, 7, 6],
        # -X face
        [0, 4, 7], [0, 7, 3],
        # +X face
        [1, 2, 6], [1, 6, 5],
    ], dtype=np.int32)
    return TriMesh(verts, faces)


def make_ground_plane(size: float = 10.0, y: float = 0.0) -> TriMesh:
    """Flat quad (2 triangles) in the XZ plane at the given Y height."""
    s = size / 2.0
    verts = np.array([
        [-s, y, -s],
        [ s, y, -s],
        [ s, y,  s],
        [-s, y,  s],
    ], dtype=np.float64)
    faces = np.array([
        [0, 2, 1],
        [0, 3, 2],
    ], dtype=np.int32)
    return TriMesh(verts, faces)
