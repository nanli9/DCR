# Six independent MIG short-paper reviews — round 7

Date: 2026-07-28 (second panel of the day, on the revised packet)

Baseline for comparison: `paper/committee_review_onesweep_short_2026-07-28.md`
(round 6, unchanged, not overwritten).

## Frozen artifacts

- Paper: `paper/onesweep_short.pdf`
  - SHA-256:
    `d4716b9d0b786f2e6d5e3071da66975f3c0246fab61af6f265bc79a24a2606c8`
  - 720,541 bytes, 7 letter-size pages (612 × 792 pt), acmart sigconf,
    review mode with line numbers, `Anonymous Author(s)`
  - Body occupies pages 1–6; `References` begins in the right column of
    page 6 (y = 85.9 pt) and ends on page 7. Body is therefore 6 pages
    excluding references.
- Video: `benchmarks/paper_fig/out/onesweep_scene_video.mp4`
  - SHA-256:
    `a9ef4e4158734e98fd040f698e0007dacd595e27ed6e7611c7d91207988a7901`
  - 8,065,820 bytes, 50.20 s, 1920 × 1080, 30 fps, H.264, 1,506 frames,
    single video stream, no audio track

The video hash is byte-identical to the round-6 packet. The PDF hash is new
(round 6 was `f7fd3f83…`, 715,083 bytes, six pages), i.e. this panel read the
revision, not the baseline. Both hashes were computed by the coordinator
directly from the files at report time.

## Protocol

Six isolated AI reviewer contexts received only the frozen PDF, the frozen
MP4, and a common review brief. Each was given a distinct primary lens. They
were prohibited from reading repository planning files, manuscript source,
prior review rounds, or one another's reports. They applied the MIG 2026
short-paper bar: focused results, emerging ideas, or concise technical
contributions, judged on originality, technical quality, clarity,
significance, reproducibility, and MIG relevance.

**These are independent simulated AI reviews, not human peer reviews.**
Isolation reduces cross-contamination but does not remove correlated model
blind spots, and a simulated panel cannot substitute for a program committee.
Their agreement is evidence about the artifact, not a decision about it.

Every objection in this report that is checkable against the PDF or the MP4
was re-checked by the coordinator and is marked **CONFIRMED** or
**NOT CONFIRMED** against the artifact. Where a reviewer supplied a numeric
counterexample, the coordinator recomputed it independently; the recomputed
values are shown.

## Score distribution

| Reviewer | Primary lens | Score | Confidence | Video effect |
|---|---|---:|---:|---|
| R1 | Mathematical and technical correctness | 5/7, weak accept | 5/5 | Raised confidence only |
| R2 | Novelty and significance | 5/7, weak accept | 4/5 | Raised confidence only |
| R3 | Evaluation and reproducibility | 5/7, weak accept | 4/5 | Raised confidence only |
| R4 | Clarity and submission readiness | 5/7, weak accept | 4/5 | Raised confidence only |
| R5 | Practitioner value and MIG fit | 5/7, weak accept | 4/5 | Raised confidence only |
| R6 | Skeptical senior-PC calibration | 5/7, weak accept | 4/5 | Raised confidence only |

Mean: **5.00/7**. Median: **5/7**. Mode: **5/7** (six of six).
Mean confidence 4.17/5; R1, the correctness lens, is the single 5/5.

There is no outlier. This is the tightest distribution any panel has returned
on this paper: six identical scores, six identical recommendations, and
unanimous agreement that the video raised confidence without moving a score.

## Area-chair-style recommendation

**Weak accept (5/7), confidence 4/5, on scientific merit. Do not upload
unchanged.**

The mathematical kernel is, by the unanimous testimony of six independent
re-derivations, correct. R1 states it flatly: *"I found no incorrect equation
anywhere in the paper, which is rare."* R6, running the skeptical lens,
concurs: *"I found no algebraic error anywhere in Section 3. That is rare and
it is the paper's principal asset."* Between them the six reviewers
re-derived and machine-checked Thms. 3.1–3.3, Cor. 3.4, Prop. 3.5, Remark 1's
`κ_r` law, both relaxation boundaries, the damped per-impulse masses, the
`(1+b)²` divisor, the worst-case constant `(κ²−2)²/[4(κ²−1)]`, and the
`b* = (√37−5)/6 = 0.180` root, across something on the order of a million
random draws plus exact rational arithmetic. Nothing was found rounded in the
authors' favour.

What holds the paper at weak accept is not the theory. It is that (i) the
single most consequential empirical block in the paper has no row in the
validation table, (ii) the number that would tell a practitioner whether the
recommended weight helps in the regime the figures and video actually show is
absent although the sweep evidently exists, and (iii) the figure that carries
the paper's only shipped-host evidence is set at 1.85–4.63 pt with a printing
collision, a stray graphical artifact, and a non-printing duplicate caption in
its text layer that names the host engine.

All three are repairable without new science. Items (i) and (iii) are hours of
work. Item (ii) is one number from a sweep the paper already ran.

## What is strong

1. **A correct, independently re-derived mathematical kernel.** Six lenses,
   six from-scratch re-derivations, zero incorrect equations. R2: *"Nothing I
   checked was wrong or rounded in the authors' favour."* The `κ = 1` matched
   identity is exact, not asymptotic: R1 verified it in exact rational
   arithmetic (Python `Fractions`, 400 parameter sets, 0 mismatches on
   impulse, `v+`, `q̇+`, `q+`) and notes the paper's own reported
   `5.5 × 10⁻¹⁶` is *understated*.
2. **The `κ²` factor is a real, non-obvious, actionable finding.** On a host
   reading back `2 Δq/h`, the textbook remedy `(M_q + hD_q + h²K_q)⁻¹` is no
   longer matched and injects. R2: *"a finding a practitioner would not guess
   and could act on the same afternoon."* Four reviewers verified the failure
   condition `M(2−b) > m(1+b)²` with zero mismatches over 20,000–100,000
   draws each.
3. **Scope discipline that every reviewer independently praised.** The boxed
   *"Scope (stated once, binding for every result)"* binds all five formal
   results, and each reviewer checked that it does. R4 calls it *"exemplary
   and rare."*
4. **Prior-art concessions that survive a novelty audit.** R2, whose entire
   lens is novelty: *"Reading with a novelty lens, I could not find anything
   known being passed off as new."* The paper disowns the Delassus operator,
   the reduced-mass shock loss, the backward-Euler propagator, the
   implicit-step mobility `[1, 24]`, Gauss-Seidel order effects `[4, 7]`, and
   the modal embedding.
5. **Verified quotes and references.** R1 and R2 independently fetched
   `box2d.org/posts/2024/02/solver2d/` and confirmed *"it can lead to energy
   creation and jitter if not tuned carefully"* verbatim in the Baumgarte
   Stabilization section, and the Giles et al. Real-Time Live PDF for *"can
   inject an arbitrary amount of energy into the system due to position
   correction"* verbatim. Both 2026 arXiv references (2603.16424, 2602.08094)
   exist and are characterised accurately. R5 initially suspected `[1]` and
   `[24]` were bibliography-only and **retracted it** after finding the
   grouped citation `[1, 24]` in Section 3 — that retraction is itself
   evidence the citation audit was real.
6. **Structurally independent validation.** Closed-form toy, plain
   mass-spring chains with no modal basis anywhere, exact rational
   arithmetic, and a shipped solver. R1: the nonmodal collapse *"is the right
   control for the claim that ρ is basis-independent."* R3 reproduced the
   entire analytic half from the printed equations alone *"in about half an
   hour."*
