#!/usr/bin/env python3
"""MIG short paper F3 — the symmetric three-solver adversarial budget matrix.

TWO metrics over the SAME 24 cells (scene x relax x budget), governor OFF:

  TOP ROW    R = peak modal energy / peak incident rigid KE
             A severity DIAGNOSTIC. It is what the paper has always reported
             and it is NOT the enforced invariant: the incident KE of one
             impactor is not the supply that Eq. (2) budgets against.

  BOTTOM ROW M = max_n [ E_mod^n - E_mod^0
                         - eta * sum_{k<=n} max(dE_rig^k, 0) ]      [joules]
             Eq. (2) ITSELF, evaluated un-governed, as the paper prints it.
             M <= 0 satisfies the invariant; M > 0 is an actual violation.
             (R1 / plan §6.3.)

The bottom row is in JOULES, not a ratio, and that is deliberate. A ratio needs
a denominator, and every available denominator misleads somewhere: dividing by
the supply accumulated SO FAR explodes in the opening substeps (a 0.13 J lead
became "U = 20"), while dividing by the run's TOTAL supply hides real
violations whose peak came early (AVBD violates in 23/24 cells with that ratio
below 1). The signed joule margin is the quantity the verdict is actually made
on, it needs no denominator, and it keeps the severity ordering visible:
XPBD overdraws by up to 4.4e7 J, AVBD by at most 15 J.

Reading the two rows together is the point. The panel's central criticism was
that the paper measured R and claimed Eq. (2). Where they agree (XPBD: 8/24
either way) the diagnostic was fine; where they diverge (AVBD: R flags 2 cells,
Eq. (2) is violated in 23) the diagnostic was the wrong instrument.

A symmetric-log colour scale is used for the margin so that both the 1e-3 J and
the 1e7 J ends stay legible on one axis.

The relaxation axis is INERT on the impulse backend by construction
(solver_impulse.py:290-292 -- the implicit modal weight needs no
under-relaxation); its two relax rows are bit-identical and are drawn hatched to
say so rather than implying an independent measurement.

Reads the R1 CSV, which carries BOTH metrics from the SAME instrumented run
(so the two rows cannot drift apart), and whose R column is asserted against
the frozen E-S1b clamp-OFF values by `--check-frozen`.

Run:
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
from matplotlib.colors import TwoSlopeNorm, SymLogNorm

from benchmarks.paper_fig.figstyle import apply_style, save

CSV = os.path.join(_ROOT,
                   "benchmarks/paper_eval/x1_passivity/out/eq2_utilization.csv")
SOLVERS = [("xpbd", "XPBD"), ("avbd", "AVBD"), ("impulse", "impulse")]
SCENES = ["shelf", "ledge", "dinner"]
SCENE_LABEL = {"shelf": "shelf", "ledge": "ledge", "dinner": "table"}
RELAXES = [0.7, 1.0]
BUDGETS = [(4, 1), (8, 2), (16, 4), (32, 8)]

CMAP = plt.get_cmap("RdBu_r")

# TOP: log10 of the ratio R, diverging at 0 (= R of 1).
NORM_R = TwoSlopeNorm(vmin=-1.2, vcenter=0.0, vmax=5.2)
CB_TICKS_R = [-1, 0, 1, 2, 3, 4, 5]
CB_LABELS_R = ["$10^{-1}$", "$10^{0}$", "$10^{1}$", "$10^{2}$",
               "$10^{3}$", "$10^{4}$", "$10^{5}$"]

# BOTTOM: the signed Eq.-(2) margin in joules, diverging at 0 (the invariant).
# Symmetric log: the data spans -4e2 J (comfortably satisfied) to +4e7 J
# (grossly violated), with AVBD's real violations living at 1e-2..1e1 J.
NORM_M = SymLogNorm(linthresh=1e-2, linscale=0.6,
                    vmin=-1e3, vmax=1e8, base=10)
CB_TICKS_M = [-1e2, -1e0, 0, 1e0, 1e2, 1e4, 1e6, 1e8]
CB_LABELS_M = ["$-10^{2}$", "$-10^{0}$", "$0$", "$10^{0}$", "$10^{2}$",
               "$10^{4}$", "$10^{6}$", "$10^{8}$"]


def _fmt(v):
    """Ratio formatter (top row): always positive, spans 1e-2..1e5."""
    if not np.isfinite(v):
        return "--"
    if v >= 1e4:
        return f"{v:.0e}".replace("e+0", "e").replace("e+", "e")
    if v >= 100:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def _fmt_margin(v):
    """Signed joule formatter (bottom row). Keeps the sign visible, since the
    sign IS the verdict, and compresses the huge XPBD values."""
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


def _grid(idx, key, field):
    M = np.full((len(SCENES) * len(RELAXES), len(BUDGETS)), np.nan)
    for i, scene in enumerate(SCENES):
        for j, rl in enumerate(RELAXES):
            for k, (it, su) in enumerate(BUDGETS):
                v = idx.get((key, scene, rl, it, su), {}).get(field)
                if v is not None:
                    M[i * len(RELAXES) + j, k] = v
    return M


def _panel(ax, M, label, show_hatch, kind="ratio"):
    if kind == "ratio":
        ax.imshow(np.log10(M), cmap=CMAP, norm=NORM_R, aspect="auto")
        fmt, hot = _fmt, (lambda v: v > 30 or v < 0.12)
    else:                                     # signed joule margin
        ax.imshow(M, cmap=CMAP, norm=NORM_M, aspect="auto")
        fmt, hot = _fmt_margin, (lambda v: v > 1e2 or v < -1e2)
    for a in range(M.shape[0]):
        for b in range(M.shape[1]):
            v = M[a, b]
            ax.text(b, a, fmt(v), ha="center", va="center", fontsize=5.6,
                    color="white" if (np.isfinite(v) and hot(v)) else "black")
    if show_hatch:                       # the inert relax axis (impulse only)
        for a in range(M.shape[0]):
            if a % 2 == 1:
                ax.add_patch(plt.Rectangle(
                    (-0.5, a - 0.5), M.shape[1], 1.0, fill=False,
                    hatch="///", edgecolor="0.45", linewidth=0.0, alpha=0.55))
    ax.set_title(label, fontsize=8, pad=3)
    ax.grid(False)


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))

    def _f(r, k):
        v = r.get(k, "")
        if v in ("", "None", None):
            return None
        try:
            return float(v)
        except ValueError:
            return None

    idx = {}
    for r in rows:
        key = (r["solver"], r["scene"], float(r["relax"]),
               int(r["iters"]), int(r["substeps"]))
        idx[key] = {"R": _f(r, "ratio_off"), "M": _f(r, "margin_J")}

    ylabels = [f"{SCENE_LABEL[s]}  {rl:g}" for s in SCENES for rl in RELAXES]
    xlabels = [f"{i}$\\times${s}" for (i, s) in BUDGETS]

    fig, axes = plt.subplots(2, 3, figsize=(7.0, 4.4), sharey=True,
                             sharex=True)
    for col, (key, label) in enumerate(SOLVERS):
        _panel(axes[0, col], _grid(idx, key, "R"), label, key == "impulse",
               kind="ratio")
        _panel(axes[1, col], _grid(idx, key, "M"), "", key == "impulse",
               kind="margin")

    for col in range(3):
        axes[1, col].set_xticks(range(len(xlabels)), xlabels, fontsize=6.5)
        axes[1, col].set_xlabel("iterations $\\times$ substeps", fontsize=7)
    for row in range(2):
        axes[row, 0].set_yticks(range(len(ylabels)), ylabels, fontsize=6.5)
        axes[row, 0].set_ylabel("scene, modal relaxation", fontsize=7)

    # row captions, on the right edge
    axes[0, 2].text(1.06, 0.5, "$R$  (diagnostic)", transform=axes[0, 2].transAxes,
                    rotation=270, va="center", ha="left", fontsize=7.5)
    axes[1, 2].text(1.06, 0.5, "Eq.~(2) margin [J]",
                    transform=axes[1, 2].transAxes,
                    rotation=270, va="center", ha="left", fontsize=7.5)

    sm_r = plt.cm.ScalarMappable(cmap=CMAP, norm=NORM_R)
    cb_r = fig.colorbar(sm_r, ax=axes[0, :], fraction=0.022, pad=0.055,
                        ticks=CB_TICKS_R)
    cb_r.ax.set_yticklabels(CB_LABELS_R, fontsize=6.5)
    cb_r.set_label("peak modal E / incident rigid KE", fontsize=6.5)
    cb_r.ax.axhline(0.0, color="k", lw=1.0)

    sm_m = plt.cm.ScalarMappable(cmap=CMAP, norm=NORM_M)
    cb_m = fig.colorbar(sm_m, ax=axes[1, :], fraction=0.022, pad=0.055,
                        ticks=CB_TICKS_M)
    cb_m.ax.set_yticklabels(CB_LABELS_M, fontsize=6.5)
    cb_m.set_label("Eq.-(2) margin [J]   ($>0$ violates)", fontsize=6.5)
    cb_m.ax.axhline(0.0, color="k", lw=1.0)

    save(fig, "fig_s1_solver_matrix.pdf")


if __name__ == "__main__":
    main()
