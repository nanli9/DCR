#!/usr/bin/env python3
"""E9 — cross-term Schur vs engaged-gated block-GS q-block (foundation §3.2).

The shipped modal q-block is block Gauss-Seidel (z owned by the colored primal,
q solved holding z, under-relaxed) — passive at truncated budgets. The REJECTED
alternative is the cross-term Schur: eliminate the body's z-DOF into the q-block
(A_qz A_zz^{-1} A_zq), which softens H_q and, applied without the Δz back-
substitution, injects energy when the solve is truncated. `solver._modal_
schur_crossterm` (default OFF) resurrects it behind a flag for this measurement.

Runs the shelf (support + stacked cubes) at 8x2 (truncated) and 32x4 (near-
converged), both formulations, passivity clamp OFF (isolate the formulation),
and reports peak modal energy. Expected: block-GS bounded at both budgets;
Schur injects at 8x2 and the gap narrows toward parity as the budget grows.

Out: benchmarks/paper_eval/x1_passivity/out/schur_vs_blockgs.csv
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_schur_vs_blockgs.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from scenes.reduced_shelf import build_reduced_shelf

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
RELAX = 0.7
BUDGETS = [(4, 1), (8, 2), (16, 4), (32, 4)]


def run(iters, substeps, *, schur, steps):
    H = build_reduced_shelf(device="cpu", iterations=iters, avbd_substeps=substeps,
                            solver="avbd", cargo_material=None)
    sol = H.world._solver
    sol._modal_relax = float(RELAX)
    sol._modal_symplectic = True
    # MONITOR the §15 ledger (record, no perturbation) so we measure whether the
    # FORMULATION injects — the clamp itself is not what E9 isolates.
    sol._enforce_modal_passivity = True
    sol._modal_eta = 1.0
    sol._psv_monitor_only = True
    sol._modal_schur_crossterm = bool(schur)
    w = H.world
    peak = 0.0
    nan = False
    for _ in range(steps):
        w.step()
        Em = float(getattr(sol, "last_modal_KE", 0.0) + getattr(sol, "last_modal_PE", 0.0))
        if not np.isfinite(Em):
            nan = True
            break
        peak = max(peak, Em)
    led = getattr(sol, "_psv_ledger", None)
    if led is None:
        return dict(peak_modal=peak, nan=nan, passive=None, holds=None,
                    excess=None, gain=None, cap=None)
    return dict(peak_modal=peak, nan=nan,
                passive=bool(led.passive()), holds=bool(led.holds()),
                excess=float(led.max_net_excess), deposit=float(led.max_deposit),
                gain=float(led.cum_modal_gain),
                cap=float(led.eta * led.cum_rigid_loss))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=300)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print(f"### E9 Schur vs block-GS (shelf support, clamp OFF, {args.steps} steps) ###",
          flush=True)
    rows = []
    for it, su in BUDGETS:
        b = run(it, su, schur=False, steps=args.steps)      # block-GS (shipped)
        s = run(it, su, schur=True, steps=args.steps)       # cross-term Schur (rejected)
        ratio = s["peak_modal"] / max(b["peak_modal"], 1e-30)
        rows.append(dict(iters=it, substeps=su, budget=f"{it}x{su}",
                         blockgs_peak=b["peak_modal"], schur_peak=s["peak_modal"],
                         peak_ratio=ratio,
                         blockgs_passive=b["passive"], schur_passive=s["passive"],
                         blockgs_excess=b.get("excess"), schur_excess=s.get("excess"),
                         schur_nan=s["nan"]))
        print(f"  {it}x{su}: block-GS passive={b['passive']} (excess={b.get('excess'):.3g})  "
              f"|  Schur passive={s['passive']} (excess={s.get('excess'):.3g})  "
              f"peak {b['peak_modal']:.3g}/{s['peak_modal']:.3g}"
              f"{'  [Schur blowup]' if s['nan'] else ''}", flush=True)

    keys = ["budget", "iters", "substeps", "blockgs_peak", "schur_peak", "peak_ratio",
            "blockgs_passive", "schur_passive", "blockgs_excess", "schur_excess",
            "schur_nan"]
    with open(os.path.join(OUT, "schur_vs_blockgs.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k]) for k in keys})
    with open(os.path.join(OUT, "schur_vs_blockgs.config.json"), "w") as fh:
        json.dump(dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       scene="shelf (support + stacked cubes)", solver="avbd", device="cpu",
                       relax=RELAX, budgets=[f"{i}x{s}" for i, s in BUDGETS], steps=args.steps,
                       note="cross-term Schur (translational M_eff, no Δz back-sub) vs "
                            "engaged-gated block-GS; clamp OFF to isolate the formulation"),
                  fh, indent=2)
    n_schur_pass = sum(1 for r in rows if r["schur_passive"])
    n_bg_pass = sum(1 for r in rows if r["blockgs_passive"])
    print(f"\nblock-GS passive {n_bg_pass}/{len(rows)}; Schur passive {n_schur_pass}/{len(rows)}. "
          f"peak parity at {rows[-1]['budget']}: ratio {rows[-1]['peak_ratio']:.3g}. "
          f"wrote schur_vs_blockgs.csv")


if __name__ == "__main__":
    main()
