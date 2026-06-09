"""GPU-residency parity tests for ReducedCoupledAVBDCoupler.

The coupler's per-AVBD-iteration Schur solve was ported from a numpy host hook
(forcing a device→host→device round-trip every iteration) to on-device warp
kernels (`dcr/avbd/reduced_coupled_kernels.py`). This test pins that the device
path is numerically faithful to the numpy reference and physically equivalent.

Both worlds run on the SAME device (cuda:0) so the only variable is the hook
path (`coupler.device_resident`), not the warp backend. The device kernels
compute in float64 internally (matching the numpy reference, whose inputs are
the same float32 solver values), so over a few steps the two trajectories agree
to round-off. Over longer runs the sensitive impact/ring-down dynamics amplify
that round-off (different summation order → ~1e-14/step → chaotic growth), so we
assert TIGHT parity early and BOUNDED ABSOLUTE drift + physical equivalence
(drift-fix steady state, passivity) over the full run — not tight long-run
parity, which no faithful reimplementation could provide.

CLAUDE.md rule 6: the numpy path is the reference and stays the default on CPU.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _cuda_or_skip() -> str:
    wp = pytest.importorskip("warp")
    wp.init()
    if wp.get_cuda_device_count() < 1:
        pytest.skip("no CUDA device for GPU-residency parity test")
    return "cuda:0"


def _run(device: str, device_resident: bool, n_steps: int) -> dict:
    from scenes.reduced_support_shelf import build_reduced_support_shelf
    handle = build_reduced_support_shelf(
        h=1.0 / 120.0, device=device, iterations=4, avbd_substeps=4,
        overlay_enabled=False, reduced_support_enabled=True,
        coupled_avbd=True, to_eigenbasis=True)
    w = handle.world
    c = w.reduced_coupled_coupler
    # Override the attach-time auto-default so we can A/B the two hook paths
    # on the same device.
    c.device_resident = device_resident
    for _ in range(n_steps):
        w.step()
    s = w._solver
    return {
        "coupler": c,
        "q_s": c.rs.q_s.copy(),
        "q_d": c.rs.q_d.copy(),
        "qdot_d": c.rs.qdot_d.copy(),
        "x": s.x.numpy().copy(),
        "q": s.q.numpy().copy(),
        "anchor": s.c_world_anchor.numpy().copy(),
        "probe_y": np.array(
            [float(s.x.numpy()[b, 1]) for b in c.tracked_body_indices]),
    }


def test_device_path_active_on_cuda():
    """The device-resident path actually engages (flag + graph capture)."""
    dev = _cuda_or_skip()
    r = _run(dev, True, 30)
    c = r["coupler"]
    assert c.device_resident is True
    assert c._device_ready is True
    # solver dropped the per-hook host drains and captured the iter loop.
    assert c._dev_n_b > 0
    # all device results finite
    for k in ("q_s", "q_d", "qdot_d", "x", "q", "anchor"):
        assert np.all(np.isfinite(r[k])), f"{k} has non-finite entries"


def test_tight_parity_early():
    """Before chaotic amplification, device == numpy reference to round-off."""
    dev = _cuda_or_skip()
    ref = _run(dev, False, 8)
    gpu = _run(dev, True, 8)
    # q_s is the physically-meaningful static sag; pin it tightest.
    np.testing.assert_allclose(gpu["q_s"], ref["q_s"], rtol=1e-6, atol=1e-12)
    np.testing.assert_allclose(gpu["x"], ref["x"], rtol=1e-5, atol=1e-7)
    np.testing.assert_allclose(gpu["q"], ref["q"], rtol=1e-5, atol=1e-7)
    np.testing.assert_allclose(
        gpu["anchor"], ref["anchor"], rtol=1e-5, atol=1e-9)


def test_bounded_drift_and_physical_equivalence():
    """Over a full impact + ring-down run, absolute drift stays tiny and the
    drift-fix steady state matches the reference (probe settle, q_s, passivity).
    """
    dev = _cuda_or_skip()
    N = 200
    ref = _run(dev, False, N)
    gpu = _run(dev, True, N)

    # Absolute drift bounds (physical scales: q in metres, x in metres). The
    # sensitive ring-down amplifies round-off, but only to nm/1e-8 levels.
    assert np.max(np.abs(gpu["x"] - ref["x"])) < 1e-5
    assert np.max(np.abs(gpu["q"] - ref["q"])) < 1e-4
    assert np.max(np.abs(gpu["q_s"] - ref["q_s"])) < 1e-7
    assert np.max(np.abs(gpu["q_d"] - ref["q_d"])) < 1e-5

    # Drift-fix property: probes settle to the same height (no ratchet drift).
    assert np.max(np.abs(gpu["probe_y"] - ref["probe_y"])) < 1e-6

    # Steady-state static sag matches to several sig figs.
    rel_qs = (np.linalg.norm(gpu["q_s"] - ref["q_s"])
              / max(np.linalg.norm(ref["q_s"]), 1e-30))
    assert rel_qs < 1e-3

    # Passivity violation count (logged, not enforced) is comparable. This is a
    # DISCRETE count over ~800 substeps; near the threshold a sub-1e-7 CPU↔GPU
    # q_d divergence (the same chaotic round-off the bounded-drift asserts above
    # tolerate) flips several counts, so compare order-of-magnitude, not exactly.
    # (The anchor static low-pass REDUCES the absolute count — q_d is more
    # passive — but its lower count is proportionally more count-sensitive.)
    cr, cg = ref["coupler"], gpu["coupler"]
    vr, vg = cr.last_passivity_violations, cg.last_passivity_violations
    assert abs(vr - vg) <= max(12, int(0.25 * max(vr, vg))), (vr, vg)
