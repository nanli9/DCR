# MIG short — Round 4 plan: borderline → solid accept

Written 2026-07-20. Inputs: the Opus 4.8 panel (mean 4.50, "borderline weak
accept", pre-Q-round) and the Fable panel on the Q8 build (mean 4.33, "publishable,
not safe", artifacts locked: PDF `276cc375…`, video `30a862fa…`, supplement
`d5c9a8e6…`). Deadline: MIG 2026, **Aug 7**. Freeze target: **Aug 3**.

The user directive for this round: plan only, no code changes yet. Phase 2 is
the only phase that touches code; everything in it is listed for execution, not
executed.

---

## 0. What was verified in-session (2026-07-20, this file's authority)

Two findings that reorder the whole round were checked against the
implementation, not taken from the reviews:

**V1 — the strict bound Eq. (2) is provable for the loop as built.**
Reviewer 1 (Fable panel) argued step 6's test makes step 7's clip inert, so the
telescoping closes on Eq. (2), not Eq. (4). Verified in
`dcr/avbd/_solver/solver_impulse.py:983–1013` (`_psv_commit`) +
`dcr/avbd/_solver/passivity.py` (`passivity_gamma`, `ReservoirLedger.deposit/commit`):

- Order is credit (`deposit`, line 998) → test (`passivity_gamma`, 1001) →
  project (γ-scale q, q̇, cargo, 1003–1011) → debit (`commit`, 1012) with the
  debit taken on the **post-projection** realized gain.
- Let `c_k = η·max(ΔE_rig,0)`, `d_k = max(ΔE_modal,0)` (realized). The test
  enforces `d_k ≤ B_{k-1} + c_k`, so `B_k = B_{k-1} + c_k − d_k ≥ 0` and the
  step-7 clip never binds. Telescoping: `E^n − E^0 = Σ ΔE_k ≤ Σ d_k ≤ Σ c_k` —
  **strict Eq. (2)**. Substeps where modal energy falls only shrink the LHS;
  no refund to B is needed for the bound.
- Caveat that must enter the theorem statement: the test fires only beyond an
  explicit tolerance (`passivity_gamma` default `tol=1e-12`; ledger check
  `tol=1e-9`), so the floating-point guarantee is Eq. (2) + N·tol (≤ ~1e-7 J
  over the longest run). Measured governed margins ±1.1e-13 J corroborate.
- Still to confirm at execution time (expected mechanical): the XPBD and AVBD
  mirrors (`solver_xpbd.py` `_substep_cpu` ledger block ~line 1231;
  `solver_6dof.py` ~2621 and ~3290) preserve the same order and post-projection
  debit. The impulse docstring says they mirror; read them anyway.

Consequence: the Q8 round record's verdict "strict Eq. (2) needs a different
loop (§10)" is **wrong**. The theorem upgrade is a *text-only* change — no
re-run, no trajectory change — and it deletes the paper's most-attacked
apparatus (eq:budgeted, the "three objects" paragraph, the 7–389 J slack, the
23-vs-1 asymmetry defense, the abstract hedge). Four of six Fable reviewers and
all six Opus reviewers hit this; it is the single highest-leverage fix and it
is free.

**V2 — the gravity-supply residual is real and is the artifact the reviewers
computed.** `W_g` is displacement-based: `m·g·(x⁺−x⁻)`
(`solver_impulse.py:990–995`, mirrored in `solver_xpbd.py:1231–1237`,
`solver_6dof.py:2621–2627` and `3290–3296`). Under the symplectic velocity
update, free fall gives `W_g − ΔKE = +½mg²h²` per dynamic body per substep —
phantom supply. So main_short.tex:259–260 ("free ballistic motion registers
zero supply") is false as implemented, the impulse host's "worst margin
−5.7×10⁻⁴ J" (tex:442) is one substep of integrator residual (panel-verified:
implied mass constant across a 64× range of h), and the Limitations sentence
"2–274× the tightest slack" (tex:700) compares AVBD overdrafts against an
artifact quantum. Fix: trapezoidal `W_g = m·g·((v⁻+v⁺)/2)·h`, which zeroes
free-fall supply *identically* (algebra: ½(v⁺²−v⁻²) ≡ (v⁺+v⁻)/2·gh) for all
three hosts at the velocity level. Requires snapshotting `v⁻` next to the
existing `x_prev` snapshot. Carries a `# DEVIATION` note against foundation
§15's accounting and the paper's Eq. (3), which must be restated.

---

## 1. Combined findings ledger (both panels, deduped)

