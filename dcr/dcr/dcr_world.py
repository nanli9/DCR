"""DCR-enabled simulation world.

Extends the rigid body World (Stage 1) with modal-path distant collision
response (Eqs. 9–13). After the PGS solve, new impact impulses on elastic
bodies are propagated via the IIR modal stepper, and the resulting surface
displacement is converted to separation velocities at resting contacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..rigid.body import RigidBody, quat_integrate
from ..rigid.collision import Contact, detect_contacts
from ..rigid.energy import rigid_kinetic_energy
from ..rigid.joint import DistanceJoint
from ..rigid.solver import ConstraintSolver
from .modal_dcr import ModalDCRCoupler
from .passive_dcr import PassiveDCRCoupler
from .spatial_dcr import SpatialDCRCoupler
from .tilt_dcr import TiltDCRCoupler, TiltResult, apply_tilt_bounds


@dataclass
class DCRWorld:
    """Rigid body world with modal-path DCR coupling.

    Usage is identical to rigid.World, but with added DCR couplers
    that process elastic body vibrations after each PGS solve.

    Supports both original forced-IIR couplers (Stage 5) and passive
    energy-bounded couplers (Stage E3). Use one or the other per body.

    Attributes:
        dcr_couplers: List of ModalDCRCoupler, one per elastic body.
        passive_couplers: List of PassiveDCRCoupler for energy-bounded injection.
        eta: Transfer efficiency for passive couplers (foundation §1).
        dcr_enabled: Toggle DCR on/off (for A/B comparison).
    """

    bodies: list[RigidBody] = field(default_factory=list)
    joints: list[DistanceJoint] = field(default_factory=list)
    gravity: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -9.81, 0.0]))
    h: float = 1e-2
    solver: ConstraintSolver = field(default_factory=lambda: ConstraintSolver())
    time: float = 0.0
    prev_contacts: list[Contact] = field(default_factory=list)

    dcr_couplers: list[ModalDCRCoupler] = field(default_factory=list)
    passive_couplers: list[PassiveDCRCoupler] = field(default_factory=list)
    spatial_couplers: list[SpatialDCRCoupler] = field(default_factory=list)
    tilt_couplers: list[TiltDCRCoupler] = field(default_factory=list)
    tilt_only: bool = False  # If True, skip normal fallback for tilt couplers
    dcr_enabled: bool = True
    eta: float = 0.3  # Transfer efficiency η ∈ [0, 1] (foundation §1)

    # Diagnostics.
    last_dcr_ke_injected: float = 0.0
    last_E_loss: float = 0.0
    last_E_max: float = 0.0

    def __post_init__(self) -> None:
        self.solver.h = self.h

    def add_body(self, body: RigidBody) -> int:
        self.bodies.append(body)
        return len(self.bodies) - 1

    def add_joint(self, joint: DistanceJoint) -> None:
        self.joints.append(joint)

    def add_dcr_coupler(self, coupler: ModalDCRCoupler) -> None:
        self.dcr_couplers.append(coupler)

    def add_passive_coupler(self, coupler: PassiveDCRCoupler) -> None:
        self.passive_couplers.append(coupler)

    def add_spatial_coupler(self, coupler: SpatialDCRCoupler) -> None:
        self.spatial_couplers.append(coupler)

    def add_tilt_coupler(self, coupler: TiltDCRCoupler) -> None:
        self.tilt_couplers.append(coupler)

    def step(self) -> list[Contact]:
        """Advance simulation by one time step h with DCR.

        Flow:
            1. Apply gravity
            2. Detect contacts
            3. PGS solve → λ
            4. DCR: map new impacts → IIR → Δv at resting contacts (Eqs. 9–13)
            5. Apply DCR velocity corrections (Path B, Eqs. 12–13)
            6. Symplectic Euler position integration

        Returns the contact list for this step.
        """
        # 1. Apply gravity.
        for body in self.bodies:
            body.force = np.zeros(6)
            if not body.is_static:
                body.force[0:3] = body.mass * self.gravity

        # 2. Detect contacts.
        contacts = detect_contacts(self.bodies, self.prev_contacts)

        # E0.3: sample rigid KE before solve (foundation §1).
        E_pre = rigid_kinetic_energy(self.bodies)

        # 3. Solve constraints → velocities updated, get λ.
        lam = self.solver.solve(self.bodies, contacts, self.joints)

        # E0.3: sample rigid KE after solve, compute E_loss (foundation §1).
        E_post = rigid_kinetic_energy(self.bodies)
        self.last_E_loss = max(0.0, E_pre - E_post)
        self.last_E_max = self.eta * self.last_E_loss

        # 4. DCR pipeline (Path B: apply velocity corrections post-solve).
        self.last_dcr_ke_injected = 0.0
        if self.dcr_enabled and len(lam) > 0:
            # Original modal-path couplers (Stage 5, forced IIR).
            for coupler in self.dcr_couplers:
                dcr_velocities = coupler.process_step(contacts, lam, self.h)
                self._apply_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)

            # Passive energy-bounded couplers (Stage E3).
            for coupler in self.passive_couplers:
                dcr_velocities = coupler.process_step(
                    contacts, lam, self.h, self.last_E_max)
                self._apply_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)

            # Spatial-attenuation couplers (Stage 6).
            for coupler in self.spatial_couplers:
                dcr_velocities = coupler.process_step(contacts, lam, self.h)
                self._apply_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)

            # Tilt-DCR couplers (contact frame extension).
            # The tilt coupler replaces the normal DCR kick: the full
            # impulse goes along n' (tilted normal), not n + extra J_t.
            # For contacts without tilt (theta ~ 0), apply the standard
            # normal kick as fallback.
            for coupler in self.tilt_couplers:
                tilt_results = coupler.process_step(
                    contacts, lam, self.h, self.last_E_max)
                # Bodies that got tilt results — their kick is fully
                # handled by _apply_tilt_dcr_velocities along n'.
                tilted_bodies = {r.body_idx for r in tilt_results}
                # For bodies with no tilt (theta ~ 0), fall back to
                # the standard normal kick (unless tilt_only mode).
                if not self.tilt_only:
                    fallback = {k: v for k, v in coupler.last_dcr_velocities.items()
                                if k not in tilted_bodies}
                    if fallback:
                        self._apply_dcr_velocities(
                            fallback, contacts, coupler.elastic_body_idx)
                self._apply_tilt_dcr_velocities(tilt_results, coupler)

        # 5. Integrate positions.
        for body in self.bodies:
            if body.is_static:
                continue
            body.position += self.h * body.velocity[:3]
            body.orientation = quat_integrate(
                body.orientation, body.velocity[3:6], self.h)

        self.time += self.h
        self.prev_contacts = contacts
        return contacts

    def _apply_dcr_velocities(
        self,
        dcr_velocities: dict[int, float],
        contacts: list[Contact],
        elastic_idx: int,
    ) -> None:
        """Apply DCR separation velocities to resting bodies (Eq. 13/19)."""
        for body_idx, dv in dcr_velocities.items():
            body = self.bodies[body_idx]
            if body.is_static:
                continue

            for c in contacts:
                if c.is_new:
                    continue
                if (c.body_a == elastic_idx and c.body_b == body_idx) or \
                   (c.body_b == elastic_idx and c.body_a == body_idx):
                    # DEVIATION: solver normals point from B toward A.
                    normal = c.normal
                    if c.body_b == elastic_idx:
                        push_dir = normal   # push A away from elastic B
                    else:
                        push_dir = -normal  # push B away from elastic A

                    ke_before = 0.5 * body.mass * np.dot(
                        body.velocity[:3], body.velocity[:3])
                    body.velocity[:3] += dv * push_dir
                    ke_after = 0.5 * body.mass * np.dot(
                        body.velocity[:3], body.velocity[:3])
                    self.last_dcr_ke_injected += ke_after - ke_before
                    break

    def _apply_tilt_dcr_velocities(
        self,
        tilt_results: list[TiltResult],
        coupler: TiltDCRCoupler,
    ) -> None:
        """Apply the FULL DCR impulse along the tilted normal n'.

        Replaces the standard normal kick for bodies with nonzero tilt.
        The impulse J = m * dv * n' is decomposed:
          - J_n = (J . push_dir) * push_dir  → normal component
          - J_t = J - J_n                     → tangential (bounded)

        Both are applied as linear velocity. Angular response emerges
        from friction constraints in subsequent solver steps.
        """
        for r in tilt_results:
            body = self.bodies[r.body_idx]
            if body.is_static:
                continue

            # Full impulse along tilted normal
            J_mag = body.mass * r.dv
            J_full = J_mag * r.n_tilt

            # Decompose
            J_n_scalar = float(np.dot(J_full, r.push_dir))
            J_n_vec = J_n_scalar * r.push_dir
            J_t = J_full - J_n_vec

            # Apply bounds to tangential component only
            J_t = apply_tilt_bounds(
                J_n_scalar, J_t, body.mass, r.dv,
                coupler.mu_dcr, coupler.eta_t)

            # Recombine: bounded J_t + J_n (skip J_n in tilt_only mode)
            J_total = J_t if self.tilt_only else J_n_vec + J_t

            ke_before = 0.5 * body.mass * np.dot(
                body.velocity[:3], body.velocity[:3])
            body.velocity[:3] += J_total / body.mass
            ke_after = 0.5 * body.mass * np.dot(
                body.velocity[:3], body.velocity[:3])
            self.last_dcr_ke_injected += ke_after - ke_before

    def kinetic_energy(self) -> float:
        ke = 0.0
        for body in self.bodies:
            if body.is_static:
                continue
            v = body.velocity
            M = body.mass_matrix()
            ke += 0.5 * v @ M @ v
        return ke

    def potential_energy(self, ref_height: float = 0.0) -> float:
        pe = 0.0
        for body in self.bodies:
            if body.is_static:
                continue
            pe += body.mass * (-self.gravity[1]) * (body.position[1] - ref_height)
        return pe

    def total_energy(self, ref_height: float = 0.0) -> float:
        return self.kinetic_energy() + self.potential_energy(ref_height)
