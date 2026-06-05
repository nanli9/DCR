# Reduced-Coordinate AVBD Support Contact

## Document version

**v2 — gap-closing revision.**

This revision keeps the original formulation intact and adds the material that the
first draft underweighted. The substantive additions are:

```text
1. Honest positioning vs. subspace deformable contact   (new front-matter section)
2. Scope and applicability statement                    (new front-matter section)
3. Implicit-Euler "transient smearing" analysis          (new Section 8)
4. Two-rate sub-stepped reduced block (transient fix)    (new Section 9, updates Section 10 loop)
5. Unified modal + spatial-attenuation regime            (new Section 12, restores DCR's large-object half)
6. Basis local-vs-distant transfer trade, formalized     (expanded Section 13)
7. Cost model including collision detection              (new Section 17)
8. Updated milestones / diagnostics / acceptance / risks (Sections 19–22)
```

The single most important addition is Section 8–9. A coupled implicit solve stepped at
the rigid-body rate converges toward implicit Euler, which damps out exactly the
high-frequency vibration that produced DCR's visible distant "kick." Section 8 quantifies
that loss; Section 9 fixes it by sub-stepping the (tiny) reduced block while still sourcing
the forcing from the converged augmented contact response, so the no-post-fix-kick property
is preserved.

---

## Is this an extension of DCR?

**Yes, but only if framed carefully.**

This should not be described as "classic DCR with AVBD." Classic DCR is a post-process style method: rigid contact happens first, then modal response is injected afterward as a distant collision response.

This new idea is better described as:

> A reduced-coordinate, variational reformulation of DCR, where the deformable support is represented by a modal/contact-enriched subspace and solved directly inside AVBD contact.

So the relationship is:

```text
Classic DCR:
    rigid contact solve
    -> extract impulse / impact
    -> modal response post-fix
    -> explicit distant response

Proposed method:
    rigid bodies + reduced deformable support
    -> solve contact together in AVBD
    -> deformation response emerges from the reduced coordinates
    -> transient distant response recovered by a sub-stepped overlay (Section 9)
```

The **DCR value proposition** is preserved:

```text
Do not simulate the full FEM mesh.
Use a cheap reduced surrogate to create deformable distant support response.
```

But the mechanism changes:

```text
Do not inject modal response afterward (as an event-gated kick).
Make the modal coordinates actual generalized coordinates of the AVBD solve,
and recover the transient peak with a two-rate sub-step driven by the
converged contact forcing.
```

A strong paper framing would be:

> We extend the DCR idea from post-hoc modal impulse response to a reduced-coordinate variational contact formulation. The support remains low-dimensional, but it participates directly in the contact solve.

A weaker and misleading framing would be:

> We just replaced DCR with full deformable simulation.

That would destroy the original DCR contribution. The key is that this method still uses **modal reduction / subspace deformation**, not full FEM.

---

## Honest positioning: what is and is not novel

This section exists because the first draft overstated novelty, and a reviewer will catch it
immediately.

**What this is, mechanically.** Once the reduced coordinates \(q\) are real generalized
coordinates solved implicitly with contact written against the deformed surface
\(x_s(q)=x_s^0+Uq\), the machinery is *subspace (reduced-order) deformable simulation with
contact*. That is a mature field: subspace dynamics and reduced internal forces
(Barbic & James), dynamic response textures (DyRT, James & Pai), and a decade of reduced /
condensed contact solvers. The augmented-Lagrangian contact layer is AVBD
(Giles, Diaz & Yuksel, SIGGRAPH 2025), itself an extension of VBD (Chen et al. 2024).

**What is genuinely ours to claim.** Not "subspace contact" in the abstract — that exists.
The defensible contributions are:

```text
(a) A reduced-support coupling specialized for DCR's use case: distant collision
    response on resting/support surfaces, robust at the low AVBD iteration counts
    (e.g. 4-8) that real-time AVBD actually uses.

(b) A two-rate construction (Section 9) that recovers the transient distant peak
    that an implicit macro-step would otherwise smear away, while sourcing the
    forcing from the converged augmented contact response rather than an event gate.
    This is the bridge between DCR's IIR-peak idea and a coupled solve.

(c) A single reduced framework that unifies the resonant-object regime (modal
    coupling) with the large-object/terrain regime (geodesic spatial attenuation),
    which classic DCR handled with two disconnected models (Section 12).
```

**The baseline that actually threatens us is not full FEM.** It is "ordinary subspace
deformable contact." Every comparison must include it (see Section 19, Milestone 7,
baseline D). If our method is indistinguishable from generic subspace contact, then only
(b) and (c) survive as contributions, and the paper must be written around them.

---

## Scope and applicability

State this plainly rather than letting a reviewer infer it.

```text
Designed for:
    - small-to-medium resonant objects (tables, shelves, roofs, fridges)
    - KNOWN support surfaces where contact location is approximately predictable
      (shelves, ledges, planks, racks)

Not handled by modal reduction alone:
    - large terrain traveling waves (a 16-128 mode basis cannot represent a deep,
      wide half-space). This is exactly why classic DCR used a SEPARATE geodesic
      attenuation model. We re-introduce that regime explicitly in Section 12,
      as a hybrid, rather than pretending modes cover it.
```

The original draft silently dropped the terrain/attenuation half of DCR. Section 12 restores
it; this section names the limitation so the restoration reads as a contribution rather than
a patch.

---

# 1. Motivation

The previous AVBD-DCR coupling became increasingly complicated:

```text
AVBD contact impulse
-> modal projection
-> passive energy cap
-> impact reservoir
-> coherent impulse bank
-> moving-support correction
```

This is patching around the fact that modal response is being added **after** the contact solve.

The cleaner idea is:

```text
Make the reduced deformable support part of the contact solve itself.
```

