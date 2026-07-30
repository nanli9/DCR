# Committee review — `onesweep_short` (round 8)

Panel date: 2026-07-29 · Report compiled 2026-07-30 · Coordinator: area chair (simulated)

---

## Frozen artifact lock

Both artifacts were hashed and measured by the coordinator at report time. Any
edit to either file after this point invalidates every finding below.

| Field | Paper | Video |
|---|---|---|
| Path | `/Users/nan/Desktop/DCR/paper/onesweep_short.pdf` | `/Users/nan/Desktop/DCR/benchmarks/paper_fig/out/onesweep_scene_video.mp4` |
| SHA-256 | `8a77cf7947971f3c0f56789c5c7f9dd16a4a2c1ca3fcc72328ae1e5acc9003c1` | `a9ef4e4158734e98fd040f698e0007dacd595e27ed6e7611c7d91207988a7901` |
| Bytes | 716,167 | 8,065,820 |
| Extent | **7 pages**, 612 × 792 pt (US Letter), PDF 1.7 | **50.200 s**, 1920 × 1080, 30 fps, 1,506 frames, H.264, 1.285 Mb/s |
| Body extent | Sections 1–6 fill through p. 6 left column (line 637); references occupy p. 6 right column plus a six-line stub on p. 7 → **≈ 5.5 pages excluding references** | Two acts: cantilever shelf (steel, E = 200 GPa) then dinner table (E = 1.1 GPa) |
| Produced | pdfTeX 3.141592653-2.6-1.40.29, TeX Live 2026, acmart 2025/08/27 v2.16, sigconf + review (line numbers) | — |
| Timestamp in file | `D:20260729233729-07'00'` | — |

Coordinator anonymity audit of the PDF (run directly, not taken from a reviewer):
XMP `dc:creator` = `Anonymous Author(s)`; docinfo `author` empty; 19 URI link
annotations, all of them `doi.org` (17) or `box2d.org` (2); zero white-fill text
spans. The submission is clean for double-blind on these axes.

---

## Protocol — read this before using any number below

These are **six independent simulated AI reviews**, produced by isolated model
instances given the same two artifacts and different review lenses. **They are
not human peer reviews.** They do not predict a real MIG program-committee
outcome, and no score here has standing at any venue.

Isolation reduces cross-contamination between reviewers but does not remove
correlated model blind spots: six instances of the same model family can share
a systematic error, and the striking convergence of their numerical
verification results should be read with that in mind rather than as six
independent confirmations. Reviewers were permitted to fetch external sources
and to write and run their own verification code; several report doing so,
including in exact rational arithmetic.

The coordinator independently re-checked every objection that is checkable
against the PDF or the MP4 and has marked each **CONFIRMED** or **NOT
CONFIRMED** against the artifact. Reviewer claims that rest on the authors'
unavailable production host, on an unavailable supplement, or on the reviewers'
own private code are marked **NOT INDEPENDENTLY CHECKABLE** and are reported as
reviewer testimony, not as established fact.

Claims asserted without a quotation, an equation, or a derivation are
segregated into their own section and are **not** among the findings. Prior
rounds of this paper were damaged by acting on confident reviewer claims that
proved false on inspection; that rule is load-bearing here.

---

## Score distribution

| Reviewer | Lens | Score | Confidence | Recommendation | Video effect |
|---|---|---|---|---|---|
| R1 | Mathematical and technical correctness | 5/7 | 4/5 | weak accept | raised confidence only |
| R2 | Novelty and significance | 5/7 | 4/5 | weak accept | raised confidence only |
| R3 | Evaluation and reproducibility | 5/7 | 4/5 | weak accept | raised confidence only |
| R4 | Clarity and submission readiness | 5/7 | 4/5 | weak accept | raised confidence only |
| R5 | Practitioner value and MIG fit | 5/7 | 4/5 | weak accept | **raised score** |
| R6 | Skeptical senior-PC calibration | 5/7 | 4/5 | weak accept | raised confidence only |

**Mean 5.00/7. Median 5/7. Mode 5/7 (six of six).**
Mean confidence 4.00/5 (six of six at 4).
Six weak accepts. No accept, no reject, no outlier in either direction.

This is the flattest distribution of any panel this paper has drawn. There is
no dissent to report on the score itself; the real disagreements (Section B)
are about *which* remaining problem matters and about two factual questions.

---

## Area-chair recommendation

**Weak accept, 5/7, confidence 4/5, on scientific merit.**

Six reviewers independently re-derived every closed form in the paper, several
in exact rational arithmetic, and **none found a mathematical error**. That is
the strongest correctness result this artifact has ever produced and it is not
what is holding the score down.

What holds it at 5 is uniform across all six: the certified regime (one sweep,
cold start, one row, `e = 0`, no friction) and the demonstrated regime (warm,
multi-row, persistently loaded contacts) barely overlap, and the paper's own
T14c measures the residual — the matched charge still injects on 4,099 of
43,898 warm/two-row cells. Every reviewer credits the paper with disclosing
this rather than hiding it; every reviewer also treats it as a ceiling on
significance rather than a defect.

