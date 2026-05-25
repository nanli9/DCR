# Patch-mode benchmarking / experiment infrastructure

> Snapshot taken before context compaction. As of commit `2cf1fe7` on
> branch `energy-injection`. Pick up from here when iterating on benchmark
> standards.

## What exists

- **Harness:** `scripts/analyze_patch_mode.py` — headless, no viewer required.
  Builds each scene, runs `simulate()`, reports per-body metrics in a plain
  text table. Currently main() sweeps all three scenes × {coevoet,
  point_impulse (Version B), patch} with patch using `damping_scale=5`.
- **Scenes:** `shelf`, `truck`, `ledge` (defined in `scripts/run_scenes.py`).
- **Modes:**
  - `coevoet` — paper baseline `Δv = d_max / h` (Eq. 12)
  - `energy_prescribed` (Version A) — linear COM kick along `n′`, magnitude
    from energy budget
  - `energy_prescribed_point_impulse` (Version B) — true point impulse at
    contact along `n′`, magnitude from energy budget
  - `energy_prescribed_patch` (Patch) — patch-clustered, bilateral
    `K_total = K_body + Φ·Φᵀ` solve, modal back-reaction; prompt §9
- **Recording:** `scripts/run_scenes.py::simulate()` settles 200 steps
  (impactors held static, DCR off), zeros non-impactor velocities, then
  records `times`, `positions`, `orientations` per body for N steps.

## Per-body metrics currently reported

| metric | definition | what it indicates |
|---|---|---|
| `min_y` | `min(positions[name][:, 1])` | how low the body goes |
| `max_y` | `max(positions[name][:, 1])` | how high it bounces |
| `penetration` | `SHELF_TOP - (min_y - hy)` | how far body bottom went below the slab top (`SHELF_TOP = 0.015` hardcoded; assumes flat horizontal slab) |
| `max_tilt°` | max over time of angle between body's +y axis (rotated by orientation quaternion) and world's +y | how much it tipped (90° = on its side) |
| `x_drift`, `z_drift` | `xs[-1] - xs[0]`, `zs[-1] - zs[0]` | net horizontal travel from start |

## Knobs being swept

- `--mode` — 4 modes (see above)
- `--beta` — energy budget fraction, default 0.25
- `--damping-scale` — FEM Rayleigh damping multiplier (NEW). Default 1.0;
  5–20 gives fast visual settling on the patch mode. Quantified sweep on
  truck below.
- `--deformed-normal-method` — `patch_fit` / `barbic_james`
- `--friction-cone-clip`, `--kinematic-cap` — A/B path tunings

## Findings on this baseline so far

- **Coevoet** is the clean reference (books bounce up vertically, ~0°
  tilt, no drift).
- **Version B** is too violent on thin-body scenes (90° tilt on shelf
  books; 2.7 m drift on truck lumber).
- **Patch mode at `damping_scale=1`**: also too aggressive on thin bodies
  + continuous slow drift because slab keeps ringing for 5+ seconds.
- **Patch mode at `damping_scale=5`**: drift drops ~25× (cone 1.82 m →
  0.067 m); kicks taper as modal reservoir drains.
- **Patch mode's genuine win**: ledge boulder rotates **36°** (rolling
  response from `r̄ × λ` when lever is not parallel to `n_def`) vs 0°
  coevoet / 2.6° Version B.

### Truck damping sweep (3 independent runs, identical to ~1%)

| `--damping-scale` | cone_0 drift | lumber_0 drift | lumber_3 drift | tail y_range |
|---|---|---|---|---|
| **1.0** (default) | **1.82 m** | **1.01 m** | **0.89 m** | tiny (settled) |
| **5.0** | 0.067 m | 0.038 m | 0.098 m | tiny |
| **20.0** | 0.001 m | 0.014 m | 0.010 m | ≈ 0 |

