"""Phase 0 baseline timing harness for the reduced-modal coupler GPU-residency work.

Reproduces the user's run (`run_reduced_support_shelf_viser.py --device cuda:0`,
default --mode coupled_iir_modal --reduced-basis eigen) headlessly and reports
where the wall-clock goes, so we can confirm the per-iteration host-sync is the
dominant cost before/after the device port.

Usage:
    uv run python scripts/_diag_coupler_gpu_timing.py --device cpu    --frames 300
    uv run python scripts/_diag_coupler_gpu_timing.py --device cuda:0 --frames 300

This is a throwaway diagnostic (underscore-prefixed); not part of the library.
"""
from __future__ import annotations

import argparse
import sys
import time as _t
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_support_shelf import build_reduced_support_shelf


def run(device: str, frames: int, substeps: int, iterations: int,
        warmup: int, device_resident: bool) -> dict:
    handle = build_reduced_support_shelf(
        h=1.0 / 120.0,
        device=device,
        iterations=iterations,
        avbd_substeps=substeps,
        overlay_enabled=False,
        restart_overlay_each_step=True,
        reduced_support_enabled=True,
        coupled_avbd=True,          # --mode coupled_iir_modal
        to_eigenbasis=True,         # --reduced-basis eigen
    )
    world = handle.world
    coupler = world.reduced_coupled_coupler
    assert coupler is not None, "expected the coupled_iir_modal coupler"

    # Opt-in device-resident hooks (no-op until Phase 1 lands the flag).
    if device_resident and hasattr(world._solver, "hooks_device_resident"):
        world._solver.hooks_device_resident = True

    solve_ms, step_ms = [], []
    n_iter_solves = 0
    for f in range(frames):
        t0 = _t.perf_counter()
        world.step()
        dt = (_t.perf_counter() - t0) * 1000.0
        if f >= warmup:
            step_ms.append(dt)
            solve_ms.append(world.last_solve_ms)
            n_iter_solves = getattr(coupler, "last_n_iter_solves", 0)

    def stats(a):
        a = np.asarray(a)
        return dict(mean=float(a.mean()), p50=float(np.percentile(a, 50)),
                    p95=float(np.percentile(a, 95)))

    return dict(
        device=device, substeps=substeps, iterations=iterations,
        n_iter_solves=int(n_iter_solves),
        step=stats(step_ms), solve=stats(solve_ms),
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--frames", type=int, default=300)
    p.add_argument("--warmup", type=int, default=40)
    p.add_argument("--substeps", type=int, default=4)
    p.add_argument("--iterations", type=int, default=4)
    p.add_argument("--device-resident", action="store_true",
                   help="Enable solver.hooks_device_resident (Phase 1+).")
    p.add_argument("--sweep", action="store_true",
                   help="Sweep substeps*iterations to fingerprint the sync "
                        "cost (last_solve_ms should scale with hook-fire count).")
    args = p.parse_args(argv)

    if args.sweep:
        print(f"[sweep] device={args.device}  "
              f"(last_solve_ms vs substeps*iterations = hook fires/step)")
        print(f"{'substeps':>9} {'iters':>6} {'fires':>6} "
              f"{'solve_p50':>10} {'step_p50':>10}")
        for ss, it in [(1, 1), (1, 4), (2, 4), (4, 4), (4, 8), (8, 8)]:
            r = run(args.device, args.frames, ss, it, args.warmup,
                    args.device_resident)
            fires = ss * it
            print(f"{ss:>9} {it:>6} {fires:>6} "
                  f"{r['solve']['p50']:>10.3f} {r['step']['p50']:>10.3f}")
        return 0

    r = run(args.device, args.frames, args.substeps, args.iterations,
            args.warmup, args.device_resident)
    print(f"[timing] device={r['device']} substeps={r['substeps']} "
          f"iterations={r['iterations']} "
          f"hook_fires/step={r['n_iter_solves']} "
          f"device_resident={args.device_resident}")
    print(f"  solve_ms  mean={r['solve']['mean']:.3f}  "
          f"p50={r['solve']['p50']:.3f}  p95={r['solve']['p95']:.3f}")
    print(f"  step_ms   mean={r['step']['mean']:.3f}  "
          f"p50={r['step']['p50']:.3f}  p95={r['step']['p95']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
