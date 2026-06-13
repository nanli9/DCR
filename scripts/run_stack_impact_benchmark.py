#!/usr/bin/env python3
"""Stack reaction to a heavy fast box — per-cube energy log + figure.

Drops a heavy box (fast initial velocity) onto a 3-cube stack and logs each
body's kinetic energy so the impact wave travelling top → bottom through the
tower, and the slab ring, are visible. Optionally overlays solvers.

Outputs (docs/):
  * data/stack_impact_<kind>_<solver>.csv          — per-body KE time series
  * figures/stack_impact_reaction_<kind>.png       — per-cube wave (dynamic AVBD)
  * figures/stack_impact_solvers_<kind>.png        — total/slab/box across solvers

    uv run python scripts/run_stack_impact_benchmark.py
    uv run python scripts/run_stack_impact_benchmark.py --impactor-rho 8000 --impactor-v0 8 --k-c 4e6 --h 2e-4
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from dcr.twobody.multibody import build_stack_impact
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem,
                                        XPBDDynamicSystem)

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "docs" / "data"
_FIG = _ROOT / "docs" / "figures"


def run(sys, info, h, steps):
    st = sys.initial_state()
    nb = len(sys.bodies)
    cols = ["t", "total", "max_pen", "KE_slab"] + \
           [f"KE_body{i}" for i in range(1, nb)]
    L = {c: [] for c in cols}
    for s in range(steps):
        st = sys.step(st, h)
        e = sys.energy_breakdown(st)
        L["t"].append(s * h)
        L["total"].append(e["total"])
        L["max_pen"].append(e["max_penetration"])
        L["KE_slab"].append(e["KE_body0"])
        for i in range(1, nb):
            L[f"KE_body{i}"].append(e[f"KE_body{i}"])
    out = {c: np.asarray(v) for c, v in L.items()}
    out["v_end"] = float(np.linalg.norm(st.v))
    return out


def _plot_wave(L, info, kind, h):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    stack = info["stack_bodies"]
    imp = info["impactor_body"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(L["t"], L[f"KE_body{imp}"], lw=2.0, color="#e0635a", label="box (impactor)")
    labels = ([f"stack #{k} (bottom)" if k == 0 else
               (f"stack #{k} (top)" if bi == stack[-1] else f"stack #{k}")
               for k, bi in enumerate(stack)])
    cmap = plt.get_cmap("viridis")
    for k, bi in enumerate(stack):
        ax.plot(L["t"], L[f"KE_body{bi}"], lw=1.5,
                color=cmap(0.15 + 0.7 * k / max(1, len(stack) - 1)), label=labels[k])
    ax.plot(L["t"], L["KE_slab"], lw=1.5, color="#888", ls="--", label="slab (modal)")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("kinetic energy [J]")
    ax.set_title(f"Stack reaction to a heavy fast box ({kind}, dynamic AVBD)\n"
                 "box slams stack → stiff cubes transmit → slab rings → "
                 "energy returns to the box (two-way)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)
    # zoom the x-axis to the first ~120 ms where the wave is
    t_imp = L["t"][int(np.argmax(L[f"KE_body{stack[-1]}"] > 1e-3))]
    ax.set_xlim(max(0, t_imp - 0.01), t_imp + 0.12)
    fig.tight_layout()
    _FIG.mkdir(parents=True, exist_ok=True)
    out = _FIG / f"stack_impact_reaction_{kind}.png"
    fig.savefig(out, dpi=130)
    print(f"  wrote {out}")


def _plot_solvers(results, info, kind):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"AVBD": "#fb923c", "GT": "#222", "XPBD": "#34d399",
              "SPLIT": "#e0635a"}
    imp = info["impactor_body"]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.3))
    fig.suptitle(f"Heavy-box-on-stack across solvers ({kind})", fontsize=13)
    for name, L in results.items():
        c = colors.get(name)
        ax[0].plot(L["t"], L["total"], label=name, color=c, lw=1.3)
        ax[1].plot(L["t"], L["KE_slab"], label=name, color=c, lw=1.2)
        ax[2].plot(L["t"], L[f"KE_body{imp}"], label=name, color=c, lw=1.2)
    ax[0].set_title("Total energy (passivity)")
    ax[1].set_title("Slab modal KE (two-way ring)")
    ax[2].set_title("Box KE (bounce-back)")
    for a in ax:
        a.set_xlabel("t [s]"); a.legend(fontsize=9); a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = _FIG / f"stack_impact_solvers_{kind}.png"
    fig.savefig(out, dpi=130)
    print(f"  wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--n-stack", dest="n_stack", type=int, default=3)
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--impactor-rho", dest="impactor_rho", type=float, default=5000.0)
    ap.add_argument("--impactor-v0", dest="impactor_v0", type=float, default=5.0)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e6)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--solvers", action="store_true",
                    help="also overlay GT / SPLIT / XPBD (slower)")
    args = ap.parse_args()

    def build():
        return build_stack_impact(args.kind, n_stack=args.n_stack,
                                  impactor_rho=args.impactor_rho,
                                  impactor_v0=args.impactor_v0, k_c=args.k_c,
                                  damping=args.damping)

    base, info = build()
    imp_ke0 = 0.5 * base.bodies[info["impactor_body"]].M[1, 1] * args.impactor_v0 ** 2
    print(f"kind={args.kind} stack={args.n_stack} box: rho={args.impactor_rho} "
          f"v0={args.impactor_v0} m/s  (impact KE ≈ {imp_ke0:.1f} J)")

    solvers = {"AVBD": AVBDDynamicSystem(base, n_outer=8, n_inner=4)}
    if args.solvers:
        solvers["GT"] = base
        solvers["SPLIT"] = SplitOneWaySystem(base)
        if args.kind == "fem":
            solvers["XPBD"] = XPBDDynamicSystem(base, n_iters=30)

    results = {}
    for name, sv in solvers.items():
        L = run(sv, info, args.h, args.steps)
        results[name] = L
        _DATA.mkdir(parents=True, exist_ok=True)
        nb = len(sv.bodies)
        cols = ["t", "total", "max_pen", "KE_slab"] + \
               [f"KE_body{i}" for i in range(1, nb)]
        with (_DATA / f"stack_impact_{args.kind}_{name.lower()}.csv").open(
                "w", newline="") as f:
            w = csv.writer(f); w.writerow(cols)
            for r in range(len(L["t"])):
                w.writerow([f"{L[c][r]:.8g}" for c in cols])
        box_key = f"KE_body{info['impactor_body']}"
        print(f"  {name:5s} slab_KE_peak={L['KE_slab'].max():.3e}J  "
              f"box_KE_end={L[box_key][-1]:.3e}J  "
              f"maxΔE={np.diff(L['total']).max():+.2e}  max_pen={L['max_pen'].max()*1e3:.2f}mm  "
              f"|v|end={L['v_end']:.2e}")

    _plot_wave(results["AVBD"], info, args.kind, args.h)
    if args.solvers:
        _plot_solvers(results, info, args.kind)


if __name__ == "__main__":
    main()
