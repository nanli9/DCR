#!/usr/bin/env python3
"""Why does enabling Phase B (moving-support pass) tame the runaway E_modal?

Hypothesis: Phase B is a *drain* on the modal reservoir (it spends up to
beta*E_modal/step as work on the resting bodies, world.py:699). That drain
is proportional to E_modal, so it counteracts the back-reaction leak —
but the leaked (non-physical) energy is dumped into the rigid bodies
instead of vanishing. This measures both sides of that."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import build_truck_scene
from dcr.modal.energy import modal_energy


def run(phase_b: bool, n_steps=480, ms_beta=0.1):
    world, coupler, boxes, mesh, _ = build_truck_scene(
        device="cpu", h=1.0 / 120.0, eta=0.5, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0,
        enable_phase_b=phase_b, ms_beta=ms_beta)
    freqs = coupler.modal.frequencies
    stp = coupler._stepper
    U = coupler.modal.U_surf

    def disp_mm():
        d = (U @ stp.q).reshape(-1, 3)
        return float(np.linalg.norm(d, axis=1).max()) * 1000.0

    def bpos(i):
        return np.array(world._descs[i].dcr_body.position, dtype=float)
    p0 = {b.body_idx: bpos(b.body_idx).copy() for b in boxes}

    peakE = peakD = 0.0
    cum_W_support = 0.0
    for _ in range(n_steps):
        world.step()
        peakE = max(peakE, float(modal_energy(stp.q, stp.qdot, freqs)))
        peakD = max(peakD, disp_mm())
        cum_W_support += float(getattr(world, "last_W_support", 0.0))
    finalE = float(modal_energy(stp.q, stp.qdot, freqs))
    # Total rigid-body travel (proxy for "how much did bodies move").
    body_travel = sum(float(np.linalg.norm(bpos(b.body_idx) - p0[b.body_idx]))
                      for b in boxes)
    return dict(peakE=peakE, finalE=finalE, peakD=peakD, finalD=disp_mm(),
                cum_W=cum_W_support, travel=body_travel)


def main():
    off = run(phase_b=False)
    on = run(phase_b=True)
    print(f"{'config':<16} {'peakE_modal':>12} {'finalE_modal':>12} "
          f"{'peakDisp_mm':>11} {'finalDisp_mm':>12} {'cumW_support':>12} "
          f"{'bodyTravel_m':>12}")
    for name, r in (("Phase B OFF", off), ("Phase B ON", on)):
        print(f"{name:<16} {r['peakE']:>12.3e} {r['finalE']:>12.3e} "
              f"{r['peakD']:>11.2f} {r['finalD']:>12.4f} {r['cum_W']:>12.3e} "
              f"{r['travel']:>12.4f}")


if __name__ == "__main__":
    main()
