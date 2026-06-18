# Stage 2 — Residency verification + profiling loop (dynamic coupler)

After the Stage 1 dynamic-constraint port, re-audited residency and re-profiled
the four scenes. The dynamic terms are **diagonal additions** to the existing
modal block, so the cost structure is unchanged from the already-optimized
AVBD-Native coupler — and is in fact cheaper (6 split kernels removed).

## Residency audit (pass)

- `coupler.device_resident = True` and the iteration loop is CUDA-graph captured
  on all 4 scenes.
- Probe over one `solver.step()`: **`inner.sync = 0`** (no `synchronize` in the
  hot loop). The new `k_predict` (substep begin) and `k_qdot` (substep end) are
  launch-only, eager (they sit at the substep boundaries, outside the captured
  iteration loop) — they add no host readback.
- The only host round-trip is the once-per-macro-step diagnostics sync, now
  pulling a single `(q, q̇)` instead of the split state: readbacks **11 → 7**.

## Profiling table (RTX 3060, fp64, iters=4, substeps=4, h=1/120)

| scene  | CPU ref ms/solve | GPU ms/solve | GPU speedup vs CPU | vs Stage-0 baseline |
|--------|-----------------:|-------------:|-------------------:|--------------------:|
| truck  | 77.6             | 4.00         | 19.4×              | 4.54 → 4.00 (−12%) |
| ledge  | —                | 3.26         | —                  | 3.66 → 3.26 (−11%) |
| shelf  | —                | 3.19         | —                  | 3.66 → 3.19 (−13%) |
| dinner | —                | 4.33         | —                  | 4.90 → 4.33 (−12%) |

The CPU numpy reference forces a device→host→device round-trip every AVBD
iteration (16 round-trips/step: 244 `.numpy()` + 28 syncs measured), so the
GPU-resident path is ~19× faster here — a real GPU win (unlike the tiny twobody
solve in `warp_gpu_resident.md`, where the GPU only matched the CPU LAPACK).

## Profile → optimize → profile: no new >10% lever

The dynamic block reuses the existing kernels' iteration structure (k_hq is still
`dim (r,r)`; k_g still loops over r; k_predict/k_qdot are trivial `dim r`
elementwise). The dominant cost remains the per-iteration r×r Schur solve, which
the AVBD-Native branch already drove to its floor with the block-cooperative
tiled Cholesky inside the captured graph (`warp_gpu_resident.md` — stopped at the
<10% diminishing-returns criterion). The port did not reintroduce a hot spot; it
*removed* six split kernels per substep, so the new floor is strictly below the
baseline. The only remaining sub-10% candidate (folding k_predict/k_qdot into the
captured region across the substep boundary) is ~2% and below the stop
threshold. **Profiling loop stopped per the <10% criterion.**

Parity held at every step (max|Δq| = 1.6e-13 at N=1, machine precision).
