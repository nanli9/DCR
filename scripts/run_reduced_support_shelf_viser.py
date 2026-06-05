#!/usr/bin/env python3
"""Live viser viewer for the Reduced-Coordinate AVBD Support shelf scene.

Open http://localhost:8181 in a browser (port configurable) to see:
  - Falling impactor + resting probe boxes (batched rigid bodies)
  - The reduced support's deformed surface, lifted/dropped per-vertex by
    U(x) · q. Toggle overlay on/off to live-watch the §8 transient
    smearing get restored by §9's sub-stepped IIR.
  - Live HUD: q_max, probe d_max, probe Δv, E_rigid, E_q, E_overlay_injected.

GUI knobs (all live; rebuilds the scene on big changes):
  - Pause / Speed / Reset
  - AVBD iterations (4 / 8 / 16 / 32 — the iteration sweep §20.1)
  - Overlay enabled / restart_each_step (§9.3)
  - rho_q (q-block AL penalty; see DEVIATION in reduced_support_solve.py)
  - reduced support enabled (sanity baseline)

Usage:
    uv run python scripts/run_reduced_support_shelf_viser.py
    uv run python scripts/run_reduced_support_shelf_viser.py --port 8200
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_support_shelf import (
    build_reduced_support_shelf,
    N_GRID_X,
    N_GRID_Z,
)
from dcr.rigid.energy import rigid_kinetic_energy


_CUBE_V = np.array([
    [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
    [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
], dtype=np.float32)
_CUBE_F = np.array([
    [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
    [2, 3, 7], [2, 7, 6], [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3],
], dtype=np.uint32)


def _shelf_faces(n_grid_x: int, n_grid_z: int) -> np.ndarray:
    """Triangle indices for the (n_grid_x, n_grid_z) shelf grid.

    Vertex `i * n_grid_z + k` lives at column i, row k (matching the
    `indexing="ij"` ravel order in make_synthetic_modal_basis_for_shelf).
    Two triangles per cell. Returns (n_tris, 3) uint32.
    """
    faces = []
    for i in range(n_grid_x - 1):
        for k in range(n_grid_z - 1):
            v00 = i * n_grid_z + k
            v10 = (i + 1) * n_grid_z + k
            v01 = i * n_grid_z + (k + 1)
            v11 = (i + 1) * n_grid_z + (k + 1)
            # CCW seen from +y (outward normal).
            faces.append([v00, v11, v10])
            faces.append([v00, v01, v11])
    return np.asarray(faces, dtype=np.uint32)


def _shelf_world_vertices(handle, q: np.ndarray) -> np.ndarray:
    """rest + U · q at every sample point. Returns (n_pts, 3) float32."""
    rs = handle.rs
    # einsum: (n_pts, 3, r) · (r,) → (n_pts, 3)
    disp = np.einsum("kij,j->ki", rs.U_points, q)
    return (rs.point_positions_rest + disp).astype(np.float32)


class ReducedSupportViewer:
    """Browser-based viser viewer + live solver thread for the v1 scene."""

    def __init__(self, args, handle):
        import viser
        self.args = args
        self.handle = handle
        self.world = handle.world
        self.rs = handle.rs
        self._world_lock = threading.Lock()
        self._stop = threading.Event()
        self._frame = 0
        self._hud_interval = 3

        # Snapshot taken AFTER attach_reduced_support but BEFORE first
        # step. The reset button restores from this.
        self._initial_snapshot = self.world.snapshot()
        self._initial_q = self.rs.q.copy()
        self._initial_qdot = self.rs.qdot.copy()

        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass

        # ---- Reduced shelf surface mesh ----
        self._shelf_faces = _shelf_faces(N_GRID_X, N_GRID_Z)
        self._shelf_rest_verts = (
            self.rs.point_positions_rest.astype(np.float32).copy())
        self.shelf_handle = self.server.scene.add_mesh_simple(
            "/reduced_shelf",
            vertices=self._shelf_rest_verts,
            faces=self._shelf_faces,
            color=(0.55, 0.50, 0.40),
            flat_shading=False,
            side="double",
        )

        # ---- Batched bodies (impactor + probes) ----
        # Walk world descs to find dynamic bodies and their sizes/colors.
        self._body_avbd_indices = []
        sizes_list = []
        colors_list = []
        positions_init = []
        wxyz_init = []
        for di, desc in enumerate(self.world._descs):
            if desc.avbd_body is None:
                continue
            self._body_avbd_indices.append(int(desc.avbd_body.index))
            he = desc.avbd_body.half_extents
            sizes_list.append((2 * he[0], 2 * he[1], 2 * he[2]))
            # Impactor = red, probes = green/blue, others = grey.
            if di == handle.impactor_idx:
                colors_list.append((220, 60, 60))
            elif di in handle.probe_indices:
                colors_list.append((60, 200, 120))
            else:
                colors_list.append((150, 150, 150))
            positions_init.append(tuple(desc.dcr_body.position))
            wxyz_init.append(tuple(desc.dcr_body.orientation))

        sizes = np.array(sizes_list, dtype=np.float32)
        colors = np.array(colors_list, dtype=np.uint8)
        bp = np.array(positions_init, dtype=np.float32)
        bw = np.array(wxyz_init, dtype=np.float32)
        self._batched_bodies = self.server.scene.add_batched_meshes_simple(
            "/bodies",
            _CUBE_V, _CUBE_F,
            batched_wxyzs=bw,
            batched_positions=bp,
            batched_scales=sizes,
            batched_colors=colors,
            flat_shading=True, side="double",
        )
        self._bp_buf = bp.copy()
        self._bw_buf = bw.copy()

        # Probe normal arrows (visualise Δv injection direction). Skipped
        # for v1 — viser arrow API would need an extra mesh handle. The
        # HUD prints Δv numerically per probe.

        # ---- GUI ----
        with self.server.gui.add_folder("Playback"):
            self.gui_pause = self.server.gui.add_checkbox(
                "pause", initial_value=False)
            self.gui_speed = self.server.gui.add_slider(
                "speed", min=0.05, max=4.0, step=0.05, initial_value=1.0)
            self.gui_reset = self.server.gui.add_button("reset scene")
            self.gui_reset.on_click(lambda _: self._reset_scene())

        with self.server.gui.add_folder("Solver"):
            self.gui_iters = self.server.gui.add_slider(
                "AVBD iterations", min=4, max=32, step=2,
                initial_value=int(self.world.avbd_iterations))
            self.gui_iters.on_update(self._iters_changed)

        with self.server.gui.add_folder("Reduced support"):
            self.gui_rs_enabled = self.server.gui.add_checkbox(
                "reduced support enabled",
                initial_value=bool(self.rs.enabled),
                hint="Off ⇒ vanilla AVBD only (no q-block, no overlay).")
            self.gui_rs_enabled.on_update(self._rs_enabled_changed)
            self.gui_overlay = self.server.gui.add_checkbox(
                "transient overlay (§9)",
                initial_value=bool(self.rs.overlay_enabled),
                hint="The decisive A/B. On = sub-stepped IIR peak. "
                     "Off = bare quasi-static d_qs / h.")
            self.gui_overlay.on_update(self._overlay_changed)
            self.gui_restart = self.server.gui.add_checkbox(
                "restart overlay each step (§9.3)",
                initial_value=bool(self.rs.restart_overlay_each_step))
            self.gui_restart.on_update(self._restart_changed)
            rho_init = float(self.world.reduced_support_coupler.rho_q)
            if rho_init <= 0:
                rho_init = 1.0e4
            self.gui_rho_q = self.server.gui.add_slider(
                "rho_q (log10)", min=2.0, max=8.0, step=0.1,
                initial_value=float(np.log10(max(rho_init, 1.0))),
                hint="q-block AL penalty (force/length). Auto-sized to "
                     "(1/h^2)·M_q[0,0] on first step; drag to retune.")
            self.gui_rho_q.on_update(self._rho_q_changed)

        # ---- Items (3) + (4): bounded overlay discipline ----
        with self.server.gui.add_folder("Overlay discipline (3+4)"):
            c0 = self.world.reduced_support_coupler
            self.gui_cap_on = self.server.gui.add_checkbox(
                "energy cap (item 3)",
                initial_value=bool(c0.energy_cap_enabled),
                hint="α=min(1,√(η·E_src/E_inj)). Off ⇒ raw injection.")
            self.gui_cap_on.on_update(self._cap_changed)
            self.gui_eta = self.server.gui.add_slider(
                "η_overlay", min=0.0, max=1.0, step=0.05,
                initial_value=float(c0.eta_overlay),
                hint="Fraction of source rigid-KE loss available to the "
                     "overlay's distant Δv injection.")
            self.gui_eta.on_update(self._eta_changed)
            self.gui_hp = self.server.gui.add_checkbox(
                "high-pass r̃ (overlay HP)",
                initial_value=bool(c0.overlay_high_pass),
                hint="r̃[n] − r̃[n−1] so steady loads don't re-excite the "
                     "IIR. Off ⇒ raw spec §9.2 formulation.")
            self.gui_hp.on_update(self._hp_changed)
            self.gui_cd_steps = self.server.gui.add_slider(
                "cooldown (item 4) steps", min=0, max=6, step=1,
                initial_value=int(c0.cooldown_steps),
                hint="Probe receivers' OWN contact rows are gated out of "
                     "r̃ for N macro steps after a kick. 0 ⇒ disabled.")
            self.gui_cd_steps.on_update(self._cd_steps_changed)
            self.gui_cd_thr = self.server.gui.add_slider(
                "cooldown |Δv| trigger [m/s]",
                min=0.01, max=2.0, step=0.01,
                initial_value=float(c0.cooldown_dv_threshold),
                hint="Δv below this doesn't arm the cooldown.")
            self.gui_cd_thr.on_update(self._cd_thr_changed)
            self.gui_fcap_on = self.server.gui.add_checkbox(
                "physical F_n cap (per body)",
                initial_value=bool(c0.physical_force_cap_enabled),
                hint="Caps total F_n per tracked body at "
                     "K·(m·|v_pre|/h + m·g). Tames λ overshoot at low N.")
            self.gui_fcap_on.on_update(self._fcap_on_changed)
            self.gui_fcap_K = self.server.gui.add_slider(
                "F_n cap K_safety",
                min=1.0, max=10.0, step=0.5,
                initial_value=float(c0.physical_force_cap_K_safety),
                hint="Multiplier on m·|v_pre|/h + m·g. 1 = strict, "
                     "3 = default, 10 = effectively off.")
            self.gui_fcap_K.on_update(self._fcap_K_changed)

        with self.server.gui.add_folder("Status"):
            self.gui_t = self.server.gui.add_text("t [s]", initial_value="0.000")
            self.gui_step_ms = self.server.gui.add_text(
                "step time [ms]", initial_value="0.0")
            self.gui_e_rigid = self.server.gui.add_text(
                "E_rigid [J]", initial_value="0.0")
            self.gui_e_q = self.server.gui.add_text(
                "E_q [J]", initial_value="0.0")
            self.gui_e_overlay = self.server.gui.add_text(
                "E_overlay_injected [J]", initial_value="0.0")
            self.gui_q_max = self.server.gui.add_text(
                "q_max_disp [m]", initial_value="0.0")
            self.gui_d_max = self.server.gui.add_text(
                "max probe d_max [m]", initial_value="0.0")
            self.gui_dv = self.server.gui.add_text(
                "max probe |Δv| [m/s]", initial_value="0.0")
            self.gui_n_tracked = self.server.gui.add_text(
                "tracked rows", initial_value="0")
            # Items (3) + (4) live diagnostics.
            self.gui_alpha = self.server.gui.add_text(
                "α (cap)", initial_value="1.000")
            self.gui_e_src = self.server.gui.add_text(
                "E_src [J]", initial_value="0.0")
            self.gui_e_inj_cand = self.server.gui.add_text(
                "E_inj_candidate [J]", initial_value="0.0")
            self.gui_e_inj_real = self.server.gui.add_text(
                "E_inj_realised [J]", initial_value="0.0")
            self.gui_n_cooldown = self.server.gui.add_text(
                "probes in cooldown", initial_value="0")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)

    # ---- GUI callbacks ---------------------------------------------------

    def _iters_changed(self, _evt):
        with self._world_lock:
            self.world.avbd_iterations = int(self.gui_iters.value)
            self.world._solver.iterations = int(self.gui_iters.value)
            self.world._solver._graph = None

    def _rs_enabled_changed(self, _evt):
        with self._world_lock:
            self.rs.enabled = bool(self.gui_rs_enabled.value)

    def _overlay_changed(self, _evt):
        with self._world_lock:
            self.rs.overlay_enabled = bool(self.gui_overlay.value)

    def _restart_changed(self, _evt):
        with self._world_lock:
            self.rs.restart_overlay_each_step = bool(self.gui_restart.value)

    def _rho_q_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.rho_q = float(10.0 ** float(self.gui_rho_q.value))

    def _cap_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.energy_cap_enabled = bool(self.gui_cap_on.value)

    def _eta_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.eta_overlay = float(self.gui_eta.value)

    def _hp_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.overlay_high_pass = bool(self.gui_hp.value)

    def _cd_steps_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.cooldown_steps = int(self.gui_cd_steps.value)
                if c.cooldown_steps == 0:
                    c._probe_cooldown.clear()

    def _cd_thr_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.cooldown_dv_threshold = float(self.gui_cd_thr.value)

    def _fcap_on_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.physical_force_cap_enabled = bool(self.gui_fcap_on.value)

    def _fcap_K_changed(self, _evt):
        with self._world_lock:
            c = self.world.reduced_support_coupler
            if c is not None:
                c.physical_force_cap_K_safety = float(self.gui_fcap_K.value)

    def _reset_scene(self):
        with self._world_lock:
            self.world.restore(self._initial_snapshot)
            self.rs.q[:] = self._initial_q
            self.rs.qdot[:] = self._initial_qdot
            self.rs.q_hat[:] = self._initial_q
            self.rs.q_prev_macro[:] = self._initial_q
            self.world.reduced_support_energy_log.clear()
        self._render_tick()

    # ---- Render + loop ---------------------------------------------------

    def run(self):
        self._thread.start()
        print(f"\n[viser] open http://localhost:{self.args.port} in a browser")
        print("        (Ctrl-C to quit)")
        try:
            while not self._stop.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            self._stop.set()
            self._thread.join(timeout=1.0)

    def _run_loop(self):
        h = self.world.h
        last_wall = time.perf_counter()
        accum = 0.0
        while not self._stop.is_set():
            now = time.perf_counter()
            dt_wall = now - last_wall
            last_wall = now
            if self.gui_pause.value:
                time.sleep(1.0 / 60.0)
                continue
            speed = float(self.gui_speed.value)
            accum += dt_wall * speed
            # Cap steps/frame so the solver can't run away from the
            # renderer on a slow machine.
            n_done = 0
            while accum >= h and n_done < 4:
                with self._world_lock:
                    self.world.step()
                accum -= h
                n_done += 1
            self._render_tick()

    def _render_tick(self):
        # Bodies — pre-allocated batched writes.
        descs = self.world._descs
        # Walk in the same order as construction.
        slot = 0
        for desc in descs:
            if desc.avbd_body is None:
                continue
            self._bp_buf[slot] = desc.dcr_body.position
            self._bw_buf[slot] = desc.dcr_body.orientation
            slot += 1
        # Reduced shelf surface — recompute deformed vertices each tick.
        deformed = _shelf_world_vertices(self.handle, self.rs.q)

        with self.server.atomic():
            self._batched_bodies.batched_positions = self._bp_buf
            self._batched_bodies.batched_wxyzs = self._bw_buf
            self.shelf_handle.vertices = deformed

        # HUD throttle.
        self._frame += 1
        if (self._frame % self._hud_interval) != 0:
            return
        coupler = self.world.reduced_support_coupler
        E_rigid = rigid_kinetic_energy(
            [d.dcr_body for d in self.world._descs])
        if coupler is not None:
            d_max_vec = coupler.last_probe_d_max
            dv_vec = coupler.last_probe_dv
            d_max = float(np.max(d_max_vec)) if d_max_vec.size > 0 else 0.0
            dv_max = float(np.max(np.abs(dv_vec))) if dv_vec.size > 0 else 0.0
            E_q = coupler.last_E_q
            E_inj = coupler.last_E_overlay_injected
            q_max = coupler.last_q_max_disp
            n_tracked = coupler.last_n_tracked_rows
            alpha_cap = coupler.last_alpha_cap
            E_src = coupler.last_E_src
            E_inj_cand = coupler.last_E_inj_candidate
            E_inj_real = coupler.last_E_inj_realised
            n_cooldown = coupler.last_n_cooldown_active
        else:
            d_max = dv_max = E_q = E_inj = q_max = 0.0
            n_tracked = 0
            alpha_cap = 1.0
            E_src = E_inj_cand = E_inj_real = 0.0
            n_cooldown = 0

        with self.server.atomic():
            self.gui_t.value = f"{self.world.time:.3f}"
            self.gui_step_ms.value = f"{self.world.last_step_ms:.2f}"
            self.gui_e_rigid.value = f"{E_rigid:.4f}"
            self.gui_e_q.value = f"{E_q:.4g}"
            self.gui_e_overlay.value = f"{E_inj:+.4g}"
            self.gui_q_max.value = f"{q_max:.4g}"
            self.gui_d_max.value = f"{d_max:.4g}"
            self.gui_dv.value = f"{dv_max:.4g}"
            self.gui_n_tracked.value = str(n_tracked)
            self.gui_alpha.value = f"{alpha_cap:.3f}"
            self.gui_e_src.value = f"{E_src:.4g}"
            self.gui_e_inj_cand.value = f"{E_inj_cand:.4g}"
            self.gui_e_inj_real.value = f"{E_inj_real:+.4g}"
            self.gui_n_cooldown.value = str(n_cooldown)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Live viser viewer for the Reduced-Coordinate AVBD "
                    "Support shelf scene.")
    p.add_argument("--port", type=int, default=8181)
    p.add_argument("--h", type=float, default=1.0 / 120.0)
    p.add_argument("--device", default="cpu")
    p.add_argument("--iterations", type=int, default=4)
    p.add_argument("--overlay", dest="overlay", action="store_true",
                   default=True)
    p.add_argument("--no-overlay", dest="overlay", action="store_false")
    p.add_argument("--r-modal", type=int, default=8)
    p.add_argument("--r-local", type=int, default=8)
    p.add_argument("--impactor-drop-height", type=float, default=0.30)
    p.add_argument("--impactor-v0-y", type=float, default=-1.0)
    args = p.parse_args(argv)

    handle = build_reduced_support_shelf(
        h=args.h,
        device=args.device,
        iterations=args.iterations,
        n_modes_global=args.r_modal,
        n_modes_local=args.r_local,
        overlay_enabled=args.overlay,
        restart_overlay_each_step=True,
        reduced_support_enabled=True,
        impactor_drop_height=args.impactor_drop_height,
        impactor_v0=(0.0, args.impactor_v0_y, 0.0),
    )

    print("[scene]", handle.name)
    print(f"  modal ω = {handle.rs.modal_omega}")
    print(f"  ω·h     = {handle.rs.modal_omega * args.h}")

    viewer = ReducedSupportViewer(args, handle)
    viewer.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
