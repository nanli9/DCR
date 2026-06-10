"""GPU-resident warp kernels for ReducedCoupledXPBDCoupler (device path).

Device port of the per-XPBD-iteration monolithic primal Schur solve in
`reduced_coupled_xpbd.py` — the sibling of `dcr.avbd.reduced_coupled_kernels`.
The numpy hooks force a full device→host→device round-trip every iteration
(`.numpy()` / `.assign()`), which on CUDA both drains the pipeline and disables
CUDA-graph capture of the whole substep loop (`solver_6dof.py` bypasses the
graph when any Python hook is set). This module runs begin / iteration / end
fully on-device so the substep loop is capturable and nothing leaves the GPU
mid-step.

Reuse: the Schur core is identical to AVBD's, so the bulk of the kernels are
imported verbatim from `dcr.avbd.reduced_coupled_kernels` (k_hq, k_g, k_body,
k_body_cross, k_hmb, k_schur, k_rhs, k_eps_solve(_tiled), k_backsub,
k_reduce_diag, k_iir_precompute, k_modal_energy, k_passivity, k_sync_total).
Only the XPBD-specific *contact-force adapter* (proposal §6.1) differs and is
defined here:

  k_eval_and_gate   substep_begin: bilinear U_y at each candidate corner, freeze
                    the anchor y = shelf_y_rest + U_y·(LP of q_s+q_d), gap-test.
  k_count_active    per-body count of active corners (feeds the gravity dual).
  k_rowforce_xpbd   per-row contact force f = min(ρ·C + m·g/n_active, 0) with a
                    FIXED ρ = contact_stiffness — no AL dual, no escalation.
  k_body_fdef       per-body momentum-deficit force f_body = −(m/h²)·Δy / n_act.
  k_fq_momentum     modal load F_q = Σ_body f_body · Σ_active U_y  (the IIR drive,
                    recovered from momentum deficit, NOT the penalty sum).
  k_iir_apply_xpbd  short-τ EMA (kills substep-bounce) → static/dynamic split →
                    exact-resonator step on (q_d, q̇_d).
  k_anchor_lp_xpbd  EMA low-pass of (q_s + q_d) for the contact anchor.

# DEVIATION (internal f64 to match the numpy reference): all arithmetic is
# wp.float64; solver x/q are float32 (the same values the numpy hook upcasts),
# so promoting in-kernel reproduces the reference to round-off. Parity test
# gate: rtol 1e-5 vs the numpy path.
"""
from __future__ import annotations

import warp as wp

wp.set_module_options({"enable_backward": False})

# Shared types + the bit-identical Schur kernels, imported verbatim from AVBD.
from ..avbd.reduced_coupled_kernels import (  # noqa: F401  (re-exported)
    vec3d, vec4d, mat33d,
    _to_vec3d, _to_mat33d, _quat_to_R,
    k_hq, k_g, k_body, k_body_cross, k_hmb, k_schur, k_rhs,
    k_eps_solve, make_k_eps_solve_tiled,
    k_backsub, k_reduce_diag,
    k_iir_precompute, k_modal_energy, k_passivity, k_sync_total,
)

_ZERO = wp.constant(wp.float64(0.0))
_ONE = wp.constant(wp.float64(1.0))


