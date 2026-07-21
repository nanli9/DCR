# DCR Patch-Kick Tilt Artifact: Contact-Compatible Null-Space Projection Fix

## 1. Problem Summary

The observed utensil tilt is not caused by the deformable mesh itself. When the DCR modal coupling is disabled, for example with

\[
\eta = 0,
\]

the tilt disappears. As \(\eta\) increases, the tilt scales approximately linearly. Therefore, the artifact comes from the DCR coupling.

The current DCR coupling applies a modal-response kick at the contact patch centroid. For a thin body resting on a table, the patch centroid is usually on the bottom face, below the center of mass. If the kick contains any tangential component, that offset creates an angular impulse:

\[
\boldsymbol{\tau} = \mathbf{r} \times \mathbf{F},
\]

where

\[
\mathbf{r} = \mathbf{x}_{\text{patch}} - \mathbf{x}_{\text{COM}}.
\]

For a thin utensil, \(\|\mathbf{r}\|\) may only be around \(5\text{ mm}\), but the moment of inertia is also small. A light body with mass around \(60\text{ g}\) and low rotational inertia can visibly tilt or yaw from a small angular impulse.

This is not purely a numerical bug. It is the DCR coupling transferring modal energy into nearby rigid bodies. However, the *point-patch approximation* is too crude for stable area contacts.

The bad part is not that DCR transfers energy. The bad part is that a stable resting area contact is treated as a point contact, so the induced kick can contain contact-incompatible angular velocity.

---

## 2. Why Simple Parameter Tuning Is Not Enough

Reducing \(\eta\), reducing \(\gamma\), increasing utensil mass, or changing body thickness can reduce the visible artifact, but these are not real algorithmic fixes.

For example:

| Knob | Effect | Problem |
|---|---|---|
| Lower \(\eta\) | Reduces modal energy injection | Weakens the DCR effect itself |
| Lower \(\gamma\) | Reduces visible kick magnitude | Hides the symptom, not the mechanism |
| Increase utensil mass | Reduces angular response | Changes the physical scene |
| Make utensils thicker | Increases rotational robustness | Looks unrealistic |
| Move all kicks to COM | Removes torque for flat objects | Kills legitimate toppling for tall objects |

The important point:

\[
\text{smaller kick} \neq \text{correct coupling}.
\]

A real fix should preserve DCR energy transfer while preventing stable resting contacts from receiving fake differential patch motion.

---

## 3. Correct Direction

The correct algorithmic fix is:

> Keep the DCR energy transfer, but project the induced rigid-body kick into the null-space of stable resting contact so the patch moves coherently instead of twisting from a fake point impulse.

The current pipeline is effectively:

\[
\text{modal patch velocity}
\rightarrow
\text{point kick at centroid}
\rightarrow
(\Delta \mathbf{v}, \Delta \boldsymbol{\omega}).
\]

The fixed version should be:

\[
\text{modal patch velocity}
\rightarrow
\text{area-compatible patch kick}
\rightarrow
\text{contact null-space projection}
\rightarrow
\text{passivity cap}
\rightarrow
(\Delta \mathbf{v}, \Delta \boldsymbol{\omega}).
\]

---

## 4. Generalized Velocity Representation

Represent the rigid-body velocity increment as a generalized velocity:

\[
\Delta \mathbf{u}
=
\begin{bmatrix}
\Delta \mathbf{v} \\
\Delta \boldsymbol{\omega}
\end{bmatrix},
\]

where

\[
\Delta \mathbf{v} \in \mathbb{R}^3
\]

is the linear velocity increment, and

\[
\Delta \boldsymbol{\omega} \in \mathbb{R}^3
\]

is the angular velocity increment.

For a sampled contact point \(\mathbf{x}_i\) on the contact polygon, define the lever arm:

\[
\mathbf{r}_i = \mathbf{x}_i - \mathbf{x}_{\text{COM}}.
\]

The velocity induced at this point by the generalized velocity increment is