7. **Negative results published against the authors' own interest.** The
   diagonal-charge failure, the `0.57`-of-converged amplitude cost under the
   heading *"Passive and conservative, not accurate"*, the refusal to claim
   the companion's successful arm (*"its success is evidence about stiffening
   the row, not about the one-sweep identity"*), Fig. 1's caption stating
   *"(b) is not ground truth"*, and the `4099 of 43,898` warm-cell
   disclosure. R6: *"Very few submissions argue against their own best-looking
   result."*
8. **Direct MIG fit.** XPBD `[15]` was itself a MIG paper, the target is the
   fixed local-iteration budget games actually run, and the deliverable is a
   scalar computable before the solve plus a one-line row-weight change costed
   at `0.99–1.02×` the mass-only default.

## Fact-checked issues

Every item below carries the reviewer's own quoted evidence or derivation,
plus the coordinator's independent verification against the artifact.

### 1. `T14` is cited twice in the body and has no row in Table 1; `T12` does not exist anywhere — **CONFIRMED**

Raised by **all six reviewers**, four of them as a major.

R5's evidence: *"Section 4: 'The guarantee is paid for in amplitude instead, a
median 0.57 of the converged one against 0.85 at 16 iterations (T14).'
Section 6: 'Warm states and simultaneously active rows are measured, not
proved (T14): the mass-only index calls safe a row that injects on 2795 of
43,783 warm and two-row cells, order alone flips 734 signs, and the matched
charge … still injects on 4099 of 43,898.' Table 1's rows are T1, T2, T3, T4,
T5, T6, T7, T8a, T8b, T9, T10, T11, T13."*

R6 adds the framing that makes it a defect rather than a typo: *"Section 4:
'Every closed form above was checked numerically by the suite of Table 1' …
For a paper whose credibility rests on the suite, two holes in the table, one
of them under the negative results, is a real defect."*

**Coordinator check: CONFIRMED.** `pdftotext` over the full PDF, then a
tokenised count of every `T`-label: Table 1's rows are exactly
`T1, T2, T3, T4, T5, T6, T7, T8a, T8b, T9, T10, T11, T13`. `T12` occurs zero
times in the entire document. `T14` occurs exactly twice, both in body prose
(Section 4 and Section 6), never as a table row. `T13` occurs four times
(twice in the table region, twice in body).

This is the panel's only unanimous finding and its cheapest repair.

### 2. No mass-only baseline on the warm / two-row population — **CONFIRMED (as an absence)**

Raised as a **major** by R2, R3, R5 and R6.

R5, on the practitioner lens: *"The matched charge injects on 4099 of 43,898
warm and two-row cells (9.3%), and the paper never states what the mass-only
weight does on those same cells, so I cannot size the benefit in the only
regime a production engine actually lives in."*

R2 identifies precisely why the two published numbers cannot be compared:
*"'the mass-only index calls safe a row that injects on 2795 of 43,783 warm
and two-row cells' (a false-negative rate of the diagnostic) and 'the matched
charge … still injects on 4099 of 43,898' (an injection rate of the weight).
The directly comparable figure … is never given, although the sweep clearly
exists."*

R3: *"a reader cannot tell whether the matched weight reduces injection out of
scope. This matters because Fig. 1 and the video are both in that regime."*

**Coordinator check: CONFIRMED.** The strings `2795`, `43,783`, `4099`,
`43,898` and `734` each occur exactly once in the PDF, all inside the single
Limitations sentence quoted above. No mass-only *injection* count on the warm
population appears anywhere in the paper. The two denominators (`43,783` vs
`43,898`) do differ, with no explanation given — R3, R4 and R6 each flag the
discrepancy independently.

### 3. Corollary 3.4's "if and only if" is false as literally stated — **CONFIRMED**

Raised as a defect by R1 (major) and R4 (minor); marked *verified* by R2, R3,
R5 and R6. See §B.1 for why that is not a real contradiction.

R1's evidence: *"Cor. 3.4: 'one sweep is passive at every row direction if and
only if 0 ≤ W ≤ 2G⁻¹ in the Loewner order.' The bracket of (6) on the ray is
`c(c−2)a − w_r − 2α̃`, so outside [0,2] injection requires
`a > (w_r + 2α̃)/[c(c−2)]` — which is a statement about the row's scale.
Physical counterexample at unit row norm: M = 0.1 kg, m = 1 kg, κ = 1,
h = 1e−3, b = 0.01, |J_c| = 1, W = 3G⁻¹ … ΔE = −2.089e−2 J < 0, passive;
injection only begins at c > 4.33."*

R4's independent counterexample: *"c = 2.5 (well outside the interval),
w_r = 1, a = J^T G⁻¹ J = 0.2, one sweep gives ΔE = −0.333 E⁻, passive."*

**Coordinator check: CONFIRMED, and both counterexamples reproduce exactly.**
Substituting into the paper's own Eq. (8):

- R4's cell: `c = 2.5, a = 0.2, w_r = 1, α̃ = 0` → bracket
  `= 2.5(0.5)(0.2) − 1 = −0.75 < 0`, `D = 1.5`, `ΔE/E⁻ = −0.333333`.
- R1's cell: `G = m(1+b) = 1.01`, `a = 1/1.01`, `w_r = 10`. Recomputed
  `ΔE/E⁻` at `c = 1, 2, 3, 4.3` is `−0.9099, −0.6967, −0.4179, −0.0102`; the
  first injecting value is `c = 4.34` at `+0.0027`. Injection onset
  `c* = 1 + √(1 + w_r/a) = 4.331666`, matching R1's *"c > 4.33"* to four
  figures. At `v = −1 m/s`, `E⁻ = 0.05 J` and `ΔE = −0.0209 J`, i.e. R1's
  `−2.089e−2 J` exactly.

The paper states the correct condition itself one sentence later in Eq. (8).
The sufficiency direction is correct and was proved four separate ways by the
panel (congruence with `S = G^{1/2}`, `P² ≼ 2P ⟺ λ_max(P) ≤ 2`). Only the
necessity direction needs the quantifier to range over row *magnitude*.

R1 additionally observes that the paper's own validating sentence — *"Of 2500
randomized symmetric charges each met with an adversarial row direction, all
1222 inside the interval are passive and all 1278 outside inject"* — must in
fact be scaling the row adversarially, not only rotating it. **Coordinator
check: CONFIRMED** that the sentence says *"adversarial row direction"*; the
underlying harness was not inspected (report-only mandate).

### 4. The compliance term in the danger index omits the row's own stored energy — **CONFIRMED**

Raised by R6 (marked *refuted* on the fact-check), R3 and R4 (minor), and
noted from a different angle by R1.

R6's evidence: *"Eq. (2) defines E as the bodies' Hamiltonian only … and
Thm. 3.2 states 'A compliance α̃ shifts it to ρ = L/(w_m + 2α̃)'. But with
Eq. (1)'s conventions the constraint stiffness is `1/(α̃h²)`, so the row
stores `½ α̃ λ²/h² = α̃ v²/(2W²)` … Adding it … gives `(v²/2W²)[L − w_m − α̃]`,
i.e. boundary `L/(w_m + α̃)`. I tested this on 20,000 random draws against
total energy including the constraint spring: the paper's rule mis-signs 332
cells, all of them false negatives."*

R3 derives the same result independently: *"after the sweep `C+ = α̃ h v / D`,
leaving `U+ = α̃ v²/(2D²) > 0` … Over 3e5 log-uniform draws, 779 cells (3.6%
of the paper-injecting set) change verdict."*

R4 confirms the factor and locates the danger: *"In the band
`w_m + α̃ < L < w_m + 2α̃` the paper's index reports ρ ≤ 1 while total energy
including the compliance rises, i.e. a false negative, which is the direction
the paper itself flags as dangerous."*

