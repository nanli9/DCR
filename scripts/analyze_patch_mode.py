"""Headless analysis harness across scenes × modes, with pass/fail rubric.

For each (scene, mode), records rigid-body trajectories then evaluates
against `dcr.benchmark.rubric` and prints both the raw metric table and
a per-body pass/fail summary.

Run: uv run python scripts/analyze_patch_mode.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from dcr.benchmark import BodyRubric, evaluate_run, quat_to_tilt_deg
from dcr.benchmark.energy_log import EnergyLog
from dcr.benchmark.plots import plot_energy_timeseries
from scripts.run_scenes import (
    build_ledge_scene,
    build_shelf_scene,
    build_truck_scene,
    simulate,
)


PLOT_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "plots"


SCENE_BUILDERS = {
    "shelf": build_shelf_scene,
    "truck": build_truck_scene,
    "ledge": build_ledge_scene,
}


# Default support-surface height per scene (where most bodies rest).
SCENE_DEFAULT_SUPPORT = {
    "shelf": 0.015,    # slab top
    "truck": 0.03,     # ground_top
    "ledge": 0.04,     # ledge_top
}


# Per-body support overrides (body sits on something other than the
# default support surface).
# ledge:  pedestal_top = ledge_top + 2*pedestal_hy + 0.001 = 0.141
LEDGE_PEDESTAL_TOP = 0.04 + 2 * 0.05 + 0.001
SCENE_SUPPORT_OVERRIDES = {
    "shelf": {},
    "truck": {},
    "ledge": {
        "box_0": LEDGE_PEDESTAL_TOP,
        "box_1": LEDGE_PEDESTAL_TOP,
        "box_2": LEDGE_PEDESTAL_TOP,
    },
}


# Per-body rubric overrides — relax bounds for bodies whose intended
# behavior is something other than "stay still and upright".
SCENE_RUBRIC_OVERRIDES = {
    "shelf": {
        # Drop is the impactor; it falls a long way, so x/z drift is
        # measured relative to its drop position. Tail-y range will be
        # tiny after it settles. Keep default rubric.
    },
    "truck": {
        # Drop bodies are impactors; same as above.
    },
    "ledge": {
        # The boulder is the impactor AND the test subject for rolling
        # response. Rolling is intentional — allow more tilt and drift.
        "boulder": BodyRubric(
            penetration_max_m=0.005,
            max_tilt_deg=90.0,
            x_drift_max_m=0.15,
            z_drift_max_m=0.10,
            tail_y_range_max_m=0.010,
        ),
    },
}


def analyze_run(scene: str, mode: str, beta: float = 0.25,
                n_steps: int = 1500, damping_scale: float = 1.0):
    import sys
    print(f"\n========== scene={scene}  mode={mode}  beta={beta}  "
          f"damping_scale={damping_scale}  steps={n_steps} ==========",
          flush=True)
    builder = SCENE_BUILDERS[scene]
    world, coupler, body_info, _mesh, _title = builder(
        velocity_mode=mode, beta=beta, damping_scale=damping_scale)
    # Turn on energy logging for this run; the world appends one entry
    # per step. Negligible overhead (~one dict per step).
    world.enable_energy_logging = True
    world.energy_log = EnergyLog()
    print(f"  built scene ({len(world.bodies)} bodies), "
          f"simulating {n_steps} steps...", flush=True)
    times, positions, orientations = simulate(
        world, coupler, body_info, n_steps=n_steps)
    sys.stdout.flush()

    # Raw metric table (same as before).
    default_support = SCENE_DEFAULT_SUPPORT[scene]
    overrides = SCENE_SUPPORT_OVERRIDES[scene]
    print(f"{'body':<10} {'min_y':>9} {'max_y':>9} {'penetration':>12}  "
          f"{'max_tilt°':>10} {'x_drift':>9}  {'z_drift':>9}  {'tail_yr':>8}")
    for name, (_idx, _hx, hy, _hz, _color) in body_info.items():
        pos = np.array(positions[name])
        orient = np.array(orientations[name])
        ys = pos[:, 1]
        xs = pos[:, 0]
        zs = pos[:, 2]
        body_bottom = ys - hy
        support_y = overrides.get(name, default_support)
        pen = float(max(0.0, support_y - body_bottom.min()))
        tilts = [quat_to_tilt_deg(q) for q in orient]
        x_drift = float(xs[-1] - xs[0])
        z_drift = float(zs[-1] - zs[0])
        # tail y range over last 0.5s
        times_arr = np.asarray(times)
        tail_mask = times_arr >= (times_arr[-1] - 0.5)
        if tail_mask.sum() < 2:
            tail_mask[-2:] = True
        tail_yr = float(ys[tail_mask].max() - ys[tail_mask].min())
        print(f"{name:<10} {ys.min():>9.4f} {ys.max():>9.4f} {pen:>12.4f}  "
              f"{max(tilts):>10.2f} {x_drift:>+9.4f} {z_drift:>+9.4f}  "
              f"{tail_yr:>8.4f}")

    # Pass/fail rubric.
    support_for = {**{n: default_support for n in body_info},
                   **overrides}
    body_overrides = SCENE_RUBRIC_OVERRIDES.get(scene, {})
    result = evaluate_run(
        scene=scene, mode=mode, body_info=body_info,
        positions=positions, orientations=orientations,
        times=np.asarray(times),
        support_for=support_for,
        body_overrides=body_overrides,
    )
    print()
    for body_result in result.body_results:
        print(f"  {body_result}")
    print(f"  >>> {result.summary()}")

    # Energy plot for this run.
    inv_violation = world.energy_log.invariant_violation()
    inv_str = (f"OK (cumulative injected ≤ η · cumulative loss)"
               if inv_violation <= 1e-9
               else f"VIOLATED by {inv_violation:.3e} J")
    print(f"  §15 invariant: {inv_str}")
    stem = f"energy_{scene}_{mode}_b{beta:g}_ds{damping_scale:g}"
    plot_path = PLOT_DIR / f"{stem}.png"
    csv_path = PLOT_DIR.parent / "data" / f"{stem}.csv"
    title = (f"{scene}/{mode}  β={beta:g}  damping_scale={damping_scale:g}  "
             f"steps={n_steps}")
    plot_energy_timeseries(world.energy_log, title=title, out_path=plot_path)
    world.energy_log.to_csv(csv_path)
    print(f"  energy plot: {plot_path.relative_to(PLOT_DIR.parents[1])}")
    print(f"  energy csv:  {csv_path.relative_to(PLOT_DIR.parents[1])}")
    sys.stdout.flush()
    return result


def main():
    n_steps = 1500
    beta = 0.25
    all_results = []
    # Patch mode gets --damping-scale 5; other modes 1.0.
    for scene in ["shelf", "truck", "ledge"]:
        for mode in ["coevoet", "energy_prescribed_point_impulse",
                     "energy_prescribed_patch"]:
            try:
                ds = 5.0 if mode == "energy_prescribed_patch" else 1.0
                result = analyze_run(scene, mode, beta=beta,
                                     n_steps=n_steps, damping_scale=ds)
                all_results.append(result)
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {e}", flush=True)

    # Final grid: scene × mode pass/fail.
    print("\n\n==================== SUMMARY GRID ====================")
    by_scene_mode = {(r.scene, r.mode): r for r in all_results}
    modes = ["coevoet", "energy_prescribed_point_impulse",
             "energy_prescribed_patch"]
    header = f"{'scene':<8} " + " ".join(f"{m[:18]:>20}" for m in modes)
    print(header)
    for scene in ["shelf", "truck", "ledge"]:
        row = [f"{scene:<8} "]
        for mode in modes:
            r = by_scene_mode.get((scene, mode))
            if r is None:
                row.append(f"{'(error)':>20}")
            else:
                flag = "PASS" if r.passed else "FAIL"
                n_pass = sum(1 for b in r.body_results if b.passed)
                n_total = len(r.body_results)
                row.append(f"{flag} {n_pass}/{n_total}".rjust(20))
        print(" ".join(row))


if __name__ == "__main__":
    main()
