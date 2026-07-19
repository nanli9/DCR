#!/usr/bin/env python3
"""Where should a band-selective projection split, and does the answer survive
across scenes? (R8 follow-up; NOT a paper number.)

`probe_r8_feasibility.py` used a single hard-coded 10 kHz split. That is
correct for the shelf, whose spectrum has its decade-wide gap at
2.03 -> 20.7 kHz, and WRONG elsewhere:

    shelf    gap  2.03k ->  20.7k Hz    10 kHz sits inside it        ok
    ledge    gap 17.0k  -> 170.1k Hz    10 kHz is below the bending
                                        band's top: three genuine
                                        bending modes got scaled     WRONG
    dinner   gap  469   ->   4.70k Hz   10 kHz is above the whole
                                        spectrum: E_high = 0         DEGENERATE

So this records the per-mode modal state at every clamp decision and sweeps
the split offline, which answers three things the fixed cut could not:

  1. is the bimodal structure universal, or a shelf artifact?
  2. is there a split that is BOTH feasible and effective? In particular the
     substep Nyquist -- modes above it are unrepresentable by the integrator,
     which is a physical criterion rather than a fitted one.
  3. how sensitive is the answer to where the split is put?

For each candidate split we report the two quantities that decide it:
  infeasible  fraction of clamp substeps with ceiling < E_preserved, i.e.
              no gamma in [0,1] satisfies Eq. (2)
  pen_max     worst-case penetration proxy [mm] -- how far the projection
              lifts the support into the resting body

Measurement-only: the real gamma stays live, the wrapper returns it unchanged.

Out: out/{band_split_sweep.csv, band_split_state.npz, *.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/probe_band_split_sweep.py
"""
from __future__ import annotations

