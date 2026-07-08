"""Modal contact network demo scene (§N2): every object is a deformable cargo
cube carrying its own reduced modes, and a STACKED cube feels the ring of the
cube under it through the box-box modal network.

Layout (looking down the +x axis, slab in the xz-plane at y = support_top):

                              [upper]      ← layer 3 (offset back over base)
        impactor↓          [mid]           ← layer 2 (offset off base)
    resting                   [base]       ← layer 1 (on slab)
      [L]      [I]        [B stack]
    ───────────────────────────────  slab (reduced modal support)
     -0.28     0.0        +0.26

- `resting` (left): a cargo cube resting on the slab — the CONTROL. It rings only
  from the slab (support contact), exactly the pre-existing behaviour.
- `impactor` (middle): a cargo cube dropped onto the slab — excites the slab ring.
- `base` / `mid` / `upper` (right): a THREE-high zig-zag stack. `base` rests on
  the slab; `mid` and `upper` touch ONLY the cube below them (box-box). With the
  network ON, `mid` rings because `base` rings, and `upper` rings because `mid`
  rings — the ring climbs the tower through two box-box hops. With the network
  OFF, `mid` and `upper` stay dead.

The three slab-resting cubes are native support cargo; `mid` and `upper` are
`allow_stacked` cargo coupled only through the box-box network. Toggle `network=`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import make_debug_reduced_shelf_support
from dcr.avbd.cargo.fem_rigid import (
    build_fem_rigid_cube, build_fem_cube, build_rigid_cube)
from dcr.avbd.cargo.abd import build_abd_cube
from dcr.fem.material import Material
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


@dataclass
class CargoNetworkHandle:
    world: AVBDDCRWorld
    rs: object
    cubes: dict = field(default_factory=dict)     # name -> cargo body model
    avbd_idx: dict = field(default_factory=dict)  # name -> avbd body index
    support_top: float = 0.0
    support_length: float = 0.8
    support_width: float = 0.4
    network: bool = True
    kind: str = "fem_rigid"


def _cube(kind, size, E, rho, n_elastic):
    """Build a cargo cube of the requested material (rigid | fem_rigid | fem |
    abd) — the same dropdown as the single-cube cargo scene. Only cubes with
    elastic modes (k>0) participate in the modal network; a "rigid" cube (k=0)
    couples nothing (no modal column)."""
    if kind == "abd":
        return build_abd_cube(size=size, nx=3, kappa_v=2.0e3, alpha0=1.0,
                              drop_y=0.0)
    if kind == "rigid":
        return build_rigid_cube(size=size, nx=3, drop_y=0.0,
                                material=Material(E=E, nu=0.3, rho=rho))
    builder = {"fem_rigid": build_fem_rigid_cube, "fem": build_fem_cube}[kind]
    return builder(size=size, nx=3, n_elastic=n_elastic, drop_y=0.0,
                   material=Material(E=E, nu=0.3, rho=rho))


def build_cargo_network_scene(
    *,
    network: bool = True,
    ride: bool = False,             # §N2 rigid-ride: lower cube's flex lifts the
                                    # upper's RIGID body (needs friction; N3 gate)
    kind: str = "fem_rigid",        # cube material (rigid | fem_rigid | fem | abd)
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 12,
    substeps: int = 4,
    support_length: float = 0.8,
    support_width: float = 0.4,
    support_thickness: float = 0.02,
    support_top: float = 0.0,
    support_youngs: float = 1.0e10,
    support_density: float = 500.0,
    cube_size: float = 0.1,
    cube_youngs: float = 1.2e5,     # soft ⇒ visible flex
    cube_density: float = 600.0,
    n_elastic: int = 3,
    impactor_drop: float = 0.22,    # drop height above resting → strong ring
    stack_offset: float = 0.035,    # upper cube x-offset (not corner-aligned)
    device_resident: bool | None = None,
    solver: str = "avbd",
    friction: float = 0.4,          # μ on floor + cubes (E6 friction sweep knob)
) -> CargoNetworkHandle:
    half = 0.5 * cube_size
    world = AVBDDCRWorld(
        h=h, device=device, avbd_iterations=int(iterations),
        avbd_substeps=int(substeps),
        solver_kind="xpbd" if solver == "xpbd" else "avbd")
    if device_resident is not None and solver != "xpbd":
        world._solver._modal_device_resident = bool(device_resident)
    world.add_floor(floor_y=support_top, friction=float(friction), name="support")

    # x positions of the four cubes.
    x_rest, x_imp, x_base = -0.28, 0.0, 0.26
    y0 = support_top + half                       # a cube resting on the slab

    cubes, idx = {}, {}

    def add_ground(name, cx, drop):
        cube = _cube(kind, cube_size, cube_youngs, cube_density, n_elastic)
        di = world.add_box(
            mass=float(cube.mass), half_extents=(half, half, half),
            position=(cx, y0 + drop, 0.0), friction=float(friction), name=name)
        cubes[name] = cube
        idx[name] = int(world._descs[di].avbd_body.index)

    add_ground("resting", x_rest, 0.0)
    add_ground("impactor", x_imp, impactor_drop)
    add_ground("base", x_base, 0.0)

    # Right stack: two more layers on `base` (box-box only) — cubes reached ONLY
    # through the modal network. Zig-zag offset (not corner-aligned) with the
    # tower COM over the base so it stays standing; every box-box joint is offset,
    # and the top cube feels the base's ring through TWO box-box hops.
    def add_stacked(name, cx, layer):
        cube = _cube(kind, cube_size, cube_youngs, cube_density, n_elastic)
        di = world.add_box(
            mass=float(cube.mass), half_extents=(half, half, half),
            position=(cx, y0 + layer * cube_size, 0.0), friction=float(friction), name=name)
        cubes[name] = cube
        idx[name] = int(world._descs[di].avbd_body.index)

    add_stacked("mid", x_base + stack_offset, 1)     # layer 2: offset off base
    add_stacked("upper", x_base, 2)                  # layer 3: offset back over base

    # Reduced modal slab with a contact zone under each ground cube.
    rs = make_debug_reduced_shelf_support(
        length=support_length, width=support_width, thickness=support_thickness,
        youngs=support_youngs, density=support_density, poisson=0.30,
        n_modes_global=8, n_modes_local=1,
        contact_zone_centers=[(x_rest, 0.0), (x_imp, 0.0), (x_base, 0.0)],
        probe_xz=[(x_rest, 0.0), (x_imp, 0.0), (x_base, 0.0)],
        y_rest=support_top, overlay_enabled=False,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, to_eigenbasis=True)

    # Native support for the three slab-resting cubes; the upper cube is a
    # stacked cargo coupled ONLY through the box-box modal network.
    tracked = [idx["resting"], idx["impactor"], idx["base"]]
    world.enable_reduced_modal_support(
        rs, tracked_body_indices=tracked,
        shelf_length=support_length, shelf_width=support_width,
        shelf_y_rest=support_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
    for name in ("resting", "impactor", "base"):
        world.add_native_cargo(idx[name], cubes[name])
    for name in ("mid", "upper"):
        world.add_native_cargo(idx[name], cubes[name], allow_stacked=True)

    world._solver._modal_contact_network = bool(network)
    world._solver._modal_contact_ride = bool(ride)   # §N2 rigid ride (N3)
    return CargoNetworkHandle(
        world=world, rs=rs, cubes=cubes, avbd_idx=idx,
        support_top=support_top, support_length=support_length,
        support_width=support_width, network=network, kind=kind)


def cube_state_world(handle: CargoNetworkHandle, name: str) -> np.ndarray:
    """Config z = [p(3), q(4 wxyz), a(k)] for cube `name`, for skinning."""
    s = handle.world._solver
    bi = handle.avbd_idx[name]
    p = s.positions()[bi].astype(np.float64)
    q_xyzw = s.orientations()[bi].astype(np.float64)
    q_wxyz = np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]])
    a = s.cargo_a(bi)
    z = np.zeros(7 + handle.cubes[name].k)
    z[0:3] = p
    z[3:7] = q_wxyz
    z[7:] = a
    return z
