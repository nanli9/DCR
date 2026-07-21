# Modal Back-Reaction Fix for Persistent DCR / AVBD-DCR

## Purpose

This note documents the core fix for the persistent-modal DCR problem:

> If the modal/FEM support gives energy to a rigid object, the modal system must lose the corresponding energy.

Without this fix, the FEM/modal mesh behaves like an infinite or under-debited energy source. It can keep vibrating and keep kicking objects even after it has already transferred energy into them.

This is likely one major reason why objects resting on a wooden supporting mesh keep jittering for a long time.

---

## The core issue

The current persistent modal pipeline is roughly:

```text
rigid body hits support
    -> rigid body loses kinetic energy
    -> some fraction is injected into modal qdot
    -> modal support vibrates
    -> modal support velocity kicks objects above it
```

The missing piece is:

```text
when the modal support kicks a rigid object,
the modal support must lose energy.
```

If this is missing, the system does this:

```text
modal support gives impulse to rigid body
rigid body gains kinetic energy
modal qdot does not decrease
modal energy remains too high
support keeps kicking again
```

That is artificial energy creation.

---

## Important correction

Do **not** think of the workflow as:

```text
E_modal -> solve q and qdot
```

The scalar modal energy is not enough to determine the modal state.

The correct workflow is:

```text
q, qdot are the modal state
E_modal is computed from q, qdot
```

Modal energy is:

```math
E_{\mathrm{modal}}
=
\frac12 \dot q^T \dot q
+
\frac12 q^T\Omega^2q
```

where:

```text
q      : modal displacement coordinates
qdot   : modal velocity coordinates
Ω      : diagonal modal frequency matrix
```

---

## Impact-side modal injection

When a rigid body hits the FEM support, obtain the contact impulse `J_impact`.

Project it into modal coordinates:

```math
s = \Phi(x_c)^T J_{\mathrm{impact}}
```

where:

```text
Φ(x_c) : modal basis evaluated at the impact/contact point
```

Candidate modal update:

```math
\dot q_{\mathrm{candidate}}
=
\dot q_{\mathrm{old}} + s
```

Energy change under scaled kick:

```math
\Delta E_{\mathrm{modal}}(\alpha)
=
\alpha \dot q_{\mathrm{old}}^Ts
+
\frac12\alpha^2s^Ts
```

Rigid energy loss:

```math
E_{\mathrm{loss}}
=
\max(0,E_{\mathrm{rigid}}^{pre}-E_{\mathrm{rigid}}^{post})
```

Modal injection budget:

```math
E_{\max}
=
\eta E_{\mathrm{loss}}
```

Choose `α` such that:

```math
\Delta E_{\mathrm{modal}}(\alpha)
\le
E_{\max}
```

Then inject:

```math
\dot q
\leftarrow
\dot q + \alpha s
```

This handles the energy transfer:

```text
rigid body -> modal support
```

But this is only half of the story.

---

## Missing output-side energy debit

Later, the modal support can move and push objects.

At a support/contact point `x_s`, modal displacement is:

```math
u_s = \Phi(x_s)q
```

Modal support velocity is:

```math
v_s = \Phi(x_s)\dot q
```

If this moving support applies an impulse `J_support` to a rigid object, then the rigid body gains kinetic energy.

Therefore the modal system must receive the opposite generalized impulse:

```math
\boxed{
\dot q
\leftarrow
\dot q
-
\Phi(x_s)^T J_{\mathrm{support}}
}
```

This is the required **modal back-reaction**.

---

## Physical meaning

Forward map:

```math
v_s = \Phi(x_s)\dot q
```

Reverse map:

```math
\dot q \leftarrow \dot q - \Phi(x_s)^TJ
```

These must be exact transposes of each other.

If the same `Φ(x_s)` is not used in both directions, the coupling is not energy-consistent.

The support should not be allowed to do this:

```text
use Φ_A to compute support velocity
use Φ_B^T to apply back-reaction
```

That silently leaks or creates energy.

---

## Rigid impulse update

For a rigid body with mass `m`, inertia `I`, contact offset `r`, and impulse `J`:

```math
v^+
=
v^-
+
\frac{J}{m}
```

```math
\omega^+
=
\omega^-
+
I^{-1}(r\times J)
```

Contact point velocity before impulse:

```math
v_p^-
=
v^-
+
\omega^-\times r
```

Rigid kinetic-energy change caused by this impulse:

```math
\Delta E_{\mathrm{rigid}}
=
J^Tv_p^-
+
\frac12J^TK_{\mathrm{body}}J
```

where:

```math
K_{\mathrm{body}}
=
\frac{1}{m}I_3
+
[r]_\times^T I^{-1}[r]_\times
```

depending on the cross-product matrix convention, this may also appear as:

```math
K_{\mathrm{body}}
=
\frac{1}{m}I_3
-
[r]_\times I^{-1}[r]_\times
```

