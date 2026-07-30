"""T14 addendum: how often does the SHIPPED (mass-only) weight itself inject on
the warm / two-row cells, and on what denominator?

WHY THIS SCRIPT EXISTS. run_t14_warm_multirow.py reports, for the mass-only
weight, only the two DISAGREEMENT counters (false negatives = index says safe and
the sweep injects; false positives = index says injects and the sweep is passive).
True positives are never tallied, so the mass arm's total injecting count
FN + TP is not recoverable from t14_warm_multirow.csv. For the matched charge the
predictor is the constant `pred_inj = False` (Thm 3.3), so THERE false_neg IS the
injecting count. The two published numbers are therefore different quantities:
2795 index misses (mass) against 4099 injections (matched), on denominators that
also differ (43,783 against 43,898). This script measures the missing quantity,
on the identical populations, and reports both arms on a common paired
denominator as well.

MEASUREMENT ONLY. Nothing here extends any theorem. Every hypothesis of the
paper's results (one sweep, cold start, e = 0, hard contact, one row) is
deliberately violated in blocks B and D; the deliverable is the measured boundary
of the shipped weight and of the diagnostic, not a guarantee.

METHOD. Blocks B and D of run_t14_warm_multirow.py are re-run VERBATIM through
that module's own primitives (warm_cell, two_row_sweep, PREDICTORS, PAIRED); this
file adds counters and changes nothing else. Both populations are exactly
reproducible: block B is a deterministic logspace/linspace grid, block D reseeds
np.random.default_rng(20260728) inside every arm ("same draws in every arm"). A
HARD self-check refuses to write output unless the reproduced activity counts and
false-negative counts equal the shipped headline exactly:

    mass    43,783 cells, 2,795 false negatives, 9,877 false positives
    matched 43,898 cells, 4,099 injecting

DENOMINATORS. A cell counts only if the row (block B) or BOTH rows (block D) are
still active after the sweep, and activity is measured under that arm's own
weight. In block B the post-solve multiplier sign depends only on the predicted
gap, which is weight-independent, so both arms see the same 35,688 cells. In
block D the first row solved moves the second row's gap through W J_c, so which
draws leave both rows active does depend on the weight: 8,095 (mass) against
8,210 (matched). 35,688 + 8,095 = 43,783 and 35,688 + 8,210 = 43,898. Same
draws, weight-dependent active subsets. The PAIRED block below intersects the two
active sets so that both arms are also reported on one common denominator.

OUTPUT
  out/t14_massarm_baseline.csv          summary blocks (below)
  out/t14_massarm_baseline_cells.csv.gz per-cell dump for the supplement

BLOCKS IN THE CSV
  B_inject       per (kappa, weight, predictor): active, injecting, FN, FP
  B_inject_total per weight, summed over both kappa and all four predictors
  D_inject       per (warm, shared, kappa, weight): both-active, injecting, FN, FP
  D_inject_total per weight, summed over the four (warm/shared) x kappa arms
  PAIRED_D       block D restricted to draws both-active under BOTH weights
  HEADLINE       the combined numbers the paper may quote, with the self-check
"""

from __future__ import annotations

import gzip
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CheckLog, write_csv                                # noqa: E402
from run_t14_warm_multirow import (                                   # noqa: E402
    PAIRED,
    PREDICTORS,
    two_row_sweep,
    warm_cell,
)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Shipped headline (t14_warm_multirow.csv, block HEADLINE). The self-check below
# is an equality gate, not a tolerance: if any of these moves, this script stops
# and no number is written.
SHIPPED = dict(
    combined_cells_mass=43783,
    combined_false_neg=2795,
    combined_false_pos=9877,
    combined_cells_matched=43898,
    combined_injecting_matched=4099,
    warm_onerow_cells_mass=35688,
    tworow_cells_mass=8095,
)

WEIGHTS = ("mass", "matched")


def _pred_inj(weight, index_value):
    """The arm's pre-solve prediction, copied from run_t14_warm_multirow.py:387
    and :703. For the matched charge the prediction is the constant False
    (Thm 3.3 is a cold-start passivity statement), which is exactly why that
    arm's false_neg equals its injecting count."""
    return False if weight == "matched" else index_value > 1.0


