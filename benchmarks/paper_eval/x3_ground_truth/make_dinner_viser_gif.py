#!/usr/bin/env python3
"""X3 — DINNER-TABLE GIF rendered by the PRODUCTION viser renderer.

Uses viser's real WebGL renderer (the same one `run_reduced_dinner_viser.py`
serves) to draw the dinner scene with the decorated glTF assets (pot / plate /
candle) and a deforming wood table, then captures frames headlessly via a
Chrome client + `client.get_render(...)` and assembles a GIF. Full-FEM ground
truth (left) and the native modal method (right) are placed side by side in one
viser world so the camera and lighting are identical.

Physics comes from the X3 dinner drivers (`dinner_scene_gt.py`): both arms are
built from ONE shared `FEMModel` of the table (native = modal reduction of the
GT operator). The slow full-FEM GT is cached to <scratch>/dinner_gt.npz.

Rendering: table deformation exaggerated ×EXAG (captioned); objects ride the
table (plates/candles glued to the surface, pot falls at true scale then presses
in); native at h=1/480. Headless Chrome via playwright (system google-chrome),
software WebGL (swiftshader) — no display required.

Out: docs/paper_eval/x3_dinner_viser.gif
Run: .venv/bin/python benchmarks/paper_eval/x3_ground_truth/make_dinner_viser_gif.py
"""
from __future__ import annotations

import io
import os
import sys
import time

import numpy as np
from PIL import Image

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import viser
from playwright.sync_api import sync_playwright

from scripts.render_assets import _resolve_kind_template
from scripts.run_reduced_support_shelf_viser import _slab_faces
from benchmarks.paper_eval.x3_ground_truth.dinner_scene_gt import (
    run_dinner_gt, run_dinner_native, DINNER,
)

OUT_GIF = os.path.join(_ROOT, "docs", "paper_eval", "x3_dinner_viser.gif")
CACHE = "/tmp/claude-1000/-home-nan-Desktop-DCR/f8ea4cb4-913d-4e83-ab95-c5716fd7f611/scratchpad/dinner_gt.npz"

L, W, TOP = DINNER.length, DINNER.width, DINNER.top
RENDER_THK = 0.09                # rendered table thickness (visual only; the
#                                  physics table is DINNER.thickness=0.03)
EXAG = 6.0                        # gentle, realistic table vibration (bodies
#                                   jump at TRUE scale — the two-way kick)
XOFF = 0.82                       # half-separation of the two arms in world x
T0, T1 = -0.10, 0.52             # show the pot descend + the plates launch
NFRAMES = int(os.environ.get("X3_NFRAMES", "150"))   # captured frames (smooth)
RES_H, RES_W = 1080, 1920        # 1080p base


# --------------------------------------------------------------------------- #
def _surf_at(grid, gx, gz, x, z):
    ix = int(np.clip(np.searchsorted(gx, x) - 1, 0, len(gx) - 2))
    iz = int(np.clip(np.searchsorted(gz, z) - 1, 0, len(gz) - 2))
    tx = (x - gx[ix]) / (gx[ix + 1] - gx[ix])
    tz = (z - gz[iz]) / (gz[iz + 1] - gz[iz])
    return float((1 - tx) * (1 - tz) * grid[ix, iz] + tx * (1 - tz) * grid[ix + 1, iz]
                 + (1 - tx) * tz * grid[ix, iz + 1] + tx * tz * grid[ix + 1, iz + 1])


def _slab_verts(gx, gz, grid, xoff):
    nx, nz = len(gx), len(gz)
    top = np.zeros((nx * nz, 3), np.float32)
    for i, x in enumerate(gx):
        for k, z in enumerate(gz):
            top[i * nz + k] = (x + xoff, TOP + EXAG * grid[i, k], z)
    bot = top.copy()
    bot[:, 1] = TOP - RENDER_THK
    return np.vstack([top, bot])


def _rgb(c):
    return tuple(int(np.clip(round(v * 255), 0, 255)) for v in c)


# --------------------------------------------------------------------------- #
def _load_sims():
    if os.path.exists(CACHE):
        print(f"[cache] GT from {CACHE}", flush=True)
        d = np.load(CACHE, allow_pickle=True)
        gt = {k: d[k] for k in d.files}
    else:
        print("[GT] full-FEM dinner (slow) …", flush=True)
        gt = run_dinner_gt()
        np.savez(CACHE, **{k: v for k, v in gt.items() if isinstance(v, np.ndarray)})
    print("[native] modal dinner …", flush=True)
    nv = run_dinner_native(num_modes=20, n_frames=int(0.55 * 480), h=1.0 / 480.0)
    return gt, nv


