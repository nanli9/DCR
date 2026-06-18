"""Stage 7 — unified viser: scene × solver × material × device (live switching).

One viewer over the full matrix:

  * scene    — cargo (single deformable cube on the support) | the four
               production scenes truck / ledge / shelf / dinner (a deformable
               impactor + rigid bystanders on the reduced-modal support).
  * solver   — avbd (Schur–Newton, Stages 3–5) | xpbd (compliant Gauss–Seidel,
               Stage 6). Flip to compare the two device-resident primals of the
               SAME dynamic two-way constraint (two_band_coupling.html).
  * material — fem_rigid | abd | fem (the deformable impactor's body model).
  * device   — cpu | cuda:0 (GPU-resident on CUDA).

Rendering: the deformed support grid, the deformable impactor's skinned surface
(modal flex / affine shear), and the rigid bystanders as boxes. Two render-only
"deformation exaggeration" sliders (cube flex, slab deflection) default to 1.0
(TRUE SCALE); the rigid drop/tumble is always true scale. Real flex is ~1e-5 m,
so raise the sliders (~300) to see the modal/affine motion.

Notes:
  * abd + xpbd auto-routes to AVBD: abd's stiff nonlinear V⊥ is not Gauss–Seidel-
    stable in the substep sweep budget (the XPBDDynamicSystem oracle note); the
    HUD shows the effective solver.
  * XPBD uses a higher iteration budget on the many-body production scenes (its
    GS has no ρ-escalation; ~16 iters vs AVBD's scene default) for robustness.
  * This renders simple boxes, not the decorated `model/<kind>/` assets — those
    stay in scripts/run_reduced_scene_viser.py (rigid cargo, no solver/material
    switching).

Run:
    .venv/bin/python scripts/run_native_scenes_viser.py --scene ledge --device cuda:0
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

from scenes.reduced_fem_rigid_cargo import build_cargo_scene
from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table

N_GRID_X, N_GRID_Z = 21, 11
KINDS = ("fem_rigid", "abd", "fem")
SOLVERS = ("avbd", "xpbd")
SCENES = ("cargo", "truck", "ledge", "shelf", "dinner")
_PROD = {"truck": build_reduced_truck, "ledge": build_reduced_ledge,
         "shelf": build_reduced_shelf, "dinner": build_reduced_dinner_table}
_CUBE_COLOR = {"fem_rigid": (77, 140, 217), "abd": (217, 120, 77),
               "fem": (120, 200, 120)}
_EXAG_MAX = 2000.0

# unit-box corner table (x,y,z bits) + 12-triangle faces for that ordering.
_BOX_CORNERS = np.array(
    [[sx, sy, sz] for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)
     for sz in (-1.0, 1.0)], dtype=np.float64)
_BOX_FACES = np.array([
    (0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
    (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3),
], dtype=np.int32)


def _effective_solver(solver: str, kind: str) -> str:
    """abd routes to AVBD (its stiff V⊥ is not GS-stable; oracle note)."""
    return "avbd" if (solver == "xpbd" and kind == "abd") else solver


def _iters_for(solver: str) -> dict:
    """XPBD GS needs more sweeps than AVBD AL on the many-body scenes."""
    return {"iterations": 16, "avbd_substeps": 4} if solver == "xpbd" else {}


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


def _quat_wxyz_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def _box_verts(half, p, q_xyzw) -> np.ndarray:
    q_wxyz = (q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2])
    R = _quat_wxyz_to_R(q_wxyz)
    return ((_BOX_CORNERS * np.asarray(half)) @ R.T + p).astype(np.float32)


class UnifiedViser:
    def __init__(self, args):
        import viser
        self.args = args
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self.scene = args.scene
        self.kind = args.kind
        self.solver = args.solver
        self.device = args.device
        self.paused = False
        self.cube_exag = float(args.cube_exag)
        self.support_exag = float(args.support_exag)
        self._pending_rebuild = False
        self._support_faces = _support_faces(N_GRID_X, N_GRID_Z)
        self._build()
        self._init_gui()

    # ---- scene + render setup ---------------------------------------
    def _build(self):
        eff = _effective_solver(self.solver, self.kind)
        self._eff_solver = eff
        rd = self.device.startswith("cuda")
        if self.scene == "cargo":
            self.handle = build_cargo_scene(
                self.kind, device=self.device, solver=eff,
                drop_height=self.args.drop, spin=self.args.spin,
                device_resident=rd)
        else:
            self.handle = _PROD[self.scene](
                device=self.device, solver=eff, cargo_material=self.kind,
                **_iters_for(eff))
        self.rs = self.handle.rs
        self.world = self.handle.world
        self.coupler = self.world.reduced_coupled_coupler
        self._collect_render()
        self._make_meshes()

    def _collect_render(self):
        """Build the box list (rigid bystanders) + the deformable impactor."""
        self._boxes = []     # (avbd_idx, half, color_u8)
        self._deform = None  # (cube, avbd_idx, color_u8)
        if self.scene == "cargo":
            self._deform = (self.handle.cube, self.handle.avbd_idx,
                            _CUBE_COLOR[self.kind])
            return
        imp_dcr = self.handle.impactor_idx
        cargo_idx = self.handle.cargo_avbd_idx
        for b in self.handle.bodies:
            if b.dcr_idx == imp_dcr:
                continue                      # the impactor is the deformable
            desc = self.world._descs[b.dcr_idx]
            if desc.avbd_body is None:
                continue
            col = tuple(int(255 * c) for c in b.color)
            self._boxes.append((int(desc.avbd_body.index), b.half_extents, col))
        if self.handle.cargo_cube is not None and cargo_idx is not None:
            self._deform = (self.handle.cargo_cube, cargo_idx,
                            _CUBE_COLOR[self.kind])
        else:
            # rigid impactor (cargo_material=None): render it as a box too.
            for b in self.handle.bodies:
                if b.dcr_idx == imp_dcr:
                    desc = self.world._descs[b.dcr_idx]
                    col = tuple(int(255 * c) for c in b.color)
                    self._boxes.append(
                        (int(desc.avbd_body.index), b.half_extents, col))

    def _make_meshes(self):
        self.support = self.server.scene.add_mesh_simple(
            "/support", vertices=_support_verts(self.rs, self.support_exag),
            faces=self._support_faces, color=(150, 150, 150),
            flat_shading=False, side="double")
        P, Q = self.world._solver.positions(), self.world._solver.orientations()
        self._box_meshes = []
        for i, (idx, half, col) in enumerate(self._boxes):
            m = self.server.scene.add_mesh_simple(
                f"/box_{i}", vertices=_box_verts(half, P[idx], Q[idx]),
                faces=_BOX_FACES, color=col, flat_shading=True, side="double")
            self._box_meshes.append(m)
        self._deform_mesh = None
        if self._deform is not None:
            cube, idx, col = self._deform
            self._deform_mesh = self.server.scene.add_mesh_simple(
                "/deform", vertices=self._deform_verts(),
                faces=cube.surf_faces.astype(np.int32), color=col,
                flat_shading=True, side="double")

    def _deform_verts(self) -> np.ndarray:
        cube, idx, _ = self._deform
        P, Q = self.world._solver.positions(), self.world._solver.orientations()
        qx = Q[idx]
        z = np.zeros(7 + cube.k)
        z[0:3] = P[idx].astype(np.float64)
        z[3:7] = (qx[3], qx[0], qx[1], qx[2])           # xyzw -> wxyz
        z[7:] = self.coupler.cargo_a[idx]
        return cube.deformed_surface(z, self.cube_exag).astype(np.float32)

    def _rebuild(self):
        names = ["/support", "/deform"] + [f"/box_{i}"
                                           for i in range(len(self._boxes))]
        for n in names:
            try:
                self.server.scene.remove_by_name(n)
            except Exception:
                pass
        self._build()

    # ---- GUI ---------------------------------------------------------
    def _init_gui(self):
        g = self.server.gui
        with g.add_folder("scene × solver × material × device"):
            self.gui_scene = g.add_dropdown("scene", SCENES,
                                            initial_value=self.scene)
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
        for w in (self.gui_scene, self.gui_solver, self.gui_kind,
                  self.gui_device):
            w.on_update(_request)
        self.gui_reset.on_click(_request)
        self.gui_pause.on_update(
            lambda _: setattr(self, "paused", self.gui_pause.value))
        self.gui_cube_exag.on_update(
            lambda _: setattr(self, "cube_exag", self.gui_cube_exag.value))
        self.gui_support_exag.on_update(
            lambda _: setattr(self, "support_exag", self.gui_support_exag.value))

    # ---- loop --------------------------------------------------------
    def run(self):
        print(f"\n  unified viser: http://localhost:{self.args.port}")
        print(f"  scene={self.scene} solver={self.solver} material={self.kind} "
              f"device={self.device}\n")
        while True:
            if self._pending_rebuild:
                self._pending_rebuild = False
                self.scene = self.gui_scene.value
                self.solver = self.gui_solver.value
                self.kind = self.gui_kind.value
                self.device = self.gui_device.value
                self._rebuild()
            c = self.coupler
            if not self.paused:
                t0 = time.perf_counter()
                self.world.step()
                ms = (time.perf_counter() - t0) * 1e3
                P, Q = (self.world._solver.positions(),
                        self.world._solver.orientations())
                for m, (idx, half, _) in zip(self._box_meshes, self._boxes):
                    m.vertices = _box_verts(half, P[idx], Q[idx])
                if self._deform_mesh is not None:
                    self._deform_mesh.vertices = self._deform_verts()
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
                resident = getattr(self.world._solver,
                                   "hooks_device_resident", False)
                self.hud_back.value = (
                    f"{self.device} {'(GPU-resident)' if resident else ''}")
            time.sleep(max(0.0, 1.0 / 120.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="cargo", choices=SCENES)
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
