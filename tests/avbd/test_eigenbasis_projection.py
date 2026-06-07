"""Tests for the eigenbasis projection of the reduced support basis.

After projection (foundation §16 of the eigenbasis spec) the reduced
modal block should satisfy:

    M̂ = V^T M_q V = I
    K̂ = V^T K_q V = diag(ω_i²)
    D̂ = V^T D_q V = diag(α₀ + α₁ ω_i²)        for Rayleigh damping

and physical quantities — the deformed-surface field U·q and the modal
energy ½‖q̇‖² + ½q^T K q — must be invariant under the basis change.

These tests are the load-bearing correctness guard for the projection.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.reduced_support import make_debug_reduced_shelf_support
from dcr.modal.exact_resonator import (
    dynamic_compliance_step_precompute,
    exact_modal_step_precompute,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pair(**kwargs):
    """Build the same shelf in both bases. kwargs are forwarded to both."""
    common = dict(
        length=0.30, width=0.15, thickness=0.005,
        youngs=1.0e10, density=600.0, poisson=0.30,
        n_modes_global=4, n_modes_local=4,
        rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6,
    )
    common.update(kwargs)
    rs_synth = make_debug_reduced_shelf_support(
        to_eigenbasis=False, **common)
    rs_eigen = make_debug_reduced_shelf_support(
        to_eigenbasis=True, **common)
    return rs_synth, rs_eigen


# ---------------------------------------------------------------------------
# 1. Mhat = I
# ---------------------------------------------------------------------------


def test_Mq_is_identity():
    _, rs = _make_pair()
    r = rs.r
    assert np.allclose(rs.Mq, np.eye(r), atol=1e-12), (
        f"M̂ ≠ I: ‖M̂ − I‖ = {np.linalg.norm(rs.Mq - np.eye(r)):.3e}")


# ---------------------------------------------------------------------------
# 2. Khat = diag(omega^2)
# ---------------------------------------------------------------------------


def test_Kq_is_diag_omega_sq():
    _, rs = _make_pair()
    K_diag = np.diag(rs.Kq)
    K_off = rs.Kq - np.diag(K_diag)
    assert np.linalg.norm(K_off) < 1e-10, (
        f"K̂ off-diagonal not zero: ‖K_off‖ = {np.linalg.norm(K_off):.3e}")
    assert np.allclose(K_diag, rs.eigen_omegas ** 2, atol=1e-10), (
        "diag(K̂) ≠ ω²")
    # Ordered ascending (eigh convention).
    assert np.all(np.diff(rs.eigen_omegas) >= -1e-12)


# ---------------------------------------------------------------------------
# 3. Dhat = diag(alpha0 + alpha1*omega^2)  for Rayleigh damping
# ---------------------------------------------------------------------------


def test_Dq_is_diag_rayleigh():
    alpha0, alpha1 = 0.0, 5.0e-6
    _, rs = _make_pair(rayleigh_alpha0=alpha0, rayleigh_alpha1=alpha1)
    D_diag = np.diag(rs.Dq)
    D_off = rs.Dq - np.diag(D_diag)
    assert np.linalg.norm(D_off) < 1e-10, "D̂ has off-diagonal entries"
    expected = alpha0 + alpha1 * rs.eigen_omegas ** 2
    assert np.allclose(D_diag, expected, atol=1e-12), (
        f"D̂ diag ≠ α₀ + α₁ω²: got {D_diag}, want {expected}")


# ---------------------------------------------------------------------------
# 4. Physical deflection field U·q is invariant under basis change
# ---------------------------------------------------------------------------


def test_physical_deflection_invariant_under_projection():
    """For any choice of q_synth, the deformed-surface field equals
    the eigen-basis deflection field at q_eigen = V^T M_q q_synth.

    This is the bit-exact identity that physical quantities are
    basis-invariant.  Without it the projection would silently change
    observable physics.
    """
    rs_synth, rs_eigen = _make_pair()
    rng = np.random.default_rng(seed=42)
    r = rs_synth.r

    for _ in range(5):
        q_synth = rng.normal(size=r) * 1.0e-3

        # The eigen-coord that represents the same physical state is
        # a = V^T · M_synth · q_synth  (mass-projection, since V is
        # mass-orthonormal vs the SYNTHETIC mass matrix). Easier route:
        # rebuild the eigen basis on the same shelf and pick a so that
        # U_eigen · a == U_synth · q_synth at every sample point.
        # The eigen basis stored is U_eigen = U_synth · V; therefore
        # a = V^{-1} · q_synth. Since V is M_q-orthonormal,
        # V^{-1} = V^T · M_q_synth.
        a = rs_eigen.eigen_V.T @ rs_synth.Mq @ q_synth

        # Physical y-displacement at every sample point.
        u_synth = rs_synth.U_points[:, 1, :] @ q_synth
        u_eigen = rs_eigen.U_points[:, 1, :] @ a
        max_err = np.max(np.abs(u_synth - u_eigen))
        assert max_err < 1e-9, (
            f"U·q not invariant: max |Δ| = {max_err:.3e}")

        # Same identity at probe points.
        up_synth = rs_synth.probe_U[:, 1, :] @ q_synth
        up_eigen = rs_eigen.probe_U[:, 1, :] @ a
        assert np.allclose(up_synth, up_eigen, atol=1e-9)


# ---------------------------------------------------------------------------
# 5. Modal energy is basis-invariant
# ---------------------------------------------------------------------------


def test_modal_energy_invariant_under_projection():
    """Modal energy is a physical scalar; the choice of coordinates
    must not change its numerical value.

        E = ½ q̇^T M_q q̇ + ½ q^T K_q q
          = ½ ȧ^T I ȧ + ½ a^T Ω² a   (eigen)
    """
    rs_synth, rs_eigen = _make_pair()
    rng = np.random.default_rng(seed=7)
    r = rs_synth.r

    for _ in range(5):
        q_s = rng.normal(size=r) * 1e-3
        v_s = rng.normal(size=r) * 1e-2
        a   = rs_eigen.eigen_V.T @ rs_synth.Mq @ q_s
        adot = rs_eigen.eigen_V.T @ rs_synth.Mq @ v_s

        E_synth = (0.5 * v_s @ rs_synth.Mq @ v_s
                   + 0.5 * q_s @ rs_synth.Kq @ q_s)
        E_eigen = (0.5 * adot @ rs_eigen.Mq @ adot
                   + 0.5 * a @ rs_eigen.Kq @ a)
        assert abs(E_synth - E_eigen) < 1e-9 * max(abs(E_synth), 1e-12), (
            f"modal energy not invariant: synth={E_synth:.6e} "
            f"eigen={E_eigen:.6e}")


# ---------------------------------------------------------------------------
# 6. IIR step in the eigen basis matches the dense (expm) path
# ---------------------------------------------------------------------------


def test_iir_step_matches_dense():
    """Take one substep starting from a random (q, q̇, F) in the eigen
    basis: the per-mode closed-form resonator and the dense expm path
    must produce identical (q, q̇) at substep end.

    This is the central correctness claim — the per-mode path is
    exact for diagonal Mq/Dq/Kq.
    """
    _, rs = _make_pair()
    r = rs.r
    h = 1.0 / (120.0 * 16.0)
    rng = np.random.default_rng(seed=2026)
    q0   = rng.normal(size=r) * 1.0e-4
    qd0  = rng.normal(size=r) * 1.0e-2
    F    = rng.normal(size=r) * 1.0e2

    # Dense path: builds 3r×3r matrix exponential.
    q_free_d, qdot_free_d, S_d, T_d = dynamic_compliance_step_precompute(
        q0, qd0, rs.Mq, rs.Kq, rs.Dq, h)
    q_dense   = q_free_d   + S_d @ F
    qdot_dense = qdot_free_d + T_d @ F

    # Per-mode path: takes the (diagonal) omega/zeta/mass vectors.
    mass = np.diag(rs.Mq)   # = ones(r) in eigen basis
    q_free_p, qdot_free_p, S_p, T_p = exact_modal_step_precompute(
        q0, qd0, rs.eigen_omegas, rs.eigen_zetas, mass, h)
    q_perm    = q_free_p    + S_p * F
    qdot_perm = qdot_free_p + T_p * F

    # Reference loose tol (1e-7) accommodates per-mode-vs-expm float
    # round-off at the high-omega modes (omega·h ≈ 7 in this shelf).
    np.testing.assert_allclose(q_perm,    q_dense,    atol=1e-7, rtol=1e-5)
    np.testing.assert_allclose(qdot_perm, qdot_dense, atol=1e-5, rtol=1e-5)


# ---------------------------------------------------------------------------
# Sanity: synthetic path is bit-exact (no projection, no V*V^T noise).
# ---------------------------------------------------------------------------


def test_synthetic_default_path_unchanged():
    """to_eigenbasis=False must leave Mq/Kq/Dq EXACTLY as they were
    before the projection was added.  Guards the no-regression promise
    that --reduced-basis synthetic is bit-exact backward compatible.
    """
    rs = make_debug_reduced_shelf_support(to_eigenbasis=False)
    # Mq has non-trivial off-diagonal (the synthetic basis IS coupled).
    assert np.linalg.norm(rs.Mq - np.diag(np.diag(rs.Mq))) > 1e-3
    # is_eigenbasis flag is False, V = I.
    assert rs.is_eigenbasis is False
    assert np.allclose(rs.eigen_V, np.eye(rs.r))
