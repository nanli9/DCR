#!/usr/bin/env python3
"""Does the coherent impact impulse bank close the low-iteration gap the
reservoir left open? (coherent_impact_impulse_bank_fix §11-§13).

Story so far (docs §9/§10): total rigid E_loss is iteration-insensitive (~46 J),
but the modal injection collapses at low AVBD iters. The reservoir fixed the
TIMING starvation (iters=4 no longer injects 0) but not the MAGNITUDE: a soft
solve smears one impact over many small per-frame impulses, and per-frame
injection keeps only Σ½‖s_i‖², discarding the cross terms ½‖Σs_i‖² would recover.

The bank accumulates the impulses of one physical impact over a short causal
window and injects the event-level ½‖Σs_i‖² once. The decisive quantity is the
coherence ratio R = ‖Σs_i‖²/Σ‖s_i‖²:
  * R ≫ 1  ⇒ low-iter AVBD really smeared one coherent impact; banking recovers it.
  * R ≈ 1  ⇒ the impulses are genuinely incoherent; banking cannot help and the
            §14 sharp-impulse estimator is the honest next step.

Sweep: iters ∈ {4,8,16,32} × config ∈ {is_new(λ-only), reservoir+δp, bank+δp}.
Acceptance (spec §12):
  (A) CV(E_injected)_bank < 0.35  OR  CV_bank < 0.5·CV_reservoir.
  (B) passivity cum_E_inj ≤ η·cum_E_loss + ε  (every config).
  (C) budget utilization rises at iters=4 (bank vs reservoir).
"""
from __future__ import annotations

import numpy as np

from scripts.run_scenes_avbd import build_shelf_scene

ETA = 0.5
ITERS = [4, 8, 16, 32]

# (label, use_bank, use_reservoir, impulse_source)
CONFIGS = [
    ("is_new   λ-only", False, False, "lambda_only"),
    ("reservoir δp    ", False, True, "delta_p"),
    ("bank      δp    ", True, False, "delta_p"),
]


def run(use_bank: bool, use_reservoir: bool, source: str, iters: int,
        n_steps: int = 200, device: str = "cpu") -> dict[str, float]:
    world, coupler, *_ = build_shelf_scene(
        device=device, h=1.0 / 120.0, eta=ETA, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
    coupler.use_coherent_impulse_bank = use_bank
    coupler.use_impact_reservoir = use_reservoir
    coupler.impulse_source = source

    cum_E_loss = 0.0
    n_inj = 0
    for _ in range(n_steps):
        world.step()
        cum_E_loss += float(world.last_E_loss)
        if coupler.last_E_modal_injected > 1e-12:
            n_inj += 1

    cum_inj = float(coupler.cum_E_modal_injected)
    budget = ETA * cum_E_loss
    if use_bank:
        deposit = float(coupler._bank.cum_E_deposit)
        expired = float(coupler._bank.cum_E_expired)
        final_budget = float(coupler._bank.total_budget())
        R = float(coupler.last_R_coherence)
    else:
        deposit = float(coupler.cum_E_reservoir_deposit)
        expired = float(coupler.cum_E_reservoir_expired)
        final_budget = float(sum(
            e.energy for e in coupler.impact_reservoirs.values()))
        R = 0.0
    return {
        "cum_E_loss": cum_E_loss,
        "cum_inj": cum_inj,
        "fill": (cum_inj / budget) if budget > 1e-30 else 0.0,
        "util": (cum_inj / deposit) if deposit > 1e-30 else 0.0,
        "R": R,
        "n_inj": n_inj,
        "deposit": deposit,
        "expired": expired,
        "final_budget": final_budget,
        "peak_E_modal": float(coupler.last_E_modal_peak),
        "passive_ok": cum_inj <= budget + 1e-6,
    }


def _cv(xs: list[float]) -> float:
    a = np.asarray(xs, dtype=np.float64)
    m = float(np.mean(a))
    return float(np.std(a) / m) if abs(m) > 1e-30 else 0.0


def main() -> None:
    res: dict[str, dict[int, dict[str, float]]] = {}
    for label, ub, ur, src in CONFIGS:
        res[label] = {it: run(ub, ur, src, it) for it in ITERS}

    for label, *_ in CONFIGS:
        print(f"\n=== {label.strip()} ===")
        print(f"{'iters':>6}{'cum_inj':>11}{'fill':>8}{'util':>8}{'R_coh':>8}"
              f"{'n_inj':>7}{'deposit':>10}{'expired':>9}{'E_loss':>9}")
        for it in ITERS:
            r = res[label][it]
            print(f"{it:>6}{r['cum_inj']:>11.4g}{r['fill']:>8.3f}"
                  f"{r['util']:>8.3f}{r['R']:>8.2f}{r['n_inj']:>7d}"
                  f"{r['deposit']:>10.4g}{r['expired']:>9.4g}"
                  f"{r['cum_E_loss']:>9.4g}")

    def cv_of(label):
        return _cv([res[label][it]["cum_inj"] for it in ITERS])

    cv_res = cv_of("reservoir δp    ")
    cv_bank = cv_of("bank      δp    ")
    cv_isnew = cv_of("is_new   λ-only")
    print("\n" + "=" * 70)
    print(f"CV(cum_inj) across iters {ITERS}:")
    print(f"  is_new   λ-only : {cv_isnew:.3f}")
    print(f"  reservoir δp    : {cv_res:.3f}")
    print(f"  bank      δp    : {cv_bank:.3f}")
    print("-" * 70)
    okA = (cv_bank < 0.35) or (cv_res > 1e-30 and cv_bank < 0.5 * cv_res)
    print(f"(A) CV_bank={cv_bank:.3f} < 0.35 ? {cv_bank < 0.35}  OR  "
          f"< 0.5·CV_res({0.5*cv_res:.3f}) ? {cv_res>1e-30 and cv_bank<0.5*cv_res}"
          f"  => {'PASS' if okA else 'FAIL'}")
    passive_all = all(res[c[0]][it]["passive_ok"] for c in CONFIGS for it in ITERS)
    print(f"(B) passivity cum_inj ≤ η·cum_E_loss (all configs): "
          f"{'PASS' if passive_all else 'FAIL'}")
    u4_res = res["reservoir δp    "][4]["util"]
    u4_bank = res["bank      δp    "][4]["util"]
    print(f"(C) iters=4 budget utilization: reservoir={u4_res:.3f} -> "
          f"bank={u4_bank:.3f}  ({'up' if u4_bank > u4_res else 'NOT up'})")
    print("=" * 70)
    print("iters=4 cum_inj:  "
          + "  ".join(f"{c[0].strip()}={res[c[0]][4]['cum_inj']:.3g}"
                      for c in CONFIGS))
    print("mean R_coherence (bank, per iters): "
          + "  ".join(f"{it}:{res['bank      δp    '][it]['R']:.2f}"
                      for it in ITERS))
    print("\nVerdict: if R_coherence ≫ 1 and CV_bank dropped, banking recovered "
          "the smeared impact.\nIf R_coherence ≈ 1 and iters=4 stayed near "
          "1-2 J, low-iter AVBD is a genuinely\ndifferent trajectory → §14 "
          "sharp-impulse estimator is the honest next step.")


if __name__ == "__main__":
    main()
