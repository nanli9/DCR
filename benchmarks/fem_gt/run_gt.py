"""All-FEM ground truth for every production scene (G1: every body FEM).

    python -m benchmarks.fem_gt.run_gt --scene dinner
    python -m benchmarks.fem_gt.run_gt --scene all --quick

Builds the native scene (rigid cargo mode — only the geometry is mirrored),
converts every body to a full-FEM box + the corner-fixed FEM support slab
(`benchmarks/fem_gt/common.py`), runs the X3 two-phase settle/release
protocol, and writes `benchmarks/fem_gt/out/<scene>_gt.{csv,json}`.

The convergent signal is the support deflection field / mid-span u_y and the
interval-averaged contact ledger (validation plan §6.1) — launch KE is
contact-model-limited, use it only as a secondary.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.fem_gt.common import (      # noqa: E402
    SUPPORTS, gt_sim_from_handle, run_scene_gt,
)

SCENES = ("truck", "ledge", "shelf", "dinner", "cargo")


def _build_handle(scene: str):
    """Native scene in rigid-cargo mode (geometry donor only) + impactor name."""
    if scene == "cargo":
        from scenes.reduced_cargo_network import build_cargo_network_scene
        return build_cargo_network_scene(kind="rigid"), "impactor"
    builders = {
        "truck": "scenes.reduced_truck:build_reduced_truck",
        "ledge": "scenes.reduced_ledge:build_reduced_ledge",
        "shelf": "scenes.reduced_shelf:build_reduced_shelf",
        "dinner": "scenes.reduced_dinner_table:build_reduced_dinner_table",
    }
    mod_name, fn_name = builders[scene].split(":")
    import importlib
    handle = getattr(importlib.import_module(mod_name), fn_name)()
    imp_name = next(b.name for b in handle.bodies
                    if b.dcr_idx == handle.impactor_idx)
    return handle, imp_name


class _CargoHandleAdapter:
    """Adapt `CargoNetworkHandle` (cubes dict) to the `handle.bodies` shape
    `gt_sim_from_handle` consumes."""

    class _B:
        def __init__(self, name, dcr_idx, half):
            self.name = name
            self.dcr_idx = dcr_idx
            self.half_extents = half
            self.orientation_wxyz = (1.0, 0.0, 0.0, 0.0)

    def __init__(self, h):
        self.world = h.world
        # avbd idx == desc idx ordering differs; recover dcr idx per name
        by_avbd = {int(d.avbd_body.index): i
                   for i, d in enumerate(h.world._descs)
                   if d.avbd_body is not None}
        self.bodies = []
        for name, cube in h.cubes.items():
            half = tuple(getattr(cube, "half_extents", None)
                         or (cube.half_extent,) * 3)
            self.bodies.append(
                self._B(name, by_avbd[h.avbd_idx[name]], half))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", default="all",
                    choices=SCENES + ("all",))
    ap.add_argument("--h-fine", type=float, default=5e-5)
    ap.add_argument("--t-settle", type=float, default=0.4)
    ap.add_argument("--t-run", type=float, default=1.2)
    ap.add_argument("--body-youngs", type=float, default=1.0e6,
                    help="body FEM Young's modulus (match the native cargo "
                         "default so both arms share the per-body operator)")
    ap.add_argument("--quick", action="store_true",
                    help="smoke settings: h=1e-4, settle 0.15 s, run 0.3 s")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    if args.quick:
        args.h_fine, args.t_settle, args.t_run = 1e-4, 0.15, 0.3

    scenes = SCENES if args.scene == "all" else (args.scene,)
    for scene in scenes:
        handle, imp_name = _build_handle(scene)
        if scene == "cargo":
            handle = _CargoHandleAdapter(handle)
        t0 = time.perf_counter()
        rec = run_scene_gt(
            scene, handle, imp_name, h_fine=args.h_fine,
            t_settle=args.t_settle, t_run=args.t_run,
            body_youngs=args.body_youngs, out_dir=args.out)
        wall = time.perf_counter() - t0
        mid = np.asarray(rec["probes"]["support_mid_uy"])
        print(f"{scene}: {wall:.1f}s wall for "
              f"{args.t_settle + args.t_run:.2f}s sim | "
              f"support mid u_y range [{mid.min():.3e}, {mid.max():.3e}] m | "
              f"ledger keys {sorted(set(k for f in rec['ledger'] for k in f))}")


if __name__ == "__main__":
    main()
