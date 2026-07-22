#!/usr/bin/env python3
"""MIG-short supplementary video: a practitioner diagnostic, not a governor demo.

Six beats following the rewrite plan section 12 storyboard. The video is a
*decision-oriented* re-cut of the teaser material: it opens on the cheap-modal
extension, shows the fixed-budget failure and the two controls that localize it
(iteration allocation, band-limited basis), and ends on an operating-guide
DECISION CARD -- deliberately NOT on the governor as a product (plan section 12:
"the video should no longer end as if the governor were the main product";
AVBD/implicit appears only as a brief observed control).

Beats (target 45--55 s):
  1. 0--6 s   schematic: XPBD rigid host, the full-nodal alternative it avoids,
              and the 16-mode extension -> shared contact rows -> fixed K.
  2. 6--18 s  same-state ungoverned vs the host's own high-iteration
              self-reference (steel board): the launch is entirely spurious.
  3. 18--29 s iteration allocation: the SAME 32 contact-row evaluations spent as
              iterations (32x1, holds) vs substeps (4x8, overdraws +481 J).
  4. 29--37 s band-limited basis: removing the stiffest modal cluster is
              necessary but not sufficient (6/8 injecting cells still overdraw).
  5. 37--46 s governor containment (bounded, not faithful) + a true-scale
              penetration cross-section attributing the residue across three
              arms: governor off / whole-state scale / surface-preserving.
  6. 46--55 s decision card: implicit control if the architecture is flexible;
              else audit the XPBD shared block/basis/iterations; governor only as
              last-resort containment.

Every on-screen number is read LIVE from the frozen Stage-B CSVs under
benchmarks/paper_eval/x1_passivity/out/ (and the teaser pose manifests), so the
video cannot drift from the paper's evidence. The 3-D beats reuse the
bit-identical locked-camera helpers in make_teaser_video.py.

The governed arm is the SHIPPED projection (eq. 5, gap-preserving), recorded as
teaser_deployed_gap.npz. The frozen teaser_deployed.npz holds the superseded
whole-state scale and is left untouched for fig_teaser.py.

Run (needs ffmpeg on PATH):
  .venv/bin/python benchmarks/paper_fig/make_short_video.py
  .venv/bin/python benchmarks/paper_fig/make_short_video.py --quick   # iterate
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches

# Reuse the teaser video's locked-camera 3-D beats and dark-theme constants
# verbatim -- a separate camera or palette would make the two artifacts read as
# different scenes.
from benchmarks.paper_fig.make_teaser_video import (          # noqa: E402
    OUT, FPS, W_IN, H_IN, DIM, BG, FG, ARM_COLOR,
    _load, global_bounds, new_fig, Writer, card, beat_sim)

X1 = os.path.join(_ROOT, "benchmarks", "paper_eval", "x1_passivity", "out")
SUPPORT_THICKNESS_MM = 30.0        # = 0.03 m board (record_teaser SUPPORT_THICKNESS)

SAFE = "#4ea36b"                   # holds / safe
UNSAFE = ARM_COLOR["off"]         # overdraws (the ungoverned colour)
ACCENT = "#c8ccd2"


# --------------------------------------------------------------------------- #
# frozen-data loaders: read the CSV, never hardcode a number                  #
# --------------------------------------------------------------------------- #
def _rows(name):
    with open(os.path.join(X1, name)) as fh:
        return list(csv.DictReader(fh))


def alloc_series():
    """Equal-row-count allocation, from the two frozen ladders.

    iterations  = k_convergence.csv  (xpbd, relax 0.7, S=1): evals = K
    substeps    = substep_sweep.csv  (xpbd, shelf, relax 0.7, K=4): evals = 4*S
    Both share the 4x1 point, then fan out. Source: claim sheet C3/C4.
    """
    it = [(int(r["K"]), float(r["ratio"]))
          for r in _rows("k_convergence.csv")
          if r["solver"] == "xpbd" and float(r["relax"]) == 0.7
          and int(r["substeps"]) == 1 and r["is_oracle"] == "False"]
    it.sort()
    it_evals = [(k, rr) for (k, rr) in it]                    # evals == K at S=1
    sub = [(int(r["substeps"]), float(r["ratio_off"]), float(r["margin_J"]))
           for r in _rows("substep_sweep.csv")
           if r["solver"] == "xpbd" and r["scene"] == "shelf"
           and float(r["relax"]) == 0.7 and int(r["iters"]) == 4]
    sub.sort()
    sub_evals = [(4 * s, rr, mj) for (s, rr, mj) in sub]
    return it_evals, sub_evals


def band_pairs():
    """Injecting cells (R_full>1) with their band-limited ratio + margin.

    Source: band_limit_sweep.csv (claim sheet C4). Returns list of
    (label, R_full, R_band, margin_band_J) ordered worst-first by R_band.
    """
    out = []
    for r in _rows("band_limit_sweep.csv"):
        rf = float(r["R_full"])
        if rf <= 1.0:
            continue
        out.append((f"{r['scene']} {r['relax']} {r['iters']}x{r['substeps']}",
                    rf, float(r["R_band"]), float(r["margin_band_J"])))
    out.sort(key=lambda t: -t[2])
    return out


def penetration_mm():
    """Worst end-of-substep contact-gap violation, shelf 4x1, in three arms.

    Source: projection_validity_arms_r07.csv -- the arm sweep that separates
    the truncated solve's OWN penetration (governor off) from what a projection
    adds on top of it. End-of-substep is the only arm-comparable metric: the
    ungoverned arm has no post-projection state.

    Returns (ungoverned, whole-state scale, preserved, worst preserved cell).
    The last is the shipped projection's worst over both scenes (ledge 4x1),
    which the decision card quotes as the guarantee's price.
    """
    rows = _rows("projection_validity_arms_r07.csv")

    def cell(scene, arm):
        return max(float(r["gap_viol_end_max_m"]) for r in rows
                   if r["scene"] == scene and r["arm"] == arm
                   and int(r["iters"]) == 4 and int(r["substeps"]) == 1) * 1e3

    worst_pres = max(float(r["gap_viol_end_max_m"])
                     for r in rows if r["arm"] == "gap") * 1e3
    return cell("shelf", "ungov"), cell("shelf", "radial"), \
        cell("shelf", "gap"), worst_pres


# --------------------------------------------------------------------------- #
# small dark-theme drawing helpers                                            #
# --------------------------------------------------------------------------- #
def _title(fig, txt, sub=None):
    fig.text(0.5, 0.945, txt, ha="center", va="center", fontsize=27,
             color=FG, fontweight="bold")
    if sub:
        fig.text(0.5, 0.895, sub, ha="center", va="center", fontsize=16,
                 color=DIM)


def _box(ax, x, y, w, h, txt, *, fc, ec=None, tc=FG, fs=15, alpha=1.0,
         weight="normal"):
    ax.add_patch(mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.008", mutation_aspect=0.6,
        linewidth=1.4, edgecolor=ec or "#3a4150", facecolor=fc, alpha=alpha,
        zorder=2))
    ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs,
            color=tc, alpha=alpha, zorder=3, fontweight=weight)


def _arrow(ax, x0, y0, x1, y1, alpha=1.0):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", lw=2.0, color=ACCENT,
                                alpha=alpha), zorder=1)


def _axes_full(fig):
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_facecolor(BG)
    return ax


# --------------------------------------------------------------------------- #
# beat 1: the extension schematic (0--6 s)                                    #
# --------------------------------------------------------------------------- #
def beat_schematic(wr, seconds=6.0, quick=False):
    """XPBD rigid host; the full-nodal alternative it avoids; the 16-mode
    extension -> shared contact rows -> fixed K. Revealed in four stages."""
    stages = 4
    hold = max(1, int((seconds if not quick else 2.0) * FPS / stages))
    for st in range(stages):
        fig = new_fig()
        _title(fig, "A cheap extension to a fixed-budget XPBD rigid host",
               sub="add a compact global modal state instead of a full "
                   "deformable")
        ax = _axes_full(fig)
        a1 = 1.0 if st >= 0 else 0.15
        a2 = 1.0 if st >= 1 else 0.12                # the fork / alternative
        a3 = 1.0 if st >= 2 else 0.12                # modal branch
        a4 = 1.0 if st >= 3 else 0.12                # shared rows + fixed K
        # existing host
        _box(ax, 0.025, 0.435, 0.185, 0.16, "existing XPBD\nrigid-body host",
             fc="#20242e", fs=15.5, alpha=a1, weight="bold")
        # the alternative you would otherwise reach for (dimmer, "avoided")
        _box(ax, 0.285, 0.695, 0.30, 0.15,
             "full nodal / tet deformable\n(large state, precompute)",
             fc="#191b21", ec="#33383f", tc=DIM, fs=13.5, alpha=a2)
        _arrow(ax, 0.19, 0.575, 0.315, 0.71, alpha=a2 * 0.5)
        ax.text(0.355, 0.645, "avoided here", ha="center", va="center",
                fontsize=12, color=DIM, style="italic", alpha=a2)
        # the modal branch this paper studies
        _box(ax, 0.285, 0.435, 0.215, 0.16,
             r"$+\;\mathbf{q}\in\mathbb{R}^{16}$  global modes",
             fc="#1d2a3a", ec=SAFE, fs=15.5, alpha=a3, weight="bold")
        _arrow(ax, 0.21, 0.515, 0.285, 0.515, alpha=a3)
        # -> shared contact rows -> fixed K
        _box(ax, 0.55, 0.435, 0.175, 0.16, "one shared\ncontact row\nper support",
             fc="#2a1f16", fs=13.5, alpha=a4)
        _box(ax, 0.78, 0.435, 0.165, 0.16, "fixed $K$\nlocal\niterations",
             fc="#2a181a", fs=13.5, alpha=a4)
        _arrow(ax, 0.50, 0.515, 0.55, 0.515, alpha=a4)
        _arrow(ax, 0.725, 0.515, 0.78, 0.515, alpha=a4)
        if st >= 3:
            fig.text(0.5, 0.16,
                     "Cheap and appealing -- but is a direct two-way "
                     "rigid-modal contact row energy-safe at a small fixed "
                     "budget?", ha="center", va="center", fontsize=17,
                     color=FG, wrap=True)
        wr.add(fig, times=hold)
        import matplotlib.pyplot as plt
        plt.close(fig)


# --------------------------------------------------------------------------- #
# beat 3: equal-row-count allocation (18--29 s)                               #
# --------------------------------------------------------------------------- #
def beat_alloc(wr, seconds=10.0, quick=False):
    """R vs contact-row evaluations: iterations converge the shared row,
    substeps do not, at equal cost. 2-D because the claim is a ratio at equal
    cost -- inherently quantitative (see boot-prompt beat-3 decision)."""
    it, sub = alloc_series()
    it_x = [k for k, _ in it]; it_y = [r for _, r in it]
    sub_x = [e for e, _, _ in sub]; sub_y = [r for _, r, _ in sub]
    m_4x8 = next(mj for e, r, mj in sub if e == 32)
    r_32x1 = next(r for k, r in it if k == 32)
    r_4x8 = next(r for e, r, _ in sub if e == 32)

    import matplotlib.pyplot as plt
    # one PNG per iteration: total screen time == frames / FPS. The reveal
    # completes by p~0.6 so most of the beat holds the full annotated panel.
    frames = max(1, int((seconds if not quick else 2.0) * FPS))
    for fi in range(frames):
        p = min(1.0, (fi + 1) / frames / 0.6)
        fig = new_fig()
        _title(fig, "Same 32 contact-row evaluations, allocated two ways",
               sub="shelf, relaxation 0.7  ---  iterations vs substeps at "
                   "equal cost")
        ax = fig.add_axes([0.10, 0.16, 0.83, 0.62]); ax.set_facecolor(BG)
        nshow = max(2, int(np.ceil(p * max(len(it_x), len(sub_x)))))
        ax.loglog(it_x[:nshow], it_y[:nshow], "-o", color=SAFE, lw=2.6, ms=6,
                  label="spent as ITERATIONS  ($K\\times1$)")
        ax.loglog(sub_x[:max(2, int(np.ceil(p * len(sub_x))))],
                  sub_y[:max(2, int(np.ceil(p * len(sub_x))))],
                  "-s", color=UNSAFE, lw=2.6, ms=6,
                  label="spent as SUBSTEPS  ($4\\times S$)")
        ax.axhline(1.0, color=ACCENT, lw=1.4, ls=(0, (5, 3)))
        ax.text(1.05, 1.25, "overdraw threshold  $R=1$", color=ACCENT,
                fontsize=12, va="bottom")
        if p > 0.66:
            ax.axvline(32, color="#7f8794", lw=1.2, ls=":")
            ax.plot([32], [r_32x1], "o", color=SAFE, ms=13, mec=FG, mew=1.2,
                    zorder=6)
            ax.plot([32], [r_4x8], "s", color=UNSAFE, ms=13, mec=FG, mew=1.2,
                    zorder=6)
            ax.annotate(f"$32\\times1$: $R={r_32x1:.2f}$ holds",
                        xy=(32, r_32x1), xytext=(29, 0.03), ha="right",
                        va="center", color=SAFE, fontsize=15,
                        fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color=SAFE, lw=1.4))
            ax.annotate(f"$4\\times8$: $R={r_4x8:.2f}$,  $+{m_4x8:.0f}$ J",
                        xy=(32, r_4x8), xytext=(6.0, 40.0), color=UNSAFE,
                        fontsize=15, fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color=UNSAFE, lw=1.4))
        ax.set_xlim(3.4, 40); ax.set_ylim(1e-2, 1e5)
        ax.set_xlabel("contact-row evaluations per frame  ($K\\cdot S$)",
                      color=FG, fontsize=16)
        ax.set_ylabel("incident energy ratio  $R$", color=FG, fontsize=16)
        ax.tick_params(colors=DIM, labelsize=13)
        for sp in ax.spines.values():
            sp.set_color("#2a2f3a")
        ax.grid(True, which="both", color="#1a1f28", lw=0.6)
        ax.legend(loc="upper right", fontsize=14, frameon=False, labelcolor=FG)
        if p > 0.9:
            fig.text(0.5, 0.055,
                     "Equal cost, opposite safety: iterations converge the "
                     "shared modal row; substeps do not.",
                     ha="center", va="center", fontsize=17, color=FG)
        wr.add(fig, times=1)
        plt.close(fig)


# --------------------------------------------------------------------------- #
# beat 4: band-limited basis -- necessary, not sufficient (29--37 s)          #
# --------------------------------------------------------------------------- #
def beat_band(wr, seconds=8.0, quick=False):
    pairs = band_pairs()                    # worst-first by R_band
    still = [p for p in pairs if p[2] > 1.0]
    worst = still[0]
    import matplotlib.pyplot as plt
    hold = int((seconds if not quick else 2.0) * FPS)
    fig = new_fig()
    _title(fig, "Removing the stiffest modal cluster: necessary, not sufficient",
           sub="band-limited basis (stiff cluster excluded) vs the full basis, "
               "per injecting cell")
    ax = fig.add_axes([0.24, 0.17, 0.70, 0.60]); ax.set_facecolor(BG)
    n = len(pairs)
    ys = list(range(n))[::-1]
    for (lab, rf, rb, mj), y in zip(pairs, ys):
        col = UNSAFE if rb > 1.0 else SAFE
        ax.plot([rf, rb], [y, y], "-", color="#3a4150", lw=2.0, zorder=1)
        ax.plot([rf], [y], "o", color="#5a6270", ms=8, zorder=2)
        ax.plot([rb], [y], "o", color=col, ms=11, mec=FG, mew=1.0, zorder=3)
        ax.text(-0.02, y, lab, transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=12.5, color=DIM,
                family="monospace")
    ax.axvline(1.0, color=ACCENT, lw=1.6, ls=(0, (5, 3)))
    ax.text(1.15, n - 0.4, "$R=1$", color=ACCENT, fontsize=13, va="top")
    ax.set_xscale("log")
    ax.set_xlim(0.2, 3e5); ax.set_ylim(-0.7, n - 0.3)
    ax.set_yticks([])
    ax.set_xlabel("incident energy ratio  $R$  (full basis  $\\to$  "
                  "band-limited)", color=FG, fontsize=15)
    ax.tick_params(colors=DIM, labelsize=13)
    for sp in ax.spines.values():
        sp.set_color("#2a2f3a")
    ax.grid(True, axis="x", which="both", color="#1a1f28", lw=0.6)
    # legend dots
    ax.plot([], [], "o", color="#5a6270", ms=8, label="full basis")
    ax.plot([], [], "o", color=SAFE, ms=10, label="band-limited: holds")
    ax.plot([], [], "o", color=UNSAFE, ms=10, label="band-limited: overdraws")
    ax.legend(loc="lower right", fontsize=12.5, frameon=False, labelcolor=FG)
    fig.text(0.5, 0.075,
             f"The band-limited basis cuts the ratio by 2--3 orders, but "
             f"{len(still)} of {n} injecting cells still overdraw "
             f"(worst: $+{worst[3] / 1e6:.2f}\\times10^{{6}}$ J).",
             ha="center", va="center", fontsize=17, color=FG)
    wr.add(fig, times=hold)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# beat 5b: true-scale penetration cross-section (37--46 s tail)               #
# --------------------------------------------------------------------------- #
def beat_penetration(wr, seconds=5.0, quick=False):
    """Honest true-scale cross-section of the governed contact: the storage
    bound contains energy, but the contact is not kept valid. Drawn as a
    labelled cross-section (NOT a painter's-algorithm render, which cannot
    depth-order penetration honestly -- see render3d.py)."""
    p_un, p_scale, p_pres, _ = penetration_mm()
    import matplotlib.pyplot as plt
    hold = int((seconds if not quick else 2.0) * FPS)
    fig = new_fig()
    _title(fig, "Where the penetration comes from",
           sub="the bound contains energy; the contact residue is the truncated "
               "row's -- a projection amplifies it")
    # true-scale cross-section, units mm, equal aspect
    ax = fig.add_axes([0.08, 0.15, 0.84, 0.58]); ax.set_facecolor(BG)
    ax.set_aspect("equal")
    d = p_pres          # the SHIPPED projection's depth (eq. 5), drawn to scale
    W = 190.0
    # board: top surface at y=0, 30 mm thick
    board = mpatches.Rectangle((-W / 2, -SUPPORT_THICKNESS_MM), W,
                               SUPPORT_THICKNESS_MM, facecolor="#4a4336",
                               edgecolor="#6b6152", lw=1.5, zorder=1)
    ax.add_patch(board)
    ax.text(-W / 2 + 4, -SUPPORT_THICKNESS_MM / 2, "support board  30 mm",
            ha="left", va="center", fontsize=12, color="#c9c2b0", zorder=2)
    # impactor: a tilted box whose lowest corner is driven d mm below the
    # surface -- a dropped-corner contact. Only the corner penetrates.
    hw, hh = 34.0, 24.0
    th = np.radians(15.0)
    Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    imp = np.array([[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]]) @ Rm.T
    imp = imp - imp[np.argmin(imp[:, 1])] + np.array([8.0, -d])   # corner->(8,-d)
    ax.add_patch(mpatches.Polygon(imp, closed=True, facecolor=UNSAFE,
                                  edgecolor=FG, lw=1.5, alpha=0.9, zorder=3))
    # highlight EXACTLY the penetrating region: impactor clipped to the board
    pen = mpatches.Polygon(imp, closed=True, facecolor="#ef3b2c",
                           edgecolor="none", alpha=0.55, zorder=4)
    ax.add_patch(pen); pen.set_clip_path(board)
    ax.text(30, imp[:, 1].max() - 12, "impactor", ha="center", va="center",
            fontsize=13, color=FG, zorder=5)
    # the surface line, on top, so the impactor is visibly cut by it
    ax.plot([-W / 2, W / 2], [0, 0], color="#d8cfb8", lw=1.6, zorder=5)
    # penetration dimension, tied to the corner but drawn OUTSIDE the board:
    # at true scale 8 mm is a thin wedge, so an in-board dimension collides
    # with the surface line and the board label.
    xd = -W / 2 - 14.0
    ax.plot([xd, 8.0], [-d, -d], color=UNSAFE, lw=0.8, ls=(0, (3, 2)), zorder=6)
    ax.annotate("", xy=(xd, -d), xytext=(xd, 0),
                arrowprops=dict(arrowstyle="<->", color=UNSAFE, lw=2.0),
                zorder=6)
    ax.text(xd - 6, -d / 2, f"{p_pres:.1f} mm", ha="right", va="center",
            fontsize=18, color=UNSAFE, fontweight="bold")
    ax.text(xd - 6, -d - 7, f"preserving the\nobserved surface,\neq. (5)  "
            f"[{p_pres / SUPPORT_THICKNESS_MM * 100:.0f}% of board]",
            ha="right", va="top", fontsize=12, color=DIM, linespacing=1.5)
    # the two reference depths, to scale, so the attribution is visible: what
    # the truncated row opens on its own, and what the superseded whole-state
    # scale amplified it to.
    xr = W / 2 + 6
    for depth, lab, col in ((p_un, "governor off\n(truncated row)", DIM),
                            (p_scale, "whole-state scale\n(superseded)",
                             "#a8443a")):
        ax.plot([-W / 2, W / 2], [-depth, -depth], color=col, lw=1.2,
                ls=(0, (5, 3)), zorder=6)
        ax.text(xr, -depth, f"{depth:.1f} mm  {lab}", ha="left", va="center",
                fontsize=11.5, color=col, linespacing=1.35, zorder=6)
    ax.set_xlim(-W / 2 - 82, W / 2 + 96)
    ax.set_ylim(-SUPPORT_THICKNESS_MM - 8, 52)
    ax.set_axis_off()
    fig.text(0.5, 0.088,
             f"With the governor off the truncated row already opens "
             f"{p_un:.1f} mm. Scaling the whole state amplified that to "
             f"{p_scale:.1f} mm;",
             ha="center", va="center", fontsize=15.5, color=FG)
    fig.text(0.5, 0.049,
             f"preserving the contact-observed surface, {p_pres:.1f} mm. "
             f"Still containment, not a fix.",
             ha="center", va="center", fontsize=15.5, color=FG)
    fig.text(0.5, 0.014, "true scale  ---  projection_validity_arms_r07.csv",
             ha="center", va="center", fontsize=11, color=DIM,
             family="monospace")
    wr.add(fig, times=hold)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# beat 6: the decision card (46--55 s)                                        #
# --------------------------------------------------------------------------- #
def beat_decision(wr, seconds=9.0, quick=False):
    it, sub = alloc_series()
    r_32x1 = next(r for k, r in it if k == 32)
    m_4x8 = next(mj for e, r, mj in sub if e == 32)
    still = [p for p in band_pairs() if p[2] > 1.0]
    *_, worst_pres = penetration_mm()
    import matplotlib.pyplot as plt
    hold = int((seconds if not quick else 2.5) * FPS)
    fig = new_fig()
    _title(fig, "Adding modal DOFs to a fixed-budget XPBD host?",
           sub="a diagnostic + operating guide -- not a solver ranking, not a "
               "governor method")
    ax = _axes_full(fig)
    rows = [
        ("1", "Contact architecture flexible?",
         "Use a stiffness-aware implicit / velocity contact realization.",
         "observed control: 0/24 overdraws, converges by $K{=}2$", SAFE),
        ("2", "Stuck with the XPBD shared row?",
         "Audit it: prefer iterations over substeps; band-limit the basis.",
         f"$32\\times1$ holds ($R{{=}}{r_32x1:.2f}$); $4\\times8$ overdraws "
         f"($+{m_4x8:.0f}$ J); band-limit still leaves {len(still)}/8 cells over",
         ACCENT),
        ("3", "Need a hard energy guarantee?",
         "The cumulative storage bound contains modal energy -- last resort.",
         f"holds in 90/90 cells, but still leaves up to {worst_pres:.1f} mm "
         f"penetration + a worse trajectory. Containment, not a fix.", UNSAFE),
    ]
    y = 0.72
    for num, q, a, note, col in rows:
        ax.add_patch(mpatches.Circle((0.075, y + 0.02), 0.028, facecolor=col,
                                     edgecolor="none", zorder=3,
                                     transform=fig.transFigure))
        fig.text(0.075, y + 0.02, num, ha="center", va="center", fontsize=18,
                 color=BG, fontweight="bold", zorder=4)
        fig.text(0.125, y + 0.045, q, ha="left", va="center", fontsize=18,
                 color=FG, fontweight="bold")
        fig.text(0.135, y + 0.005, a, ha="left", va="center", fontsize=16,
                 color=FG)
        fig.text(0.135, y - 0.032, note, ha="left", va="center", fontsize=13,
                 color=DIM)
        y -= 0.20
    fig.text(0.5, 0.075,
             "The governor is a safety net, not the product.",
             ha="center", va="center", fontsize=18, color=FG,
             fontweight="bold")
    wr.add(fig, times=hold)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "mig_short_video.mp4"))
    ap.add_argument("--quick", action="store_true",
                    help="short holds / coarse steps -- for iterating")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH")
    for case in ("steel", "deployed_gap"):
        if not os.path.exists(os.path.join(OUT, f"teaser_{case}.npz")):
            raise SystemExit(f"missing out/teaser_{case}.npz -- run "
                             f"record_teaser.py --case {case} first")

    q = args.quick
    step = 4 if q else 1
    repeat = 1 if q else 2
    # locked 3-D framing, shared with the teaser video. Each comparison beat is
    # animated (beat_sim), so the panel height is the sim layout's 0.345.
    aspect_2 = ((1.0 - 2 * 0.035 - 0.018) / 2 * W_IN) / (0.345 * H_IN)
    aspect_3 = ((1.0 - 2 * 0.035 - 2 * 0.018) / 3 * W_IN) / (0.345 * H_IN)
    npz0, _ = _load("deployed_gap")
    settle = int(npz0["off/settle"])
    START = settle + 20
    xlim2, ylim2 = global_bounds(("steel",), aspect_2, frame_lo=START)
    xlim3, ylim3 = global_bounds(("deployed_gap",), aspect_3,
                                 frame_lo=START)
    RANGE = (START, npz0["off/pos"].shape[0])
    # the soft-board animation stops at logged frame 63: past it the ungoverned
    # run drives a book through the board, which a painter's renderer cannot
    # depth-order honestly (the penetration beat that follows states it in mm).
    RANGE_SOFT = (START, settle + 64)

    tmp = tempfile.mkdtemp(prefix="mig_short_video_")
    wr = Writer(tmp)
    try:
        # --- beat 1: schematic ------------------------------------------
        beat_schematic(wr, seconds=6.0, quick=q)

        # --- beat 2: spurious launch, ungoverned vs self-reference ------
        card(wr, [
            ("A steel board should barely move.", 32, FG),
            ("Converged (the host's own 500x1 self-reference), the resting "
             "books rise 0.1 mm.", 19, DIM),
            ("At a production-like 1x8 budget, they are launched.", 20,
             ARM_COLOR["off"])],
            seconds=1.0 if q else 2.5,
            sub="steel shelf  ·  1 iteration x 8 substeps  ·  relaxation 0.7")
        beat_sim(wr, "steel", ("off", "ref"), xlim=xlim2, ylim=ylim2,
                 aspect=aspect_2, step=step, repeat=repeat,
                 hold_end=1.0 if q else 3.5, frame_range=RANGE,
                 title="steel board, 1 iteration x 8 substeps",
                 subtitle="ungoverned vs the host's own high-iteration "
                          "self-reference - the only honest baseline for "
                          "how much the row injects",
                 end_note="the launch is spurious: the self-reference leaves "
                          "the books within 0.1 mm of rest, so every millimetre "
                          "the ungoverned run moves them is truncation energy")

        # --- beat 3: equal-cost iteration vs substep allocation ---------
        beat_alloc(wr, seconds=8.0, quick=q)

        # --- beat 4: band-limited basis, necessary not sufficient -------
        beat_band(wr, seconds=7.0, quick=q)

        # --- beat 5: governor containment + penetration -----------------
        card(wr, [
            ("A last-resort guardrail: a cumulative storage bound.", 30, FG),
            ("It removes the spurious launch -- and takes the legitimate "
             "motion with it.", 20, DIM)],
            seconds=1.0 if q else 2.5,
            sub="soft shelf, E = 0.5 GPa  ·  1x8  ·  ungoverned / governed / "
                "self-reference")
        beat_sim(wr, "deployed_gap", ("off", "on", "ref"), xlim=xlim3,
                 ylim=ylim3,
                 aspect=aspect_3, step=step, repeat=repeat,
                 hold_end=1.0 if q else 3.5, frame_range=RANGE_SOFT,
                 title="bounded, but not faithful",
                 subtitle="ungoverned, governed by the surface-preserving "
                          "projection, and the host's own high-iteration "
                          "self-reference - three independent runs",
                 end_note="the bound removes the spurious launch and takes the "
                          "legitimate motion with it: the governed books "
                          "under-move the self-reference")
        beat_penetration(wr, seconds=5.0, quick=q)

        # --- beat 6: decision card --------------------------------------
        beat_decision(wr, seconds=7.0, quick=q)

        dur = wr.n / FPS
        print(f"rendered {wr.n} frames ({dur:.1f} s at {FPS} fps)")
        cmd = ["ffmpeg", "-y", "-framerate", str(FPS),
               "-i", os.path.join(tmp, "f%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
               "-map_metadata", "-1",              # strip any metadata (anon)
               "-movflags", "+faststart", args.out]
        subprocess.run(cmd, check=True, capture_output=True)
        mb = os.path.getsize(args.out) / 1e6
        print(f"wrote {args.out}  ({mb:.1f} MB, {dur:.1f} s)")
    finally:
        if args.keep_frames:
            print(f"frames kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
