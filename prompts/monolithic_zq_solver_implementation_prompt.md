# TASK — Monolithic (z, q) solve: promote modal `q` to a native solver DOF

Implement **exactly** what `../DCR-AVBD-Native/two_band_coupling.html` describes
("Modal Contact as a Dynamic Two-Way Constraint", Approach B): **one
backward-Euler / AVBD solve over `(z, q)`** in which the support's modal
amplitude `q` is a **genuine dynamic degree of freedom inside the rigid solver**,
co-solved with the rigid bodies `z` and the box-box self-collision — in the
*same* iteration, in `dcr/avbd/_solver/solver_6dof.py` and its warp kernels.

Branch: `avbd-native-dynamic-constraint`. Read `two_band_coupling.html` in full
before writing code. Read `CLAUDE.md`.

## HARD CONSTRAINTS (non-negotiable)

1. **`q` is a native DOF of the solver.** It lives in `solver_6dof.py` with state
   `(q, q̇) ∈ ℝ^r × ℝ^r`, modal mass `M_q`, stiffness `K_q`, damping `D_q`, and
   the per-support-contact mode-shape row `U_y,j`. It is advanced by the **same
   implicit step** as the bodies. It is NOT a separate object updated around the
   solver.
2. **No coupler, no hook layer.** Delete / retire `dcr/avbd/reduced_coupled_avbd.py`
   and `dcr/avbd/reduced_coupled_xpbd.py` and the `substep_begin_hook /
   iteration_hook / substep_end_hook` plumbing in `solver_6dof.py`. The previous
   `cosolve_stacked_q` "Route A" was a *staggered* block-Gauss-Seidel
   approximation done in a hook — that whole approach is replaced. There is no
   anchor write-back trick, no pose overwrite, no `_stacked_set`. The contact
   constraint reads `q` **directly** (`y_rest + U_y·q`), not a pre-baked anchor.
