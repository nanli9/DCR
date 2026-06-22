"""Device (warp) port of the native modal q-block — `Solver6DOF._solve_q_block`.

M1.3: makes the native `(z, q)` modal path (two_band_coupling.html, Approach B)
GPU-resident and CUDA-graph-capturable. The host reference is the numpy
`Solver6DOF._solve_q_block` (block coordinate descent on E(z,q): the colored
primal owns z, this q-block owns q). This module ports that *exact* block-GS
update to a handful of small `wp.launch`-only kernels so nothing leaves the GPU
mid-iteration.

This is the BLOCK-GAUSS-SEIDEL q-block, NOT the cross-term Schur of the coupler
(`reduced_coupled_kernels.py`): no `k_body`/`k_schur`/`k_backsub`, no Δz
back-substitution. The q-block updates only q; the bodies' pose update comes
entirely from the colored primal, which reads the live surface y_rest + U_y·q
in-kernel. The only deviation from a literal simultaneous Newton step is the
under-relaxation `relax` (a numerical solver setting; see
`solver_6dof.py::_solve_q_block` and docs/native_modal_support.md).

All modal math is in `wp.float64` (reading the float32 solver state, converting
up) so the device path matches the numpy reference to fp64 roundoff — the same
idiom the coupler kernels use. The single float32 mirror `q32` is written so the
primal/dual SUPPORT_CONTACT kernels (which read `q_modal` as float32) see the
update, exactly as the host path's `self.q_modal.assign(...)`.

Per-slot scratch `rowdata` (shape (n_sup, 2)) columns:  0:k_lhs  1:f
"""
from __future__ import annotations

import warp as wp

wp.set_module_options({"enable_backward": False})

vec3d = wp.vec3d

_ZERO = wp.constant(wp.float64(0.0))
_ONE = wp.constant(wp.float64(1.0))
_HALF = wp.constant(wp.float64(0.5))


# ---------------------------------------------------------------------------
# float64 quaternion → rotation (XYZW), bit-faithful to modal_qblock._quat_to_R
# ---------------------------------------------------------------------------
@wp.func
def _quat_to_R64(qx: wp.float64, qy: wp.float64, qz: wp.float64,
                 qw: wp.float64):
    n = qx * qx + qy * qy + qz * qz + qw * qw
    if n < wp.float64(1e-30):
        return wp.mat33d(_ONE, _ZERO, _ZERO,
                         _ZERO, _ONE, _ZERO,
                         _ZERO, _ZERO, _ONE)
    s = wp.float64(2.0) / n
    return wp.mat33d(
        _ONE - s * (qy * qy + qz * qz), s * (qx * qy - qz * qw), s * (qx * qz + qy * qw),
        s * (qx * qy + qz * qw), _ONE - s * (qx * qx + qz * qz), s * (qy * qz - qx * qw),
        s * (qx * qz - qy * qw), s * (qy * qz + qx * qw), _ONE - s * (qx * qx + qy * qy))


