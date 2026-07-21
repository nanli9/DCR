Subject: Two-way modal contact — corner contact forces

Hi Sheldon,

Quick update on the two-way coupling you suggested I explore — it works. I
generalized the modal response into a single shared contact constraint, so every
body carries its own modes and a stacked cube feels the ring of the cube beneath it
through the box-box contact. The same contact multiplier drives both cubes' modes
and the rigid motion, so it stays momentum-consistent.

I also pulled the actual contact forces at the corners, like you asked. Test scene: a
3-high stack plus a plain resting control cube, all on a modal slab. What I see:

- the plain resting cube shares its weight evenly across its 4 corners (≈ m·g/4 each);
- in the stack, each joint carries exactly the weight above it — resting → m·g,
  base → 3 m·g, base↔mid → 2 m·g, mid↔upper → m·g — within ~1–2%, with the ring
  modulation riding on top, and the stack foot's corners loaded unevenly where the
  tower leans.

Figure attached (contact force vs time, per corner and per joint). I also did a quick
check of whether ABD helps — happy to share that separately.

Happy to walk through any of it.

Best,
Nan
