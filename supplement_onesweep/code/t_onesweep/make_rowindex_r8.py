#!/usr/bin/env python3
"""make_rowindex_r8.py -- R8 re-layout of F2 (`fig_onesweep_rowindex.pdf`).

WHY. Two review panels flagged the shipped F2 for five defects, all confirmed at
source in `make_figs.fig_rowindex()` and on a 300 dpi render of the typeset page:

  1. In-panel type. Measured off the content stream of the shipped graphic,
     its glyphs are drawn at 4.20-12.00 pt and, after the 0.442955 page scale,
     PRINT at 1.86-5.32 pt; the smallest full-size (non-script) glyph prints at
     2.66 pt. The floor set by the paper's own line numbers is 5.98 pt. This
     rebuild prints 4.27-7.60 pt with every full-size glyph at 6.00 pt or more;
     the three values below 5.98 (4.27, 4.48, 4.76) are mathtext sub- and
     superscripts, which matplotlib always draws at 0.7x their base size, so
     lifting them over 5.98 would need an 8.54 pt base for every string
     carrying a subscript. At this canvas that forces a three-line x label,
     i.e. about 9 pt more float height, which the page budget cannot fund.
  2. The iteration-decay inset's x tick labels ("2", "4") printed straight
     through the readout line "... shelf 2/9, ledge 4/9".
  3. A red rectangle sat on the inset's "2" y tick. It is not an annotation: it
     is a DATA point (ledge scene, backward-Euler-weight arm, open red square at
     rho_mid = 4352, dE/E- = -0.0584) that the inset was drawn on top of.
  4. The annotation "(passive only where 2(w_row - w_r) <= w_r)" states a
     sufficient condition as if it were necessary, and uses `w_row`, a symbol the
     paper never defines.
  5. The graphic carried a suptitle and a five-line footer that the paper's
     trim cropped out of VIEW but not out of the CONTENT STREAM, so
     `pdftotext onesweep_short.pdf` still extracted "Shipped XPBD support row:
     ..." (the host name, a de-anonymisation risk) and "rho_matched", a symbol
     that appears nowhere else in the document.

HOW THIS FIXES ALL FIVE WITHOUT A SINGLE .tex CHANGE. The paper includes F2 as

    \\includegraphics[trim=0 74 0 40,clip,width=0.88\\textwidth]{fig_onesweep_rowindex.pdf}

against a MediaBox of 1005.84 x 457.864 pt, so the visible region is the band
y in [74, 417.864] (343.864 pt tall), rendered at
scale = 0.88 * 506.295 / 1005.84 = 0.442955, i.e. 445.54 x 152.30 pt on the page.

This script therefore builds a canvas of EXACTLY that MediaBox (fixed figsize,
saved with bbox_inches=None, so no tight-bbox surprise), lays every artist out
inside the visible band, leaves the cropped strips completely EMPTY (nothing to
extract: defect 5 is fixed at the source, not re-cropped), and multiplies every
font size by 1/0.442955 = 2.2576 so that a "6.0 pt" design size prints at 6.0 pt.
Geometry is designed in PRINTED points throughout; `P()` converts to canvas
points. The include line, the trim, the float height and therefore the page
ruler are all untouched.

Re-layout (defects 1-4):
  * readout counts move OUT of the axes into the panel head, two lines above
    each panel, where no datum, inset or legend can ever reach them;
  * the eight-entry in-panel legend becomes a seven-entry figure-level strip
    across the top (three scenes, three weights, the boundary line), freeing
    the whole plot area;
  * the inset moves into the band below dE/E- = -1.05, which contains no datum
    in any panel (the most negative measured cell is -0.9866), with its tick
    labels on top so they cannot run into the panel's own x axis;
  * quadrant shading is replaced by two half-plane bands (injects / passive),
    which is what the y axis already says and needs no legend entry;
  * the sufficient-not-necessary annotation is deleted. The exact criterion is
    the panel's own x axis (inject iff rho_mid > 1 for the mass weight), and the
    per-scene counts stay in the panel head.

NO DATA PATH IS DUPLICATED OR CHANGED. Every marker, count and curve is read
from the same logged CSVs through the same display transforms as
`make_figs.fig_rowindex()`, and the parity gate (on unless `--no-parity`)
rebuilds the shipped figure via `fix_rowindex_legend.build_figure()` and
asserts, panel by panel, that the 54 scatter offsets per panel and the four
inset curves are bit-identical to it.
No existing harness file is modified.

Gates that must pass before `--install` writes into paper/figures/:
  G1  MediaBox == 1005.84 x 457.864 pt (the paper's absolute trim stays valid);
  G2  every string's base size prints at >= 5.98 pt (the line-number size);
  G3  the text layer contains none of "XPBD", "rho_matched", "w_row",
      "passive only where", "validated boundary", and no path or user name;
  G4  the drawn counts equal the CSV-derived counts (27/27, 9/9, 2/9, 4/9,
      7/9, 5/9), so the body's "shelf 2/9" statement stays true;
  G5  no text box overlaps another, and no text box or the inset covers a
      plotted datum;
  G6  scatter/inset parity with the shipped figure;
  G7  every drawn artist lies inside the band the trim keeps, so nothing is
      clipped and nothing hides in the cropped strips;
  G8  adjacent tick labels stay >= 0.5 printed pt apart.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_rowindex_r8.py --install
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mpl-onesweep-")
import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.lines import Line2D                          # noqa: E402
from matplotlib.patches import Patch                         # noqa: E402

import make_figs                                             # noqa: E402

OUT = os.path.join(_HERE, "out")
PAPER_FIGS = os.path.join(_ROOT, "paper", "figures")
STEM = "fig_onesweep_rowindex"

# --------------------------------------------------------------------------- #
# The paper's geometry. Do not change without changing the include line.       #
# --------------------------------------------------------------------------- #
CANVAS_W = 1005.84          # pt, MediaBox width  (pinned by the include line)
CANVAS_H = 457.864          # pt, MediaBox height (pinned by the include line)
TRIM_B, TRIM_T = 74.0, 40.0                 # trim=0 74 0 40
TEXTWIDTH = 506.295         # pt, \textwidth in the ACM two-column class
INCLUDE_FRAC = 0.88         # width=0.88\textwidth
SCALE = INCLUDE_FRAC * TEXTWIDTH / CANVAS_W          # 0.442955 (canvas -> page)
INV = 1.0 / SCALE                                    # 2.257575 (page -> canvas)
PW = CANVAS_W * SCALE                                # 445.540 pt printed width
PH = (CANVAS_H - TRIM_B - TRIM_T) * SCALE            # 152.303 pt printed height

# Font sizes in PRINTED points. The paper's line numbers print at 5.98 pt and
# its body at 9.08 pt; nothing here may go below 5.98.
FS_TITLE = 7.6
FS_COUNT = 6.4
FS_COUNT_M = 6.1                  # the middle panel's per-scene count line
FS_AXIS = 6.8
FS_TICK = 6.4
FS_LEG = 6.4
FS_NOTE = 6.1
FS_INSET = 6.0
FONT_FLOOR = 5.98
MARKER_D = 3.6                    # printed marker diameter (pt)

# Layout in PRINTED points, origin at the bottom left of the VISIBLE band. The
# middle panel is the widest: it carries the longest axis label and the longest
# count line (the per-scene passive counts).
AX_X0, AX_GAP = 31.0, 10.0
AX_WS = (124.0, 145.0, 124.0)
AX_Y0, AX_H = 30.5, 83.0
LEG_Y = 141.8                     # bottom edge of the legend strip
TITLE_Y = 140.2                   # top edge of the panel title
COUNT1_Y = 130.4
COUNT2_Y = 122.2

# Shared y limits: the data span [-0.9866, 8.918e4]; the extra negative decades
# are deliberate empty space that carries the inset (see module docstring). The
# most negative datum sits at 0.34 of the panel height, the inset ends at 0.28.
YLIM = (-1e7, 2e5)
YTICKS = [-1e2, -1e0, 0.0, 1e0, 1e2, 1e4]
LINTHRESH = 1e-2

BAND_INJ = "#d62728"              # dE > 0 half plane
BAND_PAS = "#2ca02c"              # dE < 0 half plane
BAND_ALPHA = 0.055

FORBIDDEN = ("XPBD", "rho_matched", "w_row", "passive only where",
             "validated boundary", "/Users", "Desktop", "onesweep_short")


def _pad():
    """Half a marker plus half a point, in canvas points."""
    return (MARKER_D / 2.0 + 0.5) / SCALE


def P(pt):
    """Printed points -> canvas points."""
    return pt * INV


def rect(x0, y0, w, h):
    """Printed-point rectangle -> figure fraction rectangle."""
    return [P(x0) / CANVAS_W, (TRIM_B + P(y0)) / CANVAS_H,
            P(w) / CANVAS_W, P(h) / CANVAS_H]


def fxy(x0, y0):
    """Printed-point position -> figure fraction position."""
    return P(x0) / CANVAS_W, (TRIM_B + P(y0)) / CANVAS_H


# --------------------------------------------------------------------------- #
# Data (identical transforms to make_figs.fig_rowindex)                        #
# --------------------------------------------------------------------------- #
def e_minus(r):
    wr = float(r["w_r"]); v = float(r["v"])
    return 0.5 * (1.0 / wr) * v * v            # logged row-reduced KE scale


def rho_be(r):
    return float(r["rho"])                     # logged L / (w_m + 2 a_tilde)


def rho_mid(r):
    """Result-6 midpoint index, a display transform of logged columns:
    (L + 2 sum_i a_i) / (w_r + 2 a_tilde), with sum_i a_i = w_row - w_r."""
    L = float(r["L"]); w_row = float(r["w_row"]); w_r = float(r["w_r"])
    a = float(r["a_tilde"])
    return (L + 2.0 * (w_row - w_r)) / (w_r + 2.0 * a)


def load_cells():
    rows = [r for r in make_figs.load_csv("t4_shipped.csv")
            if str(r["valid"]) == "True"]
    prim = [r for r in rows if int(r["iterations"]) == 1]
    annex = [r for r in rows if int(r["iterations"]) != 1]
    matched = [r for r in make_figs.load_csv("t4_matched.csv")
               if str(r["valid"]) == "True" and int(r["iterations"]) == 1]
    if not matched:
        raise RuntimeError("t4_matched.csv has no valid one-sweep cells")
    return prim, annex, matched


def counts(prim, matched):
    mass = [r for r in prim if r["arm"] == "mass"]
    impl = [r for r in prim if r["arm"] == "implicit"]
    scenes = list(make_figs.SCENE_STYLE)
    c = {
        "n_mass": len(mass),
        "sign_be": sum((rho_be(r) > 1.0) == (float(r["dE_be"]) > 0.0)
                       for r in mass),
        "sign_mid": sum((rho_mid(r) > 1.0) == (float(r["dE_meas"]) > 0.0)
                        for r in mass),
        "n_per": {s: sum(1 for r in mass if r["scene"] == s) for s in scenes},
        "be_pass_be": {s: sum(float(r["dE_be"]) <= 1e-12
                              for r in impl if r["scene"] == s) for s in scenes},
        "be_pass_sym": {s: sum(float(r["dE_meas"]) <= 1e-12
                               for r in impl if r["scene"] == s)
                        for s in scenes},
        "matched_pass": {s: sum(float(r["dE_meas"]) <= 1e-12
                                for r in matched if r["scene"] == s)
                         for s in scenes},
        "matched_n": {s: sum(1 for r in matched if r["scene"] == s)
                      for s in scenes},
    }
    c["be_inj_sym"] = {s: c["n_per"][s] - c["be_pass_sym"][s] for s in scenes}
    return c


# --------------------------------------------------------------------------- #
# Figure                                                                       #
# --------------------------------------------------------------------------- #
def build_figure():
    prim, annex, matched = load_cells()
    c = counts(prim, matched)
    style = make_figs.SCENE_STYLE

    fig = plt.figure(figsize=(CANVAS_W / 72.0, CANVAS_H / 72.0), dpi=72)
    x0s = [AX_X0]
    for w in AX_WS[:-1]:
        x0s.append(x0s[-1] + w + AX_GAP)
    axes = [fig.add_axes(rect(x0s[i], AX_Y0, AX_WS[i], AX_H))
            for i in range(3)]
    axL, axM, axR = axes
    tracked = {"text": [], "points": {0: [], 1: [], 2: []}, "inset": None}

    def panel_common(ax, idx):
        ax.set_xscale("log")
        ax.set_yscale("symlog", linthresh=LINTHRESH)
        ax.set_ylim(*YLIM)
        ax.set_yticks(YTICKS)
        ax.tick_params(axis="both", which="major", labelsize=P(FS_TICK),
                       length=P(1.8), width=P(0.4), pad=P(1.6))
        ax.tick_params(axis="both", which="minor", length=P(0.9),
                       width=P(0.3))
        for s in ax.spines.values():
            s.set_linewidth(P(0.5))
        if idx:
            ax.set_yticklabels([])

    def bands(ax):
        xlo, xhi = ax.get_xlim()
        ax.add_patch(plt.Rectangle((xlo, 0.0), xhi - xlo, YLIM[1],
                                   color=BAND_INJ, alpha=BAND_ALPHA, zorder=0))
        ax.add_patch(plt.Rectangle((xlo, YLIM[0]), xhi - xlo, -YLIM[0],
                                   color=BAND_PAS, alpha=BAND_ALPHA, zorder=0))
        ax.set_xlim(xlo, xhi)

    def scatter(ax, idx, rows, xfunc, ykey, filled, alpha=1.0, dark_edge=False):
        for scene, (mk, cvec) in style.items():
            sel = [r for r in rows if r["scene"] == scene]
            if not sel:
                continue
            x = np.array([xfunc(r) for r in sel])
            y = np.array([float(r[ykey]) / e_minus(r) for r in sel])
            o = np.argsort(x)
            ax.scatter(x[o], y[o], marker=mk,
                       facecolors=(cvec if filled else "none"),
                       edgecolors=("k" if (filled and dark_edge) else cvec),
                       s=P(MARKER_D) ** 2, linewidths=P(0.55),
                       alpha=alpha, zorder=(6 if filled else 4),
                       label="_nolegend_")
            tracked["points"][idx].extend(zip(x[o], y[o]))

    def head(ax, title, line1, line2, fs2=None):
        cx = ax.get_position().x0 + ax.get_position().width / 2.0
        for y, s, fs in ((TITLE_Y, title, FS_TITLE),
                         (COUNT1_Y, line1, FS_COUNT),
                         (COUNT2_Y, line2, fs2 or FS_COUNT)):
            t = fig.text(cx, fxy(0.0, y)[1], s, ha="center", va="top",
                         fontsize=P(fs))
            tracked["text"].append(t)

    def note(ax, x, y, s, fs=FS_NOTE, ha="left", va="center"):
        t = ax.text(x, y, s, transform=ax.transAxes, fontsize=P(fs),
                    ha=ha, va=va, zorder=8)
        tracked["text"].append(t)
        return t

    mass = [r for r in prim if r["arm"] == "mass"]
    impl = [r for r in prim if r["arm"] == "implicit"]

    # ---- LEFT: backward-Euler control, boundary rho = 1 -------------------- #
    panel_common(axL, 0)
    scatter(axL, 0, mass, rho_be, "dE_be", filled=True)
    scatter(axL, 0, impl, rho_be, "dE_be", filled=False)
    bands(axL)
    axL.vlines(1.0, -2.0, YLIM[1], color="k", lw=P(0.55),
               ls=(0, (3, 2)), zorder=2)
    axL.axhline(0.0, color="k", lw=P(0.5), ls=(0, (3, 2)), zorder=2)
    axL.set_ylabel(r"one-substep  $\Delta E / E^{-}$", fontsize=P(FS_AXIS),
                   labelpad=P(1.6))
    axL.set_xlabel("row danger index" "\n"
                   r"$\rho = L/(w_m + 2\tilde\alpha)$",
                   fontsize=P(FS_AXIS), labelpad=P(1.4))
    head(axL, "Backward-Euler control",
         r"mass weight sign vs $\rho > 1$: %d/%d" % (c["sign_be"], c["n_mass"]),
         "BE weight passive: %d/%d per scene"
         % (c["be_pass_be"]["shelf"], c["n_per"]["shelf"]))
    note(axL, 0.03, 0.965, "injects", ha="left", va="top", fs=FS_NOTE)
    note(axL, 0.03, 0.035, "passive", ha="left", va="bottom", fs=FS_NOTE)

    # ---- MIDDLE: shipped symplectic default, boundary rho_mid = 1 --------- #
    panel_common(axM, 1)
    scatter(axM, 1, mass, rho_mid, "dE_meas", filled=True)
    scatter(axM, 1, impl, rho_mid, "dE_meas", filled=False)
    bands(axM)
    axM.vlines(1.0, -2.0, YLIM[1], color="k", lw=P(0.55),
               ls=(0, (3, 2)), zorder=2)
    axM.axhline(0.0, color="k", lw=P(0.5), ls=(0, (3, 2)), zorder=2)
    axM.set_xlabel("midpoint index" "\n"
                   r"$\rho_{\mathrm{mid}} = (L + 2\Sigma_i a_i)"
                   r"/(w_r + 2\tilde\alpha)$",
                   fontsize=P(FS_AXIS), labelpad=P(1.4))
    head(axM, "Shipped symplectic default",
         r"mass weight sign vs $\rho_{\mathrm{mid}} > 1$: %d/%d"
         % (c["sign_mid"], c["n_mass"]),
         "BE weight passive: dinner %d/%d, shelf %d/%d, ledge %d/%d"
         % (c["be_pass_sym"]["dinner"], c["n_per"]["dinner"],
            c["be_pass_sym"]["shelf"], c["n_per"]["shelf"],
            c["be_pass_sym"]["ledge"], c["n_per"]["ledge"]),
         fs2=FS_COUNT_M)
    note(axM, 0.145, 0.955, r"$\dot q^{+} = 2\,\Delta q/h$", va="top")

    # ---- RIGHT: reconstruction-matched weight ----------------------------- #
    panel_common(axR, 2)
    scatter(axR, 2, impl, rho_be, "dE_meas", filled=False, alpha=0.5)
    scatter(axR, 2, matched, lambda r: float(r["rho_host"]), "dE_meas",
            filled=True, dark_edge=True)
    bands(axR)
    axR.axhline(0.0, color="k", lw=P(0.5), ls=(0, (3, 2)), zorder=2)
    axR.set_xlabel("row danger index" "\n"
                   r"$\rho = L/(w_m + 2\tilde\alpha)$",
                   fontsize=P(FS_AXIS), labelpad=P(1.4))
    head(axR, "Reconstruction-matched weight",
         "matched weight passive: %d/%d per scene"
         % (c["matched_pass"]["shelf"], c["matched_n"]["shelf"]),
         "BE injects: shelf %d/%d, ledge %d/%d"
         % (c["be_inj_sym"]["shelf"], c["n_per"]["shelf"],
            c["be_inj_sym"]["ledge"], c["n_per"]["ledge"]))
    note(axR, 0.035, 0.955, r"$w = 1/(4 M_q + h^2 K_q)$", va="top")

    # ---- inset: iteration decay, in the empty band below dE/E- = -1 ------- #
    axin = axM.inset_axes([0.03, 0.02, 0.55, 0.21])
    s_vals = sorted(set(float(r["s"]) for r in annex))
    for sv in s_vals:
        sel = sorted([r for r in annex if abs(float(r["s"]) - sv) < 1e-30],
                     key=lambda r: int(r["iterations"]))
        if not sel:
            continue
        it = np.array([int(r["iterations"]) for r in sel])
        de = np.array([float(r["dE_meas"]) for r in sel])
        axin.plot(it, de, "-o", ms=P(1.5), lw=P(0.55))
    axin.axhline(0.0, color="k", lw=P(0.4), ls=(0, (2, 2)))
    axin.set_xticks([2, 4, 8])
    axin.set_yticks([0, 2])
    axin.xaxis.set_ticks_position("top")
    axin.xaxis.set_label_position("top")
    axin.tick_params(axis="both", labelsize=P(FS_INSET), length=P(1.2),
                     width=P(0.35), pad=P(0.8))
    for s in axin.spines.values():
        s.set_linewidth(P(0.4))
    axin.patch.set_alpha(1.0)
    tracked["inset"] = axin
    note(axM, 0.600, 0.120, "shelf, mass weight:" "\n"
         r"$\Delta E$ (J) vs sweeps", fs=FS_INSET, va="center")

    # ---- figure-level legend strip ---------------------------------------- #
    handles = [Line2D([0], [0], marker=mk, color="w", markerfacecolor=cv,
                      markeredgecolor=cv, markersize=P(3.2), label=sc)
               for sc, (mk, cv) in style.items()]
    handles += [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#555555",
               markeredgecolor="#555555", markersize=P(3.2),
               label="mass weight (filled)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor="#555555", markersize=P(3.2),
               label="backward-Euler weight (open)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#555555",
               markeredgecolor="k", markersize=P(3.2),
               label="matched weight"),
        Line2D([0], [0], color="k", lw=P(0.55), ls=(0, (3, 2)),
               label="index = 1"),
    ]
    leg = fig.legend(handles=handles, loc="lower center",
                     bbox_to_anchor=(0.5, fxy(0.0, LEG_Y)[1]),
                     ncol=len(handles), fontsize=P(FS_LEG), frameon=False,
                     handlelength=1.3, handletextpad=0.4, columnspacing=1.1,
                     borderpad=0.0, borderaxespad=0.0)
    tracked["legend"] = leg
    return fig, tracked, c


# --------------------------------------------------------------------------- #
# Gates                                                                        #
# --------------------------------------------------------------------------- #
def bbox_of(artist, renderer):
    return artist.get_window_extent(renderer)


def audit(fig, tracked, c, verbose=True):
    """G2 (type size), G5 (overlap). Window extents are canvas points because
    the figure dpi is 72; printed size = canvas size * SCALE."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    fails = []

    sizes = []
    for t in fig.findobj(matplotlib.text.Text):
        s = t.get_text()
        if not s or not s.strip():
            continue
        pr = t.get_fontsize() * SCALE
        sizes.append((pr, s.replace("\n", " | ")[:48]))
    sizes.sort()
    for pr, s in sizes:
        if pr < FONT_FLOOR - 1e-9:
            fails.append("G2 type %.2f pt < %.2f: %r" % (pr, FONT_FLOOR, s))
    if verbose:
        print("G2 smallest printed type: %.2f pt  (%s)" % sizes[0])
        print("   next four: " + ", ".join("%.2f" % p for p, _ in sizes[1:5]))

    boxes = []
    for t in tracked["text"]:
        boxes.append((t.get_text().replace("\n", " | ")[:34],
                      bbox_of(t, rend)))
    if verbose:
        print("   printed text extents (pt):")
        for name, bb in boxes:
            print("     %6.1f x %5.1f  %s"
                  % (bb.width * SCALE, bb.height * SCALE, name))
    boxes.append(("LEGEND", tracked["legend"].get_window_extent(rend)))
    boxes.append(("INSET", tracked["inset"].get_tightbbox(rend)))

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            if a.overlaps(b):
                fails.append("G5 text overlap: %r vs %r"
                             % (boxes[i][0], boxes[j][0]))

    MARKER_PAD = _pad()
    axes = [ax for ax in fig.axes if ax is not tracked["inset"]]
    for idx, ax in enumerate(axes):
        pts = tracked["points"][idx]
        if not pts:
            continue
        xy = ax.transData.transform(np.array(pts))
        for name, bb in boxes:
            hit = ((xy[:, 0] > bb.x0 - MARKER_PAD) &
                   (xy[:, 0] < bb.x1 + MARKER_PAD) &
                   (xy[:, 1] > bb.y0 - MARKER_PAD) &
                   (xy[:, 1] < bb.y1 + MARKER_PAD))
            if hit.any():
                k = int(np.argmax(hit))
                fails.append("G5 %r covers datum panel%d (%.4g, %.4g)"
                             % (name, idx, pts[k][0], pts[k][1]))
        inside = ((xy[:, 0] >= ax.bbox.x0) & (xy[:, 0] <= ax.bbox.x1) &
                  (xy[:, 1] >= ax.bbox.y0) & (xy[:, 1] <= ax.bbox.y1))
        if not inside.all():
            fails.append("G5 panel%d clips %d datum(s)"
                         % (idx, int((~inside).sum())))

    # G7: everything drawn must lie inside the band the paper's trim keeps.
    # (Display coordinates are canvas points with the origin bottom left, the
    # same convention as the PDF MediaBox, because the figure dpi is 72.)
    band = (0.0, TRIM_B, CANVAS_W, CANVAS_H - TRIM_T)
    drawn = [("panel%d" % i, ax.get_tightbbox(rend))
             for i, ax in enumerate(axes)]
    drawn += [("INSET", tracked["inset"].get_tightbbox(rend)),
              ("LEGEND", tracked["legend"].get_window_extent(rend))]
    drawn += [(t.get_text().replace("\n", " | ")[:26], bbox_of(t, rend))
              for t in tracked["text"]]
    worst = 0.0
    for name, bb in drawn:
        over = max(band[0] - bb.x0, bb.x1 - band[2],
                   band[1] - bb.y0, bb.y1 - band[3])
        worst = max(worst, over)
        if over > 0.25:
            fails.append("G7 %r sticks %.2f canvas pt (printed %.2f pt) "
                         "outside the visible band" % (name, over,
                                                       over * SCALE))
    # G8: adjacent tick labels must not touch (they are the smallest type).
    for idx, ax in enumerate(axes):
        for which, labs in (("x", ax.get_xticklabels()),
                            ("y", ax.get_yticklabels())):
            vis = [t for t in labs if t.get_visible() and t.get_text()]
            bbs = sorted((bbox_of(t, rend) for t in vis),
                         key=lambda b: b.x0 if which == "x" else b.y0)
            for a, b in zip(bbs, bbs[1:]):
                gap = (b.x0 - a.x1) if which == "x" else (b.y0 - a.y1)
                if gap < P(0.5):
                    fails.append("G8 panel%d %s tick labels %.2f printed pt "
                                 "apart (floor 0.50)"
                                 % (idx, which, gap * SCALE))
    if verbose:
        lb = tracked["legend"].get_window_extent(rend)
        print("   legend printed width %.1f pt of %.1f; worst band overshoot "
              "%.2f canvas pt (%.2f printed)"
              % (lb.width * SCALE, PW, worst, worst * SCALE))
        for name, bb in drawn[:4]:
            print("     %-7s printed x %6.1f..%6.1f  y %6.1f..%6.1f"
                  % (name, bb.x0 * SCALE, bb.x1 * SCALE,
                     (bb.y0 - TRIM_B) * SCALE, (bb.y1 - TRIM_B) * SCALE))
    return fails


