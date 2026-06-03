"""Phase B / spec §12 (Test 7): passivity line search with γ rescale.

Algorithm under test (`dcr/avbd/reservoir.py::passivity_scale_gamma`):

    γ = 1
    for attempt in range(max_passivity_attempts):
        W = run_solve(γ)
        if W ≤ E_budget + tol: accept
        γ ← γ · √(E_budget / (W + ε))
    if still violating: γ = 0; run_solve(0); accept

Test contracts:
  - W ≤ budget on attempt 0 → γ stays 1, exactly one call.
  - W > budget → γ shrinks, eventually accepts (or fallback γ=0).
  - The accepted W is always ≤ E_budget + tolerance.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.reservoir import (
    gamma_rescale,
    passivity_scale_gamma,
)


# ---------------------------------------------------------------------------
# Test 7a: γ stays at 1 when first attempt fits the budget
# ---------------------------------------------------------------------------

def test_gamma_stays_one_when_under_budget():
    """If run_solve(1) returns W ≤ E_budget, the line search accepts on the
    first call without rescaling γ."""
    calls = []

    def run_solve(gamma):
        calls.append(gamma)
        return 0.5   # always under any sane budget below

    gamma, W, attempts = passivity_scale_gamma(
        run_solve, E_budget=1.0, max_attempts=3)
    assert gamma == 1.0
    assert W == 0.5
    assert attempts == 1
    assert calls == [1.0]


# ---------------------------------------------------------------------------
# Test 7b: γ shrinks when work exceeds budget; eventually accepts
# ---------------------------------------------------------------------------

def test_gamma_shrinks_until_accepted():
    """run_solve(γ) returns W that scales quadratically in γ (the natural
    behavior of impulse-work in a 1-attempt linear solve). After one
    rescale γ' = γ · √(B/W), the next-attempt work hits B exactly.
    """
    # Imagine: W(γ) = γ² · 10.  At γ=1, W=10 > B=2.5.
    # Rescale: γ' = 1 · √(2.5/10) = 0.5  → W(0.5) = 0.25·10 = 2.5 ≤ B+tol.
    def run_solve(gamma):
        return (gamma ** 2) * 10.0

    gamma, W, attempts = passivity_scale_gamma(
        run_solve, E_budget=2.5, max_attempts=3, tolerance=1e-9)
    assert gamma == pytest.approx(0.5, rel=1e-6)
    assert W == pytest.approx(2.5, rel=1e-6)
    assert attempts == 2


# ---------------------------------------------------------------------------
# Test 7c: pathological run_solve that NEVER fits triggers γ=0 fallback
# ---------------------------------------------------------------------------

def test_gamma_falls_back_to_zero_when_unsatisfiable():
    """If `run_solve` is non-quadratic (e.g. constant) and always exceeds
    budget, the line search must give up after max_attempts and force γ=0
    (which always satisfies the bound by construction)."""
    def run_solve(gamma):
        # Constant huge work regardless of γ — pathological case.
        if gamma == 0.0:
            return 0.0   # γ=0 → support contributes nothing → no work
        return 100.0

    gamma, W, attempts = passivity_scale_gamma(
        run_solve, E_budget=1.0, max_attempts=3)
    assert gamma == 0.0
    assert W == 0.0
    assert attempts == 4    # max_attempts + 1 fallback


# ---------------------------------------------------------------------------
# Test 7d: accepted W is ALWAYS ≤ E_budget + tolerance, no exceptions
# ---------------------------------------------------------------------------

def test_accepted_W_always_within_budget_battery():
    """Random battery: 50 different (W-as-function-of-γ) profiles. The
    accepted W must satisfy the bound in every single case — this is the
    spec's hard requirement."""
    rng = np.random.default_rng(31)
    for trial in range(50):
        # Random quadratic, scaled to over/under budget.
        coef = float(rng.uniform(0.5, 50.0))
        E_budget = float(rng.uniform(0.01, 10.0))

        def run_solve(gamma, _c=coef):
            if gamma == 0.0:
                return 0.0
            return _c * gamma * gamma

        _, W, _ = passivity_scale_gamma(
            run_solve, E_budget=E_budget, max_attempts=3, tolerance=1e-6)
        assert W <= E_budget + 1e-6, (
            f"trial {trial}: W={W:.4e} > budget+tol ({E_budget+1e-6:.4e})")


# ---------------------------------------------------------------------------
# Test 7e: zero E_budget gates to γ=0 quickly
# ---------------------------------------------------------------------------

def test_zero_budget_short_circuits_to_gamma_zero():
    """When E_budget = 0 (empty reservoir), the line search collapses
    to γ=0 within max_attempts — no support work allowed.
    Spec §12 'early reject if E_budget is near zero' (we don't short-circuit
    in the helper itself; the rescale loop does the right thing anyway).
    """
    def run_solve(gamma):
        if gamma == 0.0:
            return 0.0
        return 1.0  # any positive number > 0 budget

    gamma, W, attempts = passivity_scale_gamma(
        run_solve, E_budget=0.0, max_attempts=3, tolerance=0.0)
    assert gamma == 0.0
    assert W == 0.0
    # On attempt 1: W=1 > budget=0, rescale factor = √(0/(1+ε)) = 0
    # → γ → 0. On attempt 2: run_solve(0) returns 0 ≤ 0 → accept.
    # So we converge on the *second* attempt, no fallback needed.
    assert attempts == 2


# ---------------------------------------------------------------------------
# gamma_rescale primitive sanity
# ---------------------------------------------------------------------------

def test_gamma_rescale_returns_one_when_no_work():
    """W=0 ⇒ rescale factor is 1.0 (no scaling needed)."""
    assert gamma_rescale(W_current=0.0, E_budget=1.0) == 1.0


def test_gamma_rescale_shrinks_when_over():
    """W > B ⇒ rescale factor √(B/W) < 1."""
    f = gamma_rescale(W_current=4.0, E_budget=1.0)
    assert f == pytest.approx(0.5, rel=1e-6)
