# Deformation-Aware Contact Frame Extension to DCR

> Extension of the Distant Collision Response method [Coevoet et al. 2020]
> to include lateral impulses derived from the local modal displacement gradient.

---

## 1. Motivation

### The limitation of standard DCR

The DCR method [Coevoet et al. 2020] augments a rigid body simulation with distant vibration response. When a heavy object impacts an elastic body (e.g., a table), the method propagates the impact through a precomputed modal basis and injects velocity kicks at distant resting contacts. This produces qualitatively plausible secondary effects -- plates rattle, objects jump.

However, DCR replaces the deformable contact surface with a **rigid proxy plane**. The contact normal at every resting point is always the original surface normal (e.g., straight up for a horizontal table). This means:

- DCR velocity kicks are always **purely normal** (vertical on a table).
- Objects on the surface get pushed up/down but never sideways.
- **Tall, thin objects** (books, dominos) cannot topple from DCR alone because toppling requires a lateral force component.

### What happens in reality

When a heavy object impacts a flexible surface, the surface **bends locally**. This bending tilts the surface normal at nearby points. An object resting on the tilted surface experiences a contact force with a lateral component. For a tall, thin object (high center of mass, narrow base), even a small lateral component can exceed the tipping threshold.

### The extension idea

Instead of injecting the DCR impulse along the original normal `n`, compute a **tilted normal** `n'` from the modal displacement gradient at the contact point, and redirect the DCR impulse along `n'`. The lateral component of this redirected impulse produces rocking motion that can topple unstable objects.

---

## 2. Mathematical Foundation

### 2.1 Standard DCR recap (Eqs. 9-13 from [Coevoet 2020])

Given an impact at surface point `x_c` with impulse `lambda`, the modal forcing is:

```
r = U_surf(x_c)^T * n * lambda_N                           (Eq. 9)
```

The IIR stepper produces modal displacement history `q^(k)` for `k = 1..K` substeps. At each resting contact point `x_i`, the maximum normal displacement is:

```
d_{max} = max_k |n^T * U_surf(x_i) * q^(k)|                (Eq. 11)
```

This is converted to a separation velocity:

```
Delta_v = d_{max} / h                                        (Eq. 12)
```

Applied as a velocity kick along the contact normal:

```
v_body += Delta_v * n                                        (Eq. 13)
```

**Key limitation**: Eq. 13 always uses the original normal `n`. No lateral component.

### 2.2 Tilted normal from modal displacement gradient

Treat the elastic surface locally as a height field. At a surface triangle with vertices `{v_0, v_1, v_2}`, original normal `n`, and tangent frame `{t_1, t_2}`, define the normal displacement at each vertex:

```
w_i = n^T * u(v_i) = n^T * U_surf(v_i) * q_{peak}
```

where `q_{peak} = q^(k*)` is the modal state at the substep `k*` of maximum displacement:

```
k* = argmax_k |n^T * U_surf(x_c) * q^(k)|
```

The tangential slopes are computed by fitting a plane through the three samples. In the tangent-frame parametric space:

```
p_k = (t_1 . (v_k - v_0),  t_2 . (v_k - v_0))     for k = 0, 1, 2
```

Solve the 2x2 system:

```
[p_{1,x}  p_{1,y}] [s_1]   [w_1 - w_0]
[p_{2,x}  p_{2,y}] [s_2] = [w_2 - w_0]
```

The tilted normal is:

```
n' = normalize(n - s_1 * t_1 - s_2 * t_2)
```

**Note:** For a linear (constant-strain) triangle, this patch fit is mathematically identical to the analytic gradient of the barycentric interpolation of mode shapes. The two approaches give the same result.

### 2.3 Lateral velocity from slope-derived tilt

The tilted normal `n'` determines the **lateral direction** only. It is **not** used to apply the full impulse along `n'` (i.e., we do NOT compute `v += Delta_v * n'`).

**Lateral direction:**

```
t = n' - (n' . n) * n             # tangential projection
t_dir = normalize(t)              # unit lateral direction
```

**Lateral magnitude:**

```
dv_t = lateral_fraction * |Delta_v|
```

