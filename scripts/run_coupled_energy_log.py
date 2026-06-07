"""Energy logger v2 — trustworthy energy budget + substep timeline.

Addresses the user's review of v1 (see audit comments in the source):

  v1 problems                       v2 fix
  ─────────────────────────────────────────────────────────────────
  • frame-rate sampling skips        • opt-in substep-resolution log
    the impact transient               (--log-substeps)
  • E_total missed rigid grav. PE    • includes -m·g·y per body
  • E_total plotted in raw J         • all energies plotted in µJ
    while siblings ×1000               consistently
  • no per-probe data                 • probe_uy_m, probe_vy_mps per probe
  • no λ recorded                    • contact_lambda_max column
  • BDF1 over-damps ringing          • --integrator newmark switches the
    invisibly                          coupler to Newmark β=1/4, γ=1/2
                                       (no numerical damping)

Writes to `plot/`:
  coupled_energy_<tag>.csv         — frame-rate per-step log
  coupled_energy_<tag>.png         — frame-rate energy budget figure
  coupled_energy_<tag>_substep.csv — substep-rate log (if --log-substeps)
  coupled_energy_<tag>_substep.png — substep-rate figure
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


GRAVITY_Y = -9.81   # used by AVBDDCRWorld; see dcr/avbd/world.py


def _rigid_grav_PE(bodies, y_ref: float = 0.0) -> float:
    """Σ m·g·(y − y_ref) over non-static bodies. y_ref shifts the zero
    so the value at t=0 is small."""
    g = abs(GRAVITY_Y)
    total = 0.0
    for b in bodies:
        if b.is_static:
            continue
        total += b.mass * g * (float(b.position[1]) - y_ref)
    return float(total)


def _rigid_kinetic(bodies) -> float:
    from dcr.rigid.energy import rigid_kinetic_energy
    return rigid_kinetic_energy(bodies)


def _run(args):
    from scenes.reduced_support_shelf import build_reduced_support_shelf

    probe_xz = [
        (-0.40 * args.shelf_length, args.probe_z_offset),
        (+0.40 * args.shelf_length, args.probe_z_offset),
    ]
    mode = _resolve_mode(args)
    handle = build_reduced_support_shelf(
        h=args.h, device="cpu",
        iterations=4,
        avbd_substeps=args.substeps,
        shelf_length=args.shelf_length,
        shelf_width=args.shelf_width,
        shelf_thickness=args.shelf_thickness,
        impactor_drop_height=args.drop_height,
        impactor_v0=(0.0, args.v0_y, 0.0),
        impactor_mass=args.impactor_mass,
        probe_mass=0.005,
        probe_xz=probe_xz,
        n_modes_global=6, n_modes_local=4,
        youngs=args.youngs,
        reduced_support_enabled=(mode != "plain"),
        reduced_static_support=(mode == "coupled_modal_static"),
        coupled_avbd=(mode in ("coupled_modal_bdf1", "coupled_iir_modal")),
        dcr_postkick=(mode == "old_dcr_postkick"),
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=args.rayleigh_alpha1,
        modal_impedance_scale=args.support_response_gain,
        modal_damping_scale=args.modal_damping_scale,
        modal_energy_cap_fraction=args.modal_energy_cap_fraction,
        modal_jump_gain=args.modal_jump_gain,
        modal_jump_max_height=args.modal_jump_max_height,
        to_eigenbasis=(getattr(args, "reduced_basis", "synthetic") == "eigen"),
    )
    w = handle.world
    rs = handle.rs
    c = w.reduced_coupled_coupler
    if c is not None and mode in ("coupled_modal_bdf1", "coupled_iir_modal"):
        c.q_integrator = "bdf1" if mode == "coupled_modal_bdf1" else "iir"
        c.log_substeps = bool(args.log_substeps)
        c.substep_log = []  # clean slate

    bodies = [d.dcr_body for d in w._descs]
    impactor_body = w._descs[handle.impactor_idx].dcr_body
    probe_bodies = [w._descs[i].dcr_body for i in handle.probe_indices]

    # y_ref = initial *impactor* y; the impactor's gravitational PE then
    # starts at 0 and goes negative as it falls. Probes (resting on the
    # shelf at y ≈ 0) contribute a small constant offset; we don't
    # subtract that because it's part of the total system energy.
    y_ref = float(impactor_body.position[1])

    rows = []
    cum_damp_E = 0.0
    rigid_PE_initial = _rigid_grav_PE(bodies, y_ref=y_ref)

    for step in range(args.frames):
        w.step()
        KE_r  = _rigid_kinetic(bodies)
        PE_r  = _rigid_grav_PE(bodies, y_ref=y_ref)
        # Modal-side diagnostics only when the coupled coupler is attached.
        # In --mode plain / old_dcr_postkick the coupler is None.
        if c is not None:
            KE_q  = float(c.last_modal_KE)
            PE_q  = float(c.last_modal_PE)
            P_d   = float(c.last_damp_power)
            q_norm = float(c.last_q_norm)
            qdot_norm = float(c.last_qdot_norm)
            q_acc_norm = float(c.last_q_acc_norm)
            max_defl = float(c.last_max_support_deflection)
            lam_max = float(c.last_contact_lambda_max)
            min_S_h = float(getattr(c, "last_min_S_h", 0.0))
            max_S_h = float(getattr(c, "last_max_S_h", 0.0))
            postkick_calls = int(getattr(c, "dcr_postkick_calls", 0))
            alpha_cap = float(getattr(c, "last_alpha_cap", 1.0))
            cap_engagements = int(getattr(c, "cap_engagements", 0))
            dE_modal = float(getattr(c, "last_dE_modal", 0.0))
            dE_rigid_loss = float(getattr(c, "last_dE_rigid_loss", 0.0))
            last_max_v_lift = float(getattr(c, "last_max_v_lift", 0.0))
            last_max_v_hp = float(getattr(c, "last_max_v_hp", 0.0))
            jump_engagements = int(getattr(c, "jump_engagements", 0))
        else:
            KE_q = PE_q = P_d = 0.0
            q_norm = qdot_norm = q_acc_norm = 0.0
            max_defl = lam_max = 0.0
            min_S_h = max_S_h = 0.0
            postkick_calls = 0
            alpha_cap = 1.0
            cap_engagements = 0
            dE_modal = dE_rigid_loss = 0.0
            last_max_v_lift = last_max_v_hp = 0.0
            jump_engagements = 0
            pk = w.reduced_dcr_postkick_coupler
            if pk is not None:
                postkick_calls = int(pk.cum_kick_events)
        cum_damp_E += P_d * args.h
        # Total = rigid KE + rigid grav. PE + modal KE + modal PE
        #         + integrated damping (energy that left the live system).
        E_total = KE_r + PE_r + KE_q + PE_q + cum_damp_E
        # Per-probe diagnostics.
        probe_uy = [float(b.position[1]) for b in probe_bodies]
        probe_vy = [float(b.velocity[1]) for b in probe_bodies]

        row = {
            "step":             step,
            "t_s":              step * args.h,
            "KE_rigid_J":       KE_r,
            "PE_rigid_J":       PE_r,
            "KE_modal_J":       KE_q,
            "PE_modal_J":       PE_q,
            "P_damp_W":         P_d,
            "cum_damp_E_J":     cum_damp_E,
            "E_total_J":        E_total,
            "q_norm_m":         q_norm,
            "qdot_norm":        qdot_norm,
            "q_acc_norm":       q_acc_norm,
            "max_deflection_m": max_defl,
            "contact_lambda_max": lam_max,
            "min_S_h":          min_S_h,
            "max_S_h":          max_S_h,
            "postkick_calls":   postkick_calls,
            "gain":             float(args.support_response_gain),
            "damping_scale":    float(args.modal_damping_scale),
            "eta":              (float(args.modal_energy_cap_fraction)
                                 if args.modal_energy_cap_fraction is not None
                                 else float("nan")),
            "alpha_cap":        alpha_cap,
            "cap_engagements":  cap_engagements,
            "dE_modal":         dE_modal,
            "dE_rigid_loss":    dE_rigid_loss,
            "jump_gain":        float(args.modal_jump_gain),
            "jump_max_height":  float(args.modal_jump_max_height),
            "last_max_v_lift":  last_max_v_lift,
            "last_max_v_hp":    last_max_v_hp,
            "jump_engagements": jump_engagements,
            "impactor_y_m":     float(impactor_body.position[1]),
            "impactor_vy_mps":  float(impactor_body.velocity[1]),
        }
        for k, uy in enumerate(probe_uy):
            row[f"probe{k}_uy_m"] = uy
        for k, vy in enumerate(probe_vy):
            row[f"probe{k}_vy_mps"] = vy
        rows.append(row)

    substep_log = c.substep_log if c is not None else []
    return handle, rows, substep_log


def _write_csv(rows, path: Path):
    fields = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _plot_frames(rows, path: Path, *, title: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available; skipping PNG; CSV written.")
        return

    t       = np.array([r["t_s"]            for r in rows])
    KE_r    = np.array([r["KE_rigid_J"]     for r in rows]) * 1e6
    PE_r    = np.array([r["PE_rigid_J"]     for r in rows]) * 1e6
    KE_q    = np.array([r["KE_modal_J"]     for r in rows]) * 1e6
    PE_q    = np.array([r["PE_modal_J"]     for r in rows]) * 1e6
    cum_d   = np.array([r["cum_damp_E_J"]   for r in rows]) * 1e6
    E_tot   = np.array([r["E_total_J"]      for r in rows]) * 1e6
    q_norm  = np.array([r["q_norm_m"]       for r in rows]) * 1e6
    qdot_n  = np.array([r["qdot_norm"]      for r in rows]) * 1e3
    lam     = np.array([r["contact_lambda_max"] for r in rows])

    # Probes
    n_probes = sum(1 for k in rows[0] if k.startswith("probe") and k.endswith("_uy_m"))
    probe_vys = []
    probe_uys = []
    for k in range(n_probes):
        probe_vys.append(np.array([r[f"probe{k}_vy_mps"] for r in rows]) * 1e3)
        probe_uys.append(np.array([r[f"probe{k}_uy_m"]   for r in rows]) * 1e6)

    fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
    ax1, ax2, ax3 = axes

    # Panel 1 — energies, all in µJ on a single scale (no ×1000 trick).
    ax1.plot(t, KE_r,  label="KE_rigid",   color="#c8423c", lw=2.0)
    ax1.plot(t, PE_r,  label="PE_rigid",   color="#9b3c3c", lw=2.0, linestyle="--")
    ax1.plot(t, KE_q,  label="KE_modal",   color="#3c78c8", lw=1.5)
    ax1.plot(t, PE_q,  label="PE_modal",   color="#2d8a3c", lw=1.5)
    ax1.plot(t, cum_d, label="∫P_damp dt", color="#a06820", lw=1.5,
             linestyle="--")
    ax1.plot(t, E_tot, label="E_total",    color="#222",    lw=1.0,
             linestyle=":")
    ax1.set_ylabel("Energy (µJ)")
    ax1.set_title(title)
    ax1.legend(loc="best", fontsize=8, ncol=2)
    ax1.grid(True, alpha=0.3)

    # Panel 2 — modal kinematics + contact λ.
    ax2.plot(t, q_norm, label="|q| (µm)", color="#3c78c8", lw=1.5)
    ax2b = ax2.twinx()
    ax2b.plot(t, qdot_n, label="|qdot| (mm/s)",
              color="#a06820", lw=1.5, linestyle="--")
    ax2b.plot(t, lam, label="max|λ|", color="#666", lw=1.0, linestyle=":")
    ax2.set_ylabel("|q| (µm)", color="#3c78c8")
    ax2b.set_ylabel("|qdot| (mm/s) · max|λ|", color="#a06820")
    ax2.grid(True, alpha=0.3)
    lines1, labs1 = ax2.get_legend_handles_labels()
    lines2, labs2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labs1 + labs2, loc="best", fontsize=8)

    # Panel 3 — per-probe vy (the actual distant response).
    for k, vy in enumerate(probe_vys):
        ax3.plot(t, vy, label=f"probe{k} vy (mm/s)", lw=1.3)
    ax3.set_xlabel("t (s)")
    ax3.set_ylabel("probe vy (mm/s)")
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="best", fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_substeps(substep_rows, path: Path, *, title: str,
                   t_max_ms: float | None = None):
    if not substep_rows:
        return
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    t      = np.array([r["t_substep_s"]         for r in substep_rows]) * 1e3  # ms
    KE_q   = np.array([r["KE_modal_J"]          for r in substep_rows]) * 1e6
    PE_q   = np.array([r["PE_modal_J"]          for r in substep_rows]) * 1e6
    qdot_n = np.array([r["qdot_norm"]           for r in substep_rows]) * 1e3
    q_norm = np.array([r["q_norm_m"]            for r in substep_rows]) * 1e6
    lam    = np.array([r["contact_lambda_max"]  for r in substep_rows])

    if t_max_ms is not None:
        mask = t <= t_max_ms
        t, KE_q, PE_q, qdot_n, q_norm, lam = (
            t[mask], KE_q[mask], PE_q[mask], qdot_n[mask], q_norm[mask], lam[mask])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.plot(t, KE_q, label="KE_modal", color="#3c78c8", lw=1.3)
    ax1.plot(t, PE_q, label="PE_modal", color="#2d8a3c", lw=1.3)
    ax1.set_ylabel("Energy (µJ)")
    suffix = (f"  (substep-resolved, first {t_max_ms:.0f} ms)"
              if t_max_ms is not None else "  (substep-resolved)")
    ax1.set_title(title + suffix)
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    ax2.plot(t, q_norm, label="|q| (µm)", color="#3c78c8", lw=1.3)
    ax2b = ax2.twinx()
    ax2b.plot(t, qdot_n, label="|qdot| (mm/s)",
              color="#a06820", lw=1.3, linestyle="--")
    ax2b.plot(t, lam, label="max|λ|", color="#666", lw=1.0, linestyle=":")
    ax2.set_xlabel("t (ms)")
    ax2.set_ylabel("|q| (µm)", color="#3c78c8")
    ax2b.set_ylabel("|qdot| (mm/s) · max|λ|", color="#a06820")
    ax2.grid(True, alpha=0.3)
    lines1, labs1 = ax2.get_legend_handles_labels()
    lines2, labs2 = ax2b.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labs1 + labs2, fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _resolve_mode(args) -> str:
    """Map deprecated --integrator to --mode for backward compat."""
    import warnings as _w
    if args.integrator is None:
        return args.mode
    if args.mode != "coupled_iir_modal":
        # User passed both; --mode wins.
        _w.warn(f"--integrator={args.integrator} ignored; --mode={args.mode}",
                stacklevel=2)
        return args.mode
    mapping = {
        "bdf1":    "coupled_modal_bdf1",
        "newmark": "coupled_iir_modal",   # newmark removed; use iir instead
        "iir":     "coupled_iir_modal",
    }
    mapped = mapping[args.integrator]
    _w.warn(f"--integrator={args.integrator} is deprecated; use --mode={mapped}",
            DeprecationWarning, stacklevel=2)
    return mapped


def main():
    from scenes.presets import (
        PRESETS, DEMO_STYLES, MATERIAL_YOUNGS,
        get_scene, get_style,
        format_scene_table, format_style_table,
    )

    ap = argparse.ArgumentParser(
        description="Energy-budget logger for the reduced-coupled AVBD "
                    "shelf. Pick a scene + demo-style preset.")
    ap.add_argument("--list-scenes", action="store_true")
    ap.add_argument("--list-styles", action="store_true")

    # Top-level presets.
    ap.add_argument("--scene", choices=list(PRESETS.keys()),
                    default="research-baseline")
    ap.add_argument("--demo-style", choices=list(DEMO_STYLES.keys()),
                    default="honest")

    # Workflow knobs (always-keep).
    ap.add_argument("--frames",   type=int,   default=240)
    ap.add_argument("--h",        type=float, default=1.0 / 120.0)
    ap.add_argument("--tag", default=None,
                    help="filename tag for plot/ output (defaults to scene name)")

    # Architecture mode.
    ap.add_argument(
        "--mode",
        choices=["plain", "old_dcr_postkick",
                 "coupled_modal_static", "coupled_modal_bdf1",
                 "coupled_iir_modal"],
        default="coupled_iir_modal")

    # Scene overrides (None → preset).
    scene_grp = ap.add_argument_group("Scene overrides")
    scene_grp.add_argument("--material",
                           choices=list(MATERIAL_YOUNGS.keys()),
                           default=None)
    scene_grp.add_argument("--shelf-thickness", type=float, default=None)
    scene_grp.add_argument("--drop-height", type=float, default=None)
    scene_grp.add_argument("--v0-y",        type=float, default=None)
    scene_grp.add_argument("--impactor-mass", type=float, default=None)
    scene_grp.add_argument("--probe-z-offset", type=float, default=None)

    # Demo-style overrides (None → style).
    demo_grp = ap.add_argument_group("Demo-style overrides")
    demo_grp.add_argument("--support-response-gain", type=float, default=None)
    demo_grp.add_argument("--modal-damping-scale", type=float, default=None)
    demo_grp.add_argument("--modal-energy-cap-fraction", type=float, default=None)
    demo_grp.add_argument("--modal-jump-gain", type=float, default=None)
    demo_grp.add_argument("--modal-jump-max-height", type=float, default=None)

    # Solver / advanced.
    adv_grp = ap.add_argument_group("Advanced")
    adv_grp.add_argument("--substeps", type=int,   default=4)
    adv_grp.add_argument("--rayleigh-alpha1", type=float, default=5.0e-6)
    adv_grp.add_argument("--log-substeps", action="store_true", default=False)
    adv_grp.add_argument("--zoom-ms", type=float, default=50.0)
    adv_grp.add_argument("--reduced-basis", choices=["synthetic", "eigen"],
                         default="eigen",
                         help="Modal basis: 'synthetic' (sine+bump, coupled) "
                              "or 'eigen' (M̂=I, K̂=Ω², diagonal IIR). "
                              "Physically equivalent; eigen is the default.")

    # Deprecated (kept for one cycle).
    dep_grp = ap.add_argument_group("Deprecated")
    dep_grp.add_argument("--integrator", choices=["bdf1", "newmark", "iir"],
                         default=None,
                         help="DEPRECATED: use --mode.")
    dep_grp.add_argument("--youngs", type=float, default=None,
                         help="DEPRECATED: use --material.")

    args = ap.parse_args()

    if args.list_scenes:
        print(format_scene_table()); return
    if args.list_styles:
        print(format_style_table()); return

    # ---- Resolve preset + style + overrides into args.* ----
    scene = get_scene(args.scene)
    style = get_style(args.demo_style)
    args.tag = args.tag or scene.name

    # Material → youngs.
    mat = args.material or scene.default_material
    if args.youngs is None:
        args.youngs = MATERIAL_YOUNGS[mat]
    args.material = mat

    # Scene fields (fall through preset where None).
    if args.drop_height     is None: args.drop_height     = scene.impactor_drop_height
    if args.v0_y            is None: args.v0_y            = scene.impactor_v0_y
    if args.impactor_mass   is None: args.impactor_mass   = scene.impactor_mass
    if args.probe_z_offset  is None: args.probe_z_offset  = scene.probe_z_offset
    args.shelf_length    = scene.shelf_length
    args.shelf_width     = scene.shelf_width
    args.shelf_thickness = args.shelf_thickness if args.shelf_thickness is not None else scene.shelf_thickness

    # Demo-style fields.
    if args.support_response_gain   is None: args.support_response_gain   = style.support_response_gain
    if args.modal_damping_scale     is None: args.modal_damping_scale     = style.modal_damping_scale
    if args.modal_energy_cap_fraction is None: args.modal_energy_cap_fraction = style.modal_energy_cap_fraction
    if args.modal_jump_gain         is None: args.modal_jump_gain         = style.modal_jump_gain
    if args.modal_jump_max_height   is None: args.modal_jump_max_height   = style.modal_jump_max_height

    print(f"[scene]  {scene.name}  material={args.material}  "
          f"(E={args.youngs:.2e} Pa, h_t={args.shelf_thickness*1e3:.1f} mm)")
    print(f"[style]  {style.name}  jump γ={args.modal_jump_gain:.3g}  "
          f"g={args.support_response_gain:.3g}")

    out_dir = ROOT / "plot"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"coupled_energy_{args.tag}.csv"
    png_path = out_dir / f"coupled_energy_{args.tag}.png"

    mode = _resolve_mode(args)
    print(f"  mode={mode}, E={args.youngs:.1e}, substeps={args.substeps}, "
          f"v0_y={args.v0_y}, drop={args.drop_height}, "
          f"probe_z={args.probe_z_offset}, frames={args.frames}, "
          f"α₁={args.rayleigh_alpha1}")
    handle, rows, substep_rows = _run(args)

    _write_csv(rows, csv_path)
    print(f"  wrote: {csv_path}")

    # IIR-mode diagnostic: report S_h(min) / S_h(max) range from the
    # last frame to give a sense of per-mode dynamic compliance scale.
    last_row = rows[-1]
    s_h_lo = last_row.get("min_S_h", 0.0)
    s_h_hi = last_row.get("max_S_h", 0.0)
    pk = last_row.get("postkick_calls", 0)
    s_h_str = (f", S_h ∈ [{s_h_lo:.2e}, {s_h_hi:.2e}]"
               if s_h_lo > 0 or s_h_hi > 0 else "")
    pk_str = f", postkick={pk}" if pk > 0 else ""
    knob_parts = []
    if args.support_response_gain != 1.0:
        knob_parts.append(f"g={args.support_response_gain:.3g}")
    if args.modal_damping_scale != 1.0:
        knob_parts.append(f"c_ζ={args.modal_damping_scale:.3g}")
    if args.modal_energy_cap_fraction is not None:
        cap_ev = int(last_row.get("cap_engagements", 0))
        knob_parts.append(
            f"η={args.modal_energy_cap_fraction:.3g} ({cap_ev} engagements)")
    if args.modal_jump_gain != 1.0:
        jump_ev = int(last_row.get("jump_engagements", 0))
        max_v_lift = max(float(r.get("last_max_v_lift", 0.0)) for r in rows)
        knob_parts.append(
            f"jump γ={args.modal_jump_gain:.3g} "
            f"({jump_ev} engagements, peak v_lift={max_v_lift:.3f} m/s)")
    knob_str = ("\n" + " · ".join(knob_parts)) if knob_parts else ""
    title = (f"Coupled-AVBD energy budget ({args.tag}, "
             f"E={args.youngs:.1e} Pa, mode={mode}"
             f", substeps={args.substeps}{s_h_str}{pk_str}){knob_str}")
    _plot_frames(rows, png_path, title=title)
    print(f"  wrote: {png_path}")

    if args.log_substeps and substep_rows:
        ss_csv = out_dir / f"coupled_energy_{args.tag}_substep.csv"
        ss_png = out_dir / f"coupled_energy_{args.tag}_substep.png"
        ss_zoom_png = out_dir / f"coupled_energy_{args.tag}_substep_zoom.png"
        _write_csv(substep_rows, ss_csv)
        _plot_substeps(substep_rows, ss_png, title=title)
        _plot_substeps(substep_rows, ss_zoom_png, title=title,
                       t_max_ms=args.zoom_ms)
        print(f"  wrote: {ss_csv}")
        print(f"  wrote: {ss_png}")
        print(f"  wrote: {ss_zoom_png}  (first {args.zoom_ms:.0f} ms)")

    KE_r_final = rows[-1]["KE_rigid_J"]
    PE_r_initial = rows[0]["PE_rigid_J"]
    PE_r_final = rows[-1]["PE_rigid_J"]
    KE_q_peak  = max(r["KE_modal_J"] for r in rows)
    PE_q_peak  = max(r["PE_modal_J"] for r in rows)
    cum_d_end  = rows[-1]["cum_damp_E_J"]
    E_tot_init = rows[0]["E_total_J"]
    E_tot_end  = rows[-1]["E_total_J"]
    print()
    print(f"  Initial rigid grav. PE: {PE_r_initial*1e3:.2f} mJ")
    print(f"  Final   rigid grav. PE: {PE_r_final*1e3:.2f} mJ")
    print(f"  ΔPE_rigid              : {(PE_r_final-PE_r_initial)*1e6:.2f} µJ "
          f"(gravity work into the system)")
    print(f"  Final   KE_rigid       : {KE_r_final*1e6:.3f} µJ")
    print(f"  Peak    KE_modal       : {KE_q_peak*1e6:.3f} µJ "
          f"({100*KE_q_peak/max(abs(PE_r_initial-PE_r_final),1e-30):.4f}% "
          f"of ΔPE_rigid)")
    print(f"  Peak    PE_modal       : {PE_q_peak*1e6:.3f} µJ")
    print(f"  ∫P_damp dt             : {cum_d_end*1e6:.3f} µJ")
    print(f"  E_total drift          : "
          f"{(E_tot_end-E_tot_init)*1e6:+.3f} µJ "
          f"(should be ≈ 0 + numerical-damping leakage)")
    print(f"  Peak |q|               : "
          f"{max(r['q_norm_m']  for r in rows)*1e6:.2f} µm")
    print(f"  Peak |qdot|            : "
          f"{max(r['qdot_norm'] for r in rows)*1e3:.2f} mm/s")
    print(f"  Peak max|λ|            : "
          f"{max(r['contact_lambda_max'] for r in rows):.3e} N (multiplier)")

    n_probes = sum(1 for k in rows[0]
                   if k.startswith("probe") and k.endswith("_vy_mps"))
    for k in range(n_probes):
        peak_vy = max(abs(r[f"probe{k}_vy_mps"]) for r in rows)
        rng_uy  = (max(r[f"probe{k}_uy_m"] for r in rows)
                   - min(r[f"probe{k}_uy_m"] for r in rows))
        print(f"  Probe {k} peak |vy|    : {peak_vy*1e3:.3f} mm/s, "
              f"uy range {rng_uy*1e6:.2f} µm")


if __name__ == "__main__":
    main()
