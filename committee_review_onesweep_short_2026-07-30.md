# MIG 2026 Short-Paper Panel Review

Date: 2026-07-30  
Review type: six isolated AI reviewer simulations plus area-chair synthesis  
Paper: `onesweep_short.pdf`  
Video supplement: `onesweep_scene_video.mp4`

## Artifact lock

- PDF SHA-256:
  `8a77cf7947971f3c0f56789c5c7f9dd16a4a2c1ca3fcc72328ae1e5acc9003c1`
- Video SHA-256:
  `a9ef4e4158734e98fd040f698e0007dacd595e27ed6e7611c7d91207988a7901`
- PDF: 716,167 bytes; seven letter-size pages; six body pages with
  references beginning on page 6 and continuing onto page 7.
- Video: 8,065,820 bytes; 50.2 seconds; 1920x1080; 30 fps H.264;
  1,506 frames; no audio stream.

The end-of-panel hashes matched the frozen copies reviewed by every panel
member. The PDF contains no embedded files.

## Rubric and protocol

The panel applied the live
[official MIG 2026 short-paper call](https://mig.siggraph.org/2026/papers.htm).
It defines short papers as focused results, emerging ideas, or concise
technical contributions; permits 4--6 body pages excluding references; and
reviews originality, technical quality, clarity, significance,
reproducibility where applicable, and MIG relevance.

Each reviewer received a fresh zero-context thread, the same frozen PDF/video
pair, the same rubric and 1--7 score scale, and a different primary lens.
Reviewers were forbidden from reading repository history, paper/benchmark
source, planning files, historical reviews, or one another's reports. All six
read the complete paper, visually inspected every page, and inspected the full
video timeline before scoring.

These are independent AI reviewer simulations, not human peer reviews.
Isolation reduces anchoring between simulated reviewers; it does not turn the
vote distribution into a statistical estimate of human acceptance probability.

## Panel result

| Reviewer | Primary lens | Score | Confidence | Video effect |
|---|---|---:|---:|---|
| R1 | Mathematical soundness | 5/7, weak accept | 4/5 | Raises confidence, not score |
| R2 | Novelty and significance | 5/7, weak accept | 4/5 | Raises 4 to 5 |
| R3 | Evaluation and reproducibility | 5/7, weak accept | 4/5 | Raises confidence, not score |
| R4 | Clarity and presentation | 5/7, weak accept | 4/5 | Raises 4 to 5 |
| R5 | Practitioner value and MIG fit | 5/7, weak accept | 4/5 | Raises 4 to 5 |
| R6 | Senior generalist calibration | 5/7, weak accept | 4/5 | Raises confidence, not score |

Distribution: `5, 5, 5, 5, 5, 5`  
Mean, median, and mode: `5`  
Area-chair recommendation: **5/7, weak accept**  
Area-chair confidence: **4/5**

The unanimity is meaningful in one limited sense: six different review lenses
found the scoped result acceptable and none found a theorem-invalidating
error. It should not be read as a prediction of unanimous human acceptance.

## Area-chair synthesis

### What the paper establishes

Under one cold, restitution-free, frictionless, normal-only unilateral row and
one Gauss--Seidel sweep, the paper gives a reconstruction-dependent energy
sign boundary. With restorative velocity reconstruction
`qdot+ = kappa Delta q / h`, the mass-only row injects exactly when

`kappa^2 + (omega h)^2 > 2 + m/M`.

The reconstruction-matched restorative operator

`G = kappa^2 M_c + h^2 K_c`

used through `W = G^{-1}` in both the row denominator and the actual
restorative correction yields the displayed one-sweep inelastic-loss identity.
The passive family `0 <= W <= 2 G^{-1}` exposes a useful accuracy-versus-margin
choice, while the ordering result explains when a trailing restorative row
does or does not remove the injection.

The coordinator and R1 independently re-derived the scalar boundary, the
matched loss, the passive-family congruence, and the ordering/relaxation
relations. R1 additionally ran 789 exact-rational check groups, including
off-diagonal multicoordinate cases, without finding a core contradiction.

This is a credible, moderately original, focused short-paper result. It is a
row-local diagnostic and intervention, not a passivity theorem for a complete
contact solver.

### Strongest acceptance case

1. **Sound, checkable narrow theorem.** The central algebra is concise,
   falsifiable, and survived independent derivations and randomized/exact
   checks.

2. **Reconstruction dependence is practically important.** A
   backward-Euler-shaped weight can itself inject on the shipped `kappa=2`
   reconstruction. Treating the host's velocity read-back as part of the
   effective row operator is the paper's strongest insight.

3. **Good claim discipline.** The paper explicitly disclaims novelty for
   finite-iteration injection, modal embedding, effective mass, and converged
   dissipativity. It also separates passivity from accuracy.

4. **Broad validation design for six body pages.** The phase map, nonmodal
   collapse, exact-rational checks, reconstruction controls, ordering tests,
   27-cell shipped-row test, equal-cost comparison, and negative
   warm/two-row scan probe different parts of the claim.

5. **Strong MIG fit.** This is a solver-level contribution about visible
   secondary motion under a fixed interactive budget. The video makes the
   practical failure and the weight-only intervention legible.

### Strongest rejection case

The theorem excludes the regimes that dominate ordinary production contact:
warm state, simultaneous active rows, friction, restitution, and every
intermediate iteration count `1 < n < infinity`. The paper's own out-of-scope
stress test shows that the matched charge still injects in 4,099 of 43,898
warm/two-row cells, while the mass-only danger index makes 2,795 false-safe
calls. The matched `c=1` choice on the shipped `kappa=2` host is also
deliberately conservative, with reported median amplitude 0.57 of converged.

This rejection argument does not prevail under the focused short-paper bar
because the authors state the scope and negative results candidly, and the
local theorem remains useful. It decisively prevents a stronger accept and
means the paper must not be sold as a globally passive production solver.

## Individual reviewer reports

### R1 — Mathematical soundness

**5/7, confidence 4/5.** R1 independently derived Eq. 6's energy change,
verified the `W=G^{-1}` telescoping step, proved the passive-family interval by
congruence, and ran 789 exact-rational check groups. No fatal mathematical
error was found.

R1's main concerns are reach and precision: the warm/two-row failures are
substantive, the `c=1` response is over-dissipative at `kappa=2`, and the
general six-degree-of-freedom inelastic-pair interpretation should use the
rigid row-effective mass `1/w_r` rather than switching back to an unexplained
body mass `M`. R1 also requests the promised code/CSV artifact, a `c`-family
scene comparison, a state-aware fallback beyond theorem scope, and a formal
overlap disclosure for the companion submission.

The full video raises confidence that the intervention has visible
system-level consequences but does not change R1's score because the scenes
are warm and multi-contact.

### R2 — Novelty and significance

**5/7, confidence 4/5.** R2 judges the ingredients mature but their synthesis
incremental-and-real: the new part is the unilateral row-local sign test,
asymmetric reconstruction dependence, and matched
denominator-plus-correction identity. Targeted primary-source checks found no
exact novelty collision.

R2's main concerns are the cold one-row scope, unavailable companion boundary,
the absence of the promised reproducibility artifact, and the lack of a
scene-level comparison across `c=1`, intermediate `c`, `c=2`, extra
iterations, and distinct energy-safe methods. R2 also asks for a conservative
multi-row sufficient condition or diagnostic.

For R2 the paper alone is borderline; the continuous controlled two-scene
video raises the final score from 4 to 5 by resolving enough practical
significance uncertainty.

### R3 — Evaluation and reproducibility

**5/7, confidence 4/5.** R3 finds the internal baseline structure strong:
mass-only, backward-Euler-shaped, matched, converged, additional-iteration,
nonmodal, ordering, and negative out-of-scope tests. No supplied evidence
contradicts the scoped theorem.

R3's largest concern is that the manuscript promises per-cell CSVs, runnable
checks, and host excerpts that are absent from the reviewed packet. Aggregate
counts therefore cannot be independently audited. Evidence also comes from
one host and a small number of scenes/cells, with no cross-engine validation
or distinct published practical baseline.

R3 asks for the raw packet, failure-magnitude and mechanism breakdowns for the
4,099 matched warm/two-row cases, uncertainty tests for modal/reconstruction
parameters, and an equal-wall-clock accuracy/passivity comparison. R3 also
asks the authors to clarify that the video's approximately 925,575 J shelf
transient is a different time statistic from Figure 1's 1,707 J snapshot.
The video strengthens qualitative confidence but does not change the score.

### R4 — Clarity and presentation

**5/7, confidence 4/5.** R4 finds the argument logically organized and the
rendering clean, but the paper is compressed enough to make operational use
difficult. Mobility, row weight, charge, effective mass, `w`, `W`, `mu`, and
`m_eff` need a notation/units map. The generalized reconstruction-dependent
recipe should appear earlier, before readers can mistake the `kappa=1`
specialization for the shipped-host index.

Table 1's shorthand results, Figure 3's marker/index/inset density, Figure 4's
low-contrast points, and the video's small low-contrast footers are the main
visual bottlenecks. R4 recommends a compact algorithm box showing exactly
where `W` is used, larger/simpler plots, clearer table columns, and a stronger
theorem-versus-system-demo distinction.

The video raises R4 from borderline to weak accept by demonstrating a visible
and controlled consequence, but it does not repair the absent data artifact.

### R5 — Practitioner value and MIG fit

**5/7, confidence 4/5.** R5 regards the formal result and host-classification
recipe as useful and inexpensive for diagonal modal bases. The paper gives
more accuracy/cost discussion than many short papers and correctly recommends
open-loop modal excitation when persistent surface feedback is unnecessary.

R5 nevertheless finds the packet insufficient for a production adoption
decision: no absolute/end-to-end CPU or GPU timings, no active-row/modal-rank
scaling in a real workload, no scene-level `c`-family Pareto, and no deployable
fallback for warm multi-contact. Both stiffness-aware system arms eliminate
the gross modal-overrun count, so the system study supports stiffness-aware
charging more strongly than it isolates the exact matched formula's practical
advantage.

The video raises R5 from 4 to 5 by showing that the artifact is visually
consequential and that the matched arm's conservative motion is observable
rather than hidden.

### R6 — Senior generalist

**5/7, confidence 4/5.** R6's adversarial read finds that the central claim
survives within scope and is original enough for a focused MIG short paper.
The strongest reject argument is the practical-framing/guarantee gap, but it
does not defeat a clearly bounded local result.

R6 asks for a fuller derivation of Eq. 6 and the Loewner-order corollary,
decomposition of the warm/two-row failures, complete energy-ledger
definitions for isolated projection versus full substep/frame, sensitivity to
modal/reconstruction errors, end-to-end timing, and the missing artifact.
R6 also distinguishes scientific merit from packet readiness: the former is
weak-accept quality; the latter needs correction.

The video leaves R6's score at 5 but raises practical-confidence calibration
from roughly 3 to 4.

## Video adjudication

The video is decision-relevant, not decorative.

- **Shelf, approximately 0:00--0:14.** The mass-shaped arm reaches 56.8 mm
  maximum book lift versus 5.3 mm for the matched arm. The displayed
  converged reference is 9.6 mm, so the matched arm is stable-looking but
  conservative. A transient modal-energy peak near 925,575 J is shown.

- **Table, approximately 0:14--0:47.** The mass-shaped arm reaches 32.9 mm
  maximum item lift versus 7.6 mm matched, while both converged grids lie at
  11.6--11.8 mm. The table is the cleaner accuracy scene because it displays
  both the mass-arm overshoot and matched-arm undershoot.

- **Closing slate, approximately 0:47--0:50.2.** The shipped-host rule
  `w=1/(4 M_q+h^2 K_q)` is clear.

The video discloses fixed budget, independent runs, governor off,
slow-motion/repeated peak frames, offline CPU float64, and no real-time claim.
The impacted objects do not directly strike the displaced secondary objects.

Both scenes contain resting/persistent contacts before the highlighted impact;
small arm differences are already visible before the drop. They are therefore
warm, multi-row system corroboration beyond the theorem, not visual proofs of
the cold one-row identity. The video should say that more prominently and
enlarge/simplify its footer text.

## Fact-checked packet and positioning issues

### Reproducibility and administration

1. The PDF promises an anonymous supplement containing per-cell CSVs,
   runnable analytic checks, drivers, and shipped-host excerpts. The reviewed
   packet contains only the PDF and MP4, and the PDF has zero embedded files.
   If those files exist as a separately uploaded EasyChair attachment, this
   concern disappears after the packet is verified; otherwise it is the
   largest readiness defect.

2. No assigned EasyChair paper ID is visible in the PDF. The official MIG call
   requires it in the anonymous review copy.

3. The paper is otherwise visibly anonymous, all PDF fonts are embedded, and
   the video/PDF producer metadata inspected by the coordinator contains no
   author identity. The 8.1 MB video is below MIG's 200 MB supplement limit.

4. The PDF is untagged, Figure 3 is difficult at ordinary zoom, video footers
   are too small, and page 7 is almost entirely blank. These are polish and
   accessibility issues, not scientific defects.

### Companion overlap

The paper discloses that a companion submission under anonymous review shares
the host and two arms of the 24-cell experiment. The supplied packet cannot
establish that manuscript's venue or degree of overlap. This is not evidence
of a policy violation. The authors should send the chairs an exact overlap
table and ensure this paper remains self-contained if the companion is
unavailable.

### Omitted close prior work

The narrow result still appears original, but the statement that the 2026
bilateral port-Hamiltonian paper is the “closest guarantee” is too strong
without discussing two older neighbors:

- [Rath 2008, *Energy-Stable Modelling of Contacting Modal Objects with
  Piece-Wise Linear Interaction
  Force*](https://dafx.de/paper-archive/2008/papers/dafx08_27.pdf) gives
  equal-and-opposite point-mass/modal-object interaction, exact-energy contact
  phase entry, monotonically nonincreasing total energy, repeated/continuous
  contact, and a real-time implementation. It uses piecewise-linear contact
  springs and exact phase transition matrices rather than a truncated PBD row.

- [Kim et al. 2017, *Haptic Rendering and Interactive Simulation Using
  Passive Midpoint
  Integration*](https://doi.org/10.1177/0278364917731821) gives
  non-iterative discrete-passive simulation in generalized and maximal
  coordinates with unilateral multi-point Coulomb LCP contact and a flexible
  beam example. It is a whole-integrator method rather than this paper's
  pre-solve PBD row index/charge.

Neither is an exact scoop of the submitted danger threshold or
reconstruction-matched row charge. Both should be cited and distinguished to
make the positioning credible.

## Prioritized revision list

### Before submission

1. **Attach and verify the promised anonymous artifact.** Include every
   per-cell CSV, parameter range/draw, seed, runnable command, analytic check,
   shipped-host excerpt, scene configuration, and timing protocol cited by
   T1--T14.

2. **Add the assigned paper ID** to the anonymous review copy.

3. **Disclose companion overlap to the chairs.** Supply a precise table of
   shared host code, experiment arms, configurations, outputs, figures, and
   conclusions.

4. **Repair the closest-prior-work claim.** Add Rath 2008 and passive midpoint
   integration, then state the surviving distinction: a reconstruction-aware
   pre-solve sign threshold and matched denominator/correction for one
   truncated unilateral PBD row.

5. **Tighten notation and derivation.** Add a compact units/notation map,
   derive Eq. 6 and the Corollary 3.4 congruence, state the general rigid
   row-effective mass as `1/w_r`, and include a minimal old-row/new-row
   pseudocode box. Correct the likely T14a/T14b cross-reference in the
   practitioner paragraph.

6. **Clarify evidence scope and time statistics.** Label the video scenes
   explicitly as warm multi-row corroboration, and distinguish the video's
   925,575 J transient peak from Figure 1's 1,707 J shown-time value.

### Highest-value scientific additions

7. **Show the passive-family Pareto.** On the shipped row and both video
   scenes, compare at least `c={1,1.5,2}`, the backward-Euler-shaped arm,
   under-relaxation, and extra iterations at equal wall-clock work. Report
   total-energy sign/margin, impulse, rigid velocity, modal amplitude/velocity,
   object motion, and error to convergence.

8. **Explain out-of-scope failures.** Break the 4,099 matched warm/two-row
   injections down by state, row order, active-set changes, reconstruction,
   severity, and absolute/relative energy gain. Add a runtime residual,
   governor, or conservative fallback if available.

9. **Report production economics.** Give absolute and end-to-end CPU/GPU
   timings, active-row and modal-rank scaling, variable-timestep behavior, and
   the fraction of total frame cost.

10. **Broaden external validation.** A second host, frictional stack, or
    multi-support gameplay scene would materially increase confidence without
    changing the theorem.

### Presentation

11. Add one implementation/notation box; simplify Table 1's result columns;
    split or enlarge Figure 3; increase Figure 4 contrast; enlarge video
    qualification text; and compress the bibliography enough to avoid the
    nearly empty seventh page.

## Final recommendation

**Scientific merit: 5/7, weak accept, confidence 4/5.**

The paper contains a technically sound, useful, and sufficiently original
focused result for MIG's short-paper category. Its strongest contribution is
the reconstruction-aware one-row sign diagnostic and the requirement that the
matched operator be used in both the denominator and restorative correction.

**Submission readiness: do not upload the exact frozen packet unchanged.**

At minimum, verify/attach the promised artifact, add the assigned paper ID,
disclose companion overlap to the chairs, and repair the closest-prior-work
positioning. The warm/multi-row limitations and conservative `c=1` response
are scientific scope constraints that cap the score but do not overturn the
weak-accept recommendation.
