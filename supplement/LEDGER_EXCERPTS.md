# Frozen results ledger — excerpts

Each entry carries the generating command, the commit and the machine. Reproduced verbatim from the project's results ledger.

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

### E-C6 — the DEPLOYED budgets 1×8 and 2×4 (plan §7.7)

**Machine:** Apple M4, CPU only, CPython 3.12 (the ARM-M4-only header above).
**Commit:** `7f7450a` working tree, plus the `run_perf_reps.py`
`--budget` / `--out-prefix` patch committed as the C6 commit. No solver source
was touched; both new flags are additive and default to the frozen behaviour
(`--budget` unset ⇒ PAPER_CONFIG 16×4; `--out-prefix` unset ⇒ `perf_reps`, so
the frozen `perf_reps.csv` is never appended to — verified untouched).

**Why:** the paper motivates with "interactive position-based solvers ship
budgets near 1×8 to 2×4" but the sweep starts at 4×1. The panel was right that
this was unmeasured. It is now measured, and it strengthens the motivation.

Cells: (K,S) ∈ {(1,8), (2,4)} × 3 scenes × 3 hosts, relaxation 0.7 (the
follow-solver default; inert on impulse) = **18 cells**, run OFF and ON.

#### Commands

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_eq2_utilization.py \
    --budgets 1x8,2x4 --relaxes 0.7 --out eq2_deployed
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_solver_matrix.py \
    --budgets 1x8,2x4 --relaxes 0.7 --out solver_matrix_deployed
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_projection_validity.py \
    --scenes shelf,ledge --budgets 1x8,2x4 --relax 0.7 \
    --out projection_validity_deployed
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_governed_accuracy.py \
    --scene shelf --cell 1x8 --relax 0.7 --out governed_accuracy_1x8
.venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_reps.py \
    --budget 1x8 --only shelf,ledge,dinner --out-prefix perf_reps_1x8
.venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_reps.py \
    --budget 2x4 --only shelf,ledge,dinner --out-prefix perf_reps_2x4
