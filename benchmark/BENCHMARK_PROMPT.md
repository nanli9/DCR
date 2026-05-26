# DCR Follow-up Full Benchmark Suite

This document is a self-contained, executable spec for the full benchmark sweep of the DCR follow-up. Hand it to Claude Code as the prompt for a run. After all six benchmarks finish, the `benchmark/` tree below is what gets handed back for plotting.

The point of this spec is twofold:
1. Every run produces **raw per-step data** (CSV) plus **derived metrics** (JSON), in a fixed schema, in a fixed location, so plotting is purely a schema-driven operation.
2. Each benchmark has a single source of truth (a manifest JSON) listing every run that belongs to it, so the plotter can iterate without globbing or guessing.

---

## 1. Directory layout

Create exactly this structure under the repo root before any run starts:

```
benchmark/
├── BENCHMARK_PROMPT.md              # this file
├── runs/                             # raw per-step data, never overwritten
│   ├── B1_energy_conservation/
│   ├── B2_deformed_normal/
│   ├── B3_beta_sweep/
│   ├── B4_eta_sweep/
│   ├── B5_material/
│   └── B6_runtime/
├── manifests/                        # one JSON per benchmark listing all runs
│   ├── B1_manifest.json
│   ├── B2_manifest.json
│   ├── B3_manifest.json
│   ├── B4_manifest.json
│   ├── B5_manifest.json
│   ├── B6_manifest.json
│   └── MANIFEST.json                 # top-level index of the six above
├── plots/                            # plotting output (filled in later)
│   ├── B1_energy_conservation/
│   ├── B2_deformed_normal/
│   ├── B3_beta_sweep/
│   ├── B4_eta_sweep/
│   ├── B5_material/
│   └── B6_runtime/
└── logs/                             # stdout/stderr per run, for debugging
    ├── B1/
    ├── B2/
    └── ...
```

Rules:
- `runs/` is append-only once a benchmark completes. Re-running an experiment **must** write to a new subfolder with a timestamp suffix; do not overwrite.
- `plots/` is regenerated on every plotting pass; nothing under `runs/` ever depends on `plots/`.
- `logs/<Bx>/<run_id>.log` captures stdout + stderr verbatim for that run.

---

## 2. File schemas

Every benchmark writes the same three file types (with one or two optional add-ons). Field names are **mandatory and case-sensitive** — the plotter selects columns by name.

### 2.1 `<run_id>_energy.csv` — per-step energy log

One row per simulation step (i.e., per `DCRWorld.step()` call). UTF-8, comma-separated, with a header row.

| column | unit | description |
|---|---|---|
| `step` | int | step index, 0-based |
| `t` | s | simulation time at end of step |
| `E_rigid_KE` | J | total rigid-body kinetic energy (sum over all dynamic bodies) |
| `E_modal` | J | total modal energy (sum over all modal-equipped bodies) |
| `dE_rigid_loss` | J | `max(0, E_rigid_KE[k-1] - E_rigid_KE[k])` from constraint + restitution loss |
| `dE_modal_injected` | J | positive part of modal energy change due to DCR injection this step |
| `dE_modal_extracted` | J | positive part of modal energy decrease due to damping + back-reaction this step |
| `cum_E_loss` | J | running sum of `dE_rigid_loss` |
| `cum_E_budget_eta` | J | `eta * cum_E_loss` (the §15 ceiling) |
| `cum_E_injected` | J | running sum of `dE_modal_injected` |
| `cum_E_extracted` | J | running sum of `dE_modal_extracted` |
| `alpha` | — | passive scaling coefficient applied this step (NaN for paper-baseline mode) |
| `eta` | — | the η in effect (constant within a run; included per-row for plotter convenience) |
| `beta` | — | the β in effect (constant within a run) |
| `n_active_kicks` | int | number of DCR distant-velocity kicks issued this step |
| `n_active_contacts` | int | total active contacts in the rigid solver this step |

Critical: for the paper-baseline `coevoet` mode, `dE_modal_injected` and `cum_E_injected` must **still** be populated. They come from the side-channel accounting described in §6.1 below. The plotter assumes both methods log the same columns.

### 2.2 `<run_id>_trajectory.csv` — per-step body kinematics

One row per (step, body). Header:

```
step, t, body_name, x, y, z, qx, qy, qz, qw, vx, vy, vz, wx, wy, wz, tilt_deg, drift_m
```

