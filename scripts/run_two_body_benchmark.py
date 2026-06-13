#!/usr/bin/env python3
"""Benchmark + correctness log for the two-way reduced coupling.

Runs the cube-on-slab drop for both cube models (ABD affine, FEM modal) and for
single-cube and stacked configurations, logging the energy of EACH body (cube(s)
and slab) separately over time. Writes per-run CSVs and summary plots, and prints
a verification table.

Correctness is verified four independent ways (no reliance on a separate static
Newton, which can jump basins for tall ABD stacks):
  1. settles      — ‖v‖ → 0;
  2. passivity    — total mechanical energy monotone non-increasing;
  3. equilibrium  — static residual ‖∇V_el + ∇V_contact − f_grav‖ → 0 at rest;
  4. geometry     — each cube centroid rests at slab_top + (2i+1)·half.

    uv run python scripts/run_two_body_benchmark.py
    uv run python scripts/run_two_body_benchmark.py --n-cubes 3 --steps 6000
"""
from __future__ import annotations

import argparse
import csv
import os

import numpy as np

from dcr.twobody.multibody import build_stack

_OUT = "docs/figures"
_LOG = "docs/twobody_logs"
_SLAB_TOP = 0.025
_HALF = 0.05


def _centroid_y(sys, state, body_idx: int) -> float:
    z = sys.body_z(state, body_idx)
    b = sys.bodies[body_idx]
    if b.ndof == 12:                       # ABD: q[1] is world centroid y
        return float(z[1])
    return float(b.corner_rest[0, 1] + _HALF + z[1])  # FEM: drop + carrier disp


def run_case(kind: str, n_cubes: int, h: float, steps: int,
             damping: float, k_c: float):
    sys = build_stack(kind, n_cubes, damping=damping, k_c=k_c)
    st = sys.initial_state()
    rows = []
    totals = []
    max_pen = 0.0
    for i in range(steps):
        st = sys.step(st, h)
        e = sys.energy_breakdown(st)
        max_pen = max(max_pen, e["max_penetration"])
        totals.append(e["total"])
        row = {"t": i * h, "total": e["total"], "PE_grav": e["PE_grav"],
               "PE_contact": e["PE_contact"],
               "KE_slab": e["KE_body0"], "PEel_slab": e["PEel_body0"]}
        for c in range(n_cubes):
            row[f"KE_cube{c}"] = e[f"KE_body{c + 1}"]
            row[f"PEel_cube{c}"] = e[f"PEel_body{c + 1}"]
        rows.append(row)

    totals = np.array(totals)
    vmag = float(np.linalg.norm(st.v))
    residual = sys.static_residual(st)
    monotone_worst = float(np.diff(totals).max()) if len(totals) > 1 else 0.0
    heights = [_centroid_y(sys, st, b) for b in range(1, n_cubes + 1)]
    expected = [_SLAB_TOP + (2 * i + 1) * _HALF for i in range(n_cubes)]
    height_err = float(max(abs(a - b) for a, b in zip(heights, expected)))

    summary = {
        "kind": kind, "n_cubes": n_cubes, "vmag": vmag, "residual": residual,
        "monotone_worst": monotone_worst, "max_pen_mm": max_pen * 1e3,
        "height_err_mm": height_err * 1e3, "heights": heights, "expected": expected,
    }
    return sys, rows, summary


def write_csv(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def plot_single(rows_by_kind, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.4))
    for kind, rows in rows_by_kind.items():
        t = [r["t"] for r in rows]
        axs[0].plot(t, [r["KE_cube0"] for r in rows], label=f"{kind} cube KE")
        axs[0].plot(t, [r["KE_slab"] for r in rows], "--", label=f"{kind} slab KE")
        axs[1].plot(t, [r["PEel_cube0"] for r in rows], label=f"{kind} cube elastic")
        axs[1].plot(t, [r["PEel_slab"] for r in rows], "--", label=f"{kind} slab elastic")
    axs[0].set_title("Kinetic energy per body  (→ 0)")
    axs[1].set_title("Elastic strain energy per body  (→ static sag)")
    for ax in axs:
        ax.set_xlabel("t [s]"); ax.set_ylabel("energy [J]"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.suptitle("Two-way coupling — energy logged separately for cube and slab")
    fig.tight_layout(); fig.savefig(path, dpi=110)
    print(f"  saved {path}")


def plot_stack(sys, rows, kind, n_cubes, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.4))
    t = [r["t"] for r in rows]
    for c in range(n_cubes):
        axs[0].plot(t, [r[f"KE_cube{c}"] for r in rows], label=f"cube{c} KE")
        axs[1].plot(t, [r[f"PEel_cube{c}"] for r in rows], label=f"cube{c} elastic")
    axs[0].plot(t, [r["KE_slab"] for r in rows], "k--", label="slab KE")
    axs[1].plot(t, [r["PEel_slab"] for r in rows], "k--", label="slab elastic")
    axs[0].set_title(f"{kind} stack (n={n_cubes}) — KE per body (→ 0)")
    axs[1].set_title(f"{kind} stack (n={n_cubes}) — elastic PE per body")
    for ax in axs:
        ax.set_xlabel("t [s]"); ax.set_ylabel("energy [J]"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=110)
    print(f"  saved {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--steps", type=int, default=5000)
    ap.add_argument("--n-cubes", dest="n_cubes", type=int, default=3)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e5)
    args = ap.parse_args()

    print("=" * 78)
    print("TWO-WAY REDUCED COUPLING — BENCHMARK & VERIFICATION")
    print("=" * 78)
    hdr = f"{'case':<14}{'vmag':>10}{'residual':>11}{'mono_worst':>12}{'maxpen_mm':>11}{'height_err_mm':>15}"
    print(hdr)
    print("-" * len(hdr))

    # ---- single cube: ABD vs FEM (energy logged separately) ----
    single_rows = {}
    for kind in ("abd", "fem"):
        sys, rows, s = run_case(kind, 1, args.h, args.steps, args.damping, args.k_c)
        single_rows[kind] = rows
        write_csv(rows, f"{_LOG}/single_{kind}.csv")
        print(f"{kind+' single':<14}{s['vmag']:>10.1e}{s['residual']:>11.1e}"
              f"{s['monotone_worst']:>12.1e}{s['max_pen_mm']:>11.2f}{s['height_err_mm']:>15.3f}")
    plot_single(single_rows, f"{_OUT}/two_body_energy_per_body.png")

    # ---- stack: ABD and FEM ----
    for kind in ("abd", "fem"):
        sys, rows, s = run_case(kind, args.n_cubes, args.h, args.steps, args.damping, args.k_c)
        write_csv(rows, f"{_LOG}/stack_{kind}_n{args.n_cubes}.csv")
        print(f"{kind+f' stack n{args.n_cubes}':<14}{s['vmag']:>10.1e}{s['residual']:>11.1e}"
              f"{s['monotone_worst']:>12.1e}{s['max_pen_mm']:>11.2f}{s['height_err_mm']:>15.3f}")
        plot_stack(sys, rows, kind, args.n_cubes,
                   f"{_OUT}/stack_{kind}_n{args.n_cubes}.png")
        print(f"   {kind} rest heights {np.round(s['heights'],4)}  expected {np.round(s['expected'],4)}")

    print("-" * len(hdr))
    print("PASS criteria: vmag<1e-3, residual<1e-5, mono_worst<1e-5, "
          "maxpen<2mm, height_err<2mm")
    print(f"CSV logs in {_LOG}/ , plots in {_OUT}/")


if __name__ == "__main__":
    main()
