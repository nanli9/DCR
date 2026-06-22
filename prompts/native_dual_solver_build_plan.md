# Plan — Two independent native solvers (AVBD + XPBD), reduced modal as a native constraint, no coupler

> **TRIGGER:** the user starts this build by saying **“build native dual solvers”**
> (equivalently “execute the native dual-solver plan”). On that trigger, read this
> file top-to-bottom, confirm the 5 open decisions below, then begin at Stage 0.
>
> Build prompt for a fresh context. Read this top-to-bottom before writing code.
> Branch: continue on `avbd-native-dynamic-constraint` (or fork a new branch off it).
> Reference spec for the constraint math: `two_band_coupling.html` (user holds it;
> it is cited throughout the code but not checked in). Cite it + the foundation
> docs in every touched function; mark any divergence with `# DEVIATION:`.

## The goal (what the user actually wants)

Two **genuinely independent** GPU-resident physics solvers:

- a native **AVBD** solver, and
- a native **XPBD** solver,

each of which solves the **entire** problem in its own formulation:
rigid-body dynamics **+ body↔body box-box / floor contact + the reduced-modal
support**. The reduced-modal support is expressed as a **constraint native to
each solver** (an Augmented-Lagrangian constraint block for AVBD; a compliant
position-based constraint for XPBD). `two_band_coupling.html` is the single
constraint spec both must realize.

Hard requirements:
- **No coupler.** The reduced modal is "just another constraint" inside each
  solver, not an external object hooked into a host solve.
- **No shared solver segment.** The XPBD solver must NOT route its rigid
  integration / box-box / floor contact through the AVBD solver. Each solver is
  self-contained. (Today the "xpbd" path is only an XPBD *modal coupler* riding
  the AVBD host for rigid + box-box + per-corner floor — that is exactly the
  shared segment to eliminate.)
- Scenes select a **solver object** directly (`SolverAVBD` or `SolverXPBD`); same
  scene, two solvers, no coupler indirection.

## Current state (verified this session — the mismatch to fix)

- **One** rigid solver exists: `dcr/avbd/_solver/solver_6dof.py::Solver6DOF`. It is
  the AVBD (Augmented Lagrangian) solver and owns: inertial predictor; colored
  AVBD primal solving **box↔box** (SAT 15-axis + Sutherland-Hodgman face-clip
  manifold, up to 4 pts/pair) + **box↔floor** with the AL contact/friction force
  `f = clamp(c_penalty·C + λ, ±μ|λ_n|)` (`kernels_6dof.py`); dual/penalty update;
  velocity update.
- **AVBD already treats the reduced modal as a native constraint** — the (z,q)
  path (Approach B / M1 / M2) is built INTO `Solver6DOF`: `set_modal_support`,
  `add_support_contact_corner`, `add_cargo_native`, the augmented q-block
  (`solver_6dof.py` + `dcr/avbd/_solver/modal_qblock_kernels.py`). **No coupler,
  no hook.** This is the template for what the XPBD solver must do natively. It is
  done + GPU-resident + parity-tested (tests/avbd_native/test_native_*).
- **Couplers (to be removed):** `dcr/avbd/reduced_coupled_avbd.py`,
  `reduced_coupled_xpbd.py` (+ `reduced_coupled_kernels.py`,
  `reduced_coupled_xpbd_kernels.py`). They hook into `Solver6DOF` via
  `substep_begin_hook / iteration_hook / substep_end_hook` (`world.py:454-456`,
  `622-624`) and add the body↔support modal constraint EXTERNALLY. The XPBD
  coupler explicitly rides "the GPU solver's real per-corner FLOOR collision"
  (its own header) — the shared AVBD segment. `solver="avbd"|"xpbd"` in the
  scenes currently selects a coupler; `solver="native"` uses the AVBD-native path.
- **Body↔body box-box is never in any coupler** — it is only the host AVBD
  primal. So today `solver="xpbd"` still solves all rigid contact with AVBD.
  (Verified: avbd vs xpbd give bit-identical stack trajectories.)

## What is reusable vs new

Reusable (solver-agnostic or AVBD-side template):
- **Contact geometry**: the SAT + face-clip **manifold generation** in
  `kernels_6dof.py` (`obb_contact_manifold_6dof`, broadphase LBVH, `_sat_obb`).
  It produces contact points / normals / tangents independent of how they are
  *solved*. The XPBD solver should reuse the manifold, then project contacts
  XPBD-style instead of AVBD-style.
- **Reduced-support data layer**: `dcr/avbd/reduced_support.py` (Mq/Kq/Dq,
  U_points, mode shapes) — shared, solver-agnostic.
- **Cargo body models**: `dcr/avbd/cargo/{fem_rigid,abd}.py` (Mq_block/Kq_block/
  Dq_block, corner_modal Φ_c, internal_grad/hess for abd) — solver-agnostic.
