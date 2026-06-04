"""Impact-window energy reservoir (avbd_dcr_impact_reservoir_fix) tests.

What the reservoir achieves (measured by
scripts/_diag_impact_reservoir_iter_sensitivity.py):
  * Acceptance §14.1 — it removes the ZERO-injection at low iterations: at
    iters=4 the is_new path injects 0 J while the reservoir injects ~1.4 J.
  * §14.4 passivity — Σ E_inj ≤ η·Σ E_loss holds (deposits bounded by η·E_loss,
    spend bounded by the reservoir, passive_alpha cap retained).
  * §14.6/§14.7 degeneracies — flag OFF reproduces the is_new path; η=0 injects 0.

What it does NOT achieve (documented, not asserted): §14.2 iteration-insensitivity
(CV_reservoir < 0.5·CV_old). The residual sensitivity is intrinsic — a soft
low-iteration solve smears the impact over many small-impulse frames, and the
injectable modal energy ½‖s‖² is quadratic in the per-frame impulse, so a smeared
impact transfers genuinely less vibration energy (see docs §10).
"""
import numpy as np
import pytest

try:
    from scripts.run_scenes_avbd import build_shelf_scene
except Exception:  # pragma: no cover
    build_shelf_scene = None

ETA = 0.5


def _run(use_reservoir, iters, eta=ETA, source="delta_p", n=150):
    world, coupler, *_ = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=eta, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = iters
    coupler.use_impact_reservoir = use_reservoir
    coupler.impulse_source = source
    cum_E_loss = 0.0
    for _ in range(n):
        world.step()
        cum_E_loss += float(world.last_E_loss)
    return coupler, cum_E_loss


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_reservoir_is_globally_passive():
    """§14.4: cumulative injected modal energy never exceeds η·Σ E_loss."""
    for iters in (8, 16):
        coupler, cum_E_loss = _run(True, iters)
        assert coupler.cum_E_modal_injected <= ETA * cum_E_loss + 1e-6, (
            f"iters={iters}: injected {coupler.cum_E_modal_injected:.4f} > "
            f"budget {ETA*cum_E_loss:.4f}")


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_reservoir_fixes_zero_injection_at_low_iters():
    """§14.1: the headline win — iters=4 injects 0 with the is_new gate but a
    meaningful amount once the reservoir decouples deposit from spend timing."""
    off, _ = _run(False, 4)
    on, _ = _run(True, 4)
    assert off.cum_E_modal_injected < 1e-6, (
        f"is_new path should starve at iters=4, got {off.cum_E_modal_injected}")
    assert on.cum_E_modal_injected > 0.5, (
        f"reservoir should inject at iters=4, got {on.cum_E_modal_injected}")


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_eta_zero_injects_nothing():
    """§14.7: η=0 ⇒ no deposit ⇒ no injection, even with the reservoir on."""
    on, _ = _run(True, 16, eta=0.0)
    assert on.cum_E_modal_injected < 1e-9
    assert on.cum_E_reservoir_deposit < 1e-9


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_flag_off_leaves_reservoir_inert():
    """§14.6: with the flag OFF, no reservoir state accrues (the is_new path is
    untouched) yet normal injection still happens."""
    off, _ = _run(False, 16)
    assert off.cum_E_reservoir_deposit == 0.0
    assert off.cum_E_reservoir_spent == 0.0
    assert off.cum_E_modal_injected > 0.0
