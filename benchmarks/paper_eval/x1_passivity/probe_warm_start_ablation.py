#!/usr/bin/env python3
"""Reviewer response — is the position-based injection a FORMULATION property or
a WARM-START artifact?

Both review panels' single largest objection: the three hosts differ not only in
formulation but in warm-starting. Table 1 records that the position-based host
resets the contact multiplier lambda<-0 every substep, while the
augmented-Lagrangian and impulse hosts carry duals. Warm-starting is a nearly
free convergence accelerator (a memory read, ~0 extra row evaluations), so at
"equal cost" (K*S row evaluations) the carried-dual hosts get a head start the
budget axis does not equalize. The confound: is "the position-based host injects"
really "*this* un-warm-started deployment of it injects"?

This probe isolates it. It runs the SAME 24-cell XPBD sweep as
run_eq2_utilization.py TWICE, changing ONE thing:

  OFF : sol._warm_start_lam = False   (the paper default; lambda<-0 each substep)
  ON  : sol._warm_start_lam = True    (carry the contact multiplier across
                                       substeps -- the AL host's Table-1 row)

The measurement is run_eq2_utilization.one() verbatim (same ledger, same
neutered gamma, same R and margin_J), so OFF reproduces the reported numbers
bit-for-bit and ON is the only variable. The solver change is guarded and
defaults OFF (solver_xpbd.py: _warm_start_lam), so nothing else in the repo
moves.

Reading:
  * If warm-started XPBD STILL injects (R>>1, margin>0), the amplification is a
    formulation/truncation property, not a warm-start artifact -- the headline
    survives the confound.
  * If warm-starting removes it (R->~1), the cross-host ordering was largely a
    warm-start artifact and the paper must say so.

Out: out/{warm_start_ablation.csv, warm_start_ablation.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_warm_start_ablation.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x1_passivity.run_eq2_utilization import one   # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (       # noqa: E402
    SCENES, BUDGETS, RELAXES, NFRAMES)
from benchmarks.paper_eval.paper_config import write_manifest            # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _warm(sol):
    """Carry the contact multiplier across substeps (the ablation)."""
    sol._warm_start_lam = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--budgets", default="")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--out", default="warm_start_ablation")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]
    if args.budgets:
        budgets = [tuple(int(v) for v in b.lower().split("x"))
                   for b in args.budgets.split(",") if b.strip()]
    else:
        budgets = BUDGETS

    print(f"### warm-start ablation, position-based host: "
          f"{len(scenes) * len(relaxes) * len(budgets)} cells "
          f"({platform.machine()}, {platform.system()}) ###", flush=True)
    print("#   OFF = paper default (lambda<-0 / substep); "
          "ON = carry contact multiplier", flush=True)

    rows = []
    for scene in scenes:
        fn = SCENES[scene]
        for relax in relaxes:
            for (it, su) in budgets:
                off = one(fn, "xpbd", it, su, relax, args.nframes)
                on = one(fn, "xpbd", it, su, relax, args.nframes, mutate=_warm)
                row = dict(
                    scene=scene, relax=relax, iters=it, substeps=su,
                    R_off=off["ratio_off"], R_on=on["ratio_off"],
                    margin_off_J=off["margin_J"], margin_on_J=on["margin_J"],
                    e_modal_off=off["e_modal_peak"], e_modal_on=on["e_modal_peak"],
                    finite_on=on["finite"])
                rows.append(row)
                rr = (on["ratio_off"] / off["ratio_off"]
                      if off["ratio_off"] not in (0.0, float("inf")) else float("nan"))
                print(f"  {scene:7s} relax={relax} {it:2d}x{su}: "
                      f"R_off={off['ratio_off']:12.4g}  R_on={on['ratio_off']:12.4g}"
                      f"  (on/off={rr:7.3g})"
                      f"  margin_off={_g(off['margin_J'])}  "
                      f"margin_on={_g(on['margin_J'])} J", flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
        note=("Reviewer response: warm-start ablation on the position-based "
              "host. OFF = paper default (contact multiplier reset to 0 each "
              "substep); ON = multiplier carried across substeps "
              "(solver_xpbd.py _warm_start_lam, default OFF). Same "
              "run_eq2_utilization.one() measurement in both arms, so OFF "
              "reproduces eq2_utilization.csv and ON is the only variable. "
              "Tests whether the position-based injection is a formulation "
              "property or a warm-start artifact."))

    # ---- verdict ---------------------------------------------------------
    def _cross(key):
        return sum(1 for r in rows if r[key] is not None and r[key] > 1.0)

    def _viol(key):
        return sum(1 for r in rows if r[key] is not None and r[key] > 0.0)

    n = len(rows)
    worst_off = max(r["R_off"] for r in rows)
    worst_on = max(r["R_on"] for r in rows)
    print("\n--- verdict ---")
    print(f"  R > 1 (injection):   OFF {_cross('R_off')}/{n} cells,  "
          f"ON {_cross('R_on')}/{n} cells")
    print(f"  Eq.(2) margin > 0:   OFF {_viol('margin_off_J')}/{n} cells,  "
          f"ON {_viol('margin_on_J')}/{n} cells")
    print(f"  worst R:             OFF {worst_off:.4g},  ON {worst_on:.4g}")
    ratios = [r["R_on"] / r["R_off"] for r in rows
              if r["R_off"] not in (0.0, float("inf")) and np.isfinite(r["R_off"])]
    if ratios:
        print(f"  R_on / R_off:        median {np.median(ratios):.3g},  "
              f"min {min(ratios):.3g},  max {max(ratios):.3g}")
    print(f"\nwrote {csv_path}")


def _g(v):
    return f"{v:+.4g}" if v is not None else "n/a"


if __name__ == "__main__":
    main()
