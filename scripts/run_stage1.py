#!/usr/bin/env python3
"""Stage 1 visualization: rigid body simulator demos.

Usage:
    python scripts/run_stage1.py bounce    # Single box bouncing
    python scripts/run_stage1.py stack     # 10 stacked boxes
    python scripts/run_stage1.py incline   # Box on inclined plane
"""
from __future__ import annotations

import sys

import numpy as np
import polyscope as ps

from dcr.geom import make_box, make_ground_plane
from dcr.rigid import (
    World, ConstraintSolver,
    make_dynamic_box, make_dynamic_sphere, make_static_plane,
)
from dcr.rigid.body import quat_to_rot


def _box_verts(body) -> np.ndarray:
    """Return 8 world-space vertices for a box body."""
    hx, hy, hz = body.shape.half_extents
    R = body.rotation_matrix()
    signs = np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                      [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]], dtype=np.float64)
    return body.position + (R @ (signs * np.array([hx, hy, hz])).T).T


BOX_FACES = np.array([
    [0,2,1],[0,3,2],[4,5,6],[4,6,7],
    [0,1,5],[0,5,4],[2,3,7],[2,7,6],
    [0,4,7],[0,7,3],[1,2,6],[1,6,5],
], dtype=np.int32)


def demo_bounce():
    world = World(h=1e-3, solver=ConstraintSolver(h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=50))
    ground = make_static_plane(friction=0.5)
    box = make_dynamic_box(1.0, 0.15, 0.15, 0.15, position=(0, 2, 0),
                           restitution=0.5, friction=0.5)
    world.add_body(ground)
    world.add_body(box)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    gm = make_ground_plane(size=6.0, y=0.0)
    ps.register_surface_mesh("ground", gm.vertices, gm.faces).set_color((0.5, 0.5, 0.5))
    sm = ps.register_surface_mesh("box", _box_verts(box), BOX_FACES)
    sm.set_color((0.8, 0.4, 0.2))

    def step_callback():
        for _ in range(10):
            world.step()
        sm.update_vertex_positions(_box_verts(box))

    ps.set_user_callback(step_callback)
    ps.show()


def demo_stack():
    world = World(h=1e-2, solver=ConstraintSolver(h=1e-2, cfm=1e-6, erp=0.1, pgs_iterations=300))
    ground = make_static_plane(friction=0.8)
    world.add_body(ground)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")
    gm = make_ground_plane(size=6.0, y=0.0)
    ps.register_surface_mesh("ground", gm.vertices, gm.faces).set_color((0.5, 0.5, 0.5))

    meshes = []
    bodies = []
    colors = [(0.8, 0.3, 0.2), (0.2, 0.6, 0.8), (0.3, 0.8, 0.3),
              (0.8, 0.8, 0.2), (0.8, 0.2, 0.8)]
    for i in range(10):
        y = 0.1 + 0.2 * i
        b = make_dynamic_box(1.0, 0.1, 0.1, 0.1, position=(0, y, 0),
                             restitution=0.0, friction=0.8)
        world.add_body(b)
        bodies.append(b)
        sm = ps.register_surface_mesh(f"box_{i}", _box_verts(b), BOX_FACES)
        sm.set_color(colors[i % len(colors)])
        meshes.append(sm)

    def step_callback():
        world.step()
        for i, (b, sm) in enumerate(zip(bodies, meshes)):
            sm.update_vertex_positions(_box_verts(b))

    ps.set_user_callback(step_callback)
    ps.show()


def demo_incline():
    mu = 0.5
    angle = np.arctan(mu) * 1.5  # above friction angle -> slides

    world = World(h=1e-2, solver=ConstraintSolver(h=1e-2, cfm=1e-6, erp=0.2, pgs_iterations=50))
    nx, ny = -np.sin(angle), np.cos(angle)
    plane = make_static_plane(normal=(nx, ny, 0), friction=mu)
    world.add_body(plane)

    box = make_dynamic_box(1.0, 0.1, 0.1, 0.1, position=(0, 1.5, 0),
                           restitution=0.0, friction=mu)
    world.add_body(box)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("none")

    # Inclined plane mesh
    s = 5.0
    R = np.array([[ny, nx, 0], [-nx, ny, 0], [0, 0, 1]])
    plane_verts = np.array([[-s, 0, -s], [s, 0, -s], [s, 0, s], [-s, 0, s]]) @ R.T
    plane_faces = np.array([[0, 2, 1], [0, 3, 2]], dtype=np.int32)
    ps.register_surface_mesh("incline", plane_verts, plane_faces).set_color((0.5, 0.5, 0.5))

    sm = ps.register_surface_mesh("box", _box_verts(box), BOX_FACES)
    sm.set_color((0.8, 0.4, 0.2))

    def step_callback():
        world.step()
        sm.update_vertex_positions(_box_verts(box))

    ps.set_user_callback(step_callback)
    ps.show()


if __name__ == "__main__":
    demos = {"bounce": demo_bounce, "stack": demo_stack, "incline": demo_incline}
    name = sys.argv[1] if len(sys.argv) > 1 else "bounce"
    if name not in demos:
        print(f"Usage: {sys.argv[0]} [{'/'.join(demos)}]")
        sys.exit(1)
    demos[name]()
