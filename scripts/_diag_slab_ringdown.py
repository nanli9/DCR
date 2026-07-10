#!/usr/bin/env python3
"""Step-0 diagnosis for the slab ring-down (settle) feature.

Question: after the dinner-scene pot impact, how long does the table's modal
ring stay visible, which modes carry it, is the decay a clean exponential
(⇒ a ring-down operator will work) or continuously re-pumped by contact
chatter (⇒ fix the pump first), and what per-mode decay rate does the
Rayleigh damping (alpha0 + alpha1·omega²) actually give?

Per-mode oscillation energy about the (post-ring) static sag q̄:

    E_i(t) = ½ q̇_i² + ½ ω_i² (q_i − q̄_i)²        (mass-normalized, M_q = I)

For an unforced damped mode this decays as E_i(0)·exp(−2 ζ_i ω_i t) with no
oscillatory component, so the log-slope fit is sample-rate independent
(foundation §9: dissipation measured from the energy decrement).

Usage:
    python scripts/_diag_slab_ringdown.py [--solver avbd] [--frames 600]
"""
from __future__ import annotations

import argparse
import os

import numpy as np

from scenes.reduced_dinner_table import build_reduced_dinner_table


def run(solver: str = "avbd", n_frames: int = 600, symplectic: bool = True,
        ringdown: str = "off", delay: float = 0.15):
    """Viewer-parity dinner run (fem basis, 6 iters x 2 substeps, h=1/120)."""
    handle = build_reduced_dinner_table(
        device="cpu", iterations=6, avbd_substeps=2,
        solver=solver, support_basis="fem",
    )
    world = handle.world
    sol = world._solver
    if hasattr(sol, "_modal_symplectic"):
        sol._modal_symplectic = bool(symplectic)
    if ringdown != "off":
        world.set_modal_ringdown(ringdown, delay=delay)
    rs = handle.rs

    omega = np.asarray(rs.eigen_omegas if rs.eigen_omegas is not None
                       else rs.modal_omega, dtype=np.float64)
    r = omega.shape[0]
    h = 1.0 / 120.0

    # NOTE: native-thin path never syncs desc.dcr_body — read SOLVER state.
    sidx = [int(world._descs[i].avbd_body.index) for i in handle.probe_indices]
    plate_y0 = None  # snapshot after settle, before impact

    Q = np.zeros((n_frames, r))
    QD = np.zeros((n_frames, r))
    T = np.arange(n_frames) * h
    lift = np.zeros(n_frames)

    for f in range(n_frames):
        world.step()
        Q[f] = sol.modal_q
        QD[f] = sol.modal_qdot
        ys = np.asarray(sol.positions(), dtype=np.float64)[sidx, 1]
        if plate_y0 is None and f == 8:   # match probe settle=8 convention
            plate_y0 = ys.copy()
        if plate_y0 is not None:
            lift[f] = float(np.max(ys - plate_y0))

    return dict(handle=handle, rs=rs, omega=omega, h=h, Q=Q, QD=QD, T=T,
                lift=lift, ringdown=ringdown,
                D_settle=float(getattr(sol, "cum_ringdown_dissipated", 0.0)))


