"""GPU-resident warp kernels for ReducedCoupledAVBDCoupler.iteration_hook.

Device port of the per-AVBD-iteration monolithic primal Schur solve in
`reduced_coupled_avbd.py:iteration_hook` (the eigen `--reduced-basis eigen`,
`--mode coupled_iir_modal` hot path). The numpy version forces a full
device→host→device round-trip every AVBD iteration; at 4 substeps × 4 iterations
that is ~16 GPU pipeline drains per step and dominates wall-clock on CUDA. This
module runs the whole solve on-device so nothing leaves the GPU mid-step, and is
CUDA-graph-capturable (issues only `wp.launch`).

The solve is split into ~10 small kernels, each PARALLEL over its natural
dimension (r×r Schur/Hessian entries, contact rows, tracked bodies). Only the
r×r Gaussian elimination is single-thread (it is inherently sequential and r is
small). This replaces an earlier single-thread monolith that was memory-latency
bound at ~1 ms/launch; parallelizing hides that latency across many warps.

# DEVIATION (internal f64 to match the numpy reference): all arithmetic is
# wp.float64. The solver state arrays (x, q, c_lambda, ...) are float32 — the
# SAME float32 values the numpy hook reads via `.numpy()` before upcasting — so
# promoting to f64 in-kernel reproduces the numpy result to round-off.
# Writebacks (x, q, c_world_anchor) cast back to float32, matching the numpy
# hook's `.assign(...astype(np.float32))`.

The kernels are DETERMINISTIC (no atomics): per-row contact forces are computed
once (`k_rowforce`) and the modal/Hessian sums loop over rows in the SAME order
as the numpy `U_y_arr.T @ f_arr` reductions, so the device result tracks the
reference to floating round-off (parity test gate: rtol 1e-5).

Math (per body i, summed over its FLOOR_CONTACT rows j) mirrors the numpy
docstring in reduced_coupled_avbd.py:

  S      = K_q + Σ ρ U_y U_yᵀ  −  Σ_i Mᵢᵀ H_x,iⁱⁿᵛ Mᵢ          (r×r)
  rhs_q  = -g_q                +  Σ_i Mᵢᵀ H_x,iⁱⁿᵛ g_x,i        (r,)
  Δq_s   = (S + ε·I)⁻¹ rhs_q
  Δx_i   = -H_x,iⁱⁿᵛ (g_x,i + Mᵢ Δq_s)            (Mᵢ = -ρ J_x,i J_q,iᵀ)

H_x,i is the per-body 6×6 [[A, Bᵀ],[B, D]] with A diagonal (the floor normal is
ŷ for every row), inverted by a 2×2 block formula with one hand-rolled 3×3
inverse — algebraically exact, matching np.linalg.inv to round-off.

Per-row scratch (`rowdata`, shape (cap_rows, 8)) columns:
  0:k  1:f  2:ja0  3:ja2  4:rsx  5:rsy  6:rsz  7:rho_used
"""
from __future__ import annotations

import warp as wp

wp.set_module_options({"enable_backward": False})

vec3d = wp.vec3d
vec4d = wp.vec4d
mat33d = wp.mat33d

_ZERO = wp.constant(wp.float64(0.0))
_ONE = wp.constant(wp.float64(1.0))
_HALF = wp.constant(wp.float64(0.5))


# ---------------------------------------------------------------------------
# Type converters (read float32 solver arrays as float64)
# ---------------------------------------------------------------------------
@wp.func
def _to_vec3d(v: wp.vec3) -> vec3d:
    return vec3d(wp.float64(v[0]), wp.float64(v[1]), wp.float64(v[2]))


@wp.func
def _to_mat33d(m: wp.mat33) -> mat33d:
    return mat33d(
        wp.float64(m[0, 0]), wp.float64(m[0, 1]), wp.float64(m[0, 2]),
        wp.float64(m[1, 0]), wp.float64(m[1, 1]), wp.float64(m[1, 2]),
        wp.float64(m[2, 0]), wp.float64(m[2, 1]), wp.float64(m[2, 2]))


# ---------------------------------------------------------------------------
# Quaternion helpers (XYZW) — replicate reduced_coupled_avbd.py exactly so the
# device path is bit-faithful to the numpy reference (its small-angle cutoffs
# are 1e-12, unlike the solver kernel's 1e-9).
# ---------------------------------------------------------------------------
@wp.func
def _quat_to_R(qx: wp.float64, qy: wp.float64, qz: wp.float64,
               qw: wp.float64) -> mat33d:
    xx = qx * qx
    yy = qy * qy
    zz = qz * qz
    xy = qx * qy
    xz = qx * qz
    yz = qy * qz
    wx = qw * qx
    wy = qw * qy
    wz = qw * qz
    two = wp.float64(2.0)
    return mat33d(
        _ONE - two * (yy + zz), two * (xy - wz), two * (xz + wy),
        two * (xy + wz), _ONE - two * (xx + zz), two * (yz - wx),
        two * (xz - wy), two * (yz + wx), _ONE - two * (xx + yy))


@wp.func
def _quat_mul(a: vec4d, b: vec4d) -> vec4d:
    ax = a[0]; ay = a[1]; az = a[2]; aw = a[3]
    bx = b[0]; by = b[1]; bz = b[2]; bw = b[3]
    return vec4d(
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz)


@wp.func
def _quat_inv(qx: wp.float64, qy: wp.float64, qz: wp.float64,
              qw: wp.float64) -> vec4d:
    n2 = qx * qx + qy * qy + qz * qz + qw * qw
    if n2 < wp.float64(1e-30):
        return vec4d(_ZERO, _ZERO, _ZERO, _ONE)
    return vec4d(-qx / n2, -qy / n2, -qz / n2, qw / n2)


