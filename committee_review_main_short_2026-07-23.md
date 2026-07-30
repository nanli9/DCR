# Six-reviewer blind panel — `main_short.pdf` + `mig_short_video.mp4`

**Date:** 2026-07-23
**Artifacts reviewed:** `paper/main_short.pdf` (built 00:44, 7 pp = 6 content + refs, CFP-compliant),
`benchmarks/paper_fig/out/mig_short_video.mp4` (53.3 s, 1920×1080, 30 fps, **no audio track**)
**Protocol:** six independent reviewers, each given only the PDF and the video. No access to the repo,
`NUMBERS.md`, prior committee reviews, prompts, or each other's reviews. Personas differ by expertise.

---

## Verdict

| # | Reviewer expertise | Rec | Score | Conf |
|---|---|---|---|---|
| R1 | Position-based dynamics / real-time rigid solvers | **Weak Accept** | 6/10 | 4 |
| R2 | Model reduction / modal dynamics | **Weak Reject** | 4/10 | 4 |
| R3 | Contact mechanics / numerical optimization | **Weak Reject** | 5/10 | 4 |
| R4 | Passivity / energy safety / haptics control | **Weak Accept** | 6/10 | 4 |
| R5 | Games practitioner / benchmarking methodology | **Weak Accept** | 6/10 | 4 |
| R6 | Senior PC generalist (venue fit, framing) | **Weak Accept** | 6/10 | 4 |

**4 Weak Accept / 2 Weak Reject. Mean 5.5/10. Median Weak Accept.**

**General advice: ACCEPT-leaning borderline.** Above the reject line, not safe. Every reviewer
was positive on the same thing (the within-host `W_q` control) and negative on overlapping,
cheap-to-fix things. No reviewer challenged the correctness of Prop. 4.1 — three verified the
induction independently and all three passed it. Nobody proposed rejection on novelty grounds.

The two Weak Rejects are not framing complaints. R2 and R3 both reject on **evidence integrity**:
a numeric inconsistency in Figure 2, a flat self-contradiction about the table scene, and a
recommendation whose only reported outcome is that the energy went away.

---

## Consensus findings (independent agreement, ranked by how many reviewers found them)

### 1. The recommended fix is never shown to preserve the vibration — 5 of 6, top-2 for all five

R1, R2, R3, R5, R6 each independently made this their #1 or #2 weakness, without seeing each other.

§3.2 reports the `W_q` swap taking the deployed ledge 4×1 from `R = 1.2×10⁵` to `8×10⁻⁵`. The
converged references elsewhere in the paper sit at `R ≈ 0.273–0.2996`. So the recommended arm
stores **3–4 orders less** modal energy than a converged solve of the same law. R2 works the
arithmetic: at h = 1/120 the implicit weight `1/(1+h·d_i+(ω_i h)²)` cuts even the ledge
*fundamental* (118 Hz, ωh ≈ 6.2) by ≈39×, and every stiffer mode by far more.

The paper devotes §4.1 to proving the *governor* buys safety by deleting the motion you wanted,
then recommends a mechanism with the same structural risk and reports no deflection, no ring
amplitude, no ring frequency, no render, and no video frame for it. R1 additionally asks whether
the separate symplectic modal-elastic constraint is still applied when the implicit weight is used
— if so the stiffness is counted twice and the arm is over-suppressed rather than corrected.

**Fix (all five converge on the same one):** one figure row or table line — peak deflection and
recovered ring frequency for the weight-swapped arm against the implicit reference, at the cells
where `R` is already reported. R5: *"This single answer is the difference between a Weak Accept and
an Accept from me."* R6: *"Answer question 1 affirmatively with a trajectory comparison and I would
argue for it."*

### 2. Figure 2's margin panel cannot be reconciled with §4.1 — R1 and R3, independently; verified

Both reviewers derived the same contradiction from different directions, and it checks out:

- §4.1: *"At a moderate injecting cell (shelf, 8×2, relaxation 0.7) peak modal energy is **1555.6 J**
  ungoverned."*
- Fig. 2, bottom panel, shelf 0.7 / 8×2: margin **+1824 J**.

With `E⁰_mod = 0` (stated in §2), `η = 1`, and a supply that is a sum of `max(·,0)` terms, the
margin `E_mod − Σc` can never exceed the peak modal energy. 1824 > 1555.6.

Same test on the ledge: 0.7 / 8×2 shows `R = 47.5` against the stated incident 371 J → peak
`E_mod ≈ 1.8×10⁴ J`, while the margin panel reads **+2×10⁵ J**, 11× larger. Ledge 1.0 / 8×2
(`R = 168`, +4e5) implies 2381 J of incident KE against 371 J stated.

R3 confirmed the same ratio test **passes** for the other six violating cells (shelf 4×1: 31.6 and
30.0 J; ledge 4×1: 333 and 400 J — all within ~15% of mgh), so this is specific, not a rounding
artifact, and cannot be explained by rounding "+2e5" down by 6–11×.

The most likely benign explanation (R1) is that `R` is windowed to the impact while the margin runs
over the whole run including settling — §3.1 does say the host *"already injects 10³ J from resting
settling alone."* **But if that is the answer, the celebrated 8/24-vs-9/24 disagreement, which
Fig. 2's caption calls "itself a result," is partly an artifact of two measurement windows rather
than a property of two diagnostics.** Either way this must be stated in the caption and the two
panels recomputed on a common window.

R3: *"a diagnostic paper's contribution is its numbers... I cannot recommend acceptance while the
central figure self-contradicts."* This single item is most of the gap between the Weak Accepts and
the Weak Rejects.

### 3. Flat contradiction about the table scene — R2, R3, R5, R6; verified verbatim

Within §3.1, two pages apart:

- p. 3 col. 1: *"the table, **which never injects on any host**, does not [carry modes three to four
  orders above the substep rate]."*
- p. 3 col. 2: *"the largest augmented-Lagrangian one (**6.7 J, at the starved 4×1 table corner**)"*
  and *"the augmented-Lagrangian host being the worse **on the table** (1.70 against 0.37)."*

