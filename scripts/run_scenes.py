#!/usr/bin/env python3
"""Extra demo scenes for passive DCR.

Three scenes demonstrating different impact scenarios:
  1. truck   — Heavy truck bounces on road, cones shake, lumber stack topples
  2. shelf   — Heavy object dropped on a shelf, books topple
  3. ledge   — Boulder hits a cliff ledge, balanced rocks fall off

Usage:
    uv run python scripts/run_scenes.py truck
    uv run python scripts/run_scenes.py shelf
    uv run python scripts/run_scenes.py ledge
    uv run python scripts/run_scenes.py all          # run all three
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.dcr import PassiveDCRCoupler, DCRWorld


H = 5e-3
ETA = 0.5

# Fixed simulated duration for the playback (seconds). n_steps is derived
# from this and the active timestep h, so changing h does not change the
# wallclock playback length — only the simulation resolution within it.
SIM_DURATION_DEFAULT = 2.0      # seconds, for shelf and ledge
SIM_DURATION_TRUCK = 1.8        # seconds, for truck (matches old 1800 steps @ h=1e-3)


def _fix_corners(mesh):
    v = mesh.vertices
    tol = 1e-8
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    mask = (((np.abs(v[:, 0] - xmin) < tol) | (np.abs(v[:, 0] - xmax) < tol)) &
            ((np.abs(v[:, 2] - zmin) < tol) | (np.abs(v[:, 2] - zmax) < tol)))
    return np.where(mask)[0].astype(np.int32)


def _fix_one_edge(mesh):
    """Fix only the -x edge (cantilever-style) for the shelf/ledge."""
    v = mesh.vertices
    tol = 1e-8
    xmin = v[:, 0].min()
    mask = np.abs(v[:, 0] - xmin) < tol
    return np.where(mask)[0].astype(np.int32)


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


# ======================================================================
# Scene 1: Truck on Road
# ======================================================================

def _add_coupler(
    world,
    modal,
    elastic_body_idx,
    velocity_mode: str = "coevoet",
    beta: float = 0.25,
    budget_source: str = "min_rigid_loss_modal",
    enforce_bound: bool = False,
    deformed_normal_method: str = "patch_fit",
    friction_cone_clip: bool = False,
    kinematic_cap: str = "none",
    causal_gating: bool = False,
    contact_shell_delta: float = 1e-4,
    v_min_closing: float = 0.044,
    e_modal_cutoff_frac: float = 1e-5,
):
    """Create and register a passive DCR coupler.

    Args:
        velocity_mode: PassiveDCRCoupler.dcr_velocity_mode. See
            docs/distant_velocity_modes.md.
        beta: PassiveDCRCoupler.energy_response_beta (for energy_* modes).
        budget_source: PassiveDCRCoupler.energy_budget_source.
        enforce_bound: DCRWorld.enforce_rigid_energy_bound. Recommended True
            when velocity_mode is one of the energy_* modes.
        deformed_normal_method: "patch_fit" (default) or "barbic_james".
            See PassiveDCRCoupler docstring + foundation §17.
        friction_cone_clip: Mitigate the post-solver tangential-leak
            sliding by projecting the deformed-normal kick onto the
            Coulomb cone around the REST normal. See
            PassiveDCRCoupler.friction_cone_clip_enabled docstring.
        kinematic_cap: "none" (default) or "coevoet" — cap the per-step
            energy-mode kick magnitude by d_max/h to recover Coevoet's
            h-invariance. See PassiveDCRCoupler.kinematic_cap docstring.
        causal_gating: Enable contact-causal passive coupling gates for
            patch mode (default False). When True, patch dispatch
            additionally requires the receiver to be within
            `contact_shell_delta` of the slab AND the slab to be moving
            into it at >= `v_min_closing`. See
            prompts/passive_contact_causal_modal_coupling.md.
        contact_shell_delta: Contact-shell tolerance δ in m (proposal §1).
        v_min_closing: Closing-velocity deadband in m/s (proposal §2).
        e_modal_cutoff_frac: Skip patch dispatch when modal energy drops
            below this fraction of the running-peak (proposal §3).
    """
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=elastic_body_idx,
        dcr_velocity_mode=velocity_mode,
        energy_response_beta=beta,
        energy_budget_source=budget_source,
        deformed_normal_method=deformed_normal_method,
        friction_cone_clip_enabled=friction_cone_clip,
        kinematic_cap=kinematic_cap,
        causal_gating=causal_gating,
        contact_shell_delta=contact_shell_delta,
        v_min_closing=v_min_closing,
        e_modal_cutoff_frac=e_modal_cutoff_frac,
    )
    world.enforce_rigid_energy_bound = enforce_bound
    world.add_passive_coupler(coupler)
    return coupler


def build_truck_scene(velocity_mode="coevoet", beta=0.25,
                      budget_source="min_rigid_loss_modal", enforce_bound=False,
                      deformed_normal_method="patch_fit",
                      friction_cone_clip=False, kinematic_cap="none",
                      damping_scale=1.0,
                      causal_gating=False,
                      contact_shell_delta=1e-4,
                      v_min_closing=0.044,
                      e_modal_cutoff_frac=1e-5):
    """Heavy objects dropped sequentially on road. Cones and lumber respond.

    Three drops at different positions and heights so they hit the ground
    one after another — each impact shakes the cones and lumber stack
    progressively harder.

    Inspired by the paper's 'Low-rider truck' scene (Figure 5).
    Ground is the elastic body; impactors, cones, and lumber are rigid.
    """
    world = DCRWorld(
        h=H, eta=ETA,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=120),
        dcr_enabled=True,
    )

    # Ground: wide elastic slab (2.5m x 1.5m, thin).
    mesh = make_slab_tet_mesh(length=2.5, width=1.5, height=0.06,
                              nx=16, ny=10, nz=2)
    mat = Material(E=10.0e9, nu=0.3, rho=500.0)  # stiff ground
    ground_top = 0.03
    ground = make_static_plane(normal=(0, 1, 0),
                               point=(0, ground_top, 0), friction=0.6)
    ground_idx = world.add_body(ground)

    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0 * damping_scale, alpha1=1e-5 * damping_scale)
    modal = ModalAnalysis(fem=fem, num_modes=15)
    coupler = _add_coupler(
        world, modal, ground_idx,
        velocity_mode=velocity_mode, beta=beta,
        budget_source=budget_source, enforce_bound=enforce_bound,
        deformed_normal_method=deformed_normal_method,
        friction_cone_clip=friction_cone_clip, kinematic_cap=kinematic_cap,
        causal_gating=causal_gating,
        contact_shell_delta=contact_shell_delta,
        v_min_closing=v_min_closing,
        e_modal_cutoff_frac=e_modal_cutoff_frac,
    )

    body_info = {}  # name -> (idx, hx, hy, hz, color)

    # Three sequential drops at different positions and heights.
    # Low drops with staggered timing via height:
    #   drop_0 hits at ~0.14s (0.1m), drop_1 at ~0.32s (0.5m), drop_2 at ~0.54s (1.4m)
    drops = [
        ("drop_light", -0.5,  0.10,  20.0, (0.4, 0.6, 0.9)),   # light, low
        ("drop_mid",   -0.3,  0.50,  50.0, (0.3, 0.4, 0.8)),   # medium
        ("drop_heavy", -0.05,  2.40, 100.0, (0.2, 0.25, 0.6)),  # heavy
    ]
    drop_hx, drop_hy, drop_hz = 0.10, 0.07, 0.08
    for name, dx, dy, mass, color in drops:
        drop = make_dynamic_box(
            mass=mass, hx=drop_hx, hy=drop_hy, hz=drop_hz,
            position=(dx, ground_top + drop_hy + dy, 0.0),
            restitution=0.05, friction=0.6,
        )
        idx = world.add_body(drop)
        body_info[name] = (idx, drop_hx, drop_hy, drop_hz, color)

    # Traffic cones: line of 5 small light boxes on right side.
    for ci, cz in enumerate([-0.4, -0.2, 0.0, 0.2, 0.4]):
        cone_hx, cone_hy, cone_hz = 0.025, 0.04, 0.025
        cone = make_dynamic_box(
            mass=0.3, hx=cone_hx, hy=cone_hy, hz=cone_hz,
            position=(0.6, ground_top + cone_hy + 0.001, cz),
            restitution=0.0, friction=0.5,
        )
        idx = world.add_body(cone)
        body_info[f"cone_{ci}"] = (idx, cone_hx, cone_hy, cone_hz, (1.0, 0.5, 0.0))

    # Lumber stack: 4 blocks stacked vertically.
    lumber_hx, lumber_hy, lumber_hz = 0.06, 0.025, 0.12
    for li in range(4):
        y = ground_top + lumber_hy + li * 2 * lumber_hy + 0.001 * (li + 1)
        lumber = make_dynamic_box(
            mass=2.0, hx=lumber_hx, hy=lumber_hy, hz=lumber_hz,
            position=(0.3, y, 0.0),
            restitution=0.0, friction=0.7,
        )
        idx = world.add_body(lumber)
        body_info[f"lumber_{li}"] = (idx, lumber_hx, lumber_hy, lumber_hz,
                                     (0.6, 0.35, 0.15))

    return world, coupler, body_info, mesh, "Road Impact (3 sequential drops)"


# ======================================================================
# Scene 2: Bookshelf Drop
# ======================================================================

def build_shelf_scene(velocity_mode="coevoet", beta=0.25,
                      budget_source="min_rigid_loss_modal", enforce_bound=False,
                      deformed_normal_method="patch_fit",
                      friction_cone_clip=False, kinematic_cap="none",
                      damping_scale=1.0,
                      causal_gating=False,
                      contact_shell_delta=1e-4,
                      v_min_closing=0.044,
                      e_modal_cutoff_frac=1e-5):
    """Heavy box dropped on a shelf. Books standing upright topple.

    The shelf is a cantilever beam (fixed at one edge). Books are
    thin tall dominoes standing on end. A heavy box drops
    onto the free end of the shelf.
    """
    world = DCRWorld(
        h=H, eta=ETA,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=120),
        dcr_enabled=True,
    )

    # Shelf: narrow elastic slab, fixed on left edge (cantilever).
    mesh = make_slab_tet_mesh(length=0.8, width=0.3, height=0.03,
                              nx=12, ny=5, nz=2)
    # Soft slab so the deformed normal (used by Version B) has visible
    # tilt during impact — previously controlled by the now-removed
    # `tilt_mode` flag.
    mat = Material(E=0.5e9, nu=0.3, rho=600.0)
    shelf_top = 0.015  # top of slab (height/2)
    shelf = make_static_plane(normal=(0, 1, 0),
                              point=(0, shelf_top, 0), friction=0.5)
    shelf_idx = world.add_body(shelf)

    fixed = _fix_one_edge(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=3.0 * damping_scale, alpha1=1e-5 * damping_scale)
    modal = ModalAnalysis(fem=fem, num_modes=12)
    coupler = _add_coupler(
        world, modal, shelf_idx,
        velocity_mode=velocity_mode, beta=beta,
        budget_source=budget_source, enforce_bound=enforce_bound,
        deformed_normal_method=deformed_normal_method,
        friction_cone_clip=friction_cone_clip, kinematic_cap=kinematic_cap,
        causal_gating=causal_gating,
        contact_shell_delta=contact_shell_delta,
        v_min_closing=v_min_closing,
        e_modal_cutoff_frac=e_modal_cutoff_frac,
    )

    body_info = {}

    # Books: thin tall dominoes standing upright on the shelf.
    book_colors = [
        (0.8, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.8),
        (0.7, 0.5, 0.1), (0.6, 0.2, 0.6),
    ]
    for bi in range(5):
        book_hx, book_hy, book_hz = 0.005, 0.04, 0.03  # thin x, tall y
        bx = -0.15 + bi * 0.04  # spaced ~1.5x height apart for domino chain
        book = make_dynamic_box(
            mass=1.3, hx=book_hx, hy=book_hy, hz=book_hz,
            position=(bx, shelf_top + book_hy + 0.001, 0.0),
            restitution=0.0, friction=0.3,
        )
        idx = world.add_body(book)
        body_info[f"book_{bi}"] = (idx, book_hx, book_hy, book_hz, book_colors[bi])

    # Heavy box dropped on the free end (right side) of the shelf.
    drop_hx, drop_hy, drop_hz = 0.05, 0.05, 0.05
    drop = make_dynamic_box(
        mass=8.0, hx=drop_hx, hy=drop_hy, hz=drop_hz,
        position=(0.15, shelf_top + drop_hy + 0.6, 0.0),
        restitution=0.1, friction=0.5,
    )
    idx = world.add_body(drop)
    body_info["drop"] = (idx, drop_hx, drop_hy, drop_hz, (0.3, 0.3, 0.3))

    return world, coupler, body_info, mesh, "Bookshelf Drop"


# ======================================================================
# Scene 3: Cliff Ledge / Rockfall
# ======================================================================

def build_ledge_scene(velocity_mode="coevoet", beta=0.25,
                      damping_scale=1.0,
                      budget_source="min_rigid_loss_modal", enforce_bound=False,
                      deformed_normal_method="patch_fit",
                      friction_cone_clip=False, kinematic_cap="none",
                      causal_gating=False,
                      contact_shell_delta=1e-4,
                      v_min_closing=0.044,
                      e_modal_cutoff_frac=1e-5):
    """Boulder hits a cliff ledge, balanced rocks fall off the edge.

    Inspired by the paper's 'Rockfall' scene. The ledge is an elastic
    slab fixed at one edge (the cliff wall). Rocks are small boxes
    balanced near the free edge. A heavy boulder drops onto the ledge.
    """
    world = DCRWorld(
        h=H, eta=ETA,
        solver=ConstraintSolver(h=H, cfm=1e-6, erp=0.2, pgs_iterations=120),
        dcr_enabled=True,
    )

    # Ledge: elastic slab, cantilever from left edge.
    mesh = make_slab_tet_mesh(length=1.2, width=0.8, height=0.08,
                              nx=12, ny=8, nz=2)
    mat = Material(E=10.0e9, nu=0.3, rho=2500.0)  # stone
    ledge_top = 0.04
    ledge = make_static_plane(normal=(0, 1, 0),
                              point=(0, ledge_top, 0), friction=0.5)
    ledge_idx = world.add_body(ledge)

    fixed = _fix_one_edge(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=1.0 * damping_scale, alpha1=1e-5 * damping_scale)
    modal = ModalAnalysis(fem=fem, num_modes=12)
    coupler = _add_coupler(
        world, modal, ledge_idx,
        velocity_mode=velocity_mode, beta=beta,
        budget_source=budget_source, enforce_bound=enforce_bound,
        deformed_normal_method=deformed_normal_method,
        friction_cone_clip=friction_cone_clip, kinematic_cap=kinematic_cap,
        causal_gating=causal_gating,
        contact_shell_delta=contact_shell_delta,
        v_min_closing=v_min_closing,
        e_modal_cutoff_frac=e_modal_cutoff_frac,
    )

    body_info = {}

    # Big box sitting at the free edge (right side) of the ledge.
    pedestal_hx, pedestal_hy, pedestal_hz = 0.06, 0.05, 0.06
    pedestal = make_dynamic_box(
        mass=5.0, hx=pedestal_hx, hy=pedestal_hy, hz=pedestal_hz,
        position=(0.0, ledge_top + pedestal_hy + 0.001, 0.0),
        restitution=0.0, friction=0.4,
    )
    idx = world.add_body(pedestal)
    body_info["pedestal"] = (idx, pedestal_hx, pedestal_hy, pedestal_hz,
                             (0.55, 0.45, 0.35))

    # Tall, thin pillars at the outer edge of the pedestal — barely balanced.
    pillar_hx, pillar_hy, pillar_hz = 0.01, 0.04, 0.01
    # Place at outer x-edge of pedestal (pedestal edge is at x = 0.5 + 0.06 = 0.56)
    # Pillar center at x = 0.54, so inner edge at 0.53, outer edge at 0.55 — near the lip.
    stack_offsets = [
        (0.04, 0.0, -0.035),  # front-edge
        (0.04, 0.0,  0.00),   # center-edge
        (0.04, 0.0,  0.035),  # back-edge
    ]
    colors = [(0.7, 0.3, 0.3), (0.3, 0.6, 0.3), (0.3, 0.3, 0.7)]
    pedestal_top = ledge_top + 2 * pedestal_hy + 0.001
    for si, ((sx, _, sz), color) in enumerate(zip(stack_offsets, colors)):
        box = make_dynamic_box(
            mass=0.5, hx=pillar_hx, hy=pillar_hy, hz=pillar_hz,
            position=(0.0 + sx, pedestal_top + pillar_hy + 0.001, sz),
            restitution=0.0, friction=0.5,
        )
        idx = world.add_body(box)
        body_info[f"box_{si}"] = (idx, pillar_hx, pillar_hy, pillar_hz, color)

    # Boulder: heavy rock dropped right next to the pedestal.
    boulder_h = 0.08
    boulder = make_dynamic_box(
        mass=50.0, hx=boulder_h, hy=boulder_h, hz=boulder_h,
        position=(0.30, ledge_top + boulder_h + 0.8, 0.0),
        restitution=0.1, friction=0.5,
    )
    idx = world.add_body(boulder)
    body_info["boulder"] = (idx, boulder_h, boulder_h, boulder_h, (0.5, 0.4, 0.3))

    return world, coupler, body_info, mesh, "Cliff Ledge Rockfall"


# ======================================================================
# Simulation + Polyscope playback
# ======================================================================

def simulate(world, coupler, body_info, n_steps=1500):
    """Settle then simulate, recording positions."""
    # Identify impactors: bodies named drop_*, truck, boulder, drop.
    impactor_names = {"drop", "truck", "boulder"}
    impactor_idxs = []
    for name, (idx, *_) in body_info.items():
        if name in impactor_names or name.startswith("drop_"):
            impactor_idxs.append(idx)

    # Settle: hold impactors static, DCR off.
    for idx in impactor_idxs:
        world.bodies[idx].is_static = True
    old_dcr = world.dcr_enabled
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    # Zero velocities of non-impactor bodies.
    for idx_body in range(len(world.bodies)):
        if idx_body not in impactor_idxs and not world.bodies[idx_body].is_static:
            world.bodies[idx_body].velocity[:] = 0.0
    for idx in impactor_idxs:
        world.bodies[idx].is_static = False
    world.dcr_enabled = old_dcr
    world.time = 0.0

    # Record.
    times = []
    positions = {name: [] for name in body_info}
    orientations = {name: [] for name in body_info}

    for step_i in range(n_steps):
        world.step()
        times.append(world.time)
        for name, (idx, *_) in body_info.items():
            positions[name].append(world.bodies[idx].position.copy())
            orientations[name].append(world.bodies[idx].orientation.copy())

    return times, positions, orientations


def playback_polyscope(mesh, body_info, times, positions, orientations, title):
    """Interactive polyscope playback driven by wall-clock time.

    Previously the playback advanced by ONE stored frame per polyscope
    render tick, which meant the wall-clock speed depended on the sim
    timestep h: at h=1e-3 the animation ran ~0.18× real-time, at h=1e-2
    it ran ~1.8× real-time. Now we advance by the actual wall-clock dt
    multiplied by a user-controlled `speed` slider (default 1.0 =
    real-time), and pick the nearest stored frame. Playback speed is
    therefore independent of h.
    """
    import time
    import polyscope as ps
    from dcr.rigid.body import quat_to_rot

    ps.init()
    ps.set_up_dir("y_up")
    ps.set_ground_plane_mode("shadow_only")

    # Register elastic surface.
    surface = mesh.extract_surface()
    ps.register_surface_mesh("elastic_surface", surface.vertices,
                             surface.faces, color=(0.6, 0.5, 0.35))

    # Render the infinite collision plane as a large semi-transparent quad.
    # Offset slightly below the slab surface to avoid Z-fighting.
    plane_y = mesh.vertices[:, 1].max() - 0.001
    plane_sz = 3.0
    plane_verts = np.array([
        [-plane_sz, plane_y, -plane_sz],
        [+plane_sz, plane_y, -plane_sz],
        [+plane_sz, plane_y, +plane_sz],
        [-plane_sz, plane_y, +plane_sz],
    ])
    plane_faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32)
    ps.register_surface_mesh("ground_plane", plane_verts, plane_faces,
                             color=(0.85, 0.85, 0.80), transparency=0.5)

    # Register each body.
    ps_meshes = {}
    box_meshes = {}
    for name, (idx, hx, hy, hz, color) in body_info.items():
        bm = _box_mesh(hx, hy, hz)
        box_meshes[name] = bm
        R0 = quat_to_rot(orientations[name][0])
        pos0 = positions[name][0]
        sm = ps.register_surface_mesh(name, (R0 @ bm[0].T).T + pos0, bm[1], color=color)
        ps_meshes[name] = sm

    n_total = len(times)
    t_first = float(times[0])
    t_last = float(times[-1])
    # Recorded timestep (= world.h). Assumes uniform spacing — matches
    # how `simulate()` records exactly one snapshot per step.
    if n_total > 1:
        dt_record = float(times[1] - times[0])
    else:
        dt_record = 1.0  # degenerate, but avoid div-zero

    sim_t = [t_first]              # current displayed simulated time (s)
    is_playing = [True]
    speed = [1.0]                  # wall-clock × speed = simulated-time / s
    last_wall = [None]             # last callback's perf_counter()

    def _frame_for_sim_t(t: float) -> int:
        si = int(round((t - t_first) / dt_record))
        return max(0, min(si, n_total - 1))

    def callback():
        import polyscope.imgui as imgui
        now = time.perf_counter()
        if last_wall[0] is None:
            last_wall[0] = now
        dt_wall = now - last_wall[0]
        last_wall[0] = now

        if is_playing[0]:
            sim_t[0] += dt_wall * speed[0]
            if sim_t[0] >= t_last:
                sim_t[0] = t_last
                is_playing[0] = False

        # UI: scrubber over simulated time (seconds), independent of h.
        changed, new_val = imgui.SliderFloat(
            "Time (s)", float(sim_t[0]), t_first, t_last)
        if changed:
            sim_t[0] = float(new_val)
        _, is_playing[0] = imgui.Checkbox("Play", is_playing[0])
        _, speed[0] = imgui.SliderFloat("Speed", speed[0], 0.05, 4.0)

        si = _frame_for_sim_t(sim_t[0])
        imgui.Text(f"{title}  (eta={ETA})")
        imgui.Text(f"t = {times[si]*1000:.0f} ms   "
                   f"(h = {dt_record*1000:.2f} ms, speed = {speed[0]:.2f}×)")

        for name in body_info:
            R = quat_to_rot(orientations[name][si])
            ps_meshes[name].update_vertex_positions(
                (R @ box_meshes[name][0].T).T + positions[name][si])

    ps.set_user_callback(callback)
    ps.show()


# ======================================================================
# Main
# ======================================================================

SCENES = {
    "truck": build_truck_scene,
    "shelf": build_shelf_scene,
    "ledge": build_ledge_scene,
}


_VALID_VELOCITY_MODES = {
    "dcr",
    "energy_prescribed",
    "energy_prescribed_point_impulse",
    "energy_prescribed_patch",
}

# CLI mode name -> PassiveDCRCoupler.dcr_velocity_mode string.
# "dcr" is the short CLI alias for the paper's baseline (internally "coevoet").
_CLI_TO_COUPLER_MODE = {
    "dcr": "coevoet",
    "energy_prescribed": "energy_prescribed",
    "energy_prescribed_point_impulse": "energy_prescribed_point_impulse",
    # Step 1 of the patch-based reformulation (prompt §9.1). Currently
    # response-silent — clusters contacts and builds patches but emits no
    # kicks. Observable via coupler.last_patches.
    "energy_prescribed_patch": "energy_prescribed_patch",
}


def _parse_kv_flag(name: str, default):
    """Tiny --name value / --name=value parser."""
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default


def main():
    if len(sys.argv) < 2 or any(a in ("-h", "--help") for a in sys.argv):
        print("Usage: uv run python scripts/run_scenes.py <scene> "
              "[--mode <name>] [--beta <0..1>] [--budget-source <name>] "
              "[--sim-duration <seconds>]")
        print(f"  Available scenes: {', '.join(SCENES.keys())}, all")
        print(f"  --mode <name>:    DCR distant velocity mode "
              f"(default: dcr). One of:")
        print(f"                      dcr                              (paper Eq. 12, Coevoet 2020 baseline)")
        print(f"                      energy_prescribed                (Version A: linear COM kick, deformed normal)")
        print(f"                      energy_prescribed_point_impulse  (Version B: true point impulse, deformed normal)")
        print(f"                      energy_prescribed_patch          (Patch reformulation step 1: clusters")
        print(f"                                                       contacts by body pair, builds geometric")
        print(f"                                                       patches; response-silent — no kicks yet.")
        print(f"                                                       Observable via coupler.last_patches.)")
        print(f"  --beta <0..1>:    energy_response_beta (default: 0.25). "
              f"Used by energy_* modes.")
        print(f"  --budget-source:  rigid_loss | modal_reservoir | "
              f"min_rigid_loss_modal (default).")
        print(f"  --deformed-normal-method: patch_fit (default) | barbic_james.")
        print(f"                            patch_fit = surface plane-fit "
              f"heuristic (existing).")
        print(f"                            barbic_james = F^-T push-forward "
              f"using FEM shape-function gradients")
        print(f"                            (foundation §17; Barbič & James "
              f"2008 IEEE ToH §4.1).")
        print(f"  --friction-cone-clip:     Project the post-solver kick onto "
              f"the Coulomb cone around the REST contact normal,")
        print(f"                            preventing the tangential 'sliding' "
              f"leak from a deformed-normal kick (energy_* modes).")
        print(f"                            Default off. Recommended on for "
              f"the energy_* modes with deformed normal.")
        print(f"  --kinematic-cap:  none (default) | coevoet.")
        print(f"                            coevoet caps per-step γ ≤ d_max/h, "
              f"recovering Coevoet's h-invariance as an upper bound")
        print(f"                            (energy_* modes). Useful at "
              f"large h to prevent oversized kicks.")
        print(f"  --damping-scale:  Multiply the FEM Rayleigh damping (α₀, α₁) "
              f"by this factor (default: 1.0). Use larger values (e.g.,")
        print(f"                    5-20) to make the elastic slab settle "
              f"faster — useful for `energy_prescribed_patch` which keeps")
        print(f"                    delivering kicks to bodies on the slab "
              f"as long as the modal reservoir has energy.")
        print(f"  --sim-duration:   Simulated duration in seconds; n_steps is "
              f"derived as round(duration / h) so playback length stays "
              f"constant when you change h (default: 2.0s, truck: 1.8s).")
        print(f"  --causal-gating:  Enable contact-causal patch gates "
              f"(default off; energy_prescribed_patch only).")
        print(f"                    Combines: (1) contact-shell gate "
              f"(gap <= delta), (2) closing-velocity deadband, (3) numerical")
        print(f"                    E_modal cutoff. See "
              f"prompts/passive_contact_causal_modal_coupling.md.")
        print(f"  --contact-shell-delta <f>: shell tolerance δ in m "
              f"(default: 1e-4).")
        print(f"  --v-min-closing <f>:       closing-velocity deadband in m/s "
              f"(default: 0.044 = √(2·g·1e-4)).")
        print(f"  --e-modal-cutoff-frac <f>: numerical cutoff as fraction "
              f"of peak E_modal (default: 1e-5).")
        sys.exit(1)

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    # Skip positional args that come after a known --flag (its value).
    # --friction-cone-clip is a boolean (no value) and is NOT in this list.
    flag_value_args = set()
    for i, a in enumerate(sys.argv):
        if a in ("--mode", "--beta", "--budget-source",
                 "--deformed-normal-method",
                 "--kinematic-cap",
                 "--damping-scale",
                 "--sim-duration",
                 "--contact-shell-delta",
                 "--v-min-closing",
                 "--e-modal-cutoff-frac") and i + 1 < len(sys.argv):
            flag_value_args.add(sys.argv[i + 1])
    args = [a for a in args if a not in flag_value_args]

    velocity_mode = _parse_kv_flag("--mode", "dcr")
    if velocity_mode not in _VALID_VELOCITY_MODES:
        print(f"Unknown --mode: {velocity_mode!r}")
        print(f"Valid: {sorted(_VALID_VELOCITY_MODES)}")
        sys.exit(1)
    try:
        beta = float(_parse_kv_flag("--beta", 0.25))
    except ValueError:
        print(f"--beta must be a float; got {_parse_kv_flag('--beta', None)!r}")
        sys.exit(1)
    budget_source = _parse_kv_flag("--budget-source", "min_rigid_loss_modal")
    deformed_normal_method = _parse_kv_flag(
        "--deformed-normal-method", "patch_fit")
    if deformed_normal_method not in ("patch_fit", "barbic_james"):
        print(f"Unknown --deformed-normal-method: {deformed_normal_method!r}")
        print(f"Valid: patch_fit, barbic_james")
        sys.exit(1)
    friction_cone_clip = "--friction-cone-clip" in sys.argv
    kinematic_cap = _parse_kv_flag("--kinematic-cap", "none")
    if kinematic_cap not in ("none", "coevoet"):
        print(f"Unknown --kinematic-cap: {kinematic_cap!r}")
        print(f"Valid: none, coevoet")
        sys.exit(1)
    try:
        damping_scale = float(_parse_kv_flag("--damping-scale", 1.0))
    except ValueError:
        print(f"--damping-scale must be a float; got "
              f"{_parse_kv_flag('--damping-scale', None)!r}")
        sys.exit(1)
    if damping_scale <= 0.0:
        print(f"--damping-scale must be > 0; got {damping_scale}")
        sys.exit(1)

    # Contact-causal gate flags (proposal: prompts/passive_contact_causal_modal_coupling.md).
    causal_gating = "--causal-gating" in sys.argv
    try:
        contact_shell_delta = float(_parse_kv_flag("--contact-shell-delta", 1e-4))
        v_min_closing = float(_parse_kv_flag("--v-min-closing", 0.044))
        e_modal_cutoff_frac = float(_parse_kv_flag("--e-modal-cutoff-frac", 1e-5))
    except ValueError:
        print("--contact-shell-delta / --v-min-closing / --e-modal-cutoff-frac "
              "must be floats")
        sys.exit(1)

    sim_duration_arg = _parse_kv_flag("--sim-duration", None)

    # Map --mode → (coupler.dcr_velocity_mode, enforce_rigid_energy_bound).
    # The patch mode is included here so the world enforces the rigid-energy
    # bound consistently with the other energy_* modes — it's a no-op for
    # step 1 (no kicks emitted) but keeps semantics aligned for §9.2-9.6.
    is_energy_mode = velocity_mode in (
        "energy_prescribed",
        "energy_prescribed_point_impulse",
        "energy_prescribed_patch",
    )
    coupler_mode = _CLI_TO_COUPLER_MODE[velocity_mode]
    enforce_bound = is_energy_mode  # cap recommended on for energy_* modes

    scene_name = args[0] if args else "all"

    if scene_name == "all":
        names = list(SCENES.keys())
    elif scene_name in SCENES:
        names = [scene_name]
    else:
        print(f"Unknown scene: {scene_name}")
        print(f"Available: {', '.join(SCENES.keys())}, all")
        sys.exit(1)

    mode_str = ""
    if velocity_mode != "dcr":
        mode_str = f" + {velocity_mode}"
        if is_energy_mode:
            mode_str += f"(β={beta})"
            if friction_cone_clip:
                mode_str += " +clip"
            if kinematic_cap != "none":
                mode_str += f" +cap={kinematic_cap}"
            if causal_gating:
                mode_str += " +causal"

    for name in names:
        print(f"\n{'='*60}")
        print(f"Building scene: {name}{mode_str}")
        print(f"{'='*60}")
        world, coupler, body_info, mesh, title = SCENES[name](
            velocity_mode=coupler_mode,
            beta=beta,
            budget_source=budget_source,
            enforce_bound=enforce_bound,
            deformed_normal_method=deformed_normal_method,
            friction_cone_clip=friction_cone_clip,
            kinematic_cap=kinematic_cap,
            damping_scale=damping_scale,
            causal_gating=causal_gating,
            contact_shell_delta=contact_shell_delta,
            v_min_closing=v_min_closing,
            e_modal_cutoff_frac=e_modal_cutoff_frac,
        )
        print(f"  Bodies: {len(world.bodies)}")
        print(f"  Dynamic: {[n for n in body_info]}")

        # Derive n_steps from a fixed simulated duration so playback length
        # is independent of the active timestep h.
        if sim_duration_arg is not None:
            sim_duration = float(sim_duration_arg)
        else:
            sim_duration = SIM_DURATION_TRUCK if name == "truck" else SIM_DURATION_DEFAULT
        n_steps = max(1, int(round(sim_duration / world.h)))
        print(f"Simulating ({sim_duration:.2f}s @ h={world.h:.4g} → "
              f"{n_steps} steps)...")
        times, positions, orientations = simulate(
            world, coupler, body_info, n_steps=n_steps)
        print(f"  Done. {len(times)} frames recorded.")

        print("Launching polyscope...")
        playback_polyscope(mesh, body_info, times, positions, orientations, title)


if __name__ == "__main__":
    main()
