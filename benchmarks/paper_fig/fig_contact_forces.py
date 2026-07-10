#!/usr/bin/env python3
"""W5 restyle — contact-force ledger + two-way ring (the sheldon stack).

Panel (a) THE DISCRIMINATOR (visually first): the top cube's steady ring
amplitude |a| with the modal network ON (native fem-rigid / abd) vs OFF and
fully-rigid (identically zero) -- the two-way coupling is what makes a body two
box-box hops from the impact ring at all.
Panel (b): the static contact-force ledger -- each joint's measured normal load
vs the analytic stack-above * mg, balancing to < 1.9%.

Reads only the vendored committed JSON. Run:
  .venv/bin/python benchmarks/paper_fig/fig_contact_forces.py
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import PALETTE, apply_style, save

JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/contact_forces.json")


def main():
    apply_style()
    d = json.load(open(JSON))

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(7.0, 2.7))

    # ---- (a) two-way ring discriminator ---------------------------------- #
    # The abd variant is excluded from this panel: its affine coordinate is
    # not commensurable with a mass-normalized modal amplitude, and its
    # long-horizon buildup is unresolved (paper Fig. 1 caption + limitations).
    ring = d["ring_upper"]
    order = ["fem_rigid", "rigid", "off"]
    lab = {"fem_rigid": "native\n(fem-rigid)",
           "rigid": "rigid\ncargo", "off": "network\nOFF"}
    col = {"fem_rigid": PALETTE["native"],
           "rigid": "0.6", "off": "0.6"}
    vals = [ring[k] for k in order]
    floor = 1e-6
    heights = [max(v, floor) for v in vals]
    xs = np.arange(len(order))
    axa.bar(xs, heights, color=[col[k] for k in order], width=0.62,
            edgecolor="white", linewidth=0.5)
    for x, v in zip(xs, vals):
        axa.text(x, max(v, floor) * 1.3, ("$\\equiv0$" if v == 0 else f"{v:.1e}"),
                 ha="center", va="bottom", fontsize=6.2)
    axa.set_yscale("log")
    axa.set_ylim(floor, 2e-4)
    axa.set_xticks(xs)
    axa.set_xticklabels([lab[k] for k in order], fontsize=6.3)
    axa.set_ylabel(r"top-cube ring amplitude $|a|$")
    axa.set_title("(a)", loc="left", fontsize=8)

    # ---- (b) contact-force ledger ---------------------------------------- #
    ledger = d["ledger"]
    jorder = ["resting_support", "base_support", "base_mid_box", "mid_upper_box"]
    jlab = {"resting_support": "resting\n/ slab", "base_support": "base\n/ slab",
            "base_mid_box": "mid\n/ base", "mid_upper_box": "upper\n/ mid"}
    meas = [ledger[j]["measured"] for j in jorder]
    exp = [ledger[j]["expect"] for j in jorder]
    err = [ledger[j]["err_pct"] for j in jorder]
    xs = np.arange(len(jorder))
    w = 0.36
    axb.bar(xs - w/2, exp, width=w, color="0.7", label=r"analytic $(\Sigma\,{\rm above})\,mg$")
    axb.bar(xs + w/2, meas, width=w, color=PALETTE["native"], label="measured")
    for x, m, e in zip(xs, meas, err):
        axb.text(x + w/2, m + 0.3, f"{e:.1f}%", ha="center", va="bottom", fontsize=6.2,
                 color="0.35")
    axb.set_xticks(xs)
    axb.set_xticklabels([jlab[j] for j in jorder], fontsize=6.3)
    axb.set_ylabel(r"joint normal load  [N]")
    axb.legend(loc="upper right", frameon=False)
    axb.set_ylim(0, max(meas) * 1.28)
    axb.set_title("(b)", loc="left", fontsize=8)

    fig.tight_layout(w_pad=1.5)
    save(fig, "fig_contact_forces.pdf")


if __name__ == "__main__":
    main()
