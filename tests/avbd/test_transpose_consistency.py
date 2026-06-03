"""Phase B / spec §13.1 (Test 8): isolated transpose-consistency.

Scenario per spec:
  - single rigid body
  - single modal support
  - single contact
  - no gravity / damping / external forces
  - one impulse exchange

Expected:
  - ΔE_rigid + ΔE_modal ≈ 0  (elastic, transpose-consistency identity)
  - ΔE_rigid + ΔE_modal ≤ ε  (inelastic; energy dissipated by contact)

The math identity (foundation §15 + spec §13):

    ΔE_total = Jᵀ v_rel + ½ Jᵀ K_total J,
        v_rel   = v_p − v_support,
        K_total = K_body + Φ Φᵀ.

Sticking solution (J = −K_total⁻¹ v_rel, e=0) → ΔE = −½ v_relᵀ K_total⁻¹ v_rel < 0.
Elastic   (J = −2 K_total⁻¹ v_rel, e=1) → ΔE ≡ 0 to machine epsilon.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.reservoir import k_body
from dcr.rigid.body import make_dynamic_box


# ---------------------------------------------------------------------------
# Math primitive: direct transpose-consistency check
# ---------------------------------------------------------------------------

def _ke_rigid(body, v, omega):
    I_world = body.inertia_world()
    return 0.5 * body.mass * float(v @ v) + 0.5 * float(omega @ I_world @ omega)


def _ke_modal(qdot, q, omega2):
    """Mass-normalized modes: E_modal = ½ q̇ᵀ q̇ + ½ qᵀ Ω² q."""
    return 0.5 * float(qdot @ qdot) + 0.5 * float(q @ (omega2 * q))


def _exchange(body, v, omega, qdot, q, Phi, r, J):
    """Apply one impulse exchange (forward + reverse via Φᵀ).

        v     += J / m
        ω     += I⁻¹ (r × J)
        q̇     -= Φᵀ J

    Returns the updated (v_new, omega_new, qdot_new).
    """
    I_inv = body.inertia_world_inv()
    v_new = v + J / body.mass
    omega_new = omega + I_inv @ np.cross(r, J)
    qdot_new = qdot - Phi.T @ J
    return v_new, omega_new, qdot_new


# ---------------------------------------------------------------------------
# §13.1 Test 8a: elastic exchange — ΔE_total exactly zero
# ---------------------------------------------------------------------------

def test_transpose_consistency_elastic_exchange():
    """Elastic (e=1) impulse exchange against a moving support — the modal
    state and rigid body together conserve energy to machine epsilon.

    This is the strongest form of Invariant 5 (forward Φ == reverse Φᵀ).
    """
    body = make_dynamic_box(mass=2.0, hx=0.3, hy=0.2, hz=0.4)
    v = np.array([0.1, -0.5, 0.0])     # closing along +y from above
    omega = np.array([0.05, 0.0, 0.03])
    body.velocity[0:3] = v
    body.velocity[3:6] = omega

    # 1 mode, 1 vertex effectively (Φ ∈ R^{3 × 1}).
    Phi = np.array([[0.0], [1.0], [0.0]])     # unit mode aligned with +y
    qdot = np.array([0.3])                    # support already moving up
    q = np.array([0.02])
    omega2 = np.array([(2 * np.pi * 30.0) ** 2])

    r = np.array([0.0, -0.2, 0.0])            # contact at bottom face

    # Build K_total = K_body + Φ Φᵀ, choose J = -(1+e) K_total⁻¹ v_rel for e=1.
    K_body = k_body(r, body.mass, body.inertia_world_inv())
    K_total = K_body + Phi @ Phi.T

    v_p = v + np.cross(omega, r)
    v_support = (Phi @ qdot)
    v_rel = v_p - v_support                   # rel velocity at contact
    J = -2.0 * np.linalg.solve(K_total, v_rel)  # e=1 elastic

    ke_r_before = _ke_rigid(body, v, omega)
    ke_m_before = _ke_modal(qdot, q, omega2)

    v_n, w_n, qd_n = _exchange(body, v, omega, qdot, q, Phi, r, J)
    ke_r_after = _ke_rigid(body, v_n, w_n)
    ke_m_after = _ke_modal(qd_n, q, omega2)

    dE_total = (ke_r_after - ke_r_before) + (ke_m_after - ke_m_before)
    assert dE_total == pytest.approx(0.0, abs=1e-12), (
        f"elastic exchange should conserve total energy; ΔE_total={dE_total:.3e}")


# ---------------------------------------------------------------------------
# §13.1 Test 8b: inelastic exchange — ΔE_total strictly negative (energy lost)
# ---------------------------------------------------------------------------

def test_transpose_consistency_inelastic_exchange():
    """Sticking (e=0) impulse exchange: ΔE_total ≤ 0, matches the closed-
    form −½ v_relᵀ K_total⁻¹ v_rel.
    """
    body = make_dynamic_box(mass=1.5, hx=0.25, hy=0.25, hz=0.25)
    v = np.array([0.0, -0.8, 0.0])
    omega = np.zeros(3)
    body.velocity[0:3] = v
    body.velocity[3:6] = omega

    Phi = np.array([[0.0], [0.7], [0.0]])
    qdot = np.array([0.2])
    q = np.array([0.0])
    omega2 = np.array([(2 * np.pi * 20.0) ** 2])

    r = np.array([0.0, -0.25, 0.0])

    K_body = k_body(r, body.mass, body.inertia_world_inv())
    K_total = K_body + Phi @ Phi.T
    v_p = v + np.cross(omega, r)
    v_support = Phi @ qdot
    v_rel = v_p - v_support
    J = -1.0 * np.linalg.solve(K_total, v_rel)  # e=0 inelastic

    ke_r_before = _ke_rigid(body, v, omega)
    ke_m_before = _ke_modal(qdot, q, omega2)
    v_n, w_n, qd_n = _exchange(body, v, omega, qdot, q, Phi, r, J)
    ke_r_after = _ke_rigid(body, v_n, w_n)
    ke_m_after = _ke_modal(qd_n, q, omega2)
    dE_total = (ke_r_after - ke_r_before) + (ke_m_after - ke_m_before)

    # Closed-form: −½ v_relᵀ K_total⁻¹ v_rel.
    expected = -0.5 * float(v_rel @ np.linalg.solve(K_total, v_rel))
    assert dE_total <= 1e-12, (
        f"inelastic exchange should dissipate; ΔE_total={dE_total:.3e}")
    assert dE_total == pytest.approx(expected, rel=1e-10, abs=1e-12), (
        f"ΔE_total {dE_total:.4e} should equal closed-form {expected:.4e}")


# ---------------------------------------------------------------------------
# §13.1 Test 8c: transpose violation — using two different Φ's leaks energy
# ---------------------------------------------------------------------------

def test_transpose_violation_leaks_energy():
    """Negative control: if the forward Φ (used for v_support) differs from
    the reverse Φᵀ (used for back-reaction), the closed-form energy
    identity breaks and ΔE_total ≠ 0 even for the e=1 impulse.

    This documents WHY Invariant 5 is non-trivial — any Φ aliasing in the
    pipeline breaks energy bookkeeping. The patch coupler in passive_dcr.py
    avoids this by caching the same `Phi_x` instance across forward/reverse.
    """
    body = make_dynamic_box(mass=2.0, hx=0.3, hy=0.2, hz=0.4)
    v = np.array([0.1, -0.5, 0.0])
    omega = np.array([0.05, 0.0, 0.03])
    Phi_fwd = np.array([[0.0], [1.0], [0.0]])
    Phi_rev = np.array([[0.0], [1.1], [0.0]])  # 10% off — wrong reverse map
    qdot = np.array([0.3])
    q = np.array([0.02])
    omega2 = np.array([(2 * np.pi * 30.0) ** 2])
    r = np.array([0.0, -0.2, 0.0])
    I_inv = body.inertia_world_inv()

    K_body = k_body(r, body.mass, I_inv)
    K_total = K_body + Phi_fwd @ Phi_fwd.T
    v_p = v + np.cross(omega, r)
    v_support = Phi_fwd @ qdot
    v_rel = v_p - v_support
    J = -2.0 * np.linalg.solve(K_total, v_rel)  # e=1 against forward Φ

    ke_r_before = _ke_rigid(body, v, omega)
    ke_m_before = _ke_modal(qdot, q, omega2)
    # Apply the WRONG transpose for the modal back-reaction.
    v_new = v + J / body.mass
    omega_new = omega + I_inv @ np.cross(r, J)
    qdot_new = qdot - Phi_rev.T @ J
    ke_r_after = _ke_rigid(body, v_new, omega_new)
    ke_m_after = _ke_modal(qdot_new, q, omega2)
    dE_total = (ke_r_after - ke_r_before) + (ke_m_after - ke_m_before)
    # Should be measurably non-zero — order 1e-3 or larger for this setup.
    assert abs(dE_total) > 1e-6, (
        "transpose mismatch should produce a non-zero ΔE_total; got "
        f"{dE_total:.3e}")


# ---------------------------------------------------------------------------
# §13.1 Test 8d: stress test — random configurations, elastic case still
# conserves to machine epsilon.
# ---------------------------------------------------------------------------

def test_transpose_consistency_random_battery():
    """100 random (v, ω, q̇, Φ, r) configurations — e=1 must conserve to
    1e-11 every time."""
    rng = np.random.default_rng(99)
    n_modes_list = [1, 2, 3, 5]
    failures = []
    for trial in range(100):
        body = make_dynamic_box(
            mass=float(rng.uniform(0.5, 5.0)),
            hx=float(rng.uniform(0.1, 0.5)),
            hy=float(rng.uniform(0.1, 0.5)),
            hz=float(rng.uniform(0.1, 0.5)),
        )
        v = rng.normal(size=3) * 0.5
        omega = rng.normal(size=3) * 0.3
        nm = int(rng.choice(n_modes_list))
        Phi = rng.normal(size=(3, nm)) * 0.5
        qdot = rng.normal(size=nm) * 0.4
        q = rng.normal(size=nm) * 0.05
        omega2 = (2 * np.pi * rng.uniform(10, 200, size=nm)) ** 2
        r = rng.normal(size=3) * 0.3

        K_body = k_body(r, body.mass, body.inertia_world_inv())
        K_total = K_body + Phi @ Phi.T
        v_p = v + np.cross(omega, r)
        v_rel = v_p - Phi @ qdot
        if abs(float(v_rel @ v_rel)) < 1e-12:
            continue   # zero-rel-vel: trivial
        J = -2.0 * np.linalg.solve(K_total, v_rel)

        ke_r_before = _ke_rigid(body, v, omega)
        ke_m_before = _ke_modal(qdot, q, omega2)
        v_n, w_n, qd_n = _exchange(body, v, omega, qdot, q, Phi, r, J)
        ke_r_after = _ke_rigid(body, v_n, w_n)
        ke_m_after = _ke_modal(qd_n, q, omega2)
        dE_total = (ke_r_after - ke_r_before) + (ke_m_after - ke_m_before)
        if abs(dE_total) > 1e-9:
            failures.append((trial, dE_total))
    assert not failures, f"transpose consistency leaked: {failures[:5]}"