- **AVBD-native modal constraint** (`Solver6DOF` augmented q-block) — the
  reference behaviour the XPBD-native modal must agree with (cross-solver
  signature: dynamic ring vs frozen-q̇ counterfactual).
- **XPBD modal-constraint math**: `reduced_coupled_xpbd.py` /
  `reduced_coupled_xpbd_kernels.py` (per-mode compliant constraint
  α_i = 1/K_q[i,i], Macklin §3.5 damped update, unilateral floor compliance).
  Re-express it INSIDE the new standalone XPBD solver — same projection math,
  but now over the solver's own bodies/contacts, not a coupler hook.

New:
- **`SolverXPBD`** — a standalone XPBD solver parallel to `Solver6DOF`: XPBD
  substep loop (predict → compliant-constraint Gauss-Seidel projection →
  velocity from position delta), **its own** box-box + floor contact as XPBD
  constraints (with friction), and the reduced-modal as native XPBD constraints.
- A **common solver interface** both solvers implement, so scenes are
  solver-agnostic.

## Stacking context from this session (validate, don't inherit silently)

The truck lumber stack collapse the user hit is an **AVBD box-box friction
instability on perfectly-symmetric resting stacks** (NOT modal, NOT coupler):
friction=0 holds, a 0.1 mm symmetry break holds, γ=1.0 / β=1e6 hold; the contact
frame sign-flips step-to-step and pumps energy (see memory
`truck-stack-collapse-is-host-boxbox`). Implications for THIS build:
- The new **XPBD** solver gets its **own** box-box contact — it will NOT inherit
  this AVBD bug, but it must be validated on stacking in its own right (XPBD
  position-based contact stacks differently; warm-starting / substep count
  matter).
- Decide (below) whether the **AVBD** box-box friction bug is fixed as part of
  this work or tracked separately.

## Cross-cutting rules (every stage)

- **CPU reference first** (CLAUDE.md rule 6): write the obviously-correct numpy
  XPBD solve, pass acceptance, THEN the warp/device version; keep the CPU path as
  the parity reference. CUDA is in scope on this branch.
- **Parity gate:** every device change matches its CPU reference to fp64 roundoff
  on a smooth trajectory (float32-ULP tracking with engaged contact) before it
  lands.
- **Residency gate:** `step()` issues only `wp.launch` in the hot loop — no
  `.numpy()` / `synchronize` / host readback; state stays in `wp.array` on
  `cuda:0`; fixed launch sequence CUDA-graph-captured. Audit each stage.
- **Cite the math:** `two_band_coupling.html` (+ Macklin 2016 XPBD, §3.5 damping;
  AVBD §3.3 AL) in touched functions; `# DEVIATION:` for any divergence.
- **Profiling artifact** per stage: ms/step + speedup table + parity number.
- **No new dependency** (CLAUDE.md).

## Stages

### Stage 0 — Design the SHARED CONSTRAINT API (decision #2) + scaffolding
- Design ONE symmetric **constraint interface** that both solvers consume. Model
  each physical interaction as a pluggable constraint with a solver-agnostic
  description and two projection backends (AVBD Augmented-Lagrangian, XPBD
  compliant): **box↔box contact**, **box↔floor**, **reduced-modal support**
  (per-mode elastic + support-contact rows reading `y_rest + U_y·q`), **cargo
  modal block** (rigid k=0 / fem_rigid / fem / abd). Geometry (the SAT/face-clip
  manifold) is shared; only the per-constraint *projection* differs per solver.
- Define the **common solver interface** the scenes use: `add_box`, `add_floor` /
  `add_floor_contact_box`, `enable_self_collision`, `set_modal_support`,
  `add_support_contact_corner`, `add_cargo`, `step`,
  `positions/orientations/velocities`, `modal_q` / `cargo_a` / `last_modal_KE`
  (+ the diagnostics the viser HUD reads — see Stage 5).
- File layout: `dcr/avbd/_solver/solver_avbd.py` (the refactored `Solver6DOF`,
  alias `Solver6DOF = SolverAVBD`), new `dcr/avbd/_solver/solver_xpbd.py` +
  `xpbd_kernels.py`, and a shared `constraints.py` (the interface + geometry glue).
- Scene selection: scenes take `solver=` mapping to a solver class; no coupler.
  Keep the coupler path importable until Stage 6.
- **Accept:** the constraint interface + both solver classes exist; `solver="avbd"`
  resolves to `SolverAVBD` over the new interface (xpbd may be a stub erroring
  until Stage 2); a throwaway smoke scene builds; existing AVBD-native tests green.

