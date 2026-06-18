# Dynamic two-way modal contact constraint — AVBD-Native port (Stages 1–7)

End-to-end summary of porting the finalized dynamic two-way modal contact
constraint (`two_band_coupling.html`, "Approach B") into the GPU-resident
AVBD-Native solver, with **two** device-resident primals (AVBD + XPBD), three
cube materials, and CPU/GPU parity throughout.

## What was ported, and why here

The constraint carries the support's full dynamic modal state `q` (its own
inertia `M_q`, stiffness `K_q`, damping `D_q`) **inside the same contact solve**
as the bodies. The single contact multiplier that lifts a body is the reaction
that loads the mode, and the mode's inertia pushes back — the two-way loop is
structural, and the step is passive for free (backward Euler on a bounded-below
potential). No η governor, no static/dynamic split, no IIR overlay.

It was ported into **AVBD-Native** (not the twobody framework) because that
solver has real per-corner box collision + friction, CUDA-graph capture and zero
host readback — so tumbling cubes do not interpenetrate (the twobody branch's
fixed-pair +y penalty contact did). The CPU/numpy reference is kept as the
parity oracle for every device kernel (CLAUDE.md rule 6).

## Architecture

A coupler interposes on the `Solver6DOF` substep loop via three hooks
(`substep_begin` / `iteration` / `substep_end`). It treats all modal DOFs as one
**augmented** vector `Q = [q_support(r); a_cargo(k); …]` with block-diagonal
`M_q/K_q/D_q`; the per-body rigid 6-DOF blocks are unchanged. The contact's
per-row modal gradient is `[−U_y | +G_a]` — the support surface basis `U_y` and
the co-rotated cargo corner shape `G_a = n̂ᵀ·R·Φ_c`.

Two primals solve the **same** incremental potential:

| primal | module | per-iteration solve |
|--------|--------|---------------------|
| **AVBD** (Schur–Newton) | `reduced_coupled_avbd.py` | augmented modal block `M_q/h²+D_q/h+K_q` + per-body 6×6, Schur-reduced over `Q`; AL contact (λ, ρ) |
| **XPBD** (compliant Gauss–Seidel) | `reduced_coupled_xpbd.py` | per-mode modal compliant constraints (Macklin damped) + unilateral FLOOR contact, projected GS; XPBD multipliers reset per substep |

The XPBD coupler **subclasses** the AVBD coupler — it inherits the substep
caches, predictor, anchor and energy/passivity diagnostics, and overrides only
the iteration primal and the device sweep. Both are fully GPU-resident: state in
`wp.array` on `cuda:0`, the iteration loop captured into a CUDA graph, the only
host readback once per macro-step for the HUD.

## Materials

| material | body | XPBD | AVBD |
|----------|------|:----:|:----:|
| `fem`       | translation(3) + modal (world-fixed Φ_c) | ✓ | ✓ |
| `fem_rigid` | co-rotated rigid frame ⊕ modal (R·Φ_c) | ✓ | ✓ |
| `abd`       | rigid frame ⊕ 9-DOF affine, quartic V⊥ | — (→AVBD) | ✓ |

`abd`'s stiff (~255 Hz) nonlinear V⊥ is not Gauss–Seidel-stable in the substep
sweep budget (the `XPBDDynamicSystem` oracle's own note) — it routes to AVBD,
which solves V⊥ implicitly. XPBD covers `fem` and `fem_rigid`.

## Parity (CPU reference ↔ GPU-resident)

Parity is gated at the small-N horizon (machine precision; afterward q̇'s 1/h
amplification + tumbling round-off grow chaotically). Build twice (shared scipy
eigh basis), toggle `coupler.device_resident`.

| path | material | parity (n=3) |
|------|----------|--------------|
| AVBD | fem_rigid / abd / fem | ≤ 1e-11 on `q`, `a` |
| XPBD | fem / fem_rigid | **bit-identical** (`|Δq|=|Δa|=|Δx|=0.0`) |

Two-way counterfactual (both primals, CPU + GPU): `freeze_qdot` ⇒ modal KE ≡ 0
(0 mm / 0 J bystander kick); dynamic `q̇` launches the modes. Total modal energy
monotone non-increasing on free ring-down (passivity certificate logged).

## Residency + profiling (`cuda:0`, RTX 3060 Laptop)

Both couplers: `hooks_device_resident=True`, CUDA graph captured, **0 host
`synchronize_device` per step** in the hot loop. Device-resident vs
CPU-coupler-on-GPU:

| stage | material | CPU-coupler-on-GPU | device-resident | speedup |
|-------|----------|-------------------:|----------------:|--------:|
| AVBD (S3) | fem_rigid | ~40 ms | 4.4 ms | 9.2× |
| AVBD (S4) | abd       |    —   | 5.2 ms |  ~9× |
| AVBD (S5) | fem       |    —   | 4.4 ms |  ~9× |
| XPBD (S6) | fem       | 24.7 ms | 3.5 ms | 7.1× |
| XPBD (S6) | fem_rigid | 24.9 ms | 3.5 ms | 7.1× |

## Test suite

`tests/avbd_native/` — one green suite, **40 tests**:
- `test_dynamic_coupling.py` (6) — AVBD dynamic constraint + counterfactual
- `test_fem_rigid_cargo.py` (4), `test_fem_rigid_coupling.py` (5),
  `test_abd_coupling.py`, `test_fem_coupling.py` — AVBD materials + parity
- `test_xpbd_coupling.py` (12) — XPBD parity, residency, two-way, passivity,
  determinism, smoke (fem / fem_rigid), abd→AVBD routing

## Viser

- `scripts/run_native_scenes_viser.py` — live solver × material × device on the
  cargo scene (flip avbd↔xpbd to compare the two primals).
- `scripts/run_reduced_scene_viser.py` — the four production scenes
  (truck/ledge/shelf/dinner) with rigid cargo on the reduced-modal support.

## Remaining

Wiring the deformable materials into the four production scenes (their impactors
are currently rigid) is the open Stage-7 piece; the cargo scene exercises the
full solver × material × device matrix today.
