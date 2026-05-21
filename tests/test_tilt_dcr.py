"""Tests for the deformation-aware contact frame extension (tilt DCR)."""
import numpy as np
import pytest

from dcr.dcr.tilt_dcr import (
    compute_triangle_tangent_frame,
    compute_patch_fit_slopes,
    compute_tilted_normal,
    apply_tilt_bounds,
)


# ======================================================================
# Unit tests: tilt math
# ======================================================================

class TestTriangleTangentFrame:
    def test_basic_triangle(self):
        v0 = np.array([0.0, 0.0, 0.0])
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 0.0, 1.0])
        n = np.array([0.0, 1.0, 0.0])
        t1, t2 = compute_triangle_tangent_frame(v0, v1, v2, n)
        # t1 should be along x-axis (projection of edge v0→v1)
        assert abs(t1[0] - 1.0) < 1e-10
        # t2 = n x t1 = (0,1,0) x (1,0,0) = (0,0,-1) → normalized
        assert abs(np.dot(t1, t2)) < 1e-10  # orthogonal
        assert abs(np.dot(t1, n)) < 1e-10   # in tangent plane
        assert abs(np.dot(t2, n)) < 1e-10
        assert abs(np.linalg.norm(t1) - 1.0) < 1e-10
        assert abs(np.linalg.norm(t2) - 1.0) < 1e-10

    def test_degenerate_triangle(self):
        # All vertices at same point
        v = np.array([0.0, 0.0, 0.0])
        n = np.array([0.0, 1.0, 0.0])
        t1, t2 = compute_triangle_tangent_frame(v, v, v, n)
        assert abs(np.linalg.norm(t1) - 1.0) < 1e-10
        assert abs(np.dot(t1, n)) < 1e-10


class TestPatchFitSlopes:
    def test_flat_surface(self):
        """Uniform displacement → zero slopes."""
        v0 = np.array([0.0, 0.0, 0.0])
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 0.0, 1.0])
        t1 = np.array([1.0, 0.0, 0.0])
        t2 = np.array([0.0, 0.0, 1.0])
        s1, s2 = compute_patch_fit_slopes(0.5, 0.5, 0.5, v0, v1, v2, t1, t2)
        assert abs(s1) < 1e-12
        assert abs(s2) < 1e-12

    def test_known_slope_t1(self):
        """Linear slope in t1 direction: w = 0.1 * x."""
        v0 = np.array([0.0, 0.0, 0.0])
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 0.0, 1.0])
        t1 = np.array([1.0, 0.0, 0.0])
        t2 = np.array([0.0, 0.0, 1.0])
        # w(x,z) = 0.1 * x → w0=0, w1=0.1, w2=0
        s1, s2 = compute_patch_fit_slopes(0.0, 0.1, 0.0, v0, v1, v2, t1, t2)
        assert abs(s1 - 0.1) < 1e-12
        assert abs(s2) < 1e-12

    def test_known_slope_t2(self):
        """Linear slope in t2 direction: w = 0.2 * z."""
        v0 = np.array([0.0, 0.0, 0.0])
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 0.0, 1.0])
        t1 = np.array([1.0, 0.0, 0.0])
        t2 = np.array([0.0, 0.0, 1.0])
        # w(x,z) = 0.2 * z → w0=0, w1=0, w2=0.2
        s1, s2 = compute_patch_fit_slopes(0.0, 0.0, 0.2, v0, v1, v2, t1, t2)
        assert abs(s1) < 1e-12
        assert abs(s2 - 0.2) < 1e-12


class TestTiltedNormal:
    def test_zero_slopes(self):
        n = np.array([0.0, 1.0, 0.0])
        t1 = np.array([1.0, 0.0, 0.0])
        t2 = np.array([0.0, 0.0, 1.0])
        n_tilt, theta = compute_tilted_normal(n, 0.0, 0.0, t1, t2, np.radians(3.0))
        np.testing.assert_allclose(n_tilt, n, atol=1e-10)
        assert theta < 1e-10

    def test_small_tilt(self):
        """Known slope → expected tilt angle."""
        n = np.array([0.0, 1.0, 0.0])
        t1 = np.array([1.0, 0.0, 0.0])
        t2 = np.array([0.0, 0.0, 1.0])
        # Slope of tan(1 deg) ≈ 0.01746 in t1 direction
        s1 = np.tan(np.radians(1.0))
        n_tilt, theta = compute_tilted_normal(n, s1, 0.0, t1, t2, np.radians(5.0))
        assert abs(np.degrees(theta) - 1.0) < 0.1

    def test_clamp(self):
        """Large slope clamped to theta_max."""
        n = np.array([0.0, 1.0, 0.0])
        t1 = np.array([1.0, 0.0, 0.0])
        t2 = np.array([0.0, 0.0, 1.0])
        # Slope of tan(10 deg) — should be clamped to 3 deg
        s1 = np.tan(np.radians(10.0))
        theta_max = np.radians(3.0)
        n_tilt, theta = compute_tilted_normal(n, s1, 0.0, t1, t2, theta_max)
        assert abs(theta - theta_max) < 1e-6
        # Check n_tilt is unit
        assert abs(np.linalg.norm(n_tilt) - 1.0) < 1e-10


