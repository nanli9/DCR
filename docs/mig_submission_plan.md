# MIG 2026 — detailed execution plan (v2, deep)

Companion to `docs/experiment_plan.md` (metric×scene×baseline map, G1–G5 gap
analysis) and the paper (`paper` branch, worktree `DCR/paper`). This is the
**execution** document: every task carries `Serves` (which claim / paper cell),
`Needs` (branch, files, compute, dependencies), `Procedure`, `Output format`
(exact artifact spec), `Validation` (acceptance + sanity counterfactuals), and
`Effort / Risk / Fallback`.

---

## 0. Venue facts and logistics (verified 2026-07-07)

| item | value | source |
|---|---|---|
| Submission window | **Jul 25 – Aug 7, 2026 (AoE)** | mig.siggraph.org/2026 |
| Notification / camera-ready / conf. | Sep 24 / Oct 8 / Dec 11–13 (Charleston SC) | same |
| Format | ACM `acmart`, **sigconf**; review copy `[sigconf,screen,review,anonymous]` | MIG CFP (2025 wording; re-check 2026 CFP when posted) |
| Page limit | **long ≤ 10 pages excluding references**; short 4–6 | same |
| Review | **double-blind**; include EasyChair paper ID | same |
| Supplementary | video strongly encouraged, **≤ 200 MB** total | same |
| System | EasyChair (`mig2026` expected) | same |
| Author req. | ORCID required for camera-ready | same |
| Local toolchain | TeXLive 2026 with `acmart.cls` + `ACM-Reference-Format.bst` ✓; `latexmk` ✓ | verified |

**Internal target: submit Aug 5 AoE** (2-day buffer).

## 0.1 Status ledger (update as tasks close)

