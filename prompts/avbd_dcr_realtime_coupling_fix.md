# AVBD-DCR Real-Time Coupling Fix

## Core question

The concern is valid:

> Does coupling DCR with AVBD require high AVBD iteration counts, and if so, does that make the method too expensive for real time?

The answer is:

> The naive coupling can require high iterations, but that is a coupling-design problem, not an unavoidable property of AVBD.

The bad design is to drive DCR from the converged AVBD dual multiplier only. The fix is to drive DCR from an effective contact impulse or measured contact momentum change, then enforce passivity with a cheaper real-time approximation.

---

# 1. Why the naive coupling becomes iteration-sensitive

In the current setup, DCR reads AVBD's contact multiplier:

```text
DCR impulse source = solver.lambdas()
```

That means DCR is reading the dual variable `lambda` from the augmented-Lagrangian contact solve.

In AVBD / augmented-Lagrangian contact, the constraint force has two parts:

```math
f_c
=
-\left(\rho C(x) + \lambda\right)\frac{\partial C}{\partial x}
```

or, in normal-contact scalar form:

```math
f_N
\sim
\left(\rho_N C_N^+ + \lambda_N\right)n.
```

The key point is:

```text
At low iteration count, the augmentation/stiffness term rho C can already resist penetration,
but the dual lambda may not have fully grown yet.
```

So the rigid body can lose kinetic energy, while the reported dual-only multiplier is still too small.

That creates the pathology:

```text
AVBD has already stopped/slowed the rigid body,
but DCR reads a weak lambda,
therefore DCR injects too little modal energy.
```

At higher iterations, `lambda` becomes more accurate, so DCR appears to improve. But relying on that is expensive and conceptually wrong for a real-time method.

## Blunt diagnosis

Do **not** fix this by increasing AVBD iterations.

That is the expensive fix. It may make `lambda` more trustworthy, but it burns the point of AVBD and still does not solve material cases where the modal projection is physically small.

The correct fix is:

```text
dual-only lambda  ->  effective contact impulse
```

---

# 2. Correct impulse source for DCR

## 2.1 Bad impulse source

Do not use:

```math
J_{\lambda}
=
h\lambda_N n
```

as the only DCR impulse source.

This is iteration-sensitive because `lambda_N` is under-grown at low AVBD iterations.

---

## 2.2 Better impulse source: augmented effective impulse

Use the augmented contact force:

```math
f_{\mathrm{eff}}
\sim
\left(\lambda_N + \rho_N C_N^+\right)n.
```

Then define the effective normal impulse:

```math
J_{\mathrm{eff},N}
=
h\left(\lambda_N + \rho_N C_N^+\right)n.
```

For friction, include tangential impulse as well:

```math
J_{\mathrm{eff}}
=
J_{\mathrm{eff},N}+J_{\mathrm{eff},T}.
```

This is much less iteration-sensitive because it includes the term that actually carries the low-iteration contact response.

---

## 2.3 Best impulse source: measured contact momentum change

The most robust version is to expose the actual contact-induced momentum change from the AVBD solve:

```math
J_{\mathrm{eff}}
\approx
\Delta p_{\mathrm{contact}}.
```

For one rigid body, if the contact impulse is `J` at contact offset `r`, then:

```math
\Delta v
=
\frac{J}{m},
```

```math
\Delta \omega
=
I^{-1}(r\times J).
```

The contact-point velocity change is:

```math
\Delta v_p
=
\Delta v + \Delta\omega\times r.
```

This is the quantity DCR should care about, because DCR is trying to transfer contact momentum/energy into modal response.

---

# 3. Modal injection using the effective impulse

For each contact `k` at support point `x_k`, project the effective impulse into modal space:

```math
s_k
=
\Phi(x_k)^T J_{\mathrm{eff},k}.
```

Aggregate over contacts:

```math
s
=
\sum_k \Phi(x_k)^T J_{\mathrm{eff},k}.
```

Candidate modal velocity update:

```math
\dot q_{\mathrm{cand}}
=
\dot q_{\mathrm{old}} + s.
```

The modal kinetic-energy change under scaling `alpha` is:

```math
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha \dot q_{\mathrm{old}}^T s
+
\frac12\alpha^2 s^Ts.
```

