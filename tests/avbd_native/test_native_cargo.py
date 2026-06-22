"""M2 — native cargo deformation (fem_rigid), no coupler.

A deformable cargo cube is a tumbling 6-DOF rigid box (real SAT collision) whose
elastic modes `a ∈ R^k` join the augmented native modal vector Q = [q_support; a]
(two_band_coupling.html). The cube's contact corners feed BOTH the rigid gradient
(colored primal) and the co-rotated modal gradient G_a = n̂ᵀ·R·Φ_c (the q-block);
the cube's frozen corner flex is baked into the SUPPORT_CONTACT anchor so the
primal/dual kernels are unchanged. No coupler, no hook — `add_cargo_native`.

Parity follows the M1.3 method: the device augmented q-block is float64, so on a
SMOOTH trajectory (plucked cube, no contact) it matches the numpy reference to
fp64 roundoff; with engaged contact it tracks at float32-ULP (chaotic round-off),
the macroscopic energy agreeing.
"""
from __future__ import annotations

import numpy as np
import pytest
import warp as wp

from dcr.avbd._solver.solver_6dof import Solver6DOF
from dcr.avbd.cargo.fem_rigid import (
    build_fem_rigid_cube,
    build_fem_cube,
    build_rigid_cube,
)
from dcr.avbd.cargo.abd import build_abd_cube
from dcr.fem.fem_model import Material


def _make_test_cube(kind, n_elastic, E):
    """Build a cargo cube of the requested material (the builders differ)."""
    if kind == "abd":
        return build_abd_cube(size=0.1, nx=3, kappa_v=2.0e3, alpha0=1.0, drop_y=0.0)
    if kind == "rigid":
        # k=0 baseline: a pure rigid cube with no elastic modes.
        return build_rigid_cube(size=0.1, nx=3, drop_y=0.0,
                                material=Material(E=E, nu=0.3, rho=600.0))
    builder = {"fem_rigid": build_fem_rigid_cube, "fem": build_fem_cube}[kind]
    return builder(size=0.1, n_elastic=n_elastic, drop_y=0.0,
                   material=Material(E=E, nu=0.3, rho=600.0))


def _has_cuda() -> bool:
    try:
        wp.init()
        return wp.get_cuda_device_count() > 0
    except Exception:
        return False


def _build(device="cpu", resident=None, *, kind="fem_rigid", drop=0.05,
           mass=None, E=1.0e6, n_elastic=3, gravity=(0.0, -9.81, 0.0)):
    """A deformable cube (kind = fem_rigid | fem) on a 2-mode modal slab via the
    native cargo path."""
    s = Solver6DOF(dt=1.0 / 60.0, iterations=10, substeps=4, device=device,
                   gravity=gravity)
    size = 0.1
    half = 0.5 * size
    cube = _make_test_cube(kind, n_elastic, E)
    m = float(cube.mass) if mass is None else mass
    body = s.add_box(position=(0.0, half + drop, 0.0),
                     half_extents=(half,) * 3, mass=m)
    r = 2
    omegas = np.array([45.0, 150.0])
    Mq = np.eye(r)
    Kq = np.diag(omegas ** 2)
    Dq = 0.02 * Mq + 2.0e-5 * Kq
    s.set_modal_support(Mq, Kq, Dq)
    if resident is not None:
        s._modal_device_resident = resident
    U_y = np.array([1.0, 0.4])
    rows = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                off = (sx * half, sy * half, sz * half)
                rows.append((s.add_support_contact_corner(
                    body, off_a=off, y_rest=0.0, U_y_row=U_y), off))
    cb = cube.corner_body
    support_rows = [(slot, int(np.argmin(np.linalg.norm(cb - np.array(off), axis=1))))
                    for slot, off in rows]
    s.add_cargo_native(body, cube, support_rows)
    return s, body, cube


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["fem_rigid", "fem", "abd"])
def test_cargo_deforms_and_rings_two_way_cpu(kind):
    """The cube deforms (a ≠ 0) AND the slab rings (modal KE > 0); the frozen-q̇
    counterfactual kills the slab ring. No tunneling. fem_rigid (co-rotated
    modes) and fem (world-fixed modes, corotate=False) both via the native
    cargo path."""
    peak = {}
    for name, frz in (("dyn", False), ("frz", True)):
        s, body, cube = _build(kind=kind)
        s._modal_freeze_qdot = frz
        pk = 0.0
        for _ in range(120):
            s.step()
            pk = max(pk, s.last_modal_KE)
        peak[name] = pk
        P = s.positions()
        assert np.all(np.isfinite(P)), "no NaN"
        assert float(P[body.index][1]) > -0.02, "cube must not tunnel the slab"
        if not frz:
            assert np.linalg.norm(s.cargo_a(body.index)) > 1e-12, "cube must deform"
    assert peak["dyn"] > 1e-7, f"dynamic slab should ring ({peak['dyn']:.2e})"
    assert peak["dyn"] > 10.0 * max(peak["frz"], 1e-30), (
        f"dynamic ring {peak['dyn']:.2e} should dwarf frozen {peak['frz']:.2e}")


