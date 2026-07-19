# MIG 2026 Short Paper — Week 1 Results Ledger

This ledger freezes only measurements generated on the ARM Mac identified below.
No x86 result may be combined with these values. Claim language follows
`docs/mig2026_short_paper_plan.md` §1 and the 2026-07-10/2026-07-18 addenda in
`docs/novelty_positioning.md`.

## Provenance

- Branch: `impulse-native-constraint`
- Week-1 starting/source commit: `b39c5d23a426b47d7534ab1060ac8f3773a8ff12`
- Machine: Apple MacBook Air `Mac16,12`, Apple M4 (10 cores), 16 GB RAM, ARM64
- OS: macOS 15.2 (build 24C2101), Darwin 24.2.0
- Python: 3.12.12 from `.venv/bin/python`
- Measurement policy: one machine only; no x86 values; commands run from the
  repository root; every experimental section records its source commit.

Machine command:

```sh
uname -a
uname -m
sw_vers
system_profiler SPHardwareDataType
.venv/bin/python --version
git rev-parse HEAD
```

## A0 — Evidence and Venue Verification

Source commit: `b39c5d23a426b47d7534ab1060ac8f3773a8ff12`.

### FEM-ground-truth scene count

- Paper-reported count: **3** scenes — slab, ledge, and dinner.
- Branch GT-harness count: **5** scenes — truck, ledge, shelf, dinner, and cargo.
- Interpretation: the paper's accuracy evidence is three scenes. The larger
  five-scene harness is repository coverage and must not be reported as five
  paper-validated scenes.

Generating command:

```sh
rg -n -i 'ground|FEM|slab|ledge|dinner|shelf|cargo|truck|scene' paper/sections/40_results.tex
rg -n 'SCENES|scene|choices|shelf|ledge|cargo|truck|dinner' benchmarks/fem_gt tests/fem_gt
```

Source anchors: `paper/sections/40_results.tex` lines 20–22 and
`benchmarks/fem_gt/run_gt.py` line 32.

### Official MIG 2026 specifications

