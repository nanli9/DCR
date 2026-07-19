# Literature Gap Audit Progress

## 2026-07-19 MIG Teaser / Visual-Demo Design

- Began an advisory audit of existing XPBD governor-OFF/ON artifacts and current MIG supplementary-material expectations.
- Key starting distinction: a high modal-energy ratio is not automatically a visually exploding object; the current shelf 8x2 case stores 99.6% of the error in very stiff modes and can look only modestly displaced despite a 196x energy error.
- Ranked preliminary cases: shelf `8x2` is the paper-safe comparison because it has a converged reference; legacy `2x4` is only a possible video hero pending true-scale rendering; penetration-heavy `4x1` should not lead the visual story.
- Found the intended true visual-failure runner: `run_native_scenes_viser.py --inject-xpbd`, a shelf/steel-board XPBD `1x16` preset tied to the frozen ~55 kJ OFF / 40.8 J ON production-budget result. This supersedes `2x4` as the first case to capture.
- Located two canonical times: frame 31 (`0.258 s`) is the best synchronized deformation still (24.12/5.93/20.48/20.00 mm peak across OFF/ON/converged-XPBD/oracle), while frame 34 (`0.283 s`) is the OFF energy maximum. Frozen 48-row surface-deflection traces support an honest static render.
- Rechecked the live MIG 2026 CFP: no teaser/paper image is required; supplementary materials such as videos are strongly encouraged up to 200 MB.
- Confirmed that Figure 1 is already the OFF/ON activation-energy plot and labeled as the teaser. The likely edit is a compact qualitative-plus-trace composite, not an extra standalone figure, because the body already fills all six allowed content pages.
- Visually audited page 1: the existing single-column Figure 1 has enough footprint for a shallow OFF/ON/reference strip above a compressed energy trace without adding a new float.
- Audited the live viewer controls: all scientific overlays exist, but capture and camera are manual, matching the ledger's current “interactive capture” blocker.
- Confirmed the hero scene composition and camera need: board profile + five upright books + free-end falling book, shown from one locked low three-quarter view.
- Flagged a provenance constraint: the visual `1x16` preset is legacy/production evidence outside the current 24-cell matrix, so the paper teaser should remain anchored to `8x2`; `1x16` is best used as a clearly labeled video demonstration.
- Found an additional provenance difference: the demo preset uses a 200 GPa steel support and relax `1.0`, unlike the paper's `8x2`, relax `0.7` shelf. It must be labeled as a separate stress case.
- Reproduced that current stress case: 17.98 kJ OFF vs 2.13 J ON, but only 0.642 mm vs 0.0115 mm true-scale board deflection. The next validation target is downstream book launch/topple; otherwise the demo should visualize vibration energy rather than call it a visible explosion.
- Measured the downstream response: OFF launches the five resting books 33--46 mm; ON launches none. The `1x16` stress case is therefore visually strong at true scale when the camera emphasizes the bystanders, despite sub-millimeter board motion.
- Measured canonical `8x2` and converged-reference rigid motion: OFF lifts books 15--23 mm, ON 2--8 mm, but the reference spans 8--31 mm. This rules out a simplistic “ON = correct” teaser and makes the third reference panel essential.
- Finalized the recommendation: replace the current plot-only Figure 1 with a same-footprint three-frame `8x2` OFF/ON/reference strip plus the compressed activation trace; use the steel `1x16` bystander-launch case as the labeled supplementary-video opener, followed by the canonical reference comparison.

## 2026-07-18 MIG Short-Paper Panel Review

