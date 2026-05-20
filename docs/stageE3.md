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
