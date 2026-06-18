"""GPU-resident XPBD device kernels for `ReducedCoupledXPBDCoupler` (Stage 6).

These mirror the CPU XPBD reference (`reduced_coupled_xpbd.py:iteration_hook`)
launch-for-launch, reusing the AVBD coupler's augmented-Q device buffers (the
`row_U_y = [+U_y | −G_a]` convention, the block-diagonal `Mq/Kq/Dq`, the moving
basis kernels). Only the per-iteration primal differs: compliant-constraint
Gauss–Seidel (Macklin 2016) instead of the Schur–Newton. Quaternion / matrix
helpers and the geometry/predictor kernels are shared with
`reduced_coupled_kernels.py` (imported there) so the device path is bit-faithful
to the numpy reference. All kernels are pure `wp.launch` with fixed dims ⇒
CUDA-graph-capturable, zero host readback in the hot loop.

# DEVIATION (two_band_coupling.html): the modal elastic constraints (per
# augmented-Q component, independent ⇒ parallel) and the unilateral FLOOR
# contacts (which all share the support modal q ⇒ serialized in one single-
# thread kernel, fixed row order) reproduce the CPU sweep order exactly, so
# CPU↔GPU parity holds to fp64 roundoff.
"""
from __future__ import annotations

import warp as wp

from .reduced_coupled_kernels import (  # shared helpers (XYZW quats, 1e-12 cutoffs)
    vec3d,
    vec4d,
    mat33d,
    _quat_to_R,
    _quat_mul,
    _quat_inv,
    _quat_from_rotvec,
    _quat_to_rotvec,
    _inv3,
    _to_vec3d,
    _to_mat33d,
)

wp.set_module_options({"enable_backward": False})

_ZERO = wp.constant(wp.float64(0.0))
_ONE = wp.constant(wp.float64(1.0))


# ---------------------------------------------------------------------------
# substep_begin: freeze the rigid predictor pose + per-row Jacobian, reset the
# XPBD multipliers, seed the working modal state at the predictor q̃.
# ---------------------------------------------------------------------------
@wp.kernel
def k_xpbd_begin_body(
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    x_inertial: wp.array(dtype=wp.vec3),
    q_inertial: wp.array(dtype=wp.quat),
    mass: wp.array(dtype=float),
    inertia_local: wp.array(dtype=wp.mat33),
    xb: wp.array(dtype=vec3d),
    qb: wp.array(dtype=vec4d),
    invm: wp.array(dtype=wp.float64),
    Iinv: wp.array(dtype=mat33d),
    active: wp.array(dtype=int),
):
    """Per tracked body: snapshot the solver's free-flight predictor as the XPBD
    start pose, the inverse mass and the (frozen) world inverse inertia, and
    clear the owned-this-substep flag. dim = max_b."""
    t = wp.tid()
    if t >= counts[0]:
        return
    b = body_ids[t]
    active[t] = 0
    qq = q_inertial[b]
    qx = wp.float64(qq[0]); qy = wp.float64(qq[1])
    qz = wp.float64(qq[2]); qw = wp.float64(qq[3])
    R = _quat_to_R(qx, qy, qz, qw)
    xi = x_inertial[b]
    xb[t] = vec3d(wp.float64(xi[0]), wp.float64(xi[1]), wp.float64(xi[2]))
    qb[t] = vec4d(qx, qy, qz, qw)
    m = wp.float64(mass[b])
    invm[t] = _ONE / m
    Il = _to_mat33d(inertia_local[b])
    Iw = R * Il * wp.transpose(R)
    # regularize like the CPU reference (+1e-12 I) before inverting.
    Iw = mat33d(Iw[0, 0] + wp.float64(1e-12), Iw[0, 1], Iw[0, 2],
                Iw[1, 0], Iw[1, 1] + wp.float64(1e-12), Iw[1, 2],
                Iw[2, 0], Iw[2, 1], Iw[2, 2] + wp.float64(1e-12))
    Iinv[t] = _inv3(Iw)


@wp.kernel
def k_xpbd_begin_row(
    counts: wp.array(dtype=int),
    lam_c: wp.array(dtype=wp.float64),
):
    """Per tracked FLOOR row: reset the contact multiplier λ_c. The corner lever
    arm r = R·off and the angular Jacobian j_ang are NOT frozen here — they are
    recomputed from the live qb each sweep in `k_xpbd_contact` (see the DEVIATION
    there; mirrors the CPU reference). dim = cap_rows."""
    rr = wp.tid()
    if rr >= counts[2]:
        return
    lam_c[rr] = _ZERO