- Reopened the panel review because `paper/main_short.pdf` was regenerated after the preserved audit: current SHA-256 is `8d4b83f9663ded4b91f337577d9aef2f511a561086c1134d3bbdc37b676baa15`, 6 pages, generated 23:06 PDT. The earlier 4-page verdict is stale pending re-audit.
- Detected concurrent source edits at 23:24 that are not compiled into the requested 23:06 PDF; locked the assessment to the PDF hash and excluded source-only evidence.
- Completed the fresh five-lens calibration for the 23:06 PDF: scores 3, 2, 3, 2, 4 (mean 2.8, median 3), overall borderline with a weak-reject lean. The diagnostic/negative result is publishable in principle; gross-loss attribution, update ordering, prior-art positioning, and governed usefulness remain the main acceptance risks.
- Final artifact check found a newly compiled 23:26 PDF (`fd78290...`); reopened the assessment for a delta review so the delivered panel matches the user's latest file.
- Extracted the latest 7-page build. It now includes AVBD contact-validity rows and governed accuracy/spectral evidence; these repair evaluation completeness while confirming that the projection improves scalar energy but worsens the state trajectory.
- Visually audited pages 5–7 and recalibrated the panel to 3, 2, 3, 3, 4 (mean/median 3). Body text spills onto page 7 alongside references, creating a likely six-content-page compliance issue.
- Diffed the final 23:28 build (`e959b15...`): only wording/layout changed. The conclusion overflow is reduced to three lines on page 7; the panel score remains unchanged.
- Started a fresh five-reviewer MIG-style assessment of `paper/main_short.pdf` under a short-paper bar.
- Preserved existing workspace planning state and added a scoped review section rather than replacing earlier plans.
- Verified the supplied artifact is a current 4-page anonymous MIG-formatted PDF and extracted its text for claim/evidence reconstruction.
- Dispatched three independent panel lenses (technical, novelty/fit, and evaluation/presentation); the primary reviewer is separately performing generalist and adversarial decision calibration.
- Completed the full four-page visual/text audit and received all three independent specialist reviews.
- Began panel calibration; the specialist scores are 2/5 technical, 3/5 novelty/fit, and 2/5 evaluation, all at confidence 4/5.
- Added an independent practitioner accept-side review (3/5, confidence 4/5) and completed the primary generalist/meta-review (3/5, confidence 4/5).
- Final panel distribution is 2, 3, 2, 3, 3 (mean 2.6/5, median 3/5): borderline, leaning weak reject for the supplied PDF. No manuscript or solver files were modified.


## 2026-07-18 Velocity-Impulse Native-Modal Check

- Began a read-only audit of commit `462b717` and the current worktree; no source-code or solver-configuration changes are authorized.
- Scoped the task to host-solver identity, slab runtime representation, comparison with the earlier XPBD/AVBD paths, ABD similarity, and a fresh primary-literature novelty screen.
- Read the committed design note, meeting walkthrough, solver symbol map, and commit summary; confirmed the host is Schur+PGS velocity impulse and identified the support-vs-box-box semantic split.
- Traced scene construction through `ReducedSupport`, synthetic basis generation, FEM-eigenmode support generation, and world row replacement; clarified that the runtime slab is a fixed-base reduced deformable support rather than a full FEM body or ordinary rigid body.
- Ran the six dedicated velocity-impulse tests successfully and mapped the XPBD/AVBD comparison points for the architecture verdict.
- Downloaded and text-audited primary Hauser, Zheng/James, Rath, and Sheth papers in `/tmp`; confirmed direct equation-level precedents for velocity-level impulse/modal contact and the narrower surviving role of the directional ledger.
- Audited the impulse backend's passivity mechanism and viewer wiring; found that the projector exists and cargo scenes can activate it through `--passivity`, but it is off by default, unactivated by the dedicated impulse tests, and disabled for support-only impulse scenes by the viewer's symplectic-path classification.
- Added Kaufman et al. 2008 Staggered Projections and reduced dynamic-contact LCP work to the primary-source comparison; confirmed that generalized modal/reduced coordinates in velocity-level contact are established prior art.
- Audited the current manuscript against the pivot; confirmed that its XPBD/AVBD host claims, GPU/120-Hz/512-body evidence, and host-specific stabilization story do not currently describe the velocity-impulse implementation.
- Completed the final novelty/MIG calibration: strong venue fit but only a narrow potentially novel directional budget remains; current impulse demonstration is approximately 4/10 on novelty and is not yet long-paper ready.
- No solver, scene, manuscript, or source-code files were changed during this audit; only the research-planning notes were updated.

## 2026-07-11 Demo Repositioning

