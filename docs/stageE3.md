# Stage E3 — Wire Injection into the Rigid Step

Replaces the forced-IIR injection (Stages 4/5) with the energy-bounded velocity-kick injection.

## What was added

- `dcr/modal/homogeneous_stepper.py`: Exact exponential integrator (Option A) for damped SDOF modes. Maintains explicit `(q, qdot)` state. Precomputes 2x2 state-transition matrices per mode.
- `dcr/dcr/passive_dcr.py`: `PassiveDCRCoupler` — energy-bounded DCR coupler that:
  1. Projects full contact impulse `j` (normal + tangential) onto modal basis → `s_total` (E1)
  2. Computes `alpha = passive_alpha(s_total, qdot, E_max)` (E2)
  3. Applies velocity kick `qdot += alpha * s_total` (foundation §7)
  4. Steps homogeneous stepper for `h/T` sub-steps
  5. Computes distant contact response via Eqs. 11-13 (unchanged from Stage 5)
- `dcr/dcr/dcr_world.py`: Updated to sample `E_rigid_pre/post` around the solve, compute `E_max = eta * E_loss`, and pass it to passive couplers.

## DEVIATION from paper

The injection enters as an initial-condition perturbation to `qdot`, not as an impulse forcing term inside Eq. 10 (foundation §15). The Stage 4 forced-IIR code is kept intact for comparison.

## Limitations

The energy bound applies only to the **modal-path** injection. The Stage 6 spatial-attenuation path is empirical and is **not** energy-budgeted in this follow-up.

## Acceptance results (3 tests)

- **eta=0:** No modal injection. E_modal stays at zero. Plates don't move.
- **eta=1:** Plates move. Cumulative `E_modal_injected <= cumulative E_loss` verified at every step across 500 steps.
- **Sanity vs original DCR:** Passive plates move in the same direction as original forced-IIR plates at the same impact frames. Amplitudes differ (different scaling methods).

## Add-on: γ-decay stabilizer (opt-in, # DEVIATION from §15 for γ < 1)

Multi-contact / persistent-contact scenes (e.g. the truck benchmark) excite the modal system at near-every rigid step. With pure Rayleigh damping at the paper-style coefficients (ζ ≈ 1e-3 to 1e-2 at typical ω), the persistent modal state accumulates visible ringing across many seconds. The paper sidesteps this by *resetting* `(q, q̇) ← 0` at the start of every rigid step (paper §4.5) — discarding state entirely, which dissolves any notion of cumulative modal energy and so dissolves §15.

`PassiveDCRCoupler.modal_decay_gamma ∈ [0, 1]` is a one-parameter generalization:

| γ      | Behavior                                                         | Position                                |
|--------|------------------------------------------------------------------|-----------------------------------------|
| 1.0    | Persistent `(q, q̇)`, foundation §15 main method (default)        | Main contribution                       |
| 0.95   | Mild end-of-step decay; preserves cumulative-bound semantics     | Default research mode (recommended)     |
| 0.8    | Aggressive damping; suppresses visible ringing in truck-like scenes | Robust demo mode                     |
| 0.0    | Full reset each rigid step — original-DCR-style                  | Paper-comparison ablation (limiting case) |

**Implementation.** `HomogeneousStepper.apply_rigid_step_decay()` multiplies `(q, q̇) *= γ` at the **end** of each rigid step (after `step_n()` and after `_compute_distant_response`, so the DCR effect has already read the modal displacement). Returns the dissipated energy `(1 − γ²) · E_modal_pre`, which lands on `coupler.last_E_modal_attenuation_diss` and is logged as `dE_modal_attenuation` in `EnergyLog`.

**Passivity.** The §15 invariant
`cumulative E_modal_injected ≤ η · cumulative E_rigid_loss`
is preserved for all γ ∈ [0, 1] — the operator only removes modal energy, never refunds the injection reservoir (refunding would let one rigid impact fund unlimited future kicks). Tested in `tests/stageE3/test_gamma_decay.py::test_section_15_invariant_holds_under_gamma` across γ ∈ {0.0, 0.5, 0.95, 1.0}.

**α formula under γ.** `passive_alpha()` already uses the full quadratic `α · q̇ᵀs + ½α²|s|² ≤ E_budget` with sign-aware discriminant — this stays correct for all γ ∈ [0, 1]. Only γ=0 makes `q̇_old = 0` so the linear term vanishes; for γ ∈ (0, 1) the linear "kick aligned with current motion" term still contributes (foundation §6).

**CLI.** `--modal-decay-gamma <f>` in `scripts/run_scenes.py`. Default 1.0 (no behavior change). Recommended pairings (see `CONTRIBUTIONS.md §6`):
- *Default research:* γ ∈ [0.95, 1.0], `--causal-gating`, `--beta 0.10`, `--damping-scale 3`
- *Robust demo:* γ ∈ [0.8, 0.9], `--causal-gating`, `--beta 0.10`, `--damping-scale 3`
- *Paper-comparison ablation:* `--modal-decay-gamma 0.0`

**Why this framing rather than a hard reset.** Reset-as-main would erase the follow-up's main contribution (persistent state + §15 cumulative bound on real modal energy) and leave us looking like "DCR + an energy sticker." γ as a knob keeps the persistent-state framework as the headline and includes the paper's behavior as the γ=0 endpoint of the same dissipative-modal-energy family.
