"""Shared primitives for the T-suite (one-sweep XPBD passivity boundary).

PURE NUMPY. No scipy, no `dcr.*` import, no eigendecomposition anywhere in this
module (grep-assertable: the token "eig" never appears below outside this
docstring). Every symbol implements the note's Model-and-conventions box
literally; each closed form cites its Result number (R1-R5) from
`scratchpad/onesweep_theory_note.md`. Forms the plan marks PLAN-DERIVED were
re-derived from the model box by the scaffold agent before implementation; the
derivation is written above each such function and all four agree with the plan
(see the module-level DERIVATION LEDGER note at the bottom of this docstring).

Model box (note "Model and conventions")
-----------------------------------------
Rigid body: row-visible mobility w_r (scalar). Its energy along the contact row
is that of an equivalent scalar mass M_eq = 1/w_r; because impulses only change
the row-projected component, dE_rigid = 0.5*M_eq*(v+^2 - v^2) is EXACT for a full
6-DOF body too (off-row KE cancels in the difference).
Restorative DOFs q: mass matrix M_c, stiffness K_c, damping C_c (diag
c_i = 2*zeta_i*omega_i*m_i). Contact row C = z - q >= 0, multiplier lam >= 0.
XPBD local solve: dlam = (-C - a_tilde*lam)/(w + a_tilde), position correction
dx = W J^T dlam, velocity reconstruction qdot = dx/h. Cold start: q = qdot = 0,
contact exactly touching, incoming gap rate v < 0, predicted penetration
C_tilde = h*v. Shorthand b = (omega*h)^2 = h^2 k/m. True Hamiltonian
E = 0.5*M v^2 + 0.5*qdot^T M_c qdot + 0.5*q^T K_c q at substep boundaries.

DERIVATION LEDGER (scaffold agent, 2026-07-23)
----------------------------------------------
Every PLAN-DERIVED form below was re-derived from the model box by hand:
  R4 a_tilde-generalized dE          -> AGREES with plan
  R4 effective-weight matrix form    -> AGREES with plan
  collapse identity y == rho - 1     -> AGREES with plan
  R5 order-A / order-B forms + ratio -> AGREES with plan (D_B/D_A == (1+b)^2 exact)
No discrepancy was found. The trailing-spring strengthening (dE_A < 0 for all
b,m,M, one sweep) is proven closed-form in the R5 comment.
"""
from __future__ import annotations

import csv
import os
import sys

import numpy as np

# --------------------------------------------------------------------------- #
# 1. Local XPBD Gauss-Seidel solve (note, Model box)                          #
# --------------------------------------------------------------------------- #
def local_solve(C, lam, w, a_tilde=0.0, unilateral=False):
    """One XPBD Gauss-Seidel local solve (note, Model box):

        dlam = (-C - a_tilde*lam) / (w + a_tilde)

    Returns (dlam, new_lam). The unilateral variant clamps
    new_lam = max(0, lam + dlam) and returns the CLAMPED increment
    dlam = new_lam - lam, so the caller applies a consistent position update.
    """
    dlam = (-C - a_tilde * lam) / (w + a_tilde)
    new_lam = lam + dlam
    if unilateral:
        clamped = max(0.0, new_lam)
        dlam = clamped - lam
        new_lam = clamped
    return dlam, new_lam