**Coordinator check: CONFIRMED.** From Eq. (1) as printed
(`Δλ = (−C − α̃λ)/(w + α̃)`, `α̃ = α/h²`), a cold solve gives
`λ+ = −C̃/(w+α̃)` and `C+ = −α̃λ+`, hence `U+ = C+²/(2α̃h²) = α̃v²/(2D²)`.
Adding `U+` to the paper's `ΔE` converts `−2α̃` to `−α̃`. Over 200,000
log-uniform draws in `(M, m, b, α̃)`: the paper's rule `L > w_m + 2α̃`
mis-signs total energy on **2,159 cells, all 2,159 false negatives**
(predicted passive, total energy rose); the rule `L > w_m + α̃` mis-signs
**0**. R6's 332/20,000 and R3's 779 are the same phenomenon at different
sampling densities.

Scope of the consequence, which the panel is careful about: every `α̃ = 0`
result is untouched, and every shipped measurement in the paper is hard
contact, so **no reported number changes**. What changes is the threshold the
paper hands a practitioner for a *soft* row, and it is permissive in the
unsafe direction. R1 checked the companion case and found the matched charge
robust: *"including it preserves the sign (the total change is
`−(v²/2D²)(w_r + a + α̃) < 0`)"*. Both are correct about different objects.

The paper nowhere labels Eq. (2) as bodies-only. `E` is called *"the true
Hamiltonian"*, and the only accounting disclaimer present concerns damping
(*"E is the undamped Hamiltonian: the damper acts in the predictor"*), not
compliance. **Coordinator check: CONFIRMED** by full-text search.

### 5. Figure 3's middle-panel annotation states a sufficient condition as necessary — **CONFIRMED**

Raised by R1, R3, R4 (with a numeric counterexample) and R6.

R4's evidence: *"'only where' asserts necessity. Counterexample from the
paper's own criterion in Remark 1: at m = M, b = 5, κ = 2 with the
backward-Euler weight m(1+b), we have `2Σa_i = 2/m = 2 > w_r = 1/M = 1`, so
the annotation predicts injection; but `M(2−b) = −3` is not `> m(1+b)² = 36`,
so the row is passive, and a direct sweep gives ΔE = −0.796 E⁻."*

R1 supplies the exact form: *"the exact condition … is
`w_r ≥ W(2−b)/(1+b)`. Since `(2−b)/(1+b) < 2` for every b > 0, the legend's
`2W ≤ w_r` is strictly sufficient and never necessary; the two coincide only
in the `b → 0` limit."*

**Coordinator check: CONFIRMED.** The in-figure string is
`(passive only where 2(w_row − w_r) ≤ w_r)`, present in the rendered artwork
at 3.35 pt. Recomputing R4's cell through Eq. (6): `G = m(κ²+b) = 9`,
`μ_c = m(1+b) = 6`, `u = 1/6`, `u²G = 0.25`, `2J^T u = 0.3333`, `w_r = 1` →
bracket `= −1.0833`, `D = 1.16667`, `ΔE/E⁻ = −0.795918`, i.e. R4's `−0.796`
to three figures. Sufficiency also verified algebraically: `2M ≤ m` implies
`m(1+b)² ≥ 2M(1+b)² ≥ 2M ≥ M(2−b)` for all `b ≥ 0`.

Separately, R4 and R6 note the symbol `w_row` used in this annotation and in
the `ρ_mid` axis label appears **nowhere in the body text**, which writes the
same quantity as `w_m = w_r + Σa_i`; and the paper defines an unrelated
`m_row = 1/(J_c^T G⁻¹ J_c)` in Thm. 3.3. **Coordinator check: CONFIRMED** —
`w_row` occurs zero times in the body text layer, only inside Figure 3.

### 6. `ρ_matched` is reported as a result but never defined — **CONFIRMED**

Raised by R1 and R3.

R3's evidence: *"Fig. 3 right-panel readout: 'ρ_matched < 1 all cells
(max 0.32)', and the body says of the matched weight 'is passive on every
cell, its danger index below one throughout'. ρ_matched appears nowhere in the
text. With W = G⁻¹ the Thm 3.3 injection ratio is `a/(w_r + 2a + 2α̃)` …
strictly less than 1/2 for every parameter value"* — i.e. under the natural
definition the reported result is implied by the theorem rather than evidence
for it.

R1 adds that the same panel labels its x-axis with a *different* quantity
(`ρ = L/(w_m + 2α̃)`), so two distinct objects are both called a danger index
in one panel, and proposes a single `κ`-general index
`ρ_κ = [L + (κ²−2)Σa_i]/(w_r + 2α̃)` that reproduces `ρ` at `κ = 1` and
`ρ_mid` at `κ = 2`.

**Coordinator check: CONFIRMED.** The string `rho_matched` occurs exactly once
in the PDF, inside Figure 3's non-printing text layer (see item 8). It is
never defined in the body. `ρ_mid` *is* defined, but only inline in Section 4
(`ρ_mid = (L + 2Σ_i a_i)/(w_r + 2α̃)`), not as a numbered definition.

### 7. Figure 3 is set at 1.85–4.63 pt and its inset collides with the readout box — **CONFIRMED**

R4's major, with measurements: *"panel titles 4.63 pt, axis labels 4.19 pt,
tick labels 4.41 pt, and the readout boxes that carry the results … at
3.35 pt. The inset legend is 2.65 pt and its y-tick '0' is 1.85 pt. Body text
is 9.08 pt … Rendering the middle panel at true 300 dpi print resolution shows
the inset's x-tick labels 2 and 4 printing directly through 'shelf 2/9' and
'ledge 4/9' in the readout box, and the inset's axis label 'iterations'
running into the box's lower-right corner. There is also an unexplained red
rectangle drawn around the inset's y-tick label '2'."*

R6 independently reports the same collision at 420 dpi.

**Coordinator check: CONFIRMED on all counts.** PyMuPDF span-level font sizes
inside the Figure 3 bounding box on page 5, exactly reproducing R4's numbers:
`1.85, 2.32, 2.35, 2.47, 2.65, 2.87, 2.93, 3.09, 3.31, 3.35, 3.53, 4.19,
4.41, 4.63` pt. Body text on the same page measures 8.97–9.08 pt, and the
acmart **line numbers** measure 5.98 pt — the panel readouts that carry the
paper's shipped-host counts are set smaller than the line numbers. A 300 dpi
render of the middle panel confirms visually that the inset's `2` and `4`
x-tick labels print over `shelf 2/9, ledge 4/9`, that `iterations` overruns
the readout box, and that **a red rectangle is drawn around the inset's `2`
y-tick label** with nothing in the caption or body accounting for it.

### 8. Figure 3's artwork carries a non-printing duplicate caption that names the host as "XPBD" — **CONFIRMED**

R4's evidence: *"pdftotext on p.5 returns 'Shipped XPBD support row: each
reconstruction against its validated boundary, and the reconstruction-matched
fix' and a full second caption … positioned at y = 65–75 (over the running
head) and y = 241–266 (over the real caption). Rendering those bands at
700–900 dpi shows nothing there, so the text is white or otherwise
non-printing … It would become visible in any colour-inverting or dark-mode
viewer, and it identifies the host as 'XPBD' where the body says only 'a
production position-based support solver'."*

**Coordinator check: CONFIRMED.** `pdftotext -bbox` on page 5 places
`Shipped XPBD support row: …` at y = 65.0 and a second caption
(`Left: the backward-Euler control flips sign at the row danger index rho = 1
…` / `Middle: the shipped symplectic default reconstructs qdot+ = 2 dq/h …` /
`Right: … (27/27; rho_matched < 1) …`) interleaved at y = 243–264. A 300 dpi
render of both bands shows only the running head and the single real LaTeX
caption. The string `XPBD` occurs twice in the PDF: once here, once in
reference `[15]`'s legitimate title.