\[
\Delta \mathbf{v}_i
=
\Delta \mathbf{v}
+
\Delta \boldsymbol{\omega} \times \mathbf{r}_i.
\]

This can be written using a point-velocity Jacobian:

\[
\Delta \mathbf{v}_i = J_i \Delta \mathbf{u},
\]

with

\[
J_i =
\begin{bmatrix}
I & -[\mathbf{r}_i]_{\times}
\end{bmatrix}.
\]

Here, \([\mathbf{r}_i]_{\times}\) is the skew-symmetric cross-product matrix such that

\[
[\mathbf{r}_i]_{\times}\mathbf{a}
=
\mathbf{r}_i \times \mathbf{a}.
\]

The sign convention follows:

\[
\Delta \boldsymbol{\omega} \times \mathbf{r}_i
=
-[\mathbf{r}_i]_{\times}\Delta \boldsymbol{\omega}.
\]

---

## 5. Mean Patch Motion

For an area contact, the body should not be driven by only one centroid sample. Instead, use several samples over the contact polygon.

For \(N\) contact samples, define the mean patch Jacobian:

\[
\bar{J}
=
\frac{1}{N}
\sum_{i=1}^{N} J_i.
\]

The mean patch velocity increment is then

\[
\Delta \bar{\mathbf{v}}
=
\bar{J}\Delta \mathbf{u}.
\]

For a stable flat resting contact, the physically acceptable DCR kick should mostly move the entire patch coherently. It should not make one side of the patch move up while the other side moves down.

So the relevant quantity is not the absolute point velocity, but the differential velocity relative to the patch mean:

\[
\Delta \mathbf{v}_i - \Delta \bar{\mathbf{v}}
=
(J_i - \bar{J})\Delta \mathbf{u}.
\]

---

## 6. Normal Differential Constraint

Let \(\mathbf{n}\) be the contact normal. For a stable resting patch, require the normal differential velocity to vanish or be strongly suppressed:

\[
\mathbf{n}^T (J_i - \bar{J})\Delta \mathbf{u} = 0.
\]

This means that all contact sample points receive the same normal velocity as the patch mean. This prevents artificial pitch or roll where one side of the utensil is lifted by the DCR kick.

Define each normal differential constraint row as

\[
D_i^{(n)}
=
\mathbf{n}^T (J_i - \bar{J}).
\]

Stacking the rows gives

\[
D_n \Delta \mathbf{u} = 0.
\]

This is the minimal projection worth implementing first.

---

## 7. Optional Tangential Differential Constraints

If yaw or spin artifacts remain, also suppress tangential differential motion. Let \(\mathbf{t}_1\) and \(\mathbf{t}_2\) be two orthonormal tangent directions spanning the contact plane.

Then add:

\[
\mathbf{t}_1^T (J_i - \bar{J})\Delta \mathbf{u} = 0,
\]

\[
\mathbf{t}_2^T (J_i - \bar{J})\Delta \mathbf{u} = 0.
\]

The corresponding rows are

\[
D_i^{(t_1)}
=
\mathbf{t}_1^T (J_i - \bar{J}),
\]

\[
D_i^{(t_2)}
=
\mathbf{t}_2^T (J_i - \bar{J}).
\]

However, these tangential rows should not be applied unconditionally. They can suppress legitimate sliding, rattling, and frictional response.

Use tangential rows only when the object is in a sticking or nearly resting state.

A weighted version is preferable:

\[
D =
\begin{bmatrix}
D_n \\
\sqrt{w_t}D_{t_1} \\
\sqrt{w_t}D_{t_2}
\end{bmatrix},
\]

where

\[
w_t \in [0.1, 0.5].
\]

Start with \(w_t = 0\), then increase only if yaw artifacts remain.

---

## 8. Mass-Metric Projection

The raw DCR kick gives a generalized velocity increment:

\[
\Delta \mathbf{u}_{\text{raw}}.
\]

We want the closest contact-compatible velocity increment in the mass metric:

\[
\Delta \mathbf{u}_{\text{proj}}
=
\arg\min_{\Delta \mathbf{u}}
\frac{1}{2}
(\Delta \mathbf{u} - \Delta \mathbf{u}_{\text{raw}})^T
M
(\Delta \mathbf{u} - \Delta \mathbf{u}_{\text{raw}})
\]

subject to

\[
D\Delta \mathbf{u} = 0.
\]

The rigid-body mass matrix is

\[
M =
\begin{bmatrix}
mI & 0 \\
0 & I_{\text{world}}
\end{bmatrix},
\]

where \(m\) is the body mass and \(I_{\text{world}}\) is the world-space inertia tensor.

The closed-form projection is

\[
\Delta \mathbf{u}_{\text{proj}}
=
\Delta \mathbf{u}_{\text{raw}}
-
M^{-1}D^T
\left(
D M^{-1}D^T + \epsilon I
\right)^{-1}
D \Delta \mathbf{u}_{\text{raw}}.
\]

Here \(\epsilon I\) is a small regularization term for numerical robustness.

Use something like

\[
\epsilon \in [10^{-8}, 10^{-5}]
\]

depending on units and conditioning.

---

## 9. Why This Preserves the Passivity Bound

The projection removes components from the raw kick. In the ideal mass-metric case, the projected update has no more kinetic energy than the original update:

\[
\|\Delta \mathbf{u}_{\text{proj}}\|_M
\le
\|\Delta \mathbf{u}_{\text{raw}}\|_M.
\]

where

\[
\|\Delta \mathbf{u}\|_M^2
=
\Delta \mathbf{u}^T M \Delta \mathbf{u}.
\]

Therefore, projection should not violate the passive-energy bound. It only removes contact-incompatible components.

However, for implementation safety, still recompute the actual kinetic energy after projection:

\[
\Delta E_{\text{proj}}
=
\frac{1}{2}
\Delta \mathbf{u}_{\text{proj}}^T
M
\Delta \mathbf{u}_{\text{proj}}.
\]

Then feed this projected energy into the existing passivity cascade.

The correct order is:

\[
\Delta \mathbf{u}_{\text{raw}}
\rightarrow
\Delta \mathbf{u}_{\text{proj}}
\rightarrow
\text{recompute energy}
\rightarrow
\text{passivity scale}
\rightarrow
\Delta \mathbf{u}_{\text{final}}.
\]

Do not compute passivity on the raw kick and then project without updating energy accounting.

---

## 10. Where to Insert in the Coupler

Put the projection inside:

```text
_compute_distant_response_patch
```

The intended insertion point is between the raw DCR kick construction and the existing passivity cascade.

Recommended pipeline:

```text
1. Compute raw DCR patch response.
2. Convert raw response to generalized velocity:
      Δu_raw = [Δv_raw, Δω_raw]

3. If stable area-contact gate passes:
      Δu_proj = project_contact_compatible(Δu_raw)
   Else:
      Δu_proj = Δu_raw

4. Recompute kinetic energy from Δu_proj.

5. Run existing §9.6 / §15 passivity scaling.

6. Apply final Δv, Δω to the rigid body.
```

The projection should happen before passivity scaling because the projected kick is the actual candidate kick. The passivity machinery should operate on the kick you may actually apply.

---

## 11. Practical Gating

Do not apply this projection to every object in every contact. That would over-stabilize the simulation and suppress valid DCR effects.

Enable it only for stable area contacts.

A reasonable gate:

```python
thin_body = half_y / max(half_x, half_z) < 0.25
stable_patch = num_patch_points >= 3
resting = abs(v_normal) < v_n_thresh and norm(v_tangent) < v_t_thresh

if thin_body and stable_patch and resting:
    project_dcr_kick = True
else:
    project_dcr_kick = False
```

Suggested criteria:

\[
\frac{h_y}{\max(h_x, h_z)} < 0.25
\]

for thin bodies, where \(h_x,h_y,h_z\) are half-extents.

Require:

\[
N_{\text{patch}} \ge 3.
\]

