#!/usr/bin/env python3
"""fix_rowindex_legend.py -- bbox-preserving legibility repair for F2.

CONTEXT. F2 (`fig_onesweep_rowindex.pdf`) is included in the paper as

    \\includegraphics[trim=0 60 0 30,clip,width=0.92\\textwidth]{...}

so its MediaBox (1005.84 x 457.864 pt) is load-bearing: the trim values are
absolute offsets into that box and they crop away the graphic's own title and
footer bands. The figure therefore CANNOT be re-canvassed without also editing
its include line, which is outside the current remit. It also cannot move to a
single column: three panels, each carrying a three-line readout, a note box, an
eight-entry legend and an inset, do not survive a 3.35 in width.

WHAT THIS SCRIPT DOES (the part that is safe). Two defects are fixable WITHOUT
touching the MediaBox, because only artists that stick out past the axes set the
tight bounding box, and every artist changed here lives strictly inside a panel:

  1. OCCLUSION (fixed here). The right panel's legend sits at "lower right" and
     physically covers the third line of that panel's own readout box,
     "BE-weight injects here: shelf 7/9, ledge 5/9". Two measured numbers are
     unreadable on the printed page. The legend moves to the empty upper-right
     corner of that panel, which carries no markers: the injecting (open) points
     of the matched panel sit well below the top of the shared y range, which is
     set by the other two panels.

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO. The in-panel type (readouts at 7.6,
notes at 8.0, legends at 6.0 to 7.6 pt) prints at 2.8 to 3.5 pt after the 0.461
page shrink, and it cannot be repaired from inside the panels. Raising those
sizes was tried and measured: at 10.5 pt the middle panel's readout runs under
the iteration-decay inset and the right panel's legend runs under its note box,
because the panels are already packed at the current sizes. Type on this figure
is a canvas-size problem, and the canvas is pinned by the paper's absolute trim.
Fixing it properly needs a re-canvassed figure AND dropping trim/clip from its
include line, which is a second .tex edit outside the current remit.

NO DATA PATH IS DUPLICATED. The figure is built by calling
`make_figs.fig_rowindex()` itself, with `make_figs._save` temporarily replaced
so the Figure object is handed back instead of written. Every number, marker and
axis comes from the tracked harness unchanged; this script only re-positions and
re-sizes text that is already there. `make_figs.py` is not modified on disk.

The script asserts the output MediaBox still equals the original's before it
will install, so a silent break of the trim is impossible.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/fix_rowindex_legend.py
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mpl-onesweep-")
import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402

import make_figs                                             # noqa: E402

OUT = os.path.join(_HERE, "out")
PAPER_FIGS = os.path.join(_ROOT, "paper", "figures")

# The MediaBox the paper's trim=0 60 0 30 is measured against, in PostScript
# points, as reported by pdfinfo on the shipped figure.
REQUIRED_MEDIABOX = (1005.84, 457.864)
MEDIABOX_TOL = 0.75            # pt; font metrics can wobble the tight bbox

# The page shrink for this figure is 465.79047 / (1005.84 * 1.00375) = 0.4614.
# No font size is changed: see the module docstring for why in-panel sizes
# cannot be raised without creating new overlaps.


def build_figure():
    """Run make_figs.fig_rowindex() but keep the Figure instead of saving it."""
    grabbed = {}

    def _grab(fig, stem):
        grabbed["fig"] = fig
        grabbed["stem"] = stem
        return None, None

    real_save = make_figs._save
    try:
        make_figs._save = _grab
        make_figs.fig_rowindex()
    finally:
        make_figs._save = real_save
    return grabbed["fig"], grabbed["stem"]


def repair(fig):
    """Interior-only repair. Nothing here can move the tight bounding box.

    Exactly one change: the right panel's legend moves from "lower right", where
    it covers the third line of that panel's own readout, to "upper right",
    which is empty. Font sizes, marker sizes, axes, data and every other artist
    are left exactly as make_figs.py drew them.
    """
    axR = fig.axes[2]
    legR = axR.get_legend()
    if legR is None:
        raise RuntimeError("right panel has no legend: t4_matched.csv missing? "
                           "make_figs.fig_rowindex draws panel C only when the "
                           "matched-arm CSV is present.")
    legR.set_loc("upper right")
    return fig


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true",
                    help="copy over paper/figures/fig_onesweep_rowindex.pdf "
                         "(only if the MediaBox check passes)")
    args = ap.parse_args()

    fig, stem = build_figure()
    repair(fig)

    pdf = os.path.join(OUT, stem + "_legendfix.pdf")
    png = os.path.join(OUT, stem + "_legendfix.png")
    fig.savefig(pdf, bbox_inches="tight")          # same call as make_figs._save
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("built %s" % os.path.relpath(pdf, _ROOT))

    # Hard gate: the paper's absolute trim is only valid against this MediaBox.
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader                       # noqa: F401
        except ImportError:
            PdfReader = None
    if PdfReader is not None:
        box = PdfReader(pdf).pages[0].mediabox
        got = (float(box.width), float(box.height))
    else:
        import subprocess
        txt = subprocess.run(["pdfinfo", pdf], capture_output=True,
                             text=True).stdout
        line = [l for l in txt.splitlines() if l.startswith("Page size")][0]
        got = tuple(float(v) for v in line.split(":")[1].split("pts")[0]
                    .split("x"))
    dw = abs(got[0] - REQUIRED_MEDIABOX[0])
    dh = abs(got[1] - REQUIRED_MEDIABOX[1])
    print("MediaBox %.3f x %.3f  (required %.3f x %.3f, delta %.3f / %.3f)"
          % (got[0], got[1], REQUIRED_MEDIABOX[0], REQUIRED_MEDIABOX[1], dw, dh))
    ok = dw <= MEDIABOX_TOL and dh <= MEDIABOX_TOL
    if not ok:
        print("REFUSING to install: the MediaBox moved, so the paper's "
              "trim=0 60 0 30 would crop the wrong region.")
        sys.exit(1)
    if args.install:
        dst = os.path.join(PAPER_FIGS, "fig_onesweep_rowindex.pdf")
        shutil.copyfile(pdf, dst)
        print("installed -> %s" % os.path.relpath(dst, _ROOT))


if __name__ == "__main__":
    main()
