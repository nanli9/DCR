"""Unit tests for dcr.benchmark.rubric.

Synthetic trajectories — no scene runs, no FEM.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.benchmark import (
    BodyRubric,
    BodyResult,
    RunResult,
    evaluate_body,
    evaluate_run,
    quat_to_tilt_deg,
)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _identity_quat():
    return np.array([1.0, 0.0, 0.0, 0.0])


def _axis_angle_quat(axis, angle_rad):
    """Quaternion (w, x, y, z) for a rotation by `angle_rad` around `axis`."""
    axis = np.asarray(axis, dtype=np.float64)
    axis = axis / np.linalg.norm(axis)
    c, s = np.cos(angle_rad / 2.0), np.sin(angle_rad / 2.0)
    return np.array([c, s * axis[0], s * axis[1], s * axis[2]])


def _static_trajectory(n_steps=100, position=(0.0, 0.1, 0.0), dt=0.01):
    """Body holds still at `position` with identity orientation."""
    times = np.arange(n_steps) * dt
    positions = np.tile(np.array(position, dtype=np.float64), (n_steps, 1))
    orientations = np.tile(_identity_quat(), (n_steps, 1))
    return times, positions, orientations


# ----------------------------------------------------------------------
# quat_to_tilt_deg
# ----------------------------------------------------------------------

class TestQuatToTiltDeg:
    def test_identity_is_zero(self):
        assert quat_to_tilt_deg(_identity_quat()) == pytest.approx(0.0)

    def test_90_deg_about_x(self):
        q = _axis_angle_quat([1, 0, 0], np.pi / 2)
        assert quat_to_tilt_deg(q) == pytest.approx(90.0, abs=1e-6)

    def test_180_deg_upside_down_treated_as_zero(self):
        # abs(cos) -> upside-down is same as upright
        q = _axis_angle_quat([1, 0, 0], np.pi)
        assert quat_to_tilt_deg(q) == pytest.approx(0.0, abs=1e-6)

    def test_45_deg_about_z(self):
        q = _axis_angle_quat([0, 0, 1], np.pi / 4)
        assert quat_to_tilt_deg(q) == pytest.approx(45.0, abs=1e-6)


# ----------------------------------------------------------------------
# evaluate_body — clean pass cases
# ----------------------------------------------------------------------

class TestEvaluateBodyPass:
    def test_static_body_passes(self):
        times, positions, orientations = _static_trajectory()
        # body at y=0.1, hy=0.05 -> bottom at 0.05; support at 0.05 -> no pen
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert result.passed
        assert result.fails == []
        assert result.metrics["penetration_max_m"] == pytest.approx(0.0)

    def test_settled_after_initial_motion(self):
        # First half: bouncing UPWARD only (we don't dip below support);
        # second half: settled. Tail window 0.5s, dt=0.01, n=200 -> tail
        # = last 50 steps. Body center at y=0.1 with hy=0.05 so bottom
        # is at 0.05 = support; we only add positive y motion.
        n = 200
        dt = 0.01
        times = np.arange(n) * dt
        ys = np.full(n, 0.1)
        # ringing strictly above rest position
        ys[:50] += 0.01 * (1.0 + np.sin(np.linspace(0, 6 * np.pi, 50))) / 2
        positions = np.column_stack([np.zeros(n), ys, np.zeros(n)])
        orientations = np.tile(_identity_quat(), (n, 1))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert result.passed, f"unexpected fails: {result.fails}"


# ----------------------------------------------------------------------
# evaluate_body — per-axis fail cases
# ----------------------------------------------------------------------

class TestEvaluateBodyFail:
    def test_penetration_fails_when_below_support(self):
        # body center dips to y=0.04, hy=0.05 -> bottom at -0.01, support at 0
        n = 100
        times = np.arange(n) * 0.01
        positions = np.tile([0.0, 0.1, 0.0], (n, 1)).astype(np.float64)
        positions[50, 1] = 0.04  # one timestep dip → bottom = -0.01
        orientations = np.tile(_identity_quat(), (n, 1))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.0,
        )
        assert not result.passed
        assert "penetration" in result.fails
        assert result.metrics["penetration_max_m"] == pytest.approx(0.01)

    def test_tilt_fails_when_over_threshold(self):
        n = 100
        times = np.arange(n) * 0.01
        positions = np.tile([0.0, 0.1, 0.0], (n, 1)).astype(np.float64)
        orientations = np.tile(_identity_quat(), (n, 1))
        # final 10 steps: tilt 10° about x axis (> default 5°)
        orientations[-10:] = _axis_angle_quat([1, 0, 0], np.radians(10.0))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert not result.passed
        assert "tilt" in result.fails
        assert result.metrics["max_tilt_deg"] == pytest.approx(10.0, abs=1e-3)

    def test_x_drift_fails_when_over_threshold(self):
        n = 100
        times = np.arange(n) * 0.01
        # drift from x=0 to x=0.06 (> default 0.05)
        xs = np.linspace(0.0, 0.06, n)
        positions = np.column_stack([xs, np.full(n, 0.1), np.zeros(n)])
        orientations = np.tile(_identity_quat(), (n, 1))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert not result.passed
        assert "x_drift" in result.fails

    def test_z_drift_fails_when_over_threshold(self):
        n = 100
        times = np.arange(n) * 0.01
        zs = np.linspace(0.0, -0.07, n)
        positions = np.column_stack([np.zeros(n), np.full(n, 0.1), zs])
        orientations = np.tile(_identity_quat(), (n, 1))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert not result.passed
        assert "z_drift" in result.fails

    def test_tail_y_range_fails_when_still_bouncing(self):
        # Body never settles — sinusoidal ringing through entire run.
        n = 200
        dt = 0.01
        times = np.arange(n) * dt
        # Amplitude 0.01 m → tail_y_range ≈ 0.02 > 0.005 threshold
        ys = 0.1 + 0.01 * np.sin(np.linspace(0, 20 * np.pi, n))
        positions = np.column_stack([np.zeros(n), ys, np.zeros(n)])
        orientations = np.tile(_identity_quat(), (n, 1))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert not result.passed
        assert "tail_y_range" in result.fails

    def test_multiple_fails_all_recorded(self):
        n = 100
        times = np.arange(n) * 0.01
        # Drift in x AND tilt
        xs = np.linspace(0.0, 0.10, n)
        positions = np.column_stack([xs, np.full(n, 0.1), np.zeros(n)])
        orientations = np.tile(_axis_angle_quat([1, 0, 0], np.radians(45)),
                               (n, 1))
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05,
        )
        assert not result.passed
        assert "x_drift" in result.fails
        assert "tilt" in result.fails


# ----------------------------------------------------------------------
# evaluate_body — custom rubric
# ----------------------------------------------------------------------

class TestEvaluateBodyCustomRubric:
    def test_relaxed_tilt_passes(self):
        # 30° tilt would fail default (5°) but pass when rubric allows 90°.
        n = 100
        times = np.arange(n) * 0.01
        positions = np.tile([0.0, 0.1, 0.0], (n, 1)).astype(np.float64)
        orientations = np.tile(_axis_angle_quat([1, 0, 0], np.radians(30)),
                               (n, 1))
        relaxed = BodyRubric(max_tilt_deg=90.0)
        result = evaluate_body(
            name="b", positions=positions, orientations=orientations,
            times=times, half_y=0.05, support_y=0.05, rubric=relaxed,
        )
        assert result.passed


# ----------------------------------------------------------------------
# evaluate_run
# ----------------------------------------------------------------------

class TestEvaluateRun:
    def _make_body_info(self):
        # (idx, hx, hy, hz, color)
        return {
            "a": (0, 0.05, 0.05, 0.05, (1, 0, 0)),
            "b": (1, 0.05, 0.05, 0.05, (0, 1, 0)),
        }

    def _make_traj(self, n, position=(0.0, 0.1, 0.0)):
        times = np.arange(n) * 0.01
        positions = np.tile(np.array(position, dtype=np.float64), (n, 1))
        orientations = np.tile(_identity_quat(), (n, 1))
        return times, positions, orientations

    def test_all_pass_run_passes(self):
        body_info = self._make_body_info()
        n = 100
        times, pos_a, orient_a = self._make_traj(n)
        _, pos_b, orient_b = self._make_traj(n, position=(0.1, 0.1, 0.0))
        positions = {"a": pos_a, "b": pos_b}
        orientations = {"a": orient_a, "b": orient_b}
        support_for = {"a": 0.05, "b": 0.05}
        result = evaluate_run(
            scene="test", mode="test",
            body_info=body_info, positions=positions,
            orientations=orientations, times=times,
            support_for=support_for,
        )
        assert result.passed
        assert all(b.passed for b in result.body_results)
        assert "PASS" in result.summary()

    def test_one_body_fail_makes_run_fail(self):
        body_info = self._make_body_info()
        n = 100
        times, pos_a, orient_a = self._make_traj(n)
        # b drifts past threshold
        _, pos_b, orient_b = self._make_traj(n)
        pos_b[:, 0] = np.linspace(0.0, 0.10, n)
        positions = {"a": pos_a, "b": pos_b}
        orientations = {"a": orient_a, "b": orient_b}
        support_for = {"a": 0.05, "b": 0.05}
        result = evaluate_run(
            scene="test", mode="test",
            body_info=body_info, positions=positions,
            orientations=orientations, times=times,
            support_for=support_for,
        )
        assert not result.passed
        n_pass = sum(1 for b in result.body_results if b.passed)
        assert n_pass == 1

    def test_body_override_relaxes_one_body_only(self):
        body_info = self._make_body_info()
        n = 100
        # Both bodies have 30° tilt — would fail default. Override only a.
        times = np.arange(n) * 0.01
        tilted = np.tile(_axis_angle_quat([1, 0, 0], np.radians(30)), (n, 1))
        positions = {
            "a": np.tile([0.0, 0.1, 0.0], (n, 1)).astype(np.float64),
            "b": np.tile([0.1, 0.1, 0.0], (n, 1)).astype(np.float64),
        }
        orientations = {"a": tilted, "b": tilted}
        support_for = {"a": 0.05, "b": 0.05}
        body_overrides = {"a": BodyRubric(max_tilt_deg=90.0)}
        result = evaluate_run(
            scene="test", mode="test",
            body_info=body_info, positions=positions,
            orientations=orientations, times=times,
            support_for=support_for,
            body_overrides=body_overrides,
        )
        a_result = next(b for b in result.body_results if b.name == "a")
        b_result = next(b for b in result.body_results if b.name == "b")
        assert a_result.passed
        assert not b_result.passed
        assert "tilt" in b_result.fails

    def test_default_support_when_no_entry(self):
        body_info = self._make_body_info()
        n = 100
        times, pos_a, orient_a = self._make_traj(n)
        _, pos_b, orient_b = self._make_traj(n, position=(0.1, 0.1, 0.0))
        positions = {"a": pos_a, "b": pos_b}
        orientations = {"a": orient_a, "b": orient_b}
        # No entries — both fall back to default_support_y=0.05
        result = evaluate_run(
            scene="test", mode="test",
            body_info=body_info, positions=positions,
            orientations=orientations, times=times,
            support_for={},
            default_support_y=0.05,
        )
        assert result.passed
