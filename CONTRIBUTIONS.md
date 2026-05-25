# Contributions Beyond the Original DCR Paper

This repo reproduces **Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* CGF 39(8), SCA 2020** (PDF at `reference/DCR_SCA2020_preprint.pdf`) and then extends it. This document lists what is original to this codebase and the math underpinning it.

> Build prompts and the full math foundation live in `prompts/`. This file is the executive summary.

---

## What the paper provides (for context)

- **Rigid-body contact pipeline.** Schur-complement linear system (paper Eq. 2), PGS solver, normal + Coulomb friction.
- **Modal DCR.** Project full contact impulse onto a precomputed modal basis and drive a forced damped IIR step (paper Eq. 10) on each mode; reconstruct surface deformation by basis expansion.
- **Spatial DCR.** For large bodies where modal eigenmodes lose resolution, propagate a localized deformation field along a heat-method geodesic from the contact point.
- **Distant velocity response.** At contact points where the resolved λ is small (the rigid solver says "no impact" but the elastic surface has deformed into the body), inject a normal velocity `Δv = d_max / h` to the rigid body (paper Eq. 12) so it visibly bounces away.

This repo reproduces all of the above on CPU-only Python (`numpy` + `scipy.sparse` + `polyscope`, `warp-lang` for hot loops), one stage per branch (`stage1-rigid` … `stage7-scenes`).

---

## Contributions of this repo beyond the paper

### 1. Passive, energy-bounded modal injection (this follow-up's core)

The paper's modal step treats the projected impulse as a *forced* IIR input (Eq. 10) with no global accounting against the rigid body's energy budget. This repo replaces that with a **velocity-level kick to `q̇` funded by the rigid-body kinetic-energy loss**, capped by a quadratic passivity bound so that

> Cumulative modal energy injected ≤ `η ·` cumulative rigid energy lost, for `η ∈ [0, 1]`, **globally over every contact in every step**.

- **Stage E0** — `dcr/rigid/energy.py:rigid_kinetic_energy` and `dcr/modal/energy.py:modal_energy` (foundation §1, §2). Per-step bookkeeping of both reservoirs.
- **Stage E1** — `dcr/modal/passive_inject.py:project_impulse`, `aggregate_kicks` (foundation §4, §8). `s = Φ(x_c)ᵀ j` and per-body sum over multiple contacts in one step.
- **Stage E2** — `dcr/modal/passive_inject.py:passive_alpha` (foundation §6). Closed-form positive root `α* = (−b + √(b² + 2aE_max)) / a`, clamped to `[0, 1]`.
- **Stage E3** — `dcr/dcr/passive_dcr.py:PassiveDCRCoupler` and `dcr/modal/homogeneous_stepper.py` (foundation §7, §15). Replaces Eq. 10's forced IIR with `q̇ ← q̇ + α·s` followed by free damped oscillation. Every change to the modal stepper carries a `# DEVIATION:` comment citing §15.
- **Stage E4** — global aggregation: a single α per body per step covers *all* contacts (foundation §8, §3, §9). Tested with `tests/stageE4` for monotone dissipation in absence of input.
- **Stage E5** — η sweep showing the bound binds at the predicted ratio (`docs/stageE5/`).

### 2. Energy-prescribed distant-velocity modes (Versions A and B)

The paper's `Δv = d_max / h` (Eq. 12) is a length-per-step heuristic with no energy semantics. This repo adds two new modes that prescribe the kick from the same passivity budget used for the modal injection, so the rigid bounce-back becomes physically meaningful:

| Mode | Direction | Mechanism | Sets velocity for | Magnitude driver |
|------|-----------|-----------|-------------------|------------------|
| `dcr` (paper Eq. 12) | smooth contact normal | linear COM kick | translation only | `d_max / h` (kinematic) |
| `energy_prescribed` (Version A) | **deformed** normal `n′` | linear COM kick | translation only | `√(2·E_target/m)` (energy budget) |
| `energy_prescribed_point_impulse` (Version B) | deformed normal `n′` | **true point impulse** `J = m·v` | translation + rotation | quadratic γ\*\_B from energy budget |
| `energy_prescribed_patch` (Patch reformulation) | deformed normal `n′` at patch centroid `x̄` | point impulse `λ = K_total⁻¹·Δv_des` at `x̄` (clustered contacts) | translation + rotation | **modal velocity `v_f = Φ(x̄)·q̇`**; energy budget is a passivity *limit*, not a driver |

