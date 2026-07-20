#!/usr/bin/env python3
"""Supplementary video: what a fixed-budget contact row does to bystanders.

Four beats, all from the frozen traces written by record_teaser.py:

  1. steel board, production-like 1x8 budget -- ungoverned vs governed, side
     by side. The XPBD self-reference leaves the books alone (0.1 mm), so
     every millimetre the ungoverned run moves them is spurious.
  2. a freeze on that contrast with the measured launch heights.
  3. the paper's soft-board scene at the same 1x8 budget, three arms --
     ungoverned, governed, XPBD self-reference. Here the books legitimately
     move, and the governed arm under-moves them: bounded, not faithful.
  4. the invariant itself, with the cursor swept through the run.

Every arm is an independent run from its own reset state; nothing is toggled
mid-trajectory. The camera, framing and scale are locked across all panels
and all frames -- computed once over every frame of every arm so the view
never drifts between beats.

Run (needs ffmpeg on PATH):
  .venv/bin/python benchmarks/paper_fig/make_teaser_video.py
  .venv/bin/python benchmarks/paper_fig/make_teaser_video.py --quick
"""
from __future__ import annotations

import argparse
import json
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
import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import PALETTE, OUT
from benchmarks.paper_fig.render3d import (
    Camera, Renderer, assert_layering_valid, box_corners, slab_top)

SUPPORT_THICKNESS = 0.03
BOARD_COLOR = (0.76, 0.72, 0.63)
CAM = dict(eye=(1.00, 0.40, 0.62), target=(-0.05, 0.065, 0.0), fov_deg=34.0)

FPS = 30
W_IN, H_IN, DPI = 16.0, 9.0, 120          # 1920 x 1080
BG = "#0f1116"
FG = "#e8e8ea"
DIM = "#9aa0a8"

ARM_COLOR = {"off": PALETTE["clamp_off"], "on": PALETTE["native"],
             "ref": "#c8ccd2"}
ARM_LABEL = {"off": "ungoverned", "on": "governed",
             "ref": "XPBD self-reference (500x1)"}


def _eng(v: float) -> str:
    """Readable joules: thousands separated, three significant figures."""
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.3g}"


def _load(case):
    npz = np.load(os.path.join(OUT, f"teaser_{case}.npz"))
    with open(os.path.join(OUT, f"teaser_{case}.manifest.json")) as fh:
        man = json.load(fh)
    return npz, man


def global_bounds(cases, aspect, margin=0.06, frame_lo=None, y_max=0.245):
    """One framing for every displayed frame of every arm of every case.

    Per-frame auto-framing would make the view breathe; a comparison whose
    camera moves is not a comparison. Geometry above `y_max` is excluded so
    the impactor's 0.5 m descent does not shrink the whole scene -- the beat
    starts after it is already near the board.
    """
    cam = Camera(aspect=aspect, **CAM)
    pts = [np.array([[sx * 0.4, 0.015 + sy * SUPPORT_THICKNESS, sz * 0.15]
                     for sx in (-1, 1) for sy in (-1, 0) for sz in (-1, 1)])]
    for case in cases:
        npz, man = _load(case)
        lo = int(npz["off/settle"]) if frame_lo is None else frame_lo
        for arm in ("off", "on", "ref"):
            pos, quat = npz[f"{arm}/pos"], npz[f"{arm}/quat"]
            for i, b in enumerate(man["bodies"]):
                for f in range(lo, pos.shape[0], 2):
                    V = box_corners(b["half"], pos[f, i], quat[f, i])
                    if V[:, 1].max() <= y_max:
                        pts.append(V)
    xy, _ = cam.project(np.vstack(pts))
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    c = 0.5 * (lo + hi)
    hw, hh = 0.5 * (hi - lo) * (1 + margin)
    if hw / hh < aspect:
        hw = hh * aspect
    else:
        hh = hw / aspect
    return (c[0] - hw, c[0] + hw), (c[1] - hh, c[1] + hh)


