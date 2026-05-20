"""Stage 7: End-to-end scenes and ground-truth comparison.

Reproduces two scenes from the paper and generates a qualitative
ground-truth comparison between DCR-augmented rigid simulation and
a fully-coupled FEM deformable simulation.

Usage:
    python scripts/run_stage7.py                # Dinner scene (polyscope, pre-recorded)
    python scripts/run_stage7.py dinner         # Dinner scene (polyscope, pre-recorded)
    python scripts/run_stage7.py spatial        # Spatial attenuation (polyscope, pre-recorded)
    python scripts/run_stage7.py compare        # DCR vs ground-truth (matplotlib)
    python scripts/run_stage7.py --realtime     # Dinner scene, physics stepping live
    python scripts/run_stage7.py spatial --realtime  # Spatial scene, physics live
    python scripts/run_stage7.py --save         # Save all GIFs to docs/stage7/
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.patches as mpatches

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel, NewmarkIntegrator, SimpleRigidBody, CoupledFEMRigidSim
from dcr.modal import ModalAnalysis
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.dcr import ModalDCRCoupler, SpatialDCRCoupler, DCRWorld

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "stage7"


# ======================================================================
# Shared helpers
# ======================================================================

def _fix_corners(mesh) -> np.ndarray:
    """Return indices of corner nodes (x-min/max AND z-min/max)."""
    v = mesh.vertices
    tol = 1e-8
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    mask = (((np.abs(v[:, 0] - xmin) < tol) | (np.abs(v[:, 0] - xmax) < tol)) &
            ((np.abs(v[:, 2] - zmin) < tol) | (np.abs(v[:, 2] - zmax) < tol)))
    return np.where(mask)[0].astype(np.int32)


# ======================================================================
# Scene 1 — "Dinner is served" (modal DCR)
# ======================================================================

def run_dinner() -> dict:
    """Run the 'dinner is served' scene and return trajectory data."""
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    # Elastic table.
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    table_top = height / 2
    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=10)
    coupler = ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_dcr_coupler(coupler)

    # Plates.
    plate_hy = 0.02
    plate_positions = [
        (-0.3, table_top + plate_hy + 0.001, 0.15),
        (0.3, table_top + plate_hy + 0.001, -0.1),
        (0.0, table_top + plate_hy + 0.001, -0.2),
    ]
    plate_idxs = []
    for pos in plate_positions:
        p = make_dynamic_box(0.2, 0.06, plate_hy, 0.06,
                             position=pos, restitution=0.0, friction=0.5)
        plate_idxs.append(world.add_body(p))

    # Heavy pot.
    pot_hy = 0.08
    pot = make_dynamic_box(5.0, 0.08, pot_hy, 0.08,
                           position=(0.0, table_top + pot_hy + 0.8, 0.0),
                           restitution=0.1, friction=0.5)
    pot_idx = world.add_body(pot)

    # Settle.
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in plate_idxs:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = True

    # Simulate.
    n_steps = 800
    times, pot_ys, plate_ys, plate_vys = [], [], [], []
    for step_i in range(n_steps):
        world.step()
        times.append(world.time)
        pot_ys.append(world.bodies[pot_idx].position[1])
        plate_ys.append([world.bodies[i].position[1] for i in plate_idxs])
        plate_vys.append([world.bodies[i].velocity[1] for i in plate_idxs])

    return {
        "times": np.array(times),
        "pot_y": np.array(pot_ys),
        "plate_ys": np.array(plate_ys),
        "plate_vys": np.array(plate_vys),
        "table_top": table_top,
        "table_length": length,
        "plate_positions": plate_positions,
    }


def render_dinner_mp4(data: dict, path: Path) -> None:
    """Render a side-view animation of the dinner scene."""
    times = data["times"]
    pot_y = data["pot_y"]
    plate_ys = data["plate_ys"]
    table_top = data["table_top"]
    n_frames = len(times)
    n_plates = plate_ys.shape[1]

    fig, (ax_scene, ax_vel) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Stage 7 — Dinner is Served (Modal DCR)", fontsize=13)

    # Scene view (side view: X vs Y).
    ax_scene.set_xlim(-0.6, 0.6)
    ax_scene.set_ylim(-0.05, 1.1)
    ax_scene.set_xlabel("x [m]")
    ax_scene.set_ylabel("y [m]")
    ax_scene.set_aspect("equal")
    ax_scene.set_title("Side view")

    # Table line.
    ax_scene.axhline(table_top, color="sienna", lw=3, label="table")

    pot_rect = mpatches.FancyBboxPatch(
        (-0.08, pot_y[0] - 0.08), 0.16, 0.16,
        boxstyle="round,pad=0.005", fc="gray", ec="black", lw=1)
    ax_scene.add_patch(pot_rect)

    plate_xs = [p[0] for p in data["plate_positions"]]
    plate_rects = []
    colours = ["#cc3333", "#3366cc", "#33aa33"]
    for i in range(n_plates):
        r = mpatches.FancyBboxPatch(
            (plate_xs[i] - 0.06, plate_ys[0, i] - 0.02), 0.12, 0.04,
            boxstyle="round,pad=0.003", fc=colours[i], ec="black", lw=0.8)
        ax_scene.add_patch(r)
        plate_rects.append(r)

    time_text = ax_scene.text(0.02, 0.95, "", transform=ax_scene.transAxes,
                              fontsize=10, verticalalignment="top")

    # Velocity plot.
    ax_vel.set_xlim(0, times[-1] * 1000)
    vy_max = max(0.05, np.max(np.abs(data["plate_vys"])) * 1.3)
    ax_vel.set_ylim(-vy_max, vy_max)
    ax_vel.set_xlabel("time [ms]")
    ax_vel.set_ylabel("plate vy [m/s]")
    ax_vel.set_title("Plate Y-velocity")
    ax_vel.axhline(0, color="gray", lw=0.5)

    vel_lines = []
    for i in range(n_plates):
        ln, = ax_vel.plot([], [], color=colours[i], lw=1.2,
                          label=f"plate {i}")
        vel_lines.append(ln)
    ax_vel.legend(fontsize=8, loc="upper right")

    vline = ax_vel.axvline(0, color="black", lw=0.5, ls="--")

    fig.tight_layout(rect=[0, 0, 1, 0.93])

    skip = max(1, n_frames // 300)

    def update(frame_i):
        fi = frame_i * skip
        if fi >= n_frames:
            fi = n_frames - 1
        t_ms = times[fi] * 1000

        pot_rect.set_y(pot_y[fi] - 0.08)
        for i in range(n_plates):
            plate_rects[i].set_y(plate_ys[fi, i] - 0.02)

        time_text.set_text(f"t = {t_ms:.1f} ms")

        for i in range(n_plates):
            vel_lines[i].set_data(times[:fi + 1] * 1000,
                                  data["plate_vys"][:fi + 1, i])
        vline.set_xdata([t_ms])
        return [pot_rect, time_text, vline] + plate_rects + vel_lines

    n_anim_frames = n_frames // skip
    anim = FuncAnimation(fig, update, frames=n_anim_frames, interval=33, blit=False)
    anim.save(str(path), writer="pillow", fps=30)
    plt.close(fig)
    print(f"  Saved {path}")


# ======================================================================
# Scene 2 — Spatial attenuation
# ======================================================================

def run_spatial(beta: float = 0.5) -> dict:
    """Run the spatial attenuation scene and return trajectory data."""
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    length, width, height = 2.0, 0.3, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=20, ny=3, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    table_top = height / 2

    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=10)
    coupler = SpatialDCRCoupler(modal=modal, elastic_body_idx=table_idx,
                                C=2.0, beta=beta)
    world.add_spatial_coupler(coupler)

    # Response boxes at varying distances.
    box_hy = 0.02
    box_xs = [-0.5, -0.2, 0.1, 0.4, 0.7]
    box_idxs = []
    for x in box_xs:
        b = make_dynamic_box(0.05, 0.04, box_hy, 0.04,
                             position=(x, table_top + box_hy + 0.001, 0.0),
                             restitution=0.0, friction=0.5)
        box_idxs.append(world.add_body(b))

    # Heavy impactor.
    imp_hy = 0.08
    imp = make_dynamic_box(10.0, 0.08, imp_hy, 0.08,
                           position=(-0.9, table_top + imp_hy + 1.5, 0.0),
                           restitution=0.1, friction=0.5)
    imp_idx = world.add_body(imp)

    # Settle.
    world.bodies[imp_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in box_idxs:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[imp_idx].is_static = False
    world.dcr_enabled = True

    # Simulate.
    n_steps = 1200
    times, imp_ys, box_ys, box_vys = [], [], [], []
    for step_i in range(n_steps):
        world.step()
        times.append(world.time)
        imp_ys.append(world.bodies[imp_idx].position[1])
        box_ys.append([world.bodies[i].position[1] for i in box_idxs])
        box_vys.append([world.bodies[i].velocity[1] for i in box_idxs])

    return {
        "times": np.array(times),
        "imp_y": np.array(imp_ys),
        "box_ys": np.array(box_ys),
        "box_vys": np.array(box_vys),
        "table_top": table_top,
        "box_xs": box_xs,
        "beta": beta,
        "slab_length": length,
    }


def render_spatial_mp4(data: dict, path: Path) -> None:
    """Render a side-view animation of the spatial attenuation scene."""
    times = data["times"]
    imp_y = data["imp_y"]
    box_ys = data["box_ys"]
    table_top = data["table_top"]
    box_xs = data["box_xs"]
    n_frames = len(times)
    n_boxes = len(box_xs)

    fig, (ax_scene, ax_vel) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Stage 7 — Spatial Attenuation DCR "
                 f"(\u03b2={data['beta']})", fontsize=13)

    ax_scene.set_xlim(-1.1, 1.1)
    ax_scene.set_ylim(-0.1, 1.8)
    ax_scene.set_xlabel("x [m]")
    ax_scene.set_ylabel("y [m]")
    ax_scene.set_aspect("equal")
    ax_scene.set_title("Side view")

    # Slab.
    slab_hw = data["slab_length"] / 2
    ax_scene.plot([-slab_hw, slab_hw], [table_top, table_top],
                  color="sienna", lw=4)

    imp_rect = mpatches.FancyBboxPatch(
        (-0.9 - 0.08, imp_y[0] - 0.08), 0.16, 0.16,
        boxstyle="round,pad=0.005", fc="gray", ec="black", lw=1)
    ax_scene.add_patch(imp_rect)

    cmap = plt.cm.viridis
    box_colours = [cmap(i / max(1, n_boxes - 1)) for i in range(n_boxes)]
    box_rects = []
    for i in range(n_boxes):
        r = mpatches.FancyBboxPatch(
            (box_xs[i] - 0.04, box_ys[0, i] - 0.02), 0.08, 0.04,
            boxstyle="round,pad=0.003", fc=box_colours[i], ec="black", lw=0.8)
        ax_scene.add_patch(r)
        box_rects.append(r)

    time_text = ax_scene.text(0.02, 0.95, "", transform=ax_scene.transAxes,
                              fontsize=10, verticalalignment="top")

    # Velocity plot.
    ax_vel.set_xlim(0, times[-1] * 1000)
    vy_max = max(0.05, np.max(np.abs(data["box_vys"])) * 1.3)
    ax_vel.set_ylim(-vy_max * 0.5, vy_max)
    ax_vel.set_xlabel("time [ms]")
    ax_vel.set_ylabel("box vy [m/s]")
    ax_vel.set_title("Box Y-velocity vs distance")
    ax_vel.axhline(0, color="gray", lw=0.5)

    vel_lines = []
    for i in range(n_boxes):
        ln, = ax_vel.plot([], [], color=box_colours[i], lw=1.2,
                          label=f"x={box_xs[i]:+.1f}")
        vel_lines.append(ln)
    ax_vel.legend(fontsize=7, loc="upper right")
    vline = ax_vel.axvline(0, color="black", lw=0.5, ls="--")

    fig.tight_layout(rect=[0, 0, 1, 0.93])

    skip = max(1, n_frames // 300)

    def update(frame_i):
        fi = frame_i * skip
        if fi >= n_frames:
            fi = n_frames - 1
        t_ms = times[fi] * 1000

        imp_rect.set_y(imp_y[fi] - 0.08)
        for i in range(n_boxes):
            box_rects[i].set_y(box_ys[fi, i] - 0.02)

        time_text.set_text(f"t = {t_ms:.1f} ms")

        for i in range(n_boxes):
            vel_lines[i].set_data(times[:fi + 1] * 1000,
                                  data["box_vys"][:fi + 1, i])
        vline.set_xdata([t_ms])
        return [imp_rect, time_text, vline] + box_rects + vel_lines

    n_anim_frames = n_frames // skip
    anim = FuncAnimation(fig, update, frames=n_anim_frames, interval=33, blit=False)
    anim.save(str(path), writer="pillow", fps=30)
    plt.close(fig)
    print(f"  Saved {path}")


# ======================================================================
# Comparison — DCR vs ground truth
# ======================================================================

def run_comparison() -> tuple[dict, dict]:
    """Run both DCR and ground-truth sims and return trajectory data."""
    # Shared FEM model (small for speed).
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=6, ny=4, nz=1)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=10)
    table_top = mesh.vertices[:, 1].max()

    # Use a low drop height so the pot impacts quickly in both sims.
    # 0.05m free-fall takes sqrt(2*0.05/9.81) ≈ 0.10s = 100ms.
    drop_height = 0.05
    pot_hy = 0.08

    # --- DCR sim ---
    print("  Running DCR simulation...")
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )
    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)
    coupler = ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_dcr_coupler(coupler)

    plate_pos = [(-0.3, table_top + 0.021, 0.0), (0.3, table_top + 0.021, 0.0)]
    plate_idxs = []
    for pos in plate_pos:
        p = make_dynamic_box(0.2, 0.06, 0.02, 0.06,
                             position=pos, restitution=0.0, friction=0.5)
        plate_idxs.append(world.add_body(p))

    pot = make_dynamic_box(5.0, 0.08, pot_hy, 0.08,
                           position=(0.0, table_top + pot_hy + drop_height, 0.0),
                           restitution=0.1, friction=0.5)
    pot_idx = world.add_body(pot)

    # Settle plates (freeze pot during settling).
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in plate_idxs:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = True

    # Record from time=0 after settling.
    t_record_start = world.time
    dcr_times, dcr_pot_y, dcr_plate_ys, dcr_plate_vys = [], [], [], []
    for _ in range(400):
        world.step()
        dcr_times.append(world.time - t_record_start)
        dcr_pot_y.append(world.bodies[pot_idx].position[1])
        dcr_plate_ys.append([world.bodies[i].position[1] for i in plate_idxs])
        dcr_plate_vys.append([world.bodies[i].velocity[1] for i in plate_idxs])

    dcr_data = {
        "times": np.array(dcr_times),
        "pot_y": np.array(dcr_pot_y),
        "plate_ys": np.array(dcr_plate_ys),
        "plate_vys": np.array(dcr_plate_vys),
    }

    # --- Ground-truth sim ---
    # Pre-settle plates on the deformable surface before dropping the pot.
    print("  Running ground-truth FEM simulation (settling plates)...")
    gt_plates_settle = [
        SimpleRigidBody(mass=0.2, y=table_top + 0.021,
                        half_height=0.02, half_width_x=0.06, half_width_z=0.06),
        SimpleRigidBody(mass=0.2, y=table_top + 0.021,
                        half_height=0.02, half_width_x=0.06, half_width_z=0.06),
    ]
    # Settle without pot: run plates on the deformable table under gravity
    # until they reach steady state.
    gt_pot_frozen = SimpleRigidBody(
        mass=5.0, y=table_top + pot_hy + drop_height + 100.0,  # far away
        half_height=pot_hy,
    )
    settle_sim = CoupledFEMRigidSim(fem=fem, h_fine=1e-4, k_penalty=5e7)
    settle_sim.run(
        pot=gt_pot_frozen, plates=gt_plates_settle,
        plate_xz=[(-0.3, 0.0), (0.3, 0.0)], pot_xz=(0.0, 0.0),
        t_total=0.1, record_every=1000,
    )
    # Capture settled plate positions and zero their velocities.
    settled_plate_ys = [p.y for p in gt_plates_settle]
    for p in gt_plates_settle:
        p.vy = 0.0

    # Now run with the pot actually dropping.
    print("  Running ground-truth FEM simulation (pot drop)...")
    gt_pot = SimpleRigidBody(
        mass=5.0, y=table_top + pot_hy + drop_height,
        half_height=pot_hy, half_width_x=0.08, half_width_z=0.08,
    )
    gt_plates = [
        SimpleRigidBody(mass=0.2, y=settled_plate_ys[0], vy=0.0,
                        half_height=0.02, half_width_x=0.06, half_width_z=0.06),
        SimpleRigidBody(mass=0.2, y=settled_plate_ys[1], vy=0.0,
                        half_height=0.02, half_width_x=0.06, half_width_z=0.06),
    ]

    # Run long enough for pot to fall (drop_height) and response to propagate.
    # Free-fall time ≈ sqrt(2*drop_height/g) + response time.
    t_fall = np.sqrt(2 * drop_height / 9.81)
    t_total_gt = t_fall + 0.15  # fall time + 150ms of response
    gt_sim = CoupledFEMRigidSim(fem=fem, h_fine=1e-4, k_penalty=5e7)
    gt_data = gt_sim.run(
        pot=gt_pot, plates=gt_plates,
        plate_xz=[(-0.3, 0.0), (0.3, 0.0)], pot_xz=(0.0, 0.0),
        t_total=t_total_gt, record_every=10,
    )

    return dcr_data, gt_data


def render_comparison_mp4(dcr: dict, gt: dict, path: Path) -> None:
    """Render side-by-side DCR vs ground-truth comparison."""
    n_plates = dcr["plate_ys"].shape[1]
    colours = ["#cc3333", "#3366cc"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle("Stage 7 — DCR vs Ground-Truth Comparison", fontsize=13)

    # Row 0: plate Y-position over time.
    ax_pos_dcr = axes[0, 0]
    ax_pos_gt = axes[0, 1]

    # Row 1: plate Y-velocity over time.
    ax_vel_dcr = axes[1, 0]
    ax_vel_gt = axes[1, 1]

    t_max = max(dcr["times"][-1], gt["times"][-1]) * 1000

    for ax, title in [(ax_pos_dcr, "DCR — plate Y position"),
                      (ax_pos_gt, "Ground Truth — plate Y position")]:
        ax.set_xlim(0, t_max)
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("y [m]")
        ax.set_title(title, fontsize=10)

    for ax, title in [(ax_vel_dcr, "DCR — plate Y velocity"),
                      (ax_vel_gt, "Ground Truth — plate Y velocity")]:
        ax.set_xlim(0, t_max)
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("vy [m/s]")
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color="gray", lw=0.5)

    # Compute y-axis limits.
    all_ys = np.concatenate([dcr["plate_ys"].ravel(), gt["plate_ys"].ravel()])
    y_min = all_ys.min() - 0.01
    y_max = all_ys.max() + 0.01
    ax_pos_dcr.set_ylim(y_min, y_max)
    ax_pos_gt.set_ylim(y_min, y_max)

    all_vys = np.concatenate([dcr["plate_vys"].ravel(), gt["plate_vys"].ravel()])
    vy_lim = max(0.05, np.max(np.abs(all_vys)) * 1.3)
    ax_vel_dcr.set_ylim(-vy_lim * 0.5, vy_lim)
    ax_vel_gt.set_ylim(-vy_lim * 0.5, vy_lim)

    # Lines.
    dcr_pos_lines, dcr_vel_lines = [], []
    gt_pos_lines, gt_vel_lines = [], []
    for i in range(n_plates):
        l1, = ax_pos_dcr.plot([], [], color=colours[i], lw=1.2,
                              label=f"plate {i}")
        l2, = ax_vel_dcr.plot([], [], color=colours[i], lw=1.2,
                              label=f"plate {i}")
        l3, = ax_pos_gt.plot([], [], color=colours[i], lw=1.2,
                             label=f"plate {i}")
        l4, = ax_vel_gt.plot([], [], color=colours[i], lw=1.2,
                             label=f"plate {i}")
        dcr_pos_lines.append(l1)
        dcr_vel_lines.append(l2)
        gt_pos_lines.append(l3)
        gt_vel_lines.append(l4)

    for ax in [ax_pos_dcr, ax_vel_dcr, ax_pos_gt, ax_vel_gt]:
        ax.legend(fontsize=7, loc="upper right")

    vlines = []
    for ax in [ax_pos_dcr, ax_vel_dcr, ax_pos_gt, ax_vel_gt]:
        vl = ax.axvline(0, color="black", lw=0.5, ls="--")
        vlines.append(vl)

    fig.tight_layout(rect=[0, 0, 1, 0.94])

    # Animate at a common time base.
    dcr_t = dcr["times"] * 1000
    gt_t = gt["times"] * 1000
    t_end = min(dcr_t[-1], gt_t[-1])
    frame_dt = t_end / 300
    anim_times = np.arange(0, t_end, frame_dt)

    def update(frame_i):
        t_ms = anim_times[frame_i]

        # DCR.
        fi_dcr = np.searchsorted(dcr_t, t_ms)
        fi_dcr = min(fi_dcr, len(dcr_t) - 1)
        for i in range(n_plates):
            dcr_pos_lines[i].set_data(dcr_t[:fi_dcr + 1],
                                      dcr["plate_ys"][:fi_dcr + 1, i])
            dcr_vel_lines[i].set_data(dcr_t[:fi_dcr + 1],
                                      dcr["plate_vys"][:fi_dcr + 1, i])

        # GT.
        fi_gt = np.searchsorted(gt_t, t_ms)
        fi_gt = min(fi_gt, len(gt_t) - 1)
        for i in range(n_plates):
            gt_pos_lines[i].set_data(gt_t[:fi_gt + 1],
                                     gt["plate_ys"][:fi_gt + 1, i])
            gt_vel_lines[i].set_data(gt_t[:fi_gt + 1],
                                     gt["plate_vys"][:fi_gt + 1, i])

        for vl in vlines:
            vl.set_xdata([t_ms])

        return (dcr_pos_lines + dcr_vel_lines + gt_pos_lines + gt_vel_lines
                + vlines)

    anim = FuncAnimation(fig, update, frames=len(anim_times),
                         interval=33, blit=False)
    anim.save(str(path), writer="pillow", fps=30)
    plt.close(fig)
    print(f"  Saved {path}")


# ======================================================================
# Polyscope interactive playback
# ======================================================================

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


def show_dinner(data: dict) -> None:
    """Interactive polyscope playback of the dinner scene."""
    import polyscope as ps

    times = data["times"]
    pot_y = data["pot_y"]
    plate_ys = data["plate_ys"]
    n_frames = len(times)
    n_plates = plate_ys.shape[1]

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Table surface.
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    surface = mesh.extract_surface()
    ps.register_surface_mesh("table", surface.vertices, surface.faces,
                             color=(0.6, 0.4, 0.2))

    # Pot.
    pot_mesh_v, pot_mesh_f = _box_mesh(0.08, 0.08, 0.08)
    pot_pos0 = np.array([0.0, pot_y[0], 0.0])
    pot_ps = ps.register_surface_mesh("pot", pot_mesh_v + pot_pos0,
                                       pot_mesh_f, color=(0.3, 0.3, 0.3))

    # Plates.
    plate_meshes = [_box_mesh(0.06, 0.02, 0.06) for _ in range(n_plates)]
    plate_xs = [p[0] for p in data["plate_positions"]]
    plate_zs = [p[2] for p in data["plate_positions"]]
    plate_ps = []
    for i in range(n_plates):
        pos = np.array([plate_xs[i], plate_ys[0, i], plate_zs[i]])
        pm = ps.register_surface_mesh(
            f"plate_{i}", plate_meshes[i][0] + pos,
            plate_meshes[i][1], color=(0.8, 0.2, 0.2))
        plate_ps.append(pm)

    frame_idx = [0]
    is_playing = [True]

    def callback() -> None:
        import polyscope.imgui as imgui
        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])
        fi = frame_idx[0]
        t_ms = times[fi] * 1000
        imgui.Text(f"t = {t_ms:.1f} ms — Dinner is Served (DCR)")

        if is_playing[0]:
            frame_idx[0] = (frame_idx[0] + 1) % n_frames

        pot_ps.update_vertex_positions(
            pot_mesh_v + np.array([0.0, pot_y[fi], 0.0]))
        for i in range(n_plates):
            pos = np.array([plate_xs[i], plate_ys[fi, i], plate_zs[i]])
            plate_ps[i].update_vertex_positions(plate_meshes[i][0] + pos)

    ps.set_user_callback(callback)
    ps.show()


def show_spatial(data: dict) -> None:
    """Interactive polyscope playback of the spatial attenuation scene."""
    import polyscope as ps

    times = data["times"]
    imp_y = data["imp_y"]
    box_ys = data["box_ys"]
    box_xs = data["box_xs"]
    n_frames = len(times)
    n_boxes = len(box_xs)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Slab surface.
    mesh = make_slab_tet_mesh(length=2.0, width=0.3, height=0.05,
                              nx=20, ny=3, nz=2)
    surface = mesh.extract_surface()
    ps.register_surface_mesh("slab", surface.vertices, surface.faces,
                             color=(0.5, 0.35, 0.2))

    # Impactor.
    imp_mesh_v, imp_mesh_f = _box_mesh(0.08, 0.08, 0.08)
    imp_pos0 = np.array([-0.9, imp_y[0], 0.0])
    imp_ps = ps.register_surface_mesh("impactor", imp_mesh_v + imp_pos0,
                                       imp_mesh_f, color=(0.3, 0.3, 0.3))

    # Boxes.
    box_meshes = [_box_mesh(0.04, 0.02, 0.04) for _ in range(n_boxes)]
    box_ps = []
    for i in range(n_boxes):
        pos = np.array([box_xs[i], box_ys[0, i], 0.0])
        bm = ps.register_surface_mesh(
            f"box_{i}", box_meshes[i][0] + pos,
            box_meshes[i][1], color=(0.8, 0.3, 0.1))
        box_ps.append(bm)

    frame_idx = [0]
    is_playing = [True]

    def callback() -> None:
        import polyscope.imgui as imgui
        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])
        fi = frame_idx[0]
        t_ms = times[fi] * 1000
        imgui.Text(f"t = {t_ms:.1f} ms — Spatial Attenuation "
                   f"(\u03b2={data['beta']})")

        if is_playing[0]:
            frame_idx[0] = (frame_idx[0] + 1) % n_frames

        imp_ps.update_vertex_positions(
            imp_mesh_v + np.array([-0.9, imp_y[fi], 0.0]))
        for i in range(n_boxes):
            pos = np.array([box_xs[i], box_ys[fi, i], 0.0])
            box_ps[i].update_vertex_positions(box_meshes[i][0] + pos)

    ps.set_user_callback(callback)
    ps.show()


def show_comparison(dcr: dict, gt: dict) -> None:
    """Show the comparison as a matplotlib interactive window."""
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt

    n_plates = dcr["plate_ys"].shape[1]
    colours = ["#cc3333", "#3366cc"]

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle("Stage 7 — DCR vs Ground-Truth Comparison", fontsize=13)

    ax_pos_dcr, ax_pos_gt = axes[0, 0], axes[0, 1]
    ax_vel_dcr, ax_vel_gt = axes[1, 0], axes[1, 1]

    for ax, title in [(ax_pos_dcr, "DCR — plate Y position"),
                      (ax_pos_gt, "Ground Truth — plate Y position")]:
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("y [m]")
        ax.set_title(title, fontsize=10)

    for ax, title in [(ax_vel_dcr, "DCR — plate Y velocity"),
                      (ax_vel_gt, "Ground Truth — plate Y velocity")]:
        ax.set_xlabel("time [ms]")
        ax.set_ylabel("vy [m/s]")
        ax.set_title(title, fontsize=10)
        ax.axhline(0, color="gray", lw=0.5)

    for i in range(n_plates):
        ax_pos_dcr.plot(dcr["times"] * 1000, dcr["plate_ys"][:, i],
                        color=colours[i], lw=1.2, label=f"plate {i}")
        ax_vel_dcr.plot(dcr["times"] * 1000, dcr["plate_vys"][:, i],
                        color=colours[i], lw=1.2, label=f"plate {i}")
        ax_pos_gt.plot(gt["times"] * 1000, gt["plate_ys"][:, i],
                       color=colours[i], lw=1.2, label=f"plate {i}")
        ax_vel_gt.plot(gt["times"] * 1000, gt["plate_vys"][:, i],
                       color=colours[i], lw=1.2, label=f"plate {i}")

    for ax in [ax_pos_dcr, ax_vel_dcr, ax_pos_gt, ax_vel_gt]:
        ax.legend(fontsize=8, loc="upper right")

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    plt.show()


# ======================================================================
# Real-time mode — physics steps live inside polyscope callback
# ======================================================================

def _build_dinner_world():
    """Build the dinner scene world (shared by pre-recorded and real-time)."""
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    table_top = height / 2
    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=10)
    coupler = ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_dcr_coupler(coupler)

    plate_hy = 0.02
    plate_positions = [
        (-0.3, table_top + plate_hy + 0.001, 0.15),
        (0.3, table_top + plate_hy + 0.001, -0.1),
        (0.0, table_top + plate_hy + 0.001, -0.2),
    ]
    plate_idxs = []
    for pos in plate_positions:
        p = make_dynamic_box(0.2, 0.06, plate_hy, 0.06,
                             position=pos, restitution=0.0, friction=0.5)
        plate_idxs.append(world.add_body(p))

    pot_hy = 0.08
    pot = make_dynamic_box(5.0, 0.08, pot_hy, 0.08,
                           position=(0.0, table_top + pot_hy + 0.8, 0.0),
                           restitution=0.1, friction=0.5)
    pot_idx = world.add_body(pot)

    # Settle plates.
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in plate_idxs:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = True

    return world, mesh, plate_idxs, pot_idx, plate_positions


def _build_spatial_world(beta: float = 0.5):
    """Build the spatial attenuation scene world."""
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    length, width, height = 2.0, 0.3, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=20, ny=3, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    table_top = height / 2
    table = make_static_plane(normal=(0, 1, 0),
                              point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=10)
    coupler = SpatialDCRCoupler(modal=modal, elastic_body_idx=table_idx,
                                C=2.0, beta=beta)
    world.add_spatial_coupler(coupler)

    box_hy = 0.02
    box_xs = [-0.5, -0.2, 0.1, 0.4, 0.7]
    box_idxs = []
    for x in box_xs:
        b = make_dynamic_box(0.05, 0.04, box_hy, 0.04,
                             position=(x, table_top + box_hy + 0.001, 0.0),
                             restitution=0.0, friction=0.5)
        box_idxs.append(world.add_body(b))

    imp_hy = 0.08
    imp = make_dynamic_box(10.0, 0.08, imp_hy, 0.08,
                           position=(-0.9, table_top + imp_hy + 1.5, 0.0),
                           restitution=0.1, friction=0.5)
    imp_idx = world.add_body(imp)

    # Settle.
    world.bodies[imp_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in box_idxs:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[imp_idx].is_static = False
    world.dcr_enabled = True

    return world, mesh, box_idxs, imp_idx, box_xs


def realtime_dinner() -> None:
    """Real-time dinner scene: physics steps live in polyscope callback."""
    import polyscope as ps
    import time as _time

    print("  Building scene...")
    world, mesh, plate_idxs, pot_idx, plate_positions = _build_dinner_world()

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    surface = mesh.extract_surface()
    ps.register_surface_mesh("table", surface.vertices, surface.faces,
                             color=(0.6, 0.4, 0.2))

    pot_mesh_v, pot_mesh_f = _box_mesh(0.08, 0.08, 0.08)
    pot_ps = ps.register_surface_mesh(
        "pot", pot_mesh_v + world.bodies[pot_idx].position,
        pot_mesh_f, color=(0.3, 0.3, 0.3))

    n_plates = len(plate_idxs)
    plate_meshes = [_box_mesh(0.06, 0.02, 0.06) for _ in range(n_plates)]
    plate_ps = []
    for i, idx in enumerate(plate_idxs):
        pm = ps.register_surface_mesh(
            f"plate_{i}", plate_meshes[i][0] + world.bodies[idx].position,
            plate_meshes[i][1], color=(0.8, 0.2, 0.2))
        plate_ps.append(pm)

    is_running = [True]
    steps_per_frame = [10]  # physics steps per display frame
    wall_prev = [_time.perf_counter()]

    def callback() -> None:
        import polyscope.imgui as imgui

        _, is_running[0] = imgui.Checkbox("Running", is_running[0])
        changed, new_val = imgui.SliderInt("Steps/frame", steps_per_frame[0], 1, 50)
        if changed:
            steps_per_frame[0] = new_val

        t_ms = world.time * 1000
        wall_now = _time.perf_counter()
        wall_dt = wall_now - wall_prev[0]
        wall_prev[0] = wall_now
        fps = 1.0 / wall_dt if wall_dt > 0 else 0

        imgui.Text(f"t = {t_ms:.1f} ms  |  display {fps:.0f} fps  |  "
                   f"REAL-TIME Dinner (DCR)")

        if is_running[0]:
            for _ in range(steps_per_frame[0]):
                world.step()

        # Update visuals.
        pot_ps.update_vertex_positions(
            pot_mesh_v + world.bodies[pot_idx].position)
        for i, idx in enumerate(plate_idxs):
            plate_ps[i].update_vertex_positions(
                plate_meshes[i][0] + world.bodies[idx].position)

    ps.set_user_callback(callback)
    ps.show()


def realtime_spatial(beta: float = 0.5) -> None:
    """Real-time spatial scene: physics steps live in polyscope callback."""
    import polyscope as ps
    import time as _time

    print("  Building scene...")
    world, mesh, box_idxs, imp_idx, box_xs = _build_spatial_world(beta)

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    surface = mesh.extract_surface()
    ps.register_surface_mesh("slab", surface.vertices, surface.faces,
                             color=(0.5, 0.35, 0.2))

    imp_mesh_v, imp_mesh_f = _box_mesh(0.08, 0.08, 0.08)
    imp_ps = ps.register_surface_mesh(
        "impactor", imp_mesh_v + world.bodies[imp_idx].position,
        imp_mesh_f, color=(0.3, 0.3, 0.3))

    n_boxes = len(box_idxs)
    box_meshes = [_box_mesh(0.04, 0.02, 0.04) for _ in range(n_boxes)]
    box_ps = []
    for i, idx in enumerate(box_idxs):
        bm = ps.register_surface_mesh(
            f"box_{i}", box_meshes[i][0] + world.bodies[idx].position,
            box_meshes[i][1], color=(0.8, 0.3, 0.1))
        box_ps.append(bm)

    is_running = [True]
    steps_per_frame = [10]
    wall_prev = [_time.perf_counter()]

    def callback() -> None:
        import polyscope.imgui as imgui

        _, is_running[0] = imgui.Checkbox("Running", is_running[0])
        changed, new_val = imgui.SliderInt("Steps/frame", steps_per_frame[0], 1, 50)
        if changed:
            steps_per_frame[0] = new_val

        t_ms = world.time * 1000
        wall_now = _time.perf_counter()
        wall_dt = wall_now - wall_prev[0]
        wall_prev[0] = wall_now
        fps = 1.0 / wall_dt if wall_dt > 0 else 0

        imgui.Text(f"t = {t_ms:.1f} ms  |  display {fps:.0f} fps  |  "
                   f"REAL-TIME Spatial (\u03b2={beta})")

        if is_running[0]:
            for _ in range(steps_per_frame[0]):
                world.step()

        imp_ps.update_vertex_positions(
            imp_mesh_v + world.bodies[imp_idx].position)
        for i, idx in enumerate(box_idxs):
            box_ps[i].update_vertex_positions(
                box_meshes[i][0] + world.bodies[idx].position)

    ps.set_user_callback(callback)
    ps.show()


# ======================================================================
# Main
# ======================================================================

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    save_gifs = "--save" in flags
    realtime = "--realtime" in flags

    mode = args[0] if args else ("all" if save_gifs else "dinner")

    if realtime:
        # Real-time mode: step physics live in polyscope callback.
        if mode in ("dinner",):
            print("=== Real-time: Dinner is Served (Modal DCR) ===")
            realtime_dinner()
        elif mode == "spatial":
            print("=== Real-time: Spatial Attenuation DCR ===")
            realtime_spatial()
        else:
            print("=== Real-time: Dinner is Served (Modal DCR) ===")
            realtime_dinner()
        return

    if mode in ("dinner", "all"):
        print("=== Scene 1: Dinner is Served (Modal DCR) ===")
        data = run_dinner()
        max_vys = np.max(data["plate_vys"], axis=0)
        for i, vy in enumerate(max_vys):
            print(f"  Plate {i}: max vy = {vy:.4f} m/s")
        if save_gifs or mode == "all":
            render_dinner_mp4(data, OUT_DIR / "dinner.gif")
        if not save_gifs or mode == "dinner":
            show_dinner(data)

    if mode in ("spatial", "all"):
        print("=== Scene 2: Spatial Attenuation DCR ===")
        data = run_spatial(beta=0.5)
        max_vys = np.max(data["box_vys"], axis=0)
        for i, vy in enumerate(max_vys):
            print(f"  Box x={data['box_xs'][i]:+.1f}: max vy = {vy:.4f} m/s")
        if save_gifs or mode == "all":
            render_spatial_mp4(data, OUT_DIR / "spatial.gif")
        if not save_gifs or mode == "spatial":
            show_spatial(data)

    if mode in ("compare", "all"):
        print("=== Scene 3: DCR vs Ground-Truth Comparison ===")
        dcr_data, gt_data = run_comparison()
        print("  DCR plate max vy:",
              [f"{v:.4f}" for v in np.max(dcr_data["plate_vys"], axis=0)])
        print("  GT  plate max vy:",
              [f"{v:.4f}" for v in np.max(gt_data["plate_vys"], axis=0)])
        if save_gifs or mode == "all":
            render_comparison_mp4(dcr_data, gt_data, OUT_DIR / "compare.gif")
        if not save_gifs or mode == "compare":
            show_comparison(dcr_data, gt_data)

    if save_gifs:
        print(f"\nDone. GIFs saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
