# Supplementary material

Anonymous submission. This bundle contains the source, the scene specification,
the frozen results-ledger excerpts, and the raw data behind every number in the
paper, plus the supplementary video.

```
README.md              this file
CLAIMS_INDEX.md        every results section -> data file -> command
LEDGER_EXCERPTS.md     the frozen ledger entries (command, commit, machine)
DECISION_TABLE.md      the practitioner decision table (paper conclusion prose)
data/                  raw CSVs and their .config.json manifests
code_snapshot.zip      the source needed to re-derive them
smoke_test.py          clean-unpack check (see §4)
requirements-freeze.txt
mig_short_video.mp4    the supplementary video (see §5)
SHA256SUMS
```

Commit identifiers read `<commit>` throughout: a searchable hash would identify
the authors. `code_snapshot.zip` is the exact source state those commits name.

## 1. Machine, versions, and what is exact

Every solver-behaviour measurement in the short paper was produced on a single
machine — **Apple M4, CPU only, CPython 3.12, float64, arm64** — running
serially. (A device-resident monitor path exists in the codebase; its timings
are out of scope for this short paper and are not indexed here.)

We do not mix machines, and the reason bears on reproducing this work:
**chaotic contact stacks diverge across architectures under floating-point
reassociation.** The printed digits are exact on arm64 and should be expected
to differ on x86-64 — in a recorded instance, three contact tests and one
scene's standing-pillar outcome differed between the two. What is portable is
the *qualitative* result: which host violates the bound, by how many orders of
magnitude, and that the violation decays with iteration count. `smoke_test.py`
therefore asserts qualitatively and prints the digits for comparison.

Package versions are pinned in `requirements-freeze.txt`.

## 2. Scene specification

Every value below is read from the scene-builder signatures and from a built
solver, not transcribed by hand.

| quantity | unit | shelf | ledge | table |
|---|---|---|---|---|
| support length | m | 0.80 | 1.20 | 2.20 |
| support width | m | 0.30 | 0.80 | 1.10 |
| support thickness | m | 0.030 | 0.080 | 0.040 |
| support top height | m | 0.015 | 0.040 | 0.030 |
| Young's modulus E | Pa | 5e+08 | 1e+10 | 1.1e+09 |
| density | kg/m^3 | 600 | 500 | 770 |
| Poisson ratio | - | 0.30 | 0.30 | 0.30 |
| impactor mass | kg | 6.0 | 50.0 | 5.0 |
| impactor drop height | m | 0.50 | 0.80 | 0.50 |
| impactor initial speed | m/s | 0.0 | 0.0 | -- |
| Rayleigh alpha_0 | 1/s | 3.0 | 2.0 | 2.0 |
| Rayleigh alpha_1 | s | 1.0e-05 | 1.0e-05 | 1.0e-05 |
| global modes REQUESTED | - | 10 | 12 | 10 |
| local modes REQUESTED | - | 14 | 16 | 14 |
| timestep h | s | 0.008333 | 0.008333 | 0.008333 |
| modal rank r REALIZED | - | 16 | 16 | 24 |
|   of which stiff cluster | - | 6 | 4 | 14 |
| lowest mode | Hz | 20.3 | 118.1 | 4.7 |
| highest mode | Hz | 24708 | 190903 | 5202 |
| support rows (eq. 1) | - | 48 | 40 | 200 |
| dynamic bodies | - | 7 | 6 | 26 |

Seeds: none. The CPU path has no RNG; every run is bit-deterministic on a fixed machine (Apple M4, CPython 3.12).

**REQUESTED vs REALIZED modes.** `n_modes_local` is clamped to the number of distinct contact zones (`scenes/reduced_scene_common.py:242`, deduped within 15 mm, because coincident bumps make Mq singular), so the delivered rank is smaller than `n_modes_global + n_modes_local` on the shelf and ledge. The paper's Table 1 prints the REALIZED rank.


## 3. Data

`CLAIMS_INDEX.md` maps each of these to the paper claim it supports and the
command that produced it.

### §2 scene specification and row counts
- `data/scene_spec.csv`
- `data/scene_spec.md`

