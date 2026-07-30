#!/usr/bin/env python3
"""One-sweep teaser: same scene, same budget, same instant, one row weight apart.

Two stacked true-scale renders of ONE frozen instant of ONE recorded scene, from
ONE locked camera, at true scale. The two panels are independent runs of the
shipped position-based host from identical build states at the same fixed budget
(1 constraint iteration x 8 substeps per 1/120 s frame). The ONLY difference is
the modal contact row's weight:

  (a) mass-shaped weight  1/M_q                     -> the resting books launch
  (b) matched charge      1/(4 M_q + h^2 K_q)       -> the resting books stay put
      i.e. mu = m(kappa^2 + b) at the host's shipped kappa = 2

NOTHING IS STAGED and nothing is re-simulated here. Every pose, every board
deflection and every joule on the page is read from the frozen recording
    out/onesweep_scene_data/onesweep_scene_traj.npz
written by onesweep_scene_record.py (git_sha e58083a), the same recording the
supplementary video plays. This script only reads, projects and labels it.

DISPLAYED INSTANT (data-driven, not chosen by eye): substep 541, the argmax over
the recorded window of the mass-shaped arm's highest bystander rise, i.e. the
instant its books are at their highest. That is 113.5 ms after the dropped
weight first touches the shelf. Both panels show that same substep: one shared
clock, so the difference on the page is the physics, not the edit.

ANNOTATED NUMBERS, all read at that substep from the npz above:
  board-mode energy   unfixed/e_modal[541] = 1707.1965 J -> "1,707 J"
                      fixed/e_modal[541]   =    0.3546 J -> "0.35 J"
  peak book rise      running max of max_b {arm}/book_rise_mm over the displayed
                      window: unfixed 56.8227 mm -> "56.8 mm",
                              fixed    5.2789 mm -> "5.3 mm"
  At this substep both running maxima already equal the FULL-RUN maxima
  recorded in scene_data_summary.json (book_rise_max_mm 56.82268 / 5.27887),
  so each annotation is at once the instant's value and the run's.

The remaining figure text comes from scene_data_summary.json: operating_point
(iterations, substeps, modal_relax, governor) and scene (impactor_mass_kg,
drop_height_m). The 125 mm clearance floor is the rotation-aware minimum
weight-to-book separation measured for the video (128.4 mm, quoted down to 125).

The joule figure is labelled board-mode energy because that is what it is: on
this shelf 99.998% of the peak total sits in the board's own modes
(act1_shelf_energy_split.json, modal_fraction_of_total 0.99998), not in the
books. It must never be read as the books' kinetic energy.

Output is a vector PDF sized for one acmart sigconf column: 3.33 x 2.35 in
(239.76 x 169.2 pt), drawn with no bbox="tight" shrink so that
\\includegraphics[width=\\columnwidth] does not rescale the type.

Run:
  .venv/bin/python benchmarks/paper_fig/fig_onesweep_teaser.py            # PDF
  .venv/bin/python benchmarks/paper_fig/fig_onesweep_teaser.py --preview  # PNG
then copy out/fig_onesweep_teaser.pdf into paper/figures/.
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

DATA_DIR = os.path.join(OUT, "onesweep_scene_data")
NPZ = os.path.join(DATA_DIR, "onesweep_scene_traj.npz")
SUMMARY = os.path.join(DATA_DIR, "scene_data_summary.json")

ARMS = ("unfixed", "fixed")
# Okabe-Ito, the same two arm colours the other paper figures and the
# supplementary video use: vermillion for the injecting arm, bluish-green for
# the matched one.
ARM_COLOR = {"unfixed": PALETTE["clamp_off"], "fixed": PALETTE["variant"]}
ARM_LABEL = {"unfixed": "mass-shaped row weight",
             "fixed": "matched row weight"}
ARM_MATH = {"unfixed": r"$w = 1/M_q$",
            "fixed": r"$w = 1/(4M_q + h^2 K_q)$"}

# The video's locked shelf camera, reused unchanged: the eye sits almost in the
# books' own plane (4.7 deg of azimuth, for depth cue only) and 8 deg above the
# board, which is what makes "a book has left the surface" legible at all and
# what makes the renderer's support-behind-bodies draw order exact.
CAM = dict(eye=(0.10, 0.255, 1.20), target=(0.00, 0.070, 0.0), fov_deg=24.0)

# Printed on white, so the video's dark theme is dropped. Steel board (the
# scene's material is steel, E = 200 GPa), light rules, dark body edges.
SUPPORT_COLOR = (0.70, 0.73, 0.78)
GRID_COLOR = "#8a919c"
GHOST_COLOR = "0.52"
SPINE_COLOR = "0.72"
INK = "0.20"
FINE = "0.36"

GHOST_MM = 3.0                 # rest-pose silhouette threshold (video's value)
GRID_Z = (0.10, 0.14)          # ruler strip, in FRONT of every body
GRID_STEP = 0.10               # 10 cm ticks: the figure's scale cue


def load():
    d = np.load(NPZ)
    with open(SUMMARY) as fh:
        summary = json.load(fh)
    return d, summary


def display_frame(d, lo: int) -> int:
    """The substep shown: peak bystander rise of the mass-shaped arm.

    Read off the recording rather than picked by eye. Both panels are drawn at
    this one substep.
    """
    r = np.asarray(d["unfixed/book_rise_mm"], float).max(axis=1)
    return lo + int(np.argmax(r[lo:]))


def rise_running_max(d, arm, lo: int, f: int) -> float:
    """Highest lift of any book so far [mm], the video's own readout."""
    r = np.asarray(d[f"{arm}/book_rise_mm"], float).max(axis=1)
    return float(np.maximum.accumulate(r[lo:f + 1])[-1])


