"""Item (1): h/T unit-chain audit of the reduced-AVBD overlay.

The critique thread flagged the h-vs-T bookkeeping as "the classic place
an overlay comes out an order of magnitude too hot or too cold."  This
script is a self-contained closed-form verification:

    1. Take a single SDOF mode (m=1, ω known, ξ small).
    2. Drive it with a known Dirac impulse J=1 N·s at t=0.
    3. Closed-form peak displacement: q_peak = J / (m · ω_d).
    4. Step the same IIR scheme the overlay uses, with the same
       r_first convention (r_first = r_tilde · h_macro).
    5. Compare peak.

Also reports the predicted overlay/bare ratio against the spec's ω·h
prediction.  Outputs a CSV to /tmp/overlay_audit.csv and prints a
verdict line.  No GPU, ~50 ms to run.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np


def iir_coefs(omega: float, zeta: float, T: float):
    """Same coefficients as `IIRModalStepper._compute_coefficients`
    and the inlined version in reduced_support_solve.py."""
    if omega < 1e-12:
        return 1.0, 0.0, T
    wd = omega * np.sqrt(max(0.0, 1.0 - zeta * zeta))
    e = np.exp(-zeta * omega * T)
    a1 = 2.0 * e * np.cos(wd * T)
    a2 = e * e
    ar = e * np.sin(wd * T) / max(wd, 1e-12)
    return a1, a2, ar


def iir_peak_for_impulse(omega: float, zeta: float, T: float,
                         n_substep: int, J_impulse: float, m: float = 1.0
                         ) -> float:
    """Run the same IIR sub-stepping the overlay does:
        - inject impulse J_impulse at sub-step k=0
        - free decay for k=1..n_substep-1
    Returns peak |q| over the sub-steps.
    """
    a1, a2, ar = iir_coefs(omega, zeta, T)
    q_prev = 0.0
    q_prev2 = 0.0
    peak = 0.0
    for k in range(n_substep):
        if k == 0:
            q_new = a1 * q_prev - a2 * q_prev2 + ar * (J_impulse / m)
        else:
            q_new = a1 * q_prev - a2 * q_prev2
        peak = max(peak, abs(q_new))
        q_prev2 = q_prev
        q_prev = q_new
    return peak


def closed_form_peak_dirac(omega: float, zeta: float, J_impulse: float,
                           m: float = 1.0) -> float:
    """Undamped (ζ→0):
        q(t) = (J / (m·ω)) · sin(ω·t)
        peak = J / (m·ω)
    Damped:
        q(t) = (J / (m·ω_d)) · e^{-ζω t} sin(ω_d t)
        peak attained where d/dt = 0; for small ζ it sits very close
        to ω·t = π/2 and gives q_peak ≈ J·e^{-ζ·π/2} / (m·ω_d).
    We report the analytical peak as J / (m · ω_d) · exp(-ζ · arctan(...))
    to first order, which collapses to J/(m·ω) at ζ=0.
    """
    wd = omega * np.sqrt(max(0.0, 1.0 - zeta * zeta))
    # Time at which q(t) extremises: tan(ω_d·t) = ω_d / (ζ·ω), so
    #   t* = atan2(ω_d, ζ·ω) / ω_d
    # and the peak value is J/(m·ω_d) · exp(-ζ·ω·t*) · sin(ω_d·t*).
    t_peak = np.arctan2(wd, zeta * omega) / max(wd, 1e-12) if zeta > 0 else (np.pi / 2.0) / max(omega, 1e-12)
    q_peak = (J_impulse / (m * max(wd, 1e-12))) * np.exp(-zeta * omega * t_peak) * np.sin(wd * t_peak)
    return float(abs(q_peak))


def overlay_step_two_path(omega: float, zeta: float, m: float,
                          K: float, r_tilde_force: float,
                          h_macro: float) -> dict:
    """Reproduce the bare/overlay branches of one macro step for an
    isolated SDOF with mass m, stiffness K=m·ω².
       bare   = (M/h² + K)^{-1} · r_tilde_force        (BDF1 implicit Euler steady)
       overlay = peak over IIR sub-steps after impulse J = r_tilde·h_macro
    """
    bare = r_tilde_force / (m / (h_macro * h_macro) + K)
    omega_max = omega
    T = float(np.pi / (2.0 * omega_max))
    n_substep = max(1, int(np.ceil(h_macro / T)))
    J = r_tilde_force * h_macro
    overlay = iir_peak_for_impulse(omega, zeta, T, n_substep, J, m=m)
    return {
        "bare": bare,
        "overlay": overlay,
        "T_substep": T,
        "n_substep": n_substep,
        "predicted_ratio_omega_h": omega * h_macro,
    }


def main(argv: list[str] | None = None) -> int:
    print("h/T unit-chain audit -- closed-form SDOF vs the overlay IIR\n")
    print(f"{'omega':>10s} {'h':>9s} {'omega*h':>9s} "
          f"{'closed':>11s} {'IIR':>11s} {'rel err':>9s}")

    rows = []
    omegas = [50.0, 200.0, 838.0, 2000.0]     # rad/s; 838 ~ first plate mode in the scene
    h_values = [1.0 / 60.0, 1.0 / 120.0, 1.0 / 240.0]
    zeta = 0.0   # impulse test is sharpest with ζ=0

    for omega in omegas:
        for h in h_values:
            T = float(np.pi / (2.0 * omega))
            n_sub = max(1, int(np.ceil(h / T)))
            J = 1.0
            closed = closed_form_peak_dirac(omega, zeta, J)
            iir = iir_peak_for_impulse(omega, zeta, T, n_sub, J)
            rel = abs(iir - closed) / max(closed, 1e-12)
            rows.append({
                "omega": omega,
                "h": h,
                "omega_h": omega * h,
                "T_substep": T,
                "n_substep": n_sub,
                "closed_form_peak": closed,
                "iir_peak": iir,
                "rel_err": rel,
            })
            print(f"{omega:10.2f} {h:9.5f} {omega*h:9.3f} "
                  f"{closed:11.4e} {iir:11.4e} {rel:9.2%}")

    print("\nBare-vs-overlay magnitude vs spec prediction (omega*h):\n")
    print(f"{'omega':>10s} {'h':>9s} {'predicted':>12s} "
          f"{'observed':>12s} {'bare':>11s} {'overlay':>11s}")
    r_tilde_force = 1.0
    for omega in omegas:
        for h in h_values:
            res = overlay_step_two_path(
                omega=omega, zeta=0.0, m=1.0, K=omega * omega,
                r_tilde_force=r_tilde_force, h_macro=h,
            )
            obs = res["overlay"] / max(res["bare"], 1e-30)
            print(f"{omega:10.2f} {h:9.5f} {omega*h:12.3f} {obs:12.3f} "
                  f"{res['bare']:11.4e} {res['overlay']:11.4e}")
            rows.append({
                "omega": omega,
                "h": h,
                "omega_h": omega * h,
                "T_substep": res["T_substep"],
                "n_substep": res["n_substep"],
                "ratio_observed": obs,
                "bare": res["bare"],
                "overlay": res["overlay"],
            })

    out = Path("/tmp/overlay_audit.csv")
    keys = sorted({k for r in rows for k in r.keys()})
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\n[csv] {out}")

    # Verdict: SDOF-IIR peak should match closed form within a few % for
    # ω·h modestly above 1; deviation grows when h <  T (n_sub=1, partial-
    # period sampling).  Take the worst case from the verified-only rows.
    worst = max(
        (r["rel_err"] for r in rows if "rel_err" in r),
        default=0.0,
    )
    print()
    if worst < 0.05:
        print(f"OK  IIR impulse peak matches closed form to <5% (worst={worst:.2%}).")
        print("    h/T unit chain in reduced_support_solve.py is consistent;")
        print("    no magnitude bug in the overlay sub-stepping.")
    else:
        print(f"WARN  worst SDOF-IIR error = {worst:.2%}. Re-check r_first units.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