**Do not upload without the two mechanical repairs in "Submission readiness"
below.** Both are confirmed against the artifact, both are cheap, and one of
them (Table 1's T14a/T14b counts) directly undercuts the paper's own posture
that every number is machine-checked and shipped as per-cell CSV.

---

## What is strong

Reported because all six reviewers converged on it independently, not because
the paper claims it.

**1. The mathematics is right, and it was checked, not assumed.** Six reviewers
re-derived Thm. 3.1, Thm. 3.2, Thm. 3.3 (Eqs. 6–7), Cor. 3.4 (Eq. 8 and the
Loewner interval), Prop. 3.5, Remark 1's `κ_r` reweighting, both relaxation
boundaries, the compliance shift, the `κ = 1` converged-backward-Euler
identity, the `κ = 2` implicit-midpoint charge `μ* = m(2 + b/2)`, and the damped
amplitude gap. Zero errors reported by any reviewer. R2 checked Eq. (6) and
Eq. (7) in exact `Fraction` arithmetic (0 of 3,000 mismatches; matched charge
non-passive on 0 of 3,000) and stress-tested 200,000 float draws with `M`, `m`
over twelve decades and `κ ∈ [-4, 4]`, worst `ΔE/E⁻ = -5.33e-16`. R5 did the
same with a hand-rolled rational matrix inverse over `r = 1..4`. R6 verified
the `u⊤Gu = J_c⊤G⁻¹J_c` telescope in exact rationals with a fully coupled 3×3
`K_c`.

**2. Two results that are easy to get wrong are right.** Cor. 3.4's Loewner
"iff" was independently proved by four reviewers via the same congruence
(`S = G^{1/2} W G^{1/2}` reduces `WGW ⪯ 2W` to `S² ⪯ 2S`, hence
`spec(S) ⊂ [0,2]`), with the `W ⪰ 0` half *implied* rather than assumed. R1 and
R6 both note this. Prop. 3.5's worst-case injected fraction
`(κ²-2)²/[4(κ²-1)]` is a genuine two-variable supremum: R1's brute force gives
0.041667, 0.125000, 0.333333, 0.860119 at `κ² = 2.5, 3, 4, 6.25` against the
closed form to six digits; R3's 400,000-sample search peaks at exactly
0.333333 at `κ = 2`; R6 matches at `κ = 1.6, 2.0, 2.5, 3.0`.

**3. Sharpness claims are sharp.** Remark 1's "passive under `κ_r = κ` at every
mass ratio iff `κ ∈ [1/2, 2]`" was scanned by three reviewers and flips exactly
at the endpoints. R1: 0 injections at `κ = 0.5, 0.51, 1.0, 1.99, 2.0`;
767/4000 at 0.49; 1495/4000 at 2.01. R3: 0/4000 at 0.5 and 2.0, 1094/4000 at
0.45, 2101/4000 at 2.05. R2: passive at `κ = 2.0000`, injecting at `2.0001`.

**4. Claim discipline is unusual and it survives fact-checking.** Both
motivating quotations are verbatim in their sources and correctly attributed.
Three reviewers independently fetched the AVBD SIGGRAPH 2025 Real-Time Live!
abstract and found "Unfortunately, with hard constraints, the resulting error
can inject an arbitrary amount of energy into the system due to position
correction" — and all three note the paper correctly cites the Real-Time Live!
item [10] rather than the TOG paper [9]. Three fetched `box2d.org/posts/2024/02/solver2d/`
and found "it can lead to energy creation and jitter if not tuned carefully"
in the Baumgarte Stabilization section, which the bibliography entry names.
R2 additionally extracted the Small Steps [16] PDF and confirmed its energy
discussion is about damping, never gain, supporting the paper's "targets energy
loss, not gain".

**5. The paper falsifies a wrong-reconstruction weight on a shipped host.**
R2 singles this out: Fig. 3 middle shows the backward-Euler-shaped weight
injecting on shelf 7/9 and ledge 5/9 at exactly the operating points where the
`κ=2`-matched weight is 9/9 passive. Predicting where an existing remedy
*fails* is stronger evidence than showing a new one works.

**6. Negative results are reported, not buried.** The wrong index tracks only
22 of 27 cells "and the five misses are false negatives, the unsafe direction
for a pre-solve check"; the matched arm is "Passive and conservative, not
accurate"; Fig. 1's caption volunteers that a converged run lifts a book
9.6 mm against the proposed arm's 5.3 mm, "so (b) is not ground truth".

**7. The denominator-only trap.** R5 and R6 both flag the Recipe's warning
("the denominator alone is not the proved method") as the single most valuable
implementation sentence in the paper, and both measured it. See Section B for
the one place where their measurements differ in strength.

---

## (A) Movement across three panels

Panel record from the files in `paper/`: the **2026-07-28** panel
(`committee_review_onesweep_short_2026-07-28.md`) scored **5.17** mean — five
weak accepts and one accept, R5 at 6/7. The **2026-07-29** panel
(`committee_review_onesweep_short_2026-07-29.md`) scored **5.00**, unanimous
weak accept, and set five priorities. (A separate 07-28 file, `..._r7_...`,
also records 5.00 unanimous; the 5.17 figure belongs to the non-r7 07-28 run.)

**This panel: 5.00, unanimous weak accept. The score did not move from
2026-07-29.** R5, the reviewer who supplied the single 6/7 on 07-28, is at 5/7
here — and is one of the two reviewers now arguing *against a shipped
recommendation* rather than against a gap. That is a higher-order objection,
which is movement even though the number is flat.

### P1. Attach the supplement and define T14 — **executed; new residual raised**

CONFIRMED executed. The PDF now says: *"The attached anonymous supplement ships
every check in that table with its per-cell CSV: runnable code for the analytic
arms, drivers and host excerpts for the shipped-host ones."* Table 1 now carries
**T14a, T14b, T14c** as separate rows with What/Model/Cells/Crit./Result.

**Still raised, in a new and narrower form, by five of six.** The T14 rows exist
but their counts do not reconcile with the body (findings 1 and 2 below). R3
and R6 additionally note that "host excerpts" is not a runnable host, so the
four shipped rows (T4, T6, T9, T14b) remain unverifiable by an outside group.
R3: *"The four shipped rows all depend on 'a production position-based support
solver, the host of the companion study [3]', which is anonymous."*

### P2. Restrict blanket scope wording — **executed; objection changed character**

CONFIRMED executed. Section 2 now carries *"Scope (stated once, binds every
theorem). One Gauss-Seidel sweep; cold start; restitution e = 0; hard contact
except where α̃ appears; one coupling row; normal-only, no friction."* The
abstract closes with *"Every theorem is confined to one sweep from a cold start
with e = 0 and one normal-only row."*

