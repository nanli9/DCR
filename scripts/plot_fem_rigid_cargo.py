"""Stage 3 artifact — fem_rigid cargo: dynamic-vs-frozen plot + skinned GIF.

Drops a soft fem_rigid cube onto the reduced-modal support and records, per
frame: cube COM height, cargo modal energy (the cube's own flex), support
modal energy, and contact penetration. Runs twice — the full dynamic two-way
constraint vs the `freeze_qdot` counterfactual (cube modal velocity held at 0)
— to show the `two_band_coupling.html` two-way signature per cargo cube:
the dynamic cube FLEXES and rings; the frozen one does not, and neither
penetrates the support.

Outputs:
  docs/avbd_native/stage3_fem_rigid_cargo.png   (quantitative dynamic-vs-frozen)
  docs/avbd_native/stage3_fem_rigid_cargo.gif   (skinned cube + support, side view)

GIF (not MP4): the environment has no ffmpeg / imageio-ffmpeg backend, and
CLAUDE.md forbids adding a dependency without written justification. imageio's
native Pillow GIF writer needs nothing new, so the visual artifact is a GIF.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from scenes.reduced_fem_rigid_cargo import build_fem_rigid_cargo, cube_state_world

OUT = ROOT / "docs" / "avbd_native"
N_GRID_X, N_GRID_Z = 21, 11


def run(freeze: bool, n_steps: int, device: str = "cpu", spin: float = 6.0,
        capture_surface: bool = False):
    """Step the scene; return per-frame diagnostics (+ skinned surfaces)."""
    h = build_fem_rigid_cargo(
        device=device, freeze_qdot=freeze, drop_height=0.04, spin=spin,
        device_resident=False)
    c, solver = h.coupler, h.world._solver
    t, com_y, cargo_E, supp_E, pen, a_norm = ([] for _ in range(6))
    cube_frames, supp_frames = [], []
    for step in range(n_steps):
        h.world.step()
        t.append(step * (1.0 / 120.0))
        com_y.append(float(solver.positions()[h.avbd_idx][1]))
        cargo_E.append(c.last_cargo_modal_KE + c.last_cargo_modal_PE)
        supp_E.append(c.last_modal_KE + c.last_modal_PE)
        pen.append(c.last_contact_residual)
        a_norm.append(float(np.linalg.norm(c.cargo_a[h.avbd_idx])))
        if capture_surface:
            z = cube_state_world(h)
            cube_frames.append(h.cube.deformed_surface(z, exaggerate=300.0))
            dy = h.rs.U_points[:, 1, :] @ h.rs.q
            supp = h.rs.point_positions_rest.copy()
            supp[:, 1] += dy * 300.0
            supp_frames.append(supp)
    return {
        "t": np.array(t), "com_y": np.array(com_y),
        "cargo_E": np.array(cargo_E), "supp_E": np.array(supp_E),
        "pen": np.array(pen), "a_norm": np.array(a_norm),
        "handle": h, "cube_frames": cube_frames, "supp_frames": supp_frames,
    }


def make_plot(dyn, frz, path: Path):
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    ax[0, 0].plot(dyn["t"], dyn["com_y"], label="dynamic", lw=1.6)
    ax[0, 0].plot(frz["t"], frz["com_y"], "--", label="frozen q̇≡0", lw=1.2)
    ax[0, 0].set_title("cube COM height (m)")
    ax[0, 0].set_xlabel("t (s)"); ax[0, 0].legend(); ax[0, 0].grid(alpha=0.3)

    ax[0, 1].plot(dyn["t"], dyn["cargo_E"], label="dynamic", lw=1.6)
    ax[0, 1].plot(frz["t"], frz["cargo_E"], "--", label="frozen q̇≡0", lw=1.2)
    ax[0, 1].set_title("cube modal energy ½ȧᵀȧ+½aᵀΩ²a (J) — the flex")
    ax[0, 1].set_xlabel("t (s)"); ax[0, 1].legend(); ax[0, 1].grid(alpha=0.3)

    ax[1, 0].plot(dyn["t"], dyn["supp_E"], label="dynamic", lw=1.6)
    ax[1, 0].plot(frz["t"], frz["supp_E"], "--", label="frozen q̇≡0", lw=1.2)
    ax[1, 0].set_title("support modal energy (J) — two-way ring")
    ax[1, 0].set_xlabel("t (s)"); ax[1, 0].legend(); ax[1, 0].grid(alpha=0.3)

    ax[1, 1].plot(dyn["t"], np.array(dyn["pen"]) * 1e3, label="dynamic", lw=1.6)
    ax[1, 1].plot(frz["t"], np.array(frz["pen"]) * 1e3, "--",
                  label="frozen q̇≡0", lw=1.2)
    ax[1, 1].set_title("contact penetration (mm) — zero = no interpenetration")
    ax[1, 1].set_xlabel("t (s)"); ax[1, 1].legend(); ax[1, 1].grid(alpha=0.3)

    fig.suptitle("Stage 3 — fem_rigid cube on reduced-modal support: "
                 "dynamic two-way constraint vs frozen counterfactual",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"wrote {path}")


def make_gif(dyn, path: Path, stride: int = 2):
    try:
        import imageio.v2 as imageio
    except Exception as e:  # pragma: no cover
        print(f"imageio unavailable ({e}); skipping GIF")
        return
    cube = dyn["handle"].cube
    faces = cube.surf_faces
    L, W = dyn["handle"].support_length, dyn["handle"].support_width
    frames = []
    cf, sf = dyn["cube_frames"], dyn["supp_frames"]
    for i in range(0, len(cf), stride):
        fig = plt.figure(figsize=(5, 4))
        ax = fig.add_subplot(111, projection="3d")
        # support deformed grid (modal flex ×300).
        sp = sf[i]
        X = sp[:, 0].reshape(N_GRID_X, N_GRID_Z)
        Y = sp[:, 1].reshape(N_GRID_X, N_GRID_Z)
        Z = sp[:, 2].reshape(N_GRID_X, N_GRID_Z)
        ax.plot_surface(X, Z, Y, alpha=0.35, color="0.6", linewidth=0)
        # skinned cube (modal flex ×300).
        verts = cf[i]
        tris = [verts[f] for f in faces]
        coll = Poly3DCollection(
            [[(v[0], v[2], v[1]) for v in tri] for tri in tris],
            alpha=0.9, facecolor=(0.30, 0.55, 0.85), edgecolor=(0.1, 0.2, 0.4),
            linewidths=0.2)
        ax.add_collection3d(coll)
        ax.set_xlim(-L / 2, L / 2); ax.set_ylim(-W / 2, W / 2)
        ax.set_zlim(-0.02, 0.18)
        ax.set_box_aspect((L, W, 0.2))
        ax.set_title(f"fem_rigid cube (flex ×300)  t={dyn['t'][i]:.2f}s",
                     fontsize=9)
        ax.view_init(elev=12, azim=-72)
        ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
        fig.tight_layout()
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
        frames.append(buf)
        plt.close(fig)
    imageio.mimsave(path, frames, duration=1000.0 * stride / 120.0, loop=0)
    print(f"wrote {path}  ({len(frames)} frames)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = 220
    print("running dynamic ...")
    dyn = run(freeze=False, n_steps=n, capture_surface=True)
    print("running frozen ...")
    frz = run(freeze=True, n_steps=n, capture_surface=False)
    make_plot(dyn, frz, OUT / "stage3_fem_rigid_cargo.png")
    make_gif(dyn, OUT / "stage3_fem_rigid_cargo.gif")
    # console summary (the two-way tell-tale).
    print(f"  dynamic peak cube modal E = {dyn['cargo_E'].max():.3e} J")
    print(f"  frozen  peak cube modal E = {frz['cargo_E'].max():.3e} J")
    print(f"  dynamic peak support E    = {dyn['supp_E'].max():.3e} J")
    print(f"  max penetration dyn/frz   = "
          f"{dyn['pen'].max()*1e3:.4f} / {frz['pen'].max()*1e3:.4f} mm")


if __name__ == "__main__":
    main()
