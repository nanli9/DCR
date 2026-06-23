"""Warp device kernels for `SolverXPBD` — the device-resident XPBD substep.

Device + CUDA-graph path for the standalone XPBD solver
(`native_dual_solver_build_plan.md` Stage 2b). The CPU numpy reference in
`solver_xpbd.py::_substep_cpu` lands first and stays the correctness anchor
(CLAUDE.md rule 6); these kernels re-express that EXACT substep on resident
`wp.array` state so `step()` issues only `wp.launch` (no `.numpy()` /
synchronize / host readback in the hot loop) and the fixed launch sequence is
CUDA-graph-capturable.

Design (why this shape — see the Stage-2b profile + bench in docs):
* The dominant cost (≈77 %) is the support/modal Gauss-Seidel sweep, which is
  **sequentially coupled through the shared modal vector q** — every support row
  reads the q that the previous row wrote. That dependency chain cannot be
  colored into independent parallel groups (all rows conflict through q), and
  the scenes are tiny (≤ ~20 bodies, ~70 sequential rows). So the substep runs
  as **compiled sequential `dim=1` kernels** — this preserves the exact GS
  ordering (→ fp64 parity with the numpy reference) while removing the per-row
  Python/numpy interpreter overhead that made the CPU path slow.
  # DEVIATION: none in the math — the projection ORDER is byte-identical to the
  # numpy reference; only host-loop / launch overhead is removed.

* The work is fused into TWO phase kernels per substep — `k_pos_phase`
  (predict + contact generation + position GS solve) and `k_vel_phase`
  (velocity-from-Δx + modal commit + velocity GS solve + diagnostics). This
  cuts the per-substep launch count ~5× (≈10 → 2 kernels), which directly
  removes the launch-overhead floor that dominates small CUDA scenes (the
  per-body predict / velocity-update are serialized inside the phase kernels —
  negligible for these body counts).

* All math is `wp.float64` (state stored f64 on device), so the device path
  matches the numpy reference to fp64 roundoff — the idiom used by
  `modal_qblock_kernels.py`.

Scope: linear cargo (rigid k=0 / fem_rigid / fem; per-mode diagonal block) is
device-resident; **abd** (nonlinear V⊥) and the (rare) multi-cargo case fall
back to the numpy reference — documented in `solver_xpbd.py`.

Spec: Macklin et al. 2016 (XPBD) + §3.5 damping; Müller et al. 2020 (rigid
XPBD); `two_band_coupling.html` (Approach B). Numpy reference re-expressed here:
`solver_xpbd.py` (`_project_normal`, `_project_support`, `_project_modal_elastic`,
`_project_cargo_elastic`, `_solve_velocity`, `_box_box`).
"""
from __future__ import annotations

import warp as wp

wp.set_module_options({"enable_backward": False})

_ZERO = wp.constant(wp.float64(0.0))
_ONE = wp.constant(wp.float64(1.0))
_HALF = wp.constant(wp.float64(0.5))
_TWO = wp.constant(wp.float64(2.0))


@wp.func
def zero_mat() -> wp.mat33d:
    """Zero 3×3 (placeholder for the unused B-side inertia of a floor contact)."""
    return wp.mat33d(_ZERO, _ZERO, _ZERO, _ZERO, _ZERO, _ZERO, _ZERO, _ZERO, _ZERO)


# ===========================================================================
# float64 quaternion / matrix helpers — byte-faithful to solver_xpbd.py's
# numpy _quat_* (XYZW), so the device path tracks the reference to fp64.
# ===========================================================================
@wp.func
def quat_to_R(q: wp.quatd) -> wp.mat33d:
    """Rotation matrix from a (near-unit) XYZW quaternion — the non-normalized
    form of numpy `_quat_to_R` (assumes ‖q‖≈1, as the reference does)."""
    x = q[0]
    y = q[1]
    z = q[2]
    w = q[3]
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z
    return wp.mat33d(
        _ONE - _TWO * (yy + zz), _TWO * (xy - wz), _TWO * (xz + wy),
        _TWO * (xy + wz), _ONE - _TWO * (xx + zz), _TWO * (yz - wx),
        _TWO * (xz - wy), _TWO * (yz + wx), _ONE - _TWO * (xx + yy))


@wp.func
def colv(m: wp.mat33d, k: int) -> wp.vec3d:
    """k-th column of m (a body axis in world frame: numpy R[:, k])."""
    return wp.vec3d(m[0, k], m[1, k], m[2, k])


@wp.func
def qmul(a: wp.quatd, b: wp.quatd) -> wp.quatd:
    """Hamilton product a ⊗ b for XYZW quaternions (numpy `_quat_mul`)."""
    ax = a[0]
    ay = a[1]
    az = a[2]
    aw = a[3]
    bx = b[0]
    by = b[1]
    bz = b[2]
    bw = b[3]
    return wp.quatd(
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz)


@wp.func
def qinv(q: wp.quatd) -> wp.quatd:
    """Inverse of a (near-)unit XYZW quaternion (numpy `_quat_inv`)."""
    x = q[0]
    y = q[1]
    z = q[2]
    w = q[3]
    n2 = x * x + y * y + z * z + w * w
    if n2 < wp.float64(1e-300):
        return wp.quatd(_ZERO, _ZERO, _ZERO, _ONE)
    inv = _ONE / n2
    return wp.quatd(-x * inv, -y * inv, -z * inv, w * inv)


@wp.func
def quat_to_rotvec(q: wp.quatd) -> wp.vec3d:
    """Rotation vector (axis·angle) of an XYZW quaternion (numpy
    `_quat_to_rotvec`); used for ω = Δθ/h."""
    x = q[0]
    y = q[1]
    z = q[2]
    w = q[3]
    if w < _ZERO:                       # shortest arc
        x = -x
        y = -y
        z = -z
        w = -w
    v = wp.vec3d(x, y, z)
    s = wp.sqrt(x * x + y * y + z * z)
    if s < wp.float64(1e-12):
        return _TWO * v                 # small-angle: θ ≈ 2·(vector part)
    angle = _TWO * wp.atan2(s, w)
    return (angle / s) * v


@wp.func
def quat_integrate(q: wp.quatd, omega: wp.vec3d, h: wp.float64) -> wp.quatd:
    """q⁺ = normalize(q + ½ h (ω,0) ⊗ q) (numpy `_quat_integrate`)."""
    wq = wp.quatd(omega[0], omega[1], omega[2], _ZERO)
    m = qmul(wq, q)
    qn = wp.quatd(q[0] + _HALF * h * m[0], q[1] + _HALF * h * m[1],
                  q[2] + _HALF * h * m[2], q[3] + _HALF * h * m[3])
    n = wp.sqrt(qn[0] * qn[0] + qn[1] * qn[1] + qn[2] * qn[2] + qn[3] * qn[3])
    if n > wp.float64(1e-12):
        return wp.quatd(qn[0] / n, qn[1] / n, qn[2] / n, qn[3] / n)
    return wp.quatd(_ZERO, _ZERO, _ZERO, _ONE)


@wp.func
def quat_apply_rotvec(q: wp.quatd, dphi: wp.vec3d) -> wp.quatd:
    """q⁺ = normalize(q + ½ (dφ,0) ⊗ q) (numpy `_quat_apply_rotvec`)."""
    wq = wp.quatd(dphi[0], dphi[1], dphi[2], _ZERO)
    m = qmul(wq, q)
    qn = wp.quatd(q[0] + _HALF * m[0], q[1] + _HALF * m[1],
                  q[2] + _HALF * m[2], q[3] + _HALF * m[3])
    n = wp.sqrt(qn[0] * qn[0] + qn[1] * qn[1] + qn[2] * qn[2] + qn[3] * qn[3])
    if n > wp.float64(1e-12):
        return wp.quatd(qn[0] / n, qn[1] / n, qn[2] / n, qn[3] / n)
    return q


@wp.func
def iIw(R: wp.mat33d, Il: wp.mat33d) -> wp.mat33d:
    """Inverse inertia in world: R · I⁻¹_local · Rᵀ (numpy `_inv_I_world`)."""
    return R * Il * wp.transpose(R)


@wp.func
def gen_inv_mass(invm_i: wp.float64, invIw: wp.mat33d,
                 r: wp.vec3d, n: wp.vec3d) -> wp.float64:
    """Generalized inverse mass invm + (r×n)ᵀ I⁻¹_w (r×n) (numpy `_gen_inv_mass`)."""
    rn = wp.cross(r, n)
    return invm_i + wp.dot(rn, invIw * rn)


@wp.func
def apply_pos(X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
              invm: wp.array(dtype=wp.float64), i: int,
              p: wp.vec3d, r_w: wp.vec3d, invIw: wp.mat33d):
    """Apply position impulse p at world offset r_w to body i (numpy `_apply`)."""
    im = invm[i]
    if im == _ZERO:
        return
    X[i] = X[i] + im * p
    dphi = invIw * wp.cross(r_w, p)
    Q[i] = quat_apply_rotvec(Q[i], dphi)


# ===========================================================================
# Building blocks (one per phase of `_substep_cpu`). Each mutates the resident
# arrays in place; composed by the two phase kernels below.
# ===========================================================================
@wp.func
def predict_bodies_f(nb: int, X: wp.array(dtype=wp.vec3d),
                     Q: wp.array(dtype=wp.quatd), V: wp.array(dtype=wp.vec3d),
                     W: wp.array(dtype=wp.vec3d),
                     x_prev: wp.array(dtype=wp.vec3d),
                     q_prev: wp.array(dtype=wp.quatd),
                     invm: wp.array(dtype=wp.float64), g: wp.vec3d,
                     h: wp.float64):
    """x̂ = x + h(v + hg), q̂ = integrate(q, ω, h); snapshot x_prev/q_prev."""
    for i in range(nb):
        x_prev[i] = X[i]
        q_prev[i] = Q[i]
        if invm[i] != _ZERO:
            V[i] = V[i] + h * g
            X[i] = X[i] + h * V[i]
            Q[i] = quat_integrate(Q[i], W[i], h)


@wp.func
def predict_modal_f(q: wp.array(dtype=wp.float64),
                    qdot: wp.array(dtype=wp.float64),
                    q_n: wp.array(dtype=wp.float64),
                    grav: wp.array(dtype=wp.float64),
                    lam_q: wp.array(dtype=wp.float64),
                    freeze: int, h: wp.float64, r: int):
    """q̃ = qⁿ + h_pred·q̇ⁿ + h²·M_q⁻¹f_grav; q_n=qⁿ; λ_q=0 (freeze ⇒ h_pred=0)."""
    hp = h
    if freeze != 0:
        hp = _ZERO
    for i in range(r):
        q_n[i] = q[i]
        q[i] = q[i] + hp * qdot[i] + h * h * grav[i]
        lam_q[i] = _ZERO