3. **One variational step over `(z, q)`** per substep — the single incremental
   potential below. The two-way loop must be *structural* (one shared multiplier
   per contact, opposite-sign gradients = Newton's third law), NOT injected. No
   `η`, no energy reservoir/governor, no IIR resonator, no `q_s/q_d` split, no
   velocity band, no high-pass/cooldown. These are explicitly deleted by the
   foundation.
4. **Box-box stays in the same solve.** Body↔body self-collision
   (`BOX_BOX_CONTACT_6DOF`, LBVH broadphase + SAT) is solved by the same solver
   iteration as `z` and `q`. The `(z,q)` coupling is **body↔support only** (the
   foundation has no body↔body modal term); box-box rows are ordinary
   rigid-rigid contacts with no `q` gradient. A stacked pile must both ride the
   ring (its grounded contacts load/feel `q`) AND stay intact (box-box), with no
   coupler arbitration.
5. **CPU numpy reference first, then warp** (CLAUDE.md rule 6). The numpy
   reference is the parity oracle; the warp/device path must match it.
6. **Every modal/contact equation carries a `# DEVIATION` comment** only where it
   diverges from the foundation, citing the section. The math below is verbatim
   from the foundation — implement it, don't re-derive.

## THE EXACT MATH (from the foundation — implement verbatim)

State: `z` = rigid bodies (position + orientation; velocity `v = [v_lin; ω]`),
one 6-block per body. `q ∈ ℝ^r` = modal amplitudes, **mass-normalized**
(`M_q = I`, `K_q = diag(ω²)`), dynamic with state `(q, q̇)`.

**Contact as a constraint on `(z, q)`** — the cube rests on the deformed surface
whose height is set by the full `q`:

    g_j(z, q) = corner_y,j(z) − (y_rest,j + U_y,j · q)  ≥ 0      # non-penetration
    ∂g/∂z = J_x,j = [n̂ ; r × n̂]            # body Jacobian, from collision detection
    ∂g/∂q = −U_y,j ≡ J_q,j                  # mode shape sampled where the body touches
    f_j   = clamp(ρ g_j + λ_j, −∞, 0)        # unilateral, compressive-only

`U_y,j` is the single object coupling body and mode.

**Single incremental potential** (backward Euler / AVBD augmented-Lagrangian),
minimized over `(z, q)` each substep:

    E(z, q) = Σ_i 1/(2h²) ‖z_i − z̃_i‖²_{M_i}      # rigid inertia
            +       1/(2h²) ‖q − q̃‖²_{M_q}         # modal inertia  ◀ the one NEW term
            +       ½ qᵀ K_q q                       # modal stiffness
            +  Σ_j  Φ_AL( g_j(z, q) )                # contact — sees the FULL q

**Inertial predictors** (the modal one carries the ring history `q̇ⁿ` — NOT
zeroed; that is the whole point):

    z̃_i = z_iⁿ + h v_iⁿ + h² M_i⁻¹ f_i^ext
    q̃   = qⁿ  + h q̇ⁿ  + h² M_q⁻¹ f_q^grav        # f_q^grav = Uᵀ f_grav → static sag at equilibrium

**Newton/Schur block** (∇E = 0). The cross-block `−ρ J_x U_yᵀ` is the *only* body↔
mode coupling; `H_q` gains an inertia and a damping term over the static coupler:

    [ H_x,i        −ρ J_x,i U_y,jᵀ ] [Δz_i]   [ −g_x,i ]
    [ −ρ U_y,j J_x,iᵀ      H_q     ] [Δq  ] = [ −g_q   ]

    H_q = 1/h²·M_q + 1/h·D_q + K_q + Σ_j k_j U_y,j U_y,jᵀ
    g_q = 1/h²·M_q (q − q̃) + 1/h·D_q (q − qⁿ) + K_q q − Σ_j U_y,j f_j

Solve: **Schur-eliminate Δz_i per body** (each `H_x,i` is a dense 6×6), solve the
resulting `r×r` system for `Δq`, back-substitute the `Δz_i`. After the step:

    q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h

**Two-way / momentum-conserving:** one multiplier `f_j` per contact enters both
gradients with opposite signs through the same scalar — `g_x += +J_x,j f_j`,
`g_q += −U_y,j f_j` (Newton's third law).

**Passive for free:** backward Euler on this potential is unconditionally
dissipative, `Ė = −q̇ᵀ D_q q̇ − Σ v_iᵀ C_i v_i ≤ 0`. No governor needed.

## ARCHITECTURE: how `q` interleaves with box-box in the AVBD colored solver

`solver_6dof.py` is a VBD/AVBD **block coordinate descent** (per-body local 6×6
solves, graph-colored so independent bodies update in parallel; box-box couples
adjacent bodies handled across colors). The foundation's "Schur-eliminate Δz_i
per body, then solve r×r for Δq" is exactly a block solve where `q` is **one
extra global block** alongside the colored body blocks. Realize it as:

- Each solver iteration:
  1. For each color, the per-body local solve assembles `H_x,i` from rigid
     inertia + **all** rows touching body i (FLOOR, **box-box**, and **support**
     contacts), and the cross term `−ρ J_x,i U_y,jᵀ` for its *support* rows only.
     Box-box rows contribute to `H_x,i` and couple to the neighbor body through
     the existing coloring — they have **no** `q` term.
  2. A `q`-block step assembles `H_q` and `g_q` by gathering `Σ_j` over **all
     active support contacts** (every body's support rows), solves the `r×r`
     system for `Δq`, updates `q`.
  3. The next color's bodies see the updated `q` directly through
     `g_j = corner_y − (y_rest + U_y·q)`.
  This is block coordinate descent on the single potential `E(z,q)` — faithful to
  the foundation (the per-body Schur + global `Δq` solve), with box-box handled
  natively by the colored body blocks. Document the interleave order with a
  `# DEVIATION` only if it departs from a literal simultaneous Newton step.
- The support contact row type must evaluate `g_j` against **live `q`** each
  projection (not a frozen anchor): store `U_y,j` and `y_rest,j` per row; compute
  `surf = y_rest + U_y·q` inside the kernel.
- `q, q̇, M_q (=I), K_q (=diag ω²), D_q, U_y` per support row, and the body→row
  adjacency, are solver-resident arrays (warp on device; numpy on CPU reference).

## WHERE THINGS LIVE / WHAT TO TOUCH

- `dcr/avbd/_solver/solver_6dof.py` — add `q/q̇/M_q/K_q/D_q` state + the predictor,
  the support-row tables (`U_y`, `y_rest`, body↔row map), the `q`-block solve, the
  `q̇` commit; remove the hook fields.
- `dcr/avbd/_solver/kernels_6dof.py` — the support contact constraint must read
  `q` (`eval` of `g_j`, `∂g/∂q = −U_y`); add the `q`-block assembly + solve kernels
  (gather support loads → `H_q`, `g_q` → `r×r` solve → update `q`); the cross term
  in `primal_update_6dof`. Box-box kernels unchanged.
- `dcr/avbd/reduced_support.py` — the modal data source (`U` at contact points,
  `eigen_omegas`→`K_q`, Rayleigh→`D_q`, mass-normalized so `M_q=I`). Feed it into
  the solver directly (no coupler).
- `dcr/avbd/world.py` — replace `attach_reduced_coupled_avbd/_xpbd` with a single
  `enable_reduced_modal_support(rs, tracked_rows, …)` that loads the modal DOF
  into the solver. Remove the coupler wiring.
- `scenes/reduced_scene_common.py` (`build_support_and_attach`) and the scene
  files — point at the new solver API. Keep the SAME scenes (truck, ledge, shelf,
  dinner, cargo) for validation.
- `scripts/run_native_scenes_viser.py` — drop the `cosolve_stacked_q` checkbox;
  the modal support is now intrinsic. The slab always rings two-way.
- DELETE `reduced_coupled_avbd.py`, `reduced_coupled_xpbd.py`, their kernels
  (`reduced_coupled_kernels.py`, `reduced_coupled_xpbd_kernels.py`) and tests that
  assert the hook's internals — or keep them only as a `git`-history reference.

## ACCEPTANCE (demonstrate each: test + plot/MP4/console)

- **Faithfulness:** the support surface a body rests on is `y_rest + U_y·q` with
  live `q` in the *same* solve; grep shows no anchor write-back, no pose overwrite,
  no coupler hook.
- **Two-way energy loop:** drop the impactor; modal KE > 0 (the support rings) and
  it lifts bystanders; the frozen-`q̇` counterfactual (set `q̇≡0` predictor) gives
  zero ring — reproduce the foundation's "energy loop" plot.
- **Passivity:** assert total mechanical energy `E(z,q)` is monotone
  non-increasing each free (no-input) step within integrator tolerance; log
  `Ė ≤ 0`. No reservoir/governor anywhere.
- **Stacks (the whole point of unifying with box-box):** ledge pedestal+pillars —
  pillars **rock** from the boulder; truck 4-high lumber stays intact (min
  adjacent gap ≳ −0.002 m) while riding the ring; shelf / dinner no new deep
  penetration; cargo (fem_rigid/abd) never crashes over 500 steps. Both the
  heavy-impactor and default cases must be stable (the old staggered hook
  over-deflected a global mode on a 60 kg drop — the monolithic solve must not).
- **CPU↔GPU parity:** numpy reference vs warp device agree to tolerance on a
  single-cube and a stacked scene (skipped if no CUDA, but written).
- **Suite green:** `PYTHONPATH=$PWD python -m pytest tests/avbd_native/ -q` —
  everything passes except the known pre-existing
  `test_fem_rigid_coupling.py::test_free_modal_ringdown_is_energy_monotone`
  (E rose ~2e-12 at 1e-12 tol on the clean tree). New tests for the in-solver
  `(z,q)` step replace the retired coupler tests.

## HONEST-BOUNDARY notes to carry (from the foundation, do not overclaim)

- **Numerical damping:** backward Euler removes energy even at `D_q=0`; the ring
  decay is physical + integrator damping, not separately tunable. For a controlled
  modal Q use BDF2 / implicit-midpoint or substep finer — note it, don't fake it.
- **Timescale:** at `h ∼ 1–4 ms`, modes above `~1/(2h)` are over-damped/under-
  resolved; only low modes (<~100 Hz sag & sway) are faithful. A crisp kHz ring
  needs finer `h` or a hybrid exact-exponential resonator for airborne intervals.
- **Novelty framing (foundation "Honest boundary"):** the physics is classical
  flexible-multibody (floating-frame / component-mode-synthesis; the affine-body /
  IPC family with modal reduction). The contribution is realizing it as compliant
  constraints **inside a real-time position-based rigid solver (AVBD/GPU)** — this
  is the *in-solver ground truth*; the cheaper approximate passivity-governed
  coupling is validated against it.

## STARTING POINTERS

- The retired coupler (`reduced_coupled_avbd.py`) already contains correct,
  vectorized assembly of `H_q`, `g_q`, the cross block `−ρ J_x U_yᵀ`, the
  predictor `q̃`, and the `q̇` commit (its `iteration_hook` non-augmented + augmented
  paths). Lift that math into the solver's iteration/kernels — the equations are
  right; what changes is **where** they run (in-solver, every iteration, with box-
  box bodies native) and that `q` is no longer a hook-owned object.
- `_solver/kernels_6dof.py:eval_box_box_C` / `primal_update_6dof` show the colored
  per-body local-solve structure to extend with the support-contact `q` cross term
  and the `q`-block.
- Foundation: `../DCR-AVBD-Native/two_band_coupling.html`. Prior staggered
  realization + its limits: `CONTRIBUTIONS.md` §"Phase D" and memory
  `route-a-stacked-cosolve.md`.

GOAL: when you run viser, the slab is a genuine modal DOF inside the one solver —
contact loads the modes, the ringing modes push the bodies back, stacks ride the
ring and hold together — all from a single passive backward-Euler `(z,q)` step,
with box-box in the same solve and **no coupler anywhere**.
