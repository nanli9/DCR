"""Stage X1 — parity of the VECTORIZED rigid-energy accounting (foundation §15).

`rigid_mechanical_energy` was vectorized over bodies (batched Rᵀω + quadratic
forms) and given an optional precomputed `Il` (body-local inertia) so the §15
clamp no longer re-inverts the constant 3×3 inertia every substep. This asserts
the vectorized path is numerically identical to the retained scalar reference
`_rigid_mechanical_energy_loop`, on the exact code paths the two solvers exercise:

  * random dynamic bodies (KE only, and KE + gravitational PE),
  * the precomputed-Il fast path == the invert-internally reference path,
  * static bodies (m ≤ 0) skipped,
  * a dynamic body with a SINGULAR inertia drops its angular term (not the whole
    body) — the try/except-skip semantics of the loop, preserved by the
    zero-row convention in `local_inertia_from_invIl`,
  * degenerate (near-zero-norm) quaternion → identity, matching the scalar guard.

No warp / scene dependency: this is a pure-numpy unit of the accounting kernel.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.passivity import (
    rigid_mechanical_energy,
    _rigid_mechanical_energy_loop,
    local_inertia_from_invIl,
    _quat_to_R,
    _quat_to_R_batch,
)

_RTOL = 1e-9
_ATOL = 1e-12


def _rand_quats(rng, n):
    q = rng.standard_normal((n, 4))
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def _rand_spd_invIl(rng, n):
    """n random SPD body-local inverse-inertia 3×3 (a real inertia's inverse)."""
    out = np.empty((n, 3, 3))
    for i in range(n):
        A = rng.standard_normal((3, 3))
        out[i] = A @ A.T + 3.0 * np.eye(3)   # SPD, well-conditioned
    return out


def _scene(rng, n, static_idx=(), singular_idx=()):
    V = rng.standard_normal((n, 3))
    W = rng.standard_normal((n, 3))
    Q = _rand_quats(rng, n)
    mass = rng.uniform(0.5, 4.0, size=n)
    invIl = _rand_spd_invIl(rng, n)
    for i in static_idx:
        mass[i] = 0.0
        invIl[i] = 0.0                       # static: zero inverse inertia
    for i in singular_idx:
        invIl[i] = 0.0                       # dynamic body, exactly-singular inertia
    X = rng.standard_normal((n, 3))
    return V, W, Q, mass, invIl, X


@pytest.mark.parametrize("seed", range(6))
def test_ke_only_matches_scalar_reference(seed):
    rng = np.random.default_rng(seed)
    V, W, Q, mass, invIl, _ = _scene(rng, n=7)
    ref = _rigid_mechanical_energy_loop(V, W, Q, mass, invIl)
    got = rigid_mechanical_energy(V, W, Q, mass, invIl)
    assert got == pytest.approx(ref, rel=_RTOL, abs=_ATOL)


@pytest.mark.parametrize("seed", range(6))
def test_ke_plus_gravity_pe_matches_reference(seed):
    rng = np.random.default_rng(seed)
    V, W, Q, mass, invIl, X = _scene(rng, n=7)
    g = np.array([0.0, -9.81, 0.0])
    ref = _rigid_mechanical_energy_loop(V, W, Q, mass, invIl, X=X, gravity=g)
    got = rigid_mechanical_energy(V, W, Q, mass, invIl, X=X, gravity=g)
    assert got == pytest.approx(ref, rel=_RTOL, abs=_ATOL)


@pytest.mark.parametrize("seed", range(4))
def test_precomputed_Il_equals_internal_inversion(seed):
    """The hot path (solver passes cached Il) must equal the Il=None reference
    path bit-for-bit — the cache only hoists the constant inversion out."""
    rng = np.random.default_rng(seed)
    V, W, Q, mass, invIl, X = _scene(rng, n=5)
    g = np.array([0.0, -9.81, 0.0])
    Il = local_inertia_from_invIl(invIl)
    a = rigid_mechanical_energy(V, W, Q, mass, invIl, X=X, gravity=g)
    b = rigid_mechanical_energy(V, W, Q, mass, invIl, X=X, gravity=g, Il=Il)
    assert a == b            # identical Il, identical arithmetic order → exact


def test_static_bodies_skipped():
    rng = np.random.default_rng(11)
    V, W, Q, mass, invIl, X = _scene(rng, n=6, static_idx=(1, 4))
    g = np.array([0.0, -9.81, 0.0])
    ref = _rigid_mechanical_energy_loop(V, W, Q, mass, invIl, X=X, gravity=g)
    got = rigid_mechanical_energy(V, W, Q, mass, invIl, X=X, gravity=g)
    assert got == pytest.approx(ref, rel=_RTOL, abs=_ATOL)


def test_singular_inertia_drops_only_angular_term():
    """A DYNAMIC body (m > 0) with an exactly-singular inertia keeps its linear KE
    but drops the angular term (the loop's try/except-skip on np.linalg.inv), and
    the vectorized path agrees via the zero-row convention."""
    rng = np.random.default_rng(23)
    V, W, Q, mass, invIl, X = _scene(rng, n=5, singular_idx=(2,))
    assert mass[2] > 0.0                     # still a dynamic body
    ref = _rigid_mechanical_energy_loop(V, W, Q, mass, invIl)
    got = rigid_mechanical_energy(V, W, Q, mass, invIl)
    assert got == pytest.approx(ref, rel=_RTOL, abs=_ATOL)
    # the zero-row convention is what makes them agree: body 2 contributes 0 angular
    Il = local_inertia_from_invIl(invIl)
    assert np.allclose(Il[2], 0.0)
    # sanity: dropping only the angular term ⇒ result still includes its linear KE
    assert got > 0.0


def test_empty_and_all_static_return_zero():
    empty = np.zeros((0, 3, 3))
    assert rigid_mechanical_energy(np.zeros((0, 3)), np.zeros((0, 3)),
                                   np.zeros((0, 4)), np.zeros(0), empty) == 0.0
    rng = np.random.default_rng(3)
    V, W, Q, mass, invIl, _ = _scene(rng, n=3, static_idx=(0, 1, 2))
    assert rigid_mechanical_energy(V, W, Q, mass, invIl) == 0.0


@pytest.mark.parametrize("seed", range(4))
def test_quat_batch_matches_scalar(seed):
    rng = np.random.default_rng(100 + seed)
    Q = _rand_quats(rng, 8)
    Rb = _quat_to_R_batch(Q)
    for i in range(Q.shape[0]):
        assert np.allclose(Rb[i], _quat_to_R(Q[i]), rtol=0, atol=1e-14)


def test_degenerate_quat_is_identity_both_paths():
    q0 = np.zeros((1, 4))                     # ‖q‖² = 0 < 1e-30 → identity
    assert np.allclose(_quat_to_R_batch(q0)[0], np.eye(3))
    assert np.allclose(_quat_to_R(q0[0]), np.eye(3))
