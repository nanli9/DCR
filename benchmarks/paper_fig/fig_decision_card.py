#!/usr/bin/env python3
"""MIG short paper — the DECISION CARD, promoted from the supplementary video.

Every reviewer who watched the video called its closing decision card the
clearest statement of the paper's contribution anywhere in the submission, and
noted it existed ONLY in the supplement. This script renders that card as a
column-width vector figure so it lands in the paper (near the Conclusion).

Faithful to the video's beat 8 (frame f_24): three ordered branches keyed to
what the practitioner CAN change, each with the one number that supports it, and
the closing line that the guardrail is a safety net, not the product. Numbers
are the paper's own (Fig. 2, Fig. 3, Table 1, Prop. 4.1).

Vector PDF, house style (figstyle). No data axes — a laid-out flowchart.
Run: .venv/bin/python benchmarks/paper_fig/fig_decision_card.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

from benchmarks.paper_fig.figstyle import apply_style, save, PALETTE

# Branch accent colours reuse the house palette (video uses green/grey/orange).
C_GREEN = PALETTE["variant"]     # #009E73 — the clean control (implicit)
C_GREY = "#8A8A8A"               # the "stuck with it" middle road
C_ORANGE = PALETTE["dcr"]        # #E69F00 — the last-resort guardrail
INK = "#111111"
SUB = "#555555"

# Each branch: (number, accent, question, recommendation-lines[], stat-lines[]).
# Lines are pre-wrapped to the card width so layout is explicit (no auto-wrap).
BRANCHES = [
    (1, C_GREEN,
     "Can you change the contact row?",
     ["Make its modal weight stiffness-aware:",
      "implicit $(M{+}hD{+}h^2K)^{-1}$, not $1/M$."],
     ["within-host control: $8/24\\!\\to\\!0/24$ overdraws, no host swap"]),
    (2, C_GREY,
     "Stuck with the XPBD shared row?",
     ["Audit it: prefer iterations over substeps;",
      "band-limit the basis."],
     ["$32{\\times}1$ holds ($R\\!=\\!0.30$); $4{\\times}8$ overdraws ($+481$ J);",
      "band-limiting still leaves 6/8 cells over"]),
    (3, C_ORANGE,
     "Need a hard energy guarantee?",
     ["The cumulative storage bound contains",
      "modal energy — last resort."],
     ["holds in 90/90 cells, but still leaves up to 17.8 mm",
      "penetration + a worse trajectory. Containment, not a fix."]),
]


def build():
    apply_style()
    # Compact aspect (wider than tall) so the column float stays short: the same
    # readable text, less vertical whitespace.
    fig = plt.figure(figsize=(3.42, 3.14))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ---- title + subtitle ------------------------------------------------
    ax.text(0.5, 0.982, "Adding modal DOFs to a fixed-budget XPBD host?",
            ha="center", va="top", fontsize=9.0, fontweight="bold", color=INK)
    ax.text(0.5, 0.935,
            "a diagnostic + operating guide — not a solver ranking, "
            "not a governor method",
            ha="center", va="top", fontsize=6.2, style="italic", color=SUB)

    # ---- three branch cards ---------------------------------------------
    top = 0.885         # top of first card
    card_h = 0.238      # card height (holds question + 2 rec + 2 stat lines)
    gap = 0.017         # gap between cards
    x0, x1 = 0.035, 0.965
    tx = x0 + 0.120     # text left margin (clears the number disc)
    for i, (num, accent, q, rec_lines, stats) in enumerate(BRANCHES):
        yt = top - i * (card_h + gap)
        yb = yt - card_h
        # card panel
        ax.add_patch(FancyBboxPatch(
            (x0, yb), x1 - x0, card_h,
            boxstyle="round,pad=0.006,rounding_size=0.016",
            linewidth=0.8, edgecolor=accent, facecolor=accent + "14",
            mutation_aspect=0.62, zorder=1))
        # number disc
        cx, cy = x0 + 0.058, yt - 0.050
        ax.add_patch(Circle((cx, cy), 0.032, color=accent, zorder=3))
        ax.text(cx, cy, str(num), ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="white", zorder=4)
        # running vertical cursor down the card
        cur = yt - 0.028
        ax.text(tx, cur, q, ha="left", va="top",
                fontsize=8.0, fontweight="bold", color=INK, zorder=3)
        cur -= 0.062
        for rl in rec_lines:                      # recommendation
            ax.text(tx, cur, rl, ha="left", va="top",
                    fontsize=7.2, color=INK, zorder=3)
            cur -= 0.039
        cur -= 0.010
        for s in stats:                           # supporting numbers (grey)
            ax.text(tx, cur, s, ha="left", va="top",
                    fontsize=6.3, color=SUB, zorder=3)
            cur -= 0.036

    # ---- footer ----------------------------------------------------------
    ax.add_patch(FancyBboxPatch(
        (x0, 0.008), x1 - x0, 0.056,
        boxstyle="round,pad=0.004,rounding_size=0.010",
        linewidth=0, facecolor="#EDEDED", zorder=1))
    ax.text(0.5, 0.036, "The governor is a safety net, not the product.",
            ha="center", va="center", fontsize=8.2, fontweight="bold",
            color=INK, zorder=3)

    return save(fig, "fig_decision_card.pdf")


if __name__ == "__main__":
    build()
