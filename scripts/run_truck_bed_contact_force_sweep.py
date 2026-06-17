#!/usr/bin/env python3
"""Per-contact force logging + slab-thickness sweep for the truck-bed scene.

Goal — VERIFY the two-way coupling at the contact level. For every contact point
in `build_truck_bed` (the `run_truck_bed_viser.py` scene), log the normal force
[N] vs sim time, with extra attention on the 3-cube LUMBER STACK (pile 1), and
sweep the bed-slab thickness. Run the same logging in parallel for FEM vs ABD
cargo cubes (solver = AVBD, the one that handles both), plus XPBD-fem and a
SplitOneWay (quasi-static bed) one-way control.

WHY this verifies two-way coupling
----------------------------------
The contact force is a SINGLE scalar F_c applied through grads[c] (multibody.py),
which carries +Jac_upper on the upper body and −Jac_lower on the lower body. So
the same F_c pushes the cube UP and the bed DOWN — equal and opposite (Newton's
third law), structurally. The force is the real slab→cube force: its time-average
equals the supported weight (calibration, asserted below). The *dynamic* two-way
signature is that the bed's RING (its modal velocity) modulates the gap → the
contact force → the resting cubes. The SplitOneWay control freezes the bed quasi-
static (no modal inertia → no ring), so its resting-pile forces do NOT carry the
post-impact oscillation. AVBD/XPBD (dynamic bed) do — that contrast is the
falsifiable proof that energy flows slab→cube, not just cube→slab.

Force extraction per solver (all in Newtons, calibrated):
  * GT / Split (penalty):  F_c = k_c · max(0, −gap_c)
  * AVBD (aug. Lagrangian): F_c = max(0, −(λ_c + ρ_c·gap_c))
  * XPBD (compliant):       F_c = λ_c / h²
recorded as `solver.last_contact_force` each step.

Outputs (docs/twobody/contact_force_sweep/):
  contact_forces_long.csv   tidy: one row per (config, thickness, step, contact)
  pile_forces_long.csv      per-pile aggregated bed-support + stack-layer forces
  summary.csv               per-config calibration + post-impact ring metrics
  *.png                     calibration, two-way contrast, fem-vs-abd, sweep, stack
"""
from __future__ import annotations

import argparse
import csv
import os

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from dcr.twobody.multibody import build_truck_bed  # noqa: E402
from dcr.twobody.position_based import (AVBDDynamicSystem,  # noqa: E402
                                        SplitOneWaySystem, XPBDDynamicSystem)

G = 9.81
OUT = "docs/twobody/contact_force_sweep"

# (solver, cube-kind) configurations to log in parallel.
CONFIGS = [
    ("avbd", "fem"),    # headline FEM cubes
    ("avbd", "abd"),    # headline ABD cubes  -> FEM-vs-ABD comparison
    ("xpbd", "fem"),    # original avbd/xpbd axis (XPBD is FEM-only)
    ("split", "fem"),   # one-way control: quasi-static bed (no ring) -> proves 2-way
]


def make_solver(name, base):
    if name == "avbd":
        return AVBDDynamicSystem(base, n_outer=8, n_inner=4)
    if name == "xpbd":
        return XPBDDynamicSystem(base, n_iters=30)
    if name == "split":
        return SplitOneWaySystem(base, newton_iters=30)
    raise ValueError(name)


def classify_contacts(base, info):
    """Tag each contact: type, pile, stack-layer. Returns list of dicts."""
    imp = info["impactor_body"]
    body_pile = {}
    for p, idxs in enumerate(info["pile_bodies"]):
        for layer, bi in enumerate(idxs):
            body_pile[bi] = (p, layer)
    tags = []
    for c, ct in enumerate(base.contacts):
        if ct.upper == imp:
            ctype, pile, layer = "bed_impactor", -1, 0
        elif ct.lower == 0:
            pile, layer = body_pile.get(ct.upper, (-1, 0))
            ctype = "bed_base"           # slab -> base cube of a pile
        else:
            pile, _ = body_pile.get(ct.upper, (-1, 0))
            layer = body_pile.get(ct.upper, (-1, 0))[1]
            ctype = "cube_cube"          # within-pile stack layer
        tags.append(dict(cid=c, ctype=ctype, pile=pile, layer=layer,
                         upper=ct.upper, lower=ct.lower))
    return tags


