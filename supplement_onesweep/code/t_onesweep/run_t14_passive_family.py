"""T14: the PASSIVE FAMILY of charge operators (panel item 1, 2026-07-28).

WHY THIS EXISTS. The paper proves that the reconstruction-matched charge
W = G^{-1}, G = kappa^2 M_c + h^2 K_c, makes one cold-start sweep passive
unconditionally (Thm `thm:exact`, T10). It presents that charge as THE fix, and
it separately reports (Sec. "Accuracy against a converged reference", T11) that
at kappa = 2 the matched charge over-dissipates, returning between 1/2 and 1 of
the converged modal amplitude. Sec. 6 lists that shortfall as a limitation.

Both statements are true, and together they hide a one-line fact: G^{-1} is not
the boundary of passivity, it is the MIDPOINT of a whole admissible interval,
and the converged-amplitude charge the paper reports as unreachable is the far
endpoint of that interval.

THE FAMILY (derivation; a substitution into the paper's own Eq. (6)).
Eq. (6) / (T10-1) is, for an arbitrary charge operator W with u := W J_c,

    dE = (v^2 / 2 D^2) [ u^T G u - w_r - 2 J_c^T u - 2 a_tilde ],
    D  = w_r + J_c^T u + a_tilde .                                     (T14-0)

Put W = c G^{-1} for a scalar c. Then u = c G^{-1} J_c, and with

    a := J_c^T G^{-1} J_c  >= 0        (the matched row-visible modal mobility)

both bracket terms telescope through the SAME quantity:

    u^T G u = c^2 J_c^T G^{-1} G G^{-1} J_c = c^2 a ,
    J_c^T u = c a ,

so (T14-0) collapses to a scalar quadratic in c:

    dE = (v^2 / 2 D^2) [ c(c-2) a - w_r - 2 a_tilde ] ,
    D  = w_r + c a + a_tilde .                                         (T14-1)

Because a >= 0, w_r > 0 and a_tilde >= 0, and because c(c-2) <= 0 exactly on
0 <= c <= 2,

    EVERY c in [0, 2] is passive, unconditionally, under precisely the
    hypotheses Thm `thm:exact` already carries: one sweep, cold start, e = 0,
    hard contact, kappa_r = 1, any kappa != 0, any M_c > 0, any K_c >= 0, any
    a_tilde >= 0, any number of coupled coordinates.                   (T14-2)

and the interval is SHARP: for any c outside [0, 2] the coefficient c(c-2) is
strictly positive, so the row injects as soon as a > (w_r + 2 a_tilde)/(c(c-2)),
which is reachable at any c outside [0,2] by softening or lightening the mode.
The exact per-row critical coordinate is

    c_crit = 1 + sqrt( 1 + (w_r + 2 a_tilde)/a )  in (2, inf) ,        (T14-3)

so a given row is passive on [0, c_crit] and injects on (c_crit, inf) union
(-inf, 2 - c_crit).

ENDPOINTS, and why this is not a loose end.
  c = 1  is the paper's matched charge. At a_tilde = 0, (T14-1) is
         dE = -v^2/(2(w_r + a)), the perfectly inelastic (e = 0) shock loss of
         the pair (M, 1/a). So Thm `thm:exact`'s exactness identity is exactly
         the c = 1 specialization of this corollary; nothing already claimed is
         weakened, generalized away, or restated.
  c = 2  is the scalar charge mu = G/2. At kappa = 2 undamped and one
         coordinate, G/2 = m(2 + b/2) = mu_*, which run_t11_accuracy.py already
         identifies as the charge that reproduces the host's own converged step
         (Ref-MID) exactly. Block F below verifies that identification in all
         four observables (p, v+, q+, qdot+) and against the shipped
         out/t11_accuracy.csv columns. So the converged amplitude the paper
         reports as out of reach IS reachable, passively, at the endpoint.
  c = 0  is passive but degenerate: W = 0, the mode is not coupled to the row at
         all and receives no deposit. It is included for sharpness of the
         interval, not as a design point. (The interval is CLOSED at 0; a naive
         reading "fails for c <= 0" is wrong at c = 0 and right for c < 0.)

OPERATOR FORM (strictly stronger than the scalar ray). Requiring passivity for
every row direction J_c rather than one fixed row turns (T14-2) into a Loewner
interval. u^T G u <= 2 J_c^T u for all J_c reads W G W <= 2 W, and for
symmetric W with G > 0 that holds if and only if

    0 <= W <= 2 G^{-1}   (Loewner order).                              (T14-4)

Proof of the equivalence: for W > 0, W G W <= 2 W iff W^{1/2} G W^{1/2} <= 2 I
iff G^{1/2} W G^{1/2} <= 2 I (the two have the same spectrum) iff W <= 2G^{-1};
and if W has an eigenvalue lam < 0 with unit eigenvector x then
x^T W G W x = (Wx)^T G (Wx) > 0 > 2 lam = 2 x^T W x, so W >= 0 is necessary.
Block C checks both directions, including a constructive adversarial row
direction for every W outside the interval.

The scalar family is the ray W = c G^{-1} inside (T14-4). Two immediate
corollaries checked below:
  * a charge that includes the damper, W = c (G + h C_c)^{-1}, satisfies
    W <= c G^{-1} <= 2 G^{-1} for c <= 2, so folding damping into the charge can
    only move a weight further INSIDE the family, never out (block D);
  * a MIS-SPECIFIED G is exactly a point of the family at a shifted coordinate.
    With the weight built from G_hat instead of G, and
    a_hat = J^T G_hat^{-1} J, A = J^T G_hat^{-1} G G_hat^{-1} J, the injection
    predicate is identically (T14-1) at
        c_eff = c A / a_hat ,   a_eff = a_hat^2 / A .                  (T14-5)
    Scalar: c_eff = c G/G_hat. A kappa = 1 weight on the paper's kappa = 2 host
    is c_eff = (4+b)/(1+b) in (1, 4], leaving the family whenever
    (4+b)/(1+b) > c_crit, which block G2 checks reduces EXACTLY to the paper's
    already-published condition M(2-b) > m(1+b)^2. The family coordinate
    therefore reproduces a result the paper states independently.

SELECTION CRITERION (what the panel actually asked for). c = 2 is not fragile
because it is marginally passive: (T14-1) at c = 2 is dE = -(v^2/2D^2)(w_r +
2 a_tilde), strictly negative for every w_r > 0. It is fragile because it sits
ON the boundary of the admissible interval, so the surviving margin is a margin
in the CHARGE, not in the energy, and (T14-3) measures it:

    tolerable relative overshoot from c = 1 : c_crit/1 - 1 >= 100%
    tolerable relative overshoot from c = 2 : c_crit/2 - 1 = [sqrt(1+r) - 1]/2,
                                              r := (w_r + 2 a_tilde)/a,

which vanishes as the row's coupling strengthens (a >> w_r). Block G1 measures
the distribution; block G3 exhibits the failure on the paper's own stated
hypothesis violation, a diagonal-only charge on a non-diagonal K_c, paired
across c on identical instances. This is the reason the SHIPPED default does not
move: c = 1 keeps a factor-of-two margin against every G mis-estimate above,
including the kappa mis-estimate of (T14-5); c = 2 keeps none.

TOLERANCES, and what was NOT done (no tolerance was loosened to make a claim
pass). dE is a difference of nearly equal energies, and the c grid deliberately
contains cells where the predicate margin N = c(c-2)a - w_r - 2a_tilde is near
zero, i.e. where dE itself is near zero. A PURE-RELATIVE residual there measures
cancellation, not the identity. The T13 protocol is therefore used verbatim: two
normalizers, both reported, neither replacing the other.

  * SCALE-NORMALIZED residual |pred - meas| / E^-, asserted on EVERY cell of the
    admissible half-line c >= 0. This is the cancellation-free scale
    (E^- = v^2/(2 w_r) is the incoming energy) and it sits at machine epsilon:
    8.516e-16 scalar on 28,500 cells, 1.594e-12 multi-mode on 11,400
    (cond-limited).
  * PURE-RELATIVE residual |pred - meas|/|meas|, asserted only on cells whose
    ENERGY margin |dE|/E^- clears a gate. That gate is not cosmetic: the
    residual is ~ eps E^-, so the pure-relative number is inflated by exactly
    E^-/|dE|, and the gate bounds that amplification. Gate 1e-3 with a 1e-12 bar
    for the scalar block (well-conditioned, the T11 bar), gate 1e-2 with a 1e-9
    bar for the multi-mode block (explicit G^{-1} on coupled K_c reaches
    cond ~ 4e6, exactly as T10 documents). Gated counts are printed.

A SEPARATE and physically meaningful fact came out of the c < 0 cells and is
reported rather than hidden. A negative charge operator is not merely
non-passive: it destroys the WELL-POSEDNESS of the local solve. The row
denominator is D = w_r + c a + a_tilde, so for c < 0 it can vanish or change
sign, and the sweep divides by it. Every residual above machine epsilon in this
script, without exception, comes from such a near-singular c < 0 cell (worst
4.0e-8 of E^- at |D| = 6.7e-7). The c < 0 cells are therefore asserted under an
explicit well-posedness gate |D| / (w_r + |c| a + a_tilde) >= 1e-2 and the
excluded count is printed. This gives the lower endpoint c = 0 two independent
justifications, an energy one and a well-posedness one.

Sign checks are gated by the same relative margin and the gated-out count is
reported. The governing exactness check is block E: the same identity over
fractions.Fraction with exact Gaussian elimination, residual identically zero,
including cells 1e-9 either side of c = 2 and, in block E2, exact-rational cells
placed 1e-9 either side of the true injection boundary c_crit itself, where the
sign is resolved at ZERO tolerance.

Interpreter: .venv/bin/python. Pure numpy + stdlib
fractions + csv. Imports its one-sweep kernels from run_t10_multimode.py and
its converged references from run_t11_accuracy.py; neither is modified.
"""
from __future__ import annotations