# ===========================================================================
# substep_begin: evaluate basis, freeze anchor, gap-gate active corners
# ===========================================================================
@wp.kernel
def k_eval_and_gate(
    x: wp.array(dtype=wp.vec3),         # predictor positions (substep-begin snapshot)
    q: wp.array(dtype=wp.quat),
    counts: wp.array(dtype=int),
    r: int,
    row_body: wp.array(dtype=int),
    row_off: wp.array(dtype=vec3d),
    grid_Uy: wp.array2d(dtype=wp.float64),
    n_grid_x: int,
    n_grid_z: int,
    length: wp.float64,
    width: wp.float64,
    shelf_y_rest: wp.float64,
    q_s_anchor: wp.array(dtype=wp.float64),   # LP(q_s + q_d)
    margin: wp.float64,
    row_U_y: wp.array2d(dtype=wp.float64),    # out
    row_anchor_y: wp.array(dtype=wp.float64),  # out (frozen for the substep)
    row_active: wp.array(dtype=int),           # out
):
    """One thread per candidate corner row. Bilinear-interpolates U_y at the
    corner (x, z) = body_pos + R·off (device port of evaluate_basis_at_point),
    freezes the anchor y, and flags the row active iff gap ≤ margin. dim =
    cap_rows. Mirrors substep_begin_hook step 4."""
    rr = wp.tid()
    if rr >= counts[2]:
        return
    bidx = row_body[rr]
    qq = q[bidx]
    R = _quat_to_R(wp.float64(qq[0]), wp.float64(qq[1]),
                   wp.float64(qq[2]), wp.float64(qq[3]))
    corner = _to_vec3d(x[bidx]) + R * row_off[rr]
    xw = corner[0]
    zw = corner[2]

    fx = (xw + length * wp.float64(0.5)) / length * wp.float64(n_grid_x - 1)
    fz = (zw + width * wp.float64(0.5)) / width * wp.float64(n_grid_z - 1)
    ix = int(wp.clamp(wp.floor(fx), wp.float64(0.0), wp.float64(n_grid_x - 2)))
    iz = int(wp.clamp(wp.floor(fz), wp.float64(0.0), wp.float64(n_grid_z - 2)))
    tx = wp.clamp(fx - wp.float64(ix), wp.float64(0.0), wp.float64(1.0))
    tz = wp.clamp(fz - wp.float64(iz), wp.float64(0.0), wp.float64(1.0))

    i00 = ix * n_grid_z + iz
    i10 = (ix + 1) * n_grid_z + iz
    i01 = ix * n_grid_z + (iz + 1)
    i11 = (ix + 1) * n_grid_z + (iz + 1)
    w00 = (wp.float64(1.0) - tx) * (wp.float64(1.0) - tz)
    w10 = tx * (wp.float64(1.0) - tz)
    w01 = (wp.float64(1.0) - tx) * tz
    w11 = tx * tz

    dy = wp.float64(0.0)
    for c in range(r):
        uyc = (w00 * grid_Uy[i00, c] + w10 * grid_Uy[i10, c]
               + w01 * grid_Uy[i01, c] + w11 * grid_Uy[i11, c])
        row_U_y[rr, c] = uyc
        dy += uyc * q_s_anchor[c]
    anchor_y = shelf_y_rest + dy
    row_anchor_y[rr] = anchor_y
    gap = corner[1] - anchor_y
    if gap > margin:
        row_active[rr] = int(0)
    else:
        row_active[rr] = int(1)


@wp.kernel
def k_count_active(
    counts: wp.array(dtype=int),
    body_row_start: wp.array(dtype=int),
    row_active: wp.array(dtype=int),
    n_active: wp.array(dtype=int),     # out, per body slot
):
    """Active-corner count per tracked body (feeds the gravity phantom dual
    m·g/n_active). dim = max_b."""
    t = wp.tid()
    if t >= counts[0]:
        return
    cnt = int(0)
    for rr in range(body_row_start[t], body_row_start[t + 1]):
        cnt += row_active[rr]
    n_active[t] = cnt


