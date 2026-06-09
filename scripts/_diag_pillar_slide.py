#!/usr/bin/env python3
"""WHY do the pillars slide on the pedestal ("box surface") as if frictionless?

Box-box μ = sqrt(μ_a·μ_b) ≈ 0.45 here (NOT zero), and the user says it is
insensitive to iters/substeps — so it is not the coefficient or convergence.
Hypothesis: the pedestal is a COUPLER-tracked body (it has a floor contact);
the coupler overwrites its pose each AVBD iteration with a floor-only Schur
step that ignores the box-box contacts + friction of the pillars resting ON it
→ the pedestal slips out from under the pillars → apparent frictionless slide.

Discriminators (user params: thickness 0.1 m, boulder 50 kg, drop 0.8, v0 0, wood):
  BASELINE     : ped μ=0.4, pillar μ=0.5, coupler ON
  HIGH_FRIC    : ped μ=1.0, pillar μ=1.0, coupler ON   (does μ even matter?)
  COUPLER_OFF  : baseline μ, hooks nulled → pedestal on a RIGID floor
Metric: per-pillar horizontal slide relative to the PEDESTAL (px-pedx, pz-pedz)
— the true relative slip on the contact surface — plus pillar height (on the
pedestal y≈0.20 vs fallen to floor y≈0.05) and tilt.
"""
from __future__ import annotations
import argparse
import numpy as np

from dcr.avbd.world import AVBDDCRWorld
from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, build_support_and_attach, ReducedSceneHandle)


def build(*, device, thickness=0.1, ped_fric=0.4, pillar_fric=0.5,
          iterations=4, substeps=4):
    top = 0.04
    world = AVBDDCRWorld(h=1.0 / 120.0, device=device,
                         avbd_iterations=iterations, avbd_substeps=substeps)
    world.add_floor(floor_y=top, friction=0.5, name="ledge")
    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add
    resting_xz = []
    ped_h = (0.09, 0.045, 0.09)
    ped_idx = add("pedestal", 5.0, ped_h, (0.0, top + ped_h[1] + 0.001, 0.0),
                  (0.55, 0.52, 0.47), "box", friction=ped_fric)
    resting_xz.append((0.0, 0.0))
    pillar_h = (0.012, 0.05, 0.012)
    pedestal_top = top + 2 * ped_h[1] + 0.001
    pil_idx = []
    for si, sz in enumerate([-0.035, 0.0, 0.035]):
        pi = add(f"pillar_{si}", 0.5, pillar_h,
                 (0.0, pedestal_top + pillar_h[1] + 0.001, sz),
                 (0.7, 0.65, 0.6), "pillar", friction=pillar_fric)
        pil_idx.append(pi); resting_xz.append((0.0, sz))
    br = 0.08
    imp = add("boulder", 50.0, (br, br, br), (0.30, top + br + 0.8, 0.0),
              (0.42, 0.38, 0.32), "boulder", friction=0.5)
    resting_xz.append((0.30, 0.0))
    contact_zones = [(0.30, 0.0)] + resting_xz
    rs = build_support_and_attach(
        world, bodies, support_length=1.2, support_width=0.8,
        support_thickness=thickness, support_top=top, youngs=1.0e10,
        density=600.0, poisson=0.30, n_modes_global=12, n_modes_local=16,
        contact_zones=contact_zones, probe_xz=resting_xz,
        rayleigh_alpha0=2.0, rayleigh_alpha1=1.0e-5, modal_impedance_scale=1.0,
        modal_damping_scale=1.0, to_eigenbasis=True, modal_static_lp_tau=0.05)
    h = ReducedSceneHandle(world=world, rs=rs, impactor_idx=imp,
                           probe_indices=pil_idx, bodies=bodies, name="ledge")
    h.ped_idx = ped_idx
    return h


def run(label, *, device, coupler_off=False, n=900, **kw):
    h = build(device=device, **kw)
    w = h.world; bod = w.bodies; ped = h.ped_idx; pil = h.probe_indices
    if coupler_off:
        w._solver.substep_begin_hook = None
        w._solver.iteration_hook = None
        w._solver.substep_end_hook = None
        w._solver.hooks_device_resident = False
    rel = np.zeros((n, len(pil)))     # horizontal slip of pillar rel pedestal
    pily = np.zeros((n, len(pil)))
    pedx = np.zeros((n, 2))
    rel0 = None
    for k in range(n):
        w.step()
        pp = np.asarray(bod[ped].position, float)
        pedx[k] = [pp[0], pp[2]]
        for j, pi in enumerate(pil):
            q = np.asarray(bod[pi].position, float)
            d = np.array([q[0] - pp[0], q[2] - pp[2]])
            if rel0 is None:
                pass
            rel[k, j] = np.linalg.norm(d)
            pily[k, j] = q[1]
    # slip = change in pillar-rel-pedestal horizontal offset from its rest value
    slip = rel - rel[0:1, :]
    print(f"\n{label}  (device={device})")
    print(f"  {'window':<12}{'maxRelSlip_mm':>14}{'pedDrift_mm':>12}"
          f"{'pil_y_min':>10}{'onPedestal?':>12}")
    for lo, hi in [(60, 200), (200, 500), (500, n)]:
        s = slice(lo, hi)
        max_slip = np.abs(slip[s]).max() * 1e3
        ped_drift = np.ptp(pedx[s], axis=0)
        ped_drift = float(np.hypot(*ped_drift)) * 1e3
        ymin = float(pily[s].min())
        on_ped = "yes" if ymin > 0.14 else "FELL"
        print(f"  {f'{lo}-{hi}':<12}{max_slip:>14.3f}{ped_drift:>12.4f}"
              f"{ymin:>10.4f}{on_ped:>12}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--n", type=int, default=900)
    a = ap.parse_args()
    print("Pillar slide on pedestal. RelSlip = |pillar−pedestal| horizontal "
          "change from rest [mm] (true contact-surface slip). pedDrift = how "
          "far the pedestal itself moved [mm].")
    run("BASELINE (ped0.4/pil0.5, coupler ON)", device=a.device, n=a.n)
    run("HIGH_FRIC (ped1.0/pil1.0, coupler ON)", device=a.device, n=a.n,
        ped_fric=1.0, pillar_fric=1.0)
    run("COUPLER_OFF (rigid floor)", device=a.device, n=a.n, coupler_off=True)


if __name__ == "__main__":
    main()