The lateral velocity is a fixed fraction of the DCR separation velocity. The tilt angle determines only the *direction*, not the magnitude. This makes the response **scene-independent** — the same `lateral_fraction` works for soft shelves (E ~ 0.5 GPa, large tilt angles) and stiff ground (E ~ 10 GPa, tiny tilt angles) without per-scene parameter tuning.

**Capping:**

```
dv_t = min(dv_t, dv_t_max)                  # velocity cap
dv_t = min(dv_t, sqrt(eta_t) * |Delta_v|)   # energy cap
dv_t = min(dv_t, mu_dcr * |Delta_v|)        # Coulomb cap
```

The three caps prevent instability and ensure the lateral response remains bounded.

### 2.4 Application strategy

The lateral correction is applied as a **linear velocity change only**:

```
v_{lin} += dv_t * t_dir           # lateral component (both modes)
v_{lin} += dv_n * n               # normal component (tilt-coupled only)
```

where `dv_n = min(|Delta_v|, dv_n_max)` is a capped version of the standard DCR kick.

Angular velocity is NOT directly injected. Instead, the rocking/tipping response emerges naturally from the contact solver in subsequent steps:

1. The body's base receives a lateral velocity push.
2. In the next step, friction at the bottom contact constrains the base.
3. The body's top continues by inertia.
4. This produces natural tipping rotation via the contact constraints.

**Rationale:** Directly injecting angular velocity via `omega += I^{-1} (r x J_t)` causes unrealistic spinning for thin objects. A book with moment of inertia `I ~ 10^{-4} kg.m^2` would spin wildly from even a small lateral impulse. Letting the contact solver handle rotation is more physically consistent and visually natural.

---

## 3. Safety Bounds

Four bounds are enforced to prevent instability:

### Bound 1: Maximum tilt angle

```
theta = arccos(n . n')
if theta > theta_max:
    n' = slerp(n, n', theta_max / theta)
```

Default: `theta_max = 10 degrees`. Prevents unrealistic lateral directions from numerical noise in the modal slopes.

### Bound 2: Coulomb-like lateral cap

```
dv_t <= mu_DCR * |Delta_v|
```

Default: `mu_DCR = 0.5`. Ensures the lateral velocity remains a fraction of the DCR separation velocity, analogous to friction limiting tangential forces.

### Bound 3: Energy budget

```
dv_t <= sqrt(eta_t) * |Delta_v|
```

Equivalent to: `0.5 * m * dv_t^2 <= eta_t * E_DCR`, where `E_DCR = 0.5 * m * Delta_v^2`.

Default: `eta_t = 0.5`. The lateral kinetic energy cannot exceed a fraction of the DCR kick energy.

### Bound 4: Velocity cap

```
dv_t <= dv_t_max
```

Default: `dv_t_max = 1.5 m/s`. Absolute cap on the lateral velocity correction regardless of amplification or DCR magnitude.

---

## 4. Comparison with Standard DCR

| Aspect | Standard DCR | DCR + Tilt Extension |
|--------|-------------|---------------------|
| Contact normal | Fixed (original surface normal) | Unchanged (tilted normal used for lateral direction only) |
| Impulse direction | Always along `n` | `dv_n * n` (capped) + `dv_t * t_dir` (amplified, bounded) |
| Lateral response | None | Amplified lateral kick from surface slope |
| Angular response | None (vertical jumps only) | Emerges via contact solver from lateral kick |
| Tall thin objects | Jump vertically, stay upright | Rock and topple |
| Precomputation | Mode shapes at surface | Mode shapes + per-triangle tangent frames |
| Runtime cost | `O(K * n_contacts * n_modes)` | Same + `O(n_resting * n_modes)` per step |
| Contact geometry | Unchanged (rigid proxy) | Unchanged (rigid proxy) |
| Collision detection | Unchanged | Unchanged |
| Solver modification | None | None |

### What this extension does NOT do

