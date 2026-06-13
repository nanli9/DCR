# Approach B — the dynamic modal contact constraint in AVBD and XPBD

> Branch `twobody-avbd-dynamic-constraint`. Implements `two_band_coupling.html`
> ("Modal Contact as a Dynamic Two-Way Constraint") and validates it against the
> monolithic ground truth on this branch.

## What this is

The earlier coupler **split** the support's deformation: the static sag `q_s`
went into the contact constraint, while the fast ring `q_d` was evolved by a
separate IIR resonator and injected one-way as an energy-governed velocity band.
That seam is exactly why energy only flowed rigid → support.

**Approach B drops the split.** It carries the support's *full dynamic* modal
state `q` (its own inertia `M_q`, stiffness `K_q`, damping `D_q`) **inside the
same contact solve** as the bodies. One implicit-Euler step minimizes a single
incremental potential over the stacked rigid + modal coordinates `z`:

```
E(z) = Σ_b 1/(2h²)‖z_b − z̃_b‖²_M_b   (inertia; gravity in z̃, modal M_q/h² in the stacked mass)
     + Σ_b V_b(z_b)                    (internal elastic, incl. ½ qᵀK_q q)
     + Σ_c Φ_contact( gap_c(z) )        (contact — sees the FULL dynamic q)
```

The two-way loop is then **structural**: one contact multiplier lifts a body and
is the very reaction that loads the mode; because `q` has inertia, the mode
springs back and pushes the body. Backward Euler on this bounded-below potential
is unconditionally dissipative, so the run is **passive for free** — no `η` /
reservoir governor, no velocity band, no high-pass/cooldown.

## Three solvers of the same potential

| solver | file | contact | iteration | cubes |
|---|---|---|---|---|
| **GT** (ground truth) | `dcr/twobody/multibody.py` | raw penalty | dense Newton → convergence | ABD, FEM |
| **AVBD** | `dcr/twobody/position_based.py` | augmented Lagrangian (λ+ρ) | fixed budget (6 outer × 3 inner) | ABD, FEM |
| **XPBD** | `dcr/twobody/position_based.py` | compliant (α=1/k_c) | Gauss–Seidel (25 iters) | FEM |

GT is the in-solver ground truth (`two_band_coupling.html` honesty card). AVBD
and XPBD are the **real-time position-based solvers** the project targets; both
realize the *same* dynamic-constraint potential. For XPBD the modal stiffness
`K_q` is expressed exactly as diagonal compliant constraints (one per mode), with
the modal Rayleigh damping applied through Macklin's damped compliant-constraint
update so the modes ring down. AVBD uses a dense-Newton primal in this reference
(the device-resident Schur-block realization lives in
`dcr/avbd/reduced_coupled_avbd.py`).

`AVBDDynamicSystem` / `XPBDDynamicSystem` compose over a `MultiBodySystem`, so
they share its DOF layout, mass/damping/gravity, contact geometry, per-body
energy logging and the basin-free `static_residual` — only `step()` differs.

## Results (`scripts/run_solver_comparison_benchmark.py`)

**Side-by-side, FEM cubes** (impactor dropped on the slab between 3 resting cubes,
h=5e-4, 3000 steps):

| solver | modal peak | cube peak | max ΔE | ‖v‖ end | max penetration | ‖z_end − z_end(GT)‖ |
|---|---|---|---|---|---|---|
| GT   | 3.54 J | 6.73 J | −1.9e-9 | 7.5e-4 | 1.503 mm | — |
| AVBD | 2.56 J | 6.73 J | +4.6e-9 | 8.3e-4 | **0.207 mm** | 1.9e-5 |
| XPBD | 3.61 J | 6.73 J | −3.4e-9 | 1.1e-3 | 1.505 mm | 7.9e-7 |

- **Same rest state** as the GT (‖Δz‖ ≤ 2e-5) — all three settle to the static sag.
- **Two-way loop** in all three: the slab modal energy spikes at impact then rings
  down, and the ring kicks the resting bystander cube **>1300×** its pre-impact
  KE — slab → cube momentum with no velocity band.