Where `tilt_deg` is the angle between the body's current up-axis and its rest up-axis (in degrees), and `drift_m` is the horizontal (xz-plane) distance from the body's initial position. Both are convenient to precompute here so the plotter doesn't need a quaternion library.

### 2.3 `<run_id>_summary.json` — derived metrics

```json
{
  "run_id": "B2-ledge__energy_prescribed_point_impulse__barbic_james",
  "benchmark": "B2",
  "scene": "ledge",
  "mode": "energy_prescribed_point_impulse",
  "flavor": "barbic_james",
  "params": {
    "eta": 0.95,
    "beta": 0.25,
    "h": 0.01,
    "duration_s": 4.0,
    "damping_scale": 1.0,
    "restitution": 0.15,
    "material": "wood",
    "causal_gating": false
  },
  "n_steps": 400,
  "wall_time_total_s": 1.84,
  "wall_time_ms_per_step": { "mean": 4.6, "p50": 4.2, "p95": 7.1, "p99": 9.3, "max": 12.4 },
  "rubric_pass": true,
  "invariant_max_violation_J": 0.0,
  "energy_totals": {
    "cum_E_loss_final_J": 18.7,
    "cum_E_budget_eta_final_J": 17.77,
    "cum_E_injected_final_J": 12.3,
    "cum_E_extracted_final_J": 11.9,
    "E_modal_peak_J": 4.2,
    "ratio_injected_over_budget": 0.692
  },
  "injection_signal": {
    "peak_rate_W": 380.0,
    "temporal_concentration_herfindahl": 0.41,
    "spectral_centroid_Hz": 22.1,
    "n_distinct_kick_events": 8
  },
  "bodies": [
    {
      "name": "boulder",
      "mass_kg": 50.0,
      "max_tilt_deg": 36.0,
      "drift_m": 0.08,
      "max_penetration_mm": 0.7,
      "tail_y_settle_mm": 1.2,
      "cum_J_normal": 12.3,
      "cum_J_tangential": 0.4,
      "rubric_pass": true
    }
  ]
}
```

