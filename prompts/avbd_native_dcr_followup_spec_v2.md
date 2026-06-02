# AVBD-Native Passive DCR Follow-Up — Implementation Spec v2

## Purpose

Implement an **AVBD-native** version of the current DCR follow-up.

This branch should focus on one question:

> Can DCR be reformulated as a passive variational contact problem where a modal deformable object acts as a finite-energy moving support?

The implementation should combine:

1. AVBD contact solving,
2. passive modal-energy injection,
3. Barbič-James deformation-aware normals,
4. modal moving-support contact,
5. explicit reservoir-based passivity,
6. transpose-consistent modal back-reaction,
7. closed-system energy checks.

This branch is **not** about comparing PGS and AVBD.

---

## Correct framing

Use this framing:

> The deformable object is a passive finite-energy moving support.  
> AVBD solves contact against that support.  
> The support can only do as much physical work as the explicit modal/rigid reservoir allows.

Do **not** use this framing:

> AVBD has an energy term, therefore passivity is automatic.

That is wrong.

The AVBD objective is a numerical optimization objective. The physical passivity claim must be enforced with explicit energy accounting.

---

## Non-goals

Do not implement or emphasize:

- no PGS comparison,
- no solver-vs-solver benchmark,
- no old DCR `d_max / h` velocity kick as the main path,
- no claim that AVBD objective decrease equals physical energy decrease,
- no claim that BJ normals generate energy,
- no claim that internal invariants alone prove physical correctness.

One external physical anchor is still allowed and recommended:

```text
A single FEM/SOFA-style ground-truth comparison scene.
```

This is not a PGS comparison. It is a correctness anchor. Internal passivity is necessary but not sufficient; a method can satisfy its own invariants and still produce wrong motion.

---

## High-level pipeline

The AVBD-native pipeline should be:

```text
1. AVBD detects/solves ordinary contact.
2. AVBD contact impulses excite modal coordinates through passive injection.
3. Modal deformation defines a moving support geometry.
4. BJ deformation gives the local contact frame.
5. AVBD solves contact against the moving support.
6. A physical contact-work estimator measures support→rigid work.
7. A passivity line search scales support motion if work exceeds budget.
8. Accepted support impulses apply modal back-reaction.
9. Logs separate AVBD objective, physical energy, contact work, and budget.
```

The old pipeline:

```text
modal displacement -> d_max / h -> explicit rigid velocity kick
```

should not be the main mechanism in this branch.

---

# 1. State variables

## 1.1 Rigid body state

For each body `b`:

```text
x_b      : center of mass position
R_b      : orientation
v_b      : linear velocity
ω_b      : angular velocity
m_b      : mass
I_b      : world-space inertia tensor
```

Rigid kinetic energy:

```math
E_{\mathrm{rigid},b}
=
\frac12 m_b \|v_b\|^2
+
\frac12 \omega_b^T I_b \omega_b
```

Total rigid kinetic energy:

```math
E_{\mathrm{rigid}}
=
\sum_b E_{\mathrm{rigid},b}
```

---

## 1.2 Modal state

For each modal support:

```text
q        : modal displacement coordinates
qdot     : modal velocity coordinates
Ω        : diagonal modal frequency matrix
ζ        : modal damping ratios or Rayleigh damping parameters
Φ(x)     : modal basis evaluated at surface point x
∇Φ(x)    : modal basis gradient evaluated at surface point x
```

Assume mass-normalized modes.

Modal energy:

```math
E_{\mathrm{modal}}
=
\frac12 \dot q^T \dot q
+
\frac12 q^T \Omega^2 q
```

---

# 2. Modal support geometry

For a rest support point `x_s^0`:

```math
u_s(q) = \Phi(x_s^0)q
```

Deformed support position:

```math
x_s(q) = x_s^0 + \Phi(x_s^0)q
```

Support velocity:

```math
v_s(q,\dot q) = \Phi(x_s^0)\dot q
```

This support velocity replaces the old DCR scalar response:

```math
\Delta v = d_{\max}/h
```

Do not use `d_max / h` as the main response path.

---

# 3. Barbič-James deformation-aware normal

Approximate the deformation gradient:

```math
F(x)
=
I + \nabla u(x)
=
I + \nabla \Phi(x)q
```

Compute the BJ normal:

