# Scenes and Demo Styles — Reference

The reduced-coupled AVBD scripts accept two top-level preset selectors:

```bash
--scene <name>        # geometry + impactor parameters
--demo-style <name>   # visual amplification (γ, η, exaggeration, ...)
```

Pick a coherent bundle from each, then override individual knobs only when needed. The preset definitions live in [`scenes/presets.py`](../scenes/presets.py).

## Scene presets

| name | shelf (L × W × h_t) | impactor (mass, v0, drop) | default material |
|---|---|---|---|
| `research-baseline` | 30 × 15 × 0.5 cm | 0.5 kg, −1 m/s, 15 cm | wood |
| `cutting-board`     | 30 × 20 × 2.5 cm | 0.15 kg, −2 m/s, 25 cm | wood |
| `pantry-shelf`      | 60 × 30 × 1.5 cm | 0.25 kg, −0.5 m/s, 20 cm | plastic |
| `dining-table`      | 100 × 60 × 3.0 cm | 0.5 kg, −1.5 m/s, 30 cm | wood |
| `metal-plate`       | 30 × 15 × 0.5 cm | 0.5 kg, −1 m/s, 20 cm | steel |

**Key intuition:** the modal response is *very* sensitive to `shelf_thickness` (bending stiffness ∝ h³). At fixed material and impactor, going from 5 mm to 30 mm cuts peak |q| by ~10×. The presets bundle thickness with an appropriately scaled impactor so the visible response stays similar across scenes.

> **Reproducing the benchmarks in `docs/sweep_*/RESULTS.md`:** those sweeps were calibrated at `impactor_drop_height = 0.02 m` (2 cm) with `impactor_v0_y = -1 m/s`, NOT at the preset's demo-friendly drop heights above. The preset defaults are 15–30 cm so the cube *visibly falls* in viser, but that gives ~5–10× more kinetic energy at impact, so probe rise / peak |q| numbers will be larger than the benchmark tables. To exactly reproduce the sweep numbers, pass `--drop-height 0.02 --v0-y -1.0` explicitly on top of `--scene research-baseline`.

## How slab thickness affects the result

The `shelf_thickness` parameter is the single most sensitive knob in the whole pipeline. Increasing it cuts visible response *fast* — the bending stiffness scales as h³, and most response metrics scale as some negative power of h. Two formulas tell the whole story:

```
D_flex = E · h_t³ / (12·(1-ν²))           # flexural rigidity, ∝ h³
μ_area = ρ · h_t                           # mass per unit area,  ∝ h
ω_n     = (n·π/L)² · √(D_flex / μ_area)    # natural frequency,  ∝ h
```

So when you double the thickness:

- bending stiffness grows **8×** (h³)
- mass per area grows **2×** (h)
- natural frequency grows **2×** (h)
- static deflection under a given load drops **8×** (1/h³)
- peak modal `q` under an impulse drops ~4× (1/h²) — see below

### Measured sweep on the wood-shelf scene

This is a thickness sweep at fixed material (E = 10 GPa wood), fixed impactor (0.5 kg, −1 m/s drop), `--modal-jump-gain 8`, 120 frames. Hardware: CPU, Apple Silicon.

| `shelf_thickness` | ω₁ | Peak \|q\| | Peak v_lift | Probe rise (γ=8) |
|---:|---:|---:|---:|---:|
| **2.5 mm** | 14.9 Hz | 1398 µm | **443** mm/s (clamped) | **5851 µm** |
| **5.0 mm** *(research-baseline)* | 29.8 Hz | 448 µm | **443** mm/s (clamped) | **5072 µm** |
| **10 mm** | 59.6 Hz | 222 µm | **443** mm/s (clamped) | **3323 µm** |
| **15 mm** *(pantry-shelf)* | 89.4 Hz | 100 µm | ~280 mm/s | ~2700 µm |
| **20 mm** | 119 Hz | 44 µm | 195 mm/s | **2194 µm** |
| **25 mm** *(cutting-board)* | 149 Hz | 28 µm | ~150 mm/s | ~1500 µm |
| **30 mm** *(dining-table)* | 179 Hz | 19 µm | ~140 mm/s | ~1200 µm |
| **50 mm** | 298 Hz | **13 µm** | 126 mm/s | **924 µm** |

Three things this table tells you:

1. **Peak |q| collapses with thickness.** From 2.5 mm to 50 mm the modal coordinate drops ~108× — almost exactly the predicted 1/h² scaling for impulse-driven response. At 50 mm the shelf is *effectively rigid* in modal terms; the modal block barely moves.

2. **The probe-rise curve is gentler than peak-|q| because the `v_max` clamp masks the difference for thin shelves.** With default `modal-jump-max-height = 0.01 m`, `v_max = √(2·g·h_max) ≈ 0.443 m/s`. At thickness ≤ 10 mm the natural `v_lift` exceeds this ceiling and the clamp binds — so the probe rise is set by the clamp, not by physics. Past ~20 mm the clamp stops binding and probe rise tracks the physics directly (still ~`1/h²`).

3. **The natural frequency rises 20×** going from 2.5 mm to 50 mm. The 50 mm slab rings at 300 Hz — far above the high-pass filter's 30 ms cutoff, so the filter passes the signal cleanly, but the bending displacement is so small there's nothing for the jump-gain knob to amplify.

### What this means for picking a scene

| You want… | Pick |
|---|---|
| Visible response with γ=1 (honest physics) | `research-baseline` or any preset with `shelf_thickness ≤ 10 mm` |
| Realistic kitchen/desk furniture geometry | `cutting-board`, `pantry-shelf`, or `dining-table` — but expect to use γ ≥ 4 |
| "Demo this looks like a real table" | `dining-table` + `paper-figure` style, or use `--render-thickness 0.03` + a thinner physical shelf |
| Energy-budget sanity checks | `research-baseline` + `honest` style |

