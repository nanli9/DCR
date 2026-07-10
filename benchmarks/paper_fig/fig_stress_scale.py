#!/usr/bin/env python3
"""Scale stress figure — N-body sweep on the device path, from committed CSVs.

Panel (a): ms/step vs body count N (16 -> 512) for three iteration budgets on
the device-resident co-solved path, with the 120 Hz real-time region and an
N^0.5 slope guide (the measured growth is sublinear: 32x bodies -> ~5.5x cost).
Panel (b): the two-way modal overhead (coupling - frozen-ring baseline) at the
paper budget vs N -- flat at ~0.1 ms: the fixed 28-mode block does not grow
with body count, so at scale the cost is the rigid contact solve.

Reads only committed CSVs. Run:
  .venv/bin/python benchmarks/paper_fig/fig_stress_scale.py
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


def main():
    apply_style()
    grid = _read(os.path.join(X5, "stress_device.csv"))
    arms = _read(os.path.join(X5, "stress_device_arms.csv"))

    fig, (axa, axb) = plt.subplots(
        1, 2, figsize=(7.0, 2.5), gridspec_kw=dict(width_ratios=[1.25, 1.0]))

    # ---- (a) ms/step vs N, per budget ------------------------------------- #
    style = {"8x1": (PALETTE["variant"], "^", "8×1 (real-time)"),
             "16x2": (PALETTE["dcr"], "s", "16×2"),
             "16x4": (PALETTE["native"], "o", "16×4 (paper)")}
    for b, (col, mk, lab) in style.items():
        rows = sorted((r for r in grid if r["budget"] == b),
                      key=lambda r: int(r["n_bodies"]))
        xs = np.array([int(r["n_bodies"]) for r in rows])
        ys = np.array([float(r["mean_ms"]) for r in rows])
        axa.plot(xs, ys, marker=mk, color=col, label=lab)
    # N^0.5 slope guide anchored under the 16x4 curve
    ns = np.array([16.0, 512.0])
    y0 = 6.2
    axa.plot(ns, y0 * np.sqrt(ns / ns[0]), color="0.45", lw=0.8, ls=":",
             zorder=1)
    axa.text(150, 24, r"$\propto N^{1/2}$", color="0.35", fontsize=6.5,
             rotation=18)
    axa.axhspan(0.5, RT_MS, color=PALETTE["rt"], alpha=0.12)
    axa.axhline(RT_MS, color=PALETTE["rt"], lw=0.9, ls="--")
    axa.text(17, RT_MS * 0.88, "120 Hz real-time", color=PALETTE["rt"],
             fontsize=6.5, va="top")
    axa.set_xscale("log", base=2)
    axa.set_yscale("log")
    axa.set_xticks([16, 32, 64, 128, 256, 512])
    axa.set_xticklabels(["16", "32", "64", "128", "256", "512"])
    axa.set_ylim(0.9, 70)
    axa.set_xlabel("movable bodies $N$ (one fixed 28-mode slab)")
    axa.set_ylabel("ms / step (RTX 4090)")
    axa.legend(loc="upper left", frameon=False)
    axa.set_title("(a)", loc="left", fontsize=8)

    # ---- (b) modal overhead vs N ------------------------------------------ #
    rows = sorted(arms, key=lambda r: int(r["n_bodies"]))
    xs = np.array([int(r["n_bodies"]) for r in rows])
    ov = np.array([float(r["modal_overhead_ms"]) for r in rows])
    base = np.array([float(r["baseline_ms"]) for r in rows])
    axb.axhline(0.0, color="0.45", lw=0.8)
    axb.plot(xs, ov, marker="o", color=PALETTE["native"],
             label="two-way modal overhead")
    axb.plot(xs, base, marker=".", ms=3, color="0.6", lw=0.9, ls="--",
             label="rigid baseline (ring frozen)")
    axb.set_xscale("log", base=2)
    axb.set_xticks([16, 32, 64, 128, 256, 512])
    axb.set_xticklabels(["16", "32", "64", "128", "256", "512"])
    axb.set_yscale("symlog", linthresh=1.0)
    axb.set_ylim(-0.6, 70)
    axb.set_xlabel("movable bodies $N$")
    axb.set_ylabel("ms / step @ 16×4")
    axb.legend(loc="upper left", frameon=False)
    axb.text(20, 0.32, r"$|\Delta|\leq 0.10$ ms at every $N$",
             color=PALETTE["native"], fontsize=6.5)
    axb.set_title("(b)", loc="left", fontsize=8)

    fig.tight_layout(w_pad=1.6)
    save(fig, "fig_stress_scale.pdf")

    # ---- single-column variant (panel (a) only) for the page-capped paper -- #
    fig2, ax = plt.subplots(figsize=(3.4, 2.35))
    for b, (col, mk, lab) in style.items():
        rows = sorted((r for r in grid if r["budget"] == b),
                      key=lambda r: int(r["n_bodies"]))
        xs = np.array([int(r["n_bodies"]) for r in rows])
        ys = np.array([float(r["mean_ms"]) for r in rows])
        ax.plot(xs, ys, marker=mk, color=col, label=lab)
    ax.plot(ns, y0 * np.sqrt(ns / ns[0]), color="0.45", lw=0.8, ls=":",
            zorder=1)
    ax.text(150, 25, r"$\propto N^{1/2}$", color="0.35", fontsize=6.5,
            rotation=20)
    ax.axhspan(0.5, RT_MS, color=PALETTE["rt"], alpha=0.12)
    ax.axhline(RT_MS, color=PALETTE["rt"], lw=0.9, ls="--")
    ax.text(17, RT_MS * 0.86, "120 Hz real-time", color=PALETTE["rt"],
            fontsize=6.5, va="top")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks([16, 32, 64, 128, 256, 512])
    ax.set_xticklabels(["16", "32", "64", "128", "256", "512"])
    ax.set_ylim(0.9, 70)
    ax.set_xlabel("movable bodies $N$ (one fixed 28-mode slab)")
    ax.set_ylabel("ms / step (RTX 4090)")
    ax.legend(loc="upper left", frameon=False)
    fig2.tight_layout()
    save(fig2, "fig_stress_scale_col.pdf")


if __name__ == "__main__":
    main()
