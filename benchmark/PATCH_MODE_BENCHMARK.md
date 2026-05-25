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

## Files to know

| file | role |
|---|---|
| `scripts/analyze_patch_mode.py` | the harness — analyze + sweep |
| `scripts/run_scenes.py` | scene builders + `simulate()` + CLI |
| `dcr/dcr/contact_patch.py` | patch primitives, K matrix, cone, passivity |
| `dcr/dcr/passive_dcr.py::_compute_distant_response_patch` | patch pipeline |
| `dcr/dcr/dcr_world.py::_apply_patch_impulse_dcr_velocities` | impulse apply |
| `CONTRIBUTIONS.md` §5 | written description of the patch reformulation |
| `tests/stageDV/test_contact_patch.py` | 60 unit + integration tests |

## How to run

```bash
# Full audit (15-20 min, 9 runs)
uv run python scripts/analyze_patch_mode.py

# Visual sim of a single scene/mode (with viewer)
uv run python scripts/run_scenes.py truck --mode energy_prescribed_patch \
    --damping-scale 5 --sim-duration 2.0

# Damping sweep on one scene
uv run python -c "
from scripts.run_scenes import build_truck_scene, simulate
import numpy as np
for ds in [1.0, 5.0, 20.0]:
    world, coupler, body_info, *_ = build_truck_scene(
        velocity_mode='energy_prescribed_patch', beta=0.25, damping_scale=ds)
    _, positions, _ = simulate(world, coupler, body_info, n_steps=1000)
    for name in ['cone_0', 'lumber_0']:
        xs = np.array([p[0] for p in positions[name]])
        print(f'ds={ds}  {name}  drift={float(np.abs(xs-xs[0]).max()):.4f}')
"

# Regression suite
uv run pytest tests/stageDV/ tests/stageE4/
```
