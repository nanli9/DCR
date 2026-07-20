# Supplementary material

Anonymous submission. This bundle contains the scene specification, the frozen
results-ledger excerpts, and the raw CSVs behind every number in the paper.

All solver-behaviour measurements were produced on a single machine — Apple M4,
CPU only, CPython 3.12, float64 — running serially. Chaotic contact stacks
diverge across architectures under floating-point reassociation, so we do not
mix machines; the sole exception is the device-resident timing paragraph, which
is reported separately and labelled as such in the paper.

Source commit for this bundle: `6f6e608`.

## 1. Scene specification

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


## 2. Ledger excerpts

`LEDGER_EXCERPTS.md` reproduces the frozen entries for the 24-cell matrix
(E-S1b), the deployed budgets (E-C6) and the robustness ablation (E-C9),
each with its generating command, commit and machine.

## 3. Raw data

### matrix (Fig. 1, Table 1, §3.1)
- `data/solver_matrix.csv`
- `data/eq2_utilization.csv`

### iteration budget (Fig. 3, §3.2)
- `data/k_convergence.csv`
- `data/selfconvergence.csv`
- `data/complementarity_residual.csv`
- `data/complementarity_residual_nd.csv`
- `data/complementarity_residual_nd_ledge.csv`

### deployed budgets 1x8 / 2x4 (§3.2, E-C6)
- `data/eq2_deployed.csv`
- `data/solver_matrix_deployed.csv`
- `data/projection_validity_deployed.csv`
- `data/governed_accuracy_1x8.csv`

### enforcement cost (Table 2, §3.3)
- `data/projection_validity.csv`
- `data/projection_validity_avbd.csv`
- `data/governed_accuracy.csv`

### robustness ablation (§3.2, E-C9)
- `data/robustness_ablation.csv`
- `data/k_convergence_ledge_worst.csv`

### supplement-only probes (E-C9c/d)
- `data/supply_partition.csv`
- `data/long_horizon.csv`

### scene specification (P8.a)
- `data/scene_spec.csv`
- `data/scene_spec.md`

## 4. Reproducing

Every harness is measurement-only: it imports the scenes and solvers read-only
and sets each knob at runtime. None modifies solver source, and each neuters the
governor's actuator (`passivity_gamma` forced to 1.0) so the ledger runs live
while the trajectory stays bit-identical to an ungoverned run. The
non-perturbation property is asserted, not assumed: the ablation's two base rows
reproduce the frozen matrix ratios exactly (119534 and 6333.22).

Commands are listed with each ledger entry in `LEDGER_EXCERPTS.md`.

## 5. Video

A supplementary video (ungoverned / governed / converged reference at the same
starved budget) is **not included in this revision**: it requires an interactive
capture session that the offline pipeline cannot perform. The teaser figure
shows the same three-arm comparison as stills.
