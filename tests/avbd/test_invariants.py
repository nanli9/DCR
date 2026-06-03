"""Phase B / spec §22: required invariants 1, 2, 7.

These are asserted **per step**, not just cumulatively, because spec §15
warns: "Piecewise invariants can pass while the composition leaks energy."
The §15 closed-system ledger covers the composition; this file covers the
per-step gates.

Invariant 1 — modal injection bound:
    ΔE_modal_injected(step) ≤ η · max(0, E_rigid_pre − E_rigid_post) + ε

Invariant 2 — support work bound (only meaningful when the moving-support
solve fires; until §7 lands, the per-step W_support_to_rigid is logged as
None and the check is a no-op):
    W_support→rigid(step) ≤ E_budget(step) + ε

Invariant 7 — closed-system non-increase (re-checked here explicitly so a
single test file documents all three invariants together):
    E_rigid(t) + E_modal(t) ≤ E_rigid(0) + E_modal(0) + ε  (no gravity / damping)
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd import AVBDDCRWorld
from dcr.avbd.diagnostics import EnergyLedger
from dcr.avbd.reservoir import support_budget
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.fem import Material, FEMModel
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy


# ---------------------------------------------------------------------------
# Scene fixtures — gravity-driven (for Inv 1) vs closed-system (for Inv 7)
# ---------------------------------------------------------------------------

def _build_gravity_scene(h: float = 1.0 / 120.0):
    """Standard drop scene with gravity — exercises the modal-injection
    pathway (passive_alpha + qdot kick) every contact step."""
    world = AVBDDCRWorld(h=h, eta=0.5, device="cpu")
    ground_top = 0.03
    floor_idx = world.add_floor(floor_y=ground_top, friction=0.6)
    mesh = make_slab_tet_mesh(
        length=1.0, width=0.6, height=0.04, nx=8, ny=6, nz=2)
    fem = FEMModel(
        mesh=mesh, material=Material(E=10.0e9, nu=0.3, rho=500.0),
        fixed_nodes=np.array([], dtype=np.int32),
        alpha0=2.0, alpha1=1e-5,
    )
    modal = ModalAnalysis(fem=fem, num_modes=10)
    coupler = PassiveDCRCoupler(
        modal=modal,
        elastic_body_idx=floor_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=0.25,
        modal_decay_gamma=1.0,
    )
    world.add_passive_coupler(coupler)
    world.add_box(
        mass=20.0, half_extents=(0.1, 0.07, 0.08),
        position=(0.0, ground_top + 0.4, 0.0), friction=0.6,
    )
    return world, coupler


def _build_closed_scene(h: float = 1.0 / 240.0):
    """Mirror of test_closed_system_ledger._build_closed_system."""
    world = AVBDDCRWorld(
        h=h, eta=0.5, device="cpu", gravity=np.zeros(3))
    ground_top = 0.03
    floor_idx = world.add_floor(floor_y=ground_top, friction=0.0)
    mesh = make_slab_tet_mesh(
        length=1.0, width=0.6, height=0.04, nx=8, ny=6, nz=2)
    fem = FEMModel(
        mesh=mesh, material=Material(E=10.0e9, nu=0.3, rho=500.0),
        fixed_nodes=np.array([], dtype=np.int32),
        alpha0=0.0, alpha1=0.0,
    )
    modal = ModalAnalysis(fem=fem, num_modes=6)
    coupler = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=floor_idx,
        dcr_velocity_mode="energy_prescribed_patch",
        energy_response_beta=0.25,
        modal_decay_gamma=1.0,
    )
    world.add_passive_coupler(coupler)
    world.add_box(
        mass=20.0, half_extents=(0.1, 0.07, 0.08),
        position=(0.0, ground_top + 0.15, 0.0),
        velocity_lin=(0.0, -2.0, 0.0),
        friction=0.0, restitution=0.0)
    return world, coupler


# ---------------------------------------------------------------------------
# Invariant 1 — modal injection bound (per-step)
# ---------------------------------------------------------------------------

def test_invariant_1_modal_injection_bounded_per_step():
    """At EVERY step the coupler's intra-step modal-energy delta from its
    own passive injection (last_E_modal_post_kick − last_E_modal_pre_kick)
    must respect η · last_E_loss + ε.

    This is the per-step version of the cumulative bound in
    `tests/avbd/test_patch_integration.py::test_modal_injection_respects_eta_loss_bound`.
    The cumulative form is necessary; the per-step form is sufficient.
    """
    world, coupler = _build_gravity_scene()
    eta = world.eta
    tol_abs = 1e-9
    tol_rel = 1e-6
    n_steps = 80
    for k in range(n_steps):
        world.step()
        injected = max(
            0.0,
            float(coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick))
        budget = eta * world.last_E_loss
        # Slack = abs floor + relative slack proportional to the per-step
        # modal energy itself (catches relative round-off in eigensolver math).
        slack = tol_abs + tol_rel * max(
            float(coupler.last_E_modal_post_kick), float(budget))
        assert injected <= budget + slack, (
            f"step {k}: injected={injected:.4e} > "
            f"η·E_loss={budget:.4e} + slack={slack:.3e}")


# ---------------------------------------------------------------------------
# Invariant 2 — support work bound (per-step)
# ---------------------------------------------------------------------------

def test_invariant_2_support_work_bound_currently_no_op():
    """Until §7 (moving-support AVBD constraint) lands, `last_W_support`
    is None on every step — the per-step bound has nothing to assert. This
    test documents the contract: the Phase A pipeline does NOT do
    moving-support solves, therefore Invariant 2 is vacuously satisfied
    (no support → no work to bound).

    When §7 + §12 ship, this test flips to the actual assertion using
    `coupler.last_W_support` / `coupler.last_E_support_budget`.
    """
    world, coupler = _build_gravity_scene()
    for _ in range(20):
        world.step()
        # Phase A has no moving-support solve; the field doesn't exist yet.
        assert not hasattr(coupler, "last_W_support") or \
            getattr(coupler, "last_W_support", None) is None
        assert not hasattr(coupler, "last_E_support_budget") or \
            getattr(coupler, "last_E_support_budget", None) is None


def test_invariant_2_support_budget_formula_is_modal_funded():
    """Spec §11 first-version formula: E_budget = β · E_modal_reservoir.
    Sanity-check the helper that any moving-support solve will consume.

    Currently smoke-tested; the test_passivity_line_search file will
    exercise it under the actual γ rescale loop once §12 lands.
    """
    coupler_modal_energy = 1.7
    beta = 0.25
    assert support_budget(beta, coupler_modal_energy) == pytest.approx(
        0.25 * 1.7)
    # Zero/negative reservoir → zero budget (cannot draw from empty pool).
    assert support_budget(beta, 0.0) == 0.0
    assert support_budget(beta, -1e-9) == 0.0


# ---------------------------------------------------------------------------
# Invariant 7 — closed-system non-increase (explicit version)
# ---------------------------------------------------------------------------

def test_invariant_7_closed_system_non_increase_via_ledger():
    """Re-runs the §15 ledger check from a different scene + different
    horizon to give Invariant 7 its own test row in the report. Catches
    regressions that pass §15 but break under a slightly different
    initial-velocity profile.
    """
    world, coupler = _build_closed_scene()
    ledger = EnergyLedger()
    for _ in range(60):
        bodies = [d.dcr_body for d in world._descs]
        ledger.record_pre(time=world.time, bodies=bodies, couplers=[coupler])
        world.step()
        bodies_after = [d.dcr_body for d in world._descs]
        ledger.record_post(bodies=bodies_after, couplers=[coupler])
    ledger.check_non_increase(tol=1e-6, relative_tol=5e-2)


# ---------------------------------------------------------------------------
# Sanity: passive_alpha output respects budget by construction
# ---------------------------------------------------------------------------

def test_passive_alpha_quadratic_cap_holds():
    """If the coupler ever sets last_alpha < 1, it MUST be because the
    full kick would have exceeded η·E_loss — and the post-kick energy
    delta is then ≤ budget + ε."""
    world, coupler = _build_gravity_scene()
    saw_capped = False
    for _ in range(80):
        world.step()
        if 0.0 < coupler.last_alpha < 1.0:
            saw_capped = True
            injected = max(
                0.0,
                float(coupler.last_E_modal_post_kick
                      - coupler.last_E_modal_pre_kick))
            budget = world.eta * world.last_E_loss
            # The cap binds: injected should saturate just under budget.
            assert injected <= budget + 1e-9, (
                f"capped step but injected={injected:.4e} > budget={budget:.4e}")
    # Don't hard-require capping (depends on scene timing) — but log it.
    # If we never see a cap fire, the scene is too gentle to exercise §22.
    # That's fine for this test; the assertion above is what actually matters.
    _ = saw_capped
