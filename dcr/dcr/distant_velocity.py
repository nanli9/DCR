"""Distant-velocity helpers for the energy-prescribed DCR modes.

Two modes are wired to use these helpers (see passive_dcr.py and
dcr_world.py):

  - "energy_prescribed"                 (Version A) — linear COM kick only.
  - "energy_prescribed_point_impulse"   (Version B) — true point impulse
    (linear + angular) along the deformed contact normal.

Both pick the kick magnitude γ from an energy budget so that the realized
ΔKE matches E_target = β·E_available exactly by construction (foundation §16).

# DEVIATION (foundation §15, §16; paper §5.4):
# - The DCR paper (Coevoet et al. 2020, Eq. 12) prescribes Δv = d_max / h,
#   a length/h kinematic recipe. This module replaces that recipe with an
#   energy-budget recipe for the two new modes only. The paper's recipe
#   is preserved unchanged for dcr_velocity_mode="coevoet" /
#   "bounded_coevoet".
# - Version A applies a COM-linear kick only (no angular component), so its
#   energy formula uses only the linear cross-term m·(v·n')·γ. The angular
#   component of a true point impulse is intentionally omitted in Version A;
#   Version B keeps it.

# CORRECTION (2026-05, foundation §16):
# - Previous releases used γ = √(2 E_target / m) (Version A) and
#   J = √(2 E_target / k) (Version B). Both formulas treat the kick as if
#   the body started at rest, dropping the cross-term that appears whenever
#   v·n' ≠ 0 (Version A) or v_c·n' ≠ 0 with v_c = v + ω×r (Version B).
#   The realized ΔKE then over- or under-shoots E_target, and the global
#   passivity cap in dcr_world.py silently corrected the difference.
# - The corrected formulas solve the full quadratic
#       ΔKE(γ) = b·γ + ½·a·γ² = E_target,
#       γ*    = (-b + √(b² + 2·a·E_target)) / a,
#   structurally identical to passive_alpha (foundation §6).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..rigid.body import RigidBody


# Numerical floor for "zero" effective mass / quadratic coefficient.
_EPS_TINY = 1e-18


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
        speed: Scalar speed magnitude γ*_A (foundation §16); non-negative.
            With the cross-term correction this is the positive root of
            the quadratic ΔKE(γ) = m·(v·u)·γ + ½·m·γ² = E_target, not the
            naive √(2 E_target / m).
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
        J_mag: Impulse magnitude (scalar; non-negative). With the cross-term
            correction this is m·γ*_B where γ*_B is the positive root of the
            quadratic ΔKE(γ) = m·(u·v_c)·γ + ½·a·γ² = E_target with
            a = m + m²·(r×u)ᵀ·I_inv·(r×u) (foundation §16).
        u: (3,) unit-vector direction (deformed contact normal n').
        r: (3,) lever arm contact_point - body.position (world frame).
        theta: Tilt angle in radians (diagnostic only).
        n_rest: (3,) un-deformed contact normal (unit vector), or None.
            When set together with `mu`, the world applies a Coulomb
            friction correction at lever arm r after the main kick — see
            `contact_point_friction_correction` and dcr_world's
            `_apply_point_impulse_dcr_velocities`. Populated by the
            coupler when `friction_cone_clip_enabled=True`. Defaults to
            None (correction disabled).
        mu: Coulomb friction coefficient (scalar ≥ 0), or None. Paired
            with `n_rest` to enable the contact-point friction correction.
    """
    body_idx: int
    J_mag: float
    u: NDArray[np.float64]
    r: NDArray[np.float64]
    theta: float = 0.0
    n_rest: NDArray[np.float64] | None = None
    mu: float | None = None


# ----------------------------------------------------------------------
# Inverse effective mass at a point along a direction (paper Eq. 17)
# ----------------------------------------------------------------------

