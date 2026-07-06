"""Scene GT smoke (quick settings): the all-FEM GT harness must run the
production scenes without bodies falling through the support, blowing up, or
losing the deflection signal. Shelf (fast) + ledge (pillar stack exercises
FEM-body-on-FEM-body contact). The full five-scene sweep is the CLI:
`python -m benchmarks.fem_gt.run_gt --scene all --quick`."""
from __future__ import annotations

import numpy as np
import pytest

from benchmarks.fem_gt.common import SUPPORTS, run_scene_gt
from benchmarks.fem_gt.run_gt import _build_handle

QUICK = dict(h_fine=1e-4, t_settle=0.15, t_run=0.3, record_every=50)


@pytest.mark.parametrize("scene", ["shelf", "ledge"])
def test_scene_gt_quick(scene, tmp_path):
    handle, imp_name = _build_handle(scene)
    rec = run_scene_gt(scene, handle, imp_name, out_dir=tmp_path, **QUICK)

    # outputs written
    assert (tmp_path / f"{scene}_gt.csv").exists()
    assert (tmp_path / f"{scene}_gt.json").exists()

    # nothing fell to the safety floor; every body finite and above the slab
    keys = {k for frame in rec["ledger"] for k in frame}
    assert not any(low == "floor" for _, low in keys), keys
    spec = SUPPORTS[scene]
    for name, ys in rec["com_y"].items():
        assert np.all(np.isfinite(ys))
        if name != "support":
            assert ys[-1] > spec.top - 0.05, (name, ys[-1])

    # the impact left a deflection signal on the support, and it stayed sane
    mid = np.asarray(rec["probes"]["support_mid_uy"])
    assert np.all(np.isfinite(mid))
    assert np.abs(mid).max() > 1e-9          # the ring is visible
    assert np.abs(mid).max() < 0.01          # and physical (< 1 cm)


def test_ledge_stack_carries_weight():
    """The pillar→pedestal→support chain must show up in the ledger with the
    pedestal joint carrying more than any single pillar joint."""
    handle, imp_name = _build_handle("ledge")
    rec = run_scene_gt("ledge", handle, imp_name,
                       out_dir=None, **QUICK)
    # average over the run: after the boulder lands the pillars ROCK (the
    # scene's strong-coupling topple), so a single frame can catch lift-off

    def mean_force(pred):
        vals = [v for frame in rec["ledger"] for (a, b), v in frame.items()
                if pred(a, b)]
        return float(np.mean(vals)) if vals else 0.0

    ped = mean_force(lambda a, b: a == "pedestal" and b == "support")
    pil = mean_force(lambda a, b: a.startswith("pillar") and b == "pedestal")
    assert ped > 0.0
    assert pil > 0.0                          # pillars ride the pedestal
    assert ped > pil                          # pedestal carries the stack
