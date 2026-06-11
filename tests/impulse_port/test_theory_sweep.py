"""Fast suite version of the impulse-port theory sweep (proposal §3.2-§3.4, §15).

The full sweep (solver × η × iters, with plot) lives in
`scripts/sweep_impulse_port_theory.py`. This is the CI-fast subset: XPBD only,
a small η grid, fewer steps — but it asserts the SAME theoretical invariants so
a regression in the governor or the friction pass fails the suite:

  T1  per-prefix §15 bound: reservoir R = η·ΣL − Σ ΔE_modal stays ≥ 0
  T2  η = 1 never clamps (safety bound, not a dial)
  T3  governor engages at η < 1 (clamps appear)
  T4  friction settles the body (lateral v, yaw ω_y → ~0)
  T5  friction is orthogonal to the ring (qd_peak with ≈ without)
"""
from __future__ import annotations

import numpy as np
import pytest

from scripts.sweep_impulse_port_theory import run_case

_ETAS = [0.25, 0.5, 1.0]
_ITERS = 4
# Lower η leaves more rigid KE for friction to dissipate, so the body settles
# SLOWER (η=0.25: lat 0.13 @300 → 2.4e-5 @480 → 2.5e-6 @720). It still settles —
# friction guarantees it at every η — but the T4 window must be long enough.
_N = 540


@pytest.fixture(scope="module")
def cases():
    """One sweep, shared across the assertion tests (each case is ~1s)."""
    out = {}
    out["nofric"] = run_case("xpbd", _ITERS, 1.0, False, _N)["qd_peak"]
    for eta in _ETAS:
        out[eta] = run_case("xpbd", _ITERS, eta, True, _N)
    return out


@pytest.mark.parametrize("eta", _ETAS)
def test_T1_per_prefix_bound(cases, eta):
    assert cases[eta]["res_min"] >= -1e-9, cases[eta]["res_min"]


def test_T2_no_clamp_at_eta1(cases):
    assert cases[1.0]["clamps"] == 0, cases[1.0]["clamps"]


def test_T3_governor_engages_below_eta1(cases):
    assert any(cases[e]["clamps"] > 0 for e in _ETAS if e < 1.0), \
        {e: cases[e]["clamps"] for e in _ETAS}


@pytest.mark.parametrize("eta", _ETAS)
def test_T4_body_settles(cases, eta):
    r = cases[eta]
    assert r["lat"] < 1e-3, r["lat"]
    assert r["wy"] < 1e-2, r["wy"]


@pytest.mark.parametrize("eta", _ETAS)
def test_T5_ring_preserved_by_friction(cases, eta):
    ratio = cases[eta]["qd_peak"] / max(cases["nofric"], 1e-9)
    assert 0.7 <= ratio <= 1.3, ratio
