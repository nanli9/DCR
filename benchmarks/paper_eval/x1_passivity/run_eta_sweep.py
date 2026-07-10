#!/usr/bin/env python3
"""X1c — η sensitivity of the passivity clamp (the paper's only knob).

The clamp enforces ΔE_modal ≤ η·ΔE_rigid_loss (foundation §15) with η = 1
everywhere in the paper. This sweep measures what η actually buys: XPBD (the
injecting formulation) on the three robustness scenes, clamp ON, at

  * the injecting budget 8×2  (un-clamped ratios 53.7 / 47 / 2.15, X1), and
  * the paper budget    16×4  (naturally passive at η = 1 — clamp inert),

for η ∈ {0.1, 0.3, 0.5, 1.0}. Per cell: the passivity ratio (peak support-ring
energy / impactor KE), the ledger invariant `passive()`, clamp activations,
the realized modal gain vs its η-budget, and the peak ring amplitude |a|∞
(the over-damping dial).

Expected story: the bound scales with η (ratio ∝ η where the clamp is load-
bearing); at the paper budget the clamp stays inert only while η exceeds the
scene's NATURAL transfer ratio (~0.2–0.4 of the loss budget, X1/E6) — below it
the governor bites even in the safe region and damps the valid ring. η = 1 is
the passivity-only default; smaller η is a stronger guarantee bought with ring
amplitude.

Out: benchmarks/paper_eval/x1_passivity/out/eta_sweep.csv + manifest
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_eta_sweep.py [--quick]
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

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from dcr.rigid.energy import rigid_kinetic_energy
from benchmarks.paper_eval.paper_config import apply_passivity, write_manifest

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}
RELAX = 0.7                       # PAPER_CONFIG relax; X1 sweeps it, we pin it
ETAS = [0.1, 0.3, 0.5, 1.0]
BUDGETS = [(8, 2), (16, 4)]       # injecting / naturally-passive (X1)


def one(build_fn, iters, subs, eta, nframes):
    H = build_fn(device="cpu", iterations=iters, avbd_substeps=subs,
                 solver="xpbd")
    sol = H.world._solver
    sol.modal_relax = RELAX
    sol._support_block_relax = RELAX
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=True, eta=eta)
    w = H.world
    ib = w._descs[H.impactor_idx].dcr_body
    for _ in range(8):
        w.step()
    Eimp = Ering = amax = 0.0
    finite = True
    for _ in range(nframes):
        w.step()
        Eimp = max(Eimp, rigid_kinetic_energy([ib]))
        e = sol.last_modal_KE + sol.last_modal_PE
        if not np.isfinite(e):
            finite = False
            break
        Ering = max(Ering, e)
        if sol._q is not None and sol._q.size:
            amax = max(amax, float(np.max(np.abs(sol._q))))
    L = sol._psv_ledger
    return dict(
        passivity=(Ering / max(Eimp, 1e-9)) if finite else float("inf"),
        passive=(L.passive() if L else None),
        n_clamped=(L.n_clamped if L else None),
        n_steps=(L.n_steps if L else None),
        cum_gain=(L.cum_modal_gain if L else None),
        cum_budget=(L.eta * L.cum_rigid_loss if L else None),
        amax=amax, finite=finite)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    nframes = 70 if args.quick else 100

    rows = []
    print("### X1c eta sweep: XPBD clamp ON, eta x budget x scene ###",
          flush=True)
    for scene, fn in SCENES.items():
        for (it, su) in BUDGETS:
            for eta in ETAS:
                r = one(fn, it, su, eta, nframes)
                rows.append(dict(scene=scene, iters=it, substeps=su, eta=eta,
                                 relax=RELAX, **r))
                print(f"  {scene:7s} {it:2d}x{su} eta={eta:4.2f}: "
                      f"ratio={r['passivity']:8.3f} passive={r['passive']} "
                      f"clamp={r['n_clamped']}/{r['n_steps']} "
                      f"gain={r['cum_gain']:.3g}/budget={r['cum_budget']:.3g} "
                      f"|a|={r['amax']:.3g}", flush=True)

    keys = list(rows[0].keys())
    with open(os.path.join(OUT, "eta_sweep.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(OUT, "eta_sweep.csv", scenes=list(SCENES), solvers=["xpbd"],
                   note=f"clamp ON, eta in {ETAS}, budgets {BUDGETS}, "
                        f"relax {RELAX}; OFF reference = robustness_clamp.csv")
    print(f"\nwrote eta_sweep.csv ({len(rows)} rows) to {OUT}/")


if __name__ == "__main__":
    main()
