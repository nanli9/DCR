"""Energy-prescribed injection (docs §12 "option 1") tests.

prescribed_alpha scales the kick DIRECTION Φ(x)ᵀJ up OR down to deposit a
prescribed modal energy (= μ·available budget), instead of passive_alpha's
scale-DOWN-only cap. Layered on the impact reservoir it makes the injected modal
energy iteration-INSENSITIVE (the magnitude comes from η·E_loss, not from the
smeared ‖s‖) while staying globally passive (the realized ΔE is debited from the
reservoir, bounded by η·Σ E_loss).

The diagnostic (scripts/_diag_prescribed_injection_iter_sensitivity.py) shows
CV(E_modal) across iters {4,8,16,32} drops 0.69 → 0.02 and iters=4 fill rises
0.06 → 1.0. These tests pin the math (prescribed_alpha hits E_target, scales up,
clamps) and the scene-level passivity + iteration-insensitivity + OFF default.
"""
import numpy as np
import pytest

from dcr.modal.passive_inject import passive_alpha, prescribed_alpha

try:
    from scripts.run_scenes_avbd import build_shelf_scene
except Exception:  # pragma: no cover
    build_shelf_scene = None

ETA = 0.5


# ----------------------------- unit tests (no scene) ---------------------------

def test_prescribed_hits_target_when_qdot_zero():
    """With q̇=0 (b=0), prescribed_alpha deposits exactly E_target: α=√(2E/a)."""
    s = np.array([0.3, -0.1, 0.2])
    qdot = np.zeros(3)
    a = float(s @ s)
    for E_target in (1e-3, 0.05, 1.0, 50.0):
        alpha = prescribed_alpha(s, qdot, E_target, alpha_max=1e6)
        dE = alpha * float(qdot @ s) + 0.5 * alpha * alpha * a
        assert dE == pytest.approx(E_target, rel=1e-9)


def test_prescribed_hits_target_with_qdot():
    """General q̇: the realized ΔE = α·b + ½α²·a equals E_target exactly."""
    rng = np.random.default_rng(1)
    for _ in range(50):
        s = rng.standard_normal(4)
        qdot = rng.standard_normal(4)
        E_target = float(abs(rng.standard_normal()) * 3.0)
        a = float(s @ s)
        b = float(qdot @ s)
        alpha = prescribed_alpha(s, qdot, E_target, alpha_max=1e9)
        dE = alpha * b + 0.5 * alpha * alpha * a
        assert dE == pytest.approx(E_target, rel=1e-7, abs=1e-9)
        assert alpha >= 0.0


def test_prescribed_scales_up_where_passive_clamps():
    """The whole point: when the budget exceeds the raw kick energy, passive
    clamps at α=1 (under-injects) but prescribed scales UP past 1."""
    s = np.array([0.01, 0.0, 0.0])      # tiny kick, ½‖s‖² = 5e-5
    qdot = np.zeros(3)
    big_budget = 1.0
    a_pass = passive_alpha(s, qdot, big_budget)
    a_pre = prescribed_alpha(s, qdot, big_budget, alpha_max=1e6)
    assert a_pass == pytest.approx(1.0)         # passive clamped, leaves budget
    assert a_pre > 1.0                          # prescribed fills the budget
    assert 0.5 * (a_pre ** 2) * float(s @ s) == pytest.approx(big_budget, rel=1e-9)


def test_prescribed_alpha_max_clamp_and_zero_budget():
    s = np.array([1e-6, 0.0, 0.0])
    qdot = np.zeros(3)
    assert prescribed_alpha(s, qdot, 1.0, alpha_max=10.0) == pytest.approx(10.0)
    assert prescribed_alpha(s, qdot, 0.0, alpha_max=10.0) == 0.0      # no budget
    assert prescribed_alpha(np.zeros(3), qdot, 1.0) == 0.0            # no direction


# ----------------------------- scene-level guards ------------------------------

def _run(scaling, iters, use_reservoir=True, source="delta_p", eta=ETA, n=140):
    world, coupler, *_ = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=eta, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = iters
    coupler.use_impact_reservoir = use_reservoir
    coupler.impulse_source = source
    coupler.injection_scaling = scaling
    cum_E_loss = 0.0
    for _ in range(n):
        world.step()
        cum_E_loss += float(world.last_E_loss)
    return coupler, cum_E_loss


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_prescribed_is_globally_passive():
    """Even scaling UP, Σ E_inj ≤ η·Σ E_loss — the reservoir bounds the spend."""
    for iters in (4, 8, 16):
        coupler, cum_E_loss = _run("prescribed", iters)
        assert coupler.cum_E_modal_injected <= ETA * cum_E_loss + 1e-6, (
            f"iters={iters}: injected {coupler.cum_E_modal_injected:.4f} > "
            f"budget {ETA * cum_E_loss:.4f}")


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_prescribed_is_iteration_insensitive():
    """The headline: injected modal energy is ~flat across iters (CV small),
    where the passive cap leaves it spread ~10× from iters=4 to iters=16."""
    inj = {}
    for iters in (4, 8, 16):
        coupler, _ = _run("prescribed", iters)
        inj[iters] = coupler.cum_E_modal_injected
    vals = np.array(list(inj.values()))
    cv = float(np.std(vals) / np.mean(vals))
    assert cv < 0.15, f"prescribed CV across iters too high: {cv:.3f} ({inj})"
    assert inj[4] > 10.0, f"iters=4 should now inject a full budget, got {inj[4]}"


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_eta_zero_injects_nothing_prescribed():
    """η=0 ⇒ no budget ⇒ prescribed injects nothing (E_target=0)."""
    coupler, _ = _run("prescribed", 16, eta=0.0)
    assert coupler.cum_E_modal_injected < 1e-9


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_passive_default_unchanged():
    """Default injection_scaling is 'passive' and reproduces the capped
    behavior (iters=4 reservoir fill is small, far below the budget)."""
    world, coupler, *_ = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=ETA, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    assert coupler.injection_scaling == "passive"
    coupler.use_impact_reservoir = True
    coupler.impulse_source = "delta_p"
    cumL = 0.0
    for _ in range(140):
        world.step()
        cumL += float(world.last_E_loss)
    world._solver.iterations = 4
    # Passive at iters=4 stays well under the budget (the starvation we fix).
    assert coupler.cum_E_modal_injected <= ETA * cumL + 1e-6


def test_invalid_injection_scaling_rejected():
    from dcr.dcr.passive_dcr import PassiveDCRCoupler  # noqa: F401
    if build_shelf_scene is None:
        pytest.skip("shelf scene unavailable")
    world, coupler, *_ = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=ETA, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    assert coupler.injection_scaling == "passive"   # default
