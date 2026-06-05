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
# Mesh resolution selector
# ---------------------------------------------------------------------------
# `medium` matches the per-scene defaults baked in pre-resolution-selector;
# `coarse` ~halves the in-plane subdivisions for a fast preview; `fine` 1.5×
# the in-plane subdivisions and doubles the through-thickness layer count
# (so the bending modes get a real second through-the-depth row). The modal
# eigenproblem scales roughly with node count, so `fine` on `ledge`/`truck`
# adds a few seconds to scene startup.
MESH_RESOLUTIONS = ("coarse", "medium", "fine")
_MESH_SCALE = {"coarse": 0.55, "medium": 1.0, "fine": 1.5}


def _scaled_subdiv(
    nx: int, ny: int, nz: int, level: str
) -> tuple[int, int, int]:
    s = _MESH_SCALE[level]
    nx_s = max(4, int(round(nx * s)))
    ny_s = max(3, int(round(ny * s)))
    # nz stays >= 2 (need at least one through-thickness layer for bending);
    # only `fine` doubles it, otherwise we keep the baseline.
    nz_s = max(2, nz * 2 if level == "fine" else nz)
    return nx_s, ny_s, nz_s


# ---------------------------------------------------------------------------
# Scene builders
# ---------------------------------------------------------------------------

def build_truck_scene(
    device: str, h: float, eta: float, beta: float,
    causal_gating: bool, modal_decay_gamma: float,
    enable_phase_b: bool = False, ms_beta: float = 0.1,
    use_bj: bool = False,
    mesh_resolution: str = "medium",
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
    nx, ny, nz = _scaled_subdiv(16, 10, 2, mesh_resolution)
    mesh = make_slab_tet_mesh(
        length=2.5, width=1.5, height=0.06, nx=nx, ny=ny, nz=nz)
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
    mesh_resolution: str = "medium",
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

    nx, ny, nz = _scaled_subdiv(12, 5, 2, mesh_resolution)
    mesh = make_slab_tet_mesh(
        length=0.8, width=0.3, height=0.03, nx=nx, ny=ny, nz=nz)
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
    mesh_resolution: str = "medium",
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

    nx, ny, nz = _scaled_subdiv(12, 8, 2, mesh_resolution)
    mesh = make_slab_tet_mesh(
        length=1.2, width=0.8, height=0.08, nx=nx, ny=ny, nz=nz)
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


def build_dinner_table_scene(
    device: str, h: float, eta: float, beta: float,
    causal_gating: bool, modal_decay_gamma: float,
    enable_phase_b: bool = False, ms_beta: float = 0.1,
    use_bj: bool = False,
    mesh_resolution: str = "medium",
) -> tuple[AVBDDCRWorld, PassiveDCRCoupler, list[SceneBox], object, str]:
    """Pot drops on a wooden dinner table; plates rattle and topple.

    Modeled on the DCR paper's distant-response demo: a heavy object lands
    on the elastic surface at the center, and the modal coupling rocks
    nearby small objects through the support's vibration. The table is a
    corner-pinned wood slab (four legs at the corners — `_fix_corners`),
    matching the truck scene's stiff-but-light FEM (E=10 GPa, ρ=500 kg/m³).
    """
    world = AVBDDCRWorld(
        h=h, eta=eta, device=device,
        avbd_iterations=10, avbd_substeps=4,
        enable_moving_support_pass=enable_phase_b,
        moving_support_beta=ms_beta,
        moving_support_use_bj=use_bj,
    )
    table_top = 0.03
    table_idx = world.add_floor(
        floor_y=table_top, friction=0.5, name="table")

    nx, ny, nz = _scaled_subdiv(14, 12, 2, mesh_resolution)
    mesh = make_slab_tet_mesh(
        length=1.2, width=1.0, height=0.04, nx=nx, ny=ny, nz=nz)
    mat = Material(E=10.0e9, nu=0.3, rho=500.0)
    fem = FEMModel(
        mesh=mesh, material=mat,
        fixed_nodes=_fix_corners(mesh),
        alpha0=2.0, alpha1=1e-5,
    )
    modal = ModalAnalysis(fem=fem, num_modes=15)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=table_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=beta,
        deformed_normal_method=("barbic_james" if use_bj else "patch_fit"),
        causal_gating=causal_gating,
        modal_decay_gamma=modal_decay_gamma,
    )
    world.add_passive_coupler(coupler)

    boxes: list[SceneBox] = []

    # Plate primitive: shallow, wide base (17 cm across, 2 cm thick) so it
    # reads as a plate and stays stable until the table rings. 5 columns
    # along the table's long axis × 3 rows across, center slot vacated for
    # the pot drop → 14 plates.
    plate_h = (0.085, 0.010, 0.085)
    plate_palette = [
        (0.95, 0.92, 0.85),  # off-white porcelain
        (0.85, 0.65, 0.55),  # terracotta
        (0.55, 0.70, 0.85),  # pale blue glaze
        (0.80, 0.80, 0.70),  # bone
    ]
    xs = [-0.40, -0.20, 0.0, 0.20, 0.40]
    zs = [-0.30, 0.0, 0.30]
    plate_count = 0
    for xi, x in enumerate(xs):
        for zi, z in enumerate(zs):
            # Reserve the center slot for the pot.
            if xi == 2 and zi == 1:
                continue
            name = f"plate_{plate_count}"
            color = plate_palette[plate_count % len(plate_palette)]
            idx = world.add_box(
                mass=0.4, half_extents=plate_h,
                position=(x, table_top + plate_h[1] + 0.001, z),
                friction=0.4, name=name,
            )
            boxes.append(SceneBox(name=name, body_idx=idx,
                                  half_extents=plate_h, color=color))
            plate_count += 1

    # The pot: heavy cast-iron-style box, drops from ~0.5 m above center
    # so it hits with ~3 m/s. Square base, modestly tall.
    pot_h = (0.08, 0.10, 0.08)
    idx = world.add_box(
        mass=8.0, half_extents=pot_h,
        position=(0.0, table_top + pot_h[1] + 0.5, 0.0),
        friction=0.5, name="pot",
    )
    boxes.append(SceneBox(name="pot", body_idx=idx,
                          half_extents=pot_h, color=(0.20, 0.18, 0.16)))

    return world, coupler, boxes, mesh, "Dinner Table (AVBD + patch DCR)"