- **Passive**: total energy monotone to round-off (max ΔE ~ 1e-9).
- **AVBD's augmented Lagrangian** holds the load with the multiplier, driving
  penetration to 0.2 mm vs the penalty solvers' 1.5 mm.

Figure: `docs/figures/solver_cmp_side_by_side_fem.png`. CSV time series per solver
under `docs/data/solver_cmp_*.csv`.

ABD settle (`--scene settle --kind abd`): AVBD matches the GT rest to 1.3e-5 with
0.005 mm penetration (vs GT 0.157 mm), energy monotone.

## Run it

```bash
# logged comparison + 4-panel figure (scenes: side_by_side, settle, stack)
uv run python scripts/run_solver_comparison_benchmark.py --scene side_by_side --kind fem
uv run python scripts/run_solver_comparison_benchmark.py --scene stack --kind abd --no-xpbd

# one-way SPLIT vs two-way DYNAMIC overlay (the PI's question)
uv run python scripts/run_split_vs_dynamic_overlay.py --scene side_by_side --with-gt
uv run python scripts/run_split_vs_dynamic_overlay.py --scene stack --kind fem

# lockstep 3-up viser (GT grey / AVBD orange / XPBD green)
uv run python scripts/run_solver_comparison_viser.py        # http://localhost:8198

# acceptance tests (settle+passive, GT parity, two-way kick, AL non-penetration)
uv run python -m pytest tests/twobody/test_position_based.py -q
```

## One-way split vs two-way dynamic — the PI's question

`scripts/run_split_vs_dynamic_overlay.py` runs the SAME scene through the old
**split** (`SplitOneWaySystem` — slab modal `q` held quasi-static, the production
coupler's documented `H_q = K_q`, `q̇=0`) and the **dynamic constraint**
(`AVBDDynamicSystem`), and overlays the tell-tales.

**The rigorous two-way signature is the slab's modal kinetic energy** (figure
`docs/figures/split_vs_dynamic_side_by_side_fem.png`):

| quantity (side-by-side, FEM) | SPLIT (1-way) | DYN (2-way) | GT |
|---|---|---|---|
| slab modal KE peak | **0.000 J** (structural) | 1.52 J | 1.79 J |
| bystander cube KE peak | 0.030 J | 0.091 J | 0.151 J |
| settling time (rigid KE → 0) | ~2 s | ~0.4 s | ~0.4 s |

- **Slab modal KE ≡ 0 in the split** — a quasi-static slab stores no kinetic
  energy, so it *cannot ring*. In the dynamic constraint it rings to ~1.5 J and
  decays as it feeds energy back. That nonzero modal KE *is* the two-way loop.
- The split's slab is a **lossless quasi-static spring**: it absorbs none of the
  impact (no modal inertia to ring, no `q̇` for `D_q` to damp), so the impactor
  bounces for ~2 s. The dynamic slab rings *and* damps, settling in ~0.4 s.
- The distant bystander gets a **3–5× stronger, resonant** kick in the dynamic
  case; the split only transmits weak, repeated *quasi-static* nudges (the global
  sag), never a kinetic ring.

Honest nuance for the PI: the split is *not literally* zero-transmission — its
global static sag does move a bystander a little — but it carries **no kinetic
energy** and produces **no resonant ring or impact absorption**. The dynamic
constraint restores all three. The stack scene (`--scene stack`) shows the same
slab-modal-KE 0-vs-ringing split.

## Heavy box dropped BESIDE a stack (`build_stack_impact`)

A resting tower of `n_stack` cubes on the slab + a **heavy box dropped fast onto
bare slab next to the tower** (box↔slab contact only — it does *not* touch the
stack; cube↔cube + cube0↔slab hold the tower). The box rings the slab and **the
ring kicks the tower** — the two-way dynamic constraint carries the slab's ring
back into the resting stack, so the tower jolts. The box starts beside the tower
at `impactor_drop` (≈ stack-top height) with a downward initial velocity
(`MultiBodySystem.v0`, respected by every solver), at `impactor_rho/material_rho`×
the tower density. Default 6000 kg/m³ × 5 m/s ≈ **75 J** — stable at `k_c=1e6`,
`h=5e-4` with 0.09 mm penetration.

