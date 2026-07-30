#!/usr/bin/env python3
"""T5 -- Gauss-Seidel ordering and iteration sweep (validates note R5).

Standalone two-row toy, exactly the note's R5 recipe (theory note
`scratchpad/onesweep_theory_note.md`, "Result 5"; plan section T5):

  DOFs (z, q). Rigid mass M at z; restorative DOF q with mass m, stiffness k.
  Rows:
    contact  C_c = z - q   (hard, unilateral, a_tilde = 0)
    spring   C_s = q        (compliant, alpha_s = 1/k -> a_tilde_s = 1/(k h^2))
  Cold start: contact touching (z = q = 0), incoming rate zdot = v = -1,
  q = qdot = 0. Predicted positions z~ = h v, q~ = 0. Multipliers start at 0.

  Order A = [contact, spring]  (trailing spring relaxes the fresh deposit)
  Order B = [spring, contact]  (spring is a no-op from rest; contact == R2)

The single local solve is `common.local_solve` (note Model box); no
eigendecomposition, no dcr import, pure numpy. Every closed form is
`common.r5_*` (PLAN-DERIVED, ledgered in common.py). All 1e-12 asserts are
BINDING: on failure the script records the failing identity + measured residual
and exits nonzero (CheckLog.finalize). Nothing is loosened.

Re-runnable and chunkable via CLI flags (--mm, --bvals, --orders, --nvals,
--no-converged, --out). Acceptance is defined on the FULL default grid; a chunk
runs its checks on the selected subset.

Run:
  .venv/bin/python \
      benchmarks/paper_eval/t_onesweep/run_t5_ordering.py
"""
from __future__ import annotations

import argparse
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

# Default grid (plan T5).
DEF_MM = [(1.0, 1.0), (1.0, 0.01)]          # (M, m)
DEF_B = [0.25, 1.0, 4.0, 100.0]             # b = (omega h)^2
DEF_N = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]
DEF_ORDERS = ["A", "B"]
V0 = -1.0                                    # incoming gap rate (cold start)
H = 1.0e-3
CONV_TOL = 1.0e-14                           # max|dlam| convergence threshold
CONV_CAP = 100_000                           # sweep cap (record if hit)


