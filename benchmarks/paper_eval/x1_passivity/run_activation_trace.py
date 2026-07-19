#!/usr/bin/env python3
"""F1 teaser data — modal-energy trace, governor OFF vs ON, same scene+budget.

ISOLATED benchmark. Emits the per-frame modal mechanical energy of the support
for one starved cell, run twice: un-governed (the energy runs away) and governed
(the cumulative bound holds it). Same scene, same budget, same seed -- the only
difference is `_enforce_modal_passivity`.

Also logs the running ledger budget eta * sum(max(dE_rigid, 0)) so the figure can
show the bound the governed trace is being held against, rather than just an
arbitrary flat line.

Out: out/{activation_trace.csv, activation_trace.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_activation_trace.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def trace(scene, iters, subs, relax, enforce, nframes, settle=8):
    H = SCENES[scene](device="cpu", iterations=iters, avbd_substeps=subs,
                      solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=enforce, eta=1.0)
    w = H.world
    for _ in range(settle):
        w.step()
    e_hist, b_hist = [], []
    for _ in range(nframes):
        w.step()
        e = sol.last_modal_KE + sol.last_modal_PE
        e_hist.append(float(e) if np.isfinite(e) else float("nan"))
        L = sol._psv_ledger
        b_hist.append(float(L.eta * L.cum_rigid_loss) if L is not None
                      else float("nan"))
    return e_hist, b_hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="shelf")
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--substeps", type=int, default=2)
    ap.add_argument("--relax", type=float, default=0.7)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="activation_trace")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    off, _ = trace(args.scene, args.iters, args.substeps, args.relax,
                   False, args.nframes)
    on, budget = trace(args.scene, args.iters, args.substeps, args.relax,
                       True, args.nframes)

    h = 1.0 / 120.0
    path = os.path.join(OUT, f"{args.out}.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame", "t_s", "E_modal_off_J", "E_modal_on_J",
                    "ledger_budget_on_J"])
        for i, (a, b, c) in enumerate(zip(off, on, budget)):
            w.writerow([i, i * h, a, b, c])
    write_manifest(OUT, f"{args.out}.csv", scenes=[args.scene], solvers=["xpbd"],
                   note=(f"F1 teaser: modal energy trace at {args.iters}x"
                         f"{args.substeps}, relax {args.relax}, governor OFF vs "
                         f"ON; ledger_budget = eta*cum_rigid_loss (the ON bound)"))
    print(f"peak modal energy  OFF = {np.nanmax(off):.4g} J   "
          f"ON = {np.nanmax(on):.4g} J   "
          f"(final ledger budget {budget[-1]:.4g} J)")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
