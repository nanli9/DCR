#!/usr/bin/env python3
"""V2-B profiling: per-step wall time for the device-resident velocity band
vs the V2-A numpy host-round-trip band vs the position band alone, on both
solvers (cuda:0). Prints ms/step and the V2-A/V2-B speedup.

Run: python scripts/run_impulse_port_v2b_profile.py
"""
import time

import numpy as np
import warp as wp

wp.init()
from scenes.reduced_shelf import build_reduced_shelf            # noqa: E402
from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd      # noqa: E402
from dcr.dcr.impulse_port import (                               # noqa: E402
    enable_device_band, enable_substep_band)


def _build(which):
    h = build_reduced_shelf(device="cuda:0")
    h.rs.reset_state()
    if which == "avbd":
        return h.world, h.world.reduced_coupled_coupler
    xh = mirror_to_xpbd(h, h=1 / 120., substeps=4, iterations=4,
                        device="cuda:0")
    return xh.world, xh.coupler


def _timed(which, mode, warm=30, n=200):
    world, c = _build(which)
    if mode == "dev":
        enable_device_band(world, c, eta=1.0)
    elif mode == "np":
        enable_substep_band(world, c, eta=1.0)
    elif mode == "posonly":
        c.device_resident = True                # position band only
    for _ in range(warm):
        world.step()
    wp.synchronize_device("cuda:0")
    t0 = time.perf_counter()
    for _ in range(n):
        world.step()
    wp.synchronize_device("cuda:0")
    return (time.perf_counter() - t0) / n * 1e3   # ms/step


if __name__ == "__main__":
    for which in ("avbd", "xpbd"):
        po = _timed(which, "posonly")
        dv = _timed(which, "dev")
        npb = _timed(which, "np")
        print(f"{which:5s}  pos-only={po:7.3f} ms   V2-B(device)={dv:7.3f} ms"
              f"   V2-A(numpy)={npb:8.3f} ms   speedup={npb / dv:5.1f}x"
              f"   band-overhead={dv - po:+.3f} ms")
