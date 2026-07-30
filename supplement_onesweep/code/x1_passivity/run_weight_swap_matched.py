#!/usr/bin/env python3
"""E-WS-M — the RECONSTRUCTION-MATCHED third arm of the weight swap.

WHY THIS EXISTS (reviewer objection #2 on build fc552a59). The paper reuses the
24-cell weight swap of `run_weight_swap.py` and writes that "the implicit weight
removing injection everywhere matches Theorem 4.3". That attribution is WRONG,
and the reviewer caught it:

  * `run_weight_swap.py` installs  w = 1/(M_q + h D_q + h^2 K_q), which is the
    BACKWARD-EULER (kappa = 1) weight;
  * but it also sets `sol._modal_symplectic = True`, so the host reconstructs
    qdot+ = 2 dq/h, i.e. kappa = 2;
  * and Theorem 4.3 says the kappa = 2 matched weight is 1/(4 M_q + h^2 K_q).
    On a kappa = 2 host the backward-Euler weight is NOT matched; the theorem
    predicts it VIOLATES the one-sweep bound at low stiffness.

So the existing 0/24 result corroborates that iterating/stiffening the row weight
removes injection, which is real but is NOT one-sweep matched-weight evidence.
Rather than re-label the claim down, this script runs the arm the theorem
actually predicts, so the paper can cite matched-weight evidence on a production
host at the host's own default reconstruction.

THREE ARMS, everything else held fixed (governor OFF, symplectic modal stepper,
per-substep contact regeneration, warm start, same scenes/budgets/relaxations):
    explicit  w = 1/M_q                        (shipped, the injecting baseline)
    be        w = 1/(M_q + h D_q + h^2 K_q)     (the old arm, kappa = 1 shaped)
    matched   w = 1/(4 M_q + h^2 K_q)           (Thm 4.3 at kappa = 2, THIS ARM)

The matched charge is the STORED-ENERGY mass m(kappa^2 + b), which T11 shows is
damping-independent, hence 4 M_q + h^2 K_q carries no D_q term. That is not an
oversight: including h D_q would charge the per-impulse mass instead, a different
and (at kappa = 2) unmatched quantity.

Reuses the tracked harness by import; the tracked file is never modified.
Out: out/weight_swap_matched.csv
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_weight_swap_matched.py
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

from dcr.rigid.energy import rigid_kinetic_energy                 # noqa: E402
from benchmarks.paper_eval.paper_config import (                  # noqa: E402
    apply_relax, apply_passivity, write_manifest)
# Import the tracked harness rather than copying it, so the scene builders,
# budgets and settle/frame counts are provably the same as the published arm.
from benchmarks.paper_eval.x1_passivity.run_weight_swap import (   # noqa: E402
    SCENES, BUDGETS, RELAXES, SETTLE, NFRAMES, OUT)

KAPPA_SYMPLECTIC = 2.0    # the shipped default reconstruction qdot+ = 2 dq/h


def _weights(sol):
    """Return (explicit, be, matched) diagonal contact-row modal weights."""
    mq = np.asarray(sol._mq, dtype=np.float64)
    kq = np.asarray(sol._kq, dtype=np.float64)
    dq = np.asarray(sol._dq, dtype=np.float64)
    h = float(sol.dt) / int(sol.substeps)
    live = mq > 0.0

    def inv(denom):
        return np.where(live, 1.0 / np.maximum(denom, 1e-300), 0.0)

    w_explicit = inv(mq)
    w_be = inv(mq + h * dq + (h * h) * kq)
    # Thm 4.3 / T10 at kappa = 2: G = kappa^2 M_q + h^2 K_q, no damping term.
    w_matched = inv(KAPPA_SYMPLECTIC ** 2 * mq + (h * h) * kq)
    b = np.where(live, (h * h) * kq / np.maximum(mq, 1e-300), 0.0)
    return w_explicit, w_be, w_matched, dict(
        h_sub=h, b_min=float(b[live].min()) if np.any(live) else 0.0,
        b_max=float(b[live].max()) if np.any(live) else 0.0,
        n_modes=int(live.sum()))


def one(build_fn, it, su, relax, arm, nframes=NFRAMES, settle=SETTLE):
    """One XPBD cell with arm in {'explicit','be','matched'}. Governor OFF."""
    t0 = time.perf_counter()
    H = build_fn(device="cpu", iterations=it, avbd_substeps=su, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True                      # kappa = 2, host default
    apply_passivity(sol, "xpbd", enable=False, eta=1.0)
    sol._psv_monitor_only = False

    w_expl, w_be, w_matched, diag = _weights(sol)
    if arm == "explicit":
        sol._wq_support = None                        # shipped path, bit-identical
    elif arm == "be":
        sol._wq_support = w_be
    elif arm == "matched":
        sol._wq_support = w_matched
    else:
        raise ValueError(arm)

    w = H.world
    ib = w._descs[H.impactor_idx].dcr_body
    for _ in range(settle):
        w.step()
        w._sync_avbd_to_dcr()
    e_imp = e_mod = 0.0
    finite = True
    for _ in range(nframes):
        w.step()
        w._sync_avbd_to_dcr()
        e_imp = max(e_imp, rigid_kinetic_energy([ib]))
        e = sol.last_modal_KE + sol.last_modal_PE
        if not np.isfinite(e):
            finite = False
            break
        e_mod = max(e_mod, e)
    return dict(ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
                e_modal_peak=e_mod if finite else float("inf"),
                e_imp_peak=e_imp, finite=finite,
                wall_s=time.perf_counter() - t0, **diag)


def _load_prev(path):
    """ratio_explicit / ratio_implicit from the published 24-cell CSV, so the
    explicit arm here can be checked against the published baseline."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for row in csv.DictReader(fh):
            key = (row["scene"], float(row["relax"]),
                   int(row["iters"]), int(row["substeps"]))
            out[key] = (float(row["ratio_explicit"]), float(row["ratio_implicit"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--budgets", default="4x1,8x2,16x4,32x8")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--arms", default="explicit,be,matched")
    ap.add_argument("--out", default="weight_swap_matched")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]
    budgets = [tuple(int(v) for v in b.lower().split("x"))
               for b in args.budgets.split(",") if b.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    prev = _load_prev(os.path.join(OUT, "weight_swap_full.csv"))

    rows = []
    worst_base = 0.0
    print(f"### E-WS-M matched third arm ({platform.machine()}, "
          f"{platform.system()}) ###")
    print("### explicit = shipped 1/M_q | be = 1/(M+hD+h^2K) | "
          "matched = 1/(4M+h^2K) (Thm 4.3, kappa=2) ###\n", flush=True)
    hdr = f"{'scene':7s} {'rel':4s} {'bud':6s} |"
    for a in arms:
        hdr += f" {('R_' + a):>12s}"
    hdr += f" | {'b_max':>9s} {'Dbase':>8s}"
    print(hdr, flush=True)

    for scene in scenes:
        fn = SCENES[scene]
        for relax in relaxes:
            for (it, su) in budgets:
                res = {}
                for a in arms:
                    res[a] = one(fn, it, su, relax, a, args.nframes)
                key = (scene, relax, it, su)
                pv = prev.get(key)
                reldiff = float("nan")
                if pv is not None and "explicit" in res and np.isfinite(res["explicit"]["ratio"]):
                    reldiff = abs(res["explicit"]["ratio"] - pv[0]) / max(abs(pv[0]), 1e-9)
                    worst_base = max(worst_base, reldiff)
                row = dict(scene=scene, relax=relax, iters=it, substeps=su)
                for a in arms:
                    row[f"ratio_{a}"] = res[a]["ratio"]
                    row[f"e_modal_{a}"] = res[a]["e_modal_peak"]
                    row[f"finite_{a}"] = res[a]["finite"]
                any_arm = res[arms[0]]
                row.update(b_min=any_arm["b_min"], b_max=any_arm["b_max"],
                           n_modes=any_arm["n_modes"], h_sub=any_arm["h_sub"],
                           ratio_prev_explicit=pv[0] if pv else None,
                           ratio_prev_be=pv[1] if pv else None,
                           baseline_reldiff=reldiff,
                           wall_s=sum(res[a]["wall_s"] for a in arms))
                rows.append(row)
                line = f"{scene:7s} {relax:<4} {it:2d}x{su:<3} |"
                for a in arms:
                    line += f" {res[a]['ratio']:12.4g}"
                rd = f"{reldiff:8.1e}" if np.isfinite(reldiff) else f"{'n/a':>8s}"
                line += f" | {any_arm['b_max']:9.3g} {rd}"
                print(line, flush=True)

    keys = list(rows[0].keys())
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
        note=("E-WS-M: XPBD host, governor OFF, symplectic modal stepper "
              "(kappa=2). Three contact-row modal weights: explicit 1/M_q, "
              "backward-Euler 1/(M+hD+h^2K), and the RECONSTRUCTION-MATCHED "
              "1/(4M+h^2K) of Thm 4.3 at kappa=2. Fixes the mis-attribution "
              "of the published weight-swap arm to that theorem."))

    print(f"\n--- explicit arm vs published weight_swap_full.csv: worst "
          f"|dR|/R = {worst_base:.2e} "
          f"({'PASS' if worst_base < 1e-6 else 'CHECK'}) ---")
    for a in arms:
        n_inj = sum(1 for r in rows
                    if np.isfinite(r[f"ratio_{a}"]) and r[f"ratio_{a}"] > 1.0)
        n_bad = sum(1 for r in rows if not r[f"finite_{a}"])
        print(f"--- {a:8s}: injecting (R>1) {n_inj}/{len(rows)}, "
              f"non-finite {n_bad}/{len(rows)} ---")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
