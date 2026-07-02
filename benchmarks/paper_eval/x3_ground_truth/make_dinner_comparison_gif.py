#!/usr/bin/env python3
"""X3 — DINNER-TABLE side-by-side GIF: full-FEM GT vs the native modal method.

The recognizable "dinner is served" scene: a pot dropped on a table set with
plates and candles. Left = full-FEM ground truth, right = the native modal
constraint (both a modal reduction / integration of the SAME table operator).
Objects are drawn as clean procedural dinner shapes (pot = squat cylinder,
plates = thin disks, candles = thin cylinders with a flame) riding the deforming
table; the pot falls at true scale then presses into the table.

Scale honesty (captioned): the table's true deflection is a few millimetres on a
1.2 m table, so the vertical DEFORMATION is exaggerated ×EXAG to be visible;
object footprints and the pot's fall are true scale. Native drawn at h=1/480.

The slow full-FEM GT is cached to <scratch>/dinner_gt.npz so the render can be
iterated cheaply (delete it or pass --fresh to recompute).

Out: docs/paper_eval/x3_dinner_gt_vs_native.gif
"""
from __future__ import annotations

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x3_ground_truth.dinner_scene_gt import (
    run_dinner_gt, run_dinner_native, DINNER,
)

OUT_GIF = os.path.join(_ROOT, "docs", "paper_eval", "x3_dinner_gt_vs_native.gif")
CACHE = os.path.join(os.environ.get("TMPDIR", "/tmp"), "dinner_gt.npz")
CACHE = "/tmp/claude-1000/-home-nan-Desktop-DCR/f8ea4cb4-913d-4e83-ab95-c5716fd7f611/scratchpad/dinner_gt.npz"

L, W, TOP = DINNER.length, DINNER.width, DINNER.top
EXAG = 12.0
T0, T1, FPS = -0.03, 0.42, 30
COMMON_T = np.arange(T0, T1, 1.0 / 240.0)


# --------------------------------------------------------------------------- #
# procedural dinner-object geometry (world axes x,y,z with y up → plot X,Y,Z   #
# mapped X=x, Y=z, Z=y)                                                        #
# --------------------------------------------------------------------------- #
def _cylinder(cx, cz, y0, y1, rx, rz, n=20, cap_top=True, cap_bot=True):
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    px, pz = cx + rx * np.cos(th), cz + rz * np.sin(th)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append([(px[i], pz[i], y0), (px[j], pz[j], y0),
                      (px[j], pz[j], y1), (px[i], pz[i], y1)])   # side quad
    if cap_top:
        faces.append([(px[i], pz[i], y1) for i in range(n)])
    if cap_bot:
        faces.append([(px[i], pz[i], y0) for i in range(n)])
    return faces


def _cone(cx, cz, y0, y1, r, n=12):
    th = np.linspace(0, 2 * np.pi, n, endpoint=False)
    px, pz = cx + r * np.cos(th), cz + r * np.sin(th)
    tip = (cx, cz, y1)
    return [[(px[i], pz[i], y0), (px[(i + 1) % n], pz[(i + 1) % n], y0), tip]
            for i in range(n)]


# --------------------------------------------------------------------------- #
def _surf_at(field_row_grid, gx, gz, x, z):
    """Bilinear-ish sample of the surface deflection grid (NXG,NZG) at (x,z)."""
    ix = np.clip(np.searchsorted(gx, x) - 1, 0, len(gx) - 2)
    iz = np.clip(np.searchsorted(gz, z) - 1, 0, len(gz) - 2)
    tx = (x - gx[ix]) / (gx[ix + 1] - gx[ix])
    tz = (z - gz[iz]) / (gz[iz + 1] - gz[iz])
    f = field_row_grid
    return float((1 - tx) * (1 - tz) * f[ix, iz] + tx * (1 - tz) * f[ix + 1, iz]
                 + (1 - tx) * tz * f[ix, iz + 1] + tx * tz * f[ix + 1, iz + 1])


def _resample(t_src, F, t_common):
    out = np.empty((t_common.size, F.shape[1]))
    for j in range(F.shape[1]):
        out[:, j] = np.interp(t_common, t_src, F[:, j],
                              left=F[0, j], right=F[-1, j])
    return out


def _resample1(t_src, y, t_common):
    return np.interp(t_common, t_src, y, left=y[0], right=y[-1])


def _load():
    fresh = "--fresh" in sys.argv
    if not fresh and os.path.exists(CACHE):
        print(f"[cache] loading GT from {CACHE}", flush=True)
        d = np.load(CACHE, allow_pickle=True)
        gt = {k: d[k] for k in d.files}
    else:
        print("[GT] full-FEM dinner (slow) …", flush=True)
        gt = run_dinner_gt()
        np.savez(CACHE, **{k: v for k, v in gt.items()
                           if isinstance(v, np.ndarray)})
    print("[native] modal dinner …", flush=True)
    nv = run_dinner_native(num_modes=20, n_frames=int(0.55 * 480), h=1.0 / 480.0)
    return gt, nv


