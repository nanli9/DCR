"""T4-AUDIT: make the paper's midpoint-index "27/27" independently auditable.

WHY THIS EXISTS. Fig. 4 (middle) and the validation text report that under the
shipped symplectic default the mass-arm sign is tracked by the midpoint index on
all 27 cells. That number is CORRECT, but it cannot be reproduced from
`t4_shipped.csv` as shipped, because:

  * the CSV's `sign_agree` column compares the measured sign against the
    BACKWARD-EULER index rho = L / w_row, which agrees on only 22 of 27; and
  * the CSV carries no rho_mid column at all.

An auditor recomputing from the shipped columns therefore lands on 22/27 and
would reasonably conclude the paper overstated its own result. The gap is
provenance, not honesty, and this script closes it by emitting both indices per
cell from the frozen CSV, with the general condition written out.

THE TWO INDICES. From the general multi-mode one-sweep condition (T10-2),
mass-only charge W = M_c^{-1} gives u = M_c^{-1} J_c, J_c^T u = sum_i a_i, and
u^T G u = kappa^2 sum_i a_i + L with L = sum_i a_i b_i. So injection is

    L + (kappa^2 - 2) sum_i a_i  >  w_r + 2 a_tilde .

  kappa = 1 (backward Euler):  L > w_r + sum_i a_i + 2 a_tilde = w_m + 2 a_tilde
                               => rho_BE  := L / (w_m + 2 a_tilde)
  kappa = 2 (shipped default): L + 2 sum_i a_i > w_r + 2 a_tilde
                               => rho_mid := (L + 2 sum_i a_i) / (w_r + 2 a_tilde)

Note the DENOMINATOR differs between the two, not just the numerator: at
kappa = 2 the modal mobility sum_i a_i moves from the denominator to the
numerator. That is why rho_BE is not merely a rescaling of rho_mid and why using
rho_BE on a symplectic host produces FALSE NEGATIVES, the dangerous direction
for a safety diagnostic: it reports "safe" on 5 cells that measurably inject.
Those 5 are the softest modes of the two strongly coupled scenes (shelf at
s = 1.0e-7, 7.5e-7, 5.6e-6; ledge at s = 1.0e-7, 7.5e-7), consistent with
Rmk. 1's statement that at kappa = 2 injection extends to low stiffness.

sum_i a_i is recovered from the frozen columns as w_row - w_r, exact for the
mass arm because that arm's row denominator IS w_r + sum_i a_i.

Reads:  out/t4_shipped.csv   (frozen, not modified)
Writes: out/t4_index_audit.csv
Run:    .venv/bin/python benchmarks/paper_eval/t_onesweep/run_t4_index_audit.py
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CheckLog, write_csv  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(_HERE, "out")


def _find_input(name):
    """Locate a frozen input CSV in the repo layout or in the shipped supplement.

    In the repository the CSVs live in <script dir>/out/. In the anonymous
    supplement the code is under code/t_onesweep/ and the CSVs under data/, so a
    reader running this script straight from the package needs the second path.
    Checked because the package README claims this script runs standalone."""
    for cand in (os.path.join(OUT, name),
                 os.path.join(_HERE, "..", "..", "data", name)):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    raise FileNotFoundError(
        f"{name} not found in {OUT} or the supplement's data/ directory")


def main():
    log = CheckLog()
    src = _find_input("t4_shipped.csv")
    with open(src) as fh:
        allrows = list(csv.DictReader(fh))

    # The stiffness sweep is iterations == 1; the extra shelf rows are the
    # iteration-budget inset and are excluded (they are not part of the 27).
    rows_mass = [r for r in allrows if r["iterations"] == "1" and r["arm"] == "mass"]
    log.assert_true(len(rows_mass) == 27,
                    label="27 mass-arm stiffness cells (9 per scene x 3 scenes)")

    out_rows = []
    n_be = n_mid = n_inject = 0
    false_neg_be = []
    for r in rows_mass:
        w_r = float(r["w_r"])
        w_row = float(r["w_row"])
        L = float(r["L"])
        a_t = float(r["a_tilde"])
        dE = float(r["dE_meas"])
        sum_a = w_row - w_r                      # exact for the mass arm
        rho_be = L / (w_row + 2.0 * a_t)         # kappa = 1
        rho_mid = (L + 2.0 * sum_a) / (w_r + 2.0 * a_t)   # kappa = 2, shipped
        inj = dE > 0.0
        ok_be = (rho_be > 1.0) == inj
        ok_mid = (rho_mid > 1.0) == inj
        n_be += ok_be
        n_mid += ok_mid
        n_inject += inj
        if inj and rho_be <= 1.0:
            false_neg_be.append((r["scene"], float(r["s"])))
        out_rows.append(dict(
            scene=r["scene"], s=float(r["s"]), arm="mass",
            w_r=w_r, w_row=w_row, sum_a=sum_a, L=L, a_tilde=a_t,
            rho_BE=rho_be, rho_mid=rho_mid,
            dE_meas=dE, injects=int(inj),
            BE_index_agrees=int(ok_be), mid_index_agrees=int(ok_mid),
            BE_false_negative=int(inj and rho_be <= 1.0)))

    print(f"measured injecting cells                  : {n_inject}/27")
    print(f"backward-Euler index rho_BE  agrees       : {n_be}/27")
    print(f"shipped-default index rho_mid agrees      : {n_mid}/27")
    print(f"rho_BE FALSE NEGATIVES (says safe, injects): {len(false_neg_be)}")
    for sc, s in false_neg_be:
        print(f"   {sc:8s} s = {s:.1e}")

    log.assert_true(n_mid == 27,
                    label="rho_mid tracks the measured sign on all 27 cells")
    log.assert_true(n_be == 22,
                    label="rho_BE tracks only 22/27 on the symplectic host")
    log.assert_true(len(false_neg_be) == 5,
                    label="the 5 rho_BE misses are FALSE NEGATIVES, not false positives")

    os.makedirs(OUT, exist_ok=True)
    write_csv(OUT, "t4_index_audit", out_rows,
              manifest=dict(
                  script="run_t4_index_audit.py",
                  source="t4_shipped.csv (frozen)",
                  what="per-cell rho_BE and rho_mid with the measured sign, so the "
                       "paper's 27/27 midpoint claim is auditable from the CSVs",
                  condition="inject <=> L + (kappa^2-2) sum a_i > w_r + 2 a_tilde",
                  note="rho_BE on a kappa=2 host yields 5 false negatives"))

    print("\n" + "\n".join(log.summary_lines()))
    fails = log.failures
    print(f"\nT4-AUDIT: {len(log.rows) - len(fails)}/{len(log.rows)} checks pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
