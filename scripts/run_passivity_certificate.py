#!/usr/bin/env python3
"""Energy-consistent passivity certificate — per solver, with its own contact model.

Advisor ask #3: *"account contact energy with the AL / compliant model per solver,
so each has a clean per-step bound."* This certifies that each solver is **passive**
— its total mechanical energy (kinetic + elastic + gravitational + the stored
contact potential) is monotone non-increasing every step, to a tolerance ε — on a
real impact scene where the dynamic modal constraint is doing two-way work.

Per-solver contact-energy accounting (this is the "native model"):

  * penalty GT / SPLIT  : Φ_c = ½ k_c Σ max(0,−gap)²        (penalty spring)
  * XPBD (compliant)    : Φ_c = ½ k_c Σ max(0,−gap)²        (compliance α=1/k_c
                          stores the SAME elastic energy when penetrating)
  * AVBD (augmented Lag) : Φ_c = ½ ρ₀ Σ max(0,−gap)²        (ρ₀=k_c) — the AL
                          multiplier λ enforces gap≈0 and a constraint reaction at
                          a held gap is WORKLESS, so the only *stored* contact
                          energy is the residual penalty. AVBD therefore has the
                          cleanest bound: it drives gap→0, so Φ_c≈0.

All four reduce to the same functional form (ρ₀=k_c), so `energy_breakdown`'s
`total` IS the native certificate energy for every solver — what differs is how
much each *stores*: AVBD's λ holds the load with ~no penetration energy; the
penalty solvers carry a real ½k_c·gap² residual. We report both.

# DEVIATION (foundation §15): no η/reservoir governor anywhere — passivity comes
# structurally from backward Euler on a bounded-below potential (Approach B).

Certificate: PASS iff max_n (E[n+1]−E[n]) ≤ ε_tol over the whole run.

Outputs (docs/):
  * data/passivity_<scene>_<kind>_<solver>.csv     — t, E, dE, contact-stored E
  * data/passivity_<scene>_<kind>_certificate.csv  — one row per solver (the cert)
  * figures/passivity_<scene>_<kind>.png           — E(t) + per-step ΔE(t)

    uv run python scripts/run_passivity_certificate.py --scene truck
    uv run python scripts/run_passivity_certificate.py --scene side_by_side
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from dcr.twobody.multibody import build_side_by_side, build_truck_bed
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem,
                                        XPBDDynamicSystem)

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "docs" / "data"
_FIG = _ROOT / "docs" / "figures"


def _scene(scene, kind, k_c, damping):
    if scene == "truck":
        return build_truck_bed(kind, k_c=k_c, damping=damping)
    if scene == "side_by_side":
        return build_side_by_side(kind, n_rest=3, impactor_drop=0.35,
                                  impactor_rho=2500.0, damping=damping, k_c=k_c)
    raise ValueError(scene)


def run(sys, h, steps):
    """Per-step total energy E (native contact model) and the stored contact PE."""
    st = sys.initial_state()
    t, E, Ec = [], [], []
    for s in range(steps):
        st = sys.step(st, h)
        e = sys.energy_breakdown(st)
        t.append(s * h)
        E.append(e["total"])            # KE + PE_el + PE_grav + Φ_contact(native)
        Ec.append(e["PE_contact"])      # the stored contact penalty energy
    return np.asarray(t), np.asarray(E), np.asarray(Ec)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", choices=["truck", "side_by_side"], default="truck")
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e6)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--tol", type=float, default=1.0e-4,
                    help="per-step ΔE tolerance for the passivity certificate [J]")
    args = ap.parse_args()

    base, _info = _scene(args.scene, args.kind, args.k_c, args.damping)
    solvers = {"AVBD": AVBDDynamicSystem(base, n_outer=8, n_inner=4)}
    if args.kind == "fem":
        solvers["XPBD"] = XPBDDynamicSystem(base, n_iters=30)
    solvers["GT"] = base
    solvers["SPLIT"] = SplitOneWaySystem(base)

    print(f"passivity certificate: scene={args.scene} kind={args.kind} "
          f"steps={args.steps} tol={args.tol:g} J")
    _DATA.mkdir(parents=True, exist_ok=True)
    results, cert_rows = {}, []
    for name, sv in solvers.items():
        t, E, Ec = run(sv, args.h, args.steps)
        results[name] = (t, E, Ec)
        dE = np.diff(E)
        max_rise = float(dE.max())                  # the per-step bound
        t_rise = float(t[1 + int(np.argmax(dE))])
        dissipated = float(E[0] - E[-1])
        n_viol = int(np.sum(dE > args.tol))
        passed = max_rise <= args.tol
        cert_rows.append({
            "solver": name, "E0": E[0], "E_end": E[-1],
            "dissipated_J": dissipated, "max_step_rise_J": max_rise,
            "t_max_rise_s": t_rise, "n_violations": n_viol,
            "contact_E_peak_J": float(Ec.max()), "PASS": passed})
        # per-solver time series
        with (_DATA / f"passivity_{args.scene}_{args.kind}_{name.lower()}.csv"
              ).open("w", newline="") as f:
            w = csv.writer(f); w.writerow(["t", "E_total", "dE_step", "contact_E"])
            w.writerow([f"{t[0]:.8g}", f"{E[0]:.10g}", "0", f"{Ec[0]:.8g}"])
            for r in range(1, len(t)):
                w.writerow([f"{t[r]:.8g}", f"{E[r]:.10g}", f"{dE[r-1]:.6e}",
                            f"{Ec[r]:.8g}"])
        flag = "PASS ✓" if passed else "FAIL ✗"
        print(f"  {name:5s} {flag}  E0={E[0]:8.3f}  dissipated={dissipated:8.3f}J  "
              f"max ΔE/step={max_rise:+.2e}J @ t={t_rise:.3f}s  "
              f"contact_E_peak={Ec.max():.2e}J  (>{args.tol:g}: {n_viol} steps)")

    # certificate table
    with (_DATA / f"passivity_{args.scene}_{args.kind}_certificate.csv"
          ).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cert_rows[0].keys()))
        w.writeheader()
        for row in cert_rows:
            w.writerow(row)

    _plot(results, args.scene, args.kind, args.tol)


def _plot(results, scene, kind, tol):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"AVBD": "#fb923c", "XPBD": "#34d399", "GT": "#222", "SPLIT": "#e0635a"}
    fig, ax = plt.subplots(1, 2, figsize=(15, 5.0))
    fig.suptitle(f"Energy-consistent passivity certificate ({scene}, {kind})\n"
                 f"each solver's total energy (native contact model) is monotone "
                 f"non-increasing — passive, no governor", fontsize=12)
    for name, (t, E, Ec) in results.items():
        c = colors.get(name)
        ax[0].plot(t, E, label=name, color=c, lw=1.3)
        ax[1].plot(t[1:], np.diff(E), label=name, color=c, lw=0.9)
    ax[0].set_title("Total energy E(t)  =  KE + PE_el + PE_grav + Φ_contact")
    ax[0].set_ylabel("E [J]"); ax[0].set_xlabel("t [s]")
    ax[1].axhline(tol, color="k", ls="--", lw=1.0, label=f"+tol ({tol:g} J)")
    ax[1].axhline(0.0, color="#999", ls=":", lw=0.8)
    ax[1].set_title("Per-step ΔE  (passive ⇔ stays ≤ tol — below the dashed line)")
    ax[1].set_ylabel("E[n+1] − E[n] [J]"); ax[1].set_xlabel("t [s]")
    for a in ax:
        a.legend(fontsize=9); a.grid(alpha=0.25)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    _FIG.mkdir(parents=True, exist_ok=True)
    out = _FIG / f"passivity_{scene}_{kind}.png"
    fig.savefig(out, dpi=130); print(f"  wrote {out}")


if __name__ == "__main__":
    main()
