#!/usr/bin/env python3
"""Stage 1 visualization: rigid body simulator demos.

Usage:
    python scripts/run_stage1.py bounce    # Single box bouncing
    python scripts/run_stage1.py stack     # 10 stacked boxes
    python scripts/run_stage1.py incline   # Box on inclined plane
    python scripts/run_stage1.py pair      # Sphere drops onto box on ground
    python scripts/run_stage1.py collide   # Two spheres launched at each other
"""
from __future__ import annotations

import sys

import numpy as np
import polyscope as ps

from dcr.geom import make_box, make_ground_plane
from dcr.rigid import (
    World, ConstraintSolver, DistanceJoint,
    make_dynamic_box, make_dynamic_sphere, make_static_plane,
    RigidBody, sphere_shape,
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


def _make_sphere_mesh(radius: float, subdivisions: int = 2):
    """Create an icosphere mesh (verts, faces) for rendering."""
    # Start with icosahedron
    t = (1.0 + np.sqrt(5.0)) / 2.0
    verts = [
        [-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
        [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
        [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1],
    ]
    faces = [
        [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
        [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
        [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
        [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1],
    ]
    verts = [np.array(v, dtype=np.float64) / np.linalg.norm(v) for v in verts]

    # Subdivide
    edge_cache: dict = {}
    def _midpoint(i, j):
        key = (min(i, j), max(i, j))
        if key in edge_cache:
            return edge_cache[key]
        mid = (verts[i] + verts[j]) * 0.5
        mid /= np.linalg.norm(mid)
        verts.append(mid)
        idx = len(verts) - 1
        edge_cache[key] = idx
        return idx

    for _ in range(subdivisions):
        new_faces = []
        edge_cache = {}
        for tri in faces:
            a, b, c = tri
            ab = _midpoint(a, b)
            bc = _midpoint(b, c)
            ca = _midpoint(c, a)
            new_faces.extend([
                [a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]
            ])
        faces = new_faces

    V = np.array(verts, dtype=np.float64) * radius
    F = np.array(faces, dtype=np.int32)
    return V, F


def _sphere_verts(body, ref_verts: np.ndarray) -> np.ndarray:
    """Translate reference sphere verts to body position."""
    return ref_verts + body.position


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


def demo_pair():
    """Sphere drops onto a box resting on the ground.

    Shows sphere-box and box-plane contacts simultaneously.
    Prints contact count and body velocities each frame.
    """
    world = World(h=1e-3, solver=ConstraintSolver(
        h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=50))
    ground = make_static_plane(friction=0.5)
    world.add_body(ground)

    box = make_dynamic_box(2.0, 0.2, 0.1, 0.2, position=(0, 0.1, 0),
                           restitution=0.3, friction=0.5)
    world.add_body(box)

    sphere = make_dynamic_sphere(1.0, 0.15, position=(0.05, 1.5, 0.05),
                                 restitution=0.4, friction=0.5)
    world.add_body(sphere)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    gm = make_ground_plane(size=6.0, y=0.0)
    ps.register_surface_mesh("ground", gm.vertices, gm.faces).set_color((0.5, 0.5, 0.5))

    box_sm = ps.register_surface_mesh("box", _box_verts(box), BOX_FACES)
    box_sm.set_color((0.2, 0.6, 0.8))

    sph_v, sph_f = _make_sphere_mesh(sphere.shape.half_extents[0])
    sph_sm = ps.register_surface_mesh("sphere", _sphere_verts(sphere, sph_v), sph_f)
    sph_sm.set_color((0.8, 0.4, 0.2))

    frame = [0]

    def step_callback():
        for _ in range(5):
            contacts = world.step()
        frame[0] += 1
        box_sm.update_vertex_positions(_box_verts(box))
        sph_sm.update_vertex_positions(_sphere_verts(sphere, sph_v))
        if frame[0] % 20 == 0:
            print(f"t={world.time:.2f}s  contacts={len(contacts):2d}  "
                  f"sphere_y={sphere.position[1]:.3f}  box_y={box.position[1]:.3f}  "
                  f"sphere_vy={sphere.velocity[1]:+.3f}  box_vy={box.velocity[1]:+.3f}")

    ps.set_user_callback(step_callback)
    ps.show()


def demo_collide():
    """Two spheres launched toward each other above the ground.

    Tests sphere-sphere and sphere-plane contacts.
    Prints velocities to show momentum exchange.
    """
    world = World(h=1e-3, solver=ConstraintSolver(
        h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=50))
    ground = make_static_plane(friction=0.3)
    world.add_body(ground)

    sphere_a = make_dynamic_sphere(1.0, 0.15, position=(-1.0, 0.5, 0),
                                   restitution=0.6, friction=0.3)
    sphere_a.velocity[0] = 3.0  # launch right
    world.add_body(sphere_a)

    sphere_b = make_dynamic_sphere(2.0, 0.2, position=(1.0, 0.5, 0),
                                   restitution=0.6, friction=0.3)
    sphere_b.velocity[0] = -1.5  # launch left
    world.add_body(sphere_b)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    gm = make_ground_plane(size=8.0, y=0.0)
    ps.register_surface_mesh("ground", gm.vertices, gm.faces).set_color((0.5, 0.5, 0.5))

    va, fa = _make_sphere_mesh(sphere_a.shape.half_extents[0])
    sm_a = ps.register_surface_mesh("sphere_a", _sphere_verts(sphere_a, va), fa)
    sm_a.set_color((0.8, 0.3, 0.2))

    vb, fb = _make_sphere_mesh(sphere_b.shape.half_extents[0])
    sm_b = ps.register_surface_mesh("sphere_b", _sphere_verts(sphere_b, vb), fb)
    sm_b.set_color((0.2, 0.5, 0.8))

    frame = [0]

    def step_callback():
        for _ in range(5):
            contacts = world.step()
        frame[0] += 1
        sm_a.update_vertex_positions(_sphere_verts(sphere_a, va))
        sm_b.update_vertex_positions(_sphere_verts(sphere_b, vb))
        if frame[0] % 20 == 0:
            pa = sphere_a.mass * sphere_a.velocity[0]
            pb = sphere_b.mass * sphere_b.velocity[0]
            print(f"t={world.time:.2f}s  contacts={len(contacts):2d}  "
                  f"A=({sphere_a.position[0]:+.2f},{sphere_a.position[1]:.2f}) "
                  f"vx={sphere_a.velocity[0]:+.2f}  "
                  f"B=({sphere_b.position[0]:+.2f},{sphere_b.position[1]:.2f}) "
                  f"vx={sphere_b.velocity[0]:+.2f}  "
                  f"p_total={pa + pb:+.3f}")

    ps.set_user_callback(step_callback)
    ps.show()


def _reset_body(body, pos, vel=None):
    """Reset a body to the given position with zero (or given) velocity."""
    from dcr.rigid.body import quat_identity
    body.position = np.array(pos, dtype=np.float64)
    body.orientation = quat_identity()
    body.velocity = np.array(vel, dtype=np.float64) if vel is not None else np.zeros(6)
    body.force = np.zeros(6)


def demo_linked():
    """Two spheres connected by a rigid rod, dropped onto the ground.

    The rod is a distance joint. The pair swings and bounces as a linked system.
    Press the Reset button in the UI to restart the simulation.
    """
    rod_length = 0.8
    init_a = (-0.3, 2.5, 0)
    init_b = (0.5, 2.5, 0)

    world = World(h=1e-3, solver=ConstraintSolver(
        h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=80))
    ground = make_static_plane(friction=0.5)
    world.add_body(ground)

    sA = make_dynamic_sphere(1.5, 0.12, position=init_a,
                             restitution=0.3, friction=0.5)
    idx_a = world.add_body(sA)

    sB = make_dynamic_sphere(0.8, 0.10, position=init_b,
                             restitution=0.3, friction=0.5)
    idx_b = world.add_body(sB)

    joint = DistanceJoint(
        body_a=idx_a, body_b=idx_b,
        local_anchor_a=np.zeros(3), local_anchor_b=np.zeros(3),
        rest_length=rod_length,
    )
    world.add_joint(joint)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    gm = make_ground_plane(size=8.0, y=0.0)
    ps.register_surface_mesh("ground", gm.vertices, gm.faces).set_color((0.5, 0.5, 0.5))

    vA, fA = _make_sphere_mesh(sA.shape.half_extents[0])
    sm_a = ps.register_surface_mesh("sphere_a", _sphere_verts(sA, vA), fA)
    sm_a.set_color((0.8, 0.3, 0.2))

    vB, fB = _make_sphere_mesh(sB.shape.half_extents[0])
    sm_b = ps.register_surface_mesh("sphere_b", _sphere_verts(sB, vB), fB)
    sm_b.set_color((0.2, 0.5, 0.8))

    rod_nodes = np.array([sA.position, sB.position])
    rod_edges = np.array([[0, 1]], dtype=np.int32)
    rod_net = ps.register_curve_network("rod", rod_nodes, rod_edges)
    rod_net.set_radius(0.003)
    rod_net.set_color((0.4, 0.4, 0.4))

    frame = [0]

    def step_callback():
        # Reset button
        if ps.imgui.Button("Reset"):
            _reset_body(sA, init_a)
            _reset_body(sB, init_b)
            world.time = 0.0
            world.prev_contacts = []
            world.solver._prev_lambda = {}
            frame[0] = 0
            print("--- Reset ---")

        dist = np.linalg.norm(sA.position - sB.position)
        ps.imgui.TextUnformatted(
            f"t={world.time:.2f}s  rod={dist:.4f}")

        for _ in range(5):
            world.step()
        frame[0] += 1
        sm_a.update_vertex_positions(_sphere_verts(sA, vA))
        sm_b.update_vertex_positions(_sphere_verts(sB, vB))
        rod_net.update_node_positions(np.array([sA.position, sB.position]))

        if frame[0] % 30 == 0:
            print(f"t={world.time:.2f}s  rod={dist:.4f} (target={rod_length:.2f})  "
                  f"A=({sA.position[0]:+.3f},{sA.position[1]:.3f})  "
                  f"B=({sB.position[0]:+.3f},{sB.position[1]:.3f})")

    ps.set_user_callback(step_callback)
    ps.show()


def demo_chain():
    """Three boxes connected by rods in a chain, dropped onto the ground.

    Shows multiple distance joints forming a chain / flail.
    Press the Reset button in the UI to restart the simulation.
    """
    link_len = 0.3
    box_h = 0.08
    colors = [(0.8, 0.3, 0.2), (0.3, 0.7, 0.3), (0.2, 0.4, 0.8)]
    # Space boxes so anchor-to-anchor distance = link_len exactly.
    # Each box is 2*box_h wide; gap between edges = link_len.
    spacing = 2 * box_h + link_len  # center-to-center = 0.46
    init_positions = [(-spacing, 2.0, 0), (0.0, 2.0, 0), (spacing, 2.0, 0)]

    world = World(h=1e-3, solver=ConstraintSolver(
        h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=80))
    ground = make_static_plane(friction=0.5)
    world.add_body(ground)

    boxes = []
    for pos in init_positions:
        b = make_dynamic_box(1.0, box_h, box_h, box_h, position=pos,
                             restitution=0.2, friction=0.5)
        world.add_body(b)
        boxes.append(b)

    # Give the left box a kick to create interesting swing dynamics
    boxes[0].velocity[0] = 2.0  # rightward
    boxes[0].velocity[1] = 3.0  # upward

    world.add_joint(DistanceJoint(
        body_a=1, body_b=2,
        local_anchor_a=np.array([box_h, 0, 0]),
        local_anchor_b=np.array([-box_h, 0, 0]),
        rest_length=link_len,
    ))
    world.add_joint(DistanceJoint(
        body_a=2, body_b=3,
        local_anchor_a=np.array([box_h, 0, 0]),
        local_anchor_b=np.array([-box_h, 0, 0]),
        rest_length=link_len,
    ))

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    gm = make_ground_plane(size=8.0, y=0.0)
    ps.register_surface_mesh("ground", gm.vertices, gm.faces).set_color((0.5, 0.5, 0.5))

    box_meshes = []
    for i, b in enumerate(boxes):
        sm = ps.register_surface_mesh(f"box_{i}", _box_verts(b), BOX_FACES)
        sm.set_color(colors[i])
        box_meshes.append(sm)

    def _rod_nodes():
        nodes = []
        for j in world.joints:
            nodes.append(j.world_anchor_a(world.bodies))
            nodes.append(j.world_anchor_b(world.bodies))
        return np.array(nodes)

    rod_edges = np.array([[0, 1], [2, 3]], dtype=np.int32)
    rod_net = ps.register_curve_network("rods", _rod_nodes(), rod_edges)
    rod_net.set_radius(0.003)
    rod_net.set_color((0.4, 0.4, 0.4))

    frame = [0]

    def step_callback():
        # Reset button
        if ps.imgui.Button("Reset"):
            for b, pos in zip(boxes, init_positions):
                _reset_body(b, pos)
            world.time = 0.0
            world.prev_contacts = []
            world.solver._prev_lambda = {}
            frame[0] = 0
            print("--- Reset ---")

        dists = [j.current_length(world.bodies) for j in world.joints]
        ps.imgui.TextUnformatted(
            f"t={world.time:.2f}s  rods=[{', '.join(f'{d:.3f}' for d in dists)}]")

        for _ in range(5):
            world.step()
        frame[0] += 1
        for b, sm in zip(boxes, box_meshes):
            sm.update_vertex_positions(_box_verts(b))
        rod_net.update_node_positions(_rod_nodes())

        if frame[0] % 30 == 0:
            ys = [f"{b.position[1]:.2f}" for b in boxes]
            print(f"t={world.time:.2f}s  rods=[{', '.join(f'{d:.3f}' for d in dists)}]  "
                  f"y=[{', '.join(ys)}]")

    ps.set_user_callback(step_callback)
    ps.show()


if __name__ == "__main__":
    demos = {
        "bounce": demo_bounce, "stack": demo_stack, "incline": demo_incline,
        "pair": demo_pair, "collide": demo_collide,
        "linked": demo_linked, "chain": demo_chain,
    }
    name = sys.argv[1] if len(sys.argv) > 1 else "bounce"
    if name not in demos:
        print(f"Usage: {sys.argv[0]} [{'/'.join(demos)}]")
        sys.exit(1)
    demos[name]()
