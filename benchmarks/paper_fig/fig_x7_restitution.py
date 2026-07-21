#!/usr/bin/env python3
"""W5 restyle — X7 restitution: injected/lost energy ratio vs restitution.

Paper-DCR's forced IIR re-injects vibration energy the near-elastic contact no
longer dissipates: the ratio crosses 1 near eps_r~0.8 and plateaus at 2.6x
(energy created). The native bounded arm holds at 0.05 <= 1 for every eps_r.

Reads only the vendored committed CSV. Run:
  .venv/bin/python benchmarks/paper_fig/fig_x7_restitution.py
"""
from __future__ import annotations

import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import PALETTE, apply_style, save

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/x7_restitution.csv")


def main():
    apply_style()
    with open(CSV) as fh:
        rows = list(csv.DictReader(fh))
    er = [float(r["restitution"]) for r in rows]
    dcr = [float(r["dcr_ratio"]) for r in rows]
    nat = [float(r["native_ratio"]) for r in rows]

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    ax.axhspan(1.0, 3.0, color=PALETTE["clamp_off"], alpha=0.08)
    ax.axhline(1.0, color="0.35", lw=0.9, ls="--")
    ax.text(0.02, 1.05, r"passive bound $\Delta E_{\mathrm{m}}\leq\Delta E_{\mathrm{r}}$",
            fontsize=6.5, color="0.35", va="bottom")
    ax.plot(er, dcr, marker="o", color=PALETTE["dcr"], label="one-way (D, forced IIR)")
    ax.plot(er, nat, marker="s", color=PALETTE["native"], label="native (bounded)")
    ax.annotate(r"$2.63\times$ (energy created)", xy=(er[-1], dcr[-1]),
                xytext=(0.42, 2.35), fontsize=6.5, color=PALETTE["dcr"])
    ax.annotate(r"$0.05\leq1\ \forall\varepsilon_r$", xy=(er[-1], nat[-1]),
                xytext=(0.55, 0.28), fontsize=6.5, color=PALETTE["native"])
    ax.set_xlabel(r"coefficient of restitution $\varepsilon_r$")
    ax.set_ylabel("injected / lost energy per impact")
    ax.set_ylim(0, 2.9)
    ax.set_xlim(-0.02, 1.0)
    ax.legend(loc="center left", frameon=False)
    fig.tight_layout()
    save(fig, "fig_x7_restitution.pdf")


if __name__ == "__main__":
    main()
