#!/usr/bin/env python3
"""Stage 1 counterfactual plot — dynamic two-way constraint vs frozen q̇≡0.

For each of the four reduced-coupled scenes, runs the dropped-impactor scenario
twice through `ReducedCoupledAVBDCoupler`:

  • dynamic   (`freeze_qdot=False`) — the finalized two-way constraint: the
    support's modal amplitude q is a second-order DOF, so the impact charges the
    modes and the ring's inertia pushes the bystander cargo back.
  • frozen    (`freeze_qdot=True`)  — the SplitOneWay control that deletes the
    M_q/h² inertia term (holds q̇≡0): the modal ring is exactly zero, so the
    bystander cargo gets only the quasi-static sag, no ring back-reaction.

This reproduces the `two_band_coupling.html` "Measured" signature: the modal
kinetic energy is the tell-tale (0 when frozen, nonzero when dynamic), and the
bystander cargo motion is driven by that ring. Saves one figure per scene plus a
summary bar chart under docs/avbd_native/.

    uv run python scripts/plot_dynamic_vs_frozen.py --device cpu
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge

_BUILDERS = {
    "truck": build_reduced_truck,
    "ledge": build_reduced_ledge,
    "shelf": build_reduced_shelf,
    "dinner": build_reduced_dinner_table,
}


def _run(scene: str, device: str, freeze: bool, n: int, h: float) -> dict:
    builder = _BUILDERS[scene]
    handle = builder(device=device, iterations=6, avbd_substeps=4, h=h,
                     to_eigenbasis=True)
    w = handle.world
    c = w.reduced_coupled_coupler
    c.device_resident = device.startswith("cuda")
    c.freeze_qdot = freeze
    descs = w._descs
    imp = getattr(handle, "impactor_idx", None)
    bystanders = [b.dcr_idx for b in handle.bodies if b.dcr_idx != imp]
    y0 = {i: float(descs[i].dcr_body.position[1]) for i in bystanders}

    t = np.arange(n) * h
    modal_ke = np.zeros(n)
    cargo_ke = np.zeros(n)
    max_rise = np.zeros(n)
    rise = 0.0
    for k in range(n):
        w.step()
        modal_ke[k] = float(c.last_modal_KE)
        ke = 0.0
        for i in bystanders:
            b = descs[i].dcr_body
            v = np.asarray(b.velocity[0:3], dtype=np.float64)
            ke += 0.5 * b.mass * float(v @ v)
            rise = max(rise, float(b.position[1]) - y0[i])
        cargo_ke[k] = ke
        max_rise[k] = rise
    return dict(t=t, modal_ke=modal_ke, cargo_ke=cargo_ke, max_rise=max_rise)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda:0"])
    ap.add_argument("--steps", type=int, default=240)
    ap.add_argument("--h", type=float, default=1.0 / 120.0)
    ap.add_argument("--outdir", default="docs/avbd_native")
    args = ap.parse_args(argv)

    import warp as wp
    wp.init()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    summary = {}
    for scene in _BUILDERS:
        print(f"[plot] {scene}: dynamic ...", flush=True)
        dyn = _run(scene, args.device, False, args.steps, args.h)
        print(f"[plot] {scene}: frozen q̇≡0 ...", flush=True)
        frz = _run(scene, args.device, True, args.steps, args.h)
        summary[scene] = (dyn, frz)

        fig, ax = plt.subplots(1, 3, figsize=(15, 4))
        ax[0].plot(dyn["t"], dyn["modal_ke"], "C0", label="dynamic q")
        ax[0].plot(frz["t"], frz["modal_ke"], "C3", label="frozen q̇≡0")
        ax[0].set_title(f"{scene} — modal kinetic energy")
        ax[0].set_xlabel("t [s]"); ax[0].set_ylabel("½q̇ᵀM_qq̇ [J]")
        ax[0].legend(); ax[0].grid(alpha=0.3)

        ax[1].plot(dyn["t"], dyn["cargo_ke"], "C0", label="dynamic q")
        ax[1].plot(frz["t"], frz["cargo_ke"], "C3", label="frozen q̇≡0")
        ax[1].set_title(f"{scene} — bystander cargo KE")
        ax[1].set_xlabel("t [s]"); ax[1].set_ylabel("Σ ½m|v|² [J]")
        ax[1].legend(); ax[1].grid(alpha=0.3)

        ax[2].plot(dyn["t"], dyn["max_rise"] * 1e3, "C0", label="dynamic q")
        ax[2].plot(frz["t"], frz["max_rise"] * 1e3, "C3", label="frozen q̇≡0")
        ax[2].set_title(f"{scene} — peak bystander rise")
        ax[2].set_xlabel("t [s]"); ax[2].set_ylabel("max Δy [mm]")
        ax[2].legend(); ax[2].grid(alpha=0.3)

        fig.tight_layout()
        path = outdir / f"stage1_dynamic_vs_frozen_{scene}.png"
        fig.savefig(path, dpi=110)
        plt.close(fig)
        print(f"  saved {path}")

    # Summary bar chart: peak modal KE + peak rise, dynamic vs frozen.
    scenes = list(summary.keys())
    x = np.arange(len(scenes))
    pk_modal_dyn = [summary[s][0]["modal_ke"].max() for s in scenes]
    pk_modal_frz = [summary[s][1]["modal_ke"].max() for s in scenes]
    pk_rise_dyn = [summary[s][0]["max_rise"].max() * 1e3 for s in scenes]
    pk_rise_frz = [summary[s][1]["max_rise"].max() * 1e3 for s in scenes]

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].bar(x - 0.2, pk_modal_dyn, 0.4, label="dynamic q", color="C0")
    ax[0].bar(x + 0.2, pk_modal_frz, 0.4, label="frozen q̇≡0", color="C3")
    ax[0].set_xticks(x); ax[0].set_xticklabels(scenes)
    ax[0].set_title("peak modal KE (the ring) — 0 when frozen")
    ax[0].set_ylabel("J"); ax[0].legend(); ax[0].grid(alpha=0.3, axis="y")

    ax[1].bar(x - 0.2, pk_rise_dyn, 0.4, label="dynamic q", color="C0")
    ax[1].bar(x + 0.2, pk_rise_frz, 0.4, label="frozen q̇≡0", color="C3")
    ax[1].set_xticks(x); ax[1].set_xticklabels(scenes)
    ax[1].set_title("peak bystander rise — the two-way kick")
    ax[1].set_ylabel("mm"); ax[1].legend(); ax[1].grid(alpha=0.3, axis="y")
    fig.tight_layout()
    path = outdir / "stage1_dynamic_vs_frozen_summary.png"
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  saved {path}")

    print("\n  peak modal KE / peak bystander rise (dynamic vs frozen):")
    for s in scenes:
        print(f"    {s:7s}  modalKE {summary[s][0]['modal_ke'].max():.3e} vs "
              f"{summary[s][1]['modal_ke'].max():.3e} J   "
              f"rise {summary[s][0]['max_rise'].max()*1e3:6.2f} vs "
              f"{summary[s][1]['max_rise'].max()*1e3:6.2f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
