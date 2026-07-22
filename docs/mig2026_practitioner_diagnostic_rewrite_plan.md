# MIG 2026 Short-Paper Rewrite Plan

## Practitioner diagnostic: fixed-budget XPBD with modal contact DOFs

Status: structural plan only. This document does not authorize or contain a
manuscript, solver, benchmark, or video change.

## 1. Recommended paper identity

### One-sentence thesis

Adding 16--24 global modal coordinates to an existing XPBD rigid-body host is
an attractive alternative to converting a stiff prop into a full nodal/tet
deformable, but a direct two-way rigid--modal contact row is not automatically
energy-safe under a small fixed local-iteration budget. The tested stiffness-
aware implicit/velocity realization is the preferred observed control when a
different contact architecture is available; a fixed XPBD host needs a direct
audit of its shared-row coupling, basis, and iteration budget, with a storage
guardrail only as a last resort.

### Reader contract

The paper is **not** asking a reader to choose XPBD over the tested implicit
realization. It addresses a developer who has already chosen an XPBD rigid-body
architecture for contacts and joints and now wants low-cost vibration without a
full-space deformable solve.

The first page must let a reviewer answer all four questions:

1. Who is the paper for? An existing fixed-budget XPBD rigid-body/contact host.
2. Why use modes? A small precomputed state for stiff, small-displacement
   deformation and vibration instead of many nodal coordinates and constraints.
3. Why not use the impulse realization? Use the tested realization when the
   architecture permits; it is the preferred observed control, not an inferior
   baseline or a theorem about every impulse solver.
4. When is the governor relevant? Only when the host is fixed, sufficient
   convergence or an E6a-validated shared-block path is unavailable, and
   containment is worth measured contact error.

### Candidate titles

Preferred:

> **When Modal Contact Rows Fail in Fixed-Budget XPBD**

More descriptive alternative:

> **Modal Energy Injection in Fixed-Budget XPBD Rigid--Modal Contact**

If the cross-implementation comparison remains in the title, qualify it as a
control rather than the subject:

> **A Fixed-Budget XPBD Failure in Rigid--Modal Contact, with Implicit and
> Augmented-Lagrangian Controls**

Avoid a title centered on “three solvers” or the “cumulative storage bound”; both
recreate the questions “which solver wins?” and “why is this clamp needed?”

## 2. Diagnostic versus method-paper decision

### Recommended critical path

Proceed as a **failure characterization plus operating guide**. This is the
strongest claim supported by the current short-paper evidence and already
cleared a weak-accept bar for half of the independent reviewer panel.

A diagnostic short paper is substantial if it provides:

- a credible practitioner workflow;
- a surprising and consequential failure;
- mechanism-level localization rather than a single failure screenshot;
- evidence that ordinary confounders do not remove it;
- an actionable decision rule; and
- complete reproducibility material.

The diagnostic critical path also includes two targeted soundness controls:
E1b tests whether the headline cases persist in a predefined local perturbation
neighborhood, and E6a-1 changes only the shared-row coupling strategy inside the
tested XPBD host. These controls strengthen causal attribution without turning
the submission into a new solver paper.

### Method-paper stop/go gate

Do not promote the present radial state scaling into the primary method. First
complete the diagnostic E6a ablations in section 9. In particular, do not call
the current XPBD path “explicit modal integration”: its configured free/modal-
restoring step already uses implicit midpoint. Shared-row block condensation,
stiffness-aware contact weighting, and the free modal time integrator are three
different variables.

Open a method-paper branch, E6b, only if the diagnostic ablations motivate a
mathematically consistent new hybrid contact formulation rather than a switch
between already available implementation paths.

The method route is a **go** only if all of the following hold:

1. The hybrid formulation has a concrete remaining integration/coupling problem
   or a meaningful cost disadvantage at matched wall-clock budget.
2. A new method resolves that problem rather than merely clipping the realized
   state.
3. It improves contact validity and trajectory accuracy over the current
   governor while preserving a defensible energy property.
4. Its advantage survives at least two scenes and more than one budget.

If E6a-1 or a consistent E6a-2 is easy, faster, and more accurate, retain the
diagnostic paper and recommend that *tested path* within its measured scope. A
negative result for the governor is still useful; hiding the obvious alternative
is not.

## 3. Technical motivation: modes versus full-space XPBD

