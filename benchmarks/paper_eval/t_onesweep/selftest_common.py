#!/usr/bin/env python3
"""Self-test for `t_onesweep/common.py` (scaffold acceptance).

Covers, at relative tolerance 1e-12 unless stated:
  1. R2 machine-check vector (note "Result 2"): M=m=1, v=-1, omega h=10.
  2. R3 machine-check vector (note "Result 3"): implicit weight, zeta=0.
  3. one R4 random row: one_sweep_row(mass) dE vs the r4_dE_mass formula, plus
     the effective-weight arm equality.
  4. one R5 order-A/B point: two-local-solve GS sweep (built from local_solve)
     vs the PLAN-DERIVED closed forms, including D_B/D_A == (1+b)^2 exactly.
  5. the collapse identity y == rho - 1 on 10 random mass-only rows.

Run: /Users/nan/Desktop/DCR/.venv/bin/python \
        benchmarks/paper_eval/t_onesweep/selftest_common.py
Exit code 0 iff every check passes.
"""
from __future__ import annotations

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

RNG = np.random.default_rng(20260723)


def two_row_sweep(M, m, v, b, h, order, n=1):
    """GS sweep of the note's R5 two-row toy, built purely from local_solve.

    DOFs (z, q); contact C_c = z - q (hard, unilateral); spring C_s = q with
    compliance a_tilde_s = 1/(k h^2). Cold start: z,q touching at rest, zdot=v,
    qdot=0. Returns (E_plus, D_modal) using v+ = (x+ - x_start)/h.
    """
    k = b * m / h ** 2
    Minv = np.array([1.0 / M, 1.0 / m])
    a_tilde_s = 1.0 / (k * h * h)
    x_start = np.array([0.0, 0.0])
    x = np.array([h * v, 0.0])                 # predicted positions
    Jc = np.array([1.0, -1.0]); wc = 1.0 / M + 1.0 / m
    Js = np.array([0.0, 1.0]); ws = 1.0 / m
    lam_c = lam_s = 0.0
    rows = ["c", "s"] if order == "A" else ["s", "c"]
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
    E_plus = 0.5 * M * zdot ** 2 + 0.5 * m * qdot ** 2 + 0.5 * k * q ** 2
    D = 0.5 * m * qdot ** 2 + 0.5 * k * q ** 2
    return E_plus, D