```math
n_{\mathrm{BJ}}
=
\operatorname{normalize}(F^{-T}n_0)
```

where:

```text
n_0 : rest-pose normal
```

## 3.1 Important design decision: freeze the BJ normal per step

For the first implementation, **freeze `n_BJ` per contact per step**.

Do not let `n_BJ(q)` rotate live inside each AVBD nonlinear solve.

Reason:

```text
If n_BJ depends on q during the optimization, the contact frame becomes a nonlinear moving target.
That can break descent behavior, complicate augmented-Lagrangian convergence, and create apparent work through frame rotation.
```

Implementation rule:

```text
At the beginning of the AVBD moving-support solve:
    compute F
    compute n_BJ
    validate n_BJ
    freeze it for that solve
```

Later, a fully coupled version may update the normal inside outer nonlinear iterations, but that requires a separate convergence and energy argument.

## 3.2 Fallback rules

If any of the following occur:

```text
F is singular
F is ill-conditioned
n_BJ contains NaN/Inf
||n_BJ|| is too small
```

fallback:

```math
n_{\mathrm{BJ}} \leftarrow n_0
```

Log:

```text
num_bj_fallbacks += 1
```

## 3.3 Measure whether BJ matters before relying on it

Before making BJ-on-by-default a research claim, measure:

```math
\theta_{\mathrm{BJ}}
=
\arccos(\operatorname{clamp}(n_0^T n_{\mathrm{BJ}}, -1, 1))
```

Log:

```text
mean_bj_angle_deg
max_bj_angle_deg
active_contact_bj_angle_deg
```

If the angular difference is consistently tiny, BJ normals may be numerically risky and visually irrelevant for sub-millimeter DCR deformation.

Acceptance condition for BJ usefulness:

```text
BJ should produce measurable angular difference on at least one deformation-driven scene.
Otherwise keep it as an optional ablation, not the centerpiece.
```

---

# 4. AVBD objective

Use an AVBD/VBD-style implicit Euler objective as the numerical solver objective.

For generalized rigid positions `z`:

```math
\mathcal A(z)
=
\frac{1}{2h^2}
\|z-\hat z\|_M^2
+
\Psi_{\mathrm{int}}(z)
+
\Psi_{\mathrm{contact}}(z,q)
+
\Psi_{\mathrm{constraint}}(z)
```

with:

```math
\hat z = z^n + h v^n + h^2 M^{-1}f_{\mathrm{ext}}
```

Critical distinction:

```text
AVBD objective decrease is not the physical passivity proof.
```

Therefore always log separately:

```text
AVBD objective
physical rigid kinetic energy
physical modal energy
contact work
reservoir budget
```

---

# 5. Modal objective and damping

A coupled modal objective without damping is incomplete.

Basic inertial + elastic modal objective:

```math
\mathcal A_{\mathrm{modal}}(q)
=
\frac{1}{2h^2}
\|q-\hat q\|^2
+
\frac12 q^T\Omega^2q
```

where:

```math
\hat q = q^n + h\dot q^n
```

But DCR-style modal response depends strongly on damping. Add one of the following.

## Option A: explicit modal damping after solve

For each mode `i`:

```math
\dot q_i \leftarrow \exp(-\zeta_i \omega_i h)\dot q_i
```

or use the existing Rayleigh damping model.

## Option B: damping potential

Add a velocity-proportional damping term to the objective.

Approximate modal velocity:

```math
\dot q^{n+1} \approx \frac{q^{n+1}-q^n}{h}
```

Add damping penalty:

```math
\Psi_{\mathrm{damp}}
=
\frac12
(\dot q^{n+1})^T C_q (\dot q^{n+1})
```

where `C_q` is the modal damping matrix, often diagonal for modal coordinates.

For first implementation, Option A is simpler and acceptable.

Requirement:

```text
Damping must be present somewhere.
Do not ship the coupled modal objective with ζ/Rayleigh stored but unused.
```

---

# 6. Contact gap against modal support

For rigid contact point `p_r(z)` and modal support point `x_s(q)`:

```math
g(z,q)
=
n_{\mathrm{BJ}}^T
\left(
p_r(z)-x_s(q)
\right)
-
\delta_{\mathrm{shell}}
```

Non-penetration condition:

```math
g(z,q) \ge 0
```

