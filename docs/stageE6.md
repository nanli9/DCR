# Stage E6 — Modal Sound Energy Bound (Log-Only)

This is an **energy bound**, not an audio signal. No `.wav` files, no audio backend.

## What was implemented

Per-mode dissipation tracking in the `HomogeneousStepper` (foundation §9):

```
P_diss_i = 2 ζ_i ω_i q̇_i²
E_diss = Σ_i Σ_k T · P_diss_i^(k)
```

Also computed robustly as `max(0, E_modal_post_kick - E_modal_post_step)` per rigid step — this is exact and avoids the ~2% overestimate from the forward-Euler P_diss formula.

Acoustic radiation bound with default `ρ_i = 0.1` for all modes:

```
E_sound ≤ Σ_i ρ_i · E_diss_i
```

## Results (dinner scene, η=1.0, 800 steps)

| Quantity | Value |
|---|---|
| Σ ΔE_modal (injected) | 30.37 J |
| Σ E_diss (damping) | 24.12 J |
| Σ E_sound (ρ=0.1) | 2.49 J |

Ordering `E_sound ≤ E_diss ≤ E_modal_injected` holds at every step. Zero violations.

## Future work

To produce actual sound from this bound, one would map `(q_i, q̇_i, ρ_i)` to a perceptual gain `g_i` and synthesize `p(t) = Σ g_i q̇_i(t)` (foundation §10), with `g_i` normalized so that emitted acoustic energy stays inside the budget. This is out of scope for this follow-up.

## Plots

- `docs/stageE6/sound_energy_bound.png` — Three-line cumulative plot with ordering verified.

## Tests (2 passing)

- `test_dissipation_cross_check` — P_diss sum matches robust E_before−E_after within 5%.
- `test_sound_bound_ordering` — Full dinner scene: E_sound ≤ E_diss ≤ E_injected at every step.
