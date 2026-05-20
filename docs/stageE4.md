# Stage E4 — Multi-Contact Aggregation + Monotone Dissipation

Empirically verifies foundation §8 (single global bound per step) and §3/§9 (monotone dissipation without input).

## What was verified

### E4.1: Multi-contact aggregation

Two rigid balls dropped simultaneously onto the same elastic slab, contacting at different surface points. Two injection strategies compared:

- **Per-contact-bounded (incorrect):** Apply `alpha_1 * s_1` then `alpha_2 * s_2` sequentially, each with its own copy of `E_max`. With 2 contacts, this allows up to `2 * E_max` total injection.
- **Aggregate (correct, Stage E3):** One update with `s_total = s_1 + s_2` and a single `alpha`. Guaranteed `<= E_max`.

Results (impulse sweep, E_max = 0.5J):
- Per-contact saturates at **1.0J** (2x budget) for strong impulses.
- Aggregate saturates at **0.5J** (exactly the budget).

Full two-ball simulation (500 steps, eta=1.0): cumulative injected = 2.53J, cumulative loss = 9.21J. Bound holds at every step.

### E4.2: Monotone dissipation

Single ball hits slab and bounces clear. After the last contact, no new impulses enter the modal system. With Rayleigh damping (alpha0=2.0, alpha1=1e-5):

- `E_modal(t_{k+1}) <= E_modal(t_k)` verified at every **sub-step** (not just rigid step) across 500 rigid steps of free decay.
- **Zero violations** in both the full-sim test (ball bounces clear, then free decay) and the direct stepper test (10,000 sub-steps from random initial conditions).
- Energy decays from 448J to 3e-7J over 10,000 sub-steps in the direct test.

## Plots

- `docs/stageE4/aggregation_comparison.png` — Per-contact (red, exceeds budget) vs aggregate (blue, respects budget).
- `docs/stageE4/monotone_dissipation.png` — Left: full timeline (impact + decay). Right: log-scale sub-step decay, zero violations.

## Tests (4 passing)

- `test_aggregate_vs_per_contact_energy_bound` — Synthetic comparison, per-contact injects 2x E_max, aggregate stays under.
- `test_aggregate_bound_holds_in_full_sim` — Two-ball sim, cumulative invariant at every step.
- `test_monotone_dissipation_sub_step` — Full sim: ball bounces clear, then E_modal checked at every sub-step.
- `test_monotone_dissipation_direct` — Unit: random initial conditions, 10k sub-steps, strict monotonicity.
