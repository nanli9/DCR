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

#### BJ vs rest-normal (full matrix, `scripts/compare_deformed_normals.py`)

Cumulative modal energy injection is ~identical between methods on every
pair (≤ 1% difference). The two interesting metrics are **drift** and
the **temporal profile of injection**.

| scene | mode | drift patch_fit → BJ | reduction |
|---|---|---|---|
| shelf | point_impulse | 0.046 → 0.049 m | none (flat slab) |
| truck | point_impulse | **2.27 → 1.25 m** | **1.8×** |
| ledge | point_impulse | **0.43 → 0.11 m** | **4×** |
| any | energy_prescribed | sub-mm both methods | none (Version A linear COM kick) |
| any | patch | identical to 4 sig figs | by design (§9.5 closes cone on rest normal) |

Two structural takeaways:

1. **BJ vs rest only matters for `point_impulse` mode.** Version A uses
   the averaged rest normal for the COM kick; patch mode closes its
   Coulomb cone around the rest normal per the §9.5 decision. Only
   `point_impulse` puts the kick along the deformed normal at the
   contact point.
2. **Even for `point_impulse`, BJ wins on deflecting-slab scenes.** On
   the flat shelf the rest normal is already correct; on the ledge
   cantilever the slab tilts measurably and BJ tracks that tilt. The
   energy plots make this concrete: on ledge/point_impulse, BJ delivers
   ~195 J in a single instant at impact (the kick is along the "right"
   direction immediately), patch_fit only ~75 J at impact and another
   ~120 J in trailing kicks (cumulative totals are within 2%). Same
   total energy, but BJ's tangential leak is much smaller → 4× less
   drift.

#### β sweep (`scripts/sweep_beta.py`, all 36 runs complete)

Full numeric matrix. **E_modal_peak [J] | ∑E_inj [J]** per cell.
§15_viol = 0.00e+00 for every cell.

| scene/mode | β=0.10 | β=0.25 | β=0.50 | β=1.00 |
|---|---|---|---|---|
| shelf/energy_prescribed | 22.76 \| 23.23 | 22.76 \| 23.23 | 22.76 \| 23.49 | **62.06 \| 68.09** |
| shelf/point_impulse | 22.76 \| 27.57 | 28.67 \| 34.63 | 37.94 \| 59.64 | **590.5 \| 1541** |
| shelf/patch | 22.76 \| 24.08 | 22.76 \| 24.11 | 22.76 \| 24.30 | 22.76 \| 24.79 |
| truck/energy_prescribed | 1180 \| 1303 | 1179 \| 1491 | 1466 \| 2033 | **2081 \| 3649** |
| truck/point_impulse | 1179 \| 1380 | 1266 \| 1814 | 1987 \| 3119 | **3967 \| 13980** |
| truck/patch | 1173.858 \| 1319 | 1173.854 \| 1333 | 1173.864 \| 1346 | 1173.860 \| 1340 |
| ledge/energy_prescribed | 195.1 \| 195.2 | 195.1 \| 195.2 | 195.1 \| 208.1 | 195.1 \| 223.8 |
| ledge/point_impulse | 195.1 \| 197.5 | 195.1 \| 200.3 | 195.1 \| 204.5 | 195.1 \| **282.6** |
| ledge/patch | 195.1 \| 197.7 | 195.1 \| 197.9 | 195.1 \| 197.9 | 195.1 \| 197.9 |

Three takeaways:

1. **β=1.0 is a runaway regime** for `energy_prescribed` and
   `point_impulse` (bolded cells). The worst offender is
   `truck/point_impulse`: 1380 J → 13980 J cumulative as β goes
   0.10 → 1.00 (10× more energy injected). The per-step §15 bound holds
   in every case — but the cascade (higher kick → more bouncing → more
   rigid loss → larger budget → larger kick) is open-loop.
   **Recommendation: keep β ≤ 0.5 for stability.**
2. **Patch mode is β-insensitive by design.** `truck/patch` shows
   `E_modal_peak = 1173.858 J` at β=0.10, `1173.854 J` at β=0.25,
   `1173.864 J` at β=0.50, `1173.860 J` at β=1.00 — identical to 4
   sig figs. Patch budgets from the modal reservoir
   (foundation §1.modal_reservoir), not β·E_loss; β only affects modes
   that route through the per-contact modal-path branch, which the
   patch reformulation bypasses.
3. **E_modal_peak is capped by the rigid impact energy.** On ledge
   (50 kg boulder dropped 0.8 m → ~196 J impact half-KE), every mode
   and every β sees the *same* peak ≈ 195.1 J. β only changes the
   cumulative integral (the trailing kicks after the initial impact);
   the spike is set by physics, not by β.

## Rigid-solver penetration diagnosis (Q2 follow-up)

The strict 1 mm penetration rubric flagged every `coevoet` shelf body as
failing (1.3–9.4 mm). Read-only ERP sweep on shelf+coevoet to
diagnose:

| `erp` | books max pen | `drop` impact pen |
|---|---|---|
| 0.20 (current) | 5.6 mm | 9.45 mm |
| 0.40 | **2.8 mm** | 9.45 mm |
| 0.60 | 4.2 mm | 9.45 mm |
| 0.80 | **36.3 mm** (overshoot — destabilising) | 9.45 mm |
| 0.95 | 35.7 mm | 9.45 mm |

Two distinct penetration sources:

1. **Impact penetration** (`drop` body, 9.45 mm) — the body advances
   `v_impact · h` into the slab in the timestep the contact is first
   detected. `h = 0.01 s`, impact speed ≈ 0.94 m/s → 9.4 mm exactly.
   **Independent of ERP.** Only `h` fixes this.