@wp.kernel
def k_xpbd_seed_modal(
    q: wp.array(dtype=wp.float64),
    q_hat: wp.array(dtype=wp.float64),
    lam_q: wp.array(dtype=wp.float64),
):
    """XPBD starts at the predictor: q ← q̃ and reset the modal multipliers. dim = R."""
    i = wp.tid()
    q[i] = q_hat[i]
    lam_q[i] = _ZERO


# ---------------------------------------------------------------------------
# one Gauss–Seidel sweep: modal elastic (parallel) then FLOOR contact (serial).
# ---------------------------------------------------------------------------
@wp.kernel
def k_xpbd_elastic(
    R_tot: int,
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    Dq: wp.array2d(dtype=wp.float64),
    inv_h2: wp.float64,
    h: wp.float64,
    q: wp.array(dtype=wp.float64),
    q_prev: wp.array(dtype=wp.float64),
    lam_q: wp.array(dtype=wp.float64),
):
    """Per-mode modal stiffness as a compliant constraint C_i = Q_i with
    compliance α = 1/K_q[i,i] and the Macklin damped update (§3.5) using the
    modal Rayleigh damping D_q[i,i]. Each component touches its own DOF ⇒
    parallel == the CPU sequential sweep. dim = R."""
    i = wp.tid()
    if i >= R_tot:
        return
    ki = Kq[i, i]
    if ki <= _ZERO:
        return
    alpha = _ONE / ki
    at = alpha * inv_h2
    mii = Mq[i, i]
    w = _ZERO
    if mii > _ZERO:
        w = _ONE / mii
    damp = Dq[i, i]
    gamma = _ZERO
    if damp > _ZERO:
        gamma = at * (damp * alpha) * h
    Cdot = q[i] - q_prev[i]
    denom = (_ONE + gamma) * w + at
    dlam = (-q[i] - at * lam_q[i] - gamma * Cdot) / denom
    lam_q[i] = lam_q[i] + dlam
    q[i] = q[i] + w * dlam


@wp.kernel
def k_xpbd_contact(
    counts: wp.array(dtype=int),
    R_tot: int,
    row_tbody: wp.array(dtype=int),
    row_U_y: wp.array2d(dtype=wp.float64),
    floor_y_rest: wp.array(dtype=wp.float64),
    row_off: wp.array(dtype=vec3d),
    invm: wp.array(dtype=wp.float64),
    Iinv: wp.array(dtype=mat33d),
    Mq: wp.array2d(dtype=wp.float64),
    at_c: wp.float64,
    xb: wp.array(dtype=vec3d),
    qb: wp.array(dtype=vec4d),
    q: wp.array(dtype=wp.float64),
    lam_c: wp.array(dtype=wp.float64),
    active: wp.array(dtype=int),
):
    """Unilateral FLOOR contact, one compliant constraint per tracked corner,
    projected SERIALLY (all share the support modal q) in the topology row
    order — identical to the CPU reference (single thread). C = corner_y −
    (floor + Σ row_U_y·q); ∂C/∂Q = −row_U_y (= [−U_y | +G_a]). Updates the cube
    rigid pose (translation + rotvec), the support modal q and the cargo modal a
    through the one shared multiplier λ_c ≥ 0. dim = 1.

    # DEVIATION (XPBD rigid positional constraint, Macklin et al. 2020): the
    # corner lever arm rsw = R(qb)·off and the angular Jacobian j_ang are
    # recomputed from the LIVE projected orientation qb every sweep (NOT frozen
    # at substep begin), so the rotational correction feeds back into the next
    # corner's gap — otherwise serial Gauss–Seidel pumps angular momentum and a
    # resting box spins up. Mirrors the CPU reference exactly ⇒ parity holds."""
    if wp.tid() != 0:
        return
    n = counts[2]
    for rr in range(n):
        t = row_tbody[rr]
        qf = qb[t]
        Rb = _quat_to_R(qf[0], qf[1], qf[2], qf[3])
        rsw = Rb * row_off[rr]
        corner_y = xb[t][1] + rsw[1]
        surf = floor_y_rest[rr]
        for c in range(R_tot):
            surf += row_U_y[rr, c] * q[c]
        C = corner_y - surf
        lam = lam_c[rr]
        if C >= _ZERO and lam == _ZERO:
            continue
        jang = vec3d(-rsw[2], _ZERO, rsw[0])
        # generalized inverse mass w = ∇Cᵀ M⁻¹ ∇C
        w = invm[t] + wp.dot(jang, Iinv[t] * jang)
        for c in range(R_tot):
            g = row_U_y[rr, c]               # |∂C/∂Q_c| = |row_U_y|
            mcc = Mq[c, c]
            if mcc > _ZERO:
                w += g * g / mcc
        dlam = (-C - at_c * lam) / (w + at_c)
        new = lam + dlam
        if new < _ZERO:
            new = _ZERO
        dlam = new - lam
        lam_c[rr] = new
        if new > _ZERO:
            active[t] = 1                  # coupler owns this body's pose
        # apply Δz = M⁻¹ ∇C dlam
        xv = xb[t]
        xb[t] = vec3d(xv[0], xv[1] + invm[t] * dlam, xv[2])
        dtheta = (Iinv[t] * jang) * dlam
        dq = _quat_from_rotvec(dtheta)
        nq = _quat_mul(dq, qb[t])
        nrm = wp.sqrt(nq[0] * nq[0] + nq[1] * nq[1] + nq[2] * nq[2] + nq[3] * nq[3])
        if nrm > wp.float64(1e-12):
            nq = vec4d(nq[0] / nrm, nq[1] / nrm, nq[2] / nrm, nq[3] / nrm)
        qb[t] = nq
        for c in range(R_tot):
            mcc = Mq[c, c]
            if mcc > _ZERO:
                q[c] = q[c] + (-row_U_y[rr, c] / mcc) * dlam


