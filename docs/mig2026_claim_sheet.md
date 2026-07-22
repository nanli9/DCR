# MIG 2026 Short Paper — Frozen Claim Sheet (Stage A)

Authority: `docs/mig2026_practitioner_diagnostic_rewrite_plan.md` §4 (claim
hierarchy), §8 (count integrity), §11 Stage A. This sheet is the hard filter for
every sentence the rewrite writes: **every claim maps to exactly one frozen
evidence source**; a claim with no source is deleted or explicitly labelled
motivation/hypothesis. Frozen sources live under
`benchmarks/paper_eval/x1_passivity/out/` (CSV + manifest) and are transcribed
with commit/machine in `docs/mig2026_results_ledger.md`.

Status legend: **[F]** frozen (evidence exists, in ledger); **[B]** pending
Stage B (must be produced and frozen before the dependent sentence is written);
**[L]** literature (citation, not our measurement).

---

## 0. Frozen thesis (plan §1)

Adding 16–24 global modal coordinates to an existing fixed-budget XPBD
rigid-body host is an attractive alternative to converting a stiff prop into a
full nodal/tet deformable, **but a direct two-way rigid–modal contact row is not
automatically energy-safe under a small fixed local-iteration budget.** The
tested stiffness-aware implicit/velocity realization is the preferred *observed
control* when a different contact architecture is available; a fixed XPBD host
needs a direct audit of its shared-row coupling, basis, and iteration budget,
with a storage guardrail only as a last resort.

The paper is a **failure characterization + operating guide**, not a solver
ranking and not a governor method paper.

---

## 1. Leading claims (plan §4) — each with its one frozen source

### C1 — Compact modal state is a credible low-cost XPBD workflow
**Claim.** Adding a compact modal state (≈10–24 global amplitudes) to an XPBD
rigid host is a credible low-cost workflow for stiff, small-displacement
response, distinct from a full-space XPBD deformable.
- Ranks 16/16/24 (shelf/ledge/table). **[F]** `scene_spec.csv` (E-C9e), ledger
  §R3.1 / §E-C9e; paper Table 1.
- Same-operator FEM fidelity: peak-deflection ratio ladder
  0.38→0.54→0.79→0.88 as `h` refines 1/120→1/960; ring frequency 78.0 vs
  78.3 Hz (0.4%); far-field Spearman ρ=0.89, no fitted attenuation. **[F]**
  `benchmarks/paper_eval/x3_ground_truth/out/ledge_convergence.csv`,
  `ledge_falloff.csv`; ledger §A0 / §R4 ring note.
- Modes vs full-space tradeoff (state size, precompute, dense shared-`q`). **[L]**
  `peng2024reduced`, `zheng2011`, `hauser2003`, `james2002dyrt`.
- **Rewrite action:** first paragraph; distinguish from full-space XPBD. Do NOT
  import the 13.6× full-FEM speed number (different config — plan §3, nonclaim).

### C2 — A direct two-way row in the tested XPBD implementation injects catastrophically
**Claim.** In **our tested XPBD implementation**, a direct two-way contact row
can inject catastrophic modal energy at fixed low local-iteration budgets.
- 24-cell sweep, 3 scenes × relax {0.7,1.0} × 4 budgets. Incident-ratio
  R>1 in **8/24** (XPBD), 2/24 (AVBD), 0/24 (impulse). **[F]** `solver_matrix.csv`,
  ledger §E-S1b.
- Strict Eq. (2) ledger-margin violated in **9/24** (XPBD), 3/24 (AVBD), 0/24
  (impulse). **[F]** `eq2_utilization.csv`, ledger §R1. **KEEP 8/24 AND 9/24
  DISTINCT** (plan §8; two different metrics).
- Worst overdraw 4.4×10⁷ J (ledge, relax 1.0, 4×1; peak modal 4.44×10⁷ J vs
  incident 371 J → R=1.2×10⁵). **[F]** `eq2_utilization.csv` / `solver_matrix.csv`.
- Visible launch (books thrown >their height). **[F]** `fig_teaser.pdf`,
  activation_trace.csv.
