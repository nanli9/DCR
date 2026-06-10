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
    Kq: wp.array2d(dtype=wp.float64),
    row_U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    Hq: wp.array2d(dtype=wp.float64),
):
    """H_q[a,b] = K_q[a,b] + Σ_row k·U_y[a]·U_y[b]. dim = (r, r)."""
    a, b = wp.tid()
    acc = Kq[a, b]
    nrows = counts[2]
    for rr in range(nrows):
        acc += rowdata[rr, 0] * row_U_y[rr, a] * row_U_y[rr, b]
    Hq[a, b] = acc


@wp.kernel
def k_g(
    r: int,
    counts: wp.array(dtype=int),
    Kq: wp.array2d(dtype=wp.float64),
    q_s: wp.array(dtype=wp.float64),
    row_U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    gq: wp.array(dtype=wp.float64),
    Fq: wp.array(dtype=wp.float64),
):
    """g_q[a] = (K_q·q_s)[a] − Σ_row f·U_y[a];  F_q[a] = Σ_row f·U_y[a].
    dim = r."""
    a = wp.tid()
    kqs = wp.float64(0.0)
    for b in range(r):
        kqs += Kq[a, b] * q_s[b]
    ff = wp.float64(0.0)
    nrows = counts[2]
    for rr in range(nrows):
        ff += rowdata[rr, 1] * row_U_y[rr, a]
    gq[a] = kqs - ff
    Fq[a] = ff


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
    q_s: wp.array(dtype=wp.float64),
    diag: wp.array(dtype=wp.float64),
):
    """ε-regularize S, solve S·dq = rhs (Gaussian elimination, partial pivot),
    apply q_s += dq. Single thread (GE is sequential; r is small). dim = 1."""
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
        q_s[a] = q_s[a] + dq[a]
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
        q_s: wp.array(dtype=wp.float64),
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

        # dq = Δq_s ; q_s += dq ; ‖dq‖ → diag[2].
        wp.tile_store(dq, xt)
        qt = wp.tile_load(q_s, shape=R)
        qt = qt + xt
        wp.tile_store(q_s, qt)
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
    q_s: wp.array(dtype=wp.float64),
    diag: wp.array(dtype=wp.float64),
    c_world_anchor: wp.array(dtype=wp.vec3),
):
    """anchor.y = floor_y_rest + U_y_stack·q_s. dim = cap_rows."""
    tr = wp.tid()
    if tr >= counts[1]:
        return
    if diag[3] != wp.float64(0.0):
        return
    ri = tracked_rows[tr]
    dy = wp.float64(0.0)
    for c1 in range(r):
        dy += U_y_stack[tr, c1] * q_s[c1]
    anc = c_world_anchor[ri]
    c_world_anchor[ri] = wp.vec3(anc[0], wp.float32(floor_y_rest[tr] + dy),
                                 anc[2])


