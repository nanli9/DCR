#!/usr/bin/env python3
"""Instrument the impact window: show the AVBD dual-variable (lam) impulse
magnitudes handed to the coupler at NEW contacts on the elastic shelf, vs
the 1e-3 impulse_threshold that gates the modal kick. Compares a healthy
config (iters=10) against the user's (iters=4, high substeps)."""
from __future__ import annotations
import sys
import numpy as np
from scripts.run_scenes_avbd import build_shelf_scene
from dcr.rigid.solver import _pick_friction_dirs


def run(iters, substeps, lo=30, hi=54):
    world, coupler, boxes, mesh, _ = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=1.0, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
    world._solver.substeps = int(substeps)
    eb = coupler.elastic_body_idx
    thr = coupler.impulse_threshold

    print(f"\n### iters={iters} substeps={substeps}  "
          f"(elastic_body_idx={eb}, impulse_threshold={thr:g})")
    print(f"{'step':>4} {'totElastic':>10} {'resting':>7} {'new':>4} "
          f"{'maxNewImpls':>12} {'>thr?':>6} {'alpha':>9} "
          f"{'E_max':>10} {'dEmodal':>10}")
    for k in range(hi):
        from dcr.modal.energy import modal_energy
        freqs = coupler.modal.frequencies
        em_pre = float(modal_energy(coupler._stepper.q,
                                    coupler._stepper.qdot, freqs))
        world.step()
        em_post = float(modal_energy(coupler._stepper.q,
                                     coupler._stepper.qdot, freqs))
        if k < lo:
            continue
        contacts = world.last_contacts
        lam = world.last_lam
        new_impulses = []
        n_tot = n_rest = 0
        for ci, c in enumerate(contacts):
            if c.body_a != eb and c.body_b != eb:
                continue
            n_tot += 1
            if not c.is_new:
                n_rest += 1
                continue
            if 3 * ci + 2 >= len(lam):
                continue
            lN, lT1, lT2 = lam[3 * ci], lam[3 * ci + 1], lam[3 * ci + 2]
            t1, t2 = _pick_friction_dirs(c.normal)
            j = c.normal * lN + t1 * lT1 + t2 * lT2
            new_impulses.append(float(np.linalg.norm(j)))
        n_new = len(new_impulses)
        mx = max(new_impulses) if new_impulses else 0.0
        n_pass = sum(1 for v in new_impulses if v >= thr)
        print(f"{k:>4} {n_tot:>10} {n_rest:>7} {n_new:>4} "
              f"{mx:>12.4e} {n_pass:>6} {coupler.last_alpha:>9.4f} "
              f"{world.last_E_max:>10.4e} {em_post-em_pre:>10.3e}")


def main():
    run(10, 4)
    run(4, 6)


if __name__ == "__main__":
    main()
