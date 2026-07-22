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
# 2026-07-19 Six-Reviewer MIG Short-Paper Review

- Started a new six-reviewer audit of the user-specified PDF.
- Declared the reviewers as independent AI reviewer simulations and activated file-based planning for traceability.
- Locked the current 05:23 PDT seven-page artifact by full SHA-256 and extracted all text.
- Completed the first-pass claim/method/results/limitations reconstruction; visual inspection and current-rule verification remain in progress.
- Rendered and visually audited all seven pages. The PDF is clean and readable; six pages are body content and page 7 is references only.
- Verified the live official MIG 2026 call: length is compliant, scope fit is direct, and the rubric is now frozen for all six reviewers.
- Launched the first three isolated reviewers (technical physics, contact numerics, novelty/significance) and independently spot-checked the closest cited energy/contact work using primary sources.
- Received two isolated reviews: one weak reject (3/7) and one borderline/lean accept (4/7); launched evaluation and clarity reviewers as slots opened. Remaining reviewers have not seen these votes.
- First wave complete: scores 3, 3, and 4 (mean 3.33/7), all at confidence 4/5. Launched the senior-PC sixth review after the numerics slot opened.
- All six isolated reviews completed. Final scores are 3, 3, 4, 3, 3, and 5; vote split is four weak reject, one borderline/lean accept, one weak accept; every confidence is 4/5.
- Reconciled the panel into a weak-reject-as-framed recommendation with two revision paths: diagnostic-paper reframing as the practical route, or contact-consistent governed enforcement as the stronger method route.
- Prepared the final user-facing panel summary, format check, consensus strengths/blockers, and prioritized acceptance advice.
- Detected that `paper/main_short.pdf` was regenerated at 17:43 PDT after the sealed panel. Reopened the task and invalidated the old scores for the current artifact.
- Locked the replacement artifact (`103ac0e...`), extracted 7,075 words, rendered all seven pages, and began a fresh claim/method/evidence audit.
- Completed the full text audit through references. The regenerated build materially strengthens the teaser and explains cross-host confounds, strict-vs-implemented invariants, spectral behavior, recycling, and runtime limitations; the core contact-validity and governed-validation weaknesses remain.
- Visually inspected pages 1–4. No rendering defects found; the new hero figure and solver-matrix heatmap are clear, while the method/settings table remains compressed.
- Finished the visual audit. Found a new submission-critical delta: four conclusion lines spill onto page 7 before the references, so the current build appears to exceed a six-content-page limit. Also found stale “injection threshold” wording inside Figure 3.
- Began the live MIG 2026 rule check; located the official conference site after a domain-restricted search returned no results.
- Verified the official 2026 CFP. The body overflow onto page 7 is a real six-page-limit violation, and the current anonymous review PDF also lacks the required unique paper ID. Froze the official six-criterion rubric for the fresh panel.
- Confirmed all PDF fonts are embedded and no file attachments are present; recorded that `qpdf` is unavailable, while Poppler checks and rendering succeeded.
- Received the first fresh isolated report: novelty/significance reviewer votes 5/7 weak accept at confidence 4/5, principally on the diagnostic study rather than the governor.
- Received the physics/energy review: 3/7 weak reject at confidence 4/5. Scientific merit is near borderline if reframed as a diagnostic/emergency limiter, but current physical validity, validation, and format defects drive rejection.
- Received the contact/numerics review: 3/7 weak reject at confidence 4/5. It independently flags supply partition dependence, the mismatch between Eq. (2) and the stricter ledger policy, and causal/per-row overinterpretation.
- Received the evaluation/reproducibility review: 4/7 borderline at confidence 4/5, leaning scientifically positive under the short-paper bar but finding the current PDF administratively unready.
- Received the clarity/practitioner review: 3/7 weak reject at confidence 4/5; without the format defects it would be near borderline/weak accept on the diagnostic result.
- Received the senior-PC review: 3/7 weak reject at confidence 4/5, while judging the empirical diagnostic potentially publishable by itself.
- Rechecked the frozen hash and reconciled the senior review's Eq. (1) complaint as a reviewer misread: the outer minus applies to the full parenthesized surface height, so the printed Jacobian sign is correct.
- Completed meta-review calibration: scores `3,3,5,4,3,3` (mean 3.50/7, median 3), four weak rejects / one borderline / one weak accept, all confidence 4/5. Locked the recommendation to weak reject for the current PDF, with a credible acceptance path as a measurement-first diagnostic short paper.
- Marked the current-artifact review phases complete and prepared the final user-facing verdict, reviewer table, consensus evidence, and prioritized revision advice.

## P-round (plan §8) — executed 2026-07-19/20

| item | code branch | paper worktree |
|---|---|---|
| baseline checkpoint | — | `f14a138` |
| P0 spill + gate v2 + fig label | `dc440d2` | `1c1da83` |
| P1+P2+P4+P5 tex pass | — | `9e82ddf` |
| P7 / E-C9 ablation | `6f6e608` | — |
| P3+P6+E-C9 in §3.2 | — | `b2b179a` |
| P8 supplement | `412503a` | — |

Gate v2 (`scripts/check_page_gate.py`) green on every tex commit: body ends
p. 6, 0 overfull, 0 undefined, 18 references.

Headlines:
- **E-C9 took 6 seconds, not overnight.** 24/24 configurations still violate
  Eq. (2) with R > 1 across h, compliance, rank and damping. Both base rows
  reproduce the frozen E-S1b ratios EXACTLY (119534, 6333.22) — the
  non-perturbation proof.
- **The §8.4 rank contingency fired, in the good direction.** Excluding the
  stiff cluster cuts R 286× (shelf) / 36× (ledge) but the violation survives
  (+584 J, +1.24e6 J). Stiff-tail localization = sharpened diagnosis, exactly
  as pre-registered — not a retraction.
- **Two real errors found that neither panel caught.** Table 1's modal rank was
  the REQUESTED mode count, not the delivered one (24/28 → 16/16; the paper
  contradicted itself against §3.3). And §3.2's complementarity residual was
  dimensionally mixed *and* numerically just penetration in metres, with an
  unsupported "conditions begin to hold at K≈24". Both corrected.
- **P6(a)'s anticipated 10²–10³× drift floor was wrong** (real: 2–274×).
  Printed as measured, per D5.
- **P8.c's offline route did not exist** (traces hold deflection fields only),
  so the per-substep supply is now logged instead. Partition-dependence is real
  but ≤7.7%; long-horizon recycling is flat over a 10× horizon.
- **A large body of uncommitted prior work was found in both worktrees** and
  committed unchanged as a labeled baseline (`f14a138`) so the P-item diffs
  stay readable. The long-paper repositioning edits were left alone.

OPEN:
- **P8.d video** — blocked on the user's interactive capture session. Only
  user-action item; slot and note are in the supplement README.
- `\acmSubmissionID{}` — fill after EasyChair registration (window opens
  Jul 25).
- Submit ≥24 h before 2026-08-07 23:59 AoE.

# 2026-07-19 Current PDF + video-supplement six-reviewer rerun

