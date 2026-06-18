# Plan — Dynamic two-way modal constraint in the GPU-resident AVBD/XPBD solver (AVBD-Native), 4 scenes, fem/abd/fem_rigid materials

## Context

The two-way dynamic modal contact constraint ("Approach B", `two_band_coupling.html`)
is finalized and validated on the `twobody-warp-gpu-resident` branch — but that branch's
contact is a **fixed-pair, +y-only penalty list with no collision detection**, so tumbling
cubes interpenetrate. The user wants the *production* path: take the **well-optimized,
GPU-resident AVBD solver on the `AVBD-Native` branch** (real box-box SAT collision +
friction, CUDA-graph capture, zero host readback — *no* penetration problem), upgrade its
modal coupling from **quasi-static** to the **finalized dynamic constraint**, run its four
scenes (truck, ledge, shelf, dinner table), and add a **fem/abd/fem_rigid cube-material
dropdown**. Both AVBD and XPBD must be **fully GPU-resident**; the underlying math must
**never change** (always reference `two_band_coupling.html`, mark any divergence with
`# DEVIATION:`); after each stage run the **profiling → optimization → profiling** loop
(per `docs/twobody/warp_gpu_resident.md`) until no >10% speedup remains.

Decisions locked with the user:
- **Architecture:** Path A — port the constraint INTO the AVBD-Native solver, **staged**.
- **XPBD:** build a **GPU-resident XPBD** too (a dedicated stage; CPU `XPBDDynamicSystem` is the parity oracle).
- **Cube materials, in order:** **fem_rigid → abd → fem**.

## Approach

New branch **off `AVBD-Native`** (it has the solver + 4 scenes + viser + the GPU modal
coupler to upgrade). The dynamic-constraint math and the cube body models are *referenced*
from the twobody work (`dcr/twobody/position_based.py`, `rigid_modal.py`, `reduced_body.py`)
and re-expressed in the AVBD-Native solver's idiom — they do **not** transfer as drop-in code
(different solver paradigm: per-body block descent vs monolithic Newton).

Cross-cutting rules for every stage:
- **Parity gate (never change math):** each GPU change must match its CPU reference to fp64
  roundoff before it lands. Oracles: support modal block → `reduced_support_solve.py:365-368`
  (already the dynamic formula); cube modal coupling → twobody `RigidModalSystem` /
  `AVBDDynamicSystem`. Cite `two_band_coupling.html` equations in touched functions.
- **Residency gate:** `step()` issues only `wp.launch` in the hot loop (no `.numpy()`/
  `synchronize`/host readback); state stays in `wp.array` on `cuda:0`; fixed launch sequence
  captured into a CUDA graph. Audit each stage.
- **Profiling artifact:** ms/step + speedup table + the parity number, per stage.

### Stage 0 — Branch + baseline audit
- Create branch off `AVBD-Native`. Run each of the 4 scenes' viser (`scripts/run_reduced_scene_viser.py --scene {truck,ledge,shelf,dinner}`) on `cuda:0`; confirm the quasi-static coupled solver is GPU-resident (residency audit) and record **baseline ms/step per scene**.
- **Accept:** all 4 scenes launch + step on GPU; baseline profiling table recorded.

### Stage 1 — Dynamic modal constraint into the GPU AVBD coupler (the core "put the constraint in")
- **Modify** `dcr/avbd/reduced_coupled_avbd.py`: replace the quasi-static block (the lines `H_q = Kq.copy(); g_q = Kq @ self.rs.q_s`, ~`:1103`) with the dynamic block
  `H_q = Mq/h² + Kq + Dq/h ; g_q = Mq/h²(q−q̂) + Kq q + Dq q̇` (predictor `q̂ = qⁿ + h q̇ⁿ + h² Mq⁻¹ f_q^grav`; carry `q̇` across steps). Everything downstream (U_y contributions `:1218`, cross-block `−ρ J_x U_yᵀ` `:1221`, Schur reduce `:1250`) is **unchanged** — the dynamic terms are diagonal additions to the modal block.
