"""Minimal OBJ file I/O for triangle meshes."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .mesh import TriMesh


def load_obj(path: str | Path) -> TriMesh:
    """Load an OBJ file containing only 'v' and 'f' lines (triangles)."""
    verts: list[list[float]] = []
    faces: list[list[int]] = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == "v":
                verts.append([float(x) for x in parts[1:4]])
            elif parts[0] == "f":
                # OBJ indices are 1-based; may have v/vt/vn format.
                idxs = [int(p.split("/")[0]) - 1 for p in parts[1:]]
                if len(idxs) == 3:
                    faces.append(idxs)
                elif len(idxs) == 4:
                    # Quad → two triangles.
                    faces.append([idxs[0], idxs[1], idxs[2]])
                    faces.append([idxs[0], idxs[2], idxs[3]])
    return TriMesh(np.array(verts, dtype=np.float64),
                   np.array(faces, dtype=np.int32))


def save_obj(mesh: TriMesh, path: str | Path) -> None:
    """Write a triangle mesh to OBJ."""
    with open(path, "w") as f:
        for v in mesh.vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in mesh.faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
