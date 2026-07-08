"""W5 figure-pass shared style: colorblind-safe arm palette + print rcParams.

Every paper figure imports PALETTE and apply_style() so the arm colors are
constant across ALL figures and the fonts embed at >=7 pt print size. Vector PDF
output only (savefig .pdf). No in-image titles (the caption carries it).
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Okabe-Ito colorblind-safe. W5 arm assignments (held constant everywhere):
PALETTE = dict(
    native="#0072B2",     # blue  — the native modal solver
    gt="#000000",         # black (dashed) — full-FEM ground truth
    dcr="#E69F00",        # orange — paper-DCR one-way
    clamp_off="#D55E00",  # vermillion — clamp OFF / injecting
    variant="#009E73",    # bluish-green (teal) — a variant arm (Schur, all-cargo)
    rt="#009E73",         # real-time region accent
    grid="#BBBBBB",
)
GT_DASH = (0, (5, 2))

# where generated PDFs land (also copied into paper/figures/ by the caller)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def apply_style():
    plt.rcParams.update({
        "pdf.fonttype": 42,          # embed TrueType (no Type-3), reviewer-safe
        "ps.fonttype": 42,
        "font.family": "sans-serif",
        "font.size": 8,              # >= 7 pt at print size
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.6,
        "lines.linewidth": 1.4,
        "lines.markersize": 4,
        "axes.grid": True,
        "grid.color": PALETTE["grid"],
        "grid.linewidth": 0.4,
        "grid.alpha": 0.6,
        "axes.axisbelow": True,
        "figure.dpi": 200,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"wrote {path}")
    return path
