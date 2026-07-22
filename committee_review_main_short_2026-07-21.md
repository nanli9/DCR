# Committee Review — *Modal Energy Injection in Three Fixed-Budget Contact Solvers*
### Mock MIG 2026 short-paper review panel · compiled 2026-07-21
### Materials: `paper/main_short.pdf` (7 pp) + `benchmarks/paper_fig/out/teaser_video.mp4` (45 s)

Six independent reviewers, each reading the paper and video cold (double-blind; none told the
provenance of the work), each with a different expertise/disposition, each instructed to be willing
to reject. Scores are on a 1 (strong reject) – 7 (strong accept) scale.

---

## Verdict at a glance

| # | Reviewer lens | Score | Verdict | Conf. |
|---|---------------|:-----:|:-------:|:-----:|
| R1 | Contact-solver internals (XPBD/AVBD/impulse) | **5/7** Weak Accept | ACCEPT | 4/5 |
| R2 | Modal reduction / deformable + energy-control prior work | **5/7** Weak Accept | ACCEPT | 4/5 |
| R3 | Experimental methodology / empirical rigor | **5/7** Weak Accept* | ACCEPT | 4/5 |
| R4 | Area-chair / significance & venue fit | **3/7** Weak Reject | REJECT | 4/5 |
| R5 | Games practitioner / real-time utility | **3/7** Weak Reject | REJECT | 4/5 |
| R6 | Clarity / presentation / accessibility | **3/7** Weak Reject | REJECT | 4/5 |

**Mean 4.0 / 7 · Median 4.0 · Split 3–3.** \*R3 accepts but states a stricter reading of its own
central objection (no measurement variance) "could defensibly land at Weak Reject."

**Bottom line:** technically sound, unusually honest, on-topic — but contested on significance,
practical value, and communication. A split-committee borderline that, as-is, would more likely miss
the bar at a competitive venue, with a well-defined and achievable path to acceptance on revision.

---

## Where all six agree

**Strong consensus — strengths:**
1. **Technical soundness is high.** Three reviewers (R1, R2, R3) independently verified Proposition 2.1
   by hand and found it correct; the "credit-before-test" ledger ordering genuinely removes the
   telescoping slack, and γ-scaling bounds *total* modal energy (kinetic + elastic), not just velocity.
2. **Internal numeric consistency is exemplary.** R1, R2, and R3 each audited the headline arithmetic
   across abstract/body/figures/video and every cross-reference ties out to the quoted digits
   (4.44×10⁷/371 = 1.197×10⁵; 1555.6/7.92 = 196×; 22 352/7.92 = 2823×; cell bookkeeping 90 = 72+18,
   78 distinct = 60+18; Fig 1 thumbnails match the video to the digit). "Many accepted papers fail this
   audit; this one passes."
3. **Exemplary intellectual honesty.** Universal praise: "bounded, not faithful," "safety envelope not
   an accuracy device," "measure but do not explain" (AVBD), "no unqualified real-time claim," the
   102–118 % recycling disclosure. The video foregrounds the method's *own* failure mode.
4. **The video communicates better than the paper** — noted by all six; R6 calls it "a near-model" and
   recommends importing its framing into the paper.
5. **Relevance to MIG is High** for all six (contact, PBD/XPBD, modal reduction, interactive budgets).

**Strong consensus — weaknesses:**
1. **The measurement is the real contribution; the storage bound is minimal and transplanted** — and the
   authors say so. Near-unanimous.
2. **The writing is punishingly dense** — every reviewer flagged it; several caught the same defects
   (a skipped step in the §2 substep enumeration; a garbled "inter passivity" sentence on p.2).
3. **"Energy-safe" overstates the guarantee.** The supply is a *gross, recyclable* loss (102–118 % of
   true loss on AVBD), so the bound is a bookkeeping cap against a possibly-inflated ledger, not
   physical passivity. Flagged by R1, R2, R3, R4.

---

## Why the three rejects reject (the fault lines)

