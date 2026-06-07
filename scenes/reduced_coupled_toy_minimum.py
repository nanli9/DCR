"""Toy scene 1 for `--reduced-coupled-avbd`: one rigid box on a compliant
shelf, no probes, no impactors.

Used by tests/avbd/test_reduced_coupled_avbd.py to assert:
  - static settling: q reaches K_q⁻¹·F at rest.
  - no overlay invocation: cum_overlay_events_fired stays 0.
  - Schur conditioning stays bounded.
  - dq norm decreases inside the iteration loop.
  - hook is at its own fixed point (double-update consistency).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import (
    ReducedSupport, make_debug_reduced_shelf_support,
)
from dcr.avbd.reduced_coupled_avbd import ReducedCoupledAVBDCoupler


N_GRID_X = 21
N_GRID_Z = 11


@dataclass
class ToyHandle:
    world: AVBDDCRWorld
    rs: ReducedSupport
    coupler: ReducedCoupledAVBDCoupler
    box_idx: int
    name: str = "Reduced-Coupled-AVBD Toy Scene 1"


def build_toy_scene_1(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 8,
    avbd_substeps: int = 1,
    mass: float = 0.05,
    half_extent: float = 0.02,
    shelf_length: float = 0.30,
    shelf_width: float = 0.15,
    shelf_thickness: float = 0.005,
    shelf_y_rest: float = 0.0,
    youngs: float = 2.0e11,
    density: float = 7850.0,
    n_modes_global: int = 6,
    n_modes_local: int = 4,
    rho_clip: float = 1.0e9,
    rayleigh_alpha0: float = 0.0,
    rayleigh_alpha1: float = 5.0e-6,
    dynamic_q: bool = True,
) -> ToyHandle:
    """One box (`mass` kg) resting at center of the shelf, no probes.

    Parameters tuned so K_q⁻¹·F is in the 1–100 µm range — well above
    numerical noise and small enough to stay in linear regime.
    """
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=iterations,
        avbd_substeps=avbd_substeps,
    )
    world.add_floor(floor_y=shelf_y_rest, friction=0.30, name="shelf_floor")

    # One box resting at center. Half-extent + 1e-4 epsilon to avoid
    # numerical penetration at frame 0.
    py = shelf_y_rest + half_extent + 1e-4
    box_idx = world.add_box(
        mass=mass,
        half_extents=(half_extent, half_extent, half_extent),
        position=(0.0, float(py), 0.0),
        velocity_lin=(0.0, 0.0, 0.0),
        friction=0.30,
        name="resting_box",
    )

    # Reduced support — contact zone at center (where the box lands).
    # When dynamic_q is True, modal damping (Rayleigh α₀·M + α₁·K) makes
    # the shelf ring then decay; default α₁=1e-4 gives ~5-10 visible
    # cycles for steel-like parameters.
    rs = make_debug_reduced_shelf_support(
        length=shelf_length,
        width=shelf_width,
        thickness=shelf_thickness,
        youngs=youngs,
        density=density,
        n_modes_global=n_modes_global,
        n_modes_local=n_modes_local,
        contact_zone_centers=[(0.0, 0.0)],
        probe_xz=[],
        y_rest=shelf_y_rest,
        rayleigh_alpha0=rayleigh_alpha0,
        rayleigh_alpha1=rayleigh_alpha1,
    )
    rs.probe_body_indices = []

    avbd_box_idx = int(world._descs[box_idx].avbd_body.index)
    coupler = world.attach_reduced_coupled_avbd(
        rs,
        tracked_body_indices=[avbd_box_idx],
        shelf_length=shelf_length,
        shelf_width=shelf_width,
        shelf_y_rest=shelf_y_rest,
        n_grid_x=N_GRID_X,
        n_grid_z=N_GRID_Z,
        rho_clip=rho_clip,
    )
    coupler.dynamic_q = bool(dynamic_q)
    return ToyHandle(world=world, rs=rs, coupler=coupler, box_idx=box_idx)
