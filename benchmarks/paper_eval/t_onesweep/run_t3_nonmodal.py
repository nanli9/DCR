#!/usr/bin/env python3
"""T3 -- NONMODAL mass-spring validation of the one-sweep matrix condition (R4).

Canonical theory: scratchpad/onesweep_theory_note.md, Result 4 (R4). Plan:
wf1/plan.md section T3. This experiment kills the "modal-artifact" reading of the
one-sweep injection: it reproduces the exact R4 energy-sign boundary in PLAIN
point-mass / spring degrees of freedom in physical coordinates, with NO
eigendecomposition, NO modal basis, and NO import from dcr.modal anywhere. The
row danger index rho = L / w_m (with L = h^2 J M^-1 K M^-1 J^T the row-projected
stiffness mobility and w_m = w_r + J M^-1 J^T the mass-only row mobility) predicts
the sign of the true one-projection energy change on a chain of physical springs
exactly as it does for a modal reduction, because R4 is a coordinate-free matrix
statement, h^2 J M^-1 K M^-1 J^T  vs  J M^-1 J^T.

Because the whole point is "no eigendecomposition, no modal basis anywhere below",
this file runs a SOURCE SELF-SCAN at startup: the substrings "eig" and "modal"
must not appear anywhere after the boundary sentinel line. That is why the body
below speaks of "row mobility" (not the w-word that embeds e-i-g), of
"adjacent-link springs" (not the n-word that embeds e-i-g), and of "physical /
restorative degrees of freedom" (not the m-word). The scan itself builds the two
forbidden substrings from fragments so it does not trip on its own source.

Derivations re-verified in-session (execution agent, 2026-07-23), matching the
note's R4 and the scaffold common.py DERIVATION LEDGER:

  Mass-only arm, one cold-start projection on the contact row, physical coords:
    dlam   = -h v / w_m
    dx     = M_c^-1 J_c^T dlam              (physical position deposit)
    v+     = v + w_r dlam / h               (rigid block, full dlam)
    dE     = 0.5 (1/w_r) (v+^2 - v^2) + 0.5 (1/h^2) dx^T M_c dx + 0.5 dx^T K dx
           = (v^2 / (2 w_m^2)) (L - w_m)                          [algebra below]
           = (v^2 / (2 w_m)) (rho - 1)
    => collapse identity y := 2 dE w_m / v^2 = rho - 1  EXACTLY (hard, mass-only).
    Rigid piece: v+ = v (w_m - w_r)/w_m, so 0.5(1/w_r)(v+^2 - v^2)
      = 0.5 v^2 (w_r - 2 w_m)/w_m^2.
    Chain kinetic: 0.5 (1/h^2) dlam^2 J_c M_c^-1 J_c^T = 0.5 v^2 (w_m - w_r)/w_m^2.
    Chain potential: 0.5 dlam^2 J_c M_c^-1 K M_c^-1 J_c^T = 0.5 v^2 L / w_m^2.
    Sum: 0.5 v^2 [ (w_r - 2 w_m) + (w_m - w_r) + L ] / w_m^2 = 0.5 v^2 (L - w_m)/w_m^2.

  Matrix implicit arm, W_e = (M_c + h^2 K)^-1 in BOTH denominator and correction:
    w_eff = w_r + J_c W_e J_c^T,  dlam = -h v / w_eff,  dx = W_e J_c^T dlam.
    Chain kinetic + potential = 0.5 (1/h^2) dlam^2 J_c W_e (M_c + h^2 K) W_e J_c^T
                              = 0.5 (1/h^2) dlam^2 J_c W_e J_c^T   (telescopes)
                              = 0.5 v^2 (w_eff - w_r)/w_eff^2.
    With the same rigid algebra: dE = -v^2 / (2 w_eff) EXACTLY (undamped), < 0
    unconditionally (w_eff > 0). This is the R3/R4 implicit-arm remedy, verified
    here in physical coordinates with a dense N=8 solve, no spectral reduction.

Output: out/t3_nonmodal.csv (+ .config.json manifest). No figure here: figure F3
is built later by make_figs.py from this CSV (plan section 3).

Run (canonical full sweep, ~seconds):
  /Users/nan/Desktop/DCR/.venv/bin/python \
      benchmarks/paper_eval/t_onesweep/run_t3_nonmodal.py
Chunkable via --variants / --mratios / --arms / --nk / --out (see --help).
"""
# SELF_SCAN_BOUNDARY_v1 -- forbidden token substrings must not appear below here.
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

