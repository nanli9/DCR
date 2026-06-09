"""Smoke test for the XPBD reduced-coupled coupler.

Builds a small shelf + single box, attaches the coupler, runs 30 steps, and
asserts the diagnostics surface is populated and the box is supported by the
deformable shelf rather than free-falling through it. Mirrors the AVBD
coupler's smoke test in spirit — not a numerical-accuracy test.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.reduced_support import make_debug_reduced_shelf_support
from dcr.xpbd import XPBDWorld


@pytest.mark.parametrize("anchor_lp", [True, False])
def test_box_lands_on_deformable_shelf(anchor_lp: bool) -> None:
    rs = make_debug_reduced_shelf_support(
        length=0.30,
        width=0.15,
        thickness=0.005,
        youngs=2.0e11,
        n_modes_global=8,
        n_modes_local=0,
        y_rest=0.0,
        to_eigenbasis=True,
    )
    world = XPBDWorld(
        dt=1.0 / 60.0,
        substeps=4,
        iterations=4,
        gravity=(0.0, -9.81, 0.0),
        floor_y=-1.0,
        device="cpu",
    )
    box = world.add_box(
        position=(0.0, 0.05, 0.0),
        half_extents=(0.03, 0.015, 0.03),
        mass=0.1,
    )
    coupler = world.attach_reduced_coupled_xpbd(
        rs,
        tracked_body_indices=[box.index],
        shelf_length=0.30,
        shelf_width=0.15,
        shelf_y_rest=0.0,
        n_grid_x=21,
        n_grid_z=11,
        contact_stiffness=1.0e9,
        anchor_static_lowpass=anchor_lp,
    )

    # Sanity: hook wiring took (compare via __self__ since bound methods
    # are freshly minted on each attribute access).
    assert world.solver.iteration_hook.__self__ is coupler
    assert world.solver.substep_begin_hook.__self__ is coupler
    assert world.solver.substep_end_hook.__self__ is coupler
    # Floor mask flipped for the tracked body.
    floor_mask = world.solver.floor_disabled.numpy()
    assert floor_mask[box.index] == 1

    for _ in range(30):
        world.step()

    # The box should be resting on or near the shelf surface — not below the
    # XPBD floor (-1.0), and not still at the drop height (+0.05 m).
    y = float(world.positions()[box.index, 1])
    assert -0.5 < y < 0.05, f"box ended at y={y} (expected near shelf y=0)"

    # The coupler ran and populated diagnostics.
    assert coupler.last_n_tracked_rows > 0, "no contact rows were ever active"
    assert coupler.last_n_iter_solves > 0
    assert np.isfinite(coupler.last_q_norm)
    assert np.isfinite(coupler.last_dq_norm)
    # Some static sag from the 0.1 kg load — q_s should be non-trivial.
    assert coupler.last_q_s_norm > 0.0
