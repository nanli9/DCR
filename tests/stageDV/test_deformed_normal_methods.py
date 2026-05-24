"""Unit + small-q A/B tests for the deformed-normal methods.

Two implementations of the deformed contact normal n' are available:

  - "patch_fit"    (default) — finite-difference (n·u) over the contact
                                triangle's 3 surface vertices and tilt
                                n_rest by the in-plane gradient.
  - "barbic_james" (new)     — F^{-T} push-forward using the analytical
                                FEM shape-function gradients of the
                                contact triangle's owning tet.

This file verifies that the new barbic_james implementation:
  (1) at rest (q = 0), returns n_rest exactly,
  (2) builds its cache correctly (uniqueness of tri→tet, Σᵢ ∇Nᵢ = 0),
  (3) the angular discrepancy vs patch_fit scales **linearly** with ‖q‖.

NOTE: an earlier draft of this file (and the surrounding docs) claimed
the two methods agree to O(‖q‖²). That was wrong. The methods agree at
q = 0 but differ at O(‖q‖) because the patch fit cannot see the modal
displacement at the 4th (interior) tet vertex — its shape function
vanishes on the surface triangle so the surface plane-fit misses it,
while the FEM gradient ∇N_D ⊗ u_D contributes linearly in q to F^{-T}.
This is the principled reason the BJ method is an upgrade, not a wash.

Reference: foundation §17; Barbič & James 2008 IEEE ToH §4.1
(see reference/BarbicJames-2008-IEEE-TOH.pdf).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from dcr.dcr.deformed_normal import (
    SurfaceTangentFrames,
    compute_deformed_normal,
)
from dcr.dcr.deformed_normal_bj import (
    BarbicJamesCache,
    build_barbic_james_cache,
    compute_deformed_normal_barbic_james,
)
from dcr.fem import FEMModel, Material
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis


# ----------------------------------------------------------------------
# Shared fixtures
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def modal():
    """Small fixed-corner slab modal analysis (matches test_dcr_velocity_modes)."""
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    tol = 1e-8
    xs = mesh.vertices[:, 0]
    zs = mesh.vertices[:, 2]
    x_min, x_max = xs.min(), xs.max()
    z_min, z_max = zs.min(), zs.max()
    on_xmin = np.abs(xs - x_min) < tol
    on_xmax = np.abs(xs - x_max) < tol
    on_zmin = np.abs(zs - z_min) < tol
    on_zmax = np.abs(zs - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)
    fem_model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                         alpha0=2.0, alpha1=1e-5)
    return ModalAnalysis(fem=fem_model, num_modes=10)


@pytest.fixture(scope="module")
def surface(modal):
    return modal.fem.mesh.extract_surface()


@pytest.fixture(scope="module")
def vert_to_surf_idx(modal):
    max_vert = modal.fem.mesh.num_vertices
    arr = np.full(max_vert, -1, dtype=np.int32)
    for si, vi in enumerate(modal.surface_vertex_indices):
        arr[vi] = si
    return arr


@pytest.fixture(scope="module")
def tangent_frames(surface):
    return SurfaceTangentFrames(surface=surface)


@pytest.fixture(scope="module")
def cache(modal, surface):
    return build_barbic_james_cache(modal, surface)


def _contact_point_above_slab(surface):
    """Pick the centroid of the first surface triangle as a representative
    contact point. Same convention as test_dcr_velocity_modes."""
    face = surface.faces[0]
    v0 = surface.vertices[face[0]]
    v1 = surface.vertices[face[1]]
    v2 = surface.vertices[face[2]]
    return (v0 + v1 + v2) / 3.0


def _rest_normal(surface):
    """Approximate rest normal at the first triangle (oriented +y for a slab)."""
    face = surface.faces[0]
    v0 = surface.vertices[face[0]]
    v1 = surface.vertices[face[1]]
    v2 = surface.vertices[face[2]]
    n_raw = np.cross(v1 - v0, v2 - v0)
    n = n_raw / np.linalg.norm(n_raw)
    # Orient so the y-component is positive (above-slab side).
    if n[1] < 0:
        n = -n
    return n


def _angle_between(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    return float(np.arccos(np.clip(a @ b, -1.0, 1.0)))


# ----------------------------------------------------------------------
# (1) At rest, F = I ⇒ n' == n_rest exactly.
# ----------------------------------------------------------------------

class TestBarbicJamesAtRest:
    def test_q_zero_returns_n_rest_exactly(self, modal, surface, cache):
        n_rest = _rest_normal(surface)
        x_c = _contact_point_above_slab(surface)
        q = np.zeros(modal.U.shape[1])

        n_prime, theta, _ = compute_deformed_normal_barbic_james(
            contact_point=x_c, push_dir=n_rest, q=q,
            surface=surface, cache=cache,
            theta_max=math.radians(3.0),
        )

        # At rest F = I, so F^{-T} · n_rest = n_rest. Tolerance is just
        # accumulated floating-point noise from the solve + normalize.
        assert np.allclose(n_prime, n_rest, atol=1e-14)
        assert abs(theta) < 1e-14
        assert abs(np.linalg.norm(n_prime) - 1.0) < 1e-14


# ----------------------------------------------------------------------
# (2) Cache correctness — uniqueness of tri→tet, FEM gradient identities.
# ----------------------------------------------------------------------

class TestBarbicJamesCacheBuild:
    def test_tri_to_tet_uniqueness(self, modal, surface, cache):
        """Every surface triangle was uniquely assigned to a tet, and the
        assignment is consistent (the 3 face vertices are 3 of the 4 tet
        vertices)."""
        n_faces = surface.faces.shape[0]
        assert cache.tri_to_tet.shape == (n_faces,)
        for fi in range(n_faces):
            ti = int(cache.tri_to_tet[fi])
            tet_vs = set(int(v) for v in cache.tet_vertex_indices[ti])
            face_vs = set(int(v) for v in surface.faces[fi])
            assert face_vs.issubset(tet_vs), (
                f"face {fi} verts {face_vs} not a subset of tet {ti} verts {tet_vs}")

    def test_grad_N_partition_of_unity(self, cache):
        """For a linear simplex, Σᵢ ∇Nᵢ = 0 (partition-of-unity property)."""
        sums = cache.tet_grad_N.sum(axis=1)   # (n_tets, 3)
        assert np.allclose(sums, 0.0, atol=1e-10), (
            f"max ‖Σᵢ ∇Nᵢ‖ = {np.max(np.abs(sums))}")

    def test_U_full_shape_matches_mesh(self, modal, cache):
        n_vertices = modal.fem.mesh.num_vertices
        n_modes = modal.U.shape[1]
        assert cache.U_full.shape == (3 * n_vertices, n_modes)
        # Constrained rows are zero.
        fixed_dofs = np.setdiff1d(
            np.arange(modal.fem.n_full_dofs), modal.fem.free_dofs)
        if fixed_dofs.size:
            assert np.all(cache.U_full[fixed_dofs, :] == 0.0)


# ----------------------------------------------------------------------
# (3) Small-q A/B agreement: O(‖q‖²) angular difference vs patch_fit.
# ----------------------------------------------------------------------

class TestSmallQDiscrepancyScalesLinearly:
    """The methods differ at first order in ‖q‖ (interior-tet-vertex
    contribution). Confirm: (a) both reduce to n_rest at q = 0, and
    (b) the angular discrepancy scales linearly with ‖q‖ (ratio of 10
    per 10× scale increase, modulo float noise floor)."""

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_linear_scaling(
        self, modal, surface, vert_to_surf_idx, tangent_frames,
        cache, seed,
    ):
        n_rest = _rest_normal(surface)
        x_c = _contact_point_above_slab(surface)
        rng = np.random.default_rng(seed)
        q_unit = rng.standard_normal(modal.U.shape[1])
        q_unit = q_unit / np.linalg.norm(q_unit)

        # Wide θ_max so the clamp doesn't truncate the comparison.
        theta_max = math.pi

        angles = []
        scales = [1e-6, 1e-5, 1e-4, 1e-3]
        for s in scales:
            q = s * q_unit
            # patch_fit takes q_history; feed it a single-row history.
            q_hist = q[np.newaxis, :]
            n_pf, _, _ = compute_deformed_normal(
                contact_point=x_c, push_dir=n_rest, q_history=q_hist,
                modal_U_surf=modal.U_surf,
                surface_vertex_indices=modal.surface_vertex_indices,
                surface=surface,
                vert_to_surf_idx=vert_to_surf_idx,
                tangent_frames=tangent_frames,
                theta_max=theta_max,
            )
            n_bj, _, _ = compute_deformed_normal_barbic_james(
                contact_point=x_c, push_dir=n_rest, q=q,
                surface=surface, cache=cache,
                theta_max=theta_max,
            )
            angles.append(_angle_between(n_pf, n_bj))

        # Each 10× increase in scale should give ~10× increase in angle
        # (linear regime). Allow 5% slack on the ratio.
        for i in range(len(scales) - 1):
            if angles[i] < 1e-14:
                continue  # below floating-point noise floor
            ratio = angles[i + 1] / angles[i]
            assert 9.5 < ratio < 10.5, (
                f"expected ~10× linear scaling between scales[{i}]={scales[i]}"
                f" and scales[{i+1}]={scales[i+1]}; got ratio={ratio:.3f}, "
                f"angles={angles}")

        # Also assert the regression: dθ/d‖q‖ coefficient is stable
        # across scales (within 1% — confirms it's truly linear and not
        # dominated by quadratic terms at the larger scales).
        coefs = [angles[i] / scales[i] for i in range(len(scales))]
        coef_range = max(coefs) - min(coefs)
        assert coef_range / max(coefs) < 0.01, (
            f"non-constant dθ/d‖q‖ coefficient: {coefs}")

    @pytest.mark.parametrize("seed", [0, 1, 2])
    @pytest.mark.parametrize("q_scale", [1e-6, 1e-4])
    def test_methods_return_unit_vectors(
        self, modal, surface, vert_to_surf_idx, tangent_frames,
        cache, seed, q_scale,
    ):
        n_rest = _rest_normal(surface)
        x_c = _contact_point_above_slab(surface)
        rng = np.random.default_rng(seed)
        q = q_scale * rng.standard_normal(modal.U.shape[1])
        q_hist = q[np.newaxis, :]

        n_pf, _, _ = compute_deformed_normal(
            contact_point=x_c, push_dir=n_rest, q_history=q_hist,
            modal_U_surf=modal.U_surf,
            surface_vertex_indices=modal.surface_vertex_indices,
            surface=surface,
            vert_to_surf_idx=vert_to_surf_idx,
            tangent_frames=tangent_frames,
            theta_max=math.pi,
        )
        n_bj, _, _ = compute_deformed_normal_barbic_james(
            contact_point=x_c, push_dir=n_rest, q=q,
            surface=surface, cache=cache,
            theta_max=math.pi,
        )

        assert abs(np.linalg.norm(n_pf) - 1.0) < 1e-12
        assert abs(np.linalg.norm(n_bj) - 1.0) < 1e-12

    def test_q_zero_both_methods_return_n_rest(
        self, modal, surface, vert_to_surf_idx, tangent_frames, cache,
    ):
        """Sanity: at q=0 both methods reduce to n_rest (no clamp involved)."""
        n_rest = _rest_normal(surface)
        x_c = _contact_point_above_slab(surface)
        q = np.zeros(modal.U.shape[1])
        q_hist = q[np.newaxis, :]

        n_pf, _, _ = compute_deformed_normal(
            contact_point=x_c, push_dir=n_rest, q_history=q_hist,
            modal_U_surf=modal.U_surf,
            surface_vertex_indices=modal.surface_vertex_indices,
            surface=surface,
            vert_to_surf_idx=vert_to_surf_idx,
            tangent_frames=tangent_frames,
            theta_max=math.radians(3.0),
        )
        n_bj, _, _ = compute_deformed_normal_barbic_james(
            contact_point=x_c, push_dir=n_rest, q=q,
            surface=surface, cache=cache,
            theta_max=math.radians(3.0),
        )
        assert np.allclose(n_pf, n_rest, atol=1e-12)
        assert np.allclose(n_bj, n_rest, atol=1e-14)


# ----------------------------------------------------------------------
# (4) Toggle integration — coupler builds the cache when method is set.
# ----------------------------------------------------------------------

class TestCouplerToggle:
    def test_unknown_method_raises(self, modal):
        from dcr.dcr import PassiveDCRCoupler
        with pytest.raises(ValueError, match="unknown deformed_normal_method"):
            PassiveDCRCoupler(
                modal=modal, elastic_body_idx=0,
                deformed_normal_method="not_a_real_method",
            )

    def test_patch_fit_default_no_cache_built(self, modal):
        from dcr.dcr import PassiveDCRCoupler
        c = PassiveDCRCoupler(modal=modal, elastic_body_idx=0)
        assert c.deformed_normal_method == "patch_fit"
        assert c._bj_cache is None

    def test_barbic_james_builds_cache(self, modal):
        from dcr.dcr import PassiveDCRCoupler
        c = PassiveDCRCoupler(
            modal=modal, elastic_body_idx=0,
            deformed_normal_method="barbic_james",
        )
        assert c._bj_cache is not None
        assert isinstance(c._bj_cache, BarbicJamesCache)