def bounds(d, f: int, box_ratio: float, x_pad: float, margin: float = 0.05):
    """One xlim/ylim for BOTH panels: same camera, same window, same scale.

    Computed over every body corner of both arms at the displayed substep plus
    the strip of board that is shown, then padded to the panel's own
    width/height ratio so `set_aspect("equal")` fills it without distorting
    anything. A comparison whose panels differ in framing is not a comparison.
    """
    cam = Camera(aspect=1.0, **CAM)
    half = np.asarray(d["half"], float)
    pts = []
    for arm in ARMS:
        pos, quat = d[f"{arm}/pos"][f], d[f"{arm}/quat"][f]
        for i in range(half.shape[0]):
            pts.append(box_corners(half[i], pos[i], quat[i]))
    board_y = float(d["support_rest"][0, 1])
    thick = float(d["support_thickness"])
    z0 = float(d["support_rest"][:, 2].min())
    z1 = float(d["support_rest"][:, 2].max())
    body_x = np.vstack(pts)[:, 0]
    x0 = max(float(d["support_rest"][:, 0].min()), body_x.min() - x_pad)
    x1 = min(float(d["support_rest"][:, 0].max()), body_x.max() + x_pad)
    pts.append(np.array([[sx, board_y - thick, sz]
                         for sx in (x0, x1) for sz in (z0, z1)]))
    pts.append(np.array([[sx, board_y, sz]
                         for sx in (x0, x1) for sz in (z0, z1)]))
    P = np.vstack(pts)
    xy, _ = cam.project(P)
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    c = 0.5 * (lo + hi)
    hw, hh = 0.5 * (hi - lo) * (1.0 + margin)
    if hw / hh < box_ratio:
        hw = hh * box_ratio
    else:
        hh = hw / box_ratio
    xlim = [c[0] - hw, c[0] + hw]

    # The panel is much wider than the content is tall, so the ratio padding
    # above can push the window past the free end of the shelf and leave a
    # wedge of empty page inside the panel. Slide the window (never resize it,
    # so the scale is untouched) until the board's free end meets the right
    # edge, and only if every body of every arm still fits with room to spare.
    board = np.array([[float(d["support_rest"][:, 0].max()), yv, zv]
                      for yv in (board_y, board_y - thick) for zv in (z0, z1)])
    end_x = float(cam.project(board)[0][:, 0].max())
    shift = xlim[1] - end_x
    if shift > 0.0:
        cand = [xlim[0] - shift, xlim[1] - shift]
        body_xy, _ = cam.project(np.vstack(pts[:-2]))
        keep = 0.02 * (cand[1] - cand[0])
        if (body_xy[:, 0].min() > cand[0] + keep
                and body_xy[:, 0].max() < cand[1] - keep):
            xlim = cand
    return tuple(xlim), (c[1] - hh, c[1] + hh), (x0, x1)


