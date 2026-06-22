# Stage 1 — Dynamic two-way modal constraint in the GPU AVBD coupler

Ports the finalized dynamic modal contact constraint (`two_band_coupling.html`,
"Approach B") into the GPU-resident `ReducedCoupledAVBDCoupler`, replacing the
quasi-static modal block and removing the two-band split machinery. Branch
`avbd-native-dynamic-constraint` (off `AVBD-Native`).

## What changed (math)

The support's modal amplitude `q` is now a **second-order dynamic DOF** `(q, q̇)`
solved jointly with the bodies in one backward-Euler substep (size `h =
h_substep`). The only change to the per-iteration monolithic Schur block is two
diagonal additions to the modal Hessian/gradient (cite `two_band_coupling.html`,
"The Newton / Schur block — only H_q gains two terms"):

```
H_q = 1/h²·M_q + 1/h·D_q + K_q + Σ_j k_j U_y,j U_y,jᵀ
g_q = 1/h²·M_q(q − q̃) + 1/h·D_q(q − qⁿ) + K_q q − Σ_j U_y,j f_j
```

- predictor (carries the ring history `q̇ⁿ` — not zeroed):
  `q̃ = qⁿ + h q̇ⁿ + h² M_q⁻¹ f_q^grav`
- velocity update after the substep: `q̇ⁿ⁺¹ = (qⁿ⁺¹ − qⁿ)/h`
- the contact anchor is seeded from the **full** predictor `q̃` (sag + ring),
  and the bodies feel the ring through the unchanged cross-block `−ρ J_x U_yᵀ`.

Everything downstream (U_y eval, per-body `H_x` blocks, cross-block, Schur
reduce, back-substitution, the tiled Cholesky solve) is **unchanged** — the
dynamic terms are diagonal additions.

### DEVIATIONS (vs the older support-only oracle)

- **Implicit damping.** `g_q` uses the implicit `1/h·D_q(q − qⁿ)` (whose
  derivative is exactly the `1/h·D_q` Hessian term — self-consistent, and the
  basis of the `Ė = −q̇ᵀD_qq̇ ≤ 0` passivity proof). The older
  `reduced_support_solve.py:368` used the explicit `D_q·q̇ⁿ` with a mismatched
  Hessian its own comment calls a "regulariser". The finalized HTML form is the
  consistent, passive one; both share the same Hessian.
- **`f_q^grav = 0`** for the fixed support (its modes are zero-mean about the
  undeformed rest slab — the sag is produced by the contact load at
  equilibrium, not modal self-weight), so `q̃ = qⁿ + h q̇ⁿ`.
- **Per-substep `h`.** Predictor/inertia/damping/velocity all use `h_substep`
  (true per-substep backward Euler), not the `h_macro` mix of the support-only
  oracle.

### Removed (the two-band split machinery)

`q_s/q_d` split, EMA high-pass, the eigen exact-resonator (`k_iir_precompute`,
`k_iir_apply`), the passivity governor / energy snapshot (`k_passivity`,
`k_modal_energy`), the `q = q_s+q_d` sync (`k_sync_total`), the contact-anchor
static low-pass (`k_anchor_lp`), and the resident buffers `q_s/q_d/qdot_d/
F_q_static_lp/q_free/qdot_free/S_h_diag/T_h_diag/F_q_dyn/q_total/qdot_total/
eigen_omega/eigen_zeta/Mq_diag`. The data layer collapses to a single
`(q, qdot, q_prev_macro, q_hat)`; `rs.q_s`/`rs.q_d` are kept only as deprecated
read aliases (`q_s → q`, `q_d → 0`) for the legacy viser HUD.

Two new tiny kernels replace the six removed ones: `k_predict` (snapshot qⁿ +
predictor) and `k_qdot` (velocity update).

## Parity (acceptance a) — GPU device path == CPU numpy reference

Both run on `cuda:0`; the only variable is `coupler.device_resident`. Build is
deterministic (scipy `eigh`), so two builds share the basis exactly.