@wp.func
def _quat_from_rotvec(rv: vec3d) -> vec4d:
    theta = wp.sqrt(rv[0] * rv[0] + rv[1] * rv[1] + rv[2] * rv[2])
    if theta < wp.float64(1e-12):
        return vec4d(_ZERO, _ZERO, _ZERO, _ONE)
    half = _HALF * theta
    s = wp.sin(half) / theta
    return vec4d(rv[0] * s, rv[1] * s, rv[2] * s, wp.cos(half))


@wp.func
def _quat_to_rotvec(qx: wp.float64, qy: wp.float64, qz: wp.float64,
                    qw: wp.float64) -> vec3d:
    s_norm = wp.sqrt(qx * qx + qy * qy + qz * qz)
    if s_norm < wp.float64(1e-12):
        return vec3d(_ZERO, _ZERO, _ZERO)
    w = wp.clamp(qw, -_ONE, _ONE)
    theta = wp.float64(2.0) * wp.atan2(s_norm, w)
    f = theta / s_norm
    return vec3d(qx * f, qy * f, qz * f)


@wp.func
def _inv3(m: mat33d) -> mat33d:
    """3×3 inverse via cofactors (caller guarantees non-singular)."""
    a = m[0, 0]; b = m[0, 1]; c = m[0, 2]
    d = m[1, 0]; e = m[1, 1]; f = m[1, 2]
    g = m[2, 0]; h = m[2, 1]; i = m[2, 2]
    A = e * i - f * h
    B = -(d * i - f * g)
    C = d * h - e * g
    D = -(b * i - c * h)
    E = a * i - c * g
    F = -(a * h - b * g)
    G = b * f - c * e
    H = -(a * f - c * d)
    I = a * e - b * d
    det = a * A + b * B + c * C
    inv_det = _ONE / det
    return mat33d(A * inv_det, D * inv_det, G * inv_det,
                  B * inv_det, E * inv_det, H * inv_det,
                  C * inv_det, F * inv_det, I * inv_det)


# ===========================================================================
# Stage kernels (launch order encodes the data dependencies on the stream)
# ===========================================================================
@wp.kernel
def k_rowforce(
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    c_world_anchor: wp.array(dtype=wp.vec3),
    c_lambda: wp.array(dtype=float),
    c_penalty: wp.array(dtype=float),
    c_fmin: wp.array(dtype=float),
    c_fmax: wp.array(dtype=float),
    c_alpha_C0: wp.array(dtype=float),
    c_stiffness: wp.array(dtype=float),
    counts: wp.array(dtype=int),
    row_index: wp.array(dtype=int),
    row_body: wp.array(dtype=int),
    row_off: wp.array(dtype=vec3d),
    rho_clip: wp.float64,
    rowdata: wp.array2d(dtype=wp.float64),
):
    """Per contact row: compute the AL contact force f, the LHS weight k, the
    angular Jacobian (ja0, ja2), r_self, and rho_used. Mirrors the per-row
    block of iteration_hook's body loop. dim = cap_rows."""
    rr = wp.tid()
    if rr >= counts[2]:
        return
    ri = row_index[rr]
    bidx = row_body[rr]
    qq = q[bidx]
    R = _quat_to_R(wp.float64(qq[0]), wp.float64(qq[1]),
                   wp.float64(qq[2]), wp.float64(qq[3]))
    r_self = R * row_off[rr]
    ja0 = -r_self[2]
    ja2 = r_self[0]

    anc = c_world_anchor[ri]
    C = wp.float64(x[bidx][1]) + r_self[1] - wp.float64(anc[1])
    s_stiff = c_stiffness[ri]
    lam_eff = wp.float64(0.0)
    if wp.isinf(s_stiff) != 0:
        C = C - wp.float64(c_alpha_C0[ri])
        lam_eff = wp.float64(c_lambda[ri])
    rho = wp.float64(c_penalty[ri])
    rho_used = wp.min(rho, rho_clip)

    f_lo = wp.float64(c_fmin[ri])
    f_hi = wp.float64(c_fmax[ri])
    lam_plus = rho_used * C + lam_eff
    f = wp.clamp(lam_plus, f_lo, f_hi)

    abs_C = wp.abs(C)
    safe_abs_C = wp.max(abs_C, wp.float64(1e-12))
    k = rho_used
    if (lam_plus < f_lo) and (abs_C > wp.float64(1e-12)):
        k = wp.abs(f_lo - lam_plus) / safe_abs_C
    if (lam_plus > f_hi) and (abs_C > wp.float64(1e-12)):
        k = wp.abs(f_hi - lam_plus) / safe_abs_C

    rowdata[rr, 0] = k
    rowdata[rr, 1] = f
    rowdata[rr, 2] = ja0
    rowdata[rr, 3] = ja2
    rowdata[rr, 4] = r_self[0]
    rowdata[rr, 5] = r_self[1]
    rowdata[rr, 6] = r_self[2]
    rowdata[rr, 7] = rho_used