Let:

```math
a = s^Ts,
```

```math
b = \dot q_{\mathrm{old}}^Ts.
```

Let the available injection budget be:

```math
E_{\max}
=
\eta E_{\mathrm{loss}},
```

where:

```math
E_{\mathrm{loss}}
=
\max\left(0,E_{\mathrm{rigid}}^{\mathrm{pre}}-E_{\mathrm{rigid}}^{\mathrm{post}}\right).
```

If the full update satisfies:

```math
b+\frac12a \le E_{\max},
```

then use:

```math
\alpha = 1.
```

Otherwise solve the quadratic bound:

```math
\alpha^*
=
\frac{-b+\sqrt{b^2+2aE_{\max}}}{a}.
```

Then clamp:

```math
\alpha
=
\operatorname{clamp}(\alpha^*,0,1).
```

Apply:

```math
\dot q
\leftarrow
\dot q + \alpha s.
```

Required invariant:

```math
\Delta E_{\mathrm{modal,injected}}
\le
\eta E_{\mathrm{loss}} + \epsilon.
```

---

# 4. Why high iteration is the wrong fix

High AVBD iterations make the dual `lambda` more converged, but this creates several problems.

## 4.1 It hurts performance

If DCR needs 16-32 AVBD iterations to behave correctly, then the coupling is not real-time-friendly.

Real-time AVBD-DCR should work at roughly:

```text
6-10 AVBD iterations
```

for the ordinary solve, depending on scene complexity.

## 4.2 It hides the wrong measurement

The actual issue is not that AVBD is iterative. The issue is that DCR reads an incomplete force representation.

At low iteration count:

```math
\lambda_N \quad \text{is incomplete,}
```

but:

```math
\lambda_N + \rho_N C_N^+
```

is closer to the actual contact force used by the solve.

## 4.3 It does not fix physically tiny modal response

Some scenes should have weak DCR response.

For example, a stiff/heavy ledge can have:

```text
small mode-shape amplitude at contact,
high modal frequencies,
strong damping,
small projection Phi^T J.
```

Then:

```math
s = \Phi(x)^T J
```

is genuinely small.

No amount of solver iteration should magically make a stiff slab behave like a soft shelf.

---

# 5. Moving-support response and passivity

The AVBD-native DCR branch should treat the deformable/modal object as a finite-energy moving support.

Modal support position:

```math
x_s(q)
=
x_s^0 + \Phi(x_s^0)q.
```

Modal support velocity:

```math
v_s(q,\dot q)
=
\Phi(x_s^0)\dot q.
```

This replaces the old DCR velocity kick:

```math
\Delta v = \frac{d_{\max}}{h}.
```

The old `d_max / h` path should not be the main mechanism in the AVBD-native branch.

---

# 6. Contact work estimator

The moving support can only do as much work on rigid bodies as its reservoir allows.

The work estimator should be impulse-based, not just global rigid kinetic-energy difference.

For one impulse `J` applied at contact offset `r`, the rigid velocity update is:

```math
\Delta v
=
\frac{J}{m},
```

```math
\Delta \omega
=
I^{-1}(r\times J).
```

The kinetic-energy change due only to this impulse is:

```math
\Delta E_{\mathrm{rigid}}(J)
=
J^T v_p^{\mathrm{before}}
+
\frac12J^T K_{\mathrm{body}}J.
```

where:

```math
v_p^{\mathrm{before}}
=
v + \omega\times r.
```

The effective inverse mass matrix at the contact point is:

```math
K_{\mathrm{body}}
=
\frac{1}{m}I_3
+
[r]_{\times}^T I^{-1}[r]_{\times}.
```

Then the positive work done by the support is:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
=
\max\left(0,\Delta E_{\mathrm{rigid}}(J)\right).
```

For multiple impulses, either accumulate them sequentially while updating intermediate velocities, or combine impulses per body/patch. Do not double-count.

---

# 7. Support work budget

Use the modal reservoir as the main support-work budget:

```math
E_{\mathrm{budget}}
=
\beta E_{\mathrm{modal,reservoir}}.
```

The key invariant is:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
\le
E_{\mathrm{budget}} + \epsilon.
```

For a closed system with no gravity, no damping, and no external work, the stronger invariant is:

