#!/usr/bin/env python3
"""Truck-bed road impact — the busy multi-pile scene — on AVBD and XPBD.

The `scenes/reduced_truck.py` layout brought into the `MultiBodySystem` (twobody)
framework: a flexible **truck-bed / road slab** (the modal support) carrying
several resting cargo piles of varying mass (a light crate, a 3-cube lumber
stack, a heavy crate, a 2-crate stack), with a HEAVY box dropped fast on bare
bed between them. The drop rings the bed and the ring rocks every distant pile —
two-way, through the support — which is exactly what the dynamic modal contact
constraint (Approach B) realizes inside the real-time position-based solvers.

Runs both real-time solvers (AVBD, XPBD) plus, with `--solvers`, the GT and the
one-way SPLIT for contrast. Logs every body's kinetic energy.

Outputs (docs/):
  * data/truck_bed_<kind>_<solver>.csv          — per-body KE / total / pen
  * figures/truck_bed_reaction_<kind>.png       — drive (box+bed) + per-pile wave
  * figures/truck_bed_solvers_<kind>.png        — total/bed/cargo across solvers

    uv run python scripts/run_truck_bed_benchmark.py
    uv run python scripts/run_truck_bed_benchmark.py --solvers
    uv run python scripts/run_truck_bed_benchmark.py --impactor-rho 9000 --impactor-v0 8
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from dcr.twobody.multibody import build_truck_bed
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem,
                                        XPBDDynamicSystem)

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "docs" / "data"
_FIG = _ROOT / "docs" / "figures"


def run(sys, h, steps):
    st = sys.initial_state()
    nb = len(sys.bodies)
    cols = ["t", "total", "max_pen", "KE_slab"] + [f"KE_body{i}" for i in range(1, nb)]
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


def _write_csv(L, nb, path):
    cols = ["t", "total", "max_pen", "KE_slab"] + [f"KE_body{i}" for i in range(1, nb)]
    _DATA.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in range(len(L["t"])):
            w.writerow([f"{L[c][r]:.8g}" for c in cols])


def _plot_reaction(L, info, kind):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    imp = info["impactor_body"]
    piles, labels = info["pile_bodies"], info["labels"]
    cmap = plt.get_cmap("turbo")
    t = L["t"]
    t_imp = t[int(np.argmax(L["KE_slab"] > 0.5))]
    xlim = (max(0.0, t_imp - 0.02), t_imp + 0.40)
    i0 = int(xlim[0] / (t[1] - t[0]))

    fig, ax = plt.subplots(1, 2, figsize=(15.5, 5.4))
    fig.suptitle(f"Truck-bed road impact ({kind}, dynamic AVBD): heavy box rings "
                 f"the bed → the ring ROCKS every cargo pile", fontsize=13)
    # left: the DRIVE — box lands & rings the bed (own large scale)
    ax[0].plot(t, L[f"KE_body{imp}"], lw=2.0, color="#e0635a", label="dropped box")
    ax[0].plot(t, L["KE_slab"], lw=1.6, color="#888", ls="--", label="bed modal KE (ring)")
    ax[0].set_title("Drive: box lands on bare bed → bed rings")
    ax[0].set_ylabel("kinetic energy [J]")
    # right: the REACTION — each cargo pile rocked by the ring (own small scale)
    peak = 1e-9
    for p, (idxs, lab) in enumerate(zip(piles, labels)):
        ke = sum(L[f"KE_body{bi}"] for bi in idxs)
        peak = max(peak, ke[i0:].max())
        ax[1].plot(t, ke, lw=1.8, color=cmap(0.12 + 0.72 * p / max(1, len(piles) - 1)),
                   label=lab)
    ax[1].plot(t, L["KE_slab"], lw=0.9, color="#bbb", ls="--", label="bed (ref)")
    ax[1].set_title("Reaction: the bed ring rocks every distant pile (own scale)")
    ax[1].set_ylabel("pile kinetic energy [J]")
    ax[1].set_ylim(-0.05 * peak, 1.3 * peak)
    for a in ax:
        a.set_xlabel("t [s]"); a.set_xlim(*xlim); a.legend(fontsize=9); a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    _FIG.mkdir(parents=True, exist_ok=True)
    out = _FIG / f"truck_bed_reaction_{kind}.png"
    fig.savefig(out, dpi=130); print(f"  wrote {out}")


def _plot_solvers(results, info, kind):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"AVBD": "#fb923c", "XPBD": "#34d399", "GT": "#222", "SPLIT": "#e0635a"}
    cargo = info["all_cargo"]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.3))
    fig.suptitle(f"Truck-bed impact across solvers ({kind})", fontsize=13)
    for name, L in results.items():
        c = colors.get(name)
        ax[0].plot(L["t"], L["total"], label=name, color=c, lw=1.3)
        ax[1].plot(L["t"], L["KE_slab"], label=name, color=c, lw=1.2)
        ax[2].plot(L["t"], sum(L[f"KE_body{b}"] for b in cargo), label=name, color=c, lw=1.2)
    ax[0].set_title("Total energy (passivity)")
    ax[1].set_title("Bed modal KE (two-way ring)")
    ax[2].set_title("Total cargo KE (the rocking)")
    for a in ax:
        a.set_xlabel("t [s]"); a.legend(fontsize=9); a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = _FIG / f"truck_bed_solvers_{kind}.png"
    fig.savefig(out, dpi=130); print(f"  wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--impactor-rho", dest="impactor_rho", type=float, default=6000.0)
    ap.add_argument("--impactor-v0", dest="impactor_v0", type=float, default=6.0)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e6)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--solvers", action="store_true",
                    help="also overlay GT / SPLIT (slower)")
    args = ap.parse_args()

    base, info = build_truck_bed(args.kind, impactor_rho=args.impactor_rho,
                                 impactor_v0=args.impactor_v0, k_c=args.k_c,
                                 damping=args.damping)
    imp = info["impactor_body"]
    imp_ke0 = 0.5 * base.bodies[imp].M[1, 1] * args.impactor_v0 ** 2
    print(f"truck-bed {args.kind}: {len(base.bodies)} bodies, {base.n} dof, "
          f"{len(base.contacts)} contacts | box rho={args.impactor_rho} "
          f"v0={args.impactor_v0} (impact KE ≈ {imp_ke0:.1f} J)")
    print(f"  piles: {info['labels']}")

    solvers = {"AVBD": AVBDDynamicSystem(base, n_outer=8, n_inner=4)}
    if args.kind == "fem":
        solvers["XPBD"] = XPBDDynamicSystem(base, n_iters=30)
    if args.solvers:
        solvers["GT"] = base
        solvers["SPLIT"] = SplitOneWaySystem(base)

    results = {}
    for name, sv in solvers.items():
        L = run(sv, args.h, args.steps)
        results[name] = L
        _write_csv(L, len(sv.bodies), _DATA / f"truck_bed_{args.kind}_{name.lower()}.csv")
        cargo_peak = max(sum(L[f"KE_body{b}"][40:] for b in info["all_cargo"]))
        print(f"  {name:5s} bed_KE_peak={L['KE_slab'].max():.3e}J  "
              f"cargo_KE_peak={cargo_peak:.3e}J  "
              f"maxΔE={np.diff(L['total']).max():+.2e}  "
              f"max_pen={L['max_pen'].max()*1e3:.3f}mm  |v|end={L['v_end']:.2e}")

    _plot_reaction(results["AVBD"], info, args.kind)
    if len(results) > 1:
        _plot_solvers(results, info, args.kind)


if __name__ == "__main__":
    main()
