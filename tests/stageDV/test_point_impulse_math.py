"""Analytical unit tests for the energy-prescribed kick math (this follow-up).

These tests verify, on hand-constructed rigid bodies, that:

  Version A (linear-only, k = 1/m):
    speed = sqrt(2 * E_target / m)
    realized ΔKE = ½ m · speed² = E_target  (to 1e-12)

  Version B (full k, true point impulse):
    J = sqrt(2 * E_target / k),  k = 1/m + (r×u)·I_inv·(r×u)
    Apply at contact: v += (J/m)·u,  ω += J · I_inv · (r × u)
    realized ΔKE_linear  = ½ m ‖Δv‖² = ½ J²/m
    realized ΔKE_angular = ½ Δω · I_world · Δω
    realized ΔKE_total   = ½ J² k = E_target  (to 1e-12)

These checks are independent of the modal pipeline — they pin the algebra
itself.
"""
from __future__ import annotations

import numpy as np

from dcr.dcr.distant_velocity import (
    PointImpulseKick,
    impulse_from_energy_point,
    inv_eff_mass_linear,
    inv_eff_mass_point_impulse,
    speed_from_energy_linear,
)
from dcr.rigid.body import RigidBody, compute_box_inertia


_TOL = 1e-12


def _box_body(mass: float = 2.0,
              half_extents: tuple[float, float, float] = (0.1, 0.1, 0.1),
              position: tuple[float, float, float] = (0.0, 0.0, 0.0),
              ) -> RigidBody:
    """Construct a unit-quaternion box at a given world position."""
    hx, hy, hz = half_extents
    return RigidBody(
        mass=mass,
        inertia_body=compute_box_inertia(mass, hx, hy, hz),
        position=np.array(position, dtype=np.float64),
    )


# ----------------------------------------------------------------------
# inv_eff_mass_linear
# ----------------------------------------------------------------------

class TestInvEffMassLinear:
    def test_returns_1_over_m(self) -> None:
        body = _box_body(mass=2.5)
        assert inv_eff_mass_linear(body) == 1.0 / 2.5

    def test_static_returns_zero(self) -> None:
        body = _box_body(mass=2.5)
        body.is_static = True
        assert inv_eff_mass_linear(body) == 0.0


# ----------------------------------------------------------------------
# inv_eff_mass_point_impulse
# ----------------------------------------------------------------------

class TestInvEffMassPointImpulse:
    def test_zero_lever_arm_reduces_to_1_over_m(self) -> None:
        """When r = 0 (kick at COM), the angular term vanishes → k = 1/m."""
        body = _box_body(mass=3.0)
        r = np.zeros(3)
        u = np.array([0.0, 1.0, 0.0])
        k = inv_eff_mass_point_impulse(body, r, u)
        assert abs(k - 1.0 / 3.0) < _TOL

    def test_parallel_lever_arm_reduces_to_1_over_m(self) -> None:
        """When r is parallel to u, r × u = 0 → angular term vanishes."""
        body = _box_body(mass=3.0)
        u = np.array([0.0, 1.0, 0.0])
        r = 0.5 * u  # parallel
        k = inv_eff_mass_point_impulse(body, r, u)
        assert abs(k - 1.0 / 3.0) < _TOL

    def test_perpendicular_lever_arm_adds_angular(self) -> None:
        """When r ⊥ u, k = 1/m + (r·r)·(1/I) for diag identity-axis-aligned I."""
        body = _box_body(mass=2.0, half_extents=(0.5, 0.5, 0.5))
        # Identity orientation → I_world == diag(I_body).
        u = np.array([0.0, 1.0, 0.0])  # along world y
        r = np.array([0.3, 0.0, 0.0])  # along world x
        # r × u = (0.3*1)·z_hat = (0, 0, 0.3)
        # I_world_inv @ (r×u) = (0, 0, 0.3 / I_zz)
        # (r×u) · (I_world_inv (r×u)) = 0.09 / I_zz
        I_zz = body.inertia_body[2]
        expected = 1.0 / 2.0 + 0.09 / I_zz
        k = inv_eff_mass_point_impulse(body, r, u)
        assert abs(k - expected) < _TOL


# ----------------------------------------------------------------------
# Version A: speed_from_energy_linear → realized ΔKE
# ----------------------------------------------------------------------