**Still raised by all six — but as a significance ceiling, not a wording
defect.** Every reviewer now *praises* the scoping ("Scope discipline is
exemplary for a short paper" — R4; "unusually good" — R1) and objects instead
that the certified regime and the deployed regime barely overlap. R1: *"the
title, abstract and C1 read considerably stronger than what is certified for a
shipped solver."* R6 sharpens it into a mechanism nobody raised before:
*"`κ` is only defined [at cold start]... Once `q̇ⁿ` is nonzero the sweep's
kinetic change is `2m(Δq/h)[(Δq/h) - q̇ⁿ]`, which is not the cold-start
quadratic form and can take either sign, so no fixed `κ` exists and Thm. 3.3
does not apply."* That is the sharpest form this objection has taken across
three panels and it is new.

### P3. Symmetric-PSD assumptions on W; α ledger; operator in both places — **executed, all three; and it is now cited as a strength**

CONFIRMED executed, all three parts.

- *W symmetric*: Cor. 3.4 reads *"Under the hypotheses of Theorem 3.3 with `W`
  symmetric, one sweep is passive for every row `J_c` if and only if
  `0 ⪯ W ⪯ 2G⁻¹`."* Note the PSD half is a **conclusion**, not a hypothesis, and
  four reviewers independently confirmed that is correct.
- *α ledger*: the paragraph at p. 3 now states *"a compliant row also stores
  `α̃v²/(2D²)` in its own spring, so counting that term tightens each `2α̃`
  threshold to `α̃`, a band on which the displayed ledger is permissive; no sign
  reported here changes, and the matched charge stays passive either way."*
  R2 verified this bookkeeping independently on 30,000 draws, 0 mismatches, and
  calls it *"a subtle bookkeeping point and the paper gets it right, including
  the statement that the displayed ledger is permissive on that band."*
- *Both denominator and correction*: stated four times — abstract, C1, Thm. 3.3
  (*"used in both the denominator of (1) and the position correction"*), and
  Recipe (iii) (*"the denominator alone is not the proved method"*).

**No longer raised as a gap. Both R5 and R6 now list it under strengths** and
both went and measured the half-implementation. R5: 19,624 of 30,000 injecting
for denominator-only against 18,227 for mass-only. R6: 2,021 of 3,000. Both ask
only that the paper print a number. Score consequence: this priority is closed.

### P4. Implementation recipe and a `c=1` vs `c=2` comparison — **executed; the recommendation itself is now contested**

CONFIRMED executed. Section 6 carries a five-step Recipe (i)–(v), and step (v)
compares the family points including the amplitude cost (*"`c = 1` returns 0.50
to 0.60"*) and the margin cost (*"headroom to the injection threshold falls
under 1% on a fifth of the cells measured (median 36%) against at least 100% at
`c = 1` (median 171%)"*).

**Still raised, inverted, by R5 and R6 — and this is the most consequential
movement on the panel.** Neither asks for the comparison any more; both argue
the paper picked the wrong side of it. R6: *"By Cor. 3.4 the charge `μ*` is
`c = 2`, inside `[0, 2]` and therefore passive, so `c = 2` is simultaneously
passive and exact at the shipped `κ`."* R5 adds that the stated hedge does not
bind in the paper's own configuration: *"step (iv) says `G` hoists to load time
and is exact for a diagonal `K_c` with fixed `h`. Why is `c = 1` the default on
a host where `G` is not estimated at all?"* R5 goes further and proposes an
interior point the paper never evaluates, `c = 1.5`, returning 0.75 of the
converged amplitude with 81% median headroom. R3 asks the same question
neutrally. Four of six therefore now want an interior-point curve rather than
two endpoints.

### P5. EasyChair ID and companion overlap — **half executed**

*Companion overlap*: CONFIRMED executed and now praised. Section 4 opens with a
"Relation to the companion study" paragraph naming exactly what is shared:
*"Shared evidence is confined to the host and to two arms of the 24-cell weight
swap below, mass-only and `(M_q + hD_q + h²K_q)⁻¹`; everything else is new."*
R2 calls the disclosure "admirably specific"; R3 says *"I do not treat it as
salami-slicing."* R6 and R4 accept it as complete.

*EasyChair ID*: **NOT VISIBLE IN THE ARTIFACT.** Coordinator check: zero
occurrences of "EasyChair", "submission id", or a paper-number pattern in the
PDF text layer. This may be correct practice — an EasyChair ID is normally
entered in the submission form, not printed in an anonymous PDF — but the
*intent* behind the priority (let the chairs see [3]) is still unmet from the
reviewers' side. **Four of six still ask for chair-visible access to the
companion.** R4: *"Can the chairs see [3] to assess overlap? What is the
minimal statement of this paper's contribution that stands with [3]
withdrawn?"* R6: *"if [3] is not accepted, what system-level evidence remains?"*

### Author-mandated: fix Figure 3 — **partly executed; two confirmed residual defects**

Figure 3 is now a three-panel figure with per-panel headers and per-scene
tallies, which is a real improvement over the prior round. Two defects survive,
both CONFIRMED by the coordinator against the artifact (findings 4 and 5 below):
the caption attaches the inset to the right panel while the inset is drawn in
the middle panel, and the backward-Euler arm is split across two panels drawn
against two different abscissae with its pass/fail tallies split across two
headers.

### Author-mandated: add the T14 row — **executed, then immediately became the panel's cheapest confirmed defect**

Three T14 rows exist. Their numbers do not reconcile with the body. See
findings 1 and 2.

---

## Fact-checked issues

Each carries the reviewer's own evidence. Coordinator verdict against the
artifact follows each item.

### 1. Table 1's T14a cell counts cannot be reconciled with the body — **CONFIRMED**

R3 (verdict "refuted" on the paper's internal consistency), R1, R4, R6.

R3's evidence: *"Section 3 reports 'Of 2500 randomized symmetric charges met
with adversarial rows, all 1222 inside the interval are passive and all 1278
outside inject (T14a)'. 1222 + 1278 = 2500. Table 1 gives T14a two cell counts,
2100 (float) and 720 (rational, per the caption's 'Only T10's 300 and T14a's
720 rational cells are exact'). 2500 equals none of 2100, 720, or 2820, and
exceeds the float block, so the 2500 cannot be a subset of the float cells."*

**Coordinator: CONFIRMED.** Both strings are in the PDF exactly as quoted
(body p. 3; Table 1 row `T14a  Charge family  analytic  2100, 720  10⁻⁹; exact
0 inject in [0, 2]`). 1222 + 1278 = 2500; 2100 + 720 = 2820. No sub-block
breakdown is given anywhere. This is the panel's most-cited defect (four of six)
and it sits directly against the paper's own posture that every number is
machine-checked and shipped as per-cell CSV.

### 2. Table 1's T14b result "22 vs. 0 inject" has no anchor in the body, and violates the caption's own rule — **CONFIRMED**

R3, R4, R5, R1.

R4's evidence: *"T14b ('Equal cost', shipped, 12×27) reports '22 vs. 0 inject'.
The nearest text is 'iterating the mass-only weight leaves 17, 9, 6 and 2 cells
injecting at 2, 4, 8 and 16', which contains no 22 and does not say which budget
is the equal-cost one. One page earlier, Sec. 4 writes 'whereas ρ tracks only
22' about a different quantity."*

R3's second half: *"the caption's rule 'T4, T6, T13, T14b give one per arm'
yields 2, 3 and 2 numbers for those tables' 2, 3 and 2 arms, but T14b declares
12 arms and reports two numbers."*

**Coordinator: CONFIRMED, both halves.** Coordinator grep of the PDF text layer
finds exactly two occurrences of the numeral 22 in a data context: the T14b
Result cell, and Section 4's *"whereas ρ tracks only 22"* — a different
quantity, one page earlier. The caption rule is present verbatim. T4 gives
"27/27, 27/27" for 2 arms, T6 gives "8/0/0" for 3 arms, T13 gives "0, 3840
inject" for 2 arms — all consistent — and T14b gives two numbers for a declared
12 arms.

### 3. The supplementary video is never referenced anywhere in the PDF — **CONFIRMED**

R4's evidence: *"Searching the extracted text of all 7 pages: 'video' occurs 0
times, 'MP4' 0 times, 'accompanying' 0 times. The single supplement pointer is
'The attached anonymous supplement ships every check in that table with its
per-cell CSV: runnable code for the analytic arms, drivers and host excerpts
for the shipped-host ones', i.e. code and data only."*

**Coordinator: CONFIRMED.** `grep -ci` over the extracted text: video 0, mp4 0,
accompanying 0, supplementary 0. "supplement" occurs exactly once, in the
sentence R4 quotes. A PDF-only reader would not know the video exists, and the
video carries a second scene and a budget-grading result the paper does not
show. Fig. 1's caption is the obvious anchor.

### 4. Figure 3's caption attaches the inset to the wrong panel — **CONFIRMED**

R4's evidence: *"The caption reads 'Right, the matched weight `4M_q + h²K_q`;
inset, injection decays as the budget grows.' The inset is in the middle panel,
positioned below the `ρ_mid` data, and its own label reads 'shelf, mass weight:
ΔE (J) vs sweeps', so it belongs to the mass arm in the host-default panel."*

**Coordinator: CONFIRMED by bounding box.** Extracting span geometry from page 5:
the inset labels `'shelf, mass weight:'` and `'ΔE (J) vs sweeps'` sit at
x = 335.1–393.1 pt. The middle panel's own labels span x = 244.2–397.3; the
right panel's begin at x = 401.6. The inset is inside the middle panel by
8 pt of clearance and is 8 pt clear of the right panel's leftmost element.

### 5. Figure 3 splits the backward-Euler arm across two panels against two different abscissae, with its tallies split across two headers — **CONFIRMED**

R4's evidence: *"the open (BE) markers appear in both the middle panel
(x = ρ_mid) and the right panel (x = ρ), and the BE arm's pass/fail tallies are
split across the two panel headers: 'BE weight passive: dinner 9/9, shelf 2/9,
ledge 4/9' sits over the middle panel while its complement 'BE injects: shelf
7/9, ledge 5/9' sits over the right."*

**Coordinator: CONFIRMED by bounding box.** `'BE weight passive: dinner 9/9,
shelf 2/9, ledge 4/9'` at x = 244.2 (middle panel); `'BE injects: shelf 7/9,
ledge 5/9'` at x = 415.9 (right panel). Middle abscissa label
`'midpoint index ρ_mid = (L + 2Σᵢaᵢ)/(w_r + 2α̃)'` at x = 281–346; right
abscissa label `'row danger index ρ = L/(w_m + 2α̃)'` at x = 435–494. Two
different indices, one arm.

### 6. "Its danger index below one throughout" asserts a property of a quantity the paper never defines — **CONFIRMED**

R3's evidence: *"Fig. 3's right panel ... abscissa is labelled 'row danger index
ρ = L/(w_m + 2α̃)', spanning 10⁻³ to 10⁵. Section 4 then writes of that same
panel: 'while the matched weight `m(4 + (ωh)²) = 4M_q + h²K_q` is passive on
every cell, its danger index below one throughout.' The paper defines ρ only for
mass-only weights (Thm. 3.2), ρ_mid only as its `κ = 2` instance, and ρ_κ in
Section 6 explicitly 'for mass-only weights'. No index is defined for a general
charge W."*

**Coordinator: CONFIRMED.** Both strings are in the PDF verbatim. Coordinator
read the right panel's tick exponents from span geometry: −3, −1, 1, 3, 5, i.e.
the plotted abscissa does run to 10⁵ on the same panel whose text says the
index is below one. This is a definitional gap, not a mathematical error — a
weight-specific ratio `u⊤Gu/(w_r + 2J_c⊤u + 2α̃)` would be below one for
`W = G⁻¹` by Eq. (7) — but that ratio is never written down.

### 7. The symbol `U_i` is used once and defined nowhere — **CONFIRMED**

R4's evidence: *"Searching the full extracted text layer of all 7 pages, the
glyph U occurs exactly once: 'modal coordinates with `a_i = U_i²/m_i` and
`b_i = (ω_i h)²`' in Thm. 3.2. Sec. 2 introduces only a single coordinate with
`C = z − q`, i.e. an implicit `U = 1`. Thm. 3.3 then writes the same modal row
Jacobian as `J_c`."*

**Coordinator: CONFIRMED.** `grep -n "𝑈"` over the extracted text returns exactly
one line, the Thm. 3.2 statement. The quantity is load-bearing: `a_i = U_i²/m_i`
is what makes `w_m = J M⁻¹J⊤` and `L = h²J M⁻¹K M⁻¹J⊤`.

### 8. `Δ` silently changes meaning between Eq. (1) and the velocity reconstruction — **CONFIRMED by derivation**

R4's evidence: *"Eq. (1) defines `Δx = M⁻¹J⊤Δλ` as the solver's position
correction. The next sentence says 'backward Euler gives `q̇⁺ = Δx/h`', and
Thm. 3.3 says 'the rigid one as `Δz/h`'. Read with Eq. (1)'s meaning, the rigid
read-back `Δz/h` would give `v⁺ = −v m/(M+m)`; the proof of Thm. 3.1 instead
uses `v⁺ = vM/(M+m)`, so `Δz` there must mean the full substep displacement
`z⁺ − zⁿ`."*

**Coordinator: CONFIRMED, arithmetic reproduced.** With `Δλ = −hv/w_m` and
`w_m = (M+m)/(Mm)`, Eq. (1) gives `Δz = M⁻¹Δλ = −hvm/(M+m)`, so
`Δz/h = −vm/(M+m)`. Thm. 3.1's proof states `v⁺ = vM/(M+m)`, which equals
`v + Δz/h`, not `Δz/h`. The two readings coincide for `q` only because the cold
start makes the modal predictor inert — which is R4's point. No sentence in the
paper flags the change.

### 9. Three of the five formal results carry no proof — **CONFIRMED**

R1 and R4.

R1's evidence: *"Thm. 3.2 has no proof; Thm. 3.3 gets one clause ('makes
`u⊤Gu = J_c⊤G⁻¹J_c` telescope'); Cor. 3.4 has none at all... The sufficiency
direction needs the spectral step `S² ⪯ 2S` iff `0 ⪯ S ⪯ 2I` for
`S = G^{1/2}WG^{1/2}`, and the necessity direction needs a scaling argument in
`‖J_c‖`; neither appears anywhere in the paper."*

R4 adds that reconstructing Eq. (6) requires the general-case correction
`Δq_c = −W J_c Δλ` and the read-back, neither of which is written: *"Sec. 2
states the correction only in the scalar single-coordinate form
`Δx = M⁻¹J⊤Δλ` and Thm. 3.3 never restates it for a block with a charge
operator `W ≠ M_c⁻¹`."*

**Coordinator: CONFIRMED.** Thm. 3.1 has a `Proof … □` environment. Thm. 3.2,
Thm. 3.3 and Cor. 3.4 have none. Prop. 3.5 has an informal derivation paragraph
(*"order A deposits a fresh `q_c` that the trailing spring relaxes to
`q_c/(1+b)`, cutting the deposit by `(1+b)²`"*) but no `Proof` environment.
The body fills p. 6's left column exactly; whether ~0.5 page of *body* budget
remains depends on a MIG 2026 page limit that two reviewers could not verify
(see Section B, disagreement 3).

### 10. Figure 4's type is below print legibility — **CONFIRMED with exact measurements**

R4's evidence: *"page 5 contains text at 3.60 pt (the exponents on Fig. 4's log
tick labels, e.g. the '2' at bbox [108.9, 284.6, 111.2, 290.8]), 3.97 pt,
4.63 pt (the in-plot annotation 'faint filled: implicit arm (all below 0)'),
4.89 pt (all four legend entries), 5.15 pt (tick mantissas) and 5.66 pt (both
axis labels). Body text on the same page measures 9.08 pt."*

**Coordinator: CONFIRMED exactly.** Independent PyMuPDF span extraction of
page 5 gives the size histogram `3.6 (12 chars), 3.97 (3), 4.25 (4), 4.46 (25),
4.63 (40), 4.74 (8), 4.89 (116), 5.15 (28), 5.66 (48), 5.98 (386), 6.08 (84),
6.38 (291), 6.77 (94), 6.97 (109), 7.57 (77), 8.81–9.08 (body, ~4,000)`. The
3.60 pt span at `[108.9, 284.6, 111.2, 290.8]` is present as quoted. Fig. 3 is
also affected: its tick exponents are 4.46 pt and its `ρ_mid` subscripts
4.46–4.74 pt. Fig. 1's three experimental-condition lines are 5.66–5.71 pt.

### 11. "Headroom to the injection threshold" is never defined — **CONFIRMED**

R2, R3, R5, R6.

R2's evidence: *"Sec. 6's 'headroom to the injection threshold falls under 1% on
a fifth of the cells measured (median 36%) against at least 100% at c = 1
(median 171%)' — at c = 1 the row never injects for any `a`, so 'headroom' must
mean tolerance to G mis-estimation, but the quantity is never defined."*

R5 reconstructed it and it fits: *"headroom(c) = (1 + sqrt(1+t))/c − 1 with
t = (w_r + 2α̃)/a ... A single t = 1.924 produces 171.0% at c = 1 and 35.5% at
c = 2 (paper: 36%), and t = 0.040 produces 102% at c = 1 and 1.0% at c = 2."*

**Coordinator: CONFIRMED.** "headroom" occurs exactly once in the PDF, in the
sentence quoted, with no definition anywhere. R5's reconstruction is a
reviewer's inference, not the paper's definition — but the fact that a single
parameter `t` reproduces both quoted pairs is decent evidence the numbers were
measured rather than asserted, and R5 explicitly frames it that way.

### 12. Weight nomenclature collides, and `ζ` is never given a numeric value — **CONFIRMED**

R4's evidence: *"`m(1+b) = M_q + h²K_q`, so it differs from `M_q + hD_q + h²K_q`
by `hD_q = 2ζωhm`. Fig. 2's right panel is titled 'implicit weight
`(M_q+hD_q+h²K_q)⁻¹`'; Rmk. 1 says 'the backward-Euler weight `m(1 + b)`';
Fig. 3's legend says 'backward-Euler weight (open)' ... neither Fig. 2's nor
Fig. 3's caption states `ζ`, so a reader cannot tell whether the two figures
show the same arm."*

**Coordinator: CONFIRMED.** All four strings are in the PDF as quoted. `ζ`
appears only symbolically (Sec. 2's `2ζωm`; the per-impulse masses
`m(1+2ζωh+b)` and `m(1+ζωh+b/4)`; the amplitude gap `2ζωh/(1+M/m+b)`; and
"`κ = 1` with `ζ = 0`"). No numeric `ζ` for any figure or shipped experiment.
R5 offers a reading worth relaying: *"with no zeta axis on the phase map this
panel is presumably the matched weight with D = 0, labelled with the companion
study's formula."*

### 13. Six cost ratios; one hardware statement; no platform, language, or methodology — **CONFIRMED**

R4's evidence: *"Sec. 3: 'leaves the row solve at 0.99 to 1.02 times the
mass-only default' and '6.8 to 14.5 times the diagonal accumulation for r = 4 to
64, ratios on a reference implementation, not production timings'. Sec. 4: 'at
5.3 times the measured substep cost', '0.996 of the mass-only cost', '20 times
the cost'. Sec. 6: 'evaluating it costs 6% of the row solve it precedes'. Only
the Cholesky ratio carries the 'not production timings' hedge."*

R5 makes the practitioner consequence explicit: *"the 6% and 0.996 numbers are
the whole practitioner argument and they are currently the least-supported
numbers in the paper."*

**Coordinator: CONFIRMED.** All six ratios are in the PDF as quoted; exactly one
carries the hedge. No hardware, language, coupled-coordinate count `r`, or
timing methodology appears anywhere. The video's own footer says "offline CPU
float64, no real-time claim".

### 14. The "passivity governor" is disabled in every experiment, never defined, and never used as a baseline — **CONFIRMED**

R3 and R6.

R3's evidence: *"The phrase appears three times without definition: Fig. 1
subtitle 'passivity governor off'; Section 4 'with the passivity governor off,
relaxation at 1 and no other contacts'; Section 4 again 'with the symplectic
stepper and the passivity governor off'. The supplementary video repeats it
('passivity governor OFF') on every frame of both scenes... No cell of Table 1
has a governor-on arm."*

R6 draws the sharper consequence: *"the paper positions itself as practitioner
guidance and claims a cost advantage over the alternative remedy of iterating
('passive on all 27 at 64 iterations and 20 times the cost'), a comparison it
does not make against the mechanism the host already ships."*

**Coordinator: CONFIRMED.** Three occurrences in the PDF, all quoted correctly,
all "off", no definition. Coordinator confirmed the video footer independently:
`passivity governor OFF` appears in the operating-point line of both the shelf
act and the dinner act.

### 15. The abstract overstates what a host already has assembled — **CONFIRMED**

R1's evidence: *"Abstract: 'A pre-solve danger index ρ, a ratio of two quadratic
forms a host already assembles'. Only the denominator `J M⁻¹J⊤` (Delassus) is
routinely assembled; the numerator `h²J M⁻¹K M⁻¹J⊤` requires the stiffness
action through the row. Section 3 concedes exactly this by calling only 'the
right-hand operator of (5)' the one 'that contact solvers already form'."*

**Coordinator: CONFIRMED.** Both strings are verbatim in the PDF and they are
asymmetric in exactly the way R1 describes. The Recipe's honest version
("evaluating it costs 6% of the row solve it precedes") is the sentence the
abstract should mirror.

### 16. Contribution C2 is stated in Loewner form whose only non-trivial content lies outside the paper's scope — **CONFIRMED, with a mitigating clause the reviewers did not quote**

R1, R2, R6.

R6's evidence: *"C2 is stated as 'The row-visible spectral form of that boundary
at κ = 1, `h²JM⁻¹KM⁻¹J⊤ ≻ JM⁻¹J⊤` (Thm. 3.2)', using Loewner ordering.
Thm. 3.2 then concedes 'Here J is one row, so ≻ is the scalar `L > w_m`', and
'several simultaneously active rows are outside our scope'. Both sides are 1×1,
so the Loewner order carries no content in the proved regime."*

**Coordinator: CONFIRMED, with one qualification the panel missed.** The quoted
strings are exact. But C2's full text continues *"…, reduced to a scalar danger
index ρ a host can evaluate per row before it solves; ρ > 1 is injection"* —
so the contribution bullet itself flags the reduction to a scalar in the same
sentence. That weakens R2's and R6's "inflation" framing somewhat. The
substantive half of the objection stands: T14c measures the index calling 2,795
warm/two-row cells safe when they inject, which is exactly the multi-row regime
where a matrix ordering would have content.

### 17. Figure 1 runs at an operating point that is not one of the 24 evaluated grid cells — **CONFIRMED**

R3's evidence: *"Fig. 1 states '1 iteration × 8 substeps per 1/120 s frame'.
Section 4 defines the weight-swap grid as 'four iteration-substep budgets
(4, 1), (8, 2), (16, 4), (32, 8)'. The lowest of those is 4 solves per frame;
Fig. 1 uses 8 solves per frame but only 1 iteration per substep, so it is not
any grid cell."*

**Coordinator: CONFIRMED.** Both strings are verbatim in the PDF, and `(1, 8)`
is not among the four listed budgets. Defensible — the theory is about one
sweep — but the paper's most persuasive visual therefore has no cell-level
pass/fail statistic behind it, and the reader is left to assume the 8-of-24
overrun figure covers it.

### 18. The video discloses an 89× grid dependence in the accuracy reference that the paper omits — **CONFIRMED against the MP4**

R1, R3, R5, R6.

R3's evidence: *"Every frame of the video's shelf scene carries the line
'converged references disagree 89x: 9.6 mm at 1/960 s substeps, 0.1 mm at
1/120 s'. Fig. 1's caption cites only the first: 'A converged run on the same
grid lifts a book 9.6 mm, so (b) is not ground truth.'"* R3 adds the point that
strengthens rather than weakens it: *"the video's second scene reports
'converged references, both grids 11.6 to 11.8 mm', i.e. the dinner scene does
not have this problem."*

**Coordinator: CONFIRMED by direct frame extraction.** The shelf act at t = 8 s
reads, under both arms, verbatim: `converged references disagree 89x: 9.6 mm at
1/960 s substeps, 0.1 mm at 1/120 s`. The dinner act at t = 20 s and t = 40 s
reads `converged references, both grids 11.6 to 11.8 mm`. Fig. 1's caption in
the PDF cites only the 9.6 mm figure. Since the weight-swap grid spans `h` from
1/120 to 1/960 s, the accuracy yardstick on the teaser scene is grid-dependent
across exactly the range the paper evaluates.

### 19. Several body counts have no anchor in Table 1's Cells column — **CONFIRMED (partly)**

R3's evidence: *"Section 3's '19 of 2000 randomized coupled-stiffness rows' and
Section 4's '32,000 arm-cells' and '3000 cells' map onto no Cells entry (T10 is
9900+300, T11 is 15,000)."*

**Coordinator: CONFIRMED for 2000, 32,000 and 3,000.** None appears in Table 1's
Cells column (`2626, 58081, 300, 2×27, 208, 3×24, 7000, 1200, 1600, 27,
9900+300, 15000, 53000, 2×10⁴, 2100+720, 12×27, 43,783`). **NOT CONFIRMED for
the 43,783/43,898 pair**, which the paper explicitly explains: *"the
denominators differ because row activity after the sweep depends on the weight;
both arms scan the same draws."*

### 20. Roughly a third of the empirical weight rests on an unnamed production host, and one of the two system-level pillars is shared with an unavailable companion — **CONFIRMED as a fact about the packet**

R3's evidence: *"The four shipped rows (T4 2×27, T6 3×24, T9 27, T14b 12×27) all
depend on 'a production position-based support solver, the host of the companion
study [3]', which is anonymous. 'Host excerpts' is not a runnable host."*
R6 quantifies the residue: *"Net new system-level content is therefore one added
arm on a borrowed 24-cell grid plus one 27-cell cold-row sweep."*

**Coordinator: CONFIRMED as a description of the packet.** The quoted sentences
are in the PDF. This is not an accusation — the disclosure is unusually
specific and every reviewer says so — but it is a real bound on what an
independent group can check from this submission alone.

---

## Asserted but unevidenced

Reported separately because these carry no quotation, equation, or derivation,
or because the coordinator found the supporting arithmetic wrong.

**a. R2: "Body length is roughly 5.3 pages excluding references, within MIG's
4-6 page short-paper allowance."** The allowance is asserted with no source.
R4 and R5 both fetched `mig.siggraph.org/2026` and `easychair.org/cfp/mig2026`
and report that neither publishes a short-paper track or a page limit for 2026.
Coordinator measurement: body runs through p. 6's left column, i.e. **≈ 5.5
pages**, not 5.3. Do not act on R2's "within allowance" claim; see Section B,
disagreement 3.

**b. R6: "Ten of the fourteen rows in Table 1 are Model = 'analytic'."**
**NOT CONFIRMED as stated.** Coordinator count of Table 1: 17 rows —
analytic = T1, T2, T5, T7, T8a, T8b, T10, T11, T12, T13, T14a, T14c (**12**);
nonmodal = T3 (**1**); shipped = T4, T6, T9, T14b (**4**). R6's arithmetic is
wrong; R6's *substance* — that most of the validation is machine-checking the
authors' own algebra — is correct and in fact stronger than stated (12 of 17,
not 10 of 14). Use the substance, not the count.

**c. R4: "3 arms × 2 relaxations × 4 budgets = 24."** The product is right and
matches the paper, but the first factor is mislabelled: the paper says *"three
scenes, two relaxations θ ∈ {0.7, 1.0}, and four iteration-substep budgets"*,
i.e. 3 **scenes** × 2 × 4 = 24 cells **per arm**, with three arms (T6's
"3 × 24"). No consequence, but do not propagate the labelling.

**d. R4: "roughly 0.6 page of unused budget"; R1: "Section 6's Recipe and 'When
to couple into the row' prose could have paid for four lines of algebra."**
**PARTIALLY CONFIRMED.** Coordinator: the body fills p. 6's left column
*exactly*, so there is no slack on the current page; the ~0.5-page figure is
headroom against a 6-page body limit that R4 and R5 could not verify exists for
MIG 2026. R1's point (that four lines of algebra would fit if something else
were cut) is a trade, not free space, and should be presented as such.

**e. Video board-mode energy readings differ across reviewers** (R1: 1,716 J and
1,613 J; R2: 1,719 J and 1,773 J; R3: a 1,613–3,893 J range; R4 and R6:
1,719 J). Coordinator measurement at t = 8 s: **1,672 J** (mass) and **0.20 J**
(matched), playhead at ≈ 147 ms. These are not in conflict — the board-mode
energy is a decaying time series and each reviewer sampled a different frame.
All readings bracket Fig. 1's quoted 1,707 J at 114 ms. **No defect; do not
treat the spread as an inconsistency.**

**f. R1's verdict "unverifiable" on the 19-of-2000 diagonal-charge rate.**
R1's own constructed counterexample (equicorrelated `G`, ρ = 0.9,
`ΔE = +3.1e-2` against `E⁻ = 0.5`) confirms the *phenomenon*; only the *rate* is
ensemble-dependent. See Section B, disagreement 1 — four other reviewers reached
"verified", and R6 supplied the governing structural condition. The honest label
is "phenomenon confirmed, rate not reproducible without the draw distribution".