# _ROOT sys.path pattern (mirrors the x1_passivity harness lines 46-49): repo
# root on path so this runs from any cwd.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.t_onesweep import common as C  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

# Default output basename -- assembled from fragments so the literal file body
# never carries the forbidden substring, though the runtime value equals the
# plan's prescribed output basename.
_OUT_DEFAULT = "t3_non" + "mo" + "dal"
_SENTINEL = "SELF_SCAN_BOUNDARY_v1"
# Forbidden substrings built from fragments (so this line is itself clean).
_FORBIDDEN = ("e" + "ig", "mo" + "dal")

VARIANTS = ("i_single", "ii_uniform", "iii_wide", "iv_nonuniform")
MRATIOS_DEFAULT = (0.01, 1.0, 10.0)


# --------------------------------------------------------------------------- #
# Source self-scan (plan T3: the two forbidden substrings, built as fragments    #
# in _FORBIDDEN, must not appear anywhere below the boundary sentinel)            #
# --------------------------------------------------------------------------- #
def source_self_scan():
    """Scan THIS file's source below the boundary sentinel for the forbidden
    substrings. Returns a list of (token, line_no, line_text) hits (empty ==
    clean). The check is case-insensitive; the sentinel and the token fragments
    above are constructed so the scanner cannot flag itself.
    """
    with open(os.path.abspath(__file__), "r") as fh:
        src = fh.read()
    idx = src.find(_SENTINEL)
    if idx < 0:
        raise RuntimeError("self-scan: boundary sentinel not found in source")
    body = src[idx:]
    body_lo = body.lower()
    base_line = src[:idx].count("\n")  # 0-based line of the sentinel
    hits = []
    for tok in _FORBIDDEN:
        start = 0
        while True:
            pos = body_lo.find(tok, start)
            if pos < 0:
                break
            line_no = base_line + body[:pos].count("\n") + 1  # 1-based
            line_txt = body.splitlines()[body[:pos].count("\n")].strip()
            hits.append((tok, line_no, line_txt))
            start = pos + 1
    return hits


# --------------------------------------------------------------------------- #
# Variant builders (physical chains; NO spectral reduction)                    #
# --------------------------------------------------------------------------- #
def chain_spec(variant, m_base):
    """Return (N, masses (N,), spring_shape (N,), J_c (N,)) for a variant.

    spring_shape is the per-link stiffness at unit stiffness scale k=1; the actual
    stiffness array is k * spring_shape. All chains are anchored (a ground spring
    at the last node), so K is SPD and (M_c + h^2 K) is invertible.

      i_single      : one restorative node with a ground spring (scalar sanity).
      ii_uniform    : 8-node chain, equal masses, equal adjacent-link + ground
                      springs, contact row on node 0  (J_c = [-1, 0, ...]).
      iii_wide      : same 8-node chain, a plank row across nodes 0 and 1
                      (J_c = [-0.5, -0.5, 0, ...]) -- exercises the off-diagonal
                      of K through J M^-1 K M^-1 J^T.
      iv_nonuniform : 8-node chain, m_j = m (1 + 0.5 sin j), k_j = k (1 + 0.3 cos j),
                      contact row on node 0.
    """
    if variant == "i_single":
        N = 1
        masses = np.array([m_base], dtype=np.float64)
        spring_shape = np.array([1.0], dtype=np.float64)      # ground spring only
        J_c = np.array([-1.0], dtype=np.float64)
    elif variant in ("ii_uniform", "iii_wide"):
        N = 8
        masses = m_base * np.ones(N, dtype=np.float64)
        spring_shape = np.ones(N, dtype=np.float64)           # 7 links + 1 ground
        J_c = np.zeros(N, dtype=np.float64)
        if variant == "ii_uniform":
            J_c[0] = -1.0
        else:
            J_c[0] = -0.5
            J_c[1] = -0.5
    elif variant == "iv_nonuniform":
        N = 8
        j = np.arange(N, dtype=np.float64)
        masses = m_base * (1.0 + 0.5 * np.sin(j))
        spring_shape = (1.0 + 0.3 * np.cos(j))
        J_c = np.zeros(N, dtype=np.float64)
        J_c[0] = -1.0
    else:
        raise ValueError(f"unknown variant {variant!r}")
    return N, masses, spring_shape, J_c


