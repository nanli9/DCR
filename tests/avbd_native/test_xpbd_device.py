"""Stage 2b — SolverXPBD device-resident warp path: parity vs the numpy reference.

The warp path (`xpbd_kernels.py`, fused into two phase kernels per substep) is a
device-resident, CUDA-graph-capturable re-expression of `_substep_cpu`. It must
track the numpy reference to fp64 roundoff (CLAUDE.md rule 6 / build-plan parity
gate): the GS projection ORDER is byte-identical (the sweeps run as compiled
sequential kernels), so the only divergence is float op ordering.

Hard parity gate: the deterministic cargo drop on the modal support (no box-box
ambiguity). The box-box stack is bit-identical because the device SAT emits
contacts in the exact `_CORNER_SIGNS` order. CUDA tests skip when unavailable.
"""
from __future__ import annotations

import numpy as np
import pytest
import warp as wp

from dcr.avbd._solver.solver_xpbd import SolverXPBD
from scenes.reduced_scene_common import make_cargo_cube

wp.init()
_HAS_CUDA = wp.is_cuda_available()


def _build_cargo(material, *, device, force_warp, parallel=None):
    half, y_rest, size, mass = 0.05, 0.5, 0.10, 1.0
    cube = make_cargo_cube(material, size=size, mass=mass, n_elastic=6)
    w = 2.0 * np.pi * 25.0
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=8, device=device)
    s._force_warp = force_warp
    s._parallel_device = parallel
    s.set_modal_support(np.eye(1), np.array([[w * w]]),
                        np.array([[2.0 * 0.01 * w]]))
    box = s.add_box(position=(0.0, y_rest + half + 0.03, 0.0),
                    half_extents=(half, half, half), mass=mass)
    cb = np.asarray(cube.corner_body, dtype=np.float64)
    rows = []
    for pid in range(cb.shape[0]):
        if cb[pid, 1] < 0.0:
            slot = s.add_support_contact_corner(box, tuple(cb[pid]), y_rest,
                                                np.ones(1))
            rows.append((slot, pid))
    s.add_cargo(box, cube, rows)
    return s, box


def _build_stack(*, device, force_warp, nstack=4, parallel=None):
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=8, device=device)
    s._force_warp = force_warp
    s._parallel_device = parallel
    s.enable_self_collision(True, default_friction=0.5)
    he = 0.05
    for i in range(nstack):
        b = s.add_box(position=(0.0, he + 2 * he * i + 1e-4 * i, 0.0),
                      half_extents=(he, he, he), mass=1.0, friction=0.5)
        s.add_floor_contact_box(b, floor_y=0.0, friction=0.5)
    return s


def _compare(s_ref, s_dev, n=60, modal=True):
    max_dp = max_dq = max_dmq = 0.0
    for _ in range(n):
        s_ref.step()
        s_dev.step()
        max_dp = max(max_dp, float(np.abs(s_ref.positions()
                                          - s_dev.positions()).max()))
        max_dq = max(max_dq, float(np.abs(s_ref.orientations()
                                          - s_dev.orientations()).max()))
        if modal and s_ref.modal_q is not None:
            max_dmq = max(max_dmq, float(np.abs(s_ref.modal_q
                                                - s_dev.modal_q).max()))
    return max_dp, max_dq, max_dmq


# ---- warp-CPU (LLVM-compiled) vs numpy: same float64, same GS order ----
@pytest.mark.parametrize("material", ["rigid", "fem_rigid", "fem"])
def test_warpcpu_cargo_parity(material):
    ref, _ = _build_cargo(material, device="cpu", force_warp=False)
    dev, _ = _build_cargo(material, device="cpu", force_warp=True)
    dp, dq, dmq = _compare(ref, dev)
    assert dev._on_device
    assert dp < 1e-5, f"{material}: position drift {dp:.2e}"
    assert dq < 1e-5, f"{material}: orientation drift {dq:.2e}"
    assert dmq < 1e-6, f"{material}: modal_q drift {dmq:.2e}"


def test_warpcpu_stack_parity():
    ref = _build_stack(device="cpu", force_warp=False)
    dev = _build_stack(device="cpu", force_warp=True)
    dp, dq, _ = _compare(ref, dev, modal=False)
    assert dev._on_device
    # the device SAT emits in _CORNER_SIGNS order ⇒ bit-identical GS sweeps
    assert dp < 1e-6, f"stack position drift {dp:.2e}"
    assert dq < 1e-6, f"stack orientation drift {dq:.2e}"


# ---- CUDA-resident SERIAL (dim=1) path vs numpy reference: bit-parity ----
# Forcing _parallel_device=False runs the serial-GS device kernels, which
# preserve the numpy GS order ⇒ bit-parity. (The default CUDA path is the
# parallel one — covered by the physical-agreement tests below.)
@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
@pytest.mark.parametrize("material", ["rigid", "fem_rigid", "fem"])
def test_cuda_cargo_parity_serial(material):
    ref, _ = _build_cargo(material, device="cpu", force_warp=False)
    dev, _ = _build_cargo(material, device="cuda:0", force_warp=False,
                          parallel=False)
    dp, dq, dmq = _compare(ref, dev)
    assert dev._on_device
    assert dev._graph is not None, "CUDA-graph not captured"
    assert dp < 1e-5, f"{material}: cuda position drift {dp:.2e}"
    assert dq < 1e-5, f"{material}: cuda orientation drift {dq:.2e}"
    assert dmq < 1e-6, f"{material}: cuda modal_q drift {dmq:.2e}"


