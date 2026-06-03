"""Phase B / spec §6–§13: moving-support AVBD contact at the adapter layer.

Spec §19 step 9 describes this as a **separate** solve run after the
ordinary AVBD contact pass: the modal support enters as a finite-energy
moving geometry, the contact gap is computed against `x_s(q)`, and the
support contribution is scaled by γ from a passivity line search so that
W_support→rigid never exceeds the modal reservoir budget E_budget.

This file implements the per-body, per-contact primitive. Wiring it into
`AVBDDCRWorld.step()` is opt-in: a Phase A world that never calls
`solve_one_contact` is bit-identical to before; a Phase B world that
does call it gets the moving-support pass AFTER the patch coupler's
modal injection.

# DEVIATION (foundation §15, spec §7.3): for the first implementation we
# freeze the BJ normal per solve (`n_BJ = n_rest` is acceptable when
# the deformation is small — spec §3.3 explicitly allows treating BJ as
# an optional ablation that fires only on deformation-driven scenes).
# When `compute_deformed_normal_barbic_james` is available the caller
# may pre-compute and pass the frozen BJ normal as `n_frame`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..dcr.contact_patch import cone_project_impulse
from ..rigid.body import RigidBody
from .reservoir import (
    estimate_impulse_work,
    k_body,
    modal_energy,
    passivity_scale_gamma,
    support_budget,
)


@dataclass
class MovingSupportResult:
    """Output of one moving-support solve (spec §22 Inv 2 / §21 log fields)."""
    J: NDArray[np.float64]                # accepted support impulse (world)
    qdot_after: NDArray[np.float64]       # modal velocity after back-reaction
    v_after: NDArray[np.float64]          # body linear velocity after impulse
    omega_after: NDArray[np.float64]      # body angular velocity after impulse
    W_support_to_rigid: float             # §10 estimate
    E_support_budget: float               # §11 budget
    gamma_final: float                    # §12 accepted γ
    attempts: int                         # §12 line-search count
    gated_out: bool = False               # true if a causal gate fired


def _check_causal_gates(
    gap: float,
    v_rel_normal: float,
    E_modal_now: float,
    E_modal_peak: float,
    contact_shell_delta: float,
    v_min_closing: float,
    e_modal_cutoff_frac: float,
) -> bool:
    """Spec §14: gate moving-support contact eligibility.

    Returns True ⇒ all gates pass, contact is eligible.

    §14.1 gap:    g ≤ contact_shell_delta
    §14.2 close:  v_rel_normal < −v_min_closing   (closing in n̄ direction)
    §14.3 modal:  E_modal_now > e_modal_cutoff_frac · E_modal_peak
    """
    if gap > contact_shell_delta:
        return False
    if v_rel_normal > -v_min_closing:
        return False
    if E_modal_peak > 0.0 and E_modal_now < e_modal_cutoff_frac * E_modal_peak:
        return False
    return True


def solve_one_contact(
    body: RigidBody,
    r: NDArray[np.float64],
    Phi: NDArray[np.float64],
    n_frame: NDArray[np.float64],
    qdot: NDArray[np.float64],
    q: NDArray[np.float64],
    omega2_diag: NDArray[np.float64],
    *,
    beta: float = 0.1,
    mu: float | None = None,
    gap: float = 0.0,
    max_attempts: int = 3,
    tolerance: float = 1e-6,
    causal_gating: bool = True,
    contact_shell_delta: float = 1e-4,
    v_min_closing: float = 0.044,
    e_modal_cutoff_frac: float = 1e-5,
    E_modal_peak: float | None = None,
    restitution: float = 0.0,
) -> MovingSupportResult:
    """One moving-support AVBD contact (spec §6–§13).

    Mathematics:
        v_p     = v + ω × r            (rigid contact-point vel)
        v_s     = γ · Φ q̇              (γ-scaled moving-support vel, §12)
        v_rel   = v_p − v_s
        K_total = K_body + Φ Φᵀ        (§9 effective mass for combined system)
        J       = −(1 + e) · K_total⁻¹ · v_rel
        J       ← cone_project(J, n_frame, μ)        (§8 Coulomb)
        W       = max(0, ΔE_rigid(J))                 (§10 impulse estimator)

    γ line search (§12): if W > E_budget = β·E_modal, scale γ ← γ·√(B/W)
    and retry up to `max_attempts`. Then apply the accepted impulse:

        v          += J / m
        ω          += I⁻¹ (r × J)
        q̇          -= Φᵀ J                            (§13 transpose-consistent)

    Args:
        body:    Receiver rigid body. Read-only; result returns updated state.
        r:       (3,) lever arm = contact_point − body.position (world frame).
        Phi:     (3, n_modes) modal basis Φ(x_s) at the support point.
        n_frame: (3,) **frozen** contact-frame normal (spec §3.1, §8.1) —
                 BJ normal if available, else n_rest. Must be unit-length.
        qdot:    (n_modes,) current modal velocity.
        q:       (n_modes,) current modal displacement.
        omega2_diag: (n_modes,) diagonal of Ω² (squared natural freqs).
        beta:    Budget fraction (§11 E_budget = β · E_modal_reservoir).
        mu:      Coulomb friction coefficient. Defaults to body.friction.
        gap:     Current contact gap (for §14.1 gate). 0 means at-shell.
        causal_gating: If True, apply §14 gates (returns gated_out=True on fail).
        E_modal_peak: Running max of E_modal for §14.3 numerical cutoff.
                      If None, use current E_modal (which makes §14.3 vacuous).
        restitution: e in J = −(1+e) K_total⁻¹ v_rel. 0 = sticking; 1 = elastic.

    Returns:
        MovingSupportResult — caller is responsible for writing v_after,
        omega_after, qdot_after back into body / coupler state.
    """
    if mu is None:
        mu = float(getattr(body, "friction", 0.5))

    # Snapshot pre-impulse state.
    v = np.asarray(body.velocity[0:3], dtype=np.float64).copy()
    omega = np.asarray(body.velocity[3:6], dtype=np.float64).copy()
    I_inv = body.inertia_world_inv()
    v_p = v + np.cross(omega, r)
    v_s_full = Phi @ qdot

    # Effective mass for the combined rigid + modal system (§9).
    K_body_local = k_body(r, body.mass, I_inv)
    K_total = K_body_local + Phi @ Phi.T

    # Budget from the modal reservoir (§11 first-version formula).
    E_modal_now = modal_energy(qdot, q, omega2_diag)
    E_budget = support_budget(beta, E_modal_now)
    if E_modal_peak is None:
        E_modal_peak = E_modal_now

    # Spec §22 Inv 3: q = q̇ = 0 ⇒ no moving-support contribution. With an
    # empty reservoir there is nothing for the support to spend — the
    # method must degenerate to ordinary AVBD contact, which the caller
    # has already run upstream. Short-circuit with γ = 0, J = 0.
    if E_modal_now <= 1e-18:
        return MovingSupportResult(
            J=np.zeros(3), qdot_after=qdot.copy(),
            v_after=v.copy(), omega_after=omega.copy(),
            W_support_to_rigid=0.0, E_support_budget=0.0,
            gamma_final=0.0, attempts=0, gated_out=False,
        )

    n_unit = np.asarray(n_frame, dtype=np.float64)
    n_norm = float(np.linalg.norm(n_unit))
    if n_norm > 1e-30:
        n_unit = n_unit / n_norm

    # §14 causal gating — only meaningful when the support could push back.
    v_rel_full = v_p - v_s_full
    v_rel_n = float(v_rel_full @ n_unit)
    if causal_gating and not _check_causal_gates(
        gap=gap, v_rel_normal=v_rel_n,
        E_modal_now=E_modal_now, E_modal_peak=E_modal_peak,
        contact_shell_delta=contact_shell_delta,
        v_min_closing=v_min_closing,
        e_modal_cutoff_frac=e_modal_cutoff_frac,
    ):
        return MovingSupportResult(
            J=np.zeros(3), qdot_after=qdot.copy(),
            v_after=v.copy(), omega_after=omega.copy(),
            W_support_to_rigid=0.0, E_support_budget=E_budget,
            gamma_final=0.0, attempts=0, gated_out=True,
        )

    # γ line search (spec §12). Inner solver returns ΔE_rigid; outer caller
    # checks against E_budget and rescales γ if needed. We use a small
    # closure to expose J alongside W to the outer wrapper.
    last = {"J": np.zeros(3)}

    def run_solve(gamma: float) -> float:
        v_s = gamma * v_s_full
        v_rel = v_p - v_s
        J = -(1.0 + restitution) * np.linalg.solve(K_total, v_rel)
        J, _ = cone_project_impulse(J, n_unit, mu)
        last["J"] = J
        # §10 impulse-work estimator, max(0, ·) per spec.
        W_signed = estimate_impulse_work(
            J, v, omega, r, body.mass, I_inv)
        return float(max(0.0, W_signed))

    gamma_final, W_final, attempts = passivity_scale_gamma(
        run_solve, E_budget=E_budget,
        max_attempts=max_attempts, tolerance=tolerance)
    J = last["J"]

    # Apply the impulse to the rigid body and back-react the modal state
    # using the SAME Phi instance (spec §13 / Invariant 5).
    v_after = v + J / body.mass
    omega_after = omega + I_inv @ np.cross(r, J)
    qdot_after = qdot - Phi.T @ J

    return MovingSupportResult(
        J=J, qdot_after=qdot_after,
        v_after=v_after, omega_after=omega_after,
        W_support_to_rigid=W_final, E_support_budget=E_budget,
        gamma_final=gamma_final, attempts=attempts,
        gated_out=False,
    )
