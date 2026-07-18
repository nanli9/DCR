"""Dinner-table scene driven by the Reduced-Coordinate AVBD coupler.

This duplicates the DCR paper's §5.1 "Dinner is served" setting (Fig. 1):
a banquet-size table (2.2 × 1.1 m) with six place settings (plate + fork +
knife), four teacups, two candlesticks, and a 5 kg pot dropped from above —
masses per §5.1 (plates 0.5 kg, teacups 0.4 kg, candlesticks 0.8 kg) and
table material per Table 2 (E = 1.1 GPa, nu = 0.3, rho = 770 kg/m³). Unlike
the paper, the drop point `pot_drop_xz` is a parameter, so the
distance-attenuation of the response can be shown on the table itself
(the paper demonstrates position sweeps only on the ground/scaffold
spatial-attenuation path, §5.3).

The table is the reduced-modal deformable support; the pot's impact rings
the table's modal field and the coupling rocks the place settings through
the deformed support geometry (native q-in-solver path, or the coupled
AVBD/XPBD paths).

Each body carries `render_kind` so the viewer can skin it with the
decorated asset in `model/{kind}/` and toggle the collision proxy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import (
    ReducedSupport,
    make_debug_reduced_shelf_support,
)

from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z
from scenes.reduced_scene_common import make_cargo_cube, register_all_cargo


@dataclass
class DinnerBody:
    """Per-body render metadata for the viewer (mirrors run_scenes_avbd's
    SceneBox: the box half_extents ARE the collision proxy; render_kind
    only swaps the decorated template at draw time)."""
    name: str
    dcr_idx: int
    half_extents: tuple[float, float, float]
    color: tuple[float, float, float]
    render_kind: str = "box"
    orientation_wxyz: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)


@dataclass
class DinnerSceneHandle:
    """Bundle the viewer needs. Kept field-compatible with
    ShelfSceneHandle (`.rs`, `.impactor_idx`, `.probe_indices`) so the
    reduced viewer's diagnostics keep working; `.bodies` adds the
    decorated-render metadata."""
    world: AVBDDCRWorld
    rs: ReducedSupport
    impactor_idx: int                       # the pot
    probe_indices: list[int]                # the place-setting plates
    bodies: list[DinnerBody] = field(default_factory=list)
    name: str = "Reduced-Coordinate AVBD Dinner Table"
    cargo_cube: object = None
    cargo_avbd_idx: int | None = None
    cargo_material: str | None = None
    # All-cargo wiring (§N2 generalization): {dcr_idx: (cargo_body, avbd_idx)}
    # for EVERY body when built with cargo_all=True; empty otherwise.
    cargo_map: dict = field(default_factory=dict)


def build_reduced_dinner_table(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 6,
    avbd_substeps: int = 2,
    # Table = the reduced-modal support. DCR §5.1 "Dinner is served"
    # duplication: banquet-size table, paper Table 2 material (E = 1.1 GPa,
    # nu = 0.3, rho = 770 — the §5.1 prose says 700 kg/m³; Table 2 says 770,
    # we follow Table 2). The low E is the paper's own trick: "low to account
    # for the fact that our finite element model is solid while a typical
    # table will be constructed from thinner pieces of wood".
    table_length: float = 2.2,
    table_width: float = 1.1,
    table_thickness: float = 0.04,
    table_top: float = 0.03,
    youngs: float = 1.1e9,
    density: float = 770.0,
    poisson: float = 0.30,
    n_modes_global: int = 10,
    n_modes_local: int = 14,
    pot_drop_height: float = 0.5,
    pot_mass: float = 5.0,                     # DCR §5.1: pot is 5 kg
    pot_drop_xz: tuple[float, float] = (0.0, 0.0),
    pot_v0_y: float = 0.0,
    util_mass: float = 0.06,
    util_half_y: float = 0.005,
    rayleigh_alpha0: float = 2.0,
    rayleigh_alpha1: float = 1.0e-5,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = True,
    modal_static_lp_tau: float = 0.05,
    solver: str = "avbd",
    cargo_material: str | None = None,
    cargo_all: bool = False,
    cargo_n_elastic: int = 6,
    support_basis: str = "debug",
) -> DinnerSceneHandle:
    """Construct the dinner-table scene + attach the reduced-coupled AVBD
    support (the table). Returns a handle carrying per-body render
    metadata for the decorated viewer."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
        solver_kind=solver if solver in ("xpbd", "impulse") else "avbd",
    )
    # Table-as-floor: AVBD's floor is +y up; objects rest at y = table_top.
    world.add_floor(floor_y=table_top, friction=0.5, name="table")

    bodies: list[DinnerBody] = []

    def _add(name, mass, half, pos, color, kind,
             quat=(1.0, 0.0, 0.0, 0.0), friction=0.4, vel=(0.0, 0.0, 0.0)):
        idx = world.add_box(
            mass=mass, half_extents=half, position=pos,
            orientation_wxyz=quat, velocity_lin=vel, friction=friction,
            name=name,
        )
        bodies.append(DinnerBody(
            name=name, dcr_idx=idx, half_extents=half,
            color=color, render_kind=kind, orientation_wxyz=quat))
        return idx

    # ---- Six place settings (plate flanked by fork / knife), DCR §5.1
    # masses: plates 0.5 kg. Three settings per long side of the table. ----
    plate_h = (0.085, 0.010, 0.085)
    plate_palette = [
        (0.95, 0.92, 0.85), (0.85, 0.65, 0.55),
        (0.55, 0.70, 0.85), (0.80, 0.80, 0.70),
    ]
    px_spots = (-0.72, 0.0, 0.72)
    plate_spots = [(px, sz * 0.34) for sz in (-1.0, 1.0) for px in px_spots]
    fork_h = (0.10, util_half_y, 0.012)
    knife_h = (0.10, util_half_y, 0.013)
    util_color = (0.78, 0.80, 0.85)
    util_offset = 0.13
    util_q = (0.70710678, 0.0, 0.70710678, 0.0)  # 90° about +Y

    plate_indices: list[int] = []
    resting_xz: list[tuple[float, float]] = []
    for pi, (px, pz) in enumerate(plate_spots):
        pidx = _add(f"plate_{pi}", 0.5, plate_h,
                    (px, table_top + plate_h[1] + 0.001, pz),
                    plate_palette[pi % 4], "plate")
        plate_indices.append(pidx)
        resting_xz.append((px, pz))
        sign_z = 1.0 if pz > 0 else -1.0
        fork_x = px + sign_z * util_offset
        knife_x = px - sign_z * util_offset
        _add(f"fork_{pi}", util_mass, fork_h,
             (fork_x, table_top + fork_h[1] + 0.001, pz),
             util_color, "fork", quat=util_q)
        _add(f"knife_{pi}", util_mass, knife_h,
             (knife_x, table_top + knife_h[1] + 0.001, pz),
             util_color, "knife", quat=util_q)
        resting_xz.append((fork_x, pz))
        resting_xz.append((knife_x, pz))

    # ---- Four teacups (DCR §5.1: 0.4 kg), on the inner side of the outer
    # place settings. No cup asset in model/ — a small pot renders as a cup.
    cup_h = (0.035, 0.030, 0.035)
    cup_color = (0.93, 0.90, 0.88)
    cup_spots = [(px + 0.16, pz - (0.16 if pz > 0 else -0.16))
                 for (px, pz) in plate_spots if px != 0.0]
    for ci, (cx, cz) in enumerate(cup_spots):
        _add(f"cup_{ci}", 0.4, cup_h,
             (cx, table_top + cup_h[1] + 0.001, cz),
             cup_color, "pot", friction=0.45)
        resting_xz.append((cx, cz))

    # ---- Two candlesticks on the centre line (DCR §5.1: 0.8 kg) ----
    candle_h = (0.025, 0.090, 0.025)
    candle_palette = [(0.94, 0.88, 0.74), (0.78, 0.20, 0.18)]
    candle_spots = [(-0.45, 0.0), (0.45, 0.0)]
    for ci, (cx, cz) in enumerate(candle_spots):
        _add(f"candle_{ci}", 0.8, candle_h,
             (cx, table_top + candle_h[1] + 0.001, cz),
             candle_palette[ci % 2], "candle", friction=0.45)
        resting_xz.append((cx, cz))

    # ---- The pot (DCR §5.1: 5 kg): drops on `pot_drop_xz` — the paper drops
    # it once at the centre; parameterizing the drop point is what lets the
    # distance-attenuation story be shown on the table itself. ----
    pot_h = (0.13, 0.065, 0.082)
    pot_x, pot_z = (float(v) for v in pot_drop_xz)
    pot_idx = _add("pot", pot_mass, pot_h,
                   (pot_x, table_top + pot_h[1] + pot_drop_height, pot_z),
                   (0.20, 0.18, 0.16), "pot", friction=0.5,
                   vel=(0.0, float(pot_v0_y), 0.0))

    # ---- Reduced-modal support (synthetic basis). Bump modes are placed
    # at the pot impact point + every resting object so the q-block has
    # local compliance where the contact happens. ----
    contact_zones = [(pot_x, pot_z)] + resting_xz
    if support_basis == "fem":
        # G1 shared-operator arm (docs/benchmark_plan.md §4): the table's
        # modal basis IS the eigenbasis of the same discrete FEM operator the
        # all-FEM GT integrates — same mesh rule (§3 rung R1: 20 cells/m,
        # 3 through thickness), same corner-column Dirichlet set, same
        # Rayleigh damping. Impedance/damping gain knobs are deliberately NOT
        # applied here: scaling the physical operator would break sharing.
        from dcr.avbd.fem_modal_support import make_fem_modal_support
        from dcr.fem.fem_model import FEMModel
        from dcr.fem.material import Material
        from dcr.fem.multibody_gt import corner_column_nodes
        from dcr.geom.tet_mesh import make_slab_tet_mesh
        mesh = make_slab_tet_mesh(
            length=table_length, width=table_width, height=table_thickness,
            nx=max(6, int(round(20.0 * table_length))),
            ny=max(4, int(round(20.0 * table_width))), nz=3)
        fem = FEMModel(mesh=mesh,
                       material=Material(E=youngs, nu=poisson, rho=density),
                       fixed_nodes=corner_column_nodes(mesh),
                       alpha0=rayleigh_alpha0, alpha1=rayleigh_alpha1)
        rs, _ = make_fem_modal_support(
            fem, num_modes=n_modes_global + n_modes_local, y_rest=table_top,
            n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z, probe_xz=resting_xz)
    elif support_basis == "debug":
        rs = make_debug_reduced_shelf_support(
            length=table_length, width=table_width, thickness=table_thickness,
            youngs=youngs, density=density, poisson=poisson,
            n_modes_global=n_modes_global, n_modes_local=n_modes_local,
            contact_zone_centers=contact_zones,
            probe_xz=resting_xz,
            y_rest=table_top,
            overlay_enabled=False, restart_overlay_each_step=False,
            rayleigh_alpha0=rayleigh_alpha0, rayleigh_alpha1=rayleigh_alpha1,
            modal_impedance_scale=modal_impedance_scale,
            modal_damping_scale=modal_damping_scale,
            to_eigenbasis=to_eigenbasis,
        )
    else:
        raise ValueError(f"unknown support_basis {support_basis!r} "
                         "(debug | fem)")

    # DCR idx → AVBD idx (the coupler tracks AVBD-side indices).
    tracked: list[int] = []
    for b in bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is not None:
            tracked.append(int(desc.avbd_body.index))
    rs.probe_body_indices = list(tracked)

    if solver not in ("avbd", "native", "xpbd", "impulse"):
        raise ValueError(f"unknown solver {solver!r} (avbd | xpbd | impulse)")
    # Native dynamic two-way modal constraint (two_band_coupling.html): q is a
    # solver DOF, NO coupler. The World's solver_kind ("xpbd"|"avbd") routes this
    # native wiring to SolverXPBD or SolverAVBD; deformable cargo (M2) joins via
    # add_native_cargo.
    world.enable_reduced_modal_support(
        rs, tracked_body_indices=tracked,
        shelf_length=table_length, shelf_width=table_width,
        shelf_y_rest=table_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)

    cargo_cube = None
    cargo_avbd_idx = None
    cargo_map: dict = {}
    if cargo_material is not None and cargo_all:
        # §N2 all-cargo: every place setting, candle, and the pot carry their
        # own box-shaped modal blocks on the box-box network (plates are thin
        # slabs, forks/knives thin bars — real shapes, not min-extent cubes).
        cargo_map = register_all_cargo(world, bodies, cargo_material,
                                       impactor_dcr=pot_idx,
                                       n_elastic=cargo_n_elastic)
        if pot_idx in cargo_map:
            cargo_cube, cargo_avbd_idx = cargo_map[pot_idx]
    elif cargo_material is not None:
        cargo_avbd_idx = int(world._descs[pot_idx].avbd_body.index)
        size = 2.0 * float(min(pot_h))
        cargo_cube = make_cargo_cube(cargo_material, size=size,
                                     mass=float(pot_mass))
        world.add_native_cargo(cargo_avbd_idx, cargo_cube)

    return DinnerSceneHandle(
        world=world, rs=rs,
        impactor_idx=pot_idx, probe_indices=plate_indices,
        bodies=bodies,
        cargo_cube=cargo_cube, cargo_avbd_idx=cargo_avbd_idx,
        cargo_material=cargo_material, cargo_map=cargo_map,
        name="Reduced-Coordinate AVBD Dinner Table",
    )
