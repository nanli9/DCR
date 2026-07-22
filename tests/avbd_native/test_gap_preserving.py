"""Gap-preserving passivity projection (post-MIG follow-up to the §15 clamp).

The shipped governor scales the whole modal state radially, which shrinks the
load-bearing sag U_y·q that resting bodies stand on and opens up to 21.6 mm of
penetration (paper §3.3, Table 2). `gap_preserving_projection` lands on a
DIFFERENT admissible point — one that holds the active rows' observed surface
fixed where the budget affords it — while enforcing the SAME bound (foundation
§15). These tests pin the properties the guarantee rests on:

  1. it reduces EXACTLY to the shipped radial γ when no row is active,
  2. the split is contact-invisible and K-orthogonal,
  3. rung 1 preserves U_c·q exactly (zero clamp-induced penetration),
  4. the post-projection energy is admissible on BOTH rungs (Prop. 4.1),
  5. rung 2 is never worse than radial (β ≥ γ), so the fallback is monotone,
  6. it is inert whenever the step already fits (bit-identical trajectories).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.passivity import (
    gap_preserving_projection, modal_mech_energy, passivity_gamma,
    quasi_static_split)


def _modes(r=8, seed=0):
    """Mass-normalized modal system: M = I, K = diag(ω²), spectrum spanning the
    soft/stiff split the shelf actually has (20 Hz .. 25 kHz)."""
    rng = np.random.default_rng(seed)
    f = np.geomspace(20.0, 2.5e4, r)
    Kq = (2 * np.pi * f) ** 2
    Mq = np.ones(r)
    return Kq, Mq, rng


def test_reduces_to_radial_gamma_without_active_rows():
    """No active rows ⇒ the shipped governor, to the last bit."""
    Kq, Mq, rng = _modes()
    q, qd = rng.normal(size=Kq.size) * 1e-3, rng.normal(size=Kq.size)
    ke, pe = modal_mech_energy(qd, q, Mq, Kq)
    e_new, e_old, budget = ke + pe, 0.0, 0.05 * (ke + pe)
    U_c = np.zeros((0, Kq.size))
    q2, qd2, g, info = gap_preserving_projection(
        q, qd, Kq, Mq, U_c, e_old, budget)
    g_ref = passivity_gamma(e_new, e_old, budget)
    assert g == pytest.approx(g_ref, rel=1e-12)
    assert np.allclose(q2, q * g_ref, rtol=0, atol=0)
    assert np.allclose(qd2, qd * g_ref, rtol=0, atol=0)


def test_split_is_contact_invisible_and_K_orthogonal():
    """The two properties that make the projection closed-form."""
    Kq, Mq, rng = _modes(r=12, seed=1)
    q = rng.normal(size=Kq.size) * 1e-3
    U_c = rng.normal(size=(4, Kq.size))
    q_qs, q_perp, e_qs = quasi_static_split(q, Kq, U_c)
    assert np.allclose(U_c @ q_perp, 0.0, atol=1e-12)          # invisible
    assert abs(float(q_qs @ (Kq * q_perp))) < 1e-6 * max(
        1.0, abs(float(q_qs @ (Kq * q_qs))))                   # K-orthogonal
    assert np.allclose(U_c @ q_qs, U_c @ q, rtol=1e-9)         # realizes d
    # E_qs is the MINIMUM elastic energy realizing d, so it cannot exceed PE(q)
    assert e_qs <= 0.5 * float(q @ (Kq * q)) + 1e-12
    assert e_qs == pytest.approx(0.5 * float(q_qs @ (Kq * q_qs)), rel=1e-9)


def test_rung1_preserves_the_contact_surface_exactly():
    """Where the budget affords it, the observed gap does not move at all —
    this is the 21.6 mm artifact's direct cure."""
    Kq, Mq, rng = _modes(r=10, seed=2)
    # soft load-bearing sag + a violent stiff ring (the measured pathology:
    # 99.6% of injected energy sits in the stiff cluster, paper §3.3)
    q = np.zeros(Kq.size)
    q[0], q[1] = 2.0e-2, 5.0e-3
    q[-3:] = 4.0e-4
    qd = np.zeros(Kq.size)
    qd[-3:] = 8.0e2
    U_c = np.zeros((2, Kq.size))
    U_c[0, :3] = [1.0, 0.4, 0.1]
    U_c[1, :3] = [0.8, -0.3, 0.2]
    ke, pe = modal_mech_energy(qd, q, Mq, Kq)
    e_new = ke + pe
    q_qs, _, e_qs = quasi_static_split(q, Kq, U_c)
    ceiling = 0.5 * (e_qs + e_new)          # affordable: e_qs < ceiling < e_new
    assert e_qs < ceiling < e_new
    q2, qd2, g, info = gap_preserving_projection(
        q, qd, Kq, Mq, U_c, 0.0, ceiling)
    assert info["rung"] == 1
    assert np.allclose(U_c @ q2, U_c @ q, rtol=1e-9, atol=1e-15)
    # ... and it strictly beats radial, which would shrink the surface by γ
    g_rad = passivity_gamma(e_new, 0.0, ceiling)
    assert np.max(np.abs(U_c @ q2 - U_c @ q)) < np.max(
        np.abs(U_c @ (q * g_rad) - U_c @ q))


