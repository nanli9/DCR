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

**The 3-vs-5 discrepancy is not a counting error — it is a vocabulary collision
between the paper and the repo, and resolving it exposes a false sentence in the
current paper text.**

- Paper-reported count: **3** scored GT scenes — slab, ledge, dinner
  (`paper/sections/40_results.tex:20-22`).
- Branch GT-harness count: **5** — `benchmarks/fem_gt/run_gt.py:32`
  `SCENES = ("truck", "ledge", "shelf", "dinner", "cargo")`.
- **The two lists are in different vocabularies.** Confirmed mappings from the
  paper text: paper `road` = repo `truck` (`40_results.tex:23-24`), paper
  `stack` = repo `cargo` (`40_results.tex:91`). In paper words the harness
  covers **road, ledge, shelf, dinner, stack**.
- **`slab` is not in the harness at all.** The slab GT is a standalone script,
  `benchmarks/paper_eval/x3_ground_truth/scene_and_gt.py`, which does **not
  exist on this branch** (only a stale `.pyc`); it lives on `benchmark`.
- Therefore the overlap between "paper GT scenes" and "harness GT scenes" is
  **two** (ledge, dinner). Neither list is a subset of the other. The correct
  statement is *not* "3 of the harness's 5".

**Consequence — a paper sentence is false as written.** `40_results.tex:21-22`
says the stack and shelf are "network-stress and ablation scenes with **no FEM
twin**". Both *do* have genuine unreduced FEM twins, with committed R0/R1/R2
artifacts (`benchmarks/fem_gt/out/{shelf,cargo}_gt{,_r1,_r2}.{csv,json}`,
verified present) and a five-row measured ladder table at
`docs/benchmark_plan.md:100-112` (shelf 7 bodies/351 nodes/28.9 s;
cargo 6/455/33.4 s). **Do not carry this sentence into the short paper.**

**What is defensible.** A GT *arm* exists for five scenes; a scored native-vs-GT
*comparison* (deflection trace + peak-deflection ratio) is what the paper
reports, and that exists for three (slab, ledge, dinner) — on this branch only
ledge (`x3_ground_truth/run_ledge_ladder.py:104`) and dinner
(`benchmarks/dinner_dcr/run_h_ladder.py:79`) are reproducible; slab requires the
`benchmark` branch. The short paper should say **"three scored ground-truth
comparisons"**, and must not claim the other scenes lack FEM twins.

Generating commands:

```sh
sed -n '18,26p;86,92p' paper/sections/40_results.tex   # paper's own wording + road/stack mapping
sed -n '30,34p' benchmarks/fem_gt/run_gt.py            # SCENES tuple
ls benchmarks/fem_gt/out/                              # R0/R1/R2 artifacts for all five
sed -n '96,112p' docs/benchmark_plan.md                # measured five-row ladder
ls benchmarks/paper_eval/x3_ground_truth/              # slab GT absent on this branch
git ls-tree -r --name-only benchmark | grep x3_ground_truth   # slab GT present there
```

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

### E-S1b — the SYMMETRIC three-solver matrix (the plan's actual acceptance test)

The plan's E-S1 acceptance criterion is that *"the three-solver table in the
paper is symmetric (same cells, same metric)"*. The impulse-only run above does
not test that. This run does: **all three backends over the identical 24 cells,
one harness, one metric, one machine.** 72 cells, each run twice (clamp OFF and
ON) = 144 executions.

Generating command:

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_solver_matrix.py
```

Source commit: `e6ab01f` (working tree). Harness:
`benchmarks/paper_eval/x1_passivity/run_solver_matrix.py`; data:
`out/solver_matrix.csv` + manifest. Config re-implemented on this branch from
the `benchmark`-branch X1 harness — no branch merge.

**Harness fidelity, and a metric bug that had to be fixed first.** These scenes
take the *native-thin* step path (`dcr/avbd/world.py:779-793`): with no DCR
coupler attached, `world.step()` returns before `_sync_avbd_to_dcr()`, so the
`dcr_body` mirror is never written and `rigid_kinetic_energy()` on it returns a
permanent **0.0** — which silently turns the metric's denominator into the
`1e-9` floor and inflates every ratio by ~10⁹. The reference X1 matrix was
generated on a branch whose scenes attached a coupler, so the mirror was live
there. The harness now mirrors state explicitly (host-side copy only; nothing in
the thin path reads the mirror, so the solve cannot be perturbed).

Validation that the port is faithful: with the fix, this harness reproduces the
`benchmark`-branch XPBD reference cells **exactly** — shelf 0.7 4×1 6333.22,
shelf 0.7 8×2 53.73, shelf 1.0 4×1 1.0962×10⁴, ledge 0.7 4×1 5.6266×10⁴,
ledge 1.0 4×1 **1.19534×10⁵**, ledge 1.0 8×2 167.7, and the clamped values
1.1969 / 1.0107 / 1.2213 / 1.0673.

#### Results (clamp OFF = un-governed; ratio = peak modal E / peak incident rigid KE)

| solver | cells injecting (ratio > 1) | worst ratio | shelf worst | ledge worst | dinner worst |
|---|---:|---:|---:|---:|---:|
| XPBD | **8 / 24** | **1.19534×10⁵** | 1.09621×10⁴ | 1.19534×10⁵ | 0.372141 |
| AVBD | **2 / 24** | **1.70032** | 0.858702 | 0.262042 | 1.70032 |
| impulse | **0 / 24** | **0.531421** | 0.531421 | 0.178394 | 0.182370 |

With the governor ON, **all 72 cells satisfy the cumulative ledger invariant**
(`holds()`), worst realized ratio 1.22129 (XPBD), 0.871517 (AVBD), 0.531421
(impulse, unchanged — the clamp never fires in any impulse cell).

The XPBD injecting cells are shelf and ledge at the two starved budgets only:

| scene | relax | budget | OFF | ON | substeps clamped |
|---|---:|---:|---:|---:|---:|
| shelf | 0.7 | 4×1 | 6333.2 | 1.1969 | 107/108 |
| shelf | 0.7 | 8×2 | 53.731 | 1.0107 | 162/216 |
| shelf | 1.0 | 4×1 | 1.0962×10⁴ | 1.2213 | 107/108 |
| shelf | 1.0 | 8×2 | 123.66 | 1.0025 | 170/216 |
| ledge | 0.7 | 4×1 | 5.6266×10⁴ | 1.0673 | 98/108 |
| ledge | 0.7 | 8×2 | 47.453 | 1.0151 | 96/216 |
| ledge | 1.0 | 4×1 | **1.19534×10⁵** | 1.0659 | 101/108 |
| ledge | 1.0 | 8×2 | 167.72 | 1.0122 | 98/216 |

Worst cell in absolute terms (ledge, relax 1.0, 4×1): peak modal energy
**4.4356×10⁷ J** against an incident impactor KE of **371.07 J**. Governed, the
same cell realizes cumulative modal gain 425.7718 J against cumulative rigid
loss 425.7718 J — saturated exactly on the η=1 ceiling to round-off.

#### Three caveats that must travel with these numbers

1. **The OFF-run ledger verdict is only real for the impulse backend.** With
   enforcement off, XPBD never updates the accounting (`cum_rigid_loss` and
   `cum_modal_gain` are 0.0 in all 24 cells, so `holds()` is *vacuously* true)
   and AVBD has no ledger object at all (verdict `None`). Only impulse keeps the
   accounting live as a monitor, so only its 24/24 OFF verdict is evidence. Do
   not report "the ledger holds with the clamp off" for XPBD or AVBD.
2. **The relax axis is inert on the impulse backend by construction.**
   `modal_relax`, `_support_block_relax` and `_modal_symplectic` exist on
   `SolverImpulse` but are never read (`solver_impulse.py:290-292` — the
   implicit modal weight `(M + hD + h²K)⁻¹` needs no under-relaxation). Verified
   empirically: **identical to the last digit across relax in every one of the
   12 cell pairs.** So impulse contributes 24 executions but 12 distinct
   configurations. This is the formulation-vs-iteration argument as data, but it
   must be stated, not hidden behind a symmetric-looking table.
3. **"ON" here forces the ACTIVE γ-projection on all three backends**, including
   AVBD, whose production default is monitor-only (`solver_6dof.py:653`). That
   is a measurement-side override for comparability, not a solver change. AVBD's
   clamp fires in up to 353 substeps under this override.

#### Independent cross-validation of the impulse arm

The impulse column was produced here by a completely different denominator code
path from the E-S1 run above (state mirror + `rigid_kinetic_energy` vs direct
solver-array reads + `rigid_mechanical_energy`). They agree:

| cell | this harness | E-S1 harness |
|---|---:|---:|
| shelf 32×8 | 0.531421 | 0.5314210975 |
| ledge 8×2 | 0.112632 | 0.1126316523 |
| ledge 16×4 | 0.178394 | 0.1783941253 |
| dinner 8×2 | 0.182370 | 0.1823704044 |

#### CLAIM IMPACT — two frozen numbers change

- ✅ **"XPBD amplifies modal energy by up to 1.2×10⁵"** — CONFIRMED exactly
  (1.19534×10⁵, ledge relax 1.0 4×1). Keep as written.
- ❌ **"an augmented-Lagrangian (AVBD) … remain[s] within the measured supply
  bound in the same sweep"** — **CONTRADICTED.** AVBD injects in 2 of 24 cells
  (dinner 4×1, ratio 1.1789 at relax 0.7 and 1.7003 at relax 1.0). The governor
  bounds both (0.87152 / 0.86101). The §1 sentence must be rewritten; see the
  claim-update section at the end of this ledger.
- ⚠️ **"XPBD injects in 12/24 cells"** (plan §2 evidence inventory; paper §4
  "12 of 24") — now **8/24** on this branch. The four lost cells are all dinner,
  and the cause is not a solver change: **the dinner scene was materially
  redefined on this branch** (table 1.2×1.0 m / E = 1.0×10¹⁰ Pa / ρ = 500 →
  2.2×1.1 m / E = 1.1×10⁹ Pa / ρ = 770, plus 6 place settings + 4 teacups + 2
  candlesticks instead of 4 settings + 4 candles — the DCR §5.1 duplication,
  `git diff benchmark -- scenes/reduced_dinner_table.py`). The paper's dinner
  worst case of 5.1×10³ describes the **superseded** scene. On the current
  dinner scene XPBD's worst ratio is 0.372 — it does not inject at all.

## E-S2 — Iteration-Budget Convergence

Source commit: `e6ab01f` (working tree). Harness:
`benchmarks/paper_eval/x1_passivity/run_k_convergence.py`; data:
`out/k_convergence.csv`, figure `out/k_convergence.{png,pdf}`.

Generating command:

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_k_convergence.py
```

