# BOOT PROMPT — MIG short-paper six-panel response pass (plan §8, P-round)

Paste this into a fresh Claude Code session at the repo root:

> Read `prompts/mig_short_sixpanel_response_boot.md` and execute it,
> starting at P0.

Everything below is the work order for that session.

## What this is

Two six-reviewer simulated panels reviewed `paper/main_short.pdf` on
2026-07-19 (panel A: the 05:23 build `f36166d…`; panel B: the 17:43 rebuild
`103ac0e…` of the current source). Both returned 3.5/7, weak reject as
framed, with the same consensus: the measurement/diagnosis is the
publishable core; the deficits are guarantee precision, evidential
robustness, and reproducibility. The response plan is
`docs/mig2026_short_paper_plan.md` **§8** (items P0–P9); each item carries
its acceptance criteria there. This session executes
**P0 → (P1+P2+P4+P5 as one tex pass) → launch P7 overnight → P3 → P6 →
E-C9 freeze + §3.2 → P8(a–c)**. P9 gates every commit.

The panels were verified on 2026-07-19 (see the §8 preamble). Trust that
calibration — do not re-verify, do not re-litigate:

- **Page spill is CONFIRMED and is a regression from `cbf57b6`**: the
  current source builds to 7 pages with the body ending on p. 7 (probe
  `\label` before `\bibliographystyle`; 0 overfull). The C-round "body ends
  p. 6" log predates that commit. This is P0.1 and nothing ships over it.
- **Fig. 3's in-plot label is stale**: `benchmarks/paper_fig/`
  `fig_s2_kconvergence.py:64` renders `"injection threshold"`. Fix the
  string, sweep the other short-paper figure scripts for
  `injection|dissipat`, re-render from frozen CSVs only (P0.2).
- **The Eq. (1) sign complaint was excluded correctly** (∂C/∂q = −U_y).
  No action.
- **Do NOT redo already-landed items**: reservoir terminology (C2),
  enforcement ordering + ledger block (C3), truncation scoping (C4),
  warm-start precision + as-deployed clause (C5), deployed budgets (C6),
  hauser/rath/kaufman citations (C7), the deflection-sequence teaser (C8).
  Both panels repeat blockers the paper already concedes in-text — those
  are position disagreements, answered; only §8's items are open.
- **Ablation scope is settled**: P7 is the *single-host robustness*
  ablation (config-level, verified: `h` / `n_modes_*` / `rayleigh_*` are
  scene-builder kwargs; XPBD `contact_compliance` / `support_compliance`
  are runtime attrs, `solver_xpbd.py:243-266`). The C5-G *cross-host
  matching* arms stay NO-GO; the carried-λ warm-start arm is a code change
  and stays barred — it is answered in text per §8.4.

## Read first, in order

1. `CLAUDE.md`
2. `docs/mig2026_short_paper_plan.md` — §1 (binding claim discipline), §7
   (last round, for the C6 harness pattern), **§8 (this work order)**
3. `docs/mig2026_results_ledger.md` — frozen numbers; E-S1b and E-C6 are
   immutable; this round adds **E-C9**
4. `paper/main_short.tex` and `paper/NUMBERS.md`

## Hard rules

- Branches: code on `impulse-native-constraint`; tex ONLY in the `paper/`
  worktree (orphan branch, latexmk — never commit code there). Figure
  scripts live on the code branch; rendered PDFs go to the paper worktree.
- **No solver behavior changes.** Allowed: figure-script label edits
  (plotting-only, P0.2) and harness extensions in the C6 pattern (P7 sets
  every knob at runtime via builder kwargs / solver attrs; it never edits
  solver source).
- Solver-behaviour numbers: **ARM M4 only**, serial runs only (the
  concurrent-run wall-clock corruption is a recorded incident), frozen into
  `docs/mig2026_results_ledger.md` as **E-C9** (command + commit + machine)
  BEFORE any number enters the tex. `paper/NUMBERS.md` synced in the same
  pass.
- **Gate v2, per tex commit, no exceptions** (the `cbf57b6` lesson): keep a
  permanent `\label{bodyend}` immediately before `\bibliographystyle`;
  after every commit rebuild and check with Python (never grep the log —
  recorded grep failure): `bodyend` page ≤ 6 from the `.aux`, total pages
  from the `.log`, 0 overfull via `re.finditer(r'Overfull[^\n]*', …)`.
- Page funding: cuts come from §8.2's ladder (floats before words; teaser
  caption, Fig. 2 caption's denominator sentence, forgiveness-paragraph
  compression; last resort Table 2 AVBD rows → supplement). No cut may
  touch a frozen number.
- **E-C9 contingency is pre-registered** (§8.4): if the rank sweep removes
  the amplification below the stiff cluster, that is a sharpened diagnosis
  (stiff-tail localization) — wording follows the numbers; acceptance is
  persistence-in-kind, not magnitude stability. Decide phrasing only after
  the ledger entry is frozen.
- Commits: one per P-item — code branch `mig-short P<n>: <what>`, paper
  worktree separate. Run each §8.x acceptance check before claiming an item
  done; log progress in `progress.md`, surprises in `findings.md`.

## Order of work

| Item | One line |
|---|---|
| P0 | Fix the p. 7 spill (cut ladder), re-render fig_s2 label, add `\acmSubmissionID{}` placeholder, install gate v2 (§8.2) |
| P1 | Scope attributive claims to "the three tested implementations"; grep-audit `formulation`; title unchanged (§8.3) |
| P2 | "One row" = one row law instantiated at every support contact; per-scene counts from the ledger (§8.3) |
| P4 | Cite macklin2016xpbd + giles2025avbd (in bib, uncited); add a VERIFIED sequential-impulse source or omit fields; name the two references once (§8.3) |
| P5 | Abstract gains the deployed-budget range (9.8 mm, 1.02–1.19×, E-C6) beside 21.6; bound re-billed as a deliberately minimal audited fail-safe — never "intentionally crude" (§8.3) |
| P7 | Launch E-C9 overnight: XPBD robustness over h/compliance/rank/damping on the two base cells + worst-cell K-ladder + nondimensionalized `min(C,λ)` residual re-log (§8.4) |
| P3 | One definition block (strict Eq. (2) / enforced ledger recursion / one-deposit allowance) + Proposition with induction sketch (§8.3) |
| P6 | Limitations: AVBD drift-floor multiple (offline from CSVs, freeze derived value) + supply partition-dependence sentence (§8.3) |
| E-C9 | Freeze ledger entry, then 2–4 sentences in §3.2; full table to the supplement (§8.4) |
| P8 | Supplement: scene-spec table, repro bundle, partition/recycling probes (offline-first), video placeholder (§8.5) |

The video (P8.d) is blocked on the user's interactive browser capture
session — do not attempt it headless; leave the supplement slot and note.

## Done means

All §8 acceptance criteria pass; gate v2 is green on the final build (body
ends ≤ p. 6, refs excluded, 0 overfull); the P1 grep audit is clean (every
surviving `formulation` justified as axis label); E-C9 is frozen with
commands + commit + machine and `paper/NUMBERS.md` agrees; the supplement
bundle exists and is anonymized; a red-team re-read against BOTH panels'
blocker lists is written into `findings.md`; hand to PI. Deadline: submit
≥24 h before **2026-08-07 23:59 AoE** (window opens Jul 25; fill
`\acmSubmissionID` after EasyChair registration; re-check video specs when
the portal opens).
