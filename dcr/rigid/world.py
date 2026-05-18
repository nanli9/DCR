"""Rigid body simulation world.

Symplectic Euler integration with constraint-based contact (paper §3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .body import RigidBody, quat_integrate
from .collision import Contact, detect_contacts
from .joint import DistanceJoint
from .solver import ConstraintSolver


@dataclass
class World:
    """Container for rigid body simulation state."""
    bodies: list[RigidBody] = field(default_factory=list)
    joints: list[DistanceJoint] = field(default_factory=list)
    gravity: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -9.81, 0.0]))
    h: float = 1e-2
    solver: ConstraintSolver = field(default_factory=lambda: ConstraintSolver())
    time: float = 0.0
    prev_contacts: list[Contact] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.solver.h = self.h

    def add_body(self, body: RigidBody) -> int:
        """Add a body and return its index."""
        self.bodies.append(body)
        return len(self.bodies) - 1

    def add_joint(self, joint: DistanceJoint) -> None:
        """Add a distance joint between two bodies."""
        self.joints.append(joint)

    def step(self) -> list[Contact]:
        """Advance simulation by one time step h.

        Returns the contact list for this step.
        """
        # 1. Apply gravity as an external force.
        for body in self.bodies:
            body.force = np.zeros(6)
            if not body.is_static:
                body.force[0:3] = body.mass * self.gravity

        # 2. Detect contacts.
        contacts = detect_contacts(self.bodies, self.prev_contacts)

        # 3. Solve constraints and update velocities.
        lam = self.solver.solve(self.bodies, contacts, self.joints)

        # 4. Integrate positions with symplectic Euler.
        for body in self.bodies:
            if body.is_static:
                continue
            v_lin = body.velocity[0:3]
            omega = body.velocity[3:6]

            body.position += self.h * v_lin
            body.orientation = quat_integrate(
                body.orientation, omega, self.h)

        self.time += self.h
        self.prev_contacts = contacts
        return contacts

    def kinetic_energy(self) -> float:
        """Total kinetic energy: sum of 0.5 * v^T * M * v over dynamic bodies."""
        ke = 0.0
        for body in self.bodies:
            if body.is_static:
                continue
            v = body.velocity
            M = body.mass_matrix()
            ke += 0.5 * v @ M @ v
        return ke

    def potential_energy(self, ref_height: float = 0.0) -> float:
        """Total gravitational PE relative to ref_height (assumes gravity along -Y)."""
        pe = 0.0
        for body in self.bodies:
            if body.is_static:
                continue
            pe += body.mass * (-self.gravity[1]) * (body.position[1] - ref_height)
        return pe

    def total_energy(self, ref_height: float = 0.0) -> float:
        return self.kinetic_energy() + self.potential_energy(ref_height)