- Neighborhood robustness of the headline cells. **[B] E1b** — required before
  the abstract/caption magnitudes are rounded and the "not a knife-edge" claim is
  finalized.
- **Rewrite action:** central empirical result; then its E1b spread + supported
  precision. Implementation-scoped throughout.

### C3 — The amplification is finite-iteration truncation of the shared modal coupling
**Claim.** In the controlled shelf/ledge ladder the amplification is *associated
with* finite-iteration truncation of the shared modal contact coupling.
- Six-order decay with K toward the implicit reference (2.96×10⁴ at K=1 →
  0.300 at K=32; ref 0.2735). **[F]** `k_convergence.csv`,
  `k_convergence_ledge_worst.csv`, ledger §E-S2/§R4.
- Gap converges (27.9 mm→3.6 µm by K=64) but separated-row multiplier clears a
  rung later (rises 84×→139× through K=24, →0 at K=64). **[F]**
  `complementarity_residual.csv` (+`_nd`,`_nd_ledge`), ledger §R3.4.
- Self-convergence stops short of the reference (XPBD plateaus 0.2996 by K≈64;
  residual 2.6×10⁻² is a fixed point; trajectory 34% of ref peak). **[F]**
  `selfconvergence.csv`, `selfconvergence_long.csv`, ledger §R4.
- Warm-start control: footprint unchanged (same 8/24, worst 1.20×10⁵), worse at
  4×1 (3.1×). **[F]** `warm_start_ablation.csv`, ledger §E-C9g.
- Equal-row-count control (see C4). **[F]** `substep_sweep.csv`.
- **E6a-1 causal ablation** decides whether the sharper cause is serial
  shared-row coupling. **[B] E6a-1** — do NOT pre-commit to a mechanism until
  frozen; a one-cell result is a causal probe, not a cure (plan §4 C3, §9 E6a).
- **Rewrite action:** "truncation pathology" vs "different converged fixed point"
  line stays explicit. Cite `wei2026earlyterm` for the under-convergence-injection
  *observation* (it is prior art — nonclaim).

### C4 — Budget allocation and basis selection matter
**Claim.** Iterations outperform substeps for this shared row, and removing the
stiffest cluster reduces but does not guarantee safety.
- 32 row-evals as iterations (K=32,S=1): R=0.300, Eq. (2) holds; as substeps
  (K=4,S=8): R=3.13, +481 J. **[F]** `substep_sweep.csv`, ledger §R3.3.
- Warm-start unchanged (C3). **[F]** `warm_start_ablation.csv`.
- Band-limit / stiff-cluster ablation: excluding the stiff cluster cuts shelf
  4×1 ratio 6333→22.1 (+584 J still overdrawn); 6/8 injecting cells still
  overdraw (worst ledge 4×1 +1.24×10⁶ J). **[F]** `band_limit_sweep.csv`,
  `robustness_ablation.csv`, ledger §E-C9/§E-C9g.
- Optional stronger basis rule (cutoff ladder). **[B] E3 (stretch)** — use only
  if a cross-scene frontier appears; else keep the band ablation.
- **Rewrite action:** operating guidance, NOT a universal formula. One-cell
  results are causal probes.

### C5 — The cumulative radial projection guarantees the scalar bound but is an emergency envelope
**Claim.** A cumulative radial projection guarantees the printed scalar storage
inequality (Prop.) but is an emergency containment envelope, not accurate contact.
- Proposition (unconditional, up to accounting tol). **[F]** Prop. in §2; proof
  in-paper; 90 governed cells at roundoff floor, worst margin 1.1×10⁻¹³ J
  (`eq2_utilization.csv` governed rows).
- Penetration up to 21.6 mm (72% board thickness) at 4×1; 9.8 mm at deployed
  1×8/2×4. **[F]** `projection_validity.csv`, `projection_validity_deployed.csv`,
  ledger §E-S3/§R5.4; paper Table 2.
- Worse trajectory (L∞ 33%→71% of ref peak governed). **[F]**
  `governed_accuracy.csv`, `governed_accuracy_1x8.csv`, ledger §R5.1b.
