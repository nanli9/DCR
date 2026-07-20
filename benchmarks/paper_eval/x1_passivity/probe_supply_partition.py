#!/usr/bin/env python3
"""E-C9c — how much of the supply is an artifact of the substep PARTITION?
(plan §8.5, P8.c)

Panel B's numerics reviewer objected that the reservoir's funding

    sum_k max(dE_rig^k, 0)

is a gross sum over SUBSTEP boundaries, so a finer partition rectifies more of
the rigid subsystem's own fluctuation into "supply". The paper's existing
sentence -- substep endpoints tile the timeline exactly, so no rigid energy
change escapes -- answers COMPLETENESS, which is a different property. The
objection is correct and this measures it.

--------------------------------------------------------------------------
WHY THIS IS NOT THE h-SWEEP
--------------------------------------------------------------------------
E-C9's `h` axis also changes the partition, but it changes the TRAJECTORY too:
a different timestep is a different discrete solve, so any change in supply
confounds "the accounting saw more fluctuation" with "the physics differed".

This probe holds the trajectory FIXED. It records the per-substep sequence
dE_rig^k from a single run and then re-aggregates that one sequence at coarser
granularity, summing the signed per-substep changes within each group BEFORE
taking the positive part:

    supply(g) = sum over groups G of max( sum_{k in G} dE_rig^k , 0 )

g = 1 is the substep granularity the solver actually funds itself at; g = S is
frame granularity. Because the endpoints telescope, sum_{k in G} dE_rig^k is
exactly the rigid-energy change across the whole group, so supply(g) is what the
SAME run would have been credited had the ledger been evaluated that coarsely.

    coarsening ratio  =  supply(1) / supply(S)

is then a pure partition effect: > 1 means substep-granular accounting credits
more than frame-granular accounting on the identical trajectory, and the excess
is rectified fluctuation, not dissipation.

Measurement-only: wraps `PassivityLedger.deposit` to record its argument and
passes the value through untouched, with `passivity_gamma` forced to 1.0 as in
run_eq2_utilization (every state write in the enforcement path is guarded by
`if gamma < 1.0`, so the trajectory is bit-identical to an ungoverned run).

Out: out/{supply_partition.csv, supply_partition.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_supply_partition.py
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
from dcr.rigid.energy import rigid_kinetic_energy                # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, SETTLE, NFRAMES)
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# (scene, relax, K, S) -- the two base cells of E-C9 plus the two deployed
# budgets, whose larger S makes the partition question sharpest.
CELLS = [
    ("shelf", 0.7, 4, 1), ("ledge", 1.0, 4, 1),
    ("shelf", 0.7, 1, 8), ("shelf", 0.7, 2, 4),
    ("ledge", 0.7, 1, 8), ("ledge", 0.7, 2, 4),
]


def run_cell(scene, relax, iters, subs, solver="xpbd", nframes=NFRAMES,
             settle=SETTLE, eta=1.0):
    """One ungoverned run; returns the per-substep dE_rig sequence."""
    H = SCENES[scene](device="cpu", iterations=iters, avbd_substeps=subs,
                      solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=True, eta=eta)
    sol._psv_monitor_only = False
    if getattr(sol, "_psv_ledger", None) is None:
        from dcr.avbd._solver.passivity import PassivityLedger
        sol._psv_ledger = PassivityLedger(eta=float(eta))
    led = sol._psv_ledger

    series: list[float] = []
    orig_deposit = led.deposit

    def deposit_wrap(rigid_loss: float):
        series.append(float(rigid_loss))      # signed, per substep
        return orig_deposit(rigid_loss)       # value passed through unchanged

    led.deposit = deposit_wrap
    orig_gamma = _psv_mod.passivity_gamma
    _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0
    try:
        w = H.world
        for _ in range(settle):
            w.step()
            w._sync_avbd_to_dcr()
        for _ in range(nframes):
            w.step()
            w._sync_avbd_to_dcr()
    finally:
        _psv_mod.passivity_gamma = orig_gamma
        led.deposit = orig_deposit
    return np.asarray(series, dtype=np.float64)


def supply_at(series: np.ndarray, group: int) -> float:
    """Gross positive-part supply when the ledger is evaluated every `group`
    substeps. Signed changes telescope within a group, so this is what the SAME
    trajectory would have been credited at that granularity."""
    if group <= 1:
        return float(np.maximum(series, 0.0).sum())
    n = (len(series) // group) * group
    if n == 0:
        return float("nan")
    grouped = series[:n].reshape(-1, group).sum(axis=1)
    tail = series[n:].sum() if len(series) > n else 0.0
    return float(np.maximum(grouped, 0.0).sum() + max(tail, 0.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--out", default="supply_partition")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### E-C9c supply partition-dependence ({platform.machine()}) ###",
          flush=True)
    print("#   same trajectory, ledger re-aggregated at coarser granularity",
          flush=True)
    rows = []
    for (scene, relax, K, S) in CELLS:
        s = run_cell(scene, relax, K, S, nframes=args.nframes)
        if s.size == 0:
            print(f"  {scene} {K}x{S}: no deposits logged"); continue
        sub = supply_at(s, 1)
        frame = supply_at(s, S)
        net = float(s.sum())
        row = dict(scene=scene, relax=relax, iters=K, substeps=S,
                   n_substeps=int(s.size),
                   supply_substep_J=sub, supply_frame_J=frame,
                   net_change_J=net,
                   coarsening_ratio=(sub / frame) if frame > 0 else float("nan"),
                   # how much of the substep-granular supply is fluctuation the
                   # coarser view cancels out
                   rectified_frac=((sub - frame) / sub) if sub > 0 else float("nan"))
        rows.append(row)
        print(f"  {scene:6s} relax={relax} {K}x{S}: "
              f"substep {sub:10.4g} J  frame {frame:10.4g} J  "
              f"ratio {row['coarsening_ratio']:6.3f}  "
              f"rectified {100 * row['rectified_frac']:5.1f}%  "
              f"(net {net:+.4g} J over {s.size} substeps)", flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=sorted({c[0] for c in CELLS}),
        solvers=["xpbd"],
        note=("E-C9c (plan §8.5 P8.c): partition-dependence of the reservoir "
              "supply. The per-substep signed dE_rig sequence of ONE ungoverned "
              "run is re-aggregated at coarser granularity, so the trajectory is "
              "held fixed and the change is a pure accounting-partition effect "
              "(unlike the E-C9 h axis, which also changes the solve). "
              "coarsening_ratio = supply(substep) / supply(frame); "
              "rectified_frac = the share of substep-granular supply that "
              "coarser accounting cancels as fluctuation. Measurement-only: "
              "deposit() is wrapped and its value passed through, "
              "passivity_gamma == 1.0."))
    if rows:
        rs = [r["coarsening_ratio"] for r in rows if np.isfinite(r["coarsening_ratio"])]
        fr = [r["rectified_frac"] for r in rows if np.isfinite(r["rectified_frac"])]
        print(f"\n  coarsening ratio {min(rs):.3f}--{max(rs):.3f}; "
              f"rectified fraction {100 * min(fr):.1f}--{100 * max(fr):.1f}%")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
