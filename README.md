# DCR — Distant Collision Response

A from-scratch Python reproduction of:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

Plus a follow-up: **passive energy-bounded modal injection** — rigid-body kinetic energy lost during contact funds a bounded velocity kick to the modal state, with artist-controllable transfer efficiency `eta` and a hard energy ceiling `dE_modal <= eta * dE_rigid_loss`.

> See `CONTRIBUTIONS.md` for the full list of contributions beyond the paper and a condensed math foundation. The paper PDF lives in `reference/`; build prompts and the long-form math foundation live in `prompts/`.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Run

Run all tests:

```bash
uv run pytest tests/ -v          # Stage tests + AVBD tests (141 in tests/avbd/)
```

## Reduced-Coordinate AVBD Support Contact (v1)

> Branch: `AVBD-Native`. Build plan in `prompts/reduced_coordinate_avbd_support_dcr_extension.md`.
> Combined audit + benchmarks in [`docs/reduced_support_v1.md`](docs/reduced_support_v1.md).

A native, inside-iteration coupling of a reduced support coordinate `q`
into AVBD: the shelf surface deflects as `x_s(q) = x_s⁰ + U·q` and the
AVBD floor anchor is rewritten between every primal/dual launch. A
two-rate transient overlay then sub-steps a modal IIR to recover the
distant peak that the implicit macro step otherwise smears.

```bash
# Decisive A/B (Section 20.1 of the spec): overlay vs bare, iter sweep.
uv run python scripts/run_reduced_support_benchmark.py --frames 120

# Realtime viewer (viser):  drop the impactor, watch the probes get
# kicked, toggle overlay / restart / rho_q sliders.
uv run python scripts/run_reduced_support_shelf_viser.py

# Headless CLI driver:
uv run python scripts/run_reduced_support_shelf.py --overlay --frames 60
uv run python scripts/run_reduced_support_shelf.py --no-overlay --frames 60
```

Headline results (h = 1/120, single-mode shelf at ω ≈ 838 rad/s, 87
tests green):

* **Physical static sag**: q deflects 5.9 mm under the impactor at
  iter=4; the same probe sitting at distance feels that deflection
  through `U` — post-fix DCR sees a rigid shelf and gives 0.
* **Energy cap (item 3) + receiver cooldown (item 4) + per-body
  physical F_n cap** keep the cumulative injected KE under `η · E_src`
  (η = 0.95) and the per-step Δv physically bounded. Probe jump
  heights drop from 16 cm (unbounded, iter=4) to < 1 cm with the cap,
  matching what a 5 g probe sitting on a thin shelf should plausibly
  experience under a 0.5 kg impactor hit.
* **Overlay/bare ratio approaches `ω·h ≈ 7` at converged AVBD**:
  ratio = 2.05 → 7.64 across iter ∈ {4, 8, 16, 32}. The spec's
  Section 8 prediction is only recoverable once AVBD itself has
  converged (high iter); at low iter, the F_n cap dominates the
  overlay magnitude.
* **Iteration sensitivity is fundamental, not removed**: at low N,
  AVBD's λ overshoots the converged contact force on fast impacts;
  the inside-AVBD q-block reflects this overshoot (`d_bare` of 5.9 mm
  at N=4 vs 0.35 mm at N=32). The cap bounds the overlay-driven
  distant Δv to a physical range, but the bare q magnitude still
  tracks AVBD's residual.
* **Step-time regression** from disabling CUDA-graph capture when the
  iteration hook is wired: ~3–6× (1.94 → 11.16 ms/step at iter=4).

Soft spots, surfaced and documented:

* The overlay is a bolted-on injection layer. A self-feedback loop
  (probe lands → r̃ → probe kicked again) is suppressed by the
  high-pass + cooldown + energy cap + per-body F_n cap but not absent
  by construction. The Path-B 1-D toy in `scripts/path_b_1d_toy.py`
  shows the loop and the energy pump vanish if you instead sub-step
  the *coupled* contact solve against `x_s(q)` — 0 injection events
  across 5 s, energy bounded by modal damping alone.
