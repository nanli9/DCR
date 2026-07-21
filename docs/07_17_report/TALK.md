# Oral walkthrough — 07/17 meeting (~7–8 min)

Pacing: each block ≈ the time shown. Scroll cue in [brackets]. Speak short
sentences; pause after each pin. Numbers below match the HTML exactly.

---

## Opening — 30 s  [page top]

Last time I showed you the one-way version. Since then I finished the two-way
coupling you asked for — and it came out cleaner than I expected. I didn't add
a coupling force. I made the contact constraint itself carry the modes. Let me
walk you through it: two minutes for the idea, then the evidence.

## Where we were — 30 s  [card 0]

Quick recap. Before, the contact solver ran on rigid bodies only. After the
solve, I fed the impulses into the modal oscillators. So the ring was just a
readout — the modes could never push back on any contact force. That's the
red crossed arrow here. One-way.

## The move — 2 min  [card 1, the two equations + diagram]

Here is the whole change. It's one substitution.

A contact constraint is a gap: the separation between two contact points must
stay non-negative. I just measure that gap at the **deformed** surface point —
rigid pose **plus** mode shapes times amplitudes.

Project it on the contact normal, and the row gains one linear term per body:
C-rigid, plus G-hat-A times a-A, minus G-hat-B times a-B. G-hat is simple —
one number per mode: how far unit amplitude of that mode moves the contact
point along the normal.

[point at the diagram] So one multiplier, lambda, now serves everything. The
modal amplitudes became extra **columns** in the contact Jacobian. They are
solver unknowns now, not a post-solve read.

And two things come for free. First, it's genuinely two-way: dC/da is not
zero, so when a mode flexes, the gap changes, so the force changes — inside
the same solve. Second, momentum: one lambda on one row means the force that
drives A's modes is exactly the reaction B feels. Newton's third law is in the
algebra. No correction step, no energy from nowhere.

## The network — 1 min  [card 2 + network diagram]

Here's the part I like most. The row is symmetric in A and B — nothing says B
must be the ground. A rigid body is just the case with zero modal columns. The
support contact from last time is the case with modes on one side only.

So cube-on-slab and cube-on-cube are the **same row type**. I gave every cube
its own modal analysis — its own FEM mesh, its own eigensolve, mass-normalized
modes. And vibration travels hop by hop through the contacts: slab, base, mid,
upper. [point at OFF panel] Turn the network off, the top cube is dead. And
the passivity bound is enforced globally across the whole network, not per
contact.

## Evidence: the contact forces — 90 s  [the pinned figure]

Three places to look on this figure.

**Pin one** — the four flat lines. These are running means of the contact
multipliers. They settle on exactly the weight above each joint: m-g, two m-g,
three m-g — within two percent, zero per-joint tuning. Adding modes to the
rows did not corrupt the statics. The multipliers are still real forces.

**Pin two** — the two-way proof. The top cube touches only the middle cube —
two hops from the slab. Network on: it rings. Network off: identically zero.
There is no other path. The ring can only arrive through the shared rows.

**Pin three** — the stack foot. Three m-g total, split unevenly toward the
corner the tower leans on. Load transfer is resolved corner by corner.

## Bonus — 20 s  [two-way KPI card]

One side effect I didn't design for: the modal compliance smooths the box-box
chatter. The force ripple drops from ±2.7 to ±1.5 newtons, and the mean stays
at m-g.

## Real-time — 90 s  [RTX 4090 card]

Performance. This is measured on my 4090 server — the same co-solve, fully
device-resident in CUDA. At 120 hertz, real-time means 8.3 milliseconds per
step.

At the production budget — sixteen iterations, four substeps — the scenes run
5.6 to 9.2 milliseconds. Ledge and shelf are real-time even there. The two
heaviest scenes sit at about 0.9 of real-time; drop them to sixteen-by-two and
the heaviest one runs 4.65 milliseconds — 1.8 times real-time.

I also stress-tested scale: 512 bodies runs 6.4 milliseconds at eight-by-one —
still real-time, and the cost grows about square-root of N. And the energy
ledger holds in all 38 measured device cells, with the clamp never firing.

## ABD — 30 s  [ABD card — skip unless time / he asks]

