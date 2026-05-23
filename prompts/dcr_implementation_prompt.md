# Reproducing "Distant Collision Response in Rigid Body Simulations" — Implementation Prompt

**Paper.** Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations*. Computer Graphics Forum 39(8), 2020 (SCA 2020). PDF lives at `reference/DCR_SCA2020_preprint.pdf`.

**Your job (Claude).** Reproduce the core method of the paper from scratch, in Python, CPU-only, with NVIDIA `warp` for any inner loops that benefit from kernel-style data parallelism. No C++. Build it in stages. Get each stage stable, tested, and visualized before moving to the next. Do **not** skip ahead.

---

## Ground rules

1. **Language / stack.** Python 3.10+, `numpy`, `scipy` (sparse + `eigsh`), `warp-lang` (CPU device only for now), and a lightweight viewer (`polyscope` preferred — fastest to integrate; `pyvista` acceptable). No PyTorch, no JAX, no Taichi. No CUDA assumptions.
2. **CPU-only.** Always launch warp with `wp.init()` and `device="cpu"`. We will revisit GPU later — not now.
3. **Fast iteration beats clever.** Prefer a slow-but-obviously-correct reference path. Add the fast warp version *after* the reference matches.
4. **No dependency creep.** If you reach for a new library, stop and justify it in the PR description.
5. **Conventions.**
   - Generalized velocity of a rigid body is `v = [v_lin (3); ω (3)]` (linear first, then angular).
   - Quaternions for rotation, stored `(w, x, y, z)`.
   - World-frame contact normals point *out of* body A into body B (consistent with the paper's `λ_N ≥ 0`).
6. **Test every stage.** Each stage has acceptance criteria below. Write the test, run it, show a plot or short MP4, and only then proceed.
7. **Math fidelity.** Every equation cited below is copied from the paper. Use these exact forms in code comments and in docstrings. If you deviate (e.g., regularization tweaks), say so explicitly.
8. **Out of scope for this reproduction:**
   - GPU/CUDA, large-scale benchmarks, follow-up papers, sound synthesis, bounce maps, contact-graph shock propagation, anisotropic friction. Just DCR core.

---

## Stage 0 — Project skeleton and viewer

**Goal.** A runnable project that can load a tet/tri mesh and render a single static scene.

**Tasks.**
- Layout:
  ```
  dcr/
    __init__.py
    geom/           # mesh I/O (OBJ surface, .veg or .msh tet meshes)
    rigid/          # rigid body sim (Stage 1)
    fem/            # FEM assembly (Stage 2)
    modal/          # modal analysis + IIR (Stages 3-4)
    dcr/            # the coupling layer (Stages 5-6)
    viewer/         # polyscope wrapper
    scenes/         # scene definitions (python files)
  tests/
  data/             # mesh assets
  scripts/          # entry points: run_stage1.py, etc.
  ```
- One scene file (`scenes/test_box.py`) that drops a box on a plane and renders it static.
- `scripts/run_viewer.py` that loads any scene and shows it.

**Acceptance.** `python scripts/run_viewer.py scenes/test_box.py` opens polyscope with the box and the ground.

---

## Stage 1 — Rigid body simulator (Eq. 1 → Eq. 2 → Eq. 3)

This is the load-bearing piece. Do not move on until it stacks ten boxes without exploding.

### 1.1 Integration scheme

Symplectic Euler, time step `h` (default `h = 1e-2`).

### 1.2 The big linear system (Eq. 1)

For an `n`-body system with `m` scalar constraints:

```
[  M     -J^T  ] [ v^+ ]     [ M v + h f ]
[                ]            
[  J    (1/h^2) ε I ] [ λ^+ ]  =  [ -(γ/h) φ ]
```

where:
- `M ∈ R^{6n×6n}` is the block-diagonal mass matrix (per body: `diag(m, m, m, I_xx, I_yy, I_zz)` in body frame; transform inertia to world frame each step).
- `J ∈ R^{m×6n}` is the constraint Jacobian (rows are stacked: non-interpenetration first, then friction).
- `v ∈ R^{6n}` are generalized velocities at the start of the step; `v^+` at the end.
- `f ∈ R^{6n}` is applied force (gravity + external).
- `λ^+ ∈ R^m` are constraint impulses.
- `φ ∈ R^m` are constraint violations (signed penetration depth for normals; zero or stick offset for friction).
- `ε` is **CFM** (constraint force mixing) — small diagonal regularization. Default `ε = 1e-6`.
- `γ` is **ERP** (error reduction parameter) ∈ `(0, 1]`. Default `γ = 0.2`.

### 1.3 Schur complement (Eq. 2)

Eliminate `v^+` since `M` is block-diagonal and trivially invertible:

```
( (1/h^2) ε I + J M^{-1} J^T ) λ^+  =  -(γ/h) φ  -  J M^{-1} (M v + h f)
\____________  ____________/             \_____________  _____________/
             \/                                        \/
             A                                         b
```

`A` is SPD because `M^{-1}` is SPD and `(1/h^2) ε I` is SPD. Good — we can use PGS.

### 1.4 LCP / BLCP form (Eq. 3)

With contact, we need feasibility and complementarity:

```
A λ^+ - b = w = w^+ - w^-
0 ≤ w^+ ⊥ (λ^+ - λ_lo) ≥ 0
0 ≤ w^- ⊥ (λ_hi - λ^+) ≥ 0
```

- Normal constraints: `λ_lo = 0`, `λ_hi = +∞`.
- Friction rows (box approximation of Coulomb cone): `λ_lo = -μ λ_N`, `λ_hi = +μ λ_N`. Compute the bounds **after** an initial solve of the normal-only problem (as the paper does), then resolve with friction bounds locked. One outer iteration is fine for Stage 1.

### 1.5 Solver

Projected Gauss-Seidel (PGS) on the BLCP. Reference implementation should be plain numpy. ~30–50 inner iterations. After it works:
- Build a warp version that updates `λ` in parallel-friendly graph-color order (skip the coloring optimization; just write a straightforward warp kernel that loops constraints in serial inside a single-thread kernel — this is fine on CPU and matches the reference exactly).

### 1.6 Newtonian restitution (Eq. 4)

For each *new* normal contact `i` (impacting, not resting), modify the right-hand side:

```
b_i  ←  b_i  -  ε_r  J_{row i}  v
```

where `ε_r ∈ [0, 1]` is the coefficient of restitution. We use small values (paper uses `0.15`). Detect "new" vs "resting" by checking whether the contact existed in the previous step's contact set (with a small spatial tolerance).

⚠️ Naming clash: the paper uses `ε` for *both* CFM and restitution. In code, use `cfm` and `restitution` (or `eps_cfm`, `eps_r`). No exceptions.

### 1.7 Collision detection

Stage 1 only needs sphere-sphere, sphere-plane, and box-plane. Use SAT for box-box later if needed for stacking. Generate at most 4 contacts per box-plane pair (one per corner that penetrates).

### 1.8 Once v⁺ is solved

Plug `λ^+` back into the first row of Eq. 1:
```
v^+ = v + h M^{-1} f + M^{-1} J^T λ^+
```
Then advance positions and orientations with symplectic Euler (quaternion update via `q^+ = normalize(q + 0.5 h Ω(ω^+) q)`).

### 1.9 Acceptance criteria

- Single box falls, hits ground, bounces with restitution `0.5` to ~`0.25` of drop height (energy ratio = `ε_r^2`).
- Ten boxes stacked vertically remain stacked for 5 seconds without drift > 1 mm.
- A box at rest on an inclined plane (slope < `atan(μ)`) does not slide.
- A box at rest on an inclined plane (slope > `atan(μ)`) slides with accel ≈ `g (sin θ - μ cos θ)`.
- Energy plot for a bouncing ball monotonically decreases.

Commit point: tag this `stage1-rigid`.

---

## Stage 2 — Linear FEM model (Eq. 5)

We are going to treat one or more rigid bodies as *if* they were stiff elastic solids, but **only for the purpose of computing distant collision response.** The bodies still translate/rotate as rigid in Stage 1.

### 2.1 Tet mesh

- Load `.msh` (gmsh) or `.veg` (Vega) tetrahedral meshes. Bundle 2–3 small assets in `data/`: a thin table-like slab, a beam, a small block.
- Extract the surface triangle mesh (faces shared by exactly one tet) for later use in Stage 5.

### 2.2 Element matrices

Linear (constant-strain) tetrahedral elements. For each tet:
- Material: Young's modulus `E`, Poisson ratio `ν` (paper uses `E ≈ 1.1 GPa`, `ν = 0.3` for wood-like).
- Build Lamé constants `λ_L = E ν / ((1+ν)(1-2ν))`, `μ_L = E / (2(1+ν))`.
- 3D elasticity matrix `D ∈ R^{6×6}` for isotropic linear elasticity.
- Strain-displacement matrix `B ∈ R^{6×12}` from rest-shape derivatives.
- Element stiffness: `K_e = V_e B^T D B`.
- Element mass (consistent): standard 4-node tet consistent mass `M_e`. Lumped mass is acceptable for Stage 2; the paper does not specify, and lumped is friendlier to the generalized eigenproblem.

### 2.3 Assembly

Assemble global `M ∈ R^{3n×3n}`, `K ∈ R^{3n×3n}` as sparse CSR matrices (`scipy.sparse`).

### 2.4 The model equation (Eq. 5)

```
M ü + D u̇ + K u = f
```

with `u ∈ R^{3n}` the nodal displacements, and Rayleigh damping (used later in Stage 3):

```
D = α_0 M + α_1 K
```

### 2.5 Acceptance criteria (no modal yet — just FEM sanity)

- A cantilever beam (one end fixed) under gravity gives a static tip deflection within 5% of the Euler–Bernoulli analytical solution `wL^4 / (8 EI)` for slender geometry.
- Mass matrix row sums equal total mass to floating-point precision.
- Stiffness matrix is symmetric and positive semi-definite (smallest eigenvalue ≥ 0 numerically; six near-zero rigid-body modes when no BC applied).

Commit: `stage2-fem`.

---

## Stage 3 — Modal analysis (Eqs. 6 → 7 → 8)

### 3.1 Boundary conditions

Apply *fixed* boundary conditions to selected nodes (paper assumes the elastic object is static — e.g., the table is pinned at its feet). Remove those rows/cols from `M` and `K` to get the constrained system.

### 3.2 Generalized eigenproblem

Solve, for the lowest `m` modes (paper uses `m = 20`):

```
K ψ_i  =  ω_i^2  M ψ_i
```

Use `scipy.sparse.linalg.eigsh(K, k=m, M=M, sigma=0, which='LM')` (shift-invert near zero). Sort by ascending `ω_i`.

### 3.3 Modal projection (Eq. 6)

```
u = U q,    U = [ψ_1, ψ_2, ..., ψ_m] ∈ R^{3n × m},    q ∈ R^m
```

### 3.4 Reduced matrices (Eq. 7)

Substitute and premultiply by `U^T`:

```
M_q q̈ + D_q q̇ + K_q q  =  r,        r = U^T f
M_q = U^T M U,    D_q = U^T D U,    K_q = U^T K U
```

With mass-normalized eigenvectors, `M_q = I` and `K_q = diag(ω_i^2)`. With Rayleigh damping, `D_q` is also diagonal. So we get `m` decoupled ODEs.

### 3.5 Decoupled scalar ODEs (Eq. 8)

```
q̈_i  +  ( α_0 + α_1 (k_i / m_i) )  q̇_i  +  (k_i / m_i)  q_i  =  r_i / m_i
```

where `m_i = (M_q)_{ii}`, `k_i = (K_q)_{ii}`.

### 3.6 Storage optimization

After computing `U`, **keep only the rows of `U` corresponding to surface vertices** of the elastic object's mesh — we only need surface displacements for contact response (see paper §4.1, last paragraph). Store as a dense `R^{3 n_surf × m}` matrix. Also store a mapping from triangle surface mesh to these rows.

### 3.7 Acceptance criteria

- For a fixed-bottom slab matching the paper's "table" parameters (`E = 1.1 GPa`, `ν = 0.3`, density `770 kg/m³`), the four lowest eigenfrequencies are within the same order of magnitude as paper Fig. 2 (`ω ≈ 393, 512, 677, 758` rad/s). Exact match is not required (mesh-dependent).
- Visualize each of the first 4 modes as colored displacement on the surface mesh (matches paper Fig. 2 in spirit).
- `M_q ≈ I` to `1e-8` if mass-normalized.

Commit: `stage3-modal`.

---

## Stage 4 — IIR modal stepper (Eq. 10) and sub-step rate

### 4.1 Sub-step size

The modal IIR runs at a much finer rate than the rigid body step `h`. From the paper:

```
T  =  π / (2 ω_max)
```

where `ω_max` is the largest natural frequency in the retained modal set. `T` will typically be `1e-4` to `1e-5` s.

### 4.2 IIR filter (Eq. 10)

For each mode `j`, James & Pai 2002 IIR:

```
q_j^(k)  =  a_{1,j} q_j^(k-1)  -  a_{2,j} q_j^(k-2)  +  a_{r,j} ( r_j^(k-1) / (m_j T) )
```

Filter coefficients (derive from the per-mode SDOF system in Eq. 8 — see James & Pai 2002 for the closed form). Cache `(a_1, a_2, a_r)` per mode once at setup.

### 4.3 Forcing

When the rigid body solver reports a new contact impulse, you'll inject `r^(1) = (accumulated reduced impulse from Stage 5)` and `r^(k) = 0` for `k > 1`. The IIR then steps `h/T` sub-steps per rigid body step.

### 4.4 Acceptance criteria

- A unit impulse on a single mode produces a decaying sinusoid at the correct frequency `ω_j` and damping ratio implied by Rayleigh `(α_0, α_1)`.
- Sum of two modes excited simultaneously is the sum of their individual responses (linearity check).

Commit: `stage4-iir`.

---

## Stage 5 — Modal-path distant collision response (Eqs. 9 → 11 → 12 → 13)

This is the first integration of FEM/modal machinery with the Stage 1 solver.

### 5.1 Map a new contact impulse onto the surface mesh

For each new contact `c` between a rigid body and an elastic object:
- Find the closest surface triangle of the elastic object's stored mesh.
- Compute barycentric coordinates inside it. `H_c ∈ R^{3 × 3 n_surf}` is the sparse selector that picks the three triangle vertices and weights them.
- Reduced impulse (Eq. 9):

```
r_c  =  U^T  H_c^T  n_c  λ_N
```

(`n_c` is the contact normal in world frame. `λ_N` is the normal impulse from Stage 1's PGS solve.)

If multiple new contacts hit the same elastic body this step, **sum** the `r_c`'s into one `r`.

### 5.2 Step the IIR for one rigid frame

Run `h/T` sub-steps of Eq. 10 with the forcing applied at sub-step `k = 1` only.

### 5.3 Max displacement at distant contacts (Eq. 11)

For every *existing* (resting) contact `p` between *some other* rigid body and the same elastic object, identify the surface node(s) `i` near `p`. The maximum normal-direction displacement observed during the `h/T` sub-steps:

```
d_{i,max}  =  max_{k = 1 ... h/T}   | n_i^T  U_i  q^(k) |
```

where `U_i` is the (3-row) block of `U` for surface node `i`, and `n_i` is the contact normal at `p`.

**Simplification (paper §4.5).** If you skip damping carry-over between rigid steps and reset `q^(0) = q^(-1) = 0` each step, you can just take the undamped peak. Use this simplification first; it's robust.

### 5.4 Velocity change (Eq. 12) and mapping back (Eq. 13)

```
Δv_i  =  d_{i,max} / h
Δv_p  =  H_p  Δv
```

where `H_p` is the barycentric weight matrix for the *existing* contact `p`.

### 5.5 Injecting the response into the rigid solver

Two paths (paper §4.5):

**Path A (preferred, cleaner).** Modify `b` in Eq. 2: at the row of the normal constraint of contact `p`, add a desired separation velocity equal to `Δv_p`. This mirrors how Newton restitution is added (Eq. 4).

**Path B (fallback, if your solver doesn't expose `b`).** Apply an explicit impulse using effective mass (Eqs. 17–18):

```
m_eff  =  1 / ( J_p  M^{-1}  J_p^T )
h f_p  =  m_eff  Δv_p  n_p
```

Implement Path A. Path B is a sanity check; they should agree to within a few percent.

### 5.6 Thresholding (paper §4.5)

If `λ_N` of the new contact is below a small threshold (e.g., `1e-3` of body weight), skip the whole DCR pipeline for that contact.

### 5.7 Acceptance criteria

- Reproduce a small "Dinner is served"-style scene: an elastic slab pinned at four corners with a few free rigid plates resting on top. Drop a heavy rigid pot. Plates should *visibly* jump on the rigid frame after impact. Without DCR, plates do not move at all.
- Disable DCR and re-run: scene is silent (plates motionless). Re-enable: plates jump. Two videos in `docs/stage5/`.
- Energy bookkeeping: log the kinetic energy injected into plates per impact; should scale roughly linearly with `λ_N` (small-impulse linear regime).

Commit: `stage5-modal-dcr`.

---

## Stage 6 — Spatial attenuation path (Eqs. 14 → 15 → 16 → 19)

For large objects (terrain, scaffolding) where traveling waves dominate over standing modes.

### 6.1 Precompute self-impulse displacement amplitude per vertex

For each surface vertex `v` of the large elastic mesh, apply a unit normal impulse *at that same vertex* and record the maximum displacement magnitude observed using the modal machinery from Stages 3–4. Store as a vector `q̂ ∈ R^{n_surf}` of self-amplitudes (one scalar per surface node).

This is the per-vertex "how much would this point displace if struck here" lookup.

### 6.2 Local displacement at the impact (Eq. 15)

```
Δx_c  =  q̂^T  h_c  λ_N
```

where `h_c` is the barycentric weight *vector* at the impact location (note: now a vector, not the `H` matrix, because `q̂` is per-vertex scalar).

### 6.3 Attenuation factor (Eq. 14)

```
s  =  exp( -α (r - r_0) )  ·  (r / r_0)^{-β}
```

- `r` is the geodesic distance from impact `c` to distant contact `p` (along the surface).
- `r_0` is a minimum distance (≈ element size). Paper sets `r_0 = 1` and folds the exponential into a constant `C`, giving the simplified form `s = C r^{-β}`. Implement both forms; default to the simplified.
- `α` is material absorption. `β` depends on geometry: `≈ 0` for rods, `0.5` for shells, `1` for volumes.
- Implementation simplification (paper §4.5): `s = C r^{-β}`, with `C ∈ [0.4, 2.0]`, `β ∈ {0.5, 1, 2}`.

### 6.4 Geodesic distance

Implement the **heat method** [Crane, Weischedel, Wardetzky 2013] on the surface triangle mesh:
1. Integrate the heat equation for short time `t`: `(M - t L) u = δ_source` (with cotan Laplacian `L` and lumped mass `M`).
2. Compute the normalized gradient `X = -∇u / |∇u|`.
3. Solve the Poisson equation `L φ = ∇·X`.
4. Subtract the minimum so distances are ≥ 0.

Use `pylibigl`'s `heat_geodesic` if available; otherwise implement it (it's ~50 lines on top of cotan Laplacian). Cache distances per source vertex in a dict (paper §4.5).

### 6.5 Response (Eqs. 16, 19)

```
Δv_p  =  s  ·  Δx_c / h
h f_p  =  s  m_eff  (Δx_c / h)  n_p     (Eq. 19, Path B)
```

### 6.6 Acceptance criteria

- A "scaffold" or "ground slab" scene where a heavy rigid body impacts one end and resting rigid bodies at the other end receive an impulse that decays with distance.
- Sweep `β ∈ {0.5, 1, 2}` and `C ∈ {0.4, 1, 2}`. Produce a 2×3 montage matching the paper's Fig. 9 in spirit (single frame per parameter pair).
- Plot attenuation vs distance: sanity-check the slope on a log-log plot matches `-β`.

Commit: `stage6-spatial-dcr`.

---

## Stage 7 — End-to-end scenes and ground-truth comparison

### 7.1 Reproduce two scenes from the paper

- **Dinner is served** (modal path): table slab + rigid plates/cups + dropped pot.
- **Low-rider truck on ground** or **Scaffold** (spatial attenuation path).

### 7.2 Qualitative ground-truth check

Set up a small version of the Dinner scene where the table is also simulated as a deformable FEM body with implicit Newmark/backward-Euler at `h_fine = 1e-5` (yes, this is slow — that's the point). Compare the *trajectories of the rigid plates* between:
- Full FEM coupled sim (ground truth).
- Stage 5 DCR-augmented rigid sim.

We're not after pixel-accurate match — just same qualitative behavior (plates lift at roughly the right times by roughly the right amounts).

### 7.3 Acceptance criteria

- Two short MP4s in `docs/stage7/`, one per scene.
- One side-by-side comparison MP4 (DCR vs ground truth) with a velocity-magnitude plot overlay.

Commit: `stage7-scenes`.

---

## Quick reference: every paper equation in one place

| Eq. | Meaning | Where used |
|-----|---------|-----------|
| 1 | Constrained dynamics linear system | Stage 1 |
| 2 | Schur complement form, defines `A` and `b` | Stage 1 |
| 3 | BLCP feasibility/complementarity | Stage 1 |
| 4 | Newton restitution as RHS modification | Stage 1 |
| 5 | FEM dynamics `M ü + D u̇ + K u = f` | Stage 2 |
| 6 | Modal projection `u = U q` | Stage 3 |
| 7 | Reduced FEM `M_q q̈ + D_q q̇ + K_q q = r` | Stage 3 |
| 8 | Decoupled scalar ODE per mode | Stage 3 |
| 9 | Contact → reduced impulse `r_c = U^T H_c^T n_c λ_N` | Stage 5 |
| 10 | IIR filter step | Stage 4 |
| 11 | Max distant displacement | Stage 5 |
| 12 | Velocity change `Δv_i = d_{i,max} / h` | Stage 5 |
| 13 | Map back via barycentrics `Δv_p = H_p Δv` | Stage 5 |
| 14 | Spatial attenuation `s = exp(-α(r-r_0)) (r/r_0)^{-β}` | Stage 6 |
| 15 | Local displacement `Δx_c = q̂^T h_c λ_N` | Stage 6 |
| 16 | Distant Δv via attenuation | Stage 6 |
| 17 | Effective mass `m_eff = 1 / (J_p M^{-1} J_p^T)` | Stages 5, 6 (Path B) |
| 18 | Impulse `h f_p = m_eff Δv_p n_p` | Stages 5, 6 (Path B) |
| 19 | Spatial-attenuation impulse `h f_p = s m_eff (Δx_c/h) n_p` | Stage 6 |

Sub-step rate: `T = π / (2 ω_max)`.

---

## Default parameter values (from paper Tables 1–2)

| Parameter | Default | Source |
|-----------|---------|--------|
| Rigid time step `h` | `1e-2` s | Table 1 |
| Number of modes `m` | 20 | §4.1 |
| Coefficient of restitution | 0.15 | §5.4 |
| Friction `μ` | 0.5 (paper doesn't specify) | reasonable default |
| CFM `ε_cfm` | `1e-6` | reasonable default |
| ERP `γ` | 0.2 | reasonable default |
| Rayleigh `(α_0, α_1)` | `(10, 1e-7)` | §5.3 |
| Table: `E, ν, ρ` | `1.1 GPa, 0.3, 770 kg/m³` | Table 2 |
| Cliff/ground: `E, ν, ρ` | `10 GPa, 0.3, 500 kg/m³` | Table 2 |
| Spatial atten. `C` | 0.4–2.0 | §5.3 |
| Spatial atten. `β` | 0.5, 1.0, 2.0 | §5.3 |
| Optimized fit (scaffold) | `α=0.048, β=0.8, r_0=0.033` | Fig. 10 |

---

## Working-rhythm reminders

- One stage at a time. **Never** start stage `N+1` before stage `N` passes its acceptance criteria.
- After each stage, write a short `docs/stageN.md` (one screen of text) describing what was done, what was hard, and what was punted. Future-you will thank present-you.
- If a stage seems too easy, you almost certainly missed an edge case. Re-read the paper's section for that stage.
- If a stage seems impossible, the paper probably waved its hands somewhere. Find the hand-wave and pick a defensible simplification. Document it.
