#!/usr/bin/env python3
"""AVBD-native viser launcher for the passive-DCR demo scenes.

Replaces the polyscope-based recorded-playback flow in
`scripts/run_scenes.py` with:
  * `AVBDDCRWorld` (AVBD warp solver under the hood)
  * `PassiveDCRCoupler` in "energy_prescribed_patch" mode (spec §1, §9)
  * viser browser viewer with live solver thread + GUI knobs

Usage:
    uv run python scripts/run_scenes_avbd.py truck
    uv run python scripts/run_scenes_avbd.py shelf --device cpu
    uv run python scripts/run_scenes_avbd.py ledge --port 8181

Open http://localhost:<port> (default 8181) in a browser.

Spec mapping:
  - prompts/avbd_native_dcr_followup_spec_v2.md §1, §9
  - ~/.claude/plans/here-i-want-to-kind-valiant.md
"""
from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass

import numpy as np

from dcr.avbd import AVBDDCRWorld
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.fem import Material, FEMModel
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy


# ---------------------------------------------------------------------------
# Scene primitives
# ---------------------------------------------------------------------------

@dataclass
class SceneBox:
    """Per-body viewer metadata."""
    name: str
    body_idx: int
    half_extents: tuple[float, float, float]
    color: tuple[float, float, float]


def _fix_corners(mesh) -> np.ndarray:
    v = mesh.vertices
    tol = 1e-8
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    mask = (
        ((np.abs(v[:, 0] - xmin) < tol) | (np.abs(v[:, 0] - xmax) < tol))
        & ((np.abs(v[:, 2] - zmin) < tol) | (np.abs(v[:, 2] - zmax) < tol))
    )
    return np.where(mask)[0].astype(np.int32)


def _fix_one_edge(mesh) -> np.ndarray:
    """Cantilever boundary: pin only the -x edge."""
    v = mesh.vertices
    tol = 1e-8
    xmin = v[:, 0].min()
    return np.where(np.abs(v[:, 0] - xmin) < tol)[0].astype(np.int32)


# ---------------------------------------------------------------------------
# Scene builders
# ---------------------------------------------------------------------------

def build_truck_scene(
    device: str, h: float, eta: float, beta: float,
    causal_gating: bool, modal_decay_gamma: float,
    enable_phase_b: bool = False, ms_beta: float = 0.1,
    use_bj: bool = False,
) -> tuple[AVBDDCRWorld, PassiveDCRCoupler, list[SceneBox], object, str]:
    """Heavy objects dropped sequentially on a wood-like 'road'."""
    world = AVBDDCRWorld(
        h=h, eta=eta, device=device,
        avbd_iterations=10, avbd_substeps=4,
        enable_moving_support_pass=enable_phase_b,
        moving_support_beta=ms_beta,
        moving_support_use_bj=use_bj,
    )
    ground_top = 0.03
    floor_idx = world.add_floor(floor_y=ground_top, friction=0.6, name="road")

    # FEM ground for the modal coupler (E=10 GPa, ρ=500 kg/m^3 wood).
    mesh = make_slab_tet_mesh(
        length=2.5, width=1.5, height=0.06, nx=16, ny=10, nz=2)
    mat = Material(E=10.0e9, nu=0.3, rho=500.0)
    fem = FEMModel(
        mesh=mesh, material=mat,
        fixed_nodes=_fix_corners(mesh),
        alpha0=2.0, alpha1=1e-5,
    )
    modal = ModalAnalysis(fem=fem, num_modes=15)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=floor_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=beta,
        deformed_normal_method=("barbic_james" if use_bj else "patch_fit"),
        causal_gating=causal_gating,
        modal_decay_gamma=modal_decay_gamma,
    )
    world.add_passive_coupler(coupler)

    boxes: list[SceneBox] = []
    drops = [
        ("drop_light", -0.5, 0.10,  20.0, (0.4, 0.6, 0.9)),
        ("drop_mid",   -0.3, 0.50,  50.0, (0.3, 0.4, 0.8)),
        ("drop_heavy", -0.05, 2.40, 100.0, (0.2, 0.25, 0.6)),
    ]
    drop_h = (0.10, 0.07, 0.08)
    for name, dx, dy, mass, color in drops:
        idx = world.add_box(
            mass=mass, half_extents=drop_h,
            position=(dx, ground_top + drop_h[1] + dy, 0.0),
            friction=0.6,
            name=name,
        )
        boxes.append(SceneBox(name=name, body_idx=idx,
                              half_extents=drop_h, color=color))

    # Cones (5 small) and lumber stack (4 blocks).
    cone_h = (0.025, 0.04, 0.025)
    for ci, cz in enumerate([-0.4, -0.2, 0.0, 0.2, 0.4]):
        idx = world.add_box(
            mass=0.3, half_extents=cone_h,
            position=(0.6, ground_top + cone_h[1] + 0.001, cz),
            friction=0.5,
            name=f"cone_{ci}",
        )
        boxes.append(SceneBox(name=f"cone_{ci}", body_idx=idx,
                              half_extents=cone_h, color=(1.0, 0.5, 0.0)))

    lumber_h = (0.06, 0.025, 0.12)
    for li in range(4):
        y = ground_top + lumber_h[1] + li * 2 * lumber_h[1] + 0.001 * (li + 1)
        idx = world.add_box(
            mass=2.0, half_extents=lumber_h,
            position=(0.3, y, 0.0), friction=0.7,
            name=f"lumber_{li}",
        )
        boxes.append(SceneBox(name=f"lumber_{li}", body_idx=idx,
                              half_extents=lumber_h, color=(0.6, 0.35, 0.15)))

    return world, coupler, boxes, mesh, "Road Impact (AVBD + patch DCR)"


