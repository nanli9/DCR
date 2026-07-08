# NUMBERS.md — provenance ledger

Binding rule (docs/mig_submission_plan.md §0.2): every number printed in the
paper traces to a committed artifact. Source of truth = the CSV on the
`benchmark` branch under `benchmarks/paper_eval/`; the per-stage docs
(`docs/paper_eval/x*.md`) are narrative and in two known places STALE relative
to the CSVs (noted below). Format: `value ← file : column/row`.

## §4.3 slab full-FEM anchor (X3)

| printed | value | source |
|---|---|---|
| ladder 0.56→0.75→0.90→1.03 | 0.5581 / 0.7519 / 0.8954 / 1.0253 | `x3_ground_truth/out/x3_convergence.csv : mid_ratio_native_over_gt @ h_inv 120/240/480/960` |
| ring 81.0 vs 80.7 Hz, 0.4% | 81.044 / 80.714 / 0.41% | `x3_ground_truth/out/x3_freq.csv` |
| aliasing note (read at h=1/480) | — | `docs/paper_eval/x3.md` Result 2 |
| mode-truncation 35.8% k=1, ≈27–30% k≥2 | 35.754 / 27.056 / 29.547 … | `x3_ground_truth/out/x3_mode_convergence.csv : field_profile_err_pct` |
| launch KE non-convergent 158→39→69 mJ | — | `docs/paper_eval/x3.md` Result-1 table (GT h 1e-4/5e-5/2.5e-5); CSV artifact not committed — regenerate in E3 if quoted further |
| deflection field stable to 1% | mid −0.616/−0.609/−0.610 mm | same doc table |
| GT wall-clock 13.6× native | 13.288 vs 0.977 s/sim-s, speedup 13.59 | `x3_ground_truth/out/x3_wallclock.csv` |
| tet ladder 3–10%/rung, 67k nodes | — | fem-gt commit fb9ae0f (native branch, docs) — re-cite in W3 |

## §4.3 dinner ground truth (native-branch harness — NOT X-suite)

| printed | value | source |
|---|---|---|
| GT ring 9.2–9.9 Hz vs f1=9.8 Hz; 18 min/1.2 s; insensitivity 24→48 modes, 0.7→1.0 relax | — | dinner GT harness (`benchmarks/dinner_dcr/run_dinner_dcr.py`, `docs/dinner_dcr/results.json` + `gt_d{0,1,2}/`) — insensitivity claims still to be pinned to a CSV in E3 |
| ~7× near-field deficit (as plotted) | Fig. panels: native ~7 mm vs GT ~50 mm near-field | `docs/dinner_dcr/response_vs_distance.png` + results.json |
| E5 h-ladder: median launch ratio 0.016→0.052→0.136→0.257 @ h=1/120→1/960, n=72/rung | medians; IQR in CSV | `benchmark/runs/substep/dinner_h_ladder.csv` (native branch) |
| per-step cost flat ~35 ms across the ladder | 34.8–38.1 | h-ladder run log (same CSV run) |
| ~34 s/sim-s at 1/960; ~22× under GT | 0.035·960=33.6; (18·60/1.2)/33.6=22.3 | derived: ladder ms/step × steps; GT wall from harness protocol |

## §4.4 vs-DCR falloff (X2)

| printed | value | source |
|---|---|---|
| R/D/native peak KE @0.14 m: 2.9/13.5/9.8 mJ | 2.9364 / 13.5470 / 9.8311 | `x2_vs_dcr/out/x2_response_vs_distance.csv` row dist 0.140 |
| @0.42 m D collapses to 0.9 mJ | 0.9282 | same, row 0.420 |
| @0.56 m: D 0.87, native 2.0 mJ, 2.3× | 0.8672 / 2.0029 → 2.31× | same, row 0.560 |
| method-level caveat (arms at own h; native drawn h=1/240 ≈0.75× amplitude) | — | `docs/paper_eval/x2.md` honesty notes |

## §4.5 passivity (X1)

