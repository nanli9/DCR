# The Native Dynamic Constraint on the Velocity-Impulse Solver

**Branch:** `impulse-native-constraint` · **Backend:** `dcr/avbd/_solver/solver_impulse.py` (`make_solver("impulse")`)

## What this is

The two-way modal contact row of `docs/07_17_report/contact_forces.html` —
same formulation, same gap function — carried by the **main-branch
velocity-impulse solver** (paper Eq. 2/3: Schur-complement BLCP + Projected
Gauss-Seidel, `dcr/rigid/solver.py`) instead of AVBD or XPBD. The modal
amplitudes are extra DOFs exactly the way ABD adds affine DOFs:

```
1)  p = x + R (r + Φ·a)                          # deformed contact point
2)  0 ≤ C_rigid + Ĝ_A·a_A − Ĝ_B·a_B  ⊥  λ ≥ 0    # one shared unilateral row
3)  rigid: ±Jᵀλ    modes: +Ĝ_Aᵀλ, −Ĝ_Bᵀλ         # same λ routed to every DOF
```

At the velocity level the row gains modal **columns** and the Schur complement
(paper Eq. 2) gains the modal block:

```
A = (1/h²)·cfm·I + J M⁻¹ Jᵀ + Ĝ W_eff Ĝᵀ         # extended Delassus
b = −(erp/h)·φ − (J·v_free + Ĝ·ȧ_free)           # φ = deformed-surface gap
W_eff = (M_q + h·D_q + h²·K_q)⁻¹                 # implicit-SDOF impulse response
```

solved by the **same PGS with λ_N ≥ 0** (paper Eq. 3, boxed friction), the
solved impulse distributed `Δv = M⁻¹Jᵀλ` (rigid) and `Δȧ = W_eff Ĝᵀλ` (modes).
`W_eff` is why stiff modes cannot destabilize the co-solve: for `h²ω² ≫ 1` the
mode simply refuses impulse — the same effective mass the AVBD q-block
assembles as `H_q·h²`.

Rules carried over from the production backends: friction rows are rigid-only
(modal columns live on the normal row exclusively); the slab's `Ĝ` degenerates
to the sampled `U_y` (`∂C/∂q = −U_y`); cargo `Ĝ_a = n̂ᵀ·R·Φ_c[pid]` frozen per
substep with nearest-rest-corner snap; the §15 passivity ledger
(`passivity.py`) is shared verbatim and applied globally across support + all
cargo blocks.

## Box-box semantics: one measured deviation

Support (slab) rows carry the **full native columns** — gap, velocity map, and
Delassus. That is the report's two-way headline (pre-sag, detune, damping) and
it is stable and exact here (see the statics below).

Box-box rows default to the **shipped AVBD semantics** (`_modal_contact_ride`
off): the row solves rigid-only and the shared λ drives both cubes' modes
open-loop (`+Ĝ_Aᵀλ / −Ĝ_Bᵀλ`). The full monolithic box-box row is available as
`_modal_contact_ride = True`, opt-in, because it is measurably unstable on
off-center stacks: the λ ≥ 0 clamp rectifies the ringing-surface velocity
oscillation (±Ĝ·ȧ ≈ ±1.6 cm/s on the §N2 demo cubes) into net torque — the
§N2 zig-zag tower ratchets ω_z (+0.1 → +0.34 rad/s over 0.3 s, independent of
PGS iteration count) and topples at ~1 s. This is the same instability the
repo has already documented twice: the Route-A coupler-era "stacks ride the
modal ring — ledge pillars rock", and AVBD's `_bake_ride_crest` shipping the
ride engagement-gated + capped (N3). The deviation is marked `# DEVIATION` at
the row-assembly site.

## Evidence (2026-07-17, `tests/avbd_native/test_solver_impulse.py`, 6 passed)

* **Floor statics** — settled box: Σλ_N/h = 5.8860 N = m·g exactly, |v| ~1e-16.
* **Analytic support sag** — one uniform mode: q = −1.490953e-3 vs analytic
  −1.490941e-3 (K·q = −m·g); body rides y_rest + U_y·q; multipliers = m·g.
* **Stack statics ledger** (report "the static ledger is exact") — §N2 scene,
  settled multipliers per joint: resting→slab = m·g, base→slab = 3·m·g,
  base↔mid = 2·m·g, mid↔upper = m·g, each within 3%, stack standing.
* **Two-way causality** (report "it is genuinely two-way") — peak |a_upper|
  = 1.2e-4 network ON, **identically zero** OFF; upper touches only mid, two
  box-box hops from the slab.
* **§15 passivity** — ledger `passive()` and `holds()` across the full 3 s
  run (1440 substeps), globally across the network. Also holds on all four
  production scenes (truck/ledge/shelf/dinner, all-cargo, FEM eigenbasis).
* **Payload mass-loading A/B** — two-way plate pre-sags ≈ −12 mm under the
  payload before impact; one-way plate stays flat (< 20% of that); the
  uncoupled payload still rides the readout ring (~7 mm post-impact span) via
  the impulse-native one-way hook in `scenes/payload_plate.py`.

## Run it

```bash
.venv/bin/python scripts/run_native_scenes_viser.py --scene cargo   --solver impulse
.venv/bin/python scripts/run_native_scenes_viser.py --scene payload --solver impulse
.venv/bin/python scripts/run_native_scenes_viser.py --scene dinner  --solver impulse
.venv/bin/python -m pytest tests/avbd_native/test_solver_impulse.py -v
```

All six viser scenes run on the backend (cargo, payload, truck, ledge, shelf,
dinner — all-cargo included). CPU/numpy only by design (reference formulation
study, CLAUDE.md rule 6); `abd` cargo routes to AVBD (nonlinear V⊥ not
implemented here); the sound demo stays AVBD-only.