| Choice | Runtime state | Best use | Main cost/limitation | Role in this paper |
|---|---|---|---|---|
| Full nodal/tet XPBD deformable | Many vertex coordinates and local internal constraints | Large/local/nonlinear deformation | More online DOFs and constraints; mesh-dependent cost | Credible alternative, not a baseline the paper claims to dominate |
| Rigid frame plus modal state | Six rigid DOFs plus approximately 10--24 global amplitudes | Stiff props, small displacement, ringing, fixed content | Precomputation and linear/basis truncation; dense contact coupling through shared `q` | Target practitioner workflow |
| Tested implicit/velocity realization | Same compact modal state; stiffness-aware modal contact weight | Solver architecture is flexible | Different time discretization and velocity-level contact semantics | Preferred observed control; not a solver-class theorem |
| XPBD shared-row block condensation | Same XPBD host and implicit-midpoint modal restoring step; active support rows gathered through shared `q` | Fixed host can change its row solve | Different convergence path; current path uses a diagonal rigid-body block approximation | E6a-1 causal ablation and possible in-host mitigation |
| XPBD plus cumulative governor | Existing XPBD path plus ledger/projection | Emergency containment in an immutable host | Can suppress legitimate motion and violate contact | Last-resort fallback only |

The important numerical observation is not merely “16 is smaller than thousands.”
Every support contact touches the same global modal vector, so the row graph is
dense on `q`; many local nodal constraints are numerous but sparse. The paper
must explain why a small reduced state can still converge poorly under truncated
local projections.

Use the existing same-operator result as the fidelity anchor: the retained modal
state recovers the low-frequency ledge response with approximately 0.4% frequency
error and spatial rank correlation 0.89. Do not import the separate 13.6x
full-FEM speed result without verifying that its scene and timing protocol match
the short-paper configuration.

## 4. Claim hierarchy

### Claims that should lead the paper

| ID | Defensible claim | Current evidence | Rewrite action |
|---|---|---|---|
| C1 | Adding a compact modal state to an XPBD rigid host is a credible low-cost workflow for stiff, small-displacement response. | Ranks 16/16/24; same-operator FEM frequency and spatial agreement; prior modal/reduced-XPBD literature. | Put in the first paragraph; distinguish it from full-space XPBD. |
| C2 | A direct two-way row in the **tested XPBD implementation** can inject catastrophic modal energy at fixed low local-iteration budgets. | Three scenes, two relaxations, four schedules; 8/24 incident-ratio violations and 9/24 strict ledger-margin violations; worst overdraw 4.4e7 J; visible launch. | Make this the central empirical result, then report its E1b neighborhood robustness and supported precision. |
| C3 | In the controlled shelf ladder, the amplification is associated with finite-iteration truncation of the shared modal contact coupling. | Six-order decay with `K`; gap convergence; high-iteration same-path reference; warm-start control; equal-row-count comparison. | Use E6a to decide whether the sharper cause is serial shared-row coupling, stiffness-aware contact weighting, both, or neither; do not pre-commit to one. |
| C4 | Budget allocation and basis selection matter: iterations outperform substeps for this shared row, and removing the stiffest cluster reduces but does not guarantee safety. | `K=32,S=1` versus `K=4,S=8`; warm-start unchanged; current band ablation. | Present as operating guidance, not a universal formula. |
| C5 | A cumulative radial projection guarantees the printed scalar storage inequality but is an emergency envelope, not accurate contact. | Proposition; all governed cells; 21.6 mm penetration; worse trajectory; corrective impulse and multiplier variance. | Move after the diagnostic and state its cost in the same paragraph as its guarantee. |

### Explicit nonclaims

The rewritten paper must not claim:

- all XPBD implementations exhibit the measured failure;
- modal reduction itself is energy-unsafe;
- AVBD or impulse methods are passive as solver classes;
- equal row evaluations are equal wall-clock cost;
- the cumulative ledger is contact-port passivity, total-energy stability, or a
  physical energy audit;
- the governor is preferable to the tested implicit/velocity path or an
  E6a-validated shared-block path;
- the governor preserves contact, trajectory accuracy, or the FEM solution;
- a quantitative modal/full-space speed advantage unless measured in the same
  configuration;
- that the configured XPBD modal restoring step is explicit; or
- a general implicit-block recommendation from a one-scene/one-budget ablation.

## 5. Practitioner decision rule

The conclusion, abstract, and one compact page-6 box should all encode the same
order of operations:

1. **Choose the deformation representation.** Use full-space XPBD for large,
   local, or strongly nonlinear deformation; use modes for compact stiff-body
   response and vibration.
2. **If the contact architecture is flexible, prefer the tested stiffness-aware
   implicit/velocity realization.** It is the cleanest observed control in this
   study, but the recommendation remains implementation-specific unless E6b
   supplies matched, replicated evidence.
