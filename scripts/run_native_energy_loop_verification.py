#!/usr/bin/env python3
"""Two-way coupling + slab⇄object energy-loop verification for the NATIVE solvers.

Replicates the twobody `contact_force_sweep` verification on the current native
AVBD (`Solver6DOF`) / XPBD (`SolverXPBD`) reduced-modal-support scenes (NON-cargo):
per-contact force logging + the energy loop + a one-way control + an
iterations×substeps sweep, for several scenes and both solvers.

Outputs (docs/native_energy_loop/):
  loop_<scene>_<solver>.png        4-panel energy loop (E, height/airborne, forces)
  control_<scene>_<solver>.png     two-way vs one-way (freeze q̇) overlay
  percontact_<scene>_<solver>.png  per-corner force, impactor + resting object
  sweep_<scene>_<solver>.png       iters×substeps heatmaps of the loop metrics
  schematic.png                    annotated box-and-arrow energy loop
  summary.csv                      every (scene,solver,iters,substeps,coupling) metric
  loop_series.csv                  per-step series for the primary (16,4) configs
  README.md                        verified findings

Run:  .venv/bin/python scripts/run_native_energy_loop_verification.py
      [--scenes shelf,ledge,dinner] [--quick]
"""
from __future__ import annotations

import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scripts.probe_native_energy_loop import run, loop_metrics

SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "native_energy_loop")
G = 9.81


