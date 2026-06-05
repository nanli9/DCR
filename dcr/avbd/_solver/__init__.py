"""Vendored AVBD 3D rigid-body solver.

Vendored from the upstream port at https://github.com/nanli9/AVBD
(src/avbd3d/) for use as the DCR project's rigid solver. Only the 6-DOF
rigid path is re-exported; the particle solver and deformable-bunny
helpers remain in the source files for completeness but are not part of
the DCR public API.

Sync point: upstream commit 5bd6eac ("Fully GPU-resident solver + fused
primal + instanced viewer render", 2026-06-04). Re-synced solver_6dof.py
+ kernels_6dof.py to pick up two CUDA-only perf passes on top of the
previous sync (52d2483):
  - 33b0303: warp-per-body primal solve (warp-shuffle reduction joining
    G lanes per body — 2.8-5.1x on GPU). CPU is explicitly gated to the
    serial `primal_update_6dof` kernel; new `Solver6DOF` kwargs
    (primal_group_size, primal_shuffle, primal_fused) all have defaults
    that no-op on CPU.
  - 5bd6eac: fully GPU-resident solver (zero per-substep host readbacks
    via double-buffered fused primal + recolor-at-flush + fixed-capacity
    pools). New kwargs `gpu_resident`, `recolor_every_substep`,
    `unsafe_fixed_capacity` — all gated to CUDA via `_resident_on(dev)`,
    so CPU goes down the original readback path unchanged. Also sets
    module-wide `enable_backward=False` (forward-only solver — VBD/AVBD
    is not autodiff-based, and the `__shfl_down_sync` func_native has
    no adjoint).
DCR-local additions on top of upstream: `Solver6DOF.penalties()`
accessor used by the DCR coupler's 'augmented' effective-impulse source
(prompts/avbd_dcr_realtime_coupling_fix §2.2). The other vendored files
(coloring/kernels/scene/solver/deformable) are byte-identical to
upstream and were left untouched.

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
