# DCR Distant Velocity Modes — Energy-Prescribed Follow-up

> **Paper-level claim (use this framing, do not drift):**
> "Replace a timestep-sensitive kinematic velocity prescription with a
> passive energy-prescribed distant response, improving timestep robustness
> of artist-facing controls while preserving passivity."
>
> NOT "Δv independent of h." Residual h-dependence through `E_available`
> is expected and acceptable; the goal is *reduced sensitivity*, not
> invariance.

## Why

The DCR paper (Coevoet et al. 2020, CGF 39(8)) prescribes the distant
separation velocity as

```
Δv = d_max / h                                                       (Eq. 12)
```

The artist tunes `d_max` — a *length* — and the simulator divides by the
timestep. At a fixed `h` this is fine, but the same `d_max` at different
`h` injects very different kinetic energy into the resting body, which
breaks artist-facing controls under timestep changes. The paper itself
flags this in §5.4. This follow-up adds two alternative modes that
prescribe the kick magnitude from an *energy budget* (so the artist's
knob has dimensionless meaning) while preserving the existing kick
direction and passivity cap.

## Modes

The mode is selected on the coupler via `PassiveDCRCoupler.dcr_velocity_mode`
(see `dcr/dcr/passive_dcr.py`). The hard rigid-energy bound is independently
toggled by `DCRWorld.enforce_rigid_energy_bound`.

| Mode (`dcr_velocity_mode`)          | Bound flag | Kick direction       | Kick mechanism                          |
|-------------------------------------|------------|----------------------|------------------------------------------|
| `coevoet`                           | (any)      | contact normal       | linear COM (existing `_apply_dcr_velocities`) |
| `coevoet` + `enforce_rigid_energy_bound=True` (≡ `bounded_coevoet`) | on | contact normal | linear COM, scaled to satisfy rigid-loss bound |
| `energy_prescribed` (Version A)     | recommended on | **deformed contact normal n′** | linear COM                       |
| `energy_prescribed_point_impulse` (Version B) | recommended on | deformed contact normal n′ | TRUE point impulse (linear + angular)  |

A vs B is a controlled comparison: same direction `n′`, only the kick
mechanism (linear-only vs point-impulse with angular) varies.

## Math

Let `E_available` be a per-step energy budget (see "Budget source"). The
artist control is

```
β = energy_response_beta ∈ [0, 1]      # dimensionless
E_target = β · max(E_available, 0)
```

### Version A — linear-only, deformed normal

```
u    = compute_deformed_normal(contact, q_history, modal)   # same primitive as B
v    = body.velocity[0:3]
γ*_A = -(v·u) + √((v·u)² + 2 E_target / m)                  # quadratic-budget root
body.velocity[0:3] += γ*_A · u
```

Realized ΔKE = `E_target` *exactly* — for any incoming `v` along or against `u`.

**`# DEVIATION` (foundation §15, paper §5.4):** the task spec proposed
`k = 1/m + (r×u)·I_inv·(r×u)`. We drop the angular term for Version A
because `_apply_linear_kick_dcr_velocities` only updates
`body.velocity[:3]` — the angular term would represent energy not
actually injected. Version B uses the full formula AND the angular kick,
restoring physical consistency.

### Version B — true point impulse, deformed contact normal

```
u    = compute_deformed_normal(contact, q_history, modal)   # n′ from modal disp
r    = contact_point - body.position                         # lever arm
v_c  = v + ω × r                                             # contact-point velocity
k    = 1/m + (r × u) · I_world_inv · (r × u)                 # inverse eff. mass (paper Eq. 17)
a    = m² · k
b    = m · (u · v_c)
γ*_B = (-b + √(b² + 2·a·E_target)) / a                       # quadratic-budget root
J    = m · γ*_B                                              # impulse magnitude
body.velocity[0:3] += (J / m) · u
body.velocity[3:6] += J · I_world_inv @ cross(r, u)
```

Realized linear + angular ΔKE = `E_target` *exactly* — for any incoming
`v` and `ω` (see `tests/stageDV/test_energy_bookkeeping.py`).

Both γ\*_A and γ\*_B are derived in `passive_modal_energy_injection_foundation.md` §16 from the same quadratic-budget principle as §6's passive α\*. The bracketed `k` is the inverse effective mass at the contact point along `n′` — the paper's Eq. 17 specialized to a normal direction.

The deformed normal `n′` is the same primitive the tilt coupler uses
(extracted into `dcr/dcr/deformed_normal.py` so both Version B and
`TiltDCRCoupler` share it). It is a *numerical heuristic*, not a derived
quantity — see the `# DEVIATION` note in that module.

### Passivity cap (post-proposal)

Both versions optionally run through a hard rigid-energy bound:

```
ΔE_total(s) = s · A + s² · B    ≤    0.999 · ΔE_loss
```

