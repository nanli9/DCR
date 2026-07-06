# All-scenes generalization: §N2 cargo network everywhere + all-FEM ground truth

Two halves of "wire the generalization for all the scenes, not just cargo, and
get a FEM ground truth for each" (`docs/experiment_plan.md`, G1/G2 feeder):

1. **Every body in every production scene is a modal cargo body on the box-box
   contact network** — the `reduced_cargo_network` (§N2) recipe applied to
   truck / ledge / shelf / dinner, with each body's REAL (hx,hy,hz) modal
   shapes.
2. **An all-FEM ground-truth arm for every scene** — every body full FEM (not
   just the support slab), coupled by the X3-class penalty contact.

## 1. All-cargo scenes (§N2 generalization)

### What changed
- `dcr/avbd/cargo/fem_rigid.py` — `build_fem_rigid_box(half_extents, …)` +
  `box_corner_ids`: the FFR modal body generalized from cubes to anisotropic
  boxes (plates, planks, cutlery). `build_fem_rigid_cube` is an
  exact-equivalence wrapper (bit-identical mesh/modes), so all cube parity
  tests stand. Same for `build_abd_box` in `abd.py`. DEVIATION note added:
  the gyroscopic torque ω×I₀ω is still dropped, now for anisotropic I₀
  (drop/settle scenes, low spin).
- `scenes/reduced_scene_common.py` — `make_cargo_body` (box-shaped cargo,
  mass-matched density) + `register_all_cargo`: every body gets
  `add_native_cargo(..., allow_stacked=True)` (grounded bodies still bind
  their support rows; the flag only waives the no-rows error for stacked
  bodies) and `_modal_contact_network=True`. `build_support_and_attach` and
  all four production builders take `cargo_all=True`.
- `scripts/run_native_scenes_viser.py` — all-cargo is the DEFAULT for
  production scenes (`--no-all-cargo` restores the legacy single-deformable
  mode). Routes to AVBD (the network is AVBD-native; XPBD = N5), renders
  every body as a skinned deformable, enables the network/ride toggles
  scene-wide, and wires the passivity checkbox to the cargo path (ledger
  always on; monitor ↔ active clamp) on every scene, matching the cargo
  scene.

### The solver needed no changes
`Solver6DOF`'s augmented modal path already supports N cargo bodies with
per-body k (dict-keyed cargo state, block-diagonal `M_q/K_q/D_q`), the
box-box net rows are geometry-agnostic (nearest-corner snap reads
`corner_modal`), and the §15 passivity ledger scales the whole augmented
state `[q_support; a_0…a_N]` with one γ.

### Evidence
- `tests/avbd_native/test_box_cargo.py` — box builder invariants (corner
  order, mass, anisotropic inertia, thin-plate-softer-than-cube, k=0 boxes,
  cube-wrapper equivalence). 8 passed.
- `tests/avbd_native/test_all_cargo_scenes.py` — all four production scenes
  build with `cargo_all=True` (every body registered, augmented size
  r + Σkᵢ, network on), step stably, and ring after the pot impact. 5 passed.
- `tests/avbd_native/test_viser_all_cargo_wiring.py` — headless viser wiring
  (viser server stubbed): AVBD routing, all-bodies deform render, passivity
  monitor default, legacy mode, `--inject-xpbd` unaffected. 6 passed.
- Full `tests/avbd_native/` suite: 167+ passed, no regressions (CUDA-gated
  skips only).

### Knobs
`--no-all-cargo` (legacy mode) · `--no-network` (§N2 network off — stacked
bodies inert) · per-body modes `cargo_n_elastic=3` (the cargo-scene value).

## 2. All-FEM ground truth for every scene

### Design (`dcr/fem/multibody_gt.py`)
- `FEMBody` = one linear-FEM `FEMModel` + implicit Newmark (paper Eq. 5,
  trapezoidal) + a constant world origin. Free bodies carry NO Dirichlet
  BCs: `K_eff = K + c0·M + c1·D` stays SPD, and rigid translation is an exact
  zero-energy mode of linear FEM — a free body falls, lands, and deforms with
  no separate rigid state. The support is a corner-fixed slab (the X3
  `fix_corners` pattern, `corner_column_nodes`).