@wp.func
def predict_cargo_f(a: wp.array(dtype=wp.float64),
                    adot: wp.array(dtype=wp.float64),
                    a_n: wp.array(dtype=wp.float64),
                    lam: wp.array(dtype=wp.float64),
                    freeze: int, h: wp.float64, k: int, n_lam: int):
    """ã = aⁿ + h_pred·ȧⁿ; a_n=aⁿ; λ=0 (numpy cargo predict)."""
    hp = h
    if freeze != 0:
        hp = _ZERO
    for i in range(k):
        a_n[i] = a[i]
        a[i] = a[i] + hp * adot[i]
    for i in range(n_lam):
        lam[i] = _ZERO


@wp.func
def reset_support_f(sup_lam: wp.array(dtype=wp.float64), ns: int):
    for s in range(ns):
        sup_lam[s] = _ZERO


# ---- contact generation: floor corners + SAT box-box ----------------------
@wp.func
def sat_overlap(axis: wp.vec3d, a0: wp.vec3d, a1: wp.vec3d, a2: wp.vec3d,
                b0: wp.vec3d, b1: wp.vec3d, b2: wp.vec3d,
                ha: wp.vec3d, hb: wp.vec3d, d: wp.vec3d) -> wp.float64:
    """SAT overlap along `axis` (numpy `_box_box.overlap`); inf if axis ~0."""
    L = wp.length(axis)
    if L < wp.float64(1e-10):
        return wp.float64(1e300)
    n = axis / L
    pa = ha[0] * wp.abs(wp.dot(a0, n)) + ha[1] * wp.abs(wp.dot(a1, n)) \
        + ha[2] * wp.abs(wp.dot(a2, n))
    pb = hb[0] * wp.abs(wp.dot(b0, n)) + hb[1] * wp.abs(wp.dot(b1, n)) \
        + hb[2] * wp.abs(wp.dot(b2, n))
    return pa + pb - wp.abs(wp.dot(d, n))


@wp.func
def sat_orient(axis: wp.vec3d, d: wp.vec3d) -> wp.vec3d:
    """Orient a face axis from B toward A (numpy `_box_box.orient`)."""
    nn = wp.normalize(axis)
    if wp.dot(d, nn) > _ZERO:
        return -nn
    return nn


@wp.func
def sd_to_face(p: wp.vec3d, R: wp.mat33d, he: wp.vec3d, c: wp.vec3d,
               fn: wp.vec3d, margin: wp.float64) -> wp.float64:
    """Signed distance of point p below the face of OBB (R,he,c) with outward
    normal fn (numpy `_box_box.sd_to_face`); inf if p is outside the face slab."""
    pc = p - c
    acc = _ZERO
    for k in range(3):
        ck = colv(R, k)
        if wp.abs(wp.dot(ck, fn)) > wp.float64(0.9):
            continue
        if wp.abs(wp.dot(ck, pc)) > he[k] + margin:
            return wp.float64(1e300)
    for k in range(3):
        acc = acc + he[k] * wp.abs(wp.dot(colv(R, k), fn))
    return wp.dot(pc, fn) - acc


@wp.func
def emit_contact(cur: wp.array(dtype=wp.int32),
                 c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
                 c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
                 c_n: wp.array(dtype=wp.vec3d),
                 c_floory: wp.array(dtype=wp.float64),
                 c_mu: wp.array(dtype=wp.float64),
                 c_lam: wp.array(dtype=wp.float64),
                 c_jt: wp.array(dtype=wp.vec3d), cap: int,
                 a: int, b: int, ra: wp.vec3d, rb: wp.vec3d, n: wp.vec3d,
                 floor_y: wp.float64, mu: wp.float64):
    idx = cur[0]
    if idx >= cap:
        return
    c_a[idx] = a
    c_b[idx] = b
    c_ra[idx] = ra
    c_rb[idx] = rb
    c_n[idx] = n
    c_floory[idx] = floor_y
    c_mu[idx] = mu
    c_lam[idx] = _ZERO
    c_jt[idx] = wp.vec3d(_ZERO, _ZERO, _ZERO)
    cur[0] = idx + 1


@wp.func
def gen_contacts_f(X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
                   invm: wp.array(dtype=wp.float64), hE: wp.array(dtype=wp.vec3d),
                   signs: wp.array(dtype=wp.vec3d),
                   fl_bi: wp.array(dtype=wp.int32),
                   fl_y: wp.array(dtype=wp.float64),
                   fl_mu: wp.array(dtype=wp.float64),
                   n_floor: int, nb: int, self_collide: int,
                   self_mu: wp.float64, margin: wp.float64, cap: int,
                   cur: wp.array(dtype=wp.int32),
                   c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
                   c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
                   c_n: wp.array(dtype=wp.vec3d),
                   c_floory: wp.array(dtype=wp.float64),
                   c_mu: wp.array(dtype=wp.float64),
                   c_lam: wp.array(dtype=wp.float64),
                   c_jt: wp.array(dtype=wp.vec3d)):
    """Re-express numpy `_collect_contacts`: floor-corner contacts + SAT box-box
    (15-axis + corner-clip, split-penetration emit). Sequential so the contact
    ORDER matches the numpy reference exactly (→ GS parity)."""
    cur[0] = 0
    up = wp.vec3d(_ZERO, _ONE, _ZERO)
    zv = wp.vec3d(_ZERO, _ZERO, _ZERO)

    for f in range(n_floor):
        bi = fl_bi[f]
        fy = fl_y[f]
        mu = fl_mu[f]
        R = quat_to_R(Q[bi])
        he = hE[bi]
        for ci in range(8):
            s = signs[ci]
            off = wp.vec3d(s[0] * he[0], s[1] * he[1], s[2] * he[2])
            cw = X[bi] + R * off
            if cw[1] - fy < margin:
                emit_contact(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory, c_mu,
                             c_lam, c_jt, cap, bi, -1, off, zv, up, fy, mu)

    if self_collide == 0:
        return
    for i in range(nb):
        for j in range(i + 1, nb):
            if invm[i] == _ZERO and invm[j] == _ZERO:
                continue
            Ra = quat_to_R(Q[i])
            Rb = quat_to_R(Q[j])
            ha = hE[i]
            hb = hE[j]
            d = X[j] - X[i]
            a0 = colv(Ra, 0)
            a1 = colv(Ra, 1)
            a2 = colv(Ra, 2)
            b0 = colv(Rb, 0)
            b1 = colv(Rb, 1)
            b2 = colv(Rb, 2)

            sep = int(0)
            min_face = wp.float64(1e300)
            best = zv
            for fa in range(6):
                ax = a0
                if fa == 1:
                    ax = a1
                if fa == 2:
                    ax = a2
                if fa == 3:
                    ax = b0
                if fa == 4:
                    ax = b1
                if fa == 5:
                    ax = b2
                ov = sat_overlap(ax, a0, a1, a2, b0, b1, b2, ha, hb, d)
                if ov < -margin:
                    sep = 1
                if ov < min_face:
                    min_face = ov
                    best = sat_orient(ax, d)
            min_edge = wp.float64(1e300)
            for ea in range(3):
                ua = a0
                if ea == 1:
                    ua = a1
                if ea == 2:
                    ua = a2
                for eb in range(3):
                    ub = b0
                    if eb == 1:
                        ub = b1
                    if eb == 2:
                        ub = b2
                    ov = sat_overlap(wp.cross(ua, ub), a0, a1, a2, b0, b1, b2,
                                     ha, hb, d)
                    if ov < -margin:
                        sep = 1
                    if ov < min_edge:
                        min_edge = ov
            if sep == 1:
                continue
            normal = best
            pen = wp.min(min_face, min_edge)
            if pen < _ZERO:
                pen = _ZERO

            emitted = int(0)
            for ci in range(8):
                if emitted >= 4:
                    break
                s = signs[ci]
                off = wp.vec3d(s[0] * hb[0], s[1] * hb[1], s[2] * hb[2])
                cw = X[j] + Rb * off
                sd = sd_to_face(cw, Ra, ha, X[i], -normal, margin)
                if sd < margin:
                    pc = -sd
                    if pc < _ZERO:
                        pc = _ZERO          # pen_c = max(0, -sd)
                    pa_w = cw - _HALF * pc * normal
                    pb_w = cw + _HALF * pc * normal
                    ra = wp.transpose(Ra) * (pa_w - X[i])
                    rb = wp.transpose(Rb) * (pb_w - X[j])
                    emit_contact(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory,
                                 c_mu, c_lam, c_jt, cap, i, j, ra, rb, normal,
                                 _ZERO, self_mu)
                    emitted = emitted + 1
            for ci in range(8):
                if emitted >= 4:
                    break
                s = signs[ci]
                off = wp.vec3d(s[0] * ha[0], s[1] * ha[1], s[2] * ha[2])
                cw = X[i] + Ra * off
                sd = sd_to_face(cw, Rb, hb, X[j], normal, margin)
                if sd < margin:
                    pc = -sd
                    if pc < _ZERO:
                        pc = _ZERO
                    pa_w = cw - _HALF * pc * normal
                    pb_w = cw + _HALF * pc * normal
                    ra = wp.transpose(Ra) * (pa_w - X[i])
                    rb = wp.transpose(Rb) * (pb_w - X[j])
                    emit_contact(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory,
                                 c_mu, c_lam, c_jt, cap, i, j, ra, rb, normal,
                                 _ZERO, self_mu)
                    emitted = emitted + 1
            if emitted == 0:
                cw = _HALF * (X[i] + X[j])
                pa_w = cw - _HALF * pen * normal
                pb_w = cw + _HALF * pen * normal
                ra = wp.transpose(Ra) * (pa_w - X[i])
                rb = wp.transpose(Rb) * (pb_w - X[j])
                emit_contact(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory, c_mu,
                             c_lam, c_jt, cap, i, j, ra, rb, normal, _ZERO,
                             self_mu)


