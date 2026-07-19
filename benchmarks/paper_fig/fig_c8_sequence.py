#!/usr/bin/env python3
"""MIG short paper F1 (teaser) — the deflected support surface, three arms.

Plan §7.9 / C8. The board's own deflection field, sampled at the 48 support
contact rows, at three timestamps through one impact at the frozen accuracy
cell (shelf, 8x2, relaxation 0.7 — the §6.7 / E-R5 cell):

    ungoverned   the un-governed position-based host
    governed     the same run with the cumulative storage bound enforced
    reference    the converged oracle (implicit realization, K=500)

This is the SAME quantity the contact row sees, d_i = U_y[i] . q [m], read
straight from the frozen traces written by run_governed_accuracy.py. NO new
solver run: the .npz is committed evidence and this script only draws it.

The horizontal axis is the world x of each support contact, so the curve is a
sampled profile of the deflected board under the six resting objects rather
than a schematic.

Run:
  .venv/bin/python benchmarks/paper_fig/fig_c8_sequence.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import apply_style, save, PALETTE

TRACES = os.path.join(
    _ROOT, "benchmarks/paper_eval/x1_passivity/out/governed_accuracy_traces.npz")

H = 1.0 / 120.0          # frame period; the traces are one row per frame
FRAMES = (28, 31, 60)    # approach, peak deflection, ring-down
ARMS = (("ungoverned", "un-governed", PALETTE["clamp_off"], "-"),
        ("governed", "governed", PALETTE["native"], "-"),
        ("oracle", "converged reference", "0.35", "--"))


def support_x():
    """World x of each support contact row, in the traces' column order.

    Built from the scene at rest. Deflections are sub-cm against a half-metre
    span, so the rest-pose corner position is the right abscissa; using the
    live pose would move the samples by less than the marker width.
    """
    from scenes.reduced_shelf import build_reduced_shelf
    world = build_reduced_shelf(device="cpu", iterations=8, avbd_substeps=2,
                                solver="xpbd").world
    sol = world._solver
    X = sol._X
    return np.array([X[sc.bi][0] + sc.off[0] for sc in sol._support])


def main():
    apply_style()
    z = np.load(TRACES)
    x = support_x()
    order = np.argsort(x)
    xs = x[order]

    fig, axes = plt.subplots(1, 3, figsize=(3.4, 1.35), sharey=True)
    for ax, f in zip(axes, FRAMES):
        for key, label, colour, style in ARMS:
            # plot SAG = -d, so downward deflection reads as a positive
            # excursion; d = U_y . q is negative when the board sags.
            d = -z[key][f][order] * 1e3          # m -> mm, sign flipped
            ax.plot(xs, d, style, color=colour, lw=1.2, label=label)
            ax.plot(xs, d, ".", color=colour, ms=2.0)
        ax.axhline(0.0, color="0.75", lw=0.6, zorder=0)
        ax.set_title(f"$t={f * H * 1e3:.0f}$ ms", pad=2, fontsize=6)
        ax.tick_params(labelsize=5.5)
        ax.set_xticks([-0.2, 0.0, 0.2])
    axes[0].set_ylabel("sag [mm]", fontsize=6)
    axes[1].set_xlabel("position along board [m]", fontsize=6)
    axes[0].legend(loc="upper left", frameon=False, handlelength=1.6,
                   borderaxespad=0.1, fontsize=5)
    fig.tight_layout(pad=0.2, w_pad=0.35)
    save(fig, "fig_c8_sequence.pdf")


if __name__ == "__main__":
    main()
