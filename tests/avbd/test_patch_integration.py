"""End-to-end Phase A integration: AVBD + patch coupler run a truck-like
scene without raising and respect the foundation §15 energy invariant
(cumulative dE_modal_injected ≤ η · cumulative dE_rigid_loss + ε)."""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd import AVBDDCRWorld
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.fem import Material, FEMModel
from dcr.geom import make_slab_tet_mesh
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy


def _build_mini_scene(h: float = 1.0 / 120.0):
    """Tiny truck-like scene: one drop above a wood slab."""
    world = AVBDDCRWorld(h=h, eta=0.5, device="cpu")
    ground_top = 0.03
    floor_idx = world.add_floor(floor_y=ground_top, friction=0.6)
    mesh = make_slab_tet_mesh(
        length=1.0, width=0.6, height=0.04, nx=8, ny=6, nz=2)
    fem = FEMModel(
        mesh=mesh,
        material=Material(E=10.0e9, nu=0.3, rho=500.0),
        fixed_nodes=np.array([], dtype=np.int32),  # free-free for simplicity
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
        position=(0.0, ground_top + 0.5, 0.0), friction=0.6,
    )
    return world, coupler


def test_avbd_patch_runs_50_steps():
    world, coupler = _build_mini_scene()
    for _ in range(50):
        world.step()
    assert world.time > 0.0


def test_only_patch_mode_accepted():
    """The world refuses any non-patch coupler at registration time."""
    world = AVBDDCRWorld(h=1.0 / 120.0)
    # Build a minimal modal so PassiveDCRCoupler.__init__ runs.
    mesh = make_slab_tet_mesh(length=0.5, width=0.5, height=0.05,
                              nx=4, ny=4, nz=2)
    fem = FEMModel(
        mesh=mesh, material=Material(E=1e9, nu=0.3, rho=500.0),
        fixed_nodes=np.array([], dtype=np.int32),
    )
    modal = ModalAnalysis(fem=fem, num_modes=4)
    # Passive coupler with the AVBD-allowed mode succeeds.
    ok = PassiveDCRCoupler(
        modal=modal, elastic_body_idx=0,
        dcr_velocity_mode="energy_prescribed_patch")
    world.add_floor(0.0)
    world.add_passive_coupler(ok)
    # Coupler construction with a forbidden mode is rejected up-front.
    with pytest.raises(ValueError):
        PassiveDCRCoupler(modal=modal, elastic_body_idx=0,
                          dcr_velocity_mode="coevoet")


def test_modal_injection_respects_eta_loss_bound():
    """Foundation §15: cumulative dE_modal_injected ≤ η · cumulative dE_rigid_loss
    (with a small numerical tolerance). Run a brief drop + bounce.
    """
    h = 1.0 / 120.0
    world, coupler = _build_mini_scene(h=h)
    cum_loss = 0.0
    cum_inject = 0.0
    omega = coupler.modal.frequencies
    e_modal_prev = 0.0
    for _ in range(60):
        e_modal_prev = float(modal_energy(
            coupler._stepper.q, coupler._stepper.qdot, omega))
        world.step()
        e_modal_post = float(modal_energy(
            coupler._stepper.q, coupler._stepper.qdot, omega))
        cum_loss += world.last_E_loss
        # net change in modal energy is the *injected minus dissipated*;
        # we only need an upper bound on injection, so use the increase.
        dE_modal = max(0.0, e_modal_post - e_modal_prev)
        cum_inject += dE_modal
    eta = world.eta
    # Allow 5% tolerance — homogeneous stepper damping + numerical noise
    # add slack vs the pure analytic bound. Empirically, in Phase A the
    # patch coupler's internal `passive_alpha` already enforces the bound
    # tightly; this is a safety net for the full pipeline.
    assert cum_inject <= eta * cum_loss + 1e-4 + 0.05 * eta * cum_loss, (
        f"§15 invariant violated: dE_modal_inj={cum_inject:.5f} > "
        f"eta * dE_rigid_loss={eta * cum_loss:.5f}")
