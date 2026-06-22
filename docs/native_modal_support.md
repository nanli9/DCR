# Native modal support — the monolithic `(z, q)` solve (M1)

Implements `prompts/monolithic_zq_solver_implementation_prompt.md` /
`../DCR-AVBD-Native/two_band_coupling.html` (Approach B): the support's modal
amplitude `q ∈ ℝ^r` is promoted to a **native DOF inside `Solver6DOF`**,
co-solved with the rigid bodies `z` and box-box self-collision in one
backward-Euler step. **No coupler, no hook** on this path.

## What `q` is (and isn't)

- `q` is the **slab's** deformation field, compressed to `r` mass-normalized
  modal amplitudes (`M_q = I`, `K_q = diag(ω²)`, `D_q` Rayleigh). It is a
  second-order DOF `(q, q̇)`. **One `q` for the whole slab**, shared by every
  body resting on it.
- The rigid bodies each keep their own 6-DOF `z = [x; orientation]`. `q` is
  **not** a body DOF — bodies and `q` are *coupled* through contact, not shared.
- The slab is not a rigid body in the solver; it exists only as `q` + the
  per-contact mode shapes `U_y`.

## Architecture (where it lives)

| Piece | Location |
|---|---|
| Modal state `q/q̇/M_q/K_q/D_q`, predictor `q̃`, `q̇` commit | `dcr/avbd/_solver/solver_6dof.py` (`set_modal_support`, `_modal_predict`, `_modal_commit`) |
| `SUPPORT_CONTACT_6DOF` row — reads live surface `y_rest + U_y·q` in-kernel | `kernels_6dof.py` (`primal_update_6dof`, `dual_update_6dof`) |
| The `q`-block (`r×r` solve each iteration), numpy reference | `solver_6dof.py::_solve_q_block` |
| The `q`-block, **GPU-resident float64 warp kernels** (M1.3) | `solver_6dof.py::_solve_q_block_device` / `_modal_qblock_kernels.py` |
| World API (retypes support-height FLOOR rows → SUPPORT, samples `U_y`) | `world.py::enable_reduced_modal_support` |
| Scene wiring (`solver="native"`) | `scenes/reduced_scene_common.py`, `reduced_dinner_table.py` |
| Viewer (`--solver native`) | `scripts/run_native_scenes_viser.py` |
| numpy ground-truth oracle | `dcr/avbd/modal_qblock.py` |

The contact constraint is `g_j(z,q) = corner_y(z) − (y_rest_j + U_y,j·q) ≥ 0`,
read against the **live** `q` (no pre-baked anchor, no write-back). The one
multiplier `f_j` enters the body gradient (`+J_x f`) and the modal gradient
(`−U_y f`) with opposite signs — Newton's third law.

## What works (validated)

`tests/avbd_native/`: `test_modal_qblock.py`, `test_native_modal_support.py`,
`test_native_scene.py`, `test_native_stacks.py` (12 tests). Plus the full suite
green except the one **pre-existing** failure
`test_fem_rigid_coupling.py::test_free_modal_ringdown_is_energy_monotone`
(cargo coupler, `~2e-13` over a `1e-12` tol — fails identically on a clean tree).

- **Faithfulness** — body rests on the live `y_rest + U_y·q` surface; grep shows
  no anchor write-back / pose overwrite / coupler hook on the native path.
- **Two-way loop** — drop the impactor → support rings (modal KE > 0) and lifts
  bystanders; the frozen-`q̇` predictor counterfactual gives ~zero ring.
- **Passivity** — modal-only free ringdown is monotone non-increasing; a loaded
  truck scene's ring peaks then decays ~99% (`Ė ≤ 0`, no governor).
- **Stacks** — truck 4-high lumber holds (<0.5° tilt over 500 steps, robust to
  impactor mass); ledge rings; nothing tunnels.

## The `q`-block: block coordinate descent + relaxation (`# DEVIATION`)

`_solve_q_block` solves `H_q Δq = −g_q` with `z` held at the colored primal's
current value, under-relaxed by `solver._modal_relax` (default **0.1**), each
iteration. Two documented deviations from a literal simultaneous Newton step:

1. **Block Gauss–Seidel** (z-blocks via the colored primal, then the q-block)
   instead of one simultaneous Newton solve — the interleave the prompt's
   ARCHITECTURE section authorizes. Keeps box-box **native** in the colored
   primal; the q-block only updates `q`.
2. **Engaged-only gather** — only compressive (`f<0`) support contacts load the
   mode; a separated corner exerts no force and must not stiffen it.

