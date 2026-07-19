# BOOT PROMPT — MIG short paper, R5 (plan §6.7)

Paste this into a fresh Claude Code session at the repo root:

> Read `prompts/mig_short_R5_boot.md` and execute it.

---

## Where things stand

R0–R4 and R7b are **done, committed and frozen**. R5, R6, R7 remain.

| item | code branch | paper worktree |
|---|---|---|
| R0 ten text fixes | `7c621dc` | `e62880c` |
| R7b device re-verification | `250b45d` | `50d881d` |
| R1 Eq.-(2) measured un-governed | `73c95c5` | `aae0c2c` |
| R2 ledger pinned in-paper | `29ed217` | `3d7f3df` |
| R3 controlled comparison | `14983e0` | `4a92015` |
| R4 self-convergence (negative) | `bf391b6` | `e9e3c2d` |

Branches: code on `impulse-native-constraint`; tex ONLY in the `paper/`
worktree (orphan branch, `latexmk -pdf main_short.tex`). Never commit code to
`paper/`. Paper currently builds at **6 pages**, 0 undefined refs, 0 warnings.

## Read first, in order

1. `CLAUDE.md`
2. `docs/mig2026_short_paper_plan.md` — §1 (binding claim discipline) and
   **§6.7** (the R5 work order)
3. `docs/mig2026_results_ledger.md` — read the **R1, R3 and R4 sections at the
   end**; they change what R5 can claim (see "What R1–R4 changed" below)
4. `findings.md` — the last four sections; three of them are corrections of my
   own mistakes and carry lessons that apply directly to R5
5. `paper/main_short.tex` §3.1–3.3

## Hard rules (unchanged, and one addition)

- **No solver behaviour changes.** All new measurement is harness-side
  wrappers, provably non-perturbing. The established pattern, used by R1/R3/R4:
  set `_enforce_modal_passivity = True` so the ledger runs live, then force
  module-level `passivity_gamma` to return `1.0` — every state write in all
  three enforcement paths is guarded by `if gamma < 1.0`
  (`solver_xpbd.py:1244`, `solver_6dof.py:2639`, `solver_impulse.py:1003`), so
  the branch is dead and the trajectory is bit-identical to un-governed.
  Verify by reproducing frozen E-S1b values exactly (`--check-frozen`).
- **AVBD's ledger must be PRE-CONSTRUCTED** or it silently measures nothing —
  it builds lazily on the first substep (`solver_6dof.py:2449`), unlike XPBD at
  `set_modal_support`. See `run_eq2_utilization.py` for the three-line fix.
  This is the single most likely way to waste an hour on R5.
- **Solver-behaviour numbers: ARM M4 only**, frozen in
  `docs/mig2026_results_ledger.md` with command + commit + machine BEFORE the
  number enters the tex. The compshare pod is x86 and is for device timings
  (`docs/mig2026_device_ledger.md`) and correctness checks only.
- **ADDITION, learned the hard way this session: sanity-check every derived
  quantity before reporting it.** Two metrics I wrote were wrong and had to be
  retracted — a ratio whose denominator accumulated from zero (inflated a
  0.13 J overdraw into "U = 20"), and an FFT ring frequency that moved with
  window length. Check a ratio against absolute joules, and check any spectral
  or windowed quantity is stable under a parameter it should not depend on.
- One commit per R-item, message `mig-short R<n>: <what>`, code and paper
  committed separately. Log progress in `progress.md`, surprises in
  `findings.md`.

## What R1–R4 changed that R5 must respect

1. **The verdict is the strict Eq. (2) margin in JOULES**, not a ratio and not
   `passive()`. `margin_J = max_n[E_mod^n − E_mod^0 − η Σ_{k≤n} max(ΔE_rig,0)]`;
   `> 0` violates. The implementation's `passive()` additionally forgives one
   substep's largest deposit (7–389 J in these scenes) — that leniency is
   documented in §2 but is NOT what we report. User decision, 2026-07-19.
2. **R is a severity diagnostic only.** "Injects" is reserved for `R > 1`;
   "violates" for Eq. (2). Do not reintroduce the conflation.
