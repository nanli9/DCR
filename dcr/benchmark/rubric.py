"""Pass/fail rubric for a single benchmark run.

Design (see `benchmark/PATCH_MODE_BENCHMARK.md` Q2):

- Per-body checks, evaluated over the full trajectory:
    * `penetration_max_m`   how far the body's bottom went below its
                            support surface. 1 mm is strict on purpose
                            — it forces us to acknowledge rigid-solver
                            ERP slack when it shows up.
    * `max_tilt_deg`        max angle between body +y and world +y, from
                            the quaternion. 0° = upright.
    * `x_drift_max_m`, `z_drift_max_m`   |final - initial| horizontal
                            displacement.
    * `tail_y_range_max_m`  max-min y over the last `tail_window_s`. Tiny
                            means "settled".

- A body passes iff every check passes. Run passes iff every body passes.

- Per-body rubric overrides via `body_overrides` allow scene-specific
  relaxations (e.g. the ledge boulder is *supposed* to roll, so its
  `max_tilt_deg` can be 90).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from dcr.rigid.body import quat_to_rot


# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class BodyRubric:
    """Tolerances for a single body. Defaults are the strict baseline."""
    penetration_max_m: float = 0.001     # 1 mm
    max_tilt_deg: float = 5.0
    x_drift_max_m: float = 0.05
    z_drift_max_m: float = 0.05
    tail_y_range_max_m: float = 0.005    # over last `tail_window_s`
    tail_window_s: float = 0.5


DEFAULT_RUBRIC = BodyRubric()


@dataclass
class BodyResult:
    name: str
    passed: bool
    fails: list[str]
    metrics: dict[str, float]   # raw measured values per metric

    def __str__(self) -> str:
        flag = "PASS" if self.passed else "FAIL"
        if self.fails:
            return f"{self.name:<12} {flag}  fails: {','.join(self.fails)}"
        return f"{self.name:<12} {flag}"


@dataclass
class RunResult:
    scene: str
    mode: str
    body_results: list[BodyResult]
    passed: bool

    def summary(self) -> str:
        flag = "PASS" if self.passed else "FAIL"
        n_pass = sum(1 for b in self.body_results if b.passed)
        return (f"run {self.scene}/{self.mode}: {flag} "
                f"({n_pass}/{len(self.body_results)} bodies)")


# ----------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------

def quat_to_tilt_deg(q: NDArray[np.float64]) -> float:
    """Angle in degrees between body +y axis and world +y axis.

    0° = upright; 90° = on its side; 180° = upside down. Uses `abs(cos)`
    so upside-down is treated identically to upright (we don't usually
    care which face is up — only how far from vertical).
    """
    R = quat_to_rot(q)
    up_world = R @ np.array([0.0, 1.0, 0.0])
    cos_theta = float(np.clip(up_world[1], -1.0, 1.0))
    return float(np.degrees(np.arccos(abs(cos_theta))))


# ----------------------------------------------------------------------
# Per-body evaluation
# ----------------------------------------------------------------------

def evaluate_body(
    name: str,
    positions: NDArray[np.float64],       # (T, 3)
    orientations: NDArray[np.float64],    # (T, 4) quaternion (w, x, y, z)
    times: NDArray[np.float64],           # (T,)
    half_y: float,                        # body half-extent in body +y
    support_y: float,                     # support surface height
    rubric: BodyRubric = DEFAULT_RUBRIC,
) -> BodyResult:
    """Score one body's trajectory against `rubric`."""
    positions = np.asarray(positions, dtype=np.float64)
    orientations = np.asarray(orientations, dtype=np.float64)
    times = np.asarray(times, dtype=np.float64)

    ys = positions[:, 1]
    xs = positions[:, 0]
    zs = positions[:, 2]

    body_bottom = ys - half_y
    penetration_max = float(max(0.0, support_y - body_bottom.min()))

    tilts = np.array([quat_to_tilt_deg(q) for q in orientations])
    max_tilt = float(tilts.max())

    x_drift = float(xs[-1] - xs[0])
    z_drift = float(zs[-1] - zs[0])

    # Tail-window y range: last `tail_window_s` of sim.
    t_end = float(times[-1])
    tail_mask = times >= (t_end - rubric.tail_window_s)
    if tail_mask.sum() < 2:
        tail_mask = np.zeros_like(times, dtype=bool)
        tail_mask[-2:] = True
    tail_y_range = float(ys[tail_mask].max() - ys[tail_mask].min())

    metrics = {
        "penetration_max_m": penetration_max,
        "max_tilt_deg": max_tilt,
        "x_drift_m": x_drift,
        "z_drift_m": z_drift,
        "tail_y_range_m": tail_y_range,
    }

    fails: list[str] = []
    if penetration_max > rubric.penetration_max_m:
        fails.append("penetration")
    if max_tilt > rubric.max_tilt_deg:
        fails.append("tilt")
    if abs(x_drift) > rubric.x_drift_max_m:
        fails.append("x_drift")
    if abs(z_drift) > rubric.z_drift_max_m:
        fails.append("z_drift")
    if tail_y_range > rubric.tail_y_range_max_m:
        fails.append("tail_y_range")

    return BodyResult(name=name, passed=len(fails) == 0,
                      fails=fails, metrics=metrics)


# ----------------------------------------------------------------------
# Run evaluation
# ----------------------------------------------------------------------

def evaluate_run(
    scene: str,
    mode: str,
    body_info: Mapping[str, tuple],       # name -> (idx, hx, hy, hz, color)
    positions: Mapping[str, list],        # name -> list of (3,) positions
    orientations: Mapping[str, list],     # name -> list of (4,) quaternions
    times: NDArray[np.float64],
    support_for: Mapping[str, float],     # body name -> support_y
    rubric: BodyRubric = DEFAULT_RUBRIC,
    body_overrides: Mapping[str, BodyRubric] | None = None,
    default_support_y: float = 0.0,
) -> RunResult:
    """Evaluate every body in `body_info` against the rubric.

    `support_for` maps body name to its support-surface height. Bodies
    without an entry get `default_support_y`. `body_overrides` maps body
    name to a custom `BodyRubric` (e.g. the ledge boulder gets a relaxed
    tilt limit because rolling is the point).
    """
    body_overrides = body_overrides or {}
    results: list[BodyResult] = []
    for name, (_idx, _hx, hy, _hz, _color) in body_info.items():
        positions_arr = np.asarray(positions[name], dtype=np.float64)
        orientations_arr = np.asarray(orientations[name], dtype=np.float64)
        support_y = support_for.get(name, default_support_y)
        body_rubric = body_overrides.get(name, rubric)
        result = evaluate_body(
            name=name,
            positions=positions_arr,
            orientations=orientations_arr,
            times=times,
            half_y=hy,
            support_y=support_y,
            rubric=body_rubric,
        )
        results.append(result)

    run_passed = all(r.passed for r in results)
    return RunResult(scene=scene, mode=mode,
                     body_results=results, passed=run_passed)
