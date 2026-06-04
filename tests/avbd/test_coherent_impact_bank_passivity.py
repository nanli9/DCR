"""Coherent impact impulse bank (coherent_impact_impulse_bank_fix) tests.

What the bank DOES (asserted here):
  * §17.1 cross terms — banking N coherent kicks injects ½‖Σs_i‖², recovering
    the positive cross terms a per-frame Σ½‖s_i‖² discards (for N=2 equal kicks,
    exactly 2×).
  * §17.2 no fabrication — antiparallel kicks (s, −s) are rejected by the
    directional gate, so opposite impulses never manufacture energy.
  * §17.3-4 passivity / depletion — every injection is capped by passive_alpha,
    and the budget is debited by exactly the realized ΔE (≥ 0 always).
  * §17.5 expiry — an event past max_event_age is deleted (no delayed kick).
  * Scene guards: η=0 ⇒ 0; flag OFF ⇒ inert; global passivity; and the
    no-double-count guard — bank + reservoir both ON ⇒ the bank wins and the
    reservoir never deposits, so Σ E_inj ≤ η·Σ E_loss still holds (the spec §15
    config would otherwise double-count η·E_loss).

What it does NOT achieve (documented in docs §11, NOT asserted): closing the
low-iteration injection gap. The diagnostic
(scripts/_diag_impact_bank_iter_sensitivity.py) shows the bank injects LESS than
the reservoir at every iteration count — coherent deferral loses passive budget
to decay faster than the cross-term gain recovers it, and R_coherence is flat
≈ window across iters (no iteration-dependent smearing to recover). The honest
conclusion is the spec §14 sharp-impulse estimator, not extraction from the
smeared solver output.
"""
import numpy as np
import pytest

from dcr.dcr.impact_bank import ImpactBank, ImpactEvent, ImpactKey
from dcr.modal.passive_inject import passive_alpha

try:
    from scripts.run_scenes_avbd import build_shelf_scene
except Exception:  # pragma: no cover - scene builder optional in some envs
    build_shelf_scene = None

ETA = 0.5
KEY = ImpactKey(body_id=1, support_id=0)


def _seed(bank: ImpactBank, key: ImpactKey, budget: float) -> ImpactEvent:
    """Create an event with a given budget (bypassing the λ_N deposit)."""
    ev = bank._get_or_create(key)
    ev.B_event = budget
    return ev


# ----------------------------- unit tests (no scene) ---------------------------

def test_cross_terms_recovered():
    """§17.1: two equal coherent kicks s bank to S=2s, so the injectable
    ½‖S‖² = ½‖2s‖² = 2‖s‖² — exactly twice the per-frame Σ½‖s‖² = ‖s‖²."""
    bank = ImpactBank(n_modes=3, mode="modal_sum", window=2)
    bank.begin_step()
    _seed(bank, KEY, budget=1e3)
    s = np.array([1.0, 0.5, -0.25])
    n = np.array([0.0, 0.0, 1.0])
    J = np.array([0.0, 0.0, 1.0])
    assert bank.accumulate(KEY, s, J, np.zeros(3), n, 1.0, 0.0) == "accumulated"
    assert bank.accumulate(KEY, s, J, np.zeros(3), n, 1.0, 0.0) == "accumulated"
    ev = bank.event(KEY)
    E_bank = 0.5 * float(ev.S_event @ ev.S_event)
    E_perframe = 2.0 * (0.5 * float(s @ s))
    assert E_bank == pytest.approx(2.0 * E_perframe, rel=1e-9)
    assert bank.coherence_ratio(ev) == pytest.approx(2.0, rel=1e-6)


def test_antiparallel_makes_no_fake_energy():
    """§17.2: an antiparallel second kick (s, −s) is rejected by the directional
    gate, so the bank never fabricates energy by merging opposite impulses."""
    bank = ImpactBank(n_modes=3, mode="modal_sum", window=4)
    bank.begin_step()
    _seed(bank, KEY, budget=1e3)
    s = np.array([1.0, 0.0, 0.0])
    n = np.array([0.0, 0.0, 1.0])
    J = np.array([0.0, 0.0, 1.0])
    assert bank.accumulate(KEY, s, J, np.zeros(3), n, 1.0, 0.0) == "accumulated"
    reason = bank.accumulate(KEY, -s, -J, np.zeros(3), n, 1.0, 0.0)
    assert reason == "rejected_directional"
    ev = bank.event(KEY)
    # S_event is still the single real impulse, not 0 and not inflated.
    np.testing.assert_allclose(ev.S_event, s)
    E_bank = 0.5 * float(ev.S_event @ ev.S_event)
    assert E_bank <= 0.5 * float(s @ s) + 1e-12   # no fabrication


