#!/usr/bin/env python3
"""E-S1 — velocity-impulse backend on the X1 24-cell configuration.

This is a measurement-only port of the benchmark branch's
``run_robustness_clamp.py`` configuration.  It preserves the three scenes, four
iteration/substep budgets, two legacy relaxation-axis values, eight warm-up
frames, and the reported metric:

    peak total modal mechanical energy / peak incident-impactor rigid KE.

``SolverImpulse`` uses the implicit modal weight ``(M+hD+h²K)^-1`` at full
weight and does not consume the XPBD/AVBD relaxation axis.  We nevertheless run
fresh independent simulations for both axis values so the output has the same
24 cells as X1; the duplicated axis is marked explicitly in the CSV/manifest.

Every ungoverned cell records both cumulative ledger verdicts.  A cell is rerun
with the foundation-§15 full-state gamma projection when the energy ratio is
greater than one, either ledger verdict fails, or the state becomes non-finite.
The governing rerun is stored in the same row.

Outputs:
  benchmarks/paper_eval/x1_passivity/out/impulse_robustness.csv
  benchmarks/paper_eval/x1_passivity/out/impulse_robustness.config.json

Run:
  .venv/bin/python benchmarks/paper_eval/x1_passivity/run_impulse_robustness.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections.abc import Callable

import numpy as np


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from benchmarks.paper_eval.paper_config import write_manifest
from dcr.avbd._solver.passivity import rigid_mechanical_energy
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
SCENES: dict[str, Callable] = {
    "shelf": build_reduced_shelf,
    "ledge": build_reduced_ledge,
    "dinner": build_reduced_dinner_table,
}
SCENE_ORDER = ("shelf", "ledge", "dinner")
BUDGETS = ((4, 1), (8, 2), (16, 4), (32, 8))
LEGACY_RELAX_AXIS = (0.7, 1.0)
WARMUP_FRAMES = 8
FULL_FRAMES = 100


def _one(build_fn: Callable, iterations: int, substeps: int, *,
         enforce: bool, nframes: int) -> dict[str, object]:
    """Measure one deterministic cell; solver state is never modified beyond
    enabling the already-implemented foundation-§15 monitor/projection."""
    handle = build_fn(device="cpu", iterations=iterations,
                      avbd_substeps=substeps, solver="impulse")
    solver = handle.world._solver
    if solver.__class__.__name__ != "SolverImpulse":
        raise RuntimeError(f"expected SolverImpulse, got {type(solver)!r}")
    if not np.isclose(float(solver.modal_relax), 1.0):
        raise RuntimeError("impulse backend must retain its full implicit weight")

    solver._enforce_modal_passivity = bool(enforce)
    solver._psv_monitor_only = False
    solver._modal_eta = 1.0
    if solver._psv_ledger is not None:
        solver._psv_ledger.eta = 1.0

    world = handle.world
    impactor_bi = int(world._descs[handle.impactor_idx].avbd_body.index)
    for _ in range(WARMUP_FRAMES):
        world.step()

    incident_ke = 0.0
    peak_modal = 0.0
    finite = True
    for _ in range(nframes):
        world.step()
        # Native-thin worlds intentionally skip the legacy AVBD→DCR body mirror.
        # Read the impactor's authoritative solver state directly; with X/gravity
        # omitted, rigid_mechanical_energy is exactly rigid kinetic energy.
        sl = slice(impactor_bi, impactor_bi + 1)
        impactor_ke = rigid_mechanical_energy(
            solver._V[sl], solver._W[sl],
            solver._Q[sl][:, [3, 0, 1, 2]],
            solver._mass[sl], solver._invIl[sl])
        incident_ke = max(incident_ke, impactor_ke)
        modal_energy = float(solver._modal_energy_total())
        if not np.isfinite(modal_energy):
            finite = False
            peak_modal = float("inf")
            break
        peak_modal = max(peak_modal, modal_energy)

    ledger = solver._psv_ledger
    if ledger is None:
        raise RuntimeError("impulse passivity ledger was not constructed")
    ratio = (peak_modal / max(incident_ke, 1.0e-9)
             if finite else float("inf"))
    return {
        "peak_modal_J": peak_modal,
        "incident_rigid_ke_J": incident_ke,
        "injection_ratio": ratio,
        "ledger_passive": bool(ledger.passive()),
        "ledger_holds": bool(ledger.holds()),
        "max_net_excess_J": float(ledger.max_net_excess),
        "max_deposit_J": float(ledger.max_deposit),
        "cum_modal_gain_J": float(ledger.cum_modal_gain),
        "cum_rigid_loss_J": float(ledger.cum_rigid_loss),
        "n_clamped": int(ledger.n_clamped),
        "n_ledger_steps": int(ledger.n_steps),
        "finite": finite,
    }


def _needs_governed_rerun(result: dict[str, object]) -> bool:
    return (not bool(result["finite"])
            or float(result["injection_ratio"]) > 1.0
            or not bool(result["ledger_passive"])
            or not bool(result["ledger_holds"]))


def _flatten(prefix: str, result: dict[str, object] | None) -> dict[str, object]:
    keys = (
        "peak_modal_J", "incident_rigid_ke_J", "injection_ratio",
        "ledger_passive", "ledger_holds", "max_net_excess_J",
        "max_deposit_J", "cum_modal_gain_J", "cum_rigid_loss_J",
        "n_clamped", "n_ledger_steps", "finite",
    )
    return {f"{prefix}_{key}": ("" if result is None else result[key])
            for key in keys}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick", action="store_true",
        help="70 frames/cell; writes impulse_robustness_quick.* for smoke testing")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    nframes = 70 if args.quick else FULL_FRAMES
    stem = "impulse_robustness_quick" if args.quick else "impulse_robustness"

    rows: list[dict[str, object]] = []
    print("### E-S1 impulse backend: X1 24-cell configuration ###", flush=True)
    for scene in SCENE_ORDER:
        build_fn = SCENES[scene]
        for relax_axis in LEGACY_RELAX_AXIS:
            for iterations, substeps in BUDGETS:
                raw = _one(build_fn, iterations, substeps,
                           enforce=False, nframes=nframes)
                needs_governor = _needs_governed_rerun(raw)
                governed = (_one(build_fn, iterations, substeps,
                                 enforce=True, nframes=nframes)
                            if needs_governor else None)
                row = {
                    "scene": scene,
                    "legacy_relax_axis": relax_axis,
                    "relax_consumed_by_impulse": False,
                    "iterations": iterations,
                    "substeps": substeps,
                    "warmup_frames": WARMUP_FRAMES,
                    "measured_frames": nframes,
                    "governed_rerun": needs_governor,
                    **_flatten("raw", raw),
                    **_flatten("governed", governed),
                }
                rows.append(row)
                suffix = ""
                if governed is not None:
                    suffix = (f" -> governed {governed['injection_ratio']:.6g}, "
                              f"ledger={governed['ledger_passive']}/"
                              f"{governed['ledger_holds']}, "
                              f"clamp={governed['n_clamped']}")
                print(
                    f"  {scene:7s} axis={relax_axis:.1f} "
                    f"{iterations:2d}x{substeps}: "
                    f"ratio={raw['injection_ratio']:.6g}, "
                    f"ledger={raw['ledger_passive']}/{raw['ledger_holds']}"
                    f"{suffix}", flush=True)

    if len(rows) != 24:
        raise AssertionError(f"expected 24 cells, got {len(rows)}")

    csv_name = stem + ".csv"
    csv_path = os.path.join(OUT, csv_name)
    with open(csv_path, "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    write_manifest(
        OUT, csv_name, scenes=SCENE_ORDER, solvers=["impulse"],
        stage="E-S1",
        matrix_config={
            "budgets": [list(x) for x in BUDGETS],
            "legacy_relax_axis": list(LEGACY_RELAX_AXIS),
            "relax_consumed_by_impulse": False,
            "warmup_frames": WARMUP_FRAMES,
            "measured_frames": nframes,
            "metric": "peak total modal energy / peak incident impactor rigid KE",
            "governed_rerun_trigger": (
                "ratio>1 or cumulative ledger verdict failure or non-finite"),
        },
        note=("Measurement-only port of benchmark-branch X1 configuration; "
              "no solver behavior changes."),
    )

    n_ratio = sum(float(r["raw_injection_ratio"]) > 1.0 for r in rows)
    n_ledger = sum((not bool(r["raw_ledger_passive"]))
                   or (not bool(r["raw_ledger_holds"])) for r in rows)
    n_governed = sum(bool(r["governed_rerun"]) for r in rows)
    print(
        f"\nraw ratio>1: {n_ratio}/24; raw ledger failure: {n_ledger}/24; "
        f"governed reruns: {n_governed}/24", flush=True)
    print(f"wrote {csv_path}", flush=True)


if __name__ == "__main__":
    main()