Violation form:

```math
C_N(z,q)
=
\delta_{\mathrm{shell}}
-
n_{\mathrm{BJ}}^T
\left(
p_r(z)-x_s(q)
\right)
```

Positive violation:

```math
C_N^+ = \max(0,C_N)
```

---

# 7. Augmented-Lagrangian normal contact

Normal contact energy:

```math
\Psi_N
=
\lambda_N C_N^+
+
\frac12 \rho_N (C_N^+)^2
```

Dual update:

```math
\lambda_N
\leftarrow
\max(0,\lambda_N+\rho_N C_N^+)
```

Requirements:

```text
normal multiplier is nonnegative
inactive contacts do not receive dual updates
contact deactivates when gap is open and relative normal velocity is separating
final normal impulse or equivalent impulse must be exposed
```

---

# 8. Friction contact

Tangential step displacement:

```math
\Delta x_t
=
(I-nn^T)
\left[
(p_r^{n+1}-p_r^n)
-
(x_s^{n+1}-x_s^n)
\right]
```

Tangential multiplier:

```math
\lambda_T
```

Coulomb cone:

```math
\|\lambda_T\| \le \mu \lambda_N
```

Projection:

```math
\lambda_T
\leftarrow
\begin{cases}
\lambda_T,
&
\|\lambda_T\|\le \mu\lambda_N,
\\
\mu\lambda_N
\frac{\lambda_T}{\|\lambda_T\|},
&
\text{otherwise}.
\end{cases}
```

## 8.1 Frozen friction frame

Use a frozen contact frame per solve:

```text
n = frozen n_BJ or n0 fallback
t1, t2 = frozen orthonormal tangent basis
```

Do not rotate the friction cone continuously during the inner solve.

Reason:

```text
A rotating tangential frame can create spurious tangential work and makes work accounting ambiguous.
```

---

# 9. Passive modal injection from AVBD impulses

The AVBD contact solve must expose per-contact impulse or equivalent impulse.

For contact `k` at support point `x_k` with impulse `J_k`:

```math
s_k = \Phi(x_k)^T J_k
```

Aggregate:

```math
s = \sum_k s_k
```

Candidate modal kick:

```math
\dot q_{\mathrm{cand}} = \dot q_{\mathrm{old}} + s
```

Scaled energy change:

```math
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha \dot q_{\mathrm{old}}^T s
+
\frac12 \alpha^2 s^Ts
```

Rigid loss:

```math
E_{\mathrm{loss}}
=
\max(0,E_{\mathrm{rigid}}^{pre}-E_{\mathrm{rigid}}^{post})
```

Modal injection budget:

```math
E_{\max} = \eta E_{\mathrm{loss}}
```

Let:

```math
a=s^Ts
```

```math
b=\dot q_{\mathrm{old}}^Ts
```

If:

```math
b+\frac12a \le E_{\max}
```

use:

```math
\alpha=1
```

Otherwise:

```math
\alpha^*
=
\frac{-b+\sqrt{b^2+2aE_{\max}}}{a}
```

and:

```math
\alpha=\operatorname{clamp}(\alpha^*,0,1)
```

Apply:

```math
\dot q \leftarrow \dot q+\alpha s
```

Invariant:

```math
\Delta E_{\mathrm{modal,injected}}
\le
\eta E_{\mathrm{loss}}+\epsilon
```

---

# 10. Contact work estimation

This is the single load-bearing component of the finite-energy claim.

The primary contact-work estimator must be impulse-based.

Do **not** make this the primary estimator:

```math
W = \max(0,E_{\mathrm{rigid}}^{after}-E_{\mathrm{rigid}}^{before})
```

That global rigid-KE delta is contaminated in a coupled AVBD solve. It can include:

```text
gravity
other contacts
external forces
ordinary collision response
constraint stabilization
numerical damping
```

It may be useful as a cross-check only if the substep is isolated.

## 10.1 Primary estimator: impulse-work estimate

