#!/usr/bin/env python3
"""Decay profile of the boulder vibration in the reduced-coupled ledge scene.

Follow-up to `_diag_reduced_ledge_boulder.py`, which showed COUPLER_OFF is
EXACTLY dead-still (so the vibration is the modal coupling, not base AVBD) but
that the late-window jitter is tiny (vy~1e-5 m/s, 0 sign-flips). Question now:
is the perceptible motion a DECAYING post-impact transient (physical ring-down,
expected) or a SUSTAINED limit cycle (artifact)? And does modal damping /
substeps act as a lever?

Prints vy_std + |q_s| + |q_d| (the visible ring) per time window so the decay
envelope is visible. Impact lands ~step 48 (0.8 m drop @ h=1/120)."""
from __future__ import annotations

import numpy as np

from scenes.reduced_ledge import build_reduced_ledge


def run(label, *, iters=4, substeps=4, damping=1.0, coupler_off=False, n=900):
    handle = build_reduced_ledge(
        device="cpu", iterations=iters, avbd_substeps=substeps,
        youngs=1.0e10, density=600.0, modal_damping_scale=damping)
    world = handle.world
    cp = world.reduced_coupled_coupler
    if coupler_off:
        world._solver.substep_begin_hook = None
        world._solver.iteration_hook = None
        world._solver.substep_end_hook = None
        world._solver.hooks_device_resident = False

    b = handle.impactor_idx
    bod = world.bodies
    vy = np.zeros(n); qs = np.zeros(n); qd = np.zeros(n)
    for k in range(n):
        world.step()
        vy[k] = float(bod[b].velocity[1])
        if not coupler_off:
            qs[k] = float(np.linalg.norm(cp.rs.q_s))
            qd[k] = float(np.linalg.norm(cp.rs.q_d))

    wins = [("impact 48-120", 48, 120), ("ring 120-300", 120, 300),
            ("mid 300-540", 300, 540), ("late 540-720", 540, 720),
            ("tail 720-900", 720, 900)]
    print(f"\n{label}")
    print(f"  {'window':<16}{'vy_std':>11}{'vy_max':>11}{'flips':>7}"
          f"{'|q_s|mean':>11}{'|q_d|mean':>11}")
    for nm, lo, hi in wins:
        seg = vy[lo:hi]
        nz = seg[np.abs(seg) > 1e-9]
        fl = int(np.sum(np.diff(np.sign(nz)) != 0)) if len(nz) > 1 else 0
        print(f"  {nm:<16}{np.std(seg):>11.2e}{np.max(np.abs(seg)):>11.2e}"
              f"{fl:>7d}{qs[lo:hi].mean():>11.2e}{qd[lo:hi].mean():>11.2e}")


def main():
    run("FULL (iters=4,sub=4,damp=1)", )
    run("COUPLER_OFF (rigid floor)   ", coupler_off=True)
    run("DAMP=4 (4x modal damping)   ", damping=4.0)
    run("SUBSTEPS=8                  ", substeps=8)


if __name__ == "__main__":
    main()