def _prep(sim, gx, gz, dt, is_gt):
    """Impact-aligned per-frame (u_grid, pot_y, plate_ys) on the common clock."""
    nx, nz = len(gx), len(gz)
    mid = (nx // 2) * nz + (nz // 2)
    f = sim["field"]
    if is_gt:
        f = f - np.median(f[:10], axis=0)
        t = sim["times"]
    else:
        t = np.arange(f.shape[0]) * dt
    t = t - t[int(np.argmax(np.abs(f[:, mid])))]
    tc = np.linspace(T0, T1, NFRAMES)

    def rs(y):
        y = np.asarray(y)
        if y.ndim == 1:
            return np.interp(tc, t, y, left=y[0], right=y[-1])
        out = np.empty((NFRAMES, y.shape[1]))
        for j in range(y.shape[1]):
            out[:, j] = np.interp(tc, t, y[:, j], left=y[0, j], right=y[-1, j])
        return out

    F = rs(f).reshape(NFRAMES, nx, nz)
    return F, rs(sim["pot_y"]), rs(sim["plate_ys"])


def main():
    gt, nv = _load_sims()
    gx, gz = gt["gx"], gt["gz"]
    nx, nz = len(gx), len(gz)
    gtU, gt_pot, gt_pl = _prep(gt, gx, gz, None, True)
    nvU, nv_pot, nv_pl = _prep(nv, gx, gz, 1.0 / 480.0, False)
    faces = _slab_faces(nx, nz)
    ph = DINNER.pot_half

    # ---- viser scene ----
    server = viser.ViserServer(host="127.0.0.1", port=8231)
    server.scene.set_up_direction("+y")
    tmpl = {k: _resolve_kind_template(k) for k in ("pot", "plate", "candle")}

    arms = []
    for name, xoff, U, poty, ply in (
            ("full-FEM ground truth", -XOFF, gtU, gt_pot, gt_pl),
            ("native modal (20 modes)", XOFF, nvU, nv_pot, nv_pl)):
        tbl = server.scene.add_mesh_simple(
            f"/{name}/table", vertices=_slab_verts(gx, gz, U[0], xoff),
            faces=faces, color=(0.42, 0.28, 0.17), flat_shading=False,
            side="double")
        Vp, Fp = tmpl["pot"]
        pot = server.scene.add_batched_meshes_simple(
            f"/{name}/pot", Vp, Fp,
            batched_wxyzs=np.array([[1., 0, 0, 0]], np.float32),
            batched_positions=np.array([[xoff, TOP + ph[1], 0.]], np.float32),
            batched_scales=np.array([[2 * h for h in ph]], np.float32),
            batched_colors=np.array([_rgb((0.20, 0.18, 0.16))], np.uint8),
            flat_shading=True, side="double")
        Vpl, Fpl = tmpl["plate"]
        pxz = DINNER.plate_xz
        plates = server.scene.add_batched_meshes_simple(
            f"/{name}/plate", Vpl, Fpl,
            batched_wxyzs=np.tile([1., 0, 0, 0], (len(pxz), 1)).astype(np.float32),
            batched_positions=np.zeros((len(pxz), 3), np.float32),
            batched_scales=np.tile([2 * h for h in DINNER.plate_half],
                                   (len(pxz), 1)).astype(np.float32),
            batched_colors=np.array([_rgb(c) for c in DINNER.plate_colors], np.uint8),
            flat_shading=True, side="double")
        Vc, Fc = tmpl["candle"]
        cxz = DINNER.candle_xz
        candles = server.scene.add_batched_meshes_simple(
            f"/{name}/candle", Vc, Fc,
            batched_wxyzs=np.tile([1., 0, 0, 0], (len(cxz), 1)).astype(np.float32),
            batched_positions=np.zeros((len(cxz), 3), np.float32),
            batched_scales=np.tile([2 * h for h in DINNER.candle_half],
                                   (len(cxz), 1)).astype(np.float32),
            batched_colors=np.array([_rgb(c) for c in DINNER.candle_colors], np.uint8),
            flat_shading=True, side="double")
        server.scene.add_label(f"/{name}/label", name,
                               position=(xoff, TOP + 0.34, 0.0))
        arms.append(dict(xoff=xoff, U=U, poty=poty, ply=ply, tbl=tbl, pot=pot,
                         plates=plates, candles=candles))

    def _bodies_for(arm, i):
        grid = arm["U"][i]
        xoff = arm["xoff"]

        def u_at(x, z):
            return _surf_at(grid, gx, gz, x, z)

        # Bodies at their REAL recorded height so they visibly JUMP off the
        # table (the two-way kick), kept coherent with the exaggerated table via
        # the (EXAG−1)·u term: render_y = y_recorded + (EXAG−1)·u(x,z). At rest
        # (y ≈ surface) this rides the exaggerated dip; when launched, the true
        # jump dominates and the object leaves the table.
        pl_pos = np.array(
            [[xoff + px, arm["ply"][i, k] + (EXAG - 1.0) * u_at(px, pz), pz]
             for k, (px, pz) in enumerate(DINNER.plate_xz)], np.float32)
        # candles are decoration (not simulated) → ride the exaggerated surface.
        cd_pos = np.array(
            [[xoff + cx, TOP + EXAG * u_at(cx, cz) + DINNER.candle_half[1], cz]
             for (cx, cz) in DINNER.candle_xz], np.float32)
        pot_pos = np.array(
            [[xoff, arm["poty"][i] + (EXAG - 1.0) * u_at(0.0, 0.0), 0.0]],
            np.float32)
        return pl_pos, cd_pos, pot_pos

    # ---- headless Chrome client ----
    url = f"http://127.0.0.1:8231"
    frames = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome", headless=True,
            args=["--no-sandbox", "--use-gl=swiftshader", "--enable-webgl",
                  "--ignore-gpu-blocklist", f"--window-size={RES_W},{RES_H}"])
        page = browser.new_page(viewport={"width": RES_W, "height": RES_H})
        page.goto(url, wait_until="domcontentloaded")
        print("[viser] waiting for client …", flush=True)
        t0 = time.time()
        while not server.get_clients() and time.time() - t0 < 30:
            time.sleep(0.2)
        clients = server.get_clients()
        if not clients:
            raise RuntimeError("no viser client connected")
        client = list(clients.values())[0]
        time.sleep(3.0)                     # let the scene meshes load
        # Frame both tables (span x≈±1.4 m) from an elevated 3/4 view.
        cam = client.camera
        cam.up_direction = (0.0, 1.0, 0.0)
        cam.position = (0.0, 1.05, 3.05)
        cam.look_at = (0.0, TOP + 0.05, 0.0)
        cam.fov = 0.64
        time.sleep(0.5)

        print(f"[render] capturing {NFRAMES} frames …", flush=True)
        for i in range(NFRAMES):
            with server.atomic():
                for arm in arms:
                    arm["tbl"].vertices = _slab_verts(gx, gz, arm["U"][i], arm["xoff"])
                    pl, cd, po = _bodies_for(arm, i)
                    arm["plates"].batched_positions = pl
                    arm["candles"].batched_positions = cd
                    arm["pot"].batched_positions = po
            time.sleep(0.03)
            img = client.get_render(height=RES_H, width=RES_W)
            frames.append(Image.fromarray(img).convert("RGB"))
            if (i + 1) % 12 == 0:
                print(f"   {i+1}/{NFRAMES}", flush=True)
        browser.close()

    # Auto-crop the white margins to a common content box (+ padding).
    arrs = [np.asarray(f) for f in frames]
    mask = np.zeros(arrs[0].shape[:2], bool)
    for a in arrs:
        mask |= np.any(a < 245, axis=2)
    ys, xs = np.where(mask)
    pad = 24
    y0, y1 = max(0, ys.min() - pad), min(arrs[0].shape[0], ys.max() + pad)
    x0, x1 = max(0, xs.min() - pad), min(arrs[0].shape[1], xs.max() + pad)
    frames = [f.crop((x0, y0, x1, y1)) for f in frames]

    os.makedirs(os.path.dirname(OUT_GIF), exist_ok=True)
    frames[0].save(OUT_GIF, save_all=True, append_images=frames[1:],
                   duration=int(1000 / 30), loop=0, optimize=True)
    print(f"wrote {OUT_GIF}  ({len(frames)} frames, crop {x1-x0}x{y1-y0})",
          flush=True)
    server.stop()


if __name__ == "__main__":
    main()