- **Modify** `dcr/avbd/reduced_coupled_kernels.py`: the device kernels (`k_hq`/`k_g`/`k_schur`/`k_backsub`) get the same `Mq/h² + Dq/h` additions and the `q̂` predictor; **no host readback added**. Upload `Mq`, `Dq`, `q̂`, `q̇` as resident `wp.array`s.
- **Delete the split machinery** (the dynamic constraint makes it unnecessary): `dcr/avbd/reservoir.py` (η governor), `dcr/avbd/reduced_dcr_postkick.py` (one-way velocity kick), and in `reduced_coupled_avbd.py` the `q_s/q_d` split + EMA high-pass + `_substep_end_split` + IIR overlay. Drop `qdot`-on-`q_d`; carry a single `(q, q̇)`. Keep `reduced_support.py` data layer (Mq/Kq/Dq/U_points) but collapse the split fields to one `q, q̇`.
- **Reuse / oracle:** `reduced_support_solve.py:365-368` is the exact CPU dynamic formula — keep it (or a thin numpy mirror) as the parity oracle.
- **Accept:** (a) GPU dynamic coupler matches the CPU dynamic oracle to ≤1e-12 on truck; (b) the two-way counterfactual reproduces the `two_band_coupling.html` signature — dynamic `q` launches the bystander cargo while frozen `q̇≡0` gives 0 mm / 0 J; total energy monotone non-increasing (passive by backward Euler). **Test** `tests/avbd_native/test_dynamic_coupling.py` + **plot** split-vs-dynamic per scene.

### Stage 2 — Residency verification + profiling loop (native rigid cargo)
- Residency audit on the upgraded coupler (the new `Mq/h²`/`Dq/h` terms must not introduce a host readback). Confirm CUDA-graph replay intact.
- Profile per scene (truck busiest); apply the lever ladder from `docs/twobody/warp_gpu_resident.md` (the modal Schur is small/serial — candidate levers: fold the modal block into the captured graph, batch the per-body Schur contributions); reprofile; **stop at <10%**. Parity held at each step.
- **Accept:** residency audit pass + profiling table (ms/step, speedup) + parity number.

### Stage 3 — `fem_rigid` cube material (first material)
- Add a **fem_rigid cargo body type**: the native 6-DOF rigid box (already has real SAT collision) **+ per-body elastic modes** `a∈ℝ^k` solved in its per-body block. The cube's contact corner feeds BOTH the rigid gradient (`[n̂; r×n̂]`) and the modal gradient (`R·Φ_c`, co-rotated mode shape at the corner) — the same dynamic modal block (`Mq_cube/h² + Kq_cube + Dq_cube/h`) as the support, but attached to a moving cargo body.
- **Reuse / reference:** `dcr/twobody/rigid_modal.py` (`build_fem_rigid_cube` eigenmode extraction; `point_jac_tan` = the co-rotated `R·Φ_c` contact Jacobian; isotropic-inertia simplification). Eigenmodes from the cube's FEM (`dcr/modal/modal_analysis.py`).
- GPU-resident: new per-body modal kernels (device); parity vs a CPU `RigidModalSystem`-style reference.
- **Accept:** a `fem_rigid` cube on the ledge scene **tumbles with real collision (zero penetration) AND flexes (modal)**; parity ≤ tol; energy monotone. **Test** + **MP4** (ledge rockfall, fem_rigid cargo).

### Stage 4 — `abd` cube material
- Add an **affine 12-DOF body type** (`p + A`, quartic orthogonality potential `V⊥`) as a cargo option, with real collision on its deformed geometry. **Reference** `dcr/twobody/reduced_body.py` `ABDAffineBody` (mass Eq.4, `V⊥` Eq.6-8, constant point Jacobians). New per-body affine primal kernel (device).
- **Accept:** abd cube tumbles + shears under impact, real collision; parity ≤ tol; energy monotone. **Test** + **MP4**.

### Stage 5 — `fem` cube material
- Add the **translation(3)+modal** cargo body type (no rotation) — a restriction of fem_rigid. Reference `reduced_body.py` `FEMModalBody`.
- **Accept:** fem cube on every scene; CPU/GPU parity ≤ tol. **Test** + matrix smoke (4 scenes × 3 materials, 200 steps, no NaN, energy monotone).

