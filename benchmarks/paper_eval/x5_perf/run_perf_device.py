#!/usr/bin/env python3
"""E7 device arm / G3a — real-time reconciliation on the CUDA device path.

The companion `run_perf.py` times the SYMPLECTIC CPU-host path (the passivity-
validated correctness path) at 29-58 ms/step -- not real-time at h=1/120. This
harness times the path a reviewer will ask about: the device-resident native
co-solved (z,q) AVBD solver (`_solve_q_block_device`, the warp modal-solve +
full-substep CUDA-graph capture landed in f94c850) on `device="cuda:0"`. This is
the path whose "0.9-2.4 ms (unvalidated)" number the plan (experiment_plan.md G3)
flagged as needing CUDA to validate.

Two products:

(1) perf_device.csv -- scenes x 3 arms at PAPER_CONFIG (relax 0.7, 16x4, h=1/120):
      baseline  modal ring frozen (rigid cost floor, support DOF present)
      coupling  two-way modal support DOF live, passivity clamp OFF
      clamp     coupling + passivity clamp ON (AVBD monitor-only ledger, §15)

(2) perf_device_budget.csv -- dinner+ledge x budget sweep {8x1..32x4}, clamp ON:
      the interactive-rate-vs-budget curve and the 120 Hz real-time crossover.
      Shows the passivity ledger stays satisfied at EVERY budget device-resident
      (the clamp is what lets you drop the budget to real-time without blow-up).

GPU timing discipline: `wp.synchronize_device` brackets every timed step (measure
GPU execution, not async launch-enqueue). 10 warm-up steps (JIT + graph capture).

Run: ~/dcr-venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_device.py \
        --frames 200 --device cuda:0 [--scenes dinner,ledge,shelf,truck]
"""
from __future__ import annotations

import argparse
import csv
import inspect
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import warp as wp

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_truck import build_reduced_truck

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# PAPER_CONFIG (inlined; server copy lacks paper_config.py). Mirrors it exactly.
RELAX = 0.7
HZ = 120.0
RT_MS = 1000.0 / HZ

SCENES = {
    "shelf": build_reduced_shelf,
    "ledge": build_reduced_ledge,
    "dinner": build_reduced_dinner_table,
    "truck": build_reduced_truck,
}


def _build(build_fn, iters, subs, device):
    """Support scene device-resident, cargo rigid (`_solve_q_block_device` path
    with full-substep capture). Mirrors run_native_scenes_viser's `cand`."""
    rd = str(device).startswith("cuda")
    cand = dict(
        device=device, solver="avbd", device_resident=rd,
        cargo_material=None,               # rigid cargo -> device-resident support q-block
        iterations=int(iters), avbd_substeps=int(subs),
        support_basis="fem",               # dinner: modal basis = GT operator eigenbasis
    )
    params = inspect.signature(build_fn).parameters
    kw = {k: v for k, v in cand.items() if k in params}
    return build_fn(**kw)


def _ledger_state(sol):
    """(cum_modal_gain, eta*cum_rigid_loss, passive?) or (None,None,None)."""
    led = getattr(sol, "_psv_ledger", None)
    if led is None:
        return None, None, None
    gain = float(getattr(led, "cum_modal_gain", 0.0))
    cap = float(getattr(led, "eta", 1.0)) * float(getattr(led, "cum_rigid_loss", 0.0))
    tol = float(getattr(led, "tol", 0.0))
    return gain, cap, bool(gain <= cap + tol)


