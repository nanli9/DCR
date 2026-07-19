# Novelty positioning — adversarial prior-art check (2026-07-04)

Result of a three-cluster adversarial prior-art search (each cluster tasked with
*finding the paper that scoops us*, not confirming novelty). Read this before
writing the intro — it changes the headline framing.

## Headline finding (the pivot)

**The real novelty adversary is Zheng & James 2011, not DCR.** The "we are two-way,
DCR is one-way" story you may have thought was the headline is **largely preempted**
and must be retired as the lead claim. Here is the chain:

- DCR (Coevoet et al. 2020) is *explicitly* the cheap, real-time, **one-way**
  approximation of an expensive **two-way** predecessor — and DCR §2 cites that
  predecessor by name: **Zheng & James, "Toward High-Quality Modal Contact Sound,"
  SIGGRAPH/TOG 2011.**
- Zheng-James 2011 already: carries modal amplitudes as generalized-coordinate
  solver DOFs; uses **one shared contact multiplier** that drives *both* the rigid
  and modal parts (two-way, momentum-conserving by construction); adaptively
  activates modes by modal energy; and lets **stacks transmit vibration through
  their contacts.** That is the core mechanism this project calls its two-way
  generalization.

So "first two-way rigid↔modal contact coupling" / "first to make modal amplitudes
native contact DOFs" / "first momentum-conserving-by-construction shared multiplier"
are **not claimable.** Zheng-James did the mechanism (offline); Sheth 2015 and
classical FFRF did it too. The constraint-based two-way coupling is **less rare than
it looks.**

## The three-way positioning (the clearest way to state it)

Verified against primary sources: Zheng-James's abstract ("resolve modal vibrations
in **both** collision and frictional contact processing stages") and — decisively —
the **DCR paper's own related work** (Coevoet et al., a co-author is the PI): Zheng-
James "take all contacts ... into account, and produce **coupled motions** that would
not otherwise be produced in a rigid body simulation ... only produced with a **large
computational cost**." DCR §4 confirms itself one-way: it injects a distant-response
`Δv` and "our simulations remain rigid as we do not seek to visualize any deformation
of the surface." So:

| | two-way | real-time | passivity bound |
|---|:--:|:--:|:--:|
| Zheng-James 2011 | ✅ | ❌ (offline, "large cost") | ❌ (damping only) |
| DCR 2020 | ❌ (one-way inject) | ✅ | ❌ |
| **This project** | ✅ | ✅ | ✅ |

**Do NOT claim the two-way coupling as the novelty — Zheng-James 2011 has it.** The
defensible claim is the empty cell: *two-way AND real-time AND passive in one solver.*
DCR made Zheng-James cheap by dropping two-way; this project keeps two-way at real-time
cost (modes as native AL constraints) and adds the passivity guarantee neither had.

## What survives — the two genuinely unoccupied axes

Every one of the three clusters independently landed on the *same* two survivable
contributions:

1. **The enforced, directional passivity bound** `ΔE_modal ≤ η·ΔE_rigid_loss` on the
   contact→modal transfer. **Absent from the entire literature.** Zheng-James uses
   *dissipative damping* (energy leaks out, not a cap on injection); the Betsch/Hesch
   energy-momentum integrators *conserve* (`ΔE=0` equality, symmetric, no η) rather
   than *cap* directionally; port-Hamiltonian multibody (Brugnoli 2021) and haptic
   TDPA (Hannaford-Ryu 2002) give the passivity-inequality *genre* but not this
   specific contact→modal transfer budget. **This is the cleanest air.**
2. **Vibration modes as native compliant-constraint DOFs inside a real-time
   position-based / augmented-Lagrangian rigid solver (XPBD / AVBD / VBD).**
   Zheng-James is an *offline* velocity-level LCP/QP (Staggered Projections); the
   real-time-AL host is unoccupied. AVBD/VBD/XPBD host rigid+soft contact but carry
   **no modal DOFs** — the slot is empty.

A weaker third (the body-body **modal contact network**) is real but *not* first —
Zheng-James stacks already ring — so frame it as "generalized *and passivity-bounded*
across a body-body network," never "first network."