`R = 1.70 > 1` and `+6.74 J > 0` on the table. Both sentences cannot be true. The table is the
paper's own negative control for the whole mechanism story, so this is the worst possible place for
it. Compounding it, §3.2's *"violates (2) in all six deployed cells"* (3 scenes × {1×8, 2×4})
includes table cells the sweep reports at the roundoff floor.

Related, and separately flagged by R1/R3/R4/R6: the mechanism does not separate the control anyway.
The table's `ω_max h ≈ 2.7×10²` gives `(ωh)² ≈ 7×10⁴` from Eq. (4) — the stiffness-blind
over-estimate is present there at four orders of magnitude — yet the table is benign at every budget
on every host. Eq. (4) is at best necessary, not sufficient, and the "three to four orders vs. not"
split is a rhetorical threshold rather than a derived one. The table also has the *largest* stiff
cluster (14/24) and the *most* support rows (200), so something unmeasured is doing real work.

### 4. The 200 GPa board in the video is in no section of the paper — 6 of 6

Video beats 2–3 are titled *"STIFF board (E = 200 GPa) (steel)"*. §3.1's three scenes are
0.5 / 10 / 1.1 GPa. The beat that establishes "the problem is real," and which consumes roughly a
fifth of the runtime, is a fourth unreported configuration. The video does disclose it — beat 5's
footer reads *"SOFTER board, E = 0.5 GPa (a different board from beat 2, and the one in Fig. 1)"* —
which every reviewer credited as honest, and every reviewer still flagged, because §3 says *"the
supplementary video shows the comparisons at true scale"* and a viewer carries beat 2 forward.

### 5. The video's closing card gives the opposite advice from Figure 4 — R1, R2, R3, R6; verified

| | Box 1 |
|---|---|
| **Video card** (t ≈ 48–53 s) | "Contact architecture flexible? **Use a stiffness-aware implicit / velocity contact realization.** observed control: 0/24 overdraws, converges by K = 2" |
| **Paper Fig. 4** | "Can you change the contact row? **Make its modal weight stiffness-aware: implicit (M+hD+h²K)⁻¹, not 1/M.** within-host control: 8/24→0/24 overdraws, **no host swap**" |

The video recommends swapping hosts, citing the confounded cross-host strip. The paper recommends
*not* swapping hosts, citing the within-host control — and the Conclusion says *"the real question
is not XPBD versus another solver but the contact-row weight,"* while the video's own subtitle says
*"not a solver ranking,"* which its own box 1 then is. Boxes 2 and 3 match the paper exactly, so
this is a stale box 1, not a design disagreement. **Highest fix-value-per-minute item in the whole
package.**

### 6. Warm start: text says 3.1×, Fig. 3(a) shows ~1.5–1.6× — R1, R2, R4, R5, R6

Five reviewers measured the annotated warm-start marker against the cold K=4 point off the plot at
600 dpi and independently got ≈1.5–1.6×, against §3.1's *"3.1× worse at 4×1."* Either the 3.1× is a
different cell or a column aggregate — say which, and label both values on the plot.

### 7. §5 undercuts the premise and the guide has no box for it — R1, R2, R3, R5, R6

*"the reduced model therefore captures 38% of the reference peak"* and *"the deployed 1/120 aliasing
the recovered ring to 47.25 Hz"* against 78.3 Hz — 2.6× wrong in amplitude, 40% wrong in frequency,
on a **richer k=24 basis than the sweep's rank-16**, so the deployed case is worse than 38%. R1
notes the two recommendations then pull against each other: fidelity is fixed only by refining Δt,
i.e. by the substeps box 2 tells the reader not to buy. R5 and R6 both propose the same fix — a
**box 0** ("is the reduction valid at your Δt?") ahead of box 1.

Three reviewers (R2, R3, R4) separately object to the word **"aliasing"**: at Δt = 1/120 with S = 4
the substep rate is 480 Hz, so a 78.3 Hz ring is ~6× oversampled and cannot alias. This is
integrator frequency warping, which is a different and more interesting statement.

R2 adds a check nobody else ran: §3.1 gives the ledge's retained band as **118 Hz**–191 kHz, but §5
recovers a **78.0 Hz** ring from a *superset* basis on the same ledge. If the k=24 set is genuinely
richer, its minimum cannot be lower than the rank-16 set's. Needs reconciling or the retention rule
needs describing.

### 8. Abstract ranges are not checkable from Table 1 — R1, R2, R3, R5, R6

*"from 2.4–47.6× the truncated solve's own to 1.0–6.3×."* The four printed rows give 2.41–12.86×
(scaled) and 1.00–2.02× (preserved). The extremes carrying the abstract — 47.6× and 6.3×, i.e. 3.7×
and 3.1× beyond anything printed — live only in the unshown relaxation-1.0 rows. The parenthetical
*"(both relaxations; Table 1 shows the 0.7 rows)"* is honest, but in a paper whose entire value is
measured numbers, a four-row table should carry the rows the abstract cites.

### 9. "90 measured cells" contains 12 bit-identical duplicates — R4, R6

§4 is transparent (*"72 sweep executions (60 distinct...)"*), but the abstract, contribution (3) and
Fig. 4 all quote 90 without the qualifier. Distinct count is 78.

### 10. The 8/24 vs 9/24 slip — R3, R5

Fig. 2's caption makes the R-count (8) and the Eq. (2) count (9) a headline result, then §3.2 and
Fig. 4 box 1 both report the weight swap as *"8/24 → 0/24 **overdraws**"* — the R-count under the
Eq. (2) word. Either the swap arm was only evaluated on the eight `R > 1` cells (leaving the ninth,
shelf 1.0 / 16×4 at +5×10⁻³ J, unchecked) or the terminology slipped. R3 further argues the 8-vs-9
framing is oversold: the extra cell has a **5 mJ** margin, and the paper establishes an accounting
floor of 10⁻³ J for the AVBD/implicit hosts *only*, explicitly stating the position-based host *"has
no small floor."*

---

## Reviewer-specific findings worth acting on

