# Six-reviewer blind panel -- `onesweep_short.pdf` + `onesweep_scene_video.mp4`

**Date:** 2026-07-25
**Artifacts reviewed:** `paper/onesweep_short.pdf` (built 22:04, **6 pp** = approx. 5.3-5.5 pp of
content with the bibliography beginning in the left column of p. 6, so inside a 4-6 page limit
excluding references), `benchmarks/paper_fig/out/onesweep_scene_video.mp4` (**50.2 s, 1920x1080,
30 fps, single video stream, no audio track**, 1506 frames, two acts: act 1 side-by-side panels,
act 2 stacked panels).
**Protocol:** six independent reviewers, each given only the PDF and the supplementary video frame
set. No access to the repo, the LaTeX source, `NUMBERS.md`, prior committee reviews, prompts, or
each other's reviews. Personas differ by expertise. Every reviewer re-derived the theorems
independently; five ran their own numerical or exact-rational reimplementations of the one-sweep
projection.

---

## Verdict

| # | Reviewer expertise | Rec | Score | Conf |
|---|---|---|---|---|
| R1 | Position-based dynamics / real-time rigid-body solvers | **Weak Accept** | 6/10 | 4 |
| R2 | Model reduction / modal dynamics | **Weak Accept** | 6/10 | 4 |
| R3 | Contact mechanics / numerical optimization / meaning of "passive" | **Weak Accept** | 6/10 | 4 |
| R4 | Passivity and energy safety / co-simulation / haptics control | **Weak Accept** | 6/10 | 4 |
| R5 | Games practitioner / benchmarking methodologist | **Weak Accept** | 6/10 | 4 |
| R6 | Senior PC generalist (venue fit, framing) | **Weak Accept** | 7/10 | 4 |

**6 Weak Accept / 0 Reject. Mean 6.17/10. Median 6/10. Confidence 4/5 unanimous.**

**General advice: ACCEPT-leaning, conditional on printed-equation and printed-claim repairs.**
This is the first panel on this project with no dissent, and no reviewer challenged the paper's
central algebra: Thm 3.1, Thm 3.3's telescoping, the reduced-mass inelastic-loss identity, the
kappa-general boundary, the kappa = 2 arithmetic, the (1+b)^2 divisor and both relaxation boundaries
were each independently reproduced by all six. The accept is nevertheless contingent, for two
reasons the authors should not read past:

1. **Two reviewers independently derived the same closed form and both concluded that Prop. 3.4's
   add-on claim ("in addition one-sweep passive") is FALSE at the paper's own shipped kappa = 2.**
   No reviewer who checked it confirmed it. R1 and R3 produced the identical condition,
   `(kappa^2 + b)/(1+b)^2 > 2 + m/M`, from independent derivations, and both point out that the
   kappa = 1 case the paper says it cannot prove in closed form follows in one line.
2. **Three of six reviewers state the video moved them across a boundary.** R5: *"Before the video I
   was at a weak reject."* R3: *"Reading the PDF alone I was at weak reject leaning borderline."*
   R4: *"Yes, upward, from Borderline to Weak Accept."* The PDF alone does not carry the current
   tally. Anything that weakens the video's standing (arm selection, the missing index display, the
   undisclosed pre-impact divergence) is therefore load-bearing on the score.

**Score-versus-text consistency note.** Five of six reviewers list at least three weaknesses they
themselves label "major" and still recommend Weak Accept. That is not incoherent here: in every case
the "what would change my score" paragraph says an Accept is reachable with text-only changes, and
all six say explicitly that no headline claim failed their checks. R6 is the cleanest example
(*"I would not reject over anything I found: no headline claim failed my checks, and the theorems
reproduced to machine precision under adversarial parameter draws"*). The panel's majors are
repairs, not refutations. The exception worth naming: R5's stated downside condition
(*"Downward to reject (3-4) if the authors defend Eq. 6 as printed"*) and R4's
(*"Down to Weak Reject (4) if the quoted motivating sentence cannot be located in [6], since it
appears in the abstract"*) are both live, and both are decided by facts the authors can check today.

---

## Consensus findings

Ranked by how many reviewers independently found them. Cheap-to-fix items are marked **[text]**;
items needing a measurement or a re-render are marked **[work]**.

### 1. Table 1 does not reconcile with the prose -- 6 of 6 -- **[text]**

Every reviewer, without exception, tried to audit Table 1 and could not. The specific unreconcilable
cells are the same ones each time:

- **T10** is labelled with 9,900 attempted cells but reports an outcome of "300/300 exact", under a
  caption that says "Outcome is passing over attempted cells unless stated". R1, R2, R3, R4, R5, R6
  all flag this. R4: *"What happened on the other 9600?"*
- **T11** reports "8/8" while the prose for the same comparison cites 3,000 cells and a 32,000-arm-cell
  residual check (R1, R2, R3, R6). R6: *"T11's '8/8' is never explained while the body's 3000 cells
  appear in no table row."*
- The 2,000-row randomized coupled-stiffness experiment described on p. 3 corresponds to no table row
  (R3, R5).
- **T3** says 288/288 while the body says "all 288 **live** cells", implying an undocumented liveness
  filter (R5).
- **T6**'s outcome column (8/0/0) counts **injecting** cells, the opposite polarity from every other
  row (R1).
- The "sign" criterion is a 10^-9 dead band with no stated normalization, while the Tol. column shows
  10^-12 for the same rows, and the dead band silently sets every denominator in the table (R5).

**Why it matters:** the paper's principal evidential asset is that everything is machine-checked, and
Table 1 is where a referee goes to audit that. R2: *"a referee who catches one number that
contradicts its own figure will stop trusting the other cell counts."* R5 goes further and asks for
the table to be retitled: *"Retitle the table 'closed-form verification' and mark the three solver
rows (T4, T6, T9) as the only external evidence, so the reader is not invited to read eleven rows as
eleven independent tests."*

**Converged fix:** define every denominator and the dead-band normalization in the caption; make the
9,900 / 300 / 2,000 counts consistent or add a column saying what each subset is; state the liveness
filter; flip T6's polarity or mark it in the header. R3 and R5 additionally ask for a one-word
provenance column (new / shared with [3]).

### 2. Three quoted numbers silently assume m = M -- 6 of 6 -- **[text]**

The over-deposit factors "1.5 at b = 1, 51 at b = 10^2, 5001 at b = 10^4" follow from
`(M + m(1+b))/(M+m)` only at m = M, which the paper never states. All six reviewers derived the
formula, confirmed it, and independently noted the hidden operating point. R2 gives the alternative:
*"at m/M = 0.1 they are 1.09, 10.1, 910."* R4: *"at m/M = 0.5 they are 1.33, 34.3, 3334."*

Adjacent, same class: the damping coefficient "0.979 zeta omega h" has no stated operating point
(R3, R5, both note it also implies m = M given the paper's own `c = 2 zeta omega m`), and
"returns half the converged modal amplitude in the stiff limit" requires `m(omega h)^2 >> M` per R2.

**Fix:** add "at m = M" before the three factors, or give them as the formula. One clause.

### 3. Which coordinates carry the reconstruction factor kappa is never stated, and the diagnostic's boundary depends on it -- 4 of 6 -- **[text]**

R1 (rank 3 major), R2 (rank 1 major), R4 (rank 1 major), R5 (folded into rank 3). Three of them
independently generalized the derivation and arrived at the same expression. The paper's printed
results are recoverable only if kappa rescales the **restorative** block's velocity recovery while
the rigid side of the row is recovered at backward Euler.

- R1: *"my derivation gives a rigid-side term `-kappa_r*(2 - kappa_r)*w_r`, so if the symplectic
  implicit-midpoint reconstruction also applies to the rigid velocity (kappa_r = 2), that term
  vanishes and the mass-only kappa = 2 boundary becomes b > 0, not b > m/M - 2."* R1 measured the
  paper's boundary mispredicting 33 of 3,000 random cells under kappa_r = 2 (all with m/M > 2,
  predicted passive, measured injecting) and 0 of 3,000 under kappa_r = 1.
- R2: *"Reading B ... changes the headline boundary to `(omega*h)^2 * M/(M+m) > kappa(2-kappa)`, which
  at kappa = 2 has NO passive region for any mass ratio."* R2 measured 1908/2000 injecting cells at
  kappa = 3 under the uniform convention.
- R4: *"an implicit-midpoint host reconstructs `v+ = 2(x+ - x-)/h - v-` for the rigid body too"*, with
  an explicit counterexample: *"kappa = 3, M = 1 kg, m = 50 kg, omega h = 10 ... DeltaE = +1.50 J per
  sweep."* R4 measured 1422/2000 injecting at kappa = 3, 1648/2000 at kappa = 5.
- R5: *"the -w_r term is exactly where that assumption enters, and Thm 3.3's statement never says
  it."*

**These three derivations are mutually consistent, not contradictory.** R1 checked kappa_r in {1, 2}
and found the matched charge still strictly dissipative under both. R2 and R4 checked kappa > 2 and
found the matched charge can inject there. Read together: under a uniform host-wide reconstruction
the matched charge is passive for kappa in (0, 2] and can inject for kappa > 2, while the mass-only
boundary and the diagnostic change qualitatively at kappa = 2. R1 states the reassuring half
explicitly: *"The matched weight stays passive under either convention; the diagnostic does not."*

**Fix (all four converge):** state the convention per coordinate in Sec. 2 and inside Thm 3.3, print
the general `dE` with the `-kappa_r(2 - kappa_r) w_r` term, and tabulate the mass-only boundary for
`(kappa_r, kappa) = (1,1), (1,2), (2,2)`. One extra symbol and a three-row table. R1 adds that the
robustness of the matched charge across conventions is itself a result worth stating.

### 4. No cost, timing or per-row overhead anywhere, at a real-time venue -- 5 of 6 -- **[work, small]**

R1 (rank 8), R3 (rank 9), R4 (rank 7), R5 (rank 6), R6 (rank 8). R2 did not raise it.

R4 puts the sharpest version: *"The claim 'priceable before the solve' is a performance claim in
disguise."* R5: *"the guidance is asserted to be cheap rather than shown to be cheap."* R3 notes the
cheap shortcut is closed off by the paper's own data: *"the paper shows the diagonal shortcut breaks
Eq. (7) on 19 of 2000 coupled rows, so the cheap version is unsafe"*, and supplies the obvious
answer the paper never gives: for a fixed basis and fixed h, `G^-1` is one precomputation per body
per substep, since G does not depend on the row.

**Fix:** one paragraph. Per-row flop count for rho (a 2n-multiply dot product over engaged modes, per
R1) and for applying `(kappa^2 M_c + h^2 K_c)^-1` to `J_c^T`; a statement that the factorisation
caches; the machine; and one measured overhead number from the 27-cell runs. R6 notes the answer is
presumably "free", *"which is a selling point the paper leaves on the table."*

### 5. The practical delta over the already-published stiffness-aware weight is never shown at system level -- 5 of 6 -- **[work]**

R2 (rank 5), R3 (video, and a gating item in "what would change my score"), R4 (rank 2 major),
R5 (rank 7), R6 (rank 3). This is the panel's most expensive finding and the only one that is
structural rather than editorial.

On the 24-cell production grid the mass-only arm injects on 8, the kappa = 1 stiffness-aware weight
`(M_q + hD_q + h^2 K_q)^-1` on 0, and the reconstruction-matched weight also on 0. The separation
appears only in the isolated 27-cell row test, where the published weight injects on 12 of 27.

- R4: *"So the only novel ingredient is the kappa^2 factor, and no reported experiment shows a shipped
  operating point where a host needs it. That reduces the demonstrated practical contribution to a
  re-explanation of why an existing remedy works."*
- R2: *"a reader can reasonably conclude the published weight is the better engineering choice on the
  evidence shown."*
- R6: *"A practitioner asks: I already ship `(Mq + h*Dq + h^2*Kq)^-1` and it never injected on your
  24 cells, why change?"*
- R3 wants the third arm in the video: *"As shot, the video supports 'a stiffness-blind row weight is
  catastrophic here', not 'the matched weight is the necessary remedy'."*

**Fix, in descending order of cost:** (a) one system-level cell where the published weight injects
and the matched weight does not, which R4 and R6 both say would take the paper to Accept outright and
R6 says belongs in the abstract; (b) if none exists, say so in one sentence and reconcile 12/27
against 0/24 (the panel's own hypothesis is that the 27-cell sweep reaches rho far above shipped
values, which R4 asks the authors to confirm); (c) add the published arm to the video as a third
panel and to the T11 accuracy comparison, which R5 notes needs no new machinery.

### 6. The video demonstrates the weight, not the index the title leads with -- 5 of 6 -- **[work, small]**

R1, R2, R3, R5, R6. No frame in the video ever displays rho, rho_mid, or a predicted-versus-measured
sign, yet the closing card asserts *"One index per contact row, computable before the solve"*.

- R5: *"The video is evidence for the weight, not for the index."*
- R1: *"the evidence is for the weight (C1/C3), not for the index (C2), even though the end card
  asserts the index."*
- R6 makes it the difference between his 7 and an 8: *"Had the video shown rho predicted before the
  solve against the measured sign, or the shipped implicit weight as a third panel, I would have
  moved to Accept."*

**Fix:** one overlay per act showing rho or rho_mid for the coupled row and the measured sign, or
soften the closing card to claim only what is shown.

### 7. The paper omits the video's own 89x disclosure about the converged reference -- 6 of 6 noted, 3 ranked -- **[text]**

The video states, on the shelf scene, *"converged references disagree 89x: 9.6 mm at 1/960 s
substeps, 0.1 mm at 1/120 s"*. The paper quotes only the 9.6 mm and calls it a converged run.

- R4 (rank 5): *"Against the other grid the matched arm's 5.3 mm is 53x too large rather than 1.8x too
  small, so the reader's impression of how close the fix lands depends entirely on which reference is
  shown."*
- R1: *"which suggests book rise on the shelf is simply not converged in h and should not be an
  accuracy anchor at all."*
- R5 (rank 9): *"the honest reading of 'the matched weight returns half the converged amplitude' is
  'half of a quantity that is not itself converged in h'."*

Every reviewer credited the disclosure as honest and to the authors' advantage in the video; every
reviewer noted its absence from the PDF. R4: *"The supplement is more honest than the submission
here."* The table scene has no such problem (11.6 to 11.8 mm on both grids), which several reviewers
noted makes the omission look selective rather than accidental.

**Fix:** move the 89x line into Fig. 1's caption and the T11 paragraph, say which grid the reference
is taken on, and say plainly that T11 is converged in iterations at fixed h, not converged in h.

### 8. Paper and video quote different headline joules for the same run, and the paper gives no energy scale -- 6 of 6 -- **[text]**

Fig. 1 reports 1,707 J of board-mode energy at 114 ms. The video's readout for what appears to be the
same run peaks at 925,575 J against a disclosed 64.5 J of starting scene energy. The paper never
mentions the peak and never gives the scene energy, so the reader cannot scale 1,707 J at all.
Reviewers computed the drop input themselves (6 kg x 9.81 x 1.00 m = 58.9 J) and reported the ratios:
29x from the paper, 14,350x from the video (R1, R4, R6 all did this arithmetic independently).

R1 also flags an interpolation problem: *"the mass arm reads 1,917 J at about 85 ms and 1,870 J at
about 270 ms, yet the caption reports 1,707 J at 114 ms"*, and asks whether figure and video are the
same run. R6: *"a reader flipping between them sees a 542x discrepancy with no signpost."* R5 notes
Fig. 1 also pairs an instantaneous energy (114 ms) with a run-maximum rise (56.8 mm).

**Fix:** state the scene's total energy next to the joule figures, report the peak as well as the
114 ms value, say whether Fig. 1 and the video are the same run, and use one time convention per
panel.

### 9. Fig. 3 cannot be audited at print size, and three reviewers read three different cell counts out of it -- 6 of 6 -- **[work, figure]**

All six reviewers report Fig. 3 as the weak figure: three panels, three different x-axes carrying
three different indices, an inset, four marker shapes with fill semantics, roughly a dozen inline
annotations at 5-6 pt, and a caption that concedes *"Panel readouts and cell counts are in the
text"*. R2 and R6 both had to re-render the page at 400 dpi to read it. R3: *"for a figure carrying
the paper's only shipped-host numbers that is a real problem."*

The consequence is a genuine, unresolved disagreement over what the figure and body say (see
**Split opinions 2**): R2 reports the body transcribing an injecting count as a passive count
(a five-cell error), R6 reports body and figure reconciling once read at high resolution, and R5 read
a third set of counts. The panel cannot settle it from the artifacts.

**Fix:** move the panel readouts into the caption or a small table, split the figure or drop the
inset into prose, unstack the legend from the right panel's readout (R6 reports it physically
truncating the text), and print one definition of each index used identically in body, axis and
caption.

### 10. The framing quotation attributed to [6] could not be located, and the bibliography has date errors -- 4 of 6 -- **[text]**

R1, R4, R5, R6 each tried to verify the sentence *"offers no mathematical framework for predicting
when energy is added"*, in quotation marks in both the abstract and the introduction, and none could
find it at the cited source. R4 fetched both the Solver2D post and the repository: *"the post does
discuss energy creation ('it can lead to energy creation and jitter if not tuned carefully', 'There
can be a small amount of potential energy generation', 'the first call to SolveConstraints will add
extra energy') but not that claim about a missing framework."* R1 adds that the repository README
contains no occurrence of the word energy at all, and asks for a locator for the second quotation
attributed to [9] as well.

**Secretary's note the authors should act on directly:** the three reviewers who reported a year for
[6] reported **three different years** (R1: 2022; R4: 2012; R5: no year, no venue, no URL). R6
separately reports [5] dated 2019 for what is GDC 2005, and R5 reports "Ssamak Arbatani" for Siamak
in [11]. Either the entry is hard to read or the reviewers transcribed differently; check the
`.bib` directly rather than trusting any one report.

**Why it matters (R4):** *"A direct quotation that carries the paper's motivation must be locatable."*
This is R4's stated downgrade trigger.

**Fix:** give a resolvable pointer (URL plus section) or drop the quotation marks and make the
observation in the authors' own voice; correct the year to 2024; fix [5] and [11].

### 11. The theorems are cold-start and single-row while the deployment is warm, multi-substep, multi-row and gravity-preloaded -- 5 of 6 -- **[text]**

R1 (rank 4 major), R2 (rank 9), R3 (rank 8), R5 (rank 8), R6 (rank 9 as a rhetoric item). All five
credit the scope box, and all five say the bridge to the scenes is never stated in one place.

- R1: *"The abstract reads 'makes one sweep lose exactly a perfectly inelastic impact and stay passive
  for every kappa', which a skimming practitioner will take as a passivity guarantee for the shipped
  loop. It is not one: it is a cold-start, single-row, single-sweep guarantee plus 78 measured cells."*
- R3 adds a hypothesis nobody else caught: *"a gravity-preloaded shelf has q != 0, so the shipped
  scenes violate the cold start from t = 0, not just after the first impact."*
- R2: *"Hosts in the room run 4-8 iterations with warm starts and many simultaneous rows."*
- R5: *"one active row is not the case a shipping title has."*

**Fix:** one short paragraph at the head of Sec. 4 stating what the theorems cover, what the scenes
are, and that the connection is measured sign agreement plus the rho_mid correction; plus one
sentence in the abstract. R1 asks additionally how many of the 8 substeps are cold in the reported
runs.

### 12. The host is described as "production"/"shipped" without support, its scenes and two of three arms come from an unreadable companion, and the "passivity governor" is disabled everywhere and defined nowhere -- 6 of 6 touch it, 2 make it top-2 -- **[text, mostly]**

- **Companion entanglement (6 of 6):** R1 (rank 7), R4 (rank 6), R5 (rank 2), R6 (rank 9), R2 and R3
  in passing. All six credit the disclosure paragraph as the right form. R1: *"A short paper is
  allowed to be narrow, but it must be judgeable on its own."* R4: *"if [3] is rejected this paper's
  system corroboration loses its documented context."* R6 is the only reviewer to rule on the salami
  question and rules in the paper's favour: *"the split is theory versus system diagnostic rather
  than results salami, and it is disclosed in a dedicated paragraph."* R1 and R4 leave it open.
- **Unearned words (R2 rank 2, R5 rank 2):** R5: *"At a games venue those words carry real weight and
  should not be used loosely."* R2: *"The host is described only as 'a production position-based
  support solver' and shares its scenes with a companion submission, which reads as the authors' own
  research code rather than a shipped engine."*
- **The kappa = 2 premise has no citation (R2 rank 2, major):** *"The standard position-based
  reconstruction in the literature the paper itself cites ([14] XPBD, [17] rigid XPBD) is
  `v = (x+ - x-)/h`, i.e. kappa = 1, and I could not find a documented kappa = 2 host convention."*
  R2 notes the consequence: *"If most hosts reconstruct at kappa = 1, then the published remedy is
  already correct and this paper's new weight is unnecessary in practice."* This is R2's stated
  downgrade trigger.
- **The governor (R3 rank 10, R5 rank 2):** never defined, default state never stated, off for every
  reported result including the teaser. R3: *"The first question from the room will be 'why not leave
  the governor on?'"* R5: *"If the host ships that governor on, the headline demo is a configuration
  the host would never run."*

**Fix:** rename to "our research host" or name a third-party engine; define the governor in one
sentence with its default and report one cell with it on; either cite a host that reconstructs at
kappa = 2 or reframe as "hosts that recover velocity at any kappa != 1"; make the 27-cell test fully
self-describing so Sec. 4 stands without [3].

### 13. No per-scene parameters are reported, so no system-level number is traceable -- 4 of 6 -- **[text]**

R5 makes it his rank 1: *"the entire theory is parameterized by (omega h, m/M, kappa, theta,
alpha-tilde), and the paper's own phase map has those axes. Yet for the shelf, ledge and dinner
scenes we are never given m, M, omega_i, the mode count, the contact tolerance, or the rho and
rho_mid values of any cell ... I cannot place Fig. 1's 1,707 J on Fig. 2."* R1 and R4 ask for the
same thing as the fix to their companion-entanglement items. R2 asks for the missing half-page that
makes the index computable at all: *"m = m_i/U_i^2 with U_i = phi_i^T n, so m = 1/(phi_i^T n)^2 for
mass-normalised modes"*, plus the note that rho must be evaluated on the **retained** basis (R2
verified that adding a retained mode raises rho exactly when the added mode's `(omega_i h)^2` exceeds
the current rho).

