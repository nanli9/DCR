# Implementation Sketch — Two-Way Reduced Coupling (ABD cube ↔ FEM-modal slab)

**Branch:** `twobody-abd-fem-coupling`
**Status:** design + self-contained CPU-reference demonstrator (not wired into the
production GPU coupler).
**Companion:** `docs/two_way_modal_coupling_investigation.md` (the why),
`docs/ABD.pdf` (Lan et al. 2022, the reference model for the affine cube).

---

## 0. Goal & scope

Demonstrate, in an obviously-correct CPU/numpy reference, the claim from the
investigation: **two reduced elastic bodies in two-way contact + damping settle
to the static-sag equilibrium.** Concretely — a cube dropped on a supported slab,
where:

- the **slab** is a **FEM modal** reduced body (real eigenmodes of a clamped
  plate — bending sag is the point);
- the **cube** is modelled **two interchangeable ways** so we can *compare* them
  side-by-side in the viewer:
  1. **ABD affine** — 12 DOF affine body (`docs/ABD.pdf`, Eq. 1–8);
  2. **FEM modal** — rigid translation carrier + first *k* elastic eigenmodes.

Both cube models couple to the slab through **the same monolithic
incremental-potential step** (ABD Eq. 9, penalty contact in place of the log
barrier). That single variational step is what makes settling a *descent
theorem* (F1 from the investigation removed), not a babysat impulse.

**Out of scope on purpose** (kept honest per CLAUDE.md): no full IPC log-barrier,
no CCD, no friction, no GPU kernel. Penalty contact + implicit Euler is the
minimal thing that exhibits the passive settling. Every simplification carries a
`# DEVIATION:` comment.

---

## 1. The unified `ReducedBody` interface

Both cube models and the slab implement one interface so the coupled step is
generic. A body owns generalized coords `z ∈ R^n`, velocity `ż`, and exposes:

| method | meaning |
|---|---|
| `M` (n×n) | constant generalized mass (ABD Eq. 4 / modal `I`) |
| `internal_grad(z)`, `internal_hess(z)` | `∇V_b`, `∇²V_b` (ABD `V⊥` Eq. 7–8 / modal `½zᵀK_q z`) |
| `D` (n×n) | Rayleigh damping (modal `D_q`, ABD `α₀M+α₁K_int`) |
| `gravity_force()` | constant generalized gravity load |
| `point_world(z, pid)` | world position of tracked contact point `pid` |
| `point_jac(z, pid)` | `∂point_world/∂z` (3×n), constant in `z` for both models |

Tracked points: the cube's 4 bottom corners; the slab's nearest top-surface
vertex under each corner.

### 1a. ABD affine cube (`ABDAffineBody`)

- DOF `z = q = (p, a₁, a₂, a₃) ∈ R¹²`, world map `x_k = A x̄_k + p = J(x̄_k) q`
  with **constant** `J(x̄) = [I₃ | x̄₀I₃ | x̄₁I₃ | x̄₂I₃]` (ABD Eq. 1). So
  `point_jac` is just `J(x̄_corner)` — orientation-independent (the win from the
  investigation §2c).
- Mass `M = Σ_n m_n J(x̄_n)ᵀ J(x̄_n)` (ABD Eq. 4), lumped nodal masses `m_n` taken
  from the cube FEM `M_full` diagonal — exact, reuses the mesh.
- Internal energy = stiff orthogonality potential
  `V⊥ = κv( Σ_i(aᵢ·aᵢ−1)² + Σ_{i≠j}(aᵢ·aⱼ)² )` (Eq. 7); grad/Hess from Eq. 8:
  ```
  ∂V⊥/∂aᵢ   = 2κv( 2(aᵢ·aᵢ−1)aᵢ + 2 Σ_{j≠i}(aⱼ⊗aⱼ)aᵢ )
  ∂²V⊥/∂aᵢ² = 2κv( 4 aᵢ⊗aᵢ + 2(‖aᵢ‖²−1)I₃ + 2 Σ_{j≠i} aⱼ⊗aⱼ )
  ```
  (the `p` block has zero internal energy; cross `aᵢ–aⱼ` Hessian blocks from the
  `(aᵢ·aⱼ)²` term included).

### 1b. FEM modal cube (`FEMModalBody`, also used for the slab)

- Reuse `dcr/fem/FEMModel` + `dcr/modal/ModalAnalysis` on `data/block.msh`
  (cube) / `data/slab.msh` (slab).
- **Slab**: clamp perimeter-bottom nodes (`fixed_nodes`) → genuine bending modes
  and a real static sag. Coords `q ∈ R^r`, `M_q=I`, `K_q=diag(ωᵢ²)`, `D_q`
  Rayleigh. `point_world` = `rest + U_surf_row @ q`.
- **Cube**: free body → 6 rigid modes are singular under `eigsh(sigma=0)`.
  - # DEVIATION (impl, ABD Eq. 9): we do not co-rotate a floating frame. We split
    the cube into a **rigid translation carrier `p∈R³`** (mass `m·I₃`) plus the
    **first *k* elastic eigenmodes** `a∈R^k` (computed with a small positive
    shift, the 6 ≈0-frequency rigid modes discarded by an `ω` threshold), which
    are M-orthogonal to translation → block-diagonal mass `diag(mI₃, I_k)`. Rigid
    *rotation* is dropped (flat, axis-aligned drop, small tilt). This keeps the
    comparison apples-to-apples: ABD vs FEM differ **only in the deformation
    basis** (affine homogeneous strain vs true elastic mode shapes), both on a
    translation carrier. `point_world = rest_corner + p + Φ_corner @ a`.

