"""Vendored AVBD 3D rigid-body solver.

Vendored from the upstream port at https://github.com/nanli9/AVBD
(src/avbd3d/) for use as the DCR project's rigid solver. Only the 6-DOF
rigid path is re-exported; the particle solver and deformable-bunny
helpers remain in the source files for completeness but are not part of
the DCR public API.

Sync point: upstream commit 52d2483 ("Default to paper-faithful 'jacobi'
graph coloring", 2026-06-03). Re-synced solver_6dof.py + kernels_6dof.py
to pick up the perf pass: achieved-color-count primal bound (A0/A1),
speculative 'jacobi' coloring (A2, now the default), stable-graph recolor
skip (A4), static half-extent re-upload skip (A5), the captured-graph
set_*() .assign() correctness fix, and read_state_batched(include_rows=)
HUD throttle (B1). The other vendored files (coloring/kernels/scene/
solver/deformable) are byte-identical to upstream and were left untouched.

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
