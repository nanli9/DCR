# MIG teaser figure + supplementary video

Both artifacts come from the same frozen pose traces, so the figure and the
video can never disagree about what happened.

```
record_teaser.py   ->  out/teaser_<case>.npz + .manifest.json   (the sim)
fig_teaser.py      ->  out/fig_teaser.pdf   -> paper/figures/   (Figure 1)
make_teaser_video.py -> out/teaser_video.mp4                    (supplementary)
render3d.py        ->  shared painter's-algorithm renderer
```

## Reproducing

```bash
.venv/bin/python benchmarks/paper_fig/record_teaser.py --case deployed --verify-unperturbed
.venv/bin/python benchmarks/paper_fig/record_teaser.py --case steel    --verify-unperturbed
.venv/bin/python benchmarks/paper_fig/fig_teaser.py                # -> fig_teaser.pdf
.venv/bin/python benchmarks/paper_fig/make_teaser_video.py         # -> teaser_video.mp4 (needs ffmpeg)
cp benchmarks/paper_fig/out/fig_teaser.pdf paper/figures/
```

`--quick` on the video renders every 4th frame for iterating on layout.

## What is recorded

Sim setup mirrors `x1_passivity/run_governed_accuracy.run_arm` exactly — same
builder defaults, `settle=8`, `nframes=100`, `_modal_symplectic=True`,
`apply_relax`/`apply_passivity`, `eta=1` — so a frame here is the same frame
the paper's numbers come from. The canonical case reproduces the paper's
§Accuracy cell exactly (1555.6 J ungoverned, 29.26 J governed, 8.22 J
self-converged).

Three arms per case, each an **independent build stepped from its own reset
state**. Nothing is toggled mid-trajectory: a mid-run toggle would compare a
diverged state against itself.

Ungoverned arms run the reservoir accounting live with `passivity_gamma`
pinned to 1.0 (the paper §3.1 protocol), which is what lets the figure draw
the supply curve on an arm that is not governed. `--verify-unperturbed`
asserts bitwise identity against a ledger-free run rather than assuming it;
both cases pass with `max|dpos| = max|dq| = 0`.

## Cases

| case | budget | board | ungoverned | governed | reference (K=500) |
|---|---|---|---|---|---|
| `canonical` | 8×2 | E=0.5 GPa | 1555.6 J | 29.26 J | 8.22 J |
| `deployed` | 1×8 | E=0.5 GPa | 22352 J | 29.49 J | 8.22 J |
| `steel` | 1×8 | steel | 48299 J | 17.81 J | 0.0706 J |

`deployed` is Figure 1. Against the impulse oracle (7.92 J) it reproduces the
paper's deployed-cell ratios: 22352/7.92 = 2822× and 29.49/7.92 = 3.7×.

## Budget vocabulary (binding)

`K×S` = K constraint iterations per substep, S substeps per 1/120 s frame.
`1×S` is the one-iteration small-step regime of Macklin et al. (SCA 2019),
which is a legitimate schedule, **not a universal engine default** — nothing
in the figure, video or paper may say "what XPBD ships". 1×8 and 2×4 are
described as *production-like interactive budgets*; 1×16 as a *small-step
stress budget*. `BUDGET_LABEL` in `record_teaser.py` is the single source of
truth. Note also that equal `K·S` is not equal cost: a substep repeats
contact generation and integration, so 1×16 is materially dearer than 8×2 at
the same sweep count.

## Renderer: draw order

`render3d.py` is a painter's-algorithm rasteriser, which cannot by itself
separate the support slab from a body resting on it: a body's base is
coplanar with the slab top to within microns, so slab cells in front of the
body win on centroid depth and paint over its lower faces — visible as a
notch bitten out of the impactor's base. Primitives therefore carry a
`layer` (`LAYER_SUPPORT` < `LAYER_BODY`) resolved before the depth sort.

That order is exact only while every body sits on top of the deflected
surface, so `assert_layering_valid` checks exactly that, per frame, against
the slab sample nearest in (x, z) — the *deflected* surface, not the rest
plane, since the board sags several mm under load and a body resting on it is
legitimately below its own rest height.

The guard is not decorative: it caught that from logged frame 66 (t = 0.55 s)
the **ungoverned** soft-board run drives `book_0` clean through the board
(22.8 mm below the local surface). That is a real symptom of the same
truncation energy — contact fails outright — but a body inside the support
cannot be depth-ordered honestly, so the soft-board video beat stops at
frame 64 and says so on screen. The steel case never trips it, and the
teaser's frame 50 is well before it.

## Honesty constraints these artifacts are built to respect

- **Three panels, not two.** A two-panel off/on image would claim trajectory
  recovery; the paper measures the opposite. The converged reference stays.
- **True scale everywhere.** No exaggeration factor; `slab_top` takes
  `exaggeration=1.0`.
- **One locked camera.** Framing is computed once over every arm (and, in the
  video, every displayed frame) so the view never drifts between panels.
- **Bystander silhouettes only.** The impactor's descent is the input, not a
  result, so it gets no ghost.
- **The rigid rebound is left visible.** The impactor bounces in both budgeted
  arms and rests in the reference; the bound governs modal storage only, and
  the figure does not hide that.
- **On the soft board the books legitimately move** (the reference lifts one
  19 mm). The governed run under-moves them. That is the paper's "bounded, not
  faithful" finding, and it is the reason the soft board — not the steel one —
  is the paper figure.
