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
from dcr.dcr import PassiveDCRCoupler, TiltDCRCoupler, DCRWorld


H = 1e-3
ETA = 0.5


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
    tilt_mode=None,
    velocity_mode: str = "coevoet",
    beta: float = 0.25,
    budget_source: str = "min_rigid_loss_modal",
    enforce_bound: bool = False,
):
    """Create and register a passive (or tilt) DCR coupler.

    Args:
        tilt_mode: None for standard DCR, "tilt" or "tilt-coupled" for tilt extension.
        velocity_mode: PassiveDCRCoupler.dcr_velocity_mode. See
            docs/distant_velocity_modes.md.
        beta: PassiveDCRCoupler.energy_response_beta (for energy_* modes).
        budget_source: PassiveDCRCoupler.energy_budget_source.
        enforce_bound: DCRWorld.enforce_rigid_energy_bound. Recommended True
            when velocity_mode is one of the energy_* modes.
    """
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=elastic_body_idx,
        dcr_velocity_mode=velocity_mode,
        energy_response_beta=beta,
        energy_budget_source=budget_source,
    )
    world.enforce_rigid_energy_bound = enforce_bound
    if tilt_mode:
        # NOTE: TiltDCRCoupler.process_step calls passive.process_step
        # WITHOUT `bodies`, which the energy_* modes require. The main()
        # CLI rejects this combination before reaching here.
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
        world.tilt_mode = tilt_mode
    else:
        world.add_passive_coupler(coupler)
    return coupler