# --------------------------------------------------------------------------- #
# Figures                                                                     #
# --------------------------------------------------------------------------- #
def fig_loop(scene, solver, rec):
    """4-panel: the energy loop, the bounces, and the per-corner forces."""
    t = rec["t"]
    m = loop_metrics(rec)
    ti = t[m["impact_f"]]
    fig, ax = plt.subplots(4, 1, figsize=(11, 12), sharex=True)

    # 1 — the slab⇄object energy loop + impactor KE (the source).
    ax[0].plot(t, rec["Eimp"] * 1e3, "C0", lw=1.1, label="impactor KE (source)")
    ax[0].plot(t, rec["Eslab"] * 1e3, "C3", lw=1.3, label="SLAB modal ring KE+PE")
    ax[0].plot(t, rec["Erest"] * 1e3, "C2", lw=1.3,
               label="resting object mech E (KE+gravPE)")
    ax[0].plot(t, rec["ErestKE"] * 1e3, "C2", lw=0.7, ls=":", alpha=0.7,
               label="resting object KE only")
    ax[0].axvline(ti, color="k", lw=0.6, ls="--", alpha=0.6)
    ax[0].set_ylabel("energy [mJ]")
    ax[0].set_title(
        f"{scene} / {solver} — slab⇄object energy loop  "
        f"(impactor {m['Eimp_peak']:.1f} J → slab {m['Eslab_peak']*1e3:.0f} mJ "
        f"→ object launch {m['Erest_launch']*1e3:.1f} mJ)")
    ax[0].legend(fontsize=8, loc="upper right"); ax[0].grid(alpha=0.3)

    # 2 — resting object height + airborne shading (the bounces).
    ax[1].plot(t, rec["ylift"] * 1e3, "C2", lw=1.1, label="resting object lift [mm]")
    ax[1].axhline(0, color="k", lw=0.5)
    air = rec["gap"] > 1e-4
    y0, y1 = ax[1].get_ylim()
    ax[1].fill_between(t, y0, y1, where=air, color="orange", alpha=0.15,
                       label="airborne (gap>0)")
    ax[1].set_ylim(y0, y1)
    ax[1].set_ylabel("lift [mm]")
    ax[1].set_title(f"bounces = {m['bounces']} (max lift {m['max_lift_mm']:.1f} mm, "
                    f"slab rings = {m['slab_rings']})")
    ax[1].legend(fontsize=8, loc="upper right"); ax[1].grid(alpha=0.3)

    # 3 — impactor per-corner contact force (slab → impactor feedback).
    Fi = rec["Fimp"]
    for c in range(Fi.shape[1]):
        ax[2].plot(t, Fi[:, c], lw=0.9, label=f"corner {c}")
    ax[2].set_ylabel("impactor force [N]")
    ax[2].set_title(f"slab→impactor contact force per corner "
                    f"(peak {m['Fimp_peak']:.0f} N) — repeated spikes = rebounds")
    ax[2].legend(fontsize=7, ncol=4, loc="upper right"); ax[2].grid(alpha=0.3)

    # 4 — resting object per-corner contact force (slab → object feedback).
    Fr = rec["Frest"]
    for c in range(Fr.shape[1]):
        ax[3].plot(t, Fr[:, c], lw=0.9, label=f"corner {c}")
    ax[3].set_ylabel("resting force [N]"); ax[3].set_xlabel("sim time [s]")
    ax[3].set_title(f"slab→resting-object contact force per corner "
                    f"(peak {m['Frest_peak']:.0f} N)")
    ax[3].legend(fontsize=7, ncol=4, loc="upper right"); ax[3].grid(alpha=0.3)

    fig.tight_layout()
    p = os.path.join(OUT, f"loop_{scene}_{solver}.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def fig_control(scene, solver, rec2, rec1):
    """two-way (q̇ active) vs one-way (q̇ frozen) overlay — the discriminating test."""
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    ax[0].plot(rec2["t"], rec2["Eslab"] * 1e3, "C3", lw=1.3,
               label="slab ring — TWO-WAY (q̇ active)")
    ax[0].plot(rec1["t"], rec1["Eslab"] * 1e3, "C3", lw=1.0, ls="--", alpha=0.8,
               label="slab ring — ONE-WAY (q̇ frozen)")
    ax[0].set_ylabel("slab energy [mJ]")
    ax[0].set_title(f"{scene} / {solver} — coupling control: does freezing the "
                    f"modal ring kill the feedback?")
    ax[0].legend(fontsize=8); ax[0].grid(alpha=0.3)

    ax[1].plot(rec2["t"], rec2["ErestKE"] * 1e3, "C2", lw=1.3,
               label="resting-object KE — TWO-WAY")
    ax[1].plot(rec1["t"], rec1["ErestKE"] * 1e3, "C2", lw=1.0, ls="--", alpha=0.8,
               label="resting-object KE — ONE-WAY")
    m2, m1 = loop_metrics(rec2), loop_metrics(rec1)
    ratio = (m2["ErestKE_peak"] / m1["ErestKE_peak"]
             if m1["ErestKE_peak"] > 1e-12 else float("inf"))
    ax[1].set_ylabel("resting object KE [mJ]"); ax[1].set_xlabel("sim time [s]")
    ax[1].set_title(f"object KE peak two-way/one-way = {ratio:.1f}×  "
                    f"(slab peak {m2['Eslab_peak']*1e3:.0f} vs "
                    f"{m1['Eslab_peak']*1e3:.0f} mJ)")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    fig.tight_layout()
    p = os.path.join(OUT, f"control_{scene}_{solver}.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return ratio


def fig_sweep(scene, solver, grid, iters_list, subs_list):
    """iters×substeps heatmaps of the headline loop metrics."""
    keys = [("Eslab_peak", "slab ring peak [mJ]", 1e3),
            ("ErestKE_peak", "object KE peak [mJ]", 1e3),
            ("bounces", "object bounces", 1.0),
            ("twoway_ratio", "object KE two-way/one-way", 1.0)]
    fig, axs = plt.subplots(1, 4, figsize=(17, 4.2))
    for ax, (k, title, sc) in zip(axs, keys):
        M = np.array([[grid[(it, su)][k] * sc for su in subs_list]
                      for it in iters_list], dtype=float)
        im = ax.imshow(M, origin="lower", aspect="auto", cmap="viridis")
        ax.set_xticks(range(len(subs_list))); ax.set_xticklabels(subs_list)
        ax.set_yticks(range(len(iters_list))); ax.set_yticklabels(iters_list)
        ax.set_xlabel("substeps"); ax.set_ylabel("iterations")
        ax.set_title(title, fontsize=9)
        for i in range(len(iters_list)):
            for j in range(len(subs_list)):
                v = M[i, j]
                ax.text(j, i, f"{v:.1f}" if abs(v) < 1e4 else f"{v:.0f}",
                        ha="center", va="center", color="w", fontsize=7)
        fig.colorbar(im, ax=ax, fraction=0.046)
    fig.suptitle(f"{scene} / {solver} — iterations×substeps sweep "
                 f"(two-way coupling robustness)", fontsize=11)
    fig.tight_layout()
    p = os.path.join(OUT, f"sweep_{scene}_{solver}.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


def fig_schematic(anno):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    boxes = [(1.5, 4.2, f"IMPACTOR\ndrops on slab\nKE ≈ {anno['imp']:.0f} J"),
             (5.0, 4.2, f"SLAB modal ring\n(reduced coord q)\npeak ≈ {anno['slab']:.0f} mJ"),
             (8.5, 4.2, f"RESTING object\n(+impactor rebound)\n≈ {anno['rest']:.0f} mJ launch")]
    for x, y, txt in boxes:
        ax.add_patch(plt.Rectangle((x - 1.15, y - 0.7), 2.3, 1.4, fc="#eef", ec="k"))
        ax.text(x, y, txt, ha="center", va="center", fontsize=9)
    ax.annotate("", xy=(3.8, 4.2), xytext=(2.7, 4.2),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color="C0"))
    ax.text(3.25, 4.55, "impact", ha="center", fontsize=8, color="C0")
    ax.annotate("", xy=(7.3, 4.5), xytext=(6.2, 4.5),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color="C2"))
    ax.text(6.75, 4.9, "slab → object\n(ring launches it)", ha="center",
            fontsize=8, color="C2")
    ax.annotate("", xy=(6.2, 3.9), xytext=(7.3, 3.9),
                arrowprops=dict(arrowstyle="-|>", lw=2.2, color="C3"))
    ax.text(6.75, 3.35, "object → slab\n(landing re-rings)", ha="center",
            fontsize=8, color="C3")
    ax.text(5.0, 2.0, "modal + contact damping → rest", ha="center",
            fontsize=8, color="gray")
    ax.annotate("", xy=(5.0, 2.4), xytext=(5.0, 3.4),
                arrowprops=dict(arrowstyle="-|>", lw=1.4, color="gray"))
    ax.set_title("Two-way energy loop (slab ⇄ object), native solvers\n"
                 "the green+red pair IS the loop — one shared contact "
                 "multiplier carries both directions", fontsize=11)
    fig.tight_layout()
    p = os.path.join(OUT, "schematic.png")
    fig.savefig(p, dpi=120); plt.close(fig)
    return p


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--solvers", default="avbd,xpbd")
    ap.add_argument("--quick", action="store_true",
                    help="2×2 sweep + 140 frames (smoke); else 3×3 + 200.")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    scenes = [s for s in args.scenes.split(",") if s]
    solvers = [s for s in args.solvers.split(",") if s]

    iters_list = [8, 16] if args.quick else [8, 16, 32]
    subs_list = [2, 4] if args.quick else [2, 4, 8]
    nf_detail = 140 if args.quick else 220
    nf_sweep = 120 if args.quick else 170

    summary_rows = [["scene", "solver", "iters", "substeps", "coupling",
                     "Eimp_peak_J", "Eslab_peak_mJ", "ErestKE_peak_mJ",
                     "Erest_launch_mJ", "slab_rings", "bounces", "max_lift_mm",
                     "Frest_peak_N", "Fimp_peak_N", "twoway_ratio", "finite"]]
    series_rows = [["scene", "solver", "step", "t_s", "Eimp_J", "Eslab_mJ",
                    "Erest_mJ", "ErestKE_mJ", "lift_mm", "min_gap_m",
                    "Fimp_sum_N", "Frest_sum_N"]]
    anno = {"imp": 0.0, "slab": 0.0, "rest": 0.0}

    for scene in scenes:
        fn = SCENES[scene]
        for solver in solvers:
            print(f"\n### {scene} / {solver} — detailed loop + control ###",
                  flush=True)
            # detailed two-way + one-way control at the reference (16,4).
            rec2 = run(fn, solver, iterations=16, substeps=4, n_frames=nf_detail,
                       freeze_qdot=False)
            rec1 = run(fn, solver, iterations=16, substeps=4, n_frames=nf_detail,
                       freeze_qdot=True)
            p = fig_loop(scene, solver, rec2)
            ratio = fig_control(scene, solver, rec2, rec1)
            # per-contact summed-force figure
            _fig_percontact(scene, solver, rec2)
            m2 = loop_metrics(rec2)
            print(f"  loop: Eimp={m2['Eimp_peak']:.1f}J Eslab={m2['Eslab_peak']*1e3:.0f}mJ "
                  f"objKE={m2['ErestKE_peak']*1e3:.1f}mJ bounces={m2['bounces']} "
                  f"rings={m2['slab_rings']} two/one-way={ratio:.1f}×  -> {os.path.basename(p)}")
            if scene == "shelf" and solver == "xpbd":
                anno = {"imp": m2["Eimp_peak"], "slab": m2["Eslab_peak"] * 1e3,
                        "rest": m2["Erest_launch"] * 1e3}
            # series CSV for the reference configs
            for f in range(len(rec2["t"])):
                series_rows.append([
                    scene, solver, f, f"{rec2['t'][f]:.5f}",
                    f"{rec2['Eimp'][f]:.6g}", f"{rec2['Eslab'][f]*1e3:.6g}",
                    f"{rec2['Erest'][f]*1e3:.6g}", f"{rec2['ErestKE'][f]*1e3:.6g}",
                    f"{rec2['ylift'][f]*1e3:.6g}", f"{rec2['gap'][f]:.6g}",
                    f"{rec2['Fimp'][f].sum():.4f}", f"{rec2['Frest'][f].sum():.4f}"])
            for cpl, rr in (("two_way", rec2), ("one_way", rec1)):
                mm = loop_metrics(rr)
                summary_rows.append([
                    scene, solver, 16, 4, cpl, f"{mm['Eimp_peak']:.4f}",
                    f"{mm['Eslab_peak']*1e3:.4f}", f"{mm['ErestKE_peak']*1e3:.4f}",
                    f"{mm['Erest_launch']*1e3:.4f}", mm["slab_rings"], mm["bounces"],
                    f"{mm['max_lift_mm']:.3f}", f"{mm['Frest_peak']:.2f}",
                    f"{mm['Fimp_peak']:.2f}", f"{ratio:.3f}", mm["finite"]])

            # ---- iterations × substeps sweep ----
            print(f"  sweep {len(iters_list)}×{len(subs_list)} (iters×substeps) ...",
                  flush=True)
            grid = {}
            for it in iters_list:
                for su in subs_list:
                    r2 = run(fn, solver, iterations=it, substeps=su,
                             n_frames=nf_sweep, freeze_qdot=False)
                    r1 = run(fn, solver, iterations=it, substeps=su,
                             n_frames=nf_sweep, freeze_qdot=True)
                    a, b = loop_metrics(r2), loop_metrics(r1)
                    tw = (a["ErestKE_peak"] / b["ErestKE_peak"]
                          if b["ErestKE_peak"] > 1e-12 else 0.0)
                    grid[(it, su)] = dict(twoway_ratio=tw, **a)
                    for cpl, mm in (("two_way", a), ("one_way", b)):
                        summary_rows.append([
                            scene, solver, it, su, cpl, f"{mm['Eimp_peak']:.4f}",
                            f"{mm['Eslab_peak']*1e3:.4f}",
                            f"{mm['ErestKE_peak']*1e3:.4f}",
                            f"{mm['Erest_launch']*1e3:.4f}", mm["slab_rings"],
                            mm["bounces"], f"{mm['max_lift_mm']:.3f}",
                            f"{mm['Frest_peak']:.2f}", f"{mm['Fimp_peak']:.2f}",
                            f"{tw:.3f}", mm["finite"]])
                    print(f"    iters={it:2d} subs={su}: Eslab={a['Eslab_peak']*1e3:7.0f}mJ "
                          f"objKE={a['ErestKE_peak']*1e3:7.1f}mJ bounces={a['bounces']:2d} "
                          f"two/one-way={tw:5.1f}×", flush=True)
            fig_sweep(scene, solver, grid, iters_list, subs_list)

    fig_schematic(anno)
    with open(os.path.join(OUT, "summary.csv"), "w", newline="") as fh:
        csv.writer(fh).writerows(summary_rows)
    with open(os.path.join(OUT, "loop_series.csv"), "w", newline="") as fh:
        csv.writer(fh).writerows(series_rows)
    print(f"\nwrote summary.csv, loop_series.csv, figures to {OUT}/")


def _fig_percontact(scene, solver, rec):
    """Stand-alone per-corner force figure (impactor + resting object)."""
    t = rec["t"]
    fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for c in range(rec["Fimp"].shape[1]):
        ax[0].plot(t, rec["Fimp"][:, c], lw=0.9, label=f"corner {c}")
    ax[0].set_ylabel("impactor force [N]")
    ax[0].set_title(f"{scene} / {solver} — per-contact-point force "
                    f"(impactor body {rec['impactor']})")
    ax[0].legend(fontsize=7, ncol=4); ax[0].grid(alpha=0.3)
    for c in range(rec["Frest"].shape[1]):
        ax[1].plot(t, rec["Frest"][:, c], lw=0.9, label=f"corner {c}")
    ax[1].set_ylabel("resting object force [N]"); ax[1].set_xlabel("sim time [s]")
    ax[1].set_title(f"resting object (body {rec['tracked_book']})")
    ax[1].legend(fontsize=7, ncol=4); ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"percontact_{scene}_{solver}.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
