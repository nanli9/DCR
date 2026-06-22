# Stage 6 — GPU-resident XPBD coupled dynamic modal constraint

The highest-risk stage: a **second device-resident primal** for the dynamic
two-way modal contact constraint (`two_band_coupling.html`). Where the AVBD
coupler (`reduced_coupled_avbd.py`) solves the coupled (rigid 6-DOF ⊕ augmented
modal `Q`) block by per-iteration **Schur–Newton**, the XPBD coupler
(`reduced_coupled_xpbd.py`) solves the **same** incremental potential with the
**XPBD** primal (Macklin et al. 2016): every elastic force and the unilateral
contact are compliant constraints projected Gauss–Seidel inside one substep,
the modal Rayleigh damping `D_q` applied through Macklin's damped update (§3.5).

CPU parity oracle: `dcr/twobody/position_based.py:XPBDDynamicSystem` (its math is
not changed). The coupler re-expresses that oracle in the AVBD-Native solver
idiom so the cube rides the GPU solver's real per-corner FLOOR collision — the
Path-A no-penetration benefit — while the modal coupling is XPBD.

## Design — reuse the AVBD machinery, swap only the primal

`ReducedCoupledXPBDCoupler` subclasses `ReducedCoupledAVBDCoupler` and **inherits
verbatim** the shared backward-Euler machinery: the per-substep caches (moving
basis `U_y`, the co-rotated cargo gradient `G_a`, the augmented-`Q` layout, the
contact anchor), the modal-velocity commit and the energy/passivity diagnostics.
Only the per-iteration primal is overridden.

One `iteration_hook` = one Gauss–Seidel sweep:
1. **per-mode modal elastic** `C_i = Q_i` (support `q` and each cargo `a`),
   compliance `α_i = 1/K_q[i,i]`, damped update with `D_q[i,i]` — independent per
   component ⇒ parallel `dim = R`;
2. **unilateral FLOOR contact** per tracked corner, `C = gap ≥ 0`, compliance
   `α_c = 1/k_contact`, `λ_c ≥ 0`, coupling the cube rigid 6-DOF + cube `a` +
   support `q` through one shared multiplier (the structural two-way loop) —
   serialized (all contacts share `q`) `dim = 1`, same row order on CPU + GPU.

The augmented `row_U_y = [+U_y | −G_a]` convention makes the support and cargo
modal contributions uniform: `∂C/∂Q = −row_U_y` and `w_modal = Σ row_U_y² /
M_q[i,i]` cover both. The coupler owns the tracked bodies' rigid pose (projected
from the solver's inertial predictor) + the modal state + the rigid velocity;
the solver owns the predictor, the per-corner FLOOR-row emission and untracked
bodies.

GPU residency mirrors the AVBD path: the geometry/predictor kernels are reused
(`k_eval_basis`, `k_eval_cargo`, `k_predict`, `k_qdot`, `k_anchor`); the XPBD
sweep is new device kernels (`reduced_coupled_xpbd_kernels.py`) — all pure
`wp.launch` with fixed dims ⇒ the iteration loop is CUDA-graph-captured, zero
host readback in the hot loop (one `.numpy()` per macro-step for the HUD).

## Material support (matches the oracle exactly)

- **`fem`** (translation+modal) and **`fem_rigid`** (co-rotated rigid frame ⊕
  modal): fully supported. The LINEAR modal stiffness is an exact diagonal
  compliant constraint and the modal damping rings it down — stable, two-way,
  passive.
- **`abd`** (nonlinear quartic V⊥): the **AVBD-preferred** material. The oracle's
  own note — *"ABD's mass-proportional damping is not wired through the
  per-constraint damp term here, so the AVBD path is the one exercised for ABD"*.
  The V⊥ is a stiff (~255 Hz at the cube's κ_v) nonlinear constraint; Gauss–
  Seidel cannot dissipate it in the substep sweep budget, so abd-XPBD accumulates
  affine deformation over a sustained contact (it projects fine for a few steps —
  enough for parity). **abd routes to the AVBD coupler**, which solves V⊥
  implicitly (`test_xpbd_abd_uses_avbd` shows AVBD-abd stays near-rigid under
  spin where XPBD would not). Honest per CLAUDE.md rule 8; consistent with the
  oracle. The abd `elastic_constraints` (ported from the oracle) is kept for
  reference / short-horizon parity.

## Acceptance

`tests/avbd_native/test_xpbd_coupling.py` (12 tests, all pass):
- **CPU↔GPU parity** at the parity-gate horizon (n=3): **bit-identical**
  (`|Δq| = |Δa| = |Δx| = 0.0`, well within the ≤1e-11 / ≤1e-6 gate) for `fem`
  and `fem_rigid`. Afterward the round-off grows chaotically (q̇'s 1/h
  amplification + tumbling), exactly as the AVBD path documents.
- **Residency**: `hooks_device_resident=True`, the iteration loop is captured
  into a CUDA graph, **0 host `synchronize_device` calls per step** in the hot
  loop.
- **Two-way counterfactual**: `freeze_qdot` ⇒ cargo modal **KE ≡ 0**; the dynamic
  run rings (KE > 0) — on both CPU and GPU.
- **Passivity**: free modal ring-down total energy monotone non-increasing,
  decays below ½·E₀.
- **Determinism** (bit-equal re-runs) and **smoke** (200 steps, spin=2.0:
  finite, bounded, zero penetration, settled on the support) for fem / fem_rigid.

The existing 28 `tests/avbd_native` AVBD/material tests stay green (40 total).

## Profiling (`cuda:0`, RTX 3060 Laptop)

| material  | CPU-coupler-on-GPU | device-resident XPBD | speedup |
|-----------|-------------------:|---------------------:|--------:|
| fem       |          24.7 ms   |              3.5 ms  |  7.1×   |
| fem_rigid |          24.9 ms   |              3.5 ms  |  7.1×   |

The residency win (eliminating the per-iteration host round-trip) is the lever,
matching the AVBD path's ~9×. The serial contact kernel (`dim=1`, by necessity —
all contacts share the support `q`) is negligible at these scene sizes; no
further >10% lever remains for the single-cube scene.

### Artifact (`scripts/plot_xpbd_cargo.py`)
`docs/avbd_native/stage6_xpbd_cargo.png` — for fem and fem_rigid, overlays AVBD
dynamic vs XPBD dynamic vs XPBD frozen: the XPBD dynamic modal **ring** (cargo +
support modal KE) tracks AVBD's, while the frozen control is flat at 0; the cube
settles and penetration stays sub-mm. XPBD dynamic peak cargo modal-KE 4.5e-3 J
(fem) / 2.5e-3 J (fem_rigid); frozen peak **0.0**; max penetration ~0.4 mm.