Instead of treating modal DCR as a post-fix, solve for rigid body motion and modal deformation together.

---

# 2. Core representation

Let the deformable support be represented by reduced coordinates:

```math
q \in \mathbb{R}^r
```

where:

```math
r \ll 3N
```

For a rest support point \(x_s^0\), the reduced deformation is:

```math
u_s(q) = U(x_s^0)q
```

and the deformed support position is:

```math
x_s(q) = x_s^0 + U(x_s^0)q
```

Here:

```math
U(x_s^0) \in \mathbb{R}^{3 \times r}
```

is the reduced basis evaluated at the support point.

If using pure vibration modes:

```math
U = \Phi
```

If using enriched modes:

```math
U =
\left[
\Phi_{\mathrm{modal}},
\Phi_{\mathrm{static}},
\Phi_{\mathrm{patch}}
\right]
```

This is the recommended version.

---

# 3. Reduced support energy

For a general reduced basis \(U\), define:

```math
M_q = U^T M U
```

```math
K_q = U^T K U
```

The reduced support energy is:

```math
E_q
=
\frac12 \dot q^T M_q \dot q
+
\frac12 q^T K_q q
```

If the modes are mass-normalized vibration modes, then:

```math
M_q = I
```

and if the modal stiffness is diagonal:

```math
K_q = \Omega^2
```

so:

```math
E_q
=
\frac12 \dot q^T \dot q
+
\frac12 q^T \Omega^2 q
```

For enriched bases, do **not** assume mass-normalization unless you explicitly orthonormalize the full basis. Use \(M_q\) and \(K_q\).

---

# 4. Unified reduced AVBD objective

Let:

- \(z\): rigid body generalized coordinates,
- \(q\): reduced support coordinates,
- \(h\): timestep,
- \(\hat z\): predicted rigid state,
- \(\hat q\): predicted reduced state.

The coupled reduced AVBD objective is:

```math
\mathcal A(z,q)
=
\frac{1}{2h^2}\|z-\hat z\|_{M_z}^{2}
+
\frac{1}{2h^2}\|q-\hat q\|_{M_q}^{2}
+
\frac12 q^T K_q q
+
\Psi_{\mathrm{damp}}(q)
+
\Psi_{\mathrm{contact}}(z,q)
```

The key difference from post-fix DCR is that contact depends directly on \(q\):

```math
\Psi_{\mathrm{contact}} = \Psi_{\mathrm{contact}}(z,q)
```

So contact forces directly update both rigid bodies and reduced support coordinates.

**Note (see Section 8–9).** Minimizing this objective at the rigid-body step size \(h\)
produces the *quasi-static / implicit-Euler* deformation \(q\). That is the correct
quantity for non-penetration and resting/stacking behavior, but it is **not** the transient
vibration peak that drives a visible distant response. The transient is recovered separately
by the two-rate overlay in Section 9, driven by the converged contact forcing of this same
objective. The distant response thus does not require any additional term in
\(\mathcal A(z,q)\); it is computed from the converged Lagrange data.

---

# 5. Contact constraint against reduced support

For a rigid contact point \(p_r(z)\) and a reduced support point \(x_s(q)\), define the gap:

```math
g(z,q)
=
n^T\left[p_r(z)-x_s(q)\right]-\delta
```

where:

- \(n\) is the contact normal,
- \(\delta\) is the contact shell thickness.

The non-penetration constraint is:

```math
g(z,q) \ge 0
```

The violation form is:

```math
C(z,q)
=
\delta
-
n^T\left[p_r(z)-x_s(q)\right]
```

and the positive violation is:

```math
C^+(z,q)=\max(0,C(z,q))
```

The augmented Lagrangian normal contact energy is:

```math
\Psi_c(z,q)
=
\lambda C^+(z,q)
+
\frac12 \rho \left(C^+(z,q)\right)^2
```

with dual update:

```math
\lambda
\leftarrow
\max(0,\lambda+\rho C^+)
```

---

# 6. Modal/reduced contact Jacobian

The reduced support position is:

```math
x_s(q)=x_s^0+U(x_s^0)q
```

The constraint is:

```math
C(z,q)
=
\delta
-
n^T\left[p_r(z)-x_s^0-U(x_s^0)q\right]
```

Therefore:

```math
\frac{\partial C}{\partial q}
=
U(x_s^0)^T n
```

Define the reduced contact Jacobian:

```math
J_q = U(x_s^0)^T n
```

The contact force contribution to the reduced gradient is:

```math
g_q^{\mathrm{contact}}
=
(\lambda+\rho C^+)J_q
```

and the Gauss-Newton / local quadratic contact Hessian contribution is:

```math
H_q^{\mathrm{contact}}
=
\rho J_q J_q^T
```

This is the central mechanism.

In the post-fix DCR version, the solver first computes contact and then projects an impulse afterward:

```math
s = U(x_c)^T J
```

In the reduced AVBD version, the contact constraint already contains \(q\), so the full augmented response:

```math
\lambda + \rho C^+
```

updates the reduced coordinates directly.

This avoids the low-iteration problem where reading only the converged dual \(\lambda\) misses the augmentation term.

---

# 7. Reduced modal block solve

During an AVBD iteration, with rigid state \(z\) temporarily fixed, solve a small reduced block for \(q\).

The reduced objective for \(q\) is:

```math
\mathcal A_q(q)
=
\frac{1}{2h^2}\|q-\hat q\|_{M_q}^{2}
+
\frac12 q^T K_q q
+
\Psi_{\mathrm{damp}}(q)
+
\sum_{c\in\mathcal C}
\left[
\lambda_c C_c^+(z,q)
+
\frac12\rho_c\left(C_c^+(z,q)\right)^2
\right]
```

Linearize each active contact:

```math
C_c(z,q+\Delta q)
\approx
C_c(z,q)+J_{q,c}^T\Delta q
```

