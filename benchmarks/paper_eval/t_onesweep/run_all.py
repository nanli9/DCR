#!/usr/bin/env python3
"""run_all.py -- sequential driver + acceptance table for the T-suite.

Plan section T6 (`scratchpad/wf1/plan.md`): "run_all.py runs T1 -> T6 ->
make_figs sequentially with a wall-clock report and a final PASS/FAIL table per
acceptance criterion; exits nonzero on any failure." Theory note:
`scratchpad/onesweep_theory_note.md`.

Two independent products:

  1. RUN TABLE  -- runs each step (T1, T2, T3, T5, T4, T6, make_figs) as a
     subprocess (T4 chunked by scene/arm so no single command is long), reporting
     per-step PASS/FAIL from the exit code plus wall-clock. `--steps` runs a
     subset; `--table-only` skips running entirely.

  2. ACCEPTANCE TABLE -- rebuilt PURELY from the output CSVs (self-contained,
     reproducible without a live run): every acceptance criterion of plan
     section 2, its measured value, and PASS/FAIL. The single re-derivation
     (T2 h-independence, 5 cells) uses common.one_sweep_row; everything else is
     read straight from a logged column.

Exit code: nonzero if ANY run step failed OR ANY acceptance criterion FAILED
(the shipped-solver symplectic path legitimately fails T4 (b)-(d) on strongly
coupled scenes -- a documented note/model gap, not a loosened tolerance -- so a
full run reports the suite as PARTIAL and exits nonzero, by design).

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/run_all.py
     .venv/bin/python .../run_all.py --steps T1,T6        # subset
     .venv/bin/python .../run_all.py --table-only         # table from CSVs
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import numpy as np

# _ROOT sys.path pattern (run_weight_swap.py lines 46-49).
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PY = sys.executable

# ------------------------------------------------------------------ steps ---- #
# Each step is (name, [list of arg-lists]). T4 is chunked by scene/arm so no
# single subprocess is long (each ~3 s); the first chunk writes fresh, the rest
# merge with --append.
STEPS = [
    ("T1", [["run_t1_identities.py"]]),
    ("T2", [["run_t2_phasemap.py"]]),
    ("T3", [["run_t3_nonmodal.py"]]),
    ("T5", [["run_t5_ordering.py"]]),
    ("T4", [
        ["run_t4_shipped.py", "--scenes", "shelf", "--arms", "mass,implicit",
         "--out", "t4_shipped"],
        ["run_t4_shipped.py", "--scenes", "ledge", "--arms", "mass,implicit",
         "--out", "t4_shipped", "--append"],
        ["run_t4_shipped.py", "--scenes", "dinner", "--arms", "mass,implicit",
         "--out", "t4_shipped", "--append"],
        ["run_t4_shipped.py", "--annex", "--out", "t4_shipped", "--append"],
    ]),
    ("T6", [["run_t6_ews_reuse.py"]]),
    ("make_figs", [["make_figs.py"]]),
]
STEP_NAMES = [s[0] for s in STEPS]


def run_steps(selected):
    """Run the selected steps as subprocesses; return {name: (passed, wall_s)}."""
    results = {}
    print("=" * 74)
    print("RUN TABLE  (sequential; T4 chunked by scene/arm)")
    print("=" * 74)
    for name, cmds in STEPS:
        if name not in selected:
            continue
        t0 = time.time()
        ok = True
        for cmd in cmds:
            script = os.path.join(HERE, cmd[0])
            rc = subprocess.run([PY, script] + cmd[1:], cwd=_ROOT).returncode
            if rc != 0:
                ok = False
        wall = time.time() - t0
        results[name] = (ok, wall)
        print("  [%s] %-10s  %7.2f s  (%d cmd%s)"
              % ("PASS" if ok else "FAIL", name, wall,
                 len(cmds), "" if len(cmds) == 1 else "s"))
    return results


# ---------------------------------------------------------- CSV helpers ------ #
def _read(name):
    import csv
    path = os.path.join(OUT, name)
    if not os.path.isfile(path):
        raise FileNotFoundError("missing CSV: %s" % os.path.relpath(path, _ROOT))
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _isT(x):
    return str(x).strip().lower() == "true"


# ------------------------------------------------ acceptance evaluators ------ #
def acc_T1():
    rows = _read("t1_identities.csv")
    binding = [r for r in rows if _isT(r["binding"])]
    npass = sum(1 for r in binding if _isT(r["pass"]))
    maxrel = max((_f(r["max_rel_err"]) for r in binding), default=0.0)
    ok = npass == len(binding)
    return [("T1", "all binding identity checks pass (rel<=1e-12)",
             "%d/%d pass, max_rel=%.2e" % (npass, len(binding), maxrel), ok)]


def acc_T2():
    rows = _read("t2_phasemap.csv")
    relerr = max(max(_f(r["relerr_mass_Eplus"]) for r in rows),
                 max(_f(r["relerr_impl_dE"]) for r in rows))
    mis = sum(1 for r in rows
              if int(r["in_band"]) == 0 and int(r["sign_agree"]) == 0)
    dEi = np.array([_f(r["dE_impl"]) for r in rows])
    impl_neg = bool(np.all(dEi < 0.0))
    out = [
        ("T2", "(i) sim vs R2/R3 closed forms rel<=1e-12 every cell",
         "max_rel=%.2e" % relerr, relerr <= 1e-12),
        ("T2", "(ii) 0 misclassified cells outside 1e-9 band",
         "misclassified=%d / %d" % (mis, len(rows)), mis == 0),
        ("T2", "(iii) dE_impl<0 on all cells",
         "max dE_impl=%.2e" % float(dEi.max()), impl_neg),
    ]
    # (iv) h-independence: re-derive 5 cells at h=1e-3 vs 1e-2 (dE/E- identical).
    worst = 0.0
    for oh, mm in [(0.1, 1.0), (0.5, 1.0), (2.0, 1.0), (5.0, 1.0), (20.0, 1.0)]:
        vals = []
        for h in (1e-3, 1e-2):
            omega = oh / h
            m = mm       # M = 1
            k = m * omega * omega
            res = C.one_sweep_row(1.0, [-1.0], [[m]], [[k]], h, -1.0, "mass")
            vals.append(res["dE"] / res["E_minus"])
        worst = max(worst, abs(vals[0] - vals[1]) / abs(vals[1]))
    out.append(("T2", "(iv) h-independence dE/E- rel<=1e-12 (5 cells)",
                "max_rel=%.2e" % worst, worst <= 1e-12))
    return out


def acc_T3():
    rows = _read("t3_nonmodal.csv")
    # (a) collapse identity |y-(rho-1)| <= 1e-12*max(1,rho).
    worst_a = 0.0
    for r in rows:
        rho = _f(r["rho"]); y = _f(r["y"])
        worst_a = max(worst_a, abs(y - (rho - 1.0)) / max(1.0, rho))
    # (b) sign agreement outside band (band cells labelled "band").
    nonband = [r for r in rows if str(r["sign_agree"]) != "band"]
    sa = sum(1 for r in nonband if _isT(r["sign_agree"]))
    # (c) dE == R4 mass form rel<=1e-12.
    def relerr(a, b):
        a = _f(a); b = _f(b)
        return abs(a - b) / abs(b) if b != 0 else abs(a - b)
    worst_c = max(relerr(r["dE_mass"], r["dE_mass_form"]) for r in rows)
    # (d) implicit dE == form rel<=1e-12 AND dE<0 on all.
    worst_d = max(relerr(r["dE_impl"], r["dE_impl_form"]) for r in rows)
    impl_neg = all(_f(r["dE_impl"]) < 0 for r in rows)
    return [
        ("T3", "(a) collapse |y-(rho-1)|<=1e-12*max(1,rho)",
         "max_norm_res=%.2e" % worst_a, worst_a <= 1e-12),
        ("T3", "(b) sign agreement outside 1e-9 band = 100%",
         "%d/%d agree" % (sa, len(nonband)), sa == len(nonband)),
        ("T3", "(c) dE == R4 matrix formula rel<=1e-12",
         "max_rel=%.2e" % worst_c, worst_c <= 1e-12),
        ("T3", "(d) implicit dE == -v^2/(2 w_eff) rel<=1e-12 & <0 all",
         "max_rel=%.2e, all<0=%s" % (worst_d, impl_neg),
         worst_d <= 1e-12 and impl_neg),
    ]


def acc_T4():
    rows = _read("t4_shipped.csv")
    prim = [r for r in rows if int(r["iterations"]) == 1 and _isT(r["valid"])]
    scenes = sorted(set(r["scene"] for r in prim))

    # (a) R1 shipped-array check: r1_ok populated at s=1.
    r1_rows = [r for r in prim if str(r.get("r1_ok", "")) not in ("", "None")]
    r1_ok = all(_isT(r["r1_ok"]) for r in r1_rows) and len(r1_rows) > 0
    r1_res = max((_f(r["r1_res"]) for r in r1_rows), default=float("nan"))

    def scene_pass(path):  # path in {"sym","be"}
        sa_key = "sign_agree" if path == "sym" else "sign_agree_be"
        rd_key = "reldiff_sym" if path == "sym" else "reldiff_be"
        pv_key = "passive_meas" if path == "sym" else "passive_be"
        passing = []
        detail = {}
        for sc in scenes:
            mass = [r for r in prim if r["scene"] == sc and r["arm"] == "mass"
                    and not _isT(r["band"])]
            impl = [r for r in prim if r["scene"] == sc and r["arm"] == "implicit"]
            b_ok = all(_isT(r[sa_key]) for r in mass) and len(mass) > 0
            c_ok = all(_f(r[rd_key]) <= 1e-3 for r in mass) and len(mass) > 0
            d_ok = all(_isT(r[pv_key]) for r in impl) and len(impl) > 0
            nb_sa = sum(1 for r in mass if _isT(r[sa_key]))
            nb_c = sum(1 for r in mass if _f(r[rd_key]) <= 1e-3)
            pv = sum(1 for r in impl if _isT(r[pv_key]))
            detail[sc] = (nb_sa, len(mass), nb_c, len(mass), pv, len(impl))
            if b_ok and c_ok and d_ok:
                passing.append(sc)
        return passing, detail

    sym_pass, sym_d = scene_pass("sym")
    be_pass, be_d = scene_pass("be")

    def fmt(detail):
        return "; ".join("%s b=%d/%d c=%d/%d d=%d/%d"
                         % (sc, d[0], d[1], d[2], d[3], d[4], d[5])
                         for sc, d in detail.items())

    sym_line98 = ("shelf" in sym_pass) and len(sym_pass) >= 2
    be_line98 = ("shelf" in be_pass) and len(be_pass) >= 2

    return [
        ("T4", "(a) R1 shipped-array weight check rel<=1e-12",
         "max r1_res=%.2e (n=%d)" % (r1_res, len(r1_rows)), r1_ok),
        ("T4", "(b)(c)(d) [MANDATED symplectic] pass on >=2 scenes incl shelf",
         "scenes passing={%s}; %s" % (",".join(sym_pass) or "-", fmt(sym_d)),
         sym_line98),
        ("T4", "(b)(c)(d) [BE control] pass on >=2 scenes incl shelf",
         "scenes passing={%s}; %s" % (",".join(be_pass) or "-", fmt(be_d)),
         be_line98),
    ]


def acc_T5():
    rows = _read("t5_ordering.csv")

    def cell(M, m, b, order, n1=True, converged=False):
        out = []
        for r in rows:
            if (abs(_f(r["M"]) - M) < 1e-12 and abs(_f(r["m"]) - m) < 1e-12
                    and abs(_f(r["b"]) - b) < 1e-9 and r["order"] == order):
                is_conv = _isT(r["converged_flag"])
                if converged and is_conv:
                    out.append(r)
                elif (not converged) and (not is_conv) and int(r["n"]) == 1 and n1:
                    out.append(r)
        return out

    grid = [(M, m, b) for (M, m) in [(1.0, 1.0), (1.0, 0.01)]
            for b in (0.25, 1.0, 4.0, 100.0)]

    # (i) D_B/D_A == (1+b)^2 at n=1.
    worst_i = 0.0
    for (M, m, b) in grid:
        A = cell(M, m, b, "A"); B = cell(M, m, b, "B")
        if A and B:
            DA = _f(A[0]["D_modal"]); DB = _f(B[0]["D_modal"])
            ratio = DB / DA
            worst_i = max(worst_i, abs(ratio - (1.0 + b) ** 2) / ((1.0 + b) ** 2))
    # (ii) dE_A(n=1) <= +1e-15.
    worst_ii = -np.inf
    for (M, m, b) in grid:
        A = cell(M, m, b, "A")
        if A:
            worst_ii = max(worst_ii, _f(A[0]["dE"]))
    # (iii) order B n=1 injects iff b > 1 + m/M.
    iii_ok = True
    for (M, m, b) in grid:
        B = cell(M, m, b, "B")
        if B:
            inj = _f(B[0]["dE"]) > 0.0
            pred = b > (1.0 + m / M)
            if inj != pred:
                iii_ok = False
    # (iv) converged: dE<=1e-12, KKT (Cc>=-1e-12, lam_c>=0, |Cc*lam_c|<=1e-12),
    #      order A-vs-B agreement on E_plus <= 1e-10.
    worst_dE = -np.inf
    worst_kkt = 0.0
    worst_cc = np.inf
    worst_lam = np.inf
    worst_agree = 0.0
    for (M, m, b) in grid:
        A = cell(M, m, b, "A", converged=True)
        B = cell(M, m, b, "B", converged=True)
        for r in (A + B):
            worst_dE = max(worst_dE, _f(r["dE"]))
            cc = _f(r["Cc"]); lam = _f(r["lam_c"])
            worst_cc = min(worst_cc, cc)
            worst_lam = min(worst_lam, lam)
            worst_kkt = max(worst_kkt, abs(cc * lam))
        if A and B:
            ea = _f(A[0]["E_plus"]); eb = _f(B[0]["E_plus"])
            worst_agree = max(worst_agree, abs(ea - eb) / max(abs(ea), abs(eb)))
    iv_ok = (worst_dE <= 1e-12 and worst_cc >= -1e-12 and worst_lam >= 0.0
             and worst_kkt <= 1e-12 and worst_agree <= 1e-10)
    return [
        ("T5", "(i) D_B/D_A == (1+b)^2 at n=1 rel<=1e-12",
         "max_rel=%.2e" % worst_i, worst_i <= 1e-12),
        ("T5", "(ii) dE_A(n=1) <= +1e-15 every cell",
         "max dE_A=%.2e" % worst_ii, worst_ii <= 1e-15),
        ("T5", "(iii) order-B n=1 injects iff b>1+m/M",
         "sign law holds=%s" % iii_ok, iii_ok),
        ("T5", "(iv) converged dE<=1e-12, KKT, A/B agree<=1e-10",
         "dE=%.2e Cc>=%.1e lam>=%.1e |Cc*lam|<=%.1e agree=%.2e"
         % (worst_dE, worst_cc, worst_lam, worst_kkt, worst_agree), iv_ok),
    ]


def acc_T6(total_wall):
    rows = _read("t6_ews_corroboration.csv")
    n_expl = sum(1 for r in rows if _isT(r["inject_explicit"]))
    n_impl = sum(1 for r in rows if _isT(r["inject_implicit"]))
    maxr1 = max(_f(r["r1_reldiff"]) for r in rows)
    counts_ok = (len(rows) == 24 and n_expl == 8 and n_impl == 0)
    out = [
        ("T6", "counts match (explicit=8, implicit=0, rows=24)",
         "rows=%d expl=%d impl=%d" % (len(rows), n_expl, n_impl), counts_ok),
        ("T6", "R1-consistency <= 5% on all 24 rows",
         "max_reldiff=%.2e" % maxr1, maxr1 <= 0.05),
    ]
    if total_wall is not None:
        out.append(("T6", "run_all total wall-clock <= 45 min",
                    "%.1f s" % total_wall, total_wall <= 45 * 60))
    return out


def acc_figs():
    need = ["fig_onesweep_phase_map", "fig_onesweep_rowindex",
            "fig_onesweep_nonmodal", "fig_onesweep_ordering"]
    have = [b for b in need
            if os.path.isfile(os.path.join(OUT, b + ".pdf"))
            and os.path.isfile(os.path.join(OUT, b + ".png"))]
    return [("Figs", "exactly 4 figures built (PDF + PNG twins)",
             "%d/4 present" % len(have), len(have) == 4)]


def build_acceptance(total_wall=None):
    table = []
    for fn in (acc_T1, acc_T2, acc_T3, acc_T4, acc_T5):
        table += fn()
    table += acc_T6(total_wall)
    table += acc_figs()
    return table


def print_acceptance(table):
    print("\n" + "=" * 74)
    print("ACCEPTANCE TABLE  (plan section 2; rebuilt from output CSVs)")
    print("=" * 74)
    w = max(len(c) for _, c, _, _ in table)
    for exp, crit, meas, ok in table:
        print("  [%s] %-5s %-*s | %s"
              % ("PASS" if ok else "FAIL", exp, w, crit, meas))
    nfail = sum(1 for *_, ok in [(e, c, m, o) for e, c, m, o in table] if not ok)
    npass = len(table) - nfail
    print("-" * 74)
    print("  %d criteria: %d PASS, %d FAIL" % (len(table), npass, nfail))
    return nfail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--steps", default="all",
                    help="comma list from %s, or 'all'." % ",".join(STEP_NAMES))
    ap.add_argument("--table-only", action="store_true",
                    help="skip running; build the acceptance table from CSVs.")
    ap.add_argument("--list", action="store_true", help="list steps and exit.")
    args = ap.parse_args()

    if args.list:
        print("steps:", ", ".join(STEP_NAMES))
        return

    if args.steps.strip().lower() == "all":
        selected = set(STEP_NAMES)
    else:
        selected = set(s.strip() for s in args.steps.split(",") if s.strip())
        bad = selected - set(STEP_NAMES)
        if bad:
            print("unknown steps: %s (choose from %s)"
                  % (",".join(sorted(bad)), ",".join(STEP_NAMES)))
            sys.exit(2)

    run_fail = False
    total_wall = None
    if not args.table_only:
        t0 = time.time()
        results = run_steps(selected)
        total_wall = time.time() - t0
        run_fail = any(not ok for ok, _ in results.values())
        print("-" * 74)
        print("  total run wall-clock: %.2f s" % total_wall)

    # The acceptance table always covers the full suite (reads all CSVs). When a
    # subset ran, still report it if every CSV exists; otherwise skip gracefully.
    acc_fail = 0
    try:
        table = build_acceptance(total_wall if not args.table_only else None)
        acc_fail = print_acceptance(table)
    except FileNotFoundError as e:
        print("\n[acceptance table skipped] %s" % e)
        if args.table_only:
            sys.exit(2)

    if run_fail or acc_fail:
        print("\nSUITE RESULT: PARTIAL/FAIL "
              "(run_fail=%s, acceptance_failures=%d)" % (run_fail, acc_fail))
        sys.exit(1)
    print("\nSUITE RESULT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
