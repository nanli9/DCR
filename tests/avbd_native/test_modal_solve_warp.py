"""Parity: the warp-cooperative modal solve (k_modal_solve_warp, dim=32) is
bit-faithful to the single-thread reference (k_modal_solve, dim=1).

OPTIMIZATION guard (structure/vectorization only, no math change): the warp
kernel fans the O(r³) partial-pivot Gaussian elimination across one warp's 32
lanes (lane i owns row i, r ≤ 32). Within each column's elimination the rows are
independent, so it performs the SAME fp64 operations in the SAME per-element
order → the modal amplitude update q must match the serial kernel to the bit.
This replaced ~73% of the native step's GPU time (a single fp64 thread, ~310 µs
→ ~50 µs). The solver uses the warp kernel only on CUDA for r ≤ 32; CPU and
r > 32 keep the dim=1 reference exercised here as the ground truth.
"""
from __future__ import annotations

import numpy as np
import pytest
import warp as wp


def _has_cuda() -> bool:
    try:
        wp.init()
        return wp.get_cuda_device_count() > 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _has_cuda(),
                                reason="warp modal solve parity needs CUDA")


def _solve(kernel, dim, r, Hq0, gq0, q0, eps, relax, dev):
    import dcr.avbd._solver.modal_qblock_kernels as MK
    Hq = wp.array(Hq0.copy(), dtype=wp.float64, device=dev)
    gq = wp.array(gq0.copy(), dtype=wp.float64, device=dev)
    dq = wp.zeros(r, dtype=wp.float64, device=dev)
    q = wp.array(q0.copy(), dtype=wp.float64, device=dev)
    q32 = wp.zeros(r, dtype=wp.float32, device=dev)
    kern = getattr(MK, kernel)
    wp.launch(kern, dim=dim,
              inputs=[r, wp.float64(eps), wp.float64(relax), Hq, gq, dq, q, q32],
              device=dev)
    wp.synchronize_device(dev)
    return q.numpy().copy(), q32.numpy().copy()


@pytest.mark.parametrize("r", [1, 2, 8, 16, 21, 24, 31, 32])
def test_warp_solve_bit_identical_to_serial(r):
    dev = "cuda:0"
    rng = np.random.default_rng(1234 + r)
    for _ in range(25):
        A = rng.standard_normal((r, r))
        Hq0 = A @ A.T + r * np.eye(r)          # SPD, well-conditioned
        gq0 = rng.standard_normal(r)
        q0 = rng.standard_normal(r)
        eps, relax = 1e-9, 0.7
        qs, q32s = _solve("k_modal_solve", 1, r, Hq0, gq0, q0, eps, relax, dev)
        qp, q32p = _solve("k_modal_solve_warp", 32, r, Hq0, gq0, q0, eps, relax, dev)
        # bit-identical: same ops, same order
        assert np.array_equal(qs, qp), f"r={r}: fp64 q mismatch {np.abs(qs-qp).max():.3e}"
        assert np.array_equal(q32s, q32p), f"r={r}: fp32 mirror mismatch"
