"""V6 — Apples-to-apples BCD vs coupled-AVBD benchmark.

Builds the same shelf scene (impactor + 2 probes) under each of:

  - reduced-static-support (BCD), substeps=1
  - reduced-static-support (BCD), substeps=8
  - reduced-coupled-avbd,         substeps=1
  - reduced-coupled-avbd,         substeps=8

For each cell, records mean step time (ms), peak |q| (µm), peak probe
|vy| (mm/s), and `cum_overlay_events_fired` (must be 0 for both paths).

The 2×2 layout disentangles the two factors the user flagged:

  - substep-overhead = compare BCD-substeps=1 to BCD-substeps=8
  - coupling-overhead = compare BCD-substeps=N to coupled-substeps=N

Writes a markdown table to stdout AND `docs/figures/bcd_vs_coupled_table.md`.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_one(*, mode: str, substeps: int, n_frames: int):
    from scenes.reduced_support_shelf import build_reduced_support_shelf
    bcd     = (mode == "bcd")
    coupled = (mode == "coupled")
    h = build_reduced_support_shelf(
        h=1.0 / 120.0,
        device="cpu",
        iterations=4,
        avbd_substeps=substeps,
        impactor_drop_height=0.02,
        impactor_v0=(0.0, -0.5, 0.0),
        impactor_mass=0.5,
        probe_mass=0.005,
        n_modes_global=6,
        n_modes_local=4,
        reduced_support_enabled=True,
        reduced_static_support=bcd,
        coupled_avbd=coupled,
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=5.0e-6,
    )
    w = h.world

    peak_q = 0.0
    peak_probe_vy = 0.0
    t0 = time.perf_counter()
    for _ in range(n_frames):
        w.step()
        peak_q = max(peak_q, float(np.linalg.norm(h.rs.q)))
        for desc_i in h.probe_indices:
            b = w._descs[desc_i].dcr_body
            peak_probe_vy = max(peak_probe_vy, abs(float(b.velocity[1])))
    dt = time.perf_counter() - t0
    mean_ms = 1000.0 * dt / n_frames

    if coupled:
        coupler_overlay = w.reduced_coupled_coupler.cum_overlay_events_fired
    elif bcd:
        coupler_overlay = w.reduced_support_coupler.cum_overlay_events_fired
    else:
        coupler_overlay = 0

    return {
        "mode":     mode,
        "substeps": substeps,
        "mean_ms":  mean_ms,
        "peak_q_m": peak_q,
        "peak_probe_vy_mps": peak_probe_vy,
        "overlay":  int(coupler_overlay),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument(
        "--out-md",
        default=str(ROOT / "docs" / "figures" / "bcd_vs_coupled_table.md"))
    args = ap.parse_args()

    cells = []
    for mode in ("bcd", "coupled"):
        for substeps in (1, 8):
            print(f"  {mode:>8s}  substeps={substeps} ...", flush=True)
            cells.append(_run_one(mode=mode, substeps=substeps,
                                  n_frames=args.frames))

    md = []
    md.append("# V6 — BCD vs Coupled-AVBD apples-to-apples")
    md.append(f"")
    md.append(f"Scene: shelf + impactor (-0.5 m/s) + 2 probes; "
              f"frames={args.frames}, iterations=4.")
    md.append("")
    md.append("| Mode | Substeps | Step (ms) | Peak |q| (µm) | "
              "Peak probe |vy| (mm/s) | Overlay events |")
    md.append("|:---|---:|---:|---:|---:|---:|")
    for c in cells:
        md.append(f"| {c['mode']:>7s} | {c['substeps']:>2d} "
                  f"| {c['mean_ms']:>8.2f} "
                  f"| {1e6*c['peak_q_m']:>8.2f} "
                  f"| {1e3*c['peak_probe_vy_mps']:>8.2f} "
                  f"| {c['overlay']:>2d} |")
    md.append("")

    # Compute and append cost breakdown.
    by_key = {(c['mode'], c['substeps']): c for c in cells}
    bcd_1 = by_key.get(('bcd', 1))
    bcd_8 = by_key.get(('bcd', 8))
    cou_1 = by_key.get(('coupled', 1))
    cou_8 = by_key.get(('coupled', 8))

    md.append("## Cost decomposition")
    md.append("")
    if bcd_1 and bcd_8:
        ratio = bcd_8['mean_ms'] / bcd_1['mean_ms']
        md.append(f"- Substep cost factor (BCD): "
                  f"{ratio:.2f}× going 1→8 substeps "
                  f"(ideal: 8× if linear in substeps).")
    if bcd_1 and cou_1:
        ratio = cou_1['mean_ms'] / bcd_1['mean_ms']
        md.append(f"- Coupling cost factor (substeps=1): "
                  f"{ratio:.2f}× going BCD→coupled at the same "
                  f"substep count.")
    if bcd_8 and cou_8:
        ratio = cou_8['mean_ms'] / bcd_8['mean_ms']
        md.append(f"- Coupling cost factor (substeps=8): "
                  f"{ratio:.2f}× going BCD→coupled at the same "
                  f"substep count.")

    out_path = Path(args.out_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md))
    print()
    for line in md:
        print(line)
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
