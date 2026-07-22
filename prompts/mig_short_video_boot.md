# Build the MIG 2026 supplementary video (Stage F, video)

## Orientation (do this before rendering anything)
1. Read CLAUDE.md, then `docs/mig2026_video_asset_inventory.md` IN FULL — it is
   the beat-by-beat asset map (reuse vs. new), the render pipeline, and the one
   real risk with its fallback. That inventory is the authority for this task.
2. Read the rewrite plan's §12 (video storyboard) in
   `docs/mig2026_practitioner_diagnostic_rewrite_plan.md`, and the claim sheet
   `docs/mig2026_claim_sheet.md` (for the decision-card wording — the video must
   not overclaim; AVBD is a brief control only, the governor is NOT the product).
3. The committed core is done: the paper (branch `paper`, worktree `paper/`,
   HEAD `ffaf08e`) and the E0 supplement (`make_supplement.py`, synced +
   smoke-tested) are complete and gate-passing. This task produces the video
   only. Do NOT touch `main_short.tex` unless a caption references the video.

## State: pipeline is present and verified (2026-07-21)
- `benchmarks/paper_fig/render3d.py` — offline 3D rasterizer.
- `benchmarks/paper_fig/make_teaser_video.py` — the current 4-beat assembler
  (steel launch → freeze → soft-board 3-arm → invariant); `--quick` for a fast
  proof. This is what you re-cut into the §12 six-beat timeline.
- `benchmarks/paper_fig/record_teaser.py` — writes frozen pose `.npz`+manifest.
- Frozen poses present: `teaser_canonical.npz`, `teaser_deployed.npz`,
  `teaser_steel.npz` (+ manifests) in `benchmarks/paper_fig/out/`.
- `ffmpeg` on PATH. **Offline render only** — no live backend, no new deps.

## The §12 six-beat timeline (45–55 s) and asset status
| t (s) | beat | status |
|---|---|---|
| 0–6 | schematic: XPBD rigid host + full-nodal alt + 16-mode extension → shared rows → fixed K | **NEW** 2-D (matplotlib; reuse the `fig_teaser.py` schematic idiom) |
| 6–18 | same-state XPBD ungoverned vs high-iteration self-reference; keep the visible launch | **REUSE** (make_teaser_video beats 1–2) |
| 18–29 | iteration allocation: 32×1 vs 4×8 at equal row count | **NEW** — see RISK below |
| 29–37 | "removing the stiff cluster is not sufficient" (band) panel | **NEW** 2-D from `band_limit_sweep.csv` |
| 37–46 | governor containment + true-scale penetration close-up | **REUSE** (beat 3) + **NEW** tight-camera penetration frame |
| 46–55 | decision card: implicit if flexible → verify XPBD block/basis/iterations → governor only as containment | **NEW** 2-D card (mirrors the conclusion + DECISION_TABLE.md) |

## The one real risk (surface to the user if hit)
The 18–29 s **32×1-vs-4×8** side-by-side needs frozen 3-D poses at those budgets.
`record_teaser.py` currently records only the 1×8/steel cases, and memory
`[[mig-qround-queued]]` records "Q5 blocked (no 4×1 poses)". **Try** generating
the poses via `record_teaser.py` first; if pose generation is blocked, **fall
back** to a 2-D overlay of the frozen `substep_sweep.csv` / `k_convergence.csv`
curves (R vs. row-evals: 32×1 holds, 4×8 injects) — data is frozen, no pose
needed, equally honest. Decide 3-D-vs-2-D for this beat BEFORE rendering; do not
block the whole video on it.

## Order of work
1. Generate/confirm the 32×1 & 4×8 poses, or commit to the 2-D fallback for
   beat 3.
2. Build the four cheap NEW 2-D assets (schematic, band panel, decision card,
   penetration-close-up camera) — data already frozen.
3. Re-cut `make_teaser_video.py` into the six-beat §12 timeline; keep camera and
   scale LOCKED across panels (compute once over all frames of all arms); AVBD at
   most a brief control view; the video must not end as if the governor were the
   product.
4. Encode ≤ 200 MB (CFP limit); verify no author metadata (`ffprobe`; the
   historical trap is FFmpeg encoder tags — those are generic and fine, but check
   there is no author/title identity).
5. **Re-run the E0 supplement assembler LAST** so the bundle ships the new video:
   `.venv/bin/python benchmarks/paper_eval/x1_passivity/make_supplement.py`
   then re-verify the clean-unpack smoke test + SHA256SUMS (63/63 before; the
   count rises by the new video). The assembler already carries the correct data
   + DECISION_TABLE.md; only the video asset (and later `\acmSubmissionID`) remain.

## Discipline
- Every on-screen number → a frozen source (claim sheet / ledger). No overclaim.
- Round 4.4×10⁷ J to the E1b neighborhood if shown; keep "governed (containment)"
  labeled as containment, never a reference.
- Deformation magnification, if any, must be labeled; OFF/ON panels share initial
  state, camera, timestep, budget and colour scale.
- Update findings.md / progress.md / task_plan.md; commit the video + the
  refreshed supplement (paper text is untouched by this task).

## After the video: remaining Stage F/G
- `\acmSubmissionID{}` — fill after EasyChair registration (window opens
  2026-07-25); hash the final PDF + video + supplement together.
- **Stage G** — six isolated reviewers on the final PDF + video + supplement,
  comprehension questions BEFORE scores (why modal DOFs; why not the impulse
  realization; main contribution; when the governor), ≤1 rewrite cycle, then
  compare against the frozen `32f2951d…` fallback and keep the stronger packet.
