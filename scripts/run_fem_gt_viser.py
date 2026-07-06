"""Viser viewer for the all-FEM ground truth (every body FEM, G1 arm).

Steps `MultiFEMSim` (dcr/fem/multibody_gt.py) live and renders every FEM
body's deformed surface — the support slab AND the free bodies — with a
deformation-exaggeration slider (true deflections are sub-mm; raise it to
~200 to SEE the ring) and a TET-WIREFRAME toggle that overlays each body's
full tet mesh (interior edges included) deforming with the same
exaggeration. The X3 two-phase protocol runs inline: the impactor
is parked +100 m away, the scene settles, and at t = settle the impactor is
restored to its drop pose (HUD shows the phase).

NOT real time: the GT costs ~13–55 s wall per simulated second (that is the
point of a ground truth). The "sim steps / frame" slider trades smoothness
for wall-clock pace.

Run:
    .venv/bin/python scripts/run_fem_gt_viser.py --scene dinner
then open http://localhost:8193
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

from benchmarks.fem_gt.common import SUPPORTS, gt_sim_from_handle  # noqa: E402
from benchmarks.fem_gt.run_gt import SCENES, _build_handle, \
    _CargoHandleAdapter  # noqa: E402

_SUPPORT_COLOR = (140, 110, 70)
_IMPACTOR_COLOR = (77, 140, 217)
_EXAG_MAX = 2000.0


def _tet_edges(tets: np.ndarray) -> np.ndarray:
    """Unique undirected edges (E,2) of a (T,4) tet array — the full tet
    wireframe, interior edges included."""
    pairs = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    e = np.concatenate([tets[:, list(p)] for p in pairs], axis=0)
    e = np.sort(e.astype(np.int64), axis=1)
    return np.unique(e, axis=0)


class GTViser:
    def __init__(self, args):
        import viser
        self.args = args
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self.scene = args.scene
        self.paused = False
        self.exag = float(args.exag)
        self.steps_per_frame = int(args.steps_per_frame)
        self.wireframe = bool(args.wireframe)
        self._pending_rebuild = False
        self._build()
        self._init_gui()

    # ---- sim + render setup -----------------------------------------
    def _build(self):
        handle, self.imp_name = _build_handle(self.scene)
        if self.scene == "cargo":
            handle = _CargoHandleAdapter(handle)
        h_fine = 1e-4 if self.args.quick else 5e-5
        self.sim = gt_sim_from_handle(handle, SUPPORTS[self.scene],
                                      h_fine=h_fine,
                                      body_youngs=self.args.body_youngs)
        self.t_settle = float(self.args.t_settle)
        # per-body colors from the scene metadata (support: wood tone)
        colors = {b.name: tuple(int(255 * c) for c in getattr(
            b, "color", (0.6, 0.6, 0.6))) for b in handle.bodies}
        colors[self.imp_name] = _IMPACTOR_COLOR
        colors["support"] = _SUPPORT_COLOR
        # park the impactor (X3 settle phase); restored at t = t_settle
        self.imp = self.sim.body(self.imp_name)
        self._imp_com0 = self.imp.com().copy()
        self.imp.translate((100.0, 0.0, 0.0))
        self.released = False
        # surface mesh per body (faces fixed; verts refreshed per frame)
        self._surf = []      # (body, sv_ids, mesh_handle)
        self._wire = []      # (body, edge_ids (E,2), line_handle)
        for b in self.sim.bodies:
            surface = b.fem.mesh.extract_surface()
            sv = np.unique(surface.faces.ravel())
            remap = np.full(b.fem.mesh.num_vertices, -1, dtype=np.int64)
            remap[sv] = np.arange(len(sv))
            faces = remap[surface.faces].astype(np.int32)
            mesh = self.server.scene.add_mesh_simple(
                f"/gt_{b.name}", vertices=self._body_verts(b, sv),
                faces=faces, color=colors.get(b.name, (150, 150, 150)),
                flat_shading=True, side="double")
            self._surf.append((b, sv, mesh))
            # tet wireframe: every unique tet edge (interior included),
            # deforming with the same exaggeration as the surface
            edges = _tet_edges(b.fem.mesh.tets)
            wire = self.server.scene.add_line_segments(
                f"/gt_wire_{b.name}",
                points=self._wire_points(b, edges),
                colors=(25, 25, 28), line_width=1.0,
                visible=self.wireframe)
            self._wire.append((b, edges, wire))
        # support-mid probe (the X3 mid-span u_y signal)
        sup = self.sim.body("support")
        v = sup.fem.mesh.vertices[sup.top_verts]
        self._mid_idx = int(np.argmin(v[:, 0] ** 2 + v[:, 2] ** 2))

    def _body_pts_full(self, b) -> np.ndarray:
        """ALL world verts with the DEFORMATION exaggerated about the body's
        mean translation (free bodies carry rigid motion inside u, so scaling
        u directly would fling them; scale only the deviation)."""
        u = b.u_full().reshape(-1, 3)
        mean = u.mean(axis=0)
        u_dev = u - mean
        return (b.origin + b.fem.mesh.vertices + mean
                + self.exag * u_dev).astype(np.float32)

    def _body_verts(self, b, sv) -> np.ndarray:
        return self._body_pts_full(b)[sv]

    def _wire_points(self, b, edges) -> np.ndarray:
        """(E,2,3) tet-edge segments at the exaggerated world positions."""
        return self._body_pts_full(b)[edges]

    def _rebuild(self):
        for b, _, _ in self._surf:
            for prefix in ("/gt_", "/gt_wire_"):
                try:
                    self.server.scene.remove_by_name(f"{prefix}{b.name}")
                except Exception:
                    pass
        self._build()

    # ---- GUI ---------------------------------------------------------
    def _init_gui(self):
        g = self.server.gui
        with g.add_folder("GT sim"):
            self.gui_scene = g.add_dropdown("scene", SCENES,
                                            initial_value=self.scene)
            self.gui_pause = g.add_checkbox("pause", initial_value=self.paused)
            self.gui_spf = g.add_slider(
                "sim steps / frame", 1, 500, 1, self.steps_per_frame,
                hint="more = faster wall-clock playback, choppier render")
            self.gui_exag = g.add_slider(
                "deformation ×", 1.0, _EXAG_MAX, 1.0, self.exag,
                hint="render-only; GT deflections are sub-mm, raise to ~200")
            self.gui_wire = g.add_checkbox(
                "tet wireframe", initial_value=self.wireframe,
                hint="overlay every body's full tet mesh (interior edges "
                     "included), deforming with the same exaggeration")
            self.gui_reset = g.add_button("reset / rebuild")
        with g.add_folder("GT diagnostics"):
            self.hud_phase = g.add_text("phase", initial_value="settling")
            self.hud_t = g.add_text("sim t [s]", initial_value="0.000")
            self.hud_ms = g.add_text("wall [ms/frame]", initial_value="—")
            self.hud_mid = g.add_text("support mid u_y [mm]",
                                      initial_value="—")
            self.hud_led = g.add_text("Σ support contact force [N]",
                                      initial_value="—")
        self.gui_scene.on_update(
            lambda _: setattr(self, "_pending_rebuild", True))
        self.gui_reset.on_click(
            lambda _: setattr(self, "_pending_rebuild", True))
        self.gui_pause.on_update(
            lambda _: setattr(self, "paused", self.gui_pause.value))
        self.gui_spf.on_update(
            lambda _: setattr(self, "steps_per_frame",
                              int(self.gui_spf.value)))
        self.gui_exag.on_update(
            lambda _: setattr(self, "exag", float(self.gui_exag.value)))
        self.gui_wire.on_update(self._wire_changed)

    def _wire_changed(self, _evt=None):
        self.wireframe = bool(self.gui_wire.value)
        for b, edges, wire in self._wire:
            wire.visible = self.wireframe
            if self.wireframe:
                wire.points = self._wire_points(b, edges)

    # ---- loop --------------------------------------------------------
    def step_frame(self):
        """One render frame: N fine steps + release + mesh refresh."""
        for _ in range(self.steps_per_frame):
            if not self.released and self.sim.t >= self.t_settle:
                # release = restore the exact pre-park pose at rest
                self.imp.translate(tuple(self._imp_com0 - self.imp.com()))
                self.imp.set_velocity((0.0, 0.0, 0.0))
                self.released = True
            self.sim.step()
        for b, sv, mesh in self._surf:
            mesh.vertices = self._body_verts(b, sv)
        if self.wireframe:
            for b, edges, wire in self._wire:
                wire.points = self._wire_points(b, edges)

    def run(self):
        print(f"\n  FEM-GT viser: http://localhost:{self.args.port}")
        print(f"  scene={self.scene}  h_fine={self.sim.h_fine}  "
              f"(quick={self.args.quick})  — not real time; "
              f"raise 'sim steps / frame' to speed up\n")
        while True:
            if self._pending_rebuild:
                self._pending_rebuild = False
                self.scene = self.gui_scene.value
                self._rebuild()
            if not self.paused:
                t0 = time.perf_counter()
                self.step_frame()
                ms = (time.perf_counter() - t0) * 1e3
                self.hud_phase.value = ("released"
                                        if self.released else "settling")
                self.hud_t.value = f"{self.sim.t:.3f}"
                self.hud_ms.value = f"{ms:.0f}"
                sup = self.sim.body("support")
                self.hud_mid.value = (
                    f"{sup.top_uy()[self._mid_idx] * 1e3:+.4f}")
                led = sum(v for (a, b), v in self.sim.ledger.items()
                          if b == "support")
                self.hud_led.value = f"{led:.2f}"
            time.sleep(0.001)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", default="dinner", choices=SCENES)
    ap.add_argument("--quick", action="store_true",
                    help="h_fine=1e-4 (2x faster, softer contact pin)")
    ap.add_argument("--t-settle", type=float, default=0.4)
    ap.add_argument("--body-youngs", type=float, default=1.0e6)
    ap.add_argument("--exag", type=float, default=200.0,
                    help="initial deformation exaggeration (render-only)")
    ap.add_argument("--wireframe", action="store_true",
                    help="start with the tet-wireframe overlay ON (toggle "
                         "live in the GUI)")
    ap.add_argument("--steps-per-frame", type=int, default=100,
                    help="fine sim steps per rendered frame")
    ap.add_argument("--port", type=int, default=8193)
    GTViser(ap.parse_args()).run()


if __name__ == "__main__":
    main()
