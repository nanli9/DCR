"""Stage 4 — co-rotated affine (abd) cube coupling in the dynamic AVBD coupler.

An abd cargo cube — a 6-DOF rigid frame (real SAT collision, tumbling) PLUS a
9-DOF body-frame affine deformation F governed by the stiff quartic
orthogonality potential V⊥ (Lan et al. 2022, ABD Eq. 6–8) — dropped onto the
reduced-modal support. The affine deformation rides the SAME augmented modal
vector Q = [q_support; d_cube] as fem_rigid (the affine corner Jacobian B_c
plays the role of the modal Φ_c), with the nonlinear V⊥ as the cargo block's
internal grad/Hess. CPU reference path (CLAUDE.md rule 6).

Validates: determinism, the cube SHEARS on impact, V⊥ keeps F near a rotation,
free-ringdown energy monotonicity, two-way counterfactual, zero penetration.
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
from dcr.avbd.cargo.abd import build_abd_cube
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

SUPPORT_TOP = 0.0


def _build(*, freeze_qdot=False, drop=0.03, pluck=0.0, kappa_v=2.0e3):
    h = 1.0 / 120.0
    world = AVBDDCRWorld(h=h, device="cpu", avbd_iterations=8, avbd_substeps=4)
    world.add_floor(floor_y=SUPPORT_TOP, friction=0.5, name="support")

    cube = build_abd_cube(size=0.1, nx=3, kappa_v=kappa_v, alpha0=2.0, drop_y=0.0)
    half = cube.half_extent
    dcr_idx = world.add_box(
        mass=cube.mass, half_extents=(half, half, half),
        position=(0.0, SUPPORT_TOP + half + drop, 0.0),
        velocity_ang=(0.0, 0.0, 1.5),               # spin so R ≠ I (co-rotation)
        friction=0.5, name="abd_cube")
    avbd_idx = int(world._descs[dcr_idx].avbd_body.index)

    rs = make_debug_reduced_shelf_support(
        length=0.6, width=0.4, thickness=0.02,
        youngs=1.0e10, density=500.0, poisson=0.30,
        n_modes_global=8, n_modes_local=1,
        contact_zone_centers=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        y_rest=SUPPORT_TOP, overlay_enabled=False,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, to_eigenbasis=True)
    coupler = world.attach_reduced_coupled_avbd(
        rs, tracked_body_indices=[avbd_idx],
        shelf_length=0.6, shelf_width=0.4, shelf_y_rest=SUPPORT_TOP,
        n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z, device_resident=False)
    coupler.freeze_qdot = bool(freeze_qdot)
    coupler.add_cargo(avbd_idx, cube)
    if pluck != 0.0:
        coupler.cargo_adot[avbd_idx][:] = pluck
    return world, coupler, avbd_idx, cube


def _run(world, coupler, avbd_idx, n):
    solver = world._solver
    peak_KE, max_pen, max_d = 0.0, 0.0, 0.0
    max_ortho_err = 0.0
    d_traj = []
    for _ in range(n):
        world.step()
        peak_KE = max(peak_KE, coupler.last_cargo_modal_KE)
        max_pen = max(max_pen, coupler.last_contact_residual)
        d = coupler.cargo_a[avbd_idx]
        d_traj.append(d.copy())
        max_d = max(max_d, float(np.abs(d).max()))
        F = np.eye(3) + d.reshape(3, 3)
        max_ortho_err = max(max_ortho_err,
                            float(np.linalg.norm(F.T @ F - np.eye(3))))
    y = float(solver.positions()[avbd_idx][1])
    return dict(peak_KE=peak_KE, max_pen=max_pen, max_d=max_d,
                max_ortho_err=max_ortho_err, d_traj=np.array(d_traj), y=y)


def test_abd_determinism():
    w1, c1, i1, _ = _build()
    w2, c2, i2, _ = _build()
    r1 = _run(w1, c1, i1, 40)
    r2 = _run(w2, c2, i2, 40)
    np.testing.assert_array_equal(r1["d_traj"], r2["d_traj"])
    assert r1["y"] == r2["y"]


def test_cube_shears_on_impact():
    """The affine deformation F departs from I on impact (the cube shears),
    and the cube settles on the support."""
    world, coupler, avbd_idx, _ = _build(drop=0.03)
    r = _run(world, coupler, avbd_idx, 150)
    assert np.all(np.isfinite(r["d_traj"]))
    assert r["max_d"] > 1e-4, f"cube did not shear: {r['max_d']:.3e}"
    assert r["peak_KE"] > 1e-9, r["peak_KE"]
    assert abs(r["y"] - (SUPPORT_TOP + 0.05)) < 0.02, r["y"]


def test_v_perp_keeps_near_orthogonal():
    """V⊥ pulls F back toward a rotation — ‖FᵀF − I‖ stays bounded (the cube
    deforms but does not collapse). ABD Eq. 6–8."""
    world, coupler, avbd_idx, _ = _build(drop=0.03, kappa_v=2.0e3)
    r = _run(world, coupler, avbd_idx, 150)
    assert r["max_ortho_err"] < 0.5, r["max_ortho_err"]


def test_free_ringdown_energy_monotone():
    """A plucked affine deformation, cube held clear of the support, rings down
    with monotone non-increasing mechanical energy (½ḋᵀM_F ḋ + V⊥) — backward
    Euler is dissipative."""
    world, coupler, avbd_idx, cube = _build(drop=2.0, pluck=2.0e-2)

    def energy():
        return coupler.last_cargo_modal_KE + coupler.last_cargo_modal_PE

    E_prev, E0 = None, None
    for step in range(60):
        world.step()
        assert coupler.last_contact_residual < 1e-6
        E = energy()
        if E0 is None:
            E0 = E
        if E_prev is not None:
            assert E <= E_prev + 1e-12, f"step {step}: E rose {E_prev}→{E}"
        E_prev = E
    assert E_prev < 0.9 * E0, (E_prev, E0)


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


def _run_device(device_resident, n_steps):
    h = 1.0 / 120.0
    world = AVBDDCRWorld(h=h, device="cuda:0", avbd_iterations=8, avbd_substeps=4)
    world.add_floor(floor_y=SUPPORT_TOP, friction=0.5, name="support")
    cube = build_abd_cube(size=0.1, nx=3, kappa_v=2.0e3, alpha0=2.0, drop_y=0.0)
    half = cube.half_extent
    dcr_idx = world.add_box(
        mass=cube.mass, half_extents=(half, half, half),
        position=(0.0, SUPPORT_TOP + half + 0.03, 0.0),
        velocity_ang=(0.0, 0.0, 1.5), friction=0.5, name="abd_cube")
    avbd_idx = int(world._descs[dcr_idx].avbd_body.index)
    rs = make_debug_reduced_shelf_support(
        length=0.6, width=0.4, thickness=0.02, youngs=1.0e10, density=500.0,
        poisson=0.30, n_modes_global=8, n_modes_local=1,
        contact_zone_centers=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        y_rest=SUPPORT_TOP, overlay_enabled=False,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, to_eigenbasis=True)
    coupler = world.attach_reduced_coupled_avbd(
        rs, tracked_body_indices=[avbd_idx], shelf_length=0.6, shelf_width=0.4,
        shelf_y_rest=SUPPORT_TOP, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
        device_resident=device_resident)
    coupler.add_cargo(avbd_idx, cube)
    for _ in range(n_steps):
        world.step()
    return {"q": rs.q.copy(), "d": coupler.cargo_a[avbd_idx].copy(),
            "x": world._solver.positions()[avbd_idx].copy()}


def test_cpu_gpu_abd_parity_machine_precision():
    """The GPU-resident abd path (augmented modal R=r+9, k_eval_cargo affine
    gradient, the NONLINEAR V⊥ via k_cargo_internal) matches the numpy
    reference to fp64 round-off at a short horizon — the same build-twice /
    toggle-device_resident gate, exercising the affine block + V⊥ kernel."""
    _cuda_or_skip()
    ref = _run_device(False, 3)
    gpu = _run_device(True, 3)
    assert np.max(np.abs(gpu["q"] - ref["q"])) <= 1e-11, \
        np.max(np.abs(gpu["q"] - ref["q"]))
    assert np.max(np.abs(gpu["d"] - ref["d"])) <= 1e-11, \
        np.max(np.abs(gpu["d"] - ref["d"]))
    assert np.max(np.abs(gpu["x"] - ref["x"])) <= 1e-6, \
        np.max(np.abs(gpu["x"] - ref["x"]))


def test_two_way_counterfactual_freeze_vs_dynamic():
    wf, cf, idf, _ = _build(freeze_qdot=True, drop=0.03)
    rf = _run(wf, cf, idf, 150)
    assert rf["peak_KE"] == 0.0

    wd, cd, idd, _ = _build(freeze_qdot=False, drop=0.03)
    rd = _run(wd, cd, idd, 150)
    assert rd["peak_KE"] > 1e-9
    assert rd["peak_KE"] > rf["peak_KE"]
    assert rf["max_pen"] < 5e-3 and rd["max_pen"] < 5e-3, (rf["max_pen"], rd["max_pen"])
