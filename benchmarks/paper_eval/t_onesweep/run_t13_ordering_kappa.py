#!/usr/bin/env python3
"""T13 -- reconstruction-general Gauss-Seidel ordering (kappa carried through T5).

WHY THIS SCRIPT EXISTS. run_t5_ordering.py validates the ordering result at ONE
velocity reconstruction only: it contains no kappa (it hardcodes qdot+ = dq/h,
i.e. backward Euler, kappa = 1) and its default stiffness ladder
DEF_B = [0.25, 1.0, 4.0, 100.0] floors b = (omega h)^2 at 0.25. The trailing-
spring passivity add-on attached to the ordering proposition ("order A is in
addition one-sweep passive") is therefore validated only on the kappa = 1 slice
and only above b = 0.25. Both restrictions matter: the add-on is UNCONDITIONALLY
TRUE at kappa = 1 (one line, below) and FALSE at the shipped symplectic default
kappa = 2 inside a low-stiffness band that starts below b = 0.25. This script
carries kappa through the T5 toy, extends b down to 1e-3, maps the band, and
certifies its edge in exact rational arithmetic.

run_t5_ordering.py is NOT edited. It is imported here and re-run cell by cell as
a provenance check (block P): the kappa-general sweep at kappa = 1 must return
run_t5's numbers bit for bit, and must equal the shipped out/t5_ordering.csv.

MODEL (identical to T5 apart from the reconstruction). DOFs (z, q). Rigid mass M
at z, restorative DOF q with mass m and stiffness k = b m / h^2. Rows:
    contact  C_c = z - q   (hard, unilateral, a_tilde = 0)
    spring   C_s = q       (compliant, alpha_s = 1/k -> a_tilde_s = 1/(k h^2))
Cold start z = q = qdot = 0, incoming rate v < 0, predicted (z~, q~) = (h v, 0),
multipliers 0. Order A = [contact, spring] (trailing spring), order B =
[spring, contact] (spring is a no-op from rest, so B reproduces the one-row R2
result). Reconstruction: the rigid DOF always reads back zdot+ = dz/h; the
restorative DOF reads back
    qdot+ = kappa * dq / h,     kappa = 1 backward Euler, 2 implicit midpoint,
with dq the NET position change of q over the whole sweep (T7 convention,
run_t7_reconstruction.py lines 116-135). True post-step Hamiltonian
E+ = 1/2 M zdot+^2 + 1/2 m qdot+^2 + 1/2 k q+^2, E- = 1/2 M v^2.

DERIVATION (n = 1, cold start; all four forms re-derived here from the model box
and checked against common.r5_* at kappa = 1).
Let g = v M/(M+m).  Contact solve: dlam_c = -h v/(1/M + 1/m) > 0, giving
z1 = h g and q1 = h g (the gap closes exactly).
Order B: the spring sees q~ = 0 and lam_s = 0, so dlam_s = 0 and it is inert;
the contact solve is then the plain one-row solve, dq = h g, hence
    D_B(kappa) = 1/2 m (kappa g)^2 + 1/2 k (h g)^2 = 1/2 m g^2 (kappa^2 + b),
    E+_B       = 1/2 M g^2 + D_B.                                       (T13-1)
Order A: the trailing spring row relaxes the fresh q1 = h g. With w_s = 1/m and
a_tilde_s = 1/(b m), dlam_s = -h g/(1/m + 1/(b m)) = -h g b m/(1+b), so
q+ = h g - h g b/(1+b) = h g/(1+b); z is untouched, dq = h g/(1+b). Hence
    D_A(kappa) = 1/2 m g^2 (kappa^2 + b)/(1+b)^2,
    E+_A       = 1/2 M g^2 + D_A.                                       (T13-2)
    D_B/D_A    = (1+b)^2   EXACTLY, for EVERY kappa.                    (T13-3)
So the ordering divisor of the paper's proposition is kappa-independent; only the
passivity add-on is not. Subtracting E- = 1/2 M v^2 and using g = v M/(M+m),
    dE_A = 1/2 v^2 M m/(M+m)^2 * [ M (kappa^2+b)/(1+b)^2 - 2M - m ],
    dE_B = 1/2 v^2 M m/(M+m)^2 * [ M (kappa^2+b)          - 2M - m ],   (T13-4)
i.e. order A is order B with (kappa^2+b) divided by (1+b)^2:
    INJECTION A  <=>  (kappa^2 + b)/(1+b)^2 > 2 + m/M,
    INJECTION B  <=>   kappa^2 + b          > 2 + m/M.                  (T13-5)
(T13-5B at kappa = 1 is b > 1 + m/M, the paper's Theorem 1; at kappa = 2 it is
b > m/M - 2, the paper's reconstruction remark. Both are reproduced in block B.)

CONSEQUENCES OF (T13-5A), the point of this script.
(a) kappa = 1: the left side is (1+b)/(1+b)^2 = 1/(1+b) <= 1 < 2 + m/M for every
    b >= 0 and every m, M > 0. Order A is one-sweep passive UNCONDITIONALLY, in
    one line. The paper's "we do not prove this in closed form" is unnecessary.
(b) With s := 2 + m/M, (T13-5A) is the quadratic
        s b^2 + (2s - 1) b + (s - kappa^2) < 0,
    whose positive root exists iff kappa^2 > s = 2 + m/M, i.e. iff
        m/M < kappa^2 - 2.                                              (T13-6)
    Then order A injects exactly on the band 0 <= b < b*, with (cancellation-free
    conjugate form; the naive [sqrt(D) - (2s-1)]/(2s) cancels as kappa^2 -> s)
        b*(kappa, m/M) = 2 (kappa^2 - s) / ( sqrt(1 + 4 s (kappa^2 - 1)) + 2s - 1 ).
                                                                        (T13-7)
    kappa = 1 gives kappa^2 - s < 0: empty band, consistent with (a).
    kappa = 2 gives a band whenever m < 2M; at m = M, b* = 2/(sqrt(37)+5)
    = (sqrt(37) - 5)/6 = 0.1804604...
(c) The trailing spring is therefore still worth something at kappa = 2: order B
    injects at EVERY b once m < 2M, while order A injects only on b < b*. The
    divisor narrows an unconditional injection to a bounded low-stiffness band;
    it is not a passivity certificate off kappa = 1.
(d) SIZE of the order-A violation. From (T13-4), dE_A/|E-| = (m/M)(M f - 2M - m)/
    (M(1 + m/M)^2) with f = (kappa^2+b)/(1+b)^2. It is largest as b -> 0, where
    f -> kappa^2 and, writing c = kappa^2 - 2 and mu = m/M,
        dE_A/|E-| -> mu (c - mu)/(1 + mu)^2,
    maximized at mu* = c/(c+2) with value
        sup dE_A/|E-| = c^2 / (4 (c + 1)) = (kappa^2-2)^2 / (4 (kappa^2-1)).  (T13-8)
    kappa = 2 gives exactly 1/3 at m = M/2: the trailing-spring order can add a
    third of the incoming kinetic energy in ONE sweep. Block F checks (T13-8).

TOLERANCES (nothing is loosened; the cancellation-limited cells are decided
exactly instead). Three separate criteria are used, each at the tightest value
it can be posed at:
  (1) SCALE-NORMALIZED residual |dE_measured - dE_closed_form| / (E_- + E_+)
      <= 1e-14 on ALL 40,000 float cells of the map. E_- + E_+ is a sum of
      positive terms and carries no cancellation at any b, so this criterion is
      posable everywhere. ACHIEVED: worst 8.0e-16.
  (2) PURE-RELATIVE agreement at rtol 1e-12 on the 39,956 of 40,000 cells whose
      injection margin |N|/S is at least 1e-3. ACHIEVED: worst 1.9e-13. It is NOT
      posed on the remaining 44 cells, which lie within 1e-3 relative of the
      boundary, because the injection value
          N(b) = M(kappa^2 + b) - (2M + m)(1 + b)^2
      has a root at b*, and |N|/S is exactly the relative cancellation in dE
      itself, so NO float evaluation of either side retains relative accuracy
      there. That is inherent conditioning, not a loose check: at the grid's
      closest approach (|N|/S = 1.5e-5) the attainable relative accuracy is about
      1e-16/1.5e-5 = 7e-12, and a 1e-12 check on those cells fails at 2e-12, i.e.
      exactly at the conditioning floor. The floor is closed by (3), not loosened.
  (3) EXACT rational arithmetic (fractions.Fraction, block D), ZERO tolerance,
      600 cells (300 per order), the same device run_t10_multimode.py uses to
      close its operator claim. This includes cells placed 1e-9 either side of
      b*, six orders of magnitude further inside the float-undecidable region
      than any map cell: there the exact sign of dE and the exact sign of N must
      agree, and the two straddling cells must disagree with each other, which
      certifies b* as the true edge. Same for the order-B edge 2 + m/M - kappa^2
      (13 edges), which at kappa = 1 is the paper's Theorem 1 boundary.
Sign agreement (measured vs predicted) is asserted outside a relative dead band
of 1e-9 in N, the convention Table 1 of the paper already uses for T2/T3/T7/T8;
that dead band is reported EMPTY on the shipped grid (min margin 1.5e-5).

Run:
  /Users/nan/Desktop/DCR/.venv/bin/python \
      benchmarks/paper_eval/t_onesweep/run_t13_ordering_kappa.py
"""
from __future__ import annotations

