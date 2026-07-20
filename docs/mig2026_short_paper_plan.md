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
> cumulative modal-storage projection, funded by *measured gross rigid-side
> loss*, that bounds XPBD's gain across all tested budgets, and validate the reduced modal response
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
   ledger + γ-projection of realized modal state; funding is *measured gross
   rigid-side loss* (scene-wide, gravity-corrected, gross kinetic-energy loss
   of the rigid subsystem — an envelope on contact dissipation, not a
   measurement of it).
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
- The supply is **"measured gross rigid-side loss"**, verbatim, in every
  headline site (C2, 2026-07-19). Never "contact dissipation" / "rigid-side
  dissipation" / "source-referenced" — Eq. (3) is a gravity-corrected KE
  balance that also counts rigid→modal transfer and unrelated rigid–rigid
  losses. "Dissipation" survives only in negations, third-party method
  descriptions, and the Limitations recycling paragraph.
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

---

## 7. Second review-response round — codex panel (planned 2026-07-19)

A second simulated five-reviewer panel (codex) reviewed `main_short.pdf` built
2026-07-18 **23:28** — i.e. the WIP state between R4 (`e9e3c2d`, 23:07) and
R5–R7 (`b359d0b`, 23:54). Verdict: 3/5, borderline leaning weak reject.
Its read: the strongest contribution is the cross-formulation measurement +
negative result; the governor is convincing as an *audited emergency brake*,
not as a practical method. It returned eight "highest-impact revisions",
mapped 1:1 to items C1–C8 below.

**Verification pass (2026-07-19 session) — this plan is calibrated by it:**

- Every checkable number/quote in the review matches the build it saw.
- All five suggested references are REAL and accurately characterized
  (agent-verified against the actual PDFs, not just the URLs). No
  hallucinated citations. Details under C7.
- MIG CFP re-verified at `mig.siggraph.org/2026/papers.htm` — **this
  discharges §2 A0's format re-check**: short papers **4–6 pages excluding
  references**; submission window 25 Jul – 7 Aug 2026 23:59 AoE; notification
  24 Sep; camera-ready 8 Oct; double-blind, EasyChair. Criteria: originality,
  technical quality, clarity, significance, reproducibility where applicable,
  relevance.
- The review's ordering suspicion (#3) is **CONFIRMED IN CODE**: the paper's
  Enforcement sentence ("credited … *before* the contact solve",
  `main_short.tex` ¶Enforcement) matches NO host. All three hosts measure the
  loss AFTER the velocity solve and credit it in the SAME substep, then
  γ-test, project, debit: `dcr/avbd/_solver/solver_xpbd.py:1241`,
  `solver_impulse.py:998`, `solver_6dof.py:2630`. C3 fixes the sentence, not
  the code.
- Already fixed before this round (stale review items — **do not redo**):
  page spill (#1: current `a74dfa6` build ends the body on p. 6 with refs
  alone on p. 7; a clean rebuild of `e9e3c2d` is 6 pp total); TDPA /
  energy-tank / FEPR citations (#7, the governor-ancestry half — landed in
  R6/`b359d0b`, and the FEPR sentence already draws the equality-manifold vs
  one-sided distinction correctly); CPU baseline + % overhead (#part of R4's
  list — landed in R7/`b359d0b`).
- Panel misses worth remembering: "seven references" was actually six;
  "warm starting is ordinarily a solver-policy choice" is only fully true for
  the impulse host (λ←0 per substep IS published XPBD; carried duals+penalty
  ARE constitutive of AVBD) — C5 words this precisely rather than conceding
  it wholesale.

Binding constraints: unchanged from §6 — no solver behavior changes; ARM M4
only for solver-behaviour numbers; every new number frozen in
`docs/mig2026_results_ledger.md` (command + commit + machine) BEFORE it
enters the tex; body ≤ 6 pages excluding references (the C1 gate). The C5-G
ablations are the only gated exception, same gate discipline as R8. R7b
(device re-verification) remains blocked on the user's pod and is not part of
this round.

### 7.1 Priorities

| ID | Review ask | Work | Cost |
|---|---|---|---|
| C1 | #1 page limit | already satisfied — becomes a standing per-commit gate | 0 |
| C2 | #2 energy terminology | define ONE term at Eq. (3); sweep ~9 sites | 0.5 d |
| C3 | #3 exact ledger pseudocode | fix the wrong ordering sentence + compact algorithm block | 0.5 d |
| C4 | #4 reframe as measurement | audit-level only: scope the conclusion's truncation claim | 0.1 d |
| C5 | #5 comparison language | heading + warm-start precision; ablations GATED (C5-G) | 0.25 d |
| C6 | #6 deployed budgets 1×8, 2×4 | NEW numbers: 18-cell deployed-budget table T3 | 1–1.5 d |
| C7 | #7 related work | cite hauser2003 + rath2008 (already in bib); add kaufman2008 | 0.25 d |
| C8 | #8 visual + video | governed/un-governed sequence figure + supplementary video | 1–1.5 d |

Execution order: C2 → C3 (+C4) as one text pass; C6 harness launched the same
day (overnight runs); then C7; C5; C8. C1 gates every paper-worktree commit.

### 7.2 C1 — page budget (standing gate, no work item)

Already compliant: body ends on p. 6, references start p. 7 (refs excluded
per CFP). The gate: after every tex commit in this round, rebuild and check
(a) the last body line is on p. 6 or earlier, (b) References opens no earlier
than the body's final page. C3's algorithm block, C6's table T3, and C8's
figure all ADD content — the space ledger in 7.9 pre-identifies the cuts that
pay for them. If the build overflows: demote in this order — T3 detail rows →
supplement; C8 figure → supplement; C3 float → enumerated lines in-paragraph.

### 7.3 C2 — energy-terminology sweep (the load-bearing text fix)

The review's sharpest point, still true of the current build: headline
phrases say "contact dissipation" while Eq. (3) computes **scene-wide,
gravity-corrected, gross rigid-side kinetic-energy loss** — which includes
legitimate rigid→modal transfer (loss, not dissipation), losses at unrelated
rigid–rigid contacts, and recycling (§Limitations' own 0.4–32% / 102–118%
numbers prove the point). The §2 "Every term, exactly" and "What is
guaranteed" paragraphs are already precise; the fix is making every headline
agree with them.

- Coin the term ONCE, at Eq. (3): "…we call this the **measured gross
  rigid-side loss**" (long form on first use: scene-wide, gravity-corrected,
  gross kinetic-energy loss of the rigid subsystem). Then use that term
  verbatim everywhere.
- Sites to rewrite (phrase-anchored; grep confirms the full list):
  1. Abstract: "Measured against the energy contact actually dissipated".
  2. Abstract: "funded by measured contact dissipation".
  3. Teaser caption: "measured rigid-side contact dissipation, not a tuned
     constant" → "measured gross rigid-side loss, not a tuned constant".
  4. Contribution 2: "funded by measured rigid-side dissipation".
  5. ¶Relation-to-concurrent: same phrase.
  6. ¶Relation-to-passivity: "funded by measured gross rigid-side
     dissipation — energy the solve removed elsewhere" (closest to correct;
     align the noun).
  7. §2 ¶The-invariant: "never exceed what contact has actually dissipated
     on the rigid side".
  8. §2 ¶What-is-guaranteed: "source-referenced supply: … measured
     rigid-side contact dissipation" — replace "source-referenced" with
     "measured, not prescribed" and the noun with the coined term.
  9. Conclusion: "funded by measured contact dissipation".
- KEEP: "not contact-port passivity" (a negation/disclaimer — the review
  endorses it); the Limitations recycling paragraph (already exact); the
  word "dissipated" wherever it names genuine dissipation.
- Also update THIS plan's §1 frozen thesis + contribution bullet 2
  ("source-referenced … contact dissipation only") to the same wording, per
  the D5 rule that plan and paper never disagree.