# --------------------------------------------------------------------------- #
# 2. General one-projection cold-start row (note R2/R3/R4)                     #
# --------------------------------------------------------------------------- #
def one_sweep_row(wr, J_c, M_c, K_c, h, v, weight_mode,
                  a_tilde=0.0, relax=1.0, C_damp=None):
    """One projection of a single cold-start contact row (note R2/R3/R4).

    Mirrors `solver_xpbd.py::_project_support` (lines 1540/1546-1549): the
    denominator uses `w_row + a_tilde`; the rigid block takes the FULL dlam
    (line 1546-1547); the restorative block takes `relax * dlam` (line 1549).

    Parameters
    ----------
    wr        : scalar rigid row mobility w_r = J_r M_r^{-1} J_r^T.
    J_c       : (r,) restorative-block Jacobian (the modal amplitudes U_i, signed;
                for the scalar C = z - q this is [-1]).
    M_c, K_c  : (r,r) restorative mass / stiffness (diagonal in the modal basis).
    weight_mode : "mass"     -> W = M_c^{-1}         (shipped 1/M_q weight)
                  "implicit" -> W = (M_c + h C_c + h^2 K_c)^{-1}  (note R3 remedy;
                                same W in denominator AND correction).
    C_damp    : (r,r) damping matrix (diag 2 zeta omega m); only used for implicit.

    Returns a dict with dlam, dx (relaxed position deposit), qdot, v_rigid_plus,
    E_minus, E_plus, dE, w_row, w_modal. Energies use the TRUE (M_c, K_c) forms,
    so the implicit arm is charged its true post-step Hamiltonian, not m_eff.
    """
    J_c = np.atleast_1d(np.asarray(J_c, dtype=np.float64))
    M_c = np.atleast_2d(np.asarray(M_c, dtype=np.float64))
    K_c = np.atleast_2d(np.asarray(K_c, dtype=np.float64))
    if weight_mode == "mass":
        W = np.linalg.inv(M_c)
    elif weight_mode == "implicit":
        if C_damp is None:
            C_damp = np.zeros_like(M_c)
        else:
            C_damp = np.atleast_2d(np.asarray(C_damp, dtype=np.float64))
        W = np.linalg.inv(M_c + h * C_damp + (h * h) * K_c)
    else:
        raise ValueError(f"weight_mode must be 'mass' or 'implicit', got {weight_mode!r}")

    w_modal = float(J_c @ (W @ J_c))
    w_row = wr + w_modal
    C_tilde = h * v                                    # predicted penetration
    dlam = -C_tilde / (w_row + a_tilde)                # solver line 1540 (cold lam=0)
    dx = relax * (W @ J_c) * dlam                      # restorative deposit (line 1549)
    qdot = dx / h                                      # velocity reconstruction
    v_rigid_plus = v + wr * dlam / h                   # rigid block, FULL dlam (line 1546)

    M_eq = 1.0 / wr
    E_minus = 0.5 * M_eq * v * v                       # modal at rest contributes 0
    E_plus = (0.5 * M_eq * v_rigid_plus * v_rigid_plus
              + 0.5 * float(qdot @ (M_c @ qdot))
              + 0.5 * float(dx @ (K_c @ dx)))
    return dict(dlam=dlam, dx=dx, qdot=qdot, v_rigid_plus=v_rigid_plus,
                E_minus=E_minus, E_plus=E_plus, dE=E_plus - E_minus,
                w_row=w_row, w_modal=w_modal)


# --------------------------------------------------------------------------- #
# 3. Closed forms                                                             #
# --------------------------------------------------------------------------- #

# ---- R1: per-impulse mobility ratio (note R1, exact) ---------------------- #
def r1_ratio(m, zeta, omega, h):
    """Mass-only / effective per-impulse velocity response ratio (note R1):

        mu_mass / mu_eff = (m + h c + h^2 k)/m = 1 + 2 zeta omega h + (omega h)^2

    (m unused numerically but kept in the signature for call-site clarity.)
    """
    return 1.0 + 2.0 * zeta * omega * h + (omega * h) ** 2


# ---- R2: one-sweep injection theorem (note R2, exact, mass-only) ---------- #
def r2_E_plus(M, m, v, b):
    """Post-step energy, one sweep, cold start, mass-only weight (note R2):

        E+ = 0.5 v^2 (M/(M+m))^2 (M + m + m b),   b = (omega h)^2.
    """
    return 0.5 * v * v * (M / (M + m)) ** 2 * (M + m + m * b)


def r2_dE(M, m, v, b):
    """dE = E+ - E-, E- = 0.5 M v^2 (note R2)."""
    return r2_E_plus(M, m, v, b) - 0.5 * M * v * v


def r2_boundary_b(M, m):
    """Injection boundary in b: E+ > E-  <=>  b > 1 + m/M (note R2)."""
    return 1.0 + m / M


# ---- R3: implicit-weight exactness identity (note R3) --------------------- #
def r3_m_eff(m, omega_h, zeta=0.0):
    """Effective mass the row charges the restorative DOF (note R3):

        m_eff = m (1 + 2 zeta omega h + (omega h)^2).

    Undamped it is exactly the quadratic form m(1+b) converting the
    reconstructed velocity into the true post-step modal Hamiltonian.
    """
    b = omega_h * omega_h
    return m * (1.0 + 2.0 * zeta * omega_h + b)


