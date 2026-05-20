"""Stage E3 visualization: Passive energy-bounded DCR demo.

Side-by-side comparison:
  - Original DCR (forced IIR, Stage 5)
  - Passive DCR (energy-bounded velocity kick, Stage E3) at eta=0.3 and eta=1.0

Shows the dinner-is-served scene with energy tracking overlay.

Usage:
    python scripts/run_stageE3.py                # polyscope interactive
    python scripts/run_stageE3.py --plot-only     # just energy plots, no polyscope
"""
import sys
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.dcr import ModalDCRCoupler, PassiveDCRCoupler, DCRWorld

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "stageE3")
os.makedirs(OUT_DIR, exist_ok=True)

N_SIM_STEPS = 800
H = 1e-3


def _build_fem_modal():
    """Build the shared FEM/modal model (table slab)."""
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
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
    return mesh, ModalAnalysis(fem=fem_model, num_modes=10)


def _build_scene_original(mesh, modal):
    """Build scene with original forced-IIR DCR (Stage 5)."""
    world = DCRWorld(h=H,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=80))
    table_top = 0.025
    table = make_static_plane(normal=(0, 1, 0), point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)
    coupler = ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_dcr_coupler(coupler)
    plate_indices = _add_plates_and_pot(world, table_top)
    return world, plate_indices, None


def _build_scene_passive(mesh, modal, eta):
    """Build scene with passive energy-bounded DCR (Stage E3)."""
    world = DCRWorld(h=H, eta=eta,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=80))
    table_top = 0.025
    table = make_static_plane(normal=(0, 1, 0), point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)
    plate_indices = _add_plates_and_pot(world, table_top)
    return world, plate_indices, coupler


def _add_plates_and_pot(world, table_top):
    plate_hy = 0.02
    plate_indices = []
    for pos in [(-0.3, table_top + plate_hy + 0.001, 0.15),
                (0.3, table_top + plate_hy + 0.001, -0.1),
                (0.0, table_top + plate_hy + 0.001, -0.2)]:
        plate = make_dynamic_box(mass=0.2, hx=0.06, hy=plate_hy, hz=0.06,
                                 position=pos, restitution=0.0, friction=0.5)
        plate_indices.append(world.add_body(plate))
    pot = make_dynamic_box(mass=5.0, hx=0.08, hy=0.08, hz=0.08,
                           position=(0.0, table_top + 0.08 + 0.8, 0.0),
                           restitution=0.1, friction=0.5)
    world.add_body(pot)
    return plate_indices


def _settle(world, plate_indices, n_steps=200):
    pot_idx = len(world.bodies) - 1
    world.bodies[pot_idx].is_static = True
    old_dcr = world.dcr_enabled
    world.dcr_enabled = False
    for _ in range(n_steps):
        world.step()
    for idx in plate_indices:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = old_dcr


def _run_sim(world, plate_indices, coupler=None):
    """Run simulation and collect diagnostics."""
    pot_idx = len(world.bodies) - 1
    times = []
    plate_vy = [[] for _ in plate_indices]
    plate_y = [[] for _ in plate_indices]
    plate_pos = [[] for _ in plate_indices]
    pot_pos = []
    cum_injected = []
    cum_loss = []
    c_inj = 0.0
    c_loss = 0.0

    omega = coupler.modal.frequencies if coupler else None

    for step_i in range(N_SIM_STEPS):
        world.step()
        times.append(world.time)

        for i, idx in enumerate(plate_indices):
            plate_vy[i].append(world.bodies[idx].velocity[1])
            plate_y[i].append(world.bodies[idx].position[1])
            plate_pos[i].append(world.bodies[idx].position.copy())

        pot_pos.append(world.bodies[pot_idx].position.copy())

        if coupler is not None:
            dE = max(0.0, coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick)
            c_inj += dE
            c_loss += world.last_E_loss
        cum_injected.append(c_inj)
        cum_loss.append(c_loss)

    return {
        "times": np.array(times),
        "plate_vy": [np.array(v) for v in plate_vy],
        "plate_y": [np.array(y) for y in plate_y],
        "plate_pos": [np.array(p) for p in plate_pos],
        "pot_pos": np.array(pot_pos),
        "cum_injected": np.array(cum_injected),
        "cum_loss": np.array(cum_loss),
    }


