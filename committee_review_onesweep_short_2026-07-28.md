# Six independent MIG short-paper reviews

Date: 2026-07-28

## Frozen artifacts

- Paper: `paper/onesweep_short.pdf`
  - SHA-256:
    `f7fd3f83ec6e095951084383a9906123ff0bcce662524e9b29fecd38d83fa45c`
  - 715,083 bytes, six letter-size pages
- Video: `benchmarks/paper_fig/out/onesweep_scene_video.mp4`
  - SHA-256:
    `a9ef4e4158734e98fd040f698e0007dacd595e27ed6e7611c7d91207988a7901`
  - 50.2 s, 1920×1080, 30 fps, H.264, 1,506 frames, no audio

The paper and video were copied to a frozen packet before review. Their hashes
were rechecked after all reports and remained unchanged.

## Protocol

Six isolated AI reviewer contexts received only the frozen PDF, MP4, and a
common review brief. They were prohibited from reading repository planning
files, historical reviews, manuscript source, or another reviewer's report.
They used the official MIG 2026 short-paper bar: focused results, emerging
ideas, or concise technical contributions, assessed for originality, technical
quality, clarity, significance, reproducibility where applicable, and MIG
relevance. Every reviewer had to read all six pages and inspect the complete
video before scoring.

These are independent simulated AI reviews, not human peer reviews. Isolation
reduces cross-contamination but does not remove correlated model blind spots.

## Score distribution

| Reviewer | Primary lens | Score | Confidence | Video effect |
|---|---|---:|---:|---|
| R1 | Mathematical and technical correctness | 5/7, weak accept | 4/5 | Raised confidence |
| R2 | Novelty and significance | 5/7, weak accept | 4/5 | Raised confidence |
| R3 | Evaluation and reproducibility | 5/7, weak accept | 4/5 | Raised confidence |
| R4 | Clarity and submission readiness | 5/7, weak accept | 4/5 | Raised confidence |
| R5 | Practitioner value and MIG fit | 6/7, accept | 4/5 | Raised confidence |
| R6 | Skeptical senior-PC calibration | 5/7, weak accept | 4/5 | Raised confidence |

Mean: **5.17/7**. Median and mode: **5/7**. Five weak accepts, one
accept, no rejects. Confidence is unanimously **4/5**.

## Area-chair-style recommendation

**Weak accept (5/7), confidence 4/5, on scientific merit.**

The focused contribution clears the MIG short-paper bar. The paper converts a
known qualitative failure—energy creation by a truncated position-level
contact solve—into an exact reconstruction-dependent sign test for one cold
unilateral row, then gives a sufficient operator weight that makes the scoped
sweep passive. The scalar boundary, row-visible form, and submitted
`W=G^{-1}` loss identity survived independent checks. No reviewer found a
counterexample under the declared cold/one-row/normal-contact assumptions.

The packet should nevertheless **not be uploaded unchanged**. Two
decision-relevant issues follow directly from the submitted equations and
validation definitions, and the promised empirical supplement plus assigned
paper ID are absent.

## What is strong

1. **Correct, focused mathematical kernel.** The exact scalar boundary
   `κ² + (ωh)² > 2 + m/M`, the row-visible danger index, and the
   reconstruction-dependent operator treatment form a coherent short-paper
   contribution.
2. **Useful reconstruction warning.** The paper shows that a
   backward-Euler-shaped weight can itself inject when used on the shipped
   `κ=2` reconstruction. That is a practical failure mode a solver developer
   could otherwise miss.
3. **Scope discipline.** The paper repeatedly limits the theorem to one cold
   sweep, one unilateral normal row, zero restitution, and no friction. It does
   not claim first observation of energy injection, first modal coupling, or
   whole-solver passivity.
4. **Broad validation design for six pages.** The packet reports an analytic
   phase map, nonmodal collapse, rational identities, a shipped-row test,
   reconstruction/relaxation checks, converged-reference analysis, and two
   system scenes.
5. **Honest passivity-versus-accuracy discussion.** The paper explicitly says
   the submitted `κ=2` remedy is conservative and can return only one-half to
   all of the converged amplitude.
