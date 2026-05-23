"""Distant-velocity helpers for the energy-prescribed DCR modes.

Two modes are wired to use these helpers (see passive_dcr.py and
dcr_world.py):

  - "energy_prescribed"                 (Version A) — linear COM kick only.
  - "energy_prescribed_point_impulse"   (Version B) — true point impulse
    (linear + angular) along the deformed contact normal.

Both pick the kick magnitude from an energy budget so that the realized
ΔKE matches E_target = β·E_available by construction.

# DEVIATION (foundation §15, paper §5.4):
# - The DCR paper (Coevoet et al. 2020, Eq. 12) prescribes Δv = d_max / h,
#   a length/h kinematic recipe. This module replaces that recipe with an
#   energy-budget recipe for the two new modes only. The paper's recipe
#   is preserved unchanged for dcr_velocity_mode="coevoet" /
#   "bounded_coevoet".
# - Version A uses k = 1/m. We drop the angular term from the spec's
#   k = 1/m + (r×u)·I_inv·(r×u) formula because the existing kick
#   application path (_apply_dcr_velocities) updates only
#   body.velocity[:3] — adding the angular term would correspond to
#   energy that is NOT actually injected. Version B uses the full k AND
#   applies the angular component, restoring physical consistency.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..rigid.body import RigidBody


# ----------------------------------------------------------------------
# LinearKick — return type for Version A (linear COM kick at deformed normal)
# ----------------------------------------------------------------------

@dataclass
class LinearKick:
    """One Version-A linear COM kick along the deformed contact normal n'.

    Applied to body p by `_apply_linear_kick_dcr_velocities` (dcr_world.py):

        body.velocity[0:3] += scale * speed * u

    where scale ∈ [0, 1] is the passivity-cap factor from
    `_bound_linear_kick_dcr_velocities`.

    Attributes:
        body_idx: Index of the body receiving the kick.
        speed: Scalar speed magnitude `√(2 · E_target / m)`; non-negative.
        u: (3,) unit-vector direction (deformed contact normal n').
        theta: Tilt angle vs the un-deformed normal (diagnostic only).
    """
    body_idx: int
    speed: float
    u: NDArray[np.float64]
    theta: float = 0.0


# ----------------------------------------------------------------------
# PointImpulseKick — return type for Version B
# ----------------------------------------------------------------------

@dataclass
class PointImpulseKick:
    """One distant-body kick as a point impulse at a contact point.

    Applied to body p with lever arm r = contact_point - body.position by
    `_apply_point_impulse_dcr_velocities` (dcr_world.py):

        body.velocity[0:3] += scale * (J_mag / m_p) * u
        body.velocity[3:6] += scale * J_mag * I_world_inv_p @ cross(r, u)

    where scale ∈ [0, 1] is the passivity-cap factor from
    `_bound_point_impulse_dcr_velocities`.

    Attributes:
        body_idx: Index of the body receiving the kick.
        J_mag: Impulse magnitude (scalar; non-negative).
        u: (3,) unit-vector direction (deformed contact normal n').
        r: (3,) lever arm contact_point - body.position (world frame).
        theta: Tilt angle in radians (diagnostic only).
    """
    body_idx: int
    J_mag: float
    u: NDArray[np.float64]
    r: NDArray[np.float64]
    theta: float = 0.0


# ----------------------------------------------------------------------
# Inverse effective mass at a point along a direction
# ----------------------------------------------------------------------

def inv_eff_mass_linear(body: RigidBody) -> float:
    """k = 1/m (no angular term, Version A).

    Matches the COM-linear kick mechanism in `_apply_dcr_velocities`.
    Static bodies and zero-mass bodies return 0.0.

    # DEVIATION: the spec proposed k = 1/m + (r×u)·I_inv·(r×u). This
    # version drops the angular term because the realized kick is linear
    # at the COM; including it would cause ΔKE_realized > E_target.
    """
    if body.is_static or body.mass <= 0.0:
        return 0.0
    return 1.0 / body.mass


def inv_eff_mass_point_impulse(
    body: RigidBody,
    r: NDArray[np.float64],
    u: NDArray[np.float64],
) -> float:
    """k = 1/m + (r×u)·I_world_inv·(r×u) — point-impulse inverse mass (Version B).

    Derivation: applying a point impulse J·u at offset r imparts
        Δv_lin = (J/m)·u
        Δω     = J·I_inv·(r × u)
    The velocity change AT THE CONTACT POINT in direction u is
        (Δv_lin + Δω × r) · u
            = J·(1/m + (r × u)·I_inv·(r × u))
            = J·k
    and the kinetic energy added is
        ΔKE = ½ m‖Δv_lin‖² + ½ Δω·I·Δω
            = ½ J² (1/m + (r×u)·I_inv·(r×u))
            = ½ J² k
    so for ΔKE = E_target we get J = √(2 E_target / k).

    Static / zero-mass bodies return 0.0.
    """
    if body.is_static or body.mass <= 0.0:
        return 0.0
    rxu = np.cross(r, u)
    I_inv = body.inertia_world_inv()
    return float((1.0 / body.mass) + (rxu @ I_inv @ rxu))


# ----------------------------------------------------------------------
# Energy-prescribed magnitudes
# ----------------------------------------------------------------------

def speed_from_energy_linear(body: RigidBody, E_target: float) -> float:
    """Version A: scalar speed s such that ½ m s² = max(E_target, 0).

    s = √(2 · (1/m) · max(E_target, 0)) for dynamic bodies; 0 otherwise.
    """
    k = inv_eff_mass_linear(body)
    if k <= 0.0:
        return 0.0
    return float(np.sqrt(2.0 * k * max(0.0, E_target)))


def impulse_from_energy_point(
    body: RigidBody,
    r: NDArray[np.float64],
    u: NDArray[np.float64],
    E_target: float,
) -> float:
    """Version B: impulse magnitude J such that ½ J² k = max(E_target, 0).

    J = √(2 · max(E_target, 0) / k) for dynamic bodies; 0 otherwise.
    """
    k = inv_eff_mass_point_impulse(body, r, u)
    if k <= 1e-18:
        return 0.0
    return float(np.sqrt(2.0 * max(0.0, E_target) / k))
