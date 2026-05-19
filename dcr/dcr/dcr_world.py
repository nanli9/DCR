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
from ..rigid.joint import DistanceJoint
from ..rigid.solver import ConstraintSolver
from .modal_dcr import ModalDCRCoupler


@dataclass
class DCRWorld:
    """Rigid body world with modal-path DCR coupling.

    Usage is identical to rigid.World, but with added DCR couplers
    that process elastic body vibrations after each PGS solve.

    Attributes:
        dcr_couplers: List of ModalDCRCoupler, one per elastic body.
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
    dcr_enabled: bool = True

    # Diagnostics.
    last_dcr_ke_injected: float = 0.0

    def __post_init__(self) -> None:
        self.solver.h = self.h

    def add_body(self, body: RigidBody) -> int:
        self.bodies.append(body)
        return len(self.bodies) - 1

    def add_joint(self, joint: DistanceJoint) -> None:
        self.joints.append(joint)

    def add_dcr_coupler(self, coupler: ModalDCRCoupler) -> None:
        self.dcr_couplers.append(coupler)

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

        # 3. Solve constraints → velocities updated, get λ.
        lam = self.solver.solve(self.bodies, contacts, self.joints)

        # 4. DCR pipeline (Path B: apply velocity corrections post-solve).
        self.last_dcr_ke_injected = 0.0
        if self.dcr_enabled and self.dcr_couplers and len(lam) > 0:
            for coupler in self.dcr_couplers:
                dcr_velocities = coupler.process_step(contacts, lam, self.h)

                # Eq. 13: Apply Δv to resting bodies in the normal direction.
                for body_idx, dv in dcr_velocities.items():
                    body = self.bodies[body_idx]
                    if body.is_static:
                        continue

                    # Find the contact normal for this body (use the first
                    # resting contact with the elastic body).
                    for c in contacts:
                        if c.is_new:
                            continue
                        elastic_idx = coupler.elastic_body_idx
                        if (c.body_a == elastic_idx and c.body_b == body_idx) or \
                           (c.body_b == elastic_idx and c.body_a == body_idx):
                            # Apply separation velocity along normal.
                            # DEVIATION: the solver's contact normals point
                            # from body B toward body A (see collision.py).
                            # We want to push the resting body away from
                            # the elastic surface.
                            normal = c.normal
                            if c.body_b == elastic_idx:
                                # Normal from elastic (B) toward rigid (A).
                                # Push A in +normal (away from elastic).
                                push_dir = normal
                            else:
                                # Normal from rigid (B) toward elastic (A).
                                # Push B in -normal (away from elastic).
                                push_dir = -normal

                            # Track KE before/after for diagnostics.
                            ke_before = 0.5 * body.mass * np.dot(
                                body.velocity[:3], body.velocity[:3])

                            body.velocity[:3] += dv * push_dir

                            ke_after = 0.5 * body.mass * np.dot(
                                body.velocity[:3], body.velocity[:3])
                            self.last_dcr_ke_injected += ke_after - ke_before
                            break

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
