"""Distance joint (rigid rod) constraint.

A bilateral constraint that maintains a fixed distance between two anchor
points on different bodies. Like a rigid rod connecting two objects.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .body import RigidBody


@dataclass
class DistanceJoint:
    """A rigid rod connecting two bodies.

    Attributes:
        body_a: index of body A.
        body_b: index of body B.
        local_anchor_a: (3,) attachment point in body A's local frame.
        local_anchor_b: (3,) attachment point in body B's local frame.
        rest_length: target distance between the two anchor points.
    """
    body_a: int
    body_b: int
    local_anchor_a: NDArray[np.float64]
    local_anchor_b: NDArray[np.float64]
    rest_length: float

    def world_anchor_a(self, bodies: list[RigidBody]) -> NDArray[np.float64]:
        b = bodies[self.body_a]
        return b.position + b.rotation_matrix() @ self.local_anchor_a

    def world_anchor_b(self, bodies: list[RigidBody]) -> NDArray[np.float64]:
        b = bodies[self.body_b]
        return b.position + b.rotation_matrix() @ self.local_anchor_b

    def current_length(self, bodies: list[RigidBody]) -> float:
        diff = self.world_anchor_a(bodies) - self.world_anchor_b(bodies)
        return float(np.linalg.norm(diff))

    def direction(self, bodies: list[RigidBody]) -> NDArray[np.float64]:
        """Unit vector from anchor B toward anchor A."""
        diff = self.world_anchor_a(bodies) - self.world_anchor_b(bodies)
        d = np.linalg.norm(diff)
        if d < 1e-12:
            return np.array([0.0, 1.0, 0.0])
        return diff / d

    def violation(self, bodies: list[RigidBody]) -> float:
        """Signed constraint error: positive = stretched, negative = compressed."""
        return self.current_length(bodies) - self.rest_length