def r3_dE(M, m_eff, v):
    """One-sweep energy change with the implicit weight (note R3, undamped exact):

        dE = -0.5 (M m_eff)/(M + m_eff) v^2   < 0 unconditionally.

    This is the perfectly-inelastic-impact loss of the pair (M, m_eff). Damped:
    the true stored energy uses m(1+b) < m_eff, so the real dE is strictly below
    this value.
    """
    return -0.5 * (M * m_eff) / (M + m_eff) * v * v


# ---- R4: multi-DOF row-visible condition (note R4) ------------------------ #
# DERIVATION (a_tilde-generalized mass-only dE, PLAN-DERIVED; re-derived here).
# Denominator W_d = w_m + a_tilde; dlam = -h v / W_d.
# Rigid: v+ = v(1 - w_r/W_d);  dE_rigid = 0.5(1/w_r)v^2[(1-w_r/W_d)^2 - 1]
#            = v^2(-1/W_d + w_r/(2 W_d^2)).
# Modal KE = 0.5 (dlam/h)^2 sum a_i        = 0.5 (v^2/W_d^2) (w_m - w_r).
# Modal PE = 0.5 (dlam/h)^2 sum a_i b_i    = 0.5 (v^2/W_d^2) L.
# Summing, with sum a_i = w_m - w_r and L = w_E - w_m:
#   dE = (v^2/W_d^2)[ (w_m + L)/2 - w_m - a_tilde ].
# At a_tilde = 0 this is (v^2/w_m^2)(w_E/2 - w_m), the note's R4 form. AGREES.
def r4_dE_mass(v, w_r, w_m, L, a_tilde=0.0):
    """Mass-only one-sweep dE for a general row (note R4, a_tilde-generalized):

        dE = v^2 [ (w_m + L)/2 - w_m - a_tilde ] / (w_m + a_tilde)^2,
        w_m = w_r + sum a_i,  L = sum a_i b_i = w_E - w_m.

    Injection  <=>  L > w_m + 2 a_tilde  (note R4). `w_r` is accepted for
    call-site symmetry; it enters only through w_m.
    """
    return v * v * (0.5 * (w_m + L) - w_m - a_tilde) / (w_m + a_tilde) ** 2


def r4_rho(L, w_m, a_tilde=0.0):
    """Row danger index (note R4): rho = L/(w_m + 2 a_tilde); injection iff rho>1."""
    return L / (w_m + 2.0 * a_tilde)


# DERIVATION (effective-weight matrix dE, PLAN-DERIVED; re-derived here).
# Undamped M_c_eff = M_c + h^2 K_c, so w_eff = w_r + J (M_c + h^2 K_c)^{-1} J^T.
# Per mode the true stored energy 0.5 m qdot^2 + 0.5 k dx^2 = 0.5 m_eff qdot^2
# (dx = h qdot, k h^2 = m b), hence modal total = 0.5(dlam/h)^2 (w_eff - w_r).
# With W_e = w_eff + a_tilde and the same rigid algebra as above:
#   dE = (v^2/W_e^2)[ w_eff/2 - W_e ] = -v^2 (w_eff/2 + a_tilde)/(w_eff + a_tilde)^2.
# At a_tilde = 0: -v^2/(2 w_eff), the note's R4 form. AGREES; dE < 0 always.
def r4_w_eff(w_r, J_c, M_c, K_c, h):
    """Undamped effective row weight (note R4): w_r + J (M_c + h^2 K_c)^{-1} J^T."""
    J_c = np.atleast_1d(np.asarray(J_c, dtype=np.float64))
    M_c = np.atleast_2d(np.asarray(M_c, dtype=np.float64))
    K_c = np.atleast_2d(np.asarray(K_c, dtype=np.float64))
    W = np.linalg.inv(M_c + (h * h) * K_c)
    return w_r + float(J_c @ (W @ J_c))


def r4_dE_implicit(v, w_eff, a_tilde=0.0):
    """Effective-weight one-sweep dE (note R4, undamped exact):

        dE = -v^2 (w_eff/2 + a_tilde)/(w_eff + a_tilde)^2   < 0 unconditionally.
    """
    return -v * v * (0.5 * w_eff + a_tilde) / (w_eff + a_tilde) ** 2


