"""Reduced-Coordinate AVBD Support Contact — minimal shelf scene (v1).

Drops one rigid impactor box onto the center of a synthetic deformable
shelf. Two small "probe" boxes rest at distant points on the shelf so
the bare-vs-overlay comparison (Section 20.1 of
`prompts/reduced_coordinate_avbd_support_dcr_extension.md`) can be read
directly off probe kinematics.

The shelf itself is a flat AVBD floor at y = `shelf_y_rest`. The
reduced support is a Python-side object whose coordinates q deform a
*virtual* surface offset (anchor-shift trick — see
`dcr/avbd/reduced_support_solve.py`); the AVBD-side floor at y=0 is
what catches the rigid bodies for non-penetration, and the deformation
is applied per-row inside the AVBD substep loop.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import (
    ReducedSupport,
    make_debug_reduced_shelf_support,
)


# Grid resolution defaults — must match the values inside
# `make_synthetic_modal_basis_for_shelf` so the coupler's bilinear
# evaluator can find the right cells.
N_GRID_X = 21
N_GRID_Z = 11


@dataclass
class ShelfSceneHandle:
    """Bundle the caller needs to drive and observe the scene."""
    world: AVBDDCRWorld
    rs: ReducedSupport
    impactor_idx: int
    probe_indices: list[int]
    name: str


def build_reduced_support_shelf(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 4,
    avbd_substeps: int = 1,
    shelf_length: float = 0.30,
    shelf_width: float = 0.15,
    shelf_thickness: float = 0.005,
    shelf_y_rest: float = 0.0,
    youngs: float = 2.0e11,
    density: float = 7850.0,
    poisson: float = 0.30,
    n_modes_global: int = 8,
    n_modes_local: int = 8,
    impactor_drop_height: float = 0.30,
    impactor_mass: float = 0.50,
    impactor_half_extent: float = 0.02,
    impactor_v0: tuple[float, float, float] = (0.0, -1.0, 0.0),
    probe_mass: float = 0.005,
    probe_half_extent: float = 0.0075,
    probe_xz: list[tuple[float, float]] | None = None,
    overlay_enabled: bool = True,
    restart_overlay_each_step: bool = True,
    reduced_support_enabled: bool = True,
    reduced_static_support: bool = False,
    coupled_avbd: bool = False,
    dcr_postkick: bool = False,
    rayleigh_alpha0: float = 0.0,
    rayleigh_alpha1: float = 5.0e-6,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    modal_energy_cap_fraction: float | None = None,
    modal_jump_gain: float = 1.0,
    modal_jump_max_height: float = 0.01,
) -> ShelfSceneHandle:
    """Construct the shelf scene + attach (or not) the reduced support.

    `reduced_support_enabled=False` builds the scene without wiring the
    coupler — useful for an apples-to-apples baseline against the
    existing rigid-only AVBD path. The shelf-as-floor AVBD path is
    identical in both cases.

    `reduced_static_support=True` attaches the coupler in static-sag
    mode: the q-block solve still runs every AVBD iteration and the
    rigid contacts see the deformed support geometry, but the legacy
    transient overlay path (high-pass r_tilde, two-rate IIR, probe Δv
    injection, F_n cap, cooldown, energy cap) is bypassed entirely.
    Implies `overlay_enabled=False`. This is the cleaned secondary
    extension described in the static-sag refactor — it does NOT model
    distant transient response.
    """
    if reduced_static_support:
        overlay_enabled = False
        restart_overlay_each_step = False
    if coupled_avbd:
        overlay_enabled = False
        restart_overlay_each_step = False
    if coupled_avbd and reduced_static_support:
        raise ValueError(
            "coupled_avbd and reduced_static_support are mutually exclusive")
    if probe_xz is None:
        probe_xz = [
            (-0.40 * shelf_length, 0.0),
            (+0.40 * shelf_length, 0.0),
        ]

    world = AVBDDCRWorld(
        h=h,
        device=device,
        avbd_iterations=iterations,
        avbd_substeps=int(avbd_substeps),
    )

    # Shelf-as-floor. AVBD's floor is +y up; bodies sitting on it
    # contact at y = shelf_y_rest.
    world.add_floor(floor_y=shelf_y_rest, friction=0.30, name="shelf_floor")

    # Probes first so we know their AVBD indices when wiring the
    # reduced support.
    probe_indices: list[int] = []
    for (xp, zp) in probe_xz:
        # Park the probe so its bottom corner sits exactly at the shelf.
        py = shelf_y_rest + probe_half_extent + 1e-4
        idx = world.add_box(
            mass=probe_mass,
            half_extents=(probe_half_extent,) * 3,
            position=(float(xp), float(py), float(zp)),
            velocity_lin=(0.0, 0.0, 0.0),
            friction=0.30,
            name=f"probe_{len(probe_indices)}",
        )
        probe_indices.append(idx)

    # Impactor — drops from height onto the shelf center.
    impactor_idx = world.add_box(
        mass=impactor_mass,
        half_extents=(impactor_half_extent,) * 3,
        position=(0.0, shelf_y_rest + impactor_drop_height, 0.0),
        velocity_lin=tuple(float(v) for v in impactor_v0),
        friction=0.30,
        name="impactor",
    )

    # Reduced support data (synthetic basis). Contact zones include
    # the impactor center + the two probe centers so the local
    # Gaussian-bump modes give the q-block real compliance to project
    # onto.
    contact_zones = [(0.0, 0.0)] + list(probe_xz)
    rs = make_debug_reduced_shelf_support(
        length=shelf_length,
        width=shelf_width,
        thickness=shelf_thickness,
        youngs=youngs,
        density=density,
        poisson=poisson,
        n_modes_global=n_modes_global,
        n_modes_local=n_modes_local,
        contact_zone_centers=contact_zones,
        probe_xz=probe_xz,
        y_rest=shelf_y_rest,
        overlay_enabled=overlay_enabled,
        restart_overlay_each_step=restart_overlay_each_step,
        rayleigh_alpha0=rayleigh_alpha0,
        rayleigh_alpha1=rayleigh_alpha1,
        modal_impedance_scale=modal_impedance_scale,
        modal_damping_scale=modal_damping_scale,
    )

    # AVBDDCRWorld assigns a static "floor" body at DCR index 0 ahead
    # of dynamic bodies; the AVBD-side indexing skips the floor. The
    # value returned by add_box above (and stored in probe_indices /
    # impactor_idx) is the DCR-side index. For the coupler we need
    # AVBD-side indices (which is what solver.c_body_a stores). Look
    # them up via the descriptor list.
    avbd_probe_indices: list[int] = []
    for dcr_idx in probe_indices:
        desc = world._descs[dcr_idx]
        if desc.avbd_body is not None:
            avbd_probe_indices.append(int(desc.avbd_body.index))
        else:
            avbd_probe_indices.append(-1)
    avbd_impactor_idx = (
        int(world._descs[impactor_idx].avbd_body.index)
        if world._descs[impactor_idx].avbd_body is not None
        else -1)
    rs.probe_body_indices = list(avbd_probe_indices)

    if reduced_support_enabled:
        tracked_bodies = [b for b in avbd_probe_indices if b >= 0]
        if avbd_impactor_idx >= 0:
            tracked_bodies.append(avbd_impactor_idx)
        if dcr_postkick:
            # Legacy --mode old_dcr_postkick: rigid-floor AVBD + Δv kick.
            # No reduced-coupled coupler attached; the support exists
            # only so the modal basis is available for the post-step
            # IIR + d_max sampling. AVBD treats the floor as rigid.
            world.attach_reduced_dcr_postkick(
                rs,
                tracked_body_indices=tracked_bodies,
                shelf_length=shelf_length,
                shelf_width=shelf_width,
                shelf_y_rest=shelf_y_rest,
                n_grid_x=N_GRID_X,
                n_grid_z=N_GRID_Z,
            )
        elif coupled_avbd:
            world.attach_reduced_coupled_avbd(
                rs,
                tracked_body_indices=tracked_bodies,
                shelf_length=shelf_length,
                shelf_width=shelf_width,
                shelf_y_rest=shelf_y_rest,
                n_grid_x=N_GRID_X,
                n_grid_z=N_GRID_Z,
            )
            if (modal_energy_cap_fraction is not None
                    and world.reduced_coupled_coupler is not None):
                world.reduced_coupled_coupler.modal_energy_cap_fraction = (
                    float(modal_energy_cap_fraction))
            if world.reduced_coupled_coupler is not None:
                world.reduced_coupled_coupler.modal_jump_gain = (
                    float(modal_jump_gain))
                world.reduced_coupled_coupler.modal_jump_max_height = (
                    float(modal_jump_max_height))
        else:
            world.attach_reduced_support(
                rs,
                tracked_body_indices=tracked_bodies,
                shelf_length=shelf_length,
                shelf_width=shelf_width,
                shelf_y_rest=shelf_y_rest,
                n_grid_x=N_GRID_X,
                n_grid_z=N_GRID_Z,
                static_only=reduced_static_support,
            )

    return ShelfSceneHandle(
        world=world,
        rs=rs,
        impactor_idx=impactor_idx,
        probe_indices=probe_indices,
        name="Reduced-Coordinate AVBD Shelf (v1)",
    )
