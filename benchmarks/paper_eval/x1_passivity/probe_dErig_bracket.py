#!/usr/bin/env python3
"""R1 DIAGNOSTIC — is the per-substep dE_rig bracket CONTIGUOUS on each backend?

Not a paper experiment. This decides whether the R1 Eq.-(2) utilization U is
trustworthy on a given backend, before any U number is reported.

WHY THIS EXISTS
---------------
Each backend funds the reservoir with

    dE_rig^k = (E_rig_pre^k - E_rig_post^k) + grav_work^k

captured at two points inside the substep. That is only a valid accounting of
"what contact dissipated this substep" if the brackets TILE the timeline, i.e.

    E_rig_post^k  ==  E_rig_pre^{k+1}                          (contiguity)

If rigid velocities change between one substep's post-capture and the next
substep's pre-capture, that change is invisible to the ledger: it is neither
credited nor debited, and the reservoir is funded from a partial view. Symptom
seen on AVBD in the R1 matrix: gross rigid GAIN exceeded gross rigid LOSS in
every cell (return channel 102-118%), together with U > 1 in 23/24 cells while
R stayed at ~0.2 -- i.e. a huge apparent modal overdraw with a tiny denominator.

The XPBD path captures both endpoints inside `_substep_cpu`
(solver_xpbd.py:1072 and :1223), so it should tile exactly. AVBD captures
pre in `_modal_predict` (solver_6dof.py:2453) and post in `_modal_commit`
(:2617); whether those tile depends on where the rigid velocity integration
sits relative to the modal block.

WHAT IT REPORTS
---------------
Per backend, over N logged substeps:
  gap^k        = E_rig_pre^{k+1} - E_rig_post^k        [J]  (0 == contiguous)
  sum |gap|    relative to the gross supply sum max(dE_rig,0)
A backend whose |gap| sum is a significant fraction of its gross supply has an
UNTRUSTWORTHY U and must not have an Eq.-(2) number reported for it.

Measurement-only: wraps the same module-level `passivity_gamma` (forced to 1.0,
so the projection is dead) and reads solver state; changes nothing.

Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_dErig_bracket.py
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                    # noqa: E402
from dcr.avbd._solver.passivity import (                         # noqa: E402
    rigid_mechanical_energy, local_inertia_from_invIl, PassivityLedger)
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity)


def _rig_E(sol, solver):
    """Total rigid KE (translational + rotational), read from whichever arrays
    this backend calls authoritative, using the SAME expression the ledger uses.

    Per-backend quat handling matters: solver_6dof and solver_xpbd expose
    `_psv_quats_wxyz()`, while SolverImpulse inlines the same reorder at its
    call site (solver_impulse.py:988). Passing raw XYZW would silently
    mis-weight the angular KE of rotated anisotropic bodies.
    """
    if solver == "avbd":
        V = sol.v.numpy(); W = sol.omega.numpy()
        Q = sol._psv_quats_wxyz()
        mass, invIl = sol._mass, sol._inv_I_local
        Il = sol._psv_local_inertia()
    else:
        V, W = sol._V, sol._W
        Q = (sol._psv_quats_wxyz() if hasattr(sol, "_psv_quats_wxyz")
             else sol._Q[:, [3, 0, 1, 2]])
        mass, invIl = sol._mass, sol._invIl
        Il = local_inertia_from_invIl(invIl)
    return rigid_mechanical_energy(V, W, Q, mass, invIl, Il=Il)


def run(scene, solver, iters, subs, relax, nframes, settle=8, eta=1.0):
    H = SCENES[scene](device="cpu", iterations=iters, avbd_substeps=subs,
                      solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=True, eta=eta)
    sol._psv_monitor_only = False
    if getattr(sol, "_psv_ledger", None) is None:
        sol._psv_ledger = PassivityLedger(eta=float(eta))
    led = sol._psv_ledger

    ev = []                     # (E_pre, E_post, rigid_loss) per deposit
    orig_dep = led.deposit
    pre_box = {"E": np.nan}

    # XPBD/AVBD stash the pre-substep energy on the solver (`_E_rig_pre`).
    # SolverImpulse instead passes it as an ARGUMENT to _psv_commit
    # (solver_impulse.py:842), so there is nothing on `self` to read -- wrap
    # that call to capture it.
    orig_psv_commit = getattr(sol, "_psv_commit", None)
    if orig_psv_commit is not None:
        def psv_commit_wrap(h, x_prev, E_rig_pre, E_modal_pre):
            pre_box["E"] = float(E_rig_pre)
            return orig_psv_commit(h, x_prev, E_rig_pre, E_modal_pre)
        sol._psv_commit = psv_commit_wrap

    # deposit() is called exactly once per substep, immediately after the
    # backend computes E_rig_post -- so at call time the pre value for THIS
    # substep is available and the live arrays hold its post value.
    def dep_wrap(rigid_loss):
        pre = (pre_box["E"] if orig_psv_commit is not None
               else float(getattr(sol, "_E_rig_pre", np.nan)))
        ev.append((pre, _rig_E(sol, solver), float(rigid_loss)))
        return orig_dep(rigid_loss)

    led.deposit = dep_wrap
    orig_gamma = _psv_mod.passivity_gamma
    _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0
    try:
        w = H.world
        for _ in range(settle + nframes):
            w.step()
    finally:
        _psv_mod.passivity_gamma = orig_gamma
        led.deposit = orig_dep
        if orig_psv_commit is not None:
            sol._psv_commit = orig_psv_commit

    a = np.asarray(ev, dtype=np.float64)
    if a.shape[0] < 3:
        return None
    E_pre, E_post, loss = a[:, 0], a[:, 1], a[:, 2]
    gaps = E_pre[1:] - E_post[:-1]           # 0 => contiguous brackets
    gross_pos = float(np.maximum(loss, 0.0).sum())
    gross_neg = float(np.maximum(-loss, 0.0).sum())
    return dict(
        n=a.shape[0],
        gap_abs_sum=float(np.abs(gaps).sum()),
        gap_max=float(np.abs(gaps).max()),
        gap_mean=float(np.abs(gaps).mean()),
        gross_pos=gross_pos, gross_neg=gross_neg,
        gap_over_supply=(float(np.abs(gaps).sum()) / gross_pos
                         if gross_pos > 0 else float("inf")),
        E_first=float(E_pre[0]), E_last=float(E_post[-1]),
        loss_sum=float(loss.sum()),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,dinner")
    ap.add_argument("--solvers", default="xpbd,avbd,impulse")
    ap.add_argument("--budget", default="16x4")
    ap.add_argument("--relax", type=float, default=1.0)
    ap.add_argument("--nframes", type=int, default=40)
    args = ap.parse_args()
    it, su = (int(v) for v in args.budget.lower().split("x"))

    print("### dE_rig bracket contiguity probe ###")
    print("#  gap^k = E_rig_pre^{k+1} - E_rig_post^k;  0 => brackets tile the "
          "timeline")
    print("#  gap/supply >> 0 => the ledger sees only part of the rigid energy "
          "change => U is NOT trustworthy on that backend\n")
    print(f"{'solver':8s} {'scene':8s} {'n':>5s} {'sum|gap| [J]':>13s} "
          f"{'max|gap|':>11s} {'gross supply':>13s} {'gap/supply':>11s}  verdict")
    for solver in [s.strip() for s in args.solvers.split(",")]:
        for scene in [s.strip() for s in args.scenes.split(",")]:
            r = run(scene, solver, it, su, args.relax, args.nframes)
            if r is None:
                print(f"{solver:8s} {scene:8s}  (no deposits logged)")
                continue
            ratio = r["gap_over_supply"]
            verdict = ("CONTIGUOUS" if ratio < 1e-9 else
                       "small leak" if ratio < 1e-2 else
                       "NOT CONTIGUOUS -- U untrustworthy")
            print(f"{solver:8s} {scene:8s} {r['n']:5d} {r['gap_abs_sum']:13.5g} "
                  f"{r['gap_max']:11.4g} {r['gross_pos']:13.5g} "
                  f"{ratio:11.4g}  {verdict}")


if __name__ == "__main__":
    main()