# --------------------------------------------------------------------------- #
# Block B: warm grid, one row (grid identical to run_t14_warm_multirow.block_B) #
# --------------------------------------------------------------------------- #
def block_B_inject(log, rows, cells):
    print("\n== B. warm grid, one row: how often does each weight INJECT? ==")
    h = 1.0 / 960.0
    bs = np.logspace(-2, 2, 12)
    mMs = np.logspace(-2, 1, 6)
    warm_q = np.linspace(-2.0, 2.0, 9)
    warm_v = np.linspace(-2.0, 2.0, 9)
    tot = {w: dict(n=0, inj=0, fn=0, fp=0) for w in WEIGHTS}
    # Active-cell KEY sets per weight, so the paired denominator below is an
    # intersection of populations, not an equality of two counts.
    act_keys = {w: set() for w in WEIGHTS}
    inj_by_key = {w: {} for w in WEIGHTS}
    for kappa in (1.0, 2.0):
        for weight in WEIGHTS:
            for pred in PREDICTORS:
                n_act = n_inj = fn = fp = 0
                for ib, b in enumerate(bs):
                    for imM, mM in enumerate(mMs):
                        for iqn, qn in enumerate(warm_q):
                            for iqd, qd in enumerate(warm_v):
                                c = warm_cell(1.0, mM, b, h, kappa, weight, qn, qd,
                                              pred)
                                if not c["active"]:
                                    continue
                                key = (kappa, pred, ib, imM, iqn, iqd)
                                act_keys[weight].add(key)
                                n_act += 1
                                inj = c["dE"] > 0.0
                                n_inj += int(inj)
                                inj_by_key[weight][key] = inj
                                pi = _pred_inj(weight, c["index"])
                                if inj and not pi:
                                    fn += 1
                                elif pi and not inj:
                                    fp += 1
                                cells.append(
                                    f"B,{kappa:g},{weight},{pred},,,"
                                    f"{b:.17g},{mM:.17g},{qn:.17g},{qd:.17g},,"
                                    f"{c['index']:.17g},{c['dE']:.17g},"
                                    f"{int(inj)},{int(pi)}\n")
                t = tot[weight]
                t["n"] += n_act
                t["inj"] += n_inj
                t["fn"] += fn
                t["fp"] += fp
                star = " *" if pred == PAIRED[kappa] else "  "
                print(f"  {star}kappa={kappa:g} {weight:8s} {pred:10s}: "
                      f"{n_act:6d} active, INJECTING {n_inj:6d} "
                      f"({100.0 * n_inj / max(n_act, 1):5.2f}%), "
                      f"FN {fn:5d}, FP {fp:5d}")
                rows.append(dict(block="B_inject", kappa=kappa, weight=weight,
                                 predictor=pred, paired=int(pred == PAIRED[kappa]),
                                 n_active=n_act, n_injecting=n_inj,
                                 inject_frac=n_inj / max(n_act, 1),
                                 false_neg=fn, false_pos=fp))
    for weight in WEIGHTS:
        t = tot[weight]
        print(f"   TOTAL block B, {weight:8s}: {t['n']} active, {t['inj']} "
              f"injecting ({100.0 * t['inj'] / max(t['n'], 1):.2f}%), "
              f"{t['fn']} FN, {t['fp']} FP")
        rows.append(dict(block="B_inject_total", weight=weight, n_active=t["n"],
                         n_injecting=t["inj"],
                         inject_frac=t["inj"] / max(t["n"], 1),
                         false_neg=t["fn"], false_pos=t["fp"]))
        log.assert_true(True, label=f"B-total. {weight}: {t['inj']}/{t['n']} "
                                    f"injecting, {t['fn']} false negatives")
    # Activity in block B cannot depend on the weight: the post-solve multiplier
    # sign is set by the PREDICTED gap C~ = z~ + J_c' q~, which is formed before
    # any charge is applied (warm_cell: dlam = max(0, -C~/(w_row + a~))).
    same_set = act_keys["mass"] == act_keys["matched"]
    log.assert_true(tot["mass"]["n"] == tot["matched"]["n"] and same_set,
                    label=f"B. one-row activity is weight-independent, as SETS "
                          f"({tot['mass']['n']} identical cells in both arms)")
    common = act_keys["mass"] & act_keys["matched"]
    pb = dict(n=len(common),
              inj_mass=sum(inj_by_key["mass"][k] for k in common),
              inj_matched=sum(inj_by_key["matched"][k] for k in common))
    print(f"   PAIRED block B (active under BOTH weights): {pb['n']} cells, "
          f"mass {pb['inj_mass']} injecting, matched {pb['inj_matched']} "
          f"injecting")
    rows.append(dict(block="PAIRED_B", weight="mass", n_active=pb["n"],
                     n_injecting=pb["inj_mass"],
                     inject_frac=pb["inj_mass"] / max(pb["n"], 1)))
    rows.append(dict(block="PAIRED_B", weight="matched", n_active=pb["n"],
                     n_injecting=pb["inj_matched"],
                     inject_frac=pb["inj_matched"] / max(pb["n"], 1)))
    return tot, pb


