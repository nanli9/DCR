"""Stage 5 visualization: 'Dinner is served' DCR demo.

An elastic table with plates resting on it. A heavy pot drops onto the table.
With DCR enabled, the plates jump from the transmitted vibration.
Without DCR, the plates stay still.

Usage:
    python scripts/run_stage5.py          # DCR enabled (default)
    python scripts/run_stage5.py --no-dcr # DCR disabled for comparison
"""
import sys
import numpy as np
import polyscope as ps

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.rigid import (
    make_dynamic_box, make_static_plane,
    ConstraintSolver,
)
from dcr.dcr import ModalDCRCoupler, DCRWorld
from dcr.rigid.body import quat_to_rot


def main() -> None:
    dcr_on = "--no-dcr" not in sys.argv

    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=dcr_on,
    )

    # --- Table (static plane at slab top surface + elastic FEM) ---
    table_top = 0.025  # height/2 of slab
    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    tol = 1e-8
    x_min, x_max = mesh.vertices[:, 0].min(), mesh.vertices[:, 0].max()
    z_min, z_max = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    on_xmin = np.abs(mesh.vertices[:, 0] - x_min) < tol
    on_xmax = np.abs(mesh.vertices[:, 0] - x_max) < tol
    on_zmin = np.abs(mesh.vertices[:, 2] - z_min) < tol
    on_zmax = np.abs(mesh.vertices[:, 2] - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)
    fem_model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                         alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem_model, num_modes=10)
    coupler = ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_dcr_coupler(coupler)

    # --- Plates (resting on top of slab) ---
    plate_hy = 0.02
    plate_positions = [
        (-0.3, table_top + plate_hy + 0.001, 0.15),
        (0.3, table_top + plate_hy + 0.001, -0.1),
        (0.0, table_top + plate_hy + 0.001, -0.2),
    ]
    plate_indices = []
    for pos in plate_positions:
        plate = make_dynamic_box(
            mass=0.2, hx=0.06, hy=plate_hy, hz=0.06,
            position=pos, restitution=0.0, friction=0.5,
        )
        plate_indices.append(world.add_body(plate))

    # --- Heavy pot ---
    pot_hy = 0.08
    pot = make_dynamic_box(
        mass=5.0, hx=0.08, hy=pot_hy, hz=0.08,
        position=(0.0, table_top + pot_hy + 0.8, 0.0),
        restitution=0.1, friction=0.5,
    )
    pot_idx = world.add_body(pot)

    # Settle plates.
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in plate_indices:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = dcr_on

    mode = "DCR ON" if dcr_on else "DCR OFF"
    print(f"=== Stage 5: Dinner-is-served demo ({mode}) ===")
    print(f"Table: {mesh.num_vertices} verts, {mesh.num_tets} tets")
    print(f"Plates: {len(plate_indices)}, Pot mass: 5.0 kg")

    # Record trajectory for polyscope playback.
    n_sim_steps = 600
    record_every = 5
    frames = []

    for step_i in range(n_sim_steps):
        contacts = world.step()

        if step_i % record_every == 0:
            frame = {
                "pot": world.bodies[pot_idx].position.copy(),
                "pot_ori": world.bodies[pot_idx].orientation.copy(),
                "plates": [world.bodies[idx].position.copy() for idx in plate_indices],
                "plate_oris": [world.bodies[idx].orientation.copy() for idx in plate_indices],
                "time": world.time,
            }
            frames.append(frame)

        # Log key events.
        new_on_table = [c for c in contacts if c.is_new and
                        (c.body_a == table_idx or c.body_b == table_idx) and
                        (c.body_a == pot_idx or c.body_b == pot_idx)]
        if new_on_table:
            plate_vys = [world.bodies[idx].velocity[1] for idx in plate_indices]
            max_vy = max(plate_vys)
            print(f"  Step {step_i}: POT IMPACT! plate max vy = {max_vy:.4f} m/s")

    # Final stats.
    for i, idx in enumerate(plate_indices):
        pos = world.bodies[idx].position
        print(f"  Plate {i}: final y = {pos[1]:.4f} m, vy = {world.bodies[idx].velocity[1]:.4f} m/s")

    # --- Polyscope playback ---
    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Register table surface.
    table_surface = mesh.extract_surface()
    ps.register_surface_mesh("table", table_surface.vertices, table_surface.faces,
                             color=(0.6, 0.4, 0.2))

    # Register pot and plates as boxes (just point clouds for now).
    pot_mesh = _box_mesh(0.08, 0.08, 0.08)
    plate_meshes = [_box_mesh(0.06, 0.02, 0.06) for _ in plate_indices]

    pot_ps = ps.register_surface_mesh("pot", pot_mesh[0] + frames[0]["pot"],
                                       pot_mesh[1], color=(0.3, 0.3, 0.3))
    plate_ps = []
    for i in range(len(plate_indices)):
        pm = ps.register_surface_mesh(
            f"plate_{i}",
            plate_meshes[i][0] + frames[0]["plates"][i],
            plate_meshes[i][1],
            color=(0.8, 0.2, 0.2),
        )
        plate_ps.append(pm)

    frame_idx = [0]
    is_playing = [True]
    n_frames = len(frames)

    def callback() -> None:
        import polyscope.imgui as imgui

        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])

        fi = frame_idx[0]
        t_ms = frames[fi]["time"] * 1000
        imgui.Text(f"t = {t_ms:.1f} ms  ({mode})")

        if is_playing[0]:
            frame_idx[0] = (frame_idx[0] + 1) % n_frames

        R_pot = quat_to_rot(frames[fi]["pot_ori"])
        pot_ps.update_vertex_positions(
            (R_pot @ pot_mesh[0].T).T + frames[fi]["pot"])
        for i in range(len(plate_indices)):
            R_pl = quat_to_rot(frames[fi]["plate_oris"][i])
            plate_ps[i].update_vertex_positions(
                (R_pl @ plate_meshes[i][0].T).T + frames[fi]["plates"][i])

    ps.set_user_callback(callback)
    ps.show()


def _box_mesh(hx: float, hy: float, hz: float):
    """Simple box mesh (8 verts, 12 faces) centered at origin."""
    verts = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz],
    ], dtype=np.float64)
    faces = np.array([
        [0,2,1],[0,3,2], [4,5,6],[4,6,7],
        [0,1,5],[0,5,4], [2,3,7],[2,7,6],
        [0,4,7],[0,7,3], [1,2,6],[1,6,5],
    ], dtype=np.int32)
    return verts, faces


if __name__ == "__main__":
    main()
