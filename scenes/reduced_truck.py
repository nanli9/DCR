"""Road-impact scene driven by the Reduced-Coordinate AVBD coupler.

The DCR "truck / road" layout — a heavy crate dropped on a wood-like road
slab, with traffic cones, stacked lumber, and lighter crates resting
nearby — but with the **road itself as the reduced-modal deformable
support** (`ReducedCoupledAVBDCoupler`, the q_s + q_d coupled path), NOT
the patch `PassiveDCRCoupler`. The dropped crate's impact rings the road's
modal field and the coupling rocks the resting cones / lumber / crates
through the deformed support geometry inside the AVBD iteration
(cross-block ρ·J_x·J_q^T).

Render kinds: `crate`, `cone`, `lumber` (decorated assets in
`model/<kind>/`, fetched locally via scripts/fetch_sketchfab_models.py).
"""
from __future__ import annotations

from dcr.avbd.world import AVBDDCRWorld

from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, ReducedSceneHandle, build_support_and_attach,
)


def build_reduced_truck(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 8,
    avbd_substeps: int = 4,
    # Road = the reduced-modal support. 2.5 m × 1.5 m wood slab.
    support_length: float = 2.5,
    support_width: float = 1.5,
    support_thickness: float = 0.06,
    support_top: float = 0.03,
    youngs: float = 1.0e10,
    density: float = 500.0,
    poisson: float = 0.30,
    n_modes_global: int = 12,
    n_modes_local: int = 16,
    # Primary impactor: the heavy crate dropped on road center.
    impactor_mass: float = 40.0,
    impactor_drop_height: float = 0.7,
    impactor_v0: float = 0.0,
    rayleigh_alpha0: float = 2.0,
    rayleigh_alpha1: float = 1.0e-5,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = True,
    modal_static_lp_tau: float = 0.05,
    solver: str = "avbd",
    cargo_material: str | None = None,
    cargo_all: bool = False,
    cargo_n_elastic: int = 6,
) -> ReducedSceneHandle:
    """Construct the road scene + attach the reduced-coupled AVBD support
    (the road). Returns a handle carrying per-body render metadata."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
        solver_kind="xpbd" if solver == "xpbd" else "avbd",
    )
    world.add_floor(floor_y=support_top, friction=0.6, name="road")

    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    top = support_top
    resting_xz: list[tuple[float, float]] = []

    # ---- Two lighter crates resting off-center so the impact rocks them. ----
    crate_h = (0.10, 0.07, 0.08)
    for ci, (cx, cz, col) in enumerate([
        (-0.6, -0.22, (0.55, 0.40, 0.22)),
        (-0.6, 0.22, (0.45, 0.32, 0.18)),
    ]):
        add(f"crate_rest_{ci}", 2.5, crate_h,
            (cx, top + crate_h[1] + 0.001, cz), col, "crate", friction=0.6)
        resting_xz.append((cx, cz))

    # ---- Five traffic cones in a row along the road's width. ----
    cone_h = (0.03, 0.05, 0.03)
    for ci, cz in enumerate([-0.4, -0.2, 0.0, 0.2, 0.4]):
        add(f"cone_{ci}", 0.3, cone_h,
            (0.7, top + cone_h[1] + 0.001, cz), (1.0, 0.45, 0.05), "cone",
            friction=0.5)
        resting_xz.append((0.7, cz))

    # ---- Stacked lumber (4 timber blocks) on the other side. ----
    lumber_h = (0.06, 0.025, 0.12)
    for li in range(4):
        y = top + lumber_h[1] + li * 2 * lumber_h[1] + 0.001 * (li + 1)
        add(f"lumber_{li}", 2.0, lumber_h,
            (0.35, y, 0.0), (0.62, 0.42, 0.20), "lumber", friction=0.7)
    resting_xz.append((0.35, 0.0))

    # ---- The heavy crate: drops on road center (the controllable impactor). ----
    drop_h = (0.12, 0.09, 0.10)
    impactor_idx = add(
        "drop_heavy", float(impactor_mass), drop_h,
        (0.0, top + drop_h[1] + float(impactor_drop_height), 0.0),
        (0.30, 0.22, 0.14), "crate", friction=0.6,
        vel=(0.0, float(impactor_v0), 0.0))

    contact_zones = [(0.0, 0.0)] + resting_xz
    rs = build_support_and_attach(
        world, bodies,
        support_length=support_length, support_width=support_width,
        support_thickness=support_thickness, support_top=support_top,
        youngs=youngs, density=density, poisson=poisson,
        n_modes_global=n_modes_global, n_modes_local=n_modes_local,
        contact_zones=contact_zones, probe_xz=resting_xz,
        rayleigh_alpha0=rayleigh_alpha0, rayleigh_alpha1=rayleigh_alpha1,
        modal_impedance_scale=modal_impedance_scale,
        modal_damping_scale=modal_damping_scale,
        to_eigenbasis=to_eigenbasis, modal_static_lp_tau=modal_static_lp_tau,
        solver=solver, cargo_material=cargo_material,
        cargo_impactor_dcr=impactor_idx,
        cargo_all=cargo_all, cargo_n_elastic=cargo_n_elastic,
    )

    coupler = world.reduced_coupled_coupler
    # native path stashes the impactor cargo on rs; the coupler attrs are the
    # legacy (pre-native) source and are absent on this branch
    native_cube = getattr(rs, "_native_cargo_cube", None)
    native_idx = getattr(rs, "_native_cargo_avbd_idx", None)
    return ReducedSceneHandle(
        world=world, rs=rs,
        impactor_idx=impactor_idx,
        probe_indices=[b.dcr_idx for b in bodies if b.render_kind == "cone"],
        bodies=bodies,
        name="Reduced-Coordinate AVBD Road Impact",
        impactor_label="crate",
        cargo_cube=(native_cube if native_cube is not None
                    else getattr(coupler, "_scene_cargo_cube", None)),
        cargo_avbd_idx=(native_idx if native_idx is not None
                        else getattr(coupler, "_scene_cargo_avbd_idx", None)),
        cargo_material=cargo_material,
        cargo_map=getattr(rs, "_native_cargo_map", None) or {},
    )