### Sharpening (important): it is the solver *class*, not "constraint formulation"

Zheng-James is **already a constraint formulation** — Staggered Projections is a
velocity-level LCP/QP, contact impulses are the complementarity multipliers, modal
DOFs live in that constrained system. So **do not claim "first constraint
formulation."** The real, defensible axis is the **class of constraint solver**:

- Zheng-James = a **global LCP/QP solved (near-)to convergence** (offline, expensive
  — the family DCR exists to avoid).
- This project = a **local, fixed-low-iteration, GPU-parallel position-based /
  augmented-Lagrangian** solver (XPBD/AVBD/VBD) — the real-time game family.

**Why this is a contribution, not a port.** A global QP absorbs a stiff modal DOF
(`K_q ~ 10¹¹`) implicitly for free; a fixed-low-iteration *local* solver makes that
stiff, dense modal block **diverge** under naive Gauss-Seidel. Making it stable and
two-way there is real algorithmic content (engaged-gated block-GS, rejected
cross-term Schur, under-relaxation, Woodbury/Schur condensation, `modal_relax`) that
Zheng-James never faced.

**The unifying narrative (bind the two axes into one claim).** The real-time regime
*creates* the failure mode the offline convergent solver never had: because the
solver under-converges, it can **inject energy** into the modes (X1: up to 119,534×
at low iteration budget; clamp inert at high budget). The passivity bound is not a
separate feature — it is **what makes real-time modal contact safe**. Zheng-James
didn't need it (convergent QP + dissipative damping); this project needs it *because*
it is fast. Frame the paper as: *"we bring two-way modal contact into the real-time
augmented-Lagrangian regime, which introduces an energy-injection failure mode absent
offline, and the enforced passivity bound `ΔE_modal ≤ η·ΔE_rigid_loss` is the fix that
makes it usable."* One story, not a port plus a bound. Do not lean on the real-time
leg alone — it is the more attackable one ("incremental port to XPBD"); the passivity
bound is the leg no prior work has.

## Differentiation table

Axes: **DOF** = modal amplitude a native solver DOF · **2-way** = shared unilateral
contact multiplier excites modes *and* reacts on bodies · **Modal** = vibration
eigenmodes (vs affine/frames/full-space) · **Passive** = enforced energy-transfer
*inequality* (not just conservation/damping) · **RT-AL** = real-time position-based/
augmented-Lagrangian host · **Network** = body-body vibration through contact.

| Work | DOF | 2-way | Modal | Passive | RT-AL | Network |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| **This project** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Zheng & James 2011 (modal contact sound) | ✅ | ✅ | ✅ | ❌ (damping) | ❌ (offline LCP/QP) | ✅ |
| DCR — Coevoet 2020 (the base) | ❌ (sep. IIR) | ❌ (1-way inject) | ✅ | ❌ | ✅ | ❌ |
| Sheth, Lu, Yu, Fedkiw 2015 | ✅ | ✅ | ✅-capable | ❌ (momentum, not energy) | ❌ | partial |
| ABD — Lan et al. 2022 | ✅ | ✅ (IPC barrier) | ❌ (affine) | ❌ | ❌ (IPC/Newton) | ✅ |
| FFRF / CMS + energy-momentum (Shabana; Betsch/Uhlar; contact-impact CMS 2013) | ✅ | ✅ | ✅ | ❌ (conserves≠caps) | ❌ (offline) | ✅ |
| Port-Hamiltonian FMB — Brugnoli 2021 | ✅ | ✅ | ✅ | genre only | ❌ | ❌ |
| AVBD/VBD 2024–25 · XPBD 2016 (the host) | ❌ | ✅ (rigid/soft) | ❌ | ❌ | ✅ | ✅ |
| DyRT — James & Pai 2002 | ✅ (deformable) | ❌ (display) | ✅ | ❌ | ✅ | ❌ |

Only the top row is all-✅; the discriminating columns are **Passive** and **RT-AL**
(no prior row has both), which is the paper's novelty surface.

## Rarity verdict

