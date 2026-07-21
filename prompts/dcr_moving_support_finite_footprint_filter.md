# DCR Moving-Support Tilt Artifact: Finite-Footprint Support Filtering Fix

## 1. Updated Diagnosis

The earlier contact-compatible projection fixed a real degree of freedom, but it did not reduce the dominant visible tilt.

The projection correctly removes spurious angular velocity injected by the DCR patch kick:

\[
\Delta \mathbf{u}_{\text{raw}}
\rightarrow
\Delta \mathbf{u}_{\text{proj}},
\]

where

\[
\Delta \mathbf{u}
=
\begin{bmatrix}
\Delta \mathbf{v} \\
\Delta \boldsymbol{\omega}
\end{bmatrix}.
\]

Direct measurement confirmed that the projection can kill per-kick angular velocity injections, for example reducing an observed kick of approximately

\[
2.22 \ \text{rad/s}
\]

down to roughly

\[
10^{-9} \ \text{rad/s}.
\]

The linear velocity increment \(\Delta \mathbf{v}\) is preserved, and yaw can survive when it lies in the contact null-space.

However, the macro tilt did not change. That means the dominant visible tilt is not caused by the direct DCR angular kick.

The remaining tilt comes from a different channel:

\[
\text{modal geometry deformation}
\rightarrow
\text{moving support surface}
\rightarrow
\text{AVBD contact solve}
\rightarrow
\text{rigid-body rotation}.
\]

This is different from the old assumed mechanism:

\[
\text{DCR patch kick}
\rightarrow
\Delta \boldsymbol{\omega}.
\]

Therefore:

- The patch-kick projection is mathematically correct.
- It fixes a real but non-dominant artifact.
- The visible tilt is mainly caused by the slab physically bending under the object.
- AVBD rotates the resting rigid body to maintain contact with the moving, deforming support surface.

---

## 2. Why Lowering \(\gamma\) Is Not a Research Fix

The visible tilt scales with the modal decay parameter \(\gamma\), because \(\gamma\) controls how long the slab keeps bending.

A simple decay update can be interpreted as

\[
q_k(t+h) \leftarrow \gamma q_k(t+h),
\]

or similarly,

\[
\dot q_k(t+h) \leftarrow \gamma \dot q_k(t+h).
\]

Lowering \(\gamma\) reduces the visible tilt because it damps the modal vibration faster.

But this is not a strong algorithmic fix unless it is explicitly justified as physical modal damping.

The trap is:

\[
\text{lower } \gamma
\neq
\text{correct moving-support coupling}.
\]

Lowering \(\gamma\) reduces everything:

\[
\text{modal vibration},
\quad
\text{rattle},
\quad
\text{support deformation},
\quad
\text{DCR response duration}.
\]

It is useful as a diagnostic knob. It is weak as the main method.

A better fix should preserve the useful distant response while preventing thin resting objects from conforming to unresolved or exaggerated modal curvature.

---

## 3. Correct Algorithmic Direction

The correct fix is:

> Replace raw pointwise moving support with a finite-footprint effective support surface for thin resting bodies.

The contact solver should not force a thin rigid utensil to conform to every oscillating local deformation of the slab.

Instead, the object should see an averaged support patch.

The goal is:

\[
\text{keep mean support motion}
\quad
\text{but suppress unresolved patch-scale slope/curvature}.
\]

This means the object can still rattle, bounce, or slide, but it should not be forced to tilt just because the reduced modal slab surface has local bending across a small contact patch.

---

## 4. Raw Moving Support Formulation

The deformed support surface is currently represented as

\[
\mathbf{x}_{\text{surface}}(\mathbf{X}, t)
=
\mathbf{X}
+
\mathbf{u}(\mathbf{X}, t),
\]

where the modal displacement is

\[
\mathbf{u}(\mathbf{X}, t)
=
\sum_k \boldsymbol{\phi}_k(\mathbf{X}) q_k(t).
\]

Here:

- \(\mathbf{X}\) is a rest-space or undeformed surface point.
- \(\boldsymbol{\phi}_k(\mathbf{X})\) is the \(k\)-th mode shape evaluated at \(\mathbf{X}\).
- \(q_k(t)\) is the modal coordinate.

The modal velocity field is

\[
\dot{\mathbf{u}}(\mathbf{X}, t)
=
\sum_k \boldsymbol{\phi}_k(\mathbf{X}) \dot q_k(t).
\]

For a contact patch with sample points \(\mathbf{x}_i\), the raw support displacement is