Scene: **shelf drop** (deterministic single impactor; the plan says avoid
chaotic stacks, and shelf/ledge are the two scenes that reproduce the reference
X1 cells exactly on this machine). **Substeps pinned at 1** so the local
iteration budget `K` is the only variable — this isolates iteration truncation
from substep refinement and is the adversarial corner where truncation
dominates. Clamp OFF throughout. Same metric as E-S1.

| K | XPBD | AVBD | impulse |
|---:|---:|---:|---:|
| 1 | 29586.4 | 0.970996 | — |
| 2 | 13035.9 | 0.607336 | 0.273974 |
| 3 | 9660.10 | 0.614843 | — |
| 4 | 6333.22 | 0.502239 | 0.273496 |
| 6 | 904.183 | 0.493902 | — |
| 8 | 265.711 | 0.450603 | 0.274160 |
| 12 | 54.1496 | 0.393107 | — |
| 16 | 9.57998 | 0.430469 | 0.273751 |
| 24 | 0.486377 | 0.497832 | — |
| 32 | 0.300305 | 0.451712 | 0.273498 |
| 64 | — | — | 0.273506 |
| **500 (oracle)** | — | — | **0.273481** |

**Acceptance: PASS.** XPBD's curve is **monotone non-increasing in K** over the
whole sweep and decays toward the oracle: the gap |XPBD − oracle| shrinks from
**2.95861×10⁴ to 2.68×10⁻²**, six orders of magnitude. XPBD crosses the
injection threshold (ratio = 1) between K = 16 (9.58) and K = 24 (0.486).

The oracle is **impulse at K = 500**, ratio **0.273481** — the same code path as
the impulse sweep points, run to convergence, so it is a converged reference of
the same model rather than a different model.

Supporting reading, and the sharpest single fact in this experiment: **the
impulse backend is already converged at K = 2.** Its ratio moves only in the
fourth decimal across K = 2 → 500 (0.273974 → 0.273481, a spread of 4.9×10⁻⁴),
while XPBD moves by five orders of magnitude over the same budget range. That is
the formulation-vs-iteration dichotomy measured on one scene with one metric.

**Caveat that must travel with the AVBD column.** The denominator (peak incident
impactor KE) is solver- and budget-dependent, and at very low K it is not
comparable across solvers: AVBD's is 13.0 J at K = 1 rising to 28.2 J at K = 32,
i.e. at K = 1 AVBD under-resolves the drop itself. XPBD's denominator is stable
(27.89 J at K = 1, 27.45 J for all K ≥ 2) and impulse's is stable at 28.95 J, so
the XPBD trend and the XPBD-vs-oracle comparison are clean. **Do not read the
AVBD curve as a convergence trend** — it is non-monotone (0.971 → 0.452 with
excursions) and partly denominator-driven.

## E-S3 — Post-Projection Contact Validity

Source commit: `e6ab01f` (working tree). Harness:
`benchmarks/paper_eval/x1_passivity/run_projection_validity.py`; data:
`out/projection_validity.csv`.

Generating command:

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_projection_validity.py
```

The hole this closes: the γ-projection scales realized `(q, q̇)` *after* the
contact solve has finished (`solver_xpbd.py:1244-1250`, the last act of
`_substep_cpu`). Scaling `q` moves the deformed support surface
`y_rest + U_y·q` **without re-solving contact**. A contact reviewer will probe
this. Measurement is by runtime wrappers only — the module-level
`passivity_gamma` (pre-scale), `ledger.commit` (post-scale), and `_substep_cpu`
(substep boundaries); every wrapper returns the original value unchanged.

**Non-perturbation check**: the wrapped runs reproduce E-S1's independent clamp
counts exactly (shelf 8×2: 162/216; shelf 4×1: 107/108; ledge 4×1: 98/108;
ledge 8×2: 96/216). The instrumentation does not change the solve.

XPBD, relax 0.7, starved budgets, 108 logged frames:

| cell | clamped | min γ | (a) gap violation median / worst | (b) next-substep impulse median / worst / steady | (c) λ variance clamped / unclamped | (d) ΔP across projection |
|---|---:|---:|---:|---:|---:|---:|
| shelf 4×1 | 107/108 | 0.00712 | 1.248×10⁻³ / **2.160×10⁻²** m | 0.6629 / 9.452 N·s / — | 4.00×10⁻⁸ / 0 | **0** |
| shelf 8×2 | 162/216 | 0.0884 | 2.993×10⁻⁴ / 6.464×10⁻³ m | 0.2973 / 8.748 / 0.04312 N·s (**6.90×**) | 2.19×10⁻⁹ / 8.45×10⁻¹¹ (26×) | **0** |
| ledge 4×1 | 98/108 | 0.00388 | 6.969×10⁻⁵ / **2.119×10⁻²** m | 0.5331 / 112.4 / 0.5199 N·s (1.03×) | 1.13×10⁻⁷ / 1.06×10⁻⁷ (1.07×) | **0** |
| ledge 8×2 | 96/216 | 0.0369 | 7.027×10⁻⁵ / 4.076×10⁻³ m | 2.310 / 108.1 / 0.2657 N·s (**8.69×**) | 4.03×10⁻⁷ / 6.89×10⁻⁹ (58×) | **0** |

Numbers for the Limitations paragraph (one each, as the plan specifies):

- **(a) Post-projection gap violation**: median **0.07–1.25 mm**, worst case
  **21.6 mm** (shelf 4×1). The projection *increases* the worst violation — the
  pre-scale worst in the same cells is 6.2 mm (shelf 4×1) and 0.51 mm (shelf
  8×2), so the γ-scale accounts for roughly a 3.5× (shelf 4×1) to 12.6× (shelf
  8×2) increase in worst-case penetration. Mechanism: γ < 1 shrinks the sag
  `U_y·q`, lifting the support surface into the resting body. **This is the
  honest cost of enforcing the bound at the state level, and it is the "stable
  but not accurate when the clamp bites" limitation stated plainly.**
- **(b) Corrective normal impulse in the following substep**: median **1.03× to
  8.69×** the unclamped steady-state value; worst single substep **112.4 N·s**
  (ledge 4×1) against a 0.52 N·s steady state. The contact solve does recover —
  the violation is corrected on the next substep rather than accumulating — but
  it pays a visible transient.
- **(c) λ variance (chatter proxy)**: **1.07× to 58×** the unclamped variance on
  clamp-active substeps.
- **(d) Net rigid linear-momentum change across the projection: exactly 0.000**
  in every clamp-active substep of all four cells. This is **zero by
  construction, not by luck** — the projection writes only `_q`/`_qdot` and
  never touches `_V`/`_W` (`solver_xpbd.py:1246-1247`); we verified it
  numerically rather than asserting it. Substep-to-substep momentum change on
  clamp-active substeps (median 0.0031–4.09 kg·m/s) is **at or below** the
  unclamped baseline (0.389–4.08), so the governor does not pump rigid momentum.

The ledger holds and is passive in all four cells.

**Caveat**: in the shelf 4×1 cell the clamp fires on 107 of 108 substeps, so
only one unclamped substep exists and the steady-state reference is undefined
(reported as "—", ratio not computed). The 8×2 cells are the meaningful
ratio measurements; 4×1 is reported for the worst-case gap only.

---

## Claim-text updates required by these numbers (plan §1)

Per plan §4 D5, a surprise updates the claim wording **now**, not in week 3.

**1. The AVBD sentence is wrong as frozen.** Current §1 text: *"…while an
augmented-Lagrangian (AVBD) and an implicit sequential-impulse realization
remain within the measured supply bound in the same sweep."* AVBD injects in
2/24 cells (dinner 4×1: 1.1789 and 1.7003). Proposed replacement, which is both
true and *stronger* for the paper's thesis (it makes the injection ordering a
spectrum rather than a binary, and the governor load-bearing on two solver
classes rather than one):

> Projection-based XPBD amplifies modal energy by up to 1.2×10⁵ relative to
> incident rigid kinetic energy in an adversarial budget sweep; an
> augmented-Lagrangian (AVBD) realization exceeds the supply bound only
> marginally and only in the most starved cells (worst 1.7×), while an implicit
> sequential-impulse realization stays within it in every cell of the same
> sweep.

**2. "12 of 24 cells" must become "8 of 24"** wherever the short paper reports
the XPBD matrix on *this* branch's scenes, with the dinner-scene redefinition
noted — or the sentence must be scoped to the scene set it was measured on. Do
not silently carry 12/24 forward.

**3. The paper's dinner worst case (5.1×10³) may not be cited** alongside
numbers from this branch: it belongs to the superseded dinner scene.

**4. Unaffected and safe to keep**: the 1.2×10⁵ headline (reproduced exactly),
the definition of the ratio as peak modal energy / incident rigid KE, the
adversarial-low-budget framing, the impulse backend as baseline/oracle, and the
K-convergence story (now measured, E-S2).

**5. Newly supportable, within the §1 rules**: the truncation claim is no longer
an assertion — E-S2 measures XPBD decaying monotonically toward the converged
oracle over six orders of magnitude. Per the 2026-07-18 addendum this must still
be phrased as *our quantitative measurement on unilateral contact→modal
transfer*, never as the novel identification of under-convergence injection
(arXiv 2603.16424 states that observation plainly, 2026).

---

## R0 — derived quantities entering `main_short.tex` (2026-07-18)

Plan §6.2. These are **derivations from already-frozen numbers and scene
constants**, not new measurements — no run was performed. Source anchors given
so each is recomputable. Code commit at time of derivation: `753479f`
(`impulse-native-constraint`).

| quantity | value | derivation | anchor |
|---|---|---|---|
| impulse worst ratio (conclusion) | **0.53** | E-S1b impulse column, worst over 24 cells = 0.531421 | this ledger, E-S1b results table |
| AVBD worst ratio | **1.70** | E-S1b AVBD worst = 1.70032 (dinner 4×1, relax 1.0) | same |
| AVBD table-scene pair | **1.18 / 1.70** | dinner 4×1 relax 0.7 = 1.1789, relax 1.0 = 1.7003 | E-S1b claim-impact note |
| XPBD table-scene worst | **0.37** | dinner column worst = 0.372141 (does not inject) | E-S1b results table |
| distinct configurations | **60** | 24 (XPBD) + 24 (AVBD) + 12 (impulse: relax axis inert, 12 bit-identical pairs) | E-S1b caveat 2 |
| shelf board thickness | **0.03 m** | `support_thickness` default | `scenes/reduced_shelf.py:35` |
| shelf board span | **0.8 m** | `support_length` default | `scenes/reduced_shelf.py:33` |
| 21.6 mm as % thickness | **72%** | 0.0216 / 0.03 | E-S3 (a) + the two rows above |
| 21.6 mm as % span | **2.7%** | 0.0216 / 0.8 | same |
| road/truck slab | **2.5 × 1.5 m** | scene docstring + support defaults | `scenes/reduced_truck.py:1-30` |
| device hardware | **NVIDIA RTX 4090** (warp 1.15) | device timing arm | `paper/NUMBERS.md` §4.7 device |

### R0 items deferred (not text-only)

- **R0.10 static-sag normalization.** Plan §6.2 item 10 asks for 21.6 mm
  normalized by slab geometry *and* by "the unclamped static sag of the same
  cell". The geometry half is done above. **The static-sag half is not frozen
  anywhere** and requires an instrumented run, so it is out of R0's text-only
  scope; plan §6.7 already assigns the normalized-penetration presentation to
  **R5**. Deferred there deliberately, not dropped.

### R0 acceptance

- Grep audit over `main_short.tex` clean: zero hits for "supply bound",
  "injection threshold", "contact reviewer", "truck"; "72"/"M4"/"orders of
  magnitude" all scoped as intended.
- `latexmk -pdf main_short.tex` → 5 pages, 0 undefined references, 0 LaTeX
  warnings, worst overfull 1.98 pt.
- `paper/NUMBERS.md` cross-check: no conflict (that file indexes the *long*
  paper's §4.x; short-paper numbers are frozen in this file).

---

## R1 — Eq.-(2) utilization with the governor OFF (2026-07-19)

Plan §6.3, the load-bearing fix. Closes E-S1b caveat 1: with the clamp OFF the
Eq.-(2) accounting previously existed only on the impulse backend (XPBD's was
vacuous, AVBD had no ledger object), so the abstract's "AVBD exceeds the supply
bound (1.7×)" had **no supporting measurement** — 1.7 was R.

Harness: `benchmarks/paper_eval/x1_passivity/run_eq2_utilization.py`
Data: `out/eq2_utilization.csv`; figure `benchmarks/paper_fig/fig_s1_solver_matrix.py`
Machine: Apple M4, CPU only, CPython 3.12. Commit `250b45d` + working tree.

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_eq2_utilization.py --check-frozen
```

