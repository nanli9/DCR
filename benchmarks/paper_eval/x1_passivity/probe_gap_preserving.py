#!/usr/bin/env python3
"""Gap-preserving projection A/B — does it kill the penetration and KEEP the bound?

POST-MIG follow-up probe. The shipped governor scales the whole modal state
radially, which shrinks the load-bearing sag U_y.q that resting bodies stand on
and opens up to 21.6 mm of penetration (paper 3.3, Table 2). The successor
(passivity.gap_preserving_projection) enforces the SAME bound but lands on a
different admissible point:

  rung 1  E_qs <= ceiling : hold U_c.q EXACTLY, scale only the contact-invisible
                            remainder and qdot   -> zero clamp-induced gap
  rung 2  E_qs >  ceiling : scale the load-bearing part alone by beta >= gamma
                            -> strictly less penetration than radial

Unlike the two R8 variants (probe_r8_feasibility.py), rung 2 is always feasible,
so the guarantee stays unconditional -- this probe is where that claim is
checked against real trajectories rather than asserted.

This is a FULL A/B RUN, not a per-substep counterfactual: each arm is its own
trajectory, so the caveat that sank the R8 counterfactual (a real run diverges)
does not apply to the headline numbers here. The arms do diverge, which is why
peak modal energy and the invariant are reported per arm.

Per arm we log, over the clamp-active substeps:
  - worst / median post-projection support-gap violation      [mm]
  - the ledger invariant (passive(), holds(), worst margin)   [J]
  - peak modal energy (accuracy proxy vs. the ungoverned run) [J]
  - rung histogram (gap-preserving arm only)

Out: out/{gap_preserving.csv, gap_preserving.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_gap_preserving.py
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


def _viol(sol):
    """max(0, -C) over support rows: C = corner_y - (y_rest + U_y.q). Mirrors
    _project_support and run_projection_validity._gaps."""
    q, X, Q = sol._q, sol._X, sol._Q
    worst = 0.0
    for sc in sol._support:
        R = _qR(np.asarray(Q[sc.bi], dtype=np.float64))
        corner_y = float(X[sc.bi][1]) + float((R @ sc.off)[1])
        worst = max(worst, -(corner_y - (sc.y_rest + float(sc.U_y @ q))))
    return max(0.0, worst)


def run_arm(scene, iters, subs, relax, gap_preserving, nframes, settle=8):
    H = SCENES[scene](device="cpu", iterations=iters, avbd_substeps=subs,
                      solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True         # the clamp is host-path only
    apply_passivity(sol, "xpbd", enable=True, eta=1.0)
    sol._psv_gap_preserving = bool(gap_preserving)
    led = sol._psv_ledger

    rec = {}
    steps = []
    e_peak = [0.0]

    orig_gamma = _psv_mod.passivity_gamma
    orig_gap = _psv_mod.gap_preserving_projection
    orig_commit = led.commit

    def gamma_wrap(e_new, e_old, budget, tol=1e-12):
        g = orig_gamma(e_new, e_old, budget, tol=tol)
        rec.clear()
        rec.update(gamma=float(g), pre_viol=_viol(sol), rung=0)
        return g

    def gap_wrap(q, qdot, Kq, Mq, U_c, e_old, budget, tol=1e-12, **kw):
        pre = _viol(sol)
        q2, qd2, g, info = orig_gap(q, qdot, Kq, Mq, U_c, e_old, budget,
                                    tol=tol, **kw)
        rec.clear()
        rec.update(gamma=float(g), pre_viol=pre, rung=int(info["rung"]),
                   n_rows=int(np.asarray(U_c).shape[0]),
                   n_preserved=int(info.get("n_preserved", 0)),
                   E_qs=float(info["E_qs"]), ceiling=float(info["ceiling"]))
        return q2, qd2, g, info

    def commit_wrap(realized_gain, budget, alpha, e_modal_now=None):
        orig_commit(realized_gain, budget, alpha, e_modal_now=e_modal_now)
        if e_modal_now is not None:
            e_peak[0] = max(e_peak[0], float(e_modal_now))
        if rec and rec.get("gamma", 1.0) < 1.0:
            steps.append(dict(post_viol=_viol(sol), **rec))
        rec.clear()

    _psv_mod.passivity_gamma = gamma_wrap
    _psv_mod.gap_preserving_projection = gap_wrap
    led.commit = commit_wrap
    try:
        for _ in range(settle + nframes):
            H.world.step()
    finally:
        _psv_mod.passivity_gamma = orig_gamma
        _psv_mod.gap_preserving_projection = orig_gap
        led.commit = orig_commit

    post = np.array([s["post_viol"] for s in steps]) if steps else np.zeros(1)
    pre = np.array([s["pre_viol"] for s in steps]) if steps else np.zeros(1)
    rungs = [s["rung"] for s in steps]
    return dict(
        n_clamped=len(steps), n_steps=led.n_steps,
        viol_post_max=float(post.max()), viol_post_med=float(np.median(post)),
        viol_pre_max=float(pre.max()),
        clamp_induced_max=float(np.maximum(post - pre, 0.0).max()),
        e_modal_peak=e_peak[0],
        passive=bool(led.passive()), holds=bool(led.holds()),
        max_net_excess=float(led.max_net_excess),
        max_deposit=float(led.max_deposit),
        rung1=sum(1 for r in rungs if r == 1),
        rung1b=sum(1 for r in rungs if r == 11),
        rung2=sum(1 for r in rungs if r == 2),
        rung_fallback=sum(1 for r in rungs if r == -1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="shelf:4x1:0.7,shelf:8x2:0.7,"
                                       "ledge:4x1:0.7,ledge:8x2:0.7")
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="gap_preserving")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### gap-preserving projection A/B ({platform.machine()}) ###")
    print("radial = shipped governor (paper Table 2); gap = follow-up\n",
          flush=True)

    rows = []
    for spec in args.cells.split(","):
        scene, budget, relax = spec.split(":")
        K, S = (int(v) for v in budget.lower().split("x"))
        relax = float(relax)
        tag = f"{scene} {K}x{S} r{relax}"
        a = run_arm(scene, K, S, relax, False, args.nframes)
        b = run_arm(scene, K, S, relax, True, args.nframes)
        nb = max(b["n_clamped"], 1)
        print(f"  {tag}")
        print(f"    radial : clamped {a['n_clamped']}/{a['n_steps']}  "
              f"viol med/max {1e3*a['viol_post_med']:7.3f} / "
              f"{1e3*a['viol_post_max']:7.3f} mm   "
              f"peak E_mod {a['e_modal_peak']:.4g} J   "
              f"passive={a['passive']} holds={a['holds']}")
        print(f"    gap    : clamped {b['n_clamped']}/{b['n_steps']}  "
              f"viol med/max {1e3*b['viol_post_med']:7.3f} / "
              f"{1e3*b['viol_post_max']:7.3f} mm   "
              f"peak E_mod {b['e_modal_peak']:.4g} J   "
              f"passive={b['passive']} holds={b['holds']}")
        print(f"    rungs  : rung1 {b['rung1']}/{nb} "
              f"({100.0*b['rung1']/nb:.1f}% zero-gap)  rung1b {b['rung1b']}  "
              f"rung2 {b['rung2']}  fallback {b['rung_fallback']}   "
              f"worst-case {1e3*a['viol_post_max']:.2f} -> "
              f"{1e3*b['viol_post_max']:.2f} mm "
              f"({a['viol_post_max']/max(b['viol_post_max'],1e-12):.2f}x better)")
        print(flush=True)
        rows.append(dict(scene=scene, iters=K, substeps=S, relax=relax,
                         **{f"radial_{k}": v for k, v in a.items()},
                         **{f"gap_{k}": v for k, v in b.items()}))

    p = os.path.join(OUT, f"{args.out}.csv")
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        [w.writerow(r) for r in rows]
    write_manifest(
        OUT, f"{args.out}.csv", scenes=sorted({r["scene"] for r in rows}),
        solvers=["xpbd"],
        note=("POST-MIG follow-up. Full A/B run (not a counterfactual) of the "
              "shipped radial gamma-projection against the gap-preserving "
              "projection, which enforces the same cumulative bound but "
              "preserves the active contact rows' observed surface where the "
              "budget affords it. Reports post-projection penetration, the "
              "ledger invariant per arm, and the rung histogram."))
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
