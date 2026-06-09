#!/usr/bin/env python3
"""Viser viewer for the REDUCED-MODAL coupled AVBD demo scenes.

One viewer, four scenes — all driven by `ReducedCoupledAVBDCoupler`
(the q_s + q_d coupled path, GPU device-resident on cuda):

    dinner  — place settings + candles, a pot dropped on a wood table
    truck   — crates / cones / lumber on a wood road, heavy crate dropped
    shelf   — books standing on a soft cantilever shelf, a weight dropped
    ledge   — pillars balanced on a stone ledge, a boulder dropped

In every scene the **support surface itself is the reduced-modal
deformable** (table / road / shelf / ledge): the dropped impactor rings
the support's modal field and the coupling rocks the resting objects
through the deformed support geometry inside the AVBD iteration
(cross-block ρ·J_x·J_q^T) — no patch DCR, no post-fix velocity kick.

Rigid bodies are skinned with the decorated `model/<kind>/` assets and a
"show collision proxies" toggle swaps in the dim AABB cube the physics
actually sees. The GUI exposes the reduced-modal knobs (AVBD
iters/substeps, modal impedance/damping on rebuild), the impactor
mass/drop/launch, the support material/thickness, and the display-only
modal exaggeration.

    uv run python scripts/run_reduced_scene_viser.py --scene truck
    uv run python scripts/run_reduced_scene_viser.py --scene ledge --device cpu
    # then open http://localhost:8190
"""
from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z
# Decorated render templates + collision-proxy cube (shared loader).
from scripts.render_assets import (
    _resolve_kind_template, _KIND_TEMPLATE_SOURCE, _CUBE_V, _CUBE_F,
)
# Deformable-slab surface (top+bottom sheets) shared with the shelf viewer.
from scripts.run_reduced_support_shelf_viser import (
    _slab_faces, _slab_world_vertices,
)


def _rgb_u8(c) -> tuple[int, int, int]:
    return tuple(int(np.clip(round(v * 255), 0, 255)) for v in c)


# Support material → (Young's modulus [Pa], density [kg/m³]). Young's modulus
# map matches scenes/presets.py MATERIAL_YOUNGS; densities are representative.
_MATERIAL: dict[str, tuple[float, float]] = {
    "steel":   (2.0e11, 7850.0),   # ~rigid at support scale (stiff stone)
    "wood":    (1.0e10,  600.0),   # the recommended demo material
    "plastic": (1.0e9,  1200.0),   # visibly flexes
    "soft":    (1.0e8,  1000.0),   # rubbery, exaggerated demo
}


@dataclass
class ScenePreset:
    """Per-scene defaults + the adapter that maps the viewer's generic knob
    set onto each builder's signature (the dinner builder uses pot_*/table_*
    names; the truck/shelf/ledge builders use impactor_*/support_* names)."""
    label: str
    build: Callable                       # (args, youngs, density) -> handle
    impactor_label: str                   # "pot" / "crate" / "weight" / "boulder"
    support_color: tuple[float, float, float]
    material: str = "wood"
    thickness: float = 0.03               # support thickness [m]
    impactor_mass: float = 8.0
    drop_height: float = 0.5
    impactor_v0: float = 0.0
    mass_range: tuple[float, float] = (0.5, 20.0)
    iters: int = 4
    substeps: int = 4
    exaggerate: float = 1.0      # 1 = honest (no display exaggeration)


def _dinner_build(a, youngs, density):
    return build_reduced_dinner_table(
        device=a.device, iterations=a.iters, avbd_substeps=a.substeps,
        table_thickness=a.thickness, youngs=youngs, density=density,
        pot_mass=a.impactor_mass, pot_drop_height=a.drop_height,
        pot_v0_y=a.impactor_v0,
        modal_impedance_scale=a.impedance, modal_damping_scale=a.damping,
        to_eigenbasis=True)


def _generic_build(builder):
    def _b(a, youngs, density):
        return builder(
            device=a.device, iterations=a.iters, avbd_substeps=a.substeps,
            support_thickness=a.thickness, youngs=youngs, density=density,
            impactor_mass=a.impactor_mass, impactor_drop_height=a.drop_height,
            impactor_v0=a.impactor_v0,
            modal_impedance_scale=a.impedance, modal_damping_scale=a.damping,
            to_eigenbasis=True)
    return _b


