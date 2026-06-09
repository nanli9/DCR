#!/usr/bin/env python3
"""What does the boulder VISIBLY do on the reduced-coupled ledge, and do the
pillars ever settle?  (vy alone was sub-micron; check pos/angle p2p + angular.)

Measures, over a long GPU run, per window:
  boulder : |v_lin| std, |omega| std, position peak-to-peak [mm] (x,y,z),
            orientation-angle peak-to-peak [deg]   ← the actually-visible motion
  pillars : mean/max speed, mean y (have they fallen off the pedestal?)
"""
from __future__ import annotations
import argparse
import numpy as np
from scripts._diag_ledge_deepdive import build_ledge


def quat_angle_deg(wxyz):
    w = np.clip(abs(float(wxyz[0])), 0.0, 1.0)
    return np.degrees(2.0 * np.arccos(w))


def run(label, *, with_stack, device, n=2400):
    h = build_ledge(with_stack=with_stack, device=device)
    w = h.world; b = h.impactor_idx; pillars = h.probe_indices; bod = w.bodies
    vlin = np.zeros(n); wmag = np.zeros(n)
    pos = np.zeros((n, 3)); ang = np.zeros(n)
    pil_v = np.zeros(n); pil_y = np.zeros(n)
    for k in range(n):
        w.step()
        v = np.asarray(bod[b].velocity, dtype=float)
        vlin[k] = np.linalg.norm(v[:3]); wmag[k] = np.linalg.norm(v[3:])
        pos[k] = np.asarray(bod[b].position, dtype=float)
        ang[k] = quat_angle_deg(bod[b].orientation)
        if pillars:
            pil_v[k] = max(np.linalg.norm(bod[p].velocity[:3]) for p in pillars)
            pil_y[k] = min(float(bod[p].position[1]) for p in pillars)
    print(f"\n{label}  (device={device})")
    print(f"  {'window':<12}{'|v|std':>10}{'|w|std':>10}"
          f"{'x_ptp_mm':>9}{'y_ptp_mm':>9}{'z_ptp_mm':>9}{'ang_ptp_deg':>12}"
          + (f"{'pilV_mx':>9}{'pilV_mn':>9}{'pilY_mn':>9}" if with_stack else ""))
    for lo, hi in [(120, 300), (600, 900), (1200, 1500), (n - 300, n)]:
        s = slice(lo, hi)
        row = (f"  {f'{lo}-{hi}':<12}{np.std(vlin[s]):>10.2e}{np.std(wmag[s]):>10.2e}"
               f"{np.ptp(pos[s,0])*1e3:>9.3f}{np.ptp(pos[s,1])*1e3:>9.3f}"
               f"{np.ptp(pos[s,2])*1e3:>9.3f}{np.ptp(ang[s]):>12.4f}")
        if with_stack:
            row += (f"{pil_v[s].max():>9.2e}{pil_v[s].mean():>9.2e}"
                    f"{pil_y[s].mean():>9.4f}")
        print(row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=2400)
    a = ap.parse_args()
    print("ledge floor_y=0.04, boulder half=0.08 → rests centre ~0.12 m. "
          "ptp = peak-to-peak (visible wobble). pillars start y≈0.20.")
    run("FULL (stack)   ", with_stack=True, device=a.device, n=a.n)
    run("BOULDER_ONLY   ", with_stack=False, device=a.device, n=a.n)


if __name__ == "__main__":
    main()
