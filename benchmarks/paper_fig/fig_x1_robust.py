#!/usr/bin/env python3
"""W5 restyle — X1 adversarial passivity robustness (E1 ablation).

Passivity ratio (peak modal energy over the eta*rigid-loss budget) across
scene x relaxation x iteration budget, clamp OFF vs ON. OFF injects at truncated
budgets (up to 1.2e5x on ledge); ON passes the ledger invariant in every cell and
is bit-inert in the already-safe region. Log color; the passive line is ratio=1.

Reads only the vendored committed CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_x1_robust.py
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

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/robustness_clamp.csv")


def _fmt(v):
    if v >= 100:
        return f"{v:.0e}".replace("e+0", "e").replace("e+", "e")
    if v >= 10:
        return f"{v:.0f}"
    return f"{v:.2f}"


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))

    scenes = ["shelf", "ledge", "dinner"]
    relaxes = sorted(set(float(r["relax"]) for r in rows))
    budgets = sorted(set((int(r["iters"]), int(r["substeps"])) for r in rows),
                     key=lambda b: b[0] * b[1])
    cols = [(s, rx) for s in scenes for rx in relaxes]
    col_lab = [f"{s}\n$\\omega_r$={rx:g}" for s, rx in cols]
    row_lab = [f"{it}×{su}" for it, su in budgets]

    def grid(key):
        M = np.full((len(budgets), len(cols)), np.nan)
        for r in rows:
            b = (int(r["iters"]), int(r["substeps"]))
            c = (r["scene"], float(r["relax"]))
            if b in budgets and c in cols:
                M[budgets.index(b), cols.index(c)] = float(r[key])
        return M

    off, on = grid("passivity_off"), grid("passivity_on")
    Loff, Lon = np.log10(off), np.log10(on)
    norm = TwoSlopeNorm(vmin=-1.0, vcenter=0.0, vmax=5.0)  # log10; 0 = passive (ratio 1)
    cmap = plt.get_cmap("RdBu_r")

    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    for ax, L, raw, title in ((axes[0], Loff, off, "clamp OFF"),
                              (axes[1], Lon, on, "clamp ON")):
        im = ax.imshow(L, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels(col_lab, fontsize=6)
        ax.set_yticks(range(len(budgets)))
        ax.set_yticklabels(row_lab, fontsize=7)
        for i in range(len(budgets)):
            for j in range(len(cols)):
                v = raw[i, j]
                if np.isnan(v):
                    continue
                lum = norm(np.log10(v))
                ax.text(j, i, _fmt(v), ha="center", va="center", fontsize=5.4,
                        color="white" if (lum > 0.72 or lum < 0.2) else "black")
        ax.set_title(title, fontsize=8)
        ax.set_xticks(np.arange(-.5, len(cols), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(budgets), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.0)
        ax.tick_params(which="minor", length=0)

    # y-axis title on the left panel only — both panels share the same budget
    # rows, and a title on the right panel collides with the left panel's cells.
    axes[0].set_ylabel("budget (iters × substeps)")

    cb = fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02,
                      ticks=[-1, 0, 1, 3, 5])
    cb.ax.set_yticklabels(["0.1", "1", "10", r"$10^3$", r"$10^5$"], fontsize=6.5)
    cb.set_label("passivity ratio (injection factor)", fontsize=7)
    save(fig, "fig_x1_robust.pdf")


if __name__ == "__main__":
    main()
