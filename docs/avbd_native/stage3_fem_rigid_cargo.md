# Stage 3 — `fem_rigid` cube material (CPU reference)

The first cube material of the `fem_rigid → abd → fem` dropdown. A `fem_rigid`
cargo body is a full 6-DOF rigid box (real SAT collision, already in the
AVBD-Native solver) **plus** `k` FEM elastic modes `a ∈ ℝ^k` carried in its
body frame (floating-frame reduced body, `dcr/avbd/cargo/fem_rigid.py`). On
impact it tumbles/settles with zero penetration **and** flexes.

## Coupling — augmented modal vector

All modal DOFs are assembled into ONE augmented vector

    Q = [ q_support(r) ; a_b0(k) ; a_b1(k) ; ... ]

with **block-diagonal** `M_q / K_q / D_q` (support block ⊕ per-cube
`I / Ω² / D_modal`). The per-body 6×6 rigid Schur blocks are **unchanged**; the
single generalization is the per-row modal gradient, which grows from the
support's `−U_y` to also carry the co-rotated cube term

    G_a = n̂ᵀ · R · Φ_c              (FEMRigidModalBody.point_jac_tan, modal cols = R·Φ_c)

in that body's `a`-columns. The cube's corner flex `(R·Φ_c·â)_y` folds into the
contact anchor — exactly mirroring the support's staggered `q̂` seed — so the
gap/force computation `C = corner_rigid_y − (floor + U_y·q̂ − G_a·â)` is
byte-identical to the pure-rigid path. The live `a` still updates through the
augmented Schur block each iteration; `ȧ = (aⁿ⁺¹ − aⁿ)/h` after the substep is
the per-cube ring-carrying mechanism (`two_band_coupling.html`, "After the step").

Everything is the dynamic two-way constraint, per cube: one shared multiplier
carries both directions, backward Euler is dissipative ⇒ passive by construction.

### Deviations (flagged in code)
- **Global vs per-body elimination** (plan §3 says "per-body block"): the cube
  modes are eliminated as a GLOBAL augmented block, not folded into the per-body
  6×6. The two orderings are exact block-Gaussian re-orderings of the SAME
  monolithic Newton system ⇒ identical converged Δ; the global form reuses the
  existing Schur machinery untouched.
- **Modal gravity dropped** (`â = aⁿ + h·ȧⁿ`, no `h²` term): the elastic modes
  are M-orthogonal to the rigid translation modes, so `Φᵀ(uniform gravity) ≈ 0`
  — identical reasoning to the support's `f_q^grav = 0`.
- **Corner-snapped modal sampling:** a contact row's modal block is the nearest
  cube corner's `Φ_c`. SAT box contacts are corner/edge contacts and the modal
  field is smooth, so this is faithful for the box geometry.

## Reference-first (CLAUDE.md rule 6)

This stage lands the **CPU reference** path. The cargo path is a separate branch
(`_iteration_hook_augmented` / `_setup_cargo_substep`) that activates only when
cargo bodies are registered — the cargo-EMPTY path (every support-only scene)
runs the existing CPU/GPU code **verbatim**, so the Stage-1 CPU↔GPU parity stays
bit-exact (`tests/avbd_native/test_dynamic_coupling.py` still green). The
augmented-modal **device kernels** (GPU residency + CPU↔GPU parity for cargo)
land next; until then `fem_rigid` scenes route through the CPU reference
(`_use_device` returns False when cargo is present).

## Acceptance (CPU)

`tests/avbd_native/test_fem_rigid_coupling.py` (4 tests, all pass):
- **determinism** — two CPU builds step bit-identically.
- **cube flexes on impact** — modal `a` and modal KE become clearly nonzero
  (well above the ~1e-15 round-off floor); cube settles at `support_top + half`.
- **free modal ring-down is energy-monotone** — a plucked cube held clear of the
  support rings down with monotone non-increasing modal energy (backward Euler).
- **two-way counterfactual** — `freeze_qdot` ⇒ modal KE ≡ 0; the full dynamic
  constraint rings (>0) and carries strictly more modal energy.

Plus `tests/avbd_native/test_fem_rigid_cargo.py` (4 tests): FD-verified
co-rotated contact Jacobian `R·Φ_c`, mass-normalized modes, dissipative free
step.

### Artifacts (`scripts/plot_fem_rigid_cargo.py`)
- `docs/avbd_native/stage3_fem_rigid_cargo.png` — dynamic vs frozen: COM height,
  cube modal energy (the flex), support modal energy (the two-way ring), and
  contact penetration.
- `docs/avbd_native/stage3_fem_rigid_cargo.gif` — skinned cube (modal flex ×300)
  tumbling onto the deformed support; zero visible interpenetration.

Measured (soft cube `E=1e6`, drop 4 cm, spin 6 rad/s, 220 steps):

| quantity | dynamic | frozen q̇≡0 |
|---|---:|---:|
| peak cube modal energy (J) | 1.65e-2 | 1.06e-2 |
| peak support modal energy (J) | 3.80e-3 | — |
| **max contact penetration (mm)** | **0.0025** | **0.0014** |

The cube flexes (dynamic rings above the frozen static-only deflection), the
support rings beneath it (two-way), and penetration is at the **micron** level
— real SAT collision, no interpenetration.

> **MP4 → GIF:** the environment has no ffmpeg / imageio-ffmpeg backend and
> CLAUDE.md forbids unjustified new dependencies, so the animated artifact is a
> GIF (imageio's native Pillow writer). The live viser (Stage 7) is the
> interactive visual.
