"""Stage E4 acceptance tests — multi-contact aggregation + monotone dissipation.

E4 criteria (passive_energy_injection_implementation_prompt.md):
1. Multi-contact: aggregate (single alpha) stays under E_loss budget;
   per-contact-bounded (sequential alphas) can exceed it.
2. Monotone dissipation: E_modal(t_{k+1}) <= E_modal(t_k) after last impact,
   asserted at every modal sub-step.
3. Unit test: monotone non-increasing at sub-step granularity.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy
from dcr.modal.passive_inject import (
    eval_basis_at_point, project_impulse, aggregate_kicks, passive_alpha,
)
from dcr.modal.homogeneous_stepper import HomogeneousStepper
from dcr.rigid import (
    make_dynamic_box, make_static_plane,
    ConstraintSolver,
)
from dcr.dcr import PassiveDCRCoupler, DCRWorld


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_slab_modal():
    """Build a small elastic slab with modal analysis (shared by E4 tests)."""
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    tol = 1e-8
    x_min, x_max = mesh.vertices[:, 0].min(), mesh.vertices[:, 0].max()
    z_min, z_max = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    on_xmin = np.abs(mesh.vertices[:, 0] - x_min) < tol
    on_xmax = np.abs(mesh.vertices[:, 0] - x_max) < tol
    on_zmin = np.abs(mesh.vertices[:, 2] - z_min) < tol
    on_zmax = np.abs(mesh.vertices[:, 2] - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)

    fem_model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                         alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem_model, num_modes=10)
    return modal


def _build_two_ball_scene(h: float = 1e-3, eta: float = 1.0):
    """Two balls dropped simultaneously onto an elastic slab.

    Ball A hits near (-0.3, 0, 0), Ball B hits near (0.3, 0, 0).
    """
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=eta,
    )

    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)

    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    # Two balls dropped from the same height
    ball_a = make_dynamic_box(
        mass=1.0, hx=0.04, hy=0.04, hz=0.04,
        position=(-0.3, 0.5, 0.0), restitution=0.1, friction=0.5,
    )
    ball_b = make_dynamic_box(
        mass=1.0, hx=0.04, hy=0.04, hz=0.04,
        position=(0.3, 0.5, 0.0), restitution=0.1, friction=0.5,
    )
    idx_a = world.add_body(ball_a)
    idx_b = world.add_body(ball_b)

    return world, coupler, idx_a, idx_b


def _simulate_per_contact_bounded(modal, impulses, contact_points, E_max):
    """Incorrect per-contact-bounded injection: each contact gets its own alpha with full E_max.

    This can exceed the budget because m contacts each get E_max, allowing up to m*E_max total.
    Foundation §8 explains why this is wrong.
    """
    stepper = HomogeneousStepper.from_modal_analysis(modal)
    surface = modal.fem.mesh.extract_surface()
    max_vert = modal.fem.mesh.num_vertices
    vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
    for si, vi in enumerate(modal.surface_vertex_indices):
        vert_to_surf_idx[vi] = si

    omega = modal.frequencies
    total_injected = 0.0

    for j_world, point in zip(impulses, contact_points):
        Phi_x = eval_basis_at_point(
            point, surface, modal.U_surf,
            modal.surface_vertex_indices, vert_to_surf_idx,
        )
        s_c = project_impulse(Phi_x, j_world)

        E_pre = modal_energy(stepper.q, stepper.qdot, omega)
        alpha = passive_alpha(s_c, stepper.qdot, E_max)  # each gets full budget
        stepper.qdot += alpha * s_c
        E_post = modal_energy(stepper.q, stepper.qdot, omega)
        total_injected += E_post - E_pre

    return total_injected


def _simulate_aggregate(modal, impulses, contact_points, E_max):
    """Correct aggregate injection: single alpha for s_total (foundation §8)."""
    stepper = HomogeneousStepper.from_modal_analysis(modal)
    surface = modal.fem.mesh.extract_surface()
    max_vert = modal.fem.mesh.num_vertices
    vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
    for si, vi in enumerate(modal.surface_vertex_indices):
        vert_to_surf_idx[vi] = si

    omega = modal.frequencies

    kicks = []
    for j_world, point in zip(impulses, contact_points):
        Phi_x = eval_basis_at_point(
            point, surface, modal.U_surf,
            modal.surface_vertex_indices, vert_to_surf_idx,
        )
        s_c = project_impulse(Phi_x, j_world)
        kicks.append(s_c)

    s_total = aggregate_kicks(kicks)

    E_pre = modal_energy(stepper.q, stepper.qdot, omega)
    alpha = passive_alpha(s_total, stepper.qdot, E_max)
    stepper.qdot += alpha * s_total
    E_post = modal_energy(stepper.q, stepper.qdot, omega)

    return E_post - E_pre


# ---------------------------------------------------------------------------
# E4.1: Multi-contact aggregation
# ---------------------------------------------------------------------------

def test_aggregate_vs_per_contact_energy_bound():
    """E4.1: Aggregate (single alpha) stays under E_max; per-contact can exceed it.

    Two synthetic impulses at different surface points, same E_max budget.
    The per-contact path applies two sequential bounded kicks each with full E_max,
    allowing up to 2*E_max total. The aggregate path uses one alpha for s_total,
    guaranteeing <= E_max (foundation §8).
    """
    modal = _build_slab_modal()

    # Two strong impulses at different surface points
    point_a = np.array([-0.3, 0.025, 0.0])
    point_b = np.array([0.3, 0.025, 0.0])
    j_a = np.array([0.0, 50.0, 0.0])  # strong upward impulse
    j_b = np.array([0.0, 50.0, 0.0])

    impulses = [j_a, j_b]
    contact_points = [point_a, point_b]

    # Small energy budget to make the cap active
    E_max = 0.1

    injected_per_contact = _simulate_per_contact_bounded(
        modal, impulses, contact_points, E_max)
    injected_aggregate = _simulate_aggregate(
        modal, impulses, contact_points, E_max)

    print(f"  Per-contact injected: {injected_per_contact:.6e}")
    print(f"  Aggregate injected:   {injected_aggregate:.6e}")
    print(f"  E_max budget:         {E_max:.6e}")

    # Aggregate must stay under budget
    assert injected_aggregate <= E_max + 1e-12, (
        f"Aggregate exceeded budget: {injected_aggregate:.6e} > {E_max:.6e}")

    # Per-contact CAN exceed budget (by up to factor of m=2)
    # This isn't guaranteed for all inputs, but with these strong co-directional
    # impulses it should happen.
    assert injected_per_contact > E_max * 0.99, (
        f"Per-contact should exceed or saturate budget: {injected_per_contact:.6e}")

    print(f"  Per-contact / E_max ratio: {injected_per_contact / E_max:.2f}x")


def test_aggregate_bound_holds_in_full_sim():
    """E4.1 (integration): run the two-ball scene and verify cumulative bound."""
    world, coupler, idx_a, idx_b = _build_two_ball_scene(eta=1.0)
    omega = coupler.modal.frequencies

    cumulative_injected = 0.0
    cumulative_loss = 0.0

    for step_i in range(500):
        world.step()
        dE = coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick
        cumulative_injected += dE
        cumulative_loss += world.last_E_loss

        assert cumulative_injected <= cumulative_loss + 1e-9, (
            f"Step {step_i}: cumulative injected {cumulative_injected:.6e} > "
            f"cumulative loss {cumulative_loss:.6e}")

    print(f"  Two-ball sim: cumulative injected = {cumulative_injected:.6e}")
    print(f"  Two-ball sim: cumulative loss = {cumulative_loss:.6e}")


# ---------------------------------------------------------------------------
# E4.2: Monotone dissipation
# ---------------------------------------------------------------------------

def test_monotone_dissipation_sub_step():
    """E4.2: After last impact, E_modal is monotonically non-increasing at sub-step level.

    One ball hits slab and bounces clear. After impact, no further contact
    impulses enter the modal system. With positive Rayleigh damping,
    E_modal(t_{k+1}) <= E_modal(t_k) for all sub-steps k after the last contact.
    Foundation §3, §9.
    """
    world = DCRWorld(
        h=1e-3,
        solver=ConstraintSolver(h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=1.0,
    )

    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)

    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    # Single ball, high enough to generate a good impact, low restitution
    ball = make_dynamic_box(
        mass=2.0, hx=0.05, hy=0.05, hz=0.05,
        position=(0.0, 0.3, 0.0), restitution=0.8, friction=0.3,
    )
    world.add_body(ball)

    # Run until ball hits and bounces clear (detect by ball being above table
    # with upward velocity and no contact for several steps)
    omega = coupler.modal.frequencies
    had_contact = False
    no_contact_steps = 0
    impact_done = False
    post_impact_step = 0

    # Phase 1: run until ball bounces clear (no contact for 50 steps)
    for step_i in range(2000):
        contacts = world.step()
        has_elastic_contact = any(
            c.body_a == table_idx or c.body_b == table_idx
            for c in contacts
            if not (c.body_a == table_idx and c.body_b == table_idx)
        )

        if has_elastic_contact:
            had_contact = True
            no_contact_steps = 0
        elif had_contact:
            no_contact_steps += 1
            if no_contact_steps >= 50:
                impact_done = True
                post_impact_step = step_i
                break

    assert impact_done, "Ball never bounced clear of table"
    assert modal_energy(coupler._stepper.q, coupler._stepper.qdot, omega) > 1e-10, \
        "Modal energy should be nonzero after impact"

    # Phase 2: no more contacts. Step the modal state and check monotonicity
    # at the sub-step level.
    stepper = coupler._stepper
    n_substeps_per_rigid = max(1, int(np.ceil(world.h / stepper.T)))

    E_prev = modal_energy(stepper.q, stepper.qdot, omega)
    violations = []

    for rigid_step in range(500):
        # Step modal state (no kick — no contacts)
        for sub in range(n_substeps_per_rigid):
            stepper.step()
            E_curr = modal_energy(stepper.q, stepper.qdot, omega)
            if E_curr > E_prev + 1e-12:
                violations.append(
                    (rigid_step, sub, E_prev, E_curr, E_curr - E_prev))
            E_prev = E_curr

    E_final = modal_energy(stepper.q, stepper.qdot, omega)
    print(f"  Post-impact E_modal start: {E_prev:.6e}")
    print(f"  Post-impact E_modal final: {E_final:.6e}")
    print(f"  Sub-step violations: {len(violations)}")

    assert len(violations) == 0, (
        f"Monotone dissipation violated at {len(violations)} sub-steps. "
        f"Worst: dE = {max(v[4] for v in violations):.2e}")


def test_monotone_dissipation_direct():
    """E4.2 (unit): Direct stepper test — E_modal decreases every sub-step.

    Initialize stepper with known state, step without kicks, verify monotonicity.
    """
    modal = _build_slab_modal()
    stepper = HomogeneousStepper.from_modal_analysis(modal)
    omega = modal.frequencies

    # Seed with a known kick
    rng = np.random.default_rng(42)
    stepper.qdot = rng.standard_normal(modal.num_modes) * 10.0

    E_start = modal_energy(stepper.q, stepper.qdot, omega)
    assert E_start > 0.0
    E_prev = E_start

    for k in range(10000):
        stepper.step()
        E_curr = modal_energy(stepper.q, stepper.qdot, omega)
        assert E_curr <= E_prev + 1e-12, (
            f"Sub-step {k}: E increased from {E_prev:.6e} to {E_curr:.6e}")
        E_prev = E_curr

    E_final = modal_energy(stepper.q, stepper.qdot, omega)
    print(f"  Direct test: E_start = {E_start:.6e}, E_final = {E_final:.6e}")
    print(f"  Decay ratio: {E_final / E_start:.6f}")
    assert E_final < E_start, "Energy should have decayed"
