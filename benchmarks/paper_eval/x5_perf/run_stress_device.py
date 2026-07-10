#!/usr/bin/env python3
"""Scale stress test on the CUDA device path — reviewer gap "scenes top out
at 25 bodies".

Same measurement protocol as `run_perf_device.py` (Table 7 of the paper):
device-resident native co-solved (z,q) AVBD, warp modal solve + full-substep
CUDA-graph capture, relax 0.7, h=1/120, `wp.synchronize_device` brackets
every timed step, 10 warm-up steps, 200 timed frames. The only new axis is
N: the stress scene (`scenes/reduced_stress.py`) puts N resting crates + 1
heavy center impactor on one fixed-basis modal slab, so the sweep isolates
body / support-contact-row count from modal-block size (28 modes at all N).

Passivity on this path is measured the same way as the paper's 20/20 device
cells (`probe_device_passivity.py`): the in-solver clamp is gated on
`_modal_symplectic` and does NOT execute on the co-solved path, so a
separate pass runs the read-only external §15 ledger over the trajectory
(deposit rigid loss, commit realized modal gain, check the net invariant).
Timing runs and ledger runs are separate so per-step host readbacks never
pollute ms/step.

Three products:
(1) stress_device.csv       -- N x budget timing grid (ms/step, 120 Hz
                               envelope, post-run eject sanity).
(2) stress_device_arms.csv  -- N sweep @ paper budget, baseline (modal ring
                               frozen) vs coupling: two-way overhead vs N.
(3) stress_device_psv.csv   -- N x budget read-only passivity ledger.

Run: ~/dcr-venv/bin/python benchmarks/paper_eval/x5_perf/run_stress_device.py \
        --frames 200 --device cuda:0 [--bodies 16,32,64,128,256,512]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import warp as wp

from scenes.reduced_stress import build_reduced_stress
from dcr.avbd._solver.passivity import (
    rigid_mechanical_energy, modal_mech_energy, PassivityLedger)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

RELAX = 0.7
HZ = 120.0
RT_MS = 1000.0 / HZ


def _build(n_bodies, iters, subs, device, arm):
    H = build_reduced_stress(n_bodies=int(n_bodies), device=device,
                             iterations=int(iters), avbd_substeps=int(subs),
                             solver="avbd", cargo_material=None)
    sol = H.world._solver
    sol._modal_relax = float(RELAX)
    if hasattr(sol, "_modal_symplectic"):
        sol._modal_symplectic = False      # device path = co-solved constraint
    if arm == "baseline" and hasattr(sol, "_modal_freeze_qdot"):
        sol._modal_freeze_qdot = True
    return H


def _time_run(*, n_bodies, device, frames, iters, subs, arm):
    H = _build(n_bodies, iters, subs, device, arm)
    sol = H.world._solver
    w = H.world
    dev = wp.get_device(device) if str(device).startswith("cuda") else None

    def _sync():
        if dev is not None:
            wp.synchronize_device(dev)

    for _ in range(10):                    # warm up: JIT, kernel cache, capture
        w.step()
    _sync()
    per = np.empty(frames)
    for i in range(frames):
        _sync()
        t0 = time.perf_counter()
        w.step()
        _sync()
        per[i] = (time.perf_counter() - t0) * 1e3

    nb = len(sol._mass) if hasattr(sol, "_mass") else 0
    r = getattr(sol, "_r", 0) or getattr(sol, "_n_modes", 0)
    graph = getattr(sol, "_substep_graph", None)
    # post-run sanity: nothing ejected (a stress test that exploded is not a
    # timing result)
    pos = np.asarray(sol.positions(), dtype=np.float64)
    max_xy = float(np.abs(pos[:, [0, 2]]).max())
    min_y = float(pos[:, 1].min())
    return dict(mean_ms=float(per.mean()), p50_ms=float(np.median(per)),
                worst_ms=float(per.max()), std_ms=float(per.std()),
                nb=nb, modes=int(r), captured=bool(graph is not None),
                max_xy=max_xy, min_y=min_y)


# ---- read-only §15 ledger over the co-solved trajectory (probe_device_ --- #
# ---- passivity.py's measurement, verbatim) ------------------------------- #

def _rigid_ke(sol):
    V = sol.v.numpy(); Wo = sol.omega.numpy(); Qq = sol._psv_quats_wxyz()
    return rigid_mechanical_energy(V, Wo, Qq, sol._mass, sol._inv_I_local,
                                   Il=sol._psv_local_inertia())


def _modal_e(sol):
    if hasattr(sol, "_sync_modal_host_mirrors"):
        sol._sync_modal_host_mirrors()
    ke, pe = modal_mech_energy(sol._qdot_modal_host, sol._q_modal_host,
                               sol._Mq, sol._Kq)
    return ke + pe


def _psv_probe(*, n_bodies, device, iters, subs, steps, eta=1.0):
    H = _build(n_bodies, iters, subs, device, arm="coupling")
    sol = H.world._solver
    w = H.world
    grav = np.asarray(sol.gravity, dtype=np.float64)
    mass = np.asarray(sol._mass, dtype=np.float64)

    led = PassivityLedger(eta=float(eta))
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
        grav_work = float((mass * ((x - x_prev) @ grav)).sum())
        rigid_loss = (e_rig_prev - e_rig) + grav_work
        realized_gain = e_mod - e_mod_prev
        budget = led.deposit(rigid_loss)
        led.commit(realized_gain, budget, alpha=1.0, e_modal_now=e_mod)
        peak_modal = max(peak_modal, e_mod)
        e_rig_prev, e_mod_prev, x_prev = e_rig, e_mod, x.copy()

    return dict(holds=bool(led.holds()), passive=bool(led.passive()),
                cum_modal_gain=float(led.cum_modal_gain),
                eta_cum_loss=float(led.eta * led.cum_rigid_loss),
                max_net_excess=float(led.max_net_excess),
                max_deposit=float(led.max_deposit),
                peak_modal=float(peak_modal), e_modal_0=float(led.e_modal_0),
                n_steps=int(led.n_steps))


def _gpu_name():
    try:
        return subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            stderr=subprocess.DEVNULL).decode().strip().splitlines()[0]
    except Exception:
        return "unknown"


def _write_csv(name, keys, rows):
    with open(os.path.join(OUT, name), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (f"{r[k]:.5g}" if isinstance(r[k], float) else r[k])
                         for k in keys})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--bodies", default="16,32,64,128,256,512")
    ap.add_argument("--budgets", default="8x1,16x2,16x4")
    ap.add_argument("--fixed", default="16x4", help="paper budget for the arms rows")
    ap.add_argument("--psv-steps", type=int, default=240,
                    help="rigid steps for the read-only passivity ledger pass")
    ap.add_argument("--skip-psv", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    body_counts = [int(x) for x in args.bodies.split(",") if x.strip()]
    budgets = [b.strip() for b in args.budgets.split(",") if b.strip()]
    f_it, f_su = (int(x) for x in args.fixed.split("x"))

    wp.init()
    gpu = _gpu_name()
    print(f"### stress N-sweep on {args.device} ({gpu}) warp {wp.__version__}, "
          f"{args.frames} frames ###", flush=True)

    # ---- (1) N x budget timing grid ---------------------------------------- #
    rows = []
    for n in body_counts:
        for b in budgets:
            it, su = (int(x) for x in b.split("x"))
            r = _time_run(n_bodies=n, device=args.device, frames=args.frames,
                          iters=it, subs=su, arm="coupling")
            row = dict(n_bodies=n, budget=b, iters=it, substeps=su,
                       nb=r["nb"], modes=r["modes"], mean_ms=r["mean_ms"],
                       p50_ms=r["p50_ms"], worst_ms=r["worst_ms"],
                       std_ms=r["std_ms"],
                       steps_per_s=1000.0 / max(r["mean_ms"], 1e-9),
                       rt_factor_120hz=RT_MS / max(r["mean_ms"], 1e-9),
                       realtime_120hz=bool(r["mean_ms"] <= RT_MS),
                       captured=r["captured"], max_xy=r["max_xy"],
                       min_y=r["min_y"])
            rows.append(row)
            rt = "RT" if row["realtime_120hz"] else "  "
            print(f"  N={n:4d} {b:5s}: {r['mean_ms']:7.2f} ms  "
                  f"{row['steps_per_s']:7.1f} st/s {row['rt_factor_120hz']:5.2f}x "
                  f"[{rt}] cap={r['captured']} max_xy={r['max_xy']:.2f} "
                  f"min_y={r['min_y']:.3f}", flush=True)
    _write_csv("stress_device.csv",
               ["n_bodies", "budget", "iters", "substeps", "nb", "modes",
                "mean_ms", "p50_ms", "worst_ms", "std_ms", "steps_per_s",
                "rt_factor_120hz", "realtime_120hz", "captured", "max_xy",
                "min_y"], rows)

    # ---- (2) baseline vs coupling at the paper budget ----------------------- #
    print(f"\n-- stress_device_arms.csv: modal overhead @ {args.fixed} --", flush=True)
    arows = []
    for n in body_counts:
        base = _time_run(n_bodies=n, device=args.device, frames=args.frames,
                         iters=f_it, subs=f_su, arm="baseline")
        coup = _time_run(n_bodies=n, device=args.device, frames=args.frames,
                         iters=f_it, subs=f_su, arm="coupling")
        row = dict(n_bodies=n, budget=args.fixed, nb=coup["nb"],
                   modes=coup["modes"], baseline_ms=base["mean_ms"],
                   coupling_ms=coup["mean_ms"],
                   modal_overhead_ms=coup["mean_ms"] - base["mean_ms"],
                   steps_per_s=1000.0 / max(coup["mean_ms"], 1e-9))
        arows.append(row)
        print(f"  N={n:4d}: base={base['mean_ms']:7.2f} coup={coup['mean_ms']:7.2f} ms  "
              f"modal+={row['modal_overhead_ms']:5.2f}", flush=True)
    _write_csv("stress_device_arms.csv",
               ["n_bodies", "budget", "nb", "modes", "baseline_ms",
                "coupling_ms", "modal_overhead_ms", "steps_per_s"], arows)

    # ---- (3) read-only passivity ledger per cell ---------------------------- #
    prows = []
    if not args.skip_psv:
        print(f"\n-- stress_device_psv.csv: external §15 ledger, "
              f"{args.psv_steps} steps --", flush=True)
        for n in body_counts:
            for b in budgets:
                it, su = (int(x) for x in b.split("x"))
                r = _psv_probe(n_bodies=n, device=args.device, iters=it,
                               subs=su, steps=args.psv_steps)
                r.update(n_bodies=n, budget=b, iters=it, substeps=su)
                prows.append(r)
                print(f"  N={n:4d} {b:5s}: holds={r['holds']} passive={r['passive']}  "
                      f"Σgain={r['cum_modal_gain']:.4g}  η·Σloss={r['eta_cum_loss']:.4g}  "
                      f"net_excess={r['max_net_excess']:.3g}", flush=True)
        _write_csv("stress_device_psv.csv",
                   ["n_bodies", "budget", "iters", "substeps", "holds",
                    "passive", "cum_modal_gain", "eta_cum_loss",
                    "max_net_excess", "max_deposit", "peak_modal", "e_modal_0",
                    "n_steps"], prows)

    m = dict(figure="stress_device.csv", stage="stress-scale",
             generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
             device=args.device, gpu=gpu, warp=wp.__version__,
             numpy=np.__version__, python=platform.python_version(),
             relax=RELAX, frames=args.frames, psv_steps=args.psv_steps,
             bodies=body_counts, budgets=budgets, fixed=args.fixed,
             note="N-body stress grid, fixed 28-mode slab basis; device-resident "
                  "native co-solved (z,q) AVBD; passivity via read-only external "
                  "ledger (in-solver clamp is symplectic-host-only)")
    with open(os.path.join(OUT, "stress_device.config.json"), "w") as fh:
        json.dump(m, fh, indent=2)

    n_pass = sum(1 for r in prows if r["passive"]) if prows else "n/a"
    print(f"\npassive {n_pass}/{len(prows) if prows else 'skipped'} cells. "
          f"wrote out/stress_device.csv + _arms.csv + _psv.csv")


if __name__ == "__main__":
    main()