The implementation must unit-test the sign convention.

---

## Modal energy change from back-reaction

Let:

```math
\delta \dot q
=
-\Phi(x_s)^TJ
```

Then:

```math
\dot q^+
=
\dot q^-
+
\delta \dot q
```

Modal kinetic-energy change from the velocity update is:

```math
\Delta E_{\mathrm{modal,kin}}
=
(\dot q^-)^T\delta \dot q
+
\frac12
\delta \dot q^T\delta \dot q
```

Since:

```math
\delta \dot q = -\Phi^TJ
```

we get:

```math
\Delta E_{\mathrm{modal,kin}}
=
-(\dot q^-)^T\Phi^TJ
+
\frac12
J^T\Phi\Phi^TJ
```

The first term is the energy extracted from modal motion.

The second term is the cost of changing modal velocity.

If the impulse solve is consistent, then in an isolated no-gravity/no-damping exchange:

```math
\Delta E_{\mathrm{rigid}}
+
\Delta E_{\mathrm{modal}}
\le
0
```

For elastic exchange, it may be approximately conserved. For inelastic contact, it should decrease.

---

## Why this fixes the long-vibration problem

Without back-reaction:

```text
modal support pushes object
object gains kinetic energy
modal energy remains almost unchanged
modal support continues vibrating
object keeps receiving small kicks
```

With back-reaction:

```text
modal support pushes object
object gains kinetic energy
modal qdot is reduced
modal energy is drained
residual vibration decays faster
resting objects stop receiving repeated artificial kicks
```

So the fix is not merely visual damping.

It restores the missing energy path:

```text
modal support -> rigid body
```

---

## Minimal implementation rule

Every time the DCR/modal support applies an impulse to a rigid body, do this:

```python
# Forward support velocity used earlier:
v_s = Phi_x @ qdot

# Rigid impulse applied to object:
apply_impulse_to_rigid(body, J_support, contact_point)

# Mandatory modal back-reaction:
qdot -= Phi_x.T @ J_support
```

`Phi_x` must be the exact basis evaluation used to compute `v_s`.

---

## If the implementation currently applies velocity directly

If the current DCR path applies a velocity correction rather than an impulse:

```python
body.v += delta_v
```

then convert it to an equivalent impulse before applying back-reaction.

For pure linear COM velocity:

```math
J = m\Delta v
```

For point impulse with rotation:

```math
\Delta v_p = K_{\mathrm{body}}J
```

so:

```math
J = K_{\mathrm{body}}^{-1}\Delta v_p
```

Then apply:

```math
\dot q
\leftarrow
\dot q
-
\Phi(x_s)^TJ
```

Do not skip this conversion.

A direct velocity assignment without equivalent impulse cannot be debited correctly from the modal reservoir.

---

## Corrected persistent-modal DCR pipeline

```text
1. Rigid impact is solved.
2. Measure rigid kinetic-energy loss.
3. Project impact impulse into modal coordinates.
4. Apply bounded modal injection:
       qdot += α Φ(x_c)^T J_impact

5. Modal state evolves:
       q, qdot persist
       damping is applied

6. At support/contact point:
       u_s = Φ(x_s)q
       v_s = Φ(x_s)qdot

7. Contact response is computed.
       This may be:
           - DCR point impulse
           - patch impulse
           - AVBD moving-support contact impulse

8. Apply impulse J_support to rigid body.

9. Mandatory modal back-reaction:
       qdot -= Φ(x_s)^T J_support

10. Recompute E_modal.

11. Check energy ledger:
       E_rigid_gain_from_support <= E_modal_lost + tolerance
```

---

## AVBD-specific version

In AVBD-native DCR, the modal support should enter as a moving contact boundary.

Support position:

```math
x_s(q)
=
x_s^0
+
\Phi(x_s^0)q
```

Support velocity:

```math
v_s(q,\dot q)
=
\Phi(x_s^0)\dot q
```

AVBD solves for contact impulse:

```math
J_{\mathrm{support}}
```

Then apply the same back-reaction:

```math
\dot q
\leftarrow
\dot q
-
\Phi(x_s)^TJ_{\mathrm{support}}
```

This is cleaner than the old post-process DCR path because AVBD exposes a contact impulse generated by the moving support.

---

## Passivity condition

The moving support should not transfer more work than its available reservoir.