Reading: `tail_y_range` (max-min y over last 0.2s) is small for all damping
values → bodies are essentially not bouncing up-and-down at end of sim
regardless. The main effect of damping is on horizontal drift (sliding
from cone-allowed tangent kicks fed by long-decay twist modes).

## Gaps / things to formalize before this is a real benchmark

Open questions to iterate on:

1. **Reference / "ground truth":** currently we compare against `coevoet`
   as the rigid baseline, but coevoet itself is a hack. Higher-fidelity
   reference options: a high-resolution FEM run, or the paper's §5.2 SOFA
   setup if available.

2. **Acceptance criteria:** what numerical bound counts as "this mode
   works on this scene"? Example:
   ```
   max_tilt° < 5°
   AND |x_drift| < 0.05 m
   AND penetration < 1 cm
   AND modal energy invariant holds (cumulative)
   ```

3. **Scene library:** 3 scenes is thin. Candidates to add:
   - Sphere on incline (exercises rolling response)
   - Thick block on slab corner (lever ⟂ normal — patch torque region)
   - Wedge against vertical wall (n_def tilts dramatically)
   - Domino chain (sensitivity to small tangent kicks)
   - Boulder on rocking pedestal (the ledge boulder shines here already)

4. **Time budget:** each scene-mode pair takes ~1.5 min (modal
   eigenanalysis + 1500 steps). 9 pairs = 15 min for a full pass. Want
   a quick-mode (300 steps) and a full-mode option, or a `--scenes`
   flag to limit?

5. **Output format:** currently plain text table. Want CSV per run +
   combined comparison plot script (matplotlib bar chart / line plot)?

6. **Parameter sweep tooling:** sweep `damping_scale`, `beta`,
   `deformed_normal_method` etc. over a grid? Save raw trajectories
   (`.npz`) to disk for replay/visualization?

7. **Passivity invariant logging:** assert
   `cumulative ΔE_modal_extracted ≤ E_modal_reservoir` per step?
   (Foundation §15-style invariant — already enforced for INJECTION,
   not yet logged for EXTRACTION direction.)

8. **Determinism / regression baseline:** pin trajectory checksums so
   any future code change that alters output is flagged. The existing
   `tests/stageDV/test_dcr_velocity_modes.py` does this for some modes;
   could extend.

When you come back interactively, pick (1)–(8) one at a time and we turn
the diagnostic harness into a real benchmark suite.

## Status of the open questions

| Q | name | status |
|---|---|---|
| Q1 | Reference / ground truth | open |
| Q2 | Acceptance criteria | **landed** — `dcr/benchmark/rubric.py` + harness wiring (commit `4e60b76`). Strict 1 mm penetration, per-body PASS/FAIL with run AND. Surfaced that coevoet baseline itself fails (1.3–9.4 mm penetration on shelf) → rigid-solver ERP slack to address next. |
| Q3 | Scene library expansion | partially scoped — deferred until benchmark machinery stabilises. User has confirmed primitives are sufficient for fast iteration; dinner-table (complex mesh + collision proxy) is on the roadmap but not Q-blocking. |
| Q4 | Time budget | not yet formalised |
| Q5 | Output format (CSV, plots) | **landed in part** — matplotlib PNGs per run via `dcr/benchmark/plots.py` (commit `3fd7402`). CSV emission still open. |
| Q6 | Parameter sweep tooling | **landed in part** — `scripts/sweep_beta.py` (β over `{0.1, 0.25, 0.5, 1.0}`) and `scripts/compare_deformed_normals.py` (BJ vs rest) (commit `4e5a0ce`). Grid over η + damping_scale still open. |
| Q7 | Passivity invariant logging | **landed** — `EnergyLog.invariant_violation()` checks `∑ΔE_modal_injected ≤ η · ∑ΔE_rigid_loss` (foundation §15) and the harness prints it per run. |
| Q8 | Determinism / regression baseline | not yet formalised |

## Energy bookkeeping (Q5 + Q7)

`dcr/benchmark/energy_log.py` defines an `EnergyLog` that records per
step:

- `E_rigid_KE_post`        - rigid kinetic energy after the solve + DCR kicks
- `E_modal_post`           - ½‖q̇‖² + ½‖ω q‖² at step end
- `dE_rigid_loss`          - the world's per-step rigid loss (foundation §1)
- `dE_modal_injected`      - per-step modal energy delta (positive = injected,
                            negative = back-reaction extraction, patch mode)
- `alpha`                  - passive-scaling coefficient that step
- `eta`                    - transfer efficiency η

The energy plot has 4 panels:
  (a) E_rigid_KE(t), E_modal(t)            - state
  (b) cumulative ΔE_rigid_loss / η·loss / ΔE_injected / ΔE_extracted
                                            - the §15 bound visualised
  (c) per-step ΔE_modal_injected           - injection vs extraction split
  (d) α(t)                                 - when the bound is binding

### Findings from the energy plots

- **§15 invariant holds across all (scene, mode, β) tested** —
  `EnergyLog.invariant_violation()` returns 0 for every run.
- **`barbic_james` vs `patch_fit` produce near-identical energy** on the
  flat shelf/truck scenes (e.g. shelf+point_impulse: E_modal_peak 28.668 J
  vs 28.669 J). Expected — the deformed normal barely tilts from rest on
  a flat slab. The two methods should diverge measurably on the ledge
  scene where the slab cantilevers; comparison plot in
  `benchmark/plots/compare_normals_*.png`.
- **β sweep reveals a runaway regime at β=1.0**: on shelf+point_impulse,
  β=0.1/0.25/0.5 stay tightly bounded (cumulative injection 27–55 J);
  β=1.0 cascades to 1180 J. The per-step §15 bound holds in all cases,
  but at β=1 the modal kick is large enough to make the dropper rebound
  multiple times, each rebound adds more rigid loss, which raises the
  per-step budget, allowing even larger kicks. The bound is local; the
  feedback loop is not. **Recommendation: keep β ≤ 0.5 for stability.**

## Files to know

| file | role |
|---|---|
| `scripts/analyze_patch_mode.py` | per-run harness; prints rubric + saves energy PNG |
| `scripts/compare_deformed_normals.py` | BJ vs rest-normal, all scenes × modes |
| `scripts/sweep_beta.py` | β ∈ {0.1, 0.25, 0.5, 1.0} sweep, all scenes × modes |
| `scripts/run_scenes.py` | scene builders + `simulate()` + visual CLI |
| `dcr/benchmark/rubric.py` | pass/fail rubric (Q2) |
| `dcr/benchmark/energy_log.py` | per-step energy log + §15 invariant check (Q7) |
| `dcr/benchmark/plots.py` | matplotlib plotters (Q5) |
| `dcr/dcr/contact_patch.py` | patch primitives, K matrix, cone, passivity |
| `dcr/dcr/passive_dcr.py::_compute_distant_response_patch` | patch pipeline |
| `dcr/dcr/dcr_world.py` | DCRWorld + the `enable_energy_logging` flag |
| `CONTRIBUTIONS.md` §5 | written description of the patch reformulation |
| `tests/stageDV/test_contact_patch.py` | 60 patch unit + integration tests |
| `tests/benchmark/test_rubric.py` | 17 rubric unit tests |

## How to run

```bash
# Per-run analysis + energy plots (9 runs, ~15 min)
uv run python scripts/analyze_patch_mode.py

# BJ vs rest-normal comparison (18 runs, ~25 min)
uv run python scripts/compare_deformed_normals.py

# β sweep (36 runs, ~50 min)
uv run python scripts/sweep_beta.py

# Visual sim of one scene/mode (with viewer)
uv run python scripts/run_scenes.py truck --mode energy_prescribed_patch \
    --damping-scale 5 --sim-duration 2.0

# Regression
uv run pytest tests/stageDV/ tests/stageE4/ tests/benchmark/
```

Output plots all land in `benchmark/plots/` (PNGs, named by scene/mode/
parameter).