# DERIVATION (collapse identity, PLAN-DERIVED; re-derived here).
# From r4_dE_mass at a_tilde = 0: dE = (v^2/(2 w_m))(rho - 1) with rho = L/w_m.
# Hence y := 2 dE w_m / v^2 = rho - 1 EXACTLY (hard contact, mass-only). AGREES.
def collapse_y(dE, w_m, v):
    """Collapse coordinate y = 2 dE w_m / v^2; equals rho - 1 exactly
    (hard contact, mass-only weight) (note R4)."""
    return 2.0 * dE * w_m / (v * v)


# ---- R5: Gauss-Seidel ordering, n = 1 closed forms (note R5) -------------- #
# DERIVATION (order-A / order-B, PLAN-DERIVED; re-derived here). Two rows on
# (z, q): contact C_c = z - q (hard, unilateral), spring C_s = q with
# a_tilde_s = 1/(k h^2). A single compliant spring row from rest relaxes a
# predicted q~ to q~/(1+b) (note R5; w_s = 1/m, dlam_s = -q~/(1/m + 1/(k h^2)),
# Dq = dlam_s/m, q+ = q~ m/(k h^2 + m) = q~/(1+b)).
#
# Order B [spring, contact]: the spring is a no-op from q~ = 0, then the contact
# is the plain R2 solve. So E+_B = R2 and modal deposit
#   D_B = 0.5 m qdot_B^2 + 0.5 k q_B^2 = 0.5 v^2 (M/(M+m))^2 m (1 + b).
#
# Order A [contact, spring]: contact deposits q1 = h v M/(M+m); the trailing
# spring relaxes it to q1/(1+b). With g = v M/(M+m), qdot+ = g/(1+b),
# q+ = h g/(1+b):
#   0.5 m qdot+^2 + 0.5 k q+^2 = 0.5 g^2 (m + m b)/(1+b)^2 = 0.5 g^2 m/(1+b),
#   E+_A = 0.5 M g^2 + 0.5 g^2 m/(1+b) = 0.5 v^2 (M/(M+m))^2 (M + m/(1+b)),
#   D_A = 0.5 v^2 (M/(M+m))^2 m/(1+b),   D_B/D_A = (1+b)^2  EXACTLY.
#
# Trailing-spring strengthening (proof that dE_A < 0 for ALL b, m, M):
#   dE_A = E+_A - 0.5 M v^2 = 0.5 v^2 M m [ M/(1+b) - 2M - m ] / (M+m)^2.
#   Since b >= 0 => M/(1+b) <= M => M/(1+b) - 2M - m <= -M - m < 0, so dE_A < 0.
# All four sub-results AGREE with the plan.
def r5_E_plus_B(M, m, v, b):
    """Order B = [spring, contact], n=1 (note R5): equals R2."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * (M + m + m * b)


def r5_D_B(M, m, v, b):
    """Order B modal deposit (note R5): 0.5 v^2 (M/(M+m))^2 m (1+b)."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * m * (1.0 + b)