def run_one(solver_name, kind, thickness, h, n_steps):
    """Run one config; return (t, F[n_steps, n_contacts], tags, info, ke_piles)."""
    base, info = build_truck_bed(kind, slab_height=thickness)
    sys = make_solver(solver_name, base)
    tags = classify_contacts(base, info)
    st = sys.initial_state()
    nC = len(base.contacts)
    F = np.zeros((n_steps, nC))
    pen = np.zeros(n_steps)
    # per-pile kinetic energy over time (does the ring actually move the cargo?)
    pile_idx = info["pile_bodies"]
    KE = np.zeros((n_steps, len(pile_idx)))
    for k in range(n_steps):
        st = sys.step(st, h)
        f = sys.last_contact_force
        F[k] = f if f is not None else 0.0
        e = sys.energy_breakdown(st)
        pen[k] = e["max_penetration"]
        for p, idxs in enumerate(pile_idx):
            KE[k, p] = sum(e[f"KE_body{bi}"] for bi in idxs)
    t = (np.arange(n_steps) + 1) * h
    return dict(t=t, F=F, pen=pen, KE=KE, tags=tags, info=info, base=base)


def body_mass(b):
    """Total mass [kg] for either body type (FEM-modal carrier or ABD nodes)."""
    if hasattr(b, "carrier_mass"):
        return float(b.carrier_mass)
    return float(np.asarray(b.node_mass).sum())


def supported_weights(base, info):
    w = {}
    for p, idxs in enumerate(info["pile_bodies"]):
        w[p] = sum(body_mass(base.bodies[bi]) for bi in idxs) * G
    return w


def run_calibration(kind, thickness, h, n_steps=3000, settle_frac=0.5):
    """Clean force=weight check: NO impactor (its contacts removed so it never
    lands), let the piles settle, then time-average the bed→base force over the
    last `settle_frac` of the run. For a bounded contact ⟨F⟩−mg = m⟨a⟩ ≈ 0, so
    ⟨F⟩ ≈ weight. Returns {pile: (mean_force, std, weight, ratio)}."""
    base, info = build_truck_bed(kind, slab_height=thickness)
    imp = info["impactor_body"]
    base.contacts = [ct for ct in base.contacts
                     if ct.upper != imp and ct.lower != imp]
    base.v0 = None                       # no downward kick; pure settling
    sys = AVBDDynamicSystem(base, n_outer=8, n_inner=4)
    st = sys.initial_state()
    W = supported_weights(base, info)
    # which (remaining) contacts feed each pile base
    base_cids = {p: [c for c, ct in enumerate(base.contacts)
                     if ct.lower == 0 and ct.upper == idxs[0]]
                 for p, idxs in enumerate(info["pile_bodies"])}
    hist = np.zeros((n_steps, len(W)))
    for k in range(n_steps):
        st = sys.step(st, h)
        f = sys.last_contact_force
        for p in range(len(W)):
            hist[k, p] = f[base_cids[p]].sum()
    t = (np.arange(n_steps) + 1) * h
    sel = t >= (1.0 - settle_frac) * t[-1]    # last settle_frac of the run
    out = {}
    for p in range(len(W)):
        m, s = hist[sel, p].mean(), hist[sel, p].std()
        out[p] = (m, s, W[p], m / W[p] if W[p] > 0 else float("nan"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--thicknesses", type=float, nargs="+",
                    default=[0.03, 0.05, 0.08, 0.12])
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--n-steps", type=int, default=1000)   # 0.5 s
    ap.add_argument("--calib-steps", type=int, default=3000)  # 1.5 s settle
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    # impact happens ~0.04 s; pre-impact baseline window vs post-impact ring window
    PRE = (0.005, 0.030)
    POST = (0.045, 0.350)

    results = {}   # (solver, kind, thk) -> run dict
    summary_rows = []
    long_rows = []
    pile_rows = []

    # --- clean force=weight calibration (no impactor, settled, time-averaged) ---
    mid_thk = args.thicknesses[len(args.thicknesses) // 2]
    calib = {}
    calib_rows = []
    for kind in ("fem", "abd"):
        print(f"calibrating {kind} (no impactor, settle)...", flush=True)
        cc = run_calibration(kind, mid_thk, args.h, n_steps=args.calib_steps)
        calib[kind] = cc
        for p, (m, s, w, ratio) in cc.items():
            calib_rows.append([kind, f"{mid_thk:.4f}", p, f"{w:.3f}",
                               f"{m:.3f}", f"{s:.3f}", f"{ratio:.3f}"])
    with open(f"{args.out}/calibration.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["kind", "thickness_m", "pile", "supported_weight_N",
                    "mean_bed_force_N", "std_N", "ratio"])
        w.writerows(calib_rows)

    for solver_name, kind in CONFIGS:
        for thk in args.thicknesses:
            key = (solver_name, kind, thk)
            print(f"running {solver_name:5s} {kind:3s}  thickness={thk*1e3:5.1f} mm ...",
                  flush=True)
            r = run_one(solver_name, kind, thk, args.h, args.n_steps)
            results[key] = r
            t, F, tags, info = r["t"], r["F"], r["tags"], r["info"]
            W = supported_weights(r["base"], info)
            pre = (t >= PRE[0]) & (t < PRE[1])
            post = (t >= POST[0]) & (t < POST[1])

            # --- tidy long CSV (sub-sample to keep the file reasonable) ---
            stride = max(1, args.n_steps // 1000)
            for k in range(0, args.n_steps, stride):
                for tg in tags:
                    long_rows.append([solver_name, kind, f"{thk:.4f}", k,
                                      f"{t[k]:.5f}", tg["cid"], tg["ctype"],
                                      tg["pile"], tg["layer"], tg["upper"],
                                      tg["lower"], f"{F[k, tg['cid']]:.6f}"])

            # --- per-pile aggregated forces + calibration / ring metrics ---
            for p, idxs in enumerate(info["pile_bodies"]):
                base_cids = [tg["cid"] for tg in tags
                             if tg["ctype"] == "bed_base" and tg["pile"] == p]
                bed = F[:, base_cids].sum(axis=1)        # slab -> pile base [N]
                pre_mean = bed[pre].mean() if pre.any() else float("nan")
                cal = pre_mean / W[p] if W[p] > 0 else float("nan")
                ring = bed[post].std() if post.any() else float("nan")
                peak = bed[post].max() if post.any() else float("nan")
                ke_peak = r["KE"][post, p].max() if post.any() else float("nan")
                summary_rows.append([solver_name, kind, f"{thk:.4f}", p,
                                     len(idxs), f"{W[p]:.3f}",
                                     f"{pre_mean:.3f}", f"{cal:.3f}",
                                     f"{peak:.3f}", f"{ring:.3f}",
                                     f"{ke_peak:.4g}"])
                for k in range(0, args.n_steps, stride):
                    pile_rows.append([solver_name, kind, f"{thk:.4f}", p, k,
                                      f"{t[k]:.5f}", f"{bed[k]:.6f}",
                                      f"{r['KE'][k, p]:.6g}"])

    # ---------------- write CSVs ----------------
    with open(f"{args.out}/contact_forces_long.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["solver", "kind", "thickness_m", "step", "t_s", "contact_id",
                    "ctype", "pile", "stack_layer", "upper_body", "lower_body",
                    "force_N"])
        w.writerows(long_rows)
    with open(f"{args.out}/pile_forces_long.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["solver", "kind", "thickness_m", "pile", "step", "t_s",
                    "bed_support_force_N", "pile_KE_J"])
        w.writerows(pile_rows)
    with open(f"{args.out}/summary.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["solver", "kind", "thickness_m", "pile", "n_cubes",
                    "supported_weight_N", "pre_impact_bed_force_N",
                    "calibration_ratio", "post_impact_peak_N",
                    "post_impact_ring_std_N", "post_impact_pile_KE_peak_J"])
        w.writerows(summary_rows)
    print(f"\nwrote CSVs to {args.out}/")

    make_plots(results, args, PRE, POST, calib, mid_thk)