- Started an assessment of whether physically small jump amplitudes undermine the contribution or MIG suitability once the DCR-style artistic-control demo is removed.
- Restored the existing manuscript-review and novelty-audit context; no project implementation changes are planned for this advisory task.
- Audited the manuscript and confirmed that launch height is already classified as a secondary/non-convergent observable; the core claims are solver stability, a directional passivity bound, contact-network coupling, and validation.
- Verified the current official MIG 2026 CFP: physics-based animation and interactive simulation are explicit topics; review criteria are technical rather than spectacle-driven.
- Identified the key pivot hazard: using ABD as an application/basis demonstration is compatible, but replacing the modal/passivity method with generic ABD two-way contact would substantially weaken novelty.
- Visually inspected the existing network and ABD/contact-force artifacts; the concept is present but the teaser/video still needs a polished scientific-visualization treatment.
- Completed the replacement-demo design. Recommended a new mass-loaded resonance scene as the causal back-reaction hero, supported by the existing network, FEM, passivity, and scaling experiments.
- Final advisory conclusion: removing DCR-style large jumps strengthens claim alignment; MIG scope fit remains strong, but long-paper readiness depends on closing integrated enforcement/accuracy/performance evidence and keeping ABD claims conditional.

## 2026-07-07

- Started local literature gap audit at user request.
- Created local planning files for the research trail.
- Spawned a novelty/scoop-finding subagent.
- Ran initial web searches for modal contact/passivity/reduced contact terms; no direct scoop found yet.
- Received and closed subagent. It found no exact all-axis scoop and rated novelty risk medium.
- Cross-checked key source categories: Zheng & James, DCR local PDF, XPBD/VBD, ABD/Embedded IPC/M-ABD, convex rigid-deformable contact, and port-Hamiltonian flexible multibody.

## 2026-07-09

- Started a fresh MIG regular-paper review of `paper/main.pdf`.
- Scoped the assessment to the manuscript itself and explicitly excluded the production demo.
- Located the current manuscript source, compiled PDF, figures, and paper-evaluation artifacts.
- Confirmed the compiled artifact is 10 pages and extracted it to text for page-level review.
- Identified major disclosed evidence gaps: pending validation cells, split accuracy/performance paths, unmatched restitution, and pending road-scene accuracy.
- Completed a first pass over all manuscript sections and isolated claim/evidence inconsistencies around the controller derivation, device-path guarantee, momentum, and accuracy at the advertised timestep.
- Visually inspected all 10 PDF pages and audited parameter specification, baseline matching, runtime reporting, and submission-readiness artifacts.
- Cross-checked the local DCR primary source and found that its stated contact-graph capability is understated in the manuscript's positioning table.
- Completed independent technical, evaluation, and novelty/presentation reviews and calibrated the final verdict.
- Final recommendation for the current manuscript: 2/5 weak reject, confidence 4/5; production demo excluded from consideration.

## 2026-07-09 Novelty Re-Verification

