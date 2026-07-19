#!/usr/bin/env python3
"""R5.2 — post-projection contact validity on the AVBD host (plan §6.7).

Ports the E-S3 probe (`run_projection_validity.py`, position-based host) to the
augmented-Lagrangian host so Table 2 covers AVBD's problem cells: the table
scene at 4x1, both relaxations, which are the only two cells where AVBD exceeds
R=1 (1.179 and 1.700) and which carry its two real Eq.-(2) overdrafts
(+5.35 J, +15.08 J -- R1).

The wrappers do NOT port unchanged. Four things differ, and each is a place a
naive port silently produces wrong numbers:

  1. `sol._q` on this host is the list of BODY QUATERNIONS (xyzw), not the
     modal coordinate. The modal state is `_q_modal_host`. Reading `_q` as the
     E-S3 helper does would compute a gap from a quaternion.
  2. Support rows are stored as parallel lists (`_support_row_cidx` into
     `_rows`, `_support_U_y_rows`, `_support_y_rest`), not as objects carrying
     `.U_y`/`.y_rest`/`.off`.
  3. The ledger is built LAZILY on the first substep (solver_6dof.py:2449),
     unlike the position-based host which builds it at `set_modal_support`. A
     harness that grabs `sol._psv_ledger` at setup finds None and measures
     NOTHING. It must be pre-constructed. (This is the whole of E-S1b caveat 1.)
  4. The multiplier is `sol.c_lambda[cidx]`, and support rows are push-up
     (fmin=-inf, fmax=0), so lambda is NEGATIVE; magnitudes are used.

Clamp site: `_modal_commit` (solver_6dof.py:2637), the support-only path. The
table scene is built without native cargo, so the augmented (q_support, a_cargo)
clamp at :3303 does not fire here -- asserted at runtime rather than assumed.

`_psv_monitor_only` is forced False so the projection is ACTIVE, exactly as the
matrix harness's ON column does (E-S1b caveat 3). That is a measurement-side
override of a production default, not a solver change: the repo default stays
monitor-only. Every wrapper returns its wrapped value unchanged.

Out: out/{projection_validity_avbd.csv, *.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/run_projection_validity_avbd.py
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
    """All support-row gaps C = corner_y - (y_rest + U_y.q); C<0 is violation.

    AVBD equivalent of E-S3's `_gaps`. `_qR` takes xyzw and `sol.q` is warp's
    xyzw layout, so no reordering is needed here (unlike the §15 energy path,
    which needs `_psv_quats_wxyz`)."""
    q = sol._q_modal_host
    if q is None or not sol._support_row_cidx:
        return np.zeros(0)
    X = sol.x.numpy()
    Qt = sol.q.numpy()
    out = np.empty(len(sol._support_row_cidx))
    for s, cidx in enumerate(sol._support_row_cidx):
        row = sol._rows[cidx]
        bi = int(row.body_a)
        R = _qR(np.asarray(Qt[bi], dtype=np.float64))
        off = np.asarray(row.off_a, dtype=np.float64)
        corner_y = float(X[bi][1]) + float((R @ off)[1])
        U_y = np.asarray(sol._support_U_y_rows[s], dtype=np.float64)
        r = min(U_y.size, q.size)
        out[s] = corner_y - (float(sol._support_y_rest[s])
                             + float(U_y[:r] @ q[:r]))
    return out


def _viol(sol):
    g = _gaps(sol)
    return float(np.maximum(0.0, -g).max()) if g.size else 0.0


def _lam(sol):
    """|lambda| on the support rows (push-up rows carry lambda <= 0)."""
    if not sol._support_row_cidx:
        return np.zeros(0)
    lam = sol.c_lambda.numpy()
    return np.abs(np.array([float(lam[c]) for c in sol._support_row_cidx],
                           dtype=np.float64))


def _momentum(sol):
    m = np.asarray(sol._mass, dtype=np.float64)
    dyn = m > 0.0
    return (m[:, None] * np.asarray(sol.v.numpy(), dtype=np.float64))[dyn].sum(axis=0)


def run_cell(scene, iters, subs, relax, nframes, settle=8, eta=1.0):
    H = SCENES[scene](device="cpu", iterations=iters, avbd_substeps=subs,
                      solver="avbd")
    sol = H.world._solver
    apply_relax(sol, "avbd", relax)
    sol._modal_symplectic = True          # host path; the clamp is host-only
    apply_passivity(sol, "avbd", enable=True, eta=eta)
    sol._psv_monitor_only = False         # make the projection ACTIVE

    # (3) PRE-CONSTRUCT the ledger. The lazy init is guarded
    # `if self._psv_ledger is None`, so the solver adopts this object.
    if getattr(sol, "_psv_ledger", None) is None:
        from dcr.avbd._solver.passivity import PassivityLedger
        sol._psv_ledger = PassivityLedger(eta=float(eta))
    led = sol._psv_ledger
    assert led is not None, "AVBD ledger absent -- the probe would measure nothing"
    # This scene must be on the support-only clamp path, not the cargo one.
    assert not getattr(sol, "_cargo_blocks", None), \
        "native cargo present: the augmented clamp (:3303) would fire instead"

    h_sub = sol.dt / sol.substeps
    rec, steps = {}, []

    # ---- (i) pre-scale: patch the module attribute (imported function-locally
    #          inside _modal_commit, so a module patch is picked up) ----------
    orig_gamma = _psv_mod.passivity_gamma

    def gamma_wrap(e_new, e_old, budget, tol=1e-12):
        g = orig_gamma(e_new, e_old, budget, tol=tol)
        rec["gamma"] = float(g)
        rec["pre_viol"] = _viol(sol)
        rec["pre_P"] = _momentum(sol)
        return g                                   # unchanged: no behaviour change

    _psv_mod.passivity_gamma = gamma_wrap

    # ---- (ii) post-scale: wrap the ledger's commit ------------------------
    orig_commit = led.commit

    def commit_wrap(realized_gain, budget, alpha, e_modal_now=None):
        rec["post_viol"] = _viol(sol)
        rec["post_P"] = _momentum(sol)
        return orig_commit(realized_gain, budget, alpha, e_modal_now=e_modal_now)

    led.commit = commit_wrap

    # ---- (iii) substep boundaries ----------------------------------------
    orig_step = sol._step_one

    def step_wrap():
        rec.clear()
        orig_step()
        lam = _lam(sol)
        steps.append(dict(
            gamma=rec.get("gamma", 1.0),
            pre_viol=rec.get("pre_viol", float("nan")),
            post_viol=rec.get("post_viol", float("nan")),
            dP_proj=float(np.linalg.norm(rec["post_P"] - rec["pre_P"]))
                    if "post_P" in rec and "pre_P" in rec else float("nan"),
            P_end=_momentum(sol),
            lam_sum=float(lam.sum()),
            lam_var=float(lam.var()) if lam.size else 0.0))

    sol._step_one = step_wrap

    try:
        w = H.world
        for _ in range(settle + nframes):
            w.step()
    finally:
        _psv_mod.passivity_gamma = orig_gamma

    # ---- reduce (identical reduction to E-S3, so the rows are comparable) --
    n = len(steps)
    clamped = [k for k in range(n) if steps[k]["gamma"] < 1.0]
    free = [k for k in range(n) if steps[k]["gamma"] >= 1.0]
    # UNITS: this host's `c_lambda` is a FORCE in newtons -- X1d
    # (`run_static_ledger.py`) validates Sum|lambda_N| = m.g per resting body
    # against the analytic weight. So the impulse is lambda*h_sub, NOT the
    # lambda/h_sub of the position-based probe, whose multiplier is a different
    # object. The reported quantity is the RATIO next/steady, which is invariant
    # to this factor either way; the absolute column is fixed so nothing
    # mislabelled is frozen.
    imp = lambda k: steps[k]["lam_sum"] * h_sub          # noqa: E731  [N.s]
    steady = float(np.median([imp(k) for k in free])) if free else float("nan")

    def med_max(vals):
        v = np.asarray([x for x in vals if np.isfinite(x)], dtype=np.float64)
        return (float(np.median(v)), float(v.max())) if v.size else (
            float("nan"), float("nan"))

    post_med, post_max = med_max([steps[k]["post_viol"] for k in clamped])
    pre_med, pre_max = med_max([steps[k]["pre_viol"] for k in clamped])
    nxt_med, nxt_max = med_max([imp(k + 1) for k in clamped if k + 1 < n])
    lv_med, lv_max = med_max([steps[k]["lam_var"] for k in clamped])
    lv_free_med, _ = med_max([steps[k]["lam_var"] for k in free])
    dP_med, dP_max = med_max([steps[k]["dP_proj"] for k in clamped])
    dPs_c_med, dPs_c_max = med_max(
        [float(np.linalg.norm(steps[k + 1]["P_end"] - steps[k]["P_end"]))
         for k in clamped if k + 1 < n])
    dPs_f_med, _ = med_max(
        [float(np.linalg.norm(steps[k + 1]["P_end"] - steps[k]["P_end"]))
         for k in free if k + 1 < n])

    return dict(
        solver="avbd", scene=scene, iters=iters, substeps=subs, relax=relax,
        n_substeps=n, n_clamped=len(clamped),
        gamma_min=min((steps[k]["gamma"] for k in clamped), default=1.0),
        gap_viol_post_median_m=post_med, gap_viol_post_max_m=post_max,
        gap_viol_pre_median_m=pre_med, gap_viol_pre_max_m=pre_max,
        impulse_next_median_Ns=nxt_med, impulse_next_max_Ns=nxt_max,
        impulse_steady_median_Ns=steady,
        impulse_next_over_steady=(nxt_med / steady) if steady else float("nan"),
        lam_var_clamped_median=lv_med, lam_var_clamped_max=lv_max,
        lam_var_free_median=lv_free_med,
        lam_var_ratio=(lv_med / lv_free_med) if lv_free_med else float("nan"),
        dP_across_projection_median=dP_med, dP_across_projection_max=dP_max,
        dP_substep_clamped_median=dPs_c_med, dP_substep_clamped_max=dPs_c_max,
        dP_substep_free_median=dPs_f_med,
        ledger_holds=led.holds(), ledger_passive=led.passive())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="dinner")
    ap.add_argument("--budgets", default="4x1")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="projection_validity_avbd")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    budgets = [tuple(int(v) for v in b.lower().split("x"))
               for b in args.budgets.split(",") if b.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]

    print(f"### R5.2 post-projection contact validity, AVBD host "
          f"({platform.machine()}) ###", flush=True)
    rows = []
    for scene in scenes:
        for (it, su) in budgets:
            for rx in relaxes:
                r = run_cell(scene, it, su, rx, args.nframes)
                rows.append(r)
                print(f"\n  {scene} {it}x{su} relax={rx}: clamp fired "
                      f"{r['n_clamped']}/{r['n_substeps']} substeps, "
                      f"min gamma={r['gamma_min']:.6g}")
                print(f"    (a) post-scale gap violation  median="
                      f"{r['gap_viol_post_median_m']:.3e} m  worst="
                      f"{r['gap_viol_post_max_m']:.3e} m   (pre-scale worst "
                      f"{r['gap_viol_pre_max_m']:.3e} m)")
                print(f"    (b) next-substep normal impulse median="
                      f"{r['impulse_next_median_Ns']:.4g} N.s  steady="
                      f"{r['impulse_steady_median_Ns']:.4g}   ratio="
                      f"{r['impulse_next_over_steady']:.3f}")
                print(f"    (c) lambda variance clamped median="
                      f"{r['lam_var_clamped_median']:.4g}  unclamped median="
                      f"{r['lam_var_free_median']:.4g}   ratio="
                      f"{r['lam_var_ratio']:.3g}")
                print(f"    (d) |dP| across projection worst="
                      f"{r['dP_across_projection_max']:.3e} kg.m/s "
                      f"(expected 0 by construction)")
                print(f"    ledger: holds={r['ledger_holds']} "
                      f"passive={r['ledger_passive']}")

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(OUT, f"{args.out}.csv", scenes=scenes, solvers=["avbd"],
                   note=("R5.2 (plan §6.7): E-S3's post-projection contact "
                         "validity probe ported to the augmented-Lagrangian "
                         "host, on the two cells where it exceeds R=1 (table "
                         "scene, 4x1, both relaxations). Same reduction as "
                         "E-S3 so the rows are directly comparable. Runtime "
                         "wrappers only; the ledger is pre-constructed because "
                         "this host builds it lazily on the first substep."))
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
