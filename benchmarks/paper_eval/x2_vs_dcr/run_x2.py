#!/usr/bin/env python3
"""X2 — head-to-head vs original DCR (the C1 follow-up evidence).

The first figure a reviewer of a DCR follow-up looks for: the SAME scene under
three arms — (a) rigid-only, (b) paper-DCR (the post-solve forced-IIR distant
response), (c) the native modal constraint — and a distant-object
response-vs-distance curve. An impactor is dropped OFF to one side of a shelf/
table lined with resting "bystander" objects at increasing distance; we measure
each bystander's peak kinetic energy (the two-way response) vs its distance from
the impact.

Arms:
  * rigid-only  — `DCRWorld(dcr_enabled=False)`: no distant-response machinery.
  * paper-DCR   — `DCRWorld` + `ModalDCRCoupler` (Eq. 10 forced-IIR + post-solve
    Δv = d_max/h kick), `ConstraintSolver`. Hand-tuned: num_modes (+ C/β/r0 for
    the spatial variant, not used here), FEM material, Rayleigh damping.
  * native      — the X3 FEM-modal support (q a solver DOF, two-way + X1-passive).
    Tunables: relax + budget, shared across scenes.

Both modal arms use the SAME slab FEM operator (`scene_and_gt.build_fem` /
`build_fem_modal_scene`), so this is a method-level comparison on matched
geometry (like the paper vs SOFA), not a solver-controlled ablation.

Out: benchmarks/paper_eval/x2_vs_dcr/out/{x2_response_vs_distance.csv,.png,
     x2_capability.csv, manifest}
Run: .venv/bin/python benchmarks/paper_eval/x2_vs_dcr/run_x2.py
"""
from __future__ import annotations

import csv
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.rigid.energy import rigid_kinetic_energy as _rigid_ke_bodies
from dcr.dcr import ModalDCRCoupler, DCRWorld

from benchmarks.paper_eval.paper_config import write_manifest
from benchmarks.paper_eval.x3_ground_truth.scene_and_gt import (
    build_fem, run_native, SLAB, SCENE,
)
from benchmarks.paper_eval.x3_ground_truth.fem_modal_support import fix_corners

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

IMP_X = SCENE.impactor_x                         # 0.28 — off-centre drop
BYSTANDER_XS = (0.14, 0.0, -0.14, -0.28)         # row at increasing distance
DIST = np.array([abs(x - IMP_X) for x in BYSTANDER_XS])
TOP = SLAB.support_top
G = 9.81


# --------------------------------------------------------------------------- #
# paper-DCR / rigid-only arms (DCRWorld + ModalDCRCoupler over the SAME slab)  #
# --------------------------------------------------------------------------- #
def run_dcr_arm(dcr_enabled: bool, n_steps: int = 320) -> dict:
    h = 1e-3
    world = DCRWorld(h=h, solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2,
                     pgs_iterations=80), dcr_enabled=dcr_enabled)
    table = make_static_plane(normal=(0, 1, 0), point=(0, TOP, 0), friction=0.4)
    table_idx = world.add_body(table)
    fem = build_fem(SLAB)                          # SAME operator as native arm
    modal = ModalAnalysis(fem=fem, num_modes=16)
    world.add_dcr_coupler(ModalDCRCoupler(modal=modal, elastic_body_idx=table_idx))

    bh = SCENE.bystander_half
    by_idx = []
    for bx in BYSTANDER_XS:
        b = make_dynamic_box(SCENE.bystander_mass, bh[0], bh[1], bh[2],
                             position=(bx, TOP + bh[1] + 1e-3, 0.0),
                             restitution=0.0, friction=0.3)
        by_idx.append(world.add_body(b))
    ih = SCENE.impactor_half
    imp = make_dynamic_box(SCENE.impactor_mass, ih[0], ih[1], ih[2],
                           position=(IMP_X, TOP + ih[1] + SCENE.drop_height, 0.0),
                           restitution=0.0, friction=0.5)
    imp_idx = world.add_body(imp)

    # settle bystanders (impactor frozen, dcr off)
    world.bodies[imp_idx].is_static = True
    was = world.dcr_enabled
    world.dcr_enabled = False
    for _ in range(120):
        world.step()
    for i in by_idx:
        world.bodies[i].velocity[:] = 0.0
    y0 = [float(world.bodies[i].position[1]) for i in by_idx]
    world.bodies[imp_idx].is_static = False
    world.dcr_enabled = was

    peak_ke = np.zeros(len(by_idx))
    peak_lift = np.zeros(len(by_idx))
    cum_inj = 0.0
    for _ in range(n_steps):
        world.step()
        cum_inj += float(getattr(world, "last_dcr_ke_injected", 0.0))
        for j, i in enumerate(by_idx):
            b = world.bodies[i]
            ke = 0.5 * b.mass * float(b.velocity[:3] @ b.velocity[:3])
            peak_ke[j] = max(peak_ke[j], ke)
            peak_lift[j] = max(peak_lift[j], float(b.position[1]) - y0[j])
    return dict(peak_ke=peak_ke, peak_lift=peak_lift, cum_injected=cum_inj)


