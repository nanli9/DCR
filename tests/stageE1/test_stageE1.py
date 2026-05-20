"""Stage E1 acceptance tests — modal velocity-kick projection.

E1.3 criteria:
1. Single-mode toy basis (n_modes=1, constant vector field): s_c matches
   hand calculation for unit normal and unit tangential impulse.
2. Linearity: s(j1 + j2) == s(j1) + s(j2) to 1e-12.
3. Aggregation: two contacts summed matches one combined call.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.geom.mesh import TriMesh
from dcr.modal.passive_inject import (
    eval_basis_at_point,
    project_impulse,
    aggregate_kicks,
)


def _make_toy_basis():
    """Build a minimal surface mesh + constant mode basis for testing.

    A single quad (two triangles) on the XZ plane at y=0, vertices at
    (0,0,0), (1,0,0), (1,0,1), (0,0,1).

    Single mode (n_modes=1): constant displacement psi = [0, 1, 0] at every
    vertex (uniform vertical motion).

    Returns:
        surface, U_surf, surface_vertex_indices, vert_to_surf_idx
    """
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    faces = np.array([
        [0, 1, 2],
        [0, 2, 3],
    ], dtype=np.int32)
    surface = TriMesh(vertices=vertices, faces=faces)

    n_surf = 4
    n_modes = 1
    # Constant mode: psi = [0, 1, 0] at every vertex
    U_surf = np.zeros((3 * n_surf, n_modes), dtype=np.float64)
    for i in range(n_surf):
        U_surf[3 * i + 1, 0] = 1.0  # y-component = 1.0

    surface_vertex_indices = np.arange(n_surf, dtype=np.int32)

    vert_to_surf_idx = np.arange(n_surf, dtype=np.int32)

    return surface, U_surf, surface_vertex_indices, vert_to_surf_idx


def _make_multimode_basis():
    """Build a toy basis with 3 modes for richer testing.

    Same quad mesh. Modes:
      mode 0: psi = [1, 0, 0] (x-motion)
      mode 1: psi = [0, 1, 0] (y-motion)
      mode 2: psi = [0, 0, 1] (z-motion)
    """
    vertices = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 1.0],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    faces = np.array([
        [0, 1, 2],
        [0, 2, 3],
    ], dtype=np.int32)
    surface = TriMesh(vertices=vertices, faces=faces)

    n_surf = 4
    n_modes = 3
    U_surf = np.zeros((3 * n_surf, n_modes), dtype=np.float64)
    for i in range(n_surf):
        U_surf[3 * i + 0, 0] = 1.0  # mode 0: x
        U_surf[3 * i + 1, 1] = 1.0  # mode 1: y
        U_surf[3 * i + 2, 2] = 1.0  # mode 2: z

    surface_vertex_indices = np.arange(n_surf, dtype=np.int32)
    vert_to_surf_idx = np.arange(n_surf, dtype=np.int32)

    return surface, U_surf, surface_vertex_indices, vert_to_surf_idx


class TestSingleModeToyBasis:
    """E1.3 criterion 1: single-mode constant basis, hand-calculated results."""

    def test_normal_impulse_y(self) -> None:
        """Unit y-impulse on constant y-mode: s = 1.0."""
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.5, 0.0, 0.5])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)
        # Phi_x should be [[0], [1], [0]] (constant mode = [0,1,0])
        assert Phi_x.shape == (3, 1)
        np.testing.assert_allclose(Phi_x[:, 0], [0, 1, 0], atol=1e-12)

        j_normal = np.array([0.0, 1.0, 0.0])  # unit y impulse
        s = project_impulse(Phi_x, j_normal)
        # s = Phi^T j = [0,1,0] . [0,1,0] = 1.0
        assert s.shape == (1,)
        assert abs(s[0] - 1.0) < 1e-12

    def test_tangential_impulse_x(self) -> None:
        """Unit x-impulse on constant y-mode: s = 0.0 (orthogonal)."""
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.5, 0.0, 0.5])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)

        j_tangent = np.array([1.0, 0.0, 0.0])
        s = project_impulse(Phi_x, j_tangent)
        assert abs(s[0]) < 1e-12

    def test_diagonal_impulse(self) -> None:
        """Impulse [0, 3, 0] on y-mode: s = 3.0."""
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.25, 0.0, 0.75])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)

        j = np.array([0.0, 3.0, 0.0])
        s = project_impulse(Phi_x, j)
        assert abs(s[0] - 3.0) < 1e-12


class TestMultiMode:
    """Multi-mode basis: impulse projects onto each mode independently."""

    def test_identity_projection(self) -> None:
        """With orthonormal constant modes, Phi^T j = j."""
        surface, U_surf, svi, v2s = _make_multimode_basis()
        point = np.array([0.5, 0.0, 0.5])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)

        j = np.array([2.0, -3.0, 0.7])
        s = project_impulse(Phi_x, j)
        np.testing.assert_allclose(s, j, atol=1e-12)


class TestLinearity:
    """E1.3 criterion 2: s(j1 + j2) == s(j1) + s(j2)."""

    def test_linearity_single_mode(self) -> None:
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.3, 0.0, 0.6])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)

        j1 = np.array([1.0, 2.0, -1.0])
        j2 = np.array([-0.5, 3.0, 0.7])

        s1 = project_impulse(Phi_x, j1)
        s2 = project_impulse(Phi_x, j2)
        s_sum = project_impulse(Phi_x, j1 + j2)
        np.testing.assert_allclose(s_sum, s1 + s2, atol=1e-12)

    def test_linearity_multimode(self) -> None:
        surface, U_surf, svi, v2s = _make_multimode_basis()
        point = np.array([0.7, 0.0, 0.2])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)

        rng = np.random.default_rng(123)
        for _ in range(50):
            j1 = rng.standard_normal(3)
            j2 = rng.standard_normal(3)
            s1 = project_impulse(Phi_x, j1)
            s2 = project_impulse(Phi_x, j2)
            s_sum = project_impulse(Phi_x, j1 + j2)
            np.testing.assert_allclose(s_sum, s1 + s2, atol=1e-12)


class TestAggregation:
    """E1.3 criterion 3: two contacts summed == one combined call."""

    def test_aggregate_two_contacts(self) -> None:
        surface, U_surf, svi, v2s = _make_multimode_basis()

        point1 = np.array([0.2, 0.0, 0.3])
        point2 = np.array([0.8, 0.0, 0.7])
        j1 = np.array([1.0, -1.0, 0.5])
        j2 = np.array([0.3, 2.0, -0.4])

        Phi1 = eval_basis_at_point(point1, surface, U_surf, svi, v2s)
        Phi2 = eval_basis_at_point(point2, surface, U_surf, svi, v2s)

        s1 = project_impulse(Phi1, j1)
        s2 = project_impulse(Phi2, j2)

        s_aggregated = aggregate_kicks([s1, s2])
        s_manual_sum = s1 + s2

        np.testing.assert_allclose(s_aggregated, s_manual_sum, atol=1e-15)

    def test_aggregate_empty(self) -> None:
        s = aggregate_kicks([])
        assert len(s) == 0

    def test_aggregate_single(self) -> None:
        s1 = np.array([1.0, 2.0, 3.0])
        s_agg = aggregate_kicks([s1])
        np.testing.assert_allclose(s_agg, s1, atol=1e-15)


class TestEdgeCases:
    """Additional robustness checks."""

    def test_vertex_point(self) -> None:
        """Query exactly at a vertex."""
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.0, 0.0, 0.0])  # vertex 0
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)
        np.testing.assert_allclose(Phi_x[:, 0], [0, 1, 0], atol=1e-12)

    def test_edge_point(self) -> None:
        """Query on a triangle edge."""
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.5, 0.0, 0.0])  # midpoint of edge v0-v1
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)
        # Constant mode → same value everywhere
        np.testing.assert_allclose(Phi_x[:, 0], [0, 1, 0], atol=1e-12)

    def test_zero_impulse(self) -> None:
        """Zero impulse → zero kick."""
        surface, U_surf, svi, v2s = _make_toy_basis()
        point = np.array([0.5, 0.0, 0.5])
        Phi_x = eval_basis_at_point(point, surface, U_surf, svi, v2s)
        s = project_impulse(Phi_x, np.zeros(3))
        np.testing.assert_allclose(s, 0.0, atol=1e-15)
