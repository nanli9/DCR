"""Stage E2 acceptance tests — passive scaling coefficient alpha.

E2.3 criteria:
1. Property-based: dE_modal(alpha) <= E_max + 1e-12, alpha in [0,1] for 10k samples.
2. Monotonicity: dE_modal non-decreasing in alpha when b >= 0.
3. Opposing-impulse: b < 0 returns alpha=1 even with E_max=0.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.modal.passive_inject import passive_alpha


def _delta_E(s, qdot, alpha):
    """Compute dE_modal(alpha) = alpha * b + 0.5 * alpha^2 * a."""
    a = np.dot(s, s)
    b = np.dot(qdot, s)
    return alpha * b + 0.5 * alpha**2 * a


class TestPropertyBased:
    """E2.3 criterion 1: property-based test over random samples."""

    def test_energy_bound_10k_samples(self) -> None:
        rng = np.random.default_rng(42)
        n_modes = 5
        violations = 0

        for _ in range(10_000):
            s = rng.standard_normal(n_modes) * rng.uniform(0.01, 10.0)
            qdot = rng.standard_normal(n_modes) * rng.uniform(0.01, 10.0)
            E_max = rng.uniform(0.0, 50.0)

            alpha = passive_alpha(s, qdot, E_max)
            dE = _delta_E(s, qdot, alpha)

            assert 0.0 <= alpha <= 1.0, f"alpha={alpha} out of [0,1]"
            if dE > E_max + 1e-12:
                violations += 1

        assert violations == 0, f"{violations} violations in 10k samples"

    def test_zero_E_max_samples(self) -> None:
        """With E_max=0, dE_modal(alpha) must be <= 0 + 1e-12."""
        rng = np.random.default_rng(99)
        n_modes = 3

        for _ in range(5_000):
            s = rng.standard_normal(n_modes)
            qdot = rng.standard_normal(n_modes)

            alpha = passive_alpha(s, qdot, 0.0)
            dE = _delta_E(s, qdot, alpha)

            assert 0.0 <= alpha <= 1.0
            assert dE <= 1e-12, f"dE={dE} > 0 with E_max=0"


class TestMonotonicity:
    """E2.3 criterion 2: dE_modal non-decreasing in alpha when b >= 0."""

    def test_monotone_b_positive(self) -> None:
        rng = np.random.default_rng(77)
        n_modes = 4

        for _ in range(100):
            s = rng.standard_normal(n_modes)
            # Ensure b >= 0 by aligning qdot with s
            qdot = np.abs(rng.standard_normal(n_modes)) * np.sign(s + 1e-10)
            b = np.dot(qdot, s)
            if b < 0:
                qdot = -qdot  # flip to make b positive

            alphas = np.linspace(0.0, 1.0, 50)
            dEs = [_delta_E(s, qdot, a) for a in alphas]

            for i in range(1, len(dEs)):
                assert dEs[i] >= dEs[i - 1] - 1e-14, \
                    f"Non-monotone: dE[{i}]={dEs[i]:.6e} < dE[{i-1}]={dEs[i-1]:.6e}"


class TestOpposingImpulse:
    """E2.3 criterion 3: b < 0 → alpha=1 even with E_max=0."""

    def test_opposing_hand_constructed(self) -> None:
        """qdot = [1, 0], s = [-2, 0] → b = -2, a = 4, dE_full = -2+2 = 0 <= 0."""
        s = np.array([-2.0, 0.0])
        qdot = np.array([1.0, 0.0])
        # b = qdot . s = -2, a = s . s = 4
        # dE_full = b + 0.5*a = -2 + 2 = 0 <= 0
        alpha = passive_alpha(s, qdot, E_max=0.0)
        assert alpha == 1.0

    def test_strongly_opposing(self) -> None:
        """qdot = [3, 0], s = [-1, 0] → b = -3, a = 1, dE_full = -3+0.5 = -2.5."""
        s = np.array([-1.0, 0.0])
        qdot = np.array([3.0, 0.0])
        alpha = passive_alpha(s, qdot, E_max=0.0)
        assert alpha == 1.0
        # Verify dE is indeed negative
        dE = _delta_E(s, qdot, alpha)
        assert dE < 0.0

    def test_weakly_opposing_with_budget(self) -> None:
        """b < 0 but |b| < 0.5*a → dE_full > 0. Should still cap correctly."""
        s = np.array([2.0, 0.0])   # a = 4
        qdot = np.array([-0.5, 0.0])  # b = -1, dE_full = -1 + 2 = 1
        alpha = passive_alpha(s, qdot, E_max=0.5)
        dE = _delta_E(s, qdot, alpha)
        assert 0.0 <= alpha <= 1.0
        assert dE <= 0.5 + 1e-12


class TestEdgeCases:
    """Additional edge-case coverage."""

    def test_zero_impulse(self) -> None:
        alpha = passive_alpha(np.zeros(3), np.array([1.0, 2.0, 3.0]), 10.0)
        assert alpha == 0.0

    def test_zero_qdot(self) -> None:
        """qdot=0 → b=0, dE_full = 0.5*a. Alpha depends on E_max."""
        s = np.array([1.0, 0.0])
        qdot = np.zeros(2)
        # a = 1, b = 0, dE_full = 0.5
        # E_max = 1.0 → full kick fits
        assert passive_alpha(s, qdot, 1.0) == 1.0
        # E_max = 0.1 → need cap
        alpha = passive_alpha(s, qdot, 0.1)
        assert 0.0 < alpha < 1.0
        dE = _delta_E(s, qdot, alpha)
        assert abs(dE - 0.1) < 1e-12  # should hit exactly E_max

    def test_large_E_max(self) -> None:
        """Huge budget → always alpha=1."""
        rng = np.random.default_rng(55)
        for _ in range(100):
            s = rng.standard_normal(5)
            qdot = rng.standard_normal(5)
            alpha = passive_alpha(s, qdot, 1e10)
            assert alpha == 1.0

    def test_scalar_mode(self) -> None:
        """Single-mode case for easy verification."""
        s = np.array([2.0])
        qdot = np.array([1.0])
        # a=4, b=2, dE_full = 2+2 = 4
        # E_max = 1: solve 2*alpha + 2*alpha^2 = 1
        # 2*alpha^2 + 2*alpha - 1 = 0 → alpha = (-2 + sqrt(4+8)) / 4 = (-2+sqrt(12))/4
        expected = (-2.0 + np.sqrt(12.0)) / 4.0
        alpha = passive_alpha(s, qdot, 1.0)
        assert abs(alpha - expected) < 1e-12