3. **If the XPBD host is fixed, audit the shared modal block before tuning around
   it.** Test block condensation if the host supports it and recommend that path
   only if E6a-1 repeats beyond its smoke case. Then select the basis and local
   iteration count together: remove unresolved stiff modes, spend the local
   budget on iterations rather than assuming substeps are interchangeable, and
   audit gap, separated-row multiplier, and energy behavior.
4. **If the fixed host still cannot converge, use the cumulative governor only
   as containment.** Surface the penetration/trajectory cost to the application;
   do not call the result physically corrected.

Do not write “increase the budget until fully converged.” The existing evidence
supports a more specific statement: increase relevant local iterations and verify
both sides of complementarity; more substeps at the same row-evaluation count did
not reproduce that outcome.

## 6. Six-page body storyboard

### Page 1 — Audience, temptation, and visible failure

Content:

- New title and a 180--220 word abstract.
- Teaser showing the existing XPBD host plus a small modal vector, then the
  ungoverned failure against the high-iteration XPBD self-reference.
- First introduction paragraph: why a practitioner uses modes instead of a full
  nodal/tet body.
- Second paragraph: the global shared-modal coupling trap and exact paper scope.

The page must say before any equations:

> If solver architecture is unconstrained, our evidence favors the tested
> stiffness-aware velocity-level realization; our target is the existing
> fixed-budget XPBD host.

### Page 2 — The tempting extension and experimental contract

Content:

- One diagram/equation for rigid frame plus modal amplitudes in the shared
  unilateral row.
- One sentence explaining why all support rows touch the same `q` block.
- Modal energy definition and the two diagnostics, clearly separating incident
  ratio from the ledger margin.
- Compact protocol: three scenes, ranks, schedules, relaxation, same row/camera/
  initialization.
- A compressed four-row implementation-difference table or prose disclosure.

Related work should be one compact paragraph covering rigid XPBD, modal
deformation/contact, reduced XPBD, and energy-control precedent. Move the detailed
bilateral/passivity/FEPR distinctions to the supplement unless needed to defend a
specific claim.

### Page 3 — What fails, and what the controls establish

Content:

- Compact cross-implementation control: tested XPBD, AVBD, and implicit result.
- Headline counts and magnitudes, emphasizing implementation scope.
- E1b neighborhood-robustness summary and appropriately rounded headline
  magnitudes.
- Warm-start control.
- Explanation that AVBD/impulse are controls, not a solver-family ranking.

Visual:

- Prefer one XPBD-centered heatmap plus a small three-implementation summary
  strip (`violating cells`, `worst margin`, `worst R`).
- Put the complete 72-cell two-metric heatmap and all host-table fields in the
  reproducibility artifact.

### Page 4 — Why the failure appears and what users should change

Content:

- Iteration-only convergence ladder and direct gap/separated-row diagnostics.
- Equal-row-evaluation `32x1` versus `4x8` contrast.
- Warm-start conclusion in one sentence.
- E6a-1 shared-row block-condensation result; label a one-case result as a
  causal probe, not a general cure.
- Frequency/basis result, preferably the new cutoff ladder described below.
- Clear line between truncation pathology and the different converged fixed point.

Visual:

- A three-panel operating-envelope figure:
  1. energy/margin versus `K`;
  2. complementarity residuals versus `K`;
  3. cutoff frequency versus minimum safe `K`, or the current band ablation if
     no stable frontier emerges.

This is the page that makes the diagnostic academically substantial.

### Page 5 — Last-resort guardrail and its price

Content:

- Introduce the cumulative storage inequality only now, after its deployment
  corner is established.
- Credit--test--scale--debit loop in compact pseudocode.
- Reduce the proof to the induction invariant and one paragraph; put extended
  algebra and all 90 rows in the supplement.
- Place guarantee and physical cost side by side.

Visual/table:

- A compact contact-cost table with maximum penetration, corrective impulse,
  multiplier variance, and trajectory-direction result.
- Explicit label: “Accounting guarantee; not contact correction.”

### Page 6 — Decision guide, scope, and conclusion

Content:

- One short paragraph on same-operator FEM fidelity: why modes are meaningful in
  the targeted small-displacement regime.
- Only the runtime facts needed for deployment; remove monitor-only GPU details
  unless they support a retained claim.
- Practitioner decision box from section 5.
- Compact limitations: implementation-specific, normal-only/e=0, global and
  recyclable supply, no governed FEM/device validation.
- Conclusion written as an ordered recommendation, not a solver ranking.

End on the practical warning:

> A low-dimensional modal extension is cheap in state size, not automatically
> easy for a truncated local contact solve.

Page 7 remains references only.

## 7. Working abstract blueprint

Use six sentences, each with one job:

1. Existing XPBD rigid-body host plus the modal-versus-full-space motivation.
2. The dense shared-modal contact row and finite-budget risk.
3. Experimental protocol and implementation-specific scope.
4. XPBD magnitude plus truncation/equal-row/warm-start/band evidence.
5. Preferred practitioner response: the tested implicit/velocity path when the
   architecture is flexible; otherwise the E6a-supported shared-block option,
   iterations, and a verified basis in a fixed XPBD host.
6. Last-resort governor, exact narrow guarantee, and severe contact cost.

A working north-star version is:

> Rigid-body XPBD engines already solve contacts and joints, and adding a small
> modal state is an attractive way to give stiff props low-cost vibration without
> introducing a full nodal deformable. We show that directly inserting this
> globally shared state into two-way unilateral contact is not automatically
> energy-safe when the XPBD host runs only a few local iterations. Across three
> scenes and fixed schedules, our tested XPBD implementation overdraws the
> measured rigid-side supply by up to 4.4e7 J, while augmented-Lagrangian and
> implicit implementations serve as markedly milder controls. A same-path
> iteration ladder, equal-row-count schedules, warm-starting, and mode truncation
> localize the catastrophic XPBD amplification to finite-budget convergence of
> the shared modal coupling. A controlled in-host block ablation tests whether
> serial row-wise coupling is causal. When architecture permits, our tested
> stiffness-aware implicit/velocity realization is the preferred observed
> control; in a fixed XPBD host, basis selection and local iterations must be
> verified together. For hosts that still cannot converge, a cumulative modal-
> storage projection enforces its scalar accounting bound, but creates up to
> 21.6 mm penetration and is therefore containment rather than corrected contact.

This is a blueprint, not final prose. Recheck every count and compress only after
the final figures are locked.

## 8. Keep, compress, move, and remove

| Current material | Action | Reason |
|---|---|---|
| Current visual XPBD launch | Keep and reframe | Strongest perceptual evidence |
| 24-cell three-host sweep | Keep compact summary | Establishes controls and scale |
| Full two-metric 72-cell heatmap | Move complete version to supplement | Too much page area for a control |
| Iteration ladder and residuals | Expand/recompose | Central causal evidence |
| Equal row evaluations | Keep prominently | Actionable and surprising |
| Warm-start result | Keep in one sentence/panel annotation | Removes an obvious confound |
| Current binary stiff-cluster ablation | Keep only as fallback; replace with cutoff ladder if possible | Not yet a usable band-selection rule |
| Complete host-difference Table 1 | Move to supplement; retain critical differences in prose | Avoids accidental solver-class comparison |
| Bound loop and proposition | Keep after results, compress proof | Auditability without making it the main story |
| Contact-validity table | Keep and simplify | Necessary honesty and method calibration |
| Full-FEM paragraph | Compress to fidelity anchor | Motivates modes; governed path remains unvalidated |
| Detailed CPU/runtime cells | Compress to selected deployment facts | Not central to the diagnostic mechanism |
| Monitor-only GPU paragraph | Remove unless claim retained | Does not time the governed path |
| Long concurrent/passivity positioning | Move most to supplement | Front-loads disclaimers before significance |
| “Production-like” / “deployed” wording | Remove or define concretely | Reviewers challenged the unsupported deployment label |
| Broad “prefer AVBD/implicit” conclusion | Replace with ordered, implementation-specific decision rule | One unmatched implementation per host |
| Repeated 72/60/90/78 counts | Consolidate in one protocol note | Reduces cognitive load and inconsistency risk |

The consolidated protocol note must keep the two headline definitions separate:
`8/24` cells exceed the incident-ratio criterion, while `9/24` violate the strict
Eq. 2 ledger margin. Never substitute one count for the other.

## 9. New evidence plan

### E0 — Required without new science: reproducibility packet

Deliver the ledger actually cited by the paper:

- source commit and artifact hashes;
- exact commands and environment;
- all scene/material/contact parameters;
- all per-cell raw values;
- high-iteration and FEM-reference definitions;
- timing protocol;
- figure-generation commands; and
- a smoke script that regenerates headline counts.

This is a submission requirement for the rewritten narrative, not optional polish.

### E1 — Cheap required audit: gravity/no-contact accounting

For every host and substep schedule:

- free flight under gravity with no contacts;
- rigid-only contact with modal coupling disabled;
- modal free vibration with no rigid contact.

Report the ledger residual relative to the 6.7 J AVBD effect. If the residual is
not negligible, do not interpret the small AVBD overdrafts as contact injection.
The catastrophic XPBD evidence may remain, but the cross-control claim must narrow.

