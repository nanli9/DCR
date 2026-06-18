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

### Resting multi-body stability (XPBD)

Two corrections were needed for the XPBD primal to hold a quasi-static
multi-body scene at rest (the AVBD primal already did, via its Schur solve + AL
ρ-escalation):

1. **Live contact geometry** (`# DEVIATION`, Macklin et al. *Detailed Rigid Body
   Simulation with XPBD* 2020): the corner lever arm `r = R(qb)·off` and the
   angular Jacobian `j_ang` are recomputed from the **live** projected
   orientation each Gauss–Seidel sweep, not frozen at substep-begin. With a
   frozen `j_ang` the rotational correction applied to `qb` never feeds back
   into the re-evaluated gap `C`, so serial GS over a resting box's corners
   pumps angular momentum unboundedly (a flat resting body spun up to
   `|ω|≈185 rad/s` → flew 6.5 m before the impactor even dropped).
2. **Active-body write-back**: the coupler writes its projected pose/velocity
   back to the solver **only for bodies whose FLOOR contact went active**
   (`λ_c>0`) this substep — matching the AVBD coupler, which only writes the
   bodies in `per_body_Hx_inv`. Writing *every* tracked body (the earlier
   behavior) clobbered the solver's box-box resolution for stacked/separated
   bystanders (e.g. ledge pillars) with the free-flight predictor.

After both, XPBD pre-impact bystander drift matches AVBD to sub-mm on all four
scenes (e.g. ledge pedestal 6558 mm → 1.26 mm). Both the CPU reference and the
device kernels carry the fix and stay CPU↔GPU bit-identical.

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

`tests/avbd_native/` — one green suite, **54 tests**:
- `test_dynamic_coupling.py` (6) — AVBD dynamic constraint + counterfactual
- `test_fem_rigid_cargo.py` (4), `test_fem_rigid_coupling.py` (5),
  `test_abd_coupling.py`, `test_fem_coupling.py` — AVBD materials + parity
- `test_xpbd_coupling.py` (12) — XPBD parity, residency, two-way, passivity,
  determinism, smoke (fem / fem_rigid), abd→AVBD routing
- `test_production_scenes.py` (14) — the four scenes × solver × deformable
  material (truck/ledge/shelf/dinner): finite, bounded penetration, the impactor
  flexes + the support rings, rigid-default unchanged, **and resting bystanders
  stay quasi-static pre-impact under XPBD** (the resting-blow-up regression)

## Scenes × materials

Every reduced-modal scene now takes `solver` (avbd|xpbd) and `cargo_material`
(fem_rigid|abd|fem|None): the impactor becomes a deformable cargo cube coupled at
its contact corners (sized to its footprint, mass matched), the rigid box stays
the SAT collision proxy, bystanders rest rigid. `cargo_material=None` is the
legacy rigid impactor. Shared seam: `scenes/reduced_scene_common.py:
build_support_and_attach` (truck/ledge/shelf) + `reduced_dinner_table` directly.
XPBD uses a higher iteration budget on the many-body scenes (no ρ-escalation;
~16 iters vs AVBD's 6–10) — e.g. dinner+xpbd max penetration drops 31 mm → 1.8 mm.

## Viser

- `scripts/run_native_scenes_viser.py` — live **scene × solver × material ×
  device** (cargo + truck/ledge/shelf/dinner). The support renders as a **solid
  slab of its true thickness** (the deflected top grid extruded down), the
  deformable impactor is skinned, bystanders are boxes. Knobs mirror
  `run_reduced_scene_viser.py`: Sim (speed), Scene (support thickness, impactor
  mass / drop / launch velocity — reset to the scene preset on a scene change),
  Reduced-modal solver (iterations live, substeps / modal impedance / damping on
  rebuild), Visualization (cube-flex + slab-deflection exaggeration default 1.0 =
  true scale, slab render thickness, full vs static modal view, impactor-as-
  collision-proxy), and a two-way HUD + diagnostics block. Flip avbd↔xpbd to
  compare the primals; abd+xpbd auto-routes to AVBD.
- `scripts/run_reduced_scene_viser.py` — the four scenes with decorated
  `model/<kind>/` assets (rigid cargo; no solver/material switching).
