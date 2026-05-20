# DCR — Distant Collision Response

A from-scratch Python reproduction of:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

The goal is to reproduce the core DCR method: modal-path response for small objects, spatial-attenuation path for large objects, with qualitative ground-truth comparison.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Run

Run all tests:

```bash
uv run pytest tests/ -v
```

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
uv run python scripts/run_stage6.py            # Default: β=0.5 (shell-like)
uv run python scripts/run_stage6.py --beta 1   # Volume-like attenuation
uv run python scripts/run_stage6.py --beta 2   # Strong decay
```

### Viewer

Launch a scene in polyscope:

```bash
uv run python scripts/run_viewer.py scenes/test_box.py
```

## Tech stack

- **numpy** / **scipy** — linear algebra, sparse FEM assembly, eigenproblems
- **warp-lang** (CPU) — hot inner loops
- **polyscope** — 3D visualization

## Project structure

```
dcr/
  geom/      Mesh data structures, OBJ I/O, procedural generators
  rigid/     Rigid body simulator (Stage 1)
  fem/       Linear FEM (Stage 2)
  modal/     Eigenproblem + IIR filters (Stages 3-4)
  dcr/       DCR coupling layer (Stages 5-6)
  viewer/    Polyscope wrapper
scenes/      Scene definitions
scripts/     Entry points
tests/       pytest tests
```