```math
E_{\mathrm{rigid}}^{n+1}
+
E_{\mathrm{modal}}^{n+1}
\le
E_{\mathrm{rigid}}^n
+
E_{\mathrm{modal}}^n
+
\epsilon.
```

With damping enabled, total energy should decrease.

---

# 8. Full passivity line search: correct but expensive

The rigorous validation version can use a passivity line search.

Let `gamma` scale the modal support motion:

```math
v_s^{\gamma}
=
\gamma v_s.
```

or:

```math
x_s^{\gamma}
=
x_s^0 + \gamma\Phi q.
```

Validation algorithm:

```text
gamma = 1

for attempt in range(max_passivity_attempts):
    run AVBD moving-support contact solve using gamma
    compute impulse-based W_support_to_rigid

    if W_support_to_rigid <= E_budget + tolerance:
        accept
        break

    gamma = gamma * sqrt(E_budget / (W_support_to_rigid + eps))

if still violating:
    gamma = 0
    rerun with rest support only
```

This is physically defensible, but too expensive for the real-time path.

Worst-case cost:

```text
1 ordinary AVBD solve
+ 1 moving-support AVBD solve
+ up to 3 passivity reruns
```

That can become:

```text
up to 5 AVBD solves per frame
```

That is not acceptable for real-time unless the scene is tiny.

---

# 9. Real-time fix: one-shot gamma

For real-time mode, do not perform repeated AVBD reruns.

Use a one-shot work estimate:

```math
\gamma
=
\min\left(
1,
\sqrt{\frac{E_{\mathrm{budget}}}{W_{\mathrm{candidate}}+\epsilon}}
\right).
```

Then solve once with scaled support motion.

Real-time algorithm:

```text
1. Estimate candidate support work W_candidate.
2. Compute one-shot gamma.
3. Solve moving-support contact once using gamma.
4. Measure final work.
5. If violation is severe, skip support work for this step.
```

This is less rigorous than full line search, but it is the right real-time compromise.

The rule should be:

```text
full line search = validation/debug mode
one-shot gamma = real-time mode
```

---

# 10. Even better real-time fix: one-frame delayed support response

The cleanest real-time pipeline is to avoid same-frame ordinary solve plus support solve.

Use this instead:

```text
Step n:
    1. Use existing modal q and qdot as the moving support.
    2. Solve ordinary + support contacts in one AVBD pass.
    3. Measure support work and apply modal back-reaction.
    4. Use new impact impulses to inject modal energy for step n+1.
```

This gives:

```text
one AVBD solve per frame
```

instead of:

```text
ordinary solve + moving-support solve + passivity reruns
```

The cost is one-frame latency in the modal response.

That tradeoff is acceptable because modal deformation is not really an instantaneous rigid impulse anyway. It is a dynamic support response.

For graphics/animation, one-frame latency is usually much cheaper and visually acceptable.

---

# 11. Contact patching

Do not create a moving-support constraint for every raw contact point.

Modal response is low-frequency. Many neighboring contacts should be aggregated.

Instead of:

```text
40 contact points
-> 40 Phi^T J projections
-> 40 modal-support constraints
```

use:

```text
40 contact points
-> 1-4 representative contact patches
-> 1-4 aggregated impulses
-> 1-4 modal-support constraints
```

Patch impulse:

```math
J_{\mathrm{patch}}
=
\sum_{k\in\mathcal P} J_k.
```

Patch position can be impulse-weighted:

```math
x_{\mathrm{patch}}
=
\frac{\sum_{k\in\mathcal P}\|J_k\|x_k}{\sum_{k\in\mathcal P}\|J_k\|+\epsilon}.
```

Patch modal projection:

```math
s_{\mathrm{patch}}
=
\Phi(x_{\mathrm{patch}})^T J_{\mathrm{patch}}.
```

Set hard caps:

```yaml
max_modal_support_contacts: 4
max_passivity_attempts_realtime: 0 or 1
max_passivity_attempts_validation: 3
```

If the method needs dozens of moving-support contacts to show the effect, it is not a real-time DCR follow-up anymore.

---

# 12. Causal gating

Residual modal vibration should not create infinite delayed bumps.

A modal-support contact should only be active if all gates pass.

## 12.1 Gap gate

