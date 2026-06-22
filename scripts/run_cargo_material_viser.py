"""Live viser for the rigid / fem_rigid / abd / fem cube materials (Stages 3–5).

Drops one deformable cube onto the reduced-modal support and renders it live:
the skinned cube surface (modal flex or affine shear, exaggerated for the eye),
the deformed support grid it rings, and a HUD showing the two-way tell-tales.
Switch the cube material (rigid → fem_rigid → abd → fem) and the device
(cpu / cuda:0) from the GUI; the scene rebuilds. "rigid" is the plain 6-DOF
k=0 baseline — it tumbles and rings the support but carries no deformation.

This is a focused slice of the Stage-7 unified viser — material × device on the
AVBD solver + the one cargo scene — so the cube materials can be inspected
interactively (not just via the docs/avbd_native GIFs). The full
scene × solver × material × device matrix is Stage 7.

Run:
    .venv/bin/python scripts/run_cargo_material_viser.py --kind abd --device cuda:0
then open http://localhost:8191
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_fem_rigid_cargo import build_cargo_scene, cube_state_world

N_GRID_X, N_GRID_Z = 21, 11
KINDS = ("rigid", "fem_rigid", "abd", "fem")
# Per-material flex exaggeration for the eye (the real deformation is tiny).
# "rigid" (k=0) carries no flex, so its exaggeration is a no-op (kept at 1.0).
_EXAG = {"rigid": 1.0, "fem_rigid": 300.0, "abd": 40.0, "fem": 300.0}
_CUBE_COLOR = {"rigid": (150, 155, 165), "fem_rigid": (77, 140, 217),
               "abd": (217, 120, 77), "fem": (120, 200, 120)}


def _support_faces(nx: int, nz: int) -> np.ndarray:
    """Two triangles per grid quad over the (nx × nz) support sample grid
    (vertex index ix*nz + iz, matching make_debug_reduced_shelf_support)."""
    faces = []
    for ix in range(nx - 1):
        for iz in range(nz - 1):
            a = ix * nz + iz
            b = (ix + 1) * nz + iz
            c = (ix + 1) * nz + (iz + 1)
            d = ix * nz + (iz + 1)
            faces.append((a, b, c))
            faces.append((a, c, d))
    return np.array(faces, dtype=np.int32)


def _support_verts(rs, exag: float) -> np.ndarray:
    v = rs.point_positions_rest.copy().astype(np.float32)
    v[:, 1] += (rs.U_points[:, 1, :] @ rs.q).astype(np.float32) * exag
    return v


class CargoViser:
    def __init__(self, args):
        import viser
        self.args = args
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self.kind = args.kind
        self.device = args.device
        self.paused = False
        # Rebuilding allocates warp arrays / captures a CUDA graph, which is NOT
        # safe to do from viser's GUI-callback thread while the main loop is
        # mid-world.step() on the same CUDA context. So GUI callbacks only RAISE
        # this flag; the main loop performs the rebuild itself (single-threaded).
        self._pending_rebuild = False
        self._support_faces = _support_faces(N_GRID_X, N_GRID_Z)
        self._build()
        self._init_gui()

    # ---- scene -------------------------------------------------------
    def _build(self):
        self.handle = build_cargo_scene(
            self.kind, device=self.device, drop_height=self.args.drop,
            spin=self.args.spin,
            device_resident=self.device.startswith("cuda"))
        self.rs = self.handle.rs
        self.cube = self.handle.cube
        exag = _EXAG[self.kind]
        # support mesh
        self.support = self.server.scene.add_mesh_simple(
            "/support", vertices=_support_verts(self.rs, exag),
            faces=self._support_faces, color=(150, 150, 150),
            flat_shading=False, side="double")
        # cube mesh (skinned, exaggerated flex)
        z = cube_state_world(self.handle)
        self.cube_mesh = self.server.scene.add_mesh_simple(
            "/cube", vertices=self.cube.deformed_surface(z, exag).astype(np.float32),
            faces=self.cube.surf_faces.astype(np.int32),
            color=_CUBE_COLOR[self.kind], flat_shading=True, side="double")

    def _rebuild(self):
        for name in ("/support", "/cube"):
            try:
                self.server.scene.remove_by_name(name)
            except Exception:
                pass
        self._build()

    # ---- GUI ---------------------------------------------------------
    def _init_gui(self):
        g = self.server.gui
        with g.add_folder("Material × device"):
            self.gui_kind = g.add_dropdown("material", KINDS, initial_value=self.kind)
            self.gui_device = g.add_dropdown(
                "device", ("cpu", "cuda:0"), initial_value=self.device)
            self.gui_pause = g.add_checkbox("pause", initial_value=False)
            self.gui_reset = g.add_button("reset / rebuild")
        with g.add_folder("two-way HUD"):
            self.hud_ms = g.add_text("ms / step", initial_value="—")
            self.hud_cube = g.add_text("cube deform E (J)", initial_value="—")
            self.hud_supp = g.add_text("support modal KE (J)", initial_value="—")
            self.hud_pen = g.add_text("max penetration (mm)", initial_value="—")
            self.hud_back = g.add_text("backend", initial_value="—")

        # GUI callbacks (server thread) only request a rebuild; the main loop
        # performs it so all warp/CUDA + scene-graph mutation is single-threaded.
        def _request(_=None):
            self._pending_rebuild = True
        self.gui_kind.on_update(_request)
        self.gui_device.on_update(_request)
        self.gui_reset.on_click(_request)
        self.gui_pause.on_update(lambda _: setattr(self, "paused",
                                                   self.gui_pause.value))

    # ---- loop --------------------------------------------------------
    def run(self):
        print(f"\n  cargo-material viser: http://localhost:{self.args.port}")
        print(f"  material={self.kind}  device={self.device}\n")
        while True:
            # Perform any GUI-requested rebuild HERE (main thread), reading the
            # latest widget values, before touching the (now-current) handles.
            if self._pending_rebuild:
                self._pending_rebuild = False
                self.kind = self.gui_kind.value
                self.device = self.gui_device.value
                self._rebuild()
            c = self.handle.coupler
            if not self.paused:
                t0 = time.perf_counter()
                self.handle.world.step()
                ms = (time.perf_counter() - t0) * 1e3
                exag = _EXAG[self.kind]
                z = cube_state_world(self.handle)
                self.cube_mesh.vertices = self.cube.deformed_surface(
                    z, exag).astype(np.float32)
                self.support.vertices = _support_verts(self.rs, exag)
                self.hud_ms.value = f"{ms:.2f}"
                self.hud_cube.value = (
                    f"{c.last_cargo_modal_KE + c.last_cargo_modal_PE:.3e}")
                self.hud_supp.value = f"{c.last_modal_KE:.3e}"
                self.hud_pen.value = (
                    f"{c.last_contact_residual * 1e3:.4f}")
                resident = getattr(self.handle.world._solver,
                                   "hooks_device_resident", False)
                self.hud_back.value = (
                    f"{self.device} {'(GPU-resident)' if resident else ''}")
            time.sleep(max(0.0, 1.0 / 120.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="fem_rigid", choices=KINDS)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--drop", type=float, default=0.04)
    ap.add_argument("--spin", type=float, default=4.0)
    ap.add_argument("--port", type=int, default=8191)
    CargoViser(ap.parse_args()).run()


if __name__ == "__main__":
    main()
