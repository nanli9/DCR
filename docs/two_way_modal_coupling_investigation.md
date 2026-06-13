# Investigation — Two-Way Modal Coupling (cube modal ↔ slab modal)

**Status:** investigation only, no code changed. Question posed by PI brainstorm.
**Date:** 2026-06-13.
**Companion reference added:** `docs/ABD.pdf` — Lan, Kaufman, Li, Jiang, Yang,
*Affine Body Dynamics: Fast, Stable and Intersection-free Simulation of Stiff
Materials*, ACM TOG 41(4), Art. 67, 2022.

---

## 1. The question

Today the repo gives modal (reduced) coordinates to **the support only** (the
slab / "table"). The colliding **cube stays a rigid body** — it has no internal
modes. Energy can flow cube-KE → slab vibration, and (already) the slab's
surface velocity feeds back into the cube's rigid impulse, but the cube itself
never *rings*.

The proposal: give the **cube its own modal reduced coordinates too**. Then at
each contact corner there is a local vibration on *both* sides. Kinetic energy
of the cube splits into (a) cube internal vibration, (b) slab internal
vibration; the slab vibration feeds back into the cube (rigid + modal), the cube
vibration feeds back into the cube rigid motion, etc. 

> **Does this fully-coupled, two-way-modal system eventually come to rest at the
> static-sag equilibrium under damping — like the static support test — or can it
> sustain / grow energy (limit cycle, blow-up, ringing forever)?**

Short answer: **Yes, it provably settles to the static-sag equilibrium —
*provided* two conditions hold (positive modal damping on *both* bodies, and a
*symmetric/passive* contact coupling). The current one-way η-budgeted impulse
port does not by itself guarantee the second condition for a modal↔modal pair;
the monolithic variational route does. ABD is exactly the rigorous version of
that monolithic route — and is an excellent fit for the cube, but cannot replace
the slab's FEM modal basis.**

The rest of this note justifies that and gives the failure modes to watch.

---

## 2. What the coupling looks like today (grounded in code)

The dynamic body↔ring channel is `dcr/dcr/impulse_port.py`. Per in-contact
corner (support normal `n`, world lever `r`, slab modal column `U_y`):

```
ġ = (v_lin + ω×r)·n − U_yᵀ q̇_d                  # relative normal velocity (already two-way at v-level)
w = nᵀM⁻¹n + (r×n)ᵀ I⁻¹ (r×n) + ‖U_y‖²           # effective inverse mass + modal 1/M_q  (DCR Eq.17)
λ = max(0, −(1+e)·ġ / w)                         # unilateral, e = 0
Δv_lin = λ n/m ,  Δω = I⁻¹(r×n)λ ,  Δq̇_d = −U_y λ   # ONE impulse, opposite signs → momentum conserving
```

Two facts to carry forward:

1. **It is already momentum-conserving and already two-way *for the slab*.** A
   single scalar `λ` is applied to the body (`+`) and the ring (`−`) through one
   shared effective mass `w`. The slab's modal velocity `U_yᵀq̇_d` is inside `ġ`,
   so a ringing slab *does* push back on the cube. This is the right template.

2. **But the *governor* is one-way.** `passive_alpha` / `reservoir_alpha`
   (`dcr/modal/passive_inject.py`, foundation §15) bound only the *modal
   injection*, funded by the *rigid* KE loss: `Σ ΔE_modal ≤ η·Σ ΔE_rigid_loss`.
   That budget is asymmetric by design — it assumes the cube is the energy
   source and the ring is the sink. For a **modal↔modal** pair there is no
   privileged source/sink; energy must be free to flow *both* directions without
   a unidirectional cap.

The slab modal stepper (`dcr/modal/homogeneous_stepper.py`) integrates each mode
as an **exactly-damped SDOF oscillator** with per-mode Rayleigh damping `ζ_j`
(`q'' + 2ζωq' + ω²q = 0`, closed-form state transition). So the slab side
*already dissipates*. A cube modal model would need the same.

---

## 3. The physics: a damped coupled linear system settles to static equilibrium

### 3.1 While contact is maintained, it is one linear dissipative system

Stack the states of the in-contact phase:

```
z = [ x_c, v_c          # cube rigid (translation + rotation)
      q_c, q̇_c          # cube modes
      q_s, q̇_s ]        # slab modes
```

Each modal block obeys `M q̈ + C q̇ + K q = Jᵀλ` with `M = I` (mass-normalized
modes, per CLAUDE.md), `K = diag(ω²) ≻ 0`, `C = diag(2ζω) ⪰ 0`. The contact
applies the *same* normal impulse `λ` to every participating DOF through its
Jacobian, with the action–reaction signs the impulse port already uses. Gravity
is a constant load `g`.

If the coupling is **symmetric** (the slab feels `−J_sᵀλ` exactly as the cube
feels `+J_cᵀλ`, through one shared `λ` and one shared effective mass — the §2
template extended to a second modal block), the closed-contact dynamics are a
**linear time-invariant dissipative system**

