#!/usr/bin/env python3
"""X5 — performance consolidation at PAPER_CONFIG (one table, paper Tables 1/3 level).

ISOLATED benchmark. Times each non-cargo scene × solver at PAPER_CONFIG on the CPU
host path (the symplectic modal step is host-only), reporting ms/step (mean +
worst-frame), the modal-support overhead vs a rigid-only baseline (support DOF
present but the modal ring frozen), and the passive-clamp overhead. Also sweeps the
mode count k to give a cost-vs-modes curve (accuracy-vs-k lives in X3).

Note (honest): CUDA is NOT timed here — the symplectic modal step runs host-only,
so the paper config's timings are CPU. The device residency + warp-CPU-beats-CUDA
crossover story is a separate axis (see docs/avbd_native/native_dual_solver.md).

Out: benchmarks/paper_eval/x5_perf/out/{perf.csv, perf_modes.csv} + manifest
Run: .venv/bin/python benchmarks/paper_eval/x5_perf/run_perf.py [--frames N]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from benchmarks.paper_eval.paper_config import (
    PAPER_CONFIG, apply_relax, apply_passivity, write_manifest,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}


def _time_run(build_fn, solver, *, frames, freeze=False, clamp=False):
    it, su = PAPER_CONFIG["iterations"], PAPER_CONFIG["substeps"]
    H = build_fn(device="cpu", iterations=it, avbd_substeps=su, solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver)
    sol._modal_symplectic = True
    fz = "_modal_freeze_qdot" if solver == "avbd" else "_freeze_qdot"
    if freeze and hasattr(sol, fz):
        setattr(sol, fz, True)
        sol._modal_symplectic = False   # frozen ⇒ BE (matches probe convention)
    if clamp:
        apply_passivity(sol, solver, enable=True)
    w = H.world
    for _ in range(5):          # warm up (JIT/caches)
        w.step()
    per = np.empty(frames)
    for i in range(frames):
        t0 = time.perf_counter()
        w.step()
        per[i] = (time.perf_counter() - t0) * 1e3
    nb = len(sol._mass) if hasattr(sol, "_mass") else 0
    r = getattr(sol, "_r", 0) or getattr(sol, "_n_modes", 0)
    return dict(mean_ms=float(per.mean()), p50_ms=float(np.median(per)),
                worst_ms=float(per.max()), nb=nb, modes=r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=120)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print(f"### X5 perf @ PAPER_CONFIG (CPU host, {args.frames} frames) ###",
          flush=True)

    rows = []
    for scene, fn in SCENES.items():
        for solver in ("xpbd", "avbd"):
            full = _time_run(fn, solver, frames=args.frames)
            rigid = _time_run(fn, solver, frames=args.frames, freeze=True)
            clamp = _time_run(fn, solver, frames=args.frames, clamp=True)
            overhead = full["mean_ms"] - rigid["mean_ms"]
            clamp_ovh = clamp["mean_ms"] - full["mean_ms"]
            rows.append(dict(
                scene=scene, solver=solver, nb=full["nb"], modes=full["modes"],
                mean_ms=full["mean_ms"], worst_ms=full["worst_ms"],
                rigid_ms=rigid["mean_ms"], modal_overhead_ms=overhead,
                clamp_overhead_ms=clamp_ovh,
                steps_per_s=1000.0 / max(full["mean_ms"], 1e-9)))
            print(f"  {scene:7s}/{solver}: nb={full['nb']} modes={full['modes']}  "
                  f"mean={full['mean_ms']:6.2f}ms worst={full['worst_ms']:6.2f}ms  "
                  f"modal+={overhead:5.2f}ms clamp+={clamp_ovh:5.2f}ms  "
                  f"{1000.0/max(full['mean_ms'],1e-9):5.1f} steps/s", flush=True)

    keys = ["scene", "solver", "nb", "modes", "mean_ms", "worst_ms", "rigid_ms",
            "modal_overhead_ms", "clamp_overhead_ms", "steps_per_s"]
    with open(os.path.join(OUT, "perf.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.4g}" if isinstance(r[k], float) else r[k])
                        for k in keys})
    write_manifest(OUT, "perf.csv", scenes=list(SCENES), solvers=["xpbd", "avbd"],
                   frames=args.frames, device="cpu",
                   note="ms/step at PAPER_CONFIG; modal_overhead vs frozen-ring rigid baseline")
    rt = sum(1 for r in rows if r["mean_ms"] <= 1000.0 / 120.0)
    print(f"\n{rt}/{len(rows)} scene-solver configs are real-time at 120 Hz "
          f"(≤ {1000.0/120.0:.2f} ms/step). wrote perf.csv")


if __name__ == "__main__":
    main()