def main():
    os.makedirs(OUT, exist_ok=True)
    print("### X2 — head-to-head vs original DCR ###", flush=True)
    print(f"impact @ x={IMP_X}; bystanders {BYSTANDER_XS}; dist {np.round(DIST,3)}",
          flush=True)

    print("[rigid-only] …", flush=True)
    rigid = run_dcr_arm(dcr_enabled=False)
    print(f"   peak KE (mJ): {np.round(rigid['peak_ke']*1e3,3)}", flush=True)

    print("[paper-DCR] …", flush=True)
    dcr = run_dcr_arm(dcr_enabled=True)
    print(f"   peak KE (mJ): {np.round(dcr['peak_ke']*1e3,3)}  "
          f"injected={dcr['cum_injected']:.4g} J", flush=True)

    print("[native] …", flush=True)
    nv = run_native(solver="avbd", num_modes=16, bystander_xs=BYSTANDER_XS,
                    n_frames=220, relax=1.0, h=1.0 / 240.0)
    nv_ke = nv["by_ke"]
    print(f"   peak KE (mJ): {np.round(nv_ke*1e3,3)}", flush=True)

    # ---- response-vs-distance figure ----
    order = np.argsort(DIST)
    d = DIST[order]
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    ax.plot(d, rigid["peak_ke"][order] * 1e3, "s-", color="0.5",
            label="rigid-only (no response)")
    ax.plot(d, dcr["peak_ke"][order] * 1e3, "o-C1", label="paper-DCR (forced-IIR)")
    ax.plot(d, nv_ke[order] * 1e3, "^-C0", label="native modal constraint")
    ax.set_xlabel("distance from impact  |x − x_impact|  [m]")
    ax.set_ylabel("distant-object peak KE  [mJ]")
    ax.set_title("X2  Distant-response vs distance — rigid-only / paper-DCR / "
                 "native\n(off-centre impact on the same slab operator)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "x2_response_vs_distance.png"), dpi=120)
    plt.close(fig)

    with open(os.path.join(OUT, "x2_response_vs_distance.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["bystander_x", "dist_m", "rigid_peakKE_mJ",
                    "dcr_peakKE_mJ", "native_peakKE_mJ",
                    "rigid_lift_mm", "dcr_lift_mm", "native_lift_mm"])
        for j, bx in enumerate(BYSTANDER_XS):
            w.writerow([bx, f"{DIST[j]:.3f}", f"{rigid['peak_ke'][j]*1e3:.4f}",
                        f"{dcr['peak_ke'][j]*1e3:.4f}", f"{nv_ke[j]*1e3:.4f}",
                        f"{rigid['peak_lift'][j]*1e3:.4f}",
                        f"{dcr['peak_lift'][j]*1e3:.4f}",
                        f"{nv['by_lift'][j]*1e3:.4f}"])

    # ---- capability table ----
    cap = [
        ("distant-response machinery", "none", "post-solve forced-IIR kick",
         "in-solver modal DOF (two-way)"),
        ("hand-tuned response params", "0", "num_modes, C/β/r0 (spatial), "
         "Rayleigh α0/α1", "relax + budget (shared)"),
        ("energy-bounded (passive)", "n/a (rigid)", "NO (double-counts, see X7)",
         "YES (X1 clamp, ≤ loss)"),
        ("back-reaction: support sag under load", "no", "no (one-way kick)",
         "yes (q co-solved)"),
        ("back-reaction: re-ring on object landing", "no", "no", "yes"),
        ("ground-truth-validated magnitude", "n/a", "not shown", "yes (X3)"),
    ]
    with open(os.path.join(OUT, "x2_capability.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["capability", "rigid-only", "paper-DCR", "native"])
        for row in cap:
            w.writerow(row)

    write_manifest(OUT, "x2_response_vs_distance",
                   scenes=["offcentre_shelf_row"],
                   solvers=["rigid", "paper-dcr", "native-avbd"],
                   note="response-vs-distance, 3 arms, matched slab operator; "
                        "native injected via in-solver modal DOF",
                   bystander_xs=list(BYSTANDER_XS), impact_x=IMP_X,
                   dcr_injected_J=dcr["cum_injected"])
    print(f"\nwrote x2_* to {OUT}/", flush=True)


if __name__ == "__main__":
    main()
