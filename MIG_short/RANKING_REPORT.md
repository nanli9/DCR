# Blind Calibration: Ranking Report

**Manuscript:** *A Per-Row Danger Index and a Reconstruction-Matched Effective Mass for One-Sweep Passive Contact Coupling in Fixed-Budget Position-Based Solvers* (blind ID **P03**)
**Comparators:** 7 accepted MIG short papers (MIG 2024 + MIG 2025)
**Evidence level:** title + abstract only, for all 8 entries
**Unblinded:** 2026-07-30, from `blind_key.json`

---

## 1. Headline

**The manuscript placed 1st of 8 with both rankers.** Ranker 1 scored it 5.5/7 and placed it in the *Accept* tier (3 entries); Ranker 2 scored it 5.0/7 and placed it in the *Accept* tier (2 entries).

Two qualifications belong in the same breath. **Both rankers deliberately left their top tier ("clear accept") empty for the entire batch**, so first place here is the top of a field whose ceiling neither ranker was willing to reach from abstracts alone. And the comparator set contains **no rejected papers** — see §5 — so "first among seven accepted papers" is a statement about how the abstract reads relative to published work, not a prediction of acceptance.

---

## 2. Full unblinded rankings, side by side

| | Ranker 1 | score | Ranker 2 | score |
|---|---|---|---|---|
| 1 | **► MANUSCRIPT** (P03) — *Per-Row Danger Index / Reconstruction-Matched Effective Mass* | **5.5** | **► MANUSCRIPT** (P03) — *Per-Row Danger Index / One-Sweep Passive Contact Coupling* | **5.0** |
| 2 | Adaptive Sub-stepping for Constrained Rigid Body Simulations (P08, MIG 2024) | 5.0 | Adaptive Sub-stepping for Constrained Rigid Body Simulations (P08, MIG 2024) | 4.5 |
| 3 | Trajectory-aware Smears for Stylized 3D Animations (P04, MIG 2025) | 4.5 | Expressive Animation Retiming from Impulse-Based Gestures (P02, MIG 2024) | 4.0 |
| 4 | DRUMS: Drummer Reconstruction Using MIDI Sequences (P01, MIG 2025) | 4.0 | Trajectory-aware Smears for Stylized 3D Animations (P04, MIG 2025) | 4.0 |
| 5 | Controller influence on self-determination versus performance… (P07, MIG 2024) | 3.75 | DRUMS: Drummer Reconstruction Using MIDI Sequences (P01, MIG 2025) | 3.5 |
| 6 | Expressive Animation Retiming from Impulse-Based Gestures (P02, MIG 2024) | 3.5 | Controller influence on self-determination versus performance… (P07, MIG 2024) | 3.25 |
| 7 | Investigating How Text and Motion Style Shape Directness in ECAs (P06, MIG 2025) | 3.25 | Investigating How Text and Motion Style Shape Directness in ECAs (P06, MIG 2025) | 3.0 |
| 8 | Storyboarding in Extended Reality (P05, MIG 2025) | 2.5 | Storyboarding in Extended Reality (P05, MIG 2025) | 2.25 |

### Tier assignment

| Tier | Ranker 1 | Ranker 2 |
|---|---|---|
| Clear accept | *(empty, by explicit choice)* | *(empty, by explicit choice)* |
| Accept | **MANUSCRIPT**, P08, P04 | **MANUSCRIPT**, P08 |
| Borderline | P01, P07, P02, P06 | P02, P04, P01, P07 |
| Below bar | P05 | P06, P05 |

Note the scale compression: the manuscript's 5.5 and 5.0 sit on a 7-point scale where 5 = "weak accept" and 6 = "accept". Ranker 1 labels 5.5 *accept*; Ranker 2 labels 5.0 *accept*. Neither ranker awarded any entry a 6 or a 7.

---

## 3. Ranker agreement

**They agree exactly on the manuscript: rank 1 of 8, Accept tier, both rankers.** There is no disagreement about its placement to report. The only difference is a half-point in score (5.5 vs 5.0) and the composition of the tier beneath it (Ranker 1 admitted a third paper to Accept; Ranker 2 did not).