* Iteration sensitivity from AVBD's own un-convergedness at low N
  propagates into the inside-AVBD q-block's `d_bare`. We don't cap
  the q-block (would distort the AL gradient and break coupling), so
  `q_max` itself remains iteration-sensitive. The downstream overlay
  Δv is bounded by the per-body F_n cap so the user-visible probe
  motion stays physical regardless of N.

Six follow-up gates, all closed:

| # | item | script | result |
|---|------|--------|--------|
| 1 | h/T unit-chain audit | `scripts/audit_overlay_h_t.py` | 0.00 % closed-form error |
| 2 | rest-impactor pump | `scripts/run_rest_impactor_pump_test.py` | < 0.2 % of drop case |
| 3 | energy cap | in `reduced_support_solve.py` (`# Item (3)`) | invariant test green |
| 4 | receiver cooldown | in `reduced_support_solve.py` (`# Item (4)`) | dedicated test green |
| 5 | ρ_q principled sweep | `scripts/run_rho_q_sweep.py` | auto = sweet spot |
| 6 | Path-B 1-D toy probe | `scripts/path_b_1d_toy.py` | 0 injection, E bounded |

## Reduced-Coordinate Coupled AVBD (IIR exact resonator + demo knobs)

> Branch: `AVBD-Native`. Full design + benchmark in [`docs/reduced_coupled_avbd.md`](docs/reduced_coupled_avbd.md). Scene preset reference in [`docs/scenes.md`](docs/scenes.md).

The successor to the v1 overlay: a **monolithic primal Newton block** over rigid `x` and modal `q` inside the AVBD iteration loop, with `q` as a first-class primal variable in the Schur complement. The modal step is the paper's **IIR exact resonator** (Eq. 10) lifted into a *dynamic compliance* form `q = q_free + S_h(q − q_free)` — no BDF1/Newmark inside Newton, no post-fix Δv kick. **141 AVBD tests green.**

### Drift-fix v1: static / dynamic modal split (default since 2026-06-08)

The naive "feed q into the contact anchor" coupling above is **non-passive under unilateral contact**. With AVBD's floor enforced one-sidedly (λ ≤ 0, push-up only), the up-swing of a zero-mean oscillating `q` is stiffly enforced by non-penetration while the down-swing is only enforced by gravity. The result is a position-level ratchet: on **steel × 5 kg × iter=4 × sub=4**, probes sitting on the shelf drift **+108 mm upward over 5 s** — purely an artifact of the coupling, not physical behavior.

The fix splits the modal coordinate `q = q_s + q_d`:

| Component | Role | Where it lives |
|---|---|---|
| **`q_s`** algebraic static sag | Solved coupled with `x` in the Schur block. Baseline `H_{q_s} = K_q`, gradient `g_{q_s} = K_q·q_s − Σ U_y·f` | **Sole driver of the contact anchor** `floor_y_rest + U_y·q_s` |
| **`q_d`** dynamic IIR ring | Evolves once per substep through the exact resonator, forced by `F_q_dyn = F_q_total − low_pass(F_q_total)` (EMA, τ ≈ 50 ms) | **Visual only** — renders as `U·(q_s + q_d)` but never enters the contact constraint or `H_xq` cross block |

Because `q_d` never touches the anchor, the ratchet cannot form. Because `q_s` is algebraic, AVBD residual at low iter counts no longer leaks into modal kinetic energy (the failure mode of the legacy IIR commit `F_implied = S_h⁻¹·(q − q_free)`, which amplified residual by `T_h · S_h⁻¹ ≈ ω · cot(ωh/2)` — ~640× on the canonical steel scene). Impact transient is still visible because `F_q_dyn` captures the high-frequency part of the contact load and drives `q_d` to ring.

