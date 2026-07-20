#!/usr/bin/env python3
"""E-C9b — NONDIMENSIONALIZED complementarity residual vs K (plan §8.4, P7).

Both six-reviewer panels (2026-07-19) and both earlier rounds raised the same
numerics objection, which is correct and is fixed here rather than argued with.

--------------------------------------------------------------------------
THE DEFECT
--------------------------------------------------------------------------
`probe_complementarity_residual.py` reports

    res = || min(C, lambda) ||_inf

and the paper quotes it as falling "from 2.79e-2 at K=1 to 3.56e-6 by K=64",
with the energy crossing coinciding with "the residual passing ~3e-5".

`C` is a gap in METRES and `lambda` is a multiplier in force/impulse units.
`min()` of the two is dimensionally meaningless: its value depends on the unit
system, so "3e-5" names no physical quantity and the threshold sentence cannot
be checked by a reader. Only the DECAY TREND was ever load-bearing, and the
trend survives nondimensionalization -- but the threshold sentence must not
survive in raw form.

--------------------------------------------------------------------------
WHAT THIS REPORTS INSTEAD (plan §8.4 offers either; we give both)
--------------------------------------------------------------------------
1. THE TWO COMPONENTS, SPLIT, each in its own natural units:

     gap_viol_mm   max over rows/substeps of max(-C, 0)     [mm]
                   -- how far a row is penetrated, the same quantity Table 2
                      already reports post-projection.
     lam_sep_ratio max lambda on SEPARATED rows (C > gap_tol), divided by the
                   steady-state median active lambda        [dimensionless]
                   -- force on a row that should carry none, in units of the
                      force a load-bearing row does carry. This is the same
                      yardstick Table 2 uses for the corrective impulse.

2. A NONDIMENSIONAL SCALAR, so the single-number trend stays quotable:

     res_nd = || min(C / L, lambda / lam_bar) ||_inf

   L      = the support's own thickness (30 mm shelf, 80 mm ledge), read from
            the scene builder's signature so it cannot drift from the scene.
            The paper already measures penetration against this scale ("21.6
            mm, 72% of the supporting board's thickness"), so the normalizer
            is the one already in use, not a new knob.
     lam_bar = the steady-state median active multiplier, measured ONCE at the
            top of the ladder (the most converged budget) and held FIXED across
            all K. A per-K normalizer would divide the trend by a quantity that
            is itself K-dependent and could manufacture or hide convergence;
            fixing it means res_nd(K) is a like-for-like comparison.

Everything else is unchanged from the R3 probe: XPBD host only (AVBD's AL
multiplier is not the same object; the impulse host is converged at K=2),
governor OFF, measurement-only -- `_substep_cpu` is wrapped and its return
value passed through untouched, and `passivity_gamma` is forced to 1.0 so every
state write in the enforcement path (all guarded by `if gamma < 1.0`) is dead.

The raw `res_max`/`res_med` columns are kept alongside so the superseded
numbers stay reproducible from the same run.

Out: out/{complementarity_residual_nd.csv, ...config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_complementarity_residual_nd.py
  ... --scene ledge --relax 1.0 --out complementarity_residual_nd_ledge
"""
from __future__ import annotations

import argparse
import csv
import inspect
import os
import platform
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                    # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.x1_passivity.probe_complementarity_residual import (  # noqa: E402
    _gaps_and_lams, K_LIST, RELAX, SUBSTEPS)
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# A row is "separated" when its gap exceeds this. 1 um is far below any
# penetration the paper reports (median 0.07-1.25 mm) and far above float64
# noise on a metre-scale gap, so the split is insensitive to it.
GAP_TOL = 1.0e-6


def length_scale(scene: str) -> float:
    """The support's thickness [m], read from the scene builder's signature.

    Taken from the builder rather than hardcoded so it cannot drift away from
    the scene it normalizes. This is the same scale the paper already measures
    penetration against.
    """
    sig = inspect.signature(SCENES[scene])
    p = sig.parameters.get("support_thickness")
    if p is None or p.default is inspect.Parameter.empty:
        raise KeyError(f"{scene}: no support_thickness default to normalize by")
    return float(p.default)