@wp.kernel
def k_hq(
    r: int,
    counts: wp.array(dtype=int),
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    Dq: wp.array2d(dtype=wp.float64),
    inv_dt2: wp.float64,
    inv_dt: wp.float64,
    row_U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    Hq: wp.array2d(dtype=wp.float64),
):
    """Dynamic modal Hessian (two_band_coupling.html):
        H_q[a,b] = 1/h²·M_q[a,b] + 1/h·D_q[a,b] + K_q[a,b]
                   + Σ_row k·U_y[a]·U_y[b].
    The 1/h²·M_q and 1/h·D_q terms are the only change from the static
    coupler. dim = (r, r)."""
    a, b = wp.tid()
    acc = inv_dt2 * Mq[a, b] + inv_dt * Dq[a, b] + Kq[a, b]
    nrows = counts[2]
    for rr in range(nrows):
        acc += rowdata[rr, 0] * row_U_y[rr, a] * row_U_y[rr, b]
    Hq[a, b] = acc


@wp.kernel
def k_g(
    r: int,
    counts: wp.array(dtype=int),
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    Dq: wp.array2d(dtype=wp.float64),
    inv_dt2: wp.float64,
    inv_dt: wp.float64,
    q: wp.array(dtype=wp.float64),
    q_hat: wp.array(dtype=wp.float64),
    q_prev: wp.array(dtype=wp.float64),
    row_U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    gq: wp.array(dtype=wp.float64),
    Fq: wp.array(dtype=wp.float64),
):
    """Dynamic modal gradient (two_band_coupling.html):
        g_q[a] = Σ_b [1/h²·M_q[a,b]·(q[b]−q̃[b])
                      + 1/h·D_q[a,b]·(q[b]−qⁿ[b])
                      + K_q[a,b]·q[b]]  − Σ_row f·U_y[a]
    with q̃ = q_hat (predictor) and qⁿ = q_prev (substep start). The damping
    term is the IMPLICIT 1/h·D_q(q−qⁿ) — consistent with the 1/h·D_q Hessian
    and the Ė = −q̇ᵀD_qq̇ ≤ 0 passivity proof. F_q[a] = Σ_row f·U_y[a] is the
    modal contact-load projection (diagnostic). dim = r."""
    a = wp.tid()
    inertial = wp.float64(0.0)
    for b in range(r):
        inertial += (inv_dt2 * Mq[a, b] * (q[b] - q_hat[b])
                     + inv_dt * Dq[a, b] * (q[b] - q_prev[b])
                     + Kq[a, b] * q[b])
    ff = wp.float64(0.0)
    nrows = counts[2]
    for rr in range(nrows):
        ff += rowdata[rr, 1] * row_U_y[rr, a]
    gq[a] = inertial - ff
    Fq[a] = ff


@wp.kernel
def k_predict(
    r: int,
    h: wp.float64,
    q: wp.array(dtype=wp.float64),
    qdot: wp.array(dtype=wp.float64),
    q_prev: wp.array(dtype=wp.float64),
    q_hat: wp.array(dtype=wp.float64),
):
    """Substep predictor (two_band_coupling.html — "Inertial predictors"):
    snapshot qⁿ = q and form q̃ = qⁿ + h·q̇ⁿ (+ h²M_q⁻¹f_q^grav = 0 for the
    fixed support). The predictor carries the ring velocity q̇ⁿ. dim = r."""
    a = wp.tid()
    q_prev[a] = q[a]
    q_hat[a] = q[a] + h * qdot[a]


@wp.kernel
def k_qdot(
    r: int,
    inv_dt: wp.float64,
    q: wp.array(dtype=wp.float64),
    q_prev: wp.array(dtype=wp.float64),
    qdot: wp.array(dtype=wp.float64),
):
    """Velocity update (two_band_coupling.html — "After the step"):
    q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h. dim = r."""
    a = wp.tid()
    qdot[a] = (q[a] - q_prev[a]) * inv_dt


@wp.func
def _hxi_mul(TL: mat33d, TR: mat33d, BL: mat33d, BR: mat33d,
             v0: vec3d, v1: vec3d):
    """H_x⁻¹ · [v0; v1] split into (top, bottom) 3-vecs."""
    return TL * v0 + TR * v1, BL * v0 + BR * v1