```
ż = A z + b,     with total mechanical energy
E(z) = ½ v_cᵀM_c v_c + ½(q̇_cᵀq̇_c + q_cᵀK_c q_c) + ½(q̇_sᵀq̇_s + q_sᵀK_s q_s) + V_grav
```

a Lyapunov function whose rate is **`Ė = −q̇_cᵀC_c q̇_c − q̇_sᵀC_s q̇_s ≤ 0`** —
energy can only leave, through the modal dampers. There is no contact-work term
because the shared impulse does equal-and-opposite work on the two sides (that is
*precisely* what "passive/symmetric coupling" means). The unique equilibrium is

```
v_c = q̇_c = q̇_s = 0,   q_c* = K_c⁻¹ J_cᵀλ*,   q_s* = K_s⁻¹ J_sᵀλ*
```

i.e. **the static sag** — the cube resting, both bodies deformed to exactly the
deflection that holds up gravity. With `C ⪰ 0` and the pair `(A, C)` observable
(any real structure with at least one damped mode coupled to the load is), this
equilibrium is **globally asymptotically stable**. So in the maintained-contact
regime the answer is an unconditional *yes — it decays to static sag*, exactly
like a multi-DOF damped oscillator. This is the same statement as "a damped
elastic table with a weight on it stops wobbling and settles to its sag."

### 3.2 The feedback the PI anticipated is real but harmless to convergence

Two coupled modal systems with nearby frequencies will **beat** — energy
sloshes cube↔slab before it dissipates. That *is* the "slab vibration feeds back
to the cube" effect. It is physical and it does **not** threaten convergence; it
only sets the **timescale**: the decay envelope is governed by the *smaller* of
the two damping ratios, not by the contact. Expect "energy ping-pongs a while,
then both ring down to the sag," not "instant settle." Worst case is a near-
resonance (`ω_cube ≈ ω_slab`) with tiny damping → very long ring-down, but still
monotone-in-envelope decay.

---

## 4. The three ways it can *fail* to settle (what to actually watch)

The §3 guarantee rests on assumptions the current architecture does **not**
automatically satisfy once the cube becomes modal. Each is a concrete risk:

| # | Failure mode | Cause | Guard |
|---|---|---|---|
| **F1** | **Energy growth / limit cycle** | Coupling not symmetric — e.g. cube→slab and slab→cube applied as two *separate* sequential impulses, or the one-way η-budget caps one direction but not the reverse. Then the discrete map can *create* energy. The repo already flags this: corners are applied sequentially because "Jacobi can over-extract." A second modal block multiplies that risk. | Use **one shared scalar `λ`** with `w = nᵀM⁻¹n + (r×n)ᵀI⁻¹(r×n) + ‖U_y,cube‖² + ‖U_y,slab‖²`, applied to all three blocks at once. Or go monolithic (§5). **Drop the one-way reservoir cap for modal↔modal** — it has no source/sink to bound. |
| **F2** | **Internal ringing that never stops** | A modal block with `ζ = 0`. While the cube is *airborne* (contact open) its internal vibration is damped only by its own `C_c`; if that is zero it rings forever and the system reaches "rigid rest + permanent hum," never true static rest. | Require **`ζ_cube > 0`** (same Rayleigh model the slab already uses in `homogeneous_stepper.py`). |
| **F3** | **Non-smooth chatter at separation** | Contact is *unilateral* — the cube can leave and re-land. Each event is a hybrid switch; a naïve restitution or a per-substep impulse that fires on micro-separations can pump a buzzing limit cycle. | `e = 0` (already), apply the impulse only on genuine closing (`ġ < −ε`, already in the port via `_VEL_EPS`), and prefer the implicit/variational step which handles re-contact as a barrier rather than an event. |

Bottom line: the continuous physics says *settle*. Whether the **discretization**
settles is entirely a question of keeping the coupling passive. The impulse-port
path *can* be made passive for a modal↔modal pair (single shared `λ`, no one-way
cap, both `ζ>0`), but it is fragile. The robust route is variational.

---

## 5. Where ABD fits — and where it doesn't

ABD (`docs/ABD.pdf`) is directly relevant because it solves *exactly* the
"nearly-rigid body with a small reduced deformation" problem the PI wants to give
the cube — and it solves the two-way coupling question in the rigorous way.

### 5.1 What ABD gives you that helps

- **A principled reduced-deformable "rigid" body.** ABD replaces SE(3) rigid
  coords with **12 affine DOFs** `q = (p, a₁, a₂, a₃)` (translation + a 3×3
  linear map) held near-rigid by a stiff *orthogonality potential*
  `V⊥ = κv‖AᵀA − I‖²_F` (Eq. 6–7). Key conveniences that line up with our
  follow-up's design (CLAUDE.md §5):
  - **Constant mass matrix** `M = ∫ρ J(x̄)ᵀJ(x̄)` (Eq. 4) — no re-assembly.
  - **No Coriolis / no nonlinear `ω×Iω` term** (Eq. 3–5) — same reason our
    mass-normalized modal state has `M_q = I` and a trivial stepper.
  - Equations of motion are just `M q̈ = −∇V + f` (Eq. 5) — a plain potential
    gradient, identical in spirit to our SDOF modal blocks.