def build_truck_scene(tilt_mode=None, velocity_mode="coevoet", beta=0.25,
                      budget_source="min_rigid_loss_modal", enforce_bound=False):
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
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=15)
    coupler = _add_coupler(
        world, modal, ground_idx, tilt_mode=tilt_mode,
        velocity_mode=velocity_mode, beta=beta,
        budget_source=budget_source, enforce_bound=enforce_bound,
    )

    body_info = {}  # name -> (idx, hx, hy, hz, color)

    # Three sequential drops at different positions and heights.
    # Low drops with staggered timing via height:
    #   drop_0 hits at ~0.14s (0.1m), drop_1 at ~0.32s (0.5m), drop_2 at ~0.54s (1.4m)
    drops = [
        ("drop_light", -0.5,  0.10,  20.0, (0.4, 0.6, 0.9)),   # light, low
        ("drop_mid",   -0.3,  0.50,  50.0, (0.3, 0.4, 0.8)),   # medium
        ("drop_heavy", -0.05,  2.40, 220.0, (0.2, 0.25, 0.6)),  # heavy
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

def build_shelf_scene(tilt_mode=None, velocity_mode="coevoet", beta=0.25,
                      budget_source="min_rigid_loss_modal", enforce_bound=False):
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
    mat = Material(E=0.5e9 if tilt_mode else 8.0e9, nu=0.3, rho=600.0)
    shelf_top = 0.015  # top of slab (height/2)
    shelf = make_static_plane(normal=(0, 1, 0),
                              point=(0, shelf_top, 0), friction=0.5)
    shelf_idx = world.add_body(shelf)

    fixed = _fix_one_edge(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=3.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=12)
    coupler = _add_coupler(
        world, modal, shelf_idx, tilt_mode=tilt_mode,
        velocity_mode=velocity_mode, beta=beta,
        budget_source=budget_source, enforce_bound=enforce_bound,
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
            mass=0.3, hx=book_hx, hy=book_hy, hz=book_hz,
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

def build_ledge_scene(tilt_mode=None, velocity_mode="coevoet", beta=0.25,
                      budget_source="min_rigid_loss_modal", enforce_bound=False):
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
                   alpha0=1.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=12)
    coupler = _add_coupler(
        world, modal, ledge_idx, tilt_mode=tilt_mode,
        velocity_mode=velocity_mode, beta=beta,
        budget_source=budget_source, enforce_bound=enforce_bound,
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
    """Interactive polyscope playback with rotation."""
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
        imgui.Text(f"{title}  (eta={ETA})")
        imgui.Text(f"t = {times[si]*1000:.0f} ms")

        if is_playing[0]:
            if frame_idx[0] < n_frames - 1:
                frame_idx[0] += 1
            else:
                is_playing[0] = False

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
    "coevoet",
    "bounded_coevoet",
    "energy_prescribed",
    "energy_prescribed_point_impulse",
}


def _parse_kv_flag(name: str, default):
    """Tiny --name value / --name=value parser (avoids argparse to keep the
    positional `<scene>` argument and the existing --tilt flags intact)."""
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default


def main():
    if len(sys.argv) < 2 or any(a in ("-h", "--help") for a in sys.argv):
        print("Usage: uv run python scripts/run_scenes.py <scene> "
              "[--tilt|--tilt-coupled] [--mode <name>] [--beta <0..1>] "
              "[--budget-source <name>]")
        print(f"  Available scenes: {', '.join(SCENES.keys())}, all")
        print(f"  --tilt:           Lateral-only tilt extension")
        print(f"  --tilt-coupled:   Capped vertical + lateral tilt extension")
        print(f"  --mode <name>:    DCR distant velocity mode "
              f"(default: coevoet). One of:")
        print(f"                      coevoet                          (paper Eq. 12)")
        print(f"                      bounded_coevoet                  (Eq. 12 + rigid-energy cap)")
        print(f"                      energy_prescribed                (Version A, linear)")
        print(f"                      energy_prescribed_point_impulse  (Version B, point impulse)")
        print(f"  --beta <0..1>:    energy_response_beta (default: 0.25). "
              f"Used by energy_* modes.")
        print(f"  --budget-source:  rigid_loss | modal_reservoir | "
              f"min_rigid_loss_modal (default).")
        print(f"  NOTE: --tilt / --tilt-coupled is mutually exclusive "
              f"with the energy_* modes.")
        sys.exit(1)

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    # Skip positional args that come after a known --flag (its value).
    flag_value_args = set()
    for i, a in enumerate(sys.argv):
        if a in ("--mode", "--beta", "--budget-source") and i + 1 < len(sys.argv):
            flag_value_args.add(sys.argv[i + 1])
    args = [a for a in args if a not in flag_value_args]

    tilt_mode = None
    if "--tilt-coupled" in sys.argv:
        tilt_mode = "tilt-coupled"
    elif "--tilt" in sys.argv:
        tilt_mode = "tilt"

    velocity_mode = _parse_kv_flag("--mode", "coevoet")
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

    # Map --mode → (coupler.dcr_velocity_mode, enforce_rigid_energy_bound).
    # "bounded_coevoet" is "coevoet" with the rigid-energy cap on.
    is_energy_mode = velocity_mode in (
        "energy_prescribed", "energy_prescribed_point_impulse")
    if velocity_mode == "bounded_coevoet":
        coupler_mode = "coevoet"
        enforce_bound = True
    else:
        coupler_mode = velocity_mode
        enforce_bound = is_energy_mode  # cap recommended on for energy_* modes

    # Tilt + energy_* is a semantic conflict — see docs/distant_velocity_modes.md.
    if tilt_mode and is_energy_mode:
        print(f"Error: --tilt / --tilt-coupled is incompatible with "
              f"--mode {velocity_mode}.")
        print(f"  Version B is the unified cleaner alternative to the tilt "
              f"coupler's decomposition; using both together is a semantic "
              f"conflict.")
        print(f"  Pick one:")
        print(f"    drop {('--tilt-coupled' if tilt_mode == 'tilt-coupled' else '--tilt')}, "
              f"or")
        print(f"    use --mode coevoet (or bounded_coevoet) with the tilt flag.")
        sys.exit(1)

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
    if tilt_mode:
        mode_str += f" + {tilt_mode.upper()}"
    if velocity_mode != "coevoet":
        mode_str += f" + {velocity_mode}"
        if is_energy_mode:
            mode_str += f"(β={beta})"

    for name in names:
        print(f"\n{'='*60}")
        print(f"Building scene: {name}{mode_str}")
        print(f"{'='*60}")
        world, coupler, body_info, mesh, title = SCENES[name](
            tilt_mode=tilt_mode,
            velocity_mode=coupler_mode,
            beta=beta,
            budget_source=budget_source,
            enforce_bound=enforce_bound,
        )
        if tilt_mode:
            title += f" [{tilt_mode.upper()}]"
        print(f"  Bodies: {len(world.bodies)}")
        print(f"  Dynamic: {[n for n in body_info]}")

        n_steps = 1800 if name == "truck" else 2000
        print(f"Simulating ({n_steps * H:.1f}s)...")
        times, positions, orientations = simulate(world, coupler, body_info, n_steps=n_steps)
        print(f"  Done. {len(times)} frames recorded.")

        print("Launching polyscope...")
        playback_polyscope(mesh, body_info, times, positions, orientations, title)


if __name__ == "__main__":
    main()