For accepted moving-support contact impulses:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
\approx
\sum_k J_k^T v_{p,k}^{avg}
```

where:

```math
v_{p,k}^{avg}
=
\frac12
\left(
v_{p,k}^{before}
+
v_{p,k}^{after}
\right)
```

and `J_k` is the impulse applied to the rigid body by the moving support.

Equivalent kinetic-energy identity:

For a rigid body impulse `J` at contact offset `r`:

```math
\Delta v = \frac{J}{m}
```

```math
\Delta \omega = I^{-1}(r\times J)
```

The kinetic-energy change due only to this impulse is:

```math
\Delta E_{\mathrm{rigid}}(J)
=
J^T v_p^{before}
+
\frac12 J^T K_{\mathrm{body}}J
```

with:

```math
v_p^{before}=v+\omega\times r
```

and:

```math
K_{\mathrm{body}}
=
\frac{1}{m}I_3
-
[r]_{\times} I^{-1} [r]_{\times}
```

Because:

```math
[r]_{\times}^T = -[r]_{\times}
```

this is equivalent to:

```math
K_{\mathrm{body}}
=
\frac{1}{m}I_3
+
[r]_{\times}^T I^{-1} [r]_{\times}
```

depending on the implementation convention for cross-product matrices.

Implementation requirement:

```text
Add sign/unit tests for K_body.
Do not trust this formula until tests pass.
```

Then:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
=
\max(0,\Delta E_{\mathrm{rigid}}(J))
```

For multiple impulses, either:

1. accumulate sequentially and update intermediate velocities, or
2. compute a combined impulse per body/patch before evaluating energy.

Do not double-count.

---

# 11. Work budget

Recommended first version:

```math
E_{\mathrm{budget}}
=
\beta E_{\mathrm{modal,reservoir}}
```

This is cleaner than using rigid loss for the moving-support response because the support motion should be funded by the modal reservoir.

Optional diagnostic:

```math
E_{\mathrm{rigid-loss-budget}}
=
\eta
\max(0,E_{\mathrm{rigid}}^{pre}-E_{\mathrm{rigid}}^{post})
```

Main support-work invariant:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
\le
E_{\mathrm{budget}}+\epsilon
```

Stronger closed-system condition for no gravity / no external work:

```math
E_{\mathrm{rigid}}^{n+1}
+
E_{\mathrm{modal}}^{n+1}
\le
E_{\mathrm{rigid}}^n
+
E_{\mathrm{modal}}^n
+
\epsilon
```

---

# 12. Passivity line search

Scale the moving-support contribution with:

```math
\gamma \in [0,1]
```

Use either:

```math
v_s^\gamma = \gamma v_s
```

or:

```math
x_s^\gamma = x_s^0+\gamma\Phi q
```

Algorithm:

```text
γ = 1

for attempt in range(max_passivity_attempts):
    run AVBD moving-support contact solve using γ
    compute impulse-based W_support_to_rigid

    if W_support_to_rigid <= E_budget + tolerance:
        accept
        break

    γ = γ * sqrt(E_budget / (W_support_to_rigid + eps))

if still violating:
    γ = 0
    rerun with rest support only
