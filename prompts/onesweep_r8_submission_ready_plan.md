# One-sweep short paper: R8 submission-ready plan (written 2026-07-29)

Target: `/Users/nan/Desktop/DCR/paper/onesweep_short.tex` (worktree branch `paper`, code-free).
Baseline artifact verified this session: `onesweep_short.pdf` sha256
`d4716b9d0b786f2e6d5e3071da66975f3c0246fab61af6f265bc79a24a2606c8`, body 5.4983 on the
column-aware ruler (References word at page 6, xMin 317.955 > 300 so col 2, yMin 85.86,
f = -0.00339, body = 5 + (1 - 0.00339)/2 = 5.4983). Every claim below was re-verified against
the .tex, the PDF, the two panel reports, the T-suite scripts and the CSVs; sites are
file:line anchors into the CURRENT files.

BINDING GUARDS, restated because two of the last three rounds contained a false reviewer claim:

- The four DO-NOT-FIX items stand. (1) Eq. (6) at tex:770-773 keeps its single `- \Rr`;
  (2) body "shelf $2/9$" at tex:1070 stays; (3) "for every $\kappa \neq 0$" at tex:784 stays;
  (4) **Thm 3.2's printed compliance form `\rho = L/(\wm + 2\tilde\alpha)` at tex:745-746 stays
  exactly as printed.** Item E below adds a LEDGER-LABELING sentence and must not alter any
  `2\tilde\alpha` anywhere: the printed rule signs the paper's own Eq.-(6) ledger with 0
  mis-signs over 200,000 draws; the "fix" to `\wm + \tilde\alpha` mis-signs 1970 of them.
- Never run a mutating git command in either worktree. Never touch `paper/main_short.tex`.
- T-suite convention: NEW scripts only; never edit an existing file under
  `benchmarks/paper_eval/t_onesweep/` (this includes `make_figs.py`, `fix_rowindex_legend.py`,
  `make_supplement*.py`, `run_t14_*.py`); new scripts import them.
- No em/en dashes; `--` only in bib page ranges and the ACM date boilerplate. No AI-tells.
- Any number introduced into the body gets its CSV provenance bullet in the .tex header
  comment block IN THE SAME EDIT.
- Measure the ruler after EVERY batch (formula in the header of this plan's source prompt;
  pdftotext -bbox-layout, References word). Sub-line trims across different paragraphs buy
  0.0000; a paragraph must lose a whole ~60-char column line (~133-char full-width line).
- Stale-context correction: the Fig. 3 include line is NOT `trim=0 60 0 30 ... 0.92\textwidth`
  any more. The CURRENT line, tex:919, is
  `\includegraphics[trim=0 74 0 40,clip,width=0.88\textwidth]{fig_onesweep_rowindex.pdf}`.
  \textwidth = 506.295 pt (build log), so scale = 0.88*506.295/1005.84 = 0.4430 and the
  rendered height is (457.864-74-40)*0.4430 = 152.3 pt. Drawn 7.6 pt readouts print at
  3.37 pt, matching R4's measured 3.35 pt. Plan around THESE numbers.

---

## 1. Verified status, item by item

### A. Figure 3 (author-mandated) — DEFECTS REAL, all five confirmed at source

- Artwork built by `make_figs.fig_rowindex()` (make_figs.py:152-425). Confirmed in code:
  - Stale non-printing caption = the artwork's own suptitle + footer bands:
    `fig.suptitle("Shipped XPBD support row: ...")` at make_figs.py:411 and the 5-line
    `fig.text(0.5, -0.16, "Left: ... rho_matched < 1 ...")` at :414-425. The paper's trim
    crops them visually; the strings stay in the content stream. This is simultaneously the
    only `rho_matched` in the document and the `XPBD` de-anonymization-adjacent leak.
  - Sufficient-stated-as-necessary annotation `(passive only where 2(w_row-w_r) <= w_r)` at
    make_figs.py:297, drawn 7.6 pt (prints 3.37 pt). Also uses `w_row`, a symbol the body
    never defines.
  - Inset `axM.inset_axes([0.63, 0.10, 0.34, 0.26])` at :309, fonts 6-7.5 pt drawn
    (2.66-3.32 pt printed); it overlaps the middle readout box at (0.03, 0.03), which is how
    the inset's `2`/`4` x-ticks print through "shelf 2/9, ledge 4/9".
  - Right-panel readout prints `rho_matched < 1 all cells (max %.2f)` at :375-386.
  - The red rectangle near the inset's `2` tick: no dedicated artist; the candidates are the
    agreement-quadrant `plt.Rectangle(..., color="#d62728", alpha=0.2)` patches (:251-257)
    whose edges pass under the inset. Root cause is not load-bearing: the repair is verified
    on a 300 dpi render, whatever drew it.
- Constraint verified: `fix_rowindex_legend.py` exposes `build_figure()` (make_figs with
  `_save` intercepted) and `repair(fig)` and hard-gates on MediaBox 1005.84 x 457.864
  (REQUIRED_MEDIABOX at :74). Its own docstring records that raising in-panel type inside the
  pinned canvas was tried and collides: type size is a canvas problem while the paper keeps
  the absolute trim.

### B. Table 1 T14 row + T12 (author-mandated) — DEFECT REAL

