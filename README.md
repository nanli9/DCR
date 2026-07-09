# DCR — Distant Collision Response
### branch: `native-dynamic-constraint`

A from-scratch Python reproduction of:

> Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.

**This branch's contribution.** The paper produces the distant/modal response with a *separately integrated* modal IIR: rigid contact impulses force a reduced resonator, the peak modal displacement is read off, turned into a velocity bias `Δv = d_max/h`, and injected **one-way** into the contact RHS. This branch instead promotes the support's modal amplitude `q` to a **native, first-class constrained degree of freedom** that is co-solved with the rigid poses inside the solver — bidirectional, transpose-consistent, and energy-bounded by construction. See [The method](#the-method) below and `docs/proposal_modal_response_as_constraint.md` for the full write-up.

> The paper PDF is in `reference/`. Contributions beyond the paper and the condensed math foundation are in `CONTRIBUTIONS.md`. Build prompts and the long-form foundation live in `prompts/`.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                  # install
uv run pytest tests/ -v  # run the test suite
```

## Run the viewer

`scripts/run_native_scenes_viser.py` is the main entry point — one interactive
[viser](https://viser.studio) viewer over the full **scene × solver × material × device** matrix. It drives the native solvers directly (no coupler): drop an impactor onto a deformable support, watch the modal ring propagate through the contact network and kick distant bodies, and flip every knob live in the browser.

```bash
uv run python scripts/run_native_scenes_viser.py
# then open http://localhost:8192
```

Some starting points:

```bash
# AVBD on the shelf, GPU-resident (AVBD is device-resident on CUDA)
uv run python scripts/run_native_scenes_viser.py --scene shelf --solver avbd --device cuda:0

# The cargo network — five deformable cubes; the ring climbs the stack cube-to-cube
uv run python scripts/run_native_scenes_viser.py --scene cargo --solver avbd

# XPBD vs AVBD, same dynamic constraint, two realizations (flip live in the GUI too)
uv run python scripts/run_native_scenes_viser.py --scene cargo --solver xpbd
```

### Flags

Every flag is also a live control in the browser GUI; the CLI just sets the initial state.

| Flag | Choices (default) | What |
|---|---|---|
| `--scene` | `cargo` · `truck` · `ledge` · `shelf` · `dinner` (`cargo`) | Which scene. `cargo` is the §N2 modal-network stack; the other four are the production scenes. |
| `--solver` | `xpbd` · `avbd` (`xpbd`) | Which **native** solver. Both host `q` as a constrained DOF; no coupler, no shared segment. |
| `--kind` | `rigid` · `fem_rigid` · `abd` · `fem` (`fem_rigid`) | Impactor body model. `rigid` is the plain 6-DOF baseline (no deformation). |
| `--material` | `steel` … `rubber` (per-scene preset) | Support-slab material → Young's modulus + density. Stiffer = deflects less. |
| `--device` | `cpu` · `cuda:0` (`cpu`) | AVBD is GPU-resident on CUDA; XPBD is CPU-only for now. |
| `--modal-relax` | float (`0.7`) | Modal under-relaxation (how hard `q` chases per iteration). Higher = more visible ring. |
| `--port` | int (`8192`) | Viser server port. |

Toggle/preset flags: `--no-network` (start with the box-box modal network off),
`--no-all-cargo` (production scenes: one deformable impactor + rigid bystanders,
the legacy mode), `--ride`, `--passivity`, and the two demo presets below.

> On the production scenes the default is **all-cargo** (§N2): *every* body — plates,
> forks, cones, lumber, boulders — is a box-shaped modal cargo on the box-box
> network. That path is AVBD-native, so it routes to AVBD regardless of `--solver`.
> For a direct XPBD-vs-AVBD comparison use `--scene cargo`.

### GUI

The browser panel groups controls into **Sim** (speed), **Scene** (support
material / thickness, impactor mass / drop / launch velocity), **Reduced-modal
solver** (iterations, substeps, modal impedance, modal damping), and
**Visualization** (cube-flex + slab-deflection render exaggeration — default
`1.0` = true scale; real flex is ~1e-5 m, so raise to ~300 to see it). A
diagnostics block reports `|q_s|` (static sag), `|q_d|` (dynamic ring), substep
count, and the modal-energy-vs-loss-budget passivity ledger.

## The method

The reframing, in one line: **contact is a single constraint on the rigid pose
`z` and the modal amplitude `q` jointly**, not a rigid contact plus a one-way
bias.

- **One gap, two Jacobian blocks.** A body resting on the deformable support
  touches its *live* surface `y_rest + U_y·q`, so the contact gap
  `g(z, q) = corner_y(z) − (y_rest + U_y·q) ≥ 0` depends on both. A single
  non-negative multiplier `f` enforces it and enters the body gradient (`+J_x f`)
  and the modal gradient (`−U_y f`) with opposite signs — Newton's third law.
  The coupling is **bidirectional** (a penetration pushes the support down; a
  support deflection relieves the penetration, inside one solve) and
  **transpose-consistent**, which is the algebraic condition for the step not to
  create energy.

- **Two native solvers, no coupler.** The same constraint is realized in two
  genuinely independent solvers, both carrying `q` as a first-class DOF:
  - `avbd` — augmented-Lagrangian primal Newton; `q` is co-solved via the
    Schur-complement `q`-block (engaged-gated block-GS).
  - `xpbd` — compliant Gauss–Seidel; `q` is a compliant DOF (compliance
    `1/k_modal`), transpose-consistency automatic from the single gradient.

  There is no separately integrated IIR and no post-solve `Δv` kick.

- **Modal contact network (§N2).** With stacked/touching cargo bodies, the ring
  propagates body-to-body through the box-box contact rows — the impact on the
  support climbs a tower cube-to-cube.

- **Passivity (foundation §15).** The modal energy the ring can hold is bounded
  by the physical contact work that forced it: `E_modal ≤ η · rigid-loss`.
  AVBD's variational structure makes it **naturally passive** without a clamp;
  XPBD's fixed-low-iteration budget is **not** — its modal energy can blow up,
  and the optional clamp brings it back to a physical ring. The ledger is on by
  default in **monitor** mode (measures, physics-neutral); the clamp is opt-in.

Two demo presets make the passivity story visible:

```bash
# XPBD support path (steel shelf) at a production budget — modal energy runs
# away to ~5e4 J (scene has ~1 J). Tick "enforce passivity bound" in the GUI to
# bring it to a physical ring. (Try --solver avbd instead: the clamp does nothing.)
uv run python scripts/run_native_scenes_viser.py --inject-xpbd

# Cargo network at a starved real-time budget — the local solver under-converges
# and the HUD reads INJECTING ✗; the clamp flips it PASSIVE ✓. On AVBD this is a
# bounded ledger violation that damps, not a visual blowup.
uv run python scripts/run_native_scenes_viser.py --inject
```

Design docs: `docs/proposal_modal_response_as_constraint.md` (the pitch),
`docs/native_modal_support.md` (the monolithic `(z, q)` solve),
`docs/network/n2.md` (the modal network), `docs/all_scenes_generalization.md`
(all-cargo generalization + FEM ground truth).

## Tech stack

- **numpy** / **scipy** — dense + sparse linear algebra, FEM assembly, eigenproblems
- **warp-lang** — hot inner loops; GPU-resident device kernels for the AVBD native path (CUDA), with the numpy path kept as the parity reference
- **viser** — interactive browser viewer (the native-scenes viewer)
- **polyscope** — 3D visualization (original stage/scene scripts)
- **matplotlib** — 2D plots and GIF animation

## Project structure

```
dcr/
  geom/      Mesh data structures, OBJ I/O, procedural generators
  rigid/     Rigid body simulator (Stage 1)
  fem/       Linear FEM (Stage 2)
  modal/     Eigenproblem, IIR filters, homogeneous stepper, passive injection
  avbd/      Native solvers: the (z, q) co-solve, cargo body models, modal network
  dcr/       DCR coupling layer (modal-path, spatial-path)
  viewer/    Polyscope wrapper
scenes/      Scene definitions (reduced_*.py = native-scene builders)
scripts/     Entry points (run_native_scenes_viser.py, run_scenes.py, run_stage*.py)
tests/       pytest tests (stage1-7, stageE0-E5, avbd/, avbd_native/)
docs/        Design notes, per-stage notes, plots, benchmarks
```
