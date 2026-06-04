#!/usr/bin/env python3
"""Killer diagnostic (realtime-coupling-fix §16): is the DCR modal injection
iteration-sensitive, and does the effective-impulse source fix it?

For each `impulse_source` × AVBD `iterations`, run the shelf scene (one heavy
8 kg drop onto a soft cantilever) and measure both the CAPPED injected modal
energy AND the raw PRE-CAP kick magnitude. The pre-cap magnitude is the real
test of the prompt's hypothesis (that λ-only is under-grown at low iters),
because the passive_alpha energy cap can mask source differences.

  * lambda_only : J = λ_N·n + λ_T·t (today).
  * augmented   : λ + h·k·C⁺  (§2.2).
  * delta_p     : −(rigid partner's measured contact Δp)  (§2.3).

Columns reported per source:
  cum_inj   cumulative CAPPED injected modal energy (J)
  n_inj     number of steps that fired a new-contact injection
  s_norm    mean raw ‖s‖ on injecting steps (pre-cap source magnitude)
  dE_raw    mean uncapped injection b+½a on injecting steps (pre-cap)
  alpha     mean passive_alpha on injecting steps (<1 ⇒ cap is binding)
  E_loss    cumulative rigid KE removed by AVBD (the budget driver)
"""
from __future__ import annotations

import numpy as np

from scripts.run_scenes_avbd import build_shelf_scene

ETA = 0.5
SOURCES = ["lambda_only", "augmented", "delta_p"]
ITERS = [4, 8, 16, 32]


def run(impulse_source: str, iters: int, n_steps: int = 200,
        device: str = "cpu") -> dict[str, float]:
    world, coupler, _boxes, _mesh, _ = build_shelf_scene(
        device=device, h=1.0 / 120.0, eta=ETA, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
    coupler.impulse_source = impulse_source

    cum_E_loss = 0.0
    n_inj = 0
    sum_s = sum_dE = sum_alpha = 0.0
    for _ in range(n_steps):
        world.step()
        cum_E_loss += float(world.last_E_loss)
        if coupler.last_E_modal_injected > 1e-12:
            n_inj += 1
            sum_s += float(coupler.last_s_total_norm)
            sum_dE += float(coupler.last_dE_full_uncapped)
            sum_alpha += float(coupler.last_alpha)

    nz = max(1, n_inj)
    return {
        "cum_injected": float(coupler.cum_E_modal_injected),
        "n_inj": n_inj,
        "s_norm": sum_s / nz,
        "dE_raw": sum_dE / nz,
        "alpha": sum_alpha / nz,
        "cum_E_loss": cum_E_loss,
    }


def _cv(xs: list[float]) -> float:
    a = np.asarray(xs, dtype=np.float64)
    m = float(np.mean(a))
    return float(np.std(a) / m) if abs(m) > 1e-30 else 0.0


def main() -> None:
    results: dict[str, dict[int, dict[str, float]]] = {s: {} for s in SOURCES}
    for src in SOURCES:
        for it in ITERS:
            results[src][it] = run(src, it)

    for src in SOURCES:
        print(f"\n=== impulse_source = {src} ===")
        print(f"{'iters':>6}{'cum_inj':>12}{'n_inj':>7}{'s_norm':>12}"
              f"{'dE_raw':>12}{'alpha':>8}{'E_loss':>12}")
        for it in ITERS:
            r = results[src][it]
            print(f"{it:>6}{r['cum_injected']:>12.4e}{r['n_inj']:>7d}"
                  f"{r['s_norm']:>12.4e}{r['dE_raw']:>12.4e}"
                  f"{r['alpha']:>8.3f}{r['cum_E_loss']:>12.4e}")

    # Is the SOURCE magnitude iteration-sensitive? Compare raw ‖s‖ CV.
    print("\n" + "=" * 64)
    print("CV of raw pre-cap ‖s‖ across iters (the prompt's hypothesis is that")
    print("lambda_only ‖s‖ rises with iters while delta_p ‖s‖ stays flat):")
    for src in SOURCES:
        s_by_iter = [results[src][it]["s_norm"] for it in ITERS]
        print(f"  {src:<12} CV(‖s‖) = {_cv(s_by_iter):.3f}   "
              f"values = [{', '.join(f'{v:.3e}' for v in s_by_iter)}]")

    print("\nCV of CAPPED cumulative injection across iters:")
    for src in SOURCES:
        inj = [results[src][it]["cum_injected"] for it in ITERS]
        print(f"  {src:<12} CV(inj) = {_cv(inj):.3f}")
    print("=" * 64)


if __name__ == "__main__":
    main()
