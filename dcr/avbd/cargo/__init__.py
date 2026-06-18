"""Deformable cargo body models for the AVBD-Native dynamic-constraint port.

Cargo bodies that ride the GPU AVBD solver as rigid boxes (real SAT collision)
*and* carry reduced elastic DOFs coupled to their contact corners, via the same
dynamic two-way modal constraint as the support (`two_band_coupling.html`):

- `fem_rigid`  — 6-DOF rigid frame ⊕ k FEM elastic modes (floating-frame).
- `abd`        — affine 12-DOF body (p + A), quartic orthogonality potential.
- `fem`        — translation(3) ⊕ modes (no rotation; a restriction of fem_rigid).
"""
from .fem_rigid import (
    FEMRigidModalBody,
    build_fem_rigid_cube,
    cube_corner_ids,
)

__all__ = [
    "FEMRigidModalBody",
    "build_fem_rigid_cube",
    "cube_corner_ids",
]