# --------------------------------------------------------------------------- #
# Block D: two active rows (draws identical to block_D, same seed per arm)      #
# --------------------------------------------------------------------------- #
def _draws(rng):
    """One draw of block_D's parameter set, in the SAME rng order as
    run_t14_warm_multirow.block_D:664-684."""
    h = 1.0 / 960.0
    m1 = 10.0 ** rng.uniform(-1.5, 1.0)
    m2 = 10.0 ** rng.uniform(-1.5, 1.0)
    M_c = np.diag([m1, m2])
    b1 = 10.0 ** rng.uniform(-2, 1.2)
    b2 = 10.0 ** rng.uniform(-2, 1.2)
    K_c = np.diag([m1 * b1 / h / h, m2 * b2 / h / h])
    t1 = rng.uniform(0.0, np.pi)
    t2 = rng.uniform(0.0, np.pi)
    J1 = -np.array([np.cos(t1), np.sin(t1)])
    J2 = -np.array([np.cos(t2), np.sin(t2)])
    M1 = 10.0 ** rng.uniform(-1, 1)
    M2 = 10.0 ** rng.uniform(-1, 1)
    v1 = -10.0 ** rng.uniform(-1, 0.5)
    v2 = -10.0 ** rng.uniform(-1, 0.5)
    return dict(M_c=M_c, K_c=K_c, J1=J1, J2=J2, M1=M1, M2=M2, v1=v1, v2=v2)