`scripts/run_stack_impact_benchmark.py --solvers` logs per-body KE and plots the
reaction (`docs/figures/stack_impact_{reaction,solvers}_fem.png`):

| solver | slab modal KE peak | stack kicked | max ΔE | max pen |
|---|---|---|---|---|
| AVBD | 24.0 J | **839×** (quiet→3.6 J) | −2.8e-6 | 0.09 mm |
| GT | 26.0 J | yes | −5e-6 | 2.51 mm |
| XPBD | 27.5 J | yes | −1e-5 | 2.50 mm |
| **SPLIT (1-way)** | **0.000 J** | **barely** | −7e-5 | 2.69 mm |

The box lands on the slab beside the tower (box KE → 0), the **slab rings** (24–27 J),
and the ring **kicks the resting stack ~840×** its pre-impact KE — the *top* cube
reacts most (the tower amplifies the base motion). Under the **split** the
quasi-static slab cannot ring (slab modal KE ≡ 0), so the tower is barely
disturbed — the one-way path can't transmit the impact through the support.

Live viewer (watch the box land beside the tower and the ring kick it):
```bash
uv run python scripts/run_stack_impact_viser.py                              # AVBD: tower gets kicked
uv run python scripts/run_stack_impact_viser.py --solver split               # one-way: tower barely reacts
uv run python scripts/run_stack_impact_viser.py --kind abd --impactor-rho 8000 --impactor-v0 8
```

## Truck-bed road impact — the busy multi-pile scene (`build_truck_bed`)

`scenes/reduced_truck.py`'s road layout brought into the `MultiBodySystem`
framework so AVBD/XPBD are exercised on a **busy, multi-pile** scene. A flexible
**bed slab** (1.6 m × 0.8 m, 20 modes, clamped short ends) carries a mixed cargo
load — a light crate, a **3-cube lumber stack**, a heavy crate, and a 2-crate
stack — and a **heavy box (≈108 J) is dropped on bare bed** between them. The box
rings the bed and the ring **rocks every distant cargo pile** (`docs/figures/
truck_bed_{reaction,solvers}_fem.png`):

| solver (fem, 2000 steps, h=5e-4) | bed modal KE peak | cargo KE peak | max ΔE | max pen | settles |
|---|---|---|---|---|---|
| **AVBD** | 41.1 J | 3.31 J | **−1.6e-5** | **0.18 mm** | ‖v‖=0.14 |
| **XPBD** | 45.4 J | 3.73 J | −2.6e-4 | 3.34 mm | ‖v‖=0.26 |
| GT | 43.4 J | 3.27 J | −5.4e-5 | 3.34 mm | ‖v‖=0.34 |
| **SPLIT (1-way)** | **0.000 J** | 1.43 J | −7.2e-5 | 1.04 mm | **‖v‖=3.24 ✗** |

- Both real-time solvers (AVBD, XPBD) **agree with the GT** on the bed ring and
  the cargo rocking; AVBD's augmented Lagrangian holds the load to **0.18 mm**
  penetration vs the penalty solvers' 3.3 mm.
- The cargo reaction is **staggered**: the nearest piles rock first, then the wave
  reaches the far ones (`truck_bed_reaction_fem.png`, right panel). The tall
  lumber stack reacts most (it amplifies the bed motion).
- **SPLIT cannot ring the bed** (modal KE ≡ 0), so the cargo gets only **~½** the
  kick (1.4 J vs 3.3–3.7 J) and the run **never settles** (the lossless
  quasi-static bed absorbs nothing, so the box keeps bouncing: ‖v‖end = 3.2).

```bash
uv run python scripts/run_truck_bed_benchmark.py --solvers      # AVBD/XPBD/GT/SPLIT
uv run python scripts/run_truck_bed_benchmark.py --impactor-rho 9000 --impactor-v0 8
```

## Energy-consistent passivity certificate (`run_passivity_certificate.py`)