---

## 2. The monolithic coupled step (`coupled_step.py`)

Stack `z = [z_cube ; z_slab]`, block-diagonal `M`, `D`, gravity `f`. One implicit
-Euler step = one Newton minimization of the **incremental potential** (ABD
Eq. 9, penalty contact):

```
E(z) = Σ_b 1/(2h²) (z_b − ẑ_b)ᵀ M_b (z_b − ẑ_b)        # inertia
     + Σ_b V_b(z_b)                                      # internal elastic (V⊥ / ½qᵀKq)
     + Σ_i ½ k_c · [gap_i(z)]_−²                         # penalty contact  (DEVIATION: barrier→penalty)
     + grav. linear term
ẑ_b = z_b^n + h ż_b^n + h² M_b⁻¹ f_grav,b
```

with `gap_i(z) = y_corner_i(z_cube) − y_slab_i(z_slab)` (normal = +y).

Newton: `H Δz = −g`,
```
g = M(z−ẑ)/h² + ∇V(z) + (D/h)(z−z^n) + Σ_i k_c[gap_i]_− · ∇gap_i      # implicit Rayleigh damping in (D/h) term
H = M/h² + ∇²V + D/h + Σ_i (gap_i<0) k_c · ∇gap_iᵀ∇gap_i
```
`∇gap_i = [ +point_jac_cube(y-row) ; −point_jac_slab(y-row) ]` is **constant per
active set** → Newton converges in 1–2 iterations. Solve dense (≤ ~30 DOF).
Velocity update `ż^{n+1} = (z^{n+1} − z^n)/h`.

**Passivity:** each step is descent on a bounded-below `E`; with `D ⪰ 0` and the
shared `∇gap` doing equal-and-opposite work on the two bodies, total mechanical
energy is monotone non-increasing → the run converges to `argmin E` = the static
sag (cube resting, slab + cube deformed to hold gravity). This is the
investigation §3 result, now discrete and unconditional.

---

## 3. Energy bookkeeping & acceptance

`coupled_step.energy(state)` returns `{KE, PE_elastic, PE_grav, PE_contact, total}`:
```
KE          = ½ żᵀ M ż
PE_elastic  = V_cube(z) + V_slab(z)
PE_grav     = −Σ_b f_grav,bᵀ z_b   (linear gravity potential)
PE_contact  = Σ_i ½ k_c [gap_i]_−²
```
**Acceptance (test `tests/twobody/test_settle.py`):**
1. `‖ż‖ → 0` (both bodies come to rest within tol).
2. `total` energy is monotone non-increasing across the run (passivity), within
   a small per-step Newton tolerance.
3. Final config matches an **independent static solve**: the static minimizer of
   `E` with `ż=0` (Newton on `∇V + ∇V_contact + grav = 0`) — i.e. the analytic
   static sag — to within tol. Same spirit as the `reduced_coupled_avbd` T1 test.
4. Run both cube models; both pass (1)–(3). Their *final sag* differs (ABD
   homogeneous vs FEM modal), which is the comparison payload.

---

## 4. The viser comparison (`scripts/run_two_body_coupling_viser.py`)

Two columns in one viser window, stepped in lockstep:

- **Left: ABD cube** on its slab.  **Right: FEM-modal cube** on an identical slab.
- Live meshes: cube surface (deformed by `z`), slab top surface (deformed by
  `U_surf q`), shown with a display-only deformation exaggeration slider.
- GUI readouts per side: KE, elastic PE, contact PE, total energy, max corner
  penetration, slab center sag. A shared energy-vs-time plot makes the "rings
  then settles to the same static total" story visible.
- Knobs: drop height, cube mass, `κ` (ABD stiffness), `k_c` (contact penalty),
  modal damping, # cube elastic modes, slab material.

What the comparison should *show*: both settle to rest; ABD's cube deforms as a
single homogeneous squish; the FEM cube shows a richer (corner-localized /
bending) deformation field; the slab static sag is essentially identical between
the two (it's the slab's own modes that set it). This makes concrete the
investigation's conclusion: **ABD is the cheaper near-rigid cube model and is
sufficient for settling; FEM modal buys deformation richness the slab-side keeps
anyway.**

---

## 5. Files

```
dcr/twobody/__init__.py
dcr/twobody/reduced_body.py     # ReducedBody, ABDAffineBody, FEMModalBody, builders
dcr/twobody/coupled_step.py     # monolithic implicit step + energy()
scripts/run_two_body_coupling_viser.py
tests/twobody/test_settle.py
docs/two_way_modal_coupling_impl_sketch.md   # this file
```

## 6. Map back to the production path (future, not this branch)

The `H` block above is the dense, two-body, penalty version of the production
`reduced_coupled_avbd` Schur block. Promoting this prototype = (a) swap penalty →
log-barrier + CCD, (b) replace the cube's 12-DOF dense block into the coupler's
per-body `H_x,i`, (c) add the cube-`q` ↔ slab-`q` cross term `ρ J_q,cube J_q,slabᵀ`
to the global Schur matrix. The prototype validates the physics and the energy
behavior before paying that integration cost.
