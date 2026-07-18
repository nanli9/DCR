"""Shared scaffolding for the reduced-modal demo scenes.

The dinner-table scene (`scenes/reduced_dinner_table.py`) was the first
scene driven by `ReducedCoupledAVBDCoupler` (the q_s + q_d coupled path).
The truck / shelf / ledge scenes reuse that exact recipe — a flat AVBD
floor standing in for the deformable support's top surface, rigid bodies
resting on it, and a synthetic reduced-modal basis with local compliance
bumps under every contact — so this module factors out the parts they
share:

  * `ReducedSceneBody`   — per-body render metadata (mirrors the dinner
    scene's `DinnerBody`: the box half_extents ARE the collision proxy;
    `render_kind` only swaps the decorated `model/<kind>/` template).
  * `ReducedSceneHandle` — field-compatible with `DinnerSceneHandle` so
    the shared viser viewer drives every scene uniformly.
  * `build_support_and_attach` — make the synthetic basis + map DCR body
    indices to AVBD-side indices + attach the coupled coupler.

No physics deviates from the dinner recipe; this is pure de-duplication.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import (
    ReducedSupport,
    make_debug_reduced_shelf_support,
)
from dcr.avbd.cargo.fem_rigid import (
    build_fem_rigid_box,
    build_fem_box,
    build_rigid_box,
)
from dcr.avbd.cargo.abd import build_abd_box
from dcr.fem.material import Material

from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


def make_cargo_body(kind: str, *, half_extents, mass: float,
                    resolution: int | tuple[int, int, int] = 3,
                    n_elastic: int = 6, youngs: float = 1.0e6,
                    density: float = 600.0):
    """Build a deformable cargo body of the requested material shaped as the
    (hx,hy,hz) BOX of the rigid body it overlays — the modal body the native
    path couples at its contact corners (`add_native_cargo`). The FEM density
    is rescaled so the cargo's total mass matches the rigid body's."""
    hx, hy, hz = (float(v) for v in half_extents)
    vol = 8.0 * hx * hy * hz
    rho = max(1.0, float(mass) / max(vol, 1e-12))
    mat = Material(E=youngs, nu=0.3, rho=rho)
    if kind == "rigid":
        # Pure 6-DOF rigid body (k=0): the no-deformation baseline. It still
        # rings the support's modal field through its contact corners (M1).
        return build_rigid_box(half_extents=(hx, hy, hz),
                               resolution=resolution, material=mat, drop_y=0.0)
    if kind == "fem_rigid":
        return build_fem_rigid_box((hx, hy, hz), resolution=resolution,
                                   n_elastic=n_elastic, material=mat,
                                   drop_y=0.0)
    if kind == "fem":
        return build_fem_box(half_extents=(hx, hy, hz), resolution=resolution,
                             n_elastic=n_elastic, material=mat, drop_y=0.0)
    if kind == "abd":
        return build_abd_box((hx, hy, hz), resolution=resolution,
                             kappa_v=2.0e3, alpha0=2.0, drop_y=0.0)
    raise ValueError(
        f"unknown cargo material {kind!r} (rigid | fem_rigid | abd | fem)")


def make_cargo_cube(kind: str, *, size: float, mass: float, nx: int = 3,
                    n_elastic: int = 6, youngs: float = 1.0e6,
                    density: float = 600.0):
    """Cube-shaped cargo body (edge `size`) — exact-equivalence wrapper over
    `make_cargo_body` (kept for the legacy single-impactor call sites)."""
    return make_cargo_body(kind, half_extents=(0.5 * size,) * 3, mass=mass,
                           resolution=(nx, nx, nx), n_elastic=n_elastic,
                           youngs=youngs, density=density)


def register_all_cargo(
    world: AVBDDCRWorld,
    bodies,
    cargo_material: str,
    *,
    impactor_dcr: int | None = None,
    n_elastic: int = 3,
    youngs: float = 1.0e6,
) -> dict[int, tuple[object, int]]:
    """§N2 generalization (all-cargo scenes): register EVERY body as a
    box-shaped deformable cargo on the native augmented-modal path and enable
    the box-box modal contact network — the `reduced_cargo_network` recipe
    applied to the production scenes, with each body's REAL (hx,hy,hz) modal
    shapes instead of a min-extent cube collapse.

    Call AFTER `enable_reduced_modal_support`. `allow_stacked=True` for every
    body: grounded bodies still bind their support rows (the flag only waives
    the no-support-rows error), while stacked bodies (lumber piles) couple
    purely through the box-box network. Returns {dcr_idx: (cargo_body,
    avbd_idx)}. On XPBD the per-body support coupling works but the box-box
    network does not exist yet (N5) — stacked bodies' modes stay inert there.
    """
    cargo_map: dict[int, tuple[object, int]] = {}
    for b in bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is None:
            continue
        avbd_idx = int(desc.avbd_body.index)
        body = make_cargo_body(
            cargo_material, half_extents=b.half_extents,
            mass=float(desc.dcr_body.mass), n_elastic=n_elastic,
            youngs=youngs)
        world.add_native_cargo(avbd_idx, body, allow_stacked=True)
        cargo_map[b.dcr_idx] = (body, avbd_idx)
    if hasattr(world._solver, "_modal_contact_network"):
        world._solver._modal_contact_network = True
    return cargo_map


@dataclass
class ReducedSceneBody:
    """Per-body render metadata for the viewer. The box `half_extents` are
    the collision proxy the AVBD solver actually sees; `render_kind` only
    selects the decorated template in `model/<kind>/` at draw time."""
    name: str
    dcr_idx: int
    half_extents: tuple[float, float, float]
    color: tuple[float, float, float]
    render_kind: str = "box"
    orientation_wxyz: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)


@dataclass
class ReducedSceneHandle:
    """Everything the viewer needs to drive + observe a reduced-modal scene.

    Field-compatible with `reduced_dinner_table.DinnerSceneHandle`
    (`.world`, `.rs`, `.impactor_idx`, `.probe_indices`, `.bodies`,
    `.name`) so one viewer serves every scene. `.impactor_label` lets the
    GUI name the primary dropped object ("pot" / "boulder" / "crate" …)."""
    world: AVBDDCRWorld
    rs: ReducedSupport
    impactor_idx: int
    probe_indices: list[int]
    bodies: list[ReducedSceneBody] = field(default_factory=list)
    name: str = "Reduced-Coordinate AVBD Scene"
    impactor_label: str = "impactor"
    # Deformable-cargo wiring (Stage 7): set when the impactor is a deformable
    # material (fem_rigid/abd/fem) coupled via `coupler.add_cargo`. None ⇒ the
    # impactor is a plain rigid body (the default / legacy behavior).
    cargo_cube: object = None              # FEMRigidModalBody | ABDAffineBody
    cargo_avbd_idx: int | None = None
    cargo_material: str | None = None
    # All-cargo wiring (§N2 generalization): {dcr_idx: (cargo_body, avbd_idx)}
    # for EVERY body when the scene was built with cargo_all=True; empty dict
    # otherwise. The impactor's entry is duplicated in cargo_cube/_avbd_idx.
    cargo_map: dict = field(default_factory=dict)


class BodyAdder:
    """Tiny helper bound to a world + body list: `add(...)` registers a box
    in the AVBD world AND appends its `ReducedSceneBody` render metadata,
    returning the DCR index (mirrors the dinner builder's `_add`)."""

    def __init__(self, world: AVBDDCRWorld, bodies: list[ReducedSceneBody]):
        self.world = world
        self.bodies = bodies

    def add(self, name, mass, half, pos, color, kind,
            quat=(1.0, 0.0, 0.0, 0.0), friction=0.4, vel=(0.0, 0.0, 0.0)) -> int:
        idx = self.world.add_box(
            mass=mass, half_extents=half, position=pos,
            orientation_wxyz=quat, velocity_lin=vel, friction=friction,
            name=name,
        )
        self.bodies.append(ReducedSceneBody(
            name=name, dcr_idx=idx, half_extents=half,
            color=color, render_kind=kind, orientation_wxyz=quat))
        return idx


def build_support_and_attach(
    world: AVBDDCRWorld,
    bodies: list[ReducedSceneBody],
    *,
    support_length: float,
    support_width: float,
    support_thickness: float,
    support_top: float,
    youngs: float,
    density: float,
    poisson: float,
    n_modes_global: int,
    n_modes_local: int,
    contact_zones: list[tuple[float, float]],
    probe_xz: list[tuple[float, float]],
    rayleigh_alpha0: float,
    rayleigh_alpha1: float,
    modal_impedance_scale: float,
    modal_damping_scale: float,
    to_eigenbasis: bool,
    modal_static_lp_tau: float,
    solver: str = "avbd",
    cargo_material: str | None = None,
    cargo_impactor_dcr: int | None = None,
    cargo_n_elastic: int = 6,
    cargo_all: bool = False,
) -> ReducedSupport:
    """Build the synthetic reduced-modal support, track every dynamic body,
    and attach the coupled coupler (`solver` = "avbd" Schur–Newton | "xpbd"
    compliant Gauss–Seidel, Stage 6). Returns the `ReducedSupport`.

    When `cargo_material` is set, the impactor (`cargo_impactor_dcr`) is made a
    deformable cargo cube of that material (fem_rigid/abd/fem), coupled at its
    contact corners through the same dynamic modal block as the support
    (`coupler.add_cargo`); the cube is sized to the impactor's footprint and its
    mass matched. The rigid box stays the SAT collision proxy. `None` ⇒ the
    impactor is plain rigid (legacy). The built cube + its AVBD index are stashed
    on `world.reduced_coupled_coupler` (read back by the scene for the handle).
    """
    # The basis builder places one Gaussian bump (local compliance mode) per
    # contact zone. If asked for MORE local modes than distinct zones it pads
    # with extra bumps that coincide with existing ones, which makes the
    # reduced mass matrix Mq singular and breaks the eigenbasis projection
    # (`leading minor of B is not positive definite`). So dedup coincident
    # zones (within half the bump sigma ≈ 0.015 m) and clamp the local-mode
    # count to the distinct-zone count: exactly one bump per distinct contact.
    _tol = 0.015

    def _dedup(zones):
        out: list[tuple[float, float]] = []
        for z in zones:
            if all((z[0] - o[0]) ** 2 + (z[1] - o[1]) ** 2 > _tol * _tol
                   for o in out):
                out.append((float(z[0]), float(z[1])))
        return out

    distinct_zones = _dedup(contact_zones)
    n_modes_local = min(int(n_modes_local), len(distinct_zones))

    rs = make_debug_reduced_shelf_support(
        length=support_length, width=support_width, thickness=support_thickness,
        youngs=youngs, density=density, poisson=poisson,
        n_modes_global=n_modes_global, n_modes_local=n_modes_local,
        contact_zone_centers=distinct_zones,
        probe_xz=probe_xz,
        y_rest=support_top,
        overlay_enabled=False, restart_overlay_each_step=False,
        rayleigh_alpha0=rayleigh_alpha0, rayleigh_alpha1=rayleigh_alpha1,
        modal_impedance_scale=modal_impedance_scale,
        modal_damping_scale=modal_damping_scale,
        to_eigenbasis=to_eigenbasis,
    )

    # The coupler tracks AVBD-side body indices; map them from DCR indices.
    tracked: list[int] = []
    for b in bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is not None:
            tracked.append(int(desc.avbd_body.index))
    rs.probe_body_indices = list(tracked)

    if solver in ("avbd", "native", "xpbd", "impulse"):
        # Native dynamic two-way modal constraint (two_band_coupling.html,
        # Approach B): q is a solver DOF, NO coupler. Deformable cargo (M2) joins
        # the augmented modal vector via add_native_cargo (fem_rigid/fem/abd).
        # The World was created with solver_kind = "xpbd"|"avbd", so this same
        # native wiring drives SolverXPBD or SolverAVBD (Stage 5).
        #
        # Repoints (native dual-solver plan): solver="avbd" and solver="xpbd"
        # both select the NATIVE solver of that kind. The external reduced
        # couplers are reachable as "avbd_coupler" / "xpbd_coupler"
        # (transitional; deleted in Stage 6). "native" is a back-compat alias.
        world.enable_reduced_modal_support(
            rs,
            tracked_body_indices=tracked,
            shelf_length=support_length,
            shelf_width=support_width,
            shelf_y_rest=support_top,
            n_grid_x=N_GRID_X,
            n_grid_z=N_GRID_Z,
        )
        if cargo_material is not None and cargo_all:
            # §N2 all-cargo: every body a box-shaped modal cargo on the
            # box-box network (the cargo-network recipe, production scenes).
            cargo_map = register_all_cargo(
                world, bodies, cargo_material,
                impactor_dcr=cargo_impactor_dcr, n_elastic=cargo_n_elastic)
            rs._native_cargo_map = cargo_map       # read back by the scene
            if cargo_impactor_dcr in cargo_map:
                cube, avbd_idx = cargo_map[cargo_impactor_dcr]
                rs._native_cargo_cube = cube
                rs._native_cargo_avbd_idx = avbd_idx
        elif cargo_material is not None and cargo_impactor_dcr is not None:
            desc = world._descs[cargo_impactor_dcr]
            avbd_idx = int(desc.avbd_body.index)
            imp = next(b for b in bodies if b.dcr_idx == cargo_impactor_dcr)
            size = 2.0 * float(min(imp.half_extents))
            mass = float(desc.dcr_body.mass)
            cube = make_cargo_cube(cargo_material, size=size, mass=mass,
                                   n_elastic=cargo_n_elastic)
            world.add_native_cargo(avbd_idx, cube)
            rs._native_cargo_cube = cube           # read back by the scene
            rs._native_cargo_avbd_idx = avbd_idx
        return rs
    raise ValueError(f"unknown solver {solver!r} (avbd | xpbd | impulse)")
