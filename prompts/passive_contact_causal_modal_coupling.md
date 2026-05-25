# Passive Contact-Causal Modal Coupling Proposal

## Core Diagnosis

The problem is not primarily **how aggressively to quiet the slab**.

That framing is weak. The real issue is that the current coupling lets a weak residual modal state produce open-loop rigid-body kicks after the causal contact event is over.

The current formulation is effectively allowing the persistent modal state to behave like an open-loop kick generator.

That is not the desired behavior.

---

## Main Recommendation

Do **not** aggressively quiet the slab.

Keep the modal reservoir.

Replace the patch-kick dispatch rule with a **passive, contact-causal coupling rule**.

The slab is allowed to keep vibrating internally, but it is only allowed to affect rigid bodies when the modal motion is contact-causal, receiver-eligible, and energy-passive.

---

## Recommended Method: Contact-Causal Passive Modal Coupling

The slab is allowed to keep vibrating internally, but it is only allowed to affect rigid bodies when three conditions are true.

### 1. There is an actual nearby or active receiver contact

The object must be touching, or within a small contact shell of the slab.

$$
g_c \le \delta_{\text{contact}}
$$

where:

- $g_c$ is the contact gap at receiver/contact point $c$.
- $\delta_{\text{contact}}$ is a small contact-shell tolerance.

If the object is not near the slab, the slab should not fire any rigid-body response into it.

---

### 2. The modal surface is moving into the rigid body

Let the modal normal velocity at contact point $c$ be:

$$
v_m(c) = \mathbf n_c^T \Phi(c)\dot{\mathbf q}
$$

Let the rigid body's contact-point normal velocity be:

$$
v_b(c) = \mathbf n_c^T \mathbf v_{\text{body}}(c)
$$

Only inject if the slab is closing the gap:

$$
v_m(c) - v_b(c) > v_{\min}
$$

If the slab is moving downward, sideways, or only producing tiny solver-noise motion, it does nothing.

This is the important conceptual correction: the slab is not allowed to inject just because it still contains modal energy. It can only inject when its motion is mechanically relevant to an active or near-active contact.

---

### 3. The outgoing impulse must be energy-debited from the modal reservoir

If a body impulse $J_c$ is applied, subtract the equal-and-opposite generalized impulse from the modal state:

$$
\dot{\mathbf q}
\leftarrow
\dot{\mathbf q}
-
J_c \Phi(c)^T \mathbf n_c
$$

Then clamp $J_c$ so that the modal energy never goes negative and the total transfer stays passive:

$$
\Delta E_{\text{body}} \le \eta E_{\text{modal}}
$$

where $\eta$ is a per-timestep transfer fraction, for example:

$$
\eta \in [0.05, 0.2]
$$

This changes the interpretation from:

> The slab has residual vibration, so it keeps firing DCR kicks.

into:

> The slab is a passive moving boundary. It can only push objects when it is actually moving into them, and whatever energy it gives them is removed from the modal reservoir.

---

## The Key Design Change

The current branch sounds like it has this structure:

$$
E_{\text{modal}} > 0
\quad \Rightarrow \quad
\text{dispatch patch kick}
$$

That is too simple and too aggressive. It lets tiny leftover modal energy become visible rigid-body artifacts.

Replace it with:

$$
\text{active receiver contact}
\;\land\;
\text{positive modal closing velocity}
\;\land\;
\text{passivity budget available}
\quad \Rightarrow \quad
\text{apply impulse}
$$

This is much better than quieting.

---

## How Aggressive Should Slab-Quieting Be?

Almost not aggressive at all.

For the research branch, do **not** use a 1% modal-energy cutoff as the main solution. That is arbitrary and reviewer-vulnerable.

A reviewer can ask:

> Why 1%? Why not 0.1% or 5%?

There is no strong principled answer except that it looked better.

Use only a tiny numerical cutoff for computation, not physics:

$$
E_{\text{modal}} < 10^{-5} E_{\text{peak}}
$$

or:

$$
E_{\text{modal}} < 10^{-6} E_{\text{injected,total}}
$$

At that point, the cutoff is not changing the physical model. It is saying the remaining energy is below numerical or visual significance.

The real visual stabilization should come from **receiver-side eligibility**, not slab-side deletion.

---

## Better Threshold: Contact-Mechanical Deadband

Instead of an arbitrary energy cutoff, use a deadband based on whether the modal motion can actually create observable separation.

A clean threshold is:

$$
v_{\min} = \sqrt{2g\delta_{\text{slop}}}
$$

where:

- $g$ is gravitational acceleration.
- $\delta_{\text{slop}}$ is the contact tolerance or solver slop.

Example:

$$
\delta_{\text{slop}} = 10^{-4}\ \text{m}
$$

Then:

$$
v_{\min}
\approx
\sqrt{2(9.81)(10^{-4})}
\approx
0.044\ \text{m/s}
$$

Meaning: if the modal surface velocity cannot even lift the object above contact slop, do not inject a visible kick.

This is much more defensible than saying “quiet when energy is below 1%.”

---

## Concrete Algorithm

For each rigid timestep:

```cpp
// Modal state persists. Do NOT reset q or qdot.
integrateModalState(q, qdot, impacts, dt);

// For each rigid body / patch receiver:
for each receiver contact c:
    g = contact_gap(c);

    if (g > contact_shell)
        continue;

    n = contact_normal(c);

    v_modal = dot(n, Phi(c) * qdot);
    v_body  = dot(n, body_point_velocity(c));

    closing = v_modal - v_body;

    if (closing <= v_min)
        continue;

    m_eff = effective_mass_along_normal(body, c, n);

    // Candidate impulse needed to match modal surface velocity.
    J = coupling_strength * m_eff * closing;

    // Energy budget clamp.
    E_modal_before = modalEnergy(q, qdot);
    J = clampByModalEnergyBudget(J, E_modal_before, eta);

    if (J <= 0)
        continue;

    // Apply to rigid body.
    applyImpulse(body, c, J * n);

    // Debit modal reservoir with equal-and-opposite generalized impulse.
    qdot -= J * transpose(Phi(c)) * n;

    // Optional safety line search to enforce passivity exactly.
    enforceNoEnergyCreation(q, qdot, body_state_before, body_state_after);
```

---

## What This Fixes

| Problem | Previous fixes | Proposed fix |
|---|---|---|
| Residual slab state keeps bumping books | Kill, damp, or threshold slab | Prevent illegal receiver coupling |
| Energy reservoir needs to persist | Resetting breaks it | Reservoir persists |
| Visual jitter after impact | Arbitrary cutoff | Contact-mechanical deadband |
| Reviewer asks “why this threshold?” | Weak answer | Threshold tied to contact slop, lift height, and passivity |
| Physical meaning | Questionable | Slab behaves like passive moving boundary |

---

## Paper-Framing Sentence

> Unlike the original DCR formulation, which estimates a per-step displacement response and applies an open-loop velocity correction, our persistent modal formulation treats the reduced deformable substrate as a passive moving boundary. Rigid bodies receive modal impulses only through active or near-active contacts, only when modal motion closes the contact gap, and only under an explicit modal energy budget.

---

## Bottom Line
This proposed method is a real theory improvement:

**Passive contact-causal modal coupling with receiver-side deadband and modal energy debit.**

The slab should not be aggressively quieted. The coupling should be made more physically selective and energy-passive.

That is the clean fix.