Then solve:

```math
H_q\Delta q=-g_q
```

with:

```math
H_q
=
\frac{1}{h^2}M_q
+
K_q
+
D_q
+
\sum_{c\in\mathcal C}
\rho_c J_{q,c}J_{q,c}^T
```

and:

```math
g_q
=
\frac{1}{h^2}M_q(q-\hat q)
+
K_q q
+
g_{\mathrm{damp}}
+
\sum_{c\in\mathcal C}
(\lambda_c+\rho_c C_c^+)J_{q,c}
```

Then update:

```math
q \leftarrow q + \Delta q
```

Because \(q\) is low-dimensional, this dense solve is cheap:

```math
H_q \in \mathbb{R}^{r\times r}
```

with typical values like:

```math
r = 16, 32, 64, 128
```

---

# 8. The implicit-Euler transient-smearing problem

**This is the gap the first draft missed entirely.** It is also the one that can quietly
invalidate the whole approach, so it gets a full derivation.

Classic DCR's visible distant effect came from grabbing the **peak** of a fast modal
vibration. It ran an IIR filter at a sub-step \(T=\pi/(2\omega_{\max})\), several orders of
magnitude smaller than \(h\), and took the maximum displacement over the macro-step. The
coupled AVBD solve does the opposite: it integrates \(q\) implicitly at the macro-step \(h\)
with a few iterations, and AVBD converges toward implicit (backward) Euler. Backward Euler is
numerically dissipative for under-resolved oscillations. So the coupled solve naturally
returns the *quasi-static* deformation and **suppresses the transient peak**.

## 8.1 Per-mode amplification

Take one mass-normalized mode with frequency \(\omega\) and (for clarity) zero physical damping:

```math
\ddot q + \omega^2 q = \phi
```

Drive it with an impulsive contact response that imparts an initial modal velocity
\(\dot q(0)=v_0\) (this \(v_0\) is the modal projection of the contact impulse). The
continuous undamped solution and its peak are:

```math
q(t) = \frac{v_0}{\omega}\sin(\omega t),
\qquad
q_{\mathrm{peak}} = \frac{v_0}{\omega}.
```

This \(q_{\mathrm{peak}}\) is what DCR's IIR captures and what produces the distant kick.

Now apply **one backward-Euler step** of size \(h\) to the first-order form, with \(q^0=0\),
\(\dot q^0=v_0\):

```math
\dot q^{1} = \frac{v_0}{1+\omega^2 h^2},
\qquad
q^{1} = h\,\dot q^{1} = \frac{h\,v_0}{1+\omega^2 h^2}.
```

For a stiff mode, \(\omega h \gg 1\), so:

```math
q^{1} \approx \frac{v_0}{\omega^2 h},
\qquad
\frac{q^{1}}{q_{\mathrm{peak}}} \approx \frac{1}{\omega h}.
```

The macro-step **underestimates the peak by a factor \(\sim \omega h\)**, and it does so
monotonically — there is no overshoot, because backward Euler's amplification factor for the
oscillatory mode has modulus

```math
\frac{1}{\sqrt{1+\omega^2 h^2}} \approx \frac{1}{\omega h} \ll 1,
```

so whatever vibration energy exists is gone within roughly one step.

## 8.2 What this means with real numbers

Using the table modal frequencies reported in the original DCR paper
(\(\omega_1=393.1\), \(\omega_4=758.2\) rad/s) and a typical rigid step \(h=10^{-2}\) s:

```text
omega*h  ranges from ~3.9 (mode 1) to ~7.6 (mode 4)

=> the coupled macro-step underestimates the distant displacement peak
   by roughly 4x to 8x for the table, and shows NO oscillation.
```

In other words: the coupled solve will produce *correct resting/stacking behavior* but a
*much weaker, non-lively* distant response than DCR. If you only implement Sections 4–7 and
stop, the most likely experimental outcome is "cleaner code, but the plates barely move."
That is the failure mode to anticipate.

---

# 9. Two-rate sub-stepped reduced block (transient recovery)

The fix keeps the coupled solve for everything it is good at (non-penetration, resting,
two-way gap coupling) and adds a cheap sub-stepped overlay for the transient that the
macro-step erases. Crucially, the overlay is **driven by the converged augmented contact
forcing**, not by an `is_new` event — so the no-post-fix-kick property of the coupled
formulation is preserved.

## 9.1 Quasi-static / transient split

Conceptually split the reduced response into:

```math
q = q_{\mathrm{qs}} + \tilde q
```

- \(q_{\mathrm{qs}}\): the quasi-static coupled deformation solved by AVBD (Sections 4–7).
  Used for the gap, non-penetration, resting contacts, and two-way coupling.
- \(\tilde q\): the transient vibration overlay, integrated at a fine sub-step, used **only**
  to compute the distant response. It is not fed back into the non-penetration constraint
  (that would re-introduce stiffness and chatter); it is applied as a distant velocity change.

## 9.2 Forcing the overlay from the converged solve

After the AVBD macro-step converges, each active contact \(c\) carries an augmented normal
response

```math
f_c = \lambda_c + \rho_c C_c^+ .
```

Assemble the reduced transient forcing exactly as the contact term of the reduced gradient:

```math
\tilde r = \sum_{c\in\mathcal C}\big(\lambda_c + \rho_c C_c^+\big)\,J_{q,c}
         = \sum_{c\in\mathcal C} f_c\,U(x_c)^T n_c .
```

This is the same quantity that drove \(q\) in the coupled block, so the overlay is energetically
consistent with the solve and requires **no event detection**.

## 9.3 Sub-stepped modal integration

Integrate the reduced modal system at the DCR sub-step

```math
T = \frac{\pi}{2\,\omega_{\max}}
```