- `MultiFEMSim` couples bodies by the X3-class penalty: the upper body's
  bottom-face vertices vs the lower body's DEFORMED top surface (vectorized
  barycentric height field), vertical normal, frictionless, plus a floor
  halfspace. Pairs are auto-detected per step (XZ AABB overlap, upper = higher
  COM).
- DEVIATIONS (all in the module docstring): penalty height-field contact
  (same fidelity class as `CoupledFEMRigidSim` — score deflection FIELDS, not
  launch KE, per plan §6.1); linear-FEM small-rotation validity (score the
  ledge's pre-topple ring, not the topple); per-vertex penalty stiffness
  pinned to the lightest participating node's ~1.5 kHz oscillator and capped
  at hω ≤ 0.35 (measured: energy pumping at hω ≈ 0.94); a contact dashpot at
  ζ=0.2 of critical (X3's semi-implicit rigid update supplied this
  dissipation implicitly; two trapezoidal FEM sides need it explicitly).

### Harness (`benchmarks/fem_gt/`)
`python -m benchmarks.fem_gt.run_gt --scene {truck,ledge,shelf,dinner,cargo,all} [--quick]`

Geometry is mirrored FROM the live native scene handle (half-extents +
orientations from handle metadata, initial positions from the solver at t=0,
masses from the descriptors), so the GT arm cannot drift from the native
scenes. Two-phase X3 protocol (park the impactor +100 m, settle, release).
Outputs `benchmarks/fem_gt/out/<scene>_gt.{csv,json}`: per-frame support
mid-span u_y, per-body COM/energies, interval-averaged contact ledger.

### Evidence
- `tests/fem_gt/test_multibody_gt.py` — static two-box ledger vs analytic
  (joint = m·g, floor = Σm·g, within 2%); slab sags under a resting box with
  bounded energies; free fall is exact ballistic with ~1e-10 J elastic
  residual. 3 passed.
- `tests/fem_gt/test_scene_gt_smoke.py` — shelf + ledge quick runs: nothing
  falls through, deflection signal present and physical, and the ledge
  ledger resolves the pillar→pedestal→support chain with the pedestal
  carrying more than any pillar. 3 passed.
- Five-scene sweep (quick): correct contact topology everywhere — truck's
  lumber chain `lumber_3→2→1→0→support`, dinner's 17 place settings
  (rotated cutlery included), cargo's zig-zag tower `upper→mid→base`.
- Five-scene sweep at production resolution (h_fine=5e-5, settle 0.4 s +
  run 1.2 s), support mid-span u_y peak / wall time:
  | scene | mid u_y peak | wall (1.6 s sim) | notes |
  |---|---|---|---|
  | truck | −3.6 mm | 88 s | 40 kg crate from 0.7 m on the wood road |
  | ledge | −0.96 mm | 28 s | boulder ring; pillars clash (topple) |
  | shelf | −1.5 mm | 22 s | 6 kg tome on the free end |
  | dinner | ±0.5 mm | 69 s | pot + 16 settled place settings |
  | cargo | ±10 µm | 24 s | matches the native scene's ~1e-5 m flex scale |
  Cost is 13–55 s wall per simulated second — the same order as X3's
  29 s/sim-s single-slab GT.
- Settle-protocol note: the parked impactor FREE-FALLS at x+100 (no support
  there), so release restores the full pre-park COM and rest velocity
  (`common.py`); translating back by −100 alone released it at the wrong
  height (or inside the slab — the pre-fix truck run exploded this way).
- Known contact-model limit, restated: SIDE-face contact is not resolved
  (bottom-verts-vs-top-surface only), so post-topple pile behavior (truck
  lumber after the big impact, clashing ledge pillars) is approximate. The
  scored signal — the support deflection field — is upstream of it.

### Honest gap (next step for G1 acceptance)
This delivers the GT ARM. The X3-style acceptance number ("native/GT
mid-deflection → 1.0 as h→0") additionally needs the NATIVE arm's modal basis
to be the eigenbasis of the SAME FEM operator per scene
(`fem_modal_support.py` / `dinner_scene_gt.py` pattern, `benchmark` branch).
The production scenes currently use the synthetic debug basis, so the strict
convergence claim is not yet comparable; wiring the shared-operator native
arm per scene is the immediate follow-up. Note also the per-body FEM E
defaults to the native cargo default (1e6 Pa) — pass `--body-youngs` to match
any cargo material sweep.
