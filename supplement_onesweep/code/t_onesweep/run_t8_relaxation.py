#!/usr/bin/env python3
"""T8 - relaxation boundary for the SHIPPED convention (VERIFY-FIRST gate, M2).

The shipped solver relaxes ONLY the modal position correction:

    dcr/avbd/_solver/solver_xpbd.py 1546-1549:
        X[bi][1] += invm[bi] * dlam                 # rigid: FULL dlam
        Q[bi]     = _quat_apply_rotvec(..., ... * dlam)   # rigid: FULL dlam
        rel = self.modal_relax
        q += rel * (-sc.U_y * wq) * dlam            # modal position: * rel = theta

so the multiplier `dlam` (line 1540) and the rigid update are UN-relaxed; theta
scales the modal deposit only. This module derives the exact one-sweep mass-arm
injection boundary for THAT convention, machine-checks it to rel <= 1e-12, and
contrasts it with codex's L > (2/theta - 1) w_m (which is a DIFFERENT convention).

DERIVATION (from the model box; re-derived, not copied from prose)
------------------------------------------------------------------
General reconstruction qdot+ = kappa dq/h, mass-only charge mu_c = m, modal-only
relaxation theta (rigid + multiplier un-relaxed). With w_m = 1/M + 1/m:
  dlam  = -h v / w_m                                      (theta-independent)
  v+    = v + dlam/(M h) = v M/(M+m)                      (rigid loss theta-INDEP)
  dq    = theta (-1/m) dlam,  s = dq/h = theta v M/(M+m)
  qdot+ = kappa s,  q+ = dq
  E_modal+ = 1/2 (m kappa^2 + k h^2) s^2 = 1/2 m(kappa^2+b) theta^2 [vM/(M+m)]^2

  dE = 1/2 v^2 M m/(M+m)^2 * [ M theta^2 (kappa^2 + b) - 2 M - m ].          (T8-1)

SHIPPED BOUNDARY:  dE > 0  <=>  theta^2 (kappa^2 + b) > 2 + m/M.             (T8-2)
  theta = 1, kappa = 1 -> b > 1 + m/M  (Theorem 1 / C1, exact reduction).
  Deposit E_modal+ scales EXACTLY as theta^2; rigid loss is theta-independent, so
  dE(theta) = (theta-indep rigid loss) + theta^2 (deposit at theta=1), MONOTONE
  decreasing as theta drops. Under-relaxation can only move an injecting cell to
  passive, NEVER a passive cell to injecting.                               (T8-3)

WHOLE-CORRECTION convention (theta scales rigid AND modal correction; the
convention codex assumed). Same algebra with v+ = v(1 - theta m/(M+m)):
  dE = 1/2 v^2 [ -2 theta M m/(M+m) + theta^2 M m/(M+m)^2 (m + (kappa^2+b) M) ]. (T8-4)
  boundary (kappa=1): theta (m + (1+b)M)/(M+m) > 2  <=>  L > (2/theta - 1) w_m,
  L = b/m, w_m = 1/M + 1/m   (codex's coefficient, CONFIRMED under THIS convention). (T8-5)

The two conventions agree at theta = 1 (both reduce to Theorem 1) and DISAGREE for
theta < 1: shipped scales the deposit by theta^2, whole-correction also shrinks the
rigid loss. Reviewer anchor (findings.md 2026-07-23): M=m=1, b=4, kappa=1, v=-1:
theta=1 -> +0.25 (both); theta=0.5 -> -0.0625 (whole, codex) vs -0.21875 (shipped).
Either way the sweep flips injecting->passive, so the paper's "cannot flip either
arm's sign" is false; the SHIPPED boundary the paper must print is (T8-2).

Run (fast, pure numpy):
    .venv/bin/python run_t8_relaxation.py
Output: out/t8_relaxation.csv (+ .config.json manifest with git_sha, seed).
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C              # noqa: E402
from benchmarks.paper_eval.t_onesweep.run_t7_reconstruction import (  # noqa: E402
    Battery, kappa_row, stable_dE)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SEED = 20260724
THETAS = [0.25, 0.5, 0.7, 0.9, 1.0]
FIELDS = ["check_id", "group", "n_cases", "max_rel_err", "max_abs_err", "tol",
          "binding", "pass", "note"]


# --------------------------------------------------------------------------- #
# Closed forms (DERIVED above).                                               #
# --------------------------------------------------------------------------- #
def dE_shipped(M, m, v, b, kappa, theta):
    """(T8-1) shipped modal-only relaxation, mass arm."""
    return (0.5 * v * v * M * m / (M + m) ** 2
            * (M * theta ** 2 * (kappa ** 2 + b) - 2.0 * M - m))


def shipped_inject_value(M, m, b, kappa, theta):
    """(T8-2) shipped injection value J; inject <=> J>0; J = theta^2(kappa^2+b) - (2+m/M)."""
    return theta ** 2 * (kappa ** 2 + b) - (2.0 + m / M)


def dE_whole(M, m, v, b, kappa, theta):
    """(T8-4) whole-correction relaxation (theta on rigid AND modal), mass arm."""
    return 0.5 * v * v * (-2.0 * theta * M * m / (M + m)
                          + theta ** 2 * M * m / (M + m) ** 2
                          * (m + (kappa ** 2 + b) * M))


def whole_inject_value_k1(M, m, b, theta):
    """(T8-5) whole-correction kappa=1 injection value in codex's form:
    L - (2/theta - 1) w_m, L = b/m, w_m = 1/M + 1/m; inject <=> > 0."""
    L = b / m
    w_m = 1.0 / M + 1.0 / m
    return L - (2.0 / theta - 1.0) * w_m


def whole_row(M, m, b, h, v, mu_c, kappa, theta):
    """SIM: theta scales BOTH rigid and modal position corrections (whole
    correction); the multiplier/denominator are un-relaxed. Used to machine-check
    (T8-4)/(T8-5) and confirm codex's coefficient under ITS OWN convention."""
    k = b * m / (h * h)
    wq = 1.0 / mu_c
    w_row = 1.0 / M + wq
    dlam = -(h * v) / w_row
    dz = theta * (1.0 / M) * dlam                 # rigid correction, RELAXED
    dq = theta * (-wq) * dlam                     # modal correction, RELAXED
    s = dq / h
    qdot = kappa * s
    v_plus = v + dz / h
    E_minus = 0.5 * M * v * v
    E_plus = 0.5 * M * v_plus * v_plus + 0.5 * m * qdot * qdot + 0.5 * k * dq * dq
    return dict(dlam=dlam, dq=dq, qdot=qdot, v_plus=v_plus,
                E_minus=E_minus, E_plus=E_plus, dE=E_plus - E_minus)


