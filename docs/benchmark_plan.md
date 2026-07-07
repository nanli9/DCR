# Benchmark plan — runbook + FEM-GT refinement (future reference)

Written 2026-07-06. Companion to `docs/experiment_plan.md` (the scenes ×
metrics × baselines matrix) and `docs/all_scenes_generalization.md` (what the
all-cargo + all-FEM-GT generalization delivered). This file is the **how to
run it and what to fix next** document.

---

## 1. X-suite (branch `benchmark`) — the committed evidence

The already-measured X0–X7 evidence lives on branch `benchmark`
(`benchmarks/paper_eval/`, docs in `docs/paper_eval/`). Reproduce block:

```bash
# in a worktree, so the working tree / live viewers stay untouched:
git worktree add ../DCR-benchmark benchmark
cd ../DCR-benchmark
<repo>/.venv/bin/python -m benchmarks.paper_eval.x1_passivity.run_blowup_figure
<repo>/.venv/bin/python -m benchmarks.paper_eval.x2_vs_dcr.run_x2
<repo>/.venv/bin/python -m benchmarks.paper_eval.x3_ground_truth.run_x3
<repo>/.venv/bin/python -m benchmarks.paper_eval.x5_perf.run_perf
```

Expected headline numbers (verified against `docs/paper_eval/*.md` on the
branch, 2026-07-06):

| harness | headline |
|---|---|
| X1 passivity | OFF injects 12/24 cells, up to 119,534×; ON 24/24 passive (0 clamps at relax 0.7) |
| X2 vs-DCR falloff | native 9.8/4.9/3.2/2.0 mJ vs DCR 13.6/6.1/0.9/0.9 at 0.14–0.56 m (2.3× at the far object) |
| X3 FEM-GT | native/GT mid-deflection 0.56→0.75→0.89→1.02 as h=1/120→1/960; ring 81.0 vs 80.7 Hz |
| X5 perf | clamp +1–2 ms (2–5%); AVBD 1.3–2.8× XPBD; dinner/avbd 58 ms, ledge/avbd 29 ms |
| X7 restitution | paper-DCR ratio → 2.6× as ε_r→1; native ≤ 1 ∀ε_r |

Caveats already established: X-suite pins PAPER_CONFIG (relax 0.7, 16×4,
symplectic, h=1/120); the "0 clamps" holds at relax 0.7 (16/432 at relax 1.0).
X4 (impulse-train replay) needs per-substep impulse logging; X6 breadth
scenes are scoped but unbuilt.

## 2. This branch — all-FEM GT runbook

```bash
.venv/bin/python -m benchmarks.fem_gt.run_gt --scene all           # production res
.venv/bin/python -m benchmarks.fem_gt.run_gt --scene dinner --quick
.venv/bin/python scripts/run_fem_gt_viser.py --scene dinner        # live viewer
#   GUI: tet-wireframe toggle, deformation ×, sim-steps/frame
```

Outputs: `benchmarks/fem_gt/out/<scene>_gt[_r{n}].{csv,json}` — support
mid-span u_y per frame, per-body COM/energies, interval-averaged contact
ledger; the manifest now carries `peak_mid_uy` / `ring_hz` / `wall_s`.
NOTE (2026-07-07): the probe now records every 50 fine steps (400 Hz) — the
original 200-step stride (100 Hz) aliased the ~80–170 Hz supports ring and
under-sampled the impact transient, which is why the re-recorded R0 peaks
(e.g. shelf 4.3 mm) read higher than the first-run numbers (shelf −1.5 mm).

## 3. FEM-GT resolution gap — **the current tet counts are NOT enough**

Current meshes (R0, what §2 measured):