# ---- position GS solve: normal → modal → cargo → support (×iters) ----------
@wp.func
def pos_solve_f(
        X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
        invm: wp.array(dtype=wp.float64), invIl: wp.array(dtype=wp.mat33d),
        cnt: wp.array(dtype=wp.int32),
        c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
        c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
        c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
        c_lam: wp.array(dtype=wp.float64),
        modal: int, r: int,
        q: wp.array(dtype=wp.float64), q_n: wp.array(dtype=wp.float64),
        kq: wp.array(dtype=wp.float64), wq: wp.array(dtype=wp.float64),
        dq: wp.array(dtype=wp.float64), lam_q: wp.array(dtype=wp.float64),
        has_cargo: int, ck: int,
        cg_a: wp.array(dtype=wp.float64), cg_an: wp.array(dtype=wp.float64),
        cg_kq: wp.array(dtype=wp.float64), cg_mq: wp.array(dtype=wp.float64),
        cg_dq: wp.array(dtype=wp.float64), cg_lam: wp.array(dtype=wp.float64),
        cg_phi: wp.array(dtype=wp.float64, ndim=3),
        ns: int, sup_bi: wp.array(dtype=wp.int32),
        sup_off: wp.array(dtype=wp.vec3d), sup_yrest: wp.array(dtype=wp.float64),
        sup_Uy: wp.array(dtype=wp.float64, ndim=2),
        sup_lam: wp.array(dtype=wp.float64), sup_pid: wp.array(dtype=wp.int32),
        iters: int, a_tilde: wp.float64, inv_h2: wp.float64, h: wp.float64,
        support_compliance: wp.float64, modal_relax: wp.float64):
    n_c = cnt[0]
    at_sup = support_compliance * inv_h2
    for _it in range(iters):
        # ---- normal contacts (unilateral λ ≥ 0) ----
        for ci in range(n_c):
            a = c_a[ci]
            n = c_n[ci]
            Ra = quat_to_R(Q[a])
            ra_w = Ra * c_ra[ci]
            pa = X[a] + ra_w
            invIa = iIw(Ra, invIl[a])
            b = c_b[ci]
            C = _ZERO
            w = _ZERO
            rb_w = wp.vec3d(_ZERO, _ZERO, _ZERO)
            invIb = zero_mat()
            if b < 0:
                C = pa[1] - c_floory[ci]
                w = gen_inv_mass(invm[a], invIa, ra_w, n)
            else:
                Rb = quat_to_R(Q[b])
                rb_w = Rb * c_rb[ci]
                pb = X[b] + rb_w
                invIb = iIw(Rb, invIl[b])
                C = wp.dot(pa - pb, n)
                w = gen_inv_mass(invm[a], invIa, ra_w, n) \
                    + gen_inv_mass(invm[b], invIb, rb_w, n)
            if C >= _ZERO or w <= _ZERO:
                continue
            dlam = (-C - a_tilde * c_lam[ci]) / (w + a_tilde)
            new = c_lam[ci] + dlam
            if new < _ZERO:
                new = _ZERO
            dlam = new - c_lam[ci]
            c_lam[ci] = new
            p = dlam * n
            apply_pos(X, Q, invm, a, p, ra_w, invIa)
            if b >= 0:
                apply_pos(X, Q, invm, b, -p, rb_w, invIb)

        if modal != 0:
            # ---- modal elastic (per-mode compliant, Macklin §3.5 damped) ----
            for i in range(r):
                ki = kq[i]
                if ki <= _ZERO:
                    continue
                alpha = _ONE / ki
                at = alpha * inv_h2
                wi = wq[i]
                gamma = _ZERO
                if dq[i] > _ZERO:
                    gamma = at * (dq[i] * alpha) * h
                Cdot = q[i] - q_n[i]
                denom = (_ONE + gamma) * wi + at
                dl = (-q[i] - at * lam_q[i] - gamma * Cdot) / denom
                lam_q[i] = lam_q[i] + dl
                q[i] = q[i] + wi * dl

            # ---- cargo elastic (linear per-mode block) ----
            if has_cargo != 0:
                for i in range(ck):
                    ki = cg_kq[i]
                    if ki <= _ZERO:
                        continue
                    alpha = _ONE / ki
                    at = alpha * inv_h2
                    wi = _ZERO
                    if cg_mq[i] > _ZERO:
                        wi = _ONE / cg_mq[i]
                    gamma = _ZERO
                    if cg_dq[i] > _ZERO:
                        gamma = at * (cg_dq[i] * alpha) * h
                    Cdot = cg_a[i] - cg_an[i]
                    denom = (_ONE + gamma) * wi + at
                    dl = (-cg_a[i] - at * cg_lam[i] - gamma * Cdot) / denom
                    cg_lam[i] = cg_lam[i] + dl
                    cg_a[i] = cg_a[i] + wi * dl

            # ---- support rows (unilateral, surface y_rest + U_y·q + cargo flex) ----
            for s in range(ns):
                bi = sup_bi[s]
                R = quat_to_R(Q[bi])
                r_w = R * sup_off[s]
                corner_y = X[bi][1] + r_w[1]
                surf = sup_yrest[s]
                for i in range(r):
                    surf = surf + sup_Uy[s, i] * q[i]
                pid = sup_pid[s]
                has_g = int(0)
                if has_cargo != 0 and pid >= 0:
                    has_g = 1
                    flex = _ZERO
                    for cc in range(ck):
                        ga = R[1, 0] * cg_phi[pid, 0, cc] \
                            + R[1, 1] * cg_phi[pid, 1, cc] \
                            + R[1, 2] * cg_phi[pid, 2, cc]
                        flex = flex + ga * cg_a[cc]
                    surf = surf + flex
                C = corner_y - surf
                if C >= _ZERO and sup_lam[s] == _ZERO:
                    continue
                j_ang = wp.vec3d(-r_w[2], _ZERO, r_w[0])    # cross(r_w, e_y)
                invIw = iIw(R, invIl[bi])
                w = invm[bi] + wp.dot(j_ang, invIw * j_ang)
                for i in range(r):
                    w = w + sup_Uy[s, i] * sup_Uy[s, i] * wq[i]
                if has_g == 1:
                    for cc in range(ck):
                        ga = R[1, 0] * cg_phi[pid, 0, cc] \
                            + R[1, 1] * cg_phi[pid, 1, cc] \
                            + R[1, 2] * cg_phi[pid, 2, cc]
                        mgg = _ZERO
                        if cg_mq[cc] > _ZERO:
                            mgg = ga / cg_mq[cc]
                        w = w + ga * mgg                    # GᵀM⁻¹G
                dlam = (-C - at_sup * sup_lam[s]) / (w + at_sup)
                new = sup_lam[s] + dlam
                if new < _ZERO:
                    new = _ZERO
                dlam = new - sup_lam[s]
                sup_lam[s] = new
                if dlam == _ZERO:
                    continue
                X[bi] = X[bi] + wp.vec3d(_ZERO, invm[bi] * dlam, _ZERO)
                Q[bi] = quat_apply_rotvec(Q[bi], (invIw * j_ang) * dlam)
                for i in range(r):
                    q[i] = q[i] + modal_relax * (-sup_Uy[s, i] * wq[i]) * dlam
                if has_g == 1:
                    for cc in range(ck):
                        ga = R[1, 0] * cg_phi[pid, 0, cc] \
                            + R[1, 1] * cg_phi[pid, 1, cc] \
                            + R[1, 2] * cg_phi[pid, 2, cc]
                        mgg = _ZERO
                        if cg_mq[cc] > _ZERO:
                            mgg = ga / cg_mq[cc]
                        cg_a[cc] = cg_a[cc] + modal_relax * mgg * dlam


@wp.func
def velupd_f(nb: int, X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
             x_prev: wp.array(dtype=wp.vec3d), q_prev: wp.array(dtype=wp.quatd),
             V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
             invm: wp.array(dtype=wp.float64), h: wp.float64):
    """v = (x − x_prev)/h, ω = log(q ⊗ q_prev⁻¹)/h (numpy velocity update)."""
    for i in range(nb):
        if invm[i] != _ZERO:
            V[i] = (X[i] - x_prev[i]) / h
            dqq = qmul(Q[i], qinv(q_prev[i]))
            W[i] = quat_to_rotvec(dqq) / h


@wp.func
def modal_commit_f(q: wp.array(dtype=wp.float64), q_n: wp.array(dtype=wp.float64),
                   qdot: wp.array(dtype=wp.float64),
                   mq: wp.array(dtype=wp.float64), kq: wp.array(dtype=wp.float64),
                   freeze: int, h: wp.float64, r: int,
                   diag: wp.array(dtype=wp.float64)):
    """q̇ⁿ⁺¹ = (q − qⁿ)/h (or 0 if frozen); modal KE/PE diagnostics."""
    ke = _ZERO
    pe = _ZERO
    for i in range(r):
        if freeze != 0:
            qdot[i] = _ZERO
        else:
            qdot[i] = (q[i] - q_n[i]) / h
            ke = ke + qdot[i] * mq[i] * qdot[i]
        pe = pe + q[i] * kq[i] * q[i]
    if freeze != 0:
        diag[1] = _ZERO
    else:
        diag[1] = _HALF * ke
    diag[2] = _HALF * pe


@wp.func
def cargo_commit_f(a: wp.array(dtype=wp.float64), a_n: wp.array(dtype=wp.float64),
                   adot: wp.array(dtype=wp.float64),
                   freeze: int, h: wp.float64, k: int):
    for i in range(k):
        if freeze != 0:
            adot[i] = _ZERO
        else:
            adot[i] = (a[i] - a_n[i]) / h