### E1b — Required neighborhood-robustness audit

The current benchmark is deterministic: `seed=0` is reserved and the paper
configuration does not use an RNG. Therefore do **not** promise a seed sweep
unless randomness is deliberately introduced and documented. Pre-register a
small deterministic perturbation ensemble instead.

Freeze the headline cells from the unperturbed ledger before running the audit:

- the worst XPBD cell in each scene;
- the `32x1` versus `4x8` equal-row-evaluation pair; and
- the worst governed-penetration cell.

Use the same paired perturbations for every compared arm. Include 8--12 variants
spanning the following local neighborhood without a combinatorial factorial:

- impact/contact offsets in `x` or `z` of approximately `+/-1--2 mm`;
- drop height or initial normal speed changes of approximately `+/-1%`;
- small positive and negative initial-orientation changes; and
- a separately labeled set of controlled contact-row-order permutations.

Do not pool row-order sensitivity with physical initial-condition sensitivity.
For every headline cell report the positive-ledger-margin fraction, median and
IQR, min/max or robust quantiles, and the logarithmic spread of nonzero
magnitudes. For the guardrail cell report penetration and trajectory-error spread
as well. Round the abstract, captions, and conclusion to the precision supported
by this ensemble rather than preserving five- or six-digit single-run maxima.

This is a **local neighborhood-robustness audit**, not population statistics:
make no p-value or probability claim. If the sign changes materially across the
predefined neighborhood, replace “robust failure” with an existence-and-
sensitivity claim and show the exact fraction rather than hiding the variation.

### E2 — Preferred mechanism analysis: exact-host iteration matrix

For representative active-contact states from shelf and ledge:

1. Freeze the contact set and linearize the exact current XPBD update.
2. Assemble or numerically identify the one-sweep iteration map.
3. Verify that the map predicts an actual one-sweep perturbation.
4. Measure convergence factor/spectral radius versus relaxation, modal rank, and
   frequency content.
5. Compare predicted residual decay against measured gap, separated-row
   multiplier, and energy ladders.

Include this result only if it predicts both scenes without tuning. Do not reuse
the separate averaged-Jacobi device-path spectral-radius result.

### E3 — Preferred practitioner analysis: frequency-cutoff by iteration ladder

For shelf and ledge, construct nested bases using a dimensionless cutoff based on
substep size, for example `f_max * h_sub` values spanning below and above the
Nyquist-scale region. Sweep at least:

- `K = {4, 8, 16, 24, 32}` with `S=1`;
- the practical schedules `1x8` and `2x4`; and
- the existing full basis.

Measure:

- incident ratio and ledger margin;
- gap and separated-row multiplier residual;
- modal/FEM trajectory or field error; and
- wall-clock cost.

Success criterion: a stable safe frontier or monotone tradeoff repeats in at
least shelf and ledge. If no universal frontier appears, publish that negative
result and instruct users to audit rather than promise a cutoff rule.

### E4 — Selected matched-cost comparison

At one visible shelf case and one adversarial ledge case, compare at approximately
equal wall-clock cost:

- more XPBD iterations;
- a truncated modal basis;
- tested implicit realization; and
- current governor.

Report energy margin, penetration, trajectory error, and cost. This answers the
reviewer's practical question directly even if the result favors the implicit
control.

### E5 — Optional motivation evidence: modal versus full-space cost

Only if the setup is straightforward, compare the current reduced arm with a
full-space XPBD/FEM arm on the same discrete operator and contact treatment.
Match fidelity and report online DOFs, constraints, and wall-clock cost. Do not
delay the diagnostic rewrite for this experiment; the existing fidelity anchor
and primary literature are sufficient for the audience argument.

### E6a — Required diagnostic causal ablations inside the XPBD host

Lock the vocabulary before implementing anything. Three variables that were
previously called an “implicit modal block” must remain separate:

1. the free/modal-restoring time integrator (the configured XPBD baseline already
   uses implicit midpoint);
2. the modal effective weight used by a contact update; and
3. serial row-wise versus joint block treatment of contacts sharing the same
   modal vector.

#### E6a-1 — Shared-row block-condensation ablation (committed core)

Compare the current serial support-row XPBD path with the existing
`_support_block` shared-modal condensation path. Hold fixed the scene and state,
modal basis, implicit-midpoint restoring step, timestep/substeps, local-iteration
budget, compliance, relaxation, warm-start policy, contact-row definitions, and
all non-support constraints. Run both:

- a frozen-state/active-set one-step audit; and
- the corresponding full rollout from the identical initialization.

