"""fem_rigid cargo demo scene (Stage 3 — AVBD-Native dynamic-constraint port).

A single `fem_rigid` cube — a full 6-DOF rigid box with real SAT collision
PLUS k FEM elastic modes carried in its body frame (floating-frame reduced
body, `dcr/avbd/cargo/fem_rigid.py`) — dropped onto the reduced-modal
support. The cube's contact corners feed BOTH the rigid contact gradient and
the co-rotated modal gradient n̂ᵀ·R·Φ_c into the SAME dynamic two-way modal
block as the support (`two_band_coupling.html`), assembled as the augmented
modal vector Q = [q_support; a_cube]. On impact the cube tumbles/settles with
zero penetration (rigid SAT) AND flexes (its elastic modes ring), while the
support rings underneath it — both directions through one shared multiplier.

This is the first cube-material scene of the fem_rigid → abd → fem dropdown.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import ReducedSupport, make_debug_reduced_shelf_support
from dcr.avbd.reduced_coupled_avbd import ReducedCoupledAVBDCoupler
from dcr.avbd.cargo.fem_rigid import FEMRigidModalBody, build_fem_rigid_cube
from dcr.fem.material import Material
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


@dataclass
class FEMRigidCargoHandle:
    """Everything needed to drive + render the fem_rigid cargo scene."""
    world: AVBDDCRWorld
    rs: ReducedSupport
    coupler: ReducedCoupledAVBDCoupler
    cube: FEMRigidModalBody
    avbd_idx: int
    support_top: float
    support_length: float
    support_width: float
    name: str = "fem_rigid cargo on reduced-modal support"


def build_fem_rigid_cargo(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 8,
    avbd_substeps: int = 4,
    support_length: float = 0.6,
    support_width: float = 0.4,
    support_thickness: float = 0.02,
    support_top: float = 0.0,
    support_youngs: float = 1.0e10,
    support_density: float = 500.0,
    cube_size: float = 0.1,
    cube_nx: int = 3,
    cube_youngs: float = 1.0e6,
    cube_density: float = 600.0,
    n_elastic: int = 6,
    drop_height: float = 0.04,
    spin: float = 0.0,
    freeze_qdot: bool = False,
    device_resident: bool | None = None,
) -> FEMRigidCargoHandle:
    """Build the scene + attach the dynamic coupler with one fem_rigid cube.

    `spin` (rad/s about z) makes the cube tumble so the co-rotated R·Φ_c
    modal Jacobian is exercised at non-trivial orientations. `cube_youngs`
    is soft by default so the elastic flex is visible (the rigid SAT
    collision is independent of modal softness — penetration is unaffected).
    """
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps))
    world.add_floor(floor_y=support_top, friction=0.5, name="support")

    cube = build_fem_rigid_cube(
        size=cube_size, nx=cube_nx, n_elastic=n_elastic,
        material=Material(E=cube_youngs, nu=0.3, rho=cube_density), drop_y=0.0)
    half = cube.half_extent
    dcr_idx = world.add_box(
        mass=cube.mass, half_extents=(half, half, half),
        position=(0.0, support_top + half + float(drop_height), 0.0),
        velocity_ang=(0.0, 0.0, float(spin)),
        friction=0.5, name="fem_rigid_cube")
    avbd_idx = int(world._descs[dcr_idx].avbd_body.index)

    rs = make_debug_reduced_shelf_support(
        length=support_length, width=support_width, thickness=support_thickness,
        youngs=support_youngs, density=support_density, poisson=0.30,
        n_modes_global=8, n_modes_local=1,
        contact_zone_centers=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        y_rest=support_top, overlay_enabled=False,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, to_eigenbasis=True)

    coupler = world.attach_reduced_coupled_avbd(
        rs, tracked_body_indices=[avbd_idx],
        shelf_length=support_length, shelf_width=support_width,
        shelf_y_rest=support_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
        device_resident=device_resident)
    coupler.freeze_qdot = bool(freeze_qdot)
    coupler.add_cargo(avbd_idx, cube)

    return FEMRigidCargoHandle(
        world=world, rs=rs, coupler=coupler, cube=cube, avbd_idx=avbd_idx,
        support_top=support_top, support_length=support_length,
        support_width=support_width)


def cube_state_world(handle: FEMRigidCargoHandle) -> np.ndarray:
    """Current cube config z = [p(3), q(4 wxyz), a(k)] from the live AVBD body
    + the coupler's modal amplitude — for skinning `cube.deformed_surface`."""
    solver = handle.world._solver
    p = solver.positions()[handle.avbd_idx].astype(np.float64)
    q_xyzw = solver.orientations()[handle.avbd_idx].astype(np.float64)
    q_wxyz = np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]])
    a = handle.coupler.cargo_a[handle.avbd_idx].copy()
    z = np.zeros(7 + handle.cube.k)
    z[0:3] = p
    z[3:7] = q_wxyz
    z[7:] = a
    return z
