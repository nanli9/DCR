#!/usr/bin/env python3
"""E-S2 — iteration-budget (K) convergence sweep with the impulse oracle.

ISOLATED benchmark. Reuses the E-S1 cell runner (`run_solver_matrix.one`) so the
metric is bit-identical across E-S1 and E-S2: peak modal energy (KE+PE) over
peak incident rigid KE of the impactor, un-governed (clamp OFF).

Question: is the modal energy injection a TRUNCATION artifact of the fixed local
iteration budget, or a property of the coupling itself? Sweep the budget K and
watch the ratio.

Scene: the shelf drop -- a deterministic single-impactor scene (the plan
explicitly says avoid chaotic stacks; shelf and ledge reproduce the reference
X1 cells exactly on this machine, dinner does not because the scene was
redefined on this branch). Substeps are PINNED AT 1 so K is the only knob: this
isolates local-iteration truncation from substep refinement, and it is the
adversarial corner where truncation dominates.

Curves:
  * xpbd     K = 1..32
  * avbd     K = 1..32
  * impulse  K = 2..64
  * impulse  K = 500  -- the converged reference lambda*, drawn as a horizontal
    oracle line. Same code path as the K-sweep points, so the oracle is not a
    different model: it is the same solver run to (near) convergence.

Acceptance (plan §2, E-S2): XPBD's curve decays toward the oracle line as K
grows -- "truncation creates it, convergence cures it".

Out: out/{k_convergence.csv, k_convergence.png, k_convergence.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_k_convergence.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, one)
from benchmarks.paper_eval.paper_config import write_manifest       # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

K_XPBD = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32]
K_AVBD = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32]
K_IMPULSE = [2, 4, 8, 16, 32, 64]
K_ORACLE = 500
SUBSTEPS = 1
RELAX = 0.7   # PAPER_CONFIG relax; inert on the impulse backend


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="shelf", choices=sorted(SCENES))
    ap.add_argument("--substeps", type=int, default=SUBSTEPS)
    ap.add_argument("--relax", type=float, default=RELAX)
    ap.add_argument("--oracle", type=int, default=K_ORACLE)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="k_convergence")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    fn = SCENES[args.scene]

    plan = ([("xpbd", k) for k in K_XPBD]
            + [("avbd", k) for k in K_AVBD]
            + [("impulse", k) for k in K_IMPULSE]
            + [("impulse", args.oracle)])

    print(f"### E-S2 K-convergence: scene={args.scene} substeps={args.substeps} "
          f"relax={args.relax} ({platform.machine()}) ###", flush=True)
    rows = []
    for solver, k in plan:
        r = one(fn, solver, k, args.substeps, args.relax, False, args.nframes)
        is_oracle = (solver == "impulse" and k == args.oracle)
        rows.append(dict(solver=solver, K=k, substeps=args.substeps,
                         relax=args.relax, is_oracle=is_oracle,
                         ratio=r["ratio"], e_modal_peak=r["e_modal_peak"],
                         e_imp_peak=r["e_imp_peak"], holds=r["holds"],
                         passive=r["passive"], finite=r["finite"],
                         wall_s=r["wall_s"]))
        print(f"  {solver:7s} K={k:3d}{' (ORACLE)' if is_oracle else '        '}: "
              f"ratio={r['ratio']:12.6g}  E_modal={r['e_modal_peak']:10.4g} J  "
              f"E_imp={r['e_imp_peak']:8.4g} J  holds={r['holds']} "
              f"[{r['wall_s']:.1f}s]", flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(OUT, f"{args.out}.csv", scenes=[args.scene],
                   solvers=["xpbd", "avbd", "impulse"],
                   note=(f"E-S2 K-convergence, substeps={args.substeps} pinned, "
                         f"clamp OFF; oracle = impulse K={args.oracle}. "
                         f"ratio = peak modal E / peak incident rigid KE."))

    _fig(rows, args, csv_path)

    # ---- acceptance check -------------------------------------------------
    oracle = next(r["ratio"] for r in rows if r["is_oracle"])
    xp = [r for r in rows if r["solver"] == "xpbd"]
    lo, hi = xp[0]["ratio"], xp[-1]["ratio"]
    print(f"\n--- acceptance (plan §2 E-S2) ---")
    print(f"  oracle (impulse K={args.oracle}) ratio = {oracle:.6g}")
    print(f"  xpbd K={xp[0]['K']} ratio = {lo:.6g}   ->   "
          f"xpbd K={xp[-1]['K']} ratio = {hi:.6g}")
    print(f"  |xpbd-oracle| shrinks {abs(lo - oracle):.6g} -> "
          f"{abs(hi - oracle):.6g}: "
          f"{'PASS (decays toward oracle)' if abs(hi - oracle) < abs(lo - oracle) else 'FAIL'}")
    mono = all(xp[i]["ratio"] >= xp[i + 1]["ratio"] for i in range(len(xp) - 1))
    print(f"  xpbd monotone non-increasing in K: {mono}")
    print(f"\nwrote {csv_path}")


def _fig(rows, args, csv_path):
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    styles = {"xpbd": ("o-", "tab:red"), "avbd": ("s-", "tab:blue"),
              "impulse": ("^-", "tab:green")}
    for solver in ("xpbd", "avbd", "impulse"):
        pts = [r for r in rows if r["solver"] == solver and not r["is_oracle"]]
        if not pts:
            continue
        mk, c = styles[solver]
        ax.plot([p["K"] for p in pts], [p["ratio"] for p in pts], mk, color=c,
                label=solver.upper(), ms=4, lw=1.4)
    oracle = next(r["ratio"] for r in rows if r["is_oracle"])
    ax.axhline(oracle, ls="--", c="k", lw=1.2,
               label=f"oracle: impulse $K$={args.oracle} ({oracle:.3g})")
    ax.axhline(1.0, ls=":", c="0.5", lw=1.0)
    ax.text(1.05, 1.05, "injection threshold", fontsize=7, color="0.4")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel(r"local iteration budget $K$  (substeps = %d)" % args.substeps)
    ax.set_ylabel("peak modal energy / incident rigid KE")
    ax.set_title(f"E-S2: injection is a truncation artifact ({args.scene} drop)",
                 fontsize=10)
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    fig.tight_layout()
    png = csv_path.replace(".csv", ".png")
    fig.savefig(png, dpi=160)
    fig.savefig(png.replace(".png", ".pdf"))
    print(f"wrote {png}")


if __name__ == "__main__":
    main()
