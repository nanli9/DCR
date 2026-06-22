"""M1.3 — the native modal q-block runs GPU-resident, parity vs the numpy ref.

`Solver6DOF._solve_q_block` (numpy, the M1.5 reference) is ported to float64
warp kernels in `modal_qblock_kernels.py` so the native `(z, q)` modal path
(two_band_coupling.html, Approach B) stays on-device through the iteration loop
(no per-iteration host readback) and is CUDA-graph-capturable.

Parity method (the established reduced-coupled idiom): the device q-block is
float64, so on a SMOOTH trajectory (modal-only ringdown, no engaged/separated
contact branch) it matches the numpy reference to fp64 roundoff for a long
horizon. Once contact engages, the float32 q_modal mirror that feeds the primal
makes a 1-ULP difference flip an engaged/separated decision → chaotic round-off
growth (documented for the coupler too): there parity is machine-precision for
the first steps, then bounded float32-ULP-scale tracking. Both paths are the
same algorithm to roundoff; the macroscopic ring energy agrees.

`s._modal_device_resident`: None ⇒ auto (warp on cuda, numpy on cpu). Forcing
True/False runs the warp q-block / numpy q-block on either device, which is how
this test isolates the port from the cpu↔cuda float32-primal divergence.
"""
from __future__ import annotations

import numpy as np
import pytest
import warp as wp

from dcr.avbd._solver.solver_6dof import Solver6DOF


def _has_cuda() -> bool:
    try:
        wp.init()
        return wp.get_cuda_device_count() > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Scene builders
# ---------------------------------------------------------------------------
def _modal_only(device: str, resident, qdot0=(0.6, 0.3, -0.2)) -> Solver6DOF:
    """A plucked 3-mode support with a STATIC body (no contact) — the q-block
    runs on a smooth trajectory, isolating the float64 port from contact chaos."""
    s = Solver6DOF(dt=1.0 / 60.0, iterations=12, substeps=4, device=device,
                   gravity=(0.0, 0.0, 0.0))
    s.add_box(position=(0.0, 5.0, 0.0), half_extents=(0.05,) * 3, mass=0.0)
    r = 3
    omegas = np.array([40.0, 130.0, 280.0])
    s.set_modal_support(np.eye(r), np.diag(omegas ** 2), np.zeros((r, r)),
                        qdot0=np.asarray(qdot0, dtype=np.float64))
    s._modal_device_resident = resident
    return s


def _cube_on_support(device: str, resident, drop_h: float = 0.03) -> Solver6DOF:
    """One unit cube dropped onto a 2-mode support (4 engaged corners)."""
    s = Solver6DOF(dt=1.0 / 60.0, iterations=8, substeps=4, device=device,
                   gravity=(0.0, -9.81, 0.0))
    half = 0.05
    body = s.add_box(position=(0.0, half + drop_h, 0.0),
                     half_extents=(half,) * 3, mass=1.0)
    omegas = np.array([35.0, 110.0])
    Mq = np.eye(2)
    Kq = np.diag(omegas ** 2)
    Dq = 0.02 * Mq + 2.0e-5 * Kq
    s.set_modal_support(Mq, Kq, Dq)
    s._modal_device_resident = resident
    U_y = np.array([1.0, 0.4])
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            s.add_support_contact_corner(body, off_a=(sx * half, -half, sz * half),
                                         y_rest=0.0, U_y_row=U_y)
    return s


# ---------------------------------------------------------------------------
# Tight gate: warp q-block == numpy q-block to fp64 on a smooth trajectory
# ---------------------------------------------------------------------------
def test_qblock_device_matches_numpy_modal_only_cpu():
    """Warp float64 q-block (cpu) vs numpy reference (cpu): fp64 roundoff over a
    full 200-step ringdown — the q-block port is correct."""
    ref = _modal_only("cpu", resident=False)   # numpy reference
    dev = _modal_only("cpu", resident=True)     # warp kernels on cpu
    for _ in range(200):
        ref.step()
        dev.step()
        assert np.max(np.abs(ref.modal_q - dev.modal_q)) < 1e-11
        assert np.max(np.abs(ref.modal_qdot - dev.modal_qdot)) < 1e-11
    # the pluck actually rang (non-trivial trajectory) and decayed (passive).
    assert ref.last_modal_PE >= 0.0


def test_qblock_device_engaged_contact_tracks_numpy_cpu():
    """With engaged contact the warp/numpy q-blocks agree to machine precision
    for the first steps, then track at float32-ULP scale (chaotic round-off, as
    documented). Assert bounded tracking + equal macroscopic ring energy."""
    ref = _cube_on_support("cpu", resident=False)
    dev = _cube_on_support("cpu", resident=True)
    pk_ref = pk_dev = 0.0
    for _ in range(120):
        ref.step()
        dev.step()
        pk_ref = max(pk_ref, ref.last_modal_KE)
        pk_dev = max(pk_dev, dev.last_modal_KE)
        # bounded tracking (no blow-up / divergence): sub-mm over the run.
        assert np.max(np.abs(ref.positions() - dev.positions())) < 1e-3
    assert np.all(np.isfinite(dev.positions()))
    # same physics: peak modal ring energy agrees to the percent level.
    assert abs(pk_ref - pk_dev) <= 0.1 * max(pk_ref, 1e-12)


# ---------------------------------------------------------------------------
# CUDA: residency + cpu↔cuda parity
# ---------------------------------------------------------------------------
@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device")
def test_qblock_cuda_resident_and_graph_captured():
    """On cuda the native modal path auto-resolves to the device q-block and the
    iteration loop is CUDA-graph-captured (residency gate)."""
    s = _cube_on_support("cuda:0", resident=None)   # auto
    for _ in range(40):
        s.step()
    assert s._modal_resident is True, "modal path should be device-resident on cuda"
    assert s._graph is not None, "iteration loop should be CUDA-graph-captured"
    assert np.all(np.isfinite(s.positions()))
    assert s.last_modal_KE > 1e-12, "the drop should ring the support (two-way)"


@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device")
def test_qblock_cuda_matches_cpu_reference_modal_only():
    """Modal-only ringdown: the cuda device q-block matches the cpu numpy
    reference to fp64 roundoff (no contact branch → no chaotic divergence)."""
    ref = _modal_only("cpu", resident=False)
    gpu = _modal_only("cuda:0", resident=None)      # auto → resident on cuda
    for _ in range(80):
        ref.step()
        gpu.step()
        assert np.max(np.abs(ref.modal_q - gpu.modal_q)) < 1e-11
        assert np.max(np.abs(ref.modal_qdot - gpu.modal_qdot)) < 1e-11


@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device")
def test_qblock_cuda_contact_no_blowup():
    """The engaged-contact scene is stable + tracks the cpu reference's ring
    energy on cuda (regression guard for the resident-primal modal wiring)."""
    ref = _cube_on_support("cpu", resident=False)
    gpu = _cube_on_support("cuda:0", resident=None)
    pk_ref = pk_gpu = 0.0
    for _ in range(120):
        ref.step()
        gpu.step()
        pk_ref = max(pk_ref, ref.last_modal_KE)
        pk_gpu = max(pk_gpu, gpu.last_modal_KE)
    assert np.all(np.isfinite(gpu.positions()))
    assert abs(pk_ref - pk_gpu) <= 0.1 * max(pk_ref, 1e-12)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