### §3.1 one row, three hosts, 24 cells (Fig. 2, Table 1)
- `data/solver_matrix.csv`
- `data/eq2_utilization.csv`
- `data/substep_sweep.csv`

### §3.2 iteration budget and convergence (Fig. 3)
- `data/k_convergence.csv`
- `data/selfconvergence.csv`
- `data/complementarity_residual.csv`
- `data/complementarity_residual_nd.csv`
- `data/complementarity_residual_nd_ledge.csv`

### §3.2 deployed budgets 1x8 / 2x4
- `data/eq2_deployed.csv`
- `data/solver_matrix_deployed.csv`
- `data/projection_validity_deployed.csv`
- `data/governed_accuracy_1x8.csv`

### §3.2 robustness ablation and worst-cell ladder
- `data/robustness_ablation.csv`
- `data/k_convergence_ledge_worst.csv`

### §3.1--§3.2 accounting, robustness, mechanism controls (E1/E1b/E6a-1)
- `data/e1_accounting_audit.csv`
- `data/e1b_neighborhood.csv`
- `data/e6a1_block_condensation.csv`

### §3.1/§3.5 reviewer-response ablations (warm-start, band-limit)
- `data/warm_start_ablation.csv`
- `data/band_limit_sweep.csv`

### §4.1 cost of enforcement (Table 1)
- `data/projection_validity.csv`
- `data/projection_validity_avbd.csv`
- `data/governed_accuracy.csv`

### §5.1 reduced response against a full-FEM reference
- `data/ledge_convergence.csv`
- `data/ledge_falloff.csv`

### §5.2 runtime cost (CPU; the device monitor path is out of the short paper)
- `data/perf_reps_summary.csv`
- `data/perf_reps_1x8_summary.csv`
- `data/perf_reps_2x4_summary.csv`

### §6 limitations: supply partition and long-horizon recycling
- `data/supply_partition.csv`
- `data/long_horizon.csv`

## 4. Reproducing

Unpack the snapshot and run the smoke test:

```sh
unzip code_snapshot.zip -d code_snapshot
python -m venv .venv && .venv/bin/pip install -r requirements-freeze.txt
.venv/bin/python smoke_test.py
```

It builds one scene from source and re-derives one cell of the 24-cell sweep on
all three hosts — the paper's central contrast in miniature — asserting the
qualitative outcome and printing the digits.

Every harness in `benchmarks/paper_eval/` is measurement-only: it imports the
scenes and solvers read-only and sets each knob at runtime. None modifies solver
source, and each neuters the governor's actuator (`passivity_gamma` forced to
1.0) so the reservoir accounting runs live while the trajectory stays
bit-identical to an ungoverned run. That non-perturbation property is asserted,
not assumed: the ablation's two base rows reproduce the frozen matrix ratios
exactly (119534 and 6333.22).

Full invocations are listed with each entry in `LEDGER_EXCERPTS.md`.

## 5. Video

`mig_short_video.mp4` (52.0 s, 1920x1080, H.264, no audio) is a six-beat
practitioner diagnostic that follows the paper's structure: (1) the cheap modal
extension to a fixed-budget XPBD rigid host; (2) the spurious bystander launch —
ungoverned versus the host's own high-iteration self-reference (500x1) on a
steel board, at identical camera and true scale; (3) the same 32 contact-row
evaluations spent as iterations (32x1, holds) versus substeps (4x8, overdraws);
(4) the band-limited basis, necessary but not sufficient; (5) the last-resort
storage bound as containment, with a true-scale penetration cross-section; and
(6) a decision card. It was rendered headlessly from frozen traces and the
bundled result CSVs — no interactive capture — by
`benchmarks/paper_fig/make_short_video.py`.

It is deliberately not a success reel. It ends on the operating-guide decision
rule, not on the guardrail: the storage bound appears only as last-resort
containment, captioned *bounded, but not faithful*, and every on-screen number
is read live from the bundled data.

## 6. Verifying this bundle

```sh
shasum -a 256 -c SHA256SUMS
```