def build_long_slab_scene(
    device: str, h: float, eta: float, beta: float,
    causal_gating: bool, modal_decay_gamma: float,
    enable_phase_b: bool = False, ms_beta: float = 0.1,
    use_bj: bool = False,
    mesh_resolution: str = "medium",
) -> tuple[AVBDDCRWorld, PassiveDCRCoupler, list[SceneBox], object, str]:
    """Long thin slab; heavy box drops at one end, plate targets along the
    length so the geodesic-distance attenuation is visually obvious.

    Use with ``--use-geodesic`` and the 'show attenuation heatmap' viewer
    toggle: the slab is colored by α(d_geo) from the most recent impact,
    and the plate response should fall off along the length.

    Slab: 2.5 m × 0.4 m × 0.04 m wood (E=10 GPa, ρ=500); cantilever-pinned
    at the -x edge to match the impact at the *other* (+x) end — that
    fixed end keeps the impact-end free to ring.
    """
    world = AVBDDCRWorld(
        h=h, eta=eta, device=device,
        avbd_iterations=10, avbd_substeps=4,
        enable_moving_support_pass=enable_phase_b,
        moving_support_beta=ms_beta,
        moving_support_use_bj=use_bj,
    )
    slab_top = 0.04
    slab_idx = world.add_floor(
        floor_y=slab_top, friction=0.5, name="long_slab")

    # Long aspect-ratio slab — enough length for the geodesic decay to be
    # visually distinguishable from a Euclidean falloff. Through-thickness
    # subdivisions stay 2 at every resolution so the slab doesn't get
    # absurdly heavy at 'fine'.
    nx, ny, nz = _scaled_subdiv(36, 6, 2, mesh_resolution)
    mesh = make_slab_tet_mesh(
        length=2.5, width=0.4, height=0.04, nx=nx, ny=ny, nz=nz)
    mat = Material(E=10.0e9, nu=0.3, rho=500.0)
    fem = FEMModel(
        mesh=mesh, material=mat,
        fixed_nodes=_fix_one_edge(mesh),
        alpha0=2.0, alpha1=1e-5,
    )
    modal = ModalAnalysis(fem=fem, num_modes=20)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=slab_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=beta,
        deformed_normal_method=("barbic_james" if use_bj else "patch_fit"),
        causal_gating=causal_gating,
        modal_decay_gamma=modal_decay_gamma,
        use_geodesic_attenuation=True,  # this is the showcase scene
    )
    world.add_passive_coupler(coupler)

    boxes: list[SceneBox] = []

    # Plate targets along the length (impact at +x end). 8 plates spread
    # from x ≈ +0.95 m (closest to impact, still off the strike point)
    # down to x ≈ -1.05 m (cantilever end). Coloring by index so the
    # falloff is read by both visible motion AND the colored attenuation
    # heatmap underneath each plate.
    plate_h = (0.06, 0.010, 0.06)
    plate_xs = [0.95, 0.65, 0.35, 0.05, -0.25, -0.55, -0.85, -1.05]
    palette = [
        (0.95, 0.92, 0.85),
        (0.85, 0.65, 0.55),
        (0.55, 0.70, 0.85),
        (0.80, 0.80, 0.70),
    ]
    for i, x in enumerate(plate_xs):
        name = f"plate_{i}"
        idx = world.add_box(
            mass=0.4, half_extents=plate_h,
            position=(x, slab_top + plate_h[1] + 0.001, 0.0),
            friction=0.4, name=name,
        )
        boxes.append(SceneBox(name=name, body_idx=idx,
                              half_extents=plate_h, color=palette[i % len(palette)]))

    # Heavy impactor at the +x (free) end, dropped from 0.6 m above. The
    # cantilever-fixed -x end keeps the impact-end ringing rather than
    # absorbing the impulse into the support.
    impactor_h = (0.07, 0.07, 0.07)
    impactor_x = 1.15
    idx = world.add_box(
        mass=10.0, half_extents=impactor_h,
        position=(impactor_x, slab_top + impactor_h[1] + 0.6, 0.0),
        friction=0.5, name="impactor",
    )
    boxes.append(SceneBox(name="impactor", body_idx=idx,
                          half_extents=impactor_h, color=(0.20, 0.18, 0.16)))

    return world, coupler, boxes, mesh, "Long Slab (geodesic attenuation showcase)"


