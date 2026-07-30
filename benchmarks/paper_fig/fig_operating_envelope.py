#!/usr/bin/env python3
"""MIG short paper Fig. 3 (rewrite) — the XPBD operating envelope.

Three aligned panels; the page the plan calls the one that makes the diagnostic
academically substantial. All position-based (XPBD), governor OFF.

  (a) INJECTION vs LOCAL ITERATIONS.  R = peak modal E / incident rigid KE on a
      deterministic shelf drop, substeps pinned at 1 so K is the only variable.
      XPBD decays monotonically toward the implicit converged reference, crossing
      the incident-energy threshold R=1 between K=16 and 24. Two annotations
      carry results that used to cost separate prose: the 32x1-vs-4x8 equal-row
      pair (iterations beat substeps) and warm-start (does not help; worse at
      4x1).
  (b) COMPLEMENTARITY vs K.  The gap residual (end-of-substep penetration)
      converges with K, confirming the falling ratio is the ROW converging, not
      a scalar shrinking coincidentally.
  (c) SHARED-ROW TREATMENT (E6a-1).  Serial per-row support projection (paper
      path) vs joint block condensation, R vs budget, both scenes. The serial
      path converges/holds by 16x4-32x1; block condensation does NOT -- it is a
      different, worse convergence path, injecting where serial holds. This
      replaces the un-run E3 cutoff panel (plan Fig. 3), and is the causal probe
      that block condensation is not the fix.

Reads k_convergence.csv, substep_sweep.csv, warm_start_ablation.csv,
complementarity_residual.csv, e6a1_block_condensation.csv (all frozen).

Run: .venv/bin/python benchmarks/paper_fig/fig_operating_envelope.py
"""
from __future__ import annotations

import csv
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import matplotlib.pyplot as plt

from benchmarks.paper_fig.figstyle import apply_style, save, PALETTE

OUTD = "benchmarks/paper_eval/x1_passivity/out"


def _load(name):
    with open(os.path.join(_ROOT, OUTD, name)) as fh:
        return list(csv.DictReader(fh))


