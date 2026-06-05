"""Benchmark sweep for Reduced-Coordinate AVBD Support v1.

Runs the shelf scene at AVBD iteration counts N ∈ {4, 8, 16, 32} with
both arms (bare reduced AVBD, reduced AVBD + bounded overlay), and
reports per-N metrics.

Decisive comparisons:
  1. Iteration invariance (headline win over post-fix DCR):
     `q_max_disp` and the impact-frame `d_max` should track within a
     few percent across N. Post-fix's distant kick swings with N.
  2. Bare-vs-overlay ratio: the spec predicts ω·h suppression of the
     bare arm — at h = 1/120 s and ω ≈ 838 rad/s, ratio ≈ 7.
  3. Energy invariant (item 3): cumulative |E_inj_realised| ≤ η · Σ E_src
     across the full run.
  4. Step-time regression from CUDA-graph disable when the hooks are
     wired (item 7 from the prioritised list).

Writes /tmp/reduced_support_benchmark.{csv,png}.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time as _t
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_support_shelf import build_reduced_support_shelf


def _run(*, iterations: int, frames: int, h: float, overlay: bool,
         reduced_support: bool = True) -> dict:
    handle = build_reduced_support_shelf(
        h=h,
        device="cpu",
        iterations=iterations,
        impactor_drop_height=0.30,
        impactor_v0=(0.0, -1.0, 0.0),
        overlay_enabled=overlay,
        restart_overlay_each_step=True,
        reduced_support_enabled=reduced_support,
    )
    w = handle.world
    c = w.reduced_support_coupler

    max_dv = 0.0
    max_q = 0.0
    max_d_bare = 0.0
    cum_inj_abs = 0.0
    cum_src = 0.0
    step_times = []
    n_iter_solves_total = 0
    cooldown_hits = 0

    for frame in range(frames):
        t0 = _t.perf_counter()
        w.step()
        step_times.append((_t.perf_counter() - t0) * 1000.0)

        if c is not None:
            if c.last_probe_dv.size > 0:
                max_dv = max(max_dv, float(np.max(np.abs(c.last_probe_dv))))
            if c.last_probe_d_max.size > 0:
                max_d_bare = max(max_d_bare, float(np.max(c.last_probe_d_max)))
            max_q = max(max_q, float(c.last_q_max_disp))
            cum_inj_abs += abs(c.last_E_inj_realised)
            cum_src += c.last_E_src
            n_iter_solves_total += int(c.last_n_iter_solves)
            if c.last_n_cooldown_active > 0:
                cooldown_hits += 1

    step_times = np.array(step_times)
    return {
        "iterations": iterations,
        "frames": frames,
        "h": h,
        "overlay": overlay,
        "reduced_support": reduced_support,
        "max_probe_dv": max_dv,
        "max_q_disp": max_q,
        "max_d_peak": max_d_bare,
        "cum_E_inj_abs": cum_inj_abs,
        "cum_E_src": cum_src,
        "ratio_inj_src": cum_inj_abs / max(cum_src, 1e-12),
        "step_ms_mean": float(step_times.mean()),
        "step_ms_p95": float(np.percentile(step_times, 95)),
        "step_ms_p99": float(np.percentile(step_times, 99)),
        "n_iter_solves_total": n_iter_solves_total,
        "cooldown_active_frames": cooldown_hits,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frames", type=int, default=120)
    p.add_argument("--h", type=float, default=1.0 / 120.0)
    p.add_argument("--iter-counts", default="4,8,16,32")
    p.add_argument("--csv", default="/tmp/reduced_support_benchmark.csv")
    p.add_argument("--png", default="/tmp/reduced_support_benchmark.png")
    args = p.parse_args(argv)

    iter_counts = [int(x) for x in args.iter_counts.split(",")]
    print(f"[benchmark] frames={args.frames} h={args.h} iters={iter_counts}\n")

    rows = []
    for it in iter_counts:
        for overlay in (False, True):
            print(f"  running iter={it} overlay={overlay}")
            r = _run(iterations=it, frames=args.frames, h=args.h,
                     overlay=overlay)
            r["arm"] = "overlay" if overlay else "bare"
            rows.append(r)
    # Sanity baseline: reduced-support OFF entirely.
    print(f"  running iter=4 reduced_support=OFF (baseline rigid AVBD)")
    r0 = _run(iterations=4, frames=args.frames, h=args.h, overlay=False,
              reduced_support=False)
    r0["arm"] = "no_reduced"
    rows.append(r0)

    # ---- Summary table ----
    print()
    print(f"{'iter':>5s} {'arm':>10s} {'max|Δv|':>9s} {'max q':>10s} "
          f"{'inj_cum':>9s} {'src_cum':>9s} {'ratio':>7s} "
          f"{'ms/mean':>9s} {'ms/p99':>9s}")
    for r in rows:
        print(f"{r['iterations']:5d} {r['arm']:>10s} "
              f"{r['max_probe_dv']:9.4f} {r['max_q_disp']:10.3e} "
              f"{r['cum_E_inj_abs']:9.3e} {r['cum_E_src']:9.3e} "
              f"{r['ratio_inj_src']:7.3f} {r['step_ms_mean']:9.2f} "
              f"{r['step_ms_p99']:9.2f}")

    # ---- Headline metrics ----
    bare_rows = [r for r in rows if r["arm"] == "bare"]
    overlay_rows = [r for r in rows if r["arm"] == "overlay"]
    if bare_rows and overlay_rows:
        bare_q = np.array([r["max_q_disp"] for r in bare_rows])
        overlay_q = np.array([r["max_q_disp"] for r in overlay_rows])
        bare_dv = np.array([r["max_probe_dv"] for r in bare_rows])
        overlay_dv = np.array([r["max_probe_dv"] for r in overlay_rows])

        def cv(x):
            return float(np.std(x) / max(np.mean(x), 1e-12))

        print("\n[iteration invariance]")
        print(f"  CV of max q_disp across N: bare={cv(bare_q):.3%}, "
              f"overlay={cv(overlay_q):.3%}")
        print(f"  CV of max |Δv| across N: bare={cv(bare_dv):.3%}, "
              f"overlay={cv(overlay_dv):.3%}")

        print("\n[overlay vs bare ratio]")
        for b, o in zip(bare_rows, overlay_rows):
            assert b["iterations"] == o["iterations"]
            r_dv = o["max_probe_dv"] / max(b["max_probe_dv"], 1e-12)
            r_q = o["max_q_disp"] / max(b["max_q_disp"], 1e-12)
            print(f"  iter={b['iterations']:3d}  Δv ratio = {r_dv:6.2f}  "
                  f"q_disp ratio = {r_q:6.2f}")

        no_red_rows = [r for r in rows if r["arm"] == "no_reduced"]
        if no_red_rows:
            nr = no_red_rows[0]
            bare4 = next(r for r in bare_rows if r["iterations"] == 4)
            print("\n[step-time regression — CUDA-graph disabled with hook]")
            print(f"  no-reduced     iter=4 mean = {nr['step_ms_mean']:.2f} ms")
            print(f"  bare-reduced   iter=4 mean = {bare4['step_ms_mean']:.2f} ms")
            print(f"  ratio (slowdown)            = "
                  f"{bare4['step_ms_mean'] / max(nr['step_ms_mean'], 1e-6):.2f}×")

    # CSV.
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\n[csv] {args.csv}")

    # Plot.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available")
        return 0
    iters = [r["iterations"] for r in bare_rows]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    ax = axes[0, 0]
    ax.plot(iters, [r["max_q_disp"] for r in bare_rows], "o-", label="bare")
    ax.plot(iters, [r["max_q_disp"] for r in overlay_rows], "s-", label="overlay")
    ax.set_xlabel("AVBD iterations"); ax.set_ylabel("max q_disp [m]")
    ax.set_yscale("log"); ax.legend(); ax.grid(True, alpha=0.3)
    ax.set_title("iteration invariance: max q_disp")
    ax = axes[0, 1]
    ax.plot(iters, [r["max_probe_dv"] for r in bare_rows], "o-", label="bare")
    ax.plot(iters, [r["max_probe_dv"] for r in overlay_rows], "s-", label="overlay")
    ax.set_xlabel("AVBD iterations"); ax.set_ylabel("max probe |Δv| [m/s]")
    ax.legend(); ax.grid(True, alpha=0.3)
    ax.set_title("overlay/bare distant response")
    ax = axes[1, 0]
    ax.plot(iters, [r["cum_E_inj_abs"] for r in overlay_rows], "o-",
            label="overlay: cum |E_inj|")
    ax.plot(iters, [r["cum_E_src"] for r in overlay_rows], "s-",
            label="overlay: cum E_src")
    ax.set_xlabel("AVBD iterations"); ax.set_ylabel("cumulative energy [J]")
    ax.set_yscale("log"); ax.legend(); ax.grid(True, alpha=0.3)
    ax.set_title("energy bookkeeping (cap working)")
    ax = axes[1, 1]
    ax.plot(iters, [r["step_ms_mean"] for r in bare_rows], "o-", label="bare-reduced")
    ax.plot(iters, [r["step_ms_mean"] for r in overlay_rows], "s-", label="overlay-reduced")
    if no_red_rows:
        ax.axhline(no_red_rows[0]["step_ms_mean"], color="gray", ls="--",
                   label="no reduced support")
    ax.set_xlabel("AVBD iterations"); ax.set_ylabel("step time [ms]")
    ax.legend(); ax.grid(True, alpha=0.3)
    ax.set_title("step-time regression")
    fig.suptitle(
        f"Reduced-Coordinate AVBD Support v1 — benchmark "
        f"(h={args.h:.5g}, {args.frames} frames)")
    fig.tight_layout()
    fig.savefig(args.png, dpi=110)
    print(f"[plot] {args.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
