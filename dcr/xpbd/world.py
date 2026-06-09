"""XPBD world wrapper for the reduced-coupled coupler.

The minimal sibling of `dcr.avbd.world.AVBDDCRWorld` — just enough scaffolding
to build a scene, attach a `ReducedCoupledXPBDCoupler`, and step. The XPBD
solver itself (`dcr.xpbd._solver.solver_6dof.Solver6DOF`) does all the
constraint work for non-tracked bodies; the coupler handles per-corner contacts
on tracked bodies via Python hooks (`substep_begin / iteration / substep_end`).

For the tracked bodies we set `floor_disabled = 1` so XPBD's global-floor
constraint doesn't fight the coupler's per-corner deformable anchors.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..avbd.reduced_support import ReducedSupport
from ._solver.solver_6dof import RigidBody, Solver6DOF
from .reduced_coupled_xpbd import ReducedCoupledXPBDCoupler


@dataclass
class XPBDWorld:
    """Scene + step wrapper around `Solver6DOF` with a single attach point
    for the reduced-coupled modal coupler."""

    dt: float = 1.0 / 60.0
    substeps: int = 8
    iterations: int = 4
    gravity: tuple[float, float, float] = (0.0, -9.81, 0.0)
    floor_y: float = 0.0
    friction: float = 0.6
    restitution: float = 0.0
    device: str = "cpu"
    # Broad phase: "lbvh" / "hashgrid" / "grid". `None` (default) auto-picks:
    # cuda → "lbvh" (GPU device-resident tree, the fast path); cpu → "grid"
    # (host NumPy — `wp.Bvh` and `wp.HashGrid` are CUDA-only in Warp 1.13,
    # and on cpu Warp the .numpy() readback of body positions is just a
    # memcpy, so the host broad-phase has negligible overhead).
    broadphase: str | None = None

    _solver: Solver6DOF | None = field(default=None, init=False, repr=False)
    _coupler: ReducedCoupledXPBDCoupler | None = field(
        default=None, init=False, repr=False)
    time: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        bp = self.broadphase
        if bp is None:
            bp = "lbvh" if str(self.device).startswith("cuda") else "grid"
        self._solver = Solver6DOF(
            dt=self.dt,
            substeps=self.substeps,
            iterations=self.iterations,
            gravity=self.gravity,
            floor_y=self.floor_y,
            friction=self.friction,
            restitution=self.restitution,
            device=self.device,
            broadphase=bp,
        )

    @property
    def solver(self) -> Solver6DOF:
        assert self._solver is not None
        return self._solver

    @property
    def coupler(self) -> ReducedCoupledXPBDCoupler | None:
        return self._coupler

    # ---- scene building ----------------------------------------------------
    def add_box(self, *args, **kwargs) -> RigidBody:
        return self.solver.add_box(*args, **kwargs)

    def add_particle(self, *args, **kwargs) -> RigidBody:
        return self.solver.add_particle(*args, **kwargs)

    def add_joint(self, *args, **kwargs) -> int:
        return self.solver.add_joint(*args, **kwargs)

    # ---- coupler attachment ------------------------------------------------
    def attach_reduced_coupled_xpbd(
        self,
        rs: ReducedSupport,
        *,
        tracked_body_indices: list[int],
        shelf_length: float,
        shelf_width: float,
        shelf_y_rest: float,
        n_grid_x: int,
        n_grid_z: int,
        contact_stiffness: float = 1.0e8,
        modal_static_lp_tau: float = 0.05,
        anchor_static_lowpass: bool = True,
        contact_active_margin: float = 2.0e-3,
    ) -> ReducedCoupledXPBDCoupler:
        """Install the monolithic primal coupler. The proposal's §2.1 with
        XPBD as the host solver: same constraint formulation, same
        static/dynamic split, same exact-resonator IIR for `q_d`. The only
        XPBD-specific knobs are `contact_stiffness` (XPBD has no AL
        escalation — equivalent to AVBD's `rho_clip`) and the active-set
        margin used when identifying penetrating corners at substep_begin.
        """
        if self._solver is None:
            raise RuntimeError("XPBDWorld._solver is not initialized")
        if self._coupler is not None:
            raise RuntimeError("ReducedCoupledXPBDCoupler is already attached")

        # Force tracked bodies off XPBD's global floor — the coupler manages
        # their per-corner anchors on the deformable support.
        self.solver._flush()
        mask_host = np.asarray(
            self.solver._floor_disabled_host, np.int32).copy()
        for b in tracked_body_indices:
            mask_host[int(b)] = 1
        # Write back to the device-resident mask. _flush() has already
        # allocated `solver.floor_disabled` from `_floor_disabled_host`.
        self.solver._floor_disabled_host = mask_host.tolist()
        self.solver.floor_disabled.assign(mask_host)

        coupler = ReducedCoupledXPBDCoupler(
            rs=rs,
            tracked_body_indices=list(tracked_body_indices),
            shelf_length=float(shelf_length),
            shelf_width=float(shelf_width),
            shelf_y_rest=float(shelf_y_rest),
            n_grid_x=int(n_grid_x),
            n_grid_z=int(n_grid_z),
            h_macro=float(self.dt),
            h_substep=float(self.dt) / float(self.substeps),
            contact_stiffness=float(contact_stiffness),
            modal_static_lp_tau=float(modal_static_lp_tau),
            anchor_static_lowpass=bool(anchor_static_lowpass),
            contact_active_margin=float(contact_active_margin),
        )
        rs.overlay_enabled = False
        rs.restart_overlay_each_step = False
        self.solver.substep_begin_hook = coupler.substep_begin_hook
        self.solver.iteration_hook = coupler.iteration_hook
        self.solver.substep_end_hook = coupler.substep_end_hook
        self._coupler = coupler
        return coupler

    # ---- step --------------------------------------------------------------
    def step(self) -> None:
        self.solver.step()
        self.time += float(self.dt)

    # ---- readback ----------------------------------------------------------
    def positions(self) -> np.ndarray:
        return self.solver.positions()

    def orientations(self) -> np.ndarray:
        return self.solver.orientations()

    def velocities(self) -> np.ndarray:
        return self.solver.velocities()