**Validation sweep** (`scripts/run_reduced_support_shelf.py`, 5 s, iter=4 × sub=4):

| Scenario | Legacy IIR-anchor | Split (default) |
|---|---:|---:|
| Steel × 0.5–2 kg | clean (−0.1 mm) | clean (−0.1 mm) |
| **Steel × 5 kg** | **+108 mm drift** | **−0.12 mm settle** ✓ |
| **Steel × 6 kg** | +152 mm | −0.13 mm ✓ |
| **Steel × 10 kg** | +354 mm | −0.15 mm ✓ |
| **Substep 16 × 5 kg** | **+1553 mm (catastrophic)** | −0.12 mm ✓ |
| Material sweep (5 kg) | mixed | all < 1 mm ✓ |
| `peak \|q_d\|` (transient ring) | n/a | 8.3e-3 ✓ |

The drift-fix is **iter-budget-independent** (legacy needed iter ≥ 8 to mask the bug at sub=4; split is clean at iter=4) and removes the non-monotonic substep resonance window (legacy: sub=4 and sub=16 both diverged; split: all four sub ∈ {2, 4, 8, 16} settle to −0.12 mm).

**Real-time cost:** ~6–10% per step at iter=4 × sub=4 (18.5 ms vs 17.3 ms on the canonical scene), shrinking to < 1 % at iter=8 × sub=4. Still real-time.

```bash
uv run python scripts/run_reduced_support_shelf_viser.py --material steel --impactor-mass 5
```

GUI: the HUD shows separate `|q_s|` (static sag) and `|q_d|` (dynamic ring) readouts, and the **Display → render mode** dropdown toggles between `q_s + q_d` (visual total, may look like penetration when q_d swings up) and `q_s only` (contact-honest, what the constraint actually sees). Implementation lives in `dcr/avbd/reduced_coupled_avbd.py` (`substep_begin_hook` / `iteration_hook` / `substep_end_hook`); design rationale + diagnostic ladder in [`~/.claude/plans/you-are-working-in-fizzy-waffle.md`](~/.claude/plans/you-are-working-in-fizzy-waffle.md).

### Two-knob recipe (most use cases)

```bash
# The 95% case: pick a scene, pick a demo style.
uv run python scripts/run_reduced_support_shelf_viser.py \
    --scene dining-table --demo-style visible

# See what's available:
uv run python scripts/run_reduced_support_shelf_viser.py --list-scenes
uv run python scripts/run_reduced_support_shelf_viser.py --list-styles
```

Scenes bundle scene geometry + impactor params. Styles bundle the demo amplification knobs. Individual `--<flag>` overrides still work on top.

| `--scene` | What | `--demo-style` | What |
|---|---|---|---|
| `research-baseline` | 5 mm shelf (current default) | `honest` | no exaggeration |
| `cutting-board` | 25 mm wood, knife impactor | `paper-figure` | 10× display exaggeration |
| `pantry-shelf` | 15 mm shelf, spice jar | | |
| `dining-table` | 30 mm hardwood (1 × 0.6 m) | | |
| `metal-plate` | 5 mm steel | | |

Once viser is running, the browser GUI exposes a "Scene rebuild" panel for swapping material / shelf thickness / impactor mass-velocity-drop parameters in place, plus live render controls (`render mode`, `display q exaggerate`, `render thickness`). The HUD reports `|q_s|` (static sag), `|q_d|` (dynamic ring), substep count, and contact-residual diagnostics.

