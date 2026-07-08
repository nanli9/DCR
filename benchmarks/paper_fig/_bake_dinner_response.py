#!/usr/bin/env python3
"""One-time bake: join dinner dy_max (vendored JSON) with the scene's static body
positions to produce a plot-ready CSV (distance from drop point per body per arm).

The vendored dinner_results.json carries dy_max per body per arm but not the body
rest positions; those are deterministic from the dinner scene builder. This bakes
data/dinner_response.csv so fig_dinner_response.py reads only committed data.
Run once: .venv/bin/python benchmarks/paper_fig/_bake_dinner_response.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from scenes.reduced_dinner_table import build_reduced_dinner_table

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ARMS = ["native_rigid", "native_cargo", "gt"]


def main():
    # static body rest positions (x,z) by name — independent of the drop point
    handle = build_reduced_dinner_table(device="cpu")
    sol = handle.world._solver
    idx = {b.name: int(handle.world._descs[b.dcr_idx].avbd_body.index)
           for b in handle.bodies}
    P0 = sol.positions()
    xz = {n: (float(P0[i][0]), float(P0[i][2])) for n, i in idx.items()}

    results = json.load(open(os.path.join(DATA, "dinner_results.json")))
    rows = []
    for di, entry in enumerate(results):
        drop = entry["drop_xz"]
        bodies = set()
        for arm in ARMS:
            bodies |= set(entry.get(arm, {}).get("dy_max", {}).keys())
        for n in sorted(bodies):
            if n not in xz or "pot" in n or "impact" in n:
                continue                       # skip the impactor / unplaced
            dist = float(np.hypot(xz[n][0] - drop[0], xz[n][1] - drop[1]))
            row = dict(drop_idx=di, drop_x=drop[0], drop_z=drop[1], body=n,
                       dist_m=dist)
            for arm in ARMS:
                v = entry.get(arm, {}).get("dy_max", {}).get(n)
                row[arm + "_mm"] = (float(v) * 1e3) if v is not None else ""
            rows.append(row)

    keys = ["drop_idx", "drop_x", "drop_z", "body", "dist_m",
            "native_rigid_mm", "native_cargo_mm", "gt_mm"]
    with open(os.path.join(DATA, "dinner_response.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.5g}" if isinstance(r[k], float) else r[k])
                        for k in keys})
    print(f"wrote data/dinner_response.csv ({len(rows)} body-rows, "
          f"{len(results)} drop points)")


if __name__ == "__main__":
    main()
