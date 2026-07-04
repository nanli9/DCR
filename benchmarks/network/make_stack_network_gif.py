#!/usr/bin/env python3
"""§N2 render — the stacked cube feels the ring of the cube under it.

Side-by-side 3D render of the multi-cube modal-network scene
(`scenes/reduced_cargo_network.py`), network OFF (left) vs ON (right), plus a
quantitative trace of the STACKED (upper-right) cube's modal amplitude |a|(t).
Each cube is drawn as its true deformed surface (`FEMRigidModalBody.deformed_
surface`), so the modal ripple is the actual `Φ·a` field; the flex is scaled by a
common EXAG (captioned) because true modal displacement is sub-millimetre.

The point of the render: with the network OFF the upper-right cube is inert (its
only contact — box-box with the base — carries no modal column); with the network
ON it ripples, funded by the ring of the base cube it rests on. The left/middle
control cubes ring in both (they sit on the modal slab).

Renderer: matplotlib 3D (Agg, headless) — the same lightweight stack as
`benchmarks/paper_eval/x3_ground_truth/make_comparison_scene_gif.py` (no viser /
browser dependency; playwright is not installed in this environment).

Out: docs/network/network_stack.gif
Run: .venv/bin/python benchmarks/network/make_stack_network_gif.py
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

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_cargo_network import build_cargo_network_scene, cube_state_world

OUT_GIF = os.path.join(_ROOT, "docs", "network", "network_stack.gif")

NAMES = ["resting", "impactor", "base", "upper"]
COLOR = {"resting": "#7f8c9b", "impactor": "#1f77b4",
         "base": "#7f8c9b", "upper": "#e8710a"}   # upper = the star
N_STEPS = 360                                       # 3.0 s at h=1/120
STRIDE = 3                                          # 40 fps → 120 render frames
FPS = 30


def simulate(network):
    """Run the scene; record each cube's config z=[p,q,a] per frame + |a_upper|."""
    h = build_cargo_network_scene(network=network)
    s = h.world._solver
    traj = {nm: [] for nm in NAMES}
    a_up = []
    for _ in range(N_STEPS):
        s.step()
        for nm in NAMES:
            traj[nm].append(cube_state_world(h, nm))
        a_up.append(float(np.linalg.norm(s.cargo_a(h.avbd_idx["upper"]))))
    return h, {nm: np.array(traj[nm]) for nm in NAMES}, np.array(a_up)


def main():
    print("### §N2 stacked-cube network GIF ###", flush=True)
    print("[sim] network OFF …", flush=True)
    hoff, toff, a_off = simulate(False)
    print("[sim] network ON  …", flush=True)
    hon, ton, a_on = simulate(True)

    cube = hon.cubes                                # body models (same geometry)
    faces = {nm: cube[nm].surf_faces for nm in NAMES}

    # Common EXAG: scale the max modal flex over the run to ~35 % of a cube.
    half = 0.05
    raw = 1e-12
    for tr in (toff, ton):
        for nm in NAMES:
            for z in tr[nm][::4]:
                a = z[7:]
                raw = max(raw, float(np.abs(cube[nm].surf_modal @ a).max()))
    EXAG = 0.6 * half / raw
    print(f"[render] max raw flex {raw*1e3:.3f} mm → EXAG ×{EXAG:.0f}", flush=True)

    frames = list(range(0, N_STEPS, STRIDE))
    tsec = np.arange(N_STEPS) / 120.0

    fig = plt.figure(figsize=(12.5, 6.6))
    fig.suptitle("Modal contact network — a stacked cube feels the ring of the "
                 f"cube under it   (modal flex ×{EXAG:.0f}; same drop both sides)",
                 fontsize=11)
    axL = fig.add_axes([0.02, 0.30, 0.42, 0.62], projection="3d")
    axR = fig.add_axes([0.46, 0.30, 0.42, 0.62], projection="3d")
    axT = fig.add_axes([0.08, 0.07, 0.84, 0.17])

    def draw_scene(ax, tr, title):
        ax.clear()
        for nm in NAMES:
            z = tr[nm][i]
            V = cube[nm].deformed_surface(z, exaggerate=EXAG)     # (Ns,3) world
            # world (x=length, y=up, z=depth) → plot (X=x, Y=z, Z=y)
            polys = [[(V[k, 0], V[k, 2], V[k, 1]) for k in f] for f in faces[nm]]
            hl = nm == "upper"
            ax.add_collection3d(Poly3DCollection(
                polys, facecolor=COLOR[nm], edgecolor="k",
                linewidths=0.5 if hl else 0.25, alpha=0.95 if hl else 0.8))
        ax.text2D(0.5, 0.98, title, transform=ax.transAxes, ha="center",
                  fontsize=10)
        ax.set_xlim(-0.40, 0.40); ax.set_ylim(-0.22, 0.22); ax.set_zlim(0.0, 0.26)
        ax.set_box_aspect((0.80, 0.44, 0.26))
        ax.set_xlabel("x [m]", fontsize=8); ax.set_zticks([])
        ax.view_init(elev=16, azim=-70); ax.tick_params(labelsize=7)

    def draw_trace():
        axT.clear()
        axT.plot(tsec[:i + 1], a_off[:i + 1] * 1e6, color="#7f8c9b", lw=1.6,
                 label="network OFF (upper cube inert)")
        axT.plot(tsec[:i + 1], a_on[:i + 1] * 1e6, color="#e8710a", lw=1.8,
                 label="network ON (upper cube rings)")
        axT.set_xlim(0, tsec[-1]); axT.set_ylim(0, max(a_on.max() * 1e6 * 1.1, 1e-3))
        axT.set_xlabel("time [s]", fontsize=8)
        axT.set_ylabel(r"upper cube $\|a\|$  [µ]", fontsize=8)
        axT.legend(loc="upper right", fontsize=8, framealpha=0.9)
        axT.tick_params(labelsize=7); axT.grid(alpha=0.25)

    def draw(fi):
        nonlocal i
        i = frames[fi]
        draw_scene(axL, toff, "network OFF")
        draw_scene(axR, ton, "network ON")
        draw_trace()

    i = 0
    print(f"[render] {len(frames)} frames @ {FPS} fps …", flush=True)
    anim = FuncAnimation(fig, draw, frames=len(frames), blit=False)
    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    anim.save(OUT_GIF, writer=PillowWriter(fps=FPS))
    plt.close(fig)
    print(f"wrote {OUT_GIF}", flush=True)


if __name__ == "__main__":
    main()
