"""Rigid-body kinetic energy observable (Stage E0).

Implements E_rigid = sum_b (0.5 m_b ||v_b||^2 + 0.5 omega_b^T I_b omega_b)
(foundation §1).
See passive_energy_injection_implementation_prompt.md E0.1.
"""
from __future__ import annotations

import numpy as np

from .body import RigidBody


def rigid_kinetic_energy(bodies: list[RigidBody]) -> float:
    """Total rigid-body kinetic energy (foundation §1, core eq. §15).

    E_rigid = sum_b (0.5 m_b ||v_b||^2 + 0.5 omega_b^T I_b omega_b)

    with I_b in world frame (rotated body-frame inertia each step).
    Skips static bodies.
    """
    ke = 0.0
    for body in bodies:
        if body.is_static:
            continue
        v_lin = body.velocity[0:3]
        omega = body.velocity[3:6]
        I_world = body.inertia_world()
        ke += 0.5 * body.mass * np.dot(v_lin, v_lin)
        ke += 0.5 * omega @ I_world @ omega
    return float(ke)
