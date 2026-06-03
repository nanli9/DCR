#!/usr/bin/env python3
"""Decisive test: is the modal back-reaction (passive_dcr.py:1006,
qdot -= Phi^T lam) the source of the runaway E_modal?

Runs the truck scene twice — once stock, once with the back-reaction
neutralized (snapshot qdot before _compute_distant_response_patch and
restore it after, which disables ONLY line 1006's write) — and compares
peak / final E_modal."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import build_truck_scene
from dcr.modal.energy import modal_energy


def run(disable_backreaction: bool, n_steps=480):
    world, coupler, boxes, mesh, _ = build_truck_scene(
        device="cpu", h=1.0 / 120.0, eta=0.5, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    freqs = coupler.modal.frequencies
    stp = coupler._stepper

    if disable_backreaction:
        orig = coupler._compute_distant_response_patch

        def wrapped(*a, **kw):
            qsnap = stp.qdot.copy()
            out = orig(*a, **kw)
            stp.qdot[:] = qsnap          # undo the back-reaction write
            return out
        coupler._compute_distant_response_patch = wrapped

    U = coupler.modal.U_surf

    def disp_mm():
        d = (U @ stp.q).reshape(-1, 3)
        return float(np.linalg.norm(d, axis=1).max()) * 1000.0

    peak = peak_d = 0.0
    for _ in range(n_steps):
        world.step()
        peak = max(peak, float(modal_energy(stp.q, stp.qdot, freqs)))
        peak_d = max(peak_d, disp_mm())
    final = float(modal_energy(stp.q, stp.qdot, freqs))
    return peak, final, peak_d, disp_mm()


def main():
    p0, f0, pd0, fd0 = run(disable_backreaction=False)
    p1, f1, pd1, fd1 = run(disable_backreaction=True)
    print(f"{'config':<28} {'peak E_modal':>13} {'final E_modal':>13} "
          f"{'peakDisp_mm':>12} {'finalDisp_mm':>13}")
    print(f"{'stock (back-reaction on)':<28} {p0:>13.3e} {f0:>13.3e} "
          f"{pd0:>12.3f} {fd0:>13.4f}")
    print(f"{'back-reaction DISABLED':<28} {p1:>13.3e} {f1:>13.3e} "
          f"{pd1:>12.3f} {fd1:>13.4f}")


if __name__ == "__main__":
    main()
