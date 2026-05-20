# Stage E1 — Modal Velocity-Kick Projection

Implements `s = Phi(x_c)^T j` — projecting a contact impulse onto the modal basis to produce a raw velocity kick vector.

## What was added

- `dcr/modal/passive_inject.py`:
  - `eval_basis_at_point()`: locates closest surface triangle, interpolates `U_surf` with barycentric weights to get `Phi(x_c)` (3 x n_modes).
  - `project_impulse()`: `s_c = Phi(x_c)^T j` — pure function, no state.
  - `aggregate_kicks()`: `s_total = sum_k s_k` for multiple contacts per body (foundation §8).

## Key differences from paper Eq. 9

- Projects the **full impulse** `j` (normal + tangential), not just `n_c * lambda_N`.
- Output is a **modal velocity kick** (not a force), because mass-normalized modes give `M_q = I`.

## Acceptance results (12 tests)

- **Toy basis (1 mode, constant [0,1,0]):** Normal y-impulse → s=1.0, tangential x-impulse → s=0.0. Matches hand calc.
- **Linearity:** `s(j1+j2) == s(j1) + s(j2)` verified over 50 random samples, error < 1e-12.
- **Aggregation:** Two-contact sum matches combined call to machine epsilon.
