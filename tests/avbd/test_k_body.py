"""Phase B / spec §10 (Test 6): impulse-work estimator must match the
direct before/after kinetic energy delta for a single rigid body and a
known impulse.

    ΔE_rigid(J) = Jᵀ v_p_before + ½ Jᵀ K_body J,    v_p = v + ω × r
    K_body      = (1/m) I₃ + [r]×ᵀ I⁻¹ [r]×

Reference: dcr/avbd/reservoir.py
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.reservoir import (
    cross_matrix,
    estimate_impulse_work,
    k_body,
    support_work,
)
from dcr.rigid.body import make_dynamic_box


def _ke(m: float, v: np.ndarray, omega: np.ndarray, I_world: np.ndarray) -> float:
    return 0.5 * m * float(v @ v) + 0.5 * float(omega @ I_world @ omega)


def test_cross_matrix_basic():
    """[r]× v should equal r × v."""
    rng = np.random.default_rng(0)
    for _ in range(20):
        r = rng.normal(size=3)
        v = rng.normal(size=3)
        assert np.allclose(cross_matrix(r) @ v, np.cross(r, v))


def test_cross_matrix_skew_symmetric():
    """[r]×ᵀ = −[r]× is the identity §10 relies on."""
    rng = np.random.default_rng(1)
    r = rng.normal(size=3)
    R = cross_matrix(r)
    assert np.allclose(R.T, -R)


def test_k_body_symmetric_psd():
    """K_body must be symmetric and positive (semi-)definite — it represents
    the inverse effective mass at the contact point."""
    box = make_dynamic_box(mass=2.0, hx=0.3, hy=0.2, hz=0.4)
    I_inv = box.inertia_world_inv()
    rng = np.random.default_rng(2)
    for _ in range(10):
        r = rng.normal(size=3) * 0.5
        K = k_body(r, box.mass, I_inv)
        assert np.allclose(K, K.T, atol=1e-12)
        eigvals = np.linalg.eigvalsh(K)
        assert eigvals.min() > -1e-12, eigvals


def test_k_body_zero_offset_reduces_to_1_over_m():
    """At r=0 the angular term vanishes and K_body = (1/m) I₃."""
    box = make_dynamic_box(mass=3.7, hx=0.5, hy=0.5, hz=0.5)
    K = k_body(np.zeros(3), box.mass, box.inertia_world_inv())
    assert np.allclose(K, (1.0 / 3.7) * np.eye(3))


def test_impulse_work_matches_direct_delta_ke_pure_linear():
    """Single impulse at COM (r=0): only linear KE changes.
    ΔKE_direct = ½ m (|v+J/m|² − |v|²)."""
    box = make_dynamic_box(mass=2.0, hx=0.3, hy=0.2, hz=0.4)
    v = np.array([0.1, -0.2, 0.05])
    omega = np.array([0.4, -0.1, 0.2])
    box.velocity[0:3] = v
    box.velocity[3:6] = omega
    I_world = box.inertia_world()
    I_inv = box.inertia_world_inv()

    J = np.array([1.5, 0.0, -0.7])
    r = np.zeros(3)

    ke_before = _ke(box.mass, v, omega, I_world)
    v_after = v + J / box.mass
    omega_after = omega + I_inv @ np.cross(r, J)
    ke_after = _ke(box.mass, v_after, omega_after, I_world)
    dKE_direct = ke_after - ke_before

    dKE_est = estimate_impulse_work(
        J, v, omega, r, box.mass, I_inv)

    assert dKE_est == pytest.approx(dKE_direct, rel=1e-10, abs=1e-12)


def test_impulse_work_matches_direct_delta_ke_offset():
    """Single impulse at offset r ≠ 0: both linear and angular KE change.
    Must still match the direct delta exactly (§10.1 identity is exact, not
    a Taylor expansion)."""
    box = make_dynamic_box(mass=2.0, hx=0.3, hy=0.2, hz=0.4)
    v = np.array([0.5, -0.3, 0.1])
    omega = np.array([0.2, 0.7, -0.5])
    box.velocity[0:3] = v
    box.velocity[3:6] = omega
    I_world = box.inertia_world()
    I_inv = box.inertia_world_inv()

    J = np.array([-0.4, 1.2, 0.6])
    r = np.array([0.3, -0.2, 0.4])

    ke_before = _ke(box.mass, v, omega, I_world)
    v_after = v + J / box.mass
    omega_after = omega + I_inv @ np.cross(r, J)
    ke_after = _ke(box.mass, v_after, omega_after, I_world)
    dKE_direct = ke_after - ke_before

    dKE_est = estimate_impulse_work(
        J, v, omega, r, box.mass, I_inv)

    assert dKE_est == pytest.approx(dKE_direct, rel=1e-10, abs=1e-12)


def test_impulse_work_random_battery():
    """Stress test: 100 random (J, r, v, ω) tuples, all must agree with
    the direct ΔKE to floating-point tolerance. This is the foundational
    sanity check for the entire §22 invariant 2 chain."""
    rng = np.random.default_rng(42)
    box = make_dynamic_box(mass=1.7, hx=0.5, hy=0.3, hz=0.4)
    I_world = box.inertia_world()
    I_inv = box.inertia_world_inv()
    for _ in range(100):
        v = rng.normal(size=3) * 0.5
        omega = rng.normal(size=3) * 0.3
        J = rng.normal(size=3) * 2.0
        r = rng.normal(size=3) * 0.4
        ke_b = _ke(box.mass, v, omega, I_world)
        v_a = v + J / box.mass
        w_a = omega + I_inv @ np.cross(r, J)
        ke_a = _ke(box.mass, v_a, w_a, I_world)
        dKE_direct = ke_a - ke_b
        dKE_est = estimate_impulse_work(J, v, omega, r, box.mass, I_inv)
        assert dKE_est == pytest.approx(dKE_direct, rel=1e-9, abs=1e-12)


def test_support_work_sequential_two_impulses():
    """`support_work` accumulates ΔKE for a sequence of impulses with
    intermediate velocity updates — should equal the direct ΔKE between
    pre- and post-sequence kinetic energies (with max(0, ·) clamp)."""
    rng = np.random.default_rng(7)
    box = make_dynamic_box(mass=2.5, hx=0.3, hy=0.4, hz=0.5)
    I_world = box.inertia_world()
    I_inv = box.inertia_world_inv()
    v0 = rng.normal(size=3) * 0.2
    w0 = rng.normal(size=3) * 0.1
    J1 = np.array([0.5, 0.2, -0.1])
    r1 = np.array([0.1, 0.0, 0.0])
    J2 = np.array([-0.3, 0.4, 0.2])
    r2 = np.array([0.0, 0.2, -0.1])

    ke_pre = _ke(box.mass, v0, w0, I_world)
    v1 = v0 + J1 / box.mass
    w1 = w0 + I_inv @ np.cross(r1, J1)
    v2 = v1 + J2 / box.mass
    w2 = w1 + I_inv @ np.cross(r2, J2)
    ke_post = _ke(box.mass, v2, w2, I_world)
    dKE_direct = max(0.0, ke_post - ke_pre)

    W = support_work([J1, J2], v0, w0, [r1, r2], box.mass, I_inv)
    assert W == pytest.approx(dKE_direct, rel=1e-10, abs=1e-12)
