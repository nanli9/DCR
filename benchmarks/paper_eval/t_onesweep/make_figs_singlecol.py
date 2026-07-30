#!/usr/bin/env python3
"""make_figs_singlecol.py -- single-column re-plot of the F1 phase map.

WHY THIS EXISTS. F1 (`fig_onesweep_phase_map.pdf`, built by `make_figs.py`) was
drawn on a 10.4 in canvas and placed in the paper as a two-column `figure*` at
0.92\\textwidth (465.8 pt). That is a 0.60x shrink, so its 9 pt tick labels
reached the printed page at about 4.6 pt, and its in-panel legend sat on top of
the data. This script redraws the SAME figure from the SAME CSV at exactly one
column width, so the on-page shrink is 1.00x and every glyph reaches the page at
the size it is set here.

Convention (kept from the earlier session): NEW script, never an edit to a
tracked harness file. `make_figs.py` is untouched and still builds the
wide version into out/.

WHAT IS IDENTICAL TO make_figs.py:fig_phase_map()
  * the input file: out/t2_phasemap.csv (no physics recomputed anywhere);
  * the plotted quantities: logged columns dE_mass_norm and dE_impl_norm on the
    logged (omega_h, m_over_M) grid;
  * the single theory overlay: the analytic sign boundary (omega h)^2 = 1 + m/M,
    which states the hypothesis of the claim rather than fitting the data;
  * the color scale: shared SymLogNorm(linthresh=1e-2) on RdBu_r with the same
    robust vmax = 99th percentile of |dE_mass_norm|.

WHAT CHANGES (presentation only)
  * canvas 3.34927 in wide == \\columnwidth of the acmart sigconf class, saved
    WITHOUT bbox_inches="tight" so the MediaBox is exactly one column and
    \\includegraphics[width=\\columnwidth] scales by 0.996 (PostScript points in,
    TeX points out);
  * type sizes raised so that NO GLYPH on the page is below 6 pt, counting
    mathtext sub- and superscripts, which matplotlib sets at 0.7x the base size
    and which are what the earlier layout audit was measuring. The wide version
    set tick labels at 10 pt on a canvas the page shrank by 0.596, so its tick
    digits printed at 5.96 pt and their exponents at 4.17 pt, and its panel-title
    superscripts at 4.59 pt. Two consequences for this version: the base sizes
    are 8.5 to 9.0 pt (0.7x of which clears 6 pt), and the log tick labels are
    written as plain decimals rather than powers of ten, so the axis numbers
    carry no reduced-size glyph at all;
  * the panel-title formulas use mathtext {+} so they fit the narrower panel
    without dropping the operator the title names;
  * the boundary legend moved OUT of the data area to a figure-level row below
    the axes, so it cannot occlude any cell or readout;
  * the suptitle band and the footer band are dropped. They restated the LaTeX
    caption verbatim and the paper cropped them away with trim/clip; a
    regenerated figure should not need cropping;
  * the 241 x 241 pcolormesh is rasterized at 600 dpi. Text stays vector. This
    is a file-size choice (the vector version embedded 58,081 quads, 2.4 MB);
    it changes no datum.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_figs_singlecol.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mpl-onesweep-")
import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
import matplotlib.colors as mcolors                          # noqa: E402
import matplotlib.ticker as mticker                          # noqa: E402
from matplotlib.lines import Line2D                          # noqa: E402

from make_figs import load_csv, col                          # noqa: E402

OUT = os.path.join(_HERE, "out")
PAPER_FIGS = os.path.join(_ROOT, "paper", "figures")

# acmart sigconf, [sigconf,screen,review,anonymous]: \columnwidth = 241.14749 pt.
COLUMN_W_IN = 241.14749 / 72.0                               # 3.34927 in

# On-page point sizes. Scale to the page is 0.996, so these are the printed
# sizes to within 0.4%. Every one of them is at or above 8.5, so mathtext
# sub- and superscripts (0.7x) land at or above 5.95 pt, and the only elements
# that contain any are the titles, the legend and the colorbar label, all set at
# 8.7 or more so their reduced glyphs clear 6.0 pt.
FS_TICK = 8.5                  # plain decimals: no reduced glyphs at all
FS_CBAR_TICK = 8.5             # plain decimals: no reduced glyphs at all
FS_CBAR_LABEL = 8.7            # contains $E^-$        -> 6.09 pt superscript
FS_AXLABEL = 9.0               # $\omega h$, $m/M$: no sub/superscripts
FS_TITLE = 8.7                 # contains $M_q$, $h^2$ -> 6.09 pt sub/superscript
FS_LEGEND = 8.7                # contains $(\omega h)^2$ -> 6.09 pt superscript


def _plain(v):
    """Decade value -> plain decimal string ('0.001', '1', '1000').

    Log axes normally render as $10^{-3}$, whose exponent matplotlib sets at
    0.7x. Writing the decade out keeps every digit at the full label size.
    """
    if v == 0:
        return "0"
    neg = v < 0
    a = abs(v)
    exp = int(round(np.log10(a)))
    s = ("%.*f" % (max(0, -exp), a)) if exp < 0 else ("%d" % round(a))
    return ("-" + s) if neg else s


def fig_phase_map_singlecol(height_in=1.86):
    rows = load_csv("t2_phasemap.csv")
    oh = col(rows, "omega_h")
    mm = col(rows, "m_over_M")
    z_mass = col(rows, "dE_mass_norm")     # logged dE/E- (mass arm)
    z_impl = col(rows, "dE_impl_norm")     # logged dE/E- (implicit arm)

    ox, ix = np.unique(oh, return_inverse=True)
    my, iy = np.unique(mm, return_inverse=True)
    Zm = np.full((my.size, ox.size), np.nan)
    Zi = np.full((my.size, ox.size), np.nan)
    Zm[iy, ix] = z_mass
    Zi[iy, ix] = z_impl

    vmax = float(np.nanpercentile(np.abs(z_mass), 99))
    norm = mcolors.SymLogNorm(linthresh=1e-2, vmin=-vmax, vmax=vmax, base=10)
    cmap = plt.get_cmap("RdBu_r")

    fig, axes = plt.subplots(
        1, 2, figsize=(COLUMN_W_IN, height_in), sharex=True, sharey=True,
        layout="constrained")
    fig.get_layout_engine().set(w_pad=0.010, h_pad=0.006,
                                wspace=0.030, hspace=0.0)

    y_curve = my
    x_curve = np.sqrt(1.0 + y_curve)

    # Titles use the caption's own vocabulary ("Left: the mass-only weight ...
    # Right: the implicit weight ..."), so no unreferenced (a)/(b) labels appear.
    # {+} keeps mathtext from padding the operators, which is what lets the
    # implicit-weight formula stay on the panel at 8.7 pt.
    for ax, Z, title in (
            (axes[0], Zm, "mass-only weight\n$1/M_q$"),
            (axes[1], Zi,
             "implicit weight\n$(M_q{+}hD_q{+}h^2K_q)^{-1}$")):
        pcm = ax.pcolormesh(ox, my, Z, cmap=cmap, norm=norm,
                            shading="nearest", rasterized=True)
        ax.plot(x_curve, y_curve, "k-", lw=1.0)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(r"$\omega h$", fontsize=FS_AXLABEL, labelpad=1.0)
        ax.set_title(title, fontsize=FS_TITLE, pad=2.0, linespacing=1.15)
        ax.set_xlim(ox.min(), ox.max())
        ax.set_ylim(my.min(), my.max())
        # Fixed decade ticks with plain decimal labels (see _plain). The y range
        # spans six decades; every decade gets a tick mark, but only alternate
        # decades get a label, so 8.5 pt digits never collide on a short panel.
        xticks = [0.1, 1.0, 10.0]
        yticks = [1e-3, 1e-1, 10.0, 1000.0]
        yticks_minor = [1e-2, 1.0, 100.0]
        ax.xaxis.set_major_locator(mticker.FixedLocator(xticks))
        ax.xaxis.set_major_formatter(
            mticker.FixedFormatter([_plain(v) for v in xticks]))
        ax.yaxis.set_major_locator(mticker.FixedLocator(yticks))
        ax.yaxis.set_major_formatter(
            mticker.FixedFormatter([_plain(v) for v in yticks]))
        ax.xaxis.set_minor_locator(mticker.NullLocator())
        ax.yaxis.set_minor_locator(mticker.FixedLocator(yticks_minor))
        # Without this the default log minor formatter re-labels them as powers.
        ax.yaxis.set_minor_formatter(mticker.NullFormatter())
        ax.tick_params(axis="both", which="major", labelsize=FS_TICK,
                       length=2.6, pad=1.4, width=0.6)
        ax.tick_params(axis="y", which="minor", length=1.4, width=0.6)
        for s in ax.spines.values():
            s.set_linewidth(0.6)
    axes[0].set_ylabel(r"$m/M$", fontsize=FS_AXLABEL, labelpad=1.0)

    cb = fig.colorbar(pcm, ax=axes, fraction=0.050, pad=0.018, aspect=16)
    cb.set_label(r"signed $\Delta E / E^-$  (SymLog)", fontsize=FS_CBAR_LABEL,
                 labelpad=1.5)
    cticks = [-100.0, -1.0, 0.0, 1.0, 100.0]
    cb.set_ticks(cticks)
    cb.ax.set_yticklabels([_plain(v) for v in cticks])
    cb.ax.tick_params(labelsize=FS_CBAR_TICK, length=2.0, pad=1.2, width=0.6)
    cb.outline.set_linewidth(0.6)

    # Legend OUTSIDE the data area (constrained-layout reserves its own row), so
    # it cannot cover a cell, the boundary curve, or any axis.
    fig.legend(handles=[Line2D([0], [0], color="k", lw=1.0,
                               label=r"analytic boundary $(\omega h)^2 = 1 + m/M$")],
               loc="outside lower center", fontsize=FS_LEGEND, frameon=False,
               handlelength=1.6, handletextpad=0.5, borderpad=0.1,
               borderaxespad=0.0)

    stem = "fig_onesweep_phase_map"
    pdf = os.path.join(OUT, stem + "_singlecol.pdf")
    png = os.path.join(OUT, stem + "_singlecol.png")
    # No bbox_inches="tight": the MediaBox must stay exactly one column wide.
    fig.savefig(pdf, dpi=600)
    fig.savefig(png, dpi=400)
    plt.close(fig)
    return pdf, png


def main():
    ap = argparse.ArgumentParser(description="single-column F1 re-plot")
    ap.add_argument("--height", type=float, default=1.86,
                    help="canvas height in inches (width is fixed at one column)")
    ap.add_argument("--install", action="store_true",
                    help="copy the result over paper/figures/"
                         "fig_onesweep_phase_map.pdf")
    args = ap.parse_args()

    pdf, png = fig_phase_map_singlecol(height_in=args.height)
    print("built %s" % os.path.relpath(pdf, _ROOT))
    print("built %s" % os.path.relpath(png, _ROOT))
    if args.install:
        dst = os.path.join(PAPER_FIGS, "fig_onesweep_phase_map.pdf")
        shutil.copyfile(pdf, dst)
        print("installed -> %s" % os.path.relpath(dst, _ROOT))


if __name__ == "__main__":
    main()
