#!/usr/bin/env python3
"""R4 — XPBD self-convergence to K=500, and STATE-level agreement (plan §6.6).

Two questions the E-S2 energy curve cannot answer on its own.

1. Does the position-based host, converged against ITSELF, actually reach the
   implicit oracle? E-S2 stops at K=32, where the energy ratio is 0.300 against
   the oracle's 0.2735 -- a gap of 2.7e-2 that could plausibly be a floor rather
   than a tail. We extend its column to K in {64, 128, 256, 500}.

2. Does agreement hold on the STATE, not just on one scalar? A single energy
   ratio can match while the trajectory differs. The panel asked for states, so
   we compare the deflection trajectory itself:

     d_i(t) = U_y[i] . q(t)        [m], the live surface deflection at support
                                   row i -- the same expression the contact row
                                   uses (`solver_*.py` _SupportContact.U_y), so
                                   it is the physical quantity the coupling
                                   actually sees, not an abstract modal norm.

   Reported against the oracle trajectory:
     peak      max_t max_i |d_i(t)|                    ratio to oracle
     ring      dominant FFT frequency of the probe trace, post-impact [Hz]
     Linf      max_t max_i |d_i^K(t) - d_i^oracle(t)|  [m], and relative to
               the oracle's own peak deflection

The oracle is the implicit sequential-impulse host at K=500 -- the SAME code
path run to convergence, not a different model (E-S2's framing, preserved).

Measurement-only: `passivity_gamma` is forced to 1.0 so the governor cannot
perturb any trajectory (every state write in the enforcement path is guarded by
`if gamma < 1.0`), and the governor is left disabled anyway. Traces are read at
frame boundaries from host state.

Out: out/{selfconvergence.csv, selfconvergence_traces.npz, *.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/run_selfconvergence.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                    # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy                # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

K_XPBD = [16, 24, 32, 64, 128, 256, 500]   # E-S2's top three + the extension
K_ORACLE = 500
RELAX = 0.7        # PAPER_CONFIG; identical to E-S2 so the columns overlay
SUBSTEPS = 1       # pinned, so K is the only variable (identical to E-S2)
H = 1.0 / 120.0


def _deflection(sol):
    """d_i = U_y[i] . q  for every support row [m]. Same expression the contact
    row uses, so this is the surface the coupling actually sees."""
    q = sol._q
    if q is None or not sol._support:
        return np.zeros(0)
    return np.array([float(sc.U_y @ q) for sc in sol._support])


def run_cell(scene, solver, K, substeps, relax, nframes, settle=8):
    t0 = time.perf_counter()
    H_ = SCENES[scene](device="cpu", iterations=K, avbd_substeps=substeps,
                       solver=solver)
    sol = H_.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=False)        # governor OFF

    orig_gamma = _psv_mod.passivity_gamma
    _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0
    trace = []
    e_imp = e_mod = 0.0
    finite = True
    try:
        w = H_.world
        ib = w._descs[H_.impactor_idx].dcr_body
        for _ in range(settle):
            w.step()
            w._sync_avbd_to_dcr()
        for _ in range(nframes):
            w.step()
            w._sync_avbd_to_dcr()
            e_imp = max(e_imp, rigid_kinetic_energy([ib]))
            e = sol.last_modal_KE + sol.last_modal_PE
            if not np.isfinite(e):
                finite = False
                break
            e_mod = max(e_mod, e)
            trace.append(_deflection(sol))
    finally:
        _psv_mod.passivity_gamma = orig_gamma

    D = np.asarray(trace, dtype=np.float64)           # (frames, n_rows)
    return dict(ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
                finite=finite, wall_s=time.perf_counter() - t0), D


def _ring_hz(x, h):
    """Dominant frequency of a deflection trace, DC removed [Hz]."""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    if x.size < 8:
        return float("nan")
    w = np.hanning(x.size)
    P = np.abs(np.fft.rfft(x * w))
    f = np.fft.rfftfreq(x.size, d=h)
    P[0] = 0.0                                        # kill residual DC
    return float(f[int(np.argmax(P))])


def _probe(D):
    """Scalar probe trace: the row with the largest peak excursion."""
    if D.size == 0:
        return np.zeros(0)
    return D[:, int(np.argmax(np.abs(D).max(axis=0)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="shelf")
    ap.add_argument("--relax", type=float, default=RELAX)
    ap.add_argument("--substeps", type=int, default=SUBSTEPS)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--oracle", type=int, default=K_ORACLE)
    ap.add_argument("--out", default="selfconvergence")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### R4 self-convergence + state agreement: scene={args.scene} "
          f"substeps={args.substeps} relax={args.relax} "
          f"({platform.machine()}) ###", flush=True)

    # ---- the oracle: implicit host run to convergence ---------------------
    om, OD = run_cell(args.scene, "impulse", args.oracle, args.substeps,
                      args.relax, args.nframes)
    o_probe = _probe(OD)
    o_peak = float(np.abs(OD).max()) if OD.size else float("nan")
    o_ring = _ring_hz(o_probe, H * args.substeps)
    print(f"  ORACLE impulse K={args.oracle}: ratio={om['ratio']:.7g}  "
          f"peak|d|={o_peak:.6g} m  ring={o_ring:.4g} Hz  "
          f"[{om['wall_s']:.1f}s]", flush=True)

    rows = [dict(solver="impulse", K=args.oracle, is_oracle=True,
                 ratio=om["ratio"], d_peak=o_peak, ring_hz=o_ring,
                 d_gap_ratio=1.0, linf_m=0.0, linf_rel=0.0,
                 energy_gap=0.0, finite=om["finite"], wall_s=om["wall_s"])]
    traces = {f"oracle_impulse_K{args.oracle}": OD}

    for K in K_XPBD:
        m, D = run_cell(args.scene, "xpbd", K, args.substeps, args.relax,
                        args.nframes)
        p = _probe(D)
        peak = float(np.abs(D).max()) if D.size else float("nan")
        ring = _ring_hz(p, H * args.substeps)
        n = min(len(D), len(OD))
        linf = (float(np.abs(D[:n] - OD[:n]).max())
                if (D.size and OD.size) else float("nan"))
        rows.append(dict(
            solver="xpbd", K=K, is_oracle=False, ratio=m["ratio"],
            d_peak=peak, ring_hz=ring,
            d_gap_ratio=(peak / o_peak) if o_peak else float("nan"),
            linf_m=linf, linf_rel=(linf / o_peak) if o_peak else float("nan"),
            energy_gap=abs(m["ratio"] - om["ratio"]),
            finite=m["finite"], wall_s=m["wall_s"]))
        traces[f"xpbd_K{K}"] = D
        print(f"  xpbd  K={K:4d}: ratio={m['ratio']:11.7g}  "
              f"|dE|={abs(m['ratio'] - om['ratio']):10.4g}  "
              f"peak|d|={peak:.6g} m ({peak / o_peak:.4f}x)  "
              f"ring={ring:.4g} Hz  Linf={linf:.4g} m "
              f"({100.0 * linf / o_peak:.2f}% of peak)  [{m['wall_s']:.1f}s]",
              flush=True)

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    np.savez_compressed(os.path.join(OUT, f"{args.out}_traces.npz"), **traces)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=[args.scene],
        solvers=["xpbd", "impulse"],
        note=("R4 (plan §6.6): XPBD self-convergence K->500 against the "
              "implicit oracle at K=500, substeps pinned to 1 and relax 0.7 so "
              "the column overlays E-S2. State-level agreement uses the "
              "deflection trajectory d_i = U_y[i].q [m], the same expression "
              "the contact row uses: peak, dominant ring frequency, and Linf "
              "against the oracle trace. Measurement-only (governor disabled "
              "and passivity_gamma forced to 1.0)."))

    # ---- acceptance -------------------------------------------------------
    k32 = next((r for r in rows if r["K"] == 32 and not r["is_oracle"]), None)
    top = rows[-1]
    print("\n--- acceptance (plan §6.6) ---")
    if k32:
        print(f"  energy gap at K=32   : {k32['energy_gap']:.4g}")
    print(f"  energy gap at K={top['K']}  : {top['energy_gap']:.4g}")
    if k32 and top["energy_gap"] > 0:
        print(f"  improvement           : "
              f"{k32['energy_gap'] / top['energy_gap']:.4g}x")
    print(f"  state: peak ratio {top['d_gap_ratio']:.4f}x, "
          f"ring {top['ring_hz']:.4g} vs oracle {o_ring:.4g} Hz, "
          f"Linf {top['linf_m']:.4g} m ({100.0 * top['linf_rel']:.2f}% of peak)")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
