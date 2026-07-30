# Reconstruction-Contrast Supplementary Video — Report

## Verdict

**Submission-ready: YES.** All three verifiers (numbers, claims, tech) return
pass/confirmed. Every on-screen scalar traces to the logged trajectory
`onesweep_video_traj.npz` with zero relative difference; nothing is hardcoded or
fabricated. Claim discipline, anonymity, and honesty all hold on every rendered
frame. The remaining flagged items are one framing risk (major, from the
`numbers` verifier) and three cosmetic/non-blocking nits; none of them fabricate
data, and the video already handles the underlying compromise honestly. No fix
phase was run (`FIX: null`); see "Verifier issues" for what that leaves open.

**Distinct from the companion video: YES.** This is a new, independently built
artifact (`make_onesweep_video.py` -> `out/onesweep_video.mp4`). It imports only
`figstyle` for aesthetics and does not touch, import from, or resemble the shipped
`mig_short_video.mp4` / `make_short_video.py` / `teaser_video.mp4` /
`make_teaser_video.py`. Those protected files are byte- and mtime-unchanged. The
companion video is the six-beat §12 decision diagnostic; this video is a
single-cell, three-arm reconstruction contrast on one cold impact. Different
substrate, different message, different render.

## Operating point

- **Scene:** ledge (chosen over the equally-clean shelf for larger, more legible
  energy separation; dinner rejected — its heavy pot never lets the symplectic
  arm inject).
- **Stiffness scale:** s = 6.521e-6 (a fine-sweep point between the 9-point grid).
- **Regime:** cold single-row impact, isolated (n_active <= 1, runner-up gap
  ~50 m), gravity off, v0 = -1 m/s, h = 1/120 s, substeps = 1, iterations = 1.
- **Driven mode:** 1, with omega*h = 0.0632, b = (omega h)^2 = 3.99e-3.
- **Mass ratio:** m/M = 0.0751 row-visible (M = 1/w_r = 13.31 kg) / 0.02 for the
  full 50 kg impactor.
- **Row quantities:** w_r = 0.0751, w_m = 0.341, w_eff = 0.256, L = 0.902,
  a_tilde = 1.44e-4. (Note: the on-screen/npz values are L = 0.902404 and
  w_eff = 0.255915; the task's prose summary listed stale figures L = 0.778 /
  w_eff = 0.302 — the frames use the real logged values, see verifier note below.)
- **Energy budgets:** incident bound E- = 0.5 (1/w_r) v0^2 = 6.654 J;
  full-impactor KE E0 = 25.0 J.

A single cell gives all three arms a clean predictor -> post-impact-sign match.

## The three rho values (all computed from the cold row BEFORE stepping)

| Arm | rho name | value | rule | prediction |
|-----|----------|-------|------|------------|
| 1 | MASS_BE (mass weight + backward-Euler) | rho = 2.642 = L/(w_m + 2 a_tilde), note R4 | >1 -> inject | INJECTS |
| 2 | IMPL_BE (implicit weight + BE) | rho_impl = -0.0380 = (G_impl - D_impl)/(w_r + D_impl + 2 a_tilde) | <1 -> passive | PASSIVE |
| 3 | IMPL_SYMP (implicit weight + shipped symplectic implicit-midpoint) | rho_mid = 19.02 = [L + 2(w_m - w_r)]/(w_r + 2 a_tilde), note R6 | >1 -> inject | INJECTS |

All three post-impact (one-substep) energy signs match their predictor
(SIGN_MATCH = 3/3).

## Beats (52 s, 5 beats; every frame is a real solver substep)

- **Beat 0 — SETUP (~0-5 s):** schematic, the predictor rho = L/(w_m + 2 a_tilde),
  the rule "predict before you solve", and scope statement (one sweep / cold
  start / e = 0 / hard contact / single row).
- **Beat 1 — Arm MASS_BE, PREDICT + PLAY (~5-18 s):** rho = 2.64 > 1 -> predicts
  inject. Modal ring-up crosses the incident line (6.65 J, peak ratio 2.71x) and
  the energy ledger dE_cum crosses 0 (peak +2.40 J). Side view drives the real
  corner_y (over-penetration to -0.52 m) and surf_disp (surface mode-shape ring).
  Verdict: INJECTS (final ledger -6.90 J as the finite impactor exhausts).
- **Beat 2 — Arm IMPL_BE, FIX (~18-30 s):** m_eff repricing, rho_impl = -0.04 < 1.
  Same incident state; ledger stays <= 0 (peak -2.03 J, final -6.89 J).
  Verdict: PASSIVE. Honestly captioned "same-size ring, funded by rigid-KE loss"
  because the modal ring is the *same* 2.71x size as arm 1 — the passive verdict
  rests on the ledger sign, not ring size.
- **Beat 3 — Arm IMPL_SYMP, TWIST (~30-43 s):** host reconstructs qdot = 2 dq/h
  (4x modal KE, data-confirmed: IMPL_SYMP/IMPL_BE modal_ke = 4.000 exactly at
  impact), grounded by rho_mid = 19.0 > 1. Ledger climbs to +18.43 J and stays
  above budget -> INJECTS and is the only sustained runaway (corner plunges to
  ~-0.88 m; peak modal 6.52x incident = 43.4 J). The implicit-weight remedy FAILS
  under the shipped symplectic reconstruction.