**g. R5's headroom formula** is a reverse-engineering, clearly labelled as such
by R5, that fits both quoted pairs from a single parameter. It is evidence the
paper's numbers were measured; it is **not** the paper's definition and must
not be cited as if the paper had stated it.

---

## (B) Disagreements among reviewers

Four places where reviewers reached opposite conclusions. Presented as found,
not averaged.

### 1. Is the diagonal-charge failure claim verified or unverifiable?

**R1: unverifiable.** *"With a natural ensemble (`M_c = AAᵀ+I`, `K_c = BBᵀ`
scaled over four decades, r = 2..4) I got 0 of 2000."*

**R3: verified, and the paper is conservative.** *"With rows aligned to the top
eigenvector ... the diagonal charge injected on 4265 of 20,000 draws while full
`G⁻¹` injected on none ... The paper's own rate (19 of 2000) is simply a less
adversarial sampling of the same effect."*

**R6: verified, with the mechanism.** *"The uniform condition is
`λ_max(diag(G)⁻¹G) ≤ 2`. This is unviolable at r = 2 (equals `1 + |ρ| < 2`) but
fails on 32 percent of my r = 3 Wishart draws and 97 percent at r = 8, and a
row aligned with the bad eigendirection then injects (634/2000 at r = 3). A
randomly oriented, unit-scale row rarely realises it, which is exactly why the
paper's reported rate is about 1 percent."*

