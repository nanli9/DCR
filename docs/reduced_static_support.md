# Reduced-Coordinate AVBD — Static-Sag Refactor

This document describes the cleaned secondary extension to the reduced-coordinate AVBD support coupler. It strips the v1 prototype down to the one thing the reduced support cleanly provides: **persistent static compliant support deformation under resting loads**, with rigid contacts seeing the deformed geometry. Distant transient response is explicitly out of scope — the post-fix DCR coupler is the right path for that.

## What the refactor does

The reduced support is represented as

```
x_s(q) = x_s,0 + U · q
```

with reduced support energy

```
E_q(q) = (1/2) q^T K_q q
```

(or `(1/2) Σ_k ω_k^2 q_k^2` for the diagonal modal sub-block). The contact constraints see the deformed support geometry `C(x, q) ≥ 0` via the AVBD anchor `anchor_y = floor_y_rest + U_y · q`. The q-block is solved inside the AVBD iteration loop by minimising the augmented Lagrangian for `q` exactly as in the v1 spec §6/§7 — but in the cleaned mode, **nothing else fires**.

## How to use

```bash
# Static-sag mode (cleaned path).
uv run python scripts/run_reduced_support_shelf.py \
    --reduced-static-support --iterations 8 --frames 120

# In code:
build_reduced_support_shelf(..., reduced_static_support=True)
# or:
world.attach_reduced_support(rs, ..., static_only=True)
```

`--reduced-static-support` implies `--no-overlay`. The two modes are not meant to be composed.

## Files changed

| File | Change |
|---|---|
| `dcr/avbd/reduced_support_solve.py` | Added `static_only: bool = False` field on `ReducedSupportCoupler`. Added instrumentation fields `last_q_norm`, `last_max_support_deflection`, `last_overlay_events_fired`, `cum_overlay_events_fired`. In `post_step`, an early return short-circuits the entire overlay / kick / cap / cooldown / high-pass path when `static_only=True`. The kick path increments `cum_overlay_events_fired` only when a non-zero Δv is actually injected. |
| `dcr/avbd/world.py` | `attach_reduced_support(..., static_only=False)` plumbs the flag through. When `static_only` is set, the wrapper forces `rs.overlay_enabled = False` and `rs.restart_overlay_each_step = False` so the rest of the codebase sees a consistent flag state. Energy log appended each step now carries the static-mode instrumentation. |
| `scenes/reduced_support_shelf.py` | `build_reduced_support_shelf(..., reduced_static_support=False)` plumbs the flag through. Setting it forces `overlay_enabled=False`. |
| `scripts/run_reduced_support_shelf.py` | New `--reduced-static-support` CLI flag. When set, the run script prints the static-mode diagnostic line (`|q|`, `max_defl`, `overlay_events`) per frame and adds a summary that flags any nonzero `cum_overlay_events`. |
| `tests/avbd/test_reduced_static_support.py` | **New** — 7 tests pinning the static-sag guarantees (resting sag, relaxation, deformed-geometry visibility, zero overlay events, no probe Δv injection, iteration stability, q-block runs). |
| `docs/reduced_static_support.md` | **New** — this document. |

## Overlay code paths disabled in static-only mode

All identified in `dcr/avbd/reduced_support_solve.py` and gated by the `static_only` flag in `post_step`:

| Path | Original location | Behaviour in static mode |
|---|---|---|
| `_assemble_r_tilde` two-rate IIR sub-step | `post_step` lines 503–592 | Skipped entirely. |
| High-pass differencing (`_r_tilde_prev`) | `post_step` lines 506–515 | Never executed; `_r_tilde_prev` stays `None`. |
| Probe Δv injection (`solver.v.assign`, prev_v) | `post_step` lines 632–678 | Skipped; probe velocities only change through gravity + AVBD contact response. |
| Energy cap (`α = √(η·E_src/E_inj)`) | `post_step` lines 599–630 | Skipped; `last_alpha_cap = 0.0`. |
| Cooldown gate | `post_step` lines 453–461, 685–690; `_assemble_r_tilde` line 730 | Skipped; `_probe_cooldown` stays empty. |
| Physical F_n cap (`K_safety · m·|v|/h`) | `_assemble_r_tilde` lines 744–772 | `_assemble_r_tilde` is never called. |
| `prepare_step(body_v_pre_y)` | `world.step` lines 504–510 | Still called but the cached `_body_v_pre_y` is unused. |