@wp.kernel
def k_anchor_lp(
    r: int,
    q_s: wp.array(dtype=wp.float64),
    a_lp: wp.float64,
    q_s_anchor_lp: wp.array(dtype=wp.float64),
):
    """EMA low-pass of q_s for the contact anchor (collision-kick + rock fix):
        q_s_anchor_lp += a_lp·(q_s − q_s_anchor_lp).
    Routes only the smooth static-sag part of q_s into the anchor so an impact
    spike in q_s no longer jumps the surface under a body. dim = r."""
    i = wp.tid()
    if i >= r:
        return
    q_s_anchor_lp[i] = q_s_anchor_lp[i] + a_lp * (q_s[i] - q_s_anchor_lp[i])


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
def k_iir_precompute(
    r: int,
    q_d: wp.array(dtype=wp.float64),
    qdot_d: wp.array(dtype=wp.float64),
    omega: wp.array(dtype=wp.float64),
    zeta: wp.array(dtype=wp.float64),
    mass: wp.array(dtype=wp.float64),
    h: wp.float64,
    q_free: wp.array(dtype=wp.float64),
    qdot_free: wp.array(dtype=wp.float64),
    S_h_diag: wp.array(dtype=wp.float64),
    T_h_diag: wp.array(dtype=wp.float64),
):
    """Per-mode exact resonator precompute (eigen path). Device port of
    exact_modal_step_precompute (exact_resonator.py); branch ladder
    frozen/rigid/critical/over/under. dim = r."""
    i = wp.tid()
    if i >= r:
        return
    q = q_d[i]
    qd = qdot_d[i]
    m = mass[i]
    om = omega[i]
    ze = zeta[i]

    safe_mass = m
    if not (m > wp.float64(0.0)):
        safe_mass = wp.float64(1.0)
    safe_omega = om
    if not (om > wp.float64(1e-12)):
        safe_omega = wp.float64(1.0)
    frozen = not (wp.isfinite(m) != 0 and m > wp.float64(0.0))
    rigid = (not frozen) and (
        (om * h < wp.float64(1e-6)) or (om < wp.float64(1e-12)))
    crit = (not frozen) and (not rigid) and (
        wp.abs(ze - wp.float64(1.0)) < wp.float64(1e-6))
    over = (not frozen) and (not rigid) and (not crit) and (
        ze > wp.float64(1.0))

    ai = ze * safe_omega
    ki = safe_mass * safe_omega * safe_omega
    safe_ki = wp.max(ki, wp.float64(1e-40))
    E = wp.exp(-ai * h)

    qf = q
    qdf = qd
    S = wp.float64(1e-18)
    T = wp.float64(0.0)
    if frozen:
        qf = q
        qdf = qd
        S = wp.float64(1e-18)
        T = wp.float64(0.0)
    elif rigid:
        qf = q + h * qd
        qdf = qd
        S = (h * h) / (wp.float64(2.0) * safe_mass)
        T = h / safe_mass
    elif crit:
        wh = safe_omega * h
        qf = E * ((wp.float64(1.0) + wh) * q + h * qd)
        qdf = E * (-(safe_omega * safe_omega) * h * q
                   + (wp.float64(1.0) - wh) * qd)
        S = (wp.float64(1.0) - E * (wp.float64(1.0) + wh)) / safe_ki
        T = E * h / safe_mass
    elif over:
        wd = safe_omega * wp.sqrt(wp.max(ze * ze - wp.float64(1.0),
                                         wp.float64(1e-30)))
        ch = wp.cosh(wd * h)
        sh = wp.sinh(wd * h)
        aow = ai / wd
        qf = E * ((ch + aow * sh) * q + (sh / wd) * qd)
        qdf = E * (-(safe_omega * safe_omega / wd) * sh * q
                   + (ch - aow * sh) * qd)
        S = (wp.float64(1.0) - E * (ch + aow * sh)) / safe_ki
        T = E * sh / (safe_mass * wd)
    else:
        wd = safe_omega * wp.sqrt(wp.max(wp.float64(1.0) - ze * ze,
                                         wp.float64(1e-30)))
        c = wp.cos(wd * h)
        s = wp.sin(wd * h)
        aow = ai / wd
        qf = E * ((c + aow * s) * q + (s / wd) * qd)
        qdf = E * (-(safe_omega * safe_omega / wd) * s * q
                   + (c - aow * s) * qd)
        S = (wp.float64(1.0) - E * (c + aow * s)) / safe_ki
        T = E * s / (safe_mass * wd)

    q_free[i] = qf
    qdot_free[i] = qdf
    S_h_diag[i] = wp.max(S, wp.float64(1e-18))
    T_h_diag[i] = T


@wp.kernel
def k_modal_energy(
    r: int,
    q_d: wp.array(dtype=wp.float64),
    qdot_d: wp.array(dtype=wp.float64),
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    out: wp.array(dtype=wp.float64),
    out_idx: int,
):
    """out[out_idx] = ½·q̇·Mq·q̇ + ½·q·Kq·q  (modal energy). dim = 1."""
    if wp.tid() != 0:
        return
    ke = wp.float64(0.0)
    pe = wp.float64(0.0)
    for a in range(r):
        mv = wp.float64(0.0)
        kv = wp.float64(0.0)
        for b in range(r):
            mv += Mq[a, b] * qdot_d[b]
            kv += Kq[a, b] * q_d[b]
        ke += qdot_d[a] * mv
        pe += q_d[a] * kv
    out[out_idx] = wp.float64(0.5) * ke + wp.float64(0.5) * pe