Agreement across the whole batch is high:

- **Spearman ρ = 0.857** (Σd² = 12, n = 8)
- **Kendall τ = 0.786** (25 concordant, 3 discordant pairs out of 28)
- **Identical at 5 of 8 positions** (ranks 1, 2, 7, 8 and the P06/P05 bottom pair).
- **All 3 discordant pairs involve a single entry**, P02 (*Expressive Animation Retiming*), which Ranker 1 put 6th and Ranker 2 put 3rd. Both rankers independently flagged that region as noise: Ranker 1 wrote "P07 vs. P02 (3.75 vs. 3.5) … are effectively interchangeable"; Ranker 2 wrote "P02 and P04 are close to indistinguishable on the evidence … reverse the order and I would not object."

**A caution against over-reading this agreement.** The two rankers are independent in the sense that they were prompted separately without seeing each other's output — they are *not* two independent human reviewers. Their prose converges to near-verbatim on the manuscript's chief virtue: Ranker 1 wrote "Verification density and intellectual honesty", Ranker 2 wrote "Evidence density and intellectual honesty". They also produced structurally identical reports, both spontaneously refused to populate the top tier, and both identified the same weakness in the same terms. Correlated priors are a more parsimonious explanation of ρ = 0.857 than convergent independent judgment. **Treat this as one opinion measured twice, not two opinions that agreed.**

### Where they differ about the manuscript at all

Only in degree. Ranker 1's higher score comes with a stronger positive framing of the honesty disclaimer, which it says it "weighted in its favor":

> "Only P03 explicitly disclaims the part of its territory that is already known, which I weighted in its favor."

Ranker 2's lower score comes with a sharper framing of the same scope caveat as a cost, not just a limit:

> "…a narrow guarantee purchased against a broad-sounding title; a reviewer will ask whether anything survives in a real multi-contact scene."

That is the entire disagreement: whether the title/scope mismatch is a readability problem (R1) or a claim-credibility problem (R2).

---

## 4. What the rankers said about the manuscript, verbatim

### Ranker 1 — rank 1/8, 5.5, *accept*

> **Justification.** This is the only abstract in the batch that states a falsifiable result (a closed-form sign boundary κ² + (ωh)² = 2 + m/M), the exact regime it holds in, and the verification that backs it, including an ablation with a before/after count.
>
> - **Strongest:** Verification density and intellectual honesty — machine-checked to 1e-12 over a 58k-cell phase map, an operator identity in exact rational arithmetic, a three-arm weight swap moving overruns 8/24 → 0/24, and an explicit "that it happens is known and not our claim."
> - **Weakest:** The abstract is close to unreadable for a non-specialist PC member; it front-loads notation before the problem, and the self-declared scope (one sweep, cold start, e = 0, one normal-only row, a niche technique of carrying modal amplitudes in contact rows) invites the reviewer question "does this cover anything a shipping engine actually does?"

On the empty top tier:

> "P03 comes closest on evidence and would move to clear accept if the full text is readable"

On what it could not verify:

> "**Whether the math is right.** P03's boundary condition and operator identity could be correct, correct but trivial, or wrong. Machine-checking to 1e-12 verifies the closed forms against a numerical model; it does not verify that the model is the right one."

Ranked **2nd of 5** in "entries I most want full text for":

> "**P03** — I need to know two things the abstract cannot settle: whether the exposition is salvageable for this audience, and whether the one-sweep / cold-start / normal-only scope leaves a result that applies to a real engine or only to a model problem."

### Ranker 2 — rank 1/8, 5.0, *accept*

> **Justification.** The only entry whose abstract carries actual proof-level evidence (closed-form sign boundary, machine-checked to 1e-12 over a 58,081-cell phase map, an exact-rational operator identity, and a controlled three-arm swap moving overruns 8/24 → 0/24), aimed squarely at MIG's physics-based-animation core.
>
> **Strongest.** Evidence density and intellectual honesty: it explicitly disclaims the phenomenon as prior-known and claims only the framework, and it states its own assumptions rather than hiding them.
>
> **Weakest.** Near-unreadable for a general MIG audience, and the closing sentence confines every theorem to one sweep, cold start, e = 0, one normal-only row, which is a narrow guarantee purchased against a broad-sounding title; a reviewer will ask whether anything survives in a real multi-contact scene.