2. **Resting penetration** (books, 2.8–5.6 mm) — steady-state of
   `g·h²/erp` ± Baumgarte ringing. Minimum at `erp ≈ 0.4`; `erp ≥ 0.8`
   destabilises into 36 mm overshoot.

**Implication for the rubric:** 1 mm is structurally too tight for
PGS+Baumgarte at `h = 0.01`. Three principled options, no action taken
in this diagnosis pass:

| option | impact pen | resting pen | cost |
|---|---|---|---|
| Tighten `erp` to 0.4 + per-body-type rubric (e.g. `penetration_max_m = 0.010` for impactors, `0.003` for resting) | 9.45 mm (no change) | 2.8 mm | zero — config change |
| Halve `h` to 0.005 + keep rubric | ~4.7 mm | ~0.7 mm | 2× compute |
| Accept 1 cm as the practical bound | 9.45 mm | 5.6 mm | zero |

## Contact-causal gating — empirical evaluation

The proposal in `prompts/passive_contact_causal_modal_coupling.md` adds
three gates to the patch-mode dispatch (opt-in via `--causal-gating`,
landed in commit `d1b0405`):

1. **Contact-shell** (`gap ≤ δ_contact`, default `1e-4 m`)
2. **Closing-velocity** (`(v_f − v_p) · push_dir > v_min`, default `0.044 m/s = √(2·g·1e-4)`)
3. **Numerical cutoff** (skip when `E_modal < 1e-5 · E_peak`)

Implementation passes 328 tests including 16 new `TestCausalGating`
tests, all §15-invariant-clean.

### Finding: gates alone do not quiet visual bumping

User-reported problem: on
`truck --mode energy_prescribed_patch --beta 0.7 --deformed-normal-method barbic_james --sim-duration 15`,
slab vibration continues sub-millimetre for the full 15 s and bodies
"buzz" (350-490 zero-crossings per body in the last 5 s).

Apples-to-apples 8 s comparison (`causal_gating={off, on}`, β=0.70,
damping_scale=1.0, BJ normal):

| body | UNGATED bumps / y_range | GATED bumps / y_range |
|---|---|---|
| cone_0 | 176 / 5.6 mm | 99 / 32.8 mm |
| cone_2 | 266 / 0.8 mm | 99 / 24.7 mm |
| cone_4 | 67 / 56.9 mm | 90 / 42.3 mm |
| **lumber_1** | **137 / 8.6 mm** | **40 / 385.9 mm** |
| lumber_2 | 139 / 10.9 mm | 123 / 8.9 mm |

The gates reduce bump *count* (as designed) but **increase bump
amplitude** — sometimes catastrophically. `lumber_1` flies 386 mm above
its resting position in the gated case.

**Structural cause**: the cone projection (`λ_n ≥ 0`) already zeroes
the AWAY half of the slab's oscillation. The closing-velocity gate
zeroes some of the INTO half too. Net energy delivered per cycle is
approximately unchanged — only the **temporal concentration** changes.
Larger concentrated kicks throw bodies higher. Empirically, peak
`E_modal` is HIGHER with gating (1646 J vs 1203 J ungated) because the
back-reaction `q̇ -= Φᵀλ` fires less often → reservoir drains slower →
each gated kick is bigger.

### β-sweep with gating: smaller β is the fix

Gated × β ∈ {0.10, 0.15, 0.25, 0.50} on the truck scene (8 s sim each,
last 3 s tail):

| β (gated) | max y_range across bodies | total bumps |
|---|---|---|
| **0.10** | **3.21 mm** | 1568 |
| 0.15 | 10.6 mm | 1411 |
| 0.25 | 13.4 mm | 1025 |
| 0.50 | 102.5 mm | 1228 |
| 0.70 | 385.9 mm | ~990 |

β=0.10 with gating is the cleanest config across the entire sweep —
max body amplitude stays below 3.2 mm in the last 3 s. The trajectory
plot
`benchmark/plots/causal_gating_truck/truck_gated_beta_comparison_tail3s.png`
overlays β ∈ {0.10, 0.25, 0.70} (gated) + the ungated β=0.70 baseline
per body; the `lumber_1` subplot shows the structural failure most
clearly (red gated-β=0.70 spikes to 0.4 m; green gated-β=0.10 stays
tight near 0.18 m).

### Reviewer-defensible recipe

Two practical configurations that quiet the bumping while preserving
the §15 invariant:

| recipe | knobs | trade-off |
|---|---|---|
| **gated + small β** (preferred) | `--causal-gating --beta 0.10` | Fully principled. Each kick is small AND only fires when slab is closing into body. Limits modal-to-rigid transfer to 10% per step. |
| **gated + heavy damping** | `--causal-gating --damping-scale 10` | Works visually but `damping-scale > 1` is a cosmetic knob, not a physical material constant. Defensible only as "engineering polish for visual demos." |
| **gated + small β + light damping** | `--causal-gating --beta 0.10 --damping-scale 3` | Cleanest combination. Each mitigation does its principled job, no single knob carries the burden. |

The structural lesson: **persistent modal state requires both a per-kick
frequency rule AND a per-kick magnitude rule.** Gates alone supply
frequency; β alone supplies magnitude; either alone is empirically
insufficient on the truck scene. The proposal's "do not aggressively
quiet the slab" framing is correct in spirit (the gates are the right
*kind* of fix), but the choice of β is not optional once gating is on
— `β ≤ 0.2` is the practical cap.

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