@wp.kernel
def k_xpbd_write_rigid(
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    xb: wp.array(dtype=vec3d),
    qb: wp.array(dtype=vec4d),
    active: wp.array(dtype=int),
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
):
    """Push the XPBD-projected pose to the solver state (rendering + the
    substep_end penetration diagnostic + body-body SAT of other bodies). Only the
    coupler-owned bodies (active FLOOR contact this substep) are written; the rest
    keep the solver's box-box primal pose. dim = max_b."""
    t = wp.tid()
    if t >= counts[0]:
        return
    if active[t] == 0:
        return
    b = body_ids[t]
    xv = xb[t]
    x[b] = wp.vec3(wp.float32(xv[0]), wp.float32(xv[1]), wp.float32(xv[2]))
    qv = qb[t]
    q[b] = wp.quat(wp.float32(qv[0]), wp.float32(qv[1]),
                   wp.float32(qv[2]), wp.float32(qv[3]))


@wp.kernel
def k_xpbd_rigid_vel(
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    xb: wp.array(dtype=vec3d),
    qb: wp.array(dtype=vec4d),
    active: wp.array(dtype=int),
    x_initial: wp.array(dtype=wp.vec3),
    q_initial: wp.array(dtype=wp.quat),
    inv_dt: wp.float64,
    v: wp.array(dtype=wp.vec3),
    omega: wp.array(dtype=wp.vec3),
):
    """XPBD velocity update for the coupler-owned tracked bodies: v = (x−xⁿ)/h,
    ω = log(q ⊗ qⁿ⁻¹)/h (overrides the solver's finalize, which used its own
    primal pose). Only the active (owned) bodies; the rest keep the solver's
    box-box velocity. dim = max_b."""
    t = wp.tid()
    if t >= counts[0]:
        return
    if active[t] == 0:
        return
    b = body_ids[t]
    xv = xb[t]
    xi = x_initial[b]
    v[b] = wp.vec3(
        wp.float32((xv[0] - wp.float64(xi[0])) * inv_dt),
        wp.float32((xv[1] - wp.float64(xi[1])) * inv_dt),
        wp.float32((xv[2] - wp.float64(xi[2])) * inv_dt))
    qi = q_initial[b]
    qinv = _quat_inv(wp.float64(qi[0]), wp.float64(qi[1]),
                     wp.float64(qi[2]), wp.float64(qi[3]))
    dq = _quat_mul(qb[t], qinv)
    rv = _quat_to_rotvec(dq[0], dq[1], dq[2], dq[3])
    omega[b] = wp.vec3(wp.float32(rv[0] * inv_dt),
                       wp.float32(rv[1] * inv_dt),
                       wp.float32(rv[2] * inv_dt))
