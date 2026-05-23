# Passive Modal Energy Injection — Implementation Prompt

**Math foundation.** `passive_modal_energy_injection_foundation.md` (project root). Read it before you write a line of code.

**Original DCR plan.** `dcr_implementation_prompt.md`. This follow-up assumes Stages 1–6 of that plan (rigid → FEM → modal → IIR → modal DCR → spatial DCR) are complete and passing their acceptance criteria. Stage 7 (scenes / ground truth) is nice to have but not strictly required to begin Stage E0.

**Your job (Claude).** Extend the DCR project with a passive, energy-bounded injection mechanism: rigid-body kinetic energy lost during contact resolution funds a bounded velocity-level kick to the reduced modal state. The modal subsystem is then dissipative without further input. Build it in stages. Get each stage stable, tested, and visualized before moving to the next. Do **not** skip ahead.

---

## Ground rules (additions to those of the DCR prompt)

1. **Same stack, same CPU-only constraint.** Python 3.10+, `numpy`, `scipy`, `warp-lang` on `device="cpu"`, `polyscope`. No new dependencies.

2. **Velocity-level injection.** This follow-up replaces the paper's *forced IIR* (Eq. 10 with `r^(1) ≠ 0`) with a *velocity kick* to `q̇` followed by *free* damped oscillation of the modal state. The two formulations are equivalent at the SDOF level but the discrete code path is different. Every modal stepper change must carry a `# DEVIATION:` comment referencing §15 of the foundation.

3. **Energy is the contract.** The injection step must satisfy
   ```
   ΔE_modal  ≤  η · ΔE_rigid_loss
   ```
   globally, per rigid step, across all contacts in that step. This bound is testable and must be tested.

4. **No silent stacking.** Multiple contacts in one rigid step produce ONE bounded update with the aggregated `s_total` (foundation §8), not `m` independent updates that could each consume the full budget.

5. **Naming.**
   - `eta` — artist-controllable transfer efficiency η ∈ [0, 1].
   - `E_rigid_pre`, `E_rigid_post`, `E_loss`, `E_max` — rigid-side budget scalars.
   - `s_total` ∈ R^{n_modes} — aggregated modal velocity kick (pre-scaling).
   - `alpha` — passive scaling coefficient ∈ [0, 1].
   - `q`, `qdot` — modal displacement / velocity vectors.
   - `Phi(x)` ∈ R^{3 × n_modes} — modal basis evaluated at a world point on the elastic surface (i.e., barycentric-interpolated row block of the stored surface-restricted `U`).

6. **Free modal stepper.** From Stage E3 onward, the IIR's forcing term `a_{r,j} r^(k-1) / (m_j T)` is zero. The IIR becomes the homogeneous response of a damped SDOF seeded by `(q^(0), q̇^(0))`. Keep the homogeneous stepper code-adjacent to the original IIR; do not delete the forced version (acceptance comparisons depend on it).

7. **Same testing rhythm.** Each stage has acceptance criteria below. Run them, save a plot or short MP4 under `docs/stageE<n>/`, write a one-screen `docs/stageE<n>.md`, and only then proceed.

8. **Out of scope for this follow-up:**
   - Actual audio synthesis. Stage E6 logs a scalar bound only.
   - GPU port.
   - Bounce maps, anisotropic friction, contact-graph shock propagation.
   - Anything in the "claims to avoid" list (§14 of the foundation).

---

## Stage E0 — Energy bookkeeping (no behavior change)

**Goal.** Make rigid and modal energy first-class observables. Nothing in the simulation behaves differently yet.

### E0.1 Rigid kinetic energy

For an `n`-body system,

```
E_rigid  =  Σ_b ( 0.5 m_b ||v_b||^2  +  0.5 ω_b^T I_b ω_b )
```

with `I_b` in world frame (rotate the body-frame inertia each step, as in Stage 1).

Implement `rigid_kinetic_energy(state) -> float` in `dcr/rigid/energy.py`.

### E0.2 Modal kinetic + potential

With mass-normalized modes from Stage 3 (`M_q = I`),

```
E_modal  =  0.5 q̇^T q̇  +  0.5 q^T Ω^2 q,        Ω = diag(ω_1, ..., ω_m)
```

Implement `modal_energy(q, qdot, omega) -> float` in `dcr/modal/energy.py`.

