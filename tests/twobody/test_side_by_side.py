"""Acceptance: a dropped impactor rings the slab and KICKS the resting cubes.

Demonstrates that the monolithic implicit penalty contact transfers slab→cube
momentum (the "velocity band" effect) with no explicit velocity impulse:

  1. before impact the bystander cubes are ~quiet;
  2. after impact the center (mid-span) bystander is kicked by ≥100×;
  3. the whole scene settles (‖v‖ → 0), energy monotone non-increasing.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.twobody.multibody import build_side_by_side

_H = 5.0e-4
_STEPS = 5000


@pytest.mark.parametrize("kind", ["abd", "fem"])
def test_bystander_kick(kind):
    sysm, info = build_side_by_side(kind, n_rest=3, impactor_drop=0.35,
                                    impactor_rho=2500.0, damping=0.6, k_c=4.0e5)
    imp = info["impactor_body"]
    mid = info["rest_bodies"][len(info["rest_bodies"]) // 2]
    st = sysm.initial_state()

    ke_mid, imp_y, totals = [], [], [sysm.energy_breakdown(st)["total"]]
    max_pen = 0.0
    for _ in range(_STEPS):
        st = sysm.step(st, _H)
        e = sysm.energy_breakdown(st)
        ke_mid.append(e[f"KE_body{mid}"])
        b = sysm.bodies[imp]
        z = sysm.body_z(st, imp)
        imp_y.append(z[1] if b.ndof == 12 else b.corner_rest[0, 1] + 0.05 + z[1])
        totals.append(e["total"])
        max_pen = max(max_pen, e["max_penetration"])
    ke_mid = np.array(ke_mid)
    imp_y = np.array(imp_y)
    totals = np.array(totals)

    # impact step = impactor first reaches slab level
    it = int(np.argmax(imp_y < 0.085))
    quiet = ke_mid[max(0, it - 60):it].max()          # 30 ms quiet window pre-impact
    kick = ke_mid[it:it + 400].max()                  # peak just after impact

    assert quiet < 1.0e-3, f"bystander not quiet before impact: {quiet}"
    assert kick > 100.0 * quiet, f"weak kick: {kick} vs quiet {quiet}"
    assert np.linalg.norm(st.v) < 1.0e-2               # settles
    assert np.diff(totals).max() < 1.0e-5             # passivity
    assert max_pen < 3.0e-3
