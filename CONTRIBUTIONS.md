# Contributions Beyond the Original DCR Paper — AVBD-Native Branch

This branch (`AVBD`) reformulates the passive-DCR follow-up against the
**AVBD (Augmented Vertex Block Descent)** rigid solver instead of the
original custom PGS solver, and implements the additional energy-
accounting machinery spelled out in
`prompts/avbd_native_dcr_followup_spec_v2.md`.

The paper being reproduced is
**Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid
Body Simulations.* CGF 39(8), SCA 2020**
(PDF at `reference/DCR_SCA2020_preprint.pdf`).

> Full build prompts and the math foundation live in `prompts/`. The
> AVBD reformulation spec is `prompts/avbd_native_dcr_followup_spec_v2.md`.
> The original Stage 1–7 + E0–E5 contributions (PGS solver, modal
> injection, Versions A/B, patch reformulation, benchmark infra) live in
> the `main` branch's `CONTRIBUTIONS.md` and the `prompts/` foundation
> files. **This document is the AVBD-only summary.**

---

## What changed and why

The original follow-up (`main`) used a hand-written PGS Schur-complement
rigid solver. Every change to the modal pipeline carried a `# DEVIATION:
foundation §15` comment because the passive injection replaced the
paper's forced IIR (Eq. 10).

This branch swaps the rigid layer for AVBD and adds a moving-support
contact pass that the patch reformulation only approximated. The
motivation is architectural, not numerical:

1. **AVBD's variational structure** naturally accepts modal coordinates
   as co-optimization variables. PGS is a complementarity solver on a
   fixed constraint set; extending it to co-solve with deformable state
   is awkward. AVBD's primal/dual objective can be extended with a
   modal/elastic term and a contact-with-moving-support term, and the
   inner loop co-optimizes them.
