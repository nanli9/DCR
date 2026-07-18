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
# (the reduced coupler is removed — both solvers are native, no coupler)
from dcr.avbd.cargo.fem_rigid import (
    build_fem_rigid_cube,
    build_fem_cube,
    build_rigid_cube,
)
from dcr.avbd.cargo.abd import build_abd_cube
from dcr.fem.material import Material
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


@dataclass
class FEMRigidCargoHandle:
    """Everything needed to drive + render a cargo scene (any cube material)."""
    world: AVBDDCRWorld
    rs: ReducedSupport
    coupler: object | None   # always None now (native path; the coupler is removed)
    cube: object                 # FEMRigidModalBody | ABDAffineBody | FEMModalBody
    avbd_idx: int
    support_top: float
    support_length: float
    support_width: float
    kind: str = "fem_rigid"
    name: str = "cargo on reduced-modal support"


def _make_cube(kind, *, cube_size, cube_nx, cube_youngs, cube_density,
               n_elastic):
    """Build the requested cargo cube body (rigid | fem_rigid | abd | fem)."""
    if kind == "rigid":
        # Pure 6-DOF rigid cube (k=0): the no-deformation baseline.
        return build_rigid_cube(
            size=cube_size, nx=cube_nx,
            material=Material(E=cube_youngs, nu=0.3, rho=cube_density),
            drop_y=0.0)
    if kind == "fem_rigid":
        return build_fem_rigid_cube(
            size=cube_size, nx=cube_nx, n_elastic=n_elastic,
            material=Material(E=cube_youngs, nu=0.3, rho=cube_density),
            drop_y=0.0)
    if kind == "abd":
        # κ_v controls the affine shear stiffness (V⊥); soft enough to shear
        # visibly, stiff enough to stay near-rigid.
        return build_abd_cube(size=cube_size, nx=cube_nx, kappa_v=2.0e3,
                              alpha0=2.0, drop_y=0.0)
    if kind == "fem":
        # translation+modal, NO co-rotation (a restriction of fem_rigid).
        return build_fem_cube(
            size=cube_size, nx=cube_nx, n_elastic=n_elastic,
            material=Material(E=cube_youngs, nu=0.3, rho=cube_density),
            drop_y=0.0)
    raise ValueError(
        f"unknown cargo kind {kind!r} (rigid | fem_rigid | abd | fem)")


def build_cargo_scene(
    kind: str = "fem_rigid",
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
    solver: str = "avbd",
    xpbd_contact_compliance: float = 1.0e-8,
) -> FEMRigidCargoHandle:
    """Build a one-cube cargo scene (cube material = `kind`) + attach the
    dynamic coupler. `spin` (rad/s about z) tumbles the cube so the co-rotated
    contact Jacobian is exercised at non-trivial orientations. `solver` selects
    the per-iteration primal: "avbd" (Schur–Newton) or "xpbd" (compliant
    Gauss–Seidel, Stage 6)."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
        solver_kind=solver if solver in ("xpbd", "impulse") else "avbd")
    world.add_floor(floor_y=support_top, friction=0.5, name="support")

    cube = _make_cube(kind, cube_size=cube_size, cube_nx=cube_nx,
                      cube_youngs=cube_youngs, cube_density=cube_density,
                      n_elastic=n_elastic)
    half = cube.half_extent
    dcr_idx = world.add_box(
        mass=cube.mass, half_extents=(half, half, half),
        position=(0.0, support_top + half + float(drop_height), 0.0),
        velocity_ang=(0.0, 0.0, float(spin)),
        friction=0.5, name=f"{kind}_cube")
    avbd_idx = int(world._descs[dcr_idx].avbd_body.index)

    rs = make_debug_reduced_shelf_support(
        length=support_length, width=support_width, thickness=support_thickness,
        youngs=support_youngs, density=support_density, poisson=0.30,
        n_modes_global=8, n_modes_local=1,
        contact_zone_centers=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        y_rest=support_top, overlay_enabled=False,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, to_eigenbasis=True)

    if solver in ("avbd", "native", "xpbd", "impulse"):
        # Native cargo (M2): the cube's elastic modes are a NATIVE modal block of
        # the chosen solver (two_band_coupling.html, Approach B). No coupler, no
        # hook — the cube's support contacts and its a-modes are co-solved in the
        # same step. The World's solver_kind routes to SolverXPBD or SolverAVBD.
        # rigid (k=0) reduces this to the support-only modal solve. Couplers are
        # "avbd_coupler" / "xpbd_coupler" (transitional, deleted Stage 6).
        if kind not in ("rigid", "fem_rigid", "fem", "abd"):
            raise ValueError(
                f"native solver supports kind in (rigid, fem_rigid, fem, abd) "
                f"(got {kind!r}).")
        # device residency is an AVBD-native knob (SolverXPBD is CPU-only here).
        if device_resident is not None and solver != "xpbd":
            world._solver._modal_device_resident = bool(device_resident)
        world.enable_reduced_modal_support(
            rs, tracked_body_indices=[avbd_idx],
            shelf_length=support_length, shelf_width=support_width,
            shelf_y_rest=support_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
        world.add_native_cargo(avbd_idx, cube)
        # freeze-q̇ counterfactual flag: SolverAVBD uses _modal_freeze_qdot,
        # SolverXPBD uses _freeze_qdot.
        if solver == "xpbd":
            world._solver._freeze_qdot = bool(freeze_qdot)
        else:
            world._solver._modal_freeze_qdot = bool(freeze_qdot)
        return FEMRigidCargoHandle(
            world=world, rs=rs, coupler=None, cube=cube, avbd_idx=avbd_idx,
            support_top=support_top, support_length=support_length,
            support_width=support_width, kind=kind)
    raise ValueError(f"unknown solver {solver!r} (avbd | xpbd | impulse)")


def build_fem_rigid_cargo(**kwargs) -> FEMRigidCargoHandle:
    """fem_rigid specialization of `build_cargo_scene` (back-compat)."""
    return build_cargo_scene("fem_rigid", **kwargs)


def cube_state_world(handle: FEMRigidCargoHandle) -> np.ndarray:
    """Current cube config z = [p(3), q(4 wxyz), a(k)] from the live AVBD body
    + the coupler's modal amplitude — for skinning `cube.deformed_surface`."""
    solver = handle.world._solver
    p = solver.positions()[handle.avbd_idx].astype(np.float64)
    q_xyzw = solver.orientations()[handle.avbd_idx].astype(np.float64)
    q_wxyz = np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]])
    # native path: a lives on the solver (no coupler); coupler path: on the coupler.
    a = (solver.cargo_a(handle.avbd_idx) if handle.coupler is None
         else handle.coupler.cargo_a[handle.avbd_idx].copy())
    z = np.zeros(7 + handle.cube.k)
    z[0:3] = p
    z[3:7] = q_wxyz
    z[7:] = a
    return z
