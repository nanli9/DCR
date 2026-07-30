# MIG 2026 Short-Paper Panel Review

Date: 2026-07-29  
Review type: six isolated AI reviewer simulations plus area-chair synthesis  
Paper: `onesweep_short.pdf`  
Supplement: `onesweep_scene_video.mp4`

## Artifact lock

- PDF SHA-256:
  `d4716b9d0b786f2e6d5e3071da66975f3c0246fab61af6f265bc79a24a2606c8`
- Video SHA-256:
  `a9ef4e4158734e98fd040f698e0007dacd595e27ed6e7611c7d91207988a7901`
- PDF: 720,541 bytes, seven total pages, comprising six body pages and a
  references spill page.
- Video: 8,065,820 bytes, 50.2 s, 1920x1080, 30 fps H.264, 1,506 frames,
  no audio stream.

The final hash check matched the artifacts reviewed by all panel members.

## Rubric and protocol

The panel applied the current
[official MIG 2026 short-paper rubric](https://mig.siggraph.org/2026/papers.htm):
short papers may present focused results, emerging ideas, or concise technical
contributions and are reviewed for originality, technical quality, clarity,
significance, reproducibility where applicable, and MIG relevance. The
official limit is 4--6 body pages excluding references, with supplementary
material encouraged up to 200 MB.

Each reviewer received a fresh isolated context, the same artifact hashes,
rubric, and 1--7 score scale, and a distinct primary lens. Reviewers were
forbidden from reading historical workspace reviews, planning files, paper
source, benchmark source/data, or one another's reports. Every counted reviewer
inspected all PDF pages and the complete video. A stalled senior-review thread
was discarded without contributing a vote; its sealed replacement completed
the sixth review.

These are simulated AI reviews, not human peer reviews. Isolation reduces
cross-review anchoring but does not make the votes statistically independent
human outcomes.

## Panel result

| Reviewer | Primary lens | Score | Confidence |
|---|---|---:|---:|
| R1 | Mathematical soundness | 5/7, weak accept | 4/5 |
| R2 | Novelty and significance | 5/7, weak accept | 4/5 |
| R3 | Evaluation and reproducibility | 5/7, weak accept | 4/5 |
| R4 | Clarity and presentation | 5/7, weak accept | 4/5 |
| R5 | Practitioner value and MIG fit | 5/7, weak accept | 4/5 |
| R6 | Senior generalist calibration | 5/7, weak accept | 3/5 |

Distribution: `5, 5, 5, 5, 5, 5`  
Mean, median, and mode: `5`  
Area-chair recommendation: **5/7, weak accept**  
Area-chair confidence: **4/5**

No reviewer found a theorem-invalidating error in the headline hard-contact
result. The exact packet should nevertheless not be uploaded unchanged because
it has reproducibility, scope-wording, theorem-precision, and administrative
defects that are straightforward to repair before submission.

## What the panel believes the paper establishes

For one cold-start, restitution-free, normal-only unilateral row and one
Gauss--Seidel sweep, the paper gives a reconstruction-dependent energy sign
boundary. With restorative velocity reconstruction
`qdot+ = kappa Delta q / h`, the scalar mass-only sweep injects exactly beyond
`kappa^2 + (omega h)^2 = 2 + m/M`. The block charge associated with
`G = kappa^2 M_c + h^2 K_c`, used consistently in both the row denominator and
the restorative correction, yields the matched one-sweep loss identity. The
new Corollary 3.4 correctly exposes the passive family on the
`W = c G^{-1}` ray for `0 <= c <= 2`, including the accuracy-versus-margin
tradeoff between the interior `c=1` choice and the endpoint `c=2`.

The reconstruction dependence is the strongest contribution. A
backward-Euler-shaped row can be unsafe on the shipped `kappa=2` reconstruction,
and the paper supplies a pre-solve diagnostic and a matched alternative. The
panel regards this as a credible, focused, moderately original MIG short-paper
contribution. It is not a theorem for a complete contact solver.

## Consensus strengths

1. **Technically sound narrow core.** R1 independently recovered the scalar
   sign boundary, Eq. 6 cancellation, Corollary 3.4 interval, and ordering
   divisor. The other five reviewers found no contradictory algebra.

2. **Good claim discipline.** The paper does not claim discovery of
   finite-iteration energy injection, two-way modal coupling, or reduced
   coordinates in a position-based host. It isolates the new claim to the
   reconstruction-aware sign test and row charge.

3. **Unusually broad validation for six body pages.** The phase map, nonmodal
   collapse, exact-rational operator checks, reconstruction mismatch,
   ordering test, 27-cell shipped-row test, and cost/amplitude comparisons
   probe distinct parts of the analysis.

4. **Passivity is not conflated with accuracy.** The paper now states that the
   shipped `kappa=2`, `c=1` arm is conservative and reports a median amplitude
   of 0.57 of converged, compared with 0.85 after 16 iterations. It also derives
   the `c=2` endpoint rather than hiding the tradeoff.

5. **Useful implementation economics.** For a diagonal modal block, the
   matched row is reported at 0.996 of the mass-only row's measured cost. The
   paper also explains when coupled stiffness requires a denser operator.

6. **Strong short-paper and MIG fit.** This is a compact solver diagnostic and
   remedy for a visually meaningful interactive-simulation failure. The video
   makes the effect immediately legible.

## Decision-relevant weaknesses

### 1. The guarantee is local, not a production-solver safety result

The proof excludes warm states, simultaneous rows, friction, restitution, and
all intermediate iteration counts `1 < n < infinity`. This limitation is
empirically consequential: page 6 reports that the mass-only index has 2,795
false-safe cases among 43,783 warm/two-row samples and that the matched charge
still injects on 4,099 of 43,898 samples, approximately 9.3%.

That does not refute the cold one-row theorem. It means the paper should be
read as a row-local diagnostic/remedy and warning about reconstruction
dependence, not as a globally passive fixed-budget contact solver.

The manuscript's blanket wording is internally inconsistent: the abstract and
pages 2 and 6 say that “every statement” or “every result” is confined to the
cold one-row scope, while Section 4 reports multi-iteration and warm/two-row
measurements. Replace those phrases with “every theorem/guarantee.”

### 2. The promised reproducibility artifact is missing from this packet

Page 4 says per-cell parameters, predicted/measured signs, and related evidence
are in an attached anonymous supplement. The reviewed PDF has zero embedded
files, and the only supplied supplement is the MP4. The aggregate claims
therefore cannot be independently audited from this packet.

Table 1 also ends at T13, while pages 5 and 6 cite T14 for
converged-amplitude/cost results and warm/two-row/resting-contact results. Add
and define the missing T14 row or rows, repair the T12/T14 numbering, and
include all parameter ranges, seeds, row matrices, signs, and host settings in
the anonymous data supplement.

### 3. Two theorem statements need precision

- Corollary 3.4 should explicitly assume that the charge/mobility operator
  `W` is symmetric positive semidefinite and clarify the quantification behind
  “every row direction.” The matched interior point remains valid, but the
  stated necessity requires an admissible operator and an unrestricted
  coupling/row class.
- Equation 2's ledger contains rigid/modal kinetic energy and modal elastic
  energy, while Eqs. 6--8 also discuss positive contact compliance. If
  `alpha > 0` represents physical constraint compliance, define and include its
  stored energy; otherwise state that `alpha` is numerical regularization and
  that “passive” refers only to the displayed ledger. The headline hard-contact
  `alpha=0` result is unaffected.

The implementation must also say explicitly that the matched operator is used
in both the denominator and the actual restorative correction. Changing only a
denominator scalar is not the proved method.

### 4. The practical choice needs a direct `c`-family comparison

The submitted `c=1` setting has strong passivity margin but is deliberately
over-dissipative on the `kappa=2` host. The new `c=2` endpoint recovers the
scalar converged amplitude but approaches the passivity boundary. A compact
production-row sweep over at least `c={1, 1.5, 2}` should report:

- true total-energy sign and margin;
- amplitude/trajectory error against converged;
- impulse/contact error;
- equal-cost comparison with more iterations or substeps.

This is the highest-value scientific addition because the paper already
contains the governing family.

### 5. Companion-paper overlap and self-containment

The paper openly states that two weight-swap arms are shared with an anonymous
companion submission under review. The supplied packet cannot establish the
companion's venue or degree of overlap, so the panel does not infer a policy
violation. Before submission, disclose both manuscripts and the exact shared
evidence to the MIG chairs and ensure this paper remains independently
reviewable if the companion is unavailable.

## Video adjudication

The video materially improves significance and comprehension but does not
change the theorem's scope.

- **Shelf, approximately 0:00--0:14.23.** The mass-shaped run reaches 56.8 mm
  maximum book lift, versus 5.3 mm for the matched run. The displayed
  converged reference is 9.6 mm, so the matched arm is controlled but
  conservative. At the displayed video start, the mass-shaped trajectory
  already carries 65.2 J of board-mode energy while the matched trajectory is
  below 0.001 J. The footer discloses independent runs and no mid-trajectory
  toggle; this is a whole-run weight comparison, not an identical-state
  isolated-impact ablation.

- **Table, approximately 0:14.23--0:46.80.** A 5 kg pot lands on the bare
  center and remains more than 85 mm from other objects, making the secondary
  response deformation-mediated. The mass-shaped arm reaches 32.9 mm maximum
  item lift, the matched arm 7.6 mm, and the two converged grids agree at
  11.6--11.8 mm. This is the cleaner accuracy scene: matched is substantially
  closer than mass-shaped but remains under-responsive.

- **Closing slate, approximately 0:46.80--0:50.20.** The implementable
  `kappa=2`, `c=1` rule is clear. The video correctly disclaims real-time
  performance, uses offline CPU float64, keeps the governor off, and labels
  independent runs.

The two scenes include persistent/resting contacts and are therefore
system-level corroboration beyond the proof, not direct tests of the theorem.
The supplement should foreground that distinction, enlarge the small footer
text, define “total scene energy,” and, if space permits, add a converged or
`c=2` comparison.

## Individual reviewer précis

### R1 — Mathematical soundness

**5/7, confidence 4/5.** Independently re-derived the scalar boundary, matched
loss identity, passive family, and ordering result. Found no hard-contact
theorem error. Requested explicit symmetric-PSD/row-direction assumptions,
clarification of compliant energy, and a direct `c=1` versus `c=2` test.

### R2 — Novelty and significance

**5/7, confidence 4/5.** Judged the reconstruction-dependent unilateral-row
threshold moderately original after checking the closest primary literature.
Praised the paper's positioning and operator result. Main reservations were the
cold one-row scope, conservative response, missing supplement/T14 definition,
terminology inversion, and incomplete common-budget comparison to practical
mitigations.

### R3 — Evaluation and reproducibility

**5/7, confidence 4/5.** Found the analytic/nonmodal/shipped-row evidence broad
for a short paper and the fixed-budget weight swap well controlled. Withheld a
firmer accept because T14 and raw per-cell evidence are absent, warm/multi-row
failures are under-presented, and the paper lacks equal-work/equal-accuracy
comparisons along the passive family.

### R4 — Clarity and presentation

**5/7, confidence 4/5.** Found the paper decipherable and candid but difficult
to operationalize quickly. Requested one implementation box, normalized
mobility/effective-mass notation, a clear theorem-versus-video distinction,
larger Figure 3/video annotations, repaired test numbering, and removal of the
nearly blank reference page.

### R5 — Practitioner value and MIG fit

**5/7, confidence 4/5.** Considered the row-level result useful and cheap for
diagonal modal bases, with a convincing failure/remedy demonstration. The main
concern is deployability: ordinary game contacts are warm and multi-row, the
video demonstrates stabilization rather than real-time deployment, and the
packet lacks end-to-end timing and equal-error baselines.

### R6 — Senior generalist

**5/7, confidence 3/5.** Found no fatal issue and judged the focused result
above the short-paper bar. The full video audit increased confidence in the
empirical effect but not the score: both scenes confirm suppression of
injection while also showing conservative matched amplitude and no extension
of the theorem.

## Prioritized revision list

### Mandatory before upload

1. Attach the promised anonymous per-cell supplement and restore/define T14.
2. Replace “every statement/result” with “every theorem/guarantee”; label the
   video scenes as beyond-theorem system corroboration.
3. State `W`'s symmetric-PSD assumptions, row-direction quantifier, and the
   exact compliance-energy ledger; say explicitly that the operator changes
   both denominator and correction.
4. Add a compact implementation box that defines mobility versus effective
   mass/charge and the general-`kappa` index.
5. Add the EasyChair-assigned paper ID before submission.
6. Disclose the companion-paper overlap to the chairs and make this paper
   independently auditable.

### Highest-value scientific strengthening

7. Add a small `c={1,1.5,2}` shipped-row accuracy/passivity/margin comparison.
8. Give T14 a failure map or breakdown and state the runtime fallback for warm
   or simultaneously active rows.
9. Report equal-cost accuracy against added iterations/substeps and, if
   available, end-to-end row or frame timing.

### Presentation polish

10. Enlarge/simplify Figure 3 and the video's footer annotations.
11. Compress the bibliography/body so two references do not occupy an almost
    empty seventh page.

## Area-chair bottom line

**Scientific merit: weak accept, 5/7, confidence 4/5.** The central hard-contact
theorem appears sound, the reconstruction dependence is useful and moderately
original, and the video makes the consequence relevant to MIG. The result is
appropriately focused for a short paper.

**Submission readiness: not ready to upload unchanged.** The missing promised
supplement/T14 definition, blanket scope wording, two theorem-precision issues,
missing paper ID, and companion-overlap disclosure should all be repaired.
These are serious for a no-rebuttal venue, but none presently refutes the
paper's narrow scientific contribution.
