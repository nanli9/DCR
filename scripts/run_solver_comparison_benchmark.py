#!/usr/bin/env python3
"""GT (monolithic) vs AVBD vs XPBD on the dynamic modal contact constraint.

Runs the SAME scene through three solvers of the unified-dynamic-constraint
incremental potential (`dcr/twobody/position_based.py` + the `MultiBodySystem`
ground truth) and logs per-body energy so the two-way rigid↔modal loop and the
solver agreement are visible:

  * GT   — `MultiBodySystem`: dense Newton-to-convergence + penalty contact
           (the in-solver ground truth the HTML calls out).
  * AVBD — augmented-Lagrangian, fixed iteration budget (real-time target).
  * XPBD — compliant constraints, Gauss–Seidel (real-time target; FEM-modal).

Outputs (under docs/):
  * data/solver_cmp_<scene>_<kind>_<solver>.csv  — per-step energy time series
  * figures/solver_cmp_<scene>_<kind>.png        — 4-panel comparison

Examples:
    uv run python scripts/run_solver_comparison_benchmark.py --scene side_by_side --kind fem
    uv run python scripts/run_solver_comparison_benchmark.py --scene settle --kind abd --no-xpbd
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from dcr.twobody.multibody import build_side_by_side, build_stack
from dcr.twobody.position_based import AVBDDynamicSystem, XPBDDynamicSystem

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "docs" / "data"
_FIG = _ROOT / "docs" / "figures"


def _build_scene(scene: str, kind: str, k_c: float, damping: float):
    """Return (system, info). info marks impactor/rest bodies (side_by_side)."""
    if scene == "side_by_side":
        return build_side_by_side(kind, n_rest=3, impactor_drop=0.35,
                                  impactor_rho=2500.0, damping=damping, k_c=k_c)
    if scene == "settle":
        sysm = build_stack(kind, n_cubes=2, damping=damping, k_c=k_c, gap=0.01)
        return sysm, {"impactor_body": None, "rest_bodies": []}
    if scene == "stack":
        # a taller tower (3 cubes) dropped onto the slab — cube↔cube + cube↔slab
        # contacts, the slab rings under the settling stack.
        sysm = build_stack(kind, n_cubes=3, damping=damping, k_c=k_c, gap=0.02)
        return sysm, {"impactor_body": None, "rest_bodies": []}
    raise ValueError(scene)


def _impactor_y(sys, st, imp: int) -> float:
    z = sys.body_z(st, imp)
    b = sys.bodies[imp]
    return float(z[1] if b.ndof == 12 else b.corner_rest[0, 1] + 0.05 + z[1])


def run_solver(sys, info, h: float, steps: int) -> dict:
    """Step `sys` and return per-step logged arrays."""
    st = sys.initial_state()
    nb = len(sys.bodies)
    log = {f"KE_body{i}": [] for i in range(nb)}
    log["t"], log["total"], log["KE_slab"], log["PEel_slab"] = [], [], [], []
    log["KE_cubes"], log["max_pen"], log["impactor_y"] = [], [], []
    imp = info.get("impactor_body")
    for s in range(steps):
        st = sys.step(st, h)
        e = sys.energy_breakdown(st)
        log["t"].append(s * h)
        log["total"].append(e["total"])
        log["KE_slab"].append(e["KE_body0"])      # body 0 is always the slab
        log["PEel_slab"].append(e["PEel_body0"])
        log["KE_cubes"].append(sum(e[f"KE_body{i}"] for i in range(1, nb)))
        log["max_pen"].append(e["max_penetration"])
        log["impactor_y"].append(_impactor_y(sys, st, imp) if imp is not None
                                 else np.nan)
        for i in range(nb):
            log[f"KE_body{i}"].append(e[f"KE_body{i}"])
    out = {k: np.asarray(v) for k, v in log.items()}
    out["v_end"] = float(np.linalg.norm(st.v))
    out["state_end"] = st
    return out


def write_csv(path: Path, logs: dict, nb: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["t", "total", "KE_slab", "PEel_slab", "KE_cubes", "max_pen",
            "impactor_y"] + [f"KE_body{i}" for i in range(nb)]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in range(len(logs["t"])):
            w.writerow([f"{logs[c][r]:.8g}" for c in cols])


def make_plot(results: dict, scene: str, kind: str, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"GT": "#222222", "AVBD": "#fb923c", "XPBD": "#34d399"}
    fig, ax = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(f"Dynamic modal contact constraint — GT vs AVBD vs XPBD "
                 f"({scene}, {kind} cubes)", fontsize=13)

    for name, L in results.items():
        c = colors.get(name, None)
        t = L["t"]
        ax[0, 0].plot(t, L["total"], label=name, color=c, lw=1.4)
        ax[0, 1].plot(t, L["KE_slab"] + L["PEel_slab"], label=name, color=c, lw=1.2)
        ax[1, 0].plot(t, L["KE_cubes"], label=name, color=c, lw=1.2)
        ax[1, 1].plot(t, L["max_pen"] * 1e3, label=name, color=c, lw=1.2)

    ax[0, 0].set_title("Total mechanical energy (passivity: monotone ↓)")
    ax[0, 0].set_ylabel("E_total [J]")
    ax[0, 1].set_title("Slab modal energy  KE_q + ½qᵀK_q q  (the support's ring)")
    ax[0, 1].set_ylabel("E_modal [J]")
    ax[1, 0].set_title("Cube kinetic energy  (energy looped back from the ring)")
    ax[1, 0].set_ylabel("KE_cubes [J]")
    ax[1, 1].set_title("Max penetration  (AVBD's AL drives gap→0)")
    ax[1, 1].set_ylabel("penetration [mm]")
    for a in ax.ravel():
        a.set_xlabel("t [s]")
        a.legend(fontsize=9)
        a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    print(f"  wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", choices=["side_by_side", "settle", "stack"],
                    default="side_by_side")
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--k-c", dest="k_c", type=float, default=4.0e5)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--no-xpbd", action="store_true",
                    help="skip XPBD (required for abd cubes — not wired)")
    ap.add_argument("--avbd-outer", type=int, default=6)
    ap.add_argument("--avbd-inner", type=int, default=3)
    ap.add_argument("--xpbd-iters", type=int, default=25)
    args = ap.parse_args()

    sysm, info = _build_scene(args.scene, args.kind, args.k_c, args.damping)
    nb = len(sysm.bodies)

    solvers = {"GT": sysm,
               "AVBD": AVBDDynamicSystem(sysm, n_outer=args.avbd_outer,
                                         n_inner=args.avbd_inner)}
    if not args.no_xpbd and args.kind == "fem":
        solvers["XPBD"] = XPBDDynamicSystem(sysm, n_iters=args.xpbd_iters)
    elif args.kind == "abd" and not args.no_xpbd:
        print("note: XPBD path exercises FEM-modal bodies; skipping for abd.")

    results = {}
    print(f"scene={args.scene} kind={args.kind} h={args.h} steps={args.steps}")
    for name, sv in solvers.items():
        L = run_solver(sv, info, args.h, args.steps)
        results[name] = L
        tag = f"solver_cmp_{args.scene}_{args.kind}_{name}.csv"
        write_csv(_DATA / tag, L, nb)
        modal_peak = float((L["KE_slab"] + L["PEel_slab"]).max())
        cube_peak = float(L["KE_cubes"].max())
        print(f"  {name:5s}  modal_peak={modal_peak:.3e}J  "
              f"cube_peak={cube_peak:.3e}J  maxΔE={np.diff(L['total']).max():+.2e}  "
              f"|v|end={L['v_end']:.2e}  max_pen={L['max_pen'].max()*1e3:.3f}mm")

    # Rest-height agreement (AVBD/XPBD vs GT), final state.
    gt_end = results["GT"]["state_end"].z
    for name in solvers:
        if name == "GT":
            continue
        d = float(np.linalg.norm(results[name]["state_end"].z - gt_end))
        print(f"  ‖z_end({name}) − z_end(GT)‖ = {d:.3e}")

    make_plot(results, args.scene, args.kind,
              _FIG / f"solver_cmp_{args.scene}_{args.kind}.png")


if __name__ == "__main__":
    main()
