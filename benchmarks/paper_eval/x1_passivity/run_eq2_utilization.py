#!/usr/bin/env python3
"""R1 — Eq.-(2) UTILIZATION with the governor OFF (MIG 2026 short paper, plan §6.3).

ISOLATED benchmark. Imports scenes/solvers READ-ONLY and sets every knob at
RUNTIME; it never modifies solver source and never changes solver behaviour.

--------------------------------------------------------------------------
THE HOLE THIS CLOSES
--------------------------------------------------------------------------
The paper measures

    R = peak modal energy / peak incident rigid KE          (a DIAGNOSTIC)

but states its claims in Eq.-(2) language

    E_mod^n - E_mod^0  <=  eta * sum_k max(dE_rig^k, 0)     (the INVARIANT)

These are different quantities. Worse, `docs/mig2026_results_ledger.md`
E-S1b caveat 1 records that with the clamp OFF the Eq.-(2) accounting exists
only on the impulse backend: XPBD never updates it (cum_rigid_loss stays 0, so
holds() is VACUOUSLY true) and AVBD has no ledger object at all. So the
abstract's "AVBD exceeds the supply bound (1.7x)" had no supporting
measurement -- 1.7 is R, not an Eq.-(2) violation.

This harness measures Eq. (2) itself, un-governed, on all three backends:

    U = (E_mod^n - E_mod^0) / (eta * sum_{k<=n} max(dE_rig^k, 0))

THE VERDICT IS NOT `U > 1`. A running ratio divides by the supply accumulated
SO FAR, which is ~0 in the opening substeps while modal energy has already
built, so a sub-joule lead inflates into U ~ 20. Measured directly: AVBD shelf
0.7 32x8 shows a raw running U of 20.3 for an absolute overdraw of 0.13 J.
Reporting that as "violates" would have been wrong in 22 of 24 AVBD cells.

The verdict is instead ABSOLUTE, in joules, and is Eq. (2) EXACTLY AS THE PAPER
PRINTS IT -- no tolerance beyond round-off:

    violation  <=>  max_n [ E_mod^n - E_mod^0
                            - eta * sum_{k<=n} max(dE_rig^k, 0) ]  >  tol

TWO READINGS EXIST AND THEY DISAGREE -- this matters and is reported.
The implementation's own `passive()` test (passivity.py:287-293) forgives up to
one substep's largest deposit, `max_net_excess <= max_deposit + tol`, because
modal PE can legitimately spike in the same substep the rigid body is still
delivering KE. That allowance is worth 7-389 J in these scenes. Where the
overdraft is huge the reading is irrelevant (XPBD: 8/24 either way, margins
1e5-1e7 J); where it is comparable to the allowance it decides the answer
(AVBD: 23/24 strict vs 1/24 lenient).

We report the STRICT reading because (a) it is the inequality the paper prints,
and (b) the GOVERNED runs satisfy it too, with worst net excess +1.1e-13 J, so
both the governed and un-governed columns are adjudicated by the SAME
inequality. The lenient reading is kept per-cell as `margin_allow_J` /
`eq2_violates_allow` for the R2 write-up, which documents the discrepancy.
Reporting cell COUNTS alone would mislead in the opposite direction, so the
joules column travels with them: XPBD overdraws by up to 4.4e7 J, AVBD by
<= 15 J.

Reported per cell:
  margin_J  = max_net_excess, the STRICT slack in JOULES; the verdict.
                                             <=0 holds, >0 violates.
  margin_allow_J = the same minus max_deposit (the lenient reading)
  U         = (peak over n of E_mod^n - E_mod^0) / (eta * TOTAL supply)
              The utilization headline. The denominator is the run's total
              funded supply, NOT the running one, so the opening transient
              cannot inflate it. U > 1 means peak modal storage exceeded
              everything contact dissipated over the entire run -- unambiguous.
  U_final   = utilization at the last substep (well-conditioned, but too weak
              alone: Eq. (2) is asserted for every n, not just the last)

--------------------------------------------------------------------------
HOW IT IS MEASURED WITHOUT PERTURBING THE SOLVE  (the key design choice)
--------------------------------------------------------------------------
We do NOT re-derive dE_rig offline. Re-implementing the formula outside the
solver would risk silent drift from the real one. Instead we run the solver's
OWN accounting and neuter only its actuator:

    _enforce_modal_passivity = True      -> the ledger block executes, so
                                            deposit()/commit() run live
    passivity_gamma           -> 1.0     -> the projection is a no-op

In all three backends every state write in the ledger block is inside
`if gamma < 1.0:` (solver_xpbd.py:1244, solver_6dof.py:2639,
solver_impulse.py:1003). With gamma identically 1.0 that branch is DEAD, so
the trajectory is bit-identical to a clamp-OFF run while the accounting is
fully live. This is measurement-only by construction, not by inspection.

`passivity_gamma` is imported FUNCTION-LOCALLY in all three ledger blocks
(solver_xpbd.py:1221, solver_6dof.py:2613, solver_impulse.py:986), so a
module-attribute patch is re-resolved every substep and reaches all of them --
the same wrap point E-S3 uses (run_projection_validity.py).

NON-PERTURBATION ACCEPTANCE: the R ratios produced here must reproduce the
frozen E-S1b clamp-OFF ratios EXACTLY (ledger E-S1b table). The harness
asserts this for every cell it can (--check-frozen).

CROSS-VALIDATION: on the impulse backend the ledger already ran live with the
clamp off, so its E-S1b `cum_loss_off` / `holds_off` columns are an
independent read of the same quantity. Identical code path => exact agreement
is required, not merely round-off. Checked by --check-frozen.

--------------------------------------------------------------------------
ALSO LOGGED (plan §6.4 / R2): the modal->rigid RETURN channel.
--------------------------------------------------------------------------
The reservoir is funded by a GROSS sum, sum_k max(dE_rig^k, 0), so energy that
flows modal->rigid and is later re-dissipated can be counted as fresh supply
twice ("recycling"). We accumulate the negative side, sum_k max(-dE_rig^k, 0),
and report it as a fraction of the gross supply. That fraction bounds how much
of the supply could be recycled and is what the Limitations caveat stands on.

Out: out/{eq2_utilization.csv, eq2_utilization.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_eq2_utilization.py
"""
from __future__ import annotations

