# Stage E5 — η Sweep on the "Dinner is Served" Scene

Reproduces the dinner scene with the passive energy-bounded injection mechanism, swept over η ∈ {0.0, 0.1, 0.3, 0.5, 1.0}.

## What changes visually as η increases

- **η = 0.0**: No modal injection. Plates remain stationary — pot drops and bounces, plates ignore it entirely.
- **η = 0.1**: Plates lift slightly (~0.6 mm/s peak velocity). Subtle but perceptible response.
- **η = 0.3**: Clear plate motion (~1 mm/s). This is the default value — good visual response without feeling exaggerated.
- **η = 0.5**: Strong response (~1.3 mm/s). Plates jump noticeably above the table surface.
- **η = 1.0**: Maximum response (~1.8 mm/s). Plates jump high. Starts to look slightly exaggerated — full rigid energy loss transferred to modal vibrations.

The response saturates around η = 0.5. Beyond that, additional energy budget increases amplitude but the visual character doesn't change much. At η = 1.0, the physics is still energy-bounded (no energy creation) but the response looks stronger than one would expect from a real table.

## Energy invariant

For every η, the cumulative energy invariant holds at every step:

```
Σ ΔE_modal  ≤  η · Σ E_loss  +  ε_tol
```

| η | Σ ΔE_modal (J) | η · Σ E_loss (J) | Max margin (J) |
|---|---|---|---|
| 0.0 | 0.000 | 0.000 | 0.000 |
| 0.1 | 3.172 | 4.178 | 1.006 |
| 0.3 | 6.535 | 12.623 | 6.088 |
| 0.5 | 11.789 | 21.145 | 9.356 |
| 1.0 | 27.636 | 42.895 | 15.258 |

Zero violations across all runs.

## Outputs

- `docs/stageE5/dinner_eta_*.gif` — Animated side-view for each η.
- `docs/stageE5/eta_sweep_strip.png` — 5-panel comparison at t = 500 ms.
- `docs/stageE5/energy_invariant.png` — I_K vs L_K for all η values.
- `docs/stageE5/data_eta_*.json` — Raw simulation data.