import csv
import os
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CheckLog, write_csv                       # noqa: E402
from run_t10_multimode import (one_sweep_general,            # noqa: E402
                               rational_solve,
                               random_modal_row)
from run_t11_accuracy import ref_mid, sweep_arm              # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# The c grid: interior, both endpoints, 1e-9 either side of each endpoint, and
# well outside on both sides.
C_GRID = [-1.0, -0.1, -1e-9, 0.0, 1e-9, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5,
          1.75, 1.9, 1.99, 2.0 - 1e-9, 2.0, 2.0 + 1e-9, 2.01, 2.1, 2.5, 3.0, 4.0]
IN_FAMILY = [c for c in C_GRID if 0.0 <= c <= 2.0]


def family_dE(v, w_r, a, c, a_tilde=0.0):
    """(T14-1): dE = (v^2/2D^2)[c(c-2)a - w_r - 2 a_tilde], D = w_r + c a + a_tilde."""
    D = w_r + c * a + a_tilde
    return (v * v / (2.0 * D * D)) * (c * (c - 2.0) * a - w_r - 2.0 * a_tilde)


def family_margin(w_r, a, c, a_tilde=0.0):
    """Signed injection margin N = c(c-2)a - w_r - 2 a_tilde and its scale."""
    N = c * (c - 2.0) * a - w_r - 2.0 * a_tilde
    S = abs(c * (c - 2.0)) * a + w_r + 2.0 * a_tilde
    return N, S


def well_posed(w_r, a, c, a_tilde=0.0):
    """|D| relative to the sum of the magnitudes of its terms. The local solve
    divides by D = w_r + c a + a_tilde; for c < 0 that can vanish, which is a
    well-posedness failure of the row, not an energy statement."""
    D = w_r + c * a + a_tilde
    return abs(D) / (w_r + abs(c) * a + a_tilde)


def c_crit(w_r, a, a_tilde=0.0):
    """(T14-3): the positive root of c(c-2)a = w_r + 2 a_tilde."""
    return 1.0 + np.sqrt(1.0 + (w_r + 2.0 * a_tilde) / a)


def rand_scalar(rng):
    M = 10.0 ** rng.uniform(-2, 3)
    m = 10.0 ** rng.uniform(-2, 2)
    omega = 10.0 ** rng.uniform(0, 3.5)
    h = 10.0 ** rng.uniform(-3.5, -1.5)
    v = -10.0 ** rng.uniform(-2, 1)
    kappa = float(rng.choice([1.0, 2.0])) if rng.integers(0, 2) else rng.uniform(0.3, 3.0)
    a_tilde = 0.0 if rng.integers(0, 2) else 10.0 ** rng.uniform(-6.0, 0.0)
    zeta = 0.0 if rng.integers(0, 2) else 10.0 ** rng.uniform(-3.0, -0.3)
    return M, m, omega, h, v, kappa, a_tilde, zeta