@wp.func
def velsolve_f(X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
               V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
               invm: wp.array(dtype=wp.float64), invIl: wp.array(dtype=wp.mat33d),
               cnt: wp.array(dtype=wp.int32),
               c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
               c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
               c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
               c_mu: wp.array(dtype=wp.float64), c_lam: wp.array(dtype=wp.float64),
               c_jt: wp.array(dtype=wp.vec3d),
               ns: int, sup_bi: wp.array(dtype=wp.int32),
               sup_off: wp.array(dtype=wp.vec3d),
               sup_lam: wp.array(dtype=wp.float64),
               sup_mu: wp.array(dtype=wp.float64),
               sup_jt: wp.array(dtype=wp.vec3d),
               iters: int, fric_static: wp.float64, h: wp.float64,
               diag: wp.array(dtype=wp.float64)):
    """Inelastic normal restitution (e=0) + sequential-impulse Coulomb friction
    (|j_t| ≤ μ λ_n/h) for contacts AND support rows; then max-penetration
    diagnostic (numpy `_solve_velocity` / `_solve_velocity_support`)."""
    n_c = cnt[0]
    for s in range(ns):                 # reset support friction accumulator
        sup_jt[s] = wp.vec3d(_ZERO, _ZERO, _ZERO)
    up = wp.vec3d(_ZERO, _ONE, _ZERO)
    for _it in range(iters):
        for ci in range(n_c):
            if c_lam[ci] <= _ZERO:
                continue
            a = c_a[ci]
            n = c_n[ci]
            Ra = quat_to_R(Q[a])
            ra_w = Ra * c_ra[ci]
            invIa = iIw(Ra, invIl[a])
            b = c_b[ci]
            rb_w = wp.vec3d(_ZERO, _ZERO, _ZERO)
            invIb = zero_mat()
            if b >= 0:
                Rb = quat_to_R(Q[b])
                rb_w = Rb * c_rb[ci]
                invIb = iIw(Rb, invIl[b])
            vp = V[a] + wp.cross(W[a], ra_w)
            if b >= 0:
                vp = vp - (V[b] + wp.cross(W[b], rb_w))
            vn = wp.dot(vp, n)
            wn = gen_inv_mass(invm[a], invIa, ra_w, n)
            if b >= 0:
                wn = wn + gen_inv_mass(invm[b], invIb, rb_w, n)
            if wn > _ZERO and wp.abs(vn) > wp.float64(1e-12):
                P = (-vn / wn) * n
                V[a] = V[a] + invm[a] * P
                W[a] = W[a] + invIa * wp.cross(ra_w, P)
                if b >= 0:
                    V[b] = V[b] - invm[b] * P
                    W[b] = W[b] - invIb * wp.cross(rb_w, P)
            mu = c_mu[ci]
            if mu <= _ZERO:
                continue
            vp = V[a] + wp.cross(W[a], ra_w)
            if b >= 0:
                vp = vp - (V[b] + wp.cross(W[b], rb_w))
            v_t = vp - wp.dot(vp, n) * n
            mag = wp.length(v_t)
            if mag < wp.float64(1e-12):
                continue
            t = v_t / mag
            wt = gen_inv_mass(invm[a], invIa, ra_w, t)
            if b >= 0:
                wt = wt + gen_inv_mass(invm[b], invIb, rb_w, t)
            if wt <= _ZERO:
                continue
            new_jt = c_jt[ci] + (-mag / wt) * t
            j_max = mu * fric_static * c_lam[ci] / h
            njt = wp.length(new_jt)
            if njt > j_max:
                new_jt = new_jt * (j_max / njt)
            dP = new_jt - c_jt[ci]
            c_jt[ci] = new_jt
            V[a] = V[a] + invm[a] * dP
            W[a] = W[a] + invIa * wp.cross(ra_w, dP)
            if b >= 0:
                V[b] = V[b] - invm[b] * dP
                W[b] = W[b] - invIb * wp.cross(rb_w, dP)
        # support tangential Coulomb friction (numpy `_solve_velocity_support`):
        # normal = e_y, friction-only (no e=0 restitution — keep soft modal q̇).
        for s in range(ns):
            mu_s = sup_mu[s]
            if sup_lam[s] <= _ZERO or mu_s <= _ZERO:
                continue
            bi = sup_bi[s]
            if invm[bi] == _ZERO:
                continue
            Rs = quat_to_R(Q[bi])
            r_w = Rs * sup_off[s]
            invIs = iIw(Rs, invIl[bi])
            vps = V[bi] + wp.cross(W[bi], r_w)
            vts = vps - wp.dot(vps, up) * up
            mags = wp.length(vts)
            if mags < wp.float64(1e-12):
                continue
            ts = vts / mags
            wts = gen_inv_mass(invm[bi], invIs, r_w, ts)
            if wts <= _ZERO:
                continue
            new_js = sup_jt[s] + (-mags / wts) * ts
            jmax_s = mu_s * fric_static * sup_lam[s] / h
            njs = wp.length(new_js)
            if njs > jmax_s:
                new_js = new_js * (jmax_s / njs)
            dPs = new_js - sup_jt[s]
            sup_jt[s] = new_js
            V[bi] = V[bi] + invm[bi] * dPs
            W[bi] = W[bi] + invIs * wp.cross(r_w, dPs)

    maxpen = _ZERO
    for ci in range(n_c):
        a = c_a[ci]
        Ra = quat_to_R(Q[a])
        pa = X[a] + Ra * c_ra[ci]
        b = c_b[ci]
        pen = _ZERO
        if b < 0:
            pen = c_floory[ci] - pa[1]
        else:
            Rb = quat_to_R(Q[b])
            pb = X[b] + Rb * c_rb[ci]
            pen = wp.dot(pb - pa, c_n[ci])
        if pen < _ZERO:
            pen = _ZERO
        if pen > maxpen:
            maxpen = pen
    diag[0] = maxpen


# ===========================================================================
# Fused phase kernels (dim=1) — the captured launch units. Two per substep.
# ===========================================================================
@wp.kernel
def k_pos_phase(
        nb: int, modal: int, has_cargo: int,
        X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
        V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
        x_prev: wp.array(dtype=wp.vec3d), q_prev: wp.array(dtype=wp.quatd),
        invm: wp.array(dtype=wp.float64), invIl: wp.array(dtype=wp.mat33d),
        hE: wp.array(dtype=wp.vec3d), g: wp.vec3d, h: wp.float64,
        # modal predict + solve
        r: int, q: wp.array(dtype=wp.float64), qdot: wp.array(dtype=wp.float64),
        q_n: wp.array(dtype=wp.float64), grav: wp.array(dtype=wp.float64),
        kq: wp.array(dtype=wp.float64), wq: wp.array(dtype=wp.float64),
        dq: wp.array(dtype=wp.float64), lam_q: wp.array(dtype=wp.float64),
        # cargo predict + solve
        ck: int, n_lam: int,
        cg_a: wp.array(dtype=wp.float64), cg_adot: wp.array(dtype=wp.float64),
        cg_an: wp.array(dtype=wp.float64), cg_kq: wp.array(dtype=wp.float64),
        cg_mq: wp.array(dtype=wp.float64), cg_dq: wp.array(dtype=wp.float64),
        cg_lam: wp.array(dtype=wp.float64),
        cg_phi: wp.array(dtype=wp.float64, ndim=3),
        # contact gen
        signs: wp.array(dtype=wp.vec3d), fl_bi: wp.array(dtype=wp.int32),
        fl_y: wp.array(dtype=wp.float64), fl_mu: wp.array(dtype=wp.float64),
        n_floor: int, self_collide: int, self_mu: wp.float64,
        margin: wp.float64, cap: int, cur: wp.array(dtype=wp.int32),
        c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
        c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
        c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
        c_mu: wp.array(dtype=wp.float64), c_lam: wp.array(dtype=wp.float64),
        c_jt: wp.array(dtype=wp.vec3d),
        # support
        ns: int, sup_bi: wp.array(dtype=wp.int32),
        sup_off: wp.array(dtype=wp.vec3d), sup_yrest: wp.array(dtype=wp.float64),
        sup_Uy: wp.array(dtype=wp.float64, ndim=2),
        sup_lam: wp.array(dtype=wp.float64), sup_pid: wp.array(dtype=wp.int32),
        # scalars
        freeze: int, iters: int, a_tilde: wp.float64, inv_h2: wp.float64,
        support_compliance: wp.float64, modal_relax: wp.float64):
    """Predict (bodies + modal + cargo) → reset support λ → generate contacts →
    position GS solve. One launch per substep."""
    predict_bodies_f(nb, X, Q, V, W, x_prev, q_prev, invm, g, h)
    if modal != 0:
        predict_modal_f(q, qdot, q_n, grav, lam_q, freeze, h, r)
        if has_cargo != 0:
            predict_cargo_f(cg_a, cg_adot, cg_an, cg_lam, freeze, h, ck, n_lam)
        reset_support_f(sup_lam, ns)
    gen_contacts_f(X, Q, invm, hE, signs, fl_bi, fl_y, fl_mu, n_floor, nb,
                   self_collide, self_mu, margin, cap, cur, c_a, c_b, c_ra,
                   c_rb, c_n, c_floory, c_mu, c_lam, c_jt)
    pos_solve_f(X, Q, invm, invIl, cur, c_a, c_b, c_ra, c_rb, c_n, c_floory,
                c_lam, modal, r, q, q_n, kq, wq, dq, lam_q, has_cargo, ck,
                cg_a, cg_an, cg_kq, cg_mq, cg_dq, cg_lam, cg_phi, ns, sup_bi,
                sup_off, sup_yrest, sup_Uy, sup_lam, sup_pid, iters, a_tilde,
                inv_h2, h, support_compliance, modal_relax)


@wp.kernel
def k_vel_phase(
        nb: int, modal: int, has_cargo: int,
        X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
        V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
        x_prev: wp.array(dtype=wp.vec3d), q_prev: wp.array(dtype=wp.quatd),
        invm: wp.array(dtype=wp.float64), invIl: wp.array(dtype=wp.mat33d),
        h: wp.float64,
        r: int, q: wp.array(dtype=wp.float64), q_n: wp.array(dtype=wp.float64),
        qdot: wp.array(dtype=wp.float64), mq: wp.array(dtype=wp.float64),
        kq: wp.array(dtype=wp.float64),
        ck: int, cg_a: wp.array(dtype=wp.float64),
        cg_an: wp.array(dtype=wp.float64), cg_adot: wp.array(dtype=wp.float64),
        cnt: wp.array(dtype=wp.int32),
        c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
        c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
        c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
        c_mu: wp.array(dtype=wp.float64), c_lam: wp.array(dtype=wp.float64),
        c_jt: wp.array(dtype=wp.vec3d),
        ns: int, sup_bi: wp.array(dtype=wp.int32),
        sup_off: wp.array(dtype=wp.vec3d), sup_lam: wp.array(dtype=wp.float64),
        sup_mu: wp.array(dtype=wp.float64), sup_jt: wp.array(dtype=wp.vec3d),
        freeze: int, iters: int, fric_static: wp.float64,
        diag: wp.array(dtype=wp.float64)):
    """Velocity-from-Δx → modal/cargo commit → velocity GS solve + diagnostics.
    One launch per substep."""
    velupd_f(nb, X, Q, x_prev, q_prev, V, W, invm, h)
    if modal != 0:
        modal_commit_f(q, q_n, qdot, mq, kq, freeze, h, r, diag)
        if has_cargo != 0:
            cargo_commit_f(cg_a, cg_an, cg_adot, freeze, h, ck)
    velsolve_f(X, Q, V, W, invm, invIl, cnt, c_a, c_b, c_ra, c_rb, c_n,
               c_floory, c_mu, c_lam, c_jt, ns, sup_bi, sup_off, sup_lam,
               sup_mu, sup_jt, iters, fric_static, h, diag)


# ===========================================================================
# PARALLEL device path (Jacobi + Macklin constraint-averaging).
#
# The dim=1 phase kernels above preserve exact serial-GS order for bit-parity
# with the numpy reference. This path instead exposes the per-constraint
# parallelism the GPU needs: in each iteration every constraint projects from
# the SAME start-of-iteration state, accumulates its body / modal correction
# into a scratch buffer via atomics, and a per-body apply divides the summed
# correction by the number of constraints touching that body (Macklin et al.
# 2014, "Unified Particle Physics", §averaged constraint projection — the
# stable parallel relaxation). The constraints, compliances and forces are
# byte-for-byte the serial ones; only the iteration SCHEDULE changes (serial
# Gauss–Seidel → averaged Jacobi), the same deviation the colored AVBD primal
# already takes. Launch dims are static (fixed pool capacities, early-out past
# the live count) so the whole substep captures into one CUDA graph.
#
# Accumulators are flat float64[3*nb] / float64[r] / float64[ck] so every
# scatter is a scalar wp.atomic_add (hardware fp64 atomics on sm_60+; the
# vec3d-atomic path is intentionally avoided). The apply kernels zero the
# accumulator they consume, so no separate clear launch is needed.
# ===========================================================================
@wp.func
def emit_atomic(cur: wp.array(dtype=wp.int32),
                c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
                c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
                c_n: wp.array(dtype=wp.vec3d),
                c_floory: wp.array(dtype=wp.float64),
                c_mu: wp.array(dtype=wp.float64),
                c_lam: wp.array(dtype=wp.float64),
                c_jt: wp.array(dtype=wp.vec3d), cap: int,
                a: int, b: int, ra: wp.vec3d, rb: wp.vec3d, n: wp.vec3d,
                floor_y: wp.float64, mu: wp.float64):
    """Append a contact with an ATOMIC slot reservation (parallel-safe variant of
    emit_contact). Contact ORDER is nondeterministic — fine, the solve is Jacobi."""
    idx = wp.atomic_add(cur, 0, 1)
    if idx >= cap:
        return
    c_a[idx] = a
    c_b[idx] = b
    c_ra[idx] = ra
    c_rb[idx] = rb
    c_n[idx] = n
    c_floory[idx] = floor_y
    c_mu[idx] = mu
    c_lam[idx] = _ZERO
    c_jt[idx] = wp.vec3d(_ZERO, _ZERO, _ZERO)


