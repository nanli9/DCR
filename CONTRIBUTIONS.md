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

| Mode | Direction | Mechanism | Sets velocity for |
|------|-----------|-----------|-------------------|
| `dcr` (paper Eq. 12) | smooth contact normal | linear COM kick | translation only |
| `energy_prescribed` (Version A) | **deformed** normal `n′` | linear COM kick | translation only |
| `energy_prescribed_point_impulse` (Version B) | deformed normal `n′` | **true point impulse** `J = m·v` | translation + rotation |

A vs B is a controlled comparison: same direction `n′`, different kick mechanism. Both consume `β · E_available` where `E_available = min(η·E_rigid_loss, E_modal_reservoir)` (or either alone, per `--budget-source`). Details: `docs/distant_velocity_modes.md`.

### 3. Deformation-aware contact frame

`dcr/dcr/deformed_normal.py:compute_deformed_normal` reconstructs the local elastic surface normal at the contact point from the current modal state and applies the kick along that direction instead of the rest-pose normal. This was originally the goal of a separate "tilt DCR" coupler; Version B replaces that path more cleanly (single impulse instead of normal-kick + tangential-correction with hand-tuned caps), and Version A now uses the same primitive too so its only difference from B is the impulse mechanism.

### 4. Global rigid-energy bound across all DCR kicks per step

`DCRWorld.enforce_rigid_energy_bound = True` aggregates the predicted ΔKE from every DCR distant velocity assignment in a step and uniformly scales them so the total stays ≤ `η · E_rigid_loss`. The cap binds rarely on the paper-baseline `dcr` mode (the Eq. 12 kick is usually small enough on its own) and binds often on the energy-prescribed modes when `β` is pushed high — both behaviors are documented in `docs/distant_velocity_modes.md`.

### 5. Honest scope clarifications (binding per foundation §14)

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
| Deformed normal primitive | `dcr/dcr/deformed_normal.py` |
| Distant-velocity Versions A/B | `dcr/dcr/distant_velocity.py` |
| Global rigid-energy bound | `dcr/dcr/dcr_world.py:DCRWorld.enforce_rigid_energy_bound` |
| Demo runner | `scripts/run_scenes.py` |

Per-stage notes and plots live in `docs/stageE0.md` … `docs/stageE5.md`; comparative h-sweep results in `docs/distant_velocity_modes.md`.
