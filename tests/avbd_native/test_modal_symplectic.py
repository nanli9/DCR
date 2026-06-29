"""SDOF validation of the shared implicit-midpoint modal stepper.

Confirms the energy-conserving claims behind the symplectic modal path:
  1. undamped free vibration conserves modal energy (vs backward Euler bleeding
     it to ~0),
  2. a lightly damped mode decays at the PHYSICAL rate exp(-2ζω t),
  3. the integrator is A-stable on a 24 kHz stiff mode (ωh ≈ 300 ≫ 2) where an
     explicit symplectic scheme would blow up.

See dcr/modal/symplectic_stepper.py and
prompts/symplectic_modal_integrator_prompt.md.
"""
from __future__ import annotations

import numpy as np

from dcr.modal.symplectic_stepper import (
    modal_midpoint_coeffs,
    modal_midpoint_commit,
)


def _step_midpoint(q, qdot, mass, stiff, damp, h, n_steps):
    """Free (F=0) SDOF rollout under implicit midpoint. Returns q/qdot history."""
    q = np.array([q], dtype=np.float64)
    qdot = np.array([qdot], dtype=np.float64)
    mass = np.array([mass]); stiff = np.array([stiff]); damp = np.array([damp])
    hist_q = [float(q[0])]
    hist_qd = [float(qdot[0])]
    for _ in range(n_steps):
        _, _, q_star, _ = modal_midpoint_coeffs(q, qdot, mass, stiff, damp, h)
        q_next = q_star                          # no contact force ⇒ q = q_star
        qdot = modal_midpoint_commit(q_next, q, qdot, h)
        q = q_next
        hist_q.append(float(q[0]))
        hist_qd.append(float(qdot[0]))
    return np.array(hist_q), np.array(hist_qd)


def _step_be(q, qdot, mass, stiff, damp, h, n_steps):
    """Free SDOF rollout under backward Euler (the dissipative reference)."""
    M, K, D = mass, stiff, damp
    inv_h2 = 1.0 / (h * h)
    hist_E = []
    for _ in range(n_steps):
        q_tilde = q + h * qdot
        H = M * inv_h2 + D / h + K
        rhs = (M * inv_h2) * q_tilde + (D / h) * q
        q_next = rhs / H
        qdot = (q_next - q) / h
        q = q_next
    return q, qdot


def _energy(q, qdot, omega):
    return 0.5 * qdot * qdot + 0.5 * omega * omega * q * q


def test_undamped_energy_conserved():
    # Low mode ~20 Hz, no damping; implicit midpoint conserves the quadratic
    # energy invariant of the linear oscillator exactly (det of amplification = 1).
    omega = 2.0 * np.pi * 20.0
    h = 1.0 / 120.0 / 4.0                          # substep dt (avbd_substeps=4)
    n = int(round(1.0 / h))                        # 1 s
    q, qd = _step_midpoint(1.0, 0.0, 1.0, omega * omega, 0.0, h, n)
    E0 = _energy(q[0], qd[0], omega)
    E1 = _energy(q[-1], qd[-1], omega)
    assert abs(E1 / E0 - 1.0) < 1e-3              # conserved (typically ~1e-9)


def test_damped_decays_at_physical_rate_unlike_be():
    # 20 Hz, ζ=0.012. Physical energy decay over 1 s is exp(-2ζω·t); midpoint
    # tracks it, backward Euler over-dissipates to ~0 (the bug we are fixing).
    omega = 2.0 * np.pi * 20.0
    zeta = 0.012
    h = 1.0 / 120.0 / 4.0
    n = int(round(1.0 / h))
    K = omega * omega
    D = 2.0 * zeta * omega
    q, qd = _step_midpoint(1.0, 0.0, 1.0, K, D, h, n)
    ratio_mid = _energy(q[-1], qd[-1], omega) / _energy(q[0], qd[0], omega)

    qb, qdb = _step_be(1.0, 0.0, 1.0, K, D, h, n)
    E0 = _energy(1.0, 0.0, omega)
    ratio_be = _energy(qb, qdb, omega) / E0

    physical = np.exp(-2.0 * zeta * omega * 1.0)   # ≈ 0.049
    # midpoint within a factor of ~2 of the physical decay …
    assert 0.5 * physical < ratio_mid < 2.0 * physical
    # … while backward Euler has bled essentially all of it away.
    assert ratio_be < 0.1 * ratio_mid


def test_stiff_mode_A_stable():
    # 24 kHz mode: ωh ≈ 2π·24000·2.08e-3 ≈ 314 ≫ 2. Explicit symplectic blows up
    # here; implicit midpoint must stay bounded.
    omega = 2.0 * np.pi * 24000.0
    zeta = 0.02
    h = 1.0 / 120.0 / 4.0
    K = omega * omega
    D = 2.0 * zeta * omega
    q, qd = _step_midpoint(1e-6, 0.0, 1.0, K, D, h, 400)
    assert np.all(np.isfinite(q))
    assert np.abs(q).max() <= 10.0 * 1e-6          # no growth


def test_commit_is_scheme_consistent():
    # The midpoint velocity reconstruction must be 2(q⁺−qⁿ)/h − q̇ⁿ, not the BE
    # difference; check the helper returns exactly that.
    q_n = np.array([0.3]); qdot_n = np.array([-1.1]); q_next = np.array([0.5])
    h = 0.002
    out = modal_midpoint_commit(q_next, q_n, qdot_n, h)
    assert np.allclose(out, 2.0 * (q_next - q_n) / h - qdot_n)