On the empty top tier:

> "P03 is the only entry with a realistic path to that tier, and only if the full text shows the theorems are correct *and* that the one-sweep / cold-start / normal-only confinement is not fatal to the practical claim."

On what it could not verify:

> "**Correctness of formal claims.** P03's sign boundary, its passivity result for the matched operator, and the claim that κ = 1, ζ = 0 reproduces the converged implicit step are all checkable only in the body. The machine-checked and exact-rational language is a strong signal but is not verification."
>
> "**Writing quality of the body.** P03's abstract is dense to the point of exclusion, but that may be compression rather than a property of the paper."

Ranked **1st of 4** in "entries I most want full text for":

> "**P03** — highest ceiling and highest variance in the batch. I need the proofs, the phase-map methodology, and an honest read on whether the scope caveats leave a result that matters in a shipped engine. Also whether Section 1 can be made legible to a MIG reader."

### The single most consistent finding

**Both rankers named the same weakest thing, independently, in nearly the same words: the abstract is unreadable for a general MIG audience, and the scope confinement (one sweep, cold start, e = 0, one normal-only row) reads as narrow against a broad title.** Both then made their willingness to escalate the paper conditional on exactly that: R1 on "whether the exposition is salvageable," R2 on "whether Section 1 can be made legible to a MIG reader" and whether the confinement "is not fatal to the practical claim." This is the one actionable output of the exercise, and it is the finding with the least methodological contamination — it is a judgment about the manuscript's own prose, which the rankers read directly.

---

## 5. Honest methodology limits

**Read this section before quoting the headline anywhere.** The exercise has four defects, and the third is severe.

### 5.1 This ranked abstracts, not papers

Every entry was judged on title + abstract alone, including the manuscript. The evidence level was forced down to this floor because 2 of the 7 corpus papers are abstract-only (ACM DL hard-blocks automated access; no mirror exists for either). Both rankers said explicitly that they cannot assess: whether the results exist, whether the math is correct, video quality, statistical validity, related-work honesty, generality, or the writing quality of the body. Ranker 2 called the manuscript "highest ceiling **and highest variance** in the batch" — meaning its abstract-level score is the least stable of the eight under full-text review. **A first-place finish on abstracts is not a first-place finish on papers, and both rankers said so.**

### 5.2 The corpus is n = 7, and only 2 entries are topically comparable

The collector verified that MIG labels long-vs-short per paper only for 2024 and 2025, and that those two years accepted **exactly seven** short papers between them. The corpus is complete for what is verifiable, but it is 7 points, from 2 years, and **only 2 of the 7 are physics/simulation papers** (*Adaptive Sub-stepping*, *Trajectory-aware Smears*). The other 5 are XR/animation/HCI. The manuscript's nearest neighbour in the entire comparison set is a single paper, P08. Additional caveats from the collector: 3 of 5 full texts are repository/preprint versions rather than ACM camera-ready; the 2024 short-paper labels rest on a single source; and the MIG 2025 acceptance statistic is third-party. No distributional claim should be built on this.

### 5.3 Accepted papers are a censored sample — this is not a predicted accept

**Every comparator was accepted.** There are no rejected MIG short papers in the set, because rejected papers are not published and cannot be collected. The exercise therefore measures *where the manuscript falls within the accepted distribution*, which answers a different question from *would it be accepted*.

Concretely: the acceptance decision is made against the full submission pool, which at MIG 2025 was 46 submissions for 19 accepted papers. The 7 comparators are draws from the ~40% that survived; the ~60% that did not are invisible here. Ranking above surviving papers is consistent with acceptance but does not establish it, because the bar is set by the reviewers' response to the *submission*, not by the ranked position among *survivors*. A paper can top a field of accepted work on abstract-level evidence density and still be rejected on a defect that only appears in the body — which is precisely the class of defect both rankers flagged and could not check.

### 5.4 The blind did not hold — the preparer says so in writing