- Reopened the six-reviewer task because the user explicitly supplied the current video supplement in addition to the PDF.
- Activated a fresh artifact lock and blind-panel run; prior panel scores will not be reused unless the PDF hash proves identical, and the supplement's evidentiary effect will be judged independently.
- Locked the new PDF as `627a14e...` and the supplement as `6dcd904...`; the PDF does not match the previously reviewed build, so a full fresh review is required.
- Extracted 7,323 PDF words and rendered all seven pages. Timestamped video-sheet creation hit a missing FFmpeg `drawtext` filter; switched to fixed-interval ordered sheets.
- Visually inspected the full-paper contact sheet and the first half of the video. The previous page-7 body spill is fixed; the supplement clearly demonstrates the steel-board stabilization and begins an honest soft-board counterexample.
- Completed the video visual audit. It is a useful, concise supplement that demonstrates both the success case and the governor's failure to recover a faithful trajectory; no audio stream is present or needed for the claim.
- Began the detailed PDF text audit and confirmed the revision now frames the projection as an audited emergency fail-safe rather than a constructive contact method.
- Audited the method and core results. The revision adds useful matched-within-XPBD convergence and robustness evidence, while still conceding the weaker implemented recursion, cross-host confounds, spectral non-correction, and substantial contact invalidity.
- Finished the PDF text and packaging audit. The body now fits six pages, fonts are embedded, and the supplement materially helps; the remaining likely administrative defect is the absent assigned paper ID.
- Began a live official-rubric check; direct URL opening was blocked by browser safety handling, so the next attempt will use an indexed official-domain result.
- Verified the live official MIG 2026 call through the site's own navigation. The paper fits the six-content-page limit and the video is eligible; the missing unique paper ID remains a mandatory pre-submission fix.
- Confirmed the MP4 decodes cleanly for all 1,343 frames and finished a close page-1 clarity check.
- Completed close visual inspection of the densest result/limitations pages; no rendering defect found, with information density remaining a presentation risk rather than a compliance problem.
- Marked artifact/rubric inspection complete and launched blind reviewers 1–3 (physics/energy, contact numerics, novelty/significance). Reviewers cannot access prior panel notes or one another's conclusions.
- First blind batch completed and remains sealed from later reviewers. Launched reviewers 4–6 (evaluation/reproducibility, clarity/practitioner, senior-PC generalist) with the same frozen artifacts and rubric.
- Confirmed the MP4 carries no author-identifying metadata; only generic FFmpeg encoder tags are present.
- All six blind reviews completed on unchanged hashes. Scores are `5,3,4,3,5,5` (mean `4.17/7`, median `4.5/7`), all confidence `4/5`: three weak accepts, one borderline lean reject, and two weak rejects.
- Reconciled the panel to a borderline/lean-weak-accept scientific recommendation under the short-paper bar, with a mandatory paper-ID fix and four high-impact scientific/reproducibility revisions before upload.
- Prepared the self-contained six-reviewer table, area-chair verdict, supplement assessment, and ranked pre-submission actions; all review phases are complete.
- The generic plan checker could not parse this repository's custom multi-project plan (`0/0 phases`); manual phase audit confirms current review phases 11–14 are complete.

# 2026-07-20 Current-artifact six-reviewer rerun

- Activated the file-based review plan and locked the user-specified PDF/video.
- Both artifacts changed after the last completed panel; all earlier scores were marked stale.
- Began phase 15: reconstructing and visually auditing the seven-page PDF and complete 44.77-second MP4 before launching six isolated reviewers.
- Extracted all 7,348 words and rendered all seven PDF pages; read the full method, results, limitations, conclusion, and references.
- Launched isolated reviewers 1–3 on physics/energy, contact numerics, and novelty/significance while the primary reviewer continued the artifact audit.
- Visually inspected all seven rendered pages; layout and six-page body compliance are clean, with only high information density and a missing visible paper ID as submission-readiness concerns.
- Rechecked the official live MIG 2026 CFP and froze its short-paper scope, page rule, review criteria, supplement allowance, anonymity requirement, and unique-paper-ID rule for this panel.
- Inspected the complete MP4 via full decode, ordered frames, and a two-second contact sheet. The video is technically clean, anonymous, visually legible, and scientifically candid about both stabilization and lost legitimate motion.
- Completed phase 15 after confirming font embedding, absence of PDF attachments, and unchanged artifact hashes; phase 16 (six isolated reviews) is in progress.
- Reviewers 1 and 3 returned independent weak-accept scores (both 5/7, confidence 4/5) and converged on an unprompted theorem/indexing inconsistency. Launched reviewers 4 and 5 as slots became available; all reports remain sealed from one another.
- Reviewer 2 returned `4/7` borderline/lean reject (confidence 4/5), adding a schedule-matched-reference concern. Reviewer 6 was launched in the freed slot; all six panel assignments are now underway or complete.
- Reviewer 4 returned `3/7` weak reject (confidence 4/5), driven chiefly by the missing ledger/code/data promised by the paper. Four reports are complete; reviewers 5 and 6 remain in progress.
- Reviewer 5 returned `5/7` weak accept (confidence 4/5), emphasizing practitioner value and clearer target/guarantee/observation terminology. Five reports are complete; only the senior generalist remains.
- Reviewer 6 returned `5/7` weak accept (confidence 4/5). Final panel: `5,4,5,3,5,5`, mean `4.50/7`, median `5/7`, four weak accepts versus one borderline/lean reject and one weak reject.
- Reconciled all reports into a borderline weak-accept scientific verdict, conditional on repairing the guarantee/indexing statement and attaching the promised reproducibility archive; prepared prioritized pre-submission advice.
- Rechecked both SHA-256 values after all six reviews; neither frozen artifact changed. Marked phases 15–18 complete and finalized the self-contained panel report.

# 2026-07-20 20:05 PDF + unchanged-video audit

- Activated the file-based review workflow for the user's six-reviewer request.
- Locked the current PDF at `4aea9e00...` and the MP4 at `30a862fa...`.
- The MP4 is byte-identical to the prior panel artifact, but the PDF changed from `276cc375...`; marked all earlier paper scores stale and began phase 19.
- Started phase 20 in parallel with artifact reconstruction: six reviewers receive only the frozen PDF/MP4 and a common 1–7 review scale; earlier planning/review files are explicitly off limits.
- Extracted the full PDF text, checked fonts/images, rendered all seven pages, and inspected a full contact sheet. The six-body-page plus references-only layout is visually clean, though information-dense.
- Read the abstract, contribution framing, method chronology, and strict-bound proof. The new PDF materially repairs the old theorem/indexing ambiguity by proving Eq. (2) directly with same-substep credit and debit.
- Completed the main text audit through conclusion. Corrected the metric count distinction (budget violations `9/24, 3/24, 0/24`; incident-ratio flags `8/24, 2/24, 0/24`) and recorded the evaluation strengths plus remaining supply, control, accuracy, contact-validity, and reproducibility limitations.
- Inspected pages 1–2 at original rendered resolution; both are clean and legible. Flagged the absence of a visible paper ID for later verification against the live CFP.
- Inspected pages 3–4 at original resolution. No visual defects; the revised proof and Figure 2 metric distinction are materially clearer than the stale reviewed artifact.
- Inspected pages 5–6 at original resolution. The evaluation and limitations are cleanly rendered, with no evidence-hidden-in-tiny-print issue beyond normal short-paper density.
- Inspected the references-only page 7 and fully decoded/re-sampled the unchanged 44.77-second MP4. The supplement remains technically clean and scientifically candid, but it visualizes only the XPBD shelf examples.
- Rechecked the official live MIG 2026 CFP. Confirmed the 4–6 content-page rule, rubric, supplement allowance, strong venue fit, anonymity requirement, and unique-paper-ID requirement.
- Finished the attachment/metadata/anonymity check. Neither artifact exposes an author identity; the PDF contains no embedded ledger/archive, confirming that the promised reproducibility material is absent from the supplied packet.
- Marked phase 19 complete after a full text, page, video, metadata, packaging, hash, and live-CFP audit; phase 20 remains in progress with isolated reviewers.
- Reopened the scientific consistency audit after directly comparing Figure 2 cells with the new prose. Confirmed a severe stale-figure/new-text conflict: heatmap `8/23/0`, AVBD max `15 J` versus prose `9/3/0`, AVBD max `6.7 J`; this must be treated as an acceptance blocker until the authoritative dataset is identified and every dependent claim is regenerated.
- Zoom-audited Table 1. Confirmed that `H_ii` is undefined and the displayed XPBD weight cannot be unambiguously verified; recorded this as a technical-clarity/reproducibility blocker rather than assuming the implementation itself is wrong.
- Five of six isolated reports are complete: scores `3,3,3,3,5`, all confidence `4/5` (four weak rejects, one weak accept). Reviewer 6 remains isolated and in progress; no report was shown to another reviewer.
- Reviewer 6 returned `2/7` reject and independently confirmed the Figure 2/prose mismatch. Final panel is `3,3,3,3,5,2` (mean `3.17`, median `3`; five reject, one weak accept; all confidence `4/5`).
- Reconciled the six reports with the primary artifact audit, rechecked both hashes unchanged, and marked phases 20–22 complete. Final advice: do not submit the current PDF; repair the authoritative data/figure/prose chain first, then address notation, artifact packaging, and the highest-value physical/evaluation controls.