| printed | value | source |
|---|---|---|
| 12/24 cells inject OFF; 24/24 passive ON | verified by direct CSV scan 2026-07-07 | `x1_passivity/out/robustness_clamp.csv : passivity_off>1 count; passive_on all True` |
| worst per scene OFF: shelf 1.1e4, ledge 1.2e5, dinner 5.1e3 | 10,962 / 119,533.86 / 5,141 | same : max(passivity_off) per scene |
| every injecting cell lands ≤1.22 ON | max passivity_on 1.2197 (shelf) | same |
| PAPER_CONFIG (16×4, 0.7): 0 clamps, identical | n_clamped=0; passivity_off==passivity_on (0.4366/0.2200/0.2220) | same, rows iters=16,substeps=4,relax=0.7 |
| shelf 8×2: 53.7× OFF → 1.01 ON | 53.7307 / 1.0107 | same, row shelf/0.7/8/2 |
| clamps 174/236; inert 0/472; ledger excess ~3e-17 J; AVBD monitor 0.617/0.271, excess 0.026 J | — | `docs/paper_eval/x1.md` Results table (pre-doc validated run) |
| blow-up 5.5e4 / 9.2e6 / 3.0e6 J OFF → 40.8/36.0/42.3 J ON (~1 J scene) | 54,986.7 / 9,243,073 / 3,028,624 → 40.77/35.99/42.32 | `x1_passivity/out/blowup_prod.csv` rows xpbd 1×16, 2×4, 1×8 |
| AVBD bit-identical 0.91/0.79 J, 0 activations | Emod_off==Emod_on 0.90742/0.78789 | same, rows avbd 4×4, 2×4 |
| cap cost +37–64% XPBD extreme budgets | cost_pct 36.83–64.45 | same : cost_pct |
| over-damping: cap-ON \|a\|≈1.2e-5 vs 6e-4 converged-XPBD vs 8e-5 AVBD | q_on 1.10–1.18e-5; q_off (2×4) 4.06e-3?; doc cites converged-XPBD 6e-4, AVBD 8e-5 | `blowup_prod.csv : q_on`; references `docs/paper_eval/x1_blowup.md` §3b — pin the 6e-4/8e-5 to a CSV in E1 |
| γ projection / reservoir / grav_work−ΔKE budget | mechanism | `dcr/avbd/_solver/passivity.py` + `docs/paper_eval/x1.md` Mechanism §1–3 |

## §4.6 restitution (X7)

| printed | value | source |
|---|---|---|
| DCR loss collapses 7.30→0.20 J; injection grows 0.15→0.52 J | 7.30154→0.198139; 0.14898→0.524016 | `x7_restitution/out/x7_restitution.csv` |
| ratio crosses ~0.8, plateaus 2.63–2.64 | 2.6328 (0.9) … 2.6447 (0.99); 0.7→0.1419 | same : dcr_ratio |
| native 0.053 ∀ε_r, passive | 0.0527, native_passive True all rows | same : native_ratio |
| windowing caveat; native e=0 | — | `docs/paper_eval/x7.md` honesty notes |

## §4.7 runtime (X5) — CSV newer than doc; CSV wins

`x5_perf/out/perf.csv` (mtime Jul 6 20:57) supersedes the stale table in
`docs/paper_eval/x5.md` (20:53; shows 58.3/28.8/31.4 ms — an older run).
Single run; E7 re-measures with repetitions + R/D baselines.

| printed | value | source |
|---|---|---|
| Table 3 all cells | mean_ms/worst_ms/clamp_overhead_ms/steps_per_s | `x5_perf/out/perf.csv` (6 rows) |
| AVBD 1.6–3.1× XPBD | 26.9/17.1=1.57; 42.0/15.8=2.66; 102.9/33.7=3.05 | derived from same |
| ledge/AVBD 15.8 ms ≈ 63 steps/s (fastest validated) | 15.78 / 63.37 | same |
| dinner/AVBD ~34 ms (cited in §4.3) | 33.73 | same |
| device path 0.9–2.4 ms, non-symplectic, not passivity-validated | — | `docs/avbd_native/native_dual_solver.md` (native branch) |

## Table 2 matrix cells (new/changed this pass)

| cell | source |
|---|---|
| Slab L2 .56→1.03 (was 1.02 — typo: 1.0253 rounds to 1.03) | x3_convergence.csv |
| Slab distant-response 2.3×D | x2_response_vs_distance.csv |
| Passivity ✓ dinner/ledge/shelf | robustness_clamp.csv (passive_on) |
| Ablation ✓ dinner 5.1e3× / ledge 1.2e5× / shelf 1.1e4× | robustness_clamp.csv (passivity_off) |
| Ablation Stack → n/a (was ✓X1 — robustness scenes are shelf/ledge/dinner, not the cargo stack) | CSV scene column |
| Restitution dinner .05 vs 2.6 | x7_restitution.csv |
| Runtime dinner 33.7 / ledge 15.8 / shelf 17.1 (AVBD) | perf.csv |

## §4.6 momentum (E4 probe, native branch)

| printed | value | source |
|---|---|---|
| free-flight pair drift 0.0 | max ‖ΔP‖ = 0.0 over pre-contact window | `benchmark/runs/momentum/probeA_budget_sweep.csv : free_flight_drift` (native branch) |
| impact creation +47/+12/+1.8/+0.2 % | 46.6 / 11.8 / 1.8 / 0.2 | same : creation_pct @ 12×4 / 32×4 / 64×4 / 12×16 (rigid cubes) |
| identical with network on/off | 46.6 == 46.6 == 46.6 | same : rows (12×4, network True/False, fem_rigid/rigid) |
| clamp momentum-silent: identical before first activation | first clamp frame 1, first divergence frame 2, 183 activations | `benchmark/runs/momentum/probeB_clamp.csv` + `summary.json` |

## §4.1–4.2 (pre-existing, unchanged)

Ledger 0.06–1.9%, ripple ±2.72→±1.48 N, ring 1.1e-5/0 ←
`benchmarks/network/report_sheldon_contact_forces.py` output +
`docs/sheldon_report/` (native branch).