- **Does NOT modify the contact solver's normals.** The LCP friction cone and non-penetration constraint always use the original `n`. The tilted `n'` is only used to redirect the DCR impulse post-solve.
- **Does NOT rebuild collision geometry.** Contact detection always uses the rigid proxy surface.
- **Does NOT run a full FEM contact solve.** The method retains DCR's key advantage: cheap post-hoc velocity corrections on top of a rigid simulation.
- **Does NOT claim physical accuracy.** The tilt is an approximation -- it captures the qualitative effect of surface bending (objects tip instead of just jumping) without the cost of deformable contact.

---

## 5. Integration with Passive Energy Injection

The tilt extension is designed to work with the passive energy-bounded DCR variant (foundation document: `passive_modal_energy_injection_foundation.md`).

### Architecture

```
PassiveDCRCoupler (Stage E3)
    |
    |-- process_step(contacts, lam, h, E_max) -> dcr_velocities
    |   |-- Project impulses to modal basis (E1)
    |   |-- Passive scaling alpha (E2, foundation section 6)
    |   |-- Velocity kick: qdot += alpha * s_total (E3)
    |   |-- Homogeneous stepping -> q_history_transient
    |   '-- Compute scalar Delta_v at resting contacts (Eqs. 11-12)
    |
    v
TiltDCRCoupler (wraps PassiveDCRCoupler)
    |
    |-- Calls passive.process_step() to get dcr_velocities + q_history
    |-- For each resting contact with nonzero Delta_v:
    |   |-- Find peak substep k* from q_history
    |   |-- Sample w_i = n . U_surf[v_i] @ q_peak at triangle vertices
    |   |-- Compute slopes (s1, s2) via patch fit
    |   |-- Compute tilted normal n' (with theta_max clamp)
    |   |-- Decompose J into J_n + J_t
    |   '-- Apply Coulomb + energy bounds to J_t
    '-- Return list of TiltResult
```

### Energy budget flow

The passive energy injection pipeline ensures:

```
cumulative E_modal_injected <= eta * cumulative E_rigid_loss    (foundation section 15)
```

The tilt extension adds tangential kinetic energy on top:

```
Delta_KE_tilt = 0.5 * m * ||J_t/m||^2 = ||J_t||^2 / (2m)
```

This is bounded by `eta_t * E_DCR` (Bound 3), which is itself a fraction of the energy already budgeted for the normal DCR kick. The tilt does not create a separate energy channel -- it redistributes a fraction of the existing DCR energy into the lateral direction.

---

## 6. Algorithm Summary

### Offline (per DCR-enabled elastic body)

```
1. Standard: compute FEM mesh, modal analysis, surface extraction
2. NEW: for each surface triangle:
   - Compute outward normal n_tri
   - Compute orthonormal tangent frame (t1, t2) from edge + normal
   - Store for runtime lookup
```

### Runtime (per rigid simulation step)

```
1. Run rigid solver (standard)
2. Compute E_loss = E_pre - E_post (standard)
3. Run PassiveDCRCoupler.process_step() (standard):
   - Modal forcing from new impacts
   - Passive alpha scaling
   - Velocity kick to persistent modal state
   - Compute transient q_history
   - Compute scalar Delta_v at resting contacts
   - Apply Delta_v along original normal n (standard DCR)
4. NEW: Run TiltDCRCoupler:
   a. For each resting contact with Delta_v > 0:
      - Find closest surface triangle
      - Find peak substep k* in q_history
      - Sample normal displacement w_i at 3 triangle vertices
      - Compute slopes (s1, s2) via 2x2 linear solve
      - Compute tilted normal n' = normalize(n - s1*t1 - s2*t2)
      - Clamp tilt angle to theta_max
      - Compute lateral direction t_dir and raw magnitude dv_t_raw = |dv| * tan(theta)
      - Amplify: dv_t = lateral_gain * dv_t_raw
      - Apply velocity, energy, and Coulomb caps
   b. Apply dv_t * t_dir as lateral velocity kick
   c. In tilt-coupled mode: also apply min(|dv|, dv_n_max) * n as capped vertical kick