@wp.kernel
def pk_gen_floor(X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
                 hE: wp.array(dtype=wp.vec3d), signs: wp.array(dtype=wp.vec3d),
                 fl_bi: wp.array(dtype=wp.int32), fl_y: wp.array(dtype=wp.float64),
                 fl_mu: wp.array(dtype=wp.float64), n_floor: int,
                 margin: wp.float64, cap: int, cur: wp.array(dtype=wp.int32),
                 c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
                 c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
                 c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
                 c_mu: wp.array(dtype=wp.float64), c_lam: wp.array(dtype=wp.float64),
                 c_jt: wp.array(dtype=wp.vec3d)):
    """Floor-corner contacts, one thread per floor registration (dim=n_floor)."""
    f = wp.tid()
    if f >= n_floor:
        return
    bi = fl_bi[f]
    fy = fl_y[f]
    mu = fl_mu[f]
    R = quat_to_R(Q[bi])
    he = hE[bi]
    up = wp.vec3d(_ZERO, _ONE, _ZERO)
    zv = wp.vec3d(_ZERO, _ZERO, _ZERO)
    for ci in range(8):
        s = signs[ci]
        off = wp.vec3d(s[0] * he[0], s[1] * he[1], s[2] * he[2])
        cw = X[bi] + R * off
        if cw[1] - fy < margin:
            emit_atomic(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory, c_mu, c_lam,
                        c_jt, cap, bi, -1, off, zv, up, fy, mu)


@wp.kernel
def pk_gen_boxbox(X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
                  invm: wp.array(dtype=wp.float64), hE: wp.array(dtype=wp.vec3d),
                  signs: wp.array(dtype=wp.vec3d), nb: int, self_mu: wp.float64,
                  margin: wp.float64, cap: int, cur: wp.array(dtype=wp.int32),
                  c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
                  c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
                  c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
                  c_mu: wp.array(dtype=wp.float64), c_lam: wp.array(dtype=wp.float64),
                  c_jt: wp.array(dtype=wp.vec3d)):
    """SAT box-box for ONE body pair (i,j), one thread per pair (dim=nb*nb,
    i<j active). Body of numpy `_box_box`; ATOMIC emit. This is the per-step hot
    spot — the O(nb²) SAT was the dim=1 fixed cost; here it fans over the pairs."""
    tid = wp.tid()
    i = tid / nb
    j = tid % nb
    if i >= j:
        return
    if invm[i] == _ZERO and invm[j] == _ZERO:
        return
    Ra = quat_to_R(Q[i])
    Rb = quat_to_R(Q[j])
    ha = hE[i]
    hb = hE[j]
    d = X[j] - X[i]
    a0 = colv(Ra, 0)
    a1 = colv(Ra, 1)
    a2 = colv(Ra, 2)
    b0 = colv(Rb, 0)
    b1 = colv(Rb, 1)
    b2 = colv(Rb, 2)
    zv = wp.vec3d(_ZERO, _ZERO, _ZERO)
    sep = int(0)
    min_face = wp.float64(1e300)
    best = zv
    for fa in range(6):
        ax = a0
        if fa == 1:
            ax = a1
        if fa == 2:
            ax = a2
        if fa == 3:
            ax = b0
        if fa == 4:
            ax = b1
        if fa == 5:
            ax = b2
        ov = sat_overlap(ax, a0, a1, a2, b0, b1, b2, ha, hb, d)
        if ov < -margin:
            sep = 1
        if ov < min_face:
            min_face = ov
            best = sat_orient(ax, d)
    min_edge = wp.float64(1e300)
    for ea in range(3):
        ua = a0
        if ea == 1:
            ua = a1
        if ea == 2:
            ua = a2
        for eb in range(3):
            ub = b0
            if eb == 1:
                ub = b1
            if eb == 2:
                ub = b2
            ov = sat_overlap(wp.cross(ua, ub), a0, a1, a2, b0, b1, b2, ha, hb, d)
            if ov < -margin:
                sep = 1
            if ov < min_edge:
                min_edge = ov
    if sep == 1:
        return
    normal = best
    pen = wp.min(min_face, min_edge)
    if pen < _ZERO:
        pen = _ZERO
    emitted = int(0)
    for ci in range(8):
        if emitted >= 4:
            break
        s = signs[ci]
        off = wp.vec3d(s[0] * hb[0], s[1] * hb[1], s[2] * hb[2])
        cw = X[j] + Rb * off
        sd = sd_to_face(cw, Ra, ha, X[i], -normal, margin)
        if sd < margin:
            pc = -sd
            if pc < _ZERO:
                pc = _ZERO
            pa_w = cw - _HALF * pc * normal
            pb_w = cw + _HALF * pc * normal
            ra = wp.transpose(Ra) * (pa_w - X[i])
            rb = wp.transpose(Rb) * (pb_w - X[j])
            emit_atomic(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory, c_mu, c_lam,
                        c_jt, cap, i, j, ra, rb, normal, _ZERO, self_mu)
            emitted = emitted + 1
    for ci in range(8):
        if emitted >= 4:
            break
        s = signs[ci]
        off = wp.vec3d(s[0] * ha[0], s[1] * ha[1], s[2] * ha[2])
        cw = X[i] + Ra * off
        sd = sd_to_face(cw, Rb, hb, X[j], normal, margin)
        if sd < margin:
            pc = -sd
            if pc < _ZERO:
                pc = _ZERO
            pa_w = cw - _HALF * pc * normal
            pb_w = cw + _HALF * pc * normal
            ra = wp.transpose(Ra) * (pa_w - X[i])
            rb = wp.transpose(Rb) * (pb_w - X[j])
            emit_atomic(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory, c_mu, c_lam,
                        c_jt, cap, i, j, ra, rb, normal, _ZERO, self_mu)
            emitted = emitted + 1
    if emitted == 0:
        cw = _HALF * (X[i] + X[j])
        pa_w = cw - _HALF * pen * normal
        pb_w = cw + _HALF * pen * normal
        ra = wp.transpose(Ra) * (pa_w - X[i])
        rb = wp.transpose(Rb) * (pb_w - X[j])
        emit_atomic(cur, c_a, c_b, c_ra, c_rb, c_n, c_floory, c_mu, c_lam,
                    c_jt, cap, i, j, ra, rb, normal, _ZERO, self_mu)


@wp.kernel
def pk_prep(nb: int, modal: int, has_cargo: int,
           X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
           V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
           x_prev: wp.array(dtype=wp.vec3d), q_prev: wp.array(dtype=wp.quatd),
           invm: wp.array(dtype=wp.float64), hE: wp.array(dtype=wp.vec3d),
           g: wp.vec3d, h: wp.float64,
           r: int, q: wp.array(dtype=wp.float64), qdot: wp.array(dtype=wp.float64),
           q_n: wp.array(dtype=wp.float64), grav: wp.array(dtype=wp.float64),
           lam_q: wp.array(dtype=wp.float64),
           ck: int, n_lam: int, cg_a: wp.array(dtype=wp.float64),
           cg_adot: wp.array(dtype=wp.float64), cg_an: wp.array(dtype=wp.float64),
           cg_lam: wp.array(dtype=wp.float64),
           signs: wp.array(dtype=wp.vec3d), fl_bi: wp.array(dtype=wp.int32),
           fl_y: wp.array(dtype=wp.float64), fl_mu: wp.array(dtype=wp.float64),
           n_floor: int, self_collide: int, self_mu: wp.float64,
           margin: wp.float64, cap: int, cur: wp.array(dtype=wp.int32),
           c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
           c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
           c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
           c_mu: wp.array(dtype=wp.float64), c_lam: wp.array(dtype=wp.float64),
           c_jt: wp.array(dtype=wp.vec3d), ns: int,
           sup_lam: wp.array(dtype=wp.float64), freeze: int):
    """Inertial predict (bodies + modal + cargo) → reset support λ → reset the
    contact counter. dim=1 (predict is O(nb) — cheap); contact GENERATION is the
    separate parallel pk_gen_floor / pk_gen_boxbox launches (the O(nb²) SAT was
    the dominant per-step fixed cost in the old dim=1 prep)."""
    predict_bodies_f(nb, X, Q, V, W, x_prev, q_prev, invm, g, h)
    if modal != 0:
        predict_modal_f(q, qdot, q_n, grav, lam_q, freeze, h, r)
        if has_cargo != 0:
            predict_cargo_f(cg_a, cg_adot, cg_an, cg_lam, freeze, h, ck, n_lam)
        reset_support_f(sup_lam, ns)
    cur[0] = 0


@wp.kernel
def pk_count_deg(cnt: wp.array(dtype=wp.int32),
                 c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
                 ns: int, sup_bi: wp.array(dtype=wp.int32),
                 nb: int, deg: wp.array(dtype=wp.float64)):
    """deg[i] = #constraints (contacts + support rows) touching body i. dim=1,
    once per substep — the constraint set is constant across the iter loop."""
    for i in range(nb):
        deg[i] = _ZERO
    n_c = cnt[0]
    for ci in range(n_c):
        deg[c_a[ci]] = deg[c_a[ci]] + _ONE
        b = c_b[ci]
        if b >= 0:
            deg[b] = deg[b] + _ONE
    for s in range(ns):
        deg[sup_bi[s]] = deg[sup_bi[s]] + _ONE