def draw_scene(ax, npz, man, arm, frame, *, aspect, xlim, ylim):
    ax.clear()
    ax.set_facecolor(BG)
    cam = Camera(aspect=aspect, **CAM)
    r = Renderer(cam, ambient=0.46, diffuse=0.60)
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
        # silhouettes mark BYSTANDER displacement; the impactor's own descent
        # is the input, not a result, so it gets none
        if moved[i] > 2.0 and not b["is_impactor"]:
            r.add_box_wire(b["half"], p0[i], q0[i], color="#6b7280", lw=0.9,
                           ls=(0, (3, 2)), alpha=0.85)
        r.add_box(b["half"], pos[i], quat[i], b["color"],
                  edge=(0.12, 0.13, 0.16))
    r.draw(ax, xlim=xlim, ylim=ylim, lw=0.6)
    return ax


def scene_axes(fig, rect):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color("#2a2f3a")
        sp.set_linewidth(1.0)
    return ax


class Writer:
    """Sequentially numbered PNG frames for ffmpeg."""

    def __init__(self, d):
        self.d = d
        self.n = 0

    def add(self, fig, times=1):
        for _ in range(times):
            fig.savefig(os.path.join(self.d, f"f{self.n:05d}.png"),
                        dpi=DPI, facecolor=BG)
            self.n += 1


def new_fig():
    fig = plt.figure(figsize=(W_IN, H_IN), facecolor=BG)
    return fig


def card(wr, lines, seconds=3.0, sub=None):
    fig = new_fig()
    y = 0.62
    for i, (txt, size, col) in enumerate(lines):
        fig.text(0.5, y, txt, ha="center", va="center", fontsize=size,
                 color=col, family="sans-serif",
                 fontweight="bold" if i == 0 else "normal")
        y -= (size / 260.0) + 0.045
    if sub:
        fig.text(0.5, 0.13, sub, ha="center", va="center", fontsize=15,
                 color=DIM)
    wr.add(fig, times=int(seconds * FPS))
    plt.close(fig)


def beat_sim(wr, case, arms, *, xlim, ylim, aspect, title, subtitle,
             hold_end=2.0, step=1, repeat=2, annotate_launch=True,
             frame_range=None, end_note=None):
    """One comparison beat: N locked panels stepping through the run."""
    npz, man = _load(case)
    settle = int(npz["off/settle"])
    nf = npz["off/pos"].shape[0]
    lo, hi = frame_range or (settle, nf)
    h = float(man["h"])

    fig = new_fig()
    fig.text(0.5, 0.962, title, ha="center", va="center", fontsize=26,
             color=FG, fontweight="bold")
    fig.text(0.5, 0.920, subtitle, ha="center", va="center", fontsize=14,
             color=DIM)
    n = len(arms)
    pad, gap = 0.035, 0.018
    pw = (1.0 - 2 * pad - (n - 1) * gap) / n
    p_bot, p_h = 0.505, 0.345
    axes, labels = [], []
    for j, arm in enumerate(arms):
        ax = scene_axes(fig, [pad + j * (pw + gap), p_bot, pw, p_h])
        axes.append(ax)
        fig.text(pad + j * (pw + gap) + pw / 2, 0.876, ARM_LABEL[arm],
                 ha="center", va="center", fontsize=18,
                 color=ARM_COLOR[arm], fontweight="bold")
        labels.append(fig.text(pad + j * (pw + gap) + pw / 2, 0.470, "",
                               ha="center", va="center", fontsize=15,
                               color=ARM_COLOR[arm]))

    # synchronised trace under the panels: the same instant, as a number
    axt = fig.add_axes([0.075, 0.115, 0.885, 0.285])
    axt.set_facecolor(BG)
    t = (np.arange(npz["off/e_mod"].shape[0]) - settle) * h
    for arm in arms:
        axt.semilogy(t, np.maximum(npz[f"{arm}/e_mod"], 1e-4),
                     color=ARM_COLOR[arm], lw=1.8,
                     ls="-" if arm != "ref" else (0, (5, 2)),
                     label=ARM_LABEL[arm])
    axt.semilogy(t, np.maximum(npz["on/supply"], 1e-4), color="#7f8794",
                 lw=1.4, ls=(0, (1.5, 1.5)),
                 label=r"budget $\eta\sum\max(\Delta E_{\rm rig},0)$")
    axt.set_xlim((lo - settle) * h, t[-1])
    axt.set_ylim(1e-2, float(max(npz[f"{a}/e_mod"].max() for a in arms)) * 4)
    axt.set_ylabel(r"$E_{\rm mod}$ [J]", color=FG, fontsize=14)
    axt.set_xlabel("time after settling [s]", color=FG, fontsize=14)
    axt.tick_params(colors=DIM, labelsize=12)
    for sp in axt.spines.values():
        sp.set_color("#2a2f3a")
    axt.grid(True, color="#1c212b", lw=0.7)
    axt.legend(loc="upper right", fontsize=12, frameon=False, labelcolor=FG,
               ncol=len(arms) + 1, handlelength=1.6, columnspacing=1.0)
    cursor = axt.axvline((lo - settle) * h, color=FG, lw=1.4)

    tclock = fig.text(0.5, 0.045, "", ha="center", va="center", fontsize=15,
                      color=DIM, family="monospace")
    rest = {a: npz[f"{a}/pos"][settle - 1][:, 1] for a in arms}
    bystander = [i for i, b in enumerate(man["bodies"]) if not b["is_impactor"]]
    for f in range(lo, hi, step):
        for ax, arm in zip(axes, arms):
            draw_scene(ax, npz, man, arm, f, aspect=aspect,
                       xlim=xlim, ylim=ylim)
        for lab, arm in zip(labels, arms):
            e = npz[f"{arm}/e_mod"][f]
            rise = (npz[f"{arm}/pos"][f][:, 1] - rest[arm]) * 1e3
            mx = max(rise[i] for i in bystander)
            txt = f"$E_{{\\rm mod}}$ = {e:,.1f} J"
            if annotate_launch:
                txt += f"    books +{max(mx, 0.0):.0f} mm"
            lab.set_text(txt)
        cursor.set_xdata([(f - settle) * h] * 2)
        tclock.set_text(f"t = {(f - settle) * h:5.3f} s   "
                        f"independent runs from identical reset states, "
                        f"true scale")
        wr.add(fig, times=repeat)
    if end_note:
        fig.text(0.5, 0.017, end_note, ha="center", va="center", fontsize=13,
                 color=DIM)
    if hold_end:
        wr.add(fig, times=int(hold_end * FPS))
    plt.close(fig)