def main():
    apply_style()
    kconv = _load("k_convergence.csv")
    subs = _load("substep_sweep.csv")
    warm = _load("warm_start_ablation.csv")
    comp = _load("complementarity_residual.csv")
    e6a1 = _load("e6a1_block_condensation.csv")

    fig, (axA, axB, axC) = plt.subplots(1, 3, figsize=(7.1, 2.5))

    # ---- (a) R vs K ----------------------------------------------------
    oracle = next(float(r["ratio"]) for r in kconv if r["is_oracle"] == "True")
    pts = sorted(((int(r["K"]), float(r["ratio"])) for r in kconv
                  if r["solver"] == "xpbd" and r["is_oracle"] != "True"),
                 key=lambda p: p[0])
    axA.plot([p[0] for p in pts], [p[1] for p in pts], "-o",
             color=PALETTE["clamp_off"], label="XPBD ($S{=}1$)", ms=3.2)
    axA.axhline(oracle, ls=(0, (5, 2)), c="k", lw=1.0,
                label=f"implicit ref. {oracle:.3f}")
    axA.axhline(1.0, ls=":", c="0.45", lw=0.9)
    axA.text(1.1, 1.35, "incident-energy thr.", fontsize=5.6, color="0.35")
    # 4x8 equal-row point (32 row-evals as substeps): R=3.13
    r_4x8 = next(float(r["ratio_off"]) for r in subs if r["solver"] == "xpbd"
                 and r["scene"] == "shelf" and float(r["relax"]) == 0.7
                 and int(r["iters"]) == 4 and int(r["substeps"]) == 8)
    r_32x1 = next(p[1] for p in pts if p[0] == 32)
    # warm-start at 4x1: worse
    w41 = next(r for r in warm if r["scene"] == "shelf"
               and float(r["relax"]) == 0.7 and int(r["iters"]) == 4
               and int(r["substeps"]) == 1)
    # The diamond and the cross are SINGLE points, not series. The diamond spends
    # the same 32 row evaluations as substeps (S=8), so it does not lie on the
    # S=1 curve; the cross is the 4x1 cell re-run with carried duals and lands
    # within a factor 3 of the curve at K=4. Both were previously labelled by
    # annotate() text with xytext but no arrowprops, so the labels floated free
    # of their markers and the cross read as a point of the curve. Every label
    # here now carries a leader line to the thing it names.
    _leader = dict(arrowstyle="-", lw=0.55, color="0.45",
                   shrinkA=1.5, shrinkB=2.5)
    axA.plot([4], [r_4x8], "D", color=PALETTE["native"], ms=4.8, ls="none",
             zorder=5)
    axA.annotate("$4{\\times}8$ subs.\n(32 evals, injects)", (4, r_4x8),
                 fontsize=5.4, xytext=(3.6, 15.0), color=PALETTE["native"],
                 ha="right", va="center",
                 arrowprops=dict(_leader, color=PALETTE["native"]))
    axA.annotate("$32{\\times}1$\n(holds)", (32, r_32x1), fontsize=5.4,
                 xytext=(11.0, 0.62), color=PALETTE["clamp_off"], ha="center",
                 va="center", arrowprops=dict(_leader,
                                              color=PALETTE["clamp_off"]))
    axA.plot([4], [float(w41["R_on"])], "x", color="0.3", ms=5.5, mew=1.5,
             ls="none", zorder=5)
    axA.annotate("warm start $4{\\times}1$\n(worse than cold)",
                 (4, float(w41["R_on"])), fontsize=5.4, xytext=(1.05, 900.0),
                 color="0.3", va="center", arrowprops=dict(_leader))
    axA.set_xscale("log", base=2); axA.set_yscale("log")
    axA.set_xticks([1, 2, 4, 8, 16, 32], ["1", "2", "4", "8", "16", "32"])
    axA.set_xlabel("local iterations $K$"); axA.set_ylabel("$R$")
    axA.set_title("(a) injection vs iterations", fontsize=7.5)
    axA.legend(frameon=False, loc="upper right", fontsize=5.8)

    # ---- (b) complementarity residual vs K -----------------------------
    cp = sorted(((int(r["K"]), float(r["res_max"]) * 1e3, float(r["res_med"]) * 1e3)
                 for r in comp if r["solver"] == "xpbd" and r["scene"] == "shelf"),
                key=lambda p: p[0])
    axB.plot([p[0] for p in cp], [p[1] for p in cp], "-o",
             color=PALETTE["clamp_off"], ms=3.2, label="max gap")
    axB.plot([p[0] for p in cp], [p[2] for p in cp], "-s",
             color=PALETTE["native"], ms=3.0, label="median gap")
    axB.set_xscale("log", base=2); axB.set_yscale("log")
    axB.set_xlabel("local iterations $K$")
    axB.set_ylabel("end-substep gap [mm]")
    axB.set_title("(b) complementarity vs $K$", fontsize=7.5)
    axB.legend(frameon=False, loc="upper right", fontsize=6)

    # ---- (c) E6a-1 serial vs block -------------------------------------
    order = [(4, 1), (8, 2), (16, 4), (32, 1)]
    lab = ["4$\\times$1", "8$\\times$2", "16$\\times$4", "32$\\times$1"]
    roll = [r for r in e6a1 if r["kind"] == "rollout"]
    scstyle = {"shelf": PALETTE["clamp_off"], "ledge": PALETTE["variant"]}
    for scene in ("shelf", "ledge"):
        for mode, ls, mk in (("serial", "-", "o"), ("block", "--", "^")):
            ys = []
            for (it, su) in order:
                v = next((float(r["ratio"]) for r in roll if r["scene"] == scene
                          and r["mode"] == mode and int(r["iters"]) == it
                          and int(r["substeps"]) == su), None)
                ys.append(v)
            axC.plot(range(len(order)), ys, ls, marker=mk, ms=3.0,
                     color=scstyle[scene], lw=1.2,
                     label=f"{scene} {mode}")
    axC.axhline(1.0, ls=":", c="0.45", lw=0.9)
    axC.set_yscale("log")
    axC.set_xticks(range(len(order)), lab, fontsize=6)
    axC.set_xlabel("budget (iters $\\times$ substeps)")
    axC.set_ylabel("$R$")
    axC.set_title("(c) serial vs block (E6a-1)", fontsize=7.5)
    axC.legend(frameon=False, loc="upper right", fontsize=5.4, ncol=1)

    fig.tight_layout(pad=0.4)
    save(fig, "fig_operating_envelope.pdf")


if __name__ == "__main__":
    main()