### Stage 1 — Port the AVBD solver onto the shared interface (behavior-neutral)
- Re-express the existing `Solver6DOF` AVBD path (rigid + box-box + floor + native
  modal + cargo) as the AVBD projection backend of the Stage-0 constraint
  interface, becoming `SolverAVBD`. This is a **refactor, not a behavior change** —
  same AL math, same trajectories.
- Make the scenes use `SolverAVBD` directly for `solver="avbd"`; drop
  `attach_reduced_coupled_avbd` from the scene seams (`scenes/reduced_scene_common.py`
  + `reduced_*` scenes). Confirm the native AVBD path covers everything the AVBD
  coupler did (support coupling, cargo, multi-body, the 4 production scenes).
- **Accept:** the refactor is **behavior-neutral** — the full `tests/avbd_native`
  AVBD/native suite passes with trajectories matching pre-refactor to fp64
  (snapshot a few before refactoring); all 4 production + cargo scenes build/step
  on `solver="avbd"` with NO coupler (`world.reduced_coupled_coupler is None`),
  no NaN, cuda-resident; document any scene the native path can't yet reproduce.

### Stage 2 — Standalone XPBD rigid core (the big new piece)
- Build `SolverXPBD` as the **XPBD projection backend of the Stage-0 shared
  interface** — it consumes the same constraint descriptions as `SolverAVBD`,
  projecting them compliant-style. XPBD substep integrator (Macklin "Small Steps"): per
  substep predict `x̂ = x + h v + h²g`, then `iterations` Gauss-Seidel sweeps of
  **compliant** constraints, then `v = (x − x_prev)/h` (and the quaternion
  analogue for orientation).
- **Box↔box + floor contact as XPBD constraints**: reuse the SAT/face-clip
  **manifold** from `kernels_6dof.py` (geometry only), then project each contact
  as a compliant unilateral constraint (α_contact = compliance/h², λ ≥ 0) with
  Coulomb friction (positional friction, |Δx_t| ≤ μ Δx_n). CPU ref first, then
  device + CUDA-graph.
