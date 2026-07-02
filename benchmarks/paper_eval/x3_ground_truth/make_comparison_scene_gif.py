#!/usr/bin/env python3
"""X3 — side-by-side RENDERED SCENE GIF: full-FEM GT vs the native modal method.

A 3D render of the actual scene: the slab as a deforming plate (surface colored
by deflection), the impactor and bystander as real boxes resting on it, GT on the
left and the native modal constraint on the right, impact-aligned. An arrow
points at each slab to draw the eye to the deformation being compared.

Scale honesty: the true surface deflection is sub-millimetre on a 1 m slab, so
every vertical DEVIATION FROM REST (slab surface, impactor, bystander) is scaled
by a single common factor `EXAG` (printed + captioned) — the boxes stay coherent
with the surface they ride. Horizontal geometry and box footprints are true size.
Native is drawn at h=1/480 (above Nyquist for the ~81 Hz ring, near-converged
amplitude; see docs/paper_eval/x3.md X3-B for the paper-step amplitude).

Out: docs/paper_eval/x3_gt_vs_native_scene.gif
Run: .venv/bin/python benchmarks/paper_eval/x3_ground_truth/make_comparison_scene_gif.py
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

from benchmarks.paper_eval.x3_ground_truth.scene_and_gt import (
    run_ground_truth, run_native, SLAB, SCENE,
)

OUT_GIF = os.path.join(_ROOT, "docs", "paper_eval", "x3_gt_vs_native_scene.gif")

L, W, TH = SLAB.length, SLAB.width, SLAB.thickness
TOP = SLAB.support_top
NXG, NZG = 25, 13                       # slab surface render grid
GX = np.linspace(-L / 2, L / 2, NXG)
GZ = np.linspace(-W / 2, W / 2, NZG)
GRID_XZ = [(float(x), float(z)) for x in GX for z in GZ]   # row-major (x outer)

IMP_X = SCENE.impactor_x
BY_X = SCENE.bystander_xs[0]
IH = SCENE.impactor_half
BH = SCENE.bystander_half
EXAG = 70.0                              # vertical deviation-from-rest scale

# impact-aligned timeline, 240 Hz samples, 30 fps playback
T0, T1, FPS = -0.02, 0.34, 30
COMMON_T = np.arange(T0, T1, 1.0 / 240.0)


def _impact_shift(t, mid):
    return t - t[int(np.argmax(np.abs(mid)))]


def _resample_field(t_src, field_src, t_common):
    out = np.empty((t_common.size, field_src.shape[1]))
    for j in range(field_src.shape[1]):
        out[:, j] = np.interp(t_common, t_src, field_src[:, j],
                              left=field_src[0, j], right=field_src[-1, j])
    return out


def _resample_1d(t_src, y_src, t_common):
    return np.interp(t_common, t_src, y_src, left=y_src[0], right=y_src[-1])


def _box_faces(cx, cz, cy, hx, hz, hy):
    """6 quad faces of an axis-aligned box centred at (cx,cz,cy) — world axes
    mapped (x=length, z=width, y=up) → plot (X=x, Y=z, Z=y)."""
    xs = [cx - hx, cx + hx]
    zs = [cz - hz, cz + hz]
    ys = [cy - hy, cy + hy]
    c = [(xs[i], zs[j], ys[k]) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    # vertex index: i*4 + j*2 + k
    def v(i, j, k):
        return c[i * 4 + j * 2 + k]
    return [
        [v(0, 0, 0), v(0, 1, 0), v(0, 1, 1), v(0, 0, 1)],   # x-
        [v(1, 0, 0), v(1, 1, 0), v(1, 1, 1), v(1, 0, 1)],   # x+
        [v(0, 0, 0), v(1, 0, 0), v(1, 0, 1), v(0, 0, 1)],   # z-
        [v(0, 1, 0), v(1, 1, 0), v(1, 1, 1), v(0, 1, 1)],   # z+
        [v(0, 0, 0), v(1, 0, 0), v(1, 1, 0), v(0, 1, 0)],   # y-
        [v(0, 0, 1), v(1, 0, 1), v(1, 1, 1), v(0, 1, 1)],   # y+ (top)
    ]


def main():
    print("### X3 rendered-scene GIF — GT vs native ###", flush=True)

    print("[GT] full-FEM (surface grid) …", flush=True)
    gt = run_ground_truth(h_fine=5e-5, probe_defl_xz=GRID_XZ, record_every=20)
    gt_u = gt["probe_defl"] - np.median(gt["probe_defl"][:10], axis=0)
    mid_col = (NXG // 2) * NZG + (NZG // 2)
    gt_t = _impact_shift(gt["times"], gt_u[:, mid_col])
    gtU = _resample_field(gt_t, gt_u, COMMON_T)
    gt_imp = _resample_1d(gt_t, gt["pot_y"], COMMON_T)
    gt_by = _resample_1d(gt_t, gt["plate_ys"][:, 0], COMMON_T)

    print("[native] modal constraint (surface grid) …", flush=True)
    nv = run_native(solver="avbd", num_modes=16, probe_defl_xz=GRID_XZ,
                    n_frames=int(0.55 * 480), relax=1.0, h=1.0 / 480.0)
    nv_u = nv["u_field"]
    nv_traw = np.arange(nv_u.shape[0]) / 480.0
    nv_t = _impact_shift(nv_traw, nv_u[:, mid_col])
    nvU = _resample_field(nv_t, nv_u, COMMON_T)
    nv_imp = _resample_1d(nv_t, nv["imp_y"], COMMON_T)
    nv_by = _resample_1d(nv_t, nv["by_y"][:, 0], COMMON_T)

    # Vertical axis is TRUE metres. Only the slab-surface deflection and the
    # bodies' vertical DISPLACEMENT-from-rest are exaggerated ×EXAG; box SIZES
    # stay true, so the boxes sit coherently on the visibly-deforming plate.
    rest_imp = TOP + IH[1]              # impactor box centre at rest (bottom on slab)
    rest_by = TOP + BH[1]
    defl_max = EXAG * max(np.abs(gt_u).max(), np.abs(nv_u).max())    # ~m
    z_lo = TOP - defl_max - 0.02
    z_hi = TOP + 2 * IH[1] + defl_max + 0.03   # top of impactor riding the ring
    z_rng = z_hi - z_lo

    Xg, Zg = np.meshgrid(GX, GZ, indexing="ij")

    fig = plt.figure(figsize=(12, 5.4))
    fig.suptitle("Rendered scene — full-FEM ground truth  vs  native modal "
                 f"constraint   (slab deformation ×{EXAG:.0f} to be visible; "
                 "boxes true size; impact-aligned)", fontsize=11)
    axL = fig.add_subplot(1, 2, 1, projection="3d")
    axR = fig.add_subplot(1, 2, 2, projection="3d")
    panels = [
        (axL, "full-FEM ground truth", "k", "Greys", gtU, gt_imp, gt_by),
        (axR, "native modal method (16 modes)", "C3", "Reds", nvU, nv_imp, nv_by),
    ]

    zmid = NZG // 2                    # z=0 column of the surface grid

    def draw(i):
        for ax, title, edge, cmap, U, impy, byy in panels:
            ax.clear()
            field = U[i].reshape(NXG, NZG)
            surf = TOP + EXAG * field                        # true metres
            ax.plot_surface(Xg, Zg, surf, cmap=cmap,
                            vmin=TOP - defl_max, vmax=TOP + defl_max,
                            rstride=1, cstride=1, linewidth=0.15,
                            edgecolor=edge, alpha=0.9, antialiased=True)
            # Boxes ride the (exaggerated) deforming surface at their footprint:
            # bottom glued to the slab top, true box size on top. The impactor
            # presses into the dip it creates; the bystander rides the ring.
            row = field[:, zmid]                             # u_y(x) at z=0
            imp_top = TOP + EXAG * float(np.interp(IMP_X, GX, row))
            by_top = TOP + EXAG * float(np.interp(BY_X, GX, row))
            ax.add_collection3d(Poly3DCollection(
                _box_faces(IMP_X, 0.0, imp_top + IH[1], IH[0], IH[2], IH[1]),
                facecolor="#1f77b4", edgecolor="k", alpha=0.85, linewidths=0.6))
            ax.add_collection3d(Poly3DCollection(
                _box_faces(BY_X, 0.0, by_top + BH[1], BH[0], BH[2], BH[1]),
                facecolor="#2ecc40", edgecolor="k", alpha=1.0, linewidths=0.8))
            ax.text(IMP_X, 0.0, imp_top + 2 * IH[1] + 0.02, "impactor\n(drives)",
                    color="#1f77b4", fontsize=7.5, ha="center", va="bottom")
            ax.text(BY_X, 0.0, by_top + 2 * BH[1] + 0.05, "bystander\n(responds)",
                    color="#188a2e", fontsize=7.5, ha="center", va="bottom")
            # arrow pointing at the slab deformation.
            ax.quiver(-L * 0.15, -W * 1.3, TOP + 0.11, L * 0.12, W * 0.9, -0.10,
                      color=edge, lw=2, arrow_length_ratio=0.3)
            ax.text(-L * 0.2, -W * 1.5, TOP + 0.13, "slab: compare\ndeformation",
                    color=edge, fontsize=8, ha="center")
            ax.text2D(0.5, 0.97, title, transform=ax.transAxes, ha="center",
                      fontsize=10)
            ax.set_xlim(-L / 2, L / 2)
            ax.set_ylim(-W, W)
            ax.set_zlim(z_lo, z_hi)
            ax.set_box_aspect((L, 2 * W, z_rng))
            ax.set_xlabel("x [m]", fontsize=8)
            ax.set_ylabel("z [m]", fontsize=8)
            ax.set_zticks([])
            ax.view_init(elev=20, azim=-62)
            ax.tick_params(labelsize=7)
        axL.text2D(0.02, 0.04, f"t = {COMMON_T[i]*1e3:+5.0f} ms",
                   transform=axL.transAxes, fontsize=10, fontfamily="monospace")

    print(f"[render] {COMMON_T.size} frames @ {FPS} fps  (EXAG=×{EXAG:.0f}) …",
          flush=True)
    anim = FuncAnimation(fig, draw, frames=COMMON_T.size, blit=False)
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    anim.save(OUT_GIF, writer=PillowWriter(fps=FPS))
    plt.close(fig)
    print(f"wrote {OUT_GIF}", flush=True)


if __name__ == "__main__":
    main()