SCENES = {
    "truck": build_truck_scene,
    "shelf": build_shelf_scene,
    "ledge": build_ledge_scene,
    "dinner_table": build_dinner_table_scene,
    "long_slab": build_long_slab_scene,
}


# ---------------------------------------------------------------------------
# Viser viewer
# ---------------------------------------------------------------------------

# Unit cube template (half-extents 0.5 → multiply by 2*half_extents per
# instance to recover the real box). Drives the instanced-render path so the
# whole body set lives in one viser node (kills the per-handle message
# stutter — see upstream avbd3d/examples/viewer.py:75-88).
_CUBE_V = np.array([
    [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
    [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
], dtype=np.float32)
_CUBE_F = np.array([
    [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
    [2, 3, 7], [2, 7, 6], [1, 2, 6], [1, 6, 5], [0, 4, 7], [0, 7, 3],
], dtype=np.uint32)


def _thermal_uint8(alpha: np.ndarray) -> np.ndarray:
    """Vectorized 5-stop thermal ramp on alpha ∈ [0, 1].

    Designed for high contrast against the warm beige slab base color, so
    the falloff reads clearly at a glance.

    α=0.00 → deep navy   ( 10,  20,  70)   "cold / far"
    α=0.25 → blue        ( 20, 100, 230)
    α=0.50 → cyan-green  ( 40, 220, 200)
    α=0.75 → orange      (255, 160,  30)
    α=1.00 → fire red    (240,  30,  20)   "hot / near"

    Returns (N, 4) uint8 RGBA suitable for trimesh.visual.vertex_colors.
    """
    a = np.clip(alpha.astype(np.float32), 0.0, 1.0)
    # 5 stops at α = 0, 0.25, 0.5, 0.75, 1.0
    stops = np.array(
        [[ 10,  20,  70],
         [ 20, 100, 230],
         [ 40, 220, 200],
         [255, 160,  30],
         [240,  30,  20]], dtype=np.float32)
    # Bucket each α into the 4 segments and lerp within.
    seg = np.minimum((a * 4.0).astype(np.int32), 3)
    t = (a * 4.0 - seg)[:, None]
    c_lo = stops[seg]
    c_hi = stops[seg + 1]
    rgb = c_lo * (1.0 - t) + c_hi * t
    out = np.zeros((a.size, 4), dtype=np.uint8)
    out[:, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    out[:, 3] = 255
    return out


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
    # Vectorized gather: build a (n_v, 3) displacement buffer addressed by
    # global vertex idx; rows for non-surface verts stay zero (kept from the
    # initial zero-init). 100x faster than the per-vertex Python loop on
    # 1000-vert slabs — was the main vibration-on tick cost.
    surf_idx_map = coupler._vert_to_surf_idx  # vertex -> surf-row (-1 = fixed)
    mask = surf_idx_map >= 0
    if mask.any():
        # Per-vertex disp = U_surf rows reshaped (n_surf, 3) gathered by
        # surf-row id.
        surf_disp = surf_disp_flat.reshape(-1, 3)  # (n_surf, 3)
        verts[mask] = verts[mask] + surf_disp[surf_idx_map[mask]]
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
        # Human-readable mesh-resolution label for the read-only GUI display.
        # Baked at scene-build time; only --mesh-resolution at startup
        # changes it.
        self.mesh_resolution_label = (
            f"{getattr(args, 'mesh_resolution', 'medium')} "
            f"({int(slab_mesh.tets.shape[0])} tets, "
            f"{int(slab_mesh.vertices.shape[0])} nodes)"
        )

        # Recommended low-iteration coupling (docs §12 — the "reservoir δp
        # PRESCRIBED" column): impact reservoir (timing) + delta_p impulse
        # (iteration-insensitive) + energy-prescribed scaling (magnitude from
        # the η·E_loss budget). ON by default so the modal coupling holds up
        # when the AVBD-iterations slider is dragged low; toggle live in the
        # DCR folder, or start the pre-§12 path with --legacy-coupling.
        if not getattr(args, "legacy_coupling", False):
            coupler.use_impact_reservoir = True
            coupler.impulse_source = "delta_p"
            coupler.injection_scaling = "prescribed"
            coupler.prescribed_mu = 1.0

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
        # Geodesic-attenuation heatmap (paper §4.5). Lazy: created the first
        # time "show attenuation heatmap" is enabled. The trimesh handle has
        # no live setter, so a rebuild is `remove + re-add` — a full glTF
        # re-encode every time. To kill the per-tick cost we only rebuild
        # when the inputs actually changed: (a) a new impact updated the
        # attenuation field (id(field) differs), or (b) the displayed
        # vertices changed (vibration on AND a new solver tick → check by
        # comparing the q vector's id) or (c) the user changed visibility
        # state (handled by setting _heatmap_dirty in _vis_changed).
        self._heatmap_handle = None
        # Off-surface vertices (or "no impact yet" fallback) use a neutral
        # cool gray-blue so the thermal ramp pops. RGBA uint8.
        self._heatmap_base_color = np.array(
            [55, 65, 85, 255], dtype=np.uint8)
        self._heatmap_last_field_id = -1   # id() of last_attenuation_field
        self._heatmap_last_time = -1.0     # world.time at last build
        self._heatmap_dirty = True         # force first build (toggle/init)
        # Wave-propagation animation state. Re-anchored whenever the impact
        # *source vertex* changes (NOT just when last_attenuation_field gets
        # rebuilt — the coupler refreshes that array every contact step even
        # for a stable resting contact, which would pin dt_since at 0 and
        # kill the propagation). Tracking the vert id instead lets the same
        # contact spot keep its anchor across many steps, so the pulse
        # actually travels. Re-anchors also fire when the field arrives for
        # the very first time (vert goes None → int) and when a min hold-off
        # has elapsed since the last anchor (so a fresh impact at the same
        # vert after the wave fades does replay).
        self._wave_t_impact = -1.0         # world.time when the latest impact landed
        self._wave_last_impact_vert = None  # last anchored coupler._last_impact_vert
        # Tuned defaults: c=2 m/s + sigma=15cm covers a 2.5m slab in ~1.2s with
        # a clearly localized leading edge; cycles=0 = clean single pulse.
        self._wave_speed_mps = 2.0
        self._wave_sigma_m = 0.15
        self._wave_ringdown_cycles = 0.0   # trailing-wake oscillations
        # 3D-bump extrusion of the heatmap surface — the field also raises
        # the surface vertices by alpha * bump_height. Default 1.5 cm (≈
        # 1× plate thickness) so the dome is visible from any angle without
        # crashing into resting bodies. Settable live in the GUI.
        self._heatmap_bump_m = 0.015
        # Frame counter for HUD throttling. HUD text writes are 15 separate
        # websocket messages per tick — at ~100 Hz that's the second-biggest
        # source of render-thread chatter after the body updates. Pushing
        # them every Nth frame still gives the user a comfortable refresh
        # rate (~30 Hz) without saturating the websocket.
        self._frame = 0
        self._hud_interval = 3   # 100 Hz tick → ~33 Hz HUD

        # Instanced body rendering (upstream avbd3d viewer perf pass):
        # ONE viser node for the entire body set; per-tick updates are two
        # array writes (batched_positions + batched_wxyzs). Per-instance
        # `batched_scales = 2 * half_extents` recovers the real box from the
        # unit-cube template. Kills the per-handle message stutter on
        # multi-body scenes (was the dominant tick cost on dinner_table /
        # long_slab).
        n_bodies = len(scene_boxes)
        self._body_idxs = np.array(
            [sb.body_idx for sb in scene_boxes], dtype=np.int64)
        scales = np.array(
            [(2.0 * sb.half_extents[0], 2.0 * sb.half_extents[1],
              2.0 * sb.half_extents[2]) for sb in scene_boxes],
            dtype=np.float32)
        colors = np.array(
            [(int(np.clip(sb.color[0], 0, 1) * 255),
              int(np.clip(sb.color[1], 0, 1) * 255),
              int(np.clip(sb.color[2], 0, 1) * 255)) for sb in scene_boxes],
            dtype=np.uint8)
        # Initial poses (matched to the snapshot taken just above).
        bp_init = np.array(
            [world._descs[i].dcr_body.position for i in self._body_idxs],
            dtype=np.float32)
        bw_init = np.array(
            [world._descs[i].dcr_body.orientation for i in self._body_idxs],
            dtype=np.float32)
        self._batched_bodies = self.server.scene.add_batched_meshes_simple(
            "/bodies_batched",
            _CUBE_V, _CUBE_F,
            batched_wxyzs=bw_init,
            batched_positions=bp_init,
            batched_scales=scales,
            batched_colors=colors,
            flat_shading=True, side="double",
        )
        # Pre-allocated update buffers — refilled per tick, written twice.
        self._bp_buf = bp_init.copy()
        self._bw_buf = bw_init.copy()

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
            self.gui_show_heatmap = self.server.gui.add_checkbox(
                "show attenuation heatmap", initial_value=False,
                hint="Visualize α(d_geo) from the most recent impact (paper "
                     "§4.5). Combines three signals so the field is hard to "
                     "miss: (1) thermal colormap (deep navy=far, fire-red="
                     "near); (2) 3D dome — the slab surface rises by "
                     "α·bump near the source; (3) a bright source marker "
                     "sphere at the impact xyz. Only meaningful when 'use "
                     "geodesic attenuation' is also ON in the DCR folder; "
                     "otherwise the slab still draws but α is not applied "
                     "to the kicks. Updates on each new impact.")
            self.gui_heat_bump_cm = self.server.gui.add_slider(
                "heatmap bump (cm)", 0.0, 8.0, step=0.1,
                initial_value=100.0 * self._heatmap_bump_m,
                hint="Vertical extrusion scale for the heatmap dome. 0 = "
                     "flat colored slab; 1.5 cm (default) = clearly visible "
                     "from any angle. Pure visualization — does not affect "
                     "the simulation.")
            self.gui_wave_prop = self.server.gui.add_checkbox(
                "wave propagation",
                initial_value=True,
                hint="Animate the heatmap as a ring expanding outward from "
                     "the most recent impact (DCR paper §4.5 figure look). "
                     "Off = static α(d) field; On = a Gaussian pulse rides "
                     "the wavefront at 'wave speed' so the slab visibly "
                     "ripples on each new impact. Pure visualization — does "
                     "not affect the simulation.")
            self.gui_wave_speed = self.server.gui.add_slider(
                "wave speed (m/s)", 0.2, 8.0, step=0.1,
                initial_value=self._wave_speed_mps,
                hint="Outward propagation speed of the visualized wavefront. "
                     "2 m/s (default) traverses the long-slab in ~1 s.")
            self.gui_wave_width_cm = self.server.gui.add_slider(
                "wave width (cm)", 2.0, 60.0, step=1.0,
                initial_value=100.0 * self._wave_sigma_m,
                hint="Gaussian pulse width σ. Smaller = sharper, more "
                     "localized ring; larger = broader, more diffuse glow.")
            self.gui_wave_cycles = self.server.gui.add_slider(
                "wave ringdown cycles", 0.0, 6.0, step=0.5,
                initial_value=self._wave_ringdown_cycles,
                hint="Trailing oscillations behind the front (0 = clean "
                     "single pulse; 2-4 = visible ripple wake like the "
                     "paper's multi-ring figure).")
            # Read-only display of the active FEM resolution. Resolution is
            # baked at scene-build time (the FEM/modal pipeline depends on it),
            # so this label is informational — relaunch with a different
            # --mesh-resolution to change it.
            self.server.gui.add_text(
                "FEM resolution",
                initial_value=self.mesh_resolution_label,
                hint="Slab FEM mesh subdivision level chosen at startup via "
                     "--mesh-resolution {coarse, medium, fine}. The number "
                     "in parens is the tet count. Relaunch to change.",
            ).disabled = True
        with self.server.gui.add_folder("Simulation"):
            self.gui_pause = self.server.gui.add_checkbox(
                "pause", initial_value=False)
            self.gui_speed = self.server.gui.add_slider(
                "speed (× real-time)", 0.05, 4.0, step=0.05, initial_value=1.0)
            # Default 4 iterations: the recommended low-iter setting for the
            # §12 prescribed/reservoir coupling — fast enough to feel real-time
            # in the browser, slow enough for the DCR coupling to drive the
            # visible response. Push the value into the live solver too so
            # the initial steps already run at 4.
            world._solver.iterations = 4
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
            self.gui_prescribed = self.server.gui.add_checkbox(
                "energy-prescribed injection (§12)",
                initial_value=(coupler.injection_scaling == "prescribed"),
                hint="Scale the modal kick to deposit μ·budget of energy "
                     "(instead of capping at the raw, smeared impulse). Makes "
                     "the coupling iteration-insensitive; still globally "
                     "passive. OFF = the pre-§12 passive cap.")
            self.gui_reservoir = self.server.gui.add_checkbox(
                "impact reservoir (timing)",
                initial_value=bool(coupler.use_impact_reservoir),
                hint="Deposit η·E_loss every step and spend it within a short "
                     "window, so injection doesn't hinge on is_new timing.")
            self.gui_impulse_source = self.server.gui.add_dropdown(
                "impulse_source",
                ("delta_p", "lambda_only", "augmented"),
                initial_value=str(coupler.impulse_source),
                hint="delta_p = measured momentum change (iteration-"
                     "insensitive); the recommended source for low iters.")
            self.gui_prescribed_mu = self.server.gui.add_slider(
                "prescribed_mu", 0.0, 1.0, step=0.01,
                initial_value=float(coupler.prescribed_mu),
                hint="Fraction of the η·E_loss budget the prescribed kick "
                     "deposits per step. 1.0 = hit the passivity bound.")
            self.gui_use_geodesic = self.server.gui.add_checkbox(
                "use geodesic attenuation (paper §4.5)",
                initial_value=bool(coupler.use_geodesic_attenuation),
                hint="Multiply the patch-mode v_f at each receiver by "
                     "α = clip(C·(max(d,r0)/r0)^{-β}, 0, 1) where d is the "
                     "heat-method geodesic distance from the most recent "
                     "impact. α∈[0,1] so passivity is preserved. Enable "
                     "'show attenuation heatmap' in Visualization to "
                     "see α colored on the slab.")
            self.gui_geo_beta = self.server.gui.add_slider(
                "geodesic_beta", 0.1, 2.0, step=0.05,
                initial_value=float(coupler.geodesic_beta),
                hint="Falloff exponent. 0.5 = paper's shells default; 1.0 "
                     "= volume default; higher = sharper drop with "
                     "distance. Only used when 'use geodesic attenuation' "
                     "is on.")
            self.gui_geo_C = self.server.gui.add_slider(
                "geodesic_C", 0.1, 2.0, step=0.05,
                initial_value=float(coupler.geodesic_C),
                hint="Attenuation amplitude. C·(r/r0)^{-β} is clipped to "
                     "[0, 1] for passivity, so values > 1 only widen the "
                     "near-source plateau.")
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
            self.gui_e_inj = self.server.gui.add_text(
                "E_modal inj / step (J)", initial_value="—")
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
        self.gui_prescribed.on_update(self._prescribed_changed)
        self.gui_reservoir.on_update(self._reservoir_changed)
        self.gui_impulse_source.on_update(self._impulse_source_changed)
        self.gui_prescribed_mu.on_update(self._prescribed_mu_changed)
        self.gui_phase_b.on_update(self._phase_b_changed)
        self.gui_ms_beta.on_update(self._ms_beta_changed)
        self.gui_use_bj.on_update(self._use_bj_changed)
        self.gui_show_vibration.on_update(self._vis_changed)
        self.gui_tet_style.on_update(self._vis_changed)
        self.gui_show_heatmap.on_update(self._vis_changed)
        self.gui_heat_bump_cm.on_update(self._heat_bump_changed)
        self.gui_wave_prop.on_update(self._wave_changed)
        self.gui_wave_speed.on_update(self._wave_changed)
        self.gui_wave_width_cm.on_update(self._wave_changed)
        self.gui_wave_cycles.on_update(self._wave_changed)
        self.gui_use_geodesic.on_update(self._geo_changed)
        self.gui_geo_beta.on_update(self._geo_beta_changed)
        self.gui_geo_C.on_update(self._geo_C_changed)

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

    def _prescribed_changed(self, _evt):
        self.coupler.injection_scaling = (
            "prescribed" if bool(self.gui_prescribed.value) else "passive")

    def _reservoir_changed(self, _evt):
        self.coupler.use_impact_reservoir = bool(self.gui_reservoir.value)

    def _impulse_source_changed(self, _evt):
        self.coupler.impulse_source = str(self.gui_impulse_source.value)

    def _prescribed_mu_changed(self, _evt):
        self.coupler.prescribed_mu = float(self.gui_prescribed_mu.value)

    def _phase_b_changed(self, _evt):
        self.world.enable_moving_support_pass = bool(self.gui_phase_b.value)

    def _ms_beta_changed(self, _evt):
        self.world.moving_support_beta = float(self.gui_ms_beta.value)

    def _vis_changed(self, _evt):
        # Apply immediately (responds even when paused), then let
        # _render_tick keep it in sync each frame.
        self._heatmap_dirty = True
        self._apply_surface_vis()

    def _apply_surface_vis(self):
        """Update the slab's rendered vertices, color, and which handle is
        visible, per the three Visualization checkboxes.

        Off/off/off (default) = flat, solid, rigid-looking slab.
        vibration on → rest + Φ·q drives all three handles' vertices.
        tet-mesh style → wireframe twin replaces the solid handle.
        heatmap on → trimesh handle with per-vertex α colors (paper §4.5
        ramp) replaces both other handles. The trimesh handle has no
        live setter, so we remove + re-add on each call.
        """
        show_vibration = bool(self.gui_show_vibration.value)
        tet_style = bool(self.gui_tet_style.value)
        show_heatmap = bool(self.gui_show_heatmap.value)

        if show_vibration:
            verts = _surface_vertex_world_positions(
                self.coupler, self.slab_mesh).astype(np.float32)
        else:
            verts = self._surf_rest_verts            # flat / rigid look

        # Keep the solid and wire handles' vertices in sync so toggling
        # heatmap off restores them without a stale geometry frame.
        for handle in (self.surface_handle, self.surface_handle_wire):
            try:
                handle.vertices = verts
            except Exception:
                pass

        if show_heatmap:
            # Two paths:
            #   wave_on  → outward-traveling Gaussian pulse riding on α(d).
            #              Rebuild every tick (the pulse moves).
            #   wave_off → static α(d) field, rebuild only when something
            #              actually changed (dirty flag, new impact via
            #              field-id swap, or vibration advanced world.time).
            field = self.coupler.last_attenuation_field
            d_field = self.coupler.last_geodesic_distance_field
            field_id = id(field) if field is not None else 0
            t_now = float(getattr(self.world, "time", 0.0))
            wave_on = bool(self.gui_wave_prop.value)

            # Re-anchor the wave clock when:
            #   (a) the impact source VERTEX changed (new spot, or first
            #       impact after None) — NOT when only the field ndarray id
            #       flipped (the coupler rebuilds that every contact step,
            #       which would pin dt_since at 0); OR
            #   (b) the previous wave has had time to traverse the slab —
            #       a long-held contact at the same vertex still replays a
            #       fresh pulse once the prior one fades.
            cur_vert = getattr(self.coupler, "_last_impact_vert", None)
            if cur_vert is not None and field is not None:
                vert_changed = cur_vert != self._wave_last_impact_vert
                # Re-anchor cooldown: half the time it takes the front to
                # cross 1.5× the longest geodesic distance currently in the
                # field (bounded to >= 0.5 s so we don't replay constantly).
                wave_dur = max(0.5, 1.5 * float(np.nanmax(
                    np.where(np.isfinite(d_field), d_field, 0.0)))
                    / max(0.1, float(self._wave_speed_mps))
                ) if d_field is not None else 1.0
                cooldown_done = (
                    self._wave_t_impact < 0.0
                    or (t_now - self._wave_t_impact) > wave_dur
                )
                if vert_changed or cooldown_done:
                    self._wave_t_impact = t_now
                    self._wave_last_impact_vert = int(cur_vert)

            need_rebuild = (
                self._heatmap_handle is None
                or self._heatmap_dirty
                or field_id != self._heatmap_last_field_id
                or (show_vibration and t_now != self._heatmap_last_time)
                or (wave_on and field is not None
                    and t_now != self._heatmap_last_time)
            )
            if need_rebuild:
                # Per-vertex thermal colors + 3D bump (verts lift by env·bump
                # along +y) — three signals stacked so the field is hard to
                # miss: color, dome shape, and the source marker below.
                n_v = verts.shape[0]
                colors = np.tile(self._heatmap_base_color, (n_v, 1))
                bumped = verts.copy().astype(np.float32)
                if field is not None and len(field) >= n_v:
                    surf_global = self.coupler.modal.surface_vertex_indices
                    surf_alpha = field[surf_global].astype(np.float32)
                    if (wave_on and d_field is not None
                            and len(d_field) >= n_v
                            and self._wave_t_impact >= 0.0):
                        # DCR-paper figure look: Gaussian pulse centered at
                        # the wavefront position c·Δt, riding on the static
                        # α(d) envelope so the ring fades as it expands.
                        # phase > 0 → vertex ahead of front (not reached yet)
                        # phase < 0 → wavefront has already passed
                        surf_d = d_field[surf_global].astype(np.float32)
                        # Guard +inf entries (off-surface neighbors that
                        # heat-method left disconnected) so the exp doesn't
                        # warn — they end up at envelope=0 anyway.
                        surf_d = np.where(
                            np.isfinite(surf_d), surf_d, 1e6).astype(np.float32)
                        dt_since = max(0.0, t_now - self._wave_t_impact)
                        front = float(self._wave_speed_mps) * dt_since
                        sigma = max(1e-3, float(self._wave_sigma_m))
                        phase = surf_d - front
                        # Leading Gaussian pulse on the wavefront.
                        pulse = np.exp(-(phase / sigma) ** 2)
                        # Optional trailing ringdown (only behind the front,
                        # phase < 0). Envelope decays over ~3σ; oscillation
                        # period = sigma / cycles.
                        cycles = float(self._wave_ringdown_cycles)
                        if cycles > 0.0:
                            behind = np.maximum(-phase, 0.0)
                            decay = np.exp(-behind / (3.0 * sigma))
                            osc = 0.5 + 0.5 * np.cos(
                                2.0 * np.pi * cycles * behind / sigma)
                            ring = decay * osc
                            pulse = np.clip(pulse + 0.6 * ring, 0.0, 1.0)
                        # α(d) attenuates the pulse with distance — passivity
                        # is preserved in spirit (envelope ≤ α).
                        envelope = (surf_alpha * pulse).astype(np.float32)
                    else:
                        # Wave off (or no impact yet) → static α field.
                        envelope = surf_alpha
                    ramp = _thermal_uint8(envelope)
                    colors[surf_global] = ramp
                    # 3D dome: lift each surface vertex by envelope * bump.
                    # Off-surface verts (interior nodes) stay at rest height.
                    if self._heatmap_bump_m > 0.0:
                        bumped[surf_global, 1] = (
                            bumped[surf_global, 1]
                            + self._heatmap_bump_m * envelope)
                if self._heatmap_handle is not None:
                    try:
                        self._heatmap_handle.remove()
                    except Exception:
                        pass
                    self._heatmap_handle = None
                import trimesh
                tm = trimesh.Trimesh(
                    vertices=bumped,
                    faces=self._surf_faces,
                    process=False,
                )
                tm.visual.vertex_colors = colors
                self._heatmap_handle = self.server.scene.add_mesh_trimesh(
                    "/elastic_surface_heatmap", tm)
                self._heatmap_last_field_id = field_id
                self._heatmap_last_time = t_now
                self._heatmap_dirty = False
            self.surface_handle.visible = False
            self.surface_handle_wire.visible = False
        else:
            # Heatmap off: tear down the trimesh handle if it exists, and
            # restore the solid/wire visibility per tet_style.
            if self._heatmap_handle is not None:
                try:
                    self._heatmap_handle.remove()
                except Exception:
                    pass
                self._heatmap_handle = None
            self.surface_handle.visible = not tet_style
            self.surface_handle_wire.visible = tet_style

    def _geo_changed(self, _evt):
        self.coupler.use_geodesic_attenuation = bool(self.gui_use_geodesic.value)
        # Force a heatmap refresh so toggling shows immediate effect.
        self._apply_surface_vis()

    def _geo_beta_changed(self, _evt):
        self.coupler.geodesic_beta = float(self.gui_geo_beta.value)
        # Field uses the new β at next refresh; trigger one now.
        self.coupler._refresh_attenuation_field()
        self._heatmap_dirty = True
        self._apply_surface_vis()

    def _geo_C_changed(self, _evt):
        self.coupler.geodesic_C = float(self.gui_geo_C.value)
        self.coupler._refresh_attenuation_field()
        self._heatmap_dirty = True
        self._apply_surface_vis()

    def _heat_bump_changed(self, _evt):
        self._heatmap_bump_m = float(self.gui_heat_bump_cm.value) / 100.0
        self._heatmap_dirty = True
        self._apply_surface_vis()

    def _wave_changed(self, _evt):
        # Pull wave knobs back into instance state; envelope rebuild runs on
        # the next tick. Setting _heatmap_dirty forces an immediate refresh
        # so the user sees the change without waiting for the next impact.
        self._wave_speed_mps = float(self.gui_wave_speed.value)
        self._wave_sigma_m = float(self.gui_wave_width_cm.value) / 100.0
        self._wave_ringdown_cycles = float(self.gui_wave_cycles.value)
        self._heatmap_dirty = True
        self._apply_surface_vis()

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
        # Clear the wave anchor so the post-reset boulder counts as a fresh
        # impact and re-anchors on first contact (otherwise dt_since would
        # carry over from the pre-reset run).
        self._wave_t_impact = -1.0
        self._wave_last_impact_vert = None
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
        # Instanced body update: fill the pre-allocated buffers and push
        # to the BatchedMesh in two array writes (regardless of N bodies).
        descs = w._descs
        for k, bi in enumerate(self._body_idxs):
            db = descs[int(bi)].dcr_body
            self._bp_buf[k] = db.position
            self._bw_buf[k] = db.orientation
        # Wrap the two writes in server.atomic() so the browser applies
        # them as a single transaction (no inter-frame teleport).
        with self.server.atomic():
            self._batched_bodies.batched_positions = self._bp_buf
            self._batched_bodies.batched_wxyzs = self._bw_buf
        # Elastic surface — honors the Visualization checkboxes (render
        # FEM vibration, FEM tet-mesh style, show attenuation heatmap).
        # Default: flat solid slab, so the road/shelf reads as a plain
        # rigid body and the Φ·q compute is skipped entirely.
        self._apply_surface_vis()

        # HUD throttle: text fields don't need to update at solver rate.
        # ~33 Hz refresh feels live to the eye and slashes per-tick
        # websocket chatter. All 15 writes wrapped in server.atomic() so
        # they hit the browser as a single transaction.
        self._frame += 1
        if (self._frame % self._hud_interval) != 0:
            return
        from dcr.rigid.energy import rigid_kinetic_energy
        bodies = [d.dcr_body for d in w._descs]
        e_rigid = rigid_kinetic_energy(bodies)
        e_modal = float(modal_energy(
            self.coupler._stepper.q, self.coupler._stepper.qdot,
            self.coupler.modal.frequencies))
        with self.server.atomic():
            self.gui_t.value = f"{w.time:.3f}"
            self.gui_step_ms.value = f"{w.last_step_ms:.2f}"
            self.gui_e_rigid.value = f"{e_rigid:.4f}"
            self.gui_e_modal.value = f"{e_modal:.4f}"
            self.gui_e_loss.value = f"{w.last_E_loss:.4f}"
            self.gui_e_inj.value = f"{self.coupler.last_E_modal_injected:.4f}"
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
    ap.add_argument(
        "--legacy-coupling", action="store_true",
        help="Start with the pre-§12 coupling (passive scaling, no reservoir, "
             "lambda_only) instead of the recommended reservoir+delta_p+"
             "prescribed combo. Either way, toggle live in the DCR GUI folder.")
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
    ap.add_argument(
        "--mesh-resolution", choices=MESH_RESOLUTIONS, default="medium",
        help="Slab FEM mesh subdivision level. 'medium' (default) matches the "
             "baseline (nx,ny,nz); 'coarse' ~halves the in-plane subdivisions "
             "for fast iteration; 'fine' 1.5x in-plane and 2x through-thickness "
             "(adds a few seconds to scene startup — modal eigenproblem scales "
             "with node count). Baked at scene build time (no live switching).")
    args = ap.parse_args()

    builder = SCENES[args.scene]
    world, coupler, boxes, mesh, title = builder(
        device=args.device, h=args.h, eta=args.eta, beta=args.beta,
        causal_gating=args.causal_gating,
        modal_decay_gamma=args.modal_decay_gamma,
        enable_phase_b=args.phase_b,
        ms_beta=args.ms_beta,
        use_bj=args.use_bj,
        mesh_resolution=args.mesh_resolution,
    )
    n_tets = int(mesh.tets.shape[0])
    n_nodes = int(mesh.vertices.shape[0])
    print(f"\n{title}")
    print(f"  bodies={len(world._descs)}  modes={coupler.modal.U.shape[1]}")
    print(f"  mesh resolution={args.mesh_resolution}  "
          f"tets={n_tets}  nodes={n_nodes}")
    print(f"  device={args.device}  h={args.h:g}  beta={args.beta}  eta={args.eta}")
    print(f"  viser: http://localhost:{args.port}\n")
    viewer = AVBDDCRViewer(args, world, coupler, boxes, mesh, title)
    viewer.run()


if __name__ == "__main__":
    main()