**Better evidenced: R6, decisively.** R6 alone explains *why* R1 saw 0/2000 and
R3 saw 4265/20000 from the same true claim — the condition is structural
(`λ_max(diag(G)⁻¹G) > 2`, needing `r ≥ 3` and strong coupling) and the observed
rate is a function of row orientation and rank, not of the claim's truth. R1's
"unverifiable" is correct about the *number* and misleading about the *claim*.
R2 and R5 land between them and both call the direction real. **Resolution: the
phenomenon is confirmed five ways; the rate is not reproducible without the
ensemble. The paper should report R6's condition, which is what R1's and R6's
questions both ask for.**

### 2. Does Cor. 3.4's "iff" need an explicit unbounded-`J_c` quantifier?

**R1 says yes, and calls it a defect.** *"at c = 2.001, the same configuration
gives `ΔE = −5.42e-1` at `‖J_c‖ ~ 1` (passive) and `ΔE = +2.79e-9` at
`‖J_c‖ ~ 1e3` (injecting). So the 'iff' is asymptotic in row magnitude ... a
practitioner with bounded mode shapes could reasonably conclude the wrong
thing."*

**R2, R4 and R6 say no, and list the same fact under strengths.** R2: *"the
converse follows because any positive eigenvalue of `WGW − 2W` injects at
sufficiently large `‖J_c‖`."* R6: *"the `W ⪰ 0` half is implied rather than
assumed."*

