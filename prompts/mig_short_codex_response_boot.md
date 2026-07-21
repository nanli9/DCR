# BOOT PROMPT — MIG short-paper codex-panel response pass (plan §7)

Paste this into a fresh Claude Code session at the repo root:

> Read `prompts/mig_short_codex_response_boot.md` and execute it, starting
> at C2.

Everything below is the work order for that session.

## What this is

A second simulated five-reviewer panel (codex) reviewed `paper/main_short.pdf`
(built 2026-07-18 23:28) and returned 3/5, borderline leaning weak reject,
with eight "highest-impact revisions". The response plan is
`docs/mig2026_short_paper_plan.md` **§7** (items C1–C8, one per revision);
each item carries its own acceptance criteria there. This session executes
**C2 → C3 → C4 → C6 → C7 → C5 → C8**, with C1 as a standing per-commit gate.
C5-G (ablations) is gated NO-GO by default — do not start it.

The review was independently verified on 2026-07-19 (see the §7 preamble)
before this plan was written. Trust that calibration:

- Do NOT redo the stale items: the page spill (#1) is already fixed (body
  ends p. 6, refs on p. 7), the TDPA/energy-tank/FEPR citations and the CPU
  overhead percentages already landed in `b359d0b`.
- DO trust the confirmed code finding: the paper's Enforcement sentence
  ("credited … before the contact solve") is WRONG about the implementation.
  All three hosts credit AFTER the velocity solve, same substep:
  `dcr/avbd/_solver/solver_xpbd.py:1241`, `solver_impulse.py:998`,
  `solver_6dof.py:2630`. C3 fixes the sentence, never the code.
- All five references the panel suggested are real and were verified against
  their PDFs; the three still to cite are enumerated in §7.8 (two are
  already in `references.bib`, uncited; kaufman2008 is a new entry — fill
  page numbers from DOI 10.1145/1409060.1409117, do not guess).

## Read first, in order

1. `CLAUDE.md`
2. `docs/mig2026_short_paper_plan.md` — §1 (binding claim discipline), §6
   (last round, for context and the E-S3 non-perturbation pattern), **§7
   (this work order)**
3. `docs/mig2026_results_ledger.md` — frozen numbers; nothing frozen there
   may change this round
4. `paper/main_short.tex` and `paper/NUMBERS.md`

## Hard rules

- Branches: code on `impulse-native-constraint`; tex ONLY in the `paper/`
  worktree (orphan branch, latexmk — never commit code there).
- **No solver behavior changes.** C6 is harness-side only (extend the §6.3
  budget list; E-S3-pattern wrappers must reproduce frozen clamp counts
  exactly). C5-G is the only gated exception and defaults NO-GO.
- Solver-behaviour numbers: **ARM M4 only**, frozen into
  `docs/mig2026_results_ledger.md` as entry **E-C6** (command + commit +
  machine) BEFORE the number enters the tex. `paper/NUMBERS.md` synced in
  the same pass.
- The frozen 24-cell matrix (§E-S1b) is immutable: C6's deployed-budget
  cells are reported as a SEPARATE table T3, never merged into Fig. 1.
- C2's coined term ("measured gross rigid-side loss") is defined once at
  Eq. (3) and used verbatim everywhere after; plan §1's thesis wording is
  updated in the same commit so plan and paper never disagree.
- Page gate (C1): after every tex commit, rebuild and confirm the body ends
  on p. 6 or earlier with references excluded. Overflow order: T3 detail →
  supplement, C8 figure → supplement, C3 float → in-paragraph lines.
- Commits: one per C-item — code branch messages `mig-short C<n>: <what>`,
  paper-worktree commits separate. Run each §7.x acceptance check before
  claiming the item done; log progress in `progress.md`, surprises in
  `findings.md`.

## Order of work

| Item | One line |
|---|---|
| C2 | Terminology sweep: replace every headline "contact dissipation" with the coined gross-loss term; ~9 phrase-anchored sites in §7.3; grep audit |
| C3 | Fix the Enforcement ordering sentence (post-solve, same-substep credit) + compact ledger pseudocode incl. "contact is NOT re-solved" (§7.4) |
| C4 | Scope the conclusion's "truncation artifact" claim to the position-based host (§7.5) |
| C6 | 18 deployed-budget cells (1×8, 2×4 × 3 scenes × 3 hosts), OFF+ON, five metrics, table T3; freeze as E-C6 first (§7.7) |
| C7 | Cite hauser2003 + rath2008 (already in bib), add kaufman2008; one attributing sentence each (§7.8) |
| C5 | "Equal row evaluations" heading + precise warm-start wording; record the C5-G gate decision (§7.6) |
| C8 | Governed/un-governed/reference sequence figure from frozen traces + 60–90 s anonymized supplementary video (§7.9) |

## Done means

All §7 acceptance criteria pass; `latexmk -pdf main_short.tex` builds clean
with the body ending ≤ p. 6 (refs excluded); the C2 and C3 grep audits are
clean ("dissipat"/"source-referenced"/"actually" each justified; zero hits
for "before the contact solve"); E-C6 is frozen with commands + commit +
machine; a red-team re-read against BOTH panels' blockers is written into
`findings.md`. Deadline: submit ≥24 h before **2026-08-07 23:59 AoE**
(window opens Jul 25; camera-ready Oct 8 if accepted).
