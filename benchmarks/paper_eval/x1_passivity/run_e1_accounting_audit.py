#!/usr/bin/env python3
"""E1 — gravity / no-contact accounting audit (rewrite plan §9 E1).

ISOLATED benchmark. Imports scenes/solvers READ-ONLY, sets every knob at
RUNTIME, never edits solver source. Same measurement-only contract as R1
(`run_eq2_utilization.py`): the reservoir ledger runs LIVE while
`passivity_gamma` is forced to 1.0, so every state write in the ledger block
(guarded by `if gamma < 1.0`) is DEAD and the trajectory is bit-identical to a
clamp-OFF run. We measure the ledger, we do not steer with it.

--------------------------------------------------------------------------
WHAT THIS ESTABLISHES: the ACCOUNTING NOISE FLOOR.
--------------------------------------------------------------------------
The paper's cross-host control claim is "the augmented-Lagrangian host overdraws
by at most 6.7 J (3/24 cells), a mild control against the position-based host's
4.4e7 J." For "overdraws by 6.7 J" to mean "injects a little via contact", the
6.7 J must sit ABOVE the accounting floor -- the ledger margin that appears with
NO contact-to-modal injection at all. If the floor is comparable to 6.7 J, the
small AVBD overdrafts cannot be read as contact injection and the cross-control
claim must narrow (plan §9 E1). The catastrophic 4.4e7 J XPBD evidence is
unaffected either way -- it is seven orders above any conceivable floor.

Two no-injection controls, per host and per schedule (all scenes):

  resting_no_impact : impactor raised 50 m out of reach, so NO impact event ever
                   occurs; the scene's standing books rest on the modal support
                   under real (resting) contact. Any ledger margin here is
                   accounting residual -- there is no impact to inject modal
                   energy. This is the IN-REGIME floor: the same contact that the
                   paper runs, minus the injection event. (The strict zero-contact
                   variant is trivial here: the modal gravity load is exactly zero
                   in these scenes, verified, so with no contact the modes are
                   never excited and E_mod == 0 identically.)
  modal_freevib  : resting_no_impact + an initial modal velocity kick (~1 J), so
                   the modes ring while riding the resting contact -- exactly the
                   paper's regime, minus impact. E_mod^0 is taken AFTER the kick,
                   supply is ~0, so a stepper that conserves/decays gives
                   margin <= 0. Any large positive margin is energy CREATED
                   downstream of the kick -- the modal-channel floor.

The position-based host is NOT expected to show a small floor here: it injects
from the resting-book settling alone at a starved budget (consistent with its
in-regime 4.4e7 J catastrophe), so its "floor" is moot. The floor that gates the
cross-host control claim is the augmented-Lagrangian / implicit one.

The residual reported per cell is `margin_J` = the ledger's strict
`max_net_excess` -- the SAME quantity the paper's headline verdict uses, so the
floor is measured in the headline's own units.

Out: out/{e1_accounting_audit.csv, e1_accounting_audit.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_e1_accounting_audit.py
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

import dcr.avbd._solver.passivity as _psv_mod                      # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy                  # noqa: E402
from benchmarks.paper_eval.x1_passivity.run_solver_matrix import (  # noqa: E402
    SCENES, SOLVERS, BUDGETS, SETTLE, NFRAMES)
from benchmarks.paper_eval.x1_passivity.run_eq2_utilization import (  # noqa: E402
    _neuter_gamma)
from benchmarks.paper_eval.paper_config import (                   # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

RAISE_M = 50.0          # impactor drop height (m); free-fall over 0.9 s ~ 4 m
KICK_J = 1.0            # target modal KE for the free-vibration control
# The number every floor is compared against: worst AVBD overdraft in the sweep
# (dinner 4x1, +6.7 J). Frozen in eq2_utilization.csv / ledger §R1.
AVBD_EFFECT_J = 6.7


def _modal_mass(sol, r):
    """Return the (r,) diagonal modal mass, or ones if mass-normalized/unknown."""
    mq = getattr(sol, "_mq", None)
    if mq is None:
        M = getattr(sol, "_Mq", None)
        if M is not None:
            M = np.asarray(M, dtype=np.float64)
            mq = np.diag(M) if M.ndim == 2 else M
    return (np.asarray(mq, dtype=np.float64) if mq is not None else np.ones(r))


def _kick_modes(sol, energy_J):
    """Set an initial modal velocity carrying ~energy_J of modal KE.

    Handles the two modal-velocity handles: `_qdot` (XPBD/impulse) and
    `_qdot_modal_host` (AVBD). Returns the realized KE, or None if neither is
    present. With mass-normalized modes E_KE = 1/2 qdot^T M_q qdot."""
    attr = ("_qdot" if getattr(sol, "_qdot", None) is not None
            else "_qdot_modal_host"
            if getattr(sol, "_qdot_modal_host", None) is not None else None)
    if attr is None:
        return None
    r = np.asarray(getattr(sol, attr), dtype=np.float64).shape[0]
    if r == 0:
        return None
    m = _modal_mass(sol, r)
    c = float(np.sqrt(2.0 * energy_J / max(float(np.sum(m)), 1e-30)))
    qd = np.full(r, c, dtype=np.float64)
    setattr(sol, attr, qd)
    return 0.5 * float(qd @ (m * qd))


def one(build_fn, solver, iters, subs, relax, control, eta=1.0,
        nframes=NFRAMES, settle=SETTLE):
    """Run one no-injection control cell with the Eq.-(2) ledger live."""
    t0 = time.perf_counter()
    # Raise the impactor 50 m so no impact ever occurs. Builders name the drop
    # height differently: shelf/ledge `impactor_drop_height`, dinner
    # `pot_drop_height`. Cargo kwargs are common to all three.
    common = dict(device="cpu", iterations=iters, avbd_substeps=subs,
                  solver=solver, cargo_material=None, cargo_all=False,
                  cargo_n_elastic=0)
    try:
        H = build_fn(impactor_drop_height=RAISE_M, **common)
    except TypeError:
        H = build_fn(pot_drop_height=RAISE_M, **common)
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=True, eta=eta)
    sol._psv_monitor_only = False

    kick_realized = None
    if control == "modal_freevib":
        kick_realized = _kick_modes(sol, KICK_J)

    if getattr(sol, "_psv_ledger", None) is None:
        from dcr.avbd._solver.passivity import PassivityLedger
        sol._psv_ledger = PassivityLedger(eta=float(eta))
    led = sol._psv_ledger

    trace = {"peak_net": -np.inf, "gross_pos": 0.0, "gross_neg": 0.0,
             "e_mod_0": None}
    orig_commit = led.commit
    orig_deposit = led.deposit

    def deposit_wrap(rigid_loss: float):
        if rigid_loss >= 0.0:
            trace["gross_pos"] += float(rigid_loss)
        else:
            trace["gross_neg"] += float(-rigid_loss)
        return orig_deposit(rigid_loss)

    def commit_wrap(realized_gain, budget, alpha, e_modal_now=None):
        r = orig_commit(realized_gain, budget, alpha, e_modal_now=e_modal_now)
        if e_modal_now is not None:
            if trace["e_mod_0"] is None:
                trace["e_mod_0"] = float(getattr(led, "e_modal_0", 0.0))
            trace["peak_net"] = max(trace["peak_net"],
                                    float(e_modal_now) - trace["e_mod_0"])
        return r

    led.deposit = deposit_wrap
    led.commit = commit_wrap

    orig_gamma = _neuter_gamma()
    finite = True
    e_mod = 0.0
    try:
        w = H.world
        ib = w._descs[H.impactor_idx].dcr_body
        for _ in range(settle):
            w.step(); w._sync_avbd_to_dcr()
        for _ in range(nframes):
            w.step(); w._sync_avbd_to_dcr()
            e = sol.last_modal_KE + sol.last_modal_PE
            if not np.isfinite(e):
                finite = False
                break
            e_mod = max(e_mod, e)
        _ = rigid_kinetic_energy([ib])          # touch, keeps the mirror synced
    finally:
        _psv_mod.passivity_gamma = orig_gamma
        led.commit = orig_commit
        led.deposit = orig_deposit

    gross = trace["gross_pos"]
    margin = float(led.max_net_excess)
    peak_net = trace["peak_net"] if np.isfinite(trace["peak_net"]) else None
    return dict(
        control=control, solver=solver, iters=iters, substeps=subs,
        relax=relax,
        margin_J=margin,                       # THE residual (strict verdict)
        eq2_violates=bool(margin > led.tol),
        gross_supply_J=gross,
        return_channel_J=trace["gross_neg"],
        cum_modal_gain_J=float(led.cum_modal_gain),
        peak_net_modal_J=peak_net,
        peak_modal_E_J=e_mod if finite else float("inf"),
        kick_realized_J=kick_realized,
        n_steps=int(getattr(led, "n_steps", 0)),
        finite=finite,
        wall_s=time.perf_counter() - t0,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solvers", default=",".join(SOLVERS))
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--controls",
                    default="resting_no_impact,modal_freevib")
    ap.add_argument("--budgets", default="")
    ap.add_argument("--relax", type=float, default=0.7)
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--eta", type=float, default=1.0)
    ap.add_argument("--out", default="e1_accounting_audit")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    solvers = [s.strip() for s in args.solvers.split(",") if s.strip()]
    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    controls = [c.strip() for c in args.controls.split(",") if c.strip()]
    if args.budgets:
        budgets = [tuple(int(v) for v in b.lower().split("x"))
                   for b in args.budgets.split(",") if b.strip()]
    else:
        budgets = BUDGETS

    rows = []
    n = len(controls) * len(solvers) * len(scenes) * len(budgets)
    print(f"### E1 accounting audit: {n} control cells "
          f"({platform.machine()}, {platform.system()}); "
          f"floor vs the {AVBD_EFFECT_J} J AVBD effect ###", flush=True)
    for control in controls:
        for solver in solvers:
            for scene in scenes:
                fn = SCENES[scene]
                for (it, su) in budgets:
                    m = one(fn, solver, it, su, args.relax, control,
                            eta=args.eta, nframes=args.nframes)
                    rows.append(dict(scene=scene, **m))
                    print(f"  {control:14s} {solver:7s} {scene:7s} {it:2d}x{su}"
                          f" relax={args.relax}: margin={m['margin_J']:+11.4g} J"
                          f"  supply={m['gross_supply_J']:10.4g} J"
                          f"  modal_gain={m['cum_modal_gain_J']:10.4g} J"
                          f"  {'VIOLATES' if m['eq2_violates'] else 'holds'}",
                          flush=True)

    keys = list(rows[0].keys())
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=solvers,
        note=("E1 (rewrite plan §9): gravity/no-contact accounting audit. Three "
              "no-injection controls (freefall, freefall_pin, modal_freevib) run "
              "with cargo removed and the impactor raised 50 m so NO contact ever "
              "occurs. Ledger live, passivity_gamma==1.0 (dead actuator), so this "
              "is measurement-only. margin_J = ledger strict max_net_excess = the "
              "accounting FLOOR in the headline verdict's own units; compared to "
              "the 6.7 J worst AVBD overdraft. freefall_pin zeroes modal gravity "
              "(pure numerical floor); modal_freevib kicks the modes ~1 J with no "
              "contact (modal-stepper floor)."))

    # ---- floor summary vs 6.7 J -----------------------------------------
    # The FLOOR is the ledger margin NOT explained by a deliberate input. For
    # modal_freevib we injected ~1 J by hand, so the residual worth reading is
    # margin - kick (energy the stepper created downstream of the kick); a
    # negative value means the stepper decayed the kick (no creation). For
    # resting_no_impact there is no kick, so the residual is the margin itself.
    def _floor(r):
        k = r.get("kick_realized_J")
        return r["margin_J"] - (float(k) if (r["control"] == "modal_freevib"
                                             and k is not None) else 0.0)
    print("\n--- accounting floor vs the 6.7 J AVBD effect "
          "(modal_freevib: margin net of the ~1 J kick) ---")
    for solver in solvers:
        for control in controls:
            sr = [r for r in rows if r["solver"] == solver
                  and r["control"] == control and r["finite"]]
            if not sr:
                continue
            worst = max(sr, key=_floor)
            worst_floor = _floor(worst)
            print(f"  {solver:7s} {control:17s}: worst floor "
                  f"{worst_floor:+.4g} J "
                  f"({worst['scene']} {worst['iters']}x{worst['substeps']}) "
                  f"[{'<<' if abs(worst_floor) < 0.1 * AVBD_EFFECT_J else '!!'} "
                  f"6.7 J]")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
