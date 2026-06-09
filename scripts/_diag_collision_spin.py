#!/usr/bin/env python3
"""Do FALLING objects pick up spurious ANGULAR VELOCITY on collision?

Cleanest isolation: drop a perfectly axis-aligned box FLAT (zero spin) onto the
floor. By symmetry the 4 corner contacts should resolve with ZERO net torque →
|ω| must stay ~0. Any |ω| after impact is a spurious contact artifact (the
parallel corner-impulse resolution not staying symmetric at finite iterations).

Discriminators: coupler ON (deformable support) vs OFF (rigid floor), and an
iteration sweep — to see whether it is the modal coupling or the base AVBD
contact solve, and whether iterations cure it."""
from __future__ import annotations
import argparse
import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, build_support_and_attach, ReducedSceneHandle)


def build(*, device, iters, substeps, mass=50.0, drop=0.3, half=0.08,
          thickness=0.1):
    top = 0.04
    world = AVBDDCRWorld(h=1.0/120.0, device=device,
                         avbd_iterations=iters, avbd_substeps=substeps)
    world.add_floor(floor_y=top, friction=0.5, name="ledge")
    bodies = []
    add = BodyAdder(world, bodies).add
    # perfectly axis-aligned, centred, zero spin
    idx = add("drop", mass, (half, half, half),
              (0.0, top + half + drop, 0.0), (0.4, 0.4, 0.4), "box",
              friction=0.5)
    rs = build_support_and_attach(
        world, bodies, support_length=1.2, support_width=0.8,
        support_thickness=thickness, support_top=top, youngs=1.0e10,
        density=600.0, poisson=0.30, n_modes_global=12, n_modes_local=16,
        contact_zones=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, modal_impedance_scale=1.0,
        modal_damping_scale=1.0, to_eigenbasis=True, modal_static_lp_tau=0.05)
    return ReducedSceneHandle(world=world, rs=rs, impactor_idx=idx,
                              probe_indices=[], bodies=bodies, name="drop")


def run(label, *, device, coupler_off=False, iters=4, substeps=4, n=600):
    h = build(device=device, iters=iters, substeps=substeps)
    w = h.world; b = h.impactor_idx; bod = w.bodies
    if coupler_off:
        w._solver.substep_begin_hook = None
        w._solver.iteration_hook = None
        w._solver.substep_end_hook = None
        w._solver.hooks_device_resident = False
    wm = np.zeros(n); vy = np.zeros(n)
    for k in range(n):
        w.step()
        v = np.asarray(bod[b].velocity, float)
        wm[k] = np.linalg.norm(v[3:]); vy[k] = v[1]
    # impact ≈ first step vy recovers above -0.5 after the fall
    falling = np.where(vy < -0.5)[0]
    imp = int(falling[-1]) + 1 if len(falling) else 40
    peak = float(np.max(wm[imp:min(imp+120, n)]))      # |ω| peak after impact
    late = float(np.max(wm[max(0, n-120):n]))           # |ω| residual
    print(f"  {label:<28} |ω|peak_postimpact={peak:.3e}  |ω|late={late:.3e} "
          f"rad/s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    a = ap.parse_args()
    print("Axis-aligned box dropped FLAT (zero spin) → |ω| MUST be ~0 if "
          "contact is symmetric:\n")
    run("COUPLER ON  it=4", device=a.device, iters=4)
    run("COUPLER OFF it=4 (rigid)", device=a.device, iters=4, coupler_off=True)
    run("COUPLER OFF it=16", device=a.device, iters=16, coupler_off=True)
    run("COUPLER OFF it=4 sub=8", device=a.device, iters=4, substeps=8,
        coupler_off=True)
    print()
    run("CPU COUPLER OFF it=4", device="cpu", iters=4, coupler_off=True)


if __name__ == "__main__":
    main()