`_modal_relax` is a **numerical** solver setting (like the iteration count /
SOR), *not* a physical knob — `q` still has only `M_q/K_q/D_q`. Un-relaxed, the
q-block takes a full Newton step each iteration while the primal advances `z` by
one step, so `q` over-deflects on a stiff impact transient and topples stacks
(truck lumber → 36°). `ω ≤ 0.15` is the stable regime; `0.1` holds the stack and
still rings two-way + passive. The cost: `q` under-converges within the substep,
so the ring is **gentler** than a fully-converged solve.

## The cross-term Schur — implemented and REJECTED (key finding)

The principled, no-relaxation fix is the foundation's explicit cross-term
`S = H_q − Σ Mᵀ H_x⁻¹ M` with `M = −ρ J_x U_yᵀ`. It was implemented (each
grounded body's full `H_x` incl. box-box, Schur, `Δq`) and **does not work** as a
drop-in. Three successive attempts, each failing.

### What `Δz` and `Δq` are (reading the table)

The monolithic coupled step is one Newton solve of the 2×2 block system for
**both** unknowns at once:

```
[ H_x   M  ] [Δz]   [ −g_x ]      M  = −ρ J_x U_yᵀ   (the cross block)
[ Mᵀ   H_q ] [Δq] = [ −g_q ]      Δz = body pose update (6/body)
                                  Δq = slab modal-amplitude update (r)
```

`Δz` and `Δq` come out as a **consistent pair**. Schur elimination solves
`(H_q − Mᵀ H_x⁻¹ M) Δq = −g_q + Mᵀ H_x⁻¹ g_x` for `Δq`, then back-substitutes
`Δz = H_x⁻¹(−g_x − M·Δq)`. That **full `Δz` has two parts**:

- `−H_x⁻¹ g_x` — the body's **own** solve (its rigid inertia + its contacts),
  independent of the mode. **This is exactly what the colored primal already
  computes** for the body.
- `−H_x⁻¹ M·Δq` — the **cross** part: the body moving *because* the surface `q`
  moved.

So the three variants differ only in how much of `Δz` the q-block applies on top
of the primal:

- **`Δq` only** — apply `Δq` to `q`, apply *no* `Δz`. Inconsistent: `Δq` was
  computed assuming the bodies *also* move by `Δz`; they don't → energy injected.
- **`Δq` + full `Δz`** — apply `Δq` and the *complete* `Δz` (both parts). But the
  primal *also* does the `−H_x⁻¹ g_x` part, so it runs **twice** → the body
  over-moves and fights the primal → 180° flip.
- **`Δq` + cross-only `Δz`** — apply `Δq` and only `−H_x⁻¹ M·Δq`, leaving
  `−H_x⁻¹ g_x` to the primal. No double-step — but still topples (the softening
  tension below).

**Why the shipped block-GS has no `Δz` at all:** its q-block computes **only
`Δq`** and writes it to `q`; the bodies' *entire* pose update comes from the
colored primal, which already sees the new surface through the live
`y_rest + U_y·q` it reads in-kernel. "`Δq` is in the q-block, `Δz` is in the
primal" — that clean split is what keeps box-box native and the step passive.

| Variant | Result on truck lumber |
|---|---|
| `Δq` only (no `Δz` back-sub) | injects energy → collapse (−0.05 m, peakKE 6 J) |
| `Δq` + **full** `Δz` back-sub | double-steps body vs primal → **180° flip** |
| `Δq` + **cross-only** `Δz` (`−H_x⁻¹MΔq`) | still topples at every relaxation |

Relax sweep, cross-only `Δz` (300-step truck tilt / peak modal KE):

```
relax=0.1: 180.0°  0.34J     relax=0.5: 180.0°  4.10J
relax=0.2: 162.4°  1.46J     relax=0.7: 180.0°  4.95J
relax=0.3: 180.0°  2.75J     relax=1.0:  37.2°  4.84J
```

**Root cause — a real tension, not just a bug.** The cross-term Schur *softens*
the effective modal stiffness (`S < H_q`) → **larger** `Δq` → a **more vivid**
ring → which shakes the stack **harder**. The retired coupler's "intact stack"
was not better coupling: Route A *dropped* stacked bodies from the modal load, so
the support barely rings under a stack (peakKE ≈ 0). So "vivid ring **and** intact
stack" is genuinely in tension for these support parameters.

A correct fully-converged cross-term needs the grounded bodies **removed from the
colored primal** so the q-block solely owns them (no double-step) — an invasive
coloring/primal change — and likely gentler modal parameters so the truck
specifically holds. That is out of M1 scope.

**Decision:** ship block-GS + `_modal_relax = 0.1` (stable, holds stacks, rings
two-way, passive). The vivid-stiff cross-term ring is deferred.

## Honest boundaries (carried from the foundation)

- Backward Euler removes energy even at `D_q = 0`; the ring decay is physical +
  integrator damping, not separately tunable. Relaxation adds further numerical
  damping. For a controlled modal Q use BDF2 / finer substeps.
- At `h ∼ 1–4 ms` only low modes (<~100 Hz sag & sway) are faithful; a crisp kHz
  ring needs finer `h` or a hybrid exact-exponential resonator for airborne
  intervals.
- The physics is classical flexible-multibody (floating-frame / CMS; the
  affine-body / IPC family with modal reduction). The contribution is realizing
  it as compliant constraints inside a real-time position-based rigid solver
  (AVBD), box-box native, no coupler.

## M1.3 — the GPU-resident device `q`-block (done)

`_solve_q_block` is ported to float64 warp kernels (`modal_qblock_kernels.py`):
`k_modal_rowforce` (per-slot engaged-contact force) → `k_modal_hq` / `k_modal_gq`
(assemble `H_q`, `g_q`) → `k_modal_solve` (single-thread GE, partial pivot,
`q ← q + relax·Δq`, refresh float32 mirror), plus `k_modal_predict` / `k_modal_qdot`
/ `k_modal_diag`. All modal math is `wp.float64` reading the float32 solver state
— the same idiom as `reduced_coupled_kernels.py`. It is the BLOCK-GS q-block (no
cross-term Schur, no `Δz` back-sub): the colored primal owns `z`, the q-block owns
`q`. Issues only `wp.launch` inside `_run_iter_loop`, so the iteration loop is now
**CUDA-graph-capturable with modal enabled** (the per-substep predictor/commit
run outside the captured loop; one small diag readback per substep, not per
iteration).

- **Dispatch** — `solver._modal_device_resident`: `None` ⇒ auto (warp on cuda,
  the numpy `_solve_q_block` reference on cpu). Forcing `True`/`False` runs the
  warp / numpy q-block on either device (how the parity test isolates the port).
- **Parity** (`tests/avbd_native/test_native_qblock_device.py`, 5 tests): on a
  smooth modal-only ringdown the warp float64 q-block matches the numpy reference
  to **fp64 roundoff** (≤1e-11 over 200 steps; measured ~1e-18), and cpu↔cuda
  agree to ~2e-24. With engaged contact, parity is machine-precision for the
  first steps then tracks at float32-ULP scale — the float32 `q_modal` mirror
  feeding the primal flips an engaged/separated branch on a 1-ULP difference
  (the documented "chaotic round-off growth"); the macroscopic ring energy still
  agrees to the percent level.
- **Resident-primal modal wiring** — the native modal support was only ever wired
  into the (G=1) `primal_update_6dof` / `dual_update_6dof`; the cuda resident
  shuffle-fused primal does NOT read `q_modal`, so it ignored the deformed surface
  while the q-block still loaded the mode → energy blow-up on cuda. The native
  modal path now forces `G=1` (the `SUPPORT_CONTACT`-aware primal) on every
  device — still a plain `wp.launch`, fully GPU-resident + graph-capturable. The
  shuffle-fused modal primal is a **deferred profiling optimization** (out of M1.3
  scope: M1.3 is residency + parity, not the fastest primal).

## M2 — native cargo deformation (fem_rigid, done)

A deformable cargo cube is a tumbling 6-DOF rigid box (real SAT collision) whose
elastic modes `a ∈ ℝ^k` join the **augmented native modal vector**
`Q = [q_support; a_cube]` (block-diagonal `M_q/K_q/D_q`) — co-solved with the
bodies in the same backward-Euler step by the augmented q-block. No coupler, no
hook (`Solver6DOF.add_cargo_native` / `world.add_native_cargo`).

- **Per-row gradient** `W = [U_y | −G_a]` generalizes the support's `U_y`, where
  `G_a = n̂ᵀ·R·Φ_c[pid]` is the cube's co-rotated modal contact gradient (the
  per-cube analogue of `U_y`). The q-block reads the gap against the ORIGINAL
  `y_rest + W·Q` (rigid corner + the cube flex via `G_a·a`).