### Method — measurement-only by CONSTRUCTION

The plan proposed replicating the ΔE_rig formula offline. We do **not**: a
replica can drift from the real formula silently. Instead the solver's OWN
ledger runs live (`_enforce_modal_passivity = True`) while its actuator is
neutered — the module-level `passivity_gamma` is forced to return 1.0. In all
three backends every state write in the ledger block sits inside
`if gamma < 1.0` (`solver_xpbd.py:1244`, `solver_6dof.py:2639`,
`solver_impulse.py:1003`), so that branch is DEAD and the trajectory is
bit-identical to a clamp-OFF run. `passivity_gamma` is imported
function-locally in all three, so one module patch reaches them all.

**AVBD needs its ledger pre-constructed.** It builds `PassivityLedger` lazily on
the first substep (`solver_6dof.py:2449`, `:3057`), unlike XPBD which builds it
at `set_modal_support`. A harness reading `sol._psv_ledger` at setup finds
`None` and silently measures nothing — this is the whole of E-S1b caveat 1's
"AVBD has no ledger object at all". The lazy init is guarded
`if self._psv_ledger is None`, so pre-constructing the same object with the
same η makes the solver adopt it. **Anyone re-deriving these numbers must do
this.**

### Verdict definition — the printed inequality, not the enforced one

**These are two different inequalities and they disagree.** Reported here:

    margin_J = max_n [ E_mod^n − E_mod^0 − η·Σ_{k≤n} max(ΔE_rig^k, 0) ]
    violation ⟺ margin_J > 0                       (Eq. 2 EXACTLY AS PRINTED)

The implementation's own `passive()` (`passivity.py:287-293`) instead forgives
up to one substep's largest deposit, `max_net_excess ≤ max_deposit + tol`,
because modal PE can spike in the same substep the rigid body is still
delivering KE. **That allowance is worth 7–389 J in these scenes**, so:

| reading | XPBD | AVBD | impulse |
|---|---:|---:|---:|
| Eq. (2) as printed (strict) | 8/24 | **23/24** | 0/24 |
| implementation `passive()` (allowance) | 8/24 | **1/24** | 0/24 |
| implementation `holds()` (gross-gain form) | 9/24 | 2/24 | 0/24 |

The strict reading is reported (user decision 2026-07-19) because it is what
the paper prints AND because the **governed** runs satisfy it too — worst
`max_net_excess_on` is +1.14×10⁻¹³ J (XPBD), +2.43×10⁻¹⁷ (AVBD), −5.7×10⁻⁴
(impulse), from the committed `solver_matrix.csv`. So both columns are
adjudicated by one inequality. **R2 must document the discrepancy in-paper.**

Cell counts alone mislead in the opposite direction, so the joules always
travel with them: XPBD overdraws by up to 4.4×10⁷ J, AVBD by ≤ 15.08 J.

### Results (governor OFF, η = 1)

| solver | Eq.(2) violated | margin range [J] | worst R | return channel |
|---|---:|---:|---:|---:|
| XPBD | **8/24** | −0.0398 … **+4.436×10⁷** | 1.19534×10⁵ | 3.39–32.15% |
| AVBD | **23/24** | −0.00205 … **+15.083** | 1.70032 | 101.99–118.17% |
| impulse | **0/24** | −0.1806 … −5.743×10⁻⁴ | 0.531421 | 0.41–27.09% |

XPBD's violating cells (identical to its R > 1 set):

| scene | relax | budget | R | margin [J] | supply [J] |
|---|---:|---:|---:|---:|---:|
| shelf | 0.7 | 4×1 | 6333.22 | +1.738×10⁵ | 38.06 |
| shelf | 0.7 | 8×2 | 53.7307 | +1823.91 | 39.76 |
| shelf | 1.0 | 4×1 | 10962.1 | +3.008×10⁵ | 39.94 |
| shelf | 1.0 | 8×2 | 123.656 | +3549.07 | 40.94 |
| ledge | 0.7 | 4×1 | 56266.2 | +2.0817×10⁷ | 422.67 |
| ledge | 0.7 | 8×2 | 47.453 | +1.941×10⁵ | 406.26 |
| ledge | 1.0 | 4×1 | 119534 | **+4.4355×10⁷** | 454.92 |
| ledge | 1.0 | 8×2 | 167.723 | +4.0546×10⁵ | 414.33 |

AVBD: violates in 23/24, but every margin except two is ≤ 0.14 J. The two real
ones are the table-scene starved cells that R also flagged:
dinner 0.7 4×1 (R 1.17891, margin **+5.353 J**) and
dinner 1.0 4×1 (R 1.70032, margin **+15.083 J**). Its single satisfying cell
is shelf 0.7 4×1 (margin −0.00205 J).

### THE TWO METRICS DIVERGE — this is the panel's blocker, demonstrated

R and Eq. (2) agree on XPBD (8/24 both) and impulse (0/24 both). On AVBD they
do not: **R flags 2 cells, Eq. (2) is violated in 23.** R is a severity
diagnostic and understates pervasiveness; the invariant is the claim. Reported
as measured, not argued.

### Acceptance — all three checks pass

1. **Non-perturbation**: all 8 frozen E-S1b XPBD cells and all 3 per-solver
   worst-over-cells values reproduce EXACTLY (`--check-frozen`).
2. **Impulse cross-validation**: `cum_rigid_loss` vs E-S1b's live OFF-run
   monitor over 24 cells — **worst relative difference 0.00e+00** (bit-exact,
   not merely round-off, because it is the same accounting, not a replica).
3. **Bracket contiguity** (`probe_dErig_bracket.py`): E_rig_post^k ==
   E_rig_pre^{k+1} with sum|gap| = **0 J exactly** on all three backends, so
   the per-substep ΔE_rig brackets tile the timeline and no rigid energy change
   escapes the accounting.

### Return channel (feeds R2)