- PDF/tex confirmed: Table 1 rows are T1-T11, T13 (tex:989-1001). `T14` appears in body prose
  exactly twice, tex:1124 (equal-cost amplitude 0.57/0.85) and tex:1201 (warm/two-row
  limitation numbers), with no model/cells/criterion anywhere. `T12` appears zero times in
  the typeset paper; the supplement ships `run_t12_hypotheses.py` + `t12_hypotheses.csv`
  (confirmed in `supplement_onesweep/code/t_onesweep/` and `data/`).
- The two denominators EXPLAINED, verified in `run_t14_warm_multirow.py`:
  `combined_cells_mass = 43,783` and `combined_cells_matched = 43,898` are sums of
  `n_active` over identical parameter draws (block D reseeds `default_rng(20260728)` per arm,
  comment "same draws in every arm"; block B grids are deterministic). A cell counts only if
  the row is ACTIVE under that arm's weight (block B skips `not c["active"]`, :381-385;
  block D requires `min(dlam) > 0`, :698-700), and activity depends on the weight. Same
  population of draws, weight-dependent active subsets. One clause states this.
- Also verified for the row content: for the matched arm `pred_inj = False` always
  (run_t14_warm_multirow.py:388-390, :702-705), so its `false_neg` IS its injection count;
  for the mass arm `false_neg` is an index miss, NOT an injection count. This is exactly why
  item J's number is missing (see J).

### C. Supplement packaging — GAP REAL

- `supplement_onesweep/` (README, SHA256SUMS, code/{host_excerpt,t_onesweep,x1_passivity},
  data/, 35 data entries) and `supplement_onesweep.zip` (6,672,894 B) both exist, built
  2026-07-28 19:30 — BEFORE the T14 text landed (PDF 22:39). Verified absent from the
  package: `run_t14_passive_family.py`, `run_t14_equalcost.py`, `run_t14_warm_multirow.py`,
  `run_tcost.py`, and ALL `t14_*.csv` / `tcost_*.csv`. The paper cites T14 twice and prints
  tcost's 0.99-1.02 and 6.8-14.5 ratios, so the shipped package cannot audit them.
- Build path exists and is the right one: `make_supplement_full.py` (NEW, 07-28) fixed the
  import-shim problem, re-runs every runnable check from a clean copy, hard-gates on
  anonymity, and is table-driven: "REGISTERING A NEW T-SCRIPT IS ONE LINE. Append one
  `TS(...)` row to TSCRIPTS" (:33, TSCRIPTS at :84). Convention forbids editing it; a new
  script imports it and extends `TSCRIPTS` programmatically.

### D. Blanket scope wording — DEFECT REAL, three body sites plus one abstract site

- tex:515-517 (abstract): "Every statement is confined to one sweep from a cold start..."
- tex:588-589 (Sec 1): "Every statement is confined to one Gauss-Seidel sweep..."
- tex:666 (Scope box heading): "(stated once, binding for every result)"
- tex:1197 (Limitations): "Section~\ref{sec:model}'s scope binds every result"
- The inconsistency is real: Section 4 prints multi-iteration (tex:1114-1124) and Section 6
  warm/two-row (tex:1200-1206) MEASUREMENTS, so "every statement/result" is false on its
  face. Panel remedy "every theorem/guarantee" is correct and cheap.
- Second clause of the panel's mandatory #2 (label the scenes beyond-theorem): the
  system-corroboration paragraph tags its protocol "(hard contact, cold impacts)" at
  tex:1080-1081 while its scenes carry warm resting rows from the second substep onward
  (r7-confirmed video evidence: 65.2 J board-mode energy before the impactor lands). One
  clause fixes it in the body; the video itself is frozen (see §5).

### E. Theorem precision (W PSD; alpha-tilde ledger; both-places) — PARTLY REAL

- W assumptions: REAL GAP. Thm 3.3 (tex:765-766) says only "a charge operator $W$";
  Cor. 3.4 (tex:813-814) uses the Loewner order, which presupposes symmetry, without stating
  it. The harness (run_t14_passive_family.py block C) draws symmetric PSD W and its header
  proves the interval equivalence "for symmetric W with G > 0". Add the words.
