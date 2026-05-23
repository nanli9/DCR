# DCR Distant Velocity Modes — Energy-Prescribed Follow-up

> **Paper-level claim (use this framing, do not drift):**
> "Replace a timestep-sensitive kinematic velocity prescription with a
> passive energy-prescribed distant response, improving timestep robustness
> of artist-facing controls while preserving passivity."
>
> NOT "Δv independent of h." Residual h-dependence through `E_available`
> is expected and acceptable; the goal is *reduced sensitivity*, not
> invariance.

## Why

The DCR paper (Coevoet et al. 2020, CGF 39(8)) prescribes the distant
separation velocity as

```
Δv = d_max / h                                                       (Eq. 12)
```

The artist tunes `d_max` — a *length* — and the simulator divides by the
timestep. At a fixed `h` this is fine, but the same `d_max` at different
`h` injects very different kinetic energy into the resting body, which
breaks artist-facing controls under timestep changes. The paper itself
flags this in §5.4. This follow-up adds two alternative modes that
prescribe the kick magnitude from an *energy budget* (so the artist's
knob has dimensionless meaning) while preserving the existing kick
direction and passivity cap.

## Modes

The mode is selected on the coupler via `PassiveDCRCoupler.dcr_velocity_mode`
(see `dcr/dcr/passive_dcr.py`). The hard rigid-energy bound is independently
toggled by `DCRWorld.enforce_rigid_energy_bound`.

| Mode (`dcr_velocity_mode`)          | Bound flag | Kick direction       | Kick mechanism                          |
|-------------------------------------|------------|----------------------|------------------------------------------|
| `coevoet`                           | (any)      | contact normal       | linear COM (existing `_apply_dcr_velocities`) |
| `coevoet` + `enforce_rigid_energy_bound=True` (≡ `bounded_coevoet`) | on | contact normal | linear COM, scaled to satisfy rigid-loss bound |
| `energy_prescribed` (Version A)     | recommended on | contact normal | linear COM                            |
| `energy_prescribed_point_impulse` (Version B) | recommended on | deformed contact normal n′ | TRUE point impulse (linear + angular)  |

## Math

Let `E_available` be a per-step energy budget (see "Budget source"). The
artist control is

```
β = energy_response_beta ∈ [0, 1]      # dimensionless
E_target = β · max(E_available, 0)
```

### Version A — linear-only

```
k = 1 / m                              # ignores angular response
dv = √(2 k · E_target) = √(2 E_target / m)
body.velocity[0:3] += dv · push_dir
```

Realized ΔKE = ½ m dv² = `E_target` exactly.

**`# DEVIATION` (foundation §15, paper §5.4):** the task spec proposed
`k = 1/m + (r×u)·I_inv·(r×u)`. We drop the angular term for Version A
because `_apply_dcr_velocities` only updates `body.velocity[:3]` — the
angular term would represent energy not actually injected, causing
realized ΔKE to *exceed* E_target. Version B uses the full formula AND
the angular kick, restoring physical consistency.

### Version B — true point impulse, deformed contact normal

```
u = compute_deformed_normal(contact, q_history, modal)     # n′ from modal disp
r = contact_point - body.position                           # lever arm
k = 1/m + (r × u) · I_world_inv · (r × u)                   # inverse eff. mass at contact
J = √(2 E_target / k)                                       # impulse magnitude
body.velocity[0:3] += (J / m) · u
body.velocity[3:6] += J · I_world_inv @ cross(r, u)
```

Realized ΔKE = ½ m ‖Δv_lin‖² + ½ Δω · I · Δω = ½ J² k = `E_target` exactly
(see `tests/stageDV/test_point_impulse_math.py:test_realized_dKE_matches_E_target_from_rest`).

The deformed normal `n′` is the same primitive the tilt coupler uses
(extracted into `dcr/dcr/deformed_normal.py` so both Version B and
`TiltDCRCoupler` share it). It is a *numerical heuristic*, not a derived
quantity — see the `# DEVIATION` note in that module.

### Passivity cap (post-proposal)

Both versions optionally run through a hard rigid-energy bound:

```
ΔE_total(s) = s · A + s² · B    ≤    0.999 · ΔE_loss
```

(Vector form per foundation §15 / this follow-up; see
`dcr/dcr/dcr_world.py:_bound_dcr_velocities` for scalar-dv and
`_bound_point_impulse_dcr_velocities` for linear + angular point impulses.)

