"""Payload mass-loading demo — the per-body coupling toggle made visible.

One soft plate, one resting payload, one falling impactor. The scene is built
TWICE by the viewer (side by side); the ONLY difference is whether the
payload's floor rows are in `tracked_body_indices` when the native support is
enabled:

  coupled=True  — the payload's support rows carry the plate's modal columns
                  (the shared two-way constraint): its weight pre-sags the
                  plate, the ring shakes it, and the added mass DETUNES and
                  DAMPS the ring.
  coupled=False — the payload is left OFF the tracked list AND given the
                  previous one-way treatment: every substep its floor-row
                  anchors are moved to the live deformed-surface height
                  y_rest + U_y·q (the readout ride the removed two-band path
                  used), so it bounces on the ring like the old bystanders
                  did. But its weight and inertia never enter q — the plate's
                  response never knows the payload exists: no sag under it,
                  no mass-loading detune, no contact damping.

The impactor is tracked on BOTH sides, so both plates receive the same
excitation; the payload is the only experimental variable.

Soft plate on purpose: with the viewer's stock "soft" material (E = 1e8,
rho = 1000) the fundamental is ~4-5 Hz with mm-cm deflection, so sag, ring,
detune, and payload rattle are all visible at TRUE SCALE (render
exaggeration 1). No cargo bodies, no box-box network — this is the support
row (two_band_coupling.html) in its purest form.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import (
    evaluate_basis_at_point, make_debug_reduced_shelf_support)
from dcr.avbd._solver.solver_6dof import FLOOR_CONTACT_6DOF, _modal_quat_to_R
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


@dataclass
class PayloadPlateHandle:
    world: AVBDDCRWorld
    rs: object
    avbd_idx: dict = field(default_factory=dict)   # name -> avbd body index
    coupled: bool = True
    support_top: float = 0.0
    support_length: float = 0.8
    support_width: float = 0.4
    payload_half: float = 0.06
    impactor_half: float = 0.05


def build_payload_plate_scene(
    *,
    coupled: bool = True,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 12,
    substeps: int = 4,
    solver: str = "avbd",
    support_length: float = 0.8,
    support_width: float = 0.4,
    support_thickness: float = 0.02,
    support_top: float = 0.0,
    support_youngs: float = 1.0e8,       # the viewer's "soft" preset: ~4.7 Hz
    support_density: float = 1000.0,
    payload_mass: float = 3.0,
    payload_size: float = 0.12,
    payload_x: float = 0.18,
    impactor_mass: float = 1.0,
    impactor_size: float = 0.10,
    impactor_x: float = -0.22,
    impactor_drop: float = 0.30,
    rayleigh_alpha0: float = 1.2,        # tau ~ 1.7 s — a countable ring
    rayleigh_alpha1: float = 1.0e-5,
    friction: float = 0.5,
    device_resident: bool | None = None,
) -> PayloadPlateHandle:
    ph, ih = 0.5 * float(payload_size), 0.5 * float(impactor_size)
    world = AVBDDCRWorld(
        h=h, device=device, avbd_iterations=int(iterations),
        avbd_substeps=int(substeps),
        solver_kind=solver if solver in ("xpbd", "impulse") else "avbd")
    if device_resident is not None and solver != "xpbd":
        world._solver._modal_device_resident = bool(device_resident)
    world.add_floor(floor_y=support_top, friction=float(friction),
                    name="support")

    idx: dict[str, int] = {}
    di = world.add_box(
        mass=float(payload_mass), half_extents=(ph, ph, ph),
        position=(float(payload_x), support_top + ph, 0.0),
        friction=float(friction), name="payload")
    idx["payload"] = int(world._descs[di].avbd_body.index)
    di = world.add_box(
        mass=float(impactor_mass), half_extents=(ih, ih, ih),
        position=(float(impactor_x), support_top + ih + float(impactor_drop),
                  0.0),
        friction=float(friction), name="impactor")
    idx["impactor"] = int(world._descs[di].avbd_body.index)

    # Identical basis on both sides (same zones either way), so the uncoupled
    # plate is the exact unloaded reference for the coupled one.
    rs = make_debug_reduced_shelf_support(
        length=support_length, width=support_width,
        thickness=support_thickness,
        youngs=support_youngs, density=support_density, poisson=0.30,
        n_modes_global=8, n_modes_local=2,
        contact_zone_centers=[(float(payload_x), 0.0),
                              (float(impactor_x), 0.0)],
        probe_xz=[(float(payload_x), 0.0), (float(impactor_x), 0.0)],
        y_rest=support_top, overlay_enabled=False,
        rayleigh_alpha0=float(rayleigh_alpha0),
        rayleigh_alpha1=float(rayleigh_alpha1),
        to_eigenbasis=True)

    # THE toggle: an untracked body keeps plain rigid-floor rows — the plate
    # response never sees it. The one-way arm then rides those rows on the
    # readout surface (hook below), exactly like the previous scheme.
    tracked = [idx["impactor"]] + ([idx["payload"]] if coupled else [])
    world.enable_reduced_modal_support(
        rs, tracked_body_indices=tracked,
        shelf_length=support_length, shelf_width=support_width,
        shelf_y_rest=support_top, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)

    handle = PayloadPlateHandle(
        world=world, rs=rs, avbd_idx=idx, coupled=bool(coupled),
        support_top=float(support_top), support_length=float(support_length),
        support_width=float(support_width), payload_half=ph,
        impactor_half=ih)
    if not coupled and solver != "xpbd":
        _attach_one_way_ride(handle)
    return handle


def _attach_one_way_ride(handle: PayloadPlateHandle) -> None:
    """The previous ONE-WAY treatment for the uncoupled payload: each substep,
    move its floor-row anchors to the live deformed-surface height

        y_anchor = y_rest + U_y(x_corner, z_corner) · q

    so the payload RIDES the readout ring — it bounces like the old bystanders
    did, and the surface never interpenetrates it. The coupling stays strictly
    one-way: the payload's weight/inertia appear in no modal row, so the plate
    neither sags under it nor detunes nor loses ring energy to it.

    # DEVIATION: intentionally one-way — this is the A/B *baseline* arm. It
    # re-creates, at the demo layer, the removed two-band anchor-follow path
    # (see reduced_support.py, "two-band split ... REMOVED"): surface → body
    # only, no back-reaction. Not a solver feature; AVBD host path only (the
    # hook disables CUDA-graph capture, which this CPU demo never uses).
    """
    s = handle.world._solver
    bi = int(handle.avbd_idx["payload"])
    L, W, top = handle.support_length, handle.support_width, handle.support_top

    if not hasattr(s, "_rows"):
        # Impulse backend: no AVBD row pool. Same one-way readout ride, moved
        # to the solver's floor registration: each substep the payload's floor
        # height follows the live surface at the body's (x, z) — surface →
        # body only, weight/inertia in no modal row (the A/B baseline arm).
        def hook_impulse(sol):
            q = sol.modal_q
            if q is None:
                return
            pos = sol._X[bi]
            u = evaluate_basis_at_point(
                handle.rs, (float(pos[0]), float(pos[2])),
                length=L, width=W, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
            y = top + float(u[1, :] @ q)
            sol._floors = [(b, y if b == bi else fy, mu)
                           for (b, fy, mu) in sol._floors]

        s.substep_begin_hook = hook_impulse
        return

    def hook(sol):
        q = sol.modal_q
        if q is None:
            return
        pos = np.asarray(sol.positions()[bi], dtype=np.float64)
        R = _modal_quat_to_R(
            np.asarray(sol.orientations()[bi], dtype=np.float64))
        pool = getattr(sol, "c_world_anchor", None)
        anchors = pool.numpy() if pool is not None else None  # cpu: zero-copy
        for i, row in enumerate(sol._rows):
            if row.type != FLOOR_CONTACT_6DOF or int(row.body_a) != bi:
                continue
            r_w = R @ np.asarray(row.off_a, dtype=np.float64)
            u = evaluate_basis_at_point(
                handle.rs, (float(pos[0] + r_w[0]), float(pos[2] + r_w[2])),
                length=L, width=W, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
            y = top + float(u[1, :] @ q)
            row.world_anchor = (row.world_anchor[0], y, row.world_anchor[2])
            if anchors is not None and i < anchors.shape[0]:
                anchors[i][1] = y

    s.substep_begin_hook = hook


def payload_point_deflection(handle: PayloadPlateHandle) -> float:
    """Plate surface deflection [m] at the payload's (x, z), read through the
    probe basis (probe 0 is parked at the payload point)."""
    return float(handle.rs.probe_U[0, 1, :] @ handle.rs.q)