- **R4 (significance):** The named "bound" contribution is self-disclaimed as minimal, non-faithful, and
  *dominated by the remedies the paper itself prefers* (convergence, band-limiting). The durable,
  actionable takeaway reduces to "prefer implicit/AVBD; band-limit stiff modes" — narrow and
  partly expected. Honesty sharpens the *measurement* but argues the *bound* out of a contribution.
- **R5 (practitioner):** "The only place enforcement is real, it isn't real-time; the only place it's
  real-time, it isn't enforced." Enforced governor measured only on an 11–125 ms CPU; the 5.3–9.4 ms
  4090 path is a read-only monitor. And the cost — ~9.8 mm penetration at deployed budgets (21.6 mm
  adversarial = 72 % of a 30 mm board), plus a trajectory that *under-moves and increases* error where
  it engages — is a price games devs would sooner reject than pay.
- **R6 (clarity):** A short paper must land one point for a non-specialist; this one buries it under
  notation, clause-chains, an overloaded Fig 2 (3 solvers × 2 metrics × 6 rows × 4 cols, two diverging
  color scales, hatching), and *five* contributions in six pages. A communication reject — the video
  proves the opacity is fixable.

---

## Recurring technical criticisms (independently corroborated — the highest-leverage fixes)

Ranked by how many reviewers raised them and how central they are:

1. **The "three formulations" framing is confounded** *(R1 + R3, both technical-deep, independently).*
   The seven-order spread is better read as **implicit vs. explicit modal-block integration** than as
   position-vs-multiplier-vs-velocity. The impulse host "never injects / converged at K=2" essentially
   *because* it integrates the modal DOF implicitly, (M+hD+h²K)⁻¹. This questions the framing of
   contribution #1. **Fix: the ablation — give XPBD an implicit modal weight (or the impulse host an
   explicit one) at fixed K and show whether injection follows the formulation label or the modal
   weight.** This is the single strongest technical critique.
2. **No replication / variance / seed-sensitivity for the headline energy numbers** *(R3 central; R1, R2
   note single-run maxima).* "Three independent runs" = the three *conditions* (ungoverned/governed/
   self-reference), i.e. **N=1 per cell** on self-described *chaotic* dynamics, quoted to 5–6 sig figs
   (1.19534×10⁵, 1555.6 J, 21.6 mm). The only replicated section (runtime, §3.5) is the most rigorous —
   the contrast is telling. **Fix: a seed sweep with reported spreads; round to supported precision;
   show the *sign* of the margin is stable even where the magnitude isn't.**
3. **AVBD overdraft "measured but not explained"** *(R1, R2, R4).* One of three core findings is a black
   box; without a mechanism, is 6.7 J a ceiling or an adversarial floor? Weakens the "prefer AVBD" half.
4. **The bound is dominated by band-limiting / not faithful / never enforced in real time** *(R2, R4, R5).*
   §3.3 itself names band-limiting the co-solved basis (99.6 % of injected energy is in >20 kHz stiff
   modes) as the "first-line remedy." **Fix: show the governor beats band-limiting in *some* regime, OR
   demonstrate an enforced real-time governor, OR reframe it explicitly as a last-resort fail-safe and
   lead with the measurement.**
5. **§3.4 reduced-vs-FEM is weak/under-explained** *(R1, R2, R3).* The reduced/FEM peak-deflection ratio
   *rises* 0.38→0.88 with mesh refinement for a *fixed* 24-mode basis (counter-intuitive, unexplained —
   possibly the *reference* denominator moving with h), and the far-field is validated only by Spearman
   ρ=0.89 — a **rank** correlation of falloff shape, not **magnitude**, which is exactly what a
   distant-response method needs. **Fix: explain the direction; report far-field magnitude error.**
6. **Scope/communication** *(R6, R5, R4).* Cut to one or two contributions; import the video's
   intuition-first framing ("a steel board should barely move → it gets launched"); rebuild Fig 2 to a
   legible headline (violations XPBD 8/24, AVBD 2/24, impulse 0/24) with the full sweep in the supplement.

---