```

Recommended defaults:

```text
max_passivity_attempts = 3
passivity_tolerance    = 1e-6 relative to scene energy
eps                    = 1e-12
β                      = 0.1 initially
η                      = 0.5 initially
```

Important performance note:

```text
This can require up to 1 ordinary AVBD solve + 4 moving-support solves per step.
That may be too expensive for real time.
```

Therefore also implement:

```text
early reject if E_budget is near zero
early reject if causal gates fail
optional one-shot analytic γ if work scales quadratically enough
warm-start moving-support solves
cap active modal-support contacts/patches
```

---

# 13. Transpose-consistent modal back-reaction

If AVBD applies impulse `J` to the rigid body from the modal support, the modal state must receive the opposite generalized impulse:

```math
\dot q \leftarrow \dot q - \Phi(x_s)^T J
```

This only works if the forward and reverse maps are exactly transpose-consistent.

Forward map used by contact:

```math
v_s = \Phi(x_s)\dot q
```

Reverse map must use the exact same:

```math
\Phi(x_s)^T J
```

Requirements:

```text
same support point x_s
same basis evaluation Φ
same frame convention
same impulse J actually applied by the support
same rest/deformed coordinate convention
```

Do not use one Φ for forward support velocity and another Φ for back-reaction.

## 13.1 Dedicated isolated energy test

Add this test:

```text
single rigid body
single modal support
single contact
no gravity
no damping
no external forces
one impulse exchange
```

Expected:

```math
\Delta E_{\mathrm{rigid}}
+
\Delta E_{\mathrm{modal}}
\approx 0
```

or, if the contact is intentionally inelastic:

```math
\Delta E_{\mathrm{rigid}}
+
\Delta E_{\mathrm{modal}}
\le \epsilon
```

This is stronger than merely checking that modal energy decreases.

---

# 14. Causal gating

Residual modal vibration should not create infinite delayed bumps.

A moving-support contact is eligible only if all conditions pass.

## 14.1 Gap condition

```math
g(z,q) \le \delta_{\mathrm{gate}}
```

## 14.2 Closing condition

Use a relative velocity threshold, but avoid hard-coding gravity into all cases.

Rest-normal relative velocity:

```math
v_{\mathrm{rel},n}
=
n_0^T(v_p-v_s)
```

Require:

```math
v_{\mathrm{rel},n}< -v_{\min}
```

Suggested default for gravity-dominated vertical scenes:

```math
v_{\min} = \sqrt{2g\delta_{\mathrm{gate}}}
```

But for horizontal or non-gravity-driven contacts, allow config override:

```text
v_min_closing: user-configurable
```

## 14.3 Modal-energy condition

```math
E_{\mathrm{modal}} > \epsilon_E E_{\mathrm{modal,peak}}
```

Suggested:

```text
epsilon_E = 1e-5
```

If any gate fails:

```text
skip moving-support AVBD contact
do not debit modal reservoir
do not apply support work
```

---

# 15. Closed-system global energy ledger

Piecewise invariants can pass while the composition leaks energy.

Add an end-to-end closed-system test.

Scenario:

```text
no gravity
no damping
no external forces
one rigid body
one modal support
one or several contacts
```

Required result over many steps:

```math
E_{\mathrm{rigid}}(t)
+
E_{\mathrm{modal}}(t)
\le
E_{\mathrm{rigid}}(0)
+
E_{\mathrm{modal}}(0)
+
\epsilon
```

If damping is enabled, total energy should decrease.

This test catches:

```text
double-counted reservoirs
bad work estimator signs
non-transpose back-reaction
BJ frame energy injection
γ-loop accounting errors
```

This is mandatory.

---

# 16. Real-time viability constraints

This branch is AVBD-only, but it still targets DCR-style interactive/real-time use.

Add a performance budget section to logs.

Log:

```text
num_avbd_solves_per_step
num_passivity_reruns
num_active_modal_support_contacts
num_modal_basis_evals
num_bj_normal_evals
time_contact_solve_ms
time_modal_eval_ms
time_passivity_line_search_ms
total_step_ms
```

Initial target:

```text
interactive prototype: < 33 ms/step if possible
research prototype: explain when exceeding 33 ms/step
```

Hard warning:

```text
ordinary AVBD solve + moving-support solve + up to 3 reruns can be too expensive.
```

Therefore first implementation should support:

```text
contact patching
warm starts
early gating
max active support contacts
one-shot γ approximation
```

---

# 17. Code layout

Create AVBD-specific files:

```text
dcr/avbd/
    __init__.py

    state.py
        AVBDRigidBodyState
        AVBDModalState
        AVBDStepState

    modal_support.py
        ModalSupport
        eval_modal_displacement()
        eval_modal_velocity()
        eval_deformation_gradient()
        eval_bj_normal()
        eval_bj_angle()

    objective.py
        avbd_inertia_energy()
        modal_inertia_energy()
        modal_elastic_energy()
        modal_damping_update()
        total_avbd_objective()

    constraints/
        __init__.py
        modal_contact.py
            ModalSupportContact
            compute_gap()
            compute_normal_violation()
            normal_augmented_energy()
            update_normal_dual()
            compute_tangent_displacement()
            project_friction_cone()
            freeze_contact_frame()

    reservoir.py
        rigid_kinetic_energy()
        modal_energy()
        passive_alpha_from_impulse()
        estimate_impulse_work()
        estimate_global_ke_crosscheck()
        passivity_scale_gamma()
        closed_system_energy_ledger()

    solver.py
        AVBDPrimalSolver
        AVBDDualUpdater
        solve_avbd_step()

    dcr_coupler.py
        AVBDPassiveDCRCoupler
        collect_contact_impulses()
        inject_modal_passive()
        solve_moving_support_contacts()
        apply_modal_backreaction()

    diagnostics.py
        AVBDEnergyLogEntry
        AVBDEnergyLogger
        check_passivity_violation()
        check_bj_normal_validity()
        check_closed_system_energy()
        check_realtime_budget()
