# Stage 4 — `abd` cube material (co-rotated affine)

The second cube material. An `abd` cargo body is a 6-DOF rigid frame `(p, R)`
(carried by the AVBD-Native solver — real SAT collision, tumbling) **plus** a
9-DOF body-frame affine deformation `F` governed by the stiff quartic
orthogonality potential `V⊥` (Lan et al. 2022, ABD Eq. 6–8). World map:

    x = p + R · (F · x̄)          d = vec(F − I) ∈ ℝ⁹   (d = 0 ⇒ F = I)

## Reuses the Stage-3 augmented-modal coupling verbatim

The affine corner Jacobian `B_c` (3×9, `u_body = (F−I)·x̄_c`) plays the **exact
role** of the modal `Φ_c` (3×k): the coupling gradient is `n̂ᵀ·R·B_c` and the
deformation `d` rides the **same augmented modal vector** `Q = [q_support;
d_cube]`. A uniform cargo interface (`Mq_block / Kq_block / Dq_block`,
`corner_modal = B_c`, `internal_grad_d / internal_hess_d`,
`has_nonlinear_internal`) lets one coupler serve both materials. The only
abd-specific pieces:

| | fem_rigid | abd |
|---|---|---|
| deform dim k | 6 (modes) | 9 (affine F−I) |
| `Mq_block` | I (mass-normalized) | block-diag(Q,Q,Q), Q = Σ mₙ x̄ₙx̄ₙᵀ |
| elastic | linear `K_q = diag(ω²)` | **nonlinear** `V⊥` (Kq_block = 0) |
| `Dq_block` | modal Rayleigh | α₀·M_F |

The nonlinear `V⊥` grad/Hess is added to the cargo block each iteration
(re-linearized at the live `d`): CPU in `_iteration_hook_augmented`, GPU in the
new `k_cargo_internal` kernel (one thread per affine body, disjoint 9-blocks ⇒
no atomics). Everything else — the augmented `Mq/Kq/Dq` upload, `k_eval_cargo`
co-rotated gradient, the Schur reduction, `k_anchor` corner-flex — is shared.

### Deviations (flagged in `dcr/avbd/cargo/abd.py`)
- **Co-rotated affine vs reference global affine** (ABD Eq. 1, approved): the
  reference `ABDAffineBody` is a global 12-DOF affine with no rigid frame (flat
  drop). Here the rigid rotation is the solver's tumbling 6-DOF body and `F` is
  the body-frame affine on top — so the cube tumbles (real SAT) AND shears,
  satisfying the Stage-4 acceptance. The two coincide for a non-rotating drop.
- **Collision on the rigid frame**: SAT uses the rigid box; `F` couples into the
  contact only through the corner gradient `n̂ᵀ·R·B_c` (the staggered corner-flex
  anchor, identical in spirit to fem_rigid's modal-corner coupling). `V⊥` keeps
  `F` near a rotation, so the box barely deviates.
- **COM-relative ⇒ p↔F decouples**: with centroid-relative nodes the affine
  mass `M_F` decouples from the rigid translation (the solver owns `p`), and
  `Φᵀ(uniform gravity) = 0`, so the predictor is `d̂ = d + h·ḋ` (no `h²` term).

## Acceptance

`tests/avbd_native/test_abd_coupling.py` (6 tests, all pass):
- **determinism**, **cube shears on impact** (`F` departs from `I`; cube settles),
- **V⊥ keeps F near orthogonal** (`‖FᵀF − I‖` bounded — deforms, doesn't collapse),
- **free ring-down energy-monotone** (`½ḋᵀM_F ḋ + V⊥` non-increasing, backward Euler),
- **CPU↔GPU parity ≤ 1e-11** on `q` and `d` (the nonlinear V⊥ path through `k_cargo_internal`),
- **two-way counterfactual** (`freeze_qdot` ⇒ KE ≡ 0; dynamic rings, more energy).

### GPU residency + speedup (RTX 3060, 1 abd cube, iters=8 × substeps=4)

| path | ms/step | hot-loop sync |
|---|---:|---:|
| CPU coupler on GPU solver | 46.3 | many |
| **GPU-resident** (`k_cargo_internal`) | **5.22** | **0** (`hooks_device_resident=True`) |

An **8.9× speedup**; `R = 18` (support 9 ⊕ affine 9). Residency gate pass.

### Artifacts (`scripts/plot_fem_rigid_cargo.py --kind abd`)
- `docs/avbd_native/stage4_abd_cargo.png` — dynamic vs frozen: COM height,
  affine energy (V⊥), support modal energy (two-way ring), penetration.
- `docs/avbd_native/stage4_abd_cargo.gif` — skinned cube (affine flex ×40)
  tumbling + shearing onto the deformed support; **max penetration ~0.003 mm**.

Measured (κ_v = 2e3, drop 4 cm, spin 6 rad/s): dynamic peak affine energy
3.13e-4 J > frozen 2.65e-4 J (the ring carries more); support rings to 2.68e-3 J;
penetration micron-level. The cube tumbles (real SAT), shears (affine V⊥), and
rings the support two-way.