def make_plots(results_orig, results_03, results_10):
    """Generate comparison plots."""
    times = results_orig["times"]

    # --- Plot 1: Plate vertical velocity comparison ---
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    labels = ["Original DCR", "Passive (η=0.3)", "Passive (η=1.0)"]
    colors = ["blue", "orange", "green"]
    all_results = [results_orig, results_03, results_10]

    for ax_i, (res, label, color) in enumerate(zip(all_results, labels, colors)):
        ax = axes[ax_i]
        for i in range(3):
            ax.plot(res["times"] * 1000, res["plate_vy"][i] * 1000,
                    linewidth=0.5, alpha=0.8,
                    label=f"Plate {i}" if ax_i == 0 else None)
        ax.set_ylabel("vy (mm/s)")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, times[-1] * 1000)

    axes[0].legend(fontsize=8)
    axes[-1].set_xlabel("Time (ms)")
    fig.suptitle("Stage E3: Plate vertical velocity — Original vs Passive DCR", y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "plate_velocity_comparison.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved plate_velocity_comparison.png")

    # --- Plot 2: Energy invariant (eta=1.0) ---
    fig, ax = plt.subplots(figsize=(10, 5))
    t_ms = results_10["times"] * 1000
    ax.plot(t_ms, results_10["cum_loss"], "r-", linewidth=1.5,
            label="η · Σ E_loss (η=1.0)")
    ax.plot(t_ms, results_10["cum_injected"], "b-", linewidth=1.5,
            label="Σ E_modal_injected")
    ax.fill_between(t_ms, results_10["cum_injected"], results_10["cum_loss"],
                    alpha=0.15, color="green", label="headroom")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Cumulative energy (J)")
    ax.set_title("Stage E3: Energy invariant — cumulative injection ≤ cumulative loss")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "energy_invariant.png"), dpi=150)
    plt.close(fig)
    print("  Saved energy_invariant.png")

    # --- Plot 3: Plate Y position (height) comparison ---
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    for ax_i, (res, label, color) in enumerate(zip(all_results, labels, colors)):
        ax = axes[ax_i]
        for i in range(3):
            y0 = res["plate_y"][i][0]
            dy = (res["plate_y"][i] - y0) * 1000  # mm
            ax.plot(res["times"] * 1000, dy, linewidth=0.8, label=f"Plate {i}")
        ax.set_xlabel("Time (ms)")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        if ax_i == 0:
            ax.set_ylabel("Δy (mm)")
            ax.legend(fontsize=8)
    fig.suptitle("Stage E3: Plate vertical displacement", y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "plate_displacement_comparison.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  Saved plate_displacement_comparison.png")