3. **XPBD does not converge to the oracle** (R4): it plateaus at ratio 0.2996
   vs the oracle's 0.2735, and the deflection trajectory differs by 34% of
   peak. **This directly constrains R5's headline number** — see below.
4. **The return channel is large** (102–118% on AVBD), so any statement about
   "energy contact dissipated" carries the Limitations caveat.

## R5 — the work order (plan §6.7)

### R5.1 Accuracy quantification — RECHECK THE ARITHMETIC FIRST

Plan §6.7 says: at shelf 8×2 relax 0.7, ungoverned R = 53.7, governed realized
1.011, converged reference 0.2735 → "energy error to the reference falls from
~200× to ~3.7×".

**Verify this before writing it.** Two reasons it may not survive:
- R4 showed the converged position-based host reaches **0.2996**, not the
  oracle's 0.2735. Which denominator is the right "reference" for a governed
  XPBD run is now a real question — arguably 0.2996 (what this host converges
  to) rather than 0.2735 (what a different host converges to). State the
  choice explicitly whichever way you go.
- 53.7/0.2735 = 196 and 1.011/0.2735 = 3.70, so the arithmetic works, but these
  are RATIOS of ratios. Consider also reporting it in joules, consistent with
  the R1/R3/R4 convention.

Then compute the deflection-trace counterpart (governed vs oracle), reusing
`run_selfconvergence.py`'s `_deflection()` and L∞ machinery.

Frame honestly, per the plan: the governor moves an unusable trajectory to
within a few × of the reference energy; it is a **safety envelope, not an
accuracy device**.

### R5.2 Table-1 completion — AVBD validity rows

Port the E-S3 wrappers (`run_projection_validity.py`) to the AVBD host
(`solver_6dof`) and add the table-scene 4×1 rows, forcing the clamp exactly as
E-S1b caveat 3 describes (`_psv_monitor_only = False`, a measurement-side
override, not a solver change). Note E-S3 currently covers XPBD only, and its
`_gaps()` reads `sol._support` / `sol._q` — check the AVBD equivalents before
assuming the helper ports unchanged.

### R5.3 Qualitative triptych

One strip, three frames, same timestamp: ungoverned / governed / converged
reference. Reuses the committed video shot-list pipeline.

### R5.4 Normalized penetration

R0 deferred half of plan §6.2 item 10 to here. The geometry half is already in
the paper (21.6 mm = 72% of the 30 mm board thickness, 2.7% of the 0.8 m span,
frozen in the ledger's R0 section). **Still missing: the unclamped static sag
of the same cell**, which needs an instrumented run — that is why it was
deferred. Measure it and complete the normalization.

### Acceptance (plan §6.7)

Numbers frozen in the ledger with command + commit + machine; Table 1 covers
the AVBD problem cells; triptych renders; `latexmk -pdf` builds clean.

## Watch the page budget

The paper is at **6 pages**, which is the CFP ceiling excluding references.
R5 adds a table block and a figure. Plan §6.12's demotion order if it
overflows: **substep sweep first, then the triptych**, to supplementary.

## Then R6 and R7 (do not start before R5 is committed)

- **R6** (§6.8, ~0.25 d, no compute): add passivity observer (Hannaford & Ryu
  2002), energy tanks (Franken et al. 2011 / Ferraguti et al.), FEPR (Dinev et
  al. 2018) with one framing sentence each. Position the reservoir as a
  passivity-observer transplant with a gross-loss supply and a state-space (not
  force-space) actuator; FEPR preserves TOTAL energy, ours caps one subsystem's
  storage. These join, not replace, the four must-cite adversaries of §1.
- **R7** (§6.9): the device half is **already done** (R7b, committed). Only the
  CPU half remains: baseline step time next to the 0.8–2.9 ms ledger overhead,
  as a percentage, per scene/budget. §3.5 already names the RTX 4090, keeps
  "monitor-only" explicit, and states the qualified real-time sentence.
- **R8 remains NO-GO by default** (§6.10). Do not start it.

## Done means

All §6 acceptance criteria pass; `latexmk -pdf main_short.tex` builds clean in
the paper worktree; a D9-style red-team re-read against the five panel blockers
is written into `findings.md`. Deadline: submit ≥24 h before
**2026-08-07 23:59 AoE** (window opens Jul 25).