import argparse
import os
import sys
from fractions import Fraction as F

import numpy as np

# _ROOT sys.path pattern (run_t5_ordering.py lines 41-45): repo root on path so
# this runs from any cwd.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C           # noqa: E402
from benchmarks.paper_eval.t_onesweep import run_t5_ordering as T5  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

V0 = -1.0
H = 1.0e-3
DEADBAND = 1.0e-9          # relative dead band for sign checks (Table 1 convention)
RTOL = 1.0e-12             # binding PURE-RELATIVE closed-form tolerance
RESID_TOL = 1.0e-14        # binding SCALE-NORMALIZED residual tolerance, |.|/E_minus
MARGIN_REL = 1.0e-3        # margin above which the pure-relative check is posable
NB = 100                   # b samples in the map
NMU = 100                  # m/M samples in the map
B_LO, B_HI = 1.0e-3, 1.0e2
MU_LO, MU_HI = 1.0e-2, 1.0e1
KAPPAS = [1.0, 2.0]
CONV_CAP = 100_000


# --------------------------------------------------------------------------- #
# 1. kappa-general two-row sweep (T5 toy + T7 reconstruction).                 #
# --------------------------------------------------------------------------- #
def two_row_run_kappa(M, m, v, b, h, order, kappa, n=1, converge=False,
                      cap=CONV_CAP, state_tol=1e-15):
    """T5's two_row_run with the velocity reconstruction qdot+ = kappa*dq/h.

    At kappa = 1.0 every arithmetic operation is identical to T5's (the only
    added operation is a multiplication by the float 1.0, which is exact), so
    block P below expects BIT-IDENTICAL agreement, not merely 1e-15.

    Returns E_plus/E_minus/dE (naive), dE_stable (cancellation-free, used for
    sign), the modal deposit D, the multipliers, the contact gap and n_used.
    """
    k = b * m / h ** 2
    Minv = np.array([1.0 / M, 1.0 / m])
    a_tilde_s = 1.0 / (k * h * h)
    x_start = np.array([0.0, 0.0])
    x = np.array([h * v, 0.0])                              # predicted (z~, q~)
    Jc = np.array([1.0, -1.0]); wc = 1.0 / M + 1.0 / m      # C_c = z - q
    Js = np.array([0.0, 1.0]); ws = 1.0 / m                 # C_s = q
    lam_c = 0.0
    lam_s = 0.0
    rows = ["c", "s"] if order == "A" else ["s", "c"]

    def sweep_once(x, lam_c, lam_s):
        for rw in rows:
            if rw == "c":
                Cval = float(Jc @ x)
                dlam, lam_c = C.local_solve(Cval, lam_c, wc, 0.0, unilateral=True)
                x = x + Minv * Jc * dlam
            else:
                Cval = float(Js @ x)
                dlam, lam_s = C.local_solve(Cval, lam_s, ws, a_tilde_s, unilateral=False)
                x = x + Minv * Js * dlam
        return x, lam_c, lam_s

    hit_cap = False
    if converge:
        # DEVIATION (T5 docstring, "Endpoints and interior"): the converged
        # endpoint is detected on the STATE increment settling to the machine
        # floor, the strictly stronger criterion T5 already adopted, not on
        # max|dlam| < 1e-14 which stops on the geometric tail.
        n_used = 0
        while True:
            x_prev = x.copy()
            x, lam_c, lam_s = sweep_once(x, lam_c, lam_s)
            n_used += 1
            d_state = float(np.max(np.abs(x - x_prev)))
            scale = max(float(np.max(np.abs(x))), 1e-300)
            if d_state <= state_tol * scale:
                break
            if n_used >= cap:
                hit_cap = True
                break
    else:
        n_used = n
        for _ in range(n):
            x, lam_c, lam_s = sweep_once(x, lam_c, lam_s)

    dz = float(x[0] - x_start[0])
    dq = float(x[1] - x_start[1])
    zdot = dz / h
    qdot = kappa * (dq / h)                    # T7 convention: kappa on q only
    q = float(x[1])
    E_minus = 0.5 * M * v * v
    E_plus = 0.5 * M * zdot ** 2 + 0.5 * m * qdot ** 2 + 0.5 * k * q ** 2
    D = 0.5 * m * qdot ** 2 + 0.5 * k * q ** 2
    # Cancellation-free dE (T7 `stable_dE` pattern). Only the contact row moves
    # z, so the total rigid impulse is lam_c and dv = zdot - v = lam_c/(M h) is
    # formed directly instead of by subtracting two nearly equal energies.
    dv = lam_c / (M * h)
    dE_stable = 0.5 * M * dv * (zdot + v) + D
    return dict(E_plus=E_plus, E_minus=E_minus, dE=E_plus - E_minus,
                dE_stable=dE_stable, D=D, lam_c=lam_c, lam_s=lam_s,
                Cc=float(x[0] - x[1]), zdot=zdot, qdot=qdot, q=q, z=float(x[0]),
                n_used=n_used, hit_cap=hit_cap)