# ===========================================================================
# iteration: per-row XPBD contact force (fixed ρ + gravity phantom dual)
# ===========================================================================
@wp.kernel
def k_rowforce_xpbd(
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    mass: wp.array(dtype=float),
    counts: wp.array(dtype=int),
    row_index: wp.array(dtype=int),    # unused (kept for signature symmetry)
    row_body: wp.array(dtype=int),
    row_body_slot: wp.array(dtype=int),
    row_off: wp.array(dtype=vec3d),
    row_anchor_y: wp.array(dtype=wp.float64),
    row_active: wp.array(dtype=int),
    n_active: wp.array(dtype=int),
    contact_stiffness: wp.float64,
    grav_y: wp.float64,
    rowdata: wp.array2d(dtype=wp.float64),
):
    """Per contact row: f = min(ρ·C + m·g/n_active, 0), k = ρ (fixed). Inactive
    rows write k=f=rho_used=0 so every downstream sum (k_hq, k_g, k_body,
    k_body_cross) drops them exactly — bit-parity with the numpy gap-filter that
    EXCLUDES them. dim = cap_rows. Mirrors iteration_hook's per-row block.

    rowdata columns: 0:k  1:f  2:ja0  3:ja2  4:rsx  5:rsy  6:rsz  7:rho_used"""
    rr = wp.tid()
    if rr >= counts[2]:
        return
    bidx = row_body[rr]
    qq = q[bidx]
    R = _quat_to_R(wp.float64(qq[0]), wp.float64(qq[1]),
                   wp.float64(qq[2]), wp.float64(qq[3]))
    r_self = R * row_off[rr]
    ja0 = -r_self[2]
    ja2 = r_self[0]
    rowdata[rr, 2] = ja0
    rowdata[rr, 3] = ja2
    rowdata[rr, 4] = r_self[0]
    rowdata[rr, 5] = r_self[1]
    rowdata[rr, 6] = r_self[2]

    if row_active[rr] == 0:
        rowdata[rr, 0] = _ZERO
        rowdata[rr, 1] = _ZERO
        rowdata[rr, 7] = _ZERO
        return

    na = n_active[row_body_slot[rr]]
    if na <= 0:
        rowdata[rr, 0] = _ZERO
        rowdata[rr, 1] = _ZERO
        rowdata[rr, 7] = _ZERO
        return

    m = wp.float64(mass[bidx])
    C = wp.float64(x[bidx][1]) + r_self[1] - row_anchor_y[rr]
    lam_eff_grav = m * grav_y / wp.float64(na)      # ≤ 0
    lam_plus = contact_stiffness * C + lam_eff_grav
    f = wp.min(lam_plus, _ZERO)

    rowdata[rr, 0] = contact_stiffness
    rowdata[rr, 1] = f
    rowdata[rr, 7] = contact_stiffness


# ===========================================================================
# end-of-iteration: momentum-deficit modal load (the IIR drive)
# ===========================================================================
@wp.kernel
def k_body_fdef(
    x: wp.array(dtype=wp.vec3),         # current positions (after back-sub)
    x_pred: wp.array(dtype=wp.vec3),
    mass: wp.array(dtype=float),
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    n_active: wp.array(dtype=int),
    inv_dt2: wp.float64,
    f_per_row: wp.array(dtype=wp.float64),   # out, per body slot
):
    """Per-body momentum-deficit contact force, distributed over active corners:
        f_body_y = −m/h²·(x_y − x_pred_y) ; f_per_row = f_body_y / n_active.
    dim = max_b. Mirrors iteration_hook's implicit-force-recovery block."""
    t = wp.tid()
    if t >= counts[0]:
        return
    na = n_active[t]
    if na <= 0:
        f_per_row[t] = _ZERO
        return
    bidx = body_ids[t]
    m = wp.float64(mass[bidx])
    dy = wp.float64(x[bidx][1]) - wp.float64(x_pred[bidx][1])
    f_per_row[t] = (-m * inv_dt2 * dy) / wp.float64(na)


@wp.kernel
def k_fq_momentum(
    r: int,
    counts: wp.array(dtype=int),
    body_row_start: wp.array(dtype=int),
    row_active: wp.array(dtype=int),
    row_U_y: wp.array2d(dtype=wp.float64),
    f_per_row: wp.array(dtype=wp.float64),
    Fq: wp.array(dtype=wp.float64),     # out (overwrite)
):
    """F_q[a] = Σ_body f_per_row · Σ_{active rows} U_y[row, a]. dim = r. Mirrors
    `_last_F_q_contact += f_per_row * U_y_arr.sum(axis=0)` over bodies."""
    a = wp.tid()
    if a >= r:
        return
    acc = wp.float64(0.0)
    n_b = counts[0]
    for t in range(n_b):
        fpr = f_per_row[t]
        s = wp.float64(0.0)
        for rr in range(body_row_start[t], body_row_start[t + 1]):
            if row_active[rr] != 0:
                s += row_U_y[rr, a]
        acc += fpr * s
    Fq[a] = acc


