"""Run the `--reduced-coupled-avbd` prototype scene.

This is the Python-side monolithic coupled reduced-coordinate AVBD
coupler — q is a first-class solve variable; each AVBD iteration solves
the full Schur-eliminated [Δx; Δq] system with the cross-coupling
ρ·J_x·J_q^T block; q is updated INSIDE the iteration loop, never via an
after-solve overlay or post-fix DCR kick.

Typical use:

    # Toy scene 1: one box resting on the compliant shelf.
    uv run python scripts/run_reduced_coupled_avbd.py --toy --frames 40

    # Shelf scene: impactor at center + distant probe.
    uv run python scripts/run_reduced_coupled_avbd.py --shelf --frames 60

    # Iteration sweep (proof of iteration stability).
    for n in 4 8 16 32; do
      uv run python scripts/run_reduced_coupled_avbd.py --toy \\
        --iterations $n --quiet --frames 40
    done
"""
from __future__ import annotations

import argparse
import sys
import time as _t
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_toy(args) -> None:
    from scenes.reduced_coupled_toy_minimum import build_toy_scene_1
    handle = build_toy_scene_1(
        h=args.h,
        device=args.device,
        iterations=args.iterations,
        avbd_substeps=args.substeps,
        mass=args.mass,
    )
    print(f"[scene] {handle.name}")
    print(f"  iterations = {args.iterations}  substeps = {args.substeps}")
    print(f"  box mass   = {args.mass} kg")
    print(f"  r          = {handle.rs.r}  (modal={handle.rs.r_modal})")
    _drive(handle, args, label="toy")


def _run_shelf(args) -> None:
    from scenes.reduced_support_shelf import build_reduced_support_shelf
    handle = build_reduced_support_shelf(
        h=args.h,
        device=args.device,
        iterations=args.iterations,
        n_modes_global=6, n_modes_local=4,
        impactor_drop_height=0.02,
        impactor_v0=(0.0, -0.5, 0.0),
        impactor_mass=0.5,
        probe_mass=0.005,
        reduced_support_enabled=True,
        coupled_avbd=True,
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=0.0,
        to_eigenbasis=(getattr(args, "reduced_basis", "synthetic") == "eigen"),
    )
    print(f"[scene] {handle.name}")
    print(f"  iterations = {args.iterations}  substeps = 1")
    print(f"  impactor (DCR idx) = {handle.impactor_idx}")
    print(f"  probes  (DCR idx)  = {handle.probe_indices}")
    _drive(handle, args, label="shelf")


def _drive(handle, args, *, label: str) -> None:
    w = handle.world
    c = w.reduced_coupled_coupler
    assert c is not None, "coupled coupler not attached"

    step_times: list[float] = []
    for f in range(args.frames):
        t0 = _t.perf_counter()
        w.step()
        step_ms = (_t.perf_counter() - t0) * 1000.0
        step_times.append(step_ms)
        if not args.quiet:
            print(
                f"  f={f:3d} t={w.time:.4f} "
                f"|q|={c.last_q_norm:.3e} "
                f"max_defl={c.last_max_support_deflection:.3e} "
                f"pen={c.last_contact_residual:.2e} "
                f"cond={c.last_Schur_condition_estimate:.2e} "
                f"dq={c.last_dq_norm:.2e} "
                f"overlay={c.cum_overlay_events_fired} "
                f"({step_ms:.1f} ms)"
            )

    print("\n[summary]")
    print(f"  scene                 = {label}")
    print(f"  iterations            = {args.iterations}")
    print(f"  frames                = {args.frames}")
    print(f"  final |q|             = {c.last_q_norm:.6e}")
    print(f"  final max deflection  = {c.last_max_support_deflection:.6e} m")
    print(f"  final penetration     = {c.last_contact_residual:.6e} m")
    print(f"  final cond(S)         = {c.last_Schur_condition_estimate:.3e}")
    print(f"  cum_overlay_events    = {c.cum_overlay_events_fired}")
    print(f"  mean step time        = {np.mean(step_times):.2f} ms")
    if c.cum_overlay_events_fired != 0:
        print("  WARNING: overlay events fired — coupled mode is supposed "
              "to keep this at 0.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Reduced-Coordinate Coupled AVBD prototype.")
    p.add_argument("--toy", action="store_true",
                   help="Run toy scene 1 (single box on shelf, no probes).")
    p.add_argument("--shelf", action="store_true",
                   help="Run the shelf scene with impactor + probes.")
    p.add_argument("--iterations", type=int, default=8,
                   help="AVBD iterations per substep.")
    p.add_argument("--substeps", type=int, default=4,
                   help="AVBD substeps per macro step (toy only).")
    p.add_argument("--frames", type=int, default=40)
    p.add_argument("--h", type=float, default=1.0 / 120.0)
    p.add_argument("--device", default="cpu")
    p.add_argument("--mass", type=float, default=0.05,
                   help="Box mass for toy scene (kg).")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress per-frame output.")
    p.add_argument("--reduced-basis", choices=["synthetic", "eigen"],
                   default="eigen",
                   help="Modal basis (eigen → diagonal IIR; physics equivalent).")
    args = p.parse_args(argv)

    if not args.toy and not args.shelf:
        args.toy = True

    if args.toy:
        _run_toy(args)
    if args.shelf:
        _run_shelf(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
