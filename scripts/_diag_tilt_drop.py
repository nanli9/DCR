#!/usr/bin/env python3
"""Asymmetric landing: drop a box with a small initial TILT onto the floor.
Physically it lands on one edge, rocks, and should SETTLE (friction + gravity).
Question: does it settle cleanly, or keep vibrating? And does the deformable
support (coupler ON) AMPLIFY / sustain the post-impact angular wobble vs a
rigid floor (coupler OFF)?

|ω| peak (impact transient) and |ω| late (residual) tell the story."""
from __future__ import annotations
import argparse
import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, build_support_and_attach, ReducedSceneHandle)


def _quat_tilt_wxyz(deg):
    a = np.radians(deg) / 2.0
    return (float(np.cos(a)), 0.0, 0.0, float(np.sin(a)))   # tilt about x


def build(*, device, iters=4, substeps=4, tilt_deg=10.0, mass=8.0, drop=0.3,
          half=0.06, thickness=0.05):
    top = 0.04
    world = AVBDDCRWorld(h=1.0/120.0, device=device,
                         avbd_iterations=iters, avbd_substeps=substeps)
    world.add_floor(floor_y=top, friction=0.5, name="floor")
    bodies = []
    add = BodyAdder(world, bodies).add
    idx = add("drop", mass, (half, half, half),
              (0.0, top + half + drop, 0.0), (0.4, 0.4, 0.4), "box",
              quat=_quat_tilt_wxyz(tilt_deg), friction=0.5)
    rs = build_support_and_attach(
        world, bodies, support_length=1.2, support_width=0.8,
        support_thickness=thickness, support_top=top, youngs=1.0e10,
        density=600.0, poisson=0.30, n_modes_global=12, n_modes_local=16,
        contact_zones=[(0.0, 0.0)], probe_xz=[(0.0, 0.0)],
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, modal_impedance_scale=1.0,
        modal_damping_scale=1.0, to_eigenbasis=True, modal_static_lp_tau=0.05)
    return ReducedSceneHandle(world=world, rs=rs, impactor_idx=idx,
                              probe_indices=[], bodies=bodies, name="tilt")


def ang(wxyz):
    return np.degrees(2*np.arccos(np.clip(abs(float(wxyz[0])),0,1)))


def run(label, *, device, coupler_off=False, lowpass=True, tilt=10.0, n=720):
    h = build(device=device, tilt_deg=tilt)
    w = h.world; b = h.impactor_idx; bod = w.bodies
    w.reduced_coupled_coupler.anchor_static_lowpass = lowpass
    if coupler_off:
        w._solver.substep_begin_hook = None
        w._solver.iteration_hook = None
        w._solver.substep_end_hook = None
        w._solver.hooks_device_resident = False
    wm = np.zeros(n); a = np.zeros(n)
    for k in range(n):
        w.step()
        wm[k] = np.linalg.norm(np.asarray(bod[b].velocity, float)[3:])
        a[k] = ang(bod[b].orientation)
    peak = float(wm[40:160].max())
    mid = float(wm[160:360].max())
    late = float(wm[n-200:n].max())
    print(f"  {label:<30} |ω|peak={peak:.3e} |ω|mid={mid:.3e} "
          f"|ω|late={late:.3e}  final_tilt={a[-1]:.2f}°")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    a = ap.parse_args()
    print("Box dropped with 10° tilt. |ω| should spike at impact then DECAY to "
          "~0 as it settles. Sustained |ω|late = a problem.\n")
    run("COUPLER ON  it=4", device=a.device)
    run("COUPLER OFF it=4 (rigid)", device=a.device, coupler_off=True)
    run("COUPLER ON  it=4 lowpass=off", device=a.device, lowpass=False)
    run("COUPLER ON  it=16", device=a.device)
    print()
    run("CPU COUPLER ON it=4", device="cpu")
    run("CPU COUPLER OFF it=4 (rigid)", device="cpu", coupler_off=True)


if __name__ == "__main__":
    main()