Cluster coverage of the target (10 = someone basically did it): classical
multibody/passivity **7/10**, reduced-DOF solvers/ABD **6/10**, graphics modal/sound
**6/10**. So the **formulation as a whole is only modestly novel (~3–4/10 "rare")** —
its mechanism is well-covered — but the **two surviving axes (passivity bound +
real-time-AL embedding) are cleanly unoccupied**, which is a sufficient, defensible
contribution *if the framing pivots to them.*

Net: publishability holds at ~6/10 **conditional on the pivot**. If the intro leads
with "two-way vs DCR," a reviewer who knows Zheng-James can reject for lack of
novelty → ~4. If it leads with "passivity-bounded modal contact brought into the
real-time AL regime, narrowing the Zheng-James gap DCR only approximates one-way,"
it holds at 6, maybe 6.5.

## Do / don't for the paper

**Don't claim:** first two-way rigid↔modal contact · first modal amplitudes as
contact DOFs · momentum-conservation-by-construction as novel · "unlike DCR, two-way"
as the headline.

**Do claim:** (1) an **enforced per-step passivity inequality** bounding contact→modal
energy transfer, absent in all prior modal-contact work; (2) vibration modes as
**first-class compliant-constraint DOFs in a real-time position-based/AL rigid solver
(XPBD/AVBD/VBD, GPU-resident)** — Zheng-James's two-way coupling brought from offline
LCP/QP into the real-time regime; (3) that guarantee generalized across a **body-body
modal contact network**; (4) validated against a full-FEM ground truth.

## Candidate intro sentence

> "Zheng & James [2011] carry modal amplitudes as generalized coordinates driven
> two-way by a single shared contact multiplier — but only in an *offline*
> velocity-level solver with merely *dissipative* damping; DCR [Coevoet 2020]
> approximates that coupling *one-way* for real time. We instead embed vibration
> modes as first-class **compliant-constraint DOFs inside a real-time augmented-
> Lagrangian rigid solver**, where one unilateral contact multiplier excites the
> modes and reacts on the bodies within the same iteration under an **enforced
> passivity bound** `ΔE_modal ≤ η·ΔE_rigid_loss`, generalized to a body-body modal
> contact network — neither the real-time-AL embedding nor the passivity bound
> exists in prior work."

## Must-cite adversaries (related work)

- **Zheng & James 2011**, *Toward High-Quality Modal Contact Sound*, TOG/SIGGRAPH —
  the true two-way predecessor. cs.cornell.edu/projects/Sound/mc/
- **Coevoet, Andrews, Relles, Kry 2020**, *Distant Collision Response*, CGF/SCA — base.
- **Sheth, Lu, Yu, Fedkiw 2015**, *Fully Momentum-Conserving Reduced Deformable
  Bodies…*, SCA — two-way, conserves momentum (not energy). dl.acm.org/10.1145/2786784.2786787
- **Lan, Kaufman, Li, Jiang, Yang 2022**, *Affine Body Dynamics*, SIGGRAPH — reduced
  body as native contact DOF (affine, IPC, no passivity). arxiv.org/abs/2201.10022
- **Shabana**, *Dynamics of Multibody Systems* (FFRF); **Betsch & Uhlar 2007** /
  **Uhlar-Betsch** energy-momentum modally-reduced FMB; contact-impact CMS (Acta
  Mech. Sinica 2013) — classical two-way modal+contact, conserving not capping.
- **Brugnoli, Alazard, Pommier-Budinger, Matignon 2021**, *Port-Hamiltonian flexible
  multibody dynamics*, MSD — the passivity-inequality genre.
- **Giles, Diaz, Yuksel 2025** (AVBD, SIGGRAPH) / **Chen et al. 2024** (VBD) /
  **Macklin et al. 2016** (XPBD) — the real-time-AL host family.
- **James & Pai 2002** (DyRT) — one-way real-time modal, the graphics precedent.

## Addendum (2026-07-10): the transcription itself is not a contribution either

