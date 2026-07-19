#!/usr/bin/env python3
"""R3 — end-of-substep complementarity residual vs local iteration budget K.

Plan §6.5, the "how converged is the row, actually?" probe. E-S2 shows the
energy ratio decaying with K; a reviewer is entitled to ask whether that is
convergence of the CONSTRAINT or merely of one scalar. This measures the
constraint directly.

For the support rows the contact conditions are

    C >= 0,   lambda >= 0,   C * lambda = 0                    (Eq. 1)

so a natural scalar residual is the Fischer-Burmeister-style

    res = || min(C, lambda) ||_inf      over the support rows, end of substep

which is 0 exactly at a complementary solution: either the gap is closed
(C = 0) or the row carries no force (lambda = 0). We report the max over the
logged substeps (the worst instant, which is what a starved budget breaks) and
the median (the typical instant).

SCOPE, stated rather than hidden: this is measured on the POSITION-BASED host
only. That is the host the truncation story is about, and it is the one whose
support rows expose both C and lambda in host state (`_support[i].lam` and the
gap expression mirrored from `_project_support`). The augmented-Lagrangian host
solves a penalty/AL form whose "lambda" is not the same object, and the impulse
host is already converged at K=2 (E-S2), so a residual-vs-K curve there is
flat by construction and uninformative. Reporting one number per host without
that caveat would be an apples-to-oranges comparison of exactly the kind R3
exists to remove.

Measurement-only: wraps `_substep_cpu` to read state at the substep boundary
and returns the original value unchanged; the module-level `passivity_gamma`
is forced to 1.0 so the governor cannot perturb the trajectory (the same
neutering R1 uses -- every state write in the enforcement path is guarded by
`if gamma < 1.0`).

Out: out/{complementarity_residual.csv, complementarity_residual.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_complementarity_residual.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                    # noqa: E402
from dcr.avbd.modal_qblock import _quat_to_R as _qR              # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# E-S2's ladder, extended at the top so the residual is seen to bottom out.
K_LIST = [1, 2, 4, 8, 16, 24, 32, 64, 128]
RELAX = 0.7        # PAPER_CONFIG; identical to E-S2 so the curves overlay
SUBSTEPS = 1       # pinned, so K is the only variable (identical to E-S2)


def _gaps_and_lams(sol):
    """(C, lambda) for every support row, end of substep.

    C = corner_y - (y_rest + U_y . q), mirroring `_project_support`
    (solver_xpbd.py:1435-1444) exactly as the E-S3 validity probe does.
    """
    q, X, Q = sol._q, sol._X, sol._Q
    n = len(sol._support)
    C = np.empty(n)
    lam = np.empty(n)
    for i, sc in enumerate(sol._support):
        R = _qR(np.asarray(Q[sc.bi], dtype=np.float64))
        corner_y = float(X[sc.bi][1]) + float((R @ sc.off)[1])
        C[i] = corner_y - (sc.y_rest + float(sc.U_y @ q))
        lam[i] = float(sc.lam)
    return C, lam


def run_cell(scene, K, substeps, relax, nframes, settle=8):
    H = SCENES[scene](device="cpu", iterations=K, avbd_substeps=substeps,
                      solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=False)     # governor OFF for this probe

    res = []
    orig_substep = sol._substep_cpu

    def substep_wrap(h):
        orig_substep(h)                            # unchanged
        C, lam = _gaps_and_lams(sol)
        if C.size:
            # complementarity residual: 0 iff every row has C=0 or lambda=0
            res.append(float(np.abs(np.minimum(C, lam)).max()))

    sol._substep_cpu = substep_wrap
    orig_gamma = _psv_mod.passivity_gamma
    _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0
    try:
        w = H.world
        for _ in range(settle + nframes):
            w.step()
    finally:
        _psv_mod.passivity_gamma = orig_gamma
        sol._substep_cpu = orig_substep

    a = np.asarray(res, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return None
    return dict(res_max=float(a.max()), res_med=float(np.median(a)),
                res_mean=float(a.mean()), n_substeps=int(a.size))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="shelf")
    ap.add_argument("--relax", type=float, default=RELAX)
    ap.add_argument("--substeps", type=int, default=SUBSTEPS)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="complementarity_residual")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### R3 complementarity residual vs K: scene={args.scene} "
          f"substeps={args.substeps} relax={args.relax} "
          f"({platform.machine()}) ###", flush=True)
    print("#   res = ||min(C, lambda)||_inf at end of substep, XPBD host, "
          "governor OFF", flush=True)
    rows = []
    for K in K_LIST:
        m = run_cell(args.scene, K, args.substeps, args.relax, args.nframes)
        if m is None:
            print(f"  K={K:4d}: (no support rows logged)")
            continue
        rows.append(dict(solver="xpbd", scene=args.scene, K=K,
                         substeps=args.substeps, relax=args.relax, **m))
        print(f"  K={K:4d}: max={m['res_max']:.6g}  median={m['res_med']:.6g}"
              f"  n={m['n_substeps']}", flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=[args.scene], solvers=["xpbd"],
        note=("R3 (plan §6.5): end-of-substep complementarity residual "
              "||min(C, lambda)||_inf vs local iteration budget K, XPBD host, "
              "substeps pinned to 1 and relax 0.7 so the ladder overlays E-S2. "
              "Measurement-only (wraps _substep_cpu, returns unchanged; "
              "passivity_gamma forced to 1.0). XPBD only, deliberately: AVBD's "
              "AL multiplier is not the same object and the impulse host is "
              "converged at K=2, so a cross-host residual would be "
              "apples-to-oranges."))
    if len(rows) > 1:
        print(f"\n  residual falls {rows[0]['res_max']:.4g} -> "
              f"{rows[-1]['res_max']:.4g} over K={rows[0]['K']}..{rows[-1]['K']}"
              f"  ({rows[0]['res_max'] / max(rows[-1]['res_max'], 1e-300):.3g}x)")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
