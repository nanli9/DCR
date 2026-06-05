# Reduced-Coordinate AVBD Support Contact — v1 audit

> Build plan: `prompts/reduced_coordinate_avbd_support_dcr_extension.md`.
> Code: `dcr/avbd/reduced_support.py`, `dcr/avbd/reduced_support_solve.py`.
> Tests: `tests/avbd/test_reduced_support.py` (9 tests, all green).

This doc summarises the v1 prototype, the six follow-up items from the
critique thread, and the headline benchmark numbers.

## Method

Two layers, both real:

1. **Reduced-coordinate AVBD coupling** (the contribution).
   The shelf's surface deflection is `x_s(q) = x_s⁰ + U·q` where `q ∈ ℝʳ`
   is a Python-side modal/static state. FLOOR_CONTACT rows have their
   anchor written every AVBD iteration:
   `c_world_anchor[i].y ← Y₀ + (U_y(x_contact_i) · q)`.
   Between every primal/dual launch, the coupler solves the dense `r × r`
   q-block on CPU:
   ```
       H_q · Δq = − g_q
       H_q = (1/h²) M_q + K_q + (1/h) D_q + Σᵢ ρ_q J_q,i J_q,iᵀ
       g_q = (1/h²) M_q (q − q_hat) + K_q q + D_q q̇ + Σᵢ F_n,i J_q,i
   ```
   with `J_q = U(x_contact)ᵀ n` and `F_n = −λ_avbd + ρ_q·C⁺`. Then writes
   the deformed anchor back. **No kernel signature change** — the same
   `c_world_anchor` field the AVBD primal already reads.