| # | Finding | Source | Current status | Disposition | Phase |
|---|---|---|---|---|---|
| S1 | Headline "23 of 24" measured against Eq. (2); Prop. 2.1 proves only Eq. (4); R1 argues strict (2) is provable | Opus R1 + Fable main + Fable Rev1 | Q2 narrowed vocabulary only; V1 says provable | **Upgrade the theorem to strict Eq. (2) (+N·tol); delete Eq. (4) apparatus** | P1 |
| S2 | Eq. (3) leaves +½mg²h²/body/substep; "zero ballistic supply" false; impulse margins & "2–274×" floor are artifacts | Fable #2 (new; absent from Opus) | Confirmed (V2) | **Trapezoidal W_g + re-run the ledger sweeps** | P2 |
| S3 | §3.5 prints 0.9–3.4% (16×4) while shipped `LEDGER_EXCERPTS.md` measures 6.6–34.3% at deployed 1×8/2×4 and instructs "state as T3 rows"; CSVs absent from `data/` | Fable #1 (self-inflicted by Q1; = the "E-C6 omission") | Confirmed; excerpts §(5) table lines 944–980 | **Add deployed-budget overhead sentences + ship `perf_reps_{1x8,2x4}_summary.csv` + CLAIMS_INDEX rows** | P3 |
| S4 | "21 of its 23 cells below 0.15 J" (tex:445–446) — actual 19; 21 only at ≤0.158 J | Fable #3 | Confirmed by panel | Re-derive from the P2 re-run (numbers change again); then state whichever honest form holds | P3 |
| S5 | "spread 4.9×10⁻⁴" (tex:488) — that's the K=2 vs K=500 endpoint diff; max−min is 6.795×10⁻⁴ | Fable #4 | Confirmed; ratio metric — **not** affected by P2 (no ledger in R) | Text: "moves only in the fourth decimal (K=2 vs K=500 differ by 4.9×10⁻⁴; max−min 6.8×10⁻⁴)" or simply print max−min | P3 |
| S6 | "5.0–8.9 ms/step" (tex:650) — shipped `perf_device.csv` gives 5.29–9.21 / 5.32–9.35; R7b re-run never shipped; fourth scene `truck` undocumented in CSV | Fable #5 | Confirmed; note tex:651–652 already names the fourth scene "a road slab" = `truck` | Quote the shipped CSV (5.3–9.2), map `truck`→"road slab (§3.5)" in CLAIMS_INDEX (or ship the R7b CSV and cite it) | P3 |
| S7 | Showcased accuracy reference is schedule-confounded (1×8 vs 500×1) though iterations≢substeps is the paper's own point | Opus R2 | Untouched (round-3 NO-GO on re-solves) | Default: one scoping sentence in §3.4/§sec:gt. Stretch: a K=500×S=8 reference run if it fits the runtime budget | P4 |
| S8 | Claims must stay "our tested implementations", not solver classes | Opus R3 | Q4 narrowed; title residual adjudicated (keep per plan §8.3 P1) | Final grep sweep (`formulation-class`, `descent-class`, bare "XPBD/AVBD" generics) — abstract/intro/conclusion only | P4 |
| S9 | Governor is an emergency limiter; 21.6 mm, sag suppression, worse trajectories | Opus R4 | Disclosed in 4 places; Q5 close-up open-by-decision (no 4×1 poses; E-C11 slow path defined) | No text change needed. Optional: E-C11 (one serial ARM replay of shelf 4×1 with pose capture, must reproduce 21.6 mm) — **PI decision** | P4 |
| S10 | Reproducibility packet | Opus R5 | **Closed** — unanimous 5.00/5 | Preserve through P2/P3: every changed CSV re-shipped, SHA256SUMS + CLAIMS_INDEX regenerated, smoke test re-run from clean unpack | P5 |
| S11 | EasyChair paper ID required in the anonymous version | Opus + CFP | Open | Insert at freeze | P5 |
| S12 | Panel not perfectly blind (CLAUDE.md/memory auto-injected) | Fable caveat | Process note | Optional clean-room re-panel from a neutral checkout with context stripped; treat scores as soft either way | P5 |

Dropped/void items: shipped-video hash mismatch (the Fable panel locked
`30a862fa…`, which *is* the shipped E-C9f render — closed); Fig. 1 / E-S1b
(frozen; ratio R does not involve the ledger, so P2 does not touch it).

---

## 2. Phases

### P0 — Gate: formalize V1 (½ day, text/math only)
1. Read the XPBD + AVBD ledger mirrors listed in V1; confirm order and
   post-projection debit. Any divergence → S1 falls back to "state Eq. (4) as
   the guarantee and re-measure the headline under it" (see Risk R1).
2. Write the four-line induction cleanly, with the tolerance accounted:
   *For any η∈(0,1] and any host, the loop maintains B≥0 and guarantees
   Eq. (2) up to an explicit accounting tolerance N·tol (exact arithmetic:
   strictly), assuming nothing about the contact solve.*