**R3 (contact/numerics) — the block-condensation ablation is probably measuring the wrong thing.**
Reading Fig. 3(c) directly, both block curves are **non-monotone in K at fixed S**: shelf block goes
2.5 (16×4) → 12.5 (32×1) and ledge block 7.5 → 66, while both serial curves *fall* over the same
change. Iterating a block correction and getting worse is the signature of an over-relaxing
simultaneous (Jacobi-like) projection, not of a "worse convergence path." An exact Schur
condensation should reach the coupled fixed point in *fewer* iterations than serial Gauss–Seidel,
not 700× worse at identical K and S. The condensed operator is also built on the same stiffness-blind
`W_q = I` the same subsection identifies as the cause. The abstract still asserts *"better spent on
iterations than on substeps or a block solve"* on this evidence. **Ask:** is the m×m system solved
exactly, is any under-relaxation applied, and what is its per-iteration cost?

**R3 — Prop. 4.1 is correct but omits three assumptions.** All three reviewers who checked the
induction (R3, R4, and R2 partially) passed it, including the same-substep credit ordering and all
three projection branches. R3's gaps: (a) the projection's ordering relative to the shared
implicit-midpoint modal restoring step is never stated — if the restoring step runs *after* the
projection within a substep, it can lift `E_mod` above `Ē`; (b) `E∓_mod` is ambiguous as to whether
the "+" endpoint is pre- or post-projection; (c) `U_c K⁻¹ U_cᵀ` is **singular** whenever the engaged
row count exceeds r (16 or 24, against 48/40/200 instantiated rows), so a pseudo-inverse is required
but the paper writes the system as invertible. One sentence each.

**R4 (passivity) — the reservoir has no ceiling and no leak, and the accrual is never measured.**
This is the one place the paper departs from the tank literature it adapts: energy tanks cap `B`
from above precisely so accumulated credit cannot fund a future burst. §6 concedes *"It is also
uncapped, so (2) bounds a run, not a limit,"* and Eq. (3) sums over **all dynamic bodies, not only
those in contact**, so in a crowded scene the prop's budget is credited by every unrelated collision
in the level. In Fig. 1 the budget line is flat at ≈30 J from t ≈ 0.25 s — one 29 J impact buys ≈30 J
of permanent, non-expiring headroom for a prop whose converged ring is 8.22 J. All three test scenes
are ~0.8 s with one impactor, the most favourable possible case, and no long-horizon or
repeated-impact run appears anywhere. **Prop. 4.1 survives unchanged with `B ← min(B, B_max)`** —
R4 calls the B_max sweep the single experiment that converts *"bounds a run"* into something a
practitioner can rely on, and notes Fig. 4 box 3's header *"Need a hard energy guarantee?"* is where
"hard" outruns the mathematics.

**R4 — quantitative verdict on how tight Eq. (2) actually is** (the most useful single paragraph in
the panel): *not vacuous, but ~4× loose where it binds and unbounded in the limit that matters.*
Where it binds it works (22,352 → 30.2 J, 740×). Its residual slack against ground truth is
3.6–3.7× (28.7 J governed vs 7.92 J reference; 30.2 vs 8.22). In incident-energy terms it permits
`R = 1.70` — 70% **more** than the impact delivered — and 1.70 is *identical* to the AVBD host's
worst ungoverned R, i.e. on that host the governor reduces the worst ratio by nothing. §4 reports all
90 governed cells at the roundoff floor and §4.1 concedes the projection *"stores what the bound
permits rather than the least it can,"* so the tightness of the guarantee **is** the tightness of the
budget, with no margin of its own.

**R4 — the AVBD host's supply is not dissipation, and it is disclosed in one clause.** §6:
opposite-channel exposure *"reaches ... **102–118% on the augmented-Lagrangian host**."* Exceeding
100% means net dissipation on that host is ≤ 0 and the entire reservoir is funded by recycling — so
on that host Prop. 4.1 is an accounting identity, not a safety statement. A reader of Fig. 2's
control strip ("AVBD 2/24 | 3/24, +6.74 J") comes away thinking that host is nearly benign, which is
what §6 quietly retracts. **Fix:** annotate the exposure percentage directly in the control strip.

**R4 — Fig. 2's margin panel cannot show slack.** Every non-violating cell reads −1e-16 to −8e-16 J,
i.e. numerically zero. A safety reader cannot tell whether the implicit host passes with 1 J or
1000 J of slack. Plot the margin normalized by supply, or the minimum slack.

**R4/R5 — the supply is never reported in joules anywhere.** "Overdraws by 4.4×10⁷ J" is
uninterpretable in isolation: 4.4×10⁷ J against a 10 J supply and against a 4×10⁵ J supply are very
different findings, and on a diverging run the supply is itself inflated by the artifact.

**R2 (modal) — the bases are unreported and the band-limiting control is incomplete.** No
eigen-spectrum, no boundary conditions, no mesh resolution, no Poisson ratio, no Rayleigh
coefficients — and `d_i` enters Eq. (4) directly, so the central mechanism equation has an
unspecified parameter (R5 independently). R2 also finds the spectra implausible: 16 modes spanning
118 Hz–191 kHz is a 1619× frequency ratio inside the first 16 modes, and a 2.2 × 1.1 m table at the
stated E and ρ should have a ~20 Hz fundamental, not a 4.7 kHz floor. Most importantly: *"Removing
the stiff cluster" is not band-limiting* — the residual band after removal is never reported, and the
control the paper needs is **R and the Eq. (2) margin as a function of a cutoff expressed in
`ω_max h`** (≤ 1, ≤ 0.3). Without it, "the failure is the row weight rather than the fixed budget" is
established but "and not simply the basis" is not. R2: *"I would raise my score substantially if it
comes back showing injection survives a real band limit."*

**R2 — the row that fails may not be the row [19] gives.** §1 says the row is *"one linearization
step from the velocity-level law ... same Jacobian and multiplier as Zheng and James [19],"* but [19]
resolves against the reduced effective mass of the implicit step, not `M_q⁻¹ = I`. So the single
ingredient identified as the lever is itself a departure from [19], and "we take the row as given" is
inaccurate — the row as given is the stiffness-aware one. Doesn't invalidate the measurement,
materially changes what the title and abstract are entitled to claim.

**R1 — the equal-row comparison is conservative in the paper's favour, and the paper never says so.**
A cell is scored at K·S row evaluations, treating an iteration and a substep as equal cost. But these
hosts use per-substep contact regeneration, so 4×8 is *strictly more expensive* in wall clock than
32×1. The iterations conclusion is understated, not overstated. Say it.

