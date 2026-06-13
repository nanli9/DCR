"""Two-way reduced-coordinate coupling demonstrator (investigation branch).

A self-contained CPU/numpy reference that couples TWO reduced elastic bodies in
contact and shows they settle to the static-sag equilibrium under damping
(see `docs/two_way_modal_coupling_investigation.md` and
`docs/two_way_modal_coupling_impl_sketch.md`).

The slab is always a FEM-modal reduced body. The cube is modelled two
interchangeable ways for comparison:

  * `ABDAffineBody`  — 12-DOF affine body (Lan et al. 2022, `docs/ABD.pdf`).
  * `FEMModalBody`   — translation carrier + FEM elastic eigenmodes.

Both couple through the same monolithic incremental-potential step in
`coupled_step.py`.

NOTE: this is a reference demonstrator, NOT wired into the production
`reduced_coupled_avbd` GPU coupler. Penalty contact (not the IPC log barrier)
and a non-rotating cube carrier are deliberate, documented simplifications.
"""
from __future__ import annotations

from dcr.twobody.reduced_body import (
    ABDAffineBody,
    FEMModalBody,
    build_abd_cube,
    build_fem_cube,
    build_fem_slab,
)
from dcr.twobody.coupled_step import (
    ContactPair,
    TwoBodySystem,
    TwoBodyState,
)

__all__ = [
    "ABDAffineBody",
    "FEMModalBody",
    "build_abd_cube",
    "build_fem_cube",
    "build_fem_slab",
    "ContactPair",
    "TwoBodySystem",
    "TwoBodyState",
]
