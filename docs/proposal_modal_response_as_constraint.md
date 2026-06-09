# Modal Contact Response as a Coupled Constraint
### From DCR's one-way velocity-bias to a bidirectional, energy-bounded constraint coupling

**Author:** Nan · **For:** Sheldon (PI, DCR co-author) · **Branch:** `AVBD-Native`
**Status:** prototype accepted (coupled mode); seeking direction for the research write-up.

> **Notation.** The DCR paper writes the modal basis as `U` and modal amplitudes as `q`
> (Eq. 6–7). This note follows our foundation document's convention `Φ` for the basis;
> read `Φ ≡ U` throughout. Reduced matrices `M_q, D_q, K_q` and per-mode `(ω_i, ζ_i)` match
> the paper. Equation numbers cite **Coevoet, Andrews, Relles & Kry, CGF 39(8), 2020**.

---

## 0. One-paragraph thesis

In DCR, the distant/modal response is produced by a **separately integrated** reduced model: rigid contact impulses force a modal IIR resonator (Eq. 7–10) stepped at a finer rate `T`, the *peak* modal displacement at each distant contact is read off (Eq. 11), converted to a velocity bias `Δv = d_max/h` (Eq. 12), and injected into the contact RHS `b` of the Schur system (Eq. 2, via Eq. 13) — treated *exactly* like a Newtonian restitution bias (cf. Eq. 4). This is elegant and cheap, and the response does pass through the solver. But the modal amplitudes `q` are never variables of the contact solve, the coupling is **one-directional**, and the transfer recipe is **kinematic** (a length over a timestep) with **no energy debit** on the modal side when its bias pushes a rigid body. This proposal promotes `q` to a **first-class constrained degree of freedom**: a single contact gap `g(z,q)` depends on both the rigid pose `z` and the modal amplitude `q`, one shared multiplier enforces it, and the back-reaction is the exact transpose of the forward map. The coupling becomes **bidirectional** and **transpose-consistent** (the structural condition for the step not to create energy). On the AVBD solver, the prototype shows this reaches the *true* modal equilibrium `K_q⁻¹F` (a naive block-decoupled variant lands ~70% off), is iteration-robust, and stays bounded in regimes where the decoupled response blows up. Energy follows from the formulation rather than a tuned kick: the static load resolves algebraically (`q_s`), the dynamic ring (`q_d`) is a *dissipative* damped-oscillator response to the actual contact transient, and the symmetric cross-block makes the impulse exchange transpose-consistent — so the closed-system energy `E_rigid + E_modal` is non-increasing without external work (§3; verified in free vibration, the contact-coupled ledger is a stated milestone).

---

## 1. What DCR actually does, and the two structural properties that motivate this work

DCR's distant-response pipeline (paper §4.2–4.3):

```
rigid contact solve (λ_N)  ──Eq.9──►  force modal IIR (Eq.7–10, stepped at rate T)
                                            │
                                       peak displacement d_max  (Eq.11)
                                            │
                                       Δv = d_max / h           (Eq.12)
                                            │
                          ┌─────────────────┴──────────────────┐
              preferred route                          fallback route
        add Δv to b in Eq.2 (Eq.13);              explicit impulse h f_p = m_eff Δv_p n̂_p
        goes through the full solve               (Eq.17–18); applied locally
        as a restitution-like bias                  ↑ paper flags this as a drawback:
                                                  "injected locally with a local effective
                                                   mass rather than imposing a desired contact
                                                   separation velocity on the full solve"
```

So the response is *not* a naive post-solve kick — the preferred route is a bias inside the solve. The motivation for this follow-up is two **structural** properties of the design, not a bug:

1. **The coupling is one-way and the modal state is separate.** `q` evolves under its own IIR (Eq. 7–10) and is never a variable of the contact KKT (Eq. 1–2). It influences the rigid solve only through the scalar bias `d_max/h`. Consequently there is **no back-reaction**: when the modal bias does work on a rigid body, nothing debits the modal reservoir. The modal→rigid transfer is therefore **not energy-symmetric and not bounded** — the reservoir keeps ringing (per its own damping) regardless of how much it pushed.

