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
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube, build_fem_cube
from dcr.avbd.cargo.abd import build_abd_cube
from dcr.fem.material import Material

from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


def make_cargo_cube(kind: str, *, size: float, mass: float, nx: int = 3,
                    n_elastic: int = 6, youngs: float = 1.0e6,
                    density: float = 600.0):
    """Build a deformable cargo cube body of the requested material, scaled to
    `size` (edge length) — the modal-overlay body the coupler couples at its
    contact corners (`reduced_coupled_avbd` / `reduced_coupled_xpbd`). The cube's
    own FEM density is rescaled so its total mass matches the scene impactor."""
    # density ∝ mass / size³ so build_*_cube's total_mass() ≈ the impactor mass.
    rho = max(1.0, float(mass) / max(size ** 3, 1e-9))
    if kind == "fem_rigid":
        return build_fem_rigid_cube(size=size, nx=nx, n_elastic=n_elastic,
                                    material=Material(E=youngs, nu=0.3, rho=rho),
                                    drop_y=0.0)
    if kind == "fem":
        return build_fem_cube(size=size, nx=nx, n_elastic=n_elastic,
                              material=Material(E=youngs, nu=0.3, rho=rho),
                              drop_y=0.0)
    if kind == "abd":
        return build_abd_cube(size=size, nx=nx, kappa_v=2.0e3, alpha0=2.0,
                              drop_y=0.0)
    raise ValueError(f"unknown cargo material {kind!r} (fem_rigid | abd | fem)")


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

    if solver == "xpbd":
        coupler = world.attach_reduced_coupled_xpbd(
            rs,
            tracked_body_indices=tracked,
            shelf_length=support_length,
            shelf_width=support_width,
            shelf_y_rest=support_top,
            n_grid_x=N_GRID_X,
            n_grid_z=N_GRID_Z,
        )
    elif solver == "avbd":
        coupler = world.attach_reduced_coupled_avbd(
            rs,
            tracked_body_indices=tracked,
            shelf_length=support_length,
            shelf_width=support_width,
            shelf_y_rest=support_top,
            n_grid_x=N_GRID_X,
            n_grid_z=N_GRID_Z,
            modal_static_lp_tau=modal_static_lp_tau,
        )
    else:
        raise ValueError(f"unknown solver {solver!r} (avbd | xpbd)")

    # Deformable cargo: make the impactor a modal/affine cube coupled at its
    # contact corners (Stage 7). The cube is sized to the impactor footprint and
    # its mass matched; the rigid box remains the collision proxy.
    if cargo_material is not None and cargo_impactor_dcr is not None:
        desc = world._descs[cargo_impactor_dcr]
        avbd_idx = int(desc.avbd_body.index)
        imp = next(b for b in bodies if b.dcr_idx == cargo_impactor_dcr)
        size = 2.0 * float(min(imp.half_extents))     # cube within the box
        mass = float(desc.dcr_body.mass)
        cube = make_cargo_cube(cargo_material, size=size, mass=mass,
                               n_elastic=cargo_n_elastic)
        coupler.add_cargo(avbd_idx, cube)
        coupler._scene_cargo_cube = cube              # read back by the scene
        coupler._scene_cargo_avbd_idx = avbd_idx
    return rs