```math
g(z,q)
\le
\delta_{\mathrm{gate}}.
```

## 12.2 Closing velocity gate

Rest-normal relative velocity:

```math
v_{\mathrm{rel},n}
=
n_0^T(v_p-v_s).
```

Require:

```math
v_{\mathrm{rel},n}
<
-v_{\min}.
```

For gravity-dominated vertical scenes, a useful default is:

```math
v_{\min}
=
\sqrt{2g\delta_{\mathrm{gate}}}.
```

## 12.3 Modal energy gate

```math
E_{\mathrm{modal}}
>
\epsilon_E E_{\mathrm{modal,peak}}.
```

If any gate fails:

```text
skip moving-support AVBD contact
do not debit modal reservoir
do not apply support work
```

---

# 13. Transpose-consistent modal back-reaction

If the support applies impulse `J` to the rigid body, the modal support must receive the opposite generalized impulse.

Forward map:

```math
v_s
=
\Phi(x_s)\dot q.
```

Reverse map:

```math
\dot q
\leftarrow
\dot q - \Phi(x_s)^TJ.
```

The same support point, basis evaluation, impulse convention, and coordinate convention must be used in both directions.

Otherwise the method can create or destroy energy silently.

Dedicated test:

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
\le \epsilon.
```

---

# 14. BJ normal handling

For the modal support deformation:

```math
u(x)
=
\Phi(x)q.
```

Approximate deformation gradient:

```math
F(x)
=
I+\nabla\Phi(x)q.
```

Barbič-James deformation-aware normal:

```math
n_{\mathrm{BJ}}
=
\operatorname{normalize}\left(F^{-T}n_0\right).
```

For the first implementation, freeze the BJ normal per contact per step:

```text
compute n_BJ once
validate it
freeze it during the AVBD solve
```

Do not rotate the normal live inside the nonlinear solve in v1.

If `F` is singular, ill-conditioned, or produces NaN/Inf:

```math
n_{\mathrm{BJ}}
\leftarrow
n_0.
```

Log the angle:

```math
\theta_{\mathrm{BJ}}
=
\arccos\left(\operatorname{clamp}(n_0^Tn_{\mathrm{BJ}},-1,1)\right).
```

If the angle is consistently tiny, BJ normals are probably not a strong centerpiece for the paper. Keep them as an ablation unless the measured angular difference is meaningful.

---

# 15. Recommended architecture: three modes

Implement three modes.

## 15.1 Debug / physical validation mode

```yaml
mode: debug_physical
avbd_iters: 16-32
impulse_source: effective_augmented_impulse_or_measured_delta_p
passivity_line_search: true
max_passivity_attempts: 3
contact_patching: optional
closed_system_energy_test: true
```

Purpose:

```text
prove the method is physically defensible.
```

Use this mode for paper figures, energy plots, and invariants.

---

## 15.2 Real-time safe mode

```yaml
mode: realtime_safe
avbd_iters: 6-10
impulse_source: effective_augmented_impulse_or_measured_delta_p
passivity_line_search: false
gamma: one_shot
contact_patching: true
max_modal_support_contacts: 4
causal_gating: true
warm_start_lambda: true
```

Purpose:

```text
make the method interactive.
```

This is the mode that should target real-time performance.

---

## 15.3 Lambda-only ablation mode

```yaml
mode: ablation_lambda_only
avbd_iters: variable
impulse_source: dual_lambda_only
passivity_line_search: optional
```

Purpose:

```text
prove that lambda-only coupling is iteration-sensitive and inferior.
```

This is not the production mode. It is an ablation.

---

# 16. Killer diagnostic experiment

Run the same scene and same impact with:

```text
iters = 4, 8, 16, 32
```

Compare:

```text
1. lambda-only modal injection
2. effective-impulse modal injection
3. measured rigid energy loss
4. modal injected energy
5. support work
6. visible displacement/toppling
7. total step time
```

Expected result:

```text
effective-impulse DCR should be much less iteration-sensitive than lambda-only DCR.
```

If effective-impulse DCR is still highly iteration-sensitive, then the AVBD coupling is not mature enough yet.

---

# 17. Required logs

Log these per step:

```text
step_id
time
mode
avbd_iters