def inv_eff_mass_linear(body: RigidBody) -> float:
    """k = 1/m (no angular term, Version A).

    Matches the COM-linear kick mechanism in `_apply_linear_kick_dcr_velocities`.
    Static bodies and zero-mass bodies return 0.0.

    # DEVIATION: the spec proposed k = 1/m + (r×u)·I_inv·(r×u). This
    # version drops the angular term because the realized kick is linear
    # at the COM; including it would model energy not actually injected.
    """
    if body.is_static or body.mass <= 0.0:
        return 0.0
    return 1.0 / body.mass


def inv_eff_mass_point_impulse(
    body: RigidBody,
    r: NDArray[np.float64],
    u: NDArray[np.float64],
) -> float:
    """k = 1/m + (r×u)·I_world_inv·(r×u) — inverse effective mass at the
    contact point along direction u (Version B; paper Eq. 17 specialized to
    a normal direction).

    Derivation: applying a point impulse J·u at offset r imparts
        Δv_lin = (J/m)·u
        Δω     = J·I_inv·(r × u)
    The velocity change AT THE CONTACT POINT in direction u is
        (Δv_lin + Δω × r) · u
            = J·(1/m + (r × u)·I_inv·(r × u))
            = J·k.
    Starting at rest (v_c = 0), the kinetic energy added would be
        ½ J² (1/m + (r×u)·I_inv·(r×u)) = ½ J² k.
    For v_c ≠ 0 the full energy expression carries a cross-term — see
    `impulse_from_energy_point` for the γ*_B quadratic that handles it
    (foundation §16).

    Static / zero-mass bodies return 0.0.
    """
    if body.is_static or body.mass <= 0.0:
        return 0.0
    rxu = np.cross(r, u)
    I_inv = body.inertia_world_inv()
    return float((1.0 / body.mass) + (rxu @ I_inv @ rxu))


# ----------------------------------------------------------------------
# Energy-prescribed magnitudes — quadratic γ* (foundation §16)
# ----------------------------------------------------------------------

def gamma_from_energy_linear(
    body: RigidBody,
    u: NDArray[np.float64],
    E_target: float,
) -> float:
    """Version A: speed γ*_A such that the realized linear ΔKE equals
    max(E_target, 0) exactly (foundation §16).

    The body receives the kick `v ← v + γ·u` along the deformed contact
    normal u. The realized kinetic-energy change is

        ΔKE(γ) = ½ m ‖v + γu‖² - ½ m ‖v‖²
               = m·(v·u)·γ + ½·m·γ².

    Setting ΔKE(γ) = E_target gives the quadratic

        ½·m·γ² + m·(v·u)·γ - E_target = 0,
        γ*_A = -(v·u) + √((v·u)² + 2·E_target / m)   (the non-negative root).

    This is structurally identical to `passive_alpha` (foundation §6) with
    a = m, b = m·(v·u). The discriminant is always ≥ 0 when E_target ≥ 0
    (since (v·u)² + 2·E_target/m ≥ 0), and γ*_A ≥ 0 because
    √(b² + 2aE) ≥ |b|.

    # CORRECTION (2026-05, foundation §16): previous formula
    # γ = √(2 E_target / m) ignored the cross-term m·(v·u)·γ, causing
    # the realized ΔKE to differ from E_target whenever v·u ≠ 0. The
    # post-hoc cap in dcr_world.py masked this silently.

    Args:
        body: Receiving rigid body; v = body.velocity[0:3] is read.
        u: (3,) deformed contact normal (unit vector).
        E_target: Energy to inject at this body (J). Non-positive ⇒ 0.

    Returns:
        γ*_A: Non-negative scalar speed. 0.0 for static / zero-mass bodies
        and for E_target ≤ 0.
    """
    if body.is_static or body.mass <= 0.0:
        return 0.0
    if E_target <= 0.0:
        return 0.0
    m = float(body.mass)
    v = body.velocity[0:3]
    v_dot_u = float(v @ u)
    # Quadratic: a = m, b = m·(v·u). γ* = (-b + √(b² + 2aE)) / a.
    discr = v_dot_u * v_dot_u + 2.0 * E_target / m
    # discr ≥ 0 for E_target ≥ 0; max() is paranoia against −0.0 from fp.
    gamma_star = -v_dot_u + float(np.sqrt(max(0.0, discr)))
    # γ* is ≥ 0 by construction; clip to guard against fp noise.
    return max(0.0, gamma_star)


