"""Derived-metric computation for the §2.3 summary JSON.

Pure functions over an `EnergyLog`, the per-step kinematics captured by
`scripts.run_scenes.simulate(..., record_velocities=True)`, and the
`RunResult` from `dcr.benchmark.rubric.evaluate_run`. Producing the
summary JSON is the single end-of-run step `scripts/run_one.py` invokes
to write `<run_id>_summary.json` per
`benchmark/BENCHMARK_PROMPT.md` §2.3.

All field names + nesting follow the spec verbatim — the plotter selects
keys by name. Whenever the spec is silent (e.g. how to define
`peak_rate_W` when only one step has a non-zero injection), the chosen
fallback is documented inline.
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray

from .energy_log import EnergyLog
from .rubric import RunResult, quat_to_tilt_deg


# ---------------------------------------------------------------------------
# Injection-signal stats over a `dE_modal_injected[t]` time-series.
# ---------------------------------------------------------------------------

def _injection_signal_stats(
    dE_inj: NDArray[np.float64],
    h: float,
) -> dict[str, float]:
    """Compute peak-rate / Herfindahl / FFT-centroid / kick-count for the
    per-step modal-injection deltas. All four fields are in `§2.3`.

    `dE_inj` is the per-step modal injection energy in J. `h` is the
    timestep in s. Empty / all-zero series return zeros across the board.
    """
    dE = np.asarray(dE_inj, dtype=np.float64)
    n = dE.size
    if n == 0 or float(dE.max(initial=0.0)) <= 0.0:
        return {
            "peak_rate_W": 0.0,
            "temporal_concentration_herfindahl": 0.0,
            "spectral_centroid_Hz": 0.0,
            "n_distinct_kick_events": 0,
        }

    peak_per_step_J = float(dE.max())
    peak_rate_W = peak_per_step_J / max(h, 1e-12)

    total = float(dE.sum())
    if total > 0:
        # Herfindahl over the steps that actually injected: §2.3.
        positive = dE[dE > 0.0]
        herfindahl = float(np.sum((positive / total) ** 2))
    else:
        herfindahl = 0.0

    # Magnitude FFT centroid in Hz. Sampling rate = 1/h.
    fft = np.fft.rfft(dE - dE.mean())
    mag = np.abs(fft)
    freqs = np.fft.rfftfreq(n, d=h)
    msum = float(mag.sum())
    spectral_centroid_Hz = float(np.dot(freqs, mag) / msum) if msum > 0 else 0.0

    # Distinct events: steps with dE > 1 % of peak-per-step (§2.3).
    n_distinct = int(np.sum(dE > 0.01 * peak_per_step_J))

    return {
        "peak_rate_W": peak_rate_W,
        "temporal_concentration_herfindahl": herfindahl,
        "spectral_centroid_Hz": spectral_centroid_Hz,
        "n_distinct_kick_events": n_distinct,
    }


# ---------------------------------------------------------------------------
# Per-body derived metrics for the summary JSON.
# ---------------------------------------------------------------------------

def _per_body_metrics(
    name: str,
    positions: NDArray[np.float64],       # (T, 3)
    orientations: NDArray[np.float64],    # (T, 4)
    velocities: NDArray[np.float64] | None,  # (T, 6) or None
    times: NDArray[np.float64],
    half_y: float,
    mass: float,
    support_y: float,
    body_result: Any,                     # BodyResult from rubric
    late_phase_window_s: float | None,    # B5: 3.0 → enable late_phase block
    impulse_totals: tuple[float, float] | None,  # (cum_J_n, cum_J_t) or None
) -> dict[str, Any]:
    """One entry of summary.json's `bodies[]` list."""
    ys = positions[:, 1]
    body_bottom = ys - half_y
    drift_xz = float(np.hypot(
        positions[-1, 0] - positions[0, 0],
        positions[-1, 2] - positions[0, 2],
    ))
    max_pen_mm = float(max(0.0, support_y - body_bottom.min()) * 1000.0)
    tilts = np.array([quat_to_tilt_deg(q) for q in orientations])
    max_tilt = float(tilts.max())

    # Tail-window y range (last 0.5 s, matching the rubric default), in mm.
    t_end = float(times[-1])
    tail_mask = times >= (t_end - 0.5)
    if tail_mask.sum() < 2:
        tail_mask = np.zeros_like(times, dtype=bool)
        tail_mask[-2:] = True
    tail_y_settle_mm = float((ys[tail_mask].max() - ys[tail_mask].min()) * 1000.0)

    body = {
        "name": name,
        "mass_kg": float(mass),
        "max_tilt_deg": max_tilt,
        "drift_m": drift_xz,
        "max_penetration_mm": max_pen_mm,
        "tail_y_settle_mm": tail_y_settle_mm,
        "rubric_pass": bool(body_result.passed),
    }

    if impulse_totals is not None:
        cum_J_n, cum_J_t = impulse_totals
        body["cum_J_normal"] = float(cum_J_n)
        body["cum_J_tangential"] = float(cum_J_t)
    else:
        body["cum_J_normal"] = 0.0
        body["cum_J_tangential"] = 0.0

    # B5: late-phase metrics over the last `late_phase_window_s` seconds.
    # `n_bumps_last_3s` = count of vy zero-crossings — needs the
    # `velocities` array recorded by `simulate(..., record_velocities=True)`.
    if late_phase_window_s is not None and velocities is not None:
        late_mask = times >= (t_end - late_phase_window_s)
        if late_mask.sum() >= 2:
            vy = velocities[late_mask, 1]
            ys_late = ys[late_mask]
            zc = int(np.sum(np.diff(np.sign(vy)) != 0))
            body["late_phase"] = {
                "y_range_last_3s_mm": float(
                    (ys_late.max() - ys_late.min()) * 1000.0),
                "n_bumps_last_3s": zc,
            }
        else:
            body["late_phase"] = {
                "y_range_last_3s_mm": 0.0,
                "n_bumps_last_3s": 0,
            }
    return body


