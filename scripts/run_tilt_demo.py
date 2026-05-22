#!/usr/bin/env python3
"""Bookshelf domino demo: plain / DCR / tilt / tilt-coupled comparison.

Demonstrates the deformation-aware contact frame extension. A heavy
block drops onto a cantilever shelf; thin upright books respond.

  --plain        : No DCR — books stay still (rigid-only baseline).
  --dcr          : Passive DCR — books jump vertically but don't topple.
  --tilt         : Lateral-only tilt — amplified lateral kicks, no vertical.
  --tilt-coupled : Capped vertical DCR + amplified lateral tilt (default).
  --all          : Run all four and print comparison summary.

Usage:
    uv run python scripts/run_tilt_demo.py --tilt-coupled
    uv run python scripts/run_tilt_demo.py --all
"""
from __future__ import annotations

import sys

import numpy as np

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.rigid.body import quat_to_rot
from dcr.dcr import PassiveDCRCoupler, TiltDCRCoupler, DCRWorld


H = 1e-3
ETA = 0.5
N_STEPS = 2000


def _fix_one_edge(mesh):
    """Fix only the -x edge (cantilever-style)."""
    v = mesh.vertices
    tol = 1e-8
    xmin = v[:, 0].min()
    mask = np.abs(v[:, 0] - xmin) < tol
    return np.where(mask)[0].astype(np.int32)


def build_scene(mode: str):
    """Build the bookshelf scene.

    Args:
        mode: 'plain', 'dcr', 'tilt', or 'tilt-coupled'.

    Returns:
        (world, coupler_or_None, tilt_coupler_or_None, body_info, mesh, title)
    """
    dcr_on = mode in ("dcr", "tilt", "tilt-coupled")
    tilt_on = mode in ("tilt", "tilt-coupled")

    world = DCRWorld(
        h=H, eta=ETA,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=120),
        dcr_enabled=dcr_on,
    )

    # Ground plane at y=0 (catches objects that fall off the shelf).
    ground = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    world.add_body(ground)

    # Shelf: bounded plane elevated above ground, cantilever slab.
    shelf_top = 0.3
    mesh = make_slab_tet_mesh(length=0.8, width=0.3, height=0.03,
                              nx=12, ny=5, nz=2)
    mesh.vertices[:, 1] += shelf_top - 0.015  # shift mesh top to shelf_top
    mat = Material(E=0.5e9 if tilt_on else 8.0e9, nu=0.3, rho=600.0)

    shelf = make_static_plane(normal=(0, 1, 0),
                              point=(0, shelf_top, 0), friction=0.5,
                              bounds=(0.4, 0.15))  # match slab half-extents
    shelf_idx = world.add_body(shelf)

    fixed = _fix_one_edge(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=3.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=12)

    coupler = None
    tilt_coupler = None

    if dcr_on:
        coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=shelf_idx)
        if tilt_on:
            tilt_coupler = TiltDCRCoupler(
                passive=coupler,
                theta_max=np.radians(10.0),
                mu_dcr=0.5,
                eta_t=0.5,
                lateral_fraction=0.3,
                dv_t_max=1.5,
                dv_n_max=0.3,
            )
            world.add_tilt_coupler(tilt_coupler)
            world.tilt_mode = mode  # "tilt" or "tilt-coupled"
        else:
            world.add_passive_coupler(coupler)

    body_info = {}

    # Books: 6 thin tall dominoes standing upright on the shelf.
    book_colors = [
        (0.8, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.8),
        (0.7, 0.5, 0.1), (0.6, 0.2, 0.6),
    ]
    for bi in range(5):
        book_hx, book_hy, book_hz = 0.005, 0.04, 0.03
        bx = -0.15 + bi * 0.04
        book = make_dynamic_box(
            mass=0.3, hx=book_hx, hy=book_hy, hz=book_hz,
            position=(bx, shelf_top + book_hy + 0.001, 0.0),
            restitution=0.0, friction=0.3,
        )
        idx = world.add_body(book)
        body_info[f"book_{bi}"] = (idx, book_hx, book_hy, book_hz,
                                   book_colors[bi])

    # Drop on the free end (right side) of the shelf.
    drop_hx, drop_hy, drop_hz = 0.05, 0.05, 0.05
    drop = make_dynamic_box(
        mass=20.0, hx=drop_hx, hy=drop_hy, hz=drop_hz,
        position=(0.15, shelf_top + drop_hy + 0.6, 0.0),
        restitution=0.1, friction=0.5,
    )
    idx = world.add_body(drop)
    body_info["drop"] = (idx, drop_hx, drop_hy, drop_hz, (0.3, 0.3, 0.3))

    title = {"plain": "Plain Rigid", "dcr": "Passive DCR",
             "tilt": "Tilt (lateral only)",
             "tilt-coupled": "Tilt-Coupled (vert+lat)"}[mode]

    return world, coupler, tilt_coupler, body_info, mesh, title


