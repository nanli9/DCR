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

Pending.

## E-S2 — Iteration-Budget Convergence

Pending.

## E-S3 — Post-Projection Contact Validity

Pending.

