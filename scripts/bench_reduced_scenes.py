#!/usr/bin/env python3
"""Headless baseline / profiling harness for the reduced-coupled AVBD scenes.

Builds each of the four demo scenes (truck / ledge / shelf / dinner) on the
chosen device with the viewer's default solver settings (iters=4, substeps=4,
h=1/120), warms up (so the CUDA graph is captured), times N steps, and reports
ms/step — both `world.step()` wall-clock and the pure solver part
(`world.last_solve_ms`).

Also runs a lightweight residency audit on the device path: it instruments
`warp.array.numpy` / `wp.synchronize*` and counts host readbacks issued during
ONE `solver.step()` (the AVBD + coupler inner loop). The residency contract
(per docs/twobody/warp_gpu_resident.md) is that the iteration loop issues only
`wp.launch` and is CUDA-graph captured; the only permitted host round-trip is
the once-per-macro-step diagnostics readback for the HUD.

    uv run python scripts/bench_reduced_scenes.py --device cuda:0
    uv run python scripts/bench_reduced_scenes.py --scene truck --steps 300
"""
from __future__ import annotations

import argparse
import statistics
import time

import numpy as np

from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge


# Viewer default knobs (scripts/run_reduced_scene_viser.py ScenePreset).
DEFAULT_ITERS = 4
DEFAULT_SUBSTEPS = 4
DEFAULT_H = 1.0 / 120.0


def _build(scene: str, device: str, iters: int, substeps: int, h: float):
    common = dict(device=device, iterations=iters, avbd_substeps=substeps,
                  h=h, to_eigenbasis=True)
    if scene == "dinner":
        return build_reduced_dinner_table(**common)
    if scene == "truck":
        return build_reduced_truck(**common)
    if scene == "shelf":
        return build_reduced_shelf(**common)
    if scene == "ledge":
        return build_reduced_ledge(**common)
    raise ValueError(f"unknown scene {scene!r}")


class _ReadbackCounter:
    """Context manager that counts host readbacks (`wp.array.numpy` and
    `wp.synchronize*`) while active — the residency probe."""

    def __init__(self):
        self.numpy_calls = 0
        self.sync_calls = 0
        self._orig_numpy = None
        self._orig_sync = None
        self._orig_sync_dev = None

    def __enter__(self):
        import warp as wp
        self._orig_numpy = wp.array.numpy
        self._orig_sync = getattr(wp, "synchronize", None)
        self._orig_sync_dev = getattr(wp, "synchronize_device", None)
        counter = self

        def _counting_numpy(arr, *a, **k):
            counter.numpy_calls += 1
            return counter._orig_numpy(arr, *a, **k)

        wp.array.numpy = _counting_numpy
        if self._orig_sync is not None:
            def _counting_sync(*a, **k):
                counter.sync_calls += 1
                return counter._orig_sync(*a, **k)
            wp.synchronize = _counting_sync
        if self._orig_sync_dev is not None:
            def _counting_sync_dev(*a, **k):
                counter.sync_calls += 1
                return counter._orig_sync_dev(*a, **k)
            wp.synchronize_device = _counting_sync_dev
        return self

    def __exit__(self, *exc):
        import warp as wp
        wp.array.numpy = self._orig_numpy
        if self._orig_sync is not None:
            wp.synchronize = self._orig_sync
        if self._orig_sync_dev is not None:
            wp.synchronize_device = self._orig_sync_dev
        return False


def bench_scene(scene: str, device: str, iters: int, substeps: int, h: float,
                warmup: int, steps: int) -> dict:
    handle = _build(scene, device, iters, substeps, h)
    world = handle.world
    coupler = world.reduced_coupled_coupler
    rs = handle.rs

    dev_res = bool(getattr(coupler, "device_resident", False))

    # Warm up: triggers device-buffer alloc, kernel compile, CUDA-graph capture.
    for _ in range(warmup):
        world.step()

    solver = world._solver
    graph_captured = getattr(solver, "_graph", None) is not None

    # Residency probe on ONE pure solver step (the AVBD + coupler inner loop).
    with _ReadbackCounter() as rc:
        solver.step()
    inner_numpy = rc.numpy_calls
    inner_sync = rc.sync_calls

    # Timed window: full world.step() wall-clock + pure-solver ms.
    world_ms = []
    solve_ms = []
    for _ in range(steps):
        t0 = time.perf_counter()
        world.step()
        world_ms.append((time.perf_counter() - t0) * 1e3)
        solve_ms.append(float(getattr(world, "last_solve_ms", float("nan"))))

    return dict(
        scene=scene, device=device, iters=iters, substeps=substeps,
        n_bodies=len(handle.bodies), r=int(rs.r),
        device_resident=dev_res, graph_captured=graph_captured,
        inner_numpy=inner_numpy, inner_sync=inner_sync,
        world_mean=statistics.mean(world_ms),
        world_median=statistics.median(world_ms),
        solve_mean=statistics.mean(solve_ms),
        solve_median=statistics.median(solve_ms),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", default="all",
                    choices=["all", "truck", "ledge", "shelf", "dinner"])
    ap.add_argument("--device", default="cuda:0", choices=["cpu", "cuda:0"])
    ap.add_argument("--iters", type=int, default=DEFAULT_ITERS)
    ap.add_argument("--substeps", type=int, default=DEFAULT_SUBSTEPS)
    ap.add_argument("--h", type=float, default=DEFAULT_H)
    ap.add_argument("--warmup", type=int, default=30)
    ap.add_argument("--steps", type=int, default=200)
    args = ap.parse_args(argv)

    import warp as wp
    wp.init()

    scenes = (["truck", "ledge", "shelf", "dinner"]
              if args.scene == "all" else [args.scene])
    rows = []
    for sc in scenes:
        print(f"[bench] building+timing {sc} on {args.device} "
              f"(iters={args.iters} substeps={args.substeps}) ...", flush=True)
        rows.append(bench_scene(sc, args.device, args.iters, args.substeps,
                                args.h, args.warmup, args.steps))

    print()
    print(f"  Reduced-coupled AVBD baseline — device={args.device}  "
          f"iters={args.iters} substeps={args.substeps}  "
          f"warmup={args.warmup} steps={args.steps}")
    print("  " + "-" * 92)
    hdr = (f"  {'scene':8s} {'bodies':>6s} {'r':>3s} {'resident':>8s} "
           f"{'graph':>5s} {'inner.np':>8s} {'inner.sync':>10s} "
           f"{'world ms':>9s} {'solve ms':>9s}")
    print(hdr)
    print("  " + "-" * 92)
    for r in rows:
        print(f"  {r['scene']:8s} {r['n_bodies']:6d} {r['r']:3d} "
              f"{str(r['device_resident']):>8s} {str(r['graph_captured']):>5s} "
              f"{r['inner_numpy']:8d} {r['inner_sync']:10d} "
              f"{r['world_median']:9.2f} {r['solve_median']:9.2f}")
    print("  " + "-" * 92)
    print("  (world/solve = median ms/step; inner.np/sync = host readbacks "
          "inside ONE solver.step())")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
