#!/usr/bin/env python3
"""Why does the LEDGE scene suffer the boulder buzz most, while dinner/truck/
shelf look OK?  Compare the impactor's post-impact ring + late residual across
all four reduced-coupled scenes, with the same viewer presets, on GPU.

For each scene also report support-coupling descriptors that could explain a
difference: r (modes), max |U_y| at the impactor contact (free-end vs centre),
static sag |q_s|, and the impactor mass.
"""
from __future__ import annotations
import argparse
import numpy as np

from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge

# (youngs, density) for the viewer material presets.
WOOD = (1.0e10, 600.0)
PLASTIC = (1.0e9, 1200.0)


def builders(device):
    return {
        "dinner": lambda: build_reduced_dinner_table(
            device=device, iterations=4, avbd_substeps=4, table_thickness=0.03,
            youngs=WOOD[0], density=WOOD[1], pot_mass=8.0, pot_drop_height=0.5,
            to_eigenbasis=True),
        "truck": lambda: build_reduced_truck(
            device=device, iterations=4, avbd_substeps=4, support_thickness=0.06,
            youngs=WOOD[0], density=WOOD[1], impactor_mass=40.0,
            impactor_drop_height=0.7, to_eigenbasis=True),
        "shelf": lambda: build_reduced_shelf(
            device=device, iterations=4, avbd_substeps=4, support_thickness=0.03,
            youngs=PLASTIC[0], density=PLASTIC[1], impactor_mass=6.0,
            impactor_drop_height=0.5, to_eigenbasis=True),
        "ledge": lambda: build_reduced_ledge(
            device=device, iterations=4, avbd_substeps=4, support_thickness=0.08,
            youngs=WOOD[0], density=WOOD[1], impactor_mass=50.0,
            impactor_drop_height=0.8, to_eigenbasis=True),
    }


def quat_angle_deg(wxyz):
    w = np.clip(abs(float(wxyz[0])), 0.0, 1.0)
    return np.degrees(2.0 * np.arccos(w))


def run(name, build, n=1500):
    h = build()
    w = h.world; b = h.impactor_idx; bod = w.bodies; rs = h.rs
    m_imp = float(bod[b].mass) if np.isfinite(bod[b].mass) else -1.0
    wmag = np.zeros(n); ang = np.zeros(n)
    for k in range(n):
        w.step()
        wmag[k] = float(np.linalg.norm(np.asarray(bod[b].velocity, float)[3:]))
        ang[k] = quat_angle_deg(bod[b].orientation)

    def win(lo, hi):
        return np.std(wmag[lo:hi]), np.ptp(ang[lo:hi])     # |w|std, ang_ptp[deg]

    uy_max = float(np.abs(rs.U_points[:, 1, :]).max()) if rs.U_points.shape[0] else 0.0
    qs = float(np.linalg.norm(rs.q_s)); r = int(rs.r)
    rw, ra = win(120, 300); lw, la = win(max(0, n - 300), n)
    print(f"{name:<8} m_imp={m_imp:>6.1f}kg r={r:>3d} maxUy={uy_max:>7.2e} "
          f"|q_s|={qs:>8.2e} | RING |w|std={rw:.2e} ang_ptp={ra:>7.3f}deg "
          f"| LATE |w|std={lw:.2e} ang_ptp={la:>7.3f}deg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=1500)
    a = ap.parse_args()
    print("RING=120-300 (post-impact), LATE=last 300 steps. y_ptp = boulder/"
          "impactor vertical peak-to-peak [mm] (visible wobble).\n")
    bs = builders(a.device)
    for name in ["dinner", "truck", "shelf", "ledge"]:
        try:
            run(name, bs[name], n=a.n)
        except Exception as e:
            print(f"{name:<8} FAILED {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