def test_rigid_cargo_no_deform_but_rings_two_way_cpu():
    """The "rigid" cargo material (k=0): the cube carries NO elastic modes — its
    augmented a-block is empty so it cannot deform — yet it still rings the slab
    two-way through its contact corners (the M1 support-only modal load). The
    frozen-q̇ counterfactual kills the slab ring; nothing tunnels. This is the
    k=0 limit of fem_rigid: the native cargo path reduces to the support solve."""
    s0, b0, cube0 = _build(kind="rigid")
    assert cube0.k == 0, "rigid cargo must carry zero elastic modes"
    assert s0.cargo_a(b0.index).size == 0, "rigid cargo has an empty a-block"

    peak = {}
    for name, frz in (("dyn", False), ("frz", True)):
        s, body, cube = _build(kind="rigid")
        s._modal_freeze_qdot = frz
        pk = 0.0
        for _ in range(120):
            s.step()
            pk = max(pk, s.last_modal_KE)
        peak[name] = pk
        P = s.positions()
        assert np.all(np.isfinite(P)), "no NaN"
        assert float(P[body.index][1]) > -0.02, "cube must not tunnel the slab"
        # The cube never deforms — the a-block is empty for the whole run.
        assert np.linalg.norm(s.cargo_a(body.index)) == 0.0, "rigid cube cannot deform"
    assert peak["dyn"] > 1e-7, f"rigid cube should still ring the slab ({peak['dyn']:.2e})"
    assert peak["dyn"] > 10.0 * max(peak["frz"], 1e-30), (
        f"dynamic ring {peak['dyn']:.2e} should dwarf frozen {peak['frz']:.2e}")


def test_abd_shears_under_impact_and_v_perp_passive():
    """abd: the cube shears under impact (orthogonality defect ‖FᵀF−I‖ > 0) with
    no tunneling, and a plucked affine deformation relaxes monotone (V⊥ + damping
    is dissipative — the nonlinear internal is wired into the augmented q-block)."""
    # impact → shear, no tunnel
    s, body, cube = _build(kind="abd", drop=0.05)
    s._modal_freeze_qdot = False
    max_shear = 0.0
    for _ in range(180):
        s.step()
        d = s.cargo_a(body.index)
        F = np.eye(3) + d.reshape(3, 3)
        max_shear = max(max_shear, float(np.linalg.norm(F.T @ F - np.eye(3))))
    P = s.positions()
    assert np.all(np.isfinite(P))
    assert max_shear > 1e-9, "abd cube should shear under impact"
    assert float(P[body.index][1]) > -0.02, "abd cube must not tunnel"
    # V⊥ passivity: pluck a sheared F with a static body, energy monotone down
    s2, b2, cube2 = _build(kind="abd", mass=0.0, drop=2.0)
    s2._a_cargo_host[b2.index][:] = 0.05 * np.array(
        [1, 0.2, 0, 0.2, -1, 0, 0, 0, 1.0])
    s2._build_augmented_modal()
    o = s2._cargo_offset[b2.index]

    def E():
        Qd = s2._qdot_aug
        return 0.5 * float(Qd @ s2._Mq_aug @ Qd) + cube2.internal_energy(s2._q_aug[o:])
    s2.step()
    E_prev = E()
    E0 = E_prev
    for _ in range(120):
        s2.step()
        e = E()
        assert e <= E_prev + 1e-7, f"V⊥ energy rose {E_prev:.3e} -> {e:.3e}"
        E_prev = e
    assert E_prev < 0.7 * E0, "the plucked affine deformation should relax"


def test_cargo_passivity_free_ringdown_cpu():
    """Static body (no contact), pluck the cube modes: the augmented modal energy
    rings down monotone non-increasing (backward Euler is dissipative)."""
    s, body, cube = _build(mass=0.0, drop=2.0)
    s._a_cargo_host[body.index][:] = np.array([0.02, -0.01, 0.015])[:cube.k]
    s._adot_cargo_host[body.index][:] = 0.0
    s._build_augmented_modal()

    def E():
        Q, Qd = s._q_aug, s._qdot_aug
        return float(0.5 * Qd @ s._Mq_aug @ Qd + 0.5 * Q @ s._Kq_aug @ Q)

    s.step()
    E_prev = E()
    E0 = E_prev
    for _ in range(120):
        s.step()
        e = E()
        assert e <= E_prev + 1e-9, f"modal energy rose {E_prev:.3e} -> {e:.3e}"
        E_prev = e
    assert E_prev < 0.7 * E0, "the plucked cube ring should decay"


