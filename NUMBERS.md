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

## §4.3 ledge ground truth (E2 + E3; shared-operator slab GT)

Measured 2026-07-08 on the compshare server. Ledge = boulder impactor + pedestal
responder on a 1.2×0.8×0.08 m slab (E softened to 1.1 GPa, pre-topple linear
regime). GT = CoupledFEMRigidSim implicit Newmark h_fine=5e-5.

| printed | value | source |
|---|---|---|
| shared-operator gate \|Δλ\|=6e-8 (native modes == eigsh(K,M)) | 5.960e-08 | `x3_ground_truth/out/ledge_gt.config.json : shared_operator_gate` |
| GT self-trust 0.18% (halve h_fine to 2.5e-5) | 0.18 | same `: gt_selftrust_pct` |
| convergence ratio 0.38→0.54→0.79→0.88 @ h=1/120→1/960 | .379845/.539993/.792395/.881803 | `x3_ground_truth/out/ledge_convergence.csv : ratio_peak` |
| finer h plateaus ~0.9 (0.94/0.87 @ 1/1920/1/3840) — k=24 mode truncation | 0.936 / 0.865 | reproducible via `_ledge_fine.py` (peak/PEAK_GT=4.2595e-3); trend, not headline |
| ring native 78.0 vs GT 78.3 Hz (0.4%); aliases at 1/120 (47 Hz) | 78.0 / 78.341; 0.435% | `ledge_convergence.csv : f_ring_native, f_ring_gt @ 1/960` |
| falloff peaks at pedestal (antinode) not impact; standing wave | native .00203→.00229(ped)→.00163; GT .00324→.00426(ped)→.00341 | `x3_ground_truth/out/ledge_falloff.csv : resp_native, resp_gt` |
| Spearman ρ(native,GT) falloff = 0.89 (≥0.8) | 0.886 | `ledge_gt.config.json : spearman_falloff` |

## §4.4 vs-DCR falloff (X2)

| printed | value | source |
|---|---|---|
| R/D/native peak KE @0.14 m: 2.9/13.5/9.8 mJ | 2.9364 / 13.5470 / 9.8311 | `x2_vs_dcr/out/x2_response_vs_distance.csv` row dist 0.140 |
| @0.42 m D collapses to 0.9 mJ | 0.9282 | same, row 0.420 |
| @0.56 m: D 0.87, native 2.0 mJ, 2.3× | 0.8672 / 2.0029 → 2.31× | same, row 0.560 |
| method-level caveat (arms at own h; native drawn h=1/240 ≈0.75× amplitude) | — | `docs/paper_eval/x2.md` honesty notes |

## §4.5 passivity (X1)