2. **Phase A** (this branch's first half) is the solver swap + viewer
   migration. The patch reformulation's modal-side math is unchanged —
   what changes is who computes the rigid contact impulses (AVBD instead
   of PGS) and how they get exposed to the modal back-reaction.
3. **Phase B** implements the spec's six deferred items:
   §7 (moving-support AVBD constraint), §10 (impulse-work estimator),
   §12 (γ passivity line search), §13.1 (transpose-consistency test),
   §15 (closed-system energy ledger), §22 (per-step invariants 1, 2, 7).

The viewer is also migrated from polyscope to **viser** (browser-based,
live solver thread with reactive GUI controls), matching the stack the
vendored AVBD solver was built for.

---

## Architecture: AVBD ↔ DCR coupling

The repo now has a layered architecture:

```
┌──────────────────────────────────────────────────────────────────────┐
│                  scripts/run_scenes_avbd.py (viser viewer)           │
│  Simulation/DCR/Phase B/Status folders · live solver thread          │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
┌────────────────────────────┴─────────────────────────────────────────┐
│                  dcr/avbd/AVBDDCRWorld  (the adapter)                │
│  step() :                                                            │
│   1. snapshot E_rigid_pre                                            │
│   2. Solver6DOF.step()                       ← AVBD primal/dual loop │
│   3. sync AVBD → DCR-side RigidBody[] (batched)                      │
│   4. extract_contacts() with avbd→dcr index map                      │
│   5. coupler.process_step()                  ← patch coupler         │
│      └─ § passive modal injection (qdot += αs)                       │
│      └─ § patch K_total solve + Coulomb + Newton-3rd back-reaction   │
│   6. apply_patch_kicks() to rigid + sync DCR → AVBD                  │
│   7. _run_moving_support_pass() (Phase B, opt-in)                    │
│      └─ § solve_one_contact() per patch                              │
│      └─ § γ line search per spec §12                                 │
│      └─ § BJ-deformed normal (frozen per solve) per spec §3.1        │
│      └─ § transpose-consistent qdot ← qdot − Φᵀ J                    │
└──────────────────────────────────────────────────────────────────────┘
              │                                       │
   ┌──────────┴──────────┐               ┌────────────┴──────────────┐
   │ dcr/avbd/_solver/   │               │ dcr/dcr/passive_dcr.py    │
   │ vendored AVBD warp  │               │ PassiveDCRCoupler         │
   │ (Solver6DOF, kernels)│              │ (energy_prescribed_patch) │
   └─────────────────────┘               └───────────────────────────┘
```

**Key design rule:** AVBD does not see the modal state during its own
iteration. The moving-support pass (Phase B) runs as a *separate* solve
after AVBD returns, per spec §19 step 9. This avoids touching the
vendored warp kernels — Phase B is Python at the adapter layer.

The two-way bridge is:
- **AVBD → DCR**: positions/orientations/velocities synced into the
  parallel `dcr_body` list after each AVBD step. Quaternion convention
  swap (AVBD = XYZW, DCR = WXYZ). Single batched `.numpy()` per array.
- **DCR → AVBD**: when patch kicks or moving-support kicks modify
  velocities, we push them back with `wp.array.assign(np_arr)` — does
  not reallocate the warp buffer so cached kernel array refs stay valid.
  Skipped when nothing changed (perf gate).

---

## Phase A — solver swap + viser migration

### A.1 Vendored AVBD solver

`/Users/nan/Desktop/fracture/avbd3d/` was copied into
`dcr/avbd/_solver/` (underscore namespace so we can add sibling
modules). No `avbd3d` import from the original repo; DCR is
self-contained. `pyproject.toml` adds `viser>=1.0.29` and bumps
`warp-lang>=1.13.0`.

### A.2 `AVBDDCRWorld` (the adapter)

`dcr/avbd/world.py`. A dataclass that wraps `Solver6DOF` and exposes
the same surface area `DCRWorld` had. Maintains a **parallel DCR-side
RigidBody list** so `PassiveDCRCoupler.process_step()` (which reads
`bodies[i].mass`, `.position`, `.velocity`, `.inertia_world_inv()`,
etc.) keeps working unchanged. Per-stage timing breakdown
(`last_solve_ms`, `last_extract_ms`, `last_coupler_ms`,
`last_moving_support_ms`, `last_sync_ms`) is published for the viewer.

`add_floor(floor_y, ...)` registers a synthetic infinite-mass static
floor on the DCR side (no AVBD body). `add_box(...)` creates both an
AVBD `RigidBody` and the parallel DCR `RigidBody`; wires the AVBD-side
`add_floor_contact_box` if a floor is registered; auto-enables AVBD's
self-collision pool on first box add.

`snapshot()` / `restore()` power the viewer's "reset scene" button —
captures (position, orientation, velocity, modal q/qdot, time), and
restores via batched `assign()` calls so no Warp buffer is reallocated
(kernel array refs survive). Held under a `_world_lock` so a reset
click landing mid-step doesn't corrupt mid-launch kernel arrays.

### A.3 Contact extraction (`dcr/avbd/contact_extract.py`)

AVBD exposes `lambdas()` and walks `_rows`, but not pre-formed contact
records. `extract_contacts(solver, floor_body_idx, prev_contact_keys,
dt, avbd_to_dcr)` walks the constraint pool and produces DCR-shaped
`Contact` records + per-contact `(λ_N, λ_T1, λ_T2)` triples in DCR's
friction basis.

Three correctness hurdles surfaced and were fixed:

1. **AVBD λ sign for floor contacts.** `FLOOR_CONTACT_6DOF` rows have
   `fmax = 0` ⇒ λ ≤ 0. The *physical upward* magnitude is `−λ`.
   Empirically verified via h-sweep.
2. **AVBD λ is force-like in BDF1, not impulse.** Discovered via
   `Σ|λ| ≈ m·g` (constant in h, not scaling with h ⇒ force, not
   impulse). Fix: multiply by `dt` in the extractor. Verified ratio
   0.999 for a settled box.
3. **AVBD→DCR body index remap.** AVBD assigns body indices in the
   order `solver.add_box(...)` is called; DCR-side indices are
   positions in `_descs`, which includes a static floor entry AVBD
   doesn't see. Without the remap a scene with the floor at DCR index
   0 and the only box at AVBD index 0 emits `Contact(body_a=0,
   body_b=0)` and `cluster_contacts_by_body_pair` silently produces
   empty patch lists. The world now passes an explicit
   `avbd_to_dcr: dict[int, int]` map. Lookups against AVBD arrays
   (positions, orientations) still use AVBD indices; only the emitted
   `Contact` records are remapped.

### A.4 viser viewer (`scripts/run_scenes_avbd.py`)

Three scene builders (`build_truck_scene`, `build_shelf_scene`,
`build_ledge_scene`) return `(AVBDDCRWorld, PassiveDCRCoupler,
SceneBoxes, mesh, title)`. The `AVBDDCRViewer` class:

- one `server.scene.add_box` handle per body (XYZW → WXYZ swap on
  every render tick),
- one elastic-surface mesh handle, vertex positions updated from
  `U_surf · q + rest_surf` each tick (visualises modal deformation),
- GUI folders: **Simulation** (pause / speed / AVBD iterations /
  AVBD substeps), **DCR** (β, η, modal_decay_γ, causal_gating),
  **Phase B** (enable_moving_support_pass, β, use_bj — see §B.5
  below), **Actions** (reset scene), **Status** + **Phase B Status**.
- Wall-clock-driven `_run_loop`: catches up to real time with `pause`
  / `speed` knobs; cap of 4 steps/frame so the solver can't run away
  from the renderer on a slow machine.

---

## Phase B — spec §7/§10/§12/§13.1/§15/§22

### B.1 `dcr/avbd/reservoir.py` — §10/§11/§12 primitives

Three exports, all energy-bookkeeping primitives that the Phase B
machinery composes:

| Function | Spec | What it computes |
|---|---|---|
| `k_body(r, m, I⁻¹)` | §10 | `K_body = (1/m) I + [r]×ᵀ I⁻¹ [r]×` — symmetrized, PSD |
| `estimate_impulse_work(J, v, ω, r, m, I⁻¹)` | §10.1 | `ΔE_rigid(J) = Jᵀ v_p + ½ Jᵀ K_body J` |
| `support_work([J_k], v, ω, [r_k], m, I⁻¹)` | §10.1 | sequential accumulation with intermediate v/ω updates |
| `support_budget(β, E_modal_reservoir)` | §11 | `E_budget = β · E_modal_reservoir` |
| `gamma_rescale(W, E_budget)` | §12 | `γ ← γ · √(B/(W+ε))` factor |
| `passivity_scale_gamma(run_solve, E_budget, ...)` | §12 | full line search with γ=0 fallback |

The `estimate_impulse_work` identity matches the direct before/after
ΔKE to **1e-9 across 100 random impulses** (Test 6,
`tests/avbd/test_k_body.py`).

### B.2 `dcr/avbd/diagnostics.py` — §15/§21 energy ledger

`EnergyLogEntry` captures the spec §21 subset that's load-bearing for
invariants 1, 2, 7. `EnergyLedger` records `(E_rigid_pre, E_modal_pre,
E_rigid_post, E_modal_post)` per step via `record_pre()` /
`record_post(**kwargs)` calls bracketing `world.step()`. Exposes:

- `check_non_increase(tol, relative_tol)` — raises on the first step
  where `E_total_post > E_total(0) + slack`, with full context.
- `total_energy_series()` and `rigid_modal_series()` — numpy arrays
  for plotting.
- Running E_modal_peak tracked across `record_pre/post` (used by
  spec §14.3 modal-cutoff gate).

### B.3 `dcr/avbd/moving_support_solve.py` — §6–§13

The spec §19 step 9 primitive. One call per patch per step:

```python
res = solve_one_contact(
    body, r, Phi, n_frame, qdot, q, omega2_diag,
    beta=0.1, mu=body.friction, gap=0.0,
    max_attempts=3, causal_gating=True,
    contact_shell_delta=1e-4, v_min_closing=0.044,
    e_modal_cutoff_frac=1e-5, E_modal_peak=...,
    restitution=0.0,
)
```

Pipeline:

1. **Snapshot** v, ω, I⁻¹, build `K_body` and `K_total = K_body + ΦΦᵀ`.
2. **Inv 3 short-circuit** — if `E_modal_now ≤ 1e-18`, return (J=0,
   no state change). Method must reduce to ordinary AVBD contact when
   the reservoir is empty.
3. **§14 causal gating** — check `gap ≤ contact_shell_delta`, closing
   `v_rel_n < −v_min_closing`, modal `E_modal_now > εₑ · E_modal_peak`.
   Failing returns `gated_out=True` with zero impulse.
4. **γ line search** (`passivity_scale_gamma`). Inner `run_solve(γ)`:
   - `v_s = γ · Φ q̇`,  `v_rel = v_p − v_s`
   - `J = −(1+e) · K_total⁻¹ · v_rel`
   - `J ← cone_project(J, n_frame, μ)`   (frozen-frame Coulomb)
   - `W = max(0, estimate_impulse_work(J, v, ω, r, m, I⁻¹))`
   - return W to outer line-search; outer rescales γ if `W > β·E_modal`.
5. **Apply** the accepted impulse and transpose-consistent
   back-reaction using the **same Φ instance** (spec §13 / Inv 5):
   ```
   v        += J / m
   ω        += I⁻¹ (r × J)
   q̇        -= Φᵀ J
   ```

Returns a `MovingSupportResult` carrying `(J, qdot_after, v_after,
omega_after, W_support_to_rigid, E_support_budget, gamma_final,
attempts, gated_out)`.

### B.4 Wiring into `AVBDDCRWorld.step()`

New flag `enable_moving_support_pass: bool = False`. When `True`, after
the patch coupler returns, `_run_moving_support_pass(bodies)` is
called. Iterates each `coupler.last_patches`, picks the receiver body
(the non-elastic side of each patch), builds Φ(x̄) via
`eval_basis_at_point` (KD-tree cached), picks `n_frame` per the BJ
toggle (§B.5), calls `solve_one_contact`, and writes the returned
state directly into `body.velocity` / `coupler._stepper.qdot`.

Diagnostics aggregated per step for the viewer:
`last_W_support`, `last_E_support_budget`, `last_gamma_support_min`,
`last_n_moving_support`, `last_n_moving_support_gated`,
`last_bj_angle_deg_max`, `last_bj_fallbacks`, `last_moving_support_ms`.

The pass is bit-identical-disabled when `enable_moving_support_pass`
is `False` (no allocations, no diagnostic writes, no warp roundtrips).

### B.5 Barbič-James deformed normals (§3, §3.1)

When `moving_support_use_bj=True` AND the coupler was built with
`deformed_normal_method="barbic_james"` (it caches a `BarbicJamesCache`
of `tri_to_tet` + per-tet ∇N gradients), the moving-support pass
computes a **frozen-per-step** BJ normal at the patch centroid:

```
F     = I + Σ_k u_k(q) ⊗ ∇N_k        (assembled from the owning tet)
n_BJ  = normalize(F⁻ᵀ · n_rest)
n_BJ  ← clamp_normal_angle(n_BJ, n_rest, θ_max)
```

Validation falls back to `n_rest` if `F` is singular, the result has
NaN/Inf, or unit-length is lost beyond 1e-6 — `last_bj_fallbacks`
increments and the diagnostic surfaces in the viewer.

Spec §3.1 freeze rule: BJ normal is computed once at the top of the
moving-support solve and held fixed across the γ line search — we
don't let `n_BJ(q)` rotate inside the inner loop, which would make the
contact frame a nonlinear moving target and complicate energy
accounting.

Performance: the BJ closest-triangle scan was originally O(n_tri)
brute-force per call (~200 ms per step on the truck scene). Fixed by
sharing the same `cKDTree` centroid cache used by
`eval_basis_at_point` and `compute_deformed_normal` — final cost is
~5 ms per step on the same scene (~40× speedup, identical numerics).

### B.6 Per-step invariants asserted (spec §22)

`tests/avbd/test_invariants.py` asserts at every step:

- **Inv 1 — modal injection bound:** `ΔE_modal_injected ≤ η · E_loss + ε`.
  Measured from the coupler's `last_E_modal_post_kick −
  last_E_modal_pre_kick`. Per-step (not just cumulative).
- **Inv 2 — support work bound:** `W_support→rigid ≤ E_budget + ε`,
  every step the moving-support pass fires.
- **Inv 3 — zero reservoir ⇒ zero support work:** the short-circuit
  above. Documented test in `test_moving_support_solve.py`.
- **Inv 4 — failed gate ⇒ zero support work:** gap/closing/modal
  gates verified independently.
- **Inv 5 — transpose consistency:** elastic-exchange test in
  `test_transpose_consistency.py` shows `ΔE_rigid + ΔE_modal ≡ 0` to
  machine epsilon for e=1; closed-form `−½ v_relᵀ K_total⁻¹ v_rel`
  for e=0.
- **Inv 7 — closed-system non-increase:** `EnergyLedger.check_non_increase`
  across 100-step no-gravity / no-damping runs.

A negative-control test (`test_transpose_violation_leaks_energy`)
documents that a 10% Φ mismatch between forward and reverse maps
introduces a measurable `> 1e-6 J` energy leak — locking in why
Invariant 5 is non-trivial.

---

## Phase C — low-iteration coupling robustness (docs §9–§12)

Phases A/B couple cleanly at the default 40 inner iterations, but the
modal injection **starves at low AVBD iteration counts** — the regime
that makes the solver real-time. At `iters=4` the books on the shelf
scene barely vibrate. `docs/avbd_dcr_coupling_findings.md` §9–§12 records
the full investigation; the summary:

**Root cause (two parts).** (1) *Timing* — the injection only fired on
`is_new` contact frames, which desync from the `E_loss` spike at low
iters (total `E_loss ≈ 46 J` is iteration-insensitive, but the fraction
landing on an injecting frame collapses). (2) *Magnitude* — the kick
`s = Φ(x)ᵀJ` takes its size from the contact impulse `J`, which a soft
low-iteration solve smears thin, and `passive_alpha` can only scale
**down** (α∈[0,1]) — so a large `η·E_loss` budget sits unspent.

**Three fixes tried, two refuted** (kept as OFF-by-default ablations):

| Fix | Flag | Result |
|---|---|---|
| Effective impulse source | `impulse_source ∈ {lambda_only, augmented, delta_p}` | §9: refuted for magnitude — the `passive_alpha` cap binds regardless of source. `delta_p` (measured Δp) is iteration-insensitive, useful as a *direction*. |
| Impact-window reservoir | `use_impact_reservoir` | §10: fixes **timing** (iters=4: 0 → 1.4 J) but not magnitude; CV stays ~0.68. |
| Coherent impulse bank | `use_coherent_impulse_bank` | §11: **refuted** — banking ½‖Σs‖² defers the spend and loses budget to decay faster than the cross-term gain; worse than per-frame. |
| **Energy-prescribed injection** | **`injection_scaling="prescribed"`** | **§12: the fix (below).** |

**The fix — energy-prescribed injection (§12).** Keep `s`'s **direction**
(the spectral mode-mix from the contact geometry — robust across iters)
but set the **magnitude** from the budget: `prescribed_alpha` scales the
kick up OR down so `ΔE_modal = μ·(available budget)` (the foundation §15
inequality used as a **target**, not a ceiling). Layered on the reservoir
(timing) + `delta_p` (iteration-insensitive direction), the injected modal
energy becomes iteration-insensitive (shelf, η=0.5, E_rigid lost → E_modal):

| iters | E_rigid lost | is_new λ passive | reservoir δp passive | **reservoir δp PRESCRIBED** |
|---:|---:|---:|---:|---:|
| 4  | 46.5 | 0.00 | 1.43 | **23.8** |
| 8  | 44.7 | 5.79 | 7.95 | **22.8** |
| 16 | 45.2 | 12.55 | 22.6 | **22.7** |
| 32 | 45.3 | 13.59 | 22.6 | **22.6** |
| **CV** | | 0.689 | 0.678 | **0.022** |

Still globally passive: `fill = 1.000` means it hits the `η·E_loss` bound
exactly and never exceeds it (the realized ΔE is debited from the
reservoir, which is bounded by `η·Σ E_loss`). The `α_max` noise guard
never fires (the upscale is ~4×, finite, because `impulse_threshold`
rejects near-zero directions).

> **# DEVIATION (foundation §14 — the honest caveat).** Prescribed
> injection **synthesizes** modal energy the literal contact impulse did
> not carry — it re-sharpens a soft solve's response. The claim is an
> *energy-bounded modal excitation whose magnitude is prescribed from the
> rigid energy loss and whose direction is the contact-geometry mode mix*,
> NOT the impulse's true modal projection (same footing as the
> spatial-attenuation patch channel). We do **not** claim AVBD gives
> iteration-insensitive modal excitation, nor that the coherent bank
> closes the gap — neither is true.

**Library defaults unchanged.** All four flags default to the conservative
pre-§12 path (`injection_scaling="passive"`, no reservoir, `lambda_only`),
so the 105 avbd+stageE3+stageE4 regression tests are bit-identical. The
**viser viewer turns the recommended combo on by default** (`reservoir +
delta_p + prescribed`, μ=1.0); start the pre-§12 path with
`--legacy-coupling`, or toggle live in the DCR GUI folder.

New tests (all passing): `test_injection_impulse_source.py` (§9),
`test_impact_reservoir_passivity.py` (§10),
`test_coherent_impact_bank_passivity.py` (§11, 10 tests),
`test_prescribed_injection.py` (§12, 9 tests). Diagnostics:
`scripts/_diag_{injection,impact_reservoir,impact_bank,prescribed_injection}_iter_sensitivity.py`.
The new code is `dcr/modal/passive_inject.py::prescribed_alpha`,
`dcr/dcr/impact_bank.py` (the refuted bank), and the injection-scaling +
reservoir + bank wiring in `dcr/dcr/passive_dcr.py`.

---

## Math formulation

All section numbers below refer to `prompts/avbd_native_dcr_followup_spec_v2.md`.

### §1 State variables

```
Rigid body b:   x_b, R_b, v_b, ω_b, m_b, I_b
Modal support:  q, q̇, Ω = diag(ω_i), Φ(x), ∇Φ(x)
                (mass-normalized modes, so M_q = I)
```

Reservoirs:

```
E_rigid  = Σ_b  ½ m_b ‖v_b‖² + ½ ω_bᵀ I_b ω_b
E_modal  =  ½ q̇ᵀ q̇ + ½ qᵀ Ω² q
```

### §2 Modal support geometry

```
u_s(q)        = Φ(x_s^0) · q              (modal displacement at rest support point)
x_s(q)        = x_s^0 + Φ(x_s^0) · q      (deformed support position)
v_s(q, q̇)    = Φ(x_s^0) · q̇              (support velocity)
```

> **# DEVIATION from paper Eq. 12.** This support velocity replaces
> `Δv = d_max / h`. The kick at the contact is now governed by the
> modal state, not a per-step kinematic recipe.

### §3 Barbič-James deformation-aware normal

```
F(x)   = I + ∇u(x)  = I + (∇Φ(x)) · q             (deformation gradient)
n_BJ   = normalize(F⁻ᵀ · n_rest)                  (push-forward normal)
n_BJ   ← clamp_angle(n_BJ, n_rest, θ_max)         (angle-bounded)
```

Frozen per solve (§3.1) to avoid making the contact frame a non-
convex moving target. Fallback to `n_rest` on any of: singular F,
NaN/Inf, ‖n_BJ‖ ≉ 1.

### §4 AVBD objective (vendored)

```
A(z)   = (1/(2h²)) ‖z − ẑ‖²_M
       + Ψ_int(z) + Ψ_contact(z, q) + Ψ_constraint(z)
ẑ      = z^n + h v^n + h² M⁻¹ f_ext              (BDF1 inertial target)
```

Critical distinction the spec hammers: **AVBD objective decrease is
not the physical passivity proof.** We always log AVBD objective,
rigid KE, modal energy, contact work, and reservoir budget separately
(spec §21 / `EnergyLogEntry`).

### §6 Contact gap against modal support

```
g(z, q)        = n_BJᵀ · (p_r(z) − x_s(q)) − δ_shell        (signed gap)
C_N(z, q)      = δ_shell − n_BJᵀ · (p_r(z) − x_s(q))         (violation)
C_N⁺           = max(0, C_N)                                  (positive part)
```

### §7 Augmented-Lagrangian normal contact

```
Ψ_N            = λ_N · C_N⁺ + ½ ρ_N · (C_N⁺)²        (AL energy)
λ_N            ← max(0, λ_N + ρ_N · C_N⁺)            (dual update, non-adhesive)
```

In our adapter-layer Phase B implementation this is not a new warp
kernel — `solve_one_contact` runs a single closed-form `K_total⁻¹`
linear solve per patch and treats the patch as one consolidated AL
constraint. Multiple inner iterations would be needed for full §7
fidelity; the simple form is adequate for the scenes we ship.

### §8 Friction (frozen frame)

```
Δx_t           = (I − nnᵀ) [(p_r^{n+1} − p_r^n) − (x_s^{n+1} − x_s^n)]
λ_T            ← proj(λ_T, Coulomb cone of radius μ λ_N)
```

The contact frame `(n, t1, t2)` is frozen per solve (§8.1) — same
reasoning as the BJ freeze. Implemented via `cone_project_impulse`
from `dcr/dcr/contact_patch.py`, which projects `J − (J·n)n` to the
cone radius and returns a `was_clipped` flag.

### §9 Passive modal injection from AVBD impulses

Per contact k at point `x_k` with rigid impulse `J_k` (from the
ordinary AVBD solve), the spec §9 modal projection is:

```
s_k            = Φ(x_k)ᵀ · J_k                       (modal-velocity kick)
s              = Σ_k s_k                              (per-body aggregate)
```

The α scaling (spec §9, foundation §6) caps `ΔE_modal(α) = α b + ½ α² a`
at `E_max = η · E_rigid_loss`:

```
a              = sᵀ s
b              = q̇_old ᵀ s

if b + ½ a ≤ E_max:   α = 1
else:                  α* = (−b + √(b² + 2 a E_max)) / a
                       α  = clamp(α*, 0, 1)

q̇              ← q̇ + α s
```

Invariant (spec §22 Inv 1, foundation §15):

```
ΔE_modal,injected  ≤  η · E_rigid_loss + ε
```

This part of the pipeline is **unchanged from the original follow-up**
(the patch coupler runs this on AVBD's extracted impulses just as it
did on PGS's). What changes is who computes `J_k`: AVBD instead of PGS.

### §10 Contact work estimation — the load-bearing primitive

```
K_body         = (1/m) I₃ − [r]× I⁻¹ [r]×
               = (1/m) I₃ + [r]×ᵀ I⁻¹ [r]×                ([r]×ᵀ = −[r]×)

ΔE_rigid(J)    = Jᵀ v_p_before + ½ Jᵀ K_body J         (single-impulse identity)
W_support→rigid = max(0, ΔE_rigid(J))                  (spec §10 §22 Inv 2)
```

For multiple impulses on one body, accumulate sequentially with
intermediate `v` / `ω` updates (`support_work`) to avoid double-counting.

The spec warns: the global `max(0, E_rigid^{after} − E_rigid^{before})`
crosscheck is contaminated by gravity, other contacts, and constraint
stabilisation. The impulse-based estimator is the load-bearing one;
the global delta is useful only as a sanity crosscheck in isolated
substeps.

### §11 Work budget

```
E_budget       = β · E_modal_reservoir          (spec §11 first version)
                                                (default β = 0.1, η = 0.5)
```

Main support-work invariant (spec §22 Inv 2):

```
W_support→rigid  ≤  E_budget + ε
```

Stronger closed-system condition for no-gravity / no-external-work
(spec §22 Inv 7):

```
E_rigid^{n+1} + E_modal^{n+1}  ≤  E_rigid^n + E_modal^n + ε
```

### §12 Passivity line search

```
γ = 1
for attempt in range(max_passivity_attempts):       (default 3)
    run AVBD moving-support contact solve using γ
    W = impulse-work estimate
    if W ≤ E_budget + tol: accept
    γ ← γ · √(E_budget / (W + ε))

if still violating:
    γ = 0                                          (rerun with rest support only)
```

γ scales the support velocity: `v_s^γ = γ · v_s`. The γ=0 fallback
always satisfies the bound by construction (no support contribution).

### §13 Transpose-consistent modal back-reaction

```
v_s            = Φ(x_s) · q̇                              (forward map)
q̇              ← q̇ − Φ(x_s)ᵀ · J                         (reverse map)
```

The **same Φ instance** must be used for both — different x_s values,
different basis evaluations, or different frame conventions break the
energy identity:

```
ΔE_total       = Jᵀ v_rel + ½ Jᵀ K_total J            (perfectly elastic ⇒ ≡ 0)
               = −½ v_relᵀ K_total⁻¹ v_rel             (perfectly inelastic ⇒ < 0)
```

### §14 Causal gating

```
§14.1 gap:       g ≤ δ_gate                       (default 1e-4 m)
§14.2 closing:   v_rel,n < −v_min                 (default √(2·g·δ_gate) ≈ 0.044 m/s)
§14.3 modal:     E_modal > ε_E · E_modal_peak     (default 1e-5)
```

Any gate failing ⇒ skip moving-support contact, don't debit the
modal reservoir, don't apply support work.

### §15 Closed-system energy ledger

For no gravity / no damping / no external forces, with
`enable_closed_system_energy_test=True`:

```
E_total(t)     ≤ E_total(0) + ε      ∀ t
```

The §15 test is what catches:

- double-counted reservoirs,
- bad work-estimator signs,
- non-transpose back-reaction,
- BJ frame energy injection,
- γ-loop accounting errors.

Empirically holds in `tests/avbd/test_closed_system_ledger.py` to
within `1e-6 + 5e-2 · E_total(0)` across 100 closed-system steps.

### §22 Required invariants — summary table

| # | Statement | Verified by |
|---|---|---|
| 1 | `ΔE_modal,injected ≤ η · E_rigid_loss + ε` | `test_invariants.py::test_invariant_1_modal_injection_bounded_per_step` |
| 2 | `W_support→rigid ≤ E_budget + ε` | `test_moving_support_solve.py::test_inv2_W_bounded_random_battery` (100 random) |
| 3 | `q=q̇=0 ⇒ W = 0` (reduces to ordinary AVBD) | `test_moving_support_solve.py::test_inv3_zero_reservoir_means_zero_work` |
| 4 | gate fail ⇒ `W = 0` | `test_moving_support_solve.py::test_inv4_failed_*_gate_means_zero_work` |
| 5 | forward Φ ≡ reverse Φᵀ | `test_transpose_consistency.py` (4 tests, elastic + inelastic + negative control + random battery) |
| 6 | `‖n_BJ‖ = 1` or fallback to n_rest | wired in `_run_moving_support_pass`; `last_bj_fallbacks` counter |
| 7 | closed-system non-increase | `test_closed_system_ledger.py`, `test_invariants.py::test_invariant_7_closed_system_non_increase_via_ledger` |

---

## Empirical validation

### Test coverage

```
tests/avbd/                                       # 52 tests, all passing
├── test_adapter_smoke.py            (4)          # AVBDDCRWorld constructs + runs
├── test_contact_extract.py          (3)          # 4-corner normals, lam shape
├── test_impulse_units.py            (3)          # λ-as-impulse h-sweep verification
├── test_patch_integration.py        (3)          # Phase A end-to-end + §15 cumulative
├── test_k_body.py                   (8)          # §10 K_body + impulse-work estimator
├── test_passivity_line_search.py    (7)          # §12 γ rescale algorithm
├── test_transpose_consistency.py    (4)          # §13.1 / Inv 5 isolated test
├── test_closed_system_ledger.py     (4)          # §15 / Inv 7 ledger
├── test_invariants.py               (5)          # §22 Inv 1, 2, 7 per-step
├── test_moving_support_solve.py     (7)          # §7 solve_one_contact primitive
└── test_phase_b_wiring.py           (4)          # end-to-end Phase B in AVBDDCRWorld
```

Stage E3–E6 tests (27 tests) still pass — Phase A/B layered on top
of the existing modal-injection / patch / γ-decay / BJ caches without
regressing.

### Performance (truck scene, CPU warp)

| Configuration | Total | AVBD solve | Coupler | Phase B pass |
|---|---|---|---|---|
| Phase A (Phase B off)            | 124 ms | 108 ms | 9 ms | — |
| Phase B + rest normal            | 124 ms | 103 ms | 10 ms | 4 ms |
| Phase B + Barbič-James normal    | 117 ms | 101 ms | 6 ms | 5 ms |

Phase B itself costs ~5 ms/step on this scene. The AVBD inner solve
dominates at ~100 ms because the scene defaults to
`avbd_iterations=10 × avbd_substeps=4` (40 inner iters per step) for
stacked-lumber stability. The live viewer sliders let you drop this:

| AVBD iters × substeps | Total step time |
|---|---|
| 4 × 1 (= 4 inner)   | **24 ms** |
| 6 × 2 (= 12 inner)  | 35 ms |
| 10 × 4 (= 40 inner) | 139 ms |

The empirical Phase B firing pattern on the truck scene (β=0.1,
BJ on, causal gates off): pass fires from step ~30 onwards (once the
modal reservoir is seeded by the first impacts), with W ≈ 10⁻⁵–10⁻⁴ J
per step. Budget E_budget = β·E_modal ≈ 10⁻³ J → γ stays at 1 (well
inside budget). Drop β to 10⁻³ and γ shrinks below 1 — the line
search engaging.

### Bug fix uncovered during Phase B wiring

`contact_extract` was emitting `Contact(body_a=body_b=0)` for every
floor contact because AVBD-side body indices collided with the
DCR-side floor index. **Effect:** patch coupler's
`_build_patches_for_step` received self-pair clusters and produced
empty patch lists — so the Phase A response pipeline was silently
dormant for every AVBD scene. The original test suite never caught
this because no test introspected `coupler.last_patches`. Fixed by
threading an `avbd_to_dcr: dict[int, int]` map through the extractor;
lookups against AVBD arrays still use AVBD indices, only the emitted
Contact records are remapped.

---

## Commands

### Tests

```bash
uv run pytest tests/avbd/ -v         # 52 Phase A + Phase B tests
uv run pytest tests/avbd/test_k_body.py             # §10
uv run pytest tests/avbd/test_transpose_consistency.py  # §13.1
uv run pytest tests/avbd/test_closed_system_ledger.py   # §15
uv run pytest tests/avbd/test_invariants.py             # §22
uv run pytest tests/avbd/test_moving_support_solve.py   # §7
uv run pytest tests/avbd/test_phase_b_wiring.py         # integration
```

### Viewer

```bash
# Phase A baseline (Phase B off)
uv run python scripts/run_scenes_avbd.py truck

# Phase B with rest normals
uv run python scripts/run_scenes_avbd.py truck --phase-b

# Phase B with Barbič-James deformed normals
uv run python scripts/run_scenes_avbd.py truck --phase-b --use-bj

# Same on the other scenes
uv run python scripts/run_scenes_avbd.py shelf --phase-b --use-bj
uv run python scripts/run_scenes_avbd.py ledge --phase-b --use-bj

# Tune the modal-reservoir spend fraction (default 0.1)
uv run python scripts/run_scenes_avbd.py truck --phase-b --ms-beta 0.25

# Opt into CUDA if available (default: cpu)
uv run python scripts/run_scenes_avbd.py truck --phase-b --device cuda:0
```

In the browser viewer:
- **Simulation** folder: pause / speed × real-time / AVBD iterations /
  AVBD substeps (live).
- **DCR** folder: β / η / modal_decay_γ / causal_gating.
- **Phase B** folder: enable_moving_support_pass / moving_support_beta /
  use_bj_normal (all live-toggleable).
- **Actions** folder: reset scene (replays from t=0).
- **Status** + **Phase B Status** folders: per-step diagnostics.

---

## File layout

```
dcr/avbd/
├── __init__.py                       # AVBDDCRWorld, extract_contacts, ...
├── _solver/                          # vendored AVBD warp kernels (Solver6DOF, etc.)
├── world.py                          # AVBDDCRWorld adapter (Phase A core)
├── contact_extract.py                # AVBD pool → DCR Contact records
├── reservoir.py                      # §10 K_body + §11 budget + §12 γ rescale
├── moving_support_solve.py           # §7 solve_one_contact (Phase B core)
└── diagnostics.py                    # §15 EnergyLedger + §21 EnergyLogEntry

dcr/dcr/
├── passive_dcr.py                    # PassiveDCRCoupler (energy_prescribed_patch)
├── contact_patch.py                  # patch primitives, K_total, Coulomb, passivity
├── deformed_normal.py                # patch-fit deformed normal
└── deformed_normal_bj.py             # Barbič-James F⁻ᵀ normal + cache (KD-tree)

dcr/modal/
├── passive_inject.py                 # eval_basis_at_point, project_impulse, alpha
├── energy.py                         # modal_energy
└── homogeneous_stepper.py            # free damped SDOF integrator + γ-decay

dcr/rigid/
├── body.py                           # RigidBody + box/sphere/plane
├── energy.py                         # rigid_kinetic_energy
└── collision.py                      # Contact (shape consumed by coupler)

scripts/
└── run_scenes_avbd.py                # viser viewer (truck / shelf / ledge)

tests/avbd/                           # 52 tests
prompts/
├── avbd_native_dcr_followup_spec_v2.md  # this branch's spec
└── passive_modal_energy_injection_foundation.md  # core math foundation
```

---

## Scope and limitations (honest)

This branch implements spec §1–§15 + §22 invariants 1, 2, 7. The
following are **intentionally not done**:

- **Spec §20 fully coupled endpoint** — single combined `min_{z, q}
  A(z, q)` solve. Our Phase B runs the moving-support pass as a
  *separate* solve after the ordinary AVBD step (the spec §19 step 9
  formulation), not as an extension of AVBD's primal-dual loop.
- **New warp kernels** — Phase B lives in Python at the adapter layer
  (`dcr/avbd/moving_support_solve.py`). No new kernel rows in
  `dcr/avbd/_solver/`. The vendored AVBD kernels are unmodified.
- **GPU port of the Python pipeline** — DONE for `ReducedCoupledAVBDCoupler`.
  The whole coupler step (`substep_begin` basis eval + eigen IIR
  precompute + anchor seed, the per-AVBD-iteration Schur solve, and
  `substep_end` EMA + IIR `q_d` step + passivity + sync) is GPU-resident
  and the iteration loop is CUDA-graph-captured — see "GPU residency"
  below. Modal state (q_s, q_d, q̇_d, F_q_static_lp) lives on-device; the
  only host readback is once per macro-step for the render/HUD. (The
  other couplers — `ReducedSupportCoupler`, `moving_support_solve` — are
  still CPU numpy.)
- **§16 full performance budget** — we log step time and per-stage
  breakdown but don't aggressively meet the spec's `< 33 ms/step`
  goal on the truck scene at iters=10 substeps=4. At iters=4 substeps=1
  the bound is met (24 ms/step including Phase B).
- **§22 invariants 4 and 6** are tested in the solve primitive but
  not asserted across full simulation runs. Invariant 5 is tested in
  isolation but not in the live viewer; the negative-control test
  documents what a violation would look like.

The honest framing the spec §27 demands holds:

> The moving support can only transfer physical work that is
> explicitly present in its reservoir.

is the invariant we enforce. We do not claim:

- AVBD objective decrease equals physical energy decrease (§4 caveat),
- BJ normals generate energy (§3 caveat),
- internal invariants alone prove physical correctness — the spec
  recommends a FEM/SOFA-style ground-truth comparison scene as the
  external anchor, which we have not run on this branch.

---

## GPU residency: device-resident coupled `iteration_hook`

**Problem.** With `--device cuda:0`, the coupled shelf
(`--mode coupled_iir_modal --reduced-basis eigen`) was *slower than CPU*.
The AVBD solver is fully GPU-resident, but `ReducedCoupledAVBDCoupler` ran
its per-AVBD-iteration Schur solve in numpy as a Python callback fired
*inside* the solver's iteration loop. Two costs followed:

1. Every `iteration_hook` did ~9 `.numpy()` device→host pulls + 3
   `.assign()` pushes, each a full CUDA stream drain — ~16 drains/step at
   4 substeps × 4 iterations.
2. Any hook being set **disabled the solver's CUDA-graph capture**, so all
   ~136 AVBD kernel launches/step paid full Python dispatch overhead.

Measured (`scripts/_diag_coupler_gpu_timing.py`, iter=4 sub=4): bare AVBD
≈ 4 ms/step on both devices (it is graph-captured); with the coupler,
CPU ≈ 30 ms vs **CUDA 45 ms**.

**Fix (this work).**

- `dcr/avbd/reduced_coupled_kernels.py` (new) — the per-iteration Schur
  solve as ~10 warp kernels, each parallel over its natural dimension
  (r×r Hessian/Schur entries, contact rows, tracked bodies); only the
  r×r Gaussian elimination is single-thread. They read/write the solver's
  existing device arrays in place. The 6×6 per-body `H_x` is inverted by a
  2×2 block formula (A is diagonal — the floor normal is ŷ for every row)
  with one hand-rolled 3×3 inverse. Plus the substep-boundary kernels:
  `k_eval_basis` (bilinear grid interpolation of U_y at the moving contact
  corners — device port of `evaluate_basis_at_point`), `k_iir_precompute`
  (per-mode exact resonator — device port of `exact_modal_step_precompute`),
  `k_iir_apply` (EMA high-pass + force q_d), `k_passivity`, `k_sync_total`.
- `dcr/avbd/reduced_coupled_avbd.py` — `device_resident` path: row
  identification is done ONCE (the tracked FLOOR-row set, body map and
  body-frame offsets are static for the shelf); thereafter
  `substep_begin`/`iteration`/`substep_end` are pure `wp.launch`. Modal
  state (q_s, q_d, q̇_d, F_q_static_lp) stays resident on-device; the host
  readback is once per macro-step (last substep) for the render/HUD.
  Default ON when the solver is on CUDA; `device_resident=False` forces the
  numpy reference path.
- `dcr/avbd/_solver/solver_6dof.py` — `hooks_device_resident` flag drops
  the per-hook `wp.synchronize_device` drains and re-enables CUDA-graph
  capture for the iteration loop when the hook is launch-only.

**Result.** CUDA **45 → 9.6 ms/step** (4.7×), now **3.2× faster than the
CPU numpy path** (30 ms). The coupler does ZERO host→device transfers and
zero per-substep / per-iteration round-trips during a step; the iteration
loop is CUDA-graph-captured. The only remaining host reads are once per
macro-step to extract results for rendering/contact-extraction (which bare
AVBD also does) — skippable entirely in a headless run.

**Math.** No equation changed. The numpy path is the reference and stays
the default on CPU (CLAUDE.md rule 6). The kernels carry a
`# DEVIATION:` comment: they compute in float64 internally (the same
float32 solver values the numpy hook reads, upcast identically) and store
float32, so the device result matches the reference to round-off. Pinned
by `tests/avbd/test_reduced_coupled_avbd_device_parity.py`: tight parity
early (q_s to ~1e-12), and over a full impact + ring-down run, bounded
absolute drift (x to nm), identical probe settle (drift-fix preserved),
matching steady-state q_s, and comparable passivity-violation counts. The
long-run q_d/q̇_d divergence is round-off amplified by the sensitive
ring-down — unavoidable for any faithful reimplementation, physically
negligible.

**Residency scope.** Full for this coupler: basis eval, eigen IIR
precompute/apply, EMA, passivity and sync all run on-device. Row
identification (which solver rows are tracked) runs once on the host at
first contact — the tracked-row set / body map / body-frame offsets are
static for the shelf (verified: 1 distinct set over a full run), so the
moving quantity (the basis U_y at the contact corners) is what the device
recomputes each substep. If a future scene made tracked rows churn, that
one-time identification would need a device-side rebuild or a re-detect
guard.
