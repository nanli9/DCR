#!/usr/bin/env python3
"""make_figs.py -- build the FOUR one-sweep paper figures from the T-suite CSVs.

Plan section 3 (`scratchpad/wf1/plan.md`); theory note
`scratchpad/onesweep_theory_note.md` (Results R2-R5). This script reads ONLY the
four CSVs already written under out/ and draws figures. It performs NO physics
recomputation: every measured quantity is a logged column. The only curves added
are THEORY overlays that state the hypothesis of the claim (the analytic sign
boundary (omega h)^2 = 1 + m/M and the collapse line y = rho - 1), plus display
normalizations that divide a logged measurement by a logged energy scale.

Figures (exactly four, plan section 3):
  F1  fig_onesweep_phase_map.pdf   <- out/t2_phasemap.csv
  F2  fig_onesweep_rowindex.pdf    <- out/t4_shipped.csv
  F3  fig_onesweep_nonmodal.pdf    <- out/t3_nonmodal.csv
  F4  fig_onesweep_ordering.pdf    <- out/t5_ordering.csv

Each figure is written as a .pdf AND a .png twin (review copy). Captions and
annotations state the hypotheses (one sweep, cold start, e = 0) and contain NO
absolute user paths.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/make_figs.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile

import numpy as np

# _ROOT sys.path pattern (run_weight_swap.py lines 46-49): repo root on path.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Writable matplotlib cache (avoids the non-writable ~/.matplotlib warning) and
# a headless backend, both set BEFORE importing pyplot.
if not os.environ.get("MPLCONFIGDIR"):
    os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mpl-onesweep-")
import matplotlib                                            # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
import matplotlib.colors as mcolors                          # noqa: E402
from matplotlib.patches import Patch                         # noqa: E402
from matplotlib.lines import Line2D                          # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Hypothesis banner reused across captions (no absolute paths).
HYP = "Hypotheses: one sweep, cold start, e = 0."

SCENE_STYLE = {                       # scene -> (marker, color)
    "shelf": ("o", "#1f77b4"),
    "ledge": ("s", "#d62728"),
    "dinner": ("^", "#2ca02c"),
}
VARIANT_STYLE = {                     # T3 variant -> (marker, color, label)
    "i_single": ("o", "#1f77b4", "i: single node + ground spring"),
    "ii_uniform": ("s", "#ff7f0e", "ii: uniform chain N=8"),
    "iii_wide": ("D", "#2ca02c", "iii: wide row (plank on 2 nodes)"),
    "iv_nonuniform": ("^", "#9467bd", "iv: nonuniform chain N=8"),
}


# --------------------------------------------------------------------------- #
# CSV loading (read-only)                                                      #
# --------------------------------------------------------------------------- #
def load_csv(name):
    path = os.path.join(OUT, name)
    if not os.path.isfile(path):
        raise FileNotFoundError("missing CSV (run the T experiment first): %s"
                                % os.path.relpath(path, _ROOT))
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def col(rows, key, dtype=float):
    return np.array([dtype(r[key]) for r in rows])


def _save(fig, stem):
    pdf = os.path.join(OUT, stem + ".pdf")
    png = os.path.join(OUT, stem + ".png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return pdf, png


# --------------------------------------------------------------------------- #
# F1 -- (omega h, m/M) phase map, both weight arms, analytic boundary overlay  #
# --------------------------------------------------------------------------- #
def fig_phase_map():
    rows = load_csv("t2_phasemap.csv")
    oh = col(rows, "omega_h")
    mm = col(rows, "m_over_M")
    z_mass = col(rows, "dE_mass_norm")     # logged dE/E- (mass arm)
    z_impl = col(rows, "dE_impl_norm")     # logged dE/E- (implicit arm)

    # Reshape the full logspace grid onto its (m/M, omega h) axes (no recompute).
    ox, ix = np.unique(oh, return_inverse=True)
    my, iy = np.unique(mm, return_inverse=True)
    Zm = np.full((my.size, ox.size), np.nan)
    Zi = np.full((my.size, ox.size), np.nan)
    Zm[iy, ix] = z_mass
    Zi[iy, ix] = z_impl

    # Shared diverging color scale (robust vmax so a few large-b cells do not
    # wash out the sign structure). RdBu_r: red = injection (dE>0), blue = passive.
    vmax = float(np.nanpercentile(np.abs(z_mass), 99))
    norm = mcolors.SymLogNorm(linthresh=1e-2, vmin=-vmax, vmax=vmax, base=10)
    cmap = plt.get_cmap("RdBu_r")

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.5), sharex=True, sharey=True)
    # analytic boundary omega h = sqrt(1 + m/M): x as a function of the y grid.
    y_curve = my
    x_curve = np.sqrt(1.0 + y_curve)

    for ax, Z, title in ((axes[0], Zm, "mass-only weight  $1/M_q$"),
                         (axes[1], Zi, r"implicit weight  $(M_q+hD_q+h^2K_q)^{-1}$")):
        pcm = ax.pcolormesh(ox, my, Z, cmap=cmap, norm=norm, shading="nearest")
        ax.plot(x_curve, y_curve, "k-", lw=1.6,
                label=r"$(\omega h)^2 = 1 + m/M$")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(r"$\omega h$")
        ax.set_title(title, fontsize=11)
        ax.set_xlim(ox.min(), ox.max())
        ax.set_ylim(my.min(), my.max())
    axes[0].set_ylabel(r"$m/M$")
    axes[0].legend(loc="lower right", fontsize=9, framealpha=0.9)
    cb = fig.colorbar(pcm, ax=axes, fraction=0.046, pad=0.02)
    cb.set_label(r"signed $\Delta E / E^-$  (SymLog)")

    fig.suptitle("One-sweep injection phase map: measured sign vs analytic "
                 "boundary", fontsize=12, y=1.02)
    fig.text(0.5, -0.04,
             "Left arm injects (red) exactly where the solid analytic curve "
             "predicts; the implicit arm is uniformly passive (blue). "
             "Hard contact. " + HYP,
             ha="center", fontsize=9)
    return _save(fig, "fig_onesweep_phase_map")


# --------------------------------------------------------------------------- #
# F2 -- shipped solver: each reconstruction against ITS OWN validated boundary #
# --------------------------------------------------------------------------- #
def fig_rowindex():
    """Two-panel refit (theory note Result 6, reconstruction-dependence addendum).

    The T4 shipped-solver cells are read once; the figure then draws each
    reconstruction against the boundary the note validates FOR THAT
    reconstruction, so the previous "unexplained disagreement" (symplectic
    dE_meas positive below rho = 1) becomes the explained midpoint shift.

    LEFT  (control): backward-Euler reconstruction dE_be vs the row danger
      index rho = L / (w_m + 2 a_tilde). The note's R4 predictor (inject iff
      rho > 1) matches sign(dE_be) on 27/27 mass-arm cells; the implicit remedy
      is passive on 9/9 cells per scene (Result 3, open markers below zero).
    RIGHT (shipped default): symplectic implicit-midpoint reconstruction
      dE_meas, which the note verifies reconstructs qdot+ = 2 dq/h at cold start
      (factor 2.000 exact in T4) and therefore deposits 4x the modal KE. Its
      injection boundary is the MIDPOINT-corrected index
      rho_mid = [L + 2 (w_row - w_r)] / (w_r + 2 a_tilde), built only from
      logged columns; inject iff rho_mid > 1 matches sign(dE_meas) on 27/27
      mass-arm cells. The implicit remedy survives only in the weakly coupled
      scene (2 (w_row - w_r) <= w_r): dinner 9/9, shelf 2/9, ledge 4/9.

    All quantities are logged columns; rho_mid is a display transform of logged
    columns (the note's Result-6 boundary), exactly as the y-axis normalization
    divides a logged energy change by a logged energy scale. No physics is
    recomputed here.
    """
    rows = load_csv("t4_shipped.csv")
    valid = [r for r in rows if str(r["valid"]) == "True"]
    prim = [r for r in valid if int(r["iterations"]) == 1]
    annex = [r for r in valid if int(r["iterations"]) != 1]
    # Reconstruction-matched weight arm (working fix, symplectic default) from the
    # T9 companion run (run_t9_matched.py). Optional: panel C is drawn only if the
    # CSV is present. Every quantity is a logged column (no physics recomputed).
    try:
        matched = [r for r in load_csv("t4_matched.csv")
                   if str(r["valid"]) == "True" and int(r["iterations"]) == 1]
    except FileNotFoundError:
        matched = []

    def e_minus(r):
        wr = float(r["w_r"]); v = float(r["v"])
        return 0.5 * (1.0 / wr) * v * v               # logged row-reduced KE scale

    def rho_be(r):                                    # note R4 boundary index
        return float(r["rho"])                        # logged L / (w_row + 2 a_tilde)

    def rho_mid(r):                                   # note Result 6 boundary index
        # inject iff L + 2 (w_row - w_r) > w_r + 2 a_tilde  ==>  rho_mid > 1.
        L = float(r["L"]); w_row = float(r["w_row"]); w_r = float(r["w_r"])
        a = float(r["a_tilde"])
        return (L + 2.0 * (w_row - w_r)) / (w_r + 2.0 * a)

    # Sign-agreement counts recomputed here from logged columns (caption honesty).
    mass = [r for r in prim if r["arm"] == "mass"]
    impl = [r for r in prim if r["arm"] == "implicit"]
    n_be_meas = sum((rho_be(r) > 1.0) == (float(r["dE_be"]) > 0.0) for r in mass)
    n_mid_meas = sum((rho_mid(r) > 1.0) == (float(r["dE_meas"]) > 0.0) for r in mass)
    impl_be_pass = {sc: sum(float(r["dE_be"]) <= 1e-12
                            for r in impl if r["scene"] == sc) for sc in SCENE_STYLE}
    impl_sym_pass = {sc: sum(float(r["dE_meas"]) <= 1e-12
                             for r in impl if r["scene"] == sc) for sc in SCENE_STYLE}
    n_per = {sc: sum(1 for r in mass if r["scene"] == sc) for sc in SCENE_STYLE}
    # Matched-arm passivity (dE_meas <= tol) under the shipped symplectic default,
    # and the BE-weight injection it repairs, both per scene (logged columns).
    matched_pass = {sc: sum(float(r["dE_meas"]) <= 1e-12
                            for r in matched if r["scene"] == sc) for sc in SCENE_STYLE}
    matched_n = {sc: sum(1 for r in matched if r["scene"] == sc) for sc in SCENE_STYLE}
    impl_sym_inj = {sc: n_per[sc] - impl_sym_pass[sc] for sc in SCENE_STYLE}
    rho_matched_max = max((float(r["rho_matched"]) for r in matched),
                          default=float("nan"))

    ncol = 3 if matched else 2
    fig, axes = plt.subplots(1, ncol, figsize=(5.6 * ncol, 5.2), sharey=True)
    axL, axM = axes[0], axes[1]
    axR = axes[2] if matched else None

    def draw_panel(ax, xfunc, ykey, xlabel, title, boundary_label):
        # scatter: mass arm filled, implicit arm open, colored + shaped by scene.
        for arm, fill in (("mass", True), ("implicit", False)):
            for scene, (mk, cvec) in SCENE_STYLE.items():
                sel = [r for r in prim if r["arm"] == arm and r["scene"] == scene]
                if not sel:
                    continue
                x = np.array([xfunc(r) for r in sel])
                y = np.array([float(r[ykey]) / e_minus(r) for r in sel])
                o = np.argsort(x)
                ax.scatter(x[o], y[o], marker=mk,
                           facecolors=(cvec if fill else "none"),
                           edgecolors=cvec, s=55, linewidths=1.4, zorder=5,
                           label="_nolegend_")
        ax.set_xscale("log")
        ax.set_yscale("symlog", linthresh=1e-2)
        ax.axvline(1.0, color="k", lw=1.1, ls="--")
        ax.axhline(0.0, color="k", lw=1.0, ls="--")
        ax.set_xlabel(xlabel, fontsize=9.5)
        ax.set_title(title, fontsize=10.5)
        # Agreement quadrants (predictor: injection iff x > 1). Green = agree.
        xlo, xhi = ax.get_xlim()
        ylo, yhi = ax.get_ylim()
        ax.add_patch(plt.Rectangle((1.0, 0.0), xhi - 1.0, yhi - 0.0,
                                   color="#2ca02c", alpha=0.06, zorder=0))
        ax.add_patch(plt.Rectangle((xlo, ylo), 1.0 - xlo, 0.0 - ylo,
                                   color="#2ca02c", alpha=0.06, zorder=0))
        ax.add_patch(plt.Rectangle((xlo, 0.0), 1.0 - xlo, yhi - 0.0,
                                   color="#d62728", alpha=0.06, zorder=0))
        ax.add_patch(plt.Rectangle((1.0, ylo), xhi - 1.0, 0.0 - ylo,
                                   color="#d62728", alpha=0.06, zorder=0))
        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)
        # The dashed vertical line at x = 1 IS the injection boundary; it is named
        # per panel by the x-axis (rho vs rho_mid), the stat box, and the legend.
        del boundary_label
        return xlo, xhi, ylo, yhi

    # LEFT: backward-Euler control, boundary rho = 1 (matches sign 27/27).
    draw_panel(axL, rho_be, "dE_be",
               r"row danger index  $\rho = L / (w_m + 2\tilde\alpha)$",
               "Backward-Euler reconstruction (control)",
               r"$\rho = 1$")
    axL.set_ylabel(r"one-substep  $\Delta E / E^-$")
    axL.text(0.03, 0.03,
             "mass arm sign vs $\\rho{>}1$: %d/%d\n"
             "implicit arm passive: dinner %d/%d, shelf %d/%d, ledge %d/%d"
             % (n_be_meas, len(mass),
                impl_be_pass["dinner"], n_per["dinner"],
                impl_be_pass["shelf"], n_per["shelf"],
                impl_be_pass["ledge"], n_per["ledge"]),
             transform=axL.transAxes, fontsize=7.6, va="bottom",
             bbox=dict(boxstyle="round", fc="white", ec="0.7", alpha=0.9))

    # MIDDLE: shipped symplectic default, boundary rho_mid = 1 (matches sign 27/27).
    draw_panel(axM, rho_mid, "dE_meas",
               r"midpoint index  "
               r"$\rho_{\mathrm{mid}} = [L + 2(w_{\mathrm{row}} - w_r)]"
               r"/(w_r + 2\tilde\alpha)$",
               "Shipped symplectic default",
               r"$\rho_{\mathrm{mid}} = 1$")
    axM.text(0.03, 0.965,
             r"symplectic: $\dot q^+ = 2\,\Delta q/h$" "\n"
             "(2x velocity, 4x modal KE)",
             transform=axM.transAxes, fontsize=8, va="top", ha="left",
             bbox=dict(boxstyle="round", fc="#fff4e6", ec="#e08a1e", alpha=0.95))
    axM.text(0.03, 0.03,
             "mass arm sign vs $\\rho_{\\mathrm{mid}}{>}1$: %d/%d\n"
             "BE-weight remedy passive: dinner %d/%d, shelf %d/%d, ledge %d/%d\n"
             "(passive only where $2(w_{\\mathrm{row}}{-}w_r)\\leq w_r$)"
             % (n_mid_meas, len(mass),
                impl_sym_pass["dinner"], n_per["dinner"],
                impl_sym_pass["shelf"], n_per["shelf"],
                impl_sym_pass["ledge"], n_per["ledge"]),
             transform=axM.transAxes, fontsize=7.6, va="bottom",
             bbox=dict(boxstyle="round", fc="white", ec="0.7", alpha=0.9))

    # Iteration-decay bridge (annex; shelf, mass, symplectic) as an inset on the
    # symplectic panel: measured dE_meas relaxes toward zero as the GS budget
    # grows, consistent with injection being a finite-sweep artifact.
    if annex:
        axin = axM.inset_axes([0.63, 0.10, 0.34, 0.26])
        s_vals = sorted(set(float(r["s"]) for r in annex))
        for sv in s_vals:
            sel = sorted([r for r in annex if abs(float(r["s"]) - sv) < 1e-30],
                         key=lambda r: int(r["iterations"]))
            if not sel:
                continue
            it = np.array([int(r["iterations"]) for r in sel])
            de = np.array([float(r["dE_meas"]) for r in sel])
            rho0 = float(sel[0]["rho"])
            axin.plot(it, de, "-o", ms=3.5, lw=1.1,
                      label=r"$\rho_0{=}%.2g$" % rho0)
        axin.axhline(0.0, color="k", lw=0.8, ls="--")
        axin.set_xlabel("iterations", fontsize=7.5)
        axin.set_ylabel(r"$\Delta E_{\mathrm{meas}}$ (J)", fontsize=7.5)
        axin.set_title("iteration decay (shelf, mass)", fontsize=7.5)
        axin.tick_params(labelsize=6.5)
        axin.legend(fontsize=6, framealpha=0.9)

    # RIGHT (C): reconstruction-matched weight mu* = m(4+b) = 4 M_q + h^2 K_q, the
    # working fix. SAME shipped symplectic reconstruction as the middle panel; the
    # ONLY change is the contact-row modal weight (run_t9_matched.py, note T7-4).
    # Plotted against the SAME host row danger index rho as the control panel (a
    # host property, logged as rho_host) so the fix is read at the identical
    # operating points where the BE-weight remedy (open, faint) injects. The
    # matched arm (filled) is passive at every host danger index; the matched
    # weight has NO injection boundary, so the bands are full-width (passive below
    # zero, injecting above). All quantities are logged columns.
    if axR is not None:
        for scene, (mk, cvec) in SCENE_STYLE.items():
            seli = [r for r in impl if r["scene"] == scene]        # BE-weight ref
            if seli:
                x = np.array([float(r["rho"]) for r in seli])
                y = np.array([float(r["dE_meas"]) / e_minus(r) for r in seli])
                o = np.argsort(x)
                axR.scatter(x[o], y[o], marker=mk, facecolors="none",
                            edgecolors=cvec, s=52, linewidths=1.2, alpha=0.5,
                            zorder=4, label="_nolegend_")
            selm = [r for r in matched if r["scene"] == scene]     # matched fix
            if selm:
                x = np.array([float(r["rho_host"]) for r in selm])
                y = np.array([float(r["dE_meas"]) / e_minus(r) for r in selm])
                o = np.argsort(x)
                axR.scatter(x[o], y[o], marker=mk, facecolors=cvec,
                            edgecolors="k", s=60, linewidths=0.8, zorder=6,
                            label="_nolegend_")
        axR.set_xscale("log")
        axR.set_yscale("symlog", linthresh=1e-2)
        axR.axhline(0.0, color="k", lw=1.0, ls="--")
        axR.set_xlabel(r"row danger index  $\rho = L/(w_m + 2\tilde\alpha)$",
                       fontsize=9.5)
        axR.set_title("Reconstruction-matched weight (working fix)", fontsize=10.5)
        xlo, xhi = axR.get_xlim(); ylo, yhi = axR.get_ylim()
        axR.add_patch(plt.Rectangle((xlo, ylo), xhi - xlo, 0.0 - ylo,
                                    color="#2ca02c", alpha=0.06, zorder=0))
        axR.add_patch(plt.Rectangle((xlo, 0.0), xhi - xlo, yhi - 0.0,
                                    color="#d62728", alpha=0.06, zorder=0))
        axR.set_xlim(xlo, xhi); axR.set_ylim(ylo, yhi)
        axR.text(0.03, 0.965,
                 r"matched: $w = 1/[m(4{+}b)]$" "\n"
                 r"$= 1/(4 M_q + h^2 K_q)$",
                 transform=axR.transAxes, fontsize=8, va="top", ha="left",
                 bbox=dict(boxstyle="round", fc="#e8f4ea", ec="#2ca02c", alpha=0.95))
        axR.text(0.03, 0.03,
                 "matched passive: dinner %d/%d, shelf %d/%d, ledge %d/%d\n"
                 r"$\rho_{\mathrm{matched}}<1$ all cells (max %.2f)" "\n"
                 "BE-weight injects here: shelf %d/%d, ledge %d/%d"
                 % (matched_pass["dinner"], matched_n["dinner"],
                    matched_pass["shelf"], matched_n["shelf"],
                    matched_pass["ledge"], matched_n["ledge"],
                    rho_matched_max,
                    impl_sym_inj["shelf"], n_per["shelf"],
                    impl_sym_inj["ledge"], n_per["ledge"]),
                 transform=axR.transAxes, fontsize=7.6, va="bottom",
                 bbox=dict(boxstyle="round", fc="white", ec="0.7", alpha=0.9))
        pc_handles = [
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#555555",
                   markeredgecolor="k", markersize=9,
                   label=r"matched $m(4{+}b)$ (filled)"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
                   markeredgecolor="#555555", markersize=9,
                   label="BE-weight (open, faint)")]
        axR.legend(handles=pc_handles, loc="lower right", fontsize=7.0,
                   framealpha=0.9)

    # Shared legend (panels 1-2): scene shape/color, arm fill, quadrant meaning.
    scene_handles = [Line2D([0], [0], marker=mk, color="w", markerfacecolor=cv,
                            markeredgecolor=cv, markersize=9, label=sc)
                     for sc, (mk, cv) in SCENE_STYLE.items()]
    arm_handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#555555",
               markeredgecolor="#555555", markersize=9, label="mass arm (filled)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor="#555555", markersize=9,
               label="BE-weight arm (open)")]
    quad_handles = [Patch(facecolor="#2ca02c", alpha=0.2, label="predictor agrees"),
                    Patch(facecolor="#d62728", alpha=0.2, label="predictor disagrees")]
    bnd_handle = [Line2D([0], [0], color="k", lw=1.1, ls="--",
                         label=r"injection boundary ($\rho=1$ / $\rho_{\rm mid}=1$)")]
    axL.legend(handles=scene_handles + arm_handles + quad_handles + bnd_handle,
               loc="upper left", fontsize=7.6, framealpha=0.9, ncol=1)

    fig.suptitle("Shipped XPBD support row: each reconstruction against its "
                 "validated boundary, and the reconstruction-matched fix",
                 fontsize=12, y=1.02)
    fig.text(0.5, -0.16,
             "Left: the backward-Euler control flips sign at the row danger index "
             "rho = 1 (mass arm 27/27; BE-weight remedy passive 9/9 per scene).\n"
             "Middle: the shipped symplectic default reconstructs qdot+ = 2 dq/h "
             "and deposits 4x the modal KE, shifting the boundary to the midpoint\n"
             "index rho_mid = 1 (mass arm 27/27); the BE-weight remedy, matched to "
             "backward Euler, now injects (passive dinner 9/9, shelf 2/9, ledge "
             "4/9).\n"
             "Right: the reconstruction-matched weight m(4+b) = 4 M_q + h^2 K_q "
             "restores passivity at every host danger index (27/27; rho_matched < "
             "1),\n"
             "at the same operating points where the BE-weight injects (open, "
             "faint). Hard contact. " + HYP,
             ha="center", fontsize=8)
    return _save(fig, "fig_onesweep_rowindex")


# --------------------------------------------------------------------------- #
# F3 -- nonmodal collapse onto y = rho - 1 (no modal basis anywhere)           #
# --------------------------------------------------------------------------- #
def fig_nonmodal():
    rows = load_csv("t3_nonmodal.csv")
    # LEGIBILITY: this figure is placed at \columnwidth (about 3.35 in), so a
    # 7.6 in canvas was shrunk 0.44x and its 8 pt labels reached the page at
    # 3.5 pt. Canvas is now sized close to the final width so the shrink is
    # about 0.65x and every label lands near 7 pt or above.
    fig, ax = plt.subplots(figsize=(5.2, 3.9))

    rho_all = col(rows, "rho")
    rho_line = np.logspace(np.log10(rho_all.min()), np.log10(rho_all.max()), 400)
    ax.plot(rho_line, rho_line - 1.0, "k-", lw=2.0, zorder=2,
            label=r"theory  $y = \rho - 1$")

    for var, (mk, cv, lab) in VARIANT_STYLE.items():
        sel = [r for r in rows if r["variant"] == var]
        if not sel:
            continue
        rho = np.array([float(r["rho"]) for r in sel])
        y = np.array([float(r["y"]) for r in sel])         # logged 2 dE w_m / v^2
        order = np.argsort(rho)
        ax.scatter(rho[order], y[order], marker=mk, facecolors="none",
                   edgecolors=cv, s=58, linewidths=1.6, zorder=4, label=lab)
        # implicit-arm companion series (all below zero): 2 dE_impl w_m / v^2.
        dEi = np.array([float(r["dE_impl"]) for r in sel])
        wm = np.array([float(r["w_m"]) for r in sel])
        y_impl = 2.0 * dEi * wm                            # v = -1 so v^2 = 1
        ax.scatter(rho[order], y_impl[order], marker=mk, facecolors=cv,
                   edgecolors=cv, s=14, alpha=0.35, zorder=3, label="_nolegend_")

    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=1e-1)
    ax.axhline(0.0, color="0.4", lw=0.9, ls=":")
    ax.axvline(1.0, color="0.4", lw=0.9, ls=":")
    # Label the crossing on the guide line itself: the previous leader arrow
    # crossed the faint implicit series and read as data.
    ax.text(1.18, -60.0, r"$\rho = 1$", fontsize=10, color="0.35",
            va="bottom", ha="left")
    ax.text(0.02, 0.055,
            "faint filled: implicit arm (all below 0)",
            transform=ax.transAxes, fontsize=9, color="0.35")

    ax.set_xlabel(r"row danger index  $\rho = L / w_m$", fontsize=11)
    ax.set_ylabel(r"collapse coordinate  $y = 2\,\Delta E\, w_m / v^2$",
                  fontsize=11)
    ax.tick_params(labelsize=10)
    ax.legend(loc="upper left", fontsize=9.5, framealpha=0.9)
    # The in-figure footnote and title were removed: both duplicated the LaTeX
    # caption, and they were the densest elements at the shrunk placement.
    return _save(fig, "fig_onesweep_nonmodal")


# --------------------------------------------------------------------------- #
# F4 -- Gauss-Seidel ordering: modal deposit vs n, both orders, (1+b)^2 gap    #
# --------------------------------------------------------------------------- #
def fig_ordering():
    rows = load_csv("t5_ordering.csv")

    def pick(M, m, b, order, converged):
        out = []
        for r in rows:
            if (abs(float(r["M"]) - M) < 1e-12 and abs(float(r["m"]) - m) < 1e-12
                    and abs(float(r["b"]) - b) < 1e-9 and r["order"] == order
                    and (str(r["converged_flag"]) == "True") == converged):
                out.append(r)
        return out

    M, m = 1.0, 1.0
    bvals = [4.0, 100.0]
    order_style = {"A": ("-", "o"), "B": ("--", "s")}
    b_color = {4.0: "#1f77b4", 100.0: "#d62728"}

    # Same legibility fix as the nonmodal figure: canvas sized near the final
    # \columnwidth placement instead of being shrunk 0.44x.
    fig, ax = plt.subplots(figsize=(5.2, 3.9))
    for b in bvals:
        for order, (ls, mk) in order_style.items():
            fin = pick(M, m, b, order, converged=False)
            fin = sorted(fin, key=lambda r: int(r["n"]))
            if not fin:
                continue
            n = np.array([int(r["n"]) for r in fin])
            D = np.array([float(r["D_modal"]) for r in fin])
            ax.plot(n, D, ls=ls, marker=mk, ms=5, lw=1.7, color=b_color[b],
                    label="order %s, b=%g" % (order, b))
            # n=1 closed-form marker (the logged n=1 value itself).
            ax.plot(n[0], D[0], marker="*", ms=15, color=b_color[b],
                    mec="k", mew=0.6, zorder=6, label="_nolegend_")
            # converged asymptote.
            conv = pick(M, m, b, order, converged=True)
            if conv:
                Dc = float(conv[0]["D_modal"])
                ax.axhline(Dc, color=b_color[b], lw=0.7, ls=":", alpha=0.7)

    # (1+b)^2 gap annotation at n=1 (D_B/D_A = (1+b)^2, note R5).
    for b in bvals:
        a1 = pick(M, m, b, "A", converged=False)
        b1 = pick(M, m, b, "B", converged=False)
        a1 = [r for r in a1 if int(r["n"]) == 1]
        b1 = [r for r in b1 if int(r["n"]) == 1]
        if a1 and b1:
            DA = float(a1[0]["D_modal"]); DB = float(b1[0]["D_modal"])
            ax.annotate("", xy=(1, DB), xytext=(1, DA),
                        arrowprops=dict(arrowstyle="<->", color=b_color[b], lw=1.2))
            # Anchor each label just under its own top (DB) so the b=4 and b=100
            # labels separate vertically instead of colliding at the shared
            # geometric-mean height.
            ax.text(1.16, DB * 0.6,
                    r"$(1+b)^2 = %.0f$" % ((1.0 + b) ** 2),
                    color=b_color[b], fontsize=9.5, va="top")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Gauss-Seidel sweeps  $n$", fontsize=11)
    ax.set_ylabel(r"modal deposit  $D$  (J)", fontsize=11)
    ax.tick_params(labelsize=10)
    ax.legend(loc="lower right", fontsize=9.5, framealpha=0.9)
    # In-figure title and footnote removed; the LaTeX caption carries both.
    return _save(fig, "fig_onesweep_ordering")


FIGS = {
    "F1": ("fig_onesweep_phase_map", fig_phase_map),
    "F2": ("fig_onesweep_rowindex", fig_rowindex),
    "F3": ("fig_onesweep_nonmodal", fig_nonmodal),
    "F4": ("fig_onesweep_ordering", fig_ordering),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="",
                    help="comma list of figures to build (F1,F2,F3,F4); "
                         "default all.")
    args = ap.parse_args()
    want = [s.strip().upper() for s in args.only.split(",") if s.strip()] \
        or list(FIGS)

    built = []
    for key in want:
        if key not in FIGS:
            print("unknown figure %r (choose from %s)" % (key, list(FIGS)))
            sys.exit(2)
        stem, fn = FIGS[key]
        pdf, png = fn()
        built.append((key, pdf, png))
        print("[%s] %s + .png" % (key, os.path.relpath(pdf, _ROOT)))

    print("\nBuilt %d figure(s):" % len(built))
    for key, pdf, png in built:
        print("  %s -> %s" % (key, os.path.basename(pdf)))


if __name__ == "__main__":
    main()
