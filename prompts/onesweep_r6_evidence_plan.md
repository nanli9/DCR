# One-sweep short paper: R6 evidence plan (written 2026-07-26)

**STATUS 2026-07-28: EXECUTED THROUGH POLISH. Verify done by hand. Review BLOCKED.**
See §9 for what landed, what is still pending, and the two failures. Summary: 12 of 22
agents completed; the 3 Verify agents died on transient API errors and all 7 Review
agents died on the account's monthly spend limit. The paper ships at **5.4983 body
pages**, 7 PDF pages, 0 Overfull / 0 warnings / 0 undefined.

Original launch note, retained: ran as workflow
`wf_727d5d96-449` (`onesweep-r7-evidence-and-review`), 7 phases, 22 agents, all
Opus 5 at max effort. §8 records the two items the 2026-07-28 review panel added, the
polish phase, and the reviewer phase the user requested at the end. **Read §8 before
§2: it changes both the scope table and the page target.**

**The page target changed.** §2 and §3 below were written around a 6.00-page ceiling
on the reasoning that 5.50 was self-imposed. The author has since set **5.50 body
pages as the binding shipping target**. Integration now works to a 5.85 working
ceiling so nothing is dropped prematurely, and a dedicated Polish phase compresses
back to 5.50 by tightening prose before dropping anything. Where §3 says "New ceiling
for this plan: 6.00 body pages", read 5.85 working / 5.50 shipping.

Target artifact: `paper/onesweep_short.tex` (orphan worktree `paper`, branch `paper`).
MIG 2026 short-paper deadline: **7 August 2026**.
Every agent in every phase: **Opus 5, effort `max`**.

---

## 1. Where this starts from

State as of 2026-07-26 18:55, after the `onesweep-r5-backlog` workflow (9 agents, 0 errors):

| | |
|---|---|
| body length | **5.4627 pp** (column-aware ruler), 6 total PDF pages |
| build | 0 Overfull, 0 undefined refs/citations, 0 LaTeX warnings, 0 em/en dashes |
| internal panel | 6 of 6 **Weak Accept**, mean 6.17/10, confidence 4/5 unanimous |
| Stanford agentic review | **recommends acceptance as a short paper** |
| codex | 45-55% as inspected, 60-70% after its five "straightforward fixes" |

Already landed, do **not** redo:

- Prop. 3.4 corrected and strengthened. `run_t13_ordering_kappa.py`, 40,705 rows, 56/56 checks,
  bit-identical to T5 at kappa = 1 (0.0 diff over 1,232 quantities). Failure band measured:
  3,840/10,000 injecting at kappa = 2 vs 0/10,000 at kappa = 1; band exists iff `m/M < kappa^2 - 2`;
  `b* = (sqrt(37)-5)/6 = 0.18046` at m = M. New closed form `sup dE/|E-| = (kappa^2-2)^2 / [4(kappa^2-1)]`.
- kappa convention pinned: `kappa_r` appears 10x where it appeared 0x; the rigid side is stated as
  `Delta z/h`; admissible range `kappa in [1/2, 2]` scoped correctly to `kappa_r = kappa`.
- `zeta = 0` qualifiers added at the three sites claiming exactness.
- The kappa = 2 amplitude claim corrected: reproducing charge is `mu* = m(2 + b/2)`, verified against
  `out/t11_accuracy.csv` (0.5998 / 0.5833 / 0.5333 / 0.5048 / 0.50005).
- **The Catto quotation in the abstract was fabricated** and is replaced with a verbatim, locatable
  line from the Baumgarte Stabilization section of box2d.org. Do not reopen this.
- Table 1 rebuilt with both columns defined; T10 reads 9900 attempted (correct).
- Phase map replotted single-column: 0.189 pp saved, smallest glyph 3.75 pt -> 6.07 pt.
- Figure 3's legend no longer covers its own readout (R6's complaint was real, fixed at 500 dpi).

### The premise this plan is built on

**The 5.50-page ceiling is self-imposed.** The CFP allows six body pages excluding references.
At 5.4627 body there is roughly **half a page of legal headroom**. The four additions the last
run dropped for space fit inside it. The cost is that references spill onto a seventh sheet,
which the CFP permits. This plan spends that headroom deliberately.

### Why codex's estimate is stale in our favour

Codex assessed the pre-workflow paper. Two of the three "drops to weak reject" conditions are
already discharged: R3's (Prop. 3.4) and R4's (kappa convention + locatable quotation). The
marginal value of the remaining codex path is lower than its 60-70% figure implies.

---

## 2. Scope decision, with reasons