def block_D_inject(log, rows, cells):
    print("\n== D. two simultaneously active rows: injection per weight ==")
    h = 1.0 / 960.0
    tot = {w: dict(n=0, inj=0, fn=0, fp=0) for w in WEIGHTS}
    paired = dict(n=0, inj_mass=0, inj_matched=0, fn_mass=0)
    for warm in (False, True):
        for shared in (False, True):
            for kappa in (1.0, 2.0):
                # Per-arm results keyed by draw index, so the two weights can be
                # intersected afterwards on the identical draws.
                per_arm = {}
                for weight in WEIGHTS:
                    rng = np.random.default_rng(20260728)   # same draws, every arm
                    n_cells = n_inj = fn = fp = 0
                    seen = {}
                    for i in range(1500):
                        d = _draws(rng)
                        vs = (abs(d["v1"]) if shared
                              else 0.5 * (abs(d["v1"]) + abs(d["v2"])))
                        if warm:
                            qn0 = rng.uniform(-1.0, 1.0, 2) * h * vs
                            qdn0 = rng.uniform(-1.0, 1.0, 2) * vs
                        else:
                            qn0 = qdn0 = None
                        r = two_row_sweep(d["M1"], d["M2"], d["M_c"], d["K_c"],
                                          d["J1"], d["J2"], h, kappa, weight,
                                          d["v1"], d["v2"], (0, 1), shared,
                                          q_n=qn0, qdot_n=qdn0,
                                          predictor=PAIRED[kappa])
                        if min(r["dlam"]) <= 0.0:
                            continue                # not simultaneously active
                        n_cells += 1
                        inj = r["dE_total"] > 0.0
                        n_inj += int(inj)
                        pi = _pred_inj(weight, max(r["idx"]))
                        if inj and not pi:
                            fn += 1
                        elif pi and not inj:
                            fp += 1
                        seen[i] = (inj, pi)
                        cells.append(
                            f"D,{kappa:g},{weight},{PAIRED[kappa]},{int(warm)},"
                            f"{int(shared)},,,,,{i},{max(r['idx']):.17g},"
                            f"{r['dE_total']:.17g},{int(inj)},{int(pi)}\n")
                    per_arm[weight] = seen
                    t = tot[weight]
                    t["n"] += n_cells
                    t["inj"] += n_inj
                    t["fn"] += fn
                    t["fp"] += fp
                    tag = ("warm " if warm else "cold ") + \
                          ("shared body   " if shared else "separate bodies")
                    print(f"   {tag}, kappa={kappa:g}, {weight:8s}: "
                          f"{n_cells:5d} both-active, INJECTING {n_inj:5d} "
                          f"({100.0 * n_inj / max(n_cells, 1):5.2f}%), "
                          f"FN {fn:4d}, FP {fp:4d}")
                    rows.append(dict(block="D_inject", warm=int(warm),
                                     shared_body=int(shared), kappa=kappa,
                                     weight=weight, n_active=n_cells,
                                     n_injecting=n_inj,
                                     inject_frac=n_inj / max(n_cells, 1),
                                     false_neg=fn, false_pos=fp))
                common = set(per_arm["mass"]) & set(per_arm["matched"])
                paired["n"] += len(common)
                paired["inj_mass"] += sum(per_arm["mass"][i][0] for i in common)
                paired["inj_matched"] += sum(per_arm["matched"][i][0]
                                             for i in common)
                paired["fn_mass"] += sum(
                    1 for i in common
                    if per_arm["mass"][i][0] and not per_arm["mass"][i][1])
    for weight in WEIGHTS:
        t = tot[weight]
        print(f"   TOTAL block D, {weight:8s}: {t['n']} both-active, {t['inj']} "
              f"injecting ({100.0 * t['inj'] / max(t['n'], 1):.2f}%), "
              f"{t['fn']} FN, {t['fp']} FP")
        rows.append(dict(block="D_inject_total", weight=weight, n_active=t["n"],
                         n_injecting=t["inj"],
                         inject_frac=t["inj"] / max(t["n"], 1),
                         false_neg=t["fn"], false_pos=t["fp"]))
        log.assert_true(True, label=f"D-total. {weight}: {t['inj']}/{t['n']} "
                                    f"injecting, {t['fn']} false negatives")
    print(f"   PAIRED block D (both-active under BOTH weights): {paired['n']} "
          f"draws, mass {paired['inj_mass']} injecting, matched "
          f"{paired['inj_matched']} injecting")
    rows.append(dict(block="PAIRED_D", n_active=paired["n"],
                     n_injecting=paired["inj_mass"], weight="mass",
                     false_neg=paired["fn_mass"],
                     inject_frac=paired["inj_mass"] / max(paired["n"], 1)))
    rows.append(dict(block="PAIRED_D", n_active=paired["n"],
                     n_injecting=paired["inj_matched"], weight="matched",
                     false_neg=paired["inj_matched"],
                     inject_frac=paired["inj_matched"] / max(paired["n"], 1)))
    log.assert_true(True, label=f"PAIRED-D. {paired['n']} draws both-active under "
                               f"both weights: mass {paired['inj_mass']} "
                               f"injecting, matched {paired['inj_matched']}")
    return tot, paired


