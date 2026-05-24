# Mathematical Foundation: Passive Energy Injection for Reduced Modal Contact Response

## Scope

This note formulates the mathematical core of the proposed **energy-bounded modal follow-up**. It focuses only on the passive energy injection and modal reservoir mechanism, not on the original Distant Collision Response method.

The goal is to couple rigid-body impacts to a reduced modal vibration model while guaranteeing that the modal subsystem does not receive more energy than the rigid-body system loses.

---

## 1. Rigid-Body Energy Budget

Consider a rigid-body contact event between a moving rigid body and a support structure represented by a reduced modal model.

Let the rigid-body kinetic energy immediately before contact resolution be

\[
E_{\mathrm{rigid}}^{pre}
=
\sum_b
\left(
\frac{1}{2} m_b \|\mathbf v_b\|^2
+
\frac{1}{2} \boldsymbol\omega_b^T I_b \boldsymbol\omega_b
\right)^{pre}
\]

and immediately after the solver applies the local contact impulse be

\[
E_{\mathrm{rigid}}^{post}
=
\sum_b
\left(
\frac{1}{2} m_b \|\mathbf v_b\|^2
+
\frac{1}{2} \boldsymbol\omega_b^T I_b \boldsymbol\omega_b
\right)^{post}
\]

The kinetic energy lost by the rigid-body solver is

\[
\Delta E_{\mathrm{loss}}
=
\max
\left(
0,
E_{\mathrm{rigid}}^{pre}
-
E_{\mathrm{rigid}}^{post}
\right)
\]

This quantity defines the maximum energy pool from which the modal vibration system may be funded.

Introduce an artist-controllable transfer efficiency

\[
\eta \in [0,1]
\]

Then the maximum energy allowed to enter the modal reservoir is

\[
E_{\max}
=
\eta \Delta E_{\mathrm{loss}}
\]

This gives the first passivity bound:

\[
\Delta E_{\mathrm{modal}}
\leq
E_{\max}
\leq
\Delta E_{\mathrm{loss}}
\]

---

## 2. Reduced Modal State

The support structure is represented by a reduced modal displacement field

\[
\mathbf u(\mathbf x,t)
=
\sum_{i=1}^{n}
\boldsymbol\phi_i(\mathbf x) q_i(t)
\]

or, in matrix form,

\[
\mathbf u(\mathbf x,t)
=
\Phi(\mathbf x)\mathbf q(t)
\]

where

\[
\Phi(\mathbf x)
=
\begin{bmatrix}
\boldsymbol\phi_1(\mathbf x) &
\boldsymbol\phi_2(\mathbf x) &
\cdots &
\boldsymbol\phi_n(\mathbf x)
\end{bmatrix}
\in \mathbb R^{3 \times n}
\]

The modal state is

\[
\mathbf q(t) \in \mathbb R^n,
\qquad
\dot{\mathbf q}(t) \in \mathbb R^n
\]

where \(\mathbf q\) contains modal displacements and \(\dot{\mathbf q}\) contains modal velocities.

Assuming mass-normalized modes, the modal energy is

\[
E_{\mathrm{modal}}
=
\frac{1}{2}
\dot{\mathbf q}^{T}\dot{\mathbf q}
+
\frac{1}{2}
\mathbf q^{T}\Omega^2\mathbf q
\]

where

\[
\Omega =
\mathrm{diag}(\omega_1,\omega_2,\ldots,\omega_n)
\]

and \(\omega_i\) is the natural frequency of mode \(i\).

Equivalently,

\[
E_{\mathrm{modal}}
=
\frac{1}{2}
\sum_i
\left(
\dot q_i^2
+
\omega_i^2 q_i^2
\right)
\]

---

## 3. Modal Dynamics and Dissipation

Each mode evolves as a damped oscillator:

\[
\ddot q_i
+
2\zeta_i\omega_i\dot q_i
+
\omega_i^2 q_i
=
f_i
\]

where \(\zeta_i\) is the damping ratio and \(f_i\) is the generalized modal force.

In the absence of external forcing,

\[
f_i = 0
\]

the modal energy decreases according to

\[
\frac{dE_{\mathrm{modal}}}{dt}
=
-
\sum_i
2\zeta_i\omega_i\dot q_i^2
\leq
0
\]

