#!/usr/bin/env python3
"""Unified per-run executor for the DCR follow-up benchmark suite.

One invocation = one (scene, mode, flavor, params) run. Produces, in
`<out_dir>/`, the three files mandated by `benchmark/BENCHMARK_PROMPT.md`
§2:

    <run_id>_energy.csv      §2.1   — always
    <run_id>_trajectory.csv  §2.2   — always
    <run_id>_summary.json    §2.3   — always

plus the two optional logs gated by flags:

    <run_id>_impulse.csv     §2.4   — when --log-impulse-decomposition
    <run_id>_timing.csv      §2.5   — when --log-timing

The per-benchmark drivers under `scripts/benchmark/run_b*.py` import
`main()` from this module instead of subprocessing — the world build is
cheap but the import cost is real, and exceptions need to be captured
cleanly into the failed-summary path described in §6.4.

Schema invariants this script guarantees (else the plotter breaks):
- Energy CSV columns are exactly §2.1 (the `EnergyLog` schema).
- Trajectory CSV has one row per (step, body) with tilt_deg / drift_m
  pre-computed (no quaternion library needed downstream).
- Summary JSON has a `status` field that is either "ok" or "failed";
  failed runs carry a `failure_reason` and zero per-step rows.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

# Make `scripts` package importable when run as a script ----
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dcr.benchmark import BodyRubric, evaluate_run, quat_to_tilt_deg
from dcr.benchmark.energy_log import EnergyLog
from dcr.benchmark.impulse_log import ImpulseLog
from dcr.benchmark.timing_log import TimingLog
from dcr.benchmark.summary import compute_summary
from scripts.run_scenes import (
    build_ledge_scene,
    build_shelf_scene,
    build_truck_scene,
    simulate,
    H,
)


SCENE_BUILDERS = {
    "shelf": build_shelf_scene,
    "truck": build_truck_scene,
    "ledge": build_ledge_scene,
}


# Default support height per scene, matching `scripts/analyze_patch_mode.py`.
SCENE_DEFAULT_SUPPORT = {
    "shelf": 0.015,    # slab top
    "truck": 0.03,     # ground_top
    "ledge": 0.04,     # ledge_top
}

# Body-level support overrides (e.g. ledge boulder sits on pedestal_top).
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

# Per-body rubric overrides — matches `scripts/analyze_patch_mode.py`.
# The ledge boulder is the impactor AND test subject for rolling response;
# rolling is intentional so allow more tilt + drift.
SCENE_RUBRIC_OVERRIDES = {
    "shelf": {},
    "truck": {},
    "ledge": {
        "boulder": BodyRubric(
            penetration_max_m=0.005,
            max_tilt_deg=90.0,
            x_drift_max_m=0.15,
            z_drift_max_m=0.10,
            tail_y_range_max_m=0.010,
        ),
    },
}


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Single-run benchmark executor "
                    "(see benchmark/BENCHMARK_PROMPT.md §7).",
    )
    p.add_argument("--scene", required=True,
                   choices=sorted(SCENE_BUILDERS),
                   help="Scene builder to invoke.")
    p.add_argument("--mode", required=True,
                   choices=("coevoet",
                            "energy_prescribed",
                            "energy_prescribed_point_impulse",
                            "energy_prescribed_patch"),
                   help="DCR velocity mode.")
    p.add_argument("--flavor", default="rest",
                   choices=("rest", "patch_fit", "barbic_james"),
                   help="Deformed-normal flavor.")
    p.add_argument("--h", type=float, default=None,
                   help="Rigid timestep h in s. Default uses each scene's "
                        "builder default (H=5e-3). Spec §4 nominally uses "
                        "0.01; the B7 h-sweep varies this.")
    p.add_argument("--eta", type=float, default=0.95,
                   help="Transfer efficiency η (spec §4 default 0.95).")
    p.add_argument("--beta", type=float, default=0.25,
                   help="Energy response β (spec §4 default 0.25).")
    p.add_argument("--duration", type=float, default=4.0,
                   help="Simulated duration in seconds (spec §4 default 4).")
    p.add_argument("--damping-scale", type=float, default=1.0,
                   dest="damping_scale")
    p.add_argument("--restitution", type=float, default=0.15,
                   help="Logged-only; per-body restitution already set in "
                        "scene builders.")
    p.add_argument("--material", default=None,
                   choices=("wood", "steel"),
                   help="Override slab material (spec §5.5 B5). "
                        "Default keeps each scene's paper-matching material.")
    p.add_argument("--causal-gating", action="store_true",
                   dest="causal_gating",
                   help="Enable contact-causal modal gates (patch mode).")
    p.add_argument("--run-id", required=True, dest="run_id",
                   help="Run identifier; used as filename stem.")
    p.add_argument("--out-dir", required=True, dest="out_dir",
                   type=Path)
    p.add_argument("--benchmark", default="",
                   help="Benchmark identifier (B1..B6); written into summary.")
    p.add_argument("--log-paper-side-channel", action="store_true",
                   dest="log_paper_side_channel",
                   help="Enable paper-baseline modal-injection accounting "
                        "(spec §6.1). Implies paper_baseline_mode on the "
                        "coupler — applies only when --mode coevoet.")
    p.add_argument("--log-impulse-decomposition", action="store_true",
                   dest="log_impulse_decomposition",
                   help="Write per-contact <run_id>_impulse.csv (B2; §2.4).")
    p.add_argument("--log-timing", action="store_true",
                   dest="log_timing",
                   help="Write per-step <run_id>_timing.csv (B6; §2.5).")
    p.add_argument("--late-phase-window-s", type=float, default=None,
                   dest="late_phase_window_s",
                   help="When set, summary.json's per-body block gains "
                        "`late_phase.{y_range_last_3s_mm, n_bumps_last_3s}` "
                        "over this trailing window (B5: 3.0).")
    return p


# ---------------------------------------------------------------------------
# Trajectory CSV writer (§2.2).
# ---------------------------------------------------------------------------

def _write_trajectory_csv(
    path: Path,
    times: list[float],
    body_info: dict,
    positions: dict[str, list],
    orientations: dict[str, list],
    velocities: dict[str, list],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "step", "t", "body_name",
        "x", "y", "z",
        "qx", "qy", "qz", "qw",
        "vx", "vy", "vz", "wx", "wy", "wz",
        "tilt_deg", "drift_m",
    ]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        n_steps = len(times)
        for name in body_info:
            pos = np.asarray(positions[name], dtype=np.float64)
            ori = np.asarray(orientations[name], dtype=np.float64)
            vel = np.asarray(velocities[name], dtype=np.float64)
            x0, z0 = pos[0, 0], pos[0, 2]
            for step in range(n_steps):
                q = ori[step]  # (w, x, y, z) per project convention
                p = pos[step]
                v = vel[step]  # [vx, vy, vz, wx, wy, wz]
                tilt_deg = quat_to_tilt_deg(q)
                drift_m = float(np.hypot(p[0] - x0, p[2] - z0))
                w.writerow([
                    step, f"{times[step]:.6f}", name,
                    f"{p[0]:.6e}", f"{p[1]:.6e}", f"{p[2]:.6e}",
                    f"{q[1]:.6e}", f"{q[2]:.6e}", f"{q[3]:.6e}",
                    f"{q[0]:.6e}",
                    f"{v[0]:.6e}", f"{v[1]:.6e}", f"{v[2]:.6e}",
                    f"{v[3]:.6e}", f"{v[4]:.6e}", f"{v[5]:.6e}",
                    f"{tilt_deg:.6f}", f"{drift_m:.6e}",
                ])


# ---------------------------------------------------------------------------
# Body-mass collection
# ---------------------------------------------------------------------------

def _body_masses(world, body_info: dict) -> dict[str, float]:
    return {
        name: float(world.bodies[v[0]].mass)
        for name, v in body_info.items()
    }


# ---------------------------------------------------------------------------
# Main entry point (callable from drivers)
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute a single benchmark run and write the four spec files.

    Returns the summary dict on success. On failure, writes a stub
    summary with `status: failed` and re-raises (so drivers can capture
    the traceback into a `.log` file per §6.4 then continue).
    """
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id

    # --- 1. Build the scene ---------------------------------------------------
    builder = SCENE_BUILDERS[args.scene]
    # Coupler kwargs — flavor maps directly to deformed_normal_method.
    builder_kwargs = dict(
        velocity_mode=args.mode,
        beta=args.beta,
        damping_scale=args.damping_scale,
        deformed_normal_method=args.flavor,
        causal_gating=args.causal_gating,
        eta=args.eta,
        material=args.material,
        # `paper_baseline_mode` is the §6.1 side-channel toggle: bypass
        # the passive-α clamp so the paper baseline shows the unbounded
        # modal injection that gives B1 its headline contrast. We map
        # --log-paper-side-channel onto it (only meaningful with
        # mode=coevoet — for any other mode it would silently break the
        # §15 invariant the run is supposed to demonstrate).
        paper_baseline_mode=(args.log_paper_side_channel
                             and args.mode == "coevoet"),
    )
    if args.h is not None:
        builder_kwargs["h"] = args.h

    world, coupler, body_info, _mesh, _title = builder(**builder_kwargs)

    # Always-on energy logging — the summary needs it.
    world.enable_energy_logging = True
    world.energy_log = EnergyLog()

    # B2: per-contact impulse log. Populates body_name_map so the §2.4
    # `body_name` column is filled with the friendly scene-builder names.
    if args.log_impulse_decomposition:
        world.enable_impulse_logging = True
        world.impulse_log = ImpulseLog()
        world.body_name_map = {
            v[0]: name for name, v in body_info.items()
        }

    # B6: per-step timing log.
    if args.log_timing:
        world.enable_timing_log = True
        world.timing_log = TimingLog()

    # --- 2. Simulate, recording wall times per step ---------------------------
    n_steps = int(round(args.duration / world.h))
    step_wall_times = np.zeros(n_steps, dtype=np.float64)

    # We use `simulate(..., record_velocities=True)` so the trajectory
    # CSV can include vy / wx / ... without a second pass. The settle
    # phase inside `simulate()` is not timed (it precedes the recording
    # loop) — wall-time stats target the "real" simulation window.
    t_total_start = time.perf_counter()
    times, positions, orientations, velocities = simulate(
        world, coupler, body_info, n_steps=n_steps,
        record_velocities=True,
    )
    wall_total = time.perf_counter() - t_total_start

    # NOTE: simulate() doesn't currently expose per-step wall times; we
    # approximate them as `wall_total / n_steps` for the summary stats.
    # The B6 `_timing.csv` (when --log-timing is set) is the canonical
    # per-step record; the summary's `wall_time_ms_per_step` percentiles
    # therefore degenerate to a single bucket on non-B6 runs. Drivers
    # that need per-step resolution should use --log-timing.
    if n_steps > 0:
        step_wall_times[:] = wall_total / n_steps

    # --- 3. Rubric -----------------------------------------------------------
    default_support = SCENE_DEFAULT_SUPPORT[args.scene]
    overrides = SCENE_SUPPORT_OVERRIDES[args.scene]
    support_for = {**{n: default_support for n in body_info}, **overrides}
    body_overrides = SCENE_RUBRIC_OVERRIDES.get(args.scene, {})
    run_result = evaluate_run(
        scene=args.scene, mode=args.mode, body_info=body_info,
        positions=positions, orientations=orientations,
        times=np.asarray(times),
        support_for=support_for,
        body_overrides=body_overrides,
    )

    # --- 4. Write energy CSV (§2.1) ------------------------------------------
    energy_csv = out_dir / f"{run_id}_energy.csv"
    world.energy_log.to_csv(energy_csv)

    # --- 5. Write trajectory CSV (§2.2) --------------------------------------
    trajectory_csv = out_dir / f"{run_id}_trajectory.csv"
    _write_trajectory_csv(
        trajectory_csv, times, body_info, positions, orientations, velocities,
    )

    # --- 5b. Write impulse CSV (§2.4) when B2 logging is on -------------------
    impulse_totals = None
    if args.log_impulse_decomposition and world.impulse_log is not None:
        impulse_csv = out_dir / f"{run_id}_impulse.csv"
        world.impulse_log.to_csv(impulse_csv)
        impulse_totals = world.impulse_log.cumulative_J_per_body()

    # --- 5c. Write timing CSV (§2.5) when B6 logging is on --------------------
    if args.log_timing and world.timing_log is not None:
        # simulate() resets the timing log post-settle, so the entries
        # are already aligned 1:1 with the trajectory CSV.
        timing_csv = out_dir / f"{run_id}_timing.csv"
        world.timing_log.to_csv(timing_csv)
        ms_per_step = np.array(
            [e.t_total_step_ms for e in world.timing_log.entries],
            dtype=np.float64,
        )
        if ms_per_step.size > 0:
            step_wall_times[:ms_per_step.size] = ms_per_step * 1e-3

    # --- 6. Compute + write summary JSON (§2.3) ------------------------------
    params = {
        "eta": float(args.eta),
        "beta": float(args.beta),
        "h": float(world.h),
        "duration_s": float(args.duration),
        "damping_scale": float(args.damping_scale),
        "restitution": float(args.restitution),
        "material": args.material if args.material is not None else "default",
        "causal_gating": bool(args.causal_gating),
    }

    summary = compute_summary(
        run_id=run_id,
        benchmark=args.benchmark,
        scene=args.scene,
        mode=args.mode,
        flavor=args.flavor,
        params=params,
        energy_log=world.energy_log,
        body_info=body_info,
        positions=positions,
        orientations=orientations,
        velocities=velocities,
        times=np.asarray(times),
        run_result=run_result,
        bodies_mass=_body_masses(world, body_info),
        support_for=support_for,
        wall_step_times_s=step_wall_times,
        wall_total_s=wall_total,
        h=world.h,
        late_phase_window_s=args.late_phase_window_s,
        impulse_totals=impulse_totals,
    )
    summary["status"] = "ok"

    summary_json = out_dir / f"{run_id}_summary.json"
    with open(summary_json, "w") as f:
        json.dump(summary, f, indent=2)

    print(
        f"[run_one] {run_id}: {len(world.energy_log)} steps, "
        f"wall={wall_total:.2f}s, rubric={'PASS' if run_result.passed else 'FAIL'}, "
        f"cum_E_injected={summary['energy_totals']['cum_E_injected_final_J']:.3f} J, "
        f"§15 violation={summary['invariant_max_violation_J']:.2e} J",
        flush=True,
    )
    return summary


def write_failed_summary(out_dir: Path, run_id: str, benchmark: str,
                         scene: str, mode: str, flavor: str,
                         params: dict, exc: BaseException) -> None:
    """Drop a `<run_id>_summary.json` with `status: failed` so the
    manifest writer can still include the run per §6.4."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "benchmark": benchmark,
        "scene": scene,
        "mode": mode,
        "flavor": flavor,
        "params": params,
        "status": "failed",
        "failure_reason": f"{type(exc).__name__}: {exc}",
    }
    with open(out_dir / f"{run_id}_summary.json", "w") as f:
        json.dump(payload, f, indent=2)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        run(args)
        return 0
    except Exception as exc:
        traceback.print_exc()
        write_failed_summary(
            Path(args.out_dir), args.run_id, args.benchmark,
            args.scene, args.mode, args.flavor,
            {"eta": args.eta, "beta": args.beta, "duration_s": args.duration,
             "damping_scale": args.damping_scale,
             "material": args.material or "default",
             "causal_gating": args.causal_gating},
            exc,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
