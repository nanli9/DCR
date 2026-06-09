#!/usr/bin/env python3
"""Direct test: does a COUPLER-TRACKED body keep its FLOOR FRICTION?

A single box rests on the ledge floor and is given a horizontal kick vx0. With
floor μ=0.5 it should decelerate at a≈μg≈4.9 m/s² (stop in ~0.2 s for vx0=1).
If the coupler GLIDES it (vx ~ constant), the coupled iteration is dropping the
floor friction (CONTACT_TANGENT_6DOF) rows for tracked bodies — it only solves
FLOOR_CONTACT_6DOF (normal). Compare coupler ON vs OFF (rigid floor)."""
from __future__ import annotations
import argparse
import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, build_support_and_attach, ReducedSceneHandle)


def build(*, device, mass=50.0, fric=0.5, vx0=1.0, thickness=0.1):
    top = 0.04
    world = AVBDDCRWorld(h=1.0 / 120.0, device=device,
                         avbd_iterations=8, avbd_substeps=4)
    world.add_floor(floor_y=top, friction=fric, name="ledge")
    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    br = 0.08
    idx = add("slider", mass, (br, br, br), (0.0, top + br + 1e-3, 0.0),
              (0.4, 0.4, 0.4), "box", friction=fric, vel=(vx0, 0.0, 0.0))
    rs = build_support_and_attach(
        world, bodies, support_length=1.2, support_width=0.8,
        support_thickness=thickness, support_top=top, youngs=1.0e10,
        density=600.0, poisson=0.30, n_modes_global=12, n_modes_local=16,
        contact_zones=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, modal_impedance_scale=1.0,
        modal_damping_scale=1.0, to_eigenbasis=True, modal_static_lp_tau=0.05)
    return ReducedSceneHandle(world=world, rs=rs, impactor_idx=idx,
                              probe_indices=[], bodies=bodies, name="slide")


def run(label, *, device, coupler_off=False, vx0=1.0, n=240):
    h = build(device=device, vx0=vx0)
    w = h.world; b = h.impactor_idx; bod = w.bodies
    if coupler_off:
        w._solver.substep_begin_hook = None
        w._solver.iteration_hook = None
        w._solver.substep_end_hook = None
        w._solver.hooks_device_resident = False
    vx = np.zeros(n); x = np.zeros(n)
    for k in range(n):
        w.step()
        vx[k] = float(bod[b].velocity[0]); x[k] = float(bod[b].position[0])
    # Deceleration over the first 0.25 s (30 steps) while still moving.
    seg = vx[:30]
    a = float((seg[0] - seg[-1]) / (29 / 120.0)) if len(seg) > 1 else 0.0
    stop_k = next((k for k in range(n) if abs(vx[k]) < 0.02), -1)
    print(f"  {label:<26} vx0={vx0:.2f} vx@0.1s={vx[12]:+.3f} "
          f"vx@0.25s={vx[29]:+.3f} vx@0.5s={vx[59]:+.3f} | "
          f"decel≈{a:5.2f} m/s² (μg≈4.9) | "
          f"stop@={'never' if stop_k<0 else f'{stop_k/120:.2f}s'} | "
          f"glide_dist={x[-1]-x[0]:+.3f}m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    a = ap.parse_args()
    print("Box kicked at vx0 on the ledge floor (μ=0.5 → should stop in ~0.2 s):\n")
    run("COUPLER ON (tracked)", device=a.device)
    run("COUPLER OFF (rigid)", device=a.device, coupler_off=True)


if __name__ == "__main__":
    main()
