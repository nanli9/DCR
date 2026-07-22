#!/usr/bin/env python3
"""E1b — neighborhood-robustness audit of the headline XPBD cells (plan §9 E1b).

The benchmark has NO RNG (seed=0 is reserved, the paper config never draws), so
this is NOT a seed sweep and makes NO p-value or probability claim. It is a
LOCAL NEIGHBORHOOD-ROBUSTNESS audit: does each frozen headline result persist
under a small, pre-registered, deterministic ensemble of initial-condition
perturbations, and how wide is the spread?

Measurement-only, same contract as R1 (`run_eq2_utilization.py`): the reservoir
ledger runs live while `passivity_gamma == 1.0` (dead actuator), so the
trajectory is the ungoverned one and the accounting is exact.

FROZEN FIRST, THEN PERTURB (plan order). Every headline cell's UNPERTURBED
ratio/margin is asserted against the frozen ledger (eq2_utilization.csv) before
the ensemble runs; a mismatch aborts (the perturbation kwargs must be inert at
their defaults, which the shelf/ledge builders guarantee -- impactor_dx/dz/tilt
default 0.0).

TWO COHORTS, KEPT SEPARATE (plan): physical initial-condition perturbations vs
contact-row-order permutations. They are never pooled.

Physical ensemble (12, deterministic, no factorial):
  drop height  x{0.98,0.99,1.01,1.02}   (impact speed/phase, ~+/-1-2%)
  normal speed +/-0.03 m/s               (~+/-1% of the ~3 m/s impact speed)
  contact x    +/-1.5 mm                 (impactor_dx / dinner pot_drop_xz)
  contact z    +/-1.5 mm                 (impactor_dz / dinner pot_drop_xz)
  tilt         +/-0.01 rad about x       (shelf/ledge only; dinner has no param)
Row-order ensemble (4): deterministic permutations of the support-row list
(sol._support), which the solver sweeps in order -- a genuine solver-ordering
perturbation, verified to change the result.

Reported per cell, per cohort: positive-ledger-margin fraction (sign
robustness), median / IQR / min / max of the strict margin, and the log10 spread
of nonzero |margin| -- plus the same for the ratio R. Round headline magnitudes
to the precision THIS ensemble supports (plan §13).

Out: out/{e1b_neighborhood.csv, e1b_neighborhood.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_e1b_neighborhood.py
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                      # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy                  # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, SETTLE, NFRAMES)
from benchmarks.paper_eval.x1_passivity.run_eq2_utilization import (  # noqa: E402
    _neuter_gamma)
from benchmarks.paper_eval.paper_config import (                   # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Default drop heights per scene builder (for fractional drop-height variants).
SCENE_DROP = {"shelf": 0.5, "ledge": 0.8, "dinner": 0.5}
SCENE_DROPKW = {"shelf": "impactor_drop_height", "ledge": "impactor_drop_height",
                "dinner": "pot_drop_height"}
SCENE_V0KW = {"shelf": "impactor_v0", "ledge": "impactor_v0",
              "dinner": "pot_v0_y"}

# Headline cells (frozen anchors from eq2_utilization.csv). tag, scene, relax,
# iters, substeps, and the anchor ratio the unperturbed run must reproduce.
CELLS = [
    dict(tag="worst_shelf",  scene="shelf", relax=1.0, it=4, su=1, ratio=10962.1),
    dict(tag="worst_ledge",  scene="ledge", relax=1.0, it=4, su=1, ratio=119534.0),
    dict(tag="guardrail",    scene="shelf", relax=0.7, it=4, su=1, ratio=6333.22),
    dict(tag="pair_4x8",     scene="shelf", relax=0.7, it=4, su=8, ratio=3.12914),
    dict(tag="pair_32x1",    scene="shelf", relax=0.7, it=32, su=1, ratio=0.300),
    dict(tag="dinner_xpbd",  scene="dinner", relax=1.0, it=4, su=1, ratio=0.372141),
]

# Physical perturbation ensemble: (name, kind, value). Deterministic, no RNG.
PHYS = [
    ("drop-2%", "drop", 0.98), ("drop-1%", "drop", 0.99),
    ("drop+1%", "drop", 1.01), ("drop+2%", "drop", 1.02),
    ("v0-0.03", "v0", -0.03),  ("v0+0.03", "v0", 0.03),
    ("dx+1.5mm", "dx", 0.0015), ("dx-1.5mm", "dx", -0.0015),
    ("dz+1.5mm", "dz", 0.0015), ("dz-1.5mm", "dz", -0.0015),
    ("tilt+0.01", "tilt", 0.01), ("tilt-0.01", "tilt", -0.01),
]
ROWORDER_SEEDS = [1, 2, 3, 4]


def _pert_kwargs(scene, kind, val):
    """Map an abstract perturbation to scene-specific builder kwargs."""
    if kind == "drop":
        return {SCENE_DROPKW[scene]: SCENE_DROP[scene] * float(val)}
    if kind == "v0":
        return {SCENE_V0KW[scene]: float(val)}
    if kind in ("dx", "dz"):
        if scene == "dinner":
            xz = (float(val), 0.0) if kind == "dx" else (0.0, float(val))
            return {"pot_drop_xz": xz}
        return {("impactor_dx" if kind == "dx" else "impactor_dz"): float(val)}
    if kind == "tilt":
        return {} if scene == "dinner" else {"impactor_tilt": float(val)}
    raise ValueError(kind)


def measure(scene, solver, relax, it, su, build_kw=None, roworder_seed=None,
            eta=1.0, nframes=NFRAMES, settle=SETTLE):
    """One ungoverned cell with the Eq.-(2) ledger live; returns ratio + margin."""
    fn = SCENES[scene]
    H = fn(device="cpu", iterations=it, avbd_substeps=su, solver=solver,
           **(build_kw or {}))
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=True, eta=eta)
    sol._psv_monitor_only = False
    if roworder_seed is not None and len(getattr(sol, "_support", [])) > 1:
        random.Random(roworder_seed).shuffle(sol._support)
    if getattr(sol, "_psv_ledger", None) is None:
        from dcr.avbd._solver.passivity import PassivityLedger
        sol._psv_ledger = PassivityLedger(eta=float(eta))
    led = sol._psv_ledger

    orig_gamma = _neuter_gamma()
    finite = True
    e_imp = e_mod = 0.0
    try:
        w = H.world
        ib = w._descs[H.impactor_idx].dcr_body
        for _ in range(settle):
            w.step(); w._sync_avbd_to_dcr()
        for _ in range(nframes):
            w.step(); w._sync_avbd_to_dcr()
            e_imp = max(e_imp, rigid_kinetic_energy([ib]))
            e = sol.last_modal_KE + sol.last_modal_PE
            if not np.isfinite(e):
                finite = False; break
            e_mod = max(e_mod, e)
    finally:
        _psv_mod.passivity_gamma = orig_gamma

    ratio = (e_mod / max(e_imp, 1e-9)) if finite else float("inf")
    margin = float(led.max_net_excess)
    return dict(ratio=ratio, margin_J=margin, finite=finite,
                e_modal_peak=e_mod, e_imp_peak=e_imp)


def _stats(vals):
    """Spread summary for a list of margins/ratios."""
    a = np.array([v for v in vals if np.isfinite(v)], float)
    if a.size == 0:
        return {}
    nz = np.abs(a[a != 0.0])
    return dict(
        n=int(a.size),
        pos_frac=float(np.mean(a > 0.0)),
        median=float(np.median(a)), q1=float(np.percentile(a, 25)),
        q3=float(np.percentile(a, 75)),
        vmin=float(a.min()), vmax=float(a.max()),
        log10_spread=(float(np.log10(nz.max()) - np.log10(nz.min()))
                      if nz.size > 1 else 0.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="all")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--out", default="e1b_neighborhood")
    ap.add_argument("--rtol", type=float, default=2e-2,
                    help="tolerance for the unperturbed non-perturbation anchor")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    cells = (CELLS if args.cells == "all"
             else [c for c in CELLS if c["tag"] in args.cells.split(",")])

    rows = []
    print(f"### E1b neighborhood robustness ({platform.machine()}, "
          f"{platform.system()}): {len(cells)} cells x "
          f"({len(PHYS)} physical + {len(ROWORDER_SEEDS)} row-order) ###",
          flush=True)
    for c in cells:
        t0 = time.perf_counter()
        # 1) unperturbed anchor FIRST -- must reproduce the frozen ratio.
        base = measure(c["scene"], "xpbd", c["relax"], c["it"], c["su"],
                       nframes=args.nframes)
        ok = abs(base["ratio"] - c["ratio"]) <= args.rtol * abs(c["ratio"])
        print(f"\n[{c['tag']}] xpbd {c['scene']} r{c['relax']} "
              f"{c['it']}x{c['su']}: unperturbed R={base['ratio']:.6g} "
              f"(frozen {c['ratio']:.6g}) {'OK' if ok else 'ANCHOR-FAIL'}",
              flush=True)
        if not ok:
            print("  !! unperturbed run does not reproduce the frozen anchor -- "
                  "the perturbation kwargs are NOT inert; aborting this cell.")
            rows.append(dict(tag=c["tag"], cohort="anchor", pert="unperturbed",
                             **{k: c[k] for k in ("scene", "relax", "it", "su")},
                             **base))
            continue
        rows.append(dict(tag=c["tag"], cohort="anchor", pert="unperturbed",
                         scene=c["scene"], relax=c["relax"], it=c["it"],
                         su=c["su"], **base))
        # 2) physical cohort
        phys_m, phys_r = [], []
        for (name, kind, val) in PHYS:
            kw = _pert_kwargs(c["scene"], kind, val)
            if not kw and kind == "tilt":     # dinner has no tilt param
                continue
            m = measure(c["scene"], "xpbd", c["relax"], c["it"], c["su"],
                        build_kw=kw, nframes=args.nframes)
            phys_m.append(m["margin_J"]); phys_r.append(m["ratio"])
            rows.append(dict(tag=c["tag"], cohort="physical", pert=name,
                             scene=c["scene"], relax=c["relax"], it=c["it"],
                             su=c["su"], **m))
        # 3) row-order cohort (kept separate)
        row_m, row_r = [], []
        for seed in ROWORDER_SEEDS:
            m = measure(c["scene"], "xpbd", c["relax"], c["it"], c["su"],
                        roworder_seed=seed, nframes=args.nframes)
            row_m.append(m["margin_J"]); row_r.append(m["ratio"])
            rows.append(dict(tag=c["tag"], cohort="roworder", pert=f"perm{seed}",
                             scene=c["scene"], relax=c["relax"], it=c["it"],
                             su=c["su"], **m))
        sm, sr = _stats(phys_m), _stats(phys_r)
        rm, rr = _stats(row_m), _stats(row_r)
        print(f"  physical  margin: pos {sm.get('pos_frac',0)*100:.0f}%  "
              f"med {sm.get('median',0):+.4g}  IQR [{sm.get('q1',0):+.4g},"
              f"{sm.get('q3',0):+.4g}]  range [{sm.get('vmin',0):+.4g},"
              f"{sm.get('vmax',0):+.4g}]  log10-spread {sm.get('log10_spread',0):.2f}",
              flush=True)
        print(f"  physical  ratio : pos {sr.get('pos_frac',0)*100:.0f}%>0  "
              f"med {sr.get('median',0):.4g}  range [{sr.get('vmin',0):.4g},"
              f"{sr.get('vmax',0):.4g}]", flush=True)
        print(f"  roworder  margin: pos {rm.get('pos_frac',0)*100:.0f}%  "
              f"med {rm.get('median',0):+.4g}  range [{rm.get('vmin',0):+.4g},"
              f"{rm.get('vmax',0):+.4g}]  ({time.perf_counter()-t0:.0f}s)",
              flush=True)

    keys = sorted({k for r in rows for k in r})
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=sorted({c["scene"] for c in cells}),
        solvers=["xpbd"],
        note=("E1b (plan §9): deterministic local neighborhood-robustness audit "
              "of the headline XPBD cells. NO RNG, NO seed sweep, NO p-value. "
              "12 physical initial-condition perturbations (drop height, normal "
              "speed, contact x/z, tilt) and 4 contact-row-order permutations, "
              "kept in separate cohorts. Measurement-only (ledger live, "
              "passivity_gamma==1.0). Every cell's unperturbed run reproduces its "
              "frozen eq2_utilization.csv ratio before the ensemble runs."))
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
