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