# --------------------------------------------------------------------------- #
# Two-row GS sweep of the note's R5 toy (built from common.local_solve).       #
# Mirrors selftest_common.two_row_sweep, extended to expose lam_c, lam_s, the  #
# converged contact gap C_c, and (converge mode) the sweep count n_conv.       #
# --------------------------------------------------------------------------- #
def two_row_run(M, m, v, b, h, order, n=None, converge=False,
                dlam_tol=CONV_TOL, cap=CONV_CAP, state_tol=1e-15):
    """Run the (z, q) two-row toy for a fixed sweep count `n`, or to convergence
    when `converge=True` (cap `cap`).

    Returns a dict with E_plus, dE, D (modal deposit), lam_c, lam_s, contact
    gap Cc = z - q, reconstructed velocities/positions, n_used, n_conv_dlam,
    and hit_cap.

    # DEVIATION (note R5 "Endpoints and interior"; plan T5 (iv)): the plan's
    # literal convergence proxy is `max|dlam| < 1e-14`. That proxy is recorded
    # as `n_conv_dlam`, BUT it stops on the geometric linear-convergence tail:
    # for the slow cells (small m, large b) the multiplier increment reaches
    # 1e-14 while the smallest state components (q ~ 1e-5..1e-4, lam_s) still
    # carry a ~1e-13 ABSOLUTE residual, which a pure RELATIVE cross-order
    # comparison inflates above the plan's 1e-10 agreement tolerance. The two
    # GS orders provably converge to the SAME BE-KKT fixed point (that IS the
    # R5 endpoint claim), so the converged endpoint is detected on the STATE
    # increment settling to the machine floor (`max|dx| <= state_tol*max|x|`),
    # a strictly STRONGER criterion that reaches the identical fixed point. No
    # acceptance tolerance is loosened: (iv) is still asserted at 1e-10 rel, and
    # is met with ~600x margin (worst 1.7e-13). n_conv_dlam preserves the plan's
    # recorded quantity.
    """
    k = b * m / h ** 2
    Minv = np.array([1.0 / M, 1.0 / m])
    a_tilde_s = 1.0 / (k * h * h)
    x_start = np.array([0.0, 0.0])
    x = np.array([h * v, 0.0])                 # predicted positions (z~, q~)
    Jc = np.array([1.0, -1.0]); wc = 1.0 / M + 1.0 / m     # C_c = z - q
    Js = np.array([0.0, 1.0]); ws = 1.0 / m               # C_s = q
    lam_c = 0.0
    lam_s = 0.0
    rows = ["c", "s"] if order == "A" else ["s", "c"]

    hit_cap = False
    n_conv_dlam = None
    if converge:
        n_used = 0
        while True:
            max_dl = 0.0
            x_prev = x.copy()
            for rw in rows:
                if rw == "c":
                    Cval = float(Jc @ x)
                    dlam, lam_c = C.local_solve(Cval, lam_c, wc, 0.0, unilateral=True)
                    x = x + Minv * Jc * dlam
                else:
                    Cval = float(Js @ x)
                    dlam, lam_s = C.local_solve(Cval, lam_s, ws, a_tilde_s, unilateral=False)
                    x = x + Minv * Js * dlam
                max_dl = max(max_dl, abs(dlam))
            n_used += 1
            if n_conv_dlam is None and max_dl < dlam_tol:   # plan's recorded n_conv
                n_conv_dlam = n_used
            d_state = float(np.max(np.abs(x - x_prev)))
            scale = max(float(np.max(np.abs(x))), 1e-300)
            if d_state <= state_tol * scale:                # true fixed point
                break
            if n_used >= cap:
                hit_cap = True
                break
        if n_conv_dlam is None:
            n_conv_dlam = n_used
    else:
        n_used = n
        n_conv_dlam = n
        for _ in range(n):
            for rw in rows:
                if rw == "c":
                    Cval = float(Jc @ x)
                    dlam, lam_c = C.local_solve(Cval, lam_c, wc, 0.0, unilateral=True)
                    x = x + Minv * Jc * dlam
                else:
                    Cval = float(Js @ x)
                    dlam, lam_s = C.local_solve(Cval, lam_s, ws, a_tilde_s, unilateral=False)
                    x = x + Minv * Js * dlam

    vfin = (x - x_start) / h
    zdot, qdot = float(vfin[0]), float(vfin[1])
    q = float(x[1])
    z = float(x[0])
    E_plus = 0.5 * M * zdot ** 2 + 0.5 * m * qdot ** 2 + 0.5 * k * q ** 2
    E_minus = 0.5 * M * v * v
    D = 0.5 * m * qdot ** 2 + 0.5 * k * q ** 2
    Cc = z - q                                             # contact gap at end
    return dict(E_plus=E_plus, E_minus=E_minus, dE=E_plus - E_minus, D=D,
                lam_c=lam_c, lam_s=lam_s, Cc=Cc, zdot=zdot, qdot=qdot,
                q=q, z=z, n_used=n_used, n_conv_dlam=n_conv_dlam, hit_cap=hit_cap)


def _rel(a, b):
    """Symmetric relative difference; falls back to abs when both ~0."""
    denom = max(abs(a), abs(b))
    return abs(a - b) / denom if denom > 0 else abs(a - b)


def parse_args():
    p = argparse.ArgumentParser(description="T5 GS ordering + iteration sweep (R5).")
    p.add_argument("--mm", default=None,
                   help="comma list of M:m pairs, e.g. '1:1,1:0.01' (default full grid)")
    p.add_argument("--bvals", default=None,
                   help="comma list of b=(omega h)^2 values (default '0.25,1,4,100')")
    p.add_argument("--orders", default=None,
                   help="comma list from {A,B} (default 'A,B')")
    p.add_argument("--nvals", default=None,
                   help="comma list of iteration counts (default T5 ladder)")
    p.add_argument("--no-converged", action="store_true",
                   help="skip the converged endpoint runs")
    p.add_argument("--h", type=float, default=H, help="substep (default 1e-3)")
    p.add_argument("--out", default="t5_ordering", help="CSV basename (default t5_ordering)")
    return p.parse_args()


