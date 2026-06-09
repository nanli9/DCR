#!/usr/bin/env python3
"""Observe (don't theorize) WHICH bodies slide and how far, in the real scenes.

Logs every dynamic body's horizontal displacement from its start position over
a full run. Reports per-body max horizontal slide + the scene max. Ledge
(user params: thickness 0.1) vs truck, and ledge coupler ON vs OFF — to see
what actually slides and whether it is ledge-specific / coupler-driven."""
from __future__ import annotations
import argparse
import numpy as np

from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_truck import build_reduced_truck


def observe(label, handle, *, coupler_off=False, n=1200):
    w = handle.world; bod = w.bodies
    if coupler_off:
        w._solver.substep_begin_hook = None
        w._solver.iteration_hook = None
        w._solver.substep_end_hook = None
        w._solver.hooks_device_resident = False
    idxs = [b.dcr_idx for b in handle.bodies]
    names = [b.name for b in handle.bodies]
    p0 = {i: np.asarray(bod[i].position, float).copy() for i in idxs}
    horiz_max = {i: 0.0 for i in idxs}
    y_now = {i: 0.0 for i in idxs}
    for k in range(n):
        w.step()
        for i in idxs:
            p = np.asarray(bod[i].position, float)
            d = float(np.hypot(p[0] - p0[i][0], p[2] - p0[i][2]))
            horiz_max[i] = max(horiz_max[i], d)
            y_now[i] = float(p[1])
    print(f"\n{label}")
    for i, nm in zip(idxs, names):
        print(f"   {nm:<12} max_horiz_slide={horiz_max[i]*1e3:8.2f} mm "
              f"final_y={y_now[i]:.4f}")
    smax = max(horiz_max.values())
    who = names[idxs.index(max(horiz_max, key=horiz_max.get))]
    print(f"   → scene max horizontal slide = {smax*1e3:.2f} mm ({who})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=1200)
    a = ap.parse_args()
    print("Horizontal slide from start [mm] per body. Boulder=50kg drop 0.8, "
          "ledge thickness=0.1, wood, it=4/sub=4 (viewer defaults).")
    lk = dict(device=a.device, iterations=4, avbd_substeps=4,
              support_thickness=0.1, youngs=1.0e10, density=600.0,
              impactor_mass=50.0, impactor_drop_height=0.8, to_eigenbasis=True)
    observe("LEDGE coupler ON", build_reduced_ledge(**lk), n=a.n)
    observe("LEDGE coupler OFF", build_reduced_ledge(**lk), coupler_off=True, n=a.n)
    tk = dict(device=a.device, iterations=4, avbd_substeps=4,
              support_thickness=0.06, youngs=1.0e10, density=600.0,
              impactor_mass=40.0, impactor_drop_height=0.7, to_eigenbasis=True)
    observe("TRUCK coupler ON", build_reduced_truck(**tk), n=a.n)


if __name__ == "__main__":
    main()
