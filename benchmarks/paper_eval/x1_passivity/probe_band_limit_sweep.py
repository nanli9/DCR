#!/usr/bin/env python3
"""Reviewer response — does BAND-LIMITING the co-solved basis remove the
injection, or only reduce it? The full-sweep generalization of the paper's
single-cell rank result (sec 3.5: excluding the stiff cluster on the shelf 4x1
cell cuts R 6333 -> 22.1, yet 584 J is still overdrawn).

The paper names band-limiting the co-solved basis as the first-line remedy for
the stiff-tail super-Nyquist energy (sec 3.3). This probe applies that remedy to
EVERY sweep cell and measures what survives. The exclusion uses the paper's own
definition (run_robustness_ablation.py:170): rebuild with n_modes_local=0, which
drops the local contact-zone bumps where the stiff cluster lives. The realized
spectrum is read back per cell (spectrum(): rank, n_stiff) so the exclusion is a
logged measurement, not an assumed one -- n_stiff should be 0 after the drop.

Measurement is run_eq2_utilization.one() verbatim, so the band-limited R and
Eq.(2) margin are directly comparable to the reported full-basis numbers, which
are read from the committed eq2_utilization.csv (the warm-start probe already
confirmed one() reproduces that file bit-for-bit on this machine).

Reading:
  * If band-limiting drives R below 1 and the margin below 0 everywhere, the
    injection was purely the unrepresentable stiff tail and a scalar bound is
    unnecessary -- band-limit instead.
  * If R falls sharply but cells still overdraw (as the shelf 4x1 584 J does),
    band-limiting is necessary but NOT sufficient, and the bound retains a role
    as the residual backstop.

Out: out/{band_limit_sweep.csv, band_limit_sweep.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_band_limit_sweep.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x1_passivity.run_eq2_utilization import one   # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (       # noqa: E402
    SCENES, BUDGETS)
from benchmarks.paper_eval.x1_passivity.run_robustness_ablation import (  # noqa: E402
    spectrum)
from benchmarks.paper_eval.paper_config import write_manifest            # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
BASE_CSV = os.path.join(OUT, "eq2_utilization.csv")


def _band_builder(base_fn):
    """Wrap a scene builder to drop the stiff cluster (n_modes_local=0), the
    paper's own exclusion (run_robustness_ablation.py:170)."""
    def _b(**kw):
        return base_fn(n_modes_local=0, **kw)
    return _b


def _load_baseline():
    """Full-basis R and margin per XPBD cell, from the committed sweep."""
    base = {}
    with open(BASE_CSV) as fh:
        for r in csv.DictReader(fh):
            if r["solver"] != "xpbd":
                continue
            key = (r["scene"], float(r["relax"]), int(r["iters"]),
                   int(r["substeps"]))
            mj = r.get("margin_J", "")
            base[key] = (float(r["ratio_off"]),
                         float(mj) if mj not in ("", "None", None) else None)
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--budgets", default="")
    ap.add_argument("--out", default="band_limit_sweep")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]
    if args.budgets:
        budgets = [tuple(int(v) for v in b.lower().split("x"))
                   for b in args.budgets.split(",") if b.strip()]
    else:
        budgets = BUDGETS
    base = _load_baseline()

    print(f"### band-limit sweep (n_modes_local=0), position-based host "
          f"({platform.machine()}, {platform.system()}) ###", flush=True)
    print("#   full = eq2_utilization.csv (all modes);  "
          "band = stiff cluster excluded", flush=True)

    spec_holder = {}

    def _capture(sol):
        spec_holder["s"] = spectrum(sol)

    rows = []
    for scene in scenes:
        bfn = _band_builder(SCENES[scene])
        for relax in relaxes:
            for (it, su) in budgets:
                try:
                    m = one(bfn, "xpbd", it, su, relax, mutate=_capture)
                except Exception as exc:                      # noqa: BLE001
                    print(f"  {scene:7s} relax={relax} {it:2d}x{su}: "
                          f"SKIP ({type(exc).__name__}: {exc})", flush=True)
                    continue
                s = spec_holder.get("s", {})
                R_full, margin_full = base.get((scene, relax, it, su),
                                               (float("nan"), None))
                row = dict(
                    scene=scene, relax=relax, iters=it, substeps=su,
                    R_full=R_full, R_band=m["ratio_off"],
                    margin_full_J=margin_full, margin_band_J=m["margin_J"],
                    rank_band=s.get("rank"), n_stiff_band=s.get("n_stiff"),
                    f_max_band_Hz=s.get("f_max_Hz"))
                rows.append(row)
                print(f"  {scene:7s} relax={relax} {it:2d}x{su}: "
                      f"R_full={R_full:11.4g}  R_band={m['ratio_off']:10.4g}"
                      f"  margin_band={_g(m['margin_J'])} J"
                      f"  rank={s.get('rank')} n_stiff={s.get('n_stiff')}",
                      flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
        note=("Reviewer response: band-limit the co-solved basis (exclude the "
              "stiff cluster via n_modes_local=0, run_robustness_ablation.py's "
              "own definition) across the full sweep and remeasure R and the "
              "Eq.(2) margin with run_eq2_utilization.one(). full-basis values "
              "read from eq2_utilization.csv. Tests whether band-limiting the "
              "co-solve is sufficient to remove the injection or only reduces "
              "it (the shelf 4x1 cell keeps 584 J overdrawn even so)."))

    # ---- verdict ---------------------------------------------------------
    inj = [r for r in rows if r["R_full"] > 1.0]
    print("\n--- verdict (cells that inject at full basis) ---")
    still = 0
    for r in inj:
        over = r["margin_band_J"] is not None and r["margin_band_J"] > 0.0
        still += int(over)
        print(f"  {r['scene']:7s} relax={r['relax']} {r['iters']:2d}x{r['substeps']}: "
              f"R {r['R_full']:.4g} -> {r['R_band']:.4g}   "
              f"margin {_g(r['margin_full_J'])} -> {_g(r['margin_band_J'])} J   "
              f"{'STILL OVERDRAWS' if over else 'within budget'}")
    print(f"\n  of {len(inj)} full-basis injecting cells, {still} still overdraw "
          f"after band-limiting")
    print(f"wrote {csv_path}")


def _g(v):
    return f"{v:+.4g}" if v is not None else "n/a"


if __name__ == "__main__":
    main()
