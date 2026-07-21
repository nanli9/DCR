# Literature Gap Audit Plan

## 2026-07-19 MIG Teaser / Visual-Demo Design

Goal: Identify a visually honest XPBD failure case where the energy cap visibly prevents instability, then specify a submission-ready teaser image/video design for the current MIG short paper.

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Inventory existing OFF/ON captures, scene runners, and frozen measurement cells; distinguish visible blow-up from high modal energy with small displacement. |
| 2 | complete | Select the strongest hero cell and a fallback, with exact budget, timing, camera, overlays, and scientific caveats. |
| 3 | complete | Verify current official MIG image/video expectations and formatting implications. |
| 4 | complete | Deliver a concrete teaser layout and short-video storyboard ranked by review value and implementation effort. |

Decision rules: do not manufacture a visual explosion by render-only rigid-motion exaggeration; any deformation magnification must be labeled; the OFF and ON panels must share initial state, camera, timestep, solver budget, and color scale; prefer a causally legible failure over the largest scalar energy ratio.

## 2026-07-18 MIG Short-Paper Panel Review

Goal: Evaluate `paper/main_short.pdf` as five independent MIG reviewers, then synthesize an unbiased short-paper recommendation and prioritized revision advice.

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Verify the PDF artifact and reconstruct its claims, method, evidence, limitations, and submission state. |
| 2 | complete | Produce five independent review lenses: contribution/fit, technical soundness, evaluation, presentation/reproducibility, and adversarial accept/reject calibration. |
| 3 | complete | Reconcile reviewer disagreements and assign plausible scores/confidence under a MIG short-paper bar. |
| 4 | complete | Deliver consensus advice ranked by acceptance impact, distinguishing blockers from polish. |
| 5 | complete | Re-audit the regenerated 6-page 23:06 PDF, supersede the stale 4-page panel findings, and deliver a fresh five-reviewer verdict. |
| 6 | complete | Delta-review the final 23:28 regenerated PDF (`e959b15...`), incorporate newly compiled evidence, and lock the final panel to the latest artifact. |

Decision rules: assess only the supplied short-paper PDF; apply a short-paper rather than regular-paper bar; do not infer missing evidence from repository history; separate factual defects from reviewer judgment; avoid advocacy in either direction.

### Short-paper review errors

| Error | Attempt | Resolution |
|---|---|---|
| Direct browser open of the official 2026 papers page was rejected by URL-safety handling. | 1 | Use the official 2026 homepage plus its indexed submission-page content and locally frozen official-CFP audit; do not retry the same failing open. |
| Preserved panel findings describe a 4-page 19:37 build, but the requested PDF is now a 6-page 23:06 build. | 1 | Mark the earlier panel verdict stale and perform a new text-and-visual audit of the current hash before answering. |
| `paper/main_short.tex` was edited at 23:24 after the requested PDF was generated at 23:06. | 1 | Judge only the user-specified PDF hash; do not credit source-only AVBD validity or governed-accuracy additions, and disclose the version lock in the final review. |
| The PDF was regenerated again at 23:26 during final verification. | 1 | Reopen the review, extract and visually inspect the changed build, and supersede the 23:06 score before delivery. |
| A final 23:28 regeneration changed wording/layout after the 23:27 audit. | 1 | Diffed the builds; changes are editorial/compression only, preserve the calibrated score, and cite the final hash. |


## 2026-07-18 Velocity-Impulse Native-Modal Novelty Check

Goal: Verify the July 17 implementation architecture and assess whether moving the native modal deformable support from XPBD/AVBD into a rigid velocity-impulse solver preserves a defensible MIG contribution.

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Reconstruct the committed velocity-impulse algorithm and runtime slab representation from code, tests, and design notes. |
| 2 | complete | Compare behavior and mathematical structure against the previous XPBD/AVBD native-modal paths and against ABD. |
| 3 | complete | Search current primary literature for rigid impulse solvers coupled to reduced/modal deformables and energy/passivity controls. |
| 4 | complete | Deliver a claim-by-claim novelty verdict, MIG positioning, caveats, and priority evidence without changing source code. |