def parity(tracked, verbose=True):
    """G6: the plotted arrays must equal the shipped figure's, exactly."""
    import fix_rowindex_legend as frl
    ref_fig, _ = frl.build_figure()
    ref = {}
    for idx, ax in enumerate(ref_fig.axes[:3]):
        pts = []
        for coll in ax.collections:
            off = coll.get_offsets()
            if off is not None and len(off):
                pts.extend([tuple(p) for p in np.asarray(off)])
        ref[idx] = sorted(pts)
    ref_ins = []
    # `Axes.inset_axes` parents the inset to the panel, not to the figure, so
    # the shipped inset lives in axM.child_axes rather than in fig.axes.
    ref_insets = list(ref_fig.axes[3:])
    for ax in ref_fig.axes[:3]:
        ref_insets.extend(getattr(ax, "child_axes", []))
    for ax in ref_insets:
        for ln in ax.get_lines():
            xd, yd = ln.get_xdata(), ln.get_ydata()
            if len(xd) > 1:
                ref_ins.append((tuple(map(float, xd)), tuple(map(float, yd))))
    plt.close(ref_fig)

    fails = []
    for idx in range(3):
        got = sorted(tuple(map(float, p)) for p in tracked["points"][idx])
        want = sorted(tuple(map(float, p)) for p in ref[idx])
        if len(got) != len(want):
            fails.append("G6 panel%d count %d vs shipped %d"
                         % (idx, len(got), len(want)))
            continue
        d = max(abs(a[0] - b[0]) + abs(a[1] - b[1])
                for a, b in zip(got, want))
        if d != 0.0:
            fails.append("G6 panel%d offsets differ (max |d| = %.3g)"
                         % (idx, d))
        elif verbose:
            print("G6 panel%d: %d offsets bit-identical to the shipped figure"
                  % (idx, len(got)))
    ins = []
    for ln in tracked["inset"].get_lines():
        xd, yd = ln.get_xdata(), ln.get_ydata()
        if len(xd) > 1:
            ins.append((tuple(map(float, xd)), tuple(map(float, yd))))
    if sorted(ins) != sorted(ref_ins):
        fails.append("G6 inset curves differ from the shipped figure")
    elif verbose:
        print("G6 inset: %d curves bit-identical" % len(ins))
    return fails


