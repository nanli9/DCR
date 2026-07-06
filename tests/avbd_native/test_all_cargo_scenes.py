"""All-cargo production scenes (§N2 generalization): every body in
truck / ledge / shelf / dinner is a box-shaped modal cargo on the box-box
modal contact network — the `reduced_cargo_network` recipe applied to the
production scenes. Smoke acceptance: builds, registers every body, steps
stably, and the passivity ledger machinery sees the augmented state."""
from __future__ import annotations

import numpy as np
import pytest

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table

FAST = dict(iterations=4, avbd_substeps=2, cargo_material="fem_rigid",
            cargo_all=True, cargo_n_elastic=2)

BUILDERS = {
    "truck": build_reduced_truck,
    "ledge": build_reduced_ledge,
    "shelf": build_reduced_shelf,
    "dinner": build_reduced_dinner_table,
}


@pytest.mark.parametrize("scene", sorted(BUILDERS))
def test_all_cargo_scene_builds_and_steps(scene):
    handle = BUILDERS[scene](**FAST)
    sol = handle.world._solver

    # every dynamic body got a cargo block with its REAL box shape
    assert len(handle.cargo_map) == len(handle.bodies)
    for b in handle.bodies:
        body, avbd_idx = handle.cargo_map[b.dcr_idx]
        assert body.half_extents == tuple(float(v) for v in b.half_extents)
        assert body.k == 2
        assert avbd_idx in sol._cargo_bodies

    # the box-box modal network is on (AVBD-native)
    assert bool(sol._modal_contact_network)

    # augmented modal vector = support r + Σ k_i
    n_cargo_modes = sum(body.k for body, _ in handle.cargo_map.values())
    assert sol._n_modes_tot == handle.rs.q.shape[0] + n_cargo_modes

    for _ in range(30):
        handle.world.step()

    P = sol.positions()
    assert np.all(np.isfinite(P))
    # no body fell through the support or blew away
    assert float(np.abs(P[:, 1]).max()) < 5.0
    assert np.all(np.isfinite(sol.modal_q))
    for b in handle.bodies:
        _, avbd_idx = handle.cargo_map[b.dcr_idx]
        a = sol.cargo_a(avbd_idx)
        assert a.shape == (2,)
        assert np.all(np.isfinite(a))


def test_dinner_bodies_ring_after_pot_impact():
    """The network must DRIVE cargo modes: after the pot impact, at least the
    plates (grounded, near the impact) carry non-zero modal amplitude."""
    handle = build_reduced_dinner_table(**FAST, pot_drop_height=0.3)
    sol = handle.world._solver
    for _ in range(90):                      # let the pot land and ring
        handle.world.step()
    amps = {}
    for b in handle.bodies:
        _, avbd_idx = handle.cargo_map[b.dcr_idx]
        amps[b.name] = float(np.linalg.norm(sol.cargo_a(avbd_idx)))
    assert np.all(np.isfinite(list(amps.values())))
    # the pot itself must ring from its own impact
    assert amps["pot"] > 0.0
    # at least one resting body is excited through the support/network path
    others = [v for k, v in amps.items() if k != "pot"]
    assert max(others) > 0.0