def friction_cone_clip(
    J_vec: NDArray[np.float64],
    n_rest: NDArray[np.float64],
    mu: float,
) -> tuple[NDArray[np.float64], float]:
    """Project a post-solver impulse vector onto the Coulomb friction cone
    around the un-deformed contact normal n_rest with coefficient mu.

    The PGS solver closed the friction cone at the end of its iterations
    using `n_rest`. Any impulse added after that lives outside the cone
    and cannot be opposed by additional friction — its tangential part
    leaks directly into the body and shows up as visible sliding (see
    e.g. shelf scene at h=1e-2 with the deformed-normal kick along n').
    This helper performs the friction-aware correction that a one-pass
    "second iteration" of the solver would yield, without actually
    re-running PGS:

        J_n     = J_vec · n_rest                      (additional normal impulse, ±)
        J_t_vec = J_vec - J_n · n_rest                (additional tangential impulse)
        ‖J_t_vec‖ ≤ mu · max(0, J_n)                   (Coulomb cone budget)

    If the tangential magnitude exceeds the cone budget, it is scaled
    down to the budget; the normal component is unchanged. When J_n ≤ 0
    (the kick pulls into / sideways across the surface) the budget is 0
    and the tangential component is fully removed — this matches the
    physics: no additional normal impulse means no additional Coulomb
    friction is available.

    Args:
        J_vec: (3,) post-solver impulse vector (or velocity-change vector
            for the pure-linear Version A path; the algebra is identical).
        n_rest: (3,) un-deformed contact normal (unit vector). This is the
            same normal the solver used to define its friction cone.
        mu: Coulomb friction coefficient. Use min(body_a.friction,
            body_b.friction) to match the solver convention (see
            rigid/solver.py:206-207).

    Returns:
        (J_vec_clipped, s_t):
            J_vec_clipped: (3,) impulse with tangential component reduced
                to the cone budget. Norm is ≤ ‖J_vec‖.
            s_t: scalar ∈ [0, 1] — the factor applied to the original
                tangential component. 1.0 means no clipping fired.

    # DEVIATION (foundation §15): the paper / foundation are silent on
    # what should happen to the tangential component of a post-solver
    # kick. This is a principled fix specific to this follow-up's
    # deformed-normal kick path; it preserves the BJ / patch-fit
    # direction information for the normal-aligned portion of the kick
    # while taming the unphysical tangential leak.
    """
    J_n = float(J_vec @ n_rest)
    J_t_vec = J_vec - J_n * n_rest
    J_t_mag = float(np.linalg.norm(J_t_vec))
    budget = mu * max(0.0, J_n)
    if J_t_mag > budget and J_t_mag > 1e-12:
        s_t = budget / J_t_mag
        return J_n * n_rest + s_t * J_t_vec, s_t
    return J_vec.copy(), 1.0


