#!/usr/bin/env python3
"""Does the impact-window energy reservoir fix the low-iteration starvation?
(avbd_dcr_impact_reservoir_fix §12).

The confirmed root cause (docs §9): total rigid E_loss is iteration-insensitive
(~45 J at every iter count), but the modal injection only fires on is_new frames,
which desync from the E_loss spike at low AVBD iters → zero injection at iters=4.

The reservoir deposits η·E_loss every step into a short-lived per-(rigid,support)
budget and spends it whenever a contact is still near (no is_new requirement). If
it works, cumulative injected modal energy becomes ~flat across iters.

Sweep: iters ∈ {4,8,16,32} × use_impact_reservoir ∈ {False,True} ×
impulse_source ∈ {lambda_only, delta_p}. Pass conditions:
  (A) CV_reservoir / CV_old < 0.5  (target < 0.25), CV of cum injection vs iters.
  (B) passivity: cum_E_inj ≤ η·cum_E_loss + ε  (every config).
  (C) cum_E_expired > 0 in some config (budget does not live forever).
"""
from __future__ import annotations

import numpy as np

from scripts.run_scenes_avbd import build_shelf_scene

ETA = 0.5
ITERS = [4, 8, 16, 32]


def run(use_reservoir: bool, source: str, iters: int,
        n_steps: int = 200, device: str = "cpu") -> dict[str, float]:
    world, coupler, *_ = build_shelf_scene(
        device=device, h=1.0 / 120.0, eta=ETA, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
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
    final_res = float(sum(e.energy for e in coupler.impact_reservoirs.values()))
    return {
        "cum_E_loss": cum_E_loss,
        "cum_deposit": float(coupler.cum_E_reservoir_deposit),
        "cum_inj": cum_inj,
        "cum_expired": float(coupler.cum_E_reservoir_expired),
        "final_res": final_res,
        "fill": (cum_inj / budget) if budget > 1e-30 else 0.0,
        "n_inj": n_inj,
        "peak_E_modal": float(coupler.last_E_modal_peak),
        "passive_ok": cum_inj <= budget + 1e-6,
    }


def _cv(xs: list[float]) -> float:
    a = np.asarray(xs, dtype=np.float64)
    m = float(np.mean(a))
    return float(np.std(a) / m) if abs(m) > 1e-30 else 0.0


def main() -> None:
    configs = [(False, "lambda_only"), (True, "lambda_only"),
               (False, "delta_p"), (True, "delta_p")]
    res: dict[tuple, dict[int, dict[str, float]]] = {}
    for use_res, src in configs:
        res[(use_res, src)] = {it: run(use_res, src, it) for it in ITERS}

    for use_res, src in configs:
        tag = f"reservoir={'ON ' if use_res else 'OFF'}  source={src}"
        print(f"\n=== {tag} ===")
        print(f"{'iters':>6}{'cum_inj':>11}{'fill':>8}{'n_inj':>7}"
              f"{'deposit':>11}{'expired':>10}{'final_res':>11}{'E_loss':>10}")
        for it in ITERS:
            r = res[(use_res, src)][it]
            print(f"{it:>6}{r['cum_inj']:>11.4g}{r['fill']:>8.3f}{r['n_inj']:>7d}"
                  f"{r['cum_deposit']:>11.4g}{r['cum_expired']:>10.4g}"
                  f"{r['final_res']:>11.4g}{r['cum_E_loss']:>10.4g}")

    # CV of cumulative injection across iters.
    def cv_of(use_res, src):
        return _cv([res[(use_res, src)][it]["cum_inj"] for it in ITERS])

    cv_old = cv_of(False, "lambda_only")
    print("\n" + "=" * 66)
    print(f"CV(cum_inj) across iters {ITERS}:")
    for use_res, src in configs:
        print(f"  reservoir={'ON ' if use_res else 'OFF'} {src:<12} "
              f"CV = {cv_of(use_res, src):.3f}")

    # Acceptance.
    print("-" * 66)
    best = min(cv_of(True, "lambda_only"), cv_of(True, "delta_p"))
    ratio = best / cv_old if cv_old > 1e-30 else float("inf")
    okA = ratio < 0.5
    print(f"(A) best CV_reservoir / CV_old = {ratio:.3f}  "
          f"(<0.5 ? {'PASS' if okA else 'FAIL'}; <0.25 target {'MET' if ratio<0.25 else 'no'})")
    passive_all = all(res[c][it]["passive_ok"] for c in configs for it in ITERS)
    print(f"(B) passivity cum_inj ≤ η·cum_E_loss (all configs): "
          f"{'PASS' if passive_all else 'FAIL'}")
    any_expired = any(res[c][it]["cum_expired"] > 0 for c in configs for it in ITERS)
    print(f"(C) some config has cum_expired > 0: {'PASS' if any_expired else 'FAIL'}")
    print("=" * 66)
    # Headline: did the reservoir make iters=4 inject at all?
    for src in ("lambda_only", "delta_p"):
        off4 = res[(False, src)][4]["cum_inj"]
        on4 = res[(True, src)][4]["cum_inj"]
        print(f"iters=4 cum_inj  {src:<12}: OFF={off4:.4g}  ON={on4:.4g}")


if __name__ == "__main__":
    main()
