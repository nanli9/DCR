# MIG 2026 short paper — DEVICE timing ledger

**This file exists so that `docs/mig2026_results_ledger.md` can keep its
"ARM M4, CPU only" header honest.** Every number here is measured on a GPU
host and on x86, and none of it is a solver-behaviour number: it is wall-clock
only. Solver-behaviour numbers never go in this file.

---

## R7b — device-timing re-verification (2026-07-19)

Plan §6.9 R7b. Requested by the user 2026-07-18; non-blocking for submission.
Purpose: the paper's device timings were measured 2026-07-08 at commit
`f94c850`; this re-runs them at the current submission commit on a freshly
provisioned pod.

### Machine and environment

| field | value |
|---|---|
| host | `cpod-1t0b3cmcyn8f` (compshare pod, **re-provisioned**) |
| GPU | NVIDIA GeForce RTX 4090, 24 GiB, sm_89 |
| driver | 595.80 |
| CUDA toolkit (warp) | 12.9 |
| CPU host arch | x86_64 |
| warp | 1.15.0 |
| numpy / scipy | 2.2.6 / 1.15.3 |
| python | 3.10.12 |
| code commit | `7c621dc` (`impulse-native-constraint`) + uncommitted R1
  harness (measurement-only; no solver source touched) |

**NOT the same machine as the 2026-07-08 reference.** That run was on the
previous compshare pod (hostname `cpod-1skopckdit1u`, CUDA 12.8). The pod was
re-provisioned between the two runs, so a machine/driver difference is
confounded with the commit difference and **the deltas below must not be
attributed to code changes.**

### Generating command

```sh
# repo synced to the pod by tar+scp (NOT a git push: the GitHub repo is public
# and the submission is double-blind, so the branch was never published)
~/dcr-venv/bin/python benchmarks/paper_eval/x5_perf/run_perf_device.py \
    --frames 200 --device cuda:0 --scenes shelf,ledge,dinner,truck
```

Protocol (unchanged from the reference): `wp.synchronize_device` brackets every
step; 10 warm-up steps; 200 timed frames; CUDA-graph capture active
(`captured=True`, `clamp_captured=True` in all four scenes).

### Result — `perf_device.csv`, 16×4, `coupling_ms` (the paper's column)

| scene | 2026-07-08 ref [ms] | 2026-07-19 [ms] | delta | rt factor @120 Hz | worst step [ms] | std |
|---|---:|---:|---:|---:|---:|---:|
| shelf  | 5.6374 | **5.0182** | −11.0% | 1.6606 | 5.3082 | 0.051 |
| ledge  | 6.8235 | **6.5041** | −4.7%  | 1.2812 | 7.0555 | 0.494 |
| truck (road) | 8.8712 | **8.2344** | −7.2% | 1.0120 | 9.3125 | 0.594 |
| dinner (table) | 9.2002 | **8.8857** | −3.4% | 0.9378 | 9.9303 | 0.197 |

Band moves **5.6–9.2 → 5.0–8.9 ms**. Every scene got faster by 3–11%; see the
machine caveat above before reading that as a code improvement.

### Budget ladder — `perf_device_budget.csv`

| cell | 2026-07-08 ref [ms] | 2026-07-19 [ms] | rt factor |
|---|---:|---:|---:|
| ledge 16×2  | 3.28 | **3.1282** | 2.664 |
| dinner 16×2 | 4.65 | **4.4110** | 1.889 |

Full ladder (this run): dinner 8×1 1.247 / 8×2 2.378 / 16×2 4.411 / 16×4 8.830
/ 32×4 17.318; ledge 8×1 0.855 / 8×2 1.606 / 16×2 3.128 / 16×4 6.112 /
32×4 12.241.

### CLAIM IMPACT — the real-time sentence must change

The frozen sentence is: *"the shelf and ledge scenes meet a 120 Hz budget
there, the road (8.87 ms) and table (9.20 ms) scenes do not, and all scenes
meet it at 16×2 or below."*

`rt_factor_120hz` now reads shelf 1.66, ledge 1.28, **road 1.012**, table 0.938.
So the road scene has crossed the 8.33 ms line on the MEAN.

**Do not upgrade the road scene to "real-time".** Its margin is 1.2% while its
step-time std is 0.59 ms and its worst observed step is **9.31 ms (0.89×)** —
i.e. it misses the budget on the tail. The honest form, and the one consistent
with the plan §1 rule that real-time is always qualified:

> at 16×4 the shelf and ledge scenes meet a 120 Hz budget with margin
> (1.7× and 1.3×); the road scene sits at the boundary (1.01× on the mean,
> with a 9.3 ms worst step); the table scene does not (0.94×). All scenes meet
> it at 16×2 or below.

- `dinner 16×2` remains comfortably real-time (1.89×), so the "all scenes at
  16×2 or below" half of the sentence is unchanged and still true.
- `passive` is `None` in every row: this harness does not run the read-only
  passivity probe (that is `probe_device_passivity.py`). The device-path
  passivity claim is unchanged and still rests on the 2026-07-08 measurement.

### Status of the `paper/NUMBERS.md` pending item

The 2026-07-13 "pending: device re-verification" note is now **discharged** for
the timing table. The E-R1 frozen-ring x86 control (plan §6.9, "while the pod
is up") was **not** run — out of scope for this paper and not attempted.
