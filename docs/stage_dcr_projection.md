# DCR Patch-Kick Contact-Compatible Null-Space Projection (6D form)

## What this fix is

Implements the doc `prompts/dcr_patch_kick_nullspace_projection_fix.md`
§6-8 as a **6D velocity-increment** M-metric projection on the patch
kick. Replaces the impulse-space variant that an earlier draft used.

The constraint `nᵀ · (J_i − J̄) · Δu = 0` depends only on Δω, so the
projection ONLY modifies the angular component — Δv passes through
unchanged. For thin bodies in flat resting contact this means:

- Linear bounce is preserved (any direction).
- Yaw (Δω ∥ n) is in the constraint null-space and is preserved —
  yaw rotation in the contact plane is contact-compatible.
- Roll/pitch (Δω in the contact plane) is projected to ≈ 0 —
  these would lift one end of the patch off the surface.

## What this fix is NOT

It does NOT make visible tilt in the `dinner_table` scene disappear.

Measured at γ = 0.99 / η = 0.6 over 4000 steps:

| Setting | max tilt | max yaw_omega | mean ρ | E_modal_inj |
|---|---|---|---|---|
| projection off | 0.838° | 0.278 | 1.000 | 25.522 J |
| projection normal | 0.838° | 0.278 | 0.998 | 25.522 J |

The macro tilt signal is unchanged because the dominant cause of
visible tilt is **not** the patch-kick spurious torque (which the
projection does correctly kill — see below). The dominant cause is
the **moving-support effect**: the slab's surface position is
`x_surface = x_rest + Σ uᵢ qᵢ`, so as the modes oscillate the slab
physically bends. AVBD's contact resolution then rotates rigid bodies
to maintain contact with the (bent) slab. That rotation accumulates
into the visible tilt regardless of whether the patch kick was applied.

The per-step verification:

- Forced projection on EVERY patch (no gate) gives the same tilt
  (0.838°) — even when the patch kick is mathematically wiped out
  every step.
- Frame-by-frame trace shows tilt accumulating on steps where the
  fork received **zero** patch kicks.

## What the projection IS doing

It still removes a large per-kick angular kick that the centroid-
impulse formulation injects on top of the moving-support effect. From
one measured fork kick:

```
L·λ:           dv = [ 0.025, −0.063, −0.0004 ]   dw = [ 5e−4, 2e−12, 2.22 ]
du_override:   dv = [ 0.025, −0.063, −0.0004 ]   dw = [ 3e−13, −3e−19, 1.3e−9 ]
```

The raw L·λ would inject 2.22 rad/s of angular velocity (≈127°/s) on
top of the body's existing motion. The 6D projection kills it to
~10⁻⁹ rad/s. Across 4000 steps, this accounts for hundreds of mrad/s
of angular kicks that no longer hit the body. The fact that this
doesn't change the **macro tilt signal** is what tells us the macro
signal is moving-support-driven.

If the demo were stripped of modal back-reaction (no `qdot -=
Φᵀ·λ_final`), the slab would not bend and the tilt would only come
from the patch kick — at which point the projection's effect would
become visible. With modal back-reaction enabled (the default), the
slab bends regardless.

## Why this matters anyway

Two reasons:

1. **Mathematical correctness.** A centroid point impulse on a thin
   flat body should not produce contact-incompatible angular motion.
   The pre-projection kick was injecting energy into a degree of
   freedom that the contact constraint forbids — that energy was
   real and was being wasted (fought against by AVBD's next solve).
   Removing it makes the kick deliver only contact-compatible
   motion, which is what the foundation §15 passivity bound was
   meant to budget.

2. **Compatibility with future moving-support changes.** If we later
   add damping or smoothing to the slab's surface deformation (the
   real fix for the visible tilt), the projection is already in
   place and will not need rework.

## How to actually damp the visible tilt

The visible tilt is driven by `γ` (modal decay). Empirically:

| γ | max tilt (proj off) | max tilt (proj normal) |
|---|---|---|
| 1.00 | 1.392° | 1.392° |
| 0.99 | 0.838° | 0.838° |
| 0.95 | 0.35°  | 0.35°  |

The right knob for visible tilt is `coupler.modal_decay_gamma`, NOT
the projection. The projection is orthogonal to that.

## Files

- `dcr/dcr/contact_projection.py` — `project_du_contact_compatible`
  (6D, default) and `project_patch_impulse_contact_compatible`
  (3D, kept as ablation). `should_project_patch` gate now admits
  N ≥ 2 (edge contacts produce rank-1 constraint, still useful).
- `dcr/dcr/distant_velocity.py` — `PatchKick.du_override` field.
  When set, the apply path in `dcr_world.py` uses Δu directly
  instead of the L·λ centroid-impulse formula.
- `dcr/dcr/passive_dcr.py:_compute_distant_response_patch` —
  6D projection inserted AFTER the §15 dissipativity guard so it
  operates on the final lam_final. The modal back-reaction
  `qdot −= Φᵀ·λ_final` is unchanged; the difference in body
  energy between `½·λᵀ·K_body·λ` and `½·Δu_overrideᵀ·M·Δu_override`
  is dissipated by the projection (preserves foundation §15).
- `dcr/dcr/dcr_world.py:_apply_patch_impulse_dcr_velocities` —
  reads `kk.du_override` when set.
- `scripts/run_scenes_avbd.py` — viser checkboxes (DCR folder):
  "null-space projection (thin bodies)" and "└ also suppress yaw".
- `scripts/record_dinner_table.py` — `--projection {off, normal,
  normal-tangent}` and `--sweep`.
- `tests/stageDCR_projection/test_projection.py` — 15 tests:
  identity, tangential removal, energy non-increase, tangent rows,
  Δv preservation, yaw preservation, roll/pitch removal, and
  6 gating cases.

## DEVIATION notes

The projection is a `# DEVIATION:` from DCR paper §9. Cited in the
inline block at the insertion site:

- Paper §9 (single-centroid patch kick — the thing being modified)
- Foundation §15 (passivity bound preserved by M-metric non-increase)
- Fix doc §6-8 (mathematical justification)

Per CLAUDE.md §3, the deviation is explicit, not silent.