(Vector form per foundation §15 / this follow-up; see
`dcr/dcr/dcr_world.py:_bound_dcr_velocities` for scalar-dv and
`_bound_point_impulse_dcr_velocities` for linear + angular point impulses.)

The cap is OFF by default (`enforce_rigid_energy_bound=False`) to preserve
bit-for-bit the pre-follow-up "coevoet" behavior. For the two new modes,
the cap is **recommended** on.

### Deformed-normal method

The deformed contact normal `n′` (the direction Versions A and B inject
energy along) can be computed two ways, selected by
`PassiveDCRCoupler.deformed_normal_method`:

| method | mechanism | implementation | reference |
|---|---|---|---|
| `patch_fit` (default during transition) | finite-difference `n · u` across the 3 surface vertices of the contact triangle; tilt `n_rest` by the in-plane gradient; clamp to `θ_max`. Uses the peak `q` from `q_history` (paper Eq. 11 `d_max` heuristic). | `dcr/dcr/deformed_normal.py` | heuristic (this codebase) |
| `barbic_james` | analytical FEM gradient: `F = I + Σᵢ uᵢ ⊗ ∇Nᵢ` summed over the 4 vertices of the owning tet (including the interior vertex), then `n′ = normalize(F⁻ᵀ · n_rest)`. Uses the current `q` (last substep), not a peak. | `dcr/dcr/deformed_normal_bj.py` | foundation §17; **Barbič & James 2008** IEEE ToH §4.1 — `reference/BarbicJames-2008-IEEE-TOH.pdf` |

**Relationship between the two methods** — they are *not* equivalent
even at first order in `‖q‖`:

- At `q = 0`: both return `n_rest` exactly.
- For `q ≠ 0`: angular discrepancy is **linear** in `‖q‖`, set by the
  interior tet vertex's modal weight times the tangent-plane projection
  of `∇N_D`. The patch fit cannot see this contribution (the interior
  vertex's surface-triangle shape function is identically zero). On a
  fixed-corner slab the empirical coefficient is `dθ/d‖q‖ ≈ 3.85 rad/unit`
  — see `tests/stageDV/test_deformed_normal_methods.py::TestSmallQDiscrepancyScalesLinearly`.

`barbic_james` is the principled method; `patch_fit` is kept as the
default during the transition so existing scenes / tests are
bit-for-bit unchanged. Switch via the dataclass field or the
`--deformed-normal-method barbic_james` CLI flag in
`scripts/run_scenes.py`.

## Config field reference

```python
@dataclass
class PassiveDCRCoupler:
    # ... existing fields ...
    dcr_velocity_mode: str = "coevoet"
    energy_response_beta: float = 0.25
    energy_budget_source: str = "min_rigid_loss_modal"
    theta_max_deformed: float = float(np.radians(3.0))
    deformed_normal_method: str = "patch_fit"   # or "barbic_james"

@dataclass
class DCRWorld:
    # ... existing fields ...
    enforce_rigid_energy_bound: bool = False
```

### Budget source (`energy_budget_source`)

| Value                       | E_available                                         |
|-----------------------------|-----------------------------------------------------|
| `rigid_loss`                | `η · world.last_E_loss`                             |
| `modal_reservoir`           | `modal_energy(q, qdot, ω)`                          |
| `min_rigid_loss_modal` (default) | `min(η · world.last_E_loss, modal_energy(q, qdot, ω))` |

Both quantities exist in this codebase already (foundation §1 and §2);
no fallback was needed.

## How to reproduce the h-sweep benchmark

```bash
uv run python -m benchmarks.run_h_sweep \
    --modes coevoet,bounded_coevoet,energy_prescribed,energy_prescribed_point_impulse \
    --h-values 1e-3,2.5e-3,5e-3,1e-2 \
    --sim-time 1.5 \
    --beta 0.25 \
    --budget-source min_rigid_loss_modal \
    --out benchmarks/output/h_sweep.csv
```

The script writes one CSV row per `(mode, h, step)` plus a `#`-prefixed
footer with the CoV summary table.

## Latest CoV results (1.5 s sim, β=0.25, two-ball staggered scene)

> **⚠ Pre-bugfix numbers** — recorded with the older `γ = √(2 E_target / m)` /
> `J = √(2 E_target / k)` formulas that dropped the cross-term (see the
> *Corrections (2026-05)* section below). Pending regeneration when the
> `benchmarks/` directory is rebuilt on its own branch (it was removed in
> `3b7e2ee`). The relative ordering of modes is expected to be preserved
> (A still less h-sensitive than B), but the absolute mean-ΔKE values will
> shift modestly because the per-body realized energy now hits `β·E_available`
> exactly rather than being clipped post-hoc by the cap.

Metric: mean realized ΔKE per kicked body (Joules), per (mode, h) cell.
CoV = std/mean across h ∈ {1e-3, 2.5e-3, 5e-3, 1e-2}.

| Mode                                  | CoV    | Reduction vs coevoet |
|---------------------------------------|--------|----------------------|
| `coevoet`                             | 0.88   | —                    |
| `bounded_coevoet`                     | 0.88   | 0% (cap doesn't bind in this scene) |
| `energy_prescribed` (A)               | 0.24   | **−73%**             |
| `energy_prescribed_point_impulse` (B) | 0.49   | **−44%**             |

Per-cell mean ΔKE (Joules):
- `coevoet`                             : [0.00325, 0.01161, 0.00250, 0.00121]
- `energy_prescribed`               (A) : [0.1348,  0.1037,  0.1339,  0.1972]
- `energy_prescribed_point_impulse` (B) : [0.0200,  0.0210,  0.0420,  0.0639]

Version A's only h-sensitivity is through `E_available(h)`, which is mild
for this scene. Version B adds two further sources of h-dependence on top
of `E_available(h)`: (1) the deformed normal `u(q_history)` varies with
the modal-substep count (= `ceil(h/T)`), and (2) angular kicks make
trajectories diverge between modes. Both are real algorithmic properties.

## Corrections (2026-05)

The Version A and Version B magnitude formulas above were **fixed** in
this revision. The previous implementations used

```
A: γ = √(2 E_target / m)
B: J = √(2 E_target / k)
```

which treat the kick as if the body started at rest, dropping the
linear cross-term `m·(v·n′)·γ` (A) and `m·(n′·v_c)·γ` (B) that appear
whenever the receiving body already has velocity along the deformed
normal. Concretely:

- **Symptom (before fix):** per-body realized ΔKE deviated from
  `E_target` by the cross-term. The global passivity cap in
  `dcr_world.py:_bound_linear_kick_dcr_velocities` and
  `_bound_point_impulse_dcr_velocities` silently corrected by clipping —
  so the passivity bound was never violated, but `E_target` was not hit
  exactly and the cap bound more often than it should.
- **Fix:** solve the full quadratic
  `ΔKE(γ) = b·γ + ½·a·γ² = E_target` for the non-negative root
  `γ* = (-b + √(b² + 2aE)) / a`, structurally identical to `passive_alpha`
  (foundation §6). Derivation lives in foundation §16.
- **Tests:** `tests/stageDV/test_energy_bookkeeping.py` (91 cases) pins
  realized ΔKE == E_target to 1e-10 across `v·n′ ∈ {<, =, >} 0`,
  non-zero ω, non-diagonal world inertia, and various lever arms r.
  Includes regression checks that γ\*_A ≠ √(2 E_target / m) when v·n′ ≠ 0.
- **Net effect:** the cap should now bind only for genuine multi-body /
  passivity reasons, not to mask a per-body bookkeeping error. The CoV
  table above is recorded against the pre-fix formulas and will be
  re-run when `benchmarks/` is rebuilt.

## Test summary

```bash
uv run pytest tests/stageDV -v
```

| File | Count | Coverage |
|---|---:|---|
| `tests/stageDV/test_point_impulse_math.py` | 11 | Analytical algebra: inverse-effective-mass formulas, exact `½ J² k = E_target` to 1e-12 |
| `tests/stageDV/test_dcr_velocity_modes.py` | 13 | Integration: β=0 → no kick; modal-reservoir=0 → no kick; post-cap energy ≤ budget; cap rarely binds at β=0.25; CoV reduction across h; diagnostics populated; mode-string validation |

## Explicit non-claims (binding per foundation §14)

- **Not invariance** — `Δv` is NOT independent of `h`. Residual
  h-dependence through `E_available(h)` is expected and acceptable.
- **Version A and Version B have different kick mechanisms.** Both use the
  same deformed contact normal `n′` as direction. A applies a pure linear
  COM kick along `n′`; B applies a true point impulse (linear + angular)
  along `n′`. Pick by use case: A is simpler and h-stabler; B is
  physically faithful (rotation directly injected).
- **No claim of audio synthesis or sound bound** — see CLAUDE.md and
  `passive_modal_energy_injection_foundation.md` §14.

## What was removed in this follow-up

`TiltDCRCoupler` and its `--tilt` / `--tilt-coupled` CLI flags have been
deleted. Its goal — making distant bodies pick up rotation from a
deformed contact surface — is now achieved more cleanly by Version B,
which (1) uses the same deformed-normal primitive (extracted into
`dcr/dcr/deformed_normal.py`), (2) applies a single true point impulse
instead of a normal-kick + tangential-correction decomposition, and (3)
needs no hand-tuned caps (`lateral_fraction`, `dv_t_max`, `eta_t`,
`mu_dcr`).
