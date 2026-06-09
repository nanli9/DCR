#!/usr/bin/env python3
"""Box-box penetration in the truck lumber stack — is it the AVBD solver,
or the DCR patch kicks?

The patch kicks (_apply_patch_kicks) are applied as RAW post-solve velocity
changes that bypass the box-box contact constraints. The receiver is the
block in contact with the elastic floor = the BOTTOM block. A (mostly
upward) moving-support kick on the bottom block drives it into the block
above, and that penetrating velocity is only seen by AVBD next step.

If that's the cause: penetration is worst at the BOTTOM pair, survives high
iters+substeps, and vanishes when the kicks are off (eta=0)."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import build_truck_scene


def run(iters, substeps, eta, n_steps=300):
    world, coupler, boxes, mesh, _ = build_truck_scene(
        device="cpu", h=1.0/120.0, eta=eta, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
    world._solver.substeps = int(substeps)
    lum = sorted(
        [b.body_idx for b in boxes if b.name.startswith("lumber_")],
        key=lambda i: world._descs[i].dcr_body.position[1])
    he_y = next(b.half_extents[1] for b in boxes if b.name == "lumber_0")
    contact_gap = 2.0 * he_y
    # worst overlap per adjacent pair (0 = bottom-2nd, ... top-1 pairs)
    worst = [0.0] * (len(lum) - 1)
    for _ in range(n_steps):
        world.step()
        ys = [float(world._descs[i].dcr_body.position[1]) for i in lum]
        for p in range(len(lum) - 1):
            worst[p] = max(worst[p], contact_gap - (ys[p + 1] - ys[p]))
    return worst


def main():
    print("lumber stack (bottom→top pairs), worst box-box overlap (mm):\n")
    print(f"{'config':<40} {'bottom':>8} {'mid':>8} {'top':>8}")
    for label, it, sub, eta in [
        ("iters=10 sub=4  eta=0.5 (default)", 10, 4, 0.5),
        ("iters=40 sub=8  eta=0.5 (max knobs)", 40, 8, 0.5),
        ("iters=40 sub=8  eta=0.0 (no DCR kicks)", 40, 8, 0.0),
        ("iters=10 sub=4  eta=0.0 (no DCR kicks)", 10, 4, 0.0),
    ]:
        w = run(it, sub, eta)
        cells = " ".join(f"{x*1000:>8.3f}" for x in w)
        print(f"{label:<40} {cells}")


if __name__ == "__main__":
    main()