def _time_run(build_fn, scene, *, device, frames, iters, subs, arm):
    H = _build(build_fn, iters, subs, device)
    sol = H.world._solver
    sol._modal_relax = float(RELAX)
    if hasattr(sol, "_modal_symplectic"):
        sol._modal_symplectic = False      # device path = co-solved constraint, not host symplectic
    if arm == "baseline":
        if hasattr(sol, "_modal_freeze_qdot"):
            sol._modal_freeze_qdot = True
    elif arm == "clamp":
        sol._enforce_modal_passivity = True
        sol._modal_eta = 1.0
        if hasattr(sol, "_psv_monitor_only"):
            sol._psv_monitor_only = True   # AVBD empirically passive -> monitor+assert

    w = H.world
    dev = wp.get_device(device) if str(device).startswith("cuda") else None

    def _sync():
        if dev is not None:
            wp.synchronize_device(dev)

    for _ in range(10):                    # warm up: JIT, kernel cache, graph capture
        w.step()
    _sync()
    per = np.empty(frames)
    for i in range(frames):
        _sync()
        t0 = time.perf_counter()
        w.step()
        _sync()
        per[i] = (time.perf_counter() - t0) * 1e3

    nb = len(sol._mass) if hasattr(sol, "_mass") else 0
    r = getattr(sol, "_r", 0) or getattr(sol, "_n_modes", 0)
    graph = getattr(sol, "_substep_graph", None)
    gain, cap, passive = _ledger_state(sol)
    return dict(mean_ms=float(per.mean()), p50_ms=float(np.median(per)),
                worst_ms=float(per.max()), std_ms=float(per.std()),
                nb=nb, modes=int(r), captured=bool(graph is not None),
                gain=gain, cap=cap, passive=passive)


def _gpu_name():
    try:
        return subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL).decode().strip().splitlines()[0]
    except Exception:
        return "unknown"


def _manifest(name, device, gpu, frames, **extra):
    m = dict(figure=name, stage="E7-device", generated_utc=
             datetime.now(timezone.utc).isoformat(timespec="seconds"),
             device=device, gpu=gpu, warp=wp.__version__, numpy=np.__version__,
             python=platform.python_version(), relax=RELAX, frames=frames)
    m.update(extra)
    with open(os.path.join(OUT, os.path.splitext(name)[0] + ".config.json"), "w") as fh:
        json.dump(m, fh, indent=2)


