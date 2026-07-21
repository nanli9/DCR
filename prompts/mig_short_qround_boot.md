# BOOT PROMPT — MIG short-paper video-panel response pass (plan §9, Q-round)

Paste this into a fresh Claude Code session at the repo root:

> Read `prompts/mig_short_qround_boot.md` and execute it, starting at Q0.

Everything below is the work order for that session.

## What this is

A six-reviewer simulated panel reviewed the P-round build on 2026-07-19 —
for the first time WITH the video: PDF `627a14e…` (20:39 PDT build) +
`benchmarks/paper_fig/out/teaser_video.mp4` (`6dcd904…`, 44.77 s, 1080p).
Result: **4.17/7 mean, 4.5 median** (up from 3.5/7 in both P-round
panels); three weak accepts, one borderline, two weak rejects; verdict
"borderline, leaning weak accept — accept as a focused diagnostic short
paper, reject as a validated contact-control method; not a safe accept."
The full transcription is in `findings.md` §"Current PDF +
video-supplement review" (uncommitted at hand-off; Q0 commits it).

**Calibration (binding):** do NOT read 3.5 → 4.17 as an acceptance
probability — simulated panels are neither independent nor calibrated. It
means the remaining objections are identifiable. An advisor pass
(2026-07-19) sharpened the plan; its rulings are baked into §9 — where the
panel text and §9 differ, §9 wins.

The response plan is `docs/mig2026_short_paper_plan.md` **§9** (items
Q0–Q9); each item carries its acceptance criteria there. This session
executes **Q0 → Q1 → (Q2+Q3+Q4+Q7 as one tex pass) → full-audit rebuild →
Q5 fast path only → Q8**, with Q9 gating every commit. **Q6 is DEFERRED —
do not ask about it, do not build it.**

**The round's compass (§9.0):** the paper already takes the diagnostic
framing the verdict prices as acceptable, so every hour goes to precision
and packaging, none to mechanism. Reproducibility scored 2.00/5 — the
floor criterion — against a package that omitted the P8 supplement. That
gap is *mostly packaging with a small runnable-artifact gap*: the bundle
exists but still lacks runnable source, a claim→data index, versions, and
a smoke test. Q1 closes all of it.

The panel was fact-checked against the tex, the teaser manifest, and
`supplement/` on 2026-07-19 (§9.1). Trust that adjudication — do not
re-litigate, DO re-verify line numbers (they drift):

- **The reference-naming defect is REAL and manifest-verified**:
  `benchmarks/paper_fig/out/teaser_canonical.manifest.json` says
  `"solver": "xpbd", "converged": "500x1"`, while the body's §3.2
  definition block reserves "the converged reference" for the *implicit*
  realization at K=500. Fig. 1's caption and the video overlay borrow the
  wrong term. Q3 fixes it with NEW names (advisor ruling): **"implicit
  high-iteration reference (K=500)"** / **"XPBD high-iteration
  self-reference (500×1)"**, short handles "the implicit reference" /
  "the XPBD self-reference"; the word "converged" is RESERVED for
  statements where a checked criterion backs it. Audit-table-first, never
  rename blind.
- **The Proposition complaint is the paper's own disclosure read back**
  (the sketch already says "Strict (2) is not implied; it is observed…").
  The residual defect is at the CLAIM sites — the abstract's "enforced by
  a reservoir" and the contribution bullet are unqualified. Q2 promotes
  the one-deposit-relaxed bound to a numbered display (`eq:budgeted`) and
  applies the **binding vocabulary map**: *guarantees/certifies* →
  eq:budgeted ONLY; *observed* → strict Eq. (2); *limits/contains* →
  governor description. Avoid "enforced up to X" phrasings. Do not
  reprove the sketch.
- **The supplement complaint is mostly packaging with a small content
  gap**: the P8 bundle exists (~40 artifacts + ledger excerpts).
  Genuinely missing: runnable source snapshot (no `.git`), CLAIMS_INDEX
  (claim→data/command), dependency versions, clean-directory smoke test,
  SHA-256 sums, the video; and README §5 still says the video is "not
  included" — stale on both counts. This is Q1. **Redact commit hashes in
  the review bundle** (searchable hashes can break anonymity); scan zip
  member paths and generated metadata, not just file contents.
- **Do NOT redo landed items**: the definition block + Proposition (P3),
  scoping sweep (P1), deployed budgets (C6/P5), E-C9 robustness (P7),
  scene spec + probes (P8.a/c). The panel CREDITS these; the risks it
  keeps are either packaging (Q1) or the §9.1 residuals.
- **Do NOT "fix" the candor** — penetration/trajectory disclosures and
  the video's "bounded, not faithful" framing are why three lenses scored
  5/7. Protection list in §9.0.
- **The governor stays a fail-safe.** The contact-consistent composition
  is parked in §10, explicitly DO-NOT-EXECUTE; R8's NO-GO evidence
  stands; C5-G cross-host matching stays NO-GO; Q6's isolated minimal
  cell is deferred by advisor ruling. The future-work clause (Q7) is
  DELIBERATELY NONSPECIFIC — never name the §10 techniques in the paper.

## Read first, in order

1. `CLAUDE.md`
2. `docs/mig2026_short_paper_plan.md` — §1 (claim discipline), **§9 (this
   work order)**, §10 (parked; do not execute)
3. `findings.md` — §"Current PDF + video-supplement review" (the panel),
   §"P-round red-team re-read" (what is already closed vs still open)