@wp.kernel
def pk_contact_jacobi(
        X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
        invm: wp.array(dtype=wp.float64), invIl: wp.array(dtype=wp.mat33d),
        cnt: wp.array(dtype=wp.int32),
        c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
        c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
        c_n: wp.array(dtype=wp.vec3d), c_floory: wp.array(dtype=wp.float64),
        c_lam: wp.array(dtype=wp.float64), a_tilde: wp.float64,
        acc_dp: wp.array(dtype=wp.float64), acc_dr: wp.array(dtype=wp.float64)):
    """One normal-contact projection (numpy `_project_normal`), scattering the
    body correction into the Jacobi accumulators. dim=cap; early-out past cur."""
    ci = wp.tid()
    if ci >= cnt[0]:
        return
    a = c_a[ci]
    n = c_n[ci]
    Ra = quat_to_R(Q[a])
    ra_w = Ra * c_ra[ci]
    pa = X[a] + ra_w
    invIa = iIw(Ra, invIl[a])
    b = c_b[ci]
    C = _ZERO
    w = _ZERO
    rb_w = wp.vec3d(_ZERO, _ZERO, _ZERO)
    invIb = zero_mat()
    if b < 0:
        C = pa[1] - c_floory[ci]
        w = gen_inv_mass(invm[a], invIa, ra_w, n)
    else:
        Rb = quat_to_R(Q[b])
        rb_w = Rb * c_rb[ci]
        pb = X[b] + rb_w
        invIb = iIw(Rb, invIl[b])
        C = wp.dot(pa - pb, n)
        w = gen_inv_mass(invm[a], invIa, ra_w, n) \
            + gen_inv_mass(invm[b], invIb, rb_w, n)
    if C >= _ZERO or w <= _ZERO:
        return
    dlam = (-C - a_tilde * c_lam[ci]) / (w + a_tilde)
    new = c_lam[ci] + dlam
    if new < _ZERO:
        new = _ZERO
    dlam = new - c_lam[ci]
    c_lam[ci] = new
    p = dlam * n
    dpa = invm[a] * p
    dra = invIa * wp.cross(ra_w, p)
    wp.atomic_add(acc_dp, 3 * a + 0, dpa[0])
    wp.atomic_add(acc_dp, 3 * a + 1, dpa[1])
    wp.atomic_add(acc_dp, 3 * a + 2, dpa[2])
    wp.atomic_add(acc_dr, 3 * a + 0, dra[0])
    wp.atomic_add(acc_dr, 3 * a + 1, dra[1])
    wp.atomic_add(acc_dr, 3 * a + 2, dra[2])
    if b >= 0:
        pb_imp = -p
        dpb = invm[b] * pb_imp
        drb = invIb * wp.cross(rb_w, pb_imp)
        wp.atomic_add(acc_dp, 3 * b + 0, dpb[0])
        wp.atomic_add(acc_dp, 3 * b + 1, dpb[1])
        wp.atomic_add(acc_dp, 3 * b + 2, dpb[2])
        wp.atomic_add(acc_dr, 3 * b + 0, drb[0])
        wp.atomic_add(acc_dr, 3 * b + 1, drb[1])
        wp.atomic_add(acc_dr, 3 * b + 2, drb[2])


@wp.kernel
def pk_modal_elastic(r: int, q: wp.array(dtype=wp.float64),
                     q_n: wp.array(dtype=wp.float64),
                     kq: wp.array(dtype=wp.float64),
                     wq: wp.array(dtype=wp.float64),
                     dq: wp.array(dtype=wp.float64),
                     lam_q: wp.array(dtype=wp.float64),
                     inv_h2: wp.float64, h: wp.float64,
                     acc_dq: wp.array(dtype=wp.float64)):
    """Per-mode compliant modal-elastic constraint (numpy `_project_modal_elastic`).
    Independent per mode → one thread per mode. Adds onto acc_dq (separate launch
    from the support scatter, so the read-modify-write of acc_dq[i] is race-free)."""
    i = wp.tid()
    if i >= r:
        return
    ki = kq[i]
    if ki <= _ZERO:
        return
    alpha = _ONE / ki
    at = alpha * inv_h2
    wi = wq[i]
    gamma = _ZERO
    if dq[i] > _ZERO:
        gamma = at * (dq[i] * alpha) * h
    Cdot = q[i] - q_n[i]
    denom = (_ONE + gamma) * wi + at
    dl = (-q[i] - at * lam_q[i] - gamma * Cdot) / denom
    lam_q[i] = lam_q[i] + dl
    acc_dq[i] = acc_dq[i] + wi * dl


@wp.kernel
def pk_cargo_elastic(ck: int, cg_a: wp.array(dtype=wp.float64),
                     cg_an: wp.array(dtype=wp.float64),
                     cg_kq: wp.array(dtype=wp.float64),
                     cg_mq: wp.array(dtype=wp.float64),
                     cg_dq: wp.array(dtype=wp.float64),
                     cg_lam: wp.array(dtype=wp.float64),
                     inv_h2: wp.float64, h: wp.float64,
                     acc_da: wp.array(dtype=wp.float64)):
    """Linear per-mode cargo-elastic block (numpy `_project_cargo_elastic`)."""
    i = wp.tid()
    if i >= ck:
        return
    ki = cg_kq[i]
    if ki <= _ZERO:
        return
    alpha = _ONE / ki
    at = alpha * inv_h2
    wi = _ZERO
    if cg_mq[i] > _ZERO:
        wi = _ONE / cg_mq[i]
    gamma = _ZERO
    if cg_dq[i] > _ZERO:
        gamma = at * (cg_dq[i] * alpha) * h
    Cdot = cg_a[i] - cg_an[i]
    denom = (_ONE + gamma) * wi + at
    dl = (-cg_a[i] - at * cg_lam[i] - gamma * Cdot) / denom
    cg_lam[i] = cg_lam[i] + dl
    acc_da[i] = acc_da[i] + wi * dl


@wp.kernel
def pk_support_jacobi(
        X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
        invm: wp.array(dtype=wp.float64), invIl: wp.array(dtype=wp.mat33d),
        ns: int, sup_bi: wp.array(dtype=wp.int32),
        sup_off: wp.array(dtype=wp.vec3d), sup_yrest: wp.array(dtype=wp.float64),
        sup_Uy: wp.array(dtype=wp.float64, ndim=2),
        sup_lam: wp.array(dtype=wp.float64), sup_pid: wp.array(dtype=wp.int32),
        r: int, q: wp.array(dtype=wp.float64), wq: wp.array(dtype=wp.float64),
        mq: wp.array(dtype=wp.float64),
        has_cargo: int, ck: int, cg_a: wp.array(dtype=wp.float64),
        cg_mq: wp.array(dtype=wp.float64),
        cg_phi: wp.array(dtype=wp.float64, ndim=3),
        at_sup: wp.float64, modal_relax: wp.float64,
        acc_dp: wp.array(dtype=wp.float64), acc_dr: wp.array(dtype=wp.float64),
        acc_dq: wp.array(dtype=wp.float64), acc_da: wp.array(dtype=wp.float64),
        acc_dqn: wp.array(dtype=wp.float64), acc_dan: wp.array(dtype=wp.float64)):
    """One support-row projection (numpy `_project_support`): couples the rigid
    6-DOF (e_y + j_ang), the shared modal q (∂C/∂q = −U_y, under-relaxed) and the
    cargo a. Body correction → acc_dp/acc_dr (averaged later); q/a → acc_dq/acc_da
    (Jacobi over the support rows — the shared-q reduction). dim=ns."""
    s = wp.tid()
    if s >= ns:
        return
    bi = sup_bi[s]
    R = quat_to_R(Q[bi])
    r_w = R * sup_off[s]
    corner_y = X[bi][1] + r_w[1]
    surf = sup_yrest[s]
    for i in range(r):
        surf = surf + sup_Uy[s, i] * q[i]
    pid = sup_pid[s]
    has_g = int(0)
    if has_cargo != 0 and pid >= 0:
        has_g = 1
        flex = _ZERO
        for cc in range(ck):
            ga = R[1, 0] * cg_phi[pid, 0, cc] + R[1, 1] * cg_phi[pid, 1, cc] \
                + R[1, 2] * cg_phi[pid, 2, cc]
            flex = flex + ga * cg_a[cc]
        surf = surf + flex
    C = corner_y - surf
    if C >= _ZERO and sup_lam[s] == _ZERO:
        return
    j_ang = wp.vec3d(-r_w[2], _ZERO, r_w[0])
    invIw = iIw(R, invIl[bi])
    w = invm[bi] + wp.dot(j_ang, invIw * j_ang)
    for i in range(r):
        w = w + sup_Uy[s, i] * sup_Uy[s, i] * wq[i]
    if has_g == 1:
        for cc in range(ck):
            ga = R[1, 0] * cg_phi[pid, 0, cc] + R[1, 1] * cg_phi[pid, 1, cc] \
                + R[1, 2] * cg_phi[pid, 2, cc]
            mgg = _ZERO
            if cg_mq[cc] > _ZERO:
                mgg = ga / cg_mq[cc]
            w = w + ga * mgg
    dlam = (-C - at_sup * sup_lam[s]) / (w + at_sup)
    new = sup_lam[s] + dlam
    if new < _ZERO:
        new = _ZERO
    dlam = new - sup_lam[s]
    sup_lam[s] = new
    if dlam == _ZERO:
        return
    wp.atomic_add(acc_dp, 3 * bi + 1, invm[bi] * dlam)   # body normal (e_y)
    dr = (invIw * j_ang) * dlam
    wp.atomic_add(acc_dr, 3 * bi + 0, dr[0])
    wp.atomic_add(acc_dr, 3 * bi + 1, dr[1])
    wp.atomic_add(acc_dr, 3 * bi + 2, dr[2])
    # accumulate the support→q/a coupling AND count this active row per mode, so
    # the apply can average (÷ active-row count) — without it the sum over many
    # rows overshoots the stiff modal q and the parallel path diverges.
    # Per-mode under-relaxation by mq (= 1/impedance-gain g; the modes are
    # mass-normalized so mq=1 at g=1): the drive ∝ wq = g, so high impedance
    # over-drives q and the (non-self-limiting) Jacobi sum diverges where serial
    # GS survives. Scaling by min(1,mq) cancels the g over-drive — DEFAULT
    # (g=1 ⇒ mq=1) is unchanged; the fixed point (C=0 surface) is relaxation-
    # independent, so only the convergence rate drops at high g, not the physics.
    for i in range(r):
        mri = modal_relax
        if mq[i] < _ONE:
            mri = modal_relax * mq[i]
        wp.atomic_add(acc_dq, i, mri * (-sup_Uy[s, i] * wq[i]) * dlam)
        wp.atomic_add(acc_dqn, i, _ONE)
    if has_g == 1:
        for cc in range(ck):
            ga = R[1, 0] * cg_phi[pid, 0, cc] + R[1, 1] * cg_phi[pid, 1, cc] \
                + R[1, 2] * cg_phi[pid, 2, cc]
            mgg = _ZERO
            if cg_mq[cc] > _ZERO:
                mgg = ga / cg_mq[cc]
            wp.atomic_add(acc_da, cc, modal_relax * mgg * dlam)
            wp.atomic_add(acc_dan, cc, _ONE)