def _write_csv(name, keys, rows):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (f"{r[k]:.5g}" if isinstance(r[k], float) else r[k])
                         for k in keys})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--scenes", default="dinner,ledge,shelf,truck")
    ap.add_argument("--fixed", default="16x4", help="PAPER_CONFIG budget for the 3-arm table")
    ap.add_argument("--budgets", default="8x1,8x2,16x2,16x4,32x4",
                    help="budget sweep (clamp on) for dinner+ledge crossover")
    ap.add_argument("--sweep-scenes", default="dinner,ledge")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    f_it, f_su = (int(x) for x in args.fixed.split("x"))

    wp.init()
    gpu = _gpu_name()
    print(f"### E7 device arm on {args.device} ({gpu}) warp {wp.__version__}, "
          f"{args.frames} frames ###", flush=True)

    # ---- (1) fixed-budget 3-arm table -------------------------------------- #
    print(f"\n-- perf_device.csv: 3 arms @ {args.fixed} --", flush=True)
    rows = []
    for scene in scenes:
        fn = SCENES[scene]
        base = _time_run(fn, scene, device=args.device, frames=args.frames,
                         iters=f_it, subs=f_su, arm="baseline")
        coup = _time_run(fn, scene, device=args.device, frames=args.frames,
                         iters=f_it, subs=f_su, arm="coupling")
        clmp = _time_run(fn, scene, device=args.device, frames=args.frames,
                         iters=f_it, subs=f_su, arm="clamp")
        row = dict(
            scene=scene, device=args.device, budget=args.fixed, nb=coup["nb"],
            modes=coup["modes"], baseline_ms=base["mean_ms"],
            coupling_ms=coup["mean_ms"], clamp_ms=clmp["mean_ms"],
            worst_ms=coup["worst_ms"], std_ms=coup["std_ms"],
            modal_overhead_ms=coup["mean_ms"] - base["mean_ms"],
            clamp_overhead_ms=clmp["mean_ms"] - coup["mean_ms"],
            steps_per_s=1000.0 / max(coup["mean_ms"], 1e-9),
            rt_factor_120hz=RT_MS / max(coup["mean_ms"], 1e-9),
            realtime_120hz=bool(coup["mean_ms"] <= RT_MS),
            captured=coup["captured"], clamp_captured=clmp["captured"],
            clamp_gain=clmp["gain"], clamp_cap=clmp["cap"],
            clamp_passive=clmp["passive"])
        rows.append(row)
        print(f"  {scene:7s}: nb={row['nb']} modes={row['modes']}  "
              f"base={base['mean_ms']:6.2f} coup={coup['mean_ms']:6.2f} "
              f"clamp={clmp['mean_ms']:6.2f} ms  modal+={row['modal_overhead_ms']:5.2f} "
              f"clamp+={row['clamp_overhead_ms']:5.2f}  {row['steps_per_s']:6.1f} st/s "
              f"{row['rt_factor_120hz']:4.2f}x120Hz cap={coup['captured']}/{clmp['captured']} "
              f"passive={clmp['passive']}", flush=True)
    _write_csv("perf_device.csv",
               ["scene", "device", "budget", "nb", "modes", "baseline_ms",
                "coupling_ms", "clamp_ms", "worst_ms", "std_ms", "modal_overhead_ms",
                "clamp_overhead_ms", "steps_per_s", "rt_factor_120hz", "realtime_120hz",
                "captured", "clamp_captured", "clamp_gain", "clamp_cap", "clamp_passive"],
               rows)
    _manifest("perf_device.csv", args.device, gpu, args.frames, scenes=scenes,
              budget=args.fixed,
              note="device-resident native co-solved (z,q) AVBD; cargo rigid; "
                   "coupling=two-way modal support DOF; clamp=passivity ledger monitor")

    # ---- (2) budget sweep, clamp on ---------------------------------------- #
    sweep_scenes = [s.strip() for s in args.sweep_scenes.split(",") if s.strip()]
    budgets = [b.strip() for b in args.budgets.split(",") if b.strip()]
    print(f"\n-- perf_device_budget.csv: {sweep_scenes} x {budgets} (clamp on) --",
          flush=True)
    brows = []
    for scene in sweep_scenes:
        fn = SCENES[scene]
        for b in budgets:
            it, su = (int(x) for x in b.split("x"))
            r = _time_run(fn, scene, device=args.device, frames=args.frames,
                          iters=it, subs=su, arm="clamp")
            row = dict(scene=scene, budget=b, iters=it, substeps=su, modes=r["modes"],
                       mean_ms=r["mean_ms"], worst_ms=r["worst_ms"], std_ms=r["std_ms"],
                       steps_per_s=1000.0 / max(r["mean_ms"], 1e-9),
                       rt_factor_120hz=RT_MS / max(r["mean_ms"], 1e-9),
                       realtime_120hz=bool(r["mean_ms"] <= RT_MS),
                       captured=r["captured"], gain=r["gain"], cap=r["cap"],
                       passive=r["passive"])
            brows.append(row)
            rt = "RT" if row["realtime_120hz"] else "  "
            print(f"  {scene:7s} {b:5s}: {r['mean_ms']:6.2f} ms  "
                  f"{row['steps_per_s']:6.1f} st/s {row['rt_factor_120hz']:4.2f}x [{rt}] "
                  f"passive={r['passive']}", flush=True)
    _write_csv("perf_device_budget.csv",
               ["scene", "budget", "iters", "substeps", "modes", "mean_ms",
                "worst_ms", "std_ms", "steps_per_s", "rt_factor_120hz",
                "realtime_120hz", "captured", "gain", "cap", "passive"], brows)
    _manifest("perf_device_budget.csv", args.device, gpu, args.frames,
              scenes=sweep_scenes, budgets=budgets,
              note="clamp-on budget sweep; passivity ledger must hold at every budget")

    rt = sum(1 for r in rows if r["realtime_120hz"])
    print(f"\n{rt}/{len(rows)} scenes real-time at 120 Hz @ {args.fixed} on {args.device}. "
          f"wrote out/perf_device.csv + perf_device_budget.csv")


if __name__ == "__main__":
    main()
