"""Unit + integration tests for the IIR exact-resonator modal step
(paper Eq. 10 in state-space form, used by ReducedCoupledAVBDCoupler for
the q_d dynamic component).

Tests:

  Test 1. test_iir_free_response       — F=0 closed-form match.
  Test 2. test_iir_constant_force      — F=const closed-form match.
  Test 3. test_iir_static_limit        — slow loading → q → F/k.
  Test 4. test_iir_contact_sign        — physical sign of support
                                          deflection under floor load.
  Test 5. test_iir_no_postkick         — coupled-IIR mode never invokes
                                          a post-step DCR Δv kick.
  Test 6. test_iir_vs_old_dcr          — matched-impulse comparison: IIR
                                          and James-Pai Eq. 10 agree on
                                          peak and zero-crossing of q(t).
  Test 7. test_iir_energy_sanity       — modal energy bounded over impact
                                          + ringdown; trailing damping ≥ 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _per_mode_setup(omega_val: float = 1000.0, zeta_val: float = 0.01,
                    mass_val: float = 1.0,
                    q0: float = 1.0e-4, qdot0: float = 0.0):
    omega = np.array([omega_val], dtype=np.float64)
    zeta  = np.array([zeta_val],  dtype=np.float64)
    mass  = np.array([mass_val],  dtype=np.float64)
    q     = np.array([q0],        dtype=np.float64)
    qdot  = np.array([qdot0],     dtype=np.float64)
    return omega, zeta, mass, q, qdot


def _analytic_free_response(q0: float, qdot0: float,
                            omega: float, zeta: float, h: float
                            ) -> tuple[float, float]:
    """Exact analytical free response of underdamped damped oscillator."""
    a = zeta * omega
    wd = omega * np.sqrt(1.0 - zeta * zeta)
    E = np.exp(-a * h)
    c = np.cos(wd * h)
    s = np.sin(wd * h)
    q_t  = E * ((c + (a / wd) * s) * q0 + (s / wd) * qdot0)
    qd_t = E * (-(omega * omega / wd) * s * q0
                + (c - (a / wd) * s) * qdot0)
    return float(q_t), float(qd_t)


# ---------------------------------------------------------------------------
# Test 1: free response
# ---------------------------------------------------------------------------

def test_iir_free_response():
    """F=0 → q_{n+1} = q_free, qdot_{n+1} = qdot_free matches the
    analytical damped-oscillator formula to within machine precision.
    """
    from dcr.modal.exact_resonator import (
        exact_modal_step_precompute, dynamic_compliance_step_precompute)

    omega, zeta, mass, q, qd = _per_mode_setup(
        omega_val=1000.0, zeta_val=0.01, mass_val=1.0,
        q0=1.0e-4, qdot0=0.0)
    h = 1.0 / 120.0 / 16.0

    # Per-mode form
    q_free, qd_free, S, T = exact_modal_step_precompute(
        q, qd, omega, zeta, mass, h)
    q_exp, qd_exp = _analytic_free_response(q[0], qd[0],
                                            omega[0], zeta[0], h)
    assert abs(q_free[0] - q_exp) < 1.0e-15, \
        f"per-mode q_free {q_free[0]:.12e} ≠ analytic {q_exp:.12e}"
    assert abs(qd_free[0] - qd_exp) < 1.0e-12, \
        f"per-mode qdot_free {qd_free[0]:.12e} ≠ analytic {qd_exp:.12e}"

    # Matrix-exp form on the same single-mode diagonal system
    Mq = np.diag(mass)
    Kq = np.diag(mass * omega ** 2)
    Dq = np.diag(2.0 * mass * zeta * omega)
    q_free_me, qd_free_me, S_h, T_h = dynamic_compliance_step_precompute(
        q, qd, Mq, Kq, Dq, h)
    assert abs(q_free_me[0] - q_exp) < 1.0e-13, \
        f"matrix-exp q_free {q_free_me[0]:.12e} ≠ analytic {q_exp:.12e}"
    assert abs(qd_free_me[0] - qd_exp) < 1.0e-10, \
        f"matrix-exp qdot_free {qd_free_me[0]:.12e} ≠ analytic {qd_exp:.12e}"


# ---------------------------------------------------------------------------
# Test 2: constant force
# ---------------------------------------------------------------------------

def test_iir_constant_force():
    """For constant F, q_{n+1} = q_free + S·F and qdot_{n+1} = qdot_free + T·F.
    Verify by stepping a known F and comparing against scipy.integrate.solve_ivp.
    """
    pytest.importorskip("scipy")
    from scipy.integrate import solve_ivp
    from dcr.modal.exact_resonator import exact_modal_step_precompute

    omega, zeta, mass, q, qd = _per_mode_setup(
        omega_val=1000.0, zeta_val=0.01, mass_val=1.0,
        q0=1.0e-4, qdot0=0.0)
    h = 1.0 / 120.0 / 16.0
    F = 1.5    # N (per mode)

    q_free, qd_free, S, T = exact_modal_step_precompute(
        q, qd, omega, zeta, mass, h)
    q_iir  = q_free[0]  + S[0] * F
    qd_iir = qd_free[0] + T[0] * F

    # Reference: solve_ivp on the linear ODE m·q̈ + d·q̇ + k·q = F.
    m = mass[0]; w = omega[0]; z = zeta[0]
    k = m * w * w; d = 2 * m * z * w
    def ode(t, y):
        return [y[1], (F - d * y[1] - k * y[0]) / m]
    sol = solve_ivp(ode, [0.0, h], [q[0], qd[0]], method="DOP853",
                    rtol=1e-12, atol=1e-14)
    q_ref  = float(sol.y[0, -1])
    qd_ref = float(sol.y[1, -1])

    assert abs(q_iir - q_ref) < 5.0e-11, \
        f"q mismatch: IIR {q_iir:.6e} vs DOP853 {q_ref:.6e}"
    assert abs(qd_iir - qd_ref) < 5.0e-7, \
        f"qdot mismatch: IIR {qd_iir:.6e} vs DOP853 {qd_ref:.6e}"


# ---------------------------------------------------------------------------
# Test 3: static limit
# ---------------------------------------------------------------------------

def test_iir_static_limit():
    """For ω·h ≪ 1 (slow load relative to mode period), the
    quasi-static compliance dominates: many small substeps applying
    constant F drive q → F/k.
    """
    from dcr.modal.exact_resonator import exact_modal_step_precompute

    # ω = 100 rad/s, h ≈ 1 ms → ω·h ≈ 0.1 — slow loading regime.
    # ζ = 0.20 keeps the transient short (~5 periods) so the
    # post-settling check is at a true steady state.
    omega = np.array([100.0])
    zeta  = np.array([0.20])
    mass  = np.array([1.0])
    h     = 1.0e-3
    F     = 10.0
    k     = mass[0] * omega[0] ** 2

    q = np.array([0.0])
    qd = np.array([0.0])
    for _ in range(3000):
        q_free, qd_free, S, T = exact_modal_step_precompute(
            q, qd, omega, zeta, mass, h)
        q = q_free + S * F
        qd = qd_free + T * F

    rel_err = abs(q[0] - F / k) / (F / k)
    assert rel_err < 1.0e-6, \
        f"static limit: q={q[0]:.6e}, F/k={F/k:.6e}, rel_err={rel_err:.3e}"
    # Residual qdot from heavily-damped transient: should decay to
    # negligible amplitude. Threshold loose enough to absorb
    # floating-point tail.
    assert abs(qd[0]) < 1.0e-9, \
        f"static limit: qdot should be ≈ 0, got {qd[0]:.6e}"


# ---------------------------------------------------------------------------
# Test 4: contact sign
# ---------------------------------------------------------------------------

def test_iir_contact_sign():
    """Single-mode support with U_y > 0 at the contact point. A box of
    mass m sits on the support: floor anchor = floor_y_rest + U_y·q.
    Gravity pulls the box DOWN; the constraint requires the support to
    deflect DOWNWARD too, which (since U_y > 0) means q < 0.

    Verify: after many substeps with constant downward force, q is
    negative, monotonic, and converges to F/k where F is the projected
    modal force from the floor contact.

    This is the gatekeeper for the sign of `g_q -= f · U_y` in
    reduced_coupled_avbd.py:557.
    """
    from dcr.modal.exact_resonator import exact_modal_step_precompute

    # Single mode, U_y at corner = 0.5 m/√m (unitless given mass-normalized).
    omega = np.array([500.0])
    zeta  = np.array([0.02])
    mass  = np.array([1.0])
    h     = 1.0 / 120.0 / 16.0
    k     = mass[0] * omega[0] ** 2

    U_y = 0.5     # positive: q < 0 deflects support DOWN
    m_box = 0.5
    g = 9.81

    # The floor contact's f (magnitude of compressive force) equals
    # m_box·g at static equilibrium. Modal force F = -f · U_y
    # (from g_q -= f · U_y → F_external = +f · U_y when q convention
    # flips; the sign test is exactly verifying we got this right).
    #
    # If sign is correct: at static eq, k·q = F_modal → q < 0
    # If sign is wrong:   q > 0 (support deflects UP, which is unphysical)
    F_normal = m_box * g            # downward gravity load = upward normal force on support
    F_modal  = -F_normal * U_y       # see reduced_coupled_avbd.py:544–557 derivation

    q = np.array([0.0])
    qd = np.array([0.0])
    for _ in range(5000):
        q_free, qd_free, S, T = exact_modal_step_precompute(
            q, qd, omega, zeta, mass, h)
        q  = q_free + S * F_modal
        qd = qd_free + T * F_modal

    q_static_predicted = F_modal / k    # should be negative
    assert q[0] < 0, f"expected q < 0 (support deflects down), got q={q[0]:.6e}"
    rel_err = abs(q[0] - q_static_predicted) / abs(q_static_predicted)
    assert rel_err < 1.0e-3, \
        f"q={q[0]:.6e} vs predicted {q_static_predicted:.6e} (rel_err {rel_err:.3e})"


# ---------------------------------------------------------------------------
# Test 5: no post-kick in coupled-IIR mode
# ---------------------------------------------------------------------------

def test_iir_no_postkick_in_coupled_mode():
    """Across a full impactor-on-shelf run in --mode coupled_iir_modal,
    the coupler's `dcr_postkick_calls` counter must stay 0. The Δv kick
    is the architecturally-rejected approach; the IIR mode reaches modal
    response through the coupled Schur solve, not via after-the-fact
    velocity injection.

    Also asserts that the legacy `dcr_couplers` list on the world is
    empty under coupled-AVBD: there's no ModalDCRCoupler attached.
    """
    pytest.skip("reduced coupler removed (native dual-solver Stage 6); the "
                "coupled-mode toy scene is retired — native path covers this")
    pytest.importorskip("warp")
    from scenes.reduced_coupled_toy_minimum import build_toy_scene_1

    h = build_toy_scene_1(iterations=8, mass=0.05, avbd_substeps=8,
                          youngs=2.0e10,
                          rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6)
    c = h.coupler

    # No legacy DCR coupler attached.
    dcr_couplers = getattr(h.world, "dcr_couplers", None) or []
    assert len(dcr_couplers) == 0, (
        f"--mode coupled_iir_modal should not attach any ModalDCRCoupler; "
        f"found {len(dcr_couplers)}")

    for _ in range(120):
        h.world.step()

    assert c.dcr_postkick_calls == 0, (
        f"dcr_postkick_calls = {c.dcr_postkick_calls} > 0: legacy post-kick "
        "path was invoked under --mode coupled_iir_modal. Rigid bodies must "
        "feel modal response only through the coupled contact, not via Δv.")


# ---------------------------------------------------------------------------
# Test 6: IIR vs old DCR (James-Pai Eq. 10) qualitative match
# ---------------------------------------------------------------------------

def test_iir_vs_old_dcr_qualitative():
    """For the same prescribed contact-impulse history applied to the
    same single-mode oscillator, the new exact-resonator IIR and the
    legacy James-Pai IIR (paper Eq. 10) should produce qualitatively
    identical modal trajectories: peak amplitude within 10%, period
    within 5%.

    This is the "we didn't change the physics, only the wiring" test.
    """
    from dcr.modal.exact_resonator import exact_modal_step_precompute

    # Single-mode oscillator: ω = 800 rad/s (T ≈ 7.85 ms), ζ = 0.005.
    omega = np.array([800.0])
    zeta  = np.array([0.005])
    mass  = np.array([1.0])
    k     = mass[0] * omega[0] ** 2

    # Substep close to Nyquist (paper §4.1: T = π / 2 ω_max ≈ 1.96 ms)
    h = np.pi / (2.0 * omega[0])
    n_steps = 200

    # ---- New IIR (exact resonator) — impulse-driven ----
    # Apply impulse Δp = 0.01 N·s at step 0 by setting initial qdot.
    impulse = 0.01
    q_iir  = np.array([0.0])
    qd_iir = np.array([impulse / mass[0]])  # initial velocity from impulse
    traj_iir = np.zeros(n_steps)
    for k_ in range(n_steps):
        traj_iir[k_] = q_iir[0]
        q_free, qd_free, _S, _T = exact_modal_step_precompute(
            q_iir, qd_iir, omega, zeta, mass, h)
        q_iir = q_free
        qd_iir = qd_free

    # ---- Legacy James-Pai IIR (paper Eq. 10) ----
    a = zeta[0] * omega[0]
    wd = omega[0] * np.sqrt(1.0 - zeta[0] ** 2)
    exp_term = np.exp(-a * h)
    a1 = 2.0 * exp_term * np.cos(wd * h)
    a2 = exp_term * exp_term
    ar = exp_term * np.sin(wd * h) / wd

    q_prev  = 0.0
    q_prev2 = 0.0
    traj_dcr = np.zeros(n_steps)
    for k_ in range(n_steps):
        if k_ == 0:
            # Apply impulse at substep 0.
            q_new = a1 * q_prev - a2 * q_prev2 + ar * impulse / mass[0]
        else:
            q_new = a1 * q_prev - a2 * q_prev2
        traj_dcr[k_] = q_prev
        q_prev2 = q_prev
        q_prev  = q_new

    # Peak amplitude comparison: within 10%.
    peak_iir = float(np.max(np.abs(traj_iir)))
    peak_dcr = float(np.max(np.abs(traj_dcr)))
    rel = abs(peak_iir - peak_dcr) / max(peak_iir, peak_dcr, 1e-30)
    assert rel < 0.10, (
        f"peak |q| mismatch: IIR {peak_iir:.3e}, DCR {peak_dcr:.3e} "
        f"(rel {100*rel:.1f}% > 10%)")

    # Zero-crossing time comparison: within 5%.
    def first_zero_cross_idx(x):
        for k_ in range(1, len(x)):
            if x[k_] * x[k_ - 1] < 0:
                return k_
        return -1

    iir_zc = first_zero_cross_idx(traj_iir)
    dcr_zc = first_zero_cross_idx(traj_dcr)
    assert iir_zc > 0 and dcr_zc > 0, \
        f"no zero crossings found (iir={iir_zc}, dcr={dcr_zc})"
    rel_zc = abs(iir_zc - dcr_zc) / max(iir_zc, dcr_zc)
    assert rel_zc < 0.05, (
        f"zero crossing index: IIR {iir_zc}, DCR {dcr_zc} "
        f"(rel {100*rel_zc:.1f}% > 5%)")


# ---------------------------------------------------------------------------
# Test 7: energy sanity
# ---------------------------------------------------------------------------

def test_iir_energy_sanity():
    """Across a full impactor-on-shelf run in IIR mode:
      (a) the per-substep modal energy (½ qdot^T Mq qdot + ½ q^T Kq q)
          never exceeds 100 × the value at first ground contact,
      (b) trailing 30 frames show positive damping power (energy
          monotonically dissipated).
    """
    pytest.skip("reduced coupler removed (native dual-solver Stage 6); the "
                "coupled-mode toy scene is retired — native path covers this")
    pytest.importorskip("warp")
    from scenes.reduced_coupled_toy_minimum import build_toy_scene_1

    h = build_toy_scene_1(iterations=8, mass=0.05, avbd_substeps=16,
                          youngs=2.0e10,
                          rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6)
    c = h.coupler

    # Walk through; find first-contact energy and track peak/min damping.
    E_first_contact = None
    E_peak = 0.0
    damp_trail = []
    for k_ in range(240):
        h.world.step()
        E_modal = c.last_modal_KE + c.last_modal_PE
        if E_first_contact is None and E_modal > 1.0e-15:
            E_first_contact = E_modal
        if E_first_contact is not None:
            E_peak = max(E_peak, E_modal)
        if k_ >= 210:
            damp_trail.append(c.last_damp_power)

    assert E_first_contact is not None and E_first_contact > 0, \
        "no first-contact energy detected — scene never made contact?"
    assert E_peak < 100.0 * E_first_contact, (
        f"E_peak = {E_peak:.3e} > 100 × E_first_contact = "
        f"{100*E_first_contact:.3e} — energy growing unbounded.")

    # Damping power: qdot^T Dq qdot. Should be ≥ 0 since Dq is PSD.
    damp_arr = np.asarray(damp_trail)
    n_pos = int((damp_arr >= -1e-30).sum())
    assert n_pos == len(damp_arr), (
        f"trailing damping power: {len(damp_arr) - n_pos} frames "
        f"with negative damp power — Dq should be PSD.")
