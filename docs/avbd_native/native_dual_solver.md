# Native dual solvers (AVBD + XPBD) — build log

Two genuinely independent GPU-resident solvers, each solving the FULL problem
(rigid + box-box/floor contact + reduced-modal support + cargo) in its own
formulation, with the reduced modal expressed as a constraint NATIVE to that
solver. **No coupler, no shared solver segment.** Plan:
`prompts/native_dual_solver_build_plan.md`. Spec: `two_band_coupling.html`
(Approach B), Macklin 2016 (XPBD, §3.5 damping), AVBD §3.3 (AL).

## Test baseline (pre-build, branch `avbd-native-dynamic-constraint`)

`tests/avbd_native/` on commit `b71ff0f`: **101 passed, 4 failed**. The 4
failures pre-date this build and are out of scope here:

| Failing test | Cause | Disposition |
|---|---|---|
| `test_native_stacks::test_truck_lumber_stack_rides_ring_and_holds` | AVBD box-box friction instability on symmetric resting stacks (toppled 180°) | Decision #1 — tracked separately, NOT in this build |
| `test_dynamic_coupling::test_cpu_gpu_parity_machine_precision` | Coupler CPU/GPU parity | coupler test — migrate/retire in Stage 6 |
| `test_dynamic_coupling::test_cpu_gpu_early_horizon_agreement` | Coupler CPU/GPU agreement | coupler test — migrate/retire in Stage 6 |
| `test_production_scenes::test_avbd_production_scene_fem_rigid[shelf]` | Marginal threshold (`a.max()`=8.69e-10 vs 1e-9) | flaky threshold, pre-existing |

The **101 passing tests are the green-baseline contract** for the
behaviour-neutral AVBD refactor (Stages 0-1).

Environment: warp-lang 1.13.0, CUDA 12.9 / driver 13.2, RTX 3060 Laptop (sm_86),
Python 3.12.

## Stage 0 — shared constraint API + scaffolding ✅

Additive only (no edits to solver/world/scene logic):

* `dcr/avbd/_solver/constraints.py` — the ONE symmetric interface. Solver-agnostic
  constraint descriptions (`BoxBody`, `FloorContact`, `SelfCollision`,
  `ModalSupport`, `SupportContactCorner`, `Cargo`), the `Solver` runtime-checkable
  Protocol (the scene-facing surface), and `make_solver(kind, **kw)` factory.
  A `Solver` is structural — `Solver6DOF` already exposes the surface, so it is
  reused verbatim (chose Protocol over ABC because `last_modal_KE` is an instance
  attribute, which an ABC abstract-property would reject at instantiation).
* `dcr/avbd/_solver/solver_avbd.py` — `SolverAVBD(Solver6DOF)`. The canonical AVBD
  backend name; adds only the common `add_cargo` alias (→ `add_cargo_native`).
  No numerics change — behaviour-identical to `Solver6DOF`. The in-place rename
  `Solver6DOF → SolverAVBD` (+ reverse alias) is deferred to Stage 6 cleanup to
  keep Stage 0/1 low-risk; `Solver6DOF` stays importable.
* `dcr/avbd/_solver/solver_xpbd.py` — `SolverXPBD` stub raising `NotImplementedError`
  on construction (the rigid core lands in Stage 2).
* `dcr/avbd/_solver/xpbd_kernels.py` — placeholder for the Stage 2+ device kernels.
* `dcr/avbd/_solver/__init__.py` — additive exports of the above.

**Accept:** `tests/avbd_native/test_dual_solver_scaffold.py` (6 tests) green —
descriptions construct; `make_solver("avbd")` → `SolverAVBD` satisfying the
`Solver` Protocol; a smoke scene (box riding the live modal surface
`y_rest + U_y·q`) builds and steps 120× with no coupler, the support rings
two-way (modal KE > 0), no NaN; `make_solver("xpbd")` errors with a Stage-2
message; unknown kind raises. Representative existing native tests
(`test_native_modal_support`, `test_native_scene`, `test_modal_qblock`,
`test_fem_rigid_cargo` — 14 tests) stay green; package imports clean (no cycle).

No profiling artifact (Stage 0 adds no hot-path code).

## Stage 1 — AVBD ported onto the shared interface (behaviour-neutral) ✅

`solver="avbd"` now selects the **native AVBD solver** (the in-solver (z, q)
modal + cargo q-block) — NOT the external reduced coupler.

* `dcr/avbd/world.py` — `World._solver` is now a `SolverAVBD` (canonical name;
  == `Solver6DOF` behaviour). All paths (native + the transitional couplers)
  ride this AVBD solver.