5. Integrate positions (standard)
```

---

## 7. Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `theta_max` | 10 degrees | Maximum tilt angle for direction clamping |
| `mu_dcr` | 0.5 | Coulomb-like cap: `dv_t <= mu_dcr * |Delta_v|` |
| `eta_t` | 0.5 | Energy cap: `dv_t <= sqrt(eta_t) * |Delta_v|` |
| `lateral_fraction` | 0.3 | Fraction of `|Delta_v|` applied laterally (direction from tilt) |
| `dv_t_max` | 1.5 m/s | Absolute velocity cap on lateral correction |
| `dv_n_max` | 0.3 m/s | Cap on vertical DCR velocity in coupled mode |

### Operating modes

The tilt coupler supports two modes controlled by `DCRWorld.tilt_mode`:

- **`tilt_mode = "tilt"` (lateral-only ablation):** Only the bounded lateral component `dv_t * t_dir` is applied. No vertical DCR kick. Objects receive purely lateral pushes derived from the deformation slope direction — producing domino-like toppling without any vertical bouncing. This mode isolates the tilt effect for evaluation.

- **`tilt_mode = "tilt-coupled"` (default):** Applies a capped vertical DCR kick `min(|Delta_v|, dv_n_max) * n` plus the bounded lateral tilt response `dv_t * t_dir`. This is the main demonstration mode for combining visible vertical vibration response with deformation-gradient-driven rocking/toppling.

**Important:** No mode applies the full impulse along the tilted normal (`v += Delta_v * n'`). The tilted normal is used only to determine the lateral direction.

### Scene-independent design

The `lateral_fraction` parameter makes the tilt response scene-independent. Because the lateral magnitude is a fixed proportion of `|Delta_v|` (not derived from the tilt angle), the same parameter value works across scenes with different material stiffness:

- **Soft shelf (E ~ 0.5 GPa):** Large tilt angles (~2°), strong modal displacement. The tilt direction is well-defined; the lateral fraction scales with the (large) DCR kick.
- **Stiff ground (E ~ 10 GPa):** Tiny tilt angles (~0.3°), weak modal displacement. The tilt direction is still meaningful; the lateral fraction scales with the (smaller) DCR kick.

No per-scene tuning of `lateral_fraction` is needed. Object geometry still matters — tall, thin objects (high aspect ratio) are more sensitive to lateral kicks than squat ones.

---

## 8. Limitations

1. **The tilted normal is an approximation.** It captures the first-order effect of surface bending but does not model the full deformed contact geometry. Edge cases (e.g., surface curvature, contact near mesh boundaries) may produce inaccurate slopes.

2. **No contact-normal feedback.** The rigid solver always uses the original normal. The tilted normal only affects the post-hoc DCR impulse. This means the friction cone and non-penetration constraints are still computed with the flat surface assumption.

3. **No domino-chain propagation through DCR.** The tilt extension can topple the first book, but the subsequent book-to-book collisions are handled by the rigid contact solver (box-box collision detection), not by DCR. The "chain" effect is a combination of tilt-DCR (first topple) + standard rigid collision (subsequent impacts).

4. **Scene-dependent effectiveness.** Very stiff elastic bodies (E > 10 GPa) produce negligible modal displacements, making the tilt angles near zero. The extension is most effective for moderately flexible surfaces.

---

## 9. Files

| File | Description |
|------|-------------|
| `dcr/dcr/tilt_dcr.py` | TiltDCRCoupler class + tilt math functions |
| `dcr/dcr/dcr_world.py` | Integration: `_apply_tilt_dcr_velocities()` |
| `dcr/dcr/passive_dcr.py` | Exposes `last_q_history_transient` for tilt layer |
| `scripts/run_tilt_demo.py` | Standalone bookshelf demo (plain/dcr/tilt modes) |
| `scripts/run_scenes.py` | All demo scenes support `--tilt` flag |
| `tests/test_tilt_dcr.py` | Unit tests (tilt math) + integration test |

---

## References

- Coevoet, Andrews, Relles, Kry. *Distant Collision Response in Rigid Body Simulations.* Computer Graphics Forum 39(8), 2020.
- `passive_modal_energy_injection_foundation.md` (this repo) -- passive energy injection math foundation.
- `dcr_implementation_prompt.md` (this repo) -- DCR core implementation stages.
> > []()