#!/usr/bin/env python3
"""Robustness test matrix for the native two-way coupling. ISOLATED benchmark.

Sweeps the operating knobs and FLAGS every config that is unsafe:
  axes : scene {shelf,ledge,dinner} x solver {xpbd,avbd}
         x modal relax {0.1,0.25,0.5,0.7,1.0}
         x budget (iterations, substeps) {(8,2),(16,4),(32,8)}  [low/med/high]
  per config (operating dt h=1/120, default slab material):
    passivity = max(slab ring) / max(impactor KE)   -> INJECT if >1
    two-way   = object KE peak (free) / (frozen q̇)   -> DEAD if <2
    finite                                           -> BLOWUP if not (or passivity>2)
  plus a fine-dt ring-frequency pass on the relax axis (budget 16,4):
    detune    = |f_meas - f_EB| / f_EB               -> DETUNE if >15%

Flag precedence: BLOWUP > INJECT > DETUNE > DEAD > OK.

Out: out/{robustness_passivity.png, robustness_twoway.png, robustness_detune.png,
robustness_matrix.csv}.  Run: .venv/bin/python benchmarks/material_sweeps/run_robustness.py [--quick]
"""
from __future__ import annotations

import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

from benchmarks.material_sweeps.sweep_common import (
    SCENES, eb_f1, measure_ring_freq, coupling_metrics,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SOLVERS = ("xpbd", "avbd")
RELAXES = [0.1, 0.25, 0.5, 0.7, 1.0]
BUDGETS = [(8, 2), (16, 4), (32, 8)]               # (iterations, substeps)
SCENE_DEFAULT_MAT = {
    "shelf":  dict(youngs=5.0e8,  density=600.0, poisson=0.30),
    "ledge":  dict(youngs=1.0e10, density=500.0, poisson=0.30),
    "dinner": dict(youngs=1.0e10, density=500.0, poisson=0.30),
}
DETUNE_BUDGET = (16, 4)
INJECT_T, BLOWUP_T, DEAD_T, DETUNE_T = 1.0, 2.0, 2.0, 0.15


def classify(passivity, twoway, finite, detune):
    if (not finite) or (passivity is not None and passivity > BLOWUP_T):
        return "BLOWUP"
    if passivity is not None and passivity > INJECT_T:
        return "INJECT"
    if detune is not None and np.isfinite(detune) and detune > DETUNE_T:
        return "DETUNE"
    if twoway is not None and twoway < DEAD_T:
        return "DEAD"
    return "OK"


def gather(quick=False):
    nf = 120 if quick else 150
    rows = []
    # ---- stability grid (operating dt) ----
    for scene, sc in SCENES.items():
        mat = SCENE_DEFAULT_MAT[scene]
        for solver in SOLVERS:
            for relax in RELAXES:
                for (it, su) in BUDGETS:
                    cm = coupling_metrics(sc["build"], solver, build_kw=mat,
                                          relax=relax, n_frames=nf,
                                          iters=it, substeps=su)
                    rows.append(dict(scene=scene, solver=solver, relax=relax,
                                     iters=it, substeps=su,
                                     passivity=cm["passivity"],
                                     twoway=cm["twoway_ratio"],
                                     Eslab=cm["Eslab_peak"], Eimp=cm["Eimp_peak"],
                                     finite=cm["finite"], detune=None))
                    print(f"  {scene:7s}/{solver}/relax{relax:.2f}/it{it}su{su}: "
                          f"pass={cm['passivity']:.2f} two={cm['twoway_ratio']:.1f} "
                          f"fin={cm['finite']}", flush=True)
    # ---- ring-detune pass (fine dt, relax axis, fixed budget) ----
    it, su = DETUNE_BUDGET
    detune = {}
    for scene, sc in SCENES.items():
        mat = SCENE_DEFAULT_MAT[scene]
        f_eb = eb_f1(**mat, L=sc["L"], t=sc["t"])
        for solver in SOLVERS:
            for relax in RELAXES:
                fm, hz = measure_ring_freq(sc["build"], solver, L=sc["L"], t=sc["t"],
                                           build_kw=mat, relax=relax, f_hint=f_eb,
                                           iters=it, substeps=su)
                d = abs(fm - f_eb) / f_eb if (f_eb > 0 and np.isfinite(fm)) else float("nan")
                detune[(scene, solver, relax)] = (fm, f_eb, d)
                print(f"  DETUNE {scene:7s}/{solver}/relax{relax:.2f}: "
                      f"f={fm:.1f} EB={f_eb:.1f} ({d*100:.0f}%)", flush=True)
    # attach detune (at DETUNE_BUDGET) + classify each stability row
    for r in rows:
        key = (r["scene"], r["solver"], r["relax"])
        dv = detune.get(key, (np.nan, np.nan, np.nan))[2] if (r["iters"], r["substeps"]) == DETUNE_BUDGET else None
        r["detune"] = dv
        r["flag"] = classify(r["passivity"], r["twoway"], r["finite"], dv)
    return rows, detune


def _heat(ax, rows, scene, solver, key, title, vmax, center=None):
    sub = [r for r in rows if r["scene"] == scene and r["solver"] == solver]
    M = np.full((len(RELAXES), len(BUDGETS)), np.nan)
    flag = {}
    for r in sub:
        i = RELAXES.index(r["relax"]); j = BUDGETS.index((r["iters"], r["substeps"]))
        M[i, j] = r[key] if np.isfinite(r[key]) else np.nan
        flag[(i, j)] = r["flag"]
    cmap = "RdYlGn_r" if center else "viridis"
    im = ax.imshow(np.clip(M, 0, vmax), origin="lower", aspect="auto", cmap=cmap,
                   vmin=0, vmax=vmax)
    ax.set_xticks(range(len(BUDGETS)))
    ax.set_xticklabels([f"{it}/{su}" for it, su in BUDGETS], fontsize=7)
    ax.set_yticks(range(len(RELAXES))); ax.set_yticklabels(RELAXES, fontsize=7)
    ax.set_xlabel("iters/substeps", fontsize=8); ax.set_ylabel("relax", fontsize=8)
    ax.set_title(f"{scene}/{solver}: {title}", fontsize=8)
    for i in range(len(RELAXES)):
        for j in range(len(BUDGETS)):
            v = M[i, j]
            fl = flag.get((i, j), "")
            txt = "BLOW" if fl == "BLOWUP" else (f"{v:.2f}" if np.isfinite(v) else "—")
            ax.text(j, i, txt, ha="center", va="center", fontsize=6,
                    color="k" if fl in ("OK", "DEAD") else "white")
    return im


def fig_grid(rows, key, title, vmax, center, fname):
    fig, axs = plt.subplots(2, 3, figsize=(13, 7))
    for si, solver in enumerate(SOLVERS):
        for ci, scene in enumerate(SCENES):
            _heat(axs[si, ci], rows, scene, solver, key, title, vmax, center)
    fig.suptitle(f"Robustness matrix — {title} (relax × budget, default material)",
                 fontsize=12)
    fig.tight_layout()
    p = os.path.join(OUT, fname)
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def fig_detune(detune):
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
    for si, solver in enumerate(SOLVERS):
        ax = axs[si]
        for scene in SCENES:
            ys = [detune[(scene, solver, r)][2] * 100 for r in RELAXES]
            ax.plot(RELAXES, ys, "-o", label=scene)
        ax.axhspan(0, DETUNE_T * 100, color="green", alpha=0.08)
        ax.axhline(DETUNE_T * 100, color="k", lw=0.7, ls="--", label="15% detune")
        ax.set_xlabel("modal relax"); ax.set_title(f"{solver} — ring detune vs relax")
        ax.set_ylabel("|f_meas − f_EB| / f_EB  [%]")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.suptitle("Ring detune vs modal relaxation (budget 16/4, fine dt)", fontsize=12)
    fig.tight_layout()
    p = os.path.join(OUT, "robustness_detune.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print("### robustness matrix (relax × budget × scene × solver) ###", flush=True)
    rows, detune = gather(quick=args.quick)
    p1 = fig_grid(rows, "passivity", "energy passivity (ring/impactor KE; >1 = INJECT)",
                  2.0, center=1.0, fname="robustness_passivity.png")
    p2 = fig_grid(rows, "twoway", "two-way ratio (<2 = DEAD coupling)", 50.0,
                  center=None, fname="robustness_twoway.png")
    p3 = fig_detune(detune)
    keys = ["scene", "solver", "relax", "iters", "substeps", "passivity",
            "twoway", "Eslab", "Eimp", "detune", "finite", "flag"]
    with open(os.path.join(OUT, "robustness_matrix.csv"), "w", newline="") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        wcsv.writeheader()
        for r in rows:
            wcsv.writerow(r)
    # printed safe-region summary
    from collections import Counter
    print("\n=== flag counts ===")
    for fl, n in Counter(r["flag"] for r in rows).most_common():
        print(f"  {fl:7s}: {n}/{len(rows)}")
    print(f"\nwrote {p1}\n      {p2}\n      {p3}\n      robustness_matrix.csv")


if __name__ == "__main__":
    main()
