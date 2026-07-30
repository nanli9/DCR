#!/usr/bin/env python3
"""T14 -- EQUAL-COST arms on the shipped row.

The practitioner's first question, asked by two reviewers and listed by the
2026-07-28 panel as missing evidence: IS THE RECONSTRUCTION-MATCHED CONTACT-ROW
WEIGHT BETTER THAN SPENDING THE SAME BUDGET ON ANOTHER SOLVER ITERATION? Nothing
in the paper answers it, and a per-sweep passivity theorem is not by itself a
recommendation to a practitioner who can also just iterate.

This script answers it by MEASUREMENT on the shipped host, on exactly the
machinery run_t4_shipped.py and run_t9_matched.py already use (their helpers are
imported, never edited): the reduced shelf / ledge / dinner scenes, one substep,
cold start, zero gravity, bystanders parked, ONE isolated leading support row,
modal stiffness scaled by s over logspace(-7, 0, 9) so the row danger index
sweeps across the boundary. 9 s-values x 3 scenes = 27 cells per arm, the same
27 cells T4 and T9 report.

ARMS (name, contact-row modal weight, iterations, modal relaxation theta)
  mass_i1      1/M_q                              1 it   theta=1    baseline
  matched_i1   1/(kappa^2 M_q + h^2 K_q), kappa=2 1 it   theta=1    the proposal
  mass_i2      1/M_q                              2 it   theta=1    "just iterate"
  mass_i4/8/16 1/M_q                            4/8/16   theta=1    how far it goes
  implicit_i1  1/(M_q + h D_q + h^2 K_q)          1 it   theta=1    shipped swap
  relax070_i1  1/M_q                              1 it   theta=0.70 (T8-2 at b->0)
  relax050_i1  1/M_q                              1 it   theta=0.50
  relax025_i1  1/M_q                              1 it   theta=0.25
theta = 0.70 is the shipped-convention relaxation threshold of run_t8_relaxation
(T8-2): with the shipped kappa = 2 reconstruction a cold row is passive iff
theta^2 (kappa^2 + b) < 2 + m/M, i.e. theta < sqrt((2 + m/M)/4) -> 0.707 as
b -> 0 and m/M -> 0. It is the LARGEST theta the paper's own derivation licenses
at the soft end, and it is b-dependent, so it is reported as an arm, not a fix.

REFERENCE (ref_converged): the CONVERGED BACKWARD-EULER step -- implicit weight
(M_q + h D_q + h^2 K_q)^-1 with the matching backward-Euler velocity
reconstruction (kappa = 1, sol._modal_symplectic = False) at 64 iterations. This
is the same reference run_t11_accuracy.py uses analytically; here it is realized
on the shipped solver so the quaternion and velocity-pass terms are included.
Convergence is evidenced per cell by the post-solve gap residual C+ (reported as
C_resid, and normalized by |h v| as C_resid_rel).

REPORTED PER ARM AND CELL
  dE_meas            one-substep total energy change (rigid KE + modal KE + PE)
  dE_over_Eminus     dE_meas / (0.5 M_eff v^2); inject iff > 0
  inject             dE_meas > 1e-12
  overrun            peak modal energy over a 20-frame trail exceeds the whole
                     incoming rigid kinetic energy (trail_ratio > 1)
  amp                row-projected modal amplitude U_y . q after the substep [m]
  amp_ratio          amp / amp_ref against ref_converged (1.0 = reference)
  amp_excess         (amp - amp_ref) / |h v|, the position discrepancy in units
                     of the predicted penetration; stable where amp_ref -> 0
  emodal_ratio       post-substep modal energy / the reference's
  emodal_excess      (E_modal - E_modal_ref) / (0.5 M_eff v^2), the excess modal
                     energy over the converged reference as a fraction of the
                     incoming rigid kinetic energy. This, not emodal_ratio, is
                     the quality headline: the reference deposit itself falls to
                     8.1e-6 of E- on the stiffest ledge cell, so a RATIO there
                     divides by nearly nothing while the EXCESS stays meaningful.
  us_substep         MEASURED wall time of one sol._substep_cpu(h) call from the
                     identical cold snapshot, min of --reps, minus the measured
                     snapshot-restore overhead
  cost_ratio         us_substep / us_substep(matched_i1) on the SAME cell

HONESTY NOTE ON ABSOLUTE TIMES (same rule as run_tcost.py). The host is a
numpy/Python reference solver; its absolute microseconds are not production
representative. Only RATIOS measured between two arms on the same cell and the
same machine are offered as evidence, and the extra cost of the matched weight
is r divides once per substep (us_install_matched), which is reported separately.

THIS EXPERIMENT IS ALLOWED TO FAIL. If the extra iteration dominates the matched
weight at equal cost, that is the result and it is printed as the verdict. The
paper's claim is a per-sweep passivity guarantee, not a claim of dominance.

No tracked file is edited. run_t4_shipped.py and run_t9_matched.py are imported
as libraries.

Run: .venv/bin/python benchmarks/paper_eval/t_onesweep/run_t14_equalcost.py
CLI: --scenes shelf,ledge,dinner  --arms ...  --s-list "..."  --reps 15
     --trail 20  --ref-iters 64  --out t14_equalcost
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

# T4 / T9 harnesses imported as libraries (neither is modified).
from benchmarks.paper_eval.t_onesweep import run_t4_shipped as t4      # noqa: E402
from benchmarks.paper_eval.t_onesweep import run_t9_matched as t9      # noqa: E402
from benchmarks.paper_eval.paper_config import (                        # noqa: E402
    apply_relax, write_manifest)
from benchmarks.paper_eval.x1_passivity.run_weight_swap import (        # noqa: E402
    _install_weight_swap)
from dcr.avbd._solver.solver_xpbd import _quat_to_R                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
KAPPA = 2.0                       # shipped implicit-midpoint reconstruction
REF_NAME = "ref_converged"
REF2_NAME = "ref_converged2x"

ARMS = [
    dict(name="mass_i1",     weight="mass",     iterations=1, relax=1.00,
         symplectic=True),
    dict(name="matched_i1",  weight="matched",  iterations=1, relax=1.00,
         symplectic=True),
    dict(name="mass_i2",     weight="mass",     iterations=2, relax=1.00,
         symplectic=True),
    dict(name="mass_i4",     weight="mass",     iterations=4, relax=1.00,
         symplectic=True),
    dict(name="mass_i8",     weight="mass",     iterations=8, relax=1.00,
         symplectic=True),
    dict(name="mass_i16",    weight="mass",     iterations=16, relax=1.00,
         symplectic=True),
    dict(name="implicit_i1", weight="implicit", iterations=1, relax=1.00,
         symplectic=True),
    dict(name="relax070_i1", weight="mass",     iterations=1, relax=0.70,
         symplectic=True),
    dict(name="relax050_i1", weight="mass",     iterations=1, relax=0.50,
         symplectic=True),
    dict(name="relax025_i1", weight="mass",     iterations=1, relax=0.25,
         symplectic=True),
    dict(name=REF_NAME,      weight="implicit", iterations=64, relax=1.00,
         symplectic=False),
    # convergence control for the reference: same config at 2x the iterations.
    dict(name=REF2_NAME,     weight="implicit", iterations=128, relax=1.00,
         symplectic=False),
]
ARM_BY_NAME = {a["name"]: a for a in ARMS}


# --------------------------------------------------------------------------- #
# timing helper (run_tcost.py convention: min-of-reps rejects scheduler noise)  #
# --------------------------------------------------------------------------- #
def _best(fn, reps):
    best = float("inf")
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        if dt < best:
            best = dt
    return best


def _row_gap(sol, lead_sc):
    """Live support-row gap C = corner_y - (y_rest + U_y . q) at the current
    pose (solver_xpbd.py:1520-1530)."""
    R = _quat_to_R(sol._Q[lead_sc.bi])
    r_w = R @ lead_sc.off
    return (sol._X[lead_sc.bi][1] + r_w[1]
            - (lead_sc.y_rest + float(lead_sc.U_y @ sol._q)))


# --------------------------------------------------------------------------- #
# one cell = one (scene, s, arm). Setup is the T4 harness, helpers imported.    #
# --------------------------------------------------------------------------- #
def run_cell(scene, s, arm, trail=20, reps=15):
    """One T14 cell. Setup mirrors run_t9_matched.run_cell (which mirrors T4)
    verbatim through imported helpers; the ONLY changes are the installed
    contact-row weight, the iteration count, the modal relaxation theta, the
    reconstruction flag, and the added cost measurement."""
    t0 = time.perf_counter()
    spec = ARM_BY_NAME[arm]
    it = int(spec["iterations"])
    rec = dict(scene=scene, s=s, arm=arm, weight=spec["weight"], iterations=it,
               relax=spec["relax"], symplectic=spec["symplectic"], kappa=KAPPA,
               valid=False, reason="", wall_s=0.0)
    try:
        H, sol = t4._build_and_configure(scene, it)
        t4._preflight_structural(sol, it)
        if sol._wq_support is not None:
            raise t4.CellAbort("wq_support not None at build")
        apply_relax(sol, "xpbd", float(spec["relax"]))
        sol._modal_symplectic = bool(spec["symplectic"])
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
        sol._kq = np.asarray(sol._kq, float) * s         # stiffness scale
        sol._dq = np.asarray(sol._dq, float) * np.sqrt(s)
        # T4's contact-free 5-frame preflight asserts that the SCALED kq/dq are
        # live in the stepper and that no contact fires. Its 1e-9 criterion is
        # energy conservation, which only the implicit-midpoint path satisfies;
        # backward Euler is dissipative by construction, so the reference arm
        # would fail a test of the integrator, not of the setup. We therefore run
        # the preflight under the symplectic flag for EVERY arm (it exercises the
        # same scaled _kq array and the same contact generation) and restore the
        # arm's reconstruction immediately after. Recorded, not silently patched.
        _sym_arm = sol._modal_symplectic
        sol._modal_symplectic = True
        rec.update(t4._energy_conservation_preflight(sol, H))
        sol._modal_symplectic = _sym_arm
        if not rec["preflight_ok"]:
            raise t4.CellAbort("energy preflight residual %.3e > 1e-9"
                               % rec["preflight_res"])
        R = _quat_to_R(sol._Q[imp])                      # corner to exact touch
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

        # ---- install the arm's contact-row modal weight (AFTER kq/dq scaling) --
        us_install = 0.0
        if spec["weight"] == "mass":
            sol._wq_support = None                       # shipped 1/M_q
        elif spec["weight"] == "implicit":
            _install_weight_swap(sol)
            if sol._wq_support is None:
                raise t4.CellAbort("implicit weight failed to install")
        elif spec["weight"] == "matched":
            t9._install_matched_weight(sol, KAPPA)
            if sol._wq_support is None:
                raise t4.CellAbort("matched weight failed to install")
            mq_t = np.asarray(sol._mq, float)
            kq_t = np.asarray(sol._kq, float)

            def _inst():
                d = (KAPPA * KAPPA) * mq_t + (h * h) * kq_t
                return np.where(mq_t > 0.0, 1.0 / np.maximum(d, 1e-300), 0.0)
            us_install = _best(_inst, 200) * 1e6
        else:
            raise t4.CellAbort("unknown weight %r" % spec["weight"])
        rec["us_install_matched"] = us_install
        rec["n_modes"] = int(np.asarray(sol._mq).shape[0])
        rec["n_support_rows"] = len(sol._support)

        # ---- row parameters (shared x-axis with T4/T9; predictor is T4's) ------
        mp = t4._predict_mass(sol, imp, lead_sc, h)
        M_eff = 1.0 / mp["w_r"]
        v = mp["v"]
        E_minus = 0.5 * M_eff * v * v
        rec.update(w_r=mp["w_r"], L=mp["L"], a_tilde=mp["a_tilde"],
                   rho_host=mp["rho"], v=v, M_eff=M_eff, E_minus=E_minus,
                   h_sub=h, hv=abs(h * v))

        # ---- ONE measured substep from the cold snapshot ---------------------
        snap = t4._snapshot(sol, lead_sc)
        box, saved = t4._wrap_measure(sol)
        H.world.step()
        t4._unwrap(sol, saved)
        dE_meas = box["E1"] - box["E0"]
        ncontacts = box.get("ncontacts", 0)
        n_active = sum(1 for sc in sol._support if sc.lam > 0.0)
        lead_active = lead_sc.lam > 0.0
        valid = (ncontacts == 0 and n_active == 1 and lead_active)
        amp = float(lead_sc.U_y @ sol._q)                # row-projected q [m]
        e_modal = box["ke"] + box["pe"]
        C_resid = _row_gap(sol, lead_sc)
        rec.update(dE_meas=dE_meas, dE_over_Eminus=dE_meas / E_minus,
                   inject=bool(dE_meas > 1e-12), amp=amp, e_modal=e_modal,
                   modal_ke=box["ke"], modal_pe=box["pe"],
                   C_resid=C_resid, C_resid_rel=abs(C_resid) / abs(h * v),
                   lam=float(lead_sc.lam),
                   n_contacts=ncontacts, n_active_support=n_active, valid=valid)
        if not valid:
            rec["reason"] = ("ncontacts=%d n_active=%d lead_active=%s"
                             % (ncontacts, n_active, lead_active))

        # ---- observational trail (T4 step 9): peak modal energy --------------
        emax = 0.0
        for _ in range(trail):
            H.world.step()
            ke, pe = t4._modal_E(sol)
            emax = max(emax, ke + pe)
        rec["e_modal_trail_peak"] = emax
        rec["trail_ratio"] = emax / E_minus
        rec["overrun"] = bool(emax > E_minus)

        # ---- MEASURED cost of one substep, same cold state, min of `reps` ----
        def _restore():
            t4._restore(sol, snap, lead_sc)

        def _call():
            t4._restore(sol, snap, lead_sc)
            sol._substep_cpu(h)
        t_rest = _best(_restore, reps)
        t_call = _best(_call, reps)
        rec["us_restore"] = t_rest * 1e6
        rec["us_substep"] = max(t_call - t_rest, 0.0) * 1e6
        rec["reps"] = reps
    except t4.CellAbort as e:
        rec["reason"] = str(e)
        rec["valid"] = False
    rec["wall_s"] = time.perf_counter() - t0
    return rec


# --------------------------------------------------------------------------- #
# CSV / driver                                                                #
# --------------------------------------------------------------------------- #
FIELDS = ["scene", "s", "arm", "weight", "iterations", "relax", "symplectic",
          "kappa", "n_modes", "n_support_rows", "w_r", "M_eff", "L", "a_tilde",
          "rho_host", "v", "h_sub", "hv", "E_minus", "dE_meas",
          "dE_over_Eminus", "inject",
          "amp", "amp_ref", "amp_ratio", "amp_excess", "e_modal", "e_modal_ref",
          "emodal_ratio", "emodal_excess", "modal_ke", "modal_pe",
          "e_modal_trail_peak",
          "trail_ratio", "overrun", "C_resid", "C_resid_rel", "lam",
          "us_substep", "us_restore", "us_install_matched", "cost_ratio",
          "reps", "n_contacts", "n_active_support", "valid", "runner_gap",
          "preflight_res", "preflight_ok", "reason", "wall_s"]


def _fill_reference(rows):
    """Attach amp_ref / e_modal_ref / amp_ratio / emodal_ratio / cost_ratio.
    Reference = ref_converged; cost baseline = matched_i1, both per (scene, s)."""
    ref = {}
    base = {}
    for r in rows:
        k = (r["scene"], "%.6e" % float(r["s"]))
        if r["arm"] == REF_NAME and r.get("valid"):
            ref[k] = r
        if r["arm"] == "matched_i1" and r.get("valid"):
            base[k] = r
    for r in rows:
        k = (r["scene"], "%.6e" % float(r["s"]))
        rr = ref.get(k)
        if rr is not None and r.get("valid"):
            r["amp_ref"] = rr["amp"]
            r["e_modal_ref"] = rr["e_modal"]
            r["amp_ratio"] = (r["amp"] / rr["amp"]) if rr["amp"] != 0.0 else float("nan")
            r["emodal_ratio"] = ((r["e_modal"] / rr["e_modal"])
                                 if rr["e_modal"] != 0.0 else float("nan"))
            r["amp_excess"] = (r["amp"] - rr["amp"]) / r["hv"]
            r["emodal_excess"] = (r["e_modal"] - rr["e_modal"]) / r["E_minus"]
        bb = base.get(k)
        if bb is not None and r.get("valid") and bb.get("us_substep"):
            r["cost_ratio"] = r["us_substep"] / bb["us_substep"]
    return rows


def _summary(rows, arms):
    print("\n=== T14 equal-cost summary (27 cells per arm unless noted) ===",
          flush=True)
    hdr = ("  %-15s %4s %6s %5s  %8s %8s   %10s   %9s %9s   %8s %7s"
           % ("arm", "it", "theta", "cells", "inject", "overrun",
              "worst dE/E-", "med dEm/E-", "max dEm/E-", "us/step", "cost x"))
    print(hdr, flush=True)
    print("  " + "-" * (len(hdr) - 2), flush=True)
    out = []
    for a in arms:
        cells = [r for r in rows if r["arm"] == a and r.get("valid")]
        if not cells:
            continue
        spec = ARM_BY_NAME[a]
        n_inj = sum(1 for r in cells if r["inject"])
        n_ovr = sum(1 for r in cells if r["overrun"])
        worst = max(r["dE_over_Eminus"] for r in cells)

        def _fin(key):
            return [r[key] for r in cells
                    if r.get(key) is not None and np.isfinite(r.get(key, np.nan))]
        amps = _fin("amp_ratio")
        aexc = _fin("amp_excess")
        eexc = _fin("emodal_excess")
        med_amp = float(np.median(amps)) if amps else float("nan")
        max_aexc = max(np.abs(aexc)) if aexc else float("nan")
        med_eexc = float(np.median(eexc)) if eexc else float("nan")
        max_eexc = max(np.abs(eexc)) if eexc else float("nan")
        us = float(np.median([r["us_substep"] for r in cells]))
        crs = [r["cost_ratio"] for r in cells if r.get("cost_ratio")]
        cr = float(np.median(crs)) if crs else float("nan")
        print("  %-15s %4d %6.2f %5d  %4d/%-3d %4d/%-3d   %+10.3e   %+9.4f "
              "%9.4g   %8.1f %7.2f"
              % (a, spec["iterations"], spec["relax"], len(cells),
                 n_inj, len(cells), n_ovr, len(cells), worst,
                 med_eexc, max_eexc, us, cr), flush=True)
        out.append(dict(arm=a, iterations=spec["iterations"], theta=spec["relax"],
                        cells=len(cells), n_inject=n_inj, n_overrun=n_ovr,
                        worst_dE_over_Eminus=worst,
                        med_emodal_excess=med_eexc,
                        max_abs_emodal_excess=max_eexc,
                        max_abs_amp_excess=max_aexc,
                        med_amp_ratio=med_amp,
                        us_substep_median=us, cost_ratio_median=cr))
    return out


def _verdict(agg):
    """Print the plain-language verdict, negative if that is what was measured."""
    by = {a["arm"]: a for a in agg}
    m = by.get("matched_i1")
    i2 = by.get("mass_i2")
    if m is None or i2 is None:
        print("\nVERDICT: not computable (matched_i1 or mass_i2 missing).")
        return
    print("\n--- VERDICT ---")
    print("  matched_i1 : %d/%d injecting, %d/%d overrun, cost %.2fx"
          % (m["n_inject"], m["cells"], m["n_overrun"], m["cells"],
             m["cost_ratio_median"]))
    print("  mass_i2    : %d/%d injecting, %d/%d overrun, cost %.2fx"
          % (i2["n_inject"], i2["cells"], i2["n_overrun"], i2["cells"],
             i2["cost_ratio_median"]))
    if i2["n_inject"] <= m["n_inject"] and i2["cost_ratio_median"] <= 1.05:
        print("  NEGATIVE for the matched weight: the extra iteration is at "
              "least as passive at no more cost.")
    elif i2["n_inject"] <= m["n_inject"]:
        print("  MIXED: the extra iteration matches the passivity of the "
              "matched weight but costs %.2fx more."
              % i2["cost_ratio_median"])
    else:
        print("  POSITIVE for the matched weight: it is passive on %d more "
              "cells than the extra iteration and costs %.2fx of it."
              % (i2["n_inject"] - m["n_inject"],
                 m["cost_ratio_median"] / max(i2["cost_ratio_median"], 1e-12)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--arms", default=",".join(a["name"] for a in ARMS))
    ap.add_argument("--s-list", default="",
                    help="comma list; default logspace(-7,0,9) (T4/T9 grid)")
    ap.add_argument("--trail", type=int, default=20)
    ap.add_argument("--reps", type=int, default=15,
                    help="min-of-N repetitions for the substep cost measurement")
    ap.add_argument("--ref-iters", type=int, default=64,
                    help="iterations for the converged backward-Euler reference")
    ap.add_argument("--out", default="t14_equalcost")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    ARM_BY_NAME[REF_NAME]["iterations"] = int(args.ref_iters)
    ARM_BY_NAME[REF2_NAME]["iterations"] = 2 * int(args.ref_iters)

    if args.s_list.strip():
        s_grid = [float(x) for x in args.s_list.split(",") if x.strip()]
    else:
        s_grid = list(np.logspace(-7, 0, 9))
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for a in arms:
        if a not in ARM_BY_NAME:
            raise SystemExit("unknown arm %r (known: %s)"
                             % (a, ", ".join(ARM_BY_NAME)))

    print("### T14 equal-cost arms on the shipped row (%s, %s) ###"
          % (platform.machine(), platform.system()), flush=True)
    print("arms: %s" % ", ".join(arms), flush=True)
    print("s-grid (%d): %s" % (len(s_grid),
          ", ".join("%.1e" % x for x in s_grid)), flush=True)

    rows = []
    for scene in scenes:
        for s in s_grid:
            for a in arms:
                rec = run_cell(scene, s, a, trail=args.trail, reps=args.reps)
                rows.append(rec)
                print("  %-6s s=%.1e %-13s rho=%.3e dE/E-=%+.4e inj=%s "
                      "trail/E-=%.3f amp=%+.4e us=%.1f valid=%s %s"
                      % (scene, s, a, rec.get("rho_host", float("nan")),
                         rec.get("dE_over_Eminus", float("nan")),
                         rec.get("inject"), rec.get("trail_ratio", float("nan")),
                         rec.get("amp", float("nan")),
                         rec.get("us_substep", float("nan")),
                         rec["valid"], rec["reason"]), flush=True)

    _fill_reference(rows)
    csv_path = os.path.join(OUT, "%s.csv" % args.out)
    ordered = sorted(rows, key=lambda r: (str(r["scene"]), float(r["s"]),
                                          str(r["arm"])))
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: r.get(k, "") for k in FIELDS})

    agg = _summary(ordered, arms)
    agg_path = os.path.join(OUT, "%s_summary.csv" % args.out)
    if agg:
        with open(agg_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(agg[0].keys()))
            w.writeheader()
            for r in agg:
                w.writerow(r)
    _verdict(agg)

    # marginal cost of one extra Gauss-Seidel sweep, measured, and the fixed
    # per-substep overhead it is diluted by on this host (predict, contact
    # generation, velocity pass; all outside the iteration loop).
    by = {a["arm"]: a for a in agg}
    us_marg = float("nan")
    us_fixed = float("nan")
    if "mass_i1" in by:
        u1 = by["mass_i1"]["us_substep_median"]
        top = max((n for n in ("mass_i16", "mass_i8", "mass_i4", "mass_i2")
                   if n in by), key=lambda n: ARM_BY_NAME[n]["iterations"],
                  default=None)
        if top is not None:
            nit = ARM_BY_NAME[top]["iterations"]
            us_marg = (by[top]["us_substep_median"] - u1) / (nit - 1)
            us_fixed = u1 - us_marg
            print("\n  measured marginal cost of one extra sweep: %.1f us "
                  "(from mass_i1 -> %s); fixed per-substep overhead outside the "
                  "iteration loop %.1f us of %.1f (%.0f%%), which is why doubling "
                  "the iteration count costs %.2fx here and not 2.00x"
                  % (us_marg, top, us_fixed, u1, 100.0 * us_fixed / u1,
                     by["mass_i2"]["cost_ratio_median"] if "mass_i2" in by
                     else float("nan")))

    ref_cells = [r for r in ordered if r["arm"] == REF_NAME and r.get("valid")]
    ref_res = (max(r["C_resid_rel"] for r in ref_cells) if ref_cells
               else float("nan"))
    # convergence control: reference at 2x iterations must give the same amplitude
    ref2 = {(r["scene"], "%.6e" % float(r["s"])): r for r in ordered
            if r["arm"] == REF2_NAME and r.get("valid")}
    d2 = [abs(r["amp"] - ref2[k]["amp"]) / max(abs(ref2[k]["amp"]), 1e-300)
          for r in ref_cells
          for k in [(r["scene"], "%.6e" % float(r["s"]))] if k in ref2]
    ref_conv = max(d2) if d2 else float("nan")
    write_manifest(
        OUT, "%s.csv" % args.out, scenes=scenes, solvers=["xpbd"],
        note=("T14: EQUAL-COST arms on the shipped SolverXPBD support row, one "
              "substep, cold start, single isolated leading row, 9-point "
              "stiffness sweep x %d scenes. Arms: matched (kappa=2 charge "
              "4M_q+h^2K_q) at 1 iteration vs mass-only 1/M_q at 2 and 4 "
              "iterations vs the shipped implicit weight at 1 iteration vs "
              "mass-only under-relaxation theta=0.70/0.50/0.25 at 1 iteration. "
              "Reference = converged backward-Euler step (implicit weight, "
              "backward-Euler reconstruction, %d iterations; max post-solve gap "
              "residual %.2e of |h v|; doubling to %d iterations moves the "
              "modal amplitude by at most %.2e relative). Cost is MEASURED: "
              "min-of-%d wall time of sol._substep_cpu minus the snapshot-restore "
              "overhead, on a numpy/Python reference host, so only per-cell "
              "RATIOS are evidence. Measured marginal cost of one extra sweep "
              "%.1f us against %.1f us of fixed per-substep overhead outside the "
              "iteration loop. Quality is reported as emodal_excess = "
              "(E_modal - E_modal_ref)/E-, not as a ratio, because the reference "
              "deposit itself falls to 8.1e-6 of E- on the stiffest ledge cell."
              % (len(scenes), int(args.ref_iters), ref_res,
                 2 * int(args.ref_iters), ref_conv, args.reps,
                 us_marg, us_fixed)))
    print("\nCSV: %s (%d rows)" % (csv_path, len(ordered)))
    if agg:
        print("summary CSV: %s" % agg_path)
    print("reference max post-solve gap residual: %.3e of |h v| (%d cells)"
          % (ref_res, len(ref_cells)))
    print("reference convergence control (%d vs %d iterations): max relative "
          "amplitude change %.3e" % (int(args.ref_iters), 2 * int(args.ref_iters),
                                     ref_conv))


if __name__ == "__main__":
    main()