# ---------------------------------------------------------------------------
# Per-slot contact force  (mirrors the engaged-only gather in _solve_q_block)
# ---------------------------------------------------------------------------
@wp.kernel
def k_modal_rowforce(
    r: int,
    support_row_idx: wp.array(dtype=int),     # slot → c-row index
    c_active: wp.array(dtype=int),
    c_body_a: wp.array(dtype=int),
    c_off_a: wp.array(dtype=wp.vec3),
    c_penalty: wp.array(dtype=float),
    c_lambda: wp.array(dtype=float),
    c_stiffness: wp.array(dtype=float),
    c_alpha_C0: wp.array(dtype=float),
    x: wp.array(dtype=wp.vec3),
    q: wp.array(dtype=wp.quat),
    U_y: wp.array2d(dtype=wp.float64),        # (n_sup, R) per-row gradient W, f64
    q_modal: wp.array(dtype=wp.float64),      # (R,) live augmented Q, f64
    y_rest: wp.array(dtype=wp.float64),       # (n_sup,) ORIGINAL rest height
    rowdata: wp.array2d(dtype=wp.float64),    # (n_sup, 2) out: [k_lhs, f]
):
    """Per support slot: f = min(ρ·C + λ_eff, 0); only ENGAGED (f<0) compressive
    contacts load the mode. C = corner_y − (y_rest + W·Q), read against the LIVE
    Q (W = U_y for the support-only path; W = [U_y | −G_a] for native cargo, so
    Q's cargo a-block adds the cube's co-rotated corner flex). `y_rest` is the
    ORIGINAL rest height — NOT c_world_anchor, which carries the frozen cube flex
    for the primal. Writes rowdata[s] = (ρ, f) when engaged, else (0, 0).
    dim = n_sup."""
    s = wp.tid()
    cidx = support_row_idx[s]
    rowdata[s, 0] = _ZERO
    rowdata[s, 1] = _ZERO
    if c_active[cidx] == 0:
        return
    bi = c_body_a[cidx]
    qq = q[bi]
    R = _quat_to_R64(wp.float64(qq[0]), wp.float64(qq[1]),
                     wp.float64(qq[2]), wp.float64(qq[3]))
    off = c_off_a[cidx]
    r_w = R * vec3d(wp.float64(off[0]), wp.float64(off[1]), wp.float64(off[2]))
    corner_y = wp.float64(x[bi][1]) + r_w[1]
    # surf = y_rest + W·Q  (W spans support modes ⊕ the cube's −G_a a-block)
    uq = _ZERO
    for kk in range(r):
        uq += U_y[s, kk] * q_modal[kk]
    C = corner_y - (y_rest[s] + uq)
    # hard constraints (isinf stiffness) carry the AL stabilization; support
    # rows are soft (large-but-finite), so this branch is normally skipped —
    # replicate it anyway to stay bit-identical to the host path.
    stiff = wp.float64(c_stiffness[cidx])
    lam_eff = _ZERO
    if stiff > wp.float64(1e30):
        C = C - wp.float64(c_alpha_C0[cidx])
        lam_eff = wp.float64(c_lambda[cidx])
    rho = wp.float64(c_penalty[cidx])
    f = wp.min(rho * C + lam_eff, _ZERO)      # clamp(ρC+λ, −∞, 0): compressive
    if f >= _ZERO:                            # engaged contacts only
        return
    rowdata[s, 0] = rho
    rowdata[s, 1] = f


# ---------------------------------------------------------------------------
# Modal Hessian / gradient  (mirrors the H_q, g_q assembly in _solve_q_block)
# ---------------------------------------------------------------------------
@wp.kernel
def k_modal_hq(
    r: int,
    n_sup: int,
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    Dq: wp.array2d(dtype=wp.float64),
    inv_dt2: wp.float64,
    inv_dt: wp.float64,
    U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    Hq: wp.array2d(dtype=wp.float64),
):
    """H_q[a,b] = 1/h²·M_q + 1/h·D_q + K_q + Σ_s k·U_y[s,a]·U_y[s,b]. dim=(r,r)."""
    a, b = wp.tid()
    acc = inv_dt2 * Mq[a, b] + inv_dt * Dq[a, b] + Kq[a, b]
    for s in range(n_sup):
        acc += rowdata[s, 0] * U_y[s, a] * U_y[s, b]
    Hq[a, b] = acc


@wp.kernel
def k_modal_gq(
    r: int,
    n_sup: int,
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    Dq: wp.array2d(dtype=wp.float64),
    inv_dt2: wp.float64,
    inv_dt: wp.float64,
    q: wp.array(dtype=wp.float64),
    q_hat: wp.array(dtype=wp.float64),
    q_n: wp.array(dtype=wp.float64),
    U_y: wp.array2d(dtype=wp.float64),
    rowdata: wp.array2d(dtype=wp.float64),
    gq: wp.array(dtype=wp.float64),
):
    """g_q[a] = Σ_b [1/h²·M_q(q−q̃) + 1/h·D_q(q−qⁿ) + K_q·q]_a − Σ_s f·U_y[s,a].
    The IMPLICIT 1/h·D_q(q−qⁿ) damping (two_band_coupling.html). dim = r."""
    a = wp.tid()
    inertial = _ZERO
    for b in range(r):
        inertial += (inv_dt2 * Mq[a, b] * (q[b] - q_hat[b])
                     + inv_dt * Dq[a, b] * (q[b] - q_n[b])
                     + Kq[a, b] * q[b])
    ff = _ZERO
    for s in range(n_sup):
        ff += rowdata[s, 1] * U_y[s, a]
    gq[a] = inertial - ff