import argparse
import csv
import os
import platform
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dcr.avbd._solver.passivity as _psv_mod                    # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import SCENES  # noqa: E402
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def capture(scene, K, S, relax, nframes=100, settle=8):
    """Record (q, qdot, ceiling) at every clamp decision, plus the fixed
    spectrum and U_y, so any split can be evaluated offline."""
    H = SCENES[scene](device="cpu", iterations=K, avbd_substeps=S, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True
    apply_passivity(sol, "xpbd", enable=True, eta=1.0)   # real gamma stays live

    kq = np.asarray(sol._kq, dtype=np.float64)
    mq = getattr(sol, "_mq", None)
    mqv = np.ones_like(kq) if mq is None else np.asarray(mq, dtype=np.float64)
    f = np.sqrt(np.maximum(kq / np.where(mqv > 0, mqv, 1.0), 0.0)) / (2 * np.pi)
    U = np.array([np.asarray(sc.U_y, dtype=np.float64)[:kq.size]
                  for sc in sol._support]) if sol._support else np.zeros((0, kq.size))

    Q, QD, CEIL, G = [], [], [], []
    orig = _psv_mod.passivity_gamma

    def wrap(e_new, e_old, budget, tol=1e-12):
        g = orig(e_new, e_old, budget, tol=tol)          # unchanged
        if g < 1.0:                                      # clamp-active only
            Q.append(np.asarray(sol._q, dtype=np.float64).copy())
            QD.append(np.asarray(sol._qdot, dtype=np.float64).copy())
            CEIL.append(float(e_old + budget))
            G.append(float(g))
        return g

    _psv_mod.passivity_gamma = wrap
    try:
        w = H.world
        for _ in range(settle + nframes):
            w.step()
    finally:
        _psv_mod.passivity_gamma = orig
    return dict(q=np.array(Q), qdot=np.array(QD), ceiling=np.array(CEIL),
                gamma=np.array(G), kq=kq, mq=mqv, f=f, U=U)


def evaluate(st, f_split):
    """Offline evaluation of one split. Returns (infeasible_frac, pen_max_mm,
    pen_p50_mm, n_preserved)."""
    q, qd, ceil = st["q"], st["qdot"], st["ceiling"]
    if q.size == 0:
        return float("nan"), float("nan"), float("nan"), 0
    kq, mqv, U = st["kq"], st["mq"], st["U"]
    keep = st["f"] <= f_split                       # preserved band
    e_i = 0.5 * kq * q ** 2 + 0.5 * mqv * qd ** 2   # (n, r)
    E_pres = e_i[:, keep].sum(axis=1)
    E_scal = e_i[:, ~keep].sum(axis=1)
    infeas = ceil < E_pres
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.sqrt(np.clip((ceil - E_pres) / np.where(E_scal > 0, E_scal, np.nan),
                            0.0, 1.0))
    g = np.where(E_scal <= 0, 1.0, g)
    g = np.where(infeas, np.nan, g)
    scale = np.where(keep[None, :], 1.0, g[:, None])
    q_new = q * scale
    if U.size:
        d_pre = np.abs(q @ U.T).max(axis=1)
        d_new = np.abs(q_new @ U.T).max(axis=1)
    else:
        d_pre = d_new = np.zeros(len(q))
    pen = 1e3 * (d_pre - d_new)                     # mm lifted into the body
    return (float(infeas.mean()), float(np.nanmax(pen)),
            float(np.nanmedian(pen)), int(keep.sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="shelf:4x1:0.7,shelf:8x2:0.7,"
                                       "ledge:4x1:0.7,dinner:4x1:0.7")
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--out", default="band_split_sweep")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print(f"### band-split sweep ({platform.machine()}) ###")
    print("infeas = clamp substeps with NO feasible gamma; pen = penetration "
          "proxy [mm]\n", flush=True)

    rows, blobs = [], {}
    for spec in args.cells.split(","):
        scene, budget, relax = spec.split(":")
        K, S = (int(v) for v in budget.lower().split("x"))
        st = capture(scene, K, S, float(relax), args.nframes)
        f = st["f"]
        n = len(st["q"])
        if n == 0:
            print(f"  {scene} {K}x{S}: no clamp-active substeps, skipped\n")
            continue
        blobs[f"{scene}_{K}x{S}"] = st["f"]

        # candidate splits: the spectral gap, the substep Nyquist, and each
        # inter-mode boundary (so the whole trade-off curve is visible)
        fs = np.sort(f)
        gap_i = int(np.argmax(fs[1:] / np.maximum(fs[:-1], 1e-30)))
        f_gap = float(np.sqrt(fs[gap_i] * fs[gap_i + 1]))     # geometric middle
        f_nyq = 0.5 * 120.0 * S                                # substep Nyquist
        cands = [("gap", f_gap), ("nyquist", f_nyq)]
        cands += [(f"m{i+1}", float(np.sqrt(fs[i] * fs[i + 1])))
                  for i in range(len(fs) - 1)]

        # baseline: the present whole-state projection = preserve nothing
        b_inf, b_max, b_p50, _ = evaluate(st, -1.0)
        print(f"  --- {scene} {K}x{S} relax {relax}: {n} clamp substeps, "
              f"{f.size} modes, gap at {fs[gap_i]:.0f}->{fs[gap_i+1]:.0f} Hz, "
              f"substep Nyquist {f_nyq:.0f} Hz ---")
        print(f"      {'split':>10s} {'f_Hz':>10s} {'keep':>5s} "
              f"{'infeas':>8s} {'pen_max':>9s} {'pen_p50':>9s}")
        print(f"      {'present':>10s} {'-':>10s} {0:5d} "
              f"{0.0:7.1%} {b_max:8.2f}  {b_p50:8.2f}")
        seen = set()
        for tag, fv in cands:
            inf, pmax, pp50, keep = evaluate(st, fv)
            if keep in seen and tag.startswith("m"):
                continue
            seen.add(keep)
            star = "  <-- " + tag if tag in ("gap", "nyquist") else ""
            print(f"      {tag:>10s} {fv:10.1f} {keep:5d} "
                  f"{inf:7.1%} {pmax:8.2f}  {pp50:8.2f}{star}")
            rows.append(dict(scene=scene, iters=K, substeps=S, relax=float(relax),
                             split_tag=tag, f_split_Hz=fv, n_keep=keep,
                             n_clamped=n, infeasible_frac=inf,
                             pen_max_mm=pmax, pen_p50_mm=pp50,
                             present_pen_max_mm=b_max, present_pen_p50_mm=b_p50))
        print(flush=True)

    p = os.path.join(OUT, f"{args.out}.csv")
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        [w.writerow(r) for r in rows]
    np.savez_compressed(os.path.join(OUT, "band_split_spectra.npz"), **blobs)
    write_manifest(
        OUT, f"{args.out}.csv",
        scenes=sorted({r["scene"] for r in rows}), solvers=["xpbd"],
        note=("R8 follow-up (NOT a paper number): sweeps the band-selective "
              "split frequency and reports the feasibility/effectiveness "
              "trade-off per scene. Corrects probe_r8_feasibility.py's single "
              "hard-coded 10 kHz cut, which is correct only for the shelf."))
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
