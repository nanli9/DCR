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
# logged comparison + 4-panel figure
uv run python scripts/run_solver_comparison_benchmark.py --scene side_by_side --kind fem
uv run python scripts/run_solver_comparison_benchmark.py --scene settle --kind abd --no-xpbd

# lockstep 3-up viser (GT grey / AVBD orange / XPBD green)
uv run python scripts/run_solver_comparison_viser.py        # http://localhost:8198

# acceptance tests (settle+passive, GT parity, two-way kick, AL non-penetration)
uv run python -m pytest tests/twobody/test_position_based.py -q
```

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