What remains (the only physically meaningful piece): `substep_begin_hook` seeds the anchors at `floor_y_rest + U_y·q_hat`; `iteration_hook` solves the r×r block `H_q · Δq = −g_q` with `g_q = (1/h²) M_q (q − q_hat) + K_q q + D_q qdot + Σ F_n J_q` and writes deformed anchors back; `substep_end_hook` updates `qdot = (q − q_prev_macro)/h`.

## Numerical before/after

Scene: 0.5 kg impactor dropped 2 cm onto a 30 × 15 cm steel-like shelf (E = 200 GPa, h = 5 mm), 6 bending + 4 bump modes, heavy mass-proportional Rayleigh damping (α₀ = 50, α₁ = 5×10⁻⁴), AVBD iters = 8, h = 1/120 s, 120 frames to steady state.

| Configuration | Sag @ center | \|q\| | Max deflection | Step time | Overlay events |
|---|---|---|---|---|---|
| A. Rigid-only (no reduced support) | 0 | 0 | 0 m | 2.36 ms | 0 |
| B. Reduced + v1 overlay | 3.95 × 10⁻⁵ m | 4.03 × 10⁻⁵ | 3.95 × 10⁻⁵ m | 9.74 ms | **65** |
| C. Reduced + static (new) | 1.34 × 10⁻⁵ m | 1.33 × 10⁻⁵ | 1.34 × 10⁻⁵ m | 5.71 ms | **0** |

The reduced+overlay (B) figure is contaminated by the IIR transient peak being added on top of `d_bare` every step that the high-pass admits. Configuration C is the honest static sag at fixed-point. The step-time difference reflects the bypassed overlay assembly / sub-stepped IIR / energy-cap arithmetic.

## Iteration stability (acceptance criterion)

Same scene, end-of-run (120 frames) values:

| AVBD iters | \|q\| | Max deflection |
|---|---|---|
| 8  | 1.328 × 10⁻⁵ | 1.342 × 10⁻⁵ |
| 16 | 1.304 × 10⁻⁵ | 1.318 × 10⁻⁵ |
| 32 | 1.314 × 10⁻⁵ | 1.328 × 10⁻⁵ |

Relative spread < 2%, well inside the 15% tolerance used by `test_static_sag_stable_across_iterations`. Compare this to the v1 overlay path, where the same scene gave probe Δv that varied 10–100× between iters=4 and iters=32 (the original motivation for the F_n cap heuristic).

## Acceptance against the brief

> This branch is successful only if static sag works without overlay transient kicks. If the visible response depends on overlay, cooldown, high-pass, or heuristic cap logic, the branch has failed.

- Static sag is non-zero and physically scaled (≈ 13 µm under a 5 N load on the synthetic shelf). ✓
- `cum_overlay_events_fired == 0` for every test that exercises `static_only=True`, asserted in `test_no_overlay_event_in_static_mode`. ✓
- Probe velocities don't show injection kicks (`< 0.1 m/s` over the full run vs the 4–6 m/s seen in v1), asserted in `test_no_probe_velocity_injection_in_static_mode`. ✓
- Removing the load relaxes q toward zero, asserted in `test_q_relaxes_when_load_removed`. ✓
- A distant probe sees the deformed shelf at its (x, z), asserted in `test_probe_sees_deformed_shelf_geometry`. ✓
- Sag is iteration-stable, asserted in `test_static_sag_stable_across_iterations`. ✓
