"""Per-kernel GPU profiling of the device-resident reduced-modal coupler.

Pure profiling harness (underscore-prefixed throwaway). It does NOT change any
library code — it only:
  * reads `world.last_*_ms` host timers,
  * uses warp's CUDA-event activity timing (`wp.timing_begin/_end`) to attribute
    GPU time per kernel / graph / memcpy,
  * (optionally) monkeypatches the *instance* method `solver._graph_cuda_supported`
    to force the uncaptured launch path so per-kernel GPU times become visible
    (inside a captured graph the inner kernels are hidden behind one graph replay).

Three views:
  1. HOST split      — where solver.step() wall-clock goes (solve/extract/coupler/sync).
  2. GPU activity    — graph-ON: graph replay vs uncaptured kernels vs memcpy/memset.
  3. Per-kernel GPU  — graph-OFF: every kernel's summed GPU ms, coupler vs AVBD.

Usage:
    uv run python scripts/_diag_warp_kernel_profile.py --device cuda:0
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warp as wp

from scenes.reduced_support_shelf import build_reduced_support_shelf

# Coupler kernel name fragments (defined in reduced_coupled_kernels.py). Used to
# split the per-kernel report into "coupler" vs "AVBD core".
_COUPLER_KERNELS = (
    "k_rowforce", "k_hq", "k_g", "k_body", "k_schur", "k_rhs",
    "k_eps_solve", "k_backsub", "k_reduce_diag", "k_anchor",
    "k_eval_basis", "k_iir_precompute", "k_modal_energy", "k_iir_apply",
    "k_passivity", "k_sync_total",
)


def _build(device: str):
    handle = build_reduced_support_shelf(
        h=1.0 / 120.0, device=device, iterations=4, avbd_substeps=4,
        overlay_enabled=False, restart_overlay_each_step=True,
        reduced_support_enabled=True, coupled_avbd=True, to_eigenbasis=True,
    )
    return handle.world


def _filter_name(f: int) -> str:
    if f == wp.TIMING_KERNEL:
        return "kernel"
    if f == wp.TIMING_KERNEL_BUILTIN:
        return "builtin"
    if f == wp.TIMING_GRAPH:
        return "graph"
    if f == wp.TIMING_MEMCPY:
        return "memcpy"
    if f == wp.TIMING_MEMSET:
        return "memset"
    return f"f{f}"


def host_split(world, frames: int, warmup: int) -> None:
    keys = ["last_solve_ms", "last_extract_ms", "last_coupler_ms",
            "last_sync_ms", "last_step_ms"]
    acc = defaultdict(list)
    for f in range(frames):
        world.step()
        if f >= warmup:
            for k in keys:
                acc[k].append(float(getattr(world, k, 0.0)))
    print("\n=== (1) HOST split  (solver.step wall-clock, ms, p50) ===")
    for k in keys:
        a = np.asarray(acc[k])
        print(f"  {k:18s} mean={a.mean():7.3f}  p50={np.percentile(a,50):7.3f}"
              f"  p95={np.percentile(a,95):7.3f}")
    solve = np.asarray(acc["last_solve_ms"])
    step = np.asarray(acc["last_step_ms"])
    rest = step - solve
    print(f"  {'(step - solve)':18s} mean={rest.mean():7.3f}"
          f"  -> post-solve host work (sync/extract/coupler/log)")


def gpu_activity(world, frames: int) -> None:
    """Graph-ON: aggregate GPU activity by filter + by name."""
    wp.synchronize_device(world.device)
    wp.timing_begin(cuda_filter=wp.TIMING_ALL, synchronize=True)
    for _ in range(frames):
        world.step()
    results = wp.timing_end(synchronize=True)

    by_filter = defaultdict(float)
    by_name = defaultdict(lambda: [0.0, 0])  # [elapsed_ms, count]
    for r in results:
        by_filter[_filter_name(r.filter)] += r.elapsed
        by_name[(_filter_name(r.filter), r.name)][0] += r.elapsed
        by_name[(_filter_name(r.filter), r.name)][1] += 1

    print(f"\n=== (2) GPU activity  (graph-ON, {frames} steps, total ms / per-step ms) ===")
    total = sum(by_filter.values())
    for fn in sorted(by_filter, key=lambda k: -by_filter[k]):
        ms = by_filter[fn]
        print(f"  {fn:10s} total={ms:9.3f}  per-step={ms/frames:7.4f}"
              f"  ({100*ms/max(total,1e-9):5.1f}%)")
    print(f"  {'TOTAL':10s} total={total:9.3f}  per-step={total/frames:7.4f}")
    print(f"\n  top GPU activities by name (per-step ms, launches/step):")
    rows = sorted(by_name.items(), key=lambda kv: -kv[1][0])[:18]
    for (fn, name), (ms, cnt) in rows:
        short = name if len(name) <= 46 else name[:43] + "..."
        print(f"    [{fn:6s}] {short:46s} {ms/frames:8.4f}  x{cnt/frames:5.1f}")


def per_kernel_graph_off(world, frames: int) -> None:
    """Graph-OFF (monkeypatch instance): per-kernel GPU ms breakdown."""
    solver = world._solver
    orig = solver._graph_cuda_supported
    # Instance-level override → forces use_graph=False so each kernel launches
    # individually and TIMING_KERNEL can attribute GPU time per kernel.
    solver._graph_cuda_supported = lambda: False  # type: ignore[assignment]
    solver._graph = None
    try:
        wp.synchronize_device(world.device)
        for _ in range(3):  # warm the uncaptured path
            world.step()
        wp.timing_begin(cuda_filter=wp.TIMING_KERNEL, synchronize=True)
        for _ in range(frames):
            world.step()
        results = wp.timing_end(synchronize=True)
    finally:
        solver._graph_cuda_supported = orig  # type: ignore[assignment]
        solver._graph = None

    by_name = defaultdict(lambda: [0.0, 0])
    for r in results:
        nm = r.name.replace("forward kernel ", "").replace("_cuda_kernel", "")
        by_name[nm][0] += r.elapsed
        by_name[nm][1] += 1

    coupler_ms = avbd_ms = 0.0
    rows = []
    for nm, (ms, cnt) in by_name.items():
        is_coupler = any(ck in nm for ck in _COUPLER_KERNELS)
        (coupler_ms := coupler_ms)  # noqa
        if is_coupler:
            coupler_ms += ms
        else:
            avbd_ms += ms
        rows.append((nm, ms, cnt, is_coupler))
    rows.sort(key=lambda t: -t[1])

    n_launch = sum(c for _, _, c, _ in rows)
    print(f"\n=== (3) Per-kernel GPU  (graph-OFF, {frames} steps) ===")
    print(f"  total kernel GPU/step : "
          f"{(coupler_ms+avbd_ms)/frames:7.4f} ms")
    print(f"    coupler kernels/step: {coupler_ms/frames:7.4f} ms  "
          f"({100*coupler_ms/max(coupler_ms+avbd_ms,1e-9):4.1f}%)")
    print(f"    AVBD   kernels/step : {avbd_ms/frames:7.4f} ms  "
          f"({100*avbd_ms/max(coupler_ms+avbd_ms,1e-9):4.1f}%)")
    print(f"  kernel launches/step  : {n_launch/frames:6.1f}")
    print(f"\n  {'kernel':34s} {'ms/step':>9} {'launch/step':>11} {'grp':>4}")
    for nm, ms, cnt, is_c in rows[:28]:
        short = nm if len(nm) <= 34 else nm[:31] + "..."
        tag = "cpl" if is_c else "avbd"
        print(f"  {short:34s} {ms/frames:9.4f} {cnt/frames:11.1f} {tag:>4}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--warmup", type=int, default=40)
    p.add_argument("--prof-frames", type=int, default=40)
    args = p.parse_args(argv)

    if not str(args.device).startswith("cuda"):
        print("This profiler targets cuda:0 (GPU activity timing).")
    world = _build(args.device)
    solver = world._solver

    # warm up + engage device path / graph capture
    for _ in range(args.warmup):
        world.step()
    coupler = world.reduced_coupled_coupler
    print(f"device={args.device}  device_resident="
          f"{getattr(coupler,'device_resident',None)}  "
          f"hooks_device_resident={getattr(solver,'hooks_device_resident',None)}  "
          f"graph_captured={solver._graph is not None}")

    host_split(world, args.frames, args.warmup)
    gpu_activity(world, args.prof_frames)
    per_kernel_graph_off(world, args.prof_frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