Σ max(−ΔE_rig, 0) / Σ max(+ΔE_rig, 0), the bound on gross-sum recycling:
XPBD 3.39–32.15%, impulse 0.41–27.09%, **AVBD 101.99–118.17%**. Plan §6.4
expected "≲1%"; it is one to two orders of magnitude larger, and on AVBD the
gross rigid *gain* exceeds the gross loss in every cell. The Limitations
recycling caveat must stand on these numbers, and the AVBD >100% needs its own
sentence (same family as the impulse box–box rectification already named).

### A metric that was WRONG and is retracted

The first implementation used the plan's literal formula with a RUNNING
denominator, maximised over n. That denominator accumulates from ~0, so a
sub-joule in-transit lead inflated without bound: it reported "AVBD violates in
23/24 with U up to 22" for overdrafts of 0.01–0.15 J (AVBD shelf 0.7 32×8: raw
U = 20.3 for 0.13 J). Caught because a cell reported U = 21.9 while its peak
modal energy, 4.98 J, was five times SMALLER than its supply, 25.3 J. The
count 23/24 later turned out to be right for an unrelated reason (the strict
reading), but the U values were not. **A ratio whose denominator accumulates
from zero is not a verdict — check the absolute joules first.**

---

## R2 — the ledger pinned down in-paper (2026-07-19)

Plan §6.4. No new runs: this item states in the paper what the code already
does, so every quantity in Eq. (2) is recomputable by a reader. The measured
half (the return channel) comes from the R1 run above. Commit `73c95c5`.

### Code anchors for every term now stated in §2

| paper term | code | anchor |
|---|---|---|
| $E_{\mathrm{mod}} = \frac12\dot q^\top M_q\dot q + \frac12 q^\top K_q q$ | `modal_mech_energy(qdot,q,Mq,Kq)` | `dcr/avbd/_solver/passivity.py:183-191` |
| $E_{\mathrm{mod}}^0 = 0$ | `PassivityLedger.e_modal_0` default `0.0`; **no solver ever assigns it** (grep-verified), and scenes start undeformed and at rest, so it stays 0 on every CPU number in this paper | `passivity.py:249` |
| $E_{\mathrm{rig}}$ = purely kinetic, translational + rotational, ALL dynamic bodies | `rigid_mechanical_energy(V,W,Q,mass,invIl)` called **without** `X`/`gravity`, so the gravitational-PE branch is not taken; `m<=0` (static) skipped; $\omega_{\mathrm{local}}=R^\top\omega$ | `passivity.py:91-145`; call sites `solver_xpbd.py:1072`, `:1223`, `solver_6dof.py:2617`, `solver_impulse.py:987` |
| $W_g^k=\sum_b m_b\,g\cdot(x_b^{k,+}-x_b^{k,-})$ | explicit loop over dynamic bodies | `solver_xpbd.py:1231-1236`, `solver_6dof.py:2621-2626`, `solver_impulse.py:990-995` |
| $\Delta E_{\mathrm{rig}}^k=(E^{k,-}-E^{k,+})+W_g^k$ | `rigid_loss = (E_rig_pre - E_rig_post) + grav_work` | `solver_xpbd.py:1237`, `solver_6dof.py:2627`, `solver_impulse.py:996` |
| reservoir credit $B \mathrel{+}= \eta\max(\Delta E_{\mathrm{rig}},0)$ | `PassivityLedger.deposit()` | `passivity.py:257-263` |
| reservoir debit $B \leftarrow \max(B-\max(\Delta E_{\mathrm{mod}},0),0)$ | `PassivityLedger.commit()` | `passivity.py:265-285` |
| $\gamma=\min\bigl(1,\sqrt{(E_{\mathrm{mod}}^-+B)/E_{\mathrm{mod}}^+}\bigr)$ | `passivity_gamma()`; quadratic in $\gamma$ because BOTH terms of $E_{\mathrm{mod}}$ are quadratic, so it bounds KE *and* PE (unlike the velocity-only `passivity_alpha`, retained only for a unit test) | `passivity.py:211-230`; alpha at `:194-208` |
| $\eta = 1$ in every experiment | `apply_passivity(..., eta=1.0)` | `benchmarks/paper_eval/paper_config.py:85-97` |
| endpoints tile the timeline | measured, not assumed: `sum|E_post^k - E_pre^{k+1}| = 0 J` exactly on all three backends | `probe_dErig_bracket.py` (R1) |

### CAVEAT on $E_{\mathrm{mod}}^0$ — two harnesses use a DIFFERENT baseline

`e_modal_0` is never written by solver code, but **two device-arm benchmark
harnesses rebase it** to the modal energy measured after the first step:
`benchmarks/paper_eval/x5_perf/probe_device_passivity.py:97` and
`x5_perf/run_stress_device.py:136`. That is a different convention from the
$E_{\mathrm{mod}}^0=0$ the paper states: it excludes the settling transient from
the numerator instead of funding it.

- **No CPU number in this paper is affected.** R1, E-S1/E-S1b and E-S3 all leave
  the default in place, so their $E_{\mathrm{mod}}^0$ is genuinely 0.
- **The device-path passivity claims ARE on the rebased convention** — the
  `paper/NUMBERS.md` §4.7 "device path passive in 20/20 cells" and §4.8
  "18/18 passive" rows come from those two harnesses. They are *more* lenient
  than the paper's stated baseline, so they must not be quoted as evidence for
  Eq. (2) as printed without saying so. The short paper does not currently make
  that claim (§3.5 says the device path carries the ledger read-only as a
  monitor, and claims no verdict), so nothing needs changing today — but this
  is a trap for the long paper.

### The printed inequality is NOT the enforced one — now disclosed in §2

| | test | code |
|---|---|---|
| **as printed / as reported** | $\max_n[E_{\mathrm{mod}}^n-E_{\mathrm{mod}}^0-\eta\sum_{k\le n}\max(\Delta E_{\mathrm{rig}},0)]>0$ | (R1 `margin_J`) |
| implementation `passive()` | same, but forgiven up to `max_deposit` = one substep's largest deposit | `passivity.py:287-293` |
| implementation `holds()` | gross-gain form: $\sum\max(\Delta E_{\mathrm{mod}},0)\le\eta\sum\max(\Delta E_{\mathrm{rig}},0)$ | `passivity.py:295-297` |

The allowance is worth **7–389 J** in these scenes and is the entire difference
between AVBD 23/24 and 1/24. §2 now states this, states that the stricter
reading is used for BOTH columns, and gives the governed worst margin
(1.1×10⁻¹³ J) that makes doing so possible.

### Recycling caveat — the measured bound (Limitations)

$\sum_k\max(-\Delta E_{\mathrm{rig}}^k,0)\,/\,\sum_k\max(+\Delta E_{\mathrm{rig}}^k,0)$,
from the R1 instrumented runs (`eq2_utilization.csv : return_frac`):

| solver | range | reading |
|---|---:|---|
| impulse | 0.41–27.09% | |
| XPBD | 3.39–32.15% | |
| AVBD | **101.99–118.17%** | gross rigid GAIN exceeds gross loss in every cell |

Plan §6.4 expected ≲1%. It is one to two orders larger, so the caveat now
stands on data. The AVBD >100% is called out separately in Limitations as the
same phenomenon as the impulse box–box rectification (rigid-side energy
creation, which the scalar reservoir is blind to by design), not as a property
of the bound.

### Acceptance

- **Recomputable from the paper alone**: §2 now gives $E_{\mathrm{mod}}$,
  $E_{\mathrm{mod}}^0=0$, the exact $\Delta E_{\mathrm{rig}}$ with its gravity-work
  term and the pure-KE endpoint definition, the reservoir credit/debit rules,
  the closed-form $\gamma$, and $\eta=1$. Checked term-by-term against the
  anchor table above.
- **Guarantee named**: "cumulative, gross-loss-funded storage ceiling on the
  modal subsystem"; explicitly NOT contact-port passivity and NOT a signed
  per-interface transfer bound.
- **"source-referenced" now appears exactly once**, adjacent to its definition
  (was 3 loose uses in abstract / contribution 2 / conclusion, all replaced with
  "funded by measured contact dissipation").
- **Limitations carries the recycling caveat with a measured bound attached.**
- Builds clean: 5 pages, 0 undefined refs, 0 LaTeX warnings.

---

## R3 — making the comparison controlled (2026-07-19)

Plan §6.5. Answers the panel's "apples-to-apples" blocker. Machine: Apple M4,
CPU only, CPython 3.12. Commit `29ed217` + working tree.

### R3.1 — T2 solver/parameter table (paper Table 1)

Every entry read from the implementation. Anchors:

| table row | code |
|---|---|
| unknown solved for | position (`solver_xpbd._substep_cpu`), position+multiplier (`solver_6dof`), velocity (`solver_impulse._substep`) |
| XPBD compliant projection $\tilde\alpha=\alpha/h^2$, $\alpha=0$ ⇒ rigid | `solver_xpbd.py:243` (`contact_compliance=0.0` default), `:1137-1138` |
| AVBD penalty + dual update, $\alpha=0.99$, $\beta=10^5$ | `solver_6dof.py:188-189`, `:289-290` |
| impulse Schur $A=\frac{\mathrm{cfm}}{h^2}I+JM^{-1}J^\top+\hat G W\hat G^\top$ | `solver_impulse.py:22` (module docstring), PGS at `:892-912` |
| impulse implicit modal weight $W=(M+hD+h^2K)^{-1}$ | `solver_impulse.py:30-38`, `:781-783` |
| XPBD per-mode elastic compliance $1/(H_{ii}h^2-1)$ | `solver_xpbd.py:1113-1114` (`_alpha_e`) |
| iteration structure | XPBD GS sweeps w/ gap re-evaluation `solver_xpbd.py:1130-1136`; AVBD coloured primal GS + q-block; impulse PGS `solver_impulse.py:902` |
| warm start: XPBD NONE ($\lambda\leftarrow0$/substep) | `solver_xpbd.py:1119-1120` (`sc.lam = 0.0`, `_lam_q` zeroed) |
| warm start: impulse $\lambda$ cache keyed per row | `solver_impulse.py:278`, `:893-894`, `:911-912` |
| warm start: AVBD $\lambda$ + penalty carried | `solver_6dof.py:297`, `:1478-1486`, `:2001` |
| relaxation 0.7 both; **inert on impulse** | `paper_config.py:45` (`relax=0.7`); `solver_impulse.py:290-292` (`modal_relax=1.0`, never read) |
| $h=1/120$, substep $h/S$ | `paper_config.py` `h`; `solver_xpbd.py:563-564` |
| modal rank $r$ = 24 / 28 / 24 | `reduced_shelf.py:40-41` (10+14), `reduced_ledge.py:42-43` (12+16), `reduced_dinner_table.py:87-88` (10+14) |
| Rayleigh $D=\alpha_0M+\alpha_1K$, $\alpha_0\in\{2,3\}$, $\alpha_1=10^{-5}$ | `reduced_shelf.py:46-47` ($\alpha_0{=}3$), `reduced_ledge.py:48-49` / `reduced_dinner_table.py:95-96` ($\alpha_0{=}2$) |
| implicit-midpoint stepper; $\eta=1$ | `paper_config.py:45` `stepper="symplectic"`; `apply_passivity(eta=1.0)` |

### R3.2 — row-evaluation accounting

A cell costs $K\cdot S$ row evaluations per frame: 4, 16, 64, 256 across the
budget axis. So each rung **quadruples** the work and the axis spans **×64**
end to end — steeper than the $4{\times}1\to32{\times}8$ labelling suggests.
(Plan §6.5 called it "a ×4 work ladder"; ×4 is the per-rung factor, ×64 the
span. The paper now states the four counts explicitly to avoid the ambiguity.)

### R3.3 — substep-only sweep (NEW RUN)

Companion to E-S2, which pins $S=1$ and sweeps $K$. Here $K=4$ is pinned and
$S\in\{1,2,4,8\}$ swept, shelf drop, all three hosts, both relaxations,
governor OFF.

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_eq2_utilization.py \
    --scenes shelf --budgets 4x1,4x2,4x4,4x8 --relaxes 0.7,1.0 --out substep_sweep
```
Data: `benchmarks/paper_eval/x1_passivity/out/substep_sweep.csv`

XPBD, relax 0.7 (R / Eq.-(2) margin J):

| S | 1 | 2 | 4 | 8 |
|---|---:|---:|---:|---:|
| R | 6333 | 213.9 | 68.05 | **3.129** |
| margin [J] | +1.738×10⁵ | +1.429×10⁴ | +1944 | **+480.9** |

relax 1.0: R = 1.096×10⁴ / 1431 / 244.7 / **29.19**; margin +3.008×10⁵ /
+4.139×10⁴ / +7059 / **+813**.
AVBD violates 7/8 (worst margin +0.0225 J); impulse 0/8 (worst −5.7×10⁻⁴ J).

**THE EQUAL-WORK RESULT** — same scene (shelf), same relax (0.7), same machine,
same governor state as E-S2, so the two ladders overlay exactly:

| row-evals/frame | as iterations ($S{=}1$, E-S2) | as substeps ($K{=}4$, this run) |
|---:|---:|---:|
| 4 | K=4: R = 6333 | S=1: R = 6333 (same cell) |
| 8 | K=8: R = **265.7** | S=2: R = **213.9** |
| 16 | K=16: R = **9.58** | S=4: R = **68.05** |
| 32 | K=32: R = **0.300**, Eq.(2) HOLDS | S=8: R = **3.13**, margin **+481 J** |

Iterations and substeps are NOT interchangeable at equal work. The ordering is
not uniform — at 8 row-evals substeps are marginally ahead — but iterations pull
away as the budget grows, and **within this ladder only the iteration axis
reaches the regime where Eq. (2) holds.** Stated in the paper as "Equal work,
unequal outcome"; honest about the non-uniform ordering rather than claiming a
clean sweep.

### R3.4 — complementarity residual vs K (NEW RUN)

`res = ‖min(C, λ)‖∞` over support rows at end of substep. Harness
`benchmarks/paper_eval/x1_passivity/probe_complementarity_residual.py`
(measurement-only: wraps `_substep_cpu`, returns unchanged; `passivity_gamma`
forced to 1.0). Same scene/relax/substeps as E-S2 so the curves overlay.

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/probe_complementarity_residual.py
```
Data: `out/complementarity_residual.csv`

| K | 1 | 2 | 4 | 8 | 16 | 24 | 32 | 64 | 128 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| max | 2.79×10⁻² | 1.51×10⁻² | 6.16×10⁻³ | 1.85×10⁻³ | 1.59×10⁻⁴ | 2.99×10⁻⁵ | 1.07×10⁻⁵ | 3.559×10⁻⁶ | 3.559×10⁻⁶ |
| median | 9.22×10⁻⁴ | 3.95×10⁻⁴ | 2.65×10⁻⁴ | 1.33×10⁻⁴ | 1.52×10⁻⁵ | 2.26×10⁻⁶ | 3.57×10⁻⁷ | 1.068×10⁻⁷ | 1.068×10⁻⁷ |

Monotone, falls **7850×** over K=1..128, and **bottoms out by K=64** (K=128
agrees to 7 significant figures — the floor is the solve, not the budget).

**Why this matters**: it closes the "one scalar could shrink by coincidence"
objection. The E-S2 energy crossing at K≈24 coincides with the residual passing
~3×10⁻⁵, so the amplification disappears exactly as the complementarity
conditions begin to hold. The energy decay IS constraint convergence.

**Scope, stated in the paper**: XPBD only. AVBD's AL multiplier is not the same
object, and the impulse host is converged at K=2 (E-S2), so its curve is flat by
construction. Reporting one number per host would be the apples-to-oranges
comparison R3 exists to remove.

### Cross-platform test-suite check (not a paper number)

User-requested. Full `pytest tests/` on both the ARM M4 and the x86 pod, for
correctness only — **no solver-behaviour number may come from the x86 host**
(plan hard rule; chaotic contact stacks diverge between architectures under
floating-point reassociation, as the paper states). `tests/avbd/
test_adapter_smoke.py::test_box_falls_and_settles` fails on BOTH machines
(box never leaves y=0.5), so it is a pre-existing failure, not an x86 artifact
and not caused by this session — which touched no solver source.

---

## R4 — XPBD self-convergence to K=500 + state agreement (2026-07-19)

Plan §6.6. **THE ACCEPTANCE CRITERION IS NOT MET, and the negative result is
the finding.** Machine: Apple M4, CPU only. Commit `14983e0` + working tree.

Harness: `benchmarks/paper_eval/x1_passivity/run_selfconvergence.py` (NEW).
Data: `out/selfconvergence.csv` (100 frames), `out/selfconvergence_long.csv`
(300 frames, robustness check), `out/selfconvergence_traces.npz`.
Same scene/relax/substeps as E-S2 (shelf, 0.7, S=1) so the column overlays it.

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_selfconvergence.py
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_selfconvergence.py \
    --nframes 300 --out selfconvergence_long          # robustness
```

### Energy: XPBD self-converges, but NOT to the oracle

Oracle = implicit sequential-impulse host at K=500: **ratio 0.2734809**.

| K | 16 | 24 | 32 | 64 | 128 | 256 | 500 |
|---|---:|---:|---:|---:|---:|---:|---:|
| XPBD ratio | 9.579983 | 0.4863771 | 0.3003054 | 0.2999081 | 0.2996861 | 0.2996276 | **0.2996131** |
| gap to oracle | 9.307 | 0.2129 | 0.02682 | 0.02643 | 0.02621 | 0.02615 | **0.02613** |

**Plan §6.6 acceptance was "|XPBD(500) − oracle| ≪ the K=32 gap (2.7×10⁻²)".
Measured improvement: 1.026×.** The gap is a FIXED POINT, not a tail — XPBD
plateaus by K≈64 at 0.2996, which differs from the oracle by 9.6% relative.

### State: peak agrees, trajectory does not

Deflection trajectory `d_i(t) = U_y[i]·q(t)` [m] — the same expression the
contact row uses, so it is the surface the coupling actually sees.

| metric | XPBD K=500 vs oracle |
|---|---|
| peak deflection | 0.0204817 m vs 0.0200003 m = **1.0241×** (2.4% high) |
| L∞ of trace difference | **6.804×10⁻³ m = 34.02% of the oracle's peak** |
| both flat from K=32 | peak 1.0248→1.0241, L∞ 34.00%→34.02% |

So amplitudes agree to 2.4% while the trajectories differ by a third of peak —
i.e. the disagreement is in phase/shape, not scale.

### Ring frequency: NOT REPORTED, measurement unreliable

The dominant FFT peak of the deflection trace moved with window length
(XPBD 15.6 Hz at 100 frames → 11.2 Hz at 300; oracle 6 Hz in both). Over these
windows the trace is dominated by the quasi-static sag, not the elastic ring,
so the dominant peak is the settling envelope. **Do not quote these numbers.**
The resolved ring comparison is the full-FEM one already in the paper
(78.0 vs 78.3 Hz, §3.4), from a purpose-built harness. Energy, peak and L∞ are
stable to 4 s.f. across BOTH window lengths, so those are the reportable ones.

### Interpretation (now in paper §3.2)

The two hosts converge to **different discrete solutions**. That is expected
rather than alarming: they discretize the same continuous law differently — the
paper's own §1 says the position-level row is one linearization step from the
velocity-level law and takes e=0. The consequence for the paper's argument is
that the sweep separates two effects that are easy to conflate:

1. a **truncation pathology** (ratio 2.96×10⁴ → 0.2996) that convergence removes;
2. a **formulation difference** (residual 9.6% energy, 34%-of-peak trajectory)
   that convergence does NOT remove.

The §3.2 wording changed from "cured by convergence" to "largely cured by
convergence ... removes the pathology outright", and a new paragraph
"Self-convergence stops short of the reference" states the plateau and the
state metrics explicitly. This is more defensible than the original claim: a
reviewer running K=500 themselves would have found the plateau.

---

## R5 — usefulness of the governed result (2026-07-19)

Plan §6.7. Machine: Apple M4, CPU only, CPython 3.12. Commit `b639c16` +
working tree.

Harnesses (both NEW):
- `benchmarks/paper_eval/x1_passivity/run_governed_accuracy.py` (R5.1 + R5.4)
- `benchmarks/paper_eval/x1_passivity/run_projection_validity_avbd.py` (R5.2)

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_governed_accuracy.py
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_projection_validity_avbd.py
```
Data: `out/governed_accuracy.csv`, `out/governed_accuracy_traces.npz`,
`out/projection_validity_avbd.csv`.