over the macro-interval \([0,h]\). Apply \(\tilde r\) as a first-sub-step impulse
(DCR-style: \(\tilde r^{(1)}/T\), \(\tilde r^{(k)}=0\) for \(k>1\)) and step each mode \(j\)
with the James–Pai IIR filter:

```math
\tilde q_j^{(k)}
=
a_{1j}\,\tilde q_j^{(k-1)}
-
a_{2j}\,\tilde q_j^{(k-2)}
+
a_{rj}\,\frac{\tilde r^{(k-1)}_j}{m_j\,T}.
```

The overlay state may be re-initialized to zero each macro-step (the DCR "restart" option) or
carried continuously to let undamped tails contribute to subsequent steps.

## 9.4 Distant response from the overlay

For each distant contact \(i\), take the maximum normal displacement over the sub-steps
(DCR Eq. 11):

```math
d_{i,\max} = \max_{k=1\ldots h/T}\big| n_i^T U_i\,\tilde q^{(k)} \big|,
```

convert to a velocity change (DCR Eq. 12):

```math
\Delta v_i = \frac{d_{i,\max}}{h},
```

map nodal velocity changes back to contact points \(p\) via barycentric weights:

```math
\Delta v_p = H_p\,\Delta v .
```

Inject \(\Delta v_p\) into the next AVBD iteration as a target separation velocity on the
distant contact (the same place \(b\) / the constraint RHS receives a restitution-style term),
or, if the solver's ERP is not accessible, as an explicit impulse using the effective mass
(DCR Eqs. 17–19):

```math
m_{\mathrm{eff}} = \frac{1}{J_p M^{-1} J_p^T},
\qquad
h f_p = m_{\mathrm{eff}}\,\Delta v_p\,n_p .
```

## 9.5 Why this is the right bridge

```text
Coupled solve (Sections 4-7):  correct non-penetration, resting, stacking, two-way gap.
Sub-stepped overlay (Section 9): recovers the transient distant peak DCR was built around.
Shared forcing f_c = lambda + rho*C^+ : no is_new gate, no impulse bank, energetically consistent.
```

The overlay is \(O(M r)\) per macro-step (M sub-steps, diagonal modal filter), which is
negligible. This is the section that turns "cleaner code but no effect" into "cleaner code
*and* the effect."

---

# 10. Solver loop

A practical block-coordinate AVBD loop, updated to include the two-rate overlay and a frozen
per-step contact set:

```text
predict z_hat, q_hat

detect contacts ONCE against the current reduced support:
    x_s(q) = x_s^0 + U(x_s^0)q
freeze contact topology for this macro-step
build reduced contact Jacobians J_q,c = U(x_c)^T n_c

for iter in range(num_avbd_iterations):

    1. Update rigid body blocks z with q frozen.

    2. Update gaps by LINEARIZATION (no re-detection):
           C_c(z, q + dq) ~= C_c(z, q) + J_q,c^T dq

    3. Solve the reduced modal block:
           H_q dq = -g_q
           q <- q + dq

    4. Update contact multipliers:
           lambda_c <- max(0, lambda_c + rho_c C_c^+)

    5. Optionally refresh frozen normals/contact frames (see Section 14).

after iterations:
    # quasi-static coupled state is done; now recover the transient overlay
    r_tilde = sum_c (lambda_c + rho_c C_c^+) J_q,c          # Section 9.2
    substep the modal IIR over [0, h] at T = pi/(2 w_max)    # Section 9.3
    d_i,max = max_k | n_i^T U_i q_tilde^(k) |                # Section 9.4
    dv_p = H_p (d_i,max / h)                                 # distant response
    inject dv_p as target separation velocity / impulse

    qdot = (q^{n+1} - q^n) / h
    rigid velocities = velocity_from(z^{n+1}, z^n)
```

This is no longer a DCR post-fix. It is a **reduced deformable support solved inside AVBD**,
with a consistent transient overlay layered on top.

---

# 11. Why this avoids the previous failures

## 11.1 No dual-only impulse extraction

The previous coupling read a contact impulse or dual multiplier after the solve. At low AVBD iterations, the augmented Lagrangian contact force may be carried by both:

```math
\lambda
```

and:

```math
\rho C^+
```

The contact force term has the form:

```math
f_c \sim (\lambda+\rho C^+)\nabla C
```

In the reduced AVBD formulation, both terms update \(q\) through:

```math
(\lambda+\rho C^+)J_q
```

So the reduced support sees the full augmented contact response.

## 11.2 No `is_new` timing gate

The previous DCR path depended on event logic like:

```text
if is_new:
    inject modal energy
```

This caused timing starvation when the rigid energy loss and the `is_new` contact flag did not align.

In the reduced AVBD formulation, every active contact contributes to the solve:

```math
\sum_{c\in\mathcal C}
(\lambda_c+\rho_c C_c^+)J_{q,c}
```

There is no one-frame injection trigger. The transient overlay (Section 9) is also driven by
this same sum, so it inherits the property: no event gate.

## 11.3 No coherent impulse bank

The previous reservoir fix still suffered because low-iteration AVBD smeared one impact over many tiny impulses:

```math
\sum_i \frac12\|s_i\|^2
\ll
\frac12\left\|\sum_i s_i\right\|^2
```

The coherent bank was an attempt to reconstruct the event-level impulse:

```math
S_{\mathrm{event}}=\sum_i s_i
```

The reduced AVBD formulation avoids this entire layer because \(q\) is solved as a state variable, not kicked afterward.

---

# 12. Unified modal + spatial-attenuation regime for large objects

This section restores the half of DCR that the first draft dropped, as a **single reduced
framework** rather than two disconnected models — which is one of the few genuinely novel
angles available (see positioning section).

## 12.1 Why modes fail for large objects