* Scene builders (`reduced_scene_common.build_support_and_attach`,
  `reduced_dinner_table`, `reduced_fem_rigid_cargo`): `solver in ("avbd",
  "native")` → native path (`enable_reduced_modal_support` + `add_native_cargo`,
  no coupler); `solver="xpbd"` → XPBD coupler (until Stage 3/5); new
  `solver="avbd_coupler"` → the AVBD reduced coupler (transitional, deleted in
  Stage 6). `attach_reduced_coupled_avbd` is dropped from the `"avbd"` seam.
* Coupler tests pinned to the explicit `"avbd_coupler"` selector (the repoint
  forces this slice of the Stage-5/6 coupler-test migration forward, otherwise
  they'd `AttributeError` on the now-`None` coupler): `test_production_scenes`
  (avbd cases), `test_dynamic_coupling` (`_build`), `test_xpbd_coupling`
  (abd case), `test_fem_coupling` (3 sites), `test_fem_rigid_coupling` (device
  parity). `"avbd_coupler"` is the identical `attach_reduced_coupled_avbd` call,
  so those tests keep their exact prior behaviour.

**Accept:** `tests/avbd_native/test_stage1_avbd_native.py` green — the 4 production
scenes + the cargo scene build & step on `solver="avbd"` with
`reduced_coupled_coupler is None`, no NaN, cargo deforms; and **the repoint is
behaviour-neutral**: `solver="avbd"` reproduces `solver="native"` bit-for-bit
(positions, orientations, modal q via `np.array_equal`) — same code path, so the
validated M1/M2 native trajectories are preserved exactly. Full
`tests/avbd_native` suite: **114 passed, 4 failed** — the 4 failures are exactly
the pre-existing baseline set (no regressions; +13 new passing tests vs the
101-pass baseline). cuda-resident native cargo verified by
`test_native_production_cargo` (cuda) — unchanged.

Note (honesty): the production-scene *handles* (`ReducedSceneHandle.cargo_cube`)
still read cargo from the coupler via `getattr(coupler, …, None)`, so they read
`None` on the native path (cargo state is on `rs._native_cargo_*` / read via
`solver.cargo_a`). This pre-dates Stage 1; Stage 5 rewires the handles/HUD to
read native cargo from the solver.

No profiling artifact (Stage 1 is a wiring refactor; no new hot-path code — the
native AVBD hot loop is unchanged from the validated M1/M2 implementation).

## Stage 2 — standalone XPBD rigid core

`SolverXPBD` (`dcr/avbd/_solver/solver_xpbd.py`) is a genuinely independent
solver: its own Macklin "Small Steps" substep integrator + its own box-box/floor
contact, with NO coupler and NO AVBD host. It implements the shared
`constraints.Solver` surface for rigid bodies (modal/cargo raise until
Stage 3/4). `make_solver("xpbd", **avbd_kwargs)` is now a drop-in (AVBD-only
kwargs are swallowed).

### 2a — CPU reference ✅ (CLAUDE.md rule 6: obviously-correct numpy first)

Substep loop (Müller et al. 2020 "Detailed Rigid Body Simulation with XPBD" +
Macklin 2016 §3.5): predict x̂ = x + h v + h²g (+ quaternion ω-integrate) →
`iterations` Gauss-Seidel sweeps of the compliant unilateral NORMAL contact →
v = (x − x_prev)/h, ω = log(q ⊗ q_prevᵀ)/h → velocity-solve (inelastic normal
restitution + sequential-impulse Coulomb friction). Box-box uses a numpy SAT
15-axis + corner-clip manifold (the algorithm of `dcr/rigid/collision`, adapted
to this solver's layout); the floor is a plane per corner.

Four physics issues found + fixed while bringing the CPU reference up (each a
real XPBD pitfall, all caught by the acceptance tests):
1. **Friction energy injection** — purely-positional static friction drifts on a
   resting multi-corner box (the solver's own rotational transients pollute the
   position delta it keys off; a resting box slid off diagonally, |v|→1.9 m/s).
   Fixed by **velocity-level Coulomb friction** (Müller 2020 §SolveVelocities) —
   keyed off actual tangential velocity (~0 at rest), so it injects nothing.
2. **Zero-gap box-box** — coincident A/B anchors gave C=(p_a−p_b)·n≡0, so
   penetration never registered (upper box tunneled). Fixed by **split-the-
   penetration anchoring** (two distinct material points, ±½·pen along n).
3. **Missing restitution** — the position projection leaves a spurious upward
   velocity in v=(x−x_prev)/h (an upper box launches off a lower one). Fixed by
   nulling the relative normal velocity (e=0 inelastic) in the velocity solve.
4. **Symmetric-stack tip** — a *global* SAT penetration for all 4 manifold
   points gives no restoring torque, so a 4-high stack slowly tips (top box
   first, ~step 150→ runaway). Fixed with **per-corner penetration** (the deeper
   corner is pushed harder → the contact supplies the upright-restoring torque).

**Accept (CPU):** `tests/avbd_native/test_xpbd_rigid_core.py` (4 tests) green —
free fall integrates gravity; a dropped box settles at y≈half with no tunnel and
comes to rest; a **4-high box stack at rest holds** over 400 steps (it=30/sub=8:
tilt 0.28°, sink 1.0mm, top drift 1.25mm — vs the AVBD box-box path which
topples this same stack, the Decision #1 bug the XPBD solver does NOT inherit); a
tumbling box collides via real SAT with no floor tunneling. Scaffold test updated
(`make_solver("xpbd")` now constructs + conforms to the Solver Protocol; modal/
cargo raise Stage-3/4). Solver-agnostic numpy state arrays (`_X/_Q/_V/_W`) are
the single source of truth.

CPU timing (RTX 3060 host, numpy reference): ~0.4 s/step for a single drop
(it=20/sub=4); ~1.5 s/step for the 4-high stack (it=30/sub=8) — the reference is
intentionally un-accelerated; the device path below is the "then accelerate".

### 2b — device + CUDA-graph path + parity + profiling — PENDING

Remaining for the Stage-2 gate: port predict / normal-projection GS / velocity-
solve to warp kernels in `xpbd_kernels.py`, reuse the shared GPU SAT/face-clip
manifold from `kernels_6dof.py` for box-box geometry, CUDA-graph-capture the hot
loop, and add the CPU↔device parity test (≤ fp64 on a smooth drop) + the
residency audit + ms/step speedup table.

> **Device residency for SolverXPBD (2b + the device halves of Stages 3–4) is
> deferred to one batched pass** (user direction: "just do stage 3 cpu", then
> finish the remaining stages on the CPU path). The AVBD path stays
> cuda-resident throughout; only the new XPBD solver is CPU-only for now.

## Stage 3 — XPBD-native reduced-modal support (CPU) ✅

`SolverXPBD.set_modal_support` / `add_support_contact_corner` carry q ∈ R^r as a
native DOF (no coupler, no AVBD host), re-expressing the `reduced_coupled_xpbd`
math now native:
* modal predict q̃ = qⁿ + h·q̇ⁿ + h²·M_q⁻¹f_q^grav (freeze_qdot ⇒ h_pred=0);
* per-mode compliant modal-elastic C_i = q_i, α_i = 1/K_q[i,i], Macklin §3.5
  damped update via D_q[i,i] (`_project_modal_elastic`);
* unilateral support-contact rows C = corner_y − (y_rest + U_y·q), n = e_y,
  coupling the rigid 6-DOF and the modal q (∂C/∂q = −U_y) in the same GS sweep
  (`_project_support`); q̇ = (q − qⁿ)/h after the sweeps.
* freeze counterfactual: q̇ ≡ 0 exactly (the modal inertia term is deleted), so
  the frozen run carries zero modal KE.

**Accept (CPU):** `tests/avbd_native/test_xpbd_modal.py` (4 tests) green —
two-way counterfactual (dynamic rings, modal KE ≈ 0.1 J; frozen q̇≡0 ≈ 0);
free modal ring-down monotone non-increasing + decays (backward-Euler passive);
the ring lifts a bystander > 1.5× the frozen quasi-static rise; cross-solver
two-way SIGNATURE shared (both AVBD-native and XPBD-native ring under the drop
and go quiet when frozen).

Honesty note: the two native solvers do **not** agree to an order of magnitude
(AVBD ≈ 3e-4 J vs XPBD ≈ 1e-1 J on the shared scene). The AVBD native q-block
applies a conservative block-GS relaxation — it must, to keep box stacks upright
(memory `truck-stack-collapse-is-host-boxbox`) — which damps its ring far below
the compliant XPBD projection. The cross-solver agreement is **qualitative** (the
two_band_coupling.html signature), not quantitative; magnitudes are
solver-dependent. Device parity deferred (batched pass).

## Stage 4 — XPBD-native cargo materials (CPU) ✅

`SolverXPBD.add_cargo(body, cargo_body, support_rows)` registers the cube's
elastic block a ∈ R^k as its own block in Q = [q_support; a_cube], reusing
`dcr/avbd/cargo/*` body models:
* each support-contact row reads the cube's deformed corner — the gap gains
  flex = (R·Φ_c[pid]·a)_y and loads a via G_a = (R·Φ_c[pid])_y
  (`_cargo_support_grad`), w += G_aᵀ M_a⁻¹ G_a;
* the elastic block is projected compliant in the same GS sweep
  (`_project_cargo_elastic`): per-mode (α_i=1/K_q[i,i], Macklin §3.5) for the
  linear materials, abd's nonlinear V⊥ as the re-linearized compliant
  constraints from `body.elastic_constraints(a)`; ȧ=(a−aⁿ)/h.

**Accept (CPU):** `tests/avbd_native/test_xpbd_cargo.py` (5 tests) green — per
material (rigid/fem_rigid/fem/abd) the support rings two-way, no tunnel, and the
cube flexes (k>0) or carries no modes (rigid k=0); fem_rigid two-way-vs-frozen.
abd flexes on CPU XPBD (gentle drop); long-run stiff-abd stability under
sustained contact remains the documented XPBD-abd caveat. Device parity deferred.

## Stage 5 — both native solvers in every scene + viser (CPU) ✅

`World.solver_kind` ("avbd" | "xpbd") selects the backend via `make_solver` in
`__post_init__`. `World.add_box`/`add_floor` already used only the shared Solver
interface, so they host either backend unchanged; `enable_reduced_modal_support`
and `add_native_cargo` gained an XPBD branch (swap the tracked bodies' floor
contacts for support-contact rows sampling U_y; map cube corners → support rows
for cargo). Scene builders pass `solver_kind` and route `solver="xpbd"` to the
native path. Repoints: `solver="xpbd"` now selects SolverXPBD-native; the XPBD
coupler is the transitional `"xpbd_coupler"` (deleted Stage 6). XPBD-coupler
tests migrated to `"xpbd_coupler"`.

**Viser** (`scripts/run_native_scenes_viser.py`) directly rewritten: `SOLVERS =
("avbd", "xpbd")` (dropped the "native" pseudo-solver + the `solver="avbd"`=
coupler meaning); deleted the cargo→avbd fallback and the `cargo_material=None`
rigid-impactor block (both natives carry full cargo); removed `self.coupler` and
every `self.coupler.*` read — the cube state comes from `solver.cargo_a(idx)`,
the modal mirror from `solver.modal_q`, and the HUD (cube deform ‖a‖, support
modal KE, max penetration) from the native solver. Kept only the documented
abd→avbd routing in `_effective_solver`.

XPBD GS stability on the real support: the eigenbasis support is extremely stiff
(K_q up to ~3e11) and the q-block coupled to many support contacts is a stiff
linear system. AVBD solves it implicitly (unconditionally stable); XPBD's
Gauss-Seidel over (q ↔ many contacts) DIVERGES on the multi-body scenes (q→∞,
worse with more substeps — a divergence, not a stiffness limit). Fixed with a
**conservative under-relaxation** of the support→modal load
(`SolverXPBD.modal_relax = 0.25`) — the XPBD analogue of the AVBD native path's
conservative block-GS relaxation. A small support-contact compliance
(`support_compliance = 1e-8`) softens the contact→modal load too.

**Accept (CPU):** `tests/avbd_native/test_stage5_native_scenes.py` (16 tests)
green — the 4 production scenes × {avbd, xpbd} and the cargo scene × 4 materials
× {avbd, xpbd} all build & step with `reduced_coupled_coupler is None`, no NaN,
and the cube deforms (peak). The XPBD-native cuda-residency matrix is the
deferred device pass; AVBD-native cuda stays covered by
`test_native_production_cargo`.

## Stage 6 — remove the coupler architecture ✅

The reduced *coupler* is gone from the codebase (the production path was already
coupler-free after Stages 1+5). Deleted:
* the 4 coupler modules — `reduced_coupled_avbd.py`, `reduced_coupled_xpbd.py`,
  `reduced_coupled_kernels.py`, `reduced_coupled_xpbd_kernels.py`;
* `World.attach_reduced_coupled_avbd` / `attach_reduced_coupled_xpbd` + their
  imports (the `reduced_coupled_coupler` field stays, always `None`, so the dead
  `if coupler is not None` diagnostics branches are harmless);
* the `"avbd_coupler"` / `"xpbd_coupler"` scene selectors (scenes accept only
  `avbd` | `xpbd` now);
* the coupler-only `reduced_coupled_toy_minimum.py` scene;
* the coupler test files — `tests/avbd_native/{test_dynamic_coupling,
  test_xpbd_coupling, test_fem_coupling, test_abd_coupling,
  test_fem_rigid_coupling, test_production_scenes}.py` and
  `tests/avbd/{test_reduced_coupled_avbd, test_reduced_coupled_dynamics}.py`
  (their coverage — rigid + modal + cargo two-way, production scenes × material —
  is replaced by the native tests: `test_native_*`, `test_xpbd_*`,
  `test_stage5_native_scenes`). The two coupled-mode `test_iir_modal_resonator`
  functions are skipped (the coupled toy scene is retired).

Kept (separate, out of scope): the legacy STATIC `reduced_support` path
(`attach_reduced_support` + `reduced_support_solve.py` + the
`Solver6DOF.substep_*_hook` attributes it shares) — it is not the dynamic
reduced *coupled* coupler and still has live tests
(`test_reduced_support`, `test_reduced_static_support`).

**Accept:** the library + scenes import with no coupler (only a provenance
*comment* in `solver_xpbd.py` cites the re-expressed XPBD math); pytest collects
567 tests with no import errors; the legacy reduced_support + native + scaffold
tests pass. Both native solvers cover every prior production use.

Deferred (clearly noted): the XPBD device/CUDA-graph residency pass (Stage 2b +
the device halves of Stages 3–4); a handful of coupler-only *scripts*
(`run_coupled_*`, `run_reduced_coupled_avbd`, some `_diag_*`) still import the
deleted modules and would error if run — they are out of the library import
graph and the test suite, left for a scripts sweep.

## Final regression status (all stages, full `tests/` suite)

Full `tests/` suite after Stage 6: **521 passed, 30 failed, 2 skipped**. Every
one of the 30 failures is **pre-existing** — verified by re-running them on the
pre-work commit `b71ff0f`, where they fail identically:

| Failures | Track | Cause |
|---|---|---|
| 1 | `tests/avbd_native/test_native_stacks` | AVBD box-box symmetric-stack bug (Decision #1, out of scope) |
| 5 | `tests/avbd/{test_contact_extract, test_impulse_units}` | pre-existing on `b71ff0f` (older AVBD track, never green) |
| 24 | `tests/stageDV/{test_dcr_velocity_modes, test_post_solver_clip}` | separate DCR-velocity-modes track; deps `dcr/dcr`+`dcr/rigid` untouched (`git diff` empty) |

The 2 skips are the retired coupled-mode `test_iir_modal_resonator` functions.
**This build introduced 0 new failures and 28 new passing tests** (Stage 0 scaffold 6,
Stage 1 acceptance 4, Stage 2 rigid 4, Stage 3 modal 4, Stage 4 cargo 5,
Stage 5 native-scene matrix 16 — minus overlaps with deleted coupler tests).

## Stage 2b — XPBD device residency + optimization loop (the deferred pass)

Goal (user-requested follow-up): make `SolverXPBD` **device-resident** and
CUDA-graph-capturable; keep the CPU numpy path as the correctness reference;
then **loop-optimize until no huge improvement**.

### What was built
- **`xpbd_kernels.py`** — a full `wp.float64` re-expression of `_substep_cpu`:
  quat/mat helpers (byte-faithful to the numpy `_quat_*`), contact generation
  (floor corners + SAT 15-axis box-box, emitting in the exact `_CORNER_SIGNS`
  order), the position GS solve (normal → modal-elastic → cargo-elastic →
  support rows), velocity-from-Δx, modal/cargo commit, the velocity GS solve,
  and the max-penetration / modal-KE/PE diagnostics. **Fused into TWO phase
  kernels per substep** (`k_pos_phase`, `k_vel_phase`).
- **`solver_xpbd.py`** — `_build_device` (uploads all state to resident
  `wp.array` once), `_launch_substep` (2 `wp.launch`es), `_step_device`
  (capture+replay the CUDA graph; eager launch on CPU-warp), the
  `_warp_device` / `_device_compatible` dispatch, and device-aware read-back.
- Triggered by `device="cuda:0"` (GPU) or `_force_warp=True` (warp-on-CPU).
  `device="cpu"` (default) still runs the numpy reference.

### Design rationale — sequential, not parallel
The profiled hot spot is the support/modal GS sweep (~77 %), which is
**sequentially coupled through the shared modal vector `q`** (every support row
reads the `q` the previous row wrote). That chain cannot be colored into
independent parallel groups — all rows conflict through `q` — and the scenes are
tiny (≤17 bodies, ~68 sequential support rows). So the substep runs as
**compiled sequential `dim=1` kernels**: this preserves the exact GS ordering
(→ fp64 parity) and removes the per-row Python/numpy overhead that made the CPU
path slow. # DEVIATION: none in the math; only host-loop / launch overhead is removed.

### Parity (gate PASSED) — device vs numpy, max |Δ| over 120 steps
| scene | backend | Δpos | Δquat | Δmodal_q |
|---|---|---|---|---|
| cargo rigid | warp-cpu | 0 | 1.6e-15 | 8.1e-16 |
| cargo rigid | cuda | 0 | 4.0e-15 | 1.2e-15 |
| cargo fem / fem_rigid | warp-cpu | 6.0e-8\* | 1.8e-7\* | 2.8e-9 |
| cargo fem / fem_rigid | cuda | 6.0e-8\* | 1.0e-7\* | 2.3e-9 |
| box-box 4-stack | warp-cpu | 0 | 0 | — |
| box-box 4-stack | cuda | 0 | 0 | — |

(\*) the 6e-8 / 1e-7 are **float32 read-back rounding** (`positions()` /
`orientations()` return float32); the float64 state (`modal_q`) agrees to ~1e-9.
The box-box stack is **bit-identical** because the device SAT emits contacts in
the exact `_CORNER_SIGNS` order. Test: `tests/avbd_native/test_xpbd_device.py`.

### Benchmark + optimization loop (ms/step, RTX 3060 Laptop, 60 steps)
`scripts/bench_xpbd_device.py`. **Iteration 0** (granular, ~10 launches/substep):

| scene | nb | numpy | warp-cpu | cuda | ×wcpu | ×cuda |
|---|---|---|---|---|---|---|
| cargo | 1 | 16.2 | 1.38 | 5.83 | 11.8 | 2.8 |
| shelf | 6 | 56.8 | 1.67 | 15.8 | 34 | 3.6 |
| dinner | 17 | 211 | 2.93 | 76 | 72 | 2.8 |
| truck | 12 | 511 | 2.41 | 53.6 | 213 | 9.5 |
| ledge | 5 | 328 | 1.67 | 20.2 | 197 | 16 |

**Iteration 1** (kernel fusion → 2 launches/substep):

| scene | nb | numpy | warp-cpu | cuda | ×wcpu | ×cuda |
|---|---|---|---|---|---|---|
| cargo | 1 | 16.3 | 0.88 | 5.38 | 18.5 | 3.0 |
| shelf | 6 | 56.1 | 1.19 | 16.6 | 47 | 3.4 |
| dinner | 17 | 211 | 2.41 | 78 | 88 | 2.7 |
| truck | 12 | 501 | 1.86 | 53.9 | 269 | 9.3 |
| ledge | 5 | 324 | 1.19 | 20.3 | 271 | 16 |

Fusion helped **warp-cpu** (~1.5× — fewer dispatch overheads) but **not cuda**.
A sync probe ruled out the per-frame diag readback (cargo 5.4→4.9 ms without it);
fusion (60→12 graph nodes) left cuda unchanged.

### Plateau — honest conclusion
The CUDA cost is **not** launch-node overhead — it is that the entire
sequentially-`q`-coupled substep runs on **one GPU thread** (a single GPU core
is ~5–10× slower than a CPU core), and the scenes are too small for the only
parallel work (per-body predict/velocity-update, ≤17 bodies) to matter. The one
remaining lever — parallelizing the GS sweep via contact graph-coloring + a
Jacobi/colored modal update — would **break the exact GS-order parity** (a
documented deviation) and is essentially the AVBD solver's machinery, explicitly
out of scope (build-plan parity gate + Decision #1 "track separately"). So the
loop stops here:

- **warp-CPU is the fastest backend at these scene sizes** — 12–271× over the
  numpy reference, parity-exact. It is genuinely device-resident (state in
  `wp.array` on the cpu device; LLVM-compiled kernels).
- **The CUDA-resident path is delivered, parity-correct, and graph-captured.**
  It is 2.7–16× over numpy but slower than warp-cpu here; it is the right
  substrate once a scene is large enough to parallelize — which needs the GS
  parallelization above (a separate task).
- The headline win is the **compiled warp path (either backend): 1–2 orders of
  magnitude over the numpy reference**.

### Residency audit
The captured hot loop (`substeps` × {`k_pos_phase`, `k_vel_phase`}) issues only
`wp.launch` — no `.numpy()` / `synchronize` inside. State (X/Q/V/W, modal q/q̇,
cargo a, the contact pool) lives in `wp.array` on the device for the whole frame;
built once in `_build_device`, never reallocated. One 4-float diagnostic copy
happens per **frame** (outside the captured region) for the HUD/tests; it can be
made lazy.

### Scope / limitations
- **abd** cargo (nonlinear V⊥) and the rare **>1-cargo** case fall back to the
  numpy reference even on cuda (`_device_compatible()`); documented + tested
  (`test_abd_falls_back_to_numpy_on_cuda`).
- `device="cpu"` (default) still runs numpy — the parity reference (CLAUDE.md
  rule 6). warp-cpu is opt-in via `_force_warp`; cuda via `device="cuda:0"`.

## Post-build fixes (surfaced by the viser's spinning-cargo drop)

The viser drops the cargo cube spinning (`--spin 4.0`). Two distinct XPBD-support
defects only showed up under that tumble; AVBD's retyped-floor support path was
immune to both (it arrested the spin before a flip, and it carried floor
friction). Both are reproduced by `tests/avbd_native/test_cargo_spin_tunnel.py`.

### Fix 1 — anti-tunnel: constrain all 8 cube corners (commit `dca47a7`)
The XPBD support registered only the cube's *original-bottom* 4 corners. A cube
that tumbles ~180° during the fall lands on its now-bottom (unconstrained) face
and passes straight through, hanging one body-height below with its top flush
to the surface. The support is unilateral (`C = corner_y − surf ≥ 0` ⇒ inactive),
so registering **all 8 corners** is free when upright and catches whatever face
lands. Fix in `world.enable_reduced_modal_support` (XPBD branch).

### Fix 2 — support Coulomb friction (frictionless rotation)
After Fix 1 the cube rested on the support but **spun forever** (~0.155 rad/s,
never decaying). Root cause, verified by probe: the support row is normal-only
(`n = e_y`), so its torque arm `cross(r_w, e_y)` has a **structurally-zero yaw
component** — it physically cannot resist vertical-axis spin. The residual ω was
purely yaw (`ω = [3.5e-5, −0.1555, 1.2e-4]`). AVBD damped it because its support
is a *retyped floor* row that keeps Coulomb friction; the native re-expression
(`_project_support`) dropped it.

Fix: the support row inherits the cube's floor μ (`world.py` captures it before
deleting the floor entry) and runs a tangential Coulomb-friction velocity pass —
`_solve_velocity_support`, mirroring the friction half of `_solve_velocity`
(null the corner's tangential velocity, clamp to the cone `|j_t| ≤ μ·λ_n/h`,
`λ_n = sc.lam`). **Friction-only — no `e=0` normal restitution** on the support
(its normal is a soft modal-compliant contact; an inelastic kick would corrupt
the q̇ coupling). Re-expressed identically into the warp kernel (`velsolve_f`
extended with the support arrays; `sup_mu`/`sup_jt` added to the resident pool),
interleaved in the same velocity-iteration order so device parity holds.

Result (cube dropped 1 m with spin 4 rad/s, fem_rigid): |ω| → ~0 by ~step 100 on
all backends (was 0.155 sustained). Device parity preserved with friction active:
**warp-cpu 4.6e-10, cuda 2.3e-9** max |Δ| vs numpy over 200 steps. The existing
device parity suite (frictionless support, μ=0) is unchanged (9 pass).

## Stage 2c — PARALLEL CUDA path (per-constraint kernels + averaged Jacobi)

The Stage-2b device path was a single-thread `dim=1` port of `_substep_cpu` — it
preserved exact serial-GS order for bit-parity but used **one** GPU thread, so
CUDA was 14–70× *slower* than warp-CPU. AVBD, by contrast, parallelizes the same
class of work (per-body kernels + graph coloring + same-color Jacobi). The fix:
re-express the XPBD substep as **per-constraint parallel kernels with averaged
Jacobi** (Macklin et al. 2014, "Unified Particle Physics", §averaged constraint
projection): every constraint projects from the same start-of-iteration state,
scatters its body/modal correction into a scratch buffer via fp64 atomics, and a
per-body apply divides by the constraint count touching that body. Same
constraints, compliances and forces as serial — only the SCHEDULE changes (serial
GS → averaged Jacobi), the same deviation the colored AVBD primal takes.

- New `pk_*` kernels in `xpbd_kernels.py`; new `_launch_substep_parallel` in
  `solver_xpbd.py`. All launch dims are static (pool capacities, early-out past
  the live count) so the whole substep still captures into one CUDA graph.
- **Auto-select** (`_parallel_device=None`): parallel on CUDA, serial `dim=1` on
  warp-CPU (the parallel path's ~hundreds of tiny launches/frame — no graph there
  — cost more than they save on a CPU; the 2-launch serial kernel is far faster).
  So warp-CPU keeps its Stage-2b speed; only CUDA switches.
- Jacobi accumulators are flat `float64[3·nb]` (scalar fp64 atomics; the
  vec3d-atomic path is avoided). The serial `dim=1` kernels are retained and stay
  the bit-parity reference.

### Profile↔optimize loop (CUDA ms/step, RTX 3060 Laptop, 100 steps)
Each step was profiled (the discriminating tool: scale the iteration count — a
flat curve means a per-step *fixed* cost, a rising one means the *solve*):

| iter | change | cargo | dinner | truck |
|---|---|---|---|---|
| — | **Stage-2b serial dim=1** | 12.85 | 226.6 | 143.2 |
| 0 | parallelize solve (gen still dim=1) | 5.71 | 52.2 | 46.2 |
| 1 | fuse per-iter launches (7→3) | 4.37 | 51.4 | 45.5 |
| 2 | **parallelize contact gen** (O(nb²) SAT) | 4.38 | **9.66** | 15.8 |
| 3 | parallelize prep helpers (count/velprep) | 4.48 | **8.55** | 16.2 |

- **iter-2 was the big one**: the iteration-scaling probe showed dinner was *flat*
  in iters (≈46 ms fixed) — the O(nb²) box-box SAT ran in the single `dim=1`
  prep thread. Fanning it over body-pairs (atomic append; order-independent since
  the solve is Jacobi) cut dinner 5.3×, truck 2.9×.
- **iter-1** helped only the tiny cargo scene (dispatch-bound); **iter-3** gave
  ~12% on dinner → **no huge gain ⇒ plateau, loop stopped.**

**Net vs the Stage-2b serial CUDA path: cargo 2.9×, dinner 26×, truck 9× faster.**

### Honest conclusion
- warp-CPU is **still the fastest backend** (0.9 / 3.1 / 2.2 ms): the RTX 3060 runs
  fp64 at 1:64 of fp32, the scenes are small, and even fully parallel the GPU
  can't beat a native-fp64 CPU here. CUDA is now within ~3–7× of warp-CPU (was
  14–70×) — the GPU path is no longer pathological.
- The remaining CUDA cost at high iteration counts is the per-iteration
  **support-row solve** (`pk_support_jacobi`: ~96–136 threads, each looping the
  r≈24 modes — low occupancy). Lifting it needs a per-row reduction redesign
  (one thread per (row,mode), atomic surf/w reduction → dlam → scatter); that's
  high-complexity for a sub-2× gain that still won't beat warp-CPU, so it is the
  **identified-but-deferred** next lever, not done.

### Stiff-modal stability (the viser blow-up fix)
The viser exposes a **modal-impedance gain** slider (0.25–16×). The first parallel
build was stable at default (g=1) but **blew up (V/X → NaN) at g ≥ 4** — the user
hit it live. Diagnosis (verified by sweep, parallel vs serial): the impedance gain
multiplies the modal mass uniformly, so `wq` (modal inverse-mass) `= g`, and the
support→q drive `∝ wq = g`. In **serial GS** the per-row updates self-limit (each
row sees the prior rows' q); the **averaged Jacobi sum does not**, so at high g the
g-scaled drive over-shoots and diverges (serial survives all g). Averaging by the
active-row count alone only held to g≈2.

Fix: **per-mode under-relaxation of the support→q drive by `mq` (= 1/g)** in
`pk_support_jacobi` (`mri = modal_relax · min(1, mq[i])`). Because the modes are
mass-normalized (`mq=1` at g=1), the **default is byte-unchanged**; at high g it
cancels the over-drive. The relaxation does not move the fixed point (the C=0
surface), only the convergence rate — so the physics is preserved, just gentler.
Verified (parallel CUDA, 1500 steps): dinner `|X|max = 0.59` flat across g ∈
{1,2,4,8,16} (was BLEW@1); truck bounded (≤4.94; the residual at g=16 is the
pre-existing box-box lumber-stack vigor, not q-divergence). Default cargo unchanged
(rests, spin damps, modal ring KE ≈ 0.02). Regression:
`test_cuda_parallel_high_impedance_stable[4,16]`.

### Verification
- Bit-parity (serial device kernels): `test_cuda_cargo_parity_serial`,
  `test_cuda_stack_parity_serial_and_graph` force `_parallel_device=False`
  (cuda serial == numpy to 1e-5/1e-6).
- Parallel path: physical agreement, not bit-parity — `test_*_cargo_parallel_agrees`
  (cube settles within 2e-3 of serial, finite, graph-captured),
  `test_cuda_stack_parallel_stable` (stack stays finite/bounded),
  `test_cuda_parallel_high_impedance_stable` (no blow-up at g=4,16). Multi-body
  settle (dinner/truck) matches serial closely; truck's upper lumber stack settles
  a little differently (the known host box-box instability).