\[
\mathbf{u}_i
=
\mathbf{u}(\mathbf{x}_i, t).
\]

The contact solver then sees deformed support points

\[
\mathbf{x}_i + \mathbf{u}_i.
\]

If the modal surface bends across the patch, AVBD tries to rotate the rigid body so the body remains in contact with the bent support surface.

This is why visible tilt can occur even when the DCR patch kick gives zero angular velocity.

---

## 5. Finite-Footprint Support Filtering

Instead of using the raw support displacement \(\mathbf{u}_i\), define a filtered support displacement

\[
\tilde{\mathbf{u}}_i.
\]

For a contact patch with \(N\) samples, define the mean contact position:

\[
\bar{\mathbf{x}}
=
\frac{1}{N}
\sum_{i=1}^{N}
\mathbf{x}_i.
\]

Define the mean modal displacement over the patch:

\[
\bar{\mathbf{u}}
=
\frac{1}{N}
\sum_{i=1}^{N}
\mathbf{u}_i.
\]

Then approximate the local support deformation using a filtered affine model:

\[
\tilde{\mathbf{u}}_i
=
\bar{\mathbf{u}}
+
\beta A(\mathbf{x}_i - \bar{\mathbf{x}}).
\]

Here:

- \(\bar{\mathbf{u}}\) preserves the coherent mean motion of the support patch.
- \(A\) captures the best-fit local deformation gradient.
- \(\beta\) controls how much local slope/curvature is allowed to affect the rigid body.

The key parameter is

\[
\beta \in [0,1].
\]

For thin stable resting objects, use

\[
\beta \approx 0.
\]

For tall, unstable, or genuinely tipping objects, use

\[
\beta \approx 1.
\]

When \(\beta = 0\), the support patch moves coherently:

\[
\tilde{\mathbf{u}}_i
=
\bar{\mathbf{u}}.
\]

When \(\beta = 1\), the support keeps the full best-fit local affine deformation:

\[
\tilde{\mathbf{u}}_i
=
\bar{\mathbf{u}}
+
A(\mathbf{x}_i - \bar{\mathbf{x}}).
\]

---

## 6. Best-Fit Local Affine Deformation

The best-fit affine deformation \(A\) is computed by minimizing

\[
A^*
=
\arg\min_A
\sum_i
w_i
\left\|
\mathbf{u}_i
-
\bar{\mathbf{u}}
-
A(\mathbf{x}_i - \bar{\mathbf{x}})
\right\|^2.
\]

Let

\[
\mathbf{p}_i = \mathbf{x}_i - \bar{\mathbf{x}},
\]

and

\[
\mathbf{d}_i = \mathbf{u}_i - \bar{\mathbf{u}}.
\]

Then the minimization becomes

\[
A^*
=
\arg\min_A
\sum_i
w_i
\left\|
\mathbf{d}_i - A\mathbf{p}_i
\right\|^2.
\]

The normal equations give

\[
A^*
\left(
\sum_i w_i \mathbf{p}_i \mathbf{p}_i^T
\right)
=
\sum_i w_i \mathbf{d}_i \mathbf{p}_i^T.
\]

Therefore,

\[
A^*
=
\left(
\sum_i w_i \mathbf{d}_i \mathbf{p}_i^T
\right)
\left(
\sum_i w_i \mathbf{p}_i \mathbf{p}_i^T
+
\epsilon I
\right)^{-1}.
\]

Here \(\epsilon I\) is a small regularization term.

A reasonable range is

\[
\epsilon \in [10^{-8}, 10^{-5}],
\]

depending on scene units and patch conditioning.

---

## 7. Filtered Support Velocity

The same filtering should be applied to modal support velocity, otherwise the geometry and velocity are inconsistent.

For each patch point, raw modal support velocity is

\[
\dot{\mathbf{u}}_i
=
\dot{\mathbf{u}}(\mathbf{x}_i,t)
=
\sum_k \boldsymbol{\phi}_k(\mathbf{x}_i)\dot q_k(t).
\]

Define mean velocity:

\[
\bar{\dot{\mathbf{u}}}
=
\frac{1}{N}
\sum_i
\dot{\mathbf{u}}_i.
\]

Compute a best-fit velocity gradient \(\dot A\):

\[
\dot A^*
=
\arg\min_{\dot A}
\sum_i
w_i
\left\|
\dot{\mathbf{u}}_i
-
\bar{\dot{\mathbf{u}}}
-
\dot A(\mathbf{x}_i - \bar{\mathbf{x}})
\right\|^2.
\]