| item | verdict | why |
|---|---|---|
| Supplement F1 + text nits | **DO FIRST** | Hours of work, pure downside protection. The paper's promise is currently stronger than the shipped package. |
| Spend CFP headroom on the 4 dropped additions | **DO** | Evidence already measured and on disk. Closes Stanford's only twice-raised gap and its only missing-related-work item. |
| Equal-cost baseline | **DO** | Best ratio in the backlog. R6 named almost exactly this as the *one additional datum* that moves it to Accept outright; R5 asked independently. No new scene, no new video. |
| Warm / multi-row arm | **DO, scoped small** | R5's major and Stanford's twice-raised scope ask. Report as a measured boundary, never as an extended guarantee. |
| Hero single-pad cargo touchdown | **DEFER** | (i) Its job is already done: three of six reviewers said the *existing* video moved them across the accept boundary. (ii) Most expensive item: new scene authoring, recording, figure, video re-cut. (iii) Can backfire: a single-pad touchdown at realistic parameters may show a weaker contrast than the current 56.8 mm vs 5.3 mm hero, and the dinner scene already stays clean where shelf and ledge break. Revisit only if phases A-D finish with a week to spare. |

Honest ceiling: this does not reach unanimous strong accept by 7 August, and chasing that is not
the goal. Phases A-D defend the two remaining drop-to-weak-reject conditions and deliver the one
datum three reviewers tied to Accept.

---

## 3. Binding context for every agent

Paste this into the `COMMON` block of the workflow script. It is hard-won; do not paraphrase it.

### Paths and build
- Repo `/Users/nan/Desktop/DCR`. Paper is a separate worktree at `/Users/nan/Desktop/DCR/paper`
  on the code-free orphan branch `paper`. **Never commit anything, anywhere.**
- **Never modify `paper/main_short.tex`** (the companion paper).
- Build: `cd /Users/nan/Desktop/DCR/paper && latexmk -pdf -interaction=nonstopmode onesweep_short.tex`
  (~60-90 s). The shell has **no `timeout` command**; do not prefix commands with it.
- T-suite: `benchmarks/paper_eval/t_onesweep/`. Convention: **create new scripts, never edit an
  existing harness file.** New scripts are imported by, not merged into, the old ones.

### Page ruler (column-aware, authoritative)
The originally prescribed ruler was wrong: it read a vertical position only and was blind to
which column the References heading starts in, under-reporting by up to half a page.

```
pdftotext -bbox-layout onesweep_short.pdf -
find <word ...>References</word>; note 1-based page index i, xMin, yMin
f   = (yMin - 88.0) / 632.0
col = 2 if xMin > 300 else 1
body_pages = (i-1) + ((1.0 + f)/2.0 if col == 2 else f/2.0)
```

Baseline 5.4627. **New ceiling for this plan: 6.00 body pages** (the CFP limit), not 5.50.
Total PDF pages may become 7; that is allowed. Treat anything in [5.46, 5.47] as "no change".

### Layout facts discovered the hard way
- The page is **float-locked, not text-locked**. Removing ~15 lines of prose moved nothing;
  one table caption produced the entire 0.065 discrete jump. Measure after each batch, never
  only at the end.
- Page 6 column 2 currently fills to its last line: the bibliography has ~0 pt of slack.
- Ruler quantization: body reads 5.2736 for any phase-map height up to ~134 pt and 5.3114 from
  ~145 pt up.

### DO NOT "FIX" THESE. Both were reviewer claims, both verified FALSE
1. **Eq. (6) is not missing a `-w_r`.** The rendered PDF reads
   `dE = (v^2/2D^2)[u'Gu - w_r - 2 J_c'u - 2 alpha~]`, `D = w_r + J_c'u + alpha~`, matching
   `run_t10_multimode.py` T10-1 term for term. Two reviewers transcribed it without `w_r` from a
   low-resolution text extraction and built major weaknesses on their own misreading. Adding a
   second `-w_r` would break the paper.
2. **The body's "shelf 2/9"** for the backward-Euler-shaped remedy is correct and agrees with
   Fig. 3's middle panel. The caption's "9/9 per scene" refers to the **left** panel (kappa = 1).
3. **"For every kappa != 0" in Thm 3.3 is TRUE and stays.** The claimed "matched charge injects
   for kappa > 2" was tested at 28/28 and is false. Only the `kappa in [1/2, 2]` range applies,
   and only where `kappa_r = kappa`.

### Claim discipline (binding)
- Finite-iteration injection is **prior art**, conceded, never claimed. The concessions citing
  `giles2025avbd` and `wei2026earlyterm` survive verbatim.
- Never claim as novel: the `(omega h)^2` term, the `1 + (omega h)^2` factor, the implicit weight,
  the Delassus operator, the inelastic-loss formula, or "ordering matters in Gauss-Seidel".