SCENES: dict[str, ScenePreset] = {
    "dinner": ScenePreset(
        label="Dinner Table", build=_dinner_build, impactor_label="pot",
        support_color=(0.45, 0.32, 0.22), material="wood", thickness=0.03,
        impactor_mass=8.0, drop_height=0.5, mass_range=(0.5, 20.0)),
    "truck": ScenePreset(
        label="Road Impact", build=_generic_build(build_reduced_truck),
        impactor_label="crate", support_color=(0.34, 0.34, 0.36),
        material="wood", thickness=0.06,
        impactor_mass=40.0, drop_height=0.7, mass_range=(2.0, 120.0)),
    "shelf": ScenePreset(
        label="Bookshelf Drop", build=_generic_build(build_reduced_shelf),
        impactor_label="weight", support_color=(0.52, 0.38, 0.24),
        material="plastic", thickness=0.03,
        impactor_mass=6.0, drop_height=0.5, mass_range=(0.5, 20.0)),
    "ledge": ScenePreset(
        label="Cliff Ledge Rockfall", build=_generic_build(build_reduced_ledge),
        impactor_label="boulder", support_color=(0.48, 0.46, 0.42),
        material="wood", thickness=0.08,
        impactor_mass=50.0, drop_height=0.8, mass_range=(5.0, 120.0)),
}


