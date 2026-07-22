#!/usr/bin/env python3
"""Teaser: one shelf impact, three arms, one frozen instant + the invariant.

Three true-scale renders of the SAME frame of the SAME scene from the SAME
locked camera -- ungoverned, governed, and the host's own
high-iteration self-reference (500x1) -- above the energy trace that
instant is taken from.

The third panel is the point of the figure. A two-panel "off broken / on
fixed" image would claim trajectory recovery, which the paper measures and
disproves, so the reference panel stays. The impactor's own rebound is left
visible in all three panels: it is rigid-side, and the bound governs modal
storage only.

Reads only out/teaser_<case>.npz written by record_teaser.py.

Run:
  .venv/bin/python benchmarks/paper_fig/fig_teaser.py               # PDF
  .venv/bin/python benchmarks/paper_fig/fig_teaser.py --preview     # big PNG
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib
import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import PALETTE, apply_style, OUT
from benchmarks.paper_fig.render3d import (
    Camera, Renderer, assert_layering_valid, box_corners, slab_top)

SUPPORT_THICKNESS = 0.03
BOARD_COLOR = (0.76, 0.72, 0.63)

# Locked camera: a low three-quarter view down the board so the profile (and
# so the sag) reads while all five books and the impact point stay in frame.
# One camera for every panel -- a comparison whose panels differ in framing
# is not a comparison.
CAM = dict(eye=(1.00, 0.40, 0.62), target=(-0.05, 0.065, 0.0), fov_deg=34.0)

ARMS = ("off", "on", "ref")
ARM_COLOR = {"off": PALETTE["clamp_off"], "on": PALETTE["native"],
             "ref": "#333333"}
ARM_LABEL = {"off": "ungoverned", "on": "governed (containment)",
             "ref": "XPBD self-reference"}


def _eng(v: float) -> str:
    """Readable joules: thousands separated, three significant figures."""
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}"


def _load(case):
    npz = np.load(os.path.join(OUT, f"teaser_{case}.npz"))
    with open(os.path.join(OUT, f"teaser_{case}.manifest.json")) as fh:
        man = json.load(fh)
    return npz, man


def frame_bounds(cam, npz, man, frame, aspect, margin=0.06):
    """NDC limits covering every arm's geometry at `frame`, aspect-corrected.

    Computed over ALL arms at once so the three panels share one framing.
    """
    pts = [np.array([[sx * 0.4, 0.015 + sy * SUPPORT_THICKNESS, sz * 0.15]
                     for sx in (-1, 1) for sy in (-1, 0) for sz in (-1, 1)])]
    for arm in ARMS:
        pos, quat = npz[f"{arm}/pos"][frame], npz[f"{arm}/quat"][frame]
        for i, b in enumerate(man["bodies"]):
            pts.append(box_corners(b["half"], pos[i], quat[i]))
    xy, _ = cam.project(np.vstack(pts))
    x0, y0 = xy.min(axis=0)
    x1, y1 = xy.max(axis=0)
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    hw, hh = 0.5 * (x1 - x0) * (1 + margin), 0.5 * (y1 - y0) * (1 + margin)
    # grow the short axis so the on-screen scale is metrically equal in both
    if hw / hh < aspect:
        hw = hh * aspect
    else:
        hh = hw / aspect
    return (cx - hw, cx + hw), (cy - hh, cy + hh)


def render_arm(ax, npz, man, arm, frame, *, aspect, xlim, ylim,
               ghost_min_mm=2.0, annotate=True):
    """One panel: arm `arm` at absolute frame `frame`."""
    cam = Camera(aspect=aspect, **CAM)
    r = Renderer(cam)
    nx, nz = man["grid"]
    r.add_slab_seamless(slab_top(npz["support_rest"], npz["support_Uy"],
                                 npz[f"{arm}/q"][frame]),
                        nx, nz, SUPPORT_THICKNESS, BOARD_COLOR)
    pos, quat = npz[f"{arm}/pos"][frame], npz[f"{arm}/quat"][frame]
    settle = int(npz[f"{arm}/settle"])
    p0, q0 = npz[f"{arm}/pos"][settle - 1], npz[f"{arm}/quat"][settle - 1]
    top_pts = slab_top(npz["support_rest"], npz["support_Uy"],
                       npz[f"{arm}/q"][frame])
    assert_layering_valid(
        np.array([[pos[i, 0], pos[i, 1] - b["half"][1], pos[i, 2]]
                  for i, b in enumerate(man["bodies"])]), top_pts)
    moved = np.linalg.norm(pos - p0, axis=1) * 1e3
    for i, b in enumerate(man["bodies"]):
        # silhouette only where it says something, and only for BYSTANDERS:
        # the impactor's own descent is the input, not a result
        if moved[i] > ghost_min_mm and not b["is_impactor"]:
            r.add_box_wire(b["half"], p0[i], q0[i], color="0.58", lw=0.36,
                           ls=(0, (1.6, 1.3)), alpha=0.95)
        r.add_box(b["half"], pos[i], quat[i], b["color"],
                  edge=(0.22, 0.22, 0.22))
    r.draw(ax, xlim=xlim, ylim=ylim, lw=0.22)

    if annotate:
        rise = (pos[:, 1] - p0[:, 1]) * 1e3
        by = [i for i, b in enumerate(man["bodies"]) if not b["is_impactor"]]
        k = int(max(by, key=lambda i: rise[i]))
        if rise[k] > 3.0:
            xy, _ = cam.project(pos[k] + np.array([0.0, b["half"][1], 0.0]))
            dy = 0.10 * (ylim[1] - ylim[0])
            ax.annotate(f"+{rise[k]:.0f} mm", xy=(xy[0], xy[1]),
                        xytext=(xy[0], xy[1] + dy), ha="center",
                        fontsize=5.4, color=ARM_COLOR[arm],
                        arrowprops=dict(arrowstyle="-", lw=0.45,
                                        color=ARM_COLOR[arm],
                                        shrinkA=0.5, shrinkB=1.0))
    return ax


def _schematic(fig, y0, y1):
    """The plan's Fig. 1 schematic: existing XPBD rigid body + a small modal
    vector -> one shared contact row per support -> a fixed local budget K.
    Drawn as a thin strip of boxes and arrows in figure-fraction coords."""
    import matplotlib.patches as mp
    ax = fig.add_axes([0.02, y0, 0.96, y1 - y0]); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    boxes = [(0.005, 0.30, "XPBD rigid\nbody", "#f0f0f0"),
             (0.185, 0.135, "$+\\;\\mathbf{q}\\in\\mathbb{R}^{16}$", None),
             (0.40, 0.30, "shared\ncontact rows", "#fde9d9"),
             (0.72, 0.28, "fixed $K$\niterations", "#fdecec")]
    for (x, w, txt, fc) in boxes:
        if fc is not None:
            ax.add_patch(mp.FancyBboxPatch(
                (x, 0.14), w, 0.72, boxstyle="round,pad=0.01",
                linewidth=0.6, edgecolor="0.4", facecolor=fc))
        ax.text(x + w / 2, 0.5, txt, ha="center", va="center", fontsize=5.6)
    for x0, x1 in [(0.345, 0.395), (0.705, 0.715)]:
        ax.annotate("", xy=(x1, 0.5), xytext=(x0, 0.5),
                    arrowprops=dict(arrowstyle="->", lw=0.7, color="0.35"))


def build(case, frame_logged, *, figsize):
    npz, man = _load(case)
    settle = int(npz["off/settle"])
    frame = settle + int(frame_logged)
    h = float(man["h"])
    W, H = figsize
    fig = plt.figure(figsize=figsize)

    # explicit inch-space layout (figure fractions), so panel aspect is exact
    pad_l, pad_r, gap = 0.02, 0.02, 0.03
    pw = (W - pad_l - pad_r - 2 * gap) / 3.0
    # panel height chosen so the aspect ~ the scene's own (wide and short):
    # any taller and the frame is padded with empty space, which on a
    # column-width teaser is space the text needs back
    ph = 0.66
    # reserve extra top room (0.50") for the schematic strip added below
    p_bot = (H - 0.50 - ph) / H
    _schematic(fig, p_bot + ph / H + 0.045, 0.955)
    tr_bot, tr_h = 0.28 / H, 0.40 / H
    aspect = pw / ph

    cam = Camera(aspect=aspect, **CAM)
    xlim, ylim = frame_bounds(cam, npz, man, frame, aspect)

    peaks = man["peaks"]
    for j, arm in enumerate(ARMS):
        ax = fig.add_axes([(pad_l + j * (pw + gap)) / W, p_bot,
                           pw / W, ph / H])
        render_arm(ax, npz, man, arm, frame, aspect=aspect,
                   xlim=xlim, ylim=ylim)
        ax.set_axis_on()
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_linewidth(0.4)
            sp.set_color("0.72")
        ax.set_title(ARM_LABEL[arm], fontsize=6.6, color=ARM_COLOR[arm],
                     pad=2.0, fontweight="bold")
        ax.text(0.5, -0.035, f"peak $E_{{\\rm mod}}$ "
                             f"{_eng(peaks[arm]['e_mod_peak_J'])} J",
                transform=ax.transAxes, ha="center", va="top",
                fontsize=5.6, color="0.32")

    # ---- the invariant, with the rendered instant marked ----------------
    axe = fig.add_axes([0.125, tr_bot, 0.855, tr_h])
    t = (np.arange(npz["off/e_mod"].shape[0]) - settle) * h
    for arm in ARMS:
        axe.semilogy(t, np.maximum(npz[f"{arm}/e_mod"], 1e-4),
                     color=ARM_COLOR[arm], lw=0.95,
                     ls="-" if arm != "ref" else (0, (3.5, 1.5)),
                     label=ARM_LABEL[arm].replace("XPBD self-reference",
                                                  "XPBD self-ref."),
                     zorder=3 if arm == "off" else 2)
    axe.semilogy(t, np.maximum(npz["on/supply"], 1e-4), color="0.5", lw=0.8,
                 ls=(0, (1.1, 1.1)), zorder=1,
                 label=r"budget $\eta\sum\max(\Delta E_{\rm rig},0)$")
    axe.axvline(frame_logged * h, color="0.2", lw=0.7, zorder=4)
    e_off, e_on = npz["off/e_mod"][frame], npz["on/e_mod"][frame]
    axe.annotate(f"{e_off:,.0f} J", xy=(frame_logged * h, e_off),
                 xytext=(4.5, 3.5), textcoords="offset points",
                 fontsize=5.4, color=ARM_COLOR["off"], zorder=5)
    axe.annotate(f"{e_on:,.2f} J", xy=(frame_logged * h, e_on),
                 xytext=(4.5, -6.5), textcoords="offset points",
                 fontsize=5.4, color=ARM_COLOR["on"], zorder=5)
    axe.set_xlim(0.0, t[-1])
    top = float(max(npz["off/e_mod"].max(), npz["on/supply"].max())) * 3.2
    axe.set_ylim(1e-2, top)
    axe.set_xlabel("time after settling [s]", labelpad=1.0, fontsize=6.6)
    axe.set_ylabel(r"$E_{\mathrm{mod}}$ [J]", labelpad=1.2, fontsize=6.6)
    axe.tick_params(length=2, pad=1.2, labelsize=5.8)
    # no legend: the three curves carry the panel colours directly above them,
    # so only the supply needs naming, and it is named where it runs
    i_lab = settle + int(0.16 * (npz["on/supply"].shape[0] - settle))
    axe.annotate("budget, Eq. (2)",
                 xy=((i_lab - settle) * h, float(npz["on/supply"][i_lab]) * 2.2),
                 fontsize=5.3, color="0.42", ha="left", va="bottom")
    for sp in axe.spines.values():
        sp.set_linewidth(0.5)
    fig.text(0.5, 1.0 - 0.008,
             f"same initial state, camera, instant and scale  "
             f"($t={frame_logged * h:.2f}$ s after settling; true scale)",
             ha="center", va="top", fontsize=5.6, color="0.35")
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="deployed")
    ap.add_argument("--frame", type=int, default=50, help="logged frame index")
    ap.add_argument("--width", type=float, default=3.4)
    ap.add_argument("--height", type=float, default=2.05)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--name", default="fig_teaser")
    ap.add_argument("--eye", default=None, help="camera eye 'x,y,z' (tuning)")
    ap.add_argument("--target", default=None, help="camera target 'x,y,z'")
    ap.add_argument("--fov", type=float, default=None)
    args = ap.parse_args()
    if args.eye:
        CAM["eye"] = tuple(float(v) for v in args.eye.split(","))
    if args.target:
        CAM["target"] = tuple(float(v) for v in args.target.split(","))
    if args.fov:
        CAM["fov_deg"] = float(args.fov)
    apply_style()
    matplotlib.rcParams["axes.grid"] = False
    fig = build(args.case, args.frame, figsize=(args.width, args.height))
    os.makedirs(OUT, exist_ok=True)
    if args.preview:
        path = os.path.join(OUT, f"{args.name}_preview.png")
        fig.savefig(path, dpi=320)
    else:
        path = os.path.join(OUT, f"{args.name}.pdf")
        fig.savefig(path)
        fig.savefig(os.path.join(OUT, f"{args.name}.png"), dpi=240)
    plt.close(fig)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