**R1/R5/R6 — "prefer iterations over substeps" is one data point promoted to a rule, and by the
paper's own data it does nothing where the paper says the problem lives.** One pair (shelf, 0.7,
32 evals). §3.2 then says deployment is 1×8–2×4 and *"the position-based host violates (2) in all six
deployed cells."* At 8 row evaluations, reallocating them changes nothing. R5 adds the shipping
objection: **S is not a per-constraint knob** — moving 1×8 to 8×1 changes joints, stacking,
penetration and tunneling for every other constraint in the level, and directly opposes the
small-steps guidance the paper itself cites [13] as the reason 1×8–2×4 ships. None of that collateral
cost is measured. R5/R6 also note §3.2's *"Substeps do reduce the ratio (Fig. 3a), roughly 2200× over
the same range"* cites a figure containing **one** substep point and no substep curve — the video's
beat 3 has the correct two-curve plot and the paper dropped it.

**R5 — severity is measured in joules; the product is pixels.** 24 cells of energy, two anecdotal
visuals, and the paper itself proves the metrics don't track (§4.1: *"a 196× energy error coexists
with a peak deflection only 1.2× too large"*; 99.6% of the excess is above 20 kHz). A developer
cannot read any cell of Fig. 2 and know whether the shelf explodes or hums inaudibly. **Fix:** add a
geometric severity column to Fig. 2 — max spurious body displacement vs. the self-reference, per
cell. That is the number a developer triages on.

**R5 — the decision card has no cost axis and the cost that exists does not transfer.** §5's numbers
are CPython float64 ratios. R5's verdict splits cleanly: single-machine is **acceptable and arguably
correct** for the solver-behaviour results (the FP-reassociation justification is real, determinism
matters more than platform breadth for an energy ledger — R5 would not require a second machine), but
**not acceptable** as the cost basis for a guide at a games venue, since a percentage overhead in
CPython carries zero information about a C++ host, which is the only host a MIG reader has. Fixable
without new hardware: report flops per substep as a function of r, m and active-row count, persistent
bytes, and eigensolve time, and put one cost line on each Fig. 4 box. Also flags *"the same
∼0.3–2.2 ms"* against *"0.23–0.41 ms"* — 2.2 ms is 5× the upper end, and the ledger runs per substep,
so 8 substeps vs 4 should roughly double it, not quintuple it.

**R5 — untested scaling that the paper's own introduction predicts is worse.** §1 argues *"every
support contact touches the same global q, making the contact-row graph dense on the modes."* That
gets strictly worse with **several modal props sharing one iteration budget**, and nothing tests it.

**R5 — reproducibility: not reproducible.** Scenes are re-derivable (E, ρ, impactor mass, drop
height, modal rank, stiff-cluster size, mode bands, row counts, Δt, S, η, `α_sup` — more parameter
disclosure than most submissions). Solvers are not (no code, no pseudocode beyond Eqs. 1/5, no
Rayleigh coefficients, no mesh or element details, no friction settings). Five load-bearing pointers
go to supplementary material that is not offered: the 72-cell heatmap, the full host table, the
entire E6a-1 condensation ablation behind Fig. 3(c), and the corrective-transient data. There is **no
code-release statement anywhere in the paper**. R5: an anonymized code drop would change the score.

**R6 — the paper's frame contradicts its own mechanism section.** Contribution (2) says the ablations
localize the amplification to *"finite-budget convergence of the shared coupling."* §3.2 concludes it
is the stiffness-blind row weight *"rather than of the fixed budget as such."* The title foregrounds
"Fixed-Budget XPBD." These cannot all be the headline; the truth is a conjunction, and the paper's
strongest, most actionable finding — a budget-independent one-line weight change — is buried mid-
section under a negative frame. R5 makes the same point from the practitioner side and recommends
retitling around the row weight.

**R6 — the paper is too dense to referee comfortably.** ~200 distinct numeric results across ~5.3
body pages (~38/page), before Fig. 2's 48 cells and Table 1's 28 entries. §4.1 carries 10 numbers in
63 words. Each solver has 4–6 aliases ("implicit" / "the implicit host" / "the implicit realization"
/ "a sequential-impulse realization" / "the impulse realization"), and **two different things are
called "the reference"** (host 1 at K=500 and host 3 at K=500). R6: *"I read this paper three times
and had to build a name table to keep the hosts straight."* **Fix:** fix one name per host in a
sentence in §3.1, and move a third of the parenthetical numbers to the supplement.

**R6 — scope overstatement in the abstract.** *"Across three scenes ... overdraws"* — the table never
overdraws on any host at any budget. Should read "in two of three scenes." That one of three scenes
is entirely benign is exactly the scoping a practitioner needs up front.

**R6 — the headline number is not from the deployed regime.** 4.4×10⁷ J is ledge 1.0 / 4×1. The
deployed 1×8–2×4 cells get only *"worst R = 2282"* — and the paper insists R and the margin are
distinct diagnostics, so the invariant's value in the regime the paper argues is common is never
reported in joules.

**R6 — Table 1's `λ var.` column (50×, 61×) is never defined or referenced in the prose.** Variance
of what, over what window, against what baseline?

**R4/R6 — Fig. 1 mixes instantaneous and peak without saying so.** The header pins the instant
(t = 0.42 s), in-panel labels read "+93 mm" / "+19 mm" and in-plot annotations "46 J" / "0.94 J",
while sub-panel captions read *peak* 22,352 / 30.2 / 8.22 J — a 740× ratio printed next to a 49×
ratio from the same run, with the caption's *"same initial state, camera, instant and scale"*
foreclosing the "different runs" reading. Reviewers reading the video's beat 5 got +32 → +23 → +9 →
+0 mm for the self-reference through that window and could not locate 19 mm at that instant. R4
notes the **run peak (32 mm) makes the paper's own case 1.7× more strongly** than the 19 mm quoted.

---

## Video supplement — consolidated

