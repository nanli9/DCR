#!/usr/bin/env python3
"""E-S3 — post-projection contact validity probe (MIG 2026 short paper).

ISOLATED benchmark. Instruments the XPBD passivity gamma-projection entirely
from OUTSIDE the solver by wrapping three call sites at runtime; it does not
modify solver source and does not change solver behaviour (every wrapper
returns the original value unchanged).

The hole this closes: the gamma-projection scales the realized modal state
(q, qdot) *after* the contact solve has finished (solver_xpbd.py:1244-1250,
the last act of _substep_cpu). Scaling q moves the deformed support surface
y_rest + U_y.q without re-solving contact, so a reviewer will ask what happens
to contact validity. We measure it.

Per clamp-active substep we log:
  (a) max support-gap violation immediately AFTER the gamma-scale
      C = corner_y - (y_rest + U_y.q); violation = max(0, -C)   [m]
  (b) the corrective normal impulse in the NEXT substep, vs the steady-state
      (unclamped) median                                        [N.s]
  (c) lambda variance across support rows (chatter proxy)
  (d) net rigid linear-momentum change                          [kg.m/s]

Wrap points (all source-free, per the solver's own structure):
  (i)   dcr.avbd._solver.passivity.passivity_gamma -- module attribute, and the
        import at solver_xpbd.py:1221 is FUNCTION-LOCAL, so it is re-resolved
        every substep and a module-level patch is picked up. Fires after the
        velocity solve, BEFORE the scale.
  (ii)  ledger.commit(...) -- called at solver_xpbd.py:1252, AFTER the scale.
  (iii) solver._substep_cpu -- substep boundaries, for the next-substep readout.

NOTE ON (d): across the projection itself the momentum change is ZERO BY
CONSTRUCTION -- the scale touches only _q/_qdot, never _V/_W
(solver_xpbd.py:1246-1247). We verify that numerically (it is the honest
statement of what the projection does and does not do) and separately report
the substep-to-substep momentum change, which is where any real effect must
appear, against the unclamped baseline.

Out: out/{projection_validity.csv, projection_validity.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_projection_validity.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                    # noqa: E402
from dcr.avbd.modal_qblock import _quat_to_R as _qR              # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _gaps(sol):
    """All support-row gaps C = corner_y - (y_rest + U_y.q). C<0 => violation.

    Mirrors _project_support (solver_xpbd.py:1435-1444) and the existing
    external probe scripts/probe_native_energy_loop.py:50-61.
    """
    q, X, Q = sol._q, sol._X, sol._Q
    out = np.empty(len(sol._support))
    for i, sc in enumerate(sol._support):
        R = _qR(np.asarray(Q[sc.bi], dtype=np.float64))
        corner_y = float(X[sc.bi][1]) + float((R @ sc.off)[1])
        out[i] = corner_y - (sc.y_rest + float(sc.U_y @ q))
    return out


def _viol(sol):
    g = _gaps(sol)
    return float(np.maximum(0.0, -g).max()) if g.size else 0.0


def _lam(sol):
    return np.array([sc.lam for sc in sol._support], dtype=np.float64)


def _momentum(sol):
    m = np.asarray(sol._mass, dtype=np.float64)
    dyn = np.asarray(sol._invm, dtype=np.float64) > 0.0
    return (m[:, None] * np.asarray(sol._V, dtype=np.float64))[dyn].sum(axis=0)


def run_cell(scene, iters, subs, relax, nframes, settle=8):
    build = SCENES[scene]
    H = build(device="cpu", iterations=iters, avbd_substeps=subs, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True     # forces the HOST path (the clamp is host-only)
    apply_passivity(sol, "xpbd", enable=True, eta=1.0)
    led = sol._psv_ledger
    h_sub = sol.dt / sol.substeps

    rec = {}                 # scratch for the current substep
    steps = []               # one dict per substep

    # ---- (i) pre-scale capture: patch the module attribute ----------------
    orig_gamma = _psv_mod.passivity_gamma

    def gamma_wrap(e_new, e_old, budget, tol=1e-12):
        g = orig_gamma(e_new, e_old, budget, tol=tol)
        rec["gamma"] = float(g)
        rec["pre_viol"] = _viol(sol)
        rec["pre_P"] = _momentum(sol)
        return g                                   # unchanged: no behaviour change

    _psv_mod.passivity_gamma = gamma_wrap

    # ---- (ii) post-scale capture: wrap the ledger's commit ----------------
    orig_commit = led.commit

    def commit_wrap(realized_gain, budget, alpha, e_modal_now=None):
        rec["post_viol"] = _viol(sol)
        rec["post_P"] = _momentum(sol)
        return orig_commit(realized_gain, budget, alpha,
                           e_modal_now=e_modal_now)

    led.commit = commit_wrap

    # ---- (iii) substep boundaries ----------------------------------------
    orig_substep = sol._substep_cpu

    def substep_wrap(h):
        rec.clear()
        orig_substep(h)
        lam = _lam(sol)
        steps.append(dict(
            gamma=rec.get("gamma", 1.0),
            pre_viol=rec.get("pre_viol", float("nan")),
            post_viol=rec.get("post_viol", float("nan")),
            dP_proj=float(np.linalg.norm(rec["post_P"] - rec["pre_P"]))
                    if "post_P" in rec and "pre_P" in rec else float("nan"),
            P_end=_momentum(sol),
            lam_sum=float(lam.sum()), lam_var=float(lam.var()) if lam.size else 0.0,
            lam_max=float(lam.max()) if lam.size else 0.0))

    sol._substep_cpu = substep_wrap

    try:
        w = H.world
        for _ in range(settle + nframes):
            w.step()
    finally:
        _psv_mod.passivity_gamma = orig_gamma      # always restore the module

    # ---- reduce -----------------------------------------------------------
    n = len(steps)
    clamped = [k for k in range(n) if steps[k]["gamma"] < 1.0]
    free = [k for k in range(n) if steps[k]["gamma"] >= 1.0]
    imp = lambda k: steps[k]["lam_sum"] / h_sub          # noqa: E731  [N.s]
    steady = float(np.median([imp(k) for k in free])) if free else float("nan")

    def med_max(vals):
        v = np.asarray([x for x in vals if np.isfinite(x)], dtype=np.float64)
        return (float(np.median(v)), float(v.max())) if v.size else (
            float("nan"), float("nan"))

    post_med, post_max = med_max([steps[k]["post_viol"] for k in clamped])
    pre_med, pre_max = med_max([steps[k]["pre_viol"] for k in clamped])
    # (b) corrective impulse in the substep AFTER a clamp-active one
    nxt = [imp(k + 1) for k in clamped if k + 1 < n]
    nxt_med, nxt_max = med_max(nxt)
    # (c) chatter proxy
    lv_med, lv_max = med_max([steps[k]["lam_var"] for k in clamped])
    lv_free_med, _ = med_max([steps[k]["lam_var"] for k in free])
    # (d) momentum
    dP_med, dP_max = med_max([steps[k]["dP_proj"] for k in clamped])
    dPs_c = [float(np.linalg.norm(steps[k + 1]["P_end"] - steps[k]["P_end"]))
             for k in clamped if k + 1 < n]
    dPs_f = [float(np.linalg.norm(steps[k + 1]["P_end"] - steps[k]["P_end"]))
             for k in free if k + 1 < n]
    dPs_c_med, dPs_c_max = med_max(dPs_c)
    dPs_f_med, _ = med_max(dPs_f)

    return dict(
        scene=scene, iters=iters, substeps=subs, relax=relax,
        n_substeps=n, n_clamped=len(clamped),
        gamma_min=min((steps[k]["gamma"] for k in clamped), default=1.0),
        gap_viol_post_median_m=post_med, gap_viol_post_max_m=post_max,
        gap_viol_pre_median_m=pre_med, gap_viol_pre_max_m=pre_max,
        impulse_next_median_Ns=nxt_med, impulse_next_max_Ns=nxt_max,
        impulse_steady_median_Ns=steady,
        impulse_next_over_steady=(nxt_med / steady) if steady else float("nan"),
        lam_var_clamped_median=lv_med, lam_var_clamped_max=lv_max,
        lam_var_free_median=lv_free_med,
        dP_across_projection_median=dP_med, dP_across_projection_max=dP_max,
        dP_substep_clamped_median=dPs_c_med, dP_substep_clamped_max=dPs_c_max,
        dP_substep_free_median=dPs_f_med,
        ledger_holds=led.holds(), ledger_passive=led.passive())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge")
    ap.add_argument("--budgets", default="4x1,8x2")
    ap.add_argument("--relax", type=float, default=0.7)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="projection_validity")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    budgets = [tuple(int(v) for v in b.lower().split("x"))
               for b in args.budgets.split(",") if b.strip()]

    print(f"### E-S3 post-projection contact validity (XPBD, relax={args.relax}, "
          f"{platform.machine()}) ###", flush=True)
    rows = []
    for scene in scenes:
        for (it, su) in budgets:
            r = run_cell(scene, it, su, args.relax, args.nframes)
            rows.append(r)
            print(f"\n  {scene} {it}x{su}: clamp fired {r['n_clamped']}/"
                  f"{r['n_substeps']} substeps, min gamma={r['gamma_min']:.6g}")
            print(f"    (a) post-scale gap violation  median={r['gap_viol_post_median_m']:.3e} m"
                  f"  worst={r['gap_viol_post_max_m']:.3e} m"
                  f"   (pre-scale worst {r['gap_viol_pre_max_m']:.3e} m)")
            print(f"    (b) next-substep normal impulse median={r['impulse_next_median_Ns']:.4g} N.s"
                  f"  worst={r['impulse_next_max_Ns']:.4g}"
                  f"   steady={r['impulse_steady_median_Ns']:.4g}"
                  f"   ratio={r['impulse_next_over_steady']:.3f}")
            print(f"    (c) lambda variance clamped median={r['lam_var_clamped_median']:.4g}"
                  f"  worst={r['lam_var_clamped_max']:.4g}"
                  f"   unclamped median={r['lam_var_free_median']:.4g}")
            print(f"    (d) |dP| across projection median={r['dP_across_projection_median']:.3e}"
                  f"  worst={r['dP_across_projection_max']:.3e} kg.m/s"
                  f"   (expected 0 by construction)")
            print(f"        |dP| substep-to-substep clamped median={r['dP_substep_clamped_median']:.4g}"
                  f"  worst={r['dP_substep_clamped_max']:.4g}"
                  f"   unclamped median={r['dP_substep_free_median']:.4g}")
            print(f"    ledger: holds={r['ledger_holds']} passive={r['ledger_passive']}")

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
                   note=("E-S3: per clamp-active substep -- post-scale support-gap "
                         "violation, next-substep corrective normal impulse vs "
                         "unclamped steady state, lambda variance, rigid momentum "
                         "change. Instrumented by runtime wrappers only."))
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
