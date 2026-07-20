#!/usr/bin/env python3
"""E-C9d — does the recycling exposure grow with the horizon? (plan §8.5, P8.c-ii)

The Limitations paragraph bounds recycling by the return channel,
sum_k max(-dE_rig^k, 0) as a fraction of the gross supply, measured over the
standard 100-frame window. A reviewer is entitled to ask whether that fraction
is a property of the short window: if energy cycles modal -> rigid -> dissipated
repeatedly, a longer run should keep re-crediting it and the fraction should
climb.

This runs the same ungoverned cells out to 10x the standard horizon and reports
the return fraction at each. A flat fraction means the exposure is a steady-state
property of the scene, not an artifact of window length; a climbing one would
mean the caveat understates long runs.

Measurement-only throughout: it calls run_eq2_utilization.one(), whose ledger is
live while passivity_gamma == 1.0 makes every state write in the enforcement
path dead.

Out: out/{long_horizon.csv, long_horizon.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_long_horizon.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.x1_passivity import run_eq2_utilization as EQ2  # noqa: E402
from benchmarks.paper_eval.paper_config import write_manifest      # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

CELLS = [("shelf", 0.7, 4, 1), ("ledge", 1.0, 4, 1)]
HORIZONS = [100, 250, 500, 1000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="long_horizon")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### E-C9d long-horizon recycling ({platform.machine()}) ###",
          flush=True)
    rows = []
    for (scene, relax, K, S) in CELLS:
        for n in HORIZONS:
            m = EQ2.one(SCENES[scene], "xpbd", K, S, relax, nframes=n)
            rf = m["return_frac"]
            rows.append(dict(scene=scene, relax=relax, iters=K, substeps=S,
                             nframes=n, return_frac=rf,
                             gross_supply_J=m["gross_supply"],
                             return_channel_J=m["return_channel"],
                             ratio_off=m["ratio_off"],
                             margin_J=m["margin_J"],
                             eq2_violates=m["eq2_violates"]))
            print(f"  {scene:6s} {K}x{S} n={n:5d}: return "
                  f"{100.0 * rf:6.2f}%   supply {m['gross_supply']:10.4g} J   "
                  f"R {m['ratio_off']:11.4g}   "
                  f"Eq2 {'VIOLATES' if m['eq2_violates'] else 'holds'}",
                  flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=sorted({c[0] for c in CELLS}),
        solvers=["xpbd"],
        note=("E-C9d (plan §8.5 P8.c-ii): return-channel fraction vs horizon, "
              "100 -> 1000 frames, ungoverned. Tests whether the recycling "
              "exposure quoted in Limitations is a property of the 100-frame "
              "window. Measurement-only (run_eq2_utilization.one(), "
              "passivity_gamma == 1.0)."))
    for (scene, relax, K, S) in CELLS:
        sr = [r for r in rows if r["scene"] == scene]
        if sr:
            f0, f1 = sr[0]["return_frac"], sr[-1]["return_frac"]
            print(f"\n  {scene}: return fraction {100 * f0:.2f}% at "
                  f"{sr[0]['nframes']} frames -> {100 * f1:.2f}% at "
                  f"{sr[-1]['nframes']}")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
