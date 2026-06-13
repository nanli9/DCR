"""Acceptance: stacked cubes on a FEM-modal slab settle to the static sag.

Same four-way verification as the single-cube test, generalized to an N-body
stack (slab ← cube0 ← cube1 ← ...), for both cube models:
  1. settles (‖v‖ → 0);
  2. passivity (total energy monotone non-increasing);
  3. equilibrium (static residual → 0 at rest — basin-free, unlike static_solve);
  4. geometry (each cube rests near slab_top + (2i+1)·half).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.twobody.multibody import build_stack

_H = 5.0e-4
_STEPS = 5000
_SLAB_TOP = 0.025
_HALF = 0.05


def _centroid_y(sys, state, body_idx):
    z = sys.body_z(state, body_idx)
    b = sys.bodies[body_idx]
    if b.ndof == 12:
        return float(z[1])
    return float(b.corner_rest[0, 1] + _HALF + z[1])


@pytest.mark.parametrize("kind", ["abd", "fem"])
@pytest.mark.parametrize("n_cubes", [2, 3])
def test_stack_settles(kind, n_cubes):
    sys = build_stack(kind, n_cubes, damping=0.6, k_c=1.0e5)
    st = sys.initial_state()
    totals = [sys.energy_breakdown(st)["total"]]
    max_pen = 0.0
    for _ in range(_STEPS):
        st = sys.step(st, _H)
        e = sys.energy_breakdown(st)
        totals.append(e["total"])
        max_pen = max(max_pen, e["max_penetration"])
    totals = np.array(totals)

    # (1) settles
    assert np.linalg.norm(st.v) < 1.0e-3
    # (2) monotone non-increasing energy
    assert np.diff(totals).max() < 1.0e-5
    # (3) static equilibrium at rest
    assert sys.static_residual(st) < 1.0e-5
    # (4) geometry: every cube near its rigid rest height (slab sags ≲ 1 mm)
    for i in range(n_cubes):
        expected = _SLAB_TOP + (2 * i + 1) * _HALF
        assert abs(_centroid_y(sys, st, i + 1) - expected) < 2.0e-3
    # contact stayed shallow
    assert max_pen < 2.0e-3
