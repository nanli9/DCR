#!/usr/bin/env python3
"""X3 — side-by-side GIF: full-FEM ground truth vs the native modal method.

Renders the slab's TOP-SURFACE deflection profile u_y(x, t) [mm] along the
z=0 centre-line, GT on the left and the native modal constraint on the right,
impact-aligned on a shared timeline. The impactor (▼, the driver) and the
bystander (■, the responder) are drawn riding the deflected surface, so the
two-way coupling is visible: the impactor pushes the surface down and its
ring lifts/rocks the distant bystander — the SAME field in both panels.

Real units (mm) — no exaggeration; the point is that native Φ(x)·q reproduces
the full-FEM deforming surface. Native is drawn at h=1/480 (above Nyquist for
the ~81 Hz ring and near the converged amplitude; see docs/paper_eval/x3.md
X3-B for the paper-step amplitude story).

Out: docs/paper_eval/x3_gt_vs_native.gif
Run: .venv/bin/python benchmarks/paper_eval/x3_ground_truth/make_comparison_gif.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x3_ground_truth.scene_and_gt import (
    run_ground_truth, run_native, SLAB, SCENE,
)

OUT_GIF = os.path.join(_ROOT, "docs", "paper_eval", "x3_gt_vs_native.gif")

L = SLAB.length
NX = 61
XS = np.linspace(-L / 2, L / 2, NX)
SWEEP = [(float(x), 0.0) for x in XS]
IMP_X = SCENE.impactor_x
BY_X = SCENE.bystander_xs[0]

# shared impact-aligned timeline. Sample at 240 Hz (~3 frames per 81 Hz ring
# period ⇒ the oscillation renders smoothly, not aliased) and play at 30 fps.
T0, T1, FPS = -0.04, 0.40, 30
COMMON_T = np.arange(T0, T1, 1.0 / 240.0)


def _impact_shift(t, mid):
    return t - t[int(np.argmax(np.abs(mid)))]


def _resample(t_src, field_src, t_common):
    """Interpolate each x-column of field_src (n_src, NX) onto t_common."""
    out = np.empty((t_common.size, field_src.shape[1]))
    for j in range(field_src.shape[1]):
        out[:, j] = np.interp(t_common, t_src, field_src[:, j],
                              left=0.0, right=field_src[-1, j])
    return out


def _surf_at(field_row, x):
    return float(np.interp(x, XS, field_row))


def main():
    print("### X3 GIF — GT vs native side by side ###", flush=True)

    # --- GT (dense surface sweep) ---
    print("[GT] full-FEM …", flush=True)
    gt = run_ground_truth(h_fine=5e-5, probe_defl_xz=SWEEP, record_every=20)
    gt_u = (gt["probe_defl"] - np.median(gt["probe_defl"][:10], axis=0)) * 1e3
    gt_t = _impact_shift(gt["times"], gt_u[:, NX // 2])
    gtU = _resample(gt_t, gt_u, COMMON_T)

    # --- native (dense surface sweep, h=1/480) ---
    print("[native] modal constraint …", flush=True)
    nv = run_native(solver="avbd", num_modes=16, probe_defl_xz=SWEEP,
                    n_frames=int(0.7 * 480), relax=1.0, h=1.0 / 480.0)
    nv_u = nv["u_field"] * 1e3
    nv_t = _impact_shift(np.arange(nv_u.shape[0]) / 480.0, nv_u[:, NX // 2])
    nvU = _resample(nv_t, nv_u, COMMON_T)

    ylim = 1.15 * max(np.abs(gtU).max(), np.abs(nvU).max())

    # --- figure ---
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    fig.suptitle("Slab surface deflection u_y(x)  —  full-FEM ground truth  vs  "
                 "native modal constraint\n(z=0 centre-line, real mm; ▼ impactor "
                 "drives, ■ bystander responds — same field, both panels)",
                 fontsize=10)
    for ax, title in ((axL, "full-FEM ground truth"),
                      (axR, "native modal method (16 modes)")):
        ax.set_xlim(-L / 2, L / 2)
        ax.set_ylim(-ylim, ylim)
        ax.axhline(0, color="0.7", lw=0.8)
        ax.set_xlabel("x  [m]")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)
    axL.set_ylabel("surface deflection  u_y  [mm]")

    (lineL,) = axL.plot([], [], "k-", lw=2)
    (lineR,) = axR.plot([], [], "C3-", lw=2)
    fillL = fillR = None
    impL, = axL.plot([], [], "kv", ms=12, mfc="C0")
    impR, = axR.plot([], [], "kv", ms=12, mfc="C0")
    byL, = axL.plot([], [], "ks", ms=11, mfc="C2")
    byR, = axR.plot([], [], "ks", ms=11, mfc="C2")
    txt = axL.text(0.02, 0.94, "", transform=axL.transAxes, fontsize=10,
                   va="top", fontfamily="monospace")

    def _draw(ax, prev_fill, xs, u, color):
        if prev_fill is not None:
            prev_fill.remove()
        return ax.fill_between(xs, u, -ylim, color=color, alpha=0.12)

    def update(i):
        nonlocal fillL, fillR
        uL, uR = gtU[i], nvU[i]
        lineL.set_data(XS, uL)
        lineR.set_data(XS, uR)
        fillL = _draw(axL, fillL, XS, uL, "k")
        fillR = _draw(axR, fillR, XS, uR, "C3")
        impL.set_data([IMP_X], [_surf_at(uL, IMP_X)])
        impR.set_data([IMP_X], [_surf_at(uR, IMP_X)])
        byL.set_data([BY_X], [_surf_at(uL, BY_X)])
        byR.set_data([BY_X], [_surf_at(uR, BY_X)])
        txt.set_text(f"t = {COMMON_T[i]*1e3:+6.0f} ms")
        return lineL, lineR, impL, impR, byL, byR, txt

    print(f"[render] {COMMON_T.size} frames @ {FPS} fps …", flush=True)
    anim = FuncAnimation(fig, update, frames=COMMON_T.size, blit=False)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    anim.save(OUT_GIF, writer=PillowWriter(fps=FPS))
    plt.close(fig)
    print(f"wrote {OUT_GIF}", flush=True)


if __name__ == "__main__":
    main()
