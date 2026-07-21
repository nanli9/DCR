#!/usr/bin/env python3
"""E-R1 — modes-off topple control on the ledge (paper repositioning, 2026-07-13).

Two arms of the SAME ledge run at the paper configuration (16x4, relax 0.7,
symplectic modal step, h = 1/120; the static-ledger protocol of x1):

  * native — the two-way modal constraint, production path;
  * frozen — identical run with ``sol._modal_freeze_qdot = True``: the
    support's modal ring is frozen (q-dot = 0 predictor, quasi-static modes)
    — the same R-arm counterfactual the x5 stress test uses — so the ONLY
    channel removed is the transmitted vibration.

Question (paper 40_results E-R1): the native run knocks a pillar off the
pedestal.  Does that pillar survive when the ring is frozen?  If yes, the
topple is a rigid outcome caused by transmitted vibration (a two-way
capability result); if it topples anyway, the ring is not the cause and the
paper must say so.  Either way the numbers below are reported honestly.

Read-only solver introspection (poses + modal mirrors); no solver code
touched.

Out: benchmarks/paper_eval/er1_topple_control/out/topple_control.csv (+ manifest)
Run: .venv/bin/python benchmarks/paper_eval/er1_topple_control/run_topple_control.py
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

from scenes.reduced_ledge import build_reduced_ledge
from benchmarks.paper_eval.paper_config import PAPER_CONFIG, apply_relax, \
    write_manifest

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

TILT_TOPPLED_DEG = 45.0    # fallen over
TILT_SURVIVED_DEG = 10.0   # still standing (settled lean tolerance)


def _up_world(q_xyzw: np.ndarray) -> np.ndarray:
    """Body +y axis in world frame from the solver's xyzw quaternion."""
    x, y, z, w = (float(v) for v in q_xyzw)
    return np.array([2.0 * (x * y - w * z),
                     1.0 - 2.0 * (x * x + z * z),
                     2.0 * (y * z + w * x)])


def run_arm(arm: str, steps: int):
    """One ledge run; returns (per-pillar records, ring diagnostic)."""
    H = build_reduced_ledge(device="cpu",
                            iterations=PAPER_CONFIG["iterations"],
                            avbd_substeps=PAPER_CONFIG["substeps"],
                            solver="avbd")
    sol = H.world._solver
    apply_relax(sol, "avbd")
    sol._modal_symplectic = True
    if arm == "frozen":
        assert hasattr(sol, "_modal_freeze_qdot"), \
            "frozen arm needs the x5 freeze switch"
        sol._modal_freeze_qdot = True
    w = H.world

    # Poses live in the AVBD solver state (the dcr_body mirror is not synced
    # per step on this branch) — read them the way the viser renderer does.
    avbd_of = {b.name: int(w._descs[b.dcr_idx].avbd_body.index)
               for b in H.bodies if w._descs[b.dcr_idx].avbd_body is not None}
    pillars = [b for b in H.bodies if b.render_kind == "pillar"]
    P, Q = sol.positions(), sol.orientations()
    ped_top_y = float(P[avbd_of["pedestal"]][1]) + 0.045  # pedestal half-height
    y0 = {p.name: float(P[avbd_of[p.name]][1]) for p in pillars}

    def tilt_deg(q_xyzw) -> float:
        up = _up_world(q_xyzw)
        return float(np.degrees(np.arccos(np.clip(up[1], -1.0, 1.0))))

    max_tilt = {p.name: 0.0 for p in pillars}
    max_qdot = 0.0                                       # ring diagnostic
    for _ in range(steps):
        w.step()
        P, Q = sol.positions(), sol.orientations()
        for p in pillars:
            max_tilt[p.name] = max(max_tilt[p.name],
                                   tilt_deg(Q[avbd_of[p.name]]))
        qd = sol.modal_qdot
        if qd is not None:
            max_qdot = max(max_qdot, float(np.max(np.abs(qd))))

    recs = []
    P, Q = sol.positions(), sol.orientations()
    for p in pillars:
        i = avbd_of[p.name]
        t_fin = tilt_deg(Q[i])
        y_fin = float(P[i][1])
        off_pedestal = y_fin < ped_top_y                # base fell to the slab
        if t_fin > TILT_TOPPLED_DEG or off_pedestal:
            outcome = "toppled/off"
        elif t_fin < TILT_SURVIVED_DEG:
            outcome = "survived"
        else:
            outcome = "leaning"
        recs.append(dict(arm=arm, pillar=p.name, outcome=outcome,
                         tilt_final_deg=round(t_fin, 2),
                         tilt_max_deg=round(max_tilt[p.name], 2),
                         y_final_m=round(y_fin, 4),
                         y_drop_m=round(y0[p.name] - y_fin, 4),
                         off_pedestal=off_pedestal))
    return recs, max_qdot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=480)   # 4 s at h=1/120 (x1d)
    args = ap.parse_args()
    print(f"### E-R1 topple control (AVBD {PAPER_CONFIG['iterations']}x"
          f"{PAPER_CONFIG['substeps']}, relax {PAPER_CONFIG['relax']}, "
          f"symplectic, {args.steps} steps) ###", flush=True)
    rows = []
    ring = {}
    for arm in ("native", "frozen"):
        recs, max_qdot = run_arm(arm, args.steps)
        ring[arm] = max_qdot
        rows += recs
        print(f"\n[{arm}]  max |q_dot| (support ring) = {max_qdot:.3e}")
        for r in recs:
            print(f"  {r['pillar']:>9}: {r['outcome']:<11} "
                  f"tilt final {r['tilt_final_deg']:6.2f} deg  "
                  f"max {r['tilt_max_deg']:6.2f} deg  "
                  f"y drop {r['y_drop_m']*1000:6.1f} mm  "
                  f"off_pedestal={r['off_pedestal']}")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "topple_control.csv")
    with open(path, "w", newline="") as fh:
        wcsv = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        wcsv.writeheader()
        wcsv.writerows(rows)
    write_manifest(OUT, "topple_control.csv", steps=args.steps,
                   ring_max_qdot=ring,
                   note="E-R1 modes-off (frozen-ring) topple control, "
                        "ledge @ paper config; x1d static-ledger protocol")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
