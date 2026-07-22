# Claim → data → command

Every results section of the paper, the bundled file that carries its numbers,
and the command that produced that file. Commands run from the root of an
unpacked `code_snapshot.zip`; those under `§3.1`–`§3.3` and `§4` live in
`benchmarks/paper_eval/x1_passivity/`, `§3.4` in `x3_ground_truth/`, `§3.5` in
`x5_perf/`. Full invocations, with the commit and machine each was frozen on,
are in `LEDGER_EXCERPTS.md`.

This table is checked mechanically when the bundle is built: each row names a
phrase that must still occur in the paper source and a harness that must still
occur in the results ledger, so a claim cannot be edited out of the paper, or a
harness renamed, without the check failing.

| paper site | printed quantity | data | command |
|---|---|---|---|
| §2 | one row law instantiated at 48 / 40 / 200 support rows | `data/scene_spec.csv` | `make_scene_spec.py` |
| §2 | modal rank r = 16 / 16 / 24 (realized basis size) | `data/scene_spec.csv` | `make_scene_spec.py` |
| §3.1, Fig. 2 top | R > 1 in 8/24 (XPBD), 2/24 (AVBD), 0/24 (impulse) | `data/solver_matrix.csv` | `run_solver_matrix.py` |
| §3.1 | worst R = 1.19534e5 at ledge, relax 1.0, 4x1 | `data/solver_matrix.csv` | `run_solver_matrix.py` |
| §3.1 | peak modal 4.44e7 J against an incident 371 J | `data/solver_matrix.csv` | `run_solver_matrix.py` |
| §3.1 | substep refinement alone does not converge the row (0.300 at 32x1 vs 3.13 at 4x8, overdrawing 481 J) | `data/substep_sweep.csv` | `run_eq2_utilization.py --scenes shelf --budgets 4x1,4x2,4x4,4x8 --relaxes 0.7,1.0 --out substep_sweep` |
| §3.1, Fig. 2 bottom | Eq. (2) violated in 3/24 AVBD cells, 9/24 XPBD (vs R>1 in 2 and 8), 0/24 impulse; AVBD worst 6.7 J (trapezoidal W_g, foundation §15) | `data/eq2_utilization.csv` | `run_eq2_utilization.py --check-frozen` |
| §3.1 | E1 gravity/no-contact accounting audit: AVBD/impulse control floor <= 1e-3 J, 3-4 orders below the 6.7 J effect; the cross-host control claim stands | `data/e1_accounting_audit.csv` | `run_e1_accounting_audit.py` |
| §4 | governed: all 72 cells satisfy Eq. (2); worst ratio 1.22 / 0.87 | `data/solver_matrix.csv` | `run_solver_matrix.py` |
| §3.2, Fig. 3 | XPBD 2.96e4 (K=1) -> 0.300 (K=32); reference 0.2735; implicit max-min 6.8e-4 over K=2...500 | `data/k_convergence.csv` | `run_k_convergence.py` |
| §3.2 | penetration 27.9 mm (K=1) -> 3.6 um (K=64); separated-row multiplier 84x -> 139x (K=24) -> 0 (K=64) | `data/complementarity_residual_nd.csv` | `probe_complementarity_residual_nd.py` |
| §3.2 | XPBD self-convergence plateaus at 0.2996; peak agrees to 2.4%, trajectories differ by 6.8 mm (34% of reference peak) | `data/selfconvergence.csv` | `run_selfconvergence.py` |
| §3.2 | E6a-1 shared-row block condensation does NOT cure the injection: comparable at 4x1, worse at every higher budget where the serial path holds (R=12.5/66.5 at 32x1 block vs 0.30/0.09 serial); diagonal-body approximation, different convergence path; 2 scenes x 4 budgets | `data/e6a1_block_condensation.csv` | `run_e6a1_block_condensation.py` |
| §3.2 | deployed 1x8 / 2x4: XPBD violates 6/6 (worst R = 2282), AVBD 1/6, impulse 0/6 | `data/eq2_deployed.csv` | `run_eq2_utilization.py --budgets 1x8,2x4 --relaxes 0.7 --out eq2_deployed` |
| §4 | governed at the deployed budgets: all 18 satisfy Eq. (2) | `data/solver_matrix_deployed.csv` | `run_solver_matrix.py --budgets 1x8,2x4 --relaxes 0.7 --out solver_matrix_deployed` |
| §3.2 | E1b neighborhood-robustness: each injecting headline cell overdraws in 16/16 deterministic perturbations (12 physical + 4 row-order, cohorts separate), sign never flips, log10 spread 0.31-0.70; the 4.4e7 J worst case is the max of a 2.2-4.5e7 J band | `data/e1b_neighborhood.csv` | `run_e1b_neighborhood.py` |
| §3.2 | band-limit the co-solve across the sweep: 6 of 8 injecting cells still overdraw (worst ledge +1.24e6 J); shelf 4x1 R 6333->22.1, 584 J still overdrawn | `data/band_limit_sweep.csv` | `probe_band_limit_sweep.py` |
| §3.1 | warm-start ablation: carrying lambda across substeps leaves the position-based footprint unchanged (R>1 in the same 8/24 cells, worst 1.20e5), and worse at 4x1 (3.1x) | `data/warm_start_ablation.csv` | `probe_warm_start_ablation.py` |
| §4.1, Table 1 | post-projection contact validity, XPBD: clamp counts, gap violation med/max, corrective impulse, lambda variance | `data/projection_validity.csv` | `run_projection_validity.py` |
| §4.1 | AVBD projection at its one materially-overdrawing cell (dinner 1.0 4x1, +6.7 J): 1.8 mm, single clamped substep, no corrective impulse; the other R>1 cell holds the invariant (clamp inert) | `data/projection_validity_avbd.csv` | `run_projection_validity_avbd.py` |
| §4.1 | accuracy at shelf 8x2: 1555.6 J -> 29.56 J against 7.92 J; energy error 196x -> 3.7x; trajectory 6.5 mm -> 14.2 mm (governed peak +1% under trapezoidal W_g) | `data/governed_accuracy.csv` | `run_governed_accuracy.py` |
| §4.1 | deployed 1x8: energy 2823x -> 3.7x, trajectory 108% -> 96% | `data/governed_accuracy_1x8.csv` | `run_governed_accuracy.py --scene shelf --cell 1x8 --relax 0.7 --out governed_accuracy_1x8` |
| §5.1 | reduced/reference peak-deflection ratio 0.38 -> 0.88 as h refines; ring frequency agrees to 0.4% (78.0 vs 78.3 Hz) | `data/ledge_convergence.csv` | `(x3_ground_truth harness; see ledger)` |
| §5.1 | far-field falloff tracks the reference at Spearman rho = 0.89 | `data/ledge_falloff.csv` | `(x3_ground_truth harness; see ledger)` |
| §5.2 | CPU: baseline 11.0-125.6 ms; ledger adds 0.23-0.41 ms (0.9-3.4%) where it resolves above run-to-run variance | `data/perf_reps_summary.csv` | `run_perf_reps.py --only shelf,ledge,dinner --reps 10 --frames 100` |
| §5.2 | deployed 1x8/2x4: absolute 0.30-2.22 ms, percentage 6.6-34.3% (shelf/ledge, baseline shrinks); table scene 7-12% faster governed | `data/perf_reps_1x8_summary.csv` | `run_perf_reps.py --budgets 1x8,2x4 --only shelf,ledge,dinner` |
| §6 | supply partition dependence is bounded (coarsening ratio <= 1.083) | `data/supply_partition.csv` | `probe_supply_partition.py` |
| §6 | recycling is steady state, not a window artifact, over a 10x horizon | `data/long_horizon.csv` | `probe_long_horizon.py` |
| §6 | return channel 0.4-27% (impulse), 3-32% (XPBD), 102-118% (AVBD) | `data/eq2_utilization.csv` | `run_eq2_utilization.py --check-frozen` |