The advisor's third ask: *account contact energy with each solver's own model so
each carries a clean per-step bound.* The certificate logs, per solver, the total
mechanical energy with its **native** contact potential and certifies passivity
(**PASS iff** `max_n (E[n+1]−E[n]) ≤ ε_tol` over the whole run):

| native contact model | stored Φ_contact |
|---|---|
| penalty GT / SPLIT | ½·k_c·Σ max(0,−gap)² |
| XPBD (compliant, α=1/k_c) | ½·k_c·Σ max(0,−gap)²  (same elastic energy) |
| AVBD (augmented Lagrangian) | ½·ρ₀·Σ max(0,−gap)² — the multiplier λ enforcing gap≈0 is a **workless** constraint reaction, so only the residual penalty is *stored* |

All reduce to the same form (ρ₀=k_c), so `energy_breakdown.total` is the native
certificate energy for every solver — what differs is **how much each stores**.
On the truck scene (fem, 2000 steps, ε_tol = 1e-4 J):

| solver | certificate | dissipated | max per-step ΔE | contact-stored E peak |
|---|---|---|---|---|
| **AVBD** | **PASS ✓** (0 violations) | 123.3 J | **−1.6e-5 J** | **0.028 J** |
| **XPBD** | **PASS ✓** (0 violations) | 123.2 J | −2.6e-4 J | 18.1 J |
| GT | **PASS ✓** (0 violations) | 123.3 J | −5.4e-5 J | 18.2 J |
| SPLIT | PASS ✓ (passive but non-settling) | 20.2 J | −7.2e-5 J | 1.74 J |

- **Every solver is strictly passive**: the *largest* per-step energy change is
  itself negative — total energy is monotone non-increasing, no governor, no
  reservoir. Passivity is structural (backward Euler on a bounded-below potential).
- **AVBD has the cleanest bound**: its AL multiplier drives gap→0, so it stores
  **~650× less** spurious penetration energy (0.028 J) than the penalty solvers
  (18 J). The penalty/compliant solvers carry a real ½k_c·gap² residual.
- **SPLIT is passive but pathological**: it dissipates only 20 J of the 123 J it
  must absorb — the quasi-static bed cannot ring or damp, so the energy stays in
  the perpetually-bouncing box (it does not settle).

(Total energy dips slightly negative late in the run — that is only the
gravitational datum `PE_grav = −f_grav·z` as the cargo settles below `z=0`; the
constant offset does not affect the monotonicity certificate.)

```bash
uv run python scripts/run_passivity_certificate.py --scene truck
uv run python scripts/run_passivity_certificate.py --scene side_by_side
```

## Penetration fix (side-by-side scene)

The impactor previously defaulted to `x=0`, exactly the centre resting cube's `x`.
Since `build_side_by_side` has **only cube→slab contacts** (no cube↔cube), the
impactor fell straight *through* that cube. Fixed: `impactor_x=None` now drops it
into the gap between the two centre cubes (½·spacing) so it lands on bare slab,
and an impactor placed within a cube's x-span now raises `ValueError`.

## Scope / honesty

- **Numerical damping.** Backward Euler removes energy even at `D_q = 0`; the ring
  decay is physical damping *plus* integrator damping, not separately tunable.
  A controlled modal Q needs BDF2/implicit-midpoint or finer substeps.
- **AL vs penalty equilibrium.** AVBD enforces `gap ≈ 0` (better non-penetration);
  the penalty GT/XPBD leave a small residual penetration. Rest *positions* still
  agree to ≤2e-5. AVBD's penalty-based `static_residual` reads high precisely
  because the load is carried by λ, not penetration — that is correct, not a bug.
- **ABD in XPBD** is left unwired (ABD's 6 nonlinear orthogonality constraints
  project fine via `elastic_constraints`, but its mass-proportional damping is not
  routed through the per-constraint XPBD damp term). The AVBD path covers ABD.
- **Novelty.** The physics is classical flexible-multibody coupling (floating-frame
  + component-mode-synthesis; equivalently the ABD/IPC family, but *modal* rather
  than affine reduction). What is unestablished is realizing it as compliant
  constraints inside a real-time position-based rigid solver (XPBD / AVBD). This
  module is that realization, validated against the monolithic ground truth.
```