# 2026-07-20 Q-round (plan §9) — response to the 4.17/7 video panel

Order: Q0 → Q1 → (Q2+Q3+Q4+Q7 as one tex pass) → full-audit rebuild →
Q5 fast path → Q8. Q6 deferred by advisor ruling (§9.8). Q9 gates every commit.

| item | code branch | paper worktree |
|---|---|---|
| Q0 baseline + panel log | `5aa9b96`, `06c0911` | — (verified, untouched) |
| Q1 supplement v2 | `ea795b5`, `fa6e08c`, `ecf3861`, `326817a` | `36679a6` |
| Q2+Q3+Q4 tex pass (Q7 dropped) | — | `96a6a71` |
| Q3 figure + video relabel | `b8dc2e4` | `67cb5e1` |

## Q0 — adjudicate baseline + log the panel (§9.2) — DONE

- Diff-verified the three uncommitted workstream docs before committing: one
  pure-append hunk each, no deletions — plan `+652` at line 816 (§8 P-round
  work order, never committed + §9 Q-round + §10 parking lot), findings `+47`
  at 1222 (the six-reviewer transcription), progress `+23` at 441 (the panel
  round-log). Committed as `5aa9b96`. `prompts/` left untracked (house
  convention); the sound-workstream WIP left alone.
- Paper worktree: **not literally clean, but provably disjoint** — see the
  findings note. `main_short.tex`, `NUMBERS.md`, `references.bib`, `latexmkrc`
  and all three figures the short paper `\includegraphics` are unmodified at
  the P-round head `0c0bb58`.
- Clean rebuild (`latexmk -gg -pdf main_short.tex`): 7 pages, 730,379 bytes —
  the same byte count as the reviewed PDF `627a14e…`, so the build is
  reproducible modulo timestamps. Gate v2 **PASS**: body ends p. 6, 7 pages
  total, 0 overfull.
- Frozen-number spot-checks (3/3 pass): worst-cell ladder `8.5e5 → 0.165`
  over K=1…32 (`main_short.tex:528` ← `k_convergence_ledge_worst.csv`,
  846352 → 0.165324); penetration `21.6` mm + `8.69×` corrective impulse
  (`:85,:547,:550` ← Table 2 rows); modal rank `16/16/24` (`:380` ←
  `scene_spec.csv` REALIZED, the P7 correction) and the `1.1e-13` J worst
  margin over 90 measured cells / 78 distinct (`:329,:82`).

## Q1 — supplement v2 (§9.3) — DONE

Delivered all seven elements (a–g). `mig26_supplement.zip`, **1.93 MiB**, well
under the 200 MB allowance.

| element | what landed |
|---|---|
| a. runnable snapshot | `code_snapshot.zip`, 128 files, built from `git show HEAD:` (no `.git`, no working-tree state); `scripts/`, `paper_fig/`, every `out/` and the assembler itself excluded |
| b. claim index | `CLAIMS_INDEX.md`, 27 rows, one per results section; **self-checking** — refuses to build if a row's tex anchor has left `main_short.tex` or its harness has left the ledger |
| c. version record | `requirements-freeze.txt` via `importlib.metadata` (this venv is uv-managed, has no `pip`; the first run silently wrote an empty file), 38 distributions + `CPython 3.12.12 on Darwin arm64` |
| d. smoke test | `smoke_test.py`: builds the shelf scene from source, checks rank 16 / 48 rows against Table 1, re-derives the 4×1 cell on all three hosts. Qualitative asserts, digits printed |
| e. sums + one zip | `SHA256SUMS` over 54 files; `shasum -c` 0 failures |
| f. video | wired in, byte-identical to the panel-reviewed artifact (1343 frames, 44.767 s, 1920×1080, sha `6dcd904…`). README §5 rewritten — it had claimed the video was "not included" and needed an interactive capture session, false on both counts since Jul 19 |
| g. anonymity | commit hashes → `<commit>` (15, mapping written outside the bundle); zip member paths scanned; repo URLs adjudicated individually against an allowlist |

Acceptance, all from a clean unpack of the zip:
- `shasum -a 256 -c SHA256SUMS` → 54 OK, 0 FAILED
- `python smoke_test.py` → exit 0, digits match the arm64 reference **exactly**
  (`R = 6333.221296009669`)
- `verify_paper_numbers.py --data data` → exit 0, 37 passed, 1 skipped (the
  one check that needs the paper source, which the bundle does not ship)
- independent re-scan of the final zip: **0** deanon hits, **0** commit-hash
  tokens over 179 text members including the snapshot
- CLAIMS_INDEX spot-check, 10+ rows re-derived from the bundled CSVs: rank
  16/16/24, rows 48/40/200, R>1 counts 8/2/0, Eq. (2) violations 8/23/0, worst
  R 119534, governed worst 1.22/0.87, AVBD worst margin 15.08 J, impulse least
  slack −5.74e−4 J, 4×8 ratio 3.13 / 480.9 J, ladder 8.46e5→0.1653, robustness
  24/24 over 2.54–4.67e5, penetration 21.6 mm, 1556/29.26/7.918 J, deployed
  6/6 worst 2282, baseline 10.99–125.63 ms — every one matching the paper

Three things Q1 found that were not on its list (details in findings.md):
- **A real deanonymization**: the author's own GitHub account in a vendored
  module docstring, which the P8 scan would have shipped once code was added.
- **`verify_paper_numbers.py` exited 1 on the P-round paper** — two checks went
  stale when the page squeeze deleted Table 2's AVBD rows. Repaired.
- **A real error in the paper**, found by extending that verifier: §3.3's
  penetration range was E-S3's shelf-only floor re-quoted as host-wide.
  Corrected `3.5`–`12.6×` → `3.1`–`12.6×` at both sites, ledger-first, and it
  slightly strengthens the sentence it appears in. New ledger entry **E-C9e**
  freezes the scene specification, which backed two printed Table 1/§2
  quantities with no ledger entry at all.

## Q2 + Q3 + Q4 — one tex pass (§9.4–§9.6); Q7 dropped (§9.9) — DONE