Report ledger margin, incident ratio, direct complementarity residuals,
penetration, trajectory error, and both fixed-iteration and wall-clock cost. The
current block path preserves the active-row compliant fixed point, but uses a
diagonal rigid-body block approximation and a different convergence path; state
those differences explicitly rather than calling this a behavior-identical
implementation toggle.

Begin with one headline scene and one low budget as a smoke/causal probe. If the
result changes the paper's recommendation or mechanism claim, confirm it in at
least one second scene and one second budget. A single positive cell may motivate
follow-up work, but cannot license a general “block solve fixes XPBD” statement.

#### E6a-2 — Stiffness-aware contact-weight counterfactual (feasibility-gated)

The tested impulse host uses a stiffness-aware modal operator of the form
`(M_q + h D_q + h^2 K_q)^-1` in a velocity-level contact update. Do not transplant
that matrix into a position-level XPBD row merely because the operator exists.
First write the complete discrete equations and verify that the counterfactual
has a consistent state update, units, energy accounting, and interpretable fixed
point while leaving the free/restoring step and the rest of the XPBD contact
pipeline unchanged.

Proceed only if that derivation yields a genuine controlled intervention. If it
necessarily changes time discretization, contact semantics, or multiple state
updates at once, record that the ablation is not identifiable and omit it from
the diagnostic paper. If it is feasible, use the same smoke-then-replicate rule
and metrics as E6a-1.

Interpret E6a conservatively:

| E6a-1 block coupling | E6a-2 contact weight | Supported interpretation |
|---|---|---|
| Removes the failure | Does not | Serial shared-row convergence is the leading tested cause. |
| Does not | Removes the failure | Contact weighting/discretization is the leading tested cause. |
| Both remove it | Both remove it | More than one intervention helps; do not assign a unique mechanism. |
| Neither removes it | Neither removes it | The cause lies elsewhere in the pipeline; retain the empirical diagnostic and make no block-mechanism claim. |

If E6a-2 is infeasible, report only what E6a-1 identifies and do not infer the
missing column.

### E6b — Method-route experiment: replicated hybrid formulation

This experiment remains outside the diagnostic critical path. Open it only if
E6a reveals a concrete unmet need for a new, mathematically consistent hybrid
formulation. It must be compared at matched wall-clock cost, preserve contact and
trajectory accuracy better than the governor, and survive at least two scenes
and more than one budget. Use the stop/go criteria in section 2; otherwise retain
the practitioner-diagnostic paper.

## 10. Figure and table plan

### Figure 1 — “Why this extension, and what goes wrong?”

Reuse the current true-scale shelf render, but add a small schematic:

`existing XPBD rigid body + q in R^16 -> shared contact rows -> fixed K`.

Show ungoverned and high-iteration XPBD self-reference prominently. Keep the
governed result smaller and label it “containment, not reference.”

### Figure 2 — Controls, not a solver competition

Replace the full three-solver heatmap in the main paper with:

- an XPBD-focused scene/budget map; and
- a compact summary strip for XPBD/AVBD/implicit containing violation count,
  worst margin, and worst incident ratio.

Caption must say “one implementation of each; not compliance- or cost-matched.”

### Figure 3 — XPBD operating envelope

Recompose the convergence figure into three aligned panels:

- ratio/margin versus `K`;
- direct complementarity diagnostics versus `K`; and
- frequency cutoff versus required `K`, if E3 produces a stable cross-scene
  frontier; otherwise use the already declared current band-ablation panel.

Annotate `32x1` versus `4x8` and warm-start outcome directly rather than spending
separate prose on them. Add the E6a-1 headline comparison as a compact inset or
annotation only if it remains legible. If E6a-1 becomes the stronger causal
result, it replaces the optional E3 panel rather than creating a fourth panel.

### Table 1 — Guardrail outcome and decision

Rows: ungoverned XPBD, converged/more-iteration XPBD, E6a-supported shared-block
path if replicated, tested implicit control, governor. Columns: energy property,
penetration/contact validity, trajectory relation, relative cost, recommended
use. Keep exact values only where measured.

Full host details, all raw cells, and the complete contact-cost table go into the
supplement.

## 11. Rewrite sequence and gates

### Execution priority and fallback discipline

Treat the work as a deadline-ordered menu, not an all-or-nothing package:

| Priority | Items | Rule |
|---|---|---|
| Committed core | Stages A, C, D, E, F, and G; E0, E1, E1b, the E6a equation lock, and E6a-1 | Complete before optional mechanism work; a negative E6a-1 result is valid if reported honestly. |
| Next | E4 | Run after the soundness controls because it directly answers the practical mitigation question. |
| Stretch | E2, E3, and E6a-2 | Include only when technically valid and cross-scene predictive; do not delay the core rewrite. |
| Drop for this deadline | E5 | The existing same-operator fidelity anchor is sufficient for motivation. |
| Separate method gate | E6b | Open only under section 2's stop/go criteria; never let it block the diagnostic submission. |

