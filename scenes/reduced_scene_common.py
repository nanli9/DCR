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

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import (
    ReducedSupport,
    make_debug_reduced_shelf_support,
)

from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


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
) -> ReducedSupport:
    """Build the synthetic reduced-modal support, track every dynamic body,
    and attach the coupled AVBD coupler. Returns the `ReducedSupport`.

    This is exactly the dinner builder's support block (synthetic basis +
    DCR→AVBD index map + `attach_reduced_coupled_avbd`) shared verbatim.
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

    world.attach_reduced_coupled_avbd(
        rs,
        tracked_body_indices=tracked,
        shelf_length=support_length,
        shelf_width=support_width,
        shelf_y_rest=support_top,
        n_grid_x=N_GRID_X,
        n_grid_z=N_GRID_Z,
        modal_static_lp_tau=modal_static_lp_tau,
    )
    return rs
