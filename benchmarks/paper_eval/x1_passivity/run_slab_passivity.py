#!/usr/bin/env python3
"""X1e — passivity cell for the SLAB reference scene (matrix row 4).

The slab full-FEM-anchor scene (X3 `scene_and_gt.build_fem_modal_scene`) lives
on the `benchmark` branch; this runner imports that worktree read-only (its
root at --benchmark-root), builds the native arm at the paper configuration,
and evaluates the §15 ledger over the impact + ring window for both hosts:
XPBD with the clamp ON (expected inert at 16×4, as on the other scenes) and
AVBD monitor-only. Reports the ledger invariant `passive()`, activations, and
the net excess — the same cell semantics as the other scenes' passivity row.

Out: benchmarks/paper_eval/x1_passivity/out/slab_passivity.csv
Run: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
       benchmarks/paper_eval/x1_passivity/run_slab_passivity.py \
       [--benchmark-root /private/tmp/claude-501/DCR-benchmark]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark-root",
                    default="/private/tmp/claude-501/DCR-benchmark")
    ap.add_argument("--frames", type=int, default=150)
    args = ap.parse_args()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)

    sys.path.insert(0, args.benchmark_root)
    from benchmarks.paper_eval.x3_ground_truth.scene_and_gt import \
        build_fem_modal_scene                                    # noqa: E402
    from benchmarks.paper_eval.paper_config import (             # noqa: E402
        PAPER_CONFIG, apply_relax, apply_passivity)

    rows = []
    for solver in ("xpbd", "avbd"):
        H = build_fem_modal_scene(
            device="cpu", iterations=PAPER_CONFIG["iterations"],
            avbd_substeps=PAPER_CONFIG["substeps"], solver=solver)
        sol = H.world._solver
        apply_relax(sol, solver)
        sol._modal_symplectic = True
        apply_passivity(sol, solver, enable=True, eta=1.0)
        w = H.world
        for _ in range(8):
            w.step()
        finite = True
        for _ in range(args.frames):
            w.step()
            e = sol.last_modal_KE + sol.last_modal_PE
            if not np.isfinite(e):
                finite = False
                break
        L = sol._psv_ledger
        r = dict(scene="slab", solver=solver, eta=L.eta,
                 passive=bool(L.passive()), holds=bool(L.holds()),
                 n_clamped=int(L.n_clamped), n_steps=int(L.n_steps),
                 cum_gain=float(L.cum_modal_gain),
                 cum_loss=float(L.cum_rigid_loss),
                 max_net_excess=float(L.max_net_excess), finite=finite)
        rows.append(r)
        print(f"  slab {solver}: passive={r['passive']} holds={r['holds']} "
              f"clamp={r['n_clamped']}/{r['n_steps']} "
              f"gain={r['cum_gain']:.4g} loss={r['cum_loss']:.4g} "
              f"net_excess={r['max_net_excess']:.3g}", flush=True)

    with open(os.path.join(out_dir, "slab_passivity.csv"), "w",
              newline="") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        for r in rows:
            wcsv.writerow(r)
    print(f"wrote slab_passivity.csv to {out_dir}/")


if __name__ == "__main__":
    main()
