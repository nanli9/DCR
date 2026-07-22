#!/usr/bin/env python3
"""R5 — what the governed result is WORTH, and what the penetration is worth
relative to the sag it destroys (plan §6.7 items 1 and 4).

Two questions, one scene (shelf), both answered against the same references.

R5.1 -- ACCURACY. The paper so far shows the governor makes an exploding cell
finite. It does not show whether the finite answer is any GOOD. At a moderate
injecting cell (shelf 8x2, relax 0.7) we place four arms on one axis:

    ungoverned      xpbd  8x2, governor OFF        (the pathology)
    governed        xpbd  8x2, governor ON, active (the claim)
    xpbd_converged  xpbd  500x1, governor OFF      (this host, converged: R4)
    oracle          impulse 500x1, governor OFF    (the implicit reference)

R4 changed what "the reference" means: the position-based host self-converges to
0.2996, NOT to the oracle's 0.2735 (a 9.6% formulation gap that convergence does
not remove). So the accuracy improvement is reported against BOTH denominators
and the choice is stated, rather than quietly picking the flattering one.

Energy is reported in joules as well as ratios, per the R1/R3/R4 convention --
a ratio of ratios is not a quantity a reader can check.

R5.4 -- NORMALIZED PENETRATION. E-S3 measures a worst-case post-projection
penetration of 21.6 mm on shelf 4x1, and the paper currently normalizes it by
board geometry only (30 mm thick, 0.8 m span). The missing half is the sag the
projection is destroying: gamma<1 shrinks U_y.q, so the penetration cannot
exceed the sag that was there. We measure the UNCLAMPED steady-state sag of the
same scene -- tail median of max_i |d_i| over a late window, governor OFF, at a
converged budget so the sag is the scene's own equilibrium and not a truncation
artifact. "Static sag" is defined here as that tail median; the peak (impact
transient included) is reported next to it so the definition is auditable.

Measurement-only. The ungoverned/reference arms force `passivity_gamma` to 1.0
(every state write in all three enforcement paths is guarded by `if gamma < 1.0`
-- solver_xpbd.py:1244, solver_6dof.py:2639, solver_impulse.py:1003 -- so the
branch is dead and the trajectory is bit-identical to un-governed). The governed
arm leaves the real gamma live: it is the arm under test. Acceptance is that the
ungoverned and governed ratios reproduce the frozen solver_matrix.csv cell
(53.7307 / 1.0106759) EXACTLY.

Out: out/{governed_accuracy.csv, governed_accuracy_traces.npz, *.config.json}
Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/run_governed_accuracy.py
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
from benchmarks.paper_eval.x1_passivity.run_selfconvergence import (  # noqa: E402
    _deflection)
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Frozen expectations (out/solver_matrix.csv): the cell this item is about.
# Reproducing these EXACTLY is the non-perturbation check.
# The UNGOVERNED value is trajectory-independent of the ledger and is unchanged.
# The GOVERNED value moved 1.0106759 -> 1.0209246 with the trapezoidal-W_g
# supply fix (foundation §15): the corrected (larger) contact-phase supply
# relaxes the clamp slightly, so governed modal storage rises ~1% (E_mod_peak
# 29.26 -> 29.56 J). This is the intended effect of the fix, re-frozen here.
FROZEN = {"ungoverned": 53.73070660394743, "governed": 1.0209246116008728}
TOL = 0.0            # exact: same code path, same seed, same machine
F_STIFF = 1.0e4      # Hz; sits inside the shelf spectrum's 2.0k..20.7k gap


def run_arm(scene, solver, K, S, relax, nframes, *, governed, settle=8,
            gap_preserving=False):
    """One arm. `governed` True leaves the real gamma live (the arm under
    test); False neuters it to 1.0 so the run is provably un-perturbed."""
    t0 = time.perf_counter()
    H = SCENES[scene](device="cpu", iterations=K, avbd_substeps=S,
                      solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=governed, eta=1.0)
    if governed:
        # Make "governed" mean the ACTIVE projection on every backend, exactly
        # as run_solver_matrix.py's ON column does (E-S1b caveat 3). This is a
        # measurement-side override of a production default, not a solver edit.
        sol._psv_monitor_only = False
        sol._psv_gap_preserving = bool(gap_preserving)

    orig_gamma = _psv_mod.passivity_gamma
    if not governed:
        _psv_mod.passivity_gamma = lambda a, b, c, tol=1e-12: 1.0
    trace = []
    e_imp = e_mod = 0.0
    ke_pk = pe_pk = float("nan")     # the KE/PE split AT the peak-energy frame
    q_pk = qd_pk = None              # modal state at that frame
    finite = True
    try:
        w = H.world
        ib = w._descs[H.impactor_idx].dcr_body
        for _ in range(settle):
            w.step()
            w._sync_avbd_to_dcr()
        for _ in range(nframes):
            w.step()
            w._sync_avbd_to_dcr()
            e_imp = max(e_imp, rigid_kinetic_energy([ib]))
            ke, pe = sol.last_modal_KE, sol.last_modal_PE
            e = ke + pe
            if not np.isfinite(e):
                finite = False
                break
            if e > e_mod:
                e_mod, ke_pk, pe_pk = e, ke, pe
                q_pk = None if sol._q is None else np.asarray(sol._q).copy()
                qd_pk = (None if sol._qdot is None
                         else np.asarray(sol._qdot).copy())
            trace.append(_deflection(sol))
    finally:
        _psv_mod.passivity_gamma = orig_gamma

    # ---- where does the energy SIT in the spectrum? ------------------------
    # E_mod is quadratic in q with weight K_q = diag(omega^2), so a mode can
    # carry large energy at small amplitude if its frequency is high -- and a
    # high mode contributes little to U_y.q at one support row. This is the
    # only thing that can reconcile a 196x energy error with a 1.2x deflection
    # error, so we MEASURE it rather than assert it.
    # Threshold: the shelf spectrum is sharply BIMODAL -- ten bending modes at
    # 20.3 Hz..2.03 kHz, then a stiff cluster at 20.7..24.7 kHz. Any cut inside
    # that decade-wide gap gives the same answer, so F_STIFF is not a tuned
    # knob; we report the gap so a reader can check that. (A median split would
    # be arbitrary; the substep Nyquist would differ per arm and so could not
    # compare them.)
    kq = getattr(sol, "_kq", None)
    mq = getattr(sol, "_mq", None)
    cent = hi_frac = f_lo = f_hi = float("nan")
    if kq is not None and q_pk is not None:
        kq = np.asarray(kq, dtype=np.float64)
        mqv = (np.ones_like(kq) if mq is None
               else np.asarray(mq, dtype=np.float64))
        e_i = 0.5 * kq * q_pk ** 2
        if qd_pk is not None:
            e_i = e_i + 0.5 * mqv * qd_pk ** 2
        f_i = np.sqrt(np.maximum(kq / np.where(mqv > 0, mqv, 1.0), 0.0)) / (2 * np.pi)
        stiff = f_i > F_STIFF
        if stiff.any() and (~stiff).any():
            f_lo = float(f_i[~stiff].max())     # top of the resolved band
            f_hi = float(f_i[stiff].min())      # bottom of the stiff cluster
        tot = float(e_i.sum())
        if tot > 0:
            cent = float((e_i * f_i).sum() / tot)          # energy-weighted Hz
            hi_frac = float(e_i[stiff].sum() / tot)

    led = getattr(sol, "_psv_ledger", None)
    D = np.asarray(trace, dtype=np.float64)
    return dict(
        ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
        e_modal_peak_J=e_mod if finite else float("inf"),
        # Split at the peak-energy frame. This is what reconciles a 196x energy
        # error with a 1.2x deflection error: E_mod is quadratic in BOTH q and
        # qdot, so injected energy can sit almost entirely in modal VELOCITY
        # (high-frequency chatter) while the displacement stays bounded.
        ke_at_peak_J=ke_pk, pe_at_peak_J=pe_pk,
        ke_frac_at_peak=(ke_pk / e_mod) if (finite and e_mod > 0) else float("nan"),
        spectral_centroid_Hz=cent, energy_frac_above_10kHz=hi_frac,
        spectral_gap_lo_Hz=f_lo, spectral_gap_hi_Hz=f_hi,
        e_imp_peak_J=e_imp, finite=finite,
        n_clamped=(int(led.n_clamped) if led is not None
                   and hasattr(led, "n_clamped") else None),
        wall_s=time.perf_counter() - t0), D


def _linf(A, B):
    if A.size == 0 or B.size == 0:
        return float("nan")
    n = min(len(A), len(B))
    return float(np.abs(A[:n] - B[:n]).max())


def _sag(D, tail_frac=0.5):
    """Steady-state sag [m]: tail median of max_i |d_i(t)| over the last
    `tail_frac` of the window. The tail avoids the impact transient, so this is
    the load-bearing equilibrium deflection rather than the ringing peak."""
    if D.size == 0:
        return float("nan"), float("nan")
    env = np.abs(D).max(axis=1)                 # max over support rows, per frame
    k = max(1, int(len(env) * (1.0 - tail_frac)))
    return float(np.median(env[k:])), float(env.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="shelf")
    ap.add_argument("--relax", type=float, default=0.7)
    ap.add_argument("--cell", default="8x2", help="the injecting cell under test")
    ap.add_argument("--converged", type=int, default=500)
    ap.add_argument("--nframes", type=int, default=100)
    ap.add_argument("--sag-budget", default="500x1",
                    help="converged, unclamped budget defining the static sag")
    ap.add_argument("--check-frozen", action="store_true")
    ap.add_argument("--gap-preserving", action="store_true",
                    help="run the GOVERNED arm with the gap-preserving "
                         "projection instead of the shipped radial gamma")
    ap.add_argument("--out", default="governed_accuracy")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    K, S = (int(v) for v in args.cell.lower().split("x"))

    print(f"### R5 governed accuracy + normalized penetration: scene="
          f"{args.scene} cell={args.cell} relax={args.relax} "
          f"({platform.machine()}) ###", flush=True)

    arms = [
        ("ungoverned",     "xpbd",    K, S, False),
        ("governed",       "xpbd",    K, S, True),
        ("xpbd_converged", "xpbd",    args.converged, 1, False),
        ("oracle",         "impulse", args.converged, 1, False),
    ]
    res, traces = {}, {}
    for name, solver, k, s, gov in arms:
        m, D = run_arm(args.scene, solver, k, s, args.relax, args.nframes,
                       governed=gov,
                       gap_preserving=(gov and args.gap_preserving))
        res[name], traces[name] = m, D
        sag_med, sag_pk = _sag(D)
        print(f"  {name:15s} {solver:7s} {k}x{s} gov={int(gov)}: "
              f"ratio={m['ratio']:12.7g}  E_mod_peak={m['e_modal_peak_J']:11.5g} J"
              f"  E_imp_peak={m['e_imp_peak_J']:8.4g} J"
              f"  sag_tail={1e3 * sag_med:7.3f} mm  peak|d|={1e3 * sag_pk:7.3f} mm"
              f"  KE@pk={100.0 * m['ke_frac_at_peak']:5.1f}%"
              f"  centroid={m['spectral_centroid_Hz']:7.1f} Hz"
              f"  E>10kHz={100.0 * m['energy_frac_above_10kHz']:6.3f}%"
              f"  [{m['wall_s']:.1f}s]", flush=True)

    # ---- R5.1 accuracy, against BOTH candidate references ------------------
    print("\n--- R5.1 accuracy: energy error to the reference ---")
    rows = []
    for ref in ("oracle", "xpbd_converged"):
        r_ref = res[ref]["ratio"]
        e_ref = res[ref]["e_modal_peak_J"]
        u, g = res["ungoverned"], res["governed"]
        print(f"  reference = {ref} (ratio {r_ref:.7g}, "
              f"E_mod_peak {e_ref:.5g} J)")
        print(f"    ratio error : ungoverned {u['ratio'] / r_ref:10.4g}x"
              f"   ->  governed {g['ratio'] / r_ref:8.4g}x")
        print(f"    energy error: ungoverned {u['e_modal_peak_J'] / e_ref:10.4g}x"
              f"   ->  governed {g['e_modal_peak_J'] / e_ref:8.4g}x"
              f"   ({u['e_modal_peak_J'] - e_ref:+.4g} J -> "
              f"{g['e_modal_peak_J'] - e_ref:+.4g} J)")
        linf_u = _linf(traces["ungoverned"], traces[ref])
        linf_g = _linf(traces["governed"], traces[ref])
        pk_ref = float(np.abs(traces[ref]).max()) if traces[ref].size else np.nan
        print(f"    deflection Linf: ungoverned {linf_u:.4g} m"
              f"  ->  governed {linf_g:.4g} m"
              f"   ({100.0 * linf_u / pk_ref:.1f}% -> "
              f"{100.0 * linf_g / pk_ref:.1f}% of reference peak)")
        rows.append(dict(
            reference=ref, ref_ratio=r_ref, ref_e_modal_peak_J=e_ref,
            ungoverned_ratio=u["ratio"], governed_ratio=g["ratio"],
            ungoverned_ratio_err_x=u["ratio"] / r_ref,
            governed_ratio_err_x=g["ratio"] / r_ref,
            ungoverned_E_err_x=u["e_modal_peak_J"] / e_ref,
            governed_E_err_x=g["e_modal_peak_J"] / e_ref,
            ungoverned_E_err_J=u["e_modal_peak_J"] - e_ref,
            governed_E_err_J=g["e_modal_peak_J"] - e_ref,
            ungoverned_linf_m=linf_u, governed_linf_m=linf_g,
            ref_peak_defl_m=pk_ref,
            ungoverned_linf_rel=linf_u / pk_ref,
            governed_linf_rel=linf_g / pk_ref))

    # ---- R5.4 normalized penetration ---------------------------------------
    print("\n--- R5.4 normalized penetration (E-S3 worst case = 21.6 mm) ---")
    sag_rows = []
    for ref in ("xpbd_converged", "oracle"):
        med, pk = _sag(traces[ref])
        print(f"  unclamped ({ref}, {args.sag_budget}): resting sag (tail median)"
              f" {1e3 * med:.3f} mm,  peak dynamic deflection {1e3 * pk:.3f} mm")
        print(f"      -> 21.6 mm = {21.6e-3 / med:5.2f}x the resting sag,"
              f"  {21.6e-3 / pk:5.2f}x the peak dynamic deflection")
        sag_rows.append(dict(reference=ref, sag_tail_median_m=med,
                             sag_peak_m=pk, pen_over_sag_x=21.6e-3 / med,
                             pen_over_peak_defl_x=21.6e-3 / pk))

    # ---- acceptance --------------------------------------------------------
    print("\n--- acceptance: reproduce the frozen cell EXACTLY ---")
    ok = True
    for name, want in FROZEN.items():
        got = res[name]["ratio"]
        d = abs(got - want)
        good = d <= TOL
        ok &= good
        print(f"  {name:12s} got {got!r}\n               want {want!r}"
              f"   |diff|={d:.3g}  {'OK' if good else 'MISMATCH'}")
    print(f"  => {'PASS' if ok else 'FAIL'}")

    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["section", "key", "value"])
        for name, m in res.items():
            for k2, v in m.items():
                w.writerow([f"arm:{name}", k2, v])
        for r in rows:
            for k2, v in r.items():
                w.writerow([f"accuracy:{r['reference']}", k2, v])
        for r in sag_rows:
            for k2, v in r.items():
                w.writerow([f"sag:{r['reference']}", k2, v])
    np.savez_compressed(os.path.join(OUT, f"{args.out}_traces.npz"), **traces)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=[args.scene],
        solvers=["xpbd", "impulse"],
        note=("R5 (plan §6.7 items 1,4): governed-vs-ungoverned accuracy at the "
              f"{args.scene} {args.cell} relax {args.relax} cell against TWO "
              "references (the implicit oracle at K=500 and the position-based "
              "host self-converged at K=500 -- R4 showed these differ by 9.6%), "
              "in ratio, in joules, and in deflection Linf; plus the unclamped "
              "steady-state sag used to normalize the E-S3 21.6 mm worst-case "
              "post-projection penetration. Reference arms are measurement-only "
              "(passivity_gamma forced to 1.0); the governed arm is the arm "
              "under test."))
    print(f"\nwrote {csv_path}")
    if args.check_frozen and not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
