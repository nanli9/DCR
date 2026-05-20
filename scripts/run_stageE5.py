#!/usr/bin/env python3
"""Stage E5 — η sweep on the 'Dinner is served' scene.

Runs the dinner scene with passive DCR at η ∈ {0.0, 0.1, 0.3, 0.5, 1.0}.
Produces:
  - MP4 per η value
  - 5-panel strip image at a fixed post-impact time
  - Energy invariant plot (I_K vs L_K)
  - Interactive polyscope playback (η=1.0)

Usage:
    uv run python scripts/run_stageE5.py              # full run + polyscope
    uv run python scripts/run_stageE5.py --plot-only   # re-plot from saved data
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.patches as mpatches

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.rigid.energy import rigid_kinetic_energy
from dcr.dcr import PassiveDCRCoupler, DCRWorld

OUT_DIR = Path("docs/stageE5")
H = 1e-3
N_STEPS = 1000
ETA_VALUES = [0.0, 0.1, 0.3, 0.5, 1.0]


def _fix_corners(mesh) -> np.ndarray:
    v = mesh.vertices
    tol = 1e-8
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    mask = (((np.abs(v[:, 0] - xmin) < tol) | (np.abs(v[:, 0] - xmax) < tol)) &
            ((np.abs(v[:, 2] - zmin) < tol) | (np.abs(v[:, 2] - zmax) < tol)))
    return np.where(mask)[0].astype(np.int32)


def run_dinner_passive(eta: float) -> dict:
    """Run dinner scene with passive DCR at given η."""
    world = DCRWorld(
        h=H, eta=eta,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=80),
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
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

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

    # Settle plates (hold pot static, DCR off).
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in plate_idxs:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = True
    world.time = 0.0

    # Measure E_rigid(0) for tolerance.
    E_rigid_0 = rigid_kinetic_energy(world.bodies)
    # Actually, E_rigid(0) is ~0 since nothing is moving yet.
    # Use a later value — sample after first step when pot is falling.
    omega = coupler.modal.frequencies

    # Simulate.
    times, pot_ys, plate_ys, plate_vys = [], [], [], []
    pot_pos_all, plate_pos_all = [], [[] for _ in plate_idxs]
    cum_injected, cum_loss = [], []
    E_modal_hist = []
    c_inj, c_loss = 0.0, 0.0

    for step_i in range(N_STEPS):
        contacts = world.step()
        times.append(world.time)
        pot_ys.append(float(world.bodies[pot_idx].position[1]))
        plate_ys.append([float(world.bodies[i].position[1]) for i in plate_idxs])
        plate_vys.append([float(world.bodies[i].velocity[1]) for i in plate_idxs])
        pot_pos_all.append(world.bodies[pot_idx].position.copy().tolist())
        for pi, idx in enumerate(plate_idxs):
            plate_pos_all[pi].append(world.bodies[idx].position.copy().tolist())

        # Energy tracking (avoid stale dE when coupler not called).
        if len(contacts) > 0 and world.dcr_enabled:
            dE = coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick
        else:
            dE = 0.0
        c_inj += dE
        c_loss += eta * world.last_E_loss
        cum_injected.append(c_inj)
        cum_loss.append(c_loss)
        E_modal_hist.append(float(
            modal_energy(coupler._stepper.q, coupler._stepper.qdot, omega)))

        # Capture E_rigid_0 when pot starts falling (step 1).
        if step_i == 0:
            E_rigid_0 = rigid_kinetic_energy(world.bodies)

    return {
        "eta": eta,
        "times": times,
        "pot_y": pot_ys,
        "plate_ys": plate_ys,
        "plate_vys": plate_vys,
        "pot_pos": pot_pos_all,
        "plate_pos": plate_pos_all,
        "cum_injected": cum_injected,
        "cum_loss": cum_loss,
        "E_modal": E_modal_hist,
        "E_rigid_0": float(E_rigid_0),
        "table_top": table_top,
    }


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_energy_invariant(all_data: list[dict], out_dir: Path) -> None:
    """Plot I_K vs L_K for each η."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    axes = axes.flatten()

    for i, data in enumerate(all_data):
        ax = axes[i]
        eta = data["eta"]
        t = np.array(data["times"]) * 1000
        inj = np.array(data["cum_injected"])
        loss = np.array(data["cum_loss"])

        ax.plot(t, loss, "r-", lw=1.5, label=f"η·Σ E_loss")
        ax.plot(t, inj, "b-", lw=1.5, label="Σ ΔE_modal")
        ax.fill_between(t, inj, loss, alpha=0.15, color="green")
        ax.set_title(f"η = {eta}", fontsize=12)
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Energy (J)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # Check invariant
        margin = loss - inj
        violations = np.sum(margin < -1e-9)
        if violations > 0:
            ax.text(0.5, 0.9, f"VIOLATIONS: {violations}",
                    transform=ax.transAxes, color="red", fontsize=10,
                    ha="center")

    # Hide unused subplot
    axes[5].set_visible(False)

    fig.suptitle("E5.3: Energy Invariant — Σ ΔE_modal ≤ η · Σ E_loss", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "energy_invariant.png", dpi=150)
    plt.close(fig)
    print(f"  Saved energy_invariant.png")


