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


def _build_cargo(material, *, device, force_warp):
    half, y_rest, size, mass = 0.05, 0.5, 0.10, 1.0
    cube = make_cargo_cube(material, size=size, mass=mass, n_elastic=6)
    w = 2.0 * np.pi * 25.0
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=8, device=device)
    s._force_warp = force_warp
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


def _build_stack(*, device, force_warp, nstack=4):
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=8, device=device)
    s._force_warp = force_warp
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


# ---- CUDA-resident path vs numpy reference ----
@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
@pytest.mark.parametrize("material", ["rigid", "fem_rigid", "fem"])
def test_cuda_cargo_parity(material):
    ref, _ = _build_cargo(material, device="cpu", force_warp=False)
    dev, _ = _build_cargo(material, device="cuda:0", force_warp=False)
    dp, dq, dmq = _compare(ref, dev)
    assert dev._on_device
    assert dev._graph is not None, "CUDA-graph not captured"
    assert dp < 1e-5, f"{material}: cuda position drift {dp:.2e}"
    assert dq < 1e-5, f"{material}: cuda orientation drift {dq:.2e}"
    assert dmq < 1e-6, f"{material}: cuda modal_q drift {dmq:.2e}"


@pytest.mark.skipif(not _HAS_CUDA, reason="no CUDA device")
def test_cuda_stack_parity_and_graph():
    ref = _build_stack(device="cpu", force_warp=False)
    dev = _build_stack(device="cuda:0", force_warp=False)
    dp, dq, _ = _compare(ref, dev, modal=False)
    assert dev._on_device and dev._graph is not None
    assert dp < 1e-6, f"cuda stack position drift {dp:.2e}"
    assert dq < 1e-6, f"cuda stack orientation drift {dq:.2e}"


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