- Began a fresh, adversarial literature search at the user's request.
- Scope fixed to the current paper's exact combination; production demo remains excluded.
- Ran initial cross-domain searches and identified reduced dynamic contact and energy-constrained projective dynamics as important adjacent work, but no exact A+B+C+D scoop.
- Found direct passivity adversaries: classic time-domain passivity observation/control and passive reduced soft-object simulation with intermittent contacts; neither yet appears to be an exact A+B+C+D match.
- Verified Passive Midpoint Integration as a major omitted adversary combining real-time interactive simulation, discrete-time passivity, generalized-coordinate vibration, and LCP frictional contact.
- Verified PMI's vibration-coordinate example and found 2022/2026 extensions relevant to passive contact and finite-iteration energy-safe coupling.
- Audited AVBD/XPBD and broader contact-MOR work; these narrow the defensible novelty but still do not duplicate the exact directional transfer budget.
- Re-checked Zheng/James and DCR citation neighborhoods; no exact two-way AL/PBD plus transfer-bound follow-up found.
- Checked energy-constrained projective dynamics and structure-preserving MOR; both weaken the paper's binary novelty table without exactly matching its transfer cap.
- Found FEPR (SIGGRAPH 2018), a major omitted prior method for post-step energy projection in real-time PBD/PD under approximate solves.
- Logged a browser PDF-parser failure for FEPR and retained the authors' primary project page as the verified source.
- Verified Su, Schroeder, and Fedkiw 2009 as prior art for exact quadratic scaling of contact/collision impulses to prevent energy growth at frame-rate timesteps.
- Ran exact-phrase searches for modal/contact energy budgets and rigid-flexible directional transfer bounds; found no exact rigid-loss-funded modal cap.
- Added Gehr et al. 2022 as reduced modal-impact/energy-distribution prior art and You et al. 2026 as a close contact-energy target plus analytic correction adversary.
- Completed the three search-domain phases and began the final primary-source axis-by-axis cross-check.
- Cross-checked Zheng/James, Yoon 2019, FEPR, Su 2009, You 2026, Gehr 2022, and Wei 2026 against primary author, institutional, proceedings, or arXiv records.
- Logged a browser URL-safety failure for direct PMI DOI opening; technical classification remains supported by the inspected author manuscript and verified DOI/publication metadata.
- Inspected PMI's full journal HTML and verified its non-iterative real-time passivity, generalized-coordinate vibration model, and generalized/maximal Coulomb-contact formulations; classified it as the closest conceptual adversary but not an exact narrow scoop.
- Verified Kim and Ryu 2010 as prior art for bounding generated energy by measured dissipative capacity, further narrowing the surviving contribution to the modal contact port, rigid-loss supply rate, and host integration.
- Added Barbi\v{c}/James 2008 (kilohertz reduced deformable contact), Peng et al. 2024 (linear-mode/modal-derivative reduced XPBD), Hyper-Reduced PD 2018, and Goury et al. 2021 (real-time reduced LCP contact) to the adversarial neighborhood.
- Logged transient/URL-safety failures for the Barbi\v{c}/James project page, a rate-limited Peng re-open, and the legacy HAL URL; retained primary DOI/institutional records.
- Verified Rath 2008 as direct energy-stable contacting-modal-object prior art and Hauser 2003 as interactive modal collision/constraint prior art; added Bhalerao 2010 and Ducceschi et al. 2023 as modal contact/network neighbors.
- Revised claim assessment: three current broad novelty sentences are indefensible; only the exact directional supply-rate plus fixed-budget AL/shared-row intersection remains plausibly novel.
- Downloaded and text-audited Rath 2008 and Su et al. 2009. Rath is a stronger adversary than its abstract suggests: equal-and-opposite real-time modal contact with explicit rigid/free-mass-to-modal energy transfer and guaranteed total-energy nonincrease.
- Logged an SSL hostname mismatch for the Hauser author PDF and switched to authoritative alternative full-text sources rather than weakening certificate checks.
- Downloaded authoritative Hauser, Barbi\v{c}/James, and Sheth PDFs and verified their contact equations, modal/reduced bases, two-way force/impulse application, and performance/iteration regimes.
- Confirmed that real-time/interactive two-way modal-capable contact and fixed-low-iteration modal contact both predate the manuscript; neither includes the exact directional AL/PBD energy ledger.
- Extended the audit into musical-acoustics contact literature and found multiple energy-conserving modal/distributed collision schemes (2015, 2017, 2023), further narrowing the safe claim.
- Completed the primary-source axis matrix and final novelty calibration.
- Final result: no exact full-method scoop found at roughly 85% confidence; exact-scoop risk medium, overall idea novelty moderate, controller obviousness risk high, and current broad claims indefensible.
- Identified the defensible contribution as the cumulative source-referenced directional modal-storage budget inside shared rigid/modal fixed-budget AL/PBD contact rows.
- Marked all novelty re-verification phases complete; production demo remained untouched.

## 2026-07-13 Repositioning execution + E-R1 (session log)
- Executed all 21 TODO(reposition) sites in paper worktree (acronym-free, standalone framing); banner removed; builds clean, 13 pp, 0 overfull, 0 undefined refs. Uncommitted on `paper` worktree.
- E-R1 (ledge modes-off topple control): ran `benchmarks/paper_eval/er1_topple_control/run_topple_control.py` (paper config, 480 steps). ARM host: native AND frozen arms — all 3 pillars stand (ring 0.77 vs 0.0). x86 EPYC recorded run had knocked-off pillar → topple is knife-edge/platform-FP-sensitive. Paper §4.1 now says "scene dressing, not capability evidence"; NUMBERS.md entry added; x86 frozen-arm control PENDING (compshare pod unreachable).
- Regenerated fig_x2_falloff/fig_x7_restitution with "one-way (D, forced IIR)" legend; "distant response" → "far-field response" at 3 non-baseline sites.
## 2026-07-18 — MIG Short Paper Week 1