Two consequences, both worth stating plainly:
- The hidden strings are the **only** place `ρ_matched` is written down
  (item 6) and they contain the stale sentence *"BE-weight remedy, matched to
  backward Euler, now injects (passive dinner 9/9, shelf 2/9, ledge 4/9)"* —
  text that duplicates and partly contradicts the printed caption.
- Naming the host `XPBD` in an extractable layer of an anonymous submission is
  a de-anonymisation-adjacent leak of exactly the kind flagged in an earlier
  round of this paper. It is not visible to a human reader, which is why it
  survived.

### 9. Figure 4's legend occludes data in the transition band, and Fig. 4 is cited before Fig. 3 — **CONFIRMED**

R4: *"In Fig. 4 the legend box sits over the upper-left quadrant, and
rendering at 450 dpi shows ghost markers for ρ between roughly 1 and 5 … behind
the legend text 'iii: wide row (plank on 2 nodes)' and 'iv: nonuniform chain
N=8'. That is the transition band immediately above the boundary the caption is
about."*

**Coordinator check: CONFIRMED.** A 400 dpi render of Figure 4 shows faint
marker ghosts on the `y = ρ − 1` branch behind the legend box, in the decade
immediately above `ρ = 1`. On the ordering point: in Section 4's reading order
*"Nonmodal collapse (Fig. 4)"* does precede *"Shipped contact row (Fig. 3)"*.
The nuance R4 did not mention is that Table 1's caption cites Fig. 3 earlier
still (*"T4's pair uses a backward-Euler control, the host default being
Fig. 3"*), so the first citation of Fig. 3 does precede Fig. 4 — the
out-of-order pair is confined to Section 4's prose.

### 10. The abstract drops Thm. 3.3's `κ_r = 1` hypothesis — **CONFIRMED**

R1's evidence: *"Abstract: 'makes one sweep passive for any κ ≠ 0 and any
number of coupled coordinates.' Thm. 3.3 assumes 'the restorative velocity be
reconstructed as q̇+ = κΔq/h and the rigid one as Δz/h', i.e. κ_r = 1.
Remark 1 gives the correct qualified statement … which I verified: with the
matched charge and κ_r = κ, injection occurred on 13,860/20,000 draws at
κ = 3 with gains up to 3.000 × E⁻ … and on 9,021/20,000 at κ = 0.25."*

**Coordinator check: CONFIRMED.** The abstract reads
*"makes one sweep passive for any κ ≠ 0 and any number of coupled
coordinates"* with no `κ_r` qualifier. Remark 1 in the body is fully correct
and explicit: *"The matched charge is passive for every κ ≠ 0 at the κ_r = 1
of Thm. 3.3, and under κ_r = κ at every mass ratio if and only if
κ ∈ [1/2, 2]."* R3, R5 and R6 independently verified the `[1/2, 2]` interval
numerically (R5 found injections at `κ = 0.30, 0.45, 2.05, 2.50, 3.0` and
zero on `[0.5, 2.0]`). The body is right; the abstract is unqualified.

### 11. The symbol `D` carries three unrelated meanings; `J` and "per-impulse mass" are never defined — **CONFIRMED**

R2: *"Eq. (6) and Eq. (8): 'D = w_r + J_c^T u + α̃' (the row denominator).
Prop. 3.5: 'deposit modal energies D_A, D_B'. Sec. 4: 'Under the weight
(M_q + hD_q + h²K_q)⁻¹' (a damping matrix)."*

R4: *"J appears in Eq. (1) … and in Eq. (5) … but is never defined … 'Per-impulse
mass' is used to distinguish a key quantity … without ever being defined."*

**Coordinator check: CONFIRMED.** All three uses of `D` are present as quoted.
The word `Jacobian` occurs **zero** times in the PDF; `J` is used in Eqs. (1)
and (5) with only `w_r` and `j_a` defined in Section 2. `per-impulse` occurs
once, in the sentence that relies on the term, with no definition. The scalar
charge `μ_c` is likewise introduced mid-sentence (*"for a scalar charge μ_c"*)
leaving `W = 1/μ_c` to be inferred.

### 12. The middle panel of Fig. 3 is nearly one-sided — **CONFIRMED in substance**

R3: *"Rendering page 5 at 900 dpi and zooming on the region below ΔE = 0 and
left of the ρ_mid = 1 dashed line, I count three filled (mass-arm) markers,
all green triangles, i.e. all from the dinner scene; the other 24 mass-arm
cells lie above zero at ρ_mid > 1. The left (backward-Euler control) panel is
properly two-sided … The text does not say that the discriminating side of the
ρ_mid test is three cells from one scene."*

**Coordinator check: CONFIRMED in substance, with a count caveat.** At 300 dpi
I count three to four filled green (dinner) triangles on the passive side of
`ρ_mid = 1`, and **no** blue (shelf) or red (ledge) filled marker there; the
injecting side carries filled markers of all three colours. R3's structural
point — that the `27/27` headline for `ρ_mid` is scored against a passive side
populated by one scene and a handful of cells, while the `22/27` control panel
is genuinely two-sided — holds. I could not resolve 3 vs 4 at print
resolution.

### 13. No wall-clock cost anywhere, and the coupled-case cost is over-charged — **CONFIRMED**

R5: *"Section 3: 'coupled, it needs one Cholesky of G per substep and 2r²
flops per row against 2r, 6.8 to 14.5 times the diagonal accumulation for
r = 4 to 64, ratios on a reference implementation rather than production
timings.' The string 'real-time' does not occur anywhere in the paper."*
And separately: *"G = κ²M_c + h²K_c depends only on the basis, κ and h, so for
a fixed substep it is a constant that can be factored once at load time rather
than once per substep … the honest per-substep cost is the 2r² solve alone."*

**Coordinator check: CONFIRMED.** `real-time` and `milliseconds` each occur
zero times in the PDF. The only cost figures are ratios (`0.99 to 1.02`,
`0.996`, `5.3 times the measured substep cost`, `6.8 to 14.5 times`). And
`G = κ²M_c + h²K_c` as defined in Thm. 3.3 contains no state-dependent term,
so at fixed `h` the per-substep Cholesky the paper charges itself is
avoidable. This is the unusual case of a reviewer finding that the paper
*understates* its own result.

### 14. No ACM submission ID in the PDF — **CONFIRMED (artifact); requirement UNVERIFIED**

R4: *"The PDF has line numbers (review mode) and 'Anonymous Author(s)'
(anonymous mode), but a text search of all seven pages returns no 'Submission
ID' string and the page-1 footer is only 'MIG '26, Charleston, SC, USA /
2026.'"*

**Coordinator check: artifact fact CONFIRMED** — `Submission`, `submission ID`
and `acmSubmissionID` each occur zero times in the PDF. Whether MIG 2026
mandates it is R4's inference from the MIG 2025 submission page; R4 states
the 2026 CFP pages fetched do not restate it. Marked UNVERIFIED as a
requirement. This is a **repeat** of a round-6 before-upload item.

### 15. Overlap with the anonymous companion cannot be audited from this packet — **CONFIRMED (as a limitation of the packet)**

R6: *"'Shared evidence is confined to two arms of the weight swap below,
labeled as such', and later 'Our explicit arm reproduces the companion's
published ratios exactly on all 24 cells, so the two grids are the same
experiment.' … Reference [3] is not available to reviewers, so I cannot assess
the overlap myself."*

R1 and R2 raise the same point independently. R2: *"a reviewer cannot confirm
from this packet alone that the theory/measurement split is as clean as
claimed."*

**Coordinator check: CONFIRMED** that both sentences appear as quoted and that
`[3]` is *"Anonymous. 2026. … Companion paper, under anonymous review."* The
disclosure is candid; the audit is simply not possible from a PDF. This is a
PC-side verification item, not an author-side defect.

## Asserted but unevidenced

**None.** This is worth stating explicitly, because earlier rounds of this
paper were damaged by acting on reviewer claims that turned out false on
inspection. Every weakness in all six reports carries a quoted line, an
equation, a render, or a reproducible derivation. Two reviewers additionally
**retracted** items after checking them, which is the behaviour that makes the
rest credible:

- **R5 retracted** *"The nearest graphics prior work on folding stiffness into
  the constraint solve is left uncited"*, marking it `refuted` after finding
  the grouped citation `[1, 24]` in Section 3.
- **R2 retracted** a duplicated-Figure-3-caption defect, marking it `refuted`:
  *"Nearly flagged this. Extracted page 5 with PyMuPDF at the span level: the
  strings … are not drawn text spans … The rendered caption is single and
  clean. Not a defect."* Note that R2's retraction and R4's finding (item 8)
  are both correct: the caption does not *render*, and it does *exist in the
  content stream*. R4's extractor saw it; R2's did not.

Three items are best classified as **reporting under-specification rather
than defects**, and are recorded here so they are not actioned as bugs:

1. **The "19 of 2000" diagonal-charge rate.** R3: *"With Wishart-random K_c
   and r in {2,3,4} I got 0/2000 … the 1% rate is entirely a property of the
   unstated randomization."* R2 reproduced *16 of 2000* on an independently
   constructed adversarial family; R1 could not reproduce the count but
   confirmed the precondition (`λ_max(diag(G)^{-1/2} G diag(G)^{-1/2}) > 2` on
   11,406 of 20,000 random SPD `G`, reaching 4.33). The mechanism is
   unanimously real and requires `r ≥ 3`. Only the *rate* is unreproducible
   without the sampling spec.
2. **Table 1's Result column reports less than its Crit. column claims.** R3:
   *"T2 has Crit. '10⁻¹², sign' and Result '0 misclass.' … The abstract
   nonetheless says 'The closed forms are machine-checked to 10⁻¹² relative on
   a 58,081-cell phase map', a residual outcome that is never reported for
   that block."* Also `T5` lists 208 cells but 184 checks, `T1` 2626 cells but
   29 checks, with no stated relationship.
3. **Cor. 3.4's interval may be the classical under-relaxation bound in a
   metric.** R1: *"a preconditioned Richardson-type step is non-expansive in
   the G-metric when the preconditioner is under 2G⁻¹, the same structure as
   the ω ∈ (0,2) relaxation bound. The paper cites no such connection."* This
   is a positioning suggestion, not a defect; R1 notes it would *raise*
   confidence while correctly bounding the novelty to the `κ²` factor.

## Missing evidence and scope gaps

These do not refute any scoped theorem. They cap the score.

1. **The proved regime and the demonstrated regime barely overlap.** R6:
   *"Fig. 1 and the entire video are eight substeps per frame, five or twelve
   resting objects, friction on, warm rows from the second substep onward,
   i.e. entirely inside the 43,898 and outside the theorem."* R2 supplies the
   sharpest artifact evidence for this, from the video's own overlay (see
   Video assessment). Four reviewers ask for the same cheap editorial fix:
   put the `4099/43,898` number, or the regime caveat, in the abstract, the C1
   bullet, or Fig. 1's caption rather than only in the final paragraph.