def beat_freeze(wr, case, arms, frame_logged, *, xlim, ylim, aspect, title,
                message, seconds=4.5):
    npz, man = _load(case)
    settle = int(npz["off/settle"])
    f = settle + frame_logged
    h = float(man["h"])
    fig = new_fig()
    fig.text(0.5, 0.958, title, ha="center", va="center", fontsize=27,
             color=FG, fontweight="bold")
    n = len(arms)
    pad, gap = 0.035, 0.018
    pw = (1.0 - 2 * pad - (n - 1) * gap) / n
    rest = {a: npz[f"{a}/pos"][settle - 1][:, 1] for a in arms}
    bystander = [i for i, b in enumerate(man["bodies"]) if not b["is_impactor"]]
    for j, arm in enumerate(arms):
        ax = scene_axes(fig, [pad + j * (pw + gap), 0.44, pw, 0.40])
        draw_scene(ax, npz, man, arm, f, aspect=aspect, xlim=xlim, ylim=ylim)
        fig.text(pad + j * (pw + gap) + pw / 2, 0.876, ARM_LABEL[arm],
                 ha="center", va="center", fontsize=18,
                 color=ARM_COLOR[arm], fontweight="bold")
        rise = (npz[f"{arm}/pos"][f][:, 1] - rest[arm]) * 1e3
        vals = sorted((rise[i] for i in bystander), reverse=True)
        fig.text(pad + j * (pw + gap) + pw / 2, 0.395,
                 f"peak $E_{{\\rm mod}}$ "
                 f"{_eng(man['peaks'][arm]['e_mod_peak_J'])} J",
                 ha="center", va="center", fontsize=17, color=ARM_COLOR[arm])
        fig.text(pad + j * (pw + gap) + pw / 2, 0.340,
                 "books  " + ", ".join(f"{v + 0.0:+.0f}".replace("-0", "+0")
                                       for v in vals) + "  mm",
                 ha="center", va="center", fontsize=15, color=DIM)
    fig.text(0.5, 0.185, message, ha="center", va="center", fontsize=19,
             color=FG, wrap=True)
    fig.text(0.5, 0.055, f"t = {frame_logged * h:.3f} s after settling",
             ha="center", va="center", fontsize=14, color=DIM,
             family="monospace")
    wr.add(fig, times=int(seconds * FPS))
    plt.close(fig)