## Re-verifying without re-running anything

Three entry points check printed numbers against these CSVs directly:

- `verify_paper_numbers.py` — re-reads the §3.3 accuracy, contact-validity and
  §3.5 runtime numbers from the CSVs and asserts each. Pure file reads, no
  simulation, about a second:

  ```sh
  python code_snapshot/benchmarks/paper_eval/verify_paper_numbers.py --data data
  ```

  One check compares against the paper source, which this bundle does not ship;
  it reports `skip` unless you pass `--tex <path to main_short.tex>`. All
  others run.
- `run_eq2_utilization.py --check-frozen` — re-runs the 24-cell sweep and
  asserts it reproduces the frozen ratios exactly. This is also the
  non-perturbation proof: the accounting runs live while the trajectory stays
  bit-identical to an ungoverned run.
- `run_governed_accuracy.py --check-frozen` — the same for §3.3.

`smoke_test.py` in this bundle runs the cheapest version of the second one.

## Historical CSV columns (no longer a paper object)

The `eq2_*.csv` files carry `margin_allow_J`, `eq2_violates_allow`, and
`max_deposit` columns. These encode the *one-deposit-relaxed* reading of the
bound (former Eq. (4)). The paper now proves and reports the **strict** bound
Eq. (2) directly (Prop. 2.1), so the relaxed columns are retained only for
provenance and are not referenced by any paper claim; read `eq2_violates`,
`margin_J`, and `max_net_excess` instead. `max_net_excess` is exactly the signed
slack of Eq. (2) the proposition bounds.

The supply itself uses the trapezoidal gravity work `W_g = ½ m g·(v⁻+v⁺) h`
(foundation §15): free ballistic motion credits zero, so the earlier 23/24 AVBD
"overdraft" — mostly the symplectic ½mh²g² integrator artifact — resolves to
3/24, and the implicit host's margins sit at exactly zero.

## What is NOT re-derivable from this bundle

Stated so the omissions are not mistaken for oversights:

- **Device-resident timings (§3.5, second paragraph).** Measured on an NVIDIA
  RTX 4090; the CSVs are here, the hardware is not. Every other number in the
  paper comes from the single CPU machine described in the README.
- **The full-FEM reference (§3.4).** The comparison CSVs are here; regenerating
  them needs the unreduced FEM harness and hours of compute, so this bundle
  ships the results rather than the means to reproduce them cheaply.
- **The video's rendered frames.** `mig_short_video.mp4` is rendered from frozen
  traces and the bundled result CSVs; the traces are large binaries and are not
  bundled.