- alpha-tilde ledger: REAL GAP, and it must be repaired WITHOUT touching any formula
  (DO-NOT-FIX #4). Verified: Eq. (2) (tex:657-661) is called "the true Hamiltonian" and is
  bodies-only; the only accounting disclaimer (tex:834-838) covers damping, not compliance.
  Coordinator-verified facts to print: a compliant row solved cold retains
  $C^+ = -\tilde\alpha\lambda^+$, storing $\tilde\alpha v^2/(2D^2)$ that Eq. (2) does not
  count; read against total energy including that term every $2\tilde\alpha$ threshold
  tightens to $\tilde\alpha$ (the displayed ledger is permissive in exactly the band
  $\wm + \tilde\alpha < L < \wm + 2\tilde\alpha$); every $\tilde\alpha = 0$ statement and
  every shipped measurement (all hard contact) is unchanged; and the matched charge is
  passive under either ledger, the total change being
  $-(v^2/2D^2)(\Rr + a + \tilde\alpha) < 0$ (R1's check, coordinator-confirmed).
- Both-places (denominator AND correction): MOSTLY ALREADY SATISFIED — verified present in
  the abstract (tex:503-504 "in both the row denominator and the correction"), C1 bullet
  (tex:598-599), and Thm 3.3's hypothesis (tex:766-767 "used in both the denominator of (1)
  and the position correction"). The one place a practitioner reads for instructions,
  Sec. 6's weight-choice paragraph (tex:1184-1195), lacks it; the item-F recipe carries it.
- Adjacent, same class, r7 item 10 CONFIRMED and cheap: the abstract sentence
  (tex:504-507) omits Thm 3.3's rigid read-back hypothesis ($\Delta z/h$, i.e.
  $\kappa_r = 1$); Remark 1 in the body is fully correct. Add the qualifier to the abstract.

### F. Implementation recipe + c=1 vs c=2 — GAP REAL; evidence on disk, no new experiment

- No recipe box exists; the shipping procedure is distributed across Rmk. 1, Sec. 3, Sec. 4,
  Sec. 6 (R5: "six lines of pseudocode ... would replace all of it").
- The general-kappa index R1 proposed is ALGEBRAICALLY VERIFIED here from the paper's own
  Eq. (6) with $W = M_c^{-1}$: $u^{\top}Gu = \kappa^2\sum a_i + L$, $J_c^{\top}u = \sum a_i$,
  so mass-only injection is exactly
  $\rho_\kappa = [L + (\kappa^2 - 2)\sum_i a_i]/(\Rr + 2\tilde\alpha) > 1$.
  At $\kappa = 2$ this IS the printed $\rho_{\mathrm{mid}}$ (tex:1063); at $\kappa = 1$ it
  shares the unit threshold with Thm 3.2's $\rho$ (equivalent sign, different value away
  from 1 — say "same threshold", not "same index"). Provenance: already validated as the
  T7 boundary (t7_reconstruction.csv, 7000 cells) and T12 block B (0/4000 misclassified at
  five $(\kappa_r,\kappa)$ pairs); no new run needed.
- c-comparison numbers verified in `out/t14_passive_family.csv`:
  - block G1_margin: headroom_c1 min 1.0000042 (>=100% on all 4000), p50 1.7111;
    headroom_c2 p50 0.35555, frac_lt_1pct 0.20825 at c=2 vs 0.0 at c=1.
  - block F_endpoint: q_ratio_c2 = 1.0 to 2e-16 at b in {0.01,...,1e4}; q_ratio_c1 runs
    0.50005-0.5998 (the $(M+\mu_*)/(M+2\mu_*)$ interval), cross-checked against shipped
    t11_accuracy.csv columns.
  - Robustness argument verified from the script's own (T14-5): a misestimated charge is the
    family at $c_{\mathrm{eff}} = c\,G/\hat G$; at c=1 a twofold misestimate in either
    direction stays in $[0,2]$ ($\hat G = G/2 \to c_{\mathrm{eff}} = 2$;
    $\hat G = 2G \to 0.5$); at c=2 any underestimate of $\hat G$ exits.
  - The paper ALREADY prints the headroom sentence (tex:1191-1193) and "returns the converged
    amplitude exactly at the cost of margin". New content = the amplitude ratio for c=1, the
    two medians, and the interval-centre robustness clause. A c=1.5 arm does not exist on
    disk and is NOT required by the author scoping; a shipped-host c=2 arm stays deliberately
    un-run (r6 plan §8.1 binding scope; §9.8 records it as the known open item).

### G. EasyChair ID — ALREADY STRUCTURALLY SATISFIED; author action only. STRIKE from edits.

- tex:427: `\acmSubmissionID{}%` with the comment "fill upon assignment". Nothing to edit;
  no ID exists and none may be invented. Deliverable: one line in the author checklist.

### H. Companion overlap — PAPER TEXT ALREADY ADEQUATE; the disclosure is a form action

