"""Benchmark + profile harness for the SolverXPBD device-residency work.

Measures ms/step for the XPBD solver on representative scenes and, with
--profile, dumps a cProfile hot-spot breakdown of the CPU reference so the
device path targets the real cost. This is the baseline + measurement tool for
the optimization loop (native_dual_solver_build_plan.md Stage 2b).

Usage:
    python3 scripts/bench_xpbd_device.py                 # ms/step table, CPU
    python3 scripts/bench_xpbd_device.py --profile        # cProfile the hot scene
    python3 scripts/bench_xpbd_device.py --device cuda:0  # device path (once built)
"""
from __future__ import annotations

import argparse
import cProfile
import pstats
import time

import numpy as np

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_fem_rigid_cargo import build_cargo_scene

_PROD = {"truck": build_reduced_truck, "ledge": build_reduced_ledge,
         "shelf": build_reduced_shelf, "dinner": build_reduced_dinner_table}


def _xpbd_iters():
    return {"iterations": 16, "avbd_substeps": 6}


_BACKENDS = {                       # label -> (scene device, _force_warp)
    "numpy":   ("cpu", False),
    "warpcpu": ("cpu", True),
    "cuda":    ("cuda:0", False),
}


def build(scene: str, *, backend: str, material: str = "fem_rigid"):
    device, force_warp = _BACKENDS[backend]
    if scene == "cargo":
        h = build_cargo_scene(material, solver="xpbd", device=device,
                              drop_height=0.03, **_xpbd_iters())
    else:
        kw = dict(device=device, solver="xpbd", cargo_material=material,
                  **_xpbd_iters())
        if scene != "dinner":
            kw["impactor_drop_height"] = 0.05
        h = _PROD[scene](**kw)
    if force_warp:
        h.world._solver._force_warp = True
    return h


def n_bodies(handle) -> int:
    s = handle.world._solver
    s._ensure_arrays() if hasattr(s, "_ensure_arrays") else None
    try:
        return int(s.positions().shape[0])
    except Exception:
        return -1


def time_scene(scene: str, *, backend: str, n_steps: int = 100,
               warmup: int = 10, material: str = "fem_rigid") -> dict:
    h = build(scene, backend=backend, material=material)
    for _ in range(warmup):                 # incl. compile + graph capture
        h.world.step()
    t0 = time.perf_counter()
    for _ in range(n_steps):
        h.world.step()
    dt = time.perf_counter() - t0
    ok = bool(np.all(np.isfinite(h.world._solver.positions())))
    return dict(scene=scene, nb=n_bodies(h), ms=1e3 * dt / n_steps, finite=ok)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", default="numpy,warpcpu,cuda")
    ap.add_argument("--scenes", default="cargo,shelf,dinner,truck,ledge")
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--profile", action="store_true")
    ap.add_argument("--profile-scene", default="dinner")
    args = ap.parse_args()

    scenes = [s for s in args.scenes.split(",") if s]
    backends = [b for b in args.backends.split(",") if b]

    if args.profile:
        h = build(args.profile_scene, backend="numpy")
        for _ in range(5):
            h.world.step()
        pr = cProfile.Profile()
        pr.enable()
        for _ in range(40):
            h.world.step()
        pr.disable()
        st = pstats.Stats(pr).sort_stats("cumulative")
        print(f"\n=== cProfile {args.profile_scene} (xpbd, numpy) "
              f"nb={n_bodies(h)} ===")
        st.print_stats(25)
        return

    # ms/step table: rows = scenes, cols = backends, + speedup vs numpy.
    hdr = f"{'scene':<9}{'nb':>4}" + "".join(f"{b:>11}" for b in backends)
    if "numpy" in backends and len(backends) > 1:
        hdr += "".join(f"{'x:'+b:>9}" for b in backends if b != "numpy")
    print("\n" + hdr + f"   ({args.steps} steps, ms/step)")
    print("-" * len(hdr))
    for sc in scenes:
        cells, ms = [], {}
        nb = -1
        for b in backends:
            r = time_scene(sc, backend=b, n_steps=args.steps)
            nb = r["nb"]; ms[b] = r["ms"]
            cells.append(f"{r['ms']:>11.3f}" + ("" if r["finite"] else "!"))
        row = f"{sc:<9}{nb:>4}" + "".join(cells)
        if "numpy" in backends and len(backends) > 1:
            for b in backends:
                if b != "numpy":
                    sp = ms["numpy"] / ms[b] if ms[b] > 0 else 0.0
                    row += f"{sp:>8.2f}x"
        print(row)


if __name__ == "__main__":
    main()