- **The two-way coupling done right — one global variational step.** ABD builds
  a *single* incremental potential for the whole scene each step (Eq. 9):
  `E(q) = V_C(q) + V_F(q) + Σ_b E_b(q_b)`, with contact as a **barrier
  potential** `V_C = Σ κ_c B(d)` (Eq. 10–11) coupling the DOFs of *both* bodies
  symmetrically, and minimizes it with a filtered Newton solve. Because every
  step is **descent on a bounded-below potential**, the discrete system is
  passive *by construction* — it **cannot** create energy, contact and internal
  deformation are coupled both ways automatically, and the rest state is the
  global minimizer = **the static sag**. This is precisely the §3 guarantee, but
  *discrete and unconditional* — it removes every F1/F3 fragility of the impulse
  port. Restitution is an explicit, controllable dissipation model on top
  (§4.1), not an emergent accident.
- **It is the rigorous form of what the repo already prototyped.** Our
  `docs/reduced_coupled_avbd.md` monolithic Schur block (contact couples rigid
  `x` to reduced `q` through `ρ·J_x·J_qᵀ`) is a one-sided special case of ABD's
  global Hessian (`docs/ABD.pdf` §4.3, the off-diagonal `12×12` blocks linking
  contacting bodies). Extending that block so the **cube** also carries reduced
  coords — and assembling the cube-DOF↔slab-DOF cross term — is the ABD
  construction. The repo is one block away from it.

### 5.2 What ABD does *not* give you (the load-bearing caveat)

**ABD's deformation is affine only — a single homogeneous strain per body.** A
12-DOF affine map can stretch, shear, and rotate a body uniformly; it **cannot
bend**. The slab's static sag and its vibration modes are **bending-dominated**,
and bending is a non-affine displacement field. Concretely:

- For the **cube**: affine is plausibly *enough*. A small, chunky, nearly-rigid
  block deforms approximately homogeneously; 12 affine DOFs capture its dominant
  compliance. **ABD is a strong fit for the cube side.**
- For the **slab**: 12 affine DOFs **cannot represent the bending sag** that is
  the entire point of the slab modal analysis. Replacing the slab's FEM modal
  basis with ABD would throw away the very mode shapes we care about. **Keep the
  FEM modal reduction for the slab.**

So ABD is **not a drop-in replacement** for the modal pipeline. Its value here is
twofold and specific:

1. **As a model for the cube:** an affine reduced cube is a clean, cheap,
   constant-mass, Coriolis-free deformable — easier to wire in than a second FEM
   modal basis, and likely sufficient for a compact block.
2. **As the architectural blueprint for the coupling:** formulate cube+slab as
   one global incremental potential with a contact *barrier* coupling their two
   reduced coordinate sets, minimized per step. That is what makes the two-way
   modal↔modal settling-to-static-sag a *theorem* (descent on bounded-below
   energy) instead of a *hope* (passive impulse you have to babysit).

A pragmatic hybrid that respects CLAUDE.md scope: **cube = affine/ABD-style
reduced (or a small modal basis), slab = existing FEM modal basis, coupled
through a single monolithic variational/Schur step** (the `reduced_coupled_avbd`
path, extended to give the cube its own `J_q`). That inherits ABD's energy
guarantee for the *coupling* without forcing the slab into an affine model.

---

## 6. Verdict

- **Will it go to rest like the static-sag test?** Yes. A two-way modal cube↔slab
  system in maintained contact is a damped linear system whose only equilibrium
  is the static sag; with positive damping on both sides it is globally
  asymptotically stable (§3). The PI's anticipated cube↔slab feedback is real
  (beating/energy sloshing) but only lengthens the ring-down — it does not break
  convergence.
- **Conditions that must hold** (else it won't settle): (F1) the contact coupling
  must be **symmetric/passive** — one shared impulse and **no one-way η budget**
  for a modal↔modal pair; (F2) the **cube must have positive modal damping**;
  (F3) handle unilateral re-contact without chatter (variational/barrier is
  safest).
- **Does ABD help?** Yes, in two specific ways: it is an excellent **reduced
  model for the cube** (constant mass, no Coriolis, stiff-near-rigid), and it is
  the **rigorous blueprint for the two-way coupling** (one global barrier
  potential → settling is a descent theorem). It does **not** replace the slab's
  modal basis — affine DOFs can't bend.
- **Cheapest next experiment (when we do touch code):** extend the existing
  monolithic `reduced_coupled_avbd` Schur block to give the cube its own reduced
  coordinates and cross-couple cube-`q` ↔ slab-`q` through the contact, with
  positive damping on both. Reuse the exact-damped SDOF stepper for the cube.
  Watch total mechanical energy: it must be monotone non-increasing to rest. If
  it isn't, F1 (asymmetric coupling) is the first suspect.

> Scope note (CLAUDE.md): this stays inside the follow-up's charter — it is still
> passive, energy-bounded modal coupling, not a new dependency and not a
> production engine. ABD is used as a *reference model and a passivity argument*,
> not adopted wholesale.
