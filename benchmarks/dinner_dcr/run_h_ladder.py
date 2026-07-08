#!/usr/bin/env python3
"""E5 — dinner h-ladder: does the launch-amplitude deficit close as h refines?

The modal state is a co-solved constraint DOF (its integration rate IS the
substep rate), so the discriminating experiment for the ~7x dish-launch
deficit is the rigid-step ladder, mirroring X3-B: run the native rigid-dish
arm at h = 1/120 .. 1/960 against the CACHED all-FEM ground truth
(docs/dinner_dcr/gt_dN, t_run = 1.2 s) and track the per-body launch ratio.

  ratio -> 1 with h   => band-limiting of the impact impulse by the rigid
                         step (X3-B's mechanism) confirmed at the scene of
                         the claim; the deficit is a cost knob, not a flaw.
  ratio saturates     => the deficit is contact-model-side; 4.3 wording
                         must change.

Out: benchmark/runs/substep/dinner_h_ladder.csv + console summary.
Run: .venv/bin/python -m benchmarks.dinner_dcr.run_h_ladder [--drops 0 1 2]
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from benchmarks.dinner_dcr.run_dinner_dcr import (  # noqa: E402
    _native_run, _gt_from_csv, NATIVE_RIGID, DROPS)

OUT_DIR = os.path.join(ROOT, "benchmark", "runs", "substep")
T_RUN = 1.2                    # must match the recorded GT protocol
H_INVS = (120, 240, 480, 960)
TOPPLE_M = 0.3                 # unscored beyond this (GT contact limitation)
GT_FLOOR_MM = 1.0              # ignore bodies the GT barely moves


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drops", type=int, nargs="*", default=[0, 1, 2])
    ap.add_argument("--h-invs", type=int, nargs="*", default=list(H_INVS))
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    summary = {}
    for hi in args.h_invs:
        ratios = []
        for di in args.drops:
            drop = DROPS[di]
            gt = _gt_from_csv(drop, f"d{di}")
            if gt is None:
                print(f"!! no recorded GT for drop d{di}; skipping")
                continue
            nat = _native_run(drop, T_RUN, NATIVE_RIGID, h=1.0 / hi)
            for name, gt_dy in gt["dy_max"].items():
                if name == "pot" or name not in nat["dy_max"]:
                    continue
                na_dy = nat["dy_max"][name]
                scored = (gt_dy <= TOPPLE_M and na_dy <= TOPPLE_M
                          and gt_dy * 1e3 >= GT_FLOOR_MM)
                ratio = na_dy / gt_dy if gt_dy > 0 else float("nan")
                rows.append((hi, di, name, na_dy * 1e3, gt_dy * 1e3,
                             ratio, int(scored)))
                if scored:
                    ratios.append(ratio)
            print(f"h=1/{hi} drop d{di}: {nat['ms_per_step']:.1f} ms/step, "
                  f"{len(ratios)} scored so far", flush=True)
        if ratios:
            r = np.asarray(ratios)
            summary[hi] = (float(np.median(r)),
                           float(np.percentile(r, 25)),
                           float(np.percentile(r, 75)), len(r))

    with open(os.path.join(OUT_DIR, "dinner_h_ladder.csv"), "w") as f:
        f.write("h_inv,drop,body,dy_native_mm,dy_gt_mm,ratio,scored\n")
        for r in rows:
            f.write(",".join(str(v) for v in r) + "\n")

    print("\n== E5 dinner h-ladder: native/GT launch ratio (scored bodies) ==")
    for hi, (med, q25, q75, n) in summary.items():
        print(f"  h=1/{hi:<4d} median {med:.3f}  IQR [{q25:.3f}, {q75:.3f}]"
              f"  n={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
