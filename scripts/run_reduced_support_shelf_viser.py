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
from scenes.presets import (
    PRESETS, DEMO_STYLES, MATERIAL_YOUNGS,
    get_scene, get_style,
    format_scene_table, format_style_table,
    resolve_scene_kwargs, resolve_style_coupler_fields,
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


def _shelf_world_vertices(handle, q: np.ndarray,
                          exaggerate: float = 1.0) -> np.ndarray:
    """rest + exaggerate · U · q at every sample point.

    `exaggerate` is a *display-only* multiplier on the modal displacement
    — it does NOT touch the physics. Useful when q is physically tiny
    (130 µm) but we want to see the deformation in the browser. Use 1.0
    for honest display; 100.0 makes a wood-shelf impact clearly visible.
    """
    rs = handle.rs
    # einsum: (n_pts, 3, r) · (r,) → (n_pts, 3)
    disp = np.einsum("kij,j->ki", rs.U_points, q)
    return (rs.point_positions_rest + float(exaggerate) * disp
            ).astype(np.float32)


def _slab_faces(n_grid_x: int, n_grid_z: int) -> np.ndarray:
    """Closed-box mesh: top sheet + bottom sheet + 4 side strips.

    Vertex layout:
      [0 .. n_pts−1]              top    (same order as _shelf_faces)
      [n_pts .. 2·n_pts−1]        bottom (top with y -= render_thickness)

    Returns (n_tris, 3) uint32. Used only when --render-thickness > 0
    so the shelf is rendered as a thick slab without touching physics.
    """
    n_pts = n_grid_x * n_grid_z
    faces = []
    # Top sheet (CCW seen from +y, same as _shelf_faces).
    for i in range(n_grid_x - 1):
        for k in range(n_grid_z - 1):
            v00 = i * n_grid_z + k
            v10 = (i + 1) * n_grid_z + k
            v01 = i * n_grid_z + (k + 1)
            v11 = (i + 1) * n_grid_z + (k + 1)
            faces.append([v00, v11, v10])
            faces.append([v00, v01, v11])
    # Bottom sheet (reversed winding so outward normal is −y).
    for i in range(n_grid_x - 1):
        for k in range(n_grid_z - 1):
            v00 = n_pts + i * n_grid_z + k
            v10 = n_pts + (i + 1) * n_grid_z + k
            v01 = n_pts + i * n_grid_z + (k + 1)
            v11 = n_pts + (i + 1) * n_grid_z + (k + 1)
            faces.append([v00, v10, v11])
            faces.append([v00, v11, v01])
    # Side walls. Each connects a top edge segment (t0,t1) to its
    # bottom counterpart (b0,b1) via two triangles. Windings chosen so
    # outward normal points away from the slab interior.
    nx, nz = n_grid_x, n_grid_z
    # Edge i=0 (-x face, outward normal −x).
    for k in range(nz - 1):
        t0 = 0 * nz + k
        t1 = 0 * nz + (k + 1)
        b0 = n_pts + t0
        b1 = n_pts + t1
        faces.append([t0, b0, b1])
        faces.append([t0, b1, t1])
    # Edge i=nx-1 (+x face, outward normal +x).
    for k in range(nz - 1):
        t0 = (nx - 1) * nz + k
        t1 = (nx - 1) * nz + (k + 1)
        b0 = n_pts + t0
        b1 = n_pts + t1
        faces.append([t0, b1, b0])
        faces.append([t0, t1, b1])
    # Edge k=0 (-z face).
    for i in range(nx - 1):
        t0 = i * nz + 0
        t1 = (i + 1) * nz + 0
        b0 = n_pts + t0
        b1 = n_pts + t1
        faces.append([t0, b1, b0])
        faces.append([t0, t1, b1])
    # Edge k=nz-1 (+z face).
    for i in range(nx - 1):
        t0 = i * nz + (nz - 1)
        t1 = (i + 1) * nz + (nz - 1)
        b0 = n_pts + t0
        b1 = n_pts + t1
        faces.append([t0, b0, b1])
        faces.append([t0, b1, t1])
    return np.asarray(faces, dtype=np.uint32)


def _slab_world_vertices(handle, q: np.ndarray, render_thickness: float,
                         exaggerate: float = 1.0) -> np.ndarray:
    """2·n_pts vertices: top sheet from `_shelf_world_vertices`, bottom
    sheet = top shifted down by `render_thickness`.

    The bottom moves with the top by a constant offset — consistent with
    Kirchhoff plate kinematics (normals stay normal to the mid-surface).
    `render_thickness` is purely cosmetic and decoupled from the basis-
    build `shelf_thickness` parameter used for plate flexural rigidity.
    """
    top = _shelf_world_vertices(handle, q, exaggerate)
    bottom = top.copy()
    bottom[:, 1] -= float(render_thickness)
    return np.vstack([top, bottom]).astype(np.float32)


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

        # Mode detection — which coupler is live?
        #   "overlay" — the v1 ReducedSupportCoupler in non-static_only mode
        #   "static"  — ReducedSupportCoupler with static_only=True
        #   "coupled" — ReducedCoupledAVBDCoupler (the monolithic primal)
        #   "none"    — no coupler attached
        if self.world.reduced_coupled_coupler is not None:
            self.mode = "coupled"
        elif self.world.reduced_support_coupler is not None:
            self.mode = ("static"
                         if self.world.reduced_support_coupler.static_only
                         else "overlay")
        else:
            self.mode = "none"
        print(f"[viser] live coupler mode = {self.mode}")

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
        # Always use the closed-slab mesh so the "render thickness"
        # slider can sweep from 0 (degenerate, looks like a sheet) up
        # to any positive value with no remesh. The PHYSICS uses the
        # scene's shelf_thickness; this knob is cosmetic only.
        self._render_thickness = float(getattr(args, "render_thickness", 0.0))
        self._init_scene_mesh()

        # ---- Batched bodies (impactor + probes) ----
        self._init_batched_bodies()

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
            self.gui_substeps = self.server.gui.add_slider(
                "AVBD substeps", min=1, max=64, step=1,
                initial_value=int(getattr(self.world._solver, "substeps", 1)),
                hint="Substeps per macro step. 4 is the default; "
                     "higher = more numerical stability but slower.")
            self.gui_substeps.on_update(self._substeps_changed)

        # ---- Scene rebuild (drops material, thickness, impactor in/out) ----
        # Changing these triggers a world rebuild on Apply.
        from scenes.presets import (
            PRESETS as _PRESETS, MATERIAL_YOUNGS as _MAT_YOUNGS, get_scene)
        cur_scene_name = getattr(args, "scene", "research-baseline")
        cur_scene = get_scene(cur_scene_name)
        cur_material = getattr(args, "material", None) or cur_scene.default_material
        with self.server.gui.add_folder("Scene rebuild"):
            self.gui_rb_scene = self.server.gui.add_dropdown(
                "scene preset",
                options=tuple(_PRESETS.keys()),
                initial_value=cur_scene_name,
                hint="Picking a preset PRE-FILLS the sliders below. Press "
                     "Apply to rebuild the world with the chosen values.")
            self.gui_rb_scene.on_update(self._rb_scene_changed)
            self.gui_rb_mode = self.server.gui.add_dropdown(
                "mode",
                options=("plain", "coupled_modal_static",
                         "coupled_iir_modal", "old_dcr_postkick"),
                initial_value=getattr(args, "mode", "coupled_iir_modal"))
            self.gui_rb_material = self.server.gui.add_dropdown(
                "material",
                options=tuple(_MAT_YOUNGS.keys()),
                initial_value=cur_material)
            self.gui_rb_thickness_mm = self.server.gui.add_slider(
                "shelf thickness [mm]", min=1.0, max=80.0, step=0.5,
                initial_value=float(cur_scene.shelf_thickness * 1e3),
                hint="Physical plate thickness. ω ∝ h, q_static ∝ 1/h³. "
                     "Thicker → much stiffer → much smaller modal response.")
            self.gui_rb_imp_mass = self.server.gui.add_slider(
                "impactor mass [kg]", min=0.05, max=50.0, step=0.05,
                initial_value=float(cur_scene.impactor_mass))
            self.gui_rb_imp_v0 = self.server.gui.add_slider(
                "impactor v0_y [m/s]", min=-20.0, max=0.0, step=0.05,
                initial_value=float(cur_scene.impactor_v0_y))
            self.gui_rb_drop = self.server.gui.add_slider(
                "drop height [m]", min=0.0, max=2.0, step=0.01,
                initial_value=float(cur_scene.impactor_drop_height))
            self.gui_rb_apply = self.server.gui.add_button("Apply (rebuild)")
            self.gui_rb_apply.on_click(lambda _: self._rebuild_from_gui())
            self.gui_rb_status = self.server.gui.add_text(
                "rebuild status",
                initial_value=f"current: {cur_scene_name}/{cur_material}")

        with self.server.gui.add_folder("Display"):
            # Display-only multiplier on U·q for the rendered shelf
            # mesh. Physics is unaffected — same q drives contact, this
            # only scales what the browser shows.
            self.gui_q_exaggerate = self.server.gui.add_slider(
                "display q exaggerate",
                min=1.0, max=500.0, step=1.0,
                initial_value=float(args.display_q_exaggerate),
                hint="Render-only multiplier on U·q for the shelf mesh. "
                     "1 = honest; 100 = makes 130 µm look like 13 mm. "
                     "Does NOT touch the physics.")
            # In static/dynamic-split mode the contact constraint sees
            # only q_s, but the visual surface defaults to q_s + q_d so
            # impact ringing is visible. Side effect: when q_d swings the
            # surface upward, the rigid impactor (driven by q_s anchor)
            # can appear to dip below the rendered top — visual
            # penetration. Toggle to "q_s only (contact-honest)" to
            # render exactly the surface the constraint enforces.
            self.gui_render_q = self.server.gui.add_dropdown(
                "render mode",
                options=("q_s + q_d (visual total)",
                         "q_s only (contact-honest)"),
                initial_value="q_s + q_d (visual total)",
                hint="'q_s + q_d' shows the full modal state (ringing visible "
                     "but can look like penetration). 'q_s only' renders "
                     "exactly what the contact constraint sees — no "
                     "penetration, but no ringing either.")
            self.gui_render_thickness_mm = self.server.gui.add_slider(
                "render thickness [mm]", min=0.0, max=80.0, step=1.0,
                initial_value=float(self._render_thickness * 1e3),
                hint="Cosmetic only: render the shelf as a slab of this "
                     "thickness. 0 = single sheet. The PHYSICS still uses "
                     "the scene's shelf_thickness.")
            self.gui_render_thickness_mm.on_update(
                self._render_thickness_changed)

        with self.server.gui.add_folder("Reduced support"):
            self.gui_rs_enabled = self.server.gui.add_checkbox(
                "reduced support enabled",
                initial_value=bool(self.rs.enabled),
                hint="Off ⇒ vanilla AVBD only (no q-block, no overlay).")
            self.gui_rs_enabled.on_update(self._rs_enabled_changed)
            self.gui_mode_label = self.server.gui.add_text(
                "mode",
                initial_value=self.mode,
                hint="Live coupler mode: 'overlay' = v1 IIR; "
                     "'static' = BCD; 'coupled' = monolithic Newton. "
                     "Read-only.")
            # Overlay knobs only meaningful in 'overlay' mode.
            if self.mode == "overlay":
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
        # Only relevant in 'overlay' mode; static/coupled bypass all this.
        if self.mode == "overlay":
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
            self.gui_q_max = self.server.gui.add_text(
                "max support deflection [m]", initial_value="0.0")
            self.gui_q_norm = self.server.gui.add_text(
                "|q|", initial_value="0.0")
            # Drift-fix v1 split-mode HUD: separate static and dynamic
            # parts so you can see q_d ring on impact while q_s is the
            # steady sag.
            self.gui_q_s_norm = self.server.gui.add_text(
                "|q_s| (static sag)", initial_value="0.0")
            self.gui_q_d_norm = self.server.gui.add_text(
                "|q_d| (dynamic ring)", initial_value="0.0")
            self.gui_n_tracked = self.server.gui.add_text(
                "tracked rows", initial_value="0")
            # Overlay-only diagnostics — only shown in 'overlay' mode.
            if self.mode == "overlay":
                self.gui_e_q = self.server.gui.add_text(
                    "E_q [J]", initial_value="0.0")
                self.gui_e_overlay = self.server.gui.add_text(
                    "E_overlay_injected [J]", initial_value="0.0")
                self.gui_d_max = self.server.gui.add_text(
                    "max probe d_max [m]", initial_value="0.0")
                self.gui_dv = self.server.gui.add_text(
                    "max probe |Δv| [m/s]", initial_value="0.0")
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
            # Coupled-mode diagnostics.
            if self.mode == "coupled":
                self.gui_qdot = self.server.gui.add_text(
                    "|qdot| [1/s]", initial_value="0.0")
                self.gui_pen = self.server.gui.add_text(
                    "penetration [m]", initial_value="0.0")
                self.gui_cond = self.server.gui.add_text(
                    "cond(S)", initial_value="0.0")
                self.gui_dq = self.server.gui.add_text(
                    "|Δq| last iter", initial_value="0.0")
                self.gui_n_iter = self.server.gui.add_text(
                    "n_iter_solves", initial_value="0")
            # All modes: overlay events counter (must be 0 in static/coupled).
            self.gui_overlay_events = self.server.gui.add_text(
                "overlay events (cum)", initial_value="0")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)

    # ---- GUI callbacks ---------------------------------------------------

    # ------------------------------------------------------------------
    # Scene-rebuild helpers (used by both __init__ and Apply button).
    # ------------------------------------------------------------------

    def _init_scene_mesh(self):
        """Create the slab shelf mesh in viser. Call after self.rs is set."""
        self._shelf_faces = _slab_faces(N_GRID_X, N_GRID_Z)
        top0 = self.rs.point_positions_rest.astype(np.float32).copy()
        bot0 = top0.copy()
        bot0[:, 1] -= self._render_thickness
        self._shelf_rest_verts = np.vstack([top0, bot0])
        self.shelf_handle = self.server.scene.add_mesh_simple(
            "/reduced_shelf",
            vertices=self._shelf_rest_verts,
            faces=self._shelf_faces,
            color=(0.55, 0.50, 0.40),
            flat_shading=False, side="double",
        )

    def _init_batched_bodies(self):
        """Build the batched-mesh handle for impactor + probes. Walks the
        world's descriptor list, picks colors per role."""
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
            if di == self.handle.impactor_idx:
                colors_list.append((220, 60, 60))
            elif di in self.handle.probe_indices:
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

    def _swap_handle(self, new_handle):
        """Replace the live world+handle with `new_handle` (which is a
        freshly built ShelfSceneHandle). Tears down and rebuilds the
        viser scene mesh + batched bodies. Resets the reset-snapshot to
        the new world's initial state.

        Must be called with `self._world_lock` held by the caller.
        """
        # Remove old viser elements (they retain their own scene state).
        try:    self.shelf_handle.remove()
        except Exception: pass
        try:    self._batched_bodies.remove()
        except Exception: pass

        # Swap references.
        self.handle = new_handle
        self.world  = new_handle.world
        self.rs     = new_handle.rs

        # Detect new mode.
        if self.world.reduced_coupled_coupler is not None:
            self.mode = "coupled"
        elif self.world.reduced_support_coupler is not None:
            self.mode = ("static"
                         if self.world.reduced_support_coupler.static_only
                         else "overlay")
        else:
            self.mode = "none"

        # Re-init viser elements.
        self._init_scene_mesh()
        self._init_batched_bodies()

        # New snapshot for the reset button.
        self._initial_snapshot = self.world.snapshot()
        self._initial_q = self.rs.q.copy()
        self._initial_qdot = self.rs.qdot.copy()
        self._frame = 0
        if hasattr(self, "gui_mode_label"):
            try: self.gui_mode_label.value = self.mode
            except Exception: pass
        print(f"[rebuild] new scene attached  mode={self.mode}  "
              f"h_t={self.rs.point_positions_rest.shape[0]} pts")

    def _iters_changed(self, _evt):
        with self._world_lock:
            self.world.avbd_iterations = int(self.gui_iters.value)
            self.world._solver.iterations = int(self.gui_iters.value)
            self.world._solver._graph = None

    def _substeps_changed(self, _evt):
        with self._world_lock:
            n = max(1, int(self.gui_substeps.value))
            if hasattr(self.world, "avbd_substeps"):
                self.world.avbd_substeps = n
            self.world._solver.substeps = n
            self.world._solver._graph = None

    def _render_thickness_changed(self, _evt):
        # No lock needed — only affects the next mesh update on the GUI
        # thread; mesh updates happen in the GUI tick callback.
        self._render_thickness = max(
            0.0, float(self.gui_render_thickness_mm.value) * 1e-3)

    def _rb_scene_changed(self, _evt):
        """When the user picks a different scene preset in the rebuild
        dropdown, pre-populate the other rebuild controls from that
        preset's defaults. The user can then tweak and press Apply."""
        from scenes.presets import get_scene
        p = get_scene(self.gui_rb_scene.value)
        # Push values into the other rebuild widgets.
        try:
            self.gui_rb_material.value     = p.default_material
            self.gui_rb_thickness_mm.value = float(p.shelf_thickness * 1e3)
            self.gui_rb_imp_mass.value     = float(p.impactor_mass)
            self.gui_rb_imp_v0.value       = float(p.impactor_v0_y)
            self.gui_rb_drop.value         = float(p.impactor_drop_height)
            self.gui_rb_status.value = (
                f"preset: {p.name} (h_t={p.shelf_thickness*1e3:.1f} mm, "
                f"E={p.default_material}). Press Apply.")
        except Exception as e:
            self.gui_rb_status.value = f"preset update failed: {e}"

    def _rebuild_from_gui(self):
        """Read the rebuild widgets, build a fresh handle, swap it in."""
        from scenes.presets import (
            get_scene, get_style, MATERIAL_YOUNGS,
            resolve_scene_kwargs, resolve_style_coupler_fields,
        )
        try:
            scene_name = self.gui_rb_scene.value
            preset = get_scene(scene_name)
            style = get_style(getattr(self.args, "demo_style", "honest"))
            material = self.gui_rb_material.value
            mode = self.gui_rb_mode.value

            scene_kw = resolve_scene_kwargs(
                preset,
                material=material,
                shelf_thickness=float(self.gui_rb_thickness_mm.value) * 1e-3,
                impactor_mass=float(self.gui_rb_imp_mass.value),
                impactor_drop_height=float(self.gui_rb_drop.value),
                impactor_v0=(0.0, float(self.gui_rb_imp_v0.value), 0.0),
            )
            coupler_kw = resolve_style_coupler_fields(style)
            with self._world_lock:
                # Pause the sim thread briefly while we rebuild.
                was_paused = self.gui_pause.value
                self.gui_pause.value = True

                new_handle = build_reduced_support_shelf(
                    h=float(self.args.h),
                    device=str(self.args.device),
                    iterations=int(getattr(self.gui_iters, "value",
                                          self.args.iterations)),
                    avbd_substeps=int(getattr(self.gui_substeps, "value",
                                              self.args.substeps)),
                    reduced_support_enabled=(mode != "plain"),
                    reduced_static_support=(mode == "coupled_modal_static"),
                    coupled_avbd=(mode == "coupled_iir_modal"),
                    dcr_postkick=(mode == "old_dcr_postkick"),
                    rayleigh_alpha0=0.0,
                    rayleigh_alpha1=5.0e-6,
                    to_eigenbasis=(getattr(self.args, "reduced_basis",
                                           "synthetic") == "eigen"),
                    modal_static_lp_tau=float(getattr(
                        self.args, "modal_static_lp_tau", 0.05)),
                    **scene_kw,
                    **coupler_kw,
                )

                self._swap_handle(new_handle)
                self.gui_pause.value = was_paused
            self.gui_rb_status.value = (
                f"OK — {scene_name}/{material}, "
                f"h_t={self.gui_rb_thickness_mm.value:.1f} mm")
        except Exception as e:
            self.gui_rb_status.value = f"REBUILD FAILED: {e}"
            print(f"[rebuild] FAILED: {e!r}")

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
            if hasattr(self.world, "reduced_coupled_log"):
                self.world.reduced_coupled_log.clear()
            # Reset overlay-event counter on whichever coupler is live.
            cc = self._live_coupler()
            if cc is not None and hasattr(cc, "cum_overlay_events_fired"):
                cc.cum_overlay_events_fired = 0
        self._render_tick()

    def _live_coupler(self):
        """Return whichever reduced-support coupler is currently attached.
        Mode-aware: returns the ReducedCoupledAVBDCoupler in coupled mode,
        the ReducedSupportCoupler in overlay/static modes, or None.
        """
        if self.world.reduced_coupled_coupler is not None:
            return self.world.reduced_coupled_coupler
        return self.world.reduced_support_coupler

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
        # Display-only exaggeration (slider) does not touch physics.
        # Always use the slab vertex layout (top + bottom) — at
        # _render_thickness=0 it collapses to a degenerate sheet that
        # the renderer handles fine.
        #
        # Render-mode toggle: "q_s only" shows the contact-honest surface
        # (no visible penetration); the default "q_s + q_d" shows the full
        # modal state including transient ringing.
        if self.gui_render_q.value.startswith("q_s only"):
            q_for_render = self.rs.q_s
        else:
            q_for_render = self.rs.q
        deformed = _slab_world_vertices(
            self.handle, q_for_render,
            render_thickness=self._render_thickness,
            exaggerate=float(self.gui_q_exaggerate.value))

        # Defensive: rebuild thread may swap shelf_handle / _batched_bodies
        # mid-tick. If that happens, the old handle has been removed and
        # any assignment raises RuntimeError. Skip the frame — the next
        # tick will see the new handles and render correctly.
        try:
            with self.server.atomic():
                self._batched_bodies.batched_positions = self._bp_buf
                self._batched_bodies.batched_wxyzs = self._bw_buf
                self.shelf_handle.vertices = deformed
        except RuntimeError:
            return

        # HUD throttle.
        self._frame += 1
        if (self._frame % self._hud_interval) != 0:
            return
        E_rigid = rigid_kinetic_energy(
            [d.dcr_body for d in self.world._descs])
        coupler = self._live_coupler()

        # Common diagnostics (every mode exposes these).
        q_max = 0.0
        q_norm = 0.0
        q_s_norm = 0.0
        q_d_norm = 0.0
        n_tracked = 0
        overlay_events_cum = 0
        if coupler is not None:
            q_max = float(getattr(coupler, "last_max_support_deflection",
                                  getattr(coupler, "last_q_max_disp", 0.0)))
            q_norm = float(getattr(coupler, "last_q_norm", 0.0))
            if q_norm == 0.0 and hasattr(coupler, "rs"):
                q_norm = float(np.linalg.norm(coupler.rs.q))
            q_s_norm = float(getattr(coupler, "last_q_s_norm", 0.0))
            q_d_norm = float(getattr(coupler, "last_q_d_norm", 0.0))
            n_tracked = int(getattr(coupler, "last_n_tracked_rows", 0))
            overlay_events_cum = int(getattr(
                coupler, "cum_overlay_events_fired", 0))

        with self.server.atomic():
            self.gui_t.value = f"{self.world.time:.3f}"
            self.gui_step_ms.value = f"{self.world.last_step_ms:.2f}"
            self.gui_e_rigid.value = f"{E_rigid:.4f}"
            self.gui_q_max.value = f"{q_max:.4g}"
            self.gui_q_norm.value = f"{q_norm:.4g}"
            self.gui_q_s_norm.value = f"{q_s_norm:.4g}"
            self.gui_q_d_norm.value = f"{q_d_norm:.4g}"
            self.gui_n_tracked.value = str(n_tracked)
            self.gui_overlay_events.value = str(overlay_events_cum)

            # See note on the "coupled" branch below — same torn-read
            # protection: if a rebuild swapped to a different coupler,
            # missing attrs are silently skipped this tick.
            if (self.mode == "overlay" and coupler is not None
                and hasattr(coupler, "last_probe_d_max")):
                d_max_vec = coupler.last_probe_d_max
                dv_vec = coupler.last_probe_dv
                d_max = (float(np.max(d_max_vec))
                         if d_max_vec.size > 0 else 0.0)
                dv_max = (float(np.max(np.abs(dv_vec)))
                          if dv_vec.size > 0 else 0.0)
                self.gui_e_q.value = (
                    f"{getattr(coupler, 'last_E_q', 0.0):.4g}")
                self.gui_e_overlay.value = (
                    f"{getattr(coupler, 'last_E_overlay_injected', 0.0):+.4g}")
                self.gui_d_max.value = f"{d_max:.4g}"
                self.gui_dv.value = f"{dv_max:.4g}"
                self.gui_alpha.value = (
                    f"{getattr(coupler, 'last_alpha_cap', 0.0):.3f}")
                self.gui_e_src.value = (
                    f"{getattr(coupler, 'last_E_src', 0.0):.4g}")
                self.gui_e_inj_cand.value = (
                    f"{getattr(coupler, 'last_E_inj_candidate', 0.0):.4g}")
                self.gui_e_inj_real.value = (
                    f"{getattr(coupler, 'last_E_inj_realised', 0.0):+.4g}")
                self.gui_n_cooldown.value = str(
                    getattr(coupler, 'last_n_cooldown_active', 0))

            # Render-thread reads self.mode and self.world WITHOUT the
            # world lock. A concurrent _swap_handle() can swap the live
            # coupler before self.mode is updated — i.e. _live_coupler()
            # may already return a ReducedSupportCoupler while
            # self.mode == "coupled" is still the stale value. Hence
            # every field access here is getattr-with-default; missing
            # attrs are silently skipped until the next tick observes
            # the updated self.mode. (Not a logic bug — just a torn read
            # across a non-atomic rebuild.)
            if self.mode == "coupled" and coupler is not None:
                self.gui_qdot.value = (
                    f"{getattr(coupler, 'last_qdot_norm', 0.0):.3e}")
                self.gui_pen.value = (
                    f"{getattr(coupler, 'last_contact_residual', 0.0):.3e}")
                self.gui_cond.value = (
                    f"{getattr(coupler, 'last_Schur_condition_estimate', 0.0):.2e}")
                self.gui_dq.value = (
                    f"{getattr(coupler, 'last_dq_norm', 0.0):.3e}")
                self.gui_n_iter.value = str(
                    getattr(coupler, 'last_n_iter_solves', 0))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Live viser viewer for the Reduced-Coordinate AVBD "
                    "Support shelf scene. Pick a --scene preset for "
                    "scene parameters, --demo-style for visual amplification.")

    # ---- Listing flags ----
    p.add_argument("--list-scenes", action="store_true",
                   help="Print available --scene presets and exit.")
    p.add_argument("--list-styles", action="store_true",
                   help="Print available --demo-style presets and exit.")

    # ---- Top-level preset selectors ----
    p.add_argument("--scene", choices=list(PRESETS.keys()),
                   default="research-baseline",
                   help="Scene preset (geometry + impactor). Default: "
                        "research-baseline (current 5 mm shelf).")
    p.add_argument("--demo-style", choices=list(DEMO_STYLES.keys()),
                   default="honest",
                   help="Demo-amplification preset. Default: honest "
                        "(γ=1, no exaggeration).")

    # ---- Architecture mode ----
    p.add_argument("--mode",
                   choices=["plain", "old_dcr_postkick",
                            "coupled_modal_static", "coupled_iir_modal"],
                   default=None,
                   help="Modal coupling architecture. Default: "
                        "coupled_iir_modal (exact resonator inside AVBD).")

    # ---- Scene overrides (None → use preset value) ----
    scene_grp = p.add_argument_group("Scene overrides")
    scene_grp.add_argument("--material",
                           choices=list(MATERIAL_YOUNGS.keys()),
                           default=None,
                           help="Override preset's default material.")
    scene_grp.add_argument("--shelf-thickness", type=float, default=None,
                           help="Override preset's shelf thickness (m).")
    scene_grp.add_argument("--shelf-length", type=float, default=None)
    scene_grp.add_argument("--shelf-width", type=float, default=None)
    scene_grp.add_argument("--impactor-mass", type=float, default=None)
    scene_grp.add_argument("--impactor-drop-height", type=float, default=None)
    scene_grp.add_argument("--impactor-v0-y", type=float, default=None)
    scene_grp.add_argument("--probe-z-offset", type=float, default=None)

    # ---- Demo-style overrides (None → use style value) ----
    demo_grp = p.add_argument_group("Demo-style overrides")
    demo_grp.add_argument("--support-response-gain", type=float, default=None,
                          help="Modal impedance scaling. (Mq, Dq, Kq) ← /g; "
                               "ω_i, ζ_i invariant. Weak effect (~1.2× at g=8).")
    demo_grp.add_argument("--modal-damping-scale", type=float, default=None,
                          help="Multiplier on Dq → ζ_i.")
    demo_grp.add_argument("--display-q-exaggerate", type=float, default=None,
                          help="Render-only multiplier on U·q. Physics "
                               "unaffected. 1=honest, 100=makes 130 µm look "
                               "like 13 mm.")

    # ---- Render-only ----
    p.add_argument("--render-thickness", type=float, default=None,
                   help="Cosmetic slab extrusion (m). 0=single sheet. None "
                        "(default) → matches scene's shelf_thickness for a "
                        "honest 1:1 render. Physics is unaffected.")

    # ---- Reduced basis choice ----
    p.add_argument("--reduced-basis", choices=["synthetic", "eigen"],
                   default="eigen",
                   help="Modal basis used for the reduced support. "
                        "'synthetic' = sine bending + Gaussian bumps "
                        "(coupled). 'eigen' = generalized eigenbasis "
                        "(M̂=I, K̂=Ω²; diagonal per-mode IIR resonator). "
                        "Physics is invariant; 'eigen' is slightly faster "
                        "and matches the DCR paper framing.")

    # ---- Static / dynamic split tuning ----
    p.add_argument(
        "--modal-static-lp-tau", type=float, default=0.05,
        help="EMA time constant (s) for the high-pass that drives q_d. "
             "τ ≈ 50 ms (3 Hz corner). Smaller τ → q_d absorbs faster "
             "transients; larger τ → resting load fully absorbed by q_s.")

    # ---- Solver tuning (advanced) ----
    solver_grp = p.add_argument_group("Solver (advanced)")
    solver_grp.add_argument("--substeps", type=int, default=4,
                            help="AVBD substeps per macro step. 4 is the "
                                 "default; 16+ for stiff IIR scenes that "
                                 "need to resolve high-frequency modes.")
    solver_grp.add_argument("--iterations", type=int, default=4,
                            help="AVBD primal/dual iterations per substep.")

    # ---- Infrastructure ----
    infra_grp = p.add_argument_group("Infrastructure")
    infra_grp.add_argument("--port", type=int, default=8181)
    infra_grp.add_argument("--device", default="cpu")
    infra_grp.add_argument("--h", type=float, default=1.0 / 120.0,
                           help="Macro time step.")

    # ---- Deprecated (kept for one cycle) ----
    dep_grp = p.add_argument_group("Deprecated")
    dep_grp.add_argument("--integrator", choices=["bdf1", "newmark", "iir"],
                         default=None,
                         help="DEPRECATED. Maps to --mode.")
    dep_grp.add_argument("--reduced-static-support", dest="static_only",
                         action="store_true", default=False,
                         help="DEPRECATED: use --mode coupled_modal_static.")
    dep_grp.add_argument("--reduced-coupled-avbd", dest="coupled_avbd",
                         action="store_true", default=False,
                         help="DEPRECATED: use --mode coupled_iir_modal.")
    dep_grp.add_argument("--youngs", type=float, default=None,
                         help="DEPRECATED: use --material.")
    dep_grp.add_argument("--r-modal", type=int, default=None,
                         help="DEPRECATED: per-scene preset.")
    dep_grp.add_argument("--r-local", type=int, default=None,
                         help="DEPRECATED: per-scene preset.")

    args = p.parse_args(argv)

    # ---- Listing short-circuits ----
    if args.list_scenes:
        print("Available --scene presets:")
        print(format_scene_table())
        return 0
    if args.list_styles:
        print("Available --demo-style presets:")
        print(format_style_table())
        return 0

    # Resolve mode from --mode (primary) or fall back to legacy flags.
    if args.mode is not None:
        mode = args.mode
    elif args.static_only and args.coupled_avbd:
        p.error("--reduced-static-support and --reduced-coupled-avbd "
                "are mutually exclusive.")
    elif args.static_only:
        mode = "coupled_modal_static"
    elif args.coupled_avbd:
        mode = "coupled_iir_modal"
    elif args.integrator is not None:
        mode = "coupled_iir_modal"
    else:
        mode = "coupled_iir_modal"   # safe default
    args.mode = mode

    # Resolve preset + style + overrides.
    scene = get_scene(args.scene)
    style = get_style(args.demo_style)

    # Render thickness: None → match the scene's render thickness, which
    # itself defaults to shelf_thickness if the preset doesn't override.
    render_thickness = args.render_thickness
    if render_thickness is None:
        render_thickness = (scene.default_render_thickness
                            if scene.default_render_thickness is not None
                            else scene.shelf_thickness)
    args.render_thickness = float(render_thickness)

    # Resolve display_q_exaggerate (style → CLI override).
    args.display_q_exaggerate = (
        args.display_q_exaggerate
        if args.display_q_exaggerate is not None
        else style.display_q_exaggerate)

    # Build scene kwargs from preset + overrides.
    scene_kw = resolve_scene_kwargs(
        scene,
        material=args.material,
        shelf_thickness=args.shelf_thickness,
        shelf_length=args.shelf_length,
        shelf_width=args.shelf_width,
        impactor_mass=args.impactor_mass,
        impactor_drop_height=args.impactor_drop_height,
        impactor_v0=((0.0, args.impactor_v0_y, 0.0)
                     if args.impactor_v0_y is not None else None),
        n_modes_global=args.r_modal,
        n_modes_local=args.r_local,
        youngs=args.youngs,
    )
    # probe_z_offset override: rebuild probe_xz if user requested.
    if args.probe_z_offset is not None:
        L = scene_kw["shelf_length"]
        scene_kw["probe_xz"] = [
            (-0.40 * L, float(args.probe_z_offset)),
            (+0.40 * L, float(args.probe_z_offset)),
        ]

    coupler_kw = resolve_style_coupler_fields(style, overrides={
        "modal_impedance_scale":     args.support_response_gain,
        "modal_damping_scale":       args.modal_damping_scale,
    })

    # Header banner.
    mat = args.material or scene.default_material
    print(f"[scene] {scene.name}  material={mat}  "
          f"(E = {MATERIAL_YOUNGS[mat]:.2e} Pa, "
          f"h_t={scene_kw['shelf_thickness']*1e3:.1f} mm)")
    print(f"[style] {style.name}  "
          f"g={coupler_kw['modal_impedance_scale']:.3g}  "
          f"exaggerate={args.display_q_exaggerate:.3g}")
    print(f"[mode]  {mode}  substeps={args.substeps}  iter={args.iterations}")

    handle = build_reduced_support_shelf(
        h=args.h,
        device=args.device,
        iterations=args.iterations,
        avbd_substeps=args.substeps,
        overlay_enabled=False,
        restart_overlay_each_step=True,
        reduced_support_enabled=(mode != "plain"),
        reduced_static_support=(mode == "coupled_modal_static"),
        coupled_avbd=(mode == "coupled_iir_modal"),
        dcr_postkick=(mode == "old_dcr_postkick"),
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=5.0e-6,
        to_eigenbasis=(getattr(args, "reduced_basis", "synthetic") == "eigen"),
        **scene_kw,
        **coupler_kw,
    )

    print(f"  mode = {mode}")

    print("[scene]", handle.name)
    print(f"  modal ω = {handle.rs.modal_omega}")
    print(f"  ω·h     = {handle.rs.modal_omega * args.h}")

    viewer = ReducedSupportViewer(args, handle)
    viewer.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