# ---------------------------------------------------------------------------
# Parity: numpy reference vs warp device q-block
# ---------------------------------------------------------------------------
def test_cargo_qblock_device_matches_numpy_smooth_cpu():
    """Smooth trajectory (plucked cube, static body → no contact branch): the
    warp augmented q-block (cpu) matches the numpy reference to fp64 roundoff."""
    pluck = np.array([0.02, -0.01, 0.015])
    ref, rb, _ = _build("cpu", resident=False, mass=0.0, gravity=(0.0, 0.0, 0.0))
    dev, db, _ = _build("cpu", resident=True, mass=0.0, gravity=(0.0, 0.0, 0.0))
    for s, b in ((ref, rb), (dev, db)):
        s._a_cargo_host[b.index][:] = pluck
        s._build_augmented_modal()
    for _ in range(60):
        ref.step()
        dev.step()
        assert np.max(np.abs(ref.cargo_a(rb.index) - dev.cargo_a(db.index))) < 1e-11
        assert np.max(np.abs(ref.modal_q - dev.modal_q)) < 1e-11


def test_cargo_engaged_contact_tracks_cpu():
    """With engaged contact, warp tracks the numpy reference at float32-ULP scale
    (chaotic round-off) and the macroscopic slab ring energy agrees."""
    ref, rb, _ = _build("cpu", resident=False)
    dev, db, _ = _build("cpu", resident=True)
    pk_ref = pk_dev = 0.0
    for _ in range(120):
        ref.step()
        dev.step()
        pk_ref = max(pk_ref, ref.last_modal_KE)
        pk_dev = max(pk_dev, dev.last_modal_KE)
        assert np.max(np.abs(ref.positions() - dev.positions())) < 1e-3
    assert abs(pk_ref - pk_dev) <= 0.1 * max(pk_ref, 1e-12)


# ---------------------------------------------------------------------------
# CUDA residency
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device")
@pytest.mark.parametrize("kind", ["rigid", "fem_rigid", "fem", "abd"])
def test_cargo_cuda_resident_and_graph_captured(kind):
    s, body, cube = _build("cuda:0", resident=None, kind=kind)
    for _ in range(40):
        s.step()
    assert s._modal_resident is True, "cargo path should be device-resident on cuda"
    assert s._graph is not None, "iteration loop should be CUDA-graph-captured"
    assert np.all(np.isfinite(s.positions()))
    assert s.last_modal_KE > 1e-12, "the drop should ring the slab (two-way)"


@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device")
def test_cargo_cuda_matches_cpu_reference():
    ref, rb, _ = _build("cpu", resident=False)
    gpu, gb, _ = _build("cuda:0", resident=None)
    pk_ref = pk_gpu = 0.0
    for _ in range(120):
        ref.step()
        gpu.step()
        pk_ref = max(pk_ref, ref.last_modal_KE)
        pk_gpu = max(pk_gpu, gpu.last_modal_KE)
    assert np.all(np.isfinite(gpu.positions()))
    assert abs(pk_ref - pk_gpu) <= 0.1 * max(pk_ref, 1e-12)
    assert abs(np.linalg.norm(ref.cargo_a(rb.index))
               - np.linalg.norm(gpu.cargo_a(gb.index))) < 1e-9


def test_cargo_native_scene_runs_no_coupler():
    """The cargo scene builder wires native fem_rigid cargo with NO coupler
    (build_cargo_scene solver='native'): the cube settles on the slab, deforms,
    rings it two-way, and nothing tunnels."""
    from scenes.reduced_fem_rigid_cargo import build_cargo_scene, cube_state_world
    h = build_cargo_scene("fem_rigid", solver="native", device="cpu",
                          drop_height=0.04, iterations=8, avbd_substeps=4)
    assert h.coupler is None, "native path attaches no coupler"
    s = h.world._solver
    pk = 0.0
    for _ in range(150):
        h.world.step()
        pk = max(pk, s.last_modal_KE)
    P = s.positions()
    assert np.all(np.isfinite(P))
    assert float(P[h.avbd_idx][1]) > h.support_top - 0.005, "cube must not tunnel"
    assert np.linalg.norm(cube_state_world(h)[7:]) > 1e-12, "cube must deform"
    assert pk > 1e-9, "the drop should ring the slab two-way"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