Thus, without new impact energy, the modal reservoir is dissipative.

This is the passivity foundation:

\[
\text{no new input}
\Rightarrow
E_{\mathrm{modal}}(t)
\text{ cannot increase}
\]

---

## 4. Contact Impulse Projection into Modal Coordinates

Suppose a contact impulse

\[
\mathbf j \in \mathbb R^3
\]

is applied to the support at contact point

\[
\mathbf x_c
\]

The raw modal velocity kick is obtained by projecting the impulse into the modal basis:

\[
\mathbf s
=
\Delta \dot{\mathbf q}_{raw}
=
\Phi(\mathbf x_c)^T \mathbf j
\]

where

\[
\mathbf s \in \mathbb R^n
\]

This formula assumes mass-normalized modes. If modes are not mass-normalized, with modal mass matrix \(M_q\), then

\[
\mathbf s
=
M_q^{-1}\Phi(\mathbf x_c)^T\mathbf j
\]

For diagonal modal masses \(m_i\),

\[
s_i
=
\frac{
\boldsymbol\phi_i(\mathbf x_c)^T \mathbf j
}{
m_i
}
\]

The impulse \(\mathbf j\) may include both normal and tangential components:

\[
\mathbf j
=
j_n \mathbf n
+
\mathbf j_t
\]

where \(j_n\mathbf n\) excites normal support response and \(\mathbf j_t\) excites tangential/frictional vibration.

---

## 5. Why the Naive Energy Estimate Is Insufficient

A naive estimate of the raw injected modal kinetic energy is

\[
\Delta E_{\mathrm{raw}}
=
\frac{1}{2}
\mathbf s^T\mathbf s
\]

This is only correct when the current modal velocity is zero:

\[
\dot{\mathbf q}_{old} = \mathbf 0
\]

In general, the support may already be vibrating. The actual update has the form

\[
\dot{\mathbf q}_{new}
=
\dot{\mathbf q}_{old}
+
\alpha \mathbf s
\]

where \(\alpha \in [0,1]\) is a passive scaling factor.

Because modal displacement \(\mathbf q\) does not change instantaneously during an impulse, the modal potential energy is unchanged at the injection instant. The energy change is entirely kinetic:

\[
\Delta E_{\mathrm{modal}}(\alpha)
=
\frac{1}{2}
\left\|
\dot{\mathbf q}_{old}
+
\alpha\mathbf s
\right\|^2
-
\frac{1}{2}
\left\|
\dot{\mathbf q}_{old}
\right\|^2
\]

Expanding gives

\[
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha
\dot{\mathbf q}_{old}^{T}\mathbf s
+
\frac{1}{2}
\alpha^2
\mathbf s^T\mathbf s
\]

The cross term

\[
\alpha
\dot{\mathbf q}_{old}^{T}\mathbf s
\]

is essential. It accounts for whether the new impulse reinforces or opposes the current modal motion.

---

## 6. Passive Scaling Coefficient

Define

\[
a = \mathbf s^T\mathbf s
\]

\[
b = \dot{\mathbf q}_{old}^{T}\mathbf s
\]

Then

\[
\Delta E_{\mathrm{modal}}(\alpha)
=
b\alpha
+
\frac{1}{2}a\alpha^2
\]

The passive injection condition is

\[
b\alpha
+
\frac{1}{2}a\alpha^2
\leq
E_{\max}
\]

Equivalently,

\[
\frac{1}{2}a\alpha^2
+
b\alpha
-
E_{\max}
\leq
0
\]

The positive root of the equality is

\[
\alpha^{*}
=
\frac{
-b
+
\sqrt{
b^2
+
2aE_{\max}
}
}{
a
}
\]

for \(a > 0\).

The final passive scaling factor is

\[
\alpha
=
\min(1,\max(0,\alpha^{*}))
\]

A practical implementation should first evaluate the full update:

\[
\Delta E_{full}
=
b
+
\frac{1}{2}a
\]

If

\[
\Delta E_{full}
\leq
E_{\max}
\]

then set

\[
\alpha = 1
\]

Otherwise use the quadratic cap above.

---

## 7. Final Passive Injection Update

The modal velocity update is

\[
\dot{\mathbf q}_{new}
=
\dot{\mathbf q}_{old}
+
\alpha\mathbf s
\]