def test_rung2_is_never_worse_than_radial():
    """When even the sag alone overdraws, the fallback still preserves MORE
    surface than the shipped projection (β ≥ γ, since E_qs ≤ E⁺)."""
    Kq, Mq, rng = _modes(r=6, seed=3)
    q = np.zeros(Kq.size)
    q[0] = 3.0e-2                                  # nearly all energy IS the sag
    qd = np.zeros(Kq.size)
    U_c = np.zeros((1, Kq.size))
    U_c[0, 0] = 1.0
    ke, pe = modal_mech_energy(qd, q, Mq, Kq)
    e_new = ke + pe
    ceiling = 0.25 * e_new                         # forces rung 2
    q2, qd2, g, info = gap_preserving_projection(
        q, qd, Kq, Mq, U_c, 0.0, ceiling)
    assert info["rung"] == 2
    g_rad = passivity_gamma(e_new, 0.0, ceiling)
    d_new, d_rad, d_pre = (float((U_c @ q2)[0]), float((U_c @ (q * g_rad))[0]),
                           float((U_c @ q)[0]))
    assert abs(d_new - d_pre) <= abs(d_rad - d_pre) + 1e-15
    assert info["scale"] >= g_rad - 1e-12


@pytest.mark.parametrize("seed", range(24))
def test_bound_holds_on_both_rungs_randomized(seed):
    """Prop. 4.1's only requirement: the projected state is admissible. Swept
    over random states, active-set sizes (including rank-deficient and
    over-determined row sets) and budgets."""
    Kq, Mq, rng = _modes(r=10, seed=seed)
    q = rng.normal(size=Kq.size) * 10.0 ** rng.uniform(-4, -1)
    qd = rng.normal(size=Kq.size) * 10.0 ** rng.uniform(-1, 3)
    m = int(rng.integers(1, 16))                   # 1..15 rows on 10 modes
    U_c = rng.normal(size=(m, Kq.size))
    if m > 3 and seed % 3 == 0:                    # force rank deficiency
        U_c[1:] = U_c[0]
    ke, pe = modal_mech_energy(qd, q, Mq, Kq)
    e_new = ke + pe
    e_old = float(rng.uniform(0.0, 0.3) * e_new)
    budget = float(rng.uniform(0.0, 0.5) * e_new)
    ceiling = e_old + budget
    q2, qd2, g, info = gap_preserving_projection(
        q, qd, Kq, Mq, U_c, e_old, budget)
    ke2, pe2 = modal_mech_energy(qd2, q2, Mq, Kq)
    e_post = ke2 + pe2
    assert np.all(np.isfinite(q2)) and np.all(np.isfinite(qd2))
    if e_new <= ceiling:
        assert g == 1.0                                    # inert
        assert np.shares_memory(q2, q) or np.allclose(q2, q)
    else:
        assert e_post <= ceiling * (1 + 1e-9) + 1e-12      # ADMISSIBLE
        assert e_post <= e_new + 1e-12                     # never increases E
        assert 0.0 <= g <= 1.0
        if info["rung"] == 1:                              # gap preserved exactly
            assert np.allclose(U_c @ q2, U_c @ q, rtol=1e-7, atol=1e-14)