def contact_point_friction_correction(
    J: float,
    u: NDArray[np.float64],
    r: NDArray[np.float64],
    n_rest: NDArray[np.float64],
    mu: float,
    mass: float,
    I_world_inv: NDArray[np.float64],
) -> tuple[float, NDArray[np.float64]]:
    """Coulomb friction correction at the contact point for a Version-B
    point impulse kick.

    Motivation. A point impulse `J·u` applied at offset `r ≠ 0` produces
    a linear AND angular velocity change:
        Δv_lin = (J/m)·u
        Δω      = J · I_inv · (r × u)
    The contact-point velocity change is
        Δv_c = Δv_lin + Δω × r
    which generally has a tangential component RELATIVE TO n_rest even
    when u is exactly aligned with n_rest — the `Δω × r` term routes
    energy into spin, and the spin shows up as tangential motion at the
    contact patch. The PGS solver's friction cone (closed against
    n_rest) cannot oppose this because the kick is applied post-solver.
    On scenes like the shelf with Version B + BJ deformed normal, this
    is the dominant mechanism of the visible "sliding" of books along
    the slab — NOT the deformed-normal tilt of u itself (which the BJ
    method tends to produce at ≪3° in practice).

    The fix is a closed-form Coulomb friction correction applied AT THE
    CONTACT POINT (lever arm r), AFTER the main kick:

        dvc_n   = Δv_c · n_rest                      (signed scalar)
        dvc_t   = Δv_c − dvc_n · n_rest              (tangential vector)
        budget  = mu · max(0, dvc_n)                 (cone limit)
        if ‖dvc_t‖ > budget:
            excess = ‖dvc_t‖ − budget
            t̂      = dvc_t / ‖dvc_t‖
            k_t    = 1/m + (r × t̂) · I_inv · (r × t̂)   (paper Eq. 17 on t̂)
            J_f    = excess / k_t                     (friction impulse magnitude)
            # Caller applies:
            #   body.v_lin -= (J_f / m) · t̂
            #   body.ω     -= J_f · I_inv · (r × t̂)

    Properties:
        * Energy is dissipated (J_f opposes contact-point tangential
          motion). Passivity bound (foundation §15) stays valid: the
          correction can only reduce post-cap kick energy further.
        * The correction generates a counter-torque automatically because
          it is applied at r, not the COM — books that would have spun
          off get rotational damping for free.
        * Single scalar (`J_f`) per contact; no second PGS pass.
        * When n_rest is parallel to u and r is parallel to u, dvc_t = 0
          and no correction fires — the helper is a no-op for kicks that
          were already clean.

    Args:
        J: Main kick impulse magnitude (m·γ*_B), AFTER any global
            passivity-cap scaling.
        u: (3,) main kick direction (unit vector; the deformed normal).
        r: (3,) lever arm from body COM to contact point.
        n_rest: (3,) un-deformed contact normal (unit vector). Same axis
            the PGS solver closed its friction cone on.
        mu: Coulomb friction coefficient. Use
            min(body_a.friction, body_b.friction) to match
            rigid/solver.py:206-207.
        mass: Body mass (kg).
        I_world_inv: (3,3) world-frame inverse inertia tensor at the
            CURRENT body orientation.

    Returns:
        (J_f, t_hat):
            J_f: corrective friction impulse magnitude (≥ 0). 0.0 means
                the kick was already inside the Coulomb cone — no work.
            t_hat: (3,) unit vector along the tangential velocity that
                the correction opposes. The zero vector when J_f == 0.

    # DEVIATION (foundation §15): the paper / foundation are silent on
    # post-solver friction. This is a closed-form Coulomb correction for
    # this follow-up's Version-B kick path; it replaces the earlier
    # `friction_cone_clip` (which operated on u and ignored the angular
    # contribution to Δv_c) and is what the user-facing
    # `friction_cone_clip_enabled` flag now activates for Version B.
    """
    if mu <= 0.0 or J == 0.0:
        return 0.0, np.zeros(3)
    rxu = np.cross(r, u)
    dv_lin = (J / mass) * u
    dw = J * (I_world_inv @ rxu)
    dv_c = dv_lin + np.cross(dw, r)
    dvc_n = float(dv_c @ n_rest)
    dvc_t_vec = dv_c - dvc_n * n_rest
    dvc_t_mag = float(np.linalg.norm(dvc_t_vec))
    budget = mu * max(0.0, dvc_n)
    if dvc_t_mag <= budget or dvc_t_mag < 1e-12:
        return 0.0, np.zeros(3)
    excess = dvc_t_mag - budget
    t_hat = dvc_t_vec / dvc_t_mag
    rxt = np.cross(r, t_hat)
    k_t = 1.0 / mass + float(rxt @ I_world_inv @ rxt)
    if k_t <= _EPS_TINY:
        return 0.0, np.zeros(3)
    J_f = excess / k_t
    return J_f, t_hat