where

\[
\mathbf s
=
\Phi(\mathbf x_c)^T\mathbf j
\]

and \(\alpha\) is chosen so that

\[
\Delta E_{\mathrm{modal}}(\alpha)
\leq
E_{\max}
=
\eta
\max
\left(
0,
E_{\mathrm{rigid}}^{pre}
-
E_{\mathrm{rigid}}^{post}
\right)
\]

Therefore,

\[
E_{\mathrm{modal}}^{new}
-
E_{\mathrm{modal}}^{old}
\leq
\eta
\Delta E_{\mathrm{loss}}
\]

This is the core passive injection guarantee.

---

## 8. Multiple Contact Events in One Timestep

If multiple contact impulses occur during one timestep, applying the same global energy bound to each contact independently is unsafe.

For contacts \(k = 1,\ldots,m\), each with impulse \(\mathbf j_k\) at location \(\mathbf x_k\), a safe aggregate projection is

\[
\mathbf s_{total}
=
\sum_{k=1}^{m}
\Phi(\mathbf x_k)^T\mathbf j_k
\]

Then perform one globally bounded update:

\[
\dot{\mathbf q}_{new}
=
\dot{\mathbf q}_{old}
+
\alpha \mathbf s_{total}
\]

with

\[
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha
\dot{\mathbf q}_{old}^{T}
\mathbf s_{total}
+
\frac{1}{2}
\alpha^2
\mathbf s_{total}^{T}
\mathbf s_{total}
\]

and

\[
\Delta E_{\mathrm{modal}}(\alpha)
\leq
\eta
\Delta E_{\mathrm{loss,total}}
\]

This prevents repeated per-contact injection from exceeding the global energy budget.

---

## 9. Modal Damping Energy

After injection, the modal state evolves under damped dynamics.

For each mode,

\[
\ddot q_i
+
2\zeta_i\omega_i\dot q_i
+
\omega_i^2 q_i
=
0
\]

The instantaneous dissipated power is

\[
P_{\mathrm{diss},i}
=
2\zeta_i\omega_i\dot q_i^2
\]

The total dissipated power is

\[
P_{\mathrm{diss}}
=
\sum_i
2\zeta_i\omega_i\dot q_i^2
\]

Over a timestep \(\Delta t\), the dissipated modal energy is approximately

\[
E_{\mathrm{diss}}
\approx
\Delta t
\sum_i
2\zeta_i\omega_i\dot q_i^2
\]

or more robustly measured as

\[
E_{\mathrm{diss}}
=
\max
\left(
0,
E_{\mathrm{modal}}^{before}
-
E_{\mathrm{modal}}^{after}
\right)
\]

when no new external modal input is applied.

---

## 10. Optional Modal Sound Energy Bound

If modal sound is synthesized from the same state, sound should be treated as a bounded energy output rather than an independent event.

Let \(\rho_i \in [0,1]\) be the acoustic radiation coefficient for mode \(i\).

A conservative energy bound is

\[
E_{\mathrm{sound},i}
\leq
\rho_i E_{\mathrm{diss},i}
\]

and globally

\[
E_{\mathrm{sound}}
\leq
\sum_i
\rho_i E_{\mathrm{diss},i}
\]

The synthesized pressure signal may be generated as

\[
p(t)
=
\sum_i g_i q_i(t)
\]

or

\[
p(t)
=
\sum_i g_i \dot q_i(t)
\]

but the perceptual gain \(g_i\) should be normalized so that the emitted acoustic energy does not exceed the allocated sound energy budget.

The defensible claim is therefore:

\[
E_{\mathrm{sound}}
\leq
E_{\mathrm{diss}}
\leq
E_{\mathrm{modal}}
\]

not that all dissipated modal energy becomes sound.

---

## 11. Full Energy Accounting

The proposed energy flow is

\[
E_{\mathrm{rigid\ loss}}
\rightarrow
E_{\mathrm{modal}}
\rightarrow
E_{\mathrm{contact\ work}}
+
E_{\mathrm{sound}}
+
E_{\mathrm{internal\ damping}}
\]

The primary injection bound is

\[
E_{\mathrm{modal\ injected}}
\leq
\eta E_{\mathrm{rigid\ loss}}
\]

