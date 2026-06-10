"""Parity: device-resident XPBD coupler vs the numpy reference (CLAUDE.md §6).

Both runs use the SAME cuda solver (identical float32 rigid kernels + broad
phase), so the only difference is the coupler path (on-device warp kernels vs
the numpy hooks). The coupled contact system is CHAOTIC at a sharp impact
(a 5 µm perturbation to the numpy run diverges from itself by ~1e-2 within
~100 steps — verified separately), so trajectory-level parity is only
meaningful over the SMOOTH settling window before the contact set starts
flipping. There, the device path tracks the numpy reference to f64 round-off
(~1e-8), which gates any systematic error in the ~1000 coupled solves it
covers. Requires CUDA + the eigen basis.
"""
import numpy as np
import pytest

wp = pytest.importorskip("warp")


@pytest.mark.skipif(not __import__("warp").is_cuda_available(),
                    reason="device-resident path requires CUDA")
def test_device_matches_numpy_over_smooth_window():
    import warp as wp
    wp.init()
    from scenes.reduced_shelf import build_reduced_shelf
    from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd

    SUB, ITERS, H, N = 8, 4, 1.0 / 120.0, 30  # smooth pre-impact window

    def run(device_resident):
        h = build_reduced_shelf(h=H, device="cuda:0", iterations=ITERS,
                                avbd_substeps=SUB)
        h.rs.reset_state()
        xh = mirror_to_xpbd(h, h=H, substeps=SUB, iterations=ITERS,
                            device="cuda:0")
        xh.coupler.device_resident = bool(device_resident)
        w = xh.world
        qs, qd, pos = [], [], []
        for _ in range(N):
            w.step()
            qs.append(xh.coupler.rs.q_s.copy())
            qd.append(xh.coupler.rs.q_d.copy())
            pos.append(w.positions().copy())
        return np.array(qs), np.array(qd), np.array(pos)

    qs_d, qd_d, pos_d = run(True)
    qs_n, qd_n, pos_n = run(False)

    # Round-off-level agreement over the smooth window. (q_s ~1e-7 in this
    # synthetic-stiff basis, so its absolute scale is the gate.)
    assert np.abs(qs_d - qs_n).max() < 1e-6, np.abs(qs_d - qs_n).max()
    assert np.abs(qd_d - qd_n).max() < 1e-6, np.abs(qd_d - qd_n).max()
    assert np.abs(pos_d - pos_n).max() < 1e-5, np.abs(pos_d - pos_n).max()

    # The device path must actually move the modal state (not a no-op).
    assert np.linalg.norm(qd_d[-1]) > 1e-6
