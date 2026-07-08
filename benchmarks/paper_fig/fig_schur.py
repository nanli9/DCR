#!/usr/bin/env python3
"""W5 — cross-term Schur vs gated block-GS q-block (E9), from committed CSV.

Peak modal energy vs iteration budget for the two q-block formulations (shelf,
clamp OFF, monitor ledger). The rejected cross-term Schur blows up at the
truncated 4x1 budget (net-injects, open marker) while the shipped under-relaxed
block-GS stays well-behaved and passive at every budget; the two converge to
parity once the solve is converged (32x4). Open markers = the ledger flags the
run as injecting (passive=False).

Reads only the committed CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_schur.py
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

from benchmarks.paper_fig.figstyle import PALETTE, apply_style, save

CSV = os.path.join(_ROOT, "benchmarks/paper_eval/x1_passivity/out/schur_vs_blockgs.csv")


def _budget_x(b):
    it, su = b.split("x")
    return int(it) * int(su)


def main():
    apply_style()
    with open(CSV) as fh:
        rows = sorted(csv.DictReader(fh), key=lambda r: _budget_x(r["budget"]))

    x = [_budget_x(r["budget"]) for r in rows]
    labels = [r["budget"] for r in rows]
    bg = [float(r["blockgs_peak"]) for r in rows]
    sc = [float(r["schur_peak"]) for r in rows]
    bg_pass = [r["blockgs_passive"] == "True" for r in rows]
    sc_pass = [r["schur_passive"] == "True" for r in rows]

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    ax.plot(x, bg, color=PALETTE["native"], zorder=2, label="gated block-GS (shipped)")
    ax.plot(x, sc, color=PALETTE["variant"], zorder=2, label="cross-term Schur (rejected)")
    # filled = passive, open = ledger flags injecting
    for xi, yi, p in zip(x, bg, bg_pass):
        ax.scatter([xi], [yi], s=26, color=PALETTE["native"], zorder=3,
                   facecolors=PALETTE["native"] if p else "white",
                   edgecolors=PALETTE["native"], linewidths=1.1)
    for xi, yi, p in zip(x, sc, sc_pass):
        ax.scatter([xi], [yi], s=30, marker="s", zorder=3,
                   facecolors=PALETTE["variant"] if p else "white",
                   edgecolors=PALETTE["variant"], linewidths=1.1)

    # injection annotation on the 4x1 Schur point
    inj = next((i for i, p in enumerate(sc_pass) if not p), None)
    if inj is not None:
        ax.annotate("Schur injects\n(net excess 9.4e3 J)", xy=(x[inj], sc[inj]),
                    xytext=(x[inj] * 1.4, sc[inj] * 0.12), fontsize=6.5,
                    color=PALETTE["clamp_off"],
                    arrowprops=dict(arrowstyle="->", color=PALETTE["clamp_off"], lw=0.7))
    ax.annotate("parity (1%)", xy=(x[-1], sc[-1]), xytext=(x[-1] * 0.42, sc[-1] * 2.4),
                fontsize=6.5, color="0.35",
                arrowprops=dict(arrowstyle="->", color="0.6", lw=0.6))

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("iteration budget (iters × substeps)")
    ax.set_ylabel("peak modal energy  [J]")
    ax.legend(loc="center right", frameon=False)
    fig.tight_layout()
    save(fig, "fig_schur.pdf")


if __name__ == "__main__":
    main()
