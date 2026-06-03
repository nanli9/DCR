"""Phase B §10/§11/§12: impulse-work estimator, work budget, γ rescale.

Spec mapping:
  - prompts/avbd_native_dcr_followup_spec_v2.md §10 (impulse-work estimator)
  - prompts/avbd_native_dcr_followup_spec_v2.md §11 (work budget)
  - prompts/avbd_native_dcr_followup_spec_v2.md §12 (passivity line search)

These primitives are the single load-bearing components of the finite-
energy claim. The contract is that **the moving support can only
transfer physical work that is explicitly present in its reservoir**
(spec §27).

# DEVIATION (foundation §15): the foundation document's energy
# accounting is the cumulative passive-injection inequality
#   cumulative ΔE_modal_injected ≤ η · cumulative ΔE_rigid_loss + ε
# The spec §10 estimator measures the **other direction** — work done
# by the moving support **on** the rigid body — and bounds it by the
# modal reservoir budget (§11). Both inequalities must hold in the
# closed-system case (spec Invariant 7 / §15).
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# §10: K_body and impulse-work estimator
# ---------------------------------------------------------------------------

def cross_matrix(r: NDArray[np.float64]) -> NDArray[np.float64]:
    """Skew-symmetric matrix [r]× such that [r]× v = r × v for any v.

    [r]×ᵀ = -[r]× (spec §10, identity used in K_body derivation).
    """
    return np.array([
        [0.0, -r[2],  r[1]],
        [r[2],  0.0, -r[0]],
        [-r[1], r[0],  0.0],
    ])


def k_body(
    r: NDArray[np.float64],
    m: float,
    I_world_inv: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Effective point-mass matrix at offset r (spec §10).

        K_body = (1/m) I₃ − [r]× I_world⁻¹ [r]×
               = (1/m) I₃ + [r]×ᵀ I_world⁻¹ [r]×   (since [r]×ᵀ = −[r]×)

    K_body relates a world-space impulse J applied at offset r to the
    KE change it produces:

        ΔE = Jᵀ v_p_before + ½ Jᵀ K_body J,    v_p = v + ω × r.

    Args:
        r: (3,) world-frame contact offset (contact point − COM).
        m: scalar body mass.
        I_world_inv: (3, 3) world-frame inverse inertia tensor.

    Returns:
        K_body: (3, 3) symmetric positive-definite point-mass matrix.
    """
    R = cross_matrix(r)
    # Form 1 from spec: −[r]× I⁻¹ [r]×.
    K = (1.0 / m) * np.eye(3) - R @ I_world_inv @ R
    # Symmetrize to kill any numerical asymmetry from finite precision.
    return 0.5 * (K + K.T)


def estimate_impulse_work(
    J: NDArray[np.float64],
    v_before: NDArray[np.float64],
    omega_before: NDArray[np.float64],
    r: NDArray[np.float64],
    m: float,
    I_world_inv: NDArray[np.float64],
) -> float:
    """Kinetic-energy change of a rigid body from an impulse J at offset r
    (spec §10.1).

        ΔE_rigid(J) = Jᵀ v_p_before + ½ Jᵀ K_body J

    with v_p_before = v + ω × r.

    The "work done by the support on the rigid body" is the positive
    part of this quantity:

        W_support→rigid = max(0, ΔE_rigid(J))

    (spec §10.1, "Then" line). This function returns the **signed**
    ΔE — callers (e.g. `passivity_scale_gamma`) take max(0, ·).

    Args:
        J: (3,) world-frame impulse applied to the rigid body.
        v_before, omega_before: linear + angular velocity before impulse.
        r: (3,) contact offset (contact point − COM, world frame).
        m: body mass.
        I_world_inv: (3, 3) world-frame inverse inertia tensor.

    Returns:
        ΔE_rigid(J): scalar signed kinetic-energy change due to J alone.
    """
    v_p_before = v_before + np.cross(omega_before, r)
    K = k_body(r, m, I_world_inv)
    linear_term = float(J @ v_p_before)
    quadratic_term = 0.5 * float(J @ K @ J)
    return linear_term + quadratic_term


