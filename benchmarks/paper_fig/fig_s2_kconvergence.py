#!/usr/bin/env python3
"""MIG short paper F2 — injection vs local iteration budget, with the oracle.

Deterministic shelf drop, substeps pinned at 1 so the iteration budget K is the
only variable, clamp OFF. The horizontal line is the converged reference:
the implicit sequential-impulse backend at K = 500, ratio 0.2735 -- the SAME
code path as its own sweep points, run to convergence, so it is a converged
reference of the same model rather than a different model.

XPBD is monotone non-increasing in K and decays toward the oracle across six
orders of magnitude (2.96e4 at K=1 to 0.300 at K=32), crossing the injection
threshold between K=16 and K=24. The impulse backend is already converged at
K=2 (spread 4.9e-4 over K=2..500).

The AVBD curve is drawn but must NOT be read as a convergence trend: its
denominator (peak incident impactor KE) is itself budget-dependent at low K
(13.0 J at K=1 rising to 28.2 J at K=32), unlike XPBD (27.45 J for K>=2) and
impulse (28.95 J). It is shown for completeness of the three-formulation
comparison only.

Reads the committed E-S2 CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_s2_kconvergence.py
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

CSV = os.path.join(_ROOT, "benchmarks/paper_eval/x1_passivity/out/k_convergence.csv")

STYLE = {
    "xpbd":    dict(color=PALETTE["clamp_off"], marker="o", label="XPBD"),
    "avbd":    dict(color=PALETTE["native"],    marker="s", label="AVBD"),
    "impulse": dict(color=PALETTE["variant"],   marker="^", label="impulse"),
}


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))

    oracle = next(float(r["ratio"]) for r in rows if r["is_oracle"] == "True")

    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    for key in ("xpbd", "avbd", "impulse"):
        pts = sorted(((int(r["K"]), float(r["ratio"])) for r in rows
                      if r["solver"] == key and r["is_oracle"] != "True"),
                     key=lambda p: p[0])
        ax.plot([p[0] for p in pts], [p[1] for p in pts], **STYLE[key])

    ax.axhline(oracle, ls=(0, (5, 2)), c="k", lw=1.0, zorder=1,
               label=f"converged ref.\n(impulse $K$=500): {oracle:.3f}")
    ax.axhline(1.0, ls=":", c="0.45", lw=0.9, zorder=1)
    ax.text(1.05, 1.35, "injection threshold", fontsize=6, color="0.35")

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks([1, 2, 4, 8, 16, 32, 64],
                  ["1", "2", "4", "8", "16", "32", "64"])
    ax.set_xlabel("local iteration budget $K$   (substeps $=1$)")
    ax.set_ylabel("peak modal energy / incident rigid KE")
    ax.legend(frameon=False, loc="upper right", fontsize=6.5)
    save(fig, "fig_s2_kconvergence.pdf")


if __name__ == "__main__":
    main()