def build_shelf_scene(
    device: str, h: float, eta: float, beta: float,
    causal_gating: bool, modal_decay_gamma: float,
    enable_phase_b: bool = False, ms_beta: float = 0.1,
    use_bj: bool = False,
) -> tuple[AVBDDCRWorld, PassiveDCRCoupler, list[SceneBox], object, str]:
    """Heavy box drops on a soft cantilever shelf; books topple."""
    world = AVBDDCRWorld(
        h=h, eta=eta, device=device,
        avbd_iterations=10, avbd_substeps=4,
        enable_moving_support_pass=enable_phase_b,
        moving_support_beta=ms_beta,
        moving_support_use_bj=use_bj,
    )
    shelf_top = 0.015
    shelf_idx = world.add_floor(
        floor_y=shelf_top, friction=0.5, name="shelf")

    mesh = make_slab_tet_mesh(
        length=0.8, width=0.3, height=0.03, nx=12, ny=5, nz=2)
    mat = Material(E=0.5e9, nu=0.3, rho=600.0)
    fem = FEMModel(
        mesh=mesh, material=mat,
        fixed_nodes=_fix_one_edge(mesh),
        alpha0=3.0, alpha1=1e-5,
    )
    modal = ModalAnalysis(fem=fem, num_modes=12)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=shelf_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=beta,
        deformed_normal_method=("barbic_james" if use_bj else "patch_fit"),
        causal_gating=causal_gating,
        modal_decay_gamma=modal_decay_gamma,
    )
    world.add_passive_coupler(coupler)

    boxes: list[SceneBox] = []
    book_colors = [
        (0.8, 0.2, 0.2), (0.2, 0.6, 0.2), (0.2, 0.2, 0.8),
        (0.7, 0.5, 0.1), (0.6, 0.2, 0.6),
    ]
    book_h = (0.005, 0.04, 0.03)
    for bi in range(5):
        bx = -0.15 + bi * 0.04
        idx = world.add_box(
            mass=1.3, half_extents=book_h,
            position=(bx, shelf_top + book_h[1] + 0.001, 0.0),
            friction=0.3,
            name=f"book_{bi}",
        )
        boxes.append(SceneBox(name=f"book_{bi}", body_idx=idx,
                              half_extents=book_h, color=book_colors[bi]))

    drop_h = (0.05, 0.05, 0.05)
    idx = world.add_box(
        mass=8.0, half_extents=drop_h,
        position=(0.15, shelf_top + drop_h[1] + 0.6, 0.0),
        friction=0.5,
        name="drop",
    )
    boxes.append(SceneBox(name="drop", body_idx=idx,
                          half_extents=drop_h, color=(0.3, 0.3, 0.3)))
    return world, coupler, boxes, mesh, "Bookshelf Drop (AVBD + patch DCR)"