3. Decide tol presentation: keep `tol=1e-12` and state N·tol (recommended — no
   re-run, honest, dominated by the measured 1.1e-13 J margins), vs. set tol=0
   and re-run (risk: spurious ulp-level firings; not worth it).

### P1 — The theorem upgrade (1 day, LaTeX only)
Sites, all in `paper/main_short.tex`:
- **Abstract 80–89**: "The loop guarantees a one-deposit relaxation of that
  bound; the strict form is observed…" → "The loop guarantees the bound
  unconditionally (up to a stated accounting tolerance); the measured margins
  sit at the roundoff floor (1.1×10⁻¹³ J) in all 90 cells."
- **Contribution bullet 157–164**: same upgrade; delete "a one-deposit
  relaxation of the bound; the strict form is observed".
- **"Three objects, stated once" 265–290**: collapse to one object. Delete
  eq:budgeted (280–286), the 7–389 J sentence, and "under it the
  augmented-Lagrangian host would violate 1 of 24, not 23" (287–290) — the
  Eq. (4) reading exits the paper entirely.
- **Prop. + sketch 327–340**: new statement (P0.2); the sketch becomes the real
  proof (it fits in the same footprint). Keep the "observed, worst margin
  1.1×10⁻¹³ J" line as corroboration, now labeled as the roundoff floor.
- Grep sweep for orphans: `budgeted`, `one-deposit`, `one deposit`, `relaxation
  of`, `three objects`, `7--389`. Fix the Q8-flagged forward reference (the
  contribution bullet citing eq (4)) by deletion — it dissolves.
- Supplement side: `CLAIMS_INDEX.md` rows citing eq (4)/one-deposit;
  `LEDGER_EXCERPTS.md` prose; the `eq2_violates_allow` naming gets a README
  note ("historical name; the allowance column is no longer a paper object").
- **Page budget**: this deletes a display equation plus ~25 lines — it *funds*
  P3's added sentences (and, if space remains, the Q7 future-work clause the
  Q-round dropped).

### P2 — Trapezoidal W_g + re-run (2–3 days; the long pole; ALL code work lives here)
Code (4 sites + snapshot):
- Snapshot `v⁻` (lin + nothing else needed — gravity is linear-only) beside the
  existing `x_prev` capture in each host's substep.
- Replace `grav_work += m·g·(x⁺−x⁻)` with `grav_work += m·g·((v⁻+v⁺)/2)·h` in
  `solver_impulse.py:990–995`, `solver_xpbd.py:1231–1237`,
  `solver_6dof.py:2621–2627`, `solver_6dof.py:3290–3296`, each with
  `# DEVIATION` citing the paper Eq. (3) restatement and foundation §15.
- New unit test: a single free body under gravity, sweep h over ≥64×, assert
  per-substep and cumulative supply ≡ 0 to roundoff, all three hosts. This is
  Reviewer 2's exact probe; it becomes a shipped test.
Re-runs (CPU, existing harnesses under `benchmarks/paper_eval/x1_passivity/`):
- 72-cell matrix, ungoverned margins (Fig. 2 source) + governed 72; the 18
  deployed-budget T3 cells; `eq2_deployed.csv`; `eq2_utilization.csv`.
- **Not** re-run: ratio-R sweeps (Fig. 1, K-convergence, self-convergence — no
  ledger in R), FEM-reference §sec:gt, CPU/device perf.
Numbers that re-derive (update tex + NUMBERS.md + excerpts):
- tex:442 impulse margins ("0/24, worst −5.7×10⁻⁴ J" → expect roundoff-scale;
  state the resolution floor explicitly), tex:444–446 AVBD counts and
  magnitudes (23-of-24 and the S4 sentence — supply shrinks slightly, so counts
  can only hold or grow), abstract 70–73 counts, tex:259–263 (the ballistic
  sentence becomes *true* — keep it, now backed by the unit test), tex:700
  ("2–274×" re-derives against the new floor), governed 90-cell margins.
- Check: teaser/deployed governed trajectories bit-identical? γ firing pattern
  can change (smaller B). If any shown cell changes, re-render video +
  new hash; if not, video survives. Assert, don't assume.
- Bundle: regenerate changed CSVs, `LEDGER_EXCERPTS.md` §§ concerned,
  `SHA256SUMS`, re-run `smoke_test.py` from a clean unpack.

### P3 — Remaining verified defects (1 day, text + bundle)
- **S3**: after tex:640's 16×4 sentence, add the T3-scoped statement per
  `LEDGER_EXCERPTS.md:961–980`: deployed-budget overhead 6.6–34.3% (absolute
  0.30–2.22 ms, comparable to 16×4's 0.23–0.41 ms; the percentage grows because
  the baseline shrinks), and the dinner-scene negative overhead (−12.2%/−6.7%,
  outside noise) reported as measured with the suppression mechanism named as
  an unisolated conjecture. Keep the existing 120 Hz sentence (already
  consistent). Ship `perf_reps_{1x8,2x4}_summary.csv` into `supplement/data/` +
  CLAIMS_INDEX rows. Note: these are pre-P2 timings; wall-clock is unaffected
  by the W_g formula (same flop count) — state reps unchanged.