The cap is OFF by default (`enforce_rigid_energy_bound=False`) to preserve
bit-for-bit the pre-follow-up "coevoet" behavior. For the two new modes,
the cap is **recommended** on.

## Config field reference

```python
@dataclass
class PassiveDCRCoupler:
    # ... existing fields ...
    dcr_velocity_mode: str = "coevoet"
    energy_response_beta: float = 0.25
    energy_budget_source: str = "min_rigid_loss_modal"
    theta_max_deformed: float = float(np.radians(3.0))

@dataclass
class DCRWorld:
    # ... existing fields ...
    enforce_rigid_energy_bound: bool = False
```

### Budget source (`energy_budget_source`)

| Value                       | E_available                                         |
|-----------------------------|-----------------------------------------------------|
| `rigid_loss`                | `η · world.last_E_loss`                             |
| `modal_reservoir`           | `modal_energy(q, qdot, ω)`                          |
| `min_rigid_loss_modal` (default) | `min(η · world.last_E_loss, modal_energy(q, qdot, ω))` |

Both quantities exist in this codebase already (foundation §1 and §2);
no fallback was needed.

## How to reproduce the h-sweep benchmark

```bash
uv run python -m benchmarks.run_h_sweep \
    --modes coevoet,bounded_coevoet,energy_prescribed,energy_prescribed_point_impulse \
    --h-values 1e-3,2.5e-3,5e-3,1e-2 \
    --sim-time 1.5 \
    --beta 0.25 \
    --budget-source min_rigid_loss_modal \
    --out benchmarks/output/h_sweep.csv
```

The script writes one CSV row per `(mode, h, step)` plus a `#`-prefixed
footer with the CoV summary table.

## Latest CoV results (1.5 s sim, β=0.25, two-ball staggered scene)

Metric: mean realized ΔKE per kicked body (Joules), per (mode, h) cell.
CoV = std/mean across h ∈ {1e-3, 2.5e-3, 5e-3, 1e-2}.

| Mode                                  | CoV    | Reduction vs coevoet |
|---------------------------------------|--------|----------------------|
| `coevoet`                             | 0.88   | —                    |
| `bounded_coevoet`                     | 0.88   | 0% (cap doesn't bind in this scene) |
| `energy_prescribed` (A)               | 0.30   | **−66%**             |
| `energy_prescribed_point_impulse` (B) | 0.49   | **−44%**             |

Per-cell mean ΔKE (Joules):
- `coevoet`        : [0.00325, 0.01161, 0.00250, 0.00121]
- `energy_prescribed`        (A) : [0.2674, 0.4417, 0.2574, 0.2118]
- `energy_prescribed_point_impulse` (B) : [0.0200, 0.0210, 0.0420, 0.0639]

Version A's only h-sensitivity is through `E_available(h)`, which is mild
for this scene. Version B adds two further sources of h-dependence on top
of `E_available(h)`: (1) the deformed normal `u(q_history)` varies with
the modal-substep count (= `ceil(h/T)`), and (2) angular kicks make
trajectories diverge between modes. Both are real algorithmic properties.

## Test summary

```bash
uv run pytest tests/stageDV -v
```

| File | Count | Coverage |
|---|---:|---|
| `tests/stageDV/test_point_impulse_math.py` | 11 | Analytical algebra: inverse-effective-mass formulas, exact `½ J² k = E_target` to 1e-12 |
| `tests/stageDV/test_dcr_velocity_modes.py` | 13 | Integration: β=0 → no kick; modal-reservoir=0 → no kick; post-cap energy ≤ budget; cap rarely binds at β=0.25; CoV reduction across h; diagnostics populated; mode-string validation |

## Explicit non-claims (binding per foundation §14)

- **Not invariance** — `Δv` is NOT independent of `h`. Residual
  h-dependence through `E_available(h)` is expected and acceptable.
- **Version B does NOT subsume the existing tilt coupler.** Version B is
  a parallel, cleaner point-impulse alternative for the energy-prescribed
  mode only. `TiltDCRCoupler`'s observable behavior is unchanged.
- **Version A and Version B have different h-stability characteristics.**
  Version A is more h-stable; Version B is more physically faithful
  (linear AND angular response correctly accounted). Pick by use case.
- **No claim of audio synthesis or sound bound** — see CLAUDE.md and
  `passive_modal_energy_injection_foundation.md` §14.