def main():
    clog = C.CheckLog()
    h = 1e-3

    # ----- 1. R2 machine-check vector (note Result 2) --------------------- #
    M = m = 1.0; v = -1.0; b = 100.0
    k = b * m / h ** 2
    r2 = C.one_sweep_row(wr=1.0 / M, J_c=[-1.0], M_c=[[m]], K_c=[[k]],
                         h=h, v=v, weight_mode="mass")
    clog.assert_close(r2["dlam"] / h, 0.5, label="R2 vec: dlam/h == 0.5")
    clog.assert_close(r2["v_rigid_plus"], -0.5, label="R2 vec: v+ == -0.5")
    clog.assert_close(float(r2["qdot"][0]), -0.5, label="R2 vec: qdot == -0.5")
    clog.assert_close(float(r2["dx"][0]), -h / 2, label="R2 vec: q+ == -h/2")
    clog.assert_close(r2["E_minus"], 0.5, label="R2 vec: E- == 0.5")
    clog.assert_close(r2["E_plus"], 12.75, label="R2 vec: E+ == 12.75")
    clog.assert_close(r2["E_plus"] / r2["E_minus"], 25.5, label="R2 vec: ratio == 25.5")
    # closed form agrees with the sim on the vector
    clog.assert_close(C.r2_E_plus(M, m, v, b), r2["E_plus"], label="R2 form == sim")

    # ----- 2. R3 machine-check vector (note Result 3) --------------------- #
    m_eff = C.r3_m_eff(m, omega_h=10.0, zeta=0.0)
    clog.assert_close(m_eff, 101.0, label="R3 vec: m_eff == 101")
    r3 = C.one_sweep_row(wr=1.0 / M, J_c=[-1.0], M_c=[[m]], K_c=[[k]],
                         h=h, v=v, weight_mode="implicit")
    clog.assert_close(r3["w_row"], 102.0 / 101.0, label="R3 vec: w_eff == 102/101")
    clog.assert_close(r3["v_rigid_plus"], -1.0 / 102.0, label="R3 vec: v+ == -1/102")
    clog.assert_close(float(r3["qdot"][0]), -1.0 / 102.0, label="R3 vec: qdot == -1/102")
    clog.assert_close(float(r3["dx"][0]), -h / 102.0, label="R3 vec: q+ == -h/102")
    clog.assert_close(r3["E_plus"], 51.0 / 10404.0, label="R3 vec: E+ == 51/10404")
    clog.assert_close(r3["dE"], -101.0 / 204.0, label="R3 vec: dE == -101/204")
    clog.assert_close(C.r3_dE(M, m_eff, v), r3["dE"], label="R3 form == sim")

    # ----- 3. one R4 random row: sim vs formula + effective-weight arm ---- #
    r = int(RNG.integers(2, 6))
    U = RNG.uniform(0.1, 3.0, size=r) * RNG.choice([-1.0, 1.0], size=r)
    mi = 10.0 ** RNG.uniform(-1.0, 1.0, size=r)
    omega = 10.0 ** RNG.uniform(0.0, 3.0, size=r)
    w_r = 10.0 ** RNG.uniform(-1.0, 1.0)
    vv = float(RNG.uniform(-2.0, -0.1))
    ki = mi * omega ** 2
    a_i = U ** 2 / mi
    b_i = (omega * h) ** 2
    w_m = w_r + float(np.sum(a_i))
    L = float(np.sum(a_i * b_i))
    res = C.one_sweep_row(wr=w_r, J_c=U, M_c=np.diag(mi), K_c=np.diag(ki),
                          h=h, v=vv, weight_mode="mass")
    clog.assert_close(res["dE"], C.r4_dE_mass(vv, w_r, w_m, L),
                      label="R4 random row: sim dE == r4_dE_mass")
    # effective-weight arm (undamped): sim (implicit) == r4_dE_implicit(-v^2/(2 w_eff))
    w_eff = C.r4_w_eff(w_r, U, np.diag(mi), np.diag(ki), h)
    res_i = C.one_sweep_row(wr=w_r, J_c=U, M_c=np.diag(mi), K_c=np.diag(ki),
                            h=h, v=vv, weight_mode="implicit")
    clog.assert_close(res_i["dE"], C.r4_dE_implicit(vv, w_eff),
                      label="R4 random row: implicit sim dE == -v^2/(2 w_eff)")
    clog.assert_true(res_i["dE"] < 0.0, label="R4 random row: implicit dE < 0")

    # ----- 4. one R5 order-A/B point + D_B/D_A == (1+b)^2 ----------------- #
    for (Mr, mr, br) in [(1.0, 1.0, 100.0), (1.0, 0.01, 4.0)]:
        vr = -1.0
        EA, DA = two_row_sweep(Mr, mr, vr, br, h, "A")
        EB, DB = two_row_sweep(Mr, mr, vr, br, h, "B")
        tag = f"(M={Mr},m={mr},b={br})"
        clog.assert_close(EA, C.r5_E_plus_A(Mr, mr, vr, br), label=f"R5 {tag}: E+_A")
        clog.assert_close(EB, C.r5_E_plus_B(Mr, mr, vr, br), label=f"R5 {tag}: E+_B")
        clog.assert_close(DA, C.r5_D_A(Mr, mr, vr, br), label=f"R5 {tag}: D_A")
        clog.assert_close(DB, C.r5_D_B(Mr, mr, vr, br), label=f"R5 {tag}: D_B")
        clog.assert_close(DB / DA, C.r5_ratio_DB_DA(br), label=f"R5 {tag}: D_B/D_A==(1+b)^2")
        # order A is unconditionally passive at n=1 (trailing-spring strengthening)
        clog.assert_true(EA - 0.5 * Mr * vr ** 2 <= 1e-15, label=f"R5 {tag}: dE_A<=0")
    # b=100 gap is the note's ~1e4 cut, exactly 101^2
    clog.assert_close(C.r5_ratio_DB_DA(100.0), 10201.0, label="R5: (1+100)^2 == 10201")

    # ----- 5. collapse identity y == rho - 1 on 10 random rows ------------ #
    max_y_err = 0.0
    for _ in range(10):
        rr = int(RNG.integers(1, 6))
        Uu = RNG.uniform(0.1, 3.0, size=rr) * RNG.choice([-1.0, 1.0], size=rr)
        mm = 10.0 ** RNG.uniform(-1.0, 1.0, size=rr)
        om = 10.0 ** RNG.uniform(0.0, 3.0, size=rr)
        wr = 10.0 ** RNG.uniform(-1.0, 1.0)
        vv2 = float(RNG.uniform(-2.0, -0.1))
        kk = mm * om ** 2
        ai = Uu ** 2 / mm
        bi = (om * h) ** 2
        wm = wr + float(np.sum(ai))
        Ll = float(np.sum(ai * bi))
        rr_res = C.one_sweep_row(wr=wr, J_c=Uu, M_c=np.diag(mm), K_c=np.diag(kk),
                                 h=h, v=vv2, weight_mode="mass")
        y = C.collapse_y(rr_res["dE"], wm, vv2)
        rho = C.r4_rho(Ll, wm, 0.0)
        clog.assert_close(y, rho - 1.0, label="collapse: y == rho-1")
        max_y_err = max(max_y_err, abs(y - (rho - 1.0)))
    print(f"[info] collapse identity worst |y-(rho-1)| over 10 rows = {max_y_err:.3e}")

    # ----- bonus: chain_matrices sanity (symmetric, SPD when anchored) ---- #
    Kc, Mc = C.chain_matrices(8, np.ones(8), np.ones(8), anchored=True)
    clog.assert_close(Kc, Kc.T, label="chain: K symmetric")
    clog.assert_true(np.all(np.linalg.eigvalsh(Kc) > 0),
                     label="chain: K SPD (anchored)")

    clog.finalize("t_onesweep/common self-test")


if __name__ == "__main__":
    main()