Audit tables for all three are in findings.md, every site adjudicated.

- **Q2.** `eq:budgeted` is now equation (4): the one-deposit-relaxed bound has
  its own number, Prop. 2.1 guarantees *that*, and the sketch points at it. The
  vocabulary map is applied at the two claim sites the panel named — the
  abstract's "enforced by a reservoir" and the contribution bullet — each now
  splitting *guarantees* (the relaxed display) from *observed* (strict Eq. 2,
  90 cells). Zero "enforced up to X" phrasings.
- **Q3.** Every arm identity was derived from manifests and CSVs before any
  rename. All three teaser manifests are `solver: xpbd, converged: 500x1` with
  ref peak 8.223580660384274 J = `arm:xpbd_converged` to 16 digits, so Fig. 1's
  reference is Term B and its caption was the panel's exact catch. The 7.92 J
  site is `arm:oracle` = Term A and was already right. One site — "at a
  converged budget" — named *no* arm and would have been renamed wrongly by a
  blind sweep. "Converged" now survives at 2 sites, both backed by the checked
  4.9e-4 spread.
- **Q4.** `formulation` survives at 3 sites (title per plan §8.3, the abstract's
  family list paired with "three tested implementations", and franken2011's
  control formulations); 4 sites changed. The Limitations closer gains the
  explicit "one implementation of each". The row-law convention needed no
  change — P2 had already standardized it.
- **Q7 DROPPED.** The future-work clause fits at neither full nor compressed
  length. §9.9 makes it the first thing to drop when the gate is red and §9.13
  ranks it below further cuts, so it was dropped rather than funded.

