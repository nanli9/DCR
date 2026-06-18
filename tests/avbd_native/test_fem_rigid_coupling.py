"""Stage 3 — fem_rigid cube modal coupling in the dynamic AVBD coupler.

A fem_rigid cargo cube (6-DOF rigid box with real SAT collision + k FEM
elastic modes) dropped onto the reduced-modal support. The cube's contact
corners feed BOTH the rigid gradient and the co-rotated modal gradient
n̂ᵀ·R·Φ_c into the SAME dynamic two-way modal block as the support
(`two_band_coupling.html`), assembled as the augmented modal vector
Q = [q_support; a_cube]. These tests validate the CPU reference path
(CLAUDE.md rule 6: reference first, device kernels follow):

  * determinism (build twice → bit-identical),
  * the cube FLEXES on impact (its elastic modes ring),
  * a free (no-contact) modal ring-down is energy-monotone (backward Euler),
  * zero penetration at rest,
  * the two-way counterfactual: freeze q̇ ⇒ 0 modal KE, dynamic ⇒ rings.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import make_debug_reduced_shelf_support
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube
from dcr.fem.material import Material
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z


SUPPORT_TOP = 0.0

# Soft-ish cube so the elastic modes flex visibly (the near-rigid E=1e9
# default deflects ~nm). The rigid SAT collision is independent of the modal
# subspace, so softening the modes does not affect penetration.
_CUBE_MAT = Material(E=1.0e6, nu=0.3, rho=600.0)


def _build(*, freeze_qdot: bool = False, drop: float = 0.03,
           pluck: float = 0.0, n_elastic: int = 6):
    """Small modal-support scene with one fem_rigid cube above its center.

    Returns (world, coupler, avbd_idx, cube)."""
    h = 1.0 / 120.0
    world = AVBDDCRWorld(h=h, device="cpu", avbd_iterations=8, avbd_substeps=4)
    world.add_floor(floor_y=SUPPORT_TOP, friction=0.5, name="support")

    cube = build_fem_rigid_cube(size=0.1, nx=3, n_elastic=n_elastic,
                                material=_CUBE_MAT, drop_y=0.0)
    half = cube.half_extent
    dcr_idx = world.add_box(
        mass=cube.mass, half_extents=(half, half, half),
        position=(0.0, SUPPORT_TOP + half + drop, 0.0),
        friction=0.5, name="fem_rigid_cube")
    avbd_idx = int(world._descs[dcr_idx].avbd_body.index)

    rs = make_debug_reduced_shelf_support(
        length=0.6, width=0.4, thickness=0.02,
        youngs=1.0e10, density=500.0, poisson=0.30,
        n_modes_global=8, n_modes_local=1,
        contact_zone_centers=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        y_rest=SUPPORT_TOP, overlay_enabled=False,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, to_eigenbasis=True,
    )
    coupler = world.attach_reduced_coupled_avbd(
        rs, tracked_body_indices=[avbd_idx],
        shelf_length=0.6, shelf_width=0.4, shelf_y_rest=SUPPORT_TOP,
        n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z, device_resident=False)
    coupler.freeze_qdot = bool(freeze_qdot)
    coupler.add_cargo(avbd_idx, cube)
    if pluck != 0.0:
        coupler.cargo_adot[avbd_idx][:] = pluck
    return world, coupler, avbd_idx, cube


def _run(world, coupler, avbd_idx, n_steps):
    solver = world._solver
    peak_modal_KE = 0.0
    max_pen = 0.0
    a_traj = []
    for _ in range(n_steps):
        world.step()
        peak_modal_KE = max(peak_modal_KE, coupler.last_cargo_modal_KE)
        max_pen = max(max_pen, coupler.last_contact_residual)
        a_traj.append(coupler.cargo_a[avbd_idx].copy())
    y = float(solver.positions()[avbd_idx][1])
    return peak_modal_KE, max_pen, np.array(a_traj), y


def test_cargo_cpu_determinism():
    """Two independent CPU builds step bit-identically (no hidden state)."""
    w1, c1, i1, _ = _build()
    w2, c2, i2, _ = _build()
    _, _, a1, y1 = _run(w1, c1, i1, 40)
    _, _, a2, y2 = _run(w2, c2, i2, 40)
    np.testing.assert_array_equal(a1, a2)
    assert y1 == y2


def test_cube_flexes_on_impact():
    """The dropped cube's elastic modes are excited by the contact: the
    cargo modal amplitude becomes nonzero and the modal KE rings."""
    world, coupler, avbd_idx, _ = _build(drop=0.03)
    peak_KE, max_pen, a_traj, y = _run(world, coupler, avbd_idx, 150)
    assert np.all(np.isfinite(a_traj))
    assert np.abs(a_traj).max() > 1e-7, "cube did not flex"
    assert peak_KE > 1e-9, f"modal KE never rang: {peak_KE:.3e}"
    # Cube ends resting on the support (COM ≈ support_top + half_extent).
    assert abs(y - (SUPPORT_TOP + 0.05)) < 0.02, y


def test_free_modal_ringdown_is_energy_monotone():
    """A plucked cube held clear of the support (no contact) rings down with
    monotone non-increasing modal mechanical energy — backward Euler is
    dissipative (two_band_coupling.html "Passive for free"), per cube."""
    # Hold the cube well above the support so its FLOOR rows never engage.
    world, coupler, avbd_idx, cube = _build(drop=2.0, pluck=5.0e-3)
    om2 = cube.omega2

    def modal_E():
        a = coupler.cargo_a[avbd_idx]
        adot = coupler.cargo_adot[avbd_idx]
        return 0.5 * float(adot @ adot) + 0.5 * float(a @ (om2 * a))

    E_prev = None
    E0 = None
    for step in range(60):
        world.step()
        # Contact must be inactive (free fall): residual stays ~0.
        assert coupler.last_contact_residual < 1e-6
        E = coupler.last_cargo_modal_KE + coupler.last_cargo_modal_PE
        if E0 is None:
            E0 = E
        if E_prev is not None:
            assert E <= E_prev + 1e-12, f"step {step}: E rose {E_prev}→{E}"
        E_prev = E
    assert E_prev < 0.5 * E0, (E_prev, E0)


def _cuda_or_skip():
    import warp as wp
    try:
        if wp.get_cuda_device_count() < 1:
            import pytest
            pytest.skip("no CUDA device")
    except Exception:
        import pytest
        pytest.skip("warp CUDA unavailable")
    return "cuda:0"


def _run_device(device, device_resident, n_steps, spin=4.0):
    """Build on `device` with the given residency flag; return modal + body
    state after n_steps. CPU reference vs GPU-resident augmented-modal path."""
    from scenes.reduced_fem_rigid_cargo import build_fem_rigid_cargo
    h = build_fem_rigid_cargo(
        device=device, drop_height=0.03, spin=spin,
        device_resident=device_resident)
    solver = h.world._solver
    for _ in range(n_steps):
        h.world.step()
    return {
        "q": h.rs.q.copy(),
        "a": h.coupler.cargo_a[h.avbd_idx].copy(),
        "adot": h.coupler.cargo_adot[h.avbd_idx].copy(),
        "x": solver.positions()[h.avbd_idx].copy(),
    }


def test_cpu_gpu_cargo_parity_machine_precision():
    """The GPU-resident augmented-modal path (row_U_y grows to R=r+k, the
    co-rotated cargo gradient from k_eval_cargo, block-diagonal Mq/Kq/Dq)
    matches the numpy reference to fp64 round-off at a short horizon — the
    same build-twice / toggle-device_resident gate as the support-only Stage 1
    parity, now exercising the cube's elastic block."""
    dev = _cuda_or_skip()
    ref = _run_device(dev, False, 3)
    gpu = _run_device(dev, True, 3)
    # Augmented modal coords are f64 ⇒ tight; body x is f32 in the solver.
    assert np.max(np.abs(gpu["q"] - ref["q"])) <= 1e-11, \
        np.max(np.abs(gpu["q"] - ref["q"]))
    assert np.max(np.abs(gpu["a"] - ref["a"])) <= 1e-11, \
        np.max(np.abs(gpu["a"] - ref["a"]))
    assert np.max(np.abs(gpu["adot"] - ref["adot"])) <= 1e-8, \
        np.max(np.abs(gpu["adot"] - ref["adot"]))
    assert np.max(np.abs(gpu["x"] - ref["x"])) <= 1e-6, \
        np.max(np.abs(gpu["x"] - ref["x"]))


def test_two_way_counterfactual_freeze_vs_dynamic():
    """freeze_qdot ⇒ the cube's modal velocity is held at 0, so its modal KE
    is exactly 0 every step; the full dynamic constraint rings (>0) and
    carries strictly more modal energy — the `two_band_coupling.html`
    two-way signature, per cargo cube."""
    wf, cf, idf, _ = _build(freeze_qdot=True, drop=0.03)
    peak_KE_frozen, pen_f, a_f, _ = _run(wf, cf, idf, 150)
    assert peak_KE_frozen == 0.0, peak_KE_frozen

    wd, cd, idd, _ = _build(freeze_qdot=False, drop=0.03)
    peak_KE_dyn, pen_d, a_d, _ = _run(wd, cd, idd, 150)
    assert peak_KE_dyn > 1e-9
    assert peak_KE_dyn > peak_KE_frozen

    # Both keep the cube out of the support (no runaway penetration).
    assert pen_f < 5e-3 and pen_d < 5e-3, (pen_f, pen_d)
