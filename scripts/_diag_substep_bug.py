#!/usr/bin/env python3
"""Headless diagnostic for the 'high substeps starves DCR' report.

Builds the shelf scene (heavy box drops on a soft cantilever; 5 books on
the shelf), sweeps (avbd_iterations, avbd_substeps) with eta=1.0, and
measures the energy path that funds modal injection:

    E_loss  = rigid KE dissipated by the AVBD solve per rigid step
    E_max   = eta * E_loss              (injection budget, world.py:441)
    E_modal = modal energy after the coupler kick

plus the observable the user cares about: how far the books actually move.
"""
from __future__ import annotations
import sys
import numpy as np

# Reuse the exact scene builder the viewer uses.
from scripts.run_scenes_avbd import build_shelf_scene
from dcr.modal.energy import modal_energy


def run_config(iters: int, substeps: int, n_steps: int, eta: float = 1.0):
    world, coupler, boxes, mesh, _title = build_shelf_scene(
        device="cpu", h=1.0 / 120.0, eta=eta, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0,
    )
    # Override solver knobs exactly as the GUI sliders do.
    world._solver.iterations = int(iters)
    world._solver.substeps = int(substeps)

    freqs = coupler.modal.frequencies
    stp = coupler._stepper

    # Books are scene_boxes[0..4]; the heavy faller is the last ("drop").
    book_idxs = [b.body_idx for b in boxes if b.name.startswith("book_")]
    drop_idx = [b.body_idx for b in boxes if b.name == "drop"][0]

    def pos(i):
        return np.array(world._descs[i].dcr_body.position, dtype=float)

    book_p0 = {i: pos(i).copy() for i in book_idxs}

    cum_E_loss = 0.0
    cum_E_max = 0.0
    cum_inject = 0.0
    peak_E_modal = 0.0
    impact_step = None
    impact_E_loss = 0.0
    max_book_disp = 0.0

    for k in range(n_steps):
        E_modal_pre = float(modal_energy(stp.q, stp.qdot, freqs))
        world.step()
        E_modal_post = float(modal_energy(stp.q, stp.qdot, freqs))

        cum_E_loss += world.last_E_loss
        cum_E_max += world.last_E_max
        # Per-step injection = positive jump in modal energy across the step.
        inj = max(0.0, E_modal_post - E_modal_pre)
        cum_inject += inj
        peak_E_modal = max(peak_E_modal, E_modal_post)

        if world.last_E_loss > impact_E_loss:
            impact_E_loss = world.last_E_loss
            impact_step = k

        disp = max(float(np.linalg.norm(pos(i) - book_p0[i])) for i in book_idxs)
        max_book_disp = max(max_book_disp, disp)

    book_disp_final = max(
        float(np.linalg.norm(pos(i) - book_p0[i])) for i in book_idxs)
    drop_y = float(pos(drop_idx)[1])

    return dict(
        iters=iters, substeps=substeps,
        cum_E_loss=cum_E_loss, cum_E_max=cum_E_max, cum_inject=cum_inject,
        peak_E_modal=peak_E_modal,
        impact_step=impact_step, impact_E_loss=impact_E_loss,
        max_book_disp=max_book_disp, book_disp_final=book_disp_final,
        drop_y=drop_y,
    )


def main():
    n_steps = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    configs = [
        (10, 4),   # scene default / baseline
        (4, 4),    # low iters only
        (10, 6),   # high substeps only
        (4, 5),    # user report
        (4, 6),    # user report
    ]
    rows = []
    for iters, sub in configs:
        r = run_config(iters, sub, n_steps)
        rows.append(r)
        print(f"[done] iters={iters} sub={sub}", flush=True)

    print("\n" + "=" * 104)
    print(f"shelf scene, eta=1.0, h=1/120, {n_steps} steps "
          f"(~{n_steps/120:.2f}s sim)")
    print("=" * 104)
    hdr = (f"{'iters':>5} {'sub':>4} | {'cumE_loss':>11} {'cumE_max':>11} "
           f"{'cum_inject':>11} {'peakEmodal':>11} | {'impact@':>7} "
           f"{'E_loss@imp':>11} | {'maxBookDisp':>11} {'finalDisp':>10} "
           f"{'dropY':>8}")
    print(hdr)
    print("-" * 104)
    for r in rows:
        print(f"{r['iters']:>5} {r['substeps']:>4} | "
              f"{r['cum_E_loss']:>11.4e} {r['cum_E_max']:>11.4e} "
              f"{r['cum_inject']:>11.4e} {r['peak_E_modal']:>11.4e} | "
              f"{str(r['impact_step']):>7} {r['impact_E_loss']:>11.4e} | "
              f"{r['max_book_disp']:>11.4e} {r['book_disp_final']:>10.4e} "
              f"{r['drop_y']:>8.4f}")


if __name__ == "__main__":
    main()