Preserve the current PDF with SHA-256 prefix `32f2951d...` as the fallback
candidate. Its `4.50/7` mean with zero reject scores came from one simulated
AI-review panel; use that only as comparative calibration, not as an acceptance
probability or evidence about the real committee.

### Stage A — Freeze the claim sheet

1. Copy C1--C5 and the nonclaims into a manuscript claim checklist.
2. Assign every claim one figure/table/ledger source.
3. Remove any claim with no source or mark it as motivation/hypothesis.

Exit gate: no use of “XPBD” where “our tested XPBD implementation” is required;
no use of “passivity” for the scene-wide scalar ledger without an explicit
qualification.

### Stage B — Run the minimum new evidence

1. Complete E1 and freeze the accounting residual.
2. Complete E1b using the pre-registered paired perturbation ensemble.
3. Lock the three distinct E6a variables and run the E6a-1 frozen-state plus
   rollout smoke test.
4. If E6a-1 changes a recommendation or mechanism claim, repeat it in a second
   scene and second budget before using it as more than a local causal probe.
5. Attempt E6a-2 only if its discrete-equation feasibility gate passes.
6. Complete E4 next if timing data can be made genuinely comparable.
7. Attempt E2 and E3 as stretch work; select results by cross-scene predictive
   value, not by which looks most dramatic.

Exit gate: E1, E1b, and E6a-1 have frozen results; every positive or negative
causal statement matches those results; no one-cell outcome is written as a
general recommendation; all new numbers and perturbations are frozen in the
ledger. A positive mechanism result is welcome, not required for honest exit.

### Stage C — Lock figures before prose compression

1. Recompose Figures 1--3.
2. Generate the decision/guardrail table.
3. Verify labels at single-column and reduced-player sizes.

Exit gate: each visual answers one reviewer question; no visual exists merely to
preserve prior work.

### Stage D — Rewrite the north-star text first

Order:

1. title;
2. conclusion;
3. abstract;
4. first two introduction paragraphs;
5. contribution list; and
6. section headings.

Do this before moving detailed paragraphs so the body is forced to serve the new
paper identity.

Exit gate: a fresh reader who sees only title, abstract, teaser, and conclusion
can state the target practitioner, why modes are used, why implicit is preferred
as the tested control when possible, what E6a actually changed, and when the
governor is relevant.

### Stage E — Rebuild the six-page body

1. Move empirical failure before the bound.
2. Compress equations and proof.
3. Replace the broad host table/heatmap with control summaries.
4. Integrate full-space/modal motivation and same-operator fidelity.
5. Consolidate limitations and count terminology.

Run after every meaningful edit:

```text
cd paper
latexmk -pdf main_short.tex
python ../scripts/check_page_gate.py
```

Exit gate: body ends on page 6, references begin on page 7, zero overfull boxes,
and all figure/table references resolve.

### Stage F — Artifact and video

1. Package E0, including the E1b ensemble and all E6a variants, and run its smoke
   test from a clean checkout/environment.
2. Add the assigned paper ID when available.
3. Update the video according to section 12.
4. Hash the final PDF, video, and supplement together.

### Stage G — Adversarial re-review

Give six isolated reviewers only the final PDF/video/supplement, without showing
them prior scores or the rewrite history. Before asking for a score, ask them to
answer:

1. Why would anyone use modal DOFs instead of a full XPBD soft body?
2. Why not use the impulse realization?
3. What is the main scientific contribution?
4. When, if ever, should the governor be used?

Rewrite once if more than one reviewer answers any question incorrectly. Then
compare the rewrite with the frozen fallback under the same rubric. The rewrite
must improve motivation comprehension without introducing a new scientific,
reproducibility, contact-validity, or presentation defect; the score profile is
secondary calibration. After one complete rewrite/review cycle, select the
stronger packet rather than looping indefinitely.

## 12. Video rewrite

Suggested 45--55 second structure:

- **0--6 s:** existing XPBD rigid host, full nodal alternative, and 16-mode
  extension schematic.
- **6--18 s:** same-state XPBD ungoverned versus high-iteration self-reference;
  retain the visible launch.
- **18--29 s:** iteration allocation: `32x1` versus `4x8` at equal row count.
- **29--37 s:** basis/cutoff result or a concise “removing the stiff cluster is
  not sufficient” panel.
