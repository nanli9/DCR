# Finish the MIG 2026 practitioner-diagnostic rewrite (Stages E-finish → F → G)

## Orientation (do this before touching anything)
1. Read CLAUDE.md, then read `docs/mig2026_practitioner_diagnostic_rewrite_plan.md`
   IN FULL. The plan is the sole authority; its §15 amendment record is binding.
   This prompt authorizes executing its remaining stages.
2. Read `docs/mig2026_claim_sheet.md` (Stage A — claim→source map, nonclaims hard
   filter, terminology rules, and the §3a E6a vocabulary lock).
3. Read the frozen-evidence sections of `docs/mig2026_results_ledger.md`: **E1**,
   **E1b**, **E6a-1** (added this round) plus the R1/R3/R4/R5 sections the body
   already cites. Read `docs/mig2026_decision_table.md` (Table 1, drafted, NOT yet
   inserted).
4. Skim the tails of `findings.md`, `progress.md`, `task_plan.md` (search
   "2026-07-21 EXECUTE" and the Stage A–E entries) for exactly what is done.
5. The paper is LaTeX on the orphan worktree `paper/` (branch `paper`). Build:
   `cd paper && latexmk -pdf main_short.tex`. Page gate (run from `paper/`):
   `/Users/nan/Desktop/DCR/.venv/bin/python /Users/nan/Desktop/DCR/scripts/check_page_gate.py`.
   Number check (from repo root):
   `.venv/bin/python benchmarks/paper_eval/verify_paper_numbers.py`.
   Never commit code to `paper`; never commit paper text to code branches.

## Deadline
MIG 2026 short paper, due **2026-08-07** AoE. Committed core must land with margin
for Stage G.

## State: what is ALREADY DONE — do not redo
- **Stage A** complete: claim sheet + terminology frozen.
- **Stage B** complete, all frozen in the ledger + reproduced by CSVs in
  `benchmarks/paper_eval/x1_passivity/out/`:
  - **E1** (`run_e1_accounting_audit.py` → `e1_accounting_audit.csv`):
    AVBD/impulse accounting floor **≤10⁻³ J**, 3–4 orders below the 6.7 J AVBD
    effect (incl. the dinner scene). Cross-host control claim STANDS.
  - **E1b** (`run_e1b_neighborhood.py` → `e1b_neighborhood.csv`): every injecting
    headline cell fails in **16/16** deterministic perturbations (12 physical + 4
    row-order, cohorts separate); equal-row inversion + scene-dependence robust.
    **4.4×10⁷ J is the MAX of a 2.2–4.5×10⁷ J neighborhood** — round to that.
  - **E6a-1** (`run_e6a1_block_condensation.py` → `e6a1_block_condensation.csv`):
    honest NEGATIVE — shared-row block condensation does NOT fix the injection
    (comparable at 4×1, worse at every higher budget where the serial path
    converges/holds). Reproduced 2 scenes × 4 budgets. E6a-2 deferred (stretch).
- **Stage C** complete: three figures recomposed + staged in `paper/figures/`:
  `fig_teaser.pdf` (schematic strip + "governed (containment)" relabel, gen height
  2.05), `fig_xpbd_map.pdf` (Fig 2, XPBD-centered + control strip),
  `fig_operating_envelope.pdf` (Fig 3, R-vs-K + complementarity + E6a-1
  serial-vs-block). Decision Table 1 drafted in `docs/mig2026_decision_table.md`.
- **Stage D** complete: `paper/main_short.tex` north-star text rewritten (title,
  abstract, intro ¶1–2 with the WHY-TWO-WAY argument, contributions, conclusion,
  keywords, prior-art→1¶). Exit gate met.
- **Stage E** PARTIAL: Figs 2 & 3 swapped into the body; host-difference table
  (`tab:solvers`) moved to the supplement (critical diffs folded into prose,
  refs fixed); monitor-only device-GPU paragraph removed.
- **Build is CLEAN and VALID**: body ends p.6, 7 pages, 0 overfull, refs resolve,
  `verify_paper_numbers` 32/0. The paper is NOT a broken intermediate.
- **Fallback preserved**: current submission PDF is `32f2951d…`, recoverable via
  `git show c15457c:main_short.pdf`. Do not overwrite the fallback record.
- **Everything this round is UNCOMMITTED.** Code branch
  `impulse-native-constraint`: 3 new harnesses, 2 default-inert builder edits
  (`scenes/reduced_shelf.py`, `reduced_ledge.py`: `impactor_dx/dz/tilt`, verified
  byte-identical at defaults), 3 figure generators, docs (claim sheet, decision
  table, ledger E1/E1b/E6a-1), planning files. Paper worktree: reframed
  `main_short.tex` + 2 new staged figure PDFs. **First decide whether to commit
  this checkpoint** (separate commits: code+docs on `impulse-native-constraint`,
  manuscript on `paper`) before continuing.

## Remaining execution order (follow the gates; plan §11)

