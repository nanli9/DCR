"""Diagnostic probe: is `world.eta` actually wired into the COUPLED path?

Background
----------
The brief `docs/proposal_modal_response_as_constraint.md` §3 claimed the coupled
mode (`--mode coupled_iir_modal`, ReducedCoupledAVBDCoupler) is governed by the
foundation §15 budget  ΔE_modal ≤ η · ΔE_rigid_loss.

This probe tests that claim the only honest way: run the SAME coupled scene at
two different η and see whether the modal response changes at all.

Result (2026-06-08): the response is BIT-IDENTICAL across η=0.0 and η=1.0, while
`world.last_E_max = η·E_loss` correctly varies — proving the world computes the
budget but the coupled coupler never reads it. η is INERT in the coupled path.
(`_solve_passive_alpha` in reduced_coupled_avbd.py has zero call sites; the
coupled coupler has no `eta` field.) η governs only the velocity-kick injection
path (PassiveDCRCoupler.energy_prescribed_patch), which coupled mode doesn't attach.

This is a read-only diagnostic — it does not modify any library code.

Usage:
    uv run python scripts/_diag_eta_coupled_inert.py
"""
from __future__ import annotations

import numpy as np

from scenes.reduced_coupled_toy_minimum import build_toy_scene_1


def run(eta: float, frames: int = 60) -> dict:
    h = build_toy_scene_1(
        h=1 / 120, device="cpu", iterations=8, avbd_substeps=8, mass=0.05
    )
    h.world.eta = float(eta)  # the knob the brief credited
    peak_q = 0.0
    peak_defl = 0.0
    E_max_seen = []
    for _ in range(frames):
        h.world.step()
        peak_q = max(peak_q, h.coupler.last_q_norm)
        peak_defl = max(peak_defl, h.coupler.last_max_support_deflection)
        E_max_seen.append(getattr(h.world, "last_E_max", float("nan")))
    return dict(
        eta=eta,
        final_q=h.coupler.last_q_norm,
        peak_q=peak_q,
        peak_defl=peak_defl,
        passivity_viol=h.coupler.last_passivity_violations,
        world_E_max_last=E_max_seen[-1],
        world_E_max_max=float(np.nanmax(E_max_seen)),
    )


def main() -> None:
    a = run(0.0)
    b = run(1.0)

    print(f"{'metric':22s} {'eta=0.0':>16s} {'eta=1.0':>16s}  identical?")
    for k in ("final_q", "peak_q", "peak_defl", "passivity_viol"):
        print(f"{k:22s} {a[k]:>16.9e} {b[k]:>16.9e}  {a[k] == b[k]}")

    print()
    print("world.last_E_max (= eta*E_loss) varies with eta, proving E_loss>0:")
    print(f"  eta=0.0 -> last={a['world_E_max_last']:.3e}  max={a['world_E_max_max']:.3e}")
    print(f"  eta=1.0 -> last={b['world_E_max_last']:.3e}  max={b['world_E_max_max']:.3e}")

    inert = a["peak_q"] == b["peak_q"] and a["final_q"] == b["final_q"]
    print()
    print(
        "VERDICT:",
        "INERT — eta does NOT govern the coupled modal path"
        if inert
        else "ACTIVE — eta changes the coupled response",
    )


if __name__ == "__main__":
    main()
