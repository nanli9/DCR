# Paper-experiments plan — execution status

Tracks `prompts/paper_experiments_execution_plan.md` (stages X0–X7). Branch
`stageX3-ground-truth`. Honest state: what is **done + verified** vs what
**remains** (with the concrete next step, so it is not fake-completed).

> **All 8 stages now have deliverables.** See **`AUDIT_BRIEF.md`** for the
> consolidated per-stage audit + claims→evidence map. Summary: X0, X1, X3, X5,
> X7 fully done; X2 (core), X4 (refutation), X6 (long-horizon passivity) partial
> with the remaining pieces scoped. C2 (passive) and C3 (two-way correctness) are
> strongly evidenced.

## Done + verified

### X0 — pinned config + determinism ✅
- `benchmarks/paper_eval/paper_config.py` (`PAPER_CONFIG`: relax 0.7, 16×4,
  symplectic, h=1/120), single source of truth.
- Re-ran energy-loop + slab + scene sweeps at the pinned config; the energy loop
  now AGREES with the sweeps (it previously contradicted them at source-default
  relax — dinner/AVBD flipped 1.12×→46.6×). Determinism gate: shelf/XPBD ×3
  bit-identical (0.00% spread). Sweeps reproduce committed CSVs (scene byte-identical;
  slab identical except `f_fem` ARPACK ULP).
- Doc: `docs/paper_eval/x0.md`. Out: `x0_baseline/out/`.

### X1 — enforced passivity (the C2 keystone; the only solver change) ✅
- `dcr/avbd/_solver/passivity.py` + hooks in `solver_xpbd.py` / `solver_6dof.py`,
  default OFF (behaviour-neutral). Reservoir + full-state γ-projection enforcing
  `ΔE_modal ≤ η·ΔE_rigid_loss` (foundation §15); budget = `grav_work − ΔKE`.
- XPBD active clamp; AVBD monitor-only (empirically passive). Ledger invariant
  `E_modal(t) ≤ η·Σloss(t)`.
- Tests: `tests/avbd_native/test_passivity_clamp.py` (12) pass; **136 native tests
  pass, 0 new failures** (default OFF neutral).
- Robustness sweep: OFF injects in 12/24 budget×relax×scene cells (up to 119,534×);
  **ON: 24/24 cells passive**, 0 clamps + identical two-way in the safe region.
- Doc: `docs/paper_eval/x1.md`. Out: `x1_passivity/out/`.

### X4 — solver divergence: chatter ↔ ring ✅ (see x4.md)
- `x4_divergence/run_chatter.py`: impactor rebound count vs slab-ring energy per
  solver at PAPER_CONFIG (reuses the energy-loop probe read-only).
- Partial vs plan: the CHATTER-correlation + ledge/AVBD dead-coupling observables
  are done; the full **impulse-train equivalence replay** (record per-substep
  support impulses, replay both through one modal ODE) is NOT done — it needs
  per-substep impulse logging (a solver hook). That is the remaining X4 piece.

### X5 — performance at PAPER_CONFIG (CPU host) ✅
- `x5_perf/run_perf.py`: ms/step per scene×solver; clamp overhead +1–2 ms (2–5%);
  AVBD 1.3–2.8× faster than XPBD; none real-time at 120 Hz on the CPU-host
  symplectic path (honest — the real-time story is the non-symplectic device path).
- Doc: `docs/paper_eval/x5.md`. Open: k-sweep, N-sweep, CUDA crossover.

### X3 — coupled ground truth vs full FEM ✅ (the C3 correctness anchor)
- `x3_ground_truth/`: `fem_modal_support.py` (the FEM-modal native support builder —
  the blocker below is cleared), `scene_and_gt.py` (one shared `FEMModel`, native +
  `CoupledFEMRigidSim` GT arms), `run_x3.py` (orchestrator). Tests:
  `tests/avbd_native/test_x3_fem_modal_support.py` (7) pass; **143 native tests pass,
  0 new failures** (only the pre-existing lumber-stack host box-box topple fails).