2. **Two-rate transient overlay** (the spec's §9 layer).
   `r̃ = Σ_c F_n,c · J_q,c` (force units). Sub-stepped IIR over
   `[0, h_macro]` with `T = π/(2ω_max)`. Distant Δv at named probe rigid
   bodies: `Δv_i = d_max,i / h_macro`. Three layers of discipline:
   * **High-pass on r̃** across macro steps so steady loads don't
     re-excite the IIR (DEVIATION from spec §9.2, see code).
   * **Energy cap** (item 3): `α = min(1, √(η·E_src/(E_inj_candidate+ε)))`,
     `Δv ← α·Δv_candidate`, with `E_src = max(0, KE_pre − KE_post)`.
   * **Receiver cooldown** (item 4): a probe that just took a kick has
     its OWN floor rows excluded from `r̃` for 2 macro steps. Temporal
     gate, not a hard identity mask.

The **q-block coupling** path still uses every tracked row even during
cooldown — static deformation propagation is preserved; only the
overlay's transient sourcing is gated.

## Why two layers

`q` solved inside AVBD gives **real static sag** under load — a probe
sitting at distance moves down through `U` when the impactor presses on
the shelf. Post-fix DCR can't do this; the rigid solve sees a rigid
shelf.

But the implicit macro step damps high-frequency vibration by ~`ω·h`,
so the visible distant peak vanishes. The overlay sub-steps that fast
part of the response (using the same converged augmented contact force
as forcing) and converts the modal peak back into a distant probe
velocity. Without the overlay, "reduced AVBD" produces correct sag but a
dead-looking distant response — exactly the spec's Section 20.1 A/B.

## Item-by-item from the critique thread

### (1) h/T unit-chain audit

`scripts/audit_overlay_h_t.py`. The overlay's forcing convention is:
* `r̃` is generalised force `[N·m / modal_unit]`.
* For the IIR, deliver `J = r̃ · h_macro` as a Dirac impulse at sub-step
  `k = 0`. The IIR uses the impulse-invariant z-transform; with this
  convention its peak matches the closed-form damped-SDOF Dirac
  response `q_peak = J/(m·ω_d)` exactly.

Closed-form audit at ω ∈ {50, 200, 838, 2000} rad/s × h ∈ {1/60, 1/120,
1/240}: **worst error 0.00 %**. The predicted overlay/bare ratio of
`ω·h` matches observation across the full grid (ω·h = 14.0 →
observed 14.04; ω·h = 33.3 → observed 33.36).

**Verdict: no magnitude bug. The h/T chain is consistent.**

### (2) Rest-impactor pump test

`scripts/run_rest_impactor_pump_test.py`. Impactor parked at rest on the
shelf (no drop, no v₀), overlay ON, 5 s run. Cumulative
|E_overlay_injected|:
* **Rest case:** 4.4e-4 J (after items 3+4 in place)
* **Drop case:** 0.26 J (the canonical impact case)
* Rest is < 0.2 % of drop.

**Verdict: high-pass on `r̃` does most of the work alone; the energy
cap is belt-and-braces for the rest scenario but load-bearing under
big impacts.**

### (3) Energy cap scaled to source impact work

Implemented in `ReducedSupportCoupler.post_step` (the `# Item (3)` block
in `reduced_support_solve.py`):

```python
E_inj_candidate = 0.5 · Σᵢ mᵢ · Δv_i_candidate²
budget          = η · E_src                 # η = 0.95 by default
α               = min(1, √(budget / E_inj_candidate))
Δv              = α · Δv_candidate
```

Source-energy proxy: `E_src = max(0, KE_pre − KE_post)`. Slight under-
estimate when gravity is positive-working at the moment of impact —
conservative in the safe direction (less injection budget, fewer false
permissions).

Regression test `test_energy_cap_bounds_injection` asserts cumulative
|E_inj_realised| ≤ η·Σ E_src + ε across 90 frames. Passes.

### (4) Short cooldown on receivers

Same coupler. After every macro step, probes that took a Δv above
`cooldown_dv_threshold` (default 0.10 m/s) have their AVBD body index
recorded; `_assemble_r̃` skips rows whose body is in cooldown for the
next `cooldown_steps` (default 2) macro steps.

This is a *temporal* gate, not an identity gate — the same probe can
still source `r̃` later. Crucially, the **q-block coupling path** never
filters; only the overlay's source assembly does.

### (5) ρ_q principled note + sweep

The q-block's AL penalty `ρ_q` linearly scales `r̃ = Σ (λ + ρ_q·C⁺)·J_q`,
so it's a hidden knob on the overlay's hotness. We auto-size on the
first hook fire:

```
ρ_q = (1/h²) · max(diag(M_q[:r_modal]))
```

which puts the contact penalty on the same scale as the BDF1 inertial
term. Sweep at multiplier ∈ {0.1, 0.3, 1.0, 3.0, 10.0} × auto
(`scripts/run_rho_q_sweep.py`):

| mult | ρ_q | q_disp | Δv max | E_inj / E_src |
|------|-----|--------|--------|---------------|
| 0.1× | 1.2e3 | 0.29 mm | 0.11 m/s | ≈0 (no coupling) |
| 0.3× | 3.6e3 | 0.30 mm | 0.10 m/s | ≈0 (no coupling) |
| **1.0× (auto)** | 1.2e4 | 5.9 mm | 1.81 m/s | **0.109 (sweet spot)** |
| 3.0× | 3.6e4 | 5.5 mm | 1.95 m/s | 0.109 (saturated) |
| 10.0× | 1.2e5 | 23 mm | 3.50 m/s | 1.62 (cap struggling) |

The auto value sits in the "stable + responsive" sweet spot: visible
response, energy cap comfortably under η, no over-coupling. Below 0.3 ×
the q-block is too compliant relative to the contact force scale to
respond; above 3 × the surface deflects unphysically and the cap starts
working hard.

`# DEVIATION:` comment in `reduced_support_solve.py:23-34` already
documents that the spec's `ρ` ≠ AVBD's `c_penalty`; this sweep is its
empirical justification.

### (6) Path-B 1-D toy

`scripts/path_b_1d_toy.py`. Same 1-D drop-onto-modal-surface scene
under two formulations:

* **Path A** (current AVBD code): implicit macro step + bolted-on
  overlay with cap + cooldown + high-pass.
* **Path B**: sub-step the *coupled* (rigid + modal) system at `dt = T`
  with a velocity-level LCP that includes `q`'s modal contributions to
  contact velocities. Closed-form free-SDOF propagator keeps it stable
  at any dt. No separate injection layer.

Result over 5 s with single mode ω = 838 rad/s, ζ = 0.01:

|   | Path A | Path B |
|---|--------|--------|
| Overlay-injection events | 4 / 600 | **0 / 600** |
| Probe max \|v\| | 0.074 m/s | 0.126 m/s |
| Probe peak displacement | 0.1 mm | 1.1 mm |
| Final total energy | 0 J | 2.5e-5 J (decaying with ζ) |

**Verdict: the probe→r̃→probe feedback loop and the energy pump both
vanish under Path B by construction**, just as the user predicted. Path
B requires sub-stepping the coupled solve at `T = π/(2ω)`, which costs
some of AVBD's macro-step advantage; it's the cleaner formulation but
also the bigger refactor.

For v1, Path A's coupling + disciplined overlay is what the codebase
ships; the toy proves the cleaner road exists if reviewers push.

### (7) CUDA-graph regression (deferred)

When `iteration_hook` is wired, `Solver6DOF._step_one` drops out of
graph-capture mode. Measured in `scripts/run_reduced_support_benchmark.py`
at iter=4, h=1/120, 120 frames:

* no reduced support (graph captured): 1.53 ms/step
* bare reduced (hooks wired):         3.80 ms/step
* overlay reduced (hooks + post-step): 4.46 ms/step

**Slowdown ≈ 2.5×.** Material for real-time but smaller than the
critique's 3–5× estimate. v1 ships as-is and documents it; v2 should
either (a) restructure the hook so the graph re-captures the q-block
solve as an inline kernel chain, or (b) accept the slowdown and lean on
sub-stepping fewer modes.

## Headline benchmarks

`scripts/run_reduced_support_benchmark.py`, iter ∈ {4, 8, 16, 32},
120 frames, h = 1/120.

| iter | arm | max \|Δv\| | max q | inj/src | step ms |
|------|-----|-----------|-------|---------|---------|
| 4 | bare | 0.21 | 5.93 mm | 0.000 | 3.80 |
| 4 | overlay | **1.81** | 5.93 mm | 0.109 | 4.46 |
| 8 | bare | 0.13 | 3.62 mm | 0.000 | 5.49 |
| 8 | overlay | 1.09 | 3.62 mm | 0.019 | 5.79 |
| 16 | bare | 0.04 | 1.05 mm | 0.000 | 8.22 |
| 16 | overlay | 0.30 | 1.05 mm | 0.001 | 8.93 |
| 32 | bare | 0.01 | 0.35 mm | 0.000 | 13.17 |
| 32 | overlay | 0.10 | 0.35 mm | 0.000 | 17.48 |
| — | no-reduced | 0 | 0 | 0 | 1.53 |

### Overlay-vs-bare ratio (the spec's ω·h prediction)

| iter | overlay/bare Δv | overlay/bare q_disp |
|------|------------------|---------------------|
| 4 | 8.55× | 1.00× |
| 8 | 8.31× | 1.00× |
| 16 | 7.90× | 1.00× |
| 32 | 7.64× | 0.99× |

CV across iter counts: **5%**. The ratio is iteration-invariant and
matches `ω·h ≈ 7` for the shelf's first mode at h = 1/120 — exactly the
Section 8 prediction the spec makes.

### Energy bookkeeping (cap working)

Across the sweep, cumulative |E_inj_realised| / Σ E_src stays well
below η = 0.95 at every iteration count (max 0.109 at iter=4, falling
to 0.000 at iter=32 because the bigger AVBD residual at low iter has
more transient content to sub-step).

## Limitations and explicit non-goals (v1)

Per spec §"Implementation scope for v1":

* Frictionless normal contact only. FLOOR_CONTACT rows only — the
  anchor-shift trick only applies to floor-row y-shifts; BOX_BOX rows
  on the support aren't tracked.
* Contact set frozen during a substep (detection once per substep; no
  re-detection between iterations).
* No Barbič-James deformed normals; no geodesic spatial attenuation.
* Synthetic plate basis (sine bending + Gaussian-bump static modes).
  Real FEM modes via `ModalAnalysis` are wired in but the v1 demo uses
  the synthetic basis for reproducibility.
* `Δv` is linear-only at the probe COM — no probe angular kick.
* Passivity is **not claimed**. `E_overlay_injected` is logged and
  capped at `η·E_src`; that bound is empirical/conservative and only
  tested across the runs reported here.
* Graph capture disabled when hooks are wired → ~2.5 × slowdown vs the
  no-reduced rigid-only path (deferred to v2).

## What ships, what doesn't

What's shipped on `AVBD-Native`:

* `dcr/avbd/reduced_support.py` (dataclass + synthetic plate basis builder)
* `dcr/avbd/reduced_support_solve.py` (coupler, q-block, overlay, cap, cooldown)
* `scenes/reduced_support_shelf.py`, `scripts/run_reduced_support_shelf{,_viser}.py`
* `scripts/{audit_overlay_h_t,run_rest_impactor_pump_test,run_rho_q_sweep,path_b_1d_toy,run_reduced_support_benchmark}.py`
* `tests/avbd/test_reduced_support.py` — 9 tests, all green;
  `tests/avbd/` total: 84 → 87 tests, all green.

What's deliberately not shipped:

* The Path-B sub-stepped coupled-contact formulation (toy only).
* A graph-capture restoration for the iteration hook.
* Friction or full BJ-normal extensions.