**Fix:** one small table of per-scene parameters and per-cell rho / rho_mid, and two sentences mapping
a modal basis onto the paper's m. R2 also asks that "mass-normalized weight" be renamed "mass-only
weight" throughout, since in modal analysis mass-normalised means `phi^T M phi = 1` and the clash is
with the paper's own subject matter.

### 14. Budget notation and the relaxation set are undefined or internally inconsistent, and the teaser's operating point is off the grid -- 3 of 6 -- **[text]**

R1 (rank 5), R4 (rank 9), R5 (rank 10). "Four iteration-substep budgets (4, 1), (8, 2), (16, 4),
(32, 8)" is never expanded in either order. R1: *"under (iterations, substeps) they are 4 to 32
iterations, under (total, substeps) they are a constant 4 per substep ... this is a fixed-budget
paper, so the budget is the central independent variable."* The video's and Fig. 1's operating point
(1 iteration x 8 substeps) is none of the four, which all three flag.

The relaxation set is read differently by two reviewers: **R4 reports the paper printing "two
relaxations theta in {0, 0.7, 1.0}" (three values named)**, **R5 reports "two relaxations theta in
{0, 1.0}"**. Both note the same arithmetic problem: 24 = 3 scenes x 2 relaxations x 4 budgets needs
exactly two values, and if theta = 0 literally zeroes the modal correction then those cells cannot
inject by the paper's own theta^2 scaling, so 12 cells in the denominator are trivially passive.
R4: *"that cell is trivially passive and should not be counted."*

**Fix:** expand the notation once, print the two theta values, explain how a theta = 0 cell can
inject, and either add the (8, 1) cell the teaser uses or say why the teaser is off-grid.

### 15. The diagonal-only-charge warning (19 of 2000) is not reproducible, and two reviewers independently derived the sharp criterion -- 3 of 6 attempted -- **[text]**

R1, R2 and R3 all attempted it. **Nobody reproduced the rate.** R1: 0 of 4,504 rows across two
ensembles. R2: 0 of 3,000. R3: 1 of 2,000 (*"same order but the ensemble is unspecified"*).

R1 and R2 then independently proved the same sharp statement: with `W = diag(G)^-1` the condition
reduces to a quadratic form in the normalized charge matrix
`A = diag(G)^-1/2 G diag(G)^-1/2`, which has unit diagonal and is PD, so injection requires
`lambda_max(A) > 2`, **impossible for n <= 2**. R1 then reproduced injection at n = 3, 4 and 6 with a
rank-one all-ones `K_c` (+58.5, +114.9, +180.4); R2 constructed an injecting instance at n = 3 with
off-diagonals 0.9.

R1's framing of why the sharpening is better than the rate: *"As stated it sounds like a 1% risk in
general; in fact it is a zero risk below three coupled coordinates and a real risk above, which is a
more useful thing to tell me."* R2 adds the scoping note the paper should carry: in a mass-normalised
modal basis `K_c` is diagonal, so the warning applies to non-modal reduced bases only.

**Fix:** state the ensemble, and replace the rate with the criterion.

### 16. Fig. 2's caption never states kappa, so the memorable figure describes an operating point the shipped host does not use -- 3 of 6 -- **[text]**

R2, R4, R6. The drawn boundary `(omega h)^2 = 1 + m/M` is the kappa = 1 case. R6: *"at kappa = 2 the
left panel is red almost everywhere ... a reader will carry away the wrong map."* R6 adds that the
right panel at zeta = 0 **is** Thm 3.3's matched weight, which the caption also does not say. R4 asks
for zeta and for an identification of the unexplained black curve in the right panel. R2 notes the
colour is a relative energy change, so the injecting region at small m/M is nearly invisible even
where the sign is correct, and suggests a sign-only inset.

### 17. Missing hypotheses on the exactness claim: zeta = 0 -- 2 of 6, both agreeing exactly -- **[text]**

R2 (rank 10 minor) and R3 (rank 2 major) both derived the damped converged charge as
`m(1 + 2 zeta omega h + b)` and both point out the abstract's *"at kappa = 1 it reproduces the
converged implicit contact step exactly"* holds only at zeta = 0, while Sec. 2 explicitly gives the
mode a damper. R2 quantifies: *"for a stiff mode with omega*h = 10 and zeta = 0.02 the quoted
0.979*zeta*omega*h relative gap is around 20 percent, not negligible."* R3 quantifies the other
regime: *"At zeta = 0.05, omega*h = 0.31 the charges differ by 2.9%."* Both note Eq. (7) itself is
genuinely zeta-independent, as the paper claims, because the cold predictor is inert.

R3 asks for a full hypotheses list on Thm 3.3 (cold start, active row with lambda >= 0, inert
predictor, `w_r > 0` for strictness) and for the conclusion to be split into (i) Eq. (7), valid for
any zeta, and (ii) exactness against the converged step, valid at kappa = 1 and zeta = 0.

### 18. Two reviewers offer sharpenings the paper could adopt at no cost -- 2 of 6 -- **[text]**

Both are verified by their proposer and neither is in the paper.

- **R3's passive set.** From the paper's own Eq. (6) at alpha = 0, a scalar charge is non-injecting
  iff `mu >= M(sqrt(1 + G/M) - 1)`, with `G = m(kappa^2 + b)`; 0 misclassifications in 20,000 random
  cells. Since `sqrt(1+g) - 1 < g`, the matched charge is strictly interior to the passive set, and
  far interior when `G >> M`. R3: *"the paper concedes the matched charge over-dissipates at kappa = 2
  and then offers the practitioner only 'iterate, decouple, or accept it'. The one-line threshold
  above gives a third option."*
- **R2's impossibility result.** At kappa = 2 the amplitude-accurate charge `m(1 + b/4)` injects iff
  `m(1 + b/4) < 2M` (0 mismatches on 4,000 cells), so at the shipped kappa there is provably **no**
  charge that is both passive and amplitude-accurate whenever the converged modal charge is below 2M.
  R2: *"That single line would state the paper's 'passive but conservative' trade-off as a theorem
  instead of an observation."*

R1 offers a third, framed as a question rather than a result: reconstruct only the modal coordinates
at kappa = 1 while the rigid host keeps its midpoint reconstruction, which by Thm 3.3 is both passive
and exactly the converged BE step, removing the 4x over-charge and the 2x amplitude loss. R1: *"it is
the first thing I would try."*

### 19. Single-reviewer findings the authors should still act on

Each of these was raised by exactly one reviewer, in each case the reviewer whose expertise is
closest to the item.

- **"Passive" is used for a one-transition energy sign (R3, rank 3 major).** *"What is proved is the
  sign of one energy difference along one transition from one initial state. That is neither
  passivity (a storage inequality for all admissible states and inputs) nor stability."* R3 counts
  roughly 30 uses, including inside theorem statements and on figure panels, and notes that ref. [24],
  which the paper cites, proves passivity in the strict sense. Proposed rename: "one-step
  non-injecting" or "one-sweep dissipative". **Note: R4, the panel's other passivity specialist,
  did not object to the vocabulary and treated the scoping as adequate.** See Split opinions 4.
- **The haptics discrete-passivity literature is absent, making a printed sentence false (R4, rank 3
  moderate).** The sentence *"Energy-sign framings of coupling error exist as runtime residuals ...
  again not parametric thresholds"* is false once Colgate's sampled-data condition `b > KT/2 + B` and
  time-domain passivity control are in scope. R4 checked: no haptics or passivity-control reference
  appears in the 25 entries. R4 also supplies the honest reframing at no cost to the contribution:
  *"the haptics thresholds buy passivity by spending physical damping at a bilateral port, which a
  unilateral hard contact row does not have."*
- **The predictor-side damper is not unconditionally non-positive (R2, rank 6 moderate).** An explicit
  update `qdot <- qdot(1 - 2 zeta omega h)` increases modal energy when `zeta omega h > 1`, reachable
  in the paper's own stiff regime. *"In the corner where zeta*omega*h > 1 the predictor is the
  injector and the projection bound no longer covers the step."* Fix: say the damper is implicit, or
  add the condition.
- **Geometric-stiffness misattribution (R2, rank 7 moderate).** *"In both cited works geometric
  stiffness is the tensor `d(J^T lambda)/dx` ... `M + hD + h^2 K` is the linearly-implicit system
  matrix, a different object."* Note R6 read the same sentence and judged the attribution correct;
  see Split opinions 5.
- **The mechanism by which iterating fixes the problem is never named (R3, rank 7 moderate).**
  *"A reader cannot reconcile 'one sweep already zeroes the residual at any weight' with 'eight sweeps
  are passive'."* R3 asks whether it is accumulated lambda through alpha-tilde, the other rows, or the
  modal predictor, and suggests retitling around the reconstruction rather than the budget.
- **The compliance energy convention is unstated (R4, rank 10 minor).** If the regularising row's own
  stored energy `(1/2)(C+)^2/alpha` is counted, the shifted boundary is `rho > 1 + alpha/w_m`, half
  the printed offset; the two conventions disagree in sign on a band (R4: at `alpha = 0.3 w_m`,
  `rho = 1.4`, `-0.030` versus `+0.015`). R4 notes Prop. 3.4 uses the opposite reading of an
  alpha-tilde row from the one Eq. (2) implies.
- **Fig. 3's middle annotation inverts necessary and sufficient (R6, rank 4 minor).** *"'passive only
  where 2(w_row - w_r) <= w_r' states a necessary condition when the paper's own boundary makes it
  only sufficient"*, with a counterexample (M = 1, m = 0.1, b = 3: the condition fails yet the row is
  passive). *"As printed the annotation licenses the wrong pre-solve conclusion."* Fix: "only where"
  becomes "wherever". One word.
- **Fig. 1's caption overstates its own measurement (R4 rank 8, R5 rank 12).** *"throws the five
  resting books 56.8 mm off the shelf"* against a video readout of "highest book lifted so far", a
  cumulative maximum over one book, with no book leaving the shelf in any frame R4 read. R4: *"This
  is the teaser sentence of the paper and it is the one sentence contradicted by the paper's own
  supplement."*
- **The Courant distinction undercuts itself (R4, rank 11 minor).** The paper says *"for m << M the
  boundary is omega h = 1"* two sentences before saying the `1 + m/M` offset distinguishes it from a
  Courant limit at `O(1)`. R4: *"the honest claim is 'we sharpen a folklore O(1) limit into an exact
  per-sweep constant with a mass-ratio offset and a reconstruction factor'."* Note R1 credits the
  offset as genuinely distinguishing; see Split opinions 6.
- **Proof typo.** Thm 3.1's reconstruction step is printed as `qdot+ = h qddot+` (R4) or
  `qdot+ = h qdot+` (R6) where `q+ = h qdot+` is meant. Two reviewers, two transcriptions, same
  location; check the source.

---

## Independent math verification

This is the section the authors should read first. The panel re-derived essentially the whole paper,
mostly in exact rational arithmetic and with independent reimplementations of the one-sweep
projection. **What survived is listed as CONFIRMED with the reviewers who got there independently.
What did not survive, or could not be checked from the PDF, is called out explicitly.**