Then use

\[
\dot{\tilde{\mathbf{u}}}_i
=
\bar{\dot{\mathbf{u}}}
+
\beta \dot A^*(\mathbf{x}_i-\bar{\mathbf{x}}).
\]

This gives a consistent filtered moving support:

\[
\mathbf{x}_i + \tilde{\mathbf{u}}_i,
\]

with velocity

\[
\dot{\tilde{\mathbf{u}}}_i.
\]

---

## 8. How This Differs From Just Lowering \(\gamma\)

Lowering \(\gamma\) damps the entire modal state:

\[
q_k \rightarrow \gamma q_k,
\]

\[
\dot q_k \rightarrow \gamma \dot q_k.
\]

That reduces all modal effects.

Finite-footprint support filtering instead modifies how the modal surface is exposed to a stable resting contact patch:

\[
\mathbf{u}_i
\rightarrow
\tilde{\mathbf{u}}_i.
\]

The modal state still exists. The table still vibrates. DCR still has energy. The rigid body simply does not conform to every local patch-scale modal bend.

So the difference is:

\[
\text{modal damping: modifies the modal state},
\]

while

\[
\text{support filtering: modifies contact coupling to the modal state}.
\]

This is a much stronger research argument.

---

## 9. Practical Gate

Do not apply support filtering to every contact. That would over-stabilize the simulation and remove valid toppling behavior.

Use it only for thin, stable, resting area contacts.

A practical gate is:

```python
thin_body = half_y / max(half_x, half_z) < 0.25
stable_patch = num_patch_points >= 3
resting = abs(v_normal) < v_n_thresh and norm(v_tangent) < v_t_thresh
com_supported = com_projection_inside_patch_or_nearby

use_support_filter = thin_body and stable_patch and resting and com_supported
```

The thin-body test is

\[
\frac{h_y}{\max(h_x,h_z)} < 0.25,
\]

where \(h_x,h_y,h_z\) are body half-extents.

Require enough contact samples:

\[
N_{\text{patch}} \ge 3.
\]

Require near-zero normal velocity:

\[
|v_n| < v_{n,\text{thresh}}.
\]

Require near-zero tangential velocity for stable sticking contacts:

\[
\|\mathbf{v}_t\| < v_{t,\text{thresh}}.
\]

Require the center of mass projection to be supported by the patch:

\[
\mathbf{x}_{\text{COM projection}} \in \text{contact patch},
\]

or at least near it.

This prevents suppressing valid edge tipping.

---

## 10. Choosing \(\beta\)

The simplest implementation is binary:

```python
if use_support_filter:
    beta = 0.0
else:
    beta = 1.0
```

That means:

- Thin stable resting utensils get mean support motion only.
- Tall or unstable bodies see the full moving support.

A smoother version is preferable later:

\[
\beta
=
\operatorname{clamp}
\left(
\frac{h_y}{\alpha \max(h_x,h_z)},
0,
1
\right).
\]

Here \(\alpha\) controls how quickly bodies transition from thin object to tall object.

For example:

\[
\alpha \in [0.25, 0.5].
\]

Thin bodies get low \(\beta\). Tall bodies get high \(\beta\).

Another option is to make \(\beta\) depend on patch stability:

\[
\beta
=
\beta_{\text{shape}}
\cdot
\beta_{\text{motion}},
\]

where

\[
\beta_{\text{shape}}
=
\operatorname{clamp}
\left(
\frac{h_y}{\alpha \max(h_x,h_z)},
0,
1
\right),
\]

and

\[
\beta_{\text{motion}}
=
\operatorname{clamp}
\left(
\frac{\|\mathbf{v}_t\|}{v_{t,\text{thresh}}},
0,
1
\right).
\]

This means fast-moving or sliding bodies recover more of the raw support deformation.

---

## 11. Keep the Patch-Kick Projection

The earlier contact-compatible projection still matters. It solves a separate problem.

The projection handles this channel:

\[
\text{DCR patch kick}
\rightarrow
\Delta \boldsymbol{\omega}.
\]

The support filter handles this channel:

\[
\text{modal support geometry}
\rightarrow
\text{AVBD contact solve}
\rightarrow
\text{rigid-body rotation}.
\]

They are complementary.

The full corrected pipeline should be:

\[
\text{modal state}
\rightarrow
\begin{cases}
\text{filtered support geometry for contact solve}, \\
\text{projected DCR patch kick},
\end{cases}
\rightarrow
\text{AVBD}
\rightarrow
\text{passive energy accounting}.
\]