The modal damping bound is

\[
\frac{dE_{\mathrm{modal}}}{dt}
\leq
0
\quad
\text{without new input}
\]

If distant contact coupling is included, any positive work done on rigid bodies should satisfy

\[
E_{\mathrm{rigid\ gain}}
\leq
E_{\mathrm{modal\ available}}
\]

so that

\[
E_{\mathrm{rigid\ gain}}
+
E_{\mathrm{sound}}
+
E_{\mathrm{internal\ damping}}
+
E_{\mathrm{modal\ remaining}}
\leq
E_{\mathrm{modal\ injected}}
\]

This is the desired passive energy budget.

---

## 12. Pseudocode

```cpp
// Inputs:
// contacts: contact impulses on modal support during this timestep
// q, qdot: current modal displacement and velocity
// Phi(x): modal basis evaluated at world/contact point x
// E_rigid_pre, E_rigid_post: rigid kinetic energy before/after contact solve
// eta: impact-to-vibration transfer efficiency in [0,1]

double E_loss = max(0.0, E_rigid_pre - E_rigid_post);
double E_max  = eta * E_loss;

// Aggregate modal impulse direction.
Vector s_total = ZeroVector(numModes);

for (Contact c : contacts)
{
    // c.j includes normal and tangential impulse components.
    s_total += transpose(Phi(c.x)) * c.j;
}

double a = dot(s_total, s_total);
double b = dot(qdot, s_total);

double alpha = 0.0;

if (a > eps && E_max > 0.0)
{
    double dE_full = b + 0.5 * a;

    if (dE_full <= E_max)
    {
        alpha = 1.0;
    }
    else
    {
        double discr = b * b + 2.0 * a * E_max;
        double root = (-b + sqrt(max(0.0, discr))) / a;
        alpha = clamp(root, 0.0, 1.0);
    }
}

// Passive modal velocity injection.
qdot += alpha * s_total;
```

---

## 13. Claims Supported by This Formulation

This formulation supports the following claims:

1. **Bounded injection**  
   The modal subsystem cannot receive more energy than a chosen fraction of the rigid-body kinetic energy lost during contact resolution.

2. **Passivity**  
   Without new impact energy, damped modal dynamics monotonically dissipate energy.

3. **Real-time cost**  
   Injection requires only modal basis evaluation, dot products, and scalar scaling.

4. **Artist control under constraint**  
   The transfer efficiency \(\eta\) controls how much lost impact energy becomes vibration, but cannot violate the energy bound.

5. **Synchronized sound compatibility**  
   Modal sound can be generated from the same energy state, with acoustic energy bounded by dissipated modal energy.

---

## 14. Claims That Should Be Avoided

Avoid claiming:

\[
\text{the full solver is unconditionally stable}
\]

The correct claim is:

\[
\text{the modal injection step is energy-bounded and passive}
\]

Avoid claiming:

\[
\text{the sound is physically accurate}
\]

The correct claim is:

\[
\text{the sound is physically synchronized and energy-consistent with the modal state}
\]

Avoid claiming:

\[
e=1 \Rightarrow \text{no vibration is fully physically correct}
\]

The safer statement is:

\[
e=1 \Rightarrow \text{no vibration in this first-order dissipated-energy-funded model}
\]

This is conservative and passive, but it underestimates reversible elastic vibration.

---

## 15. Core Equation

The central equation of the method is

\[
\boxed{
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha
\dot{\mathbf q}^{T}\mathbf s
+
\frac{1}{2}
\alpha^2
\mathbf s^T\mathbf s
\leq
\eta
\max
\left(
0,
E_{\mathrm{rigid}}^{pre}
-
E_{\mathrm{rigid}}^{post}
\right)
}
\]

with

\[
\mathbf s
=
\Phi(\mathbf x_c)^T\mathbf j
\]

or, for multiple contacts,

\[
\mathbf s
=
\sum_k
\Phi(\mathbf x_k)^T\mathbf j_k
\]

This is the mathematical foundation of the passive modal energy injection framework.

## 16. Distant-Velocity Energy-Prescribed Modes

