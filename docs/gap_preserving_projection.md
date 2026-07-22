# Gap-preserving passivity projection — implementation + first results

> **Post-MIG follow-up.** Not in the MIG 2026 short paper, not in any frozen
> number, **default OFF**. Built and measured 2026-07-22.
> Code: `dcr/avbd/_solver/passivity.py` (`quasi_static_split`,
> `largest_feasible_prefix`, `gap_preserving_projection`), wired opt-in at
> `solver_xpbd.py` via `sol._psv_gap_preserving = True`.
> Tests: `tests/avbd_native/test_gap_preserving.py` (31).
> Probe: `benchmarks/paper_eval/x1_passivity/probe_gap_preserving.py`.

## The problem

The shipped governor scales the whole modal state radially,
`(q, q̇) ← γ(q, q̇)`. That shrinks the load-bearing sag `U_y·q` that resting
bodies stand on, lifting the support surface into them without re-solving
contact: up to **21.6 mm** of penetration, 72 % of the board thickness
(paper §3.3, Table 2). Two earlier successors were probed and gated NO-GO
(R8, 2026-07-19): band-selective was effective but **infeasible in up to 37.8 %**
of clamp substeps; deviation-referencing was feasible but only improved the
worst case **÷1.1**.

## The mechanism

The excess energy and the displacement we must not disturb live in nearly
disjoint directions (99.6 % of the injected energy is in the stiff cluster,
which barely moves the surface). So project along the directions the contacts
**cannot see**, instead of radially.

With `d = U_c q` the displacements the active rows observe, the minimum-elastic-
energy state realizing the same `d` is

```
q_qs = K⁻¹U_cᵀy,   (U_c K⁻¹ U_cᵀ) y = d,   E_qs = ½ dᵀy
```

and the remainder `q_⊥ = q − q_qs` satisfies **`U_c q_⊥ = 0`** (invisible to the
contacts) and **`q_qsᵀ K q_⊥ = 0`** (K-orthogonal). Hence
`E(q_qs + s·q_⊥, s·q̇) = E_qs + s²(E⁺ − E_qs)` — the same degree-2 homogeneity
the shipped γ exploits, so every rung is closed-form:

The precise KKT statement needs an objective. Rung 1 is the solution of the
energy-whitened proximal problem

```
min  ½‖K¹ᐟ²(q'−q)‖² + ½‖q̇'−q̇‖²
s.t. U_c q' = d,   E(q',q̇') ≤ Ē.
```

Without this metric, “the constrained projection” is underspecified.

| rung | condition | action | selected displacement rows |
|---|---|---|---|
| 1 | `E_qs ≤ Ē` | `s = √((Ē−E_qs)/(E⁺−E_qs))` | **preserved exactly** |
| 1b | prefix fits | keep largest λ-ordered prefix (bisection; `E_qs(k)` is monotone) | preserved on kept rows |
| 2 | nothing fits | `β = √(Ē/E_qs)`, `q̇ ← 0` | shrunk by `1−β`, but `β ≥ γ` always |

**The scalar-ledger induction survives.** Its proof only needs the projected state
to land in `{E ≤ E⁻+B}` with the same credit-before-test ordering; it never
constrained the *direction* of projection. If Prop. 4.1 or its lemma explicitly
names radial γ-scaling, that statement/lemma must be revised—the induction itself
is unchanged. Rung 2 is always feasible, so the ladder is unconditional unlike
both R8 variants. With no active rows the whole thing reduces **exactly** to the
shipped radial γ (asserted in the tests): the current governor is the “preserve
nothing” special case.

## Results — full A/B runs, XPBD, relax 0.7, η=1

Not a per-substep counterfactual (the caveat that sank the R8 probe): each arm is
its own trajectory. `probe_gap_preserving.py`, 100 frames + 8 settle.

| cell | worst penetration, radial → gap | median | zero-gap substeps | invariant |
|---|---|---|---|---|
| shelf 4×1 | 21.59 → **4.86 mm** (4.4×) | 1.244 → 0.292 mm | 47.6 % rung 1, 55 rung 1b | holds, both arms |
| shelf 8×2 | 6.43 → **0.50 mm** (12.8×) | 0.214 → 0.012 mm | 77.5 % rung 1, 45 rung 1b | holds, both arms |
| ledge 4×1 | 21.19 → 20.08 mm (1.06×) | 0.078 → 0.052 mm | 39.1 % rung 1, 51 rung 1b | holds, both arms |
| ledge 8×2 | 4.08 → **0.93 mm** (4.4×) | 0.070 → 0.016 mm | 99.4 % rung 1 | holds, both arms |

Peak modal energy is unchanged-to-slightly-lower in every gap arm (e.g. shelf
8×2: 29.56 → 29.0 J), so the improvement does not come from storing more energy.
Rung-2 fallbacks: 2 substeps total across all four cells; numerical fallbacks: 0.

**The mechanism is exact where it applies.** Splitting the clamp-induced
violation by row (pre-rung-1b measurement): rung 1 induced **0.0000 mm** on both
active and inactive rows, in every cell. *All* residual penetration comes from
the rungs that cannot preserve the surface.

## Why ledge 4×1 barely moves — and why that is the correct behavior

At its two worst substeps the quasi-static energy of the observed surface is
**199× and 148× the entire ceiling** (`E_qs = 6.5×10⁴ J` against a 325 J budget;
not one row of eight is affordable, so both fall to rung 2). The surface being
"preserved" at those instants is *itself* the injection artifact — a 65 kJ
deformation in a scene whose measured rigid supply is three orders smaller. No
bound-respecting projection can keep it; the energy does not exist.

