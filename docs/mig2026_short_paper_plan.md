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