```

Avoid modifying old solver files except for narrow adapters.

---

# 18. Main integration class

```python
class AVBDPassiveDCRCoupler:
    def __init__(
        self,
        modal_supports,
        eta: float = 0.5,
        beta: float = 0.1,
        contact_shell_delta: float = 1e-4,
        causal_gating: bool = True,
        max_passivity_attempts: int = 3,
        use_bj_normal: bool = True,
        freeze_bj_normal_per_step: bool = True,
        use_impulse_work_estimator: bool = True,
        enable_closed_system_energy_test: bool = False,
    ):
        ...
```

Main method:

```python
def step(self, rigid_bodies, contacts, h):
    """
    AVBD-only passive DCR step.

    1. Snapshot physical energy.
    2. Run ordinary AVBD contact solve.
    3. Collect AVBD contact impulses.
    4. Passively inject modal qdot using quadratic alpha.
    5. Apply modal damping.
    6. Evaluate modal support geometry and frozen BJ contact frames.
    7. Causally gate modal-support contacts.
    8. Run AVBD moving-support contact solve with passivity line search.
    9. Estimate support->rigid work using impulse-work estimator.
    10. Apply transpose-consistent modal back-reaction.
    11. Update rigid velocities.
    12. Log AVBD objective and physical energy separately.
    13. Check local and global energy invariants.
    """
```

---

# 19. Minimal step algorithm

```text
Input:
    rigid states at n
    modal states at n
    contact candidates
    timestep h

1. Snapshot:
       E_rigid_pre
       E_modal_pre
       AVBD_objective_pre

2. Predict:
       z_hat = z_n + h v_n + h^2 M^-1 f_ext
       q_hat = q_n + h qdot_n

3. Ordinary AVBD contact solve:
       solve normal/friction contacts
       expose contact impulses J_k

4. Passive modal injection:
       s = Σ Φ(x_k)^T J_k
       compute α
       qdot += αs

5. Modal damping:
       apply Rayleigh/modal damping update

6. Build modal support:
       x_s = x_s0 + Φq
       v_s = Φqdot
       F = I + ∇Φq
       n_BJ = normalize(F^-T n0)
       freeze n_BJ for this solve

7. BJ diagnostics:
       θ_BJ = acos(clamp(n0 dot n_BJ, -1, 1))
       log mean/max θ_BJ

8. Causal gating:
       gap gate
       closing velocity gate
       modal-energy gate

9. Moving-support AVBD solve:
       γ = 1
       repeat up to max_passivity_attempts:
           solve contact against support scaled by γ
           collect accepted support impulses
           W = impulse_work_estimator(J, v_before, K_body)
           if W <= E_budget + tol:
               accept
           else:
               reduce γ

10. Modal back-reaction:
       for every accepted support impulse J:
           qdot -= Φ(x_s)^T J
       use the exact same Φ and x_s as forward support velocity

11. Final energy:
       E_rigid_post
       E_modal_post
       AVBD_objective_post

12. Check:
       modal injection bound
       support work bound
       no-contact no-work
       zero-modal no-work
       closed-system total energy if enabled

13. Log performance:
       solve count
       rerun count
       active modal contacts
       total step time
```

---

# 20. Full coupled endpoint

The eventual target is a single coupled solve:

```math
\min_{z^{n+1},q^{n+1}}
\mathcal A(z^{n+1},q^{n+1})
```

with:

```math
\mathcal A(z,q)
=
\frac{1}{2h^2}
\|z-\hat z\|_M^2
+
\frac{1}{2h^2}
\|q-\hat q\|^2
+
\frac12 q^T\Omega^2q
+
\Psi_{\mathrm{damp}}
+
\sum_c \Psi_N(g_c(z,q))
+
\sum_c \Psi_T(z,q)
```

where:

```math
g_c(z,q)
=
n_{\mathrm{BJ}}(q_{\mathrm{frozen}})^T
\left(
p_r(z)-x_s(q)
\right)
-
\delta_{\mathrm{shell}}
```

For v1, freeze `n_BJ` per outer iteration or per step.

Do not use live continuously rotating normals until the energy/convergence behavior is understood.

---

# 21. Diagnostics to log every step

```text
step_id
time