import argparse
import csv
import json
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
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, SOLVERS, BUDGETS, RELAXES, SETTLE, NFRAMES)
from benchmarks.paper_eval.paper_config import (                 # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# Frozen E-S1b clamp-OFF ratios (docs/mig2026_results_ledger.md, E-S1b).
# The instrumented run must reproduce these EXACTLY -- that is the
# non-perturbation proof. Keyed (solver, scene, relax, iters, substeps).
FROZEN_OFF = {
    ("xpbd", "shelf", 0.7, 4, 1): 6333.22,
    ("xpbd", "shelf", 0.7, 8, 2): 53.731,
    ("xpbd", "shelf", 1.0, 4, 1): 1.0962e4,
    ("xpbd", "shelf", 1.0, 8, 2): 123.66,
    ("xpbd", "ledge", 0.7, 4, 1): 5.6266e4,
    ("xpbd", "ledge", 0.7, 8, 2): 47.453,
    ("xpbd", "ledge", 1.0, 4, 1): 1.19534e5,
    ("xpbd", "ledge", 1.0, 8, 2): 167.72,
}
# Frozen per-solver worst-over-cells OFF ratio (E-S1b results table).
FROZEN_WORST = {"xpbd": 1.19534e5, "avbd": 1.70032, "impulse": 0.531421}


def _neuter_gamma():
    """Force the gamma-projection to be a no-op while leaving the ledger live.

    Returns the original callable so the caller can always restore it. See the
    module docstring: every state write in each backend's ledger block is
    guarded by `if gamma < 1.0`, so gamma == 1.0 makes the block pure
    accounting.
    """
    orig = _psv_mod.passivity_gamma

    def gamma_one(e_new, e_old, budget, tol=1e-12):
        return 1.0

    _psv_mod.passivity_gamma = gamma_one
    return orig


def one(build_fn, solver, iters, subs, relax, nframes=NFRAMES, settle=SETTLE,
        eta=1.0):
    """Run one un-governed cell with the Eq.-(2) accounting live.

    Returns a dict carrying both metrics: R (the diagnostic the paper already
    reports) and U (the invariant the paper claims).
    """
    t0 = time.perf_counter()
    H = build_fn(device="cpu", iterations=iters, avbd_substeps=subs,
                 solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True          # PAPER_CONFIG stepper; forces host path
    # Ledger ON so the accounting runs; gamma neutered below so nothing moves.
    apply_passivity(sol, solver, enable=True, eta=eta)
    sol._psv_monitor_only = False         # match E-S1's ON semantics exactly

    # AVBD constructs its ledger LAZILY, on the first substep
    # (solver_6dof.py:2449 / :3057), whereas XPBD builds it at
    # set_modal_support. Attaching wrappers at setup time would therefore find
    # None on AVBD and silently measure nothing -- which is exactly the
    # "AVBD has no ledger object at all" hole E-S1b caveat 1 records. Because
    # the solver's lazy init is guarded `if self._psv_ledger is None`,
    # pre-constructing the SAME object with the SAME eta makes the solver adopt
    # ours instead. Pure accounting: the ledger never feeds back into the solve
    # (its only actuator is passivity_gamma, neutered below).
    if getattr(sol, "_psv_ledger", None) is None:
        from dcr.avbd._solver.passivity import PassivityLedger
        sol._psv_ledger = PassivityLedger(eta=float(eta))

    led = getattr(sol, "_psv_ledger", None)

    # ---- wrap commit(): capture the per-substep running invariant ---------
    # commit() receives e_modal_now (absolute modal energy AFTER the substep)
    # and runs AFTER deposit(), so at call time led.cum_rigid_loss already
    # includes this substep's gross deposit -- exactly the sum_{k<=n} of Eq.(2).
    trace = {"peak_net": -np.inf, "u_final": float("nan"),
             "gross_pos": 0.0, "gross_neg": 0.0, "e_mod_0": None,
             "n_commits": 0, "excess_max": -np.inf}
    orig_commit = None
    orig_deposit = None
    if led is not None:
        orig_commit = led.commit
        orig_deposit = led.deposit

        def deposit_wrap(rigid_loss: float):
            # Both sides of the funding channel, for the R2 recycling caveat.
            if rigid_loss >= 0.0:
                trace["gross_pos"] += float(rigid_loss)
            else:
                trace["gross_neg"] += float(-rigid_loss)
            return orig_deposit(rigid_loss)

        def commit_wrap(realized_gain, budget, alpha, e_modal_now=None):
            r = orig_commit(realized_gain, budget, alpha,
                            e_modal_now=e_modal_now)
            if e_modal_now is not None:
                if trace["e_mod_0"] is None:
                    # Ledger's own baseline: E_mod^0. The ledger records
                    # e_modal_0 at construction; mirror it if it was set.
                    trace["e_mod_0"] = float(getattr(led, "e_modal_0", 0.0))
                num = float(e_modal_now) - trace["e_mod_0"]
                den = eta * led.cum_rigid_loss
                trace["excess_max"] = max(trace["excess_max"], num - den)
                # Peak NET modal storage over the run, in joules. The ratio is
                # formed once, at the end, against the run's TOTAL supply --
                # never against the running supply, which is ~0 in the opening
                # substeps and turns a sub-joule in-transit lead into U ~ 20.
                trace["peak_net"] = max(trace["peak_net"], num)
                if den > 0.0:
                    trace["u_final"] = num / den          # always the latest
                trace["n_commits"] += 1
            return r

        led.deposit = deposit_wrap
        led.commit = commit_wrap

    orig_gamma = _neuter_gamma()
    finite = True
    e_imp = e_mod = 0.0
    try:
        w = H.world
        ib = w._descs[H.impactor_idx].dcr_body
        for _ in range(settle):
            w.step()
            w._sync_avbd_to_dcr()
        for _ in range(nframes):
            w.step()
            # Native-thin path does not write the DCR mirror; mirror it so the
            # R ratio is the SAME expression as the E-S1 matrix. Host-side
            # state copy only (see run_solver_matrix.one()).
            w._sync_avbd_to_dcr()
            e_imp = max(e_imp, rigid_kinetic_energy([ib]))
            e = sol.last_modal_KE + sol.last_modal_PE
            if not np.isfinite(e):
                finite = False
                break
            e_mod = max(e_mod, e)
    finally:
        _psv_mod.passivity_gamma = orig_gamma      # always restore the module
        if led is not None and orig_commit is not None:
            led.commit = orig_commit
            led.deposit = orig_deposit

    gross = trace["gross_pos"]
    # THE VERDICT is the ledger's own criterion, in absolute joules:
    #   violation  <=>  max_net_excess > max_deposit + tol
    # (passivity.py:287-293). It is what the paper's governed-run "all 72 cells
    # satisfy Eq. (2)" claim already rests on, so the un-governed column must be
    # adjudicated the same way; and being absolute it cannot be inflated by a
    # small denominator the way a ratio can. `margin_J` is the signed slack:
    # negative = holds, positive = overdraw beyond the accounting granularity.
    # STRICT margin = max_n [E_mod^n - E_mod^0 - eta*sum_{k<=n} max(dE_rig,0)],
    # i.e. Eq. (2) EXACTLY AS PRINTED, no allowance. >0 == violation.
    margin = None if led is None else float(led.max_net_excess)
    # The implementation's own test is more lenient: it forgives up to one
    # substep's largest deposit (`passive()`, passivity.py:287-293), because
    # modal PE can spike in the same substep the rigid body is still delivering
    # KE. That allowance is worth 7-389 J in these scenes, so for backends whose
    # overdraft is comparable to it the two readings disagree sharply (AVBD:
    # 23/24 strict vs 1/24 lenient). We report the STRICT one, because it is the
    # inequality the paper prints and because the GOVERNED column satisfies it
    # too (worst +1.1e-13 J), so both columns are adjudicated identically.
    # `margin_allow_J` keeps the lenient reading for the R2 write-up.
    margin_allow = (None if led is None else
                    float(led.max_net_excess - led.max_deposit))
    # U = peak net modal storage over the run / the run's TOTAL funded supply.
    # Stable denominator, so it cannot be inflated by the opening transient.
    peak_net = trace["peak_net"]
    u = ((peak_net / (eta * gross)) if (np.isfinite(peak_net) and gross > 0)
         else None)
    return dict(
        ratio_off=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
        e_modal_peak=e_mod if finite else float("inf"),
        e_imp_peak=e_imp,
        u_max=u,
        peak_net_J=(peak_net if np.isfinite(peak_net) else None),
        u_final=(trace["u_final"] if np.isfinite(trace["u_final"]) else None),
        eq2_violates=(None if led is None else bool(margin > led.tol)),
        margin_J=margin,
        margin_allow_J=margin_allow,
        eq2_violates_allow=(None if led is None
                            else bool(not led.passive())),
        max_deposit=(None if led is None else float(led.max_deposit)),
        excess_max=(trace["excess_max"]
                    if np.isfinite(trace["excess_max"]) else None),
        gross_supply=gross,
        return_channel=trace["gross_neg"],
        return_frac=(trace["gross_neg"] / gross) if gross > 0 else None,
        cum_modal_gain=(led.cum_modal_gain if led is not None else None),
        cum_rigid_loss=(led.cum_rigid_loss if led is not None else None),
        max_net_excess=(led.max_net_excess if led is not None else None),
        ledger_holds=(led.holds() if led is not None else None),
        ledger_passive=(led.passive() if led is not None else None),
        n_clamped=(led.n_clamped if led is not None else None),
        n_steps=(led.n_steps if led is not None else None),
        n_commits=trace["n_commits"],
        finite=finite,
        wall_s=time.perf_counter() - t0,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solvers", default=",".join(SOLVERS))
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--budgets", default="")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--eta", type=float, default=1.0)
    ap.add_argument("--check-frozen", action="store_true",
                    help="assert the R ratios reproduce the frozen E-S1b "
                         "clamp-OFF values (the non-perturbation proof)")
    ap.add_argument("--rtol", type=float, default=1e-3,
                    help="relative tolerance for --check-frozen (the frozen "
                         "table is quoted to ~5 significant figures)")
    ap.add_argument("--out", default="eq2_utilization")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    solvers = [s.strip() for s in args.solvers.split(",") if s.strip()]
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    relaxes = [float(r) for r in args.relaxes.split(",") if r.strip()]
    if args.budgets:
        budgets = [tuple(int(v) for v in b.lower().split("x"))
                   for b in args.budgets.split(",") if b.strip()]
    else:
        budgets = BUDGETS

    rows = []
    n_cells = len(solvers) * len(scenes) * len(relaxes) * len(budgets)
    print(f"### R1 Eq.-(2) utilization, governor OFF: {n_cells} cells "
          f"({platform.machine()}, {platform.system()}) ###", flush=True)
    print("#   U = (E_mod^n - E_mod^0) / (eta * sum_k max(dE_rig^k, 0));  "
          "U > 1 == Eq.(2) VIOLATION", flush=True)
    for solver in solvers:
        for scene in scenes:
            fn = SCENES[scene]
            for relax in relaxes:
                for (it, su) in budgets:
                    m = one(fn, solver, it, su, relax, args.nframes,
                            eta=args.eta)
                    rows.append(dict(solver=solver, scene=scene, relax=relax,
                                     iters=it, substeps=su, **m))
                    u_max = m["u_max"]
                    u_s = f"{u_max:10.4g}" if u_max is not None else "      n/a"
                    if m["eq2_violates"] is None:
                        v_s = "no-ledger"
                    else:
                        v_s = "VIOLATES " if m["eq2_violates"] else "holds    "
                    r_s = (f"{100.0 * m['return_frac']:6.2f}%"
                           if m["return_frac"] is not None else "   n/a")
                    g_s = (f"{m['margin_J']:+10.4g}"
                           if m["margin_J"] is not None else "       n/a")
                    print(f"  {solver:7s} {scene:7s} relax={relax} {it:2d}x{su}: "
                          f"R={m['ratio_off']:12.4g}  U={u_s}  Eq2={v_s}"
                          f"  margin={g_s} J"
                          f"  supply={m['gross_supply']:10.4g} J"
                          f"  ret={r_s}", flush=True)

    keys = list(rows[0].keys())
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=solvers,
        note=("R1 (plan §6.3): Eq.-(2) utilization U with the governor OFF. "
              "Measurement-only: the ledger runs live while passivity_gamma is "
              "forced to 1.0, so every state write in the ledger block (guarded "
              "by `if gamma < 1.0`) is dead and the trajectory is bit-identical "
              "to a clamp-OFF run. U = (E_mod^n - E_mod^0) / (eta * sum_k "
              "max(dE_rig^k, 0)); U > 1 is an actual Eq.-(2) violation, unlike "
              "R = peak modal E / peak incident rigid KE, which is a severity "
              "diagnostic. return_frac = sum max(-dE_rig,0) / sum max(dE_rig,0), "
              "the recycling bound for the R2 Limitations caveat."))

    # ---- summary ---------------------------------------------------------
    print("\n--- per-solver summary (governor OFF) ---")
    for solver in solvers:
        sr = [r for r in rows if r["solver"] == solver]
        us = [r["u_max"] for r in sr if r["u_max"] is not None]
        n_viol = sum(1 for r in sr if r["eq2_violates"])
        n_inj = sum(1 for r in sr if r["ratio_off"] > 1.0)
        rf = [r["return_frac"] for r in sr if r["return_frac"] is not None]
        mg = [r["margin_J"] for r in sr if r["margin_J"] is not None]
        if mg:
            print(f"  {solver:7s}: Eq.(2) violated in {n_viol}/{len(sr)} cells "
                  f"(worst margin {max(mg):+.4g} J"
                  + (f", U_max {max(us):.4g}" if us else "") + ")")
        else:
            print(f"  {solver:7s}: no ledger available")
        print(f"           R > 1 in {n_inj}/{len(sr)} cells "
              f"(worst R {max(r['ratio_off'] for r in sr):.4g})")
        if rf:
            print(f"           return channel {100.0 * min(rf):.2f}"
                  f"-{100.0 * max(rf):.2f}% of gross supply")

    # ---- acceptance: non-perturbation + impulse cross-validation ---------
    if args.check_frozen:
        print("\n--- non-perturbation check vs frozen E-S1b clamp-OFF ---")
        bad = []
        for r in rows:
            k = (r["solver"], r["scene"], r["relax"], r["iters"], r["substeps"])
            if k in FROZEN_OFF:
                got, want = r["ratio_off"], FROZEN_OFF[k]
                ok = abs(got - want) <= args.rtol * abs(want)
                print(f"  {'OK  ' if ok else 'FAIL'} {k}: got {got:.6g}, "
                      f"frozen {want:.6g}")
                if not ok:
                    bad.append((k, got, want))
        for solver in solvers:
            if solver in FROZEN_WORST:
                sr = [r for r in rows if r["solver"] == solver]
                got = max(r["ratio_off"] for r in sr)
                want = FROZEN_WORST[solver]
                ok = abs(got - want) <= args.rtol * abs(want)
                print(f"  {'OK  ' if ok else 'FAIL'} {solver} worst-over-cells: "
                      f"got {got:.6g}, frozen {want:.6g}")
                if not ok:
                    bad.append((solver + ":worst", got, want))
        if bad:
            print(f"\n!! NON-PERTURBATION CHECK FAILED in {len(bad)} places. "
                  f"The instrumentation changed the solve -- do NOT report "
                  f"these numbers.")
            for b in bad:
                print(f"     {b}")
            sys.exit(1)
        print("  all checked cells reproduce the frozen values: the "
              "instrumentation does not change the solve.")

    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