- **Zero primal/dual kernel surgery:** the cube's frozen corner flex
  `(R·Φ_c·a)_y` is baked into the `SUPPORT_CONTACT` anchor at substep begin
  (staggered, `G_a` frozen there), so the primal/dual see only `q[0:r]` — exactly
  the M1 path. The augmented Q lives only in the q-block (host + device).
- **One device path** serves both: the M1.3 kernels are generic in `r`, so cargo
  passes `R_tot = r + Σk` and the per-row `W` (refreshed each substep by the host
  freeze) — fully GPU-resident + CUDA-graph-captured.
- **Validated** (`tests/avbd_native/test_native_cargo.py`, 7): the cube deforms
  AND the slab rings two-way (frozen-q̇ ⇒ ring KE = 0); free-ringdown passivity;
  warp==numpy to fp64 on a smooth trajectory, float32-ULP tracking with contact;
  cuda residency + graph capture + cpu↔cuda agreement; the `build_cargo_scene(
  solver="native")` scene settles with no tunneling. Artifact
  `docs/avbd_native/m2_native_fem_rigid_cargo.png/.gif` (`scripts/plot_native_cargo.py`).
- **vs the coupler** (qualitative, run read-only): native peak cube elastic E is
  the same order as the avbd coupler's (block-GS + relax is gentler than the
  coupler's cross-term Schur — the same M1 trade-off). The couplers are NEVER
  touched (additive native path).