A 16–128 mode basis cannot represent a traveling Rayleigh wave on a deep, wide terrain. For
such objects, classic DCR used a geodesic spatial-attenuation model (its Eqs. 14–19). We keep
that model but source its amplitude from the same augmented contact response, and blend it
with the modal coupling by distance so a single code path handles both regimes.

## 12.2 Attenuation branch

Reusing DCR's attenuation factor at geodesic distance \(r_p\) from the impact point \(c\):

```math
s(r_p) = \exp\!\big(-\alpha (r_p - r_0)\big)\left(\frac{r_p}{r_0}\right)^{-\beta},
```

with the local displacement amplitude under the *augmented* normal response \(f_c\):

```math
\Delta x_c = \hat q^{\,T} \big(U(x_c)^T n_c\big)\, f_c,
\qquad
f_c = \lambda_c + \rho_c C_c^+,
```

where \(\hat q\) is the precomputed unit-impulse local displacement amplitude. The far-field
velocity change is:

```math
\Delta v_p^{\mathrm{atten}} = s(r_p)\,\frac{\Delta x_c}{h}.
```

## 12.3 Distance-based blend

Classify the response per distant contact by a blend weight \(w(r_p)\in[0,1]\) that favors the
modal/coupled response in the near field and the attenuation response in the far field:

```math
w(r_p) = \exp\!\left(-\left(\frac{r_p}{r_\star}\right)^2\right),
```

where \(r_\star\) is a near-field radius (a tuned modeling scale, on the order of the object's
resonant wavelength). The unified distant response is:

```math
\Delta v_p
=
w(r_p)\,\Delta v_p^{\mathrm{modal}}
+
\big(1-w(r_p)\big)\,\Delta v_p^{\mathrm{atten}},
```

with \(\Delta v_p^{\mathrm{modal}} = d_{p,\max}/h\) from Section 9.4.

## 12.4 Honest caveat on the hybrid

The attenuation branch is **explicit** (a far-field velocity correction), not part of the
coupled implicit solve. So the unified method is implicit/coupled in the near (modal) field and
explicit in the far field. That is a deliberate approximation, and the paper should say so. The
near-field coupling is where two-way contact accuracy matters (resting, stacking); the far
field is a one-way cosmetic kick, where an explicit attenuation overlay is appropriate and
cheap.

---

# 13. Basis design and the local-vs-distant transfer trade

Pure low-frequency vibration modes may not be enough, especially for local contact.

The contact projection is:

```math
J_q = U(x_c)^T n_c
```

If:

```math
U(x_c)^T n_c \approx 0
```

then contact will barely deform the support, no matter how elegant the solver is.

Therefore, the basis should be contact-enriched:

```math
U=
\left[
\Phi_{\mathrm{vibration}},
U_{\mathrm{static}},
U_{\mathrm{patch}}
\right]
```

## 13.1 The trade, made explicit

The first draft treated "add static modes" as a free fix. It is not free: **the modes that
give distant response and the modes that give local compliance pull in opposite directions**,
and the basis cannot do both with only a few vectors. Quantify it.

Define two diagnostics on the candidate basis.

**Local contact adequacy** at contact \(c\) — does the basis reproduce the true point-load
(Boussinesq-like) response \(u^*_c\) of the full FEM model? Using the \(M\)-orthogonal projector
\(P_U = U(U^T M U)^{-1} U^T M\):

```math
\varepsilon_c = \frac{\big\| (I - P_U)\,u^*_c \big\|_M}{\big\| u^*_c \big\|_M}.
```

Small \(\varepsilon_c\) means the basis captures local compliance at \(c\). Sharp point loads
are poorly represented by smooth global modes, so \(\varepsilon_c\) is large for a
vibration-only basis.

**Distant transfer** between contact \(c\) and distant point \(p\) — the static compliance
coupling through the reduced model:

```math
T(c,p) = \big(U(x_p)^T n_p\big)^T K_q^{-1} \big(U(x_c)^T n_c\big)
       = J_{q,p}^T\,K_q^{-1}\,J_{q,c}.
```

A visible distant response requires \(T(c,p)\neq 0\) for the \((c,p)\) pairs of interest.

## 13.2 Why the two fight

```text
Low-frequency vibration modes:  global support -> T(c,p) nonzero at long range (good distant)
                                smooth          -> epsilon_c large (poor local fit)

Static / patch contact modes:   local support  -> epsilon_c small (good local fit)
                                localized       -> T(c,p) ~ 0 between distant points (poor distant)
```

So you cannot simultaneously minimize \(\varepsilon_c\) and maximize distant \(T(c,p)\) with a
single small family of modes. The practical resolution is to **include both families on
purpose** — a handful of global low-frequency modes for distant transfer, plus local
static/patch modes at predicted contact zones for local compliance — and to **report both
\(\varepsilon_c\) and \(T(c,p)\)** as basis-quality metrics rather than assuming the solve will
sort it out.

## 13.3 Vibration modes

Solve the generalized eigenproblem:

```math
K\phi_i=\omega_i^2 M\phi_i
```

These modes capture global oscillation and visible distant response.

## 13.4 Static contact modes

For representative contact point \(p_j\) and direction \(d_j\), solve offline:

```math
K u_j = f_j
```

where \(f_j\) is a localized force applied at or near \(p_j\) in direction \(d_j\).

These modes capture local compliance that low-frequency vibration modes may miss.

## 13.5 Patch modes

For important contact regions, add local patch modes. These can be obtained by:

```text
1. selecting likely contact zones,
2. solving local static responses,
3. orthogonalizing them against the global modes,
4. adding them to the reduced basis.
```

This is probably necessary for shelves, ledges, planks, and support surfaces where contact is local but response should propagate. Note that static/patch modes only help at contact zones
selected offline; contact far from any selected zone returns to \(U(x_c)^T n_c\approx 0\). This
is the structural reason the method targets *known* support surfaces (see Scope section).

---

# 14. Normal handling and BJ normals

