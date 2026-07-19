#!/usr/bin/env python3
"""MIG short paper F1 (teaser) — the governor activating on a starved budget.

Modal mechanical energy of the support through one impact, same scene, same
budget (8x2), same relaxation; the ONLY difference is whether the cumulative
storage bound is enforced. Un-governed the modal energy runs to 1556 J in a
scene whose incident rigid kinetic energy is ~29 J; governed it peaks at
29.3 J and stays under the running supply budget eta*sum(max(dE_rigid,0))
that funds it (dashed).

Reads the committed trace CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_s3_activation.py
"""
from __future__ import annotations

import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import apply_style, save, PALETTE

CSV = os.path.join(_ROOT,
                   "benchmarks/paper_eval/x1_passivity/out/activation_trace.csv")


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))
    t = [float(r["t_s"]) for r in rows]
    off = [float(r["E_modal_off_J"]) for r in rows]
    on = [float(r["E_modal_on_J"]) for r in rows]
    bud = [float(r["ledger_budget_on_J"]) for r in rows]

    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    ax.plot(t, off, color=PALETTE["clamp_off"], label="governor OFF")
    ax.plot(t, on, color=PALETTE["native"], label="governor ON")
    ax.plot(t, bud, color="0.35", ls=(0, (5, 2)), lw=1.0,
            label=r"supply budget $\eta\sum\max(\Delta E_{\mathrm{rig}},0)$")
    ax.set_yscale("log")
    ax.set_xlabel("time [s]")
    ax.set_ylabel("modal mechanical energy [J]")
    ax.legend(frameon=False, fontsize=6.5, loc="lower right")
    ax.set_ylim(top=max(off) * 6.0)
    ax.annotate(f"peak {max(off):.0f} J",
                xy=(t[off.index(max(off))], max(off)),
                xytext=(6, 4), textcoords="offset points", fontsize=6.5,
                color=PALETTE["clamp_off"], ha="left")
    save(fig, "fig_s3_activation.pdf")


if __name__ == "__main__":
    main()