- Corrective impulse up to 8.9×, multiplier variance up to 62×. **[F]**
  `projection_validity.csv`, ledger §E-S3.
- **Rewrite action:** move AFTER the diagnostic (page 5); guarantee and physical
  cost in the SAME paragraph. Never call it contact correction / passivity.

---

## 2. Explicit nonclaims (plan §4) — hard filter, binding

The rewrite must NOT claim:
1. all XPBD implementations exhibit the measured failure;
2. modal reduction itself is energy-unsafe;
3. AVBD or impulse methods are passive as solver classes;
4. equal row evaluations are equal wall-clock cost;
5. the cumulative ledger is contact-port passivity, total-energy stability, or a
   physical energy audit;
6. the governor is preferable to the tested implicit/velocity path or an
   E6a-validated shared-block path;
7. the governor preserves contact, trajectory accuracy, or the FEM solution;
8. a quantitative modal/full-space speed advantage unless measured in the same
   configuration;
9. that the configured XPBD modal restoring step is explicit (it uses **implicit
   midpoint**);
10. a general implicit-block recommendation from a one-scene/one-budget ablation.

Additional binding items carried from the current `main_short.tex` header +
memory `[[novelty-recheck-2026-07-18]]`, `[[paper-transcription-equivalence-framing]]`:
- the contact row / gap / deformed contact point is a **transcription** of the
  Zheng–James velocity-level law, never claimed as ours (narrower: normal-only,
  e=0);
- two-way coupling / momentum consistency / "first modal DOFs in XPBD" are NOT
  claimed ("as contact DOFs" if the point must be made);