# ===========================================================================
# substep_end: short-τ EMA → static/dynamic split → exact-resonator step
# ===========================================================================
@wp.kernel
def k_iir_apply_xpbd(
    r: int,
    Fq: wp.array(dtype=wp.float64),               # raw F_q_total (momentum)
    F_q_total_smooth: wp.array(dtype=wp.float64),
    F_q_static_lp: wp.array(dtype=wp.float64),
    q_free: wp.array(dtype=wp.float64),
    qdot_free: wp.array(dtype=wp.float64),
    S_h_diag: wp.array(dtype=wp.float64),
    T_h_diag: wp.array(dtype=wp.float64),
    first_substep: wp.array(dtype=int),
    h: wp.float64,
    tau: wp.float64,
    band_owns: int,
    q_d: wp.array(dtype=wp.float64),
    qdot_d: wp.array(dtype=wp.float64),
    F_q_dyn: wp.array(dtype=wp.float64),
):
    """XPBD substep_end: short-τ EMA on F_q_total (kills the substep-bounce
    square-wave), THEN the static/dynamic split + exact-resonator force of q_d.
    The short-τ stage is the XPBD-only addition over AVBD's k_iir_apply. dim =
    r. Mirrors substep_end_hook lines 736–768.

    V2-B: `band_owns != 0` gates F_q_dyn to 0 so the velocity band is the sole
    ring excitation (matches the numpy V2-A gate)."""
    i = wp.tid()
    if i >= r:
        return
    raw = Fq[i]
    # Short-τ EMA (τ_short = 2h); latch on the first substep.
    if first_substep[0] != 0:
        sm = raw
    else:
        tau_short = wp.max(wp.float64(2.0) * h, wp.float64(1e-3))
        a_short = wp.min(wp.float64(1.0), h / tau_short)
        sm = F_q_total_smooth[i] + a_short * (raw - F_q_total_smooth[i])
    F_q_total_smooth[i] = sm
    f_total = sm
    # Static/dynamic split.
    if first_substep[0] != 0:
        alpha = wp.float64(1.0)
    else:
        alpha = wp.float64(1.0) - wp.exp(-h / wp.max(tau, wp.float64(1e-9)))
    f_static = (wp.float64(1.0) - alpha) * F_q_static_lp[i] + alpha * f_total
    F_q_static_lp[i] = f_static
    f_dyn = f_total - f_static
    if band_owns != 0:
        f_dyn = wp.float64(0.0)
    F_q_dyn[i] = f_dyn
    q_d[i] = q_free[i] + S_h_diag[i] * f_dyn
    qdot_d[i] = qdot_free[i] + T_h_diag[i] * f_dyn


@wp.kernel
def k_clear_first(first_substep: wp.array(dtype=int)):
    """Clear the one-time first-substep flag (dim=1). Replaces relying on the
    diagnostic k_passivity to clear it, so the passivity kernels can be gated
    off without breaking the first-substep latch."""
    if wp.tid() == 0:
        first_substep[0] = int(0)


@wp.kernel
def k_anchor_lp_xpbd(
    r: int,
    q_s: wp.array(dtype=wp.float64),
    q_d: wp.array(dtype=wp.float64),
    qd_weight: wp.float64,
    a_lp: wp.float64,
    first: wp.array(dtype=int),
    q_s_anchor_lp: wp.array(dtype=wp.float64),
):
    """EMA low-pass of the contact-anchor modal coordinate q_s + qd_weight·q_d.
    qd_weight = 0 ⇒ anchor on q_s only (AVBD parity, bodies stay still);
    qd_weight = 1 ⇒ bodies ride the dynamic ring. First substep: latch. dim=r."""
    i = wp.tid()
    if i >= r:
        return
    qt = q_s[i] + qd_weight * q_d[i]
    if first[0] != 0:
        q_s_anchor_lp[i] = qt
    else:
        q_s_anchor_lp[i] = q_s_anchor_lp[i] + a_lp * (qt - q_s_anchor_lp[i])
