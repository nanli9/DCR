# Stage 0 — Branch + baseline audit (quasi-static coupler)

Branch `avbd-native-dynamic-constraint`, forked off `AVBD-Native` (tip
`e80343e`). This records the **pre-port baseline** of the GPU-resident
reduced-coupled AVBD solver *before* the dynamic-constraint upgrade, so every
later stage can be measured against it.

## Config

Viewer defaults (`scripts/run_reduced_scene_viser.py` ScenePreset): `iters=4`,
`substeps=4`, `h=1/120`, `device=cuda:0` (RTX 3060 Laptop, Warp 1.13.0, fp64).
Harness: `scripts/bench_reduced_scenes.py` — build → 30-step warm-up (CUDA-graph
capture) → 200 timed steps, median ms/step.

## Baseline table

| scene  | bodies | r (modes) | resident | graph | inner.np | inner.sync | world ms | solve ms |
|--------|-------:|----------:|:--------:|:-----:|---------:|-----------:|---------:|---------:|
| truck  |   12   |    21     |   True   | True  |    11    |     0      |   5.17   |   4.54   |
| ledge  |    5   |    16     |   True   | True  |    11    |     0      |   4.08   |   3.66   |
| shelf  |    6   |    16     |   True   | True  |    11    |     0      |   4.09   |   3.66   |
| dinner |   17   |    24     |   True   | True  |    11    |     0      |   5.73   |   4.90   |

`world ms` = full `world.step()` wall-clock; `solve ms` = pure AVBD+coupler
solver part (`world.last_solve_ms`). All medians over 200 steps.

## Residency audit (pass)

- `coupler.device_resident = True` and `solver._graph` is captured on all 4
  scenes after warm-up.
- The per-iteration Schur inner loop (`_iteration_device`, 16 hook firings/step)
  and per-substep begin issue **only `wp.launch`** — no `.numpy()`, no
  `synchronize`. Probe counts during one `solver.step()`: **`inner.sync = 0`**.
- The `inner.np = 11` host readbacks are the **single once-per-macro-step
  diagnostics sync** (`_sync_device_to_host`, fired on the last substep only) that
  pulls the split-machinery modal state (`q_s`, `q_d`, `q̇_d`, `F_q_*`, `diag`,
  `pass_counter`) for the HUD. This is the quasi-static coupler's split state;
  **Stage 1 removes the split machinery**, so this readback is expected to shrink
  to a single `(q, q̇)` pull.

## Notes for the port

- The quasi-static modal block to replace lives at `reduced_coupled_avbd.py:1104`
  (`H_q = Kq.copy(); g_q = Kq @ self.rs.q_s`) on the CPU reference path and is
  mirrored in `k_hq` / `k_g` (`reduced_coupled_kernels.py`).
- The CPU dynamic oracle already exists at `reduced_support_solve.py:365-368`
  (`g_q = (1/h²)Mq(q−q̂) + Kq q + Dq q̇`, `H_q = (1/h²)Mq + Kq + (1/h)Dq`).
- Split machinery to delete in Stage 1: `reservoir.py`, `reduced_dcr_postkick.py`,
  and the `q_s/q_d` + EMA high-pass + eigen-IIR resonator + passivity-log path
  (`_substep_end_*`, `k_iir_*`, `k_passivity`, `k_sync_total`, `k_modal_energy`).