4. `docs/mig2026_results_ledger.md` — frozen numbers; E-S1b, E-C6, E-C9
   immutable; this round may add **E-C11** (only if Q5's slow path runs)
5. `paper/main_short.tex` and `paper/NUMBERS.md`
6. `benchmarks/paper_eval/x1_passivity/make_supplement.py` (Q1 target)

## Hard rules

- Branches: code on `impulse-native-constraint`; tex ONLY in the `paper/`
  worktree (orphan branch, latexmk — never commit code there). Figure and
  video scripts live on the code branch; rendered artifacts referenced by
  the tex go to the paper worktree as before.
- **No solver behavior changes.** Allowed: assembler/packaging code (Q1),
  figure/video LABEL-text-only re-renders from frozen traces (Q3, the
  P0.2 precedent), harness-side pose-capture additions that never edit
  solver source (Q5 slow path — new files only; `scenes/` frozen builders
  untouched).
- Solver-behaviour numbers: **ARM M4 only, serial runs only** (recorded
  incident), frozen into the ledger (command + commit + machine) BEFORE
  any number enters tex or supplement README. `paper/NUMBERS.md` synced
  in the same pass. Q5's slow path must REPRODUCE the printed 21.6 mm to
  printed precision (non-perturbation check) — it exists to render
  frames, not to make numbers — and ranks BELOW all text and
  reproducibility work.
- **Gate v2, per tex commit, no exceptions**: `scripts/check_page_gate.py`
  after every rebuild (`bodyend` ≤ p. 6 from the `.aux`, total pages +
  overfull from the `.log` via the script — never grep the log). Q2's
  display equation is the main gate pressure; funding order: (iii) prose
  shrinks as its formula moves out, then drop Q7's clause, then the
  remaining §8.2 rungs. No cut may touch a frozen number.
- Video: **no duration target — 44.8 s is sufficient** (advisor ruling).
  The Q3 relabel must be label-text-only: verify 1,343 frames / 44.77 s /
  1920×1080 unchanged; record every new SHA-256; bundle and submission
  use ONE final render. A Q5 close-up is a scientific change: numeric
  penetration overlay matching NUMBERS.md, on-screen "bounded, but not
  faithful", and it stays a SEPARATE artifact until the user approves it.
- Anonymity: extended DEANON scan — case-sensitive `\bNan\b` with manual
  review (known false positives "dominant", float `nan`), `nli62220`,
  `usc.edu`, emails, repo URLs (`github.com|gitlab|git@`), `compshare`,
  home paths — over the whole bundle including the code snapshot;
  **commit hashes redacted in review copies** (private mapping kept for
  camera-ready); scan the final zip's member paths and metadata;
  assembler refuses on confirmed hits.
- Citation discipline: no new citations expected; if one becomes
  necessary, verify fields against the source or omit (kaufman2008 rule).
- **The ONE user decision this round**: Q5's cut approval, asked only
  when a close-up exists to show. Everything else proceeds without
  questions until the Q8 hand-off.
- Commits: code branch `mig-short Q<n>: <what>`, paper worktree separate;
  one commit per item; run each §9.x acceptance check before claiming an
  item done; log progress in `progress.md`, surprises in `findings.md`.

## Order of work

| Item | One line |
|---|---|
| Q0 | Adjudicate + commit the uncommitted workstream docs (plan §8/§9/§10, findings/progress panel entries — verify hunks by diff first); clean-rebuild gate check (§9.2) |
| Q1 | Supplement v2: runnable snapshot (no `.git`), CLAIMS_INDEX, version freeze, clean-unpack smoke test (qualitative asserts — ARM-exact digits only), SHA256SUMS, video wired in, README §5 rewritten, hashes redacted, one zip (§9.3) |
| Q2 | `eq:budgeted` display + Proposition points at it + vocabulary map (guarantees→relaxed bound / observed→strict / limits→governor) swept over every `enforc|guarante|certif|observ` hit (§9.4) |
| Q3 | "implicit high-iteration reference (K=500)" vs "XPBD high-iteration self-reference (500×1)"; "converged" reserved for checked criteria; per-site arm audit table FIRST; teaser caption + fig/video label re-render (§9.5) |
| Q4 | `formulation` → "tested host implementations" everywhere except the "one implementation each" pairings; `row law` standardization; grep audit (§9.6) |
| Q7 | ONE nonspecific future-work sentence (exact wording in §9.9; first thing dropped if gate goes red); `\acmSubmissionID{}` after Jul 25 registration (§9.9) |
| Q5 | CONDITIONAL close-up: fast path only from existing poses; slow path (E-C11 replay) only after everything else is frozen, skippable; USER approves any extended cut (§9.7) |
| Q6 | **DEFERRED — skip.** Design preserved in §9.8 for the long paper; do not ask, do not build (§9.8) |
| Q8 | Final assembly LAST (fresh snapshot/sums/zip post-final-commits), final gate + banned-terms + numbers re-verification + anonymity scan of the zip, red-team re-read vs this panel's six risks, PI handoff note (§9.10) |

## Done means

All §9 acceptance criteria pass; gate v2 green on the final build (body
≤ p. 6, 0 overfull); the Q2/Q3/Q4 audit tables are in findings.md with
every site adjudicated under the vocabulary map and reserved-word rule;
`mig26_supplement.zip` exists, is anonymized (hashes redacted, member
paths scanned), carries the video + runnable snapshot + CLAIMS_INDEX +
smoke test + sums, and was assembled AFTER the last commit; the smoke
test passes from a clean unpack; the Q5 outcome and Q6 deferral are
logged; the handoff note maps panel priorities (1)–(5) to landing sites
and restates what is deliberately unaddressed (§9.1 tail —
governed-vs-FEM, n=3 hosts, AVBD mechanism, contact-consistency → §10).
Hand to PI. Deadline: submit ≥ 24 h before **2026-08-07 23:59 AoE**;
EasyChair opens Jul 25 — register, fill `\acmSubmissionID`, re-check the
portal's video specs.