### Stage E — finish the 6-page body (committed core)
The north-star text + figures are reframed, but the **body §2–§3 prose and the
Limitations still read largely as the pre-rewrite text**. Do, in order, building +
page-gating after every meaningful edit:
1. **Integrate the new evidence into the body prose** (the abstract/intro/
   conclusion already reference it; the body does not yet):
   - E1 → a one-line control note near the cross-host comparison in §3.1
     ("a gravity/no-contact audit puts the control floor below 10⁻³ J, so 6.7 J is
     real injection").
   - E1b → replace/upgrade the current "Not a knife-edge configuration" paragraph
     in §3.2 with the 16/16 sign-robustness + magnitude spread, and round the
     headline 4.4×10⁷ J to the 2.2–4.5×10⁷ J neighborhood at the abstract, §3.1,
     captions and conclusion (they must all agree).
   - E6a-1 → add to §3.2 (mechanism): block condensation does NOT fix it; cite
     Fig. 3(c). Keep the E6a vocabulary lock (claim sheet §3a): the baseline uses
     implicit-midpoint; the ablated variable is serial-vs-block only.
2. **Structural reorder (plan §11 Stage E item 1): move the empirical failure
   BEFORE the bound/proof.** Currently §2 "The row and the cumulative bound"
   (with Prop. + proof + enforcement loop) precedes §3 Results. Target: the row +
   a minimal statement of the invariant up front (enough for §3 to reference
   `eq:invariant`/`eq:derig`), then the FAILURE (matrix + operating envelope),
   then the bound + proof + enforcement loop as a later section (page ~5 per the
   storyboard), then the guardrail cost. CARE: §3 references
   `eq:invariant`/`eq:derig`/`eq:gamma`; keep those labels resolvable — introduce
   the invariant lightly where first used and move only the proof/enforcement/loop
   detail. This is the biggest, most error-prone edit — do it incrementally,
   rebuilding after each move, and never leave the build broken.
3. **Insert decision Table 1** (`docs/mig2026_decision_table.md`) in the body
   (plan §10, page 6). It needs ~15 lines — recover them from Limitations/validity
   compression. If space truly will not allow it without hurting the evidence,
   keep the conclusion's ordered decision rule as the prose form and note the
   table lives in the supplement. The block-condensation row MUST report the
   E6a-1 negative ("not a fix; worse at deployable budgets"), not a recommendation.
4. **Consolidate** the repeated 72/60/90/78 counts into one protocol note (plan
   §8), and the Limitations per plan §6 Page 6. Keep 8/24 (incident-ratio) and
   9/24 (strict Eq. 2 ledger-margin) DISTINCT everywhere.
5. **Terminology sweep** of the body: no bare "XPBD" where "our tested XPBD
   implementation" is required; no unqualified "passivity"; never "explicit modal
   integration". Grep after the reorder.
- Exit gate: body ends p.6, refs p.7, 0 overfull, all refs resolve,
  `verify_paper_numbers` still passes, every claim maps to a claim-sheet source.

### Stage F — artifact + video
1. Re-run the E0 supplement assembler LAST (after the final tex commit):
   `.venv/bin/python benchmarks/paper_eval/x1_passivity/make_supplement.py`. It
   must now bundle the E1/E1b/E6a-1 CSVs + manifests, the new figure generators,
   the full host-difference table (supplement-only) and the full 72-cell
   three-implementation heatmap (`fig_s1_solver_matrix.py`, kept for the
   supplement). Run its smoke test from a clean unpack; re-check the CLAIMS_INDEX
   self-check and SHA256SUMS.
2. Video per plan §12 (~2/3 NEW footage: schematic, 32×1-vs-4×8, band panel,
   decision card are new; only the launch and containment clips survive). Write a
   one-page asset inventory first. The offline render path uses frozen pose npz +
   `benchmarks/paper_fig/render3d.py`; a live capture may still be blocked
   (historical blocker) — if so, surface it as the one user-action item.
3. Fill `\acmSubmissionID{}` after EasyChair registration (window opened Jul 25).
   Hash the final PDF + video + supplement together.

### Stage G — adversarial re-review
Six isolated reviewers, final PDF/video/supplement only, comprehension questions
(why modal DOFs; why not the impulse realization; main contribution; when the
governor) BEFORE scores. At most ONE rewrite cycle. Then compare against the
frozen `32f2951d…` fallback under the same rubric and keep the stronger packet.

## Binding discipline (do not relax)
- Every claim → one frozen evidence source; the §4 nonclaims list is a hard filter.
- Keep 8/24 (incident-ratio) and 9/24 (strict ledger-margin) distinct everywhere.
- Never call the scalar ledger "passivity"; never call the modal restoring step
  "explicit" (it is implicit midpoint).
- One-cell results are causal probes, not recommendations.
- Round headline magnitudes (incl. 4.4×10⁷ J) to E1b-supported precision.
- A negative experimental result is valid — E6a-1 (block ≠ cure) is reported, not
  rescued.
- Page 2 must keep the WHY-TWO-WAY argument; the dense shared-`q` paragraph is the
  generality bridge; do not name specific engines in motivation without verification.

## Gotchas / commands (learned this round)
- Use a **distinct `--out`** for any harness you re-run — running R1's
  `run_eq2_utilization.py` with its default `--out` overwrites the frozen
  `eq2_utilization.csv` (restore with `git checkout -- <path>` if it happens).
- From the `paper/` worktree, the venv is at the absolute path
  `/Users/nan/Desktop/DCR/.venv/bin/python` (relative `.venv` is not there).
- matplotlib needs a writable cache; importing `benchmarks/paper_fig/figstyle`
  sets `MPLCONFIGDIR` for you. Regenerate a figure with
  `.venv/bin/python benchmarks/paper_fig/<gen>.py`, then `cp` the PDF from
  `benchmarks/paper_fig/out/` into `paper/figures/`.
- macOS has no `timeout`; run long harnesses in the background.
- Post-build edits to solver/DCR body state do NOT propagate (the solver re-reads
  the build-time pose each step); perturbations must go through builder kwargs.
  `sol._support` list-order permutation DOES propagate.

## Working style
- Announce which stage you are working on at the top of each response.
- Report each exit gate with evidence (build output, page gate, ledger rows,
  figure paths) before advancing. Update findings.md / progress.md / task_plan.md.
- Ask before anything destructive or outside the plan. When the plan and
  expedience conflict, the plan wins; when the plan is silent, propose and mark
  the choice.
