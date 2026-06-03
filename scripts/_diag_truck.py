#!/usr/bin/env python3
"""Truck scene: why does E_modal never decay / the slab vibrate forever?

Default params (matching the script's argparse defaults): eta=0.5,
beta=0.25, modal_decay_gamma=1.0, iters=10, sub=4. Logs per-window the
modal energy, the per-step injection vs decay, the new/total elastic
contact counts, and the peak surface displacement |Phi.q|."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import build_truck_scene
from dcr.modal.energy import modal_energy


def main(n_steps=720, gamma=1.0):
    world, coupler, boxes, mesh, _ = build_truck_scene(
        device="cpu", h=1.0 / 120.0, eta=0.5, beta=0.25,
        causal_gating=False, modal_decay_gamma=gamma)
    eb = coupler.elastic_body_idx
    freqs = coupler.modal.frequencies
    stp = coupler._stepper
    U = coupler.modal.U_surf                  # (3*n_surf_free, m)

    def surf_max_disp_mm():
        d = U @ stp.q                          # (3*n_surf_free,)
        return float(np.abs(d.reshape(-1, 3)).sum(axis=1).max()) * 1000.0

    print(f"modal_decay_gamma={gamma}  f=[{freqs.min()/(2*np.pi):.1f},"
          f"{freqs.max()/(2*np.pi):.1f}]Hz  alpha0(Rayleigh)=2.0")
    print(f"{'step':>4} {'t(s)':>6} {'E_modal':>10} {'Eloss/win':>10} "
          f"{'kick/win':>10} {'newC':>5} {'totC':>5} {'maxDisp_mm':>10}")
    win_loss = win_kick = 0.0
    cum_loss = cum_kick = 0.0
    for k in range(n_steps):
        world.step()
        e_post = float(modal_energy(stp.q, stp.qdot, freqs))
        # The genuine passive injection = post-kick minus pre-kick modal
        # energy reported by the coupler (bounded by E_max = eta*E_loss).
        kick = (coupler.last_E_modal_post_kick
                - coupler.last_E_modal_pre_kick)
        win_loss += world.last_E_loss
        win_kick += max(0.0, kick)
        cum_loss += world.last_E_loss
        cum_kick += max(0.0, kick)
        if k % 40 == 39:
            n_new = n_tot = 0
            for c in world.last_contacts:
                if c.body_a == eb or c.body_b == eb:
                    n_tot += 1
                    if c.is_new:
                        n_new += 1
            print(f"{k:>4} {world.time:>6.2f} {e_post:>10.3e} "
                  f"{win_loss:>10.3e} {win_kick:>10.3e} {n_new:>5} {n_tot:>5} "
                  f"{surf_max_disp_mm():>10.3f}")
            win_loss = win_kick = 0.0
    print(f"\ncumulative: kick_injected={cum_kick:.4e}  "
          f"eta*E_loss={0.5*cum_loss:.4e}  "
          f"bound holds (inj<=eta*loss)? {cum_kick <= 0.5*cum_loss + 1e-6}")


if __name__ == "__main__":
    import sys
    g = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    main(gamma=g)
