#!/usr/bin/env python3
"""T9 -- SHIPPED solver: RECONSTRUCTION-MATCHED contact-row weight (working fix).

Companion arm to run_t4_shipped.py. T4 showed that under the shipped SYMPLECTIC
(implicit-midpoint) modal reconstruction the backward-Euler implicit weight
w = (M_q + h D_q + h^2 K_q)^-1 -- the E-WS weight-swap arm -- INJECTS on the
single-row cold impact at low modal stiffness (shelf 7/9, ledge 5/9 cells), because
that weight is reconstruction-matched to kappa = 1, not to the shipped kappa = 2.

This module installs the RECONSTRUCTION-MATCHED weight for the shipped stepper and
measures that it is passive on exactly those cells. From the machine-checked
one-sweep law (run_t7_reconstruction.py, T7-2/T7-4; foundation note "M1"):

    charge mass in BOTH denominator and correction: qdot+ = kappa*dq/h, wq = 1/mu_c;
    inject iff  M*m*(kappa^2+b) > 2*M*mu_c + mu_c^2                          (T7-2)
    matched     mu_star = m(kappa^2+b) = kappa^2*M_q + h^2*K_q  gives
                dE = -1/2 * M mu_star/(M+mu_star) * v^2 < 0  for ANY kappa    (T7-4)

For the shipped symplectic default kappa = 2 this is mu_star = m(4+b) =
4*M_q + h^2*K_q (DAMPING-INDEPENDENT: at cold start the free modal predictor is
inert, so the damper stores no energy -- T7 case i, EXACT identity for any zeta).
Installed exactly like run_weight_swap._install_weight_swap (opt-in sol._wq_support,
which enters the support-row projection at solver_xpbd.py:1520 in BOTH the mobility
denominator (line 1537) and the modal position correction (line 1549); with
modal_relax = 1 -- the T4 config -- the correction weight equals the denominator
weight, so the installed mu_c is the charge mass in BOTH, the T7 clean model).

# DEVIATION (foundation note M1 / T7-4, vs paper Eq. 10 forced IIR): the modal q is
# co-solved in the support constraint under an implicit-midpoint reconstruction; the
# contact-row modal weight is set to the reconstruction-matched charge mass so the
# one-substep energy is the perfectly-inelastic loss of (M_eff, mu_star), passive.

Everything else is the T4 harness verbatim (imported, not copied): the SAME scene
builders, single-leading-row isolation, kq/dq scaling sweep, energy preflight,
snapshot/restore BE control, and one-substep dE measurement. No tracked file is
edited; run_t4_shipped.py is imported, not modified.

Two measurements per cell (T4 convention):
  dE_meas  -- shipped SYMPLECTIC path (plan-mandated primary), matched weight.
  dE_be    -- backward-Euler control on the SAME cold state, matched weight (the
              m(4+b) weight is even heavier than the kappa=1 match m(1+b), so it is
              passive under BE too; a super-passive control, not the working point).

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/run_t9_matched.py
CLI: --scenes shelf,ledge,dinner  --s-list "..." | --trim  --out t4_matched
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

# Import the T4 harness as a library (setup helpers reused verbatim; T4 unedited).
from benchmarks.paper_eval.t_onesweep import run_t4_shipped as t4    # noqa: E402
from benchmarks.paper_eval.paper_config import write_manifest        # noqa: E402
from dcr.avbd._solver.solver_xpbd import _quat_to_R                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
KAPPA = 2.0                       # shipped implicit-midpoint reconstruction


# --------------------------------------------------------------------------- #
# matched weight install + predictor                                          #
# --------------------------------------------------------------------------- #
def _install_matched_weight(sol, kappa: float = KAPPA) -> dict:
    """Set the reconstruction-matched contact-row modal weight on a built XPBD
    solver (foundation note T7-4). Mirrors run_weight_swap._install_weight_swap
    but with the kappa-matched denominator

        mu_star = m(kappa^2 + b) = kappa^2 * M_q + h^2 * K_q            (T7, matched)

    instead of the backward-Euler denom (M_q + h D_q + h^2 K_q). DAMPING-INDEPENDENT
    by construction (no D_q term): the matched mass is the stored modal energy per
    unit reconstruction rate, and at cold start the free predictor is inert so the
    damper holds none of it. Sets sol._wq_support (opt-in; None => shipped 1/M_q)."""
    mq = np.asarray(sol._mq, dtype=np.float64)
    kq = np.asarray(sol._kq, dtype=np.float64)
    h = float(sol.dt) / int(sol.substeps)
    w_explicit = np.where(mq > 0.0, 1.0 / np.maximum(mq, 1e-300), 0.0)
    denom = (kappa * kappa) * mq + (h * h) * kq          # mu_star = m(kappa^2+b)
    w_matched = np.where(mq > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)
    sol._wq_support = w_matched
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(w_explicit > 0, w_matched / w_explicit, np.nan)
    return dict(h_sub=h, wratio_min=float(np.nanmin(ratio)),
                wratio_max=float(np.nanmax(ratio)))


def _predict_matched(sol, imp, sc, h, mass_pred, kappa: float = KAPPA) -> dict:
    """Reconstruction-matched-weight predictor (foundation note T7-2/T7-4).

    Per-mode installed charge mass mu_star[i] = kappa^2 M_q[i] + h^2 K_q[i]; the
    support row's effective modal mobility is W_m = Sum U_y^2 / mu_star, so the
    effective (single-row-collapse) charge mass is mu_c = 1/W_m and, since the
    installed weight IS the matched weight, the effective host matched mass equals
    mu_c. With rigid row mobility w_r = 1/M_eff (mass_pred, the T4 mass-arm value),
    the note's symplectic injection law T7-2 collapses to the danger index

        rho_matched = M_eff / (2 M_eff + mu_c)  in (0, 1/2)   (T7-2, matched)

    -- strictly below 1 for any mu_c > 0 (unconditional passivity) -- and the
    one-substep energy is the perfectly-inelastic-impact loss (T7-4)

        dE = -1/2 * M_eff mu_c/(M_eff + mu_c) * v^2  < 0.
    """
    mq = np.asarray(sol._mq); kq = np.asarray(sol._kq)
    U = sc.U_y
    denom = (kappa * kappa) * mq + (h * h) * kq
    w_matched = np.where(mq > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)
    w_r = float(mass_pred["w_r"])
    W_m = float((U * U) @ w_matched)                     # = 1/mu_c (modal mobility)
    w_row = w_r + W_m
    L = h * h * float((U * U) @ (kq * w_matched * w_matched))
    a_tilde = float(mass_pred["a_tilde"]); v = float(mass_pred["v"])
    M_eff = 1.0 / w_r
    mu_c = (1.0 / W_m) if W_m > 0.0 else np.inf
    rho_matched = M_eff / (2.0 * M_eff + mu_c)
    dE = -0.5 * M_eff * mu_c / (M_eff + mu_c) * v * v
    return dict(w_r=w_r, w_row=w_row, L=L, a_tilde=a_tilde, W_m=W_m,
                M_eff=M_eff, mu_c=mu_c, rho=rho_matched, v=v, dE=dE)


# --------------------------------------------------------------------------- #
# one cell -- mirrors run_t4_shipped.run_cell, matched arm (T4 helpers reused) #
# --------------------------------------------------------------------------- #
def run_cell(scene, s, iterations=1, be_control=True, trail=20, kappa=KAPPA):
    """One T9 cell (matched arm). Setup is byte-for-byte the T4 harness (imported
    helpers); the ONLY changes are the installed weight and the predictor."""
    t0 = time.perf_counter()
    rec = dict(scene=scene, s=s, arm="matched", kappa=kappa, iterations=iterations,
               valid=False, reason="", wall_s=0.0)
    try:
        H, sol = t4._build_and_configure(scene, iterations)
        t4._preflight_structural(sol, iterations)
        if sol._wq_support is not None:
            raise t4.CellAbort("wq_support not None at build")
        h = sol.dt / sol.substeps
        sol.gravity[:] = 0.0
        sol._modal_grav_acc[:] = 0.0
        imp = t4._identify_impactor(H, sol)
        for i in range(sol._X.shape[0]):                 # park bystanders +50 y
            if i == imp:
                continue
            sol._X[i][1] += t4.PARK
            sol._V[i][:] = 0.0
            sol._W[i][:] = 0.0
        if scene == "dinner":
            sol._Q[imp] = t4._aa_xyzw([1, 0, 0], t4.TILT_X)
        sol._Q[imp] = t4._qmul_xyzw(t4._aa_xyzw([0, 0, 1], t4.TILT_Z), sol._Q[imp])
        sol._W[imp][:] = 0.0
        gaps = t4._impactor_gaps(sol, imp)               # unique leading row
        if len(gaps) < 2:
            raise t4.CellAbort("impactor has < 2 support rows")
        if abs(gaps[0][0] - gaps[1][0]) < 1e-9:
            raise t4.CellAbort("leading support row is a tie (%.3e)"
                               % (gaps[1][0] - gaps[0][0]))
        lead_si = gaps[0][1]
        sol._support = [sc for k, sc in enumerate(sol._support)
                        if sc.bi != imp or k == lead_si]
        lead_sc = next(sc for sc in sol._support if sc.bi == imp)
        sol._kq = np.asarray(sol._kq, float) * s         # stiffness scale (rho sweep)
        sol._dq = np.asarray(sol._dq, float) * np.sqrt(s)
        rec.update(t4._energy_conservation_preflight(sol, H))
        if not rec["preflight_ok"]:
            raise t4.CellAbort("energy preflight residual %.3e > 1e-9"
                               % rec["preflight_res"])
        R = _quat_to_R(sol._Q[imp])                      # shift corner to exact touch
        r_w = R @ lead_sc.off
        corner_y = sol._X[imp][1] + r_w[1]
        C_min = corner_y - (lead_sc.y_rest + float(lead_sc.U_y @ sol._q))
        sol._X[imp][1] -= C_min
        sol._V[imp] = np.array([0.0, -1.0, 0.0])
        sol._W[imp][:] = 0.0
        for sc in sol._support:
            sc.mu = 0.0
        g2 = sorted(
            (float((_quat_to_R(sol._Q[sc.bi]) @ sc.off)[1]) + sol._X[sc.bi][1]
             - (sc.y_rest + float(sc.U_y @ sol._q)))
            for sc in sol._support if sc is not lead_sc)
        runner_gap = g2[0] if g2 else np.inf
        rec["runner_gap"] = runner_gap
        if runner_gap <= 5.0 * h * 1.0:
            raise t4.CellAbort("runner-up gap %.3e <= 5 h|v|" % runner_gap)
        # ---- install the RECONSTRUCTION-MATCHED weight (after kq/dq scaling) ----
        diag = _install_matched_weight(sol, kappa)
        if sol._wq_support is None:
            raise t4.CellAbort("matched weight failed to install")
        rec.update(wratio_min=diag["wratio_min"], wratio_max=diag["wratio_max"])
        # ---- predictors: host mass-arm danger index (shared x) + matched ----
        mp = t4._predict_mass(sol, imp, lead_sc, h)      # host rho (default 1/M_q)
        pm = _predict_matched(sol, imp, lead_sc, h, mp, kappa)
        rec.update(w_r=pm["w_r"], w_row=pm["w_row"], L=pm["L"],
                   a_tilde=pm["a_tilde"], rho_host=mp["rho"], rho_matched=pm["rho"],
                   mu_c=pm["mu_c"], M_eff=pm["M_eff"], W_m=pm["W_m"], v=pm["v"],
                   dE_pred=pm["dE"])
        # ---- measurement: BE control (snapshot/restore) then symplectic ----
        snap = t4._snapshot(sol, lead_sc)
        dE_be = None
        if be_control:
            sol._modal_symplectic = False
            box_be, saved = t4._wrap_measure(sol)
            H.world.step()
            t4._unwrap(sol, saved)
            dE_be = box_be["E1"] - box_be["E0"]
            t4._restore(sol, snap, lead_sc)
            sol._modal_symplectic = True
        box, saved = t4._wrap_measure(sol)
        H.world.step()
        t4._unwrap(sol, saved)
        dE_meas = box["E1"] - box["E0"]
        ncontacts = box.get("ncontacts", 0)
        n_active = sum(1 for sc in sol._support if sc.lam > 0.0)
        lead_active = lead_sc.lam > 0.0
        valid = (ncontacts == 0 and n_active == 1 and lead_active)
        rec.update(
            dE_meas=dE_meas, dE_be=dE_be, modal_ke=box["ke"], modal_pe=box["pe"],
            n_contacts=ncontacts, n_active_support=n_active, valid=valid,
            reldiff_sym=(abs(dE_meas - pm["dE"]) / max(abs(pm["dE"]), 1e-15)),
            reldiff_be=(abs(dE_be - pm["dE"]) / max(abs(pm["dE"]), 1e-15)
                        if dE_be is not None else None),
            passive_meas=(dE_meas <= 1e-12),
            passive_be=((dE_be <= 1e-12) if dE_be is not None else None),
            rho_lt_1=(pm["rho"] < 1.0))
        if not valid:
            rec["reason"] = ("ncontacts=%d n_active=%d lead_active=%s"
                             % (ncontacts, n_active, lead_active))
        emax = 0.0                                       # observational trail
        for _ in range(trail):
            H.world.step()
            ke, pe = t4._modal_E(sol)
            emax = max(emax, ke + pe)
        rec["e_modal_trail_peak"] = emax
    except t4.CellAbort as e:
        rec["reason"] = str(e)
        rec["valid"] = False
    rec["wall_s"] = time.perf_counter() - t0
    return rec


# --------------------------------------------------------------------------- #
# CSV / driver                                                                #
# --------------------------------------------------------------------------- #
FIELDS = ["scene", "s", "arm", "kappa", "iterations", "w_r", "w_row", "L",
          "a_tilde", "W_m", "M_eff", "mu_c", "rho_host", "rho_matched", "rho_lt_1",
          "v", "dE_pred", "dE_meas", "dE_be", "modal_ke", "modal_pe", "reldiff_sym",
          "reldiff_be", "passive_meas", "passive_be", "n_contacts",
          "n_active_support", "valid", "runner_gap", "wratio_min", "wratio_max",
          "preflight_res", "preflight_ok", "e_modal_trail_peak", "reason", "wall_s"]


def _load_existing(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return list(csv.DictReader(fh))


def _key(r):
    return (str(r["scene"]), "%.6e" % float(r["s"]), str(r["arm"]),
            int(r["iterations"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--s-list", default="",
                    help="comma list; default logspace(-7,0,9) or trim")
    ap.add_argument("--trim", action="store_true", help="use 7-pt s-grid")
    ap.add_argument("--no-be", action="store_true", help="skip BE control")
    ap.add_argument("--trail", type=int, default=20)
    ap.add_argument("--out", default="t4_matched")
    ap.add_argument("--append", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    n_s = 7 if args.trim else 9
    if args.s_list.strip():
        s_grid = [float(x) for x in args.s_list.split(",") if x.strip()]
    else:
        s_grid = list(np.logspace(-7, 0, n_s))
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    be = not args.no_be

    print("### T9 matched-weight row sweep (%s, %s) kappa=%g mu*=m(%g+b) ###"
          % (platform.machine(), platform.system(), KAPPA, KAPPA ** 2), flush=True)
    print("s-grid (%d): %s" % (len(s_grid),
          ", ".join("%.1e" % x for x in s_grid)), flush=True)

    rows = []
    for scene in scenes:
        for s in s_grid:
            rec = run_cell(scene, s, iterations=1, be_control=be, trail=args.trail,
                           kappa=KAPPA)
            rows.append(rec)
            print("  %-6s matched s=%.1e rho_host=%.3e rho_matched=%.4f "
                  "dE_pred=%+.3e dE_meas=%+.3e dE_be=%+.3e passive=%s valid=%s %s"
                  % (scene, s, rec.get("rho_host", float("nan")),
                     rec.get("rho_matched", float("nan")),
                     rec.get("dE_pred", float("nan")),
                     rec.get("dE_meas", float("nan")),
                     (rec.get("dE_be") if rec.get("dE_be") is not None
                      else float("nan")),
                     rec.get("passive_meas"), rec["valid"], rec["reason"]),
                  flush=True)

    csv_path = os.path.join(OUT, "%s.csv" % args.out)
    merged = {}
    if args.append:
        for r in _load_existing(csv_path):
            merged[_key(r)] = r
    for r in rows:
        merged[_key(r)] = r
    ordered = sorted(merged.values(),
                     key=lambda r: (str(r["scene"]), float(r["s"])))
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    write_manifest(
        OUT, "%s.csv" % args.out, scenes=scenes, solvers=["xpbd"],
        note=("T9: shipped SolverXPBD support row, one-substep cold-start single-row "
              "impact, RECONSTRUCTION-MATCHED contact-row weight mu*=m(kappa^2+b)="
              "%g*M_q+h^2*K_q (kappa=%g, shipped symplectic). Companion to "
              "run_t4_shipped.py (helpers imported, T4 unedited). dE_meas=symplectic "
              "(primary) vs dE_be=backward-Euler control; passive iff dE<=1e-12. "
              "rho_matched=M/(2M+mu_c)<1/2 (foundation note T7-2/T7-4)."
              % (KAPPA ** 2, KAPPA)))
    print("\nCSV: %s (%d rows)" % (csv_path, len(ordered)))
    _summary(ordered)


def _summary(rows):
    print("\n--- T9 matched-weight acceptance summary ---", flush=True)
    for scene in sorted(set(r["scene"] for r in rows)):
        cells = [r for r in rows if r["scene"] == scene
                 and int(r["iterations"]) == 1]
        valid = [r for r in cells if str(r["valid"]) == "True"]
        pm = sum(1 for r in valid if str(r.get("passive_meas")) == "True")
        pb = sum(1 for r in valid if str(r.get("passive_be")) == "True")
        rlt = sum(1 for r in valid if str(r.get("rho_lt_1")) == "True")
        rho_max = max((float(r["rho_matched"]) for r in valid
                       if r.get("rho_matched") not in ("", None)), default=float("nan"))
        print("%-6s | cells=%d valid=%d | passive(sym)=%d/%d passive(be)=%d/%d | "
              "rho_matched<1: %d/%d (max=%.4f)"
              % (scene, len(cells), len(valid), pm, len(valid), pb, len(valid),
                 rlt, len(valid), rho_max), flush=True)


if __name__ == "__main__":
    main()
