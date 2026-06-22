"""Dinner-table scene driven by the Reduced-Coordinate AVBD coupler.

This is the DCR Fig. 1 "dinner is served" layout — four place settings
(plate + fork + knife), four candles, and a heavy pot dropped on the
center — but with the **table itself as the reduced-modal deformable
support** (`ReducedCoupledAVBDCoupler`, the q_s + q_d coupled path), NOT
the patch `PassiveDCRCoupler`. The pot's impact rings the table's modal
field; the coupling rocks the nearby place settings through the deformed
support geometry inside the AVBD iteration (cross-block ρ·J_x·J_q^T).

Layout / masses / proportions are copied verbatim from the AVBD-branch
`build_dinner_table_scene` so the visual is identical; only the support
physics differ (reduced-modal coupled solve instead of patch DCR).

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
from scenes.reduced_scene_common import make_cargo_cube


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


def build_reduced_dinner_table(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 6,
    avbd_substeps: int = 2,
    # Table = the reduced-modal support. 1.2 m × 1.0 m, hardwood-ish.
    table_length: float = 1.2,
    table_width: float = 1.0,
    table_thickness: float = 0.03,
    table_top: float = 0.03,
    youngs: float = 1.0e10,
    density: float = 500.0,
    poisson: float = 0.30,
    n_modes_global: int = 10,
    n_modes_local: int = 14,
    pot_drop_height: float = 0.5,
    pot_mass: float = 8.0,
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
) -> DinnerSceneHandle:
    """Construct the dinner-table scene + attach the reduced-coupled AVBD
    support (the table). Returns a handle carrying per-body render
    metadata for the decorated viewer."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
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

    # ---- Four place settings (plate flanked by fork / knife) ----
    plate_h = (0.085, 0.010, 0.085)
    plate_palette = [
        (0.95, 0.92, 0.85), (0.85, 0.65, 0.55),
        (0.55, 0.70, 0.85), (0.80, 0.80, 0.70),
    ]
    plate_spots = [(-0.32, -0.28), (-0.32, 0.28), (0.32, -0.28), (0.32, 0.28)]
    fork_h = (0.10, util_half_y, 0.012)
    knife_h = (0.10, util_half_y, 0.013)
    util_color = (0.78, 0.80, 0.85)
    util_offset = 0.13
    util_q = (0.70710678, 0.0, 0.70710678, 0.0)  # 90° about +Y

    plate_indices: list[int] = []
    resting_xz: list[tuple[float, float]] = []
    for pi, (px, pz) in enumerate(plate_spots):
        pidx = _add(f"plate_{pi}", 0.4, plate_h,
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

    # ---- Four candles near the table edges ----
    candle_h = (0.015, 0.045, 0.015)
    candle_palette = [
        (0.94, 0.88, 0.74), (0.78, 0.20, 0.18),
        (0.92, 0.86, 0.50), (0.30, 0.45, 0.55),
    ]
    candle_spots = [(-0.50, -0.45), (-0.50, 0.45), (0.50, -0.45), (0.50, 0.45)]
    for ci, (cx, cz) in enumerate(candle_spots):
        _add(f"candle_{ci}", 0.18, candle_h,
             (cx, table_top + candle_h[1] + 0.001, cz),
             candle_palette[ci % 4], "candle", friction=0.45)
        resting_xz.append((cx, cz))

    # ---- The pot: heavy, drops on center ----
    pot_h = (0.13, 0.065, 0.082)
    pot_idx = _add("pot", pot_mass, pot_h,
                   (0.0, table_top + pot_h[1] + pot_drop_height, 0.0),
                   (0.20, 0.18, 0.16), "pot", friction=0.5,
                   vel=(0.0, float(pot_v0_y), 0.0))

    # ---- Reduced-modal support (synthetic basis). Bump modes are placed
    # at the pot impact (center) + every resting object so the q-block has
    # local compliance where the contact happens. ----
    contact_zones = [(0.0, 0.0)] + resting_xz
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

    # DCR idx → AVBD idx (the coupler tracks AVBD-side indices).
    tracked: list[int] = []
    for b in bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is not None:
            tracked.append(int(desc.avbd_body.index))
    rs.probe_body_indices = list(tracked)

    coupler = None
    if solver in ("avbd", "native"):
        # Native dynamic two-way modal constraint (two_band_coupling.html): q is
        # a solver DOF, NO coupler. Deformable cargo (M2) joins the augmented
        # modal vector via add_native_cargo (fem_rigid/fem/abd). Stage-1 repoint:
        # solver="avbd" is the native AVBD path; the AVBD coupler is
        # "avbd_coupler" (transitional, deleted Stage 6); "native" is a back-
        # compat alias dropped in Stage 5.
        world.enable_reduced_modal_support(
            rs, tracked_body_indices=tracked,
            shelf_length=table_length, shelf_width=table_width,
            shelf_y_rest=table_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
    elif solver == "xpbd":
        coupler = world.attach_reduced_coupled_xpbd(
            rs, tracked_body_indices=tracked,
            shelf_length=table_length, shelf_width=table_width,
            shelf_y_rest=table_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
    elif solver == "avbd_coupler":
        coupler = world.attach_reduced_coupled_avbd(
            rs, tracked_body_indices=tracked,
            shelf_length=table_length, shelf_width=table_width,
            shelf_y_rest=table_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
            modal_static_lp_tau=modal_static_lp_tau)
    else:
        raise ValueError(
            f"unknown solver {solver!r} (avbd | xpbd | avbd_coupler)")

    cargo_cube = None
    cargo_avbd_idx = None
    if cargo_material is not None:
        cargo_avbd_idx = int(world._descs[pot_idx].avbd_body.index)
        size = 2.0 * float(min(pot_h))
        cargo_cube = make_cargo_cube(cargo_material, size=size,
                                     mass=float(pot_mass))
        if coupler is None:                       # native path (no coupler)
            world.add_native_cargo(cargo_avbd_idx, cargo_cube)
        else:
            coupler.add_cargo(cargo_avbd_idx, cargo_cube)

    return DinnerSceneHandle(
        world=world, rs=rs,
        impactor_idx=pot_idx, probe_indices=plate_indices,
        bodies=bodies,
        cargo_cube=cargo_cube, cargo_avbd_idx=cargo_avbd_idx,
        cargo_material=cargo_material,
        name="Reduced-Coordinate AVBD Dinner Table",
    )
