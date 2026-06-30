#!/usr/bin/env python3
"""Slab-material sweep + physics-accuracy validation (analytical A + full-FEM B).

ISOLATED benchmark: imports scenes / dcr FEM / the committed probe READ-ONLY.

For each slab material (steel, aluminium, glass, oak, soft) on the shelf scene,
and each native solver (XPBD, AVBD):
  - two-way coupling ratio (object KE peak two-way / one-way) + energy passivity
  - measured modal ring frequency (fine-dt FFT of q0)
vs the physics ground truth:
  - (A) analytic Euler-Bernoulli f_1 (the synthetic basis's own model)
  - (B) full 3D-FEM simply-supported plate f_1 (independent truth)
and the f ∝ sqrt(E/rho) bending-frequency scaling law.

Out: benchmarks/material_sweeps/out/{slab_physics_accuracy.png, fem_vs_analytic.png,
slab_material_sweep.csv}

Run: .venv/bin/python benchmarks/material_sweeps/run_slab_sweep.py [--quick]
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
from benchmarks.material_sweeps.sweep_common import (
    SLAB_MATERIALS, SCENES, eb_f1, measure_ring_freq, coupling_metrics,
)
from benchmarks.material_sweeps.fem_reference import (
    fem_plate_ss, euler_bernoulli_ss_selfweight_deflection,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SOLVERS = ("xpbd", "avbd")


def gather(quick=False):
    rows = []
    nf = 140 if quick else 200
    L, W, t = SCENES["shelf"]["L"], SCENES["shelf"]["W"], SCENES["shelf"]["t"]
    # order materials by sqrt(E/rho) (the bending sound speed).
    order = sorted(SLAB_MATERIALS,
                   key=lambda k: (SLAB_MATERIALS[k]["youngs"]
                                  / SLAB_MATERIALS[k]["density"]) ** 0.5)
    for name in order:
        mat = SLAB_MATERIALS[name]
        ceff = (mat["youngs"] / mat["density"]) ** 0.5
        f_eb = eb_f1(**mat, L=L, t=t)
        # (B) full-FEM truth — solver-independent, once per material.
        ff, d_fem, nv = fem_plate_ss(L, W, t, mat["youngs"], mat["poisson"],
                                     mat["density"])
        f_fem = float(ff[0])
        d_eb = euler_bernoulli_ss_selfweight_deflection(
            L, t, mat["youngs"], mat["poisson"], mat["density"])
        for solver in SOLVERS:
            cm = coupling_metrics(build_reduced_shelf, solver, build_kw=mat,
                                  n_frames=nf)
            f_meas, hz = measure_ring_freq(build_reduced_shelf, solver, L=L, t=t,
                                           build_kw=mat, f_hint=f_eb)
            rows.append(dict(
                material=name, solver=solver, E=mat["youngs"],
                rho=mat["density"], nu=mat["poisson"], c_eff=ceff,
                f_eb=f_eb, f_fem=f_fem, f_meas=f_meas, hz=hz,
                fem_nodes=nv, d_fem=d_fem, d_eb=d_eb,
                twoway=cm["twoway_ratio"], passivity=cm["passivity"],
                Eslab=cm["Eslab_peak"], Eimp=cm["Eimp_peak"],
                finite=cm["finite"],
            ))
            print(f"  {name:9s}/{solver}: f_EB={f_eb:6.1f} f_FEM={f_fem:6.1f} "
                  f"f_meas={f_meas:6.1f}Hz  two-way={cm['twoway_ratio']:5.1f}x  "
                  f"passivity={cm['passivity']:.2f}", flush=True)
    return rows, order


def fig_accuracy(rows, order):
    mats = order
    xpbd = {r["material"]: r for r in rows if r["solver"] == "xpbd"}
    avbd = {r["material"]: r for r in rows if r["solver"] == "avbd"}
    x = np.arange(len(mats))
    fig, ax = plt.subplots(2, 2, figsize=(14, 9))

    # (a) ring frequency: EB / FEM truth / measured (per solver).
    a = ax[0, 0]
    a.plot(x, [xpbd[m]["f_eb"] for m in mats], "k--o", lw=1.2, label="analytic EB (basis)")
    a.plot(x, [xpbd[m]["f_fem"] for m in mats], "C4-s", lw=1.2, label="full-FEM truth (B)")
    a.plot(x, [xpbd[m]["f_meas"] for m in mats], "C0-^", lw=1.6, label="XPBD measured ring")
    a.plot(x, [avbd[m]["f_meas"] for m in mats], "C3-v", lw=1.2, label="AVBD measured ring")
    a.set_xticks(x); a.set_xticklabels(mats); a.set_ylabel("fundamental f_1 [Hz]")
    a.set_yscale("log"); a.set_title("(a) modal ring frequency vs ground truth")
    a.legend(fontsize=8); a.grid(alpha=0.3, which="both")

    # (b) sqrt(E/rho) scaling: f_1 should be linear in c_eff (fixed geometry).
    b = ax[0, 1]
    ce = np.array([xpbd[m]["c_eff"] for m in mats])
    b.plot(ce, [xpbd[m]["f_eb"] for m in mats], "k--o", label="analytic EB")
    b.plot(ce, [xpbd[m]["f_fem"] for m in mats], "C4-s", label="full-FEM truth")
    b.plot(ce, [xpbd[m]["f_meas"] for m in mats], "C0-^", lw=1.6, label="XPBD measured")
    # ideal line through origin fit to EB
    k = np.array([xpbd[m]["f_eb"] for m in mats]) / ce
    b.plot([0, ce.max()], [0, k.mean() * ce.max()], "0.6", lw=0.8, ls=":",
           label="f ∝ √(E/ρ)")
    for m in mats:
        b.annotate(m, (xpbd[m]["c_eff"], xpbd[m]["f_eb"]), fontsize=7,
                   textcoords="offset points", xytext=(4, 4))
    b.set_xlabel("√(E/ρ)  [m/s]"); b.set_ylabel("f_1 [Hz]")
    b.set_title("(b) bending-frequency scaling law f ∝ √(E/ρ)")
    b.legend(fontsize=8); b.grid(alpha=0.3)

    # (c) two-way coupling ratio per material/solver.
    c = ax[1, 0]
    w = 0.38
    c.bar(x - w / 2, [min(xpbd[m]["twoway"], 1e4) for m in mats], w, label="XPBD", color="C0")
    c.bar(x + w / 2, [min(avbd[m]["twoway"], 1e4) for m in mats], w, label="AVBD", color="C3")
    c.axhline(1.0, color="k", lw=0.6, ls="--")
    c.set_xticks(x); c.set_xticklabels(mats); c.set_ylabel("object KE two-way / one-way")
    c.set_yscale("log"); c.set_title("(c) two-way coupling strength (freeze-q̇ control)")
    c.legend(fontsize=8); c.grid(alpha=0.3, which="both")

    # (d) energy passivity: slab ring / impactor KE (should be <= ~1).
    d = ax[1, 1]
    d.bar(x - w / 2, [xpbd[m]["passivity"] for m in mats], w, label="XPBD", color="C0")
    d.bar(x + w / 2, [avbd[m]["passivity"] for m in mats], w, label="AVBD", color="C3")
    d.axhline(1.0, color="r", lw=0.8, ls="--", label="passive bound (ring=impactor KE)")
    d.set_xticks(x); d.set_xticklabels(mats)
    d.set_ylabel("slab ring peak / impactor KE")
    d.set_title("(d) energy passivity per material")
    d.legend(fontsize=8); d.grid(alpha=0.3)

    fig.suptitle("Slab-material sweep — is the two-way coupling physically accurate?  "
                 "(symplectic modal step, both solvers)", fontsize=13)
    fig.tight_layout()
    p = os.path.join(OUT, "slab_physics_accuracy.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def fig_fem(rows, order):
    """Full-FEM-truth leg (B): convergence + EB-vs-FEM freq + static deflection."""
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))

    # (a) linear-tet shear-locking convergence for the steel slab.
    L, W, t = SCENES["shelf"]["L"], SCENES["shelf"]["W"], SCENES["shelf"]["t"]
    steel = SLAB_MATERIALS["steel"]
    f1_eb = eb_f1(**steel, L=L, t=t)
    nzs = [2, 3, 4, 5]
    rr = []
    for nz in nzs:
        ff, _, _ = fem_plate_ss(L, W, t, steel["youngs"],
                                steel["poisson"], steel["density"],
                                nx=16 * nz, ny=2 * nz + 4, nz=nz, n_modes=1)
        rr.append(ff[0] / f1_eb)
    ax[0].plot(nzs, rr, "C4-o")
    ax[0].axhline(1.0, color="k", lw=0.7, ls="--", label="Euler-Bernoulli")
    ax[0].set_xlabel("tet layers through thickness"); ax[0].set_ylabel("f_FEM / f_EB")
    ax[0].set_title("(a) FEM converges to EB as locking resolves (steel)")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)

    # (b) per-material EB vs converged FEM f_1.
    mats = order
    xpbd = {r["material"]: r for r in rows if r["solver"] == "xpbd"}
    x = np.arange(len(mats)); w = 0.38
    ax[1].bar(x - w / 2, [xpbd[m]["f_eb"] for m in mats], w, label="analytic EB", color="0.4")
    ax[1].bar(x + w / 2, [xpbd[m]["f_fem"] for m in mats], w, label="full-FEM", color="C4")
    ax[1].set_xticks(x); ax[1].set_xticklabels(mats); ax[1].set_ylabel("f_1 [Hz]")
    ax[1].set_yscale("log"); ax[1].set_title("(b) analytic basis vs full-FEM truth")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3, which="both")

    # (c) static self-weight mid deflection: EB vs FEM.
    ax[2].bar(x - w / 2, [abs(xpbd[m]["d_eb"]) * 1e3 for m in mats], w,
              label="analytic EB", color="0.4")
    ax[2].bar(x + w / 2, [abs(xpbd[m]["d_fem"]) * 1e3 for m in mats], w,
              label="full-FEM", color="C4")
    ax[2].set_xticks(x); ax[2].set_xticklabels(mats)
    ax[2].set_ylabel("|static mid deflection| [mm]")
    ax[2].set_yscale("log"); ax[2].set_title("(c) static self-weight deflection")
    ax[2].legend(fontsize=8); ax[2].grid(alpha=0.3, which="both")

    fig.suptitle("Full-FEM truth (B): the synthetic basis vs a 3D solid-FEM plate",
                 fontsize=12)
    fig.tight_layout()
    p = os.path.join(OUT, "fem_vs_analytic.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print("### slab-material sweep + physics accuracy ###", flush=True)
    rows, order = gather(quick=args.quick)
    p1 = fig_accuracy(rows, order)
    p2 = fig_fem(rows, order)
    keys = ["material", "solver", "E", "rho", "nu", "c_eff", "f_eb", "f_fem",
            "f_meas", "hz", "fem_nodes", "d_fem", "d_eb", "twoway", "passivity",
            "Eslab", "Eimp", "finite"]
    with open(os.path.join(OUT, "slab_material_sweep.csv"), "w", newline="") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=keys)
        wcsv.writeheader()
        for r in rows:
            wcsv.writerow({k: r[k] for k in keys})
    print(f"\nwrote {p1}\n      {p2}\n      slab_material_sweep.csv")


if __name__ == "__main__":
    main()
