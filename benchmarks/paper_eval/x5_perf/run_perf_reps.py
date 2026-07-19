#!/usr/bin/env python3
"""X5b — CPU-host timings at PAPER_CONFIG with repetitions (paper Table 5).

Same protocol as the benchmark-branch `run_perf.py` (warm-up 5 frames, then
`--frames` timed frames of `world.step()`), repeated `--reps` times with a
fresh scene build per repetition, so the paper can print mean ± std instead of
a single run. Adds the cargo stack (AVBD) for the validation-matrix runtime
cell. The clamp overhead is (clamped mean − unclamped mean) per repetition.

Out: benchmarks/paper_eval/x5_perf/out/{perf_reps.csv, perf_reps_summary.csv}
Run: .venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_reps.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import subprocess
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_cargo_network import build_cargo_network_scene
from benchmarks.paper_eval.paper_config import (
    PAPER_CONFIG, apply_relax, apply_passivity, write_manifest,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _build_stack(**kw):
    kw.pop("solver", None)
    kw["substeps"] = kw.pop("avbd_substeps")   # the cargo builder's kwarg name
    return build_cargo_network_scene(network=True, kind="fem_rigid",
                                     solver="avbd", **kw)


# (scene, solver, builder, symplectic); stack is AVBD-only (the paper's stack
# results are AVBD-native, §4.1–4.2) and runs the default cargo modal path —
# the symplectic step is host non-cargo only (solver_6dof._step_one_body).
CONFIGS = [
    ("shelf", "xpbd", build_reduced_shelf, True),
    ("shelf", "avbd", build_reduced_shelf, True),
    ("ledge", "xpbd", build_reduced_ledge, True),
    ("ledge", "avbd", build_reduced_ledge, True),
    ("dinner", "xpbd", build_reduced_dinner_table, True),
    ("dinner", "avbd", build_reduced_dinner_table, True),
    ("stack", "avbd", _build_stack, False),
]


def _time_run(build_fn, solver, *, frames, clamp, symplectic, budget=None):
    # budget=None keeps PAPER_CONFIG's 16x4 (every frozen number in the ledger
    # was produced that way). C6 passes (K, S) to time the deployed budgets
    # 1x8 / 2x4; nothing else about the run changes.
    it, su = budget or (PAPER_CONFIG["iterations"], PAPER_CONFIG["substeps"])
    H = build_fn(device="cpu", iterations=it, avbd_substeps=su, solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver)
    if symplectic:
        sol._modal_symplectic = True
    if clamp:
        apply_passivity(sol, solver, enable=True)
    w = H.world
    for _ in range(5):
        w.step()
    per = np.empty(frames)
    for i in range(frames):
        t0 = time.perf_counter()
        w.step()
        per[i] = (time.perf_counter() - t0) * 1e3
    return float(per.mean()), float(per.max())


def machine_info():
    chip = ""
    try:
        chip = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        try:
            with open("/proc/cpuinfo") as fh:
                for line in fh:
                    if line.startswith("model name"):
                        chip = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    return dict(platform=platform.platform(), chip=chip,
                python=platform.python_version(), numpy=np.__version__)


def _append(fname, row):
    """Incremental append so a late-config crash loses nothing."""
    path = os.path.join(OUT, fname)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--only", default=None,
                    help="comma list of scenes to run (default all)")
    ap.add_argument("--budget", default=None,
                    help="KxS override, e.g. 1x8 (default: PAPER_CONFIG 16x4)")
    ap.add_argument("--out-prefix", default="perf_reps",
                    help="output basename; C6 writes to a separate file so the "
                         "frozen 16x4 perf_reps.csv is never appended to")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    budget = (tuple(int(v) for v in args.budget.lower().split("x"))
              if args.budget else None)
    mi = machine_info()
    print(f"### X5b perf reps ({args.reps} reps x {args.frames} frames, "
          f"{mi['chip'] or mi['platform']}) ###", flush=True)

    for scene, solver, fn, sym in CONFIGS:
        if only and scene not in only:
            continue
        means, worsts, clamps = [], [], []
        for rep in range(args.reps):
            m, wst = _time_run(fn, solver, frames=args.frames, clamp=False,
                               symplectic=sym, budget=budget)
            mc, _ = _time_run(fn, solver, frames=args.frames, clamp=True,
                              symplectic=sym, budget=budget)
            means.append(m); worsts.append(wst); clamps.append(mc - m)
            _append(f"{args.out_prefix}.csv",
                    dict(scene=scene, solver=solver, rep=rep,
                         mean_ms=m, worst_ms=wst, clamp_ms=mc - m))
        mu, sd = float(np.mean(means)), float(np.std(means))
        cmu, csd = float(np.mean(clamps)), float(np.std(clamps))
        _append(f"{args.out_prefix}_summary.csv",
                dict(scene=scene, solver=solver, mean_ms=mu, std_ms=sd,
                     worst_ms=float(np.max(worsts)),
                     clamp_ms=cmu, clamp_std_ms=csd,
                     steps_per_s=1000.0 / mu, reps=args.reps,
                     frames=args.frames, symplectic=sym))
        print(f"  {scene:6s} {solver}: {mu:7.2f} ± {sd:5.2f} ms  "
              f"worst {np.max(worsts):7.2f}  clamp {cmu:+5.2f} ± {csd:4.2f}  "
              f"{1000.0 / mu:6.1f} steps/s", flush=True)

    write_manifest(OUT, f"{args.out_prefix}.csv",
                   scenes=sorted({c[0] for c in CONFIGS}),
                   solvers=["xpbd", "avbd"], machine=mi,
                   note=f"budget={args.budget or 'PAPER_CONFIG 16x4'}; "
                        f"{args.reps} reps x {args.frames} frames, fresh build "
                        f"per rep; clamp_ms = clamped mean - unclamped mean; "
                        f"stack runs the default cargo modal path (symplectic "
                        f"is host non-cargo only)")
    print(f"\nwrote perf_reps.csv, perf_reps_summary.csv to {OUT}/")


if __name__ == "__main__":
    main()
