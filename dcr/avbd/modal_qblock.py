"""Monolithic (z, q) backward-Euler step — the in-solver ground-truth oracle.

Pure-numpy reference for the dynamic two-way modal contact constraint of
`../DCR-AVBD-Native/two_band_coupling.html` ("Modal Contact as a Dynamic
Two-Way Constraint", Approach B). The support's modal amplitude `q ∈ R^r` is
a genuine second-order DOF `(q, q̇)` co-solved with the rigid bodies `z` in a
SINGLE backward-Euler / AVBD augmented-Lagrangian step minimizing one
incremental potential:

    E(z, q) = Σ_i 1/(2h²) ‖z_i − z̃_i‖²_{M_i}      # rigid inertia
            +       1/(2h²) ‖q − q̃‖²_{M_q}         # modal inertia  ◀ NEW
            +       ½ qᵀ K_q q                       # modal stiffness
            +  Σ_j  Φ_AL( g_j(z, q) )                # contact — sees the FULL q

This module has NO dependency on Solver6DOF or the (retired) coupler, so it is
unit-testable in pure numpy and serves as the parity/physics oracle the warp
in-solver path is validated against (CLAUDE.md rule 6: reference first).

Faithful to the foundation; every equation below cites it. The contact gap,
gradients, and the Newton/Schur block are implemented verbatim:

    g_j(z, q) = corner_y,j(z) − (y_rest,j + U_y,j · q)  ≥ 0      # non-penetration
    ∂g/∂z = J_x,j = [n̂ ; r × n̂]
    ∂g/∂q = −U_y,j ≡ J_q,j
    f_j   = clamp(ρ g_j + λ_j, f_lo, f_hi)                       # unilateral

    [ H_x,i        −ρ J_x,i U_y,jᵀ ] [Δz_i]   [ −g_x,i ]
    [ −ρ U_y,j J_x,iᵀ      H_q     ] [Δq  ] = [ −g_q   ]

    H_q = 1/h²·M_q + 1/h·D_q + K_q + Σ_j k_j U_y,j U_y,jᵀ
    g_q = 1/h²·M_q (q − q̃) + 1/h·D_q (q − qⁿ) + K_q q − Σ_j U_y,j f_j
    q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Quaternion helpers (xyzw convention, matching the solver)
# ---------------------------------------------------------------------------

def _quat_to_R(q_xyzw: NDArray[np.float64]) -> NDArray[np.float64]:
    x, y, z, w = (float(q_xyzw[0]), float(q_xyzw[1]),
                  float(q_xyzw[2]), float(q_xyzw[3]))
    n = x * x + y * y + z * z + w * w
    if n < 1e-30:
        return np.eye(3)
    s = 2.0 / n
    return np.array([
        [1.0 - s * (y * y + z * z), s * (x * y - z * w), s * (x * z + y * w)],
        [s * (x * y + z * w), 1.0 - s * (x * x + z * z), s * (y * z - x * w)],
        [s * (x * z - y * w), s * (y * z + x * w), 1.0 - s * (x * x + y * y)],
    ], dtype=np.float64)


def _quat_mul(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], dtype=np.float64)


def _quat_inv(q: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.array([-q[0], -q[1], -q[2], q[3]], dtype=np.float64)


def _quat_from_rotvec(rv: NDArray[np.float64]) -> NDArray[np.float64]:
    theta = float(np.linalg.norm(rv))
    if theta < 1e-12:
        return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    axis = rv / theta
    s = np.sin(0.5 * theta)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s,
                     np.cos(0.5 * theta)], dtype=np.float64)


def _quat_to_rotvec(q: NDArray[np.float64]) -> NDArray[np.float64]:
    w = float(np.clip(q[3], -1.0, 1.0))
    v = np.array([q[0], q[1], q[2]], dtype=np.float64)
    s = float(np.linalg.norm(v))
    if s < 1e-12:
        return 2.0 * v  # small-angle
    angle = 2.0 * np.arctan2(s, w)
    return (angle / s) * v


# ---------------------------------------------------------------------------
# Scene state
# ---------------------------------------------------------------------------

@dataclass
class Body:
    """A rigid body in the oracle. Generalized velocity v = [v_lin; ω]."""
    mass: float
    inertia_local: NDArray[np.float64]            # (3,3) body-frame inertia
    x: NDArray[np.float64]                         # (3,) position
    q: NDArray[np.float64]                         # (4,) orientation xyzw
    v: NDArray[np.float64]                         # (3,) linear velocity
    omega: NDArray[np.float64]                     # (3,) angular velocity

    # support contacts on this body: corner offsets (body-local), the mode-shape
    # row U_y sampled where the corner touches, and the rest height y_rest.
    corner_off: NDArray[np.float64] = field(       # (n_c, 3)
        default_factory=lambda: np.zeros((0, 3)))
    corner_U_y: NDArray[np.float64] = field(       # (n_c, r)
        default_factory=lambda: np.zeros((0, 0)))
    corner_y_rest: NDArray[np.float64] = field(    # (n_c,)
        default_factory=lambda: np.zeros((0,)))
    # AL dual per corner (warm-started across substeps).
    corner_lam: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros((0,)))


@dataclass
class ModalScene:
    """Bodies + one shared modal support (q, q̇) with M_q, K_q, D_q."""
    bodies: list[Body]
    Mq: NDArray[np.float64]                         # (r, r)
    Kq: NDArray[np.float64]                         # (r, r)
    Dq: NDArray[np.float64]                         # (r, r)
    q: NDArray[np.float64]                          # (r,)
    qdot: NDArray[np.float64]                       # (r,)
    gravity: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -9.81, 0.0]))
    f_q_grav: NDArray[np.float64] | None = None     # Uᵀ f_grav → static sag, opt
    penalty: float = 1.0e6                          # contact penalty ρ = k
    # f_q^grav default: zero (zero-mean modes about rest, as the synthetic
    # shelf support — matches the coupler's q̃ = qⁿ + h q̇ⁿ predictor).

    @property
    def r(self) -> int:
        return int(self.q.shape[0])


# ---------------------------------------------------------------------------
# Energy (for the passivity invariant)
# ---------------------------------------------------------------------------

def modal_energy(scene: ModalScene) -> float:
    """Modal mechanical energy ½ q̇ᵀ M_q q̇ + ½ qᵀ K_q q (foundation, the
    `Ė ≤ 0` passivity proof acts on this plus the rigid energy)."""
    q, qd = scene.q, scene.qdot
    return float(0.5 * qd @ scene.Mq @ qd + 0.5 * q @ scene.Kq @ q)


def rigid_energy(scene: ModalScene) -> float:
    """Rigid KE + gravitational PE summed over bodies."""
    g = scene.gravity
    e = 0.0
    for b in scene.bodies:
        if b.mass <= 0.0 or not np.isfinite(b.mass):
            continue
        R = _quat_to_R(b.q)
        I_world = R @ b.inertia_local @ R.T
        e += 0.5 * b.mass * float(b.v @ b.v)
        e += 0.5 * float(b.omega @ I_world @ b.omega)
        e += -b.mass * float(g @ b.x)   # PE = −m g·x  (g points down)
    return float(e)


def total_energy(scene: ModalScene) -> float:
    return rigid_energy(scene) + modal_energy(scene)


# ---------------------------------------------------------------------------
# The monolithic (z, q) backward-Euler step
# ---------------------------------------------------------------------------

def step_zq(
    scene: ModalScene,
    h: float,
    *,
    n_iter: int = 10,
    freeze_qdot: bool = False,
    eps_reg: float = 1.0e-12,
) -> None:
    """One backward-Euler substep over (z, q) — foundation "One variational
    step over (z, q)". Mutates `scene` in place.

    The two-way loop is structural: a single multiplier f_j per support
    contact enters the body gradient (+J_x f) and the modal gradient (−U_y f)
    with opposite signs through the SAME scalar (Newton's third law). Passive
    by construction (backward Euler is unconditionally dissipative).

    `freeze_qdot` is the counterfactual: q̇ is held at 0 (predictor q̃ = qⁿ and
    no q̇ commit), so the mode is quasi-static and carries no ring history.
    """
    n_b = len(scene.bodies)
    r = scene.r
    inv_dt = 1.0 / h
    inv_dt2 = inv_dt * inv_dt
    Mq, Kq, Dq = scene.Mq, scene.Kq, scene.Dq

    # ---- Inertial predictors (foundation "Inertial predictors") ----
    #   z̃_i = z_iⁿ + h v_iⁿ + h² M_i⁻¹ f_i^ext   (f^ext = m g  ⇒  x̃ = x+hv+h²g)
    #   q̃   = qⁿ + h q̇ⁿ + h² M_q⁻¹ f_q^grav
    # q̃ carries the ring history q̇ⁿ — NOT zeroed (the whole point), unless the
    # frozen-q̇ counterfactual.
    g_vec = scene.gravity
    x_initial = [b.x.copy() for b in scene.bodies]
    q_initial = [b.q.copy() for b in scene.bodies]
    x_inertial = []
    q_inertial = []
    for b in scene.bodies:
        if b.mass > 0.0 and np.isfinite(b.mass):
            x_inertial.append(b.x + h * b.v + h * h * g_vec)
        else:
            x_inertial.append(b.x.copy())
        # torque-free angular predictor (no external torque): orientation drifts
        # by ω over h.
        q_pred = _quat_mul(_quat_from_rotvec(b.omega * h), b.q)
        nrm = np.linalg.norm(q_pred)
        q_inertial.append(q_pred / nrm if nrm > 1e-12 else b.q.copy())
        # warm-start the body to its inertial pose.
        b.x = x_inertial[-1].copy()
        b.q = q_inertial[-1].copy()

    q_n = scene.q.copy()                            # qⁿ snapshot
    h_pred = 0.0 if freeze_qdot else h
    f_q_grav = (np.zeros(r) if scene.f_q_grav is None
                else np.asarray(scene.f_q_grav, dtype=np.float64))
    q_hat = q_n + h_pred * scene.qdot + h * h * np.linalg.solve(Mq, f_q_grav)

    n_hat = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    for _ in range(n_iter):
        # ---- Modal block base (foundation H_q, g_q first two+stiffness terms)
        q = scene.q
        H_q = inv_dt2 * Mq + inv_dt * Dq + Kq
        g_q = (inv_dt2 * (Mq @ (q - q_hat))
               + inv_dt * (Dq @ (q - q_n))
               + Kq @ q)

        per_Hxinv: dict[int, NDArray[np.float64]] = {}
        per_gx: dict[int, NDArray[np.float64]] = {}
        per_cross: dict[int, NDArray[np.float64]] = {}

        for bi, b in enumerate(scene.bodies):
            m = float(b.mass)
            if m <= 0.0 or not np.isfinite(m):
                continue
            R = _quat_to_R(b.q)
            I_world = R @ b.inertia_local @ R.T

            # rigid inertia blocks
            A = m * inv_dt2 * np.eye(3)
            Dblk = I_world * inv_dt2
            Bblk = np.zeros((3, 3))
            r_lin = m * inv_dt2 * (b.x - x_inertial[bi])
            dq_iner = _quat_mul(b.q, _quat_inv(q_inertial[bi]))
            r_ang = I_world @ (_quat_to_rotvec(dq_iner) * inv_dt2)

            cross = np.zeros((6, r))

            n_c = b.corner_off.shape[0]
            if n_c == 0:
                H_x = np.block([[A, Bblk.T], [Bblk, Dblk]])
                per_Hxinv[bi] = np.linalg.inv(H_x + eps_reg * np.eye(6))
                per_gx[bi] = np.concatenate([r_lin, r_ang])
                per_cross[bi] = -cross
                continue

            # contact geometry: corner world offset r = R·off
            r_w = b.corner_off @ R.T                 # (n_c, 3)
            j_lin = np.broadcast_to(n_hat, (n_c, 3))
            j_ang = np.empty((n_c, 3))
            j_ang[:, 0] = -r_w[:, 2]
            j_ang[:, 1] = 0.0
            j_ang[:, 2] = r_w[:, 0]

            # gap g_j = corner_y − (y_rest + U_y·q)   — sees the LIVE q
            surf = b.corner_y_rest + b.corner_U_y @ q
            C = (b.x[1] + r_w[:, 1]) - surf
            lam = b.corner_lam
            rho = scene.penalty
            f_lo = np.full(n_c, -np.inf)
            f_hi = np.zeros(n_c)                     # compressive-only
            lam_plus = rho * C + lam
            f = np.clip(lam_plus, f_lo, f_hi)

            # effective LHS stiffness (drop to the clamp slope when bounded)
            abs_C = np.abs(C)
            below = (lam_plus < f_lo) & (abs_C > 1e-12)   # never (f_lo=-inf)
            above = (lam_plus > f_hi) & (abs_C > 1e-12)
            safe_C = np.maximum(abs_C, 1e-12)
            k_lhs = np.where(above, np.abs(f_hi - lam_plus) / safe_C, rho)
            k_lhs = np.where(below, np.abs(f_lo - lam_plus) / safe_C, k_lhs)
            k_U = k_lhs[:, None] * b.corner_U_y

            # modal contributions (the shared multiplier, opposite sign)
            #   g_q -= Σ U_y f ,  H_q += Σ k U_y U_yᵀ
            g_q = g_q - b.corner_U_y.T @ f
            H_q = H_q + b.corner_U_y.T @ k_U

            # body Hessian/gradient
            k_jl = k_lhs[:, None] * j_lin
            k_ja = k_lhs[:, None] * j_ang
            A = A + j_lin.T @ k_jl
            Bblk = Bblk + j_ang.T @ k_jl
            Dblk = Dblk + j_ang.T @ k_ja
            r_lin = r_lin + j_lin.T @ f
            r_ang = r_ang + j_ang.T @ f

            # cross block H_xq = ρ J_x J_qᵀ = −ρ J_x U_yᵀ
            cross[:3, :] += j_lin.T @ k_U
            cross[3:, :] += j_ang.T @ k_U

            H_x = np.block([[A, Bblk.T], [Bblk, Dblk]])
            per_Hxinv[bi] = np.linalg.inv(H_x + eps_reg * np.eye(6))
            per_gx[bi] = np.concatenate([r_lin, r_ang])
            per_cross[bi] = -cross

        # ---- Schur-eliminate Δz per body, solve r×r for Δq ----
        S = H_q.copy()
        rhs_q = -g_q
        for bi in per_Hxinv:
            M = per_cross[bi]
            Hxi = per_Hxinv[bi]
            S = S - M.T @ Hxi @ M
            rhs_q = rhs_q + M.T @ Hxi @ per_gx[bi]
        S_reg = S + eps_reg * np.eye(r)
        dq = np.linalg.solve(S_reg, rhs_q)
        scene.q = scene.q + dq

        # ---- back-substitute Δz_i = H_x,i⁻¹(−g_x,i − M_i Δq) ----
        for bi, b in enumerate(scene.bodies):
            if bi not in per_Hxinv:
                continue
            delta = per_Hxinv[bi] @ (-(per_gx[bi] + per_cross[bi] @ dq))
            b.x = b.x + delta[:3]
            dqq = _quat_from_rotvec(delta[3:])
            newq = _quat_mul(dqq, b.q)
            nrm = np.linalg.norm(newq)
            b.q = newq / nrm if nrm > 1e-12 else b.q

        # ---- dual update (AL): λ ← clamp(λ + ρ C, f_lo, f_hi) ----
        for b in scene.bodies:
            if b.corner_off.shape[0] == 0:
                continue
            R = _quat_to_R(b.q)
            r_w = b.corner_off @ R.T
            surf = b.corner_y_rest + b.corner_U_y @ scene.q
            C = (b.x[1] + r_w[:, 1]) - surf
            b.corner_lam = np.clip(b.corner_lam + scene.penalty * C,
                                   -np.inf, 0.0)

    # ---- velocity commits (backward Euler finite difference) ----
    for bi, b in enumerate(scene.bodies):
        if b.mass <= 0.0 or not np.isfinite(b.mass):
            continue
        b.v = (b.x - x_initial[bi]) * inv_dt
        dq_step = _quat_mul(b.q, _quat_inv(q_initial[bi]))
        b.omega = _quat_to_rotvec(dq_step) * inv_dt

    if not freeze_qdot:
        scene.qdot = (scene.q - q_n) * inv_dt
    # frozen counterfactual: q̇ stays 0, mode is quasi-static (no ring history).