def text_layer(pdf, verbose=True):
    """G3: nothing extractable that the printed page does not show."""
    txt = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True).stdout
    fails = ["G3 forbidden string in text layer: %r" % w
             for w in FORBIDDEN if w.lower() in txt.lower()]
    if verbose:
        print("G3 text layer: %d chars, %d forbidden hits"
              % (len(txt.strip()), len(fails)))
    return fails


def count_gate(fig, c, verbose=True):
    """G4: the drawn strings must carry the CSV-derived counts."""
    drawn = " ".join(t.get_text() for t in fig.findobj(matplotlib.text.Text)
                     if t.get_text())
    want = ["%d/%d" % (c["sign_be"], c["n_mass"]),
            "%d/%d" % (c["sign_mid"], c["n_mass"]),
            "dinner %d/%d" % (c["be_pass_sym"]["dinner"], c["n_per"]["dinner"]),
            "shelf %d/%d" % (c["be_pass_sym"]["shelf"], c["n_per"]["shelf"]),
            "ledge %d/%d" % (c["be_pass_sym"]["ledge"], c["n_per"]["ledge"]),
            "shelf %d/%d" % (c["be_inj_sym"]["shelf"], c["n_per"]["shelf"]),
            "ledge %d/%d" % (c["be_inj_sym"]["ledge"], c["n_per"]["ledge"])]
    fails = ["G4 missing count %r in the drawn strings" % w
             for w in want if w not in drawn]
    if verbose:
        print("G4 counts: sign %d/%d and %d/%d; BE passive dinner %d, shelf %d,"
              " ledge %d; BE injects shelf %d, ledge %d; matched %d/%d"
              % (c["sign_be"], c["n_mass"], c["sign_mid"], c["n_mass"],
                 c["be_pass_sym"]["dinner"], c["be_pass_sym"]["shelf"],
                 c["be_pass_sym"]["ledge"], c["be_inj_sym"]["shelf"],
                 c["be_inj_sym"]["ledge"], c["matched_pass"]["shelf"],
                 c["matched_n"]["shelf"]))
    return fails


