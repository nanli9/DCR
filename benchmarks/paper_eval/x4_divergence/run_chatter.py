#!/usr/bin/env python3
"""X4 — solver-divergence: does XPBD ring because its contact CHATTERS?

ISOLATED benchmark. The audit found AVBD and XPBD produce very different modal
rings on the same scene. Hypothesis (memory `xpbd-vs-avbd-modal-ring-mechanism`):
the difference is in the HOST contact behaviour — XPBD's impactor rebounds many
times (chatter), re-exciting the mode each landing, while AVBD's hits once. This
script quantifies the impactor rebound count per solver and correlates it with the
slab-ring energy, at PAPER_CONFIG, using the energy-loop probe READ-ONLY.

It also logs the ledge/AVBD dead-coupling case (two-way 0.59×) alongside its ring
energy, to separate "no ring" from "ring present but not transferred".

Out: benchmarks/paper_eval/x4_divergence/out/{chatter.csv} + manifest
Run: .venv/bin/python benchmarks/paper_eval/x4_divergence/run_chatter.py
"""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scripts.probe_native_energy_loop import run, loop_metrics, _count_peaks
from benchmarks.paper_eval.paper_config import (
    PAPER_CONFIG, relaxed_builder, write_manifest,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}


def count_rebounds(Fimp_series):
    """Impactor rebounds = distinct force-spike bursts. Fimp_series is (frames,4);
    sum corners, count peaks above 5% of the max (each burst = one re-contact)."""
    fsum = np.asarray(Fimp_series).sum(axis=1)
    return _count_peaks(fsum, rel=0.05)


def main():
    os.makedirs(OUT, exist_ok=True)
    it, su = PAPER_CONFIG["iterations"], PAPER_CONFIG["substeps"]
    nf = PAPER_CONFIG["n_frames_energy"]
    print("### X4 chatter ↔ ring correlation @ PAPER_CONFIG ###", flush=True)
    rows = []
    for scene, base in SCENES.items():
        for solver in ("xpbd", "avbd"):
            fn = relaxed_builder(base, solver)      # pin relax 0.7
            rec2 = run(fn, solver, iterations=it, substeps=su, n_frames=nf,
                       freeze_qdot=False, symplectic=True)
            rec1 = run(fn, solver, iterations=it, substeps=su, n_frames=nf,
                       freeze_qdot=True, symplectic=True)
            m2, m1 = loop_metrics(rec2), loop_metrics(rec1)
            rebounds = count_rebounds(rec2["Fimp"])
            twoway = (m2["ErestKE_peak"] / m1["ErestKE_peak"]
                      if m1["ErestKE_peak"] > 1e-12 else float("inf"))
            rows.append(dict(
                scene=scene, solver=solver,
                impactor_rebounds=rebounds,
                slab_ring_mJ=m2["Eslab_peak"] * 1e3,
                slab_rings=m2["slab_rings"],
                Fimp_peak_N=m2["Fimp_peak"],
                twoway_ratio=twoway,
                objKE_mJ=m2["ErestKE_peak"] * 1e3))
            print(f"  {scene:7s}/{solver}: rebounds={rebounds:2d}  "
                  f"ring={m2['Eslab_peak']*1e3:8.1f}mJ  Fimp_peak={m2['Fimp_peak']:6.0f}N  "
                  f"two-way={twoway:6.2f}x  objKE={m2['ErestKE_peak']*1e3:6.1f}mJ",
                  flush=True)

    keys = ["scene", "solver", "impactor_rebounds", "slab_ring_mJ", "slab_rings",
            "Fimp_peak_N", "twoway_ratio", "objKE_mJ"]
    with open(os.path.join(OUT, "chatter.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.4g}" if isinstance(r[k], float) else r[k])
                        for k in keys})
    write_manifest(OUT, "chatter.csv", scenes=list(SCENES), solvers=["xpbd", "avbd"],
                   note="impactor rebound count vs slab-ring energy; PAPER_CONFIG")

    # headline correlation across all scene-solver rows
    reb = np.array([r["impactor_rebounds"] for r in rows], float)
    ring = np.array([r["slab_ring_mJ"] for r in rows], float)
    if reb.std() > 0 and ring.std() > 0:
        c = float(np.corrcoef(reb, ring)[0, 1])
        print(f"\ncorr(impactor rebounds, slab ring energy) = {c:+.2f} "
              f"across {len(rows)} scene-solver runs")
    xp = np.mean([r["impactor_rebounds"] for r in rows if r["solver"] == "xpbd"])
    av = np.mean([r["impactor_rebounds"] for r in rows if r["solver"] == "avbd"])
    print(f"mean impactor rebounds: XPBD={xp:.1f}  AVBD={av:.1f}")
    print(f"wrote chatter.csv to {OUT}/")


if __name__ == "__main__":
    main()
