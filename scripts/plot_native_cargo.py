"""M2 artifact — native fem_rigid cargo (no coupler): dynamic-vs-frozen + GIF.

The deformable cube's elastic modes `a` are a NATIVE modal block of Solver6DOF
(two_band_coupling.html, Approach B), co-solved with the rigid bodies + the slab
mode `q` in one backward-Euler step (the augmented q-block). This artifact drops
the cube on the reduced-modal slab and plots, for the dynamic run vs the frozen-q̇
counterfactual: the cube COM height, the cube's elastic energy (the deformation),
and the slab's modal ring energy (the two-way back-reaction). A skinned GIF shows
the cube flexing (exaggerated) while the slab rings beneath it.

GIF (not MP4): no ffmpeg in this environment; Pillow writes GIF with no new deps
(CLAUDE.md). Run: `.venv/bin/python scripts/plot_native_cargo.py [--device cuda:0]`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scenes.reduced_fem_rigid_cargo import build_cargo_scene, cube_state_world

OUT = Path("docs/avbd_native")
EXAG = 300.0


def run(freeze: bool, n_steps: int, device: str, capture: bool = False):
    h = build_cargo_scene("fem_rigid", solver="native", device=device,
                          freeze_qdot=freeze, drop_height=0.04, spin=6.0,
                          n_elastic=6, device_resident=(device != "cpu"))
    s = h.world._solver
    t, com_y, cube_E, slab_E, pen = ([] for _ in range(5))
    cube_frames, slab_frames = [], []
    for step in range(n_steps):
        h.world.step()
        z = cube_state_world(h)
        a = z[7:]
        adot = s.cargo_adot(h.avbd_idx)
        # cube elastic energy ½ȧᵀȧ + ½aᵀΩ²a (mass-normalized modes)
        cE = 0.5 * float(adot @ adot) + 0.5 * float(a @ (h.cube.omega2 * a))
        # slab modal KINETIC energy (support block) — the ring is in the KE; the
        # static-deflection PE is present in both dynamic and frozen and would mask
        # the two-way signature.
        qd = s._qdot_modal_host
        sE = 0.5 * float(qd @ s._Mq @ qd)
        # lowest cube corner depth below the slab rest top (penetration proxy)
        R = _quat_R(s.orientations()[h.avbd_idx])
        p = s.positions()[h.avbd_idx]
        corners = (h.cube.corner_body @ R.T) + p
        depth = max(0.0, h.support_top - float(corners[:, 1].min()))
        t.append(step / 120.0); com_y.append(float(p[1]))
        cube_E.append(cE); slab_E.append(sE); pen.append(depth)
        if capture:
            cube_frames.append(h.cube.deformed_surface(z, exaggerate=EXAG))
            dy = h.rs.U_points[:, 1, :] @ h.rs.q
            supp = h.rs.point_positions_rest.copy(); supp[:, 1] += dy * 300.0
            slab_frames.append(supp)
    return dict(t=np.array(t), com_y=np.array(com_y), cube_E=np.array(cube_E),
                slab_E=np.array(slab_E), pen=np.array(pen), handle=h,
                cube_frames=cube_frames, slab_frames=slab_frames)


def _quat_R(q_xyzw):
    x, y, z, w = (float(q_xyzw[0]), float(q_xyzw[1]), float(q_xyzw[2]), float(q_xyzw[3]))
    n = x * x + y * y + z * z + w * w
    if n < 1e-30:
        return np.eye(3)
    s = 2.0 / n
    return np.array([
        [1 - s * (y * y + z * z), s * (x * y - z * w), s * (x * z + y * w)],
        [s * (x * y + z * w), 1 - s * (x * x + z * z), s * (y * z - x * w)],
        [s * (x * z - y * w), s * (y * z + x * w), 1 - s * (x * x + y * y)]])


def make_plot(dyn, frz, path: Path):
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    ax[0, 0].plot(dyn["t"], dyn["com_y"], lw=1.6, label="dynamic")
    ax[0, 0].plot(frz["t"], frz["com_y"], "--", lw=1.2, label="frozen q̇≡0")
    ax[0, 0].set_title("cube COM height (m)")
    ax[0, 1].plot(dyn["t"], dyn["cube_E"], lw=1.6, label="dynamic")
    ax[0, 1].plot(frz["t"], frz["cube_E"], "--", lw=1.2, label="frozen q̇≡0")
    ax[0, 1].set_title("cube elastic energy (J) — the deformation")
    ax[1, 0].plot(dyn["t"], dyn["slab_E"], lw=1.6, label="dynamic")
    ax[1, 0].plot(frz["t"], frz["slab_E"], "--", lw=1.2, label="frozen q̇≡0")
    ax[1, 0].set_title("slab modal KINETIC energy (J) — two-way ring")
    ax[1, 1].plot(dyn["t"], dyn["pen"] * 1e3, lw=1.6, label="dynamic")
    ax[1, 1].set_title("cube penetration (mm) — zero = no interpenetration")
    for a in ax.ravel():
        a.set_xlabel("t (s)"); a.legend(); a.grid(alpha=0.3)
    fig.suptitle("Native fem_rigid cargo (no coupler) — augmented (q_support, a_cube)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print("wrote", path)


def make_gif(dyn, path: Path):
    try:
        from matplotlib.animation import FuncAnimation, PillowWriter
    except Exception as e:
        print("skip GIF:", e); return
    cf, sf = dyn["cube_frames"], dyn["slab_frames"]
    if not cf:
        return
    h = dyn["handle"]
    fig = plt.figure(figsize=(6, 5)); axp = fig.add_subplot(111, projection="3d")
    faces = h.cube.surf_faces

    def draw(i):
        axp.clear()
        cv = cf[i]
        axp.plot_trisurf(cv[:, 0], cv[:, 2], cv[:, 1], triangles=faces,
                         color="tab:orange", alpha=0.9, edgecolor="none")
        sv = sf[i]
        axp.scatter(sv[:, 0], sv[:, 2], sv[:, 1], s=2, c="tab:blue", alpha=0.4)
        axp.set_xlim(-0.18, 0.18); axp.set_ylim(-0.18, 0.18); axp.set_zlim(-0.02, 0.18)
        axp.set_title(f"native fem_rigid cargo  t={dyn['t'][i]:.2f}s (flex ×{EXAG:.0f})")

    step = max(1, len(cf) // 90)
    anim = FuncAnimation(fig, draw, frames=range(0, len(cf), step), interval=50)
    anim.save(path, writer=PillowWriter(fps=20))
    print("wrote", path)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--steps", type=int, default=220)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("dynamic ...")
    dyn = run(False, args.steps, args.device, capture=True)
    print("frozen ...")
    frz = run(True, args.steps, args.device, capture=False)
    make_plot(dyn, frz, OUT / "m2_native_fem_rigid_cargo.png")
    make_gif(dyn, OUT / "m2_native_fem_rigid_cargo.gif")
    print(f"  dyn peak cube elastic E = {dyn['cube_E'].max():.3e} J  "
          f"frozen = {frz['cube_E'].max():.3e} J")
    print(f"  dyn peak slab ring E    = {dyn['slab_E'].max():.3e} J  "
          f"frozen = {frz['slab_E'].max():.3e} J")
    print(f"  max penetration dyn/frz = {dyn['pen'].max()*1e3:.4f} / "
          f"{frz['pen'].max()*1e3:.4f} mm")


if __name__ == "__main__":
    main()
