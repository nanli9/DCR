"""Mirror an already-built AVBD reduced-modal scene onto the XPBD backend.

The four scene builders (`reduced_dinner_table`, `reduced_truck`,
`reduced_shelf`, `reduced_ledge`) are AVBD-bound — they emit an
`AVBDDCRWorld` + a `ReducedSupport` + per-body `ReducedSceneBody` metadata.
For the viser viewer's solver dropdown we want the SAME scene running on
the XPBD coupler instead. Rather than fork the four builders, we build the
AVBD scene as the source of truth and mirror it onto a fresh `XPBDWorld`
here. The reduced support `rs` is backend-agnostic and shared verbatim.

The mirror reads everything from the AVBD scene's `_descs[i].dcr_body`
(mass, position, orientation wxyz, velocity, friction) and the shelf
metadata from `rs.point_positions_rest` / the known grid constants.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dcr.xpbd import XPBDWorld, ReducedCoupledXPBDCoupler
from scenes.reduced_scene_common import ReducedSceneBody, ReducedSceneHandle
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


@dataclass
class XPBDSceneHandle:
    """The XPBD counterpart of `ReducedSceneHandle`. Duck-typed to expose
    the same minimum surface the viser viewer reads: `.world`, `.rs`,
    `.bodies`, `.name`, `.impactor_idx`, `.impactor_label`."""
    world: XPBDWorld
    rs: object              # ReducedSupport (same instance as AVBD's)
    impactor_idx: int       # XPBD body index of the dropped impactor
    probe_indices: list[int]
    bodies: list[ReducedSceneBody]
    name: str
    impactor_label: str
    # Per-scene-body XPBD index. The scene's `ReducedSceneBody.dcr_idx`
    # references the AVBD/DCR scene's body list (which usually has the
    # floor at index 0), NOT the XPBD body list — readers MUST translate
    # via this map before indexing into `world.positions()`.
    dcr_to_xpbd: dict[int, int] = None  # type: ignore[assignment]

    @property
    def coupler(self) -> ReducedCoupledXPBDCoupler:
        return self.world.coupler


def _wxyz_to_xyzw(q: np.ndarray) -> tuple[float, float, float, float]:
    """DCR / AVBD use (w, x, y, z); XPBD uses (x, y, z, w)."""
    w, x, y, z = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    return (x, y, z, w)


def mirror_to_xpbd(
    handle: ReducedSceneHandle,
    *,
    h: float,
    substeps: int,
    iterations: int,
    device: str = "cpu",
    contact_stiffness: float = 1.0e9,
    modal_static_lp_tau: float = 0.05,
    anchor_static_lowpass: bool = True,
) -> XPBDSceneHandle:
    """Build an XPBD-backed replica of `handle`'s scene.

    Bodies are added in the same order as `handle.bodies`, so the AVBD body
    list and the XPBD body list share indices position-for-position. The
    tracked-body set is derived from `handle.rs.probe_body_indices`
    (those are the bodies the AVBD coupler tracked), remapped to XPBD's
    index space via that same shared ordering.
    """
    rs = handle.rs

    # Shelf metadata is encoded in the rest-point grid. Length / width / y
    # are derived; n_grid_{x,z} are the well-known scene-shared constants.
    pts = rs.point_positions_rest
    shelf_length = float(pts[:, 0].max() - pts[:, 0].min())
    shelf_width = float(pts[:, 2].max() - pts[:, 2].min())
    shelf_y_rest = float(pts[0, 1])

    # Floor goes well below the support so XPBD's solve_floor_contacts never
    # fires on non-tracked bodies (we don't have any in these scenes, but be
    # safe). The coupler will mask out tracked bodies anyway. `device` is the
    # Warp device for the XPBD solver state + kernels — same code path on
    # cpu/cuda; the (numpy) coupler hooks sync via .numpy()/.assign() either
    # way. Per-frame coupler bandwidth is small (r×r modal block + per-row
    # arrays), so even cuda residency is workable for the reference path.
    xworld = XPBDWorld(
        dt=float(h),
        substeps=int(substeps),
        iterations=int(iterations),
        gravity=(0.0, -9.81, 0.0),
        floor_y=shelf_y_rest - 5.0,
        friction=0.4,
        device=device,
    )

    # Mirror each body. The DCR-side RigidBody on the AVBD descriptor carries
    # mass / position / orientation (wxyz) / velocity (6-vec) / friction.
    dcr_to_xpbd: dict[int, int] = {}
    for b in handle.bodies:
        desc = handle.world._descs[b.dcr_idx]
        dcr_b = desc.dcr_body
        pos = tuple(float(c) for c in dcr_b.position)
        quat_xyzw = _wxyz_to_xyzw(dcr_b.orientation)
        v_lin = tuple(float(c) for c in dcr_b.velocity[:3])
        omega = tuple(float(c) for c in dcr_b.velocity[3:6])
        # Static / movable: the AVBD scene marks `is_static`; mirror it.
        if getattr(dcr_b, "is_static", False):
            xbox = xworld.add_box(
                position=pos, half_extents=b.half_extents, mass=0.0,
                quaternion=quat_xyzw, velocity=(0.0, 0.0, 0.0),
                omega=(0.0, 0.0, 0.0), color=b.color, static=True)
        else:
            xbox = xworld.add_box(
                position=pos, half_extents=b.half_extents,
                mass=float(dcr_b.mass), quaternion=quat_xyzw,
                velocity=v_lin, omega=omega, color=b.color)
        dcr_to_xpbd[b.dcr_idx] = int(xbox.index)

    # Tracked bodies — `rs.probe_body_indices` is the AVBD-side index set the
    # AVBD coupler tracked. Rebuild it in XPBD-space by walking the AVBD
    # `_descs` to find the matching DCR index, then look up XPBD's mirror.
    avbd_tracked: set[int] = set(int(i) for i in rs.probe_body_indices)
    tracked_xpbd: list[int] = []
    for i_dcr, desc in enumerate(handle.world._descs):
        if desc.avbd_body is None:
            continue
        if int(desc.avbd_body.index) in avbd_tracked and i_dcr in dcr_to_xpbd:
            tracked_xpbd.append(dcr_to_xpbd[i_dcr])
    # Mirror's `rs.probe_body_indices` lives in AVBD-space; the XPBD coupler
    # uses its own list (`coupler.tracked_body_indices`). Keep `rs` shared
    # and don't mutate `probe_body_indices` — the AVBD scene still owns it.

    xworld.attach_reduced_coupled_xpbd(
        rs,
        tracked_body_indices=tracked_xpbd,
        shelf_length=shelf_length,
        shelf_width=shelf_width,
        shelf_y_rest=shelf_y_rest,
        n_grid_x=N_GRID_X,
        n_grid_z=N_GRID_Z,
        contact_stiffness=float(contact_stiffness),
        modal_static_lp_tau=float(modal_static_lp_tau),
        anchor_static_lowpass=bool(anchor_static_lowpass),
    )

    impactor_xpbd_idx = dcr_to_xpbd.get(handle.impactor_idx, -1)
    probe_xpbd_idx = [dcr_to_xpbd[i] for i in handle.probe_indices
                      if i in dcr_to_xpbd]
    return XPBDSceneHandle(
        world=xworld, rs=rs,
        impactor_idx=impactor_xpbd_idx,
        probe_indices=probe_xpbd_idx,
        bodies=handle.bodies,
        name=handle.name + " (XPBD)",
        impactor_label=handle.impactor_label,
        dcr_to_xpbd=dcr_to_xpbd,
    )