def test_tangential_dominant_contact_rejected():
    """§8.5b: a friction-dominated (scraping) contact is not banked."""
    bank = ImpactBank(n_modes=3, mode="modal_sum")
    bank.begin_step()
    _seed(bank, KEY, budget=1e3)
    s = np.array([1.0, 0.0, 0.0])
    n = np.array([0.0, 0.0, 1.0])
    # |J_t| / (|J_n| + eps) = 10 / 1 = 10 > tangential_dominance_max (2.0).
    assert bank.accumulate(KEY, s, s, np.zeros(3), n,
                           jn_abs=1.0, jt_abs=10.0) == "rejected_tangential"


def test_passivity_and_depletion():
    """§17.3/§17.4: the injection obeys ΔE ≤ B_event and the budget is debited by
    exactly the realized ΔE, never going negative."""
    rng = np.random.default_rng(0)
    for _ in range(50):
        S = rng.standard_normal(4)
        qdot = rng.standard_normal(4) * 0.3
        B = float(abs(rng.standard_normal()) * 2.0)
        a = float(S @ S)
        b = float(qdot @ S)
        alpha = passive_alpha(S, qdot, B)
        dE = alpha * b + 0.5 * alpha * alpha * a   # realized ΔE_modal
        assert dE <= B + 1e-9
        bank = ImpactBank(n_modes=4)
        bank.begin_step()
        ev = _seed(bank, KEY, budget=B)
        bank.mark_spent(KEY, max(0.0, dE))
        assert ev.B_event >= -1e-12
        assert ev.B_event == pytest.approx(max(0.0, B - max(0.0, dE)), abs=1e-9)


def test_expiry_no_delayed_kick():
    """§17.5: an event that stops receiving deposits is deleted after
    max_event_age steps — no delayed bump survives."""
    bank = ImpactBank(n_modes=3, max_event_age=8, decay=1.0)
    bank.begin_step()
    _seed(bank, KEY, budget=5.0)
    bank.event(KEY).age = 0
    # No further deposits → age increments each begin_step.
    for _ in range(8):
        bank.begin_step()
    assert KEY in bank.events            # age == 8, still alive (> not >=)
    bank.begin_step()                    # age == 9 > 8 → expired
    assert KEY not in bank.events
    assert bank.last_E_expired == pytest.approx(5.0)


def test_config_validation():
    with pytest.raises(ValueError):
        ImpactBank(n_modes=3, mode="bogus")
    with pytest.raises(ValueError):
        ImpactBank(n_modes=3, inject_policy="bogus")
    with pytest.raises(ValueError):
        ImpactBank(n_modes=3, decay=1.5)


# ----------------------------- scene-level guards ------------------------------

def _run(use_bank, use_reservoir, iters, eta=ETA, source="delta_p", n=140):
    world, coupler, *_ = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=eta, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = iters
    coupler.use_coherent_impulse_bank = use_bank
    coupler.use_impact_reservoir = use_reservoir
    coupler.impulse_source = source
    cum_E_loss = 0.0
    for _ in range(n):
        world.step()
        cum_E_loss += float(world.last_E_loss)
    return coupler, cum_E_loss


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_bank_is_globally_passive():
    """Cumulative injected modal energy never exceeds η·Σ E_loss."""
    for iters in (4, 8, 16):
        coupler, cum_E_loss = _run(True, False, iters)
        assert coupler.cum_E_modal_injected <= ETA * cum_E_loss + 1e-6, (
            f"iters={iters}: injected {coupler.cum_E_modal_injected:.4f} > "
            f"budget {ETA * cum_E_loss:.4f}")


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_eta_zero_injects_nothing():
    """η=0 ⇒ no deposit ⇒ no injection, even with the bank on."""
    coupler, _ = _run(True, False, 16, eta=0.0)
    assert coupler.cum_E_modal_injected < 1e-9
    assert coupler._bank.cum_E_deposit < 1e-9


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_flag_off_leaves_bank_inert():
    """With the flag OFF the bank never runs, yet normal injection happens."""
    coupler, _ = _run(False, False, 16)
    assert coupler._bank.cum_E_deposit == 0.0
    assert coupler._bank.cum_E_spent == 0.0
    assert coupler.cum_E_modal_injected > 0.0


@pytest.mark.skipif(build_shelf_scene is None, reason="shelf scene unavailable")
def test_bank_subsumes_reservoir_no_double_count():
    """Both flags ON: the bank wins (its branch is dispatched first), the
    reservoir never deposits, and Σ E_inj ≤ η·Σ E_loss still holds — the spec
    §15 config that turns both on cannot double-count the budget."""
    coupler, cum_E_loss = _run(True, True, 16)
    assert coupler.cum_E_reservoir_deposit == 0.0   # reservoir branch unreached
    assert coupler._bank.cum_E_deposit > 0.0        # bank is the one depositing
    assert coupler.cum_E_modal_injected <= ETA * cum_E_loss + 1e-6