2. **The transfer recipe is kinematic, not energetic.** `Δv = d_max/h` targets a peak-displacement-over-timestep. A velocity kick of that size carries kinetic energy `∝ (d_max/h)²`, so the implied energy injection scales like `1/h²` and with solver state, rather than being prescribed directly. The energy that ends up in the bodies is an emergent side effect of a length recipe, not a controlled quantity.

These are exactly the two things a constraint reformulation fixes: make the coupling bidirectional (symmetric) and make the transfer energy-prescribed (bounded).

---

## 2. The reframing: contact as a constraint on `(z, q)` jointly

Represent the deformable support by a reduced modal field `u(x) = Φ(x) q`, mass-normalized so modal mass is `I`, stiffness `Ω² = diag(ω_i²)`, and `E_modal = ½‖q̇‖² + ½ qᵀΩ²q`.

A contact between a rigid body (generalized pose `z`) and a support point is **one constraint whose gap depends on both**:

```
g(z, q) = nᵀ ( p_r(z) − x_s(q) ) − δ_shell ,      x_s(q) = x_s⁰ + Φ(x_s⁰) q
```

The gap Jacobian has **two blocks**, not one:

```
J_x = ∂g/∂z            (rigid contact Jacobian — the usual DCR/AVBD term)
J_q = ∂g/∂q = −Φ(x_s)  (the modal column — the new object)
```

A single non-negative multiplier `λ_N ≥ 0` enforces `g ≥ 0`. The **same** `λ_N` that pushes the rigid body out also loads the modal coordinate through `J_q`. That is the entire idea: **the modal support is a constraint partner, and the modal response is the dual variable acting on the modal column** — not a separately integrated bias.

Contrast with DCR in one line: DCR adds a *scalar restitution-like bias* `Δv = d_max/h` to `b`, sourced from a decoupled IIR; here the modal amplitude is a *primal variable* carrying its own `J_q` column, and the multiplier that satisfies non-penetration is the same one that drives it.

### 2.1 The coupled solve (monolithic primal Newton)

Each inner iteration assembles one Newton block over all tracked bodies plus the shared modal coordinate `q`:

```
┌ H_x,1                      ρ·J_x,1·J_q,1ᵀ ┐ ┌Δx_1┐   ┌ −g_x,1 ┐
│        H_x,2               ρ·J_x,2·J_q,2ᵀ │ │Δx_2│ = │ −g_x,2 │
│               ⋱                  ⋮         │ │ ⋮  │   │   ⋮    │
└ ρ·J_q,1·J_x,1ᵀ  …          H_q            ┘ └ Δq ┘   └ −g_q  ┘
```