| # | Claim | Attempted by | Verdict | Notes |
|---|---|---|---|---|
| 1 | Thm 3.1: `E+` closed form (Eq. 3) and boundary `(omega h)^2 > 1 + m/M` | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R1 0 sign mismatches / 4,000 exact-rational cells; R3 0 / 20,000; R6 max rel. err. 1.2e-15 / 20,000; R5 crossing located at `b* = 1 + m/M` to full precision at m/M = 0.01 to 100 |
| 2 | Eq. (6), the general one-sweep energy change: **correct form** | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | All six derive `dE = (v^2/2D^2)[u'Gu - w_r - 2 J_c'u - 2 alpha]`. Unanimous on the mathematics |
| 2b | Eq. (6) **as typeset**: is the `-w_r` term printed? | R1 R2 R3 R4 R5 R6 | **DISPUTED 4-2** | R2 R3 R4 R6 say present; R1 R5 say absent. R6 explicitly: *"I first mis-read the -w_r term as absent from a low-resolution text extraction; a 400 dpi render of the equation shows it is there."* See Split opinions 1 |
| 3 | Thm 3.3: `W = G^-1` telescoping, Eq. (7), strict negativity for every kappa != 0 | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R1 600 exact-rational blocks n = 2,3 with off-diagonal `K_c`, kappa in {1,2,3}; R3 4,000 cases n = 1..4, 5.2e-14, kappa in {-2,-1,0.5,1,2,3.7}; R5 20,000 draws, 2.2e-12; zero injecting cells anywhere |
| 4 | Eq. (7) at alpha = 0 equals the reduced-mass inelastic shock loss `-(1/2)[M m_row/(M+m_row)]v^2` | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R5 1e-16 relative; R4 7e-14; R3 calls it *"the cleanest result in the paper"* |
| 5 | Thm 3.2: Eq. (4)/(5) and the exact identity `y = 2 dE w_m/v^2 = rho - 1` | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R5 verified symbolically; R2 2,000/2,000 exact; R1 checked on 2-, 3- and 4-mass chains with off-diagonal K |
| 5b | Thm 3.2's printed definition of `b_i` | R2 R3 | **DISAGREES 2/2 attempted** | Both say the printed line is wrong and both give the same correction `b_i = (omega_i h)^2 = h^2 k_i/m_i`. R2: Eq. (4) fails 1944/2000 with the printed definition, exact 2000/2000 with the correction. R3: on a 3-mode example `L = 6.7038` but `sum a_i b_i = 42.73` with the printed definition. **They report slightly different printed forms** (R2 without `h^2`, R3 with), so check the typeset line. R1 R4 R5 R6 silently used the correct form and did not flag it |
| 6 | kappa-general boundary `kappa^2 + (omega h)^2 = 2 + m/M`, and `b > m/M - 2` at kappa = 2 | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R6 0 misclassifications / 40,000 over kappa in [0.2, 4]; R3 0 / 60,000; R5 located the m/M = 2.5 transition at b = 0.5 |
| 7 | Matched charge `m(4+b)` at kappa = 2 | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | Direct from `G = kappa^2 m + h^2 k` |
| 8 | Backward-Euler weight on a kappa = 2 host injects iff `M(2-b) > m(1+b)^2` | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R1 0 / 4,000; R6 0 / 40,000; R2 notes it confines the failure to `b < 2`, consistent with the abstract |
| 9 | `rho_mid = (L + 2 sum a_i)/(w_r + 2 alpha)` as the kappa = 2 index | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R4 confirms the paper's remark that `sum a_i` moves from denominator to numerator so this is not a rescaling of rho; R3 confirms `rho_mid >= 2M/m` for a single mode at alpha = 0; R2 proves in one line that `rho_mid >= rho` always, so misses can only be false negatives |
| 10 | Prop. 3.4: ordering divisor `(1+b)^2`, and 10201 at b = 100 | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R5 exact rationals at b = 1, 100, 37/7; R1 400/400 random cells at kappa = 1 and 2; kappa-independent |
| 11 | Prop. 3.4's add-on: order A `[contact, spring]` is "in addition one-sweep passive" | R1 R3 | **DISAGREES 2/2 attempted, 0 confirmed** | Both derive the identical closed form: order A injects iff `(kappa^2 + b)/(1+b)^2 > 2 + m/M`. Passive unconditionally at kappa = 1 (a one-line proof the paper says it does not have); fails at kappa = 2 for `b < 0.1805` at m = M, `b < 0.4568` at m/M = 0.1, never for m >= 2M. R3: 4,936 of 20,000 cells inject at kappa = 2, 0 of 20,000 at kappa = 1. Worked counterexamples: R1 M = m = 1, b = 0.01, v = -1 gives `dE = +0.116`; R3 M = 15.43 kg, m = 0.642 kg, b = 4.0e-4 gives `dE = +0.58 J`, 7.5% of `E-`. **R2, R4, R5, R6 confirmed the divisor but did not test the passivity side claim** |
| 12 | Relaxation boundaries `theta^2(kappa^2 + b) = 2 + m/M` and `L > (2/theta - 1) w_m` | R1 R2 R3 R4 R5 R6 | **CONFIRMED 6/6** | R3 0 / 40,000 each; R6 0 / 20,000 each; all confirm monotonicity, so under-relaxation can only move injecting to passive (T8's "0 unsafe flips") |
| 13 | At kappa = 1 the matched sweep reproduces the converged backward-Euler contact step exactly | R1 R2 R3 R5 R6 | **CONFIRMED 5/5 attempted, with a hypothesis the paper omits** | R3 agrees to 8.9e-16 across impulse, rigid velocity, modal amplitude and modal velocity for n = 1..4 with dense `M_c`, `K_c`; R5 and R6 to 12 digits. R2 and R3 both add that this requires **zeta = 0**: the damped converged charge is `m(1 + 2 zeta omega h + b)`. R4 did not check |
| 14 | "its charge m(4+b) being exactly four times the converged implicit-midpoint charge m(1+b/4), so it returns half the converged modal amplitude in the stiff limit" | R1 R2 R3 R5 R6 (R4 could not) | **SPLIT: 2 confirm, 2 disagree, 1 confirms-with-caveat-and-rejects-the-inference** | See Split opinions 3. Nobody disputes that the paper's converged reference is never written down, and all five say it must be |
| 15 | Over-deposit factor `(M + m(1+b))/(M+m)` and the values 1.5 / 51 / 5001 | R1 R2 R3 R5 R6 | **CONFIRMED as a formula 5/5; the three values require m = M, which is unstated** | R1 derived `q+ = h v/(mu w_r + 1)`; R2 gives 1.09 / 10.1 / 910 at m/M = 0.1 |
| 16 | "charging only the diagonal of G ... injecting on 19 of 2000 randomized coupled-stiffness rows" | R1 R2 R3 | **NOT REPRODUCED 0/3; direction confirmed; sharp criterion derived twice independently** | R1 0/4,504 across two ensembles, R2 0/3,000, R3 1/2,000. R1 and R2 both prove injection requires `lambda_max(diag(G)^-1/2 G diag(G)^-1/2) > 2`, impossible for n <= 2. R1 reproduces at n = 3, 4, 6 with rank-one all-ones `K_c` |
| 17 | Whether the theorems hold under a **uniform host-wide** reconstruction (kappa on the rigid side too) | R1 R2 R4 (R5 flagged, did not run) | **THE PAPER IS SILENT; three independent derivations agree** | General form `dE = (v^2/2D^2)[u'Gu - kappa_r(2-kappa_r) w_r - 2 kappa_r(J_c'u + alpha)]` (R1), equivalently injection iff `L > kappa(2-kappa) w_m` for mass-only weights (R2, R4). At kappa = 2 the `w_r` term vanishes and every coupled cell injects (R2 2000/2000, R4 2000/2000). Matched charge: passive for kappa in (0, 2] under either convention (R1: worst `dE` -0.49 at `kappa_r` = 1, -1.0e-5 at `kappa_r` = 2), **can inject for kappa > 2** (R2 1908/2000 at kappa = 3; R4 1422/2000 at kappa = 3, 1648/2000 at kappa = 5) |
| 18 | Prop. 3.4's load-bearing premise: the converged step is itself dissipative, including at kappa = 2 | R3 | **CONFIRMED (1 attempt)** | 0 injecting cells of 200,000 log-uniform samples with omega h in [1e-1, 1e5]. R3: *"this is not obvious at kappa = 2 because implicit midpoint is energy-conserving for the unconstrained spring ... so the framing is sound"* |
| 19 | R3's addition: exact passive set for a scalar charge, `mu >= M(sqrt(1 + G/M) - 1)` | R3 | **CONFIRMED (1 attempt)** | 0 misclassifications / 20,000 cells with mu over eight decades; reduces to `kappa^2 + b > 2 + m/M` at mu = m. Not in the paper |
| 20 | R2's addition: at kappa = 2, `m(1 + b/4)` injects iff `m(1 + b/4) < 2M`, so no charge is both passive and amplitude-accurate in that regime | R2 | **CONFIRMED (1 attempt)** | 0 mismatches / 4,000. Not in the paper |
| 21 | Fig. 3 middle annotation "passive only where `2(w_row - w_r) <= w_r`" | R6 | **DISAGREES (1 attempt)** | Necessary/sufficient inverted; counterexample M = 1, m = 0.1, b = 3 satisfies `2(w_row - w_r) = 5 > w_r = 1` yet `M(2-b) = -1 < m(1+b)^2 = 1.6`, so the row is passive |
| 22 | Basis-invariance of rho under mode rescaling; dependence on the retained basis | R2 (R4 confirmed basis-freeness) | **CONFIRMED** | `a_i` and `a_i b_i` invariant under `U -> cU, m -> c^2 m`. R2 additionally verified that adding a retained mode raises rho exactly when its `(omega_i h)^2` exceeds the current rho, so the truncation choice sets the index. Not in the paper |
| 23 | Compliance shift `rho > 1 + 2 alpha/w_m` | R1 R2 R3 R4 R5 | **CONFIRMED under the paper's Eq. (2) convention** | R4 shows the alternative convention (counting the regularising row's stored energy) gives `rho > 1 + alpha/w_m`, and the two disagree in sign on a band |
| 24 | Internal arithmetic: 241^2 = 58,081; (1+100)^2 = 10,201; 3x9 = 27; 3x2x4 = 24; 288/288; 24x3 = 72 | R1 R2 R3 R4 R5 R6 | **CONFIRMED** | All consistent across abstract, Sec. 4, Table 1 and the figures |
| 25 | Table 1 T10 (9,900 vs 300/300), T11 (8/8 vs 3,000 cells), T3 (288 "live"), T6 polarity | R1 R2 R3 R4 R5 R6 | **CANNOT BE RECONCILED FROM THE PDF 6/6** | See Consensus 1 |
| 26 | Whether Fig. 1's 1,707 J and the video's 925,575 J peak describe the same run | R1 R2 R3 R4 R5 R6 | **CANNOT BE CHECKED FROM THE PDF** | Paper gives no scene-energy scale and no peak; R1 additionally cannot interpolate 1,707 J at 114 ms between the video's 1,917 J at ~85 ms and 1,870 J at ~270 ms |
| 27 | Body-versus-figure shelf cell counts for the backward-Euler-shaped weight | R2 R5 R6 | **THREE READINGS, UNRESOLVED** | See Split opinions 2 |
| 28 | Fig. 3's `rho_mid` axis label against the body definition | R1 R2 R5 R6 | **2 could not reconcile, 2 confirmed after re-rendering at 400 dpi** | R2 and R6 both read the label as `[L + 2(w_row - w_r)]/(w_r + 2 alpha)` and both confirm it equals the body definition since `w_row - w_r = sum a_i`. R2 explicitly retracts an earlier low-resolution read. R1 and R5 could not reconcile it and R5 says *"the type is too small for me to be certain, which is itself a finding"* |
| 29 | The quoted sentence attributed to [6] | R1 R4 R5 R6 | **COULD NOT VERIFY 0/4** | See Consensus 10 |
| 30 | Existence and characterisation of refs [24] (Wei et al., arXiv 2603.16424) and [25] (You/Zheng/Li, arXiv 2602.08094) | R1 R2 R3 R4 R6 | **CONFIRMED 5/5** | All five confirm both exist and that the paper describes them accurately, including that [24] is bilateral, budget-agnostic and a genuine passivity certificate. R2 and R3 note [24]'s author list and title are garbled in the bibliography |

**Summary of the verification result the authors should quote in a response letter:** of the 13
distinct closed-form claims the paper makes, **11 were independently reproduced by every reviewer who
attempted them, most in exact rational arithmetic**, with zero sign misclassifications across
hundreds of thousands of random parameter cells. **One printed side claim (Prop. 3.4's passivity
add-on) was contradicted by both reviewers who tested it, with identical closed forms and worked
counterexamples.** One printed statement (the kappa = 2 accuracy sentence) split the panel because
the reference it compares against is never written down. Everything else on the failure side is
bookkeeping, legibility, or an unstated hypothesis.

---

## Video assessment

**What the panel thinks it proves.** Two acts (act 1 approx. 0 to 12.5-14 s, side-by-side panels,
steel cantilever shelf, E = 200 GPa, 30 mm, 6 kg dropped 1.00 m; act 2 approx. 13-15 s to 49 s,
stacked panels, dinner table, E = 1.1 GPa, 5 kg dropped 0.80 m), each two independent runs of one
host from identical states at 1 iteration x 8 substeps per 1/120 s frame with modal relaxation 1.0 and
the passivity governor off, differing **only** in the modal contact row's weight. It proves the
weight claim (C1/C3) on a real solver in two scenes, and it proves that the visible failure is
carried by the deforming body rather than by direct contact. It does **not** exercise the index (C2),
the ordering divisor (C4), or the relaxation boundary.

Three reviewers independently noted the act boundary is near 12.5-15 s, not the 22 s the frame-set
description implied, so act 2 occupies roughly 70% of the runtime and much of it is static (R2: the
table's matched arm sits at 7.6 mm from about 175 ms to the end; R6: *"about 50 s for two beats, with
act 2 nearly static from about 31 s to 46 s"*).

**Controlled: yes, on the axis it claims, and the panel says so unanimously.** The two controls the
reviewers most valued are (a) the disclosed geometric clearance (125 mm on the shelf, 85 mm on the
table) which forecloses direct impactor-to-prop contact, and (b) the budget grading printed on
screen (shelf: 2x8 still gains 151,140 J, 4x8 gains 856 J, first vanishes at 8x8; table: 3.2 J at
2x8, gone at 4x8), which forecloses the "this is just under-iteration" objection. R1: *"the
budget-grading line pre-empts the obvious objection ... and independently corroborates the paper's
claim that passivity arrives at roughly four to eight iterations."* R2 credits the clearance controls
as *"the only possible transmission path"*.

**Disclosure: the panel's unanimous verdict is that the video's disclosure exceeds the paper's.**
R1: *"The best I have seen on a supplementary video at this venue, and the main reason my confidence
is 4 rather than 3."* R3: *"the best-controlled and best-disclosed supplementary material I have
reviewed this cycle."* R4: *"This is the standard supplements should be held to."* On screen in every
frame: operating point, relaxation, governor state, material and thickness, drop mass and height,
clearance, 32x slow motion with one captured substep per video frame, the 0.9 s freeze announced as
"the same frame 28 times", "independent runs, nothing toggled mid-trajectory", "offline CPU float64,
no real-time claim", per-scene converged references, and a total-scene-energy plot with the run's
starting value drawn as a reference line so the reader can compute the overrun. R1 verified the 32x
factor is self-consistent with the clip length; R6 verified it arithmetically
(8 x 120 = 960 substeps/s captured one per frame at 30 fps).

Two disclosures **against the authors' interest** are in the video and not in the paper, and every
reviewer credited them: the 89x substep disagreement of the shelf's converged reference, and the
budget grading that shows the effect decaying by 4x8.

**Problems the panel found, in order of how many raised them:**

1. **The index is never shown (5 of 6).** See Consensus 6.
2. **Only two of three arms (4 of 6: R2, R3, R4, R5, and R6 in his rank 3).** The already-published
   stiffness-aware weight, which the paper itself reports as injection-free on all 24 system cells,
   never appears. R4: *"this video isolates 'stiffness-aware weight vs mass-only weight', not
   'reconstruction-matched kappa^2 weight vs any stiffness-aware weight'. It therefore supports a
   weaker claim than the paper's headline."*
3. **Pre-impact divergence between the two arms (2 of 6 flagged it as a problem; a third recorded the
   numbers without comment).** At 0.5 s, with the impactor still airborne and both arms reading
   0.0 mm of prop lift, the mass arm already reads 65.2 J of board-mode energy against < 0.001 J for
   the matched arm, and R1 reports the total-energy trace visibly oscillating above the 64.5 J start
   line before t = 0. R1: *"either that readout is mislabelled (65.2 J is suspiciously close to the
   64.5 J whole-scene figure) or the resting books alone are already charging the shelf mode, in
   which case the two arms are not in the same state when the impactor lands."* R2 reaches the same
   conclusion: *"the divergence therefore predates the impact."* R1 notes only the second reading is
   consistent with the pre-impact oscillation, *"and it is the more interesting one"*, because Sec. 6
   lists secular growth from resting contacts as open. **This is the one question the video raised
   that no reviewer could settle from the materials, and R1 lists it as a downgrade trigger.**
