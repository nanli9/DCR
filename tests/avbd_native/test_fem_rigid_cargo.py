"""Stage 3 (foundation) — fem_rigid cube body model.

Validates the FFR rigid+modal cube builder ported to the AVBD-Native branch
(`dcr/avbd/cargo/fem_rigid.py`): the FEM elastic eigenmodes, the mass-normalized
modal block, the corner modal Jacobians, and the co-rotated contact Jacobian
`∂x/∂a = R·Φ_c` (the per-cube analogue of the support's U_y) against a finite
difference. These are the per-cube quantities the GPU dynamic-constraint
coupling consumes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dcr.avbd.cargo.fem_rigid import (
    build_fem_rigid_cube, quat_to_matrix, rotvec_to_quat, quat_mul,
    quat_normalize,
)


def _cube(k=6):
    return build_fem_rigid_cube(size=0.1, nx=3, n_elastic=k, drop_y=0.2)


def test_modal_extraction():
    """k elastic modes, strictly positive ω² (rigid modes skipped), and the
    elastic block is mass-normalized (ΦᵀMΦ = I is built into the eigensolve)."""
    k = 6
    b = _cube(k)
    assert b.k == k
    assert b.omega2.shape == (k,)
    # Elastic modes only: every kept ω² is well above the 6 (≈0) rigid modes.
    assert np.all(b.omega2 > 1.0), b.omega2
    assert np.all(np.isfinite(b.omega2))
    # Modal mass is the identity (mass-normalized modes ⇒ M_q = I).
    M = b.mass_tan(b.rest_state())
    np.testing.assert_allclose(M[6:, 6:], np.eye(k), atol=1e-12)
    # Rigid inertia is finite + symmetric + PD.
    assert np.allclose(b.inertia0, b.inertia0.T)
    assert np.min(np.linalg.eigvalsh(b.inertia0)) > 0.0


def test_corner_modal_shapes():
    """8 cube corners, each with a (3,k) modal block (the corner's flex basis)."""
    b = _cube(6)
    assert b.n_corners() == 8
    assert b.corner_body.shape == (8, 3)
    assert b.corner_modal.shape == (8, 3, b.k)
    # Corners are near the (±half)³ box corners (COM-relative).
    half = b.half_extent
    assert np.allclose(np.abs(b.corner_body), half, atol=0.2 * half)


def test_corotated_contact_jacobian_matches_fd():
    """∂x_corner/∂[δp, δθ_world, δa] from point_jac_tan matches a central finite
    difference at a non-identity orientation + nonzero modal amplitude. This is
    the co-rotated R·Φ_c modal contact Jacobian the coupling relies on."""
    b = _cube(6)
    rng = np.random.default_rng(1)
    z = b.rest_state()
    # rotate + flex so R ≠ I and a ≠ 0 (exercise all three Jacobian blocks).
    z[3:7] = quat_normalize(quat_mul(rotvec_to_quat(
        np.array([0.3, -0.4, 0.2])), z[3:7]))
    z[7:] = rng.standard_normal(b.k) * 1e-3
    pid = 5

    J = b.point_jac_tan(z, pid)
    eps = 1e-7
    Jfd = np.zeros((3, b.tdim))
    for j in range(b.tdim):
        d = np.zeros(b.tdim); d[j] = eps
        xp = b.point_world(b.retract(z, d), pid)
        xm = b.point_world(b.retract(z, -d), pid)
        Jfd[:, j] = (xp - xm) / (2 * eps)
    np.testing.assert_allclose(J, Jfd, atol=1e-6, rtol=1e-5)

    # The modal columns are exactly R·Φ_c (the co-rotated mode shape at corner).
    R = quat_to_matrix(z[3:7])
    np.testing.assert_allclose(J[:, 6:], R @ b.corner_modal[pid], atol=1e-12)


def test_free_modal_step_is_dissipative():
    """A free (no-contact) backward-Euler step of the cube's tangent block damps
    the modal energy — the same passivity the support enjoys, per cube."""
    b = _cube(6)
    h = (1.0 / 120.0) / 4.0
    z = b.rest_state()
    rng = np.random.default_rng(2)
    v = np.zeros(b.tdim)
    v[6:] = rng.standard_normal(b.k) * 1e-2   # plucked modal velocity

    def modal_E(z, v):
        return (0.5 * float(v[6:] @ v[6:])               # ½ ȧᵀ I ȧ
                + 0.5 * float(z[7:] @ (b.omega2 * z[7:])))  # ½ aᵀ Ω² a

    # one free tangent backward-Euler step on the modal sub-block (M=I, K=Ω², D).
    E0 = modal_E(z, v)
    a, adot = z[7:].copy(), v[6:].copy()
    Om2, D = b.omega2, np.diag(b.D_modal)
    Eprev = E0
    for _ in range(300):
        a_hat = a + h * adot
        H = (1.0 / h**2) * np.eye(b.k) + np.diag(D) / h + np.diag(Om2)
        rhs = (1.0 / h**2) * a_hat + (D / h) * a
        a_new = np.linalg.solve(H, rhs)
        adot = (a_new - a) / h
        a = a_new
        E = 0.5 * float(adot @ adot) + 0.5 * float(a @ (Om2 * a))
        assert E <= Eprev + 1e-15
        Eprev = E
    assert Eprev < 0.5 * E0