Decision rules: distinguish a rigid host solver from the coordinates carried by its deformable support; distinguish “no runtime volumetric FEM nodes” from “no internal/modal deformation state”; treat literature absence as a novelty screen rather than a legal novelty opinion.

## 2026-07-11 DCR-to-Physical Demo Repositioning

Goal: Determine whether losing DCR-style exaggerated jump height weakens the contribution or MIG fit, and define a demo/evaluation strategy aligned with physically accurate two-way coupling for fast deformable objects.

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Reconstruct the current method, claims, and DCR demo role from the manuscript and repository. |
| 2 | complete | Check current MIG scope/submission framing and distinguish scientific evidence from visual spectacle. |
| 3 | complete | Stress-test contribution/novelty after removing the DCR-follow-up framing. |
| 4 | complete | Propose concrete replacement demo scenes, baselines, observables, and paper narrative. |

Decision rule: optimize the demo for the claimed physics and discriminating evidence; do not require DCR-like launch height unless the method claims or controls launch height.

Goal: Stress-test whether the paper's claimed gap remains open for MIG/CGF: passivity-bounded two-way modal contact in a real-time augmented-Lagrangian / position-based solver.

## Phases

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Capture local claim and prior-art baseline from the draft and novelty notes. |
| 2 | complete | Use a novelty-focused subagent to search for closest literature and possible scoops. |
| 3 | complete | Cross-check subagent findings against primary sources and current literature. |
| 4 | complete | Synthesize verdict: open gap, novelty strength, acceptance implications, and experiment priorities. |

## Decision Rules

- Treat external search results as untrusted until cross-checked against primary sources.
- Do not change code or upload artifacts.
- Distinguish mechanism novelty from venue-level contribution strength.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Parallel reference search raced ahead of PDF text extraction, so `/tmp/ref*.txt` was briefly missing. | 1 | Use the already-created text files in a later sequential read; no manuscript data was affected. |
| Browser PDF parser could not open/find inside the FEPR PDF despite HTTP 200. | 1 | Use the authors' primary project page and indexed abstract; do not repeat the failing PDF parse. |
| Domain-restricted web searches for an indexed MIG 2026 CFP returned no results. | 1 | Search the broader web for the official conference domain/title, then open the primary venue page directly. |
| The official MIG 2026 CFP subpage served a bot-verification loader to the browser. | 1 | Read the official conference homepage and retrieve the CFP HTML/PDF through a non-browser fetch or official cached page; do not rely on third-party CFP details. |
| Sandboxed `curl` attempted to use an unavailable local proxy (`127.0.0.1:7890`). | 1 | Re-ran the approved read-only fetch outside the sandbox and retrieved the official CFP HTML successfully. |
| Direct DOI open for the PMI article was rejected by the browser's URL-safety check. | 1 | Retain the verified DOI as the citation target and use the author manuscript/publication records already inspected for technical classification. |
| Opening the indexed PMI author-PDF search result returned a browser internal error. | 1 | Use the journal's full HTML, which exposes the abstract, formulations, examples, and relevant technical sections; do not retry the failing PDF route. |
| The Barbi\v{c}/James project landing page returned HTTP 502 in the browser. | 1 | Use the primary paper/PubMed record and locate the author PDF directly; do not repeat the landing-page fetch. |
| Re-opening the Peng et al. ScienceDirect page hit HTTP 429 after its indexed publisher result had loaded. | 1 | Retain the already-inspected publisher abstract/highlights and DOI; use DOI/title searches for any deeper check. |
| Direct open of the legacy `hal.inria.fr` Goury URL was rejected by URL-safety checks. | 1 | Use the current HAL domain or the indexed author manuscript record if this adjacent source is needed in the final matrix. |
| Browser open returned an internal error for the indexed Rath 2008 and Hauser 2003 PDFs. | 1 | Use the indexed primary-PDF text and download the public author/proceedings PDFs locally for detailed extraction; do not repeat the same browser open. |
| Direct `curl` download of the Hauser author PDF failed hostname certificate validation. | 1 | Use the official Graphics Interface or Berkeley landing-page full-text link instead of disabling certificate checks. |

