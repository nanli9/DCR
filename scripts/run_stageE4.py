#!/usr/bin/env python3
"""Stage E4 — Multi-contact aggregation + monotone dissipation.

Visual demo: Two balls dropped simultaneously onto an elastic slab.
A resting plate on the slab responds via passive DCR.
Also shows the monotone energy decay after impact.

Usage:
    uv run python scripts/run_stageE4.py              # polyscope interactive
    uv run python scripts/run_stageE4.py --plot-only   # just plots, no polyscope
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Shared slab builder
# ---------------------------------------------------------------------------


def _build_slab_modal():
    from dcr.geom import make_slab_tet_mesh
    from dcr.fem import Material, FEMModel
    from dcr.modal import ModalAnalysis

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
    return ModalAnalysis(fem=fem_model, num_modes=10)


# ---------------------------------------------------------------------------
# Plot 1: Per-contact vs aggregate energy bound
# ---------------------------------------------------------------------------


def run_aggregation_comparison(out_dir: Path) -> dict:
    """Run the per-contact vs aggregate comparison and save data."""
    from dcr.modal.energy import modal_energy
    from dcr.modal.passive_inject import (
        eval_basis_at_point, project_impulse, aggregate_kicks, passive_alpha,
    )
    from dcr.modal.homogeneous_stepper import HomogeneousStepper

    modal = _build_slab_modal()
    surface = modal.fem.mesh.extract_surface()
    max_vert = modal.fem.mesh.num_vertices
    vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
    for si, vi in enumerate(modal.surface_vertex_indices):
        vert_to_surf_idx[vi] = si

    omega = modal.frequencies

    point_a = np.array([-0.3, 0.025, 0.0])
    point_b = np.array([0.3, 0.025, 0.0])

    # Sweep impulse magnitudes to show the divergence clearly
    magnitudes = np.linspace(1.0, 100.0, 50)
    E_max = 0.5  # fixed budget

    per_contact_injected = []
    aggregate_injected = []

    for mag in magnitudes:
        j_a = np.array([0.0, mag, 0.0])
        j_b = np.array([0.0, mag, 0.0])

        # Per-contact (incorrect)
        stepper_pc = HomogeneousStepper.from_modal_analysis(modal)
        total_pc = 0.0
        for j_world, point in [(j_a, point_a), (j_b, point_b)]:
            Phi_x = eval_basis_at_point(
                point, surface, modal.U_surf,
                modal.surface_vertex_indices, vert_to_surf_idx)
            s_c = project_impulse(Phi_x, j_world)
            E_pre = modal_energy(stepper_pc.q, stepper_pc.qdot, omega)
            alpha = passive_alpha(s_c, stepper_pc.qdot, E_max)
            stepper_pc.qdot += alpha * s_c
            E_post = modal_energy(stepper_pc.q, stepper_pc.qdot, omega)
            total_pc += E_post - E_pre
        per_contact_injected.append(total_pc)

        # Aggregate (correct)
        stepper_ag = HomogeneousStepper.from_modal_analysis(modal)
        kicks = []
        for j_world, point in [(j_a, point_a), (j_b, point_b)]:
            Phi_x = eval_basis_at_point(
                point, surface, modal.U_surf,
                modal.surface_vertex_indices, vert_to_surf_idx)
            s_c = project_impulse(Phi_x, j_world)
            kicks.append(s_c)
        s_total = aggregate_kicks(kicks)
        E_pre = modal_energy(stepper_ag.q, stepper_ag.qdot, omega)
        alpha = passive_alpha(s_total, stepper_ag.qdot, E_max)
        stepper_ag.qdot += alpha * s_total
        E_post = modal_energy(stepper_ag.q, stepper_ag.qdot, omega)
        aggregate_injected.append(E_post - E_pre)

    data = {
        "magnitudes": magnitudes.tolist(),
        "per_contact_injected": per_contact_injected,
        "aggregate_injected": aggregate_injected,
        "E_max": E_max,
    }
    with open(out_dir / "aggregation_data.json", "w") as f:
        json.dump(data, f)

    return data


# ---------------------------------------------------------------------------
# Plot 2: Monotone dissipation after impact
# ---------------------------------------------------------------------------


def run_dissipation_trace(out_dir: Path) -> dict:
    """Run single-ball impact and record E_modal at every sub-step."""
    from dcr.modal.energy import modal_energy
    from dcr.modal.homogeneous_stepper import HomogeneousStepper
    from dcr.dcr import PassiveDCRCoupler, DCRWorld
    from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver

    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=1.0,
    )

    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)

    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    ball = make_dynamic_box(
        mass=2.0, hx=0.05, hy=0.05, hz=0.05,
        position=(0.0, 0.3, 0.0), restitution=0.8, friction=0.3,
    )
    world.add_body(ball)

    omega = coupler.modal.frequencies
    stepper = coupler._stepper
    n_substeps = max(1, int(np.ceil(h / stepper.T)))

    # Phase 1: run until ball bounces clear
    had_contact = False
    no_contact_steps = 0
    E_during_impact = []
    times_during = []
    t = 0.0

    for step_i in range(2000):
        contacts = world.step()
        t += h
        has_elastic_contact = any(
            c.body_a == table_idx or c.body_b == table_idx
            for c in contacts
        )

        E = modal_energy(stepper.q, stepper.qdot, omega)
        E_during_impact.append(E)
        times_during.append(t)

        if has_elastic_contact:
            had_contact = True
            no_contact_steps = 0
        elif had_contact:
            no_contact_steps += 1
            if no_contact_steps >= 50:
                break

    # Phase 2: free decay — record at sub-step granularity
    E_post_impact = []
    times_post = []
    t_post = 0.0

    for rigid_step in range(500):
        for sub in range(n_substeps):
            stepper.step()
            t_post += stepper.T
            E = modal_energy(stepper.q, stepper.qdot, omega)
            E_post_impact.append(E)
            times_post.append(t + t_post)

    data = {
        "times_during": times_during,
        "E_during_impact": E_during_impact,
        "times_post": times_post,
        "E_post_impact": E_post_impact,
    }
    with open(out_dir / "dissipation_data.json", "w") as f:
        json.dump(data, f)

    return data


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_aggregation(data: dict, out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mags = data["magnitudes"]
    pc = data["per_contact_injected"]
    ag = data["aggregate_injected"]
    E_max = data["E_max"]

    fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    ax.plot(mags, pc, "r-", linewidth=2, label="Per-contact (incorrect)")
    ax.plot(mags, ag, "b-", linewidth=2, label="Aggregate (correct)")
    ax.axhline(y=E_max, color="k", linestyle="--", linewidth=1.5,
               label=f"E_max = {E_max}")
    ax.axhline(y=2 * E_max, color="gray", linestyle=":", linewidth=1,
               label=f"2 x E_max = {2 * E_max}")

    ax.set_xlabel("Impulse magnitude (N.s)", fontsize=12)
    ax.set_ylabel("Energy injected (J)", fontsize=12)
    ax.set_title("E4.1: Per-Contact vs Aggregate Energy Injection", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    fig.savefig(out_dir / "aggregation_comparison.png", dpi=150)
    plt.close(fig)
    print(f"  Saved {out_dir / 'aggregation_comparison.png'}")


def plot_dissipation(data: dict, out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t_during = data["times_during"]
    E_during = data["E_during_impact"]
    t_post = data["times_post"]
    E_post = data["E_post_impact"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: full timeline (during + post impact)
    ax1.plot(t_during, E_during, "b-", linewidth=1.5, label="During impact")
    ax1.plot(t_post, E_post, "r-", linewidth=1.5, label="Free decay")
    ax1.set_xlabel("Time (s)", fontsize=12)
    ax1.set_ylabel("E_modal (J)", fontsize=12)
    ax1.set_title("E4.2: Modal Energy Timeline", fontsize=13)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Right: free decay zoomed, log scale
    if E_post and max(E_post) > 0:
        ax2.semilogy(t_post, E_post, "r-", linewidth=1.5)
        ax2.set_xlabel("Time (s)", fontsize=12)
        ax2.set_ylabel("E_modal (J, log scale)", fontsize=12)
        ax2.set_title("E4.2: Monotone Decay (sub-step)", fontsize=13)
        ax2.grid(True, alpha=0.3)

        # Check monotonicity and annotate
        E_arr = np.array(E_post)
        violations = np.sum(np.diff(E_arr) > 1e-15)
        ax2.text(0.05, 0.95, f"Violations: {violations}",
                 transform=ax2.transAxes, fontsize=11,
                 verticalalignment="top",
                 bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    fig.tight_layout()
    fig.savefig(out_dir / "monotone_dissipation.png", dpi=150)
    plt.close(fig)
    print(f"  Saved {out_dir / 'monotone_dissipation.png'}")


# ---------------------------------------------------------------------------
# Visual demo: two-ball scene with resting plate
# ---------------------------------------------------------------------------


def run_two_ball_visual(out_dir: Path) -> dict:
    """Run two-ball + plate scene, record positions for polyscope playback."""
    from dcr.modal.energy import modal_energy
    from dcr.dcr import PassiveDCRCoupler, DCRWorld
    from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver

    h = 1e-3
    N_STEPS = 2500

    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=1.0,
    )

    table_top = 0.025
    table = make_static_plane(
        normal=(0, 1, 0), point=(0, table_top, 0), friction=0.5)
    table_idx = world.add_body(table)

    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    # Two balls at different X positions, same height
    ball_a = make_dynamic_box(
        mass=1.0, hx=0.04, hy=0.04, hz=0.04,
        position=(-0.25, 0.6, 0.0), restitution=0.3, friction=0.5,
    )
    ball_b = make_dynamic_box(
        mass=1.0, hx=0.04, hy=0.04, hz=0.04,
        position=(0.25, 0.6, 0.0), restitution=0.3, friction=0.5,
    )
    idx_a = world.add_body(ball_a)
    idx_b = world.add_body(ball_b)

    # A plate resting on the table between the two ball landing sites
    plate = make_dynamic_box(
        mass=0.15, hx=0.05, hy=0.015, hz=0.05,
        position=(0.0, table_top + 0.016, 0.0),
        restitution=0.0, friction=0.5,
    )
    idx_plate = world.add_body(plate)

    # Settle plate (hold balls static)
    world.bodies[idx_a].is_static = True
    world.bodies[idx_b].is_static = True
    old_dcr = world.dcr_enabled
    world.dcr_enabled = False
    for _ in range(100):
        world.step()
    world.bodies[idx_plate].velocity[:] = 0.0
    world.bodies[idx_a].is_static = False
    world.bodies[idx_b].is_static = False
    world.dcr_enabled = old_dcr
    world.time = 0.0

    omega = coupler.modal.frequencies

    # Record
    times = []
    pos_a, pos_b, pos_plate = [], [], []
    E_modal_hist = []
    cum_injected, cum_loss = [], []
    c_inj, c_loss = 0.0, 0.0

    prev_post_kick = 0.0  # track last post_kick to avoid stale re-accumulation

    for step_i in range(N_STEPS):
        contacts = world.step()
        times.append(world.time)
        pos_a.append(world.bodies[idx_a].position.copy())
        pos_b.append(world.bodies[idx_b].position.copy())
        pos_plate.append(world.bodies[idx_plate].position.copy())

        # Only count dE when the coupler was actually invoked this step.
        cur_post = coupler.last_E_modal_post_kick
        if len(contacts) > 0 and world.dcr_enabled:
            dE = coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick
        else:
            dE = 0.0
        prev_post_kick = cur_post
        c_inj += dE
        c_loss += world.last_E_loss
        cum_injected.append(c_inj)
        cum_loss.append(c_loss)
        E_modal_hist.append(
            modal_energy(coupler._stepper.q, coupler._stepper.qdot, omega))

    data = {
        "times": times,
        "pos_a": [p.tolist() for p in pos_a],
        "pos_b": [p.tolist() for p in pos_b],
        "pos_plate": [p.tolist() for p in pos_plate],
        "E_modal": E_modal_hist,
        "cum_injected": cum_injected,
        "cum_loss": cum_loss,
    }
    with open(out_dir / "visual_data.json", "w") as f:
        json.dump(data, f)

    return data


def _box_mesh(hx, hy, hz):
    """Box mesh (8 verts, 12 tris) centered at origin."""
    verts = np.array([
        [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
        [-hx, -hy,  hz], [hx, -hy,  hz], [hx, hy,  hz], [-hx, hy,  hz],
    ], dtype=np.float64)
    faces = np.array([
        [0,2,1],[0,3,2], [4,5,6],[4,6,7],
        [0,1,5],[0,5,4], [2,3,7],[2,7,6],
        [0,4,7],[0,7,3], [1,2,6],[1,6,5],
    ], dtype=np.int32)
    return verts, faces


def run_polyscope(modal, vis_data: dict) -> None:
    """Interactive polyscope playback of the two-ball + plate scene."""
    import polyscope as ps

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Table surface
    table_surface = modal.fem.mesh.extract_surface()
    ps.register_surface_mesh("table", table_surface.vertices,
                             table_surface.faces, color=(0.6, 0.4, 0.2))

    pos_a = [np.array(p) for p in vis_data["pos_a"]]
    pos_b = [np.array(p) for p in vis_data["pos_b"]]
    pos_plate = [np.array(p) for p in vis_data["pos_plate"]]
    times = vis_data["times"]
    E_modal = vis_data["E_modal"]
    cum_inj = vis_data["cum_injected"]
    cum_loss = vis_data["cum_loss"]

    ball_mesh = _box_mesh(0.04, 0.04, 0.04)
    plate_mesh = _box_mesh(0.05, 0.015, 0.05)

    ball_a_ps = ps.register_surface_mesh(
        "ball_A", ball_mesh[0] + pos_a[0], ball_mesh[1],
        color=(0.2, 0.4, 0.8))
    ball_b_ps = ps.register_surface_mesh(
        "ball_B", ball_mesh[0] + pos_b[0], ball_mesh[1],
        color=(0.2, 0.8, 0.4))
    plate_ps = ps.register_surface_mesh(
        "plate", plate_mesh[0] + pos_plate[0], plate_mesh[1],
        color=(0.8, 0.2, 0.2))

    frame_idx = [0]
    is_playing = [True]
    record_every = 3
    n_total = len(times)
    n_frames = n_total // record_every

    def callback():
        import polyscope.imgui as imgui

        changed, new_val = imgui.SliderInt("Frame", frame_idx[0], 0, n_frames - 1)
        if changed:
            frame_idx[0] = new_val
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])

        si = min(frame_idx[0] * record_every, n_total - 1)
        t_ms = times[si] * 1000

        imgui.Text(f"E4: Two-Ball Multi-Contact Demo (eta=1.0)")
        imgui.Text(f"t = {t_ms:.1f} ms")
        imgui.Separator()
        imgui.Text(f"E_modal:       {E_modal[si]:.4f} J")
        imgui.Text(f"Cum injected:  {cum_inj[si]:.4f} J")
        imgui.Text(f"Cum E_loss:    {cum_loss[si]:.4f} J")
        margin = cum_loss[si] - cum_inj[si]
        imgui.Text(f"Headroom:      {margin:.4f} J")

        if is_playing[0]:
            if frame_idx[0] < n_frames - 1:
                frame_idx[0] += 1
            else:
                is_playing[0] = False  # stop at end, don't loop

        ball_a_ps.update_vertex_positions(ball_mesh[0] + pos_a[si])
        ball_b_ps.update_vertex_positions(ball_mesh[0] + pos_b[si])
        plate_ps.update_vertex_positions(plate_mesh[0] + pos_plate[si])

    ps.set_user_callback(callback)
    ps.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Stage E4 plots + visual demo")
    parser.add_argument("--plot-only", action="store_true",
                        help="Re-plot from saved data, no polyscope")
    args = parser.parse_args()

    out_dir = Path("docs/stageE4")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.plot_only:
        with open(out_dir / "aggregation_data.json") as f:
            agg_data = json.load(f)
        with open(out_dir / "dissipation_data.json") as f:
            dis_data = json.load(f)
    else:
        print("Running aggregation comparison...")
        agg_data = run_aggregation_comparison(out_dir)
        print("Running dissipation trace...")
        dis_data = run_dissipation_trace(out_dir)

    print("Generating plots...")
    plot_aggregation(agg_data, out_dir)
    plot_dissipation(dis_data, out_dir)

    # Visual demo
    if not args.plot_only:
        print("\nRunning two-ball visual demo...")
        modal = _build_slab_modal()
        vis_data = run_two_ball_visual(out_dir)
        print(f"  Recorded {len(vis_data['times'])} frames")
        print(f"  Final E_modal: {vis_data['E_modal'][-1]:.4f} J")
        print(f"  Cum injected:  {vis_data['cum_injected'][-1]:.4f} J")
        print(f"  Cum E_loss:    {vis_data['cum_loss'][-1]:.4f} J")
        print("\nLaunching polyscope...")
        run_polyscope(modal, vis_data)
    else:
        print("Done (--plot-only mode).")


if __name__ == "__main__":
    main()
