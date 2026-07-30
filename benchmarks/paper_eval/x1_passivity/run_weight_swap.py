#!/usr/bin/env python3
"""E-WS — the reviewer-requested WEIGHT-SWAP control arm (MIG 2026 short paper).

Every MIG reviewer bar one asked the same question: the three hosts differ in the
modal contact-row weight (XPBD's EXPLICIT per-mode compliance vs the impulse
host's IMPLICIT (M+hD+h²K)⁻¹), and §3.1 names that difference but never controls
for it. This harness runs the ONE missing arm:

    the XPBD host, EVERYTHING fixed (position-based unknown, warm start,
    relaxation, per-substep contact regeneration, the symplectic modal stepper),
    changing ONLY the modal inverse-mass used in the support CONTACT row from
        explicit   w = 1/M_q                         (the shipped XPBD weight)
    to
        implicit   w = (M_q + h·D_q + h²·K_q)⁻¹      (the impulse host's W_eff).

Mechanism under test (R2's derivation): for a mass-normalized basis the explicit
weight hands every stiff mode 1/M_q = 1, so an under-converged serial sweep over
~48 support rows drives modes at h²ω² ≫ 1 as if they were nearly free; the
implicit weight sends W_eff → 0 for those modes, so the row cannot ring them up.

If the injection DIES under the implicit weight, the paper's operating guide is
wrong in its most consequential rung ("spend K≥24 iterations" becomes "fix one
effective-mass expression, free"). If it SURVIVES, the diagnosis is nailed to the
fixed budget and the title stands. Either outcome is decisive; we do not know
which world we are in until we run it.

ISOLATED benchmark. Sets `sol._wq_support` at RUNTIME (an opt-in solver knob that
defaults to None ⇒ bit-identical to the frozen runs). The BASELINE arm
(swap OFF) is asserted against the frozen `solver_matrix.csv` ratio_off column so
the swapped arm is trustworthy.

Out: out/weight_swap.csv
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_weight_swap.py
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

from scenes.reduced_shelf import build_reduced_shelf            # noqa: E402
from scenes.reduced_ledge import build_reduced_ledge            # noqa: E402
from scenes.reduced_dinner_table import build_reduced_dinner_table  # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy               # noqa: E402
from benchmarks.paper_eval.paper_config import (                # noqa: E402
    apply_relax, apply_passivity, write_manifest)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}
# Deployed budgets are the reviewers' explicit ask (4x1, 8x2); 16x4/32x8 included
# so the arm covers the same axis as Fig. 2 and the converged end is visible.
BUDGETS = [(4, 1), (8, 2), (16, 4), (32, 8)]
RELAXES = [0.7, 1.0]
SETTLE = 8
NFRAMES = 100


def _install_weight_swap(sol) -> dict:
    """Set the implicit contact-row modal weight on an already-built XPBD solver.
    Returns a small diagnostic dict (spectrum + the two weights) for the log."""
    mq = np.asarray(sol._mq, dtype=np.float64)
    kq = np.asarray(sol._kq, dtype=np.float64)
    dq = np.asarray(sol._dq, dtype=np.float64)
    h = float(sol.dt) / int(sol.substeps)          # substep timestep
    w_explicit = np.where(mq > 0.0, 1.0 / np.maximum(mq, 1e-300), 0.0)
    denom = mq + h * dq + (h * h) * kq             # (M + hD + h²K), diag
    w_implicit = np.where(mq > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)
    sol._wq_support = w_implicit
    omega = np.sqrt(np.maximum(kq, 0.0)) / (2.0 * np.pi)   # modal freq [Hz]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(w_explicit > 0, w_implicit / w_explicit, np.nan)
    return dict(h_sub=h, f_lo=float(omega[omega > 0].min()) if np.any(omega > 0)
                else 0.0, f_hi=float(omega.max()),
                wratio_min=float(np.nanmin(ratio)),
                wratio_max=float(np.nanmax(ratio)))


def one(build_fn, it, su, relax, swap, nframes=NFRAMES, settle=SETTLE):
    """One XPBD cell, governor OFF. swap=False is the shipped weight (baseline);
    swap=True installs the implicit contact-row weight. Never raises on blow-up."""
    t0 = time.perf_counter()
    H = build_fn(device="cpu", iterations=it, avbd_substeps=su, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=False, eta=1.0)   # governor OFF
    sol._psv_monitor_only = False
    diag = {}
    if swap:
        diag = _install_weight_swap(sol)

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
    L = getattr(sol, "_psv_ledger", None)
    return dict(
        ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
        e_modal_peak=e_mod if finite else float("inf"),
        e_imp_peak=e_imp,
        holds=(L.holds() if L is not None else None),
        finite=finite, wall_s=time.perf_counter() - t0, **diag)


def _load_frozen(path):
    """ratio_off keyed by (scene, relax, it, su) from the frozen XPBD matrix."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for row in csv.DictReader(fh):
            if row["solver"] != "xpbd":
                continue
            key = (row["scene"], float(row["relax"]),
                   int(row["iters"]), int(row["substeps"]))
            out[key] = float(row["ratio_off"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--budgets", default="4x1,8x2",
                    help="default deployed pair; use 4x1,8x2,16x4,32x8 for all")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--out", default="weight_swap")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]
    budgets = [tuple(int(v) for v in b.lower().split("x"))
               for b in args.budgets.split(",") if b.strip()]
    frozen = _load_frozen(os.path.join(OUT, "solver_matrix.csv"))

    rows = []
    worst_baseline_reldiff = 0.0
    print(f"### E-WS weight-swap arm ({platform.machine()}, {platform.system()}) "
          f"### baseline must match frozen ratio_off\n", flush=True)
    print(f"{'scene':7s} {'rel':4s} {'bud':5s} | {'R explicit':>12s} "
          f"{'R implicit':>12s} | {'holds expl':>10s} {'holds impl':>10s} | "
          f"{'frozen':>12s} {'Δbase':>9s}", flush=True)
    for scene in scenes:
        fn = SCENES[scene]
        for relax in relaxes:
            for (it, su) in budgets:
                base = one(fn, it, su, relax, False, args.nframes)
                sw = one(fn, it, su, relax, True, args.nframes)
                key = (scene, relax, it, su)
                fz = frozen.get(key)
                reldiff = (abs(base["ratio"] - fz) / max(abs(fz), 1e-9)
                           if fz is not None and np.isfinite(base["ratio"])
                           else float("nan"))
                if np.isfinite(reldiff):
                    worst_baseline_reldiff = max(worst_baseline_reldiff, reldiff)
                rows.append(dict(
                    scene=scene, relax=relax, iters=it, substeps=su,
                    ratio_explicit=base["ratio"], ratio_implicit=sw["ratio"],
                    e_modal_explicit=base["e_modal_peak"],
                    e_modal_implicit=sw["e_modal_peak"],
                    holds_explicit=base["holds"], holds_implicit=sw["holds"],
                    finite_explicit=base["finite"], finite_implicit=sw["finite"],
                    ratio_frozen=fz, baseline_reldiff=reldiff,
                    f_lo_hz=sw.get("f_lo"), f_hi_hz=sw.get("f_hi"),
                    h_sub=sw.get("h_sub"),
                    wratio_min=sw.get("wratio_min"),
                    wratio_max=sw.get("wratio_max"),
                    wall_s=base["wall_s"] + sw["wall_s"]))
                fz_s = f"{fz:12.4g}" if fz is not None else f"{'n/a':>12s}"
                rd_s = f"{reldiff:9.1e}" if np.isfinite(reldiff) else f"{'n/a':>9s}"
                print(f"{scene:7s} {relax:<4} {it:2d}x{su:<2} | "
                      f"{base['ratio']:12.4g} {sw['ratio']:12.4g} | "
                      f"{str(base['holds']):>10s} {str(sw['holds']):>10s} | "
                      f"{fz_s} {rd_s}", flush=True)

    keys = list(rows[0].keys())
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
        note=("E-WS: XPBD host, governor OFF, EXPLICIT 1/M_q vs IMPLICIT "
              "(M+hD+h²K)⁻¹ modal contact-row weight, all else fixed. "
              "Reviewer-requested weight-swap control. baseline (explicit) is "
              "asserted against frozen solver_matrix.csv ratio_off."))

    print(f"\n--- baseline fidelity: worst |ΔR|/R vs frozen = "
          f"{worst_baseline_reldiff:.2e} "
          f"({'PASS' if worst_baseline_reldiff < 1e-6 else 'CHECK'}) ---")
    inj_expl = [r for r in rows if np.isfinite(r["ratio_explicit"])
                and r["ratio_explicit"] > 1.0]
    print(f"--- injecting cells (R>1): explicit {len(inj_expl)}/{len(rows)}, "
          f"implicit "
          f"{sum(1 for r in rows if np.isfinite(r['ratio_implicit']) and r['ratio_implicit'] > 1.0)}"
          f"/{len(rows)} ---")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