# ---------------------------------------------------------------------------
# r×r solve  (Gaussian elimination, partial pivot — mirrors coupler k_eps_solve)
# ---------------------------------------------------------------------------
@wp.func
def _abd_row(q: wp.array(dtype=wp.float64), o: int, i: int) -> vec3d:
    """Affine row aᵢ = eᵢ + d[3i:3i+3] of the ABD deformation d = vec(F−I)."""
    if i == 0:
        return vec3d(_ONE + q[o + 0], q[o + 1], q[o + 2])
    if i == 1:
        return vec3d(q[o + 3], _ONE + q[o + 4], q[o + 5])
    return vec3d(q[o + 6], q[o + 7], _ONE + q[o + 8])


@wp.kernel
def k_cargo_internal(
    off: wp.array(dtype=int),          # (n_nl,) a-block offset of each abd cube
    kappa: wp.array(dtype=wp.float64),  # (n_nl,) κ_v
    q: wp.array(dtype=wp.float64),      # (R,) augmented Q (reads the d-block)
    gq: wp.array(dtype=wp.float64),     # (R,) gradient — += V⊥ gradient
    Hq: wp.array2d(dtype=wp.float64),   # (R,R) Hessian — += V⊥ Hessian
):
    """ABD orthogonality potential V⊥ (ABD Eq. 6-8) linearized at the current d:
    add ∂V⊥/∂d to gq and ∂²V⊥/∂d² to the cube's 9×9 a-block of Hq, EACH q-block
    iteration (a damped Newton step on the quartic V⊥). One thread per abd cube;
    blocks are disjoint so the plain += after k_modal_hq/k_modal_gq is race-free.
    Mirrors ABDAffineBody.internal_grad_d / internal_hess_d exactly. dim = n_nl."""
    t = wp.tid()
    o = off[t]
    kap = kappa[t]
    four = wp.float64(4.0) * kap
    eight = wp.float64(8.0) * kap
    for i in range(3):
        ai = _abd_row(q, o, i)
        aii = wp.dot(ai, ai)
        # gradient gᵢ = 4κ(aᵢ·aᵢ−1)aᵢ + Σ_{j≠i} 4κ(aᵢ·aⱼ)aⱼ
        gi = (four * (aii - _ONE)) * ai
        for j in range(3):
            if j != i:
                aj = _abd_row(q, o, j)
                gi = gi + (four * wp.dot(ai, aj)) * aj
        gq[o + 3 * i + 0] = gq[o + 3 * i + 0] + gi[0]
        gq[o + 3 * i + 1] = gq[o + 3 * i + 1] + gi[1]
        gq[o + 3 * i + 2] = gq[o + 3 * i + 2] + gi[2]
        # diagonal Hessian block Hᵢᵢ = 8κ aᵢaᵢᵀ + 4κ(aᵢ·aᵢ−1)I + Σ_{j≠i} 4κ aⱼaⱼᵀ
        for p in range(3):
            for c in range(3):
                val = eight * ai[p] * ai[c]
                if p == c:
                    val = val + four * (aii - _ONE)
                for j in range(3):
                    if j != i:
                        aj = _abd_row(q, o, j)
                        val = val + four * aj[p] * aj[c]
                Hq[o + 3 * i + p, o + 3 * i + c] = Hq[o + 3 * i + p, o + 3 * i + c] + val
        # off-diagonal Hᵢⱼ = 4κ(aⱼaᵢᵀ + (aᵢ·aⱼ)I)  (j ≠ i)
        for j in range(3):
            if j != i:
                aj = _abd_row(q, o, j)
                aij = wp.dot(ai, aj)
                for p in range(3):
                    for c in range(3):
                        val = four * aj[p] * ai[c]
                        if p == c:
                            val = val + four * aij
                        Hq[o + 3 * i + p, o + 3 * j + c] = (
                            Hq[o + 3 * i + p, o + 3 * j + c] + val)