def assemble(N, masses, spring_shape, k):
    """Dense (K, M_c) for the chain at stiffness scale k. Uses C.chain_matrices
    (tridiagonal assembly, no spectral reduction)."""
    K, M_c = C.chain_matrices(N, masses, k * spring_shape, anchored=True)
    return K, M_c


# --------------------------------------------------------------------------- #
# One cold-start projection on the contact row (physical coordinates)          #
# --------------------------------------------------------------------------- #
def project(arm, J_c, M_c, K, w_r, h, v):
    """One unilateral projection on the contact row from cold start, measuring
    the TRUE physical energy change.

      arm == "mass"     : row mobility W = M_c^-1        (shipped 1/M_q analogue)
      arm == "implicit" : row mobility W = (M_c + h^2 K)^-1  (dense N=8 solve)

    Returns dict(dE, v_plus, dx, w_row). Cold start: chain at rest (x = xdot = 0),
    contact touching, incoming gap rate v < 0; predicted penetration C~ = h v.
    """
    Minv = np.linalg.inv(M_c)
    if arm == "mass":
        W = Minv
    elif arm == "implicit":
        W = np.linalg.inv(M_c + (h * h) * K)
    else:
        raise ValueError(f"arm must be 'mass' or 'implicit', got {arm!r}")

    w_row = w_r + float(J_c @ (W @ J_c))
    C_tilde = h * v
    dlam = -C_tilde / w_row                     # hard contact, a_tilde = 0, cold lam=0
    dx = (W @ J_c) * dlam                        # physical position deposit
    xdot = dx / h
    v_plus = v + w_r * dlam / h                  # rigid block, full dlam

    M_eq = 1.0 / w_r
    E_minus = 0.5 * M_eq * v * v                 # chain at rest contributes 0
    E_plus = (0.5 * M_eq * v_plus * v_plus
              + 0.5 * float(xdot @ (M_c @ xdot))
              + 0.5 * float(dx @ (K @ dx)))
    return dict(dE=E_plus - E_minus, v_plus=v_plus, dx=dx, w_row=w_row)


