#!/usr/bin/env python3
"""Headless dinner_table recorder.

Steps the scene without the viewer and dumps every body's (position,
orientation, linear velocity, angular velocity) per timestep to a CSV.
Use this to debug body-level behavior (e.g., the fork tilting up at one
end on settle).

`--projection {off,normal,normal-tangent}` toggles the contact-compatible
null-space projection (see `dcr/dcr/contact_projection.py`).

`--sweep` runs the full doc §17 experiment table: eta × projection grid
and writes a summary CSV with max tilt / yaw / mean rho / removed modal
energy per cell.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.run_scenes_avbd import build_dinner_table_scene


PROJECTION_MODES = ("off", "normal", "normal-tangent")
SWEEP_ETAS = (0.0, 0.3, 0.6, 0.99)
SWEEP_PROJECTIONS = ("off", "normal", "normal-tangent")


def _apply_projection_mode(coupler, mode: str) -> None:
    """Set the coupler's projection flags from a CLI mode string."""
    if mode == "off":
        coupler.projection_enabled = False
        coupler.projection_use_tangent_rows = False
    elif mode == "normal":
        coupler.projection_enabled = True
        coupler.projection_use_tangent_rows = False
    elif mode == "normal-tangent":
        coupler.projection_enabled = True
        coupler.projection_use_tangent_rows = True
    else:
        raise ValueError(f"unknown projection mode {mode!r}")


def _body_up_axis_world(q: np.ndarray) -> np.ndarray:
    """World-frame body-up axis (body's +y direction) for a (w,x,y,z) quat."""
    w, x, y, z = q
    # Second column of rotation matrix R(q): R @ [0,1,0].
    return np.array([
        2.0 * (x * y - z * w),
        1.0 - 2.0 * (x * x + z * z),
        2.0 * (y * z + x * w),
    ])


def _tilt_deg(q: np.ndarray) -> float:
    """Angle between the body's +y axis and world +y, in degrees."""
    up_w = _body_up_axis_world(q)
    cos = float(np.clip(up_w[1], -1.0, 1.0))
    return math.degrees(math.acos(cos))