def impulse_from_energy_point(
    body: RigidBody,
    r: NDArray[np.float64],
    u: NDArray[np.float64],
    E_target: float,
) -> float:
    """Version B: impulse magnitude J = m·γ*_B such that the realized
    linear + angular ΔKE equals max(E_target, 0) exactly (foundation §16).

    Applying J·u at offset r imparts
        Δv = (J/m)·u,    Δω = J·I_inv·(r × u).
    With v_c = v + ω × r the contact-point velocity, the realized
    kinetic-energy change is
        ΔKE(J) = m·(v·Δv) + ω·(I·Δω) + ½ m ‖Δv‖² + ½ Δω·I·Δω
               = J·(u·v_c) + ½·J²·k
    where k = 1/m + (r×u)·I_inv·(r×u) (paper Eq. 17). Substituting
    J = m·γ rewrites this in γ as
        ΔKE(γ) = m·(u·v_c)·γ + ½·a·γ²,
        a       = m + m² · (r×u)ᵀ · I_inv · (r×u) = m² · k,
        b       = m · (u · v_c).

    Setting ΔKE(γ) = E_target gives γ*_B = (-b + √(b² + 2aE)) / a, again
    structurally identical to passive_alpha (foundation §6). We return
    J = m·γ*_B because downstream consumers
    (`_apply_point_impulse_dcr_velocities`, `_bound_point_impulse_*`) work
    in impulse units.

    Edge cases:
        - a > 0 always when body is dynamic (since m > 0 and the quadratic
          form (r×u)ᵀ I_inv (r×u) ≥ 0 because I is SPD).
        - Discriminant ≥ 0 when E_target ≥ 0.
        - Static / zero-mass bodies return 0.0.

    # CORRECTION (2026-05, foundation §16): previous formula
    # J = √(2 E_target / k) ignored the cross-term m·(u·v_c)·γ
    # (i.e. assumed v_c · u = 0). Realized ΔKE drifted from E_target
    # whenever the contact point had non-zero velocity along u.

    Args:
        body: Receiving rigid body; v = body.velocity[0:3] and
            ω = body.velocity[3:6] are read.
        r: (3,) lever arm (contact_point - body.position) in world frame.
        u: (3,) deformed contact normal (unit vector).
        E_target: Energy to inject at this body (J). Non-positive ⇒ 0.

    Returns:
        J: Non-negative impulse magnitude m·γ*_B. 0.0 for static /
        zero-mass bodies and for E_target ≤ 0.
    """
    if body.is_static or body.mass <= 0.0:
        return 0.0
    if E_target <= 0.0:
        return 0.0
    m = float(body.mass)
    rxu = np.cross(r, u)
    I_inv = body.inertia_world_inv()
    # k = 1/m + (r×u)·I_inv·(r×u) (paper Eq. 17, inverse effective mass).
    k = (1.0 / m) + float(rxu @ I_inv @ rxu)
    if k <= _EPS_TINY:
        return 0.0
    # a = m² · k; b = m · (u · v_c) with v_c = v + ω × r.
    v = body.velocity[0:3]
    omega = body.velocity[3:6]
    v_c = v + np.cross(omega, r)
    a = (m * m) * k
    b = m * float(u @ v_c)
    discr = b * b + 2.0 * a * E_target
    gamma_star = (-b + float(np.sqrt(max(0.0, discr)))) / a
    gamma_star = max(0.0, gamma_star)
    return m * gamma_star