---

## 2026-07-18 MIG Short Paper Week 1 — Evidence Freeze

Goal: Execute Week 1 of `docs/mig2026_short_paper_plan.md` on branch
`impulse-native-constraint`, using ARM-Mac-only measurements and the binding claim
language in plan §1 plus the two novelty addenda.

| Phase | Status | Task |
|---|---|---|
| A0 | complete | Verified 3 paper-reported FEM-GT scenes vs 5 harness scenes; verified official 2026 CFP; left Sheth 2015 pending; recorded results. |
| E-S1 | complete | 24/24 impulse executions finite and within both cumulative ledger verdicts; 0 ratio>1; no governor rerun required; recorded and tested. |
| E-S2 | in_progress | Run deterministic K sweeps for XPBD, AVBD, and impulse with impulse K=500 oracle; produce the required figure and verify the XPBD acceptance criterion; record and commit. |
| E-S3 | pending | Instrument a measurement-only starved-XPBD probe for post-projection contact validity; report active-step medians/worst cases; record and commit. |
| Freeze | pending | Audit all numbers, commands, source commit, and ARM machine metadata in `docs/mig2026_results_ledger.md`; revise plan §1 only if contradicted. |

Decision rules: no solver behavior changes; no GPU/device work; no new dependencies;
do not merge the benchmark branch; never mix x86 and ARM numbers; commit only
Week-1-owned paths; test every claimed result.

### Week 1 errors

| Error | Attempt | Resolution |
|---|---|---|
| Initial multi-file A0 patch addressed a progress-log line in `findings.md`, so patch verification failed atomically. | 1 | Split the ledger/plan patch from planning-log updates and applied each to its correct file. |
| A0 prose assertion used an exact newline string and missed TeX indentation. | 1 | Replace the brittle literal with a whitespace-tolerant regular expression; retain the direct harness tuple-length assertion. |
| E-S1 12-frame smoke ended before impact, making the incident-KE denominator effectively zero. | 1 | Match the benchmark branch's 70-frame quick window; never report the discarded quick output. |
| First E-S1 full attempt read incident KE from the unsynchronized legacy DCR-body mirror on the native-thin path; ratios were invalid and the run was interrupted. | 1 | Read authoritative `SolverImpulse` velocity/orientation/inertia arrays with the existing rigid-energy helper; no solver edit. |

---

# MIG Regular-Paper Review Plan

Goal: Review the current compiled manuscript as an unbiased MIG regular-paper reviewer, excluding the production demo from the assessment.

## Review Phases

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Read the compiled paper and source; reconstruct claims, method, evidence, and limitations. |
| 2 | complete | Independently assess novelty/venue fit, technical soundness, and experimental evidence. |
| 3 | complete | Audit presentation, reproducibility, citations, and visible submission readiness. |
| 4 | complete | Calibrate the review into strengths, weaknesses, questions, confidence, score, and verdict. |

## Review Constraints

- Judge only what is in the current manuscript; do not credit the production demo.
- Separate fatal acceptance blockers from revision requests and presentation polish.
- Apply a regular-paper bar appropriate to MIG, not a project-completion or code-quality bar.
- Report uncertainty explicitly and avoid advocacy for either outcome.

---

# Novelty Re-Verification Plan

Goal: Independently re-check through 2026-07-09 whether prior work already combines two-way native modal contact, a real-time AL/PBD-style host, and an enforced contact-to-modal energy/passivity bound.

