"""Item (2): rest-impactor pump test.

Place the impactor AT REST on the shelf (no drop, no initial velocity)
with the overlay ON.  Run 5 s of simulation and watch cumulative
E_overlay_injected.

Expected behavior under the current implementation:

    - If the high-pass on r_tilde is doing its job, the cumulative
      E_overlay_injected stays flat (Delta r_tilde near zero on steady
      contact).
    - If the high-pass is fooled (e.g. by AVBD iteration noise or by
      contact-flicker), the cumulative drifts upward and the energy cap
      from item (3) becomes load-bearing.

This is the cheap deciding experiment from the critique thread.  Also
runs the same scene with the impactor dropping (the normal A/B scene)
as a sanity check that the impulsive impact still excites the overlay.

Writes CSV + auto-emits a tiny matplotlib plot (if available) to
/tmp/rest_pump_test.{csv,png}.
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


def _run_one(*, drop_height: float, v0: tuple[float, float, float],
             iterations: int, frames: int, h: float,
             label: str) -> list[dict]:
    handle = build_reduced_support_shelf(
        h=h,
        device="cpu",
        iterations=iterations,
        impactor_drop_height=drop_height,
        impactor_v0=v0,
        overlay_enabled=True,
        restart_overlay_each_step=True,
        reduced_support_enabled=True,
    )
    world = handle.world

    rows: list[dict] = []
    cumulative_E_inj = 0.0
    cumulative_abs_E_inj = 0.0
    for frame in range(frames):
        world.step()
        c = world.reduced_support_coupler
        E_inj = float(c.last_E_overlay_injected) if c else 0.0
        cumulative_E_inj += E_inj
        cumulative_abs_E_inj += abs(E_inj)
        impactor_y = float(
            world._descs[handle.impactor_idx].dcr_body.position[1])
        probe0_y = float(
            world._descs[handle.probe_indices[0]].dcr_body.position[1])
        probe0_dv = (float(c.last_probe_dv[0])
                     if c and c.last_probe_dv.size > 0 else 0.0)
        rows.append({
            "label": label,
            "frame": frame,
            "t": world.time,
            "impactor_y": impactor_y,
            "probe0_y": probe0_y,
            "probe0_dv": probe0_dv,
            "E_overlay_injected": E_inj,
            "cumulative_E_overlay_injected": cumulative_E_inj,
            "cumulative_abs_E_overlay_injected": cumulative_abs_E_inj,
            "E_q": float(c.last_E_q) if c else 0.0,
            "q_max_disp": float(c.last_q_max_disp) if c else 0.0,
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frames", type=int, default=600,
                   help="Macro steps (default 600 ~ 5 s at h=1/120).")
    p.add_argument("--iterations", type=int, default=4)
    p.add_argument("--h", type=float, default=1.0 / 120.0)
    p.add_argument("--csv", default="/tmp/rest_pump_test.csv")
    p.add_argument("--png", default="/tmp/rest_pump_test.png")
    args = p.parse_args(argv)

    print(f"[pump test] frames={args.frames} h={args.h} iters={args.iterations}")
    print()

    # The shelf scene places the impactor at
    #   y = shelf_y_rest + impactor_drop_height
    # and the contact triggers when corner crosses shelf_y_rest=0.
    # half_extent default is 0.02; rest contact at y=0.02.  We park the
    # impactor a hair above (1e-4) so the first solve resolves the
    # tiny penetration into a steady normal force, not a hard impact.
    H_REST = 0.02 + 1e-4   # impactor half-extent + epsilon
    rest_rows = _run_one(
        drop_height=H_REST,
        v0=(0.0, 0.0, 0.0),
        iterations=args.iterations,
        frames=args.frames,
        h=args.h,
        label="rest",
    )

    # Drop the same impactor from 30 cm with a -1 m/s seed velocity.  This
    # is the standard A/B scene — should produce a clear impulse spike
    # somewhere in the first 0.6 s of simulation.
    drop_rows = _run_one(
        drop_height=0.30,
        v0=(0.0, -1.0, 0.0),
        iterations=args.iterations,
        frames=args.frames,
        h=args.h,
        label="drop",
    )

    rows = rest_rows + drop_rows
    Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[csv] {args.csv}")

    # ---- Summary ----
    def _stats(rs, name):
        e_cum = rs[-1]["cumulative_E_overlay_injected"]
        e_abs = rs[-1]["cumulative_abs_E_overlay_injected"]
        dv_max = max(abs(r["probe0_dv"]) for r in rs)
        q_max = max(r["q_max_disp"] for r in rs)
        dv_mean = float(np.mean([r["probe0_dv"] for r in rs]))
        n_nonzero_steps = sum(1 for r in rs if abs(r["E_overlay_injected"]) > 1e-12)
        print(f"  [{name}]")
        print(f"    cumulative  E_overlay_injected (signed) = {e_cum:+.4e}")
        print(f"    cumulative |E_overlay_injected|         = {e_abs:.4e}")
        print(f"    n_steps with nonzero injection           = {n_nonzero_steps} / {len(rs)}")
        print(f"    max |probe0_dv|                          = {dv_max:.4f} m/s")
        print(f"    mean probe0_dv                           = {dv_mean:+.4e}")
        print(f"    max q_max_disp                           = {q_max:.4e} m")
        return e_cum, e_abs, dv_max

    print("\n[summary]")
    rest_cum, rest_abs, rest_dv = _stats(rest_rows, "REST")
    drop_cum, drop_abs, drop_dv = _stats(drop_rows, "DROP")

    print()
    if rest_abs < 1e-6:
        verdict = ("OK  rest-impactor pump test: cumulative |E_overlay_injected| "
                   "< 1e-6 J.  The high-pass alone keeps a steady contact load "
                   "from re-exciting the overlay.  Energy cap (item 3) would be "
                   "belt-and-braces, not load-bearing.")
    elif rest_abs < drop_abs * 0.1:
        verdict = ("OK  rest |E_inject| is < 10% of the drop case.  The high-pass "
                   "is doing most of the work, but an energy cap will tighten "
                   "the bound further.")
    else:
        verdict = ("WARN  rest |E_inject| is comparable to or larger than the "
                   "drop case.  The high-pass is being fooled by AVBD iteration "
                   "noise or contact flicker -- energy cap is LOAD-BEARING.")
    print(verdict)

    # ---- Plot ----
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not available; skipping png")
        return 0
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    ax = axes[0]
    ax.plot([r["t"] for r in rest_rows],
            [r["cumulative_E_overlay_injected"] for r in rest_rows],
            label="rest", color="tab:blue")
    ax.plot([r["t"] for r in drop_rows],
            [r["cumulative_E_overlay_injected"] for r in drop_rows],
            label="drop", color="tab:orange")
    ax.set_ylabel("cum. E_overlay (signed) [J]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax = axes[1]
    ax.plot([r["t"] for r in rest_rows],
            [r["probe0_dv"] for r in rest_rows],
            label="rest", color="tab:blue")
    ax.plot([r["t"] for r in drop_rows],
            [r["probe0_dv"] for r in drop_rows],
            label="drop", color="tab:orange")
    ax.set_ylabel("probe0_dv [m/s]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax = axes[2]
    ax.plot([r["t"] for r in rest_rows],
            [r["impactor_y"] for r in rest_rows],
            label="rest impactor_y", color="tab:blue")
    ax.plot([r["t"] for r in drop_rows],
            [r["impactor_y"] for r in drop_rows],
            label="drop impactor_y", color="tab:orange")
    ax.set_ylabel("impactor y [m]")
    ax.set_xlabel("t [s]")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.suptitle(
        f"Rest-impactor pump test (h={args.h:.5g}, iters={args.iterations})\n"
        f"rest |E_inj| cum = {rest_abs:.2e} J | drop |E_inj| cum = {drop_abs:.2e} J")
    fig.tight_layout()
    fig.savefig(args.png, dpi=110)
    print(f"[plot] {args.png}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
