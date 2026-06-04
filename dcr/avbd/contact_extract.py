"""Per-step contact + impulse extraction from the AVBD 6-DOF solver.

`Solver6DOF` exposes `lambdas()` (the augmented-Lagrangian dual vector
over all constraint rows) and a row metadata list `_rows`. This module
walks both, identifies each *normal* contact row (FLOOR or BOX_BOX) and
its sibling tangent rows, and assembles a list of
`dcr.rigid.collision.Contact` objects + a per-contact lam-triple array
shaped exactly the way `PassiveDCRCoupler.process_step` expects:

    lam[3*ci + 0] = λ along the contact normal in DCR convention
    lam[3*ci + 1] = λ along DCR tangent t1
    lam[3*ci + 2] = λ along DCR tangent t2

Note on bases: AVBD picks its own tangent basis per contact (world x̂/ẑ
for floor rows, n_hat/t_hat/b_hat from the manifold kernel for BOX_BOX
rows). The DCR patch coupler picks tangents via `_pick_friction_dirs`
applied to the contact normal. We rebase the world-space impulse vector
between the two conventions so the *spatial* impulse is preserved even
when the per-component magnitudes differ.

# DEVIATION: AVBD's `c_lambda` is treated as having impulse units
# (force * dt, BDF1 convention) — multiplied into world-space impulses
# without an extra `× dt`. This matches what the patch coupler's K_total
# solve expects. tests/avbd/test_impulse_units.py is the empirical gate.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from dcr.rigid.body import quat_to_rot
from dcr.rigid.collision import Contact
from dcr.rigid.solver import _pick_friction_dirs


# Vendored type-code constants (must match _solver/solver_6dof.py).
FLOOR_CONTACT_6DOF = 0
CONTACT_TANGENT_6DOF = 1
PIN_6DOF = 2
BOX_BOX_CONTACT_6DOF = 3


@dataclass
class AVBDContactRecord:
    """Per-contact bundle: the DCR Contact + its triple-index into the
    flat lam array. Useful for diagnostics and the impulse-units test.
    """
    contact: Contact
    row_idx_normal: int        # index in solver._rows of the normal row
    row_idx_t1: int            # -1 if no tangent (friction=0)
    row_idx_t2: int
    avbd_normal_world: NDArray[np.float64]  # AVBD's n_hat for this row
    avbd_t1_world: NDArray[np.float64]      # AVBD's tangent direction 1
    avbd_t2_world: NDArray[np.float64]
    j_world: NDArray[np.float64]            # reconstructed world-space impulse


def _xyzw_to_wxyz(q_xyzw: NDArray[np.float64]) -> NDArray[np.float64]:
    """AVBD stores quaternions as XYZW; DCR uses WXYZ."""
    return np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]])


def _avbd_quat_to_rot(q_xyzw: NDArray[np.float64]) -> NDArray[np.float64]:
    return quat_to_rot(_xyzw_to_wxyz(q_xyzw))


def extract_contacts(
    solver,
    floor_body_idx: int | None,
    prev_contact_keys: set | None = None,
    dt: float | None = None,
    avbd_to_dcr: dict[int, int] | None = None,
) -> tuple[
    list[Contact],
    NDArray[np.float64],
    NDArray[np.float64],
    list[AVBDContactRecord],
    set,
]:
    """Walk solver rows, build DCR-shaped contacts + lam triples.

    Args:
        solver: a Solver6DOF instance (already stepped this frame).
        floor_body_idx: the DCR-side index of the synthetic "floor" body
            in the world's parallel `_dcr_bodies` list. FLOOR_CONTACT_6DOF
            rows are mapped as `(box_body_idx, floor_body_idx)`. None
            disables floor-contact extraction (BOX_BOX only).
        prev_contact_keys: set of (body_a, body_b, row_idx) tuples seen
            on the previous step; used to populate Contact.is_new.
        dt: rigid timestep. Required to convert AVBD's dual variables
            (which carry force units in BDF1 — verified empirically with
            ratio Σ|λ|/(m·g·h) = 1/h) into impulse units that the patch
            coupler's modal projection expects. If None, falls back to
            `solver.dt`.
        avbd_to_dcr: optional dict mapping AVBD-side body index → DCR-side
            body index. When the world's `_descs` list has a static floor
            registered BEFORE any dynamic body, the DCR-side index is
            shifted by +1 relative to the AVBD-side index (the floor has
            no AVBD body). Without this map the emitted Contact records
            collide on `body_a == body_b == 0`, which silently breaks any
            downstream code that clusters contacts by body pair. If None
            (legacy callers), the identity map is used.

    Returns:
        contacts:      list[Contact], one per normal row that has λ_n > 0.
        lam:           (3*n_contacts,) flat array, normal+t1+t2 magnitudes
                       in DCR's tangent basis.
        k_normal:      (n_contacts,) per-contact normal-row penalty stiffness
                       k_N (c_penalty), parallel to `contacts`. Feeds the
                       coupler's 'augmented' effective-impulse source
                       J_eff = lam + h·k_N·C⁺·n (realtime-coupling-fix §2.2).
        records:       list[AVBDContactRecord], parallel to contacts.
        current_keys:  set of keys for next step's `prev_contact_keys`.
    """
    if prev_contact_keys is None:
        prev_contact_keys = set()

    def _to_dcr(avbd_idx: int) -> int:
        if avbd_to_dcr is None:
            return int(avbd_idx)
        return int(avbd_to_dcr.get(int(avbd_idx), int(avbd_idx)))
    # AVBD λ is force-like in BDF1; multiply by dt to obtain impulse.
    h = float(dt) if dt is not None else float(solver.dt)
    rows = solver._rows
    n_active = (
        int(solver.n_active_rows.numpy()[0])
        if solver.n_active_rows is not None
        else len(rows)
    )
    if n_active == 0:
        return [], np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64), [], set()

    # ---- Pull state from GPU ------------------------------------------------
    positions = solver.positions()          # (n_b, 3)
    orientations = solver.orientations()    # (n_b, 4) xyzw
    lambdas = solver.lambdas()              # (n_rows,)
    penalties = solver.penalties()          # (n_rows,) per-row stiffness k
    types = solver.c_type.numpy()           # (n_rows,)
    body_a = solver.c_body_a.numpy()
    body_b = solver.c_body_b.numpy()
    # off_a / off_b live as vec3 arrays.
    off_a = solver.c_off_a.numpy().reshape(-1, 3)
    # c_world_anchor for FLOOR rows holds (0, floor_y, 0); for tangent rows
    # it holds the tangent direction; for BOX_BOX rows it is unused.
    anchors = solver.c_world_anchor.numpy().reshape(-1, 3)
    siblings = solver.c_sibling.numpy()
    actives = solver.c_active.numpy()

    # Pre-compute a sibling map: normal-row idx -> (t1_row, t2_row).
    # In AVBD's _Row layout, tangent rows store `sibling = normal_idx` and
    # `partner = the other tangent of the same contact`.
    partners = solver.c_partner.numpy()
    normal_to_tangents: dict[int, tuple[int, int]] = {}
    for j in range(n_active):
        if int(types[j]) != CONTACT_TANGENT_6DOF:
            continue
        sib = int(siblings[j])
        if sib < 0:
            continue
        par = int(partners[j])
        if sib not in normal_to_tangents:
            other = par if par >= 0 else -1
            normal_to_tangents[sib] = (j, other)

    contacts: list[Contact] = []
    records: list[AVBDContactRecord] = []
    triples: list[float] = []
    k_normals: list[float] = []   # per-contact normal-row penalty k_N
    current_keys: set = set()

    for i in range(n_active):
        t = int(types[i])
        if t not in (FLOOR_CONTACT_6DOF, BOX_BOX_CONTACT_6DOF):
            continue
        if not bool(actives[i]):
            continue
        lam_n = float(lambdas[i])
        # Skip rows that the solver flagged active but didn't actually
        # produce a real contact impulse (numerical noise / separating).
        if abs(lam_n) < 1e-12:
            continue

        # Body indices on the AVBD side (used for indexing AVBD arrays).
        # DCR-side indices (used in the emitted Contact record) are
        # computed below via _to_dcr — they may differ when a static
        # floor sits at DCR index 0 ahead of any dynamic body.
        ba_avbd = int(body_a[i])

        # ---- Contact point + world normal --------------------------------
        R_a = _avbd_quat_to_rot(orientations[ba_avbd])
        p_world = positions[ba_avbd] + R_a @ off_a[i]

        if t == FLOOR_CONTACT_6DOF:
            if floor_body_idx is None:
                continue
            bb = floor_body_idx                  # already DCR-side
            ba = _to_dcr(ba_avbd)                # AVBD → DCR for receiver
            n_world = np.array([0.0, 1.0, 0.0])  # AVBD assumes +Y floor
            floor_y = float(anchors[i, 1])
            penetration = max(0.0, floor_y - float(p_world[1]))
            # AVBD floor tangents are world (1,0,0) and (0,0,1) — read
            # from the anchor of each tangent row (it stores the axis).
            avbd_t1, avbd_t2 = np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])
        else:
            # BOX_BOX contact. Without a kernel-side patch persisting the
            # contact normal we estimate it from the inter-anchor vector
            # on the receiver side. This is approximate at large
            # penetrations but adequate for the patch coupler's K_total
            # solve, which only needs a reasonable normal direction.
            bb_avbd = int(body_b[i])
            R_b = _avbd_quat_to_rot(orientations[bb_avbd])
            off_b_arr = solver.c_off_b.numpy().reshape(-1, 3)
            q_world = positions[bb_avbd] + R_b @ off_b_arr[i]
            sep = p_world - q_world
            ns = np.linalg.norm(sep)
            if ns < 1e-9:
                # Degenerate; skip.
                continue
            n_world = sep / ns
            penetration = max(0.0, -ns)  # AVBD keeps them slightly apart
            # AVBD's per-pair t/b directions are not exposed per-row; we
            # derive a consistent local basis here. The DCR re-basing
            # below makes this choice immaterial for the spatial impulse.
            avbd_t1, avbd_t2 = _pick_friction_dirs(n_world)
            # Now remap to DCR-side for the emitted Contact record.
            ba = _to_dcr(ba_avbd)
            bb = _to_dcr(bb_avbd)

        # ---- Gather tangent λ's for this normal row ----------------------
        t_idx1, t_idx2 = normal_to_tangents.get(i, (-1, -1))
        lam_t1_avbd = float(lambdas[t_idx1]) if t_idx1 >= 0 else 0.0
        lam_t2_avbd = float(lambdas[t_idx2]) if t_idx2 >= 0 else 0.0

        # ---- Reconstruct world-space impulse vector ----------------------
        # AVBD sign convention: FLOOR_CONTACT_6DOF rows have `fmax=0`, so
        # λ ≤ 0; the *physical upward* impulse magnitude is `-λ`. For
        # BOX_BOX_CONTACT_6DOF rows the constraint is two-sided in the
        # primal kernel and λ may be of either sign; we take |λ| as the
        # along-normal magnitude. Tangent rows oppose tangential slip.
        if t == FLOOR_CONTACT_6DOF:
            normal_magnitude = -lam_n
        else:
            normal_magnitude = abs(lam_n)
        j_world = h * (
            normal_magnitude * n_world
            + lam_t1_avbd * avbd_t1
            + lam_t2_avbd * avbd_t2
        )

        # ---- Rebase onto DCR's tangent basis -----------------------------
        # The coupler will call `_pick_friction_dirs(contact.normal)` and
        # `contact.normal = -n_world` (DCR convention A→B). The friction
        # picker is invariant to sign so using ±n_world yields the same
        # tangent pair; we use +n_world here for clarity.
        dcr_t1, dcr_t2 = _pick_friction_dirs(n_world)
        lam_normal_dcr = float(np.dot(j_world, n_world))
        lam_t1_dcr = float(np.dot(j_world, dcr_t1))
        lam_t2_dcr = float(np.dot(j_world, dcr_t2))

        # ---- Contact key for is_new ---------------------------------------
        key = (min(ba, bb), max(ba, bb), int(i))
        is_new = key not in prev_contact_keys
        current_keys.add(key)

        contact = Contact(
            body_a=ba,
            body_b=bb,
            point=p_world.astype(np.float64),
            # DCR convention: normal points from body A INTO body B.
            # AVBD's `n_hat` for FLOOR_CONTACT points up (from box to nothing
            # above, i.e. away from the floor). The receiver is body A,
            # so DCR's "A into B" = downward = -n_world.
            normal=(-n_world).astype(np.float64),
            penetration=float(penetration),
            is_new=is_new,
        )
        contacts.append(contact)
        records.append(AVBDContactRecord(
            contact=contact,
            row_idx_normal=i,
            row_idx_t1=t_idx1,
            row_idx_t2=t_idx2,
            avbd_normal_world=n_world.copy(),
            avbd_t1_world=avbd_t1.copy(),
            avbd_t2_world=avbd_t2.copy(),
            j_world=j_world.copy(),
        ))
        triples.extend([lam_normal_dcr, lam_t1_dcr, lam_t2_dcr])
        # Normal-row penalty k_N, parallel to `contacts` (i is the normal row).
        k_normals.append(float(penalties[i]))

    lam_flat = np.asarray(triples, dtype=np.float64)
    k_normal = np.asarray(k_normals, dtype=np.float64)
    assert len(k_normal) == len(contacts), (
        "k_normal must be parallel to contacts")
    return contacts, lam_flat, k_normal, records, current_keys
