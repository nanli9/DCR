# DCR — Distant Collision Response

A from-scratch Python reproduction of:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

Plus a follow-up: **passive energy-bounded modal injection** — rigid-body kinetic energy lost during contact funds a bounded velocity kick to the modal state, with artist-controllable transfer efficiency `eta` and a hard energy ceiling `dE_modal <= eta * dE_rigid_loss`.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Run

Run all tests (67 tests):

```bash
uv run pytest tests/ -v
```

## Demo Scenes (Passive DCR)

Interactive polyscope playback. Each scene demonstrates how an impact on an elastic surface propagates vibrations to distant resting objects.

```bash
# "Dinner is served" — pot dropped on table, plates jump (paper Fig. 1)
uv run python scripts/run_stageE3.py

# eta sweep — same dinner scene at eta = 0.0, 0.1, 0.3, 0.5, 1.0
uv run python scripts/run_stageE5.py

# Truck on road — heavy truck bounces, cones shake, lumber stack topples
uv run python scripts/run_scenes.py truck

# Bookshelf drop — heavy box dropped on shelf, books topple
uv run python scripts/run_scenes.py shelf

# Cliff ledge rockfall — boulder hits ledge, balanced rocks fall off
uv run python scripts/run_scenes.py ledge
```

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