class TestVersionARealizedDKE:
    def test_realized_dKE_matches_E_target(self) -> None:
        """½ m · speed² = E_target exactly."""
        body = _box_body(mass=2.5)
        for E_target in [0.0, 1e-6, 1.0, 12.345]:
            speed = speed_from_energy_linear(body, E_target)
            dKE_realized = 0.5 * body.mass * speed * speed
            assert abs(dKE_realized - E_target) < _TOL, (
                f"E_target={E_target} → realized {dKE_realized}")

    def test_negative_E_target_clamped_to_zero(self) -> None:
        body = _box_body(mass=2.5)
        assert speed_from_energy_linear(body, -1.0) == 0.0


# ----------------------------------------------------------------------
# Version B: realized ΔKE = E_target (linear + angular)
# ----------------------------------------------------------------------

class TestVersionBRealizedDKE:
    @staticmethod
    def _realized_dKE_point_impulse(
        body: RigidBody, r: np.ndarray, u: np.ndarray, J: float,
    ) -> float:
        """Compute the actual ΔKE produced by the body when we apply the
        point impulse (linear + angular) at lever arm r along u, from
        velocity = 0. Mirrors _apply_point_impulse_dcr_velocities.
        """
        body_c = RigidBody(
            mass=body.mass,
            inertia_body=body.inertia_body.copy(),
            position=body.position.copy(),
            orientation=body.orientation.copy(),
            velocity=body.velocity.copy(),
        )
        ke_before = 0.5 * body_c.mass * float(
            body_c.velocity[:3] @ body_c.velocity[:3])
        ke_before += 0.5 * float(
            body_c.velocity[3:6]
            @ (body_c.inertia_world() @ body_c.velocity[3:6]))
        body_c.velocity[0:3] += (J / body_c.mass) * u
        body_c.velocity[3:6] += J * (
            body_c.inertia_world_inv() @ np.cross(r, u))
        ke_after = 0.5 * body_c.mass * float(
            body_c.velocity[:3] @ body_c.velocity[:3])
        ke_after += 0.5 * float(
            body_c.velocity[3:6]
            @ (body_c.inertia_world() @ body_c.velocity[3:6]))
        return ke_after - ke_before

    def test_realized_dKE_matches_E_target_from_rest(self) -> None:
        """½ J² k = E_target exactly (from a body at rest)."""
        body = _box_body(mass=2.0, half_extents=(0.5, 0.5, 0.5))
        u = np.array([0.0, 1.0, 0.0])
        for r_xy, E_target in [
            (np.array([0.3, 0.0, 0.0]), 1.0),
            (np.array([0.0, 0.0, 0.4]), 5.0),
            (np.array([0.2, 0.1, 0.15]), 0.5),
        ]:
            J = impulse_from_energy_point(body, r_xy, u, E_target)
            dKE_realized = self._realized_dKE_point_impulse(
                body, r_xy, u, J)
            assert abs(dKE_realized - E_target) < _TOL, (
                f"E_target={E_target} r={r_xy} u={u}: realized={dKE_realized}")

    def test_zero_E_target_gives_zero_J(self) -> None:
        body = _box_body(mass=2.0)
        u = np.array([0.0, 1.0, 0.0])
        r = np.array([0.3, 0.0, 0.0])
        assert impulse_from_energy_point(body, r, u, 0.0) == 0.0
        assert impulse_from_energy_point(body, r, u, -1.0) == 0.0

    def test_static_body_returns_zero(self) -> None:
        body = _box_body(mass=2.0)
        body.is_static = True
        u = np.array([0.0, 1.0, 0.0])
        r = np.array([0.3, 0.0, 0.0])
        assert impulse_from_energy_point(body, r, u, 1.0) == 0.0


# ----------------------------------------------------------------------
# PointImpulseKick dataclass round-trip
# ----------------------------------------------------------------------

class TestPointImpulseKick:
    def test_construct_and_read(self) -> None:
        u = np.array([0.0, 1.0, 0.0])
        r = np.array([0.1, 0.2, 0.3])
        kk = PointImpulseKick(body_idx=4, J_mag=1.5, u=u, r=r, theta=0.05)
        assert kk.body_idx == 4
        assert kk.J_mag == 1.5
        assert np.allclose(kk.u, u)
        assert np.allclose(kk.r, r)
        assert kk.theta == 0.05