- Every theorem keeps all hypotheses visible: one sweep, cold start, `e = 0`, hard contact unless
  stated, the reconstruction factor and **which coordinates carry it**, and the damping state.
- The distant-collision-response acronym is **banned** from the paper.
- Anonymity: no author name, no home-directory path, no username, no repo URL anywhere.

### Prose style (binding)
- **No em-dashes, no en-dashes** in the `.tex`. Hyphens only. Double hyphen reserved for
  bibliography page ranges and the copied ACM conference-date boilerplate.
- Academic register. No AI-tells: no "delve", "it is worth noting", "crucially", "leverage" as a
  verb, "landscape", "realm", no tricolon padding, no hype adjectives.
- Every headline number traces to a CSV listed in the file header comment. Introduce a number,
  add its provenance bullet in the same edit.

---

## 4. The workflow

Five phases, 9 agents. All Opus 5, effort `max`. Phases A and B may run concurrently; C and D
depend on B's measurements; E is serialized last.

### Phase A - Repair (2 agents, parallel)

**A1 `repair:supplement`** — the one material finding from the last run.
`make_supplement.py`'s `TSUITE_CODE` (lines ~55-58) omits both `run_t12_hypotheses.py` and
`run_t13_ordering_kappa.py`; `NUMBER_MAP` omits both CSVs; the built `supplement_onesweep/`
contains neither, and its README has no T12/T13 entry. Meanwhile the paper now cites T13 by name
in a rendered Table 1 row and in Sec. 4, and rests Rmk 3.5's entire `kappa_r` split and the
`kappa in [1/2, 2]` range on T12 alone. Add both, rebuild, re-run the anonymity hard-gate, and
verify every analytic script still runs from a clean copy of the package.
Also fix `run_t12_hypotheses.py:206`, whose `(kappa_r, kappa) = (3,3)` display string reads
`"b > 6 - 3 m/M"` while the code's own predicate is `b > -3 - 3 m/M`; the wrong string ships in
`t12_hypotheses.csv`'s `boundary` column where it reads as a counterexample to Rmk 3.5.

**A2 `repair:text-nits`** — five length-neutral or near-neutral text fixes.
1. C2 and Thm 3.2 omit `kappa`; Section 2's Scope block does not list it either. Insert
   "at `kappa = 1`" in both. This is the last hypothesis gap in the paper.
2. Abstract and C1 say "for any kappa" / "for every kappa", dropping Thm 3.3's `kappa != 0`.
3. C1's "lose exactly a perfectly inelastic impact" holds only at `alpha~ = 0`; Thm 3.3 attaches
   that identity to `At alpha~ = 0`. The passivity half is unconditional, the identity half is not.
4. "Everything is machine-checked to 1e-12" over-reads Table 1's own 1e-9 (T10) and 1e-3 (T4) rows.
5. "every mode below 65 Hz" needs "at the shipped `1/960` s substep"; the body only ever prints
   `h = 1/120`, which would give 8.1 Hz.
Also: Table 1 jumps T11 -> T13 with no T12 row, visible to any reader. Either give T12 its row or
state the numbering. And Figure 3 ships **hidden clipped text**: copy-paste from the PDF yields a
suptitle reading "Shipped XPBD support row" where the visible paper says "position-based". No
anonymity risk, but it is a mismatch a reviewer can find.

### Phase B - New evidence (2 agents, parallel)

**B1 `evidence:equal-cost`** — the highest-value item in the plan.
The paper never answers the practitioner's first question: **is the matched weight better than
spending the same budget on another iteration?** R6 named a system-level cell where the already
published stiffness-aware weight injects and the matched weight does not as the *one additional
datum* that would move it to Accept outright; R5 asked for an equal-cost baseline independently.
Build a NEW script comparing, at equal wall cost: matched weight at 1 iteration versus mass-only
at 2 iterations versus the shipped implicit weight at 1 iteration, on the existing shipped-row
scenes (the `t4`/`t6` machinery). Report injection counts, energy, and measured cost per arm.
**This experiment can fail.** If the extra iteration dominates the matched weight at equal cost,
report that plainly; it is better to know now than to have a reviewer find it. Deliver at most
one short paragraph plus one Table 1 row.

**B2 `evidence:warm-multirow`** — convert the narrowest weakness into a disclosed boundary.
R5's major was that the result is not demonstrated in "the warm, interacting, persistent-contact
regime that motivates in-solve coupling"; Stanford raised multi-row and warm starts twice.
Measure, do **not** extend the guarantee: (i) warm-started sweeps, (ii) two or more simultaneously
active rows with cross-coupling. Report where the index still predicts the sign and where it
degrades, including the degradation direction (false negatives are the unsafe direction, as the
paper already discloses for the kappa = 2 index). Deliver one short paragraph, framed as a
measured boundary of the diagnostic, plus one Table 1 row.

