#!/usr/bin/env python3
"""W5 restyle — dinner drop: per-body peak jump vs distance (3 drop points).

Each panel is one pot drop point along the table; every place-setting body's peak
upward jump is plotted against its horizontal distance from the drop. The native
rigid-dish arm (DCR's own §4.5 config, blue) reproduces the full-FEM GT (black
dashed) distance falloff at ~7x lower amplitude (rigid-step band-limiting); the
all-cargo variant (teal) responds less again as soft bodies absorb the impact
compliantly. Toppled bodies (>0.3 m jump) and non-responders (<=0) are excluded
per the ground-truth contact limitation (counts printed).

Reads only the baked committed CSV (see _bake_dinner_response.py). Run:
  .venv/bin/python benchmarks/paper_fig/fig_dinner_response.py
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

from benchmarks.paper_fig.figstyle import PALETTE, GT_DASH, apply_style, save

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/dinner_response.csv")
ARMS = [("gt_mm", PALETTE["gt"], GT_DASH, "o", "full-FEM GT"),
        ("native_rigid_mm", PALETTE["native"], "-", "s", "native (rigid dishes)"),
        ("native_cargo_mm", PALETTE["variant"], "-", "^", "all-cargo variant")]
TOPPLE_MM = 300.0
FLOOR_MM = 0.05


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))
    drops = sorted(set(int(r["drop_idx"]) for r in rows))

    fig, axes = plt.subplots(1, len(drops), figsize=(7.0, 2.6), sharey=True)
    if len(drops) == 1:
        axes = [axes]
    for ax, di in zip(axes, drops):
        drows = [r for r in rows if int(r["drop_idx"]) == di]
        drop = (float(drows[0]["drop_x"]), float(drows[0]["drop_z"]))
        n_excl = 0
        for key, col, ls, mk, lab in ARMS:
            xs, ys = [], []
            for r in drows:
                v = r[key]
                if v == "":
                    continue
                v = float(v)
                if v > TOPPLE_MM:
                    n_excl += 1
                    continue
                if v < FLOOR_MM:
                    continue
                xs.append(float(r["dist_m"]))
                ys.append(v)
            o = np.argsort(xs)
            xs, ys = np.array(xs)[o], np.array(ys)[o]
            ax.plot(xs, ys, ls=ls if key != "gt_mm" else GT_DASH, marker=mk,
                    color=col, label=lab, ms=3.5, lw=1.1)
        ax.set_yscale("log")
        ax.set_xlabel("distance from drop  [m]")
        ax.set_title(f"drop ({drop[0]:g}, {drop[1]:g})", fontsize=7.5)
        ax.tick_params(labelsize=6.5)
    axes[0].set_ylabel(r"peak upward jump  [mm]")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False,
               fontsize=7, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(w_pad=0.8, rect=(0, 0.06, 1, 1))
    save(fig, "fig_dinner_response.pdf")


if __name__ == "__main__":
    main()