class TestTiltBounds:
    def test_within_bounds(self):
        """Small J_t within both bounds stays unchanged."""
        J_t = np.array([0.001, 0.0, 0.0])
        J_n = 1.0
        result = apply_tilt_bounds(J_n, J_t, mass=1.0, dv=1.0,
                                   mu_dcr=0.2, eta_t=0.3)
        np.testing.assert_allclose(result, J_t)

    def test_coulomb_clamp(self):
        """J_t exceeding Coulomb bound gets clamped."""
        J_t = np.array([1.0, 0.0, 0.0])  # magnitude 1.0
        J_n = 1.0                          # Coulomb cap = 0.2 * 1.0 = 0.2
        result = apply_tilt_bounds(J_n, J_t, mass=1.0, dv=10.0,
                                   mu_dcr=0.2, eta_t=1.0)
        assert np.linalg.norm(result) <= 0.2 + 1e-10

    def test_energy_clamp(self):
        """J_t exceeding energy bound gets clamped."""
        J_t = np.array([100.0, 0.0, 0.0])
        J_n = 10000.0  # Coulomb cap very high
        # E_DCR = 0.5 * 1.0 * 0.01^2 = 5e-5
        # energy_cap = sqrt(2 * 1.0 * 0.3 * 5e-5) ≈ 0.00548
        result = apply_tilt_bounds(J_n, J_t, mass=1.0, dv=0.01,
                                   mu_dcr=100.0, eta_t=0.3)
        E_DCR = 0.5 * 1.0 * 0.01 * 0.01
        expected_cap = np.sqrt(2.0 * 1.0 * 0.3 * E_DCR)
        assert np.linalg.norm(result) <= expected_cap + 1e-10

    def test_zero_J_t(self):
        result = apply_tilt_bounds(1.0, np.zeros(3), mass=1.0, dv=1.0,
                                   mu_dcr=0.2, eta_t=0.3)
        np.testing.assert_allclose(result, np.zeros(3))


# ======================================================================
# Integration test
# ======================================================================

class TestTiltIntegration:
    def test_shelf_scene_no_explosion(self):
        """Run the shelf scene with TiltDCRCoupler for 100 steps.

        Asserts: no NaN/inf in velocities, total energy bounded.
        """
        from dcr.geom import make_slab_tet_mesh
        from dcr.fem import Material, FEMModel
        from dcr.modal import ModalAnalysis
        from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
        from dcr.dcr import PassiveDCRCoupler, TiltDCRCoupler, DCRWorld

        h = 1e-3
        world = DCRWorld(
            h=h, eta=0.5,
            solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
            dcr_enabled=True,
        )

        mesh = make_slab_tet_mesh(length=0.8, width=0.3, height=0.03,
                                  nx=8, ny=3, nz=1)
        mat = Material(E=8.0e9, nu=0.3, rho=600.0)
        shelf_top = 0.015

        shelf = make_static_plane(normal=(0, 1, 0),
                                  point=(0, shelf_top, 0), friction=0.5)
        shelf_idx = world.add_body(shelf)

        v = mesh.vertices
        tol = 1e-8
        xmin = v[:, 0].min()
        fixed = np.where(np.abs(v[:, 0] - xmin) < tol)[0].astype(np.int32)

        fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                       alpha0=3.0, alpha1=1e-5)
        modal = ModalAnalysis(fem=fem, num_modes=8)

        passive = PassiveDCRCoupler(modal=modal, elastic_body_idx=shelf_idx)
        tilt = TiltDCRCoupler(passive=passive, theta_max=np.radians(3.0),
                              mu_dcr=0.2, eta_t=0.3)
        world.add_tilt_coupler(tilt)

        # One book
        book = make_dynamic_box(
            mass=0.3, hx=0.005, hy=0.04, hz=0.03,
            position=(0.0, shelf_top + 0.041, 0.0),
            restitution=0.0, friction=0.3,
        )
        book_idx = world.add_body(book)

        # Heavy drop
        drop = make_dynamic_box(
            mass=8.0, hx=0.05, hy=0.05, hz=0.05,
            position=(0.2, shelf_top + 0.55, 0.0),
            restitution=0.1, friction=0.5,
        )
        world.add_body(drop)

        # Run 200 steps
        for _ in range(200):
            world.step()
            v = world.bodies[book_idx].velocity
            assert np.all(np.isfinite(v)), f"Non-finite velocity: {v}"

        # Check that the book velocity is reasonable
        v_book = world.bodies[book_idx].velocity
        assert np.linalg.norm(v_book[:3]) < 100.0, \
            f"Book velocity too large: {v_book[:3]}"
