#!/usr/bin/env python3
"""X1 — passive-energy clamp: before/after robustness (the money figure).

ISOLATED benchmark. Sweeps the native XPBD solver (the injector — AVBD is
empirically passive) over budget × relax on the 3 non-cargo scenes, with the
Stage-X1 clamp OFF then ON, and records for each cell:
  passivity = slab-ring peak / impactor KE   (>1 ⇒ the energy-injection pathology)
  passive() = ledger invariant E_modal(t) ≤ η·Σ rigid loss(t) held over the run
  n_clamped = substeps the γ-projection actually bit

Expected story: OFF injects hard at low budget (passivity ≫ 1); ON drives every
cell passive (invariant holds) while leaving the safe region (16×4) untouched.

Out: benchmarks/paper_eval/x1_passivity/out/{robustness_clamp.csv, robustness_clamp.png} + manifest
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_robustness_clamp.py [--quick]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from dcr.rigid.energy import rigid_kinetic_energy
from benchmarks.paper_eval.paper_config import write_manifest

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}


def one(build_fn, iters, subs, relax, enforce, nframes):
    H = build_fn(device="cpu", iterations=iters, avbd_substeps=subs, solver="xpbd")
    sol = H.world._solver
    sol.modal_relax = relax
    sol._support_block_relax = relax
    sol._modal_symplectic = True
    sol._enforce_modal_passivity = bool(enforce)
    w = H.world
    imp = H.impactor_idx
    ib = w._descs[imp].dcr_body
    for _ in range(8):
        w.step()
    Eimp = Eslab = 0.0
    finite = True
    for _ in range(nframes):
        w.step()
        Eimp = max(Eimp, rigid_kinetic_energy([ib]))
        e = sol.last_modal_KE + sol.last_modal_PE
        if not np.isfinite(e):
            finite = False
            break
        Eslab = max(Eslab, e)
    L = sol._psv_ledger
    return dict(passivity=(Eslab / max(Eimp, 1e-9)) if finite else float("inf"),
                passive=(L.passive() if (enforce and L) else None),
                n_clamped=(L.n_clamped if (enforce and L) else None),
                n_steps=(L.n_steps if (enforce and L) else None),
                finite=finite)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    nframes = 70 if args.quick else 100
    budgets = [(4, 1), (8, 2), (16, 4)] if args.quick else [(4, 1), (8, 2), (16, 4), (32, 8)]
    relaxes = [0.7, 1.0]
    scenes = ["shelf", "ledge", "dinner"]

    rows = []
    print("### X1 robustness: XPBD clamp OFF vs ON ###", flush=True)
    for scene in scenes:
        fn = SCENES[scene]
        for relax in relaxes:
            for (it, su) in budgets:
                off = one(fn, it, su, relax, False, nframes)
                on = one(fn, it, su, relax, True, nframes)
                rows.append(dict(scene=scene, relax=relax, iters=it, substeps=su,
                                 passivity_off=off["passivity"],
                                 passivity_on=on["passivity"],
                                 passive_on=on["passive"],
                                 n_clamped=on["n_clamped"], n_steps=on["n_steps"],
                                 finite_off=off["finite"], finite_on=on["finite"]))
                print(f"  {scene:7s} relax={relax} {it:2d}x{su}: "
                      f"passivity OFF={off['passivity']:9.2f} -> ON={on['passivity']:6.3f}  "
                      f"passive={on['passive']} clamp={on['n_clamped']}/{on['n_steps']}",
                      flush=True)

    keys = ["scene", "relax", "iters", "substeps", "passivity_off", "passivity_on",
            "passive_on", "n_clamped", "n_steps", "finite_off", "finite_on"]
    with open(os.path.join(OUT, "robustness_clamp.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(OUT, "robustness_clamp.csv", scenes=scenes, solvers=["xpbd"],
                   note="XPBD budget×relax, clamp OFF vs ON; passive()=ledger invariant held")
    _fig(rows, scenes, relaxes, budgets)
    n_inject_off = sum(1 for r in rows if r["passivity_off"] > 1.0)
    n_passive_on = sum(1 for r in rows if r["passive_on"])
    print(f"\nOFF: {n_inject_off}/{len(rows)} cells inject (passivity>1). "
          f"ON: {n_passive_on}/{len(rows)} cells pass the ledger invariant.")
    print(f"wrote robustness_clamp.csv, robustness_clamp.png to {OUT}/")


def _fig(rows, scenes, relaxes, budgets):
    blabels = [f"{it}x{su}" for (it, su) in budgets]
    fig, axs = plt.subplots(2, len(scenes), figsize=(4.6 * len(scenes), 8))
    for si, scene in enumerate(scenes):
        for ri, which in enumerate(["passivity_off", "passivity_on"]):
            ax = axs[ri, si]
            M = np.full((len(relaxes), len(budgets)), np.nan)
            for r in rows:
                if r["scene"] != scene:
                    continue
                i = relaxes.index(r["relax"])
                j = budgets.index((r["iters"], r["substeps"]))
                M[i, j] = min(r[which], 1e3)
            im = ax.imshow(np.log10(np.maximum(M, 1e-3)), origin="lower",
                           aspect="auto", cmap="RdYlGn_r", vmin=-1, vmax=2)
            ax.set_xticks(range(len(budgets))); ax.set_xticklabels(blabels)
            ax.set_yticks(range(len(relaxes))); ax.set_yticklabels(relaxes)
            for i in range(len(relaxes)):
                for j in range(len(budgets)):
                    v = M[i, j]
                    ax.text(j, i, f"{v:.2f}" if v < 100 else f"{v:.0f}",
                            ha="center", va="center", fontsize=8,
                            color="k" if 0.1 < v < 10 else "w")
            tag = "OFF (raw)" if ri == 0 else "ON (clamp)"
            ax.set_title(f"{scene} — passivity {tag}", fontsize=10)
            if si == 0:
                ax.set_ylabel("modal relax")
            if ri == 1:
                ax.set_xlabel("iters×substeps")
    fig.suptitle("X1 passive-energy clamp — slab ring / impactor KE (log10; "
                 "green ≤1 passive, red ≫1 injects). Clamp drives every cell ≤1.",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "robustness_clamp.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
