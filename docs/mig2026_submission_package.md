# MIG 2026 Short Paper — Reproducibility Note & Submission Package

Companion to `docs/mig2026_results_ledger.md` (the numbers) and
`docs/mig2026_short_paper_plan.md` (the plan). This file covers plan §4
D11–D14: the reproducibility pass, the supplementary packaging, and the video
shot list.

**Blind-safety**: MIG 2026 is double-blind (verified, ledger §A0(b)). Nothing in
this file may be pasted into the submission PDF as-is — repository URLs, branch
names, machine hostnames, and author-identifying paths must be stripped or
replaced with a neutral placeholder before the repro note goes into the paper.
A blind-safe version of §1 is given in §4 below.

---

## 1. Exact reproduction of every reported number

**Machine** (single pinned host; ARM/x86 results are never mixed — chaotic
contact stacks diverge between architectures under floating-point
reassociation): Apple M4, 10 cores, 16 GB, macOS 15.2, `arm64`. Interpreter
`.venv/bin/python` = CPython 3.12.12; numpy 2.4.5, scipy 1.17.1, matplotlib
3.10.9, warp 1.13.0. CPU only.

**Determinism**: the native CPU path uses no RNG; `PAPER_CONFIG["seed"] = 0` is
reserved but unused. Runs are deterministic on a fixed machine + interpreter.
Frame counts are pinned in each harness (settle 8, logged 100) rather than
varying between "quick" and "full" modes.

| paper item | command | commit |
|---|---|---|
| Fig. 1 (teaser, F1) | `.venv/bin/python benchmarks/paper_eval/x1_passivity/run_activation_trace.py` | `7b11a3b` |
| Fig. 2 (K-convergence, F2) | `.venv/bin/python benchmarks/paper_eval/x1_passivity/run_k_convergence.py` | `3d5f91a` |
| Fig. 3 (three-solver matrix, F3) | `.venv/bin/python benchmarks/paper_eval/x1_passivity/run_solver_matrix.py` | `f884380` |
| Table 1 (post-projection validity) | `.venv/bin/python benchmarks/paper_eval/x1_passivity/run_projection_validity.py` | `aed967d` |
| §3.4 full-FEM comparison | `.venv/bin/python benchmarks/paper_eval/x3_ground_truth/run_ledge_ladder.py` | pre-existing |
| impulse backend tests | `.venv/bin/python -m pytest tests/avbd_native/test_solver_impulse.py -q` | `462b717` |
| ledger + claim freeze | `docs/mig2026_results_ledger.md` | `c217da0` |
| figure scripts | `benchmarks/paper_fig/fig_s{1,2,3}_*.py` | `7b11a3b` |
| paper source | `paper/main_short.tex` (branch `paper`) | `4c4ad1c` |

Figure regeneration (reads only committed CSVs, runs no simulation):

```sh
.venv/bin/python benchmarks/paper_fig/fig_s3_activation.py     # F1
.venv/bin/python benchmarks/paper_fig/fig_s2_kconvergence.py   # F2
.venv/bin/python benchmarks/paper_fig/fig_s1_solver_matrix.py  # F3
cp benchmarks/paper_fig/out/fig_s{1,2,3}_*.pdf paper/figures/
cd paper && latexmk -pdf main_short.tex
```

**Measurement integrity.** All four harnesses set solver knobs at runtime and
never modify solver source; the E-S3 probe instruments the γ-projection by
runtime wrappers that return the original values unchanged. Non-perturbation was
verified by reproducing the independent clamp counts exactly (162/216, 107/108,
98/108, 96/216). The E-S1b harness was validated by reproducing the
`benchmark`-branch XPBD reference cells to six digits.

---

## 2. Known reproduction hazards (record these; they cost real time)

1. **The native-thin step path.** These scenes take `world.step()`'s early
   return (`dcr/avbd/world.py:779-793`) when no DCR coupler is attached, which
   skips `_sync_avbd_to_dcr()`. Any metric that reads `dcr_body.velocity` — e.g.
   `rigid_kinetic_energy()` — silently returns **0.0**, turning a ratio's
   denominator into its `1e-9` floor and inflating results by ~10⁹. Two
   independent harnesses hit this. Mirror the state explicitly, or read solver
   arrays directly.
2. **The dinner scene was redefined on this branch** (1.2×1.0 m / E = 10 GPa →
   2.2×1.1 m / E = 1.1 GPa). Numbers for that scene are not comparable across
   branches. The long paper's dinner worst case (5.1×10³) belongs to the
   superseded scene.
3. **The relaxation axis is inert on the impulse backend** (attributes exist,
   never read). Its two relax rows are bit-identical by construction.
4. **OFF-run ledger verdicts are vacuous** for XPBD (accounting never runs) and
   absent for AVBD (no ledger object). Only the impulse backend's OFF verdict
   is evidence.
5. **The γ-projection is host-only** — there is no passivity block in the device
   step. `_modal_symplectic = True` forces the host path.

---

