# Paper-Evidence Experiment Plan — "DCR as a Native Constraint" Follow-Up

> Execution plan for closing the publishability gaps identified in the 2026-07-02 audit.
> Read `CLAUDE.md` first, then this file top to bottom before writing any code.
> Work happens on branch lineage of `avbd-native-dynamic-constraint`.

## Why this plan exists (context for the executing agent)

The intended paper claims three things:

1. **C1 — Constraint-native reformulation:** DCR's modal response path rewritten as a
   dynamic modal constraint (reduced coordinates `q, q̇` are first-class solver DOFs)
   inside two constraint-based solvers (AVBD `Solver6DOF`, XPBD `SolverXPBD`).
2. **C2 — Passive by energy:** the modal support cannot inject energy; the coupling is
   energy-bounded every step.
3. **C3 — True two-way coupling:** one shared contact multiplier both excites the modes
   and pushes back on rigid bodies (transpose-consistent by construction).

The audit found the implementation of C1 solid, C3 strongly evidenced for XPBD and
config-dependent for AVBD, and **C2 currently false of the artifact**: there is no
enforced energy bound in the native path (the `ΔE_modal ≤ η·ΔE_loss` machinery exists
only in the legacy DCR-coupler path, `dcr/dcr/dcr_world.py:281` /
`dcr/benchmark/energy_log.py:117`, default OFF), and the robustness matrix
(`benchmarks/material_sweeps/out/robustness_matrix.csv`) documents XPBD injecting up to
167× the impactor energy at budget (8,2). Also missing at paper level: a head-to-head
against original DCR, a coupled-scene ground truth, a consolidated performance story,
and scene breadth (4 scenes vs the paper's 7).

The stages below (X0–X7) close those gaps. **X0 → X1 are prerequisites for everything
else. X7 is small — do it early. X2/X3/X4 are independent of each other after X1.
X5/X6 come last.**

```
X0 (pin config) ──► X1 (enforced passivity) ──► X2 (vs DCR)
                                            ├─► X3 (ground truth)
                                            ├─► X4 (solver divergence)
                                            ├─► X7 (restitution sweep, small)
                                            └─► X5 (perf) ──► X6 (breadth scenes)
```

---

## Cross-cutting rules (binding for every stage)

1. **All CLAUDE.md rules apply**: cite equations (paper Eq. N / foundation §N) in every
   implementing docstring, `# DEVIATION:` for any divergence, `cfm`/`restitution` naming
   (never bare `eps`), CPU/numpy reference first, no new dependencies, test before
   claiming, stage-per-branch commits.
2. **Three code paths exist — never conflate them** (this has burned prior sessions):
   - *Native dual solvers* (the paper's subject): `dcr/avbd/_solver/solver_6dof.py`
     (AVBD) and `dcr/avbd/_solver/solver_xpbd.py`. Modal `q` is a native DOF.
   - *Deleted reduced coupler*: `reduced_coupled_avbd.py` era. Its docs
     (`docs/avbd_native/stage1..6_*.md`, `dynamic_constraint_port.md`) describe removed
     code. Do not resurrect or benchmark it.
   - *Legacy DCR patch coupler*: `dcr/dcr/passive_dcr.py` + `dcr_world.py` (the
     one-way "distant kick" path). Used ONLY as the baseline arm in X2/X7.
3. **Body-index offset:** scene-handle (DCR) body indices ≠ native-solver row indices.
   Use the `_solver_body_idx` mapping (see `scripts/probe_native_energy_loop.py:104-117`).
   A prior bug logged a flat-zero impactor force because of this exact mistake.
4. **FFT hygiene:** ring-frequency measurement must high-pass away the contact-settling
   envelope before the FFT (moving-average high-pass, ~1.5 ring periods) and use a fine
   measurement rate (`hz = max(600, 24·f₁)`), exactly as
   `benchmarks/material_sweeps/sweep_common.py:measure_ring_freq()` does. At default
   relax with no high-pass, AVBD falsely appeared not to ring (a retracted early claim).
5. **Symplectic-stepper scope:** `dcr/modal/symplectic_stepper.py` (implicit midpoint)
   is CPU-host, non-cargo only; `cuda` + symplectic falls back to host, and AVBD+cargo
   under symplectic raises `NotImplementedError`. Any stage touching cargo or CUDA must
   state which stepper actually ran.
6. **Known pre-existing failures are out of scope to fix** (30 total: 1 truck
   lumber-stack host box-box, 5 `tests/avbd/` old track, 24 `tests/stageDV/`). Never
   let them count against a stage; never silently "fix" them either.
7. **Output layout:** each stage is a self-contained benchmark package under
   `benchmarks/paper_eval/<stage>/` following the proven `benchmarks/material_sweeps/`
   pattern (imports `dcr`/`scenes` read-only; all solver settings applied at runtime;
   generator scripts + `out/` CSVs + PNGs + a `README.md` with the numbers). Per-stage
   narrative goes in `docs/paper_eval/<stage>.md`.
8. **Config manifest per figure:** every PNG/CSV gets a sibling `<name>.config.json`
   recording solver, relax, iters, substeps, stepper, h, frame count, seed, scene, git
   SHA. A figure that cannot be regenerated from its manifest fails its stage.
9. **Honest reporting:** report inversions, dead cells, and blow-ups as-is (the existing
   benchmarks set this precedent — e.g. ledge/AVBD two-way 0.59× is reported
   "not cherry-picked"). The paper's credibility strategy is the honest failure map.

---

## Stage X0 — Pin the paper configuration + determinism protocol

**Goal:** one frozen configuration for every headline number; eliminate the
"which relax was this run at?" problem (the energy-loop probes ran at source defaults,
the material sweeps at relax 0.7 — a paper cannot mix them) and the same-config
reproducibility wrinkle (ledge/XPBD 16×4 gave 245.8× on a 220-frame pass vs 207.6× on
a 170-frame pass of the *same* config).

**Steps:**
1. Create `benchmarks/paper_eval/paper_config.py` exporting `PAPER_CONFIG`:
   - `relax = 0.7` (AVBD `_modal_relax`, XPBD `modal_relax` / `_support_block_relax`
     as `sweep_common.py` already wires them), `iters = 16`, `substeps = 4`,
     `h = 1/120`, `stepper = "symplectic"`, gravity 9.81.
   - Justify each value from `benchmarks/material_sweeps/out/robustness_matrix.csv`
     (relax 0.7 + budget ≥ (16,4) is the documented safe operating point) in the
     module docstring.
   - Fixed probe protocol constants: `settle_s = 0.30`, `n_frames` per probe type
     (single canonical value per probe — pick the longer of the previously-used pair),
     RNG seed, FFT window rule.
2. Add `apply_paper_config(solver)` — runtime override helper (reuse/lift the override
   code from `sweep_common.py`; do not modify solver source defaults).
3. Re-run the three existing headline probes at exactly `PAPER_CONFIG` so all paper
   numbers share one setup:
   - energy loop (`scripts/run_native_energy_loop_verification.py`) — 3 scenes × 2 solvers;
   - slab material sweep (`benchmarks/material_sweeps/run_slab_sweep.py`);
   - scene sweep (`run_scene_sweep.py`).
   Write results to `benchmarks/paper_eval/x0_baseline/out/`.
4. Determinism check: run the shelf/XPBD energy-loop probe 3× with the pinned protocol;
   two-way ratio must agree run-to-run within ±5% (if not, find and pin the
   nondeterminism source — frame count, contact ordering, seed — before proceeding).

**Accept:** one config file; re-generated baseline tables at the pinned config with
manifests; 3× repeat within ±5%. **Deliverables:** `docs/paper_eval/x0.md` with the
re-baselined two-way/passivity/ring tables side-by-side against the old
mixed-config numbers.

---

## Stage X1 — Enforced passivity in the native path (the C2 mechanism) + adversarial re-run

**Goal:** make "passive by energy" a per-step guarantee instead of an empirical safe
region, then show the 90-config robustness matrix goes green. This is the only stage
that modifies solver code, and the paper's headline claim depends on it.

**Mechanism (port of the validated E-stage α-cap math to the native q-block —
`dcr/modal/passive_inject.py` has the reference implementation; foundation §6, §15):**
1. **Work estimator (spec §10 impulse form).** Per substep, for the support's contact
   rows, accumulate the work delivered *to* the modal DOFs through the shared
   multipliers:
   `W_c→m = Σ_rows (Φ_rᵀ j_r) · q̇_mid`, with `j_r` the row's impulse this substep and
   `q̇_mid = ½(q̇_pre + q̇_post)`. Include friction rows. Cite spec §10 in the docstring.
2. **Per-substep audit.** With modal energy `E_m = ½ q̇ᵀ Mq q̇ + ½ qᵀ Kq q` (the
   solver's own definition — `solver_6dof.py:2295`, `solver_xpbd.py:1029`), require
   `ΔE_m(substep) ≤ W_c→m + tol` where ΔE_m excludes the stepper's own free evolution
   (compute the homogeneous step's energy change first, then attribute the remainder
   to contact; the symplectic stepper conserves, so for it the homogeneous term is ~0
   and the audit is clean — state this).
3. **Clamp on violation.** Scale the contact-attributed velocity update
   `Δq̇ = q̇_post − q̇_free` by `α ∈ [0,1]` solving the passive-α quadratic
   (`a = Δq̇ᵀ Mq Δq̇`, `b = (Mq q̇_free)·Δq̇`, bound `= max(W_c→m, 0) + tol`), i.e.
   the exact `passive_alpha` form from foundation §6. Position term `q` has already
   moved inside the solve; if you clamp velocity only, mark it
   `# DEVIATION: position-energy not re-clamped (foundation §15 is velocity-level);`
   and show in the test that the residual position-term violation is below `tol`.
4. **Global ledger + assertion.** Per rigid step accumulate
   `E_total = Σ E_rigid + E_m + E_grav_potential` and cumulative dissipation. New test
   asserts `E_total(t) ≤ E_total(0) + ε_tol` for the full run of a drop scene
   (not sampled — every step), per CLAUDE.md rule 7. Keep the clamp behind a flag
   (`enforce_modal_passivity`, default ON for paper runs) so before/after is one switch.
5. **Adversarial re-run.** Re-run `benchmarks/material_sweeps/run_robustness.py` with
   the clamp ON, extended grid: add budget (4,1); restitution 0→0.9 if/where the native
   solvers support it (see X7 risk note); mass ratios 10⁻²–10²; h ∈ {1/60, 1/120, 1/240,
   1/480}. Output `benchmarks/paper_eval/x1_passivity/out/robustness_clamped.csv`.
6. **Inertness check.** In the previously-OK cells, two-way ratios with clamp ON must be
   within a few percent of clamp OFF (the clamp must not eat the ring in the safe region).

**Accept:** (a) zero INJECT/BLOWUP flags in the clamped matrix (DEAD/DETUNE cells may
remain — they are a coupling-quality issue, not an energy-safety issue);
(b) ledger assertion test green on all 4 scenes × 2 solvers at `PAPER_CONFIG`;
(c) inertness within tolerance; (d) parity: clamp path has a numpy reference and the
device path (if touched) matches to fp64 roundoff.
**Deliverables:** before/after robustness heatmaps (the paper's money figure),
`docs/paper_eval/x1.md`, new tests in `tests/avbd_native/test_passivity_clamp.py`.

**Fallback (only if the mechanism proves unworkable):** re-scope claim C2 to
"energy-monitored with a characterized safe region" and say so in `docs/paper_eval/x1.md`
— do not silently ship the weaker claim under the stronger title.

---

## Stage X2 — Head-to-head vs original DCR (the C1 "follow-up" evidence)

**Goal:** the first figure a reviewer of a DCR follow-up looks for: same scenes,
rigid-only vs paper-DCR vs native constraint.

**Baseline arm:** the in-repo paper-DCR implementation (`dcr/dcr/modal_dcr.py`,
IIR Eq. 10 + Δv injected into the Schur RHS of Eq. 2 — note it injects *through the
solver*, not as a post-solve kick). `scripts/run_stage7.py` and `docs/stage7.md` show
the working entry points ("Dinner is served", spatial-attenuation scene).

**Steps:**
1. **Matched scenes.** Build paper-eval variants of dinner, shelf, ledge (+ truck if
   time allows) runnable by *both* stacks: identical geometry, masses, materials
   (use paper Table 2 values where the scene mirrors a paper scene: e.g. table
   E=1.1 GPa, ν=0.3, ρ=770; 20 modes for the DCR arm as in the paper). The DCR arm
   runs in its own Stage-1/5 world (as published); the native arm runs at
   `PAPER_CONFIG`. This is a *method-level* comparison (like the original paper vs
   SOFA), not a solver-controlled ablation — state that in the doc.
   *Optional secondary arm* (only if cheap): re-implement the DCR kick inside the
   native solver (Δv into its velocity state) for a solver-controlled ablation; mark
   `# DEVIATION:` and keep it out of headline figures.
2. **Arms:** (a) rigid-only (response machinery off), (b) paper-DCR modal path with
   paper defaults, (c) native constraint (X1 clamp ON).
   *Dinner-scene geometry fix (verified against `scenes/reduced_dinner_table.py`):*
   as built, the pot drops dead-centre `(0,0)` and the 4 plates sit symmetrically at
   `(±0.32, ±0.28)` — all **equidistant** (0.425 m), candles all at 0.673 m — so there
   is NO distance spread to plot a falloff against. For the response-vs-distance curve,
   drop the pot **off-centre** (e.g. over plate_0, giving plate distances 0 / 0.56 /
   0.64 / 0.85 m). The pot xz is hard-coded, so either add an off-centre drop position
   to the scene builder OR reposition the pot AND sync the solver body state at runtime
   (moving only the DCR body will not move the solver's internal `x`/`_X`).
3. **Metrics per scene:**
   - distant-object peak displacement and peak KE vs geodesic/euclidean distance from
     impact (paper Fig. 10 style curve). NOTE the native path has NO spatial-attenuation
     term — verified: `grep` of `dcr/avbd/_solver/` finds no `r^-β`/geodesic/attenuation;
     Eq. 14 (`C·r^-β`, `dcr/dcr/spatial_dcr.py` + `geodesic.py`) is legacy-coupler-only.
     Any falloff in arm (c) is purely modal, through `Φ(x_probe)·q`. This is a genuine
     C1 advantage to MEASURE, not just assert: the paper's dinner scene is itself a
     MODAL scene (Eq. 14 was only for the LARGE objects — truck ground, cliff), so the
     native constraint reproduces the dinner attenuation with zero `C/β/r₀` fitting.
     Two honesty caveats to carry into the writeup: (i) modal spatial variation ≠ Eq. 14
     and does NOT extend to the large-object regime (low modes give smooth long-
     wavelength standing-wave variation, not localized traveling-wave decay — precisely
     why the paper needed the heuristic there); (ii) the dinner support currently uses a
     SYNTHETIC local-bump basis (`make_debug_reduced_shelf_support`, bumps placed at each
     contact zone), so the falloff is partly bump-placement-shaped — whether it is
     PHYSICALLY correct needs true FEM eigenmodes + the X3 ground-truth comparison;
   - cumulative injected vs dissipated energy per arm (ledger from X1 for arm c;
     `dcr/benchmark/energy_log.py` for arm b);
   - back-reaction observables arm b structurally lacks: support sag under a moving
     load; slab re-ring when a launched object lands (count + magnitude);
   - hand-tuned parameter count per arm (DCR: C, β, d_max, per-scene response scale;
     native: relax + budget, shared across scenes);
   - wall-clock overhead vs arm a.
4. **Repeated-impact energy test.** Drop N=10 objects in sequence on the same support;
   plot total system energy over the whole run for arms b and c. Expectation: arm b
   drifts upward (the paper's admitted non-conservation), arm c stays bounded (X1
   guarantee). If arm b does *not* drift at paper defaults (ε_r = 0.15 is small),
   report that honestly and rely on X7 to expose the effect at higher restitution.
5. Side-by-side MP4s (or GIFs matching the stage-7 tooling) for each scene.

**Accept:** response-vs-distance curves for all three arms on ≥3 scenes; energy-ledger
traces; capability table (two-way observables present/absent); videos.
**Deliverables:** `benchmarks/paper_eval/x2_vs_dcr/`, `docs/paper_eval/x2.md`.

---

## Stage X3 — Coupled ground truth vs full FEM (the correctness anchor)

**Goal:** show the two-way *magnitude* is right, not just present. This is the anchor
both `prompts/avbd_native_dcr_followup_spec_v2.md` ("internal passivity is necessary
but not sufficient") and the original paper's future-work paragraph demand.
`docs/proposal_modal_response_as_constraint.md` already lists it as the open milestone.

**Ground-truth stack (no new dependencies):** the Stage-7 `CoupledFEMRigidSim`
pattern — full FEM slab (`dcr/fem/fem_model.py`, Newmark trapezoidal
`dcr/fem/newmark.py`) at `h_fine = 1e-4` (paper used 1e-5; 1e-4 was the documented
tractable deviation), penalty contact against rigid bodies. Its rigid bodies are
1D-vertical (mass, y, vy) — acceptable because the chosen scene's response is
vertical-dominant; state this limitation up front. If time allows, upgrade to 3-DOF
planar rigid; do not block the stage on it.

**Steps:**
1. **Scene:** shelf-drop (smallest): impactor + 1–2 resting books on the slab. Matched
   initial conditions; record the impactor's contact-entry velocity in the native run
   and verify the GT run matches it before comparing responses.
2. **Ground-truth runs:** full-FEM slab at the *same* E, ν, ρ, thickness as the native
   scene's synthetic/reduced basis. Verify the GT slab's own f₁ against
   `benchmarks/material_sweeps/fem_reference.py` (already EB-validated to ~4%) before
   trusting it as truth.
3. **Compare vs native (at `PAPER_CONFIG`):** bystander lift trace `y(t)`, launch KE,
   slab midpoint deflection trace, ring spectrum (same FFT protocol), contact-force
   profiles. Report peak-amplitude error %, frequency error %, phase drift over 1 s.
4. **Mode-count convergence:** native with k ∈ {1, 2, 4, 8, 16, 32} modes → error-vs-k
   curve against the FEM reference. This doubles as the modal-truncation ablation.
4b. **Spatial-falloff validation (settles the X2 "automatic attenuation" claim).**
   Multiple probe points at increasing distance from the impact; compare the native
   response-vs-distance profile to the FEM ground truth's. Do this with **true FEM
   eigenmodes** (`dcr/modal/modal_analysis.py`), NOT the synthetic local-bump basis —
   the bump basis's falloff is partly placement-shaped, so it cannot by itself prove the
   attenuation is physical. Deliverable: native-vs-FEM falloff overlay + the k at which
   the spatial profile (not just f₁) converges. This is the evidence that upgrades X2's
   "no attenuation term needed" from a verified mechanism to a validated result.
5. **Wall-clock:** GT minutes vs native ms per simulated second (the original paper
   quotes ~30 min for <1 s of SOFA — this ratio is the value proposition).

**Accept:** qualitative match (video overlay); fundamental-mode quantities within
~10–20%; error monotonically shrinking with k; wall-clock table.
**Deliverables:** `benchmarks/paper_eval/x3_ground_truth/`, `docs/paper_eval/x3.md`,
trace-overlay + error-vs-k figures.

---

## Stage X4 — Solver-divergence study + ledge/AVBD dead-coupling autopsy

**Goal:** the same constraint currently behaves very differently across hosts (ring
magnitudes ~3 orders apart, `docs/avbd_native/native_dual_solver.md:187-193`; XPBD
impactor chatters ~17 rebounds where AVBD hits once; ledge/AVBD two-way is 0.59× and
*worsens* with budget — 0.03× at 32×8). Either tame this or attribute it cleanly. A
paper claiming solver-generality cannot leave it unexplained.

**Steps:**
1. **Chatter quantification (no modal DOFs).** Single impactor on a *rigid* slab, both
   solvers: count rebounds, log the per-step impulse train vs iteration budget and
   restitution setting. Establishes the hosts differ before any modal coupling exists.
2. **Impulse-train equivalence (the key experiment).** Record each solver's per-step
   support-row impulse train from the real coupled scene; feed *both* trains offline
   into the identical modal ODE (`dcr/modal/symplectic_stepper.py`, same Mq/Kq/Dq).
   If offline modal responses match their in-solver counterparts and differ between
   trains, the divergence is 100% host contact behavior and the constraint itself is
   solver-agnostic — a clean, publishable attribution. If they *don't* match their
   in-solver counterparts, the constraint implementations differ — find out why
   (relax, ordering, friction rows) before writing anything.
3. **Ledge/AVBD autopsy** — one probe per hypothesis, logged in the doc as a
   hypothesis table (the `avbd_dcr_coupling_findings.md` §13 format):
   (a) mode-shape magnitude `Φ(x_c)` at the resting object's feet vs the shelf scene
   (geometry hypothesis); (b) warm-start ablation (does λ warm-starting absorb the
   kick?); (c) relax sweep at fixed everything else; (d) normal-projected support
   velocity at the object's contacts (is the ring motion orthogonal to the normal?).
4. **Principled relax.** Attempt to derive the modal-block under-relaxation from the
   coupled block's spectral radius (it is an SOR factor on a block solve) instead of
   the empirical 0.7. If a derivation works, add it as an auto-default with a test; if
   not, say so and keep the robustness map as the practitioner guidance.

**Accept:** the impulse-equivalence figure (offline-replay vs in-solver modal traces);
chatter statistics table; ledge/AVBD either fixed (two-way > 2× at `PAPER_CONFIG`) or
explained with a named, probe-backed mechanism in the doc.
**Deliverables:** `benchmarks/paper_eval/x4_divergence/`, `docs/paper_eval/x4.md`.

---

## Stage X5 — Performance and scaling consolidation

**Goal:** one table at the level of the original paper's Tables 1/3 (they report
0.2–27.5 ms modal-response compute per scene, 20 modes, meshes to 7k verts). Current
numbers are scattered across five docs at inconsistent configs.

**Steps:**
1. **Consolidated table** at `PAPER_CONFIG`: scene × solver × device
   (numpy / warp-CPU / cuda) → ms/step with breakdown (contact | modal block |
   coupling), plus **overhead vs rigid-only** (same scene, support constraint off).
   Note the symplectic/CUDA fallback (rule 5) in the device column.
2. **Scaling sweeps:** modes k ∈ {4, 8, 16, 32, 64} (cost here, accuracy from X3);
   resting-body count N ∈ {10, 100, 1000} on one large support (debris field — build
   once, reuse as X6's rockfall-at-scale); contact count as measured.
3. **Worst-case frame** (impact spike), not just steady-state mean; report both.
4. **CUDA-graph capture on/off** for the resident paths.
5. **Report the honest crossover:** warp-CPU currently beats CUDA at nb ≤ 17
   (`native_dual_solver.md:378-397` — single-thread GS-bound, fp64 at 1:64 on the
   RTX 3060); find the N where the GPU wins using the N-sweep. That is a useful
   practitioner result, not a weakness — write it that way.
6. Cite X3's ground-truth wall-clock as the speedup denominator vs full FEM.

**Accept:** every scene at `PAPER_CONFIG` ≤ ~8 ms/step on its best backend (120 Hz
real-time) or an honest statement of which are not; complete table with manifests.
**Deliverables:** `benchmarks/paper_eval/x5_perf/`, `docs/paper_eval/x5.md`.

---

## Stage X6 — Breadth: paper-parity scenes + two-way-only phenomena

**Goal:** match the original's seven-scenario spread and demonstrate phenomena one-way
DCR cannot produce. Build each scene in `scenes/` following the
`reduced_scene_common.py` conventions; each ships an MP4, an energy ledger, a timing
row (into X5's table), and one scalar metric.

**Scenes (in order of evidentiary value):**
1. **Wrench-on-roof analog (friction-mediated distant response).** Impact far from a
   resting object; the object *slides* rather than lifts. Exercises the support
   friction path (support tangential velocity `Φ(x_c)·q̇` entering the Coulomb cone)
   which no current benchmark touches. Metric: slide distance vs impact energy, three
   arms as in X2. Risk: if the native support friction rows do not see support
   velocity, this scene will expose it — that is the point; fix inside the constraint
   (cite spec §8) rather than faking the demo.
2. **Washing-machine periodic forcing.** 60 s run, oscillating body on a floor
   support, second support chained (floor → fridge) if feasible. Metrics: steady-state
   response amplitude; **flat cumulative-energy ledger over 60 s** — the long-horizon
   passivity demo X1 makes provable.
3. **Scaffold two-level.** Impact upstairs, objects downstairs; response separation
   across distance. Metric: per-level peak response vs distance.
4. **Rockfall at scale.** Ledge with 50–100 debris bodies (shared with X5's N-sweep).
   Metric: ms/step + no INJECT flags at scale.
5. **fem_rigid tumbling cargo on shelf** (already built —
   `scenes/reduced_fem_rigid_cargo.py`): deformable cargo on deformable support,
   zero-penetration check. Re-run at `PAPER_CONFIG` (note stepper scope, rule 5).
6. **Stack-on-support — decision, not demo.** The 4-high lumber stack topple is the
   *host* AVBD box-box friction instability (pre-existing: `native_dual_solver.md:17`;
   XPBD's own stack holds at 0.28°). Decide: either scope stacks out of the paper's
   demo set with one honest sentence, or fix the host solver on a separate branch
   first. **Do not** let a known host energy leak sit inside a passivity paper's demo
   reel, and do not attempt the host fix inside this plan.

**Accept:** scenes 1–4 running at `PAPER_CONFIG` with their metrics + ledgers; the
stack decision documented. **Deliverables:** `scenes/paper_*.py`,
`benchmarks/paper_eval/x6_scenes/`, `docs/paper_eval/x6.md`, MP4s under `docs/paper_eval/`.

---

## Stage X7 — Restitution–energy consistency sweep (small; do early)

**Goal:** directly answer the original paper's admitted flaw — at restitution → 1 the
DCR formulation double-counts (full bounce *and* vibration energy; their §5.4: *"If the
coefficient of restitution approaches one we will have perfectly elastic collision
response and should not be distributing energy to vibrations"*). One quotable figure.

**Steps:**
1. **Check restitution support in the native solvers first.** If `Solver6DOF`/
   `SolverXPBD` have no restitution model, add the standard velocity-level Newton
   restitution to the contact rows (small, well-understood; `# DEVIATION:` citing the
   paper's ε_r usage and CLAUDE.md naming `restitution`/`eps_r`). If that is too
   invasive, run the native arm at ε_r = 0 only and sweep the DCR arm — with an
   explanatory note. Decide and document; do not fake the sweep.
2. Sweep ε_r ∈ {0, 0.15, 0.3, 0.5, 0.7, 0.9, 0.95} × {paper-DCR arm, native arm} on
   one drop scene (impactor on slab, one resting object).
3. Log post-impact total energy / pre-impact total energy per run (ledger from X1).
4. Figure: ratio vs ε_r, two curves, horizontal line at 1.0. Expected: DCR arm crosses
   1.0 at high ε_r (they kept ε_r = 0.15 precisely to dodge this); native arm stays
   ≤ 1.0 at every ε_r with the X1 clamp.

**Accept:** the figure + CSV with manifests; native arm ≤ 1.0 everywhere (if it is
not, that is an X1 bug — stop and fix X1). **Deliverables:**
`benchmarks/paper_eval/x7_restitution/`, `docs/paper_eval/x7.md`.

---

## What NOT to do (scope guards)

- Do **not** fix the host AVBD box-box stack bug inside this plan (decision-only, X6.6).
- Do **not** touch the spatial-attenuation path (DCR's large-object path) — the paper
  scopes it out explicitly; one sentence in the writeup, no code.
- Do **not** benchmark or resurrect the deleted reduced coupler.
- Do **not** modify `benchmarks/material_sweeps/` in place — extend under
  `benchmarks/paper_eval/` (the old outputs are the "before" evidence for X1).
- Do **not** claim beyond the foundation §13 list; §14 "claims to avoid" is binding.
  In particular: with the X1 clamp the claim is "the modal path cannot gain more energy
  than contact delivers" — it is *not* "the whole scene is provably passive" while the
  host box-box issue exists; word the paper accordingly.
- Do **not** average away failures. DEAD/DETUNE cells, inversions < 1×, and any
  post-clamp violations go in the tables as-is.

## Definition of done (claims → evidence map)

| Claim | Evidence required | Stage |
|---|---|---|
| C1 constraint-native reformulation | head-to-head vs paper-DCR on ≥3 matched scenes; capability table | X2 |
| C1 solver-generality | impulse-train equivalence figure + divergence attribution; ledge/AVBD resolved or explained | X4 |
| C2 passive by energy | per-step clamp + full-run ledger assertion; zero INJECT/BLOWUP in clamped robustness matrix; 60 s flat ledger; restitution sweep ≤ 1.0 | X1, X6.2, X7 |
| C3 two-way coupling (existence) | freeze-q̇ counterfactuals + shared-multiplier calibration at pinned config | X0 (re-baseline) |
| C3 two-way coupling (correctness) | full-FEM ground-truth traces within 10–20%; error-vs-k convergence | X3 |
| Practicality | consolidated perf table; overhead vs rigid-only; N/k scaling; crossover | X5 |
| Breadth | ≥6 scenarios incl. friction-mediated + periodic forcing | X6 |

Every stage ends with: `pytest tests/ -q` introducing **0 new failures** (baseline: 30
pre-existing), the stage's figures regenerable from manifests, and the stage doc
written. Only then move on.