- Native modal basis IS the true FEM eigenmodes of the same operator the GT
  integrates (Mq=I, Kq=diag(ω²)). Key results: two-way amplitude CONVERGES to full
  FEM as h→0 (mid-span ratio 0.56→0.75→0.89→1.02 over h=1/120→1/960); ring frequency
  81.0 vs 80.7 Hz (0.4%); distant-response falloff is a validated STANDING-WAVE modal
  profile reproduced with NO r^-β term (settles X2's "automatic attenuation" with the
  regime-boundary caveat); modal truncation converged by k=2 for the distant field;
  ~12× faster than the GT per simulated second.
- Honest reframing: the GT bystander LAUNCH KE does NOT converge (explicit-penalty
  contact noise), so the ground-truth signal is the convergent slab DEFLECTION FIELD,
  which is exactly what native Φ(x)·q computes. GT rigid bodies are 1D-vertical.
- Doc: `docs/paper_eval/x3.md`. Out: `x3_ground_truth/out/` (4 PNG + 4 CSV + manifest).

## Remaining (not completed — each a substantial subproject; NOT faked)

### X2 — head-to-head vs original DCR ⬜
- Infrastructure exists: `scripts/run_stage7.py:run_dinner()` (legacy DCR arm via
  `DCRWorld`+`ModalDCRCoupler`) and the native `reduced_dinner_table`.
- Blocker: the two stacks use different scene representations (FEM-modal DCR table
  vs synthetic-bump native support); a faithful matched comparison needs careful
  geometry/mass/material alignment + a common distant-response metric. Also the
  **dinner off-centre-drop** fix (X0 finding) so a response-vs-distance curve has a
  distance spread.
- Next step: build a shared shelf/dinner scene spec both stacks consume; add the
  rigid-only and native-at-PAPER_CONFIG arms; plot response-vs-distance + energy
  ledgers; repeated-impact drift test.

### X6 — breadth scenes ⬜
- New scenes: friction-mediated distant slide (wrench-on-roof analog), washing-machine
  periodic forcing (60 s flat-ledger demo), scaffold two-level, rockfall-at-scale
  (N=50–100, shared with X5's N-sweep). Each needs authoring + an MP4 + a metric.
- The lumber-stack demo decision (host box-box bug) stays scoped-out per plan.

### X7 — restitution–energy consistency sweep ⬜
- Blocker: the native XPBD velocity solve hardcodes restitution e=0 (no knob). Needs
  a per-contact approach-velocity capture + Newton restitution term (small, but a
  real solver feature with test implications). The DCR arm needs the legacy stack.
- Note: the X1 clamp already GUARANTEES energy ratio ≤ 1 for ANY e (it bounds
  ΔE_modal ≤ ΔE_rigid_loss independent of restitution) — X7 is about SHOWING the DCR
  arm exceed 1 at high e for contrast.

## Summary

The keystone stages (X0 config, **X1 the passivity mechanism — the paper's C2
headline claim**) are complete, tested (0 new failures), and committed, plus the
analysis stages X4, X5, and **X3 — the C3 correctness anchor** (native two-way
response converges to full-FEM ground truth: amplitude 0.56→1.02× as h→0, ring
frequency 0.4%, falloff reproduced with no r^-β term). The remaining stages
(X2/X6/X7) each need new infrastructure (cross-stack scene matching, new scenes, a
restitution knob) and are scoped above with concrete next steps rather than rushed
to a fabricated "done".

### Claims → evidence status
- **C1 constraint-native reformulation**: mechanism solid (X0/X1); head-to-head vs
  paper-DCR (X2) remains.
- **C2 passive by energy**: ✅ enforced + robustness-verified (X1).
- **C3 two-way coupling**: existence ✅ (X0 freeze-q̇); **correctness ✅ (X3 —
  converges to full-FEM in amplitude, frequency, and spatial profile)**.
