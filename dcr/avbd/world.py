"""AVBD-backed DCR world.

`AVBDDCRWorld` is a drop-in replacement for `dcr.dcr.DCRWorld` whose
rigid solve is delegated to the vendored AVBD `Solver6DOF`. The patch-
mode response math (`PassiveDCRCoupler`) is unchanged; this class is
the seam between AVBD's per-row constraint pool and the DCR coupler's
expectation of `(contacts, lam_triples)` per step.

Spec mapping:
  - prompts/avbd_native_dcr_followup_spec_v2.md §1   (AVBD-only framing)
  - prompts/avbd_native_dcr_followup_spec_v2.md §9   (patch reformulation)
  - prompts/avbd_native_dcr_followup_spec_v2.md §13  (transpose-consistent
                                                     modal back-reaction —
                                                     unchanged math, inherited
                                                     from passive_dcr.py)
  - prompts/avbd_native_dcr_followup_spec_v2.md §24 M1, M4, M8
                                                    (impulse exposure,
                                                     modal injection from
                                                     AVBD λ, back-reaction)

# DEVIATION (spec §7, §12, §15): Phase A does NOT add the moving-support
# AVBD constraint type, the passivity line search with γ rescale, nor the
# closed-system energy ledger. Those are deferred to a Phase B branch
# (see plan §"Out of scope").
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dcr.rigid.body import (
    RigidBody, ShapeType, box_shape, plane_shape, quat_identity,
)
from dcr.rigid.collision import Contact
from dcr.rigid.energy import rigid_kinetic_energy
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.dcr.distant_velocity import PatchKick

from ._solver import (
    Solver6DOF,
    RigidBody as AVBDRigidBody,
    FLOOR_CONTACT_6DOF,
)
from .contact_extract import extract_contacts


# ---------------------------------------------------------------------------
# Body descriptor
# ---------------------------------------------------------------------------

@dataclass
class AVBDBodyDescriptor:
    """Binding between a DCR-side RigidBody and an AVBD-side RigidBody.

    The DCR-side body is what `PassiveDCRCoupler` reads (mass, velocity,
    inertia, etc.). The AVBD-side handle is what `Solver6DOF` operates
    on. Each step we sync state from AVBD → DCR (after solve) and from
    DCR → AVBD (after patch kicks are applied).

    `avbd_body` is None for the synthetic "floor"/"elastic-ground" body
    — that body exists only on the DCR side; AVBD models the elastic
    surface as a Y-up floor plane and never gives it a kinematic body.
    """
    dcr_body: RigidBody
    avbd_body: AVBDRigidBody | None
    name: str = ""


# ---------------------------------------------------------------------------
# AVBDDCRWorld
# ---------------------------------------------------------------------------

@dataclass
class AVBDDCRWorld:
    """Replaces `DCRWorld` while keeping the same public surface.

    Differences from `DCRWorld`:
      * Rigid solve runs in AVBD's primal/dual loop (Solver6DOF).
      * Only `energy_prescribed_patch` is supported on the coupler side
        (see Phase A rip-out in `dcr/dcr/passive_dcr.py`).
      * Gravity is applied INSIDE the AVBD step (Solver6DOF takes a
        `gravity` constructor arg); the world does not re-apply it.
    """

    h: float = 1.0 / 60.0
    eta: float = 0.5
    gravity: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -9.81, 0.0]))
    device: str = "cpu"
    avbd_iterations: int = 10
    avbd_substeps: int = 1
    enforce_rigid_energy_bound: bool = False

    # Filled in by the user via add_body / add_passive_coupler.
    _descs: list[AVBDBodyDescriptor] = field(default_factory=list, init=False)
    passive_couplers: list[PassiveDCRCoupler] = field(
        default_factory=list, init=False)
    _solver: Solver6DOF | None = field(default=None, init=False, repr=False)
    _floor_y: float | None = field(default=None, init=False)
    _floor_body_idx: int | None = field(default=None, init=False)
    _prev_contact_keys: set = field(default_factory=set, init=False, repr=False)
    time: float = field(default=0.0, init=False)

    # Per-step diagnostics (mirror DCRWorld fields for run_scenes.py).
    last_E_loss: float = field(default=0.0, init=False)
    last_E_max: float = field(default=0.0, init=False)
    last_dcr_ke_injected: float = field(default=0.0, init=False)
    last_contacts: list[Contact] = field(default_factory=list, init=False, repr=False)
    last_lam: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(0), init=False, repr=False)
    last_step_ms: float = field(default=0.0, init=False)
    # Per-stage breakdown (ms). Helps profile where step time goes.
    last_solve_ms: float = field(default=0.0, init=False)
    last_extract_ms: float = field(default=0.0, init=False)
    last_coupler_ms: float = field(default=0.0, init=False)
    last_sync_ms: float = field(default=0.0, init=False)
    # Number of dynamic body velocities pushed back into AVBD this step.
    # Zero when no patch kicks fired (DCR didn't modify any velocity).
    last_sync_n: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._solver = Solver6DOF(
            dt=self.h,
            iterations=self.avbd_iterations,
            substeps=self.avbd_substeps,
            gravity=tuple(float(g) for g in self.gravity),
            device=self.device,
            post_stabilize=True,
        )

    # ---- Body registration -------------------------------------------------

    @property
    def bodies(self) -> list[RigidBody]:
        """DCR-side body list. PassiveDCRCoupler reads this."""
        return [d.dcr_body for d in self._descs]

    def add_floor(
        self,
        floor_y: float,
        friction: float = 0.5,
        name: str = "floor",
    ) -> int:
        """Register a synthetic static floor at `y = floor_y`. Returns its
        DCR-side body index. AVBD does not get its own body for the
        floor — `add_floor_contact_box` later wires rigid bodies to it.
        """
        if self._floor_y is not None:
            raise RuntimeError("AVBDDCRWorld supports a single floor")
        self._floor_y = float(floor_y)
        # The synthetic floor body is treated as static / infinite-mass on
        # the DCR side so coupler bookkeeping degenerates gracefully.
        rb = RigidBody(
            mass=float("inf"),
            inertia_body=np.full(3, float("inf")),
            position=np.array([0.0, floor_y, 0.0]),
            orientation=quat_identity(),
            velocity=np.zeros(6),
            force=np.zeros(6),
            shape=plane_shape(normal=(0.0, 1.0, 0.0)),
            is_static=True,
            friction=friction,
        )
        idx = len(self._descs)
        self._descs.append(AVBDBodyDescriptor(
            dcr_body=rb, avbd_body=None, name=name))
        self._floor_body_idx = idx
        return idx

    def add_box(
        self,
        mass: float,
        half_extents: tuple[float, float, float],
        position: tuple[float, float, float],
        orientation_wxyz: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0),
        velocity_lin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        velocity_ang: tuple[float, float, float] = (0.0, 0.0, 0.0),
        friction: float = 0.5,
        restitution: float = 0.0,
        name: str = "",
        floor_contact: bool = True,
    ) -> int:
        """Add a dynamic rigid box. Wires `add_floor_contact_box` on the
        AVBD side iff a floor has been registered AND `floor_contact`.
        Returns the DCR-side index of the new body.
        """
        if self._solver is None:
            raise RuntimeError("AVBDDCRWorld._solver is not initialized")
        hx, hy, hz = half_extents
        # AVBD quaternion convention is XYZW; we expose WXYZ on the DCR
        # API for consistency with the rest of dcr/.
        w, x, y, z = orientation_wxyz
        avbd_q = (x, y, z, w)
        avbd_body = self._solver.add_box(
            position=position,
            half_extents=half_extents,
            mass=mass,
            orientation=avbd_q,
            velocity=velocity_lin,
            angular_velocity=velocity_ang,
            friction=friction,
        )
        if floor_contact and self._floor_y is not None:
            self._solver.add_floor_contact_box(
                avbd_body, floor_y=self._floor_y, friction=friction)
        # Body-body contact between boxes uses AVBD's self-collision pool.
        # Enable lazily on first box add.
        if not self._solver._self_collide:
            self._solver.enable_self_collision(True, default_friction=friction)

        # DCR-side mirror.
        # Inertia (paper convention for box): I = m/12 * diag(...). AVBD
        # uses m/3 with half-extents (equivalent); we use the canonical
        # DCR formula for the DCR-side body so coupler kinematics agree.
        I_diag = np.array([
            mass / 12.0 * ((2 * hy) ** 2 + (2 * hz) ** 2),
            mass / 12.0 * ((2 * hx) ** 2 + (2 * hz) ** 2),
            mass / 12.0 * ((2 * hx) ** 2 + (2 * hy) ** 2),
        ])
        rb = RigidBody(
            mass=float(mass),
            inertia_body=I_diag,
            position=np.array(position, dtype=np.float64),
            orientation=np.array(orientation_wxyz, dtype=np.float64),
            velocity=np.concatenate([velocity_lin, velocity_ang]).astype(np.float64),
            force=np.zeros(6),
            shape=box_shape(hx, hy, hz),
            is_static=(mass <= 0.0),
            restitution=float(restitution),
            friction=float(friction),
        )
        idx = len(self._descs)
        self._descs.append(AVBDBodyDescriptor(
            dcr_body=rb, avbd_body=avbd_body, name=name))
        return idx

    def add_passive_coupler(self, coupler: PassiveDCRCoupler) -> None:
        if coupler.dcr_velocity_mode != "energy_prescribed_patch":
            raise ValueError(
                "AVBDDCRWorld only supports dcr_velocity_mode="
                "'energy_prescribed_patch' in Phase A; got "
                f"{coupler.dcr_velocity_mode!r}")
        self.passive_couplers.append(coupler)

    # ---- Step -------------------------------------------------------------

    def step(self) -> list[Contact]:
        """One rigid step. Flow:

            1. Snapshot pre-solve rigid KE.
            2. AVBD step (gravity inside).
            3. Sync AVBD → DCR body state.
            4. Extract contacts + lam triples.
            5. Compute E_loss, E_max.
            6. For each passive coupler: process_step → patch kicks.
            7. Apply patch kicks (Newton-3rd modal back-reaction is done
               inside coupler.process_step at the moment of the kick;
               here we just apply the impulse to the rigid body and
               push the corrected velocity back into AVBD).
            8. Bookkeeping + return contacts.
        """
        import time as _t
        t0 = _t.perf_counter()

        # (1) snapshot rigid KE.
        E_rigid_pre = rigid_kinetic_energy([d.dcr_body for d in self._descs])

        # (2) AVBD solve.
        t_solve_0 = _t.perf_counter()
        self._solver.step()
        self.last_solve_ms = (_t.perf_counter() - t_solve_0) * 1000.0

        # (3) sync state AVBD → DCR (single batched readback per array).
        self._sync_avbd_to_dcr()

        # (4) extract contacts.
        t_extract_0 = _t.perf_counter()
        contacts, lam, records, current_keys = extract_contacts(
            self._solver,
            floor_body_idx=self._floor_body_idx,
            prev_contact_keys=self._prev_contact_keys,
            dt=self.h,
        )
        self.last_extract_ms = (_t.perf_counter() - t_extract_0) * 1000.0
        self._prev_contact_keys = current_keys
        self.last_contacts = contacts
        self.last_lam = lam

        # (5) energy bookkeeping.
        E_rigid_post = rigid_kinetic_energy([d.dcr_body for d in self._descs])
        self.last_E_loss = max(0.0, E_rigid_pre - E_rigid_post)
        self.last_E_max = self.eta * self.last_E_loss
        self.last_dcr_ke_injected = 0.0

        # (6/7) coupler dispatch + apply patch impulses.
        t_coupler_0 = _t.perf_counter()
        bodies = [d.dcr_body for d in self._descs]
        kicked_any = False
        for coupler in self.passive_couplers:
            coupler.process_step(
                contacts, lam, self.h, self.last_E_max, bodies=bodies)
            patch_kicks = getattr(coupler, "last_patch_kicks", None)
            if patch_kicks:
                self._apply_patch_kicks(patch_kicks, bodies)
                kicked_any = True
        self.last_coupler_ms = (_t.perf_counter() - t_coupler_0) * 1000.0

        # Sync DCR → AVBD only if a patch kick actually modified velocities.
        # Without this gate, even on steps where the coupler is a no-op we
        # were paying ~24 full-array CPU↔Warp roundtrips (every step).
        t_sync_0 = _t.perf_counter()
        if kicked_any:
            self._sync_dcr_to_avbd_velocities_batched()
        else:
            self.last_sync_n = 0
        self.last_sync_ms = (_t.perf_counter() - t_sync_0) * 1000.0

        self.time += self.h
        self.last_step_ms = (_t.perf_counter() - t0) * 1000.0
        return contacts

    # ---- internals --------------------------------------------------------

    def _sync_avbd_to_dcr(self) -> None:
        """Copy positions / orientations / velocities from Solver6DOF
        readbacks into the parallel DCR-side body list.

        Four `.numpy()` calls (one per state array) — each is a single
        device→host transfer that's then sliced cheaply in numpy. Per-
        body indexing happens on the host-side ndarrays, no further
        GPU traffic. Quaternion convention swap: AVBD = XYZW, DCR = WXYZ.
        """
        positions = self._solver.positions()        # (n_b, 3)
        orientations = self._solver.orientations()  # (n_b, 4) xyzw
        velocities = self._solver.velocities()      # (n_b, 3)
        omegas = self._solver.angular_velocities()  # (n_b, 3)
        for desc in self._descs:
            if desc.avbd_body is None:
                continue
            i = desc.avbd_body.index
            desc.dcr_body.position[:] = positions[i]
            # XYZW → WXYZ.
            desc.dcr_body.orientation[0] = orientations[i, 3]
            desc.dcr_body.orientation[1] = orientations[i, 0]
            desc.dcr_body.orientation[2] = orientations[i, 1]
            desc.dcr_body.orientation[3] = orientations[i, 2]
            desc.dcr_body.velocity[0:3] = velocities[i]
            desc.dcr_body.velocity[3:6] = omegas[i]

    def _sync_dcr_to_avbd_velocities_batched(self) -> None:
        """After patch kicks modify DCR-side velocities, push them back
        into AVBD in a SINGLE batched read/write per array.

        The naive `Solver6DOF.set_velocity(body, v)` does
        `wp.array(self.v.numpy().copy()...)` per call — for N bodies,
        that's 2N full-array CPU↔Warp roundtrips per step. Here we do
        one download + one in-place upload per array, even with N=12
        dynamic bodies as in the truck scene.

        Uses `wp.array.assign(numpy_arr)` for in-place upload (does NOT
        reallocate the warp buffer, so kernel array refs stay valid).
        """
        sol = self._solver
        # Snapshot once.
        v_np = sol.v.numpy().copy()
        w_np = sol.omega.numpy().copy()
        n = 0
        for desc in self._descs:
            if desc.avbd_body is None or desc.dcr_body.is_static:
                continue
            i = desc.avbd_body.index
            dv = desc.dcr_body.velocity
            v_np[i] = (float(dv[0]), float(dv[1]), float(dv[2]))
            w_np[i] = (float(dv[3]), float(dv[4]), float(dv[5]))
            n += 1
        sol.v.assign(v_np)
        sol.omega.assign(w_np)
        self.last_sync_n = n

    def _apply_patch_kicks(
        self,
        kicks: list[PatchKick],
        bodies: list[RigidBody],
    ) -> None:
        """Apply patch-impulse kicks to the receiver bodies.

        Mirrors `DCRWorld._apply_patch_impulse_dcr_velocities` (dcr_world.py
        lines 539-572) — the math is identical; the coupler has already
        done §9.5 cone + §9.6 passivity scaling + the transpose-consistent
        modal back-reaction on `coupler._stepper.qdot`. We only translate
        the rigid impulse into rigid velocity here.

            v_lin += (1/m) · λ
            ω     += I_world^{-1} · (r̄ × λ)
        """
        for kk in kicks:
            body = bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0 or np.isinf(body.mass):
                continue
            ke_before = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_before += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            I_inv = body.inertia_world_inv()
            body.velocity[0:3] += kk.lam / body.mass
            body.velocity[3:6] += I_inv @ np.cross(kk.r_bar, kk.lam)
            ke_after = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_after += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            self.last_dcr_ke_injected += ke_after - ke_before

    # ---- Convenience: DCRWorld parity --------------------------------------

    def add_body(self, *_args, **_kwargs):  # pragma: no cover
        raise NotImplementedError(
            "AVBDDCRWorld does not accept generic RigidBody handles. Use "
            "add_box(...) or add_floor(...) instead so the AVBD side has "
            "the right constraint rows attached.")