# --------------------------------------------------------------------------- #
# Cell sweep                                                                   #
# --------------------------------------------------------------------------- #
def run_cells(variants, mratios, arms, nk, rho_lo, rho_hi, h, v):
    """Return (rows, arrays) where rows is a list of CSV dicts and arrays holds
    stacked numpy vectors for the vectorized acceptance asserts."""
    rho_targets = np.logspace(np.log10(rho_lo), np.log10(rho_hi), nk)
    do_impl = "implicit" in arms
    do_mass = "mass" in arms
    rows = []
    acc = {kk: [] for kk in
           ("rho", "dE_mass", "dE_mass_form", "y", "y_theory",
            "dE_impl", "dE_impl_form", "w_m")}

    for variant in variants:
        for m_base in mratios:
            N, masses, spring_shape, J_c = chain_spec(variant, m_base)
            w_r = 1.0 / 1.0                                   # M = 1 (rigid mass)
            # w_m is stiffness-independent; L is linear in k. Calibrate k so the
            # measured rho = L / w_m hits each target on the logspace grid.
            M_c = np.diag(masses)
            Minv = np.linalg.inv(M_c)
            w_m = w_r + float(J_c @ (Minv @ J_c))
            K_unit, _ = assemble(N, masses, spring_shape, 1.0)
            L_unit = (h * h) * float(J_c @ (Minv @ (K_unit @ (Minv @ J_c))))
            rho_per_k = L_unit / w_m                          # rho = rho_per_k * k

            for rho_t in rho_targets:
                k = rho_t / rho_per_k
                K, M_c = assemble(N, masses, spring_shape, k)
                L = (h * h) * float(J_c @ (Minv @ (K @ (Minv @ J_c))))
                rho = L / w_m

                row = dict(variant=variant, N=N, m=m_base, k=k,
                           w_r=w_r, w_m=w_m, L=L, rho=rho)

                # --- mass-only arm (measurement) + R4 matrix formula ---------- #
                if do_mass:
                    pm = project("mass", J_c, M_c, K, w_r, h, v)
                    dE_mass = pm["dE"]
                    dE_mass_form = C.r4_dE_mass(v, w_r, w_m, L, a_tilde=0.0)
                    y = C.collapse_y(dE_mass, w_m, v)
                else:
                    dE_mass = float("nan")
                    dE_mass_form = float("nan")
                    y = float("nan")
                y_theory = rho - 1.0

                # --- matrix implicit arm (measurement) + formula ------------- #
                if do_impl:
                    pi = project("implicit", J_c, M_c, K, w_r, h, v)
                    dE_impl = pi["dE"]
                    w_eff = C.r4_w_eff(w_r, J_c, M_c, K, h)
                    dE_impl_form = C.r4_dE_implicit(v, w_eff, a_tilde=0.0)
                else:
                    dE_impl = float("nan")
                    w_eff = float("nan")
                    dE_impl_form = float("nan")

                sign_agree = ""
                if do_mass:
                    if abs(rho - 1.0) > 1e-9:
                        sign_agree = str(bool((dE_mass > 0.0) == (rho > 1.0)))
                    else:
                        sign_agree = "band"

                row.update(dE_mass=dE_mass, dE_impl=dE_impl, y=y,
                           y_theory=y_theory, w_eff=w_eff,
                           dE_mass_form=dE_mass_form,
                           dE_impl_form=dE_impl_form, sign_agree=sign_agree)
                rows.append(row)

                acc["rho"].append(rho)
                acc["w_m"].append(w_m)
                acc["dE_mass"].append(dE_mass)
                acc["dE_mass_form"].append(dE_mass_form)
                acc["y"].append(y)
                acc["y_theory"].append(y_theory)
                acc["dE_impl"].append(dE_impl)
                acc["dE_impl_form"].append(dE_impl_form)

    arrays = {kk: np.asarray(vv, dtype=np.float64) for kk, vv in acc.items()}
    return rows, arrays, do_mass, do_impl


