"""Stage E6 acceptance tests — modal sound energy bound (log-only).

E6 criteria:
1. E_sound ≤ E_diss ≤ E_modal_total throughout the dinner scene run.
2. Per-mode dissipation via P_diss matches the robust cross-check
   (E_modal_before - E_modal_after).
3. Cumulative ordering holds pointwise.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy
from dcr.modal.homogeneous_stepper import HomogeneousStepper
from dcr.rigid import (
    make_dynamic_box, make_static_plane, ConstraintSolver,
)
from dcr.dcr import PassiveDCRCoupler, DCRWorld


def _build_slab_modal():
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
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    return ModalAnalysis(fem=fem, num_modes=10)


def test_dissipation_cross_check():
    """E6.1: P_diss sum matches E_modal_before - E_modal_after."""
    modal = _build_slab_modal()
    stepper = HomogeneousStepper.from_modal_analysis(modal)
    omega = modal.frequencies

    # Seed with energy
    rng = np.random.default_rng(42)
    stepper.qdot = rng.standard_normal(modal.num_modes) * 10.0

    E_before = modal_energy(stepper.q, stepper.qdot, omega)
    E_diss_per_mode = stepper.step_n_with_dissipation(1000)
    E_after = modal_energy(stepper.q, stepper.qdot, omega)

    E_diss_sum = float(np.sum(E_diss_per_mode))
    E_diss_robust = max(0.0, E_before - E_after)

    print(f"  E_before = {E_before:.6f}")
    print(f"  E_after = {E_after:.6f}")
    print(f"  E_diss (P_diss sum) = {E_diss_sum:.6f}")
    print(f"  E_diss (robust) = {E_diss_robust:.6f}")
    print(f"  Relative error = {abs(E_diss_sum - E_diss_robust) / E_diss_robust:.2e}")

    # They should match closely (not exactly due to discretization).
    assert abs(E_diss_sum - E_diss_robust) / max(E_diss_robust, 1e-12) < 0.05, (
        f"Dissipation mismatch: sum={E_diss_sum:.6f}, robust={E_diss_robust:.6f}")


def test_sound_bound_ordering():
    """E6.2-3: E_sound ≤ E_diss ≤ E_modal_total throughout dinner scene."""
    h = 1e-3
    world = DCRWorld(
        h=h, eta=1.0,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    table = make_static_plane(normal=(0, 1, 0), point=(0, 0.025, 0), friction=0.5)
    table_idx = world.add_body(table)

    modal = _build_slab_modal()
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    # Plates + pot
    for pos in [(-0.3, 0.046, 0.15), (0.3, 0.046, -0.1), (0.0, 0.046, -0.2)]:
        plate = make_dynamic_box(0.2, 0.06, 0.02, 0.06,
                                 position=pos, restitution=0.0, friction=0.5)
        world.add_body(plate)
    pot = make_dynamic_box(5.0, 0.08, 0.08, 0.08,
                           position=(0.0, 0.925, 0.0),
                           restitution=0.1, friction=0.5)
    pot_idx = world.add_body(pot)

    # Settle
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for b in world.bodies:
        if not b.is_static:
            b.velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = True

    omega = coupler.modal.frequencies
    rho = np.full(modal.num_modes, 0.1)  # acoustic radiation coefficient

    cum_E_diss = 0.0
    cum_E_sound = 0.0
    cum_E_injected = 0.0

    for step_i in range(500):
        contacts = world.step()

        # Only accumulate when the coupler was actually invoked this step.
        coupler_active = len(contacts) > 0 and world.dcr_enabled
        if coupler_active:
            dE = coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick
            cum_E_diss += coupler.last_E_diss_robust
            E_diss_modes = coupler.last_E_diss_per_mode
            if len(E_diss_modes) > 0:
                cum_E_sound += float(np.sum(rho * E_diss_modes))
        else:
            dE = 0.0
        cum_E_injected += dE

        # E6.3: ordering must hold pointwise
        assert cum_E_sound <= cum_E_diss + 1e-9, (
            f"Step {step_i}: E_sound {cum_E_sound:.6e} > E_diss {cum_E_diss:.6e}")

    print(f"  cum E_injected = {cum_E_injected:.4f} J")
    print(f"  cum E_diss = {cum_E_diss:.4f} J")
    print(f"  cum E_sound = {cum_E_sound:.4f} J")
    print(f"  E_sound / E_diss = {cum_E_sound / max(cum_E_diss, 1e-12):.4f}")

    # With ρ=0.1 for all modes, E_sound should be ~0.1 * E_diss
    assert cum_E_sound > 0, "E_sound should be positive after impacts"
    assert cum_E_diss > 0, "E_diss should be positive after impacts"
    assert cum_E_sound <= cum_E_diss + 1e-9, "E_sound must ≤ E_diss"
    # E_diss (robust) should be ≤ net injected (conservation)
    assert cum_E_diss <= cum_E_injected + 1e-6, (
        f"E_diss {cum_E_diss:.6f} > E_injected {cum_E_injected:.6f}")
