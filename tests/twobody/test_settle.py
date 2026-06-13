"""Acceptance: two-way reduced coupling settles to the static-sag equilibrium.

Validates the claim in `docs/two_way_modal_coupling_investigation.md` §3 for both
cube models (ABD affine + FEM modal), coupled to a FEM-modal slab:

  1. the system comes to rest (‖ż‖ → 0);
  2. total mechanical energy is monotone non-increasing (discrete passivity);
  3. the dynamic rest state matches an independent static solve (the static sag);
  4. the cube rests at the geometrically correct height on the slab.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.twobody import build_abd_cube, build_fem_cube, build_fem_slab
from dcr.twobody.coupled_step import ContactPair, TwoBodySystem

_H = 1.0e-3
_N_STEPS = 1500
_SLAB_TOP_Y = 0.025   # slab half-height (height=0.05 centered at origin)
_CUBE_HALF = 0.05


def _run(cube, slab):
    pairs = [ContactPair(i, i) for i in range(4)]
    sys = TwoBodySystem(cube=cube, slab=slab, pairs=pairs, k_c=2.0e5)
    st = sys.initial_state()
    totals = [sys.energy(st)["total"]]
    max_pen = 0.0
    for _ in range(_N_STEPS):
        st = sys.step(st, _H)
        e = sys.energy(st)
        totals.append(e["total"])
        max_pen = max(max_pen, e["max_penetration"])
    return sys, st, np.array(totals), max_pen


@pytest.mark.parametrize("builder", [build_abd_cube, build_fem_cube])
def test_two_body_settles_to_static_sag(builder):
    cube = builder()
    slab = build_fem_slab()
    sys, st, totals, max_pen = _run(cube, slab)

    # (1) comes to rest
    vmag = np.linalg.norm(np.concatenate([st.vc, st.vs]))
    assert vmag < 1.0e-3, f"did not settle: ‖v‖={vmag}"

    # (2) monotone non-increasing energy (discrete passivity); allow a tiny
    # per-step Newton-residual slack.
    incr = np.diff(totals)
    assert incr.max() < 1.0e-6, f"energy increased by {incr.max()} on some step"

    # (3) dynamic rest == independent static solve
    stat = sys.static_solve()
    assert np.allclose(st.zc, stat.zc, atol=1.0e-4)
    assert np.allclose(st.zs, stat.zs, atol=1.0e-4)

    # (4) cube rests at the right height (centroid = slab_top + half)
    expected_centroid_y = _SLAB_TOP_Y + _CUBE_HALF
    if cube.ndof == 12:           # ABD: q[1] is world centroid y
        centroid_y = st.zc[1]
    else:                          # FEM: carrier displacement from drop height
        centroid_y = 0.12 + st.zc[1]
    assert abs(centroid_y - expected_centroid_y) < 2.0e-3, (
        f"cube settled at y={centroid_y}, expected {expected_centroid_y}")

    # contact stayed shallow (penalty is soft but bounded)
    assert max_pen < 2.0e-3
