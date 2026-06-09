#!/usr/bin/env python3
"""Deep-dive: GPU limit-cycle persistence + pillar→boulder coupling on the
reduced-coupled ledge.

Claims under test (headless, lead with measurement):
  P1 persistence : does the boulder buzz PERSIST (constant-amplitude limit
                   cycle) over ~20 s, or decay? GPU vs CPU.
  P2 pillar→boulder : a 0.5 kg pillar should barely move a 50 kg boulder. Does
                   pillar activity (topple) increase boulder vy? Test via
                   (a) BOULDER_ONLY vs FULL late buzz, and (b) correlation of
                   |boulder vy| with max pillar speed in FULL.

Run: uv run python scripts/_diag_ledge_deepdive.py --device cuda:0
"""
from __future__ import annotations

import argparse
import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from scenes.reduced_scene_common import BodyAdder, ReducedSceneBody, \
    build_support_and_attach, ReducedSceneHandle


def build_ledge(*, with_stack: bool, device: str, iterations=4, substeps=4,
                youngs=1.0e10, density=600.0) -> ReducedSceneHandle:
    """Replica of scenes.reduced_ledge.build_reduced_ledge with a switch to
    drop the pedestal+pillars (BOULDER_ONLY). Kept in-sync deliberately so the
    only difference vs FULL is the stack."""
    top = 0.04
    world = AVBDDCRWorld(h=1.0 / 120.0, device=device,
                         avbd_iterations=iterations, avbd_substeps=substeps)
    world.add_floor(floor_y=top, friction=0.5, name="ledge")
    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    resting_xz: list[tuple[float, float]] = []

    if with_stack:
        ped_h = (0.09, 0.045, 0.09)
        add("pedestal", 5.0, ped_h, (0.0, top + ped_h[1] + 0.001, 0.0),
            (0.55, 0.52, 0.47), "box", friction=0.4)
        resting_xz.append((0.0, 0.0))
        pillar_h = (0.012, 0.05, 0.012)
        pedestal_top = top + 2 * ped_h[1] + 0.001
        for si, sz in enumerate([-0.035, 0.0, 0.035]):
            add(f"pillar_{si}", 0.5, pillar_h,
                (0.0, pedestal_top + pillar_h[1] + 0.001, sz),
                (0.7, 0.65, 0.6), "pillar", friction=0.5)
            resting_xz.append((0.0, sz))

    br = 0.08
    impactor_idx = add("boulder", 50.0, (br, br, br),
                       (0.30, top + br + 0.8, 0.0), (0.42, 0.38, 0.32),
                       "boulder", friction=0.5)
    resting_xz.append((0.30, 0.0))
    contact_zones = [(0.30, 0.0)] + resting_xz
    rs = build_support_and_attach(
        world, bodies, support_length=1.2, support_width=0.8,
        support_thickness=0.08, support_top=top, youngs=youngs,
        density=density, poisson=0.30, n_modes_global=12, n_modes_local=16,
        contact_zones=contact_zones, probe_xz=resting_xz,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5,
        modal_impedance_scale=1.0, modal_damping_scale=1.0,
        to_eigenbasis=True, modal_static_lp_tau=0.05)
    return ReducedSceneHandle(
        world=world, rs=rs, impactor_idx=impactor_idx,
        probe_indices=[b.dcr_idx for b in bodies if b.render_kind == "pillar"],
        bodies=bodies, name="ledge", impactor_label="boulder")


def run(label, *, with_stack, device, n=2400):
    h = build_ledge(with_stack=with_stack, device=device)
    w = h.world
    b = h.impactor_idx
    pillars = h.probe_indices
    bod = w.bodies
    vy = np.zeros(n)
    pil = np.zeros(n)
    for k in range(n):
        w.step()
        vy[k] = float(bod[b].velocity[1])
        if pillars:
            pil[k] = max(float(np.linalg.norm(bod[p].velocity[:3]))
                         for p in pillars)
    return label, vy, pil


def windows(vy, n):
    out = []
    for lo, hi in [(120, 300), (600, 900), (1200, 1500),
                   (1800, 2100), (max(0, n - 300), n)]:
        seg = vy[lo:hi]
        nz = seg[np.abs(seg) > 1e-9]
        fl = int(np.sum(np.diff(np.sign(nz)) != 0)) if len(nz) > 1 else 0
        out.append((f"{lo}-{hi}", np.std(seg), np.max(np.abs(seg)), fl))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=2400)
    a = ap.parse_args()
    n = a.n

    runs = [
        run("FULL (stack) GPU ", with_stack=True, device=a.device, n=n),
        run("BOULDER_ONLY GPU ", with_stack=False, device=a.device, n=n),
        run("FULL (stack) CPU ", with_stack=True, device="cpu", n=n),
    ]
    print("\n=== P1 persistence: boulder vy_std/vy_max/flips per window "
          "(h=1/120 → step 2400 ≈ 20 s) ===")
    for label, vy, pil in runs:
        print(f"\n{label}")
        for nm, s, m, fl in windows(vy, n):
            print(f"   {nm:<12} vy_std={s:.2e} vy_max={m:.2e} flips={fl:>4d}")

    # P2: pillar→boulder coupling in FULL-GPU.
    label, vy, pil = runs[0]
    seg = slice(300, n)
    bv = np.abs(vy[seg])
    pv = pil[seg]
    if pv.std() > 0 and bv.std() > 0:
        corr = float(np.corrcoef(bv, pv)[0, 1])
    else:
        corr = float("nan")
    med = np.median(pv)
    active = vy[seg][pv > med]
    quiet = vy[seg][pv <= med]
    _, bo_vy, _ = runs[1]
    print("\n=== P2 pillar→boulder (FULL-GPU, steps 300-end) ===")
    print(f"   corr(|boulder vy|, max pillar speed)        = {corr:+.3f}")
    print(f"   boulder vy_std | pillar ACTIVE (pv>median)  = {np.std(active):.2e}")
    print(f"   boulder vy_std | pillar QUIET  (pv<=median) = {np.std(quiet):.2e}")
    print(f"   max pillar speed over run                   = {pil.max():.2e} m/s")
    print(f"   BOULDER_ONLY late vy_std (steps {n-300}-{n})    = "
          f"{np.std(bo_vy[n-300:n]):.2e}  vs FULL = {np.std(vy[n-300:n]):.2e}")


if __name__ == "__main__":
    main()
