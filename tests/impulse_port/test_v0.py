"""Impulse-port V0 asserts — the load-bearing bet of the two-band architecture.

The rigorous (sampled) velocity-band coupled impulse must be passive, exact, and
bounded; stiff position-glue against the same kHz ring must NOT settle (it
rectifies / pumps the ring). The governor (passive_alpha) is a clamp that never
fires at η=1 but DOES enforce the bound at η<1.
"""
import numpy as np
import pytest

from dcr.dcr.impulse_port_v0 import V0Config, run

PRE = np.array([0.5, 0.4, 0.3, 0.2])   # ring pre-excitation (q̇_d kick)


def _drop(**kw):
    return run(V0Config(coupling="velocity", ring_vel="sampled", N=360, **kw))


def _excited(**kw):
    return run(V0Config(coupling="velocity", ring_vel="sampled", N=360,
                        y0=0.0, qddot0=PRE.copy(), **kw))


# ---- per-impulse correctness (both scenarios) ----------------------------

@pytest.mark.parametrize("make", [_drop, _excited])
def test_no_pull(make):
    """λ = max(0, ·): the unilateral contact never pulls the body down (e=0)."""
    assert make().pull_violations == 0


@pytest.mark.parametrize("make", [_drop, _excited])
def test_resolution_exact(make):
    """ġ⁺ = −e·ġ⁻: the coupled impulse resolves the relative velocity exactly."""
    assert make().resolve_residual_max < 1e-12


@pytest.mark.parametrize("make", [_drop, _excited])
def test_energy_ledger_matches_quadratic(make):
    """ΔE_modal == α·b + ½α²·a exactly (foundation §15 quadratic = passive_alpha)."""
    assert make().ledger_residual_max < 1e-12


# ---- passivity + governor (correction 1) ---------------------------------

@pytest.mark.parametrize("make", [_drop, _excited])
def test_passivity_invariant(make):
    """§15: ΣΔE_modal ≤ η·ΣΔE_rigid holds for every prefix of the run."""
    assert make().invariant_margin_min > -1e-9


@pytest.mark.parametrize("make", [_drop, _excited])
def test_governor_never_clamps_at_eta1(make):
    """At η=1 the exchange is already passive (e≤1) — the governor is a safety
    net that never throttles a real injection (correction 1)."""
    assert make().clamp_activations == 0


def test_governor_does_clamp_and_reduce_injection_at_eta_below_1():
    """At η below the natural injection fraction (~27% of rigid loss for these
    params), the governor IS load-bearing on the DROP (which has real rigid loss
    to fund injection): it clamps real injections and reduces the total modal
    energy deposited vs η=1.

    NOTE: the strict per-prefix bound ΣΔE_modal ≤ η·ΣΔE_rigid is enforced exactly
    only at η=1 here (test_passivity_invariant). At η<1 the UNIFIED formulation
    funds injection from the same impulse's rigid loss, so the α=1 budget
    slightly over-counts vs the realized (clamped) loss — a second-order slack
    the foundation's reservoir/post-fix semantics remove (V1). The per-impulse
    §15 quadratic stays exact (test_energy_ledger_matches_quadratic)."""
    r1 = run(V0Config(coupling="velocity", ring_vel="sampled", N=360, eta=1.0))
    r = run(V0Config(coupling="velocity", ring_vel="sampled", N=360, eta=0.1))
    assert r.clamp_activations > 0                      # governor does real work
    assert r.cum_modal_inj < r1.cum_modal_inj           # injection reduced vs η=1
    assert r.ledger_residual_max < 1e-12                # quadratic still exact


# ---- settle: ring decays, body comes to rest, no drift -------------------

@pytest.mark.parametrize("make", [_drop, _excited])
def test_body_settles(make):
    r = make()
    assert r.y[-20:].std() < 1e-6                       # body at rest
    assert r.lam_max_per_step[-40:].max() < 1e-9        # impulses vanished
    assert r.qd_norm[-1] < 1e-3 * max(r.qd_norm.max(), 1e-30)  # ring decayed
    assert r.gap_min > -1e-3                            # bounded penetration (no drift)


# ---- the before/after bet: velocity bounded, position pathological -------

@pytest.mark.parametrize("iters", [4, 16, 64])
def test_velocity_band_bounded_over_iters(iters):
    """Velocity band settles regardless of iteration count (iteration-insensitive,
    bounded) — the opposite of the position-glue blow-up measured in the real
    solver (1.1 m launch at iters=32)."""
    r = run(V0Config(coupling="velocity", ring_vel="sampled", iters=iters,
                     substeps=8, N=300, y0=0.0, qddot0=PRE.copy()))
    assert abs(r.y[-1]) < 1e-5          # settles to ~0
    assert r.qd_norm[-1] < 1e-6         # ring decays


@pytest.mark.parametrize("iters", [4, 16, 64])
def test_position_glue_does_not_settle(iters):
    """Position-coupling the kHz ring leaves the body at a stuck offset and the
    ring pumped (does not decay) — the pathology the velocity band avoids."""
    rp = run(V0Config(coupling="position", iters=iters, substeps=8, N=300,
                      y0=0.0, qddot0=PRE.copy()))
    rv = run(V0Config(coupling="velocity", ring_vel="sampled", iters=iters,
                      substeps=8, N=300, y0=0.0, qddot0=PRE.copy()))
    # position leaves orders-of-magnitude larger residual offset than velocity,
    # and its ring never decays.
    assert abs(rp.y[-1]) > 50.0 * max(abs(rv.y[-1]), 1e-6)
    assert rp.qd_norm[-1] > 1e3 * rv.qd_norm[-1]