- **Beat 4 — CODA (~43-52 s):** three dE_cum ledgers overlaid (IMPL_SYMP diverges
  up; the two BE arms track and stay net-negative) + the takeaway rule; then the
  nonmodal "no modes required" thumbnail (scalar mass-spring, real
  nonmodal_dE_mass/dE_impl vs (wh)^2, boundary at (wh)^2 = 1 + m/M = 2, closed-form
  cross-check reldiff ~4e-15).

## Final MP4

- **Path:** `/Users/nan/Desktop/DCR/benchmarks/paper_fig/out/onesweep_video.mp4`
- **Duration:** 52.0 s
- **Resolution:** 1920x1080, 30 fps, 1560 frames, h264, yuv420p (even dims), +faststart
- **Size:** 1,849,065 B. Rebuilds byte-identical (md5 06244586b812e31f1f5ecf27d92c7552)
  on a fresh run — deterministic, no date/random.
- **Metadata:** `-map_metadata -1`; container tags are generic ffmpeg/isom defaults
  (no author / path / filename / date / SHA).

## Verifier issues and status

Because `FIX: null`, **no fix phase ran**; the resolution column reflects whether
the video *as shipped* already addresses each item.

| # | Verifier | Severity | Issue | Resolved as-shipped? |
|---|----------|----------|-------|----------------------|
| 1 | numbers | **major** | Peak-modal/incident ratio is >1 on all three arms (2.71 / 2.71 / 6.52), so it is NOT a discriminator: the PASSIVE arm shows the same 2.71x ring-crossing as the injecting mass arm. Beat 1's "ring exceeds the incident line" note risks a viewer conflating ring-crossing with injection. | **Partially.** The video already anchors classification on the dE_cum ledger sign (the real 3-way separator) and beat 2 is honestly relabeled "same-size ring, funded by rigid-KE loss". The residual risk is beat 1's framing not mirroring that caption. Suggested fix (soften beat 1's "ring exceeds the incident line" note / add "ring size alone does not decide the sign") was NOT applied. **Non-blocking but recommended.** |
| 2 | numbers | minor | Task prose lists L = 0.778 / w_eff = 0.302, but npz/video use L = 0.902404 / w_eff = 0.255915. | **N/A — no video change.** The prose is stale; the rendered values are the correct traceable npz values (rho recomputes to 0 reldiff). Flagged only so stale prose is not used to "correct" the frames. |
| 3 | claims | minor | On the Arm-3 predict card (~30-34 s), the "TWIST" beat tag is partially occluded by the long centered title (trailing "T" overlapped). Cosmetic only. | **Not applied.** Optional: shorten the Arm-3 title or nudge the tag left. **Non-blocking.** |
| 4 | tech | minor | New untracked dir `benchmarks/paper_eval/t_onesweep/` follows the sibling `paper_eval` convention (er1_/x1_/...) rather than the literal `onesweep_*` naming rule. Touches no tracked file. | **Not applied.** Naming deviation only; all video-specific artifacts do use the `onesweep_*` prefix. **Non-blocking.** |
| 5 | tech | minor | In the CODA overlay the mass-only and implicit-BE ledgers are nearly coincident and both end net-negative (-6.90 vs -6.89 J); the inject-vs-passive split for those two lives in the impact-substep peak sign (+2.40 vs -2.03 J) shown per-arm, not in the overlay endpoints. | **Handled honestly, not annotated.** This is the disclosed compromise; the per-arm beats show the peak sign and the "funded by rigid-KE loss" relabel. Optional fix: mark the mass-only trace's +2.40 J early peak in the overlay. **Non-blocking.** |

### Core mandates that PASS (all three verifiers agree)

- **No fabrication:** every on-screen scalar reads from `onesweep_video_traj.npz`;
  rho = 2.6416, rho_mid = 19.02, rho_impl = -0.0380, peak ratios 2.71/2.71/6.52,
  ledger peaks +2.40 / -2.03 / +18.43 J, nonmodal boundary (wh)^2 = 2 all recompute
  at reldiff 0. The 4x/2x reconstruction factor is data-confirmed, not just
  definitional.
- **Claim discipline:** injection conceded as prior art on every footer
  ("a known effect / finite-iteration coupling"); threshold called an
  "energy-sign boundary" (never stability/blow-up/unstable/diverge); rho framed as
  a per-row predictor; m_eff repricing never framed as a novel object; no banned
  acronym; no real-time claim.
- **Anonymity:** no author name, repo path, filename, git SHA, absolute path, or
  date in any rendered frame; scene name "ledge" never drawn (only the word
  "ledger"); container tags generic.
- **Honesty:** the passive arm is not faked — it shows the same 2.71x ring and the
  verdict rests on the logged ledger sign; the arm-3 runaway uses real logged
  values with measured language.

## The reported compromise (from the DATA agent, for the record)

The clean 3-way injection classification is by the **energy-ledger sign dE**
(the note's definition, "injection = E+ > E-"), which matches all three predictors.
The task's parenthetical **peak-modal-KE <= incident** criterion for the passive
arm is NOT a clean 3-way separator at this (or any) shipped-scene operating point:
the impactor is heavy (50 kg / 25 J reserve >> 6.65 J row-visible incident), so
every arm's modal ring-up eventually crosses the incident line (IMPL_BE peaks at
2.71x too). The video correctly reframes onto the impact-substep energy split
(three-way, predictor-matched) plus the dE_cum ledger over time. This is issue #1
above and is the one substantive thing a reviewer should be aware of.