### True 3D slab vs. plate theory

Would building a real 3D tet-mesh slab give different results? **Not for visible response.** Bending stiffness scales as h³ in *any* model — Euler-Bernoulli (current), Mindlin-Reissner (shear-deformable), full 3D linear elasticity. A true 3D mesh adds:

- Through-thickness shear modes (~5000 m/s wave speed → ~100 kHz at 5 cm thickness, way above what matters for visible response)
- Top vs. bottom contact distinction (drop things on either face)
- Small corrections to the bending modes for thick plates

None of those make a 5 cm slab visibly flex under a 0.5 kg impactor at 1 m/s. **A real slab is physically rigid at room-temperature impact**, and the reduced-coupled AVBD model is being honest about that — you can't fake a hop out of a slab that doesn't bend.

### `--shelf-thickness` (physical) vs `--render-thickness` (cosmetic)

Two separate knobs — keep them distinct:

| Knob | What | When to change |
|---|---|---|
| `--shelf-thickness` | Used in `D_flex = E·h³/(12·(1-ν²))`. Real physics. | When you want a stiffer / softer scene. |
| `--render-thickness` | Cosmetic-only slab extrusion in viser. Decoupled from physics. | When you want a *thin* (e.g. 5 mm) plate physics to look like a *thick* (25 mm) table to the viewer. |

A common workflow: pick a thin `shelf_thickness` (5 mm) for visible modal response, but set `--render-thickness 0.025` so it *looks* like a 25 mm cutting board on screen. The physics is honest, the visuals are credible.

In the live viser GUI, both knobs are independent sliders: "shelf thickness [mm]" in the **Scene rebuild** folder (physical — requires Apply to rebuild) and "render thickness [mm]" in the **Demo knobs (live)** folder (cosmetic — instant update).

### research-baseline
The 5 mm thin shelf used by every benchmark and test in this repo. Pick this preset to reproduce the numbers in [`docs/sweep_modal_impedance/RESULTS.md`](sweep_modal_impedance/RESULTS.md) and [`docs/sweep_jump_gain/RESULTS.md`](sweep_jump_gain/RESULTS.md). It's the "thin slat" scenario — unusual geometry, picked because it gave visible bending without exaggeration in the original demo.

### cutting-board
A realistic 25 mm hardwood cutting board (30 × 20 cm). Drop something kitchen-sized — a knife, a rolling pin. Probes are placed at the corners (`probe_z_offset = 6 cm`) where the second bending mode is dominant.

### pantry-shelf
A longer, thinner 15 mm shelf (60 × 30 cm). Closer to the DCR paper's spice-jar-on-shelf use case. Mode 1 frequency is low (~140 rad/s) → slower visible ringing.

### dining-table
The big one: a 30 mm hardwood dining table (100 × 60 cm), 0.5 kg impactor at 1.5 m/s. Realistic for reproducing the DCR Fig. 1 dinner-scene shot. Modes are stiff (ω₁ ≈ 100 rad/s) → small-amplitude bending, so demo styles with γ ≥ 4 are recommended to see anything.

### metal-plate
5 mm steel. Stiff and fast — impulse-dominated probe response, almost no sustained sag. Useful for testing the IIR mode's transient response on high-frequency material.

## Demo-style presets

| name | jump γ | impedance g | η | display × |
|---|---:|---:|---:|---:|
| `honest`       | 1  | 1 | — | 1 |
| `visible`      | 4  | 1 | — | 1 |
| `aggressive`   | 12 | 1 | 0.5 | 1 |
| `paper-figure` | 8  | 1 | — | 10 |

### honest
γ=1 means no artistic amplification. Use this when numerical fidelity matters (paper energy plots, passivity tests).

### visible
The recommended default for screencaps and demos. Wood-shelf probe rises ~3 mm at γ=4 — clearly visible at the camera distances we use.

### aggressive
γ=12 with a 4 cm hop ceiling (`modal-jump-max-height = 0.04`) and the passive energy cap engaged at η=0.5. The cap binds the maximum modal energy injection per substep to half the rigid-body energy lost on impact, which keeps the aggressive lift physically defensible.

### paper-figure
γ=8 combined with `display-q-exaggerate = 10`. The 10× exaggeration is render-only — the physics is honest. It's there to make the support deformation visible in a still figure where you don't have motion cues. **Don't use it for video** — the exaggeration breaks frame-to-frame motion continuity.

## CLI resolution order

```
preset defaults  ←  individual --<flag> overrides on the CLI
                ←  live GUI changes (viser only)
```

So:

```bash
# Use cutting-board defaults except override jump gain.
--scene cutting-board --modal-jump-gain 6

# Use dining-table defaults but make the impactor heavier.
--scene dining-table --impactor-mass 1.5

# Use research-baseline but bump the gain.
--scene research-baseline --demo-style visible --modal-jump-gain 8
```

In the live viser GUI, the **Demo knobs (live)** folder lets you sweep γ, η, τ, render-thickness, substeps in real time — no rebuild needed. The **Scene rebuild** folder lets you change material / shelf thickness / impactor parameters and press Apply; the world is reconstructed in place.

## Adding a new scene

1. Add an entry to `PRESETS` in `scenes/presets.py`.
2. Update the tables above.
3. Run `--list-scenes` to confirm discoverability.

If your scene has a different body count (more probes, additional impactors, etc.), you may need to also touch `scenes/reduced_support_shelf.py` — the current scene builder assumes one impactor + N probes.