### All three materials + the production scenes

- **fem** (corotate=False, world-fixed modes) — `_cargo_freeze_and_W` already
  branches on `body.corotate` (`G_a = n̂ᵀ·Φ_c` vs `n̂ᵀ·R·Φ_c`), so it was free.
- **abd** (`ABDAffineBody`, `d = vec(F−I) ∈ ℝ^9`) — same co-rotated contact
  coupling (`corner_modal = B_c`), but its stiffness is the NONLINEAR quartic
  V⊥ (`K_q = 0`): the augmented q-block adds `∂V⊥/∂d` to `g` and `∂²V⊥/∂d²` to
  the 9×9 a-block EACH iteration (a damped Newton step). Host:
  `internal_grad_d`/`internal_hess_d` in `_solve_q_block_cargo`. Device:
  `k_cargo_internal` (1 thread/abd cube, disjoint blocks ⇒ race-free `+=`,
  launched between `k_modal_gq`/`k_modal_hq` and `k_modal_solve`). abd is FULLY
  GPU-resident + graph-captured; device V⊥ matches the host numpy V⊥ to fp64.
  The cube shears under impact (‖FᵀF−I‖>0); V⊥ free relaxation is monotone.
- **Production scenes** — truck/ledge/shelf/dinner take `solver="native"` +
  `cargo_material ∈ {fem_rigid, fem, abd}` via `world.add_native_cargo` (replaces
  the impactor's converted `SUPPORT_CONTACT` rows → cube corner pids). All 12
  scene×material combos build/step/no-NaN, the cube deforms, cuda-resident
  (`tests/avbd_native/test_native_production_cargo.py`, 16). The avbd/xpbd
  couplers still drive the same scenes unchanged.

## Status / next

- **M1.3 + M2 (fem_rigid, fem, abd) — ALL DONE.** The native `(z, q[, a])` path
  is GPU-resident on cuda (device float64 augmented q-block, CUDA-graph-captured)
  with CPU↔warp parity to fp64, across all three cargo materials, in the dedicated
  `build_cargo_scene(solver="native")` and the 4 production scenes. No coupler is
  ever touched (additive path; avbd/xpbd still drive the same scenes).
- **Known pre-existing failures (NOT M1.3/M2):** `test_native_stacks.py::
  test_truck_lumber_stack_rides_ring_and_holds` topples to 180° on a clean tree
  (block-GS relax=0.1 no longer holds the truck 4-high lumber — a rigid-stack
  scene-param issue, confirmed independent of the device q-block and cargo path).
  Plus 3 avbd/xpbd **coupler** test failures pre-existing at HEAD (the no-touch
  path) — tracked separately.
- **Remaining polish (not blocking):** wire the deformable cube skinning into the
  unified viser for the native cargo path; a native-cargo viser material dropdown.
- **Known pre-existing failure (NOT M1.3):** `test_native_stacks.py::
  test_truck_lumber_stack_rides_ring_and_holds` topples to 180° on a clean tree
  (block-GS relax=0.1 no longer holds the truck 4-high lumber under the current
  scene params). Confirmed independent of the device q-block (cpu host path fails
  identically). The "vivid ring **and** intact stack" tension is the cross-term
  rejection above; needs a scene-param / coloring revisit, tracked separately.