- Read the planning-with-files skill, `CLAUDE.md`, the full short-paper execution
  plan, its §1 mandatory wording rules, and both novelty-positioning addenda.
- Confirmed branch `impulse-native-constraint` and starting commit `b39c5d2`.
- Recorded unrelated dirty-worktree paths and adopted path-limited commits.
- Started A0 verification; no solver or benchmark behavior has been changed.
- Completed A0 and wrote `docs/mig2026_results_ledger.md`: 3 reported FEM-GT
  scenes vs 5 harness scenes; official MIG 2026 format/dates verified; Sheth
  2015 explicitly pending.
- Committed A0 as `c779b68`.
- Implemented and ran the measurement-only E-S1 impulse matrix port. The first
  full attempt was interrupted after finding the native-thin DCR mirror yielded
  a zero denominator; fixed the probe to read authoritative impulse arrays.
- Full E-S1: 24/24 finite, 24/24 pass both ledger verdicts, 0/24 ratio>1,
  ratio range 0.0301514327–0.5314210975, no governed reruns.
- E-S1 validation: CSV assertions passed; dedicated impulse suite 6/6 passed in
  14.40 s.

## 2026-07-18 — Review-response pass (plan §6), session start

- Server: compshare pod re-provisioned at a NEW host/port (`.env`:
  `cpod-1t0b3cmcyn8f:28432`, was `cpod-1skopckdit1u:28739`). Installed the
  existing pubkey via password auth and repointed the `compshare` alias in
  `~/.ssh/config`. Verified: RTX 4090 24 GB, driver 595.80.
- **The pod is FRESH**: no `~/DCR`, no `~/dcr-venv`. R7b therefore needs a full
  environment rebuild (clone + venv + warp) before its one command can run, and
  the branch is still not on GitHub. R7b remains non-blocking; not started.
- **R0 COMPLETE** (all ten §6.2 items in `paper/main_short.tex`):
  1. conclusion `1.0` → `0.53` (matches §3.1 and E-S1b);
  2. abstract "exceeds the supply bound" → incident-energy benchmark wording
     (no AVBD OFF-run Eq.-(2) measurement exists yet — E-S1b caveat 1);
  3. "injection threshold" → "incident-energy threshold" in both figure
     captions; one vocabulary across abstract/§3.1/conclusion;
  4. §3.1 now states the per-scene inversion in BOTH directions (worst-over-
     scenes XPBD 1.2e5 vs AVBD 1.70, but on the table scene AVBD 1.18/1.70 is
     worse than XPBD 0.37, which does not inject there);
  5. "all 72 measured cells" → 72 cells / 60 distinct configurations, with the
     bit-identical impulse relaxation pairs explained at the §3.1 occurrence;
  6. `truck` → "road slab" and introduced by geometry; machine sentence scoped
     to solver-behaviour numbers only; device hardware named (RTX 4090);
  7. η = 1 stated explicitly at Eq. (2) as the least restrictive value;
  8. deleted the abstract's "the quantity a contact reviewer will ask for";
  9. abstract "decays over six orders of magnitude" → the GAP to the reference
     shrinks by six orders (the ratio itself falls five);
  10. 21.6 mm normalized by board geometry (72% of the 30 mm thickness, 2.7%
      of the 0.8 m span) in §3.3 and Limitations.
- R0 acceptance PASSED: grep audit clean (0 hits for "supply bound",
  "injection threshold", "contact reviewer", "truck"); `latexmk -pdf` → 5 pages,
  0 undefined refs, 0 LaTeX warnings, worst overfull 1.98 pt; NUMBERS.md
  cross-check shows no conflict. Derived quantities + anchors frozen in
  `docs/mig2026_results_ledger.md` (new R0 section).
