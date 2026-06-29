"""Energy-conserving (implicit-midpoint / trapezoidal) modal time step.

Shared per-mode helper used by BOTH native solvers' symplectic modal path
(AVBD ``Solver6DOF._solve_q_block`` and XPBD ``SolverXPBD._substep_cpu`` fold).
It replaces the dissipative backward-Euler integration of the modal coordinate
``q`` with the energy-conserving implicit-midpoint rule, keeping ``q`` co-solved
inside the native support constraint (the contact force ``F`` is added to the
``rhs`` by the caller's constraint solve, NOT here).

Per mode (diagonal eigenbasis) the modal EOM is

    M q̈ + D q̇ + K q = F             (M = M_q[i], D = 2ζω, K = ω²)

Implicit midpoint with the predictor q̃ = qⁿ + h·q̇ⁿ collapses to a single
linear equation in qⁿ⁺¹ (derivation: evaluate the EOM at the midpoint state
q^{n+½} = (qⁿ+qⁿ⁺¹)/2, q̇^{n+½} = (qⁿ⁺¹−qⁿ)/h):

    H_diag · qⁿ⁺¹ = rhs + F
    H_diag = 2M/h² + D/h + K/2
    rhs    = (2M/h²)·q̃ + (D/h)·qⁿ − (K/2)·qⁿ + f_grav

with the consistent velocity reconstruction

    q̇ⁿ⁺¹ = 2·(qⁿ⁺¹ − qⁿ)/h − q̇ⁿ.

Compare backward Euler: H = M/h² + D/h + K, rhs_BE = (M/h²)q̃ + (D/h)qⁿ,
q̇ⁿ⁺¹ = (qⁿ⁺¹−qⁿ)/h. BE's amplification |λ| = 1/√(1+ω²h²) < 1 dissipates modal
energy every step (it kills the ring even when fully converged); implicit
midpoint has det = 1 → energy conserved (undamped) and decays at the PHYSICAL
rate when damped, and is A-stable on the stiff modes (ωh ≫ 2).

# DEVIATION (paper Eq. 10): the paper steps the modal IIR as a FORCED, decoupled
# recurrence. Here q is co-solved IN the native support constraint (passive by
# construction — body and q move together, momentum-conserving) and only the
# free/homogeneous part of the step is switched from backward Euler to implicit
# midpoint so the surface rings at the physical rate. See
# prompts/symplectic_modal_integrator_prompt.md and memory
# xpbd-vs-avbd-modal-ring-mechanism.md.

# DEVIATION (gravity placement vs the BE predictor): backward Euler folds gravity
# into the predictor as q̃ += h²·M⁻¹·f_grav and recovers +f_grav via its M/h²
# inertia. Midpoint's 2M/h² inertia would then inject +2·f_grav, so here gravity
# enters `rhs` directly as the FORCE f_grav and the predictor q̃ is gravity-free.

# CAVEAT: implicit midpoint is A-stable but not L-stable, so the stiffest modes
# can chatter at Nyquist; here that is negligible (heavy Rayleigh damping). If it
# ever bites, the energy-faithful fallback is the exact resonator
# `dcr/modal/exact_resonator.py:exact_modal_step_precompute`, which damps stiff
# modes cleanly and is the same physics expressed as a compliance-to-force.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def modal_midpoint_coeffs(
    q_n: NDArray[np.float64],
    qdot_n: NDArray[np.float64],
    mass: NDArray[np.float64],
    stiff: NDArray[np.float64],
    damp: NDArray[np.float64],
    h: float,
    f_grav: NDArray[np.float64] | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64],
           NDArray[np.float64], NDArray[np.float64]]:
    """Per-mode implicit-midpoint coefficients for one modal step.

    The modal equation is ``H_diag·qⁿ⁺¹ = rhs + F_contact`` where the contact
    force ``F_contact`` is supplied by the caller's constraint solve. The
    free (no-contact) solution is ``q_star = rhs/H_diag`` and the inverse mass
    the contact coupling sees is ``w_eff = 1/H_diag`` (the XPBD fold uses both).

    Args:
        q_n: modal amplitude qⁿ, (r,).
        qdot_n: modal velocity q̇ⁿ, (r,).
        mass: per-mode M_q diagonal, (r,) (= 1 for mass-normalized modes).
        stiff: per-mode K_q diagonal = ω², (r,).
        damp: per-mode D_q diagonal = 2ζω, (r,).
        h: substep timestep (s).
        f_grav: per-mode modal gravity FORCE, (r,), or None.

    Returns:
        (H_diag, rhs, q_star, w_eff), each (r,).
    """
    h = float(h)
    inv_h = 1.0 / h
    inv_h2 = inv_h * inv_h
    q_tilde = q_n + h * qdot_n                       # gravity-free predictor q̃
    H_diag = 2.0 * mass * inv_h2 + damp * inv_h + 0.5 * stiff
    rhs = ((2.0 * mass * inv_h2) * q_tilde
           + (damp * inv_h) * q_n
           - (0.5 * stiff) * q_n)
    if f_grav is not None:
        rhs = rhs + f_grav
    # Guard degenerate/frozen modes (M=K=D=0) → w_eff=0, q_star=0.
    ok = H_diag > 0.0
    w_eff = np.where(ok, 1.0 / np.where(ok, H_diag, 1.0), 0.0)
    q_star = rhs * w_eff
    return H_diag, rhs, q_star, w_eff


def modal_midpoint_commit(
    q_next: NDArray[np.float64],
    q_n: NDArray[np.float64],
    qdot_n: NDArray[np.float64],
    h: float,
) -> NDArray[np.float64]:
    """Implicit-midpoint velocity reconstruction q̇ⁿ⁺¹ = 2(qⁿ⁺¹−qⁿ)/h − q̇ⁿ.

    This is the scheme-consistent counterpart to the BE finite difference
    (qⁿ⁺¹−qⁿ)/h; using the BE difference with the midpoint position solve would
    break energy conservation.
    """
    return 2.0 * (q_next - q_n) / float(h) - qdot_n