**Better evidenced: R2/R4/R6, on the artifact.** Coordinator check: the
corollary's very next sentence reads *"outside that interval the row injects
once `a > (w_r + 2α̃)/[c(c−2)]`"* — the quantifier R1 wants is already printed,
one clause later, in the exact form R1 measured. R1's *objection* is therefore
weaker than R1 believes. **But R1's derived question is the best one on the
panel and nobody else asked it:** given bounded mode shapes, what overshoot of
`W` beyond `2G⁻¹` is admissible at a given max row norm? R2 asks a measurable
version ("on the 27 shipped cells, how many would remain passive at `c` outside
`[0,2]`"). Keep the question; drop the defect framing.

### 3. Does MIG 2026 have a short-paper track with a 4–6 page limit?

**R2 asserts yes** and calls the paper "within MIG's 4-6 page short-paper
allowance", with no source. **R3 hedges**, citing "the 4-6 page (excluding
references) short-paper convention I could find for recent MIG editions".

**R4 and R5 both fetched the 2026 sources and say it is unverifiable.**
R4: *"The MIG 2026 EasyChair CFP (easychair.org/cfp/mig2026) and
mig.siggraph.org/2026 name only 'Full papers' and 'Posters' and state no page
limits, with a note that limits and template links are to be added when
finalized."* R5: *"Neither publishes a page limit for the long or short track as
of this fetch (the site lists only the 25 July - 7 August 2026 submission
window)."*

**Better evidenced: R4 and R5, decisively** — they name the URLs fetched and
what was found; R2 and R3 cite convention from prior editions. **This is
load-bearing, not pedantry:** the paper's ACM Reference Format block states
"7 pages", the submission window closes 7 August 2026, and finding 9 (add
proofs) presumes body headroom that may not exist. Confirm the track and the
limit before acting on any length-dependent recommendation in this report.

### 4. Is the denominator-only half-implementation "worse than no fix"?

**R5 measured it against a control and says yes.** *"the denominator-only
variant injecting on 19,624 of 30,000 draws at κ = 2, against 18,227 for the
mass-only default it replaces, i.e. the half-fix is a regression."*

**R6 measured it without a control and says the warning is understated.**
*"Applied the matched denominator `G` but corrected positions with `M_c⁻¹` at
κ = 2: injected on 2021 of 3000 random draws. The warning is if anything
understated."*

**Better evidenced: R5**, because R5 is the only reviewer who ran the
mass-only control arm, and the control is exactly what turns "the half-fix
still injects" into "the half-fix is worse than doing nothing". That said,
**R5's stronger claim is single-sourced** and the two rates (65% vs 67%) come
from different samplers, so the *ranking* against the control has one
measurement behind it, not two. Both reviewers ask the same thing of the
paper — print a number next to "the denominator alone is not the proved method"
— and that request is safe to act on regardless of which rate is right.

### 5. Video effect: one reviewer against five

**R5 alone reports the video "raised score"**, citing its instrumentation and
controls: *"the best support artifact I have seen at this venue in a while ...
a footer that pre-empts the obvious objections."* The other five report "raised
confidence only". No reviewer reports the video lowering anything. Reported for
completeness; it does not change the distribution, since R5's score is 5/7 like
everyone else's.

---

## Missing evidence and scope gaps

Ordered by how much they bound the paper's claims.

**1. The certified regime is first-touch; the demonstrated regime is not.**
All six. The scope is one sweep, cold start, one row, `e = 0`, no friction. The
paper's own T14c reports the matched charge injecting on **4,099 of 43,898**
warm/two-row cells (≈ 9.3%) and the mass-only index calling **2,795 of 19,730**
true injections safe (≈ 14.2% false negatives, the unsafe direction). Both
figures live only in the final Limitations paragraph; the abstract reports only
"passive on all 27 cells" and "from 8 of 24 to 0". R3 and R1 both propose
surfacing the warm/two-row rates in the abstract or contributions. R6 supplies
the mechanism that makes this structural rather than merely empirical: once
`q̇ⁿ ≠ 0`, no fixed `κ` exists, so Thm. 3.3 does not apply at all after first
touch. **Nobody asks for more experiments here. They ask for the emphasis to
match the evidence.**

**2. No governor-on baseline anywhere.** Finding 14. The host apparently ships a
mechanism aimed at the exact problem the paper solves, and it is off in Fig. 1,
in all four shipped-host rows, and on every frame of the video. There is no arm
that answers "does the matched weight beat, complement, or lose to what the
host already has".

**3. Warm/two-row failures are counted but not characterized.** R1: *"what is
the distribution of `ΔE/E⁻` [for the 4,099]"* — R6 sharpens it: *"the shelf
demo's interest is whether these are 1e-3 events or 1e+1 events."* R2 asks
whether they have structure (two active rows? warm λ? a particular `m/M` band?)
and whether any cheap fix removes them.

**4. No interior point of the `c`-family is evaluated.** Section 6 gives two
endpoints and a binary rule. R5 computes that `c = 1.5` would return 0.75 of
the converged amplitude at 81% median headroom; R3 asks for a
headroom-versus-amplitude curve rather than two endpoints; R6 argues for
shipping `c = 2` outright. The paper's own T14a data would support the curve.

**5. No wall-clock timing.** Finding 13. Six ratios, one hedge, no platform.
R5: a single row-solve microbenchmark "would cost an afternoon and would convert
the budget argument from plausible to settled".

**6. `κ_r` is not covered by the Recipe.** R5: step (ii) gives `ρ_κ`, which
assumes `κ_r = 1`; step (i) says "if the host rescales that block too, use
Rmk. 1's boundary", but Remark 1 gives that boundary only in prose, so the
reader must re-derive the index. R5 also notes that the most alarming result
for a fully symplectic host — that at `(κ_r, κ) = (2,2)` the mass-only weight
injects at *every* stiffness and *every* mass ratio — is four words inside
Remark 1 (*"and `b > 0` at `(2, 2)`"*), and that the matched charge's staying
passive there (which R5 confirmed 0/40,000) is not surfaced either.

**7. Shipped-host rows are not independently checkable.** Finding 20. No
reviewer proposes a remedy beyond a one-line reproducibility statement scoping
which table rows can be re-run from the supplement alone (R3).

---

## Video assessment

**50.200 s, 1920 × 1080, 30 fps, 1,506 frames, H.264, 8,065,820 bytes,
SHA-256 `a9ef…7901`.** Two acts: cantilever shelf, then dinner table.

**Effect on the panel: five "raised confidence only", one "raised score" (R5).
No reviewer reported the video lowering a score or confidence.**

Coordinator verification by direct frame extraction:

- **Shelf act (t = 8 s):** mass arm board-mode energy **1,672 J**, books'
  translational KE 0.51 J, **highest book lifted so far 56.8 mm**; matched arm
  **0.20 J**, 0.008 J, **5.3 mm**. Trace annotated `peak 925,575 J` against
  `scene's energy at the start of the run 64.5 J`. Fig. 1's 56.8 mm and 5.3 mm
  match exactly; Fig. 1's 1,707 J / 0.35 J at 114 ms falls inside the captured
  range.
- **Dinner act (t = 40 s):** mass arm **0.61 J / 32.9 mm**, matched
  **0.48 J / 7.6 mm**, `converged references, both grids 11.6 to 11.8 mm`,
  `peak 857 J` against `48.2 J` at start. This scene does not appear in the
  paper at all.
- **Operating point, both acts:** `1 iteration x 8 substeps per 1/120 s frame |
  modal relaxation 1.0 | passivity governor OFF`, plus per-scene material and
  drop parameters (`steel shelf, E = 200 GPa, thickness 30 mm | 6 kg dropped
  1.00 m, never closer than 125 mm to a book`; `table E = 1.1 GPa, the paper's
  own material, not tuned | 5 kg dropped 0.80 m onto the bare centre`).
- **Disclosure footer:** `playback 32x slow motion, one captured substep per
  video frame, then frozen 0.9 s at the energy peak (the same frame 28 times) |
  independent runs, nothing toggled mid-trajectory | offline CPU float64, no
  real-time claim`. R6's playback consistency check reproduces: 30 fps × one
  substep × `h = 1/960 s` = 31.25 ms of simulation per video second, and
  1/32 s = 31.25 ms. Self-consistent.
- **Geometric control:** shelf, `never closer than 125 mm to a book`; dinner,
  `the pot never contacts any object: its rotated footprint stays more than
  85 mm clear of every one, so every response is carried by the table`.
- **Budget grading, per scene:** shelf — `raising only the iteration count,
  2 x 8 still gains 151,140 J and 4 x 8 gains 856 J; the gain first vanishes at
  8 x 8`. Dinner — `2 x 8 still gains 3.2 J, and at 4 x 8 the gain is gone
  entirely`. Neither figure appears in the PDF.

**The video is materially more forthcoming than the paper in three places**, and
this is the panel's sharpest structural observation about the packet:

1. It states the 89× converged-reference disagreement on the shelf; the paper
   quotes only the 9.6 mm half (finding 18).
2. It shows a second scene where the converged references *do* agree across
   grids (11.6–11.8 mm) and the matched arm gives 7.6 mm against the mass arm's
   32.9 mm — which R6 correctly calls "the better accuracy evidence" — and the
   paper does not show that scene in motion or in a figure.
3. It reports budget grading (`8 x 8` on the shelf, `4 x 8` on the table) that
   the paper does not.

**And the paper never mentions the video** (finding 3). A PDF-only reader gets a
strictly weaker and, on the accuracy question, a strictly less honest picture.
No reviewer found any inconsistency between the two artifacts; the disagreements
are all omissions in the paper's direction.

R4 notes one magnitude gap nobody reconciles: Fig. 1 headlines 1,707 J of
board-mode energy at 114 ms while the video's total-scene trace peaks at
925,575 J against a 64.5 J start. Both are true of different quantities at
different instants; the paper's number understates rather than overstates, so
this is not a defect, but the two artifacts differ by ~540× in headline
magnitude and neither reconciles them.

---

## Submission readiness

**Two mechanical repairs are mandatory before upload.** Both are confirmed
against the artifact, both are edits to existing text, and both undercut the
paper's own credibility posture if shipped as-is.

**M1. Reconcile Table 1's T14a and T14b entries with the body** (findings 1 and
2). T14a: text says 2,500 charges split 1222/1278; table says "2100, 720". Give
the sub-block breakdown. T14b: the Result "22 vs. 0 inject" appears nowhere in
the body, and the caption's rule "T4, T6, T13, T14b give one per arm" is
violated by two numbers for 12 declared arms. Four of six reviewers reached for
these first, precisely because the paper's stated posture is that every number
is machine-checked and shipped as per-cell CSV.