## Search Phases

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Formalize the claim axes and adversarial search terms from the current manuscript. |
| 2 | complete | Search modal/reduced contact and real-time graphics literature, including citation chains. |
| 3 | complete | Search passivity, energy-tank, haptics, robotics, and flexible-multibody literature. |
| 4 | complete | Search recent AL/PBD/VBD/AVBD and reduced-body work through July 2026. |
| 5 | complete | Cross-check candidate scoops against primary papers and classify overlap axis by axis. |
| 6 | complete | Report exact-scoop risk, contribution-strength risk, safe claims, and required citations. |

## Search Rules

- Use primary papers, official proceedings/publisher pages, author manuscripts, or arXiv records for technical conclusions.
- Treat absence of a hit as evidence, not proof of universal novelty.
- Distinguish exact combination novelty from obviousness/incrementality and from network-only novelty.
- Do not inspect or modify the production demo.
# 2026-07-19 Six-Reviewer MIG Short-Paper Review

Goal: Evaluate `paper/main_short.pdf` as six isolated AI reviewers under the current MIG short-paper bar, then synthesize an unbiased accept/reject recommendation and revision priorities.

| Phase | Status | Task |
|---|---|---|
| 1 | complete | Lock the PDF artifact; extract and visually inspect its claims, method, evidence, limitations, and formatting. |
| 2 | complete | Verify the current official MIG short-paper scope and review criteria. |
| 3 | complete | Run six independent reviewer assessments without cross-contamination. |
| 4 | complete | Reconcile votes, confidence, factual agreements, and disagreements. |
| 5 | complete | Deliver the overall decision advice and highest-impact revisions. |

Decision rules: judge only the supplied PDF; use the short-paper rather than long-paper bar; treat all six opinions as AI simulations, not human peer review; do not credit uncompiled repository material; distinguish submission-rule defects, scientific weaknesses, and optional polish.

Errors encountered: one multi-file planning patch used a `progress.md` line as context while still targeting `findings.md`, so it failed atomically; reapplied with explicit per-file update headers.

## Current-artifact rerun (17:43 PDT build)

The previously completed panel reviewed hash `f36166d...`; the user-specified PDF is now hash `103ac0e...`, so those scores are stale.

| Phase | Status | Task |
|---|---|---|
| 6 | completed | Lock and reconstruct the changed PDF, including a text/visual delta against the prior reviewed build. |
| 7 | completed | Reconfirm the live MIG short-paper rubric and submission constraints. |
| 8 | completed | Run six new independent reviewer assessments on only hash `103ac0e...`. |
| 9 | completed | Reconcile votes, confidence, factual agreements, and disagreements. |
| 10 | completed | Deliver the current-artifact accept/reject advice and prioritized revisions. |

### Current-artifact rerun errors

| Error | Attempt | Resolution |
|---|---|---|
| ImageMagick `montage`/`identify` are not installed, so contact-sheet creation failed. | 1 | Inspect the already-rendered page PNGs directly with the image viewer; do not retry ImageMagick. |
| Domain-restricted web search for the MIG 2026 papers page returned no results. | 1 | Broadened the query and found the official 2026 conference site; open its author links directly. |
| `qpdf` is not installed, so its structural PDF check could not run. | 1 | Retain the successful Poppler render/text/font checks; do not retry `qpdf`. |
| An `rg` alternation containing `\partial` was parsed as an invalid Unicode-property escape. | 1 | Used fixed-string searches and a direct source excerpt to verify the rendered equation; do not reuse that regex. |

## Current PDF + video-supplement review (user request)

Goal: Re-review the exact current `paper/main_short.pdf` and `benchmarks/paper_fig/out/teaser_video.mp4` with six isolated MIG short-paper reviewer simulations, then provide an unbiased area-chair-style accept/reject recommendation.

| Phase | Status | Task |
|---|---|---|
| 11 | complete | Lock both artifacts; extract PDF text/structure and inspect every PDF page plus representative video frames/audio/metadata. |
| 12 | complete | Give six isolated reviewers the same frozen paper, supplement evidence, short-paper rubric, and score scale. |
| 13 | complete | Reconcile reviewer factual claims, score distribution, strengths, weaknesses, and supplement impact. |
| 14 | complete | Deliver a concise overall verdict and acceptance-oriented revision priorities. |