- tex:939-944 already states: shared evidence "confined to two arms of the weight swap
  below, labeled as such; everything else is new, including the 27-cell shipped-row test and
  the matched arm." Sec. 4 labels them: the explicit arm (reproduces companion ratios
  exactly on all 24 cells, tex:1095-1097) and the $(M_q+hD_q+h^2K_q)^{-1}$ arm ("the
  companion's published arm", tex:1086-1087). The chairs cannot be addressed inside an
  anonymous PDF; the disclosure goes in the EasyChair submission form / comments-to-chairs
  field. Deliverable: exact paste-ready text (§6 below) + one optional 6-word precision in
  the paper naming the two arms in the same sentence that says "two arms".

### I. Cor. 3.4 "only if" quantifier — DEFECT REAL (verified independently of both panels)

- tex:813-814: "one sweep is passive at every row direction if and only if
  $0 \preceq W \preceq 2G^{-1}$". At fixed row MAGNITUDE the necessity fails:
  c=2.5, a=0.2, w_r=1, alpha~=0 gives bracket c(c-2)a - w_r = -0.75, dE/E- = -1/3 < 0,
  passive with c outside [0,2]. With magnitude free, necessity holds (scale t J_c until
  t^2 d'(WGW-2W)d > w_r + 2 alpha~). The onset for that cell is
  c* = 1 + sqrt(1 + w_r/a) = 1 + sqrt(6) = 3.4495 — use this, never the reviewer's 4.3317,
  which belongs to R1's different cell (w_r/a = 10.1).
- The corollary's own follow-on (tex:822-823) already prints the exact onset
  "injects once $a > (\Rr + 2\tilde\alpha)/[c(c-2)]$", and $a$ scales with row magnitude
  squared, so ONLY the quantifier wording is wrong.
- Harness confirmed consistent with the corrected quantifier: run_t14_passive_family.py
  block C scales the adversarial row (`s = sqrt(10*(w_r + 2*a_tilde)/quad); J_c *= s`,
  :447-453) and the sufficiency arm draws random magnitudes `* 10**uniform(-1,1)` with
  random w_r. So the validating sentence at tex:830-832 should say "adversarial row", not
  "adversarial row direction".

### J. Mass-only WEIGHT injection count on the warm/two-row cells — CONFIRMED ABSENT; re-run REQUIRED

- Checked the CSV before planning a re-run, as instructed: `t14_warm_multirow.csv` logs, for
  the mass arm, only `false_neg` (index safe AND injects) and `false_pos` per block
  (B_warm_summary 16 rows, D_multirow 16, D_total 4, HEADLINE 1). True positives are never
  tallied, so mass-arm injecting = FN + TP is NOT recoverable from disk; the 4000
  `B_warm_fn` per-cell rows are FN-only (capped). For the matched arm `pred_inj = False`
  makes `false_neg` == injecting, which is exactly the asymmetry R2 flagged: the paper's two
  numbers (2795 index misses / 4099 injections) are different quantities on different
  denominators.
- The grids are fully deterministic (block B linspace/logspace; block D reseeded 20260728
  per arm), so a NEW script reproduces the identical populations and adds the missing
  counter. Runtime is the same order as the original run (~10^5 sweep cells; minutes).

---

## 2. Edits and artifacts, with typeset costs (1 line = 0.00867 body pages)

Order within this section is by item, not priority; §3 gives the execution order.

### A. Figure 3 replacement — 0.0 lines target; float-risky, controlled by construction

New script `benchmarks/paper_eval/t_onesweep/make_rowindex_r8.py` (imports
`fix_rowindex_legend` for `build_figure()`/`repair(fig)` and `make_figs` transitively; edits
neither). Primary route R2, re-canvas:

1. Build the figure via `build_figure()`, apply `repair(fig)` (the existing legend fix),
   then: `fig.suptitle` REMOVED; the 5-line `fig.text` footer REMOVED (kills the stale
   caption, the `rho_matched` string and the `XPBD` leak at the source); middle readout box
   loses its third line (the sufficient-not-necessary annotation) — the printed caption and
   body already carry those counts (caption tex:926-931 says "Panel readouts and cell counts
   are in the text"); right readout drops the `rho_matched` line (undefined symbol; the
   filled markers below zero carry the content); axis label `w_row` replaced by the body's
   $\sum_i a_i$ form or dropped in favor of the printed $\rho_{\mathrm{mid}}$ definition;
   inset moved so nothing overlaps any readout at 300 dpi; in-panel fonts rescaled.
2. Save to a NEW basename `fig_onesweep_rowindex_r8.pdf` with the canvas cut to the aspect
   of the currently CROPPED region (1005.84 x 343.864 equivalent), so at the unchanged
   `width=0.88\textwidth` the rendered height stays 152.3 pt and the float-locked page does
   not move. No trim needed any more.
3. Acceptance gates INSIDE the script (it refuses to install otherwise):
   - pdftotext of the output contains none of: `XPBD`, `rho_matched`, `w_row`,
     `passive only where`, `Shipped XPBD support row`;
   - PyMuPDF span audit at the final printed scale: every in-panel string >= 5.5 pt printed
     (readouts >= 6.0 pt; tick labels >= 4.8 pt) — against the current 1.85-4.63 pt and the
     5.98 pt line numbers;
   - a 300 dpi render of the middle panel shows no glyph overlap and no stray rectangle
     (the red-box artifact is re-checked on the render, whatever drew it);
   - the counts in the readouts equal t4_shipped.csv-derived values (dinner 9/9,
     shelf 2/9, ledge 4/9 passive; 27/27 matched) — DO-NOT-FIX #2 preserved by construction
     since the data path is make_figs' own.
4. .tex edit, same batch: tex:919 becomes
   `\includegraphics[width=0.88\textwidth]{fig_onesweep_rowindex_r8.pdf}` (no trim, no clip).
   Copy the artwork into `paper/figures/`. Caption text unchanged (0 lines). Build; ruler
   must read 5.4983 +- 0.0005 before proceeding.
5. Fallback route R1 (only if the swap moves the ruler > 0.003 and cannot be re-aspected):
   keep the old MediaBox pipeline through `repair()`'s gate, keep suptitle/footer ARTISTS but
   with neutralized text of identical line count and font size, and keep tex:919 unchanged.
   Inferior (a non-printing layer remains, though a harmless one); use only if R2 fails.

Cost: 0.0 body lines. Risk: float-lock; mitigated by aspect-matching + ruler gate.

### B. Table 1 rows T12 + T14a/b/c and the denominator clause — ~4.0 lines total; float growth

1. Table rows after tex:1000 (T11) / around T13, keeping T-number order T12, T13, then T14a-c
   (mirrors the T8a/T8b precedent):
   - `T12 & Hypothesis pinning & analytic & <cells> & $10^{-12}$, sign & 13/13 checks \\`
     — 13 = count of `log.assert` calls in run_t12_hypotheses.py; integrator confirms the
     exact check count and the Cells figure by running the script once (pure numpy) or
     summing `n_cells` over the 38 CSV rows of t12_hypotheses.csv; the header bullet
     (tex:88-109) already carries the block inventory.
   - `T14a & Passive family & analytic & <float>, $720$ & $10^{-9}$; exact & 0 inject in $[0,2]$ \\`
     (float-cell total from t14_passive_family.csv blocks; 720 = block E_rational; the
     criterion split follows T10's precedent).
   - `T14b & Equal cost & shipped & $11{\times}27$ & sign & 17/9/6/2; 0 matched \\`
     (arms from t14_equalcost_summary.csv).
   - `T14c & Warm/two-row & analytic & $43{,}783$ & sign & $2795$ FN; $4099$ inj. \\`
     (Model stays "analytic": same one-sweep simulator, warm-started; the What column plus
     Limitations carry "measured, not proved").
   Overfull check mandatory: the table is `footnotesize` with tabcolsep 3.5pt; if T14c's
   Result overflows, shorten to `2795 FN, 4099` and let Limitations carry the labels.
2. Body cite repairs, zero-line: tex:1124 `(T14)` -> `(T14b)`; tex:1201 `(T14)` -> `(T14c)`;
   tex:830-832 gains `(T14a)` on the 2500-charge sentence (6 chars).
3. Denominator clause, +1 line, inside the Limitations sentence (tex:1201-1205): after
   "still injects on $4099$ of $43{,}898$" add
   `(the two denominators differ because row activity after the sweep depends on the
   weight; both arms scan the same draws)`. This is the verified mechanism (§1.B). Lands in
   the same edit as item J's number (below) so the sentence is rebuilt once, not twice.
4. Header provenance: extend the existing T14 bullets (tex:163-278) with the Table-1 row
   encodings; add a TABLE 1 NUMBERING paragraph edit: the old "there is no T12 row"
   rationale (tex:292-297) is superseded — rewrite that comment block to record the NEW
   mapping (comments cost 0.0000, verified).

Cost: 4 table rows ~= 3.1 body-line equivalents (+0.027) + 1 body line (+0.009) = +0.036.
Float-risky: yes (table float grows); the table sits [t] on its page — verify no float
migration on the build, and check `0 Overfull`.

### C. Supplement completion — 0 body lines; no float risk

New script `benchmarks/paper_eval/t_onesweep/make_supplement_r8.py`:

1. `import make_supplement_full as msf`; append TS rows for `run_t14_passive_family.py`
   (t14_passive_family), `run_t14_equalcost.py` (t14_equalcost, t14_equalcost_summary),
   `run_t14_warm_multirow.py` (t14_warm_multirow), `run_tcost.py` (tcost_shipped,
   tcost_kernels), and item J's new script+CSV; then drive msf's build entry point so the
   README claim/filename map, import shims, clean-copy re-run, anonymity hard gate, and
   SHA256SUMS all regenerate through the existing machinery. (TS signature and the callable
   entry point verified present; integrator confirms exact names at write time.)
2. Completeness gate the script enforces: every CSV named in the .tex header provenance
   block exists in `data/` — this catches the additional gap found this session:
   `x1_passivity` `weight_swap_energy.csv` / `run_weight_swap_energy.py` (source of the
   printed "10, 1 and 0 of 24", tex:1085) must be verified present and added if absent.
3. Rebuild `supplement_onesweep.zip`; verify zero occurrences of home paths, usernames, the
   banned acronym, and `XPBD` outside the legitimate reference title; print final SHA256s.
4. Upload package named for the author: `supplement_onesweep.zip` +
   `benchmarks/paper_fig/out/onesweep_scene_video.mp4` (frozen, sha
   `a9ef4e41...`), total ~15 MB, far under the 200 MB CFP limit.
5. Optional, zero body cost, integrator discretion: a `PROOFS.md` in the supplement with the
   4-6-line derivations of Thm 3.2/3.3, Cor. 3.4, Prop. 3.5 (r7 gap 7). May be skipped
   without harm; do not let it delay the build.

### D. Scope wording — net 0 to +1 line

1. tex:515-517: "Every statement is confined to" -> "Every theorem is confined to"
   (char-negative).
2. tex:588-589: same swap (char-negative).
3. tex:666: "(stated once, binding for every result)" -> "(stated once, binding for every
   formal result)" — the box genuinely binds the five formal results and the panels praised
   it; "formal" excludes the Sec. 4/6 measurements without weakening the box. If the
   paragraph gains a rendered line at build, use "binding for every theorem" instead
   (char-negative, acceptable since Cor./Prop. are covered by the theorems' shared scope
   statement and the body cites the box from each).
4. tex:1197: "scope binds every result" -> "scope binds every theorem" (char-negative).
5. tex:1080-1081: "(hard contact, cold impacts)" -> "(hard contact; the impacts arrive cold
   but the resting support rows are warm and simultaneous, beyond the Section 2 scope)".
   +1 line. This satisfies the "label the scenes beyond-theorem" half of mandatory #2 in
   the body; the frozen video is not re-cut (§5).

Cost: +0 to +1 line (+0.000 to +0.009). Not float-risky.

### E. Theorem precision — ~+4 lines

1. W assumptions, ~0 lines: tex:765-766 "price it at a charge operator $W$" ->
   "price it at a symmetric positive-semidefinite charge operator $W$" (absorbable; if the
   theorem paragraph gains a line, instead put "with $W$ symmetric positive semidefinite"
   into Cor. 3.4's opening "Under the hypotheses of Theorem~\ref{thm:exact}" clause, which
   has more slack). Note Thm 3.3's own identity $W = G^{-1}$ satisfies it trivially; the
   hypothesis matters only for the family, so the corollary is the natural home.
2. Ledger sentence, +2.5 to +3 lines, appended to the accounting paragraph after "the bound
   is the conservative half of the step" (tex:834-838):
   "$E$ is the bodies' ledger: a compliant row also stores
   $\tilde\alpha v^2/(2D^2)$ in its own spring, uncounted in \eqref{eq:hamiltonian}.
   Including it tightens each $2\tilde\alpha$ threshold to $\tilde\alpha$, a band in which
   the displayed ledger is permissive; every hard-contact statement and every shipped
   measurement is unchanged, and the matched charge is passive under either ledger, the
   total change being $-(v^2/2D^2)(\Rr + a + \tilde\alpha)$."
   BINDING: this sentence LABELS; it changes no printed formula (DO-NOT-FIX #4).
3. Abstract $\kappa_r$ qualifier, +1 line: tex:504-507, after "makes one sweep passive for
   any $\kappa \neq 0$ and any number of coupled coordinates" insert ", with the rigid
   velocity read back at $\Delta z/h$," (Thm 3.3's hypothesis; Remark 1 stays the full
   statement). The abstract is column-width; expect one added rendered line.
4. Both-places: no standalone edit; carried by the F recipe (verified already present at
   tex:503-504, :598-599, :766-767).

Cost: ~+3.5 to +4 lines (+0.030 to +0.035). Abstract is on page 1: adding a line there
shifts everything — measure after this batch specifically.

### F. Recipe + c-comparison — ~+6 to +7 lines gross, partly self-funding

1. Rewrite Sec. 6's "Weight choice follows the reconstruction" paragraph (tex:1184-1195)
   into a compact numbered recipe (run-in heading `\rih{Recipe.}` replacing the current
   heading), keeping every existing number and qualifier:
   "(i) Classify the host once: one cold sweep, read back the restorative velocity;
   $\Delta q/h$ is $\kappa = 1$, $2\Delta q/h$ is $\kappa = 2$. (ii) Per row assemble
   $\Rr$, $a_i = U_i^2/m_i$, $b_i = (\omega_i h)^2$, $L = \sum_i a_i b_i$. (iii) Injection
   test before the solve: $\rho_\kappa = [L + (\kappa^2 - 2)\sum_i a_i]/(\Rr + 2\tilde\alpha)
   > 1$ means one mass-only sweep injects ($\rho_{\mathrm{mid}}$ is its $\kappa = 2$
   instance; at $\kappa = 1$ it shares Thm.~\ref{thm:rowvisible}'s threshold). (iv) Remedy:
   charge $W = (\kappa^2 M_c + h^2 K_c)^{-1}$ in both the row denominator and the
   restorative correction, per mode $1/[m_i(\kappa^2 + b_i)]$; changing the denominator
   alone is not the proved method. (v) Diagonal $K_c$: $r$ reciprocals; coupled: $G$ is
   state-independent at fixed $h$, so factor once at load time. (vi) Amplitude: ..."
   with (vi) being the upgraded c-choice sentence below.
2. c-comparison, upgrading the existing sentence (tex:1189-1193) in place:
   "... toward $c = 2$, which returns the converged amplitude exactly (T14a; $c = 1$ rings
   at $0.50$ to $0.60$ of it) at the cost of margin: headroom to the injection threshold
   falls under $1\%$ on a fifth of the cells measured (median $36\%$), against at least
   $100\%$ at $c = 1$ (median $171\%$); and $c = 1$, the centre of the interval, alone
   tolerates a twofold misestimate of $G$ in either direction."
   Provenance bullets (same edit): q_ratio_c1 0.50005-0.5998 and medians 1.7111/0.35555
   <- t14_passive_family.csv blocks F_endpoint and G1_margin; the misestimate clause
   <- (T14-5) mapping, c_eff = c G/G-hat, stated in run_t14_passive_family.py's header.
3. Load-time factorization repair in Sec. 3 (tex:805-809), r7 item 13 (paper understates
   itself): "coupled, it needs one Cholesky of $G$ per substep" -> "coupled, $G$ is
   state-independent at fixed $h$, so one Cholesky at load time (our reference refactors
   per substep) and $2r^2$ flops per row against $2r$, ...". +0.5 line; keeps the measured
   6.8-14.5 attached to what was measured.

Cost: recipe rewrite net +4 lines (the old paragraph is absorbed), c-sentence +2 lines,
Sec. 3 +0.5 line: ~+6.5 lines (+0.056). Not float-risky (prose).

### I. Cor. 3.4 quantifier — 0 lines

1. tex:813-814: "one sweep is passive at every row direction if and only if" ->
   "one sweep is passive for every row $J_c$ if and only if" (char-negative; "every row"
   quantifies direction AND magnitude, which is the verified-true biconditional).
2. tex:830-832: "each met with an adversarial row direction" -> "each met with an
   adversarial row" (the harness scales magnitude; verified at
   run_t14_passive_family.py:447-453).