Page budget: Q2's display cost a full page, recovered in §9.13's order —
(iii)'s prose, the abstract/contribution sentences, then §8.2's named ladder
rung (Fig. 2's candidate-denominator sentence) and the hatched-rows sentence
that duplicated the body. **No frozen number touched.** Gate v2 green on every
commit; `verify_paper_numbers.py` 38/38; the claim-index self-check still
resolves every tex anchor after the edits.

Video re-render (E-C9f) verified label-only: **1343 frames, 44.766667 s,
1920×1080, yuv420p, 30/1 fps, 1 stream** — every property identical to the
panel-reviewed render. Fig. 1's text extraction shows exactly one changed line.
New sha `30a862fa…` supersedes `6dcd9042…` and is what the bundle now carries.

## Q5 — fast path unavailable, nothing shipped (§9.7)

The 21.6 mm cell is **shelf 4×1**, and **no frozen trace carries 4×1 body
poses**: the three pose-carrying teaser traces are 8×2, 1×8 and 1×8, and the
four other trace files hold deflection fields only. The teaser was built around
a production-like cell, so the adversarial corner the paper leans on was never
recorded with poses. The boot prompt scopes this session to the fast path, so
Q5 ships nothing and the round ships the Q3-relabelled 44.8 s cut — which §9.7
explicitly permits.

Two options preserved for the PI, neither built (findings.md has the detail):
a deployed-1×8 close-up at the printed **9.8 mm** (poses exist, no new physics),
or the §9.7 slow path — one serial ARM replay of shelf 4×1 with pose capture,
frozen as E-C11, reproducing 21.6 mm to printed precision as its
non-perturbation check.

## Q8 — HANDOFF TO PI (§9.10)

### Where each panel priority landed

| panel priority | landing site | commits | status |
|---|---|---|---|
| (1) reconcile/prove or rename the exact invariant | `eq:budgeted` is now eq. (4); Prop. 2.1 guarantees *that*; abstract + contribution bullet split *guarantees* from *observed* | paper `96a6a71` | **narrowed** — the loop still guarantees only the relaxed bound; no site now implies otherwise |
| (2) attach the ledger, commands, configs, plot data, hashes, code/data snapshot | `mig26_supplement.zip` — 26 data artifacts, 128-file runnable snapshot, CLAIMS_INDEX, smoke test, pinned versions, SHA256SUMS, video | code `ea795b5`, `fa6e08c`, `ecf3861` | **closed** |
| (3a) "three tested implementations" / "row law" consistently | 4 `formulation` sites → implementations; explicit "one implementation of each" in Coverage; row law already standardized by P2 | paper `96a6a71` | **narrowed** — title keeps "Cross-Formulation" per plan §8.3 |
| (3b) standardize reference names | Term A/B fixed; "converged" reserved for checked criteria; figure + video re-rendered label-only | paper `96a6a71`, `67cb5e1`; code `b8dc2e4` | **closed** |
| (4) add the assigned EasyChair paper ID | `\acmSubmissionID{}` placeholder in place | — | **OPEN — user action, see below** |
| (5) an isolated or physics-matched contact control | Q6, **deferred by advisor ruling** (§9.8); design preserved for the long paper | — | not attempted, by decision |
| (bonus) video penetration close-up | Q5 — fast path structurally unavailable | — | **open by decision**, options below |

### What is deliberately unaddressed, so a reviewer repeating it is no surprise

Unchanged from §9.1's tail and still conceded in-text: governed-vs-FEM
validation; n = 3 hosts, one implementation each; the AVBD overdraft mechanism
(measured, unexplained); contact-consistency, which is the §10 long-paper track
and carries R8's NO-GO evidence. The supply remains a scene-wide gross sum
rather than contact-port work — now *measured* (partition ≤ 7.7%, recycling
flat over 10×) but conceptually unchanged, and §4 says so.

### Three actions before upload

1. **EasyChair opens Jul 25** — register, put the assigned ID in
   `\acmSubmissionID{}` (`paper/main_short.tex:41`), rebuild, re-run the gate,
   and re-check the portal's video specs.
2. **Re-run the assembler LAST**, after the final commit, so the snapshot and
   sums reflect it:
   `.venv/bin/python benchmarks/paper_eval/x1_passivity/make_supplement.py`
3. **Decide Q5** (optional, the only open scientific choice): ship the
   44.8 s cut as reviewed, or add a close-up — either a deployed-1×8 one at the
   printed 9.8 mm from existing poses, or the 21.6 mm cell via one serial ARM
   replay frozen as E-C11.

### The one thing to carry in your head

**The video we ship is not the video the panel reviewed.** Same 1343 frames,
same 44.766667 s, same cut — three label strings changed, because the old ones
called the XPBD self-reference "the converged reference". New SHA-256
`30a862facd530dd31741e41ef1774582f2d46d42ad3043ce5bc56f5a267a5d54`, frozen as
ledger E-C9f, and it is what the bundle carries.

### Final state

Gate v2 green on every tex commit of the round; final build body ends p. 6,
7 pages, 0 overfull, 0 undefined, 732,900 B. Banned-term grep clean — every
hit is the header comment listing them, plus `real-time` describing prior work
and the explicit "we make no unqualified real-time claim" disclaimer.
`verify_paper_numbers.py` 38/38. Clean-unpack acceptance of the bundle: 54/54
checksums, smoke test exit 0 reproducing the frozen digits exactly, bundled
verifier exit 0. Independent anonymity re-scan of the final zip: 0 deanon hits,
0 commit-hash tokens over 179 text members. Deadline: submit ≥ 24 h before
**2026-08-07 23:59 AoE**.

# 2026-07-21 Current PDF + video six-reviewer audit

- Activated the file-based review workflow for the user's requested six-reviewer panel.
- Confirmed that both supplied artifacts exist and that the PDF was regenerated after the prior completed panel; prior scores will not be reused.
- Began phase 23: freeze hashes, reconstruct the paper, and inspect all paper/video evidence before opening the isolated reviewer rounds.
- Locked the PDF at `6907a3bb...` and the video at `30a862fa...`; extracted the full paper, rendered seven pages, and fully decoded the 1,343-frame video without error.
- A domain-restricted search did not index the live CFP; switched to a broad conference-title search while retaining official-site-only evidence.
- Located the official MIG 2026 homepage and followed its own Call for Papers link; the browser cache missed the target, so the exact official page will be fetched read-only instead of retrying the failed click.
- Retrieved the exact official CFP after the sandboxed proxy path failed. Froze its 4–6-page short-paper rule, supplement allowance, anonymity/ID rule, and six review criteria as the common panel rubric.
- Read all 7,412 extracted words and completed a claim/equation/results/limitations consistency pass. The main figure/prose counts now agree; the principal remaining concerns are implementation-vs-formulation attribution, severe projection-induced contact error, absent promised reproducibility material in the supplied packet, and one categorical AVBD claim in the conclusion.
- Launched isolated reviewers 1–3 on energy accounting, contact numerics, and novelty/significance. They were barred from prior reviews and repository history.
- Visually inspected pages 1–2 at original render resolution; they are clean and legible, with a strong evidence-forward teaser, but no visible unique paper ID.
- Visually inspected pages 3–4; the proof, implementation table, and two-metric matrix are clean, internally consistent, and dense but readable.
- Visually inspected pages 5–6; all evidence renders cleanly and the body fits the six-page limit, while the AVBD conclusion overstatement remains the clearest internal wording defect.
- Inspected the references-only page and a uniformly sampled contact sheet spanning the entire video. The supplement is polished and candid but visually covers only XPBD shelf examples, not the cross-formulation matrix or worst contact-validity cost.
- Audited the video's first 18 seconds at 1 fps; the comparison is causally legible and temporally synchronized, with only secondary text approaching small-player readability limits.
- Audited seconds 18–36 at 1 fps; the soft-board example and renderer limitation are presented transparently, and the supplement supports boundedness while openly showing loss of fidelity.
- Audited the final 8.77 seconds at 1 fps; the invariant plot and final qualification card are accurate and anonymous.
- Completed phase 23. All pages, frames via full decode and 1 fps audit, metadata, format, hashes, and official rules are frozen; phase 24 (six isolated reviews) is in progress.
- Confirmed zero PDF attachments and anonymous XMP metadata.
- Reviewer 3 returned independently at 4/7 (borderline leaning reject, confidence 4/5). Launched Reviewer 4 on evaluation/reproducibility in the freed slot; no report was exposed to another reviewer.
- Reviewer 2 returned independently at 3/7 (weak reject, confidence 4/5). Launched Reviewer 5 on practical value, presentation, and video in the freed slot; reports remain sealed from all other reviewers.
- Verified Reviewer 2's two internal wording findings directly in the frozen PDF: “equal cost” contradicts the body’s unequal-cost disclosure, and the abstract's formulation-level attribution is broader than the one-implementation-per-class design.
- Reviewer 1 returned independently at 3/7 (weak reject, confidence 4/5), finding the proposition algebra sound but questioning discrete supply semantics and long-horizon boundedness. Launched Reviewer 6, the senior generalist, in the freed slot.
- Reviewers 5 and 4 returned independently: 5/7 weak accept and 3/7 weak reject, both confidence 4/5. Five reports are complete; only the isolated senior-generalist report remains.
- Reviewer 6 returned independently at 5/7 weak accept, confidence 4/5. Final panel scores are `3,3,4,3,5,5` (mean 3.83, median 3.5; three weak rejects, one borderline leaning reject, two weak accepts).
- Reconciled every report against the frozen PDF/video. Consensus is strong on venue fit, phenomenon value, proof plausibility, candor, implementation confounds, weak physical meaning of the global observer, contact-validity cost, and missing artifact; disagreement is whether the empirical diagnosis alone clears the short-paper bar.
- Rechecked both artifact hashes unchanged, marked phases 24–26 complete, and prepared the self-contained weak-reject/borderline recommendation plus paper/video revision priorities.

# 2026-07-21 Immediate six-reviewer rerun

- User requested a complete rerun. Reopened the review workflow and marked every previous score stale pending a fresh artifact lock.
- Began phase 27; the live official MIG rubric verified earlier today remains the common standard, but all artifact findings and reviewer judgments will be regenerated independently.
- Locked the new PDF at `32f2951d...` and unchanged video at `30a862fa...`; fully decoded the MP4 and extracted/rendered all seven new PDF pages.
- Diffed the new build against the prior reviewed extraction. It directly fixes three former panel criticisms (implementation-specific abstract framing, equal-row-count wording, and categorical AVBD conclusion) and adds a warm-start ablation; phase 27 visual/text audit continues.
- Read the revised method/results/conclusion. The paper also adds a full band-limited injecting-cell result (6/8 remain, worst +1.24e6 J), materially addressing a prior generality objection while leaving the core contact-validity and one-implementation limitations unchanged.
- Launched isolated rerun reviewers 1–3 on energy accounting, numerics, and novelty; none received the delta or previous panel output.
- Inspected new pages 1–2 at original resolution; the repaired abstract is cleanly typeset and page layout remains submission-ready apart from the absent assigned paper ID.
- Inspected new pages 3–4; the added warm-start evidence is readable and causes no overlap, clipping, or new heatmap inconsistency.
- Inspected new pages 5–6; band-limited evidence and the corrected AVBD conclusion render cleanly, with the six-page body intact.
- Inspected references page and revalidated the unchanged full video/contact sheet. Completed phase 27 and moved the six-reviewer rerun into phase 28.
- Immediate rerun: sealed Reviewer 2 completed at **4/7 (borderline), confidence 4/5**.
- Immediate rerun: sealed Reviewer 3 completed at **5/7 (weak accept), confidence 4/5**.
- Immediate rerun: sealed Reviewer 1 completed at **4/7 (borderline), confidence 4/5**.
- Immediate rerun: Reviewers 4 and 5 are running as isolated clean-room reviews; Reviewer 6 was launched into the freed clean-room slot.
- Immediate rerun: sealed Reviewer 4 completed at **4/7 (borderline), confidence 4/5**.
- Immediate rerun: sealed Reviewer 5 completed at **5/7 (weak accept), confidence 4/5**. Reviewer 6 remains in progress.
- Immediate rerun: sealed Reviewer 6 completed at **5/7 (weak accept), confidence 4/5**.
- Immediate rerun panel complete: scores `4, 4, 5, 4, 5, 5`, mean/median `4.50/4.5`, all confidence `4/5`; reconciled verdict is borderline/weak accept leaning accept under the focused short-paper bar.
- Rechecked the frozen PDF/video hashes after all six reports; both remain unchanged. Completed phases 28–30 and prepared the self-contained rerun report.

# 2026-07-21 Rewrite-plan amendment integration

- User authorized direct edits to the rewrite plan only. Restored the file-based planning context and began phases 39–42.
- Locked the correction that the configured XPBD baseline already uses an implicit-midpoint modal restoring step; the integrated plan will test shared-row block coupling separately from any stiffness-aware contact-weight counterfactual.
- The manuscript, benchmark implementation, figures, and video remain out of scope for this turn.
- Integrated E1b into the evidence plan as a deterministic paired perturbation audit, with separate physical and row-order cohorts and no population-statistics claim.
- Replaced the ambiguous E6 with E6a-1 shared-row condensation, feasibility-gated E6a-2 stiffness-aware contact weighting, an outcome interpretation matrix, and a replicated E6b method gate.
- Moved priority/fallback rules into Stage B/G, added corresponding acceptance checks, and replaced the appended override section with a concise integrated-amendment audit trail.
- Completed a structural readback: all numbered sections are present, E1b/E6a/E6b are in the main evidence sequence, the Stage B/G gates are coherent, and Section 14 explicitly distinguishes a major paper rewrite from a technical restart.
- Final validation passed: tracked planning-file diffs have no whitespace errors, the rewritten plan has no trailing whitespace, and only the requested plan plus the planning logs were touched during this integration turn. Phases 39--42 are complete.
- Began phases 31–35 for a structural rewrite plan centered on the fixed-host XPBD practitioner. Recorded the diagnostic-versus-method decision rule and the intended solver-choice hierarchy; no manuscript or benchmark source has been changed.
- Inventoried the current short-paper structure and evidence/visual footprint. Confirmed that the main structural change is to move the empirical XPBD failure and practitioner decision path ahead of the governor/proof, while treating AVBD/impulse as controls.
- Audited the exact abstract, introduction, contribution list, limitations, and conclusion. Identified the missing first-page answer to “why retain XPBD?” and the need to reorder both contributions and conclusion around a solver-choice operating guide.
- Confirmed the six-page body gate and inventoried reusable generated figures. Established a three-visual priority that favors the practitioner workflow and XPBD operating envelope over a co-equal three-solver narrative.
- Checked current full-FEM/reduced evidence and existing solver infrastructure. Classified the current fidelity result as sufficient motivation evidence, a modal/full-space cost comparison as optional, and an XPBD-host/implicit-modal hybrid as the method-paper stop/go experiment rather than a required diagnostic rewrite.
- Mapped the current content by rendered page and drafted the target page inversion: practitioner failure first, operating envelope in the middle, and the governor/proof only after its fixed-host necessity is established.
- Audited mechanism-related assets. Identified an exact-host iteration-matrix analysis and a frequency-cutoff-by-iteration ladder as the two highest-value scientific additions, while explicitly excluding a nonmatching device-Jacobi spectral-radius result from the short-paper evidence.
- Verified that the key practitioner/mode-reduction references and automated page/build gates already exist. No new literature search is required for the rewrite plan; final bibliography metadata and repeated page/overfull checks remain explicit release gates.
- Completed phases 31–35 and created `docs/mig2026_practitioner_diagnostic_rewrite_plan.md`: a 615-line executable plan covering paper identity, claim/nonclaim matrix, six-page storyboard, figure and video redesign, required/optional experiments, method-paper stop/go criteria, rewrite order, reproducibility packet, and adversarial re-review gates.
- Confirmed via git status that the planning work changed only the new plan and the three persistent planning logs; `paper/main_short.tex` and `paper/main_short.pdf` remain untouched.
- Began phases 36–38 to review the user's modified practitioner-diagnostic rewrite plan read-only. The assessment will separate critical scientific/logic issues from optional editorial refinements.
- Read the complete modified plan. The prior 14-section structure remains coherent; the material addition is section 15, which adds variance/replication, a minimal hybrid ablation, deadline/fallback prioritization, and a metric-count safeguard. Began validating its panel references and feasibility assumptions.
- Verified the amendment's committee citations and “non-negotiable pair” wording against the saved six-reviewer report. Located the exact XPBD and impulse solver implementations for a feasibility audit of the proposed minimal modal-weight ablation.
- Compared the XPBD and impulse modal-update maps. Found that the proposed E6a conflates three possible changes (modal integrator, row effective mass, and dense support block solve); it needs a precise counterfactual definition before it can serve as causal evidence.
- Verified the frozen paper harness already enables XPBD's implicit-midpoint modal step. Concluded that section 15's “explicit modal-block integration” wording is the one material technical defect in the amendment and drafted a cleaner two-factor E6a definition.
- Completed the full coherence review with exact line locations. The amended plan is strong overall; only E6a's causal variable and E1b's deterministic perturbation protocol require correction before execution.
- Completed phases 36–38 without editing the user's plan or manuscript. Final assessment: retain section 15, correct E6a because baseline XPBD already uses implicit-midpoint modal restoration, define E1b as an explicit perturbation ensemble rather than a seed rerun, and then execute the committed-core/fallback schedule.

# 2026-07-21 EXECUTE practitioner-diagnostic rewrite

- Read the rewrite plan in full + skimmed findings/task_plan/progress. Confirmed
  branch layout by git: 3-host sweep on `impulse-native-constraint`
  (`benchmarks/paper_eval/x1_passivity/`), paper on orphan worktree `paper/`
  (`c15457c`). Verified fallback PDF `32f2951dd1446708…` and snapshotted it to
  scratchpad (also recoverable via `git show c15457c:main_short.pdf`).
- Inventoried the harness: 38 frozen CSVs in `out/`; every C1–C5 headline number
  has a real source file. Located E6a-1 infrastructure (`_support_block` in
  `SolverXPBD`) and confirmed E1/E1b harnesses do not exist yet.
- **Stage A COMPLETE.** Wrote `docs/mig2026_claim_sheet.md` (C1–C5 → one frozen
  source each; nonclaims hard filter; terminology rules; self-audit table).
  Baseline terminology audit of `main_short.tex`: passivity prose clean, 8/24 vs
  9/24 distinct, DCR/real-time clean; 3 residuals logged for Stage E. Three
  claims flagged as pending Stage-B evidence (E1b, E6a-1, E1). No manuscript or
  solver file touched this stage.
- Next: Stage B — build + freeze E1 (accounting audit), E1b (deterministic
  perturbation ensemble), E6a lock + E6a-1 (serial-row vs `_support_block`).

## 2026-07-21 Stage B — E1 + E1b COMPLETE

- **E1 accounting audit** (`run_e1_accounting_audit.py`): reused R1's live-ledger
  + neutered-gamma contract. Two no-injection controls (resting_no_impact,
  modal_freevib) × 3 hosts × 3 scenes × 4 budgets. **AVBD/impulse accounting
  floor ≤ 10⁻³ J, 3–4 orders below the 6.7 J AVBD effect** — including the dinner
  scene where the 6.7 J lives (AVBD −8×10⁻⁴ J). The cross-host control claim
  STANDS, no narrowing. Bonus: the bare XPBD symplectic modal stepper amplifies
  even resting-settle/kick energy at starved budgets (off-floor, moot, vanishes
  with budget) — consistent with its 4.4e7 J catastrophe.
  - Traps hit + fixed: (1) accidentally clobbered the frozen `eq2_utilization.csv`
    by running R1 with default `--out` → restored from git; **all my Stage-B
    harnesses use distinct `--out`.** (2) `cargo_material=None` does NOT remove
    the standing books (48 support contacts remain) → relabeled "freefall" as the
    honest "resting_no_impact"; shelf modal gravity is 0.0 so a strict no-contact
    run is a trivial floor. (3) dinner builder uses `pot_drop_height`/`pot_v0_y`,
    not `impactor_*`.
- **E1b neighborhood robustness** (`run_e1b_neighborhood.py`): deterministic, no
  RNG/seed/p-value. **All four injecting headline cells inject in 16/16
  perturbations** (12 physical + 4 row-order, cohorts separate), margin log-spread
  0.31–0.70; **equal-row inversion robust** (32×1 holds ∀, 4×8 injects ∀);
  **scene-dependence robust** (XPBD never injects on dinner). The 4.4e7 J headline
  is the max of a **2.2–4.5e7 J** neighborhood — round to that precision.
  - Discovery: post-build DCR-body AND solver-state (`_X`,`_pos`) edits do NOT
    propagate (solver re-reads build-time pose each step). Perturbations must go
    through builder kwargs. `sol._support` permutation DOES propagate (row-order
    cohort). Added **default-inert** `impactor_dx/dz/tilt` to shelf+ledge builders
    (dinner already has `pot_drop_xz`); verified byte-identical at defaults
    (shelf 4×1 R=6333.22 reproduces).
- Frozen in `docs/mig2026_results_ledger.md` (E1, E1b sections) and claim sheet.
- Uncommitted code changes on `impulse-native-constraint`: 2 new harnesses, 2
  default-inert builder edits. Not committed yet (holding for a checkpoint).

## 2026-07-21 Stage B — E6a lock + E6a-1 COMPLETE; Stage B closed

- **E6a vocabulary lock**: claim sheet §3a. Three variables kept separate;
  E6a-1 ablates ONLY variable 3 (serial vs block row treatment). Baseline
  integrator stays implicit-midpoint (nonclaim 9).
- **E6a-1** (`run_e6a1_block_condensation.py`): serial (`_support_block=False`,
  paper path) vs block condensation (`_support_block=True`), 2 scenes × 4
  budgets + a first-contact one-step delta. **Block does NOT cure the injection**
  — comparable at 4×1, markedly WORSE at 8×2/16×4/32×1 where the serial path
  converges/holds (shelf 32×1 serial R=0.30 holds, block R=12.5 injects; ledge
  32×1 serial 0.087 holds, block 66.5 injects). One-step first-contact delta
  (identical pre-state): ledge serial +37 J vs block +631 J. Refutes "block solve
  fixes XPBD"; CONFIRMS the truncation thesis (serial converges with iterations).
  Recommendation unchanged: iterate the serial path. Reproduced 2 scenes × 4
  budgets, so above the one-cell-probe bar.
- **E6a-2 DEFERRED** (stretch): feasibility gate not run; E6a interpretation
  reported from E6a-1 alone with the E6a-2 column left un-inferred (plan rule).
- **Stage B exit gate MET**: E1/E1b/E6a-1 frozen in the ledger; the E6a-1
  negative result reported honestly, not rescued; no one-cell claim; all numbers
  frozen. Fixed a real one-step-audit bug (twin builds diverge by frame 10 → use
  the first-contact substep where pre-states are byte-identical).
- Next: E4 is "Next"-tier but Stages C–G (the rewrite) are committed core and
  take priority. Moving to Stage C (recompose Figs 1–3 + decision Table 1); E4
  slots into Table 1's matched-cost row.

## 2026-07-21 Stage C — Figure 2 + Table 1 done (Fig 1/Fig 3 pending)

- **Figure 2 recomposed** (`benchmarks/paper_fig/fig_xpbd_map.py` →
  `fig_xpbd_map.pdf`, staged to `paper/figures/`): XPBD-centered dual heatmap
  (R diagnostic + Eq.2 margin invariant, 24 cells) + a compact 3-implementation
  control strip (XPBD/AVBD/implicit: cells R>1|Eq2, worst margin, worst R) with
  the E1 floor note. Caption discipline "one implementation each; not
  compliance-/cost-matched." Visually verified legible. The full 3-solver 72-cell
  heatmap (`fig_s1_solver_matrix.py`) is kept for the supplement.
- **Table 1 drafted** (`docs/mig2026_decision_table.md`): LaTeX + full provenance.
  Rows in plan §5 order (implicit / more-iterations / block-condensation /
  governor / ungoverned). The block-condensation row reports E6a-1's NEGATIVE
  result ("not a fix; worse at deployable budgets"), not a recommendation.
- **Paper build still intact**: `main_short.tex` UNTOUCHED; only a new figure PDF
  + reference docs added. Fallback `32f2951d` preserved. The text rewrite
  (Stages D–E) is the next focused effort and will edit main_short.tex with
  build-gate checks after each edit.
- **Pending Stage C**: Fig 1 (teaser + schematic), Fig 3 (operating envelope:
  R/margin vs K, complementarity vs K, band/E6a-1; annotate 32×1/4×8 + warm-start).
- **Uncommitted on `impulse-native-constraint`**: 3 new harnesses (E1/E1b/E6a-1),
  2 default-inert builder edits, 1 new figure generator; + docs (claim sheet,
  decision table, ledger E1/E1b/E6a-1 sections), planning files. Paper worktree:
  1 new staged figure PDF. Nothing committed (per base rule: commit only when
  asked) — a checkpoint commit is available on request.

## 2026-07-21 Stage D COMPLETE + Stage E in progress — paper reframed, 6 pages

- **Stage D (north-star text) DONE**, all edits in `paper/main_short.tex`:
  - Title → "When Modal Contact Rows Fail in Fixed-Budget XPBD: Diagnosis and an
    Operating Guide" (plan §1 preferred).
  - Abstract → 6-sentence practitioner blueprint with the frozen numbers,
    reflecting E1 (control floor <1e-3 J), E1b (4.4e7 = max of 2.2–4.5e7 J
    neighborhood), and E6a-1 (block condensation does NOT fix it).
  - Intro ¶1–2 → practitioner audience + why-modes-vs-full-space + the WHY-TWO-WAY
    argument (one-way double-counts energy; vibration-affects-contact) + the dense
    shared-q trap + explicit scope ("if architecture unconstrained prefer implicit;
    target is the fixed XPBD host").
  - Contributions → reordered (workflow+failure / mechanism+guide / guardrail).
  - Conclusion → ordered decision rule (plan §5), ending on the durable warning;
    E6a-1 negative folded in ("nor condensing the shared support rows … removes it").
  - Keywords → dropped "passivity". Prior-art 2¶ → 1 compact "Related work" ¶.
  - **Exit gate MET**: title+abstract+teaser+conclusion answer all 5 reader Qs.
- **Stage E (partial)**: swapped Fig 2 → `fig_xpbd_map`, Fig 3 →
  `fig_operating_envelope` (figure*, updated captions); moved the host-difference
  Table 1 (`tab:solvers`) to the supplement (critical differences folded into
  prose, both refs fixed); removed the monitor-only device-GPU paragraph.
  **Page gate PASS: body ends p.6, 7 pages, 0 overfull, refs resolve,
  verify_paper_numbers 32/0.** Paper is length-valid + coherently reframed —
  NOT a broken intermediate.
- **Fallback preserved**: `git show c15457c:main_short.pdf` = 32f2951d (untouched).
  Current `main_short.pdf` is the new reframed build (uncommitted on `paper`).
- **REMAINING Stage E**: (1) structural reorder — move the empirical failure
  before the bound/proof (§2↔§3; needs care with eq:invariant forward-refs);
  (2) insert decision Table 1 (needs ~15 lines recovered, or keep as the
  conclusion's prose decision rule); (3) limitations consolidation. Then Stage F
  (E0 packet re-run + video per §12) and Stage G (6 isolated reviewers vs the
  32f2951d fallback).

## 2026-07-21 Stage E COMPLETE — 6-page body rebuilt (reorg + evidence + compression)

All edits in `paper/main_short.tex`; built + page-gated after every meaningful
edit. Committed-core body is done.

- **Structural reorder (plan §11 Stage E item 1 — the big one).** Split old §2
  "The row and the cumulative bound": the row + invariant + supply definitions +
  the two diagnostics stay up front as §2 "The row and the invariant it must
  respect" (light; `sec:row`); the enforcement loop, `eq:gamma`, Prop + proof
  moved AFTER Results into a new §4 "A last-resort guardrail" (keeps `sec:bound`
  label, so the L174/L498 refs still resolve). New section order: Intro → §2 row+
  invariant → §3 "The failure at a fixed budget" (matrix, kconv) → §4 guardrail
  (+ `sec:validity` cost) → §5 "Fidelity and runtime" (gt, cost) → Limitations →
  Conclusion. Empirical failure now precedes the bound/proof, as the plan wants.
  Also moved the governed-sweep result ("all 72 cells hold") out of §3.1 into §4
  where the governor is defined.
- **Evidence integrated into body prose** (was only in captions/abstract):
  - E1 → one-line control note folded into §3.1 "ratio is not the invariant"
    ("gravity/no-contact audit puts the control floor <1e-3 J … 6.7 J is real
    injection, not accounting noise").
  - E1b → replaced the old single-setting "Not a knife-edge configuration" ¶ with
    the 16/16 sign-robustness + log-spread 0.31–0.70 + equal-row-inversion +
    scene-dependence ensemble; 4.4e7 J now stated as the max of a 2.2–4.5e7 J
    neighborhood (abstract/§3.1/conclusion already agreed).
  - E6a-1 → new §3.2 ¶ "Condensing the shared rows is not the fix" (cites Fig 3c;
    R=12.5/66.5 at 32×1 block vs serial 0.30/0.09), with the required diagonal-
    rigid-body-block disclosure. Vocabulary lock held (only serial-vs-block varies).
- **Count consolidation (plan §8):** 72/60/90/18 gathered into the §4 "governor
  holds" ¶; removed the duplicate governed-18 result from §3.2.
- **Limitations** compressed 4¶→3¶ ("Stability is not accuracy" / "Scope of the
  row" / "Supply and coverage"); all recycling/partition/coverage caveats kept.
- **Table 1 = FALLBACK (plan §11 E-item-3 sanctioned).** Page 6 was full to the
  line; the decision table (~18 lines) would not fit without gutting evidence, so
  the conclusion keeps the ordered decision rule in prose and `sec:validity` notes
  the decision table lives in the supplement. **Stage F TODO: make_supplement.py
  must bundle `docs/mig2026_decision_table.md`.**
- **Terminology sweep clean:** no "explicit modal"; every "passiv*" is literature
  or negated; bare "XPBD" only names the family/host/prior-work/defined-terms
  (softened abstract "catastrophic XPBD amplification" → "this … amplification");
  8/24 (incident-ratio) vs 9/24 (strict Eq.2 margin) distinct everywhere.
- **Exit gate MET:** body ends p.6, refs p.7, 0 overfull, all refs resolve,
  `verify_paper_numbers` 32/0. Visual read-through of all 6 pages: coherent, both
  figures legible.
- Next: **Stage F** (E0 supplement re-assemble incl. the decision table + E1/E1b/
  E6a-1 CSVs; video §12; \acmSubmissionID after EasyChair opens Jul 25), then
  **Stage G** (6 isolated reviewers vs the 32f2951d fallback).

## 2026-07-21 Stage F — E0 supplement synced + video asset inventory

- **E0 supplement DONE and verified.** The Stage E reorg drifted 12 CLAIMS
  anchors; re-synced `make_supplement.py`:
  - Fixed 8 drifted tex anchors; replaced the single-setting robustness row with
    E1b; added E1 + E6a-1 rows; dropped device + 9.8mm rows (not in the short
    paper); updated moved-section labels (§3.3→§4.1, §3.4→§5.1, §4→§6).
  - Added E1/E1b/E6a-1 CSVs+manifests and their ledger sections to the bundle;
    removed the device CSVs; bundled `DECISION_TABLE.md` (Table 1 fallback).
  - **Verified:** check_claims 0 failures (29 rows); anonymization scan PASS
    (0/0); clean-unpack `smoke_test.py` PASSED (rebuilds shelf 4×1, XPBD
    R=6333.22 exact vs arm64 ref); SHA256SUMS 63/63 OK. Committed 4b33aa9.
  - NOTE: the bundled `teaser_video.mp4` is still the OLD video; the FINAL
    assembler run is the LAST Stage-F step, after the new video + acmSubmissionID.
- **Video: asset inventory written** (`docs/mig2026_video_asset_inventory.md`).
  §12 storyboard mapped beat-by-beat: REUSE the launch (6–18 s) + containment
  (37–46 s) beats; NEW = schematic (0–6), 32×1-vs-4×8 (18–29), band panel
  (29–37), penetration close-up, decision card (46–55). Pipeline present
  (render3d.py, make_teaser_video.py, record_teaser.py, frozen poses, ffmpeg).
  **One real risk:** the 32×1/4×8 equal-row 3-D poses may be blocked (memory
  `[[mig-qround-queued]]` Q5 "no 4×1 poses"); mitigation = render that beat as a
  2-D frozen-curve overlay (substep_sweep/k_convergence), no pose needed.
- **Blocked (external):** `\acmSubmissionID{}` needs EasyChair registration,
  window opens **2026-07-25**.
- **Remaining:** render the video (4 new 2-D assets are cheap/data-frozen; the
  one 3-D beat has the pose risk + 2-D fallback), then final `make_supplement.py`
  run; then **Stage G** (6 isolated reviewers, comprehension Qs before scores,
  compare vs the 32f2951d fallback, ≤1 rewrite cycle).

## 2026-07-21 (session 2) — teaser label fix + density/length reduction

- **Teaser fixed** (`fig_teaser.py`, commit 0910037): the three panel titles
  overflowed their ~1-inch panels and collided ("governed (containment)XPBD
  self-reference"). Shortened "XPBD self-reference"→"XPBD self-ref." and dropped
  the title font 6.6→5.7pt; all three now fit cleanly. Regenerated + copied to
  paper/figures (paper commit ffaf08e).
- **Density/length** (paper commit ffaf08e): reduced the body from a packed 6
  pages (0 slack) to end partway down p.6 (~5.5 content-pages), less dense:
  proof→induction sketch, (1)-(7) loop→compact prose, spectral/accuracy/contact
  blocks tightened, §5.1/§5.2→headline facts. Gate PASS (0 overfull), verify
  32/0, check_claims 0.
- **References-packing wall (documented):** cutting BELOW ~5.5 pages pushes the
  18-entry bibliography onto a sparse p.7 that trips a ~1.3pt "\vbox too high
  while \output active" overfull (acmart last-page balancing). Tried \raggedbottom,
  the `balance` package, figure-shrink, and deeper prose cuts — all re-triggered
  it. The current length is the SHORTEST that keeps the references page
  non-sparse. A firm 5.0 with 0 overfull needs either trimming ~2 citations
  (scholarship call — deferred to the user) or moving §4.1/§5 detail wholesale to
  the supplement (a larger restructure). Over-cuts (intro/§2/abstract/§3.1/§4/§5
  merge) were made then REVERTED once they broke the gate.
- **Video boot prompt written**: `prompts/mig_short_video_boot.md` — self-
  contained Stage-F video task for a fresh session (reads the asset inventory,
  the §12 storyboard, the pose risk + 2-D fallback, and the final supplement
  re-run). This is the user-requested "clear prompt to start in the new session."