Verified 2026-07-18 from the official
[MIG 2026 Call for Papers](https://mig.siggraph.org/2026/papers.htm) and
[conference home page](https://mig.siggraph.org/2026/).

- Conference: **11–13 December 2026**, Zucker Graduate Education Center,
  North Charleston, South Carolina, USA.
- Submission window: **25 July–7 August 2026**; deadline **7 August 2026,
  23:59 AoE**.
- Short-paper length: **4–6 pages excluding references**; long papers are at
  most 10 pages excluding references.
- Template: ACM `acmart`, SIGGRAPH `sigconf` formatting. Review command:
  `\documentclass[sigconf, screen, review, anonymous]{acmart}`.
- Review: **double-blind**; the PDF must be anonymous and include the assigned
  paper ID. The official page states there is no rebuttal.
- Supplement/video: supplementary materials such as videos are **strongly
  encouraged**, not stated as mandatory, and may be up to **200 MB**. They are
  reviewer-visible and accompany the final paper in the ACM Digital Library.
  The 2026 CFP specifies no video duration, resolution, codec, or container.
- Submission system: EasyChair conference key `mig2026`.
- Site caveat: the 2026 home page contains two apparent stale-year typos in its
  notification/poster rows; the dedicated CFP gives the internally consistent
  2026 paper dates above.

Verification method:

```text
Open https://mig.siggraph.org/2026/ and follow “Call for Papers” to
https://mig.siggraph.org/2026/papers.htm; inspect Important Dates, Format,
Submission, and Review Process.
```

### Pending item

- Sheth, Lu, Yu, and Fedkiw (2015) full-text inspection: **PENDING — user will
  fetch the PDF**. No novelty conclusion in Week 1 treats this as resolved.

### A0 claim audit

The frozen §1 thesis does not enumerate the GT scene count, so A0 does not
contradict it. Supporting text must say **three reported FEM-GT scenes**, while
separately stating that the branch harness supports five.

## E-S1 — Impulse 24-Cell Matrix

Source commit: `c779b689299c22b7a3900a979e8c2a4995eab12c`.

Generating command:

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_impulse_robustness.py
```

Validation commands:

```sh
.venv/bin/python -m pytest tests/avbd_native/test_solver_impulse.py -q
.venv/bin/python -c '<24-row CSV invariant assertions; see session log>'
```

Configuration ported from benchmark branch `benchmark` at `0b999f4`:

- Scenes: shelf, ledge, dinner.
- Budgets: 4×1, 8×2, 16×4, 32×8 (iterations × substeps).
- Legacy relaxation axis: 0.7 and 1.0.
- Warm-up: 8 frames; measured window: 100 frames; rigid step: 1/120 s.
- Metric: peak total modal mechanical energy / peak incident impactor rigid KE.
- Ledger verdicts: `passive()` for the cumulative net-storage inequality and
  `holds()` for the cumulative positive-gain reservoir inequality.
- Important symmetry qualification: `SolverImpulse` does not consume the
  XPBD/AVBD relaxation axis; it always uses its full implicit modal weight. The
  two axis values are fresh deterministic runs and are exactly identical, so
  this is 24 executions but 12 unique impulse solver settings.

Results below apply independently at **both** legacy-axis values, 0.7 and 1.0:

| scene | budget | peak modal E (J) | incident rigid KE (J) | ratio | net-storage verdict | positive-gain verdict |
|---|---:|---:|---:|---:|:---:|:---:|
| shelf | 4×1 | 7.9179997405 | 28.9510267500 | 0.2734963360 | pass | pass |
| shelf | 8×2 | 13.7070414141 | 28.9510267500 | 0.4734561414 | pass | pass |
| shelf | 16×4 | 13.5832845752 | 28.9510267500 | 0.4691814454 | pass | pass |
| shelf | 32×8 | 15.3851864088 | 28.9510267500 | 0.5314210975 | pass | pass |
| ledge | 4×1 | 11.6066251734 | 384.9444000000 | 0.0301514327 | pass | pass |
| ledge | 8×2 | 43.3569238336 | 384.9444000000 | 0.1126316523 | pass | pass |
| ledge | 16×4 | 68.6718195267 | 384.9444000000 | 0.1783941253 | pass | pass |
| ledge | 32×8 | 55.8431063743 | 384.9444000000 | 0.1450679796 | pass | pass |
| dinner | 4×1 | 3.0348059069 | 24.1258556250 | 0.1257906022 | pass | pass |
| dinner | 8×2 | 4.3998420457 | 24.1258556250 | 0.1823704044 | pass | pass |
| dinner | 16×4 | 3.6201612286 | 24.1258556250 | 0.1500531747 | pass | pass |
| dinner | 32×8 | 4.3726149472 | 24.1258556250 | 0.1812418600 | pass | pass |

Freeze summary:

- Raw energy-ratio cells greater than one: **0/24**.
- Raw net-storage ledger failures: **0/24**.
- Raw positive-gain ledger failures: **0/24**.
- Non-finite cells: **0/24**.
- Governor reruns required: **0/24**; consequently no bounded-rerun number is
  reported and the impulse governor was not activated by this matrix.
- Ratio range: **0.0301514327–0.5314210975**. Per-scene maxima are shelf
  **0.5314210975**, ledge **0.1783941253**, and dinner **0.1823704044**.
- Dedicated impulse tests: **6 passed in 14.40 s**.

Canonical exact per-execution values, including cumulative loss/gain and
maximum ledger slack, are frozen in
`benchmarks/paper_eval/x1_passivity/out/impulse_robustness.csv`; provenance and
the non-consumed relaxation-axis caveat are in the adjacent JSON manifest.

Claim audit: this result supports, and does not contradict, the frozen §1
statement that the implicit sequential-impulse realization remains within the
measured cumulative supply bound in this sweep. It does **not** establish a
universal passivity guarantee for the impulse solver.

## E-S2 — Iteration-Budget Convergence

Pending.

## E-S3 — Post-Projection Contact Validity

Pending.
