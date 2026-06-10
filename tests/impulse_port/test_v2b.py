"""V2-B — the velocity band run FULLY ON-DEVICE (CUDA-resident), parity-tested
against the V2-A numpy reference, on BOTH solvers.

`enable_device_band` folds the band into the coupler's own device `substep_end`
as a single warp kernel (`k_velocity_band`), so the body↔ring exchange never
leaves the GPU mid-step. `enable_substep_band` (V2-A) runs the SAME band on the
numpy host, round-tripping device→host→device every substep. Both worlds run on
cuda:0, so the only variable is the band's compute path (device kernel vs numpy)
plus the already-parity-tested position band.

The device kernel computes in float64 internally (matching the numpy reference,
whose inputs are the same float32 solver values), so the two agree to round-off
early. Over a longer run the sensitive impact/ring-down dynamics amplify that
round-off (chaotic growth) — AND, with an ACTIVE governor (η<1), the reservoir's
clamp decisions are themselves round-off-sensitive — so we assert TIGHT parity
early at the SHIP config (η=1, where the governor provably never clamps) and
BOUNDED drift + physical equivalence + the §15 invariant over the full run.

CLAUDE.md rule 6: the numpy band is the reference; this pins the device port.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_H = 1.0 / 120.0


def _cuda_or_skip() -> str:
    wp = pytest.importorskip("warp")
    wp.init()
    if wp.get_cuda_device_count() < 1:
        pytest.skip("no CUDA device for V2-B device-band parity test")
    return "cuda:0"


def _build(which: str, device: str):
    from scenes.reduced_shelf import build_reduced_shelf
    h = build_reduced_shelf(device=device)
    h.rs.reset_state()
    if which == "avbd":
        return h.world, h.world.reduced_coupled_coupler
    from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd
    xh = mirror_to_xpbd(h, h=_H, substeps=4, iterations=4, device=device)
    return xh.world, xh.coupler


def _solver(world):
    return getattr(world, "_solver", None) or world.solver


def _run(which: str, mode: str, n: int, eta: float) -> dict:
    from dcr.dcr.impulse_port import enable_device_band, enable_substep_band
    world, c = _build(which, "cuda:0")
    if mode == "dev":
        enable_device_band(world, c, eta=eta)
    else:
        enable_substep_band(world, c, eta=eta)
    qd_peak = 0.0
    res_min = np.inf
    for _ in range(n):
        world.step()
        qd_peak = max(qd_peak, float(np.max(np.abs(np.asarray(c.rs.qdot_d)))))
        res_min = min(res_min, float(getattr(c, "_modal_reservoir", 0.0)))
    s = _solver(world)
    return {
        "coupler": c,
        "q_s": c.rs.q_s.copy(),
        "qdot_d": c.rs.qdot_d.copy(),
        "x": s.x.numpy().copy(),
        "q": s.q.numpy().copy(),
        "qd_peak": qd_peak,
        "res": float(getattr(c, "_modal_reservoir", 0.0)),
        "res_min": res_min,
    }


# ----------------------------------------------------------------------
# 1. The device-resident band engages on CUDA, is finite, and — as the SOLE
#    body↔ring channel — still excites the ring (band-only excitation) while
#    holding the per-prefix §15 bound (reservoir ≥ 0).
# ----------------------------------------------------------------------
@pytest.mark.parametrize("which", ["avbd", "xpbd"])
def test_device_band_active_and_excites(which):
    _cuda_or_skip()
    g = _run(which, "dev", 40, eta=1.0)
    c = g["coupler"]
    assert c.device_resident is True
    assert c._device_ready is True
    for k in ("q_s", "qdot_d", "x", "q"):
        assert np.all(np.isfinite(g[k])), f"{which}: {k} non-finite"
    assert g["qd_peak"] > 0.1, f"{which}: ring not excited ({g['qd_peak']:.3e})"
    # η=1: D(1) < 0, governor never clamps → reservoir only grows, never < 0.
    assert g["res_min"] >= -1e-9, f"{which}: res_min={g['res_min']:.3e}"


# ----------------------------------------------------------------------
# 2. Tight early parity at the SHIP config (η=1): device band == numpy band
#    to solver round-off before chaotic amplification.
# ----------------------------------------------------------------------
@pytest.mark.parametrize("which", ["avbd", "xpbd"])
def test_tight_parity_early(which):
    _cuda_or_skip()
    ref = _run(which, "np", 8, eta=1.0)
    gpu = _run(which, "dev", 8, eta=1.0)
    # q_s (the physically-meaningful static sag) tightest; x / q̇_d to round-off.
    np.testing.assert_allclose(gpu["q_s"], ref["q_s"], rtol=1e-5, atol=1e-7)
    np.testing.assert_allclose(gpu["x"], ref["x"], rtol=1e-4, atol=1e-6)
    np.testing.assert_allclose(
        gpu["qdot_d"], ref["qdot_d"], rtol=1e-4, atol=1e-5)


# ----------------------------------------------------------------------
# 3. Per-prefix §15 bound with the governor ACTIVE (η<1), on device: the
#    reservoir never goes negative (drains to machine-zero but not below).
# ----------------------------------------------------------------------
@pytest.mark.parametrize("which", ["avbd", "xpbd"])
def test_per_prefix_bound_device(which):
    _cuda_or_skip()
    g = _run(which, "dev", 80, eta=0.3)
    assert np.all(np.isfinite(g["x"])), f"{which}: non-finite"
    assert g["res_min"] >= -1e-9, f"{which}: res_min={g['res_min']:.3e}"


# ----------------------------------------------------------------------
# 4. Bounded drift + physical equivalence over a full impact + ring-down run
#    (η=1). Round-off amplifies in the chaotic ring-down, so we bound the
#    absolute drift and pin the static sag (the physical coupling).
# ----------------------------------------------------------------------
@pytest.mark.parametrize("which", ["avbd", "xpbd"])
def test_bounded_drift_and_physical_equivalence(which):
    _cuda_or_skip()
    N = 60
    ref = _run(which, "np", N, eta=1.0)
    gpu = _run(which, "dev", N, eta=1.0)
    assert np.all(np.isfinite(gpu["x"]))
    # The band couples the NORMAL (vertical, ŷ) axis — bound the vertical drift
    # (mm-scale) despite the chaotic ring-down. The tangential DOF is a free
    # frictionless slide on XPBD (floor_disabled + normal-only contact rows), so
    # its lateral position legitimately diverges on round-off and is not pinned.
    dy = np.max(np.abs(gpu["x"][:, 1] - ref["x"][:, 1]))
    assert dy < 5e-3, f"{which}: vertical drift {dy:.3e}"
    # The static sag q_s stays BOUNDED in the same regime (no blow-up / ratchet)
    # — tight q_s parity is pinned EARLY (test 2, N=8); by N=60 the chaotic
    # ring-down (and on XPBD the frictionless lateral slide that shifts the
    # contact corners) has diverged the transient, but q_s does not run away.
    assert np.linalg.norm(gpu["q_s"]) < 1e-2, which
    assert np.max(np.abs(gpu["q_s"] - ref["q_s"])) < 5e-3, which
    # Both keep the §15 bank non-negative.
    assert gpu["res_min"] >= -1e-9 and ref["res_min"] >= -1e-9