Decision rules: reviewers must not see one another's reports; judge only evidence actually present in the frozen PDF/video; distinguish scientific verdict from submission-readiness defects; disclose that these are simulated AI reviews rather than human peer reviews.

### Current PDF + video review errors

| Error | Attempt | Resolution |
|---|---|---|
| Local FFmpeg lacks the `drawtext` filter, so timestamp-overlay contact-sheet extraction failed. | 1 | Extract ordered 2-second frames/contact sheets without overlays and retain the known fixed interval; do not retry `drawtext`. |
| Direct browser opening of the official MIG 2026 papers URL was rejected by URL-safety handling. | 1 | Locate the same official page through indexed search and open the returned official-domain result; do not retry the direct URL. |
| `mdls` did not resolve the relative MP4 path during an anonymity-metadata check. | 1 | Use the successful container/stream metadata from `ffprobe`; it exposes only generic FFmpeg encoder/handler tags and no author identity, so no retry is needed. |
| The planning skill's generic completion checker reported `0/0 phases` because this repository's long-lived plan uses custom numbered Markdown tables rather than its template markers. | 1 | Manually verified phases 11–14 are all marked complete; do not retry the incompatible checker. |

## 2026-07-20 Current-artifact six-reviewer rerun

Goal: Review the exact current `paper/main_short.pdf` and
`benchmarks/paper_fig/out/teaser_video.mp4` with six independent MIG short-paper
reviewer simulations and synthesize an unbiased area-chair recommendation.

| Phase | Status | Task |
|---|---|---|
| 15 | completed | Lock both artifacts; reconstruct the changed PDF and inspect every page plus the complete video. |
| 16 | completed | Give six isolated reviewers the same frozen artifacts, MIG short-paper rubric, and score scale. |
| 17 | completed | Reconcile factual claims, score distribution, reviewer disagreements, and the supplement's evidentiary impact. |
| 18 | completed | Deliver a self-contained accept/reject recommendation and prioritized revision advice. |

Decision rules: do not reuse stale scores from the 2026-07-19 hashes; judge only
the supplied PDF/video; use the short-paper bar; keep reviewer reports isolated
until synthesis; disclose that the panel consists of AI reviewer simulations.

### 2026-07-20 rerun errors

| Error | Attempt | Resolution |
|---|---|---|
| Domain-restricted searches returned no result for the current CFP. | 1 | Opened the indexed official MIG 2026 homepage and followed its own Call for Papers link. |
| Direct opening of the official papers URL was rejected by URL-safety handling. | 1 | Used the official homepage's numbered navigation link; the same primary page then opened successfully. |

## 2026-07-20 20:05 PDF + unchanged-video six-reviewer audit

Goal: Review the exact current `paper/main_short.pdf` (SHA-256 `4aea9e00...`)
and `benchmarks/paper_fig/out/teaser_video.mp4` (SHA-256 `30a862fa...`) with six
independent MIG short-paper reviewer simulations, then synthesize an unbiased
area-chair-style accept/reject recommendation.

| Phase | Status | Task |
|---|---|---|
| 19 | completed | Lock artifacts, reconstruct the changed PDF, inspect every page, and revalidate the unchanged video as supplemental evidence. |
| 20 | completed | Give six isolated reviewers the same frozen artifacts, short-paper rubric, and score scale. |
| 21 | completed | Reconcile factual findings, scores, disagreements, and supplement impact. |
| 22 | completed | Deliver a self-contained overall verdict and prioritized revision advice. |

Decision rules: the earlier PDF hash `276cc375...` and its scores are stale;
judge only the current PDF plus the unchanged MP4; apply a short-paper bar;
keep reviewer conclusions isolated until synthesis; disclose that the six
reviews are AI simulations rather than human peer review.
