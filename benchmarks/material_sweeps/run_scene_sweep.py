#!/usr/bin/env python3
"""Multi-scene verification: does the two-way coupling generalise across the
non-cargo scenes? ISOLATED benchmark.

For shelf / ledge / dinner (each with its OWN reduced-support plate geometry),
default slab material, both native solvers, **symplectic modal step + modal
relaxation 0.7**: measure the modal ring frequency (detrended FFT of q0) against
that scene's analytic Euler-Bernoulli f_1, plus the two-way ratio (freeze-q̇
control) and energy passivity.

Out: benchmarks/material_sweeps/out/{scene_sweep.png, scene_sweep.csv}
Run: .venv/bin/python benchmarks/material_sweeps/run_scene_sweep.py [--quick]
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
    SCENES, RELAX, eb_f1, measure_ring_freq, coupling_metrics,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SOLVERS = ("xpbd", "avbd")
# default slab material per scene (matches each scene builder's default).
SCENE_DEFAULT_MAT = {
    "shelf":  dict(youngs=5.0e8,  density=600.0, poisson=0.30),
    "ledge":  dict(youngs=1.0e10, density=500.0, poisson=0.30),
    "dinner": dict(youngs=1.0e10, density=500.0, poisson=0.30),
}


def gather(quick=False):
    rows = []
    nf = 140 if quick else 200
    for name, sc in SCENES.items():
        L, t = sc["L"], sc["t"]
        mat = SCENE_DEFAULT_MAT[name]
        f_eb = eb_f1(**mat, L=L, t=t)
        for solver in SOLVERS:
            cm = coupling_metrics(sc["build"], solver, relax=RELAX, n_frames=nf)
            f_meas, hz = measure_ring_freq(sc["build"], solver, L=L, t=t,
                                           relax=RELAX, f_hint=f_eb)
            err = abs(f_meas - f_eb) / f_eb * 100.0 if f_eb > 0 else float("nan")
            rows.append(dict(scene=name, solver=solver, f_eb=f_eb, f_meas=f_meas,
                             err_pct=err, twoway=cm["twoway_ratio"],
                             passivity=cm["passivity"], Eslab=cm["Eslab_peak"],
                             Eimp=cm["Eimp_peak"], finite=cm["finite"]))
            print(f"  {name:7s}/{solver}: f_EB={f_eb:6.1f}  f_meas={f_meas:6.1f}Hz "
                  f"({err:4.0f}%)  two-way={cm['twoway_ratio']:6.1f}x  "
                  f"passivity={cm['passivity']:.2f}", flush=True)
    return rows


def fig_scene(rows):
    scenes = list(SCENES)
    xp = {r["scene"]: r for r in rows if r["solver"] == "xpbd"}
    av = {r["scene"]: r for r in rows if r["solver"] == "avbd"}
    x = np.arange(len(scenes)); w = 0.28
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))

    # (a) ring frequency: EB vs measured (both solvers).
    a = ax[0]
    a.bar(x - w, [xp[s]["f_eb"] for s in scenes], w, label="analytic EB", color="0.4")
    a.bar(x, [xp[s]["f_meas"] for s in scenes], w, label="XPBD measured", color="C0")
    a.bar(x + w, [av[s]["f_meas"] for s in scenes], w, label="AVBD measured", color="C3")
    a.set_xticks(x); a.set_xticklabels(scenes); a.set_ylabel("fundamental f_1 [Hz]")
    a.set_title("(a) ring frequency vs Euler-Bernoulli (relax 0.7)")
    a.legend(fontsize=8); a.grid(alpha=0.3)

    # (b) two-way ratio.
    b = ax[1]
    b.bar(x - w / 2, [min(xp[s]["twoway"], 1e4) for s in scenes], w, label="XPBD", color="C0")
    b.bar(x + w / 2, [min(av[s]["twoway"], 1e4) for s in scenes], w, label="AVBD", color="C3")
    b.axhline(1.0, color="k", lw=0.6, ls="--")
    b.set_xticks(x); b.set_xticklabels(scenes); b.set_ylabel("object KE two-way / one-way")
    b.set_yscale("log"); b.set_title("(b) two-way coupling strength")
    b.legend(fontsize=8); b.grid(alpha=0.3, which="both")

    # (c) passivity.
    c = ax[2]
    c.bar(x - w / 2, [xp[s]["passivity"] for s in scenes], w, label="XPBD", color="C0")
    c.bar(x + w / 2, [av[s]["passivity"] for s in scenes], w, label="AVBD", color="C3")
    c.axhline(1.0, color="r", lw=0.8, ls="--", label="passive bound")
    c.set_xticks(x); c.set_xticklabels(scenes); c.set_ylabel("slab ring / impactor KE")
    c.set_title("(c) energy passivity"); c.legend(fontsize=8); c.grid(alpha=0.3)

    fig.suptitle("Multi-scene verification (shelf / ledge / dinner) — "
                 "symplectic modal step, relax 0.7, both solvers", fontsize=12)
    fig.tight_layout()
    p = os.path.join(OUT, "scene_sweep.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print("### multi-scene verification (relax 0.7, symplectic) ###", flush=True)
    rows = gather(quick=args.quick)
    p = fig_scene(rows)
    keys = ["scene", "solver", "f_eb", "f_meas", "err_pct", "twoway",
            "passivity", "Eslab", "Eimp", "finite"]
    with open(os.path.join(OUT, "scene_sweep.csv"), "w", newline="") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=keys)
        wcsv.writeheader()
        for r in rows:
            wcsv.writerow(r)
    print(f"\nwrote {p}\n      scene_sweep.csv")


if __name__ == "__main__":
    main()