### Stage 6 — GPU-resident XPBD
- Build a **device-resident XPBD** solver path on AVBD-Native (it has none): Gauss–Seidel compliant constraints — per-mode `K_q` diagonal compliance + the cube modal constraints + unilateral contact — as graph-colored device kernels, with `D_q` via Macklin's damped update **exactly** as the CPU `XPBDDynamicSystem`. CPU `dcr/twobody/position_based.py:XPBDDynamicSystem` is the parity oracle (do not change its math).
- **Accept:** GPU XPBD parity vs CPU reference ≤ tol; residency audit pass; same two-way loop + passivity as AVBD on all 4 scenes/3 materials. **Test** + **plot**.

### Stage 7 — Unified viser (scene × solver × material × device)
- **Create** `scripts/run_native_scenes_viser.py` fusing:
  - from `git show AVBD-Native:scripts/run_reduced_scene_viser.py` — the **scene dropdown** (truck/ledge/shelf/dinner) + per-scene preset defaults + support-surface rendering + decorated body rendering + diagnostics HUD;
  - from `scripts/run_two_body_viser.py` — the **solver dropdown** (avbd/xpbd/split), **material dropdown** (fem/abd/fem_rigid), **device dropdown** (cpu/cuda:0) + live backend/ms-step HUD.
- New combined wiring: scene(4) × solver(avbd/xpbd/split) × material(fem/abd/fem_rigid) × device(cpu/cuda:0). HUD shows backend, ms/step, slab-modal-KE (the two-way tell-tale), max penetration.
- **Accept:** every combination launches, switches live, renders correctly; tumbling fem_rigid/abd shows no penetration.

### Stage 8 — Full-system profiling + docs + parity suite
- End-to-end profiling pass (all scenes/solvers/materials) to the <10% criterion; write `docs/avbd_native/dynamic_constraint_port.md` (port, residency audit, parity table, profiling trajectory) and refresh the comparison artifacts. Consolidate `tests/avbd_native/` into one green suite.

## Critical files
- **Modify:** `dcr/avbd/reduced_coupled_avbd.py` (`:1103` insertion), `dcr/avbd/reduced_coupled_kernels.py` (device block), `dcr/avbd/reduced_support.py` (collapse split → single `q,q̇`).
- **Delete:** `dcr/avbd/reservoir.py`, `dcr/avbd/reduced_dcr_postkick.py` (+ split paths in the coupler).
- **Add (new body types / solver / viser):** cargo material kernels under `dcr/avbd/_solver/` (fem_rigid, abd, fem), a GPU XPBD path, `scripts/run_native_scenes_viser.py`, `tests/avbd_native/*`, `docs/avbd_native/dynamic_constraint_port.md`.
- **Reference (read-only):** `reduced_support_solve.py:365` (parity oracle); `dcr/twobody/{position_based,rigid_modal,reduced_body,warp_step}.py` (math + GPU-residency/profiling method); `dcr/avbd/_solver/solver_6dof.py` (body model + SAT collision + hooks); `two_band_coupling.html` (the equations).

## Verification
- Per-stage: `pytest tests/avbd_native/ -q` green + the stage's plot/MP4 + residency audit + parity number + profiling table.
- End-to-end: launch `scripts/run_native_scenes_viser.py --scene ledge --solver avbd --kind fem_rigid --device cuda:0`, drop the boulder → fem_rigid cargo tumbles with **zero penetration** and rings the support two-way; switch solver→xpbd and material→abd live and confirm parity-grade behavior + GPU residency in the HUD.

## Risk notes (heaviest first)
- **Stage 6 (GPU XPBD from scratch)** and **Stage 4 (affine body type in the device solver)** are the largest, highest-risk stages — each is a new solver/body path; keep the CPU references as strict parity oracles.
- **Stage 3 fem_rigid moving-body modal coupling:** the contact-to-mode Jacobian co-rotates (`R·Φ_c`) — more involved than the static support's fixed-grid `U_y`; `rigid_modal.py:point_jac_tan` is the reference.
- Supports become **real-FEM modal** (twobody upgrade) rather than the AVBD-Native synthetic basis — defensible and `CLAUDE.md`-preferred; flag with a `# DEVIATION:` for visual-parity expectations.