The preparer's report states plainly that "the set is not truly unguessable" and lists six residual signals. The two decisive ones are verified:

| Signal | Status |
|---|---|
| **Abstract length** — "Pick the longest identifies the candidate with certainty." | **Verified.** Manuscript = 292 words; other 7 span 104–156 (median 131). The manuscript is 1.9× the next-longest. |
| **Notational register** — only entry with mathematical symbols | **Verified.** All 20 non-ASCII characters in `blind_set.md` occur inside the manuscript's entry; it is the only entry stating equations. |
| Claim-disclaiming register ("that it happens is known and not our claim"; the closing confinement sentence) | Left intact as substance; the preparer calls it "a fingerprint of an unpublished, review-anticipating draft." |
| Title length | Verified: 18 words vs a 6–13 corpus range. |
| Result density (five numeric validations; no corpus abstract quantifies its evaluation at all) | Verified from the text. |

**Why this matters more than a de-anonymization footnote.** The property that identifies the manuscript is the *same* property both rankers scored it highest for. A 292-word abstract has room for five numeric validations and a scope disclaimer; a 118-word abstract does not. Both rankers awarded first place explicitly for "evidence/verification density" and for the honesty disclaimers — i.e. for content that length purchased and that the comparator abstracts had no space to supply even if their papers contain it. Ranker 1 conceded exactly this: "I cannot distinguish 'did not mention' from 'did not do,' and I have not penalized them as if the latter were proven" — and then ranked five of them below the manuscript anyway, on evidence the manuscript had room to state. **A meaningful part of the first-place margin is an artifact of abstract length, not of paper quality.** The preparer declined to fix it, correctly, since the only fix is rewriting the author's abstract.

### 5.5 One asymmetry that cuts the other way

The 7 comparators are camera-ready abstracts that have been through review and copy-editing; the manuscript is a pre-review draft. The preparer flags this as biasing *against* the manuscript on polish. That is true for prose polish, but the reverse also holds and is worth stating: the manuscript's abstract has been iterated by its author specifically to pre-empt reviewer objections, whereas camera-ready abstracts are typically tightened for space rather than armored for review. The disclaiming register that both rankers praised is a product of that iteration. Net direction of this bias: unclear, plausibly favorable to the manuscript on the exact axis it won on.

### 5.6 What survives all of this

Two things do.

1. **The manuscript's abstract is not out of place among accepted MIG short papers.** No ranker put it in the borderline or below-bar tier, and no ranker described it as off-topic, under-scoped, or thin. Ranker 2 placed it "squarely at MIG's physics-based-animation core." Given a comparator set where two entries were judged below bar, clearing that bar comfortably is real information, and it is unaffected by the length confound.
2. **Both rankers converged on one specific, fixable weakness** (readability + the title/scope mismatch) and made escalation conditional on it. That finding is about the manuscript's own prose, not about its position relative to a censored sample, so it is the most trustworthy output of the exercise.

What does **not** survive: any claim of the form "ranked #1 against accepted MIG papers, therefore likely accept." That inference requires a rejected-paper comparison the corpus cannot supply, and a full-text comparison the evidence level cannot supply.

---

## 6. What it implies for the submission

The manuscript's abstract holds up against published MIG short papers — first of eight with both rankers, in the Accept tier for both — but the margin is inflated by a 292-word abstract having room to state evidence that 118-word camera-ready abstracts could not, and no rejected papers exist in the comparison to locate the actual bar. The one result worth acting on is that two rankers independently named the same blocker and made their support conditional on it: the abstract front-loads notation before the problem and is "near-unreadable for a general MIG audience," and the closing scope confinement reads as "a narrow guarantee purchased against a broad-sounding title." Fixing readability and the title/scope mismatch is the highest-leverage change available, and it is the only change this exercise gives evidence for; nothing here supports predicting the review outcome.

---

*Sources: `blind_set.md`, `blind_key.json`, `corpus_manifest.json`, `COLLECTION_NOTES.md`. Rank statistics computed over the two ranking orders; abstract and title word counts computed over `blind_set.md`. No paper, experiment, or repository state was modified. No git command was run.*