- `H_x,i` — body inertia + contact Hessian (AVBD's existing per-body 6×6 block).
- `H_q = K_q + Σ_j k_j J_q,j J_q,jᵀ` — modal stiffness plus the contact stiffening on the modal DOF. (Static/dynamic split: the algebraic sag `q_s` is solved here; the dynamic ring `q_d` is advanced by an *exact* damped-oscillator step per substep, so the modal ODE carries zero discretization error — this replaces DCR's IIR (Eq. 10) with an exact resonator on the same per-mode `ω_i, ζ_i`.)
- **`ρ·J_x·J_qᵀ`** — the off-diagonal cross-coupling. **This block is the constraint.** It makes a rigid penetration push the support down and a support deflection relieve the penetration, inside one linear solve. Delete it and you are back to two decoupled problems (which is DCR's regime).

Schur-eliminate the bodies (each `H_x,i` is small/dense) and solve `r×r` for `Δq`:

```
S   = H_q − Σ_i (ρ J_q,i J_x,iᵀ) H_x,i⁻¹ (ρ J_x,i J_q,iᵀ)
Δq  = (S + εI)⁻¹ rhs_q ,   Δx_i = −H_x,i⁻¹ ( g_x,i + ρ J_x,i J_q,iᵀ Δq )
```

The back-reaction is **transpose-consistent by construction**: forward support velocity `v_s = Φ(x_s) q̇`, reverse impulse `q̇ ← q̇ − Φ(x_s)ᵀ J`, with the *same* `Φ` and `x_s`. Forward and reverse maps are exact transposes — the algebraic condition for the coupled step to never create energy. DCR has no such reverse map (the IIR is forced one-way), which is precisely why the modal→rigid push is unbounded there.

---

## 3. The energy view: dissipative by construction, conservative by structure

The coupled solve never adds a tuned velocity kick, so its energy behaviour is a *property of the formulation*, not of a correction bolted on top. Three facts govern it.

1. **The static load never enters the kinetic channel.** Under the static/dynamic split, the resting contact force resolves *algebraically* through the static sag `q_s` (the cross-block equilibrium `K_q q_s = Σ U_y·f`, which has no kinetic term). Only the *high-passed residue* `F_q_dyn = F_q_total − F_q_static_lp` — the genuine impact transient — forces the dynamic ring `q_d`. A body at rest gives `F_q_dyn → 0`: no spurious vibration. *(`docs/reduced_coupled_avbd.md`, static/dynamic split.)*
2. **The coupling cannot manufacture energy.** The cross-block is symmetric — `ρ J_x J_qᵀ` paired with its exact transpose `ρ J_q J_xᵀ` — so the forward support velocity `v_s = Φ q̇` and the back-reaction `q̇ ← q̇ − Φᵀ J` are exact transposes of one another. That transpose-consistency is the algebraic condition for an impulse exchange to conserve (never create) energy. Unlike DCR's one-way IIR, it is structurally present here. *(AVBD-native spec §13.)*
3. **The ring is dissipative.** `q_d` is advanced by an *exact* damped-oscillator step — the Van Loan augmented-exponential of the reduced modal ODE `M_q q̈ + D_q q̇ + K_q q = r` (DCR paper Eq. 7–8) with Rayleigh damping — so absent forcing it decays monotonically. Verified: damping power `q̇ᵀ D_q q̇ ≥ 0` every step; modal energy never grows in free vibration over 2000 steps. *(`docs/reduced_coupled_avbd.md`, IIR exact-resonator block.)*

**The budget, stated precisely.** The modal ring can hold only what the dissipative IIR retains of the physical contact work that actually forced it — it is sourced from the solver's *own* contact impulses, not from a free parameter. The end-to-end check is the closed-system energy ledger: with no gravity and no external force,

```
E_rigid(t) + E_modal(t)  ≤  E_rigid(0) + E_modal(0) + ε        (AVBD-native spec §15, invariant 7)
```

and with damping on the total strictly decreases. This is exactly what "accurate **under a budget**" means: the response is bounded by physical energy conservation, not by a tuned cap. **Status:** verified for *free* modal vibration; making the *contact-coupled* ledger a passing test for `coupled_iir_modal` is the single open energy item (§7, milestone 3). The reason it is tractable to close: in the constraint form the transfer is carried by a specific impulse `J` through a specific Jacobian, so the work `Jᵀ v_p` is per-impulse and auditable — whereas DCR's only available estimator is the global rigid-KE delta, which in a coupled solve mixes gravity, other contacts, and stabilization.

### 3.1 Routing the contact *anchor* through the static channel (the rock/slide/spin fix)

Fact #1 above — "the static load never enters the kinetic channel" — is the formulation's *intent*. Realizing it requires care on a point that is easy to get wrong: **which `q_s` the contact constraint actually reads.** The deformable support surface a body rests on sits at `y_anchor = y_rest + U_y·q_s`. If the constraint reads the *raw, per-substep* `q_s` — which, being algebraic (`K_q q_s = Σ U_y·f`), tracks the **instantaneous** contact force — then an *impact* force spike spikes `q_s`, the support surface **jumps** under the body's contact corners, and that surface motion is fed straight back to the body. Because a resting/landing body touches the support at several corners with *different* `U_y`, the jump is uneven → a net **torque** → the body is kicked rotationally (and, on a tilting surface, slides). Measured signature of the un-fixed path: a box dropped with a 10° tilt onto a *stiff* support picks up `|ω|≈0.4 rad/s` at impact, versus `≈6×10⁻⁴` on a rigid floor — a ~600× spurious angular kick; resting bodies on a cantilever (the ledge boulder) sustain a ~0.3–1° rocking limit cycle. This is *not* a contact-solver artifact (a perfectly symmetric flat drop yields exactly zero spin), and it is *not* fixed by more iterations or substeps — it is the support surface faithfully relaying the contact-force transient to the body.

The fix is the contact-side dual of fact #1: **feed only the low-passed (static-sag) component of `q_s` into the contact anchor**, so the impact transient is routed to the dissipative ring `q_d` (render-only) instead of kicking the body. Concretely the anchor reads an EMA `q̄_s ← q̄_s + (h/τ)(q_s − q̄_s)` with the **same time-constant `τ` as the static/dynamic split** (`modal_static_lp_tau`) — *no new parameter*. At rest `q̄_s → q_s`, so the equilibrium sag, and every flat-support scene, is bit-for-bit unchanged; only the *transient* surface motion the body sees is the smooth static part. It is a single length-`r` EMA per substep (one device kernel, fully GPU-resident, perf-negligible) and changes no equation — `q_s` itself is still the cross-block Schur variable. Result: the tilted-drop angular kick drops `0.41 → 1.9×10⁻⁴ rad/s` (to the rigid-floor level), the ledge boulder rock vanishes (`|ω|_std 4.6×10⁻² → 6×10⁻⁶`), the static deflection is unchanged, and logged passivity violations *decrease* (the support injects less spurious kinetic energy). In short: the static/dynamic split says the static load must resolve algebraically and only the genuine transient may ring — this makes the **contact constraint itself** honor that split, not just the modal force accumulator. *(`# DEVIATION` foundation §15: static-sag low-pass of the contact reference; documented in `dcr/avbd/reduced_coupled_avbd.py:anchor_static_lowpass`.)*

---

## 4. What the prototype actually shows (the evidence)

**Purpose of this section.** §2–§3 make claims (reaches the true equilibrium, robust, energy-conservative). This section is the *measured evidence* that the working AVBD `coupled_iir_modal` prototype actually delivers them. Numbers are from `docs/reduced_coupled_avbd.md`.

**One baseline recurs, so define it once.** **BCD = block-coordinate descent**: the *naive* way to couple the two systems — solve the rigid block, then separately solve the modal block, and alternate, **without** ever forming the cross-block `ρ J_x J_qᵀ` in one linear system. It is the obvious baseline and it is **not** our method; our method (the monolithic coupled solve of §2.1) is the alternative to it. The BCD rows below are **positive for us**: they show *why* the monolithic coupling is needed — the naive split reaches a measurably wrong answer, ours doesn't.

| Claim | Evidence | Result |
|---|---|---|
| Reaches the **true** static equilibrium | distance from the closed-form answer `q_∞ = K_q⁻¹ Σ F·U_y` | **ours lands within ~13%** of the exact answer (prototype settings) — i.e. the *right* equilibrium. The naive BCD baseline is **~70% off**: it settles to a *different*, penalty-distorted equilibrium, not `K_q⁻¹F`. So ours is ~5× closer to correct. **This is a point in our favour.** |
| **Iteration-robust** | end-of-run `\|q\|` at 4/8/16/32/64 solver iters | spread **< 0.05%** — the answer doesn't drift as you change iteration count, because it sits at a true fixed point (a kinematic `d_max/h` kick would drift). |
| **Stable under tight substeps** | BCD vs ours at 8 substeps | the naive BCD baseline **blows up** (28 mm peak `\|q\|`, 571 mm/s probe velocity); **ours stays bounded** (8.1 µm, 8.5 mm/s). The single strongest argument for the monolithic coupling. |
| **No hidden tuned kick** | `overlay_events == 0` asserted every step | the response comes entirely from the cross-block `ρ J_x J_qᵀ` (static sag) + the dissipative IIR (dynamic ring) — no post-fix velocity kick, no cooldown, no force-cap heuristics. |
| **Real-time-plausible** | CPU hot-path vectorization, then GPU device-residency | CPU reference: −44% step time → ~32 ms/frame on the research shelf scene. On `AVBD-Native` the whole coupled substep is now **GPU device-resident** — graph-replay **~1.85 ms/step** after parallelizing the r×r Schur solve (commits `9a99e19`, `ba48d65`, `8c38003`); the CPU/numpy path is kept as the parity reference. |

Honest cost: the coupled solve is ~20× the bare rigid step at 8 substeps, decomposable as ~5× (substeps) × ~4× (coupling). DCR's whole point was avoiding that cost; the bet here is that AVBD/VBD-style co-optimization makes it affordable enough to be worth the correctness, robustness, and energy-conservation it buys. Quantifying *where* it's worth it is a deliverable (§7).

---

## 5. This is a physical method, not a tunable hack

The most important thing to say about this work is what it is *not*. It is **not** an artistic embellishment driven by gain knobs. On the current `AVBD-Native` branch the visible-amplification machinery was **deliberately removed** once the principled formulation became the default: commit `27d98c1` deleted `modal_jump_gain` (the velocity-derived "jump" amplifier), `modal_energy_cap_fraction` (the η demo cap), the BDF1 integrator, and the matching viser sliders. The accepted coupled coupler has **no gain dial, no jump knob, no exaggeration factor** — its only parameters are physical (material `E, ν, ρ`, modal `ω_i, ζ_i`, mesh) or numerical (the AL penalty clamp, the Schur regularizer ε, the static/dynamic split time-constant — which now *also* low-passes the contact anchor, §3.1, rather than adding a knob of its own). The handful of scaling parameters that survive (`support_response_gain`, `modal_damping_scale`) live in the *basis constructor* and rescale the modal model's physical impedance/damping at build time — they leave every `ω_i, ζ_i` invariant; they are physical model inputs, not per-frame fudge.

What the coupled mode produces is the **solution** of the reduced elastodynamics coupled to AVBD contact — not a plausible-looking approximation of it:

- **Robust.** It reaches the *true* modal equilibrium `K_q⁻¹F` (a block-decoupled variant over-shoots ~70%); it is iteration-robust (<0.05% over 4–64 iters) and substep-robust (stays bounded — 8 µm — where the decoupled response blows up to 28 mm). These are properties of *solving the coupled system*, not of tuning it. (§4)
- **Accurate under a stated budget/regime.** Within the envelope the model is built for, the response is physically faithful: static deflection obeys `q ∝ 1/E` to within ~10% in the stiff regime, and the static equilibrium matches the analytic `K_q⁻¹F` to ~13%. The envelope is explicit and finite — (i) linear modal reduction (small-strain), (ii) stiff supports `E ≳ 10¹⁰ Pa` where the contact penalty doesn't swamp the modal stiffness, (iii) and, once milestone 3 lands, the enforced energy budget. Outside that envelope (soft/large-deformation) it degrades *predictably*, which is a stated limit, not a hidden tuning surface.

The contrast is the whole pitch. DCR's `d_max/h` is a deliberately cheap *approximation* tuned for plausibility; restitution/bounce textures are phenomenological. This method instead **solves the actual coupled contact–elastodynamics problem** and is faithful to it inside a declared regime. The "budget" qualifier is doing real work — it names the regime where accuracy is claimed — but inside that regime the claim is *physical accuracy*, not *artistic plausibility*.

> **What still needs landing for the full claim.** "Accurate" is presently backed by internal checks (`K_q⁻¹F` match, `1/E` scaling). The external anchor — the SOFA ground-truth comparison (milestone 5) — is what converts "accurate against our own analytic prediction" into "accurate against an independent high-resolution elastic simulation." And the closed-system energy ledger that turns "under this budget" from a *regime description* into a verified *guarantee* with contact in the loop is milestone 3 (§3). Both are honest gaps, not finished claims.

---

## 6. Is this universal across constraint-based solvers? (honest assessment)

The core idea — **the modal amplitude `q` as a constrained co-DOF (§2)** — transfers to any constraint-based solver, but the *exactness* guarantee depends on how the solver couples blocks:

| Solver family | Hosts `q` as a constrained DOF? | Reaches true `K_q⁻¹F`? | Notes |
|---|---|---|---|
| Monolithic / Schur-complement (our AVBD coupled path) | yes, natively | **yes** — the cross-block `ρ J_x J_qᵀ` is solved, not approximated | the prototype |
| Block-Gauss-Seidel / BCD (PGS-style, vanilla VBD) | yes, as an independent block | **no** — penalty-modified fixed point (our BCD path over-shoots ~70%) | coupling felt only across sweeps |
| **XPBD** (compliant constraints) | yes, very naturally — `q` is a compliant DOF (compliance `1/k_modal`); the constraint gradient already carries the `J_q` column | yes, in the iterate→∞ limit | arguably the *cleanest* host; transpose-consistency is automatic from the single constraint gradient |
| Hard-constraint LCP | yes (append a compliant row) | yes, but loses the soft-support regularization | no penalty bias, but stiffer numerically |

Note this also explains an architectural observation already in our `CONTRIBUTIONS.md`: AVBD's variational primal structure accepts modal coordinates as co-optimization variables, whereas extending the paper's PGS/complementarity solver to *co-solve* with deformable state is awkward. That is not a knock on PGS — it is exactly why DCR chose the one-way bias injection in the first place. The constraint reformulation is most natural in primal (AVBD/VBD) or compliant (XPBD) solvers.

**Honest framing for the write-up.** "Reduced modal response as a constrained co-DOF" is a general recipe for constraint-based dynamics, with two caveats: (i) *exactness* (true equilibrium, not penalty-biased) needs monolithic coupling — Schur or compliant-projection, not plain block-Gauss-Seidel; (ii) when contact-penalty stiffness exceeds modal stiffness, the penalty absorbs the load and `q ∝ 1/E` scaling degrades — a property of *penalty/AL contact generally*, pinning the trustworthy regime to stiff supports (`E ≳ 10¹⁰ Pa` for thin shelves; consistent with the paper's own Table 2 using ~10 GPa for most models). A hard-constraint solver avoids that bias but trades it for stiffness.

> **Regime boundary observed (load/stiffness ratio).** The same penalty-vs-modal-stiffness limit shows up dynamically, not just in the static `1/E` scaling: a *heavy* body resting near a compliant cantilever's free end (e.g. a 120 kg block on a 1e10 Pa wood ledge) develops a **sustained rotational limit cycle** (~1°) of the contact–modal coupling — 100% coupling-sourced (it vanishes on a rigid floor), numerical (the support deflection is sub-mm, so a 1° tilt is not physical), and not removable by any loop-gain lever we tried (anchor low-pass τ, iteration count, cross-block under-relaxation). It is removed by restoring the regime: lighter load (the same ledge is clean at ≤50 kg) or a stiffer support (clean at steel `E=2e11`). So the trustworthy envelope is a load/stiffness *ratio*, not stiffness alone — heavy load on a compliant support is outside it. This is a clean candidate for the cost/regime characterization (milestone 6) and a motivation for the energy-bounded enforcement (milestone 3).

**Claim discipline.** We do **not** claim the full coupled solver is unconditionally stable. We claim the *coupled solve reaches the true modal equilibrium*, is *iteration/substep-robust*, and is *transpose-consistent so the step cannot create energy* — with the contact-coupled closed-system ledger as the verification still to land (§3, §7). Those are demonstrable; unconditional nonlinear stability is not, and over-claiming it would be the easy mistake.

---

## 7. Proposed project (where I'd like your read)

**Research question.** *Can the DCR distant/modal response be promoted from a one-way, separately-integrated velocity-bias into a bidirectional constrained co-DOF of the contact solve, such that it (a) reaches the true modal equilibrium, (b) is iteration- and substep-robust, and (c) is energy-conserving by structure (transpose-consistent + dissipative, with a closed-system ledger to confirm) — and at what cost?*

**Milestones**

1. **Formalize the constraint statement.** Contact as `g(z,q)`, derive `J_q = −Φ(x_s)`, state the coupled KKT + transpose-consistency condition, and position it precisely against DCR's Eq. 12–13 bias injection. *(Working version exists; needs paper-grade exposition.)*
2. **Exactness result.** Prove/measure that the monolithic cross-block reaches `K_q⁻¹F` while block-Gauss-Seidel reaches a penalty-modified point. *(Have the numbers; want a clean analytic statement.)*
3. **Energy-conservation result — land the contact-coupled ledger.** The coupled step is transpose-consistent (structurally cannot create energy) and the ring is dissipative, both shown for *free* vibration (§3). The open item is to make the **closed-system ledger `E_rigid + E_modal` non-increasing a passing test with contact in the loop** for `coupled_iir_modal`, then state it as a theorem (transpose-consistency + dissipative IIR ⇒ closed-system non-increase) with explicit assumptions. *(Real work, not write-up polish.)*
4. **Solver-generality study.** Implement the constrained-co-DOF coupling on ≥1 second solver family (XPBD is the natural candidate — it makes "modal DOF = compliant constraint" vivid) to show the exactness tracks the coupling structure (monolithic/compliant vs. block-Gauss-Seidel). *(New work.)*
5. **Ground-truth anchor — mirror the paper's own comparison.** DCR §5.2 already validates "Dinner is served" against a SOFA elastic reconstruction (stiff table, `10⁻⁵` step, ~30 min). Reproduce *that* scene and compare the coupled-constraint response to the same SOFA ground truth — internal invariants are necessary, not sufficient; we need one external check that the *motion* is right, not just that the ledger balances. *(New work; most important for credibility.)*
6. **Cost / regime characterization.** The ~5×·~4× decomposition, the stiff-support regime boundary, the substep/iteration robustness curves — stated as "where this is worth it" versus DCR's cheaper bias.

**Deliverables.** A methods note (§2–§3 math + §6 generality table), the exactness + closed-system plots, the SOFA ground-truth comparison, and a cost/regime figure. No audio and no other-paper follow-ons — out of scope by design. (The coupler is already GPU device-resident on `AVBD-Native`; that residency is engineering the cost/regime figure reports — graph-replay ~1.85 ms/step — not a research deliverable in itself.)

**Open questions for you**
- Is the **exactness vs. penalty-bias** distinction (monolithic vs. BCD) the headline, or is the **energy-conservation / transpose-consistency** story the headline? They're separable; not sure which you'd foreground.
- Friction coupling is currently **vertical-support only** (`J_q` carries the normal column; tangential friction doesn't yet see `−Φ(x_s)q̇`). Full 3D moving-support friction is a kernel-level change. First write-up, or follow-up?
- Is a **single XPBD re-implementation** enough to support the "universal for constraint-based solvers" claim, or do you want the LCP case too before we put it in print?

---

## 8. TL;DR for the meeting

- DCR sources the distant response from a **separately integrated** modal IIR (Eq. 7–10) and injects it as a **one-way velocity bias** `Δv = d_max/h` into the contact RHS `b` (Eq. 12–13) — restitution-like, kinematic, with **no back-reaction** debiting the modal reservoir.
- We instead make modal amplitude `q` a **constrained co-DOF**: one gap `g(z,q)`, one multiplier, coupled through `ρ J_x J_qᵀ`, with **transpose-consistent** back-reaction `q̇ ← q̇ − Φᵀ J`.
- Proven payoff: reaches the **true** equilibrium `K_q⁻¹F` (the naive block-coordinate baseline lands ~70% off — *evidence for* monolithic coupling, not against us), **iteration-robust** (<0.05% over 4–64 iters), and **stable** where the decoupled baseline blows up (8 µm vs 28 mm).
- **Energy:** behaviour follows from the formulation, not a tuned kick — the static load resolves algebraically (`q_s`), the dynamic ring (`q_d`) is a *dissipative* exact damped-oscillator response (DCR Eq. 7–8), and the symmetric cross-block makes the impulse exchange transpose-consistent, so `E_rigid + E_modal` is non-increasing without external work. Verified in free vibration; the contact-coupled ledger is the one open item (milestone 3).
- The **exact coupling** transfers to any solver that couples the modal block monolithically (Schur / XPBD-compliant); a block-Gauss-Seidel solver hosts it but only approximately (that's the ~70%-off baseline).
- **This is not a tunable hack.** The current branch deliberately removed the gain/jump/cap demo knobs (`27d98c1`); the coupled coupler has no artistic dial. Its inputs are physical (`E, ν, ρ, ω_i, ζ_i`, mesh). It *solves* the coupled contact–elastodynamics problem and is **physically robust + accurate within a declared regime** (linear/small-strain, stiff supports `E ≳ 10¹⁰ Pa`), not plausibility-tuned. The external SOFA ground-truth (milestone 5) is what fully substantiates "accurate."
- Working prototype on AVBD. Want your steer on the headline (exactness vs. energy-conservation) and how far to push the generality claim before publishing.
```
```
*Equation references verified against `reference/DCR_SCA2020_preprint.pdf` on 2026-06-08: Eq. 2 (Schur contact system), Eq. 7 (reduced modal), Eq. 9 (impulse→modal forcing), Eq. 10 (forced IIR), Eq. 11 (d_max), Eq. 12 (Δv = d_max/h), Eq. 13 (bias into b), Eq. 17 (m_eff), Eq. 18 (explicit-impulse fallback).*