```

The two perf commands were run **serially** — a first attempt overlapped them
and the overlapping rows were deleted and re-measured, because concurrent runs
contend for CPU and invalidate wall-clock. (Only timing is affected this way;
the energy sweeps are deterministic.)

#### (1) Governor OFF — Eq. (2) at the deployed budgets (`eq2_deployed.csv`)

| host | Eq. (2) violated | R > 1 | worst R | worst margin [J] | return channel |
|---|---|---|---|---|---|
| position-based | **6/6** | **6/6** | 2282 | **+1.135×10⁶** | 15.1–52.0% |
| augmented-Lagr. | 5/6 | 0/6 | 0.141 | +0.158 | 100.8–105.6% |
| seq. impulse | 0/6 | 0/6 | 0.533 | −5.74×10⁻⁴ | 5.1–27.1% |

Per-cell R (OFF), position-based: shelf 772.1 / 444.5, ledge 925.4 / 2282,
dinner 4.05 / 5.25 at 1×8 / 2×4.

**This is the strong outcome, not the benign one the risk table hedged for.**
In the frozen 24-cell matrix the position-based host exceeds R = 1 in 8/24
cells; at the two budgets the paper says are actually deployed it exceeds it in
**6 of 6**, in every scene. The deployed points carry 8 row evaluations —
*more* than the 4×1 corner's 4 — and still inject universally, which is the
equal-32 probe's substep-vs-iteration finding (K32·S1 holds; K4·S8 overdraws
481 J) reproduced at the deployed operating point.

The three-host ordering of the matrix is preserved exactly: catastrophic /
pervasive-but-negligible / never.

#### (2) Governor ON (`solver_matrix_deployed.csv`)

**18/18 cells satisfy Eq. (2).** Worst governed ratio **1.0221** (position-based,
shelf 2×4); worst net excess +2.27×10⁻¹³ J. Clamp activity per cell:

| host | shelf 1×8 | shelf 2×4 | ledge 1×8 | ledge 2×4 | dinner 1×8 | dinner 2×4 |
|---|---|---|---|---|---|---|
| position-based | 704/864 | 402/432 | 783/864 | 361/432 | 78/864 | 26/432 |
| augmented-Lagr. | 202/864 | 136/432 | 343/864 | 159/432 | 276/864 | 123/432 |
| seq. impulse | **0**/864 | **0**/432 | **0**/864 | **0**/432 | **0**/864 | **0**/432 |

The projection never fires on the impulse host at any deployed budget — the
same result as the matrix.

#### (3) Post-projection validity, position-based (`projection_validity_deployed.csv`)

| cell | clamped | min γ | gap viol. med / worst [mm] | pre-scale worst [mm] | impulse ratio |
|---|---|---|---|---|---|
| shelf 1×8 | 704/864 | 0.0113 | 0.063 / 7.78 | 3.11 | — (no steady state) |
| shelf 2×4 | 402/432 | 0.0121 | 0.127 / 9.48 | 3.08 | — (no steady state) |
| ledge 1×8 | 783/864 | 0.0101 | 0.016 / 8.26 | 2.79 | 1.19× |
| ledge 2×4 | 361/432 | 0.0092 | 0.020 / 9.75 | 2.98 | 1.02× |

`|ΔP|` across the projection is **exactly zero** in every clamp-active substep
of every cell, as at 4×1.

**The projection is markedly GENTLER at the deployed budgets than at the 4×1
corner Table 2 reports:** worst gap violation 7.8–9.8 mm against 21.6 mm, and
the corrective impulse 1.02–1.19× steady state against 8.7×. The headline
21.6 mm number is an adversarial-corner figure, and T3 says so.

#### (4) Governed accuracy, shelf 1×8 relax 0.7 (`governed_accuracy_1x8.csv`)

Converged reference (oracle, impulse K=500): ratio 0.2734809, peak modal
energy 7.9176 J.

- energy error **2823× → 3.725×** (+2.234×10⁴ J → **+21.57 J**)
- ungoverned ratio 772.06 → governed **1.01870**
- deflection L∞ **21.54 mm → 19.20 mm** = 107.7% → **96.0%** of reference peak
- against the position-based host's own fixed point (0.2996, 8.2236 J):
  2718× → 3.586×; L∞ 24.31 → 19.68 mm (118.7% → 96.1%)

**The 8×2 trajectory trade-off does NOT reproduce here, and the honest reading
is narrow.** At the frozen 8×2 cell the governor improved energy ~50× while
*doubling* state error (33% → 71% of reference peak). At the deployed 1×8 cell
it improves both, because the un-governed trajectory is already worse than the
governed one (107.7% vs 96.0%). It does **not** follow that the governor is
accurate at deployed budgets: 96% of the reference peak is still a wrong
trajectory. What reverses is only the *direction of the trade*, and §Limitations'
"stable is not accurate" stands unchanged.

Note: `run_governed_accuracy.py` prints an acceptance block comparing against
the hard-coded **8×2** frozen constants (53.73 / 1.0107), so it reports
"MISMATCH / FAIL" on any other cell. That is the guard doing its job on a cell
it was not written for, **not** a failed measurement. The frozen 8×2 numbers
are untouched.

#### (5) Wall-clock, 10 reps × 100 frames (`perf_reps_{1x8,2x4}_summary.csv`)

| cell | host | baseline [ms] | ledger [ms] | % |
|---|---|---|---|---|
| shelf 1×8 | position-based | 4.61 ± 0.05 | +0.30 ± 0.07 | +6.6% |
| shelf 1×8 | augmented-Lagr. | 3.23 ± 0.03 | +0.67 ± 0.09 | +20.9% |
| ledge 1×8 | position-based | 9.06 ± 0.17 | +2.22 ± 0.18 | +24.4% |
| ledge 1×8 | augmented-Lagr. | 3.19 ± 0.03 | +0.64 ± 0.08 | +20.0% |
| dinner 1×8 | position-based | 36.19 ± 0.38 | **−4.40 ± 0.50** | −12.2% |
| dinner 1×8 | augmented-Lagr. | 6.80 ± 0.06 | +0.85 ± 0.12 | +12.6% |
| shelf 2×4 | position-based | 3.33 ± 0.08 | +1.14 ± 0.07 | +34.3% |
| shelf 2×4 | augmented-Lagr. | 2.32 ± 0.02 | +0.35 ± 0.04 | +15.0% |
| ledge 2×4 | position-based | 6.80 ± 0.11 | +1.26 ± 0.17 | +18.5% |
| ledge 2×4 | augmented-Lagr. | 2.29 ± 0.07 | +0.30 ± 0.06 | +13.3% |
| dinner 2×4 | position-based | 25.76 ± 0.37 | **−1.72 ± 0.56** | −6.7% |
| dinner 2×4 | augmented-Lagr. | 5.38 ± 0.10 | +0.47 ± 0.10 | +8.7% |

Two things here are NOT what §3.5's 16×4 paragraph says, and both must be
stated as T3 rows rather than folded into it:

1. **The percentage overhead is much larger at deployed budgets** (6.6–34.3%
   vs 0.9–3.4% at 16×4). Expected: the ledger's per-substep cost is fixed
   while the baseline shrinks with the budget. The absolute cost is comparable
   (0.30–2.22 ms vs 0.23–0.41 ms).
2. **The table-scene overhead is NEGATIVE and outside noise** (−4.40 ± 0.50 and
   −1.72 ± 0.56 ms): the governed run is genuinely *faster*. Reading: the
   projection suppresses the divergent modal deflection, so the substep
   generates less contact work. This is a behaviour difference (the governed
   and un-governed trajectories differ), not a measurement artifact — unlike
   the 16×4 table cell, where the spread exceeded the mean and we declined to
   quote a figure. Report as measured, with the mechanism named as a
   conjecture we did not isolate.

Also worth stating: at 2×4 the position-based shelf (3.33 + 1.14 = 4.47 ms) and
ledge (6.80 + 1.26 = 8.06 ms) both fit a 120 Hz budget **with** the governor on
CPU, and shelf does at 1×8 too (4.91 ms). §3.5's "1.3–15× short of a 120 Hz
budget" is a 16×4 statement and stays scoped to 16×4.

#### Cell-count phrasing (plan §7.7's grep item)

Matrix: 72 cells, 60 distinct (impulse's 12 relax pairs are bit-identical).
T3: 18 cells, all distinct (single relax axis). Combined **90 measured cells,
78 distinct configurations** — the three sites that said "72 / 60" are updated
to "90 / 78" in the C6 commit.

**Nothing in §E-S1b changed.** T3 is a separate table; Fig. 1 is untouched.

---

## E-C9 — single-host robustness ablation of the XPBD result (plan §8.4, P7)

**Machine:** Apple M4, CPU only, CPython 3.12.12, numpy 2.4.5, macOS 15.2
(arm64 Darwin — the ARM-M4-only header above).
**Commit:** `dc440d2` (code branch `impulse-native-constraint`), working tree
adding the two new measurement-only harnesses below. **No solver source was
touched**: every knob is set at runtime via `build_reduced_*` kwargs or solver
attributes, the C6 pattern.
**Runs:** serial, one process, one cell at a time. This entry reports no
wall-clock quantity, so the concurrent-run timing incident does not bear on it;
the rule was kept anyway.

**Why:** both six-reviewer panels asked whether the position-based amplification
is a knife-edge artifact of one configuration. The paper had breadth on two axes
(budget, relaxation) and held everything else fixed.

**Acceptance, pre-registered in plan §8.4 BEFORE running** (so the reading could
not be chosen after seeing the numbers): *persistence in kind* — Eq. (2)
violated AND R >> 1 away from base — NOT magnitude stability. `h` in particular
changes the scene's difficulty, so magnitudes were expected to move.

#### Commands

```sh
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_robustness_ablation.py
.venv/bin/python benchmarks/paper_eval/x1_passivity/run_k_convergence.py \
    --scene ledge --relax 1.0 --out k_convergence_ledge_worst