The DCR paper (Coevoet et al. 2020, Eq. 12) prescribes a *distant-body* response of the form `Δv = d_max / h` — a kinematic-length recipe that, while convenient, makes the realized kinetic-energy injection vary inversely with the timestep squared. This follow-up replaces that recipe with two **energy-prescribed** modes for distant bodies, structurally identical to the §6 derivation but applied to *rigid* kinetic energy rather than modal energy.

Both modes share the same quadratic-budget principle as §6: pick the kick magnitude `γ ≥ 0` such that the realized kinetic-energy change

\[
\Delta KE(\gamma)
=
b\,\gamma
+
\tfrac12\,a\,\gamma^2
\]

equals a target energy `E_target = β · E_available`, β ∈ [0, 1]. The non-negative root is

\[
\boxed{
\gamma^*
=
\frac{-b + \sqrt{b^2 + 2 a E_{\mathrm{target}}}}{a}
}
\]

structurally identical to the §6 α\* formula but with the modal `(a = s^T s, b = q̇^T s)` replaced by rigid `(a, b)` derived below per mode. As in §6, the discriminant is always non-negative when `E_target ≥ 0`, and `γ* ≥ 0` because `√(b² + 2aE) ≥ |b|`. If `E_target ≤ 0` we set `γ* = 0` (no kick).

### 16.1. Version A — Linear COM kick along the deformed normal

Apply `v ← v + γ · n′` where `n′` is the deformed contact normal (extracted by `compute_deformed_normal`; same primitive Version B uses). The kinetic-energy change is purely linear:

\[
\Delta KE_A(\gamma)
=
\tfrac12\,m\,\lVert\mathbf v + \gamma\,\mathbf n'\rVert^2
-
\tfrac12\,m\,\lVert\mathbf v\rVert^2
=
m\,(\mathbf v\cdot\mathbf n')\,\gamma
+
\tfrac12\,m\,\gamma^2.
\]

So

\[
a_A = m,
\qquad
b_A = m\,(\mathbf v\cdot\mathbf n'),
\]

and the closed-form solution is

\[
\boxed{
\gamma^*_A
=
-(\mathbf v\cdot\mathbf n')
+
\sqrt{(\mathbf v\cdot\mathbf n')^2 + 2 E_{\mathrm{target}} / m}
}
\]

Realized `ΔKE_A(γ*_A) = E_target` exactly (to float tolerance). The previous-release formula `γ = √(2 E_target / m)` is the correct value only in the special case `v · n′ = 0`; for any other relative motion along the deformed normal it under- or over-shoots by the cross-term `m·(v·n′)·γ`.

### 16.2. Version B — True point impulse `J = m·γ·n′` at offset r

The impulse acts at lever arm `r = x_contact − x_body`, imparting

\[
\Delta\mathbf v
=
\tfrac{J}{m}\,\mathbf n',
\qquad
\Delta\boldsymbol\omega
=
J\,\mathbf I^{-1}\,(\mathbf r\times\mathbf n').
\]

Let `v_c = v + ω × r` be the contact-point velocity before the kick. The total (linear + angular) kinetic-energy change is

\[
\Delta KE_B(\gamma)
=
m\,(\mathbf n'\cdot\mathbf v_c)\,\gamma
+
\tfrac12\,
\left[
m + m^2\,(\mathbf r\times\mathbf n')^T\,\mathbf I^{-1}\,(\mathbf r\times\mathbf n')
\right]
\gamma^2,
\]

so

\[
a_B
=
m + m^2\,(\mathbf r\times\mathbf n')^T\,\mathbf I^{-1}\,(\mathbf r\times\mathbf n')
=
m^2 \cdot k,
\qquad
b_B
=
m\,(\mathbf n'\cdot\mathbf v_c),
\]

with `k = 1/m + (r × n′)ᵀ I⁻¹ (r × n′)`. The closed form is

\[
\boxed{
\gamma^*_B
=
\frac{-b_B + \sqrt{b_B^2 + 2 a_B E_{\mathrm{target}}}}{a_B},
\qquad
J^* = m\,\gamma^*_B.
}
\]

Realized `ΔKE_B(γ*_B) = E_target` exactly. The previous-release formula `J = √(2 E_target / k)` matches `J*` only when `v_c · n′ = 0`; with non-zero contact-point velocity along the deformed normal it drifts by the cross-term `m·(n′·v_c)·γ`.

### 16.3. Connection to `m_eff` (paper Eq. 17)

The bracketed quantity inside `a_B` is exactly `m² · k`, where

\[
k
=
\frac{1}{m} + (\mathbf r\times\mathbf n')^T\,\mathbf I^{-1}\,(\mathbf r\times\mathbf n')
=
\frac{1}{m_{\mathrm{eff}}}
\]

is the **inverse effective mass at the contact point along the direction n′** — precisely the quantity in the paper's Eq. 17 (Schur diagonal / contact-frame inverse mass) specialized to a single normal direction. The Version B formula therefore reads:

> *"Spend `E_target` joules of kinetic energy through the inverse effective mass at the contact along the deformed normal, correcting for the velocity the contact point already has in that direction."*

This makes the connection between the §6 modal derivation and the rigid-body recipe transparent: in §6 the relevant *inverse effective mass* is `s^T s` (the projection of the impulse-direction onto modal coordinates); in §16 it is `m_eff(r, n′)` (the projection onto a rigid-body contact frame). The same quadratic principle gives the energy-exact magnitude in both cases.

### 16.4. Passivity tie-in (§15)

Both `γ*_A` and `γ*_B` are local per-body energy-exact kicks. The §15 core inequality

\[
\Delta E_{\mathrm{modal}}(\alpha)
\le
\eta\,\max(0, E_{\mathrm{rigid}}^{pre} - E_{\mathrm{rigid}}^{post})
\]

still governs the **global** passivity bound — `E_target = β · E_available` is sourced from a passive budget upstream (see §8), and the world-level cap (`_bound_linear_kick_dcr_velocities` / `_bound_point_impulse_dcr_velocities`) remains in place as a safety net. With the corrected `γ*` formulas the per-body realized energy hits `E_target` exactly, so the cap binds only for genuine multi-body / passivity reasons rather than to mask a per-body bookkeeping error.

## 17. Deformed Contact Normal via F⁻ᵀ Push-Forward

The energy-prescribed distant-velocity modes (§16) take a direction `n′` — the deformed contact normal — as input. This section derives `n′` from the modal state `q` using the deformation-gradient push-forward, following **Barbič & James (2008), IEEE Transactions on Haptics 1(1):39–52, §4.1** (PDF: `reference/BarbicJames-2008-IEEE-TOH.pdf`).

### 17.1. Setup

Let `x_c` be the contact point on the elastic body's surface, and let `T` be the unique tet that owns the closest surface triangle to `x_c`. Denote the tet's four vertices by `{X_0, X_1, X_2, X_3}` (three on the surface, one in the interior). For a linear simplex element each shape function `N_i(x)` is linear inside `T` and its gradient `∇N_i ∈ R^3` is constant within `T`. The modal displacement at any point inside `T` is

\[
\mathbf u(\mathbf x, \mathbf q) = \sum_{i=0}^{3} N_i(\mathbf x)\,\mathbf u_i(\mathbf q),
\qquad
\mathbf u_i(\mathbf q) = \boldsymbol\Phi_{\text{full}}(\mathbf X_i)\,\mathbf q,
\]

where `Φ_full(X_i) ∈ R^{3×r}` is the full-volume modal basis evaluated at tet vertex `i`. Its Jacobian is also constant within `T`:

\[
\nabla \mathbf u(\mathbf x_c, \mathbf q) = \sum_{i=0}^{3} \mathbf u_i(\mathbf q)\otimes\nabla N_i .
\]

### 17.2. Deformation gradient and the normal push-forward

The deformation gradient at `x_c` is

\[
\boxed{
F(\mathbf x_c, \mathbf q) = I + \nabla \mathbf u(\mathbf x_c, \mathbf q) = I + \sum_{i=0}^{3} \mathbf u_i(\mathbf q)\otimes \nabla N_i .
}
\]

Normals transform contravariantly under deformation (Nanson's relation in the limit of zero area change), so the deformed unit normal is

\[
\boxed{
\mathbf n' = \frac{F^{-T}\,\mathbf n_{\text{rest}}}{\lVert F^{-T}\,\mathbf n_{\text{rest}}\rVert}.
}
\]

This is exact for arbitrary `q` within the linear-elastic small-strain regime that modal reduction targets.

### 17.3. Relationship to the patch-fit heuristic

The patch-fit method (`dcr/dcr/deformed_normal.py`) computes `n′ ≈ normalize(n_rest − s_1 t_1 − s_2 t_2)` where `(s_1, s_2)` are the in-plane gradient components of the scalar field `w(x) = n_rest · u(x)` finite-differenced across the three surface vertices.

To first order in `‖q‖`:

\[
F^{-T} \approx I - (\nabla \mathbf u)^T,
\qquad
F^{-T}\,\mathbf n_{\text{rest}} \approx \mathbf n_{\text{rest}} - \nabla^{3D}(\mathbf u\!\cdot\!\mathbf n_{\text{rest}}).
\]

Decompose `∇^{3D}(u·n_rest) = ∇_{\tan} + (∂(u·n_rest)/∂n)\,n_{\text{rest}}`. After normalization the second term is absorbed by the magnitude correction. The patch-fit returns exactly `n_{\text{rest}} − ∇_{\tan}^{\text{(surface)}}(u·n_{\text{rest}})`, with the tangential gradient computed by linear interpolation on the contact triangle. So the question becomes whether

\[
\nabla_{\tan}^{\text{(3D, via FEM)}}(\mathbf u\!\cdot\!\mathbf n_{\text{rest}})
\;\stackrel{?}{=}\;
\nabla_{\tan}^{\text{(surface, via FD)}}(\mathbf u\!\cdot\!\mathbf n_{\text{rest}}).
\]

**They are not equal.** The 3D FEM gradient picks up `u_D ⊗ ∇N_D` from the interior tet vertex `D` (whose shape function `N_D` vanishes on the contact triangle but whose gradient `∇N_D` does not). The patch fit cannot see this contribution because it only samples `u·n_rest` at the three surface vertices. Therefore:

\[
\boxed{
\bigl\lvert\angle(\mathbf n'_{\text{BJ}},\, \mathbf n'_{\text{patch}})\bigr\rvert
= C \cdot \lVert\mathbf q\rVert + \mathcal{O}(\lVert\mathbf q\rVert^2),
}
\]

where `C` is set by the tangent-plane projection of `(u_D · n_rest) ∇N_D` divided by `‖q‖`. The two methods agree exactly at `q = 0` and differ linearly in `‖q‖` for any `q ≠ 0`.

This linear-scaling regression is pinned in `tests/stageDV/test_deformed_normal_methods.py::TestSmallQDiscrepancyScalesLinearly` (typical coefficient on a fixed-corner slab: `C ≈ 3.85 rad / ‖q‖`).

### 17.4. Connection to paper Eq. 17 and to §16

The deformation gradient `F` here is the *kinematic* push-forward for normals — distinct from the *kinetic* inverse effective mass `k = 1/m + (r×n′)^T I^{-1} (r×n′)` from §16 (which is the inverse Schur diagonal at the contact point, paper Eq. 17). §16 takes `n′` as input; §17 specifies how `n′` is computed from `q`. The two derivations compose:

```
q (modal state)        ──[§17, F^{-T}]──→  n'  (deformed contact normal)
n', r, v_c, m, I       ──[§16, γ*_B]───→  J*  (point-impulse magnitude)
```

### 17.5. Cost

Per contact:
- One brute-force closest-triangle scan — `O(n_faces)` (same as the patch fit; could be replaced by a BVH for both methods).
- One tri→tet lookup — `O(1)` (precomputed).
- Four modal evaluations `u_i = Φ_full(X_i)·q` — `O(4r)` flops.
- One `3 × 3` solve for `F^{-T} n_rest` — fixed.

Barbič & James (2008) achieved 1 kHz haptic rates with this exact construction on million-point pointshells; for DCR's ≲10² contacts per step, the cost is negligible compared to the rigid-body solver.

### 17.6. Implementation toggle

In this repo, `n′` computation is selected by `PassiveDCRCoupler.deformed_normal_method`:
- `"patch_fit"` (default during the transition): the heuristic from `dcr/dcr/deformed_normal.py`.
- `"barbic_james"`: the F⁻ᵀ method derived above, implemented in `dcr/dcr/deformed_normal_bj.py`.

Both are unit-vector–valued; both go through the same downstream §16 γ\* quadratic. The toggle exists so we can A/B compare empirically before flipping the default.