@wp.kernel
def k_body(
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    mass: wp.array(dtype=float),
    inertia_local: wp.array(dtype=wp.mat33),
    x_inertial: wp.array(dtype=wp.vec3),
    q_inertial: wp.array(dtype=wp.quat),
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    body_row_start: wp.array(dtype=int),
    rowdata: wp.array2d(dtype=wp.float64),
    inv_dt2: wp.float64,
    b_TL: wp.array(dtype=mat33d),
    b_TR: wp.array(dtype=mat33d),
    b_BL: wp.array(dtype=mat33d),
    b_BR: wp.array(dtype=mat33d),
    b_gx0: wp.array(dtype=vec3d),
    b_gx1: wp.array(dtype=vec3d),
    b_hg0: wp.array(dtype=vec3d),
    b_hg1: wp.array(dtype=vec3d),
    rho_score: wp.array(dtype=wp.float64),
):
    """Per tracked body: assemble H_x = [[A,Bᵀ],[B,D]] + g_x, then block-invert
    H_x. dim = max_b (threads ≥ n_b early-out). The r-way cross-coupling block M
    is built separately in k_body_cross (parallel over modes) — splitting it out
    of this thread's serial row×r loop was the iteration-2 GPU optimisation.
    Also precomputes b_hg = H_x⁻¹·g_x (used by k_rhs) here once per body instead
    of redundantly per-mode inside k_rhs."""
    t = wp.tid()
    if t >= counts[0]:
        return
    bidx = body_ids[t]
    m = wp.float64(mass[bidx])

    if not (m > wp.float64(0.0)):
        b_TL[t] = mat33d()
        b_TR[t] = mat33d()
        b_BL[t] = mat33d()
        b_BR[t] = mat33d()
        b_gx0[t] = vec3d(_ZERO, _ZERO, _ZERO)
        b_gx1[t] = vec3d(_ZERO, _ZERO, _ZERO)
        b_hg0[t] = vec3d(_ZERO, _ZERO, _ZERO)
        b_hg1[t] = vec3d(_ZERO, _ZERO, _ZERO)
        rho_score[t] = wp.float64(0.0)
        return

    qq = q[bidx]
    qx = wp.float64(qq[0]); qy = wp.float64(qq[1])
    qz = wp.float64(qq[2]); qw = wp.float64(qq[3])
    R = _quat_to_R(qx, qy, qz, qw)
    I_local = _to_mat33d(inertia_local[bidx])
    I_world = R * I_local * wp.transpose(R)

    x_curr = _to_vec3d(x[bidx])
    x_iner = _to_vec3d(x_inertial[bidx])

    a_diag = m * inv_dt2
    a11 = m * inv_dt2
    D = I_world * inv_dt2
    b_col1 = vec3d(_ZERO, _ZERO, _ZERO)

    r_lin = vec3d(m * inv_dt2 * (x_curr[0] - x_iner[0]),
                  m * inv_dt2 * (x_curr[1] - x_iner[1]),
                  m * inv_dt2 * (x_curr[2] - x_iner[2]))

    qiq = q_inertial[bidx]
    qinv = _quat_inv(wp.float64(qiq[0]), wp.float64(qiq[1]),
                     wp.float64(qiq[2]), wp.float64(qiq[3]))
    dqi = _quat_mul(vec4d(qx, qy, qz, qw), qinv)
    dtheta = _quat_to_rotvec(dqi[0], dqi[1], dqi[2], dqi[3])
    r_ang = I_world * vec3d(dtheta[0] * inv_dt2, dtheta[1] * inv_dt2,
                            dtheta[2] * inv_dt2)

    rstart = body_row_start[t]
    rend = body_row_start[t + 1]
    rho_sc = wp.float64(0.0)
    for rr in range(rstart, rend):
        k = rowdata[rr, 0]
        f = rowdata[rr, 1]
        ja0 = rowdata[rr, 2]
        ja2 = rowdata[rr, 3]
        rsx = rowdata[rr, 4]
        rsy = rowdata[rr, 5]
        rsz = rowdata[rr, 6]
        rho_used = rowdata[rr, 7]

        a11 += k
        b_col1 = vec3d(b_col1[0] + k * ja0, b_col1[1], b_col1[2] + k * ja2)
        D = D + mat33d(k * ja0 * ja0, _ZERO, k * ja0 * ja2,
                       _ZERO, _ZERO, _ZERO,
                       k * ja2 * ja0, _ZERO, k * ja2 * ja2)

        f_mag = wp.abs(f)
        if f_mag > wp.float64(0.0):
            nr = rsy
            g0 = wp.sqrt(nr * nr + (_HALF * rsx) * (_HALF * rsx))
            g1 = wp.sqrt((_HALF * rsx) * (_HALF * rsx)
                         + (_HALF * rsz) * (_HALF * rsz))
            g2 = wp.sqrt((_HALF * rsz) * (_HALF * rsz) + nr * nr)
            D = D + mat33d(f_mag * g0, _ZERO, _ZERO,
                           _ZERO, f_mag * g1, _ZERO,
                           _ZERO, _ZERO, f_mag * g2)

        r_lin = vec3d(r_lin[0], r_lin[1] + f, r_lin[2])
        r_ang = vec3d(r_ang[0] + ja0 * f, r_ang[1], r_ang[2] + ja2 * f)

        j_ang_sq = ja0 * ja0 + ja2 * ja2
        score = (rho_used * rho_used) * (_ONE + j_ang_sq) / wp.max(
            m, wp.float64(1e-12))
        rho_sc = wp.max(rho_sc, score)
    rho_score[t] = rho_sc

    reg = wp.float64(1e-12)
    A = mat33d(a_diag + reg, _ZERO, _ZERO,
               _ZERO, a11 + reg, _ZERO,
               _ZERO, _ZERO, a_diag + reg)
    Dreg = D + mat33d(reg, _ZERO, _ZERO, _ZERO, reg, _ZERO, _ZERO, _ZERO, reg)
    Ainv = mat33d(_ONE / A[0, 0], _ZERO, _ZERO,
                  _ZERO, _ONE / A[1, 1], _ZERO,
                  _ZERO, _ZERO, _ONE / A[2, 2])
    B = mat33d(_ZERO, b_col1[0], _ZERO,
               _ZERO, b_col1[1], _ZERO,
               _ZERO, b_col1[2], _ZERO)
    Bt = wp.transpose(B)
    P = Ainv * Bt
    Sc = Dreg - B * P
    Scinv = _inv3(Sc)
    Pt = wp.transpose(P)
    b_TL[t] = Ainv + P * Scinv * Pt
    b_TR[t] = mat33d() - P * Scinv
    b_BL[t] = mat33d() - Scinv * Pt
    b_BR[t] = Scinv
    b_gx0[t] = r_lin
    b_gx1[t] = r_ang
    # H_x⁻¹·g_x once per body (k_rhs consumes this; same _hxi_mul, so the rhs
    # dot products downstream are bit-identical to the old per-mode recompute).
    hg0, hg1 = _hxi_mul(b_TL[t], b_TR[t], b_BL[t], b_BR[t], r_lin, r_ang)
    b_hg0[t] = hg0
    b_hg1[t] = hg1


