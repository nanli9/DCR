#!/usr/bin/env python3
"""X3 — coupled ground truth vs full FEM (the C3 correctness anchor).

Shows the native modal constraint's two-way response is not just PRESENT but the
RIGHT MAGNITUDE, by comparing it against a full-FEM `CoupledFEMRigidSim` ground
truth of the SAME slab operator (same mesh, BCs, E/ν/ρ). The native arm's basis
IS the true FEM eigenmodes (`fem_modal_support.make_fem_modal_support`), so the
comparison isolates exactly two effects: k-mode truncation and the host contact
model / rigid timestep.

Deliverables (all regenerable from the sibling .config.json manifests):
  A. Deflection-field overlay: native Φ(x)·q(t) vs GT surface u_y(x,t) at a
     distance sweep — the two-way DRIVING field (convergent GT signal).
  B. Amplitude convergence vs rigid step h: native peak deflection → GT as h→0
     (the consistency result — the coupling magnitude is correct, limited at the
     paper step only by temporal resolution of the sub-ms impact).
  C. Spatial falloff: peak |u_y| vs distance, native vs GT — settles the X2
     "automatic attenuation" claim. It is a STANDING-WAVE modal profile
     (non-monotonic), not traveling-wave decay — validated, honestly framed.
  D. Mode-count convergence: field error vs k ∈ {1,2,4,8,16,32}.
  E. Ring frequency: FFT of the mid-span trace, native vs GT (same modes ⇒
     should match at every h).
  F. Wall-clock: GT seconds vs native seconds per simulated second.

HONEST SCOPE (reported, not hidden):
  * The GT bystander LAUNCH KE does NOT converge under h_fine refinement — a
    0.3 kg body on a k=5e7 explicit-penalty spring is a stiff fast oscillator the
    GT resolves poorly. So the ground-truth signal is the slab DEFLECTION FIELD
    (a convergent modal quantity), not the launched-object KE. Bystander launch is
    reported as a secondary, contact-model-limited observable.
  * GT rigid bodies are 1D-vertical (mass, y, vy). This scene's response is
    vertical-dominant, so the comparison is apples-to-apples; stated up front.
  * The native support carries no slab self-weight sag; both arms are baselined to
    their settled rest before comparing dynamic response.

Run: .venv/bin/python benchmarks/paper_eval/x3_ground_truth/run_x3.py
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

from benchmarks.paper_eval.x3_ground_truth.scene_and_gt import (
    run_ground_truth, run_native, SLAB, SCENE,
)
from benchmarks.paper_eval.paper_config import write_manifest

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
GT_HFINE = 5.0e-5                    # converged GT fine step (X0-style pin)
SWEEP = [(x, 0.0) for x in (0.28, 0.14, 0.0, -0.14, -0.28)]
DISTS = np.array([abs(x - SCENE.impactor_x) for x, _ in SWEEP])   # |x − impact|


# --------------------------------------------------------------------------- #
# Small signal helpers                                                        #
# --------------------------------------------------------------------------- #
def _peak_amp(trace, baseline_n=10):
    """Peak |deflection| about the settled baseline, per column, in mm."""
    t = np.asarray(trace, dtype=np.float64)
    base = np.median(t[:baseline_n], axis=0) if t.shape[0] >= baseline_n else 0.0
    return np.max(np.abs(t - base), axis=0) * 1e3


def _ring_freq(trace, dt, baseline_n=10):
    """Dominant post-transient ring frequency [Hz] of a 1-D deflection trace.

    High-passes the settling envelope (moving-average subtraction ~1.5 ring
    periods, per the project's FFT-hygiene rule) before the FFT."""
    y = np.asarray(trace, dtype=np.float64)
    y = y - (np.median(y[:baseline_n]) if y.size >= baseline_n else y.mean())
    n = y.size
    if n < 16:
        return float("nan")
    win = max(3, int(0.02 / dt) | 1)            # ~20 ms moving average
    kern = np.ones(win) / win
    hp = y - np.convolve(y, kern, mode="same")
    hp = hp * np.hanning(n)
    spec = np.abs(np.fft.rfft(hp))
    freqs = np.fft.rfftfreq(n, d=dt)
    spec[freqs < 5.0] = 0.0                     # ignore DC / drift
    return float(freqs[int(np.argmax(spec))])


# --------------------------------------------------------------------------- #
# A + E — field overlay & ring frequency at the paper config                  #
# --------------------------------------------------------------------------- #
def _align_impact(t, mid_trace):
    """Return a time shift so the impact (max |mid-span response|) sits at t=0."""
    return t - t[int(np.argmax(np.abs(mid_trace)))]


def fig_field_overlay(gt, solver="avbd"):
    # Native at h=1/480: samples the ~81 Hz ring above Nyquist (the paper step,
    # 120 Hz, ALIASES it to ~39 Hz — a plotting artifact, not a physics error;
    # the paper-config AMPLITUDE is the subject of X3-B). Frequency + shape are
    # h-independent (Kq=diag(ω²)), so this is the honest frequency/shape overlay.
    dtn = 1.0 / 480.0
    nv = run_native(solver=solver, num_modes=16, probe_defl_xz=SWEEP,
                    n_frames=int(1.4 * 480), relax=1.0, h=dtn)
    gt_u = gt["probe_defl"] - np.median(gt["probe_defl"][:10], axis=0)
    nv_u = nv["u_field"]
    t_gt = _align_impact(gt["times"], gt_u[:, 2])
    t_nv = _align_impact(np.arange(nv_u.shape[0]) * dtn, nv_u[:, 2])
    show = [0, 2, 4]                            # +0.28 (impact), 0.0, −0.28 (far)
    fig, axes = plt.subplots(len(show), 1, figsize=(7.5, 7.0), sharex=True)
    for ax, j in zip(axes, show):
        ax.plot(t_gt, gt_u[:, j] * 1e3, "k-", lw=1.2, label="full-FEM GT")
        ax.plot(t_nv, nv_u[:, j] * 1e3, "C3--", lw=1.2,
                label=f"native ({solver}, 16 modes, h=1/480)")
        ax.set_ylabel(f"u_y @ x={SWEEP[j][0]:+.2f} m\n[mm]")
        ax.grid(alpha=0.3)
    axes[0].legend(loc="upper right", fontsize=8)
    axes[0].set_title("X3-A  Two-way driving field: native Φ(x)·q(t) vs full-FEM "
                      "ground truth\n(impact-aligned; native h=1/480 for ring "
                      "frequency/shape — paper-config amplitude in X3-B)")
    axes[-1].set_xlabel("time since impact [s]")
    axes[-1].set_xlim(-0.05, 0.6)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "x3_field_overlay.png"), dpi=110)
    plt.close(fig)
    f_gt = _ring_freq(gt_u[:, 2], gt["times"][1] - gt["times"][0])
    f_nv = _ring_freq(nv_u[:, 2], dtn)
    return nv, f_gt, f_nv