def render_mp4(data: dict, out_dir: Path) -> None:
    """Render side-view MP4 for one η value."""
    eta = data["eta"]
    times = np.array(data["times"])
    pot_y = np.array(data["pot_y"])
    plate_ys = np.array(data["plate_ys"])
    table_top = data["table_top"]
    n_frames = len(times)

    fig, (ax_scene, ax_vel) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Passive DCR — η = {eta}", fontsize=13)

    ax_scene.set_xlim(-0.6, 0.6)
    ax_scene.set_ylim(-0.05, 1.1)
    ax_scene.set_xlabel("x (m)")
    ax_scene.set_ylabel("y (m)")
    ax_scene.set_aspect("equal")
    ax_scene.set_title("Side view")
    ax_scene.axhline(table_top, color="sienna", lw=3)

    pot_rect = mpatches.FancyBboxPatch(
        (-0.08, pot_y[0] - 0.08), 0.16, 0.16,
        boxstyle="round,pad=0.005", fc="gray", ec="black", lw=1)
    ax_scene.add_patch(pot_rect)

    plate_xs = [-0.3, 0.3, 0.0]
    plate_rects = []
    for px in plate_xs:
        r = mpatches.FancyBboxPatch(
            (px - 0.06, table_top), 0.12, 0.04,
            boxstyle="round,pad=0.002", fc="tomato", ec="black", lw=0.5)
        ax_scene.add_patch(r)
        plate_rects.append(r)

    time_text = ax_scene.text(0.02, 0.95, "", transform=ax_scene.transAxes,
                              fontsize=10, verticalalignment="top")

    plate_vys = np.array(data["plate_vys"])
    colors = ["tab:blue", "tab:orange", "tab:green"]
    ax_vel.set_xlim(0, times[-1] * 1000)
    ax_vel.set_ylabel("Plate vy (mm/s)")
    ax_vel.set_xlabel("Time (ms)")
    ax_vel.set_title("Plate vertical velocity")
    ax_vel.grid(True, alpha=0.3)
    vel_lines = []
    for pi in range(3):
        ln, = ax_vel.plot([], [], color=colors[pi], lw=0.7, label=f"Plate {pi}")
        vel_lines.append(ln)
    ax_vel.legend(fontsize=8)

    skip = 4

    def init():
        return [pot_rect] + plate_rects + vel_lines + [time_text]

    def update(frame_i):
        si = frame_i * skip
        if si >= n_frames:
            si = n_frames - 1
        # Pot
        pot_rect.set_y(pot_y[si] - 0.08)
        # Plates
        for pi, pr in enumerate(plate_rects):
            pr.set_y(plate_ys[si, pi] - 0.02)
        time_text.set_text(f"t = {times[si]*1000:.0f} ms")
        # Velocity traces
        t_ms = times[:si+1] * 1000
        for pi, ln in enumerate(vel_lines):
            ln.set_data(t_ms, plate_vys[:si+1, pi] * 1000)
        ax_vel.set_ylim(np.min(plate_vys[:si+1]) * 1100,
                        max(np.max(plate_vys[:si+1]) * 1100, 0.1))
        return [pot_rect] + plate_rects + vel_lines + [time_text]

    anim = FuncAnimation(fig, update, init_func=init,
                         frames=n_frames // skip, interval=33, blit=False)
    gif_path = out_dir / f"dinner_eta_{eta}.gif"
    anim.save(str(gif_path), writer="pillow", fps=30, dpi=80)
    plt.close(fig)
    print(f"  Saved {gif_path.name}")


def render_strip(all_data: list[dict], out_dir: Path,
                 strip_time_ms: float = 500.0) -> None:
    """Render a 5-panel strip at a fixed post-impact time."""
    fig, axes = plt.subplots(1, 5, figsize=(20, 4), sharey=True)

    for i, (data, ax) in enumerate(zip(all_data, axes)):
        eta = data["eta"]
        times = np.array(data["times"])
        pot_y = np.array(data["pot_y"])
        plate_ys = np.array(data["plate_ys"])
        table_top = data["table_top"]

        # Find frame closest to strip_time_ms
        si = int(np.argmin(np.abs(times * 1000 - strip_time_ms)))

        ax.set_xlim(-0.55, 0.55)
        ax.set_ylim(-0.02, 0.25)
        ax.set_aspect("equal")
        ax.set_title(f"η = {eta}", fontsize=11)
        if i == 0:
            ax.set_ylabel("y (m)")
        ax.set_xlabel("x (m)")

        # Table
        ax.axhline(table_top, color="sienna", lw=3)

        # Pot
        pot_rect = mpatches.FancyBboxPatch(
            (-0.08, pot_y[si] - 0.08), 0.16, 0.16,
            boxstyle="round,pad=0.005", fc="gray", ec="black", lw=1)
        ax.add_patch(pot_rect)

        # Plates
        plate_xs = [-0.3, 0.3, 0.0]
        for pi, px in enumerate(plate_xs):
            r = mpatches.FancyBboxPatch(
                (px - 0.06, plate_ys[si, pi] - 0.02), 0.12, 0.04,
                boxstyle="round,pad=0.002", fc="tomato", ec="black", lw=0.5)
            ax.add_patch(r)

        ax.text(0.05, 0.92, f"t={times[si]*1000:.0f}ms",
                transform=ax.transAxes, fontsize=9)

    fig.suptitle(f"E5.2: η Sweep at t ≈ {strip_time_ms:.0f} ms", fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(out_dir / "eta_sweep_strip.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved eta_sweep_strip.png")


def run_polyscope(modal, data: dict) -> None:
    """Interactive polyscope playback for one η run."""
    import polyscope as ps

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    table_surface = modal.fem.mesh.extract_surface()
    ps.register_surface_mesh("table", table_surface.vertices,
                             table_surface.faces, color=(0.6, 0.4, 0.2))

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

    pot_mesh = _box_mesh(0.08, 0.08, 0.08)
    plate_meshes = [_box_mesh(0.06, 0.02, 0.06) for _ in range(3)]

    pot_pos = [np.array(p) for p in data["pot_pos"]]
    plate_pos = [[np.array(p) for p in pl] for pl in data["plate_pos"]]
    times = data["times"]
    eta = data["eta"]

    pot_ps = ps.register_surface_mesh(
        "pot", pot_mesh[0] + pot_pos[0], pot_mesh[1], color=(0.3, 0.3, 0.3))
    plate_ps = []
    for i in range(3):
        pm = ps.register_surface_mesh(
            f"plate_{i}", plate_meshes[i][0] + plate_pos[i][0],
            plate_meshes[i][1], color=(0.8, 0.2, 0.2))
        plate_ps.append(pm)

    frame_idx = [0]
    is_playing = [True]
    skip = 3
    n_total = len(times)
    n_frames = n_total // skip

    def callback():
        import polyscope.imgui as imgui
        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])

        si = min(frame_idx[0] * skip, n_total - 1)
        imgui.Text(f"Passive DCR (eta={eta})  t = {times[si]*1000:.1f} ms")

        if is_playing[0]:
            if frame_idx[0] < n_frames - 1:
                frame_idx[0] += 1
            else:
                is_playing[0] = False

        pot_ps.update_vertex_positions(pot_mesh[0] + pot_pos[si])
        for i in range(3):
            plate_ps[i].update_vertex_positions(
                plate_meshes[i][0] + plate_pos[i][si])

    ps.set_user_callback(callback)
    ps.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stage E5 — η sweep")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.plot_only:
        all_data = []
        for eta in ETA_VALUES:
            with open(OUT_DIR / f"data_eta_{eta}.json") as f:
                all_data.append(json.load(f))
    else:
        all_data = []
        for eta in ETA_VALUES:
            print(f"Running η = {eta}...")
            data = run_dinner_passive(eta)
            all_data.append(data)
            with open(OUT_DIR / f"data_eta_{eta}.json", "w") as f:
                json.dump(data, f)

            max_plate_vy = max(max(row) for row in data["plate_vys"])
            print(f"  max plate vy = {max_plate_vy*1000:.2f} mm/s")
            print(f"  cum injected = {data['cum_injected'][-1]:.4f} J")
            print(f"  cum η·E_loss = {data['cum_loss'][-1]:.4f} J")

    # Energy invariant check
    print("\nEnergy invariant check:")
    for data in all_data:
        eta = data["eta"]
        inj = np.array(data["cum_injected"])
        loss = np.array(data["cum_loss"])
        E0 = data["E_rigid_0"]
        eps_tol = 1e-9 * max(E0, 1.0)  # E0 might be ~0 at step 0
        violations = np.sum(inj > loss + eps_tol)
        status = "PASS" if violations == 0 else f"FAIL ({violations} violations)"
        print(f"  η={eta}: {status}  (max margin = {np.max(loss - inj):.4f} J)")

    print("\nGenerating plots...")
    plot_energy_invariant(all_data, OUT_DIR)
    render_strip(all_data, OUT_DIR)

    print("\nGenerating GIFs...")
    for data in all_data:
        try:
            render_mp4(data, OUT_DIR)
        except Exception as e:
            print(f"  GIF for η={data['eta']} failed: {e}")

    if not args.plot_only:
        # Build modal for polyscope
        mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                                  nx=10, ny=6, nz=2)
        mat = Material(E=1.1e9, nu=0.3, rho=770.0)
        fixed = _fix_corners(mesh)
        fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                       alpha0=2.0, alpha1=1e-5)
        modal = ModalAnalysis(fem=fem, num_modes=10)

        # Show η=1.0 (maximum response)
        print("\nLaunching polyscope (η=1.0)...")
        run_polyscope(modal, all_data[-1])
    else:
        print("\nDone (--plot-only).")


if __name__ == "__main__":
    main()