6. **Strong MIG fit.** Fixed-budget position-based contact, modal response, and
   visible supported-object motion are directly relevant to physics-based
   animation and interactive simulation.

## Two fact-checked scientific/reporting issues

### 1. Equation (6) contains a larger passive family

Let

```text
G = κ² M_c + h² K_c
W = c G^{-1}
a = J_c^T G^{-1} J_c
```

Substitution into submitted Eq. (6) gives

```text
ΔE = v²/(2D²) [ c(c-2)a - w_r - 2 alpha_tilde ],
D  = w_r + ca + alpha_tilde.
```

Therefore every scalar multiple **`0 < c <= 2` is unconditionally passive**
under the same theorem assumptions; `c=1` is sufficient but not unique. The
coordinator independently checked the identity in 200,000 random positive
scalar `κ=2` cases, with a maximum normalized residual of `7.4e-16` and no
positive energy change.

This matters because the paper itself derives the undamped scalar
`κ=2` converged charge

```text
mu* = m(2 + b/2) = G/2,
```

which corresponds to **`W=2G^{-1}`**, the upper endpoint of the passive
family. On the submitted model, this appears both passive and
converged-accurate, removing the current `W=G^{-1}` arm's factor-of-two
strong-coupling amplitude loss.

This does not invalidate the paper's theorem. It does mean that the current
practitioner recommendation is unnecessarily dissipative unless an unstated
production constraint rules out `c=2`.

Required repair:

- state and prove the passive family, at least for `W=cG^{-1}`;
- explain the selection criterion for `c`;
- add the `c=2`/converged-charge arm to the shipped-row and system comparisons;
- revise “matched” terminology and guidance if `c=2` is admissible.

### 2. T6's “injection” metric is only a sufficient gross-overrun test

Table 1 defines a T6 cell as “injecting” when peak modal energy exceeds peak
impactor rigid kinetic energy. That is not equivalent to the paper's formal
condition `E+ > E-`. A ratio above one is strong evidence of injection, but a
ratio at or below one does not prove total-energy nonincrease.

Consequently, the reported change from `8/24` to `0/24` establishes removal of
gross modal overruns, not by itself system-level passivity. The abstract and
Section 4 currently use the stronger word “injecting” or “injection-free.”

Required repair:

- rename T6 to a modal-energy-overrun metric everywhere; or
- recompute all 24 cells with the same total mechanical-energy sign used by
  the theorem and report both metrics.

## Missing evidence and scope gaps

These do not refute the scoped theorem, but they cap the score.

1. The paper promises per-cell parameters, predictions, and measured signs in
   an attached anonymous supplement. The reviewed packet contains only the PDF
   and MP4, and the PDF has zero embedded files.
2. Warm modal states, simultaneous rows, friction, restitution, intermediate
   iteration counts, and secular multi-step behavior remain open. The video
   scenes are useful corroboration outside the theorem, not proof of global
   passivity.
3. No equal-cost comparison is given among the passive-family endpoints,
   additional iterations, under-relaxation, the existing passivity governor,
   and open-loop modal excitation.
4. No wall-clock cost, per-row overhead, factorization policy, or implementation
   pseudocode is given for a non-diagonal `G^{-1}`.
5. The anonymous companion submission is unavailable, so exact overlap in
   evidence and intellectual contribution cannot be audited from this packet.
6. Section 2 defines `h` as a substep, while Figure 1/video use eight substeps
   per `1/120 s` frame and the 24-cell paragraph says several
   iteration-substep budgets run “at `h=1/120`.” Because the index depends on
   `h²`, frame interval, actual substep interval, and budget-pair ordering must
   be stated unambiguously.

## Video assessment

The video is a material positive and raised every reviewer's confidence, but
changed no numerical score.

- The table scene is the strongest visual evidence. A 5 kg pot lands on the
  bare center, stays more than 85 mm from every item, and the two converged
  grids agree at 11.6–11.8 mm maximum lift. The mass-shaped arm reaches
  32.9 mm; the submitted matched arm reaches 7.6 mm. This clearly shows both
  suppression of the unsafe response and conservative under-response.
