#!/usr/bin/env python3
"""Viser viewer: the DCR dinner-table scene driven by the REDUCED-MODAL
coupled AVBD solver (`ReducedCoupledAVBDCoupler`, the q_s + q_d path).

This is the place-setting layout (4 plates + forks/knives, 4 candles, a
pot dropped on center) with the **table as the reduced-modal deformable
support**. The pot's impact rings the table's modal field and the
coupling rocks the nearby objects through the deformed support geometry
inside the AVBD iteration — no patch DCR, no post-fix velocity kick.

Rendering reuses the decorated `model/{kind}/` assets + collision-proxy
toggle from `run_scenes_avbd`, and the deformable-slab surface from
`run_reduced_support_shelf_viser`. The GUI exposes the reduced-modal
knobs (AVBD iters/substeps, modal exaggeration, render mode/thickness,
impedance/damping on rebuild) PLUS a "show collision proxies" toggle.

    uv run python scripts/run_reduced_dinner_viser.py
    # then open http://localhost:8190
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from scenes.reduced_dinner_table import build_reduced_dinner_table
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


# Table material → (Young's modulus [Pa], density [kg/m³]). Young's modulus
# map matches scenes/presets.py MATERIAL_YOUNGS; densities are representative.
_MATERIAL: dict[str, tuple[float, float]] = {
    "steel":   (2.0e11, 7850.0),   # ~rigid at table scale
    "wood":    (1.0e10,  600.0),   # the recommended demo material
    "plastic": (1.0e9,  1200.0),   # visibly flexes
    "soft":    (1.0e8,  1000.0),   # rubbery, exaggerated demo
}


class ReducedDinnerViewer:
    def __init__(self, args):
        import viser

        self.args = args
        self._render_thickness = float(args.render_thickness)
        self._build_world()

        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._world_lock = threading.Lock()

        self._init_table_surface()
        self._init_bodies()
        self._init_gui()

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ---- world ---------------------------------------------------------
    def _build_world(self):
        a = self.args

        youngs, density = _MATERIAL.get(a.material, _MATERIAL["wood"])

        def _build(dev):
            return build_reduced_dinner_table(
                device=dev,
                iterations=a.iters,
                avbd_substeps=a.substeps,
                table_thickness=a.thickness,
                youngs=youngs,
                density=density,
                pot_mass=a.pot_mass,
                pot_drop_height=a.drop_height,
                pot_v0_y=a.pot_v0,
                modal_impedance_scale=a.impedance,
                modal_damping_scale=a.damping,
                to_eigenbasis=True,
            )

        # The ReducedCoupledAVBDCoupler is GPU device-resident: on cuda the
        # per-iteration Schur solve runs on-device (no host round-trip), ~7×
        # faster than the numpy reference path. Fall back to CPU only if cuda
        # is unavailable.
        try:
            self.handle = _build(a.device)
        except Exception as e:
            if a.device != "cpu":
                print(f"[viewer] device {a.device!r} unavailable "
                      f"({type(e).__name__}: {e}); falling back to cpu — "
                      f"expect ~7× slower step time.")
                a.device = "cpu"
                self.handle = _build("cpu")
            else:
                raise
        self.world = self.handle.world
        self.rs = self.handle.rs
        self.coupler = self.world.reduced_coupled_coupler
        self.h = float(a.h)
        dr = bool(getattr(self.coupler, "device_resident", False))
        print(f"[viewer] device={a.device}  coupler device_resident={dr}")

    # ---- viser scene ---------------------------------------------------
    def _init_table_surface(self):
        self._faces = _slab_faces(N_GRID_X, N_GRID_Z)
        verts0 = _slab_world_vertices(
            self.handle, self.rs.q, self._render_thickness, 1.0)
        self.table_handle = self.server.scene.add_mesh_simple(
            "/table", vertices=verts0, faces=self._faces,
            color=(0.45, 0.32, 0.22), flat_shading=False, side="double")

    def _init_bodies(self):
        """One decorated batched node per render_kind + a dim cube proxy
        node per kind. Both share poses; the toggle only flips visibility."""
        # Group the dinner bodies by render_kind, preserving order.
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
            # Dim cube proxy (the AABB physics actually sees), hidden until
            # the "show collision proxies" toggle flips it on.
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
        with g.add_folder("Sim"):
            self.gui_pause = g.add_checkbox("pause", initial_value=False)
            self.gui_speed = g.add_slider("speed", 0.05, 2.0, 0.05, 0.5)
            self.gui_reset = g.add_button("reset / rebuild")
            self.gui_reset.on_click(lambda _: self._reset())

        with g.add_folder("Scene (press reset / rebuild to apply)"):
            self.gui_material = g.add_dropdown(
                "table material", tuple(_MATERIAL.keys()),
                initial_value=self.args.material)
            self.gui_thickness = g.add_slider(
                "table thickness [mm]", 5.0, 80.0, 1.0,
                float(self.args.thickness) * 1e3)
            self.gui_pot_mass = g.add_slider(
                "pot mass [kg]", 0.5, 20.0, 0.5, float(self.args.pot_mass))
            self.gui_drop = g.add_slider(
                "pot drop height [m]", 0.0, 1.5, 0.01, float(self.args.drop_height))
            self.gui_pot_v0 = g.add_slider(
                "pot init velocity vy [m/s]", -5.0, 0.0, 0.1,
                float(self.args.pot_v0),
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
                hint="Swap each plate/fork/knife/candle/pot for the dim AABB "
                     "cube the physics actually sees. Off: decorated models.")
            self.gui_show_proxy.on_update(self._proxy_toggle_changed)
            self.gui_exagg = g.add_slider("modal exaggeration", 1.0, 500.0,
                                          1.0, float(self.args.exaggerate))
            self.gui_render_q = g.add_dropdown(
                "render modal state", ("q_s + q_d (full)", "q_s only (static)"))
            self.gui_render_thick = g.add_slider(
                "table render thickness [mm]", 0.0, 80.0, 1.0,
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
        """Rebuild the world from the current GUI knobs. Scene knobs
        (material / thickness / pot mass / drop / v0) and solver knobs
        (substeps / impedance / damping) all need a fresh basis + coupler."""
        with self._world_lock:
            a = self.args
            a.iters = int(self.gui_iters.value)
            a.substeps = int(self.gui_substeps.value)
            a.impedance = float(self.gui_impedance.value)
            a.damping = float(self.gui_damping.value)
            a.material = str(self.gui_material.value)
            a.thickness = float(self.gui_thickness.value) / 1e3
            a.pot_mass = float(self.gui_pot_mass.value)
            a.drop_height = float(self.gui_drop.value)
            a.pot_v0 = float(self.gui_pot_v0.value)
            self._build_world()
        # Body kinds/sizes are unchanged (only the pot's mass/launch differ,
        # not its render box), so the existing render groups still match.

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
        q = self.rs.q_s if self.gui_render_q.value.startswith("q_s only") else self.rs.q
        deformed = _slab_world_vertices(
            self.handle, q, self._render_thickness,
            float(self.gui_exagg.value))
        show_proxy = bool(self.gui_show_proxy.value)
        try:
            with self.server.atomic():
                self.table_handle.vertices = deformed
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cuda:0", choices=["cpu", "cuda:0"],
                    help="cuda:0 (default) runs the coupler GPU device-resident "
                         "(~7× faster); cpu uses the numpy reference path.")
    ap.add_argument("--port", type=int, default=8190)
    ap.add_argument("--h", type=float, default=1.0 / 120.0)
    # GPU device-resident makes higher fidelity cheap (~18 ms/frame at 8/4
    # on cuda); substeps=4 brings out the dynamic-ring transient.
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--substeps", type=int, default=4)
    ap.add_argument("--material", default="wood", choices=tuple(_MATERIAL.keys()),
                    help="table material → Young's modulus + density")
    ap.add_argument("--thickness", type=float, default=0.03,
                    help="table thickness [m] for flexural rigidity")
    ap.add_argument("--pot-mass", type=float, default=8.0, dest="pot_mass",
                    help="mass of the dropped pot [kg]")
    ap.add_argument("--drop-height", type=float, default=0.5, dest="drop_height",
                    help="pot release height above the table [m]")
    ap.add_argument("--pot-v0", type=float, default=0.0, dest="pot_v0",
                    help="extra downward launch velocity vy [m/s] (0 = from rest)")
    ap.add_argument("--impedance", type=float, default=1.0,
                    help="modal impedance gain (response amplitude; ω,ζ invariant)")
    ap.add_argument("--damping", type=float, default=1.0,
                    help="modal damping scale (ring-down time)")
    ap.add_argument("--exaggerate", type=float, default=80.0,
                    help="display-only modal-deflection multiplier")
    ap.add_argument("--render-thickness", type=float, default=0.02,
                    help="cosmetic table slab thickness [m]")
    args = ap.parse_args(argv)

    viewer = ReducedDinnerViewer(args)
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