def main():
    args = parse_args()
    h = float(args.h)

    if args.mm:
        mm = []
        for tok in args.mm.split(","):
            a, b = tok.split(":")
            mm.append((float(a), float(b)))
    else:
        mm = list(DEF_MM)
    bvals = [float(x) for x in args.bvals.split(",")] if args.bvals else list(DEF_B)
    orders = [x.strip() for x in args.orders.split(",")] if args.orders else list(DEF_ORDERS)
    nvals = [int(x) for x in args.nvals.split(",")] if args.nvals else list(DEF_N)
    do_conv = not args.no_converged
    v = V0

    clog = C.CheckLog()
    rows = []

    # store per-cell converged results so the A-vs-B agreement check can compare.
    conv_by_cell = {}

    for (M, m) in mm:
        b_boundary = 1.0 + m / M                    # R2 injection boundary in b
        for b in bvals:
            # ---- finite-n ladder -------------------------------------------
            for order in orders:
                for n in nvals:
                    r = two_row_run(M, m, v, b, h, order, n=n)
                    rows.append(dict(
                        M=M, m=m, b=b, order=order, n=n,
                        E_plus=r["E_plus"], dE=r["dE"], D_modal=r["D"],
                        lam_c=r["lam_c"], lam_s=r["lam_s"],
                        Cc=r["Cc"], n_conv="", converged_flag=False))

            # ---- converged endpoint ----------------------------------------
            if do_conv:
                cell_conv = {}
                for order in orders:
                    rc = two_row_run(M, m, v, b, h, order, converge=True)
                    cell_conv[order] = rc
                    rows.append(dict(
                        M=M, m=m, b=b, order=order, n=rc["n_used"],
                        E_plus=rc["E_plus"], dE=rc["dE"], D_modal=rc["D"],
                        lam_c=rc["lam_c"], lam_s=rc["lam_s"],
                        Cc=rc["Cc"], n_conv=rc["n_conv_dlam"], converged_flag=True))
                conv_by_cell[(M, m, b)] = cell_conv

            # ================= ASSERT BATTERY (plan T5 (i)-(v)) =============
            tag = f"(M={M},m={m},b={b})"

            # (i) n=1 order A and B match PLAN-DERIVED closed forms; D_B/D_A==(1+b)^2.
            if 1 in nvals:
                if "A" in orders:
                    rA1 = two_row_run(M, m, v, b, h, "A", n=1)
                    clog.assert_close(rA1["E_plus"], C.r5_E_plus_A(M, m, v, b),
                                      label=f"(i) {tag}: E+_A(n=1) == form")
                    clog.assert_close(rA1["D"], C.r5_D_A(M, m, v, b),
                                      label=f"(i) {tag}: D_A(n=1) == form")
                if "B" in orders:
                    rB1 = two_row_run(M, m, v, b, h, "B", n=1)
                    clog.assert_close(rB1["E_plus"], C.r5_E_plus_B(M, m, v, b),
                                      label=f"(i) {tag}: E+_B(n=1) == form")
                    clog.assert_close(rB1["D"], C.r5_D_B(M, m, v, b),
                                      label=f"(i) {tag}: D_B(n=1) == form")
                if "A" in orders and "B" in orders:
                    ratio = rB1["D"] / rA1["D"]
                    clog.assert_close(ratio, C.r5_ratio_DB_DA(b),
                                      label=f"(i) {tag}: D_B/D_A(n=1) == (1+b)^2")

            # (ii) dE_A(n=1) <= +1e-15 on every cell (trailing-spring passivity).
            if 1 in nvals and "A" in orders:
                clog.assert_true(rA1["dE"] <= 1e-15,
                                 label=f"(ii) {tag}: dE_A(n=1) <= +1e-15 (passive)")

            # (iii) order B at n=1 injects iff b > 1 + m/M (matches R2/T2).
            if 1 in nvals and "B" in orders:
                if abs(b - b_boundary) / b_boundary > 1e-9:
                    predicted_inject = b > b_boundary
                    measured_inject = rB1["dE"] > 0.0
                    clog.assert_true(measured_inject == predicted_inject,
                                     label=(f"(iii) {tag}: sign(dE_B,n=1) matches "
                                            f"b>{b_boundary:g} (inject={predicted_inject})"))

            # (iv) converged: A/B agreement, dE <= +1e-12, KKT complementarity.
            if do_conv:
                for order in orders:
                    rc = cell_conv[order]
                    clog.assert_true(not rc["hit_cap"],
                                     label=f"(iv) {tag} {order}: converged before cap "
                                           f"(n_conv={rc['n_used']})")
                    clog.assert_true(rc["dE"] <= 1e-12,
                                     label=f"(iv) {tag} {order}: converged dE <= +1e-12")
                    # BE-KKT contact complementarity
                    clog.assert_true(rc["Cc"] >= -1e-12,
                                     label=f"(iv) {tag} {order}: KKT C_c >= -1e-12")
                    clog.assert_true(rc["lam_c"] >= 0.0,
                                     label=f"(iv) {tag} {order}: KKT lam_c >= 0")
                    clog.assert_true(abs(rc["Cc"] * rc["lam_c"]) <= 1e-12,
                                     label=f"(iv) {tag} {order}: KKT |C_c lam_c| <= 1e-12")
                if "A" in orders and "B" in orders:
                    rcA, rcB = cell_conv["A"], cell_conv["B"]
                    for key in ("E_plus", "D", "lam_c", "lam_s", "z", "q"):
                        clog.assert_true(_rel(rcA[key], rcB[key]) <= 1e-10,
                                         label=f"(iv) {tag}: converged A==B [{key}] "
                                               f"(rel={_rel(rcA[key], rcB[key]):.2e})")

    # (v) interior n: recorded + plotted only, NO closed-form claim. (No assert;
    #     documented here and in the figure caption built by make_figs.py.)

    # ---- write CSV + manifest (BEFORE finalize, so outputs survive a fail) ---
    fieldnames = ["M", "m", "b", "order", "n", "E_plus", "dE", "D_modal",
                  "lam_c", "lam_s", "Cc", "n_conv", "converged_flag"]
    C.write_csv(
        OUT, args.out, rows, fieldnames=fieldnames,
        manifest=dict(
            scenes=["onesweep_two_row_toy(z,q)"],
            solvers=["xpbd_gs_toy"],
            note=("T5 (note R5): GS ordering + iteration sweep on the (z,q) "
                  "two-row toy. Order A=[contact,spring], B=[spring,contact]. "
                  "n=1 closed forms r5_* (PLAN-DERIVED); D_B/D_A=(1+b)^2 exact "
                  "(=1.0201e4 at b=100). Converged=BE-KKT endpoint (order-"
                  "independent, passive). Interior 1<n<converged: empirical, "
                  "NO closed-form claim (note 'Endpoints and interior'). "
                  "Cold start, e=0, hard contact, one coupling row."),
            grid=dict(mm=[list(x) for x in mm], b=bvals, n=nvals,
                      orders=orders, v0=v, h=h,
                      conv_tol=CONV_TOL, conv_cap=CONV_CAP)))

    # ---- targeted reporting the task asks for --------------------------------
    print("\n=== T5 report ===")
    if 1 in nvals and "A" in orders and "B" in orders:
        print("n=1 closed-form residuals (max relative error, sim vs r5_* form):")
        worst = 0.0
        for r in clog.rows:
            if r["kind"] == "close" and r["label"].startswith("(i)"):
                worst = max(worst, r["max_rel"])
        for r in clog.rows:
            if r["kind"] == "close" and r["label"].startswith("(i)"):
                print(f"    {r['label']}: max_rel={r['max_rel']:.3e}")
        print(f"  worst n=1 residual over all (i) checks = {worst:.3e}")
        print("\nD_B/D_A at n=1 (measured; closed form (1+b)^2):")
        for (M, m) in mm:
            for b in bvals:
                rA1 = two_row_run(M, m, v, b, h, "A", n=1)
                rB1 = two_row_run(M, m, v, b, h, "B", n=1)
                print(f"    M={M:g} m={m:g} b={b:g}: "
                      f"D_A={rA1['D']:.6e} D_B={rB1['D']:.6e} "
                      f"D_B/D_A={rB1['D'] / rA1['D']:.6e}  (1+b)^2={C.r5_ratio_DB_DA(b):.6e}")
    if do_conv:
        print("\nConverged endpoint (per cell): n_settle / n_conv(dlam<1e-14), dE, "
              "KKT, order A-vs-B agreement:")
        for (M, m, b), cc in conv_by_cell.items():
            if "A" in cc and "B" in cc:
                relE = _rel(cc["A"]["E_plus"], cc["B"]["E_plus"])
                relD = _rel(cc["A"]["D"], cc["B"]["D"])
                worst = max(_rel(cc["A"][k], cc["B"][k])
                            for k in ("E_plus", "D", "lam_c", "lam_s", "z", "q"))
                print(f"    M={M:g} m={m:g} b={b:g}: "
                      f"n_settle(A/B)={cc['A']['n_used']}/{cc['B']['n_used']} "
                      f"n_conv_dlam(A/B)={cc['A']['n_conv_dlam']}/{cc['B']['n_conv_dlam']} "
                      f"dE_A={cc['A']['dE']:.3e} dE_B={cc['B']['dE']:.3e} "
                      f"KKT|Cc*lam_c|={abs(cc['A']['Cc']*cc['A']['lam_c']):.1e} "
                      f"worst_rel(A,B)={worst:.2e}")
            else:
                for o, rc in cc.items():
                    print(f"    M={M:g} m={m:g} b={b:g} order={o}: "
                          f"n_conv={rc['n_used']} dE={rc['dE']:.3e}")

    print(f"\nwrote {os.path.join(OUT, args.out)}.csv ({len(rows)} rows) + manifest")

    # ---- finalize: exit 0 on all-pass, exit 1 listing failures (BINDING) -----
    clog.finalize("T5 GS ordering + iteration sweep (R5)")


if __name__ == "__main__":
    main()