2. **Reconstruction dependence is measured on exactly one host, which is the
   authors' own.** R6: *"kappa = 2 is measured on exactly one implementation,
   and the standard XPBD rigid-body read-back in the paper's own reference
   [18] is Δx/h, i.e. κ = 1 … The C3 recipe … is precisely the instrument
   needed to settle this, and running it once on any stock engine would cost a
   day."* R6 names this as the single change that would most move its score.
3. **No `c = 2` arm is ever run.** R5: *"c = 1 is shipped, c = 2 is proved
   passive and exactly equal to the converged step at the host's own κ = 2,
   and no scene or shipped-row arm is ever run at c = 2 … the paper recommends
   deliberately under-ringing the very effect the modes were added for, on an
   analytic headroom argument alone."* R5 also supplies the argument the paper
   is missing: `c = 1` is the centre of the Loewner interval and therefore
   tolerates a 2× misestimate of `G` in either direction, whereas `c = 2`
   tolerates none.
4. **No comparison against the host's own incumbent mitigation.** R5: every
   experiment and the video run with *"the passivity governor off"*, so a team
   that already ships a clamp gets no guidance on whether to replace it, keep
   both, or how the two interact. **Coordinator check: CONFIRMED** —
   `governor` occurs three times, all as *"passivity governor off/OFF"*.
5. **No iteration-budget comparison on the two scenes the paper actually
   shows.** R2: the video's footers report the injection vanishing at `4 × 8`
   on the table and `8 × 8` on the shelf, whereas Section 4's cost defence is
   made on the 27-cell stiffness grid. R6 asks for the same number.
6. **Friction and restitution are outside the guarantee.** R5: *"normal-only
   rows are not what an engine has"*, and asks for even a one-sentence
   expectation about a tangential row sharing the modal mobility.
7. **No proofs for four of the five formal results.** R4: *"Only Thm 3.1
   carries a proof (three lines, ending in a QED box). Thm 3.2, Thm 3.3
   (contribution C1 …), Cor 3.4 and Prop 3.5 are stated and then immediately
   discussed; there is no appendix (p.7 is references only) and the supplement
   is described as data, not proofs."* **Coordinator check: CONFIRMED** — page
   7 contains references only, and the sole supplement sentence is *"Per-cell
   parameters, index predictions and measured signs are in the attached
   anonymous supplement."* R4 notes each derivation is 4–6 lines, so the
   omission is a space decision, not a difficulty one.
8. **The shipped-host half is not independently reproducible.** R3: *"The
   analytic half is fully reproducible from the paper text alone; I
   reconstructed T2, T3, T5, T7, T8a/b, T10, T11 and T13 from the printed
   equations in about half an hour. The half that carries the practical claim
   is the half that cannot be rerun."*
9. **No pseudocode box and no single lookup table.** R5: the shipping recipe
   is distributed across Rmk. 1, Section 3, Section 4 and Section 6, and
   *"six lines of pseudocode and a four-column table (κ | read-back | index |
   matched weight) would replace all of it."* For a paper whose value
   proposition is a one-line weight change, R5 calls this *"the cheapest
   available improvement"*.

## Video assessment

**All six reviewers recorded the video's effect as "raised confidence only."**
No reviewer's score moved because of it. Every reviewer inspected it by frame
extraction rather than description.

The video is unanimously the strongest-executed piece of the packet. R4:
*"the best-executed artifact in the packet."* R5: *"an exemplary supplementary
artifact."* R3: *"a model of disclosure."*

Confirmed by the coordinator from frames at t ≈ 0.5 s and t = 44 s:

- **Disclosure is complete and on-screen.** *"1 iteration × 8 substeps per
  1/120 s frame | modal relaxation 1.0 | passivity governor OFF"*,
  *"playback 32x slow motion, one captured substep per video frame, then
  frozen 0.9 s at the energy peak (the same frame 28 times)"*, *"independent
  runs, nothing toggled mid-trajectory"*, *"offline CPU float64, no real-time
  claim"*. All CONFIRMED verbatim.