- **Accept:** (a) CPU↔device parity ≤ fp64 on a smooth drop; (b) **stacking
  validation** — a 4-high box stack at rest holds (report tilt/sink over 400
  steps; this is the user's original concern, now in the XPBD solver); (c) a
  tumbling box collides via real SAT, no tunneling; (d) residency audit +
  profiling table.

### Stage 3 — XPBD-native reduced-modal constraint
- Add the reduced-modal support to `SolverXPBD` as native XPBD constraints
  (mirror `set_modal_support` / `add_support_contact_corner`): per-mode compliant
  modal elastic constraint (α_i = 1/K_q[i,i], Macklin §3.5 damped update for D_q)
  + the unilateral support-contact rows reading the live surface `y_rest + U_y·q`,
  all projected in the same GS sweep as the rigid contacts. Carry `(q, q̇)`.
  Re-use the projection math from `reduced_coupled_xpbd.py`, now native (the body
  rides `SolverXPBD`'s OWN floor/box-box, no AVBD host).
- **Accept:** (a) CPU↔device parity; (b) **two-way counterfactual** — dynamic `q`
  rings and launches a bystander; frozen `q̇≡0` gives ~0 modal KE (the
  `two_band_coupling.html` signature); (c) **cross-solver agreement**: AVBD-native
  and XPBD-native produce the same qualitative modal signature / same-order
  energy on a shared scene; (d) passivity (total energy monotone non-increasing
  on a free ringdown).

### Stage 4 — XPBD-native cargo materials
- Add `add_cargo` to `SolverXPBD` for the cargo cube's elastic block
  (rigid k=0 / fem_rigid / fem / abd), reusing `dcr/avbd/cargo/*` body models and
  the augmented modal-vector convention `Q = [q_support; a_cargo]`. abd's
  nonlinear V⊥ as compliant constraints (the XPBD coupler already had this;
  see honesty note: stiff abd may need more sweeps — document, don't fake).
- **Accept:** the cube deforms + rings two-way + no tunnel, per material, CPU +
  cuda-resident; cross-solver order-of-magnitude agreement vs AVBD-native.

### Stage 5 — Both native solvers in all scenes + viser + regression
- Wire `solver="avbd"|"xpbd"` (native objects) through the cargo scene + the 4
  production scenes. No coupler anywhere.
- **MANDATORY: directly rewrite `scripts/run_native_scenes_viser.py`** for the new
  architecture (the user explicitly wants this done, not described). Concrete edits
  (the current file assumes a coupler + a "native" pseudo-solver):
  - `SOLVERS = ("avbd", "xpbd")` — both native; **drop the "native" pseudo-option**
    and the `solver="avbd"=coupler` meaning.
  - `_build`: delete the `if eff == "native" and self.scene == "cargo": eff="avbd"`
    fallback and the `if eff == "native": cand["cargo_material"] = None` block —
    BOTH native solvers now carry full cargo (rigid/fem_rigid/fem/abd), including
    the cargo scene.
  - Remove `self.coupler = self.world.reduced_coupled_coupler` and every
    `self.coupler.*` read. The deformable cube state now comes from the **solver**:
    `_deform_verts` reads `z[7:] = self.world._solver.cargo_a(idx)` (not
    `self.coupler.cargo_a[idx]`); the run-loop's `if c is None` modal mirror
    (`rs.q[:] = solver.modal_q`) becomes the only path.
  - HUD: replace the `if c is not None:` coupler-diagnostics branch with solver
    reads — `cube deform E`, `support modal KE`, `max penetration` all from the
    native solver's diagnostics (add solver accessors if missing; the "n/a (rigid
    impactor)" placeholder goes away — cargo deforms on both solvers now).
  - `_effective_solver`: keep ONLY whatever routing the Stage-4 honesty note
    actually requires (e.g. if XPBD-native abd needs more sweeps or isn't stable,
    document + route; otherwise remove all routing so avbd/xpbd are independent).
  - Update the module docstring (lines 1-41) to describe two native solvers, no
    coupler.
- **Accept:** full scene × solver × material × device matrix builds/steps/no-NaN/
  no-tunnel, cuda-resident; **the viser flips avbd↔xpbd live with NO coupler and
  cargo deforming under both**; profiling table; the full `tests/avbd_native`
  suite green (update tests off the coupler).

### Stage 6 — Remove the coupler architecture
- Delete `reduced_coupled_avbd.py`, `reduced_coupled_xpbd.py`,
  `reduced_coupled_kernels.py`, `reduced_coupled_xpbd_kernels.py`, the
  `attach_reduced_coupled_*` methods, and the `substep_begin/iteration/substep_end`
  hook plumbing in `Solver6DOF` IF nothing else needs it (check
  `reduced_support_coupler` legacy path first). Migrate/retire the coupler tests
  (`test_dynamic_coupling.py`, `test_xpbd_coupling.py`, `test_production_scenes.py`
  coupler cases) to the native solvers.
- **Accept:** repo builds with no coupler; both native solvers cover every prior
  use; suite green; docs updated (`docs/native_modal_support.md`, a new
  `docs/avbd_native/native_dual_solver.md`).

## Decisions (LOCKED with the user 2026-06-22)

1. **AVBD box-box friction bug** (symmetric-stack collapse, this session) →
   **TRACK SEPARATELY.** Not in scope here. The XPBD solver gets fresh contact
   regardless; the AVBD box-box friction hardening is its own later task (see
   memory `truck-stack-collapse-is-host-boxbox`). Do NOT expand this build to fix
   it — but DO still validate stacking on the new XPBD solver (Stage 2).
2. **AVBD solver scope** → **RESTRUCTURE to a shared constraint API.** This is the
   bigger refactor the user chose: design ONE symmetric constraint interface that
   BOTH solvers consume (contact / floor / reduced-modal / cargo expressed as
   pluggable constraints), and re-express the existing `Solver6DOF` AVBD path over
   it. This reshapes Stage 0 (design the shared interface) and Stage 1 (port AVBD
   onto it) — see those stages. Preserve the validated M1/M2 AVBD physics through
   the refactor via the existing parity tests (refactor must be behavior-neutral
   for AVBD: same trajectories before/after, to fp64 on the native tests).
3. **XPBD contact friction** → **POSITIONAL (Macklin)**, projected inside the
   substep Gauss-Seidel sweep.
4. **Coupler removal** → **DELETE in Stage 6** (couplers + hooks + migrate tests).
5. **Naming** (defaulted, user may override): rename `Solver6DOF` → **`SolverAVBD`**
   and add **`SolverXPBD`** as the matched pair over the shared interface; keep a
   `Solver6DOF = SolverAVBD` alias during migration so existing imports/tests don't
   break mid-refactor, then remove the alias in Stage 6.

## Key references
- AVBD-native modal template: `dcr/avbd/_solver/solver_6dof.py` (`set_modal_support`,
  `add_support_contact_corner`, `add_cargo_native`), `modal_qblock_kernels.py`.
- Contact geometry to reuse: `kernels_6dof.py` (`obb_contact_manifold_6dof`, `_sat_obb`).
- XPBD modal math to re-express: `reduced_coupled_xpbd.py` (+ kernels).
- Reduced support data: `reduced_support.py`. Cargo: `dcr/avbd/cargo/*`.
- Session memory: `truck-stack-collapse-is-host-boxbox`,
  `native-modal-zq-m1-m2-progress`, `avbd-native-dynamic-port-progress`.
- Spec: `two_band_coupling.html` (Approach B); Macklin 2016 (XPBD) + §3.5 damping.