- **37--46 s:** governor containment plus a true-scale penetration close-up.
- **46--55 s:** decision card: tested stiffness-aware velocity path if the
  architecture is flexible; otherwise verify the XPBD shared block, basis, and
  iterations; governor only as containment.

AVBD needs at most a brief control view. The video should no longer end as if the
governor were the main product.

## 13. Final acceptance checklist

### Scientific

- [ ] Practitioner workflow is explicit and credible.
- [ ] Tested implementation is distinguished from solver class.
- [ ] Modal/full-space tradeoff is stated without an unmeasured speed claim.
- [ ] Truncation claim is supported by same-path and direct residual evidence.
- [ ] Headline failures and guardrail costs have E1b neighborhood spreads, exact
      sign fractions, and supported numerical precision.
- [ ] Basis advice is supported by a cutoff ladder or explicitly presented as a
      case-specific audit.
- [ ] The paper states that baseline XPBD already uses an implicit-midpoint modal
      restoring step and never calls it explicit modal integration.
- [ ] E6a-1 isolates shared-row block treatment as far as the implementation
      permits and discloses its diagonal-body/different-convergence approximations.
- [ ] Any stiffness-aware E6a-2 result passed the discrete-equation feasibility
      gate; otherwise it is omitted without inference.
- [ ] Any implicit/shared-block recommendation is implementation-specific, and a
      recommendation-changing E6a result repeats in a second scene and budget.
- [ ] Governor guarantee and contact/trajectory cost are inseparable in prose.
- [ ] Gravity/no-contact accounting audit is below relevant effect sizes.

### Reproducibility

- [ ] Supplemental ledger is actually included.
- [ ] Commands, commits, parameters, raw cells, and hashes are complete.
- [ ] Perturbation definitions, paired arm mapping, row-order variants, and all
      E6a switches/equations are frozen.
- [ ] Headline-count smoke test passes.
- [ ] Every paper number has one frozen source row.

### Submission

- [ ] Six content pages maximum; references excluded.
- [ ] No overfull boxes or unreadable figure labels.
- [ ] Anonymous metadata and prose.
- [ ] Paper ID inserted when assigned.
- [ ] Video includes penetration and the practitioner decision rule.

## 14. Expected outcome

This plan intentionally produces a **major focus and structural rewrite**. The
title, abstract, opening motivation, contribution order, section order, principal
figures, conclusion, and video decision card should all change. The final PDF
should read as a practitioner diagnostic and operating guide, not as a three-
solver survey or a governor-centered method paper.

It is not a from-scratch technical project. The contact row, accounting equation,
existing sweep, iteration ladder, warm-start and band controls, modal/FEM fidelity
anchor, guardrail proof, and contact-cost data remain reusable. The required new
science is deliberately narrow: accounting controls, local robustness, and a
precisely defined in-host causal ablation.

The rewritten paper should no longer prompt:

> “The impulse solver works, so why does this paper exist?”

It should prompt:

> “If I add a cheap global modal state to my existing XPBD rigid-body engine,
> the obvious contact transcription can fail at my normal budget; this paper
> tells me how to detect the failure, what solver/basis/budget choices to prefer,
> and what a last-resort bound does and does not guarantee.”

That is a focused but defensible MIG short-paper contribution. A stronger method
paper remains possible later, but only if E6b produces a consistent hybrid
formulation and a contact-faithful remedy that pass the replicated matched-cost
gate.

## 15. Integrated amendment record (2026-07-21)

The second-opinion review has been incorporated into the executable sections
above; this section is an audit trail, not a second layer of instructions.

- **Neighborhood robustness:** E1b now uses a predefined deterministic
  perturbation and row-order ensemble because the current configuration has no
  active RNG. Section 13 requires spread, sign fraction, and supported precision.
- **Causal ablation:** E6 is split into E6a-1 shared-row block condensation,
  feasibility-gated E6a-2 stiffness-aware contact weighting, and the separate
  E6b method route. This corrects the earlier false implication that baseline
  XPBD uses explicit modal restoring integration.
- **Evidence scope:** a one-scene/one-budget result is only a causal probe. Any
  recommendation-changing result must repeat in a second scene and budget.
- **Deadline discipline:** section 11 now contains the committed/next/stretch/
  drop ordering, the frozen `32f2951d...` fallback, and a one-cycle comparative
  re-review gate. The prior `4.50/7` simulated mean is calibration, not an
  estimate of real acceptance probability.
- **Count integrity:** sections 4 and 8 preserve `8/24` incident-ratio violations
  versus `9/24` strict Eq. 2 ledger-margin violations.

No manuscript, solver, benchmark, figure, or video change is authorized merely
by this planning document; each implementation stage retains its own gate.
