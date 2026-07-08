#!/usr/bin/env python3
"""W5 — ledge FEM ground truth: convergence (E2) + standing-wave falloff (E3).

Panel (a): native/GT peak deflection ratio vs rigid step 1/h, converging toward
the GT (dashed at 1.0); ring frequency matches to 0.4% at 1/960 (annotated).
Panel (b): peak |u_y| along the probe line vs distance from the boulder impact
-- native (blue) tracks the GT (black dashed); both PEAK at the pedestal
(antinode), not under the impact: the modal standing wave, no fitted falloff.

Reads only committed CSVs. Run:
  .venv/bin/python benchmarks/paper_fig/fig_ledge_gt.py
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

X3 = os.path.join(_ROOT, "benchmarks/paper_eval/x3_ground_truth/out")


def _read(path):
    with open(path) as fh:
        return list(csv.DictReader(fh))


def main():
    apply_style()
    conv = _read(os.path.join(X3, "ledge_convergence.csv"))
    fall = _read(os.path.join(X3, "ledge_falloff.csv"))

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.0, 2.7))

    # ---- (a) convergence ------------------------------------------------- #
    hinv = [int(r["h_inv"]) for r in conv]
    ratio = [float(r["ratio_peak"]) for r in conv]
    axa.plot(hinv, ratio, marker="o", color=PALETTE["native"], label="native / GT")
    axa.axhline(1.0, color=PALETTE["gt"], lw=0.9, ls=GT_DASH)
    axa.text(130, 1.005, "GT", color=PALETTE["gt"], fontsize=6.5, va="bottom")
    axa.set_xscale("log", base=2)
    axa.set_xticks(hinv)
    axa.set_xticklabels([f"1/{h}" for h in hinv])
    axa.set_ylim(0.3, 1.05)
    axa.set_xlabel("rigid step $h$  [s]")
    axa.set_ylabel("peak-deflection ratio  native / GT")
    fr = conv[-1]
    axa.annotate(f"ring {float(fr['f_ring_native']):.0f} vs "
                 f"{float(fr['f_ring_gt']):.0f} Hz\n(0.4% @ 1/960)",
                 xy=(hinv[-1], ratio[-1]), xytext=(200, 0.5), fontsize=6.5,
                 color="0.35", arrowprops=dict(arrowstyle="->", color="0.6", lw=0.6))
    axa.set_title("(a)", loc="left", fontsize=8)

    # ---- (b) standing-wave falloff --------------------------------------- #
    d = [float(r["dist_from_impact_m"]) for r in fall]
    rn = [float(r["resp_native"]) * 1e3 for r in fall]   # mm
    rg = [float(r["resp_gt"]) * 1e3 for r in fall]
    axb.plot(d, rg, marker="o", color=PALETTE["gt"], ls=GT_DASH, label="full-FEM GT")
    axb.plot(d, rn, marker="s", color=PALETTE["native"], label="native")
    # pedestal antinode marker (peak of GT)
    ip = int(np.argmax(rg))
    axb.annotate("pedestal\n(antinode)", xy=(d[ip], rg[ip]),
                 xytext=(d[ip] + 0.08, rg[ip] * 0.72), fontsize=6.5, color="0.35",
                 arrowprops=dict(arrowstyle="->", color="0.6", lw=0.6))
    axb.set_xlabel("distance from impact  [m]")
    axb.set_ylabel(r"peak $|u_y|$  [mm]")
    axb.legend(loc="lower left", frameon=False)
    axb.text(0.98, 0.96, r"Spearman $\rho=0.89$", transform=axb.transAxes,
             ha="right", va="top", fontsize=6.5, color="0.35")
    axb.set_title("(b)", loc="left", fontsize=8)

    fig.tight_layout(w_pad=1.5)
    save(fig, "fig_ledge_gt.pdf")


if __name__ == "__main__":
    main()