def mediabox(pdf, verbose=True):
    """G1: the paper's absolute trim is only valid against this MediaBox."""
    txt = subprocess.run(["pdfinfo", pdf], capture_output=True,
                         text=True).stdout
    line = [l for l in txt.splitlines() if l.startswith("Page size")][0]
    got = tuple(float(v) for v in line.split(":")[1].split("pts")[0].split("x"))
    ok = abs(got[0] - CANVAS_W) < 0.05 and abs(got[1] - CANVAS_H) < 0.05
    if verbose:
        print("G1 MediaBox %.3f x %.3f pt (required %.3f x %.3f) -> %s"
              % (got[0], got[1], CANVAS_W, CANVAS_H, "OK" if ok else "FAIL"))
    return [] if ok else ["G1 MediaBox %.3f x %.3f != %.3f x %.3f"
                          % (got + (CANVAS_W, CANVAS_H))]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true",
                    help="copy over paper/figures/%s.pdf (only if every gate "
                         "passes)" % STEM)
    ap.add_argument("--no-parity", action="store_true",
                    help="skip G6 (rebuilding the shipped figure is slow)")
    ap.add_argument("--preview-dpi", type=float, default=300.0,
                    help="dpi of the print-equivalent PNG preview")
    args = ap.parse_args()

    fig, tracked, c = build_figure()
    fails = audit(fig, tracked, c)
    fails += count_gate(fig, c)
    if not args.no_parity:
        fails += parity(tracked)

    pdf = os.path.join(OUT, STEM + "_r8.pdf")
    fig.savefig(pdf)                       # bbox_inches=None: MediaBox = figsize
    png = os.path.join(OUT, STEM + "_r8.png")
    fig.savefig(png, dpi=args.preview_dpi * SCALE)   # print-equivalent raster
    plt.close(fig)
    print("built %s" % os.path.relpath(pdf, _ROOT))
    print("      %s (print-equivalent %.0f dpi)"
          % (os.path.relpath(png, _ROOT), args.preview_dpi))

    fails += mediabox(pdf)
    fails += text_layer(pdf)

    if fails:
        print("\nGATES FAILED (%d):" % len(fails))
        for f in fails:
            print("  " + f)
        sys.exit(1)
    print("\nall gates pass; printed size %.2f x %.2f pt at "
          "trim=0 74 0 40, width=0.88\\textwidth" % (PW, PH))
    if args.install:
        dst = os.path.join(PAPER_FIGS, STEM + ".pdf")
        shutil.copyfile(pdf, dst)
        print("installed -> %s" % os.path.relpath(dst, _ROOT))


if __name__ == "__main__":
    main()