def _run_once(
    *,
    out_csv: Path,
    steps: int,
    record_every: int,
    h: float,
    eta: float,
    beta: float,
    modal_decay_gamma: float,
    mesh_resolution: str,
    device: str,
    avbd_iters: int,
    util_mass: float,
    util_half_y: float,
    projection: str,
) -> dict:
    """Run a single recording. Returns the cell-level summary dict."""
    world, coupler, boxes, mesh, title = build_dinner_table_scene(
        device=device, h=h, eta=eta, beta=beta,
        causal_gating=True, modal_decay_gamma=modal_decay_gamma,
        mesh_resolution=mesh_resolution,
        util_mass=util_mass,
        util_half_y=util_half_y,
    )
    world._solver.iterations = int(avbd_iters)
    _apply_projection_mode(coupler, projection)

    # Per-utensil tilt and yaw_omega trackers; the artifact we're chasing
    # is specifically on the forks/knives (render_kind ∈ {"fork","knife"}).
    util_idxs = [sb.body_idx for sb in boxes
                 if sb.render_kind in ("fork", "knife", "spoon")]
    max_tilt_deg = 0.0
    max_yaw_omega = 0.0
    rho_sum = 0.0
    rho_count = 0
    proj_fired_total = 0
    proj_skipped_total = 0
    E_proj_removed_total = 0.0
    E_modal_injected_total = 0.0

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "step", "t", "body_idx", "name", "kind",
            "px", "py", "pz",
            "qw", "qx", "qy", "qz",
            "vx", "vy", "vz",
            "wx", "wy", "wz",
            "tilt_deg",
        ])

        def _emit(step_i: int):
            t = float(world.time)
            for sb in boxes:
                db = world._descs[sb.body_idx].dcr_body
                p = db.position
                q = db.orientation
                vel6 = db.velocity
                vl = (float(vel6[0]), float(vel6[1]), float(vel6[2]))
                wa = (float(vel6[3]), float(vel6[4]), float(vel6[5]))
                tilt = _tilt_deg(q)
                w.writerow([
                    step_i, f"{t:.6f}",
                    sb.body_idx, sb.name, sb.render_kind,
                    f"{p[0]:.6f}", f"{p[1]:.6f}", f"{p[2]:.6f}",
                    f"{q[0]:.6f}", f"{q[1]:.6f}", f"{q[2]:.6f}", f"{q[3]:.6f}",
                    f"{vl[0]:.6f}", f"{vl[1]:.6f}", f"{vl[2]:.6f}",
                    f"{wa[0]:.6f}", f"{wa[1]:.6f}", f"{wa[2]:.6f}",
                    f"{tilt:.6f}",
                ])

        _emit(0)
        for step_i in range(1, steps + 1):
            world.step()
            # Sample per-step (NOT just every record_every) so the max
            # captures transient peaks.
            for sb_idx in util_idxs:
                db = world._descs[sb_idx].dcr_body
                tilt = _tilt_deg(db.orientation)
                if tilt > max_tilt_deg:
                    max_tilt_deg = tilt
                # Yaw_omega is the world-y component of angular velocity —
                # rotation about the contact normal.
                yaw = abs(float(db.velocity[4]))
                if yaw > max_yaw_omega:
                    max_yaw_omega = yaw
            # Aggregate projection diagnostics.
            rhos = coupler.last_projection_rho
            if rhos:
                rho_sum += sum(rhos)
                rho_count += len(rhos)
            proj_fired_total += coupler.last_projection_fired
            proj_skipped_total += coupler.last_projection_skipped
            E_proj_removed_total += coupler.last_E_projection_removed
            E_modal_injected_total += coupler.last_E_modal_injected
            if step_i % record_every == 0:
                _emit(step_i)

    mean_rho = (rho_sum / rho_count) if rho_count > 0 else 1.0
    return dict(
        out_csv=str(out_csv),
        eta=eta,
        projection=projection,
        max_tilt_deg=max_tilt_deg,
        max_yaw_omega=max_yaw_omega,
        mean_rho=mean_rho,
        projection_fired=proj_fired_total,
        projection_skipped=proj_skipped_total,
        E_modal_injected_total=E_modal_injected_total,
        E_projection_removed_total=E_proj_removed_total,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="benchmark/runs/dinner_table_trace.csv")
    ap.add_argument("--steps", type=int, default=2000,
                    help="number of solver steps to record")
    ap.add_argument("--record-every", type=int, default=10,
                    help="emit a row every N solver steps")
    ap.add_argument("--h", type=float, default=1e-3)
    ap.add_argument("--eta", type=float, default=0.6)
    ap.add_argument("--beta", type=float, default=0.6)
    ap.add_argument("--modal-decay-gamma", type=float, default=0.99)
    ap.add_argument("--mesh-resolution", default="medium")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--avbd-iters", type=int, default=4)
    ap.add_argument("--util-mass", type=float, default=0.06)
    ap.add_argument("--util-half-y", type=float, default=0.005)
    ap.add_argument("--projection", choices=PROJECTION_MODES,
                    default="normal",
                    help="contact-compatible null-space projection mode "
                         "(see prompts/dcr_patch_kick_nullspace_projection_fix.md)")
    ap.add_argument("--sweep", action="store_true",
                    help="run the full doc §17 grid (overrides --eta and "
                         "--projection; writes per-cell CSVs alongside --out "
                         "and one summary CSV).")
    args = ap.parse_args()

    out = Path(args.out)

    if not args.sweep:
        info = _run_once(
            out_csv=out,
            steps=args.steps,
            record_every=args.record_every,
            h=args.h,
            eta=args.eta,
            beta=args.beta,
            modal_decay_gamma=args.modal_decay_gamma,
            mesh_resolution=args.mesh_resolution,
            device=args.device,
            avbd_iters=args.avbd_iters,
            util_mass=args.util_mass,
            util_half_y=args.util_half_y,
            projection=args.projection,
        )
        print(f"wrote {out}")
        print(f"  bodies: dinner_table; steps={args.steps}")
        print(f"  projection={info['projection']} eta={info['eta']:.2f}")
        print(f"  max_tilt_deg={info['max_tilt_deg']:.3f}  "
              f"max_yaw_omega={info['max_yaw_omega']:.4f}")
        print(f"  mean_rho={info['mean_rho']:.3f}  "
              f"proj_fired={info['projection_fired']}  "
              f"proj_skipped={info['projection_skipped']}")
        print(f"  E_modal_injected={info['E_modal_injected_total']:.4e} J  "
              f"E_proj_removed={info['E_projection_removed_total']:.4e} J")
        return 0

    # Sweep mode: ignore --eta / --projection, run the grid.
    out_dir = out if out.suffix == "" else out.parent
    out_dir = out_dir if out_dir != Path(".") else Path("benchmark/runs/dt_sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.csv"
    rows = []
    for eta in SWEEP_ETAS:
        for projection in SWEEP_PROJECTIONS:
            cell_csv = out_dir / f"eta{eta:.2f}_proj-{projection}.csv"
            print(f"[sweep] eta={eta:.2f}  projection={projection}  → {cell_csv.name}")
            info = _run_once(
                out_csv=cell_csv,
                steps=args.steps,
                record_every=args.record_every,
                h=args.h,
                eta=eta,
                beta=args.beta,
                modal_decay_gamma=args.modal_decay_gamma,
                mesh_resolution=args.mesh_resolution,
                device=args.device,
                avbd_iters=args.avbd_iters,
                util_mass=args.util_mass,
                util_half_y=args.util_half_y,
                projection=projection,
            )
            rows.append(info)
            print(f"  max_tilt_deg={info['max_tilt_deg']:.3f}  "
                  f"mean_rho={info['mean_rho']:.3f}  "
                  f"E_inj={info['E_modal_injected_total']:.3e} J  "
                  f"E_proj_removed={info['E_projection_removed_total']:.3e} J")
    with open(summary_path, "w", newline="") as f:
        ww = csv.writer(f)
        ww.writerow([
            "eta", "projection",
            "max_tilt_deg", "max_yaw_omega",
            "mean_rho", "projection_fired", "projection_skipped",
            "E_modal_injected_total", "E_projection_removed_total",
            "trace_csv",
        ])
        for r in rows:
            ww.writerow([
                f"{r['eta']:.2f}", r["projection"],
                f"{r['max_tilt_deg']:.4f}", f"{r['max_yaw_omega']:.6f}",
                f"{r['mean_rho']:.4f}", r["projection_fired"], r["projection_skipped"],
                f"{r['E_modal_injected_total']:.6e}",
                f"{r['E_projection_removed_total']:.6e}",
                Path(r["out_csv"]).name,
            ])
    print(f"[sweep] wrote summary to {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