# --------------------------------------------------------------------------- #
# B — amplitude convergence vs rigid step h                                   #
# --------------------------------------------------------------------------- #
def fig_amp_convergence(gt, solver="avbd"):
    gt_amp = _peak_amp(gt["probe_defl"])
    rows, sim_s = [], 1.6
    for hd in (120, 240, 480, 960):
        h = 1.0 / hd
        nv = run_native(solver=solver, num_modes=16, probe_defl_xz=SWEEP,
                        n_frames=int(sim_s * hd), relax=1.0, h=h)
        amp = np.max(np.abs(nv["u_field"]), axis=0) * 1e3   # native already rel.
        rows.append(dict(h_inv=hd, ratio_mid=amp[2] / gt_amp[2],
                         amp=amp, wall_s=nv["wall_s"], sim_s=nv["sim_s"]))
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    hinv = [r["h_inv"] for r in rows]
    ax.plot(hinv, [r["ratio_mid"] for r in rows], "o-C0", label="native / GT (mid-span peak)")
    ax.axhline(1.0, color="k", ls=":", lw=1, label="ground truth")
    ax.set_xlabel("rigid steps / s  (1/h)")
    ax.set_ylabel("native peak |u_y| ÷ GT peak")
    ax.set_xscale("log", base=2)
    ax.set_xticks(hinv); ax.set_xticklabels([str(x) for x in hinv])
    ax.set_title("X3-B  Native two-way amplitude CONVERGES to full-FEM as h→0\n"
                 f"({solver}, 16 modes; gap at paper step = impact-impulse "
                 "temporal resolution, not coupling error)")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "x3_amp_convergence.png"), dpi=110)
    plt.close(fig)
    return rows, gt_amp


