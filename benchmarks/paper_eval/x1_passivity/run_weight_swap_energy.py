#!/usr/bin/env python3
"""E-WS-E -- the TOTAL-MECHANICAL-ENERGY arm of the weight swap.

WHY THIS EXISTS (claim-integrity finding, 2026-07-28 panel). The published
weight-swap grid (`run_weight_swap.py`, `run_weight_swap_matched.py`) calls a
cell "injecting" when

    ratio = peak modal mechanical energy / peak impactor rigid KE  >  1

but the theory paper defines injecting as E+ > E- on the TOTAL mechanical
energy (onesweep_short.tex, the cold-start ledger paragraph). Those are
different tests. A ratio above 1 is strong evidence of injection; a ratio at or
below 1 does NOT establish total-energy nonincrease, so "8 of 24 -> 0 of 24"
under the ratio metric supports removal of gross modal overrun, not
system-level passivity.

The `holds_explicit` / `holds_implicit` columns of the published CSV cannot
substitute: `PassivityLedger.deposit`/`commit` are called only inside the
`_psv` block of `SolverXPBD._substep_cpu`, which is gated on
`_enforce_modal_passivity`. The weight-swap harness runs the governor OFF, so
the ledger is never touched and `holds()` evaluates `0.0 <= 0.0 + tol`, i.e.
vacuously True on every cell including the ratio-6333 one.

WHAT THIS SCRIPT MEASURES. The same 24-cell grid, the same three arms, with a
per-SUBSTEP readout of the scene's total mechanical energy

    E = sum_b [ 1/2 m_b |v_b|^2 + 1/2 w_b^T I_b w_b - m_b (g . x_b) ]
        + 1/2 qdot^T M_q qdot + 1/2 q^T K_q q                            (*)

which is the scene-level form of the paper's Hamiltonian
E = 1/2 M v^2 + 1/2 m qdot^2 + 1/2 k q^2 with the rigid gravitational
potential restored (gravity is conservative, so under a passive contact E must
not increase). Verified preconditions that make (*) complete for these scenes:

  * `sol._modal_grav_acc` is identically zero, so there is no modal
    gravitational potential term to add;
  * `sol._cargo` is empty, so there are no extra modal blocks;
  * `sol._modal_symplectic = True` makes `_device_compatible()` return False,
    so `_substep_cpu` is always the executed path and wrapping it sees every
    substep;
  * static bodies are skipped by `rigid_mechanical_energy` (mass <= 0) and do
    not move, so they neither store nor supply energy.

NO SOLVER FILE AND NO TRACKED HARNESS IS MODIFIED. The instrumentation is an
external wrapper installed on the instance attribute `sol._substep_cpu`; the
scenes, budgets, relaxations, settle and frame counts, and the three weight
expressions are IMPORTED from the tracked harnesses so the grid is provably the
published one.

KNOWN CONSERVATIVE BIAS (disclose with any number from here). Under the
position-based update v+ = (x+ - x-)/h with gravity applied in predict, free
ballistic motion loses exactly 1/2 m h^2 |g|^2 per body per substep. That drift
is NEGATIVE, so it can only mask injection, never manufacture it. The `dE_max`
and `net_excess` columns are therefore lower bounds on any true creation. The
matched arm doubles as the control: if the explicit arm's dE_max is orders of
magnitude above the matched arm's, the separation is not integrator drift.

Out: out/weight_swap_energy.csv
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_weight_swap_energy.py
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

from dcr.rigid.energy import rigid_kinetic_energy                  # noqa: E402
from dcr.avbd._solver.passivity import (                           # noqa: E402
    rigid_mechanical_energy, local_inertia_from_invIl, modal_mech_energy)
from benchmarks.paper_eval.paper_config import (                   # noqa: E402
    apply_relax, apply_passivity, write_manifest)
# Import BOTH tracked harnesses rather than copying them, so the grid and the
# three weight expressions are provably identical to the published arms.
from benchmarks.paper_eval.x1_passivity.run_weight_swap import (    # noqa: E402
    SCENES, BUDGETS, RELAXES, SETTLE, NFRAMES, OUT)
from benchmarks.paper_eval.x1_passivity.run_weight_swap_matched import (  # noqa: E402
    _weights, KAPPA_SYMPLECTIC)


class _EnergyProbe:
    """Per-substep total-mechanical-energy recorder, installed by wrapping the
    instance attribute `sol._substep_cpu`. Never touches the solver source."""

    def __init__(self, sol):
        self.sol = sol
        self.Il = local_inertia_from_invIl(sol._invIl)
        self.g = np.asarray(sol.gravity, dtype=np.float64)
        self.armed = False
        self.E = []          # E at every substep boundary in the armed window
        self.dE = []         # per-substep E+ - E-
        self._orig = sol._substep_cpu
        sol._substep_cpu = self._wrapped

    def _total(self) -> float:
        """Equation (*): rigid KE + rigid gravitational PE + modal KE + modal PE."""
        s = self.sol
        e = rigid_mechanical_energy(
            s._V, s._W, s._Q[:, [3, 0, 1, 2]], s._mass, s._invIl,
            X=s._X, gravity=self.g, Il=self.Il)
        if s._modal:
            ke, pe = modal_mech_energy(s._qdot, s._q, s._mq, s._kq)
            e += ke + pe
        return float(e)

    def _wrapped(self, h):
        if not self.armed:
            self._orig(h)
            return
        e0 = self._total()
        self._orig(h)
        e1 = self._total()
        if not self.E:
            self.E.append(e0)
        self.E.append(e1)
        self.dE.append(e1 - e0)

    def uninstall(self):
        self.sol._substep_cpu = self._orig


def one(build_fn, it, su, relax, arm, nframes=NFRAMES, settle=SETTLE,
        tol_rel=1e-9):
    """One XPBD cell, governor OFF, arm in {'explicit','be','matched'}.

    Returns the published ratio metric AND the total-energy metrics side by
    side, so the two definitions can be compared cell by cell.
    """
    t0 = time.perf_counter()
    H = build_fn(device="cpu", iterations=it, avbd_substeps=su, solver="xpbd")
    sol = H.world._solver
    apply_relax(sol, "xpbd", relax)
    sol._modal_symplectic = True                      # kappa = 2, host default
    apply_passivity(sol, "xpbd", enable=False, eta=1.0)
    sol._psv_monitor_only = False

    w_expl, w_be, w_matched, diag = _weights(sol)
    sol._wq_support = {"explicit": None, "be": w_be,
                       "matched": w_matched}[arm]

    sol._ensure_arrays()
    probe = _EnergyProbe(sol)

    w = H.world
    ib = w._descs[H.impactor_idx].dcr_body
    for _ in range(settle):                           # settle: not instrumented
        w.step()
        w._sync_avbd_to_dcr()
    probe.armed = True                                # arm on the measured window

    e_imp = e_mod = 0.0
    finite = True
    for _ in range(nframes):
        w.step()
        w._sync_avbd_to_dcr()
        e_imp = max(e_imp, rigid_kinetic_energy([ib]))
        e = sol.last_modal_KE + sol.last_modal_PE
        if not np.isfinite(e):
            finite = False
            break
        e_mod = max(e_mod, e)
    probe.uninstall()

    E = np.asarray(probe.E, dtype=np.float64)
    dE = np.asarray(probe.dE, dtype=np.float64)
    ok = np.isfinite(E).all() and np.isfinite(dE).all() and dE.size > 0
    if ok:
        E0 = float(E[0])
        # Energy scale for the relative tolerance: the largest magnitude the
        # scene's own energy reaches, floored so an at-rest scene is not
        # divided by zero.
        scale = max(float(np.abs(E).max()), 1e-12)
        tol = tol_rel * scale
        n_pos = int((dE > tol).sum())
        dE_max = float(dE.max())
        net_excess = float(E.max() - E0)
        e_end = float(E[-1])
        # Total energy CREATED, i.e. the positive variation of E. Upper bound on
        # creation: it does not net dissipation elsewhere against it.
        pos_var = float(np.clip(dE, 0.0, None).sum())
        # Sharpest creation signal that survives an overall dissipative trend:
        # the largest recovery above a running low-water mark,
        #     max_t [ E(t) - min_{s<=t} E(s) ].
        # Unlike net_excess this cannot be hidden by the scene having shed
        # energy earlier in the window.
        max_rebound = float((E - np.minimum.accumulate(E)).max())
    else:
        E0 = float("nan")
        scale = float("nan")
        n_pos = -1
        dE_max = float("inf")
        net_excess = float("inf")
        e_end = float("nan")
        pos_var = float("inf")
        max_rebound = float("inf")

    return dict(
        ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
        e_modal_peak=e_mod if finite else float("inf"),
        e_imp_peak=e_imp,
        finite=finite and ok,
        n_substeps=int(dE.size),
        E_start=E0, E_end=e_end, E_scale=scale,
        dE_max=dE_max, net_excess=net_excess, n_pos_substeps=n_pos,
        pos_var=pos_var, max_rebound=max_rebound,
        rebound_over_scale=(max_rebound / scale) if ok else float("inf"),
        frac_pos=(n_pos / dE.size) if (ok and dE.size) else float("nan"),
        dE_max_over_eimp=(dE_max / max(e_imp, 1e-9)) if ok else float("inf"),
        net_excess_over_eimp=(net_excess / max(e_imp, 1e-9))
        if ok else float("inf"),
        wall_s=time.perf_counter() - t0, **diag)


def _load_prev(path):
    """ratio_explicit / ratio_implicit from the published 24-cell CSV."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for row in csv.DictReader(fh):
            key = (row["scene"], float(row["relax"]),
                   int(row["iters"]), int(row["substeps"]))
            out[key] = (float(row["ratio_explicit"]),
                        float(row["ratio_implicit"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--budgets", default="4x1,8x2,16x4,32x8")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--arms", default="explicit,be,matched")
    ap.add_argument("--tol-rel", type=float, default=1e-9,
                    help="per-substep dE tolerance, relative to max|E| of the cell")
    ap.add_argument("--out", default="weight_swap_energy")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]
    budgets = [tuple(int(v) for v in b.lower().split("x"))
               for b in args.budgets.split(",") if b.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    prev = _load_prev(os.path.join(OUT, "weight_swap_full.csv"))

    rows = []
    worst_base = 0.0
    print(f"### E-WS-E total-energy arm ({platform.machine()}, "
          f"{platform.system()}) ###")
    print("### R = peak modal / peak impactor KE (published metric) | "
          "dE = max per-substep TOTAL mechanical energy rise ###\n", flush=True)
    hdr = f"{'scene':7s} {'rel':4s} {'bud':6s} |"
    for a in arms:
        hdr += f" {('R_' + a[:4]):>11s} {('dE_' + a[:4]):>11s} {('n+_' + a[:4]):>7s}"
    print(hdr, flush=True)

    for scene in scenes:
        fn = SCENES[scene]
        for relax in relaxes:
            for (it, su) in budgets:
                res = {a: one(fn, it, su, relax, a, args.nframes,
                              tol_rel=args.tol_rel) for a in arms}
                key = (scene, relax, it, su)
                pv = prev.get(key)
                reldiff = float("nan")
                if pv is not None and "explicit" in res and np.isfinite(
                        res["explicit"]["ratio"]):
                    reldiff = abs(res["explicit"]["ratio"] - pv[0]) / max(
                        abs(pv[0]), 1e-9)
                    worst_base = max(worst_base, reldiff)
                row = dict(scene=scene, relax=relax, iters=it, substeps=su)
                for a in arms:
                    r = res[a]
                    row[f"ratio_{a}"] = r["ratio"]
                    row[f"e_modal_{a}"] = r["e_modal_peak"]
                    row[f"e_imp_{a}"] = r["e_imp_peak"]
                    row[f"dE_max_{a}"] = r["dE_max"]
                    row[f"net_excess_{a}"] = r["net_excess"]
                    row[f"pos_var_{a}"] = r["pos_var"]
                    row[f"max_rebound_{a}"] = r["max_rebound"]
                    row[f"rebound_over_scale_{a}"] = r["rebound_over_scale"]
                    row[f"n_pos_{a}"] = r["n_pos_substeps"]
                    row[f"n_sub_{a}"] = r["n_substeps"]
                    row[f"frac_pos_{a}"] = r["frac_pos"]
                    row[f"dE_over_eimp_{a}"] = r["dE_max_over_eimp"]
                    row[f"net_over_eimp_{a}"] = r["net_excess_over_eimp"]
                    row[f"E_start_{a}"] = r["E_start"]
                    row[f"E_scale_{a}"] = r["E_scale"]
                    row[f"finite_{a}"] = r["finite"]
                any_arm = res[arms[0]]
                row.update(b_min=any_arm["b_min"], b_max=any_arm["b_max"],
                           n_modes=any_arm["n_modes"], h_sub=any_arm["h_sub"],
                           ratio_prev_explicit=pv[0] if pv else None,
                           ratio_prev_be=pv[1] if pv else None,
                           baseline_reldiff=reldiff,
                           tol_rel=args.tol_rel,
                           wall_s=sum(res[a]["wall_s"] for a in arms))
                rows.append(row)
                line = f"{scene:7s} {relax:<4} {it:2d}x{su:<3} |"
                for a in arms:
                    line += (f" {res[a]['ratio']:11.4g}"
                             f" {res[a]['dE_max']:11.4g}"
                             f" {res[a]['n_pos_substeps']:7d}")
                print(line, flush=True)

    keys = list(rows[0].keys())
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=["xpbd"],
        note=("E-WS-E: the published 24-cell weight-swap grid re-run with a "
              "per-substep TOTAL MECHANICAL ENERGY readout (rigid KE + rigid "
              "gravitational PE + modal KE + modal PE), so the theory paper's "
              "E+ > E- definition of injecting is measured directly instead of "
              "being proxied by peak-modal / peak-impactor-KE ratio. Governor "
              "OFF, symplectic stepper (kappa=2). Solver and tracked harnesses "
              "unmodified; instrumentation wraps the instance attribute "
              "_substep_cpu. Conservative bias: the position-based update loses "
              "1/2 m h^2 |g|^2 per body per substep in free flight, so dE_max "
              "and net_excess are LOWER bounds."))

    print(f"\n--- explicit arm vs published weight_swap_full.csv: worst "
          f"|dR|/R = {worst_base:.2e} "
          f"({'PASS' if worst_base < 1e-6 else 'CHECK'}) ---")
    for a in arms:
        n_ratio = sum(1 for r in rows
                      if np.isfinite(r[f"ratio_{a}"]) and r[f"ratio_{a}"] > 1.0)
        n_de = sum(1 for r in rows if r[f"n_pos_{a}"] != 0)
        n_net = sum(1 for r in rows
                    if not np.isfinite(r[f"net_excess_{a}"])
                    or r[f"net_excess_{a}"] > 0.0)
        wr = max((r[f"rebound_over_scale_{a}"] for r in rows), default=0.0)
        print(f"--- {a:8s}: ratio>1 {n_ratio}/{len(rows)} | "
              f"cells with any dE>tol substep {n_de}/{len(rows)} | "
              f"cells with net_excess>0 {n_net}/{len(rows)} | "
              f"worst rebound/|E| {wr:.3e} ---")
    print(f"CSV: {csv_path}")


if __name__ == "__main__":
    main()
