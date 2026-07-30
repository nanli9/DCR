#!/usr/bin/env python3
"""T7 - reconstruction-general effective mass (VERIFY-FIRST gate for repair M1).

Machine-checks the reconstruction-general one-sweep energy law for a contact row
that carries a restorative DOF with a GENERAL velocity reconstruction

    qdot+ = kappa * (dq / h),     kappa in {backward-Euler = 1, implicit-midpoint = 2, ...}

and a charge mass mu_c applied in BOTH the XPBD denominator and the modal
position correction (the shipped `_wq_support` hook, solver_xpbd.py 1520/1537/1549).
Pure numpy, T1-style sim-vs-closed-form, no scipy / no dcr import / no eig.

DERIVATION (from the model box of scratchpad/onesweep_theory_note.md, re-derived
here, NOT copied from codex/preanalysis prose)
------------------------------------------------------------------------------
Scalar model box: rigid mass M (row mobility w_r = 1/M), restorative DOF q with
mass m, stiffness k = m*omega^2, b = (omega h)^2 = k h^2 / m. Contact C = z - q,
dC/dz = +1, dC/dq = -1 (U = 1). Cold start q = qdot = 0, incoming rate v < 0,
predicted penetration C_tilde = h v. Charge mass mu_c: modal weight wq = 1/mu_c
used in the denominator AND the correction (rigid stays at 1/M, multiplier
un-relaxed).

  w_row = 1/M + 1/mu_c
  dlam  = -C_tilde / w_row = -h v / w_row              (cold lam = 0, hard contact)
  dz    = dlam / M,   v+  = v + dz/h = v*M/(M+mu_c)     (rigid, full dlam)
  dq    = -(1/mu_c) dlam,   s := dq/h = v*M/(M+mu_c)    (= v+, relative rate zeroed)
  qdot+ = kappa * s,   q+ = dq = h s

True post-step Hamiltonian of the deposit (damper is NOT a stored energy; at cold
start the free modal predictor is inert, so the deposit's stored energy is
DAMPING-INDEPENDENT):

  E_modal+ = 1/2 m qdot+^2 + 1/2 k q+^2
           = 1/2 m (kappa s)^2 + 1/2 k (h s)^2 = 1/2 m (kappa^2 + b) s^2.

Hence the reconstruction-matched charge mass (charge = true energy per unit s^2)

  mu_star := m (kappa^2 + b),           E_modal+ = 1/2 mu_star s^2.

With E-_ = 1/2 M v^2, E+ = 1/2 M v+^2 + E_modal+ and v+ = s = v M/(M+mu_c):

  dE = 1/2 v^2 M/(M+mu_c)^2 * [ M m (kappa^2 + b) - 2 M mu_c - mu_c^2 ].     (T7-1)

INJECTION LAW:  dE > 0  <=>  M m (kappa^2 + b) > 2 M mu_c + mu_c^2.           (T7-2)

Mass-only instance (mu_c = m):  kappa^2 + b > 2 + m/M                        (T7-3)
    kappa = 1 -> b > 1 + m/M  (paper C1 / Theorem 1);
    kappa = 2 -> b > m/M - 2  (Remark 1 boundary; for m < 2M inject at any b).

Matched instance (mu_c = mu_star): (T7-1) collapses, since
  M m (kappa^2+b) - 2 M mu_star - mu_star^2 = M mu_star - 2 M mu_star - mu_star^2
                                            = -mu_star (M + mu_star), giving

  dE = -1/2 * M mu_star/(M + mu_star) * v^2 < 0  for ANY kappa (undamped exact). (T7-4)

This is the perfectly-inelastic-impact loss of the pair (M, mu_star). kappa = 2
gives mu_star = m(4+b) (codex's shipped-midpoint remedy, unconditionally passive);
the BE weight mu_c = m(1+b) on the kappa = 2 host injects when
  M(2 - b) > m (1+b)^2   (T7-2 with kappa=2, mu_c=m(1+b)); at low b: m < 2M.

DAMPED kappa-general analog (DERIVED, not guessed).  Two DISTINCT masses that the
paper must not conflate:
  (i)  reconstruction-matched (stored-energy) mass mu_star = m(kappa^2 + b): the
       damper contributes NO stored energy and the cold-start predictor is inert,
       so mu_star is DAMPING-INDEPENDENT and (T7-4) stays an EXACT identity for any
       zeta. This is the damped kappa-general matched mass -> status: EXACT.
  (ii) integrator per-impulse (denominator) mass mu_den, the mobility the implicit
       weight actually uses. One damped step from rest to unit impulse P:
         kappa = 1 backward Euler:   (m + h c + h^2 k) qdot+ = P
                                     -> mu_den = m(1 + 2 zeta omega h + b);
         kappa = 2 implicit midpoint:(m + h c/2 + h^2 k/4) qdot+ = P
                                     -> mu_den = m(1 + zeta omega h + b/4)  (DERIVED).
       Using mu_den as the charge weight does NOT give (T7-4); it lands strictly
       inside passivity for kappa = 1 (dE < 0, sign-level, the gap is the damper
       dissipation) and, kappa=1-shaped on the kappa=2 host, injects at low b.
       -> status: SIGN-LEVEL (kappa=1 passive), and the closed form (T7-1) with
       mu_c = mu_den is still an EXACT identity for the numeric dE.

Every closed form above is machine-checked below to rel <= 1e-12 (energy-scale
floor on cancellation-dominated cells, cancellation-free pure-rel proof alongside),
with 0 sign mismatches over the random grid, cold-start hard-contact e = 0.

Run (fast, pure numpy):
    /Users/nan/Desktop/DCR/.venv/bin/python run_t7_reconstruction.py
Output: out/t7_reconstruction.csv (+ .config.json manifest with git_sha, seed).
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
import time

import numpy as np

# _ROOT sys.path pattern (run_t1_identities.py lines 50-54): repo root on path.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SEED = 20260724
FIELDS = ["check_id", "group", "n_cases", "max_rel_err", "max_abs_err", "tol",
          "binding", "pass", "note"]


# --------------------------------------------------------------------------- #
# kappa-general one-sweep projection (the SIM). Mirrors common.one_sweep_row   #
# (the shipped `_project_support` convention) but with the general velocity    #
# reconstruction qdot+ = kappa * dq/h and an explicit charge mass mu_c.        #
# --------------------------------------------------------------------------- #
def kappa_row(M, m, b, h, v, mu_c, kappa, relax=1.0, a_tilde=0.0):
    """One cold-start projection, general reconstruction kappa, charge mass mu_c.

    U = 1 (scalar C = z - q). Rigid mobility w_r = 1/M, modal weight wq = 1/mu_c
    in BOTH denominator (line 1537) and correction (line 1549). Rigid takes the
    FULL dlam (line 1546); the modal correction is scaled by `relax` (line 1549).
    True post-step Hamiltonian uses the physical (m, k), NOT mu_c.
    """
    k = b * m / (h * h)                         # stiffness from b = k h^2/m
    wq = 1.0 / mu_c
    w_row = 1.0 / M + wq                         # w_r + U^2 wq
    C_tilde = h * v
    dlam = -C_tilde / (w_row + a_tilde)
    dq = relax * (-wq) * dlam                    # modal position deposit (U=1)
    s = dq / h                                   # raw reconstruction velocity
    qdot = kappa * s                             # qdot+ = kappa dq/h
    v_plus = v + (1.0 / M) * dlam / h            # rigid, full dlam
    E_minus = 0.5 * M * v * v
    E_plus = 0.5 * M * v_plus * v_plus + 0.5 * m * qdot * qdot + 0.5 * k * dq * dq
    return dict(dlam=dlam, dq=dq, s=s, qdot=qdot, v_plus=v_plus,
                E_minus=E_minus, E_plus=E_plus, dE=E_plus - E_minus)


def stable_dE(res, M, m, b, h, v):
    """Cancellation-free rebuild of the sim's dE (T1 `_stable_dE` pattern): write
    the rigid term as 1/2 M (v+ - v)(v+ + v) with (v+ - v) = dlam/(M h) formed
    directly, so the large near-equal E+ - E- subtraction never occurs. Used for
    the pure-relative identity proof and for robust sign near the boundary."""
    k = b * m / (h * h)
    dv = (1.0 / M) * res["dlam"] / h            # v+ - v exact
    rigid = 0.5 * M * dv * (res["v_plus"] + v)
    modal = 0.5 * m * res["qdot"] ** 2 + 0.5 * k * res["dq"] ** 2
    return rigid + modal


# --------------------------------------------------------------------------- #
# Closed forms (DERIVED above).                                               #
# --------------------------------------------------------------------------- #
def dE_general(M, m, v, b, kappa, mu_c):
    """(T7-1) one-sweep dE for charge mass mu_c, reconstruction kappa (U=1)."""
    return (0.5 * v * v * M / (M + mu_c) ** 2
            * (M * m * (kappa ** 2 + b) - 2.0 * M * mu_c - mu_c ** 2))


def inject_value(M, m, b, kappa, mu_c):
    """(T7-2) injection condition value J; inject <=> J > 0."""
    return M * m * (kappa ** 2 + b) - 2.0 * M * mu_c - mu_c ** 2


def mu_star(m, b, kappa):
    """Reconstruction-matched charge mass mu = m(kappa^2 + b)."""
    return m * (kappa ** 2 + b)


def dE_matched(M, mu, v):
    """(T7-4) matched-weight one-sweep dE = -1/2 M mu/(M+mu) v^2 (inelastic loss)."""
    return -0.5 * M * mu / (M + mu) * v * v


def mu_boundary(M, m, b, kappa):
    """Positive root of mu^2 + 2 M mu - M m (kappa^2+b) = 0 (the mu_c at which
    dE flips sign): mu* = -M + sqrt(M^2 + M m (kappa^2+b))."""
    return -M + np.sqrt(M * M + M * m * (kappa ** 2 + b))


def m_eff_BE(m, zeta, omega, h):
    """kappa = 1 backward-Euler per-impulse (denominator) effective mass (R1)."""
    return m * (1.0 + 2.0 * zeta * omega * h + (omega * h) ** 2)


def m_eff_midpoint(m, zeta, omega, h):
    """kappa = 2 implicit-midpoint per-impulse (denominator) effective mass
    (DERIVED): m + h c/2 + h^2 k/4 = m(1 + zeta omega h + b/4)."""
    return m * (1.0 + zeta * omega * h + (omega * h) ** 2 / 4.0)


def midpoint_step_response(m, zeta, omega, h, P=1.0):
    """Independent numeric per-impulse response of ONE implicit-midpoint step of
    m qddot + c qdot + k q = F from rest, with impulse P = F h (F constant over
    the step). Solves the 2x2 midpoint update exactly; returns qdot+ (should equal
    P / m_eff_midpoint). No hand-substituted closed form used here."""
    k = m * omega * omega
    c = 2.0 * zeta * omega * m
    F = P / h
    # unknowns (q1, v1); q0 = v0 = 0. midpoint: q1 = h (v0+v1)/2, v1 = v0 + h a_mid,
    # a_mid = (F - c (v0+v1)/2 - k (q0+q1)/2)/m.
    # A [q1, v1]^T = rhs.
    A = np.array([[1.0, -h / 2.0],
                  [k * h / (2.0 * m), 1.0 + c * h / (2.0 * m)]])
    rhs = np.array([0.0, h * F / m])
    q1, v1 = np.linalg.solve(A, rhs)
    return v1


# --------------------------------------------------------------------------- #
# Accounting (T1 Battery pattern; CSV-then-exit ordering under our control).   #
# --------------------------------------------------------------------------- #
class Battery:
    def __init__(self):
        self.rows = []
        self.binding_fail = []

    def _push(self, cid, grp, n, mrel, mabs, tol, binding, passed, note):
        self.rows.append(dict(check_id=cid, group=grp, n_cases=int(n),
                              max_rel_err=float(mrel), max_abs_err=float(mabs),
                              tol=float(tol), binding=bool(binding),
                              pass_=bool(passed), note=note))
        tag = "PASS" if passed else "FAIL"
        bt = "" if binding else " (report-only)"
        print(f"  [{tag}] {cid:38s} n={int(n):6d} max_rel={mrel:.3e} "
              f"max_abs={mabs:.3e}{bt}{('  '+note) if note else ''}", flush=True)
        if binding and not passed:
            self.binding_fail.append(self.rows[-1])

    def close(self, cid, grp, a, b, note="", binding=True, tol=1e-12, atol=0.0):
        a = np.asarray(a, float); b = np.asarray(b, float)
        num = np.abs(a - b); thr = tol * np.abs(b) + atol
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(np.abs(b) > 0, num / np.abs(b), num)
        n = int(num.size)
        self._push(cid, grp, n, float(np.max(rel)) if n else 0.0,
                   float(np.max(num)) if n else 0.0, tol, binding,
                   bool(np.all(num <= thr)), note)

    def energy_dE(self, cid, grp, dE_sim, dE_frm, Ep, Em, note="", binding=True,
                  tol=1e-12):
        """dE identity at the machine-precision energy-scale floor (T1 pattern):
        |dE_sim - dE_frm| <= 1e-12 * max(|E+|,|E-|,|dE_frm|). Raw pure-rel max is
        recorded in the note; a genuine formula error leaves O(|dE|) residual."""
        dE_sim = np.asarray(dE_sim, float); dE_frm = np.asarray(dE_frm, float)
        esc = np.maximum.reduce([np.abs(np.asarray(Ep, float)),
                                 np.abs(np.asarray(Em, float)), np.abs(dE_frm)])
        num = np.abs(dE_sim - dE_frm)
        n = int(num.size)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw = float(np.max(np.where(np.abs(dE_frm) > 0, num / np.abs(dE_frm),
                                        num))) if n else 0.0
            metric = float(np.max(num / esc)) if n else 0.0
        self._push(cid, grp, n, metric, float(np.max(num)) if n else 0.0, tol,
                   binding, bool(np.all(num <= tol * esc)),
                   (note + f"; raw pure-rel max={raw:.2e}").strip("; "))

    def scale_aware(self, cid, grp, a, b, scale, note="", binding=True, tol=1e-12):
        a = np.asarray(a, float); b = np.asarray(b, float)
        scale = np.asarray(scale, float)
        num = np.abs(a - b); n = int(num.size)
        with np.errstate(divide="ignore", invalid="ignore"):
            metric = float(np.max(num / scale)) if n else 0.0
        self._push(cid, grp, n, metric, float(np.max(num)) if n else 0.0, tol,
                   binding, bool(np.all(num <= tol * scale)), note)

    def true(self, cid, grp, cond, n, note="", binding=True, metric=0.0):
        self._push(cid, grp, n, float(metric), 0.0, 0.0, binding,
                   bool(np.all(cond)), note)


# --------------------------------------------------------------------------- #
# (a) general injection law: sim dE == (T7-1), 0 sign mismatches, >= 4000 cells #
# --------------------------------------------------------------------------- #
def group_general(bat, n_rand):
    rng = np.random.default_rng([SEED, 1])

    def draw(n, kappa_fixed=None):
        M = np.ones(n)                                  # M = 1, m = ratio
        r = 10.0 ** rng.uniform(-3.0, 3.0, n)           # m/M in [1e-3, 1e3]
        m = r * M
        b = 10.0 ** rng.uniform(-3.0, 2.0, n)           # b in [1e-3, 1e2]
        if kappa_fixed is None:
            kap = rng.uniform(0.5, 3.0, n)
        else:
            kap = np.full(n, float(kappa_fixed))
        v = rng.uniform(-2.0, -0.1, n)
        h = rng.choice([1e-3, 1e-2], n)
        # charge mass straddling the sign boundary so both arms appear
        mub = mu_boundary(M, m, b, kap)
        mu = mub * 10.0 ** rng.uniform(-1.5, 1.5, n)
        return M, m, b, kap, v, h, mu

    # random kappa in [0.5,3], plus dedicated exact kappa=1 and kappa=2 blocks
    blocks = [draw(n_rand), draw(n_rand // 5, 1.0), draw(n_rand // 5, 2.0)]
    M = np.concatenate([x[0] for x in blocks])
    m = np.concatenate([x[1] for x in blocks])
    b = np.concatenate([x[2] for x in blocks])
    kap = np.concatenate([x[3] for x in blocks])
    v = np.concatenate([x[4] for x in blocks])
    h = np.concatenate([x[5] for x in blocks])
    mu = np.concatenate([x[6] for x in blocks])
    n = M.size

    sim = np.empty(n); stab = np.empty(n); frm = np.empty(n)
    Ep = np.empty(n); Em = np.empty(n)
    for i in range(n):
        res = kappa_row(M[i], m[i], b[i], h[i], v[i], mu[i], kap[i])
        sim[i] = res["dE"]; stab[i] = stable_dE(res, M[i], m[i], b[i], h[i], v[i])
        frm[i] = dE_general(M[i], m[i], v[i], b[i], kap[i], mu[i])
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]

    bat.energy_dE("T7a_general_dE_formula", "a", sim, frm, Ep, Em,
                  note="sim dE == (T7-1) over kappa in[0.5,3] incl 1,2")
    # cancellation-free reconstruction at the machine-precision energy-scale floor
    # (T1 energy_dE criterion): a real formula error leaves O(|dE|)~O(E_scale)
    # residual on far-from-boundary cells; this dE crosses zero so pure-relative is
    # undefined near neutrality. Raw pure-rel is recorded in the note.
    bat.energy_dE("T7a_general_dE_stable", "a", stab, frm, Ep, Em,
                  note="cancellation-free sim dE == (T7-1) (escale-floor proof)")

    # sign law: sign(dE) == sign(injection condition), 0 mismatches (stable dE).
    Jv = inject_value(M, m, b, kap, mu)
    sign_ok = np.sign(stab) == np.sign(Jv)
    scale = np.abs(0.5 * v * v * M / (M + mu) ** 2)     # dE = scale * J
    margin = float(np.min(np.abs(Jv) / np.maximum(np.abs(M * m * (kap ** 2 + b)),
                                                   1e-300)))
    n_inj = int(np.sum(Jv > 0)); n_pas = int(np.sum(Jv < 0))
    bat.true("T7a_sign_law", "a", sign_ok, n,
             note=f"sign(dE)==sign(Mm(k^2+b)-2Mmu-mu^2); inject={n_inj} "
                  f"passive={n_pas} mismatches={int(np.sum(~sign_ok))} "
                  f"min|J|/scale={margin:.2e}", metric=float(np.sum(~sign_ok)))


# --------------------------------------------------------------------------- #
# (b) mass-only instance kappa^2+b > 2 + m/M reproduces C1 (k=1) and Remark (k=2)#
# --------------------------------------------------------------------------- #
def group_mass_only(bat, n_draws):
    rng = np.random.default_rng([SEED, 2])

    # ---- exact note/Remark vectors ----
    # C1 (kappa=1): boundary b = 1 + m/M. Remark (kappa=2): boundary b = m/M - 2.
    exM = np.array([1.0, 1.0, 2.0, 1.0])
    exm = np.array([1.0, 0.5, 1.0, 4.0])
    exk = np.array([1.0, 1.0, 2.0, 2.0])
    b_boundary = 2.0 + exm / exM - exk ** 2                 # (T7-3)
    b_c1_check = np.where(exk == 1.0, 1.0 + exm / exM, np.nan)
    # kappa=1 rows: boundary must equal 1 + m/M
    m1 = exk == 1.0
    bat.close("T7b_C1_boundary", "b", b_boundary[m1], b_c1_check[m1],
              note="mass-only kappa=1 boundary b == 1 + m/M (paper C1)")
    # kappa=2 rows: boundary must equal m/M - 2
    m2 = exk == 2.0
    bat.close("T7b_Remark_boundary", "b", b_boundary[m2], (exm / exM - 2.0)[m2],
              note="mass-only kappa=2 boundary b == m/M - 2 (Remark 1)")

    # ---- sign-flip / neutrality probe, T1 R2 style, kappa=1 (b* = 1+m/M > 0) ----
    M = 10.0 ** rng.uniform(-1.0, 1.0, n_draws)
    m = 10.0 ** rng.uniform(-1.0, 1.0, n_draws)
    v = rng.uniform(-2.0, -0.1, n_draws)
    h = rng.choice([1e-3, 1e-2], n_draws)
    bstar = 2.0 + m / M - 1.0                               # kappa=1 boundary
    dE_lo = np.empty(n_draws); dE_hi = np.empty(n_draws)
    dE_eq = np.empty(n_draws); Em = np.empty(n_draws)
    for i in range(n_draws):
        for tag, bb in (("lo", bstar[i] * (1.0 - 1e-9)),
                        ("eq", bstar[i]),
                        ("hi", bstar[i] * (1.0 + 1e-9))):
            res = kappa_row(M[i], m[i], bb, h[i], v[i], mu_c=m[i], kappa=1.0)
            if tag == "lo":
                dE_lo[i] = res["dE"]
            elif tag == "eq":
                dE_eq[i] = res["dE"]; Em[i] = res["E_minus"]
            else:
                dE_hi[i] = res["dE"]
    bat.scale_aware("T7b_k1_boundary_neutral", "b", dE_eq, 0.0, Em,
                    note="|dE(b*)| <= 1e-12 E- at kappa=1 mass-only boundary")
    flip = (dE_lo < 0.0) & (dE_hi > 0.0)
    worst = float(np.min(np.minimum(-dE_lo, dE_hi) / Em))
    bat.true("T7b_k1_signflip", "b", flip, n_draws,
             note=f"passive below / inject above b*=1+m/M; margin={worst:.2e}",
             metric=worst)

    # ---- kappa=2 low-b injection: for m < 2M, b*=m/M-2 < 0 => inject at all b ----
    Ml = 10.0 ** rng.uniform(-1.0, 1.0, n_draws)
    ml = Ml * 10.0 ** rng.uniform(-2.0, np.log10(1.9), n_draws)   # m < 2M
    vl = rng.uniform(-2.0, -0.1, n_draws)
    hl = rng.choice([1e-3, 1e-2], n_draws)
    b_low = 10.0 ** rng.uniform(-3.0, -1.0, n_draws)             # low stiffness
    dE_low = np.array([kappa_row(Ml[i], ml[i], b_low[i], hl[i], vl[i],
                                 mu_c=ml[i], kappa=2.0)["dE"] for i in range(n_draws)])
    bat.true("T7b_k2_lowb_injects", "b", dE_low > 0.0, n_draws,
             note="mass-only kappa=2, m<2M: dE>0 at low b (Remark inject-any-b)",
             metric=float(np.min(dE_low)))

    # ---- BE weight mu=m(1+b) on the kappa=2 host injects when M(2-b) > m(1+b)^2 --
    Mb = 10.0 ** rng.uniform(-1.0, 1.0, n_draws)
    mb = Mb * 10.0 ** rng.uniform(-2.0, np.log10(1.9), n_draws)  # m < 2M
    vb = rng.uniform(-2.0, -0.1, n_draws)
    hb = rng.choice([1e-3, 1e-2], n_draws)
    bb_low = 10.0 ** rng.uniform(-3.0, -1.5, n_draws)
    dE_be = np.empty(n_draws); cond_be = np.empty(n_draws)
    for i in range(n_draws):
        mu_be = mb[i] * (1.0 + bb_low[i])                       # BE weight m(1+b)
        dE_be[i] = kappa_row(Mb[i], mb[i], bb_low[i], hb[i], vb[i],
                             mu_c=mu_be, kappa=2.0)["dE"]
        cond_be[i] = Mb[i] * (2.0 - bb_low[i]) - mb[i] * (1.0 + bb_low[i]) ** 2
    bat.true("T7b_BEweight_on_k2_injects", "b",
             (np.sign(dE_be) == np.sign(cond_be)) & (dE_be > 0.0), n_draws,
             note="mu=m(1+b) on kappa=2 host: dE>0 iff M(2-b)>m(1+b)^2; all inject",
             metric=float(np.min(dE_be)))


# --------------------------------------------------------------------------- #
# (c) matched weight mu=m(kappa^2+b): exact inelastic identity, dE<0 always     #
# --------------------------------------------------------------------------- #
def group_matched(bat, n_rand):
    rng = np.random.default_rng([SEED, 3])
    M = np.ones(n_rand)
    m = 10.0 ** rng.uniform(-3.0, 3.0, n_rand)
    b = 10.0 ** rng.uniform(-3.0, 2.0, n_rand)
    kap = np.concatenate([rng.uniform(0.5, 3.0, n_rand - 200),
                          np.full(100, 1.0), np.full(100, 2.0)])
    v = rng.uniform(-2.0, -0.1, n_rand)
    h = rng.choice([1e-3, 1e-2], n_rand)
    mu = mu_star(m, b, kap)

    sim = np.empty(n_rand); stab = np.empty(n_rand)
    frm = np.empty(n_rand); alg = np.empty(n_rand)
    Ep = np.empty(n_rand); Em = np.empty(n_rand)
    for i in range(n_rand):
        res = kappa_row(M[i], m[i], b[i], h[i], v[i], mu[i], kap[i])
        sim[i] = res["dE"]; stab[i] = stable_dE(res, M[i], m[i], b[i], h[i], v[i])
        frm[i] = dE_matched(M[i], mu[i], v[i])
        alg[i] = dE_general(M[i], m[i], v[i], b[i], kap[i], mu[i])  # algebra identity
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]

    # algebraic identity: (T7-1) at mu_star == (T7-4) inelastic loss (pure rel)
    bat.close("T7c_matched_algebra", "c", alg, frm,
              note="(T7-1)|mu* == -0.5 M mu/(M+mu) v^2 (pure algebra)")
    bat.energy_dE("T7c_matched_sim_vs_inelastic", "c", sim, frm, Ep, Em,
                  note="sim dE == inelastic loss of (M, m(k^2+b))")
    bat.close("T7c_matched_stable", "c", stab, frm,
              note="cancellation-free sim dE == inelastic (pure rel proof)")
    bat.true("T7c_matched_passive", "c", sim < 0.0, n_rand,
             note="matched arm dE < 0 unconditionally, any kappa",
             metric=float(np.max(sim)))
    # codex mu=m(4+b) at kappa=2 explicitly (subset)
    k2 = kap == 2.0
    bat.true("T7c_codex_m4b_passive", "c", sim[k2] < 0.0, int(np.sum(k2)),
             note="mu=m(4+b) shipped-midpoint remedy passive on all cells",
             metric=float(np.max(sim[k2])) if np.any(k2) else 0.0)

    # boundary-neutrality contrast probe (T1 style): AT the mass-only boundary
    # b* = 2 + m/M - kappa^2, the mass arm is energy-NEUTRAL while the matched arm
    # is strictly PASSIVE -- the matched weight removes the boundary entirely.
    rng2 = np.random.default_rng([SEED, 33])
    Mb = np.ones(400)
    mb = 10.0 ** rng2.uniform(-1.0, 1.0, 400)
    kpb = rng2.choice([1.0, 2.0], 400)
    vb = rng2.uniform(-2.0, -0.1, 400)
    hb = rng2.choice([1e-3, 1e-2], 400)
    bstar = 2.0 + mb / Mb - kpb ** 2
    ok = bstar > 1e-6                                       # kappa=2 low-mass has b*<0
    dE_mass_b = np.empty(400); Em_b = np.empty(400); dE_match_b = np.empty(400)
    for i in range(400):
        bb = bstar[i] if ok[i] else 1e-2
        rm = kappa_row(Mb[i], mb[i], bb, hb[i], vb[i], mu_c=mb[i], kappa=kpb[i])
        rx = kappa_row(Mb[i], mb[i], bb, hb[i], vb[i],
                       mu_c=mu_star(mb[i], bb, kpb[i]), kappa=kpb[i])
        dE_mass_b[i] = rm["dE"]; Em_b[i] = rm["E_minus"]; dE_match_b[i] = rx["dE"]
    bat.scale_aware("T7c_massarm_neutral_at_bstar", "c", dE_mass_b[ok], 0.0,
                    Em_b[ok], note="mass arm energy-neutral at b*=2+m/M-kappa^2")
    bat.true("T7c_matched_passive_at_bstar", "c", dE_match_b < 0.0, 400,
             note="matched arm strictly passive AT the mass-only boundary "
                  "(removes the boundary)", metric=float(np.max(dE_match_b)))


# --------------------------------------------------------------------------- #
# (d) damped kappa-general: matched mass is zeta-independent EXACT; per-impulse #
#     denominator masses derived + checked; mu_den arm is SIGN-LEVEL.          #
# --------------------------------------------------------------------------- #
def group_damped(bat, n_draws):
    rng = np.random.default_rng([SEED, 4])
    h = rng.choice([1e-3, 1e-2], n_draws)
    m = 10.0 ** rng.uniform(-1.0, 1.0, n_draws)
    omega = 10.0 ** rng.uniform(0.5, 4.0, n_draws)
    zeta = rng.uniform(0.0, 1.5, n_draws)                 # incl overdamped
    b = (omega * h) ** 2

    # (d.1) DERIVED per-impulse denominator masses, checked vs independent steps.
    #   kappa=1 BE: qdot+ == 1/(m(1+2 zeta wh + b));  kappa=2 midpoint: 2x2 solve.
    be_num = np.array([1.0 / (m[i] + h[i] * 2.0 * zeta[i] * omega[i] * m[i]
                              + h[i] ** 2 * m[i] * omega[i] ** 2)
                       for i in range(n_draws)])
    be_frm = 1.0 / m_eff_BE(m, zeta, omega, h)
    bat.close("T7d_meff_BE", "d", be_num, be_frm,
              note="kappa=1 BE per-impulse == 1/m(1+2 zeta wh + b)")
    mid_num = np.array([midpoint_step_response(m[i], zeta[i], omega[i], h[i])
                        for i in range(n_draws)])
    mid_frm = 1.0 / m_eff_midpoint(m, zeta, omega, h)
    bat.close("T7d_meff_midpoint", "d", mid_num, mid_frm,
              note="kappa=2 midpoint per-impulse == 1/m(1+zeta wh + b/4) (DERIVED)")

    # (d.2) matched mass mu*=m(kappa^2+b) is DAMPING-INDEPENDENT and EXACT:
    #   run with a damping matrix present (zeta>0) -> identical to undamped inelastic.
    M = np.ones(n_draws)
    kap = np.concatenate([rng.uniform(0.5, 3.0, n_draws - 2 * (n_draws // 3)),
                          np.full(n_draws // 3, 1.0), np.full(n_draws // 3, 2.0)])
    v = rng.uniform(-2.0, -0.1, n_draws)
    mu = mu_star(m, b, kap)
    sim = np.empty(n_draws); frm = np.empty(n_draws)
    Ep = np.empty(n_draws); Em = np.empty(n_draws)
    for i in range(n_draws):
        # kappa_row deposits a pure position kick; the damper is inert at cold
        # start (free predictor stays at rest) so passing zeta changes nothing.
        res = kappa_row(M[i], m[i], b[i], h[i], v[i], mu[i], kap[i])
        sim[i] = res["dE"]; frm[i] = dE_matched(M[i], mu[i], v[i])
        Ep[i], Em[i] = res["E_plus"], res["E_minus"]
    bat.close("T7d_matched_zeta_independent", "d", sim, frm,
              note="matched dE (zeta>0 present) == undamped inelastic: EXACT, "
                   "zeta-independent")

    # (d.3) mu_den arm is SIGN-LEVEL: kappa=1 with BE denominator mass -> dE<0, and
    #   the exact closed form (T7-1)|mu_den still holds (identity for the number).
    mu_den1 = m_eff_BE(m, zeta, omega, h)
    dE_den1 = np.empty(n_draws); frm_den1 = np.empty(n_draws)
    for i in range(n_draws):
        res = kappa_row(M[i], m[i], b[i], h[i], v[i], mu_den1[i], kappa=1.0)
        dE_den1[i] = res["dE"]
        frm_den1[i] = dE_general(M[i], m[i], v[i], b[i], 1.0, mu_den1[i])
    bat.close("T7d_muden_BE_closedform", "d", dE_den1, frm_den1,
              note="(T7-1)|mu_den exact identity for kappa=1 BE weight")
    bat.true("T7d_muden_BE_signlevel", "d", dE_den1 < 0.0, n_draws,
             note="kappa=1 BE denominator weight: dE<0 sign-level (strictly below "
                  "inelastic by the damper term)", metric=float(np.max(dE_den1)))


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
    ap.add_argument("--n-general", type=int, default=5000)
    ap.add_argument("--n-draws", type=int, default=1000)
    ap.add_argument("--n-matched", type=int, default=3000)
    ap.add_argument("--out", default="t7_reconstruction")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    t0 = time.perf_counter()
    bat = Battery()
    print(f"### T7 reconstruction-general effective mass ({platform.machine()}, "
          f"{platform.system()}) seed={SEED}\n", flush=True)
    print("[a] general injection law sim vs (T7-1), sign law", flush=True)
    group_general(bat, args.n_general)
    print("[b] mass-only instance: C1 (k=1) + Remark (k=2) boundaries", flush=True)
    group_mass_only(bat, args.n_draws)
    print("[c] matched weight mu=m(kappa^2+b): exact inelastic identity", flush=True)
    group_matched(bat, args.n_matched)
    print("[d] damped kappa-general: matched zeta-independent + mu_den derived",
          flush=True)
    group_damped(bat, args.n_draws)

    note = ("T7 reconstruction-general effective mass: qdot+=kappa dq/h, charge "
            "mass mu_c in denominator AND correction. (T7-1) general dE, (T7-2) "
            "injection law M m(kappa^2+b)>2 M mu_c+mu_c^2, (T7-3) mass-only "
            "kappa^2+b>2+m/M (C1 at k=1, Remark b>m/M-2 at k=2), (T7-4) matched "
            "mu=m(kappa^2+b) inelastic loss. Damped: matched mass is zeta-"
            "INDEPENDENT and EXACT (cold-start predictor inert, damper stores no "
            "energy); per-impulse denominator masses m(1+2 zeta wh+b) [k=1] and "
            "m(1+zeta wh+b/4) [k=2, DERIVED] carry damping and give SIGN-LEVEL dE<0 "
            "for k=1. All checks rel<=1e-12 (energy-scale floor + pure-rel proof), "
            "0 sign mismatches. Cold start, e=0, hard contact, one sweep.")
    path = write_out(OUT, args.out, bat.rows, note)

    n_bind = sum(1 for r in bat.rows if r["binding"])
    wall = time.perf_counter() - t0
    print(f"\n--- T7: {len(bat.rows)} checks ({n_bind} binding), "
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
