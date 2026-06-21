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
| The `q`-block (`r×r` solve each iteration) | `solver_6dof.py::_solve_q_block` |
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
drop-in. Three successive attempts, each failing:

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

## Status / next

- M1.0–M1.5: **done** (block-GS + relaxation). M1.3 (device `q`-block warp kernel
  + CPU↔warp parity) and M2 (cargo deformation native, then delete the coupler):
  **pending**. Cargo / the deformable `cargo` scene still run on the coupler; the
  viewer routes `native + cargo → avbd`.
