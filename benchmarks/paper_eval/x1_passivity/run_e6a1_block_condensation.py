#!/usr/bin/env python3
"""E6a-1 — shared-row block-condensation ablation (rewrite plan §9 E6a-1).

CAUSAL PROBE, not a cure claim. Changes EXACTLY ONE variable of the three the
E6a vocabulary lock separates (claim sheet §3a): serial row-wise vs joint block
treatment of the support contacts that share the one modal vector q. Everything
else is held fixed -- implicit-midpoint modal restoring step
(`_modal_symplectic=True`), modal contact weight, timestep/substeps, iteration
budget, compliance, relaxation, warm-start policy, contact-row definitions.

  serial  : sol._support_block = False  -> loops _project_support per row
            (the paper's baseline position-based path).
  block   : sol._support_block = True   -> _project_support_block condenses all
            active support rows onto q in one solve.

DISCLOSURE (plan §9): the block path preserves the active-row compliant fixed
point but uses a DIAGONAL rigid-body block approximation and a DIFFERENT
convergence path. This is an ablation, not a behaviour-identical toggle.

Two measurements, both from identical initialization:
  (A) FULL ROLLOUT LADDER over budgets, both scenes: peak modal-to-incident
      ratio R, strict ledger margin, wall-clock. Shows whether block coupling
      reduces the injection and whether the serial/block gap narrows as the
      budget grows (a convergence-path difference) or persists (a formulation
      difference).
  (B) ONE-STEP FROZEN-STATE DELTA: two deterministic builds run to the same
      representative post-impact frame k (identical, since the benchmark has no
      RNG), then ONE more substep -- one serial, one block -- from that shared
      active-set state; compares the single-step modal-energy gain. Isolates the
      per-step effect of the row treatment at a fixed contact set.

Measurement-only: ledger live, passivity_gamma == 1.0 (dead actuator).

Out: out/{e6a1_block_condensation.csv, .config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_e6a1_block_condensation.py
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

import dcr.avbd._solver.passivity as _psv_mod                      # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy                  # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, SETTLE, NFRAMES)
from benchmarks.paper_eval.x1_passivity.run_eq2_utilization import (  # noqa: E402
    _neuter_gamma)
from benchmarks.paper_eval.paper_config import (                   # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
LADDER = [(4, 1), (8, 2), (16, 4), (32, 1)]


def _build(scene, it, su, relax, block):
    fn = SCENES[scene]
    H = fn(device="cpu", iterations=it, avbd_substeps=su, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=True, eta=1.0)
    sol._psv_monitor_only = False
    sol._support_block = bool(block)           # the ONE ablated variable
    return H, sol


def rollout(scene, it, su, relax, block, nframes=NFRAMES, settle=SETTLE):
    """Full rollout; returns R, strict margin, peak modal E, wall-clock."""
    t0 = time.perf_counter()
    H, sol = _build(scene, it, su, relax, block)
    led = sol._psv_ledger
    orig = _neuter_gamma()
    w = H.world
    ib = w._descs[H.impactor_idx].dcr_body
    e_imp = e_mod = 0.0
    finite = True
    try:
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
        _psv_mod.passivity_gamma = orig
    return dict(ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
                margin_J=float(led.max_net_excess), peak_modal_J=e_mod,
                finite=finite, wall_s=time.perf_counter() - t0)


def one_step_delta(scene, it, su, relax):
    """One-step frozen-state delta at the FIRST contact substep.

    Both builds are byte-identical through the ballistic pre-contact phase (the
    benchmark has no RNG), so the substep where contact first excites the modes
    starts from an IDENTICAL state. Its modal-energy gain is therefore a clean
    single-step comparison of the row treatment at a fixed active set -- unlike a
    fixed late frame, where serial and block have already diverged."""
    out = {}
    for block in (False, True):
        H, sol = _build(scene, it, su, relax, block)
        orig = _neuter_gamma()
        w = H.world
        prev = 0.0
        first = None
        try:
            for k in range(SETTLE + NFRAMES):
                w.step(); w._sync_avbd_to_dcr()
                e = sol.last_modal_KE + sol.last_modal_PE
                if e > 1e-3:                          # first contact substep
                    first = (k, prev, e, e - prev)
                    break
                prev = e
        finally:
            _psv_mod.passivity_gamma = orig
        out[block] = first if first is not None else (None, 0.0, 0.0, 0.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge")
    ap.add_argument("--budgets", default="")
    ap.add_argument("--relax", type=float, default=0.7)
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--frame-k", type=int, default=10,
                    help="post-impact frame for the one-step delta")
    ap.add_argument("--out", default="e6a1_block_condensation")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    budgets = (LADDER if not args.budgets else
               [tuple(int(v) for v in b.lower().split("x"))
                for b in args.budgets.split(",")])

    rows = []
    print(f"### E6a-1 block-condensation ablation ({platform.machine()}, "
          f"{platform.system()}), relax={args.relax} ###", flush=True)
    print("# serial = _support_block False (paper path); "
          "block = _support_block True (condensation)\n", flush=True)
    for scene in scenes:
        print(f"--- {scene}: full-rollout ladder ---")
        for (it, su) in budgets:
            ser = rollout(scene, it, su, args.relax, False, args.nframes)
            blk = rollout(scene, it, su, args.relax, True, args.nframes)
            red = (ser["ratio"] / blk["ratio"]) if blk["ratio"] > 0 else float("nan")
            for mode, m in (("serial", ser), ("block", blk)):
                rows.append(dict(scene=scene, kind="rollout", mode=mode,
                                 iters=it, substeps=su, relax=args.relax, **m))
            print(f"  {it:2d}x{su}: serial R={ser['ratio']:11.5g} "
                  f"margin={ser['margin_J']:+11.4g}  |  block R={blk['ratio']:11.5g} "
                  f"margin={blk['margin_J']:+11.4g}  |  R_serial/R_block={red:6.3g} "
                  f"| cost {ser['wall_s']:.2f}/{blk['wall_s']:.2f}s", flush=True)
        # one-step frozen-state delta at the FIRST contact substep (4x1)
        d = one_step_delta(scene, 4, 1, args.relax)
        sk, sb, sa, sd = d[False]; bk, bb, ba, bd = d[True]
        rows.append(dict(scene=scene, kind="onestep", mode="serial", iters=4,
                         substeps=1, relax=args.relax, frame=sk, e_before=sb,
                         e_after=sa, delta_J=sd))
        rows.append(dict(scene=scene, kind="onestep", mode="block", iters=4,
                         substeps=1, relax=args.relax, frame=bk, e_before=bb,
                         e_after=ba, delta_J=bd))
        same = "identical" if abs(sb - bb) < 1e-6 else "DIVERGED-pre"
        print(f"  one-step delta @first-contact (4x1, {same} pre-state): "
              f"serial ΔE={sd:+.4g} J | block ΔE={bd:+.4g} J\n", flush=True)

    keys = sorted({k for r in rows for k in r})
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
        note=("E6a-1 (plan §9): shared-row block-condensation causal probe. "
              "Ablates ONLY _support_block (serial rows vs joint condensation) in "
              "the position-based host, holding the implicit-midpoint restoring "
              "step, modal weight, budget, compliance, relaxation, warm-start and "
              "row definitions fixed. Full-rollout ladder + one-step frozen-state "
              "delta. Block preserves the active-row compliant fixed point but "
              "uses a diagonal rigid-body block approximation and a different "
              "convergence path -- an ablation, not a behaviour-identical toggle. "
              "Measurement-only (ledger live, gamma==1)."))
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