- the under-convergence-injection *observation* is `wei2026earlyterm`'s, cited;
- the acronym "DCR" is banned (cite `coevoet2020distant` or "the one-way
  baseline").

---

## 3. Terminology rules (Stage A EXIT GATE)

These are checked by grep after every Stage D/E edit:

- **"XPBD" alone** may name the solver *family/host architecture* and prior work
  (`macklin2016xpbd`). Where a **measured failure or result** is attributed, it
  must read "our tested XPBD implementation" / "the tested position-based host" /
  "this implementation" — never a bare-family attribution that reads as "all
  XPBD". (nonclaim 1)
- **"passivity" / "passive"** is reserved for (a) the literature it names
  (time-domain passivity control, port passivity) and (b) explicitly negated
  statements ("this is **not** contact-port passivity"). The scene-wide scalar
  ledger is a **cumulative gross-loss-funded modal-storage bound**, never
  "passivity". (nonclaim 5)
- **"explicit modal integration"** is banned for the baseline: it uses
  **implicit midpoint**. (nonclaim 9)
- **"converged"** only next to a checked criterion (K=500 reference, ratio
  spread ≤ checked value). Term A = implicit oracle; Term B = XPBD
  self-reference — never conflated.
- **Count integrity:** 8/24 = incident-ratio (R>1) violations; 9/24 = strict
  Eq. (2) ledger-margin violations. Never substitute one for the other.
- **Magnitudes** (incl. 4.4×10⁷ J) rounded to E1b-supported precision, not
  five/six-digit single-run maxima. (Stage B / E1b gates this.)

---

## 3a. E6a vocabulary lock (plan §9 E6a — locked before any ablation code)

Three variables were historically conflated as an "implicit modal block." They
are distinct and must never be merged in prose or experiment:

1. **Free/modal-restoring time integrator.** The baseline XPBD host ALREADY uses
   **implicit midpoint** (`SolverXPBD._modal_symplectic=True` in the paper
   config). Never call it "explicit modal integration" (nonclaim 9). This
   variable is held FIXED in every E6a ablation.
2. **Modal effective weight in a contact update.** XPBD uses an explicit per-mode
   contact compliance `1/(H_ii h²−1)`; the impulse host uses the implicit
   operator `(M+hD+h²K)⁻¹`. This is the E6a-2 counterfactual (feasibility-gated).
3. **Serial row-wise vs joint block treatment** of support contacts sharing the
   one modal vector `q`. XPBD default = serial (`_support_block=False`, loops
   `_project_support` per row); the alternative = `_support_block=True`
   (`_project_support_block`, condenses all active support rows). **This is
   E6a-1.**

E6a-1 changes ONLY variable 3, holding 1, 2, timestep/substeps, iteration
budget, compliance, relaxation, warm-start, contact-row definitions, and all
non-support constraints fixed. Disclosure required (plan §9): `_support_block`
preserves the active-row compliant fixed point but uses a **diagonal
rigid-body block approximation** and a **different convergence path** — it is an
ablation, not a behaviour-identical toggle. A one-cell result is a **causal
probe**, never a "block solve fixes XPBD" claim; a recommendation-changing result
must repeat in a 2nd scene + 2nd budget.

## 4. Claim → source coverage check (self-audit)

| Claim | Primary frozen source | Status | Pending dep. |
|---|---|---|---|
| C1 ranks | `scene_spec.csv` | F | — |
| C1 fidelity | `x3/ledge_convergence.csv`,`ledge_falloff.csv` | F | — |
| C2 8/24 ratio | `solver_matrix.csv` | F | — |
| C2 9/24 margin | `eq2_utilization.csv` | F | — |
| C2 4.4e7 J | `eq2_utilization.csv` | F | E1b: max of 2.2–4.5e7 J neighborhood |
| C2 robustness | `e1b_neighborhood.csv` | **F** | done: 16/16 inject, log-spread ≤0.7 |
| C3 K ladder | `k_convergence*.csv` | F | — |
| C3 gap/mult | `complementarity_residual*.csv` | F | — |
| C3 self-conv | `selfconvergence*.csv` | F | — |
| C3 warm-start | `warm_start_ablation.csv` | F | — |
| C3 mechanism | `e6a1_block_condensation.csv` | **F** | E6a-1: block ≠ cure; serial converges |
| C4 32×1/4×8 | `substep_sweep.csv` | F | — |
| C4 band | `band_limit_sweep.csv`,`robustness_ablation.csv` | F | — |
| C5 prop/90 cells | `eq2_utilization.csv` (gov rows) | F | — |
| C5 penetration | `projection_validity*.csv` | F | — |
| C5 trajectory | `governed_accuracy*.csv` | F | — |
| accounting audit | `e1_accounting_audit.csv` | **F** | done: floor ≤1e-3 J ≪ 6.7 J |

**Stage-B evidence status (updated 2026-07-21):**
- **E1 (accounting audit) — FROZEN.** AVBD/impulse floor ≤ 10⁻³ J, 3–4 orders
  below the 6.7 J AVBD effect (incl. the dinner scene where it lives). The
  cross-host control claim STANDS; no narrowing required.
- **E1b (C2 robustness) — FROZEN.** All four injecting headline cells inject in
  16/16 perturbations; equal-row inversion + scene-dependence robust; the 4.4e7 J
  headline is the max of a 2.2–4.5e7 J neighborhood. Round magnitudes to this.
- **E6a-1 (C3 mechanism) — FROZEN.** Block condensation does NOT cure the
  injection (comparable at 4×1, worse at every higher budget where the serial
  path converges/holds). Refutes "block solve fixes XPBD"; confirms the
  truncation thesis (serial converges with iterations). C3 stays "associated with
  finite-iteration truncation of the shared coupling"; recommendation = iterate
  the serial path, do not switch to block. Reproduced over 2 scenes × 4 budgets.
- **E6a-2 (stiffness-aware contact weight) — DEFERRED (stretch).** Feasibility
  gate not yet run; requires deriving a consistent position-level discrete update
  before any measurement (plan §9). Not on the committed-core critical path; the
  E6a interpretation is reported from E6a-1 alone, with the E6a-2 column left
  explicitly un-inferred (plan §9 rule).

---

## 5. Unsourced material in the current draft → demote or delete (Stage E)

- Device-resident GPU timing paragraph (§sec:cost tail): monitor-only, does not
  time the governed path → remove unless a retained claim needs it (plan §8).
- "production-like"/"deployed" wording: define concretely or remove (plan §8).
- Broad "prefer AVBD/implicit" conclusion → replace with the ordered,
  implementation-specific decision rule (plan §5).
