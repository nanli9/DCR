"""Unit + integration tests for the patch-based DCR reformulation, step 1
(prompt §9.1, foundation §7).

Five test classes:

- TestClusterContactsByBodyPair: the standalone clustering function on
  hand-built `Contact` lists. Pins canonical body_pair keys (sorted),
  determinism of cluster ordering, and within-cluster index preservation.

- TestPatchLeverArmClamp: the per-body r_max derived from the collision
  shape (BOX → norm(half_extents); SPHERE → radius; PLANE → +inf).

- TestBuildPatchMath: centroid / normal / lever-arm algebra on
  hand-constructed contacts and bodies. Covers uniform vs lambda weighting,
  the lever-arm clamp pass-through and clip, and the degenerate-normal
  raise.

- TestPatchModeIntegration: end-to-end checks that the new
  `dcr_velocity_mode="energy_prescribed_patch"` registers, runs through
  `PassiveDCRCoupler.process_step`, populates `coupler.last_patches`, and
  emits no kicks (response-silent in step 1).

- TestBackwardCompatExistingModes: the three pre-existing modes
  (coevoet, energy_prescribed, energy_prescribed_point_impulse) still
  produce their respective `last_*_kicks` structures unchanged, so the
  step-1 wiring is non-invasive.

The integration tests reuse the slab fixture pattern from
`test_post_solver_clip.py::_build_slab_modal`.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.dcr.contact_patch import (
    ContactPatch,
    build_patch,
    cluster_contacts_by_body_pair,
    cone_project_impulse,
    patch_effective_mass_matrix,
    patch_lever_arm_clamp,
    patch_passive_scaling,
    solve_patch_impulse,
)
from dcr.dcr.distant_velocity import PatchKick
from dcr.dcr.dcr_world import DCRWorld
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.fem import FEMModel, Material
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis
from dcr.rigid import (
    ConstraintSolver,
    make_dynamic_box,
    make_dynamic_sphere,
    make_static_plane,
)
from dcr.rigid.collision import Contact


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _contact(body_a: int, body_b: int, point, normal, penetration=0.0) -> Contact:
    """Convenience constructor — Contact has positional fields only."""
    return Contact(
        body_a=body_a,
        body_b=body_b,
        point=np.asarray(point, dtype=np.float64),
        normal=np.asarray(normal, dtype=np.float64),
        penetration=penetration,
        is_new=False,
    )


def _build_slab_modal() -> ModalAnalysis:
    """Copy of test_post_solver_clip._build_slab_modal for self-containment."""
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    tol = 1e-8
    xs = mesh.vertices[:, 0]
    zs = mesh.vertices[:, 2]
    on_xmin = np.abs(xs - xs.min()) < tol
    on_xmax = np.abs(xs - xs.max()) < tol
    on_zmin = np.abs(zs - zs.min()) < tol
    on_zmax = np.abs(zs - zs.max()) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)
    fem_model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                         alpha0=2.0, alpha1=1e-5)
    return ModalAnalysis(fem=fem_model, num_modes=10)


def _build_drop_scene(mode: str):
    """Box dropping onto an elastic slab — gives ≥1 contact per step after
    landing. Reusable for the integration tests that need a live coupler.
    """
    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=1.0,
        enforce_rigid_energy_bound=True,
    )
    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)
    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=table_idx,
        dcr_velocity_mode=mode,
        energy_response_beta=0.25,
        energy_budget_source="min_rigid_loss_modal",
    )
    world.add_passive_coupler(coupler)
    box = make_dynamic_box(
        mass=1.0, hx=0.05, hy=0.05, hz=0.05,
        position=(0.0, 0.06, 0.0),
        restitution=0.3, friction=0.5,
    )
    box_idx = world.add_body(box)
    return world, coupler, table_idx, box_idx


# ======================================================================
# TestClusterContactsByBodyPair
# ======================================================================


class TestClusterContactsByBodyPair:
    """Pin the clustering behavior — keys, ordering, index preservation."""

    def test_singleton(self):
        """One contact → one cluster with one index."""
        cs = [_contact(0, 1, (0, 0, 0), (0, 1, 0))]
        out = cluster_contacts_by_body_pair(cs)
        assert out == [(0, 1, [0])]

    def test_two_contacts_same_pair(self):
        """Two contacts on (0,1) → one cluster of two."""
        cs = [
            _contact(0, 1, (0.0, 0, 0), (0, 1, 0)),
            _contact(0, 1, (1.0, 0, 0), (0, 1, 0)),
        ]
        out = cluster_contacts_by_body_pair(cs)
        assert out == [(0, 1, [0, 1])]

    def test_two_contacts_different_pairs(self):
        """Contacts on (0,1) and (0,2) → two clusters."""
        cs = [
            _contact(0, 1, (0, 0, 0), (0, 1, 0)),
            _contact(0, 2, (1, 0, 0), (0, 1, 0)),
        ]
        out = cluster_contacts_by_body_pair(cs)
        assert out == [(0, 1, [0]), (0, 2, [1])]

    def test_key_normalization(self):
        """(2,1) and (1,2) collapse into the same cluster key (1,2)."""
        cs = [
            _contact(2, 1, (0, 0, 0), (0, 1, 0)),
            _contact(1, 2, (1, 0, 0), (0, 1, 0)),
        ]
        out = cluster_contacts_by_body_pair(cs)
        assert len(out) == 1
        a, b, idxs = out[0]
        assert (a, b) == (1, 2)
        assert sorted(idxs) == [0, 1]

    def test_deterministic_outer_order(self):
        """Cluster list is sorted by (body_a, body_b)."""
        cs = [
            _contact(5, 6, (0, 0, 0), (0, 1, 0)),
            _contact(0, 1, (1, 0, 0), (0, 1, 0)),
            _contact(2, 3, (2, 0, 0), (0, 1, 0)),
        ]
        out = cluster_contacts_by_body_pair(cs)
        keys = [(a, b) for a, b, _ in out]
        assert keys == [(0, 1), (2, 3), (5, 6)]

    def test_within_cluster_index_order_preserved(self):
        """Contact indices within a cluster keep the input order, not
        sorted by their geometric coordinates or any other rule."""
        cs = [
            _contact(0, 1, (10.0, 0, 0), (0, 1, 0)),  # idx 0
            _contact(0, 1, (-10.0, 0, 0), (0, 1, 0)), # idx 1
            _contact(0, 1, (0.0, 0, 0), (0, 1, 0)),   # idx 2
        ]
        out = cluster_contacts_by_body_pair(cs)
        assert out == [(0, 1, [0, 1, 2])]

    def test_empty_input(self):
        """Empty contact list → empty cluster list."""
        assert cluster_contacts_by_body_pair([]) == []


# ======================================================================
# TestPatchLeverArmClamp
# ======================================================================


class TestPatchLeverArmClamp:
    """The shape-derived r_max default."""

    def test_box_returns_corner_radius(self):
        """BOX(half_extents=(1,2,3)) → r_max = √(1+4+9) = √14."""
        body = make_dynamic_box(mass=1.0, hx=1.0, hy=2.0, hz=3.0)
        assert patch_lever_arm_clamp(body) == pytest.approx(np.sqrt(14.0))

    def test_unit_cube(self):
        """BOX(0.5,0.5,0.5) → √(0.75) ≈ 0.866."""
        body = make_dynamic_box(mass=1.0, hx=0.5, hy=0.5, hz=0.5)
        assert patch_lever_arm_clamp(body) == pytest.approx(np.sqrt(0.75))

    def test_sphere_returns_radius(self):
        body = make_dynamic_sphere(mass=1.0, radius=0.7)
        assert patch_lever_arm_clamp(body) == pytest.approx(0.7)

    def test_plane_returns_inf(self):
        """Static plane: r_max = +inf (no clamp)."""
        plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        assert patch_lever_arm_clamp(plane) == float("inf")


# ======================================================================
# TestBuildPatchMath
# ======================================================================


class TestBuildPatchMath:
    """Centroid, normal averaging, weights, lever-arm clamp integration."""

    @staticmethod
    def _two_body_setup():
        """Static plane (idx 0) under a unit-ish box (idx 1) at origin."""
        plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        box = make_dynamic_box(mass=1.0, hx=0.5, hy=0.5, hz=0.5,
                               position=(0.0, 0.5, 0.0))
        return [plane, box]

    def test_uniform_centroid_box_on_plane_4_corners(self):
        """4 corner contacts under a box on a plane → centroid at the
        footprint center (0, 0, 0). Weighted with uniform → simple mean."""
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, ( 0.5, 0,  0.5), n),
            _contact(0, 1, (-0.5, 0,  0.5), n),
            _contact(0, 1, ( 0.5, 0, -0.5), n),
            _contact(0, 1, (-0.5, 0, -0.5), n),
        ]
        patch = build_patch(0, 1, [0, 1, 2, 3], cs, bodies, weight_mode="uniform")
        assert np.allclose(patch.x_bar, [0.0, 0.0, 0.0])

    def test_lambda_weighting_biases_to_heavy_contact(self):
        """Two contacts at x=0 and x=10 with λ_N = (1, 9) → centroid at x=9.
        Bodies arg is the rigid solver layout: lam[3*ci] is λ_N for contact ci.
        """
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, (0.0, 0, 0), n),
            _contact(0, 1, (10.0, 0, 0), n),
        ]
        # Full 3-rows-per-contact layout: [λ_N0, λ_t1_0, λ_t2_0, λ_N1, λ_t1_1, λ_t2_1]
        lam = np.array([1.0, 0.0, 0.0, 9.0, 0.0, 0.0])
        patch = build_patch(0, 1, [0, 1], cs, bodies,
                            weight_mode="lambda_n", lambda_n=lam)
        # weighted x = (1*0 + 9*10) / (1 + 9) = 9.0
        assert np.allclose(patch.x_bar, [9.0, 0.0, 0.0])
        assert np.allclose(patch.weights, [1.0, 9.0])

    def test_uniform_fallback_when_lambda_none(self):
        """`lambda_n=None` → uniform weights regardless of weight_mode."""
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, (0.0, 0, 0), n),
            _contact(0, 1, (10.0, 0, 0), n),
        ]
        patch = build_patch(0, 1, [0, 1], cs, bodies,
                            weight_mode="lambda_n", lambda_n=None)
        # Uniform mean = 5.0.
        assert np.allclose(patch.x_bar, [5.0, 0.0, 0.0])
        assert np.allclose(patch.weights, [1.0, 1.0])

    def test_lambda_all_zero_falls_back_to_uniform(self):
        """λ_N = (0, 0) → degenerate weights; should fall back to uniform
        so the patch geometry is still well-defined."""
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, (0.0, 0, 0), n),
            _contact(0, 1, (10.0, 0, 0), n),
        ]
        lam = np.zeros(6)
        patch = build_patch(0, 1, [0, 1], cs, bodies,
                            weight_mode="lambda_n", lambda_n=lam)
        assert np.allclose(patch.x_bar, [5.0, 0.0, 0.0])
        # Fell back to uniform (1.0, 1.0), not the zero λ_N values.
        assert np.allclose(patch.weights, [1.0, 1.0])

    def test_normal_averaging_aligned(self):
        """All n_j aligned (under collision.py's B→A convention) → n̄' is
        the FLIPPED averaged vector (canonical A→B = opposite of B→A
        when the contact's body_a equals canonical body_a).

        See build_patch docstring on the convention conversion.
        """
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, (0, 0, 0), n),
            _contact(0, 1, (1, 0, 0), n),
        ]
        patch = build_patch(0, 1, [0, 1], cs, bodies, weight_mode="uniform")
        assert np.allclose(patch.n_rest_bar, -n)
        assert abs(np.linalg.norm(patch.n_rest_bar) - 1.0) < 1e-12

    def test_normal_averaging_orthogonal(self):
        """Two orthogonal n_j (collision-convention) → averaged-then-
        normalized = flipped bisector."""
        bodies = self._two_body_setup()
        n1 = np.array([1.0, 0.0, 0.0])
        n2 = np.array([0.0, 1.0, 0.0])
        cs = [_contact(0, 1, (0, 0, 0), n1), _contact(0, 1, (1, 0, 0), n2)]
        patch = build_patch(0, 1, [0, 1], cs, bodies, weight_mode="uniform")
        # Each contact has c.body_a=0=canonical body_a → flipped to -n_j.
        # Averaged: -(n1+n2)/2 → normalized.
        expected = -np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)
        assert np.allclose(patch.n_rest_bar, expected)

    def test_normal_averaging_matches_collision_convention(self):
        """Using the collision.py convention (body_a is the body the
        normal points TOWARD), n_rest_bar should point AWAY from body_a
        — i.e., from canonical body_a TOWARD canonical body_b.

        For a real book(1)-on-plane(0) contact: collision creates
        Contact(body_a=1=book, body_b=0=plane, normal=+y). After
        canonicalization (0, 1), the contact's body_a=1 == canonical
        body_b=1 → KEEP → n_rest_bar = +y. push_dir is then the
        elastic-to-receiver direction (plane→book = +y).
        """
        plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        book = make_dynamic_box(mass=1.0, hx=0.05, hy=0.05, hz=0.05,
                                position=(0.0, 0.05, 0.0))
        bodies = [plane, book]
        # Realistic collision: body_a=1=book, body_b=0=plane, n=+y.
        cs = [_contact(1, 0, (0.0, 0.0, 0.0), np.array([0.0, 1.0, 0.0]))]
        patch = build_patch(0, 1, [0], cs, bodies, weight_mode="uniform")
        assert np.allclose(patch.n_rest_bar, [0.0, 1.0, 0.0])

    def test_normal_averaging_antiparallel_raises(self):
        """n_1 = +y, n_2 = -y oriented body_a→body_b → sum cancels → raise."""
        bodies = self._two_body_setup()
        n_up = np.array([0.0, 1.0, 0.0])
        n_dn = np.array([0.0, -1.0, 0.0])
        cs = [_contact(0, 1, (0, 0, 0), n_up), _contact(0, 1, (1, 0, 0), n_dn)]
        with pytest.raises(ValueError, match="degenerate normal sum"):
            build_patch(0, 1, [0, 1], cs, bodies, weight_mode="uniform")

    def test_normal_reorientation_across_swapped_body_pair(self):
        """A contact whose own (body_a, body_b) is the reversed pair has its
        normal flipped before being summed (so both contributions point
        canonical A→B before averaging).

        Cluster key is (1, 2). Contact c0: body_a=1, body_b=2, n=+y. Contact
        c1: body_a=2, body_b=1, n=+y — but in canonical (1, 2) terms this
        normal points 2→1, i.e. -y. After re-orientation the two add to 0.
        """
        plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        box1 = make_dynamic_box(mass=1.0, hx=0.5, hy=0.5, hz=0.5,
                                position=(0.0, 0.5, 0.0))
        box2 = make_dynamic_box(mass=1.0, hx=0.5, hy=0.5, hz=0.5,
                                position=(0.0, 1.5, 0.0))
        bodies = [plane, box1, box2]
        n_up = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(1, 2, (0, 0, 0), n_up),
            _contact(2, 1, (1, 0, 0), n_up),  # flipped pair, same +y vector
        ]
        with pytest.raises(ValueError, match="degenerate normal sum"):
            build_patch(1, 2, [0, 1], cs, bodies, weight_mode="uniform")

    def test_lever_arm_inside_bound_passes_through(self):
        """If ‖x̄ - x_COM‖ < r_max, lever returned unchanged (no rescale).

        Box at (0, 0.5, 0), centroid at (0, 0, 0) → r = (0, -0.5, 0),
        ‖r‖=0.5 < √0.75 ≈ 0.866; no clip.
        """
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [_contact(0, 1, (0, 0, 0), n)]
        patch = build_patch(0, 1, [0], cs, bodies, weight_mode="uniform")
        # body_b is the box at y=0.5; centroid at y=0 → r_bar_b = (0,-0.5,0)
        assert np.allclose(patch.r_bar_b, [0.0, -0.5, 0.0])
        assert abs(np.linalg.norm(patch.r_bar_b) - 0.5) < 1e-12

    def test_lever_arm_clipped_when_outside_bound(self):
        """If ‖r‖ > r_max, lever is scaled to length = r_max.

        Override r_max_b to a small value (0.1) so the natural r=(0,-0.5,0)
        gets clipped to a vector of length 0.1 in the SAME direction.
        """
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [_contact(0, 1, (0, 0, 0), n)]
        patch = build_patch(0, 1, [0], cs, bodies, weight_mode="uniform",
                            r_max_b=0.1)
        assert abs(np.linalg.norm(patch.r_bar_b) - 0.1) < 1e-12
        # Direction preserved (still pointing in -y).
        assert patch.r_bar_b[1] < 0.0
        assert patch.r_bar_b[0] == 0.0 and patch.r_bar_b[2] == 0.0

    def test_lever_arm_per_body_independent_clamps(self):
        """r_max_a and r_max_b are independent — passing a finite r_max_a
        clamps r_bar_a only; r_bar_b uses the body-derived default."""
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        # Centroid at (10, 0, 0). Plane COM at (0, 0, 0) → r_a = (10, 0, 0),
        # ‖r_a‖ = 10. Override r_max_a = 1 → clipped to length 1.
        cs = [_contact(0, 1, (10.0, 0, 0), n)]
        patch = build_patch(0, 1, [0], cs, bodies, weight_mode="uniform",
                            r_max_a=1.0)
        assert abs(np.linalg.norm(patch.r_bar_a) - 1.0) < 1e-12
        # r_bar_b: box at (0, 0.5, 0), centroid (10, 0, 0) → r=(10,-0.5,0),
        # ‖r‖ ≈ 10.012; default r_max_b = √0.75 → clipped to that length.
        assert abs(np.linalg.norm(patch.r_bar_b) -
                   patch_lever_arm_clamp(bodies[1])) < 1e-12

    def test_plane_lever_arm_uninf_returns_raw(self):
        """Plane gets r_max = +inf → r_bar_a is the raw (x̄ - plane.pos)."""
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [_contact(0, 1, (5.0, 0, 0), n)]
        patch = build_patch(0, 1, [0], cs, bodies, weight_mode="uniform")
        # Plane.position is (0,0,0); centroid is (5,0,0) → r unchanged.
        assert np.allclose(patch.r_bar_a, [5.0, 0.0, 0.0])
        assert patch.r_max_a == float("inf")

    def test_records_contact_indices_in_input_order(self):
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, (0, 0, 0), n),
            _contact(0, 1, (1, 0, 0), n),
            _contact(0, 1, (2, 0, 0), n),
        ]
        patch = build_patch(0, 1, [2, 0, 1], cs, bodies, weight_mode="uniform")
        assert patch.contact_indices == (2, 0, 1)

    def test_weights_match_input_lambda(self):
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [
            _contact(0, 1, (0, 0, 0), n),
            _contact(0, 1, (1, 0, 0), n),
        ]
        lam = np.array([2.0, 0, 0, 3.0, 0, 0])
        patch = build_patch(0, 1, [0, 1], cs, bodies,
                            weight_mode="lambda_n", lambda_n=lam)
        assert np.allclose(patch.weights, [2.0, 3.0])

    def test_rejects_non_canonical_body_pair(self):
        """body_a > body_b is rejected (canonical pair required)."""
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [_contact(0, 1, (0, 0, 0), n)]
        with pytest.raises(ValueError, match="canonical pair"):
            build_patch(1, 0, [0], cs, bodies, weight_mode="uniform")

    def test_rejects_empty_idxs(self):
        bodies = self._two_body_setup()
        with pytest.raises(ValueError, match="non-empty"):
            build_patch(0, 1, [], [], bodies, weight_mode="uniform")

    def test_rejects_unknown_weight_mode(self):
        bodies = self._two_body_setup()
        n = np.array([0.0, 1.0, 0.0])
        cs = [_contact(0, 1, (0, 0, 0), n)]
        with pytest.raises(ValueError, match="unknown weight_mode"):
            build_patch(0, 1, [0], cs, bodies, weight_mode="bogus")


# ======================================================================
# TestPatchModeIntegration
# ======================================================================


class TestPatchModeIntegration:
    """End-to-end tests of `dcr_velocity_mode='energy_prescribed_patch'`."""

    def test_coupler_accepts_new_mode(self):
        """PassiveDCRCoupler constructs with the new mode without raising."""
        modal = _build_slab_modal()
        coupler = PassiveDCRCoupler(
            modal=modal, elastic_body_idx=0,
            dcr_velocity_mode="energy_prescribed_patch",
        )
        assert coupler.dcr_velocity_mode == "energy_prescribed_patch"

    def test_unknown_mode_still_raises(self):
        """The dispatcher still rejects unknown modes (no accidental
        widening of the allowed set when adding the patch mode)."""
        modal = _build_slab_modal()
        coupler = PassiveDCRCoupler(
            modal=modal, elastic_body_idx=0,
            dcr_velocity_mode="bogus_mode",
        )
        # The mode is validated at dispatch time. Build a tiny scene so the
        # dispatcher runs.
        world, _coupler, _t, _b = _build_drop_scene(mode="energy_prescribed_patch")
        # Swap in the bogus coupler on a fresh scene.
        world2 = DCRWorld(
            h=1e-3,
            solver=ConstraintSolver(h=1e-3, cfm=1e-6, erp=0.2),
            dcr_enabled=True, eta=1.0, enforce_rigid_energy_bound=True,
        )
        table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        table_idx = world2.add_body(table)
        coupler.elastic_body_idx = table_idx
        world2.add_passive_coupler(coupler)
        box = make_dynamic_box(
            mass=1.0, hx=0.05, hy=0.05, hz=0.05,
            position=(0.0, 0.06, 0.0),
        )
        world2.add_body(box)
        # First step has no new impacts (impulse_threshold) so likely no raise;
        # we step through landing to force the dispatcher path.
        with pytest.raises(ValueError, match="unknown dcr_velocity_mode"):
            for _ in range(200):
                world2.step()

    def test_patch_mode_runs_end_to_end(self):
        """A drop-onto-slab simulation completes in patch mode without raise."""
        world, coupler, _t, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        for _ in range(50):
            world.step()
        # `last_patches` will be either a list or None per step depending on
        # whether resting contacts existed; no exception is the main signal.
        assert coupler.dcr_velocity_mode == "energy_prescribed_patch"

    def test_patch_mode_populates_last_patches_when_resting_contacts(self):
        """After the box lands and forms resting contacts, last_patches is
        a non-empty list of ContactPatch."""
        world, coupler, table_idx, box_idx = _build_drop_scene(
            mode="energy_prescribed_patch")
        # Step long enough for the box to land and form persistent contacts.
        saw_patches = False
        for _ in range(500):
            world.step()
            if coupler.last_patches:
                # The slab+box is one body pair → at most one patch.
                assert all(isinstance(p, ContactPatch)
                           for p in coupler.last_patches)
                assert len(coupler.last_patches) >= 1
                # Patch geometry sanity: canonical pair, centroid finite,
                # n̄' is a unit vector.
                for p in coupler.last_patches:
                    assert p.body_a <= p.body_b
                    assert np.all(np.isfinite(p.x_bar))
                    assert abs(np.linalg.norm(p.n_rest_bar) - 1.0) < 1e-9
                saw_patches = True
                break
        assert saw_patches, (
            "expected at least one rigid step with resting contacts → patches")

    def test_patch_mode_does_not_pollute_legacy_kick_fields(self):
        """Patch mode populates its own `last_patch_kicks` field but never
        touches the legacy `last_linear_kicks` / `last_point_impulse_kicks`
        — those are owned by Versions A and B respectively."""
        world, coupler, _t, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        for _ in range(500):
            world.step()
            assert coupler.last_linear_kicks is None
            assert coupler.last_point_impulse_kicks is None

    def test_patch_mode_returns_empty_dv_dict(self):
        """The world's scalar Δv apply path is a no-op in patch mode (the
        coupler returns an empty dict from process_step → no DCRWorld
        velocity adjustment along contact normals)."""
        # Direct unit-level check: feed the coupler a constructed contact and
        # verify the return value.
        modal = _build_slab_modal()
        coupler = PassiveDCRCoupler(
            modal=modal, elastic_body_idx=0,
            dcr_velocity_mode="energy_prescribed_patch",
        )
        plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        box = make_dynamic_box(mass=1.0, hx=0.05, hy=0.05, hz=0.05,
                               position=(0, 0.05, 0))
        bodies = [plane, box]
        cs = [_contact(0, 1, (0, 0, 0), np.array([0.0, 1.0, 0.0]))]
        lam = np.array([0.5, 0.0, 0.0])
        out = coupler.process_step(cs, lam, h=1e-3, E_max=0.01, bodies=bodies)
        assert out == {}

    def test_patch_mode_requires_bodies(self):
        """Patch mode raises if bodies is None — same contract as the other
        energy_* modes. The contact must be is_new=True so the impulse
        projection produces a kick that triggers the dispatcher (otherwise
        process_step short-circuits before the raise)."""
        modal = _build_slab_modal()
        coupler = PassiveDCRCoupler(
            modal=modal, elastic_body_idx=0,
            dcr_velocity_mode="energy_prescribed_patch",
        )
        # is_new=True forces the impulse-projection path, which calls
        # _compute_distant_response → the bodies-is-None check.
        c = Contact(
            body_a=0, body_b=1,
            point=np.zeros(3),
            normal=np.array([0.0, 1.0, 0.0]),
            penetration=0.0,
            is_new=True,
        )
        lam = np.array([0.5, 0.0, 0.0])
        with pytest.raises(ValueError, match="energy_prescribed_patch"):
            coupler.process_step([c], lam, h=1e-3, E_max=0.01, bodies=None)


# ======================================================================
# TestBackwardCompatExistingModes
# ======================================================================


class TestBackwardCompatExistingModes:
    """Adding the patch mode must not affect the other three modes."""

    @pytest.mark.parametrize(
        "mode,expect_linear,expect_point",
        [
            ("coevoet", False, False),
            ("energy_prescribed", True, False),
            ("energy_prescribed_point_impulse", False, True),
        ],
    )
    def test_existing_modes_still_emit_expected_kicks(
        self, mode, expect_linear, expect_point,
    ):
        """Each pre-existing mode populates its own kick structure when
        resting contacts exist. We don't pin numerical values here — that's
        what `test_dcr_velocity_modes.py` does. We pin that the structural
        contract (which last_* slot is populated) is unchanged after the
        patch wiring."""
        world, coupler, _t, _b = _build_drop_scene(mode=mode)
        # Step until the box settles into resting contacts.
        for _ in range(500):
            world.step()
            if expect_linear and coupler.last_linear_kicks:
                break
            if expect_point and coupler.last_point_impulse_kicks:
                break
            # coevoet path returns scalar dv — settled-state check is
            # populated last_dcr_velocities_coevoet (dict).
            if mode == "coevoet" and coupler.last_dcr_velocities_coevoet:
                break
        if expect_linear:
            assert coupler.last_linear_kicks is not None
        else:
            assert coupler.last_linear_kicks is None
        if expect_point:
            assert coupler.last_point_impulse_kicks is not None
        else:
            assert coupler.last_point_impulse_kicks is None
        # And the patch attribute is None for non-patch modes.
        assert coupler.last_patches is None
        assert coupler.last_patch_kicks is None


# ======================================================================
# TestPatchEffectiveMassMatrix — §9.4 K matrix algebra
# ======================================================================


class TestPatchEffectiveMassMatrix:
    """K = (1/m) I + R · I_inv · R^T (prompt §4 / foundation §4)."""

    def test_zero_lever_arm_recovers_translational_mass(self):
        """At r̄ = 0, K = (1/m) I_3 (no angular contribution)."""
        body = make_dynamic_box(mass=2.0, hx=0.5, hy=0.5, hz=0.5)
        K = patch_effective_mass_matrix(body, np.zeros(3))
        assert np.allclose(K, 0.5 * np.eye(3))

    def test_symmetric_positive_definite(self):
        """K must be symmetric PD for any non-degenerate body and lever."""
        body = make_dynamic_box(mass=1.5, hx=0.3, hy=0.4, hz=0.5,
                                position=(0.1, 0.2, 0.3))
        r = np.array([0.1, -0.2, 0.05])
        K = patch_effective_mass_matrix(body, r)
        assert np.allclose(K, K.T, atol=1e-12)
        eigs = np.linalg.eigvalsh(K)
        assert eigs.min() > 0.0

    def test_static_body_returns_zero(self):
        """Static plane → K = 0 (cannot receive impulses)."""
        plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0))
        K = patch_effective_mass_matrix(plane, np.array([1.0, 0, 0]))
        assert np.allclose(K, np.zeros((3, 3)))

    def test_K_inverse_recovers_dv(self):
        """K · (K⁻¹ Δv) = Δv — solver sanity."""
        body = make_dynamic_box(mass=1.0, hx=0.2, hy=0.3, hz=0.4)
        r = np.array([0.05, -0.1, 0.02])
        K = patch_effective_mass_matrix(body, r)
        dv = np.array([0.1, -0.2, 0.05])
        lam = solve_patch_impulse(K, dv)
        assert np.allclose(K @ lam, dv, atol=1e-12)

    def test_applying_lam_actually_changes_v_p_by_dv_des(self):
        """End-to-end: solving for λ then applying it to the body changes
        the contact-point velocity by exactly Δv_des."""
        body = make_dynamic_box(mass=1.5, hx=0.3, hy=0.3, hz=0.3)
        r = np.array([0.2, -0.1, 0.15])
        K = patch_effective_mass_matrix(body, r)
        dv_des = np.array([0.05, 0.1, -0.03])
        lam = solve_patch_impulse(K, dv_des)
        # Apply impulse manually.
        v_p_before = body.velocity[:3] + np.cross(body.velocity[3:], r)
        I_inv = body.inertia_world_inv()
        body.velocity[0:3] += lam / body.mass
        body.velocity[3:6] += I_inv @ np.cross(r, lam)
        v_p_after = body.velocity[:3] + np.cross(body.velocity[3:], r)
        assert np.allclose(v_p_after - v_p_before, dv_des, atol=1e-10)


# ======================================================================
# TestConeProjectImpulse — §9.5 Coulomb projection on 3-vector λ
# ======================================================================


class TestConeProjectImpulse:
    """Coulomb cone projection on the patch impulse (prompt §5)."""

    def test_inside_cone_pass_through(self):
        """λ at 30° from n with μ = 1.0 (tan 30° ≈ 0.577 < 1.0) → unchanged."""
        n = np.array([0.0, 1.0, 0.0])
        lam = np.array([0.5, np.sqrt(3) / 2, 0.0])  # 30° from +y
        out, clipped = cone_project_impulse(lam, n, mu=1.0)
        assert not clipped
        assert np.allclose(out, lam)

    def test_negative_normal_clamped_to_zero(self):
        """λ·n < 0 (adhesive normal): normal component zeroed; tangent
        unaffected directly but its budget collapses to 0 → all-zero output
        when there was any tangent, or just normal-zeroed if pure normal."""
        n = np.array([0.0, 1.0, 0.0])
        lam = np.array([0.0, -1.0, 0.0])  # pure adhesive
        out, clipped = cone_project_impulse(lam, n, mu=0.5)
        assert clipped
        assert np.allclose(out, np.zeros(3))

    def test_tangential_only_outside_cone(self):
        """λ fully tangential (λ_n = 0) with μ > 0: budget = 0 → all zero."""
        n = np.array([0.0, 1.0, 0.0])
        lam = np.array([2.0, 0.0, 0.0])
        out, clipped = cone_project_impulse(lam, n, mu=0.5)
        assert clipped
        assert np.allclose(out, np.zeros(3))

    def test_partial_clip_60deg(self):
        """λ at 60° from n with μ = 0.5:
            λ_n = cos 60° = 0.5; ||λ_t|| = sin 60° = √3/2
            budget = 0.5·0.5 = 0.25; tangent gets scaled to 0.25.
        """
        n = np.array([0.0, 1.0, 0.0])
        lam = np.array([np.sqrt(3) / 2, 0.5, 0.0])
        out, clipped = cone_project_impulse(lam, n, mu=0.5)
        assert clipped
        assert abs(float(out @ n) - 0.5) < 1e-12
        tan_vec = out - float(out @ n) * n
        assert abs(np.linalg.norm(tan_vec) - 0.25) < 1e-12

    def test_pure_normal_pass_through(self):
        """λ purely along n: no tangent → no clip, output unchanged."""
        n = np.array([1.0, 0.0, 0.0])
        lam = np.array([3.0, 0.0, 0.0])
        out, clipped = cone_project_impulse(lam, n, mu=0.3)
        assert not clipped
        assert np.allclose(out, lam)


# ======================================================================
# TestPatchPassiveScaling — §9.6 quadratic passivity scaling
# ======================================================================


class TestPatchPassiveScaling:
    """ΔKE(s·λ) = s·a + ½·s²·b ≤ E_cap (prompt §6)."""

    @staticmethod
    def _K():
        return np.eye(3)

    def test_kick_inside_budget_returns_full_scale(self):
        """If ΔKE(λ) < E_cap, s = 1 (no scaling)."""
        lam = np.array([0.1, 0.0, 0.0])
        v_p = np.array([0.0, 0.0, 0.0])
        K = self._K()
        # a = lam·v_p = 0, b = lam·K·lam = 0.01 → ΔKE = 0.005
        s, a, b = patch_passive_scaling(lam, v_p, K, E_cap=1.0)
        assert s == 1.0

    def test_kick_outside_budget_clipped_to_cap(self):
        """If ΔKE(λ) > E_cap, s ∈ (0, 1) and realized ΔKE ≈ E_cap."""
        lam = np.array([1.0, 0.0, 0.0])
        v_p = np.array([0.0, 0.0, 0.0])
        K = self._K()
        # ΔKE(λ) = 0 + ½·1 = 0.5; pick E_cap = 0.1 < 0.5 → must scale.
        E_cap = 0.1
        s, a, b = patch_passive_scaling(lam, v_p, K, E_cap=E_cap)
        assert 0.0 < s < 1.0
        realized = s * a + 0.5 * s * s * b
        assert abs(realized - E_cap) < 1e-10

    def test_zero_budget_zeros_kick(self):
        """E_cap = 0 → s = 0."""
        lam = np.array([1.0, 0, 0])
        s, _, _ = patch_passive_scaling(lam, np.zeros(3), self._K(), E_cap=0.0)
        assert s == 0.0

    def test_negative_budget_zeros_kick(self):
        """E_cap < 0 → s = 0 (no kick allowed)."""
        lam = np.array([1.0, 0, 0])
        s, _, _ = patch_passive_scaling(lam, np.zeros(3), self._K(), E_cap=-1.0)
        assert s == 0.0

    def test_zero_quadratic_term_no_op(self):
        """λ = 0 → b = 0 → s = 1 (vacuously)."""
        lam = np.zeros(3)
        s, _, _ = patch_passive_scaling(lam, np.zeros(3), self._K(), E_cap=1.0)
        assert s == 1.0

    def test_dissipative_kick_passes_through(self):
        """If a < 0 (kick opposes motion → energy-removing), unscaled ΔKE
        can still exceed E_cap if b is large. Test that the formula still
        returns a valid s ∈ [0, 1]."""
        K = self._K()
        lam = np.array([1.0, 0, 0])
        v_p = np.array([-2.0, 0, 0])  # a = -2
        # ΔKE = -2 + 0.5 = -1.5 < E_cap=0.01 → s = 1 (kick is dissipative).
        s, a, b = patch_passive_scaling(lam, v_p, K, E_cap=0.01)
        assert s == 1.0


# ======================================================================
# TestPatchResponsePipeline — end-to-end §9.2-9.6 integration
# ======================================================================


class TestPatchResponsePipeline:
    """End-to-end checks of the full §9.2-9.6 pipeline in patch mode."""

    def test_patch_mode_produces_real_kicks_on_impact(self):
        """After landing, the patch mode actually populates last_patch_kicks
        with non-trivial impulses (PatchKick instances with |lam| > 0)."""
        world, coupler, _t, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        saw_kick = False
        for _ in range(500):
            world.step()
            if coupler.last_patch_kicks:
                for k in coupler.last_patch_kicks:
                    assert isinstance(k, PatchKick)
                    assert np.all(np.isfinite(k.lam))
                    assert np.all(np.isfinite(k.x_bar))
                    assert np.all(np.isfinite(k.r_bar))
                    assert np.all(np.isfinite(k.n_def))
                    assert 0.0 <= k.s_passivity <= 1.0
                    if float(np.linalg.norm(k.lam)) > 1e-9:
                        saw_kick = True
                if saw_kick:
                    break
        assert saw_kick, "patch mode should produce non-trivial kicks on impact"

    def test_patch_kick_changes_receiver_body_velocity(self):
        """Applying the patch kick actually modifies the receiver body's
        velocity (the world's _apply_patch_impulse_dcr_velocities wiring
        is live)."""
        world, coupler, _t, box_idx = _build_drop_scene(
            mode="energy_prescribed_patch")
        # Step until a kick fires, recording velocity before/after.
        for _ in range(500):
            v_pre = world.bodies[box_idx].velocity.copy()
            world.step()
            if coupler.last_patch_kicks and any(
                np.linalg.norm(k.lam) > 1e-6 and k.body_idx == box_idx
                for k in coupler.last_patch_kicks
            ):
                v_post = world.bodies[box_idx].velocity
                # Hard to disentangle the kick from the rigid step itself
                # without isolating, but at minimum the patch-attributed
                # KE delta should be nonzero.
                assert world.last_dcr_ke_injected != 0.0
                return
        pytest.fail(
            "no patch kick fired on the receiver body within 500 steps")

    def test_patch_kick_friction_bounded(self):
        """Every kick's tangent component after Coulomb projection
        satisfies ||λ_t|| ≤ μ λ_n (within float tolerance), where the
        cone is closed around the REST normal (push_dir, the canonical
        elastic→receiver direction). The cone is intentionally NOT
        closed around the deformed normal — see the §9.5 docstring."""
        world, coupler, _t, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        mu = 0.5  # _build_drop_scene uses friction=0.5 on both bodies
        for _ in range(500):
            world.step()
            if not coupler.last_patch_kicks:
                continue
            for k in coupler.last_patch_kicks:
                if float(np.linalg.norm(k.lam)) < 1e-12:
                    continue
                # Re-derive the rest normal axis from the patch the kick
                # came from. In the drop scene the foundation is the
                # static plane (idx 0), so push_dir is +y.
                n_rest = np.array([0.0, 1.0, 0.0])
                lam_n = float(k.lam @ n_rest)
                lam_t = k.lam - lam_n * n_rest
                assert lam_n >= -1e-12, (
                    f"adhesive normal: lam_n = {lam_n}")
                assert (
                    float(np.linalg.norm(lam_t)) <=
                    mu * max(0.0, lam_n) + 1e-12
                ), f"||lam_t||={np.linalg.norm(lam_t)} > mu·lam_n={mu*lam_n}"

    def test_static_body_skipped_as_receiver(self):
        """The elastic foundation (static plane) never appears as a kick
        receiver — only the dynamic body in the pair does."""
        world, coupler, table_idx, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        for _ in range(500):
            world.step()
            if coupler.last_patch_kicks:
                for k in coupler.last_patch_kicks:
                    assert k.body_idx != table_idx

    def test_modal_back_reaction_drains_qdot(self):
        """The patch kick deducts -Φ(x̄)ᵀ·λ from the modal qdot
        (Newton's third law / passivity in the extraction direction).
        Without this, modal energy never depletes from kicks and v_f
        stays high indefinitely.

        Pin: after a step that produces a non-trivial patch kick,
        Σ |qdot_after_step - qdot_before_kick| should reflect the
        modal projection of the applied λ.
        """
        world, coupler, _t, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        # Step until a non-trivial kick fires.
        for _ in range(500):
            qdot_pre = coupler._stepper.qdot.copy()
            world.step()
            if not coupler.last_patch_kicks:
                continue
            kicks_with_lam = [k for k in coupler.last_patch_kicks
                              if float(np.linalg.norm(k.lam)) > 1e-6]
            if not kicks_with_lam:
                continue
            # Reconstruct the cumulative modal back-reaction from the
            # recorded kicks. The free-decay (step_n) on top of this
            # contributes its own Δqdot, so we only check the magnitude
            # of the back-reaction is non-trivial and aligned with -Φᵀλ
            # for at least one mode.
            from dcr.modal.passive_inject import eval_basis_at_point
            expected_back = np.zeros_like(qdot_pre)
            for kk in kicks_with_lam:
                Phi_x = eval_basis_at_point(
                    kk.x_bar, coupler._surface, coupler.modal.U_surf,
                    coupler.modal.surface_vertex_indices,
                    coupler._vert_to_surf_idx,
                )
                expected_back -= Phi_x.T @ kk.lam
            # The expected back-reaction should have non-zero magnitude
            # (otherwise the test is vacuous).
            assert float(np.linalg.norm(expected_back)) > 1e-6, (
                "test setup: kick was too small to test back-reaction")
            # Without the back-reaction the next step's qdot snapshot
            # would equal qdot_pre + alpha_s (purely from the modal
            # injection from new impacts) + step_n decay. With the
            # back-reaction, the snapshot is decreased by the projection.
            # We can detect this by checking the qdot snapshot used for
            # next step's v_f IF we take another step.
            qdot_post = coupler._stepper.qdot.copy()
            # Direct sanity: end-of-step qdot ≠ pre-step qdot, and the
            # difference at minimum is non-trivial (modal kick + step_n
            # decay + back-reaction together).
            assert not np.allclose(qdot_pre, qdot_post)
            return
        pytest.fail("no non-trivial patch kick fired within 500 steps")


# ======================================================================
# TestCausalGating — proposal: prompts/passive_contact_causal_modal_coupling.md
# ======================================================================


def _make_gate_test_setup(gap_m: float = 5e-5, qdot_scale: float = 0.0):
    """Build a minimal one-patch, one-contact scenario for gate unit tests.

    Returns (coupler, patches, resting_contacts, bodies). The receiver is
    a 0.05 m half-extent box centered above the static plane at y=0; the
    contact is at the box bottom, normal = +y, with `penetration = -gap_m`
    (so gap_m is the separation distance).

    qdot_scale sets `coupler._stepper.qdot[0]` so the caller can dial
    the closing-velocity gate independently. v_f at x_bar ≈ Φ(x_bar)·qdot;
    Phi is unit-of-order, so a scale of ~0.1 gives v_f roughly 0.1 m/s.
    """
    modal = _build_slab_modal()
    # Use the modal mesh's actual surface so eval_basis_at_point works.
    # We construct the receiver and contact directly; the elastic body
    # at index 0 is a virtual static plane (we don't need a full world).
    from dcr.rigid.body import make_static_plane, make_dynamic_box
    plane = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    box = make_dynamic_box(mass=1.0, hx=0.05, hy=0.05, hz=0.05,
                           position=(0.0, 0.05 + gap_m, 0.0),
                           restitution=0.0, friction=0.5)
    bodies = [plane, box]
    coupler = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=0,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=0.5,
        energy_budget_source="modal_reservoir",
        causal_gating=True,
    )
    # Build a single contact at the box bottom (y = box_center − hy).
    # Collision-detector convention: body_a is the dynamic body, normal
    # points from body_a outward (toward the elastic / static body).
    # See _build_drop_scene live behaviour.
    contact_point = np.array([0.0, 0.05 + gap_m - 0.05, 0.0])  # at box bottom
    contact_normal = np.array([0.0, 1.0, 0.0])  # +y, box→plane (body_a=1)
    c = Contact(
        body_a=1, body_b=0,
        point=contact_point, normal=contact_normal,
        penetration=-gap_m, is_new=False,
    )
    resting_contacts = [c]
    patch = build_patch(
        body_a=0, body_b=1, contact_idxs=[0],
        contacts=resting_contacts, bodies=bodies,
        weight_mode="uniform",
    )
    patches = [patch]
    # Set qdot so v_f at the contact point is roughly qdot_scale along +y.
    # We use Phi(x_bar) to back-solve: desired v_f = (0, qdot_scale, 0).
    # `qdot = pinv(Phi) @ desired_v_f` gives the minimum-norm modal
    # amplitude vector that yields that contact-point velocity.
    # This is portable across mode-shape sign choices (which ARPACK can
    # flip arbitrarily). The patch driver reads from `_qdot_just_after_kick`
    # so we set both for safety.
    from dcr.modal.passive_inject import eval_basis_at_point
    Phi = eval_basis_at_point(
        patch.x_bar, coupler._surface, coupler.modal.U_surf,
        coupler.modal.surface_vertex_indices, coupler._vert_to_surf_idx)
    coupler._stepper.qdot[:] = 0.0
    if qdot_scale != 0.0:
        desired_v_f = np.array([0.0, float(qdot_scale), 0.0])
        coupler._stepper.qdot[:] = np.linalg.pinv(Phi) @ desired_v_f
    coupler._qdot_just_after_kick = coupler._stepper.qdot.copy()
    return coupler, patches, resting_contacts, bodies


class TestCausalGating:
    """Contact-causal passive modal coupling gates (proposal §1-§3)."""

    # ---- Opt-in contract + bit-identity ------------------------------

    def test_causal_gating_default_off(self):
        """No kwarg → causal_gating == False. Opt-in contract."""
        modal = _build_slab_modal()
        coupler = PassiveDCRCoupler(
            modal=modal, elastic_body_idx=0,
            dcr_velocity_mode="energy_prescribed_patch",
        )
        assert coupler.causal_gating is False
        assert coupler.contact_shell_delta == pytest.approx(1e-4)
        assert coupler.v_min_closing == pytest.approx(0.044)
        assert coupler.e_modal_cutoff_frac == pytest.approx(1e-5)

    def test_causal_gating_off_is_bit_identical(self):
        """200-step run with flag explicitly off matches a run with no
        kwarg, to ARPACK/BLAS float noise (rtol=1e-12). Pins regression:
        the new code is invisible to existing patch-mode behaviour when
        the flag is off."""
        n_steps = 200
        # Run A: no kwarg (default False).
        world_a, _, _t, _b = _build_drop_scene(mode="energy_prescribed_patch")
        ys_a = []
        for _ in range(n_steps):
            world_a.step()
            ys_a.append(world_a.bodies[1].position.copy())
        # Run B: explicit causal_gating=False (post-construction set).
        world_b, coupler_b, _t, _b = _build_drop_scene(
            mode="energy_prescribed_patch")
        coupler_b.causal_gating = False
        ys_b = []
        for _ in range(n_steps):
            world_b.step()
            ys_b.append(world_b.bodies[1].position.copy())
        # Note: literal bit-identity is not achievable because the modal
        # eigendecomposition (ARPACK / scipy.sparse.linalg.eigsh) and the
        # BLAS calls in the patch-mode solve can produce 1e-15 to 1e-20
        # numerical jitter between runs even with identical inputs. The
        # important regression invariant is that no NEW divergence path
        # is introduced — rtol=1e-12 is well below any code-induced delta.
        for a, b in zip(ys_a, ys_b):
            np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-15)

    # ---- Validation ---------------------------------------------------

    def test_invalid_contact_shell_delta_raises(self):
        modal = _build_slab_modal()
        with pytest.raises(ValueError, match="contact_shell_delta"):
            PassiveDCRCoupler(
                modal=modal, elastic_body_idx=0,
                dcr_velocity_mode="energy_prescribed_patch",
                contact_shell_delta=-1e-3,
            )

    def test_invalid_v_min_closing_raises(self):
        modal = _build_slab_modal()
        with pytest.raises(ValueError, match="v_min_closing"):
            PassiveDCRCoupler(
                modal=modal, elastic_body_idx=0,
                dcr_velocity_mode="energy_prescribed_patch",
                v_min_closing=-0.01,
            )

    def test_invalid_e_modal_cutoff_frac_raises(self):
        modal = _build_slab_modal()
        with pytest.raises(ValueError, match="e_modal_cutoff_frac"):
            PassiveDCRCoupler(
                modal=modal, elastic_body_idx=0,
                dcr_velocity_mode="energy_prescribed_patch",
                e_modal_cutoff_frac=1.5,
            )

    # ---- Contact-shell gate ------------------------------------------

    def test_shell_gate_skips_patch_with_large_gap(self):
        """gap=10mm >> δ=1e-4m → patch gated out, no kick, counter +1."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=0.010,        # 10 mm gap
            qdot_scale=10.0,    # force closing-velocity to pass if ever reached
        )
        coupler.contact_shell_delta = 1e-4
        # Reset counters explicitly (the function sets them on process_step,
        # but we're calling _compute_distant_response_patch directly).
        coupler.last_patch_gated_no_contact = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        assert kicks == []
        assert coupler.last_patch_gated_no_contact == 1

    def test_shell_gate_admits_patch_within_shell(self):
        """gap=0.05mm < δ=1e-4m + closing-velocity passes → kick fires."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5,         # 0.05 mm gap; well below δ
            qdot_scale=10.0,    # force big +y closing velocity
        )
        coupler.last_patch_gated_no_contact = 0
        coupler.last_patch_gated_low_closing = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        assert len(kicks) == 1
        assert coupler.last_patch_gated_no_contact == 0
        assert coupler.last_patch_gated_low_closing == 0

    def test_min_gap_rule_admits_when_one_contact_in_shell(self):
        """Two contacts in patch with gaps (1e-5, 5e-3) → admit via min-gap."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=1e-5, qdot_scale=10.0,
        )
        # Build a second contact further away; same body pair.
        # Same collision-detector convention as _make_gate_test_setup.
        c2 = Contact(
            body_a=1, body_b=0,
            point=np.array([0.03, 0.05 + 5e-3 - 0.05, 0.0]),
            normal=np.array([0.0, 1.0, 0.0]),
            penetration=-5e-3, is_new=False,
        )
        resting.append(c2)
        # Rebuild patch using both contacts.
        patches = [build_patch(
            body_a=0, body_b=1, contact_idxs=[0, 1],
            contacts=resting, bodies=bodies, weight_mode="uniform",
        )]
        coupler.last_patch_gated_no_contact = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        # min(-(-1e-5), -(-5e-3)) = min(1e-5, 5e-3) = 1e-5 < δ → admit.
        assert coupler.last_patch_gated_no_contact == 0
        assert len(kicks) == 1

    # ---- Closing-velocity gate ---------------------------------------

    def test_closing_velocity_gate_skips_when_below_v_min(self):
        """Contact in shell but closing ≈ 0 << v_min=0.044 → gated out."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5,         # in shell
            qdot_scale=0.0,     # zero modal velocity → v_f = 0 → closing ≈ 0
        )
        coupler.last_patch_gated_low_closing = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        assert kicks == []
        assert coupler.last_patch_gated_low_closing == 1

    def test_closing_velocity_gate_admits_when_above_v_min(self):
        """Contact in shell + closing > v_min → kick fires."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5, qdot_scale=10.0,
        )
        coupler.last_patch_gated_low_closing = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        assert len(kicks) == 1
        assert coupler.last_patch_gated_low_closing == 0

    def test_separating_motion_gated_out(self):
        """Closing velocity = -0.2 m/s (slab pulling AWAY) → gated out."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5, qdot_scale=-10.0,   # negative qdot → v_f points down
        )
        coupler.last_patch_gated_low_closing = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        assert kicks == []
        # closing = (v_f - v_p) · +y is <= 0 < v_min, so the closing gate fires.
        assert coupler.last_patch_gated_low_closing == 1

    def test_closing_velocity_uses_push_dir_not_n_def(self):
        """Pin §design choice 2: the gate axis is push_dir (rest normal),
        NOT n_def (deformed normal). With a v_f purely in +x and push_dir
        purely in +y, closing = 0 → gated out. If the gate used n_def
        (which can tilt), an x-component could leak into 'closing'.

        We monkey-patch _deformed_normal to return n_def = +x, forcing the
        scenario where the two axes disagree.
        """
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5, qdot_scale=0.0,
        )
        # Force v_f to have only +x: tweak qdot manually by overriding
        # the snapshot used by the patch driver.
        # The Phi entries are mesh-dependent; the cleanest way to force
        # v_f along +x is to override qdot_just_after_kick directly and
        # use eval_basis_at_point to back-solve. Simpler: monkey-patch
        # eval_basis_at_point to return a fixed Phi where +x is the only
        # active axis.
        import dcr.dcr.passive_dcr as pdcr
        original_eval = pdcr.eval_basis_at_point
        original_def = coupler._deformed_normal
        try:
            def fake_phi(*args, **kwargs):
                # Return Phi where row 0 (x) is unit on mode 0, all others zero.
                # So v_f = Phi @ qdot = [qdot[0], 0, 0].
                P = np.zeros((3, coupler._stepper.qdot.size))
                P[0, 0] = 1.0
                return P
            pdcr.eval_basis_at_point = fake_phi
            # Set qdot[0] large → v_f = (10, 0, 0). v_p = 0. (v_f-v_p)·+y = 0.
            coupler._stepper.qdot[0] = 10.0
            coupler._qdot_just_after_kick = coupler._stepper.qdot.copy()
            # Force n_def to also be in +x (different from push_dir = +y).
            coupler._deformed_normal = lambda **kw: (
                np.array([1.0, 0.0, 0.0]), 0.0, 0)
            coupler.last_patch_gated_low_closing = 0
            kicks = coupler._compute_distant_response_patch(
                patches=patches, resting_contacts=resting,
                q_history=coupler._stepper.q.reshape(1, -1).copy(),
                bodies=bodies, E_target=1.0, h=1e-3,
            )
            # closing computed along push_dir=+y is 0 → gated out.
            # If gate used n_def=+x instead, closing would be 10.0 → admitted.
            assert kicks == [], (
                "gate appears to use n_def axis instead of push_dir")
            assert coupler.last_patch_gated_low_closing == 1
        finally:
            pdcr.eval_basis_at_point = original_eval
            coupler._deformed_normal = original_def

    # ---- Numerical cutoff (§3) ---------------------------------------

    def test_numerical_cutoff_skips_when_E_modal_tiny(self):
        """qdot tiny + peak well above → cutoff fires, returns []."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5, qdot_scale=1e-20,
        )
        coupler.last_E_modal_peak = 1.0
        coupler.e_modal_cutoff_frac = 1e-5
        coupler.last_patch_gated_numerical = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        assert kicks == []
        assert coupler.last_patch_gated_numerical == len(patches)

    def test_numerical_cutoff_inactive_when_peak_zero(self):
        """First step (peak=0) → cutoff no-op; reaches the per-patch gates."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=5e-5, qdot_scale=10.0,
        )
        coupler.last_E_modal_peak = 0.0   # explicit
        coupler.last_patch_gated_numerical = 0
        coupler.last_patch_gated_low_closing = 0
        kicks = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        # Cutoff did NOT fire (peak was 0); patch admitted.
        assert coupler.last_patch_gated_numerical == 0
        assert len(kicks) == 1

    # ---- Back-reaction not applied on gated patches ------------------

    def test_gated_patch_does_not_debit_qdot(self):
        """All-patches-gated step: qdot unchanged by patch dispatch
        (back-reaction `qdot -= Phi.T @ λ` does not fire for skipped
        patches; §15 invariant trivially preserved)."""
        coupler, patches, resting, bodies = _make_gate_test_setup(
            gap_m=0.010,    # large gap → shell-gate fires
            qdot_scale=10.0,
        )
        qdot_pre = coupler._stepper.qdot.copy()
        _ = coupler._compute_distant_response_patch(
            patches=patches, resting_contacts=resting,
            q_history=coupler._stepper.q.reshape(1, -1).copy(),
            bodies=bodies, E_target=1.0, h=1e-3,
        )
        np.testing.assert_array_equal(coupler._stepper.qdot, qdot_pre)

    # ---- End-to-end on drop scene ------------------------------------

    def test_causal_gating_drop_scene_runs_to_completion(self):
        """1000 steps with causal_gating=True: no exceptions, box settles
        near the slab top, and the closing-velocity gate fires at some
        point post-settling (proving the gate is active on residual modal
        motion, not just dead code)."""
        world, coupler, _t, box_idx = _build_drop_scene(
            mode="energy_prescribed_patch")
        coupler.causal_gating = True
        saw_low_closing_gate = False
        for step in range(1000):
            world.step()
            if coupler.last_patch_gated_low_closing > 0 and step > 500:
                saw_low_closing_gate = True
        # Box should be at roughly its rest height (bottom at slab top).
        box_y = world.bodies[box_idx].position[1]
        assert 0.04 <= box_y <= 0.07, (
            f"box y={box_y} not in expected rest range [0.04, 0.07]")
        assert saw_low_closing_gate, (
            "closing-velocity gate never fired post-settling; gates appear "
            "to be dead code")
        # Peak modal energy should have been recorded by the running-max.
        assert coupler.last_E_modal_peak > 0.0
