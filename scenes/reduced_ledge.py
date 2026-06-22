"""Cliff-ledge rockfall scene driven by the Reduced-Coordinate AVBD coupler.

The DCR "ledge" layout — a boulder dropped onto a stone cantilever ledge,
toppling a small set of balanced pillars on a pedestal — but with the
**ledge itself as the reduced-modal deformable support**
(`ReducedCoupledAVBDCoupler`, the q_s + q_d coupled path), NOT the patch
`PassiveDCRCoupler`. The boulder's impact rings the ledge's modal field
and the coupling unbalances the distant pillars through the deformed
support geometry inside the AVBD iteration (cross-block ρ·J_x·J_q^T).

The ledge material is matched to the road scene (stiff-but-light, E = 10
GPa, ρ = 500) so the modal projection couples strongly — the same regime
the patch-DCR ledge scene was tuned to in the AVBD branch.

Render kinds: `boulder` (the dropped rock) and `pillar` (the balanced
columns); the pedestal renders as its flat collision box so the pillars
balance on a flat surface rather than a rounded rock.
"""
from __future__ import annotations

from dcr.avbd.world import AVBDDCRWorld

from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, ReducedSceneHandle, build_support_and_attach,
)


def build_reduced_ledge(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 8,
    avbd_substeps: int = 4,
    # Ledge = the reduced-modal support. 1.2 m × 0.8 m stiff stone slab.
    support_length: float = 1.2,
    support_width: float = 0.8,
    support_thickness: float = 0.08,
    support_top: float = 0.04,
    youngs: float = 1.0e10,
    density: float = 500.0,
    poisson: float = 0.30,
    n_modes_global: int = 12,
    n_modes_local: int = 16,
    # Primary impactor: the boulder dropped onto the ledge.
    impactor_mass: float = 50.0,
    impactor_drop_height: float = 0.8,
    impactor_v0: float = 0.0,
    rayleigh_alpha0: float = 2.0,
    rayleigh_alpha1: float = 1.0e-5,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = True,
    modal_static_lp_tau: float = 0.05,
    solver: str = "avbd",
    cargo_material: str | None = None,
) -> ReducedSceneHandle:
    """Construct the ledge scene + attach the reduced-coupled AVBD support
    (the ledge). Returns a handle with per-body render metadata."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
        solver_kind="xpbd" if solver == "xpbd" else "avbd",
    )
    world.add_floor(floor_y=support_top, friction=0.5, name="ledge")

    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    top = support_top
    resting_xz: list[tuple[float, float]] = []

    # ---- Stone pedestal: a flat-topped block near ledge center. Rendered
    # as its collision box (NOT a rounded boulder) so the pillars balance on
    # a flat surface. Wider than tall to read as a platform. ----
    ped_h = (0.09, 0.045, 0.09)
    add("pedestal", 5.0, ped_h,
        (0.0, top + ped_h[1] + 0.001, 0.0), (0.55, 0.52, 0.47), "box",
        friction=0.4)
    resting_xz.append((0.0, 0.0))

    # ---- Three slender pillars balanced on the pedestal top. ----
    pillar_h = (0.012, 0.05, 0.012)
    pedestal_top = top + 2 * ped_h[1] + 0.001
    pillar_colors = [(0.72, 0.66, 0.58), (0.66, 0.60, 0.52), (0.78, 0.72, 0.64)]
    for si, sz in enumerate([-0.035, 0.0, 0.035]):
        add(f"pillar_{si}", 0.5, pillar_h,
            (0.0, pedestal_top + pillar_h[1] + 0.001, sz),
            pillar_colors[si], "pillar", friction=0.5)
        resting_xz.append((0.0, sz))

    # ---- The boulder: drops onto the ledge off to the side (impactor). ----
    br = 0.08
    impactor_idx = add(
        "boulder", float(impactor_mass), (br, br, br),
        (0.30, top + br + float(impactor_drop_height), 0.0),
        (0.42, 0.38, 0.32), "boulder", friction=0.5,
        vel=(0.0, float(impactor_v0), 0.0))
    resting_xz.append((0.30, 0.0))

    contact_zones = [(0.30, 0.0)] + resting_xz
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
    )

    coupler = world.reduced_coupled_coupler
    return ReducedSceneHandle(
        world=world, rs=rs,
        impactor_idx=impactor_idx,
        probe_indices=[b.dcr_idx for b in bodies if b.render_kind == "pillar"],
        bodies=bodies,
        name="Reduced-Coordinate AVBD Cliff Ledge Rockfall",
        impactor_label="boulder",
        cargo_cube=getattr(coupler, "_scene_cargo_cube", None),
        cargo_avbd_idx=getattr(coupler, "_scene_cargo_avbd_idx", None),
        cargo_material=cargo_material,
    )