E_rigid_pre
E_rigid_post
E_modal_pre
E_modal_post
E_modal_injected
E_modal_injection_budget
alpha_modal_injection

impulse_source
sum_lambda_impulse
sum_augmented_impulse
sum_measured_delta_p

E_support_budget
W_support_to_rigid_impulse_estimator
W_support_to_rigid_global_ke_crosscheck
gamma_support_scale
support_passivity_violation

num_contacts_raw
num_contact_patches
num_active_modal_support_contacts
num_gated_contacts

mean_bj_angle_deg
max_bj_angle_deg
num_bj_fallbacks

num_avbd_solves_per_step
num_passivity_reruns
time_contact_solve_ms
time_modal_eval_ms
time_passivity_ms
total_step_ms
```

---

# 18. Required unit tests

## Test 1: lambda-only iteration sensitivity

Run identical impact at different AVBD iterations.

Expected:

```text
lambda-only modal injection changes significantly with iteration count.
```

This demonstrates the failure mode.

---

## Test 2: effective impulse stability

Run identical impact at different AVBD iterations.

Expected:

```text
effective impulse is more stable than lambda-only impulse.
```

---

## Test 3: passive alpha bound

Check:

```math
\Delta E_{\mathrm{modal,injected}}
\le
\eta E_{\mathrm{loss}}+\epsilon.
```

---

## Test 4: impulse-work estimator

Compare:

```math
\Delta E_{\mathrm{rigid}}(J)
=
J^T v_p^{\mathrm{before}}
+
\frac12J^TK_{\mathrm{body}}J
```

against direct before/after rigid kinetic energy.

Expected:

```text
match to tolerance.
```

---

## Test 5: one-shot gamma

Given candidate work larger than the budget:

```math
W_{\mathrm{candidate}} > E_{\mathrm{budget}},
```

compute:

```math
\gamma
=
\sqrt{\frac{E_{\mathrm{budget}}}{W_{\mathrm{candidate}}+\epsilon}}.
```

Expected:

```text
gamma < 1.
```

The final accepted work should be below or near the budget.

---

## Test 6: zero modal reservoir

Input:

```math
q=0,
\qquad
\dot q=0.
```

Expected:

```text
no moving-support work
method degenerates to ordinary AVBD contact
```

---

## Test 7: transpose consistency

Single rigid body, single modal support, one impulse exchange, no gravity, no damping.

Expected:

```math
\Delta E_{\mathrm{rigid}}
+
\Delta E_{\mathrm{modal}}
\approx 0.
```

---

## Test 8: closed-system ledger

No gravity, no external forces, no damping.

Expected:

```math
E_{\mathrm{rigid}}(t)
+
E_{\mathrm{modal}}(t)
\le
E_{\mathrm{rigid}}(0)
+
E_{\mathrm{modal}}(0)
+
\epsilon.
```

---

# 19. Final recommendation

Do not make high iterations the solution.

The correct real-time direction is:

```text
dual-only lambda
    -> effective contact impulse / measured contact momentum change

full passivity rerun line search
    -> one-shot gamma in real-time mode

per-contact modal support constraints
    -> contact patches

same-frame strict modal response
    -> optional one-frame delayed support response
```

The final design should separate two goals:

```text
Validation branch:
    rigorous, slower, line-search based, closed-system checked

Real-time branch:
    one solve, effective impulse, one-shot gamma, contact patching, strict gating
```

This gives a defensible research formulation without killing performance.

---

# 20. Minimal implementation checklist

```text
[ ] Expose effective augmented contact impulse:
        J_eff = h (lambda + rho C+) n + J_t

[ ] Add measured-contact-momentum-change fallback:
        J_eff ≈ Δp_contact

[ ] Replace lambda-only modal injection with:
        s = Σ Phi(x)^T J_eff

[ ] Keep passive alpha energy cap.

[ ] Implement impulse-work estimator.

[ ] Implement one-shot gamma for real-time mode.

[ ] Keep full passivity line search only for debug/validation mode.

[ ] Add contact patching.

[ ] Add causal gating.

[ ] Add transpose-consistent modal back-reaction.

[ ] Add closed-system energy ledger.

[ ] Add ablation comparing lambda-only vs effective impulse over AVBD iteration counts.
```