Acceptance: `grep -n 'dissipat\|source-referenced\|actually' main_short.tex`
— every surviving hit individually justified (genuine dissipation, negation,
or Limitations); `paper/NUMBERS.md` phrasing cross-checked; rebuild clean;
C1 gate passes.

### 7.4 C3 — ledger pseudocode + fix the ordering sentence

Two parts; the first corrects an actual error.

(a) **The Enforcement paragraph misdescribes the algorithm.** It says the
reservoir is credited "before the contact solve"; all three hosts credit
AFTER the velocity solve, in the same substep, from that substep's measured
loss (anchors above; record them in the results ledger per the R2/§6.4
pattern). Rewrite to the true ordering, and connect it explicitly to the
one-largest-deposit forgiveness: same-substep credit is exactly why modal PE
can rise in the substep that funds it, which is the artifact the forgiveness
absorbs. The two paragraphs currently read as unrelated; after C3 they
explain each other.

(b) **Compact per-substep algorithm block** (review #3's list, verified
against `solver_xpbd.py` — identical structure in the other two hosts):

    1  snapshot  E_rig⁻ (pure KE, all bodies), E_mod⁻, positions x⁻
    2  predict (gravity); generate contacts at the predicted pose
    3  position solve (K iterations); velocity solve      # the contact solve
    4  E_rig⁺;  ΔE_rig = (E_rig⁻ − E_rig⁺) + W_g          # Eq. (3), post-solve
    5  B ← B + η·max(ΔE_rig, 0)                           # credit, same substep
    6  E_mod⁺;  if E_mod⁺ > E_mod⁻ + B:
    7      γ = √((E_mod⁻+B)/E_mod⁺);  (q, q̇) ← γ(q, q̇)   # Eq. (4)
    8  B ← max(B − max(ΔE_mod, 0), 0)                     # debit realized gain
    —  contact is NOT re-solved (the §3.3 cost)

Format: a small algorithm float if the C1 gate allows; else numbered lines
inside ¶Enforcement. State "contact is not re-solved" in the block itself —
the review asked for that bit explicitly.