def scale_bar(ax, d, *, length=0.10, x_frac=0.035, y_frac=0.88, verbose=False):
    """A true-scale bar, projected through the panel's own camera.

    The bar is a real segment of world space `length` metres long lying in the
    board's front plane, so its on-page length IS the projection of 10 cm at
    that depth, not a hand-drawn approximation. Its left end is solved for in
    projected coordinates (the projection is affine in world x at fixed depth,
    so two probes pin it down) which is what keeps the end tick inside the
    panel whatever window `bounds` returns.

    Drawn instead of a ruled lattice on the board: the lattice read as a
    rectangle etched into the board rather than as a scale.
    """
    cam = Camera(aspect=1.0, **CAM)
    zf = float(d["support_rest"][:, 2].max())          # front plane of the board
    yb = float(d["support_rest"][0, 1]) + 0.115
    xl, xh = ax.get_xlim()
    yl, yh = ax.get_ylim()
    probe, _ = cam.project(np.array([[0.0, yb, zf], [1.0, yb, zf]]))
    slope = probe[1, 0] - probe[0, 0]
    x_world = (xl + x_frac * (xh - xl) - probe[0, 0]) / slope
    P = np.array([[x_world, yb, zf], [x_world + length, yb, zf]])
    xy, _ = cam.project(P)
    y0 = yl + y_frac * (yh - yl)
    dy = 0.030 * (yh - yl)
    ax.plot(xy[:, 0], [y0, y0], color=GRID_COLOR, lw=0.7,
            solid_capstyle="butt", zorder=6)
    for k in (0, 1):
        ax.plot([xy[k, 0]] * 2, [y0 - dy, y0 + dy], color=GRID_COLOR, lw=0.7,
                zorder=6)
    ax.text(xy[1, 0] + 0.010 * (xh - xl), y0, f"{length * 100:.0f} cm",
            ha="left", va="center", fontsize=6.0, color=FINE, zorder=6)
    if verbose:
        w_in = (xy[1, 0] - xy[0, 0]) / (xh - xl) * ax.get_position().width \
            * ax.figure.get_figwidth()
        print(f"  scale bar: {length * 100:.0f} cm = {w_in:.3f} in on the page "
              f"at the board's front plane")


def draw_panel(ax, d, arm, f, *, xlim, ylim, lw=0.28):
    """Real boxes, real board deflection, true scale, locked camera."""
    r = Renderer(Camera(aspect=1.0, **CAM), ambient=0.52, diffuse=0.54)
    nx, nz = (int(v) for v in d["grid"])
    top = slab_top(d["support_rest"], d["support_Uy"], d[f"{arm}/q"][f])
    r.add_slab_seamless(top, nx, nz, float(d["support_thickness"]),
                        SUPPORT_COLOR)

    half = np.asarray(d["half"], float)
    color = np.asarray(d["color"], float)
    is_imp = np.asarray(d["is_impactor"], bool)
    pos, quat = d[f"{arm}/pos"][f], d[f"{arm}/quat"][f]
    ref = int(d[f"{arm}/ref_idx"])
    p0, q0 = d[f"{arm}/pos"][ref], d[f"{arm}/quat"][ref]

    # the painter's-algorithm premise (no body behind the support) is checked
    # against the DEFLECTED surface, not assumed
    bottoms = []
    for i in range(half.shape[0]):
        V = box_corners(half[i], pos[i], quat[i])
        bottoms.append(V[int(np.argmin(V[:, 1]))])
    assert_layering_valid(np.array(bottoms), top)

    moved = np.linalg.norm(pos - p0, axis=1) * 1e3
    for i in range(half.shape[0]):
        # dashed silhouette = where this book was resting before contact. The
        # dropped weight's own descent is the input, not a result, so it gets
        # none.
        if moved[i] > GHOST_MM and not is_imp[i]:
            r.add_box_wire(half[i], p0[i], q0[i], color=GHOST_COLOR, lw=0.38,
                           ls=(0, (1.7, 1.4)), alpha=0.95)
        r.add_box(half[i], pos[i], quat[i], color[i],
                  edge=(0.16, 0.17, 0.20))
    r.draw(ax, xlim=xlim, ylim=ylim, lw=lw)
    ax.set_axis_on()
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_linewidth(0.4)
        sp.set_color(SPINE_COLOR)
    return ax


