# Task: Fix energy bookkeeping bug in distant-velocity Versions A and B

## Context

The file `dcr/dcr/distant_velocity.py` implements two energy-prescribed distant-velocity modes. Both currently use a buggy formula:

```python
speed = sqrt(2 * E_target / m)
v += speed * n_prime  # Version A
# or
J = m * speed * n_prime  # Version B
```

and claim the realized ΔKE equals `E_target`. **This is wrong.** Adding `γ·n′` to a velocity that already has a component along `n′` produces a kinetic-energy change with a linear cross-term, not a pure quadratic. Version B has an even larger error because the angular contribution is also ignored.

The math foundation is correct in `prompts/passive_modal_energy_injection_foundation.md` §6 (the `passive_alpha` derivation). The distant-velocity modes need to use the same quadratic-budget machinery.

## The correct math

### Version A: linear COM kick along deformed normal n′

Let `γ` be the added speed (scalar) and `n′` be a unit vector. Then:

    ΔKE(γ) = m·(v·n′)·γ + ½·m·γ²

Set `ΔKE(γ) = E_target` and solve for γ ≥ 0. This is the same quadratic structure as §6:

    a = m
    b = m·(v·n′)
    γ* = (−b + √(b² + 2·a·E_target)) / a
       = −(v·n′) + √((v·n′)² + 2·E_target/m)

In LaTeX:

$$\gamma^*_A = -(\mathbf{v} \cdot \mathbf{n}') + \sqrt{(\mathbf{v} \cdot \mathbf{n}')^2 + 2 E_{\text{target}} / m}$$

Edge cases:
- If `E_target ≤ 0`, set `γ* = 0` (no kick).
- The discriminant `(v·n′)² + 2·E_target/m` is always ≥ 0 when E_target ≥ 0, so the sqrt is real.
- `γ*` is always ≥ 0 by construction (since √(b² + 2aE) ≥ |b|).

Apply: `v ← v + γ* · n′`.

### Version B: point impulse at offset r along deformed normal n′

Let `γ` be the added speed magnitude (so `J = m·γ·n′`). Let `v_c = v + ω × r` be the contact-point velocity. Then:

    ΔKE(γ) = m·γ·(n′·v_c) + ½·γ²·[m + m²·(r×n′)ᵀ·I⁻¹·(r×n′)]

So:

    a = m + m²·(r × n′)ᵀ · I⁻¹ · (r × n′)
    b = m·(n′ · v_c)
    γ* = (−b + √(b² + 2·a·E_target)) / a

In LaTeX:

$$a = m + m^2 (\mathbf{r} \times \mathbf{n}')^T \mathbf{I}^{-1} (\mathbf{r} \times \mathbf{n}')$$
$$b = m (\mathbf{n}' \cdot \mathbf{v}_c), \quad \mathbf{v}_c = \mathbf{v} + \boldsymbol{\omega} \times \mathbf{r}$$
$$\gamma^*_B = \frac{-b + \sqrt{b^2 + 2 a E_{\text{target}}}}{a}$$

Edge cases:
- If `E_target ≤ 0`, set `γ* = 0`.
- `a > 0` always (since both m > 0 and the quadratic form (r×n′)ᵀI⁻¹(r×n′) ≥ 0 because I is SPD).
- Discriminant is non-negative when E_target ≥ 0.

Apply:

```python
J = m * gamma_star * n_prime
v += J / m
omega += I_inv @ np.cross(r, J)
```

**Physical note (worth a comment in the code):** the quantity `1/m + (r×n′)ᵀ·I⁻¹·(r×n′)` is the inverse effective mass at the contact point along `n′` (equivalent to `1/m_eff` from the paper's Eq. 17 specialized to a normal direction). The corrected `a` is `m²` times this. Mentioning this in the comment links the derivation to the original paper.

## Files to change

1. **`dcr/dcr/distant_velocity.py`**
   - Replace the `speed = sqrt(2*E_target/m)` formula in Version A (`energy_prescribed`) with the γ*_A quadratic above.
   - Replace the `J = m·speed·n′` formula in Version B (`energy_prescribed_point_impulse`) with the γ*_B quadratic above.
   - Add `# DEVIATION:` comments citing §6 (same convention as the rest of the repo).
   - Add docstrings explaining the cross-term correction and the connection to `m_eff` from paper Eq. 17.
   - Handle edge cases: `E_target ≤ 0` → γ* = 0 (return without kicking).

2. **`tests/`** — add a new test file `tests/stage_distant_velocity_energy.py` that:
   - For Version A: constructs bodies with various initial velocities (including `v·n′ > 0`, `v·n′ < 0`, and `v·n′ = 0`), various E_target values, applies the kick, and asserts the realized ΔKE matches E_target to within 1e-10 (or appropriate float tolerance).
   - For Version B: same, but also varies r (contact offset), ω (initial angular velocity), and I (inertia tensor, including non-diagonal cases). Assert realized ΔKE (linear + angular) matches E_target to within tolerance.
   - Include a regression test that catches the old buggy behavior: pick a case where `v·n′ ≠ 0` and verify the new formula gives a different γ than `sqrt(2·E_target/m)`.

3. **`docs/distant_velocity_modes.md`**
   - Update the math section to reflect the corrected formulas.
   - Note the bugfix in a changelog or "corrections" subsection.
   - Re-run any h-sweep or β-sweep plots that depend on the energy-bookkeeping claim; the numbers will shift (likely β can be pushed higher for the same effective energy injection).

4. **`prompts/passive_modal_energy_injection_foundation.md`**
   - Add a subsection (e.g., §6.1 or §16) deriving γ*_A and γ*_B from the same quadratic-budget principle as §6.
   - Show the connection to `m_eff` (paper Eq. 17).

## Acceptance criteria

- All new tests in `tests/stage_distant_velocity_energy.py` pass.
- Existing tests in `tests/stageE4` still pass (the global rigid-energy bound should still hold; in fact it should bind less spuriously now).
- For Version A with `v·n′ ≠ 0`, the new γ differs from `sqrt(2·E_target/m)` — this is the regression check.
- Code review: every changed function has an updated docstring that includes the quadratic formula and a `# DEVIATION:` or `# CORRECTION:` comment referencing the foundation document.

## Do not change

- The α* derivation in `dcr/modal/passive_inject.py:passive_alpha` (this was already correct).
- The global rigid-energy bound in `DCRWorld.enforce_rigid_energy_bound` (still correct; will just bind for the right reasons now).
- The `compute_deformed_normal` primitive (independent of this bug).