def r5_E_plus_A(M, m, v, b):
    """Order A = [contact, spring], n=1 (note R5): trailing spring relaxes q."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * (M + m / (1.0 + b))


def r5_D_A(M, m, v, b):
    """Order A modal deposit (note R5): 0.5 v^2 (M/(M+m))^2 m/(1+b)."""
    return 0.5 * v * v * (M / (M + m)) ** 2 * m / (1.0 + b)


def r5_ratio_DB_DA(b):
    """Modal-deposit ratio between orders at n=1 (note R5): (1+b)^2, exact."""
    return (1.0 + b) ** 2


# --------------------------------------------------------------------------- #
# 4. Mass-spring chain assembly (T3; NO eigendecomposition)                    #
# --------------------------------------------------------------------------- #
def chain_matrices(N, masses, springs, anchored=True):
    """Tridiagonal stiffness K and diagonal mass M for a 1-D mass-spring chain.

    Convention (all N nodes are DOFs):
      * `masses`  : (N,) diagonal of M.
      * `springs` : neighbor stiffnesses. springs[j] (j = 0..N-2) connects node j
        and node j+1. If `anchored`, a ground spring is added at the last node
        (node N-1); its stiffness is springs[N-1] when len(springs) >= N, else
        springs[-1] (the uniform-chain default). If not anchored the chain has a
        rigid translation zero mode (K singular) -- the caller's responsibility.

    Returns (K, M) as dense (N,N) numpy arrays. No modal reduction here.
    """
    masses = np.asarray(masses, dtype=np.float64)
    springs = np.asarray(springs, dtype=np.float64)
    if masses.shape[0] != N:
        raise ValueError(f"masses must have length N={N}, got {masses.shape[0]}")
    if springs.shape[0] < N - 1:
        raise ValueError(f"springs must have length >= N-1={N - 1}, got {springs.shape[0]}")
    K = np.zeros((N, N), dtype=np.float64)
    for j in range(N - 1):
        kj = float(springs[j])
        K[j, j] += kj
        K[j + 1, j + 1] += kj
        K[j, j + 1] -= kj
        K[j + 1, j] -= kj
    if anchored:
        kg = float(springs[N - 1]) if springs.shape[0] >= N else float(springs[-1])
        K[N - 1, N - 1] += kg
    M = np.diag(masses)
    return K, M


# --------------------------------------------------------------------------- #
# 5. Assert bookkeeping + CSV/manifest helpers                                 #
# --------------------------------------------------------------------------- #
class CheckLog:
    """Accumulates checks and exits nonzero at end-of-script (never mid-run).

    Pass condition mirrors np.allclose: |a-b| <= rtol*|b| + atol, elementwise.
    The plan's 1e-12 machine checks are BINDING; on failure the script prints the
    failing identity and its measured residual and exits 1. Tolerances are never
    loosened silently -- a mismatch is a finding about the note/plan.
    """

    def __init__(self):
        self.rows = []

    def assert_close(self, a, b, rtol=1e-12, atol=0.0, label=""):
        a = np.asarray(a, dtype=np.float64)
        b = np.asarray(b, dtype=np.float64)
        num = np.abs(a - b)
        thr = rtol * np.abs(b) + atol
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = np.where(np.abs(b) > 0, num / np.abs(b), num)
        passed = bool(np.all(num <= thr))
        self.rows.append(dict(
            label=label, kind="close", passed=passed,
            max_abs=float(np.max(num)) if num.size else 0.0,
            max_rel=float(np.max(rel)) if rel.size else 0.0,
            rtol=rtol, atol=atol))
        return passed

    def assert_true(self, cond, label=""):
        passed = bool(np.all(cond))
        self.rows.append(dict(
            label=label, kind="true", passed=passed,
            max_abs=0.0, max_rel=0.0, rtol=0.0, atol=0.0))
        return passed

    @property
    def failures(self):
        return [r for r in self.rows if not r["passed"]]

    def summary_lines(self):
        lines = []
        for r in self.rows:
            tag = "PASS" if r["passed"] else "FAIL"
            if r["kind"] == "close":
                lines.append(f"  [{tag}] {r['label']}  max_rel={r['max_rel']:.3e} "
                             f"max_abs={r['max_abs']:.3e}  (rtol={r['rtol']:.0e}"
                             f"{'' if r['atol'] == 0 else f', atol={r['atol']:.0e}'})")
            else:
                lines.append(f"  [{tag}] {r['label']}")
        return lines

    def report(self, title="checks"):
        print(f"--- {title}: {len(self.rows)} total, {len(self.failures)} failed ---")
        for ln in self.summary_lines():
            print(ln)

    def finalize(self, title="checks"):
        """Print the summary and exit(0) on all-pass, exit(1) listing failures."""
        self.report(title)
        if self.failures:
            print(f"\nFAILED {len(self.failures)} check(s):")
            for r in self.failures:
                print(f"  {r['label']}: max_abs={r['max_abs']:.3e} "
                      f"max_rel={r['max_rel']:.3e} rtol={r['rtol']:.0e}")
            sys.exit(1)
        print(f"\nALL {len(self.rows)} CHECKS PASS")
        sys.exit(0)


def write_csv(out_dir, name, rows, fieldnames=None, manifest=None):
    """Write `<name>` (a .csv basename) into out_dir. If `manifest` is a dict,
    also emit `<stem>.config.json` via paper_config.write_manifest (imported
    lazily so this module stays pure-numpy at import time).

    Returns the CSV path. `rows` is a list of dicts.
    """
    os.makedirs(out_dir, exist_ok=True)
    if not name.endswith(".csv"):
        name = name + ".csv"
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    path = os.path.join(out_dir, name)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    if manifest is not None:
        from benchmarks.paper_eval.paper_config import write_manifest  # lazy
        write_manifest(out_dir, name, **manifest)
    return path