def main():
    log = CheckLog()
    rows = []
    cells = []
    print("T14 addendum: injection rate of the SHIPPED mass-only weight on the")
    print("     warm / two-row cells. MEASUREMENT ONLY; no theorem is extended.")
    tB, pB = block_B_inject(log, rows, cells)
    tD, pD = block_D_inject(log, rows, cells)

    print("\n== HEADLINE ==")
    comb = {w: dict(n=tB[w]["n"] + tD[w]["n"],
                    inj=tB[w]["inj"] + tD[w]["inj"],
                    fn=tB[w]["fn"] + tD[w]["fn"],
                    fp=tB[w]["fp"] + tD[w]["fp"]) for w in WEIGHTS}
    for w in WEIGHTS:
        c = comb[w]
        print(f"   {w:8s}: {c['n']} warm/two-row cells, {c['inj']} INJECTING "
              f"({100.0 * c['inj'] / c['n']:.2f}%), {c['fn']} false negatives, "
              f"{c['fp']} false positives")
    pn = pB["n"] + pD["n"]
    p_mass = pB["inj_mass"] + pD["inj_mass"]
    p_matched = pB["inj_matched"] + pD["inj_matched"]

    # ---- HARD self-check against the shipped headline. Equality, not tolerance.
    gates = [
        ("combined_cells_mass", comb["mass"]["n"]),
        ("combined_false_neg", comb["mass"]["fn"]),
        ("combined_false_pos", comb["mass"]["fp"]),
        ("combined_cells_matched", comb["matched"]["n"]),
        ("combined_injecting_matched", comb["matched"]["fn"]),
        ("warm_onerow_cells_mass", tB["mass"]["n"]),
        ("tworow_cells_mass", tD["mass"]["n"]),
    ]
    ok = True
    for name, got in gates:
        want = SHIPPED[name]
        good = got == want
        ok = ok and good
        log.assert_true(good, label=f"SELF-CHECK {name}: reproduced {got}, "
                                    f"shipped {want}")
        print(f"   self-check {name:28s}: {got:6d} vs shipped {want:6d} "
              f"{'OK' if good else 'MISMATCH'}")
    # For the matched charge the predictor is the constant False, so its false
    # negatives ARE its injections. Assert the identity rather than assume it.
    log.assert_true(comb["matched"]["fn"] == comb["matched"]["inj"],
                    label=f"matched arm: false_neg == injecting "
                          f"({comb['matched']['fn']})")
    if not ok:
        print("\nSELF-CHECK FAILED: populations did not reproduce. "
              "No number written.")
        return 1

    rows.append(dict(block="HEADLINE", weight="mass",
                     n_active=comb["mass"]["n"], n_injecting=comb["mass"]["inj"],
                     inject_frac=comb["mass"]["inj"] / comb["mass"]["n"],
                     false_neg=comb["mass"]["fn"], false_pos=comb["mass"]["fp"],
                     paired_n_active=pn, paired_n_injecting=p_mass,
                     paired_inject_frac=p_mass / max(pn, 1)))
    rows.append(dict(block="HEADLINE", weight="matched",
                     n_active=comb["matched"]["n"],
                     n_injecting=comb["matched"]["inj"],
                     inject_frac=comb["matched"]["inj"] / comb["matched"]["n"],
                     false_neg=comb["matched"]["fn"], false_pos=comb["matched"]["fp"],
                     paired_n_active=pn, paired_n_injecting=p_matched,
                     paired_inject_frac=p_matched / max(pn, 1)))
    print(f"   PAIRED denominator (cells active under BOTH weights): {pn}")
    print(f"     mass    {p_mass} injecting ({100.0 * p_mass / pn:.2f}%)")
    print(f"     matched {p_matched} injecting ({100.0 * p_matched / pn:.2f}%)")

    field_union = []
    for r in rows:
        for kk in r:
            if kk not in field_union:
                field_union.append(kk)
    rows = [{kk: r.get(kk, "") for kk in field_union} for r in rows]
    write_csv(OUT, "t14_massarm_baseline", rows, fieldnames=field_union,
              manifest=dict(
                  script="run_t14_massarm_baseline.py",
                  what="injection rate of the shipped mass-only weight, and of "
                       "the reconstruction-matched charge, on the warm and "
                       "two-row cells of T14; adds the true-positive tally that "
                       "run_t14_warm_multirow.py omits",
                  metrics="active cells and injecting cells per arm, with false "
                          "negatives / false positives, on each arm's own "
                          "denominator and on the paired both-active denominator",
                  tol="exact equality against the shipped T14 headline counts"))

    dump = os.path.join(OUT, "t14_massarm_baseline_cells.csv.gz")
    with gzip.open(dump, "wt", newline="") as fh:
        fh.write("block,kappa,weight,predictor,warm,shared_body,b,m_over_M,"
                 "q_n_norm,qdot_n_norm,draw,index,dE,inject,pred_inj\n")
        fh.write("".join(cells))
    print(f"\n   per-cell dump: {dump} ({len(cells)} rows)")

    print("\n" + "\n".join(log.summary_lines()))
    fails = log.failures
    print(f"\nT14-addendum: {len(log.rows) - len(fails)}/{len(log.rows)} checks pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