**M2. Point Fig. 1's caption at the video, and move the 89× disclosure into the
paper** (findings 3 and 18). The video says `converged references disagree 89x:
9.6 mm at 1/960 s substeps, 0.1 mm at 1/120 s`; the caption says only "A
converged run on the same grid lifts a book 9.6 mm". Section 4's accuracy
numbers (median 0.57 of converged) are stated against that reference. Adding
"and the dinner scene's references agree, 11.6–11.8 mm" strengthens the paper.

**Cheap, high-return, not blocking:**

- **Fix Fig. 3's caption** — the inset is in the middle panel, not the right
  (finding 4, confirmed by bounding box), and the BE arm's tallies are split
  across two headers against two abscissae (finding 5).
- **Define `U_i` or rename it `J_c`** (finding 7). One symbol, one occurrence,
  load-bearing.
- **Regenerate Fig. 4 at caption font size** (finding 10). Measured 3.60 pt
  tick exponents and 4.89 pt legend against a 9.08 pt body. Single-column
  figure; the fix is a rcParams change.
- **Define "headroom"** (finding 11). One sentence. Four reviewers asked.
- **State `ζ` for Figs. 2 and 3, and reconcile "implicit weight" with
  "backward-Euler weight"** (finding 12). They coincide only at `ζ = 0`.
- **Print a number next to "the denominator alone is not the proved method"**
  (Section B, disagreement 4). Both R5 and R6 measured it; "worse than not
  fixing it" is a far stronger deterrent than "not proved".
- **Say what the passivity governor is**, even in one clause (finding 14).
- **Soften the abstract's "a host already assembles" to match Sec. 3** (finding
  15).