## 3. Supplementary package (CFP: ≤ 200 MB, videos encouraged)

| item | contents | status |
|---|---|---|
| `video.mp4` | 60–90 s, shot list in §5 | **TODO — needs an interactive capture session** |
| `data/` | the 12 CSVs below + their `.config.json` manifests | ready (committed) |
| `README.txt` | blind-safe version of §1 + §2 | draft in §4 |

Keep the whole archive under 200 MB; the CSVs total ~70 kB, so the video is
effectively the entire budget. Target ≤ 150 MB encoded.

### `data/` — exactly what the paper cites (verified present 2026-07-19)

Every claim in `main_short.tex` maps to one of these. Paths are relative to
`benchmarks/paper_eval/`.

| paper location | file |
|---|---|
| Fig. 2 (solver matrix, both rows) | `x1_passivity/out/eq2_utilization.csv`, `solver_matrix.csv` |
| Fig. 3 (K-convergence) | `x1_passivity/out/k_convergence.csv` |
| §3.1 equal-work ladder — **demoted to this supplement** | `x1_passivity/out/substep_sweep.csv` |
| §3.2 complementarity residual | `x1_passivity/out/complementarity_residual.csv` |
| §3.2 self-convergence + state metrics | `x1_passivity/out/selfconvergence.csv` |
| §3.3 governed accuracy + normalized penetration | `x1_passivity/out/governed_accuracy.csv` |
| Table 2 position-based rows | `x1_passivity/out/projection_validity.csv` |
| Table 2 augmented-Lagrangian rows | `x1_passivity/out/projection_validity_avbd.csv` |
| §3.4 full-FEM convergence | `x3_ground_truth/out/ledge_convergence.csv` |
| §3.5 CPU cost | `x5_perf/out/perf_reps_summary.csv` |
| §3.5 device timings | `x5_perf/out/perf_device.csv` |

**The substep-sweep row is load-bearing for the supplement.** The paper says
"full ladder in the supplement" (§3.1) after plan §6.12's page-budget demotion,
so `substep_sweep.csv` is not optional packaging — omitting it leaves a dangling
forward reference in the submission.

---

## 4. Blind-safe repro note (paste-ready for the submission)

> All reported solver-behaviour measurements were produced on a single consumer
> laptop (10-core ARM64, 16 GB, CPU only) with CPython 3.12 and numpy 2.4,
> including the CPU enforcement-cost timings. The single exception is the
> device-resident timing paragraph, measured on a discrete GPU workstation and
> reported separately and never pooled with the CPU numbers: chaotic contact
> stacks diverge between architectures under floating-point reassociation. The native
> CPU path uses no random number generation and frame counts are pinned in each
> harness, so runs are deterministic on a fixed machine and interpreter. Each
> figure and table is regenerated by a single command from committed CSVs; the
> measurement harnesses set solver parameters at runtime and do not modify
> solver source, and the post-projection probe instruments the projection with
> wrappers that return original values unchanged, verified by reproducing
> independent clamp counts exactly. Source and data will be released on
> acceptance.

---

## 5. Video shot list (plan §3 item 5) — 60–90 s

The plan specifies four beats, all from existing viser scenes. Recommended
order, timings, and the exact commands. **Record with no terminal, no window
chrome, and no repository path visible** (double-blind).

| # | beat | length | command | what the viewer must see |
|---|---|---|---|---|
| 1 | **The failure** | ~20 s | `run_reduced_scene_viser.py` shelf, XPBD, budget 8×2, governor OFF | the support ring exploding; overlay the modal-energy number climbing past 1000 J |
| 2 | **The fix, same budget** | ~15 s | same, governor ON | visually stable; overlay energy pinned near 29 J. Cut A/B side-by-side if possible — this is Fig. 1 in motion and is the single most persuasive shot |
| 3 | **Inert when not needed** | ~10 s | same scene at 16×4, governor ON vs OFF | identical motion; state "zero activations" on screen |
| 4 | **It is a real two-way response** | ~20 s | `run_fem_gt_viser.py --scene ledge` | reduced arm overlaid on the full-FEM reference; peak at the pedestal, not under the impact |
| 5 | **Network causality** (optional, if time) | ~15 s | `run_native_scenes_viser.py` cargo network ON vs OFF | a distant body moved through the shared support |

Narration/caption rules, binding: never say "real-time" unqualified, never say
"trustworthy", never claim the contact row or the two-way coupling as ours.
Caption beat 1 as *"un-governed, at a budget interactive solvers actually
ship"*, not as a generic property of modal contact.

---

## 6. What remains after this file

- **D10** hand to advisor; **D11–13** advisor revisions.
- **Video capture** (§5) — requires an interactive browser session.
- **A0(c)**: Sheth et al. 2015 full text — still **PENDING**, user fetching. No
  related-work sentence may treat it as resolved.
- **Submission** via EasyChair (`mig2026`), ≥ 24 h before 7 Aug 2026 23:59 AoE.
- Out of scope by decision: device-resident governor (long-paper track).