@wp.kernel
def pk_apply_body(nb: int, X: wp.array(dtype=wp.vec3d),
                  Q: wp.array(dtype=wp.quatd), invm: wp.array(dtype=wp.float64),
                  deg: wp.array(dtype=wp.float64),
                  relax: wp.float64,
                  acc_dp: wp.array(dtype=wp.float64),
                  acc_dr: wp.array(dtype=wp.float64)):
    """Apply the averaged Jacobi correction X += ω·Σδx/deg, Q ← integrate(Q, ...),
    then zero the accumulator for the next iteration. `relax` is the SOR factor."""
    i = wp.tid()
    if i >= nb:
        return
    if invm[i] != _ZERO:
        d = deg[i]
        if d < _ONE:
            d = _ONE
        f = relax / d
        X[i] = X[i] + wp.vec3d(acc_dp[3 * i + 0] * f, acc_dp[3 * i + 1] * f,
                               acc_dp[3 * i + 2] * f)
        Q[i] = quat_apply_rotvec(Q[i], wp.vec3d(acc_dr[3 * i + 0] * f,
                                                acc_dr[3 * i + 1] * f,
                                                acc_dr[3 * i + 2] * f))
    acc_dp[3 * i + 0] = _ZERO
    acc_dp[3 * i + 1] = _ZERO
    acc_dp[3 * i + 2] = _ZERO
    acc_dr[3 * i + 0] = _ZERO
    acc_dr[3 * i + 1] = _ZERO
    acc_dr[3 * i + 2] = _ZERO


@wp.kernel
def pk_apply_q(r: int, q: wp.array(dtype=wp.float64),
               acc_dq: wp.array(dtype=wp.float64)):
    """q += Σδq (elastic exact + support Jacobi), then zero the accumulator."""
    i = wp.tid()
    if i >= r:
        return
    q[i] = q[i] + acc_dq[i]
    acc_dq[i] = _ZERO


@wp.kernel
def pk_apply_a(ck: int, cg_a: wp.array(dtype=wp.float64),
               acc_da: wp.array(dtype=wp.float64)):
    """a += Σδa, then zero the accumulator."""
    i = wp.tid()
    if i >= ck:
        return
    cg_a[i] = cg_a[i] + acc_da[i]
    acc_da[i] = _ZERO


@wp.kernel
def pk_modes_elastic(r: int, ck: int, has_cargo: int,
                     q: wp.array(dtype=wp.float64), q_n: wp.array(dtype=wp.float64),
                     kq: wp.array(dtype=wp.float64), wq: wp.array(dtype=wp.float64),
                     dq: wp.array(dtype=wp.float64),
                     lam_q: wp.array(dtype=wp.float64),
                     cg_a: wp.array(dtype=wp.float64),
                     cg_an: wp.array(dtype=wp.float64),
                     cg_kq: wp.array(dtype=wp.float64),
                     cg_mq: wp.array(dtype=wp.float64),
                     cg_dq: wp.array(dtype=wp.float64),
                     cg_lam: wp.array(dtype=wp.float64),
                     inv_h2: wp.float64, h: wp.float64,
                     acc_dq: wp.array(dtype=wp.float64),
                     acc_da: wp.array(dtype=wp.float64)):
    """Fused per-mode elastic: modal (i<r) + cargo (i<ck) in ONE launch
    (dim=max(r,ck)) — both are independent per-mode 1-DOF compliant solves
    (numpy `_project_modal_elastic` / `_project_cargo_elastic`). Cuts a launch
    per iteration vs the separate pk_modal_elastic + pk_cargo_elastic."""
    # Elastic is one constraint per mode (independent) → exact, applied DIRECTLY
    # to q / a (no averaging). Runs before the support scatter so support reads
    # the elastic-updated q (matches the serial elastic→support order). Only the
    # shared-q/a SUPPORT coupling goes through the averaged accumulator.
    i = wp.tid()
    if i < r:
        ki = kq[i]
        if ki > _ZERO:
            alpha = _ONE / ki
            at = alpha * inv_h2
            wi = wq[i]
            gamma = _ZERO
            if dq[i] > _ZERO:
                gamma = at * (dq[i] * alpha) * h
            Cdot = q[i] - q_n[i]
            denom = (_ONE + gamma) * wi + at
            dl = (-q[i] - at * lam_q[i] - gamma * Cdot) / denom
            lam_q[i] = lam_q[i] + dl
            q[i] = q[i] + wi * dl
    if has_cargo != 0 and i < ck:
        ki = cg_kq[i]
        if ki > _ZERO:
            alpha = _ONE / ki
            at = alpha * inv_h2
            wi = _ZERO
            if cg_mq[i] > _ZERO:
                wi = _ONE / cg_mq[i]
            gamma = _ZERO
            if cg_dq[i] > _ZERO:
                gamma = at * (cg_dq[i] * alpha) * h
            Cdot = cg_a[i] - cg_an[i]
            denom = (_ONE + gamma) * wi + at
            dl = (-cg_a[i] - at * cg_lam[i] - gamma * Cdot) / denom
            cg_lam[i] = cg_lam[i] + dl
            cg_a[i] = cg_a[i] + wi * dl


@wp.kernel
def pk_apply_all(nb: int, modal: int, has_cargo: int, r: int, ck: int,
                 X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
                 invm: wp.array(dtype=wp.float64), deg: wp.array(dtype=wp.float64),
                 relax: wp.float64, q: wp.array(dtype=wp.float64),
                 cg_a: wp.array(dtype=wp.float64),
                 acc_dp: wp.array(dtype=wp.float64),
                 acc_dr: wp.array(dtype=wp.float64),
                 acc_dq: wp.array(dtype=wp.float64),
                 acc_da: wp.array(dtype=wp.float64),
                 acc_dqn: wp.array(dtype=wp.float64),
                 acc_dan: wp.array(dtype=wp.float64)):
    """Fused apply: body (i<nb, averaged X/Q), modal q (i<r), cargo a (i<ck) in
    ONE launch (dim=max(nb,r,ck)); zeros each accumulator it consumes. Cuts two
    launches per iteration vs separate pk_apply_body/q/a. The q/a accumulators
    hold ONLY the support coupling (elastic was applied directly); they are
    averaged by the active-row count acc_dqn/acc_dan (Macklin averaging) so the
    stiff-modal Jacobi sum doesn't overshoot."""
    i = wp.tid()
    if i < nb:
        if invm[i] != _ZERO:
            d = deg[i]
            if d < _ONE:
                d = _ONE
            f = relax / d
            X[i] = X[i] + wp.vec3d(acc_dp[3 * i + 0] * f, acc_dp[3 * i + 1] * f,
                                   acc_dp[3 * i + 2] * f)
            Q[i] = quat_apply_rotvec(Q[i], wp.vec3d(acc_dr[3 * i + 0] * f,
                                                    acc_dr[3 * i + 1] * f,
                                                    acc_dr[3 * i + 2] * f))
        acc_dp[3 * i + 0] = _ZERO
        acc_dp[3 * i + 1] = _ZERO
        acc_dp[3 * i + 2] = _ZERO
        acc_dr[3 * i + 0] = _ZERO
        acc_dr[3 * i + 1] = _ZERO
        acc_dr[3 * i + 2] = _ZERO
    if modal != 0 and i < r:
        nqi = acc_dqn[i]
        if nqi > _ONE:
            q[i] = q[i] + acc_dq[i] / nqi
        else:
            q[i] = q[i] + acc_dq[i]
        acc_dq[i] = _ZERO
        acc_dqn[i] = _ZERO
    if has_cargo != 0 and i < ck:
        nai = acc_dan[i]
        if nai > _ONE:
            cg_a[i] = cg_a[i] + acc_da[i] / nai
        else:
            cg_a[i] = cg_a[i] + acc_da[i]
        acc_da[i] = _ZERO
        acc_dan[i] = _ZERO


@wp.kernel
def pk_zero_deg(nb: int, deg: wp.array(dtype=wp.float64)):
    i = wp.tid()
    if i < nb:
        deg[i] = _ZERO


@wp.kernel
def pk_deg_contacts(cnt: wp.array(dtype=wp.int32), c_a: wp.array(dtype=wp.int32),
                    c_b: wp.array(dtype=wp.int32), deg: wp.array(dtype=wp.float64)):
    """Scatter contact degree into deg (dim=cap, atomic) — parallel replacement
    for the dim=1 count loop."""
    ci = wp.tid()
    if ci >= cnt[0]:
        return
    wp.atomic_add(deg, c_a[ci], _ONE)
    b = c_b[ci]
    if b >= 0:
        wp.atomic_add(deg, b, _ONE)


@wp.kernel
def pk_deg_support(ns: int, sup_bi: wp.array(dtype=wp.int32),
                   deg: wp.array(dtype=wp.float64)):
    s = wp.tid()
    if s < ns:
        wp.atomic_add(deg, sup_bi[s], _ONE)


@wp.kernel
def pk_velupd(nb: int, X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
              x_prev: wp.array(dtype=wp.vec3d), q_prev: wp.array(dtype=wp.quatd),
              V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
              invm: wp.array(dtype=wp.float64), h: wp.float64):
    """v=(x−x_prev)/h, ω=log(Δq)/h per body (dim=nb) — parallel velupd_f."""
    i = wp.tid()
    if i >= nb or invm[i] == _ZERO:
        return
    V[i] = (X[i] - x_prev[i]) / h
    W[i] = quat_to_rotvec(qmul(Q[i], qinv(q_prev[i]))) / h


@wp.kernel
def pk_zero_jt(cap: int, c_jt: wp.array(dtype=wp.vec3d)):
    i = wp.tid()
    if i < cap:
        c_jt[i] = wp.vec3d(_ZERO, _ZERO, _ZERO)


@wp.kernel
def pk_zero_supjt(ns: int, sup_jt: wp.array(dtype=wp.vec3d)):
    i = wp.tid()
    if i < ns:
        sup_jt[i] = wp.vec3d(_ZERO, _ZERO, _ZERO)


@wp.kernel
def pk_commit(modal: int, has_cargo: int, r: int,
             q: wp.array(dtype=wp.float64), q_n: wp.array(dtype=wp.float64),
             qdot: wp.array(dtype=wp.float64), mq: wp.array(dtype=wp.float64),
             kq: wp.array(dtype=wp.float64), ck: int,
             cg_a: wp.array(dtype=wp.float64), cg_an: wp.array(dtype=wp.float64),
             cg_adot: wp.array(dtype=wp.float64), freeze: int, h: wp.float64,
             diag: wp.array(dtype=wp.float64)):
    """Modal q̇ + KE/PE diagnostics + cargo ȧ (numpy commit). dim=1 — a small
    reduction over r (≤~24 modes); keeping it serial avoids an atomic reduction."""
    if modal != 0:
        modal_commit_f(q, q_n, qdot, mq, kq, freeze, h, r, diag)
        if has_cargo != 0:
            cargo_commit_f(cg_a, cg_an, cg_adot, freeze, h, ck)


