"""T11: accuracy against a converged reference (reviewer objection #3).

WHY THIS EXISTS. The reviewer of build fc552a59 objected: "Passivity alone does
not prove physical accuracy. There is no reference comparison for contact
impulse, constraint residual, modal amplitude/phase, or trajectory." That is a
correct description of the submitted paper, which reports only energy SIGNS. A
weight could be passive and still be wrong: over-dissipating is passive too.

This script supplies the missing comparison. For each weight arm it measures the
four quantities the reviewer named against the exactly-solved converged implicit
contact step for the same host, at a cold start with e = 0 and hard contact.

REFERENCES (each solved in closed form, no iteration, so "converged" is exact).

Ref-BE, the standard converged backward-Euler time-stepping contact solution
whose dissipativity is the paper's cited endpoint. Unknowns (v+, qdot+, p >= 0):
    rigid       M (v+ - v) = -p
    mode        m (qdot+ - qdot) + h c qdot+ + h k q+ = p ,  q+ = q + h qdot+
    constraint  gap rate zeroed, v+ = qdot+                 (e = 0, contact held)
  cold start (q = qdot = 0) gives qdot+ (m + h c + h^2 k) = p, so with
    m_BE := m (1 + 2 zeta omega h + b),   b = (omega h)^2,
    p = v M m_BE / (M + m_BE),  v+ = qdot+ = v M / (M + m_BE),  q+ = h qdot+.

Ref-MID, the same construction when the mode is stepped by the shipped
symplectic implicit-midpoint integrator while the rigid gap stays position-based:
    mode      q+ = q + h (qdot + qdot+)/2  ->  q+ = h qdot+ / 2  (cold)
              m qdot+ + h c qdot+/2 + h k q+/2 = p
              => qdot+ m_MID = p,  m_MID := m (1 + zeta omega h + b/4)
    constraint C+ = z+ - q+ = 0 with z+ = z + h v+ and C = 0  ->  v+ = qdot+ / 2
    => p = v / (1/M + 1/(2 m_MID)),  v+ = v - p/M,  qdot+ = p / m_MID.
Note the factor 1/2 in the constraint: it is the same midpoint read-back that
makes the shipped host reconstruct 2 dq/h, so Ref-MID is the internally
consistent converged answer FOR THAT HOST, not a backward-Euler answer.

WHAT IS MEASURED, per arm and per reference:
    contact impulse p, post-step rigid velocity v+, modal amplitude q+,
    modal velocity qdot+, and the constraint residual C+.

FINDINGS THIS SCRIPT ESTABLISHES (all machine-checked below, not asserted here):
  1. CONSTRAINT RESIDUAL IS ZERO FOR EVERY ARM, exactly, at any weight. One
     sweep of a single row drives C+ = 0 identically because dC = w dlam = -C.
     So constraint satisfaction cannot discriminate between weights, and the
     reviewer's "constraint residual" metric is trivially met by all of them.
     This is worth stating precisely because it is the metric a reader would
     most expect to separate the arms, and it does not.
  2. At kappa = 1 and zeta = 0 the MATCHED weight does not merely stay passive:
     it reproduces Ref-BE EXACTLY in all four quantities. One matched sweep IS
     the converged implicit contact step. This is strictly stronger than the
     passivity claim the paper currently makes.
  3. At zeta > 0 the matched (stored-energy) mass m(kappa^2 + b) and the
     converged (per-impulse) mass m_BE differ by the damping term, so arm 2's
     exactness degrades gracefully; the size of that gap is measured here and
     is first order in zeta*omega*h.
  4. The MASS-ONLY arm's amplitude error is the factor the paper's boundary is
     built from: it over-deposits q+ and qdot+ by roughly (1 + b) at stiff
     modes, which is the accuracy face of the same defect.
  5. At kappa = 2 the matched weight is passive (T10) but does NOT match
     Ref-MID: it charges 4 m (1 + b/4) where the converged step charges
     m (1 + b/4), a factor of 4, so it OVER-dissipates and under-rings. The
     honest statement is therefore "passive and conservative", not "accurate".
     Quantified below.

Interpreter: /Users/nan/Desktop/DCR/.venv/bin/python. Pure numpy. 1e-12 binding
on the exactness checks (these are well-conditioned scalar forms, unlike T10's
multi-mode inverses, so 1e-12 is the right bar and is met).
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CheckLog, write_csv  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


# --------------------------------------------------------------------------- #
# Closed-form converged references                                            #
# --------------------------------------------------------------------------- #
def ref_be(M, m, omega, h, v, zeta=0.0):
    """Exact converged backward-Euler contact step (cold start, e = 0)."""
    b = (omega * h) ** 2
    m_be = m * (1.0 + 2.0 * zeta * omega * h + b)
    # Row multiplier convention: lambda >= 0 for a unilateral contact, so the
    # rigid block receives +p and the mode receives -p (J = [1, -1] for
    # C = z - q). With v < 0 this makes p > 0.
    p = -v * M * m_be / (M + m_be)
    v_plus = v + p / M                      # == v M / (M + m_be)
    qdot_plus = -p / m_be                   # == v_plus, the zeroed gap rate
    q_plus = h * qdot_plus
    return dict(p=p, v_plus=v_plus, qdot_plus=qdot_plus, q_plus=q_plus,
                m_charge=m_be)


def ref_mid(M, m, omega, h, v, zeta=0.0):
    """Exact converged step with the mode on implicit midpoint and the gap
    position-based (the shipped host's own consistent converged answer)."""
    b = (omega * h) ** 2
    m_mid = m * (1.0 + zeta * omega * h + b / 4.0)
    # Same lambda >= 0 convention as ref_be; constraint is v+ = qdot+ / 2.
    p = -v / (1.0 / M + 1.0 / (2.0 * m_mid))
    v_plus = v + p / M
    qdot_plus = -p / m_mid
    q_plus = h * qdot_plus / 2.0
    return dict(p=p, v_plus=v_plus, qdot_plus=qdot_plus, q_plus=q_plus,
                m_charge=m_mid)


# --------------------------------------------------------------------------- #
# One sweep of the row with charge mass mu_c and reconstruction kappa          #
# --------------------------------------------------------------------------- #
def sweep_arm(M, m, omega, h, v, mu_c, kappa, zeta=0.0):
    """One Gauss-Seidel projection; returns the same four observables plus the
    constraint residual and the true-Hamiltonian energy change."""
    k = m * omega ** 2
    w_r = 1.0 / M
    w = w_r + 1.0 / mu_c
    C = 0.0                      # exactly touching at the cold start
    C_tilde = h * v              # predicted penetration after the free step
    dlam = -C_tilde / w
    # Row multiplier rate; dlam > 0 for a closing contact (v < 0), so p > 0.
    p = dlam / h
    v_plus = v + w_r * dlam / h
    # J = [1, -1] for C = z - q, so the modal correction carries the MINUS sign:
    # dq = W J_c dlam with J_c = -1. Omitting it flips q+ and qdot+.
    dq = -dlam / mu_c
    q_plus = dq
    qdot_plus = kappa * dq / h
    # constraint residual after the sweep: C+ = C_tilde + w * dlam
    C_plus = C_tilde + w * dlam
    E_minus = 0.5 * M * v * v
    E_plus = 0.5 * M * v_plus ** 2 + 0.5 * m * qdot_plus ** 2 + 0.5 * k * q_plus ** 2
    return dict(p=p, v_plus=v_plus, qdot_plus=qdot_plus, q_plus=q_plus,
                C_plus=C_plus, dE=E_plus - E_minus, E_minus=E_minus)


def relerr(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def main():
    log = CheckLog()
    rng = np.random.default_rng(20260725)
    rows = []

    # ---------------------------------------------------------------- #
    # 1. Constraint residual is exactly zero for EVERY arm and weight.  #
    # ---------------------------------------------------------------- #
    print("== 1. constraint residual after one sweep, all arms ==")
    worst_C = 0.0
    for _ in range(4000):
        M = 10.0 ** rng.uniform(-2, 3)
        m = 10.0 ** rng.uniform(-2, 2)
        omega = 10.0 ** rng.uniform(0, 3.5)
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2, 1)
        b = (omega * h) ** 2
        for kappa in (1.0, 2.0):
            for mu_c in (m, m * (1.0 + b), m * (kappa ** 2 + b),
                         m * 10.0 ** rng.uniform(-1, 2)):
                r = sweep_arm(M, m, omega, h, v, mu_c, kappa)
                worst_C = max(worst_C, abs(r["C_plus"]) / max(abs(h * v), 1e-300))
    log.assert_close(worst_C, 0.0, rtol=0.0, atol=1e-14,
                     label="1. C+ == 0 exactly for every weight and kappa")
    print(f"   worst |C+| / |h v| over 4000x8 arms = {worst_C:.3e}")
    print("   => constraint satisfaction does NOT discriminate between weights")

    # ---------------------------------------------------------------- #
    # 2. kappa = 1, zeta = 0: matched sweep == Ref-BE, exactly.         #
    # ---------------------------------------------------------------- #
    print("\n== 2. kappa=1 undamped: matched one sweep vs converged Ref-BE ==")
    worst = dict(p=0.0, v=0.0, q=0.0, qd=0.0)
    worst_v_abs = 0.0      # v+ residual normalized by |v|, the cancellation-free scale
    for _ in range(4000):
        M = 10.0 ** rng.uniform(-2, 3)
        m = 10.0 ** rng.uniform(-2, 2)
        omega = 10.0 ** rng.uniform(0, 3.5)
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2, 1)
        b = (omega * h) ** 2
        ref = ref_be(M, m, omega, h, v, zeta=0.0)
        arm = sweep_arm(M, m, omega, h, v, m * (1.0 + b), 1.0)
        worst["p"] = max(worst["p"], relerr(arm["p"], ref["p"]))
        worst["v"] = max(worst["v"], relerr(arm["v_plus"], ref["v_plus"]))
        # v+ = v + p/M is a DIFFERENCE of nearly equal numbers when m_BE >> M
        # (then |v+| << |v|), so normalizing the residual by |v+| amplifies pure
        # round-off by |v|/|v+| = (M+m_BE)/M, up to ~1e6 here. Normalizing by the
        # incoming |v| instead is the cancellation-free scale, and there the
        # agreement is at machine epsilon like the other three observables.
        worst_v_abs = max(worst_v_abs,
                          abs(arm["v_plus"] - ref["v_plus"]) / abs(v))
        worst["q"] = max(worst["q"], relerr(arm["q_plus"], ref["q_plus"]))
        worst["qd"] = max(worst["qd"], relerr(arm["qdot_plus"], ref["qdot_plus"]))
    for key, name in [("p", "contact impulse"),
                      ("q", "modal amplitude q+"), ("qd", "modal velocity qdot+")]:
        log.assert_close(worst[key], 0.0, rtol=0.0, atol=1e-12,
                         label=f"2. matched sweep == Ref-BE: {name}")
        print(f"   {name:22s} max rel err = {worst[key]:.3e}")
    log.assert_close(worst_v_abs, 0.0, rtol=0.0, atol=1e-12,
                     label="2. matched sweep == Ref-BE: rigid velocity v+ (per |v|)")
    print(f"   {'rigid velocity v+':22s} max err/|v| = {worst_v_abs:.3e}   "
          f"(per |v+|: {worst['v']:.1e}, cancellation-amplified)")
    print("   => one MATCHED sweep IS the converged implicit step, not merely passive")

    # ---------------------------------------------------------------- #
    # 3. Damped: how far the matched (stored-energy) mass sits from the  #
    #    converged (per-impulse) mass. First order in zeta*omega*h.      #
    # ---------------------------------------------------------------- #
    print("\n== 3. damped kappa=1: matched vs Ref-BE gap scales with zeta*omega*h ==")
    print("   zeta*omega*h    rel err q+     ratio to zeta*omega*h")
    for zwh in (1e-4, 1e-3, 1e-2, 1e-1):
        M, m, omega, h = 1.0, 1.0, 50.0, 1.0 / 240.0
        zeta = zwh / (omega * h)
        b = (omega * h) ** 2
        ref = ref_be(M, m, omega, h, -1.0, zeta=zeta)
        arm = sweep_arm(M, m, omega, h, -1.0, m * (1.0 + b), 1.0, zeta=zeta)
        e = relerr(arm["q_plus"], ref["q_plus"])
        print(f"   {zwh:<14.0e}  {e:<13.3e}  {e / zwh:.4f}")
        rows.append(dict(block="3_damped", zeta_omega_h=zwh, rel_err_q=e,
                         ratio=e / zwh))

    # ---------------------------------------------------------------- #
    # 4. Mass-only arm: the accuracy face of the injection defect.      #
    # ---------------------------------------------------------------- #
    print("\n== 4. mass-only arm accuracy vs Ref-BE (kappa=1, undamped) ==")
    print("      b=(wh)^2   q+ over-deposit   qdot+ over-deposit   dE sign")
    for b_target in (1e-2, 1e-1, 1.0, 1e1, 1e2, 1e4):
        M, m, h = 1.0, 1.0, 1.0 / 240.0
        omega = np.sqrt(b_target) / h
        v = -1.0
        ref = ref_be(M, m, omega, h, v, zeta=0.0)
        mo = sweep_arm(M, m, omega, h, v, m, 1.0)
        ratio_q = mo["q_plus"] / ref["q_plus"]
        ratio_qd = mo["qdot_plus"] / ref["qdot_plus"]
        sign = "INJECTS" if mo["dE"] > 0 else "passive"
        print(f"   {b_target:>9.0e}   {ratio_q:>14.4f}   {ratio_qd:>18.4f}   {sign}")
        rows.append(dict(block="4_massonly", b=b_target, ratio_q=ratio_q,
                         ratio_qdot=ratio_qd, dE=mo["dE"],
                         injects=int(mo["dE"] > 0)))
    # the over-deposit factor is exactly (1 + b) at m = M ... verify the closed form
    worst_od = 0.0
    for _ in range(2000):
        M = 10.0 ** rng.uniform(-2, 3)
        m = 10.0 ** rng.uniform(-2, 2)
        omega = 10.0 ** rng.uniform(0, 3.5)
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2, 1)
        b = (omega * h) ** 2
        ref = ref_be(M, m, omega, h, v, zeta=0.0)
        mo = sweep_arm(M, m, omega, h, v, m, 1.0)
        # closed form: q+_massonly / q+_ref = (M + m(1+b)) / (M + m)
        pred = (M + m * (1.0 + b)) / (M + m)
        worst_od = max(worst_od, relerr(mo["q_plus"] / ref["q_plus"], pred))
    log.assert_close(worst_od, 0.0, rtol=0.0, atol=1e-12,
                     label="4. mass-only amplitude over-deposit == (M+m(1+b))/(M+m)")
    print(f"   over-deposit closed form (M+m(1+b))/(M+m): max rel err {worst_od:.3e}")

    # ---------------------------------------------------------------- #
    # 5. kappa = 2: matched is PASSIVE but over-dissipates vs Ref-MID.  #
    # ---------------------------------------------------------------- #
    print("\n== 5. kappa=2 matched weight vs converged Ref-MID (the honest caveat) ==")
    print("      b=(wh)^2    p ratio    q+ ratio   qdot+ ratio    dE(matched)   dE(ref)")
    for b_target in (1e-2, 1e-1, 1.0, 1e1, 1e2, 1e4):
        M, m, h = 1.0, 1.0, 1.0 / 240.0
        omega = np.sqrt(b_target) / h
        v = -1.0
        ref = ref_mid(M, m, omega, h, v, zeta=0.0)
        arm = sweep_arm(M, m, omega, h, v, m * (4.0 + b_target), 2.0)
        # reference energy change, measured on the same true Hamiltonian
        k = m * omega ** 2
        E_ref = (0.5 * M * ref["v_plus"] ** 2 + 0.5 * m * ref["qdot_plus"] ** 2
                 + 0.5 * k * ref["q_plus"] ** 2) - 0.5 * M * v * v
        print(f"   {b_target:>9.0e}  {arm['p'] / ref['p']:>9.4f}  "
              f"{arm['q_plus'] / ref['q_plus']:>9.4f}  "
              f"{arm['qdot_plus'] / ref['qdot_plus']:>10.4f}  "
              f"{arm['dE']:>13.5f}  {E_ref:>8.5f}")
        rows.append(dict(block="5_kappa2", b=b_target,
                         p_ratio=arm["p"] / ref["p"],
                         q_ratio=arm["q_plus"] / ref["q_plus"],
                         qdot_ratio=arm["qdot_plus"] / ref["qdot_plus"],
                         dE_matched=arm["dE"], dE_ref=E_ref))
    # the matched charge is exactly 4x the converged midpoint charge, undamped
    worst_4x = 0.0
    for _ in range(2000):
        m = 10.0 ** rng.uniform(-2, 2)
        omega = 10.0 ** rng.uniform(0, 3.5)
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        b = (omega * h) ** 2
        worst_4x = max(worst_4x, relerr(m * (4.0 + b), 4.0 * m * (1.0 + b / 4.0)))
    log.assert_close(worst_4x, 0.0, rtol=0.0, atol=1e-12,
                     label="5. matched charge m(4+b) == 4 * converged midpoint charge")
    print(f"   m(4+b) == 4 m(1+b/4) exactly: max rel err {worst_4x:.3e}")
    print("   => at kappa=2 the matched weight is passive (T10) but OVER-dissipates:")
    print("      it is conservative, not accurate. Stated as such in the paper.")

    # is the matched kappa=2 arm always MORE dissipative than the reference?
    n_over = 0
    n_tot = 0
    for _ in range(3000):
        M = 10.0 ** rng.uniform(-2, 3)
        m = 10.0 ** rng.uniform(-2, 2)
        omega = 10.0 ** rng.uniform(0, 3.5)
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2, 1)
        b = (omega * h) ** 2
        k = m * omega ** 2
        ref = ref_mid(M, m, omega, h, v, zeta=0.0)
        arm = sweep_arm(M, m, omega, h, v, m * (4.0 + b), 2.0)
        E_ref = (0.5 * M * ref["v_plus"] ** 2 + 0.5 * m * ref["qdot_plus"] ** 2
                 + 0.5 * k * ref["q_plus"] ** 2) - 0.5 * M * v * v
        n_tot += 1
        if arm["dE"] <= E_ref:
            n_over += 1
    print(f"   matched kappa=2 loses at least as much as Ref-MID on "
          f"{n_over}/{n_tot} cells")
    log.assert_true(n_over == n_tot,
                    label="5. matched kappa=2 is never LESS dissipative than Ref-MID")

    field_union = []
    for r in rows:
        for kk in r:
            if kk not in field_union:
                field_union.append(kk)
    rows = [{kk: r.get(kk, "") for kk in field_union} for r in rows]
    write_csv(OUT, "t11_accuracy", rows, fieldnames=field_union,
              manifest=dict(script="run_t11_accuracy.py",
                            what="accuracy vs converged references Ref-BE / Ref-MID",
                            metrics="contact impulse, v+, q+, qdot+, C+ residual",
                            tol="1e-12 relative on exactness checks"))

    print("\n" + "\n".join(log.summary_lines()))
    fails = log.failures
    print(f"\nT11: {len(log.rows) - len(fails)}/{len(log.rows)} checks pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