# --------------------------------------------------------------------------- #
# Acceptance                                                                   #
# --------------------------------------------------------------------------- #
def check_and_report(clog, rows, arr, do_mass, do_impl, v):
    rho = arr["rho"]
    w_m = arr["w_m"]
    band = np.abs(rho - 1.0) <= 1e-9        # dead band (rho == 1 calibration cell)
    live = ~band

    if do_mass:
        dE_mass = arr["dE_mass"]
        dE_mass_form = arr["dE_mass_form"]
        y = arr["y"]
        y_theory = arr["y_theory"]

        # (a) collapse identity on EVERY cell, atol = 1e-12 * max(1, rho).
        resid_a = np.abs(y - y_theory)
        thr_a = 1e-12 * np.maximum(1.0, rho)
        clog.assert_true(np.all(resid_a <= thr_a),
                         label="T3(a) collapse |2 dE w_m/v^2 - (rho-1)| "
                               "<= 1e-12*max(1,rho) on all cells")
        # (b) sign agreement outside the 1e-9 band.
        sign_ok = (dE_mass[live] > 0.0) == (rho[live] > 1.0)
        clog.assert_true(np.all(sign_ok),
                         label="T3(b) sign(dE_mass)==(rho>1) outside 1e-9 band")
        # (c) measured dE_mass == R4 matrix formula, rel <= 1e-12 (live cells;
        #     the single rho==1 calibration cell has dE==0 and is covered by (a)).
        clog.assert_close(dE_mass[live], dE_mass_form[live], rtol=1e-12, atol=0.0,
                          label="T3(c) dE_mass == R4 matrix formula (rel<=1e-12)")

        # reporting aggregates
        _report_a = dict(max_resid=float(np.max(resid_a)),
                         max_resid_norm=float(np.max(resid_a / thr_a)),
                         n_sign_live=int(live.sum()),
                         n_sign_ok=int(sign_ok.sum()),
                         max_relc=float(np.max(np.abs(
                             (dE_mass[live] - dE_mass_form[live])
                             / dE_mass_form[live]))))
    else:
        _report_a = None

    if do_impl:
        dE_impl = arr["dE_impl"]
        dE_impl_form = arr["dE_impl_form"]
        # (d1) measured implicit dE == -v^2/(2 w_eff) rel <= 1e-12 on all cells.
        clog.assert_close(dE_impl, dE_impl_form, rtol=1e-12, atol=0.0,
                          label="T3(d1) dE_impl == -v^2/(2 w_eff) (rel<=1e-12)")
        # (d2) implicit arm strictly dissipative on all cells.
        clog.assert_true(np.all(dE_impl < 0.0),
                         label="T3(d2) dE_impl < 0 on all cells")
        _report_d = dict(all_neg=bool(np.all(dE_impl < 0.0)),
                         max_reld=float(np.max(np.abs(
                             (dE_impl - dE_impl_form) / dE_impl_form))),
                         max_dE_impl=float(np.max(dE_impl)))
    else:
        _report_d = None

    # ---- per-variant table (max collapse residual, sign agreement, implicit) - #
    print("\n=== T3 ACCEPTANCE (per variant) ===")
    hdr = (f"{'variant':16s} {'cells':>5s} {'max|y-(rho-1)|':>16s} "
           f"{'max_norm_resid':>15s} {'sign_ok/live':>13s} "
           f"{'impl_all<0':>10s} {'max_rel_d':>11s}")
    print(hdr)
    variants = []
    for r in rows:
        if r["variant"] not in variants:
            variants.append(r["variant"])
    per_variant = {}
    for vv in variants:
        idx = np.array([i for i, r in enumerate(rows) if r["variant"] == vv])
        vb = np.abs(rho[idx] - 1.0) <= 1e-9
        vl = ~vb
        if do_mass:
            vresid = np.abs(arr["y"][idx] - arr["y_theory"][idx])
            vthr = 1e-12 * np.maximum(1.0, rho[idx])
            vmax = float(np.max(vresid))
            vmax_norm = float(np.max(vresid / vthr))
            vsign = (arr["dE_mass"][idx][vl] > 0.0) == (rho[idx][vl] > 0.0 + 1.0)
            n_ok = int(vsign.sum())
            n_live = int(vl.sum())
        else:
            vmax = vmax_norm = float("nan")
            n_ok = n_live = 0
        if do_impl:
            v_all_neg = bool(np.all(arr["dE_impl"][idx] < 0.0))
            v_reld = float(np.max(np.abs(
                (arr["dE_impl"][idx] - arr["dE_impl_form"][idx])
                / arr["dE_impl_form"][idx])))
        else:
            v_all_neg = False
            v_reld = float("nan")
        per_variant[vv] = dict(cells=len(idx), max_resid=vmax,
                               max_resid_norm=vmax_norm, sign_ok=n_ok,
                               sign_live=n_live, impl_all_neg=v_all_neg,
                               max_rel_d=v_reld)
        print(f"{vv:16s} {len(idx):5d} {vmax:16.3e} {vmax_norm:15.3e} "
              f"{str(n_ok)+'/'+str(n_live):>13s} {str(v_all_neg):>10s} "
              f"{v_reld:11.3e}")

    print("\n=== T3 ACCEPTANCE (overall) ===")
    if _report_a is not None:
        print(f"(a) collapse: max|y-(rho-1)| = {_report_a['max_resid']:.3e}, "
              f"max normalized residual = {_report_a['max_resid_norm']:.3e} "
              f"(pass iff <= 1.0)")
        print(f"(b) sign agreement outside 1e-9 band: "
              f"{_report_a['n_sign_ok']}/{_report_a['n_sign_live']}")
        print(f"(c) dE_mass vs R4 matrix formula: max rel err = "
              f"{_report_a['max_relc']:.3e}")
    if _report_d is not None:
        print(f"(d1) dE_impl vs -v^2/(2 w_eff): max rel err = "
              f"{_report_d['max_reld']:.3e}")
        print(f"(d2) dE_impl < 0 on all cells: {_report_d['all_neg']} "
              f"(max dE_impl = {_report_d['max_dE_impl']:.3e})")
    return per_variant, _report_a, _report_d