On ABD: it's wired in as a swappable basis. An affine cube drops into the same
rows, and the static ledger doesn't change — force balance doesn't care about
the basis. But the affine subspace can't represent bending modes, and it
showed a slow secular buildup I haven't governed yet. So modal Phi stays the
headline; ABD is a supported option.

## Close — 20 s  [last card]

So the whole method is three lines: deformed contact point, one shared
unilateral row, one lambda routed to every degree of freedom. Rigid is the
zero-column case, support is the one-sided case — that's why it's a network.
On top of this I have the global passivity ledger, all-FEM ground truth on
five scenes, and the real-time device path. That's the state of it.

---

## If he interrupts / likely questions

**"Visually it looks nearly the same as one-way."**  ← expect this one
Concede the pixels, pivot to causality:

> You're right — at true scale they look almost the same, and they should:
> the real flex is about ten microns. The difference isn't the pixels, it's
> the causality. One-way is open-loop — the modes are a movie driven by
> recorded impulses, so nothing in the scene can ever talk back to them.
> Three measurable consequences.
> First, forces: in one-way, the contact forces are bit-identical to a rigid
> sim — the modes never enter the solve. Here the joint forces come out of
> the same multiplier that drives the modes — that's why the ledger is exact
> and the box-box chatter halves.
> Second, causality: [flip the network checkbox] off, the top cube's ring is
> identically zero. Not smaller — zero.
> Third — and this one is live: [switch scene to "payload"] the same soft
> plate twice, side by side, true scale, no exaggeration. Both payloads ride
> the ring — the right one exactly the way the one-way scheme moved
> bystanders. The difference is the plate. Left, the payload is in the
> contact rows: the plate sags six millimeters under it, and after the
> impact it rings mass-loaded — detuned from four point nine hertz to one
> point six, and damped. Right, one-way: no sag, and the plate rings exactly
> like an empty plate — it even tosses the payload harder, twenty-one
> millimeters, because the payload's mass never damps the ring it's riding.
> It lifts three kilograms for free. No gain setting can fix that: sag,
> detune, and damping are back-reaction, and one-way has no path for it.

If he pushes "one-way looked more dramatic": that's because one-way is
unbounded — the forced IIR re-amplifies a sub-millisecond transient. Looking
similar but staying inside the energy budget is the feature, not the gap.
(`--inject-xpbd` shows what removing the bound looks like: blow-up.)

## Live demos (the flag question)

**Demo 1 — payload mass-loading A/B (the headline; TRUE SCALE, sliders at 1):**

```
.venv/bin/python scripts/run_native_scenes_viser.py --scene payload
```
- Two plates side by side, labeled in-scene. LEFT: payload in the contact rows
  (two-way). RIGHT: the previous one-way treatment — the payload RIDES the
  readout ring (anchor-follow, like the old bystanders; no interpenetration)
  but its weight/inertia never enter q. Only that differs; the impactor
  excites both.
- What to point at (measured): left plate pre-sags **−6.2 mm** under the
  payload; after impact the right plate rings **free at 4.9 Hz — identical to
  an empty plate** while the left rings **mass-loaded at 1.6 Hz, damped**.
  The right payload is **tossed 21 mm** by a ring its own mass never damped
  (3 kg lifted for free — the energy giveaway); the left rides the plate it
  sagged and calmed (**16 mm**, mostly the sag).
- The soft plate (~5 Hz) makes all of this visible with BOTH exaggeration
  sliders at 1 — say that out loud.
- "reset / rebuild" re-drops the impactor; the "speed" slider at ~0.25 is a
  live slow-mo for counting the beat difference.
- HUD line shows the payload-point deflection of both plates numerically.
- Static backup if the live run dies: `payload_ab.png` on the report page
  (same numbers, generated by `benchmarks/network/report_payload_ab.py`).

**Payload A/B — the complete difference inventory (all measured):**

| observable | two-way (left) | one-way (right) |
|---|---|---|
| sag under payload, pre-impact | −6.2 mm (1 kg: −1.8, 6 kg: −14.8) | 0.00 at every mass |
| payload rest height | sits visibly lower (sank with plate) | exactly at rest height |
| ring frequency at payload | 1.6 Hz mass-loaded heave | 4.9 Hz free — empty-plate identical |
| ring decay to 20% | 0.29 s (payload absorbs it) | 0.40 s (nothing may absorb it) |
| ring peak near payload | shrinks with mass: 10.7→6.8 mm (1→6 kg) | 14.54 mm — bit-identical at every mass |
| payload motion | 16 mm, "carried" (sag + heave); drops to 9 mm at 6 kg | tossed ~22 mm, ballistic; same at every mass |
| after settling | stays bowed ~−8.5 mm | returns to impactor-only sag −1.5 mm |
| energy | every mm of payload lift paid from the ring | lifts 3 kg repeatedly, zero J leaves the ring |
| momentum | payload force = reaction on plate (one λ) | payload momentum appears from nowhere |

