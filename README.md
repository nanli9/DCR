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
uv run pytest tests/ -v          # Stage tests + AVBD tests (87 in tests/avbd/)
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

* **Iteration-invariant overlay/bare ratio**: 8.55× → 7.64× across
  iter ∈ {4, 8, 16, 32}, CV ≈ 5 %. Matches the spec's `ω·h ≈ 7` Section
  8 prediction.
* **Physical static sag**: q deflects 5.9 mm under the impactor at
  iter=4; the same probe sitting at distance feels that deflection
  through `U` — post-fix DCR sees a rigid shelf and gives 0.
* **Energy cap (item 3) + receiver cooldown (item 4)** keep the
  cumulative injected KE under `η · E_src` (η = 0.95) across the full
  run; rest-impactor pump test injects < 0.2 % of the drop-case
  cumulative.
* **Step-time regression** from disabling CUDA-graph capture when the
  iteration hook is wired: 2.5× (1.53 → 3.80 ms/step at iter=4).

Soft spot, surfaced and documented:

* The overlay is a bolted-on injection layer. A self-feedback loop
  (probe lands → r̃ → probe kicked again) is suppressed by the
  high-pass + cooldown + energy cap but not absent by construction.
  The Path-B 1-D toy in `scripts/path_b_1d_toy.py` shows the loop and
  the energy pump vanish if you instead sub-step the *coupled* contact
  solve against `x_s(q)` — 0 injection events across 5 s, energy bounded
  by modal damping alone.

Six follow-up gates, all closed:

| # | item | script | result |
|---|------|--------|--------|
| 1 | h/T unit-chain audit | `scripts/audit_overlay_h_t.py` | 0.00 % closed-form error |
| 2 | rest-impactor pump | `scripts/run_rest_impactor_pump_test.py` | < 0.2 % of drop case |
| 3 | energy cap | in `reduced_support_solve.py` (`# Item (3)`) | invariant test green |
| 4 | receiver cooldown | in `reduced_support_solve.py` (`# Item (4)`) | dedicated test green |
| 5 | ρ_q principled sweep | `scripts/run_rho_q_sweep.py` | auto = sweet spot |
| 6 | Path-B 1-D toy probe | `scripts/path_b_1d_toy.py` | 0 injection, E bounded |

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