@wp.kernel
def k_body_cross(
    mass: wp.array(dtype=float),
    r: int,
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    body_row_start: wp.array(dtype=int),
    row_U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    M: wp.array3d(dtype=wp.float64),
):
    """Cross-coupling block M (6×r) per tracked body — one thread per (body,
    mode). dim = (max_b, r). Splits the per-mode inner loop out of k_body so the
    r-way work runs on r threads/body instead of serially in one thread. Only
    rows 1,3,5 are nonzero: M[·,1,c] = −Σ k·U_y ; M[·,3,c] = −Σ ja0·k·U_y ;
    M[·,5,c] = −Σ ja2·k·U_y, summed over the body's rows in the SAME order as
    the original k_body loop, so the result is bit-identical."""
    t, c1 = wp.tid()
    if t >= counts[0] or c1 >= r:
        return
    M[t, 0, c1] = wp.float64(0.0)
    M[t, 2, c1] = wp.float64(0.0)
    M[t, 4, c1] = wp.float64(0.0)
    bidx = body_ids[t]
    m = wp.float64(mass[bidx])
    if not (m > wp.float64(0.0)):
        M[t, 1, c1] = wp.float64(0.0)
        M[t, 3, c1] = wp.float64(0.0)
        M[t, 5, c1] = wp.float64(0.0)
        return
    rstart = body_row_start[t]
    rend = body_row_start[t + 1]
    m1 = wp.float64(0.0)
    m3 = wp.float64(0.0)
    m5 = wp.float64(0.0)
    for rr in range(rstart, rend):
        kuy = rowdata[rr, 0] * row_U_y[rr, c1]
        m1 = m1 - kuy
        m3 = m3 - rowdata[rr, 2] * kuy
        m5 = m5 - rowdata[rr, 3] * kuy
    M[t, 1, c1] = m1
    M[t, 3, c1] = m3
    M[t, 5, c1] = m5


@wp.kernel
def k_hmb(
    r: int,
    counts: wp.array(dtype=int),
    b_TL: wp.array(dtype=mat33d),
    b_TR: wp.array(dtype=mat33d),
    b_BL: wp.array(dtype=mat33d),
    b_BR: wp.array(dtype=mat33d),
    M: wp.array3d(dtype=wp.float64),
    Hmb_top: wp.array2d(dtype=vec3d),
    Hmb_bot: wp.array2d(dtype=vec3d),
):
    """Precompute H_x⁻¹·M[:,b] per (body, mode-b). dim = (max_b, r). In k_schur
    this product was recomputed r times per (t,b) (once for every a); hoisting it
    here computes it once. Same _hxi_mul ⇒ k_schur's dot products stay
    bit-identical. m≤0 bodies have zero blocks + zero M ⇒ zero result."""
    t, b = wp.tid()
    if t >= counts[0] or b >= r:
        return
    mb_top = vec3d(M[t, 0, b], M[t, 1, b], M[t, 2, b])
    mb_bot = vec3d(M[t, 3, b], M[t, 4, b], M[t, 5, b])
    hm_top, hm_bot = _hxi_mul(b_TL[t], b_TR[t], b_BL[t], b_BR[t],
                              mb_top, mb_bot)
    Hmb_top[t, b] = hm_top
    Hmb_bot[t, b] = hm_bot


@wp.kernel
def k_schur(
    r: int,
    counts: wp.array(dtype=int),
    Hq: wp.array2d(dtype=wp.float64),
    M: wp.array3d(dtype=wp.float64),
    Hmb_top: wp.array2d(dtype=vec3d),
    Hmb_bot: wp.array2d(dtype=vec3d),
    S: wp.array2d(dtype=wp.float64),
):
    """S[a,b] = H_q[a,b] − Σ_t (Mᵀ H_x⁻¹ M)[a,b]. dim = (r, r). H_x⁻¹·M[:,b] is
    read from k_hmb's precompute, so the per-thread work is just the two dots."""
    a, b = wp.tid()
    acc = Hq[a, b]
    n_b = counts[0]
    for t in range(n_b):
        ma_top = vec3d(M[t, 0, a], M[t, 1, a], M[t, 2, a])
        ma_bot = vec3d(M[t, 3, a], M[t, 4, a], M[t, 5, a])
        acc -= wp.dot(ma_top, Hmb_top[t, b]) + wp.dot(ma_bot, Hmb_bot[t, b])
    S[a, b] = acc


@wp.kernel
def k_rhs(
    r: int,
    counts: wp.array(dtype=int),
    gq: wp.array(dtype=wp.float64),
    b_hg0: wp.array(dtype=vec3d),
    b_hg1: wp.array(dtype=vec3d),
    M: wp.array3d(dtype=wp.float64),
    rhs: wp.array(dtype=wp.float64),
):
    """rhs[a] = −g_q[a] + Σ_t (Mᵀ H_x⁻¹ g_x)[a]. dim = r. H_x⁻¹·g_x is read from
    k_body's b_hg precompute (was recomputed per-mode here before)."""
    a = wp.tid()
    acc = -gq[a]
    n_b = counts[0]
    for t in range(n_b):
        ma_top = vec3d(M[t, 0, a], M[t, 1, a], M[t, 2, a])
        ma_bot = vec3d(M[t, 3, a], M[t, 4, a], M[t, 5, a])
        acc += wp.dot(ma_top, b_hg0[t]) + wp.dot(ma_bot, b_hg1[t])
    rhs[a] = acc


