#!/usr/bin/env python3
"""Energy-PRESCRIBED injection: does scaling the kick to the budget close the
low-iteration gap? (the §12 "option 1" fix).

Story (docs §9-§11): the modal injection s = Φ(x)ᵀJ starves at low AVBD iters
because ‖s‖ is tiny (smeared impulse) and passive_alpha can only scale DOWN
(α≤1) — so a large η·E_loss budget sits unspent. The reservoir fixes the TIMING
(budget available every frame) but not the MAGNITUDE.

Option 1 keeps s's DIRECTION (the spectral distribution from the contact
geometry, robust across iters) but sets the MAGNITUDE from the energy budget:
prescribed_alpha scales s UP or DOWN to deposit μ·(available budget). Layered on
the reservoir, each step spends the accumulated η·E_loss → fill → ~1 at all iter
counts → iteration-insensitive. Still globally passive: the realized ΔE is
debited from the reservoir, which is bounded by η·Σ E_loss.

Sweep iters ∈ {4,8,16,32}. Table: E_rigid lost → η·E_loss budget → E_modal
injected → fill. Acceptance:
  (A) CV(E_modal) across iters < 0.35 for prescribed (vs ~0.68 baseline).
  (B) passivity cum_E_inj ≤ η·cum_E_loss + ε (every config).
  (C) fill at iters=4 rises from ~0.05 (passive) toward ~1 (prescribed).
"""
from __future__ import annotations

import numpy as np

from scripts.run_scenes_avbd import build_shelf_scene

ETA = 0.5
ITERS = [4, 8, 16, 32]

# (label, use_reservoir, impulse_source, injection_scaling)
CONFIGS = [
    ("is_new   λ  passive   ", False, "lambda_only", "passive"),
    ("reservoir δp passive   ", True, "delta_p", "passive"),
    ("reservoir δp PRESCRIBED", True, "delta_p", "prescribed"),
]


def run(use_reservoir: bool, source: str, scaling: str, iters: int,
        n_steps: int = 200, device: str = "cpu") -> dict[str, float]:
    world, coupler, *_ = build_shelf_scene(
        device=device, h=1.0 / 120.0, eta=ETA, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
    coupler.use_impact_reservoir = use_reservoir
    coupler.impulse_source = source
    coupler.injection_scaling = scaling
    coupler.prescribed_mu = 1.0

    cum_E_loss = 0.0
    n_inj = 0
    cap_fired = 0
    for _ in range(n_steps):
        world.step()
        cum_E_loss += float(world.last_E_loss)
        if coupler.last_E_modal_injected > 1e-12:
            n_inj += 1
        cap_fired += int(coupler.last_prescribed_alpha_cap_fired)

    cum_inj = float(coupler.cum_E_modal_injected)
    budget = ETA * cum_E_loss
    return {
        "E_rigid_lost": cum_E_loss,
        "budget": budget,
        "E_modal": cum_inj,
        "fill": (cum_inj / budget) if budget > 1e-30 else 0.0,
        "n_inj": n_inj,
        "cap_fired": cap_fired,
        "peak_E_modal": float(coupler.last_E_modal_peak),
        "passive_ok": cum_inj <= budget + 1e-6,
    }


def _cv(xs: list[float]) -> float:
    a = np.asarray(xs, dtype=np.float64)
    m = float(np.mean(a))
    return float(np.std(a) / m) if abs(m) > 1e-30 else 0.0


def main() -> None:
    res = {label: {it: run(ur, src, sc, it) for it in ITERS}
           for label, ur, src, sc in CONFIGS}

    for label, *_ in CONFIGS:
        print(f"\n=== {label.strip()} ===")
        print(f"{'iters':>6}{'E_rigid_lost':>13}{'η·budget':>10}"
              f"{'E_modal':>10}{'fill':>8}{'n_inj':>7}{'α_cap':>7}")
        for it in ITERS:
            r = res[label][it]
            print(f"{it:>6}{r['E_rigid_lost']:>13.4g}{r['budget']:>10.4g}"
                  f"{r['E_modal']:>10.4g}{r['fill']:>8.3f}{r['n_inj']:>7d}"
                  f"{r['cap_fired']:>7d}")

    def cv_of(label):
        return _cv([res[label][it]["E_modal"] for it in ITERS])

    cv_base = cv_of("is_new   λ  passive   ")
    cv_pass = cv_of("reservoir δp passive   ")
    cv_pre = cv_of("reservoir δp PRESCRIBED")
    print("\n" + "=" * 72)
    print(f"CV(E_modal) across iters {ITERS}:")
    print(f"  is_new   λ  passive    : {cv_base:.3f}")
    print(f"  reservoir δp passive    : {cv_pass:.3f}")
    print(f"  reservoir δp PRESCRIBED : {cv_pre:.3f}")
    print("-" * 72)
    print(f"(A) CV_prescribed = {cv_pre:.3f} < 0.35 ? "
          f"{'PASS' if cv_pre < 0.35 else 'FAIL'}")
    passive_all = all(res[c[0]][it]["passive_ok"] for c in CONFIGS for it in ITERS)
    print(f"(B) passivity cum_E_inj ≤ η·cum_E_loss (all configs): "
          f"{'PASS' if passive_all else 'FAIL'}")
    f4_pass = res["reservoir δp passive   "][4]["fill"]
    f4_pre = res["reservoir δp PRESCRIBED"][4]["fill"]
    print(f"(C) iters=4 fill: reservoir-passive={f4_pass:.3f} -> "
          f"prescribed={f4_pre:.3f}  "
          f"({'UP' if f4_pre > f4_pass else 'NOT up'})")
    print("=" * 72)
    print("iters=4 E_modal:  "
          + "  ".join(f"{c[0].strip()}={res[c[0]][4]['E_modal']:.3g}"
                      for c in CONFIGS))


if __name__ == "__main__":
    main()
