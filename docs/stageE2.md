# Stage E2 — Passive Scaling Coefficient α

Implements the quadratic energy cap from foundation §6 as a pure function.

## What was added

- `passive_alpha(s, qdot, E_max) -> float` in `dcr/modal/passive_inject.py`

Given raw kick `s`, current velocity `qdot`, and energy budget `E_max = eta * E_loss`, finds the largest `alpha in [0, 1]` such that `dE_modal(alpha) = alpha*b + 0.5*alpha^2*a <= E_max`.

## Edge cases handled

- **Zero impulse** (a=0): alpha=0
- **Dissipative kick** (dE_full <= 0): alpha=1 regardless of E_max
- **Opposing impulse** (b < 0, |b| > 0.5a): alpha=1 even with E_max=0
- **Partial cap** (b > 0, E_max small): alpha between 0 and 1, solves quadratic exactly

## Acceptance results (10 tests)

- **Property-based (10k samples):** dE_modal(alpha) <= E_max + 1e-12 for all samples. Zero violations.
- **Zero E_max (5k samples):** dE_modal(alpha) <= 1e-12 for all samples.
- **Monotonicity:** Verified dE_modal non-decreasing in alpha when b >= 0.
- **Opposing impulse:** alpha=1 confirmed for hand-constructed cases with E_max=0.
- **Scalar mode:** Exact match with analytical quadratic root.