| id | task | status 2026-07-07 |
|---|---|---|
| W1 | X-suite transcription | **DONE** — §4.4 vs-DCR (X2), §4.5 passivity full prose (X1 robustness + blow-up + mechanism + price), §4.6 restitution (X7), §4.7 runtime (X5 CSV), §4.3 expanded (aliasing, k-truncation, GT-signal honesty, standing-wave scope, 13.6×); Tables 2–3 updated (+Shelf/Slab columns, +restitution row, stack-ablation cell corrected to n/a); 3 draft figures imported; `paper/NUMBERS.md` provenance ledger created. Findings: `perf.csv` (newer) supersedes stale `x5.md` table — dinner/AVBD 33.7 ms not 58.3 (E7 validation threshold updated accordingly); X3 ladder rounds to 0.56→0.90→**1.03** (matrix 1.02 was the typo, prose was right); X1 robustness scenes are shelf/ledge/dinner (NOT the cargo stack — E1's remaining gap is only the blow-up figure on paper scenes + stack, and dinner/ledge bound cells are already measured). Dinner-GT numbers (9.2–9.9 Hz, 7×) remain provisional pending E3/E5 CSV pinning |
| W4 | MIG/acmart format conversion | **DONE** — builds 8 pp with W1 content, anonymous+line numbers, wide tables→`table*`, wide figs→`figure*`, overwide equations reflowed, `\Description` added. Residual: ~7 minor overfulls, teaser missing, ORCID placeholder, EasyChair ID placeholder |
| E8 | ΔE_rigid<0 edge case | **DONE** — guards existed (deposit clamps negative loss; γ/α → 0 on non-positive ceiling); pinned by 4 new unit tests in `test_passivity_clamp.py`. **Bonus fix:** quat-order bug in the §15 energy accounting (warp xyzw fed to wxyz-expecting `rigid_mechanical_energy` in BOTH solvers) — wrong angular-KE for rotated anisotropic bodies; fixed at all 6 call sites + analytic regression test. Cube-only scenes (shelf X1) unaffected (isotropic); dinner/ledge X1 cells to re-confirm in E1 |
| E4 | momentum probe | **DONE** — `benchmarks/momentum/probe_momentum.py` + CSVs. Findings: free flight conserves exactly; a 1.5 m/s box-box impact CREATES pair momentum at truncated budgets (+46.6% @ 12×4 → +0.2% @ 12×16), identical with modal network on/off/rigid — the coupling adds no momentum error beyond the host's own; clamp is momentum-silent (bit-identical until first activation). Paper: §4.6 (momentum) added, §3.1 claim scoped, matrix Stack/Shelf momentum cells flipped |
| E5 | 7× deficit characterization | **DONE (reframed)** — the modal state is a co-solved constraint DOF (rate = substep rate; no separate integrator to sub-step), so E5 ran as the **dinner h-ladder** (`benchmarks/dinner_dcr/run_h_ladder.py` vs cached GT): median launch ratio 0.016→0.052→0.136→0.257 @ h=1/120→1/960, monotone, n=72/rung, cost flat ~35 ms/step. Mechanism = rigid-step band-limiting CONFIRMED; residual gap is an upper bound (GT launch is contact-model-limited per X3). Paper §4.3 + Limitations rewritten around the ladder + the passivity-vs-timestep trade vs DCR. Correction: draft's "~7×" was the near-field peak; all-body median at 1/120 is 0.016 |
| R1 | real-time framing decision | **DECIDED** — title now "Interactive-Rate…"; revert only if E-G3a (device-path validation) lands before Aug 1 |
| R2 | accuracy-metric decision | **DECIDED** (this doc §1.2) — deflection field primary, launch amplitude secondary; E5 characterizes the transient deficit |
| X1/X2/X3/X5/X7 | reference-scene evidence | **DONE** on `benchmark` branch (see §0.2) — needs transcription (W1) + generalization (E1–E3) |
| E1–E9, W1–W3, W5–W7 | below | open |

## 0.2 Evidence already committed (`benchmark` branch) — transcribe, don't re-run

| suite | headline (source of truth = committed CSVs under `benchmarks/paper_eval/`) |
|---|---|
| X1 | clamp OFF injects in 12/24 budget×relax×scene cells, up to **119,534×**; ON 24/24 passive, 0 activations in safe region |
| X2 | far-object KE: native 9.8/4.9/3.2/2.0 mJ vs DCR 13.6/6.1/0.9/0.9 at 0.14–0.56 m; native = standing-wave falloff, **no C·r^-β fit** |
| X3 | native/GT mid-deflection **0.56→0.75→0.89→1.02** (h=1/120→1/960); ring 81.0 vs 80.7 Hz (**0.4 %**) |
| X5 | dinner/AVBD **58 ms**, ledge/AVBD **29 ms** per step; clamp overhead +1–2 ms (2–5 %); AVBD 1.3–2.8× XPBD; device path 0.9–2.4 ms (unvalidated) |
| X7 | paper-DCR energy ratio → **2.6×** as ε_r→1; native **≤ 1 ∀ ε_r** |

> **Transcription rule (binding):** every number printed in the paper must be
> traceable to a committed CSV path, recorded in a `paper/NUMBERS.md` ledger
> (`value ← file:column:row`). Known discrepancy to resolve from CSVs before
> printing: draft §4.3 says `0.56→0.75→0.90→1.03`, experiment plan says
> `0.89→1.02` — one of them is a typo; the CSV decides.

---

## 1. The two decision-risks (both now decided — record + guard)

### 1.1 R1 — "real-time" vs the measured 17–34 Hz
X5 measures the **passivity-validated CPU path** at 58 ms (dinner) / 29 ms
(ledge) per step — not real-time at h=1/120. The 0.9–2.4 ms device path is a
different, unvalidated code path (G3). **Decision: claim "interactive rates"**;
title changed accordingly; runtime section must state the split in one honest
sentence and position device residency as engineering headroom, citing the
measured device numbers as such.
**Guard (W7 check):** grep the final PDF text for "real-time" — every
occurrence must be about *other* work (DCR, XPBD) or explicitly qualified.

### 1.2 R2 — the 7× launch-amplitude deficit
GT launch KE does **not** converge under GT refinement (2 kHz penalty-spring
oscillator, `experiment_plan.md` §6.1); the deflection field u_y does (→1.02).
**Decision:** primary accuracy metric = deflection-field error / falloff (E3);
launch amplitude demoted to "contact-model-limited secondary observable" for
*both* arms; E5 (sub-step sweep) characterizes the transient band-limiting and
feeds the fidelity-vs-passivity figure (ours vs DCR's 2.6× violation, X7).
**Guard:** §4.3 may not lead with a launch-amplitude number; the 7× appears
only alongside its explanation and the E5 curve.

---

## 2. Experiments

Common environment for ALL experiment tasks:
- **Branches:** harnesses live on `benchmark` (worktree exists:
  `/private/tmp/claude-501/DCR-benchmark`, or `git switch benchmark`); scene
  builders + current solver on `native-dynamic-constraint` (this worktree).
  First step of Week 2 is **B0: reconcile** — port/merge the five paper-scene
  builders (`scenes/reduced_{truck,dinner_table,ledge,cargo_network,fem_rigid_cargo}.py`)
  and the current clamp (`dcr/avbd/_solver/passivity.py`) onto `benchmark` so
  X-harnesses drive them. (½ day; risk of drift between branches — do this
  once, early, and freeze.)
- **Fixed config unless a task sweeps it:** PAPER_CONFIG — relax 0.7 (AVBD) /
  0.25 (XPBD), 16×4 iterations×substeps, symplectic modal stepper, h=1/120,
  fixed seeds. CPU-only (no CUDA assumed anywhere in this plan).
- **Determinism check (applies to every CSV):** rerun one grid cell twice;
  byte-identical rows required. If not, find the nondeterminism before
  trusting any number.

### E1 — Passivity ablation across paper scenes  ⟵ the title claim
- **Serves:** §4.4 (currently a TODO — the headline section); Table 2 rows
  "Passivity ΔE_m≤ηΔE_r" and "Passivity ablation"; video shot V1.
- **Needs:** B0 done; `benchmarks/paper_eval/x1_passivity/run_blowup_figure.py`
  + `run_robustness_clamp.py` extended to take a `--scene` builder; scenes:
  ledge, dinner, stack (stack already done). Compute: grid of
  {AVBD,XPBD} × budgets {8×2, 16×4, 32×4} × relax {0.25, 0.7, 1.0} × clamp
  {off,on} = 36 cells/scene × ~1–3 min ≈ **1–2 h/scene**, T=3 s sim each.
- **Procedure:** (1) run grid per scene, logging per rigid step: E_modal,
  E_rigid_loss, cumulative injected, clamp activations, α★; (2) render
  blow-up figure per scene; (3) write §4.4 from the CSVs.
- **Output format:**
  - `benchmark/runs/x1_<scene>/grid.csv` — columns:
    `scene, solver, iters, substeps, relax, clamp, steps, E_modal_peak,
    E_modal_final, inject_ratio, n_clamp_activations, alpha_min, nan_flag`.
  - `paper/figures/x1_ablation_<scene>.pdf` — log-y cumulative ΔE_modal vs t,
    two arms (OFF red, ON blue), one panel per budget; plus a budget×relax
    heatmap of `inject_ratio` (OFF).
  - Paper: §4.4 prose (~0.5 col) + Table 2 cells flip `pend→✓` with numbers.
- **Validation:**
  1. ON: **all** cells satisfy cumulative ΔE_m ≤ η·ΔE_r + ε_tol, asserted
     programmatically over the full run (stageE invariant style), not sampled.
  2. OFF: injection occurs at the low budget (expected ≥1 cell per scene);
     record the max factor per scene.
  3. Inertness claim: AVBD @ 32×4, relax 0.7 → **0 activations** (the
     "monitor-only on descent-class" claim); XPBD shows activations (the
     "load-bearing on stationarity-class" claim). If AVBD activates, the §3.3
     framing must be corrected — that is a *finding*, not a failure.
  4. Transcription guard: stack cell reproduces the committed 119,534× within
     rounding.
- **Effort:** 3 d. **Risk:** dinner ablation may be dominated by topple
  events. **Fallback:** report ledge+stack fully; dinner as
  "n/a — topple-dominated, see §limitations" (an honest n/a beats a pend).

### E2 — FEM ground truth for the ledge scene (G1)
- **Serves:** Table 2 "Modal displ. L2" + "Distant-response fidelity" ledge
  cells; the cross-scene accuracy claim; video shot V4.
- **Needs:** X3 pattern (`x3_ground_truth/{fem_modal_support.py,scene_and_gt.py}`),
  `dinner_scene_gt.py` as template; a shared `FEMModel` of the ledge support;
  native arm with `support_basis="fem"` (basis = eigenmodes of the *same*
  discrete operator — the shared-operator trick, discretization bias cancels).
  Compute: GT implicit Newmark h=5×10⁻⁵ ≈ 18 min per 1.2 s ⇒ ledge ~3 s ×
  3 h-rungs × 2 impact configs ≈ **4–6 h, batch overnight**. t_settle ≥ 2.5 s
  before impact (dinner lesson).
- **Procedure:** (1) build shared operator; (2) unit-check basis (below);
  (3) run native h-ladder 1/120→1/960 + GT; (4) extract u_y at fixed probe
  set, mid-deflection ratio, ring frequency (FFT of probe trace).
- **Output format:** `benchmark/runs/x3_ledge/convergence.csv` — columns:
  `h, ratio_mid_deflection, f_ring_native_hz, f_ring_gt_hz, L2_uy_rel`;
  paper: one row-block in a per-scene convergence table (X3-B style).
- **Validation:**
  1. ratio → 1.0 ± 0.05 at h=1/960 (slab precedent 0.56→1.02).
  2. ring frequency native vs GT within 1 %.
  3. **GT self-trust:** rerun one rung with GT h halved (2.5×10⁻⁵); u_y field
     change < 2 % — else the GT, not the method, is the bottleneck; report it.
  4. **Shared-operator unit test:** assert native ω_j == `eigsh(K,M)` of the
     GT operator to 1e-10 (guards silent basis divergence).
  5. Scope guard: measure only the pre-topple window if the boulder topples;
     the small-displacement limitation already covers this — cite it.
- **Effort:** 3–4 d wall (mostly batch). **Risk:** ledge is the
  strong-coupling scene; large rotations violate the linear-modes regime.
  **Fallback:** report the pre-topple window + state regime; do NOT drop the
  scene silently.

### E3 — Distant-response falloff per scene, metric re-cut (G2 + R2)
- **Serves:** the Claim-2 story ("constraints handle distance automatically,
  no C·r^-β fit"); replaces the current Fig. 2 whose center/right panels
  contradict the caption; Table 2 "Distant-response fidelity" row.
- **Needs:** `x2_vs_dcr/run_x2.py` generalized to dinner (exists as sweep) and
  ledge; three arms: native / paper-DCR (Eq. 10 IIR + Δv=d_max/h) / GT (F);
  R2 metric: per-body **peak deflection-field response** u_y (or ring energy
  ∫E_m dt), plus the old peak-jump as a secondary panel. Compute: reuse E2 GT
  runs where possible; dinner GT sweep exists (3 drop points).
- **Output format:**
  - `benchmark/runs/x2_<scene>/falloff.csv` — columns:
    `scene, drop_point, body_id, distance_m, resp_native, resp_dcr, resp_gt,
    toppled_flag`.
  - Rebuilt `paper/figures/response_vs_distance.pdf` — GT black dashed, native
    blue, DCR orange; log-y; toppled bodies marked ×, not plotted at a fake
    floor; caption claims ONLY what the panels show.
- **Validation:**
  1. **Quantified falloff agreement:** Spearman rank correlation between
     native and GT per-body responses ≥ 0.8 per drop point (replaces
     eyeballed "reproduces the falloff"). Print ρ in the caption.
  2. DCR arm steeper at distance: compare fitted log-slopes (fitting for
     *description* is fine; the method itself stays fit-free).
  3. Floor discipline: no plotted point may sit at a sensor floor; either the
     metric resolves it or the body is excluded with the exclusion counted in
     the caption ("n=3 toppled excluded").
  4. If ρ < 0.8 anywhere: soften Claim 2 to the regimes where it holds
     (`experiment_plan.md` §6.2 anticipated exactly this) — wording ready in
     the fallback note there.
- **Effort:** 3 d. **Risk:** metric re-cut changes the story quantitatively.
  **Fallback:** claim scoped to dinner-center + slab reference scene.

### E4 — Momentum-drift probe (G4) + clamp-momentum interaction
- **Serves:** Table 2 "Momentum drift" row (all cells); the §3.1
  "momentum-consistent by construction" sentence; answers the anticipated
  reviewer question "the α-scaled kick breaks third-law pairing — how much?"
- **Needs:** new read-only probe (pattern:
  `benchmarks/network/report_sheldon_contact_forces.py` — analysis-only, no
  solver change). Formulas: P=Σmv, L=Σ(Iω + x×mv) (+ modal momentum is zero
  by mass-orthogonality of free-body modes to rigid translations — state
  this). Scenes: all five; plus one **gravity-off** two-body ring-exchange
  scene for a clean conservation figure. Compute: minutes.
- **Procedure:** log per step; three configs: modes-off (null), modes-on
  clamp-off, modes-on clamp-on with η tiny (1e-6) to force α★<1 activity.
- **Output format:** `benchmark/runs/momentum/<scene>.csv` — columns:
  `t, Px, Py, Pz, Lx, Ly, Lz, alpha_star, clamp_active`; paper: one summary
  table row (max |ΔP|/|P₀|, max |ΔL|/|L₀| per scene) + 2 sentences in §4.
- **Validation:**
  1. Gravity-off, clamp inactive: drift at solver tolerance (report the
     number; expect ≤1e-8 relative for the shared-multiplier coupling).
  2. Forced-clamp config: measured momentum deviation while α★<1 — reported
     honestly in §3.3 as the cost of the cap (expected tiny: the kick lives in
     modal space; rigid P/L unaffected — *verify*, don't assert: the modal
     back-reaction on bodies within the same row is what's scaled).
  3. Null check: modes-off run drift equals baseline rigid solver drift.
- **Effort:** 1–2 d. **Risk:** none structural — worst case is an honest
  number in Limitations.

### E5 — Modal sub-step sweep (the 7× characterization, R2)
- **Serves:** §4.3 re-cut; the fidelity-vs-passivity figure (candidate money
  figure); Limitations bullet upgraded from hypothesis to measurement.
- **Needs:** solver flag to sub-step the modal q-block (Eq. 5 loop) at
  n × solver rate with contact set frozen per rigid step — small solver
  change, needs a `# DEVIATION:` comment and a parity test at n=1. Dinner
  center drop; substep n ∈ {1,2,4,8,16}. Compute: <1 h.
- **Output format:** `benchmark/runs/substep/dinner.csv` — columns:
  `substep, peak_jump_ratio_vs_gt, uy_ratio_vs_gt, ms_per_step,
  n_clamp_activations, E_injected_cum`; figure `substep_recovery.pdf`:
  (a) amplitude ratio vs n; (b) scatter of energy-ratio (x) vs amplitude
  fidelity (y): our points at each n, DCR's point (2.6×, ~1.0), GT at (1,1).
- **Validation:**
  1. Parity: n=1 reproduces the shipped solver bit-for-bit (or to 1e-12).
  2. Passivity invariant asserted at every n.
  3. Interpretation gate: amplitude ratio rises toward 1 with n ⇒
     band-limiting **confirmed**, deficit becomes a documented cost knob;
     flat ⇒ hypothesis **rejected** — then check kick timing vs contact
     detection and the engaged-gating window before writing anything.
- **Effort:** 1 d. **Risk:** flat curve forces a §4.3 rewrite — better now
  than from a reviewer.

### E6 — Friction interaction with the bound
- **Serves:** scope-precision of the passivity claim (Codex point 4); one
  paragraph in §3.3 + one Table row.
- **Needs:** stack scene with Coulomb friction (CPU XPBD coupler has
  friction; AVBD arm as available), μ ∈ {0, 0.2, 0.5, 1.0}. Check whether the
  ledger's s = M_q⁻¹ΣĜᵀj includes tangential impulses.
- **Output format:** `benchmark/runs/friction/stack_mu.csv` — columns:
  `mu, solver, E_modal_final, inject_ratio, n_clamp, bound_violated`;
  paper: 2–3 sentences + row.
- **Validation:** bound holds ∀μ with tangential impulses **included in the
  ledger**; if the current ledger is normal-only, either (a) add tangential
  projection (small change, DEVIATION comment) or (b) scope the printed claim
  to normal impulses explicitly. Silence is the only unacceptable outcome.
- **Effort:** 1 d.

### E7 — Runtime table completion + scaling
- **Serves:** §4.5 (new); the "interactive rates" claim; Table 2 runtime row.
- **Needs:** `x5_perf/run_perf.py` on road, stack, FEM-cargo (dinner, ledge
  committed); arms: R (modes off), D (DCR one-way), ours-AVBD, ours-XPBD;
  mode-count scaling k ∈ {8,16,24,48} on dinner; 3 repetitions; record
  machine spec (CPU model, cores, RAM, Python/numpy versions).
- **Output format:** `benchmark/runs/x5/all_scenes.csv` — columns:
  `scene, arm, k_modes, ms_per_step_mean, ms_per_step_std, rt_factor_at_120hz,
  clamp_overhead_ms`; paper: runtime table + one scaling sentence
  ("modal block is O(k): measured X µs/mode/step").
- **Validation:** (1) std/mean < 10 % over reps; (2) reproduces committed
  58/29 ms within 15 % (else machine differs — pin one benchmark machine and
  state it); (3) clamp overhead consistent with the committed 2–5 %.
- **Effort:** 1–2 d (road scene must exist — see E-road note below).

### E8 — ΔE_rigid < 0 edge case
- **Serves:** correctness of Eq. 8 as printed; one sentence in §3.3; a unit
  test.
- **Needs:** `dcr/avbd/_solver/passivity.py` + `tests/`; construct a step
  where the rigid solve *gains* energy (position-based solvers can) ⇒
  E_max < 0 ⇒ `b² + 2aE_max` may be negative.
- **Output format:** pytest `tests/.../test_passive_alpha_negative_budget.py`
  covering: E_max<0 & b≥0 → α★=0; E_max<0 & b<0 → largest α with
  ΔE(α)≤E_max if it exists else 0; a,b→0 degeneracies. Paper: one sentence
  defining behavior.
- **Validation:** tests pass; grep that the implementation actually guards the
  discriminant (if it already does, the task is transcription).
- **Effort:** 0.5 d.

### E9 — Schur-vs-gated-block-GS measurement (promote the §3.2 insight)
- **Serves:** a named results subsection (§4.6) for the paper's most
  practitioner-memorable claim: cross-term Schur injects at truncated
  budgets; explicit under-relaxed block-GS stays passive.
- **Needs:** both couplers exist (Route-A/monolithic history; the Schur arm is
  the rejected design — resurrect behind a flag, no default change); stack
  scene, 8×2 budget.
- **Output format:** `benchmark/runs/schur/stack.csv` — columns:
  `coupler, iters, substeps, E_modal_t (series), inject_ratio`; small figure:
  E_modal(t), two arms, one budget annotation; ~0.4 col of prose.
- **Validation:** Schur arm injects at 8×2 and converges to parity at 32×4
  (the "identical in a converged solve" sentence must be *shown* at high
  budget, not just asserted); block-GS passive at both.
- **Effort:** 1 d. **Slippable** to camera-ready if Week 3 overruns — the
  §3.2 prose already carries the claim qualitatively.

### E-road — Road scene disposition (explicit descope)
Road (truck/crate/cones) gets: runtime cell (E7), qualitative video shot (V5),
and **n/a with a footnote** in accuracy rows ("large-slab GT beyond
penalty-contact budget; qualitative only"). Fill the `\todo{N}` body count in
Table 1 from the built scene. No GT run. — This is a deliberate scope
decision; record it in the paper as such.

---

## 3. Writing tasks

### W1 — Transcription of committed evidence (do FIRST — 1–2 d)
- **Serves:** kills the "mostly pending" impression this week.
- **Needs:** `benchmark` branch CSVs + `docs/paper_eval/{x0..x7,STATUS,AUDIT_BRIEF}.md`.
- **Procedure:** create `paper/NUMBERS.md` ledger; write §4.4 skeleton from
  X1 (stack), X7 subsection (restitution: DCR→2.6×, native ≤1 ∀ε_r — this is
  a *measured, ours-vs-DCR* result and currently absent from the paper!),
  runtime paragraph from X5, X2 falloff numbers into §4.2/related.
- **Output format:** updated `sections/40_results.tex`; `NUMBERS.md` with one
  line per printed number: `<value> ← <csv path>:<col>:<row>`.
- **Validation:** zero numbers in §4 without a NUMBERS.md line; the
  0.90/1.03-vs-0.89/1.02 discrepancy resolved from CSV.

### W2 — Claims/framing pass (R1+R2 wording) — DONE for title; §3.3/§4 pass 1 d
Title changed. Remaining: abstract sentence on "interactive rates"; §4.5
split-sentence (validated path vs device path); §4.3 reorder per R2.
**Validation:** the W7 "real-time" grep; abstract ≤ 200 words.

### W3 — Full prose (3 d)
Per-section spec (long-paper budget ~9–10 pp incl. figures, excl. refs;
current draft is 6 pp with skeleton prose — expect +2–3 pp of content):
- **Abstract** (150–200 words): problem (1 sent) → mechanism: modes as native
  compliant DOFs, shared multiplier (2) → the bound ΔE_m≤ηΔE_r enforced
  per-step (1) → results with numbers: blow-up factor OFF, 24/24 ON, GT
  convergence →1.0, restitution ≤1 vs DCR 2.6×, ms/step (2–3) → venue hook (1).
- **Intro** (~0.75 pp): keep the fixed skeleton; expand each paragraph;
  contributions list unchanged (claim discipline: `novelty_positioning.md`
  do/don't is binding).
- **Related work** (~1 pp): expand the 4 seeded paragraphs; **add citations**:
  Müller et al. 2020 *Detailed Rigid Body Simulation with XPBD* (the host
  formulation — omission would be flagged), Macklin et al. 2019 *Small Steps
  in Physics Simulation* (band-limiting / iteration-vs-substep discussion),
  Tournier et al. 2015 *Stable Constrained Dynamics* (compliance
  regularization neighbor), Andrews et al. 2022 contact-simulation survey
  (SIGGRAPH course) for breadth. Each new cite gets one positioning sentence,
  not a list dump.
- **Method:** add §3.3 paragraphs: (a) ΔE_rigid<0 handling (E8), (b) friction
  scope (E6), (c) momentum cost of an active clamp (E4.2). Keep every
  equation-number citation per CLAUDE.md.
- **Results:** rewritten by E1–E9 outputs per the specs above.
- **Conclusion/Limitations:** resolve the `\todo` bullets — restitution
  decision is X7 (measured, cite it); ABD secular-buildup stays as future
  work; add the E5 outcome to the band-limiting bullet.
- **Bibliography:** complete every `VERIFY` field against ACM DL / publisher
  pages (volume/number/pages/authors: Relles full name from the CGF page;
  Giles/Diaz first names from the SIGGRAPH'25 page); add the four new
  entries. **Validation:** zero `VERIFY` strings left in `references.bib`;
  every entry renders without BibTeX warnings; DOIs resolve.

### W4 — Format (DONE; camera-ready deltas parked)
Remaining checklist parked for Oct: drop `review,anonymous`, add rights
commands from the ACM email, real ORCID, `\acmSubmissionID`, teaser figure,
de-anonymize, delete draft helper macros (`\todo,\note,\pend`…), kill all
remaining overfulls (currently 7 minor).

### W5 — Publication figure pass (2–3 d)
- **Standards (every figure):** vector PDF from matplotlib (`savefig .pdf`),
  embedded fonts ≥ 7 pt at print size, colorblind-safe arm palette held
  constant across ALL figures — native **blue**, GT **black dashed**, DCR
  **orange**, clamp-OFF **red**, variant **teal**; no in-image titles (the
  caption carries it); no diagnostic annotations ("Dinner is served",
  "bonus:", internal config strings); units on every axis; log axes labeled
  as such.
- **Inventory:** Fig.1 forces+ring (re-render from sheldon CSVs, split into
  (a–d) with the discriminator panel visually first), Fig.2 falloff (E3
  output), Fig.3 ablation (E1), Fig.4 substep/fidelity-vs-passivity (E5),
  Fig.5 Schur (E9, optional), teaser strip (from V-shots).
- **Output format:** one generator script per figure under
  `benchmarks/paper_fig/fig_<name>.py` reading only committed CSVs (never
  live sim) — figures regenerate with `make figures`.
- **Validation:** regenerating from a clean checkout reproduces the PDF
  byte-similar; each caption's every claim visible in its own panel (W7
  audit); no raster below 150 dpi effective.

### W6 — Supplementary video (3–4 d; capture scripts start Week 2)
- **Serves:** MIG expects it; several claims are *motion* claims.
- **Needs:** viser/polyscope offscreen capture (infra exists per
  `docs/sheldon_report`, all-scenes viser); ffmpeg; storyboard below.
- **Shot list (target 2:00–2:30 total, 1920×1080 60 fps, H.264 CRF≈18,
  ≤200 MB incl. any extra clips):**

| # | shot | source scene | dur | proves | overlay |
|---|---|---|---|---|---|
| V1 | clamp OFF blow-up vs ON, side-by-side, same seed | stack (E1 config) | 20 s | the bound is load-bearing | "η=1, 8×2 budget; OFF injects 10⁵×" |
| V2 | top-cube ring network on/off + amplitude inset | stack | 20 s | two-way through the network | "|a| ≡ 0 with network off" |
| V3 | dinner drop: native vs all-FEM GT split-screen + falloff plot inset | dinner (E3) | 30 s | GT agreement, no fitted attenuation | drop-point marker |
| V4 | ledge topple: rigid-only vs ours vs GT | ledge (E2) | 25 s | strong-coupling case | |
| V5 | road drive-by, ours vs rigid-only | road | 20 s | breadth (qualitative) | "qualitative — see paper §4" |
| V6 | fidelity-vs-passivity chart animation (E5) | plot | 15 s | the trade vs DCR | |

- **Output format:** `supplementary/video.mp4` + `supplementary/README.txt`
  (scene list, config, anonymized); per-shot capture script
  `benchmarks/video/shot_v<N>.py`.
- **Validation:** every overlay claim traceable to a CSV (NUMBERS.md);
  **anonymization**: no usernames, repo URLs, window chrome, or file paths in
  frame; metadata scrubbed (`exiftool -all=`); plays in VLC+QuickTime; total
  supplementary ≤ 200 MB.

### W7 — Adversarial pre-submission audit (1 d, gate to submission)
Checklist, all must pass:
1. **Caption-claim audit:** for each figure, list caption claims; each must be
   visible in that figure alone (the current Fig. 2 fails this today — E3
   fixes).
2. **Number audit:** every printed number has a NUMBERS.md provenance line.
3. **Marker grep:** `grep -rE "TODO|\\\\todo|\\\\note|\\\\pend|VERIFY" sections/ references.bib` → empty.
4. **Overclaim greps:** "real-time" (per R1), "first" (allowed only in "first
   ... to our knowledge" for the (Passive,RT-AL) cell — and prefer not at
   all), "guarantee" (must always be scoped to contact→modal transfer).
5. **Anonymity grep:** author names, USC, repo URLs, `docs/...` internal path
   references (rewrite draft notes), acknowledgment section absent.
6. **Build:** `latexmk -C && latexmk -pdf` clean; 0 undefined refs/citations;
   overfull count 0 (or each ≤ 2 pt and invisible); page count ≤ 10 excl.
   refs.
7. **Fresh-eyes pass:** one full read-through simulating the reviewer
   checklist in §7; every §7 item must point at its evidence.

---

## 4. Calendar with go/no-go gates

| week | dates | tasks | GATE (end of week) |
|---|---|---|---|
| 1 | Jul 7–13 | W1 transcription, B0 branch reconcile, E4 momentum, E5 substep, E8 edge case, start E1 | **G-A:** §4.4 has real numbers (stack); NUMBERS.md exists; E5 interpretation known (band-limiting confirmed or rewrite triggered) |
| 2 | Jul 14–20 | E1 (ledge/dinner), E2 ledge GT (overnight batches), E3 falloff re-cut, E6 friction, E7 runtime, V-shot capture scripts | **G-B:** Table 2 has zero `pend` that isn't a deliberate n/a; E2 ratio →1 or scoped; E3 ρ known |
| 3 | Jul 21–27 | W3 prose, W5 figures, W6 video edit, E9 if on schedule | **G-C:** complete PDF ≤10 pp, complete video draft |
| 4 | Jul 28–Aug 4 | freeze CSVs, regenerate all figures from committed data, W7 audit, supplementary packaging, EasyChair registration + paper ID into the header | **G-D (Aug 4):** W7 all-green |
| — | **Aug 5** | **SUBMIT** (buffer to Aug 7 AoE) | |

Gate rule: a red gate consumes the buffer first, then descopes in this order:
E9 → dinner-ablation cell → E6 → V5/V6 shots. The non-negotiables are E1
(title claim), E7 (title claim), E3 (figure-vs-claim integrity), W6 V1–V3,
and W7.

## 5. Risk register

| # | risk | likelihood | impact | mitigation / trigger |
|---|---|---|---|---|
| 1 | E5 shows no amplitude recovery (band-limiting wrong) | med | §4.3 story rewrite | scheduled Week 1 precisely so the rewrite fits; fallback framing: "deficit structural to solver-rate implicit integration; sub-stepping does not recover it; DCR recovers it only by violating passivity (X7)" — still a coherent trade story |
| 2 | E2 ledge GT diverges (large-displacement regime) | med | lose one accuracy column | pre-topple window scoping; limitation already written |
| 3 | AVBD clamp turns out active at production budget on a new scene | low | §3.3 dichotomy wording | report as finding; the bound's value *increases* |
| 4 | branch drift makes X-harnesses disagree with current solver | med | silent wrong numbers | B0 reconcile FIRST + determinism rerun check on every grid |
| 5 | page overflow > 10 pp after W3 | med | cuts | park E9 subsection + move per-scene convergence tables to supplementary |
| 6 | MIG'26 CFP differs from 2025 (page limit/template) | low | rework | re-check CFP when posted (watch mig.siggraph.org/2026 weekly, Week 1 onward) |

## 6. Definition of done (the reviewer checklist, all must have evidence)

1. Bound shown **load-bearing** (OFF blow-up / ON passive / high-budget inert)
   on ≥ 2 paper scenes + stack — E1 figure + table.
2. Title matches measurement: "interactive rates" + runtime table for all
   scenes with R/D baselines — E7.
3. Accuracy led by a GT-convergent metric; 7× deficit characterized (E5
   curve) and contrasted with DCR's 2.6× passivity violation (X7) — the
   trade-off figure.
4. Momentum measured, including under an active clamp — E4.
5. Falloff claim quantified (Spearman ρ printed) and every caption claim
   visible in its own figure — E3 + W7.1.
6. Friction/edge-case scope stated, not silent — E6 + E8.
7. Video shows V1–V3 minimum — W6.
8. Zero draft markers, zero unverified bib fields, anonymous, ≤ 10 pp — W7.