Require near-resting normal velocity:

\[
|v_n| < v_{n,\text{thresh}}.
\]

Require near-sticking tangential velocity if using tangent rows:

\[
\|\mathbf{v}_t\| < v_{t,\text{thresh}}.
\]

Also useful:

\[
\mathbf{x}_{\text{COM projection}} \in \text{contact polygon}
\]

or at least near the contact polygon.

This prevents applying the projection to edge contacts or genuine tipping states.

---

## 12. Minimal Implementation Version

Implement this first:

1. Sample contact patch corners or representative points.
2. Build \(J_i\) for each point.
3. Compute \(\bar{J}\).
4. Build only normal differential rows:

\[
D_i = \mathbf{n}^T(J_i - \bar{J}).
\]

5. Apply the mass-metric projection:

\[
\Delta \mathbf{u}_{\text{proj}}
=
\Delta \mathbf{u}_{\text{raw}}
-
M^{-1}D^T
\left(
D M^{-1}D^T + \epsilon I
\right)^{-1}
D \Delta \mathbf{u}_{\text{raw}}.
\]

6. Recompute energy.
7. Apply existing passivity scaling.
8. Apply final kick.

This should remove most fake pitch and roll.

If yaw remains, add weighted tangent rows.

---

## 13. Pseudocode

```python
def project_dcr_kick_contact_compatible(
    du_raw,              # shape (6,)
    patch_points,         # list of world-space points
    com_world,            # world-space COM
    normal,               # contact normal
    tangent1,             # contact tangent basis
    tangent2,
    mass,
    inertia_world,        # 3x3 world inertia
    use_tangent=False,
    tangent_weight=0.25,
    eps=1e-7,
):
    # Projects a raw DCR generalized velocity kick into the null-space
    # of stable patch-contact differential motion.
    #
    # du_raw = [dv_x, dv_y, dv_z, dw_x, dw_y, dw_z]

    N = len(patch_points)
    if N < 3:
        return du_raw

    # Build point Jacobians J_i = [I, -skew(r_i)]
    Js = []
    for x_i in patch_points:
        r_i = x_i - com_world
        J_i = np.zeros((3, 6))
        J_i[:, 0:3] = np.eye(3)
        J_i[:, 3:6] = -skew(r_i)
        Js.append(J_i)

    J_bar = sum(Js) / N

    rows = []

    # Normal differential rows
    n = normalize(normal)
    for J_i in Js:
        row = n.T @ (J_i - J_bar)
        rows.append(row)

    # Optional tangent differential rows
    if use_tangent:
        t1 = normalize(tangent1)
        t2 = normalize(tangent2)
        wt = np.sqrt(tangent_weight)

        for J_i in Js:
            rows.append(wt * (t1.T @ (J_i - J_bar)))
            rows.append(wt * (t2.T @ (J_i - J_bar)))

    D = np.stack(rows, axis=0)

    # Build inverse mass matrix
    Minv = np.zeros((6, 6))
    Minv[0:3, 0:3] = (1.0 / mass) * np.eye(3)
    Minv[3:6, 3:6] = np.linalg.inv(inertia_world)

    # Solve projection
    A = D @ Minv @ D.T + eps * np.eye(D.shape[0])
    b = D @ du_raw

    correction = Minv @ D.T @ np.linalg.solve(A, b)

    du_proj = du_raw - correction

    return du_proj
```

---

## 14. Integration Pseudocode

```python
def compute_distant_response_patch(...):
    # Existing DCR computation
    dv_raw, dw_raw = compute_raw_dcr_patch_kick(...)

    du_raw = np.concatenate([dv_raw, dw_raw])

    if should_project_dcr_kick(body, contact_patch):
        du_candidate = project_dcr_kick_contact_compatible(
            du_raw=du_raw,
            patch_points=contact_patch.points,
            com_world=body.com_world,
            normal=contact_patch.normal,
            tangent1=contact_patch.tangent1,
            tangent2=contact_patch.tangent2,
            mass=body.mass,
            inertia_world=body.inertia_world,
            use_tangent=contact_patch.is_sticking,
            tangent_weight=0.25,
            eps=1e-7,
        )
    else:
        du_candidate = du_raw

    # Recompute energy after projection
    dE_candidate = kinetic_energy_increment(
        body=body,
        du=du_candidate,
    )

    # Existing passivity machinery
    alpha = compute_passive_alpha(
        dE_candidate,
        available_modal_energy,
        ...
    )

    du_final = alpha * du_candidate

    apply_generalized_velocity_increment(body, du_final)
```

