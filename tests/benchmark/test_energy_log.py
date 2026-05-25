"""Unit tests for dcr.benchmark.energy_log.

Tests the EnergyLog accumulator + cumulative/invariant accessors with
synthetic per-step entries — no scene runs, no world.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.benchmark import EnergyLog, EnergyLogEntry


def _entry(step, t, dE_rigid_loss, dE_modal_injected, alpha=1.0, eta=0.5,
           E_rigid=0.0, E_modal=0.0):
    return EnergyLogEntry(
        step=step, t=t,
        E_rigid_KE_post=E_rigid, E_modal_post=E_modal,
        dE_rigid_loss=dE_rigid_loss,
        dE_modal_injected=dE_modal_injected,
        alpha=alpha, eta=eta,
    )


class TestEnergyLog:
    def test_empty_log(self):
        log = EnergyLog()
        assert len(log) == 0
        assert log.invariant_violation() == 0.0

    def test_append(self):
        log = EnergyLog()
        log.append(_entry(0, 0.01, 10.0, 3.0))
        log.append(_entry(1, 0.02, 5.0, 1.0))
        assert len(log) == 2

    def test_times_and_arrays(self):
        log = EnergyLog()
        log.append(_entry(0, 0.01, 10.0, 3.0))
        log.append(_entry(1, 0.02, 5.0, 1.0))
        np.testing.assert_array_equal(log.times(), [0.01, 0.02])
        np.testing.assert_array_equal(log.dE_rigid_loss(), [10.0, 5.0])
        np.testing.assert_array_equal(log.dE_modal_injected(), [3.0, 1.0])

    def test_cumulative_rigid_loss(self):
        log = EnergyLog()
        log.append(_entry(0, 0.01, 10.0, 0.0))
        log.append(_entry(1, 0.02, 5.0, 0.0))
        log.append(_entry(2, 0.03, 0.5, 0.0))
        np.testing.assert_array_almost_equal(
            log.cumulative_rigid_loss(), [10.0, 15.0, 15.5])

    def test_cumulative_injection_excludes_negative_deltas(self):
        # Positive deltas count toward injection; negative ones go to
        # extraction instead (patch mode back-reaction).
        log = EnergyLog()
        log.append(_entry(0, 0.01, 0.0, 5.0))     # +5 injected
        log.append(_entry(1, 0.02, 0.0, -2.0))    # -2 extracted, NOT counted
        log.append(_entry(2, 0.03, 0.0, 1.0))     # +1 injected
        np.testing.assert_array_almost_equal(
            log.cumulative_modal_injected(), [5.0, 5.0, 6.0])
        np.testing.assert_array_almost_equal(
            log.cumulative_modal_extracted(), [0.0, 2.0, 2.0])

    def test_invariant_holds_for_alpha_scaled_injection(self):
        # eta=0.5; each step, half the loss is injected — exactly on bound.
        log = EnergyLog()
        for s in range(5):
            log.append(_entry(s, 0.01 * s, 10.0, 5.0, eta=0.5))
        assert log.invariant_violation() == pytest.approx(0.0, abs=1e-9)

    def test_invariant_violation_detected(self):
        # eta=0.3, loss=10/step -> bound=3; we inject 5 -> violates by 2 cumul.
        log = EnergyLog()
        log.append(_entry(0, 0.01, 10.0, 5.0, eta=0.3))
        v = log.invariant_violation()
        # cum_loss=10, bound = 0.3*10 = 3, cum_inj = 5, excess = 2
        assert v == pytest.approx(2.0, abs=1e-9)

    def test_invariant_uses_first_entry_eta(self):
        # eta is constant per run; we sample from entries[0]
        log = EnergyLog()
        log.append(_entry(0, 0.01, 10.0, 3.0, eta=0.3))
        log.append(_entry(1, 0.02, 10.0, 3.0, eta=0.3))
        # cumulative bounds: [3, 6]; injected [3, 6] -> exactly on bound
        assert log.invariant_violation() == pytest.approx(0.0, abs=1e-9)

    def test_alpha_array(self):
        log = EnergyLog()
        log.append(_entry(0, 0.01, 0.0, 0.0, alpha=1.0))
        log.append(_entry(1, 0.02, 0.0, 0.0, alpha=0.3))
        log.append(_entry(2, 0.03, 0.0, 0.0, alpha=0.7))
        np.testing.assert_array_almost_equal(
            log.alpha(), [1.0, 0.3, 0.7])

    def test_E_rigid_and_E_modal_arrays(self):
        log = EnergyLog()
        log.append(_entry(0, 0.01, 0.0, 0.0, E_rigid=10.0, E_modal=1.0))
        log.append(_entry(1, 0.02, 0.0, 0.0, E_rigid=8.0, E_modal=3.0))
        np.testing.assert_array_almost_equal(log.E_rigid(), [10.0, 8.0])
        np.testing.assert_array_almost_equal(log.E_modal(), [1.0, 3.0])


class TestEnergyLogPlotSmoke:
    """Plot module is matplotlib pass-through; just check the functions
    don't crash on synthetic data and produce a file on disk."""

    def test_plot_energy_timeseries_creates_file(self, tmp_path):
        from dcr.benchmark.plots import plot_energy_timeseries
        log = EnergyLog()
        for s in range(10):
            log.append(_entry(s, 0.01 * s, 5.0, 1.0, alpha=0.5))
        out = tmp_path / "energy.png"
        result = plot_energy_timeseries(log, title="smoke test", out_path=out)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0

    def test_plot_energy_empty_log_does_not_crash(self, tmp_path):
        from dcr.benchmark.plots import plot_energy_timeseries
        log = EnergyLog()
        out = tmp_path / "empty.png"
        plot_energy_timeseries(log, title="empty", out_path=out)
        assert out.exists()

    def test_plot_param_sweep_creates_file(self, tmp_path):
        from dcr.benchmark.plots import plot_param_sweep
        logs = {}
        for beta in [0.1, 0.5, 1.0]:
            log = EnergyLog()
            for s in range(5):
                log.append(_entry(s, 0.01 * s, 5.0, beta * 2.0, alpha=beta))
            logs[beta] = log
        out = tmp_path / "sweep.png"
        plot_param_sweep(logs, param_name="β", scene="test",
                         mode="test", out_path=out)
        assert out.exists()

    def test_plot_bj_vs_rest_creates_file(self, tmp_path):
        from dcr.benchmark.plots import plot_bj_vs_rest_comparison
        log_a = EnergyLog()
        log_b = EnergyLog()
        for s in range(5):
            log_a.append(_entry(s, 0.01 * s, 5.0, 1.0, alpha=0.5))
            log_b.append(_entry(s, 0.01 * s, 5.0, 1.5, alpha=0.7))
        out = tmp_path / "compare.png"
        plot_bj_vs_rest_comparison(
            log_patch_fit=log_a, log_barbic_james=log_b,
            scene="test", mode="test", out_path=out)
        assert out.exists()