## Synthesized path to acceptance

Every reviewer named what would move them. In union, a revision that:
- **(A)** adds the modal-weight ablation to localize the cause and fix the "formulation" framing *(R1, R3)*;
- **(B)** adds a seed sweep + honest precision for the energy numbers *(R3)*;
- **(C)** explains (or bounds) the AVBD overdraft *(R1, R2, R4)*;
- **(D)** either shows the bound beating band-limiting somewhere, demonstrates real-time enforcement, or
  reframes the bound as a fail-safe and leads with the measurement *(R2, R4, R5)*;
- **(E)** tightens scope and imports the video's framing; rebuilds Fig 2 *(R6, R5)*;
- **(F)** softens "energy-safe" to "modal-storage bounded against a gross-loss ledger" *(R1–R4)*

…would, by the reviewers' own statements, move R3 to a solid accept and flip at least R6 (and plausibly
R5) — i.e. clear the bar. (A) and (B) are the two that address *soundness-of-claim* rather than taste,
and are therefore the non-negotiable pair.

---
---

# Full individual reviews

_(Verbatim, as returned by each independent reviewer.)_

---

## R1 — Contact-solver internals · Weak Accept 5/7 · ACCEPT · confidence 4/5

**Summary.** Studies what happens when an established rigid–modal contact law (a Zheng–James-style
velocity-level complementarity row, transcribed to position level, normal-only, e=0) is co-solved
inside three fixed-budget interactive solvers (XPBD, AVBD, implicit sequential-impulse) and measures the
spurious modal energy each injects under small budgets. Over a 24-cell sweep on one machine, injection
varies by seven orders of magnitude (XPBD up to 4.4×10⁷ J ≈ 1.2×10⁵× incident KE; AVBD ≤6.7 J in 3/24;
implicit never); an iteration-only sweep (Fig 3) identifies the XPBD amplification as a truncation
artifact decaying ~6 orders toward a high-iteration reference. Adds a minimal fail-safe (cumulative
storage bound, Prop 2.1) at a measured contact-validity cost (≤21.6 mm penetration).

**Strengths.** (1) The bound is correct — worked through Prop 2.1; E_mod is homogeneous degree-2 in
(q,q̇) and γ scales both, so realized energy is clamped to ≤E_mod⁻+B each substep; induction closes;
"unconditional, any host, any solve" is justified. (2) Unusual internal consistency — every spot-check
reconciles (4.44×10⁷/371 = 1.197×10⁵; R>1 in exactly 8/24 XPBD, 2/24 AVBD, 0/24 impulse; §3.3's 196×,
3.7×, 2823× all check). (3) The measurement target is formulation-agnostic even though the solvers
aren't — all three carry an explicit (q,q̇) modal state with a pinned-identical modal subsystem, so the
invariant is computed on the *same* modal model. (4) Fig-3 truncation analysis is genuinely rigorous —
doesn't rest on the falling scalar; tracks both KKT conditions (penetration 27.9 mm→3.6 µm; separated-row
multiplier 84×→139×→0 at K=64) showing gap-closure and complementarity converge at different K. (5)
Exemplary honesty. (6) Actionable and on-topic for MIG.