### E0.3 Hooks around the solver

Sample `E_rigid_pre` immediately before `solve_constraints()` (Stage 1) and `E_rigid_post` immediately after `v ← v^+`. Define

```
E_loss  =  max(0, E_rigid_pre - E_rigid_post)
```

Log `(t, E_rigid, E_modal, E_loss)` to `docs/stageE0/energy.csv` whenever the energy logger is enabled. Add a `--log-energy` flag to `scripts/run_stage*.py`.

### E0.4 Acceptance criteria

- Single bouncing ball with restitution `0.5`: energy plot shows discrete drops at each bounce of factor `ε_r^2 = 0.25`. `E_loss` per step exactly accounts for the gap to within `1e-10`.
- No-contact free fall: `E_rigid` is bounded (symplectic Euler is not exactly conservative; report the per-step drift bound).
- Modal-only scene with contacts disabled and `(q, qdot)` initialized to a known eigenmode: `E_modal(t)` decays at the analytical rate for the assigned Rayleigh damping. ≤ 5% error.

Commit: `stageE0-energy-bookkeeping`.

---

## Stage E1 — Modal velocity-kick projection (s = Φ^T j)

**Goal.** Given a contact impulse, produce the raw modal velocity kick vector. Do not yet apply it anywhere.

### E1.1 The projection (foundation §4)

For a contact at world point `x_c` on the elastic body with impulse `j ∈ R^3` (normal + tangential, world frame),

```
s_c  =  Φ(x_c)^T  j
```

Concretely: locate the surface triangle containing `x_c`, compute barycentric weights, and form `Φ(x_c) ∈ R^{3 × n_modes}` by weighted-summing the three surface-node row-blocks of the stored `U` (the surface-restricted basis from Stage 3.6). Then `s_c = Φ(x_c)^T j`.

