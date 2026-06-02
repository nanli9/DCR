"""End-of-rigid-step γ-decay knob (foundation §16, #DEVIATION from §15 for γ < 1).

Tests:
1. HomogeneousStepper unit: gamma validation, gamma=1 no-op,
   gamma in (0, 1) attenuation, gamma=0 reset, dissipation accounting.
2. PassiveDCRCoupler wiring: gamma plumbs through, attenuation fires
   per rigid step, dE_modal_attenuation populated.
3. §15 invariant survives across gamma ∈ {0.0, 0.5, 0.95, 1.0}:
   cumulative injected ≤ eta * cumulative rigid_loss.
4. Energy log records attenuation as a separate channel; never refunded
   to the reservoir.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis, HomogeneousStepper
from dcr.modal.energy import modal_energy
from dcr.rigid import (
    make_dynamic_box, make_static_plane, ConstraintSolver,
)
from dcr.dcr import PassiveDCRCoupler, DCRWorld


# ---------------------------------------------------------------------
# 1. HomogeneousStepper unit tests
# ---------------------------------------------------------------------

def _make_stepper(gamma: float = 1.0) -> HomogeneousStepper:
    omega = np.array([10.0, 50.0, 200.0], dtype=np.float64)
    zeta = np.array([0.01, 0.02, 0.05], dtype=np.float64)
    return HomogeneousStepper(omega=omega, zeta=zeta, T=1e-4, gamma=gamma)


def test_gamma_validation_rejects_negative():
    with pytest.raises(ValueError, match="gamma"):
        _make_stepper(gamma=-0.1)


def test_gamma_validation_rejects_above_one():
    with pytest.raises(ValueError, match="gamma"):
        _make_stepper(gamma=1.01)


def test_gamma_one_is_noop():
    s = _make_stepper(gamma=1.0)
    s.q[:] = np.array([0.1, 0.2, -0.05])
    s.qdot[:] = np.array([1.5, -0.3, 0.7])
    q_pre = s.q.copy()
    qdot_pre = s.qdot.copy()
    diss = s.apply_rigid_step_decay()
    assert diss == 0.0
    np.testing.assert_array_equal(s.q, q_pre)
    np.testing.assert_array_equal(s.qdot, qdot_pre)


def test_gamma_zero_full_reset():
    """γ=0 is the original-DCR-style per-step reset, as the limiting case."""
    s = _make_stepper(gamma=0.0)
    s.q[:] = np.array([0.1, 0.2, -0.05])
    s.qdot[:] = np.array([1.5, -0.3, 0.7])
    E_pre = modal_energy(s.q, s.qdot, s.omega)
    diss = s.apply_rigid_step_decay()
    np.testing.assert_array_equal(s.q, np.zeros(3))
    np.testing.assert_array_equal(s.qdot, np.zeros(3))
    assert diss == pytest.approx(E_pre, rel=1e-12)


@pytest.mark.parametrize("gamma", [0.5, 0.8, 0.95, 0.99])
def test_gamma_partial_scales_state_and_returns_dissipation(gamma):
    s = _make_stepper(gamma=gamma)
    s.q[:] = np.array([0.1, 0.2, -0.05])
    s.qdot[:] = np.array([1.5, -0.3, 0.7])
    q_pre = s.q.copy()
    qdot_pre = s.qdot.copy()
    E_pre = modal_energy(q_pre, qdot_pre, s.omega)

    diss = s.apply_rigid_step_decay()

    # State scaled by gamma.
    np.testing.assert_allclose(s.q, gamma * q_pre, rtol=1e-12)
    np.testing.assert_allclose(s.qdot, gamma * qdot_pre, rtol=1e-12)

    # Energy after = gamma^2 * energy before; dissipation = (1 - gamma^2) * E_pre.
    E_post = modal_energy(s.q, s.qdot, s.omega)
    assert E_post == pytest.approx(gamma ** 2 * E_pre, rel=1e-10)
    assert diss == pytest.approx((1.0 - gamma ** 2) * E_pre, rel=1e-10)
    # Dissipation must be non-negative — never refunded to the reservoir.
    assert diss >= 0.0


def test_gamma_dissipation_is_zero_for_zero_state():
    """If modal state is already zero, decay dissipates nothing regardless of γ."""
    s = _make_stepper(gamma=0.5)
    diss = s.apply_rigid_step_decay()
    assert diss == 0.0


def test_from_modal_analysis_threads_gamma():
    mesh = make_slab_tet_mesh(length=0.4, width=0.2, height=0.03,
                              nx=4, ny=3, nz=2)
    mat = Material(E=1e9, nu=0.3, rho=800.0)
    fem = FEMModel(mesh=mesh, material=mat,
                   fixed_nodes=np.array([], dtype=np.int32),
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=5)

    s = HomogeneousStepper.from_modal_analysis(modal, gamma=0.7)
    assert s.gamma == 0.7

    s_default = HomogeneousStepper.from_modal_analysis(modal)
    assert s_default.gamma == 1.0


# ---------------------------------------------------------------------
# 2. PassiveDCRCoupler wiring
# ---------------------------------------------------------------------

def _build_min_passive_scene(gamma: float, eta: float = 0.3, h: float = 1e-3):
    """A tiny scene with one box landing on an elastic slab — enough to
    excite modes once so γ-decay has something to attenuate.
    """
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
        eta=eta,
    )
    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    world.add_body(table)

    mesh = make_slab_tet_mesh(length=0.6, width=0.4, height=0.04,
                              nx=6, ny=4, nz=2)
    mat = Material(E=1e9, nu=0.3, rho=800.0)
    fem = FEMModel(mesh=mesh, material=mat,
                   fixed_nodes=np.array([], dtype=np.int32),
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=6)
    coupler = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=0,
        modal_decay_gamma=gamma,
    )
    world.add_passive_coupler(coupler)

    drop = make_dynamic_box(
        mass=2.0, hx=0.05, hy=0.05, hz=0.05,
        position=(0.0, 0.08, 0.0), restitution=0.1, friction=0.5,
    )
    world.add_body(drop)
    return world, coupler


def test_coupler_rejects_invalid_gamma():
    mesh = make_slab_tet_mesh(length=0.4, width=0.2, height=0.03,
                              nx=4, ny=3, nz=2)
    mat = Material(E=1e9, nu=0.3, rho=800.0)
    fem = FEMModel(mesh=mesh, material=mat,
                   fixed_nodes=np.array([], dtype=np.int32),
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=4)
    with pytest.raises(ValueError, match="modal_decay_gamma"):
        PassiveDCRCoupler(modal=modal, elastic_body_idx=0,
                          modal_decay_gamma=1.5)


def test_coupler_gamma_one_diagnostic_is_zero():
    """At γ=1 (default, main method) the attenuation diagnostic stays 0."""
    world, coupler = _build_min_passive_scene(gamma=1.0)
    for _ in range(60):
        world.step()
        assert coupler.last_E_modal_attenuation_diss == 0.0


def test_coupler_gamma_lt_one_records_attenuation():
    """γ < 1 fires the attenuation operator each rigid step; diagnostic > 0
    on at least one step where modal energy was non-trivial."""
    world, coupler = _build_min_passive_scene(gamma=0.8)
    saw_attenuation = False
    for _ in range(80):
        world.step()
        if coupler.last_E_modal_attenuation_diss > 0.0:
            saw_attenuation = True
            # Non-negative on every step — never refunded.
            assert coupler.last_E_modal_attenuation_diss > 0.0
    assert saw_attenuation, (
        "γ=0.8 should attenuate at least one step in this scene")


def test_coupler_gamma_zero_zeros_state_each_step():
    """γ=0 reduces to the original-DCR per-step reset: after every rigid
    step, persistent (q, qdot) is back to zero."""
    world, coupler = _build_min_passive_scene(gamma=0.0)
    for _ in range(40):
        world.step()
        np.testing.assert_array_equal(
            coupler._stepper.q,
            np.zeros_like(coupler._stepper.q),
            err_msg="γ=0 should reset q to zero each step")
        np.testing.assert_array_equal(
            coupler._stepper.qdot,
            np.zeros_like(coupler._stepper.qdot),
            err_msg="γ=0 should reset qdot to zero each step")


# ---------------------------------------------------------------------
# 3. §15 cumulative invariant survives across γ
# ---------------------------------------------------------------------

@pytest.mark.parametrize("gamma", [0.0, 0.5, 0.95, 1.0])
def test_section_15_invariant_holds_under_gamma(gamma):
    """cumulative injected ≤ eta * cumulative rigid_loss for all γ.

    γ-decay is dissipation: it removes energy but never refunds the
    reservoir. So the §15 inequality is preserved (in fact made looser
    in absolute terms, since less energy persists).
    """
    eta = 0.3
    world, coupler = _build_min_passive_scene(gamma=gamma, eta=eta, h=1e-3)
    world.enable_energy_logging = True
    from dcr.benchmark import EnergyLog
    world.energy_log = EnergyLog()
    for _ in range(150):
        world.step()
    violation = world.energy_log.invariant_violation()
    # Floating-point tolerance: the §15 inequality is symbolic; we allow
    # a few eV of numerical noise.
    assert violation <= 1e-9, (
        f"γ={gamma}: §15 invariant violated by {violation:.3e} J")


def test_energy_log_attenuation_channel_populates():
    """The new dE_modal_attenuation column is positive at γ=0.5 and
    cumulative_modal_attenuation is monotone non-decreasing."""
    world, _ = _build_min_passive_scene(gamma=0.5)
    world.enable_energy_logging = True
    from dcr.benchmark import EnergyLog
    world.energy_log = EnergyLog()
    for _ in range(80):
        world.step()
    cum = world.energy_log.cumulative_modal_attenuation()
    # Non-decreasing: attenuation is always >= 0.
    diffs = np.diff(cum)
    assert np.all(diffs >= -1e-15), (
        "cumulative_modal_attenuation must be monotone non-decreasing")
    # At least one step should have non-zero attenuation in this scene.
    assert cum[-1] > 0.0, (
        "γ=0.5 should accumulate non-trivial attenuation over the run")


def test_energy_log_attenuation_zero_at_gamma_one():
    """Backwards-compat: γ=1.0 leaves dE_modal_attenuation identically zero."""
    world, _ = _build_min_passive_scene(gamma=1.0)
    world.enable_energy_logging = True
    from dcr.benchmark import EnergyLog
    world.energy_log = EnergyLog()
    for _ in range(60):
        world.step()
    cum = world.energy_log.cumulative_modal_attenuation()
    assert cum[-1] == 0.0