@wp.kernel
def pk_velprep(nb: int, modal: int, has_cargo: int,
               X: wp.array(dtype=wp.vec3d), Q: wp.array(dtype=wp.quatd),
               x_prev: wp.array(dtype=wp.vec3d),
               q_prev: wp.array(dtype=wp.quatd),
               V: wp.array(dtype=wp.vec3d), W: wp.array(dtype=wp.vec3d),
               invm: wp.array(dtype=wp.float64), h: wp.float64,
               r: int, q: wp.array(dtype=wp.float64),
               q_n: wp.array(dtype=wp.float64), qdot: wp.array(dtype=wp.float64),
               mq: wp.array(dtype=wp.float64), kq: wp.array(dtype=wp.float64),
               ck: int, cg_a: wp.array(dtype=wp.float64),
               cg_an: wp.array(dtype=wp.float64),
               cg_adot: wp.array(dtype=wp.float64),
               cap: int, c_jt: wp.array(dtype=wp.vec3d),
               ns: int, sup_jt: wp.array(dtype=wp.vec3d),
               freeze: int, diag: wp.array(dtype=wp.float64)):
    """v=(x−x_prev)/h, ω=log(Δq)/h; modal/cargo commit (q̇, KE/PE); reset the
    friction accumulators c_jt/sup_jt for the velocity sweep. dim=1, reusing the
    serial @wp.func building blocks (cheap, once per substep)."""
    velupd_f(nb, X, Q, x_prev, q_prev, V, W, invm, h)
    if modal != 0:
        modal_commit_f(q, q_n, qdot, mq, kq, freeze, h, r, diag)
        if has_cargo != 0:
            cargo_commit_f(cg_a, cg_an, cg_adot, freeze, h, ck)
    for ci in range(cap):
        c_jt[ci] = wp.vec3d(_ZERO, _ZERO, _ZERO)
    for s in range(ns):
        sup_jt[s] = wp.vec3d(_ZERO, _ZERO, _ZERO)


@wp.kernel
def pk_contact_velsolve(
        Q: wp.array(dtype=wp.quatd), V: wp.array(dtype=wp.vec3d),
        W: wp.array(dtype=wp.vec3d), invm: wp.array(dtype=wp.float64),
        invIl: wp.array(dtype=wp.mat33d), cnt: wp.array(dtype=wp.int32),
        c_a: wp.array(dtype=wp.int32), c_b: wp.array(dtype=wp.int32),
        c_ra: wp.array(dtype=wp.vec3d), c_rb: wp.array(dtype=wp.vec3d),
        c_n: wp.array(dtype=wp.vec3d), c_mu: wp.array(dtype=wp.float64),
        c_lam: wp.array(dtype=wp.float64), c_jt: wp.array(dtype=wp.vec3d),
        fric_static: wp.float64, h: wp.float64,
        acc_dv: wp.array(dtype=wp.float64), acc_dw: wp.array(dtype=wp.float64)):
    """Inelastic normal restitution (e=0) + cone-clamped Coulomb friction for one
    contact (numpy `_solve_velocity`), scattering the total impulse's Δv/Δω into
    the accumulators. The friction tangent uses vp's tangential part, which the
    normal impulse leaves unchanged — so a single pass matches the serial
    restitution-then-recompute. dim=cap."""
    ci = wp.tid()
    if ci >= cnt[0]:
        return
    if c_lam[ci] <= _ZERO:
        return
    a = c_a[ci]
    n = c_n[ci]
    Ra = quat_to_R(Q[a])
    ra_w = Ra * c_ra[ci]
    invIa = iIw(Ra, invIl[a])
    b = c_b[ci]
    rb_w = wp.vec3d(_ZERO, _ZERO, _ZERO)
    invIb = zero_mat()
    if b >= 0:
        Rb = quat_to_R(Q[b])
        rb_w = Rb * c_rb[ci]
        invIb = iIw(Rb, invIl[b])
    vp = V[a] + wp.cross(W[a], ra_w)
    if b >= 0:
        vp = vp - (V[b] + wp.cross(W[b], rb_w))
    P = wp.vec3d(_ZERO, _ZERO, _ZERO)
    vn = wp.dot(vp, n)
    wn = gen_inv_mass(invm[a], invIa, ra_w, n)
    if b >= 0:
        wn = wn + gen_inv_mass(invm[b], invIb, rb_w, n)
    if wn > _ZERO and wp.abs(vn) > wp.float64(1e-12):
        P = P + (-vn / wn) * n
    mu = c_mu[ci]
    if mu > _ZERO:
        v_t = vp - wp.dot(vp, n) * n
        mag = wp.length(v_t)
        if mag >= wp.float64(1e-12):
            t = v_t / mag
            wt = gen_inv_mass(invm[a], invIa, ra_w, t)
            if b >= 0:
                wt = wt + gen_inv_mass(invm[b], invIb, rb_w, t)
            if wt > _ZERO:
                new_jt = c_jt[ci] + (-mag / wt) * t
                j_max = mu * fric_static * c_lam[ci] / h
                njt = wp.length(new_jt)
                if njt > j_max:
                    new_jt = new_jt * (j_max / njt)
                P = P + (new_jt - c_jt[ci])
                c_jt[ci] = new_jt
    dva = invm[a] * P
    dwa = invIa * wp.cross(ra_w, P)
    wp.atomic_add(acc_dv, 3 * a + 0, dva[0])
    wp.atomic_add(acc_dv, 3 * a + 1, dva[1])
    wp.atomic_add(acc_dv, 3 * a + 2, dva[2])
    wp.atomic_add(acc_dw, 3 * a + 0, dwa[0])
    wp.atomic_add(acc_dw, 3 * a + 1, dwa[1])
    wp.atomic_add(acc_dw, 3 * a + 2, dwa[2])
    if b >= 0:
        Pb = -P
        dvb = invm[b] * Pb
        dwb = invIb * wp.cross(rb_w, Pb)
        wp.atomic_add(acc_dv, 3 * b + 0, dvb[0])
        wp.atomic_add(acc_dv, 3 * b + 1, dvb[1])
        wp.atomic_add(acc_dv, 3 * b + 2, dvb[2])
        wp.atomic_add(acc_dw, 3 * b + 0, dwb[0])
        wp.atomic_add(acc_dw, 3 * b + 1, dwb[1])
        wp.atomic_add(acc_dw, 3 * b + 2, dwb[2])


@wp.kernel
def pk_support_velsolve(
        Q: wp.array(dtype=wp.quatd), V: wp.array(dtype=wp.vec3d),
        W: wp.array(dtype=wp.vec3d), invm: wp.array(dtype=wp.float64),
        invIl: wp.array(dtype=wp.mat33d), ns: int,
        sup_bi: wp.array(dtype=wp.int32), sup_off: wp.array(dtype=wp.vec3d),
        sup_lam: wp.array(dtype=wp.float64), sup_mu: wp.array(dtype=wp.float64),
        sup_jt: wp.array(dtype=wp.vec3d), fric_static: wp.float64, h: wp.float64,
        acc_dv: wp.array(dtype=wp.float64), acc_dw: wp.array(dtype=wp.float64)):
    """Support tangential Coulomb friction (numpy `_solve_velocity_support`);
    friction-only (no e=0 restitution — the support normal is soft modal). dim=ns."""
    s = wp.tid()
    if s >= ns:
        return
    mu = sup_mu[s]
    if sup_lam[s] <= _ZERO or mu <= _ZERO:
        return
    bi = sup_bi[s]
    if invm[bi] == _ZERO:
        return
    R = quat_to_R(Q[bi])
    r_w = R * sup_off[s]
    invIw = iIw(R, invIl[bi])
    up = wp.vec3d(_ZERO, _ONE, _ZERO)
    vp = V[bi] + wp.cross(W[bi], r_w)
    v_t = vp - wp.dot(vp, up) * up
    mag = wp.length(v_t)
    if mag < wp.float64(1e-12):
        return
    t = v_t / mag
    wt = gen_inv_mass(invm[bi], invIw, r_w, t)
    if wt <= _ZERO:
        return
    new_jt = sup_jt[s] + (-mag / wt) * t
    j_max = mu * fric_static * sup_lam[s] / h
    njt = wp.length(new_jt)
    if njt > j_max:
        new_jt = new_jt * (j_max / njt)
    dP = new_jt - sup_jt[s]
    sup_jt[s] = new_jt
    dv = invm[bi] * dP
    dw = invIw * wp.cross(r_w, dP)
    wp.atomic_add(acc_dv, 3 * bi + 0, dv[0])
    wp.atomic_add(acc_dv, 3 * bi + 1, dv[1])
    wp.atomic_add(acc_dv, 3 * bi + 2, dv[2])
    wp.atomic_add(acc_dw, 3 * bi + 0, dw[0])
    wp.atomic_add(acc_dw, 3 * bi + 1, dw[1])
    wp.atomic_add(acc_dw, 3 * bi + 2, dw[2])


@wp.kernel
def pk_apply_vel(nb: int, V: wp.array(dtype=wp.vec3d),
                 W: wp.array(dtype=wp.vec3d), invm: wp.array(dtype=wp.float64),
                 deg: wp.array(dtype=wp.float64), relax: wp.float64,
                 acc_dv: wp.array(dtype=wp.float64),
                 acc_dw: wp.array(dtype=wp.float64)):
    """V += ω·Σδv/deg, W += ω·Σδω/deg; zero the accumulator for the next iter."""
    i = wp.tid()
    if i >= nb:
        return
    if invm[i] != _ZERO:
        d = deg[i]
        if d < _ONE:
            d = _ONE
        f = relax / d
        V[i] = V[i] + wp.vec3d(acc_dv[3 * i + 0] * f, acc_dv[3 * i + 1] * f,
                               acc_dv[3 * i + 2] * f)
        W[i] = W[i] + wp.vec3d(acc_dw[3 * i + 0] * f, acc_dw[3 * i + 1] * f,
                               acc_dw[3 * i + 2] * f)
    acc_dv[3 * i + 0] = _ZERO
    acc_dv[3 * i + 1] = _ZERO
    acc_dv[3 * i + 2] = _ZERO
    acc_dw[3 * i + 0] = _ZERO
    acc_dw[3 * i + 1] = _ZERO
    acc_dw[3 * i + 2] = _ZERO


@wp.kernel
def pk_maxpen(cnt: wp.array(dtype=wp.int32), X: wp.array(dtype=wp.vec3d),
             Q: wp.array(dtype=wp.quatd), c_a: wp.array(dtype=wp.int32),
             c_b: wp.array(dtype=wp.int32), c_ra: wp.array(dtype=wp.vec3d),
             c_rb: wp.array(dtype=wp.vec3d), c_n: wp.array(dtype=wp.vec3d),
             c_floory: wp.array(dtype=wp.float64),
             diag: wp.array(dtype=wp.float64)):
    """Max contact penetration → diag[0] (numpy tail of `_substep_cpu`). dim=1."""
    n_c = cnt[0]
    maxpen = _ZERO
    for ci in range(n_c):
        a = c_a[ci]
        Ra = quat_to_R(Q[a])
        pa = X[a] + Ra * c_ra[ci]
        b = c_b[ci]
        pen = _ZERO
        if b < 0:
            pen = c_floory[ci] - pa[1]
        else:
            Rb = quat_to_R(Q[b])
            pb = X[b] + Rb * c_rb[ci]
            pen = wp.dot(pb - pa, c_n[ci])
        if pen < _ZERO:
            pen = _ZERO
        if pen > maxpen:
            maxpen = pen
    diag[0] = maxpen