If using deformation-aware normals, approximate the deformation gradient:

```math
F(x)=I+\nabla U(x)q
```

Then compute the Barbic-James style normal:

```math
n_{\mathrm{BJ}}
=
\operatorname{normalize}(F^{-T}n_0)
```

For the first implementation, freeze the normal during one local solve:

```text
compute n_BJ at the beginning of the iteration or step
freeze n_BJ during the block update
```

Do not allow the normal to rotate continuously inside the inner solve until convergence and energy behavior are understood.

Fallback:

```math
n_{\mathrm{BJ}} \leftarrow n_0
```

if \(F\) is singular, ill-conditioned, or produces invalid values.

**Consistency note.** Freezing \(n\) while it actually depends on \(q\) breaks the gradient
consistency of the variational solve (you are minimizing a slightly inconsistent energy). This
is a standard pragmatic choice, but it is an asterisk on the "clean variational" story and
should be disclosed. Quantify its effect by comparing frozen-normal vs. \(n_0\) vs. fully
updated \(n_{\mathrm{BJ}}\) runs in the diagnostics.

---

# 15. Damping

Reduced deformation needs damping.

A simple explicit modal damping update is:

```math
\dot q_i \leftarrow \exp(-\zeta_i\omega_i h)\dot q_i
```

For a general reduced basis, use a reduced damping matrix:

```math
C_q = U^T C U
```

The damping contribution may be written as:

```math
\Psi_{\mathrm{damp}}
=
\frac12
\left(\frac{q^{n+1}-q^n}{h}\right)^T
C_q
\left(\frac{q^{n+1}-q^n}{h}\right)
```

For v1, explicit modal/Rayleigh damping is simpler.

---

# 16. Energy and passivity

This formulation is cleaner than post-fix DCR because energy transfer happens through the coupled contact solve, not through an external modal kick.

However, do **not** claim:

```text
AVBD objective decrease proves physical passivity.
```

That is not rigorous enough. The AVBD objective is a numerical implicit-integration objective. Physical energy should still be logged separately.

Log:

```math
E_{\mathrm{rigid}}
=
\sum_b
\left(
\frac12 m_b\|v_b\|^2
+
\frac12\omega_b^TI_b\omega_b
\right)
```

```math
E_q
=
\frac12\dot q^TM_q\dot q
+
\frac12q^TK_qq
```

and total physical energy:

```math
E_{\mathrm{total}}
=
E_{\mathrm{rigid}}+E_q
```

In a no-gravity, no-external-force, damped scene, expect:

```math
E_{\mathrm{total}}^{n+1}
\le
E_{\mathrm{total}}^n + \epsilon
```

Without damping and with elastic contact, energy should be approximately conserved up to numerical/solver dissipation:

```math
E_{\mathrm{total}}^{n+1}
\approx
E_{\mathrm{total}}^n
```

If contact is inelastic or dissipative:

```math
E_{\mathrm{total}}^{n+1}
\le
E_{\mathrm{total}}^n + \epsilon
```

**Added caution for the transient overlay (Section 9).** The overlay injects a distant
velocity change \(\Delta v_p\) that is *not* guaranteed energy-conserving, exactly as DCR's kick
was not. Because it is sourced from the converged augmented response it should be small and
controlled, but you must include the overlay's injected energy in \(E_{\mathrm{total}}\) and
verify decay in a damped, force-free scene. Do not assume the coupling makes the overlay passive.

---

# 17. Cost model including collision detection

The first draft bounded only the \(O(r^3)\) modal solve and called the method cheap. That is the
*wrong* term to worry about. The original DCR paper's timings were dominated by the barycentric
mapping and geodesic solves, not the modal physics — and this method inherits the same class of
overhead. Account for it honestly.

Per macro-step cost:

```math
C_{\mathrm{step}}
=
C_{\mathrm{rigid}}
+
C_{\mathrm{detect}}
+
C_{\mathrm{surface}}
+
C_{\mathrm{block}}
+
C_{\mathrm{overlay}}
```

- **Collision detection** \(C_{\mathrm{detect}}\): if re-run every AVBD iteration against the
  deforming surface, this is \(O\big(N_{\mathrm{it}}\,(\text{broad}+\text{narrow})\big)\) and can
  dominate, plus it causes contact-set chatter that fights convergence.
  *Mitigation (Section 10):* detect once per macro-step, freeze topology, and update gaps by
  linearization \(C_c(z,q+\Delta q)\approx C_c+J_{q,c}^T\Delta q\). This collapses
  \(C_{\mathrm{detect}}\) to one broad/narrow pass per step.

- **Surface evaluation** \(C_{\mathrm{surface}}\): evaluate \(x_s(q)=x_s^0+Uq\) only at active
  contact points, not all \(N_s\) surface vertices: \(O(N_c\,r)\) per iteration. Evaluating the
  full surface every iteration is the easy mistake; avoid it.

- **Reduced block** \(C_{\mathrm{block}}\): assemble \(H_q\) at \(O(N_c r^2)\), factor at
  \(O(r^3)\), per iteration. With small \(r\) this is negligible. \(K_q, M_q, D_q\) are cached.

- **Transient overlay** \(C_{\mathrm{overlay}}\): \(O(M\,r)\) per macro-step (diagonal modal IIR),
  negligible.

Honest summary:

```text
The O(r^3) block is NOT the bottleneck.
The real costs are collision detection and full-surface evaluation,
which are controlled by: detect-once-per-step + active-contact-only surface eval
+ gap linearization. Report timings with collision detection broken out separately,
exactly as the original DCR tables did.
```

---

# 18. Minimal implementation target

Start with frictionless normal contact only.

Recommended v1 configuration:

```yaml
reduced_avbd_support:
  basis:
    vibration_modes: 16
    static_contact_modes: 16
    patch_modes: 0

  coordinates:
    solve_q_inside_avbd: true
    modal_block_solve: dense_cholesky
    update_q_every_avbd_iter: true

  transient_overlay:                 # Section 9 (the transient fix)
    enabled: true
    substep_T: pi_over_2_wmax
    forcing: converged_augmented_response   # (lambda + rho*C^+) J_q
    max_displacement_extraction: true
    restart_each_step: true          # DCR restart option; flip to false to carry tails

  large_object_mode:                 # Section 12 (unified attenuation), off for v1
    enabled: false
    attenuation_beta: 1.0
    near_field_radius_r_star: tune

  contact:
    contact_against_reduced_surface: true
    detect_once_per_step: true       # Section 17 cost control
    gap_update_by_linearization: true
    normal_contact_only_first: true
    friction_enabled: false
    frozen_normal_per_iteration: true
    augmented_lagrangian_contact: true

  damping:
    enabled: true
    mode: explicit_modal_decay_or_rayleigh

  diagnostics:
    log_E_rigid: true
    log_E_reduced_support: true
    log_E_overlay_injected: true     # Section 16 caution
    log_E_total: true
    log_AVBD_objective: true
    log_contact_penetration: true
    log_iteration_sensitivity: true
    log_basis_epsilon_c: true        # Section 13 local adequacy
    log_transfer_T_cp: true          # Section 13 distant transfer
    log_collision_detection_time: true  # Section 17
```

Do not start with friction. Friction will hide whether the reduced normal contact formulation is correct.

---

# 19. Implementation milestones

## Milestone 1: basis precomputation

Build:

```math
U
```

and reduced matrices:

```math
M_q = U^TMU
```

```math
K_q = U^TKU
```

Include both vibration modes and static contact modes. Also compute and store the basis-quality
metrics \(\varepsilon_c\) and \(T(c,p)\) (Section 13) for the candidate contact zones.

## Milestone 2: reduced support surface evaluation

Implement:

```math
x_s(q)=x_s^0+U(x_s^0)q
```

and optionally:

```math
v_s(q,\dot q)=U(x_s^0)\dot q
```

Evaluate at active contacts only (Section 17).

## Milestone 3: reduced contact Jacobian

For every active contact:

```math
J_q = U(x_c)^T n_c
```

## Milestone 4: modal block solve

Build:

```math
H_q
=
\frac{1}{h^2}M_q
+
K_q
+
D_q
+
\sum_c \rho_cJ_{q,c}J_{q,c}^T
```

and:

```math
g_q
=
\frac{1}{h^2}M_q(q-\hat q)
+
K_qq
+
g_{\mathrm{damp}}
+
\sum_c(\lambda_c+\rho_cC_c^+)J_{q,c}
```

Then solve:

```math
\Delta q=-H_q^{-1}g_q
```

## Milestone 5: block-coordinate AVBD loop

Update rigid blocks and reduced support block inside the same AVBD iteration loop, with
detect-once-per-step and gap linearization (Section 10).

## Milestone 6: transient overlay (NEW — the decisive milestone)

Implement Section 9: assemble \(\tilde r\) from the converged \((\lambda+\rho C^+)J_q\), sub-step
the modal IIR at \(T=\pi/(2\omega_{\max})\), extract \(d_{i,\max}\), inject \(\Delta v_p\).
**Run the transient-survival experiment here (Section 20) before building anything else** —
this is the result that decides whether the approach is viable.

## Milestone 7: energy logging

Log separately:

```text
AVBD objective
rigid kinetic energy
reduced support energy
overlay injected energy
total physical energy
contact penetration
contact multipliers
iteration count
step time (with collision detection broken out)
```

## Milestone 8: unified large-object mode (NEW)

Implement Section 12 (attenuation branch + distance blend) and validate on a terrain/large-slab
scene. This is the differentiator milestone.

## Milestone 9: compare to baselines

Run side-by-side:

```text
A. Current modal-DCR post-fix
B. Full deformable AVBD support
C. Reduced-coordinate AVBD support (this method)
D. Ordinary subspace deformable contact   (NEW — the baseline that tests novelty)
```

Baseline D is the one that determines whether the contribution is "a new method" or
"subspace contact applied to supports plus the transient bridge + unified attenuation."

---

# 20. Diagnostics

Use the same shelf and ledge scenes.

For iteration counts:

```text
iters = 4, 8, 16, 32
```

Report:

```text
support max displacement
rigid object displacement
book/pillar toppling rate
contact penetration
E_rigid
E_q
E_overlay
E_total
step time (with collision detection separated)
iteration sensitivity CV
visual stability
basis epsilon_c (local adequacy)
transfer T(c,p) (distant adequacy)
```

## 20.1 Transient-survival experiment (NEW — run first)

The decisive test. On the shelf/ledge scene:

```text
1. Run coupled solve WITHOUT the Section 9 overlay.
   -> measure distant displacement. Expect it suppressed by ~omega*h (Section 8).
2. Run coupled solve WITH the overlay.
   -> measure distant displacement. Expect a visible, DCR-comparable peak.
3. Compare both to a high-resolution FEM / sub-stepped reference.
```

If (1) and (2) are indistinguishable, the overlay is not doing its job or the basis cannot
express the response (check \(T(c,p)\)). If (2) matches the reference envelope, the approach is
validated.

## 20.2 Size sweep (NEW)

Vary object size from "small resonant" to "large terrain-like" and report where the modal
branch fails and the attenuation branch (Section 12) must take over. This justifies the unified
formulation empirically.

The most important diagnostic is still whether the reduced support response is less
iteration-sensitive than the post-fix DCR version:

```text
Reduced-coordinate AVBD support should remove the is_new timing artifact and lambda-only extraction artifact.
```

But it may still be basis-limited if the contact response does not project into \(U\)
(measured directly by \(\varepsilon_c\) and \(T(c,p)\)).