This generalizes the paper's Eq. 9 in two ways:
- We project the *full* impulse vector `j` (normal + frictional tangential), not just `n_c λ_N`.
- The output is a *modal velocity* kick in R^{n_modes}, not a modal *force* (the paper's `r_c = U^T H_c^T n_c λ_N` is a force-like quantity fed to the forced IIR).

With mass-normalized modes (Stage 3), no `M_q^{-1}` factor is required. If mass-normalization is ever switched off, divide componentwise by `diag(M_q)` (foundation §4).

### E1.2 Aggregation (foundation §8)

For all new contacts `{c_k}` touching the same elastic body in one rigid step,

```
s_total  =  Σ_k Φ(x_k)^T j_k
```

Per elastic body — do not mix `s_total`s across bodies.

### E1.3 Acceptance criteria

- Single-mode toy basis (`n_modes = 1`, `ψ_1` a known constant vector field): `s_c` matches a hand calculation for a unit normal impulse and for a unit tangential impulse.
- Linearity check: `s(j_1 + j_2) == s(j_1) + s(j_2)` to `1e-12`.
- Aggregation check: applying two contacts and summing matches one combined call to within machine epsilon.

Commit: `stageE1-modal-projection`.

---

## Stage E2 — Passive scaling coefficient α

**Goal.** Implement the quadratic cap (foundation §6) as a small, well-tested pure function.

### E2.1 Math

Given `s, qdot_old ∈ R^{n_modes}` and `E_max ≥ 0`:

```
a  =  s^T s
b  =  qdot_old^T s
ΔE_modal(α)  =  α b  +  0.5 α^2 a
```

Solve `ΔE_modal(α) ≤ E_max` for the largest `α ∈ [0, 1]`:

```
ΔE_full  =  b + 0.5 a

if a < eps_tiny:                  # no impulse direction
    α = 0
elif ΔE_full ≤ E_max:             # full kick fits in budget
    α = 1
else:                              # quadratic cap, positive root
    discr = max(0, b*b + 2 a E_max)
    α* = (-b + sqrt(discr)) / a
    α  = clip(α*, 0, 1)
```

Implement `passive_alpha(s, qdot, E_max) -> float` in `dcr/modal/passive_inject.py`. Pure function. No state. Tiny.

### E2.2 Edge cases

- `a = 0` (zero impulse) → `α = 0`. Trivial.
- `E_max = 0` (no rigid loss): if `b + 0.5 a ≤ 0` (impulse opposes current motion → net dissipative), allow `α = 1`; otherwise `α = 0`. Document this — it is *not* a violation of the bound, it is the bound being trivially satisfied in the negative direction.
- `b < 0` and `|b| > 0.5 a`: `ΔE_full < 0` → `α = 1` regardless of `E_max`. The new impulse decelerates the modal state.
- `b > 0, a > 0, E_max small`: `α` strictly between 0 and 1.

### E2.3 Acceptance criteria

- Property-based test over a randomly sampled grid of `(s, qdot, E_max)` (≥ 10,000 samples): assert `ΔE_modal(α) ≤ E_max + 1e-12` and `α ∈ [0, 1]` for every sample.
- Monotonicity test: `ΔE_modal` is non-decreasing in `α` on the regime `b ≥ 0`.
- Opposing-impulse test: a hand-constructed case with `b < 0` returns `α = 1` even when `E_max = 0`.

Commit: `stageE2-alpha-cap`.

---

## Stage E3 — Wire injection into the rigid step

**Goal.** Replace the forced-IIR injection of Stages 4/5 with the energy-bounded velocity-kick injection.

### E3.1 Modal stepper change

Switch the modal stepper to a homogeneous SDOF integrator with explicit `(q, qdot)` state. Two options:

- **Option A (preferred):** exact exponential integrator for a damped harmonic oscillator. For each mode `j` with `(ω_j, ζ_j)`, the 2×2 state-transition matrix over sub-step `T` is closed-form. Cheap, exact, no error analysis needed.
- **Option B:** reuse the James-Pai IIR `(a_{1,j}, a_{2,j})` coefficients from Stage 4 with `a_{r,j} ≡ 0`. Requires reconstructing one history step from `(q, qdot)`; document the reconstruction.

Pick A unless there is a good reason. Keep the Stage 4 forced-IIR code intact under a flag for acceptance comparisons.

> `# DEVIATION:` Cite foundation §15. The injection enters as initial-condition perturbation to `qdot`, not as an impulse forcing term inside Eq. 10.

### E3.2 Per-rigid-step flow

```python
# --- pre-solve ---
E_rigid_pre = rigid_kinetic_energy(state)

# --- Stage 1 rigid solve ---
lambda_plus, v_plus = solve_constraints(state, contacts, h)
state.v = v_plus

# --- post-solve ---
E_rigid_post = rigid_kinetic_energy(state)
E_loss = max(0.0, E_rigid_pre - E_rigid_post)
E_max  = eta * E_loss

# --- project new contact impulses onto the modal basis (Stage E1) ---
s_total = np.zeros(n_modes)
for c in new_contacts_on_elastic_body:
    j_world = (
        c.n  * lambda_N[c]
      + c.t1 * lambda_T1[c]
      + c.t2 * lambda_T2[c]
    )
    s_total += Phi_at(c.x).T @ j_world

# --- passive scaling (Stage E2) ---
alpha = passive_alpha(s_total, qdot, E_max)
qdot += alpha * s_total       # the injection

# --- homogeneous modal stepper for h/T sub-steps (Stage E3.1) ---
q, qdot, max_disp_per_node = step_modal_homogeneous(q, qdot, omega, zeta, h, T)

# --- distant-contact response (paper Stage 5.3–5.5, unchanged) ---
dv_p = Stage5_distant_response(max_disp_per_node, existing_contacts)
queue_dv_injection_into_next_b(dv_p)
```

The Stage 6 (spatial attenuation) path is updated symmetrically: the local self-displacement amplitude `Δx_c` is still computed from the per-vertex precomputed amplitude `q̂`, then attenuated by `s = C r^{-β}` and converted to `Δv_p` as in paper Eq. 16/19. The energy bound applies only to the *modal-path* injection in Stage E3; the spatial path is an empirical-amplitude response and is not energy-budgeted in this follow-up. Note this explicitly in the docstring and in the limitations section of `docs/stageE3.md`.

### E3.3 Acceptance criteria

- `eta = 0`: distant contacts receive no response. Plates do not move. `E_modal(t)` stays at whatever value it had at scene start (typically zero). No new energy enters the modal subsystem.
- `eta = 1`: plates move. Across the entire run, the cumulative `E_modal_injected ≤ cumulative E_loss` to within floating-point. Plot both curves on the same axes.
- Sanity vs. original DCR (Stage 5 path): plates move in the *same direction* at the *same impact frames*. Amplitudes will differ — the two methods scale impulses differently. Log the observed amplitude ratio and discuss in `docs/stageE3.md`.

Commit: `stageE3-passive-injection`.

---

## Stage E4 — Multi-contact aggregation + monotone dissipation

**Goal.** Empirically verify §8 (single global bound per step) and §3/§9 (monotone dissipation without input).

### E4.1 Multi-contact test

Synthetic scene: two rigid balls dropped simultaneously onto the same elastic slab, exactly in phase, contacting at different surface points. Run two variants:

- **Per-contact-bounded (incorrect):** apply `alpha_1 * s_1` then `alpha_2 * s_2` as two sequential bounded updates, each with its own copy of `E_max`.
- **Aggregate (correct, Stage E3):** one update with `s_total = s_1 + s_2` and one `alpha`.

Plot `E_modal_injected` vs `cumulative E_loss` for both. The aggregate path stays at or under the line; the per-contact path can cross it (by up to a factor of `m` for `m` simultaneous contacts).

### E4.2 Monotone dissipation

Scene where injection happens once at t = 0 and no further contact impulses occur (one ball hits the slab and bounces clear). With any positive Rayleigh damping,

```
E_modal(t_{k+1})  ≤  E_modal(t_k)        for all k ≥ k_impact
```

Assert this in a test. Log `E_modal` at every modal sub-step (not just rigid step) — the sub-step plot will show the smooth decay; the rigid-step plot may alias.

### E4.3 Acceptance criteria

- Plot in `docs/stageE4/`: `E_modal_injected` vs `cumulative E_loss` showing per-contact (over-budget) and aggregate (under-budget) curves side by side.
- Plot: `E_modal(t)` monotonically non-increasing after the last impact, with no upward excursions.
- Unit test asserting `E_modal[k+1] ≤ E_modal[k] + 1e-12` for every sub-step `k` after the last contact.

Commit: `stageE4-aggregate-and-dissipation`.

---

## Stage E5 — η sweep on the "Dinner is served" scene

**Goal.** Reproduce the user-facing demo with the passive injection mechanism, swept over η.

### E5.1 Scene

Same as Stage 7.1 of `dcr_implementation_prompt.md`: table slab (modes precomputed) + rigid plates/cups + dropped pot. Reuse the existing scene file.

### E5.2 Parameter sweep

`η ∈ {0.0, 0.1, 0.3, 0.5, 1.0}`. For each value, render an MP4 to `docs/stageE5/dinner_eta_<value>.mp4`. Also produce a single-frame 5-panel strip image showing one fixed time post-impact across all η values.

### E5.3 Energy invariant across the whole sim

Per rigid step `k`, compute
- `dE_modal_injected_k` — `E_modal` *immediately after the kick* minus `E_modal` *immediately before the kick* (always ≤ `E_max` by construction).
- `dE_loss_k` — `E_loss` this step.

Cumulative sums `I_K = Σ_{k=0..K} dE_modal_injected_k` and `L_K = η · Σ_{k=0..K} dE_loss_k`. Assert across the whole run:

```
I_K  ≤  L_K  +  ε_tol            for every K
ε_tol  =  1e-9 · E_rigid(0)
```

Plot `I_K` and `L_K` on the same axes. The first curve must stay at or under the second.

### E5.4 Acceptance criteria

- Five MP4s in `docs/stageE5/`.
- One 5-panel strip image.
- One energy-invariant plot, no violations.
- A `docs/stageE5.md` of ≤ one screen: what changes visually as η goes from 0 to 1, where the response saturates, where it looks unphysical.

Commit: `stageE5-eta-sweep`.

---

## Stage E6 (optional stretch) — Modal sound energy bound (log-only)

**Goal.** Implement foundation §10 as a logged scalar bound. **No audio synthesis.** No `.wav` files. No PortAudio. We are checking the energy inequality, not making sound.

### E6.1 Per-mode dissipation rate

At each modal sub-step,

```
P_diss_i  =  2 ζ_i ω_i q̇_i^2
E_diss    =  Σ_i  Σ_k  T · P_diss_i^(k)
```

Also compute `E_diss` robustly as `max(0, E_modal_before_step - E_modal_after_step)` for cross-check.

### E6.2 Acoustic radiation coefficient

Per mode, `ρ_i ∈ [0, 1]`. Default `ρ_i = 0.1` for all modes. Define the synthetic acoustic energy budget

```
E_sound  ≤  Σ_i ρ_i · E_diss_i
```

### E6.3 Acceptance criteria

- Run the Dinner scene with E6 logging enabled. Assert `E_sound ≤ E_diss ≤ E_modal_total` throughout the run.
- Three-line plot in `docs/stageE6/`: cumulative `E_sound`, cumulative `E_diss`, cumulative `E_modal_injected`. Ordering must hold pointwise.
- One-screen `docs/stageE6.md` stating: this is an energy bound, not an audio signal; future work would be to map `(q_i, q̇_i, ρ_i)` to a perceptual gain `g_i` and synthesize `p(t) = Σ g_i q̇_i(t)` (foundation §10), with `g_i` normalized so that emitted acoustic energy stays inside the budget.

Commit: `stageE6-sound-bound`.

---

## Claims to make and claims to avoid (foundation §13, §14)

When writing `README.md` and the per-stage docs:

**OK to claim.**
- Modal injection is energy-bounded and passive.
- Without new impact energy, the modal subsystem dissipates monotonically.
- Transfer efficiency `η ∈ [0, 1]` is artist-controllable under a hard energy ceiling.
- The cost per step is one basis evaluation + a handful of dot products and one scalar `α` computation.
- Sound (if added later) can be bounded by dissipated modal energy.

**Do NOT claim.**
- "The full solver is unconditionally stable." It is not. Stability is the rigid solver's responsibility; this follow-up only guarantees the *injection step* is passive.
- "The synthesized sound is physically accurate." Even with Stage E6, the sound would be *synchronized and energy-consistent*, not physically faithful.
- "Restitution ε = 1 implies zero vibration is physically correct." Under this first-order dissipated-energy-funded model, yes — but that underestimates reversible elastic vibration. State the model assumption alongside the claim.

---

## Default parameter values

| Parameter | Default | Source / notes |
|-----------|---------|----------------|
| `eta` transfer efficiency | 0.3 | sweep in Stage E5 |
| `rho_i` acoustic coefficient | 0.1 (all modes) | placeholder, Stage E6 |
| `eps_tiny` (`a < ε` branch) | `1e-18` | numerical floor for division |
| `ε_tol` energy invariant | `1e-9 · E_rigid(0)` | Stage E5 assertion |
| Sub-step rate `T` | `π / (2 ω_max)` | unchanged from DCR Stage 4 |

---

## Quick reference: every foundation equation in one place

| Section | Quantity | Where used |
|---------|---------|-----------|
| §1 | `E_loss = max(0, E_rigid_pre - E_rigid_post)` | Stage E0, E3 |
| §1 | `E_max = η · E_loss` | Stage E3 |
| §2 | `E_modal = ½ q̇^T q̇ + ½ q^T Ω^2 q` | Stage E0 |
| §3 | `dE_modal/dt ≤ 0` w/o input | Stage E4 |
| §4 | `s = Φ(x_c)^T j` | Stage E1 |
| §5 | `ΔE_modal(α) = α b + ½ α² a` | Stage E2 |
| §6 | `α* = (-b + √(b² + 2 a E_max)) / a` | Stage E2 |
| §7 | `q̇_new = q̇_old + α s` | Stage E3 |
| §8 | `s_total = Σ_k Φ(x_k)^T j_k`, single global α | Stage E3, E4 |
| §9 | `E_diss = max(0, E_modal_before - E_modal_after)` | Stage E4, E6 |
| §10 | `E_sound ≤ Σ ρ_i E_diss_i` | Stage E6 |
| §15 | **Core boxed inequality** | every injection-touching docstring |

---

## Working-rhythm reminders

- One stage at a time. Never start `E(N+1)` before `EN` passes acceptance.
- Every modal-stepper or injection edit cites foundation §15 in its docstring.
- Every deviation from `dcr_implementation_prompt.md` carries a `# DEVIATION:` comment.
- If a stage seems too easy: re-read the foundation section. The cross term `b` in §5 is the most common thing to forget.
- If a stage seems impossible: foundation §14 ("claims to avoid") usually means a hand-wave is necessary. Pick the defensible simplification and document it.