def support_work(
    impulses: Sequence[NDArray[np.float64]],
    v_before: NDArray[np.float64],
    omega_before: NDArray[np.float64],
    offsets: Sequence[NDArray[np.float64]],
    m: float,
    I_world_inv: NDArray[np.float64],
) -> float:
    """Total work the moving support does on one rigid body across a
    list of contact impulses, accumulated sequentially with intermediate
    velocity updates (spec §10.1, "for multiple impulses" — variant 1).

    Sequential accumulation avoids the double-counting that a naive
    Σ Jᵢᵀ v_p_before(0) sum would introduce when the impulses interact.

    Returns max(0, ΣΔE) so it can be compared directly against
    E_budget in `passivity_scale_gamma`.
    """
    v = np.asarray(v_before, dtype=np.float64).copy()
    omega = np.asarray(omega_before, dtype=np.float64).copy()
    total = 0.0
    for J, r in zip(impulses, offsets):
        J = np.asarray(J, dtype=np.float64)
        r = np.asarray(r, dtype=np.float64)
        v_p = v + np.cross(omega, r)
        K = k_body(r, m, I_world_inv)
        total += float(J @ v_p) + 0.5 * float(J @ K @ J)
        # Update intermediate velocity for the next impulse in this body.
        v = v + J / m
        omega = omega + I_world_inv @ np.cross(r, J)
    return float(max(0.0, total))


# ---------------------------------------------------------------------------
# §11: work budget
# ---------------------------------------------------------------------------

def modal_energy(
    qdot: NDArray[np.float64],
    q: NDArray[np.float64],
    omega2_diag: NDArray[np.float64],
) -> float:
    """Modal mechanical energy ½ q̇ᵀ q̇ + ½ qᵀ Ω² q (spec §1.2).

    Mass-normalized modes ⇒ kinetic term has no extra mass matrix.
    """
    qd = np.asarray(qdot, dtype=np.float64)
    qv = np.asarray(q, dtype=np.float64)
    om2 = np.asarray(omega2_diag, dtype=np.float64)
    return 0.5 * float(qd @ qd) + 0.5 * float(qv @ (om2 * qv))


def support_budget(
    beta: float,
    E_modal_reservoir: float,
) -> float:
    """Moving-support work budget (spec §11, "first version"):

        E_budget = β · E_modal_reservoir

    The support can do at most this much work on rigid bodies in the
    current step; anything more is rescaled by γ in §12.
    """
    return max(0.0, float(beta) * float(E_modal_reservoir))


# ---------------------------------------------------------------------------
# §12: passivity line search
# ---------------------------------------------------------------------------

def gamma_rescale(
    W_current: float,
    E_budget: float,
    eps: float = 1e-12,
) -> float:
    """One step of the γ rescale (spec §12):

        γ ← γ · √(E_budget / (W_current + ε))

    Returned scalar is the multiplicative factor to apply to the
    CURRENT γ, not the absolute new γ. Caller composes:

        gamma_next = gamma_curr * gamma_rescale(W, E_budget)
    """
    if W_current <= 0.0:
        return 1.0
    return float(np.sqrt(max(0.0, E_budget) / (max(0.0, W_current) + eps)))


def passivity_scale_gamma(
    run_solve: callable,
    E_budget: float,
    max_attempts: int = 3,
    tolerance: float = 1e-6,
    eps: float = 1e-12,
) -> tuple[float, float, int]:
    """Passivity line search (spec §12).

    `run_solve(gamma)` is the user-supplied callable that runs the
    moving-support AVBD solve with the support contribution scaled by
    `gamma`, then returns `W_support_to_rigid` (the impulse-work
    estimate aggregated over all support impulses for this step). The
    body of `run_solve` is responsible for collecting accepted impulses
    and calling `support_work(...)` or `estimate_impulse_work(...)` to
    produce its return value.

    Algorithm:
        γ = 1
        for attempt in range(max_attempts):
            W = run_solve(γ)
            if W ≤ E_budget + tol: accept
            γ ← γ · √(E_budget / (W + ε))
        if still violating: γ = 0; run_solve(0); accept

    Returns:
        (gamma_final, W_final, attempts_used)

    The fallback γ=0 always satisfies the bound by construction since
    the support stops contributing.
    """
    gamma = 1.0
    W = 0.0
    attempts = 0
    for attempts in range(1, max_attempts + 1):
        W = float(run_solve(gamma))
        if W <= E_budget + tolerance:
            return gamma, W, attempts
        gamma *= gamma_rescale(W, E_budget, eps=eps)
        gamma = float(np.clip(gamma, 0.0, 1.0))
    # Hard fallback: disable the support contribution this step.
    gamma = 0.0
    W = float(run_solve(gamma))
    return gamma, W, max_attempts + 1
