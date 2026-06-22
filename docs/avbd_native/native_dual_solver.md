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