Notes on derived fields (so they're computed identically across benchmarks):

- `invariant_max_violation_J` = `max over t of (cum_E_injected[t] − eta · cum_E_loss[t])`, clamped to ≥0. Should sit at numerical noise (<1e-9) for any passive mode. Plotter uses this to colour pass/fail.
- `temporal_concentration_herfindahl` = `Σ_t (dE_modal_injected[t] / cum_E_injected_final)²` over steps where `dE_modal_injected[t] > 0`. Range `[1/N, 1]`; 1 = single-step spike, 1/N = uniform spread.
- `spectral_centroid_Hz` = magnitude-FFT centroid of the `dE_modal_injected[t]` time-series, in Hz. Use the simulation step rate (`1/h`) as the sampling rate.
- `n_distinct_kick_events` = count of steps where `dE_modal_injected[t] > 0.01 · peak_rate_per_step`.
- `ratio_injected_over_budget` = `cum_E_injected_final / cum_E_budget_eta_final`. >1 means the §15 ceiling was exceeded.

### 2.4 `<run_id>_impulse.csv` — per-contact impulse decomposition (B2 only)

One row per (step, contact_event). Header:

```
step, t, body_name, contact_x, contact_y, contact_z, J_normal, J_tangential_u, J_tangential_v, n_rest_x, n_rest_y, n_rest_z, n_deformed_x, n_deformed_y, n_deformed_z
```

This is what lets the plotter compute the tangential-to-normal leak per scene and the rest-vs-deformed normal angle distribution.

### 2.5 `<run_id>_timing.csv` — per-step wall-clock breakdown (B6 only)

```
step, t, t_rigid_solve_ms, t_modal_step_ms, t_deformed_normal_ms, t_distant_response_ms, t_total_step_ms
```

Use a monotonic clock (`time.perf_counter_ns()` in Python). Disable any per-step prints during a B6 run so I/O doesn't pollute the timings.

---

## 3. Manifest format

After each benchmark completes, write a manifest. The plotter reads only the manifest — it does not glob `runs/`.

### 3.1 Per-benchmark manifest (`manifests/B<x>_manifest.json`)

```json
{
  "benchmark_id": "B1",
  "title": "Energy conservation: paper DCR vs follow-up",
  "completed_at": "2026-05-26T14:32:11Z",
  "git_sha": "abcd1234",
  "n_runs": 6,
  "runs": [
    {
      "run_id": "B1-paper-ledge",
      "scene": "ledge",
      "mode": "coevoet",
      "flavor": "rest",
      "params": {"eta": 0.95, "beta": 0.25, "h": 0.01, "duration_s": 4.0},
      "files": {
        "energy_csv": "runs/B1_energy_conservation/B1-paper-ledge_energy.csv",
        "trajectory_csv": "runs/B1_energy_conservation/B1-paper-ledge_trajectory.csv",
        "summary_json": "runs/B1_energy_conservation/B1-paper-ledge_summary.json",
        "log": "logs/B1/B1-paper-ledge.log"
      },
      "status": "ok"
    }
  ]
}
```

`status` is one of `ok`, `failed`, `partial`. If a run failed, still include it in the manifest with `status: "failed"` and a `failure_reason` field — the plotter will skip it but flag it.

### 3.2 Top-level manifest (`manifests/MANIFEST.json`)

```json
{
  "schema_version": "1.0",
  "repo": "<your repo URL>",
  "completed_at": "...",
  "benchmarks": [
    {"id": "B1", "manifest": "manifests/B1_manifest.json", "status": "complete"},
    {"id": "B2", "manifest": "manifests/B2_manifest.json", "status": "complete"},
    {"id": "B3", "manifest": "manifests/B3_manifest.json", "status": "complete"},
    {"id": "B4", "manifest": "manifests/B4_manifest.json", "status": "complete"},
    {"id": "B5", "manifest": "manifests/B5_manifest.json", "status": "complete"},
    {"id": "B6", "manifest": "manifests/B6_manifest.json", "status": "complete"}
  ]
}
```

---

## 4. Global conventions

**Scenes:** `ledge`, `truck`, `shelf` (primary). Optional secondary: `scaffold`, `dinner`, `washing_machine`.

**Modes (use these exact strings as the CLI value and in filenames/manifests):**
- `coevoet` — paper baseline (Eq. 10 forced IIR + Eq. 12 `Δv = d_max/h`)
- `energy_prescribed` — Version A
- `energy_prescribed_point_impulse` — Version B
- `energy_prescribed_patch` — patch reformulation

**Deformed-normal flavors:** `rest`, `patch_fit`, `barbic_james`.

**Defaults (override only where the benchmark specifies):**
| param | value |
|---|---|
| η | 0.95 |
| β | 0.25 |
| h | 0.01 s |
| duration | 4.0 s |
| damping_scale | 1.0 |
| restitution | 0.15 |
| causal_gating | false |
| material | wood (E=10 GPa, ρ=500 kg/m³, ν=0.3) |
| seed | 42 (for any stochastic initial perturbation) |

**Naming:** `run_id = "B<x>-<tag>"` for headline runs (B1), otherwise `"<scene>__<mode>__<flavor>__<paramtag>"` where `paramtag` is the swept parameter (`b0.25`, `eta0.95`, `steel`, etc.).

---

## 5. The six benchmarks

### 5.1 B1 — Energy conservation (paper DCR vs follow-up)

**Goal.** Show the paper's forced-IIR + Eq. 12 path injects modal energy without a global ceiling, while the follow-up's passive-α path always satisfies `cum_E_injected ≤ η · cum_E_loss` (§15 invariant).

**Runs (6 total):** for each scene ∈ {ledge, truck, shelf}, run both:
1. `B1-paper-<scene>`: mode=`coevoet`, flavor=`rest`, defaults otherwise.
2. `B1-passive-<scene>`: mode=`energy_prescribed_patch`, flavor=`barbic_james`, defaults otherwise.

**Mandatory:** the paper-baseline `coevoet` runs must populate `dE_modal_injected` and `cum_E_injected` via the side-channel accounting described in §6.1 — without that, the headline plot has no story.

**Writes to:** `runs/B1_energy_conservation/`.

---

### 5.2 B2 — Deformed normal comparison (rest / patch_fit / Barbič-James)

**Goal.** Quantify whether BJ differs measurably from rest-normal and from patch-fit, and on which scenes.

**Runs (15 total):** for each scene ∈ {ledge, truck, shelf}, run all five cells:
1. `(coevoet, rest)` — baseline reference
2. `(energy_prescribed_point_impulse, rest)`
3. `(energy_prescribed_point_impulse, patch_fit)`
4. `(energy_prescribed_point_impulse, barbic_james)`
5. `(energy_prescribed_patch, barbic_james)`

Defaults otherwise.

**Mandatory:** all 15 runs must write `<run_id>_impulse.csv` alongside the standard files. The impulse-decomposition CSV is what powers the tangential-leak comparison.

**Writes to:** `runs/B2_deformed_normal/`.

---

### 5.3 B3 — β parameter sweep

**Goal.** Validate the two β-related findings from CONTRIBUTIONS.md: A/B blow up at high β; patch mode is β-insensitive.

**Runs (45 total):** for each scene ∈ {ledge, truck, shelf}, each mode ∈ {`energy_prescribed`, `energy_prescribed_point_impulse`, `energy_prescribed_patch`}, sweep β ∈ {0.10, 0.25, 0.50, 0.75, 1.00}. flavor=`barbic_james`, η=0.95 fixed.

**Writes to:** `runs/B3_beta_sweep/`. `run_id = "<scene>__<mode>__b<beta>"`.

---

### 5.4 B4 — η parameter sweep

**Goal.** Confirm the §15 ceiling tracks η linearly; check the corner cases at η → 0 and η → 1.

**Runs (6 total):** scene=`truck`, mode=`energy_prescribed_patch`, flavor=`barbic_james`, β=0.25, η ∈ {0.10, 0.25, 0.50, 0.75, 0.95, 1.00}.

**Writes to:** `runs/B4_eta_sweep/`. `run_id = "truck__energy_prescribed_patch__eta<eta>"`.

---

### 5.5 B5 — Material sensitivity (wood vs steel)

**Goal.** Verify that the trailing-vibration noise documented in CONTRIBUTIONS.md caveat #3 is wood-specific.

**Runs (2 total):** scene=`truck`, mode=`energy_prescribed_patch`, flavor=`barbic_james`, β=0.70, damping_scale=1.0, causal_gating=true, duration=8.0 s, two materials:

| material | E (GPa) | ρ (kg/m³) | ν |
|---|---|---|---|
| wood | 10 | 500 | 0.3 |
| steel | 200 | 7850 | 0.3 |

**Writes to:** `runs/B5_material/`. `run_id = "truck__patch__bj__<material>"`.

In the summary JSON, additionally compute per-body for the last 3 seconds of sim:
- `y_range_last_3s_mm`
- `n_bumps_last_3s` (count of `vy` zero-crossings)

and add them inside each `bodies[]` entry under a `late_phase` subobject.

---

### 5.6 B6 — Cost / runtime overhead

**Goal.** Quantify per-step cost of each mode relative to baseline.

**Runs (12 total):** for each scene ∈ {ledge, truck, shelf}, each mode ∈ {`coevoet`, `energy_prescribed`, `energy_prescribed_point_impulse`, `energy_prescribed_patch`}. flavor=`barbic_james` (or `rest` for `coevoet`). Defaults otherwise.

**Mandatory:** all 12 runs must write `<run_id>_timing.csv`. Disable per-step prints during B6.

**Writes to:** `runs/B6_runtime/`. `run_id = "<scene>__<mode>"`.

---

## 6. Implementation notes

### 6.1 Side-channel energy accounting for the paper baseline

The paper's Eq. 10 step injects modal energy implicitly through the forcing term. To compare against the passive path on equal footing, instrument the forced-IIR step to log the modal energy delta per step:

```
E_before = 0.5 * (qdot_before @ qdot_before + (omega**2 * q_before) @ q_before)
# ... run paper Eq. 10 forced IIR step ...
E_after  = 0.5 * (qdot_after @ qdot_after  + (omega**2 * q_after)  @ q_after)
dE = E_after - E_before
dE_modal_injected[step] = max(dE, 0.0)
dE_modal_extracted[step] = max(-dE, 0.0)
```

This is a passive observer — it must not change the dynamics. Toggle behind a logging flag that is **always on** for B1 paper-baseline runs.

For the passive runs (`energy_prescribed*`), `dE_modal_injected` is already known directly from the α-scaled kick magnitude `ΔE = α · b + 0.5 · α² · a` (see CONTRIBUTIONS.md §6).

### 6.2 Sanity check before launching the full sweep

Before kicking off all 86 runs, do a single dry run to confirm the schema is correct:

1. Run one B1 paper-baseline scene (e.g., `B1-paper-ledge`) and one B1 passive scene (e.g., `B1-passive-ledge`).
2. Open both `_energy.csv` files and confirm: same column count, same column names in same order, no NaN in `cum_E_injected` or `cum_E_budget_eta`.
3. Confirm `B1-paper-ledge`'s `cum_E_injected_final` is non-trivially positive (>0.5 J on a heavy drop). If it's zero, the side-channel accounting (§6.1) didn't engage and the headline B1 plot will be flat.
4. Confirm `B1-passive-ledge`'s `invariant_max_violation_J` is <1e-9. If higher, the §15 enforcement has a bug.

Only proceed to the full sweep if both pass.

### 6.3 Reproducibility

For each manifest entry, record the git SHA (`git rev-parse HEAD`) at the start of the run and the resolved parameter dict (after defaults are applied). If a global config exists (e.g., FEM mesh resolution, number of modes), include it under a `config` field at the top of each manifest.

Use a fixed seed (42) for any stochastic perturbation. Document the seed in `params.seed`.

### 6.4 Failure handling

If a single run inside a benchmark fails (exception, NaN explosion, timeout), do not abort the benchmark — write the failed run's manifest entry with `status: "failed"`, capture the traceback in the `.log` file, and continue. The plotter will skip failed runs with a warning.

### 6.5 Total cost estimate

- B1: 6 runs × ~4 s sim ≈ <2 min wall.
- B2: 15 runs × ~4 s sim ≈ <5 min wall.
- B3: 45 runs × ~4 s sim ≈ <15 min wall.
- B4: 6 runs × ~4 s sim ≈ <2 min wall.
- B5: 2 runs × ~8 s sim ≈ <1 min wall.
- B6: 12 runs × ~4 s sim ≈ <5 min wall (note: timing-only mode, ensure no extra logging cost).

Total: ~30 min wall on a single workstation, give or take.

---

## 7. Driver invocation pattern

Adapt to whatever flag names your existing scripts already use; the key constraints are output paths and the schema. A bash sketch:

```bash
#!/usr/bin/env bash
set -euo pipefail

mkdir -p benchmark/{runs,manifests,plots,logs}/{B1_energy_conservation,B2_deformed_normal,B3_beta_sweep,B4_eta_sweep,B5_material,B6_runtime}

# ---- B1 ----
for scene in ledge truck shelf; do
  python scripts/analyze_patch_mode.py \
    --scene "$scene" --mode coevoet --flavor rest \
    --eta 0.95 --beta 0.25 --duration 4.0 \
    --run-id "B1-paper-${scene}" \
    --out-dir benchmark/runs/B1_energy_conservation \
    --log-paper-side-channel \
    >benchmark/logs/B1/"B1-paper-${scene}".log 2>&1

  python scripts/analyze_patch_mode.py \
    --scene "$scene" --mode energy_prescribed_patch --flavor barbic_james \
    --eta 0.95 --beta 0.25 --duration 4.0 \
    --run-id "B1-passive-${scene}" \
    --out-dir benchmark/runs/B1_energy_conservation \
    >benchmark/logs/B1/"B1-passive-${scene}".log 2>&1
done
python scripts/write_manifest.py --benchmark B1 \
       --runs-dir benchmark/runs/B1_energy_conservation \
       --out benchmark/manifests/B1_manifest.json

# ---- B2 ----
for scene in ledge truck shelf; do
  for cell in coevoet,rest \
              energy_prescribed_point_impulse,rest \
              energy_prescribed_point_impulse,patch_fit \
              energy_prescribed_point_impulse,barbic_james \
              energy_prescribed_patch,barbic_james; do
    mode="${cell%,*}"; flavor="${cell#*,}"
    run_id="${scene}__${mode}__${flavor}"
    python scripts/compare_deformed_normals.py \
      --scene "$scene" --mode "$mode" --flavor "$flavor" \
      --log-impulse-decomposition \
      --run-id "$run_id" \
      --out-dir benchmark/runs/B2_deformed_normal \
      >benchmark/logs/B2/"$run_id".log 2>&1
  done
done
python scripts/write_manifest.py --benchmark B2 \
       --runs-dir benchmark/runs/B2_deformed_normal \
       --out benchmark/manifests/B2_manifest.json

# ---- B3 ----
for scene in ledge truck shelf; do
  for mode in energy_prescribed energy_prescribed_point_impulse energy_prescribed_patch; do
    for beta in 0.10 0.25 0.50 0.75 1.00; do
      run_id="${scene}__${mode}__b${beta}"
      python scripts/sweep_beta.py \
        --scene "$scene" --mode "$mode" --flavor barbic_james --beta "$beta" \
        --run-id "$run_id" \
        --out-dir benchmark/runs/B3_beta_sweep \
        >benchmark/logs/B3/"$run_id".log 2>&1
    done
  done
done
python scripts/write_manifest.py --benchmark B3 \
       --runs-dir benchmark/runs/B3_beta_sweep \
       --out benchmark/manifests/B3_manifest.json

# ---- B4 ----
for eta in 0.10 0.25 0.50 0.75 0.95 1.00; do
  run_id="truck__energy_prescribed_patch__eta${eta}"
  python scripts/analyze_patch_mode.py \
    --scene truck --mode energy_prescribed_patch --flavor barbic_james \
    --eta "$eta" --beta 0.25 \
    --run-id "$run_id" \
    --out-dir benchmark/runs/B4_eta_sweep \
    >benchmark/logs/B4/"$run_id".log 2>&1
done
python scripts/write_manifest.py --benchmark B4 \
       --runs-dir benchmark/runs/B4_eta_sweep \
       --out benchmark/manifests/B4_manifest.json

# ---- B5 ----
for material in wood steel; do
  run_id="truck__patch__bj__${material}"
  python scripts/analyze_patch_mode.py \
    --scene truck --mode energy_prescribed_patch --flavor barbic_james \
    --beta 0.70 --damping-scale 1.0 --causal-gating --duration 8.0 \
    --material "$material" \
    --run-id "$run_id" \
    --out-dir benchmark/runs/B5_material \
    >benchmark/logs/B5/"$run_id".log 2>&1
done
python scripts/write_manifest.py --benchmark B5 \
       --runs-dir benchmark/runs/B5_material \
       --out benchmark/manifests/B5_manifest.json

# ---- B6 ----
for scene in ledge truck shelf; do
  for mode in coevoet energy_prescribed energy_prescribed_point_impulse energy_prescribed_patch; do
    flavor="barbic_james"
    [ "$mode" = "coevoet" ] && flavor="rest"
    run_id="${scene}__${mode}"
    python scripts/analyze_patch_mode.py \
      --scene "$scene" --mode "$mode" --flavor "$flavor" \
      --log-timing \
      --run-id "$run_id" \
      --out-dir benchmark/runs/B6_runtime \
      >benchmark/logs/B6/"$run_id".log 2>&1
  done
done
python scripts/write_manifest.py --benchmark B6 \
       --runs-dir benchmark/runs/B6_runtime \
       --out benchmark/manifests/B6_manifest.json

# ---- top-level manifest ----
python scripts/write_top_manifest.py \
       --manifests-dir benchmark/manifests \
       --out benchmark/manifests/MANIFEST.json
```

Two helper scripts are referenced above that may or may not exist yet — they're trivial wrappers:

- `scripts/write_manifest.py`: globs `<runs-dir>/*_summary.json`, reads each, and writes the per-benchmark manifest JSON.
- `scripts/write_top_manifest.py`: globs `<manifests-dir>/B*_manifest.json` and writes the top-level `MANIFEST.json`.

Add them if missing.

---

## 8. Handoff

When all six benchmarks complete:

1. Confirm `benchmark/manifests/MANIFEST.json` exists and lists all six.
2. Confirm every run referenced in every benchmark manifest has its CSV and JSON on disk.
3. Confirm zero `status: "failed"` entries (or, if any, attach the corresponding `.log` files when sharing).
4. Tarball `benchmark/runs/` and `benchmark/manifests/` together:

   ```
   tar -czf dcr_benchmark_data.tar.gz benchmark/runs benchmark/manifests
   ```

5. Share the tarball back. The plotter will read only the manifests and produce the figures under `benchmark/plots/<Bx>/`.

If any single benchmark is blocked, share the partial tarball with whatever completed plus the manifest of what failed — the plotter handles per-benchmark independence and will produce partial figures.