---

## 15. What Not To Do

### Do not only lower \(\eta\)

Lowering \(\eta\) gives

\[
\Delta E_{\text{modal}} \le \eta \Delta E_{\text{rigid loss}}.
\]

This reduces the artifact, but it also reduces the DCR effect. It is not a principled fix.

### Do not only lower \(\gamma\)

Lowering \(\gamma\) damps the visible kick but leaves the underlying point-patch torque mechanism unchanged.

### Do not always move the kick to the COM

Setting the lever to zero:

\[
\mathbf{r} = 0
\]

forces

\[
\boldsymbol{\tau} = \mathbf{r} \times \mathbf{F} = 0.
\]

This stabilizes flat utensils but destroys legitimate torque for tall bodies. A pillar, bottle, candle, or domino should be able to tip.

This is a scene hack, not a robust DCR extension.

### Do not rely on AVBD iterations to clean this up

At low iteration counts, for example 4 AVBD iterations, the contact solver may not fully correct the contact-incompatible velocity before it becomes visible.

The projection should be applied before the solver has to fight the artifact.

---

## 16. Expected Result

With the projection enabled:

- Flat utensils should still receive DCR-induced rattle.
- Spurious pitch and roll from fake point impulses should be strongly reduced.
- Yaw drift should reduce if tangent differential rows are enabled.
- Tall objects should still be able to tip if the gate excludes them.
- The energy/passivity story remains intact because the projection removes velocity components rather than adding energy.

The target behavior is not "no motion." The target behavior is:

\[
\text{DCR motion without fake area-contact twisting}.
\]

---

## 17. Recommended Experiment

Use the same scene and sweep:

\[
\eta \in \{0, 0.3, 0.6, 0.99\}.
\]

Compare these modes:

1. No DCR.
2. Current DCR point-patch kick.
3. Current DCR with lower \(\eta\).
4. Contact-compatible projection with normal rows only.
5. Contact-compatible projection with normal + tangent rows.

Measure:

\[
\max_t |\theta_{\text{roll}}(t)|,
\]

\[
\max_t |\theta_{\text{pitch}}(t)|,
\]

\[
\max_t |\omega_{\text{yaw}}(t)|,
\]

\[
\Delta E_{\text{applied}},
\]

\[
\Delta E_{\text{removed by projection}}.
\]

Also log the projection ratio:

\[
\rho =
\frac{
\|\Delta \mathbf{u}_{\text{proj}}\|_M
}{
\|\Delta \mathbf{u}_{\text{raw}}\|_M
}.
\]

If the projection is doing the right thing, \(\rho\) should be close to 1 for legitimate coherent kicks and much smaller for fake twisting kicks.

---

## 18. Final Recommendation

Implement the normal-only mass-metric projection first.

That is the cleanest fix:

\[
D_i = \mathbf{n}^T(J_i - \bar{J}).
\]

It directly targets the problem: the DCR point kick creates differential normal motion across a stable contact patch.

Then add tangent rows only if yaw drift remains:

\[
D =
\begin{bmatrix}
D_n \\
\sqrt{w_t}D_{t_1} \\
\sqrt{w_t}D_{t_2}
\end{bmatrix}.
\]

This is better than lowering \(\eta\), better than moving the kick to the COM, and better than hoping AVBD catches the problem later.

The strongest concise statement is:

> DCR should inject a patch-compatible generalized velocity, not an arbitrary point-impulse torque at the centroid of an area contact.
