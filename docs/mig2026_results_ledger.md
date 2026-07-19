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