- **The controls that matter are stated.** Shelf: *"6 kg dropped 1.00 m, never
  closer than 125 mm to a book"*. Table: *"the pot never contacts any object:
  its rotated footprint stays more than 85 mm clear of every one, so every
  response is carried by the table"*, and *"table E = 1.1 GPa, the paper's own
  material, not tuned"*. All CONFIRMED.
- **The video publishes two caveats the paper does not.** (i) *"converged
  references disagree 89x: 9.6 mm at 1/960 s substeps, 0.1 mm at 1/120 s"* —
  Fig. 1's caption reports only the 9.6 mm value. (ii) Budget grading on both
  scenes: shelf *"2 × 8 still gains 151,140 J and 4 × 8 gains 856 J; the gain
  first vanishes at 8 × 8"*; table *"2 × 8 still gains 3.2 J, and at 4 × 8 the
  gain is gone entirely"*. Both CONFIRMED. Four reviewers ask for (i) in the
  Fig. 1 caption; R2 and R6 use (ii) against the paper's cost argument.
- **The table scene corroborates the theory quantitatively.** At t = 44 s the
  overlay reads mass arm `32.9 mm / 4.04 J`, matched arm `7.6 mm / 0.081 J`,
  *"converged references, both grids 11.6 to 11.8 mm"*. `7.6/11.7 = 0.65` sits
  inside the `(M+μ*)/(M+2μ*) ∈ [1/2, 1)` over-dissipation interval that
  Section 4 predicts. CONFIRMED. R3 and R5 each derived this independently.
- **The shelf scene shows the paper's regime gap in the clearest possible
  form, and it is R2's strongest evidence.** R2: *"at playback start, before
  the impactor has landed ('highest book lifted so far 0.0 mm', books'
  KE < 0.001 J), the mass-shaped arm already reads 'board-mode energy 65.2 J',
  … while the matched arm reads < 0.001 J throughout."* **Coordinator check:
  CONFIRMED** at frame 15: the impactor is visibly still airborne, both arms
  read `highest book lifted so far 0.0 mm` and `books' translational kinetic
  energy <0.001 J`, and the two board-mode readouts are `65.2 J` (mass) and
  `<0.001 J` (matched). The energy trace shows the orange curve already
  oscillating near 10² J before `t = 0`. The divergence therefore begins in
  warm resting contact, before the cold impact, in a regime no theorem in the
  paper covers.
- Peak/start energies CONFIRMED: shelf `peak 925,575 J` against
  `scene's energy at the start of the run 64.5 J`; table `peak 857 J` against
  `48.2 J`. R6 and R3 each reported one of these; both are correct, for
  different scenes.
- Fig. 1's `56.8 mm` and `5.3 mm` running maxima match the video exactly (R5,
  R6). Fig. 1's `1,707 J` is an instantaneous readout at 114 ms, not a run
  maximum (R3, R5) — R5 read `1,705 J` at the corresponding frame.

**The one video change the panel asks for** (R1): add the backward-Euler-weight
arm. As shipped the video compares only `1/M_q` against `1/(4M_q + h²K_q)`,
which demonstrates that a *stiffer* weight is safer — something the paper
itself says is *"not the matched weight here and its success is evidence about
stiffening the row, not about the one-sweep identity."* The arm that injects
on this host is the one that would make the reconstruction-dependence claim
visible.

## Submission readiness