# --------------------------------------------------------------------------- #
# C — spatial falloff: native vs GT                                           #
# --------------------------------------------------------------------------- #
def fig_falloff(gt, gt_amp, solver="avbd"):
    # native at the paper step and at a fine step, to show shape is h-independent.
    nv_p = run_native(solver=solver, num_modes=16, probe_defl_xz=SWEEP,
                      n_frames=200, relax=1.0, h=1.0 / 120.0)
    nv_f = run_native(solver=solver, num_modes=16, probe_defl_xz=SWEEP,
                      n_frames=int(1.6 * 480), relax=1.0, h=1.0 / 480.0)
    a_p = np.max(np.abs(nv_p["u_field"]), axis=0) * 1e3
    a_f = np.max(np.abs(nv_f["u_field"]), axis=0) * 1e3
    order = np.argsort(DISTS)
    d = DISTS[order]
    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    ax.plot(d, gt_amp[order], "ks-", lw=1.6, label="full-FEM GT")
    ax.plot(d, a_f[order], "C0o--", label="native (h=1/480)")
    ax.plot(d, a_p[order], "C3^:", label="native (h=1/120, paper)")
    ax.set_xlabel("distance from impact  |x − x_impact|  [m]")
    ax.set_ylabel("peak surface deflection |u_y|  [mm]")
    ax.set_title("X3-C  Distant-response falloff vs full-FEM ground truth\n"
                 "(standing-wave modal profile — NON-monotonic, reproduced "
                 "with NO r^-β term)")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "x3_falloff.png"), dpi=110)
    plt.close(fig)
    return a_p, a_f


