#!/usr/bin/env python3
"""MIG short paper F3 — the symmetric three-solver adversarial budget matrix.

One row of contact physics run in three fixed-budget solver formulations over
the SAME 24 cells (scene x relax x budget), clamp OFF. Colour is the energy
ratio (peak modal energy / peak incident rigid KE) on a log scale diverging at
ratio = 1 (the injection threshold): red = injecting, blue = within the bound.

XPBD injects in 8/24 cells (worst 1.20e5), AVBD in 2/24 (worst 1.70), the
implicit sequential-impulse backend in 0/24 (worst 0.53).

The relaxation axis is INERT on the impulse backend by construction
(solver_impulse.py:290-292 -- the implicit modal weight needs no
under-relaxation); its two relax rows are bit-identical and are drawn hatched to
say so rather than implying an independent measurement.

Reads the committed E-S1b CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_s1_solver_matrix.py
"""
from __future__ import annotations

import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

from benchmarks.paper_fig.figstyle import apply_style, save

CSV = os.path.join(_ROOT, "benchmarks/paper_eval/x1_passivity/out/solver_matrix.csv")
SOLVERS = [("xpbd", "XPBD"), ("avbd", "AVBD"), ("impulse", "impulse")]
SCENES = ["shelf", "ledge", "dinner"]
SCENE_LABEL = {"shelf": "shelf", "ledge": "ledge", "dinner": "table"}
RELAXES = [0.7, 1.0]
BUDGETS = [(4, 1), (8, 2), (16, 4), (32, 8)]


def _fmt(v):
    if v >= 1e4:
        return f"{v:.0e}".replace("e+0", "e").replace("e+", "e")
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))

    idx = {(r["solver"], r["scene"], float(r["relax"]),
            int(r["iters"]), int(r["substeps"])): float(r["ratio_off"])
           for r in rows}

    ylabels = [f"{SCENE_LABEL[s]}  {rl:g}" for s in SCENES for rl in RELAXES]
    xlabels = [f"{i}$\\times${s}" for (i, s) in BUDGETS]

    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.5), sharey=True)
    # log10 ratio, diverging at 0 (= ratio 1, the injection threshold)
    norm = TwoSlopeNorm(vmin=-1.2, vcenter=0.0, vmax=5.2)
    cmap = plt.get_cmap("RdBu_r")

    for ax, (key, label) in zip(axes, SOLVERS):
        M = np.zeros((len(ylabels), len(BUDGETS)))
        for i, scene in enumerate(SCENES):
            for j, rl in enumerate(RELAXES):
                for k, (it, su) in enumerate(BUDGETS):
                    M[i * len(RELAXES) + j, k] = idx[(key, scene, rl, it, su)]
        ax.imshow(np.log10(M), cmap=cmap, norm=norm, aspect="auto")
        for a in range(M.shape[0]):
            for b in range(M.shape[1]):
                v = M[a, b]
                ax.text(b, a, _fmt(v), ha="center", va="center", fontsize=5.6,
                        color="white" if (v > 30 or v < 0.12) else "black")
        # mark the inert relax axis on the impulse panel
        if key == "impulse":
            for a in range(M.shape[0]):
                if a % 2 == 1:
                    ax.add_patch(plt.Rectangle(
                        (-0.5, a - 0.5), M.shape[1], 1.0, fill=False,
                        hatch="///", edgecolor="0.45", linewidth=0.0, alpha=0.55))
        ax.set_xticks(range(len(xlabels)), xlabels, fontsize=6.5)
        ax.set_title(label, fontsize=8, pad=3)
        ax.grid(False)
        ax.set_xlabel("iterations $\\times$ substeps", fontsize=7)

    axes[0].set_yticks(range(len(ylabels)), ylabels, fontsize=6.5)
    axes[0].set_ylabel("scene, modal relaxation", fontsize=7)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cb = fig.colorbar(sm, ax=axes, fraction=0.022, pad=0.015,
                      ticks=[-1, 0, 1, 2, 3, 4, 5])
    cb.ax.set_yticklabels(["$10^{-1}$", "$10^{0}$", "$10^{1}$", "$10^{2}$",
                           "$10^{3}$", "$10^{4}$", "$10^{5}$"], fontsize=6.5)
    cb.set_label("peak modal energy / incident rigid KE", fontsize=7)
    cb.ax.axhline(0.0, color="k", lw=1.0)

    save(fig, "fig_s1_solver_matrix.pdf")


if __name__ == "__main__":
    main()