Structure (all six agree it is well chosen and mirrors the paper's argument order): architecture
build-up (0–7 s) → stiff-board failure (7–17 s) → equal-row iterations-vs-substeps (17–25 s) →
band-limited-basis dumbbell (25–33 s) → guardrail title (33–35 s) → three-arm soft-board impact
(35–43 s) → penetration schematic (43–47 s) → decision card (47–53 s).

**What works.** Legible at 1080p; consistent colour coding (orange ungoverned / blue governed /
dashed self-reference); *"true scale"* and *"independent runs from identical reset states"* stamped
on every dynamic beat — repeatedly credited as exactly the right disclosure. Silence is
**appropriate** and drew no objection: the coupling is normal-only, nothing depends on audio, and
title cards carry the narration. Several numeric spot-checks match the paper **to the digit**: beat 7
reproduces Table 1's shelf 4×1 row (6.2 / 21.6 / 8.3 mm, 8.3/30 = 28%); beat 3 reproduces
"32×1: R = 0.30 holds" and "4×8: R = 3.13, +481 J"; beat 4 reproduces "6 of 8 injecting cells still
overdraw (worst +1.24×10⁶ J)"; beat 8 reproduces 90/90 and 17.8 mm. Two reviewers note beat 5's plot
is **better than Fig. 1** — it carries a complete four-entry legend where Fig. 1 leaves the dashed
self-reference curve unlabelled. Two reviewers say the beat-3 two-curve plot is **better evidence
than what the paper prints** and should be promoted into Fig. 3.

**Problems, ranked:**

1. **The closing card contradicts Fig. 4 on the central recommendation** (consensus #5 above). Stale
   box 1. Re-render from Fig. 4's text. Highest value per minute in the package.
2. **The 200 GPa board is in no section of the paper** (consensus #4), and it consumes ~a fifth of
   the runtime as the video's opening demonstration.
3. **Beat 2's assertion overshoots its own footage.** The card promises *"At a production-like 1×8
   budget, they are launched."* Reviewers sampling that beat at 2–3 Hz across its sim window
   (t = 0.19 → 0.83 s) measured book displacement peaking at **+5 to +14 mm** and reading +0 mm in
   most frames, with the closing frame captioned *"the launch is spurious."* The energy claim is
   supported (E_mod sits 2–3 decades above the budget line); nothing is launched on screen. The real
   +93 mm launch is beat 5, 25 s later, on a different board. R5 notes, wryly, that beat 2 is
   unintentionally the strongest on-screen evidence that joules are a poor proxy for pixels.
4. **The video never shows the recommendation.** The stiffness-aware `W_q` arm — Fig. 4 box 1, the
   thing the paper actually tells you to do, and the paper's single strongest result — appears
   nowhere. **Replacing beat 2 with an ungoverned / weight-swapped / self-reference triptych fixes
   problems 2, 3 and 4 in one edit, and answers consensus finding #1.** Four reviewers proposed
   exactly this independently.
5. **Instantaneous-vs-peak labels drift between video and paper** (Fig. 1's +19 mm; the 23.4 / 0.9 /
   0.5 J instantaneous readouts against Fig. 1's 22,352 / 30.2 / 8.22 J peaks). Nothing is wrong; a
   viewer moving between the two cannot connect them. Label both as peaks, or annotate
   "instantaneous."
6. **Motion budget is thin for a venue named Motion** (R6, from a frame-to-frame activity trace):
   substantive geometry motion occurs only at ~6–11 s and ~32–38 s — roughly **11 of 53 seconds**
   contain moving geometry. Beat 2 holds a frozen image ~6 s; the closing card is static ~5 s.
7. **Pacing is misallocated.** Beat 2 gets the most time and is the least informative; beats 3, 6 and
   7 are text-dense and under-held (beat 7 carries ~60 words plus six diagram labels in ~5 s, which
   needs ~600 wpm). Reclaim ~6 s from beats 2 and 8 and give them to 3 and 6.
8. **One framing overreach.** Beat 2's subtitle calls the 500×1 self-reference *"the only honest
   baseline for how much the row injects."* §3.2 is more careful — the self-reference plateaus at
   0.2996, *"a fixed point 2.6×10⁻² above the reference's 0.2735,"* and the paper deliberately keeps
   **two** references to separate a truncation pathology from a discretization difference. The video's
   claim is stronger than the paper's.
9. **The 3D viewports are ~400×300 px in frame,** so millimetre claims are sub-pixel. Zoom them.
10. **Housekeeping:** the internal CSV filename (`projection_validity_arms_r07.csv`) is on screen in
    beat 7 and should go; in the penetration schematic the 6.2 mm and 8.3 mm dashed lines are drawn
    at true scale and are visually indistinguishable, so *"the guardrail amplifies the residue"* is
    invisible — add an inset.
11. **Nothing in the video shows the AVBD or implicit hosts,** so Fig. 2's headline "scale gap" is
    never illustrated. One 5 s three-host strip would carry it.
12. **Two shots the paper most needs and does not have** (R4): a governed run under repeated impacts
    over ≥10 s with the budget curve visible, and a resting stack under the governor showing whether
    Table 1's 50–61× λ variance and 6.9–8.8× impulse spikes read as visible jitter.

---

## Recommended action order

**Must fix before submission (correctness / integrity):**

1. Reconcile Fig. 2's margin panel with §4.1 (1824 vs 1555.6 J; ledge +2e5 vs R = 47.5). State each
   panel's measurement window in the caption; if they differ, recompute both on a common window and
   re-examine whether the 8-vs-9 disagreement survives.
2. Fix the table-scene contradiction ("never injects on any host" vs the 6.7 J / R = 1.70 table
   corner), and restate Eq. (4) as necessary-not-sufficient — or name the second variable.
3. Re-render the video's decision card box 1 from Fig. 4's text.
4. Fix "across three scenes" → "in two of three scenes" in the abstract and contribution (1).
5. Resolve the warm-start 3.1× vs Fig. 3(a) ~1.5×.
6. Reconcile contribution (2) ("finite-budget convergence") with §3.2 ("rather than of the fixed
   budget as such").

**Highest score-movement per unit effort (all six reviewers, likely already on disk):**

7. Add peak deflection + recovered ring frequency for the **weight-swapped arm** against the implicit
   reference. Five of six reviewers named this the single thing most likely to move their score, and
   two said it alone would move them to Accept.
8. Swap video beat 2 for an ungoverned / weight-swapped / self-reference triptych on a board that is
   in the paper. Fixes four video problems and illustrates item 7.

**Strong additions if space and time allow:**

9. One truncation ladder in `ω_max h` (R2 — decides whether this is a row-weight paper or a
   basis-selection paper; R2 explicitly offers a substantial score increase).
10. A `B_max` tank-ceiling sweep + one ≥10 s repeated-impact run with B(t) plotted (R4 — converts
    "bounds a run" into a practitioner-usable statement; Prop. 4.1 survives `B ← min(B, B_max)`
    unchanged).
11. A geometric severity column in Fig. 2 (R5 — max spurious displacement vs self-reference per cell).
12. Language-independent cost (flops/substep vs r, m, active rows; persistent bytes; eigensolve time)
    and one cost line per Fig. 4 box.
13. Fig. 4 "box 0": is the reduction valid at your Δt? (R5, R6 independently.)
14. Report the supply in joules; annotate AVBD's 102–118% opposite-channel exposure in the control
    strip; add the relaxation-1.0 rows to Table 1; define `λ var.`; fix "aliasing" → integrator
    frequency warping; qualify "90 cells (78 distinct)"; one name per solver host.
15. Prop. 4.1: state the projection's ordering vs the restoring step, disambiguate `E∓_mod`, and note
    the pseudo-inverse for `U_c K⁻¹ U_cᵀ` when engaged rows exceed r.
16. A code-release statement.

---

## Per-reviewer bottom lines and author-facing questions

Every substantive weakness, quote and number from all six reviews is consolidated above with
per-reviewer attribution. What follows is each reviewer's own verdict paragraph and their explicit
questions to the authors — the parts a rebuttal has to answer directly.

---

### R1 — Position-based dynamics / real-time rigid solvers · Weak Accept · 6/10 · conf 4

> The core finding — that a stiffness-blind modal inverse mass in an XPBD contact row over-displaces
> stiff modes by (ω_i h)², and that a within-host swap to the backward-Euler effective inertia removes
> the overdraw in every injecting cell — is correct, useful, non-obvious, and cleanly demonstrated by
> the one control that matters. That alone justifies a MIG short paper, and the honesty about limits is
> a genuine asset. What holds it at Weak Accept rather than Accept is that the headline recommendation
> is validated only on the energy axis (does the prop still ring?), that the second recommendation
> rests on a single equal-row pair and by the paper's own data does nothing at the budgets it says
> practitioners use, that Figure 2's two panels do not reconcile, and that the shipped video advertises
> an undocumented scene and a decision card that contradicts Figure 4.

**Questions.**
1. Fig. 2 ledge/0.7/8×2: R = 47.5 against a 371 J incident implies peak modal energy ≈1.8×10⁴ J, but
   the margin panel reports +2×10⁵ J. Shelf/0.7/8×2 reports +1824 J against §4.1's 1555.6 J peak.
   With E⁰_mod = 0 and a non-negative supply, how can the margin exceed the peak? If the panels use
   different windows, does the 8-vs-9 disagreement survive a common window?
2. When you swap in W_q = (M_q+hD_q+h²K_q)⁻¹, is the separate symplectic modal-elastic constraint
   still applied in the same substep — is the stiffness counted twice, and is that why ledge 4×1
   drops to R = 8×10⁻⁵? What is the weight-swapped arm's peak deflection against the §5 FEM
   reference?
3. The table has ω_max h ≈ 2.7×10² ≫ 1, the largest stiff cluster (14/24) and the most support rows
   (200). Why does it never inject? And if it injects at the deployed 1×8/2×4, why at h = 1/960 but
   not at h = 1/120?
4. Was any constraint averaging / mass splitting applied to the shared q across the 48/40/200 rows
   that write to it? If not, how much amplification survives when it is?
5. Wall-clock for 32×1 vs 4×8, and maximum penetration on the non-modal contacts under each?
6. Does the equal-row inversion hold on the ledge and table, and at relaxation 1.0?
7. Fig. 3(a): the warm-start marker sits ≈1.5× above the cold K=4 point; the text says 3.1×. Which
   cell?

---

### R2 — Model reduction / modal dynamics · Weak Reject · 4/10 · conf 4

> What keeps it out today is that the paper's central claim — that this is a contact-row-weight failure
> at a fixed budget rather than a basis-selection failure — is not tested against the obvious
> alternative, on bases that a modal-reduction reader will not accept as reasonable (191 kHz modes at a
> 120–960 Hz step, one scene whose reported spectrum is physically implausible), plus a flat
> contradiction about the very scene used as the negative control. Everything needed is cheap. If the
> ladder shows that a properly band-limited basis still overdraws, this becomes a solid, honest short
> paper and I would move to Accept; if it shows band-limiting alone fixes it, the paper is still
> publishable but must be retitled and reframed as "how to choose the basis", with the guardrail
> demoted further. As written, the within-host control and the numeric discipline are real, which is
> why this is a weak reject rather than a reject.

**Questions.**
1. What is the retention rule and what are the eigen-spectra? How do 16 ledge modes span
   118 Hz–191 kHz (1619× inside the first 16), and how does a 2.2 × 1.1 m table have no retained mode
   below 4.7 kHz? BCs, mesh resolution, Poisson ratio, Rayleigh coefficients?
2. If the basis is truncated by a step-aware criterion (ω_max h ≤ 1) rather than "drop the stiff
   cluster", do the injecting cells still overdraw? **This decides what the paper is about, and I
   would raise my score substantially if injection survives a real band limit.**
3. Does the table inject or not? Reconcile "never injects on any host" with the +6.74 J / R = 1.70
   table corner, and state which cells "all six deployed cells" covers.
4. Under the stiffness-aware weight, what is the peak deflection and ring amplitude relative to the
   reference? R = 8×10⁻⁵ is 3–4 orders below the converged R ≈ 0.27–0.30 — does the prop still
   visibly vibrate, or does the fix buy passivity by making it rigid?
5. §5 recovers a 78.0 Hz ring from a ledge basis whose stated lowest retained mode is 118 Hz. Which
   is wrong? And justify "aliasing" rather than integrator frequency warping for 47.25 Hz.
6. Given that W_q = I is itself a departure from the reduced effective mass used in [19], is it
   accurate to describe the row as "same Jacobian and multiplier as Zheng and James"?

---

### R3 — Contact mechanics / numerical optimization · Weak Reject · 5/10 · conf 4

> The scoping, the instrumentation and the honesty are at accept level for a MIG short paper, and
> Prop. 4.1 is genuinely correct — I checked both branches of the induction, all three branches of the
> projection, and the tolerance argument. What keeps it below the line is that a diagnostic paper's
> contribution *is* its numbers, and two of the eight violating cells in the central figure cannot be
> reconciled with §4.1 or with the paper's own stated incident energies; on top of that, the
> recommendation the abstract and Fig. 4 lead with is supported only by injection vanishing and never
> by the target vibration surviving, the mechanism fails to separate the paper's own negative control,
> and the block ablation most likely measures an unrelaxed simultaneous projection rather than
> condensation. Resolving Q1, adding a fidelity number for the weight-swap arm, and either fixing or
> de-claiming the block ablation would move this to Accept — I would raise to 7/10.

**Questions.**
1. Reconcile Fig. 2 with §4.1 for shelf/0.7/8×2 (+1824 J margin vs 1555.6 J peak), ledge/0.7/8×2
   (R = 47.5, +2e5 → implies 4210 J incident) and ledge/1.0/8×2 (R = 168, +4e5 → 2381 J) against the
   371 J stated in §3.1. Is the R denominator fixed at pre-impact incident KE or re-measured per cell?
2. For the weight-swapped arm: peak deflection, ring amplitude and ring frequency against the
   implicit reference, at the cells where R is reported.
3. Block condensation: is the m×m system solved exactly, is under-relaxation applied, what is its
   per-iteration cost, and why do both block curves *increase* from 16×4 to 32×1 while both serial
   curves decrease?
4. Why does the table not inject, given ω_max h ≈ 2.7×10² makes Eq. (4) ≈ 7×10⁴ there?
5. Is the projection applied after the implicit-midpoint restoring step within a substep, and is
   E⁺_mod measured before or after the projection?
6. §5 says "one m×m solve per clamped substep (m ≤ 8)" while §2 instantiates 48/40/200 rows. How many
   rows are simultaneously engaged, and is U_cK⁻¹U_cᵀ pseudo-inverted when the count exceeds r?
7. Does the weight swap remove the ninth (margin-only) cell, shelf 1.0/16×4 at +5×10⁻³ J, or was the
   arm evaluated only on the eight R > 1 cells?
8. Was the video's 200 GPa board part of any reported sweep, and can the 19 mm / 9 mm self-reference
   discrepancy between Fig. 1 and video beat 5 be resolved?

---

### R4 — Passivity / energy safety / haptics control · Weak Accept · 6/10 · conf 4

> The diagnosis is the paper and the diagnosis is good... Proposition 4.1 and Eq. (5) are correct, and
> §6 is the most candid limitations section I have read this cycle. What keeps it at weak accept rather
> than accept is the third contribution: an uncapped, non-leaking, globally-credited reservoir whose
> slack grows without bound and is never measured; a bounded scalar the authors' own video shows to be
> a poor proxy for the artifact; a host on which the supply is demonstrably recycled energy rather than
> dissipation, disclosed in one clause; and no experimental separation from the frame-rate clamp it
> distinguishes itself from in prose. Adding a tank ceiling with a B_max sweep, one repeated-impact
> long-horizon run with B(t) plotted, the absolute supply figures, and one Su-style clamp arm would
> move this to a clear accept without changing a single conclusion — three of the four are runs the
> authors already have the harness for. If page budget forbids all of them, the ceiling experiment is
> the one that converts "bounds a run" into a statement a practitioner can rely on.

**Questions.**
1. What is the measured supply Σ max(ΔE_rig, 0), in joules, at the worst cell and at the Fig. 1 cell?
   Without it "overdraws by 4.4×10⁷ J" cannot be sized.
2. What is dB/dt in each scene after the impact transient, and what happens over 10–30 s of repeated
   impacts? Would capping B at B_max break Prop. 4.1 (I believe not), and what is the cost as a
   function of B_max and of η < 1?
3. In Fig. 1 the governed run stores 30.2 J, 3.7× the self-reference's 8.22 J, yet lifts no book,
   while the reference lifts one to 32 mm. If the governed energy is all in stiff, contact-invisible
   directions, what is Eq. (2) protecting against that a band-limited or U_c-visible bound would not
   protect against more cheaply and with less trajectory damage?
4. The table has ω_max h ≈ 2.7×10², so Eq. (4) predicts ≈7×10⁴ over-estimate there, yet it never
   injects. What distinguishes it, and does that imply a usable threshold for practitioners?
5. How is the rank-16 basis chosen such that it retains modes up to 24.7 kHz / 191 kHz? If not the 16
   lowest, how much of the failure is basis selection rather than the contact row?
6. Can you add one per-frame-clamp arm in the sense of Su et al. [16] to Table 1's three columns, so
   the cumulative-and-measured form is shown to buy something?
7. §3.1 says warm starting is "3.1× worse at 4×1" while Fig. 3(a) shows ≈1.6× and §3.2 gives the same
   1.2×10⁵ worst value as cold. Which cell?
8. §6 says box–box rows "rectify a support ring into net rigid motion, to which the ledger is blind."
   How large is that in joules or millimetres, with the governor on?

---

### R5 — Games practitioner / benchmarking methodology · Weak Accept · 6/10 · conf 4

> The diagnosis is real, the isolating experiment is clean, the guardrail is proved and honestly
> priced, and the writing refuses to overclaim — that combination is uncommon and it is why I am above
> the line. What keeps it at Weak Accept rather than Accept is that the operating guide the title sells
> is two-thirds usable: box 1 is the right advice with no measured consequence, box 2 asks for a budget
> nobody has and a knob nobody owns alone, and no box carries a cost. Add the stiffness-aware arm's
> deflection and ring measurement (one figure row, plus one video beat swapped in for the unreported
> steel board), put a language-independent cost line on each box of Fig. 4, add a per-cell geometric
> severity to Fig. 2, fix the 8/24-vs-9/24 and table-scene wordings, and commit to a code release — and
> this becomes a genuinely useful, citable practitioner paper and a clear Accept. Retitling around the
> contact-row weight, which is what §3.2 and the conclusion actually establish, would help it find the
> readers it deserves.

**Walk-through of Fig. 4 as a developer** (R5's distinctive contribution):
- **Box 1** — actionable, best item in the paper; a per-mode scalar computable once per h, with the
  cleanest evidence in the submission. Sufficient for *safety*; **not sufficient for adoption** — no
  deflection, no ring frequency, no image, no runtime. *"I would prototype it, but I would not take
  the card's word for it."*
- **Box 2** — *"partially, and the honest reading is discouraging."* K ≥ 24 for one prop is not a
  budget anyone will approve, so the real content is "you cannot afford this" and deserves to be
  stated that plainly. S is global, not a per-constraint knob. Band-limiting is cheap and actionable
  but admittedly does not work (6/8 cells still over). *Weakest box.*
- **Box 3** — actionable and correctly priced on accuracy. Prop. 4.1 is unconditional and
  host-agnostic; *"the projection is inert within budget (s = 1, bit-identical trajectories)"* is
  exactly the property that makes it shippable. But the card omits the costs that would kill it in
  review: 6.6–34.3% at deployed schedules, and the 6.9–8.8× corrective impulse with 50–61× λ variance,
  which in a game reads as a visible pop. Both belong on the card.

**Questions.** (1) Peak deflection and recovered ring frequency under the stiffness-aware W_q —
*"the difference between a Weak Accept and an Accept from me."* (2) Does the weight swap fix 8 or 9
cells? (3) Language-independent cost — flops/substep vs r, m, active rows; persistent bytes;
eigensolve time. (4) Reduced-model fidelity at the rank-16 configurations the sweep actually runs, and
should Fig. 4 carry a prior validity box? (5) Does the table inject at deployed budgets or not?
(6) Is there a compliance sweep behind "The lever is W_q, not either compliance"? (7) Anonymized code
or data release? (8) Fig. 3(a)'s relaxation setting, and what exactly is "3.1× worse at 4×1"?
(9) What happens with several modal props sharing one iteration budget? (10) Why does the video's
headline scene use a 200 GPa board that appears in no section of the paper?

---

### R6 — Senior PC generalist (venue fit, framing) · Weak Accept · 6/10 · conf 4

> What keeps it at Weak Accept is that the science is careful, the controls are the right ones, the
> arithmetic checks out wherever I probed, and the contribution is correctly sized for a short paper —
> a MIG attendee will leave with a usable rule ("do not use 1/M as the modal inverse mass in a shared
> contact row") and a fail-safe with an honest price tag. What holds it back is entirely fixable and
> entirely presentational: the paper buries its own best result under a negative frame that §3.2
> contradicts, the shipped video's final slide gives the opposite advice from Figure 4, and the prose
> is dense enough that refereeing it required a name table. Fix the video card, reconcile contribution
> (2) with §3.2's conclusion (and ideally the title), correct "three scenes" to "two of three", report
> the deployed-cell margin in joules, and move a third of the parenthetical numbers to the supplement,
> and I would move to a clear Accept. Answer question 1 affirmatively with a trajectory comparison and
> I would argue for it.

**Venue-fit verdict.** *"This is a MIG paper."* XPBD was published at MIG 2016, the target scenario is
a games problem, the budgets studied are the ones shipping solvers use, and the deliverable is a
decision card a technical director could pin up. After the two disclaimers, what remains is (a) the
measurement campaign and its causal attribution to the modal inverse mass, (b) Eq. (5)'s gap-preserving
projection direction with a matched naive control, and (c) the guide itself. *"A real if modest
package, right-sized for a short paper: it would be thin as a full paper, and it is more than a
workshop note precisely because the negative result comes with a verified one-line fix rather than only
a governor."* Related work is honest and current. Pushback: the authors disclaim so much that a reader
can finish §1 unsure anything is claimed, then §3.2 delivers a causal result that is more than a
diagnosis. Two places where hedging has gone evasive — the abstract's *"need not keep modal storage
within the measured rigid-side supply"* is a very soft way to say "overdraws by seven orders of
magnitude in a third of the sweep," and Fig. 2's *"a scale gap rather than a ranking"* is over-cautious
once §3.2 has established the causal variable.

**Contribution audit.** (1) *Supported*, with two scoping corrections (the table never overdraws; the
gravity half of the audit is asserted, not measured). (2) *Partly supported* — the localization is well
supported but to the **row weight**, not to "finite-budget convergence" as the bullet states and §3.2
explicitly denies; "prefer iterations" rests on one pair and Fig. 4 states it unqualified. (3)
*Supported* — cleanest of the three; "Containment, not a fix" is the right self-assessment.

**Figure craft.** Fig. 2 is *"the best figure in the paper"* and verified cell-by-cell. Fig. 1 is
under-ticked (three y-ticks over six decades, curve exits the top), the renders are ~1.2 in wide for
the paper's only qualitative evidence, and "46 J"/"0.94 J" are unexplained. Fig. 3(b) is half-titled;
Fig. 3(c)'s axis is ordered by schedule not cost, and "(E6a-1)" is internal nomenclature meaningless to
a reader. Fig. 4 is redundant with the Conclusion paragraph but *"for a paper whose claimed
contribution is an operating guide, the card is the deliverable and the single most reusable artifact
here. Keep it; it earns its quarter column. If space is needed, take it from §4.1's prose."* Title is
*"serviceable and honest about genre, but mis-aimed: it names the fixed budget, which §3.2 says is not
the lever."*

**Questions.** (1) Does the stiffness-aware W_q arm match the implicit reference in **trajectory**, not
just energy footprint? *"The single answer most likely to move my score."* (2) Signed Eq. (2) margin in
joules for the six deployed cells. (3) Which is the intended box-1 recommendation — paper or video?
(4) Is Fig. 1's "+19 mm" instantaneous or a peak, and are figure and video from the same run?
(5) Given §5, what should the guide tell a developer who wants correct rather than merely bounded ring
behaviour? (6) Contribution (2) vs §3.2 — which do you intend, and can the title say so? (7) Is "3.1×
worse at 4×1" the shelf cell marked in Fig. 3(a)? (8) What is `λ var.`, and can the relaxation-1.0
rows be added to Table 1?