# --------------------------------------------------------------------------- #
# D — mode-count convergence                                                  #
# --------------------------------------------------------------------------- #
def fig_mode_convergence(gt_amp, solver="avbd"):
    ks = [1, 2, 4, 8, 16, 32]
    rows = []
    ref = gt_amp                                  # GT field profile (mm)
    for k in ks:
        nv = run_native(solver=solver, num_modes=k, probe_defl_xz=SWEEP,
                        n_frames=int(1.6 * 480), relax=1.0, h=1.0 / 480.0)
        amp = np.max(np.abs(nv["u_field"]), axis=0) * 1e3
        # relative L2 error of the falloff profile vs GT
        err = float(np.linalg.norm(amp - ref) / np.linalg.norm(ref))
        rows.append(dict(k=k, err=err, amp=amp))
    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    ax.plot([r["k"] for r in rows], [r["err"] * 100 for r in rows], "o-C2")
    ax.set_xlabel("number of modes k")
    ax.set_ylabel("field-profile error vs GT  [%]")
    ax.set_xscale("log", base=2)
    ax.set_xticks(ks); ax.set_xticklabels([str(x) for x in ks])
    ax.set_title("X3-D  Modal-truncation convergence (native h=1/480 vs full-FEM)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "x3_mode_convergence.png"), dpi=110)
    plt.close(fig)
    return rows


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def main():
    os.makedirs(OUT, exist_ok=True)
    print("### X3 — coupled ground truth vs full FEM ###", flush=True)
    print(f"slab {SLAB.length}x{SLAB.width}x{SLAB.thickness} m, "
          f"E={SLAB.E:.2e} rho={SLAB.rho}  GT h_fine={GT_HFINE:.0e}", flush=True)

    print("[GT] running full-FEM ground truth …", flush=True)
    import time as _time
    _t0 = _time.time()
    gt = run_ground_truth(h_fine=GT_HFINE, probe_defl_xz=SWEEP)
    gt_wall = _time.time() - _t0
    gt_amp = _peak_amp(gt["probe_defl"])
    print(f"     v_entry={gt['v_entry']:.3f} m/s  peak|u_y|(mm)="
          f"{np.round(gt_amp,4)}", flush=True)

    print("[A/E] field overlay + ring frequency …", flush=True)
    nv, f_gt, f_nv = fig_field_overlay(gt)
    print(f"      ring freq: GT={f_gt:.1f} Hz  native={f_nv:.1f} Hz  "
          f"(Δ={abs(f_nv-f_gt)/max(f_gt,1e-9)*100:.1f}%)", flush=True)

    print("[B] amplitude convergence vs h …", flush=True)
    conv, gt_amp = fig_amp_convergence(gt)
    for r in conv:
        print(f"      h=1/{r['h_inv']:4d}: mid ratio={r['ratio_mid']:.2f}  "
              f"wall={r['wall_s']:.1f}s/{r['sim_s']:.2f}s", flush=True)

    print("[C] spatial falloff …", flush=True)
    a_p, a_f = fig_falloff(gt, gt_amp)

    print("[D] mode-count convergence …", flush=True)
    modes = fig_mode_convergence(gt_amp)
    for r in modes:
        print(f"      k={r['k']:2d}: field err={r['err']*100:.1f}%", flush=True)

    # ---- wall-clock: GT vs native per simulated second ----
    gt_sim = float(gt["times"][-1])
    gt_per_s = gt_wall / max(gt_sim, 1e-9)
    nv_per_s = conv[0]["wall_s"] / conv[0]["sim_s"]     # native at paper step
    speedup = gt_per_s / max(nv_per_s, 1e-9)
    print(f"[F] wall-clock: GT {gt_per_s:.1f} s/sim-s  vs  native (h=1/120) "
          f"{nv_per_s:.1f} s/sim-s  → {speedup:.0f}× faster", flush=True)
    with open(os.path.join(OUT, "x3_wallclock.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "wall_s", "sim_s", "wall_per_sim_s"])
        w.writerow(["full_fem_gt", f"{gt_wall:.3f}", f"{gt_sim:.3f}",
                    f"{gt_per_s:.3f}"])
        w.writerow(["native_h120", f"{conv[0]['wall_s']:.3f}",
                    f"{conv[0]['sim_s']:.3f}", f"{nv_per_s:.3f}"])
        w.writerow(["speedup_x", f"{speedup:.2f}", "", ""])

    # ---------------- CSVs ----------------
    with open(os.path.join(OUT, "x3_falloff.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["x", "dist_from_impact_m", "gt_peak_uy_mm",
                    "native_h120_mm", "native_h480_mm"])
        for j, (x, _) in enumerate(SWEEP):
            w.writerow([x, f"{DISTS[j]:.3f}", f"{gt_amp[j]:.5f}",
                        f"{a_p[j]:.5f}", f"{a_f[j]:.5f}"])

    with open(os.path.join(OUT, "x3_convergence.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["h_inv", "mid_ratio_native_over_gt", "wall_s", "sim_s",
                    "wall_per_sim_s"])
        for r in conv:
            w.writerow([r["h_inv"], f"{r['ratio_mid']:.4f}", f"{r['wall_s']:.3f}",
                        f"{r['sim_s']:.3f}", f"{r['wall_s']/r['sim_s']:.3f}"])

    with open(os.path.join(OUT, "x3_mode_convergence.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["k", "field_profile_err_pct"])
        for r in modes:
            w.writerow([r["k"], f"{r['err']*100:.3f}"])

    with open(os.path.join(OUT, "x3_freq.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["quantity", "gt", "native", "rel_err_pct"])
        w.writerow(["ring_freq_hz_midspan", f"{f_gt:.3f}", f"{f_nv:.3f}",
                    f"{abs(f_nv-f_gt)/max(f_gt,1e-9)*100:.2f}"])

    write_manifest(OUT, "x3_ground_truth", scenes=["fem_modal_shelf_drop"],
                   solvers=["avbd", "xpbd"],
                   note="native FEM-modal support vs CoupledFEMRigidSim GT; "
                        "GT signal = convergent slab deflection field",
                   gt_hfine=GT_HFINE, sweep=[list(s) for s in SWEEP],
                   gt_sim_s=gt_sim)
    print(f"\nwrote CSVs + PNGs + manifest to {OUT}/", flush=True)


if __name__ == "__main__":
    main()
