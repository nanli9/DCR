#!/usr/bin/env python3
"""E2 + E3 — ledge FEM-GT convergence ladder + distant-response falloff.

Drives `ledge_scene_gt.py`:
  E2: native peak slab-deflection / GT peak vs rigid step h ∈ {1/120..1/960};
      ring frequency (FFT of the impact-point trace) native vs GT; GT self-trust
      (halve h_fine, field change < 2%); shared-operator gate (native ω == eigsh).
  E3: peak |u_y| vs distance along the probe line (impact +0.30 -> far -0.30),
      native (paper step) vs GT; Spearman ρ(native, GT).

Out: out/ledge_convergence.csv, out/ledge_falloff.csv, out/ledge_gt.config.json
Run: ~/dcr-venv/bin/python benchmarks/paper_eval/x3_ground_truth/run_ledge_ladder.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.x3_ground_truth.ledge_scene_gt import (
    LEDGE, PROBE_XZ, build_ledge_fem, run_ledge_gt, run_ledge_native)
from benchmarks.paper_eval.x3_ground_truth.fem_modal_support import make_fem_modal_support
from dcr.modal.modal_analysis import ModalAnalysis
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
H_LADDER = [1.0 / 120, 1.0 / 240, 1.0 / 480, 1.0 / 960]
GT_HFINE = 5e-5


def dominant_hz(trace, dt, fmin=20.0, fmax=600.0):
    """Peak spectral frequency of a probe trace (detrended)."""
    x = np.asarray(trace, float)
    if x.size < 8:
        return 0.0
    x = x - x.mean()
    win = np.hanning(x.size)
    sp = np.abs(np.fft.rfft(x * win))
    fr = np.fft.rfftfreq(x.size, d=dt)
    band = (fr >= fmin) & (fr <= fmax)
    if not band.any():
        return 0.0
    return float(fr[band][np.argmax(sp[band])])


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    ra = ra - ra.mean(); rb = rb - rb.mean()
    d = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / d) if d > 0 else 0.0


def main():
    os.makedirs(OUT, exist_ok=True)
    spec = LEDGE

    # ---- shared-operator gate --------------------------------------------- #
    fem = build_ledge_fem(spec)
    rs, modal = make_fem_modal_support(fem, num_modes=24, y_rest=spec.top,
                                       n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
                                       probe_xz=PROBE_XZ, length=spec.length,
                                       width=spec.width)
    ma = ModalAnalysis(fem=fem, num_modes=24)
    gate = float(np.max(np.abs(np.asarray(modal.eigenvalues) - np.asarray(ma.eigenvalues))))
    print(f"[gate] shared-operator |Δλ|max = {gate:.3e}", flush=True)

    # ---- converged GT + self-trust ---------------------------------------- #
    print("[gt] running converged GT (h_fine=5e-5)...", flush=True)
    gt = run_ledge_gt(spec=spec, h_fine=GT_HFINE, record_every=40)
    peak_gt = float(np.max(np.abs(gt["field"])))
    ped_gt = float(np.max(np.abs(gt["probe"][:, 3])))          # pedestal (x=0)
    fring_gt = dominant_hz(gt["probe"][:, 0], np.diff(gt["times"]).mean())
    falloff_gt = np.max(np.abs(gt["probe"]), axis=0)           # per probe distance
    print(f"[gt] peak|u_y|={peak_gt:.3e} m, ped={ped_gt:.3e}, f_ring={fring_gt:.1f} Hz, "
          f"sim={gt['sim_s']:.3f}s wall={gt['wall_s']:.1f}s", flush=True)

    print("[gt] self-trust GT at h_fine=2.5e-5...", flush=True)
    gt2 = run_ledge_gt(spec=spec, h_fine=GT_HFINE / 2, record_every=80)
    peak_gt2 = float(np.max(np.abs(gt2["field"])))
    gt_selftrust = abs(peak_gt2 - peak_gt) / max(peak_gt, 1e-12)
    print(f"[gt] self-trust: peak change {gt_selftrust*100:.2f}% (want < 2%)", flush=True)

    # ---- native h-ladder --------------------------------------------------- #
    conv_rows = []
    native_paper = None
    for h in H_LADDER:
        nat = run_ledge_native(spec=spec, h=h, n_frames=int(round(320 * (1/240) / h)))
        peak_nat = float(np.max(np.abs(nat["field"])))
        ped_nat = float(np.max(np.abs(nat["probe"][:, 3])))
        fring_nat = dominant_hz(nat["probe"][:, 0], nat["dt"])
        conv_rows.append(dict(
            h=h, h_inv=int(round(1/h)), modes=nat["num_modes"],
            peak_native=peak_nat, peak_gt=peak_gt,
            ratio_peak=peak_nat / max(peak_gt, 1e-12),
            ped_native=ped_nat, ped_gt=ped_gt,
            ratio_ped=ped_nat / max(ped_gt, 1e-12),
            f_ring_native=fring_nat, f_ring_gt=fring_gt,
            f_ring_err_pct=100.0 * abs(fring_nat - fring_gt) / max(fring_gt, 1e-9),
            wall_s=nat["wall_s"]))
        if abs(1/h - 240) < 1:
            native_paper = nat
        print(f"[native] h=1/{int(round(1/h)):<4} peak={peak_nat:.3e} "
              f"ratio={peak_nat/max(peak_gt,1e-12):.3f} ped_ratio={ped_nat/max(ped_gt,1e-12):.3f} "
              f"f_ring={fring_nat:.1f} vs {fring_gt:.1f} Hz", flush=True)

    # ---- falloff (E3), native at paper step vs GT ------------------------- #
    if native_paper is None:
        native_paper = run_ledge_native(spec=spec, h=1.0/240, n_frames=320)
    falloff_nat = np.max(np.abs(native_paper["probe"]), axis=0)
    dist = np.array([abs(x - PROBE_XZ[0][0]) for (x, z) in PROBE_XZ])   # dist from impact
    rho = spearman(falloff_nat, falloff_gt)
    print(f"[falloff] Spearman ρ(native,GT) = {rho:.3f} (want ≥ 0.8)", flush=True)

    # ---- write CSVs -------------------------------------------------------- #
    ck = ["h", "h_inv", "modes", "peak_native", "peak_gt", "ratio_peak",
          "ped_native", "ped_gt", "ratio_ped", "f_ring_native", "f_ring_gt",
          "f_ring_err_pct", "wall_s"]
    with open(os.path.join(OUT, "ledge_convergence.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=ck); w.writeheader()
        for r in conv_rows:
            w.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k]) for k in ck})
    with open(os.path.join(OUT, "ledge_falloff.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["probe_x", "dist_from_impact_m", "resp_native", "resp_gt"])
        for (x, z), d, rn, rg in zip(PROBE_XZ, dist, falloff_nat, falloff_gt):
            w.writerow([x, f"{d:.4g}", f"{rn:.6g}", f"{rg:.6g}"])

    with open(os.path.join(OUT, "ledge_gt.config.json"), "w") as fh:
        json.dump(dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       scene="ledge (slab support + boulder impactor + pedestal responder)",
                       spec=dict(length=spec.length, width=spec.width, thickness=spec.thickness,
                                 E=spec.E, rho=spec.rho, boulder_mass=spec.boulder_mass,
                                 boulder_drop=spec.boulder_drop),
                       shared_operator_gate=gate, gt_hfine=GT_HFINE,
                       gt_selftrust_pct=gt_selftrust * 100, f_ring_gt_hz=fring_gt,
                       spearman_falloff=rho, h_ladder=[int(round(1/h)) for h in H_LADDER],
                       note="E2 pre-topple deflection-field convergence (linear regime, "
                            "softened E); E3 falloff along probe line"), fh, indent=2)
    print(f"\n[done] gate={gate:.2e} gt_selftrust={gt_selftrust*100:.2f}% "
          f"ratio {conv_rows[0]['ratio_peak']:.2f}→{conv_rows[-1]['ratio_peak']:.2f} "
          f"ρ={rho:.2f}. wrote ledge_convergence.csv + ledge_falloff.csv")


if __name__ == "__main__":
    main()
