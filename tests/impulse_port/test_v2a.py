"""V2-A — the velocity band folded into the PER-SUBSTEP loop, run as the SOLE
body↔ring channel, on BOTH solvers (XPBD and AVBD).

`enable_substep_band` wraps the solver's `substep_end_hook` so the band fires
once per substep (not once per step), with `band_owns_excitation=True` (the
legacy `F_q_dyn` modal forcing is gated off) and `anchor_includes_q_d=False`
(the contact anchor carries only the static sag). One momentum-conserving
impulse therefore does BOTH the ring excitation and the body reaction.

These tests are the numpy-reference parity the future device fold (V2-B) is
checked against. They assert, on each solver:
  * the run is finite and the band fires every substep,
  * the band alone still excites the ring (qdot_d peak well above zero),
  * the per-prefix §15 bound holds — the unfloored reservoir stays ≥ 0,
  * the governor never clamps at η = 1 (passivity is free there),
and across the two solvers that the ring excitation is the same order of
magnitude (the band is one solver-agnostic code path; only the body
trajectories — AVBD's position-band launch vs XPBD's gentler q_s — differ).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.dcr.impulse_port import enable_substep_band

_H = 1.0 / 120.0
_SUBSTEPS = 4
_ITERS = 4


def _build_pair():
    """Fresh AVBD shelf + its XPBD mirror, sharing the same modal support."""
    from scenes.reduced_shelf import build_reduced_shelf
    from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd

    h = build_reduced_shelf(device="cpu")
    h.rs.reset_state()
    xh = mirror_to_xpbd(h, h=_H, substeps=_SUBSTEPS, iterations=_ITERS,
                        device="cpu")
    return h, xh


def _run(world, coupler, *, eta, n_steps):
    """Enable the substep band on `world`/`coupler`, step `n_steps`, and return
    (finite, qd_peak, run_stats, positions). Reads run-level accumulators from
    `coupler._band_run` (totals across all substeps)."""
    enable_substep_band(world, coupler, eta=eta)
    qd_peak = 0.0
    for _ in range(n_steps):
        world.step()
        qd = np.asarray(coupler.rs.qdot_d, dtype=np.float64)
        qd_peak = max(qd_peak, float(np.max(np.abs(qd))))
    pos = world._solver.positions() if hasattr(world, "_solver") \
        else world.solver.x.numpy()
    pos = np.asarray(pos, dtype=np.float64)
    run = dict(coupler._band_run)
    finite = bool(np.all(np.isfinite(pos)) and np.isfinite(qd_peak))
    return finite, qd_peak, run, pos


# ----------------------------------------------------------------------
# 1. Sole-channel excitation: band folded into the substep loop excites the
#    ring on BOTH solvers, finite, firing every substep, no η=1 clamp.
# ----------------------------------------------------------------------
@pytest.mark.parametrize("which", ["xpbd", "avbd"])
def test_substep_band_excites_ring(which):
    h, xh = _build_pair()
    if which == "xpbd":
        world, coupler = xh.world, xh.coupler
    else:
        world, coupler = h.world, h.world.reduced_coupled_coupler

    finite, qd_peak, run, pos = _run(world, coupler, eta=1.0, n_steps=60)

    assert finite, f"{which}: non-finite state"
    # The band is the SOLE excitation (F_q_dyn gated off) yet the ring rings:
    assert qd_peak > 0.1, f"{which}: ring not excited, qd_peak={qd_peak:.3e}"
    # It fires per substep, not per step:
    assert run["substeps"] == 60 * _SUBSTEPS, run["substeps"]
    assert run["impulses"] > 0, f"{which}: no impulses"
    # At η = 1 the net draw D(1) < 0, so the governor provably never clamps:
    assert run["clamps"] == 0, f"{which}: η=1 clamped {run['clamps']}×"
    # Per-prefix §15 bound (η=1): unfloored reservoir never goes negative.
    assert run["reservoir_min"] >= -1e-9, f"{which}: R_min={run['reservoir_min']:.3e}"


# ----------------------------------------------------------------------
# 2. Per-prefix §15 bound with the governor ACTIVE (η < 1): the reservoir
#    stays ≥ 0 on both solvers (so Σ ΔE_modal ≤ η Σ L at every prefix).
# ----------------------------------------------------------------------
@pytest.mark.parametrize("which", ["xpbd", "avbd"])
def test_substep_band_per_prefix_bound(which):
    h, xh = _build_pair()
    if which == "xpbd":
        world, coupler = xh.world, xh.coupler
    else:
        world, coupler = h.world, h.world.reduced_coupled_coupler

    finite, qd_peak, run, pos = _run(world, coupler, eta=0.3, n_steps=80)

    assert finite, f"{which}: non-finite state"
    # The reservoir IS the global per-prefix margin η Σ L − Σ ΔE_modal; it must
    # never dip below zero (governor active here, so clamps ≥ 0 are allowed).
    assert run["reservoir_min"] >= -1e-9, f"{which}: R_min={run['reservoir_min']:.3e}"


# ----------------------------------------------------------------------
# 3. Cross-solver parity: the band is one solver-agnostic code path, so the
#    ring excitation it produces is the same order on XPBD and AVBD (the body
#    trajectories differ — that is the position band, not this one).
# ----------------------------------------------------------------------
def test_substep_band_cross_solver_parity():
    h, xh = _build_pair()
    _, qd_x, run_x, _ = _run(xh.world, xh.coupler, eta=1.0, n_steps=60)
    h2, xh2 = _build_pair()
    _, qd_a, run_a, _ = _run(h2.world, h2.world.reduced_coupled_coupler,
                             eta=1.0, n_steps=60)

    assert qd_x > 0.1 and qd_a > 0.1, (qd_x, qd_a)
    ratio = qd_x / qd_a
    # Same order of magnitude — generous band (trajectories differ), but a gross
    # divergence (one solver dead / one blown up) would break it.
    assert 0.25 <= ratio <= 4.0, f"qd_peak ratio xpbd/avbd = {ratio:.3f}"
    # Both fire on every substep and neither clamps at η = 1.
    assert run_x["clamps"] == 0 and run_a["clamps"] == 0
    assert run_x["impulses"] > 0 and run_a["impulses"] > 0