def simulate(world, body_info, tilt_coupler=None):
    """Settle then simulate, recording positions, orientations, and diagnostics."""
    # Identify impactor
    impactor_names = {"drop"}
    impactor_idxs = []
    for name, (idx, *_) in body_info.items():
        if name in impactor_names:
            impactor_idxs.append(idx)

    # Settle
    for idx in impactor_idxs:
        world.bodies[idx].is_static = True
    old_dcr = world.dcr_enabled
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx_body in range(len(world.bodies)):
        if idx_body not in impactor_idxs and not world.bodies[idx_body].is_static:
            world.bodies[idx_body].velocity[:] = 0.0
    for idx in impactor_idxs:
        world.bodies[idx].is_static = False
    world.dcr_enabled = old_dcr
    world.time = 0.0

    # Record
    times = []
    positions = {name: [] for name in body_info}
    orientations = {name: [] for name in body_info}
    max_lateral_v = {name: 0.0 for name in body_info}
    max_angular_v = {name: 0.0 for name in body_info}
    tilt_angles = []

    for step_i in range(N_STEPS):
        world.step()
        times.append(world.time)
        for name, (idx, *_) in body_info.items():
            positions[name].append(world.bodies[idx].position.copy())
            orientations[name].append(world.bodies[idx].orientation.copy())
            vx = abs(world.bodies[idx].velocity[0])
            wz = abs(world.bodies[idx].velocity[5])
            if vx > max_lateral_v[name]:
                max_lateral_v[name] = vx
            if wz > max_angular_v[name]:
                max_angular_v[name] = wz

        # Tilt diagnostics
        if tilt_coupler is not None and tilt_coupler.last_tilt_results:
            for tr in tilt_coupler.last_tilt_results:
                tilt_angles.append(np.degrees(tr.theta))

    return {
        "times": times,
        "positions": positions,
        "orientations": orientations,
        "max_lateral_v": max_lateral_v,
        "max_angular_v": max_angular_v,
        "tilt_angles": tilt_angles,
    }


def print_summary(mode: str, result: dict):
    """Print diagnostic summary."""
    print(f"\n--- {mode.upper()} ---")
    book_names = [n for n in result["max_lateral_v"] if n.startswith("book")]
    max_vx = max(result["max_lateral_v"][n] for n in book_names)
    max_wz = max(result["max_angular_v"][n] for n in book_names)
    print(f"  Max book lateral velocity (vx): {max_vx*1000:.2f} mm/s")
    print(f"  Max book angular velocity (wz): {max_wz:.4f} rad/s")
    if result["tilt_angles"]:
        angles = result["tilt_angles"]
        print(f"  Tilt angles: min={min(angles):.3f} deg, "
              f"max={max(angles):.3f} deg, mean={np.mean(angles):.3f} deg, "
              f"count={len(angles)}")
    else:
        print(f"  Tilt angles: N/A")

    # Print per-book final position
    for name in book_names:
        pos = result["positions"][name][-1]
        print(f"  {name}: final pos = ({pos[0]:.4f}, {pos[1]:.4f}, {pos[2]:.4f})")


