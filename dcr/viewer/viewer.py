"""Thin polyscope wrapper for DCR visualization."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polyscope as ps

from dcr.geom.mesh import TriMesh


@dataclass
class SceneObject:
    """A named mesh to be registered with polyscope."""
    name: str
    mesh: TriMesh
    color: tuple[float, float, float] = (0.7, 0.7, 0.7)
    transparency: float = 1.0


class Viewer:
    """Manages a polyscope window with registered meshes."""

    def __init__(self, ground_plane: bool = True) -> None:
        self._objects: list[SceneObject] = []
        self._initialized = False
        self._ground_plane = ground_plane

    def add(self, obj: SceneObject) -> None:
        self._objects.append(obj)

    def show(self) -> None:
        if not self._initialized:
            ps.init()
            ps.set_up_dir("y_up")
            ps.set_ground_plane_mode("shadow_only" if self._ground_plane else "none")
            self._initialized = True

        for obj in self._objects:
            sm = ps.register_surface_mesh(
                obj.name,
                obj.mesh.vertices,
                obj.mesh.faces,
            )
            sm.set_color(obj.color)
            sm.set_transparency(obj.transparency)

        ps.show()