.venv/bin/python benchmarks/paper_eval/x1_passivity/probe_complementarity_residual_nd.py
.venv/bin/python benchmarks/paper_eval/x1_passivity/probe_complementarity_residual_nd.py \
    --scene ledge --relax 1.0 --out complementarity_residual_nd_ledge
```

`run_robustness_ablation.py` does not re-implement the accounting: it calls
`run_eq2_utilization.one()` (the §6.3 harness, already cross-validated against
the impulse live monitor) with a wrapped builder, so the ledger runs live while
`passivity_gamma == 1.0` makes every state write in the enforcement path dead.

**Non-perturbation check — both base rows reproduce frozen E-S1b EXACTLY:**
ledge relax 1.0 4×1 → R = 119534 (frozen 119534); shelf relax 0.7 4×1 →
R = 6333.22 (frozen 6333.22).

#### (1) The ablation, governor OFF (`robustness_ablation.csv`)

**24 of 24 configurations violate Eq. (2), with R > 1 in 24 of 24.**
One axis at a time from each base cell; physical window held fixed across the
`h` axis (nframes/settle scale with 1/h), realized rank reported per row.


**ledge, relaxation 1.0, 4×1 (matrix worst cell)**

| axis | value | realized rank | R | strict Eq.-(2) margin [J] |
|---|---|---|---|---|
| *base* | — | 16 | 1.195e+05 | +4.436e+07 |
| h | 1/60 | 16 | 4.674e+05 | +1.653e+08 |
| h | 1/240 | 16 | 9804 | +3.774e+06 |
| support_compliance | 1e-06 | 16 | 9.424e+04 | +3.504e+07 |
| support_compliance | 0.0001 | 16 | 2.535 | +570.1 |
| contact_compliance | 1e-08 | 16 | 1.195e+05 | +4.435e+07 |
| contact_compliance | 1e-06 | 16 | 1.195e+05 | +4.435e+07 |
| rank | no local (excl. stiff cluster) | 12 | 3354 | +1.244e+06 |
| rank | n_global=18 | 22 | 1.279e+05 | +4.769e+07 |
| rayleigh_alpha0 | 1 | 16 | 1.195e+05 | +4.435e+07 |
| rayleigh_alpha0 | 6 | 16 | 1.195e+05 | +4.436e+07 |
| rayleigh_alpha1 | 1e-4 | 16 | 1.199e+05 | +4.447e+07 |

**shelf, relaxation 0.7, 4×1 (the 21.6 mm / teaser cell)**

| axis | value | realized rank | R | strict Eq.-(2) margin [J] |
|---|---|---|---|---|
| *base* | — | 16 | 6333 | +1.738e+05 |
| h | 1/60 | 16 | 1.534e+04 | +3.986e+05 |
| h | 1/240 | 16 | 494.6 | +1.429e+04 |
| support_compliance | 1e-06 | 16 | 6321 | +1.735e+05 |
| support_compliance | 0.0001 | 16 | 924.6 | +2.535e+04 |
| contact_compliance | 1e-08 | 16 | 6333 | +1.738e+05 |
| contact_compliance | 1e-06 | 16 | 6333 | +1.738e+05 |
| rank | no local (excl. stiff cluster) | 10 | 22.14 | +583.9 |
| rank | n_global=16 | 22 | 3.907e+04 | +1.072e+06 |
| rayleigh_alpha0 | 1 | 16 | 6412 | +1.76e+05 |
| rayleigh_alpha0 | 6 | 16 | 6218 | +1.706e+05 |
| rayleigh_alpha1 | 1e-4 | 16 | 6308 | +1.731e+05 |

Readings, in order of how much they move the result:

- **Modal rank is the strongest single lever, and it is a *sharpened diagnosis*,
  not a retraction** — the §8.4 contingency, which fired. Dropping the local
  bumps removes the stiff cluster entirely (shelf rank 16 → 10, no mode above
  2.03 kHz; ledge 16 → 12, none above 17.0 kHz) and cuts R by 286× on the shelf
  (6333 → 22.1) and 36× on the ledge (1.20×10⁵ → 3354). **But the violation
  survives**: +584 J and +1.24×10⁶ J respectively. So the amplification is
  *concentrated* in the stiff tail — consistent with §3.3, where 99.6% of the
  ungoverned energy sits there — and is *not caused only by it*. Adding
  resolved bending modes above base (rank 22) makes it worse on both scenes.
- **Support compliance is the strongest mitigator and still does not fix it.**
  At 10⁻⁴ m/N the ledge falls 1.20×10⁵ → 2.535 (47000×) and the shelf
  6333 → 924.6, yet both still overdraw (+570 J, +2.5×10⁴ J).
- **Rigid contact compliance is inert** (R unchanged to 4 significant figures on
  both scenes at both values). A useful negative control: the effect is specific
  to the contact→modal support row, not to generic contact softening.
- **Rayleigh damping is nearly inert** — ±1% on the shelf, ±0.4% on the ledge,
  across α₀ ∈ {1, 6} and α₁ = 10⁻⁴. The amplification is not a damping artifact.
- **`h` moves magnitudes in both directions, as pre-registered.** Coarser
  (1/60) is worse (ledge 4.67×10⁵), finer (1/240) is better (9804) but never
  safe. Consistent with truncation: a finer step buys more row evaluations.

#### (2) Worst-cell K-ladder (`k_convergence_ledge_worst.csv`)

Panel B asked whether convergence cures the *worst* cell or only the shelf drop.
Re-pointed at ledge relaxation 1.0, substeps pinned at 1:

R = 846352 (K=1) → 337715 → 168479 → **119534 (K=4, the frozen matrix cell)** →
52269 → 20373 → 2621 → 307.2 (K=16) → 3.976 (K=24) → **0.1653 (K=32)**,
monotone non-increasing throughout, against the converged reference 0.0288464
(impulse K=500). |XPBD − reference| shrinks 846352 → 0.1365. The crossing of
R = 1 sits between K=24 and K=32, matching the shelf sweep's K≈24.

Caveat for readers of that CSV: its `holds` column reads `True` for XPBD at
every K. That is the vacuous-ledger artifact recorded in E-S1b caveat 1 (with
the clamp off this harness never updates `cum_rigid_loss` on XPBD), **not** an
Eq.-(2) result. The Eq.-(2) verdicts in this entry come from the live-ledger
path in (1).

#### (3) Nondimensionalized complementarity residual — AND A CORRECTION
#### (`complementarity_residual_nd.csv`, `..._nd_ledge.csv`)

Both panels objected that `||min(C, λ)||_∞` mixes metres with force, so its
value is unit-system dependent and the paper's "residual passing ~3×10⁻⁵"
names no physical quantity. Re-logged with the two components split (penetration
in mm; multiplier surviving on separated rows, over the steady-state median
active multiplier λ̄, measured once at K=128 and held FIXED across the ladder)
and as `res_nd = max` of the two normalized parts, with L = the support
thickness read from the scene builder.

**shelf, relax 0.7** (L = 30 mm, λ̄ = 1.82286×10⁻⁴):

| K | 1 | 2 | 4 | 8 | 16 | 24 | 32 | 64 | 128 |
|---|---|---|---|---|---|---|---|---|---|
| gap viol. [mm] | 27.95 | 15.13 | 6.164 | 1.850 | 0.1592 | 0.02836 | 0.01075 | 0.003559 | 0.003559 |
| λ on separated rows [×λ̄] | 84.3 | 104.8 | 114.8 | 133.7 | 138.7 | 139.0 | 34.85 | **0** | **0** |
| res_nd | 84.26 | 104.8 | 114.8 | 133.7 | 138.7 | 139.0 | 34.85 | 1.186×10⁻⁴ | 1.186×10⁻⁴ |

**ledge, relax 1.0** (L = 80 mm, λ̄ = 1.14616×10⁻³): gap 25.73 → 0.05903 mm over
K = 1…128, plateauing by K=32; λ on separated rows 289.6 → 348.1 (K=4) → 309.1
(K=24) → **0** from K=32 on.

**TWO DEFECTS IN THE PRINTED SENTENCE, both found here.**

(a) **The quoted residual is, numerically, max penetration in metres.** `C` is
signed and goes negative under penetration, so `min(C, λ)` selects `C` whenever
any row is penetrated. Verified per-K: `res_raw_max` equals `gap_viol_mm_max`
to full float64 precision in 8 of the 9 shelf cells (the K=24 cell differs at
the third digit, 2.988×10⁻⁵ vs 2.836×10⁻⁵, where a λ term happened to attain
the max on one substep). The paper's "2.79×10⁻² at K=1 → 3.56×10⁻⁶ by K=64" is
therefore a penetration curve in metres — 27.95 mm → 0.0036 mm — and its
"~3×10⁻⁵ threshold" is 0.03 mm of penetration.

(b) **"The complementarity conditions begin to hold" at K≈24 is not supported.**
Only the *gap* side converges there. The *multiplier* side is at its worst at
K=24 (139× λ̄ on the shelf, 309× on the ledge) and clears only at K=64 (shelf) /
K=32 (ledge). The composite is therefore **not monotone**, contrary to "falls
monotonically". The energy crossing at K≈24 coincides with gap convergence, not
with complementarity being satisfied.

The decay trend — the only load-bearing part — survives in both components and
in `res_nd` (7.1×10⁵× shelf, 3.9×10⁵× ledge). §3.2 must be rewritten to the
split form; the raw scalar and its threshold must not survive.

#### (4) P6(a) AVBD drift floor, derived offline (`eq2_utilization.csv`)

The plan anticipated "~10²–10³× the accounting floor"; the data does not support
that range and the measured one is used instead (D5: wording follows numbers).

AVBD positive strict margins, 23 of 24 cells: min 1.370×10⁻³ J, median
3.352×10⁻² J, 21 of 23 at or below 1.574×10⁻¹ J, then 5.353 J and 15.083 J.
The implicit host runs the *same* accounting on the *same* scenes and never
produces a positive margin; its margins span −1.806×10⁻¹ … −5.743×10⁻⁴ J, so
the tightest slack that accounting ever resolves is **5.743×10⁻⁴ J**.

Ratios to that floor: min **2.4×**, median **58×**, the 21-cell bulk up to
**274×**, and the two outliers 9.3×10³× and 2.6×10⁴×. Float64 accumulation noise
on these energy scales (10²–10³ J over ~10⁴ substeps) is ~10⁻⁹ J, six orders
below the smallest AVBD overdraft. **Verdict: small but real — not FP noise.**
The honest printed form is "2–270× the tightest slack the same accounting
resolves on the never-overdrawing implicit host", NOT "10²–10³×".