@wp.kernel
def k_modal_solve(
    r: int,
    eps: wp.float64,
    relax: wp.float64,
    Hq: wp.array2d(dtype=wp.float64),   # (r,r) scratch — mutated in place as S
    gq: wp.array(dtype=wp.float64),     # (r,) gradient
    dq: wp.array(dtype=wp.float64),     # (r,) scratch
    q: wp.array(dtype=wp.float64),      # (r,) amplitude, updated
    q32: wp.array(dtype=float),         # (r,) float32 mirror for primal/dual
):
    """Solve (H_q + ε·I)·Δq = −g_q, then q ← q + relax·Δq and refresh the
    float32 mirror. Single thread (GE is sequential; r is small). dim = 1."""
    tid = wp.tid()
    if tid != 0:
        return
    for a in range(r):
        Hq[a, a] = Hq[a, a] + eps
        dq[a] = -gq[a]

    for col in range(r):
        piv = col
        big = wp.abs(Hq[col, col])
        for rr2 in range(col + 1, r):
            v = wp.abs(Hq[rr2, col])
            if v > big:
                big = v
                piv = rr2
        if piv != col:
            for cc in range(r):
                tmp = Hq[col, cc]
                Hq[col, cc] = Hq[piv, cc]
                Hq[piv, cc] = tmp
            tmpb = dq[col]
            dq[col] = dq[piv]
            dq[piv] = tmpb
        pivot = Hq[col, col]
        for rr2 in range(col + 1, r):
            factor = Hq[rr2, col] / pivot
            if factor != _ZERO:
                for cc in range(col, r):
                    Hq[rr2, cc] = Hq[rr2, cc] - factor * Hq[col, cc]
                dq[rr2] = dq[rr2] - factor * dq[col]
    for ii in range(r):
        a = r - 1 - ii
        acc = dq[a]
        for cc in range(a + 1, r):
            acc = acc - Hq[a, cc] * dq[cc]
        dq[a] = acc / Hq[a, a]

    for a in range(r):
        q[a] = q[a] + relax * dq[a]
        q32[a] = wp.float32(q[a])


# ---------------------------------------------------------------------------
# Predictor / commit / diagnostics (per-substep, outside the captured loop)
# ---------------------------------------------------------------------------
@wp.kernel
def k_modal_predict(
    r: int,
    h_pred: wp.float64,
    h2: wp.float64,
    q: wp.array(dtype=wp.float64),
    qdot: wp.array(dtype=wp.float64),
    grav_acc: wp.array(dtype=wp.float64),    # (r,) M_q⁻¹ f_q^grav (constant)
    q_n: wp.array(dtype=wp.float64),
    q_hat: wp.array(dtype=wp.float64),
    q32: wp.array(dtype=float),
):
    """qⁿ snapshot + inertial predictor q̃ = qⁿ + h·q̇ⁿ + h²·M_q⁻¹ f_q^grav
    (two_band_coupling.html — "Inertial predictors"). h_pred = 0 for the
    frozen-q̇ counterfactual. Also seeds the float32 mirror with qⁿ. dim = r."""
    a = wp.tid()
    q_n[a] = q[a]
    q_hat[a] = q[a] + h_pred * qdot[a] + h2 * grav_acc[a]
    q32[a] = wp.float32(q[a])


@wp.kernel
def k_modal_qdot(
    r: int,
    inv_dt: wp.float64,
    freeze: int,
    q: wp.array(dtype=wp.float64),
    q_n: wp.array(dtype=wp.float64),
    qdot: wp.array(dtype=wp.float64),
):
    """q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h (backward Euler). Frozen counterfactual keeps
    q̇ ≡ 0 (no commit). dim = r."""
    a = wp.tid()
    if freeze == 0:
        qdot[a] = (q[a] - q_n[a]) * inv_dt


@wp.kernel
def k_modal_diag(
    r: int,
    Mq: wp.array2d(dtype=wp.float64),
    Kq: wp.array2d(dtype=wp.float64),
    q: wp.array(dtype=wp.float64),
    qdot: wp.array(dtype=wp.float64),
    out: wp.array(dtype=wp.float64),         # (2,) [modal_KE, modal_PE]
):
    """Modal diagnostics ½q̇ᵀM_qq̇ and ½qᵀK_qq for the viewer/tests. dim = 1."""
    tid = wp.tid()
    if tid != 0:
        return
    ke = _ZERO
    pe = _ZERO
    for a in range(r):
        mqd = _ZERO
        kq = _ZERO
        for b in range(r):
            mqd += Mq[a, b] * qdot[b]
            kq += Kq[a, b] * q[b]
        ke += qdot[a] * mqd
        pe += q[a] * kq
    out[0] = _HALF * ke
    out[1] = _HALF * pe