The median substep in the same cell has `E_qs/ceiling = 0.66` (affordable), which
is why the median violation still improves. So the honest characterization is:
**the projection removes clamp-induced penetration wherever the observed surface
is fundable, and degrades to the shipped behavior exactly where the surface is
itself spurious.** That is the right structure — but it means "21.6 mm" does not
become "0 mm" in the adversarial cell, and the paper's §3.3 limitation stands as
written for that regime.

## One implementation subtlety worth keeping

The first version accepted any post-projection energy within `max(tol, 1e-9·Ē)`
of the ceiling. Analytically the rungs land *at* the ceiling, but lstsq roundoff
in the split left a per-substep residue that accumulated to **1.06×10⁻⁹ J** over
105 clamps on shelf 4×1 — five orders above the shipped projection's 1×10⁻¹³ J
floor, and enough to trip `PassivityLedger.holds()`. Not real injection, but the
bound's exactness is the whole selling point. Landing the result on the ceiling
with one radial micro-scale (`γ_fix ≈ 1 − 10⁻⁹`) restores it: the gap arm now
sits at **1.07×10⁻¹⁴ J**, better than radial's 9.9×10⁻¹⁴ J. A *large* correction
would mean the split is wrong, so that case is recorded as the fallback rung
rather than silently applied.

## Regression status

- `tests/avbd_native/` — **233 passed**, 30 skipped (unchanged).
- `verify_paper_numbers.py --tex paper/main_short.tex` — **32/32**.
- The radial arm of the probe reproduces the frozen Table 2 clamp counts exactly
  (107/108, 171/216, 97/108, 178/216) and the 21.589 mm worst case, confirming
  the default path is untouched.

## Open items before this could be a claim

1. **Coverage** — four cells, one host (XPBD), one relaxation, one machine. The
   AVBD/impulse hosts and relax 1.0 are unmeasured.
2. **Corrective impulse and λ variance** are not yet measured for the gap arm
   (Table 2's columns (b)/(c)); the expectation is that they fall with the
   penetration, but that is untested.
3. **Rung 2 refinements** — one-sided (inequality) constraints, and preserving a
   λ-weighted SVD subspace rather than whole rows, both target exactly the
   ledge 4×1 regime. Neither is built.
4. **Active-set chatter** across substeps is not characterized.
5. **Cost** — the split adds an m×m solve per clamp substep (m = active rows,
   ≤ 8 observed). Unmeasured; the shipped γ is a scalar.
6. **Gross-supply exposure** (the 102–118 % opposite-channel diagnostic) may grow
   if preserved sag springs back and is re-credited. Unmeasured.

---

## 2026-07-22 (later): promoted to the paper's method

The projection is now `\eqref{eq:gamma}` in `paper/main_short.tex` §4 and the
subject of Table 2, not a Limitations footnote. What changed since the section
above was written:

1. **All three hosts carry it** (`solver_xpbd.py`, `solver_6dof.py` ×2 call
   sites, `solver_impulse.py`), so §4's "runs identically in all three hosts"
   is true. The AVBD/impulse call sites project the *stacked* `[q; a_cargo…]`
   state, since their ledgers span cargo blocks; cargo carries no support-row
   column, so it lands in the contact-invisible remainder and is scaled.
2. **The active set is now gap-based, not λ-based** (`active_rows_from_gaps`):
   a row is active iff its gap has closed, priority `−C`. Two of the three
   hosts expose no host-side multiplier, and the multipliers are not the same
   object across hosts, so λ could not be the shared criterion. This changed the
   numbers (better on ledge, worse on shelf) — the λ variant's figures in the
   section above are superseded.
3. **The ungoverned control arm** is what licenses the paper's attribution
   claim. Full numbers, and the two pre-existing paper errors this pass turned
   up, are in `mig2026_results_ledger.md` §R8c.

Headline as it now stands: whole-state scaling amplifies the truncated solve's
own penetration by 2.4–47.6×; preserving the observed surface, by 1.0–6.3×; at
converged budgets no clamp fires at all and all three arms are identical. The
corrective transient does **not** improve, and ledge 4×1 remains unfixable by
any bound-respecting projection (its observed surface costs 340× the ceiling).

## Reviewer-safe interpretation and remaining validation

What is proved:

- Rung 1 preserves `U_c q` for the selected rows and lands inside the same scalar
  modal-energy ceiling.
- Empty `U_c` reduces to the original radial governor.
- Rung 2 is always energy-feasible, and on the selected displacement vector
  retains at least the common fraction retained by radial scaling (`β ≥ γ`).

What is not proved:

- “Zero penetration” globally. Rung 1 causes zero **projection-induced position-
  gap change on its selected rows**; pre-existing solve residuals and omitted or
  misclassified rows remain.
- Contact validity. The current policy scales `q̇`, so it does not preserve
  `U_c q̇`, complementarity, the solved contact impulse, or the next-substep
  corrective transient.
- Optimality of rung 1b. A multiplier- or gap-prioritized prefix is a
  lexicographic row-selection policy, not the all-row KKT solution or a proof of
  penetration/impulse optimality.
- Momentum preservation merely because only modal coordinates are written. That
  requires the retained basis to be mass-orthogonal to the relevant rigid
  translation/rotation modes (and is not meaningful for a fixed support in the
  same way as a free body).

Before using “contact-consistent” as a method claim, measure post-projection
`U_c q̇`, complementarity, next-step impulse, active-set churn, and trajectory
error against the trusted high-budget/FEM reference. A natural ablation is the
analogous kinetic split: preserve the minimum-norm contact-visible velocity and
scale only its nullspace component where the enlarged mandatory energy floor is
affordable. Until then, “selected-height-preserving scalar-energy governor” is
the accurate name.