AVBD_objective_before
AVBD_objective_after

E_rigid_pre
E_rigid_post
E_modal_pre
E_modal_post
E_modal_peak

E_modal_injected
E_modal_injection_budget
alpha_modal_injection

E_support_budget
W_support_to_rigid_impulse_estimator
W_support_to_rigid_global_ke_crosscheck
support_passivity_violation
gamma_support_scale

num_contacts
num_gated_contacts
num_active_modal_support_contacts
num_bj_fallbacks

mean_bj_angle_deg
max_bj_angle_deg

max_penetration
max_normal_multiplier
max_tangent_multiplier

num_avbd_solves_per_step
num_passivity_reruns
time_contact_solve_ms
time_modal_eval_ms
time_passivity_line_search_ms
total_step_ms
```

---

# 22. Required invariants

## Invariant 1: modal injection bound

```math
\Delta E_{\mathrm{modal,injected}}
\le
\eta
\max(0,E_{\mathrm{rigid}}^{pre}-E_{\mathrm{rigid}}^{post})
+
\epsilon
```

## Invariant 2: support work bound

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
\le
E_{\mathrm{budget}}
+
\epsilon
```

## Invariant 3: zero modal reservoir gives no moving-support work

If:

```math
q=0,\quad \dot q=0
```

then:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}=0
```

and the method reduces to ordinary AVBD contact.

## Invariant 4: no eligible contact gives no support work

If contact/gating fails:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}=0
```

## Invariant 5: transpose consistency

The map used for forward support velocity:

```math
v_s=\Phi(x_s)\dot q
```

must be exactly dual to back-reaction:

```math
\dot q \leftarrow \dot q-\Phi(x_s)^TJ
```

## Invariant 6: BJ normal validity

```math
\|n_{\mathrm{BJ}}\|=1
```

within tolerance, or fallback to `n0`.

## Invariant 7: closed-system non-increase

For no gravity, no damping, no external work:

```math
E_{\mathrm{rigid}}^{n+1}+E_{\mathrm{modal}}^{n+1}
\le
E_{\mathrm{rigid}}^n+E_{\mathrm{modal}}^n+\epsilon
```

With damping, total energy should decrease.

---

# 23. Unit tests

## Test 1: BJ identity

Input:

```math
q=0
```

Expected:

```math
n_{\mathrm{BJ}}=n_0
```

---

## Test 2: BJ fallback

Input:

```text
singular or ill-conditioned F
```

Expected:

```text
fallback to n0
no NaN
num_bj_fallbacks increments
```

---

## Test 3: BJ angular diagnostic

Input:

```text
known deformation gradient with known normal rotation
```

Expected:

```text
θ_BJ matches analytic value
```

---

## Test 4: passive alpha full kick

If:

```math
\Delta E_{\mathrm{full}}\le E_{\max}
```

then:

```math
\alpha=1
```

---

## Test 5: passive alpha clamp

If:

```math
\Delta E_{\mathrm{full}}>E_{\max}
```

then:

```math
0\le\alpha<1
```

and:

```math
\Delta E_{\mathrm{modal}}(\alpha)\le E_{\max}+\epsilon
```

---

## Test 6: impulse-work estimator

For a single rigid body and known impulse `J`, compare:

```math
\Delta E_{\mathrm{rigid}}(J)
=
J^T v_p^{before}
+
\frac12J^TK_{\mathrm{body}}J
```

against direct before/after kinetic energy.

Expected:

```text
match to tolerance
```

---

## Test 7: passivity line search reduces gamma

Mock AVBD solve returns:

```text
W > E_budget
```

Expected:

```text
gamma decreases
final accepted W <= E_budget + tolerance
```

---

## Test 8: transpose-consistent back-reaction

Single support/rigid contact, no gravity, no damping.

Apply impulse exchange.

Expected:

```math
\Delta E_{\mathrm{rigid}}
+
\Delta E_{\mathrm{modal}}
\approx 0
```

or non-positive if inelastic.

---

## Test 9: zero modal reservoir disables support work

Input:

```math
q=0,\quad \dot q=0
```

