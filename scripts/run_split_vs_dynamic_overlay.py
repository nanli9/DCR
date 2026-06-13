#!/usr/bin/env python3
"""ONE-WAY split vs TWO-WAY dynamic-q — the PI's question, answered on one plot.

Your PI's concern: the old static/dynamic SPLIT is *one-way* — the slab's modal
coordinate is quasi-static in the contact (no inertia, the energetic ring is
routed one-way into a render-only band), so energy flows rigid → slab and never
loops back. Approach B (the dynamic constraint) carries the FULL dynamic modal q
inside the contact, so the ring pushes the bodies back — genuinely two-way.

This runs the SAME scene through both and overlays the tell-tales:

  * SPLIT — `SplitOneWaySystem`  : slab modal q quasi-static, slab modal KE ≡ 0.
  * DYN   — `AVBDDynamicSystem`   : slab modal q dynamic (M_q/h² + D_q/h carried).
  * GT    — `MultiBodySystem`     : the monolithic dense-Newton reference (optional).

THE two-way signature is the slab's modal KINETIC energy: it is structurally 0 in
the split (the slab cannot ring), and nonzero — rising from the impact and
decaying as it feeds energy back — in the dynamic constraint. On `side_by_side`
the distant bystander cube also gets a real resonant kick only in the dynamic case.

Outputs (under docs/):
  * figures/split_vs_dynamic_<scene>_<kind>.png
  * data/split_vs_dynamic_<scene>_<kind>_<solver>.csv

    uv run python scripts/run_split_vs_dynamic_overlay.py --scene side_by_side
    uv run python scripts/run_split_vs_dynamic_overlay.py --scene stack --kind abd
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from dcr.twobody.multibody import build_side_by_side, build_stack
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem)

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "docs" / "data"
_FIG = _ROOT / "docs" / "figures"


def _scene(scene, kind, k_c, damping):
    if scene == "side_by_side":
        return build_side_by_side(kind, n_rest=3, impactor_drop=0.35,
                                  impactor_rho=2500.0, damping=damping, k_c=k_c)
    if scene == "stack":
        # a 3-cube tower dropped a hair above rest: it impacts, the slab rings,
        # and (only in the dynamic case) the ring wobbles the tower back.
        sysm = build_stack(kind, n_cubes=3, damping=damping, k_c=k_c, gap=0.02)
        return sysm, {"impactor_body": None, "rest_bodies": []}
    raise ValueError(scene)


def run(sys, info, h, steps):
    st = sys.initial_state()
    nb = len(sys.bodies)
    L = {k: [] for k in ("t", "slab_KE", "slab_PE", "cube_KE", "total",
                         "bystander_KE", "max_pen")}
    mid = (info["rest_bodies"][len(info["rest_bodies"]) // 2]
           if info.get("rest_bodies") else None)
    for s in range(steps):
        st = sys.step(st, h)
        e = sys.energy_breakdown(st)
        L["t"].append(s * h)
        L["slab_KE"].append(e["KE_body0"])
        L["slab_PE"].append(e["PEel_body0"])
        L["cube_KE"].append(sum(e[f"KE_body{i}"] for i in range(1, nb)))
        L["total"].append(e["total"])
        L["bystander_KE"].append(e[f"KE_body{mid}"] if mid is not None else np.nan)
        L["max_pen"].append(e["max_penetration"])
    out = {k: np.asarray(v) for k, v in L.items()}
    out["v_end"] = float(np.linalg.norm(st.v))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", choices=["side_by_side", "stack"],
                    default="side_by_side")
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--k-c", dest="k_c", type=float, default=4.0e5)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--with-gt", action="store_true")
    args = ap.parse_args()

    sysm, info = _scene(args.scene, args.kind, args.k_c, args.damping)
    solvers = {"SPLIT (1-way)": SplitOneWaySystem(sysm),
               "DYN (2-way)": AVBDDynamicSystem(sysm, n_outer=6, n_inner=3)}
    if args.with_gt:
        solvers["GT"] = sysm

    print(f"scene={args.scene} kind={args.kind} steps={args.steps}")
    results = {}
    for name, sv in solvers.items():
        L = run(sv, info, args.h, args.steps)
        results[name] = L
        tag = name.split()[0].lower()
        _DATA.mkdir(parents=True, exist_ok=True)
        with (_DATA / f"split_vs_dynamic_{args.scene}_{args.kind}_{tag}.csv"
              ).open("w", newline="") as f:
            w = csv.writer(f)
            cols = ["t", "slab_KE", "slab_PE", "cube_KE", "bystander_KE",
                    "total", "max_pen"]
            w.writerow(cols)
            for r in range(len(L["t"])):
                w.writerow([f"{L[c][r]:.8g}" for c in cols])
        by = L["bystander_KE"]
        by_peak = float(np.nanmax(by)) if not np.all(np.isnan(by)) else float("nan")
        print(f"  {name:14s} slab_modal_KE_peak={L['slab_KE'].max():.3e}J  "
              f"cube_KE_peak={L['cube_KE'].max():.3e}J  "
              f"bystander_KE_peak={by_peak:.3e}J  |v|end={L['v_end']:.2e}")

    _plot(results, args.scene, args.kind)


def _plot(results, scene, kind):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"SPLIT (1-way)": "#e0635a", "DYN (2-way)": "#34d399",
              "GT": "#222222"}
    has_by = scene == "side_by_side"
    fig, ax = plt.subplots(1, 3 if has_by else 2,
                           figsize=(16 if has_by else 11, 4.3))
    fig.suptitle(f"One-way SPLIT vs two-way DYNAMIC constraint  "
                 f"({scene}, {kind})", fontsize=13)
    for name, L in results.items():
        c = colors.get(name)
        ax[0].plot(L["t"], L["slab_KE"], label=name, color=c, lw=1.5)
        ax[1].plot(L["t"], L["cube_KE"], label=name, color=c, lw=1.2)
        if has_by:
            ax[2].plot(L["t"], L["bystander_KE"], label=name, color=c, lw=1.2)
    ax[0].set_title("Slab MODAL kinetic energy  ◀ the two-way signature\n"
                    "(≡0 for split: a quasi-static slab stores no kinetic energy)")
    ax[0].set_ylabel("KE_modal,slab [J]")
    ax[1].set_title("Rigid-body kinetic energy\n"
                    "(dynamic: slab rings & DAMPS the impact → settles fast;\n"
                    " split: lossless quasi-static spring absorbs nothing → rings on)")
    ax[1].set_ylabel("KE_cubes [J]")
    if has_by:
        ax[2].set_title("Distant BYSTANDER cube KE\n"
                        "(dynamic: one strong resonant kick;\n"
                        " split: weak repeated quasi-static nudges)")
        ax[2].set_ylabel("KE_bystander [J]")
    for a in ax:
        a.set_xlabel("t [s]")
        a.legend(fontsize=9)
        a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    _FIG.mkdir(parents=True, exist_ok=True)
    out = _FIG / f"split_vs_dynamic_{scene}_{kind}.png"
    fig.savefig(out, dpi=130)
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