Argue the **dependence**, not any single number: mass 1→6 kg moves every left
column entry; the right column does not change one digit. A damping knob can
fake the decay, a stiffness retune can fake one frequency — nothing can fake
a dependence on an object the formulation never sees.

Honest caveats (know before he finds them): decay alone IS imitable (say the
dependence line); the right side's clean ride hides brief free-fall gaps when
the surface drops faster than g — the soft plate makes one-way's hidden
inconsistency visible (in the old stiff scenes it was µm-invisible); the
measured detune (4.9→1.6 Hz) is for the 3 kg config — don't claim numerically
how detune scales with mass (FFT resolution + hop nonlinearity), claim the
sag/amplitude/rattle scaling instead, those are measured.

**Demo 2 — cargo stack network toggle (magnified):**

```
.venv/bin/python scripts/run_native_scenes_viser.py --scene cargo
```
- GUI checkbox **"modal contact network (stacked coupling)"** — flips the
  coupling live while it runs (AVBD). OFF ⇒ box-box rows carry no modal
  columns ⇒ the stacked cubes go structurally inert.
- Raise the **"cube flex ×"** slider to ~250 first (render-only magnification,
  true flex ~1e-5 m — say so out loud when you raise it).
- `--no-network` starts it OFF if you want the reveal in that order.
- Nuance if he asks "so OFF = your old one-way?": no — OFF is *no coupling at
  all* through box-box contacts. The one-way forced-IIR baseline is a different
  scheme; it's compared offline in the falloff figure (fig_x2, "one-way (D,
  forced IIR)"), not a live viewer mode. (The payload scene's right plate IS
  the honest one-way picture for the payload specifically.)
- Optional contrast: `--inject-xpbd` is the genuine blow-up preset — what the
  same coupling does with the bound starved.

**"What does the modal block cost?"**
Under a millisecond at production budgets — the table numbers already include
it. The step is dominated by the contact iterations, not the modes.

**"Restitution?"**
Honest limitation: the native path is e = 0 right now. The compliant row gives
contact softness, not bounce. It's on the list.

**"Momentum drift?"**
The host solver itself drifts at small iteration budgets — that's the
fixed-budget solver, not the coupling. With modes on versus off, the errors
match; the shared row adds nothing.

**"Friction sounds?" / "tangential?"**
Modal excitation comes from the normal rows only. Friction exists on the rigid
side, and the energy ledger subsumes it — passive at all four mu values I
tested. But no scrape or rolling excitation; I don't claim it.

**"Is the two-way mechanism novel?"**
No — and I don't claim it. Two-way modal contact exists offline, Zheng and
James being the closest. What I believe is new is the combination: native
modal columns in the shared rows of a fixed-budget real-time solver, plus a
directional energy bound — modal gain limited to a fraction of measured rigid
contact loss — enforced across the whole contact network. I did a hard
literature pass on this; the narrow claim survives, the broad ones don't.

**"How accurate is it against FEM?"**
Validated on the deflection field and modal frequencies against a
shared-operator all-FEM ground truth on five scenes. The honest caveat:
launch-amplitude observables are band-limited by the rigid timestep — I
validate the field, not the jump height.

---

## 60-second fallback (if time collapses)

Last meeting I had one-way response. Now the modes are inside the contact
constraint itself: the gap is measured on the deformed surface of both bodies,
so one shared multiplier pushes the rigid bodies apart and drives both bodies'
modes — two-way and momentum-consistent by construction. Every cube got its
own modal analysis, and cube-cube contact uses the same row as cube-ground, so
vibration travels through the stack: top cube rings with the network on,
dead-zero with it off. The contact-force ledger stays exact — every joint
carries the weight above it within two percent. And it's real-time on my 4090:
4.65 milliseconds for the heaviest scene at sixteen-by-two, 512 bodies at
6.4 milliseconds, energy bound holding in all 38 cells.