| horizon | max|Δq| | max|Δx| | note |
|--------:|--------:|--------:|------|
| N=1     | 1.6e-13 | 0       | machine precision |
| N=2     | 2.6e-13 | 0       | **≤1e-12 gate (plan)** ✓ |
| N=8     | 5.1e-6  | 2.8e-4  | round-off growth (graceful) |

`q̇ = Δq/h` inherits a `1/h` (=480×) amplification of q's round-off. After the
dropped crate's impact the truck (a 4-block lumber stack + tumbling cargo) is
chaotic, so the two faithful FP paths decorrelate exponentially — only the
machine-precision early gate and long-run **stability** (finite, bounded, no
blow-up) are asserted post-impact, per the established `test_warp_parity.py`
philosophy. CPU↔CPU is bit-identical.

## Two-way counterfactual (acceptance b) — the M_q/h² term IS the coupling

Per scene, dynamic `q` vs the `freeze_qdot` control (holds `q̇ ≡ 0`, deleting
exactly the M_q/h² inertia term — the `SplitOneWay` control of
`two_band_coupling.html`). Peak over a 240-step dropped-impactor run:

| scene  | modal KE dyn | modal KE frozen | bystander rise dyn | frozen |
|--------|-------------:|----------------:|-------------------:|-------:|
| truck  | 1.36 J       | **0.00 J**      | 70.7 mm            | 19.7 mm |
| ledge  | 1.40 J       | **0.00 J**      | 29.2 mm            | 13.5 mm |
| shelf  | 0.49 J       | **0.00 J**      | 2323 mm            | 327 mm |
| dinner | 2.6e-4 J     | **0.00 J**      | 14.2 mm            | 10.3 mm |

Frozen modal KE is **exactly 0** (the ring is deleted); dynamic rings and lifts
the bystander cargo beyond the frozen quasi-static sag — the two-way loop, in
the form of the constraint. Plots: `docs/avbd_native/stage1_dynamic_vs_frozen_*`.

## Passivity (acceptance) — backward Euler is dissipative

A free (no-contact) backward-Euler step of the dynamic modal block is
unconditionally dissipative: total modal energy `E = ½q̇ᵀM_qq̇ + ½qᵀK_qq` is
monotone non-increasing (test `test_backward_euler_modal_energy_monotone`, 400
steps, real reduced matrices). No η/reservoir governor — passivity is
structural.

## Residency + performance (profile)

All 4 scenes remain GPU-resident (graph captured, `inner.sync = 0`). Removing 6
split kernels and adding 2 tiny ones **improved** the solve and cut the
once-per-step diagnostics readback 11 → 7:

| scene  | baseline solve ms | dynamic solve ms |
|--------|------------------:|-----------------:|
| truck  | 4.54              | 4.00 |
| ledge  | 3.66              | 3.26 |
| shelf  | 3.66              | 3.19 |
| dinner | 4.90              | 4.33 |

(iters=4, substeps=4, h=1/120, RTX 3060, fp64, median over 200 steps.)

## Tests

`tests/avbd_native/test_dynamic_coupling.py` (6 tests) — determinism,
machine-precision CPU/GPU parity, early-horizon agreement, long-run stability,
two-way counterfactual, backward-Euler energy monotonicity. The obsolete split
parity file `tests/avbd/test_reduced_coupled_avbd_device_parity.py` was removed;
`test_q_d_rings_on_impact_under_split` → `test_dynamic_q_rings_on_impact` (modal
KE is now the ring tell-tale).

## Note on the plan's file deletions (`reservoir.py`, `reduced_dcr_postkick.py`)

The plan listed these for deletion as "split machinery". On inspection both are
**standalone legacy modules**, not part of the reduced-coupled coupler:
`reservoir.py` is impact-window energy accounting imported by
`moving_support_solve.py` + 5 tests; `reduced_dcr_postkick.py` is the legacy
one-way DCR post-kick coupler wired into `world.py` and the legacy
`reduced_support_shelf` non-coupled mode. The reduced-coupled path imports
**neither**. The actual in-coupler split machinery (q_s/q_d/EMA/IIR/passivity)
is fully removed. Deleting the two standalone files would break unrelated legacy
modes + tests, so they are kept pending an explicit decision to also retire the
legacy moving-support / postkick paths.