def run_polyscope(mesh, modal, results_03, results_10, plate_indices_03):
    """Interactive polyscope playback of passive DCR (eta=1.0)."""
    import polyscope as ps

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Table surface
    table_surface = mesh.extract_surface()
    ps.register_surface_mesh("table", table_surface.vertices,
                             table_surface.faces, color=(0.6, 0.4, 0.2))

    # Show eta=1.0 results for maximum visual effect
    res = results_10

    plate_meshes = [_box_mesh(0.06, 0.02, 0.06) for _ in range(3)]
    pot_mesh_vf = _box_mesh(0.08, 0.08, 0.08)

    # Register pot
    pot_ps = ps.register_surface_mesh(
        "pot", pot_mesh_vf[0] + res["pot_pos"][0],
        pot_mesh_vf[1], color=(0.3, 0.3, 0.3))

    # Register plates
    plate_ps = []
    for i in range(3):
        pm = ps.register_surface_mesh(
            f"plate_{i}",
            plate_meshes[i][0] + res["plate_pos"][i][0],
            plate_meshes[i][1],
            color=(0.8, 0.2, 0.2))
        plate_ps.append(pm)

    frame_idx = [0]
    is_playing = [True]
    record_every = 5
    n_total = len(res["times"])
    n_frames = n_total // record_every

    def callback():
        import polyscope.imgui as imgui
        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])

        si = min(frame_idx[0] * record_every, n_total - 1)
        t_ms = res["times"][si] * 1000
        imgui.Text(f"Passive DCR (eta=1.0)  t = {t_ms:.1f} ms")
        imgui.Text(f"Cum injected: {res['cum_injected'][si]:.4f} J")
        imgui.Text(f"Cum loss:     {res['cum_loss'][si]:.4f} J")

        if is_playing[0]:
            frame_idx[0] = (frame_idx[0] + 1) % n_frames

        # Update pot position
        pot_ps.update_vertex_positions(pot_mesh_vf[0] + res["pot_pos"][si])

        # Update plate positions
        for i in range(3):
            plate_ps[i].update_vertex_positions(
                plate_meshes[i][0] + res["plate_pos"][i][si])

    ps.set_user_callback(callback)
    ps.show()


def _box_mesh(hx, hy, hz):
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


def main():
    plot_only = "--plot-only" in sys.argv
    print("Stage E3: Passive energy-bounded DCR demo\n")

    print("Building FEM/modal model...")
    mesh, modal = _build_fem_modal()
    print(f"  {mesh.num_vertices} verts, {mesh.num_tets} tets, "
          f"{modal.num_modes} modes\n")

    # --- Run original DCR ---
    print("Running original DCR (forced IIR)...")
    world_orig, plates_orig, _ = _build_scene_original(mesh, modal)
    _settle(world_orig, plates_orig)
    results_orig = _run_sim(world_orig, plates_orig)
    max_vy_orig = max(max(r) for r in results_orig["plate_vy"])
    print(f"  Max plate vy: {max_vy_orig*1000:.2f} mm/s\n")

    # --- Run passive DCR eta=0.3 ---
    print("Running passive DCR (eta=0.3)...")
    world_03, plates_03, coupler_03 = _build_scene_passive(mesh, modal, eta=0.3)
    _settle(world_03, plates_03)
    results_03 = _run_sim(world_03, plates_03, coupler_03)
    max_vy_03 = max(max(r) for r in results_03["plate_vy"])
    print(f"  Max plate vy: {max_vy_03*1000:.2f} mm/s")
    print(f"  Cum injected: {results_03['cum_injected'][-1]:.6f} J")
    print(f"  Cum loss:     {results_03['cum_loss'][-1]:.6f} J\n")

    # --- Run passive DCR eta=1.0 ---
    print("Running passive DCR (eta=1.0)...")
    world_10, plates_10, coupler_10 = _build_scene_passive(mesh, modal, eta=1.0)
    _settle(world_10, plates_10)
    results_10 = _run_sim(world_10, plates_10, coupler_10)
    max_vy_10 = max(max(r) for r in results_10["plate_vy"])
    print(f"  Max plate vy: {max_vy_10*1000:.2f} mm/s")
    print(f"  Cum injected: {results_10['cum_injected'][-1]:.6f} J")
    print(f"  Cum loss:     {results_10['cum_loss'][-1]:.6f} J\n")

    # Amplitude ratio
    if max_vy_orig > 1e-10:
        print(f"Amplitude ratios vs original DCR:")
        print(f"  eta=0.3: {max_vy_03/max_vy_orig:.3f}x")
        print(f"  eta=1.0: {max_vy_10/max_vy_orig:.3f}x\n")

    # Generate plots
    print("Generating plots...")
    make_plots(results_orig, results_03, results_10)

    if not plot_only:
        print("\nLaunching polyscope...")
        run_polyscope(mesh, modal, results_03, results_10, plates_03)
    else:
        print("\nDone (--plot-only mode).")


if __name__ == "__main__":
    main()