# --------------------------------------------------------------------------- #
def parse_args(argv):
    p = argparse.ArgumentParser(description="T3 physical mass-spring R4 validation")
    p.add_argument("--variants", default=",".join(VARIANTS),
                   help="comma list from %s" % ",".join(VARIANTS))
    p.add_argument("--mratios", default=",".join(str(x) for x in MRATIOS_DEFAULT),
                   help="comma list of chain-node/rigid mass ratios (M=1)")
    p.add_argument("--arms", default="mass,implicit",
                   help="comma list from {mass,implicit}")
    p.add_argument("--nk", type=int, default=25, help="stiffness grid size")
    p.add_argument("--rho-lo", type=float, default=1e-2)
    p.add_argument("--rho-hi", type=float, default=1e2)
    p.add_argument("--h", type=float, default=1e-3)
    p.add_argument("--v", type=float, default=-1.0)
    p.add_argument("--out", default=_OUT_DEFAULT, help="CSV basename in out/")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # ---- source self-scan FIRST (plan T3: no forbidden substrings below banner)
    hits = source_self_scan()
    if hits:
        print("SOURCE SELF-SCAN FAILED -- forbidden substring(s) below the "
              "boundary sentinel:")
        for tok, ln, txt in hits:
            print(f"  token {tok!r} at line {ln}: {txt}")
        sys.exit(2)
    print(f"[scan] source self-scan clean: none of {list(_FORBIDDEN)} "
          f"appear below the boundary sentinel.")

    clog = C.CheckLog()
    clog.assert_true(True, label="T3 source self-scan: no forbidden substrings "
                                 "below banner")

    variants = [s.strip() for s in args.variants.split(",") if s.strip()]
    for vv in variants:
        if vv not in VARIANTS:
            print(f"unknown variant {vv!r}; choose from {VARIANTS}")
            sys.exit(2)
    mratios = [float(s) for s in args.mratios.split(",") if s.strip()]
    arms = [s.strip() for s in args.arms.split(",") if s.strip()]
    for a in arms:
        if a not in ("mass", "implicit"):
            print(f"unknown arm {a!r}; choose from mass,implicit")
            sys.exit(2)

    print(f"[cfg] variants={variants} mratios={mratios} arms={arms} "
          f"nk={args.nk} rho=[{args.rho_lo:g},{args.rho_hi:g}] "
          f"h={args.h:g} v={args.v:g}")

    rows, arr, do_mass, do_impl = run_cells(
        variants, mratios, arms, args.nk, args.rho_lo, args.rho_hi,
        args.h, args.v)

    fieldnames = ["variant", "N", "m", "k", "w_r", "w_m", "L", "rho",
                  "dE_mass", "dE_impl", "y",
                  "y_theory", "w_eff", "dE_mass_form", "dE_impl_form",
                  "sign_agree"]
    note = ("T3: physical mass-spring chain, one cold-start unilateral "
            "projection on a contact row; measured true-energy sign vs row "
            "danger index rho = L/w_m; both row-mobility arms (mass-only "
            "M_c^-1 and implicit (M_c+h^2 K)^-1). NO spectral reduction, NO "
            "reduced-basis import; source self-scan enforced. Validates R4 of "
            "onesweep_theory_note.md.")
    manifest = dict(scenes=variants, solvers=["numpy-oneshot"], note=note,
                    nk=args.nk, rho_span=[args.rho_lo, args.rho_hi],
                    h=args.h, v=args.v, arms=arms, mratios=mratios)
    csv_path = C.write_csv(OUT, args.out, rows, fieldnames=fieldnames,
                           manifest=manifest)
    print(f"[csv] {csv_path}  ({len(rows)} cells)")

    check_and_report(clog, rows, arr, do_mass, do_impl, args.v)

    clog.finalize("T3 physical mass-spring R4 validation")


if __name__ == "__main__":
    main()
