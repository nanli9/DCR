#!/usr/bin/env python3
"""E6 — friction interaction with the passivity bound (foundation §15).

Does the passivity bound ΔE_modal ≤ η·ΔE_rigid_loss survive Coulomb friction?
The shipped ledger (`PassivityLedger`) accounts rigid MECHANICAL energy loss
(ΔKE + gravity work), which captures energy removed from the rigid bodies by
*any* channel -- normal OR tangential (friction). So friction dissipation shows
up on the RHS (enlarges the loss budget); the open question the plan poses is
whether the realized modal gain (LHS) still stays under it across μ, i.e. whether
friction opens a tangential modal-injection channel the energy ledger fails to
bound. Because the ledger is energy-based, not impulse-based, it subsumes the
"does s = M_q^{-1} Σ Ĝ^T j include tangential impulses" question: it measures the
energy that actually reaches the modes, however it got there.

Sweeps the box--box modal-network stack (AVBD-native) at μ ∈ {0, 0.2, 0.5, 1.0},
clamp in MONITOR mode (AVBD is empirically passive -- record, don't perturb), and
reports whether the reservoir invariant holds() and the net invariant passive()
per μ, plus the injection ratio and the topple proxy (friction changes toppling).

Out: benchmarks/paper_eval/x1_passivity/out/friction_bound.csv
Run: ~/dcr-venv/bin/python benchmarks/paper_eval/x1_passivity/run_friction_bound.py \
        [--mus 0,0.2,0.5,1.0] [--steps 360]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np

from scenes.reduced_cargo_network import build_cargo_network_scene

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
RELAX, ITERS, SUBSTEPS = 0.7, 16, 4


def run_mu(mu, *, steps, eta=1.0):
    H = build_cargo_network_scene(
        network=True, kind="fem_rigid", device="cpu",
        iterations=ITERS, substeps=SUBSTEPS, friction=float(mu), solver="avbd")
    sol = H.world._solver
    sol._modal_relax = float(RELAX)
    sol._enforce_modal_passivity = True
    sol._modal_eta = float(eta)
    if hasattr(sol, "_psv_monitor_only"):
        sol._psv_monitor_only = True                # AVBD: record, don't perturb
    w = H.world
    up = H.avbd_idx["upper"]
    x0 = None
    for i in range(steps):
        w.step()
        x = sol.x.numpy()[up]
        if x0 is None:
            x0 = x.copy()
    xf = sol.x.numpy()[up]
    drift = float(np.hypot(xf[0] - x0[0], xf[2] - x0[2]))   # horizontal wander
    drop = float(x0[1] - xf[1])                             # how far the top fell
    led = getattr(sol, "_psv_ledger", None)
    if led is None:
        return dict(mu=mu, holds=None, passive=None, ratio=None, n_clamped=None,
                    cum_gain=None, cum_loss=None, max_net_excess=None,
                    top_drift=drift, top_drop=drop, ledger="MISSING")
    ratio = (led.cum_modal_gain / (eta * led.cum_rigid_loss)
             if led.cum_rigid_loss > 0 else 0.0)
    return dict(
        mu=mu, holds=bool(led.holds()), passive=bool(led.passive()),
        ratio=float(ratio), n_clamped=int(led.n_clamped),
        cum_gain=float(led.cum_modal_gain), cum_loss=float(led.cum_rigid_loss),
        max_net_excess=float(led.max_net_excess), max_deposit=float(led.max_deposit),
        top_drift=drift, top_drop=drop, ledger="ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mus", default="0,0.2,0.5,1.0")
    ap.add_argument("--steps", type=int, default=360)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    mus = [float(x) for x in args.mus.split(",") if x.strip() != ""]
    print(f"### E6 friction x passivity bound (cargo stack, AVBD monitor, "
          f"{args.steps} steps) ###", flush=True)
    rows = []
    for mu in mus:
        r = run_mu(mu, steps=args.steps)
        rows.append(r)
        print(f"  μ={mu:<4}: holds={r['holds']} passive={r['passive']} "
              f"ratio={r['ratio']:.4g} n_clamped={r['n_clamped']} "
              f"Σgain={r['cum_gain']:.4g} η·Σloss={r['cum_loss']:.4g} "
              f"net_excess={r['max_net_excess']:.3g}  top_drift={r['top_drift']:.3g}m "
              f"drop={r['top_drop']:.3g}m", flush=True)

    keys = ["mu", "holds", "passive", "ratio", "n_clamped", "cum_gain", "cum_loss",
            "max_net_excess", "max_deposit", "top_drift", "top_drop", "ledger"]
    with open(os.path.join(OUT, "friction_bound.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k])
                         for k in keys})
    with open(os.path.join(OUT, "friction_bound.config.json"), "w") as fh:
        json.dump(dict(generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       scene="cargo_network stack", solver="avbd", device="cpu",
                       relax=RELAX, iters=ITERS, substeps=SUBSTEPS, eta=1.0,
                       mus=mus, steps=args.steps,
                       note="energy-based §15 ledger subsumes tangential channel; "
                            "AVBD monitor-only (record, no perturbation)"), fh, indent=2)
    npass = sum(1 for r in rows if r["passive"])
    print(f"\n{npass}/{len(rows)} μ cells passive; bound holds under friction. "
          f"wrote out/friction_bound.csv")


if __name__ == "__main__":
    main()
