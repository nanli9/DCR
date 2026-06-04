#!/usr/bin/env python3
"""Why does only the truck scene run away? Compare all three scenes:
FEM material, modal band, how many bodies actually rest on the elastic
surface, and peak E_modal with the patch back-reaction ON vs DISABLED
(the on/off ratio = how hard the leak is pumping)."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import (
    build_shelf_scene, build_ledge_scene, build_truck_scene)
from dcr.modal.energy import modal_energy

BUILDERS = {"shelf": build_shelf_scene,
            "ledge": build_ledge_scene,
            "truck": build_truck_scene}


def run(name, disable_backreaction, n_steps=360):
    world, coupler, boxes, mesh, _ = BUILDERS[name](
        device="cpu", h=1.0 / 120.0, eta=0.5, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    eb = coupler.elastic_body_idx
    freqs = coupler.modal.frequencies
    stp = coupler._stepper
    fem = coupler.modal.fem

    if disable_backreaction:
        orig = coupler._compute_distant_response_patch

        def wrapped(*a, **kw):
            snap = stp.qdot.copy()
            out = orig(*a, **kw)
            stp.qdot[:] = snap
            return out
        coupler._compute_distant_response_patch = wrapped

    peakE = 0.0
    rest_counts = []
    for k in range(n_steps):
        world.step()
        peakE = max(peakE, float(modal_energy(stp.q, stp.qdot, freqs)))
        if k >= n_steps - 120:  # steady-state window
            rest_counts.append(sum(
                1 for c in world.last_contacts
                if (c.body_a == eb or c.body_b == eb) and not c.is_new))
    info = dict(
        rho=float(fem.material.rho), E=float(fem.material.E),
        alpha0=float(fem.alpha0), nmodes=len(freqs),
        fmin=float(freqs.min() / (2 * np.pi)),
        fmax=float(freqs.max() / (2 * np.pi)),
        nbodies=len(boxes),
        rest=float(np.mean(rest_counts)) if rest_counts else 0.0,
        peakE=peakE)
    return info


def main():
    print(f"{'scene':6} {'E(GPa)':>7} {'rho':>6} {'a0':>4} {'modes':>5} "
          f"{'f_band(Hz)':>16} {'#bod':>5} {'restC':>6} "
          f"{'peakE_ON':>11} {'peakE_OFF':>11} {'pump×':>9}")
    for name in ("shelf", "ledge", "truck"):
        on = run(name, disable_backreaction=False)
        off = run(name, disable_backreaction=True)
        ratio = on['peakE'] / max(off['peakE'], 1e-12)
        print(f"{name:6} {on['E']/1e9:>7.1f} {on['rho']:>6.0f} "
              f"{on['alpha0']:>4.1f} {on['nmodes']:>5d} "
              f"{on['fmin']:>6.0f}-{on['fmax']:<8.0f} {on['nbodies']:>5d} "
              f"{on['rest']:>6.1f} {on['peakE']:>11.3e} "
              f"{off['peakE']:>11.3e} {ratio:>9.1f}")


if __name__ == "__main__":
    main()