@wp.kernel
def k_eps_solve(
    r: int,
    counts: wp.array(dtype=int),
    rho_score: wp.array(dtype=wp.float64),
    eps_baseline_trace: wp.float64,
    eps_cross_factor: wp.float64,
    S: wp.array2d(dtype=wp.float64),
    rhs: wp.array(dtype=wp.float64),
    dq: wp.array(dtype=wp.float64),
    q: wp.array(dtype=wp.float64),
    diag: wp.array(dtype=wp.float64),
):
    """ε-regularize S, solve S·dq = rhs (Gaussian elimination, partial pivot),
    apply q += dq. Single thread (GE is sequential; r is small). dim = 1."""
    tid = wp.tid()
    if tid != 0:
        return
    diag[3] = wp.float64(0.0)

    max_rho2 = wp.float64(0.0)
    n_b = counts[0]
    for t in range(n_b):
        max_rho2 = wp.max(max_rho2, rho_score[t])
    eps = wp.max(eps_baseline_trace, eps_cross_factor * max_rho2)
    for a in range(r):
        S[a, a] = S[a, a] + eps
        dq[a] = rhs[a]

    singular = int(0)
    for col in range(r):
        piv = col
        big = wp.abs(S[col, col])
        for rr2 in range(col + 1, r):
            v = wp.abs(S[rr2, col])
            if v > big:
                big = v
                piv = rr2
        if big < wp.float64(1e-300):
            singular = int(1)
        if piv != col:
            for cc in range(r):
                tmp = S[col, cc]
                S[col, cc] = S[piv, cc]
                S[piv, cc] = tmp
            tmpb = dq[col]
            dq[col] = dq[piv]
            dq[piv] = tmpb
        pivot = S[col, col]
        for rr2 in range(col + 1, r):
            factor = S[rr2, col] / pivot
            if factor != wp.float64(0.0):
                for cc in range(col, r):
                    S[rr2, cc] = S[rr2, cc] - factor * S[col, cc]
                dq[rr2] = dq[rr2] - factor * dq[col]
    for ii in range(r):
        a = r - 1 - ii
        acc = dq[a]
        for cc in range(a + 1, r):
            acc = acc - S[a, cc] * dq[cc]
        dq[a] = acc / S[a, a]

    if singular != 0:
        diag[3] = _ONE
        for a in range(r):
            dq[a] = wp.float64(0.0)
        return

    dqn = wp.float64(0.0)
    for a in range(r):
        q[a] = q[a] + dq[a]
        dqn += dq[a] * dq[a]
    diag[2] = wp.sqrt(dqn)


# ---------------------------------------------------------------------------
# Cooperative-Cholesky r×r solve (block-parallel replacement for k_eps_solve)
# ---------------------------------------------------------------------------
# Profiling (scripts/_diag_warp_kernel_profile.py) showed the single-thread GE
# in k_eps_solve was the dominant GPU cost (~3.6 ms/step, 46% of all kernel
# time): a `dim=1` thread doing O(r³) elimination is memory-latency bound, no
# latency hiding. This replaces it with warp's block-cooperative tile Cholesky
# (`wp.tile_cholesky` / `wp.tile_cholesky_solve`), where one thread-block solves
# the single r×r system with all lanes participating — same arithmetic in f64,
# same ε-regularization, same q_s update + ‖dq‖ diagnostic.
#
# # DEVIATION (GE-with-partial-pivot → Cholesky): the numpy reference solves the
# # ε-regularized Schur system with np.linalg.solve (LU). The single-thread
# # device kernel mirrored that with Gaussian elimination + partial pivoting,
# # which also handles an indefinite matrix. Cholesky requires S_reg to be SPD.
# # Verified empirically (scripts probe, 4000 solves over a full impact+ring-down
# # run): S_reg is SPD throughout — min eigenvalue ~2e8, condition ~4e3, zero
# # indefinite cases — and the ε term (ε ≥ eps_baseline·tr(K_q)/r > 0) keeps it
# # PD by construction. So the partial-pivot/singular branch is unreachable here.
# # For any non-CUDA path, atypical r, or a future scene that violates SPD, the
# # caller falls back to the single-thread k_eps_solve above (full pivot +
# # singular guard). Cholesky is numerically identical to LU on this well-
# # conditioned SPD system (parity test matches np.linalg.solve to ~1e-17).
#
# Tile shapes must be compile-time constants while r (mode count) is a runtime
# scene parameter, so the kernel is generated per-r and cached.
_TILED_EPS_SOLVE_CACHE: dict[int, object] = {}


@wp.func
def _sq_f64(a: wp.float64) -> wp.float64:
    return a * a


