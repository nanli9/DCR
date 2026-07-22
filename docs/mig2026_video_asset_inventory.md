# MIG 2026 — Supplementary Video Asset Inventory (Stage F, video)

> **BUILT 2026-07-21.** `benchmarks/paper_fig/make_short_video.py` →
> `out/mig_short_video.mp4` (52.0 s, 1920×1080, H.264, no audio, 1.0 MB,
> metadata-stripped). Six §12 beats, ends on the decision card (not the
> governor). Every on-screen number is read live from the frozen Stage-B CSVs.
> **Beat-3 decision: 2-D curve panel, not 3-D poses** — the claim is an incident
> ratio at *equal cost* (32 row-evals: `32×1` R=0.30 holds vs `4×8` R=3.13,
> +481 J), inherently quantitative; +481 J on a soft board is not a dramatic
> launch, so a 3-D side-by-side would under-communicate "unsafe". The pose-gen
> risk below is therefore moot (not blocked — deliberately not used).
> **Penetration close-up: true-scale 2-D cross-section** (labelled, not a
> painter's-algorithm render, which `render3d.py` cannot depth-order honestly).
> Supplement repointed (`make_supplement.py` VIDEO → `mig_short_video.mp4`, §5
> rewritten); bundle re-verified 63/63 checksums + smoke PASS + scan PASS.

Authority: rewrite plan §12 storyboard (45–55 s). Purpose: map every beat of the
new decision-oriented video to a concrete asset — reusable vs. new — with its
render command and any blocker, BEFORE any rendering. Per plan §12, the video
must "no longer end as if the governor were the main product"; AVBD gets at most
a brief control view.

## Pipeline (all present, verified 2026-07-21)
- `benchmarks/paper_fig/render3d.py` — offline 3D rasterizer (Camera/Renderer).
- `benchmarks/paper_fig/make_teaser_video.py` — current 4-beat assembler.
- `benchmarks/paper_fig/record_teaser.py` — writes frozen pose `.npz` + manifest.
- Frozen poses present: `teaser_canonical.npz`, `teaser_deployed.npz`,
  `teaser_steel.npz` (+ manifests). `ffmpeg` on PATH.
- **Offline render only** (no live backend); scale/camera locked across panels.

## Beat map (plan §12)

| t (s) | beat | asset status | source / command | blocker |
|---|---|---|---|---|
| 0–6 | Schematic: existing XPBD rigid host **+** full nodal alternative **+** 16-mode extension → shared contact rows → fixed K | **NEW** | new 2-D schematic (matplotlib, reuse `fig_teaser.py` schematic strip idiom) → short animated build-on | none (vector/matplotlib) |
| 6–18 | Same-state XPBD **ungoverned vs high-iteration self-reference**; retain the visible launch | **REUSE** | `make_teaser_video.py` beats 1–2 (steel 1×8, off vs ref), relabel "governed"→drop or move later | none |
| 18–29 | Iteration allocation: **32×1 vs 4×8** at equal row count | **NEW** | needs frozen poses for shelf 32×1 (S=1) and 4×8 (S=8) at relax 0.7 → `record_teaser.py` new cases, then side-by-side render | **RISK: pose gen** — see below |
| 29–37 | Basis/cutoff: **"removing the stiff cluster is not sufficient"** panel | **NEW** | data exists (`band_limit_sweep.csv`); render a 2-D annotated panel (matplotlib), not a 3-D sim | none (data frozen) |
| 37–46 | Governor **containment** + true-scale **penetration close-up** | **REUSE + NEW** | reuse `make_teaser_video.py` beat 3 (soft-board 1×8, 3 arms) for containment; **new** penetration close-up = zoomed camera on the governed clamp frame (21.6 mm), reuse `teaser_*` poses with a tighter `Camera` | none (reuse poses, new camera) |
| 46–55 | **Decision card**: implicit if flexible → verify XPBD block/basis/iterations → governor only as containment | **NEW** | static/animated 2-D card (matplotlib), mirrors the conclusion decision rule + Decision Table | none |

## The one real risk (surface to user if hit)
- **18–29 s equal-row poses.** The 32×1 / 4×8 side-by-side needs frozen 3-D poses
  at those budgets. `record_teaser.py` currently records the 1×8 deployed / steel
  canonical cases only. Memory `[[mig-qround-queued]]` records "Q5 blocked (no
  4×1 poses)" — the equal-row 3-D comparison was previously blocked on pose
  generation. **Mitigation if blocked:** render 18–29 s as a 2-D overlay of the
  frozen `substep_sweep.csv` / `k_convergence.csv` curves (R vs. row-evals, 32×1
  holds vs. 4×8 injects) instead of a 3-D sim — data is frozen, no pose needed.
  This keeps the beat honest and unblocked. Decide 3-D-vs-2-D before rendering.

## Order of work (when video is executed)
1. Generate/confirm poses for 32×1 & 4×8 (or fall back to the 2-D curve panel).
2. Build the four NEW 2-D assets (schematic, band panel, decision card,
   penetration close-up camera) — cheap, data already frozen.
3. Re-cut `make_teaser_video.py` to the six-beat §12 timeline; keep camera/scale
   locked; AVBD only as a brief control.
4. Encode ≤ 200 MB (CFP), no author metadata (ffprobe check), then **re-run
   `make_supplement.py`** so the bundle ships the new `teaser_video.mp4` + its
   updated SHA256SUMS (the assembler must be the LAST step, per plan §11 F).

## Not yet done (Stage F tail)
- `\acmSubmissionID{}` — blocked until EasyChair registration opens **2026-07-25**.
- Final `make_supplement.py` run — after the new video + the acmSubmissionID
  land (the current bundle already carries the correct data + decision table;
  only the video asset and the ID remain to refresh).
