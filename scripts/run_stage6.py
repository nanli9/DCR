"""Stage 6 visualization: spatial attenuation DCR on a long slab.

A heavy impactor hits one end of a 2m slab; boxes at varying distances
respond with decreasing velocity, demonstrating the s = C r^{-β}
attenuation law (Eq. 14).

Usage:
    python scripts/run_stage6.py          # Default: β=0.5
    python scripts/run_stage6.py --beta 1 # Volume-like attenuation
"""
import sys
import numpy as np
import polyscope as ps

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.dcr import DCRWorld, SpatialDCRCoupler
from dcr.rigid.body import quat_to_rot


def main() -> None:
    beta = 0.5
    for i, arg in enumerate(sys.argv):
        if arg == "--beta" and i + 1 < len(sys.argv):
            beta = float(sys.argv[i + 1])

    # --- Build FEM model for a long slab ---
    length, width, height = 2.0, 0.3, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=20, ny=3, nz=2)
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

    # --- World setup ---
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    # Physics plane at the top surface of the slab (y = height/2).
    table_top = height / 2  # 0.025
    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    coupler = SpatialDCRCoupler(
        modal=modal, elastic_body_idx=table_idx,
        C=2.0, beta=beta,
    )
    world.add_spatial_coupler(coupler)

    # --- Lighter boxes at varying distances (lighter = jump higher) ---
    box_hy = 0.02
    box_xs = [-0.5, -0.2, 0.1, 0.4, 0.7]
    box_idxs = []
    for x in box_xs:
        box = make_dynamic_box(
            0.05, 0.04, box_hy, 0.04,
            position=(x, table_top + box_hy + 0.001, 0.0),
            restitution=0.0, friction=0.5,
        )
        box_idxs.append(world.add_body(box))

    # --- Heavy impactor dropped from higher ---
    imp_hy = 0.08
    impactor = make_dynamic_box(
        10.0, 0.08, imp_hy, 0.08,
        position=(-0.9, table_top + imp_hy + 1.5, 0.0),
        restitution=0.1, friction=0.5,
    )
    imp_idx = world.add_body(impactor)

    # Settle boxes.
    world.bodies[imp_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in box_idxs:
        world.bodies[idx].velocity[:] = 0
    world.bodies[imp_idx].is_static = False
    world.dcr_enabled = True

    print(f"=== Stage 6: Spatial Attenuation DCR (β={beta}) ===")
    print(f"Slab: {mesh.num_vertices} verts, impactor: 5 kg")
    print(f"Boxes at x = {box_xs}")

    # --- Simulate ---
    n_steps = 1200
    record_every = 5
    frames = []
    max_vys = [0.0] * len(box_idxs)

    for step_i in range(n_steps):
        contacts = world.step()

        for i, idx in enumerate(box_idxs):
            vy = world.bodies[idx].velocity[1]
            if vy > max_vys[i]:
                max_vys[i] = vy

        if step_i % record_every == 0:
            frames.append({
                "imp": world.bodies[imp_idx].position.copy(),
                "imp_ori": world.bodies[imp_idx].orientation.copy(),
                "boxes": [world.bodies[idx].position.copy() for idx in box_idxs],
                "box_oris": [world.bodies[idx].orientation.copy() for idx in box_idxs],
                "time": world.time,
            })

    print("\nBox responses (max upward vy):")
    for i, x in enumerate(box_xs):
        print(f"  x={x:+.1f}: vy = {max_vys[i]:.4f} m/s")

    # --- Polyscope playback ---
    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    surface = mesh.extract_surface()
    ps.register_surface_mesh("slab", surface.vertices, surface.faces,
                             color=(0.5, 0.35, 0.2))

    imp_mesh = _box_mesh(0.06, 0.06, 0.06)
    box_meshes = [_box_mesh(0.04, 0.02, 0.04) for _ in box_idxs]

    imp_ps = ps.register_surface_mesh("impactor", imp_mesh[0] + frames[0]["imp"],
                                       imp_mesh[1], color=(0.3, 0.3, 0.3))
    box_ps = []
    for i in range(len(box_idxs)):
        bm = ps.register_surface_mesh(
            f"box_{i}", box_meshes[i][0] + frames[0]["boxes"][i],
            box_meshes[i][1], color=(0.8, 0.3, 0.1),
        )
        box_ps.append(bm)

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
        imgui.Text(f"t = {t_ms:.1f} ms, beta = {beta}")
        if is_playing[0]:
            frame_idx[0] = (frame_idx[0] + 1) % n_frames
        R_imp = quat_to_rot(frames[fi]["imp_ori"])
        imp_ps.update_vertex_positions(
            (R_imp @ imp_mesh[0].T).T + frames[fi]["imp"])
        for i in range(len(box_idxs)):
            R_box = quat_to_rot(frames[fi]["box_oris"][i])
            box_ps[i].update_vertex_positions(
                (R_box @ box_meshes[i][0].T).T + frames[fi]["boxes"][i])

    ps.set_user_callback(callback)
    ps.show()


def _box_mesh(hx, hy, hz):
    verts = np.array([
        [-hx,-hy,-hz],[hx,-hy,-hz],[hx,hy,-hz],[-hx,hy,-hz],
        [-hx,-hy,hz],[hx,-hy,hz],[hx,hy,hz],[-hx,hy,hz],
    ], dtype=np.float64)
    faces = np.array([
        [0,2,1],[0,3,2],[4,5,6],[4,6,7],
        [0,1,5],[0,5,4],[2,3,7],[2,7,6],
        [0,4,7],[0,7,3],[1,2,6],[1,6,5],
    ], dtype=np.int32)
    return verts, faces


if __name__ == "__main__":
    main()