def make_k_eps_solve_tiled(r: int):
    """Return a block-cooperative Cholesky solver kernel specialised to `r`.

    Replaces the single-thread k_eps_solve (paper has no equivalent; this is the
    follow-up reduced-coupled Schur solve). Launch with `wp.launch_tiled(...,
    dim=[1], block_dim=B)`: one block, B lanes cooperate on the r×r solve.

    Solves  (S + ε·I) · dq = rhs  with  ε = max(eps_baseline_trace,
    eps_cross_factor·max_t rho_score[t]) ; then q_s += dq ; diag[2] = ‖dq‖.
    """
    cached = _TILED_EPS_SOLVE_CACHE.get(r)
    if cached is not None:
        return cached

    R = wp.constant(int(r))

    @wp.kernel
    def k_eps_solve_tiled(
        counts: wp.array(dtype=int),
        rho_score: wp.array(dtype=wp.float64),
        eps_baseline_trace: wp.float64,
        eps_cross_factor: wp.float64,
        S: wp.array2d(dtype=wp.float64),
        rhs: wp.array(dtype=wp.float64),
        dq: wp.array(dtype=wp.float64),
        q: wp.array(dtype=wp.float64),
        diag: wp.array(dtype=wp.float64),
    ):
        # ε from the per-body ρ scores (same reduction as k_eps_solve; n_b ≤ a
        # handful, so each lane recomputes it redundantly — trivially cheap).
        n_b = counts[0]
        max_rho2 = wp.float64(0.0)
        for t in range(n_b):
            max_rho2 = wp.max(max_rho2, rho_score[t])
        eps = wp.max(eps_baseline_trace, eps_cross_factor * max_rho2)

        # S_reg = S + ε·I, then cooperative Cholesky solve.
        St = wp.tile_load(S, shape=(R, R))
        epsv = wp.tile_full(shape=R, value=eps, dtype=wp.float64)
        St = wp.tile_diag_add(St, epsv)
        L = wp.tile_cholesky(St)
        bt = wp.tile_load(rhs, shape=R)
        xt = wp.tile_cholesky_solve(L, bt)

        # dq = Δq ; q += dq ; ‖dq‖ → diag[2].
        wp.tile_store(dq, xt)
        qt = wp.tile_load(q, shape=R)
        qt = qt + xt
        wp.tile_store(q, qt)
        sq = wp.tile_map(_sq_f64, xt)
        nrm = wp.tile_sum(sq)
        dqn2 = wp.tile_extract(nrm, 0)  # uniform across the block
        diag[2] = wp.sqrt(dqn2)
        # diag[3]: singular/non-finite flag. SPD ⇒ always finite here; the check
        # only writes a scalar (no tile op), so the branch never diverges the
        # cooperative ops above.
        if dqn2 == dqn2:
            diag[3] = _ZERO
        else:
            diag[3] = _ONE

    _TILED_EPS_SOLVE_CACHE[r] = k_eps_solve_tiled
    return k_eps_solve_tiled


@wp.kernel
def k_backsub(
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    mass: wp.array(dtype=float),
    r: int,
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    b_TL: wp.array(dtype=mat33d),
    b_TR: wp.array(dtype=mat33d),
    b_BL: wp.array(dtype=mat33d),
    b_BR: wp.array(dtype=mat33d),
    b_gx0: wp.array(dtype=vec3d),
    b_gx1: wp.array(dtype=vec3d),
    M: wp.array3d(dtype=wp.float64),
    dq: wp.array(dtype=wp.float64),
    diag: wp.array(dtype=wp.float64),
    b_dxn: wp.array(dtype=wp.float64),
    b_dthn: wp.array(dtype=wp.float64),
):
    """Δx_i = −H_x⁻¹(g_x + M·dq); apply to x, q. dim = max_b. (M·dq is computed
    inline here — splitting it into a separate parallel kernel was profiled as a
    net loss: k_backsub's cost is the per-body quaternion apply, not this loop.)"""
    t = wp.tid()
    if t >= counts[0]:
        return
    b_dxn[t] = wp.float64(0.0)
    b_dthn[t] = wp.float64(0.0)
    if diag[3] != wp.float64(0.0):
        return
    bidx = body_ids[t]
    if not (wp.float64(mass[bidx]) > wp.float64(0.0)):
        return

    md_top = vec3d(_ZERO, _ZERO, _ZERO)
    md_bot = vec3d(_ZERO, _ZERO, _ZERO)
    for c1 in range(r):
        dqc = dq[c1]
        md_top = vec3d(md_top[0] + M[t, 0, c1] * dqc,
                       md_top[1] + M[t, 1, c1] * dqc,
                       md_top[2] + M[t, 2, c1] * dqc)
        md_bot = vec3d(md_bot[0] + M[t, 3, c1] * dqc,
                       md_bot[1] + M[t, 4, c1] * dqc,
                       md_bot[2] + M[t, 5, c1] * dqc)
    gx0 = b_gx0[t]
    gx1 = b_gx1[t]
    rhs6_top = vec3d(-(gx0[0] + md_top[0]), -(gx0[1] + md_top[1]),
                     -(gx0[2] + md_top[2]))
    rhs6_bot = vec3d(-(gx1[0] + md_bot[0]), -(gx1[1] + md_bot[1]),
                     -(gx1[2] + md_bot[2]))
    d_top, d_bot = _hxi_mul(b_TL[t], b_TR[t], b_BL[t], b_BR[t],
                            rhs6_top, rhs6_bot)

    xc = x[bidx]
    x[bidx] = wp.vec3(xc[0] + wp.float32(d_top[0]),
                      xc[1] + wp.float32(d_top[1]),
                      xc[2] + wp.float32(d_top[2]))
    qq = q[bidx]
    qcur = vec4d(wp.float64(qq[0]), wp.float64(qq[1]),
                 wp.float64(qq[2]), wp.float64(qq[3]))
    dqq = _quat_from_rotvec(d_bot)
    nq = _quat_mul(dqq, qcur)
    nrm = wp.sqrt(nq[0] * nq[0] + nq[1] * nq[1] + nq[2] * nq[2] + nq[3] * nq[3])
    if nrm > wp.float64(1e-12):
        nq = vec4d(nq[0] / nrm, nq[1] / nrm, nq[2] / nrm, nq[3] / nrm)
    q[bidx] = wp.quat(wp.float32(nq[0]), wp.float32(nq[1]),
                      wp.float32(nq[2]), wp.float32(nq[3]))

    b_dxn[t] = wp.sqrt(d_top[0] * d_top[0] + d_top[1] * d_top[1]
                       + d_top[2] * d_top[2])
    b_dthn[t] = wp.sqrt(d_bot[0] * d_bot[0] + d_bot[1] * d_bot[1]
                        + d_bot[2] * d_bot[2])