- No solver, benchmark, or scene code was touched. Text + ledger only.

## 2026-07-19 — R7b + R1 complete

- **R7b DONE** (out of order, user-approved: the pod was up and billing).
  Device timing re-verified on the re-provisioned compshare RTX 4090
  (`cpod-1t0b3cmcyn8f`, driver 595.80, CUDA 12.9, warp 1.15.0). Band
  5.6–9.2 → **5.0–8.9 ms** @16×4, all four scenes 3–11% faster. The road scene
  crossed 120 Hz on the mean (1.012×) but NOT on its worst step (9.31 ms), so
  §3.5 now calls it "at the boundary" rather than real-time. Frozen in the new
  `docs/mig2026_device_ledger.md` (separate file so the results ledger keeps
  its ARM-M4-only header). Machine/driver is confounded with commit — the pod
  was re-provisioned — and the ledger says so. Commits `250b45d` / `50d881d`.
- **R1 DONE.** New harness `run_eq2_utilization.py` measures Eq. (2) itself,
  un-governed, on all three backends. Measurement-only BY CONSTRUCTION: the
  solver's own ledger runs live while `passivity_gamma` is forced to 1.0, and
  every state write in each enforcement path is guarded by `if gamma < 1.0`,
  so the trajectory is bit-identical to a clamp-OFF run.
  - Result (strict reading, Eq. (2) as printed): XPBD violates **8/24**
    (margin up to +4.436×10⁷ J), AVBD **23/24** (but ≤ +15.08 J, and ≤0.15 J in
    21 of them), impulse **0/24** (worst −5.7×10⁻⁴ J).
  - **The two metrics diverge on AVBD**: R flags 2 cells, Eq. (2) is violated in
    23. That is the panel's blocker demonstrated rather than argued, and it is
    now the §3.1 "The ratio is not the invariant" paragraph.
  - Acceptance, all three pass: non-perturbation (11/11 frozen values reproduced
    exactly), impulse cross-validation (**0.00e+00** relative over 24 cells —
    bit-exact, since it is the same accounting not a replica), and a new
    bracket-contiguity probe (`probe_dErig_bracket.py`, sum|gap| = 0 J on all
    three backends).
  - Figure `fig_s1_solver_matrix` is now two rows: R on top, the signed Eq.-(2)
    margin in JOULES below (symmetric-log). Joules, not a second ratio —
    every candidate denominator misleads (see findings.md).
  - Prose re-based: abstract, §3.1 (new paragraph), Fig. 2 caption. "Injects"
    is now reserved for R (`exceeds R=1`), "violates" for Eq. (2).
- A metric I wrote was WRONG and is retracted in findings.md + the ledger: the
  plan's literal running-denominator U inflated sub-joule leads into "U = 20".
  Two matrix re-runs lost. The verdict is now absolute joules.

## 2026-07-19 — R2 complete

- **R2 DONE** (plan §6.4), text + ledger only, no new runs; the measured half
  reuses the R1 instrumented runs.
- §2 now states every term of Eq. (2) so a reader can recompute the reservoir
  unaided: E_mod = ½q̇ᵀM_q q̇ + ½qᵀK_q q; E_mod⁰ = 0 (scenes start undeformed
  and at rest, so the settling transient must be funded like anything else);
  the exact ΔE_rig = (E_rig⁻ − E_rig⁺) + W_g with W_g = Σ m_b g·Δx_b; E_rig
  purely kinetic, translational + rotational, over ALL dynamic bodies; the
  reservoir credit/debit rules; the closed-form γ = min(1, √((E⁻+B)/E⁺)) and
  why it is closed (E_mod is quadratic, so γ bounds KE and PE, unlike the
  velocity-only α); and η = 1 throughout.
- Guarantee named precisely: a **cumulative, gross-loss-funded storage ceiling
  on the modal subsystem** — explicitly NOT contact-port passivity and NOT a
  signed per-interface transfer bound.
- **New disclosure**: the printed inequality is stricter than the enforced one
  (the `passive()` one-substep allowance, 7–389 J here). §2 states it, states
  that the strict reading is used for both columns, and gives the governed
  worst margin (1.1×10⁻¹³ J) that makes that possible.
