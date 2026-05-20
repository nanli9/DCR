"""Stage E3 acceptance tests — passive injection wired into the rigid step.

E3.3 criteria:
1. eta=0: no distant response, E_modal stays at zero.
2. eta=1: plates move, cumulative E_modal_injected <= cumulative E_loss.
3. Sanity vs original DCR: plates move in same direction at same impact frames.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy
from dcr.rigid import (
    make_dynamic_box, make_static_plane,
    ConstraintSolver,
)
from dcr.dcr import ModalDCRCoupler, PassiveDCRCoupler, DCRWorld


def _build_passive_dinner_scene(
    eta: float = 0.3,
    dcr_enabled: bool = True,
    pot_mass: float = 5.0,
    pot_height: float = 1.0,
    h: float = 1e-3,
) -> tuple[DCRWorld, list[int], int, PassiveDCRCoupler]:
    """Build the dinner scene with a PassiveDCRCoupler instead of ModalDCRCoupler."""
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=dcr_enabled,
        eta=eta,
    )

    # Elastic table (static plane for collision)
    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)

    # FEM / modal model
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
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    # Plates
    plate_indices = []
    for pos in [(-0.3, 0.025, 0.15), (0.3, 0.025, -0.1), (0.0, 0.025, -0.2)]:
        plate = make_dynamic_box(
            mass=0.2, hx=0.06, hy=0.02, hz=0.06,
            position=pos, restitution=0.0, friction=0.5,
        )
        plate_indices.append(world.add_body(plate))

    # Heavy pot
    pot = make_dynamic_box(
        mass=pot_mass, hx=0.08, hy=0.08, hz=0.08,
        position=(0.0, pot_height, 0.0), restitution=0.1, friction=0.5,
    )
    pot_idx = world.add_body(pot)

    return world, plate_indices, pot_idx, coupler


def _settle(world, plate_indices, n_steps=200):
    pot_idx = len(world.bodies) - 1
    world.bodies[pot_idx].is_static = True
    old_dcr = world.dcr_enabled
    world.dcr_enabled = False
    for _ in range(n_steps):
        world.step()
    for idx in plate_indices:
        world.bodies[idx].velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = old_dcr


def test_eta_zero_no_response():
    """E3.3 criterion 1: eta=0 → no modal injection, plates don't move."""
    world, plate_indices, _, coupler = _build_passive_dinner_scene(eta=0.0)
    _settle(world, plate_indices)

    max_vy = 0.0
    omega = coupler.modal.frequencies

    for _ in range(500):
        world.step()
        for idx in plate_indices:
            vy = abs(world.bodies[idx].velocity[1])
            max_vy = max(max_vy, vy)

    # Modal energy should be zero (no injection with eta=0)
    E_modal_final = modal_energy(
        coupler._stepper.q, coupler._stepper.qdot, omega)
    print(f"  eta=0: max plate |vy| = {max_vy:.2e}, E_modal = {E_modal_final:.2e}")

    assert E_modal_final < 1e-20, f"E_modal should be ~0 with eta=0, got {E_modal_final}"
    # Plates shouldn't move (beyond PGS numerical noise)
    assert max_vy < 1e-4, f"Plates moved with eta=0: max vy = {max_vy:.2e}"


def test_eta_one_energy_bounded():
    """E3.3 criterion 2: eta=1 → plates move, cumulative injection <= cumulative loss."""
    world, plate_indices, _, coupler = _build_passive_dinner_scene(eta=1.0)
    _settle(world, plate_indices)

    omega = coupler.modal.frequencies
    cumulative_injected = 0.0
    cumulative_loss = 0.0
    max_vy = 0.0

    for step_i in range(500):
        world.step()

        # Track energy injection per step
        dE_injected = max(0.0,
            coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick)
        cumulative_injected += dE_injected
        cumulative_loss += world.last_E_loss

        # Check invariant every step (foundation §15)
        assert cumulative_injected <= cumulative_loss + 1e-9, (
            f"Step {step_i}: cumulative injected {cumulative_injected:.6e} > "
            f"cumulative loss {cumulative_loss:.6e}")

        for idx in plate_indices:
            vy = world.bodies[idx].velocity[1]
            max_vy = max(max_vy, vy)

    print(f"  eta=1: max plate vy = {max_vy:.6e}")
    print(f"  eta=1: cumulative injected = {cumulative_injected:.6e}")
    print(f"  eta=1: cumulative loss = {cumulative_loss:.6e}")

    assert max_vy > 1e-6, f"Plates didn't move with eta=1: max vy = {max_vy:.2e}"


def test_sanity_vs_original_dcr():
    """E3.3 criterion 3: passive plates move in same direction as original DCR."""
    # --- Original DCR (forced IIR) ---
    world_orig = DCRWorld(
        h=1e-3,
        solver=ConstraintSolver(h=1e-3, cfm=1e-6, erp=0.2, pgs_iterations=80),
    )
    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world_orig.add_body(table)

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
    coupler_orig = ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world_orig.add_dcr_coupler(coupler_orig)

    plate_indices_orig = []
    for pos in [(-0.3, 0.025, 0.15), (0.3, 0.025, -0.1), (0.0, 0.025, -0.2)]:
        plate = make_dynamic_box(mass=0.2, hx=0.06, hy=0.02, hz=0.06,
                                 position=pos, restitution=0.0, friction=0.5)
        plate_indices_orig.append(world_orig.add_body(plate))
    pot = make_dynamic_box(mass=5.0, hx=0.08, hy=0.08, hz=0.08,
                           position=(0.0, 1.0, 0.0), restitution=0.1, friction=0.5)
    world_orig.add_body(pot)

    # Settle and run original
    pot_idx = len(world_orig.bodies) - 1
    world_orig.bodies[pot_idx].is_static = True
    world_orig.dcr_enabled = False
    for _ in range(200):
        world_orig.step()
    for idx in plate_indices_orig:
        world_orig.bodies[idx].velocity[:] = 0.0
    world_orig.bodies[pot_idx].is_static = False
    world_orig.dcr_enabled = True

    orig_max_vy = [0.0] * 3
    for _ in range(500):
        world_orig.step()
        for i, idx in enumerate(plate_indices_orig):
            vy = world_orig.bodies[idx].velocity[1]
            if vy > orig_max_vy[i]:
                orig_max_vy[i] = vy

    # --- Passive DCR ---
    world_pass, plate_indices_pass, _, _ = _build_passive_dinner_scene(eta=1.0)
    _settle(world_pass, plate_indices_pass)

    pass_max_vy = [0.0] * 3
    for _ in range(500):
        world_pass.step()
        for i, idx in enumerate(plate_indices_pass):
            vy = world_pass.bodies[idx].velocity[1]
            if vy > pass_max_vy[i]:
                pass_max_vy[i] = vy

    # Both should have positive upward velocity (same direction)
    for i in range(3):
        print(f"  Plate {i}: orig vy={orig_max_vy[i]:.6e}, "
              f"passive vy={pass_max_vy[i]:.6e}")
        if orig_max_vy[i] > 1e-6:
            assert pass_max_vy[i] > 1e-8, (
                f"Passive plate {i} didn't respond when original did")
