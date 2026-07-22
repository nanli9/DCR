#!/usr/bin/env python3
"""MIG short paper Fig. 2 (practitioner-diagnostic rewrite) — XPBD-CENTERED.

The rewrite reframes the paper from a three-solver survey into a fixed-budget
XPBD practitioner diagnostic, so this figure is NOT a solver competition. The
tested XPBD implementation gets the full scene x budget map (the practitioner's
own host); AVBD and the implicit realization appear only as a compact control
strip -- one implementation of each, NOT compliance- or cost-matched.

  LEFT  : XPBD-only, two stacked maps over the 24 cells (3 scenes x relax
          {0.7,1.0} x 4 budgets), governor OFF.
            top    R = peak modal E / peak incident rigid KE  (severity diagnostic)
            bottom M = Eq.(2) strict margin [J]               (the invariant; >0 violates)
          The two disagree by design (R>1 in 8/24, margin>0 in 9/24) -- that
          divergence is a result, not noise.
  RIGHT : a 3-row control strip (XPBD / AVBD / implicit) with the three summary
          numbers the plan asks for: violating cells (R>1 | Eq.2>0), worst Eq.(2)
          margin [J], worst R. It establishes the controls and the scale gap
          (4.4e7 J vs 6.7 J vs 0) without a co-equal heatmap.

The full two-metric 72-cell three-solver heatmap moves to the supplement
(fig_s1_solver_matrix.py, unchanged).

Reads the R1 CSV (eq2_utilization.csv), whose R column is asserted against the
frozen E-S1b clamp-OFF values by run_eq2_utilization --check-frozen.

Run: .venv/bin/python benchmarks/paper_fig/fig_xpbd_map.py
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
from matplotlib.colors import TwoSlopeNorm, SymLogNorm

from benchmarks.paper_fig.figstyle import apply_style, save

CSV = os.path.join(_ROOT,
                   "benchmarks/paper_eval/x1_passivity/out/eq2_utilization.csv")
SCENES = ["shelf", "ledge", "dinner"]
SCENE_LABEL = {"shelf": "shelf", "ledge": "ledge", "dinner": "table"}
RELAXES = [0.7, 1.0]
BUDGETS = [(4, 1), (8, 2), (16, 4), (32, 8)]
IMPLS = [("xpbd", "XPBD (tested)"), ("avbd", "AVBD"), ("impulse", "implicit")]

CMAP = plt.get_cmap("RdBu_r")
NORM_R = TwoSlopeNorm(vmin=-1.2, vcenter=0.0, vmax=5.2)
NORM_M = SymLogNorm(linthresh=1e-2, linscale=0.6, vmin=-1e3, vmax=1e8, base=10)


def _fmt_R(v):
    if not np.isfinite(v):
        return "--"
    if v >= 1e4:
        return f"{v:.0e}".replace("e+0", "e").replace("e+", "e")
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def _fmt_M(v):
    if not np.isfinite(v):
        return "--"
    a = abs(v)
    if a >= 1e4:
        s = f"{a:.0e}".replace("e+0", "e").replace("e+", "e")
    elif a >= 10:
        s = f"{a:.0f}"
    elif a >= 0.1:
        s = f"{a:.2f}"
    else:
        s = f"{a:.0e}".replace("e-0", "e-")
    return ("+" if v > 0 else "−") + s


def _grid(idx, field):
    M = np.full((len(SCENES) * len(RELAXES), len(BUDGETS)), np.nan)
    for i, scene in enumerate(SCENES):
        for j, rl in enumerate(RELAXES):
            for k, (it, su) in enumerate(BUDGETS):
                v = idx.get(("xpbd", scene, rl, it, su), {}).get(field)
                if v is not None:
                    M[i * len(RELAXES) + j, k] = v
    return M


def _heat(ax, M, kind, title):
    if kind == "R":
        ax.imshow(np.log10(M), cmap=CMAP, norm=NORM_R, aspect="auto")
        fmt, hot = _fmt_R, (lambda v: v > 30 or v < 0.12)
    else:
        ax.imshow(M, cmap=CMAP, norm=NORM_M, aspect="auto")
        fmt, hot = _fmt_M, (lambda v: v > 1e2 or v < -1e2)
    for a in range(M.shape[0]):
        for b in range(M.shape[1]):
            v = M[a, b]
            ax.text(b, a, fmt(v), ha="center", va="center", fontsize=5.6,
                    color="white" if (np.isfinite(v) and hot(v)) else "black")
    ax.set_title(title, fontsize=8, pad=3)
    ax.grid(False)
    ax.set_yticks(range(len(SCENES) * len(RELAXES)),
                  [f"{SCENE_LABEL[s]} {rl:g}" for s in SCENES for rl in RELAXES],
                  fontsize=6.3)


def _summary(rows):
    out = {}
    for sol, _ in IMPLS:
        sr = [r for r in rows if r["solver"] == sol]
        nR = sum(1 for r in sr if float(r["ratio_off"]) > 1)
        nEq2 = sum(1 for r in sr if r["eq2_violates"] == "True")
        wM = max(float(r["margin_J"]) for r in sr)
        wR = max(float(r["ratio_off"]) for r in sr)
        out[sol] = (nR, nEq2, wM, wR)
    return out


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))

    def _f(r, k):
        v = r.get(k, "")
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    idx = {}
    for r in rows:
        idx[(r["solver"], r["scene"], float(r["relax"]),
             int(r["iters"]), int(r["substeps"]))] = {
            "R": _f(r, "ratio_off"), "M": _f(r, "margin_J")}
    summ = _summary(rows)

    fig = plt.figure(figsize=(7.0, 3.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.15], height_ratios=[1, 1],
                          wspace=0.32, hspace=0.42)
    axR = fig.add_subplot(gs[0, 0])
    axM = fig.add_subplot(gs[1, 0])
    axS = fig.add_subplot(gs[:, 1])

    _heat(axR, _grid(idx, "R"), "R",
          "XPBD: $R$ = peak modal E / incident KE")
    _heat(axM, _grid(idx, "M"), "M", "XPBD: Eq.~(2) margin [J]  ($>$0 violates)")
    axM.set_xticks(range(len(BUDGETS)),
                   [f"{i}$\\times${s}" for (i, s) in BUDGETS], fontsize=6.5)
    axM.set_xlabel("iterations $\\times$ substeps", fontsize=7)
    axR.set_xticks(range(len(BUDGETS)), [""] * len(BUDGETS))

    # ---- control strip -------------------------------------------------
    axS.axis("off")
    axS.set_title("controls (one implementation each;\nnot compliance- "
                  "or cost-matched)", fontsize=7.2, pad=6)
    col_x = [0.0, 0.34, 0.62, 0.88]
    headers = ["", "cells\n$R{>}1$ | Eq.2", "worst\nmargin", "worst\n$R$"]
    y0 = 0.86
    for cx, h in zip(col_x, headers):
        axS.text(cx, y0, h, fontsize=6.2, fontweight="bold", va="center",
                 ha="left", transform=axS.transAxes, linespacing=1.2)
    rowcol = {"xpbd": "#D55E00", "avbd": "#E69F00", "impulse": "#0072B2"}
    for r, (sol, name) in enumerate(IMPLS):
        y = y0 - 0.22 - r * 0.17
        nR, nEq2, wM, wR = summ[sol]
        axS.text(col_x[0], y, name, fontsize=6.6, va="center", color=rowcol[sol],
                 fontweight="bold", transform=axS.transAxes)
        axS.text(col_x[1], y, f"{nR}/24 | {nEq2}/24", fontsize=6.4, va="center",
                 transform=axS.transAxes)
        mtxt = (_fmt_M(wM) + " J") if abs(wM) >= 0.1 else "$\\approx$0"
        axS.text(col_x[2], y, mtxt, fontsize=6.4, va="center",
                 transform=axS.transAxes)
        axS.text(col_x[3], y, _fmt_R(wR), fontsize=6.4, va="center",
                 transform=axS.transAxes)
    axS.text(0.02, 0.14,
             "Scale gap, not a ranking: the tested XPBD host overdraws by up to\n"
             "$4.4{\\times}10^{7}$ J, AVBD by at most $6.7$ J (3/24 cells), the\n"
             "implicit realization never. E1: the AVBD/implicit accounting floor\n"
             "is $\\leq 10^{-3}$ J, so $6.7$ J is real injection, not noise.",
             fontsize=6.0, va="top", transform=axS.transAxes,
             linespacing=1.35)

    # Colorbar for the R panel only (the margin panel uses a different
    # SymLog norm and is read from its text annotations; red = >0 = violates,
    # stated in its title).
    sm_r = plt.cm.ScalarMappable(cmap=CMAP, norm=NORM_R)
    cb = fig.colorbar(sm_r, ax=axR, fraction=0.045, pad=0.03,
                      ticks=[-1, 0, 1, 2, 3, 4, 5])
    cb.ax.set_yticklabels(["$10^{-1}$", "$1$", "$10$", "$10^{2}$", "$10^{3}$",
                           "$10^{4}$", "$10^{5}$"], fontsize=6)
    cb.ax.axhline(0.0, color="k", lw=0.8)
    cb.set_label("$R$", fontsize=7)

    p = save(fig, "fig_xpbd_map.pdf")
    return p


if __name__ == "__main__":
    main()