@wp.kernel
def k_reduce_diag(
    counts: wp.array(dtype=int),
    b_dxn: wp.array(dtype=wp.float64),
    b_dthn: wp.array(dtype=wp.float64),
    diag: wp.array(dtype=wp.float64),
):
    """diag[0] = max_t|Δx|, diag[1] = max_t|Δθ|. dim = 1."""
    tid = wp.tid()
    if tid != 0:
        return
    mx = wp.float64(0.0)
    mt = wp.float64(0.0)
    n_b = counts[0]
    for t in range(n_b):
        mx = wp.max(mx, b_dxn[t])
        mt = wp.max(mt, b_dthn[t])
    diag[0] = mx
    diag[1] = mt


@wp.kernel
def k_anchor(
    r: int,
    counts: wp.array(dtype=int),
    tracked_rows: wp.array(dtype=int),
    U_y_stack: wp.array2d(dtype=wp.float64),
    floor_y_rest: wp.array(dtype=wp.float64),
    q_coord: wp.array(dtype=wp.float64),
    diag: wp.array(dtype=wp.float64),
    c_world_anchor: wp.array(dtype=wp.vec3),
):
    """anchor.y = floor_y_rest + U_y_stack·q_coord (the deformed surface the
    bodies rest on). `q_coord` is the predictor q̃ at substep begin, or the
    updated full q at an in-loop refresh. dim = cap_rows."""
    tr = wp.tid()
    if tr >= counts[1]:
        return
    if diag[3] != wp.float64(0.0):
        return
    ri = tracked_rows[tr]
    dy = wp.float64(0.0)
    for c1 in range(r):
        dy += U_y_stack[tr, c1] * q_coord[c1]
    anc = c_world_anchor[ri]
    c_world_anchor[ri] = wp.vec3(anc[0], wp.float32(floor_y_rest[tr] + dy),
                                 anc[2])


# ===========================================================================
# substep_begin / substep_end kernels (full GPU residency)
# ===========================================================================
@wp.kernel
def k_eval_basis(
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    counts: wp.array(dtype=int),
    r: int,
    row_index: wp.array(dtype=int),
    row_body: wp.array(dtype=int),
    row_off: wp.array(dtype=vec3d),
    grid_Uy: wp.array2d(dtype=wp.float64),
    n_grid_x: int,
    n_grid_z: int,
    length: wp.float64,
    width: wp.float64,
    row_U_y: wp.array2d(dtype=wp.float64),
):
    """Bilinear interpolation of the basis U_y at each tracked contact corner
    (x, z) = body_pos + R·off. Device port of evaluate_basis_at_point
    (reduced_support.py); recomputed each substep because tracked bodies move.
    dim = cap_rows."""
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
    ix = int(wp.clamp(wp.floor(fx), wp.float64(0.0),
                      wp.float64(n_grid_x - 2)))
    iz = int(wp.clamp(wp.floor(fz), wp.float64(0.0),
                      wp.float64(n_grid_z - 2)))
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
    for c in range(r):
        row_U_y[rr, c] = (w00 * grid_Uy[i00, c] + w10 * grid_Uy[i10, c]
                          + w01 * grid_Uy[i01, c] + w11 * grid_Uy[i11, c])


@wp.kernel
def k_eval_cargo(
    q: wp.array(dtype=wp.quat),
    counts: wp.array(dtype=int),
    r: int,
    R_tot: int,
    row_body: wp.array(dtype=int),
    row_cargo_off: wp.array(dtype=int),
    row_cargo_k: wp.array(dtype=int),
    row_corner_modal: wp.array3d(dtype=wp.float64),
    row_U_y: wp.array2d(dtype=wp.float64),
):
    """Co-rotated fem_rigid cargo modal gradient into the AUGMENTED row_U_y
    cargo columns [r:R] (Stage 3, two_band_coupling.html generalized):

        row_U_y[rr, off+j] = −G_a[j] = −(R·Φ_c)[1, j] = −Σ_d R[1,d]·Φ_c[d,j]

    The device row_U_y convention is +U_y in the support cols / −G_a in the
    cargo cols, so the existing `−Σ f·U_y` (k_g), `Σ k·U_y·U_y` (k_hq) and
    `−k·U_y` (k_body_cross / k_anchor) reductions produce, for the cargo block,
    exactly the CPU augmented per-row gradient G_row = [−U_y | +G_a] — no kernel
    logic changes, only the modal dimension grows r → R. R is frozen for the
    substep (computed here at substep begin) — the per-cube analogue of the
    support's frozen U_y. dim = cap_rows; non-cargo rows just zero [r:R]."""
    rr = wp.tid()
    if rr >= counts[2]:
        return
    for c in range(r, R_tot):
        row_U_y[rr, c] = wp.float64(0.0)
    off = row_cargo_off[rr]
    if off < 0:
        return
    kk = row_cargo_k[rr]
    qq = q[row_body[rr]]
    Rm = _quat_to_R(wp.float64(qq[0]), wp.float64(qq[1]),
                    wp.float64(qq[2]), wp.float64(qq[3]))
    for j in range(kk):
        ga = (Rm[1, 0] * row_corner_modal[rr, 0, j]
              + Rm[1, 1] * row_corner_modal[rr, 1, j]
              + Rm[1, 2] * row_corner_modal[rr, 2, j])
        row_U_y[rr, off + j] = -ga

