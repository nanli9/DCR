#!/usr/bin/env python3
"""R8 pre-gate investigation — is a floor-bearing projection actually
ENFORCEABLE, and would it actually help? (plan §6.10 go/no-go)

The present projection scales the WHOLE modal state, so E_mod(gamma) =
gamma^2 * E_mod and gamma -> 0 always drives the energy to zero. Eq. (2) is
therefore enforceable BY CONSTRUCTION: a feasible gamma always exists.

Both proposed successors give up that property, in the same way. Each splits
the modal state into a part that is preserved and a part that is scaled:

  R8a  deviation-referenced   (q, qd) <- (q_eq + g(q - q_eq), g qd)
  R8b  band-selective         scale only the stiff modes, keep the bending ones

Either way the preserved part contributes a gamma-INDEPENDENT constant c to
the post-projection energy:

  E(g) = a g^2 + b g + c ,    c = energy locked in the preserved part

so the reachable minimum is c, not 0. If the ceiling (E_mod^- + B) ever falls
below c, NO gamma in [0,1] satisfies Eq. (2) and the guarantee degrades from
"by construction" to "empirically, in the cells we tried".

This script measures how often that happens, at the real decision points of a
real governed run, plus what the successor would have done to the contact
surface when it IS feasible.

R8b is the primary measurement because it needs no estimation: the bending /
stiff split is exact (the shelf spectrum is bimodal, 10 modes at
20.3 Hz..2.03 kHz then 6 at 20.7..24.7 kHz), so c = E_low is read directly
off the state. R8a additionally needs q_eq, taken as the tail-median modal
state of a converged unclamped run of the same scene; that is an estimate and
is reported separately.

SCOPE, stated plainly: this is a per-substep COUNTERFACTUAL evaluated at the
states the current governor actually visits. A true R8 run would follow a
different trajectory, so the feasible/infeasible counts are evidence about
the states this problem produces, not a simulation of R8. The feasibility
question itself (is ceiling >= c?) is well posed pointwise, which is what
makes the counterfactual meaningful.

Measurement-only: every wrapper returns its input unchanged; the real gamma
stays live because we want the genuine governed trajectory.

Out: out/{r8_feasibility.csv, r8_feasibility_substeps.csv, *.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_r8_feasibility.py
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
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _bands(sol):
    """(low, high) boolean masks over modes, split at the scene's own spectral
    gap.

    FIXED 2026-07-19. This was a hard-coded 1e4 Hz, documented as "inside the
    shelf spectrum's gap". That is true for the shelf ONLY. Every scene has a
    decade-wide gap, but its location moves by two orders of magnitude:
    469 Hz (table), 2.03 kHz (shelf), 17.0 kHz (ledge). The fixed cut therefore
    put three genuine bending modes into the scaled band on the ledge -- which
    is where the over-stated "37.8% infeasible" in the first R8 write-up came
    from -- and sat above the table's entire spectrum, making the split a no-op
    there. We now locate the largest MULTIPLICATIVE gap per scene and cut at its
    geometric middle. See the R8 sections of docs/mig2026_results_ledger.md;
    probe_band_split_sweep.py supersedes this by sweeping the split instead of
    picking one."""
    kq = np.asarray(sol._kq, dtype=np.float64)
    mq = getattr(sol, "_mq", None)
    mqv = (np.ones_like(kq) if mq is None
           else np.asarray(mq, dtype=np.float64))
    f = np.sqrt(np.maximum(kq / np.where(mqv > 0, mqv, 1.0), 0.0)) / (2 * np.pi)
    fs = np.sort(f)
    if fs.size < 2:
        return np.ones_like(f, bool), np.zeros_like(f, bool), f
    i = int(np.argmax(fs[1:] / np.maximum(fs[:-1], 1e-30)))
    f_split = float(np.sqrt(fs[i] * fs[i + 1]))          # geometric middle
    return f <= f_split, f > f_split, f


def _defl(sol, q):
    """max_i |U_y[i].q| [m] — the surface excursion the contact row sees."""
    if not sol._support:
        return 0.0
    return float(max(abs(float(sc.U_y @ q)) for sc in sol._support))


def converged_q_eq(scene, relax, K=500, nframes=100, settle=8, tail=0.5):
    """q_eq estimate: tail-median modal state of a converged UNCLAMPED run.

    This is the scene's own load-bearing equilibrium, not a truncation
    artifact. It is an ESTIMATE -- a real R8a would recompute q_eq per substep
    from the live contact forces -- so R8a results are reported separately
    from the exact R8b ones."""
    H = SCENES[scene](device="cpu", iterations=K, avbd_substeps=1, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=False)
    orig = _psv_mod.passivity_gamma
    _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0
    qs = []
    try:
        w = H.world
        for _ in range(settle):
            w.step()
        for _ in range(nframes):
            w.step()
            if sol._q is not None:
                qs.append(np.asarray(sol._q).copy())
    finally:
        _psv_mod.passivity_gamma = orig
    Q = np.asarray(qs)
    k = max(1, int(len(Q) * (1.0 - tail)))
    return np.median(Q[k:], axis=0)


def run_cell(scene, K, S, relax, q_eq, nframes=100, settle=8):
    H = SCENES[scene](device="cpu", iterations=K, avbd_substeps=S, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=True, eta=1.0)   # REAL gamma stays live
    lo, hi, _f = _bands(sol)
    kq = np.asarray(sol._kq, dtype=np.float64)
    mq = getattr(sol, "_mq", None)
    mqv = np.ones_like(kq) if mq is None else np.asarray(mq, dtype=np.float64)
    qeq = np.zeros_like(kq) if q_eq is None else np.asarray(q_eq)[:kq.size]

    rec = []
    orig = _psv_mod.passivity_gamma

    def wrap(e_new, e_old, budget, tol=1e-12):
        g = orig(e_new, e_old, budget, tol=tol)          # unchanged
        q = np.asarray(sol._q, dtype=np.float64)
        qd = np.asarray(sol._qdot, dtype=np.float64)
        pe_i = 0.5 * kq * q ** 2
        ke_i = 0.5 * mqv * qd ** 2
        e_i = pe_i + ke_i
        # self-check: our reconstruction must equal the solver's own number
        recon = float(e_i.sum())
        ceiling = e_old + budget
        # ---- R8b band-selective: preserve low modes, scale high ------------
        c_b = float(e_i[lo].sum())
        a_b = float(e_i[hi].sum())
        # ---- R8a deviation-referenced: preserve q_eq, scale (q-q_eq) & qd --
        d = q - qeq
        c_a = float(0.5 * (kq * qeq * qeq).sum())
        b_a = float((kq * qeq * d).sum())
        a_a = float(0.5 * (kq * d * d).sum() + 0.5 * (mqv * qd * qd).sum())
        rec.append(dict(
            gamma=float(g), e_new=float(e_new), e_old=float(e_old),
            budget=float(budget), ceiling=float(ceiling), recon=recon,
            E_low=c_b, E_high=a_b,
            a_a=a_a, b_a=b_a, c_a=c_a,
            defl_pre=_defl(sol, q),
            defl_now=_defl(sol, q * g),
            defl_band=_defl(sol, np.where(lo, q, q * _g_band(ceiling, c_b, a_b))),
            defl_dev=_defl(sol, qeq + _g_dev(ceiling, a_a, b_a, c_a) * d),
        ))
        return g

    _psv_mod.passivity_gamma = wrap
    try:
        w = H.world
        for _ in range(settle + nframes):
            w.step()
    finally:
        _psv_mod.passivity_gamma = orig
    return rec


def _g_band(ceiling, c, a):
    """gamma for E(g) = c + a g^2 <= ceiling. NaN if infeasible."""
    if ceiling < c:
        return float("nan")
    if a <= 0:
        return 1.0
    return float(min(1.0, np.sqrt(max(0.0, (ceiling - c) / a))))


def _g_dev(ceiling, a, b, c):
    """largest g in [0,1] with a g^2 + b g + c <= ceiling. NaN if infeasible."""
    if c > ceiling:
        return float("nan")                 # floor already exceeds the ceiling
    if a <= 0:
        return 1.0 if b <= 0 else float(min(1.0, max(0.0, (ceiling - c) / b)))
    disc = b * b - 4 * a * (c - ceiling)
    if disc < 0:
        return float("nan")
    return float(min(1.0, max(0.0, (-b + np.sqrt(disc)) / (2 * a))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="shelf:4x1:0.7,shelf:4x1:1.0,"
                                       "shelf:8x2:0.7,ledge:4x1:0.7")
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="r8_feasibility")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### R8 feasibility probe ({platform.machine()}) ###")
    print("split at each scene's own spectral gap; 'infeasible' = no gamma in "
          "[0,1] satisfies Eq. (2)\n", flush=True)

    rows, per_sub = [], []
    qeq_cache = {}
    for spec in args.cells.split(","):
        scene, budget, relax = spec.split(":")
        K, S = (int(v) for v in budget.lower().split("x"))
        relax = float(relax)
        key = (scene, relax)
        if key not in qeq_cache:
            qeq_cache[key] = converged_q_eq(scene, relax)
        rec = run_cell(scene, K, S, relax, qeq_cache[key], args.nframes)

        # self-check: reconstruction must match the solver's own e_new
        err = max(abs(r["recon"] - r["e_new"]) / max(r["e_new"], 1e-30)
                  for r in rec) if rec else 0.0
        clamped = [r for r in rec if r["gamma"] < 1.0]
        nb = sum(1 for r in clamped if r["ceiling"] < r["E_low"])
        na = sum(1 for r in clamped if r["ceiling"] < r["c_a"])
        n = max(len(clamped), 1)
        # how deep is the shortfall when infeasible?
        deep_b = [r["E_low"] / max(r["ceiling"], 1e-30)
                  for r in clamped if r["ceiling"] < r["E_low"]]
        frac_low = [r["E_low"] / max(r["e_new"], 1e-30) for r in clamped]
        tag = f"{scene} {K}x{S} relax {relax}"
        print(f"  {tag}: {len(clamped)}/{len(rec)} substeps clamped "
              f"(recon err {err:.2e})")
        print(f"      R8b band-selective INFEASIBLE in {nb}/{len(clamped)} "
              f"({100.0 * nb / n:5.1f}%)   E_low/ceiling when infeasible: "
              f"median {np.median(deep_b) if deep_b else float('nan'):.3g}")
        print(f"      R8a deviation-ref  INFEASIBLE in {na}/{len(clamped)} "
              f"({100.0 * na / n:5.1f}%)")
        print(f"      E_low as a share of total modal energy: median "
              f"{100.0 * np.median(frac_low):.3f}%")
        feas = [r for r in clamped if not np.isnan(r["defl_band"])]
        if feas:
            print(f"      surface excursion on clamp substeps [mm]: "
                  f"pre {1e3 * np.median([r['defl_pre'] for r in feas]):.3f}"
                  f" -> now {1e3 * np.median([r['defl_now'] for r in feas]):.3f}"
                  f" | band {1e3 * np.nanmedian([r['defl_band'] for r in feas]):.3f}"
                  f" | dev {1e3 * np.nanmedian([r['defl_dev'] for r in feas]):.3f}")
        print(flush=True)
        rows.append(dict(
            scene=scene, iters=K, substeps=S, relax=relax,
            n_substeps=len(rec), n_clamped=len(clamped),
            recon_rel_err=err,
            r8b_infeasible=nb, r8b_infeasible_frac=nb / n,
            r8a_infeasible=na, r8a_infeasible_frac=na / n,
            E_low_frac_median=float(np.median(frac_low)) if frac_low else 0.0,
            E_low_over_ceiling_median=(float(np.median(deep_b)) if deep_b
                                       else float("nan")),
            defl_pre_med=float(np.median([r["defl_pre"] for r in clamped])) if clamped else 0.0,
            defl_now_med=float(np.median([r["defl_now"] for r in clamped])) if clamped else 0.0,
            defl_band_med=float(np.nanmedian([r["defl_band"] for r in clamped])) if clamped else 0.0,
            defl_dev_med=float(np.nanmedian([r["defl_dev"] for r in clamped])) if clamped else 0.0))
        for i, r in enumerate(clamped):
            per_sub.append(dict(scene=scene, iters=K, substeps=S, relax=relax,
                                k=i, **r))

    p1 = os.path.join(OUT, f"{args.out}.csv")
    with open(p1, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        [w.writerow(r) for r in rows]
    p2 = os.path.join(OUT, f"{args.out}_substeps.csv")
    with open(p2, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per_sub[0].keys()))
        w.writeheader()
        [w.writerow(r) for r in per_sub]
    write_manifest(
        OUT, f"{args.out}.csv", scenes=sorted({r["scene"] for r in rows}),
        solvers=["xpbd"],
        note=("R8 pre-gate (plan §6.10): per-substep counterfactual asking "
              "whether a floor-bearing successor to the whole-state gamma "
              "projection is ENFORCEABLE. Both proposals (deviation-referenced, "
              "band-selective) leave a gamma-independent constant c in the "
              "post-projection energy, so a feasible gamma exists only when "
              "ceiling >= c. Evaluated at the decision points of a real "
              "governed run; measurement-only (every wrapper returns its input "
              "unchanged and the real gamma stays live)."))
    print(f"wrote {p1}\n      {p2}")


if __name__ == "__main__":
    main()