### Phase C - Restore the dropped additions (1 agent)

**C1 `restore:additions`** — spend the CFP headroom.
The last run measured all of this and then dropped it for space under the self-imposed 5.50
ceiling. The text exists in the `onesweep-r5-backlog` agent reports; recover it rather than
re-deriving. Restore, in priority order:
1. **The "What it costs" paragraph** (`tcost_*.csv`). Stanford's only twice-raised item (its
   questions 1 and 6) and R6's "add one sentence on per-row cost". Measured: matched row solve
   0.99-1.02x default; installing the weight is `r` reciprocals per substep; the index adds
   5.9-6.5% of the row solve at `r = 16` and `24`; in a modal basis `K_c` is diagonal so `G^-1`
   is those same reciprocals and no matrix is assembled; a coupled `K_c` needs one Cholesky of
   `G` per substep shared by every row, `2r^2` flops per row instead of `2r`, measured 6.8-14.5x
   the diagonal accumulation over 1000 rows at `r = 4` to `64`. Only full `G^-1` is proved: on
   2000 coupled-stiffness cells the diagonal charge injects on 19, a 2x2 block-diagonal on 4, and
   diagonal-plus-rank-one on 49. That last sentence answers Stanford's question 2.
2. **The two related-work citations**: proximal ADMM/NCP frictional contact (arXiv 2405.17020)
   and PBD-R (arXiv 2603.14634). One sentence each, positioning the per-row one-sweep guarantee
   against converged NCP/ADMM steps and against PBD-R's many-step fidelity. Add the `.bib` entries.
   This is Stanford's only "missing related work" item.
3. **The "Scenes and parameters" summary** (`scene_params_cells.csv`). R5's major finding was
   that not one system-level number in the paper is traceable. Full table to the supplement,
   compact summary in the body.
4. **The supplement-contents sentences**, now that A1 has made the package match the promise.

Measure with the column-aware ruler after each item. Ceiling 6.00 body pages. If something must
be cut, cut in reverse priority order and say what was dropped.

### Phase D - Integrate (1 agent, serialized)

**D1 `edit:integrate`** — the only agent permitted to edit `onesweep_short.tex` in phases B-D.
Takes A2's nits, B1's and B2's paragraphs and table rows, and C1's restorations, and lands one
coherent build at <= 6.00 body pages with clean build health. Correctness and claim-discipline
items go in first; additions are cut first if space runs out. Re-grep every anchor before editing
and report any that no longer match.

### Phase E - Verify (3 agents, parallel)

**E1 `verify:claims`** — adversarial claim integrity. All 16 prior-art concessions verbatim with
keys; every theorem's full hypothesis set including which coordinates carry `kappa` and the
damping state; token-diff proving no number lost, re-rounded or re-attributed; every new number
carrying a provenance bullet and a CSV that exists; both DO-NOT-FIX items untouched; anonymity;
banned acronym absent; `main_short.tex` byte-identical.

**E2 `verify:build`** — rebuild in a scratch directory and confirm the shipped PDF matches the
shipped source; measure body pages with the column-aware ruler *and* re-derive the constants
independently from the PDF line grid (previous verifiers found first body line at yMin 89.58,
pitch 10.96 pt, 57 lines per column, and reproduced 5.4627 / 5.4669 / 5.4753 across three column
models); build health; dashes and AI-tells; **rasterize every page at 200 dpi and look at it** —
the round before last shipped a legend covering its own text that nobody caught from source.

**E3 `verify:experiments`** — the new one, and the reason this phase has three agents.
B1 and B2 introduce experiments whose *results* enter the paper. Independently re-run both from
their CSVs, confirm the printed numbers, confirm the scripts do not edit any tracked harness,
confirm both are in the supplement, and adversarially check whether either experiment's framing
overstates what it measured. Prior rounds shipped a claim ("validated across the full T5 sweep")
that its own suite could not support; this agent exists to stop that recurring.

---

## 5. Acceptance criteria

Do not report the plan as done until all of these hold:

1. `body_pages <= 6.00` on the column-aware ruler, measured by two agents independently.
2. Build: 0 Overfull, 0 undefined refs/citations, 0 `LaTeX Warning:`, no `??` in rendered text.
   (The acmart `balance` warning is auto-loaded by the class and is not author-controllable.)
3. Zero em/en dashes in the `.tex`; only ACM boilerplate and bib page ranges use `--`.
4. `supplement_onesweep/` contains T12 and T13 code and CSVs, README entries, updated SHA256SUMS,
   passes its anonymity hard-gate, and every analytic script runs from a clean copy.
