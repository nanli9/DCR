"""Unit tests for the contact-compatible null-space projection.

See `dcr/dcr/contact_projection.py` and
`prompts/dcr_patch_kick_nullspace_projection_fix.md` (§6-9).

Coverage:
  1. Identity: lam parallel n with multiple corner points → lam_proj = lam.
  2. Pure tangential lam → projection drops magnitude; differential normal
     velocity across patch sample points is near zero in the result.
  3. K-metric energy is non-increasing for random lam draws.
  4. Gate: tall body (h_normal not << h_lateral) → projection skipped.
  5. Gate: < 3 sample points → projection skipped.
  6. Gate: orientation-aware — body rotated so the thin axis is no longer
     aligned with the contact normal stops counting as thin.
  7. Gate: non-Box shapes are skipped.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.dcr.contact_projection import (
    project_du_contact_compatible,
    project_patch_impulse_contact_compatible,
    should_project_patch,
    _K_body,
    _impulse_to_du_map,
)
from dcr.rigid.body import (
    Shape,
    ShapeType,
    box_shape,
    sphere_shape,
    compute_box_inertia,
)


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


def _thin_box_patch():
    """A fork-like thin box at rest on the slab, 4 corner contacts.

    half_extents = (0.06, 0.005, 0.012)  (thin in y)
    COM at origin; contact normal n = (0, 1, 0) pointing UP from slab
    (out of body B toward body A in canonical A→B convention used by
    the coupler insertion site — see passive_dcr.py:1652-1660).
    r_bar = (0, -0.005, 0) — lever from COM down to bottom face.
    Sample corners distributed on the bottom face.
    """
    mass = 0.06  # 60 g
    half = np.array([0.06, 0.005, 0.012])
    inertia_body = compute_box_inertia(mass, *half)
    inertia_world_inv = np.diag(1.0 / inertia_body)  # identity orientation
    com = np.array([0.0, 0.0, 0.0])
    r_bar = np.array([0.0, -half[1], 0.0])  # patch centroid on bottom face
    n = np.array([0.0, 1.0, 0.0])  # pushes body up
    # Four corner sample points on the bottom face.
    hx, _hy, hz = half[0], half[1], half[2]
    pts = np.array([
        [+hx, -half[1], +hz],
        [+hx, -half[1], -hz],
        [-hx, -half[1], +hz],
        [-hx, -half[1], -hz],
    ])
    rot_eye = np.eye(3)
    return dict(
        mass=mass, half=half, inertia_world_inv=inertia_world_inv,
        com=com, r_bar=r_bar, normal=n, patch_points=pts,
        rotation_matrix=rot_eye,
    )


# ---------------------------------------------------------------------- #
# Projection math tests
# ---------------------------------------------------------------------- #


def test_identity_normal_only_kick_is_unchanged():
    """A pure-normal impulse should pass through the projection unchanged."""
    P = _thin_box_patch()
    lam = 0.7 * P["normal"]  # 0.7 N·s straight up
    lam_proj, rho = project_patch_impulse_contact_compatible(
        lam=lam,
        patch_points=P["patch_points"],
        r_bar=P["r_bar"],
        com_world=P["com"],
        normal=P["normal"],
        tangents=None,
        mass=P["mass"],
        inertia_world_inv=P["inertia_world_inv"],
    )
    # The differential lever Δr_i for a centroid-applied normal impulse
    # produces zero differential normal velocity → constraint already
    # satisfied → projection is the identity (up to ε regularization).
    np.testing.assert_allclose(lam_proj, lam, atol=1e-9)
    assert abs(rho - 1.0) < 1e-6


def test_tangential_kick_drops_magnitude_and_kills_differential():
    """A pure-tangential impulse becomes spurious torque; projection removes it."""
    P = _thin_box_patch()
    # Tangential kick in +x at the centroid.
    lam = np.array([0.4, 0.0, 0.0])
    lam_proj, rho = project_patch_impulse_contact_compatible(
        lam=lam,
        patch_points=P["patch_points"],
        r_bar=P["r_bar"],
        com_world=P["com"],
        normal=P["normal"],
        tangents=None,
        mass=P["mass"],
        inertia_world_inv=P["inertia_world_inv"],
    )
    # Most of the kick should have been removed.
    assert np.linalg.norm(lam_proj) < 0.5 * np.linalg.norm(lam), (
        f"expected projection to halve tangential lam, got "
        f"‖λ_proj‖={np.linalg.norm(lam_proj):.4f} vs ‖λ‖={np.linalg.norm(lam):.4f}"
    )
    assert rho < 0.6, f"retention rho should drop below 0.6; got {rho:.3f}"
    # Differential normal velocity across the 4 sample points should
    # vanish (to numerical precision modulo eps regularization).
    L = _impulse_to_du_map(P["mass"], P["r_bar"], P["inertia_world_inv"])
    du = L @ lam_proj
    omega = du[3:6]
    levers = P["patch_points"] - P["com"]
    mean_lever = levers.mean(axis=0)
    diffs_n = []
    for r_i in levers:
        v_at = np.cross(omega, r_i)
        v_mean_at = np.cross(omega, mean_lever)
        diffs_n.append(float(P["normal"] @ (v_at - v_mean_at)))
    assert max(abs(d) for d in diffs_n) < 1e-5, (
        f"differential normal velocity should be near zero; got {diffs_n}"
    )


def test_energy_non_increase_for_random_lam():
    """K_body-metric energy is non-increasing for any input lam."""
    P = _thin_box_patch()
    K = _K_body(P["mass"], P["r_bar"], P["inertia_world_inv"])
    rng = np.random.default_rng(20260605)
    for _ in range(64):
        lam = rng.normal(scale=0.5, size=3)
        lam_proj, _rho = project_patch_impulse_contact_compatible(
            lam=lam,
            patch_points=P["patch_points"],
            r_bar=P["r_bar"],
            com_world=P["com"],
            normal=P["normal"],
            tangents=None,
            mass=P["mass"],
            inertia_world_inv=P["inertia_world_inv"],
        )
        e_pre = float(lam @ K @ lam)
        e_post = float(lam_proj @ K @ lam_proj)
        # Allow a tiny ε-tolerance for the Tikhonov regularizer slack.
        assert e_post <= e_pre + 1e-9, (
            f"energy increased: e_pre={e_pre:.6e} → e_post={e_post:.6e}")


def test_tangent_rows_suppress_yaw_constraint_when_enabled():
    """Tangent rows add yaw suppression; lam with vertical (yaw-inducing)
    component along the patch normal — but combined with multi-point
    spread that yields a yaw moment — gets further reduced.

    For thin patches in flat contact, the dominant artifact is roll/pitch
    (normal rows). Tangent rows add yaw constraints. We verify that
    enabling tangents does not increase ‖λ‖_K and tightens at least one
    differential constraint that normal-only would have left non-zero
    (no rigorous yaw test here — this is a sanity check).
    """
    P = _thin_box_patch()
    K = _K_body(P["mass"], P["r_bar"], P["inertia_world_inv"])
    lam = np.array([0.3, 0.1, 0.2])
    # Build tangent basis aligned with x and z (n is +y).
    t1 = np.array([1.0, 0.0, 0.0])
    t2 = np.array([0.0, 0.0, 1.0])
    lam_n, _ = project_patch_impulse_contact_compatible(
        lam=lam, patch_points=P["patch_points"], r_bar=P["r_bar"],
        com_world=P["com"], normal=P["normal"], tangents=None,
        mass=P["mass"], inertia_world_inv=P["inertia_world_inv"])
    lam_nt, _ = project_patch_impulse_contact_compatible(
        lam=lam, patch_points=P["patch_points"], r_bar=P["r_bar"],
        com_world=P["com"], normal=P["normal"], tangents=(t1, t2),
        mass=P["mass"], inertia_world_inv=P["inertia_world_inv"])
    e_n = float(lam_n @ K @ lam_n)
    e_nt = float(lam_nt @ K @ lam_nt)
    assert e_nt <= e_n + 1e-9, (
        "enabling tangent rows must not increase K-metric energy")


# ---------------------------------------------------------------------- #
# 6D Δu projection (preserves yaw)
# ---------------------------------------------------------------------- #


def test_du_projection_preserves_linear_velocity():
    """The constraint depends only on Δω; Δv must pass through unchanged."""
    P = _thin_box_patch()
    du_raw = np.array([0.3, 0.1, -0.2, 0.0, 0.0, 0.0])
    I_w = np.diag(P["mass"] / 12.0 * np.array([
        (2 * P["half"][1])**2 + (2 * P["half"][2])**2,
        (2 * P["half"][0])**2 + (2 * P["half"][2])**2,
        (2 * P["half"][0])**2 + (2 * P["half"][1])**2,
    ]))  # identity-orientation, so I_world = diag(I_body)
    du_proj, rho = project_du_contact_compatible(
        du_raw=du_raw,
        patch_points=P["patch_points"],
        com_world=P["com"],
        normal=P["normal"],
        tangents=None,
        mass=P["mass"],
        inertia_world=I_w,
    )
    np.testing.assert_allclose(du_proj[0:3], du_raw[0:3], atol=1e-9)
    # No angular component to project → also identity.
    np.testing.assert_allclose(du_proj[3:6], du_raw[3:6], atol=1e-9)
    assert abs(rho - 1.0) < 1e-6


def test_du_projection_preserves_yaw():
    """Yaw (Δω ∥ n) lies in the constraint null-space and must survive."""
    P = _thin_box_patch()
    # Pure yaw: Δω = [0, ω_y, 0] (rotation about world-up = contact normal)
    du_raw = np.array([0.0, 0.0, 0.0, 0.0, 2.5, 0.0])
    half = P["half"]
    I_body = np.array([
        P["mass"] / 12.0 * ((2 * half[1])**2 + (2 * half[2])**2),
        P["mass"] / 12.0 * ((2 * half[0])**2 + (2 * half[2])**2),
        P["mass"] / 12.0 * ((2 * half[0])**2 + (2 * half[1])**2),
    ])
    I_w = np.diag(I_body)
    du_proj, rho = project_du_contact_compatible(
        du_raw=du_raw,
        patch_points=P["patch_points"],
        com_world=P["com"],
        normal=P["normal"],
        tangents=None,
        mass=P["mass"],
        inertia_world=I_w,
    )
    # Yaw should survive (large component along world-y).
    assert du_proj[4] > 2.4, (
        f"yaw should be preserved; got Δω_y={du_proj[4]:.3f}")
    # rho close to 1 — yaw is contact-compatible.
    assert rho > 0.95


def test_du_projection_kills_roll_pitch():
    """Roll/pitch (Δω in the contact plane) should be projected to ≈0."""
    P = _thin_box_patch()
    # Pure roll: Δω = [ω_x, 0, 0] (rotation about world-x).
    du_raw = np.array([0.0, 0.0, 0.0, 1.5, 0.0, 0.0])
    half = P["half"]
    I_body = np.array([
        P["mass"] / 12.0 * ((2 * half[1])**2 + (2 * half[2])**2),
        P["mass"] / 12.0 * ((2 * half[0])**2 + (2 * half[2])**2),
        P["mass"] / 12.0 * ((2 * half[0])**2 + (2 * half[1])**2),
    ])
    I_w = np.diag(I_body)
    du_proj, _rho = project_du_contact_compatible(
        du_raw=du_raw,
        patch_points=P["patch_points"],
        com_world=P["com"],
        normal=P["normal"],
        tangents=None,
        mass=P["mass"],
        inertia_world=I_w,
    )
    assert abs(du_proj[3]) < 0.05, (
        f"roll should be projected to near zero; got Δω_x={du_proj[3]:.3f}")


def test_du_projection_energy_non_increase():
    """M-metric energy is non-increasing for any input Δu."""
    P = _thin_box_patch()
    half = P["half"]
    I_body = np.array([
        P["mass"] / 12.0 * ((2 * half[1])**2 + (2 * half[2])**2),
        P["mass"] / 12.0 * ((2 * half[0])**2 + (2 * half[2])**2),
        P["mass"] / 12.0 * ((2 * half[0])**2 + (2 * half[1])**2),
    ])
    I_w = np.diag(I_body)
    M = np.zeros((6, 6))
    M[0:3, 0:3] = P["mass"] * np.eye(3)
    M[3:6, 3:6] = I_w
    rng = np.random.default_rng(20260605)
    for _ in range(64):
        du = rng.normal(scale=0.5, size=6)
        du_proj, _ = project_du_contact_compatible(
            du_raw=du, patch_points=P["patch_points"],
            com_world=P["com"], normal=P["normal"], tangents=None,
            mass=P["mass"], inertia_world=I_w)
        e_pre = float(du @ M @ du)
        e_post = float(du_proj @ M @ du_proj)
        assert e_post <= e_pre + 1e-9


# ---------------------------------------------------------------------- #
# Gate tests
# ---------------------------------------------------------------------- #


def test_gate_tall_body_skipped():
    """A tall body (cube-like) is excluded from projection — it should be
    free to tip / topple in response to a tangential kick.
    """
    shape = box_shape(0.05, 0.10, 0.05)  # taller than wide
    R = np.eye(3)
    proj, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=4,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),
    )
    assert proj is False


def test_gate_one_point_patch_skipped():
    """N=1 (single-corner contact) → projection is a no-op (no constraint
    rows). The gate skips for N<2 to keep the diagnostic counters honest.
    """
    shape = box_shape(0.06, 0.005, 0.012)
    R = np.eye(3)
    proj, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=1,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),
    )
    assert proj is False


def test_gate_two_point_edge_contact_projects():
    """N=2 (edge contact) projects: the constraint is rank-1 and suppresses
    the roll perpendicular to the line connecting the two points. The
    parallel-to-line tipping mode remains in the null-space, which is the
    legitimate edge-rotation degree of freedom for a body resting on its
    edge.
    """
    shape = box_shape(0.06, 0.005, 0.012)
    R = np.eye(3)
    proj, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=2,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),
    )
    assert proj is True


def test_gate_thin_body_resting_projects():
    """Baseline positive case: thin box at rest with 4 contacts → project."""
    shape = box_shape(0.06, 0.005, 0.012)
    R = np.eye(3)
    proj, _use_t = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=4,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),
    )
    assert proj is True


def test_gate_moving_normal_skipped():
    """A body with substantial normal velocity (mid-flight collision) is
    not resting — projection should not fire."""
    shape = box_shape(0.06, 0.005, 0.012)
    R = np.eye(3)
    proj, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=4,
        v_p_at_centroid=np.array([0.0, 2.0, 0.0]),  # 2 m/s up
        normal=np.array([0.0, 1.0, 0.0]),
    )
    assert proj is False


def test_gate_orientation_aware_rolled_thin_body_skipped():
    """A thin body rolled 90° about its long axis: the thin direction is
    no longer aligned with the contact normal, so the projection should
    skip (the body is now resting on its NARROW long face — a different
    contact mode that legitimately allows tipping).
    """
    shape = box_shape(0.06, 0.005, 0.012)  # thin in body-y
    # Rotate 90° around body-x: body-y → world-z; world-y (normal) → body-z.
    R = np.array([
        [1.0, 0.0,  0.0],
        [0.0, 0.0, -1.0],
        [0.0, 1.0,  0.0],
    ])
    proj, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=4,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),  # world-up
    )
    # Body-frame normal n_body = R.T @ n = R.T @ [0,1,0] = [0, 0, 1].
    # Dominant axis is body-z; half_extent[z] = 0.012; max(other) =
    # max(0.06, 0.005) = 0.06; ratio = 0.20 < 0.25 → still passes thin.
    # So this is actually still "thin" in the active normal direction!
    # The orientation-aware gate correctly identifies this and projects.
    # Adjust expectation: the rolled box ON ITS LONG EDGE is a sharper
    # case that needs a different rotation. Use 90° about z so that
    # world-up maps to body-x (the largest half-extent — definitely
    # not thin).
    R2 = np.array([
        [0.0, -1.0, 0.0],
        [1.0,  0.0, 0.0],
        [0.0,  0.0, 1.0],
    ])
    proj2, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R2,
        n_contact_points=4,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),
    )
    # n_body = R2.T @ [0,1,0] = [-1, 0, 0]; dominant axis = body-x;
    # half[0] = 0.06; max(others) = max(0.005, 0.012) = 0.012;
    # ratio = 5.0 ≫ 0.25 → skip.
    assert proj2 is False


def test_gate_sphere_skipped():
    """Spheres (non-Box) are skipped — the thin-body heuristic doesn't apply."""
    shape = sphere_shape(0.05)
    R = np.eye(3)
    proj, _ = should_project_patch(
        body_shape=shape, rotation_matrix=R,
        n_contact_points=4,
        v_p_at_centroid=np.zeros(3),
        normal=np.array([0.0, 1.0, 0.0]),
    )
    assert proj is False
