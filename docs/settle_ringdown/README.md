# Modal ring-down ("settle") — native path

**Problem.** On the native-constraint path the support's modal state is the
*live contact surface*, so after an impact the table visibly rings at its
physical decay rate — seconds under render exaggeration ("rubbery table").
DCR never shows this because its vibration is a per-impact ghost scratch
computation (paper §4.5 resets the IIR each excitation; the displacement is
never rendered or collided). The native equivalent must therefore be an
explicit, snap-free, energy-audited dissipation channel: *DCR resets a
ghost; we ring down a real state and log the dissipation.*

## Step-0 diagnosis (dinner, pot drop, viewer-parity config)

`scripts/_diag_slab_ringdown.py` — per-mode oscillation energy about the sag
reference, `E_i = ½q̇_i² + ½ω_i²(q_i − q̄_i)²` (foundation §9):

- decay is **clean** (0 re-excitation events > 2 % of peak) — a removal
  operator works; there is no pump to fight;
- the carrier is mode 4 (~80 Hz, 2.1 J), decaying ~5× faster than Rayleigh
  predicts (co-solve numerical dissipation); the *tail* modes
  (126–293 Hz, σ ≈ 1.3–3.6 s⁻¹, worst t₅% = 2.3 s) carry the seconds-long
  visible shimmer under exaggeration;
- Rayleigh (α₀ = 2.0, α₁ = 1e−5) gives the visible modes σ ≈ 1 s⁻¹ — the
  "couple of seconds" is exactly the physical parameterization.

## Mechanism (`dcr/modal/ringdown.py`)

Velocity-only ⇒ position-continuous ⇒ engaged-safe (a surface whose motion
stops can only stop pushing; no penetration created, no pops):

- **kill** — per mode, once armed, zero `q̇_i` at the first crossing of the
  slowly-tracked sag reference `q̄_i` (EMA, τ = 0.3 s; a fast/algebraic
  reference spikes under impact — the coupler-era `e80343e` lesson). At the
  crossing the mode's oscillation energy is purely kinetic, so the removal
  is exactly `½m_i q̇_i²`; the mode is dead within half its period.
- **damp** — per mode, once armed, extra viscous factor
  `exp(−ζ_extra ω_i h)` sizing total damping to ~critical (smooth cousin).

**Arm-at-injection latch** (the inverse of the rolled-back wait-for-quiet
settle, which chatter starves): the delay window re-arms whenever `E_osc`
exceeds `(1+0.5)·max(EMA(E), envelope)` + floor; the envelope is set on each
trigger and decays with τ = 0.1 s. Two latch pitfalls are covered by unit
tests because each one silently reproduces "not doing the work":

1. an absolute jump detector re-arms on the symplectic step's conservative
   energy fluctuation → never engages;
2. a naive rising-edge detector latches on the µJ settling regime and then
   misses the J-scale impact → kills fire mid-delivery.

## The delay knob is the distant-response window

The ring **is** the carrier of the distant kick: dinner plates 0.4–0.8 m
out build their hop over ~0.14 s (≈ 11 carrier periods). Measured apex vs
delay (dinner, AVBD, symplectic, 6×2, h = 1/120):

| ring-down | delay [s] | plate hop apex [mm] | D_settle [J] |
|---|---|---|---|
| off | — | 1.84 | — |
| kill | 0.05 | 1.31 | 0.91 |
| kill | 0.10 | 1.25 | 0.38 |
| kill | 0.15 | **1.84 (full)** | 0.125 |

Default `delay = 0.15 s` preserves the full response; lower it for a
stiller table at the price of range-of-effect. With the default, the
post-impact oscillation energy cliffs ~5 decades right after the window
(`docs/settle_ringdown/diag_dinner_ringdown_{off,kill}.png`), the ring
floor drops ~2 further decades, and stillness becomes
exaggeration-independent (the ring *terminates* instead of decaying).
Near-field scenes (shelf) deliver their kick in the first half-cycle, so
resting-object response there is delay-insensitive (preserved to <5 % at
25 ms in `test_kick_preserved_within_5pct`).

## Energy contract

Same as the ghost-path γ-decay (`homogeneous_stepper.apply_rigid_step_decay`):
every removed Joule is **logged** (`solver.cum_ringdown_dissipated`, HUD
"ring-down D [J]") as a foundation §9/§11 internal-dissipation channel and
**never refunded** to the §15 reservoir. The operator runs post-commit,
post-clamp, so removal is never misattributed as injection; it only ever
removes energy, so §15 and §11's `dE_modal/dt ≤ 0` are strengthened.
`test_xpbd_dinner_kill_ledger_stays_passive` asserts the active §15 ledger
stays passive with the ring-down on. `# DEVIATION:` scheduled ring-down is
in neither the paper nor the foundation — it is an artistic, strictly
dissipative operator.

## Usage

- viser: `--ringdown kill` (+ `--ringdown-delay 0.15`), or the live
  "modal ring-down" dropdown + "ring-down delay [ms]" slider in the
  Reduced-modal solver folder; HUD line "ring-down D [J] (kills=N)".
- API: `world.set_modal_ringdown("kill", delay=0.15)` after
  `enable_reduced_modal_support` (both native solvers).
- Requires the eigenbasis (diagonal `M_q/K_q/D_q`; production scenes use
  `to_eigenbasis=True`). Host/CPU path only — on CUDA-resident AVBD it is
  a silent no-op and on the XPBD device path `_substep_cpu` never runs; a
  device kernel is a follow-up (trivial: velocity-only, per-mode).

## Tests

`tests/avbd_native/test_modal_ringdown.py` (7): exact-energy kill at the
crossing + position never mutated; latch delay + re-arm on re-excitation;
damp factor bookkeeping; non-diagonal basis rejected; dinner AVBD ring
collapse + hop-apex preservation + D logged; dinner XPBD §15 ledger passive;
shelf kick preserved. Full `tests/avbd_native` suite: 185 passed (4
device-compile tests need the warp kernel cache writable — sandbox note).