Acceptance: the printed ordering matches all three hosts (re-read the three
call sites, anchors frozen in the results ledger); zero grep hits for
"before the contact solve"; a reader can recompute the reservoir from the
paper alone (§6.4's criterion, now actually true of the executable order).

### 7.5 C4 — measurement-first framing (audit only)

Mostly done in the current build (title, contribution order, "safety
envelope, not an accuracy device" verbatim twice) — the panel reviewed an
older state. Remaining:

- Conclusion: "The amplification is a truncation artifact convergence
  removes" → scope it to the position-based host. §3.2 already concedes the
  K-sweep demonstrates truncation for XPBD only; AVBD's pervasive small
  Eq.-(2) overdraft is measured but untraced. The conclusion sentence must
  not outrun §3.2.
- Same check on the abstract's "A budget sweep shows the amplification is a
  truncation artifact" — acceptable if the sentence's antecedent is clearly
  the position-based catastrophe; adjust only if ambiguous.
- No further reframing: do not re-litigate R1/aae0c2c's prose re-base.

Acceptance: grep audit of "truncation" sites; each claim's scope matches the
section that demonstrates it.

### 7.6 C5 — comparison-language precision (+ gated ablations C5-G)

- Heading "Equal work, unequal outcome" → "**Equal row evaluations, unequal
  outcome**" (the body already says row evaluations; K×S does not equalize
  total work — substeps repeat integration and contact generation, which
  Table T2's "contacts regenerated per substep" row already implies).
- Warm-start sentence: replace "intrinsic to the formulation rather than a
  knob we chose" with the precise version — λ←0 each substep is the
  position-based host's published form; carried duals and penalty are
  constitutive of the augmented-Lagrangian method; the impulse host's per-row
  λ cache is a customary policy default, the one host where it is genuinely a
  choice. As-published defaults, stated as such.
- **C5-G (GATED, default NO-GO — R8 discipline):** (i) warm-start ablation:
  impulse host with the λ cache disabled (config if a flag exists; a code
  change puts it out of scope), and/or XPBD with λ carried (code change —
  out of scope this round); (ii) compliance-matching ablation: one scene,
  α = cfm/h² = 1/β pinned physically equal across hosts. GO only if C1–C8
  are frozen with ≥4 buffer days before Aug 7 AoE. NO-GO fallback: one
  clause in §3.1 or the T2 caption acknowledging that warm start and contact
  regularization follow each formulation as published, unmatched — a
  deliberate as-deployed comparison, not an oversight.

Acceptance: both wording edits in; gate decision recorded here (date +
GO/NO-GO) before Week-3 polish begins.

**C5-G GATE DECISION — NO-GO, 2026-07-19.** The gate condition ("GO only if
C1–C8 are frozen with ≥4 buffer days before Aug 7 AoE") is **not met and
cannot be met today**: C8 is blocked on an interactive browser capture session
(no offscreen render path — the same blocker recorded against R5.3 in
`progress.md`), so C1–C8 are not frozen. Both ablations also carry the
disqualifiers §7.6 already names — the XPBD-carries-λ arm is a code change
(out of scope this round), and the compliance-matching arm would change solver
behaviour and force a re-freeze of numbers that are now cited in three
sections.

The NO-GO fallback is **landed, not merely planned**: §3.1's warm-start
sentence now states that each host runs as published (λ←0 is the
position-based host's own form; carried duals + growing penalty are
constitutive of the augmented-Lagrangian method; only the impulse host's λ
cache is a genuine policy default) and closes with "The comparison is
therefore as-deployed, not compliance-matched." The panel's "warm starting is
ordinarily a solver-policy choice" is thereby answered precisely rather than
conceded wholesale — which was the §7 preamble's instruction.

Revisit only if C8 unblocks AND ≥4 buffer days remain.

### 7.7 C6 — measure the deployed budgets 1×8 and 2×4 (the new experiment)

The paper motivates with "interactive position-based solvers ship budgets
near 1×8 to 2×4" (K×S) but the sweep starts at 4×1 — the panel is right, and
our own equal-32 probe (K32·S1: R=0.300, holds; K4·S8: R=3.13, overdraws
481 J) predicts the substep-heavy deployed points are WORSE. Measuring them
most likely strengthens the motivation; if they come out benign, the
motivation falls back on the K-ladder and we report it honestly. Either
outcome publishes.

- Cells: (K,S) ∈ {(1,8), (2,4)} × 3 scenes × 3 hosts, relaxation at the
  follow-solver default (0.7 position-based/augmented-Lagrangian; inert on
  impulse) = 18 cells, run governor OFF (R, signed Eq.-(2) margin, recycling
  channel) and ON (realized ratio, clamp-active counts, margin) = 36 runs.
  Extend the §6.3 harness's budget list; reuse its offline accounting
  unchanged (already cross-validated vs the impulse live monitor).
- Validity + accuracy at the deployed points: E-S3-pattern wrappers on the
  ON runs (gap violation, corrective impulse, λ variance — Table-1 metrics),
  plus ONE governed-accuracy cell (shelf 1×8, relax 0.7, vs the converged
  reference) mirroring §6.7's 8×2 cell, plus wall-clock per §6.9's method
  (10 × 100 frames): together these are the five metrics the review asked
  for (energy, trajectory error, max gap violation, clamp frequency,
  wall-clock).
- Report as a compact **table T3**, separate from the frozen 24-cell matrix
  — Fig. 1 and every frozen §E-S1b number stay untouched. Hook: the §3.2
  "ship budgets near 1×8 to 2×4" sentence gains its measured continuation.
- Count phrasing: "all 72 measured cells" (abstract, contribution 2, §3.1)
  must either be scoped to the matrix sweep or extended to name the T3 cells
  — decide once T3's final cell count is frozen; grep all three sites.
- Freeze first: new results-ledger entry **E-C6** (commands + commit + ARM
  M4) before any number enters the tex; `paper/NUMBERS.md` synced.

Acceptance: 18/18 OFF and 18/18 ON cells finite and frozen; governed cells
all satisfy Eq. (2); T3 builds inside the C1 gate; the motivation sentence
cites measured numbers; no frozen §E-S1b value changed.

### 7.8 C7 — remaining related work (three citations)

All three verified real and correctly characterized (2026-07-19 agent pass
against the PDFs). The TDPA/tank/FEPR half of the ask is DONE (R6) — do not
re-add.

- **hauser2003** — already in `references.bib`, uncited by the short paper.
  "Interactive Deformation Using Modal Analysis with Constraints", Hauser,
  Shen, O'Brien, Graphics Interface 2003. Cite in §1 ¶1 beside the
  established-treatment / one-way-precedent sentences: interactive modal
  deformation with collision/contact constraints predates everything here.
- **rath2008** — already in `references.bib`, uncited. "Energy-Stable
  Modelling of Contacting Modal Objects with Piece-wise Linear Interaction
  Force", Matthias Rath, DAFx-08. Cite in the passivity paragraph beside
  hannaford2002: exact per-interface energy-stable modal contact at audio
  rate — contrast with our scene-level budgeted cap.
- **kaufman2008** — NEW bib entry. "Staggered Projections for Frictional
  Contact in Multibody Systems", Kaufman, Sueda, James, Pai, ACM TOG 27(5)
  (SIGGRAPH Asia 2008), DOI 10.1145/1409060.1409117 (fill pages from the
  DOI, do not guess). Cite in §1 ¶2 beside the finite-iteration-injection
  observation: velocity-level contact for rigid AND reduced deformable
  bodies, with iterative-solver energy artifacts named — it reinforces both
  "the row is not ours" and "the observation is not ours".
- One framing sentence each, respecting the §1 never-claim list. References
  are page-free per the CFP.

Acceptance: 13 references render; each new sentence attributes, never
claims; C1 gate unaffected (refs excluded).

### 7.9 C8 — one visual + the supplementary video

The current build has three figures, all plots — no scene image, no
governed/un-governed visual, no video. For a graphics venue this is the
weakest presentational point and the panel's #8.

- **In-paper figure (F-C8):** governed vs un-governed vs converged-reference
  deflection sequence — 3 timestamps × 3 arms — at the §6.7 accuracy cell
  (shelf 8×2, relax 0.7), where every trace already exists
  (`governed_accuracy` outputs + the self-convergence traces). First check
  whether §6.7's planned triptych pipeline was ever rendered (it is not in
  the current tex — resurrect it if the shot-list script exists, else render
  from the logged traces directly). A ledger/row schematic is the fallback
  only — C3's algorithm block already explains the mechanism, so the
  sequence figure carries more information per cm².
- **Space ledger** (C1 gate): F-C8 ≈ 0.25 pp + C3 block ≈ 0.12 pp + T3 ≈
  0.15 pp ⇒ ~0.5 pp of cuts, pre-identified: teaser-caption trim, §3.1's
  candidate-denominator sentence, §2 forgiveness-paragraph compression, §3.3
  prose that the figure will now show instead of tell. Cut only AFTER C2/C3
  land (their rewrites shorten some of the same paragraphs).
- **Supplementary video** (60–90 s, page-free): per §3.5's shot list —
  un-governed explosion vs governed bounded at the same starved budget
  (activation A/B), one matrix-cell montage, one GT overlay. Viser capture
  pipeline exists. Check the portal's video/format specs when the EasyChair
  form opens (A0 leftover). Anonymized — the build is `review,anonymous`;
  the video must match.

Acceptance: figure renders from frozen traces (no new solver runs); body
still ends ≤ p. 6; video plays, anonymous, within spec; both referenced from
the text.

### 7.10 Timeline (executes BEFORE the submission window opens Jul 25)

- **D-a (Jul 19):** C2 + C3 + C4 as one tex pass (single build/audit); C6
  harness extension written and launched overnight.
- **D-b (Jul 20):** C6 freeze (E-C6 ledger entry) + T3 + motivation-sentence
  update; C7 citations.
- **D-c (Jul 21):** C5 wording; C8 figure; first full C1 space
  reconciliation.
- **D-d (Jul 22):** C8 video capture + cut; final build audit.
- **D-e (Jul 23):** red-team re-read against BOTH panels' blockers (the §6
  five-lens set and this round's eight), written into `findings.md`; hand to
  PI. Week-3 (§4) unchanged; C5-G gate call no earlier than Jul 31.

### 7.11 Risk additions

| Risk | Response |
|---|---|
| C6: deployed budgets come out benign | Motivation falls back on the K-ladder; report the numbers honestly — the negative result is still a result |
| C6: T3 tempts a matrix re-freeze | T3 stays a separate table; frozen §E-S1b numbers are immutable this round |
| C2 sweep collides with frozen phrasing in NUMBERS.md | Grep both files together; NUMBERS.md is wording-synced in the same commit |
| C3 float overflows the C1 gate | Enumerated lines inside ¶Enforcement; content identical |
| C8 triptych pipeline missing/bitrotten | Render from logged traces directly; schematic is the last resort |
| Video specs unknown until portal opens | Produce 1080p H.264 ≤100 MB as the safe default; re-check at submission |
| C5-G temptation late | Binding gate, mirror of R8: no buffer ⇒ NO-GO, one as-published clause instead |

---

## 8. Third response round — two six-reviewer panels (P-round, planned 2026-07-19)

Two six-reviewer simulated panels reviewed the paper on 2026-07-19:

- **Panel A** on the 05:23 PDT build (SHA `f36166d…`, post-C8, pre-`cbf57b6`):
  3.5/7 mean (3,3,4,3,3,5), four weak reject / one lean-accept / one weak
  accept.
- **Panel B** on the 17:43 rebuild (SHA `103ac0e…`, the `cbf57b6` source):
  3.5/7 mean (3,3,5,4,3,3), four weak reject / one borderline / one weak
  accept. Criteria: originality 3.0, technical quality 3.33, clarity 4.0,
  significance 3.0, reproducibility 2.5, relevance 5.0.

Same mean, same shape as every round; individual lens swings (senior PC
5→3, novelty 4→5) are panel noise — do not chase them. Both panels converge
with rounds 1–2 on the same two deficits: **guarantee precision** and
**evidential robustness**. Codex's calibration, accepted for this round:
text fixes alone ⇒ credible borderline; text fixes + robustness evidence +
supplement ⇒ credible weak accept; contact-consistent governor ⇒ solid
accept but long-paper track (R8 NO-GO evidence stands: deviation-referencing
measured NOT to collapse 21.6 mm → 19.89; band-selective unenforceable in up
to 37.8% of clamp substeps).

**Verification pass (2026-07-19 session, Claude) — trust these, do not redo:**

- **Page spill CONFIRMED — a regression introduced by `cbf57b6`.** Scratch
  rebuild of the current source (probe `\label` before
  `\bibliographystyle`): 7 pages total, **body ends on p. 7**, 0 overfull.
  The C-round gate log ("body ends p. 6") predates `cbf57b6`, whose abstract
  addition was committed without a rebuild check. MIG allows 4–6 content
  pages excluding references ⇒ hard submission blocker.
- **Fig. 3 stale annotation CONFIRMED**: `benchmarks/paper_fig/`
  `fig_s2_kconvergence.py:64` renders `"injection threshold"` inside the
  plot. R0.3 fixed the caption only; C2's terminology sweep never reached
  figure scripts.
- **Paper ID**: no `\acmSubmissionID` in the tex. Expected (EasyChair
  assigns on registration); becomes a submission-day checklist item.
- **Eq. (1) sign complaint EXCLUDED, correctly**: C = y_c − (y_rest +
  U_yᵀq) ⇒ ∂C/∂q = −U_y. One panel-B reviewer alleged a sign error; the
  synthesis verified and excluded it. Independently re-checked. No action.
- **Ablation feasibility re-assessed** (supersedes the blanket "ablations =
  C5-G NO-GO" reading): what the panels ask for is *single-host robustness*
  ablations of the XPBD result, NOT the C5-G *cross-host matching* arms.
  Verified config-level, zero solver-source changes: `h`,
  `n_modes_global/local`, `rayleigh_alpha0/1` are `build_reduced_*` kwargs;
  XPBD `contact_compliance` / `support_compliance` are runtime-settable
  solver attributes (`solver_xpbd.py:243-266`); `run_solver_matrix.py` sets
  every knob at runtime by design. Only the carried-λ warm-start arm is a
  code change — it stays barred; answered in text (λ←0 IS published XPBD;
  the K-ladder isolates convergence level as the mechanism).
- **Already-conceded blockers repeated by both panels** (reservoir
  semantics, governor validity, confounds, governed-FEM gap): the paper
  states all of these in-text after C2–C6. This round does NOT re-litigate
  them beyond P1's scoping sweep. Position disagreements, not errors.

Binding constraints: unchanged — no solver behavior changes (figure scripts
= plotting-only edits allowed; harness extensions = C6 pattern allowed);
ARM M4 for all solver-behaviour numbers; every new number frozen in
`docs/mig2026_results_ledger.md` (command + commit + machine) BEFORE the
tex; frozen E-S1b / E-C6 immutable; body ≤ 6 pages excluding references.

### 8.1 Priorities

| ID | Ask | Work | Cost |
|---|---|---|---|
| P0 | submission blockers | page-spill fix + fig label re-render + ID checklist + **gate v2** | 0.5 d |
| P1 | scope to implementations | attributive-claim sweep, grep-audited | 0.25 d |
| P2 | "one row" ambiguity | one clarifying sentence, instantiation counts from ledger | 0.1 d |
| P3 | guarantee precision | ONE definition block + Proposition + induction sketch | 0.5 d |
| P4 | baseline citations | cite macklin2016xpbd, giles2025avbd (+SI source); name the two references | 0.25 d |
| P5 | abstract balance + billing | deployed-budget range beside 21.6; bound re-billed as audited fail-safe | 0.2 d |
| P6 | new Limitations content | AVBD drift floor + supply partition-dependence | 0.25 d |
| P7 | robustness evidence | **E-C9**: XPBD single-host ablation (h, compliance, rank, damping) + worst-cell K-ladder | 1–1.5 d |
| P8 | supplement package | scene spec, repro bundle, partition/recycling probes, video | 0.5–1 d |
| P9 | gates & handoff | scriptable page gate per commit; red-team; PI; submit early | standing |

Execution order: P0 first (nothing ships over it) → P1+P2+P4+P5 as one tex
pass → P7 harness written and launched overnight → P3 → P6 → E-C9 freeze +
§3.2 sentences → P8. P9 gates every commit.

### 8.2 P0 — submission blockers

- **P0.1 page spill.** Body must end ≤ p. 6. Fund the fix (and P3/P5's
  additions) from the §7.9 cut ladder, floats before words: teaser-caption
  trim, Fig. 2 caption's candidate-denominator sentence, §2
  forgiveness-paragraph compression; last resort, demote Table 2's AVBD rows
  to the supplement. No frozen number is touched by any cut.
- **P0.2 figure vocabulary.** `fig_s2_kconvergence.py:64` "injection
  threshold" → "incident-energy threshold" (the caption's exact term);
  grep ALL short-paper figure scripts (s1, s2, s3, teaser, c8) for
  `injection|dissipat` and fix stragglers; re-render from frozen CSVs only;
  verify the diff is label-text-only. Commit: script on the code branch,
  PDF in the paper worktree.
- **P0.3 paper ID.** Add `\acmSubmissionID{}` placeholder now; fill after
  EasyChair registration (register early in the Jul 25 window). Checklist
  item, not a tex blocker.
- **Gate v2 (the `cbf57b6` lesson).** Make the page gate scriptable and
  unskippable: a permanent innocuous `\label{bodyend}` immediately before
  `\bibliographystyle`; gate = Python (never grep) over build artifacts —
  `bodyend` page ≤ 6 from the `.aux`, total pages from the `.log`, 0
  overfull via `re.finditer`. Run after EVERY tex commit, including
  "trivial" ones — the spill came from a trivial one.

### 8.3 P1–P6 — text items

- **P1 scoping sweep.** Every causal/attributive claim names "the three
  tested implementations" (or "hosts"); "formulation" survives only as the
  axis label (the hosts ARE different formulations; what is not licensed is
  formulation-*class* attribution). Sites: abstract
  ("formulation-dependent"), §3.1 prose, conclusion ("depends strongly on
  the formulation"). Title stays — "Cross-Formulation Measurement" names
  the sweep axis, and a title change this late churns every round's
  cross-references. Grep audit: each surviving `formulation` justified.
- **P2 one row.** At Eq. (1) and the abstract's first use: one row *law*,
  instantiated at every support contact each substep; give the per-scene
  instantiation counts (from the ledger/harness logs — measurement-free).
- **P3 the guarantee, stated once.** One block defining three objects: (i)
  the printed strict invariant Eq. (2); (ii) the enforced per-substep
  ledger recursion (positive-part credit, γ-test, projection, positive-part
  debit); (iii) the implementation test's one-largest-deposit allowance.
  Then a short **Proposition + induction sketch**: the loop guarantees
  (2)-plus-allowance unconditionally (γ-projection + B ≥ 0 are the
  invariant); strict (2) is additionally *observed* in all 90 governed
  cells (worst margin 1.1×10⁻¹³ J). This answers panels' "one consistent
  definition and proof" without any code. ~0.15 pp — funded by P0.1's cuts.
- **P4 citations.** `\citep{macklin2016xpbd}` at first XPBD mention /
  Table 1; `giles2025avbd` for AVBD (optionally chen2024vbd for lineage) —
  both already in `references.bib`, uncited. Sequential impulse: add a
  verified source (Catto GDC is canonical; verify fields, no guessing —
  kaufman2008 discipline; if unverifiable offline, omit gracefully). Also
  name the two references once and use verbatim thereafter: "the converged
  oracle" (impulse @ K=500) vs "the host's self-converged fixed point".
- **P5 abstract balance + governor billing.** The abstract ends on the
  adversarial-corner 21.6 mm alone; add the deployed-budget counterpart
  (worst 9.8 mm, corrective impulse 1.02–1.19× — frozen E-C6) so the
  takeaway is the honest range, not the maximum. Same pass: re-bill the
  bound in the abstract and contribution 2 as a **deliberately minimal,
  audited fail-safe** whose enforcement cost is measured — not the paper's
  constructive method. Both panels' fastest-route ask; do NOT adopt their
  "intentionally crude" phrasing (retroactive spin — the honest form is
  "simplest admissible enforcement, costs measured"). The existing "safety
  envelope, not an accuracy device" sentences stay verbatim. Page cost
  funded by P0.1.
- **P6 Limitations additions.** (a) AVBD drift floor: compare the 0.02–0.15
  J overdrafts to the accounting noise floor (impulse worst margin
  −5.7×10⁻⁴ J) — offline from existing CSVs; freeze the derived multiple in
  the ledger; one sentence ("small, but ~10²–10³× the accounting floor —
  not FP noise"; exact figure from data). (b) Supply partition-dependence:
  Σ_k max(ΔE_rig^k, 0) depends on the substep partition (finer substeps
  rectify more fluctuation into supply) — panel B's numerics reviewer is
  right and the current "endpoints tile the timeline" sentence answers
  completeness, not partition-dependence. Acknowledge in one sentence; if
  P8.c lands a measured coarsening ratio, cite it.

### 8.4 P7 — E-C9 robustness ablation (measurement-only, C6 pattern)

The panels' "targeted evidence" ask, scoped to what needs zero solver
changes. New cells, new ledger entry **E-C9**, frozen matrix untouched.

- Base cells (XPBD, governor OFF): ledge 4×1 relax 1.0 (worst, 1.195×10⁵)
  and shelf 4×1 relax 0.7 (the 21.6 mm / teaser cell).
- One axis at a time from base, ~18–24 runs, overnight M4:
  - `h` ∈ {1/60, 1/120, 1/240};
  - contact/support compliance ∈ {0 (base), 10⁻⁸, 10⁻⁶, 10⁻⁴} m/N;
  - rank via `n_modes_global/local`: one point below the stiff cluster,
    base, one above (shelf spectrum: 10 bending < 2.1 kHz, 6 stiff >
    20 kHz — choose values that deliberately exclude/include the stiff
    six);
  - Rayleigh α₀ ∈ {1, base, 6}; α₁ ∈ {10⁻⁵ (base), 10⁻⁴}.
- Metrics per run: R and the signed Eq.-(2) margin (§6.3 offline
  accounting, already cross-validated).
- **Worst-cell K-ladder** (panel B ask): `run_k_convergence.py` re-pointed
  at ledge relax 1.0 — config-level; shows convergence cures the worst
  cell, not only the shelf drop.
- **Nondimensionalized complementarity residual** (both panels' numerics
  ask, dropped from earlier rounds — mandatory now): re-log the K-sweep
  residual with `probe_complementarity_residual.py` reporting either the
  two components split (max gap violation in mm; max λ on separated rows
  vs its steady-state median) or a normalized `min(C/ℓ, λ/λ̄)`; deterministic
  drop, hours. Text fallback if the probe fights back: state units and
  that only the decay trend is load-bearing. §3.2's "residual passing
  ~3×10⁻⁵" threshold sentence must survive only in normalized form.
- Warm start: NOT run (code change). Text answer in §3.1: λ←0 is the
  published form; the K-ladder isolates convergence level; the result
  already spans 6 budgets × 3 scenes × 2 relaxations.
- Report: 2–4 sentences in §3.2 ("the amplification is not a knife-edge
  configuration artifact: it persists in kind — Eq. (2) violated, R ≫ 1 —
  across …"), full table in the supplement.
- **Contingency (D5 rule, decided before running):** if the rank sweep
  shows the amplification lives in the stiff cluster (plausible — 99.6% of
  ungoverned energy sits there), report it as a *sharpened diagnosis*
  (stiff-tail localization, consistent with §3.3's spectral analysis), not
  a retraction; §3.2 wording follows the numbers. Acceptance is
  persistence-in-kind, not magnitude stability — `h` changes the scene's
  difficulty and magnitudes may move.

### 8.5 P8 — supplement package

- **a. Scene spec.** Exact geometry / material / mass / drop height / rank /
  damping / seeds per scene, sourced from the `build_reduced_*` signatures
  and the ledger; full table in the supplement, 1–2 pointer sentences
  in-paper (a full in-paper table cannot fit the gate).
- **b. Repro bundle.** Ledger excerpts (E-S1b, E-C6, E-C9) with commands +
  commit + machine, raw CSVs from `x1_passivity/out`, README. Anonymized.
- **c. Partition / long-horizon probes (offline-first).** (i) Recompute the
  supply at frame granularity from existing per-substep traces if logged
  (check `governed_accuracy*_traces.npz` / eq2 probe CSVs first); report
  the substep→frame coarsening ratio. (ii) Long-horizon recycling: extend
  `nframes` 100→1000 on 2 cells, recycling fraction vs time. Both
  measurement-only; supplement-grade; one in-paper sentence each only if
  the gate allows. Fallback if traces lack per-substep E_rig: P6's
  acknowledge-only sentence stands alone; probes move to the long paper.
- **d. Video.** 60–90 s: ungoverned explosion vs governed vs converged
  reference at the same starved budget + one GT overlay; anonymized; 1080p
  H.264 ≤ 100 MB default. **Blocked on the user's interactive browser
  capture session** — the only user-action item; independent of everything
  else.

### 8.6 Timeline (window opens Jul 25; deadline Aug 7 AoE)

- **D-i (Jul 20):** P0 complete (spill fixed, gate v2 in place, figure
  re-rendered); P1+P2+P4+P5 as one tex pass; P7 harness written, launched
  overnight.
- **D-ii (Jul 21):** P3 proposition; E-C9 freeze + §3.2 sentences; P6.
- **D-iii (Jul 22):** P8 a–c; full rebuild audit; red-team re-read against
  BOTH panels' lists written into `findings.md`.
- **D-iv (Jul 23):** buffer; hand to PI. Video whenever the capture session
  happens. Week-3 (§4) unchanged: PI revisions, submit ≥24 h early.

### 8.7 Risks

| Risk | Response |
|---|---|
| Cut ladder can't fund P3+P5 over the spill fix | Deeper cuts pre-named in 8.2; last resort Table 2 AVBD rows → supplement |
| Rank sweep removes the amplification at low r | Sharpened-diagnosis framing per 8.4's pre-registered contingency |
| `h`/compliance sweeps move magnitudes wildly | Acceptance = persistence in kind (violation + R ≫ 1), stated up front |
| No per-substep E_rig in existing traces | P6 acknowledge-only; probes to long paper |
| SI citation unverifiable offline | Omit fields rather than guess; camera-ready note |
| E-C9 contradicts a frozen sentence | Wording follows numbers (D5); E-S1b/E-C6 stay immutable |
| Gate v2 skipped "just once" | It is per-commit and scripted; the spill this round IS the counterexample |

## 9. Fourth response round — video panel (Q-round, planned 2026-07-19)

### 9.0 The verdict being answered

Reviewed artifacts, locked by hash (`findings.md` §"Current PDF +
video-supplement review", which transcribes the full panel): PDF `627a14e…`
(the 2026-07-19 20:39 PDT build of the P-round source) **plus, for the first
time, the video** `6dcd904…` (`benchmarks/paper_fig/out/teaser_video.mp4`,
44.77 s, 1920×1080 H.264, 1,343 frames, video-only stream). Six blind
reviewers:

| lens | score | rec |
|---|---|---|
| physics / modal energy | 5/7 | weak accept |
| contact numerics | 3/7 | weak reject |
| novelty / significance | 4/7 | borderline, lean reject |
| evaluation / reproducibility | 3/7 | weak reject |
| clarity / MIG practitioner | 5/7 | weak accept |
| senior PC generalist | 5/7 | weak accept |

Mean **4.17/7**, median 4.5/7, all confidences 4/5 — up from 3.5/7 in both
P-round panels. Criteria means: originality 3.17, technical quality 2.67,
clarity 4.00, significance 3.33, **reproducibility 2.00 (the floor)**, MIG
relevance 5.00. Area-chair line: *accept as a focused diagnostic short
paper; reject if evaluated as a validated contact-control method; not a
safe accept.* That conditional is the round's compass — the paper already
takes the diagnostic framing, so every hour goes to **precision and
packaging, none to mechanism**.

**The panel reviewed PDF + video ONLY. The P8 supplement bundle was never
attached**, so the floor criterion (reproducibility 2.00/5) was scored
against a package missing an artifact that largely exists. Calibration
(advisor pass, 2026-07-19, rulings baked into the items below): describe
that gap as *mostly packaging with a small runnable-artifact gap* — the
bundle still lacks runnable source, a claim→data/command index, dependency
versions and a smoke test, so Q1 is content work too, not relabeling. And
do NOT read 3.5 → 4.17 as an acceptance probability: simulated panels are
neither independent nor calibrated. It is evidence that the remaining
objections are identifiable — nothing more.

Panel strengths to protect (do NOT "fix" these): the candor about
penetration/trajectory cost, the "bounded, not faithful" video framing, the
limitations discipline. Three lenses scored 5/7 *because* of them.

### 9.1 Adjudication of the panel's risks (fact-checked 2026-07-19)

Verified against the tex, the teaser manifest, and `supplement/` before this
plan was written. Do not re-litigate the panel; do re-verify line numbers
(they drift).

| # | Panel risk | Verified status | Item |
|---|---|---|---|
| 1 | Prop. 2.1 guarantees only the one-deposit-relaxed bound; strict Eq. (2) only observed | TRUE — and it is the paper's *own disclosure read back* (the sketch says "Strict (2) is not implied; it is observed… worst margin 1.1e-13 J"). The residual defect is at the CLAIM sites: the abstract ("enforced by a reservoir") and the contribution bullet say "enforced" unqualified | Q2 |
| 2 | Supply is scene-wide / recyclable / schedule-dependent, not contact-port work | TRUE, disclosed, and MEASURED (E-C9c: partition effect ≤7.7% rectified; E-C9d: recycling flat over 10× horizon) — in the bundle the panel never saw | Q1 |
| 3 | Post-projection cost: 21.6 mm penetration, 8.69× corrective impulse, worse trajectories | TRUE, disclosed, priced (§3.3, Table 2). Unfixable without solver changes (barred). The video close-up is the only in-scope response; the panel itself calls it "useful but secondary" | Q5 |
| 4 | Three hosts are implementations, not formulation classes | Mixed usage confirmed: `formulation` at 5 sites (abstract intro, teaser caption, §3.1 head, matrix caption, Limitations closer), `implementations` at 2 | Q4 |
| 5 | Ledger/commands/code/data absent from the supplement | The bundle EXISTS (README, LEDGER_EXCERPTS, ~40 data artifacts, P8). Genuinely missing: a runnable source snapshot, a claim→data/command index, dependency versions, a smoke test, SHA-256 sums, and the video itself; README §5 still says the video is "not included" — false since 17:43 Jul 19 | Q1 |
| 6 | Fig. 1/video call the XPBD K=500 self-fixed point "the converged reference"; §3.2 reserves that term for the implicit realization | CONFIRMED REAL: `teaser_canonical.manifest.json` → `"solver": "xpbd", "converged": "500x1"`; the body's definition block (§3.2) sets "the converged reference" = implicit at K=500 | Q3 |

What CANNOT move this round, stated once: originality/significance (the
paper is what it is); the contact-numerics reviewer (wants the constructive
method — that is the long-paper track, §10, and R8's NO-GO evidence stands);
governed-vs-FEM validation; n=3 hosts; the AVBD mechanism. All remain
conceded in-text. The four-layer contact-consistent composition sketched in
§10 is **out of scope for this round — do not execute any part of it.**

### 9.2 Q0 — baseline adjudication + round record

The working tree holds legitimate uncommitted workstream docs: plan §8
(never committed by the P-round), the findings/progress panel-rerun entries,
and this §9/§10. Also unrelated WIP (dcr/sound, tests/stageE6, benchmark/
dirs) from the sound workstream — NOT ours to touch.

- Verify by diff that the uncommitted hunks in
  `docs/mig2026_short_paper_plan.md`, `findings.md`, `progress.md` are
  exactly: §8 + §9 + §10, the panel transcription, the panel round-log.
  Commit those three files as one round-opening commit
  (`mig-short Q0: adjudicate baseline + log the 4.17 video panel`).
  Leave `prompts/` untracked (house convention: prior boot prompts are
  untracked) and leave the sound-workstream files alone.
- Paper worktree: verify clean at the P-round head (`0c0bb58` or
  descendant); rebuild; gate v2 green (body ≤ p. 6, 0 overfull); spot-check
  3 frozen numbers against `paper/NUMBERS.md`. Do not chase a PDF hash
  match (timestamps differ); gate + numbers are the invariant.
- Acceptance: round-opening commit exists; gate green on an untouched
  rebuild; findings/progress carry the panel record.

### 9.3 Q1 — supplement v2: the package the panel never saw

Extend `benchmarks/paper_eval/x1_passivity/make_supplement.py` (assembler
only — measurement/packaging code, no solver surface). Target package = the
advisor's five elements + venue mechanics:

- **a. Runnable source snapshot** (`code_snapshot.zip`, no `.git`).
  Everything needed to re-run the printed numbers from a clean unpack —
  `dcr/`, `scenes/`, `benchmarks/paper_eval/`, `benchmarks/paper_fig/`,
  `scripts/`, `pyproject.toml`/requirements, plus `data/` assets ONLY if a
  scene build requires them. EXCLUDE: `docs/`, `prompts/`, `reference/`
  (copyrighted PDF), `findings.md`, `progress.md`, `CLAUDE.md`, `.git`,
  `benchmark*/logs`, anything binary-large not needed to run.
- **b. Claim→data/command index** (`CLAIMS_INDEX.md`): every
  figure/table/printed number mapped to its CSV and generating command.
  Derive it from `paper/NUMBERS.md` + the ledger excerpts (scrubbed) — do
  not hand-author a second provenance source.
- **c. Dependency/version record**: Python/numpy/scipy/warp versions (the
  ledger already records CPython 3.12.12 / numpy 2.4.5) in the README plus
  a `requirements-freeze.txt` from the venv.
- **d. Clean-directory smoke test** (`smoke_test.py`, shipped in the
  bundle): from an unpacked snapshot, build one scene and re-derive one
  frozen quantity (e.g. the shelf base cell). Assert QUALITATIVELY
  (violation flag, order of magnitude), print the digits; bit-exactness
  holds on ARM64/Apple silicon only — x86 FP reassociation diverges on
  chaotic stacks (recorded incident) — and the README must say exactly
  that.
- **e. SHA-256 sums** (`SHA256SUMS` over every file) and **one zip**:
  `mig26_supplement.zip` = README, LEDGER_EXCERPTS, CLAIMS_INDEX, data/,
  code_snapshot.zip, smoke_test, requirements-freeze, teaser_video.mp4,
  SHA256SUMS. Well under the 200 MB allowance.
- **f. Video wired in.** Copy `teaser_video.mp4` (the Q3-relabelled render,
  or the current one if Q3's re-render is pending) into the bundle.
  **Rewrite README §5**: the video IS included — three arms at the
  canonical shelf cell 8×2 (ungoverned / governed / XPBD 500×1
  self-reference), rendered headlessly from frozen traces by
  `benchmarks/paper_fig/make_teaser_video.py`; give duration/resolution.
  The current §5 text ("not included in this revision… requires an
  interactive capture session") is stale on both counts — delete it.
- **g. Anonymity, upgraded.** Existing DEANON patterns plus: case-sensitive
  `\bNan\b` (recorded false positives: "domi**nan**t", the float `nan` —
  review hits by hand, never auto-pass), `nli62220`, `usc\.edu`, email
  regex, repo URLs (`github\.com|gitlab|git@`), `compshare`,
  `/Users/|/home/`. **Redact commit hashes in the review copies** of the
  README and LEDGER_EXCERPTS (`<frozen-commit>` placeholder; keep the
  private mapping outside the bundle for camera-ready) — a searchable hash
  can break anonymity. Scan zip MEMBER PATHS and generated-file metadata,
  not just file contents. Assembler still REFUSES to write on any
  confirmed hit.
- Ordering rule: the FINAL assembly run happens LAST in the round (Q8), so
  sums and the snapshot reflect final commits. Q1 lands the machinery and a
  first full dry run.
- Acceptance: assembler exits 0 with scan PASS; `smoke_test.py` passes from
  a clean unpack; CLAIMS_INDEX covers every printed number (spot-check 10);
  README §5 describes the actual video; no commit hash anywhere in the
  bundle; `shasum -c` verifies; zip size printed.

### 9.4 Q2 — guarantee precision (panel priority 1)

The enforced bound gets its own number; every claim site says which bound
it means. Tex only; no semantic change to the loop's description.

- Promote the one-deposit-relaxed inequality from prose item (iii) to a
  display, using the existing macros:
  `\Emod^{\,n}-\Emod^{\,0} \le \eta\sum_{k\le n}\max(\dErig^{\,k},0)
  + \max_{k\le n}\,\eta\max(\dErig^{\,k},0)`, `\label{eq:budgeted}`.
  Item (iii)'s prose shrinks accordingly (the formula moves out — net cost
  target ≤ 2 lines).
- Proposition statement: "…enforces \eqref{eq:budgeted} unconditionally…"
  (replacing "(iii)"); sketch's "exactly~(iii)" → "exactly~\eqref{eq:budgeted}".
  The sketch's substance is already correct — do not reprove.
- **Binding vocabulary map (advisor pass — apply everywhere):**
  *guarantees / certifies* → the relaxed displayed bound
  \eqref{eq:budgeted} ONLY; *observed* → strict \eqref{eq:invariant};
  *limits / contains* → safe descriptive language for the governor. AVOID
  "enforced up to X" phrasings — they still read as an approximately
  strict guarantee. Model sentence (adapt for space, keep the structure):
  "The reservoir guarantees a relaxed storage bound with additive slack
  equal to the largest single deposit (Prop.~\ref{prop:guarantee}); the
  strict ledger inequality was additionally observed in all 90 evaluated
  cells, worst numerical margin $1.1\times10^{-13}$~J."
- Claim-site sweep under that map: grep `enforc|guarante|certif|observ`
  and adjudicate every hit — abstract, contribution bullet, §2, §3,
  Limitations, and the video end-card text if touched. *Guarantee* claims
  must point at eq:budgeted or carry Prop.~2.1; *observe* claims cite the
  90-cell measurement.
- Numbers appearing in new spots (7–389 J, 1.1e-13 J, 90 cells) re-verified
  against source before printing (NUMBERS.md discipline).
- Acceptance: gate green; grep audit table in findings (every "enforce"
  site adjudicated); NUMBERS.md synced.

### 9.5 Q3 — reference-arm naming (panel priority 3b)

Two fixed names, then a per-site audit — never rename blind:

- **Term A "implicit high-iteration reference (K=500)"** — short handle
  after first definition: "the implicit reference".
- **Term B "XPBD high-iteration self-reference (500×1)"** — short handle:
  "the XPBD self-reference".
- **"Converged" is RESERVED** (advisor pass): use it only where an
  explicit convergence criterion is stated and checked (the K-ladder
  decay, the implicit arm's $4.9\times10^{-4}$ spread across K=2…500) —
  never as an arm NAME. This removes the two-meanings defect instead of
  relabeling it. Per-site cost is flat: the short handles are no longer
  than the terms they replace; only the two definition sites grow.
- Build the audit table first: `grep -n converged paper/main_short.tex`,
  adjudicate EVERY site's arm identity from the generating harness or
  manifest. Provisional read (2026-07-19; re-derive, don't trust): abstract
  "same code path" site = Term A, OK; teaser-setup "host's own converged
  solution" → Term B wording; teaser caption "against a converged
  reference" → **Term B (manifest-verified xpbd 500×1 — this is the
  panel's exact catch)**; §3.2 kconv sites = Term A per the definition
  block, OK; governed-accuracy "converged reference's 7.92 J" → AUDIT the
  harness for which arm produced 7.92 J; "converged budget" and
  Conclusion sites → AUDIT.
- Figure + video labels: if `fig_teaser.py`'s in-figure label or
  `make_teaser_video.py`'s overlay says "converged reference" for the
  xpbd 500×1 arm, re-render with Term B. **Label-text-only** (the P0.2
  precedent): frozen traces, identical cut. Verify the re-encode: 1,343
  frames, 44.77 s, 1920×1080 unchanged; record the new SHA-256 in the
  ledger note and use THIS render everywhere (bundle + submission).
- Acceptance: audit table in findings; every site conforms to Term A/B;
  video verified label-only; gate green.

### 9.6 Q4 — implementations / row-law consistency (panel priority 3a)

- Rule: `formulation` survives ONLY where it introduces the three families
  and is paired with "one implementation each" (abstract first mention;
  the Limitations closer already has the pairing). Everywhere else —
  §3.1 head, captions, results prose — say "implementations" or "hosts".
  Causal statements always "the three tested implementations".
- `row law` audit: grep `row law|contact law|complementarity law|
  transcribed`. The source law stays "velocity-level complementarity law"
  (it names prior work's object); OUR object is "the row law" after first
  definition. Standardize second mentions.
- Acceptance: grep audit table (each surviving `formulation` justified);
  gate green.

### 9.7 Q5 — video penetration close-up (CONDITIONAL; a scientific change, not packaging)

Advisor ruling adopted: **44.8 s is already sufficient — do not chase a
duration target.** The close-up is added only if it costs no new physics:

- Locate the 21.6 mm cell: grep the tex → `paper/NUMBERS.md` → CSV row
  (governed arm, Table 2 context). Check whether existing frozen traces
  carry body poses for that cell (`teaser` traces do; the
  `governed_accuracy_1x8_traces.npz` holds deflection fields only).
- **Fast path (poses already recorded):** render the close-up headlessly
  (extend `make_teaser_video.py` or a sibling
  `make_penetration_closeup.py`): side view at the contact, slow-motion
  around the projection event, a NUMERIC penetration overlay whose values
  match the printed 21.6 mm, and the explicit on-screen label
  **"bounded, but not faithful"** — the video's existing honest register.
- **Slow path (fresh replay needed): ranks BELOW all text and
  reproducibility work.** Only after Q1/Q2/Q3/Q4 are frozen: ONE serial
  ARM re-run with pose capture, measurement-only, a bit-reproducible
  replay that MUST reproduce the printed numbers (21.6 mm to printed
  precision) as the non-perturbation check; freeze as **E-C11** (command +
  commit + machine) before any frame renders. If time runs short, skip —
  the panel calls the close-up "useful but secondary".
- **USER GATE: present the extended cut for approval before it replaces
  the reviewed video in the bundle.** If declined or skipped, ship the
  Q3-relabelled 44.8 s render — the panel already scored it positively.
- Acceptance: an approved extended render (specs re-verified, overlay
  values checked against NUMBERS.md, SHA-256 recorded) or a logged
  decision to ship the 44.8 s cut.

### 9.8 Q6 — minimal-cell experiment: DEFERRED (do not build this round)

**Advisor ruling adopted: SKIP for this submission.** A supplement-only
new experiment has limited review leverage, adds variance under the
frozen-results constraint, and can open new questions. Revisit ONLY if the
user re-opens it with one sharply stated causal ambiguity it would
resolve. Do not ask about it; do not build it. The design below is
retained as pre-registration for the long-paper track.

**Distinct from C5-G**, which gated *cross-host physics/compliance
matching* on the full scenes and stays NO-GO. This is the panel's other
suggestion: an *isolated* cell where the contact set is trivial, so host
differences in contact parameterization are minimized rather than matched.

- Setup: harness-side scene builder
  `benchmarks/paper_eval/x1_passivity/scene_minimal_cell.py` (do NOT touch
  `scenes/` — frozen builders stay frozen). One modal plate, one small
  impactor, target a single persistent contact patch. Option 1: flat drop
  (one 4-row patch, one zone). Option 2: corner drop (1-row transient).
  No new colliders — boxes only (a sphere collider would be solver-adjacent
  code, barred).
- Sweep: three hosts × K ∈ {1,2,4,8,16,32} × S=1, follow-solver relax
  defaults; measure R, Eq. (2) margin, nd-residuals. Serial, ARM M4.
  Freeze as **E-C10** before any number is used anywhere.
- Pre-registered expectations (D5: wording follows numbers): H1 implicit
  flat, R < 1 at all K. H2 XPBD injects at small K and decays; magnitude
  well below the shelf/ledge worst cells (the 1e5 amplification needs the
  multi-row stiff sweep) — if R > 1 persists even at one patch, the
  mechanism is *more* elementary than claimed; report either way. H3 AVBD
  zero-or-minor (≤ 15 J-scale).
- Pre-registered NO-GO: if no configuration yields a persistent
  single-patch contact free of secondary contacts, record E-C10 NO-GO
  with the attempted configs and stop.
- Outcome use: supplement README section + CSV. In-paper AT MOST one
  sentence in §3.1 and only if the gate affords it; default
  supplement-only.
- Cost estimate if ever re-opened: ~1–2 h build + minutes of runtime. The
  panel marked it conditional ("if one experiment is possible"); the round
  is complete — and per the advisor, safer — without it.

### 9.9 Q7 — future-work clause + submission mechanics

- One clause in Limitations/future work, if the gate affords it —
  DELIBERATELY NONSPECIFIC (advisor pass: naming condensation / per-row
  budgeted impulses invites reviewers to evaluate an untested method).
  Use: "Future work will investigate update-local, contact-consistent
  enforcement and adaptive convergence, using trajectory fidelity --- not
  storage boundedness alone --- as the acceptance criterion." The specific
  composition stays in §10, internal only, never in the paper. First
  candidate to DROP if the gate goes red.
- `\acmSubmissionID{}`: fill after EasyChair registration (window opens
  Jul 25). The panel also noted the PDF is untagged — known acmart
  limitation, accepted, no action.
- Acceptance: gate green with or without the clause; a logged decision
  either way.

### 9.10 Q8 — final assembly + handoff

- Re-run the supplement assembler LAST (post-final-commits): fresh
  snapshot, fresh sums, final video, zip.
- Final clean rebuild; gate v2; banned-terms grep; new-numbers-vs-CSV
  re-verification; anonymity scan of the whole zip.
- Handoff note (progress.md): map panel priorities (1)–(5) → landing
  sites + commits; log the Q5 outcome and the Q6 deferral; restate what is
  deliberately unaddressed (§9.1 tail) so the PI is not surprised by a
  reviewer repeating it.
- Red-team re-read of the final build against THIS panel's six risks,
  written into findings.md (P-round D-e pattern).

### 9.11 Q9 — the per-commit ritual (gates every item above)

Identical to P9: rebuild + gate v2 (`scripts/check_page_gate.py` — never
grep the log) per tex commit; ledger-before-tex for any new number
(E-C10/E-C11); ARM M4 serial for any solver-behaviour number; no frozen
number touched by any cut; kaufman2008 citation discipline (verify fields
or omit — no new citations are expected this round); code commits
`mig-short Q<n>: <what>`, paper worktree separate; progress.md per item,
surprises to findings.md.

### 9.12 Execution order + timeline

**Q0 → Q1 → (Q2 + Q3 + Q4 + Q7 as ONE tex pass, gate per commit) →
full-audit rebuild → Q5 fast path only → Q8.** Q6 is deferred — do not
ask. The ONE user decision left is Q5's cut approval, and only if a
close-up actually gets built; Q5's slow path (E-C11 replay) ranks below
everything else and is skippable. This matches the advisor's order:
snapshot + anonymity audit first, one combined tex pass, rebuild + full
vocabulary/name audits, clean-directory smoke test, portal deliverables,
paper ID, video close-up only once everything above is frozen.

| date | milestone |
|---|---|
| Jul 20–21 | Q0, Q1, tex pass (Q2/Q3/Q4/Q7), audits |
| Jul 22–24 | Q5 fast path + approval (slow path only if all else frozen) |
| Jul 25 | EasyChair opens: register, fill `\acmSubmissionID`, re-check portal video specs |
| Jul 25–Aug 5 | Q8 final assembly, PI handoff, submit |
| hard limit | ≥ 24 h before 2026-08-07 23:59 AoE |

### 9.13 Risks

| risk | mitigation |
|---|---|
| Q2's display eq. blows the gate | Formula moves OUT of (iii) prose (net ≤ 2 lines); drop Q7's clause first; remaining ladder rungs only after that; no cut touches a frozen number |
| Video re-render churns content | Label-text-only rule; verify 1,343 frames / 44.77 s / 1080p unchanged; new hash recorded; Q5 extension is a separate, user-approved artifact; no duration target |
| Code snapshot leaks identity | Extended DEANON scan incl. repo URLs; manual review of every `\bNan\b` hit (known FPs: "dominant", float `nan`); commit hashes redacted in review copies; scan zip member paths + generated metadata; assembler refuses on confirmed hits |
| Smoke test fails off-ARM (FP reassociation, recorded incident) | Qualitative asserts only (violation flag, order of magnitude); README states digits are ARM64-exact only |
| Q6 temptation | DEFERRED by decision; revisit only on a user re-open with a sharp causal ambiguity it would resolve |
| "Fixing" the candor the panel praised | §9.0 protection list; red-team re-read checks disclosures survived verbatim |
| Renaming references blind | Q3's audit-table-first rule; the 7.92 J site's arm identity must come from the harness, not from prose |

## 10. Parking lot — long-paper track: contact-consistent governor (DO NOT EXECUTE)

Sketch preserved from the 2026-07-19 brainstorm so it survives the session.
Not part of the Q-round; barred for the short paper (no solver changes;
R8 NO-GO evidence stands; the panel prices acceptance on the diagnostic
framing).

Design constraints from the NO-GO evidence: deviation-referencing failed
(21.6 → 19.89 did not close) ⇒ the injection is created by truncated
iteration dynamics, not constraint parameterization. Band-selective failed
(unenforceable in 37.8% of clamp substeps) ⇒ after-the-fact attribution is
dead; act at the moment work is done, through the mechanical channel doing
it. E-C9 ⇒ the stiff cluster is the amplifier (286×/36×) but not the source
(violation survives its removal) ⇒ at least two layers.

1. **Resolvability-split coupling**: inside each row's modal weight
   `(M+hD+h²K)⁻¹`, statically condense modes with large ωh — they
   contribute compliance but receive no velocity kick (cannot store ring
   energy the integrator cannot represent). No attribution needed; the
   energy never exists.
2. **Per-row incremental passivity guard**: each row update's energy change
   is closed-form quadratic in Δλ; clamp Δλ so ΔH ≤ B_row, with B_row
   funded by the row's own penetration-potential (bias work budgeted, not
   free). Contact-consistent by construction; conjecture: inactive at the
   LCP fixed point ⇒ fixed-point set preserved (the theorem the long paper
   needs). Reframes relax=0.7 as a blunt constant version of the guard.
3. **Contact-space overdraft removal**: remaining overdraft removed by the
   smallest-M-norm impulse in range(M⁻¹Jᵀ_active) s.t. unilaterality +
   non-negative post-fix gap velocities (small QP); global γ survives only
   as a reported-fire-rate backstop. Alternative 3′: spend iterations, not
   clamps — bounded local re-sweep on the offending island (K-ladder is the
   existing evidence it converges).
4. **Ledger demoted to certificate**: Eq. (2) + nd-residuals + governed
   deflection closing toward the converged reference (the yardstick
   deviation-referencing failed).

Measurement-only pre-studies (no solver changes; run BEFORE building any
layer): (a) deposit-time work decomposition per row (bias / stiff-h²K /
cross-term / overshoot) via the E-C9c wrapping pattern; (b) contact-space
feasibility: at every would-be clamp event in the frozen matrix, is the
excess removable through the active J under unilaterality? (c) AVBD
penalty-ramp work audit between rows (the unexplained 23/24 overdraft may
not be row-attributable — test before promising host-agnostic layers).
Prior-art check required before claiming novelty: verify 2602.08094 /
Zobel 2025 do not already propose per-row energy clamps.
