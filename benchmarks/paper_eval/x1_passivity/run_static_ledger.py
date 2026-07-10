#!/usr/bin/env python3
"""X1d — static contact-force ledger on ledge and shelf (matrix row 3).

Extends the cargo-stack ledger (§4.1, `benchmarks/network/
report_sheldon_contact_forces.py`) to the other two contact-rich scenes: after
the scene settles, each body's summed support-contact multiplier must equal the
analytic weight it carries (Σ|λ_N| = m·g per resting body; Σ over all support
rows = total supported weight). Read-only solver introspection — the same
`lambdas()/active()/_support_row_cidx` API as the stack report; no solver code
touched. AVBD at the paper configuration (16×4, relax 0.7).

The support rows are re-scanned every frame (the contact set changes as the
impactor lands), and the settled value is the tail mean over the last
`--tail` frames, with the tail std reported so an un-settled body is visible.

Out: benchmarks/paper_eval/x1_passivity/out/static_ledger.csv + manifest
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_static_ledger.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from dcr.avbd._solver.solver_6dof import BOX_BOX_CONTACT_6DOF
from benchmarks.paper_eval.paper_config import PAPER_CONFIG, apply_relax, \
    write_manifest

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES = {"ledge": build_reduced_ledge, "shelf": build_reduced_shelf}
G = 9.81


def support_force_by_avbd(sol, n_slots):
    """Σ|λ_N| of the ACTIVE support rows per AVBD body index (re-scanned:
    the row set changes as the impactor lands / bodies topple off)."""
    lam = sol.lambdas()
    act = sol.active()
    F = np.zeros(n_slots)
    for cidx in sol._support_row_cidx:
        b = int(sol._rows[cidx].body_a)
        if 0 <= b < n_slots and act[cidx]:
            F[b] += abs(float(lam[cidx]))
    return F


def boxbox_joint_forces(sol, name_of):
    """Per box-box joint: Σ|λ_N| over its active rows (sheldon-report API)."""
    lam = sol.lambdas()
    act = sol.active()
    ct = sol.c_type.numpy()
    ba = sol.c_body_a.numpy()
    bb = sol.c_body_b.numpy()
    ns = sol._gpu_pool_n_static
    na = min(int(sol.n_active_rows.numpy()[0]), sol._gpu_pool_n_capacity)
    box = {}
    for c in range(ns, na):
        if act[c] == 0 or int(ct[c]) != BOX_BOX_CONTACT_6DOF:
            continue
        a, b = int(ba[c]), int(bb[c])
        if a in name_of and b in name_of:
            key = tuple(sorted((name_of[a], name_of[b])))
            box[key] = box.get(key, 0.0) + abs(float(lam[c]))
    return box


def run_scene(name, build_fn, steps, tail):
    H = build_fn(device="cpu", iterations=PAPER_CONFIG["iterations"],
                 avbd_substeps=PAPER_CONFIG["substeps"], solver="avbd")
    sol = H.world._solver
    apply_relax(sol, "avbd")
    sol._modal_symplectic = True
    w = H.world
    # contact rows carry AVBD solver body indices, not dcr indices
    avbd_of = {}
    for b in H.bodies:
        ab = w._descs[b.dcr_idx].avbd_body
        if ab is not None:
            avbd_of[b.name] = int(ab.index)
    name_of = {v: k for k, v in avbd_of.items()}
    mass_of = {b.name: float(w._descs[b.dcr_idx].dcr_body.mass)
               for b in H.bodies}
    n_slots = max(avbd_of.values()) + 1
    hist = np.zeros((steps, n_slots))
    joints = {}
    for i in range(steps):
        w.step()
        hist[i] = support_force_by_avbd(sol, n_slots)
        for key, f in boxbox_joint_forces(sol, name_of).items():
            joints.setdefault(key, np.zeros(steps))[i] = f
    rows = []
    total_meas = total_exp = 0.0
    # settled box-box joints: which body rests on which (for the expected loads)
    settled_joint = {key: float(tr[-tail:].mean())
                     for key, tr in joints.items()
                     if tr[-tail:].mean() > 1e-3}
    riders = {}      # body -> Σ weight of bodies it carries through box-box
    for (na_, nb_), f in settled_joint.items():
        # the lighter/lower body pairing: attribute the rider by mass ordering
        # (in these scenes the rider is always the lighter body)
        rider, carrier = ((na_, nb_) if mass_of[na_] < mass_of[nb_]
                          else (nb_, na_))
        riders[carrier] = riders.get(carrier, 0.0) + mass_of[rider] * G
    for b in H.bodies:
        m = mass_of[b.name]
        exp = m * G + riders.get(b.name, 0.0)   # own weight + what it carries
        col = hist[:, avbd_of[b.name]]
        f_tail = col[-tail:]
        meas, std = float(f_tail.mean()), float(f_tail.std())
        supported = meas > 0.05 * exp
        if supported:
            total_meas += meas
            total_exp += exp
        rows.append(dict(scene=name, kind="support", body=b.name, mass=m,
                         expected_N=exp, measured_N=meas, tail_std_N=std,
                         err_pct=100.0 * abs(meas - exp) / exp,
                         supported=supported))
        print(f"  {name:6s} {b.name:14s} m={m:7.3f} kg  "
              f"F={meas:8.3f} ± {std:6.3f} N  exp={exp:8.3f} N  "
              f"err={100.0 * abs(meas - exp) / exp:5.2f}%"
              f"{'' if supported else '  [off support]'}", flush=True)
    for (na_, nb_), f in sorted(settled_joint.items()):
        rider = na_ if mass_of[na_] < mass_of[nb_] else nb_
        exp = mass_of[rider] * G
        rows.append(dict(scene=name, kind="boxbox", body=f"{na_}<->{nb_}",
                         mass=mass_of[rider], expected_N=exp, measured_N=f,
                         tail_std_N=0.0,
                         err_pct=100.0 * abs(f - exp) / exp, supported=True))
        print(f"  {name:6s} joint {na_}<->{nb_}: F={f:8.3f} N  "
              f"exp={exp:8.3f} N  err={100.0 * abs(f - exp) / exp:5.2f}%",
              flush=True)
    err_tot = 100.0 * abs(total_meas - total_exp) / max(total_exp, 1e-12)
    rows.append(dict(scene=name, kind="support", body="TOTAL(supported)",
                     mass=total_exp / G, expected_N=total_exp,
                     measured_N=total_meas, tail_std_N=0.0, err_pct=err_tot,
                     supported=True))
    print(f"  {name:6s} TOTAL          F={total_meas:8.3f} N  "
          f"exp={total_exp:8.3f} N  err={err_tot:5.2f}%", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=480)   # 4 s at h=1/120
    ap.add_argument("--tail", type=int, default=60)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    print(f"### X1d static ledger (AVBD {PAPER_CONFIG['iterations']}x"
          f"{PAPER_CONFIG['substeps']}, {args.steps} steps, "
          f"tail {args.tail}) ###", flush=True)
    rows = []
    for name, fn in SCENES.items():
        rows += run_scene(name, fn, args.steps, args.tail)
    keys = list(rows[0].keys())
    with open(os.path.join(OUT, "static_ledger.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(OUT, "static_ledger.csv", scenes=list(SCENES),
                   solvers=["avbd"],
                   note=f"settled support-contact ledger, tail={args.tail} "
                        f"of {args.steps} steps")
    print(f"\nwrote static_ledger.csv ({len(rows)} rows) to {OUT}/")


if __name__ == "__main__":
    main()