def test_rung1b_keeps_the_most_loaded_rows_when_the_full_set_is_unaffordable():
    """When the whole active set overdraws, the λ-ordered prefix that DOES fit
    is preserved exactly — the rows carrying real load are the ones kept."""
    Kq, Mq, rng = _modes(r=10, seed=11)
    q = np.zeros(Kq.size)
    q[0] = 2.0e-2                        # soft sag: cheap to preserve
    q[4] = q[5] = 2.0e-3                 # stiffer content: expensive to preserve
    qd = np.zeros(Kq.size)
    qd[-2:] = 5.0e2
    U_c = np.zeros((3, Kq.size))
    U_c[0, 0] = 1.0                      # cheap row (soft mode)
    U_c[1, 4] = 1.0                      # expensive rows (stiffer modes)
    U_c[2, 5] = 1.0
    lam = np.array([9.0, 2.0, 1.0])      # row 0 carries the load
    ke, pe = modal_mech_energy(qd, q, Mq, Kq)
    _, _, e_qs_full = quasi_static_split(q, Kq, U_c)
    _, _, e_qs_row0 = quasi_static_split(q, Kq, U_c[:1])
    ceiling = 0.5 * (e_qs_row0 + e_qs_full)     # row 0 affordable, all three not
    assert e_qs_row0 < ceiling < e_qs_full
    q2, qd2, g, info = gap_preserving_projection(
        q, qd, Kq, Mq, U_c, 0.0, ceiling, row_priority=lam)
    assert info["rung"] == 11 and 0 < info["n_preserved"] < 3
    # the highest-λ row is held exactly; energy stays admissible
    assert float(U_c[0] @ q2) == pytest.approx(float(U_c[0] @ q), rel=1e-7)
    ke2, pe2 = modal_mech_energy(qd2, q2, Mq, Kq)
    assert ke2 + pe2 <= ceiling * (1 + 1e-12)


def test_projection_lands_exactly_on_the_ceiling_not_merely_near_it():
    """The cumulative ledger sits at the float64 roundoff floor, so the
    projection must not leave a per-substep residue above the ceiling: a 1e-9
    slack accumulated to 1.1e-9 J over 105 clamps in the shelf 4x1 cell before
    the exact micro-scale was added."""
    Kq, Mq, rng = _modes(r=16, seed=5)
    for k in range(40):
        q = rng.normal(size=Kq.size) * 10.0 ** rng.uniform(-4, -2)
        qd = rng.normal(size=Kq.size) * 10.0 ** rng.uniform(0, 3)
        U_c = rng.normal(size=(int(rng.integers(1, 9)), Kq.size))
        lam = rng.uniform(0, 1, size=U_c.shape[0])
        ke, pe = modal_mech_energy(qd, q, Mq, Kq)
        ceiling = float(rng.uniform(1e-4, 0.9) * (ke + pe))
        q2, qd2, g, info = gap_preserving_projection(
            q, qd, Kq, Mq, U_c, 0.0, ceiling, row_priority=lam)
        ke2, pe2 = modal_mech_energy(qd2, q2, Mq, Kq)
        # STRICT: no positive slack at all, only float64 rounding of the scale
        assert ke2 + pe2 <= ceiling * (1 + 1e-13), (
            f"seed-step {k}: {ke2 + pe2:.17g} > {ceiling:.17g}")


def test_inert_when_the_step_already_fits():
    """γ=1 ⇒ untouched state, so governed runs stay bit-identical wherever the
    solve is already within budget (the paper's inertness property)."""
    Kq, Mq, rng = _modes(r=8, seed=7)
    q, qd = rng.normal(size=8) * 1e-4, rng.normal(size=8)
    ke, pe = modal_mech_energy(qd, q, Mq, Kq)
    U_c = rng.normal(size=(3, 8))
    q2, qd2, g, info = gap_preserving_projection(
        q, qd, Kq, Mq, U_c, 0.0, 10.0 * (ke + pe))
    assert g == 1.0 and info["rung"] == 0
    assert np.array_equal(q2, q) and np.array_equal(qd2, qd)