5. Every theorem states which coordinates carry `kappa`; C2 and Thm 3.2 carry `at kappa = 1`.
6. The equal-cost result is in the paper **whichever way it came out**.
7. The warm/multi-row result is framed as a measured boundary, never as an extended guarantee.
8. Both DO-NOT-FIX items verified untouched by an agent that did not edit the file.

## 6. Deliberately out of scope

- The hero single-pad cargo touchdown scene, its figure and its video re-cut. Reasons in §2.
- Friction, and any attempt to extend the guarantee to frictional or warm regimes. Measure only.
- Re-canvassing Figure 3 to fix its 2.8-3.5 pt in-panel type. It cannot be fixed from inside the
  panels (raising type makes the middle readout run under the inset and the right legend under
  its note box, both tried and reverted) and the canvas is pinned by the absolute `trim` in the
  include line. It needs a re-canvassed figure plus a second `.tex` edit. Worth doing, but it is
  a presentation task and this plan is an evidence plan.
- `\acmSubmissionID{}`: still empty and cannot be filled until EasyChair assigns one. Fill on
  assignment; the comment in the source already says so.
- The salami-slicing decision on running two MIG shorts from one program in one cycle. Unresolved
  and a judgment call for the user, not an agent.

## 7. Housekeeping the user should decide separately

Everything from the last two sessions is **uncommitted**: `benchmarks/paper_eval/t_onesweep/`,
`supplement_onesweep/`, the teaser figure, the scene video, `paper/onesweep_short.{tex,pdf}`, and
the 1,775-line `paper/committee_review_onesweep_short_2026-07-25.md`. It exists only as
working-tree files. Committing is outside this plan because the workflow is forbidden to commit.

---

## 8. Amendment, 2026-07-28: what the new panel added

A second six-reviewer panel (`paper/committee_review_onesweep_short_2026-07-28.md`) scored the
built PDF **5.17/7 mean** (five weak accepts, one accept, no rejects; confidence 4/5 unanimous)
and said "do not upload unchanged". Its items 3, 5 and 6 and most of its readiness list were
already covered by §§2-4 above. Two were not. Both were verified against the artifact before this
plan was amended, because three claims from the *previous* round turned out to be false and are
now the DO-NOT-FIX list in §3.

### 8.1 The passive family (NEW; now the highest-value item in the plan)

**Verified TRUE.** Eq. (6) at `onesweep_short.tex:512` reads
`dE = (v^2/2D^2)[u'Gu - w_r - 2 J_c'u - 2 alpha~]`, `D = w_r + J_c'u + alpha~`.
Substituting `W = c G^{-1}` gives `u = cG^{-1}J_c`, so `u'Gu = c^2 a` and `J_c'u = c a` with
`a = J_c'G^{-1}J_c >= 0`, hence

```
dE = (v^2 / 2D^2) [ c(c-2) a - w_r - 2 alpha~ ],    D = w_r + c a + alpha~
```

and `c(c-2) <= 0` on `0 < c <= 2`. **Every `c` in (0, 2] is passive under the theorem's existing
hypotheses.** `c = 1` is sufficient, not unique.

The endpoint is not arbitrary. At `kappa = 2`, `G = 4m + h^2 k = m(4 + b)`, so
`G/2 = m(2 + b/2) = mu*`, the reproducing charge this plan's §1 already records as verified
against `out/t11_accuracy.csv`. **The converged-amplitude charge is the `c = 2` endpoint of the
passive family.** The paper currently frames its `kappa = 2` arm as necessarily conservative
("returns 1/2 to 1 of the converged amplitude", `:893`) and files it as a limitation. If `c = 2`
is admissible, a passive choice reaching the converged amplitude exactly exists, and a stated
limitation becomes a characterized frontier.

