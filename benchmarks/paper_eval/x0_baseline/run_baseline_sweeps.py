#!/usr/bin/env python3
"""X0 — re-generate the slab + scene sweeps at PAPER_CONFIG (reproducibility leg).

ISOLATED benchmark. The material/scene sweeps already run at relax 0.7 + the
symplectic modal step (their `sweep_common.RELAX` == PAPER_CONFIG['relax']), so
this stage RE-RUNS their `gather()` functions READ-ONLY and writes fresh CSVs +
manifests under paper_eval — WITHOUT touching `benchmarks/material_sweeps/out/`
(those committed CSVs are the "before" evidence for Stage X1). Re-running also
tests reproducibility: the new numbers should match the committed ones, since the
config is identical.

Out: benchmarks/paper_eval/x0_baseline/out/{scene_sweep.csv, slab_material_sweep.csv} + manifests
Run: .venv/bin/python benchmarks/paper_eval/x0_baseline/run_baseline_sweeps.py
     [--which scene,slab] [--quick]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.material_sweeps import run_scene_sweep, run_slab_sweep
from benchmarks.material_sweeps.sweep_common import RELAX
from benchmarks.paper_eval.paper_config import PAPER_CONFIG, write_manifest

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

SCENE_KEYS = ["scene", "solver", "f_eb", "f_meas", "err_pct", "twoway",
              "passivity", "Eslab", "Eimp", "finite"]
SLAB_KEYS = ["material", "solver", "E", "rho", "nu", "c_eff", "f_eb", "f_fem",
             "f_meas", "hz", "fem_nodes", "d_fem", "d_eb", "twoway", "passivity",
             "Eslab", "Eimp", "finite"]


def _write(name, keys, rows, **manifest_kw):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in keys})
    write_manifest(OUT, name, **manifest_kw)
    print(f"  wrote {name} (+manifest)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", default="scene,slab")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # guard: the imported sweeps MUST be at the pinned relaxation, else the
    # "one shared config" premise of X0 is silently broken.
    assert abs(RELAX - PAPER_CONFIG["relax"]) < 1e-12, (
        f"material_sweeps RELAX={RELAX} != PAPER_CONFIG relax={PAPER_CONFIG['relax']}")

    which = [w for w in args.which.split(",") if w]
    print(f"### X0 baseline sweeps @ PAPER_CONFIG (relax={PAPER_CONFIG['relax']}, "
          f"symplectic{', QUICK' if args.quick else ''}) ###", flush=True)

    if "scene" in which:
        print("## scene sweep (shelf/ledge/dinner x avbd/xpbd) ##", flush=True)
        rows = run_scene_sweep.gather(quick=args.quick)
        _write("scene_sweep.csv", SCENE_KEYS, rows,
               scenes=["shelf", "ledge", "dinner"], solvers=["xpbd", "avbd"],
               source="benchmarks.material_sweeps.run_scene_sweep.gather",
               quick=bool(args.quick))

    if "slab" in which:
        print("## slab material sweep (5 materials x avbd/xpbd, shelf geom) ##",
              flush=True)
        rows, _order = run_slab_sweep.gather(quick=args.quick)
        _write("slab_material_sweep.csv", SLAB_KEYS, rows,
               scenes=["shelf"], solvers=["xpbd", "avbd"],
               source="benchmarks.material_sweeps.run_slab_sweep.gather",
               quick=bool(args.quick))


if __name__ == "__main__":
    main()