def whole_stable_dE(res, M, m, b, h, v):
    """Cancellation-free rebuild for the whole-correction sim (v+ - v = dz/h,
    dz/h = theta dlam/(M h) formed directly)."""
    k = b * m / (h * h)
    dv = res["v_plus"] - v
    rigid = 0.5 * M * dv * (res["v_plus"] + v)
    modal = 0.5 * m * res["qdot"] ** 2 + 0.5 * k * res["dq"] ** 2
    return rigid + modal


# --------------------------------------------------------------------------- #
# (1) shipped-convention boundary: sim dE == (T8-1), 0 sign mismatches         #
# --------------------------------------------------------------------------- #
def group_shipped(bat, n_cells):
    rng = np.random.default_rng([SEED, 1])
    # grid: theta x (b, m/M) x kappa, plus random fill to exceed n_cells
    M, m, b, kap, v, h, th = [], [], [], [], [], [], []
    for theta in THETAS:
        for _ in range(max(1, n_cells // (len(THETAS) * 2))):
            for kappa in (1.0, 2.0):
                M.append(1.0)
                r = 10.0 ** rng.uniform(-3.0, 3.0)
                m.append(r)
                b.append(10.0 ** rng.uniform(-3.0, 2.0))
                kap.append(kappa)
                v.append(rng.uniform(-2.0, -0.1))
                h.append(rng.choice([1e-3, 1e-2]))
                th.append(theta)
    M = np.array(M); m = np.array(m); b = np.array(b); kap = np.array(kap)
    v = np.array(v); h = np.array(h); th = np.array(th)
    n = M.size

    sim = np.empty(n); stab = np.empty(n); frm = np.empty(n)
    Ep = np.empty(n); Em = np.empty(n)
    for i in range(n):
        res = kappa_row(M[i], m[i], b[i], h[i], v[i], mu_c=m[i], kappa=kap[i],
                        relax=th[i])
        sim[i] = res["dE"]; stab[i] = stable_dE(res, M[i], m[i], b[i], h[i], v[i])
        frm[i] = dE_shipped(M[i], m[i], v[i], b[i], kap[i], th[i])
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]

    bat.energy_dE("T8_shipped_dE_formula", "shipped", sim, frm, Ep, Em,
                  note="sim(relax=theta) dE == (T8-1) modal-only relaxation")
    # cancellation-free reconstruction at the escale floor (T1 energy_dE criterion);
    # this dE crosses zero so pure-relative is undefined near neutrality.
    bat.energy_dE("T8_shipped_dE_stable", "shipped", stab, frm, Ep, Em,
                  note="cancellation-free sim dE == (T8-1) (escale-floor proof)")

    Jv = shipped_inject_value(M, m, b, kap, th)
    sign_ok = np.sign(stab) == np.sign(Jv)
    n_inj = int(np.sum(Jv > 0)); n_pas = int(np.sum(Jv < 0))
    bat.true("T8_shipped_sign_law", "shipped", sign_ok, n,
             note=f"sign(dE)==sign(theta^2(k^2+b)-(2+m/M)); inject={n_inj} "
                  f"passive={n_pas} mismatches={int(np.sum(~sign_ok))}",
             metric=float(np.sum(~sign_ok)))

    # theta=1 reduction to Theorem 1 (b > 1 + m/M) for the kappa=1 subset
    one_k1 = (th == 1.0) & (kap == 1.0)
    thm1_sign = np.sign(b[one_k1] - (1.0 + m[one_k1] / M[one_k1]))
    bat.true("T8_theta1_reduces_thm1", "shipped",
             np.sign(stab[one_k1]) == thm1_sign, int(np.sum(one_k1)),
             note="theta=1,kappa=1 boundary == Theorem 1 b>1+m/M")


# --------------------------------------------------------------------------- #
# (2) theta^2 deposit scaling (matches T1 relax_deposit_scaling)               #
# --------------------------------------------------------------------------- #
def group_deposit_scaling(bat, n_draws):
    rng = np.random.default_rng([SEED, 2])
    errs = []
    n = 0
    for _ in range(n_draws):
        M = 1.0
        m = 10.0 ** rng.uniform(-2.0, 2.0)
        b = 10.0 ** rng.uniform(-3.0, 2.0)
        kappa = float(rng.choice([1.0, 2.0]))
        v = rng.uniform(-2.0, -0.1)
        h = float(rng.choice([1e-3, 1e-2]))
        base = kappa_row(M, m, b, h, v, mu_c=m, kappa=kappa, relax=1.0)
        dep1 = 0.5 * m * base["qdot"] ** 2 + 0.5 * (b * m / h ** 2) * base["dq"] ** 2
        for theta in THETAS:
            res = kappa_row(M, m, b, h, v, mu_c=m, kappa=kappa, relax=theta)
            dep = 0.5 * m * res["qdot"] ** 2 + 0.5 * (b * m / h ** 2) * res["dq"] ** 2
            pred = theta ** 2 * dep1
            errs.append(abs(dep - pred) / (abs(pred) if abs(pred) > 0 else 1.0))
            n += 1
    bat.true("T8_deposit_theta2_scaling", "scaling",
             np.array(errs) <= 1e-12, n,
             note=f"E_modal+(theta) == theta^2 E_modal+(1); max_rel={max(errs):.2e}",
             metric=float(max(errs)))


# --------------------------------------------------------------------------- #
# (3) direction: 0 passive->injecting; injecting->passive flips DO occur        #
# --------------------------------------------------------------------------- #
def group_direction(bat, n_draws):
    rng = np.random.default_rng([SEED, 3])
    bad = 0                      # passive(theta=1) -> injecting(theta<1): forbidden
    good = 0                     # injecting(theta=1) -> passive(theta<1): expected
    n = 0
    monotone_ok = True
    for _ in range(n_draws):
        M = 1.0
        m = 10.0 ** rng.uniform(-2.0, 2.0)
        # bias b to straddle the theta=1 boundary so flips are exercised
        b0 = 1.0 + m / M
        b = b0 * 10.0 ** rng.uniform(-1.0, 1.0)
        kappa = float(rng.choice([1.0, 2.0]))
        v = rng.uniform(-2.0, -0.1)
        h = float(rng.choice([1e-3, 1e-2]))
        dE1 = kappa_row(M, m, b, h, v, mu_c=m, kappa=kappa, relax=1.0)["dE"]
        prev = dE1
        for theta in (0.9, 0.7, 0.5, 0.25):
            dE = kappa_row(M, m, b, h, v, mu_c=m, kappa=kappa, relax=theta)["dE"]
            if dE > prev + 1e-15:            # dE must MONOTONE decrease as theta drops
                monotone_ok = False
            prev = dE
            if dE1 <= 0.0 and dE > 0.0:
                bad += 1
            if dE1 > 0.0 and dE <= 0.0:
                good += 1
            n += 1
    bat.true("T8_no_passive_to_injecting", "direction", bad == 0, n,
             note=f"0 passive->injecting under theta<1 (shipped); found {bad}",
             metric=float(bad))
    bat.true("T8_dE_monotone_in_theta", "direction", monotone_ok, n,
             note="dE(theta) monotone decreasing as theta drops (rigid loss fixed, "
                  "deposit ~theta^2)")
    bat.true("T8_injecting_to_passive_occurs", "direction", good > 0, n,
             note=f"injecting->passive flips DO occur = {good} (paper 'cannot flip' "
                  f"is false)", binding=False, metric=float(good))


# --------------------------------------------------------------------------- #
# (4) whole-correction convention: codex L>(2/theta-1)w_m holds under IT        #
# --------------------------------------------------------------------------- #
def group_whole(bat, n_cells):
    rng = np.random.default_rng([SEED, 4])
    M, m, b, v, h, th = [], [], [], [], [], []
    for theta in THETAS:
        for _ in range(max(1, n_cells // len(THETAS))):
            M.append(1.0)
            m.append(10.0 ** rng.uniform(-3.0, 3.0))
            b.append(10.0 ** rng.uniform(-3.0, 2.0))
            v.append(rng.uniform(-2.0, -0.1))
            h.append(rng.choice([1e-3, 1e-2]))
            th.append(theta)
    M = np.array(M); m = np.array(m); b = np.array(b)
    v = np.array(v); h = np.array(h); th = np.array(th)
    n = M.size

    sim = np.empty(n); stab = np.empty(n); frm = np.empty(n)
    Ep = np.empty(n); Em = np.empty(n)
    for i in range(n):
        res = whole_row(M[i], m[i], b[i], h[i], v[i], mu_c=m[i], kappa=1.0,
                        theta=th[i])
        sim[i] = res["dE"]
        stab[i] = whole_stable_dE(res, M[i], m[i], b[i], h[i], v[i])
        frm[i] = dE_whole(M[i], m[i], v[i], b[i], 1.0, th[i])
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]

    bat.energy_dE("T8_whole_dE_formula", "whole", sim, frm, Ep, Em,
                  note="whole-correction sim dE == (T8-4)")
    # cancellation-free reconstruction at the escale floor (T1 energy_dE criterion);
    # whole-correction dE has a deep rigid-vs-modal near-cancellation off-boundary.
    bat.energy_dE("T8_whole_dE_stable", "whole", stab, frm, Ep, Em,
                  note="cancellation-free whole sim dE == (T8-4) (escale-floor proof)")
    # codex's coefficient: sign(dE_whole) == sign(L - (2/theta-1) w_m), kappa=1
    Jv = whole_inject_value_k1(M, m, b, th)
    sign_ok = np.sign(stab) == np.sign(Jv)
    bat.true("T8_codex_form_matches_whole", "whole", sign_ok, n,
             note=f"codex L>(2/theta-1)w_m == whole-correction boundary (kappa=1); "
                  f"mismatches={int(np.sum(~sign_ok))}", metric=float(np.sum(~sign_ok)))

    # shipped sim does NOT satisfy codex's boundary (the two conventions differ):
    # count cells where shipped and whole disagree in sign at theta<1 (must be >0).
    dis = 0
    ntest = 0
    for i in range(n):
        if th[i] == 1.0:
            continue
        s_ship = np.sign(dE_shipped(M[i], m[i], v[i], b[i], 1.0, th[i]))
        s_codex = np.sign(whole_inject_value_k1(M[i], m[i], b[i], th[i]))
        if s_ship != s_codex:
            dis += 1
        ntest += 1
    bat.true("T8_shipped_differs_from_codex", "whole", dis > 0, ntest,
             note=f"shipped (T8-2) and codex (T8-5) disagree on {dis}/{ntest} "
                  f"theta<1 cells (distinct conventions)", binding=False,
             metric=float(dis))


# --------------------------------------------------------------------------- #
# (5) exact anchor vectors + cross-check vs common.one_sweep_row(relax)         #
# --------------------------------------------------------------------------- #
def group_anchors(bat):
    # reviewer counterexample (findings.md 2026-07-23): M=m=1, b=4, kappa=1, v=-1
    M = m = 1.0; v = -1.0; b = 4.0
    d1 = kappa_row(M, m, b, 1e-3, v, mu_c=m, kappa=1.0, relax=1.0)["dE"]
    d_ship_half = kappa_row(M, m, b, 1e-3, v, mu_c=m, kappa=1.0, relax=0.5)["dE"]
    d_whole_half = whole_row(M, m, b, 1e-3, v, mu_c=m, kappa=1.0, theta=0.5)["dE"]
    bat.close("T8_anchor_theta1", "anchor",
              [d1, d_ship_half, d_whole_half], [0.25, -0.21875, -0.0625],
              note="theta=1:+0.25 (both); theta=0.5 shipped:-0.21875 whole:-0.0625 "
                   "(reviewer number)")
    # cross-check: shipped kappa_row(kappa=1,relax) == common.one_sweep_row(relax)
    rng = np.random.default_rng([SEED, 5])
    a, bb = [], []
    for _ in range(200):
        M = 1.0; m = 10.0 ** rng.uniform(-2.0, 2.0)
        b = 10.0 ** rng.uniform(-3.0, 2.0); v = rng.uniform(-2.0, -0.1)
        h = float(rng.choice([1e-3, 1e-2])); theta = float(rng.choice(THETAS))
        k = b * m / h ** 2
        a.append(kappa_row(M, m, b, h, v, mu_c=m, kappa=1.0, relax=theta)["dE"])
        bb.append(C.one_sweep_row(wr=1.0 / M, J_c=[-1.0], M_c=[[m]], K_c=[[k]],
                                  h=h, v=v, weight_mode="mass", relax=theta)["dE"])
    bat.close("T8_matches_one_sweep_row", "anchor", a, bb,
              note="kappa_row(kappa=1,relax) == common.one_sweep_row(relax) "
                   "(shipped convention, R2 harness)")


# --------------------------------------------------------------------------- #
# CSV / driver                                                                #
# --------------------------------------------------------------------------- #
def write_out(out_dir, name, rows, note):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + ".csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({"check_id": r["check_id"], "group": r["group"],
                        "n_cases": r["n_cases"],
                        "max_rel_err": repr(r["max_rel_err"]),
                        "max_abs_err": repr(r["max_abs_err"]),
                        "tol": repr(r["tol"]), "binding": r["binding"],
                        "pass": r["pass_"], "note": r["note"]})
    from benchmarks.paper_eval.paper_config import write_manifest
    write_manifest(out_dir, name + ".csv", scenes=[], solvers=["numpy-identity"],
                   seed=SEED, note=note)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-shipped", type=int, default=1200)
    ap.add_argument("--n-whole", type=int, default=1000)
    ap.add_argument("--n-draws", type=int, default=400)
    ap.add_argument("--out", default="t8_relaxation")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    t0 = time.perf_counter()
    bat = Battery()
    print(f"### T8 relaxation boundary (shipped convention) "
          f"({platform.machine()}, {platform.system()}) seed={SEED}\n", flush=True)
    print("[shipped] modal-only relaxation boundary (T8-2)", flush=True)
    group_shipped(bat, args.n_shipped)
    print("[scaling] theta^2 deposit scaling", flush=True)
    group_deposit_scaling(bat, args.n_draws)
    print("[direction] no passive->injecting; injecting->passive occurs", flush=True)
    group_direction(bat, args.n_draws)
    print("[whole] codex L>(2/theta-1)w_m under the whole-correction convention",
          flush=True)
    group_whole(bat, args.n_whole)
    print("[anchor] reviewer vectors + one_sweep_row cross-check", flush=True)
    group_anchors(bat)

    note = ("T8 relaxation boundary. SHIPPED convention (theta on the modal "
            "position correction only, solver_xpbd.py 1546-1549): boundary "
            "theta^2(kappa^2+b) > 2+m/M (T8-2), reduces to Theorem 1 b>1+m/M at "
            "theta=kappa=1; modal deposit scales EXACTLY theta^2; rigid loss "
            "theta-independent so under-relaxation only moves injecting->passive, "
            "0 passive->injecting. Codex's L>(2/theta-1)w_m is the WHOLE-correction "
            "convention (theta on rigid AND modal): CONFIRMED under that convention "
            "(T8-5), does NOT match the shipped code. Reviewer anchor M=m=1,b=4,"
            "kappa=1: theta=1 +0.25 (both), theta=0.5 shipped -0.21875 / whole "
            "-0.0625. All identities rel<=1e-12, 0 sign mismatches. The paper's "
            "'cannot flip either arm's sign' is FALSE; the shipped boundary is (T8-2).")
    path = write_out(OUT, args.out, bat.rows, note)

    n_bind = sum(1 for r in bat.rows if r["binding"])
    wall = time.perf_counter() - t0
    print(f"\n--- T8: {len(bat.rows)} checks ({n_bind} binding), "
          f"{len(bat.binding_fail)} binding failure(s), {wall:.2f}s ---")
    print(f"CSV: {path}")
    if bat.binding_fail:
        print("\nFAILED binding check(s) [tolerance NOT loosened; a finding]:")
        for r in bat.binding_fail:
            print(f"  {r['check_id']}: max_rel={r['max_rel_err']:.3e} "
                  f"max_abs={r['max_abs_err']:.3e} tol={r['tol']:.0e} [{r['note']}]")
        sys.exit(1)
    print("\nALL BINDING CHECKS PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