def main():
    gt, nv = _load()
    gx, gz = gt["gx"], gt["gz"]
    NXG, NZG = len(gx), len(gz)
    mid = (NXG // 2) * NZG + (NZG // 2)

    gt_f = gt["field"] - np.median(gt["field"][:10], axis=0)
    gt_t = gt["times"] - gt["times"][int(np.argmax(np.abs(gt_f[:, mid])))]
    gtF = _resample(gt_t, gt_f, COMMON_T)
    gt_pot = _resample1(gt_t, gt["pot_y"], COMMON_T)

    nv_f = nv["field"]
    nv_traw = np.arange(nv_f.shape[0]) / 480.0
    nv_t = nv_traw - nv_traw[int(np.argmax(np.abs(nv_f[:, mid])))]
    nvF = _resample(nv_t, nv_f, COMMON_T)
    nv_pot = _resample1(nv_t, nv["pot_y"], COMMON_T)

    defl_max = EXAG * max(np.abs(gt_f).max(), np.abs(nv_f).max())
    Xg, Zg = np.meshgrid(gx, gz, indexing="ij")
    ph = DINNER.pot_half

    z_lo = TOP - defl_max - 0.03
    z_hi = TOP + ph[1] * 2 + DINNER.pot_drop * 0.55 + 0.05
    z_rng = z_hi - z_lo

    fig = plt.figure(figsize=(12.5, 5.6))
    fig.suptitle('"Dinner is served" — full-FEM ground truth  vs  native modal '
                 f'constraint   (table deformation ×{EXAG:.0f}; pot fall true '
                 'scale; impact-aligned)', fontsize=10.5)
    axL = fig.add_subplot(1, 2, 1, projection="3d")
    axR = fig.add_subplot(1, 2, 2, projection="3d")
    panels = [(axL, "full-FEM ground truth", "Oranges", "#8a5a2b", gtF, gt_pot),
              (axR, "native modal method (20 modes)", "Oranges", "#8a5a2b",
               nvF, nv_pot)]

    def add_obj(ax, faces, color, ec="k", lw=0.3, alpha=1.0):
        ax.add_collection3d(Poly3DCollection(faces, facecolor=color,
                                             edgecolor=ec, linewidths=lw,
                                             alpha=alpha))

    def draw(i):
        for ax, title, cmap, tablecol, F, poty in panels:
            ax.clear()
            grid = F[i].reshape(NXG, NZG)
            surf = TOP + EXAG * grid
            ax.plot_surface(Xg, Zg, surf, color=tablecol, rstride=1, cstride=1,
                            linewidth=0.1, edgecolor="#5c3c1c", alpha=0.95,
                            shade=True)

            def s_at(x, z):
                return TOP + EXAG * _surf_at(grid, gx, gz, x, z)

            # plates (thin bright disks with a dark rim, riding the table; a
            # small lift + rim makes them read against the wood).
            for k, (px, pz) in enumerate(DINNER.plate_xz):
                base = s_at(px, pz) + 0.004
                add_obj(ax, _cylinder(px, pz, base, base + 3 * DINNER.plate_half[1],
                                      DINNER.plate_half[0], DINNER.plate_half[2], n=26),
                        DINNER.plate_colors[k], ec="0.15", lw=0.7)
            # candles (tall thin cylinders + flame) riding the table.
            for k, (cx, cz) in enumerate(DINNER.candle_xz):
                base = s_at(cx, cz)
                top = base + 2 * DINNER.candle_half[1]
                add_obj(ax, _cylinder(cx, cz, base, top, DINNER.candle_half[0],
                                      DINNER.candle_half[2], n=14),
                        DINNER.candle_colors[k], ec="0.3", lw=0.3)
                add_obj(ax, _cone(cx, cz, top, top + 0.03, 0.008, n=10),
                        "#ff9a1f", ec="none", alpha=0.95)
            # pot: falls at true scale, then presses into the (exaggerated) table.
            pot_bottom_true = poty[i] - ph[1]
            s_pot = s_at(0.0, 0.0)
            landed = pot_bottom_true <= TOP + 0.006
            y0 = s_pot if landed else pot_bottom_true
            add_obj(ax, _cylinder(0.0, 0.0, y0, y0 + 2 * ph[1], ph[0], ph[2], n=26),
                    "#2a2622", ec="k", lw=0.4)
            # arrow to the table.
            ax.quiver(-L * 0.12, -W * 1.25, TOP + 0.10, L * 0.10, W * 0.8, -0.09,
                      color="#5c3c1c", lw=2, arrow_length_ratio=0.3)
            ax.text(-L * 0.16, -W * 1.5, TOP + 0.12, "table: compare\ndeformation",
                    color="#5c3c1c", fontsize=8, ha="center")
            ax.text2D(0.5, 0.97, title, transform=ax.transAxes, ha="center",
                      fontsize=10)
            ax.set_xlim(-L / 2, L / 2)
            ax.set_ylim(-W / 2 - 0.05, W / 2 + 0.05)
            ax.set_zlim(z_lo, z_hi)
            ax.set_box_aspect((L, W, z_rng))
            ax.set_xlabel("x [m]", fontsize=8)
            ax.set_ylabel("z [m]", fontsize=8)
            ax.set_zticks([])
            ax.view_init(elev=26, azim=-58)
            ax.tick_params(labelsize=7)
        axL.text2D(0.02, 0.04, f"t = {COMMON_T[i]*1e3:+5.0f} ms",
                   transform=axL.transAxes, fontsize=10, fontfamily="monospace")

    print(f"[render] {COMMON_T.size} frames @ {FPS} fps (EXAG=×{EXAG:.0f}) …",
          flush=True)
    anim = FuncAnimation(fig, draw, frames=COMMON_T.size, blit=False)
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    anim.save(OUT_GIF, writer=PillowWriter(fps=FPS))
    plt.close(fig)
    print(f"wrote {OUT_GIF}", flush=True)


if __name__ == "__main__":
    main()