def beat_trace(wr, case, *, title, seconds_sweep=5.0, hold=3.0):
    npz, man = _load(case)
    settle = int(npz["off/settle"])
    h = float(man["h"])
    nf = npz["off/e_mod"].shape[0]
    t = (np.arange(nf) - settle) * h
    fig = new_fig()
    fig.text(0.5, 0.945, title, ha="center", va="center", fontsize=27,
             color=FG, fontweight="bold")
    ax = fig.add_axes([0.085, 0.16, 0.875, 0.70])
    ax.set_facecolor(BG)
    for arm in ("off", "on", "ref"):
        ax.semilogy(t, np.maximum(npz[f"{arm}/e_mod"], 1e-4),
                    color=ARM_COLOR[arm], lw=2.2,
                    ls="-" if arm != "ref" else (0, (5, 2)),
                    label=ARM_LABEL[arm])
    ax.semilogy(t, np.maximum(npz["on/supply"], 1e-4), color="#7f8794", lw=1.8,
                ls=(0, (1.5, 1.5)),
                label=r"budget  $\eta\sum\max(\Delta E_{\rm rig},0)$")
    ax.set_xlim(0, t[-1])
    ax.set_ylim(1e-2, float(npz["off/e_mod"].max()) * 4)
    ax.set_xlabel("time after settling [s]", color=FG, fontsize=17)
    ax.set_ylabel(r"modal energy $E_{\rm mod}$ [J]", color=FG, fontsize=17)
    ax.tick_params(colors=DIM, labelsize=14)
    for sp in ax.spines.values():
        sp.set_color("#2a2f3a")
    ax.grid(True, which="major", color="#232833", lw=0.8)
    leg = ax.legend(loc="upper right", fontsize=15, frameon=False,
                    labelcolor=FG)
    cursor = ax.axvline(0, color=FG, lw=1.6)
    n_steps = max(1, int(seconds_sweep * FPS))
    for k in range(n_steps):
        cursor.set_xdata([t[-1] * k / (n_steps - 1)] * 2)
        wr.add(fig)
    fig.text(0.5, 0.055,
             "ungoverned rides far above the measured supply; governed stays "
             "under it. Bounded is not faithful.",
             ha="center", va="center", fontsize=17, color=FG)
    wr.add(fig, times=int(hold * FPS))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(OUT, "teaser_video.mp4"))
    ap.add_argument("--quick", action="store_true",
                    help="every 4th frame, short holds -- for iterating")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH")
    for case in ("steel", "deployed"):
        if not os.path.exists(os.path.join(OUT, f"teaser_{case}.npz")):
            raise SystemExit(f"missing out/teaser_{case}.npz -- run "
                             f"record_teaser.py --case {case} first")

    step = 4 if args.quick else 1
    repeat = 1 if args.quick else 2
    aspect_2 = ((1.0 - 2 * 0.035 - 0.018) / 2 * W_IN) / (0.345 * H_IN)
    aspect_3 = ((1.0 - 2 * 0.035 - 2 * 0.018) / 3 * W_IN) / (0.345 * H_IN)
    # start each beat with the impactor already close to the board: the 0.3 s
    # of free fall before it lands carries no information
    npz0, _ = _load("deployed")
    settle = int(npz0["off/settle"])
    START = settle + 20
    # the freeze beats use 3 panels at a slightly taller box
    aspect_3f = ((1.0 - 2 * 0.035 - 2 * 0.018) / 3 * W_IN) / (0.40 * H_IN)
    xlim2, ylim2 = global_bounds(("steel",), aspect_2, frame_lo=START)
    xlim3, ylim3 = global_bounds(("deployed",), aspect_3, frame_lo=START)
    xlim3f, ylim3f = global_bounds(("steel", "deployed"), aspect_3f,
                                   frame_lo=START)
    RANGE = (START, npz0["off/pos"].shape[0])
    # From logged frame 66 the ungoverned soft-board run drives a book clean
    # through the board (>5 mm below the deflected surface). That is a real
    # symptom of the same truncation energy, but a painter's-algorithm
    # renderer cannot depth-order a body inside the support honestly, so the
    # soft-board beat stops before it and says so on screen.
    RANGE_SOFT = (START, settle + 64)

    tmp = tempfile.mkdtemp(prefix="teaser_video_")
    wr = Writer(tmp)
    try:
        card(wr, [
            ("How much energy does a modal contact row inject?", 34, FG),
            ("A cross-formulation measurement and a cumulative storage bound",
             19, DIM)],
            seconds=1.5 if args.quick else 3.5,
            sub="position-based (XPBD) host  ·  shelf scene  ·  "
                "1 iteration x 8 substeps per frame  ·  CPU, float64")

        card(wr, [
            ("A steel board should barely move.", 32, FG),
            ("Converged, the resting books rise 0.1 mm.", 21, DIM),
            ("At a production-like interactive budget, they are launched.",
             21, ARM_COLOR["off"])],
            seconds=1.0 if args.quick else 3.0,
            sub="steel shelf  ·  1x8  ·  relaxation 0.7  ·  eta = 1")

        beat_sim(wr, "steel", ("off", "on"), xlim=xlim2, ylim=ylim2,
                 aspect=aspect_2, step=step, repeat=repeat,
                 hold_end=0.6 if args.quick else 2.0,
                 frame_range=RANGE,
                 title="steel board, 1 iteration x 8 substeps",
                 subtitle="same scene, same budget, same instant - the only "
                          "difference is whether the storage bound is enforced")
        beat_freeze(wr, "steel", ("off", "on", "ref"), 36,
                    xlim=xlim3f, ylim=ylim3f, aspect=aspect_3f,
                    title="the launch is spurious",
                    message="the self-reference leaves the books within "
                            "0.1 mm of rest: every millimetre the ungoverned "
                            "run moves them is truncation energy",
                    seconds=1.5 if args.quick else 5.0)

        card(wr, [
            ("On the paper's soft board, the books are supposed to move.",
             28, FG),
            ("So the bound has something legitimate to suppress.", 21, DIM)],
            seconds=1.0 if args.quick else 3.0,
            sub="shelf, E = 0.5 GPa  ·  1x8  ·  relaxation 0.7")

        beat_sim(wr, "deployed", ("off", "on", "ref"), xlim=xlim3, ylim=ylim3,
                 aspect=aspect_3, step=step, repeat=repeat,
                 hold_end=0.6 if args.quick else 2.0,
                 frame_range=RANGE_SOFT,
                 end_note="window ends at 0.53 s: past it the ungoverned run "
                          "drives a book through the board, which this "
                          "renderer cannot depth-order honestly",
                 title="soft board, 1 iteration x 8 substeps",
                 subtitle="ungoverned, governed, and the host's own "
                          "high-iteration self-reference - three independent runs")
        beat_freeze(wr, "deployed", ("off", "on", "ref"), 50,
                    xlim=xlim3f, ylim=ylim3f, aspect=aspect_3f,
                    title="bounded, but not faithful",
                    message="the bound removes the spurious launch and takes "
                            "the legitimate motion with it: the governed books "
                            "under-move the reference",
                    seconds=1.5 if args.quick else 5.5)

        beat_trace(wr, "deployed", title="the invariant",
                   seconds_sweep=1.5 if args.quick else 5.0,
                   hold=1.0 if args.quick else 3.5)

        card(wr, [
            ("Boundedness, not trajectory recovery.", 32, FG),
            ("The cumulative storage bound holds in all 90 measured cells.",
             20, DIM),
            ("What it costs contact validity is measured, not assumed.",
             20, DIM)],
            seconds=1.5 if args.quick else 4.0,
            sub="enforcement is CPU host-side; no unqualified real-time claim")

        print(f"rendered {wr.n} frames ({wr.n / FPS:.1f} s at {FPS} fps)")
        cmd = ["ffmpeg", "-y", "-framerate", str(FPS),
               "-i", os.path.join(tmp, "f%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
               "-movflags", "+faststart", args.out]
        subprocess.run(cmd, check=True, capture_output=True)
        mb = os.path.getsize(args.out) / 1e6
        print(f"wrote {args.out}  ({mb:.1f} MB, {wr.n / FPS:.1f} s)")
    finally:
        if args.keep_frames:
            print(f"frames kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
