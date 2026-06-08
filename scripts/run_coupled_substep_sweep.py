"""V5 — Substep convergence sweep for `--reduced-coupled-avbd`.

Runs the toy scene at substeps ∈ {1, 2, 4, 8, 16, 32}; for each, records:

  - peak |q| during the run
  - peak |qdot|
  - final |q| (steady state)
  - cumulative damping energy ∫P_d·h_substep
  - mean step time (ms)

Writes CSV to `docs/figures/coupled_substep_sweep.csv` and a markdown
summary to stdout. Reports the relative change between successive
substep counts — a converged method should show < 5% change between
substeps=16 and substeps=32.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_one(substeps: int, n_frames: int, mass: float, youngs: float):
    from scenes.reduced_coupled_toy_minimum import build_toy_scene_1

    h = build_toy_scene_1(
        iterations=8,
        mass=mass,
        avbd_substeps=substeps,
        youngs=youngs,
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=5.0e-6,
    )
    c = h.coupler

    h_sub = h.world.h / substeps
    peak_q = 0.0
    peak_qdot = 0.0
    cum_damp_E = 0.0

    t0 = time.perf_counter()
    for _ in range(n_frames):
        h.world.step()
        peak_q = max(peak_q, float(np.linalg.norm(h.rs.q)))
        peak_qdot = max(peak_qdot, c.last_qdot_norm)
        # last_damp_power is qdot^T D_q qdot at end of last substep; we
        # approximate the integrated damping energy as P_d * h_macro
        # (good enough for the sweep — relative comparison only).
        cum_damp_E += c.last_damp_power * h.world.h
    dt = time.perf_counter() - t0
    mean_step_ms = 1000.0 * dt / n_frames

    return {
        "substeps": substeps,
        "h_sub_s":     h_sub,
        "peak_q_m":    peak_q,
        "peak_qdot":   peak_qdot,
        "final_q_m":   float(np.linalg.norm(h.rs.q)),
        "cum_damp_E_J": cum_damp_E,
        "mean_ms":     mean_step_ms,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--mass", type=float, default=0.05)
    ap.add_argument("--youngs", type=float, default=2.0e10)
    ap.add_argument(
        "--substeps", type=int, nargs="+",
        default=[1, 2, 4, 8, 16, 32])
    ap.add_argument(
        "--out-csv",
        default=str(ROOT / "docs" / "figures" / "coupled_substep_sweep.csv"))
    args = ap.parse_args()

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for n in args.substeps:
        print(f"  substeps={n} ...", flush=True)
        rows.append(_run_one(n, args.frames, args.mass, args.youngs))

    fields = ["substeps", "h_sub_s", "peak_q_m", "peak_qdot",
              "final_q_m", "cum_damp_E_J", "mean_ms"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    # Markdown table to stdout.
    print()
    print(f"# V5 substep convergence sweep — coupled-AVBD toy scene")
    print(f"  frames={args.frames}, mass={args.mass} kg, E={args.youngs:.1e} Pa")
    print()
    print("| substeps | peak |q| (µm) | peak |qdot| (mm/s) | "
          "final |q| (µm) | cum damp E (µJ) | step (ms) |")
    print("|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        print(f"| {r['substeps']:>3d} "
              f"| {1e6*r['peak_q_m']:>8.2f} "
              f"| {1e3*r['peak_qdot']:>8.2f} "
              f"| {1e6*r['final_q_m']:>8.2f} "
              f"| {1e6*r['cum_damp_E_J']:>8.2f} "
              f"| {r['mean_ms']:>6.2f} |")

    print()
    if len(rows) >= 2:
        r_last = rows[-1]
        r_prev = rows[-2]
        if r_prev["peak_q_m"] > 1e-12:
            d_peak = (r_last["peak_q_m"] - r_prev["peak_q_m"]) / r_prev["peak_q_m"]
            print(f"  Δ peak|q| between substeps={r_prev['substeps']} and "
                  f"substeps={r_last['substeps']}: {100*d_peak:+.2f}% "
                  f"({'CONVERGED' if abs(d_peak) < 0.05 else 'NOT CONVERGED'})")

    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