4. **The matched arm visibly under-responds against the converged reference in both scenes** (5.3 vs
   9.6 mm shelf; 7.6 vs 11.6-11.8 mm table). All six noted it; all six also noted this is exactly the
   paper's own admission, honestly shown. R3: *"the remedy trades one error for a smaller opposite
   one."* R6: *"the video therefore supports the paper's honest weaker claim, 'passive and
   conservative, not accurate'."*
5. **Fig. 1's caption is contradicted by the video's own readout** (R4, R5): "throws the five resting
   books 56.8 mm off the shelf" against "highest book lifted so far 56.8 mm".
6. **Mixed instantaneous and running-maximum readouts** invite the misreading Fig. 1 then commits
   (R2, R5).
7. **No timing, no audio, single seed per scene, "no real-time claim"** (R1, R3, R4, R5, R6). Honest,
   and a venue-fit problem.

**Did it move recommendations? Yes, three times, and all three upward across a boundary.**

- **R5: weak reject to weak accept.** *"Before the video I was at a weak reject: correct-but-narrow
  theory whose only system-level evidence was an invisible in-house host described with unearned
  words."* R5 also reports the video independently corroborating his own derivation that the matched
  charge is twice, not four times, the converged midpoint charge.
- **R3: weak reject leaning borderline to weak accept.** *"The video is the best-controlled and
  best-disclosed supplementary material I have reviewed this cycle ... That moved me to weak accept.
  It did not move me further, because it demonstrates the motivation rather than the theorems."*
- **R4: borderline to weak accept.** *"Act 2 answers that: a sixteen-item multi-contact table at the
  shipped budget ... in which the mass-only weight topples a candle and the matched weight does not.
  That is the evidence the theory section cannot supply."* R4 adds: *"on the strength of the video I
  believe the shipped-host claims, which is not something I could have said from the PDF."*
- R1 and R2 held their letter grade with raised confidence. R1: *"Weak Accept held with higher
  confidence, not upgraded."* R6 held his score and raised confidence: *"it is the reason I trust the
  system-level paragraph despite that grid being borrowed from the companion."*

---

## Split opinions

The panel genuinely disagreed in six places. None is manufactured and none is papered over.

### 1. Is the `-w_r` term actually printed in Eq. (6)? 4 say yes, 2 say no

R2, R3, R4 and R6 all report deriving the bracket and finding it *"exactly Eq. (6)"* as typeset. R1
and R5 both report it missing, and both built substantial cases on that reading: R1 measured the
printed form disagreeing with a direct simulation on **3,000 of 3,000** exact-rational cells and made
it his rank 2 major; R5 made it his rank 3 major and reported the printed bracket having the wrong
sign in 3 of 5 random draws, with "Downward to reject" attached to the authors defending it.

**The decisive datum is R6's, and it points to a reading artifact rather than a paper defect:**
*"I first mis-read the -w_r term as absent from a low-resolution text extraction; a 400 dpi render of
the equation shows it is there."* R2 independently reports the same failure mode on a different
object in the same figure family (*"an earlier low-resolution read suggested otherwise and was
wrong"*).

**What the authors should do:** verify the typeset Eq. (6) and, separately, the iff sentence that
immediately follows it, since R1 alleges the **sentence** drops the term even where the equation does
not (*"the sentence after Eq. (6)"* versus *"the body text on p.3 ... already uses the correct
form"*), and R5 independently says the following sentence contains `w_r`, i.e. R1 and R5 disagree
with each other about the prose. If both equation and sentence are correct as printed, say so in the
response with a rendered crop; if the sentence is short a `w_r`, it is a one-character fix. Note that
this dispute has **no bearing on the mathematics**: all six agree on the correct form.

### 2. Does the body contradict Fig. 3 on the shelf cell count? Three reviewers, three readings

- **R2 (rank 3, major):** rendered at 400 dpi and reports Fig. 3 middle reading "dinner 9/9, shelf
  2/9, ledge 4/9" passive and Fig. 3 right reading "shelf 7/9, ledge 5/9" injecting (internally
  consistent, 2+7 = 9 and 4+5 = 9), while the body prints the backward-Euler-shaped remedy as passive
  on "shelf 7/9". *"The body has transcribed the shelf INJECTING count (7/9) as a passive count, so
  the body says the backward-Euler-shaped remedy is passive on 20 of 27 cells while its own figure
  says 15 of 27."* R2 calls a five-cell error in the failure rate *"not cosmetic"* because this is the
  single comparison separating the paper's fix from the published weight.
- **R6:** also read at high resolution and reports the opposite: *"Fig. 3's three panels agree with
  each other and with the body once read at high resolution (dinner 9/9, shelf 2/9, ledge 4/9 passive
  = 12 of 27 injecting for the backward-Euler weight, and shelf 7/9 plus ledge 5/9 injecting in the
  right panel = the same 12)."*
- **R5:** reports a third set entirely: *"Fig. 3's 'dinner 9/9, shelf 9/9, ledge 4/9' matches the
  body."*

**Secretary's position:** at minimum the figure and the sentence are not legible enough to be
audited, which is itself Consensus 9. At worst R2 is right and there is a real transcription error in
the body. The authors can settle this in thirty seconds from the source, and must, because R2's
reading is a stated component of his major-weakness list.

### 3. The kappa = 2 accuracy sentence: 2 confirm, 2 disagree, 1 rejects the inference

Five reviewers attempted *"its charge m(4 + b) being exactly four times the converged
implicit-midpoint charge m(1 + b/4), so it over-dissipates, returns half the converged modal
amplitude in the stiff limit"*. R4 could not derive `m(1 + zeta omega h + b/4)` from anything stated.

- **R1 CONFIRMS both halves.** `m(4+b)/(m(1+b/4)) = 4` for all b, and separately the matched kappa = 2
  sweep gives `qdot+ = 2P/(m(4+b))` while implicit midpoint from rest gives `qdot+ = P/(m(1+b/4))`,
  so *"the ratio is exactly 1/2 per unit impulse"*. R1's reconciliation is the kappa = 2 read-back's
  own factor of 2, and he notes the paper undersells it: *"'half' is right, and is exact per unit
  impulse rather than only asymptotic."*
- **R2 CONFIRMS with a caveat.** Ratio `2(M + m(1+b/4))/(M + m(4+b)) -> 1/2`, but *"the factor 2 is
  an asymptote requiring m(omega h)^2 >> M, which the paper does not state"* (R2 measures 0.636 when
  M = 1000 m and 0.80 at b = 0).
- **R3 DISAGREES.** Against the converged implicit-midpoint **pair** solve (midpoint on both bodies,
  `C+ = 0`), R3 gets an amplitude ratio of **1/4** (0.2504 at b = 1e4), recovering 1/2 only against a
  hybrid reference that keeps the midpoint charge but imposes an end-of-step velocity-level
  constraint.
- **R5 DISAGREES.** R5 derives the converged implicit-midpoint row charge as `m(2 + b/2) =
  2m(1 + b/4)`, making `m(4+b)` exactly **twice** it, so *"'four times' is wrong by a factor two"* and
  "half the amplitude" is the correct half of the sentence. R5 notes the video's measured ratios
  (5.3/9.6 = 0.55 shelf, 7.6/11.7 = 0.65 table) support a half.
- **R6 CONFIRMS with a caveat and rejects the inference.** R6 solved the reference three ways: (A)
  modal midpoint + rigid backward Euler + position-level `C+ = 0` gives reproducing charge
  `2m(1+b/4)`, matched is 2x, ratio 0.5000; (B) midpoint on both sides gives `m(1+b/4)`, matched is
  4x, ratio 0.2501; (C) modal midpoint + rigid backward Euler + velocity-level gives 0.5001. R6's
  ruling: *"'four times the charge, so half the amplitude' is not a valid inference under any single
  convention: at a fixed convention a 4x charge gives 1/4."*

**Reading these five together.** R1/R2 and R5/R6(A) are describing the same physics with two
definitions of "charge" that differ by exactly the kappa = 2 read-back factor: R1 compares
impulse-to-velocity coefficients, R5 compares position-level row denominators. R3's 1/4 comes from a
third reference (midpoint on both sides). **So the disagreement is not about the algebra; it is
entirely about a reference the paper never writes down**, which is precisely what four of the five
ask for as the fix. R6 states the load-bearing consequence: *"The whole thesis of the paper is that
reconstruction and read-back conventions decide the answer. The one place where the paper compares
against a converged reference is precisely where it leaves the convention unstated."*

### 4. Is "passive" the wrong word? The two passivity specialists disagree

R3 makes it a rank 3 **major**: *"What is proved is the sign of one energy difference along one
transition from one initial state. That is neither passivity ... nor stability, yet 'passive' is the
operative word in the theorem statements, the figure axes and every count."* R3's specific objection
is that the paper cites [24], which proves passivity in the strict storage-inequality sense, and then
uses the same word for a one-transition sign.

