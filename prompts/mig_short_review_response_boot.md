# BOOT PROMPT — MIG short-paper review-response pass (plan §6)

Paste this into a fresh Claude Code session at the repo root:

> Read `prompts/mig_short_review_response_boot.md` and execute it, starting
> at R0.

Everything below is the work order for that session.

## What this is

A five-lens MIG panel review of `paper/main_short.pdf` (2026-07-18) returned
borderline / weak reject with one central blocker: the paper measures the
incident-energy ratio R = peak E_mod / peak incident rigid KE but repeatedly
claims in Eq.-(2) (cumulative invariant) language. The full response plan is
`docs/mig2026_short_paper_plan.md` **§6** (items R0–R8); each R-item carries
its own acceptance criteria there. This session executes **R0 → R7 in
order**. R8 is gated NO-GO by default — do not start it.

## Read first, in order

1. `CLAUDE.md`
2. `docs/mig2026_short_paper_plan.md` — §1 (binding claim discipline) and §6
   (the work order)
3. `docs/mig2026_results_ledger.md` — frozen numbers; E-S1b caveats 1–3 are
   load-bearing for R1
4. `paper/main_short.tex` and `paper/NUMBERS.md`

## Hard rules

- Branches: code on `impulse-native-constraint`; tex ONLY in the `paper/`
  worktree (orphan branch, latexmk — never commit code there).
- **No solver behavior changes.** All new measurement is harness-side
  wrappers, provably non-perturbing (the E-S3 pattern: wrapped runs must
  reproduce the frozen clamp counts exactly).
- Solver-behavior numbers: **ARM M4 only**, frozen into
  `docs/mig2026_results_ledger.md` (command + commit + machine) BEFORE the
  number enters the tex. Device timings are the single exception and live in
  `docs/mig2026_device_ledger.md` (separate file, separate machine).
- Claim wording follows plan §1 + §6. The abstract's AVBD supply-bound
  sentence is rewritten only AFTER R1's utilization (U) numbers land — do
  not pre-write it.
- Commits: one per R-item, message `mig-short R<n>: <what>`, on the code
  branch; paper-worktree commits separate.
- Run each §6.x acceptance check before claiming an item done; log progress
  in `progress.md`, surprises in `findings.md`.

## Order of work

| Item | One line |
|---|---|
| R0 | Ten pre-verified text fixes in `main_short.tex` (§6.2 list) |
| R1 | Measure Eq.-(2) utilization U, clamp OFF, all 72 cells; new heatmap panel; re-base all "supply bound" prose (§6.3) |
| R2 | Exact ΔE_rig / η=1 / γ definitions in-paper + measured modal→rigid return-transfer + recycling caveat (§6.4) |
| R3 | Solver/parameter table T2 + row-evaluation accounting + substep-only sweep + complementarity residuals (§6.5) |
| R4 | XPBD self-convergence K→500 + state-level agreement vs oracle (§6.6) |
| R5 | Governed-vs-oracle accuracy (~200×→~3.7×) + AVBD table-scene rows in Table 1 + triptych (§6.7) |
| R6 | Governor prior-art: passivity observer, energy tanks, FEPR + framing sentences (§6.8) |
| R7 | CPU overhead as % of stated baseline; device paragraph named + monitor-only explicit (§6.9) |

## R7b — the server run (user-requested, non-blocking)

Blocked on the user starting the compshare pod (2026-07-18 probe: connection
closed at the stale pod hostname). When the user says the pod is up:

1. Push `impulse-native-constraint` to origin (not on GitHub yet), then on
   the server sync `~/DCR` to the branch tip.
2. Run:
   `~/dcr-venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_device.py
   --frames 200 --device cuda:0 --scenes shelf,ledge,dinner,truck`
3. Record + diff per plan §6.9 R7b (reference: 5.64/6.82/8.87/9.20 ms @16×4;
   16×2 ledge 3.28 / dinner 4.65); re-check the qualified real-time sentence
   against the fresh `rt_factor_120hz`; update §3.5 + `paper/NUMBERS.md` if
   the band moved.

## Done means

All §6 acceptance criteria pass; `latexmk -pdf main_short.tex` builds clean
in the paper worktree; the R0 grep audit is clean; a D9-style red-team
re-read against the five panel blockers is written into `findings.md`.
Deadline: submit ≥24 h before **2026-08-07 23:59 AoE** (window opens Jul 25).