Verified and folded into the paper (commit d5035fc on `paper`). One linearization
step of the position-level gap row gives `C^{n+1} ≈ C^n + h·J·u^{n+1}`; divided by
`h` this is the velocity-level rigid–modal complementarity with a `C^n/h`
stabilization bias — the same shared Jacobian and multiplier as Zheng-James's
collision stage (velocity-level Staggered Projections, re-verified against the
Cornell project page). So "we write the constraint at position level" is a one-line
rewrite, not novelty, and the paper now says so openly (abstract, §1 contribution 2,
§2, §3.1 "Relation to the velocity-level law" = Eq. 5, §5 limitation 1).

Two scope facts sharpened during verification (both now in the paper):

- Ours is **narrower** than Zheng-James's law, not "the same constraint": modes
  couple through the normal rows only (code: friction is body-local, "no modal
  hub"), while Z-J resolve vibration in the friction stage as well.
- Velocity-level systems take Newton restitution directly (DCR adds it in `b`,
  their Eq. 4); the position-level row gives e=0 — the price of the rewrite. Z-J's
  own restitution treatment is unverified (project page silent), so the paper
  states this at formulation-class level only, never about "their law".

Net framing as worded in the paper: we do not introduce a new two-way modal-contact
law; its direct transcription into fixed-budget AL/PBD hosts is not energy-safe
(measured: XPBD injects in 12/24 cells, 5.5e4–9.2e6 J; the cross-term Schur variant
injects 9.4e3 J at 4×1; relax ≥0.65 NaNs), and the contributions are the solver
couplings (§3.2) plus the cumulative passivity projection (§3.3) — enforced on
realized modal state at the velocity/energy level, i.e. the architecture is
deliberately two-level (position-level contact, energy-level controller).

## Addendum (2026-07-18): recheck after the velocity-impulse backend

Second adversarial sweep, triggered by adding the `impulse` backend (branch
`impulse-native-constraint`): the same row + ledger now also run in a classical
velocity-level Schur/PGS solver — i.e. **Zheng-James's own solver class**. 5 search
angles, 17 sources, 79 claims, 25 adversarially verified (18 confirmed 3-0, 1
refuted, 6 unverified — verification ran out of budget on the last batch, see
caveats). Verdicts:

**RQ1 — reduced/modal DOFs inside a real-time fixed-iteration velocity-impulse
solver: NO CONFIRMED SCOOP, with one residual risk.**
- *Sheth, Lu, Yu, Fedkiw 2015* (SCA) — the closest neighbour. The claim that it
  scoops us was **refuted 1-2**: the recoverable record describes impulses remapped
  into the subspace to control per-node velocities, not reduced amplitudes as extra
  unknowns/columns in a shared-multiplier fixed-iteration PGS/Delassus solve, and it
  makes no real-time/game-engine claim. **Residual risk: full text was unretrievable**
  — solver internals (iteration budget, LCP structure) remain unverified. Get the PDF
  before the camera-ready; this is the single most likely place to be scooped.
- *Zobel, Zwölfer, Weber, Rixen 2025* (Multibody System Dynamics) — real-time FFRF
  flexible bodies **inside Unity**: adjacent territory, but contact is a **penalty**
  formulation with ray-traced search, and contact force / EoM are solved in
  **decoupled stages** (Update → LateUpdate) — no shared unilateral multiplier. Does
  not scoop; must cite as the closest "flexible bodies in a game engine" work.
- CMS-reduced flexible bodies coupled through **bilateral joints** (ScienceDirect
  S088832702030131X, 2020) — no unilateral contact/complementarity at all.

**RQ2 — the directional passivity cap: STILL CLEAN, but two 2026 neighbours now
exist and both must be cited and distinguished.**
- *You, Zheng, Li 2026* (arXiv 2602.08094), **Energy-Controllable Time Integration
  for Elastodynamic Contact** — an "A-search" implicit-Euler modification tracking
  **user-specified TOTAL-energy targets** (bidirectional: dissipation *or*
  conservation). Categorically different from a one-directional cap on
  contact→modal transfer, but it is the nearest 2026 "energy control for contact"
  work and a reviewer will know it. Operates on full nonlinear elastodynamics with
  IPC barriers — occupies neither the impulse nor the modal-DOF axis.
- *arXiv 2603.16424* (2026, port-Hamiltonian co-simulation) — **the most important
  new adversary.** It states outright that *"finite-iteration coupling across the
  partition boundary can inject spurious energy, even when each subsystem is
  passive"* and guarantees *"discrete passivity … for any finite inner-iteration
  budget"*. That is structurally our under-convergence-injection story. **Weakens the
  "we identify under-convergence as an energy-injection mechanism" framing** — do not
  claim that observation as novel. Its mechanism is passivity-**by-construction** via
  Douglas–Rachford operator splitting (Fejér monotonicity as algorithmic dissipation)
  on **bilateral** coupling interfaces of robotic systems — not a directional transfer
  cap with a reservoir ledger and state projection, and not unilateral contact. Under
  our own taxonomy (conservation/dissipation/stability don't count) it does **not**
  scoop the cap — but the *motivation sentence* is now shared prior art.
- Confirmed non-scoops: Sheth 2015 guarantees **momentum** only; friction-sound
  synthesis (Avanzini) has only A-stability of a bilinear transform; neural modal
  resonators (arXiv 2210.15306) only constrain filter poles inside the unit circle.

**RQ3 — modal DOFs in position-based / AL hosts: NO LONGER FULLY CLEAN.**
- *Mercier-Aubin & Kry 2024* (SCA/CGF 43(8)) — "reduced models" in XPBD are
  **dynamically rigidified vertex clusters**, not eigenmodes. Slot clean w.r.t. it.
- **But** *Robotics and Autonomous Systems 2024* (10.1016/j.robot.2024.104650)
  builds a reduced-order **XPBD** model from **linear vibration modes + modal
  derivatives** (soft-robot deformation reduction, confirmed 2-0). So "vibration
  modes inside an XPBD host" is **occupied** in the reduction sense. Ours remains
  distinct — modes as *contact-constraint* DOFs driven by a shared unilateral
  multiplier, not a deformation surrogate — but the sentence must be narrowed
  accordingly. Never write "first modal DOFs in XPBD"; write "first as contact DOFs".

**RQ4 — MIG 2026 (3 independent sources agree; adversarial votes errored on budget,
so treat as unverified-but-corroborated):** 11–13 December 2026, Clemson University
Innovation Campus, N. Charleston, SC. **Submission window 25 July – 7 August 2026,
23:59 AoE** — i.e. ~3 weeks out as of this addendum. Verify on mig.siggraph.org
before relying on it.

### Bottom line

The novelty framing **survives** the impulse backend, with two required edits:

1. **Frame the impulse backend as baseline/validation, never contribution.** It is
   Zheng-James's own solver class; its value is that it makes the paper a
   *cross-solver-class* study (velocity-impulse / AL / position-based, one row, one
   ledger) and it sharpens the formulation-vs-iteration argument — the implicit modal
   weight `(M+hD+h²K)⁻¹` is stable at `modal_relax = 1.0` with no under-relaxation,
   where XPBD's measured GS ceiling is 0.25. Do not claim it is real-time: measured
   14.9–32.4 ms/step in numpy on CPU (0.3–0.6× at h=1/120), matching the AVBD **CPU**
   host path; the real-time evidence remains the CUDA AVBD path.
2. **Retire "we identify the under-convergence injection failure mode" as a novel
   observation** (arXiv 2603.16424 says it plainly, 2026). Keep the *measurement* on
   unilateral contact→modal transfer (that is still ours and is quantitative), and
   keep the **directional cap with reservoir ledger + γ-projection** as the headline
   — still unoccupied after this sweep.

Caveats on this sweep: 19 of 99 agents errored on a billing limit, so 6 claims
carry 0–1 valid votes (marked unverified above) and the automated synthesis step
did not run — this section is a hand-synthesis of the confirmed set. Two absence
claims rest on abstracts/metadata because the full texts are paywalled
(S0094114X24002015, robot.2024.104650). The Sheth 2015 full text is the one gap
worth closing by hand.
