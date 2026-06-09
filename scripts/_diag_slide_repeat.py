#!/usr/bin/env python3
"""Why is the ledge sliding different run-to-run with the SAME parameters?

Two hypotheses:
  (A) GPU non-determinism (atomic contact emission → varying float-sum order)
      amplified by the chaotic balanced-pillar stack → each run diverges.
  (B) the staggered-anchor fix (refresh_anchor_each_iter=False, now default)
      calms the surface → less sliding than the old monolithic path.

Run the SAME ledge config N times and report the boulder + max-pillar horizontal
slide per run. GPU staggered ×N (variance?), GPU monolithic ×2 (old path),
CPU staggered ×2 (deterministic?)."""
from __future__ import annotations
import argparse
import numpy as np
from scenes.reduced_ledge import build_reduced_ledge


def one_run(device, refresh, n=900):
    h = build_reduced_ledge(
        device=device, iterations=4, avbd_substeps=4, support_thickness=0.1,
        youngs=1.0e10, density=600.0, impactor_mass=50.0,
        impactor_drop_height=0.8, to_eigenbasis=True)
    h.world.reduced_coupled_coupler.refresh_anchor_each_iter = refresh
    w = h.world; bod = w.bodies
    bi = h.impactor_idx
    pil = h.probe_indices
    p0 = {i: np.asarray(bod[i].position, float).copy()
          for i in [bi] + pil}
    bmax = 0.0; pmax = 0.0; pymin = 9.0
    for _ in range(n):
        w.step()
        bp = np.asarray(bod[bi].position, float)
        bmax = max(bmax, float(np.hypot(bp[0]-p0[bi][0], bp[2]-p0[bi][2])))
        for i in pil:
            pp = np.asarray(bod[i].position, float)
            pmax = max(pmax, float(np.hypot(pp[0]-p0[i][0], pp[2]-p0[i][2])))
            pymin = min(pymin, float(pp[1]))
    return bmax*1e3, pmax*1e3, pymin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=900)
    a = ap.parse_args()
    print("Boulder / max-pillar horizontal slide [mm] over identical runs "
          "(thickness 0.1, boulder 50kg, drop 0.8, it=4/sub=4):\n")

    def block(label, device, refresh, reps):
        rows = [one_run(device, refresh, a.n) for _ in range(reps)]
        b = [r[0] for r in rows]; p = [r[1] for r in rows]
        print(f"{label}")
        for k, r in enumerate(rows):
            fell = "PILLAR_FELL" if r[2] < 0.14 else "on-pedestal"
            print(f"   run{k}: boulder={r[0]:6.3f}mm  maxPillar={r[1]:6.3f}mm  "
                  f"pil_y_min={r[2]:.4f} {fell}")
        print(f"   boulder spread={max(b)-min(b):.3f}mm  "
              f"pillar spread={max(p)-min(p):.3f}mm\n")

    block("GPU staggered (current default) ×4", a.device, False, 4)
    block("GPU monolithic (old pre-fix path) ×2", a.device, True, 2)
    block("CPU staggered ×2 (determinism check)", "cpu", False, 2)


if __name__ == "__main__":
    main()