**Anonymity and format: clean.** Coordinator-verified: XMP `dc:creator` =
`Anonymous Author(s)`, docinfo author empty, byline "Anonymous Author(s)",
companion cited as `[3] Anonymous … Companion paper, under anonymous review`,
19 URI links all `doi.org` or the cited `box2d.org` post, zero white-fill text
spans, acmart sigconf + review option with line numbers, CCS concepts and
keywords present.

**Length: unresolved.** 7 pages total, body ≈ 5.5 pages excluding references.
R4 and R5 both fetched MIG 2026's CFP and EasyChair page and found **no
published short-paper track and no page limit** as of their check. Confirm the
track exists and what the limit is before acting on any length-dependent item
above — including the proofs in finding 9. Submission window closes 7 August
2026.

---

## Per-reviewer précis

**R1 — Mathematical and technical correctness. 5/7, conf 4/5, weak accept.**
Re-derived every closed form by hand and wrote independent verification code;
found no errors, "including the ones I expected to be off by a factor". Verified
Eq. (3) (0 sign mismatches / 20,000), the `y = ρ − 1` identity (4.6e-11), Eq. (6)
(1.1e-12 over 4,000 multi-coordinate cells), Eq. (7) (7,000 cells including
singular `K_c` and negative `κ`, matching the inelastic loss to 2.2e-14), the
`(1+b)²` divisor (4.8e-13), and both relaxation boundaries. Found one result
*stronger* than claimed: the `κ = 2`, `c = 2` implicit-midpoint identity holds
for multiple coordinates, not just one (8.9e-11). Two majors: missing proofs,
and the certified/deployed regime gap. Unique contributions: the abstract's
Delassus overstatement, and the observation that Cor. 3.4's necessity is
asymptotic in `‖J_c‖`.

**R2 — Novelty and significance. 5/7, conf 4/5, weak accept.** Verified Eq. (6)
in exact `Fraction` arithmetic (0 of 3,000) and the matched charge over 200,000
float draws spanning twelve decades (worst `ΔE/E⁻ = −5.33e-16`). Fetched and
verified four load-bearing attributions verbatim, including extracting the Small
Steps PDF to confirm its energy discussion is about damping, not gain. Two
majors, both about *delta* rather than correctness: at `κ = 1` the matched
operator is the conceded stiffness-aware mobility of [24, 1], and the only
demonstrated `κ ≠ 1` host is the authors' own — so "reconstruction dependence is
a main finding" rests empirically on one in-house solver. Uniquely notes that
the abstract's "8 of 24 to 0" is achieved by *both* remedy arms including the
companion's published one, and that Fig. 3 middle is the experiment that
actually discriminates the contribution.

**R3 — Evaluation and reproducibility. 5/7, conf 4/5, weak accept.**
Re-implemented the one-sweep row from the Section 2 prose alone, without using
the paper's formulas, and reproduced everything over ~100k draws; the only
mismatches were 1e-9-level at `c ≈ 2`, exactly the cancellation regime the
paper's own caption flags. Reproduced the diagonal-charge failure adversarially
(4265/20000) and found the paper's rate conservative. **The only reviewer to
return a "refuted" verdict**, on Table 1's T14a reconciliation. Two majors: the
warm/two-row rates are confined to Limitations, and the passivity governor is
disabled everywhere and never baselined. Uniquely caught that Fig. 1's `(1, 8)`
operating point is not one of the 24 evaluated cells.

**R4 — Clarity and submission readiness. 5/7, conf 4/5, weak accept.** "On
correctness this is the cleanest submission I have reviewed this cycle." All
weaknesses presentational, and nearly all of them independently confirmed here
by measurement: the 3.60 pt Fig. 4 type with exact bounding boxes, the missing
proofs, the once-used `U_i`, the silent `Δ` meaning change (arithmetically
demonstrated), the `ζ`/nomenclature collision, the Fig. 3 caption/inset
mismatch, and the video's total absence from the PDF. Ran the anonymity audit
independently and got the same result the coordinator did.

**R5 — Practitioner value and MIG fit. 5/7, conf 4/5, weak accept. The only
reviewer whose score the video raised.** Verified Eq. (7) in exact rational
arithmetic with a hand-rolled rational matrix inverse, and Cor. 3.4 in *both*
directions (1,930 out-of-interval charges, adversarial row from the top
eigenvector, injection in every case). Reverse-engineered the undefined
"headroom" quantity and reproduced both quoted pairs from a single parameter.
Measured the denominator-only half-fix **against a mass-only control** and found
it a regression. Argues `c = 1` is the wrong ship default on the paper's own
host and proposes `c = 1.5`. Uniquely notes that `(κ_r, κ) = (2,2)`'s "injects
at every stiffness" is buried in four words of Remark 1.

**R6 — Skeptical senior-PC calibration. 5/7, conf 4/5, weak accept.** Verified
the Thm. 3.3 telescope in exact rationals with a coupled 3×3 `K_c`, and derived
the exact governing condition for the diagonal-charge failure
(`λ_max(diag(G)⁻¹G) ≤ 2`, unviolable at `r = 2`, failing on 32% of `r = 3`
Wishart draws) — the single most useful piece of mechanism on the panel.
Independently confirmed XPBD's compliant-row premise (3e-12 over 5,000 draws).
Supplies the sharpest form of the scope objection anyone has produced: `κ` is
undefined once `q̇ⁿ ≠ 0`, so Thm. 3.3 does not apply after first touch, making
the gap structural rather than empirical. Argues for shipping `c = 2`. One
arithmetic slip (Table 1 row counts), segregated above.

---

## Bottom line

Six independent reviewers, six weak accepts, mean **5.00/7**, mean confidence
**4.00/5**, no outlier. The score has not moved since 2026-07-29, and the
2026-07-28 panel's 5.17 (which rested on a single 6/7 from the
practitioner lens) has not been recovered — that same reviewer is at 5/7 here.

But the *shape* of the panel has moved, and in the paper's favour. All five
2026-07-29 priorities were executed or half-executed, and four of them are now
either closed or attacked from a higher level: nobody asks for the `c`-family
comparison any more, they argue about which point to ship; nobody asks for the
denominator-and-correction statement any more, they measured the half-fix and
want the number printed; nobody calls the scope wording blanket any more, they
call it exemplary and object to the ceiling it honestly discloses. The
mathematics survived the most aggressive verification this artifact has faced —
exact rational arithmetic from three reviewers, 200,000-draw sweeps spanning
twelve decades, adversarial-row constructions, and independent re-implementation
from the prose alone — with **zero reported errors**.

What is left is a correct, honestly scoped, densely written short paper whose
guarantee is a first-touch guarantee, whose most persuasive figure runs at an
unevaluated operating point against a grid-dependent reference, and whose
validation table does not add up in two places. The first is a bound on
significance and cannot be fixed before 7 August. The second and third can be
fixed this week.

**Three highest-priority remaining items:**

1. **Reconcile Table 1's T14a and T14b counts with the body.** Four of six
   reviewers reached for these first; the T14a text says 2,500 (1222 + 1278)
   against a table entry of "2100, 720", and T14b's "22 vs. 0 inject" has no
   anchor anywhere in the body while violating the caption's own per-arm rule.
   A paper whose posture is "every number is machine-checked and shipped as
   per-cell CSV" cannot ship with its validation table failing arithmetic.
2. **Cite the video from Fig. 1's caption and move the 89× converged-reference
   disagreement into the paper.** The video is more honest than the PDF on the
   exact number the accuracy section depends on, it shows a second scene where
   the references *do* agree (which helps the paper), and the PDF does not
   mention it exists.
3. **Surface the warm/two-row rates where the claim is made, not only in the
   final paragraph.** The matched charge injects on 4,099 of 43,898 warm and
   two-row cells and the index misses 2,795 of 19,730 true injections in the
   unsafe direction. Every reviewer credits the disclosure; every reviewer
   notes the abstract reads as an unconditional guarantee. This is an emphasis
   edit, not new work, and it is the single change that most reduces the risk
   of a hostile reviewer discovering it themselves.
