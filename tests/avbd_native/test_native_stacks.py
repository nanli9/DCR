"""M1.5 — stacks ride the ring AND stay intact, native path (no coupler).

The whole point of unifying the modal q with box-box in one solve: a stacked
pile must both ride the ringing support (its grounded contacts load/feel q) AND
hold together (box-box). Here the truck's 4-high lumber stack stays intact while
the support rings under the dropped impactor. Foundation: two_band_coupling.html.
"""
from __future__ import annotations

import numpy as np
import pytest

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge


def _avbd_idx(h, name: str) -> int:
    b = next(b for b in h.bodies if b.name == name)
    return int(h.world._descs[b.dcr_idx].avbd_body.index)


def _max_tilt_deg(s, idxs) -> float:
    Q = s.orientations()
    return max(np.degrees(2.0 * np.arccos(np.clip(abs(Q[i][3]), 0.0, 1.0)))
               for i in idxs)


def test_truck_lumber_stack_rides_ring_and_holds():
    """The 4-high lumber stack rides the ring AND stays upright. Measured by
    TILT over a long (500-step) run — the real "stays intact" criterion. (A
    vertical-centre gap proxy is misleading: a rocking/toppling stack reads as
    "penetration" without true face overlap.)"""
    h = build_reduced_truck(
        device="cpu", solver="native",
        impactor_drop_height=0.06, iterations=8, avbd_substeps=4)
    s = h.world._solver
    lumber = [_avbd_idx(h, f"lumber_{i}") for i in range(4)]
    peak_KE = 0.0
    for _ in range(500):
        h.world.step()
        peak_KE = max(peak_KE, s.last_modal_KE)
        assert np.all(np.isfinite(s.positions())), "no NaN"
    # Rides the ring: the support is excited two-way.
    assert peak_KE > 1e-9, f"support should ring under the drop ({peak_KE:.2e})"
    # Stays intact: the stack does not topple (un-relaxed block-GS over-deflects
    # q and topples it to ~36°; the conservative relaxation holds it upright).
    tilt = _max_tilt_deg(s, lumber)
    assert tilt < 5.0, f"lumber stack toppled ({tilt:.1f}° tilt)"
    z_drift = max(abs(float(s.positions()[i][2])) for i in lumber)
    assert z_drift < 0.05, f"lumber stack slid apart (z drift {z_drift:.3f} m)"


def test_ledge_runs_native_and_rings():
    h = build_reduced_ledge(
        device="cpu", solver="native",
        impactor_drop_height=0.06, iterations=8, avbd_substeps=4)
    s = h.world._solver
    peak_KE = 0.0
    for _ in range(200):
        h.world.step()
        peak_KE = max(peak_KE, s.last_modal_KE)
    P = s.positions()
    assert np.all(np.isfinite(P)), "no NaN over the run"
    assert peak_KE > 1e-9, "ledge support should ring under the boulder"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