3. Do not touch the follow-on onset clause (tex:822-823); it is already exact.

### J. Mass-arm warm baseline — new script + 1.5 lines

1. New script `benchmarks/paper_eval/t_onesweep/run_t14_massarm_baseline.py`: imports
   run_t14_warm_multirow as a module; re-runs block B's deterministic grid and block D's
   seeded draws for BOTH weights, counting per arm `n_active` and `n_injecting`
   (dE > 0.0, the same predicate), writing `out/t14_massarm_baseline.csv` plus a gzipped
   full per-cell dump (both weights, ~88k rows) for the supplement.
   HARD self-check before any number is printed: reproduced totals must equal the shipped
   HEADLINE exactly — mass denominator 43,783, matched denominator 43,898, matched
   injecting 4099, mass FN 2795. Any mismatch stops the item (it would mean the population
   is not the same, and the paper sentence may not be written).
2. Paper edit, Limitations sentence (tex:1200-1206), rebuilt ONCE together with item B's
   denominator clause: insert the measured count, e.g. "... the mass-only weight itself
   injects on $N$ of $43{,}783$ of those cells, its index calling $2795$ of them safe,
   ... and the matched charge ... still injects on $4099$ of $43{,}898$ ...". N is whatever
   measures; no outcome gating. Header provenance bullet cites
   t14_massarm_baseline.csv in the same edit.
