"""Stage 7 — unified viser: solver × material × device (live switching).

Drops one deformable cube onto the reduced-modal support and renders it live —
the skinned cube (modal flex / affine shear, exaggerated), the support grid it
rings, and a two-way HUD — with LIVE dropdowns for:

  * solver   — avbd (Schur–Newton, Stages 3–5) | xpbd (compliant Gauss–Seidel,
               Stage 6). Flip between them to compare the two device-resident
               primals of the SAME dynamic two-way constraint (two_band_coupling.html).
  * material — fem_rigid | abd | fem.
  * device   — cpu | cuda:0 (GPU-resident on CUDA).

Two render-only "deformation exaggeration" sliders (cube flex, slab deflection)
default to 1.0 (TRUE SCALE) and are independent; the rigid drop/tumble is always
true scale. The real flex is tiny (~1e-5 m), so raise the sliders (~300) to see
the modal/affine deformation; --cube-exag / --support-exag set the initial values.

This fuses the solver dropdown (Stage 6) onto the material × device cargo viser.
abd + xpbd auto-routes to AVBD: abd's stiff nonlinear V⊥ is not Gauss–Seidel-
stable in the substep sweep budget (the XPBDDynamicSystem oracle note), so the
abd path is AVBD — the HUD shows the effective solver.

Scope note: the four PRODUCTION scenes (truck/ledge/shelf/dinner,
`run_reduced_scene_viser.py`) currently carry RIGID cargo; wiring the deformable
materials into them is the remaining Stage-7 piece. This viser covers the cargo
scene where the deformable materials live, across solver × material × device.

Run:
    .venv/bin/python scripts/run_native_scenes_viser.py --device cuda:0
then open http://localhost:8192
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
KINDS = ("fem_rigid", "abd", "fem")
SOLVERS = ("avbd", "xpbd")
_CUBE_COLOR = {"fem_rigid": (77, 140, 217), "abd": (217, 120, 77),
               "fem": (120, 200, 120)}
# Exaggeration is a render-only scale on the DEFORMATION (cube modal flex /
# affine shear; slab modal deflection) — the rigid drop/tumble is always true
# scale. Default 1.0 (true scale); the real flex is tiny (~1e-5 m), so crank the
# sliders to ~300 to see it. Cube and slab have INDEPENDENT factors.
_EXAG_MAX = 2000.0


def _effective_solver(solver: str, kind: str) -> str:
    """abd routes to AVBD (its stiff V⊥ is not GS-stable; oracle note)."""
    if solver == "xpbd" and kind == "abd":
        return "avbd"
    return solver


def _support_faces(nx: int, nz: int) -> np.ndarray:
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


class UnifiedViser:
    def __init__(self, args):
        import viser
        self.args = args
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self.kind = args.kind
        self.solver = args.solver
        self.device = args.device
        self.paused = False
        # Render-only deformation exaggeration (true scale = 1.0); live sliders.
        self.cube_exag = float(args.cube_exag)
        self.support_exag = float(args.support_exag)
        self._pending_rebuild = False
        self._support_faces = _support_faces(N_GRID_X, N_GRID_Z)
        self._build()
        self._init_gui()

    def _build(self):
        eff = _effective_solver(self.solver, self.kind)
        self._eff_solver = eff
        self.handle = build_cargo_scene(
            self.kind, device=self.device, solver=eff,
            drop_height=self.args.drop, spin=self.args.spin,
            device_resident=self.device.startswith("cuda"))
        self.rs = self.handle.rs
        self.cube = self.handle.cube
        self.support = self.server.scene.add_mesh_simple(
            "/support", vertices=_support_verts(self.rs, self.support_exag),
            faces=self._support_faces, color=(150, 150, 150),
            flat_shading=False, side="double")
        z = cube_state_world(self.handle)
        self.cube_mesh = self.server.scene.add_mesh_simple(
            "/cube",
            vertices=self.cube.deformed_surface(z, self.cube_exag).astype(np.float32),
            faces=self.cube.surf_faces.astype(np.int32),
            color=_CUBE_COLOR[self.kind], flat_shading=True, side="double")

    def _rebuild(self):
        for name in ("/support", "/cube"):
            try:
                self.server.scene.remove_by_name(name)
            except Exception:
                pass
        self._build()

    def _init_gui(self):
        g = self.server.gui
        with g.add_folder("scene × solver × material × device"):
            self.gui_solver = g.add_dropdown("solver", SOLVERS,
                                             initial_value=self.solver)
            self.gui_kind = g.add_dropdown("material", KINDS,
                                           initial_value=self.kind)
            self.gui_device = g.add_dropdown("device", ("cpu", "cuda:0"),
                                             initial_value=self.device)
            self.gui_pause = g.add_checkbox("pause", initial_value=False)
            self.gui_reset = g.add_button("reset / rebuild")
        with g.add_folder("deformation exaggeration (render only; 1 = true scale)"):
            self.gui_cube_exag = g.add_slider(
                "cube flex ×", min=1.0, max=_EXAG_MAX, step=1.0,
                initial_value=self.cube_exag)
            self.gui_support_exag = g.add_slider(
                "slab deflection ×", min=1.0, max=_EXAG_MAX, step=1.0,
                initial_value=self.support_exag)
        with g.add_folder("two-way HUD"):
            self.hud_eff = g.add_text("effective solver", initial_value="—")
            self.hud_ms = g.add_text("ms / step", initial_value="—")
            self.hud_cube = g.add_text("cube deform E (J)", initial_value="—")
            self.hud_supp = g.add_text("support modal KE (J)", initial_value="—")
            self.hud_pen = g.add_text("max penetration (mm)", initial_value="—")
            self.hud_back = g.add_text("backend", initial_value="—")

        def _request(_=None):
            self._pending_rebuild = True
        self.gui_solver.on_update(_request)
        self.gui_kind.on_update(_request)
        self.gui_device.on_update(_request)
        self.gui_reset.on_click(_request)
        self.gui_pause.on_update(
            lambda _: setattr(self, "paused", self.gui_pause.value))
        # Exaggeration is a per-frame render scale — no rebuild; apply live.
        self.gui_cube_exag.on_update(
            lambda _: setattr(self, "cube_exag", self.gui_cube_exag.value))
        self.gui_support_exag.on_update(
            lambda _: setattr(self, "support_exag", self.gui_support_exag.value))

    def run(self):
        print(f"\n  unified viser: http://localhost:{self.args.port}")
        print(f"  solver={self.solver} material={self.kind} device={self.device}\n")
        while True:
            if self._pending_rebuild:
                self._pending_rebuild = False
                self.solver = self.gui_solver.value
                self.kind = self.gui_kind.value
                self.device = self.gui_device.value
                self._rebuild()
            c = self.handle.coupler
            if not self.paused:
                t0 = time.perf_counter()
                self.handle.world.step()
                ms = (time.perf_counter() - t0) * 1e3
                z = cube_state_world(self.handle)
                self.cube_mesh.vertices = self.cube.deformed_surface(
                    z, self.cube_exag).astype(np.float32)
                self.support.vertices = _support_verts(self.rs, self.support_exag)
                eff = self._eff_solver
                self.hud_eff.value = (
                    eff if eff == self.solver
                    else f"{eff}  (abd→avbd: V⊥ not GS-stable)")
                self.hud_ms.value = f"{ms:.2f}"
                self.hud_cube.value = (
                    f"{c.last_cargo_modal_KE + c.last_cargo_modal_PE:.3e}")
                self.hud_supp.value = f"{c.last_modal_KE:.3e}"
                self.hud_pen.value = f"{c.last_contact_residual * 1e3:.4f}"
                resident = getattr(self.handle.world._solver,
                                   "hooks_device_resident", False)
                self.hud_back.value = (
                    f"{self.device} {'(GPU-resident)' if resident else ''}")
            time.sleep(max(0.0, 1.0 / 120.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="xpbd", choices=SOLVERS)
    ap.add_argument("--kind", default="fem_rigid", choices=KINDS)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--drop", type=float, default=0.04)
    ap.add_argument("--spin", type=float, default=4.0)
    ap.add_argument("--cube-exag", type=float, default=1.0,
                    help="initial cube-flex render exaggeration (1 = true scale)")
    ap.add_argument("--support-exag", type=float, default=1.0,
                    help="initial slab-deflection render exaggeration (1 = true scale)")
    ap.add_argument("--port", type=int, default=8192)
    UnifiedViser(ap.parse_args()).run()


if __name__ == "__main__":
    main()