# --------------------------------------------------------------------------- #
# 2. Closed forms (T13-1 .. T13-7 above).                                      #
# --------------------------------------------------------------------------- #
def t12_D_B(M, m, v, b, kappa):
    """(T13-1) order B modal deposit: 1/2 v^2 (M/(M+m))^2 m (kappa^2+b)."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * m * (kappa ** 2 + b)


def t12_E_plus_B(M, m, v, b, kappa):
    """(T13-1) order B post-step energy."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * (M + m * (kappa ** 2 + b))


def t12_D_A(M, m, v, b, kappa):
    """(T13-2) order A modal deposit: order B's divided by (1+b)^2."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * m * (kappa ** 2 + b) / (1.0 + b) ** 2


def t12_E_plus_A(M, m, v, b, kappa):
    """(T13-2) order A post-step energy."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * (
        M + m * (kappa ** 2 + b) / (1.0 + b) ** 2)


def t12_ratio_DB_DA(b):
    """(T13-3) deposit ratio (1+b)^2, exact and kappa-independent."""
    return (1.0 + b) ** 2


def t12_dE(M, m, v, b, kappa, order):
    """(T13-4) one-sweep dE at n = 1."""
    f = (kappa ** 2 + b) / (1.0 + b) ** 2 if order == "A" else (kappa ** 2 + b)
    return 0.5 * v * v * M * m / (M + m) ** 2 * (M * f - 2.0 * M - m)


def t12_inject_value(M, m, b, kappa, order):
    """(T13-5) injection value N; inject <=> N > 0.

        order A:  N = M(kappa^2+b) - (2M+m)(1+b)^2
        order B:  N = M(kappa^2+b) - (2M+m)
    """
    if order == "A":
        return M * (kappa ** 2 + b) - (2.0 * M + m) * (1.0 + b) ** 2
    return M * (kappa ** 2 + b) - (2.0 * M + m)


def t12_inject_scale(M, m, b, kappa, order):
    """Sum of the two competing positive terms of N, for the relative dead band."""
    if order == "A":
        return M * (kappa ** 2 + b) + (2.0 * M + m) * (1.0 + b) ** 2
    return M * (kappa ** 2 + b) + (2.0 * M + m)


def t12_band_exists(M, m, kappa):
    """(T13-6) order A has a nonempty injecting band iff kappa^2 > 2 + m/M."""
    return kappa ** 2 > 2.0 + m / M


def t12_b_star(M, m, kappa):
    """(T13-7) upper edge of the order-A injecting band, cancellation-free form.
    Returns nan when the band is empty (kappa^2 <= 2 + m/M)."""
    s = 2.0 + m / M
    if kappa ** 2 <= s:
        return float("nan")
    disc = 1.0 + 4.0 * s * (kappa ** 2 - 1.0)
    return 2.0 * (kappa ** 2 - s) / (np.sqrt(disc) + 2.0 * s - 1.0)


def t12_sup_ratio(kappa):
    """(T13-8) supremum of dE_A/|E-| over the order-A band: (k^2-2)^2/(4(k^2-1)),
    approached as b -> 0 at m/M = (kappa^2-2)/kappa^2. 1/3 at kappa = 2."""
    c = kappa ** 2 - 2.0
    return c * c / (4.0 * (kappa ** 2 - 1.0))


def t12_sup_mu(kappa):
    """(T13-8) the mass ratio attaining the supremum: (kappa^2-2)/kappa^2."""
    return (kappa ** 2 - 2.0) / kappa ** 2


def t12_b_star_B(M, m, kappa):
    """Order B band edge: injection iff b > 2 + m/M - kappa^2 (nan if all b)."""
    thr = 2.0 + m / M - kappa ** 2
    return thr if thr > 0.0 else float("nan")


# --------------------------------------------------------------------------- #
# 3. Exact rational sweep (block D). Same algebra, fractions.Fraction.        #
# --------------------------------------------------------------------------- #
def two_row_run_exact(M, m, v, b, h, order, kappa):
    """n = 1 two-row sweep in exact rational arithmetic. All inputs Fractions.

    Mirrors two_row_run_kappa line for line; the only change is the number type,
    so no rounding occurs anywhere between the inputs and sign(dE).
    """
    k = b * m / (h * h)
    a_ts = F(1, 1) / (k * h * h)
    z = h * v
    q = F(0, 1)
    lam_c = F(0, 1)
    lam_s = F(0, 1)
    rows = ["c", "s"] if order == "A" else ["s", "c"]
    for rw in rows:
        if rw == "c":
            Cval = z - q
            dlam = -Cval / (F(1, 1) / M + F(1, 1) / m)
            new = lam_c + dlam
            if new < 0:                       # unilateral clamp
                new = F(0, 1)
            dlam = new - lam_c
            lam_c = new
            z += dlam / M
            q -= dlam / m
        else:
            Cval = q
            dlam = (-Cval - a_ts * lam_s) / (F(1, 1) / m + a_ts)
            lam_s += dlam
            q += dlam / m
    zdot = z / h
    qdot = kappa * q / h
    E_minus = F(1, 2) * M * v * v
    E_plus = F(1, 2) * M * zdot * zdot + F(1, 2) * m * qdot * qdot + F(1, 2) * k * q * q
    D = F(1, 2) * m * qdot * qdot + F(1, 2) * k * q * q
    return dict(E_plus=E_plus, E_minus=E_minus, dE=E_plus - E_minus, D=D,
                lam_c=lam_c, q=q, zdot=zdot, qdot=qdot)