A vs B vs Patch comparison: same direction primitive (`n′`), different magnitude philosophy. A and B consume `β · E_available` to drive magnitude; Patch is driven by the support's actual modal velocity, with `β · E_modal_reservoir` as a passivity ceiling. All three use the same modal injection step (Section 1) for the slab side. Details: `docs/distant_velocity_modes.md`.

### 3. Deformation-aware contact frame

`dcr/dcr/deformed_normal.py:compute_deformed_normal` reconstructs the local elastic surface normal at the contact point from the current modal state and applies the kick along that direction instead of the rest-pose normal. This was originally the goal of a separate "tilt DCR" coupler; Version B replaces that path more cleanly (single impulse instead of normal-kick + tangential-correction with hand-tuned caps), and Version A now uses the same primitive too so its only difference from B is the impulse mechanism.

### 4. Global rigid-energy bound across all DCR kicks per step

`DCRWorld.enforce_rigid_energy_bound = True` aggregates the predicted ΔKE from every DCR distant velocity assignment in a step and uniformly scales them so the total stays ≤ `η · E_rigid_loss`. The cap binds rarely on the paper-baseline `dcr` mode (the Eq. 12 kick is usually small enough on its own) and binds often on the energy-prescribed modes when `β` is pushed high — both behaviors are documented in `docs/distant_velocity_modes.md`.

### 5. Patch-based reformulation (`energy_prescribed_patch`)

Versions A and B both keep the paper's "magnitude from the energy budget" architecture — they just change the direction (deformed normal) and the mechanism (linear vs point impulse). This reformulation steps back further and replaces the whole open-loop pipeline

> `E_target → invent γ → apply γ·n′ at the contact`

with a **passivity-limited moving deformable support**:

> `modal deformation defines a moving support → solve a contact-consistent velocity correction → project to Coulomb cone → scale by passivity`

Implemented as a fourth `--mode energy_prescribed_patch`, coexisting with the other three:

- **Contact clustering** — `dcr/dcr/contact_patch.py:cluster_contacts_by_body_pair` groups simultaneous contacts on the same body pair into a single patch; `build_patch` computes the weighted centroid `x̄`, the averaged rest normal `n̄_rest`, and per-body lever arms `r̄_a, r̄_b` (clamped to body half-extents). Replaces per-contact response with a single response point per body pair, killing the corner-migration feedback loop that destabilises Version B.
- **Bilateral velocity-matching solve** — `_compute_distant_response_patch` in `dcr/dcr/passive_dcr.py`:
  - `v_f = Φ(x̄)·q̇` modal velocity at the patch centroid (snapshotted right after the kick, before `step_n` decays it).
  - `Δv_des = v_f − v_p` desired velocity correction at the contact.
  - `λ = (K_body + Φ·Φᵀ)⁻¹ · Δv_des` — the **full 3×3 contact effective mass `K_total`** combining the rigid body's `K_body = (1/m)I + [r̄]_×·I⁻¹·[r̄]_×ᵀ` and the modal system's `Φ·Φᵀ`. Using `K_body` alone treats the modal system as an infinite-mass wall and creates a positive-feedback runaway on each modal back-reaction (verified empirically: books launched to >1 m, fixed by adding `Φ·Φᵀ`).
  - Coulomb cone projection of `λ` around the **rest normal** `n_rest` (not the deformed normal — the whole point of `n′` is to tilt λ into the lateral direction; projecting around `n′` would treat that lateral leak as "normal" and defeat its purpose).
  - Quadratic passivity scaling `s = (-a + √(a² + 2·b·E_cap))/b` with `E_cap = β · E_modal_reservoir` per patch.
