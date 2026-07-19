# MIG 2026 Short Paper — Execution Plan (drafted 2026-07-18)

Target: ACM SIGGRAPH MIG 2026 short paper. Submission window **25 Jul – 7 Aug
2026, 23:59 AoE** (from the 2026-07-18 sweep; votes errored on budget —
**re-verify on mig.siggraph.org before relying on it**, along with page limit,
template, double-blind status, and supplementary-video rules).
Venue: 11–13 Dec 2026, Clemson Innovation Campus, N. Charleston SC.

The long-paper unlock (device-resident governor + governed-path FEM validation +
forced-γ<1 GPU regression) is explicitly OUT of this plan's critical path; it is
the post-submission track (or the journal/long resubmission).

---

## 1. The claim (frozen text to defend)

Thesis (Codex's "defensible today" form, tightened):

> We show that the classical two-way rigid–modal contact row exhibits sharply
> solver-dependent energy behavior under fixed local iteration budgets.
> Projection-based XPBD amplifies modal energy by up to 1.2×10⁵ relative to
> incident rigid kinetic energy in an adversarial budget sweep; an
> augmented-Lagrangian (AVBD) realization exceeds the supply bound only
> marginally and only in the most starved cells (worst 1.7×), while an implicit
> sequential-impulse realization stays within it in every cell of the same
> sweep. We introduce a
> cumulative, source-referenced modal-storage projection that bounds XPBD's
> gain across all tested budgets, and validate the reduced modal response
> against a matched full-FEM operator. A separate GPU-resident AVBD path
> reaches interactive rates for selected scene/budget configurations while
> monitoring, rather than actively enforcing, the bound.

Contribution bullets (3 max, short-paper discipline):
1. **Measurement**: the same contact row (a transcription of the established
   Zheng-James velocity-level law) run in three fixed-budget solver classes,
   with a K-convergence study showing injection is a truncation artifact
   (→ 0 at the converged reference).
2. **The invariant + projection**: cumulative directional storage bound,
   E_m^n − E_m^0 ≤ η·Σ_k max(ΔE_rigid-loss^k, 0), enforced by a reservoir
   ledger + γ-projection of realized modal state; funding is source-referenced
   (contact dissipation only, gravity-work-compensated).
3. **Validation & cost**: reduced response vs matched full-FEM operator;
   activation demo (ungoverned injecting run → governed bounded run);
   CPU/GPU timings with honest qualification.

### Mandatory wording rules (from both adversarial sweeps + Codex passes)

- NEVER claim: the row/gap/deformed contact point, two-way coupling, modes as
  contact DOFs, momentum consistency, "first modal DOFs in XPBD" (say "as
  *contact* DOFs"), the under-convergence-injection *observation* (cite
  arXiv 2603.16424), "makes it trustworthy" (say "satisfies a prescribed
  cumulative modal-storage bound"), unqualified "real-time".
- 10⁵× always defined: **peak modal energy / incident rigid kinetic energy**,
  adversarial low-budget cells, not production settings.
- Invariant always in cumulative notation (above), never the per-step form.
- Real-time always qualified: at 16×4, shelf/ledge meet 8.33 ms; truck
  (8.87 ms) and dinner (9.20 ms) do not; all scenes meet it at ≤16×2
  (dinner 4.65 ms → 1.79×). GPU path = read-only ledger (monitored).
- Impulse backend = baseline/validation and the converged oracle. Its box-box
  ride rectification (rigid-energy pumping, invisible to the modal ledger) is
  a named limitation — the invariant governs energy entering modal storage,
  not energy spuriously created in rigid DOFs.
- New must-cite adversaries: arXiv 2603.16424 (finite-iteration injection
  observation + passivity-by-construction, bilateral), arXiv 2602.08094
  (energy-*controllable* integration, bidirectional targets), Zobel et al.
  2025 MSD (FFRF in Unity, penalty + staged), RAS 2024 10.1016/j.robot.2024.
  104650 (modes+modal-derivatives reduction in XPBD).

---

## 2. Evidence inventory

### Already in hand (cite/condense, no new runs)
- XPBD 24-cell adversarial matrix: injects in 12/24 (5.5e4–9.2e6 J; peak
  119,534× incident KE); clamp bounds all cells; inert at high budget.
  **SUPERSEDED on this branch by E-S1b (2026-07-18): 8/24, peak 1.19534e5
  reproduced exactly. The four lost cells are dinner — the dinner scene was
  materially redefined on this branch (DCR §5.1 duplication), so the paper's
  dinner worst case 5.1e3 belongs to the superseded scene. See
  `docs/mig2026_results_ledger.md` §E-S1b.**
- AVBD: 20/20 cells passive without clamp (host); device 20/20 + 18/18
  (N-sweep) with read-only ledger. **CONTRADICTED on the 24-cell matrix
  (E-S1b): AVBD injects in 2/24 cells (dinner 4×1, worst 1.7003). The §1
  thesis sentence was rewritten accordingly on 2026-07-18.**
- Activation demo: `--inject` preset (2×1 budget) ~20× injection → clamp
  flips it passive.
- η sweep, zero-pending matrix, stress N=16→512 (~√N, 8×1 real-time ∀N).
- FEM ground-truth validation: **3 scenes reported in the paper** (slab, ledge,
  dinner); the branch harness supports 5 (truck, ledge, shelf, dinner, cargo),
  which is repository coverage rather than five reported accuracy scenes.
- Impulse backend (branch `impulse-native-constraint`): 6 scenes ledger-
  passive, statics ledger exact (m·g/3m·g/2m·g/m·g ≤3%), ON/OFF causality,
  payload pre-sag; 14.9–32.4 ms/step numpy CPU.
- Perf: GPU 5.6–9.2 ms @16×4; budget ladder 1.26→9.23 ms; symplectic CPU
  correctness path 11–34 ms.

### New experiments required (all CPU, all this branch or benchmark branch)

**E-S1 — impulse 24-cell adversarial matrix** (~1 day incl. runs)
Port the X1 cell harness to `solver_kind="impulse"`; same scenes/budgets as
the XPBD/AVBD matrices. Output: per-cell ledger verdict + peak ratio.
Acceptance: the three-solver table in the paper is symmetric (same cells, same
metric). If impulse injects anywhere → the claim sentence already says
"solver-dependent"; add the cell count and show the ledger bounds it (run
enforcement on those cells). Pin ONE machine (ARM Mac) for every reported
number — the ARM/x86 FP divergence on chaotic stacks is a known confound.

**E-S2 — K-convergence sweep with the impulse oracle** (~1 day)
Deterministic drop scene (shelf or cargo impactor; avoid chaotic stacks).
Curves: peak E_modal/incident-KE vs iteration budget K for xpbd (K=1..32),
avbd (1..32), impulse (2..64), plus impulse @ K=500 as the converged
reference λ* (the Zheng-James-regime stand-in, same code path).
Acceptance: XPBD's curve decays toward the oracle line as K grows; figure
directly supports "truncation creates it, convergence cures it".

**E-S3 — post-projection contact validity** (~1 day)
Starved XPBD budget so γ<1 fires repeatedly. Per clamp-active step, log:
(a) max gap violation immediately after the γ-scale, (b) next-substep
corrective normal impulse magnitude vs steady-state, (c) λ variance (chatter
proxy), (d) net momentum change. Report medians + worst case in Limitations
(one short paragraph + one number each). This closes the hole a contact
reviewer will probe: scaling (q, q̇) after the solve moves the deformed
surface without re-solving contact.

**A0 — verifications (half day)**
- Count the FEM-GT scenes actually in the results section; reconcile with the
  5-scene harness; state the real number.
- Sheth-Lu-Yu-Fedkiw SCA 2015 full text remains **pending** for the user to
  fetch; do not freeze a resolved novelty verdict about it in Week 1.
- Confirm MIG format: page limit, acmart template variant, double-blind,
  video specs, EasyChair link.

---

## 3. Paper skeleton (assume ~4 pages + refs; adjust after A0)

1. **Introduction** (~0.75 page): Z-J law (established, cited as such) →
   game solvers truncate → measured solver-dependent injection (teaser
   figure) → the cumulative bound → contributions. Distinguish 2603.16424
   (observation + bilateral passivity-by-construction) and 2602.08094
   (bidirectional energy targets) here, not buried in related work.
2. **Row + invariant** (~1 page): the transcribed row (one equation, cited),
   cumulative invariant + reservoir + γ-projection, source-referenced funding
   rule. No derivation bloat — point to the long version/tech report.
3. **Results** (~1.5 pages):
   - F1 (teaser): render + modal-energy trace, ungoverned XPBD exploding vs
     governed bounded, same scene/budget.
   - F2: K-convergence sweep with the impulse-oracle line (E-S2).
   - F3: 3-solver × 24-cell matrix heatmap (existing XPBD/AVBD + E-S1).
   - F4: FEM-GT overlay (existing deflection trace).
   - T1: perf table with the qualified real-time statement.
4. **Limitations + outlook** (~0.5 page): stable-not-accurate when the clamp
   bites (say it plainly); normal-only, e=0; ledger does not govern
   rigid-side pumping (ride rectification, measured); enforcement is
   host-side — device governor + governed-path validation = announced next
   step (the long-paper trajectory). Post-projection validity numbers (E-S3).
5. **Video** (supplementary, high value at MIG): 60–90 s — payload A/B
   (two-way sag/detune vs one-way), network ON/OFF causality, `--inject`
   flipping INJECTING✗ → PASSIVE✓, one GT overlay. All existing viser scenes.

Where it lives: `paper` branch worktree (orphan, latexmk, Overleaf bridge;
never commit code there). New `main_short.tex` reusing `sections/` content by
condensation — do not fork the section files; write fresh condensed text.

---

## 4. Timeline (Jul 18 → Aug 7)

**Week 1 (Jul 18–24) — evidence freeze**
- D1: A0 verifications (GT count, Sheth PDF, MIG format).
- D1–2: E-S1 impulse matrix. D2–3: E-S2 K-sweep. D3–4: E-S3 validity probe.
- D5: freeze all numbers into a results ledger file; freeze the claim text
  against them (any surprise → claim wording updates NOW, not in week 3).

**Week 2 (Jul 25–31) — draft**
- D6–8: full draft of main_short.tex + all figures scripted (paper_fig/).
- D9: red-team pass — read the draft ONLY against §1's wording rules and the
  known attack ("coupling is Z-J, observation is 2603.16424, what's left is a
  clamp" — the §3.3-style distinction goes in the intro).
- D10: hand to PI; start video capture in parallel.

**Week 3 (Aug 1–7) — polish + submit**
- D11–13: PI revisions; reproducibility pass (scripts, seeds, machine pinned,
  commit hashes in the paper's repro note).
- D14: video final cut; supplementary packaging.
- D15–16 (buffer): submit ≥24 h before the Aug 7 AoE deadline.

**Parallel, non-blocking (long-paper track, only if week 1 finishes early):**
device-resident γ-projection prototype on compshare 4090 — with the explicit
understanding (Codex point) that kernels alone are not the unlock; the unlock
is a practical injecting case where the governed solve is bounded AND
meaningfully accurate AND cheaper than iterating out of the failure, plus
FEM validation rerun on the actual governed device path and a forced-γ<1
GPU regression under graph capture.

---

## 5. Risks & fallbacks

| Risk | Response |
|---|---|
| E-S1 finds impulse injection cells | Fine — strengthens "solver-dependent"; report + govern them |
| K-sweep noisy | Use the deterministic drop; average 3 seeds; report bands |
| MIG format ≠ assumed 4 pages | Skeleton scales ±1 page via Results figure count |
| Sheth 2015 turns out closer than the refuted record suggests | Impulse backend framed as baseline already — absorb via related work, claim unaffected (cap is the claim) |
| GT scene count = 3 in paper | State 3; the 5-scene harness is a repo fact, not a paper claim |
| Deadline info wrong (unverified votes) | A0 D1 re-verification; everything shifts with the real date |

---

## 6. Review-response revision plan (2026-07-18 five-lens panel on `main_short.pdf`)

Panel verdict: borderline / weak reject (2,3,2,3,3; mean 2.6). Central attack:
the paper measures the incident-energy ratio R = peak E_mod / peak incident
rigid KE but repeatedly claims in Eq.-(2) (invariant) language. **Our own
ledger already flags the underlying hole** — E-S1b caveat 1: with the clamp
OFF, Eq.-(2) accounting exists only for the impulse backend (XPBD vacuous,
AVBD absent) — so the abstract's "AVBD exceeds the supply bound (1.7×)" has
no supporting measurement today; 1.7 is R. MIG has **no rebuttal** (A0), so
every blocker is preempted in the submission or not at all.

Binding constraints: measurement- and text-side only — **no solver behavior
changes** (single exception R8, explicitly gated); ARM M4 only; every new
number frozen in `docs/mig2026_results_ledger.md` with command + commit;
page target ≤6 content pages excl. refs (current build ≈4 incl. refs, so
~2 pages of headroom per A0). **No GPU is required for any item below.**

### 6.1 Priorities

| ID | Panel blocker | Work | Cost |
|---|---|---|---|
| R0 | consistency list | text-only fixes in `main_short.tex` (all pre-verified vs ledger) | 0.5 d |
| R1 | #1 metric ≠ invariant | OFF-run Eq.-(2) utilization for all 3 solvers, new heatmap panel, prose re-base | 1–1.5 d |
| R2 | #2 ledger definition | exact ΔE_rig/η/γ definitions in-paper + measured return-transfer + Limitations caveat | 0.5–1 d |
| R3 | #3 apples-to-apples | solver/parameter table + substep-only sweep + row-evaluation accounting + residuals | 1–1.5 d |
| R4 | #4 truncation proof | XPBD K→500 self-convergence + state-level agreement metric | 0.5 d |
| R5 | #5 usefulness | governed-vs-oracle accuracy + AVBD validity rows in Table 1 + triptych frames | 1–1.5 d |
| R6 | novelty positioning | +3 refs (passivity observer, energy tanks, FEPR) + 3 framing sentences | 0.25 d |
| R7 | cost honesty | baseline + % overhead; device paragraph labeled and named | 0.25 d |
| R8 | stretch, GATED | deviation-referenced projection or post-projection re-solve | 2–3 d + full re-freeze |

### 6.2 R0 — text-only corrections (each verified against the frozen ledger)

1. Conclusion "1.2×10⁵, 1.7, and 1.0" → "… and 0.53" (E-S1b impulse worst
   0.531421; §3.1 already says 0.53 — the conclusion contradicts the body).
2. Abstract "exceeds the supply bound only marginally (1.7×)" → incident-
   benchmark wording until R1 adjudicates (no AVBD OFF-run Eq.-(2)
   measurement exists; E-S1b caveat 1). Same audit for §1's thesis sentence
   in this plan — wording updates when the R1 number lands (D5 rule).
3. Fig.-2 caption "injection threshold 1" → "incident-energy threshold 1";
   keep §3.1's "intensity diagnostic, not the enforced invariant" and make
   abstract/§3.1/conclusion use one consistent vocabulary.
4. §3.1 "three orders of magnitude better behaved … at the same budget" →
   qualify per scene: worst-over-scenes at 4×1 is XPBD 1.2×10⁵ vs AVBD 1.7,
   but in the table scene AVBD (1.18/1.70) is *worse* than XPBD (≤0.37).
   State both directions; the panel caught the flip.
5. "all 72 measured cells" (abstract, contribution 2, §3.1) → "72 cells
   (60 distinct configurations — the impulse relaxation rows are bit-identical
   by construction, cf. Fig. 2 caption)".
6. Timing paragraph: the truck scene is never introduced (repo name leaking;
   long paper calls it road). Define both extra timing scenes in one clause
   or cut them. Scope "All numbers … one machine (Apple M4, CPU only)" to
   exclude the device timings, and name the device hardware (RTX 4090).
7. State η = 1 for every experiment, at Eq. (2) ("η∈(0,1]; we run η=1, the
   least restrictive member").
8. Delete the abstract's "the quantity a contact reviewer will ask for" clause.
9. Abstract "decays … over six orders of magnitude" → "the gap to a converged
   reference shrinks by six orders of magnitude" (the ratio itself falls five:
   2.96×10⁴ → 0.300; the gap 2.96×10⁴ → 2.7×10⁻²).
10. Normalize the 21.6 mm worst penetration by slab thickness/span and by the
    unclamped static sag of the same cell.

Acceptance: grep pass over `main_short.tex` for "supply bound", "injection
threshold", "72", "truck", "M4", "orders of magnitude"; `paper/NUMBERS.md`
cross-check; rebuild clean.

### 6.3 R1 — measure Eq. (2) itself with the governor OFF (the load-bearing fix)

Extend `benchmarks/paper_eval/x1_passivity/run_solver_matrix.py` with
measurement-only wrappers (the E-S3 non-perturbation pattern) that log
per-substep rigid mechanical energy (translational + rotational, all bodies,
gravity-compensated with the ledger's own formula replicated offline) and
E_mod. Compute per cell, clamp OFF:

    U = (E_mod^n − E_mod^0) / (η · Σ_k max(ΔE_rig^k, 0))   and the margin.

- Cross-validate the offline accounting against the impulse backend's live
  monitor (24 cells must agree to round-off) and AVBD's monitor-only default;
  that agreement is the acceptance test for the offline formula.
- New figure content: a second heatmap row/panel — OFF-run U per cell, log
  scale, threshold 1 = actual Eq.-(2) violation. Governed U saturates at
  1.000 in clamped cells; report "R = 1.22 with U = 1.000" in text as the
  two-metric distinction, demonstrated rather than argued.
- Re-base every "within/exceeds the supply bound" sentence on U; R stays as
  the severity diagnostic. Add the two-line remark the panel asked for: in a
  single-drop scene the RHS of Eq. (2) is bounded by a small multiple of the
  incident KE, so R far above that multiple certifies violation — which is why
  10³–10⁵ cells are unambiguous injection while 1.2–1.7 cells need U.
- Claim risk to absorb NOW: AVBD's two table-scene cells may show U < 1 (that
  scene's many rigid–rigid contacts make gross loss large) → the AVBD sentence
  weakens to the benchmark form and the story becomes *cleaner* ("only XPBD
  violates the invariant"). If U > 1 the current sentence becomes supported.
  Either outcome publishes; wording waits for the number.

Acceptance: finite U in all 72 OFF cells; impulse cross-check exact; figure
builds; a prose audit finds zero R/U conflations left.

### 6.4 R2 — pin the ledger down in-paper

- State from code (with file anchors recorded in the results ledger): the
  exact ΔE_rig formula and gravity-work compensation, energy terms included
  (translational + rotational KE, all rigid bodies), η = 1, E_mod^0 handling,
  and the closed-form γ (energy is quadratic in γ).
- Name the guarantee precisely: a cumulative, gross-loss-funded **storage
  ceiling** on the modal subsystem — not contact-port passivity, not a signed
  per-interface transfer bound. Keep "source-referenced" only next to its
  definition.
- Add the recycling caveat to Limitations: modal→rigid return work can later
  be re-counted as fresh positive loss (gross-sum semantics). Defuse it
  empirically: in the R1 instrumented runs, accumulate the modal→rigid return
  channel and report its cumulative magnitude as a fraction of Σ max(ΔE_rig,0)
  per cell. Report whatever the number is; expectation from prior transfer
  measurements is ≲1%, but the measurement decides.

Acceptance: a reader can recompute the reservoir from the paper alone;
Limitations carries the recycling caveat with a measured bound attached.

### 6.5 R3 — make the comparison controlled

- **T2 solver/parameter table** (~0.4 page): per formulation — update
  equation, compliance/penalty treatment, the implicit modal weight
  (M + hD + h²K)⁻¹ for impulse, what "relaxation" means per solver (and that
  impulse does not consume it), iteration structure/ordering, warm start,
  stabilization, h = 1/120, substep semantics, modal rank r = 24, modal
  damping, machine. Every entry sourced from code; anchors go in the ledger.
- **Budget accounting**: state row-evaluations per frame per cell
  (K × S × rows; the 4×1 → 32×8 axis is a ×4 work ladder) — the equal-work
  reading of the matrix, in the Fig. 2 caption or §3.1.
- **Substep-only sweep**: fixed K = 4, S ∈ {1,2,4,8}, shelf drop, all three
  solvers — the companion to E-S2 (which pins S = 1 and sweeps K). One small
  figure or a 4-row table; supplement if pages run out.
- **Residuals**: log an end-of-substep complementarity residual
  (‖min(C, λ)‖∞ or solver-native equivalent) vs K inside the E-S2 harness,
  measurement-only. Report in the K-convergence figure or caption.

### 6.6 R4 — close the self-convergence gap

- Extend E-S2's XPBD column to K ∈ {64, 128, 256, 500}: XPBD converged
  against *itself* must meet the impulse oracle (0.2735).
- At the top K, add state-level agreement: peak deflection, ring frequency,
  and L∞ of the modal-deflection trace vs the oracle trajectory — the panel's
  "states, not one scalar" demand.
- Pair with the R3 residual-vs-K curve.

Acceptance: |XPBD(500) − oracle| ≪ the K = 32 gap (2.7×10⁻²) on energy AND
state metrics; figure + caption updated; frozen in the ledger.

### 6.7 R5 — usefulness of the governed result

- **Accuracy quantification** at a moderate injecting cell (shelf 8×2,
  relax 0.7): ungoverned R = 53.7, governed realized 1.011, converged
  reference 0.2735 → energy error to the reference falls from ~200× to
  ~3.7×. Compute the deflection-trace counterpart (governed vs oracle).
  Frame honestly: the governor moves an unusable trajectory to within ~4× of
  the reference energy; it is a safety envelope, not an accuracy device.
- **Qualitative triptych** (one strip, three frames, same timestamp):
  ungoverned / governed / converged reference — reuses the committed video
  shot-list pipeline.
- **Table-1 completion**: port the E-S3 wrappers to the AVBD host
  (`solver_6dof`) and add the table-scene 4×1 rows — AVBD's two injecting
  cells, forced-clamp override exactly as in E-S1b caveat 3.
- Normalized penetration (R0.10) is presented here.

Acceptance: numbers frozen; Table 1 covers the AVBD problem cells; triptych
renders.

### 6.8 R6 — prior-art positioning of the governor

Add, with one framing sentence each: time-domain passivity observer/controller
(Hannaford & Ryu 2002), energy-tank/reservoir control from robotics
(e.g. Franken et al. 2011 / Ferraguti et al.), FEPR-style energy projection
(Dinev et al. 2018). Position: the reservoir is a passivity-observer
transplant with a gross-loss supply and a state-space (not force-space)
actuator; FEPR projects to preserve *total* energy, ours caps one subsystem's
storage. This answers "a simple energy clamp without prior-art positioning"
directly. These join, not replace, the four must-cite adversaries of §1.

### 6.9 R7 — enforcement cost, honestly

- Baseline step time next to the 0.8–2.9 ms ledger overhead, as a percentage,
  per scene/budget, CPU host.
- Device paragraph: name the GPU, keep "monitor-only" explicit, and state
  plainly that a device-resident *enforced* γ does not exist (it is the
  long-paper unlock per this plan's header). The panel's "device-side governed
  timing" ask is out of scope by design — say so in the paper, don't build it.
- **R7b — device-timing re-verification on compshare (USER-REQUESTED
  2026-07-18; planned; non-blocking for submission).** Status: probed
  2026-07-18 — pod unreachable (`ssh compshare` → connection closed; DNS
  still maps the stale pod hostname `cpod-1skopckdit1u.podtcp.compshare.cn`;
  same state as the 2026-07-13 pending note in `paper/NUMBERS.md`).
  **Blocked on the user starting the pod** (and updating `~/.ssh/config` if
  the restarted pod has a new host/port). Once up:
  1. Local: push `impulse-native-constraint` to origin (the branch is not on
     GitHub yet). Server: `cd ~/DCR && git fetch origin && git checkout
     impulse-native-constraint && git reset --hard
     origin/impulse-native-constraint`. The 2026-07-08 paper numbers were
     measured at `f94c850`; the re-verification runs the CURRENT submission
     commit.
  2. `~/dcr-venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_device.py
     --frames 200 --device cuda:0 --scenes shelf,ledge,dinner,truck`
     — one command, produces both `perf_device.csv` (16×4 table) and
     `perf_device_budget.csv` (budget ladder incl. the 16×2 row).
  3. Record in `docs/mig2026_device_ledger.md` (NEW separate file, so the
     results ledger's ARM-M4-only header stays true) with hostname, GPU,
     driver, warp version, commit, command; diff against the committed
     reference `x5_perf/out/perf_device.csv` (5.64 / 6.82 / 8.87 / 9.20 ms
     @16×4; 16×2 ledge 3.28 / dinner 4.65).
  4. If the band moves, update §3.5 and `paper/NUMBERS.md`; the qualified
     real-time sentence (shelf/ledge @16×4; all scenes @≤16×2) is re-checked
     against the fresh `rt_factor_120hz` column, never assumed.
  - While the pod is up (cheap, one script, unblocks a `NUMBERS.md` pending
    item, NOT part of this paper): rerun
    `benchmarks/paper_eval/er1_topple_control/run_topple_control.py`
    frozen-ring arm on the x86 host — long-paper §4.1 item, only if time
    allows.

### 6.10 R8 — STRETCH, gated (go/no-go ≈ Jul 27; default NO-GO)

> **GATED 2026-07-19: NO-GO** (called early, on evidence — see the R8 sections
> of `docs/mig2026_results_ledger.md`). The premise is measurably false for the
> option named here: deviation-referencing does NOT collapse the 21.6 mm case
> (22.03 → 19.89 mm). The variant that does (band-selective) is unenforceable in
> up to 37.8% of clamp-active substeps. It is also not novel — the paper's own
> Table 1 already carries Rayleigh α₁K, which is frequency-selective
> dissipation. Option (b), re-solve contact once, is UNTESTED and carried to the
> long paper. NO-GO condition satisfied by the Limitations sentence at `a74dfa6`.

The panel's constructive suggestion: scale deviations about the quasi-static
equilibrium, (q, q̇) ← (q_eq + γ(q − q_eq), γ q̇), or re-solve contact once
after projection. Either preserves load-bearing sag and should collapse the
21.6 mm worst case. It is a **solver behavior change**: requires re-freezing
the full 72-cell matrix, E-S3, and the teaser. GO only if R0–R7 are frozen
and ≥5 buffer days remain before Aug 7 AoE; on NO-GO, one Limitations
sentence names it as the identified next mechanism.

### 6.11 Timeline fold-in (supersedes §4 Week-2 D6–D8 content; dates unchanged)

- D6 (Jul 25): R0 + R2 text; R1 harness built, matrix re-run overnight.
- D7: R1 figure + prose re-base; R3 table sourced from code.
- D8: R3 sweep/residuals + R4 extension (hours of M4 runtime).
- D9: R5 (accuracy + AVBD validity rows + triptych). Red-team pass now also
  re-reads the draft against the five panel blockers, not only §1 wording.
- D10: R6 + R7; hand to PI. Week 3 unchanged; buffer absorbs R8 only on GO.

### 6.12 Risk additions

| Risk | Response |
|---|---|
| R1: AVBD U < 1 (no true violation) | Benchmark wording; "only XPBD violates Eq. (2)" is a cleaner story; keep 1.7 as diagnostic |
| R1: some XPBD 16×4 cell shows U > 1 | Report it; the injecting-cell count follows U, R kept as severity scale |
| Return-transfer not ≲1% | Publish the measured number; the caveat then stands on data |
| Residual probe perturbs the solve | E-S3 pattern: wrappers return values unchanged; clamp-count cross-check must reproduce |
| Page overflow > 6 | Demote first the substep sweep, then the triptych, to supplement |
| R8 tempts a late mechanism change | The gate is binding: no re-freeze capacity ⇒ NO-GO, limitation sentence instead |
