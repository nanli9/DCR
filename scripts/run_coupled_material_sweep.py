"""Material sweep benchmark for `--reduced-coupled-avbd`.

Re-runs the impactor-on-shelf scene across {steel, wood, plastic, soft}
after the BDF1 damping-gradient fix (audit-2), and at the substep count
V5 says is needed to see transient ringing (substeps=16+).

Records per material:
  - peak |q|        — max modal amplitude during the run
  - peak |qdot|     — max modal velocity
  - peak probe rise — max (probe_y - probe_y0) seen at distant probe
  - peak probe |vy| — max abs(probe velocity_y)
  - mean step time  — measured wall time / frames
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


MATERIALS = {
    "steel":   2.0e11,
    "wood":    1.0e10,
    "plastic": 1.0e9,
    "soft":    1.0e8,
}


def _run_one(*, material: str, youngs: float, substeps: int,
             n_frames: int, impactor_v0_y: float, mode: str = "coupled_iir_modal",
             support_response_gain: float = 1.0,
             modal_damping_scale: float = 1.0,
             to_eigenbasis: bool = False,
             scene_preset=None):
    """Run one material with the given knobs. `scene_preset` (ScenePreset
    or None) supplies geometry + impactor defaults; impactor_v0_y is
    applied as an override on top."""
    from scenes.reduced_support_shelf import build_reduced_support_shelf

    p = scene_preset
    shelf_length    = p.shelf_length    if p else 0.30
    shelf_width     = p.shelf_width     if p else 0.15
    shelf_thickness = p.shelf_thickness if p else 0.005
    drop_height     = p.impactor_drop_height if p else 0.02
    impactor_mass   = p.impactor_mass   if p else 0.5

    handle = build_reduced_support_shelf(
        h=1.0 / 120.0,
        device="cpu",
        iterations=4,
        avbd_substeps=substeps,
        shelf_length=shelf_length,
        shelf_width=shelf_width,
        shelf_thickness=shelf_thickness,
        impactor_drop_height=drop_height,
        impactor_v0=(0.0, impactor_v0_y, 0.0),
        impactor_mass=impactor_mass,
        probe_mass=0.005,
        n_modes_global=6,
        n_modes_local=4,
        youngs=youngs,
        reduced_support_enabled=(mode != "plain"),
        reduced_static_support=(mode == "coupled_modal_static"),
        coupled_avbd=(mode == "coupled_iir_modal"),
        dcr_postkick=(mode == "old_dcr_postkick"),
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=5.0e-6,
        modal_impedance_scale=support_response_gain,
        modal_damping_scale=modal_damping_scale,
        to_eigenbasis=to_eigenbasis,
    )
    w = handle.world
    c = w.reduced_coupled_coupler

    # Snapshot probe initial y for rise computation.
    probe_y0 = []
    for desc_i in handle.probe_indices:
        b = w._descs[desc_i].dcr_body
        probe_y0.append(float(b.position[1]))

    peak_q      = 0.0
    peak_qdot   = 0.0
    peak_rise   = 0.0
    peak_vy     = 0.0
    t0 = time.perf_counter()
    for _ in range(n_frames):
        w.step()
        peak_q    = max(peak_q,    float(np.linalg.norm(handle.rs.q)))
        if c is not None:
            peak_qdot = max(peak_qdot, c.last_qdot_norm)
        for k, desc_i in enumerate(handle.probe_indices):
            b = w._descs[desc_i].dcr_body
            rise = float(b.position[1]) - probe_y0[k]
            peak_rise = max(peak_rise, rise)
            peak_vy   = max(peak_vy, abs(float(b.velocity[1])))
    dt = time.perf_counter() - t0

    return {
        "material":     material,
        "E":            youngs,
        "step_ms":      1000.0 * dt / n_frames,
        "peak_q_um":    1e6 * peak_q,
        "peak_qdot_mm_s": 1e3 * peak_qdot,
        "probe_rise_um": 1e6 * peak_rise,
        "probe_vy_mm_s": 1e3 * peak_vy,
    }


def main():
    from scenes.presets import (
        PRESETS, DEMO_STYLES, get_scene, get_style,
        format_scene_table, format_style_table,
    )

    ap = argparse.ArgumentParser(
        description="Run a material sweep ({steel, wood, plastic, soft}) "
                    "inside a chosen scene preset + demo-style.")
    ap.add_argument("--list-scenes", action="store_true")
    ap.add_argument("--list-styles", action="store_true")
    ap.add_argument("--scene", choices=list(PRESETS.keys()),
                    default="research-baseline")
    ap.add_argument("--demo-style", choices=list(DEMO_STYLES.keys()),
                    default="honest")
    ap.add_argument("--frames",   type=int,   default=120)
    ap.add_argument("--substeps", type=int,   default=4)
    ap.add_argument("--v0-y",     type=float, default=None,
                    help="impactor initial downward velocity (m/s). "
                         "Default: scene's value.")
    ap.add_argument("--mode",
                    choices=["plain", "old_dcr_postkick",
                             "coupled_modal_static", "coupled_iir_modal"],
                    default="coupled_iir_modal")

    # Per-knob overrides (None → demo-style value).
    ap.add_argument("--support-response-gain", type=float, default=None)
    ap.add_argument("--modal-damping-scale", type=float, default=None)
    ap.add_argument("--reduced-basis", choices=["synthetic", "eigen"],
                    default="eigen",
                    help="Modal basis (eigen → diagonal IIR; physics equivalent).")

    args = ap.parse_args()

    if args.list_scenes:
        print(format_scene_table()); return
    if args.list_styles:
        print(format_style_table()); return

    scene = get_scene(args.scene)
    style = get_style(args.demo_style)
    v0_y = args.v0_y if args.v0_y is not None else scene.impactor_v0_y
    g    = args.support_response_gain   if args.support_response_gain   is not None else style.support_response_gain
    cz   = args.modal_damping_scale     if args.modal_damping_scale     is not None else style.modal_damping_scale

    print(f"[scene]  {scene.name}  (h_t={scene.shelf_thickness*1e3:.1f} mm, "
          f"L={scene.shelf_length*1e2:.0f} cm)")
    print(f"[style]  {style.name}  (g={g:.3g}, c_ζ={cz:.3g})")

    rows = []
    for name, E in MATERIALS.items():
        print(f"  {name:>8s}  E={E:.1e} Pa  substeps={args.substeps}  "
              f"mode={args.mode}  g={g:.3g} ...",
              flush=True)
        rows.append(_run_one(
            material=name, youngs=E, substeps=args.substeps,
            n_frames=args.frames, impactor_v0_y=v0_y, mode=args.mode,
            support_response_gain=g,
            modal_damping_scale=cz,
            to_eigenbasis=(args.reduced_basis == "eigen"),
            scene_preset=scene))

    print()
    print(f"# Material sweep — {args.mode}  scene={scene.name}  "
          f"(g={g:.3g}, c_ζ={cz:.3g})")
    print(f"  frames={args.frames}, substeps={args.substeps}, "
          f"impactor v0_y={v0_y} m/s, "
          f"h_t={scene.shelf_thickness*1e3:.1f} mm")
    print()
    print("| Material |   E (Pa) | Step (ms) | Peak |q| (µm) | "
          "Peak |qdot| (mm/s) | Probe rise (µm) | Probe |vy| (mm/s) |")
    print("|:---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        print(f"| {r['material']:>7s} "
              f"| {r['E']:.1e} "
              f"| {r['step_ms']:>7.2f} "
              f"| {r['peak_q_um']:>9.2f} "
              f"| {r['peak_qdot_mm_s']:>9.2f} "
              f"| {r['probe_rise_um']:>9.2f} "
              f"| {r['probe_vy_mm_s']:>9.2f} |")


if __name__ == "__main__":
    main()