Expected:

```text
no moving-support work
ordinary AVBD contact only
```

---

## Test 10: closed-system ledger over many steps

No gravity, no external work.

Expected:

```math
E_{\mathrm{total}}(t)
\le
E_{\mathrm{total}}(0)+\epsilon
```

for all steps.

---

# 24. Implementation milestones

## Milestone 1: AVBD contact impulse exposure

Required API:

```python
contact_result.impulse_world
contact_result.point_world
contact_result.normal_world
contact_result.body_id
contact_result.support_id
contact_result.lambda_normal
contact_result.lambda_tangent
```

If AVBD only gives position corrections, estimate equivalent impulse from velocity change, but mark the estimate as approximate.

---

## Milestone 2: modal support evaluator

Implement:

```python
eval_modal_displacement(x)
eval_modal_velocity(x)
eval_deformation_gradient(x)
eval_bj_normal(x, n0)
eval_bj_angle(x, n0)
```

---

## Milestone 3: frozen contact frame

Implement:

```python
freeze_contact_frame(n_bj_or_n0)
```

Return:

```text
n
t1
t2
```

Use this frame throughout one moving-support solve.

---

## Milestone 4: passive modal injection from AVBD impulse

Feed AVBD contact impulses into the existing quadratic alpha bound.

---

## Milestone 5: impulse-work estimator

Implement and test:

```python
estimate_impulse_work(J, v_before, omega_before, r, m, I_world)
```

This is mandatory before claiming passivity.

---

## Milestone 6: moving-support AVBD contact

Contact support geometry must depend on:

```math
x_s(q)=x_s^0+\Phi q
```

Response must come from AVBD constraints, not direct velocity kick.

---

## Milestone 7: passivity line search

Implement `γ` scaling and rerun logic.

---

## Milestone 8: modal back-reaction

Apply:

```math
\dot q \leftarrow \dot q-\Phi(x_s)^TJ
```

using the exact same `Φ(x_s)` as forward support velocity.

---

## Milestone 9: closed-system energy test

Add the no-gravity/no-external-work total-energy ledger test.

---

## Milestone 10: performance logging

Log solve count and timing.

---

# 25. Acceptance criteria

This branch is successful if:

1. Contact response is AVBD-only.
2. The modal support enters as geometry/constraints.
3. The old `d_max / h` kick is not the main path.
4. AVBD contact impulses drive passive modal injection.
5. The contact-work estimator is impulse-based and unit-tested.
6. BJ normals are computed, validated, frozen per solve, and logged.
7. BJ angular difference is measured.
8. Modal damping is actually applied.
9. Moving-support work is bounded by reservoir budget.
10. Modal back-reaction is transpose-consistent.
11. Closed-system total energy is non-increasing without external work.
12. With zero modal energy, the method degenerates to ordinary AVBD contact.
13. With no eligible contact, residual vibration does not generate support work.
14. Logs separate AVBD objective from physical energy.
15. Performance logs report how many AVBD solves happen per step.

---

# 26. Recommended default config

```yaml
avbd_dcr:
  eta: 0.5
  beta: 0.1

  use_bj_normal: true
  freeze_bj_normal_per_step: true
  log_bj_angle: true

  causal_gating: true
  contact_shell_delta: 1.0e-4
  gate_delta: 1.0e-4
  v_min_closing: auto_or_user_configured
  energy_cutoff_frac: 1.0e-5

  use_impulse_work_estimator: true
  use_global_ke_work_crosscheck: true

  max_passivity_attempts: 3
  passivity_tolerance: 1.0e-6

  allow_dmax_over_h_kick: false

  apply_modal_damping: true
  damping_mode: explicit_modal_decay

  enable_closed_system_energy_test: true

  log_avbd_objective: true
  log_physical_energy: true
  log_performance: true
```

---

# 27. Final instruction to implementation agent

Build the AVBD branch around this invariant:

```text
The moving support can only transfer physical work that is explicitly present in its reservoir.
```

The most important implementation pieces are:

```text
1. impulse-based contact-work estimator
2. transpose-consistent modal back-reaction
3. frozen BJ contact frame
4. explicit modal damping
5. passivity line search
6. closed-system total-energy ledger
7. performance logging
```

If any of these are missing, the branch may still run, but the formulation is not yet defensible.