3. Supplement: the new script + CSVs ride item C's TS row list.

Cost: +1.5 lines (+0.013). Not float-risky.

---

## 3. Priority order and drop list

Execution order for the integrator (most protected first; a later item never preempts an
earlier one's page budget):

1. **B** — Table 1 T12/T14 rows + cite repairs + denominator clause (author-mandated,
   unanimous across six reviewers; MAY NOT BE DROPPED)
2. **A** — Figure 3 replacement (author-mandated; MAY NOT BE DROPPED; zero page cost)
3. **I** — Cor. 3.4 quantifier (verified-true correctness item, zero cost)
4. **D** — scope wording swaps + beyond-theorem clause (mandatory #2)
5. **E** — PSD words, ledger sentence, abstract kappa_r (mandatory #3)
6. **J** — mass-arm baseline script + number (r7's "decisive missing number"; the sentence
   depends on B's rebuilt Limitations sentence, so land together)
7. **C** — supplement completion (mandatory #1; zero body cost, independent of layout)
8. **F** — recipe + c-comparison + load-time factorization (mandatory #4 and
   highest-value #7; largest cost, lands last so the ruler consequences are attributable)
9. **G** — author checklist line only (already satisfied structurally)
10. **H** — chairs' disclosure text (author form action; optional 6-word paper precision)

Ranked drop list, first-to-drop under page pressure (only F and pieces of D/E are
droppable; A and B never):

- F.2's two medians (keep the frac_lt_1pct contrast already printed): saves 1 line.
- D.5's beyond-theorem clause (Limitations already discloses the regime; the caption of
  Fig. 1 already says "not ground truth"): saves 1 line.
- E.3 abstract kappa_r qualifier (body Remark 1 is fully correct; the abstract stays
  merely imprecise, not wrong — drop LAST among these three, it is claim discipline).
- F.1 recipe steps (i)-(ii) can compress into one step if needed: saves 1 line.
- Nothing else is droppable: E.2's ledger sentence and I are correctness-adjacent; J and B
  are the panel's decisive numbers.

## 4. Page-budget arithmetic, plainly

Start: 5.4983 (boundary value; References at exact top of p6c2; ZERO headroom — the first
added line moves the ruler to ~5.507).

Required adds (mid estimates): B +0.036, A +0.000, I +0.000, D +0.009, E +0.033, J +0.013,
F +0.056, C/G/H +0.000. Sum +0.147 -> **5.645 uncompressed**.

That exceeds the 5.50 shipping target and I am saying so explicitly: the pushers are
**F (the panel-mandated implementation recipe and c-comparison, +0.056)**,
**B (the author-mandated Table 1 rows, +0.036)**, and **E (the mandated ledger/precision
sentences, +0.033)**. None is droppable under the run's terms.

Compression budget identified (no hypothesis, qualifier, scope limit, concession or number
may be cut; these are structural savings only):

- "When to couple into the row" paragraph (tex:1174-1182): known compressible, -2 lines.
- System-corroboration paragraph (tex:1075-1097): scaffolding ("We re-run it with a third
  arm", duplicated budget listing), -1.5 lines.
- Accuracy paragraph's First/Second/Third/Fourth connectives (tex:1027-1051), -1 line.
- Related-work paragraph joins (tex:1130-1156), -1 line.
- F.1 absorbs the existing weight-choice paragraph (already netted in F's estimate).

Realistic landing: **5.56 to 5.60** after compression, worst case ~5.65 if the compression
paragraphs resist (they are float-locked; a paragraph must lose a whole line to pay).
**This is above 5.50 and the required content is what pushed it; it is comfortably below
the 6.00 hard limit (headroom >= 0.35 pages at worst case). No items are mutually
exclusive; nothing approaches a 6.00 blocker.** Report the final ruler value and the list
of paid-for lines in the run record.

Measurement protocol per batch: `latexmk -pdf -interaction=nonstopmode onesweep_short.tex`
(60-90 s, no `timeout` prefix), then the column-aware ruler, then greps: 0 Overfull,
0 LaTeX Warning, 0 undefined; pdftotext scans for `XPBD` (must appear exactly once, in
ref [15]'s title), `rho_matched`/`w_row` (zero), em/en dashes (zero outside bib ranges and
the ACM date), the banned acronym (zero), author name/home path/username (zero).

## 5. Not worth doing, with reasons (pushback the run is entitled to)

1. **Compress the bibliography to kill the near-empty page 7** (07-29 polish #11). The CFP
   limit is 4-6 body pages EXCLUDING references; 7 PDF pages is allowed and both panels
   scored the artifact knowing it. Killing p7 needs ~half a column of cuts at a
   float-locked boundary 9 days before the deadline. Risk exceeds benefit. NOT DOING.
2. **Fig. 4 legend occlusion** (r7 item 9; absent from the 07-29 priority list). The
   occluded markers are duplicate ghosts of the y = rho - 1 branch in a decade the caption
   does not cite; the include line carries a measured absolute trim (tex:1103), so an
   artwork swap has the same MediaBox trap as Fig. 3 for cosmetic gain. NOT DOING; recorded
   as known cosmetic.
3. **Any video change** (R1's backward-Euler arm; footer type size; converged/c=2 arm in
   the video). The MP4 hash `a9ef4e41...` is frozen across both panels and the paper's
   review provenance depends on it; re-cutting invalidates that and costs days. The
   beyond-theorem labeling the panel wanted is delivered in the body (D.5). Author may
   re-cut AFTER submission-ready state if time remains; not this run.
4. **The c = {1, 1.5, 2} shipped-host production sweep** (07-29 #7 in its maximal form).
   The author scoped item F to the c=1 vs c=2 comparison from EXISTING CSVs; the r6 plan
   (§8.1) bound the run to "prove the family, name the endpoint, deliver the selection
   criterion, and stop", and §9.8 records the shipped-row c=2 arm as the deliberate open
   item. A new shipped-host arm is new science under deadline. NOT DOING; the analytic
   comparison plus the robustness argument answers the decision the panel actually posed.
5. **R6's stock-engine kappa read-back run** ("run the C3 recipe once on any stock
   engine"). A day of work on a new host, out of scope for a reporting-repair run, and the
   paper's C3 recipe is precisely the instrument it hands the reader. NOT DOING.
6. **Equal-cost re-grading on the two demo scenes** (r7 B.5). Requires scene re-runs; the
   printed cost claim is scoped to the 27-cell grid where it was measured, and D's wording
   pass keeps that scoping honest. NOT DOING.
7. **In-paper proofs for Thm 3.2/3.3/Cor 3.4/Prop 3.5** (r7 gap 7): +0.15-0.20 pages,
   space-prohibitive; at most the optional supplement PROOFS.md (C.5). Body: NOT DOING.
8. **Renumbering T13 or renaming T-labels**: breaks the paper-to-supplement filename map
   (header tex:292-297 records this deliberately). T12 gets a real row instead. NOT DOING.
9. **"Fixing" any DO-NOT-FIX item**: Eq. (6)'s alleged missing `- w_r`; the shelf 2/9 vs
   9/9 "discrepancy"; the "every kappa != 0" quantifier; the Thm 3.2 compliance-term swap
   to `w_m + alpha~`. All four are verified-correct as printed. E.2's ledger sentence is a
   LABEL, not a formula change, and the integrator must diff-check that no `2\tilde\alpha`
   changed anywhere in the paper after the E batch.

## 6. Author-action checklist (outside the .tex, cannot be done by agents)

1. **EasyChair ID**: on assignment, put the number inside `\acmSubmissionID{}` at
   onesweep_short.tex:427 and rebuild. Nothing else changes.
2. **Chairs' disclosure** (item H), paste-ready for the submission form's comments field:
   "This short paper has a companion submission under review at MIG 2026 by the same
   authors (cited in the paper as [3], 'Anonymous 2026, companion paper'). The two share
   exactly one piece of evidence: the explicit (mass-only) and backward-Euler arms of the
   24-cell weight-swap grid in Section 4; our explicit arm reproduces the companion's
   published per-cell ratios exactly, and the companion's published remedy arm is reported
   here with attribution. Everything else (all closed forms, the T-suite, the 27-cell
   shipped-row test, the matched arm, the video) is unique to this paper, and it remains
   independently reviewable if the companion is unavailable."
   Optional 6-word paper precision (integrator, only if a free line exists): at tex:942,
   "two arms of the weight swap below" -> "two arms (mass-only and backward-Euler) of the
   weight swap below".
3. **Upload set**: revised `onesweep_short.pdf`; rebuilt `supplement_onesweep.zip` (with
   T14/tcost/baseline additions, new SHA256SUMS); frozen `onesweep_scene_video.mp4`.
4. Decide on C.5 (supplement PROOFS.md): nice-to-have, zero body cost, skippable.
