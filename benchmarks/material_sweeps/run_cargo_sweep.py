#!/usr/bin/env python3
"""Cargo-material sweep: rigid / fem_rigid / fem / abd. ISOLATED benchmark.

The cargo is the deformable cube riding ON the impactor (native M2 path,
`add_native_cargo`). This sweep measures how the cargo's material model changes
the OBSERVABLE two-way coupling on the shelf scene — the slab ring it produces,
the two-way ratio (freeze-q̇ control), energy passivity, and the impactor KE it
delivers — for both native solvers.

Caveat: the cargo's own internal elastic energy is folded into the augmented
modal vector [q_slab; a_cargo] and is not separately instrumented here; what is
reported is the cargo material's effect on the slab/impactor-observable coupling.

Out: benchmarks/material_sweeps/out/{cargo_material_sweep.png, cargo_material_sweep.csv}
Run: .venv/bin/python benchmarks/material_sweeps/run_cargo_sweep.py [--quick]
"""
from __future__ import annotations

import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

from scenes.reduced_shelf import build_reduced_shelf
from benchmarks.material_sweeps.sweep_common import CARGO_MATERIALS, coupling_metrics

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SOLVERS = ("xpbd", "avbd")


def gather(quick=False):
    rows = []
    nf = 140 if quick else 200
    for mat in CARGO_MATERIALS:
        for solver in SOLVERS:
            try:
                cm = coupling_metrics(build_reduced_shelf, solver,
                                      build_kw={"cargo_material": mat}, n_frames=nf)
            except NotImplementedError as e:
                # AVBD (Solver6DOF) symplectic is "host non-cargo only" — its
                # device q-block / cargo augmentation are not wired for the
                # symplectic step. Honour the user's symplectic-default directive
                # and record the config as unsupported rather than silently
                # falling back to BE.
                rows.append(dict(cargo=mat, solver=solver, unsupported=True,
                                 twoway_ratio=float("nan"), Eslab_peak=float("nan"),
                                 ErestKE_peak=float("nan"), passivity=float("nan"),
                                 Eimp_peak=float("nan"), slab_rings=-1, bounces=-1,
                                 finite=False))
                print(f"  cargo={mat:9s}/{solver}: UNSUPPORTED under symplectic "
                      f"({str(e)[:60]})", flush=True)
                continue
            rows.append(dict(cargo=mat, solver=solver, unsupported=False, **cm))
            print(f"  cargo={mat:9s}/{solver}: two-way={cm['twoway_ratio']:6.1f}x  "
                  f"slab_ring={cm['Eslab_peak']*1e3:7.1f}mJ  "
                  f"passivity={cm['passivity']:.2f}  Eimp={cm['Eimp_peak']:.1f}J",
                  flush=True)
    return rows


def fig_cargo(rows):
    mats = CARGO_MATERIALS
    xp = {r["cargo"]: r for r in rows if r["solver"] == "xpbd"}
    av = {r["cargo"]: r for r in rows if r["solver"] == "avbd"}
    x = np.arange(len(mats)); w = 0.38
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))

    def _v(d, key, scale):
        val = d[key]
        return float("nan") if (val != val) else min(val * scale, 1e5)

    def bars(a, key, title, ylabel, scale=1.0, log=False, hline=None):
        a.bar(x - w / 2, [_v(xp[m], key, scale) for m in mats], w,
              label="XPBD", color="C0")
        a.bar(x + w / 2, [_v(av[m], key, scale) for m in mats], w,
              label="AVBD (n/a: symplectic+cargo)", color="C3")
        if hline is not None:
            a.axhline(hline, color="k", lw=0.6, ls="--")
        a.set_xticks(x); a.set_xticklabels(mats); a.set_ylabel(ylabel)
        if log:
            a.set_yscale("log")
        a.set_title(title); a.legend(fontsize=8); a.grid(alpha=0.3, which="both")

    bars(ax[0, 0], "twoway_ratio", "(a) two-way coupling ratio (freeze-q̇)",
         "object KE two-way / one-way", log=True, hline=1.0)
    bars(ax[0, 1], "Eslab_peak", "(b) slab modal ring energy", "ring peak [mJ]",
         scale=1e3, log=True)
    bars(ax[1, 0], "passivity", "(c) energy passivity (ring / impactor KE)",
         "slab ring / impactor KE", hline=1.0)
    bars(ax[1, 1], "Eimp_peak", "(d) impactor KE delivered (sanity)",
         "impactor KE peak [J]")

    fig.suptitle("Cargo-material sweep (rigid / fem_rigid / fem / abd) — "
                 "effect on the slab two-way coupling, shelf scene "
                 "(symplectic modal step)", fontsize=12)
    fig.tight_layout()
    p = os.path.join(OUT, "cargo_material_sweep.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print("### cargo-material sweep ###", flush=True)
    rows = gather(quick=args.quick)
    p = fig_cargo(rows)
    keys = ["cargo", "solver", "twoway_ratio", "Eslab_peak", "ErestKE_peak",
            "passivity", "Eimp_peak", "slab_rings", "bounces", "finite"]
    with open(os.path.join(OUT, "cargo_material_sweep.csv"), "w", newline="") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        wcsv.writeheader()
        for r in rows:
            wcsv.writerow(r)
    print(f"\nwrote {p}\n      cargo_material_sweep.csv")


if __name__ == "__main__":
    main()