def build_ledge_scene(
    device: str, h: float, eta: float, beta: float,
    causal_gating: bool, modal_decay_gamma: float,
    enable_phase_b: bool = False, ms_beta: float = 0.1,
    use_bj: bool = False,
) -> tuple[AVBDDCRWorld, PassiveDCRCoupler, list[SceneBox], object, str]:
    """Boulder hits a stone cantilever ledge; balanced pillars fall."""
    world = AVBDDCRWorld(
        h=h, eta=eta, device=device,
        avbd_iterations=10, avbd_substeps=4,
        enable_moving_support_pass=enable_phase_b,
        moving_support_beta=ms_beta,
        moving_support_use_bj=use_bj,
    )
    ledge_top = 0.04
    ledge_idx = world.add_floor(
        floor_y=ledge_top, friction=0.5, name="ledge")

    mesh = make_slab_tet_mesh(
        length=1.2, width=0.8, height=0.08, nx=12, ny=8, nz=2)
    # FEM parameters matched to the truck scene: stiff-but-light wood
    # (E=10 GPa, ρ=500), α0=2.0 Rayleigh, 15 modes. Was ρ=2500, α0=1.0,
    # 12 modes — the heavier slab gave a weak modal projection (Φᵀλ tiny)
    # so the patch back-reaction could not pump. With the truck's light
    # material the ledge couples strongly, exposing the same runaway.
    mat = Material(E=10.0e9, nu=0.3, rho=500.0)
    fem = FEMModel(
        mesh=mesh, material=mat,
        fixed_nodes=_fix_one_edge(mesh),
        alpha0=2.0, alpha1=1e-5,
    )
    modal = ModalAnalysis(fem=fem, num_modes=15)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=ledge_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=beta,
        deformed_normal_method=("barbic_james" if use_bj else "patch_fit"),
        causal_gating=causal_gating,
        modal_decay_gamma=modal_decay_gamma,
    )
    world.add_passive_coupler(coupler)

    boxes: list[SceneBox] = []
    ped_h = (0.06, 0.05, 0.06)
    idx = world.add_box(
        mass=5.0, half_extents=ped_h,
        position=(0.0, ledge_top + ped_h[1] + 0.001, 0.0),
        friction=0.4, name="pedestal",
    )
    boxes.append(SceneBox(name="pedestal", body_idx=idx,
                          half_extents=ped_h, color=(0.55, 0.45, 0.35)))

    pillar_h = (0.01, 0.04, 0.01)
    pedestal_top = ledge_top + 2 * ped_h[1] + 0.001
    offsets = [(0.04, 0.0, -0.035), (0.04, 0.0, 0.00), (0.04, 0.0, 0.035)]
    colors = [(0.7, 0.3, 0.3), (0.3, 0.6, 0.3), (0.3, 0.3, 0.7)]
    for si, ((sx, _, sz), color) in enumerate(zip(offsets, colors)):
        idx = world.add_box(
            mass=0.5, half_extents=pillar_h,
            position=(sx, pedestal_top + pillar_h[1] + 0.001, sz),
            friction=0.5, name=f"box_{si}",
        )
        boxes.append(SceneBox(name=f"box_{si}", body_idx=idx,
                              half_extents=pillar_h, color=color))

    boulder_h = 0.08
    idx = world.add_box(
        mass=50.0, half_extents=(boulder_h, boulder_h, boulder_h),
        position=(0.30, ledge_top + boulder_h + 0.8, 0.0),
        friction=0.5, name="boulder",
    )
    boxes.append(SceneBox(name="boulder", body_idx=idx,
                          half_extents=(boulder_h, boulder_h, boulder_h),
                          color=(0.5, 0.4, 0.3)))
    return world, coupler, boxes, mesh, "Cliff Ledge Rockfall (AVBD + patch DCR)"


SCENES = {
    "truck": build_truck_scene,
    "shelf": build_shelf_scene,
    "ledge": build_ledge_scene,
}


# ---------------------------------------------------------------------------
# Viser viewer
# ---------------------------------------------------------------------------

def _wxyz_for_box(world: AVBDDCRWorld, body_idx: int) -> tuple[float, ...]:
    q = world._descs[body_idx].dcr_body.orientation  # wxyz
    return (float(q[0]), float(q[1]), float(q[2]), float(q[3]))