- **Modal back-reaction** (Newton's third law) — after applying `λ` to the receiver body, the modal `q̇` is decremented by `Φ(x̄)ᵀ·λ`. This drains the modal reservoir at each kick instead of relying solely on Rayleigh damping. With the `K_total` solve above, the back-reaction is energy-conservative: `ΔE_total = -½·λᵀ·K_total·λ ≤ 0` (perfectly inelastic).
- **`--damping-scale` knob** — multiplies the FEM Rayleigh damping (`α₀`, `α₁`) at scene-build time. Default `1.0`. Useful for `energy_prescribed_patch` specifically because that mode keeps delivering kicks for as long as the modal reservoir has energy; bumping to `5–20` makes the elastic slab settle in <1 s instead of ringing for the full sim.

Where the formulation visibly differs from `dcr` / Versions A/B:

| scene | what's different | data |
|---|---|---|
| `ledge` | Boulder gains real rolling rotation as it sits on the deflected pedestal. Lever `r̄` is not parallel to `n_def`, so `r̄ × λ` is non-zero → physically-meaningful torque (the whole point of the formulation). | `boulder.max_tilt°`: 0° (coevoet) → 2.6° (B) → **36°** (patch). |
| `truck` | Cones / lumber rotate by the kick at the patch centroid; less violent than Version B (6× less drift) because `K_total`'s `Φ·Φᵀ` term absorbs part of each impulse into modal back-reaction. | `lumber_3.max_tilt°`: 0° → 89.7° (B, drift 2.5 m) → **50°** (patch, drift 0.16 m). |
| `shelf` | **Less successful.** Flat thin-book geometry has `r̄ ∥ n_def`, so the torque-via-lever benefit isn't exercised; Coulomb cone tangent budget accumulates and tips books over many steps. Pure-normal projection (`μ=0`) would degenerate the formulation to ≈ Coevoet's `Δv = d_max/h`. Suggests the patch formulation is the right tool for non-flat contact geometries, less so for flat thin-body scenes. |

### 6. Empirical validation infrastructure (`dcr/benchmark/`)

The first five contributions are *formulations*; this one is the harness that lets us *check whether each formulation does what we claim*. Three pieces, all under `dcr/benchmark/`:

- **Pass/fail rubric** (`dcr/benchmark/rubric.py`) — `BodyRubric` dataclass with strict tolerances (1 mm penetration, 5° tilt, 5 cm drift, 5 mm tail-y settling), `evaluate_run()` that scores a recorded trajectory per body and ANDs into a run-level PASS/FAIL. Per-body overrides relax bounds for bodies whose intended behaviour is something other than "stay still and upright" (e.g. the ledge boulder is *supposed* to roll, so its `max_tilt_deg` is raised to 90°). 17 unit tests with synthetic trajectories pin the math.

- **Per-step energy log** (`dcr/benchmark/energy_log.py`) — `EnergyLog` accumulates one `EnergyLogEntry` per `DCRWorld.step()` capturing `E_rigid_KE`, `E_modal`, `dE_rigid_loss`, `dE_modal_injected`, `α`, `η`. The `invariant_violation()` accessor measures the worst-case excess of cumulative-injected over `η · cumulative-loss` — the foundation §15 bound made concrete and testable. `DCRWorld` gets a new `enable_energy_logging` flag (OFF by default, zero overhead OFF); turning it ON appends one entry per step from inside `step()`. 14 unit tests.

- **Matplotlib plotters** (`dcr/benchmark/plots.py`) — three batch-savefig plotters (no `plt.show()`, headless Agg backend):
  - `plot_energy_timeseries`: 4-panel per-run figure — `(a)` E_rigid/E_modal state, `(b)` cumulative loss/budget/injected/extracted with the §15 bound visualised as a green ceiling line, `(c)` per-step ΔE_modal split into injection (+) and extraction (−) bars, `(d)` α over time.
  - `plot_param_sweep`: overlays cumulative-injected and E_modal across a parameter value set (β or η).
  - `plot_bj_vs_rest_comparison`: side-by-side `patch_fit` vs `barbic_james` for one (scene, mode).

Three driver scripts use this infrastructure:

| script | what it does |
|---|---|
| `scripts/analyze_patch_mode.py` | for each (scene × mode), records trajectories, runs the rubric, prints PASS/FAIL + §15 invariant, saves one energy PNG per run |
| `scripts/compare_deformed_normals.py` | for each (scene × mode), runs both `patch_fit` and `barbic_james`, saves side-by-side energy PNG, prints comparative metric table |
| `scripts/sweep_beta.py` | for each (scene × mode), sweeps β ∈ {0.1, 0.25, 0.5, 1.0}, saves overlay PNG, prints per-β peak/cumulative/invariant |

#### What the data showed

**§15 invariant holds zero-violation across all 54 sweep runs tested** (9 scenes × 6 mode/method combinations). The passivity claim is empirically validated.

Three structural findings, captured in `benchmark/PATCH_MODE_BENCHMARK.md`:

1. **BJ vs rest-normal matters specifically for `point_impulse` mode, specifically on deflecting slabs.** Cumulative energy injected is ~identical (≤ 1 %) between the two methods on every (scene, mode) pair; the win is in *temporal/spatial concentration*:

   | scene/point_impulse | drift `patch_fit` → `barbic_james` |
   |---|---|
   | shelf (flat) | 0.046 → 0.049 m (no change) |
   | truck | 2.27 → 1.25 m (1.8×) |
   | **ledge (cantilever)** | **0.43 → 0.11 m (4× reduction)** |

   The ledge energy plot shows BJ injects ~195 J in a single spike at impact (right direction immediately, minimal tangential leak); patch_fit injects ~75 J at impact + ~120 J in trailing kicks (cumulative totals match within 2 %, but the trailing kicks have larger tangential component that the rigid body absorbs as horizontal drift).

2. **β = 1.0 is a runaway regime** for the `energy_prescribed` and `point_impulse` modes. The per-step §15 bound holds, but the cascade is open-loop: higher modal kick → more rigid bouncing → larger per-step rigid loss → larger per-step budget → larger next kick. Worst case `truck/point_impulse`: cumulative injection jumps 1380 J → 13980 J as β goes 0.1 → 1.0. **Recommendation: keep β ≤ 0.5.** Patch mode does not exhibit this behaviour (it budgets from the modal reservoir, not β·E_loss — see takeaway 3).

3. **Patch mode is β-insensitive by design** — verified across all three scenes. `truck/patch` `E_modal_peak`: 1173.858 / 1173.854 / 1173.864 / 1173.860 J for β = 0.10 / 0.25 / 0.50 / 1.00, identical to 4 sig figs. The reformulation budgets from `E_modal_reservoir` (foundation §1.modal_reservoir), so β only affects modes that route through the per-contact modal-path branch — which the patch reformulation bypasses by construction.

A side-finding worth recording: the strict 1 mm penetration rubric flags the rigid baseline (`coevoet`) as failing on shelf (1.3–9.4 mm of penetration across bodies). This is rigid-solver ERP slack (`erp = 0.2`), not a DCR issue — but the rubric now makes it visible so it can be addressed independently.

### 7. Honest scope clarifications (binding per foundation §14)

The follow-up makes **no claim** of:
- audio synthesis or `.wav` output,
- exact energy preservation (only an upper bound),
- a sound-energy bound (Stage E6 would be a logged scalar, not audio; never implemented),
- replacing the paper's spatial-attenuation path with an energy-budgeted equivalent (Stage 6 remains empirical).

These boundaries are listed in `prompts/passive_modal_energy_injection_foundation.md` §13–§14.

---

## Math foundation — condensed

Full derivations are in `prompts/passive_modal_energy_injection_foundation.md` (§1–§15). The essentials:

### Reservoirs (§1, §2)

```
E_rigid  = Σ_b  ½ mᵦ ‖vᵦ‖² + ½ ωᵦᵀ Iᵦ ωᵦ                  (rigid kinetic energy)
E_modal  =  ½ q̇ᵀ q̇ + ½ qᵀ Ω² q                            (modal energy, mass-normalized modes)
```

### Contact-impulse projection (§4, §8)

For each contact `k` at surface point `x_k` with rigid-body impulse `j_k`,

```
s_k     = Φ(x_k)ᵀ j_k                          (projection onto modal basis)
s_total = Σ_k s_k                              (single accumulated kick per body per step)
```

### Passive scaling coefficient (§6)

Let

```
a = sᵀs,  b = q̇_old ᵀ s,  E_max = η · max(0, E_rigid_pre − E_rigid_post)
```

The quadratic energy change under the candidate kick `α·s` is

```
ΔE_modal(α) = bα + ½ a α²
```

Solve `bα + ½ a α² ≤ E_max` for the largest admissible `α`:

```
α* = (−b + √(b² + 2 a E_max)) / a                          (a > 0)
α  = clamp(α*, 0, 1)                                       (use α=1 if ΔE_full ≤ E_max)
```

### Injection (§7) — the deviation

The modal step becomes

```
q̇_new = q̇_old + α · s                                     (initial-condition kick)
(q, q̇)_{t+h} = homogeneous_step(q, q̇_new, ω, ζ, h)         (free damped oscillation)
```

> **# DEVIATION** from paper Eq. 10: injection enters as an initial-condition velocity perturbation to `q̇` followed by free oscillation, not as an impulse forcing term inside the IIR.

### Energy-prescribed distant-velocity kick (this follow-up)

Per body per step,

```
E_available = min(η · E_rigid_loss, E_modal_reservoir)     (or either alone)
E_target    = β · max(E_available, 0)                      (β ∈ [0, 1])
```

**Version A — linear COM**

```
speed = √(2 · E_target / m)
v ← v + speed · n′                                         (n′ = deformed normal)
ΔKE realized = ½ m · speed² = E_target  ✓ (exact)
```

**Version B — true point impulse**

```
J = m · speed · n′                                         (linear part)
v ← v + J/m
ω ← ω + I⁻¹ (r × J)                                        (angular part)
```

`r` is the contact-point offset from COM.

### Core inequality (§15)

The single invariant that must hold every rigid step, summed across all contacts:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ΔE_modal(α) = α · q̇ᵀs + ½ α² · sᵀs  ≤  η · max(0, E_rigid_pre − E_rigid_post)  │
│                                                                          │
│                  with   s = Σ_k Φ(x_k)ᵀ j_k                              │
└──────────────────────────────────────────────────────────────────────────┘
```

This is what the test in `tests/stageE4` asserts across full simulation runs (not sampled).

---

## Where to look in the code

| Concern | File |
|---|---|
| Rigid + modal energy | `dcr/rigid/energy.py`, `dcr/modal/energy.py` |
| Impulse projection + aggregation | `dcr/modal/passive_inject.py` |
| Passive α | `dcr/modal/passive_inject.py:passive_alpha` |
| Homogeneous modal stepper | `dcr/modal/homogeneous_stepper.py` |
| Passive coupler (full pipeline) | `dcr/dcr/passive_dcr.py:PassiveDCRCoupler` |
| Deformed normal primitive | `dcr/dcr/deformed_normal.py` (patch-fit), `dcr/dcr/deformed_normal_bj.py` (Barbič-James F⁻ᵀ) |
| Distant-velocity Versions A/B | `dcr/dcr/distant_velocity.py` |
| Patch primitive + K_total + cone + passivity helpers | `dcr/dcr/contact_patch.py` |
| Patch-mode response pipeline + modal back-reaction | `dcr/dcr/passive_dcr.py:_compute_distant_response_patch` |
| Patch-impulse application on the receiver body | `dcr/dcr/dcr_world.py:_apply_patch_impulse_dcr_velocities` |
| Global rigid-energy bound | `dcr/dcr/dcr_world.py:DCRWorld.enforce_rigid_energy_bound` |
| Per-step energy log + §15 invariant | `dcr/benchmark/energy_log.py` |
| Pass/fail rubric (per-body + run-level) | `dcr/benchmark/rubric.py` |
| Matplotlib energy plotters | `dcr/benchmark/plots.py` |
| Per-run analysis harness | `scripts/analyze_patch_mode.py` |
| BJ vs rest-normal comparison sweep | `scripts/compare_deformed_normals.py` |
| β parameter sweep | `scripts/sweep_beta.py` |
| Demo runner | `scripts/run_scenes.py` |

Per-stage notes and plots live in `docs/stageE0.md` … `docs/stageE5.md`; comparative h-sweep results in `docs/distant_velocity_modes.md`; benchmark infrastructure + findings in `benchmark/PATCH_MODE_BENCHMARK.md` with PNGs under `benchmark/plots/`.