- Limitations gains the recycling caveat WITH its measured bound: return
  channel 0.4–27% (impulse), 3–32% (XPBD), 102–118% (AVBD), against the ≲1%
  plan §6.4 expected. The AVBD >100% is attributed to rigid-side energy
  creation (same family as the box–box rectification), not to the bound.
- "source-referenced" reduced from 3 loose uses to exactly 1, adjacent to its
  definition, per plan §6.4.
- All anchors recorded in `docs/mig2026_results_ledger.md`, including a
  corrected entry: `e_modal_0` IS rebased by two device-arm harnesses, so the
  device passivity rows use a more lenient baseline than the paper states.
- Builds clean: 5 pages, 0 undefined refs, 0 LaTeX warnings.

## 2026-07-19 — R3 complete

- **R3 DONE** (plan §6.5), all four items.
  - **T2 table** (paper Table 1, ~0.4 pp): per-formulation update level, contact
    treatment, modal weight, iteration structure, warm start and relaxation
    above the rule; h, substep semantics, modal rank (24/28/24), Rayleigh
    damping, stepper, η and machine held identical below it. Every entry read
    from code; the full anchor table is in the results ledger.
  - **Row-evaluation accounting**: K·S = 4/16/64/256 per frame — each rung
    quadruples the work, ×64 across the axis.
  - **Substep-only sweep** (NEW RUN, `out/substep_sweep.csv`): K=4 pinned,
    S∈{1,2,4,8}, shelf, all three hosts, both relaxes. XPBD violates 8/8,
    AVBD 7/8 (≤0.023 J), impulse 0/8.
  - **Complementarity residual vs K** (NEW harness
    `probe_complementarity_residual.py`, `out/complementarity_residual.csv`):
    2.79e-2 → 3.56e-6 over K=1..128, bottoms out by K=64.
  - Headline: **the equal-work comparison**. 32 row-evals as iterations →
    R=0.300, Eq. (2) holds; as substeps → R=3.13, +481 J. Iterations and
    substeps are not interchangeable.
- Paper is now **6 pages** (was 5) — still inside the CFP's 4–6 excluding
  references, but the headroom the plan assumed is largely spent. If R4/R5 need
  space, plan §6.12 says demote the substep sweep first, then the triptych.
- Builds clean: 0 undefined refs, 0 LaTeX warnings, no overfull boxes.
- Cross-platform test suite run on both machines at the user's request; the one
  failure is pre-existing on ARM too. No paper number comes from the x86 host.

## 2026-07-19 — R4 complete (negative result)

- **R4 DONE** (plan §6.6). New harness `run_selfconvergence.py`; XPBD extended
  to K ∈ {64,128,256,500} against the impulse oracle at K=500, plus
  state-level agreement on the deflection trajectory d_i = U_y[i]·q.
- **The plan's acceptance criterion is NOT met, and that is the finding.**
  |XPBD(500) − oracle| improves only 1.026× over the K=32 gap. XPBD plateaus
  by K≈64 at ratio 0.2996 vs the oracle's 0.2735 — a fixed point 9.6% away.
  State: peak deflection agrees to 2.4%, but trajectory L∞ is 34% of the
  oracle's peak, also flat from K=32.
- Interpretation, now in §3.2: the sweep separates a truncation pathology that
  convergence removes from a formulation difference that it does not. The two
  hosts discretize the same continuous law differently (position-level
  linearization, e=0, vs velocity-level implicit), so different converged
  solutions are expected. §3.2 reworded from "cured by convergence" to
  "largely cured ... removes the pathology outright".
- Ring frequency measured but NOT reported: window-dependent (15.6 Hz at 100
  frames vs 11.2 Hz at 300) because the deflection trace is sag-dominated over
  these windows. Energy/peak/L∞ are stable to 4 s.f. across both windows. The
  paper says so and points at the resolved full-FEM ring (78.0 vs 78.3 Hz).
- Builds clean: 6 pages, 0 undefined refs, 0 LaTeX warnings.

## 2026-07-19 — R5, R6, R7 complete (plan §6.7–6.9)

