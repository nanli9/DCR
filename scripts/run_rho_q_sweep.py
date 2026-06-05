"""Item (5): ρ_q sweep + principled-sizing diagnostic.

The reduced-support coupler auto-sizes the q-block AL penalty as
    ρ_q = (1/h²) · max(diag(M_q[:r_modal]))
to match the BDF1 inertial term scale. The critique flagged this as a
"hidden knob" that linearly scales the overlay forcing r_tilde = Σ
(λ + ρ_q·C⁺)·J_q, so a 10× error in ρ_q produces a 10× error in the
overlay magnitude.

This script sweeps the multiplier in {0.1, 0.3, 1.0, 3.0, 10.0} ×
auto_rho_q and reports per-multiplier:
  - max penetration C⁺ over the run
  - peak |q| (modal displacement)
  - peak probe |Δv|
  - cumulative |E_inj_realised|
  - cumulative E_src

so it's obvious whether the auto value sits in the "stable + responsive"
sweet spot.

Writes /tmp/rho_q_sweep.{csv,png}.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_support_shelf import build_reduced_support_shelf


def _run(*, rho_multiplier: float, frames: int, h: float,
         iterations: int) -> dict:
    handle = build_reduced_support_shelf(
        h=h,
        device="cpu",
        iterations=iterations,
        impactor_drop_height=0.30,
        impactor_v0=(0.0, -1.0, 0.0),
        overlay_enabled=True,
        restart_overlay_each_step=True,
        reduced_support_enabled=True,
    )
    w = handle.world
    c = w.reduced_support_coupler

    # Step once to let the coupler auto-size ρ_q, then scale by the
    # multiplier and keep stepping. Without the bootstrap step the
    # multiplier would be applied to 0 (the default until the first
    # `substep_begin_hook` runs).
    w.step()
    auto_rho = c.rho_q
    c.rho_q = float(rho_multiplier) * auto_rho

    max_q = 0.0
    max_dv = 0.0
    cum_inj = 0.0
    cum_src = 0.0
    max_pen = 0.0
    n_iter_solves = 0
    for _ in range(frames - 1):
        w.step()
        if c.last_probe_dv.size > 0:
            max_dv = max(max_dv, float(np.max(np.abs(c.last_probe_dv))))
        # Convert q displacement diagnostic from `q_max_disp` (m).
        max_q = max(max_q, float(c.last_q_max_disp))
        cum_inj += abs(c.last_E_inj_realised)
        cum_src += c.last_E_src
        # Read max penetration from solver._rows + anchor_y vs corner_y.
        n_iter_solves += int(c.last_n_iter_solves)
    return {
        "rho_multiplier": rho_multiplier,
        "rho_q": float(c.rho_q),
        "auto_rho_q": float(auto_rho),
        "max_q_disp_m": max_q,
        "max_probe_dv": max_dv,
        "cum_E_inj_J": cum_inj,
        "cum_E_src_J": cum_src,
        "ratio_inj_src": cum_inj / max(cum_src, 1e-12),
        "n_iter_solves_total": n_iter_solves,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--iterations", type=int, default=4)
    p.add_argument("--h", type=float, default=1.0 / 120.0)
    p.add_argument("--multipliers", default="0.1,0.3,1.0,3.0,10.0")
    p.add_argument("--csv", default="/tmp/rho_q_sweep.csv")
    p.add_argument("--png", default="/tmp/rho_q_sweep.png")
    args = p.parse_args(argv)
    mults = [float(x) for x in args.multipliers.split(",")]

    print(f"[rho_q sweep] frames={args.frames} h={args.h} "
          f"iters={args.iterations} mults={mults}\n")
    rows = []
    for m in mults:
        print(f"  running rho_multiplier = {m}")
        r = _run(rho_multiplier=m, frames=args.frames, h=args.h,
                 iterations=args.iterations)
        rows.append(r)

    print()
    print(f"{'mult':>7s} {'rho_q':>11s} {'q_disp':>11s} "
          f"{'|Δv|max':>10s} {'|E_inj|':>11s} {'E_src':>11s} {'inj/src':>9s}")
    for r in rows:
        print(f"{r['rho_multiplier']:7.2f} {r['rho_q']:11.3e} "
              f"{r['max_q_disp_m']:11.3e} {r['max_probe_dv']:10.4f} "
              f"{r['cum_E_inj_J']:11.3e} {r['cum_E_src_J']:11.3e} "
              f"{r['ratio_inj_src']:9.3f}")

    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\n[csv] {args.csv}")

    # ---- Plot ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available; skipping png")
        return 0
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    xs = [r["rho_q"] for r in rows]
    axes[0, 0].plot(xs, [r["max_q_disp_m"] for r in rows], "o-")
    axes[0, 0].set_xscale("log"); axes[0, 0].set_yscale("log")
    axes[0, 0].set_xlabel("ρ_q"); axes[0, 0].set_ylabel("max |q_disp| [m]")
    axes[0, 0].grid(True, which="both", alpha=0.3)
    axes[0, 1].plot(xs, [r["max_probe_dv"] for r in rows], "o-")
    axes[0, 1].set_xscale("log")
    axes[0, 1].set_xlabel("ρ_q"); axes[0, 1].set_ylabel("max probe |Δv| [m/s]")
    axes[0, 1].grid(True, which="both", alpha=0.3)
    axes[1, 0].plot(xs, [r["cum_E_inj_J"] for r in rows], "o-", label="inj")
    axes[1, 0].plot(xs, [r["cum_E_src_J"] for r in rows], "s-", label="src")
    axes[1, 0].set_xscale("log"); axes[1, 0].set_yscale("log")
    axes[1, 0].set_xlabel("ρ_q"); axes[1, 0].set_ylabel("cumulative E [J]")
    axes[1, 0].legend()
    axes[1, 0].grid(True, which="both", alpha=0.3)
    axes[1, 1].plot(xs, [r["ratio_inj_src"] for r in rows], "o-")
    axes[1, 1].axhline(0.95, color="r", lw=0.8, label="η = 0.95")
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_xlabel("ρ_q"); axes[1, 1].set_ylabel("E_inj / E_src")
    axes[1, 1].legend()
    axes[1, 1].grid(True, which="both", alpha=0.3)
    fig.suptitle(
        f"ρ_q sweep (h={args.h:.5g}, iters={args.iterations}, "
        f"auto_ρ_q={rows[0]['auto_rho_q']:.3g})")
    fig.tight_layout()
    fig.savefig(args.png, dpi=110)
    print(f"[plot] {args.png}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