def _box_mesh(hx, hy, hz):
    verts = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ], dtype=np.float64)
    faces = np.array([
        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
        [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5],
    ], dtype=np.int32)
    return verts, faces


def playback(mesh, body_info, result, title):
    """Interactive polyscope playback with rotation."""
    import polyscope as ps

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    surface = mesh.extract_surface()
    ps.register_surface_mesh("shelf_mesh", surface.vertices,
                             surface.faces, color=(0.6, 0.5, 0.35))

    # Ground plane at y=0 (the shelf is elevated above this).
    plane_sz = 2.0
    plane_verts = np.array([
        [-plane_sz, 0.0, -plane_sz],
        [+plane_sz, 0.0, -plane_sz],
        [+plane_sz, 0.0, +plane_sz],
        [-plane_sz, 0.0, +plane_sz],
    ])
    plane_faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    ps.register_surface_mesh("ground_plane", plane_verts, plane_faces,
                             color=(0.85, 0.85, 0.80), transparency=0.3)

    ps_meshes = {}
    box_meshes = {}
    for name, (idx, hx, hy, hz, color) in body_info.items():
        bm = _box_mesh(hx, hy, hz)
        box_meshes[name] = bm
        R0 = quat_to_rot(result["orientations"][name][0])
        pos0 = result["positions"][name][0]
        sm = ps.register_surface_mesh(name, (R0 @ bm[0].T).T + pos0,
                                       bm[1], color=color)
        ps_meshes[name] = sm

    frame_idx = [0]
    is_playing = [True]
    skip = 3
    n_total = len(result["times"])
    n_frames = n_total // skip

    def callback():
        import polyscope.imgui as imgui
        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])

        si = min(frame_idx[0] * skip, n_total - 1)
        imgui.Text(f"{title}  t = {result['times'][si]*1000:.0f} ms")

        if is_playing[0]:
            if frame_idx[0] < n_frames - 1:
                frame_idx[0] += 1
            else:
                is_playing[0] = False

        for name in body_info:
            R = quat_to_rot(result["orientations"][name][si])
            ps_meshes[name].update_vertex_positions(
                (R @ box_meshes[name][0].T).T + result["positions"][name][si])

    ps.set_user_callback(callback)
    ps.show()


def main():
    args = sys.argv[1:]
    if not args:
        args = ["--tilt-coupled"]

    modes = []
    if "--all" in args:
        modes = ["plain", "dcr", "tilt", "tilt-coupled"]
    else:
        for a in args:
            if a.startswith("--"):
                m = a[2:]
                if m in ("plain", "dcr", "tilt", "tilt-coupled"):
                    modes.append(m)
    if not modes:
        modes = ["tilt-coupled"]

    results = {}
    last_mesh = None
    last_body_info = None

    for mode in modes:
        print(f"\n{'='*60}")
        print(f"Building scene: {mode}")
        print(f"{'='*60}")
        world, coupler, tilt_coupler, body_info, mesh, title = build_scene(mode)
        print(f"  Bodies: {len(world.bodies)}")

        print(f"Simulating ({N_STEPS * H:.1f}s)...")
        result = simulate(world, body_info, tilt_coupler)
        results[mode] = result
        last_mesh = mesh
        last_body_info = body_info

        print_summary(mode, result)

    # Show polyscope for the last mode
    if last_mesh is not None:
        last_mode = modes[-1]
        title = {"plain": "Plain Rigid", "dcr": "Passive DCR",
                 "tilt": "Tilt (lateral only)",
                 "tilt-coupled": "Tilt-Coupled (vert+lat)"}[last_mode]
        print(f"\nLaunching polyscope ({title})...")
        playback(last_mesh, last_body_info, results[last_mode], title)


if __name__ == "__main__":
    main()