def t12_inject_value_exact(M, m, b, kappa, order):
    """(T13-5) injection value in exact arithmetic; inject <=> N > 0."""
    if order == "A":
        return M * (kappa * kappa + b) - (2 * M + m) * (1 + b) ** 2
    return M * (kappa * kappa + b) - (2 * M + m)


def t12_dE_exact(M, m, v, b, kappa, order):
    """(T13-4) dE in exact arithmetic."""
    f = ((kappa * kappa + b) / (1 + b) ** 2 if order == "A" else (kappa * kappa + b))
    return F(1, 2) * v * v * M * m / (M + m) ** 2 * (M * f - 2 * M - m)


def _sgn(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


def _rel(a, b):
    d = max(abs(a), abs(b))
    return abs(a - b) / d if d > 0 else abs(a - b)


# --------------------------------------------------------------------------- #
def parse_args():
    p = argparse.ArgumentParser(
        description="T13 reconstruction-general GS ordering (kappa through T5).")
    p.add_argument("--nb", type=int, default=NB, help="b samples in the map")
    p.add_argument("--nmu", type=int, default=NMU, help="m/M samples in the map")
    p.add_argument("--h", type=float, default=H)
    p.add_argument("--no-exact", action="store_true", help="skip block D")
    p.add_argument("--out", default="t13_ordering_kappa", help="CSV basename")
    return p.parse_args()


def main():
    args = parse_args()
    h = float(args.h)
    v = V0
    clog = C.CheckLog()
    rows = []

    # ===================================================================== #
    # BLOCK P -- provenance: kappa = 1 must reproduce run_t5_ordering.py.   #
    # ===================================================================== #
    worst_p = 0.0
    n_p = 0
    for (M, m) in T5.DEF_MM:
        for b in T5.DEF_B:
            for order in T5.DEF_ORDERS:
                for n in T5.DEF_N:
                    r5 = T5.two_row_run(M, m, v, b, h, order, n=n)
                    r12 = two_row_run_kappa(M, m, v, b, h, order, 1.0, n=n)
                    for key in ("E_plus", "dE", "D", "lam_c", "lam_s", "Cc"):
                        d = abs(r5[key] - r12[key])
                        worst_p = max(worst_p, d)
                        n_p += 1
                # converged endpoint
                rc5 = T5.two_row_run(M, m, v, b, h, order, converge=True)
                rc12 = two_row_run_kappa(M, m, v, b, h, order, 1.0, converge=True)
                for key in ("E_plus", "dE", "D", "lam_c", "lam_s"):
                    d = abs(rc5[key] - rc12[key])
                    worst_p = max(worst_p, d)
                    n_p += 1
                rows.append(dict(
                    block="P", arith="float", kappa=1.0, M=M, m=m, b=b, order=order,
                    n=rc12["n_used"], E_plus=rc12["E_plus"], dE=rc12["dE"],
                    dE_stable=rc12["dE_stable"], dE_form="", D_modal=rc12["D"],
                    D_form="", ratio_DB_DA="", inject_meas=rc12["dE_stable"] > 0.0,
                    inject_pred="", margin_rel="", b_star="",
                    note="converged endpoint, kappa=1, matches T5"))
    clog.assert_true(worst_p == 0.0,
                     label=f"(P) kappa=1 reproduces run_t5_ordering.py BIT-IDENTICALLY "
                           f"on {n_p} compared quantities (max abs diff {worst_p:.1e})")

    # shipped CSV round-trip (t5_ordering.csv, git_sha of the T-suite run)
    import csv as _csv
    t5_csv = os.path.join(OUT, "t5_ordering.csv")
    worst_csv = 0.0
    n_csv = 0
    if os.path.exists(t5_csv):
        with open(t5_csv) as fh:
            for rec in _csv.DictReader(fh):
                if rec["converged_flag"] == "True":
                    continue
                M, m, b = float(rec["M"]), float(rec["m"]), float(rec["b"])
                r12 = two_row_run_kappa(M, m, v, b, h, rec["order"], 1.0,
                                        n=int(rec["n"]))
                for key, col in (("E_plus", "E_plus"), ("dE", "dE"),
                                 ("D", "D_modal"), ("lam_c", "lam_c"),
                                 ("lam_s", "lam_s")):
                    worst_csv = max(worst_csv, abs(r12[key] - float(rec[col])))
                    n_csv += 1
        clog.assert_true(worst_csv == 0.0,
                         label=f"(P) kappa=1 reproduces the SHIPPED t5_ordering.csv "
                               f"exactly on {n_csv} values (max abs diff {worst_csv:.1e})")
    else:
        clog.assert_true(False, label="(P) t5_ordering.csv present")

    # ===================================================================== #
    # BLOCK A -- closed forms (T13-1..T13-4) at n = 1 over a kappa grid.    #
    # ===================================================================== #
    rng = np.random.default_rng(20260726)
    kap_grid = list(np.concatenate([
        np.array([1.0, 2.0, np.sqrt(2.0), 3.0]),
        rng.uniform(0.5, 3.0, 16)]))
    acc = {k: ([], []) for k in ("E+_A", "D_A", "E+_B", "D_B", "ratio")}
    for kappa in kap_grid:
        for (M, m) in [(1.0, 1.0), (1.0, 0.01), (1.0, 5.0), (7.0, 0.3), (0.2, 0.9)]:
            for b in [1e-3, 1e-2, 0.1, 0.25, 1.0, 4.0, 100.0]:
                rA = two_row_run_kappa(M, m, v, b, h, "A", kappa, n=1)
                rB = two_row_run_kappa(M, m, v, b, h, "B", kappa, n=1)
                for key, meas, form in (
                        ("E+_A", rA["E_plus"], t12_E_plus_A(M, m, v, b, kappa)),
                        ("D_A", rA["D"], t12_D_A(M, m, v, b, kappa)),
                        ("E+_B", rB["E_plus"], t12_E_plus_B(M, m, v, b, kappa)),
                        ("D_B", rB["D"], t12_D_B(M, m, v, b, kappa)),
                        ("ratio", rB["D"] / rA["D"], t12_ratio_DB_DA(b))):
                    acc[key][0].append(meas)
                    acc[key][1].append(form)
    n_A = sum(len(x[0]) for x in acc.values())
    lbl = {"E+_A": "(A) E+_A == (T13-2)", "D_A": "(A) D_A == (T13-2)",
           "E+_B": "(A) E+_B == (T13-1)", "D_B": "(A) D_B == (T13-1)",
           "ratio": "(A) D_B/D_A == (1+b)^2 (T13-3), kappa-independent"}
    for key, (meas, form) in acc.items():
        clog.assert_close(np.array(meas), np.array(form), rtol=RTOL,
                          label=f"{lbl[key]} on {len(meas)} cells")
    print(f"[A] {n_A} closed-form checks at rtol {RTOL:.0e} over "
          f"{len(kap_grid)} kappa values")

    # ===================================================================== #
    # BLOCK B -- the (b, m/M) map at kappa in {1, 2}, orders A and B.       #
    # ===================================================================== #
    bs = np.geomspace(B_LO, B_HI, args.nb)
    mus = np.geomspace(MU_LO, MU_HI, args.nmu)
    n_cells = args.nb * args.nmu
    M = 1.0
    counts = {}
    worst_dE_rel = 0.0
    worst_dE_cell = None
    min_margin = np.inf
    n_deadband = 0
    n_sign = 0
    peak = {}
    for kappa in KAPPAS:
        for order in ("A", "B"):
            n_inj = 0
            n_mismatch = 0
            worst_rel_cell_group = 0.0     # pure relative, margin >= MARGIN_REL
            worst_resid_group = 0.0        # |dE_meas - dE_form|/E_minus, ALL cells
            n_relposable = 0
            peak_ratio = -np.inf
            peak_cell = None
            for mu in mus:
                m = mu * M
                for b in bs:
                    r = two_row_run_kappa(M, m, v, b, h, order, kappa, n=1)
                    dE_form = t12_dE(M, m, v, b, kappa, order)
                    N = t12_inject_value(M, m, b, kappa, order)
                    S = t12_inject_scale(M, m, b, kappa, order)
                    margin = abs(N) / S
                    min_margin = min(min_margin, margin)
                    inj_meas = r["dE_stable"] > 0.0
                    inj_pred = N > 0.0
                    # (1) scale-normalized residual: posable on EVERY cell,
                    #     because E_minus + E_plus is a sum of positive terms and
                    #     so carries no cancellation at any b.
                    resid = (abs(r["dE_stable"] - dE_form)
                             / (r["E_minus"] + r["E_plus"]))
                    worst_resid_group = max(worst_resid_group, resid)
                    # (2) pure relative: only posable where dE itself is not a
                    #     near-total cancellation, i.e. away from N(b) = 0.
                    if margin >= MARGIN_REL:
                        n_relposable += 1
                        rel = _rel(r["dE_stable"], dE_form)
                        worst_rel_cell_group = max(worst_rel_cell_group, rel)
                        if rel > worst_dE_rel:
                            worst_dE_rel = rel
                            worst_dE_cell = (kappa, order, mu, b)
                    if margin >= DEADBAND:
                        n_sign += 1
                        if inj_meas != inj_pred:
                            n_mismatch += 1
                    else:
                        n_deadband += 1
                    if inj_meas:
                        n_inj += 1
                        ratio = r["dE_stable"] / r["E_minus"]
                        if ratio > peak_ratio:
                            peak_ratio = ratio
                            peak_cell = (mu, b)
                    rows.append(dict(
                        block="B", arith="float", kappa=kappa, M=M, m=m, b=b,
                        order=order, n=1, E_plus=r["E_plus"], dE=r["dE"],
                        dE_stable=r["dE_stable"], dE_form=dE_form, D_modal=r["D"],
                        D_form=(t12_D_A if order == "A" else t12_D_B)(M, m, v, b, kappa),
                        ratio_DB_DA="", inject_meas=inj_meas, inject_pred=inj_pred,
                        margin_rel=margin,
                        b_star=(t12_b_star(M, m, kappa) if order == "A"
                                else t12_b_star_B(M, m, kappa)),
                        note=""))
            counts[(kappa, order)] = n_inj
            peak[(kappa, order)] = (peak_ratio, peak_cell)
            clog.assert_true(n_mismatch == 0,
                             label=f"(B) sign(dE_measured) == sign(N) on every "
                                   f"cell outside the dead band, kappa={kappa:g} "
                                   f"order {order} ({n_mismatch} mismatches)")
            clog.assert_true(worst_resid_group <= RESID_TOL,
                             label=f"(B) |dE_measured - (T13-4)|/(E_-+E_+) <= "
                                   f"{RESID_TOL:.0e} on ALL {n_cells} cells, "
                                   f"kappa={kappa:g} order {order} (max "
                                   f"{worst_resid_group:.2e})")
            clog.assert_true(worst_rel_cell_group <= RTOL,
                             label=f"(B) dE_measured == (T13-4) at rtol {RTOL:.0e} "
                                   f"on the {n_relposable} cells with injection "
                                   f"margin >= {MARGIN_REL:.0e}, kappa={kappa:g} "
                                   f"order {order} (max rel "
                                   f"{worst_rel_cell_group:.2e})")
    clog.assert_true(counts[(1.0, "A")] == 0,
                     label=f"(B) order A at kappa=1 injects on 0 of {n_cells} cells "
                           f"(measured {counts[(1.0, 'A')]})")
    clog.assert_true(counts[(2.0, "A")] > 0,
                     label=f"(B) order A at kappa=2 injects on "
                           f"{counts[(2.0, 'A')]} of {n_cells} cells (>0)")
    clog.assert_true(n_deadband == 0,
                     label=f"(B) dead band |N|/S < {DEADBAND:.0e} is empty on the "
                           f"shipped grid ({n_deadband} cells; min margin "
                           f"{min_margin:.2e})")

    # ===================================================================== #
    # BLOCK C -- band edge bracketed in float, and the existence criterion. #
    # ===================================================================== #
    delta = 1.0e-6
    n_noband = n_noband_bad = 0
    n_brack = n_brack_bad = 0
    for kappa in KAPPAS:
        for mu in [0.01, 0.1, 0.5, 1.0, 1.5, 1.9, 1.99, 2.0, 2.5, 5.0]:
            m = mu * M
            exists_pred = t12_band_exists(M, m, kappa)
            bstar = t12_b_star(M, m, kappa)
            clog.assert_true(exists_pred == (kappa ** 2 > 2.0 + mu),
                             label=f"(C) band-existence criterion kappa^2>2+m/M "
                                   f"kappa={kappa:g} m/M={mu:g}")
            if not exists_pred:
                # no positive root: order A must be passive at every sampled b
                for b in [1e-3, 1e-2, 0.1, 1.0, 10.0, 100.0]:
                    r = two_row_run_kappa(M, m, v, b, h, "A", kappa, n=1)
                    n_noband += 1
                    if not (r["dE_stable"] <= 0.0):
                        n_noband_bad += 1
                rows.append(dict(
                    block="C", arith="float", kappa=kappa, M=M, m=m, b="",
                    order="A", n=1, E_plus="", dE="", dE_stable="", dE_form="",
                    D_modal="", D_form="", ratio_DB_DA="", inject_meas=False,
                    inject_pred=False, margin_rel="", b_star="",
                    note="band empty (kappa^2 <= 2+m/M): passive at every b"))
                continue
            for side, bb in (("below", bstar * (1.0 - delta)),
                             ("above", bstar * (1.0 + delta))):
                r = two_row_run_kappa(M, m, v, bb, h, "A", kappa, n=1)
                want = (side == "below")
                n_brack += 1
                if (r["dE_stable"] > 0.0) != want:
                    n_brack_bad += 1
                rows.append(dict(
                    block="C", arith="float", kappa=kappa, M=M, m=m, b=bb,
                    order="A", n=1, E_plus=r["E_plus"], dE=r["dE"],
                    dE_stable=r["dE_stable"],
                    dE_form=t12_dE(M, m, v, bb, kappa, "A"), D_modal=r["D"],
                    D_form=t12_D_A(M, m, v, bb, kappa), ratio_DB_DA="",
                    inject_meas=r["dE_stable"] > 0.0,
                    inject_pred=t12_inject_value(M, m, bb, kappa, "A") > 0.0,
                    margin_rel=abs(t12_inject_value(M, m, bb, kappa, "A"))
                               / t12_inject_scale(M, m, bb, kappa, "A"),
                    b_star=bstar, note=f"b* bracket {side} by {delta:g} rel"))
    clog.assert_true(n_noband_bad == 0,
                     label=f"(C) kappa^2 <= 2+m/M -> dE_A <= 0 at every sampled b "
                           f"({n_noband} cells, {n_noband_bad} bad)")
    clog.assert_true(n_brack_bad == 0,
                     label=f"(C) b* brackets the measured sign flip at {delta:g} "
                           f"relative ({n_brack} brackets, {n_brack_bad} bad)")

    # ===================================================================== #
    # BLOCK D -- exact rational certification, 300 cells, zero tolerance.   #
    # ===================================================================== #
    n_exact = 0
    n_exact_band = 0
    n_exact_band_bad = 0
    n_exact_bandB = 0
    n_exact_bandB_bad = 0
    n_exact_sign_bad = 0
    n_exact_form_bad = 0
    n_exact_ratio = 0
    n_exact_ratio_bad = 0
    if not args.no_exact:
        hF = F(1, 1000)
        vF = F(-1, 1)
        MF = F(1, 1)
        mus_ex = [F(1, 100), F(1, 10), F(1, 2), F(1, 1), F(3, 2), F(199, 100),
                  F(2, 1), F(21, 10), F(5, 2), F(5, 1)]
        b_fixed = [F(1, 10 ** 6), F(1, 1000), F(1, 100), F(1, 10), F(1, 4),
                   F(1, 2), F(1, 1), F(2, 1), F(4, 1), F(10, 1), F(100, 1)]
        eps = F(1, 10 ** 9)
        for kappa_i in (1, 2):
            kF = F(kappa_i, 1)
            for muF in mus_ex:
                mF = muF * MF
                bl = list(b_fixed)
                # two cells straddling the order-A edge b* when it exists, else
                # two more fixed cells; likewise for the order-B edge.
                bsA = t12_b_star(1.0, float(muF), float(kF))
                if np.isfinite(bsA) and bsA > 0:
                    qA = F(round(bsA * 10 ** 12), 10 ** 12)
                    bl += [qA - eps, qA + eps]
                else:
                    bl += [F(1, 10 ** 4), F(1000, 1)]
                bsB = t12_b_star_B(1.0, float(muF), float(kF))
                if np.isfinite(bsB) and bsB > 0:
                    qB = F(round(bsB * 10 ** 12), 10 ** 12)
                    bl += [qB - eps, qB + eps]
                else:
                    bl += [F(1, 10 ** 5), F(10000, 1)]
                straddleA = []
                straddleB = []
                for bF in bl:
                    for order in ("A", "B"):
                        ex = two_row_run_exact(MF, mF, vF, bF, hF, order, kF)
                        NF = t12_inject_value_exact(MF, mF, bF, kF, order)
                        dform = t12_dE_exact(MF, mF, vF, bF, kF, order)
                        if _sgn(ex["dE"]) != _sgn(NF):
                            n_exact_sign_bad += 1
                        if ex["dE"] != dform:
                            n_exact_form_bad += 1
                        if order == "A":
                            exB = two_row_run_exact(MF, mF, vF, bF, hF, "B", kF)
                            if exB["D"] != ex["D"] * (1 + bF) ** 2:
                                n_exact_ratio_bad += 1
                            n_exact_ratio += 1
                            if np.isfinite(bsA) and bF in (bl[11], bl[12]):
                                straddleA.append(NF > 0)
                        else:
                            if np.isfinite(bsB) and bF in (bl[13], bl[14]):
                                straddleB.append(NF > 0)
                        n_exact += 1
                        rows.append(dict(
                            block="D", arith="exact", kappa=kappa_i, M=1.0,
                            m=float(mF), b=float(bF), order=order, n=1,
                            E_plus=float(ex["E_plus"]), dE=float(ex["dE"]),
                            dE_stable="", dE_form=float(dform),
                            D_modal=float(ex["D"]), D_form="", ratio_DB_DA="",
                            inject_meas=ex["dE"] > 0, inject_pred=NF > 0,
                            margin_rel="", b_star=(bsA if order == "A" else bsB),
                            note="exact rational"))
                if len(straddleA) == 2:
                    n_exact_band += 1
                    if not (straddleA[0] and not straddleA[1]):
                        n_exact_band_bad += 1
                if len(straddleB) == 2:
                    # order B edge: passive BELOW, injecting ABOVE (the opposite
                    # sense to order A; at kappa = 1 this is the paper's b > 1+m/M)
                    n_exact_bandB += 1
                    if not (not straddleB[0] and straddleB[1]):
                        n_exact_bandB_bad += 1
        clog.assert_true(n_exact_sign_bad == 0,
                         label=f"(D) EXACT sign(dE) == sign(N) (T13-5) on "
                               f"{n_exact} rational cells, ZERO tolerance "
                               f"({n_exact_sign_bad} bad)")
        clog.assert_true(n_exact_form_bad == 0,
                         label=f"(D) EXACT dE == (T13-4) on {n_exact} rational "
                               f"cells, ZERO tolerance ({n_exact_form_bad} bad)")
        clog.assert_true(n_exact_ratio_bad == 0,
                         label=f"(D) EXACT D_B/D_A == (1+b)^2 (T13-3) on "
                               f"{n_exact_ratio} rational cells, ZERO tolerance "
                               f"({n_exact_ratio_bad} bad)")
        clog.assert_true(n_exact_band_bad == 0,
                         label=f"(D) EXACT order-A b* bracketed at 1e-9 (inject "
                               f"below, passive above) on {n_exact_band} band "
                               f"edges ({n_exact_band_bad} bad)")
        clog.assert_true(n_exact_bandB_bad == 0,
                         label=f"(D) EXACT order-B edge 2+m/M-kappa^2 bracketed at "
                               f"1e-9 (passive below, inject above) on "
                               f"{n_exact_bandB} edges ({n_exact_bandB_bad} bad)")
        clog.assert_true(n_exact == 600,
                         label=f"(D) exact block attempted 600 rational cells, "
                               f"300 per order (got {n_exact})")

    # ===================================================================== #
    # BLOCK E -- iteration ladder inside the kappa = 2 band (recorded).     #
    # ===================================================================== #
    ladder = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32]
    ladder_report = []
    for (mu, b) in [(1.0, 1e-3), (1.0, 0.05), (0.1, 0.1), (1.0, 0.1804)]:
        m = mu * M
        sgns = []
        for n in ladder:
            r = two_row_run_kappa(M, m, v, b, h, "A", 2.0, n=n)
            sgns.append(r["dE_stable"] > 0.0)
            rows.append(dict(
                block="E", arith="float", kappa=2.0, M=M, m=m, b=b, order="A",
                n=n, E_plus=r["E_plus"], dE=r["dE"], dE_stable=r["dE_stable"],
                dE_form="", D_modal=r["D"], D_form="", ratio_DB_DA="",
                inject_meas=r["dE_stable"] > 0.0, inject_pred="", margin_rel="",
                b_star=t12_b_star(M, m, 2.0), note="iteration ladder"))
        rc = two_row_run_kappa(M, m, v, b, h, "A", 2.0, converge=True)
        rows.append(dict(
            block="E", arith="float", kappa=2.0, M=M, m=m, b=b, order="A",
            n=rc["n_used"], E_plus=rc["E_plus"], dE=rc["dE"],
            dE_stable=rc["dE_stable"], dE_form="", D_modal=rc["D"], D_form="",
            ratio_DB_DA="", inject_meas=rc["dE_stable"] > 0.0, inject_pred="",
            margin_rel="", b_star=t12_b_star(M, m, 2.0), note="converged endpoint"))
        ladder_report.append((mu, b, sgns, rc["n_used"], rc["dE_stable"]))

    # ===================================================================== #
    # BLOCK G -- the band edge in physical units at the shipped operating   #
    # point (1 iteration x 8 substeps at 1/120 s, so h = 1/960 s). b* is a  #
    # bound on (omega h)^2, hence on the mode frequency:                    #
    #     f* = sqrt(b*) / (2 pi h)   [Hz].                                  #
    # ===================================================================== #
    H_SHIP = 1.0 / 960.0
    band_hz = []
    for mu in [0.01, 0.1, 0.5, 1.0, 1.5, 1.9]:
        bs_ = t12_b_star(1.0, mu, 2.0)
        f_star = np.sqrt(bs_) / (2.0 * np.pi * H_SHIP)
        band_hz.append((mu, bs_, f_star))
        rows.append(dict(
            block="G", arith="float", kappa=2.0, M=1.0, m=mu, b=bs_, order="A",
            n=1, E_plus="", dE="", dE_stable="", dE_form="", D_modal="",
            D_form="", ratio_DB_DA="", inject_meas="", inject_pred="",
            margin_rel="", b_star=bs_,
            note=(f"band edge in physical units at the shipped h = 1/960 s: "
                  f"order A injects for mode frequencies below "
                  f"{f_star:.4g} Hz")))

    # ===================================================================== #
    # BLOCK F -- size of the order-A violation, (T13-8).                    #
    # ===================================================================== #
    sup_report = []
    for kappa in (2.0, 2.5, 3.0):
        mu_s = t12_sup_mu(kappa)
        sup = t12_sup_ratio(kappa)
        m = mu_s * M
        prev = None
        for bb in (1e-3, 1e-6, 1e-9, 1e-12):
            r = two_row_run_kappa(M, m, v, bb, h, "A", kappa, n=1)
            ratio = r["dE_stable"] / r["E_minus"]
            rows.append(dict(
                block="F", arith="float", kappa=kappa, M=M, m=m, b=bb, order="A",
                n=1, E_plus=r["E_plus"], dE=r["dE"], dE_stable=r["dE_stable"],
                dE_form=t12_dE(M, m, v, bb, kappa, "A"), D_modal=r["D"],
                D_form=t12_D_A(M, m, v, bb, kappa), ratio_DB_DA="",
                inject_meas=r["dE_stable"] > 0.0, inject_pred=True,
                margin_rel=abs(t12_inject_value(M, m, bb, kappa, "A"))
                           / t12_inject_scale(M, m, bb, kappa, "A"),
                b_star=t12_b_star(M, m, kappa),
                note=f"(T13-8) sup dE_A/|E-| = {sup:.10g} as b->0 at m/M={mu_s:g}"))
            prev = ratio
        clog.assert_close(prev, sup, rtol=1e-10,
                          label=f"(F) dE_A/|E-| -> (T13-8) = {sup:.10g} as b -> 0 "
                                f"at kappa={kappa:g}, m/M={mu_s:g}")
        # the maximizer really is mu*: no neighbouring mass ratio does better
        worse = True
        for dmu in (-0.2, -0.05, 0.05, 0.2):
            mu2 = mu_s + dmu
            if mu2 <= 0:
                continue
            r2 = two_row_run_kappa(M, mu2 * M, v, 1e-12, h, "A", kappa, n=1)
            if r2["dE_stable"] / r2["E_minus"] > prev:
                worse = False
        clog.assert_true(worse,
                         label=f"(F) m/M = {mu_s:g} maximizes dE_A/|E-| at "
                               f"kappa={kappa:g} (T13-8)")
        sup_report.append((kappa, mu_s, sup, prev))

    # ---- write CSV + manifest BEFORE finalize -------------------------------
    fieldnames = ["block", "arith", "kappa", "M", "m", "b", "order", "n",
                  "E_plus", "dE", "dE_stable", "dE_form", "D_modal", "D_form",
                  "ratio_DB_DA", "inject_meas", "inject_pred", "margin_rel",
                  "b_star", "note"]
    C.write_csv(
        OUT, args.out, rows, fieldnames=fieldnames,
        manifest=dict(
            scenes=["onesweep_two_row_toy(z,q)"],
            solvers=["xpbd_gs_toy"],
            note=("T13: run_t5_ordering.py's two-row GS ordering toy with the "
                  "velocity reconstruction qdot+ = kappa dq/h carried through "
                  "and b extended to 1e-3. D_B/D_A = (1+b)^2 exactly for EVERY "
                  "kappa (T13-3). Order A injects iff (kappa^2+b)/(1+b)^2 > "
                  "2 + m/M (T13-5A): passive unconditionally at kappa = 1, and "
                  "at kappa = 2 injecting on the band b < b* which is nonempty "
                  "iff m < 2M, b* = 2(kappa^2-s)/(sqrt(1+4s(kappa^2-1))+2s-1), "
                  "s = 2+m/M (T13-7); the violation reaches "
                  "(kappa^2-2)^2/(4(kappa^2-1)) of the incoming kinetic energy, "
                  "exactly 1/3 at kappa=2, m=M/2, b->0 (T13-8). "
                  "Block P reproduces run_t5_ordering.py and "
                  "the shipped t5_ordering.csv bit-identically at kappa = 1. "
                  "Block D certifies the sign law and the band edge in exact "
                  "rational arithmetic on 600 cells (300 per order), zero "
                  "tolerance. Cold "
                  "start, e = 0, hard contact, one coupling row, n = 1 unless "
                  "the row says otherwise."),
            grid=dict(kappa=KAPPAS, b=[B_LO, B_HI, args.nb],
                      mu=[MU_LO, MU_HI, args.nmu], orders=["A", "B"], v0=v, h=h,
                      deadband=DEADBAND, rtol=RTOL, exact_cells=n_exact)))

    # ---- report -------------------------------------------------------------
    print("\n=== T13 report ===")
    print(f"[P] kappa=1 vs run_t5_ordering.py: max abs diff over {n_p} quantities "
          f"= {worst_p:.1e} (0.0 means bit-identical)")
    print(f"[P] kappa=1 vs shipped t5_ordering.csv: max abs diff over {n_csv} "
          f"values = {worst_csv:.1e}")
    print(f"[A] closed forms (T13-1..T13-3): {n_A} checks, rtol {RTOL:.0e}")
    print(f"[B] map {args.nb} b x {args.nmu} m/M = {n_cells} cells per (kappa, order)")
    for kappa in KAPPAS:
        for order in ("A", "B"):
            pr, pc = peak[(kappa, order)]
            ps = (f"peak dE/|E-| = {pr:.4g} at m/M={pc[0]:.4g}, b={pc[1]:.4g}"
                  if pc else "no injecting cell")
            print(f"    kappa={kappa:g} order {order}: {counts[(kappa, order)]:5d}"
                  f"/{n_cells} injecting; {ps}")
    print(f"[B] worst PURE-RELATIVE |dE_measured - dE_form| = {worst_dE_rel:.2e} "
          f"over the cells with injection margin >= {MARGIN_REL:.0e}, at "
          f"(kappa, order, m/M, b) = {worst_dE_cell}")
    print(f"[B] min relative margin |N|/S over the grid = {min_margin:.2e}; "
          f"dead-band cells = {n_deadband}; sign checks = {n_sign}")
    print("[C] band edge b*(kappa=2, m/M):")
    for mu in [0.01, 0.1, 0.5, 1.0, 1.5, 1.9, 1.99, 2.0, 2.5]:
        bs_ = t12_b_star(1.0, mu, 2.0)
        print(f"    m/M={mu:<5g} b* = {bs_:.6g}" if np.isfinite(bs_)
              else f"    m/M={mu:<5g} b* = (no band; passive at every b)")
    print(f"[D] exact rational cells: {n_exact} (300 per order); order-A band "
          f"edges bracketed exactly at 1e-9: {n_exact_band}; order-B edges: "
          f"{n_exact_bandB}")
    print(f"[G] band edge in physical units, kappa=2, shipped h = 1/960 s "
          f"(1 iteration x 8 substeps at 1/120 s):")
    for (mu, bs_, f_star) in band_hz:
        print(f"    m/M={mu:<5g} b* = {bs_:.6g} -> omega h < {np.sqrt(bs_):.6g}, "
              f"mode frequency below {f_star:.4g} Hz")
    print("[F] size of the order-A violation, sup dE_A/|E-| = (k^2-2)^2/(4(k^2-1)):")
    for (kappa, mu_s, sup, meas) in sup_report:
        print(f"    kappa={kappa:g}: sup = {sup:.10g} at m/M = {mu_s:g}; "
              f"measured at b=1e-12: {meas:.10g}")
    print("[E] kappa=2 order-A iteration ladder (injecting at n = "
          f"{ladder}):")
    for (mu, b, sgns, nconv, dEc) in ladder_report:
        first_passive = next((ladder[i] for i, s in enumerate(sgns) if not s), None)
        print(f"    m/M={mu:g} b={b:g}: {''.join('+' if s else '-' for s in sgns)}"
              f"  first passive n = {first_passive}; converged n={nconv} "
              f"dE={dEc:.3e}")
    print(f"\nwrote {os.path.join(OUT, args.out)}.csv ({len(rows)} rows) + manifest")

    clog.finalize("T13 reconstruction-general GS ordering (kappa through T5)")


if __name__ == "__main__":
    main()