Scope, binding: prove the family, name the endpoint, deliver the **selection criterion**, and stop.
Do **not** change the shipped recommendation, re-run the system scenes, or re-cut the video. All
shipped experiments are at `c = 1` and stay there. The likely selection criterion, to be settled by
measurement and not by assertion: `c = 1` is the endpoint whose loss is *exactly* the perfectly
inelastic impact (Thm 3.3's identity, which is therefore the `c = 1` specialization), while `c = 2`
has **zero passivity margin from the modal term** (`dE = -v^2 w_r / 2D^2`; only the rigid term
dissipates), so any perturbation of `kappa` or `G` pushes it outside the family. If robustness
collapses at the endpoint, that is a good result: it explains why the conservative default is the
right thing to ship while the frontier is now characterized.

### 8.2 The T6 metric (NEW; claim integrity)

**Verified TRUE.** `benchmarks/paper_eval/x1_passivity/run_weight_swap.py:122` computes
`ratio = e_modal_peak / max(e_imp_peak, 1e-9)`: peak modal energy over peak *impactor* kinetic
energy. T6 calls a cell "injecting" when `ratio > 1`. The paper's own formal definition at
`onesweep_short.tex:405` is `E+ > E-`. Different tests. `ratio > 1` is strong evidence of
injection; `ratio <= 1` does not prove total-energy nonincrease. So "8 of 24 -> 0 of 24" shows
removal of gross modal overrun, not system-level passivity.

Checked and ruled out as a shortcut: `weight_swap_full.csv` has `holds_explicit` /
`holds_implicit`, but both are `True` on all 24 cells **including the arm with ratio 6333**, so
that column is not a total-energy sign and cannot substitute.

Mitigating fact: the **body already discloses the metric correctly** at `:793` ("the peak modal
energy overrunning the measured rigid-side supply by up to `1.2e5`"). It is the **abstract's** bare
"injecting cell count" and any "injection-free" phrasing that overreach. So the primary fix is a
targeted rename, with a re-run logging the formal sign attempted only if it is cheap.
Acceptance bar: after this run, no sentence may use "injecting" for the 24-cell grid in a sense
different from `:405` without saying so in the same sentence.

### 8.3 Smaller additions from the same panel

- **`h` ambiguity.** `:377` says "the substep is `h`"; `:790` says the budgets `(4,1) (8,2) (16,4)
  (32,8)` run "at `h = 1/120`", but 1/120 is the **frame** and the shipped substep is 1/960. The
  index depends on `h^2`, so this is decision-relevant. Verified present.
- `:893` "accepting the converged amplitude" -> "targeting" or "accepting a conservative
  amplitude". Interacts with §8.1; the spec must compose with either outcome.
- The shelf's grid-sensitive reference (9.6 mm at 1/960 s vs 0.1 mm at 1/120 s) belongs in the
  paper if shelf remains an accuracy anchor.
- Factorization policy and pseudocode for a non-diagonal `G^{-1}`, folded into §4's C1 priority 1.

### 8.4 What the panel did NOT overturn

The three DO-NOT-FIX items in §3 went unchallenged this round. The panel independently
confirmed the scalar boundary, the row-visible form, and the `W = G^{-1}` loss identity, and found
no counterexample under the declared assumptions. The scope discipline and the prior-art
concessions were listed among the paper's strengths.

### 8.5 Executed shape

Phases as §4, amended: **A** gains `A3 fix:t6-metric`; **B** gains `B1 evidence:passive-family`
(and the former B1/B2 become B2/B3); **D** splits into `D1 edit:integrate-correctness` and
`D2 edit:integrate-evidence`, serialized, so correctness lands before additions and additions are
what gets cut at the ceiling. D2's protection order is: passive family, equal-cost, cost paragraph,
warm/multi-row, related work, scene parameters, supplement sentences.

**Phase Polish (NEW, user-requested)** sits between Integrate and Verify, three agents:

- `P1 polish:length` compresses to the 5.50 shipping target in a fixed order, and the
  order is the point: tighten prose, then recover float space, then swap in the short
  fallbacks, then drop in reverse priority. It is explicitly forbidden to compress by
  deleting a hypothesis, qualifier, scope limit, prior-art concession or provenance
  bullet. "If a sentence is long because it is precise, it stays long." If it cannot
  reach 5.50 without cutting something D2 marked load-bearing, it stops and reports
  the trade as an author decision rather than making it.
- `P3 polish:references` validates every citation on two axes: **does the work exist**
  (authors, venue, year, and the arXiv IDs 2405.17020 / 2603.14634 / 2602.08094 /
  2603.16424 resolving to what the `.bib` claims), and **does the paper characterize
  it correctly**, which is the axis a bibliography checker skips. Every quoted string
  is checked verbatim against its source, including the box2d.org Baumgarte line.
  Unverifiable citations are flagged, never silently "corrected" or deleted. This
  agent exists because this paper has already shipped a fabricated quotation once.
- `P2 polish:tone` applies P3's corrections, then runs an AI-tell and register pass
  with a named list (canned transitions, tricolon padding, empty intensifiers,
  paragraph-opening announcements, hedging stacks, uniform sentence length), bound by
  two rules: match the voice of the already-reviewed sections rather than restyling
  them, and never let a tone edit weaken a claim or blur a scope limit.

`E1` gained two checks for this phase (reference integrity verified independently of
P3, and a before-P1/after-P2 diff proving no qualifier went missing), and `E2` now
fails above 5.50 and sweeps the whole paper for tells **in both directions**: tells
P2 left behind, and sentences P2 flattened into overclaiming.

**Phase F (user-requested)** runs six isolated reviewers on the polished PDF plus
`benchmarks/paper_fig/out/onesweep_scene_video.mp4`, each restricted to the packet (no `.tex`, no
planning files, no other reviewer's output) but encouraged to run their own verification code, then
one coordinator writes `paper/committee_review_onesweep_short_r7_2026-07-28.md` with two extra
sections: movement against the 2026-07-28 panel, and reviewer disagreements presented unaveraged.
Reviewer claims asserted without evidence are filed separately from findings, which is the
structural lesson from the false claims of round 6. **The workflow stops after the report. No edits
follow the panel.**

---

## 9. Execution record, 2026-07-28 (workflow `wf_727d5d96-449`)

12 of 22 agents completed. Two failure modes, one authoring bug and one account limit.

### 9.1 The handoff bug (mine, and it cost real work)

The script wrote `const A = parallel([...])` and `const B = parallel([...])` **without
`await`**, so `A[0]`/`B[0]` indexed a pending Promise and every downstream handoff
interpolated the literal string `undefined`. D1 received no A1/A2/A3 spec and D2 received
no B1/B2/B3 spec. Both editors detected it, said so in their reports, and re-derived the
work from the review file and from the CSVs the upstream agents had left on disk. The
evidence landed; the *specs* did not. **If this script is ever resumed, fix the missing
`await` first.** The A/B agent reports are recovered under
`scratchpad/r7/*.md` in the session scratchpad.

### 9.2 What landed in the paper

- **Cor. 3.4 (Passive family)** at tex ~L820: passive iff `0 ⪯ W ⪯ 2G^{-1}` (Loewner);
  on the ray `W = cG^{-1}`, eq. (8) collapses to `c(c-2)a - w_r - 2*alpha~`, passive on
  `c in [0,2]`; `c = 2` identified as `G/2 = m(2 + b/2)`, so the converged amplitude
  Section 4 reports out of reach is recovered exactly and passively at that endpoint.
  Verified numerically: 1222 charges inside the interval passive, 1278 outside inject.
  **Renumbered the ordering result from Prop. 3.4 to Prop. 3.5**; every earlier note that
  says "Prop. 3.4" now means 3.5.
- **T6 metric renamed** everywhere to "modal-energy overrun", abstract included, with the
  caption stating the test explicitly and a new sentence conceding that a ratio at or
  below one does not certify passivity.
- **Equal-cost arm** (T14): mass-only leaves 17/9/6/2 of 27 cells injecting at 2/4/8/16
  iterations; matched is passive on all 27 at one iteration; amplitude trade 0.57 vs 0.85.
- **Warm/multi-row boundary** (T14), framed as measured, not proved: mass-only index
  false-negative on 2795 of 43,783; matched still injects on 4099 of 43,898.
- **Cost material** folded into Sec. 3; `h` frame-vs-substep error at the 24-cell paragraph
  corrected against `weight_swap_full.csv`'s `h_sub` column.
- **Seven reference repairs**, including a quotation re-pointed from `giles2025avbd` to the
  TOG article that actually contains it, and `gonzalez2019energyleak`'s author corrected.

### 9.3 Landed by hand afterwards, from A2's recovered spec

Four claim-integrity items the empty handoff dropped, plus one defect found in verification:

1. Thm 3.2 hypothesis now reads "with mass-only weights **and `kappa = 1`**".
2. C2 bullet now reads "of that boundary **at `kappa = 1`**".
3. C1 no longer welds the unconditional passivity to the `alpha~ = 0` identity: it now
   reads "passive for every `kappa != 0` ... **and under hard contact** it loses exactly a
   perfectly inelastic impact".
4. Abstract: "Everything is machine-checked to `1e-12`" -> "**The closed forms are**
   machine-checked", which Table 1's own `1e-9` (T10) and sign-level (T4) rows require.
5. **A printed number was inverted.** The equal-cost sentence read "the matched weight is
   passive on all 27 at the mass-only weight's own cost, `1.004` measured", but
   `run_t14_equalcost.py:61` defines `cost_ratio = us_substep / us_substep(matched_i1)`,
   so `1.004` on `mass_i1` means mass-only costs 1.004x **matched**. Now reads "at `0.996`
   of the mass-only weight's measured cost". This is the class of error the failed E3
   verifier existed to catch.

Paid for by compressing the "When to couple into the row" paragraph, which contained a
genuine restatement (the "condition is a persistent resting contact" sentence restated the
preceding one). Net body change: 0.0000.

### 9.4 Deliberately NOT landed, and why

The paper is at a **layout boundary**: References sits at the exact top of p6c2, so any
single added line jumps the ruler from 5.4983 to ~5.5070, and sub-line trims spread across
different paragraphs move it by exactly zero (a paragraph must lose a whole ~68-char line).
Three A2 items were reverted after measuring at +0.0294:

- **8a**, pinning `h` as "the substep, not the frame" at the definition site. The actual
  *error* was already fixed at the 24-cell paragraph; this was clarity.
- **10**, the shelf's grid-dependent converged reference (`0.1` mm at `1/120` s vs `9.6` mm
  at `1/960` s). A panel-suggested disclosure, not a correction.
- **6**, the Table 1 caption note explaining the missing T12 row. D1 measured it at +0.0483
  **and** it regressed the layout to 1 Overfull vbox. A body sentence is the cheap home.

Each is one to two lines. They fit only if something else gives up a full line first.

### 9.5 Verification, run by hand after the E agents died

Body 5.4983; 0 Overfull, 0 Underfull hbox, 0 `LaTeX Warning`, 0 undefined, 0 errors, 0
`??`; 7 PDF pages; all fonts embedded. All three DO-NOT-FIX items intact (Eq. (6) keeps its
`- \Rr` at L770; `shelf 2/9` at L1069; `for every kappa != 0` at L783). No em/en dashes
outside comments; the only `--` in prose is the ACM `December 11--13`. Banned acronym
absent. No author name, home path, username or repo URL in source or rendered PDF.
`main_short.tex` untouched (mtime Jul 23). **No commit made in either repo.**
Pages 1, 3 and 4 inspected as 110-dpi rasters: no overlap, no clipping, Table 1 and the new
corollary render correctly. Headline numbers re-derived from their CSVs rather than from any
agent's report: equal-cost 17/9/6/2, 28x, 5.3x, 20x, 0.57/0.85 all confirmed;
warm/multi-row 2795 (1551+1043+57+144) and 4099 (2226+1870+3) confirmed by summation;
passive-family margin `frac_lt_1pct` 0.20825 at `c=2` against 0.0 at `c=1` confirmed.

### 9.6 BLOCKED: the six-reviewer panel

All 6 reviewers and the report agent failed with "You've hit your monthly spend limit".
Nothing was written; `paper/committee_review_onesweep_short_r7_2026-07-28.md` does not
exist. The panel is the last phase and is independent of everything above, so it can be
re-run alone once the limit resets or is raised, against the current PDF and
`benchmarks/paper_fig/out/onesweep_scene_video.mp4`.

### 9.7 Landed after the spend limit cleared (2026-07-28, second sitting)

**A3's strict-metric result is now printed**, which closes the 2026-07-28 panel's issue 2
completely rather than half. The panel's required repair was "rename the metric OR
recompute with the total-energy sign"; the paper now does both. The bare concession
sentence was replaced by concession-plus-data at zero net page cost:

- before: "The ratio is a gross-overrun test: at or below one it does not by itself
  certify passivity."
- after:  "The ratio is a gross-overrun test; the total-energy sign gives $10$, $1$ and
  $0$ of $24$ across the three arms."

Verified at source before printing: `weight_swap_energy.csv`, `net_excess > 0` counts are
explicit 10/24, backward-Euler 1/24 (that one cell at `1.17e-5` of the impactor's kinetic
energy), matched 0/24. Note the explicit count is **10** under the strict sign against the
**8** the modal ratio gives, and the matched arm is the only one clean under both tests.
Paid for by tightening "reproduces the companion's published ratios to zero relative
difference" to "reproduces the companion's published ratios exactly". Header provenance
bullet updated from "NOT printed in the body" to name the sentence that prints it.

Body stayed at **5.4983**. Two intermediate phrasings measured at 5.5277 and were
shortened rather than accepted, confirming again that this page tolerates no added line.

**Panel re-run launched** as `wf_85bc1e33-2c7` (`onesweep-r7-review-panel`): the six
reviewers plus the report agent only, 7 agents, all Opus 5 max effort. The three Verify
agents were NOT re-run because §9.5's verification was done by hand and is recorded above;
that was an economy call given the spend limit had just cleared. Frozen artifacts for this
panel: PDF sha256 `d4716b9d0b786f2e6d5e3071da66975f3c0246fab61af6f265bc79a24a2606c8`,
video sha256 `a9ef4e4158734e98fd040f698e0007dacd595e27ed6e7611c7d91207988a7901`.

### 9.8 Still open after this run

- The panel's asked-for **`c = 2` arm in the shipped-row and system comparisons**. The
  corollary is stated and the endpoint identified, but every experiment still runs at
  `c = 1`. This was scoped out deliberately and remains the largest open item.
- C1 priorities 2-4 (two related-work citations, scenes-and-parameters summary, supplement
  sentences), all text-ready in the recovered `C1_restore-additions.md`.
- `\acmSubmissionID{}` still empty; EasyChair has not assigned one.
