"""Bookshelf-drop scene driven by the Reduced-Coordinate AVBD coupler.

The DCR "bookshelf" layout — a row of books standing on a soft cantilever
shelf, toppled when a heavy weight drops on the free end — but with the
**shelf itself as the reduced-modal deformable support**
(`ReducedCoupledAVBDCoupler`, the q_s + q_d coupled path), NOT the patch
`PassiveDCRCoupler`. The dropped weight bends the shelf's modal field and
the coupling tips the standing books through the deformed support geometry
inside the AVBD iteration (cross-block ρ·J_x·J_q^T).

A soft shelf (E = 0.5 GPa) makes the static sag q_s visibly large, so this
scene is the clearest read on the coupled static/dynamic split.

Render kinds: `book` only — the standing row plus a big closed book (a
heavy tome) as the dropped weight.
"""
from __future__ import annotations

from dcr.avbd.world import AVBDDCRWorld

from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, ReducedSceneHandle, build_support_and_attach,
)


def build_reduced_shelf(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 8,
    avbd_substeps: int = 4,
    # Shelf = the reduced-modal support. 0.8 m × 0.3 m soft board.
    support_length: float = 0.8,
    support_width: float = 0.3,
    support_thickness: float = 0.03,
    support_top: float = 0.015,
    youngs: float = 0.5e9,
    density: float = 600.0,
    poisson: float = 0.30,
    n_modes_global: int = 10,
    n_modes_local: int = 14,
    # Primary impactor: the heavy weight dropped on the shelf's free end.
    impactor_mass: float = 6.0,
    impactor_drop_height: float = 0.5,
    impactor_v0: float = 0.0,
    rayleigh_alpha0: float = 3.0,
    rayleigh_alpha1: float = 1.0e-5,
    modal_impedance_scale: float = 1.0,
    modal_damping_scale: float = 1.0,
    to_eigenbasis: bool = True,
    modal_static_lp_tau: float = 0.05,
) -> ReducedSceneHandle:
    """Construct the bookshelf scene + attach the reduced-coupled AVBD
    support (the shelf). Returns a handle with per-body render metadata."""
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
    )
    world.add_floor(floor_y=support_top, friction=0.5, name="shelf")

    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    top = support_top
    resting_xz: list[tuple[float, float]] = []

    # ---- Five books standing in a row near the fixed (left) edge. ----
    book_h = (0.018, 0.04, 0.03)
    book_colors = [
        (0.80, 0.20, 0.20), (0.20, 0.55, 0.25), (0.20, 0.25, 0.75),
        (0.72, 0.52, 0.12), (0.55, 0.22, 0.55),
    ]
    for bi in range(5):
        bx = -0.20 + bi * 0.045
        add(f"book_{bi}", 1.0, book_h,
            (bx, top + book_h[1] + 0.001, 0.0), book_colors[bi], "book",
            friction=0.3)
        resting_xz.append((bx, 0.0))

    # ---- The dropped weight: a big closed book (heavy tome) onto the
    # shelf's free end. Flat, wide book shape; thematically a book, not a
    # crate. This is the controllable impactor. ----
    drop_h = (0.06, 0.035, 0.08)
    impactor_idx = add(
        "drop_book", float(impactor_mass), drop_h,
        (0.22, top + drop_h[1] + float(impactor_drop_height), 0.0),
        (0.45, 0.12, 0.12), "book", friction=0.5,
        vel=(0.0, float(impactor_v0), 0.0))

    contact_zones = [(0.22, 0.0)] + resting_xz
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
    )

    return ReducedSceneHandle(
        world=world, rs=rs,
        impactor_idx=impactor_idx,
        probe_indices=[b.dcr_idx for b in bodies if b.render_kind == "book"],
        bodies=bodies,
        name="Reduced-Coordinate AVBD Bookshelf Drop",
        impactor_label="book",
    )