In words:

- The projection fixes contact-incompatible DCR velocity transfer.
- The support filter fixes moving-surface tilt.
- Modal damping controls vibration lifetime.

These should be evaluated separately.

---

## 12. Recommended Modes for Testing

Implement four comparison modes:

```text
mode 0: raw moving support + no projection

mode 1: raw moving support + DCR kick projection

mode 2: filtered support + DCR kick projection

mode 3: filtered support + DCR kick projection + physical modal damping
```

Expected outcomes:

```text
projection only:
    should kill injected angular kicks
    may not reduce macro tilt

support filtering:
    should reduce macro tilt

modal damping:
    should reduce duration of visible motion
```

This separation is important. It prevents confusing three different effects.

---

## 13. Metrics

Measure roll:

\[
\max_t |\theta_{\text{roll}}(t)|.
\]

Measure pitch:

\[
\max_t |\theta_{\text{pitch}}(t)|.
\]

Measure yaw rate:

\[
\max_t |\omega_{\text{yaw}}(t)|.
\]

Measure modal energy:

\[
E_{\text{modal}}
=
\frac{1}{2}
\dot{\mathbf{q}}^T
M_q
\dot{\mathbf{q}}
+
\frac{1}{2}
\mathbf{q}^T
K_q
\mathbf{q}.
\]

If the modal basis is mass-normalized and diagonalized, this becomes

\[
E_{\text{modal}}
=
\frac{1}{2}
\sum_k
\left(
\dot q_k^2
+
\omega_k^2 q_k^2
\right).
\]

Measure rigid-body kinetic energy:

\[
E_{\text{rigid}}
=
\frac{1}{2}m\|\mathbf{v}\|^2
+
\frac{1}{2}
\boldsymbol{\omega}^T
I_{\text{world}}
\boldsymbol{\omega}.
\]

Measure support-filter removal:

\[
E_{\text{removed support}}
=
\sum_i
w_i
\left\|
\mathbf{u}_i - \tilde{\mathbf{u}}_i
\right\|^2.
\]

This is not physical energy by itself, but it is a useful diagnostic of how much deformation the contact interface filtered.

Also measure velocity filtering:

\[
V_{\text{removed support}}
=
\sum_i
w_i
\left\|
\dot{\mathbf{u}}_i - \dot{\tilde{\mathbf{u}}}_i
\right\|^2.
\]

---

## 14. Pseudocode: Best-Fit Affine Filter

```python
def best_fit_affine_filter(
    x_points,      # list/array of contact sample positions, shape (N, 3)
    u_points,      # modal displacements at x_points, shape (N, 3)
    beta,          # support slope retention, in [0, 1]
    weights=None,
    eps=1e-7,
):
    N = len(x_points)

    if weights is None:
        weights = np.ones(N)

    x_bar = weighted_mean(x_points, weights)
    u_bar = weighted_mean(u_points, weights)

    P = np.zeros((3, 3))
    B = np.zeros((3, 3))

    for i in range(N):
        p_i = x_points[i] - x_bar
        d_i = u_points[i] - u_bar
        w_i = weights[i]

        P += w_i * np.outer(p_i, p_i)
        B += w_i * np.outer(d_i, p_i)

    A = B @ np.linalg.inv(P + eps * np.eye(3))

    u_filtered = []
    for i in range(N):
        p_i = x_points[i] - x_bar
        u_tilde_i = u_bar + beta * (A @ p_i)
        u_filtered.append(u_tilde_i)

    return np.array(u_filtered), A, u_bar
```

---

## 15. Pseudocode: Support Geometry Replacement

```python
def compute_filtered_support_patch(
    contact_patch,
    modal_state,
    body,
):
    x_points = contact_patch.points

    u_points = []
    udot_points = []

    for x_i in x_points:
        u_i = eval_modal_displacement(x_i, modal_state)
        udot_i = eval_modal_velocity(x_i, modal_state)

        u_points.append(u_i)
        udot_points.append(udot_i)

    if should_use_support_filter(body, contact_patch):
        beta = compute_beta(body, contact_patch)
    else:
        beta = 1.0

    u_filtered, A, u_bar = best_fit_affine_filter(
        x_points=x_points,
        u_points=u_points,
        beta=beta,
    )

    udot_filtered, Adot, udot_bar = best_fit_affine_filter(
        x_points=x_points,
        u_points=udot_points,
        beta=beta,
    )

    filtered_support_positions = []
    for i, x_i in enumerate(x_points):
        filtered_support_positions.append(x_i + u_filtered[i])

    return filtered_support_positions, udot_filtered
```

