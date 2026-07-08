#!/usr/bin/env python3
"""E-G3a — is the real-time co-solved DEVICE path passive WITHOUT an active clamp?

The support-path passivity clamp (`_modal_predict`/`_modal_commit`, foundation §15)
is gated on `self._modal_symplectic` -- it runs only on the CPU-host symplectic
modal step. The device-resident co-solved (z,q) path sets `_modal_symplectic=False`,
so the clamp does NOT execute there (run_perf_device's "clamp arm" is a no-op on
device). The honest G3 question is therefore whether the FAST path is passive by
construction (AVBD is a descent-class solver: empirically passive at PAPER_CONFIG).

This probe answers it with ZERO solver change: it reads the co-solved modal state
(`_q_modal_host`/`_qdot_modal_host`, mirrored back by `_modal_commit_device` each
step) and the rigid state per RIGID step, and runs the SAME PassivityLedger /
energy functions the clamp uses (deposit rigid loss, commit realized modal gain,
check the net invariant E_modal(t)-E_modal(0) <= η·Σloss(t)+granularity). Read-only,
so no `# DEVIATION:` -- it measures the shipped solver, it does not alter it.

Reports per (scene, budget): holds() (cumulative), passive() (net), max_net_excess,
cum modal gain vs η·cum loss, and n_steps. Sweeps budgets down to the real-time
region (8x1) -- the load-bearing test is whether passivity survives the LOW budget
where a stationarity-class (XPBD) solver would inject.

Run: ~/dcr-venv/bin/python benchmarks/paper_eval/x5_perf/probe_device_passivity.py \
        --device cuda:0 --scenes dinner,ledge --budgets 8x1,16x2,16x4,32x4 --steps 360
"""
from __future__ import annotations

import argparse
import csv
import inspect
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import warp as wp

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_truck import build_reduced_truck
from dcr.avbd._solver.passivity import (
    rigid_mechanical_energy, modal_mech_energy, PassivityLedger)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
RELAX = 0.7
SCENES = {"shelf": build_reduced_shelf, "ledge": build_reduced_ledge,
          "dinner": build_reduced_dinner_table, "truck": build_reduced_truck}


def _build(build_fn, iters, subs, device):
    rd = str(device).startswith("cuda")
    cand = dict(device=device, solver="avbd", device_resident=rd,
                cargo_material=None, iterations=int(iters), avbd_substeps=int(subs),
                support_basis="fem")
    params = inspect.signature(build_fn).parameters
    return build_fn(**{k: v for k, v in cand.items() if k in params})


def _rigid_ke(sol):
    V = sol.v.numpy(); Wo = sol.omega.numpy(); Qq = sol._psv_quats_wxyz()
    return rigid_mechanical_energy(V, Wo, Qq, sol._mass, sol._inv_I_local,
                                   Il=sol._psv_local_inertia())


def _modal_e(sol):
    # force the on-demand device->host mirror refresh (full-substep capture defers
    # it lazily via _modal_host_dirty; a bare attribute read would be stale/frozen)
    if hasattr(sol, "_sync_modal_host_mirrors"):
        sol._sync_modal_host_mirrors()
    ke, pe = modal_mech_energy(sol._qdot_modal_host, sol._q_modal_host,
                              sol._Mq, sol._Kq)
    return ke + pe


def probe(build_fn, *, device, iters, subs, steps, eta=1.0):
    H = _build(build_fn, iters, subs, device)
    sol = H.world._solver
    sol._modal_relax = float(RELAX)
    if hasattr(sol, "_modal_symplectic"):
        sol._modal_symplectic = False               # co-solved device path
    w = H.world
    grav = np.asarray(sol.gravity, dtype=np.float64)
    mass = np.asarray(sol._mass, dtype=np.float64)

    led = PassivityLedger(eta=float(eta))
    # e_modal_0 at rest = 0; capture the first post-step modal energy as baseline
    w.step()
    led.e_modal_0 = _modal_e(sol)
    e_mod_prev = led.e_modal_0
    e_rig_prev = _rigid_ke(sol)
    x_prev = sol.x.numpy().copy()
    peak_modal = e_mod_prev

    for _ in range(steps):
        w.step()
        e_rig = _rigid_ke(sol)
        x = sol.x.numpy()
        e_mod = _modal_e(sol)
        grav_work = float((mass * ((x - x_prev) @ grav)).sum())  # Σ_i m_i (g·Δx_i)
        rigid_loss = (e_rig_prev - e_rig) + grav_work
        realized_gain = e_mod - e_mod_prev
        budget = led.deposit(rigid_loss)
        led.commit(realized_gain, budget, alpha=1.0, e_modal_now=e_mod)
        peak_modal = max(peak_modal, e_mod)
        e_rig_prev, e_mod_prev, x_prev = e_rig, e_mod, x.copy()

    return dict(
        holds=bool(led.holds()), passive=bool(led.passive()),
        cum_modal_gain=float(led.cum_modal_gain),
        eta_cum_loss=float(led.eta * led.cum_rigid_loss),
        max_net_excess=float(led.max_net_excess),
        max_deposit=float(led.max_deposit),
        peak_modal=float(peak_modal), e_modal_0=float(led.e_modal_0),
        n_steps=int(led.n_steps))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--scenes", default="dinner,ledge")
    ap.add_argument("--budgets", default="8x1,16x2,16x4,32x4")
    ap.add_argument("--steps", type=int, default=360)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    wp.init()

    scenes = [s.strip() for s in args.scenes.split(",") if s.strip()]
    budgets = [b.strip() for b in args.budgets.split(",") if b.strip()]
    print(f"### E-G3a device passivity probe on {args.device}, {args.steps} steps ###",
          flush=True)
    rows = []
    for scene in scenes:
        for b in budgets:
            it, su = (int(x) for x in b.split("x"))
            r = probe(SCENES[scene], device=args.device, iters=it, subs=su,
                      steps=args.steps)
            r.update(scene=scene, budget=b, iters=it, substeps=su)
            rows.append(r)
            print(f"  {scene:7s} {b:5s}: holds={r['holds']} passive={r['passive']}  "
                  f"Σgain={r['cum_modal_gain']:.4g}  η·Σloss={r['eta_cum_loss']:.4g}  "
                  f"net_excess={r['max_net_excess']:.3g} (granularity {r['max_deposit']:.3g})  "
                  f"peak_Em={r['peak_modal']:.4g}", flush=True)

    keys = ["scene", "budget", "iters", "substeps", "holds", "passive",
            "cum_modal_gain", "eta_cum_loss", "max_net_excess", "max_deposit",
            "peak_modal", "e_modal_0", "n_steps"]
    with open(os.path.join(OUT, "device_passivity.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k])
                         for k in keys})
    with open(os.path.join(OUT, "device_passivity.config.json"), "w") as fh:
        json.dump(dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       device=args.device, warp=wp.__version__, numpy=np.__version__,
                       python=platform.python_version(), relax=RELAX, steps=args.steps,
                       scenes=scenes, budgets=budgets,
                       note="read-only external §15 ledger on the co-solved device path; "
                            "no active clamp; tests passivity-by-construction of AVBD"),
                  fh, indent=2)
    npass = sum(1 for r in rows if r["passive"])
    print(f"\n{npass}/{len(rows)} (scene,budget) cells passive on the device path "
          f"WITHOUT an active clamp. wrote out/device_passivity.csv")


if __name__ == "__main__":
    main()