### R5.1 — accuracy at the shelf 8×2, relax 0.7 cell

Four arms on one axis. Reference arms are measurement-only (`passivity_gamma`
forced to 1.0, so the enforcement branch is dead); the governed arm is the arm
under test, with `_psv_monitor_only=False` so the projection is ACTIVE.

| arm | budget | ratio | E_mod peak [J] | peak \|d\| [mm] | resting sag [mm] |
|---|---|---:|---:|---:|---:|
| ungoverned | xpbd 8×2 | 53.7307066 | 1555.6 | 24.116 | 1.403 |
| governed | xpbd 8×2 | 1.01067586 | 29.26 | 5.929 | 0.453 |
| xpbd converged | xpbd 500×1 | 0.2996131 | 8.2236 | 20.482 | 1.714 |
| oracle | impulse 500×1 | 0.2734809 | 7.9176 | 20.000 | 2.377 |

**The plan's arithmetic SURVIVES, and it survives under both references.** R4
made "the reference" ambiguous (the position-based host self-converges to
0.2996, not the oracle's 0.2735), so both are reported:

| reference | energy error ungoverned → governed | in joules |
|---|---|---|
| oracle (0.2734809) | **196.5× → 3.696×** | +1548 J → +21.34 J |
| xpbd converged (0.2996131) | **189.2× → 3.558×** | +1547 J → +21.04 J |

Plan §6.7 predicted "~200× → ~3.7×" from 53.7/0.2735 and 1.011/0.2735. Verified:
196.5 and 3.696. The choice of reference moves the numbers by <5%, so the claim
does not rest on it. **Paper reports the oracle-referenced pair and names the
other.**

### R5.1b — THE GOVERNOR MAKES THE TRAJECTORY WORSE, NOT BETTER

Not anticipated by the plan, and it is the sharpest result of R5.

| reference | deflection L∞ ungoverned → governed |
|---|---|
| oracle | 6.505 mm (32.5% of ref peak) → **14.28 mm (71.4%)** |
| xpbd converged | 7.988 mm (39.0%) → **14.77 mm (72.1%)** |

Energy error improves ~53×; trajectory error **doubles**. The governor is a
safety envelope, not an accuracy device — now demonstrated rather than asserted.

### R5.1c — the mechanism, measured (why 196× energy is only 1.2× deflection)

A reviewer will ask how the ungoverned run can hold 196× the reference energy
while its peak deflection is only 24.1 mm against 20.0. Answer: the excess is
neither kinetic nor low-frequency. Measured at the peak-energy frame:

| arm | KE fraction | spectral centroid | energy above 10 kHz |
|---|---:|---:|---:|
| ungoverned | 0.3% | 24130.5 Hz | **99.626%** |
| governed | 1.0% | 23350.5 Hz | **97.670%** |
| xpbd converged | 15.0% | 29.7 Hz | 0.000% |
| oracle | 6.6% | 25.2 Hz | 0.000% |

The shelf spectrum is sharply BIMODAL — ten bending modes at 20.34 Hz … 2.033
kHz, then a stiff cluster of six at 20.685 … 24.708 kHz. Any threshold inside
that decade-wide gap gives the same number, so the 10 kHz cut is not a tuned
knob (verified: the gap is 2033 → 20685 Hz). The substep rate at 8×2 is 240 Hz,
so the stiff cluster sits ~200× above its Nyquist and is unrepresentable —
this is the documented stiff-row injection mode.

**Two consequences, both honest and both new:**
1. The spurious energy lives in modes that barely move the support surface, so
   an energy metric and a deflection metric measure genuinely different things.
   This retroactively explains R4's split verdict (peak agrees to 2.4%, L∞
   differs by 34%).
2. **The γ-projection is a single scalar, so it cannot redistribute energy
   across the spectrum.** It removes the right AMOUNT (1555.6 → 29.26 J) and
   leaves the spectral character intact (99.6% → 97.7% above 10 kHz), while
   scaling down the legitimate low-frequency sag along with the noise (peak
   deflection 24.1 → 5.9 mm against a reference 20.0). That is precisely why
   R5.1b's L∞ degrades, and it is a mechanism, not a guess.

### R5.2 — AVBD post-projection contact validity (Table 2 completion)

E-S3 ported to the augmented-Lagrangian host on its two R>1 cells (table scene,
4×1, both relaxations — R = 1.179 / 1.700, Eq.-(2) margins +5.35 / +15.08 J).

| scene | relax | clamped | γ min | gap viol. med / max [mm] | pre-scale max [mm] | impulse | λ var. |
|---|---:|---:|---:|---:|---:|---:|---:|
| table | 0.7 | 27/108 | 0.729174 | 0.011 / **1.429** | 0.4646 | 1.169× | 0.41× |
| table | 1.0 | 25/108 | 0.601613 | 0.023 / **3.108** | 0.5645 | 1.392× | 1.38× |

Momentum change across the projection is **0.000e+00 kg·m/s exactly** in every
clamp-active substep (same as XPBD, and necessarily so: the scale writes only
modal state). `holds()` and `passive()` both True in both cells.

