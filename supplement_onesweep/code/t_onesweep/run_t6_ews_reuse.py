#!/usr/bin/env python3
"""T6 -- E-WS 24-cell reuse (system-level corroboration; NO rerun).

Plan section T6 (`scratchpad/wf1/plan.md`), theory note
`scratchpad/onesweep_theory_note.md` (Result R1/R2). This script does NOT run the
solver. It reads the frozen weight-swap sweep

    benchmarks/paper_eval/x1_passivity/out/weight_swap_full.csv

READ-ONLY and corroborates the one-sweep boundary theory at the system level:

  1. 24 rows present.
  2. Injecting cells (ratio > 1, finite): EXPLICIT weight == 8, IMPLICIT == 0
     (the reviewer-facing headline: swapping the modal contact-row weight from
     mass-only 1/M_q to implicit (M_q+hD_q+h^2 K_q)^-1 kills the injection).
  3. baseline_reldiff < 1e-6 on every row where present (the explicit arm is
     bit-faithful to the frozen solver_matrix baseline, so the swapped arm is
     trustworthy).
  4. R1 consistency of the logged per-mode weight ratio: for every row
        | 1/wratio_min - (1 + (2 pi f_hi h_sub)^2) |
        --------------------------------------------- <= 0.05
              1 + (2 pi f_hi h_sub)^2
     i.e. the harness's smallest logged inverse mobility 1/wratio_min matches the
     note's R1 undamped ratio 1 + (omega h)^2 with omega = 2 pi f_hi. The 5%
     slack absorbs the unlogged damping term 2 zeta omega h, which is O(10^2)
     against (omega h)^2 = O(10^6) at these frequencies (note R1, plan T6).

Writes: out/t6_ews_corroboration.csv (+ .config.json manifest).
Reads only:  x1_passivity/out/weight_swap_full.csv  (NEVER written).
Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/run_t6_ews_reuse.py
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

import numpy as np

# _ROOT sys.path pattern (run_weight_swap.py lines 46-49): repo root on path so
# this runs from any cwd.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
EWS_CSV = os.path.join(_ROOT, "benchmarks", "paper_eval", "x1_passivity",
                       "out", "weight_swap_full.csv")


def _finite_float(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False, float("nan")
    return math.isfinite(v), v


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ews-csv", default=EWS_CSV,
                    help="READ-ONLY source (frozen E-WS full sweep).")
    ap.add_argument("--out", default="t6_ews_corroboration",
                    help="output CSV basename in out/.")
    ap.add_argument("--r1-slack", type=float, default=0.05,
                    help="R1-consistency relative tolerance (plan T6: 0.05).")
    args = ap.parse_args()

    if not os.path.isfile(args.ews_csv):
        print("FATAL: E-WS CSV not found (read-only source): %s" % args.ews_csv)
        sys.exit(2)

    with open(args.ews_csv, newline="") as fh:
        ews = list(csv.DictReader(fh))

    clog = C.CheckLog()

    # ---- assert 1: 24 rows ------------------------------------------------- #
    clog.assert_true(len(ews) == 24,
                     label="T6.1 row count == 24 (measured %d)" % len(ews))

    # ---- per-row corroboration -------------------------------------------- #
    corr_rows = []
    n_inj_expl = 0
    n_inj_impl = 0
    max_baseline = 0.0
    r1_reldiffs = []
    for r in ews:
        fe, re_ = _finite_float(r["ratio_explicit"])
        fi, ri = _finite_float(r["ratio_implicit"])
        inj_e = bool(fe and re_ > 1.0)
        inj_i = bool(fi and ri > 1.0)
        n_inj_expl += int(inj_e)
        n_inj_impl += int(inj_i)

        _bok, baseline = _finite_float(r["baseline_reldiff"])
        max_baseline = max(max_baseline, abs(baseline) if _bok else float("inf"))

        f_hi = float(r["f_hi_hz"])
        h_sub = float(r["h_sub"])
        wmin = float(r["wratio_min"])
        r1_pred = 1.0 + (2.0 * math.pi * f_hi * h_sub) ** 2  # note R1, omega=2 pi f_hi
        r1_meas = 1.0 / wmin                                 # smallest logged 1/mu_eff
        r1_reldiff = abs(r1_meas - r1_pred) / r1_pred
        r1_reldiffs.append(r1_reldiff)

        corr_rows.append(dict(
            scene=r["scene"], relax=r["relax"], iters=r["iters"],
            substeps=r["substeps"],
            ratio_explicit=re_, ratio_implicit=ri,
            inject_explicit=inj_e, inject_implicit=inj_i,
            baseline_reldiff=baseline,
            f_hi_hz=f_hi, h_sub=h_sub, wratio_min=wmin,
            r1_pred=r1_pred, r1_meas=r1_meas, r1_reldiff=r1_reldiff,
            r1_ok=bool(r1_reldiff <= args.r1_slack)))

    r1_reldiffs = np.asarray(r1_reldiffs, dtype=np.float64)

    # ---- assert 2: injecting-cell counts (8 explicit, 0 implicit) --------- #
    clog.assert_true(n_inj_expl == 8,
                     label="T6.2 injecting cells explicit == 8 (measured %d)"
                     % n_inj_expl)
    clog.assert_true(n_inj_impl == 0,
                     label="T6.2 injecting cells implicit == 0 (measured %d)"
                     % n_inj_impl)

    # ---- assert 3: baseline_reldiff < 1e-6 on all present rows ------------ #
    clog.assert_true(max_baseline < 1e-6,
                     label="T6.3 max baseline_reldiff < 1e-6 (measured %.3e)"
                     % max_baseline)

    # ---- assert 4: R1 consistency <= 5% per row --------------------------- #
    clog.assert_true(bool(np.all(r1_reldiffs <= args.r1_slack)),
                     label="T6.4 R1 consistency <= %.2f on all 24 rows "
                     "(max measured %.3e)" % (args.r1_slack,
                                              float(r1_reldiffs.max())))

    # ---- write corroboration CSV (BEFORE finalize, so it survives a fail) - #
    fieldnames = ["scene", "relax", "iters", "substeps",
                  "ratio_explicit", "ratio_implicit",
                  "inject_explicit", "inject_implicit", "baseline_reldiff",
                  "f_hi_hz", "h_sub", "wratio_min",
                  "r1_pred", "r1_meas", "r1_reldiff", "r1_ok"]
    C.write_csv(
        OUT, args.out, corr_rows, fieldnames=fieldnames,
        manifest=dict(
            scenes=sorted(set(r["scene"] for r in corr_rows)),
            solvers=["xpbd"],
            note=("T6 (note R1/R2; plan T6): READ-ONLY reuse of x1_passivity/out/"
                  "weight_swap_full.csv (24 cells). Corroborates the one-sweep "
                  "boundary at system level: injecting cells explicit=%d "
                  "implicit=%d; max baseline_reldiff=%.3e (<1e-6); R1 "
                  "consistency 1/wratio_min vs 1+(2 pi f_hi h_sub)^2 max "
                  "reldiff=%.3e (<=%.2f, 5%% slack absorbs the unlogged "
                  "2 zeta omega h damping term). Source CSV never written."
                  % (n_inj_expl, n_inj_impl, max_baseline,
                     float(r1_reldiffs.max()), args.r1_slack)),
            source_csv=os.path.relpath(args.ews_csv, _ROOT),
            r1_slack=args.r1_slack))

    # ---- report ----------------------------------------------------------- #
    print("\n=== T6 E-WS corroboration (read-only reuse) ===")
    print("  source: %s" % os.path.relpath(args.ews_csv, _ROOT))
    print("  rows                : %d" % len(ews))
    print("  injecting explicit  : %d  (plan: 8)" % n_inj_expl)
    print("  injecting implicit  : %d  (plan: 0)" % n_inj_impl)
    print("  max baseline_reldiff: %.3e  (plan: < 1e-6)" % max_baseline)
    print("  R1 consistency max  : %.3e  (plan: <= %.2f)"
          % (float(r1_reldiffs.max()), args.r1_slack))

    clog.finalize(title="T6 E-WS corroboration")


if __name__ == "__main__":
    main()
