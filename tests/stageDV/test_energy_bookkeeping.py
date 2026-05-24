"""Energy-bookkeeping tests for the corrected γ*_A / γ*_B formulas.

Regression suite for the 2026-05 bugfix in `dcr/dcr/distant_velocity.py`
(see prompts/fix_distant_velocity_energy_bug.md, foundation §16).

The previous Version-A formula γ = √(2 E_target / m) and the previous
Version-B formula J = √(2 E_target / k) both dropped the linear
cross-term that appears whenever the receiving body has non-zero velocity
along the deformed contact normal. The corrected formulas solve

    ΔKE(γ) = b·γ + ½·a·γ² = E_target,
    γ*     = (-b + √(b² + 2·a·E_target)) / a,

where (a, b) match (m, m·(v·u))   for Version A,
and   (m²·k, m·(u·v_c))           for Version B,  v_c = v + ω × r.

These tests assert that the **realized** kinetic-energy change after
applying the kick equals E_target exactly (to float tolerance) across:
  • v·u > 0, v·u = 0, v·u < 0  (Version A and B)
  • non-zero ω, non-diagonal world inertia (Version B)
  • multiple lever arms r (Version B)

And include an explicit numerical regression check that γ*_A differs
from the old √(2 E_target / m) whenever v·u ≠ 0.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dcr.dcr.distant_velocity import (
    gamma_from_energy_linear,
    impulse_from_energy_point,
)
from dcr.rigid.body import (
    RigidBody,
    compute_box_inertia,
    quat_identity,
)


_TOL = 1e-10


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _box_body(
    mass: float = 2.0,
    half_extents: tuple[float, float, float] = (0.4, 0.3, 0.5),
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    velocity: np.ndarray | None = None,
    orientation: np.ndarray | None = None,
) -> RigidBody:
    """Construct a box RigidBody with optional initial v/ω and orientation."""
    hx, hy, hz = half_extents
    vel = np.zeros(6) if velocity is None else np.asarray(velocity, dtype=np.float64)
    ori = quat_identity() if orientation is None else np.asarray(orientation, dtype=np.float64)
    return RigidBody(
        mass=mass,
        inertia_body=compute_box_inertia(mass, hx, hy, hz),
        position=np.array(position, dtype=np.float64),
        orientation=ori,
        velocity=vel.copy(),
    )


def _quat_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    """Build a unit quaternion (w, x, y, z) from axis-angle."""
    axis = np.asarray(axis, dtype=np.float64)
    axis = axis / np.linalg.norm(axis)
    h = 0.5 * angle
    return np.array([math.cos(h), *(axis * math.sin(h))], dtype=np.float64)


def _ke_linear(body: RigidBody) -> float:
    v = body.velocity[0:3]
    return 0.5 * body.mass * float(v @ v)


def _ke_angular(body: RigidBody) -> float:
    omega = body.velocity[3:6]
    return 0.5 * float(omega @ (body.inertia_world() @ omega))


def _ke_total(body: RigidBody) -> float:
    return _ke_linear(body) + _ke_angular(body)


def _apply_linear_kick(body: RigidBody, u: np.ndarray, gamma: float) -> None:
    """Apply v ← v + γ·u (mirrors _apply_linear_kick_dcr_velocities)."""
    body.velocity[0:3] = body.velocity[0:3] + gamma * u


def _apply_point_impulse(
    body: RigidBody, r: np.ndarray, u: np.ndarray, J: float,
) -> None:
    """Apply linear + angular point-impulse update (mirrors
    _apply_point_impulse_dcr_velocities)."""
    body.velocity[0:3] = body.velocity[0:3] + (J / body.mass) * u
    body.velocity[3:6] = (
        body.velocity[3:6] + J * (body.inertia_world_inv() @ np.cross(r, u))
    )


# ----------------------------------------------------------------------
# Version A: linear COM kick with cross-term
# ----------------------------------------------------------------------

class TestVersionAEnergyExact:
    """For every (v·u, E_target), realized ΔKE matches E_target."""

    @pytest.mark.parametrize("v_dot_u", [-2.0, -0.5, 0.0, 0.5, 1.5])
    @pytest.mark.parametrize("E_target", [1e-6, 0.1, 1.0, 12.345])
    @pytest.mark.parametrize("mass", [0.5, 2.0, 9.7])
    def test_realized_dKE_matches_E_target(
        self, v_dot_u: float, E_target: float, mass: float,
    ) -> None:
        # Pick an arbitrary unit normal u and align v along u with the
        # requested projection (plus a tangential component that doesn't
        # affect the linear cross-term).
        u = np.array([1.0, 2.0, -0.5])
        u = u / np.linalg.norm(u)
        # Tangential vector (perpendicular to u).
        t = np.array([0.0, 1.0, 4.0])
        t = t - (t @ u) * u
        t = t / max(np.linalg.norm(t), 1e-12)
        v_lin = v_dot_u * u + 0.3 * t  # tangential 0.3 magnitude
        body = _box_body(mass=mass, velocity=np.concatenate([v_lin, np.zeros(3)]))

        ke_before = _ke_linear(body)
        gamma = gamma_from_energy_linear(body, u, E_target)
        _apply_linear_kick(body, u, gamma)
        ke_after = _ke_linear(body)

        dKE = ke_after - ke_before
        assert abs(dKE - E_target) < _TOL, (
            f"v·u={v_dot_u} m={mass} E={E_target} → realized {dKE}, "
            f"expected {E_target}, γ={gamma}")

    def test_gamma_non_negative_when_v_dot_u_negative(self) -> None:
        """γ*_A must be ≥ 0 even when v·u < 0 (kick must add energy, not flip)."""
        u = np.array([0.0, 1.0, 0.0])
        body = _box_body(mass=1.0, velocity=np.array([0, -3.0, 0, 0, 0, 0]))
        gamma = gamma_from_energy_linear(body, u, 1.0)
        assert gamma >= 0.0

    def test_zero_E_target_gives_zero_gamma(self) -> None:
        u = np.array([0.0, 1.0, 0.0])
        body = _box_body(velocity=np.array([1.0, 2.0, 3.0, 0, 0, 0]))
        assert gamma_from_energy_linear(body, u, 0.0) == 0.0
        assert gamma_from_energy_linear(body, u, -1.0) == 0.0

    def test_static_body_returns_zero(self) -> None:
        u = np.array([0.0, 1.0, 0.0])
        body = _box_body(velocity=np.array([0, 1.0, 0, 0, 0, 0]))
        body.is_static = True
        assert gamma_from_energy_linear(body, u, 1.0) == 0.0


class TestVersionARegression:
    """Pin the explicit numerical value of γ*_A for a known case, and
    confirm it differs from the old buggy formula."""

    def test_gamma_differs_from_old_formula_when_v_dot_u_nonzero(self) -> None:
        # m = 1, v·u = 2, E_target = 1
        #   new γ*_A = -2 + √(4 + 2) = -2 + √6 ≈ 0.449
        #   old γ    = √(2·1/1)      = √2     ≈ 1.414
        m, v_dot_u, E = 1.0, 2.0, 1.0
        u = np.array([1.0, 0.0, 0.0])
        body = _box_body(
            mass=m,
            velocity=np.array([v_dot_u, 0, 0, 0, 0, 0]),
        )
        gamma_new = gamma_from_energy_linear(body, u, E)
        gamma_old_buggy = math.sqrt(2.0 * E / m)

        assert abs(gamma_new - (-2.0 + math.sqrt(6.0))) < 1e-12
        assert abs(gamma_old_buggy - math.sqrt(2.0)) < 1e-12
        assert abs(gamma_new - gamma_old_buggy) > 0.5  # large, unambiguous gap

    def test_v_dot_u_zero_reduces_to_old_formula(self) -> None:
        """When v·u = 0, γ*_A degenerates to √(2·E_target/m). This is the
        only regime where the old formula was correct."""
        u = np.array([0.0, 1.0, 0.0])
        # v perpendicular to u
        body = _box_body(mass=3.0, velocity=np.array([1.0, 0.0, 4.0, 0, 0, 0]))
        gamma_new = gamma_from_energy_linear(body, u, 5.0)
        gamma_old = math.sqrt(2.0 * 5.0 / 3.0)
        assert abs(gamma_new - gamma_old) < 1e-12


# ----------------------------------------------------------------------
# Version B: point impulse (linear + angular) with full cross-term
# ----------------------------------------------------------------------

class TestVersionBEnergyExact:
    """For every (v_c·u, E_target, r, inertia), realized ΔKE matches E_target."""

    @pytest.mark.parametrize("E_target", [1e-6, 0.1, 1.0, 7.5])
    @pytest.mark.parametrize(
        "v_lin, omega, r",
        [
            # (v, ω, r) — body at rest; cross-term vanishes (sanity).
            (np.zeros(3), np.zeros(3), np.array([0.3, 0.0, 0.0])),
            # Linear-only motion toward elastic.
            (np.array([0.0, 1.5, 0.0]), np.zeros(3), np.array([0.3, 0.0, 0.0])),
            # Linear-only motion away.
            (np.array([0.0, -2.2, 0.0]), np.zeros(3), np.array([0.2, 0.1, 0.0])),
            # Angular-only — v_c at contact arises from ω × r.
            (np.zeros(3), np.array([0.0, 0.0, 4.0]), np.array([0.3, 0.0, 0.0])),
            # Mixed v + ω, r off-axis.
            (
                np.array([0.5, -0.7, 1.1]),
                np.array([0.4, -0.6, 2.0]),
                np.array([0.2, 0.15, -0.05]),
            ),
        ],
    )
    def test_realized_dKE_matches_E_target_diag_inertia(
        self, E_target: float, v_lin: np.ndarray,
        omega: np.ndarray, r: np.ndarray,
    ) -> None:
        u = np.array([0.0, 1.0, 0.0])
        body = _box_body(
            mass=2.0,
            half_extents=(0.4, 0.3, 0.5),
            velocity=np.concatenate([v_lin, omega]),
        )
        ke_before = _ke_total(body)
        J = impulse_from_energy_point(body, r, u, E_target)
        _apply_point_impulse(body, r, u, J)
        ke_after = _ke_total(body)
        dKE = ke_after - ke_before
        assert abs(dKE - E_target) < _TOL, (
            f"v={v_lin} ω={omega} r={r} E={E_target}: realized {dKE} J={J}")

    @pytest.mark.parametrize("E_target", [0.5, 2.0])
    def test_realized_dKE_matches_E_target_non_diagonal_inertia(
        self, E_target: float,
    ) -> None:
        """Non-diagonal world inertia (via rotated orientation).
        Use an anisotropic box so I_world is genuinely non-diagonal."""
        ori = _quat_axis_angle(np.array([1.0, 1.0, 0.3]), 0.6)
        body = _box_body(
            mass=2.5,
            half_extents=(0.6, 0.2, 0.4),  # anisotropic
            velocity=np.array([0.3, -0.4, 0.5, 0.8, -0.2, 1.1]),
            orientation=ori,
        )
        # Confirm world inertia is non-diagonal — guards against silent
        # rotation cancellation.
        I_world = body.inertia_world()
        off_diag_max = max(
            abs(I_world[0, 1]), abs(I_world[0, 2]), abs(I_world[1, 2]),
        )
        assert off_diag_max > 1e-3, (
            f"I_world is effectively diagonal: max off-diag = {off_diag_max}")

        u = np.array([0.3, 0.9, -0.1])
        u = u / np.linalg.norm(u)
        r = np.array([0.25, -0.1, 0.18])

        ke_before = _ke_total(body)
        J = impulse_from_energy_point(body, r, u, E_target)
        _apply_point_impulse(body, r, u, J)
        ke_after = _ke_total(body)
        dKE = ke_after - ke_before
        assert abs(dKE - E_target) < _TOL, (
            f"non-diag I; E={E_target}: realized {dKE}, J={J}")

    def test_zero_E_target_gives_zero_J(self) -> None:
        u = np.array([0.0, 1.0, 0.0])
        r = np.array([0.3, 0.0, 0.0])
        body = _box_body(velocity=np.array([1.0, 2.0, 3.0, 0.5, -0.5, 0.1]))
        assert impulse_from_energy_point(body, r, u, 0.0) == 0.0
        assert impulse_from_energy_point(body, r, u, -1.0) == 0.0

    def test_static_body_returns_zero(self) -> None:
        u = np.array([0.0, 1.0, 0.0])
        r = np.array([0.3, 0.0, 0.0])
        body = _box_body(velocity=np.array([1.0, 2.0, 3.0, 0.5, -0.5, 0.1]))
        body.is_static = True
        assert impulse_from_energy_point(body, r, u, 1.0) == 0.0


class TestVersionBRegression:
    """Pin a known numerical case showing the new formula differs from the
    old J = √(2 E / k) whenever v_c · u ≠ 0."""

    def test_J_differs_from_old_formula_when_v_c_dot_u_nonzero(self) -> None:
        # Construct a deterministic case at the COM (r = 0 ⇒ k = 1/m, no angular).
        # m = 1, v·u = 2, E = 1, u along y.
        #   old J = √(2·E/k) = √(2·1·1) = √2
        #   new γ*_B with a = m²·k = 1, b = m·(v_c·u) = 2:
        #            γ = -2 + √(4 + 2) = -2 + √6
        #   new J = m·γ = -2 + √6 ≈ 0.449
        u = np.array([0.0, 1.0, 0.0])
        r = np.zeros(3)
        body = _box_body(
            mass=1.0,
            velocity=np.array([0.0, 2.0, 0.0, 0.0, 0.0, 0.0]),
        )
        J_new = impulse_from_energy_point(body, r, u, 1.0)
        J_old_buggy = math.sqrt(2.0 * 1.0 / (1.0 / 1.0))  # √2

        assert abs(J_new - (-2.0 + math.sqrt(6.0))) < 1e-12
        assert abs(J_old_buggy - math.sqrt(2.0)) < 1e-12
        assert abs(J_new - J_old_buggy) > 0.5

    def test_v_c_dot_u_zero_reduces_to_old_formula(self) -> None:
        """When v_c · u = 0, γ*_B reduces to √(2·E_target/(m²·k))
        ⇒ J = √(2·E_target/k). Only regime where old formula was correct."""
        u = np.array([0.0, 1.0, 0.0])
        # v ⊥ u, ω = 0, r along u (so ω × r = 0 anyway). v_c · u = 0.
        r = 0.4 * u
        body = _box_body(
            mass=2.0,
            velocity=np.array([1.0, 0.0, 3.0, 0.0, 0.0, 0.0]),
        )
        J_new = impulse_from_energy_point(body, r, u, 5.0)
        # k = 1/m here (r×u = 0).
        k = 1.0 / body.mass
        J_old = math.sqrt(2.0 * 5.0 / k)
        assert abs(J_new - J_old) < 1e-12
