#!/usr/bin/env python3
"""Stage E6 — Modal sound energy bound (log-only).

Runs the dinner scene with E6 dissipation logging, produces
the three-line cumulative energy plot.

Usage:
    uv run python scripts/run_stageE6.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.modal.energy import modal_energy
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.dcr import PassiveDCRCoupler, DCRWorld

OUT_DIR = Path("docs/stageE6")


def _fix_corners(mesh):
    v = mesh.vertices
    tol = 1e-8
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    mask = (((np.abs(v[:, 0] - xmin) < tol) | (np.abs(v[:, 0] - xmax) < tol)) &
            ((np.abs(v[:, 2] - zmin) < tol) | (np.abs(v[:, 2] - zmax) < tol)))
    return np.where(mask)[0].astype(np.int32)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    h = 1e-3

    world = DCRWorld(
        h=h, eta=1.0,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)
    table = make_static_plane(normal=(0, 1, 0), point=(0, 0.025, 0), friction=0.5)
    table_idx = world.add_body(table)

    fixed = _fix_corners(mesh)
    fem = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                   alpha0=2.0, alpha1=1e-5)
    modal = ModalAnalysis(fem=fem, num_modes=10)
    coupler = PassiveDCRCoupler(modal=modal, elastic_body_idx=table_idx)
    world.add_passive_coupler(coupler)

    for pos in [(-0.3, 0.046, 0.15), (0.3, 0.046, -0.1), (0.0, 0.046, -0.2)]:
        plate = make_dynamic_box(0.2, 0.06, 0.02, 0.06,
                                 position=pos, restitution=0.0, friction=0.5)
        world.add_body(plate)
    pot = make_dynamic_box(5.0, 0.08, 0.08, 0.08,
                           position=(0.0, 0.925, 0.0),
                           restitution=0.1, friction=0.5)
    pot_idx = world.add_body(pot)

    # Settle
    world.bodies[pot_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for b in world.bodies:
        if not b.is_static:
            b.velocity[:] = 0.0
    world.bodies[pot_idx].is_static = False
    world.dcr_enabled = True
    world.time = 0.0

    omega = coupler.modal.frequencies
    rho = np.full(modal.num_modes, 0.1)

    times = []
    cum_injected, cum_diss, cum_sound = [], [], []
    c_inj, c_diss, c_sound = 0.0, 0.0, 0.0

    print("Running dinner scene with E6 logging (η=1.0)...")
    for step_i in range(800):
        contacts = world.step()
        times.append(world.time)

        coupler_active = len(contacts) > 0 and world.dcr_enabled
        if coupler_active:
            dE = coupler.last_E_modal_post_kick - coupler.last_E_modal_pre_kick
            c_diss += coupler.last_E_diss_robust
            E_diss_modes = coupler.last_E_diss_per_mode
            if len(E_diss_modes) > 0:
                c_sound += float(np.sum(rho * E_diss_modes))
        else:
            dE = 0.0
        c_inj += dE

        cum_injected.append(c_inj)
        cum_diss.append(c_diss)
        cum_sound.append(c_sound)

    print(f"  cum E_injected = {c_inj:.4f} J")
    print(f"  cum E_diss = {c_diss:.4f} J")
    print(f"  cum E_sound = {c_sound:.4f} J")

    # Plot
    t_ms = np.array(times) * 1000
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(t_ms, cum_injected, "b-", lw=2, label="Σ ΔE_modal (injected)")
    ax.plot(t_ms, cum_diss, "r-", lw=2, label="Σ E_diss (damping)")
    ax.plot(t_ms, cum_sound, "g-", lw=2, label="Σ E_sound (ρ=0.1)")

    ax.fill_between(t_ms, cum_sound, cum_diss, alpha=0.1, color="orange",
                    label="E_diss − E_sound")
    ax.fill_between(t_ms, cum_diss, cum_injected, alpha=0.1, color="blue",
                    label="E_injected − E_diss")

    ax.set_xlabel("Time (ms)", fontsize=12)
    ax.set_ylabel("Cumulative energy (J)", fontsize=12)
    ax.set_title("E6: Sound Energy Bound — E_sound ≤ E_diss ≤ E_modal_injected",
                 fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # Verify ordering
    inj = np.array(cum_injected)
    diss = np.array(cum_diss)
    sound = np.array(cum_sound)
    v1 = np.sum(sound > diss + 1e-12)
    v2 = np.sum(diss > inj + 1e-6)
    ax.text(0.02, 0.95, f"E_sound ≤ E_diss: {'PASS' if v1 == 0 else f'FAIL ({v1})'}",
            transform=ax.transAxes, fontsize=10, verticalalignment="top",
            color="green" if v1 == 0 else "red")
    ax.text(0.02, 0.89, f"E_diss ≤ E_injected: {'PASS' if v2 == 0 else f'FAIL ({v2})'}",
            transform=ax.transAxes, fontsize=10, verticalalignment="top",
            color="green" if v2 == 0 else "red")

    fig.tight_layout()
    fig.savefig(OUT_DIR / "sound_energy_bound.png", dpi=150)
    plt.close(fig)
    print(f"  Saved {OUT_DIR / 'sound_energy_bound.png'}")


if __name__ == "__main__":
    main()