- The shelf scene makes the failure dramatic, but is not an identical-state
  isolated-impact ablation. Before the displayed falling block reaches the
  shelf, the mass-shaped arm already has about 65.2 J of board-mode energy
  while the matched arm is below 0.001 J because the resting contacts have
  evolved differently. The video discloses that these are independent runs
  with no mid-trajectory toggle.
- The shelf reference is time-grid sensitive: the displayed converged lifts
  are 9.6 mm at `1/960 s` and 0.1 mm at `1/120 s`. The paper correctly uses
  the same-grid 9.6 mm comparison, but the table should remain the principal
  accuracy scene.
- The labels clearly disclose the fixed budget, disabled governor, slow-motion
  playback, independent runs, and offline CPU float64 execution with no
  real-time claim.

## Submission readiness

The PDF is anonymous, six pages, visually clean, and has embedded fonts. The
MP4 is 8.1 MB, far below the official 200 MB supplement limit. The live
MIG 2026 call allows 4–6 body pages excluding references and requires a unique
EasyChair-assigned paper ID in the anonymous review PDF. No such ID is visible
in this frozen PDF.

Before upload:

1. add the assigned paper ID;
2. attach the promised anonymous per-cell data/scripts or remove the statement
   that they are attached;
3. fix the passive-family omission and T6 terminology;
4. distinguish actual substep `h` from frame duration;
5. replace “any `κ`” with the theorem's invertible/`κ != 0` condition;
6. change “accepting the converged amplitude” to “targeting the converged
   amplitude” or “accepting a conservative amplitude” for the submitted
   `κ=2`, `c=1` arm;
7. enlarge or simplify Figure 3 and explain the missing T12 label.

## Individual reviewer précis

### R1 — Technical correctness — 5/7

The submitted scalar and operator derivations check out under scope. R1
independently found the `0<c<=2` passive family and the apparently
exact-and-passive `c=2` midpoint endpoint. This is the panel's most important
technical revision. R1 also requests the missing artifact, full-operator cost,
compliance-energy clarification, and warm/multi-row evidence.

### R2 — Novelty and significance — 5/7

The credible novelty is the exact one-sweep sign interpretation,
reconstruction dependence, and consistent row charge—not the known dynamic
stiffness, Delassus operator, modal embedding, or injection phenomenon. This is
meaningful but moderate novelty appropriate to a focused short. R2 asks for a
formula-level closest-work comparison, auditable separation from the companion,
and a practical accuracy/passivity frontier.

### R3 — Evaluation and reproducibility — 5/7

The algebraic and nonmodal checks are persuasive, but the promised cell-level
artifact is absent. R3 identified the T6 metric mismatch: a peak modal-overrun
ratio cannot be labeled as the formal total-energy injection test. The video
raises confidence but does not replace raw traces or extend the theorem.

### R4 — Clarity and readiness — 5/7

The paper is precise and candid but highly compressed. R4 recommends a compact
map from reconstruction to index, weight, guarantee, and accuracy consequence,
plus a larger Figure 3. The missing paper ID and promised supplement are
concrete packet defects. The shelf's grid-sensitive reference belongs in the
paper if that scene remains an accuracy anchor.

### R5 — Practitioner usefulness — 6/7

The diagnostic and reconstruction check are actionable for an engine
developer, and Section 6 gives a useful decision menu. R5 gives the highest
score because the narrow guarantee is honestly stated and directly relevant to
fixed-budget game physics. The main requests are an equal-cost timing/quality
comparison, explicit integration pseudocode, artifact data, and empirical
guidance beyond cold single-row onset.

### R6 — Senior-PC calibration — 5/7

The core theorem is sound and the contribution is appropriately scoped for a
short paper. The practical remedy is held below a clean accept because its
submitted `κ=2` form is over-dissipative, the videos begin outside the exact
theorem regime, and no equal-cost stable baseline or inspectable data is
included. R6 also asks the authors to clarify the physical impulse/momentum
interpretation of replacing the modal response operator.

## Bottom line

**Strong technical core, solid weak accept, not a clear accept in the current
packet.** The best revision is not merely cosmetic: promote the passive family
already latent in Eq. (6), test the `c=2` endpoint, and repair the empirical
energy terminology. With those changes, the paper's practical story could
become both less dissipative and more compelling.