def analyze(rec, out_dir: str):
    omega, Q, QD, T, h = rec["omega"], rec["Q"], rec["QD"], rec["T"], rec["h"]
    r = omega.shape[0]
    n = T.shape[0]

    # Static sag reference: mean of the last 0.5 s (ring decayed to <1% there
    # for any sigma >~ 1/s; verified below by the fitted sigma itself).
    tail = slice(n - int(0.5 / h), n)
    qbar = Q[tail].mean(axis=0)

    dev = Q - qbar[None, :]
    E = 0.5 * QD ** 2 + 0.5 * (omega[None, :] ** 2) * dev ** 2   # (n, r)
    E_tot = E.sum(axis=1)

    # Impact frame = peak of total oscillation energy.
    f_imp = int(np.argmax(E_tot))
    E_pk = float(E_tot[f_imp])

    # Re-excitation check: positive jumps of E_tot after the impact.
    dE = np.diff(E_tot)
    re_exc = np.where((dE[f_imp + 2:] > 0.02 * E_pk))[0] + f_imp + 2
    # collapse into events separated by > 5 frames
    events = []
    for i in re_exc:
        if not events or i - events[-1] > 5:
            events.append(int(i))

    # Per-mode decay fit on log E_i from just after impact to 2% of that
    # mode's peak (skip modes that never ring).
    rows = []
    for i in range(r):
        Ei = E[:, i]
        pk = float(Ei[f_imp:].max())
        if pk < 1e-12:
            continue
        f0 = f_imp + int(np.argmax(Ei[f_imp:])) + 3
        below = np.where(Ei[f0:] < 0.02 * pk)[0]
        f1 = f0 + (int(below[0]) if below.size else (n - f0))
        if f1 - f0 < 12:
            continue
        y = np.log(np.maximum(Ei[f0:f1], 1e-300))
        t = T[f0:f1]
        slope = float(np.polyfit(t, y, 1)[0])       # = −2 σ_i
        sigma_meas = -0.5 * slope
        f_hz = omega[i] / (2 * np.pi)
        # Rayleigh prediction: zeta_i = (a0/omega + a1*omega)/2 ⇒ sigma = zeta*omega
        a0, a1 = 2.0, 1.0e-5
        sigma_pred = 0.5 * (a0 + a1 * omega[i] ** 2)
        rows.append((i, f_hz, pk, sigma_meas, sigma_pred,
                     3.0 / max(sigma_meas, 1e-9)))

    rows.sort(key=lambda x: -x[2])
    print(f"\nimpact at t = {T[f_imp]:.3f} s   E_osc peak = {E_pk:.4e} J")
    print(f"re-excitation events after impact (> 2% of peak): "
          f"{len(events)} at t = {[round(float(T[i]), 2) for i in events[:10]]}")
    print(f"max plate lift = {rec['lift'].max() * 1e3:.2f} mm")
    print(f"\n{'mode':>4} {'f [Hz]':>8} {'E_pk [J]':>10} {'σ_meas [1/s]':>12} "
          f"{'σ_rayleigh':>10} {'t_5% [s]':>9}")
    for i, f_hz, pk, sm, sp, t95 in rows[:10]:
        print(f"{i:>4} {f_hz:>8.1f} {pk:>10.3e} {sm:>12.2f} {sp:>10.2f} {t95:>9.2f}")

    # Visible ring duration: time for max |U_y (q − q̄)| to fall below 0.1 mm.
    rs = rec["rs"]
    Uy = rs.U_points[:, 1, :]                      # (n_pts, r)
    defl = np.abs(dev @ Uy.T).max(axis=1)          # (n,) max |deflection| [m]
    vis = np.where(defl[f_imp:] > 1e-4)[0]
    t_vis = float(T[f_imp + vis[-1]] - T[f_imp]) if vis.size else 0.0
    vis_x = np.where(defl[f_imp:] > 1e-5)[0]     # ×300 render-exag threshold
    t_vis_x = float(T[f_imp + vis_x[-1]] - T[f_imp]) if vis_x.size else 0.0
    print(f"\nmax transient deflection = {defl[f_imp:].max() * 1e3:.2f} mm; "
          f"visible (>0.1 mm) for {t_vis:.2f} s after impact; "
          f"under x300 exaggeration (>0.01 mm) for {t_vis_x:.2f} s")

    os.makedirs(out_dir, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
        ax[0].semilogy(T, np.maximum(E_tot, 1e-12), lw=1.0)
        for ev in events:
            ax[0].axvline(T[ev], color="r", alpha=0.3, lw=0.6)
        ax[0].set_ylabel("E_osc total [J]")
        ax[0].set_title(f"dinner / pot drop — slab oscillation energy about sag"
                        f" (ring-down: {rec.get('ringdown', 'off')})")
        top = [i for i, *_ in rows[:6]]
        for i in top:
            ax[1].semilogy(T, np.maximum(E[:, i], 1e-14), lw=0.8,
                           label=f"m{i} {omega[i]/2/np.pi:.0f} Hz")
        ax[1].legend(fontsize=7, ncol=3)
        ax[1].set_ylabel("E_i [J]")
        ax[2].plot(T, defl * 1e3, lw=0.9)
        ax[2].axhline(0.1, color="k", ls="--", lw=0.6)
        ax[2].set_ylabel("max |defl − sag| [mm]")
        ax[2].set_xlabel("t [s]")
        fig.tight_layout()
        path = os.path.join(
            out_dir, f"diag_dinner_ringdown_{rec.get('ringdown', 'off')}.png")
        fig.savefig(path, dpi=130)
        print(f"plot: {path}")
    except Exception as e:  # matplotlib optional for the console diagnosis
        print(f"(plot skipped: {e})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="avbd", choices=("avbd", "xpbd"))
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--ringdown", default="off", choices=("off", "kill", "damp"))
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--out", default="docs/settle_ringdown")
    args = ap.parse_args()
    rec = run(solver=args.solver, n_frames=args.frames,
              ringdown=args.ringdown, delay=args.delay)
    if rec["ringdown"] != "off":
        print(f"D_settle (cum ring-down dissipation) = {rec['D_settle']:.4e} J")
    analyze(rec, args.out)