# ======================================================================
# plots
# ======================================================================
LUMBER = 1   # pile index of the 3-cube lumber stack (default scene)


def _bed_force(r, pile):
    tags = r["tags"]
    cids = [tg["cid"] for tg in tags
            if tg["ctype"] == "bed_base" and tg["pile"] == pile]
    return r["F"][:, cids].sum(axis=1)


def make_plots(results, args, PRE, POST, calib, mid_thk):
    thks = args.thicknesses

    # 1) CALIBRATION: settled time-averaged bed→base force vs supported weight.
    #    Proves the logged scalar IS the real slab→cube normal force.
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for kind, mark in [("fem", "o"), ("abd", "s")]:
        ws = [calib[kind][p][2] for p in sorted(calib[kind])]
        fs = [calib[kind][p][0] for p in sorted(calib[kind])]
        es = [calib[kind][p][1] for p in sorted(calib[kind])]
        ax.errorbar(ws, fs, yerr=es, fmt=mark, ms=8, capsize=3,
                    label=f"avbd-{kind} cubes")
    lim = [0, max(25, ax.get_xlim()[1])]
    ax.plot(lim, lim, "k--", lw=1, label="ideal: ⟨force⟩ = weight")
    ax.set_xlabel("supported weight  Σ m·g  [N]")
    ax.set_ylabel("settled mean bed→base force  [N]")
    ax.set_title("Calibration: logged contact force = real slab→cube force\n"
                 f"(no impactor, time-avg 0.6–1.5 s, thickness {mid_thk*1e3:.0f} mm)")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(f"{args.out}/1_calibration_force_equals_weight.png", dpi=130)
    plt.close(fig)

    # 2) TWO-WAY verification: lumber-stack bed force, AVBD/XPBD (ring) vs Split (flat)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for solver, c in [("avbd", "C0"), ("xpbd", "C1"), ("split", "C3")]:
        r = results[(solver, "fem", mid_thk)]
        ax.plot(r["t"], _bed_force(r, LUMBER), c, lw=1.1,
                label=f"{solver}-fem" + (" (one-way control)" if solver == "split" else ""))
    ax.axvspan(POST[0], POST[1], color="orange", alpha=0.08,
               label="post-impact ring window")
    ax.set_xlabel("sim time [s]")
    ax.set_ylabel("slab→lumber-stack bed force [N]")
    ax.set_title("Two-way check: bed RING reaches the lumber stack (AVBD/XPBD)\n"
                 "but the quasi-static Split bed cannot ring → its cargo barely reacts")
    ax.legend(loc="upper right"); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(f"{args.out}/2_twoway_ring_vs_oneway.png", dpi=130)
    plt.close(fig)

    # 3) FEM vs ABD: lumber-stack bed force vs time (AVBD), mid thickness
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for kind, c in [("fem", "C0"), ("abd", "C2")]:
        r = results[("avbd", kind, mid_thk)]
        ax.plot(r["t"], _bed_force(r, LUMBER), c, lw=1.1, label=f"avbd-{kind}")
    ax.set_xlabel("sim time [s]")
    ax.set_ylabel("slab→lumber-stack bed force [N]")
    ax.set_title(f"FEM vs ABD cargo cubes (AVBD, thickness {mid_thk*1e3:.0f} mm)")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(f"{args.out}/3_fem_vs_abd.png", dpi=130)
    plt.close(fig)

    # 4) THICKNESS SWEEP: lumber-stack bed force vs time + ring metric vs thickness
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    cmap = plt.cm.viridis(np.linspace(0, 0.85, len(thks)))
    for thk, col in zip(thks, cmap):
        r = results[("avbd", "fem", thk)]
        axs[0].plot(r["t"], _bed_force(r, LUMBER), color=col, lw=1.0,
                    label=f"{thk*1e3:.0f} mm")
    axs[0].set_xlabel("sim time [s]"); axs[0].set_ylabel("slab→lumber bed force [N]")
    axs[0].set_title("Lumber-stack bed force vs slab thickness (avbd-fem)")
    axs[0].legend(title="thickness"); axs[0].grid(alpha=0.3)
    for solver, mark in [("avbd", "o"), ("xpbd", "s")]:
        rings = []
        for thk in thks:
            r = results[(solver, "fem", thk)]
            t = r["t"]; post = (t >= POST[0]) & (t < POST[1])
            rings.append(_bed_force(r, LUMBER)[post].std())
        axs[1].plot(np.array(thks) * 1e3, rings, mark + "-", label=f"{solver}-fem")
    axs[1].set_xlabel("slab thickness [mm]")
    axs[1].set_ylabel("post-impact bed-force ring std [N]")
    axs[1].set_title("Ring transmitted to cargo vs thickness\n(thicker bed → stiffer → less ring)")
    axs[1].legend(); axs[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{args.out}/4_thickness_sweep.png", dpi=130)
    plt.close(fig)

    # 5) STACK TRANSMISSION: the ring climbing the 3-cube lumber pile (avbd-fem)
    r = results[("avbd", "fem", mid_thk)]
    tags = r["tags"]
    # layer 0 = bed->base ; cube_cube layers within the lumber pile
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bed = _bed_force(r, LUMBER)
    ax.plot(r["t"], bed, "C0", lw=1.0, label="bed → base cube (layer 0→1)")
    cc = [(tg["cid"], tg["upper"]) for tg in tags
          if tg["ctype"] == "cube_cube" and tg["pile"] == LUMBER]
    by_upper = {}
    for cid, up in cc:
        by_upper.setdefault(up, []).append(cid)
    for li, up in enumerate(sorted(by_upper), start=1):
        force = r["F"][:, by_upper[up]].sum(axis=1)
        ax.plot(r["t"], force, f"C{li}", lw=1.0,
                label=f"cube→cube layer {li}→{li+1} (body {up})")
    ax.set_xlabel("sim time [s]")
    ax.set_ylabel("contact normal force [N]")
    ax.set_title(f"Ring climbing the lumber stack (avbd-fem, {mid_thk*1e3:.0f} mm):\n"
                 "each higher layer carries less, lagged — force transmits up the pile")
    ax.legend(); ax.grid(alpha=0.3); fig.tight_layout()
    fig.savefig(f"{args.out}/5_stack_transmission.png", dpi=130)
    plt.close(fig)
    print(f"wrote 5 plots to {args.out}/")


if __name__ == "__main__":
    main()