| item | code | paper |
|---|---|---|
| R5 usefulness | `65d5908` | `b359d0b` |
| R6 prior art | (no code) | `b359d0b` |
| R7 CPU cost | `bc56cf7` | `b359d0b`, `64a486c` (NUMBERS.md) |

Two new harnesses: `run_governed_accuracy.py`, `run_projection_validity_avbd.py`.
CPU timings re-measured on the M4 with the existing `run_perf_reps.py`.

Headlines:
- R5.1: energy error 196.5x -> 3.696x (oracle), 189.2x -> 3.558x (XPBD fixed
  point). Frozen cell reproduced EXACTLY (|diff| = 0).
- R5.1b: the governed trajectory is WORSE — Linf 33% -> 71% of reference peak.
- R5.1c: 99.6% of ungoverned energy sits ~200x above the substep rate; a scalar
  gamma fixes the amount, not the spectrum.
- R5.2: AVBD's projection is an order of magnitude gentler (1.4/3.1 mm vs 21.6).
- R5.4: 21.6 mm = 1.05-1.08x the peak deflection the board ever reaches.
- R6: 3 refs positioned; 2 were already in the bib and uncited; franken2011 added
  and DOI-verified.
- R7: the printed 0.8-2.9 ms was from the WRONG MACHINE and its upper bound was
  noise (sigma 95% of mu). Now 0.9-3.4% of baseline on the declared host.

Paper: 6 pages of body (references alone on p7), 0 undefined refs, 0 overfull
boxes. Substep sweep demoted to supplement per §6.12.

OPEN: R5.3 triptych — blocked on an interactive browser capture session (no
offscreen render path; same blocker as the video). R8 remains NO-GO.

## 2026-07-19 — codex round 2: C2–C7 complete, C8 open (plan §7)

| item | code branch | paper worktree |
|---|---|---|
| C2 terminology | `f9b8d6f` | `20409c5` |
| C3 ordering + ledger block | `7f7450a` | `5c79918` |
| C4 truncation scope | (none) | `6c57e2d` |
| C6 deployed budgets | `7ca41b9` (E-C6) | `c1ab0d6` |
| C7 citations | (none) | `2c2183f` |
| C5 wording + gate | `<plan §7.6>` | `1555d37` |

Every commit rebuilt and gate-checked: body ends p. 6, References alone on
p. 7, 0 undefined refs, **0 overfull boxes**.

Headlines:
- **C3 found a real error, as the review suspected.** The paper said the
  reservoir is credited "before the contact solve"; all three hosts credit
  AFTER the velocity solve in the same substep. Sentence fixed, code untouched,
  anchors frozen in the ledger. The 7-step loop is now printed in-paper.
- **C6 is the strong outcome, not the benign one the risk table hedged for.**
  At the deployed budgets (1×8, 2×4) the position-based host violates Eq. (2)
  in **6/6** cells, worst R = 2282 — on 8 row evaluations, *twice* the 4×1
  corner's 4. Governed: 18/18 hold. The motivation sentence is now measured.
- **C6 also corrected two of our own overreaching sentences.** §3.5's "host-side
  enforcement is not an interactive path" was a 16×4 conclusion stated
  generally — at 2×4 shelf and ledge fit 120 Hz *with* the governor. And
  Limitations characterised an Eq.-(2) result using R, the diagnostic this
  paper argues is misleading.
- **C5-G gate: NO-GO** (recorded in plan §7.6 with the reason). Fallback clause
  landed in §3.1, not merely planned.
- **C7**: 13 references render. kaufman2008's ACM article number is NOT guessed
  — dl.acm.org 403s automated fetches, so articleno/pages are omitted with a
  camera-ready note.

OPEN — **C8**, the only unfinished item:
- *Video* (60–90 s): still blocked on an interactive browser capture session.
  No offscreen render path exists; same blocker as R5.3.
- *Figure F-C8*: NOT blocked after all. `governed_accuracy*_traces.npz` holds
  (100 frames × 48 support rows) deflection fields for all four arms, so the
  deflection sequence can be rendered offline from frozen traces per §7.9's
  fallback. What it lacks is **page space** — see findings.md.
