# Stage 5 — `fem` cube material (translation+modal, no co-rotation)

The third cube material, and a **restriction of fem_rigid** (reference
`dcr/twobody/reduced_body.py:FEMModalBody`): the same FEM elastic eigenmodes,
but the modal contact gradient is the **world-fixed** `n̂ᵀ·Φ_c` instead of the
co-rotated `n̂ᵀ·R·Φ_c`. The rigid frame still translates under the solver, but
the modal subspace does not ride a tumbling frame — the rotation-dropped
translation+modal body the twobody comparison uses.

## Implementation — one flag

`FEMRigidModalBody.corotate` (default `True`). `build_fem_cube` returns a
fem_rigid body with `corotate=False`. The coupler honors it in exactly one
place per path:

- CPU (`_setup_cargo_substep`): `G_a = R[1,:]·Φ_c` if co-rotated, else `Φ_c[1,:]`.
- GPU (`k_eval_cargo`): a per-row `row_cargo_corot` flag selects the co-rotated
  `R·Φ_c` or the world-fixed `Φ_c` y-row.

Everything else — the augmented `Q`, the dynamic block, the Schur reduction, the
corner-flex anchor, the device residency — is shared with fem_rigid. `corotate`
defaults `True`, so fem_rigid and abd are unchanged (byte-identical; their GPU
parity still holds).

## Acceptance

`tests/avbd_native/test_fem_coupling.py` (7 tests, all pass):
- **fem flexes, not co-rotated** (`corotate is False`; modes excited, settles),
- **free ring-down energy-monotone**,
- **CPU↔GPU parity ≤ 1e-11** on `q` and the modal `a`,
- **two-way counterfactual** (`freeze_qdot` ⇒ KE ≡ 0; dynamic rings),
- **3-material smoke** (`fem_rigid` / `abd` / `fem`, 200 steps): finite, no NaN,
  bounded energy, zero penetration, cube settles on the support.

The 3-material smoke is the Stage-5 acceptance matrix on the cargo scene; the
full **4-scene × 3-material** matrix (truck/ledge/shelf/dinner) is wired and
exercised by the Stage-7 unified viser.

### Artifact (`scripts/plot_fem_rigid_cargo.py --kind fem`)
- `docs/avbd_native/stage5_fem_cargo.{png,gif}` — dynamic vs frozen; skinned
  cube (modal flex ×300). Dynamic peak modal energy 1.87e-2 J > frozen 1.03e-2 J;
  support rings to 4.1e-3 J; **max penetration ~0.008 mm**.

All three cube materials (fem_rigid → abd → fem) now tumble/translate with real
SAT collision (micron-level penetration), deform under impact (modal or affine),
and ring the support two-way — CPU reference + GPU-resident, parity-gated.