def _fmt_j(v: float) -> str:
    v = float(v)
    if v >= 1000.0:
        return f"{v:,.0f} J"
    if v >= 10.0:
        return f"{v:.1f} J"
    return f"{v:.2f} J"


def text_w_in(fig, s, size, family=None, weight=None) -> float:
    """Width of `s` in inches, measured rather than guessed.

    Drawn off-canvas, measured, removed. The page budget is the binding
    constraint of this figure, so every line is checked against the column
    width instead of being hand-tuned until it looks right.
    """
    t = fig.text(0.0, -1.0, s, fontsize=size, family=family,
                 fontweight=weight)
    w = t.get_window_extent(renderer=fig.canvas.get_renderer()).width
    t.remove()
    return w / fig.dpi


def build(*, width: float, height: float, frame: int | None, verbose=True):
    d, summary = load()
    h_sub = float(d["h_sub"])
    impact = int(d["unfixed/impact_idx"])
    lo = max(0, impact - 45)                 # the video's own display window
    f = display_frame(d, lo) if frame is None else int(frame)
    t_ms = (f - impact) * h_sub * 1e3

    W, H = width, height
    fig = plt.figure(figsize=(W, H), facecolor="white")

    # ---- inch-space layout, so the panel aspect is exact ------------------
    pad_l, pad_r = 0.015, 0.015
    pw = W - pad_l - pad_r
    lab_h = 0.100                              # arm name + weight
    num_h = 0.104                              # the measured numbers
    foot = 0.325                               # operating-point strip (3 lines)
    top_pad = 0.030
    gap = 0.040                                # panel (a) to label (b)
    ph = (H - top_pad - foot - gap - 2 * (lab_h + num_h)) / 2.0
    ratio = pw / ph

    xlim, ylim, _grid_x = bounds(d, f, ratio, x_pad=0.045)

    # value columns, sized by measurement so the two panels' numbers line up
    # vertically: a comparison figure whose numbers do not align is harder to
    # read than one whose do
    N_SIZE = 6.4
    FIELDS = [("board-mode energy",
               lambda arm: _fmt_j(float(d[f"{arm}/e_modal"][f]))),
              ("peak book rise",
               lambda arm: f"{rise_running_max(d, arm, lo, f):.1f} mm")]
    w_lab = [text_w_in(fig, lab, N_SIZE) for lab, _g in FIELDS]
    w_val = [max(text_w_in(fig, g(a), N_SIZE, "monospace") for a in ARMS)
             for _lab, g in FIELDS]

    checks = []
    for j, arm in enumerate(ARMS):
        p_bot = (foot + (1 - j) * (ph + lab_h + num_h + gap)) / H
        ax = fig.add_axes([pad_l / W, p_bot, pw / W, ph / H])
        draw_panel(ax, d, arm, f, xlim=xlim, ylim=ylim)
        if arm == "fixed":
            # one scale bar for the figure, in the panel whose upper band is
            # empty by construction (its books never leave the board)
            scale_bar(ax, d, verbose=verbose)

        # Two label lines per panel, both above their own panel: the arm and its
        # weight, then the two numbers read from the recording at the displayed
        # substep. Two lines rather than one because at column width a single
        # line cannot hold both without them colliding.
        name = f"({'ab'[j]}) {ARM_LABEL[arm]}"
        y_lab = p_bot + (ph + num_h + 0.5 * lab_h) / H
        y_num = p_bot + (ph + 0.5 * num_h) / H
        fig.text(pad_l / W, y_lab, name, ha="left", va="center", fontsize=6.9,
                 color=ARM_COLOR[arm], fontweight="bold")
        w_name = text_w_in(fig, name, 6.9, weight="bold")
        fig.text((pad_l + w_name + 0.055) / W, y_lab, ARM_MATH[arm], ha="left",
                 va="center", fontsize=6.7, color=INK)
        if arm == "unfixed":
            # the silhouettes only need naming once, and this is the line a
            # reader is on while parsing the panel that has them
            fig.text(1.0 - pad_r / W, y_lab, "dashed: the books at rest",
                     ha="right", va="center", fontsize=6.0, color=FINE)
        x = pad_l
        for (lab, getter), wl, wv in zip(FIELDS, w_lab, w_val):
            fig.text(x / W, y_num, lab, ha="left", va="center",
                     fontsize=N_SIZE, color=FINE)
            fig.text((x + wl + 0.035 + wv) / W, y_num, getter(arm), ha="right",
                     va="center", fontsize=N_SIZE, color=ARM_COLOR[arm],
                     family="monospace")
            x += wl + 0.035 + wv + 0.085
        checks += [(f"{arm} name+math",
                    w_name + 0.055 + text_w_in(fig, ARM_MATH[arm], 6.7)),
                   (f"{arm} numbers", x - 0.085 - pad_l)]

    # The operating point is honesty furniture, not decoration: the effect is
    # budget-graded, so an undisclosed budget would read as rigging. The three
    # lines are carried here rather than left to the caption because a teaser is
    # read before any caption. What still does not fit (the converged scale, the
    # rebound both arms keep, the modal fraction) is carried by the caption.
    op = summary["operating_point"]
    sc = summary["scene"]
    lines = [
        (f"{op['iterations']} iteration x {op['substeps']} substeps per "
         f"1/120 s frame, modal relaxation {op['modal_relax']:.1f}, true scale"),
        (f"passivity governor off, two independent runs, {t_ms:.0f} ms after "
         f"impact"),
        (f"steel cantilever shelf, {sc['impactor_mass_kg']:.0f} kg dropped "
         f"{sc['drop_height_m']:.2f} m, never within 125 mm of a book"),
    ]
    for y, s in zip((0.236 / H, 0.141 / H, 0.046 / H), lines):
        fig.text(0.5, y, s, ha="center", va="center", fontsize=6.0, color=FINE)
        checks.append((s[:22], text_w_in(fig, s, 6.0)))

    if verbose:
        for label, w in checks:
            flag = "OK " if w <= pw else "OVER"
            print(f"  {flag} {w:5.2f} in / {pw:.2f} in   {label}")
    return fig, f, t_ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float, default=3.33)   # acmart \columnwidth
    ap.add_argument("--height", type=float, default=2.35)
    ap.add_argument("--frame", type=int, default=None,
                    help="override the data-driven displayed substep")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--name", default="fig_onesweep_teaser")
    args = ap.parse_args()

    apply_style()
    matplotlib.rcParams["axes.grid"] = False
    # exact page size: no bbox="tight" shrink-to-content, the layout above IS
    # the layout, and \includegraphics[width=\columnwidth] must not rescale it
    matplotlib.rcParams["savefig.bbox"] = None
    matplotlib.rcParams["savefig.pad_inches"] = 0.0

    fig, f, t_ms = build(width=args.width, height=args.height, frame=args.frame)
    os.makedirs(OUT, exist_ok=True)
    if args.preview:
        path = os.path.join(OUT, f"{args.name}_preview.png")
        fig.savefig(path, dpi=400, facecolor="white")
    else:
        path = os.path.join(OUT, f"{args.name}.pdf")
        fig.savefig(path, facecolor="white")
    plt.close(fig)
    print(f"wrote {path}  (substep {f}, t = {t_ms:+.1f} ms after first contact)")


if __name__ == "__main__":
    main()