R4, whose stated expertise is passivity and energy safety at coupling interfaces, does not object.
R4 treats the scoping as adequate (*"I could not find a place where the paper claimed more than it
showed"*) and reserves his majors for the reconstruction convention and the missing arm. R6 likewise
credits the title as honest.

**Secretary's note:** R3's proposed rename ("one-step non-injecting") is free and would cost the
paper nothing but the word. The disagreement is over whether it is required.

### 5. Is the geometric-stiffness attribution wrong? R2 says yes, R6 says no

R2 (rank 7 moderate): *"In both cited works geometric stiffness is the tensor d(J^T lambda)/dx, i.e.
the change of constraint-force DIRECTIONS with position, and that is the term quasi-Newton hosts
drop. M + hD + h^2 K is the linearly-implicit system matrix (material tangent), a different object."*
R2 notes the error sits inside the paper's own novelty-delimiting sentence.

R6, in his novelty assessment: *"The operator (M + h*D + h^2*K)^-1 is correctly attributed to the
geometric-stiffness and stable-constrained-dynamics line rather than claimed."*

R2 is the more specific claim and cites what the cited works actually define. Unresolved from the
artifacts; the authors should check [1] and [23] directly.

### 6. Does the `1 + m/M` offset really distinguish the boundary from a Courant limit?

R1 says yes and treats it as part of the novelty: *"the 1 + m/M offset genuinely does separate it
from a penalty Courant limit and from the asymptotic spectral-radius conditions of two-mass
co-simulation."*

R4 says the paper undercuts itself two sentences earlier: *"1 + m/M is itself O(1) except when
m >> M, i.e. exactly where the paper says the boundary reduces to the Courant-like value"*, and
proposes the weaker but defensible claim (*"we sharpen a folklore O(1) limit into an exact per-sweep
constant with a mass-ratio offset and a reconstruction factor"*).

R6 lands between them, calling the individual pieces *"elementary"* but the framing and the audit the
contribution.

### 7. Is this salami? One ruling for, none against, four abstentions

R6 is the only reviewer to rule: *"I think it does [stand alone], because the split is theory versus
system diagnostic rather than results salami, and it is disclosed in a dedicated paragraph."* R1
raises *"a fair salami question about whether the theory and the diagnostic study are one paper split
in two"* and does not answer it. R4 says *"I cannot judge whether the split is a genuine
theory/experiment division or salami slicing."* R2, R3, R5 treat it as an assessability problem
rather than an integrity one. Nobody argued it is salami.

---

## Action list

Ranked. **[REQUIRED]** items are ones at least one reviewer named as a condition for clearing the bar
or as a downgrade trigger. **[text]** means no new measurement. **[work]** means a new run, a new
figure, or a re-render. The page budget is nearly exhausted, so the cost column matters.

### Required to clear the bar

1. **[REQUIRED] [text] Fix Prop. 3.4's passivity add-on.** Replace the unproved sentence with the
   closed form both reviewers derived: order A injects iff `(kappa^2 + b)/(1+b)^2 > 2 + m/M`; state
   that this is impossible at kappa = 1 (one line, and it proves what the paper says it cannot) and
   give the root `b*(m/M)` at kappa = 2. Say explicitly that on the shipped midpoint reconstruction
   the ordering divisor does **not** buy passivity for soft modes.
   *Asked by:* R1 (rank 1 major), R3 (rank 1 major). *Cost:* two sentences plus one inequality.
   *Downgrade trigger:* R3 will drop to Weak Reject if this is defended as printed; R1 will drop if
   the corrected result no longer supports the C4 / Sec. 6 predictor-side-scoping framing and that
   framing is retained anyway.

2. **[REQUIRED] [work, small] Re-run T5 at kappa = 2 down to b = 1e-2.** The panel's reading is that
   the T5 grid never sampled the failure band, which undercuts the completeness argument the paper
   makes for its validation suite. R1: *"at the shipped 1/960 s substep this is every restorative mode
   below about 65 Hz"*, and *"the corrected statement is a better result: it explains why the shipped
   host is unsafe even with predictor-side restoring dynamics."*
   *Asked by:* R1, R3. *Cost:* one sweep on existing code, one Table 1 row updated.

3. **[REQUIRED] [text] State which coordinates carry kappa, in Sec. 2 and inside Thm 3.3, and print
   the general `dE` with the `-kappa_r(2 - kappa_r) w_r` term.** Then tabulate the mass-only boundary
   for `(kappa_r, kappa) = (1,1), (1,2), (2,2)` and state that the matched charge is passive in all
   three (a genuine robustness result the paper currently leaves on the table), while noting it can
   inject for kappa > 2 under a uniform reconstruction.
   *Asked by:* R1 (rank 3 major), R2 (rank 1 major), R4 (rank 1 major), R5 (part of rank 3).
   *Cost:* one symbol, one sentence, one three-row table. *Downgrade trigger:* R4 will drop to Weak
   Reject if the shipped host does apply one host-wide kappa, *"in which case Remark 1, rho_mid and
   the 27-cell analysis rest on a model of the host that the host does not implement."*

4. **[REQUIRED] [text] Verify and, if needed, repair Eq. (6) as typeset and the iff sentence that
   follows it.** Four reviewers read the `-w_r` term as present and one documents a low-resolution
   extraction dropping it; two read it as absent. Check the rendered PDF, then either fix it or say
   in the response that it is present with a rendered crop.
   *Asked by:* R1 (rank 2 major), R5 (rank 3 major). *Cost:* one character or one response
   paragraph. *Downgrade trigger:* R5 will drop to reject if the printed form is defended as correct
   when it is not; R1 will drop if any reported boundary or figure was computed from a form without
   `w_r`.

5. **[REQUIRED] [text] Check Thm 3.2's printed `b_i`.** Two reviewers report it dimensionally
   inconsistent with its own use; both give the same correction `b_i = (omega_i h)^2 = h^2 k_i/m_i`,
   which also removes the clash with Sec. 2's unsubscripted `b`. They report slightly different
   printed forms, so read the source line rather than either report.
   *Asked by:* R2 (rank 4 major), R3 (rank 4 moderate). *Cost:* one line.

6. **[REQUIRED] [text] Either give a resolvable locator for the [6] quotation or drop the quotation
   marks, and fix the bibliography dates.** Four reviewers failed to find the sentence; three report
   three different years for [6]; [5] is GDC 2005 not 2019; [11] has "Ssamak" for Siamak; [24]'s
   author list and title are garbled.
   *Asked by:* R1, R4, R5, R6. *Cost:* one paragraph of bibliography work. *Downgrade trigger:* R4
   will drop to Weak Reject if the sentence cannot be located, *"since it appears in the abstract."*

7. **[REQUIRED] [text] Settle the body-versus-Fig. 3 shelf count and re-audit every cell count in
   Secs. 4 and 5 against the figures and Table 1.** R2's reading implies a five-cell error in the one
   comparison that separates the paper's fix from the published weight; R6's reading implies the
   counts reconcile; R5 read a third set.
   *Asked by:* R2 (rank 3 major), and implied by R5 and R6. *Cost:* one sentence, plus an audit pass.

8. **[REQUIRED] [text] Define every Table 1 denominator, the dead-band normalization, the liveness
   filter, and the budget notation; reconcile T10, T11, T3 and T6 with the prose; print the two theta
   values and explain how a theta = 0 cell can inject.**
   *Asked by:* all six on Table 1; R1, R4, R5 on the budget and theta notation. *Cost:* a caption
   rewrite plus two or three sentences. R5 additionally asks for the table to be retitled "closed-form
   verification" with the three solver rows marked as the only external evidence, which is one word
   and a footnote.

### Strongly recommended (moves multiple reviewers toward Accept)

9. **[work] Answer the video's pre-impact 65.2 J reading.** Either the readout is mislabelled or the
   resting books alone charge the shelf mode before the drop, in which case the two arms are not in
   the same state at impact and the paper has direct evidence of the secular growth Sec. 6 lists as
   open.
   *Asked by:* R1 (video problem 2, a listed downgrade trigger), R2. *Cost:* one diagnostic run plus
   one sentence, or a corrected overlay and a re-render.

10. **[work] One system-level cell where the published stiffness-aware weight injects and the matched
    weight does not, or a plain statement that none was found plus a reconciliation of 12/27 against
    0/24.** This is the single highest-value new datum in the panel's view.
    *Asked by:* R2 (rank 5), R3, R4 (rank 2 major), R5 (rank 7), R6 (rank 3). *Cost:* a search over
    existing scenes, or one sentence if the answer is no. R4 and R6 both say the affirmative answer
    moves them to Accept outright; R6 says it *"belongs in the abstract"*; R2 says it would
    *"convert the contribution from a theorem into a reason to change code."*

11. **[text] Write the converged reference down in one display line** (which stepper on each side, and
    whether the contact condition is imposed on `C+` or on relative velocity), then derive the
    charge ratio and the amplitude ratio from that one convention so they agree.
    *Asked by:* R3 (rank 5), R4 (question 6), R5 (rank 4), R6 (rank 1 moderate), R2 (asymptote
    caveat). *Cost:* one display and one sentence. This is the fix for Split opinion 3 and it is
    cheap.

12. **[text] Add the zeta = 0 hypothesis to the exactness claim in the abstract, C1 and Thm 3.3, and
    give Thm 3.3 an explicit hypotheses list** (cold start, active row, inert predictor, `w_r > 0`).
    *Asked by:* R2 (rank 10), R3 (rank 2 major). *Cost:* one clause plus a bracketed list.

13. **[work, small] One paragraph of cost.** Per-row flop count for rho (a 2n dot product) and for
    applying `(kappa^2 M_c + h^2 K_c)^-1`; the fact that `G^-1` caches per body per substep; the
    machine; and one measured overhead figure from the 27-cell runs. Plus an explicit statement that
    all results are offline float64 so nobody reads a real-time claim into "production".
    *Asked by:* R1 (rank 8), R3 (rank 9), R4 (rank 7), R5 (rank 6), R6 (rank 8). *Cost:* one
    paragraph and one measurement.

14. **[text] Move the video's 89x converged-reference disclosure into Fig. 1's caption and the T11
    paragraph, and say that T11 is converged in iterations at fixed h.** Also state which grid is the
    reference for the over-deposit claim.
    *Asked by:* R1, R2, R4 (rank 5), R5 (rank 9), R6 (rank 6). *Cost:* two sentences.

15. **[text] Add "at m = M" to the over-deposit factors and give the operating point for the
    0.979 zeta omega h coefficient and the half-amplitude asymptote (`m(omega h)^2 >> M`).**
    *Asked by:* all six. *Cost:* three clauses.

16. **[text] Drop "production"/"shipped" unless a third-party engine is named; define the passivity
    governor and its default state in one sentence and report one cell with it on; either cite a host
    that reconstructs at kappa = 2 or reframe as "hosts that recover velocity at any kappa != 1".**
    *Asked by:* R2 (rank 2 major), R5 (rank 2 major), R3 (rank 10), R4, R6. *Cost:* wording, plus one
    cell if the governor comparison is run. *Downgrade trigger:* R2 will drop to Weak Reject if the
    kappa = 2 premise turns out to be one solver's velocity pass rather than a convention any host
    uses.

17. **[text] Add the per-scene parameter table** (M, coupled `m_i` and `omega_i` or their range, mode
    count, h, substeps, alpha-tilde, contact tolerance, and rho / rho_mid per cell), plus Fig. 1's
    scene coordinates so the teaser can be located on Fig. 2. Make the 27-cell test fully
    self-describing so Sec. 4 stands without [3].
    *Asked by:* R5 (rank 1 major), R1 (rank 7), R4 (rank 6), R2 (rank 8). *Cost:* one small table.
    This is the item most in tension with the page budget; R3 and R4 both suggest paying for it by
    cutting Table 1 to five rows or trimming the Sec. 5 co-simulation paragraph by a third.

18. **[text] Add the two modal lines that make the index computable:** `m = m_i/U_i^2` with
    `U_i = phi_i^T n` (so `m = 1/(phi_i^T n)^2` for mass-normalised modes), and the note that rho must
    be evaluated on the retained basis, where a single retained mode with `(omega_i h)^2 > rho` pushes
    the row toward injection. Rename "mass-normalized weight" to "mass-only weight" throughout.
    *Asked by:* R2 (rank 8). *Cost:* two sentences and a find-replace. R2 calls this *"the half page
    that decides whether a MIG practitioner can actually compute rho for their own reduced model."*

19. **[text] Replace the 19-of-2000 diagonal-charge rate with the sharp criterion**: diagonal-only
    charging can inject only when at least three restorative coordinates are coupled in the row,
    because the normalized charge matrix must have spectral radius above 2; and note that in a
    mass-normalised modal basis `K_c` is diagonal, so the warning applies to non-modal reduced bases
    only. State the ensemble if the rate is kept.
    *Asked by:* R1 (rank 9), R2 (question 7), R3. *Cost:* two sentences. Three reviewers tried to
    reproduce the rate and none did.

### Improves the paper

20. **[work, figure] Rebuild Fig. 3.** Move panel readouts into the caption or a table, split the
    figure or move the inset into prose, unstack the legend from the right panel's readout, print one
    definition of each index used identically in body, axis and caption, and enlarge the annotation
    type. *Asked by:* all six. *Cost:* one figure rebuild.

21. **[text] Label kappa on Fig. 2's caption, add zeta for the `hD_q` term, identify the black curve
    in the right panel, note that the right panel at zeta = 0 is Thm 3.3's matched weight, and add one
    sentence saying what the left panel looks like at kappa = 2.** *Asked by:* R2, R4, R6.
    *Cost:* a caption.

22. **[text] Fix Fig. 3's "passive only where" to "wherever".** One word, and as printed it licenses
    the wrong pre-solve conclusion. *Asked by:* R6. *Cost:* one word.

23. **[text] Fix Fig. 1's caption:** "lifts the highest of the five resting books 56.8 mm off the
    shelf surface (peak over the run)", add the scene's total energy next to the joule figures, report
    the peak as well as the 114 ms value, and say whether the figure and the video are the same run.
    *Asked by:* R4 (rank 8), R5 (rank 12), plus the joule reconciliation from all six.
    *Cost:* a caption.

24. **[text] Add the haptics discrete-passivity line to Sec. 5 and delete "again not parametric
    thresholds".** Colgate-Schenkel sampled-data passivity (`b > KT/2 + B`) and time-domain passivity
    control are squarely on the claimed gap and absent from all 25 references. The honest reframing
    (a unilateral hard row has no damping to spend and no bilateral port, and a weight is not an
    observer) costs nothing and R4 says the paper's genuine distinctions survive it.
    *Asked by:* R4 (rank 3 moderate). *Cost:* three sentences and two citations.

25. **[text] Adopt the two free sharpenings.** R3's passive set `mu >= M(sqrt(1 + G/M) - 1)`, which
    gives practitioners a passive-but-less-lossy option at kappa = 2 and states that matched is
    sufficient rather than minimal; and R2's impossibility result that at kappa = 2 no charge is both
    passive and amplitude-accurate when `m(1 + b/4) < 2M`, which turns the "passive but conservative"
    remark into a theorem. *Asked by:* R3 (rank 6), R2 (question 8). *Cost:* two remarks.

26. **[text] Rename "passive" to "one-step non-injecting" (or "one-sweep dissipative") in theorem
    statements and on figure panels, reserving passivity for the system property and for ref. [24],
    and add one sentence stating that no multi-step or stability conclusion follows and that Fig. 1's
    runaway is correlation, not a corollary.** *Asked by:* R3 (rank 3 major). Note R4, the other
    passivity specialist, did not ask for this. *Cost:* a find-replace plus one sentence.

27. **[text] Two sentences on the damper.** Say it is applied implicitly (then non-positivity is
    unconditional) or add the condition `zeta omega h <= 1` and note that above it the predictor is
    the injecting operation. *Asked by:* R2 (rank 6). *Cost:* one sentence.

28. **[text] Correct the geometric-stiffness sentence** to "the linearly-implicit system matrix whose
    stiffness term quasi-Newton hosts approximate; distinct from the geometric stiffness
    `d(J^T lambda)/dx` of [1, 23]", after checking the cited works. *Asked by:* R2 (rank 7). Note R6
    read the attribution as correct. *Cost:* one clause.

29. **[text] Two sentences reconciling "one sweep already zeroes the residual at any weight" with
    "eight sweeps are passive"**, naming the mechanism additional sweeps engage. R3 also suggests
    retitling around the reconstruction rather than the budget. *Asked by:* R3 (rank 7).
    *Cost:* two sentences.

30. **[text] State the compliance energy convention** (that alpha-tilde is a regularisation whose
    stored energy is deliberately excluded, and that counting it halves the offset), and reconcile it
    with Prop. 3.4's opposite reading of an alpha-tilde row. *Asked by:* R4 (rank 10).
    *Cost:* one sentence.

31. **[text] Promote a boxed practitioner recipe** (compute rho per row like this; if rho > 1 do this;
    the weight for your reconstruction is this) and a three-regime boundary table (kappa = 1,
    kappa = 2, under-relaxed by theta). R1 and R6 both propose paying for it by cutting the Sec. 5
    co-simulation paragraph by a third. *Asked by:* R1, R6, R2 (decision table).
    *Cost:* a boxed paragraph, funded by a cut.

32. **[text] Soften "We supply that framework" / "This paper is that framework" to "a framework
    for"**, and add one sentence saying what a reader who cannot see [3] can still verify from this
    paper alone. *Asked by:* R6 (rank 9), R1 (rank 7), R4 (rank 6). *Cost:* two clauses.

33. **[work, video] Add an on-screen rho or rho_mid overlay with the predicted sign, add the published
    stiffness-aware weight as a third panel, label the operating point as the worst case by the
    video's own grading, and trim the static tail of act 2.** *Asked by:* R1, R2, R3, R5, R6 on the
    index; R2, R3, R4, R5, R6 on the third arm. *Cost:* a re-render. R6: this plus item 10 is the
    difference between his 7 and an Accept.

34. **[text] Fix the proof typo** in Thm 3.1 (`q+ = h qdot+`, not `qdot+ = h qddot+`). *Asked by:*
    R4, R6. *Cost:* one character.

---

## Per-reviewer detail

### R1 -- Position-based dynamics and real-time rigid-body solvers

**Weak Accept, 6/10, confidence 4/5.**

*Self-described stance:* has shipped XPBD-style solvers (substepping, compliance/CFM, Gauss-Seidel row
ordering, warm starting, iteration budgets) and reads the paper *"as a note telling me what to change
in my own row weights."*

**Contribution as understood.** For one hard unilateral contact row that also reads a restorative
(modal) coordinate, a single Gauss-Seidel sweep from a cold start adds energy exactly when
`kappa^2 + (omega h)^2 > 2 + m/M`, so the row's modal mobility must be priced at
`(kappa^2 M_c + h^2 K_c)^-1` instead of `M_c^-1`, and the ratio of two quadratic forms the host
already assembles, `rho = h^2 J M^-1 K M^-1 J^T / (J M^-1 J^T)`, predicts the sign per row before the
solve.

**Summary.** *"I re-derived the central results independently, mostly in exact rational arithmetic,
and the core is correct ... That is a lot of checkable, useful content for a short paper, and the
recipe is genuinely implementable from the PDF."* Two things are wrong (Eq. 6's missing `-w_r`, and
Prop. 3.4's passivity add-on) and one is missing (which coordinates carry kappa). *"Everything else is
scope, bookkeeping and evidence hygiene."*

**Strengths.**
- Thm 3.1's `E+` matched his independent derivation identically; the boundary gave 0 sign mismatches
  over 4,000 exact-rational cells. Thm 3.3's telescoping is exact including 2- and 3-coordinate blocks
  with off-diagonal `K_c`, arbitrary kappa and nonzero compliance, and its identification with the
  reduced-mass inelastic loss is *"correct and elegant."*
- *"The recipe is implementable from the PDF and cheap per row ... I could put both in my own solver
  in an afternoon."*
- *"The observation that the constraint residual cannot discriminate is the single most
  practitioner-relevant sentence in the paper and it is correct ... That is exactly why this bug
  survives in shipped code."*
- Thm 3.2 gives an exact magnitude, not only a sign, and *"the paper under-sells it as a plot
  coordinate."*
- The kappa = 1 matched charge *"is not a fudge factor; it is the row weight the host would have had
  if it solved its own implicit system. The kappa^2 correction for a midpoint reconstruction is the
  part I had not seen before and it is the useful part."*
- *"Scope is stated once, in a boxed paragraph, and then honored ... Very few submissions at this
  length are this disciplined about what they are not claiming."*
- *"Validation culture is well above venue average for a short paper."*
- Novelty *"correctly sized and the closest prior art is found and distinguished."* Checked [24] and
  [25] exist and are described accurately.
- *"The supplementary video's disclosure is exemplary."*

**Ranked weaknesses.**
1. **major** Prop. 3.4's "in addition one-sweep passive" is **false at the shipped kappa = 2** (see the
   math table, row 11). *"The paper draws a scoping conclusion from this proposition ... which is
   exactly the sentence a practitioner would act on: if my restoring row trails the contact row I am
   safe."* On the shipped operating point the failure band `b < 0.18` covers every restorative mode
   below about 65 Hz at m = M. Also implies T5 never sampled the kappa = 2 low-b cells. Cheap to fix.
2. **major** Eq. (6) missing `-w_r`. *"Eq. (6) is the paper's one general equation, the thing a reader
   would transcribe into code."* As printed it deletes the `1 + m/M` offset the paper says
   distinguishes it from a Courant limit. Cheap to fix. (See Split opinion 1: four other reviewers
   read the term as present.)
3. **major** Thm 3.3 never says which coordinates carry kappa. *"A practitioner cannot tell from the
   PDF which convention their host is in."* The matched charge survives either convention; the index
   does not. Cheap to fix.
4. **major** Cold-start theory versus warm deployed host. *"At 8 substeps per frame only the first
   substep after touchdown is cold ... The empirical arms (27 + 24 + 27 cells) are the only support
   for the deployed configuration."* Not cheap to fix.
5. **moderate** Table 1 does not reconcile with the prose (T6 polarity, T10, T11) and the budget
   notation is undefined. *"This is a fixed-budget paper, so the budget is the central independent
   variable, and a few iterations per substep versus 32 iterations is the difference between a
   shipping regime and a non-shipping one."*
6. **moderate** The [6] quotation is not findable and [6] is misdated (R1 read the year as 2022).
   *"A quotation with quotation marks must be findable at the cited source."* Also asks for a locator
   for the [9] quotation.
7. **moderate** Evidence entangled with the anonymous companion [3]. *"A short paper is allowed to be
   narrow, but it must be judgeable on its own."*
8. **moderate** No cost evidence, and the advice ends in a shrug. *"The paper's own advice ends at
   accept a weaker ring, iterate the row, or decouple to open-loop, which is a shrug for a
   practitioner who wants both."* Proposes reconstructing modal DOFs at kappa = 1 while the rigid host
   keeps midpoint: *"it is the first thing I would try."*
9. **minor** The diagonal-charge rate is not reproducible (0 hits in ~4,500 rows) and is impossible for
   n <= 2. *"As stated it sounds like a 1% risk in general; in fact it is a zero risk below three
   coupled coordinates and a real risk above."*
10. **minor** The over-deposit numbers require m = M; `mu_c` is called a charge but used as a mass.

**Math checks.** Confirmed: Thm 3.1 (0/4,000 mismatches, exact-rational spot checks bit-identical);
Thm 3.3 with `W = G^-1` (600 blocks, n = 2 and 3, chain-Laplacian `K_c`, kappa in {1,2,3}, worst `dE`
-0.039); Remark 1's three kappa = 2 boundaries (0 mismatches / 4,000 each); the `(1+b)^2` divisor
(400/400 at kappa = 1 and 2); Thm 3.2's `y = rho - 1` and `rho_mid`; both relaxation boundaries; the
accuracy identities `4x` and `1/2` (*"'half' is right, and is exact per unit impulse rather than only
asymptotic"*); and the internal count arithmetic. **Disagrees with the paper on:** Eq. (6) as printed
(3,000/3,000 cells), Prop. 3.4's add-on (exact-rational two-row simulation), and the unstated
reconstruction convention (33/3,000 mispredictions under `kappa_r = 2`). **Could not verify:** the
19-of-2000 diagonal-charge rate. Notes a degenerate case to exclude from Thm 3.3: if
`w_r = 0, J_c = 0, alpha = 0` then `D = 0` and the solve is undefined.

**Video.** Read 9 frames. *"What the video does NOT show is the paper's headline diagnostic: no rho or
rho_mid value appears in any frame, so the evidence is for the weight (C1/C3), not for the index
(C2), even though the end card asserts the index."* On control: *"Yes for the variable it isolates,
with one caveat I cannot resolve"*, that caveat being the 65.2 J pre-impact reading. On disclosure:
*"The best I have seen on a supplementary video at this venue, and the main reason my confidence is 4
rather than 3."* Also flags the shelf's 89x reference spread (*"against the coarser reference the
matched arm's 5.3 mm is a 53x over-prediction rather than a 45% under-prediction"*) and the
paper/video joule mismatch. Net: *"Weak Accept held with higher confidence, not upgraded."*

**Novelty.** *"Correctly sized, and unusually well-disclaimed for this area."* Lists everything the
paper gives away (Delassus, geometric stiffness, BE propagator, compliant-row-equals-BE, reduced
coordinates as extra DOFs, fixed-iteration energy gain) and identifies the residual delta as (i) the
reconstruction-matched weight, (ii) the closed-form sign boundary whose `1 + m/M` offset separates it
from a Courant limit, (iii) the ordering of `L` against `w_m` as a pre-solve index with an exact
magnitude law, (iv) the `(1+b)^2` divisor. Searched and found nothing pre-empting (i) or (ii). One
citation-integrity problem cuts against the record.

**Presentation.** *"Legible but effortful."* The scope box is *"an excellent device others should
copy."* Sec. 3 packs four theorems, one remark and three specializations into a column and a half with
no worked example. *"The symbol load around one concept is heavy: w, w_m, w_r, w_E, D, L, rho,
rho_mid, a_i, b_i, u, G, W, mu_c, m_eff, m_row, kappa, theta, alpha_tilde."* Fig. 1 *"earns its space
... That is a rare and good teaser."* Fig. 3 *"needs rebuilding."*

**Questions.** 13, including: is the missing `-w_r` a typesetting slip, and was any reported result
computed from the printed form; what b range and kappa did T5 sweep; which coordinates carry kappa and
under which convention were the 27- and 24-cell measurements taken; why not decouple the
reconstruction per DOF; is the video's 65.2 J pre-impact reading real or mislabelled; what does the
budget pair mean and why is the teaser's operating point off-grid; which Table 1 numbers are attempted
counts; what was the diagonal-charge ensemble; are Fig. 1 and the video the same run; is book rise on
the shelf a usable accuracy functional at all; have you tried using the exact magnitude law as a
per-row energy budget; what does the index cost per row; and if [3] is not accepted, which claims lose
their evidence.

---

### R2 -- Model reduction and modal dynamics

**Weak Accept, 6/10, confidence 4/5.**

*Self-described stance:* modal bases and mass-normalised eigenmodes, row-visible modal mass, coupling
of modal amplitudes to contact, reduced coordinates stepped alongside a rigid host; secondary
familiarity with compliant-constraint solvers and co-simulation stability boundaries.

**Contribution as understood.** For one Gauss-Seidel sweep of a single hard unilateral contact row
coupling a rigid body to restorative coordinates from a cold start, the exact sign of the energy change
in closed form, exhibited as the ordering of two operators the solver already assembles, plus the
charge `kappa^2 M_c + h^2 K_c` that turns the sweep into exactly a perfectly inelastic impact loss.

**Summary.** *"I re-derived all four closed forms by hand and re-checked them in exact rational
arithmetic: they are right as stated, with one printed definition wrong (b_i in Thm 3.2) and one
convention left unstated that matters for the theorem's advertised generality."* The two things
holding the paper back: *"the practical case rests on an uncited premise (that the shipped host
reconstructs at kappa = 2)"* and *"the recommended weight is never shown to matter at system level
over the already-published backward-Euler-shaped weight (0 of 24 versus 0 of 24)."* Also found a
body/figure disagreement on the shelf cell counts *"that must be fixed before this can be trusted by a
reader."*

**Strengths.**
- *"For a short paper carrying five closed forms, that is unusual"* (everything reproduced exactly in
  exact rational arithmetic over thousands of random cells).
- *"Eq. (7) is genuinely elegant and useful ... the matched sweep is not merely passive, it is
  calibrated. I verified the identity holds to exact equality on 4000/4000 cells, and it gives the
  practitioner a number, not an inequality."*
- *"The reconstruction generalisation is the real novelty and it is correctly sized ... a weight
  matched to backward Euler is the wrong weight on a midpoint-reconstructing host."*
- *"The danger index is basis-invariant in the right sense"* (verified `a_i` and `a_i b_i` invariant
  under mode rescaling), and the nonmodal collapse to 4.3e-14 *"is the right control to run."*
- The diagonal-versus-full stiffness hypothesis *"is handled honestly rather than hidden."*
- The scope statement and Limitations paragraph are *"model behaviour for a short paper."*
- *"Fig. 1's caption reports the evidence against its own fix ... This is the most complete disclosure
  I have seen in a submission of this size."*
- *"The choice to test the sign with the measured projection rather than the closed form (T2, T4) is
  the right experimental design: it makes the phase map a test of the theorem rather than a plot of
  it."*

**Ranked weaknesses.**
1. **major** The paper never says which DOFs carry kappa, and the theorems are true only under one
   reading. Under a uniform reconstruction the headline boundary becomes
   `(omega h)^2 M/(M+m) > kappa(2-kappa)`, which *"at kappa = 2 has NO passive region for any mass
   ratio"*, and Thm 3.3's unconditionality fails for kappa > 2 (1908/2000 injecting at kappa = 3).
   *"Unconditional passivity for every kappa is the paper's strongest advertised claim and the reason
   the weight is presented as a fix rather than a tuning."* Cheap to fix.
2. **major** The kappa = 2 shipped default is asserted with no citation. *"The standard position-based
   reconstruction in the literature the paper itself cites ([14] XPBD, [17] rigid XPBD) is
   v = (x+ - x-)/h, i.e. kappa = 1 ... If most hosts reconstruct at kappa = 1, then the published
   remedy is already correct and this paper's new weight is unnecessary in practice."* Not cheap.
3. **major** Body versus Fig. 3 on the shelf count. *"The body has transcribed the shelf INJECTING
   count (7/9) as a passive count, so the body says the backward-Euler-shaped remedy is passive on 20
   of 27 cells while its own figure says 15 of 27 ... a five-cell error in the failure rate is not
   cosmetic."* Cheap to fix. (See Split opinion 2.)
4. **major** Thm 3.2's printed `b_i` is dimensionally inconsistent and makes Eq. (4) false as printed
   (fails 1944/2000; exact 2000/2000 with `b_i = (omega_i h)^2`). *"This is inside a theorem
   statement, and it is the one formula a practitioner must transcribe."* Cheap to fix.
5. **moderate** At system level the recommended weight is not shown to beat the published one (0/24
   versus 0/24). *"A reader can reasonably conclude the published weight is the better engineering
   choice on the evidence shown."* Not cheap.
6. **moderate** A predictor-side (explicit) modal damper is not non-positive when `zeta omega h > 1`.
   *"In the corner where zeta*omega*h > 1 the predictor is the injector and the projection bound no
   longer covers the step. A modal reader will spot this immediately."*
7. **moderate** Geometric-stiffness misattribution. *"Getting the delimited object wrong misdescribes
   the prior art it is delimiting against."* (R6 disagrees; see Split opinion 5.)
8. **moderate** *"A paper whose title advertises an effective mass never gives the map from a modal
   basis to its own m."* Gives it: `m = m_i/U_i^2`, so `m = 1/(phi_i^T n)^2` for mass-normalised
   modes. Also: "mass-normalized weight" clashes with the standard meaning; rho depends on the
   retained basis. *"This is the half page that decides whether a MIG practitioner can actually
   compute rho for their own reduced model."*
9. **moderate** Every closed form is n = 1 from a cold start with one active row, while *"hosts in the
   room run 4-8 iterations with warm starts and many simultaneous rows."* Asks for the measured
   relationship between rho at n = 1 and the sign at n = 2, 4, 8.
10. **minor** The abstract's exactness claim omits the zeta = 0 qualifier. At `omega h = 10`,
    `zeta = 0.02` the gap is around 20 percent.
11. **minor** Table 1 bookkeeping, plus the hidden `m/M = 1` and `m b >> M` operating points.
12. **minor** Fig. 3 unreadable at print size; Fig. 2's caption omits kappa. *"Omitting kappa from
    Fig. 2 invites the reader to apply the mass-only boundary to the shipped host, which is precisely
    the error the paper exists to prevent."*

**Math checks.** Confirmed: Thm 3.1 including the kappa-general form (0/4,000 mismatches); Eq. (6) and
Eq. (7) to exact equality on 400 random blocks with n = 1..3 and random SPD `M_c`, `K_c`, 0 injecting
cells, plus the exact inelastic-loss identity on 4,000/4,000; the kappa = 2 arithmetic including
`M(2-b) > m(1+b)^2` (0/4,000); Prop. 3.4's divisor (500 triples); `rho_mid` in body and figure
(re-rendered at 400 dpi, and **explicitly retracts an earlier low-resolution read that suggested they
disagreed**); both relaxation boundaries (0/3,000 each); the half-amplitude asymptote with the caveat
that it needs `m(omega h)^2 >> M`; the diagonal-charge criterion (0/3,000 in his own sampling, and a
proof it is impossible for n <= 2). **Disagrees with the paper on:** Thm 3.2's printed `b_i`.
**Caveat on Thm 3.3:** unconditionality survives only under the asymmetric convention. **Adds:** at
kappa = 2 the amplitude-accurate charge `m(1 + b/4)` injects iff `m(1 + b/4) < 2M`, so *"at the
shipped kappa there is provably NO charge that is both passive and amplitude-accurate whenever the
converged modal charge is below 2M. That single line would state the paper's 'passive but conservative'
trade-off as a theorem instead of an observation."*

**Video.** Read 9 frames. *"What is varied is the weight, so the clip is evidence for contribution C1
only; nothing on screen exercises the danger index rho, the ordering divisor, or the relaxation
boundary."* On control: *"Caveat one: the runs are NOT in the same state at first contact ... The
divergence therefore predates the impact ... This cuts against the mass arm, not the paper, but it
should be said."* On disclosure: *"Unusually good, and in one respect better than the paper"*, singling
out the 89x line that *"the paper's Fig. 1 caption omits when it quotes the 9.6 mm figure."* Also flags
that mid-run readouts are cumulative maxima, *"which invites a misreading."* Net: *"It moved me up
within Weak Accept rather than across a boundary."* The three things that did the work: the clearance
controls, the iteration grading, and the two measured converged/matched ratios bracketing the
theoretical factor 2.

**Novelty.** *"Correctly sized and, unusually, explicitly delimited."* Agrees with the delimitation
and says it removes the biggest overclaiming risk; notes the kappa = 1 case *"is essentially a
re-reading of known algebra"* since the matched sweep is the Schur complement of the implicit block.
What survives as new: the sign reading packaged as a threshold-1 scalar, the reconstruction-shaped
generalisation with its exact inelastic-loss identity, and the `(1+b)^2` divisor. Verified both 2026
arXiv references exist and are correctly characterised. Two residual risks: closeness in spirit to the
penalty Courant limit and the two-mass co-simulation boundary (*"defensible but thin as a novelty
argument on its own"*), and the geometric-stiffness misattribution *"in the novelty-delimiting sentence
itself."*

**Presentation.** Secs. 1, 2 and 6 clear; the scope box *"the best-written part of the paper."* Sec. 3
*"dense but followable by a specialist: every closed form is stated precisely enough that I could
re-derive it from the paper alone, which is the real test."* Two obstructions: the notation load and
the missing map from a modal basis to `m`. *"The 'shipped'/'production' language is doing rhetorical
work the anonymised evidence cannot support."* Nine writing defects listed, including [24]'s garbled
author list and title.

**Questions.** 10, including: which DOFs carry kappa and does Thm 3.3 survive the other convention;
what is the citation for the kappa = 2 reconstruction and *"if the field is mostly kappa = 1, what is
the practitioner's reason to adopt the new weight?"*; is the printed `b_i` a typo; which is the
measured shelf passive count; how should a reader with a mass-normalised basis compute `m`; is the
damper implicit; would you state the diagonal-charge criterion instead of the rate; is the
no-passive-and-accurate result correct; is there a system-level operating point where the two remedies
separate; and which grid is the reference for the 51x over-deposit claim.

---

### R3 -- Contact mechanics and numerical optimization

**Weak Accept, 6/10, confidence 4/5.**

*Self-described stance:* complementarity formulations, Delassus/Schur interface operators, Moreau's
inelastic shock, energy behaviour of splitting and Gauss-Seidel schemes, and *"the precise meaning of
'passive' and 'dissipative' for a time-stepping contact solve."*

**Contribution as understood.** The closed-form sign of the energy change made by one Gauss-Seidel
projection of one unilateral position-level contact row, the joint dependence on the row weight's
operator and the host's velocity read-back factor, the per-row pre-solve index, and the charge that
makes the sweep lose exactly a perfectly inelastic impact.

**Summary.** *"A narrow, carefully done theory paper about a single contact row ... I re-derived every
closed form in the paper independently and all of the central algebra is correct, including the parts I
expected to break."* Against that: Prop. 3.4's side claim is false at kappa = 2 *"by my own use of the
paper's Eq. (6)"*; the headline identity silently requires zeta = 0; Thm 3.2's `b_i` is inconsistent;
the half-amplitude claim does not follow from the reference the same sentence names; and *"the paper
uses 'passive' throughout for what is a one-transition energy sign from one specific state, while the
motivating harm is a 14,000x multi-step runaway that no theorem covers. All of these are text-level
repairs."*

**Strengths.**
- *"The algebra is right, and it is right in generality"* (Eq. 6 verified to 7e-14 relative across
  kappa in {-2,-1,0.5,1,2,3.7} and alpha in {0} U [1e-6, 1e3]).
- *"The matched sweep does not merely dissipate, it dissipates precisely Moreau's inelastic shock loss
  for the pair (M, m_row). That is a genuinely clarifying statement for a contact reader."*
- The kappa = 1 exactness claim *"is exactly true, and for any number of coupled coordinates"*
  (agreement to 8.9e-16).
- *"Reconstruction dependence is the right thing to have found ... it is not something I have seen
  written down."*
- *"Scope is stated once and then honoured."* Checked [24] and *"the characterisation of it is
  accurate."*
- The 27-cell experiment *"is well designed for what it tests"*, and reporting that all five naive-rho
  misses are false negatives *"is the kind of disclosure that earns trust."*
- *"The Fig. 4 collapse is the best single piece of evidence ... a real test of the operator form and
  not just of the scalar special case."*
- *"The supplementary video discloses its operating point more completely than almost any graphics
  video I review."*

**Ranked weaknesses.**
1. **major** Prop. 3.4's side claim is false at kappa = 2 *"and at kappa = 1 it is provable in two lines
   from the paper's own Eq. (6), so the stated inability to prove it in closed form is doubly wrong."*
   4,936 of 20,000 cells inject at kappa = 2, 0 of 20,000 at kappa = 1. *"C4 is sold as a practitioner
   rule ... On the host the paper actually ships on, that rule does not protect the row."* Cheap to fix.
2. **major** The kappa = 1 exactness holds only at zeta = 0, and zeta = 0 is nowhere in the binding
   scope list. Also missing hypotheses: active row with `lambda >= 0`, `w_r > 0` for strictness, and no
   external load on the restorative coordinate (*"a gravity-preloaded shelf has q != 0, so the shipped
   scenes violate the cold start from t = 0, not just after the first impact"*). *"A referee should be
   able to read the hypotheses off the theorem."* Cheap to fix.
3. **major** "Passive" is used for a one-transition sign. *"Contact readers use 'passive' in a specific
   technical sense, and Ref. 24 (which the paper cites) proves passivity in that sense."* Proposes
   "one-step non-injecting" or "one-sweep dissipative", plus one sentence stating that the Fig. 1
   runaway is *"evidence of correlation, not a corollary."* Cheap to fix.
4. **moderate** Thm 3.2's `b_i` is used as if dimensionless; on a 3-mode example `L = 6.7038` while
   `sum a_i b_i = 42.73` with the printed definition. *"A reader who implements from the printed
   definition computes the wrong index."*
5. **moderate** The two halves of the kappa = 2 accuracy claim are inconsistent and the reference is
   never written down. R3 gets 1/4, not 1/2, against the converged implicit-midpoint pair solve.
   *"These are the only accuracy numbers in the paper, and they are what a practitioner will use to
   decide whether the matched weight is too dissipative."*
6. **moderate** The passive set is never characterised, so *"the paper presents a sufficient charge as
   if it were the prescription."* Gives the exact threshold `mu >= M(sqrt(1 + G/M) - 1)` and notes the
   matched charge is strictly interior, *"and far inside when G >> M, so at kappa = 2 there is a whole
   interval of charges that are non-injecting and less over-dissipative than m(4+b)."*
7. **moderate** The fixed-budget framing overstates the iteration count's role and the mechanism by
   which iterating fixes the problem is never explained. *"A reader cannot reconcile 'one sweep already
   zeroes the residual at any weight' with 'eight sweeps are passive', and the unexplained gap is
   exactly where the theory stops touching the demonstration."* Suggests retitling around the
   reconstruction.
8. **moderate** Every hypothesis is violated by the scenes used to motivate them, and this is stated
   only in pieces. *"It is the difference between 'we predict this failure' and 'we observed this
   failure and have a theory of a related idealised case'. The paper is close to the honest version
   already; it just never says it in one place."*
9. **minor** No cost, no runtime, no implementation note. Notes the diagonal shortcut is closed off by
   the paper's own data and that `G^-1` is one precomputation per mode block per h.
10. **minor** The host's passivity governor is disabled everywhere and never described or compared
    against. *"The first question from the room will be 'why not leave the governor on?'"*
11. **minor** Table 1 bookkeeping and provenance. Asks for a one-word provenance column.

**Math checks.** Confirmed: Thm 3.1 with the physical reading (*"the projection is the perfectly
inelastic two-body collision"*), 0 misclassifications / 20,000; Eq. (6) to 7e-14 over 4,000 cases with
n = 1..4 and dense non-diagonal `M_c`, `K_c`; Eq. (7)'s unconditional negativity with a full case
analysis, noting *"W = G^-1 depends on kappa, so this is 'for each kappa there is a matched charge',
not 'one charge works for all kappa'; the abstract's 'passive for any kappa' reads ambiguously"*; the
inelastic-loss identity (*"the cleanest result in the paper"*); the kappa = 2 arithmetic (0/60,000);
Eq. (4)/(5) and `rho` with the `b_i` caveat; the kappa = 1 exactness for n = 1..4 (8.9e-16) with the
zeta caveat; the converged implicit-midpoint charge `m(1 + zeta omega h + b/4)`; the `(1+b)^2` divisor;
`rho_mid` (0/4,000); both relaxation boundaries (0/40,000 each), plus the observation that with
theta < 1 on only the modal side the residual is no longer zero so *"the 'residual cannot discriminate'
argument applies only at theta = 1."* **Uniquely checked and confirmed:** Prop. 3.4's load-bearing
premise that the converged step is dissipative at kappa = 2 (0 injecting of 200,000 samples),
*"so the framing is sound."* **Uniquely added and confirmed:** the exact passive-set threshold (0
misclassifications / 20,000). **Disagrees with the paper on:** Prop. 3.4's add-on, and the
half-amplitude claim. **Could not reproduce:** the diagonal-charge rate (1 of 2,000 in his own
ensemble).

**Video.** Read 10 frames. *"Yes, and unusually well"* on control, with two caveats: only the worst and
best weights are shown, so *"the video cannot separate 'the matched weight fixes it' from 'any
stiffness-aware weight fixes it'"*, and the operating point is the single worst budget, *"which is a
legitimate shipping configuration for small-step position-based hosts but should be said in the paper's
voice, not only in 8 pt video text."* On disclosure: *"Exemplary, including numbers that hurt the
authors ... The self-damaging disclosures are the ones I most credit."* Verified the 32x factor is
self-consistent with the clip length. Key problem: *"What the video demonstrates is instability ...
which no theorem in the paper covers; the theorems are one-transition sign statements. The video
therefore evidences the motivation, not the results."* Net: *"Yes, upward. Reading the PDF alone I was
at weak reject leaning borderline."*

**Novelty.** *"Correctly sized in most places, thin in one."* The thin place: the exactness half of C1
*"is very close to a known fact in the contact literature the paper itself cites"*, namely Peiret et
al.'s exact interface solve using the subsystem's active-constraint effective mass. *"The paper's
framing ... should acknowledge that lineage more directly than the current one-clause disclaimer."*
Accepts as new: the kappa-parameterisation with its concrete consequence, the per-row index with the
exact identity, and the `(1+b)^2` divisor. *"For a short paper that is a defensible contribution
provided the errors above are repaired; it would not be enough for a full paper."*

**Presentation.** *"Precise but over-compressed ... sentences routinely carry three claims at once, so
a reader who is not already inside the formalism has no landing place."* Two specific clarity failures
cost him time: `mu_c` never identified as a mass, and Prop. 3.4 never stating kappa, *"which is exactly
the variable Remark 1 spends a paragraph insisting matters."* Would cut Table 1 to five rows and spend
the space on a hypotheses list, the Prop. 3.4 closed form, and two sentences on cost. Fig. 2 and Fig. 4
*"are the strongest"*; Fig. 3 is over-packed. Reports [24]'s title garbled.

**Questions.** 11, including: at which kappa is Prop. 3.4 stated and did T5 include kappa = 2; does the
exactness hold at zeta > 0; is `b_i` equal to `(omega_i h)^2`; please write down the converged
reference; are the over-deposit factors at m = M; *"did you consider recommending a charge in that
interval at kappa = 2"*; what mechanism removes the injection as the budget grows; what does the
diagnostic cost; what does the governor do and how does the matched weight compare with leaving it on;
how far does the cold-start scope reach under gravity preload; and please state Fig. 1's sampling
instant in the panel.

---

### R4 -- Passivity and energy safety at coupling interfaces

**Weak Accept, 6/10, confidence 4/5.**

*Self-described stance:* passivity at coupling interfaces, co-simulation stability (two-mass model,
sequential/parallel modular integration), haptics discrete-time passivity (Colgate-Schenkel bounds,
time-domain passivity observers and controllers), constrained multibody contact solvers.

**Contribution as understood.** The exact energy change of one cold-start projection of a single hard
unilateral row, the injection boundary located at `kappa^2 + (omega h)^2 = 2 + m/M`, and the
reconstruction-matched charge that makes the sweep provably dissipative with loss equal to the
reduced-mass inelastic shock loss.

**Summary.** *"A narrow, correct and unusually honest theory paper about one object ... I re-derived
every central result independently and all of them hold."* Reservations are *"about sizing and
isolation rather than correctness"*: the unstated rigid-side reconstruction, no experiment isolating
the kappa^2 factor, a co-simulation-only bibliography that makes one Related Work sentence false, and
an unverifiable motivating quotation. *"All four are cheap to fix, and none of them touches the
algebra, which is why I am on the accept side."*

**Strengths.**
- *"Every theorem I checked reproduces ... Zero disagreements on tens of thousands of random cells.
  Papers whose stated algebra survives this are rarer than they should be."*
- *"The actionable item is genuinely one line of host code ... For a games audience that is the right
  shape of fix, and it is the kind of thing the passivity-observer literature does not give you."*
- The residual-blindness observation *"is short, correct and practically important."*
- *"Fig. 4 is the best single piece of evidence in the paper ... its collapse is a real cross-check
  that rho is basis-free rather than a modal-basis artifact."*
- *"The claim discipline is unusually strict for this subject area ... I could not find a place where
  the paper claimed more than it showed."*
- *"The supplementary video's disclosure is exemplary ... This is the standard supplements should be
  held to."*

**Ranked weaknesses.**
1. **major** Eq. (6) and Thm 3.3's unconditionality hold under an unstated asymmetric reconstruction.
   Under one host-wide kappa the mass-only condition becomes `L > kappa(2-kappa) w_m`, so at kappa = 2
   *"EVERY cell with nonzero coupling injects (I measured 2000/2000)"*, and the matched weight injects
   for kappa > 2 (counterexample kappa = 3, M = 1 kg, m = 50 kg, `omega h = 10`, `dE = +1.50 J`).
   *"The entire paper is an interface energy-accounting argument, and which reconstruction each side of
   the interface uses is exactly the quantity that decides where the energy comes from."* Cheap to fix.
2. **major** No experiment isolates the kappa^2 factor. *"A practitioner watching the video or reading
   Fig. 1 will conclude 'add h^2 K to the row weight', not 'match kappa'. The h^2 K term is explicitly
   disowned as prior art ... That reduces the demonstrated practical contribution to a re-explanation
   of why an existing remedy works."* Not cheap. *"If there is any shipped scene where the kappa = 1
   weight injects and the matched one does not, that single cell is the paper's most valuable number
   and belongs in the abstract."*
3. **moderate** The haptics discrete-passivity literature is absent, making the sentence *"again not
   parametric thresholds"* false. *"MIG has haptics and interaction people in the room; the omission is
   the kind that reads as convenient rather than accidental, and it inflates the perceived gap. The
   paper's genuine distinctions ... are strong enough to survive the comparison, so the honest framing
   is available at no cost."*
4. **moderate** The [6] quotation could not be found in the post or the repository, and the reference is
   dated 2012 for a February 2024 project. *"I state this as a verification failure, not an accusation:
   it is possible the quote is from a different Solver2D artifact I did not find, which is itself the
   problem."*
5. **moderate** The converged reference is iteration-converged at fixed substep, not converged in h, and
   the paper does not say so. *"An 89x spread across substep grids means the reference is not a ground
   truth for displacement at all on that scene, and the supplement says so while the paper does not."*
6. **moderate** Companion entanglement. *"The theory (Sections 2-3) is self-contained and checkable,
   which is what saves the submission. But the practitioner case is not independently assessable."*
7. **moderate** No cost number anywhere. *"The claim 'priceable before the solve' is a performance claim
   in disguise."*
8. **minor** Fig. 1's caption overstates its own measurement. *"This is the teaser sentence of the paper
   and it is the one sentence contradicted by the paper's own supplement ... the honest defect is a 5 cm
   hop and 0.03 to 0.11 J of book kinetic energy out of 925 kJ of injected modal energy, which is a more
   interesting fact."*
9. **minor** Five internal inconsistencies: the three-value theta set against a two-value cell count;
   T10's 9,900 versus 300/300; the hidden m = M; Fig. 2's caption missing kappa, zeta and an explanation
   of the black curve; and the Thm 3.1 proof typo.
10. **minor** The compliance-shifted boundary depends on an unstated energy convention. *"Anyone applying
    the diagnostic in an XPBD host with soft contact (the common case) needs to know which convention
    the threshold assumes."*
11. **minor** The Courant distinction is undercut two sentences earlier. *"The current wording implies a
    categorically different criterion and invites the repackaging objection."*

**Math checks.** Confirmed: Thm 3.1 (5e-11 over 4,000 cells, 4,000/4,000 sign agreements); Thm 3.2's
Eq. (4)/(5) and `y = rho - 1` *"exactly"*, with the note that the identity is basis-free so the Fig. 4
collapse *"is expected rather than lucky"*; Eq. (6) and Eq. (7) over 3,000 random trials with n in
{1,2,3,5}, dense SPD `M_c` and `K_c`, kappa in {-3,-1,0.5,1,2,7}, 0 cells with `dE > 0`, plus the
reduced-mass identity to 7e-14; the kappa = 2 arithmetic including the transition points at m/M = 2.5
and 10; `M(2-b) > m(1+b)^2` (0/4,000); `rho_mid` (0/3,000) and that plain rho's misses are false
negatives; the `(1+b)^2` divisor (2.8e-8, float accumulation only); both relaxation boundaries with the
monotonicity that explains T8's "0 unsafe flips". **Confirmed with caveat:** the uniform-kappa case (see
above). **Confirmed with caveat:** internal consistency, computing `mgh = 58.9 J` for act 1 and
`39.2 J` for act 2 and reporting the video's 14,350x and 17.8x overruns *"a number the paper never
gives."* **Could not verify from the PDF:** the [6] quotation. Verified [24] and [25] exist and are
described accurately, and *"confirmed from the reference list that no haptics discrete-passivity work is
cited."*

**Video.** Read 9 frames. *"Act 2 is the more valuable act: it is a genuinely multi-contact scene, which
the paper's own single-row theory does not cover, and the fix still holds there."* On control:
*"Yes, to an unusually high standard for a supplement, with one important gap"*, the gap being the
missing third arm: *"this video isolates 'stiffness-aware weight vs mass-only weight', not
'reconstruction-matched kappa^2 weight vs any stiffness-aware weight'. It therefore supports a weaker
claim than the paper's headline. A third panel with the kappa = 1 arm would have cost nothing and would
have been the decisive evidence."* On disclosure: *"The best supplement disclosure I have reviewed ...
The big number is honestly decomposed rather than hidden."* Net: *"Yes, upward, from Borderline to Weak
Accept ... on the strength of the video I believe the shipped-host claims, which is not something I
could have said from the PDF."*

**Novelty.** *"Correctly sized in the paragraph that lists what the authors do not claim, and oversized
in the paragraph that describes the gap."* Searched and did not find the kappa^2 factor stated anywhere.
Notes that the pure diagnostic, evaluated in the scalar case, *"is just b/(1 + m/M), i.e. a Courant-type
ratio read through the row. So the diagnostic on its own is close to repackaging; its value-add is that
it is computable from quantities the solver already forms and that it is basis-free."* Credits the
handling of finite-iteration passivity and the co-simulation positioning as accurate. *"Paired with the
reconstruction-matched charge and the exact inelastic-impact identity, it is a genuine if small
contribution, correctly proved, and sized appropriately for a short paper, provided the authors state
the reconstruction convention it rests on and stop implying that no closed-form energy threshold exists
anywhere in the coupling literature."*

**Presentation.** *"Dense but genuinely legible if you do the algebra with a pen, which is the real test
and which the paper passes."* The scope box *"is an excellent device and I wish more papers used it."*
Three weaknesses: compressed proofs (so one typo sits in the derivation most readers will attempt), the
never-stated rigid-side convention, and Sec. 4 as *"a wall of numbers whose provenance is split between
Table 1, the prose and figure panels."* Fig. 2 *"excellent"*, Fig. 4 *"the strongest evidence"*, Fig. 1
*"effective but its caption overstates"*, Fig. 3 *"doing the job of a table"*. Also flags "its success
is explainable about stiffening the row" as ungrammatical.

**Questions.** 10, including: which reconstruction does the rigid side use, and does the
unconditionality survive a host-wide kappa; where exactly does the [6] sentence appear; is there any
shipped operating point where the published weight injects and the matched one does not, and please
reconcile 10/27 against 0/24; *"'two relaxations theta in {0, 0.7, 1.0}': which is it? If theta = 0 is
included, the modal correction is zero and injection is impossible by your own theta^2 scaling"*; why do
the act-1 converged references disagree 89x and why is that in the video but not the paper; please define
the per-impulse mass precisely; does the compliance boundary assume the regularising row stores no
energy; what does rho cost per row per substep and can the factorisation be cached; does any book
actually leave the shelf; and what happened on T10's other 9,600 cells.

---

### R5 -- Games practitioner and benchmarking methodologist

**Weak Accept, 6/10, confidence 4/5.**

*Self-described stance:* ships and profiles constraint solvers at fixed iteration budgets;
*"I judge evidence for traceability: are operating points disclosed, are arms controlled, are pass-rate
denominators defined, would a second person reproduce the headline number from what is written."*
Competent in constraint-solver algebra and re-derives theorems rather than trusting them. Not a
co-simulation stability theorist.

**Contribution as understood.** For one unilateral contact row coupling a rigid body to a reduced
restorative block at a tiny fixed budget, the closed-form sign of one sweep, its dependence on the
reconstruction factor, the matched charge that makes the sweep exactly the inelastic impact loss, and
the packaging as a pre-solve scalar plus an ordering divisor.

**Summary.** *"A narrow theory paper with a practitioner payload: a one-line change to how a
contact-to-modal row is weighted, plus a pre-solve scalar."* Everything he checked reproduced to machine
precision except two items. *"The theory is real, non-obvious for anyone embedding reduced coordinates
in a PBD host, and honestly scoped against prior art. The evidence base is weaker than its packaging:
eight of Table 1's eleven rows verify the authors' closed forms against the authors' own model
(self-verification of algebra, valuable but not validation), and every system-level result comes from one
host the reviewer cannot see."* And: *"Not one of the three named scenes has its omega, m, M, mode count,
or rho reported, so no headline number in Fig. 1 or Section 4 is traceable or reproducible from the
PDF."*

**Strengths.**
- *"The central theorems are correct ... This is a paper whose math survives an independent referee
  reimplementation, which is not the norm."*
- *"The kappa-dependence is the genuinely new and useful observation ... exactly the kind of thing that
  silently bites anyone who bolts reduced coordinates onto an XPBD-style host."*
- *"The novelty claim is correctly sized."* Checked [24] independently; *"the characterization is
  accurate."*
- The residual-blindness argument *"is correct and practically valuable ... the kind of thing a shipping
  engineer needs told to them."*
- *"The scope declaration is disciplined and repeated where it binds ... That is honest reporting against
  interest."*
- *"The supplementary video is one of the best-controlled I have reviewed."*
- *"The one-sweep model is small enough to audit ... That is a real virtue and it is why I could localize
  the Eq. 6 error rather than merely doubt it."*

**Ranked weaknesses.**
1. **major** No scene parameters anywhere. *"I therefore cannot place Fig. 1's 1,707 J on Fig. 2, cannot
   check whether the demo scene sits where the theory says it should, cannot reproduce the 27 cells ...
   A reader who wants to repeat the measurement on their own host has no target to hit. This is the
   single biggest methodological hole for a paper that says its index is 'computable before the
   solve'."* Cheap to fix.
2. **major** Invisible in-house host, unearned words, undefined governor. *"'Production' and 'shipped'
   are not substantiated by anything in the paper ... At a games venue those words carry real weight and
   should not be used loosely."* And: *"If the host ships that governor on, the headline demo is a
   configuration the host would never run, and the paper's central narrative changes. As written I
   cannot tell."* Not cheap.
3. **major** Eq. (6) missing `-w_r`. Three independent consistency checks; *"the printed bracket has the
   wrong sign in 3 of 5 random general draws I tested ... This is the one equation a reader would
   implement, and it is the general theorem the abstract advertises."* Cheap to fix. (See Split
   opinion 1.)
4. **moderate** The kappa = 2 accuracy sentence is internally contradictory. *"In the stiff limit the
   deposited amplitude scales as the inverse of the row charge, so a 4x charge excess gives a quarter of
   the amplitude, not a half; the two halves of the sentence cannot both be true."* R5's derived charge
   is `m(2 + b/2)`, so *"m(4+b) is exactly twice it and 'half the amplitude' is the correct half of the
   sentence."* Notes the video's measured 0.55 and 0.65 agree with two.
5. **moderate** Table 1's denominators, tolerances and metrics are undefined, and *"eight of eleven rows
   are self-verification of the authors' own closed forms presented as a benchmark suite ... Fig. 4 is
   the strongest example, since y = rho - 1 is an identity that I verified symbolically, so its
   '288/288 collapse to 4.3e-14' is a code check, not a finding."*
6. **moderate** No timing, no hardware, no cost, *"at a venue whose audience is real-time and
   interactive ... As it stands the guidance is asserted to be cheap rather than shown to be cheap."*
7. **moderate** The decision-relevant comparison against the published implicit weight is never made on
   accuracy. *"A practitioner choosing between two one-line weights wants the empirical comparison ...
   the video omits it entirely, which makes the matched weight look uniquely necessary."*
8. **moderate** Actionability is limited to a case a shipping title does not have, and the abstract does
   not carry the index's known unsafe-direction failure. *"The actionable residue is therefore the weight
   rule (real, valuable, one line) rather than the index, which is what the title leads with."*
9. **moderate** The converged reference is itself substep-dependent by 89x, disclosed only in the video.
   *"The honest reading of 'the matched weight returns half the converged amplitude' is 'half of a
   quantity that is not itself converged in h'. A methodologist needs that stated in the paper."*
10. **minor** Budget notation never expanded, the teaser's operating point off-grid, and *"'two
    relaxations theta in {0, 1.0}' is either a typo or a convention that halves the grid ... as printed
    the reader cannot interpret the paper's most quoted empirical number."*
11. **minor** The [6] quotation is not verifiable and the entry has no year, venue or URL. *"This
    audience knows Solver2D, and the paper's entire opening move rests on it."*
12. **minor** Four smaller items: the hidden m = M (and the 0.979 coefficient implying the same); Fig. 3's
    `rho_mid` axis label as he reads it not matching the body (*"the type is too small for me to be
    certain, which is itself a finding"*); Fig. 1's "throws the five resting books"; and Sec. 6's
    "accepting the physically correct amplitude" reading as if the matched weight delivers it.

**Math checks.** Confirmed by rebuilding the model from Sec. 2 alone: Thm 3.1 (crossings located to full
precision at m/M = 0.01 to 100, closed form matching measured `E+` to 0.0 absolute); Thm 3.3's Eq. (7)
and unconditional negativity over 20,000 draws with n <= 4, kappa of either sign in [0.25, 14], worst
relative deviation 2.2e-12, plus the reduced-mass identity to 1e-16; the kappa = 2 arithmetic including
`M(2-b) > m(1+b)^2` at 21 points; the theta boundary at 18 crossings; Prop. 3.4's divisor in exact
rationals; the kappa = 1 exactness to 12 digits; `y = rho - 1` symbolically; `rho_mid`; the
residual-blindness identity; and all the count arithmetic. **Disagrees with the paper on:** Eq. (6) as
printed, and the "four times / half" pairing. **Could not reconcile from the PDF:** T10's 9,900 versus
300/300 versus the body's 19-of-2000; T3's 288 versus "288 live cells"; the hidden m = M; the 0.979
coefficient; Fig. 3's `rho_mid` label; and Fig. 1's 1,707 J at 114 ms paired with a run-maximum rise
that the video shows occurring around 275 ms.

**Video.** Read 12 frames, the most of any reviewer. *"Two independent runs of one host from identical
states at one fixed budget ... differing only in the modal contact row's weight."* On control: *"Yes on
the axis it claims, and better than most"*, with the missing third arm and the unlabelled worst-case
operating point as the two gaps. *"1 iteration x 8 substeps is a legitimate small-steps operating point,
but the reader should be told the effect is a strong function of the budget within the range hosts
actually use."* On disclosure: *"Excellent, and materially better than the paper."* Net: *"Yes, upward,
and by enough to matter. Before the video I was at a weak reject ... It also independently corroborated
my derivation that the matched charge is twice, not four times, the converged midpoint charge."* Did not
move further because *"it gives no evidence for the title's lead contribution, omits the third arm, and
cannot substitute for the missing scene parameters or the undefined governor."*

**Novelty.** *"Correctly sized, and unusually so."* Searched for prior statements of the kappa-dependent
matched charge and the one-sweep sign boundary in the PBD/XPBD and constraint-solver literature *"and
found none."* Credits the co-simulation distinctions as *"the right distinction"*. *"The one place the
framing overreaches is the motivating quotation attributed to the Solver2D comparison, which I could not
verify and which turns a practitioner blog remark about energy creation into 'the open problem'; that is
rhetoric, not a novelty error, but at this venue people will know the source."*

**Presentation.** *"Technically clear at the sentence level and correct in almost every derivation, but
compressed to the point where auditing it is hard work and acting on it requires guessing."* Lists terms
used before or without definition (`rho_mid`, the governor, the budget pair, "live cells", the theta
set). *"Results that carry weight are stated inline inside long paragraphs rather than displayed."*
Fourteen writing defects listed, including "Ssamak Arbatani" for Siamak in [11]. On budget: *"Pages 2
and 4 are solid symbol-heavy prose with no whitespace ... Room exists without cutting content that
matters: the co-simulation history in Section 5 could lose a third, and three of Table 1's eleven rows
could move to supplement."*

**Questions.** 11, including: is the Eq. (6) bracket not `[u'Gu - w_r - 2 J_c'u - 2 alpha]`, and is the
rigid update always at kappa = 1; which is intended, four times or twice, and which midpoint
discretization gives `m(1 + b/4)`; what is the passivity governor and is it on by default; please give
the per-scene parameters and the rho / rho_mid of each of the 27 cells; what are T10's denominators and
the liveness filter and how many cells fell inside the dead band; expand the budget notation and explain
how theta = 0 can inject; how do the matched and published weights compare against the converged
reference; what does the index cost at runtime; which `rho_mid` definition is correct; where does the
[6] phrase appear; and should T11 be read as accuracy against a grid-specific fixed point.

---

### R6 -- Senior PC generalist

**Weak Accept, 7/10, confidence 4/5.** (The panel's highest score.)

*Self-described stance:* real-time character and physics systems, has shipped constraint solvers and
reads position-based Gauss-Seidel contact code fluently; not a specialist in co-simulation stability
theory or modal reduction. *"I re-derived every theorem here by hand, cross-checked with numerics, and
spot-checked the cited prior art online."*

**Contribution as understood.** A closed-form scalar predicate, evaluable before the solve, for whether
one sweep of one unilateral row from a cold start adds energy, plus the row weight matched to the host's
velocity reconstruction that makes the sweep provably lose energy and that at kappa = 1 reproduces the
fully converged implicit contact step exactly.

**Summary.** *"I checked the mathematics independently and essentially all of it holds, including the
parts the authors flag as their contributions; the defects I found are in the accuracy discussion, one
figure annotation, the bibliography and the table bookkeeping, not in the theorems."* Reservations: the
paper is *"dense to the point of being hard work for a non-specialist"*, the practical delta over the
already-shipped weight is demonstrated only at row level, the phenomenon self-heals by four to eight
iterations, and the system-level infrastructure is borrowed.

**Strengths.**
- *"The central mathematics is correct and I could verify it adversarially ... all reproduced to machine
  precision with zero misclassifications over tens of thousands of random parameter draws. That is a
  rare experience as a reviewer."*
- *"The kappa=1 exactness identity is the real jewel and it is understated. One matched sweep does not
  approximate the converged backward-Euler contact step, it equals it ... A single-iteration solver
  being exact for a class of rows is exactly the kind of result a practitioner audience can act on."*
- *"Scope discipline is exemplary ... Many papers with weaker results claim more."*
- *"The novelty claim is correctly sized, and where I could check it the prior art is characterized
  accurately."* Confirms the AVBD quotation is verbatim-correct.
- *"The paper reports the cost of its own remedy ... Self-incriminating evidence in a teaser caption is a
  strong honesty signal."*
- *"The supplementary video is one of the better-disclosed I have reviewed."*

**Ranked weaknesses.**
1. **moderate** The kappa = 2 accuracy sentence *"cannot be read consistently under one convention, and
   the paper never says at which level its converged reference enforces the contact condition ...
   The measured 1/2 is probably right; the stated reason is not the reason."* And: *"The whole thesis of
   the paper is that reconstruction and read-back conventions decide the answer. The one place where the
   paper compares against a converged reference is precisely where it leaves the convention unstated and
   then draws an inference that does not follow."* Cheap to fix.
2. **moderate** *"The paper is at the very top of the page budget ... and pays for it in readability.
   Section 3 is a wall of algebra with almost no prose scaffolding, Section 4 is a wall of counts, and
   Figure 3 carries three panels, an inset, four marker shapes, two fill states, three readout boxes,
   symlog axes and a legend that overlaps and truncates its own readout text ... the one-line takeaway is
   currently buried in the middle of a derivation."* Cheap to fix.
3. **moderate** The practical delta over the shipped weight is never demonstrated at system level.
   *"A practitioner asks: I already ship (Mq + h*Dq + h^2*Kq)^-1 and it never injected on your 24 cells,
   why change? The paper's answer is an identity plus row-level coverage, which is a good answer but not
   the demonstration a reader wants."* Not cheap.
4. **minor** Fig. 3's *"passive only where 2(w_row - w_r) <= w_r"* states a necessary condition where the
   paper's own boundary makes it only sufficient, with a counterexample. *"As printed the annotation
   licenses the wrong pre-solve conclusion."* One word.
5. **minor** Fig. 2's reconstruction is never stated. *"The most visually memorable figure in the paper
   describes an operating point the shipped host does not use, and a reader will carry away the wrong
   map."* Also notes the right panel at zeta = 0 **is** the matched weight.
6. **minor** Numbers not reconcilable across artefacts (Fig. 1 versus the video's 925,575 J and 64.5 J;
   the 89x reference disagreement; T10 and T11). *"It reads as sloppiness in a paper that is otherwise
   unusually careful about disclosure."*
7. **minor** The framing quotation is not checkable and [5] is misdated (2019 for GDC 2005). *"The
   paper's stated gap in the literature is carried by a non-archival citation the reader cannot
   resolve."*
8. **minor** The over-deposit factors require m = M, and there is no runtime cost anywhere. *"the answer
   is presumably 'free', which is a selling point the paper leaves on the table."*
9. **minor** *"The rhetoric is slightly wider than the proof, and the system-level infrastructure is
   borrowed."* On salami: *"I think it does [stand alone], because the split is theory versus system
   diagnostic rather than results salami, and it is disclosed in a dedicated paragraph. But a reader of
   this paper alone gets the phenomenon second-hand."*

**Math checks.** Confirmed: Thm 3.1 (1.2e-15 over 20,000 draws, 0 misclassifications, exact neutrality at
equality); Eq. (6) *"as printed"*, with the explicit note *"I first mis-read the -w_r term as absent from
a low-resolution text extraction; a 400 dpi render of the equation shows it is there"*, agreement to
4.0e-12 over 4,000 draws with n = 1..4 and kappa in {-2, 0.5, 1, 2, 3.7}; Eq. (7)'s telescoping and
strict negativity with no case analysis needed, plus the reduced-mass identity to 16 digits; the kappa = 2
arithmetic (0 misclassifications / 40,000 over kappa in [0.2, 4]); `M(2-b) > m(1+b)^2` (0/40,000); the
kappa = 1 exactness to 12 digits on impulse, rigid velocity, modal amplitude and modal velocity; Prop.
3.4's divisor (10201 at b = 100 matching); both relaxation boundaries (0/20,000 each); and the internal
count arithmetic including that Fig. 3's three panels agree with each other and with the body *"once read
at high resolution"* and that the `rho_mid` axis label *"is exactly the kappa = 2 instance I derived."*
**Confirmed with caveat:** the accuracy sentence, solved three ways, with the ruling that *"'four times
the charge, so half the amplitude' is not a valid inference under any single convention."*
**Disagrees with the paper on:** Fig. 3's middle-panel annotation. **Could not check from the PDF:**
T10 and T11, the [6] quotation, and the joule reconciliation.

**Video.** Read 9 frames. *"Two acts, each a two-arm A/B on one production position-based host at a fixed
budget."* On control: *"Yes, and better controlled than most ... the frames state 'independent runs,
nothing toggled mid-trajectory', which forecloses the mid-run-toggle objection ... The playback claims are
arithmetically consistent."* The missing third arm is the gap: *"The video therefore compares the paper's
fix only against the naive baseline, not against the baseline a practitioner already has."* On
disclosure: *"Unusually high, and higher than the paper's ... Act 1 even discloses that the two converged
references disagree by 89x ... which is a caveat against the authors' own scene and which is absent from
the paper."* Also flags editorial slack: *"about 50 s for two beats, with act 2 nearly static from about
31 s to 46 s. Half the length would carry the same evidence."* Net: *"No change to the score, a clear
increase in confidence ... Had the video shown rho predicted before the solve against the measured sign,
or the shipped implicit weight as a third panel, I would have moved to Accept."*

**Novelty.** *"Correctly sized, which is the main reason I am on the accept side."* Verified [24] and the
AVBD quotation. Accepts as new: the pre-solve per-row predicate, the kappa-parameterization, the kappa = 1
exactness identity (*"the most quotable result here"*), and the ordering divisor. Two soft spots:
*"the pieces are individually elementary: the algebra is a page of reduced-mass bookkeeping that a good
practitioner could reproduce in an afternoon once told to look, so the contribution is the framing and
the audit, not technical depth; that is acceptable for a short paper but a committee member may say so."*
And the framing verbs are wider than the theorems.

**Presentation.** *"The contribution is locatable in one sentence and the title is honest ... The only
over-read the title invites, that the coupling is made passive, is explicitly closed on page 1."* Below
the title level: *"the writing is precise but unfriendly ... a non-specialist PC member can extract the
contribution but has to read it twice."* Calls the paragraph beginning "Two qualifications keep the
accounting exact" *"close to impenetrable on first pass."* On figures: *"Four figures, three of which
work."* Ten writing defects listed.

**Questions.** 11, including: exactly which converged reference at kappa = 2; is Fig. 3's "only where"
intended as sufficient; what is kappa in Fig. 2 and can the kappa = 2 map be shown; what are T10's and
T11's denominators; is there any system-level point where the published weight injects and the matched
one does not, *"if no such system cell exists, please say so explicitly"*; what does the remedy cost;
where in [6] is the sentence and is [5] not GDC 2005; do the factors assume m = M; **does the shipped host
integrate the modal restoring force in the predictor rather than as a trailing compliant row**
(*"the applicability of Theorems 3.1 and 3.3 to your own host turns entirely on this. Please state it
where the theorems are introduced, not only in the C4 discussion"*); and why the paper/video divergence.

**Note on R6's downside condition, which no other reviewer raised:** *"I would drop to Borderline ... if
the shipped host turns out to solve its modal restoring force as a trailing compliant row, in which case
Proposition 3.4's (1+b)^2 divisor applies to the paper's own evidence and the injection regime narrows
sharply."* Read together with R1's and R3's finding that Prop. 3.4's passivity add-on fails at kappa = 2,
the authors should answer this question explicitly and early: it is the one place where a correction the
panel wants and a downside condition a reviewer named point in opposite directions.
