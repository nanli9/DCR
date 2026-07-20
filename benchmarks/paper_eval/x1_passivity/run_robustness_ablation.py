#!/usr/bin/env python3
"""E-C9 — single-host robustness ablation of the XPBD result (plan §8.4, P7).

ISOLATED benchmark, C6 pattern. Imports scenes/solvers READ-ONLY and sets every
knob at RUNTIME (builder kwargs + solver attributes); it never modifies solver
source and never changes solver behaviour.

--------------------------------------------------------------------------
THE ASK
--------------------------------------------------------------------------
Both six-reviewer panels (2026-07-19) asked the same question about the
position-based amplification: is it a knife-edge artifact of one configuration?
The paper answers with breadth on two axes (budget, relaxation) but holds
everything else fixed, so the objection stands.

This measures ONE AXIS AT A TIME away from the two worst-behaved cells:

    ledge, relaxation 1.0, 4x1   -- the matrix worst cell (R = 1.19534e5)
    shelf, relaxation 0.7, 4x1   -- the 21.6 mm / teaser cell (R = 6333.22)

Axes: timestep h, contact and support compliance, modal rank, and both
Rayleigh damping coefficients. All are config-level; the verification pass
(plan §8 preamble) confirmed `h` / `n_modes_*` / `rayleigh_*` are
`build_reduced_*` kwargs and that XPBD's `contact_compliance` /
`support_compliance` are runtime-settable solver attributes
(solver_xpbd.py:243-266).

The carried-lambda warm-start arm is NOT here: it is a code change, stays
barred, and is answered in the text (lambda<-0 IS the published XPBD form; the
K-ladder isolates convergence level as the mechanism).

--------------------------------------------------------------------------
ACCEPTANCE IS PERSISTENCE-IN-KIND, NOT MAGNITUDE STABILITY
--------------------------------------------------------------------------
Pre-registered in plan §8.4 BEFORE running, so the reading cannot be chosen
after seeing the numbers. `h` in particular changes the scene's difficulty --
a finer step is a different mechanical problem, not the same one measured
better -- so magnitudes are EXPECTED to move. The claim under test is only:

    Eq. (2) still violated  AND  R >> 1,  away from the base configuration.

Pre-registered contingency: if the rank axis removes the amplification once
the stiff cluster is excluded, that is a SHARPENED DIAGNOSIS (stiff-tail
localization, consistent with §3.3's spectral analysis, where 99.6% of the
ungoverned energy sits in the stiff cluster), NOT a retraction. Wording follows
the numbers.

--------------------------------------------------------------------------
HOW IT MEASURES WITHOUT PERTURBING THE SOLVE
--------------------------------------------------------------------------
It does not re-implement the accounting. It calls `run_eq2_utilization.one()`
-- the §6.3 harness, already cross-validated against the impulse backend's live
monitor -- with a WRAPPED builder. The wrapper injects the ablated builder
kwargs and sets the ablated solver attributes post-build; `one()` then applies
relaxation / the symplectic stepper / the ledger exactly as it does for every
other cell, and neuters `passivity_gamma` to 1.0 so the ledger block's state
writes (all guarded by `if gamma < 1.0`) are dead. Same measurement code, same
non-perturbation guarantee, zero duplication.

Two knobs the wrapper must NOT collide with: `one()` passes
`iterations`/`avbd_substeps`/`solver`/`device` itself, and afterwards writes
`_modal_relax`/`modal_relax`, `_modal_symplectic`, `_enforce_modal_passivity`,
`_modal_eta`, `_psv_monitor_only`. Nothing in the ablation set overlaps those.

--------------------------------------------------------------------------
RANK IS DEFINED AGAINST THE REALIZED BASIS, NOT THE REQUESTED ONE
--------------------------------------------------------------------------
`reduced_scene_common.py:242` clamps `n_modes_local` to the number of DISTINCT
contact zones (deduped within 15 mm, because coincident bumps make Mq singular).
So the requested counts are not the delivered rank:

    shelf  10 global + 14 local requested -> rank 16 (10 bending 20.3 Hz-2.03
           kHz, then 6 stiff 20.7-24.7 kHz)
    ledge  12 global + 16 local requested -> rank 16 (12 modes 118 Hz-17.0 kHz,
           then 4 stiff 170-191 kHz)

(This is also why paper Table 1's r = 24/28 is wrong -- see findings.md.) The
rank points below are therefore chosen against the MEASURED spectrum, and every
row logs its realized rank and the stiff/resolved split so the choice is
checkable rather than asserted.

--------------------------------------------------------------------------
PHYSICAL DURATION IS HELD FIXED ACROSS THE h AXIS
--------------------------------------------------------------------------
The base protocol logs 100 frames after an 8-frame settle at h = 1/120. Holding
the FRAME count fixed while h varies would compare a 0.83 s window against a
0.42 s one and silently change which part of the impact is observed. We hold
the physical window fixed instead (nframes and settle scale with 1/h), so every
h cell watches the same event. Logged per row as `window_s`.

Out: out/{robustness_ablation.csv, robustness_ablation.config.json}
Run (serial -- see the concurrent-run wall-clock incident; this harness logs no
timings, but the rule is kept):
  .venv/bin/python benchmarks/paper_eval/x1_passivity/run_robustness_ablation.py
  .venv/bin/python .../run_robustness_ablation.py --dry-run   # configs only
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

from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, SETTLE, NFRAMES)
from benchmarks.paper_eval.x1_passivity import run_eq2_utilization as EQ2  # noqa: E402
from benchmarks.paper_eval.paper_config import write_manifest      # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

H_BASE = 1.0 / 120.0

# The two base cells, from the frozen E-S1b matrix. `frozen_R` is the published
# clamp-OFF ratio; the base row of each block must reproduce it, which is this
# harness's non-perturbation check (--check-frozen).
BASE_CELLS = [
    dict(cell="ledge_relax1.0_4x1", scene="ledge", relax=1.0, iters=4, subs=1,
         frozen_R=1.19534e5,
         note="matrix worst cell"),
    dict(cell="shelf_relax0.7_4x1", scene="shelf", relax=0.7, iters=4, subs=1,
         frozen_R=6333.22,
         note="the 21.6 mm / teaser cell"),
]

# Per-scene base values for the axes whose base differs by scene.
SCENE_BASE = {
    "shelf": dict(n_modes_global=10, n_modes_local=14, rayleigh_alpha0=3.0),
    "ledge": dict(n_modes_global=12, n_modes_local=16, rayleigh_alpha0=2.0),
}


def axis_points(scene: str) -> list[dict]:
    """One axis at a time from the base configuration.

    Each entry: axis, value (label), build_kw, sol_attrs. An empty build_kw and
    sol_attrs is the base row itself.
    """
    sb = SCENE_BASE[scene]
    ng, nl, a0 = sb["n_modes_global"], sb["n_modes_local"], sb["rayleigh_alpha0"]
    pts: list[dict] = [dict(axis="base", value="base", build_kw={}, sol_attrs={})]

    # -- timestep ---------------------------------------------------------
    for inv in (60, 240):
        pts.append(dict(axis="h", value=f"1/{inv}",
                        build_kw=dict(h=1.0 / inv), sol_attrs={}))

    # -- support compliance (the contact->modal load; base 1e-8) -----------
    for c in (1e-6, 1e-4):
        pts.append(dict(axis="support_compliance", value=f"{c:g}",
                        build_kw={}, sol_attrs=dict(support_compliance=c)))

    # -- rigid contact compliance (base 0.0 = rigid) -----------------------
    for c in (1e-8, 1e-6):
        pts.append(dict(axis="contact_compliance", value=f"{c:g}",
                        build_kw={}, sol_attrs=dict(contact_compliance=c)))

    # -- modal rank, against the REALIZED basis ---------------------------
    # n_modes_local=0 drops the local bumps entirely, which is where the stiff
    # cluster lives (they are the high-frequency compliance modes at the
    # contact zones); n_modes_global+6 adds resolved bending modes above base.
    pts.append(dict(axis="rank", value="no local (excl. stiff cluster)",
                    build_kw=dict(n_modes_local=0), sol_attrs={}))
    pts.append(dict(axis="rank", value=f"n_global={ng + 6}",
                    build_kw=dict(n_modes_global=ng + 6), sol_attrs={}))

    # -- Rayleigh damping --------------------------------------------------
    for v in (1.0, 6.0):
        if abs(v - a0) < 1e-12:
            continue
        pts.append(dict(axis="rayleigh_alpha0", value=f"{v:g}",
                        build_kw=dict(rayleigh_alpha0=v), sol_attrs={}))
    pts.append(dict(axis="rayleigh_alpha1", value="1e-4",
                    build_kw=dict(rayleigh_alpha1=1e-4), sol_attrs={}))
    return pts


def spectrum(sol) -> dict:
    """Realized modal spectrum, read from the solver's own reduced operator.

    Same source as run_governed_accuracy.py:141. Reported so the rank axis is
    checkable: `f_gap_lo`/`f_gap_hi` bracket the bimodal gap, and `n_stiff`
    counts the cluster above it.
    """
    out = dict(rank=None, f_min_Hz=None, f_max_Hz=None, n_stiff=None,
               f_gap_lo_Hz=None, f_gap_hi_Hz=None)
    kq = getattr(sol, "_kq", None)
    if kq is None:
        return out
    kq = np.asarray(kq, dtype=np.float64)
    mq = getattr(sol, "_mq", None)
    mqv = np.ones_like(kq) if mq is None else np.asarray(mq, dtype=np.float64)
    f = np.sqrt(np.maximum(kq / np.where(mqv > 0, mqv, 1.0), 0.0)) / (2 * np.pi)
    if f.size == 0:
        return out
    fs = np.sort(f)
    out["rank"] = int(f.size)
    out["f_min_Hz"] = float(fs[0])
    out["f_max_Hz"] = float(fs[-1])
    if f.size > 1:
        # The spectrum is bimodal; split at the largest multiplicative jump
        # rather than a fixed Hz threshold, so it transfers across scenes and
        # across rank settings instead of being a tuned knob.
        ratios = fs[1:] / np.maximum(fs[:-1], 1e-30)
        j = int(np.argmax(ratios))
        # The real bimodal gaps here are >= 10x (shelf 10.2x, ledge 10.0x,
        # shelf n_global=16 11.7x), while a bending series climbs by at most
        # ~4x at its bottom end and ~1.3x typically. A flat 3x threshold
        # therefore mis-fires on the 20.3 -> 81.4 Hz step once the local bumps
        # are removed and reports a 9-mode "stiff cluster" that does not exist.
        # Require a decade-ish jump AND one far above this spectrum's own
        # typical step, so the split stays a measurement rather than a knob.
        if ratios[j] > max(6.0, 3.0 * float(np.median(ratios))):
            out["f_gap_lo_Hz"] = float(fs[j])
            out["f_gap_hi_Hz"] = float(fs[j + 1])
            out["n_stiff"] = int(f.size - j - 1)
        else:
            out["n_stiff"] = 0
    return out


def make_builder(base_fn, build_kw: dict, sol_attrs: dict, cap: dict):
    """Wrap a scene builder with the ablated settings (the C6 pattern).

    `cap` is filled in with the realized spectrum and the settings actually
    landed on the solver, so every row can report what it really ran rather
    than what it asked for.
    """
    def _wrapped(**kw):
        H = base_fn(**{**kw, **build_kw})
        sol = H.world._solver
        for k, v in sol_attrs.items():
            if not hasattr(sol, k):
                raise AttributeError(
                    f"{type(sol).__name__} has no attribute {k!r}; the "
                    f"ablation would have been a silent no-op")
            setattr(sol, k, v)
        cap.update(spectrum(sol))
        cap["dt_s"] = float(getattr(sol, "dt", float("nan")))
        cap["support_compliance"] = float(getattr(sol, "support_compliance",
                                                  float("nan")))
        cap["contact_compliance"] = float(getattr(sol, "contact_compliance",
                                                  float("nan")))
        return H
    _wrapped.__name__ = getattr(base_fn, "__name__", "build") + "_ablated"
    return _wrapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="",
                    help="comma-separated base-cell keys (default: both)")
    ap.add_argument("--axes", default="",
                    help="comma-separated axis names to run (default: all)")
    ap.add_argument("--eta", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="build every configuration and report the realized "
                         "rank/spectrum/settings WITHOUT simulating")
    ap.add_argument("--rtol", type=float, default=1e-3)
    ap.add_argument("--out", default="robustness_ablation")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    cells = BASE_CELLS
    if args.cells:
        want = {c.strip() for c in args.cells.split(",") if c.strip()}
        cells = [c for c in cells if c["cell"] in want]
    want_axes = {a.strip() for a in args.axes.split(",") if a.strip()}

    plan = []
    for base in cells:
        for pt in axis_points(base["scene"]):
            if want_axes and pt["axis"] not in want_axes and pt["axis"] != "base":
                continue
            plan.append((base, pt))

    print(f"### E-C9 robustness ablation (plan §8.4): {len(plan)} runs "
          f"({platform.machine()}, {platform.system()}, "
          f"python {platform.python_version()}) ###", flush=True)
    print("#   governor OFF (gamma == 1); verdict = strict Eq.(2) margin in "
          "joules, >0 violates", flush=True)
    print("#   acceptance = persistence in kind (Eq.(2) violated AND R >> 1), "
          "NOT magnitude stability", flush=True)

    rows = []
    t_start = time.perf_counter()
    for i, (base, pt) in enumerate(plan, 1):
        scene = base["scene"]
        fn = SCENES[scene]
        cap: dict = {}
        wrapped = make_builder(fn, pt["build_kw"], pt["sol_attrs"], cap)

        # Hold the physical window fixed across the h axis (see module doc).
        h = pt["build_kw"].get("h", H_BASE)
        scale = H_BASE / h
        nframes = max(1, int(round(NFRAMES * scale)))
        settle = max(1, int(round(SETTLE * scale)))

        label = f"{base['cell']}  {pt['axis']}={pt['value']}"
        print(f"\n[{i}/{len(plan)}] {label}", flush=True)

        if args.dry_run:
            H = wrapped(device="cpu", iterations=base["iters"],
                        avbd_substeps=base["subs"], solver="xpbd")
            del H
            print(f"      rank={cap.get('rank')}  "
                  f"f {cap.get('f_min_Hz'):.1f}..{cap.get('f_max_Hz'):.1f} Hz  "
                  f"n_stiff={cap.get('n_stiff')}  "
                  f"gap {cap.get('f_gap_lo_Hz')}..{cap.get('f_gap_hi_Hz')}  "
                  f"dt={cap.get('dt_s'):.6g}  "
                  f"supp_c={cap.get('support_compliance'):g}  "
                  f"cont_c={cap.get('contact_compliance'):g}  "
                  f"nframes={nframes} settle={settle}", flush=True)
            rows.append(dict(cell=base["cell"], scene=scene, relax=base["relax"],
                             iters=base["iters"], substeps=base["subs"],
                             axis=pt["axis"], value=pt["value"],
                             nframes=nframes, settle=settle,
                             window_s=nframes * h, **cap))
            continue

        m = EQ2.one(wrapped, "xpbd", base["iters"], base["subs"], base["relax"],
                    nframes=nframes, settle=settle, eta=args.eta)
        row = dict(cell=base["cell"], scene=scene, relax=base["relax"],
                   iters=base["iters"], substeps=base["subs"],
                   axis=pt["axis"], value=pt["value"],
                   nframes=nframes, settle=settle, window_s=nframes * h,
                   **cap, **m)
        rows.append(row)
        v = ("VIOLATES" if m["eq2_violates"] else "holds   ") \
            if m["eq2_violates"] is not None else "no-ledger"
        print(f"      R={m['ratio_off']:12.4g}  Eq2={v}  "
              f"margin={m['margin_J']:+12.4g} J  "
              f"supply={m['gross_supply']:10.4g} J  "
              f"rank={cap.get('rank')} n_stiff={cap.get('n_stiff')}  "
              f"finite={m['finite']}  ({m['wall_s']:.1f} s)", flush=True)

    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    stem = args.out + ("_dryrun" if args.dry_run else "")
    csv_path = os.path.join(OUT, f"{stem}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    if not args.dry_run:
        write_manifest(
            OUT, f"{stem}.csv", scenes=sorted({c["scene"] for c in cells}),
            solvers=["xpbd"],
            note=("E-C9 (plan §8.4): single-host robustness ablation of the "
                  "XPBD result. One axis at a time (h, support/contact "
                  "compliance, modal rank, Rayleigh alpha0/alpha1) from the two "
                  "worst-behaved E-S1b cells, governor OFF. Measurement-only: "
                  "runs run_eq2_utilization.one() with a wrapped builder, so "
                  "the ledger is live while passivity_gamma == 1.0 makes every "
                  "state write in the ledger block dead. Acceptance is "
                  "persistence in kind (Eq.(2) violated AND R >> 1), NOT "
                  "magnitude stability -- pre-registered in plan 8.4 before "
                  "running. Physical window held fixed across the h axis "
                  "(nframes/settle scale with 1/h). Rank is reported as the "
                  "REALIZED basis size, which the contact-zone dedup clamp "
                  "(reduced_scene_common.py:242) makes smaller than the "
                  "requested n_modes_global+n_modes_local."))

    # ---- summary ---------------------------------------------------------
    if not args.dry_run and rows:
        print("\n--- persistence in kind, per base cell ---")
        for base in cells:
            sr = [r for r in rows if r["cell"] == base["cell"]]
            if not sr:
                continue
            n_viol = sum(1 for r in sr if r.get("eq2_violates"))
            n_big = sum(1 for r in sr if r.get("ratio_off", 0) > 1.0)
            Rs = [r["ratio_off"] for r in sr if np.isfinite(r.get("ratio_off", np.inf))]
            print(f"  {base['cell']}: Eq.(2) violated in {n_viol}/{len(sr)} "
                  f"configurations, R > 1 in {n_big}/{len(sr)}")
            if Rs:
                print(f"      R spans {min(Rs):.4g} .. {max(Rs):.4g}")
            # base-row non-perturbation check
            b = next((r for r in sr if r["axis"] == "base"), None)
            if b is not None:
                got, want = b["ratio_off"], base["frozen_R"]
                ok = abs(got - want) <= args.rtol * abs(want)
                print(f"      {'OK  ' if ok else 'FAIL'} base row reproduces "
                      f"frozen E-S1b R: got {got:.6g}, frozen {want:.6g}")
            for r in sr:
                if r["axis"] == "base":
                    continue
                print(f"        {r['axis']:20s} {str(r['value']):28s} "
                      f"R={r['ratio_off']:12.4g}  "
                      f"margin={r['margin_J']:+12.4g} J  "
                      f"rank={r.get('rank')}")

    print(f"\nwrote {csv_path}   ({time.perf_counter() - t_start:.1f} s total)")


if __name__ == "__main__":
    main()