---

# 21. Acceptance criteria

This direction is successful if:

1. The support response is produced inside the AVBD contact solve.
2. There is no post-hoc, event-gated DCR impulse kick (the transient overlay is sourced from the converged augmented response, not from `is_new`).
3. The support uses reduced coordinates, not full FEM DOFs.
4. The method is faster than full deformable AVBD support.
5. The method is less event-sensitive than current modal-DCR post-fix coupling.
6. Physical energy (including overlay-injected energy) is logged separately from the AVBD objective.
7. The reduced basis includes contact-enriched modes, not only vibration modes, and reports \(\varepsilon_c\) and \(T(c,p)\).
8. Frictionless normal contact works before friction is added.
9. The shelf scene works at low iteration counts better than the post-fix DCR version.
10. The ledge scene honestly reports whether the basis/material is too stiff to produce visible response.
11. **(NEW)** The transient-survival experiment (Section 20.1) shows the overlay restores a visible distant peak that the bare coupled solve suppresses.
12. **(NEW)** The size sweep (Section 20.2) demonstrates the unified modal+attenuation formulation covers both regimes a single model could not before.
13. **(NEW)** Comparison against ordinary subspace deformable contact (baseline D) shows a defensible difference, or the paper is honestly framed around the transient bridge and unified attenuation rather than around the coupled solve alone.

---

# 22. Risks

## Risk 1: basis cannot express local contact deformation

If:

```math
U(x_c)^Tn_c \approx 0
```

then the support will barely move.

Fix:

```text
add static contact modes and patch modes; verify with epsilon_c and T(c,p) (Section 13)
```

## Risk 2: global modal block reduces parallelism

The reduced coordinate block is global and dense. But if \(r\) is small, this is acceptable.

Cost:

```math
O(r^3)
```

for dense factorization, or cheaper if the matrix structure is reused. Note (Section 17) this is
*not* the dominant cost; collision detection is.

## Risk 3: contact nonsmoothness fights the smooth reduced basis

Contact is local and nonsmooth. Modal bases are smooth and global. This mismatch is why contact-enriched modes are necessary, and why \(\varepsilon_c\) must be measured rather than assumed small.

## Risk 4: overclaiming passivity

Do not say the AVBD objective alone proves physical passivity. Log physical energy, including
the overlay's injected energy.

## Risk 5 (NEW): transient smearing

The coupled implicit macro-step suppresses the distant peak by \(\sim\omega h\) (Section 8). If
the Section 9 overlay is omitted or mis-tuned, the headline DCR effect disappears. This is the
single largest risk; the transient-survival experiment exists to catch it early.

## Risk 6 (NEW): novelty collapse vs. subspace contact

If baseline D (ordinary subspace deformable contact) matches this method, the coupled-solve
framing is not novel. Mitigate by (a) honest positioning, and (b) leaning the contribution on
the transient bridge (Section 9) and the unified attenuation regime (Section 12).

## Risk 7 (NEW): collision-detection cost dominates

Re-detecting contacts against the deforming surface every iteration can dominate runtime and
cause chatter. Mitigate with detect-once-per-step + gap linearization + active-only surface
evaluation (Sections 10, 17).

---

# 23. Research framing

Good framing:

> We reformulate DCR-style distant deformable support response as a reduced-coordinate AVBD contact problem. Instead of injecting modal response after rigid collision, the reduced support coordinates participate directly in the variational contact solve. A two-rate sub-step, driven by the converged augmented contact response, recovers the transient distant peak that an implicit macro-step would otherwise damp. A geodesic spatial-attenuation branch extends the same reduced framework to large objects. This preserves the efficiency motivation of DCR while avoiding event-triggered post-fix coupling artifacts.

Bad framing:

> We replaced DCR with full FEM.

Bad framing:

> AVBD automatically makes the method passive.

Bad framing:

> Our coupled solve is a brand-new contact method.
> (It is built on subspace contact; the novelty is the DCR specialization,
>  the transient bridge, and the unified attenuation regime.)

Best title direction:

```text
Reduced-Coordinate AVBD Contact for DCR-Style Deformable Support Response
```

Alternative names:

```text
Subspace AVBD Contact
Reduced Variational DCR
Reduced Deformable Support Contact
Variational Reduced-Support Contact
```

**Venue.** As framed, this is a real-time/interactive physics contribution, not a top-tier
novelty contribution. Target SCA (Symposium on Computer Animation), I3D, MIG, or a CGF/TVCG
journal track. SCA fits the AVBD lineage and the real-time focus. Pushing for a top-tier
novelty venue is only justified if Milestone 8 (unified attenuation) yields a clearly new
result. Releasing code on a public AVBD-style implementation substantially strengthens the
"useful technique" claim.

---

# 24. Final verdict

This is a stronger direction than continuing to add reservoirs and coherent impulse banks.

The clean conceptual move is:

```text
Keep the reduced basis.
Delete the post-fix DCR kick.
Solve q directly inside AVBD contact for non-penetration and resting,
and recover the transient distant peak with a two-rate sub-step driven
by the converged contact forcing.
```

In one line:

> This is best viewed as a variational/reduced-coordinate extension of DCR, not classic DCR itself.

It keeps the cheap distant-response spirit of DCR, but replaces the fragile post-process modal injection with a unified reduced AVBD contact solve plus a consistent transient overlay.

**Honest bottom line.** As an engineering refactor it is very likely a real improvement and
worth building. As a research contribution its standing is contingent: it becomes a good paper
only if (1) the transient-survival experiment shows the overlay restores the distant effect,
(2) it is positioned honestly against ordinary subspace contact, and (3) the unified
attenuation regime is demonstrated. Build Milestone 6 and run Section 20.1 first — that single
experiment tells you whether you are polishing a real method or refactoring an effect into
oblivion.
