"""Regression: a spinning cargo cube must not tunnel through the modal support.

Bug (found 2026-06-23): the viser drops the cargo cube spinning (`--spin 4.0`).
The XPBD reduced-modal support only constrained the cube's *original-bottom* 4
corners; when the cube tumbled ~180° during the fall+impact, those corners ended
up on top (resting at the surface) while the now-bottom corners were
unconstrained, so the cube passed straight through and hung one body-height below
the slab (top flush with the surface). Fix: `enable_reduced_modal_support`
(XPBD branch) now registers all 8 corners — a corner above the live surface is
inactive (unilateral C ≥ 0), so the support catches whatever face lands.

AVBD did not exhibit the tunnel here (its AL contact arrested the spin before a
full flip), but the assertion covers both solvers.
"""
from __future__ import annotations

import numpy as np
import pytest

from scenes.reduced_fem_rigid_cargo import build_cargo_scene


@pytest.mark.parametrize("solver", ["xpbd", "avbd"])
@pytest.mark.parametrize("spin", [0.0, 4.0])
def test_spinning_cargo_does_not_tunnel(solver, spin):
    """Cube dropped (1 m) with spin must settle ON the support (bottom ≈ y_rest),
    not hang below it. Pre-fix, xpbd+spin=4 sank to bottom ≈ y_rest − 0.1."""
    h = build_cargo_scene("fem_rigid", solver=solver, device="cpu",
                          drop_height=1.0, iterations=16, avbd_substeps=4,
                          spin=spin)
    s = h.world._solver
    half = h.cube.half_extent
    for _ in range(400):
        h.world.step()
    assert np.all(np.isfinite(s.positions())), (solver, spin, "NaN")
    bottom = float(s.positions()[h.avbd_idx][1]) - half
    # slab top is support_top = 0.0; resting bottom must be ~0, never a full
    # body-height (0.1) below.
    assert bottom > -0.02, (
        f"{solver} spin={spin}: cube tunneled (bottom={bottom:.4f}, "
        f"expected ≈0 on the support)")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