| Item | Status |
|---|---|
| Body length | **OK.** Body ends on p. 6 left column; `References` starts p. 6 right column at y = 85.9 and ends p. 7. 6 body pages excluding references, within MIG's 4–6 rule (2025 wording; 2026 CFP does not restate it). |
| Font | **OK.** Body measures 8.97–9.08 pt, unshrunk acmart sigconf. |
| Anonymity, visible | **OK.** `Anonymous Author(s)`, review-mode line numbers, companion cited as `Anonymous. 2026 … under anonymous review`, no author name in PDF metadata. |
| Anonymity, text layer | **DEFECT.** Figure 3's non-printing layer names the host `Shipped XPBD support row` (item 8). |
| Submission ID | **ABSENT** (item 14). Repeat of a round-6 item. |
| Supplement | **Claimed, not embedded.** The PDF states *"the attached anonymous supplement"* and contains zero embedded files (`/EmbeddedFile` count 0). A `supplement_onesweep.zip` (6.7 MB, built 2026-07-28 19:30, before the PDF's 22:39 timestamp) does exist in the repository with `code/t_onesweep/run_t{1,2,3,4,5,6,7,10,13}*.py`, `run_t12_hypotheses.py`, `x1_passivity` weight-swap scripts, host excerpts, `README.md` and `SHA256SUMS`. It was **not** in the reviewed packet, so no reviewer could inspect it. Note `run_t12_hypotheses.py` exists in the supplement while `T12` appears nowhere in the paper. |
| Video size | **OK.** 8.1 MB, far under the 200 MB supplement limit. |
| Figures | **DEFECT.** Fig. 3 at 1.85–4.63 pt with a printing collision and a stray red box (item 7); Fig. 4 legend occludes data (item 9). |
| All references cited | **OK.** R4 walked `[1]`–`[26]` citation by citation and found every entry cited at least once, noting the apparent gaps were two-column extraction artifacts. |

## Movement against the 2026-07-28 (round 6) panel

Round 6: mean **5.17/7**, five weak accepts and one accept (R5, practitioner
lens, 6/7), confidence unanimously 4/5.
Round 7: mean **5.00/7**, six weak accepts, confidence 4.17/5.

**The mean moved down by 0.17 and the distribution tightened.** The single
accept became a weak accept: R5, the same lens that scored 6/7 last round,
now scores 5/7. R5's stated reasons are new, not carried over — the missing
`T14` row and the missing warm-cell baseline, both of which are properties of
text that did not exist in round 6. Confidence rose slightly (R1 moved to
5/5).

### Round-6 issue 1 — the larger passive family `W = cG⁻¹`, `0 < c ≤ 2`

**Addressed.** The revision adds **Corollary 3.4 (Passive family, C1)** with
Eq. (8) `ΔE = v²/(2D²)[c(c−2)a − w_r − 2α̃]`, states *"every c ∈ [0,2] is
passive unconditionally"*, identifies the `c = 2` endpoint as the converged
charge (*"the far endpoint c = 2 is the scalar charge G/2, which in one
coordinate at κ = 2 is m(2 + b/2): the converged amplitude that Section 4
reports out of reach is recovered exactly, and passively"*), and gives a
selection criterion in Section 6 (*"headroom to the injection threshold falls
under 1% on a fifth of the cells measured, against at least 100% at c = 1"*).

**But the fix introduced a new defect and left one round-6 request open:**

- The corollary as stated is **false in the "only if" direction** at fixed row
  magnitude (item 3), verified by two reviewers and reproduced exactly by the
  coordinator. The round-6 panel asked the authors to *"state and prove the
  passive family"*; the statement that resulted over-reaches by one quantifier.
- The round-6 panel also asked to *"add the c = 2 / converged-charge arm to the
  shipped-row and system comparisons."* **This was not done.** R5 and R6 both
  raise it again, R5 with a constructive framing the paper lacks (`c = 1` is
  the centre of the interval and tolerates a 2× misestimate of `G`; `c = 2`
  tolerates none), R6 asking instead for *"a principled interior choice — for
  instance the largest c with ρ_matched ≤ 1/2 at the row's own operating
  point."*

### Round-6 issue 2 — `T6`'s "injection" metric was a peak-modal-overrun test

**Addressed, and no current reviewer raises it.** Table 1's `T6` Crit. column
now reads `ratio`, its Result reads `8/0/0 overrun`, the caption defines
*"a cell overruns when its peak modal energy [exceeds] …"*, the abstract now
says *"takes the modal-energy overrun count from 8 of 24 to 0"*, and
Section 4 reports **both** metrics: *"The ratio is a gross-overrun test; the
total-energy sign gives 10, 1 and 0 of 24 across the three arms."*
R3 singles this out as a strength: *"it reports both weight-swap metrics and
says which is which."* CONFIRMED by coordinator against the PDF.

### Round-6 flagged items

| Round-6 item | Status in round 7 |
|---|---|
| Missing supplement | **Partly addressed, unverifiable from the packet.** A supplement now exists in the repo but was not shipped to reviewers and is not embedded in the PDF. Only R3 raises it, and only to say it is *"described only by content, not by form or completeness."* |
| Missing paper ID | **Not addressed.** R4 raises it again (item 14). |
| `h` ambiguity between frame and substep | **Addressed.** Section 4 now reads *"four iteration-substep budgets (4, 1), (8, 2), (16, 4), (32, 8), read as iterations × substeps per 1/120 s frame, so h runs from 1/120 to 1/960 s."* No current reviewer raises it. |
| `"any κ"` needing the `κ ≠ 0` condition | **Addressed textually** — the abstract now reads *"for any κ ≠ 0"*. But R1 flags the **same sentence** for a different over-reach: it drops Thm. 3.3's `κ_r = 1` hypothesis (item 10). The body's Remark 1 is fully correct. |
| `"accepting the converged amplitude"` wording | **Addressed.** The phrase occurs zero times; Section 6 now reads *"returns the converged amplitude exactly at the cost of margin."* No current reviewer raises it. |
| Enlarge or simplify Figure 3; explain the missing `T12` | **Not addressed, and both got worse.** Figure 3 is still at 1.85–4.63 pt and now has a measured printing collision, a stray red rectangle, and a non-printing duplicate caption naming the host (items 7, 8). `T12` is still absent, and `T14` is now missing too — which all six reviewers flagged (item 1). |

### Two majors that round 6 did not raise at all

Both are consequences of text the revision added:

1. **`T14` missing from Table 1** (item 1). The `T14` warm/two-row block is
   new text. Adding the honesty paragraph without adding the corresponding
   table row created the panel's only unanimous complaint.
2. **The missing mass-only baseline on the warm cells** (item 2). The
   `4099 of 43,898` disclosure is new. Publishing the fix's own failure rate
   without the baseline's failure rate on the same population is what four
   reviewers call the decisive missing number.

This is the honest summary of the round: **the revision fixed what round 6
asked for on the substance and lost 0.17 of a point to the new material it
added while fixing it.** The new complaints are cheaper to fix than the old
ones were.

## Disagreements among reviewers

Presented as found. Not averaged.

### B.1 Corollary 3.4's "if and only if": two reviewers refute it, four verify it

- **R1 (`refuted`) and R4 (`refuted`)**: the "only if" fails at fixed row
  magnitude with `w_r > 0`, with explicit physical counterexamples.
- **R2, R3, R5, R6 (`verified`)**: all four report the biconditional holding
  with zero counterexamples.

**Better evidenced: R1 and R4, decisively — and the disagreement is not about
the algebra.** Reading the four "verifying" methods shows every one of them
allowed the row *magnitude* to vary:

- R2: *"Numerically swept the ray with row-magnitude scaling."*
- R6: *"Coded with adversarial top-eigenvector rows **scaled so
  t² λ_max = 100 w_r**"* — and R6 states the necessity argument explicitly:
  *"both u'Gu and 2J_c'u scale as t² under J_c → t J_c, so a direction with
  J'(WGW−2W)J > 0 injects **once** t² J'(WGW−2W)J > w_r."* That "once" is
  precisely the missing quantifier.
- R3: searched for *"an injecting direction"* with free magnitude.
- R5: tested only sufficiency *inside* the interval (*"2000 random symmetric W
  inside the Loewner interval against 40 random row directions each"*), which
  no one disputes.

So all six reviewers agree on the mathematics. The split is over whether the
printed phrase *"passive at every row direction"* licenses unbounded scale.
The coordinator reproduced both counterexamples exactly against the paper's
own Eq. (8) (item 3). **Resolution: the sufficiency direction is correct and
unanimous; the necessity direction is true only if the quantifier includes row
magnitude, or if `w_r = α̃ = 0`. One clause fixes it, and Eq. (8) already
contains the missing threshold.**

### B.2 The compliance factor: R6 refutes Thm. 3.2's compliance clause, R1 says the result survives

- **R6 (`refuted`), with R3 and R4 concurring**: including the row's stored
  elastic energy replaces every `2α̃` with `α̃`; the paper's rule mis-signs
  total energy in the false-negative direction.
- **R1**: *"I checked that including it preserves the sign (the total change
  is `−(v²/2D²)(w_r + a + α̃) < 0`), so the result survives; one sentence
  saying this would save every careful reader the derivation."*

**Not a real contradiction — they checked different objects.** R6/R3/R4
checked Thm. 3.2's *mass-only danger index*, where the factor matters. R1
checked Eq. (7)'s *matched charge*, where the sign is robust either way. Both
are right. The coordinator's 200,000-draw check (item 4) confirms the
index-level correction: `L > w_m + 2α̃` mis-signs 2,159 cells, all false
negatives; `L > w_m + α̃` mis-signs 0. **Resolution: correct the compliance
term in Thm. 3.2 (or label Eq. (2) bodies-only), and add R1's one sentence
about Eq. (7). No shipped measurement changes — every shipped row is hard
contact.**

### B.3 Novelty ceiling: is the `κ = 1` matched charge already known?

- **R2 and R6**: at `κ = 1` the matched charge *is* the linearized
  implicit-step mobility `[1, 24]`, and *"one matched sweep equals the
  converged step"* is close to definitional for a single row. R2: *"The
  residue that is new, the κ² scaling and the exact thresholds it produces,
  is real and is the best part of the paper, but it is one factor in one
  operator, which sets a modest ceiling on significance."*
- **R1 and R5**: treat the `κ²` factor and its consequence as a genuine
  finding. R1: *"a real and non-obvious finding with a sharp consequence."*
  R5: *"a one-line change that buys convergence, not just a bound."*

**Neither side is refuted by evidence; this is a significance judgment, and
both sides cite the paper's own concession.** But note what they *agree* on:
the paper already says this in Section 3 (*"we claim none of these"*). The
disagreement is entirely about whether the **abstract** conveys the narrowing.
R6's requested fix — *"the abstract should say which factor is the
contribution"* — is one clause and is not contested by anyone. **Resolution:
adopt R6's clause. It costs nothing and it converts a significance
disagreement into agreement.**

### B.4 Whether the demo/theory gap is a disclosure problem or a substantive one

- **R6 and R2 (major)**: the proved and demonstrated regimes barely overlap,
  and the paper's own out-of-scope measurement shows the fix failing at ~9%.
  R6: *"A reader who stops at the abstract and Fig. 1 will believe something
  the paper's own data contradicts."*
- **R1 and R5**: the same facts, read as adequately disclosed. R1 calls the
  paper's refusal to claim the companion's arm *"unusually disciplined"*; R5
  lists the honest scoping among the strengths.

**Better evidenced on the factual core: R2, whose evidence is the video's own
overlay** (65.2 J of board-mode energy in the mass arm before the impactor
lands, coordinator-CONFIRMED). Nobody disputes the facts. What they dispute is
whether burying `4099/43,898` in the final paragraph is honest-enough
placement. R6's proposed remedy is explicitly editorial and cheap: *"put
4099/43,898 in the abstract or in the C1 bullet, not in the last paragraph."*
**Resolution: the fact is confirmed; the remedy the panel converges on is a
placement change, not an experiment.**

### B.5 The iteration-budget baseline: strength or weakness?

- **R5** lists the budget comparison among the strengths: *"One sweep of the
  right weight beats 16 iterations of the wrong one at 1/5 the cost"*, calling
  it *"the argument that would win an internal engineering review."*
- **R2** treats the same argument as a weakness: the video's own footers show
  the injection removed outright at `4 × 8` on the table and `8 × 8` on the
  shelf, *"i.e. on both scenes you show"*, whereas Section 4's cost defence is
  made on the 27-cell stiffness grid.

**Both cite real, coordinator-confirmed numbers, and both are right about
their own population.** The matched weight does beat 16 iterations on the
27-cell grid at 1/5 the cost; a 4× or 8× budget does remove the effect on the
two demo scenes. **Resolution: the paper's cost claim is true where it was
measured and untested where it is shown. R6 asks for exactly the missing
number — "the smallest budget at which the stiffness-blind weight is
acceptable on each of your three scenes, and how the cost of that budget
compares with the 0.996× of the matched weight."**

### B.6 The `19 of 2000` diagonal-charge rate: reproduced, or not?

- **R2**: reproduced *16 of 2000* on an independently constructed adversarial
  family (`r = 3..6`, unit-diagonal correlated `h²K_c`), with full `G⁻¹` at
  `0 of 2000`.
- **R3**: *0 of 2000* with Wishart sampling, and marks it *"the one claim in
  Section 3 I could not reproduce."*
- **R1**: could not reproduce the injection count either, but confirmed the
  precondition on 11,406 of 20,000 random SPD `G`.

**Better evidenced: R2's positive reproduction plus R3's mechanism analysis
together.** The three results are consistent: the effect requires
`λ_max(diag(G)^{-1/2} G diag(G)^{-1/2}) > 2`, impossible at `r = 2` and
reachable at `r ≥ 3` with strong alignment, so the 1% rate is a property of
the sampling. **Resolution: the claim is true and the mechanism is real; the
reporting needs the randomization spec. Not a defect to fix, a sentence to
add.**

### B.7 One reviewer's near-miss, kept for the record

R2 nearly reported the duplicated Figure 3 caption as a rendering defect and
correctly retracted after span-level extraction showed the rendered caption is
*"single and clean."* R4 reported the same strings as a *content-stream*
defect, which the coordinator confirmed. **Both are right.** This is a useful
warning for the authors: the defect is invisible to a normal reader and to at
least one common extraction path, which is why it survived to this round.

## Individual reviewer précis

### R1 — Mathematical and technical correctness — 5/7, confidence 5/5

The only 5/5 confidence on the panel, earned: R1 re-derived every closed form
from scratch and machine-checked them (Eq. (6) to `6.1e-12` over 4,000
multi-coordinate draws; Thm. 3.1's boundary 0/200,000 sign mismatches;
Prop. 3.5's `(1+b)²` to `5.9e-13` and 0/100,000 injection mismatches), and
verified the `κ = 1` converged identity in exact rational arithmetic with zero
mismatches on all four quantities. Its verdict: *"I found no incorrect
equation anywhere in the paper, which is rare."* Its one refutation is
Cor. 3.4's necessity direction (item 3). Its remaining asks are the
`κ_r = 1` qualifier in the abstract, one `κ`-general index in place of three,
`T12`/`T14`, the Fig. 3 annotation, and — the panel's only video request — a
backward-Euler-weight arm in the video.

### R2 — Novelty and significance — 5/7, confidence 4/5

The most demanding novelty audit and it came back clean: *"I could not find
anything known being passed off as new."* R2 verified both verbatim quotes
against the live sources and both 2026 arXiv references. Its three majors are
the proved/demonstrated regime gap (with the strongest single piece of
artifact evidence on the panel — the pre-impact 65.2 J overlay), the missing
warm-cell control, and a novelty ceiling: the load-bearing new content is the
`κ²` factor, since the `κ = 1` matched charge is the known implicit-step
mobility. R2 asks that the abstract say which factor is the contribution.

### R3 — Evaluation and reproducibility — 5/7, confidence 4/5

Checked the claims by direct simulation rather than by re-deriving the
algebra, over `3e5` draws spanning four-plus decades, and reproduced the
entire analytic suite from the printed equations in half an hour. Its three
majors: `T14` absent from Table 1 with two unexplained denominators; the
missing warm-cell baseline; and the observation nobody else made — the middle
panel of Fig. 3 is nearly one-sided, with the discriminating (passive) side of
the `ρ_mid` test populated by three cells from one scene, against a properly
two-sided control panel. R3 is also the reviewer who identified that
`ρ_matched` is bounded below `1/2` a priori, so *"< 1 all cells"* restates the
theorem rather than testing it.

### R4 — Clarity and submission readiness — 5/7, confidence 4/5

The most productive lens this round. Measured every font size in Fig. 3
(1.85–4.63 pt against 9.08 pt body and 5.98 pt line numbers), found the inset
printing through the readout box, found the stray red rectangle, found the
Fig. 4 legend occlusion, found the non-printing duplicate caption naming the
host `XPBD`, and confirmed the absent submission ID — all coordinator-verified.
It also independently refuted Cor. 3.4's necessity direction and the Fig. 3
annotation with clean counterexamples, and raised the one structural question
nobody else did: four of the five formal results have no proof and no pointer
to one, in a paper with no appendix.

### R5 — Practitioner value and MIG fit — 5/7, confidence 4/5

**Moved down from round 6's 6/7 accept**, on new grounds. R5 confirms the
paper is *"genuinely a Monday change"* and that it tells you when *not* to use
it, which R5 calls rarer than it should be. Its two majors are the unauditable
`T14` and the missing warm-cell baseline: *"the one number that matters for
shipping has no baseline."* Its most useful constructive contribution is the
`c = 1` vs `c = 2` argument the paper is missing (centre-of-interval
robustness to a 2× misestimate of `G`), plus the observation that the paper
over-charges its own coupled-case cost by factoring `G` per substep when `G`
is state-independent. It also wants six lines of pseudocode and a four-column
lookup table.

### R6 — Skeptical senior-PC calibration — 5/7, confidence 4/5

Ran the assume-the-others-were-charitable brief and still found the algebra
clean, including Prop. 3.5 in exact rational arithmetic. Its two majors are
the regime gap (with the cheapest possible remedy: move `4099/43,898` out of
the last paragraph) and the observation that reconstruction dependence — the
paper's self-declared main finding — is measured on exactly one host, which is
the authors' own, while the paper's own reference `[18]` uses `κ = 1`. R6
names the single change that would most move its score: run the C3 recipe once
on any stock engine and report the read-back. It is also the reviewer who
refuted the compliance accounting against total energy.

## Bottom line

**A correct paper with a reporting problem, held at a unanimous weak accept by
three cheap defects and one missing number.**

Six independent re-derivations found zero incorrect equations. Two reviewers
retracted findings after checking them. The prior-art concessions survive a
dedicated novelty audit. The video is the best artifact in the packet and
raised every reviewer's confidence.

What the panel will not let past is that the revision's new honesty paragraph
arrived without its table row and without its control, and that the figure
carrying the only shipped-host evidence is unreadable at print size and
carries a hidden text layer naming the host. None of that is science. All of
it is fixable before upload.

The round-6 panel's two decision-relevant issues are both addressed. The
score did not rise, because fixing them added text that created two new ones.
The new ones are cheaper.
