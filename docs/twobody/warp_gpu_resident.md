# GPU-resident `warp` two-body solver

A fully device-resident `warp` realization of the two-body dynamic-constraint step
(`dcr/twobody/warp_step.py`), faithful to the same incremental-potential Newton
math as the CPU/numpy reference. The numpy path stays the correctness reference
(per `CLAUDE.md`); every device kernel is parity-tested against it.

## What it is

`WarpDynamicSystem(base, mode=…, device="cuda:0")` mirrors the numpy solver API
(`initial_state`/`step`/`energy_breakdown`/`body_z`) for two modes:
- `mode="gt"`   → `MultiBodySystem` penalty Newton (single sweep).
- `mode="avbd"` → `AVBDDynamicSystem` augmented-Lagrangian (n_outer × n_inner + duals).

The step minimizes the SAME potential as the reference:

    minimize_z  Σ_b 1/(2h²)‖z_b − z̃_b‖²_M_b + Σ_b V_b(z_b) + Σ_c Φ_contact(gap_c)

It is an EXACT port (not an approximation) because the problem structure is benign:
- contact gaps are affine in z — `gap_c = base_gap_c + grad_c·z` with **constant**
  `grad_c` (orientation-independent point Jacobians);
- FEM-modal internal force is linear (folds into a constant base `B`); only ABD's
  quartic `V⊥` is re-evaluated per iteration;
- `H = M/h² + D/h + K_fem (+ ABD block) + Σ_active ρ_c grad_c grad_cᵀ` is symmetric
  SPD (M/h² dominant at h≈5·10⁻⁴), solved in-kernel by dense Cholesky (n ≤ 92).

## "Never change the math" guardrail

`tests/twobody/test_warp_parity.py` steps the numpy reference and the warp solver
from an IDENTICAL base (the modal eigensolver's per-build sign is arbitrary, so the
base MUST be shared) and asserts the trajectories agree to fp64 roundoff. Result:
**machine-precision parity** on every scene (truck-bed 92-DOF/32-contact,
stack-impact with bouncing, fem + abd, GT + AVBD) — `max|Δz| ≤ 5·10⁻¹⁴` over
100–200 steps, on warp's `cpu` and `cuda:0`. All 17 cases green. The optimizations
below keep this passing — each changed only the launch schedule, never the result
(`max|Δz| = 3.6·10⁻¹⁵` held constant across all four solver variants).

## Fully GPU resident (audit)

`step()` and `_record_step()` issue **only `wp.launch`** — no `.numpy()`, no
`synchronize`, no host readback. All state (z, v, H, g, δ, the AL multipliers)
lives in `wp.array`s on `cuda:0` for the entire Newton/AVBD loop. Host transfers
happen only at one-time setup (`initial_state`, `_build_h`) and in the diagnostics
(`energy_breakdown`/`body_z`, called per render frame — not per step). The fixed
launch sequence is captured into a **CUDA graph** and replayed once per step.

## Profile → optimize → profile (truck-bed, n=92, AVBD 8×4 = 32 solves/step)

The entire cost was the linear solve; assembly is ~1.3 ms/step. Trajectory
(`cuda:0`, RTX 3060, fp64), parity bit-identical at every stage:

| stage                                             | ms/step | speedup |
|---------------------------------------------------|--------:|--------:|
| serial single-thread Cholesky (dim=1)             |   264.2 |   1.0×  |
| parallel column Cholesky (latency-hidden)         |    68.7 |   3.8×  |
| + CUDA-graph replay (kills launch overhead)       |    43.2 |   6.1×  |
| blocked panel Cholesky + blocked substitution     |    22.5 |  11.7×  |
| + decoupled substitution block (nb_subst=12)      |    20.6 |  12.8×  |
| _numpy CPU reference (LAPACK)_                     |  _11.4_ |    —    |

Diagnosis at each step:
1. **Single-thread Cholesky** on one GPU thread is memory-latency-bound (31 Mflop/s,
   no latency hiding) — 8.4 ms/solve × 32 = the whole 264 ms.
2. **Parallel column Cholesky**: each column's below-diagonal rows across threads
   hides the latency (same left-looking arithmetic). 3.8×.
3. **CUDA graph**: the parallel solve is now 2n tiny launches/solve; graph replay
   removes the per-launch host overhead. 6.1×.
4. **Blocked Cholesky**: with launches free, the cost became the *dependency-chain
   depth* (2n sequential nodes/solve). A panel factor (NB=6) + blocked substitution
   cut the chain ~NB×. 11.7×.
5. **Decoupled substitution block** (the triangular diagonal solve is only O(bp²),
   so a larger panel is cheap): nb_subst=12. The last gain was **8.7% (<10%)** →
   optimization loop stopped here per the diminishing-returns criterion.

## Honest result

For this problem size (≤92 DOF, 32 sequential solves/step) the GPU lands at ~1.8× of
the CPU LAPACK reference. That is the expected outcome and the upfront prediction:
a small, sequential dense solve cannot beat a CPU — GPUs win on large dense/sparse
blocks or many batched systems. The remaining cost is dependency-chain-depth bound;
the next >10% lever is a sparse/Schur reorder exploiting the slab-arrow structure
(factor the independent cube blocks in parallel, Schur-complement onto the slab) —
a larger, higher-risk change deferred to keep the exact-parity guarantee intact.

## Repro

```
# parity (cpu + cuda:0, all scenes, GT + AVBD, fem + abd)
uv run python -m pytest tests/twobody/test_warp_parity.py -q
```