**Weaknesses (ranked).** (1) The "three formulations of one row" framing conflates primary-unknown
formulation with the *modal-block integration scheme*, which is the proximate cause — the impulse host
integrates the modal block implicitly (M+hD+h²K)⁻¹ while XPBD uses explicit per-mode compliance under
under-relaxed GS; the seven-order spread is better read as implicit-vs-explicit modal integration. (2)
The comparison is confounded and only partially controlled (hosts differ in contact treatment, modal
weight, warm start, relaxation; one warm-start ablation provided, no compliance-matched ablation). (3)
The constructive contribution is thin — a monitored scalar clamp, disclaimed, not faithful (21.6 mm,
≈1.05–1.08× the board's own peak dynamic deflection). (4) AVBD overdraft unexplained. (5) Gross (not net)
supply overstates tightness. (6) Very dense writing; numbered-loop glitch; K reused for diagonal modal
stiffness. (7) Narrow scope; §3.4 tangential and its rising ratio under-explained.

**Detailed.** Eq 1 reduction from Zheng–James is *asserted, not shown* — one displayed equation of the
original velocity law beside Eq 1 would remove all doubt at trivial cost. Prop 2.1 is a
tautology-by-construction — "unconditional" is real but not deep; the genuine content is empirical (holds
at 1.1×10⁻¹³ J without destabilizing) and in the cost. Eq 3 gravity correction W_g is well-designed
(free-fall registers zero supply). Fig 2 dual-panel + the two-metrics-disagree point is a nice
methodological contribution, but {4×1,…,32×8} covaries K and S so it's not a clean iteration sweep
(correctly relegated to Fig 3). Fig 3 is the cleanest result; the split-KKT tracking is worth
foregrounding. Table 2 good and honestly instrumented. §3.4 peripheral; the rising ratio deserves a
sentence. §3.5 honest and appropriately hedged.

**Axes.** Novelty Low/Medium · Soundness High · Significance Medium · Rigor Medium/High ·
Clarity Low/Medium · Relevance High.

**Recommendation:** Weak Accept, **5/7**, ACCEPT. *Reason:* technically sound where it matters (proof
correct, numbers reconcile, truncation analysis careful and honest) and delivers a concrete MIG-relevant
warning; held to the edge of borderline by a framing that under-attributes the effect to modal-block
integration, an admitted band-aid contribution, one unexplained host, and dense writing — none a
soundness failure, and MIG welcomes rigorous measurement papers.

---

## R2 — Modal reduction / deformable + energy-control prior work · Weak Accept 5/7 · ACCEPT · confidence 4/5

**Summary.** Takes a transcribed rigid–modal support-contact row as given and asks how much spurious
energy it injects into a reduced deformable body when resolved by fixed-budget solvers rather than to
convergence. Measures across XPBD/AVBD/implicit over a 24-cell sweep (injection varies 5+ orders),
identifies the position-based blowup as a truncation artifact, and adds a one-directional cumulative
bound on modal storage funded by measured gross rigid-side loss (Eq 2), enforced by a scalar projection
(Eq 4), proved unconditional (Prop 2.1), realized at 10⁻¹³ J in all 90 cells. Scrupulous that the bound
is "bounded, not faithful."

**Strengths.** (1) Exemplary claim discipline and reproducibility (frozen commands + hashes; 90-cell
verification at the roundoff floor). (2) The measurement is the real contribution and its details are
useful and non-obvious — five-order cross-formulation spread; **iterations beat substeps at equal cost**
(K=32,S=1→0.300 bounded; K=4,S=8→3.13, overdraws 481 J); ratio and invariant flag *different* cells;
spectral localization (99.6 % in stiff modes ~200× substep rate); AVBD not unconditionally benign;
worst-host ordering inverts across scenes. (3) **Prop 2.1 verified by hand** — credit-before-test absorbs
the granularity term; γ-scaling bounds total energy. (4) The §2 positioning against FEPR [4],
passivity/energy-tank [5,7], Rath [14], Wei et al. [15], You et al. [16] is accurate and fair. (5) The
video is honest (shows the governor removing legitimate motion).

**Weaknesses (ranked).** (1) The surviving novelty is thin and the paper's own logic undercuts the
governor — §3.3 says the "first-line remedy is band-limiting the co-solved basis, not a scalar," so the
governor fixes a regime whose better fix the authors acknowledge; its niche is narrow. (2) External
validity — one implementation per host, three scenes, one contact regime; can't rule out
implementation-vs-formulation, especially as the ordering inverts across scenes. (3) §3.4 is a weak,
under-explained validation — the reduced/FEM ratio *rising* 0.38→0.88 with refinement for a fixed basis
is counter-intuitive (maybe the reference denominator moves with h); far-field validated only by
Spearman ρ=0.89 (rank, not magnitude) — magnitude fidelity is exactly what a distant-response method
needs. (4) The core phenomenon is partly known ([15]). (5) Density + defects (garbled "inter passivity"
sentence; skipped step 6).

**Detailed.** The RHS of Eq 2 is a gross scene-wide loss, not per-contact dissipation — the AVBD case is
sharpest (102–118 % recycling; the tank there isn't really "funded by dissipated contact energy"); this
doesn't break boundedness but the physical interpretation doesn't hold uniformly, and is the weakest
joint in the "funded by measured loss" story. Prop 2.1: the snapshot E_mod⁻ must equal the prior
projected E_mod for the induction to chain (implicit but satisfied). Eq 4 inert at γ=1 (bit-identical) —
lets the ledger run as a pure monitor. Fig 2 is the strongest single exhibit *because* the two metrics
disagree. Fig 3 careful (reads KKT in own units). The paper *undersells* its own understanding of the
mechanism (the §3.3 spectral analysis largely explains it).

**Axes.** Novelty Medium/Low · Soundness High · Significance Medium · Rigor Medium/High ·
Clarity Medium/Low · Relevance High.

**Recommendation:** Weak Accept, **5/7**, ACCEPT (could accept a Borderline landing). *Reason:* the
load-bearing contribution is the measurement — careful, quantitative, honestly scoped, genuinely
actionable; the bound is minimal and transplanted (and says so) but sound and honestly costed. The
exemplary discipline and the weak-but-disclosed §3.4 net out, for a short paper, on the accept side of
borderline.

---

## R3 — Experimental methodology / empirical rigor · Weak Accept 5/7 · ACCEPT* · confidence 4/5

**Summary.** Measures spurious modal energy from a single transcribed contact row under small fixed
budgets in three solvers over a 24-cell sweep (worst modal-to-incident ratios 1.2×10⁵ / 1.70 / 0.53),
argues via iteration sweep that the position-based amplification is a truncation artifact, finds
iterating beats substepping, and adds a one-directional cumulative storage bound (Prop 2.1) confirmed at
10⁻¹³ J in all 90 cells at a measured cost (≤21.6 mm penetration).

**Strengths.** (1) **Internal numeric consistency is exemplary** — independently re-derived: §3.3's
2823×/3.7× = 22 352/7.92 and 29.5/7.92; 196×/189× = 1555.6/{7.92,8.22}; worst 4.44×10⁷/371 = 1.197×10⁵;
Fig-2 per-panel maxima match the headline triple; violation counts (9/8, 3/2, 0/0) match; cell
bookkeeping (90 = 72+18; 78 = 60+18, 12 duplicates = inert impulse-relaxation rows) exactly consistent;
Fig 1 matches the video. "Many accepted papers fail this audit; this one passes." (2) Unusually candid
limitations. (3) Costs measured not assumed. (4) The most defensible claims are existence-type
(ranking inversion, existence of catastrophic injection) and are properly supported. (5) Actionable
takeaway.

**Weaknesses (ranked).** (1) **No replication or sensitivity for the headline energy numbers** — the only
replicated measurements are timings (§3.5, 10 reps ± spreads). "Three independent runs" = the three
*conditions*, not replicates (the video caption confirms), so effectively **N=1 per cell** for energy,
no variance, no seed sweep, on dynamics the paper calls chaotic. For a measurement paper, characterizing
the measurement's own uncertainty is not optional and is absent. (2) **Unsupported precision** —
1.19534×10⁵, 1555.6 J, 21.6 mm are exact for one trajectory but say nothing about the neighborhood; the
peak of a chaotic trace is the most seed-sensitive quantity. (3) One implementation stands for a
formulation class (hosts differ in modal-weight treatment — the paper's own explanation is a property of
the *implementation*, not the formulation). (4) General claims rest on single-scene evidence
("iterations beat substeps" = one point; "truncation artifact" = one deterministic shelf drop). (5)
Prop 2.1 is construction-guaranteed — "holds in 90 cells" verifies the code, and B can exceed physical
availability (102–118 % on AVBD). (6) External validity / real-time framing tension (single machine;
enforced governor never real-time).

**Detailed.** The sweep and the two-metrics-disagree point are genuine methodological strengths; what it
can't support is the *precision* of any single cell. Fig 3 is the strongest experiment but one
deterministic scene. The equal-row-evaluation comparison is a single (scene, work-total) point — please
replicate. Reframe the 90-cell result as *implementation verification of a construction-guaranteed
bound*, and state the bound is on modal storage against a recyclable gross-loss ledger, not physical
conservation — the abstract's "energy-safe" undoes §4. Table 2 values check but are single-run maxima
(a lower bound on how bad it gets). §3.5 is the most statistically careful section precisely because it's
the only replicated one — the contrast is telling. Video note: the teaser leads with a "steel board"
whose 48 299 J peak appears nowhere in the paper (fine for a teaser; worth aligning).

**Axes.** Novelty Medium · Soundness Medium/High · Significance Medium · Rigor **Medium (bimodal)** ·
Clarity Medium/High · Relevance High.

**Recommendation:** Weak Accept, **5/7**, ACCEPT (on the 4/5 line). *Reason:* an honest, internally
airtight measurement paper with an actionable takeaway that fits MIG's measurement niche; the crux
against it is that a measurement paper reports no replication/variance/seed-sensitivity for its headline
numbers — single deterministic runs on chaotic dynamics quoted to five sig figs — and generalizes one
implementation per formulation to classes. Those gaps are real and central but revision-addressable, and
the honesty + verified rigor tip to accept; **a stricter reading that treats measured uncertainty as
non-negotiable could defensibly land at Weak Reject.**

---

## R4 — Area-chair / significance & venue fit · Weak Reject 3/7 · REJECT · confidence 4/5

**Summary.** A measurement paper (injection across three fixed-budget solvers over a 24-cell sweep; no
formulation dominates — XPBD up to 4.4×10⁷ J, AVBD ≤6.7 J in 3/24, implicit never; the position-based
blowup a truncation artifact per Fig 3) plus a deliberately minimal, provably-correct cumulative storage
bound (holds in all 90 cells) whose cost is measured (≤21.6 mm penetration; legitimate motion removed).

**Strengths.** Exemplary measurement discipline and honesty; a non-obvious well-supported central finding
(same law catastrophic in one formulation, benign in another; ordering inverts; truncation-artifact
diagnosis); the bound is provably correct and empirically confirmed; costs measured not hand-waved
(Table 2: impulse up to 8.9×, λ-var 62×; §3.3: 196×→3.7× energy error but trajectory error *rises* to
71 % of reference peak); good supporting studies (full-FEM §3.4, runtime §3.5).

**Weaknesses (ranked).** (1) The headline mechanism is, by the authors' own account, dominated —
convergence cures it (§3.2), band-limiting is the first-line remedy (§3.3); the bound is a *third-choice*
remedy for a narrow corner. (2) "Bounded but not faithful" undercuts practical value — books sunk 21.6 mm
into a 30 mm shelf is plausibly as objectionable as the launch. (3) Narrow applicability
(modal-reduced-deformable-vs-rigid via shared multiplier is a specific technique, not mainstream games
practice). (4) Three formulations, one implementation each, and the AVBD overdraft is a black box. (5) No
real-time enforced result — a venue-fit gap. (6) Density.

**Detailed.** What a MIG reader acts on: "if you co-solve a modal-reduced deformable with rigid bodies
through a shared multiplier at a fixed low budget, expect large spurious modal energy from a
position-based host; it's a truncation artifact; prefer implicit/AVBD and band-limit the basis." Genuinely
actionable — but note the *bound* (named contribution #2) is not the actionable part; the formulation
choice and band-limiting are, and those are established-adjacent intuitions the paper quantifies rather
than discovers. Integrity vs self-refutation: both, split across the pillars — the measurement survives
the honesty; the bound is substantially argued-down by it. Venue fit: topic fits MIG, but the absence of
an enforced real-time result pulls it toward a solver-internals study.

**Axes.** Novelty Low–Medium · Soundness High · Significance Low–Medium · Rigor Medium–High ·
Clarity Medium · Relevance Medium.

**Recommendation:** Weak Reject, **3/7**, REJECT (genuine 3-vs-4 borderline). *Reason:* a careful,
unusually honest measurement study whose significance is capped by a narrow niche and by the fact that
its named mechanism is self-disclaimed as minimal, non-faithful, and inferior to the very remedies the
paper recommends — so the durable contribution reduces to a well-quantified but modest and partly
expected observation. Integrity is real and the measurement teaches something, but for even a MIG short
paper the deliverable is a hair too thin and too solver-internal. *Flips to accept with:* an explanation
of the AVBD overdraft, evidence the bound beats band-limiting in some regime, OR an enforced governor at
a real-time budget.

---

## R5 — Games practitioner / real-time utility · Weak Reject 3/7 · REJECT · confidence 4/5

**Summary.** Measures spurious energy from an established rigid–modal contact law under small fixed
budgets across XPBD/AVBD/implicit (injection differs seven orders); shows the XPBD amplification is a
truncation artifact and that iterations beat substeps at equal cost; adds a minimal fail-safe (Prop 2.1,
90 cells at the roundoff floor) and honestly measures its cost (≤21.6 mm penetration; a "bounded, but not
faithful" trajectory that under-moves the reference).

**Strengths.** A real, under-documented problem quantified carefully; the "iterations beat substeps at
equal cost" result is crisp and actionable (mildly contradicts "small steps" folklore *for this
coupling*); mechanism nailed down (Fig 3 monotone 6-order decay; §3.2 reads both complementarity
conditions in their own units); exemplary honesty; the bound is simple and provably correct (~1 %
overhead, inert at γ=1, exact-zero momentum drift); rigor high for a short paper.

**Weaknesses (ranked).** (1) **The usable real-time energy-safe method is not delivered** — enforced
governor measured only on an 11–125 ms CPU (table scene ~8 Hz); the 5.3–9.4 ms 4090 path carries the
ledger *read-only*, and "a device-resident enforced γ does not exist in this work." "The only place
enforcement is real, it isn't real-time; the only place it's real-time, it isn't enforced." (2) The
fail-safe's cost is likely unacceptable to its target audience — 21.6 mm penetration (72 % of a 30 mm
board) adversarial, ~9.8 mm deployed (9–13× resting sag, ~1.05–1.08× peak dynamic deflection). (3)
"Bounded but not faithful" cuts deep — §3.3: governor *reduces energy error* (196×→3.7×) while
*increasing trajectory error* (6.5→14.2 mm, 33 %→71 % of reference peak); governed motion is *further*
from the reference than ungoverned. (4) The paper's own analysis points past its contribution
(band-limiting). (5) The "funding" is a loose, sometimes-invalid over-estimate (3–32 % XPBD; 102–118 %
AVBD). (6) Narrow scope (normal-only, e=0 — no friction/scraping/rolling). (7) Dense writing buries the
takeaway; enforcement loop mis-numbered.

**Detailed.** The real-time story does not hold up as a practical claim (though honestly disclaimed): the
overhead is cheap but never bolted onto a real-time enforced base solve; the "device governor would be
cheap too" argument is reasonable but untested. §3.3/Table 2 is the most honest and most damaging section
— the worst artifact occurs "where the projection is most load-bearing," i.e. exactly when you need the
fail-safe. Video: clear, legible, honest, but a slide deck of static snapshots (not continuous motion),
and it never *shows the penetration* that is the central practical cost — it sells the science, not the
usability. What a reader can DO, descending value: (1) solver choice; (2) budget allocation
(iterations>substeps); (3) the fail-safe (last-resort only).

**Axes.** Novelty Medium · Soundness High · Significance Low–Medium · Rigor High · Clarity Low–Medium ·
Relevance High.

**Recommendation:** Weak Reject, **3/7**, REJECT (borderline, leaning reject). *Reason:* rigorous,
honest, and teaches two genuinely actionable things — but from the practitioner's seat the central
deliverable does not close: enforced governor only on a non-real-time CPU, fast device path doesn't
enforce, and the measured cost (~9.8 mm penetration deployed, up to 21.6 mm, plus a trajectory that
under-moves and even *increases* error where it engages) is a price a games dev would more often reject
than pay — especially when the authors' own analysis points to an unbuilt band-limiting fix. *Flips to
accept with:* tighten to the measurement, demonstrate (or drop) real-time enforcement, show the
penetration cost visually.

---

## R6 — Clarity / presentation / accessibility · Weak Reject 3/7 · REJECT · confidence 4/5

**Summary.** When a modally-reduced deformable rests in unilateral contact with rigid bodies, the
standard approach couples them through one shared multiplier at velocity level. This paper measures the
spurious energy that row injects under small fixed budgets across three formulations (XPBD/AVBD/implicit)
over a 24-cell sweep — position-based overdraws up to 4.4×10⁷ J, AVBD mildly, implicit never — and shows
the position-based blow-up is a truncation artifact decaying six orders toward a high-iteration
reference. Adds a minimal, provably-correct cumulative storage bound (Prop 2.1; 90 cells at the roundoff
floor), honestly noting it buys boundedness at the cost of fidelity (≤21.6 mm penetration).

**Strengths.** The underlying study is sound and the experimental design is clean (one row → three
solvers → same-code-path high-iteration reference; the K·S "equal row-evaluations" control). Exemplary
honesty. The video supplement is excellent. Declarative section/figure headers do real work. Relevance to
MIG is strong.

**Weaknesses (ranked).** (1) **Too dense to serve the broad MIG audience, and the density is not all
load-bearing** — a typical attendee won't extract the takeaway on a first read; for a short paper that is
close to disqualifying, and the video proves it's fixable. (2) It tries to do too much for a short paper
(five distinct results in ~6 pages), which forces the compression. (3) The abstract is a wall of numbers
before the reader has a framework. (4) **Figure 2 is overloaded past legibility** — 3 solvers × 2
metric-rows × 6 scene/relaxation-rows × 4 budget-cols, two different diverging color scales, plus hatching
semantics; parsing needs the caption read twice. (5) Heavy notation/jargon at or before first definition
(Table 1: "coloured-block GS," "q-block Newton," "Rayleigh D"). (6) §2's "Two objects" scaffolding and the
two literature paragraphs are the densest prose exactly where a reader needs an on-ramp. (7) The practical
value is undercut by its own honesty (72 %-of-thickness penetration).

**Detailed.** Abstract accurate but a poor on-ramp — the one plain sentence ("we measure the energetic
cost of that truncation") is buried and should anchor it. Reads well: the intro's opening line; Fig 1's
caption; the Limitations section. Lost the thread: §2's 40-word clause-chains; §3.2's "two references not
the same object"; the Fig 2 body. Structure is logical; the problem is local density and scope. **Paper
vs video — the video wins decisively:** it states the question in one line, gives an intuition-primer
("A steel board should barely move" → "the resting books rise 0.1 mm" → "they are launched"), uses the
three-way visual the paper buries in tables, and lands the limitation plainly ("bounded, but not
faithful"; "no unqualified real-time claim"). **Strongest recommendation: import the video's framing into
the paper.**

**Axes.** Novelty Medium · Soundness Medium/High · Significance Medium · Rigor High ·
Clarity **Low** · Relevance High.

**Recommendation:** Weak Reject, **3/7**, REJECT (close to Borderline). *Reason:* a short paper must make
one point land for a non-specialist, and this one — despite sound, honest, rigorous work — buries its
point under extreme notation, clause-heavy prose, an overloaded Fig 2, and too many contributions. The
video communicates the same result clearly, proving the opacity is fixable and is a property of the
writing, not the science. A revision that imports the video's framing, leads with intuition, cuts scope,
rebuilds Fig 2, and introduces terminology before use would move this to a clear Accept — "I would gladly
re-review."
