#!/usr/bin/env python3
"""E4 — read-only momentum probe (paper Table 2 'Momentum drift' row).

Two probes, no solver code touched (sheldon-report pattern):

Probe A (conservation null + budget sweep). Two cargo cubes collide in free
flight: gravity zeroed, the REGISTERED box-box pair (mid, upper) teleported
1 m above the slab, one given a lateral velocity (small z offset -> oblique
hit). Pair-only P = sum m v and L = sum [x x m v + I_w w] are read straight
from the solver arrays. Finding this probe exists to pin down: at truncated
budgets the HOST solver's block-GS applies the contact row asymmetrically
within a sweep and pair momentum is NOT conserved on a fast impact
(+47% at 12x4, 1.5 m/s), converging away with budget (+0.2% at 12x16) --
and the error is IDENTICAL with the modal network on or off / rigid cubes,
i.e. the modal coupling adds no momentum error beyond the host's own
truncation error. Free flight conserves exactly; the paper's
"third law built into the row" claim must be scoped to the converged row.

Probe B (clamp/momentum interaction). The X1 shelf drop, XPBD at the
injecting 8x2 budget, clamp OFF vs ON (eta=1). Both runs are deterministic,
so every frame before the first clamp activation must be identical; after
it, the runs may diverge only through the support geometry subsequent
contacts see (the gamma projection touches modal state (q, qdot) only,
never rigid v/omega). Metric: ||dP(t)||, ||dL(t)|| between arms, the frame
of first divergence vs the frame of first activation.

Out: benchmark/runs/momentum/{probeA_pair.csv, probeB_clamp.csv,
summary.json} + console summary.

Run: .venv/bin/python benchmarks/momentum/probe_momentum.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_cargo_network import build_cargo_network_scene
from scenes.reduced_shelf import build_reduced_shelf

OUT_DIR = os.path.join(_ROOT, "benchmark", "runs", "momentum")
H_STEP = 1.0 / 120.0


# ---------------------------------------------------------------------------
# momentum from the DCR-side body mirrors (uniform across both solvers)
# ---------------------------------------------------------------------------
def momentum(bodies) -> tuple[np.ndarray, np.ndarray]:
    """(P, L) with P = sum m v and L about the world origin =
    sum [x x (m v) + I_world w] over the given RigidBody mirrors."""
    P = np.zeros(3)
    L = np.zeros(3)
    for b in bodies:
        if b.is_static:
            continue
        v = np.asarray(b.velocity[0:3], dtype=np.float64)
        w = np.asarray(b.velocity[3:6], dtype=np.float64)
        x = np.asarray(b.position, dtype=np.float64)
        P += b.mass * v
        L += np.cross(x, b.mass * v) + b.inertia_world() @ w
    return P, L


def _rel_drift(series: np.ndarray, ref: np.ndarray, floor: float) -> float:
    """max_t ||s(t) - ref|| / max(||ref||, floor)."""
    d = np.linalg.norm(series - ref[None, :], axis=1)
    return float(d.max() / max(np.linalg.norm(ref), floor))


# ---------------------------------------------------------------------------
# Probe A — free-flight pair collision: pair momentum vs solver budget
# ---------------------------------------------------------------------------
def _pair_momentum_solver(s, ids) -> tuple[np.ndarray, np.ndarray]:
    """(P, L) for the given AVBD body indices, read straight from the solver
    arrays (avoids the desc-vs-avbd index mismatch of the body mirrors)."""
    from dcr.avbd._solver.passivity import (local_inertia_from_invIl,
                                            _quat_to_R_batch)
    V = s.v.numpy(); W = s.omega.numpy(); X = s.x.numpy()
    Q = s.q.numpy()[:, [3, 0, 1, 2]]          # warp xyzw -> project wxyz
    m = np.asarray(s._mass, dtype=np.float64)
    Il = local_inertia_from_invIl(np.stack(s._inv_I_local))
    P = np.zeros(3); L = np.zeros(3)
    for i in ids:
        R = _quat_to_R_batch(Q[i:i + 1])[0]
        P += m[i] * V[i]
        L += np.cross(X[i], m[i] * V[i]) + R @ (Il[i] @ (R.T @ W[i]))
    return P, L


def _probe_a_cell(iters: int, subs: int, network: bool, kind: str,
                  n_steps: int = 30, v_impact: float = 1.5) -> dict:
    Hd = build_cargo_network_scene(network=network, kind=kind, device="cpu",
                                   solver="avbd", iterations=iters,
                                   substeps=subs)
    w = Hd.world
    s = w._solver
    w.step()                             # materialize the solver state arrays
    s.gravity = (0.0, 0.0, 0.0)          # read per launch; free flight

    # Use the REGISTERED box-box pair (mid, upper): their two-way modal
    # contact row exists for stacked cargo; arbitrary cube pairs carry none.
    ia, ib = Hd.avbd_idx["mid"], Hd.avbd_idx["upper"]
    X = s.x.numpy(); V = s.v.numpy(); W = s.omega.numpy()
    X[ia] = (-0.10, 1.0, 0.0)            # 1 m above the slab: pair-only contact
    X[ib] = (0.12, 1.0, 0.015)           # z offset -> oblique hit, L exchange
    V[ia] = (v_impact, 0.0, 0.0)
    V[ib] = 0.0
    W[ia] = 0.0
    W[ib] = 0.0
    s.x.assign(X); s.v.assign(V); s.omega.assign(W)

    series = []
    for _ in range(n_steps):
        w.step()
        P, L = _pair_momentum_solver(s, [ia, ib])
        series.append((*P, *L))
    arr = np.array(series)
    P0, Pend = arr[0, 0:3], arr[-1, 0:3]
    # pre-collision frames must conserve exactly (free flight)
    pre = arr[:6, 0:3]
    free_flight_drift = float(np.linalg.norm(pre - P0[None, :], axis=1).max())
    return dict(
        iters=iters, subs=subs, network=network, kind=kind,
        Px0=float(P0[0]), Px_end=float(Pend[0]),
        creation_pct=float((Pend[0] - P0[0]) / P0[0] * 100.0),
        free_flight_drift=free_flight_drift,
    )


def probe_a() -> dict:
    cells = [
        # budget sweep, rigid cubes (isolates the HOST solver's behaviour)
        _probe_a_cell(12, 4, False, "rigid"),
        _probe_a_cell(32, 4, False, "rigid"),
        _probe_a_cell(64, 4, False, "rigid"),
        _probe_a_cell(12, 16, False, "rigid"),
        # modal arms at the shipped budget: identical creation => the modal
        # coupling adds no momentum error beyond the host's own
        _probe_a_cell(12, 4, True, "fem_rigid"),
        _probe_a_cell(12, 4, False, "fem_rigid"),
    ]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "probeA_budget_sweep.csv"), "w") as f:
        f.write("iters,substeps,network,kind,Px0,Px_end,creation_pct,"
                "free_flight_drift\n")
        for c in cells:
            f.write(f"{c['iters']},{c['subs']},{c['network']},{c['kind']},"
                    f"{c['Px0']:.17g},{c['Px_end']:.17g},"
                    f"{c['creation_pct']:.6g},{c['free_flight_drift']:.3e}\n")
    return dict(cells=cells)


# ---------------------------------------------------------------------------
# Probe B — clamp ON vs OFF momentum divergence (XPBD 8x2, shelf)
# ---------------------------------------------------------------------------
def _run_shelf(enforce: bool, nframes: int = 120):
    Hd = build_reduced_shelf(device="cpu", iterations=8, avbd_substeps=2,
                             solver="xpbd")
    s = Hd.world._solver
    s.modal_relax = 0.7
    s._support_block_relax = 0.7
    s._modal_symplectic = True
    s._enforce_modal_passivity = bool(enforce)
    w = Hd.world
    bodies = [w._descs[i].dcr_body for i in Hd.probe_indices]
    P = np.zeros((nframes, 3)); L = np.zeros((nframes, 3))
    clamped = np.zeros(nframes, dtype=int)
    for k in range(nframes):
        w.step()
        P[k], L[k] = momentum(bodies)
        led = getattr(s, "_psv_ledger", None)
        clamped[k] = led.n_clamped if (enforce and led is not None) else 0
    return P, L, clamped


def probe_b(nframes: int = 120) -> dict:
    P_off, L_off, _ = _run_shelf(False, nframes)
    P_on, L_on, clamped = _run_shelf(True, nframes)
    dP = np.linalg.norm(P_on - P_off, axis=1)
    dL = np.linalg.norm(L_on - L_off, axis=1)
    first_clamp = int(np.argmax(clamped > 0)) if (clamped > 0).any() else -1
    div = np.where((dP > 0.0) | (dL > 0.0))[0]
    first_div = int(div[0]) if div.size else -1
    res = dict(
        n_frames=int(nframes),
        n_clamp_activations=int(clamped[-1]),
        first_clamp_frame=first_clamp,
        first_divergence_frame=first_div,
        identical_before_first_clamp=bool(first_div == -1
                                          or (0 <= first_clamp <= first_div)),
        max_dP_after=float(dP.max()),
        max_dL_after=float(dL.max()),
        P_scale=float(np.abs(P_off).max()),
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "probeB_clamp.csv"), "w") as f:
        f.write("frame,dP,dL,n_clamped_cum,"
                "Px_off,Py_off,Pz_off,Px_on,Py_on,Pz_on\n")
        for k in range(nframes):
            f.write(f"{k},{dP[k]:.17g},{dL[k]:.17g},{clamped[k]},"
                    + ",".join(f"{v:.17g}" for v in P_off[k])
                    + "," + ",".join(f"{v:.17g}" for v in P_on[k]) + "\n")
    return res


def main() -> int:
    out = {}
    print("== Probe A: pair momentum vs solver budget (box-box impact) ==")
    a = probe_a()
    out["probeA"] = a
    for c in a["cells"]:
        print(f"  {c['iters']:3d}x{c['subs']:<2d} network={c['network']!s:5s} "
              f"kind={c['kind']:9s} creation={c['creation_pct']:+.1f}%  "
              f"free-flight drift={c['free_flight_drift']:.1e}")

    print("== Probe B: clamp OFF vs ON (xpbd 8x2 shelf) ==")
    b = probe_b()
    out["probeB"] = b
    print(f"  activations={b['n_clamp_activations']}  "
          f"first clamp frame={b['first_clamp_frame']}  "
          f"first divergence frame={b['first_divergence_frame']}  "
          f"identical before first clamp={b['identical_before_first_clamp']}")
    print(f"  max |dP| after={b['max_dP_after']:.3e}  "
          f"(P scale {b['P_scale']:.3e})  max |dL| after={b['max_dL_after']:.3e}")

    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {OUT_DIR}/"
          "{probeA_budget_sweep.csv,probeB_clamp.csv,summary.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
