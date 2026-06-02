"""Vendored AVBD 3D rigid-body solver.

Copied from /Users/nan/Desktop/fracture/avbd3d/src/avbd3d/ for use as the
DCR project's rigid solver. Only the 6-DOF rigid path is re-exported;
the particle solver and deformable-bunny helpers remain in the source
files for completeness but are not part of the DCR public API.

Upstream reference: Giles et al., SIGGRAPH 2025 (Augmented Vertex Block
Descent). See dcr/avbd/_solver/solver_6dof.py for the spec §4 objective
implementation.
"""
from .solver_6dof import (
    Solver6DOF,
    RigidBody,
    box_inertia_local,
    box_inv_inertia_local,
    FLOOR_CONTACT_6DOF,
    CONTACT_TANGENT_6DOF,
    PIN_6DOF,
    BOX_BOX_CONTACT_6DOF,
)

__all__ = [
    "Solver6DOF",
    "RigidBody",
    "box_inertia_local",
    "box_inv_inertia_local",
    "FLOOR_CONTACT_6DOF",
    "CONTACT_TANGENT_6DOF",
    "PIN_6DOF",
    "BOX_BOX_CONTACT_6DOF",
]