> **Re-confirm flag (2026-07-08, CLOSED by measurement):** every X1 number
> below predates the quat-order fix in the §15 energy accounting. Measured
> old-meter error, live scenes: **ledge 1.2e-13 J** over 2 s (the boulder is
> a literal cube — isotropic, immune; only the light pillars are
> anisotropic), **dinner 1.2e-8 J** over the 1.2 s drop (vs ~15 J impact
> energy — the anisotropic pot/plates barely rotate, and the error enters
> only through ω). Eleven orders below the smallest relevant contrast ⇒ no
> printed number is affected; E1's re-run is a formality. The fix matters
> prospectively (road-scene lumber will tumble; analytic worst case is
> −50% of a body's angular KE).

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
| friction (E6): 4/4 μ passive; ratio 0.26–0.28; 0 clamps ∀μ | μ={0,.2,.5,1}: holds=passive=True; ratio 0.277/0.255/0.269/0.267; n_clamped=0 | `x1_passivity/out/friction_bound.csv` (cargo stack, AVBD monitor, 360 steps) |
| Schur vs block-GS (E9, §3.2): parity to 1% @32×4; Schur injects @4×1 (block-GS passive) | 32×4 peak_ratio 1.008; 4×1 Schur excess 9432 J (passive=False) vs block-GS -0.002 (passive=True) | `x1_passivity/out/schur_vs_blockgs.csv` (shelf, clamp OFF, monitor ledger); relax=1.0 both inject (probe) |

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
## §4.7 runtime — device-resident co-solved path (E7 device arm / G3a; RTX 4090)

> **RE-VERIFIED 2026-07-19 (R7b).** Re-run at the current submission commit on a
> **re-provisioned** compshare pod (`cpod-1t0b3cmcyn8f`, driver 595.80, CUDA
> 12.9, warp 1.15.0). All four scenes came out 3–11% FASTER; the band moves
> 5.6–9.2 → **5.0–8.9 ms** and the road/truck scene crossed the 120 Hz line on
> the mean (rt 1.012) though **not** on its worst step (9.31 ms). Because the
> pod was re-provisioned, machine/driver is confounded with commit and the
> speedup must NOT be read as a code improvement. Full record, with the
> corrected real-time sentence, in **`docs/mig2026_device_ledger.md`**. The
> rows below are the superseded 2026-07-08 reference, kept for the diff.

Measured 2026-07-08 on the compshare RTX 4090 (warp 1.15, numpy 2.2.6), native
branch commit `f94c850` (warp modal solve + full-substep CUDA-graph capture).
GPU timing: `wp.synchronize_device` brackets every step; 10 warm-up steps; 200
timed frames. Supersedes the stale `0.9–2.4 ms` estimate from
`docs/avbd_native/native_dual_solver.md`.

| printed | value | source |
|---|---|---|
| Table `perfdev` 16×4 ms/step: shelf 5.6 / ledge 6.8 / truck 8.9 / dinner 9.2 | 5.6374 / 6.8235 / 8.8712 / 9.2002 | `x5_perf/out/perf_device.csv : coupling_ms` |
| steps/s @16×4: shelf 177 / ledge 147 / truck 113 / dinner 109 | 177.39 / 146.55 / 112.72 / 108.69 | same `: steps_per_s` |
| shelf/ledge real-time @16×4 (1.5×/1.2× 120 Hz); dinner/truck 0.91×/0.94× | 1.4782 / 1.2213 / 0.90577 / 0.93937 | same `: rt_factor_120hz` |
| 16×2: ledge 3.3 / dinner 4.7 ms (real-time) | 3.28 / 4.65 | `x5_perf/out/perf_device_budget.csv : mean_ms @ 16x2` |
| 8×1: ledge 0.9 / dinner 1.3 ms (795–1092 steps/s) | 0.92 / 1.26; 1091.8 / 794.6 | same `: mean_ms, steps_per_s @ 8x1` |
| cost linear in budget (dinner 1.26→2.43→4.65→9.23→18.05 @ 8×1→32×4) | same | same `: mean_ms` sweep |
| device path passive in 20/20 cells, no active clamp; net excess < 0 ∀ | holds=passive=True ∀; max_net_excess < 0 ∀ | `x5_perf/out/device_passivity.csv` (read-only §15 ledger, 400 steps) |
| e.g. dinner 8×1 Σgain 12.7 ≤ η·Σloss 26.1; ledge 8×1 10.7 ≤ 393.6 | 12.69 / 26.09; 10.66 / 393.6 | same `: cum_modal_gain, eta_cum_loss` |

## §4.8 scale stress — N-body sweep on the device path (Fig. `fig:stress`)

Measured 2026-07-10 on the compshare RTX 4090 (warp 1.15), same protocol as
the device table (sync-bracketed steps, 10 warm-up, 200 timed frames). Scene:
`scenes/reduced_stress.py` — N crates + 1 impactor (nb = N+1) on one 4×4 m
road-material slab, basis pinned at 28 modes at every N. Passivity = the
read-only external §15 ledger (`probe_device_passivity.py` measurement), 240
steps per cell.

| printed | value | source |
|---|---|---|
| 16×4: 9.1→50.7 ms over N 16→512 (5.6×) | 9.0688→50.727 | `x5_perf/out/stress_device.csv : mean_ms @ 16x4` |
| 8×1: 1.3→6.4 ms (5.1×); every N real-time | 1.2715→6.4243; rt ∀N | same `@ 8x1`, `: realtime_120hz` |
| 16×2 real-time through N=64 | 6.98 ms @ 64 (1.19×), 9.74 @ 128 (0.86×) | same `@ 16x2` |
| ≈N^{1/2} growth | 5.05–5.60× cost for 32× bodies | derived from mean_ms ratios |
| graph capture intact at every N (513 bodies) | captured=True ∀ | same `: captured` |
| modal overhead ±0.10 ms ∀N (frozen-ring baseline) | −0.082…+0.102 | `x5_perf/out/stress_device_arms.csv : modal_overhead_ms` |
| ledger passive 18/18 cells, net excess < 0 ∀ | holds=passive=True ∀; excess −3.78…−0.12 | `x5_perf/out/stress_device_psv.csv` |
| natural transfer ratio 0.11–0.25 | 0.107–0.245 | same `: cum_modal_gain / eta_cum_loss` |
| no body ejected (grid extent 1.70 m, resting y ≥ 0.06) | max_xy=1.70, min_y 0.060–0.069 ∀ | `stress_device.csv : max_xy, min_y` |

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

## Tier-1 additions (2026-07-10, measured on compshare AMD EPYC 7542; the
## in-repo CSVs under `x1_passivity/out/` are the server runs — canonical)

### §4.5 η sweep (X1c, Table `tab:eta`)

| printed | value | source |
|---|---|---|
| all 24 cells passive; activations / gain table | verbatim | `x1_passivity/out/eta_sweep.csv` (XPBD, clamp ON, relax 0.7, 8×2 + 16×4) |
| ledge 8×2 gain = η·Σloss exactly (39.9/120/199/399 J) | 39.8788/119.6448/199.4183/398.8811 = budgets | same : cum_gain vs cum_budget |
| natural transfer ratios 0.16 / 0.34 / 0.72 (dinner/ledge/shelf) | 4.414/28.358; 143.96/418.68; 27.917/38.767 | same : cum_gain/cum_budget @ η=1, 16×4 |
| dinner 16×4 η=0.1: 228/432 clamped | 228 | same |
| saturated cells land on the ceiling; early-transient cells end below it | e.g. shelf 16×4 η=0.5: 18 clamps, 18.97 < 19.46 | same |

### §4.1 static ledger extension (X1d)

| printed | value | source |
|---|---|---|
| shelf: every body ≤0.10%, total 0.03% | max 0.098%, total 0.0303% | `x1_passivity/out/static_ledger.csv` (AVBD 16×4, 480 steps, tail 60) |
| ledge: boulder 0.32%, system total 0.25% | 0.3151% / 0.2464% | same |
| two surviving pillars lean on pedestal, joints ~8% over vertical weight | 8.01% / 7.83% (tilted normals) | same : boxbox rows |

### §4.4 matrix slab-passivity cell (X1e)

| printed | value | source |
|---|---|---|
| slab passive both hosts, 0 activations, net excess < 0 | xpbd 0/632, −6.89e-4; avbd 0/632, −5.93e-4 | `x1_passivity/out/slab_passivity.csv` (16×4, η=1; scene via benchmark-branch `scene_and_gt`) |

### §4.8 CPU timings with repetitions (X5b, Table 5)

| printed | value | source |
|---|---|---|
| shelf xpbd 65.2±0.5 / 127.4 / +0.8 / 15.3 | 65.23±0.52, worst 127.42, clamp +0.80±0.28 | `x5_perf/out/perf_reps_server.log` (the six symplectic rows: the original run crashed at the stack config before the CSV write; the log is the artifact) |
| shelf avbd 53.8±0.2 / 60.5 / +1.3 / 18.6 | 53.84±0.20, 60.54, +1.29±0.20 | same |
| ledge xpbd 110.6±1.0 / 152.8 / +0.9 / 9.0 | 110.55±0.98, 152.78, +0.93±0.76 | same |
| ledge avbd 51.6±0.1 / 54.8 / +1.3 / 19.4 | 51.56±0.11, 54.82, +1.30±0.25 | same |
| dinner xpbd 451.6±2.7 / 549.3 / +2.9 / 2.2 | 451.63±2.73, 549.30, +2.89±2.76 | same |
| dinner avbd 125.6±0.6 / 144.7 / +1.5 / 8.0 | 125.57±0.56, 144.68, +1.48±0.62 | same |
| stack (matrix cell) 78.5 ms, 12.7 steps/s | 78.536±0.643, worst 85.93, clamp +1.67±0.85 | `x5_perf/out/perf_reps_summary.csv` (default cargo modal path — symplectic is host non-cargo only) |
| AVBD 1.2–3.6× XPBD | 65.2/53.8=1.21; 110.6/51.6=2.14; 451.6/125.6=3.60 | derived |
| ledger cost +0.8–2.9 ms/step (§4.5) | clamp column range over the six symplectic rows | perf_reps_server.log |
| Mac cross-check 3.5–4.6× (M-series laptop core, same protocol) | shelf avbd 12.59±0.62; ledge avbd 11.24±0.04; dinner avbd 34.12±0.27; ledge xpbd 31.40±0.20; dinner xpbd 125.36±0.90 → factors 4.28/4.59/3.68/3.52/3.60 | local run 2026-07-10 (10 reps × 100 frames); rerun `run_perf_reps.py` locally to regenerate |

## §4.8 impact-sound render demo (E6, 2026-07-11; native-dynamic-constraint branch)

| printed | value | source |
|---|---|---|
| 11.5 J ≤ 25.7 J budget, cap never binds 0/1036 | 11.5 / 25.69 / 0 of 1036 events capped | `docs/stageE6/sound_render.md` (dinner offline render; commit 29689ef + working-tree update) |
| live = offline, 0 underruns | 932 blocks, 1,930 kicks, 0 underruns, 0 clipped; ledger bit-identical to offline | same doc, live (`dcr/sound/live.py`, PortAudio) section |
| AVBD co-solve variant (not printed) | 11.49 ≤ 25.69, 0/814 capped, γ=1 | same doc — kept as backup provenance |

## §4.1 E-R1 modes-off topple control (2026-07-13; repositioning pass)

| printed | value | source |
|---|---|---|
| topple = knife-edge scene dressing; frozen-ring control leaves all pillars standing; coupled arm on ARM also topples none | ARM host (Apple M-series), paper config 16×4 relax 0.7 symplectic, 480 steps: native max\|q̇\|=0.768, frozen 0.0; all 3 pillars tilt 0.00°/max 0.09–0.10°, y-drop 2.1 mm (static sag) both arms | `benchmarks/paper_eval/er1_topple_control/out/topple_control.csv` (code repo) |
| knocked-off pillar of the §4.1 ledger paragraph (x86 EPYC run 2026-07-10) is platform-FP-sensitive | x86 run: pillar_2 gone, pillar_0/1 leaning (+8.0/7.8% joints); ARM re-run at identical config/commit: all standing | `x1_passivity/out/static_ledger.csv` vs the E-R1 CSV; cf. ARM-vs-x86 chaotic-scene note (3 contact tests, platform FP) |
| frozen-ring control on the x86 host | PENDING — compshare pod unreachable 2026-07-13; rerun `er1_topple_control/run_topple_control.py` there before any topple-causation claim | — |