@wp.kernel
def k_iir_apply(
    r: int,
    Fq: wp.array(dtype=wp.float64),
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
    """EMA high-pass of the modal load → force q_d via the exact resonator.
    q_d = q_free + S_h·F_dyn; q̇_d = q̇_free + T_h·F_dyn. dim = r.

    V2-B: when `band_owns != 0` the velocity band is the SOLE ring excitation,
    so the forced dynamic load is gated to zero (F_q_dyn = 0 → q_d, q̇_d decay
    freely here and the band's impulse kicks q̇_d next). The EMA F_q_static_lp
    still tracks F_total, matching the numpy V2-A gate (impulse_port.py)."""
    i = wp.tid()
    if i >= r:
        return
    if first_substep[0] != 0:
        alpha = wp.float64(1.0)
    else:
        alpha = wp.float64(1.0) - wp.exp(-h / wp.max(tau, wp.float64(1e-9)))
    f_total = Fq[i]
    f_static = (wp.float64(1.0) - alpha) * F_q_static_lp[i] + alpha * f_total
    F_q_static_lp[i] = f_static
    f_dyn = f_total - f_static
    if band_owns != 0:
        f_dyn = wp.float64(0.0)
    F_q_dyn[i] = f_dyn
    q_d[i] = q_free[i] + S_h_diag[i] * f_dyn
    qdot_d[i] = qdot_free[i] + T_h_diag[i] * f_dyn


@wp.kernel
def k_passivity(
    r: int,
    q_d: wp.array(dtype=wp.float64),
    qdot_d: wp.array(dtype=wp.float64),
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    F_q_dyn: wp.array(dtype=wp.float64),
    E_begin: wp.array(dtype=wp.float64),
    h: wp.float64,
    first_substep: wp.array(dtype=int),
    pass_counter: wp.array(dtype=int),
):
    """Passivity log: increment counter if ΔE_q_d exceeds the work bound
    |h·F_dyn·q̇_d|. Also clears the first-substep EMA flag (once). dim = 1."""
    if wp.tid() != 0:
        return
    ke = wp.float64(0.0)
    pe = wp.float64(0.0)
    work = wp.float64(0.0)
    for a in range(r):
        mv = wp.float64(0.0)
        kv = wp.float64(0.0)
        for b in range(r):
            mv += Mq[a, b] * qdot_d[b]
            kv += Kq[a, b] * q_d[b]
        ke += qdot_d[a] * mv
        pe += q_d[a] * kv
        work += F_q_dyn[a] * qdot_d[a]
    e_end = wp.float64(0.5) * ke + wp.float64(0.5) * pe
    dE = e_end - E_begin[0]
    w_bound = wp.abs(h * work)
    if dE > w_bound + wp.float64(1e-12):
        pass_counter[0] = pass_counter[0] + 1
    first_substep[0] = 0


@wp.kernel
def k_sync_total(
    r: int,
    q_s: wp.array(dtype=wp.float64),
    q_d: wp.array(dtype=wp.float64),
    qdot_d: wp.array(dtype=wp.float64),
    q_total: wp.array(dtype=wp.float64),
    qdot_total: wp.array(dtype=wp.float64),
):
    """q = q_s + q_d; q̇ = q̇_d  (sync_total_from_split). dim = r."""
    i = wp.tid()
    if i >= r:
        return
    q_total[i] = q_s[i] + q_d[i]
    qdot_total[i] = qdot_d[i]


# ===========================================================================
# V2-B: device-resident velocity band (passive impulse, reservoir governor)
# ---------------------------------------------------------------------------
# Device port of dcr/dcr/impulse_port.py::apply_velocity_band — the SOLE
# body↔ring channel under `band_owns_excitation`. One momentum-conserving
# impulse per closing contact corner kicks both the modal ring (q̇_d -= U_y·λ)
# and the body (v,ω), scaled by the reservoir-exact governor so the per-prefix
# §15 bound  Σ ΔE_modal ≤ η Σ L  holds (foundation §1/§6/§15).
#
# The reservoir is a SINGLE shared scalar (one modal field) debited SEQUENTIALLY
# per corner (design rule 3: sequential-per-support, NOT Jacobi). q̇_d is also
# shared. So the band is inherently sequential over corners → a single-thread
# kernel walking the CSR rows in body-grouped order, exactly the numpy loop
# order. Corner count is small (≈ books × bottom corners) so single-thread is
# cheap next to the r×r Schur solve; the win is staying ON-DEVICE (no per-substep
# host round-trip).
#
# # DEVIATION (internal f64 to match numpy): body v/ω are accumulated in f64
# scratch (v_band/omega_band) across a body's corners and truncated to the f32
# solver arrays only at the end — mirroring the numpy reference, which mutates
# an upcast f64 copy and writes `.assign(...astype(float32))` once.
# ===========================================================================
@wp.func
def _reservoir_alpha(a_m: wp.float64, b_m: wp.float64, l1: wp.float64,
                     l2: wp.float64, R: wp.float64,
                     eta: wp.float64) -> wp.float64:
    """Reservoir-exact passive α (passive_inject.reservoir_alpha; §6/§15).
    Largest α∈[0,1] with net draw D(α)=ΔE_modal(α)−η·L(α) ≤ R."""
    eps = wp.float64(1e-18)
    one = wp.float64(1.0)
    zero = wp.float64(0.0)
    if a_m < eps:
        return one
    A = wp.float64(0.5) * a_m - eta * l2          # ≥ 0 (l2 ≤ 0)
    B = b_m - eta * l1
    if A < eps:
        if B <= zero:
            return one
        return wp.clamp(R / B, zero, one)
    disc = B * B + wp.float64(4.0) * A * wp.max(zero, R)
    alpha_plus = (-B + wp.sqrt(wp.max(zero, disc))) / (wp.float64(2.0) * A)
    return wp.clamp(alpha_plus, zero, one)


@wp.func
def _reservoir_draw(a_m: wp.float64, b_m: wp.float64, l1: wp.float64,
                    l2: wp.float64, alpha: wp.float64,
                    eta: wp.float64) -> wp.float64:
    """Net reservoir draw D(α) (passive_inject.reservoir_draw; §1/§15)."""
    return (b_m - eta * l1) * alpha \
        + (wp.float64(0.5) * a_m - eta * l2) * alpha * alpha


@wp.kernel
def k_velocity_band(
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    v: wp.array(dtype=wp.vec3),
    omega: wp.array(dtype=wp.vec3),
    mass: wp.array(dtype=float),
    inertia_local: wp.array(dtype=wp.mat33),
    counts: wp.array(dtype=int),
    body_ids: wp.array(dtype=int),
    row_body: wp.array(dtype=int),
    row_off: wp.array(dtype=vec3d),
    row_U_y: wp.array2d(dtype=wp.float64),
    row_active: wp.array(dtype=int),
    q_s: wp.array(dtype=wp.float64),
    qdot_d: wp.array(dtype=wp.float64),
    r: int,
    shelf_y_rest: wp.float64,
    margin: wp.float64,
    eta: wp.float64,
    e_rest: wp.float64,
    vel_eps: wp.float64,
    a_floor: wp.float64,
    v_band: wp.array(dtype=vec3d),       # f64 scratch (n_bodies)
    omega_band: wp.array(dtype=vec3d),   # f64 scratch (n_bodies)
    reservoir: wp.array(dtype=wp.float64),    # [1] persistent
    band_diag: wp.array(dtype=wp.float64),    # [n_impulses, max_lambda, clamps]
):
    """Single-thread sequential velocity-band impulse over contact corners.
    dim = 1. Mutates qdot_d, v, omega, reservoir, band_diag in place."""
    if wp.tid() != 0:
        return
    n_b = counts[0]
    n_rows = counts[2]
    # Upcast body v/ω into f64 accumulators (so a body's multiple corners
    # accumulate in f64, truncated to f32 only on writeback — numpy parity).
    for bb in range(n_b):
        bidx = body_ids[bb]
        v_band[bidx] = _to_vec3d(v[bidx])
        omega_band[bidx] = _to_vec3d(omega[bidx])

    res = reservoir[0]
    n_imp = _ZERO
    max_lam = _ZERO
    n_clamp = _ZERO
    # Rows are CSR-grouped by body, and R / Iⁱⁿᵛ depend only on the body pose
    # (constant during the band) — recompute them only when the body changes
    # (bit-identical to per-row, far fewer 3×3 inverses + quat→mat).
    cur_body = int(-1)
    R = wp.identity(n=3, dtype=wp.float64)
    Iinv = wp.identity(n=3, dtype=wp.float64)
    m = _ZERO

    for rr in range(n_rows):
        if row_active[rr] == 0:
            continue
        bidx = row_body[rr]
        if bidx != cur_body:
            cur_body = bidx
            m = wp.float64(mass[bidx])
            if m > _ZERO:
                qq = q[bidx]
                R = _quat_to_R(wp.float64(qq[0]), wp.float64(qq[1]),
                               wp.float64(qq[2]), wp.float64(qq[3]))
                Iinv = R * _inv3(_to_mat33d(inertia_local[bidx])) \
                    * wp.transpose(R)
        if m <= _ZERO:
            continue
        r_w = R * row_off[rr]
        corner_y = wp.float64(x[bidx][1]) + r_w[1]
        # U_y·q_s, ‖U_y‖², U_y·q̇_d  (one pass over the r modes).
        uq = _ZERO
        uu = _ZERO
        uqd = _ZERO
        for a in range(r):
            uy = row_U_y[rr, a]
            uq += uy * q_s[a]
            uu += uy * uy
            uqd += uy * qdot_d[a]
        surf_y = shelf_y_rest + uq
        if corner_y - surf_y > margin:           # separated
            continue
        vb = v_band[bidx]
        wb = omega_band[bidx]
        # (ω × r_w).y = ω_z r_x − ω_x r_z ; rxn = r_w × n̂ = (−r_z, 0, r_x).
        cross_y = wb[2] * r_w[0] - wb[0] * r_w[2]
        v_corner_y = vb[1] + cross_y
        g_dot = v_corner_y - uqd
        if g_dot >= -vel_eps:                    # not closing
            continue
        rxn = vec3d(-r_w[2], _ZERO, r_w[0])
        Iinv_rxn = Iinv * rxn          # Iⁱⁿᵛ cached per body above
        w_eff = _ONE / m + wp.dot(rxn, Iinv_rxn) + uu
        lam0 = -(_ONE + e_rest) * g_dot / w_eff
        if lam0 <= _ZERO:
            continue
        a_m = lam0 * lam0 * uu                    # ‖s‖² = λ₀²‖U_y‖²
        b_m = -lam0 * uqd                         # q̇·s = −λ₀(q̇·U_y)
        w_r = w_eff - uu                          # rigid eff inverse mass
        l1 = -v_corner_y * lam0
        l2 = -_HALF * w_r * lam0 * lam0           # ≤ 0
        alpha = _reservoir_alpha(a_m, b_m, l1, l2, res, eta)
        if (alpha < _ONE - wp.float64(1e-9)) and (a_m > a_floor):
            n_clamp += _ONE
        lam = alpha * lam0
        res -= _reservoir_draw(a_m, b_m, l1, l2, alpha, eta)
        # Apply the momentum-conserving impulse.
        v_band[bidx] = vec3d(vb[0], vb[1] + lam / m, vb[2])
        dom = Iinv_rxn * lam
        omega_band[bidx] = vec3d(wb[0] + dom[0], wb[1] + dom[1], wb[2] + dom[2])
        for a in range(r):
            qdot_d[a] = qdot_d[a] - row_U_y[rr, a] * lam
        n_imp += _ONE
        if lam > max_lam:
            max_lam = lam

    # Truncate the f64 accumulators back to the f32 solver arrays (once).
    for bb in range(n_b):
        bidx = body_ids[bb]
        vb = v_band[bidx]
        wb = omega_band[bidx]
        v[bidx] = wp.vec3(wp.float32(vb[0]), wp.float32(vb[1]),
                          wp.float32(vb[2]))
        omega[bidx] = wp.vec3(wp.float32(wb[0]), wp.float32(wb[1]),
                              wp.float32(wb[2]))
    reservoir[0] = res
    # Accumulate run totals (the host reads band_diag only on the last substep;
    # per-substep assignment would report just that substep). band_diag[3]
    # mirrors the live reservoir for a one-shot HUD read.
    band_diag[0] += n_imp
    band_diag[1] = wp.max(band_diag[1], max_lam)
    band_diag[2] += n_clamp
    band_diag[3] = res