**The projection is an order of magnitude gentler on this host** than on the
position-based one (XPBD: 44–99% of substeps clamped, worst violation 21.6 mm,
corrective impulse to 8.7×, λ variance to 58×). Consistent with R1: AVBD's
overdrafts are ≤15 J, so γ barely has to bite (min 0.60–0.73). The
pre→post multiplier is comparable (3.1× and 5.5×, against XPBD's 3.5–12.6×);
what differs is the absolute scale.

### FOUR PORTING TRAPS — the E-S3 wrappers do NOT transfer unchanged

Anyone re-deriving these must handle all four; each one silently produces wrong
numbers rather than an error.

1. **`sol._q` on AVBD is the list of body QUATERNIONS (xyzw)**
   (`solver_6dof.py:311`), not the modal coordinate — that is `_q_modal_host`.
   E-S3's `_gaps()` reads `sol._q` and would compute a gap from a quaternion.
2. **Support rows are parallel lists**, not objects: `_support_row_cidx` (index
   into `_rows`, giving `body_a`/`off_a`), `_support_U_y_rows`,
   `_support_y_rest`.
3. **The ledger must be PRE-CONSTRUCTED** (`solver_6dof.py:2449` builds it
   lazily on the first substep). The R1 trap, hit again here.
4. **UNITS: `c_lambda` is a FORCE in newtons** — X1d (`run_static_ledger.py`)
   validates Σ|λ_N| = m·g per resting body against the analytic weight. So the
   impulse is λ·h_sub, NOT the λ/h_sub of the position-based probe, whose
   multiplier is a different object. Caught by noticing a "steady impulse" of
   5052 N·s; corrected to 0.300 N·s. **The reported ratio is invariant to the
   factor** (1.169 / 1.392 either way), so no conclusion changed — but the
   absolute column would have been mislabelled by 4 orders of magnitude.
   The paper reports only the ratio, on both hosts.

Clamp site asserted at runtime, not assumed: the table scene is built without
native cargo, so the support-only clamp (`_modal_commit`, `:2637`) fires and
the augmented (q_support, a_cargo) clamp at `:3303` does not.

### R5.4 — normalized penetration (completes R0 item 10)

E-S3's worst-case post-projection penetration is 21.6 mm (shelf 4×1). R0 put
the geometry half in the paper (72% of the 30 mm board thickness, 2.7% of the
0.8 m span); the missing half was the sag the projection destroys, which needed
an instrumented run. "Resting sag" is defined as the tail median of
max_i |d_i(t)| over the last half of the window, governor OFF, at a converged
budget — so it is the scene's own equilibrium, not a truncation artifact.

| unclamped reference | resting sag | peak dynamic deflection | 21.6 mm is |
|---|---:|---:|---|
| xpbd converged 500×1 | 1.714 mm | 20.482 mm | 12.60× the sag, **1.05×** the peak |
| oracle impulse 500×1 | 2.377 mm | 20.000 mm | 9.09× the sag, **1.08×** the peak |

**The sharp statement: the worst-case penetration is the board's entire dynamic
deflection.** At the worst substep the projection does not merely reduce the
sag, it removes all of it and then some (1.05–1.08× the peak the unclamped
scene ever reaches, 9–13× its resting sag). This is a starker framing than
either the thickness fraction or the bare millimetres, and it is the honest one.

### Acceptance (plan §6.7)

1. **Non-perturbation, exact**: the ungoverned and governed arms reproduce the
   frozen `solver_matrix.csv` cell to the last digit — 53.73070660394743 and
   1.0106758619142793, |diff| = 0 (`--check-frozen`).
2. Table 2 now covers AVBD's problem cells (2 new rows).
3. Numbers frozen here with command + commit + machine before entering the tex.
4. Triptych: see the page-budget decision below.

---

## R6 — prior-art positioning of the governor (2026-07-19)

Plan §6.8. No compute: a related-work item. Commit `b639c16` + working tree.

Three lines of prior art now cited, with the positioning stated rather than
implied. Two were already in `references.bib` but **uncited**; one was added.

| work | status | framing in §1 |
|---|---|---|
| Hannaford & Ryu 2002, time-domain passivity control | in bib, was uncited | the observer: watch produced energy, damp when it goes negative |
| Franken et al. 2011, two-layer passivity / energy tanks | **ADDED** | gives the observer explicit state — spend only what the tank holds |
| Dinev et al. 2018, FEPR | in bib, was uncited | also projects state post-solve, but onto conservation of TOTAL energy |

**Verification of the new entry** (the repo's rule is that references are
verified, not recalled): Franken, Stramigioli, Misra, Secchi, Macchelli,
"Bilateral Telemanipulation With Time Delays: A Two-Layer Approach Combining
Passivity and Transparency", *IEEE Transactions on Robotics* **27**(4),
741–756, Aug 2011, doi `10.1109/TRO.2011.2142430`. Confirmed 2026-07-19 against
the University of Twente research record and the publisher DOI; the two-layer
energy-tank architecture is this paper's contribution.

### The positioning, in two claims

1. **The reservoir is a passivity observer with a transplanted supply.** It
   keeps the observer-plus-storage structure and changes the funding: the tank
   is fed by measured gross rigid-side dissipation — energy the contact solve
   demonstrably removed *elsewhere* — rather than by the port it regulates.
2. **The actuator is state-space, not force-space.** Classical passivity
   control modulates a damping force; a fixed-budget solver has already
   committed its multipliers by the time the excess is observable, so the only
   remaining actuator is a scale on realized state. This is also why the
   projection cannot be band-selective (R5.1c).

Against FEPR the difference is directional: FEPR projects onto *total*-energy
conservation and can therefore restore energy; ours is one-sided, caps a single
subsystem's storage, and never returns energy the solver lost.

This answers the panel's "a simple energy clamp without prior-art positioning"
directly, and joins rather than replaces the four must-cite adversaries of §1.

---

## R7 — enforcement cost, honestly (2026-07-19)

Plan §6.9. The device half (R7b) is already frozen in
`docs/mig2026_device_ledger.md`. This is the **CPU half**, and it corrects the
number the paper was printing.

Harness: `benchmarks/paper_eval/x5_perf/run_perf_reps.py` (existing, unmodified).
Machine: **Apple M4, CPU only, CPython 3.12** — the paper's declared CPU host.
Commit `65d5908` + working tree. 10 reps × 100 frames, warm-up 5, fresh scene
build per rep; overhead = (clamped mean − unclamped mean) per repetition.

```sh
.venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_reps.py \
    --only shelf,ledge,dinner --reps 10 --frames 100
```
Data: `x5_perf/out/perf_reps_summary.csv`, `perf_reps.csv`, `perf_reps_m4.log`.
The prior server artifacts are preserved as `perf_reps_{,summary_}server_ref.csv`.

### TWO DEFECTS IN THE PRINTED NUMBER, both found here

The paper said: *"The ledger adds 0.8–2.9 ms/step at the evaluated configuration
on the CPU host."*

1. **It was measured on the wrong machine.** That range comes from
   `x5_perf/out/perf_reps_server.log` — an **x86 server** — while §3 of the paper
   states that every solver-behaviour number except the device timing was
   produced on the Apple M4. `paper/NUMBERS.md` even records a "Mac cross-check
   3.5–4.6×", i.e. the declared host is 3.5–4.6× faster than the machine the
   number came from. This was an undisclosed second machine.
2. **The upper bound was never statistically resolved.** The 2.9 ms that sets it
   is the server's `dinner xpbd: clamp +2.89 ± 2.76` — the standard deviation
   over 10 repetitions is 95% of the mean. The headline range was quoting noise.

### Measured on the declared host (Apple M4)

| scene | solver | baseline [ms] | worst [ms] | ledger [ms] | % of baseline | resolved? |
|---|---|---:|---:|---:|---:|---|
| shelf | xpbd | 18.45 ± 0.08 | 29.55 | +0.23 ± 0.14 | 1.25% | marginal |
| shelf | avbd | 12.14 ± 0.06 | 14.32 | +0.41 ± 0.10 | **3.35%** | yes |
| ledge | xpbd | 30.68 ± 0.12 | 51.63 | +0.27 ± 0.19 | 0.86% | marginal |
| ledge | avbd | 10.99 ± 0.09 | 11.86 | +0.35 ± 0.09 | 3.22% | yes |
| table | xpbd | 125.63 ± 5.68 | 194.59 | +1.35 ± 2.08 | 1.08% | **NO** (σ > μ) |
| table | avbd | 37.47 ± 1.13 | 48.76 | +0.04 ± 1.43 | 0.09% | **NO** (σ ≫ μ) |

**Reportable claim**: the ledger costs **0.23–0.41 ms/step, 0.9–3.4% of
baseline**, on the four shelf/ledge configurations where it resolves above
run-to-run variance. On the table scene the per-repetition spread exceeds the
effect in both hosts, so it is reported as unresolved (bounded by ~1.4 ms,
consistent with the resolved rows) rather than quoted as a mean. This is
strictly more defensible than "0.8–2.9 ms" and it is on the right machine.

**The percentage is the portable quantity.** Absolute times differ 3.5–4.6×
between the two machines, but the percentages agree closely where both resolve
(shelf xpbd 1.25% M4 vs 1.23% server; ledge xpbd 0.86% vs 0.84%). That is why
plan §6.9 asked for a percentage, and it is the form the paper now prints.

**CPU baselines are far from interactive**: 11.0–125.6 ms/step at 16×4, i.e.
1.3–15× short of a 120 Hz budget. The host-side governor is not an interactive
path and the paper should not imply otherwise; this is the motivation for the
separate device measurement, not a competitor to it.

### Device half — scope, stated in the paper

R7b (frozen separately) gives 5.0–8.9 ms/step at 16×4 on an RTX 4090, ledger
carried **read-only as a monitor**. Plan §6.9 requires stating plainly that a
device-resident *enforced* γ **does not exist** — it is the long-paper unlock —
so the panel's "device-side governed timing" ask is out of scope by design. The
paper now says this rather than leaving it inferable.

### Acceptance (plan §6.9)

Baseline next to overhead as a percentage, per scene and host, on the declared
CPU machine; device paragraph names the GPU, keeps "monitor-only" explicit, and
states the absent enforced-γ path. Done.

---

## Post-R7 integrity check (2026-07-19)

Run after R0–R7 were all committed, to confirm the evidence chain still holds
end to end. Commit `581e9b9`.

1. **R1 re-run reproduces exactly.** All 8 frozen E-S1b XPBD cells and all 3
   per-solver worst-over-cells values match (`--check-frozen`), and the full
   72-cell CSV is **bit-identical in every physical column** — the only diff
   against the committed file is the `wall_s` timing field. Determinism on a
   fixed machine and interpreter is therefore measured, not assumed.
2. **R5 re-run reproduces exactly** — 53.73070660394743 and 1.0106758619142793,
   |diff| = 0.
3. **`verify_paper_numbers.py`: 34/34 pass.** Every R5/R7 number printed in
   `main_short.tex` is tied mechanically to its frozen CSV. Two of the checks
   guard reasoning rather than values: the 10 kHz spectral cut must still sit
   inside the real 2.03→20.7 kHz gap (so it cannot become a tuned knob), and the
   table-scene ledger overhead must STAY unresolved (σ > μ), because the paper
   reports it as unresolved.
4. **All 12 cited CSVs verified present** and enumerated in the supplementary
   manifest, including `substep_sweep.csv`, which §3.1's "full ladder in the
   supplement" now depends on after the §6.12 demotion.

### Status of the review-response plan

| item | state |
|---|---|
| R0–R7 | **complete, frozen, committed** |
| R5.3 triptych | **BLOCKED** — needs an interactive browser capture session (no offscreen render path); also §6.12's second demotion target |
| video.mp4 | **BLOCKED** — same capture limitation |
| R8 | **NO-GO** by default (§6.10); its gate (R0–R7 frozen, ≥5 buffer days) is now *satisfiable*, so it is a live decision at the ~Jul 27 go/no-go, not an automatic skip |

Paper: 6 pages of body, references alone on p7, 0 undefined refs, 0 overfull
boxes. Deadline 2026-08-07 23:59 AoE; submission window opens Jul 25.

---

## R8 pre-gate investigation — is a floor-bearing projection enforceable? (2026-07-19)

Plan §6.10 go/no-go evidence. **Not a paper number** — R8 is NO-GO and nothing
here enters `main_short.tex`. This exists so the ~Jul 27 gate is decided on
measurement rather than on the analytical hand-wave that prompted it.

Harness: `benchmarks/paper_eval/x1_passivity/probe_r8_feasibility.py` (NEW).
Machine: Apple M4, CPU only. Commit `a74dfa6` + working tree.
Data: `out/r8_feasibility.csv`, `out/r8_feasibility_substeps.csv`.

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/probe_r8_feasibility.py
```

### The question

The present projection scales the WHOLE modal state, so
E(γ) = γ²·E_new and γ→0 always reaches zero: Eq. (2) is enforceable **by
construction**. Both proposed successors preserve part of the state, leaving a
γ-independent constant:

    E(γ) = a γ² + b γ + c,     c = energy locked in the preserved part

so a feasible γ exists only when `ceiling = E_mod⁻ + B ≥ c`. Measured at the
real decision points of a real governed run (the actual `passivity_gamma` call
sites), with the energy split reconstructed exactly — **worst relative
reconstruction error 4.2×10⁻¹⁶** against the solver's own `e_modal_new`.

### Result — the risk is REAL, and it lands on the OTHER variant

| cell | clamped | **R8b band-selective** infeasible | **R8a deviation-ref** infeasible | E_low share of E_mod |
|---|---:|---:|---:|---:|
| shelf 4×1 r0.7 | 107/108 | **8 (7.5%)** | 0 (0.0%) | 0.087% |
| shelf 4×1 r1.0 | 107/108 | **23 (21.5%)** | 1 (0.9%) | 0.030% |
| shelf 8×2 r0.7 | 162/216 | 1 (0.6%) | 2 (1.2%) | 1.005% |
| ledge 4×1 r0.7 | 98/108 | **37 (37.8%)** | 0 (0.0%) | 0.687% |

**I had the attribution backwards.** The caveat was reasoned about
deviation-referencing (R8a, the panel's proposal) but it bites hardest on the
**band-selective** variant — the one §3.3 originally named as "the obvious next
mechanism". Band-selective would fail to enforce Eq. (2) in up to **37.8%** of
clamp-active substeps. That is not a corner case; it is a routine breakage of
the guarantee.

Why: the two floors are different objects. The deviation floor is the
**settled** sag's strain energy (median 0.050–0.074 J); the band floor is the
whole bending band including its dynamic oscillation (median 0.91–0.95 J), a
**12–20× larger** floor for the same scene.

### R8a's apparent safety is thin, and rests on a proxy

`q_eq` here is the tail-median modal state of a converged unclamped run — the
**resting** equilibrium. A real R8a would recompute q_eq per substep from the
live contact load, which during impact is larger. Since c ∝ q_eq², the critical
factor is s* = √(ceiling/c):

| cell | s* median | s* p10 | s* min | infeasible if q_eq is 2× | 4× |
|---|---:|---:|---:|---:|---:|
| shelf 4×1 r0.7 | 24.7 | 2.59 | 1.33 | 4% | 32% |
| shelf 4×1 r1.0 | 18.3 | 1.95 | 0.97 | 11% | 34% |
| **shelf 8×2 r0.7** | **1.74** | 1.19 | 0.96 | **60%** | 75% |
| ledge 4×1 r0.7 | 30.2 | 5.24 | 2.30 | 0% | 5% |

So on shelf 8×2 the median substep is already only 1.74× from infeasible, and a
merely 2× larger loaded equilibrium puts 60% of substeps out of reach. **R8a's
0–1.2% is a floor on the true infeasibility rate, not an estimate of it.**

### The generalizable insight

The floor binds **not because the preserved energy is large but because the
reservoir is nearly empty exactly where the governor matters.** In these cells
the per-substep budget is 0.020–0.167 J against a modal energy of 137–1030 J —
E_low is 0.03–1.0% of the modal energy and still exceeds the ceiling up to 38%
of the time. Any floor-bearing projection is therefore most likely to fail in
precisely the starved cells that motivate having a governor at all.

### Benefit, and why we do not claim it

Median surface excursion on clamp-active substeps [mm], shelf 4×1 r0.7:
pre-scale 1.443 → present projection **0.252** → band-selective 1.153 →
deviation-referenced 1.650. So preserving a band does retain most of the
excursion the present γ destroys, which is the mechanism's stated purpose.
**But the probe measures max_i |U_y·q|, an unsigned excursion**, so it cannot
distinguish "sag preserved" from "surface displaced the other way" — the
deviation-referenced figure exceeding the pre-scale value hints at partial
cancellation between q_eq and the scaled deviation. A benefit claim needs the
signed gap, which this probe does not measure. Not claimed.

### Bearing on the gate

- The panel's proposal (R8a) is the **better** of the two successors, and the
  paper's Limitations sentence already names that one rather than the
  band-selective variant. That choice is now measurement-backed.
- The Limitations caveat as printed ("would hold only while the reservoir
  exceeds the sag's own strain energy") is **confirmed as a live constraint**,
  not a theoretical one — s* median reaches 1.74.
- A GO would therefore need q_eq computed from the live load (not the resting
  proxy), a fallback for infeasible substeps, and re-freezing the 72-cell
  matrix under a bound that is no longer enforceable by construction. That is
  substantially more than "swap the projection".

**No paper text changes from this.** The findings support the sentence already
committed at `a74dfa6`; the numbers stay in this ledger.

### R8 addendum — the two variants trade OFF, and the plan's premise is wrong

Same probe, reading the penetration proxy (how far the projection lifts the
support *into* the resting body) rather than the unsigned excursion. This is
the visible quantity and it reverses the ranking above.

| cell | present p50 / max [mm] | band-selective p50 / max | deviation-ref p50 / max |
|---|---:|---:|---:|
| shelf 4×1 r0.7 | 1.19 / **15.46** | 0.25 / **1.04** | −0.15 / 13.96 |
| shelf 4×1 r1.0 | 1.78 / **22.03** | 0.44 / **1.63** | −0.22 / 19.89 |
| shelf 8×2 r0.7 | 0.31 / 5.98 | 0.01 / **0.25** | −0.66 / 4.89 |
| ledge 4×1 r0.7 | 0.03 / 14.39 | 0.00 / **0.07** | −0.01 / 14.29 |

**Band-selective collapses the worst case by 13–200×** (15.5→1.0, 22.0→1.6,
14.4→0.07 mm). **Deviation-referencing barely moves it** (15.5→14.0,
22.0→19.9, 14.4→14.3 mm).

**This contradicts plan §6.10 directly.** It asserts of the two variants:
"Either preserves load-bearing sag and should collapse the 21.6 mm worst case."
Measured: only the band-selective one collapses it. Deviation-referencing does
preserve the sag — but the *resting* sag is a small part of the surface during
impact, and the dynamic bending that dominates the excursion sits in the
deviation, which is scaled away just as the present projection scales it. The
negative medians are that same effect: with `q_eq` preserved and the deviation
shrunk, the surface can move *away* from the body rather than into it.

### The resulting trade-off — the effective variant is the unenforceable one

| | Eq. (2) enforceable | fixes the 21.6 mm case |
|---|---|---|
| band-selective | **NO** — infeasible up to 37.8% of clamp substeps | **YES** — worst case ÷13–200 |
| deviation-referenced | yes — 0–1.2% (thin, proxy-dependent) | **NO** — worst case ÷1.1 |

So R8 is not one mechanism with a caveat; it is two mechanisms that fail in
opposite ways. A GO would have to either recover enforceability for the
band-selective form (a fallback for infeasible substeps, which reintroduces the
whole-state scale it was meant to avoid) or accept that deviation-referencing
does not deliver the benefit R8 exists to obtain.

### Visibility

Per-substep, at governed states: the median frame differs by ~0.25–1.3 mm
between present and band-selective — sub-pixel at any normal render scale, so
typical frames look identical. The **worst** moments do not: 15–22 mm of
interpenetration on a 30 mm board is the "visible interpenetration, not a
sub-millimetre artifact" the paper already calls out, and that is exactly what
band-selective removes.

**Caveat that limits all of the above**: this is a per-substep counterfactual
evaluated on the *current* governor's trajectory. A real run under either
variant diverges, and this repo has documented that differences far smaller
than 1 mm produce visibly different outcomes on chaotic contact stacks
(the ARM/x86 divergence). "Sub-millimetre per substep" therefore does **not**
imply "the video looks the same". Only a full run would settle that, which is
what a GO costs.

### R8 GATE DECISION — **NO-GO**, decided 2026-07-19 (user-requested, early)

Plan §6.10 set the go/no-go at ~Jul 27 with default NO-GO. Called early because
the probe above settles it on evidence rather than schedule. Five grounds, in
order of weight:

1. **The premise is measurably false for the option the plan actually names.**
   §6.10 asserts "Either preserves load-bearing sag and should collapse the
   21.6 mm worst case." Deviation-referencing does **not**: worst-case
   penetration goes 22.03 → 19.89 mm (÷1.1). The item's stated benefit is not
   delivered by the mechanism it proposes.
2. **The variant that does deliver is not enforceable.** Band-selective
   collapses the worst case (22.03 → 1.63 mm, ÷13–200×) but leaves no feasible
   γ in up to **37.8%** of clamp-active substeps, because the reservoir is
   nearly empty in exactly the starved cells the governor exists for. It would
   trade a bound that holds by construction for one that holds sometimes.
3. **Not novel, and the paper's own Table 1 proves it.** Frequency-selective
   energy removal is already in this solver: Rayleigh damping
   D = α₀M + α₁K, with the α₁K term dissipating mode i in proportion to ω_i².
   That is printed in Table 1. Beyond that, discarding numerically-dominated
   high-frequency modes is textbook modal truncation, and frequency-separated
   passivity control already exists in haptics (FS-VSPC). Making the
   frequency-selectivity a *budget* rather than a *coefficient* is a modest
   variation, not a contribution — and §14's claim discipline would not permit
   claiming it.
4. **The third option was never in scope of what was tested, and is not free.**
   §6.10's option (b), re-solve contact once after projection, is untested. It
   is structurally the most promising (it leaves the whole-state γ intact, so
   Eq. (2) stays enforceable by construction, and fixes contact separately) but
   a corrective solve does work on the bodies *after* the ledger has committed,
   so it can inject energy from the other end and may need an iterated
   ledger — its own research question, not a patch.
5. **Cost is unchanged and the calendar has not improved.** It remains a solver
   behaviour change requiring re-freezing the 72-cell matrix, E-S3 and the
   teaser, with the submission window opening Jul 25 and the deadline Aug 7.

**NO-GO condition is already satisfied**: §6.10 requires "one Limitations
sentence names it as the identified next mechanism" — committed at `a74dfa6`,
naming deviation-referencing (the safer of the two) with its enforceability
caveat. No further paper change is required.

**Carried to the long paper** (not this submission): option (b) is the live
research direction, and the band/deviation trade-off measured here — effective
but unenforceable versus enforceable but ineffective — is the finding that
makes it interesting rather than a patch.
