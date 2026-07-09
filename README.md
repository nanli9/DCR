# DCR — Distant Collision Response

A from-scratch Python reproduction of:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

The goal is to reproduce the core DCR method: a **modal-path** response for small objects (rigid contact impulses force a reduced modal resonator, whose peak displacement becomes a distant velocity bias) and a **spatial-attenuation path** for large objects, validated against a qualitative ground-truth comparison.

The pipeline is built in stages: rigid body → linear FEM → modal eigenproblem → IIR resonator → modal DCR → spatial DCR → end-to-end scenes. The paper PDF is in `reference/`.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                  # install
uv run pytest tests/ -v  # run the test suite
```

## Running

Entry points live in `scripts/` (one `run_stage*.py` per stage, plus
`run_viewer.py` for polyscope). Run any of them with `uv run python scripts/<name>.py`;
pass `--help` where a script takes arguments.

## Tech stack

- **numpy** / **scipy** — linear algebra, sparse FEM assembly, eigenproblems
- **warp-lang** (CPU) — hot inner loops
- **polyscope** — 3D visualization
- **matplotlib** — 2D plots and GIF animation (Stage 7)

## Project structure

```
dcr/
  geom/      Mesh data structures, OBJ I/O, procedural generators
  rigid/     Rigid body simulator (Stage 1)
  fem/       Linear FEM (Stage 2)
  modal/     Eigenproblem + IIR filters (Stages 3-4)
  dcr/       DCR coupling layer — modal path + spatial path (Stages 5-6)
  viewer/    Polyscope wrapper
scenes/      Scene definitions
scripts/     Entry points (run_stage1.py … run_stage7.py)
tests/       pytest tests (stage1-7)
```
