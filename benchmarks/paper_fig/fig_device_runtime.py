#!/usr/bin/env python3
"""W5 — device-path runtime + passivity (E7-device / G3a), from committed CSVs.

Panel (a): ms/step vs iteration budget for the two swept scenes (dinner, ledge)
on the device-resident co-solved path; the 120 Hz real-time line + shaded
real-time region show the interactive-to-real-time crossover.
Panel (b): the §15 passivity ledger over all 20 (scene x budget) cells --
realized modal gain vs the eta*rigid-loss budget, every point below the y=x
passive boundary (passive by construction, no active clamp).

Reads only committed CSVs. Run:
  .venv/bin/python benchmarks/paper_fig/fig_device_runtime.py
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

X5 = os.path.join(_ROOT, "benchmarks/paper_eval/x5_perf/out")
RT_MS = 1000.0 / 120.0


def _read(path):
    with open(path) as fh:
        return list(csv.DictReader(fh))


def _budget_x(b):
    it, su = b.split("x")
    return int(it) * int(su)          # iteration-substep product


def main():
    apply_style()
    budget = _read(os.path.join(X5, "perf_device_budget.csv"))
    psv = _read(os.path.join(X5, "device_passivity.csv"))

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.0, 2.7))

    # ---- (a) runtime vs budget ------------------------------------------- #
    scene_style = {"dinner": (PALETTE["native"], "o", "dinner (24 modes)"),
                   "ledge": (PALETTE["variant"], "s", "ledge (16 modes)")}
    for scene, (col, mk, lab) in scene_style.items():
        rows = sorted((r for r in budget if r["scene"] == scene),
                      key=lambda r: _budget_x(r["budget"]))
        xs = [_budget_x(r["budget"]) for r in rows]
        ys = [float(r["mean_ms"]) for r in rows]
        axa.plot(xs, ys, marker=mk, color=col, label=lab)
    axa.axhspan(0, RT_MS, color=PALETTE["rt"], alpha=0.12)
    axa.axhline(RT_MS, color=PALETTE["rt"], lw=0.9, ls="--")
    axa.text(9, RT_MS * 1.06, "120 Hz real-time", color=PALETTE["rt"],
             fontsize=6.5, va="bottom")
    axa.set_xscale("log", base=2)
    axa.set_yscale("log")
    xticks = [8, 16, 32, 64, 128]
    axa.set_xticks(xticks)
    axa.set_xticklabels(["8×1", "8×2", "16×2", "16×4", "32×4"])
    axa.set_xlabel("iteration budget (iters × substeps)")
    axa.set_ylabel("ms / step (RTX 4090)")
    axa.legend(loc="upper left", frameon=False)
    axa.set_title("(a)", loc="left", fontsize=8)

    # ---- (b) passivity ledger, 20 cells ---------------------------------- #
    scenes = sorted(set(r["scene"] for r in psv))
    cmap = {"dinner": PALETTE["native"], "ledge": PALETTE["variant"],
            "shelf": PALETTE["dcr"], "truck": PALETTE["clamp_off"]}
    mk = {"dinner": "o", "ledge": "s", "shelf": "^", "truck": "D"}
    for sc in scenes:
        rows = [r for r in psv if r["scene"] == sc]
        x = [float(r["eta_cum_loss"]) for r in rows]
        y = [float(r["cum_modal_gain"]) for r in rows]
        axb.scatter(x, y, s=22, color=cmap.get(sc, "gray"),
                    marker=mk.get(sc, "o"), label=sc, zorder=3,
                    edgecolors="white", linewidths=0.4)
    lo, hi = 1.0, 1e3
    axb.plot([lo, hi], [lo, hi], color="0.35", lw=0.9, ls="--", zorder=2)
    axb.text(hi * 0.9, hi * 0.9, r"$\Delta E_{\rm m}=\eta\,\Delta E_{\rm r}$",
             fontsize=6.5, ha="right", va="top", rotation=45, color="0.35")
    axb.fill_between([lo, hi], [lo, hi], hi, color=PALETTE["rt"], alpha=0.08)
    axb.set_xscale("log")
    axb.set_yscale("log")
    axb.set_xlim(lo, hi)
    axb.set_ylim(lo, hi)
    axb.set_xlabel(r"budget $\eta\,\Sigma\,\Delta E_{\rm rigid\ loss}$  [J]")
    axb.set_ylabel(r"realized $\Sigma\,\Delta E_{\rm modal\ gain}$  [J]")
    axb.legend(loc="lower right", frameon=False, ncol=2, handletextpad=0.2,
               columnspacing=0.8)
    axb.text(1.5, hi * 0.5, "20/20 passive\nno active clamp", fontsize=6.5,
             color=PALETTE["rt"], va="top")
    axb.set_title("(b)", loc="left", fontsize=8)

    fig.tight_layout(w_pad=1.5)
    save(fig, "fig_device_runtime.pdf")


if __name__ == "__main__":
    main()