def _surface_vertex_world_positions(
    coupler: PassiveDCRCoupler,
    mesh,
) -> np.ndarray:
    """Surface-vertex positions in world coords (rest + Φ·q displacement).

    The elastic body sits at the world origin in the AVBD world (we
    represent it as a planar floor; the surface mesh visualizes the
    *modal deformation* on top of that plane).
    """
    surface = coupler._surface  # cached TriMesh of the slab surface
    verts = surface.vertices.copy()
    U_surf = coupler.modal.U_surf  # (3*n_surf_free, m)
    q = coupler._stepper.q         # (m,)
    surf_disp_flat = U_surf @ q    # (3*n_surf_free,)
    # Each surface vertex's index into surf_disp_flat:
    surf_idx_map = coupler._vert_to_surf_idx  # vertex -> surf-row (-1 = fixed)
    for vi in range(verts.shape[0]):
        si = surf_idx_map[vi]
        if si >= 0:
            base = 3 * si
            verts[vi] += surf_disp_flat[base:base + 3]
    return verts


class AVBDDCRViewer:
    """Browser-based viewer (viser) + live solver thread.

    Mirrors `fracture/avbd3d/examples/viewer.py`'s `_run_thread` pattern
    but is trimmed to what DCR needs:
      * one viser box handle per rigid body
      * one elastic-surface mesh that re-renders each tick (Φ·q)
      * GUI: pause, speed, β, η, modal_decay_γ, causal_gating
      * Status: E_rigid, E_modal, contacts, step_ms
    """

    def __init__(self, args, world, coupler, scene_boxes, slab_mesh, title):
        import viser
        self.args = args
        self.world = world
        self.coupler = coupler
        self.scene_boxes = scene_boxes
        self.slab_mesh = slab_mesh
        self.title = title

        # Take the as-built snapshot BEFORE the first step. The "reset"
        # button restores to this baseline.
        self._initial_snapshot = world.snapshot()
        # Lock guards world.step() vs world.restore() — without it a
        # reset click landing mid-step would corrupt the Warp arrays
        # the running step is mid-launching against.
        self._world_lock = threading.Lock()

        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass

        # Elastic surface mesh. Two handles share the same vertices each
        # tick — a solid one and a tet-mesh wireframe one — so the
        # "Visualization" GUI can switch between a plain rigid-looking
        # slab and the deforming FEM tet mesh without re-adding geometry.
        # See _render_tick for the per-frame vertex / visibility update.
        self._surface_tri = coupler._surface  # cached TriMesh
        self._surf_faces = self._surface_tri.faces.astype(np.int32)
        # Rest-pose surface vertices (world coords on the floor plane).
        # Used verbatim when "render FEM vibration" is off → flat slab.
        self._surf_rest_verts = self._surface_tri.vertices.astype(np.float32).copy()
        self.surface_handle = self.server.scene.add_mesh_simple(
            "/elastic_surface",
            vertices=self._surf_rest_verts,
            faces=self._surf_faces,
            color=(0.6, 0.5, 0.35),
        )
        # Tet-mesh wireframe twin (shows the FEM surface triangulation).
        self.surface_handle_wire = self.server.scene.add_mesh_simple(
            "/elastic_surface_wire",
            vertices=self._surf_rest_verts,
            faces=self._surf_faces,
            color=(0.25, 0.8, 0.45),
            wireframe=True,
            visible=False,
        )

        # Body handles.
        self.body_handles: list = []
        for sb in scene_boxes:
            ex = sb.half_extents
            pos = tuple(world._descs[sb.body_idx].dcr_body.position)
            wxyz = _wxyz_for_box(world, sb.body_idx)
            h = self.server.scene.add_box(
                f"/bodies/{sb.name}",
                dimensions=(2 * ex[0], 2 * ex[1], 2 * ex[2]),
                position=pos,
                wxyz=wxyz,
                color=sb.color,
            )
            self.body_handles.append(h)

        # GUI.
        with self.server.gui.add_folder("Visualization"):
            self.gui_show_vibration = self.server.gui.add_checkbox(
                "render FEM vibration", initial_value=False,
                hint="Apply the modal displacement Φ·q to the elastic slab. "
                     "Off (default): the slab is drawn flat, like a plain "
                     "rigid body. On: shows the modal (FEM-reduced) "
                     "deformation.")
            self.gui_tet_style = self.server.gui.add_checkbox(
                "FEM tet-mesh style", initial_value=False,
                hint="Draw the slab as a tet-mesh wireframe (the FEM surface "
                     "triangulation) instead of a solid surface. Off "
                     "(default): plain solid slab.")
        with self.server.gui.add_folder("Simulation"):
            self.gui_pause = self.server.gui.add_checkbox(
                "pause", initial_value=False)
            self.gui_speed = self.server.gui.add_slider(
                "speed (× real-time)", 0.05, 4.0, step=0.05, initial_value=1.0)
            self.gui_iters = self.server.gui.add_slider(
                "AVBD iterations", 1, 40, step=1,
                initial_value=int(world._solver.iterations))
            self.gui_substeps = self.server.gui.add_slider(
                "AVBD substeps", 1, 16, step=1,
                initial_value=int(world._solver.substeps))
        with self.server.gui.add_folder("DCR"):
            self.gui_beta = self.server.gui.add_slider(
                "energy_response_beta", 0.0, 1.0, step=0.01,
                initial_value=float(coupler.energy_response_beta))
            self.gui_eta = self.server.gui.add_slider(
                "eta", 0.0, 1.0, step=0.01,
                initial_value=float(world.eta))
            self.gui_modal_gamma = self.server.gui.add_slider(
                "modal_decay_gamma", 0.0, 1.0, step=0.01,
                initial_value=float(coupler.modal_decay_gamma))
            self.gui_causal = self.server.gui.add_checkbox(
                "causal_gating",
                initial_value=bool(coupler.causal_gating))
        with self.server.gui.add_folder("Phase B (moving support, spec §7/§12)"):
            self.gui_phase_b = self.server.gui.add_checkbox(
                "enable_moving_support_pass",
                initial_value=bool(world.enable_moving_support_pass),
                hint="Runs spec §7 moving-support AVBD solve after the patch "
                     "coupler each step. Bounded by §12 γ line search so "
                     "W_support ≤ β · E_modal. No-op when modal reservoir "
                     "is empty (spec §22 Inv 3).")
            self.gui_ms_beta = self.server.gui.add_slider(
                "moving_support_beta (§11)",
                0.0, 1.0, step=0.01,
                initial_value=float(world.moving_support_beta),
                hint="Fraction of modal reservoir the support may spend per "
                     "step. β=0 disables; β=1 allows full spend.")
            self.gui_use_bj = self.server.gui.add_checkbox(
                "use_bj_normal (§3)",
                initial_value=bool(world.moving_support_use_bj),
                hint="Use Barbič-James deformed normal for the frozen "
                     "contact frame. Only meaningful if the coupler was "
                     "built with deformed_normal_method='barbic_james' "
                     "(toggle via --use-bj at startup).")
        with self.server.gui.add_folder("Actions"):
            self.gui_reset = self.server.gui.add_button(
                "reset scene",
                hint="Restore the as-built initial positions, velocities, "
                     "modal state, and time. Re-runs from t=0.")
            self.gui_reset.on_click(lambda _: self._reset_scene())
        with self.server.gui.add_folder("Status"):
            self.gui_t = self.server.gui.add_text("t (s)", initial_value="0.000")
            self.gui_step_ms = self.server.gui.add_text(
                "step time (ms)", initial_value="—")
            self.gui_e_rigid = self.server.gui.add_text(
                "E_rigid (J)", initial_value="—")
            self.gui_e_modal = self.server.gui.add_text(
                "E_modal (J)", initial_value="—")
            self.gui_e_loss = self.server.gui.add_text(
                "E_loss / step (J)", initial_value="—")
            self.gui_n_contacts = self.server.gui.add_text(
                "contacts", initial_value="0")
            self.gui_n_patches = self.server.gui.add_text(
                "patches", initial_value="0")
        with self.server.gui.add_folder("Phase B Status"):
            self.gui_ms_active = self.server.gui.add_text(
                "moving-support active", initial_value="0")
            self.gui_ms_gated = self.server.gui.add_text(
                "moving-support gated", initial_value="0")
            self.gui_W_support = self.server.gui.add_text(
                "W_support (J)", initial_value="—")
            self.gui_E_budget = self.server.gui.add_text(
                "E_support_budget (J)", initial_value="—")
            self.gui_gamma_min = self.server.gui.add_text(
                "γ_min (§12)", initial_value="—")
            self.gui_bj_angle = self.server.gui.add_text(
                "max BJ angle (deg)", initial_value="—")
            self.gui_ms_ms = self.server.gui.add_text(
                "moving-support time (ms)", initial_value="—")

        # Wire reactive GUI knobs.
        self.gui_iters.on_update(self._iters_changed)
        self.gui_substeps.on_update(self._substeps_changed)
        self.gui_beta.on_update(self._beta_changed)
        self.gui_eta.on_update(self._eta_changed)
        self.gui_modal_gamma.on_update(self._mgamma_changed)
        self.gui_causal.on_update(self._causal_changed)
        self.gui_phase_b.on_update(self._phase_b_changed)
        self.gui_ms_beta.on_update(self._ms_beta_changed)
        self.gui_use_bj.on_update(self._use_bj_changed)
        self.gui_show_vibration.on_update(self._vis_changed)
        self.gui_tet_style.on_update(self._vis_changed)

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)

    # ---- GUI callbacks ---------------------------------------------------

    def _iters_changed(self, _evt):
        self.world._solver.iterations = int(self.gui_iters.value)

    def _substeps_changed(self, _evt):
        self.world._solver.substeps = int(self.gui_substeps.value)

    def _beta_changed(self, _evt):
        self.coupler.energy_response_beta = float(self.gui_beta.value)

    def _eta_changed(self, _evt):
        self.world.eta = float(self.gui_eta.value)

    def _mgamma_changed(self, _evt):
        new = float(self.gui_modal_gamma.value)
        self.coupler.modal_decay_gamma = new
        self.coupler._stepper.gamma = new

    def _causal_changed(self, _evt):
        self.coupler.causal_gating = bool(self.gui_causal.value)

    def _phase_b_changed(self, _evt):
        self.world.enable_moving_support_pass = bool(self.gui_phase_b.value)

    def _ms_beta_changed(self, _evt):
        self.world.moving_support_beta = float(self.gui_ms_beta.value)

    def _vis_changed(self, _evt):
        # Apply immediately (responds even when paused), then let
        # _render_tick keep it in sync each frame.
        self._apply_surface_vis()

    def _apply_surface_vis(self):
        """Update the slab's rendered vertices + which handle is visible,
        per the two Visualization checkboxes. Off/off (default) = a flat,
        solid, rigid-looking slab; vibration on = rest + Φ·q; tet-mesh
        style swaps the solid handle for the wireframe twin."""
        if bool(self.gui_show_vibration.value):
            verts = _surface_vertex_world_positions(
                self.coupler, self.slab_mesh).astype(np.float32)
        else:
            verts = self._surf_rest_verts            # flat / rigid look
        tet_style = bool(self.gui_tet_style.value)
        for handle in (self.surface_handle, self.surface_handle_wire):
            try:
                handle.vertices = verts
            except Exception:
                pass
        self.surface_handle.visible = not tet_style
        self.surface_handle_wire.visible = tet_style

    def _use_bj_changed(self, _evt):
        # Only takes effect if the coupler was built with the BJ cache
        # (deformed_normal_method='barbic_james'). When the cache is
        # absent the moving-support pass silently falls back to n_rest;
        # the BJ-angle status will stay at 0.
        self.world.moving_support_use_bj = bool(self.gui_use_bj.value)

    def _reset_scene(self):
        """Restore the as-built snapshot taken at viewer construction.

        Holds the world lock so the running solver thread can't race
        the restore. After the restore returns we immediately push one
        render tick so the viewer reflects t=0 even if the user has
        paused playback.
        """
        with self._world_lock:
            self.world.restore(self._initial_snapshot)
        self._render_tick()

    # ---- Loop ------------------------------------------------------------

    def run(self):
        self._thread.start()
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
            # Step until we've caught up, but cap at 4 steps/frame so the
            # solver can't run away from the renderer on a slow machine.
            steps_this_frame = 0
            while accum >= h and steps_this_frame < 4:
                with self._world_lock:
                    self.world.step()
                accum -= h
                steps_this_frame += 1
            self._render_tick()

    def _render_tick(self):
        w = self.world
        # body handles.
        for sb, handle in zip(self.scene_boxes, self.body_handles):
            pos = w._descs[sb.body_idx].dcr_body.position
            q_wxyz = w._descs[sb.body_idx].dcr_body.orientation
            handle.position = (float(pos[0]), float(pos[1]), float(pos[2]))
            handle.wxyz = (
                float(q_wxyz[0]), float(q_wxyz[1]),
                float(q_wxyz[2]), float(q_wxyz[3]))
        # elastic surface — honours the two Visualization checkboxes
        # (render FEM vibration on/off, solid vs tet-mesh wireframe).
        # Default: flat solid slab, so the road/shelf reads as a plain
        # rigid body and the Φ·q compute is skipped entirely.
        self._apply_surface_vis()
        # status text.
        from dcr.rigid.energy import rigid_kinetic_energy
        bodies = [d.dcr_body for d in w._descs]
        e_rigid = rigid_kinetic_energy(bodies)
        e_modal = float(modal_energy(
            self.coupler._stepper.q, self.coupler._stepper.qdot,
            self.coupler.modal.frequencies))
        self.gui_t.value = f"{w.time:.3f}"
        self.gui_step_ms.value = f"{w.last_step_ms:.2f}"
        self.gui_e_rigid.value = f"{e_rigid:.4f}"
        self.gui_e_modal.value = f"{e_modal:.4f}"
        self.gui_e_loss.value = f"{w.last_E_loss:.4f}"
        self.gui_n_contacts.value = str(len(w.last_contacts))
        n_p = (len(self.coupler.last_patch_kicks)
               if self.coupler.last_patch_kicks else 0)
        self.gui_n_patches.value = str(n_p)
        # Phase B status — meaningful only when the moving-support pass
        # actually fired this step.
        self.gui_ms_active.value = str(w.last_n_moving_support)
        self.gui_ms_gated.value = str(w.last_n_moving_support_gated)
        if w.last_n_moving_support > 0:
            self.gui_W_support.value = f"{w.last_W_support:.4e}"
            self.gui_E_budget.value = f"{w.last_E_support_budget:.4e}"
            self.gui_gamma_min.value = f"{w.last_gamma_support_min:.4f}"
        else:
            self.gui_W_support.value = "—"
            self.gui_E_budget.value = "—"
            self.gui_gamma_min.value = "—"
        self.gui_bj_angle.value = (
            f"{w.last_bj_angle_deg_max:.4f}"
            if w.last_bj_angle_deg_max > 0.0 else "—")
        self.gui_ms_ms.value = f"{w.last_moving_support_ms:.2f}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene", choices=list(SCENES.keys()))
    ap.add_argument("--device", default="cpu",
                    help="Warp device (default 'cpu'; e.g. 'cuda:0').")
    ap.add_argument("--port", type=int, default=8181)
    ap.add_argument("--h", type=float, default=1.0 / 120.0,
                    help="Rigid timestep (default 1/120 s).")
    ap.add_argument("--eta", type=float, default=0.5,
                    help="Transfer efficiency (foundation §1).")
    ap.add_argument("--beta", type=float, default=0.25,
                    help="energy_response_beta for the patch coupler.")
    ap.add_argument("--causal-gating", action="store_true")
    ap.add_argument("--modal-decay-gamma", type=float, default=1.0)
    # ---- Phase B (spec §7 / §12 / §13) ----
    ap.add_argument(
        "--phase-b", action="store_true",
        help="Enable the spec §7 moving-support AVBD pass at startup. "
             "Toggleable live via the 'Phase B' folder in the viewer GUI.")
    ap.add_argument(
        "--ms-beta", type=float, default=0.1,
        help="moving_support_beta (spec §11): fraction of modal reservoir "
             "the support may spend per step. Default 0.1.")
    ap.add_argument(
        "--use-bj", action="store_true",
        help="Build the coupler with deformed_normal_method='barbic_james' "
             "and enable the BJ-normal path in the moving-support pass. "
             "Without this flag the coupler caches no BJ basis and the "
             "viewer's 'use_bj_normal' toggle silently falls back to rest.")
    args = ap.parse_args()

    builder = SCENES[args.scene]
    world, coupler, boxes, mesh, title = builder(
        device=args.device, h=args.h, eta=args.eta, beta=args.beta,
        causal_gating=args.causal_gating,
        modal_decay_gamma=args.modal_decay_gamma,
        enable_phase_b=args.phase_b,
        ms_beta=args.ms_beta,
        use_bj=args.use_bj,
    )
    print(f"\n{title}")
    print(f"  bodies={len(world._descs)}  modes={coupler.modal.U.shape[1]}")
    print(f"  device={args.device}  h={args.h:g}  beta={args.beta}  eta={args.eta}")
    print(f"  viser: http://localhost:{args.port}\n")
    viewer = AVBDDCRViewer(args, world, coupler, boxes, mesh, title)
    viewer.run()


if __name__ == "__main__":
    main()