---

## 16. Pseudocode: Gate and \(\beta\)

```python
def should_use_support_filter(body, contact_patch):
    hx, hy, hz = body.half_extents

    thin_body = hy / max(hx, hz) < 0.25
    stable_patch = len(contact_patch.points) >= 3

    v_normal = contact_patch.relative_normal_velocity
    v_tangent = contact_patch.relative_tangent_velocity

    resting = (
        abs(v_normal) < body.params.v_n_thresh and
        np.linalg.norm(v_tangent) < body.params.v_t_thresh
    )

    com_supported = contact_patch.contains_or_near(
        project_to_contact_plane(body.com_world)
    )

    return thin_body and stable_patch and resting and com_supported
```

```python
def compute_beta(body, contact_patch):
    hx, hy, hz = body.half_extents

    alpha = 0.35

    beta_shape = hy / (alpha * max(hx, hz))
    beta_shape = np.clip(beta_shape, 0.0, 1.0)

    v_t = np.linalg.norm(contact_patch.relative_tangent_velocity)
    beta_motion = np.clip(v_t / body.params.v_t_thresh, 0.0, 1.0)

    # Conservative first version:
    # return 0.0 if should_use_support_filter(body, contact_patch) else 1.0

    # Smooth version:
    return beta_shape * beta_motion
```

For the first implementation, use the binary version:

\[
\beta =
\begin{cases}
0, & \text{thin stable resting patch}, \\
1, & \text{otherwise}.
\end{cases}
\]

That is easier to debug.

---

## 17. What Not To Do

### Do Not Use Post-AVBD Angular Damping as the Main Fix

A post-solve angular damper would look like:

\[
\boldsymbol{\omega}
\leftarrow
(1-\lambda)
\boldsymbol{\omega}.
\]

Or, for roll/pitch only:

\[
\boldsymbol{\omega}_{rp}
\leftarrow
(1-\lambda)
\boldsymbol{\omega}_{rp}.
\]

This can reduce visible tilt, but it is a demo hack.

Problems:

- It may remove valid toppling.
- It hides the actual coupling issue.
- It is difficult to justify as a physically meaningful DCR extension.
- It can fight AVBD instead of improving the contact model.

Use angular damping only as an optional emergency stabilizer, not as the paper method.

### Do Not Claim \(\gamma\) Alone Is the Fix

Lowering \(\gamma\) may be visually effective, but by itself it is parameter tuning.

It can be part of the method only if framed as physical modal damping, for example:

\[
\ddot q_k
+
2\zeta_k \omega_k \dot q_k
+
\omega_k^2 q_k
=
f_k(t).
\]

Then \(\gamma\) should correspond to a damping ratio \(\zeta_k\), not an arbitrary visual knob.

For time step \(h\), a decay factor can be related to damping approximately as

\[
\gamma_k
\approx
 e^{-\zeta_k \omega_k h}.
\]

That is a defensible physical interpretation.

---

## 18. Strong Research Framing

The stronger framing is:

> The DCR patch-kick projection removes contact-incompatible velocity transfer, while finite-footprint support filtering prevents thin resting bodies from conforming to unresolved modal curvature of the vibrating support.

This gives a clean separation:

\[
\text{projection}
=
\text{velocity-transfer correction},
\]

\[
\text{support filtering}
=
\text{moving-geometry contact correction},
\]

\[
\text{modal damping}
=
\text{physical vibration lifetime control}.
\]

This is much stronger than saying:

> Lower \(\gamma\) until the tilt looks okay.

---

## 19. Final Recommendation

The next real fix should be finite-footprint support filtering.

The implementation priority should be:

1. Keep the existing contact-compatible DCR patch-kick projection.
2. Add finite-footprint support filtering for thin stable resting contacts.
3. Start with binary \(\beta\):

\[
\beta = 0
\]

for thin stable resting patches, and

\[
\beta = 1
\]

otherwise.

4. Apply the same filtering to both support displacement and support velocity.
5. Compare against raw moving support and projection-only modes.
6. Only after that, tune physical modal damping using a justified \(\zeta_k\) or \(\gamma_k\).

The concise algorithmic statement is:

> DCR should expose a finite-footprint effective support surface to stable area contacts, not raw pointwise modal curvature that forces thin rigid bodies to tilt with every local bend of the reduced support.