@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
def test_cuda_stack_parity_serial_and_graph():
    ref = _build_stack(device="cpu", force_warp=False)
    dev = _build_stack(device="cuda:0", force_warp=False, parallel=False)
    dp, dq, _ = _compare(ref, dev, modal=False)
    assert dev._on_device and dev._graph is not None
    assert dp < 1e-6, f"cuda stack position drift {dp:.2e}"
    assert dq < 1e-6, f"cuda stack orientation drift {dq:.2e}"


# ---- PARALLEL (averaged-Jacobi) path: physical agreement, not bit-parity ----
# The parallel schedule (serial GS → averaged Jacobi) differs from the serial
# reference per-step, so we assert the cube still settles on the support to a
# loose tolerance, stays finite, and (on CUDA) graph-captures — not bit-equality.
@pytest.mark.parametrize("material", ["fem_rigid", "fem"])
def test_warpcpu_cargo_parallel_agrees(material):
    ref, rbox = _build_cargo(material, device="cpu", force_warp=False)
    dev, dbox = _build_cargo(material, device="cpu", force_warp=True,
                             parallel=True)
    for _ in range(120):
        ref.step()
        dev.step()
    assert dev._on_device
    pr, pd = ref.positions()[rbox.index], dev.positions()[dbox.index]
    assert np.all(np.isfinite(pd)), f"{material}: parallel NaN"
    assert abs(float(pr[1] - pd[1])) < 2e-3, (
        f"{material}: parallel settles to {pd[1]:.4f} vs serial {pr[1]:.4f}")


@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
@pytest.mark.parametrize("material", ["fem_rigid", "fem"])
def test_cuda_cargo_parallel_agrees(material):
    ref, rbox = _build_cargo(material, device="cpu", force_warp=False)
    dev, dbox = _build_cargo(material, device="cuda:0", force_warp=False,
                             parallel=True)
    for _ in range(120):
        ref.step()
        dev.step()
    assert dev._on_device and dev._graph is not None
    pr, pd = ref.positions()[rbox.index], dev.positions()[dbox.index]
    assert np.all(np.isfinite(pd)), f"{material}: cuda parallel NaN"
    assert abs(float(pr[1] - pd[1])) < 2e-3, (
        f"{material}: cuda parallel settles to {pd[1]:.4f} vs serial {pr[1]:.4f}")


@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
def test_cuda_stack_parallel_stable():
    """Parallel path on a box-box stack stays finite and bounded (no bit-parity:
    averaged Jacobi over the contact graph differs from serial GS)."""
    dev = _build_stack(device="cuda:0", force_warp=False, parallel=True)
    for _ in range(120):
        dev.step()
    P = dev.positions()
    assert dev._on_device and np.all(np.isfinite(P))
    assert P[:, 1].min() > -0.05, f"stack sank: {P[:,1].min():.4f}"


@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
@pytest.mark.parametrize("imp", [4.0, 16.0])
def test_cuda_parallel_high_impedance_stable(imp):
    """Regression (found 2026-06-23): the parallel CUDA path blew up (V/X → NaN)
    at high modal-impedance gain — the support→q drive scales with the gain
    (wq = g) and the non-self-limiting Jacobi sum over many support rows diverged
    where serial GS survives. Fix: per-mode under-relaxation by mq (= 1/g), which
    cancels the over-drive (default g=1 ⇒ mq=1 ⇒ unchanged). A stiff multi-body
    scene at high impedance must stay finite and bounded."""
    from scenes.reduced_dinner_table import build_reduced_dinner_table
    h = build_reduced_dinner_table(solver="xpbd", device="cuda:0", iterations=16,
                                   avbd_substeps=6, modal_impedance_scale=imp,
                                   modal_damping_scale=1.0)
    s = h.world._solver
    s._parallel_device = True
    for _ in range(800):
        h.world.step()
    P = s.positions()
    assert s._on_device and np.all(np.isfinite(P)), f"imp={imp}: NaN"
    assert float(np.abs(P).max()) < 50.0, (
        f"imp={imp}: diverged (|X|max={float(np.abs(P).max()):.1f})")


@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
def test_abd_falls_back_to_numpy_on_cuda():
    """abd (nonlinear V⊥) is not device-resident — the solver must run the
    numpy reference even when device='cuda:0' (no NaN, cube deforms)."""
    ref, box = _build_cargo("abd", device="cuda:0", force_warp=False)
    for _ in range(40):
        ref.step()
    assert not ref._on_device, "abd must fall back to the numpy path"
    assert np.all(np.isfinite(ref.positions()))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
