#!/usr/bin/env python3
"""X0 — re-run the native energy-loop two-way verification at PAPER_CONFIG.

ISOLATED benchmark. Reuses `scripts.probe_native_energy_loop.run` / `loop_metrics`
READ-ONLY and pins the modal relaxation to 0.7 (symplectic modal step) via
`paper_config.relaxed_builder`, so the energy-loop numbers finally share the SAME
configuration as the material/scene sweeps. Pre-X0 this probe ran at the solver
source-default relax (AVBD 0.1 / XPBD 0.25) — see paper_config.py.

For each scene x solver at the pinned reference budget (16 iters, 4 substeps):
  two-way ratio (object KE peak two-way / one-way), slab ring peak, impactor KE,
  passivity (ring / impactor KE), ring/bounce counts, peak contact forces.

Optionally repeats shelf/XPBD N times as the determinism gate (|spread| <= 5 %).

Out: benchmarks/paper_eval/x0_baseline/out/{energy_loop.csv, determinism.csv} + manifests
Run: .venv/bin/python benchmarks/paper_eval/x0_baseline/run_energy_loop.py
     [--scenes shelf,ledge,dinner] [--solvers avbd,xpbd]
     [--determinism-trials 3] [--smoke]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

# make the repo root importable when run as a file
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scripts.probe_native_energy_loop import run, loop_metrics
from benchmarks.paper_eval.paper_config import (
    PAPER_CONFIG, DETERMINISM_TOL, relaxed_builder, write_manifest,
)

SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def one(scene: str, solver: str, *, n_frames: int) -> dict:
    """Reference-budget two-way + one-way run at PAPER_CONFIG; return metrics."""
    fn = relaxed_builder(SCENES[scene], solver)   # <- pins relax 0.7 post-build
    it = PAPER_CONFIG["iterations"]
    su = PAPER_CONFIG["substeps"]
    # two-way uses the symplectic modal step; the frozen one-way control runs BE
    # (q̇≡0 ⇒ symplectic and BE coincide) exactly as the probe intends.
    rec2 = run(fn, solver, iterations=it, substeps=su, n_frames=n_frames,
               freeze_qdot=False, symplectic=True)
    rec1 = run(fn, solver, iterations=it, substeps=su, n_frames=n_frames,
               freeze_qdot=True, symplectic=True)
    m2, m1 = loop_metrics(rec2), loop_metrics(rec1)
    ratio = (m2["ErestKE_peak"] / m1["ErestKE_peak"]
             if m1["ErestKE_peak"] > 1e-12 else float("inf"))
    passivity = (m2["Eslab_peak"] / m2["Eimp_peak"]
                 if m2["Eimp_peak"] > 1e-12 else 0.0)
    return dict(
        scene=scene, solver=solver,
        twoway_ratio=ratio, passivity=passivity,
        Eimp_peak_J=m2["Eimp_peak"], Eslab_peak_mJ=m2["Eslab_peak"] * 1e3,
        ErestKE_peak_mJ=m2["ErestKE_peak"] * 1e3,
        ErestKE_oneway_mJ=m1["ErestKE_peak"] * 1e3,
        Eslab_oneway_mJ=m1["Eslab_peak"] * 1e3,
        slab_rings=m2["slab_rings"], bounces=m2["bounces"],
        max_lift_mm=m2["max_lift_mm"],
        Frest_peak_N=m2["Frest_peak"], Fimp_peak_N=m2["Fimp_peak"],
        finite=bool(m2["finite"] and m1["finite"]),
    )


CSV_KEYS = ["scene", "solver", "twoway_ratio", "passivity", "Eimp_peak_J",
            "Eslab_peak_mJ", "ErestKE_peak_mJ", "ErestKE_oneway_mJ",
            "Eslab_oneway_mJ", "slab_rings", "bounces", "max_lift_mm",
            "Frest_peak_N", "Fimp_peak_N", "finite"]


def _fmt(v):
    return f"{v:.4g}" if isinstance(v, float) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--solvers", default="avbd,xpbd")
    ap.add_argument("--determinism-trials", type=int, default=3,
                    help="repeat shelf/XPBD N times for the +/-5%% gate (0=skip)")
    ap.add_argument("--smoke", action="store_true",
                    help="60 frames instead of the pinned 220 (wiring check only)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    nf = 60 if args.smoke else PAPER_CONFIG["n_frames_energy"]
    scenes = [s for s in args.scenes.split(",") if s]
    solvers = [s for s in args.solvers.split(",") if s]

    print(f"### X0 energy loop @ PAPER_CONFIG (relax={PAPER_CONFIG['relax']}, "
          f"{PAPER_CONFIG['iterations']}x{PAPER_CONFIG['substeps']}, symplectic, "
          f"n_frames={nf}{' SMOKE' if args.smoke else ''}) ###", flush=True)

    rows = []
    for scene in scenes:
        for solver in solvers:
            r = one(scene, solver, n_frames=nf)
            rows.append(r)
            print(f"  {scene:7s}/{solver}: two-way={r['twoway_ratio']:8.2f}x  "
                  f"passivity={r['passivity']:.3f}  "
                  f"Eslab={r['Eslab_peak_mJ']:8.1f}mJ  Eimp={r['Eimp_peak_J']:6.2f}J  "
                  f"objKE={r['ErestKE_peak_mJ']:7.1f}mJ  rings={r['slab_rings']} "
                  f"bounces={r['bounces']} finite={r['finite']}", flush=True)

    if not args.smoke:
        with open(os.path.join(OUT, "energy_loop.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_KEYS)
            w.writeheader()
            for r in rows:
                w.writerow({k: _fmt(r[k]) for k in CSV_KEYS})
        write_manifest(OUT, "energy_loop.csv", scenes=scenes, solvers=solvers,
                       budget=f"{PAPER_CONFIG['iterations']}x{PAPER_CONFIG['substeps']}",
                       n_frames=nf,
                       note="two-way ratio = object KE peak (symplectic) / (frozen-q̇ BE control)")
        print("  wrote energy_loop.csv (+manifest)")

    # ---- determinism gate: repeat shelf/XPBD, check two-way ratio spread ----
    n_trials = 0 if args.smoke else args.determinism_trials
    if n_trials and n_trials >= 2:
        print(f"\n### determinism gate: shelf/xpbd x{n_trials} "
              f"(tol +/-{DETERMINISM_TOL*100:.0f}%) ###", flush=True)
        trials = []
        for k in range(n_trials):
            r = one("shelf", "xpbd", n_frames=nf)
            trials.append(r["twoway_ratio"])
            print(f"  trial {k}: two-way={r['twoway_ratio']:.4f}x", flush=True)
        lo, hi, mean = min(trials), max(trials), sum(trials) / len(trials)
        spread = (hi - lo) / mean if mean else float("inf")
        ok = spread <= DETERMINISM_TOL
        print(f"  mean={mean:.4f}x  spread={(spread*100):.2f}%  "
              f"-> {'PASS' if ok else 'FAIL'}", flush=True)
        with open(os.path.join(OUT, "determinism.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["scene", "solver", "trial", "twoway_ratio"])
            for k, v in enumerate(trials):
                w.writerow(["shelf", "xpbd", k, f"{v:.6f}"])
            w.writerow([])
            w.writerow(["mean", f"{mean:.6f}", "spread_frac", f"{spread:.6f}",
                        "tol", DETERMINISM_TOL, "pass", ok])
        write_manifest(OUT, "determinism.csv", scenes=["shelf"], solvers=["xpbd"],
                       trials=n_trials, spread_frac=spread, passed=bool(ok))
        print("  wrote determinism.csv (+manifest)")


if __name__ == "__main__":
    main()
