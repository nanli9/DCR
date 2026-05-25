"""Side-by-side BJ vs rest-normal benchmark across scenes × modes.

For every (scene, mode) pair where the deformed normal is consumed
(i.e. NOT coevoet — the baseline doesn't use n′ at all), runs:
  * deformed_normal_method = "patch_fit"     (rest-normal-style)
  * deformed_normal_method = "barbic_james"  (full deformed normal)

Records energy logs from both, renders a comparison PNG per pair, and
prints a compact metrics table side-by-side (rubric pass count, max
tilt, x_drift).

Run: uv run python scripts/compare_deformed_normals.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from dcr.benchmark import evaluate_run
from dcr.benchmark.energy_log import EnergyLog
from dcr.benchmark.plots import plot_bj_vs_rest_comparison
from scripts.analyze_patch_mode import (
    SCENE_BUILDERS,
    SCENE_DEFAULT_SUPPORT,
    SCENE_SUPPORT_OVERRIDES,
    SCENE_RUBRIC_OVERRIDES,
)
from scripts.run_scenes import simulate


PLOT_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "plots"


# Modes that actually CONSUME the deformed normal (coevoet does not).
COMPARABLE_MODES = [
    "energy_prescribed",
    "energy_prescribed_point_impulse",
    "energy_prescribed_patch",
]


def _run_one(scene: str, mode: str, deformed_normal_method: str,
             beta: float, n_steps: int, damping_scale: float):
    builder = SCENE_BUILDERS[scene]
    world, coupler, body_info, _mesh, _title = builder(
        velocity_mode=mode, beta=beta, damping_scale=damping_scale,
        deformed_normal_method=deformed_normal_method)
    world.enable_energy_logging = True
    world.energy_log = EnergyLog()
    times, positions, orientations = simulate(
        world, coupler, body_info, n_steps=n_steps)

    default_support = SCENE_DEFAULT_SUPPORT[scene]
    overrides = SCENE_SUPPORT_OVERRIDES[scene]
    support_for = {**{n: default_support for n in body_info}, **overrides}
    result = evaluate_run(
        scene=scene, mode=mode, body_info=body_info,
        positions=positions, orientations=orientations,
        times=np.asarray(times),
        support_for=support_for,
        body_overrides=SCENE_RUBRIC_OVERRIDES.get(scene, {}),
    )
    return world.energy_log, result, body_info


def compare_pair(scene: str, mode: str, beta: float = 0.25,
                 n_steps: int = 800,
                 damping_scale_patch: float = 5.0,
                 damping_scale_other: float = 1.0):
    ds = damping_scale_patch if mode == "energy_prescribed_patch" else damping_scale_other
    print(f"\n----- scene={scene}  mode={mode}  ds={ds} -----", flush=True)

    log_pf, result_pf, _ = _run_one(scene, mode, "patch_fit",
                                    beta, n_steps, ds)
    log_bj, result_bj, _ = _run_one(scene, mode, "barbic_james",
                                    beta, n_steps, ds)

    # Plot.
    plot_path = (PLOT_DIR / f"compare_normals_{scene}_{mode}_b{beta:g}_"
                            f"ds{ds:g}.png")
    plot_bj_vs_rest_comparison(
        log_patch_fit=log_pf, log_barbic_james=log_bj,
        scene=scene, mode=mode, out_path=plot_path)

    # Side-by-side metric table.
    def _summary(log: EnergyLog, result):
        n_pass = sum(1 for b in result.body_results if b.passed)
        n_total = len(result.body_results)
        max_tilt = max(b.metrics["max_tilt_deg"] for b in result.body_results)
        max_drift = max(abs(b.metrics["x_drift_m"])
                        for b in result.body_results)
        E_modal_peak = float(log.E_modal().max()) if len(log) else 0.0
        cum_inj = float(log.cumulative_modal_injected()[-1]) if len(log) else 0.0
        inv = log.invariant_violation()
        return n_pass, n_total, max_tilt, max_drift, E_modal_peak, cum_inj, inv

    n_p, t_p, t_pf, d_pf, e_pf, ci_pf, inv_pf = _summary(log_pf, result_pf)
    n_b, t_b, t_bj, d_bj, e_bj, ci_bj, inv_bj = _summary(log_bj, result_bj)
    print(f"  {'method':<15} {'pass':>7} {'max_tilt':>10} {'max_xdrift':>11} "
          f"{'E_mod_peak':>11} {'∑E_inj':>9} {'§15':>9}")
    print(f"  {'patch_fit':<15} {n_p}/{t_p:<5} {t_pf:>10.2f}° {d_pf:>+11.4f} "
          f"{e_pf:>11.3f} {ci_pf:>9.3f} {inv_pf:>9.2e}")
    print(f"  {'barbic_james':<15} {n_b}/{t_b:<5} {t_bj:>10.2f}° {d_bj:>+11.4f} "
          f"{e_bj:>11.3f} {ci_bj:>9.3f} {inv_bj:>9.2e}")
    print(f"  plot: {plot_path.relative_to(PLOT_DIR.parents[1])}", flush=True)


def main():
    beta = 0.25
    n_steps = 800
    for scene in ["shelf", "truck", "ledge"]:
        for mode in COMPARABLE_MODES:
            try:
                compare_pair(scene, mode, beta=beta, n_steps=n_steps)
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {e}", flush=True)
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
