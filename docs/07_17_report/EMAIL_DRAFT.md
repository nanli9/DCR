Subject: Two-way modal contact — corner contact forces in a cube stack (+ where ABD fits)

Hi Sheldon,

Following up on the two-way coupling you asked me to explore. Short version: I
generalized the modal response from a one-way support kick into a single shared
contact constraint, so *every* body carries its own modes and a stacked cube feels
the ring of the cube beneath it through the box-box contact — momentum-consistent
by construction (same multiplier pushes the rigid bodies apart and drives both
cubes' modes). Two figures attached; the contact forces are the headline.

**1. The corner contact forces balance the tower exactly (fig. contact_forces.png).**
Test scene: a reduced-modal slab holding a plain resting control cube, a dropped
impactor, and a 3-high zig-zag stack. Reading the contact multipliers directly:

- resting cube → slab: 5.89 N  (= m·g, 0.06% off)
- base cube → slab: 17.99 N   (= 3 m·g, 1.9%)
- base↔mid box-box: 11.93 N   (= 2 m·g, 1.4%)
- mid↔upper box-box: 5.82 N   (= m·g, 1.1%)

Each joint carries exactly the weight above it, no per-joint tuning. Panel (b) is
the plain resting cube — 4 corners share m·g/4 evenly. Panel (c) is the stack foot
— 3 m·g split *unevenly* across its corners (2.7→6.3 N) because the zig-zag tower
leans, which is what you'd want to see.

**2. It's genuinely two-way (panel d).** The top cube is two box-box hops from the
slab and touches only the cube under it. Network ON it rings; network OFF its modal
amplitude is identically zero. So the vibration reaching it arrives only through the
shared contacts. The modal compliance also smooths the box-box force (chatter
±2.72 N → ±1.48 N).

**3. On ABD (fig. abd_comparison.png).** I wired an ABD (affine 9-DOF) cargo cube in
and ran the same scene. It drops into the identical network — its corner Jacobian
just substitutes for the modal Φ. The static contact ledger is basis-independent
(rigid, modal, affine all hit the same m·g multiples), and the affine body does ring
through the network. But the affine subspace only captures uniform stretch/shear —
it can't represent the bending/plate modes that carry the distant response — so I'd
keep modal Φ as the primary basis and treat ABD as a swappable option / robust-
contact direction rather than a replacement. (One caveat: the affine flex showed a
slow secular buildup in the stack, so it'd need the same energy governor before I'd
claim anything about stability.)

Details + how to reproduce are in docs/sheldon_report/README.md. Happy to walk
through any of it.

Best,
Nan