class ReducedSceneViewer:
    def __init__(self, args):
        import viser

        self.args = args
        self.spec = SCENES[args.scene]
        self._render_thickness = float(args.render_thickness)
        self._build_world()

        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._world_lock = threading.Lock()

        self._init_support_surface()
        self._init_bodies()
        self._init_gui()

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ---- world ---------------------------------------------------------
    def _build_world(self):
        a = self.args
        youngs, density = _MATERIAL.get(a.material, _MATERIAL["wood"])

        # The ReducedCoupledAVBDCoupler is GPU device-resident: on cuda the
        # per-iteration Schur solve runs on-device (no host round-trip), ~7×
        # faster than the numpy reference path. Fall back to CPU only if cuda
        # is unavailable.
        try:
            self.handle = self.spec.build(a, youngs, density)
        except Exception as e:
            if a.device != "cpu":
                print(f"[viewer] device {a.device!r} unavailable "
                      f"({type(e).__name__}: {e}); falling back to cpu — "
                      f"expect ~7× slower step time.")
                a.device = "cpu"
                self.handle = self.spec.build(a, youngs, density)
            else:
                raise
        self.world = self.handle.world
        self.rs = self.handle.rs
        self.coupler = self.world.reduced_coupled_coupler
        self.h = float(a.h)
        dr = bool(getattr(self.coupler, "device_resident", False))
        print(f"[viewer] scene={a.scene} device={a.device}  "
              f"coupler device_resident={dr}")

    # ---- viser scene ---------------------------------------------------
    def _init_support_surface(self):
        self._faces = _slab_faces(N_GRID_X, N_GRID_Z)
        verts0 = _slab_world_vertices(
            self.handle, self.rs.q, self._render_thickness, 1.0)
        self.support_handle = self.server.scene.add_mesh_simple(
            "/support", vertices=verts0, faces=self._faces,
            color=self.spec.support_color, flat_shading=False, side="double")

    def _init_bodies(self):
        """One decorated batched node per render_kind + a dim cube proxy node
        per kind. Both share poses; the toggle only flips visibility."""
        groups: dict[str, list] = {}
        for b in self.handle.bodies:
            groups.setdefault(b.render_kind, []).append(b)

        self._groups = []
        for kind, blist in groups.items():
            V, F = _resolve_kind_template(kind)
            scales = np.array([[2 * h for h in b.half_extents] for b in blist],
                              dtype=np.float32)
            colors = np.array([_rgb_u8(b.color) for b in blist], dtype=np.uint8)
            bp, bw = self._gather_poses(blist)
            handle = self.server.scene.add_batched_meshes_simple(
                f"/body_{kind}", V, F,
                batched_wxyzs=bw, batched_positions=bp,
                batched_scales=scales, batched_colors=colors,
                flat_shading=True, side="double")
            proxy_colors = (colors.astype(np.int32) * 6 // 10).astype(np.uint8)
            proxy = self.server.scene.add_batched_meshes_simple(
                f"/body_{kind}_proxy", _CUBE_V, _CUBE_F,
                batched_wxyzs=bw, batched_positions=bp,
                batched_scales=scales, batched_colors=proxy_colors,
                flat_shading=True, side="double")
            proxy.visible = False
            self._groups.append(dict(
                kind=kind, bodies=blist, handle=handle, proxy=proxy,
                scales=scales))
        srcs = ", ".join(f"{g['kind']}:{_KIND_TEMPLATE_SOURCE.get(g['kind'])}"
                         for g in self._groups)
        print(f"[viewer] render templates → {srcs}")

    def _gather_poses(self, blist):
        descs = self.world._descs
        bp = np.array([descs[b.dcr_idx].dcr_body.position for b in blist],
                      dtype=np.float32)
        bw = np.array([descs[b.dcr_idx].dcr_body.orientation for b in blist],
                      dtype=np.float32)
        return bp, bw

    # ---- GUI -----------------------------------------------------------
    def _init_gui(self):
        g = self.server.gui
        sp = self.spec
        imp = sp.impactor_label
        with g.add_folder("Sim"):
            self.gui_scene = g.add_dropdown(
                "scene (rebuild)", tuple(SCENES.keys()),
                initial_value=self.args.scene)
            self.gui_pause = g.add_checkbox("pause", initial_value=False)
            self.gui_speed = g.add_slider("speed", 0.05, 2.0, 0.05, 0.5)
            self.gui_reset = g.add_button("reset / rebuild")
            self.gui_reset.on_click(lambda _: self._reset())

        with g.add_folder("Scene (press reset / rebuild to apply)"):
            self.gui_material = g.add_dropdown(
                "support material", tuple(_MATERIAL.keys()),
                initial_value=self.args.material)
            self.gui_thickness = g.add_slider(
                "support thickness [mm]", 5.0, 100.0, 1.0,
                float(self.args.thickness) * 1e3)
            self.gui_imp_mass = g.add_slider(
                f"{imp} mass [kg]", sp.mass_range[0], sp.mass_range[1],
                0.5, float(self.args.impactor_mass))
            self.gui_drop = g.add_slider(
                f"{imp} drop height [m]", 0.0, 2.0, 0.01,
                float(self.args.drop_height))
            self.gui_imp_v0 = g.add_slider(
                f"{imp} init velocity vy [m/s]", -5.0, 0.0, 0.1,
                float(self.args.impactor_v0),
                hint="Extra downward launch velocity on top of the drop. "
                     "0 = released from rest.")

        with g.add_folder("Reduced-modal solver"):
            self.gui_iters = g.add_slider("AVBD iterations", 2, 24, 1,
                                          int(self.args.iters))
            self.gui_iters.on_update(self._iters_changed)
            self.gui_substeps = g.add_slider("AVBD substeps (rebuild)", 1, 16,
                                             1, int(self.args.substeps))
            self.gui_impedance = g.add_slider(
                "modal impedance gain (rebuild)", 0.25, 16.0, 0.25,
                float(self.args.impedance))
            self.gui_damping = g.add_slider(
                "modal damping scale (rebuild)", 0.1, 8.0, 0.1,
                float(self.args.damping))

        with g.add_folder("Visualization"):
            self.gui_show_proxy = g.add_checkbox(
                "show collision proxies", initial_value=False,
                hint="Swap each decorated body for the dim AABB cube the "
                     "physics actually sees. Off: decorated models.")
            self.gui_show_proxy.on_update(self._proxy_toggle_changed)
            self.gui_exagg = g.add_slider("modal exaggeration", 1.0, 500.0,
                                          1.0, float(self.args.exaggerate))
            self.gui_render_q = g.add_dropdown(
                "render modal state", ("q_s + q_d (full)", "q_s only (static)"),
                initial_value="q_s only (static)")
            self.gui_render_thick = g.add_slider(
                "support render thickness [mm]", 0.0, 100.0, 1.0,
                self._render_thickness * 1e3)
            self.gui_render_thick.on_update(self._render_thick_changed)

        with g.add_folder("Diagnostics"):
            self.gui_t = g.add_text("t [s]", initial_value="0.000")
            self.gui_step_ms = g.add_text("step [ms]", initial_value="0.0")
            self.gui_q = g.add_text("|q|", initial_value="0")
            self.gui_qs = g.add_text("|q_s| (static sag)", initial_value="0")
            self.gui_qd = g.add_text("|q_d| (dynamic ring)", initial_value="0")
            self.gui_defl = g.add_text("max deflection [mm]", initial_value="0")
            self.gui_ntracked = g.add_text(
                "tracked bodies", initial_value=str(len(self.rs.probe_body_indices)))
            self.gui_passv = g.add_text("passivity violations", initial_value="0")

    # ---- handlers ------------------------------------------------------
    def _iters_changed(self, _evt):
        n = int(self.gui_iters.value)
        with self._world_lock:
            self.world.avbd_iterations = n
            self.world._solver.iterations = n
            self.world._solver._graph = None

    def _render_thick_changed(self, _evt):
        self._render_thickness = max(0.0, float(self.gui_render_thick.value) / 1e3)

    def _proxy_toggle_changed(self, _evt):
        show = bool(self.gui_show_proxy.value)
        with self.server.atomic():
            for grp in self._groups:
                grp["handle"].visible = not show
                grp["proxy"].visible = show

    def _reset(self):
        """Rebuild the world. A SCENE CHANGE loads the new scene's preset
        defaults (its impactor mass/drop ranges differ, so carrying the old
        slider values over would throw value-out-of-range) and rebuilds the
        render + GUI nodes. SAME-scene reset reads the live GUI knobs."""
        with self._world_lock:
            a = self.args
            new_scene = str(self.gui_scene.value)
            scene_changed = new_scene != a.scene
            if scene_changed:
                a.scene = new_scene
                self.spec = SCENES[new_scene]
                sp = self.spec
                a.material = sp.material
                a.thickness = sp.thickness
                a.impactor_mass = sp.impactor_mass
                a.drop_height = sp.drop_height
                a.impactor_v0 = sp.impactor_v0
                a.iters = sp.iters
                a.substeps = sp.substeps
                a.exaggerate = sp.exaggerate
                a.impedance = 1.0
                a.damping = 1.0
            else:
                a.iters = int(self.gui_iters.value)
                a.substeps = int(self.gui_substeps.value)
                a.impedance = float(self.gui_impedance.value)
                a.damping = float(self.gui_damping.value)
                a.material = str(self.gui_material.value)
                a.thickness = float(self.gui_thickness.value) / 1e3
                a.impactor_mass = float(self.gui_imp_mass.value)
                a.drop_height = float(self.gui_drop.value)
                a.impactor_v0 = float(self.gui_imp_v0.value)
            self._build_world()
            if scene_changed:
                # Different body set + impactor labels + slider ranges → tear
                # the GUI and render nodes down and rebuild from the new scene.
                self.server.scene.reset()
                self.server.gui.reset()
                self._init_support_surface()
                self._init_bodies()
                self._init_gui()

    # ---- loop ----------------------------------------------------------
    def _loop(self):
        last = time.perf_counter()
        accum = 0.0
        while not self._stop.is_set():
            now = time.perf_counter()
            dt = now - last
            last = now
            if self.gui_pause.value:
                time.sleep(1.0 / 60.0)
                continue
            accum += dt * float(self.gui_speed.value)
            n = 0
            t_step = 0.0
            while accum >= self.h and n < 4:
                t0 = time.perf_counter()
                with self._world_lock:
                    self.world.step()
                t_step = (time.perf_counter() - t0) * 1e3
                accum -= self.h
                n += 1
            self._render_tick(t_step)

    def _render_tick(self, step_ms):
        # Hold the world lock for the whole tick. A scene-change _reset() swaps
        # self.world / self.rs / self._groups and tears down the GUI handles
        # while holding this lock, so guarding here stops the render thread
        # from reading the new world's (shorter) _descs against the old body
        # list (IndexError) or writing to torn-down GUI elements mid-rebuild.
        with self._world_lock:
            q = (self.rs.q_s if self.gui_render_q.value.startswith("q_s only")
                 else self.rs.q)
            deformed = _slab_world_vertices(
                self.handle, q, self._render_thickness,
                float(self.gui_exagg.value))
            show_proxy = bool(self.gui_show_proxy.value)
            try:
                with self.server.atomic():
                    self.support_handle.vertices = deformed
                    for grp in self._groups:
                        bp, bw = self._gather_poses(grp["bodies"])
                        tgt = grp["proxy"] if show_proxy else grp["handle"]
                        tgt.batched_positions = bp
                        tgt.batched_wxyzs = bw
            except RuntimeError:
                return
            # Diagnostics.
            self.gui_t.value = f"{self.world.t:.3f}" if hasattr(self.world, "t") else "—"
            self.gui_step_ms.value = f"{step_ms:.1f}"
            self.gui_q.value = f"{np.linalg.norm(self.rs.q):.3e}"
            self.gui_qs.value = f"{np.linalg.norm(self.rs.q_s):.3e}"
            self.gui_qd.value = f"{np.linalg.norm(self.rs.q_d):.3e}"
            self.gui_defl.value = f"{self.coupler.last_max_support_deflection * 1e3:.3f}"
            self.gui_passv.value = str(self.coupler.last_passivity_violations)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", default="truck", choices=tuple(SCENES.keys()),
                    help="which reduced-modal demo scene to load")
    ap.add_argument("--device", default="cuda:0", choices=["cpu", "cuda:0"],
                    help="cuda:0 (default) runs the coupler GPU device-resident "
                         "(~7× faster); cpu uses the numpy reference path.")
    ap.add_argument("--port", type=int, default=8190)
    ap.add_argument("--h", type=float, default=1.0 / 120.0)
    # Knobs default to None → filled from the scene preset so each scene gets
    # its own sensible mass/drop/material/thickness/exaggeration.
    ap.add_argument("--iters", type=int, default=None)
    ap.add_argument("--substeps", type=int, default=None)
    ap.add_argument("--material", default=None, choices=tuple(_MATERIAL.keys()),
                    help="support material → Young's modulus + density")
    ap.add_argument("--thickness", type=float, default=None,
                    help="support thickness [m] for flexural rigidity")
    ap.add_argument("--impactor-mass", type=float, default=None, dest="impactor_mass",
                    help="mass of the dropped impactor [kg]")
    ap.add_argument("--drop-height", type=float, default=None, dest="drop_height",
                    help="impactor release height above the support [m]")
    ap.add_argument("--impactor-v0", type=float, default=None, dest="impactor_v0",
                    help="extra downward launch velocity vy [m/s] (0 = from rest)")
    ap.add_argument("--impedance", type=float, default=1.0,
                    help="modal impedance gain (response amplitude; ω,ζ invariant)")
    ap.add_argument("--damping", type=float, default=1.0,
                    help="modal damping scale (ring-down time)")
    ap.add_argument("--exaggerate", type=float, default=None,
                    help="display-only modal-deflection multiplier")
    ap.add_argument("--render-thickness", type=float, default=0.02,
                    help="cosmetic support slab thickness [m]")
    args = ap.parse_args(argv)

    # Fill un-set knobs from the chosen scene's preset.
    sp = SCENES[args.scene]
    if args.iters is None: args.iters = sp.iters
    if args.substeps is None: args.substeps = sp.substeps
    if args.material is None: args.material = sp.material
    if args.thickness is None: args.thickness = sp.thickness
    if args.impactor_mass is None: args.impactor_mass = sp.impactor_mass
    if args.drop_height is None: args.drop_height = sp.drop_height
    if args.impactor_v0 is None: args.impactor_v0 = sp.impactor_v0
    if args.exaggerate is None: args.exaggerate = sp.exaggerate

    viewer = ReducedSceneViewer(args)
    print(f"\n  {viewer.handle.name}")
    print(f"  bodies={len(viewer.handle.bodies)}  modes r={viewer.rs.r}  "
          f"tracked={len(viewer.rs.probe_body_indices)}")
    print(f"  device={args.device}  iters={args.iters}  substeps={args.substeps}")
    print(f"  viser: http://localhost:{args.port}\n")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