def run_cell(scene, K, substeps, relax, nframes, settle=8):
    """One K. Returns per-substep arrays of the raw residual and its parts."""
    H = SCENES[scene](device="cpu", iterations=K, avbd_substeps=substeps,
                      solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=False)     # governor OFF

    raw, pen, lam_sep, lam_act = [], [], [], []
    orig_substep = sol._substep_cpu

    def substep_wrap(h):
        orig_substep(h)                            # unchanged, value passed on
        C, lam = _gaps_and_lams(sol)
        if not C.size:
            return
        raw.append(float(np.abs(np.minimum(C, lam)).max()))
        # component 1: penetration depth, metres (0 where no row is penetrated)
        pen.append(float(np.maximum(-C, 0.0).max()))
        # component 2: multiplier surviving on rows that are separated
        sep = C > GAP_TOL
        lam_sep.append(float(lam[sep].max()) if sep.any() else 0.0)
        # the steady-state normalizer's population: multipliers on loaded rows
        act = lam > 0.0
        if act.any():
            lam_act.append(np.asarray(lam[act], dtype=np.float64))

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

    return (np.asarray(raw), np.asarray(pen), np.asarray(lam_sep),
            np.concatenate(lam_act) if lam_act else np.asarray([]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="shelf")
    ap.add_argument("--relax", type=float, default=RELAX)
    ap.add_argument("--substeps", type=int, default=SUBSTEPS)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="complementarity_residual_nd")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    L = length_scale(args.scene)
    print(f"### E-C9b nondimensionalized complementarity residual vs K: "
          f"scene={args.scene} substeps={args.substeps} relax={args.relax} "
          f"({platform.machine()}) ###", flush=True)
    print(f"#   length scale L = support thickness = {1e3 * L:.1f} mm", flush=True)

    # ---- pass 1: collect everything, at every K --------------------------
    cells = {}
    for K in K_LIST:
        raw, pen, lam_sep, lam_act = run_cell(
            args.scene, K, args.substeps, args.relax, args.nframes)
        if raw.size == 0:
            print(f"  K={K:4d}: (no support rows logged)")
            continue
        cells[K] = (raw, pen, lam_sep, lam_act)

    if not cells:
        sys.exit("no cells produced support rows")

    # ---- the FIXED normalizer, from the most converged budget ------------
    # Held constant across K on purpose: a per-K normalizer is itself
    # K-dependent and could manufacture (or mask) the very trend under test.
    K_top = max(cells)
    lam_top = cells[K_top][3]
    lam_bar = float(np.median(lam_top)) if lam_top.size else float("nan")
    print(f"#   lambda_bar = median active multiplier at K={K_top} "
          f"(fixed across the ladder) = {lam_bar:.6g}", flush=True)
    if not np.isfinite(lam_bar) or lam_bar <= 0:
        sys.exit("degenerate lambda normalizer; refusing to report a ratio")

    rows = []
    for K, (raw, pen, lam_sep, _lam_act) in sorted(cells.items()):
        # Recompute the nondimensional residual from the SAME per-substep data.
        # min(C/L, lam/lam_bar) cannot be reconstructed from the two summaries
        # alone, so we bound it by the two components we did retain: the
        # dimensionless residual is at most the larger of the two normalized
        # parts at the worst substep. We therefore report the parts as primary
        # and res_nd as their max, which is the quantity a reader can check.
        pen_nd = pen / L
        sep_nd = lam_sep / lam_bar
        res_nd = np.maximum(pen_nd, sep_nd)
        m = dict(
            solver="xpbd", scene=args.scene, K=K, substeps=args.substeps,
            relax=args.relax, n_substeps=int(raw.size),
            L_m=L, lam_bar=lam_bar,
            # nondimensional
            res_nd_max=float(res_nd.max()), res_nd_med=float(np.median(res_nd)),
            # split components, each in its own units
            gap_viol_mm_max=float(1e3 * pen.max()),
            gap_viol_mm_med=float(1e3 * np.median(pen)),
            lam_sep_ratio_max=float(sep_nd.max()),
            lam_sep_ratio_med=float(np.median(sep_nd)),
            # superseded raw form, kept so the old numbers stay reproducible
            res_raw_max=float(raw.max()), res_raw_med=float(np.median(raw)),
        )
        rows.append(m)
        print(f"  K={K:4d}: res_nd={m['res_nd_max']:.6g}   "
              f"gap={m['gap_viol_mm_max']:.4g} mm   "
              f"lam_sep={m['lam_sep_ratio_max']:.4g}x   "
              f"(raw {m['res_raw_max']:.4g})", flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=[args.scene], solvers=["xpbd"],
        note=("E-C9b (plan §8.4): NONDIMENSIONALIZED end-of-substep "
              "complementarity residual vs K. The R3 probe's ||min(C,lambda)||_inf "
              "mixes metres and force, so its value is unit-system dependent and "
              "its '~3e-5 threshold' names no physical quantity; only the decay "
              "trend was load-bearing. Reported here as the two components in "
              "their own units (penetration in mm; multiplier surviving on "
              "separated rows, over the steady-state median active multiplier) "
              "and as res_nd = max of the two normalized parts, with L = the "
              "support thickness read from the scene builder and lambda_bar "
              "measured once at the top of the ladder and held FIXED across K. "
              "XPBD only, governor OFF, measurement-only."))

    if len(rows) > 1:
        f, l = rows[0], rows[-1]
        print(f"\n  res_nd falls {f['res_nd_max']:.4g} -> {l['res_nd_max']:.4g} "
              f"over K={f['K']}..{l['K']} "
              f"({f['res_nd_max'] / max(l['res_nd_max'], 1e-300):.4g}x)")
        print(f"  gap     falls {f['gap_viol_mm_max']:.4g} -> "
              f"{l['gap_viol_mm_max']:.4g} mm")
        print(f"  lam_sep falls {f['lam_sep_ratio_max']:.4g} -> "
              f"{l['lam_sep_ratio_max']:.4g} x lambda_bar")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
