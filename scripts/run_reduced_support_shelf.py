"""Run the Reduced-Coordinate AVBD Support Contact shelf experiment.

Decisive A/B for the v1 prototype (Section 20.1 of
`prompts/reduced_coordinate_avbd_support_dcr_extension.md`): does the
two-rate transient overlay restore a visible distant peak that the bare
coupled solve suppresses?

Typical usage:

    # Bare coupled solve (no overlay) — expect probe Δv suppressed by
    # ~ω·h (≈ 7x for h = 1/120 s and the default steel-like shelf).
    uv run python scripts/run_reduced_support_shelf.py \\
        --iterations 4 --no-overlay --frames 60 --csv /tmp/bare.csv

    # With overlay — expect visibly larger probe Δv at the impact frame.
    uv run python scripts/run_reduced_support_shelf.py \\
        --iterations 4 --overlay --frames 60 --csv /tmp/overlay.csv

    # Disable the reduced support entirely (sanity that existing
    # rigid-only AVBD behavior is preserved).
    uv run python scripts/run_reduced_support_shelf.py \\
        --no-reduced-support --frames 60
"""
from __future__ import annotations

import argparse
import csv
import sys
import time as _t
from pathlib import Path

import numpy as np

# Make the repo importable when run from the project root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_support_shelf import build_reduced_support_shelf
from dcr.rigid.energy import rigid_kinetic_energy


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Reduced-Coordinate AVBD Support shelf experiment.")
    p.add_argument("--iterations", type=int, default=4,
                   help="AVBD iterations per substep (try 4 / 8 / 16 / 32).")
    p.add_argument("--frames", type=int, default=60,
                   help="Macro steps to simulate.")
    p.add_argument("--h", type=float, default=1.0 / 120.0,
                   help="Macro timestep [s].")
    p.add_argument("--device", default="cpu",
                   help="Warp device (cpu or cuda:N).")
    p.add_argument("--overlay", dest="overlay", action="store_true",
                   default=True, help="Enable transient overlay (default).")
    p.add_argument("--no-overlay", dest="overlay", action="store_false",
                   help="Disable transient overlay (BARE coupled solve).")
    p.add_argument("--reduced-support", dest="reduced_support",
                   action="store_true", default=True,
                   help="Attach the reduced support coupler (default).")
    p.add_argument("--no-reduced-support", dest="reduced_support",
                   action="store_false",
                   help="Run the scene with rigid-only AVBD (sanity).")
    p.add_argument("--restart-overlay", dest="restart_overlay",
                   action="store_true", default=True,
                   help="DCR §9.3 restart option (default ON).")
    p.add_argument("--no-restart-overlay", dest="restart_overlay",
                   action="store_false",
                   help="Carry overlay tail across macro steps.")
    p.add_argument("--r-modal", type=int, default=8,
                   help="Vibration modes in basis.")
    p.add_argument("--r-local", type=int, default=8,
                   help="Static/patch modes in basis.")
    p.add_argument("--csv", default=None,
                   help="Write per-frame metrics to this CSV path.")
    p.add_argument("--plot", action="store_true",
                   help="Render a matplotlib summary at the end.")
    p.add_argument("--quiet", action="store_true",
                   help="Don't print per-frame stats to stdout.")
    args = p.parse_args(argv)

    handle = build_reduced_support_shelf(
        h=args.h,
        device=args.device,
        iterations=args.iterations,
        n_modes_global=args.r_modal,
        n_modes_local=args.r_local,
        overlay_enabled=args.overlay,
        restart_overlay_each_step=args.restart_overlay,
        reduced_support_enabled=args.reduced_support,
    )
    world = handle.world
    rs = handle.rs

    print(f"[scene] {handle.name}")
    print(f"  reduced_support_enabled = {args.reduced_support}")
    print(f"  overlay_enabled         = {args.overlay}")
    print(f"  iterations              = {args.iterations}")
    print(f"  device                  = {args.device}")
    print(f"  r_modal / r_local       = {args.r_modal} / {args.r_local}")
    print(f"  modal ω = {rs.modal_omega}")
    print(f"  ω*h     = {rs.modal_omega * args.h}")
    print(f"  impactor (DCR idx)  = {handle.impactor_idx}")
    print(f"  probes  (DCR idx)   = {handle.probe_indices}")

    n_probes = len(handle.probe_indices)
    rows: list[dict] = []

    for frame in range(args.frames):
        t0 = _t.perf_counter()
        world.step()
        step_ms = (_t.perf_counter() - t0) * 1000.0

        # Pull per-frame metrics.
        E_rigid = rigid_kinetic_energy(
            [d.dcr_body for d in world._descs])
        coupler = world.reduced_support_coupler
        if coupler is not None:
            d_max = coupler.last_probe_d_max.tolist()
            dv = coupler.last_probe_dv.tolist()
            q_max_disp = coupler.last_q_max_disp
            E_q = coupler.last_E_q
            E_overlay = coupler.last_E_overlay_injected
            n_iter_solves = coupler.last_n_iter_solves
            n_tracked = coupler.last_n_tracked_rows
        else:
            d_max = [0.0] * n_probes
            dv = [0.0] * n_probes
            q_max_disp = 0.0
            E_q = 0.0
            E_overlay = 0.0
            n_iter_solves = 0
            n_tracked = 0

        # Probe + impactor kinematics straight off the DCR-side bodies.
        probe_y = []
        probe_vy = []
        for idx in handle.probe_indices:
            b = world._descs[idx].dcr_body
            probe_y.append(float(b.position[1]))
            probe_vy.append(float(b.velocity[1]))
        impactor_y = float(
            world._descs[handle.impactor_idx].dcr_body.position[1])
        impactor_vy = float(
            world._descs[handle.impactor_idx].dcr_body.velocity[1])

        row = {
            "frame": frame,
            "t": world.time,
            "impactor_y": impactor_y,
            "impactor_vy": impactor_vy,
            "E_rigid": E_rigid,
            "E_q": E_q,
            "E_overlay_injected": E_overlay,
            "E_total": E_rigid + E_q,
            "q_max_disp": q_max_disp,
            "n_iter_solves": n_iter_solves,
            "n_tracked_rows": n_tracked,
            "step_ms": step_ms,
        }
        for i in range(n_probes):
            row[f"probe{i}_y"] = probe_y[i]
            row[f"probe{i}_vy"] = probe_vy[i]
            row[f"probe{i}_d_max"] = d_max[i] if i < len(d_max) else 0.0
            row[f"probe{i}_dv"] = dv[i] if i < len(dv) else 0.0
        rows.append(row)

        if not args.quiet:
            dv_str = " ".join(f"{v:+.4g}" for v in dv[:n_probes])
            d_str = " ".join(f"{d:.4g}" for d in d_max[:n_probes])
            print(
                f"  f={frame:3d} t={world.time:.4f} "
                f"impactor_y={impactor_y:+.4g} "
                f"q_max={q_max_disp:.3g} "
                f"d_max=[{d_str}] dv=[{dv_str}] "
                f"E_q={E_q:.3g} E_inj={E_overlay:+.3g} "
                f"({step_ms:.1f} ms)"
            )

    # ---- CSV ----
    if args.csv:
        Path(args.csv).parent.mkdir(parents=True, exist_ok=True)
        keys = list(rows[0].keys())
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"[csv] wrote {len(rows)} rows to {args.csv}")

    # ---- Summary ----
    print("\n[summary]")
    dv_arr = np.array([[r[f"probe{i}_dv"] for i in range(n_probes)]
                       for r in rows])
    dmax_arr = np.array([[r[f"probe{i}_d_max"] for i in range(n_probes)]
                         for r in rows])
    print(f"  max |d_max| over run (per probe): "
          f"{[f'{dmax_arr[:,i].max():.4g}' for i in range(n_probes)]}")
    print(f"  max  dv   over run (per probe):   "
          f"{[f'{dv_arr[:,i].max():.4g}' for i in range(n_probes)]}")
    print(f"  sum |overlay_injected| over run:  "
          f"{sum(abs(r['E_overlay_injected']) for r in rows):.4g}")

    # ---- Plot ----
    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("[plot] matplotlib not available, skipping")
            return 0
        fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
        ts = [r["t"] for r in rows]
        ax = axes[0]
        for i in range(n_probes):
            ax.plot(ts, [r[f"probe{i}_d_max"] for r in rows],
                    label=f"probe{i} d_max")
        ax.set_ylabel("probe d_max [m]")
        ax.legend()
        ax = axes[1]
        for i in range(n_probes):
            ax.plot(ts, [r[f"probe{i}_dv"] for r in rows],
                    label=f"probe{i} Δv")
        ax.set_ylabel("probe Δv [m/s]")
        ax.legend()
        ax = axes[2]
        ax.plot(ts, [r["E_rigid"] for r in rows], label="E_rigid")
        ax.plot(ts, [r["E_q"] for r in rows], label="E_q")
        ax.plot(ts, [r["E_total"] for r in rows], label="E_total")
        ax.set_xlabel("t [s]")
        ax.set_ylabel("energy [J]")
        ax.legend()
        title = ("overlay on" if args.overlay else "overlay OFF (bare)")
        if not args.reduced_support:
            title = "reduced support OFF"
        fig.suptitle(f"Reduced AVBD Shelf — {title} "
                     f"(iters={args.iterations}, h={args.h:.5g})")
        fig.tight_layout()
        plt.show()

    return 0


if __name__ == "__main__":
    sys.exit(main())