| mesh | cells | nodes | tets | concern |
|---|---|--:|--:|---|
| support (rule: 10 cells/m plan, **2 through thickness**) | truck 25×15×2 | 1,248 | 3,750 | 2 element layers in bending; 5-tet CST hexes are bending-stiff → deflection under-resolved |
| | dinner 12×10×2 | 429 | 1,200 | same |
| | shelf 8×4×2 | 135 | 320 | same, coarsest |
| bodies (rule: base 3 on longest axis, floor 2) | 2–3 cells/axis | 36–64 | 135–180 | thin dims (plates 10 mm, forks 5 mm) get exactly 2 cells → first bending modes far too stiff |

Why it matters: linear (CST) tets lock in bending; with only 2 layers through
the thickness the support's static sag and ring frequency are both biased
stiff, and the per-body modal shapes the GT is supposed to referee are
crudest exactly where the native arm's box bodies are soft (thin plates /
cutlery). The X3 slab had the same 2-layer rule but its acceptance came from
an h-refinement sweep — the SPATIAL sweep is what we owe here.

**Refinement ladder (do in order; acceptance between rungs):**

| rung | support rule | body rule | est. nodes (dinner) | est. wall/sim-s |
|---|---|---|--:|--:|
| R0 (now) | 10/m, 2 thick | base 3, floor 2 | 429 + ~17×50 | 43 s |
| R1 | 20/m, 3 thick | base 4, floor 3 | ~1,900 + ~17×120 | ~3–5 min |
| R2 | 30/m, 4 thick | base 6, floor 3 | ~5,000 + ~17×250 | ~10–20 min |

- Acceptance (X3-B pattern): support mid-span u_y peak and dominant ring
  frequency change **< 2 %** R(n)→R(n+1), per scene. Report a per-scene
  convergence table. Stop at the first converged rung.
- Sweep h_fine alongside (5e-5 → 2.5e-5): the penalty-oscillator pin is
  capped at hω ≤ 0.35, so halving h_fine also STIFFENS contact — spatial and
  temporal refinement are coupled; converge them jointly.
- Implementation: both rules are single functions —
  `benchmarks/fem_gt/common.py::_slab_resolution` and
  `dcr/fem/multibody_gt.py::make_box_fem_body` (resolution arg). Add
  `--refine {0,1,2}` to `run_gt.py` rather than editing constants.
- Cost note: Newmark refactorizes once (splu) and back-substitutes per step;
  the per-step cost is ~linear in nodes, the height-field query ~linear in
  top tris. R2 dinner ≈ 15× R0 — still offline-friendly.

### 3.1 MEASURED (2026-07-07) — the ladder ran; the criterion needs revising

Ran R0/R1/R2 dynamics for all 5 scenes (`run_gt.py --refine {0,1,2}`,
`refine_report.py`) plus an operator-only extension R3/R4
(`eigen_ladder.py`: corner-fixed support eigsh + static self-weight sag,
no dynamics). **No scene meets the <2 % criterion at any rung**, and the
data says the criterion itself was partly wrong:

| scene | dyn peak mm R0→R1→R2 | dyn ring Hz R0→R1→R2 | operator f1 Hz R0→…→R4 (d% at R4) |
|---|---|---|---|
| truck  | 3.76 → 8.76 → 11.73 | 49.5 → 32.5 → 28.1 | 48.9 → 32.8 → 28.2 → 26.2 → 25.1 (4.1 %) |
| ledge  | 0.96 → 1.39 → 0.86  | 162 → 168 → 152    | 238 → 170 → 152 → 143 → 139 (2.9 %) |
| shelf  | 4.30 → 16.14 → 26.01| 101 → 58 → 44      | 98 → 57 → 44 → 38 → 35 (8.9 %) |
| dinner | 0.85 → 3.18 → 4.50  | 163 → 91 → 72      | 161 → 91 → 72 → 62 → 58 (7.1 %) |
| cargo  | 0.066 → 0.221 → 0.493| 60 → 164 → 177    | 455 → 237 → 177 → 145 → 130 (10.4 %) |

Findings, in decreasing order of importance:

1. **The GT dynamics faithfully reports its operator.** The dynamic ring
   frequency matches the operator's eigsh f1 to ~1–3 % in 12/15 cells
   (dinner R0–R2 near-exact; the 3 mismatched cells — ledge R0, cargo
   R0/R1 — are rungs where the FFT peak locked onto a body/stack mode, not
   the slab). The ring metric is also h_fine-insensitive (≤1.1 % across
   ledge/shelf/dinner from 5e-5 → 2.5e-5 at fixed R1). Ring frequency is a
   GOOD metric.
2. **The operator itself is nowhere near the continuum.** CST (linear-tet)
   thin-plate locking releases very slowly: f1 still drops 3–10 %/rung and
   static sag 6–24 %/rung at R4 (truck R4 = 67k nodes). Converging linear
   tets to the continuum is a dead end at feasible budgets; quadratic
   elements are out of scope. R0 was severely locked: sag off by ~3–6×.
3. **Peak transient |u_y| is non-convergent BY CONSTRUCTION.** Two
   contaminants: the per-node contact pin softens as refinement makes nodes
   lighter (mesh-coupled excitation), and the multi-body trajectories
   diverge between rungs (the ledger keys differ per rung — book-book
   collisions appear at R1, cone-cone at R2; at h_fine=2.5e-5 a shelf book
   falls to the floor). Under the h_fine check at fixed mesh the peak moves
   up to 17 % (shelf; ledge 4.8 %, dinner 1.1 % — worst exactly where
   multi-body chatter dominates). Do not use transient peaks as a
   convergence criterion.

**Revised acceptance (supersedes the <2 % rung-to-rung rule above):**

- Do NOT chase mesh-to-continuum convergence of the GT. Instead, pin a rung
  (R1: every scene's dynamics fits in minutes; nodes ≈ 5× R0) and run the
  §4 shared-operator comparison there — the native arm's modal basis is the
  eigenbasis of the SAME discrete (K, M), so operator bias cancels exactly
  and the X3 criterion (native/GT ratio → 1.0 under RIGID-step refinement)
  is meaningful at any rung.
- Score: mid-span u_y ratio + ring frequency (both operator-relative), the
  interval-averaged contact ledger (mesh-robust momentum balance), never
  transient peaks across meshes.
- In the paper, report GT support frequencies as properties of the discrete
  operator, not as physical plate frequencies (they are 4–10 % stiff at R4
  and were ~2–3.5× stiff at R0).

## 4. G1 comparison (the missing native arm)

The GT arm alone does not produce the acceptance number. Per scene:
1. Build the support `FEMModel` once (the §2/§3 mesh at the PINNED rung —
   R1 per §3.1; there is no "converged" rung, and none is needed once the
   operator is shared).
2. Native arm: modal basis = that operator's eigenbasis
   (`ModalAnalysis` → `make_fem_modal_support` pattern; `dinner_scene_gt.py`
   on `benchmark` is the template) — NOT the synthetic debug basis the
   production scenes currently use.
3. Run native at h = 1/120 → 1/960; report native/GT mid-deflection ratio
   per scene (target → 1.0, the X3 criterion) + ring-frequency error.

## 5. Operating points (benchmark-relevant config, measured 2026-07-06)

- AVBD modal under-relax class default **0.7** (production/PAPER_CONFIG).
- XPBD stays **0.25**: measured ceiling on the truck impact — 0.4 marginal,
  0.5–0.6 flings bodies ~90 m, ≥ 0.65 NaN. Do not raise to match AVBD.
- Truck 4-high lumber stack holds upright only under the conservative AVBD
  q-chase (ω ≤ 0.15) — N3-gate fragility; the stack tests pin relax 0.1.
- GT contact: k_penalty 5e7 (X3 cap), per-node pin f_c = 1.5 kHz, hω ≤ 0.35,
  contact ζ = 0.2, frictionless vertical normal (side faces unresolved —
  score deflection fields, not post-topple piles).

## 6. Deferred (tracked elsewhere)

- G3 real-time reconciliation: ON HOLD until CUDA hardware (user decision).
- G4 momentum probe, X4 impulse replay, X6 breadth: `docs/experiment_plan.md` §5.