- **S4**: write from the P2 outputs, threshold chosen so the sentence is
  exactly true (e.g. "19 of its 23 below 0.15 J" or "21 … below 0.16 J",
  whichever survives).
- **S5**: fix tex:488 wording (endpoint diff vs max−min; both numbers exist,
  label them honestly).
- **S6**: tex:650 → "5.3–9.2 ms/step" per shipped `perf_device.csv`;
  CLAIMS_INDEX maps `truck` → "road slab (§3.5)". (Alternative: ship the R7b
  CSV and keep 5.0–8.9 — only if that CSV can be produced with provenance;
  otherwise don't.)

### P4 — Opus residuals (½ day)
- **S7**: scoping sentence where the 1×8-vs-reference accuracy is showcased:
  the reference is converged in K at S=1; a schedule-matched K×8 reference is
  unbuilt (future work). Stretch option (only if a single run fits the
  schedule): implicit K=500×S=8 on the shelf accuracy cell; include as a
  one-number footnote.
- **S8**: final class-language grep sweep (abstract/intro/conclusion).
- **S9**: put E-C11 (4×1 pose replay + close-up) to the PI as an explicit
  include/skip decision; it is the round's only remaining reviewer-visible gap
  that is deliberate.

### P5 — Freeze (1 day + buffer)
1. Rebuild; body must stay ≤6 pp + references; 0 overfull.
2. `NUMBERS.md` refresh; every printed number re-greppable to a shipped CSV.
3. CLAIMS_INDEX re-verify row-by-row (each claim → file → command), including
   the two named non-reproducible items (device timings, FEM reference).
4. Anonymization sweep (the Q-round deanon leak class: metadata, paths,
   commit strings in figures/video).
5. Supplement zip + SHA256; smoke test from clean unpack on a second machine.
6. EasyChair ID into the anonymous build (S11).
7. Optional clean-room re-panel (S12): neutral checkout, no CLAUDE.md/memory
   injection, fresh reviewers, artifacts by hash. Budget 1 day; treat as
   regression test (looking for *new* factual defects, not score movement).

Suggested calendar: P0–P1 by Jul 22 · P2 by Jul 27 · P3 by Jul 29 · P4 by
Jul 31 · freeze Aug 1–3 · re-panel/buffer Aug 3–5 · submit ≤ Aug 7.

---

## 3. Risk register

- **R1 (kills S1):** an XPBD/AVBD mirror deviates from the impulse loop order
  (e.g. debits pre-projection gain — note: even that case telescopes, since the
  clip then lands B at exactly 0 = B+c−d; the real killers would be
  test-before-credit or a non-quadratic rescale). If P0 finds one → fall back
  to Q2's Eq. (4) framing *and* re-measure the abstract count under (4);
  the paper stays submittable either way.
- **R2 (P2 flips a headline):** with phantom supply removed, an impulse cell
  could show a +1e-12-scale "violation". Mitigation is already designed: the
  N·tol tolerance from P0 plus an explicit stated resolution floor; "never
  overdraws" becomes "never overdraws above the accounting's stated floor".
  AVBD 23→24/24 would actually *simplify* the prose ("pervasive" without
  exception). Do not hand-tune tolerances to preserve a count.
- **R3 (video):** γ firing pattern changes on a teaser cell → re-render +
  re-hash + E-C9g entry. Detect by bit-compare, don't eyeball.
- **R4 (page budget):** P3 adds ~6 lines; P1 frees ~25. If the net goes tight,
  the Q-round's cut ladder (§9.9/§9.13) governs; S7's sentence is the first
  casualty, not the T3 rows (integrity beats completeness).
- **R5 (scope creep):** Fig. 1, E-S1b, the title, and the settle/stylization
  ideas are all frozen/adjudicated — no reopening inside this round.

## 4. Why this reaches "solid accept" rather than another 0.2

The two panels' criteria scores localize the gap: reproducibility is already
5.00; originality/technical/significance sit at 3.0–3.2 because (a) the
headline is measured against a bound the paper doesn't prove, and (b) a
reviewer who opens the supplement finds the paper's own instruction to report
a number it doesn't. P1 removes (a) by *strengthening* the theorem to what four
of six reviewers independently wanted and one proved for us; P2 removes the
only claimed physical property that is false as implemented; P3 removes (b),
the single finding with integrity flavor — the class that sinks borderline
papers. Everything else (S7–S9) is disclosed-limitation hygiene. After P1 the
paper is also *shorter and simpler* — the honest version costs nothing.