Support-to-rigid work:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
=
\max(0,\Delta E_{\mathrm{rigid}}(J_{\mathrm{support}}))
```

Budget:

```math
E_{\mathrm{budget}}
=
\beta E_{\mathrm{modal}}
```

Require:

```math
W_{\mathrm{support}\rightarrow\mathrm{rigid}}
\le
E_{\mathrm{budget}}
+
\epsilon
```

If violated, scale the impulse or support velocity:

```math
J_{\mathrm{support}}
\leftarrow
\gamma J_{\mathrm{support}}
```

with:

```math
\gamma\in[0,1]
```

until the work bound holds.

---

## Contact-visible support velocity

Even with correct back-reaction, raw persistent modal velocity may still cause visually annoying micro-jitter.

Use a contact-visible support velocity:

```math
v_s^{\mathrm{contact}}
=
G_c\Phi(x_s)\dot q
```

where:

```math
G_c\in[0,1]
```

Recommended gates:

```text
gap gate
closing velocity gate
modal energy threshold
resting-object suppression
visual support-velocity threshold
```

Important:

```text
The raw modal state q, qdot persists for energy accounting.
The contact-visible velocity can be filtered to avoid repeated tiny kicks.
```

---

## Required diagnostics

Log every step:

```text
E_modal_before_support_impulse
E_modal_after_support_impulse

E_rigid_before_support_impulse
E_rigid_after_support_impulse

J_support
||Phi_x.T @ J_support||

Delta_E_rigid_from_support
Delta_E_modal_from_backreaction

Energy_exchange_residual:
    Delta_E_rigid_from_support + Delta_E_modal_from_backreaction

support_work_budget
support_work_violation

num_support_impulses
num_backreaction_applications
```

If:

```text
num_support_impulses > num_backreaction_applications
```

then the implementation is wrong.

---

## Required unit tests

### Test 1: zero impulse does nothing

Input:

```math
J = 0
```

Expected:

```math
\dot q^+ = \dot q^-
```

and no energy change.

---

### Test 2: forward/reverse transpose consistency

Compute:

```math
v_s = \Phi\dot q
```

Apply impulse `J`.

Check virtual work identity:

```math
J^Tv_s
=
(\Phi^TJ)^T\dot q
```

Expected:

```text
match to numerical tolerance
```

This verifies that the same `Φ` is used both ways.

---

### Test 3: isolated exchange energy ledger

Setup:

```text
one rigid body
one modal support
one contact
no gravity
no damping
no external force
```

Apply support impulse and back-reaction.

Expected:

```math
\Delta E_{\mathrm{rigid}}
+
\Delta E_{\mathrm{modal}}
\le
\epsilon
```

If this fails, the support is creating energy.

---

### Test 4: direct velocity correction is converted to impulse

If a path uses:

```python
body.v += delta_v
```

then ensure the code also computes:

```math
J = m\Delta v
```

or:

```math
J = K_{\mathrm{body}}^{-1}\Delta v_p
```

and applies:

```math
qdot -= Phi_x.T @ J
```

Expected:

```text
no support velocity correction without modal debit
```

---

### Test 5: modal energy decreases after positive support work

When:

```math
\Delta E_{\mathrm{rigid}} > 0
```

due to support impulse, expect:

```math
E_{\mathrm{modal}}^{after}
<
E_{\mathrm{modal}}^{before}
```

unless the impulse is externally funded or explicitly marked as non-modal.

---

## Failure cases to catch

### Failure 1: rigid impulse without modal debit

Bad:

```python
apply_impulse_to_rigid(body, J)
# missing qdot -= Phi.T @ J
```

This creates energy.

---

### Failure 2: velocity assignment without equivalent impulse

Bad:

```python
body.v += delta_v
# no J computed
# no qdot debit
```

This makes energy accounting impossible.

---

### Failure 3: mismatched basis

Bad:

```python
v_s = Phi_contact @ qdot
qdot -= Phi_nearest_vertex.T @ J
```

Forward and reverse maps are not transposes.

---

### Failure 4: debiting after damping only

Bad:

```text
support gives energy to rigid
modal energy is not debited
later damping slowly removes modal energy
```

Damping is not a substitute for back-reaction.

---

### Failure 5: debiting only by scalar energy

Bad:

```python
E_modal -= Delta_E_rigid
```

Modal energy is not an independent scalar state. The real modal state is `q, qdot`. You must update `qdot`.

---

## Recommended implementation checklist

```text
[ ] Identify every place where modal/DCR support changes rigid velocity.
[ ] Convert each velocity correction into an impulse J.
[ ] For every such J, evaluate the exact Phi_x used for support velocity.
[ ] Apply qdot -= Phi_x.T @ J.
[ ] Recompute E_modal after the update.
[ ] Log Delta_E_rigid and Delta_E_modal.
[ ] Add transpose virtual-work test.
[ ] Add isolated no-gravity energy-ledger test.
[ ] Add assertion: every support impulse has one modal debit.
```

---

## Short version

The previous energy bound protects:

```text
rigid impact -> modal reservoir
```

The missing fix protects:

```text
modal reservoir -> rigid object
```

The required update is:

```math
\boxed{
\dot q
\leftarrow
\dot q
-
\Phi(x_s)^T J_{\mathrm{support}}
}
```

Without this, persistent modal DCR is not passive and the FEM mesh can keep kicking objects because its reservoir is not being drained correctly.