def main():  # noqa: C901
    log = CheckLog()
    rng = np.random.default_rng(20260728)
    rows = []

    # ================================================================ #
    # A. SCALAR: closed form, sign law, and the interval, over the grid #
    # ================================================================ #
    print("== A. scalar c-family: closed form + sign law over the c grid ==")
    n_A_per_c = 1500
    max_rel_A = 0.0            # pure-relative, margin-gated, c >= 0
    max_scale_A = 0.0          # scale-normalized, every c >= 0 cell
    max_scale_A_neg = 0.0      # scale-normalized, c < 0, well-posedness gated
    n_rel_A = 0
    n_wp_excl_A = 0
    sign_bad_A = 0
    gated_A = 0
    A_counts = {}
    inst = []
    for _ in range(n_A_per_c):
        inst.append(rand_scalar(rng))
    for c in C_GRID:
        n_inj = 0
        n_pass = 0
        n_pred_inj = 0
        for (M, m, omega, h, v, kappa, a_tilde, zeta) in inst:
            k = m * omega ** 2
            M_c = np.array([[m]])
            K_c = np.array([[k]])
            J_c = np.array([-1.0])
            w_r = 1.0 / M
            G = kappa * kappa * m + h * h * k
            a = 1.0 / G                       # J_c^T G^{-1} J_c, J_c = -1
            W = np.array([[c / G]])
            r = one_sweep_general(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde)
            pred = family_dE(v, w_r, a, c, a_tilde)
            resid = abs(pred - r["dE"])
            N, S = family_margin(w_r, a, c, a_tilde)
            if c >= 0.0:
                max_scale_A = max(max_scale_A, resid / r["E_minus"])
                # pure-relative only where the ENERGY margin is healthy: rel is
                # resid/|dE| and resid ~ eps E^-, so this gate is exactly what
                # bounds the cancellation amplification factor E^-/|dE|.
                if abs(r["dE"]) / r["E_minus"] >= 1e-3:
                    n_rel_A += 1
                    max_rel_A = max(max_rel_A, resid / abs(r["dE"]))
            elif well_posed(w_r, a, c, a_tilde) >= 1e-2:
                max_scale_A_neg = max(max_scale_A_neg, resid / r["E_minus"])
            else:
                n_wp_excl_A += 1
            meas_inj = r["dE"] > 0.0
            if meas_inj:
                n_inj += 1
            else:
                n_pass += 1
            if N > 0.0:
                n_pred_inj += 1
            if abs(N) / S < 1e-6:
                gated_A += 1
            elif (N > 0.0) != meas_inj:
                sign_bad_A += 1
        A_counts[c] = (n_inj, n_pass, n_pred_inj)
        rows.append(dict(block="A_scalar", c=c, n_cells=n_A_per_c, n_inject=n_inj,
                         n_passive=n_pass, n_pred_inject=n_pred_inj,
                         in_family=int(0.0 <= c <= 2.0)))
        tag = "IN " if 0.0 <= c <= 2.0 else "OUT"
        print(f"   c={c:>16.12g} [{tag}]  measured inject {n_inj:>5d}/{n_A_per_c}"
              f"   predicted {n_pred_inj:>5d}")
    n_pos_A = len([c for c in C_GRID if c >= 0.0]) * n_A_per_c
    log.assert_close(max_scale_A, 0.0, rtol=0.0, atol=1e-14,
                     label=f"A. (T14-1) closed form == measured dE, scale-normalized "
                           f"by E^-, ALL {n_pos_A} scalar cells at c >= 0")
    log.assert_close(max_rel_A, 0.0, rtol=0.0, atol=1e-12,
                     label=f"A. (T14-1) pure-relative on the {n_rel_A} scalar cells "
                           f"at c >= 0 with energy margin |dE|/E^- >= 1e-3")
    log.assert_close(max_scale_A_neg, 0.0, rtol=0.0, atol=1e-11,
                     label=f"A. (T14-1) at c < 0, scale-normalized, on the "
                           f"well-posed cells (|D|/scale >= 1e-2)")
    log.assert_true(sign_bad_A == 0,
                    label="A. sign law c(c-2)a > w_r + 2 a_tilde matches measured sign")
    n_inj_in = sum(A_counts[c][0] for c in IN_FAMILY)
    log.assert_true(n_inj_in == 0,
                    label=f"A. every c in [0,2] passive on all "
                          f"{len(IN_FAMILY) * n_A_per_c} scalar cells")
    print(f"   c >= 0: scale-normalized {max_scale_A:.3e} on all {n_pos_A}, "
          f"pure-relative {max_rel_A:.3e} on {n_rel_A} with energy margin >= 1e-3")
    print(f"   c <  0: scale-normalized {max_scale_A_neg:.3e}; "
          f"{n_wp_excl_A} cells excluded as ill-posed (D near zero)")
    print(f"   sign mismatches {sign_bad_A}; margin-gated {gated_A}")
    print(f"   c in [0,2]: {n_inj_in} injecting cells out of "
          f"{len(IN_FAMILY) * n_A_per_c}")

    # ================================================================ #
    # B. MULTI-MODE, coupled K_c: same statements, matrix G            #
    # ================================================================ #
    print("\n== B. multi-mode coupled K_c, W = c G^{-1} ==")
    n_B_per_c = 600
    max_rel_B = 0.0
    max_scale_B = 0.0
    max_scale_B_neg = 0.0
    n_rel_B = 0
    n_wp_excl_B = 0
    sign_bad_B = 0
    gated_B = 0
    worst_cond = 0.0
    inst_B = []
    for _ in range(n_B_per_c):
        n_modes = int(rng.integers(1, 7))
        coupled = bool(rng.integers(0, 2))
        M_c, K_c, J_c = random_modal_row(rng, n_modes, coupled_K=coupled)
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2.0, 1.0)
        w_r = 10.0 ** rng.uniform(-3.0, 1.0)
        kappa = float(rng.choice([1.0, 2.0])) if rng.integers(0, 2) else rng.uniform(0.3, 3.0)
        a_tilde = 0.0 if rng.integers(0, 2) else 10.0 ** rng.uniform(-6.0, 0.0)
        inst_B.append((M_c, K_c, J_c, h, v, w_r, kappa, a_tilde, coupled))
    B_inj_in = 0
    for c in C_GRID:
        n_inj = 0
        n_pred = 0
        for (M_c, K_c, J_c, h, v, w_r, kappa, a_tilde, coupled) in inst_B:
            G = kappa * kappa * M_c + (h * h) * K_c
            Ginv = np.linalg.inv(G)
            a = float(J_c @ (Ginv @ J_c))
            W = c * Ginv
            r = one_sweep_general(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde,
                                  cond=True)
            worst_cond = max(worst_cond, r["cond_G"])
            pred = family_dE(v, w_r, a, c, a_tilde)
            resid = abs(pred - r["dE"])
            N, S = family_margin(w_r, a, c, a_tilde)
            if c >= 0.0:
                max_scale_B = max(max_scale_B, resid / r["E_minus"])
                if abs(r["dE"]) / r["E_minus"] >= 1e-2:
                    n_rel_B += 1
                    max_rel_B = max(max_rel_B, resid / abs(r["dE"]))
            elif well_posed(w_r, a, c, a_tilde) >= 1e-2:
                max_scale_B_neg = max(max_scale_B_neg, resid / r["E_minus"])
            else:
                n_wp_excl_B += 1
            meas_inj = r["dE"] > 0.0
            n_inj += int(meas_inj)
            n_pred += int(N > 0.0)
            if abs(N) / S < 1e-6:
                gated_B += 1
            elif (N > 0.0) != meas_inj:
                sign_bad_B += 1
        if 0.0 <= c <= 2.0:
            B_inj_in += n_inj
        rows.append(dict(block="B_multimode", c=c, n_cells=n_B_per_c, n_inject=n_inj,
                         n_passive=n_B_per_c - n_inj, n_pred_inject=n_pred,
                         in_family=int(0.0 <= c <= 2.0)))
        tag = "IN " if 0.0 <= c <= 2.0 else "OUT"
        print(f"   c={c:>16.12g} [{tag}]  measured inject {n_inj:>4d}/{n_B_per_c}"
              f"   predicted {n_pred:>4d}")
    n_pos_B = len([c for c in C_GRID if c >= 0.0]) * n_B_per_c
    log.assert_close(max_scale_B, 0.0, rtol=0.0, atol=1e-10,
                     label=f"B. (T14-1) closed form == measured dE, scale-normalized "
                           f"by E^-, ALL {n_pos_B} multi-mode cells at c >= 0 "
                           f"[cond-limited, see T10]")
    log.assert_close(max_rel_B, 0.0, rtol=0.0, atol=1e-9,
                     label=f"B. (T14-1) pure-relative on the {n_rel_B} multi-mode "
                           f"cells at c >= 0 with energy margin |dE|/E^- >= 1e-2 "
                           f"[cond-limited, see T10]")
    log.assert_close(max_scale_B_neg, 0.0, rtol=0.0, atol=1e-9,
                     label=f"B. (T14-1) at c < 0, scale-normalized, on the "
                           f"well-posed multi-mode cells (|D|/scale >= 1e-2)")
    log.assert_true(sign_bad_B == 0,
                    label="B. multi-mode sign law matches measured sign")
    log.assert_true(B_inj_in == 0,
                    label=f"B. every c in [0,2] passive on all "
                          f"{len(IN_FAMILY) * n_B_per_c} multi-mode cells")
    print(f"   c >= 0: scale-normalized {max_scale_B:.3e} on all {n_pos_B}, "
          f"pure-relative {max_rel_B:.3e} on {n_rel_B} with energy margin >= 1e-2 "
          f"(worst cond(G) {worst_cond:.2e})")
    print(f"   c <  0: scale-normalized {max_scale_B_neg:.3e}; "
          f"{n_wp_excl_B} cells excluded as ill-posed (D near zero)")
    print(f"   sign mismatches {sign_bad_B}; margin-gated {gated_B}")
    print(f"   c in [0,2]: {B_inj_in} injecting cells out of "
          f"{len(IN_FAMILY) * n_B_per_c}")

    # ================================================================ #
    # C. OPERATOR INTERVAL 0 <= W <= 2 G^{-1}, both directions          #
    # ================================================================ #
    print("\n== C. operator interval (T14-4): sufficiency and sharpness ==")
    n_inside = 0
    n_inside_bad = 0
    n_outside = 0
    n_outside_found = 0
    n_neg = 0
    n_neg_found = 0
    for _ in range(2500):
        n_modes = int(rng.integers(1, 7))
        M_c, K_c, J_c0 = random_modal_row(rng, n_modes, coupled_K=bool(rng.integers(0, 2)))
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        kappa = float(rng.choice([1.0, 2.0, 0.5, 3.0]))
        G = kappa * kappa * M_c + (h * h) * K_c
        A0 = rng.standard_normal((n_modes, n_modes))
        W = A0 @ A0.T + n_modes * np.eye(n_modes) * 10.0 ** rng.uniform(-3, 1)
        L = np.linalg.cholesky(G)
        lam_max = float(np.linalg.eigvalsh(L.T @ W @ L).max())
        target = float(rng.uniform(0.02, 4.0))
        W = W * (target / lam_max)
        a_tilde = 0.0 if rng.integers(0, 2) else 10.0 ** rng.uniform(-6.0, 0.0)
        if target <= 2.0:
            # sufficiency: no row direction, no rigid mobility, may inject
            n_inside += 1
            bad = False
            for _t in range(40):
                J_c = rng.standard_normal(n_modes) * 10.0 ** rng.uniform(-1, 1)
                w_r = 10.0 ** rng.uniform(-4, 2)
                v = -1.0
                r = one_sweep_general(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde)
                if r["dE"] > 0.0:
                    bad = True
                    break
            n_inside_bad += int(bad)
        else:
            # sharpness: a constructive adversarial row direction must inject
            n_outside += 1
            Q = G - 2.0 * np.linalg.inv(W)
            ev, V = np.linalg.eigh(Q)
            y = V[:, -1]
            J_c = np.linalg.solve(W, y)           # so that u = W J_c = y
            # scale the row so the modal terms dominate w_r + 2 a_tilde
            w_r = 10.0 ** rng.uniform(-3, 0)
            quad = float(y @ (Q @ y))             # = u^T G u - 2 J_c^T u
            if quad <= 0.0:
                continue
            s = np.sqrt(10.0 * (w_r + 2.0 * a_tilde) / quad)
            J_c = J_c * s
            r = one_sweep_general(w_r, J_c, M_c, K_c, h, -1.0, W, kappa, a_tilde)
            n_outside_found += int(r["dE"] > 0.0)
        # a deliberately indefinite W must also fail
        if rng.integers(0, 4) == 0:
            n_neg += 1
            Wn = W.copy()
            evn, Vn = np.linalg.eigh(Wn)
            evn[0] = -abs(evn[-1])
            Wn = Vn @ np.diag(evn) @ Vn.T
            J_c = np.linalg.solve(Wn, Vn[:, 0])
            quad = float(Vn[:, 0] @ (G @ Vn[:, 0])) - 2.0 * float(J_c @ Vn[:, 0])
            w_r = 10.0 ** rng.uniform(-3, 0)
            if quad > 0.0:
                s = np.sqrt(10.0 * w_r / quad)
                r = one_sweep_general(w_r, J_c * s, M_c, K_c, h, -1.0, Wn, kappa, 0.0)
                n_neg_found += int(r["dE"] > 0.0)
    log.assert_true(n_inside_bad == 0,
                    label=f"C. W <= 2G^-1 passive on every tested row direction "
                          f"({n_inside} operators x 40 rows)")
    log.assert_true(n_outside_found == n_outside,
                    label=f"C. every W outside the interval injects on a constructed "
                          f"row ({n_outside} operators)")
    log.assert_true(n_neg_found == n_neg,
                    label=f"C. indefinite W injects on a constructed row ({n_neg})")
    print(f"   inside  0 <= W <= 2G^-1: {n_inside} operators, "
          f"{n_inside_bad} with an injecting row (want 0)")
    print(f"   outside the interval    : {n_outside} operators, "
          f"{n_outside_found} inject on the constructed row (want all)")
    print(f"   indefinite W            : {n_neg} operators, {n_neg_found} inject")
    rows.append(dict(block="C_operator_interval", c="", n_cells=n_inside,
                     n_inject=n_inside_bad, n_passive=n_inside - n_inside_bad,
                     n_pred_inject=0, in_family=1))
    rows.append(dict(block="C_operator_interval", c="", n_cells=n_outside,
                     n_inject=n_outside_found, n_passive=n_outside - n_outside_found,
                     n_pred_inject=n_outside, in_family=0))

    # ================================================================ #
    # D. DAMPING IN THE CHARGE CAN ONLY MOVE INTO THE FAMILY            #
    # ================================================================ #
    print("\n== D. damped charge W = c (G + h C_c)^{-1}, c in (0,2] ==")
    n_D = 0
    n_D_inj = 0
    worst_shift = 0.0
    for _ in range(1200):
        n_modes = int(rng.integers(1, 6))
        M_c, K_c, J_c = random_modal_row(rng, n_modes, coupled_K=bool(rng.integers(0, 2)))
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2.0, 1.0)
        w_r = 10.0 ** rng.uniform(-3.0, 1.0)
        kappa = float(rng.choice([1.0, 2.0]))
        a_tilde = 0.0 if rng.integers(0, 2) else 10.0 ** rng.uniform(-6.0, 0.0)
        zeta = 10.0 ** rng.uniform(-3.0, -0.3)
        mvec = np.diag(M_c)
        omg = np.sqrt(np.maximum(np.diag(K_c), 0.0) / mvec)
        C_c = np.diag(2.0 * zeta * omg * mvec)
        G = kappa * kappa * M_c + (h * h) * K_c
        Gd = G + h * C_c
        for c in (0.25, 1.0, 2.0):
            W = c * np.linalg.inv(Gd)
            # the energy is the UNDAMPED Hamiltonian (paper's convention), so
            # one_sweep_general with (M_c, K_c) charges the true stored energy
            r = one_sweep_general(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde)
            n_D += 1
            n_D_inj += int(r["dE"] > 0.0)
            # effective family coordinate of the damped charge (T14-5)
            a_hat = float(J_c @ (np.linalg.inv(Gd) @ J_c))
            Ai = float(J_c @ (np.linalg.inv(Gd) @ (G @ (np.linalg.inv(Gd) @ J_c))))
            c_eff = c * Ai / a_hat
            worst_shift = max(worst_shift, c_eff / c)
    log.assert_true(n_D_inj == 0,
                    label=f"D. damped charge c(G + hC)^-1, c in (0,2], passive on "
                          f"{n_D} cells")
    log.assert_true(worst_shift <= 1.0 + 1e-12,
                    label="D. damping moves the effective coordinate DOWN "
                          "(c_eff/c <= 1 on every cell)")
    print(f"   {n_D_inj}/{n_D} inject; worst c_eff/c = {worst_shift:.15f} "
          f"(must be <= 1: damping only moves DOWN the family)")
    rows.append(dict(block="D_damped_charge", c="0.25/1/2", n_cells=n_D,
                     n_inject=n_D_inj, n_passive=n_D - n_D_inj, n_pred_inject=0,
                     in_family=1))

    # ================================================================ #
    # E. EXACT RATIONAL ARITHMETIC: the governing exactness check       #
    # ================================================================ #
    print("\n== E. exact rational arithmetic: residual identically zero ==")
    C_RAT = [Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(1),
             Fraction(3, 2), Fraction(2) - Fraction(1, 10 ** 9), Fraction(2),
             Fraction(2) + Fraction(1, 10 ** 9), Fraction(5, 2), Fraction(4),
             -Fraction(1, 10 ** 9), -Fraction(1)]
    rng_e = np.random.default_rng(20260728)
    n_E = 0
    n_E_form = 0
    n_E_sign = 0
    n_E_passive_in = 0
    n_E_in = 0
    n_E_c2 = 0
    n_E_c2_exact = 0
    for _ in range(60):
        n_modes = int(rng_e.integers(1, 5))
        M_r = [[Fraction(0) for _ in range(n_modes)] for _ in range(n_modes)]
        for i in range(n_modes):
            M_r[i][i] = Fraction(int(rng_e.integers(1, 40)), int(rng_e.integers(1, 12)))
        Kd = [Fraction(int(rng_e.integers(0, 400)), int(rng_e.integers(1, 7)))
              for _ in range(n_modes)]
        B_r = [[Fraction(int(rng_e.integers(-3, 4)), int(rng_e.integers(1, 5)))
                for _ in range(n_modes)] for _ in range(n_modes)]
        for i in range(n_modes):
            B_r[i][i] += Fraction(1)
        K_r = [[sum(B_r[t][i] * Kd[t] * B_r[t][j] for t in range(n_modes))
                for j in range(n_modes)] for i in range(n_modes)]
        J_r = [Fraction(int(rng_e.integers(-6, 7)), int(rng_e.integers(1, 5)))
               for _ in range(n_modes)]
        if all(x == 0 for x in J_r):
            J_r[0] = Fraction(1)
        h_r = Fraction(1, int(rng_e.choice([60, 120, 240, 500])))
        v_r = -Fraction(int(rng_e.integers(1, 30)), int(rng_e.integers(1, 8)))
        w_r_r = Fraction(int(rng_e.integers(1, 20)), int(rng_e.integers(1, 30)))
        kappa_r = Fraction(int(rng_e.choice([1, 2, 3])))
        a_t_r = Fraction(0) if rng_e.integers(0, 2) else \
            Fraction(1, int(rng_e.integers(1, 500)))
        G_r = [[kappa_r * kappa_r * M_r[i][j] + h_r * h_r * K_r[i][j]
                for j in range(n_modes)] for i in range(n_modes)]
        x_r = rational_solve(G_r, J_r)          # G^{-1} J_c, EXACT
        if x_r is None:
            continue
        a_r = sum(J_r[i] * x_r[i] for i in range(n_modes))   # J^T G^{-1} J
        for c_r in C_RAT:
            u_r = [c_r * xi for xi in x_r]
            w_modal_r = sum(J_r[i] * u_r[i] for i in range(n_modes))
            D_r = w_r_r + w_modal_r + a_t_r
            if D_r == 0:
                continue
            dlam_r = -h_r * v_r / D_r
            dq_r = [ui * dlam_r for ui in u_r]
            qd_r = [kappa_r * d / h_r for d in dq_r]
            v_plus_r = v_r + w_r_r * dlam_r / h_r
            E_minus_r = Fraction(1, 2) * (1 / w_r_r) * v_r * v_r
            ke_r = Fraction(1, 2) * sum(qd_r[i] * M_r[i][j] * qd_r[j]
                                        for i in range(n_modes) for j in range(n_modes))
            pe_r = Fraction(1, 2) * sum(dq_r[i] * K_r[i][j] * dq_r[j]
                                        for i in range(n_modes) for j in range(n_modes))
            E_plus_r = Fraction(1, 2) * (1 / w_r_r) * v_plus_r * v_plus_r + ke_r + pe_r
            dE_meas = E_plus_r - E_minus_r
            # (T14-1) in exact rationals
            dE_form = (v_r * v_r / (2 * D_r * D_r)) * \
                      (c_r * (c_r - 2) * a_r - w_r_r - 2 * a_t_r)
            n_E += 1
            n_E_form += int(dE_meas == dE_form)
            N_r = c_r * (c_r - 2) * a_r - w_r_r - 2 * a_t_r
            n_E_sign += int((N_r > 0) == (dE_meas > 0))
            if 0 <= c_r <= 2:
                n_E_in += 1
                n_E_passive_in += int(dE_meas < 0)
            if c_r == 2:
                n_E_c2 += 1
                # at c = 2 exactly: dE = -(v^2/2D^2)(w_r + 2 a_tilde)
                exact_c2 = -(v_r * v_r / (2 * D_r * D_r)) * (w_r_r + 2 * a_t_r)
                n_E_c2_exact += int(dE_meas == exact_c2)
    log.assert_true(n_E_form == n_E,
                    label=f"E. EXACT (T14-1) closed form, {n_E} rational cells, residual 0")
    log.assert_true(n_E_sign == n_E,
                    label=f"E. EXACT sign law, {n_E} rational cells")
    log.assert_true(n_E_passive_in == n_E_in,
                    label=f"E. EXACT strict passivity for c in [0,2], "
                          f"{n_E_in} rational cells")
    log.assert_true(n_E_c2_exact == n_E_c2,
                    label=f"E. EXACT dE(c=2) == -(v^2/2D^2)(w_r + 2 a_tilde), "
                          f"{n_E_c2} rational cells")
    print(f"   rational cells {n_E}: closed form {n_E_form}/{n_E} exact, "
          f"sign {n_E_sign}/{n_E}, passive-in-family {n_E_passive_in}/{n_E_in}, "
          f"c=2 endpoint form {n_E_c2_exact}/{n_E_c2}")
    print("   (equalities of rationals, not tolerances; includes c = 2 +/- 1e-9)")
    rows.append(dict(block="E_rational", c="grid", n_cells=n_E, n_inject=n_E - n_E_sign,
                     n_passive=n_E_passive_in, n_pred_inject=n_E_form, in_family=1))

    # ---------------------------------------------------------------- #
    # E2. EXACT boundary straddle. c_crit is irrational in general, so   #
    #     instead FIX a rational c > 2 and solve exactly for the w_r     #
    #     that puts the row on the boundary: w_r* = c(c-2)a - 2 a_tilde. #
    #     Then w_r = w_r*(1 -/+ 1e-9) sits 1e-9 either side of it and    #
    #     the measured sign is resolved at ZERO tolerance.               #
    # ---------------------------------------------------------------- #
    print("\n== E2. exact rational cells 1e-9 either side of the true boundary ==")
    eps_r = Fraction(1, 10 ** 9)
    n_E2 = 0
    n_E2_ok = 0
    rng_e2 = np.random.default_rng(777)
    for _ in range(80):
        n_modes = int(rng_e2.integers(1, 4))
        M_r = [[Fraction(0) for _ in range(n_modes)] for _ in range(n_modes)]
        for i in range(n_modes):
            M_r[i][i] = Fraction(int(rng_e2.integers(1, 20)), int(rng_e2.integers(1, 8)))
        Kd = [Fraction(int(rng_e2.integers(0, 200)), int(rng_e2.integers(1, 5)))
              for _ in range(n_modes)]
        K_r = [[Kd[i] if i == j else Fraction(0) for j in range(n_modes)]
               for i in range(n_modes)]
        J_r = [Fraction(int(rng_e2.integers(-5, 6)), int(rng_e2.integers(1, 4)))
               for _ in range(n_modes)]
        if all(x == 0 for x in J_r):
            J_r[0] = Fraction(1)
        h_r = Fraction(1, int(rng_e2.choice([60, 120, 240])))
        v_r = -Fraction(int(rng_e2.integers(1, 20)), int(rng_e2.integers(1, 6)))
        kappa_r = Fraction(int(rng_e2.choice([1, 2])))
        a_t_r = Fraction(0) if rng_e2.integers(0, 2) else \
            Fraction(1, int(rng_e2.integers(100, 5000)))
        G_r = [[kappa_r * kappa_r * M_r[i][j] + h_r * h_r * K_r[i][j]
                for j in range(n_modes)] for i in range(n_modes)]
        x_r = rational_solve(G_r, J_r)
        if x_r is None:
            continue
        a_r = sum(J_r[i] * x_r[i] for i in range(n_modes))
        if a_r <= 0:
            continue
        for c_r in (Fraction(5, 2), Fraction(3), Fraction(4)):
            w_star = c_r * (c_r - 2) * a_r - 2 * a_t_r
            if w_star <= 0:
                continue
            for side, w_r_r in (("inject", w_star * (1 - eps_r)),
                                ("passive", w_star * (1 + eps_r))):
                u_r = [c_r * xi for xi in x_r]
                w_modal_r = sum(J_r[i] * u_r[i] for i in range(n_modes))
                D_r = w_r_r + w_modal_r + a_t_r
                dlam_r = -h_r * v_r / D_r
                dq_r = [ui * dlam_r for ui in u_r]
                qd_r = [kappa_r * d / h_r for d in dq_r]
                v_plus_r = v_r + w_r_r * dlam_r / h_r
                E_minus_r = Fraction(1, 2) * (1 / w_r_r) * v_r * v_r
                ke_r = Fraction(1, 2) * sum(qd_r[i] * M_r[i][j] * qd_r[j]
                                            for i in range(n_modes)
                                            for j in range(n_modes))
                pe_r = Fraction(1, 2) * sum(dq_r[i] * K_r[i][j] * dq_r[j]
                                            for i in range(n_modes)
                                            for j in range(n_modes))
                dE_r = (Fraction(1, 2) * (1 / w_r_r) * v_plus_r * v_plus_r
                        + ke_r + pe_r) - E_minus_r
                n_E2 += 1
                n_E2_ok += int((dE_r > 0) if side == "inject" else (dE_r < 0))
    log.assert_true(n_E2_ok == n_E2,
                    label=f"E2. EXACT sign 1e-9 either side of the boundary, "
                          f"{n_E2} rational cells, zero tolerance")
    print(f"   {n_E2_ok}/{n_E2} exact-rational cells straddle the boundary correctly")
    rows.append(dict(block="E2_boundary_exact", c="5/2,3,4", n_cells=n_E2,
                     n_inject=n_E2 // 2, n_passive=n_E2 // 2, n_pred_inject=n_E2_ok))

    # ================================================================ #
    # F. ENDPOINT IDENTITY: c = 2 IS the converged-reproducing charge   #
    # ================================================================ #
    print("\n== F. c = 2 at kappa = 2 reproduces the converged step (Ref-MID) ==")
    print("      b        c=1 q ratio     c=2 q ratio        dE(c=1)        dE(c=2)")
    worst_F = 0.0
    csv_path = os.path.join(OUT, "t11_accuracy.csv")
    t11 = {}
    if os.path.exists(csv_path):
        for r in csv.DictReader(open(csv_path)):
            if r.get("block") == "5_kappa2":
                t11[float(r["b"])] = r
    worst_csv = 0.0
    n_csv = 0
    for b in (1e-2, 1e-1, 1.0, 1e1, 1e2, 1e4):
        M, m, h = 1.0, 1.0, 1.0 / 240.0
        omega = np.sqrt(b) / h
        v = -1.0
        k = m * omega ** 2
        G = 4.0 * m + h * h * k                        # kappa = 2: m(4 + b)
        ref = ref_mid(M, m, omega, h, v, zeta=0.0)
        E_ref = (0.5 * M * ref["v_plus"] ** 2 + 0.5 * m * ref["qdot_plus"] ** 2
                 + 0.5 * k * ref["q_plus"] ** 2) - 0.5 * M * v * v
        a1 = sweep_arm(M, m, omega, h, v, G / 1.0, 2.0)     # c = 1, charge G
        a2 = sweep_arm(M, m, omega, h, v, G / 2.0, 2.0)     # c = 2, charge G/2
        for key in ("p", "v_plus", "q_plus", "qdot_plus"):
            worst_F = max(worst_F, abs(a2[key] / ref[key] - 1.0))
        print(f"   {b:>8.0e}   {a1['q_plus'] / ref['q_plus']:>12.9f}   "
              f"{a2['q_plus'] / ref['q_plus']:>16.14f}   "
              f"{a1['dE']:>12.9f}   {a2['dE']:>12.9f}")
        rec = dict(block="F_endpoint", b=b, q_ratio_c1=a1["q_plus"] / ref["q_plus"],
                   q_ratio_c2=a2["q_plus"] / ref["q_plus"],
                   dE_c1=a1["dE"], dE_c2=a2["dE"], dE_ref_mid=E_ref,
                   mu_star=G / 2.0, G=G)
        if b in t11:
            rec["t11_q_ratio"] = float(t11[b]["q_ratio"])
            rec["t11_dE_matched"] = float(t11[b]["dE_matched"])
            rec["t11_dE_ref"] = float(t11[b]["dE_ref"])
            n_csv += 1
            worst_csv = max(worst_csv,
                            abs(a1["q_plus"] / ref["q_plus"] - float(t11[b]["q_ratio"]))
                            / abs(float(t11[b]["q_ratio"])),
                            abs(a2["dE"] - float(t11[b]["dE_ref"]))
                            / abs(float(t11[b]["dE_ref"])),
                            abs(a1["dE"] - float(t11[b]["dE_matched"]))
                            / abs(float(t11[b]["dE_matched"])))
        rows.append(rec)
    log.assert_close(worst_F, 0.0, rtol=0.0, atol=1e-13,
                     label="F. charge G/2 at kappa=2 reproduces Ref-MID in "
                           "p, v+, q+, qdot+")
    log.assert_close(worst_csv, 0.0, rtol=0.0, atol=1e-14,
                     label=f"F. c=1 / c=2 energies match shipped t11_accuracy.csv "
                           f"columns dE_matched / dE_ref, {n_csv} rows")
    print(f"   max |ratio - 1| over the four observables at c=2: {worst_F:.3e}")
    print(f"   agreement with shipped t11_accuracy.csv ({n_csv} rows): {worst_csv:.3e}")
    print("   => the c=2 endpoint IS mu_* = G/2 = m(2 + b/2); dE(c=2) == dE_ref")

    # exact-rational endpoint identity, zero tolerance
    n_F_rat = 0
    n_F_rat_ok = 0
    for num, den in [(1, 100), (1, 10), (1, 1), (10, 1), (100, 1), (10000, 1)]:
        b_r = Fraction(num, den)
        m_r, M_r_ = Fraction(1), Fraction(1)
        h_r = Fraction(1, 240)
        G_r = m_r * (4 + b_r)
        mu_star = 2 * m_r * (1 + b_r / 4)
        n_F_rat += 1
        n_F_rat_ok += int(G_r / 2 == mu_star == m_r * (2 + b_r / 2))
    log.assert_true(n_F_rat_ok == n_F_rat,
                    label=f"F. EXACT G/2 == mu_* == m(2 + b/2) at kappa=2, "
                          f"{n_F_rat} rational cells")
    print(f"   exact rational G/2 == mu_*: {n_F_rat_ok}/{n_F_rat}")

    # ================================================================ #
    # G1. MARGIN: tolerable charge overshoot at c = 1 versus c = 2      #
    # ================================================================ #
    print("\n== G1. margin in the charge: c_crit = 1 + sqrt(1 + (w_r+2a~)/a) ==")
    head1 = []
    head2 = []
    ratio_r = []
    max_rel_crit = 0.0
    for _ in range(4000):
        M, m, omega, h, v, kappa, a_tilde, _z = rand_scalar(rng)
        k = m * omega ** 2
        w_r = 1.0 / M
        G = kappa * kappa * m + h * h * k
        a = 1.0 / G
        cc = c_crit(w_r, a, a_tilde)
        # verify c_crit by bisection on the measured sweep
        lo, hi = cc * (1.0 - 1e-6), cc * (1.0 + 1e-6)
        M_c, K_c, J_c = np.array([[m]]), np.array([[k]]), np.array([-1.0])
        r_lo = one_sweep_general(w_r, J_c, M_c, K_c, h, v, np.array([[lo / G]]),
                                 kappa, a_tilde)
        r_hi = one_sweep_general(w_r, J_c, M_c, K_c, h, v, np.array([[hi / G]]),
                                 kappa, a_tilde)
        if r_lo["dE"] < 0.0 < r_hi["dE"]:
            max_rel_crit = max(max_rel_crit, 0.0)
        else:
            max_rel_crit = max(max_rel_crit, 1.0)
        head1.append(cc / 1.0 - 1.0)
        head2.append(cc / 2.0 - 1.0)
        ratio_r.append((w_r + 2.0 * a_tilde) / a)
    head1 = np.array(head1)
    head2 = np.array(head2)
    ratio_r = np.array(ratio_r)
    log.assert_true(max_rel_crit == 0.0,
                    label="G1. measured sign flips across the closed-form c_crit "
                          "(4000 bisection pairs)")
    log.assert_true(bool(np.all(head1 >= 1.0 - 1e-15)),
                    label="G1. headroom from c=1 is at least 100% on every cell")
    for pct in (0, 5, 25, 50, 75, 100):
        print(f"   p{pct:>3d}:  r = {np.percentile(ratio_r, pct):>10.3e}   "
              f"headroom(c=1) {100 * np.percentile(head1, pct):>9.2f}%   "
              f"headroom(c=2) {100 * np.percentile(head2, pct):>9.4f}%")
        rows.append(dict(block="G1_margin", pct=pct,
                         r_coupling=float(np.percentile(ratio_r, pct)),
                         headroom_c1=float(np.percentile(head1, pct)),
                         headroom_c2=float(np.percentile(head2, pct))))
    print(f"   headroom(c=2) < 1% on {100.0 * np.mean(head2 < 0.01):.1f}% of cells, "
          f"< 10% on {100.0 * np.mean(head2 < 0.10):.1f}%")
    rows.append(dict(block="G1_margin", pct="frac_lt_1pct",
                     headroom_c2=float(np.mean(head2 < 0.01)),
                     headroom_c1=float(np.mean(head1 < 0.01))))

    # ================================================================ #
    # G2. A MIS-SPECIFIED G IS A SHIFTED FAMILY COORDINATE (T14-5)      #
    # ================================================================ #
    print("\n== G2. mis-specified G maps to c_eff = c A / a_hat ==")
    bad_G2 = 0
    n_G2 = 0
    n_rel_G2 = 0
    max_scale_G2 = 0.0
    max_rel_G2 = 0.0
    for _ in range(4000):
        n_modes = int(rng.integers(1, 6))
        M_c, K_c, J_c = random_modal_row(rng, n_modes, coupled_K=bool(rng.integers(0, 2)))
        h = 10.0 ** rng.uniform(-3.5, -1.5)
        v = -10.0 ** rng.uniform(-2.0, 1.0)
        w_r = 10.0 ** rng.uniform(-3.0, 1.0)
        kappa = float(rng.choice([1.0, 2.0]))
        kap_hat = float(rng.choice([0.5, 1.0, 2.0, 3.0]))
        a_tilde = 0.0 if rng.integers(0, 2) else 10.0 ** rng.uniform(-6.0, 0.0)
        c = float(rng.choice([0.5, 1.0, 1.5, 2.0]))
        G = kappa * kappa * M_c + (h * h) * K_c
        Gh = kap_hat * kap_hat * M_c + (h * h) * K_c
        Ghi = np.linalg.inv(Gh)
        W = c * Ghi
        r = one_sweep_general(w_r, J_c, M_c, K_c, h, v, W, kappa, a_tilde)
        a_hat = float(J_c @ (Ghi @ J_c))
        Amat = float(J_c @ (Ghi @ (G @ (Ghi @ J_c))))
        c_eff = c * Amat / a_hat
        a_eff = a_hat * a_hat / Amat
        pred = family_dE(v, w_r, a_eff, c_eff, a_tilde)
        resid = abs(pred - r["dE"])
        n_G2 += 1
        max_scale_G2 = max(max_scale_G2, resid / r["E_minus"])
        if abs(r["dE"]) / r["E_minus"] >= 1e-2:
            rel = resid / abs(r["dE"])
            n_rel_G2 += 1
            max_rel_G2 = max(max_rel_G2, rel)
            if rel > 1e-9:
                bad_G2 += 1
    # (T14-5) composes TWO inverses of the mis-specified operator,
    # G_hat^{-1} G G_hat^{-1}, so its float conditioning is the square of T10's
    # single inverse (cond(G_hat) reaches 1.6e7 here). The governing check is
    # the cancellation-free scale-normalized one.
    log.assert_close(max_scale_G2, 0.0, rtol=0.0, atol=1e-11,
                     label=f"G2. (T14-5) mis-specified G == family at (c_eff, a_eff), "
                           f"scale-normalized, ALL {n_G2} cells")
    log.assert_true(bad_G2 == 0,
                    label=f"G2. (T14-5) pure-relative <= 1e-9 on the {n_rel_G2} cells "
                          f"with energy margin |dE|/E^- >= 1e-2")
    print(f"   scale-normalized {max_scale_G2:.3e} on all {n_G2}; pure-relative "
          f"{max_rel_G2:.3e} on {n_rel_G2} energy-margin cells, {bad_G2} over 1e-9")

    # G2b: kappa=1 weight on a kappa=2 host, EXACT, vs the paper's own condition
    n_G2b = 0
    n_G2b_ok = 0
    rng_b = np.random.default_rng(4242)
    for _ in range(4000):
        M_i = Fraction(int(rng_b.integers(1, 400)), int(rng_b.integers(1, 40)))
        m_i = Fraction(int(rng_b.integers(1, 400)), int(rng_b.integers(1, 40)))
        b_i = Fraction(int(rng_b.integers(1, 3000)), int(rng_b.integers(1, 900)))
        G_i = m_i * (4 + b_i)
        Gh_i = m_i * (1 + b_i)
        c_eff = G_i / Gh_i
        a_eff = Fraction(1) / G_i
        w_r_i = Fraction(1) / M_i
        lhs = c_eff * (c_eff - 2) * a_eff
        n_G2b += 1
        n_G2b_ok += int((lhs > w_r_i) == (M_i * (2 - b_i) > m_i * (1 + b_i) ** 2))
    log.assert_true(n_G2b_ok == n_G2b,
                    label=f"G2b. EXACT: c_eff form == paper's M(2-b) > m(1+b)^2, "
                          f"{n_G2b} rational cells")
    print(f"   EXACT kappa=1-weight-on-kappa=2-host: family predicate == the "
          f"paper's M(2-b) > m(1+b)^2 on {n_G2b_ok}/{n_G2b} rational cells")
    rows.append(dict(block="G2_misspec", n_cells=n_G2, n_inject=bad_G2,
                     n_pred_inject=n_G2b_ok, n_passive=n_G2b))

    # ================================================================ #
    # G3. THE SELECTION CRITERION: robustness collapses at the endpoint #
    #     Paired diagonal-only charge on non-diagonal K_c across c.     #
    # ================================================================ #
    print("\n== G3. diagonal-only charge on coupled K_c, PAIRED across c ==")
    n_G3 = 2000
    inst_G3 = []
    rng_g = np.random.default_rng(20260728)
    for _ in range(n_G3):
        n_modes = int(rng_g.integers(2, 9))
        M_c, K_c, J_c = random_modal_row(rng_g, n_modes, coupled_K=True)
        h = 10.0 ** rng_g.uniform(-3.5, -1.5)
        v = -10.0 ** rng_g.uniform(-2.0, 1.0)
        w_r = 10.0 ** rng_g.uniform(-3.0, 1.0)
        kappa = float(rng_g.choice([1.0, 2.0]))
        inst_G3.append((M_c, K_c, J_c, h, v, w_r, kappa))
    c_band = []
    print("      c        inject/2000     worst dE")
    for c in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
        n_inj = 0
        worst = -np.inf
        for (M_c, K_c, J_c, h, v, w_r, kappa) in inst_G3:
            G = kappa * kappa * M_c + (h * h) * K_c
            W = np.diag(c / np.diag(G))
            r = one_sweep_general(w_r, J_c, M_c, K_c, h, v, W, kappa)
            n_inj += int(r["dE"] > 0.0)
            worst = max(worst, r["dE"])
        print(f"   {c:>5.2f}     {n_inj:>5d}/{n_G3}    {worst:>12.5e}")
        rows.append(dict(block="G3_diag_on_coupled", c=c, n_cells=n_G3,
                         n_inject=n_inj, n_passive=n_G3 - n_inj))
    # closed-form safe band 2B/A for the diagonal charge (T14 note): the
    # diagonal charge is a family point with c_eff = c A/B, so its interval ends
    # at c = 2B/A. Report the distribution.
    for (M_c, K_c, J_c, h, v, w_r, kappa) in inst_G3:
        G = kappa * kappa * M_c + (h * h) * K_c
        d = J_c / np.diag(G)
        Aq = float(d @ (G @ d))
        Bq = float(J_c @ d)
        c_band.append(2.0 * Bq / Aq)
    c_band = np.array(c_band)
    print(f"   closed-form endpoint of the diagonal charge's own interval, 2B/A:")
    for pct in (0, 5, 25, 50, 75, 100):
        print(f"     p{pct:>3d} = {np.percentile(c_band, pct):.4f}")
    frac_lt2 = float(np.mean(c_band < 2.0))
    frac_lt1 = float(np.mean(c_band < 1.0))
    print(f"   2B/A < 2 on {100 * frac_lt2:.1f}% of rows (c=2 outside its interval), "
          f"< 1 on {100 * frac_lt1:.1f}% (c=1 outside)")
    rows.append(dict(block="G3_band", c="2B/A", n_cells=n_G3,
                     frac_lt_2=frac_lt2, frac_lt_1=frac_lt1,
                     band_p50=float(np.median(c_band)),
                     band_p5=float(np.percentile(c_band, 5))))

    # ================================================================ #
    # H. THE HONEST TRADE: what c = 2 costs on the contact law itself   #
    # ================================================================ #
    print("\n== H. what the endpoint costs: transfer efficiency and loss ratio ==")
    # At a_tilde = 0 the rigid loss is (v^2/2D^2)(w_r + 2 c a) and the modal
    # deposit is (v^2/2D^2) c^2 a, so the fraction of the rigid loss that ends up
    # in the mode is eta(c) = c^2 a / (w_r + 2 c a): eta(1) = a/(w_r+2a) < 1/2,
    # eta(2) = 4a/(w_r+4a) -> 1 as a/w_r -> inf. At c = 2 a strongly coupled row
    # becomes asymptotically LOSSLESS, which is not an e = 0 impact law.
    # And |dE(c=2)|/|dE(c=1)| = mu(M+mu)/(mu+2M)^2 < 1 for every mu, M.
    max_rel_H = 0.0
    print("      mu/M      eta(c=1)   eta(c=2)   |dE(2)|/|dE(1)|")
    for ratio in (1e-3, 1e-2, 0.1, 1.0, 10.0, 100.0, 1000.0):
        M_h = 1.0
        mu = ratio * M_h
        w_r = 1.0 / M_h
        a = 1.0 / mu
        eta1 = 1.0 * a / (w_r + 2.0 * a)
        eta2 = 4.0 * a / (w_r + 4.0 * a)
        dE1 = family_dE(-1.0, w_r, a, 1.0)
        dE2 = family_dE(-1.0, w_r, a, 2.0)
        pred = mu * (M_h + mu) / (mu + 2.0 * M_h) ** 2
        max_rel_H = max(max_rel_H, abs(dE2 / dE1 - pred) / pred)
        print(f"   {ratio:>8.0e}    {eta1:>8.5f}   {eta2:>8.5f}   {dE2 / dE1:>12.6f}")
        rows.append(dict(block="H_trade", mu_over_M=ratio, eta_c1=eta1, eta_c2=eta2,
                         loss_ratio=dE2 / dE1))
    for _ in range(4000):
        M_h = 10.0 ** rng.uniform(-2, 3)
        mu = 10.0 ** rng.uniform(-3, 3)
        w_r, a = 1.0 / M_h, 1.0 / mu
        dE1 = family_dE(-1.0, w_r, a, 1.0)
        dE2 = family_dE(-1.0, w_r, a, 2.0)
        pred = mu * (M_h + mu) / (mu + 2.0 * M_h) ** 2
        max_rel_H = max(max_rel_H, abs(dE2 / dE1 - pred) / pred)
    log.assert_close(max_rel_H, 0.0, rtol=0.0, atol=1e-12,
                     label="H. |dE(c=2)|/|dE(c=1)| == mu(M+mu)/(mu+2M)^2, 4007 cells")
    print(f"   loss-ratio closed form max rel err {max_rel_H:.3e}; "
          f"the ratio is 2/9 = {2/9:.6f} at mu = M and < 1 for every mu, M")
    print("   => c=2 buys the converged amplitude with a strictly weaker e=0 "
          "contact law")

    # ---------------------------------------------------------------- #
    field_union = []
    for r in rows:
        for kk in r:
            if kk not in field_union:
                field_union.append(kk)
    rows = [{kk: r.get(kk, "") for kk in field_union} for r in rows]
    write_csv(OUT, "t14_passive_family", rows, fieldnames=field_union,
              manifest=dict(
                  script="run_t14_passive_family.py",
                  what="the passive family W = c G^-1, c in [0,2]; operator "
                       "interval 0 <= W <= 2G^-1; c=2 endpoint == converged "
                       "charge mu_* = G/2; charge-margin selection criterion",
                  metrics="sign law, closed-form residual, operator-interval "
                          "sharpness, endpoint identity vs t11_accuracy.csv, "
                          "c_crit headroom, paired diagonal-charge injection",
                  tol="1e-12 scalar float, 1e-9 multi-mode float "
                      "(cond-limited, see T10), EXACT on the rational block"))

    print("\n" + "\n".join(log.summary_lines()))
    fails = log.failures
    print(f"\nT14: {len(log.rows) - len(fails)}/{len(log.rows)} checks pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