# ---------------------------------------------------------------------------
# Wall-time percentiles.
# ---------------------------------------------------------------------------

def _wall_time_stats(step_times_s: NDArray[np.float64]) -> dict[str, float]:
    """`wall_time_ms_per_step` in §2.3. Empty input → zeros."""
    t = np.asarray(step_times_s, dtype=np.float64)
    if t.size == 0:
        return {"mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    ms = t * 1000.0
    return {
        "mean": float(ms.mean()),
        "p50": float(np.percentile(ms, 50)),
        "p95": float(np.percentile(ms, 95)),
        "p99": float(np.percentile(ms, 99)),
        "max": float(ms.max()),
    }


# ---------------------------------------------------------------------------
# Top-level summary assembly.
# ---------------------------------------------------------------------------

def compute_summary(
    *,
    run_id: str,
    benchmark: str,
    scene: str,
    mode: str,
    flavor: str,
    params: Mapping[str, Any],
    energy_log: EnergyLog,
    body_info: Mapping[str, tuple],
    positions: Mapping[str, list],
    orientations: Mapping[str, list],
    velocities: Mapping[str, list] | None,
    times: NDArray[np.float64],
    run_result: RunResult,
    bodies_mass: Mapping[str, float],
    support_for: Mapping[str, float],
    wall_step_times_s: NDArray[np.float64],
    wall_total_s: float,
    h: float,
    late_phase_window_s: float | None = None,
    impulse_totals: Mapping[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Build the full `<run_id>_summary.json` payload (`§2.3`).

    `late_phase_window_s` enables the B5 `late_phase` sub-block per body.
    `impulse_totals[name] = (cum_J_normal, cum_J_tangential)` is populated
    by `scripts/run_one.py` when the B2 `_impulse.csv` was logged; passing
    `None` leaves both fields at 0 (B1/B3/B4/B5/B6 case).
    """
    dE_inj = energy_log.dE_modal_injected()
    cum_loss = energy_log.cumulative_rigid_loss()
    cum_inj = energy_log.cumulative_modal_injected()
    cum_ext = energy_log.cumulative_modal_extracted()
    cum_loss_final = float(cum_loss[-1]) if cum_loss.size else 0.0
    cum_inj_final = float(cum_inj[-1]) if cum_inj.size else 0.0
    cum_ext_final = float(cum_ext[-1]) if cum_ext.size else 0.0
    eta = float(params.get("eta", 0.95))
    cum_budget_final = eta * cum_loss_final
    E_modal_peak = float(np.max(energy_log.E_modal())) \
        if len(energy_log) else 0.0

    # `ratio_injected_over_budget`: §2.3. >1 means the §15 ceiling was
    # exceeded (which is exactly what B1 paper-baseline runs should show).
    if cum_budget_final > 0:
        ratio = cum_inj_final / cum_budget_final
    else:
        ratio = 0.0

    invariant_violation = float(energy_log.invariant_violation())

    summary = {
        "run_id": run_id,
        "benchmark": benchmark,
        "scene": scene,
        "mode": mode,
        "flavor": flavor,
        "params": dict(params),
        "n_steps": len(energy_log),
        "wall_time_total_s": float(wall_total_s),
        "wall_time_ms_per_step": _wall_time_stats(wall_step_times_s),
        "rubric_pass": bool(run_result.passed),
        "invariant_max_violation_J": invariant_violation,
        "energy_totals": {
            "cum_E_loss_final_J": cum_loss_final,
            "cum_E_budget_eta_final_J": cum_budget_final,
            "cum_E_injected_final_J": cum_inj_final,
            "cum_E_extracted_final_J": cum_ext_final,
            "E_modal_peak_J": E_modal_peak,
            "ratio_injected_over_budget": float(ratio),
        },
        "injection_signal": _injection_signal_stats(dE_inj, h),
        "bodies": [],
    }

    # Map BodyResult by name for quick lookup.
    by_name = {r.name: r for r in run_result.body_results}

    for name, (_idx, _hx, hy, _hz, _color) in body_info.items():
        pos_arr = np.asarray(positions[name], dtype=np.float64)
        ori_arr = np.asarray(orientations[name], dtype=np.float64)
        vel_arr = (np.asarray(velocities[name], dtype=np.float64)
                   if velocities is not None else None)
        body_payload = _per_body_metrics(
            name=name,
            positions=pos_arr,
            orientations=ori_arr,
            velocities=vel_arr,
            times=np.asarray(times, dtype=np.float64),
            half_y=hy,
            mass=bodies_mass.get(name, 0.0),
            support_y=support_for.get(name, 0.0),
            body_result=by_name[name],
            late_phase_window_s=late_phase_window_s,
            impulse_totals=(impulse_totals.get(name) if impulse_totals
                            else None),
        )
        summary["bodies"].append(body_payload)

    return summary
