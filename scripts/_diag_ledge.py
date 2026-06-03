#!/usr/bin/env python3
"""Why does the ledge scene barely respond regardless of iters/substeps?

Measures, per config: cumulative modal injection, peak modal energy, the
modal frequency band (vs the h=1/120 sampling rate), and displacement
broken out by body group (boulder / pedestal / pillars)."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import build_ledge_scene, build_shelf_scene
from dcr.modal.energy import modal_energy


def run(builder, name, iters, substeps, n_steps=300, eta=1.0):
    world, coupler, boxes, mesh, _ = builder(
        device="cpu", h=1.0 / 120.0, eta=eta, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    world._solver.iterations = int(iters)
    world._solver.substeps = int(substeps)
    freqs = coupler.modal.frequencies          # rad/s (omega)
    stp = coupler._stepper

    def pos(i):
        return np.array(world._descs[i].dcr_body.position, dtype=float)

    groups: dict[str, list[int]] = {}
    for b in boxes:
        key = ("boulder" if b.name == "boulder"
               else "pedestal" if b.name == "pedestal"
               else "pillars" if b.name.startswith("box_")
               else "books" if b.name.startswith("book_")
               else "drop" if b.name == "drop" else "other")
        groups.setdefault(key, []).append(b.body_idx)
    p0 = {b.body_idx: pos(b.body_idx).copy() for b in boxes}

    cum_inject = 0.0
    peak_E_modal = 0.0
    cum_E_loss = 0.0
    for _ in range(n_steps):
        e_pre = float(modal_energy(stp.q, stp.qdot, freqs))
        world.step()
        e_post = float(modal_energy(stp.q, stp.qdot, freqs))
        cum_inject += max(0.0, e_post - e_pre)
        peak_E_modal = max(peak_E_modal, e_post)
        cum_E_loss += world.last_E_loss

    disp = {g: max(float(np.linalg.norm(pos(i) - p0[i])) for i in idxs)
            for g, idxs in groups.items()}
    f_hz = freqs / (2 * np.pi)
    # n_substeps the modal stepper uses = ceil(h / T_fastest)
    n_sub_modal = int(np.ceil((1.0 / 120.0) / stp.T))
    print(f"{name:6} iter={iters:>2} sub={substeps} | "
          f"f=[{f_hz.min():7.1f},{f_hz.max():8.1f}]Hz "
          f"modalSub={n_sub_modal:>4} | "
          f"E_loss={cum_E_loss:7.2f} inject={cum_inject:9.3e} "
          f"peakEm={peak_E_modal:9.3e} | "
          + " ".join(f"{g}={disp[g]*1000:6.2f}mm" for g in sorted(disp)))


def main():
    print("Nyquist for h=1/120: modes above ~60 Hz are under-sampled\n")
    for it, sub in [(10, 4), (20, 4), (10, 8), (4, 6)]:
        run(build_ledge_scene, "ledge", it, sub)
    print()
    for it, sub in [(10, 4)]:
        run(build_shelf_scene, "shelf", it, sub)


if __name__ == "__main__":
    main()
