"""Many-body stress scene for the scale benchmark (reviewer gap: the paper's
scenes top out at 25 bodies; games-track reviewers ask for hundreds).

A large road-material slab (the truck scene's material: E = 10 GPa wood,
rho = 500) carries an N-body grid of resting crates plus one heavy crate
dropped at the center. N is the ONLY swept variable: the modal basis is
IDENTICAL at every N — 12 global modes + 16 local compliance bumps on a
fixed 4x4 zone grid (to_eigenbasis), NOT one bump per body — so a runtime
sweep over N isolates body / contact-row count from modal-block size.

Layout: crates fill a centered square grid (row-major, then trimmed to the
N cells nearest the center, deterministic lexicographic tie-break), with a
0.22 m exclusion disc at the origin so the impactor lands on bare slab.
Grid spacing stays >= 0.15 m for the default crate (0.10 m wide), so no
crate-crate contact exists at rest — every contact row is a support row,
and the count scales linearly in N. Practical cap: n_bodies <= 600 on the
default 4 m slab (spacing shrinks toward crate width beyond that).
"""
from __future__ import annotations

import math

from dcr.avbd.world import AVBDDCRWorld

from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, ReducedSceneHandle, build_support_and_attach,
)


def _grid_positions(n_bodies: int, half_span: float, excl_r: float,
                    min_spacing: float) -> list[tuple[float, float]]:
    """N grid cells nearest the center, excluding the impact disc.
    Deterministic: distance-squared key with (x, z) lexicographic tie-break."""
    cols = max(2, math.ceil(math.sqrt(float(n_bodies))))
    while True:
        spacing = 2.0 * half_span / (cols - 1)
        if spacing < min_spacing:
            raise ValueError(
                f"n_bodies={n_bodies} needs spacing {spacing:.3f} m < "
                f"{min_spacing} m on a {2*half_span:.1f} m span — enlarge the "
                f"slab or reduce n_bodies")
        pts = []
        for i in range(cols):
            for j in range(cols):
                x = -half_span + i * spacing
                z = -half_span + j * spacing
                if x * x + z * z > excl_r * excl_r:
                    pts.append((x, z))
        if len(pts) >= n_bodies:
            pts.sort(key=lambda p: (p[0] * p[0] + p[1] * p[1], p[0], p[1]))
            return pts[:n_bodies]
        cols += 1


def build_reduced_stress(
    *,
    n_bodies: int = 64,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 8,
    avbd_substeps: int = 4,
    # Road-material slab, sized to hold up to ~600 crates.
    support_length: float = 4.0,
    support_width: float = 4.0,
    support_thickness: float = 0.06,
    support_top: float = 0.03,
    youngs: float = 1.0e10,
    density: float = 500.0,
    poisson: float = 0.30,
    n_modes_global: int = 12,
    n_modes_local: int = 16,
    # Primary impactor: the truck scene's heavy crate, dropped at center.
    impactor_mass: float = 40.0,
    impactor_drop_height: float = 0.7,
    rayleigh_alpha0: float = 2.0,
    rayleigh_alpha1: float = 1.0e-5,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = True,
    modal_static_lp_tau: float = 0.05,
    solver: str = "avbd",
    cargo_material: str | None = None,
    cargo_all: bool = False,
    cargo_n_elastic: int = 3,
) -> ReducedSceneHandle:
    """Construct the N-body stress scene + attach the reduced-modal support.
    Returns the standard handle so every existing harness/viewer drives it."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
        solver_kind=solver if solver in ("xpbd", "impulse") else "avbd",
    )
    world.add_floor(floor_y=support_top, friction=0.5, name="road")

    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    top = support_top

    # ---- N resting crates on a centered grid. ----
    crate_h = (0.05, 0.04, 0.05)
    half_span = 0.5 * min(support_length, support_width) - 0.30
    grid = _grid_positions(int(n_bodies), half_span, excl_r=0.22,
                           min_spacing=0.15)
    resting_xz: list[tuple[float, float]] = []
    for bi, (cx, cz) in enumerate(grid):
        shade = 0.35 + 0.30 * ((bi * 7) % 5) / 4.0
        add(f"crate_{bi}", 1.5, crate_h,
            (cx, top + crate_h[1] + 0.001, cz), (shade, 0.72 * shade, 0.35 * shade),
            "crate", friction=0.5)
        resting_xz.append((cx, cz))

    # ---- The heavy crate: drops on the cleared center. ----
    drop_h = (0.12, 0.09, 0.10)
    impactor_idx = add(
        "drop_heavy", float(impactor_mass), drop_h,
        (0.0, top + drop_h[1] + float(impactor_drop_height), 0.0),
        (0.30, 0.22, 0.14), "crate", friction=0.6)

    # Fixed 4x4 local-compliance zone grid — deliberately NOT per body, so the
    # modal basis (12 global + 16 local -> eigenbasis) is byte-identical at
    # every N and the sweep isolates contact-row count.
    zs = [(-0.55 + 1.10 * i / 3.0) * half_span for i in range(4)]
    contact_zones = [(zx, zz) for zx in zs for zz in zs]
    probe_xz = [(0.5 * half_span, 0.0), (-0.5 * half_span, 0.0),
                (0.0, 0.5 * half_span), (0.0, -0.5 * half_span)]

    rs = build_support_and_attach(
        world, bodies,
        support_length=support_length, support_width=support_width,
        support_thickness=support_thickness, support_top=support_top,
        youngs=youngs, density=density, poisson=poisson,
        n_modes_global=n_modes_global, n_modes_local=n_modes_local,
        contact_zones=contact_zones, probe_xz=probe_xz,
        rayleigh_alpha0=rayleigh_alpha0, rayleigh_alpha1=rayleigh_alpha1,
        modal_impedance_scale=modal_impedance_scale,
        modal_damping_scale=modal_damping_scale,
        to_eigenbasis=to_eigenbasis, modal_static_lp_tau=modal_static_lp_tau,
        solver=solver, cargo_material=cargo_material,
        cargo_impactor_dcr=impactor_idx,
        cargo_all=cargo_all, cargo_n_elastic=cargo_n_elastic,
    )

    native_cube = getattr(rs, "_native_cargo_cube", None)
    native_idx = getattr(rs, "_native_cargo_avbd_idx", None)
    return ReducedSceneHandle(
        world=world, rs=rs,
        impactor_idx=impactor_idx,
        probe_indices=[b.dcr_idx for b in bodies[: min(8, len(bodies))]],
        bodies=bodies,
        name=f"Reduced-Coordinate AVBD Stress Grid (N={n_bodies})",
        impactor_label="crate",
        cargo_cube=native_cube,
        cargo_avbd_idx=native_idx,
        cargo_material=cargo_material,
        cargo_map=getattr(rs, "_native_cargo_map", None) or {},
    )
