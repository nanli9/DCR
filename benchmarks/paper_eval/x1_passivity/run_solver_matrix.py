#!/usr/bin/env python3
"""E-S1 — the three-solver adversarial budget matrix (MIG 2026 short paper).

ISOLATED benchmark. Imports scenes/solvers READ-ONLY and sets every knob at
RUNTIME; it never modifies solver source.

Ports the `benchmark`-branch X1 harness *configuration*
(`x1_passivity/run_robustness_clamp.py`: 3 scenes x relax {0.7, 1.0} x budget
{4x1, 8x2, 16x4, 32x8} = 24 cells) to all THREE solver backends, so the paper's
three-solver table is symmetric: same scenes, same cells, same metric, ONE
machine. No branch merge -- the config is re-implemented here.

Metric per cell (identical to the XPBD reference matrix):
    ratio     = peak modal energy (KE+PE) / peak incident rigid KE of the impactor
                -- an intensity diagnostic, NOT the enforced invariant.
    passive() = reservoir / net-excess ledger invariant.
    holds()   = cumulative ledger invariant  cum_modal_gain <= eta * cum_rigid_loss
                (foundation §15). This is the enforced one.

Both OFF (no enforcement) and ON (enforcement) are run per cell.

Enforcement semantics: "ON" here means the ACTIVE gamma-projection on all three
backends -- `_psv_monitor_only` is forced False even for AVBD, whose repo default
is monitor-only (solver_6dof.py:653). That makes the ON column mean the same
thing in every row. The monitor-only AVBD default is the paper's production
setting and is unchanged in the solver; this is a measurement-side override.

KNOWN, DELIBERATE ASYMMETRY (report it, do not hide it): on `SolverImpulse` the
attributes `modal_relax`, `_support_block_relax` and `_modal_symplectic` exist
but are never read (solver_impulse.py:290-292 -- the implicit modal weight
(M + hD + h^2 K)^-1 needs no under-relaxation). The relax axis is therefore
INERT on that backend by construction. We still run all 24 cells for table
symmetry and check that the two relax rows come out bit-identical; that check is
itself the formulation-vs-iteration evidence.

Out: out/{solver_matrix.csv, solver_matrix.config.json}
Run: .venv/bin/python benchmarks/paper_eval/x1_passivity/run_solver_matrix.py
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

from scenes.reduced_shelf import build_reduced_shelf            # noqa: E402
from scenes.reduced_ledge import build_reduced_ledge            # noqa: E402
from scenes.reduced_dinner_table import build_reduced_dinner_table  # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy               # noqa: E402
from benchmarks.paper_eval.paper_config import (                # noqa: E402
    apply_relax, apply_passivity, write_manifest)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table}
SOLVERS = ("xpbd", "avbd", "impulse")
BUDGETS = [(4, 1), (8, 2), (16, 4), (32, 8)]
RELAXES = [0.7, 1.0]
SETTLE = 8       # settle frames before logging (matches the reference harness)
NFRAMES = 100    # logged frames        (matches the reference harness)


def one(build_fn, solver, iters, subs, relax, enforce, nframes=NFRAMES,
        settle=SETTLE, eta=1.0, gap_preserving=False):
    """Run one cell. Returns the metric dict; never raises on blow-up."""
    t0 = time.perf_counter()
    H = build_fn(device="cpu", iterations=iters, avbd_substeps=subs,
                 solver=solver)
    sol = H.world._solver
    apply_relax(sol, solver, relax)
    # Pinned modal stepper (PAPER_CONFIG stepper="symplectic"). Live on
    # xpbd/avbd; inert on impulse (attribute exists, never read).
    sol._modal_symplectic = True
    apply_passivity(sol, solver, enable=enforce, eta=eta)
    # Make "ON" mean the same thing on all three backends: the ACTIVE
    # gamma-projection. apply_passivity() forces monitor-only for avbd (its
    # production default); override so the ON column is comparable.
    sol._psv_monitor_only = False
    # Follow-up projection (default OFF reproduces every frozen number).
    sol._psv_gap_preserving = bool(gap_preserving)

    w = H.world
    ib = w._descs[H.impactor_idx].dcr_body
    for _ in range(settle):
        w.step()
        w._sync_avbd_to_dcr()
    e_imp = e_mod = 0.0
    finite = True
    for _ in range(nframes):
        w.step()
        # These scenes run the NATIVE-THIN step path (world.py:779-793): with no
        # DCR coupler attached, world.step() returns before _sync_avbd_to_dcr(),
        # so the dcr_body mirror is never written and rigid_kinetic_energy() on
        # it reads a permanent zero. The reference X1 matrix was generated on a
        # branch whose scenes attached a coupler, so the mirror was live there.
        # Mirror it explicitly here so the metric is computed from exactly the
        # same expression as the reference harness. Host-side state copy only —
        # nothing in the thin path reads the mirror, so this cannot perturb the
        # solve (verified: it reproduces the reference XPBD cells).
        w._sync_avbd_to_dcr()
        e_imp = max(e_imp, rigid_kinetic_energy([ib]))
        e = sol.last_modal_KE + sol.last_modal_PE
        if not np.isfinite(e):
            finite = False
            break
        e_mod = max(e_mod, e)
    L = getattr(sol, "_psv_ledger", None)
    return dict(
        ratio=(e_mod / max(e_imp, 1e-9)) if finite else float("inf"),
        e_modal_peak=e_mod if finite else float("inf"),
        e_imp_peak=e_imp,
        passive=(L.passive() if L is not None else None),
        holds=(L.holds() if L is not None else None),
        cum_modal_gain=(L.cum_modal_gain if L is not None else None),
        cum_rigid_loss=(L.cum_rigid_loss if L is not None else None),
        max_net_excess=(L.max_net_excess if L is not None else None),
        n_clamped=(L.n_clamped if L is not None else None),
        n_steps=(L.n_steps if L is not None else None),
        finite=finite,
        wall_s=time.perf_counter() - t0,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solvers", default=",".join(SOLVERS),
                    help="comma list from xpbd,avbd,impulse")
    ap.add_argument("--scenes", default="shelf,ledge,dinner")
    ap.add_argument("--budgets", default="",
                    help="e.g. 4x1,8x2 (default: all four)")
    ap.add_argument("--relaxes", default="0.7,1.0")
    ap.add_argument("--on-mode", default="all", choices=("all", "injecting"),
                    help="run enforcement ON for every cell, or only for cells "
                         "whose OFF run injects (ratio > 1)")
    ap.add_argument("--nframes", type=int, default=NFRAMES)
    ap.add_argument("--gap-preserving", action="store_true",
                    help="run the ON column with the gap-preserving projection "
                         "instead of the shipped radial gamma (follow-up; the "
                         "OFF column is unaffected either way)")
    ap.add_argument("--out", default="solver_matrix")
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
    print(f"### E-S1 three-solver matrix: {n_cells} cells "
          f"({platform.machine()}, {platform.system()}) ###", flush=True)
    for solver in solvers:
        for scene in scenes:
            fn = SCENES[scene]
            for relax in relaxes:
                for (it, su) in budgets:
                    off = one(fn, solver, it, su, relax, False, args.nframes)
                    injects = (not off["finite"]) or off["ratio"] > 1.0
                    if args.on_mode == "all" or injects:
                        on = one(fn, solver, it, su, relax, True, args.nframes,
                                 gap_preserving=args.gap_preserving)
                    else:
                        on = {k: None for k in off}
                        on["finite"] = None
                    rows.append(dict(
                        solver=solver, scene=scene, relax=relax,
                        iters=it, substeps=su, injects_off=injects,
                        ratio_off=off["ratio"], ratio_on=on["ratio"],
                        passive_off=off["passive"], passive_on=on["passive"],
                        holds_off=off["holds"], holds_on=on["holds"],
                        cum_gain_off=off["cum_modal_gain"],
                        cum_gain_on=on["cum_modal_gain"],
                        cum_loss_off=off["cum_rigid_loss"],
                        cum_loss_on=on["cum_rigid_loss"],
                        max_net_excess_on=on["max_net_excess"],
                        e_modal_peak_off=off["e_modal_peak"],
                        e_imp_peak_off=off["e_imp_peak"],
                        n_clamped_on=on["n_clamped"], n_steps_on=on["n_steps"],
                        finite_off=off["finite"], finite_on=on["finite"],
                        wall_off_s=off["wall_s"], wall_on_s=on["wall_s"]))
                    r_on = on["ratio"]
                    print(f"  {solver:7s} {scene:7s} relax={relax} {it:2d}x{su}: "
                          f"OFF={off['ratio']:12.4g} -> ON="
                          f"{(f'{r_on:9.4g}' if r_on is not None else '     skip')}"
                          f"  holds(OFF)={off['holds']} holds(ON)={on['holds']}"
                          f"  clamp={on['n_clamped']}/{on['n_steps']}"
                          f"  [{off['wall_s']:.1f}s]", flush=True)

    keys = list(rows[0].keys())
    csv_path = os.path.join(OUT, f"{args.out}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write_manifest(
        OUT, f"{args.out}.csv", scenes=scenes, solvers=solvers,
        note=("E-S1: 3 solvers x scene x relax x budget, clamp OFF vs ON. "
              "ratio = peak modal energy / peak impactor KE (diagnostic); "
              "holds() = enforced cumulative ledger invariant. ON forces the "
              "ACTIVE gamma-projection on all backends (avbd default is "
              "monitor-only). relax is INERT on the impulse backend "
              "(solver_impulse.py:290-292)."))

    # ---- summary ----------------------------------------------------------
    print("\n--- per-solver summary (OFF = un-governed) ---")
    for solver in solvers:
        sr = [r for r in rows if r["solver"] == solver]
        n_inj = sum(1 for r in sr if r["injects_off"])
        worst = max((r["ratio_off"] for r in sr), default=float("nan"))
        on_rows = [r for r in sr if r["holds_on"] is not None]
        n_holds_on = sum(1 for r in on_rows if r["holds_on"])
        worst_on = max((r["ratio_on"] for r in on_rows
                        if r["ratio_on"] is not None), default=float("nan"))
        # The OFF-run ledger verdict is only meaningful where the ledger
        # accounting actually ran. On xpbd/avbd with enforcement off the ledger
        # is absent or never updated (cum_rigid_loss stays 0), so holds() is
        # vacuously True / None -- reporting it as evidence would be a lie.
        # Only the impulse backend keeps the accounting live as a monitor.
        live = [r for r in sr if r["cum_loss_off"]]
        off_verdict = (
            f"OFF ledger holds in "
            f"{sum(1 for r in live if r['holds_off'])}/{len(live)} (accounting live)"
            if live else
            "OFF ledger verdict UNAVAILABLE (accounting inactive when clamp off)")
        print(f"  {solver:7s}: OFF {n_inj}/{len(sr)} cells inject "
              f"(worst ratio {worst:.4g}); {off_verdict}; ON holds in "
              f"{n_holds_on}/{len(on_rows)} (worst ratio {worst_on:.4g})")
        # relax-inertness check for the impulse backend
        if solver == "impulse" and len(relaxes) > 1:
            bad = []
            for scene in scenes:
                for (it, su) in budgets:
                    vals = [r["ratio_off"] for r in sr
                            if r["scene"] == scene and r["iters"] == it
                            and r["substeps"] == su]
                    if len(vals) > 1 and len(set(vals)) > 1:
                        bad.append((scene, it, su, vals))
            print(f"    relax-inertness check: "
                  f"{'IDENTICAL across relax in every cell (as predicted)' if not bad else f'DIFFERS in {len(bad)} cells: {bad}'}")
    print(f"\nwrote {csv_path}")


if __name__ == "__main__":
    main()