> **Note on `shelf_thickness`:** this is the single most sensitive parameter in the whole pipeline. Bending stiffness scales as `h³`, so going from 5 mm to 30 mm cuts the peak modal response ~10× and the visible probe rise 3–5×. Full measured sweep + scaling math in [`docs/scenes.md` → "How slab thickness affects the result"](docs/scenes.md#how-slab-thickness-affects-the-result). The `shelf_thickness` (physical) and `render_thickness` (cosmetic) knobs are separate; you can have a 5 mm physical sheet that renders as a 25 mm slab.

### Architecture modes

```bash
--mode coupled_iir_modal      # IIR exact resonator (default, paper Eq. 10 + split fix)
--mode coupled_modal_static   # Quasi-static q (no dynamics)
--mode plain                  # Rigid AVBD, no reduced support
--mode old_dcr_postkick       # Legacy DCR Δv kick (ablation)
```

Two demo knobs tune the modal impedance:

| Flag | What it does |
|---|---|
| `--support-response-gain g` | Modal impedance scaling: `(Mq, Dq, Kq) ← /g`. ω, ζ invariant. |
| `--modal-damping-scale c_ζ` | Independent multiplier on Dq → ζ. Lower = longer ringdown. |

```bash
# Full sweeps:
uv run python scripts/run_coupled_material_sweep.py --frames 120
uv run python scripts/run_coupled_energy_log.py --mode coupled_iir_modal --frames 240
```

## Demo Scenes (Passive DCR)

Interactive polyscope playback. Each scene demonstrates how an impact on an elastic surface propagates vibrations to distant resting objects.

```bash
# "Dinner is served" — pot dropped on table, plates jump (paper Fig. 1)
uv run python scripts/run_stageE3.py

# eta sweep — same dinner scene at eta = 0.0, 0.1, 0.3, 0.5, 1.0
uv run python scripts/run_stageE5.py
```

### `scripts/run_scenes.py` — three scenes, three distant-velocity modes

```bash
# Default mode (`dcr`): paper Eq. 12 Δv = d_max / h
uv run python scripts/run_scenes.py truck       # heavy drops, cones shake, lumber topples
uv run python scripts/run_scenes.py shelf       # heavy box on a cantilever shelf, books topple
uv run python scripts/run_scenes.py ledge       # boulder onto a ledge, balanced rocks fall off
uv run python scripts/run_scenes.py all         # run all three back-to-back
```

Distant-velocity mode (`--mode`):

```bash
# Paper baseline (Coevoet 2020 Eq. 12) — the default
uv run python scripts/run_scenes.py shelf --mode dcr

# Version A — energy-prescribed linear COM kick along the deformed normal
uv run python scripts/run_scenes.py shelf --mode energy_prescribed --beta 0.25

# Version B — true point impulse (linear + angular) along the deformed normal
uv run python scripts/run_scenes.py shelf --mode energy_prescribed_point_impulse --beta 0.25
```

Deformed-normal method (`--deformed-normal-method`) — applies only to the `energy_*` modes:

```bash
# Default: the patch-fit heuristic (surface plane-fit on n·u).
uv run python scripts/run_scenes.py truck \
    --mode energy_prescribed_point_impulse \
    --deformed-normal-method patch_fit

# F^{-T} push-forward using FEM shape-function gradients
# (foundation §17; Barbič & James 2008 IEEE ToH §4.1).
uv run python scripts/run_scenes.py truck \
    --mode energy_prescribed_point_impulse \
    --deformed-normal-method barbic_james

# A/B run all three scenes back-to-back with the new method:
uv run python scripts/run_scenes.py all \
    --mode energy_prescribed_point_impulse \
    --deformed-normal-method barbic_james
```

Other flags:

| Flag | Default | What it does |
|---|---|---|
| `--mode <name>` | `dcr` | `dcr` \| `energy_prescribed` \| `energy_prescribed_point_impulse` |
| `--beta <0..1>` | `0.25` | Fraction of `E_available` consumed by the kick (energy_* modes only) |
| `--budget-source <name>` | `min_rigid_loss_modal` | `rigid_loss` \| `modal_reservoir` \| `min_rigid_loss_modal` |
| `--deformed-normal-method <name>` | `patch_fit` | `patch_fit` (heuristic) \| `barbic_james` (F⁻ᵀ; foundation §17). No effect when `--mode dcr`. |
| `--sim-duration <seconds>` | `2.0` (truck: `1.8`) | Simulated wallclock; `n_steps` derived as `round(duration / h)` so playback length is invariant to `h` |
| `-h`, `--help` | — | Print usage |

See `docs/distant_velocity_modes.md` for the math, the A-vs-B comparison, and h-sweep results.

## Original DCR Stages

### Stage 1 — Rigid body demos

```bash
uv run python scripts/run_stage1.py bounce    # Single box bouncing
uv run python scripts/run_stage1.py stack     # 10 stacked boxes
uv run python scripts/run_stage1.py incline   # Box on inclined plane
uv run python scripts/run_stage1.py pair      # Sphere drops onto box
uv run python scripts/run_stage1.py collide   # Two spheres colliding
uv run python scripts/run_stage1.py linked    # Two spheres linked by rod
uv run python scripts/run_stage1.py chain     # Three boxes linked by rods
```

### Stage 2 — FEM demo

```bash
uv run python scripts/run_stage2.py              # Default: 1 kg box on table
uv run python scripts/run_stage2.py --mass 5.0   # Heavier box
uv run python scripts/run_stage2.py --scale 500  # Amplify deformation display
```

### Stage 6 — Spatial attenuation DCR

```bash
uv run python scripts/run_stage6.py            # Default: beta=0.5 (shell-like)
uv run python scripts/run_stage6.py --beta 1   # Volume-like attenuation
uv run python scripts/run_stage6.py --beta 2   # Strong decay
```

### Stage 7 — End-to-end scenes and ground-truth comparison

```bash
uv run python scripts/run_stage7.py            # Dinner scene (pre-recorded playback)
uv run python scripts/run_stage7.py spatial    # Spatial attenuation (pre-recorded)
uv run python scripts/run_stage7.py compare    # DCR vs ground-truth (matplotlib)
uv run python scripts/run_stage7.py --realtime # Dinner scene, physics stepping live
uv run python scripts/run_stage7.py --save     # Save all GIFs to docs/stage7/
```

## Energy-Injection Follow-Up (Stages E0–E5)

Extends the DCR core with passive, energy-bounded modal injection:

| Stage | What | Docs |
|---|---|---|
| E0 | Energy bookkeeping (rigid + modal observables) | `docs/stageE0.md` |
| E1 | Modal velocity-kick projection (s = Phi^T j) | `docs/stageE1.md` |
| E2 | Passive scaling coefficient alpha | `docs/stageE2.md` |
| E3 | Wire injection into the rigid step | `docs/stageE3.md` |
| E4 | Multi-contact aggregation + monotone dissipation | `docs/stageE4.md` |
| E5 | eta sweep on the dinner scene | `docs/stageE5.md` |

Key properties:
- Modal injection is energy-bounded and passive: `dE_modal <= eta * dE_rigid_loss`
- Without new impacts, the modal subsystem dissipates monotonically
- Transfer efficiency `eta in [0, 1]` is artist-controllable under a hard energy ceiling
- Cost per step: one basis evaluation + a handful of dot products + one scalar alpha

## Tech stack

- **numpy** / **scipy** — linear algebra, sparse FEM assembly, eigenproblems
- **warp-lang** (CPU) — hot inner loops
- **polyscope** — 3D visualization
- **matplotlib** — 2D plots and GIF animation

## Project structure

```
dcr/
  geom/      Mesh data structures, OBJ I/O, procedural generators
  rigid/     Rigid body simulator (Stage 1)
  fem/       Linear FEM (Stage 2)
  modal/     Eigenproblem, IIR filters, homogeneous stepper, passive injection
  dcr/       DCR coupling layer (modal-path, spatial-path, passive coupler)
  viewer/    Polyscope wrapper
scenes/      Scene definitions
scripts/     Entry points (run_stage*.py, run_stageE*.py, run_scenes.py)
tests/       pytest tests (stage1-7, stageE0-E5)
docs/        Per-stage notes, plots, GIFs
```
