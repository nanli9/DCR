#!/usr/bin/env python3
"""A/B the rocking fix: refresh_anchor_each_iter True (legacy monolithic) vs
False (staggered — anchor seeded once per substep, held through iterations).

Measures the boulder's sustained ROCK (late ang_ptp / |w|std), plus guards
against regressions: boulder settle height (drift), static sag |q_s|, and the
post-impact RING. Both GPU and CPU."""
from __future__ import annotations
import argparse
import numpy as np
from scripts._diag_ledge_deepdive import build_ledge


def quat_angle_deg(wxyz):
    w = np.clip(abs(float(wxyz[0])), 0.0, 1.0)
    return np.degrees(2.0 * np.arccos(w))


def run(device, refresh, n=2400):
    h = build_ledge(with_stack=True, device=device)
    cp = h.world.reduced_coupled_coupler
    cp.refresh_anchor_each_iter = bool(refresh)
    w = h.world; b = h.impactor_idx; bod = w.bodies
    wmag = np.zeros(n); ang = np.zeros(n); ypos = np.zeros(n)
    vy = np.zeros(n); qs = np.zeros(n)
    for k in range(n):
        w.step()
        v = np.asarray(bod[b].velocity, float)
        wmag[k] = np.linalg.norm(v[3:]); vy[k] = v[1]
        ang[k] = quat_angle_deg(bod[b].orientation)
        ypos[k] = float(bod[b].position[1])
        qs[k] = float(np.linalg.norm(cp.rs.q_s))

    def W(lo, hi):
        return (np.std(wmag[lo:hi]), np.ptp(ang[lo:hi]), np.std(vy[lo:hi]))
    rw, ra, rv = W(120, 300)
    lw, la, lv = W(n - 600, n)
    tag = "LEGACY(refresh)" if refresh else "STAGGERED(fix)"
    print(f"  [{device:>6}] {tag:<16} "
          f"RING |w|std={rw:.2e} ang_ptp={ra:6.3f}° | "
          f"LATE |w|std={lw:.2e} ang_ptp={la:6.3f}° vy_std={lv:.2e} | "
          f"y_settle={ypos[n-600:n].mean():.5f}m |q_s|={qs[n-600:n].mean():.2e}")
    return la, lw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=2400)
    a = ap.parse_args()
    print(f"Ledge boulder rock — LATE = last 600 steps. y_settle≈0.12 m "
          f"expected (drift guard). n={a.n}\n")
    for dev in [a.device, "cpu"]:
        la_leg, lw_leg = run(dev, True, a.n)
        la_fix, lw_fix = run(dev, False, a.n)
        r = la_fix / la_leg if la_leg else float("nan")
        print(f"  → [{dev}] staggered ang_ptp is {r*100:.0f}% of legacy "
              f"({'IMPROVED' if r < 0.7 else 'no clear gain'})\n")


if __name__ == "__main__":
    main()
