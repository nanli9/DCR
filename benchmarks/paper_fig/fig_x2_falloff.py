#!/usr/bin/env python3
"""W5 restyle — X2 distant-response falloff vs paper-DCR (reference slab).

Peak distant-object KE vs distance from the impact. The native arm's falloff is
the slab's low-mode standing wave (gentle, reached with no C*r^-beta fit); paper-
DCR's forced IIR decays steeply in the near field, so the curves cross and the
native arm carries more energy to the far object. Rigid (no coupling) is the null:
zero beyond the struck body.

Reads only the vendored committed CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_x2_falloff.py
"""
from __future__ import annotations

import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import PALETTE, GT_DASH, apply_style, save

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "data/x2_response_vs_distance.csv")


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))
    d = [float(r["dist_m"]) for r in rows]
    dcr = [float(r["dcr_peakKE_mJ"]) for r in rows]
    nat = [float(r["native_peakKE_mJ"]) for r in rows]
    rig = [float(r["rigid_peakKE_mJ"]) for r in rows]

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    ax.plot(d, dcr, marker="o", color=PALETTE["dcr"], label="paper-DCR (forced IIR)")
    ax.plot(d, nat, marker="s", color=PALETTE["native"], label="native (standing wave)")
    # rigid null: nonzero only at the struck body
    rd = [(di, ri) for di, ri in zip(d, rig) if ri > 0]
    if rd:
        ax.scatter([p[0] for p in rd], [p[1] for p in rd], marker="x", s=26,
                   color="0.5", label="rigid (no coupling)", zorder=3)
    ax.annotate("curves cross\n(native gentler far)",
                xy=(0.305, 5.0), xytext=(0.40, 6.0), fontsize=6.5, color="0.35",
                ha="left", arrowprops=dict(arrowstyle="->", color="0.6", lw=0.6))
    ax.set_yscale("log")
    ax.set_xlabel("distance from impact  [m]")
    ax.set_ylabel("peak distant-object KE  [mJ]")
    ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    save(fig, "fig_x2_falloff.pdf")


if __name__ == "__main__":
    main()
