"""Shared helpers for the material sweeps. ISOLATED benchmark code.

Imports the scene builders and the committed energy-loop probe READ-ONLY (it
reuses `scripts.probe_native_energy_loop.run`/`loop_metrics` for the two-way /
energy metrics, and adds its own fine-timestep modal ring-frequency measurement).
Nothing in the original tree is modified.
"""
from __future__ import annotations

import numpy as np

from scenes.reduced_shelf import build_reduced_shelf

# Read-only reuse of the committed probe (two-way ratio + energy bookkeeping).
from scripts.probe_native_energy_loop import run as probe_run, loop_metrics


# --------------------------------------------------------------------------- #
# Material tables                                                             #
# --------------------------------------------------------------------------- #
# Slab materials: (E [Pa], rho [kg/m^3], nu).  sqrt(E/rho) = bending sound speed;
# note steel and aluminium have nearly equal sqrt(E/rho) -> near-equal bending
# frequency for the same geometry despite very different stiffness.
SLAB_MATERIALS = {
    "steel":    dict(youngs=2.0e11, density=7850.0, poisson=0.30),
    "aluminum": dict(youngs=6.9e10, density=2700.0, poisson=0.33),
    "glass":    dict(youngs=7.0e10, density=2500.0, poisson=0.22),
    "oak":      dict(youngs=1.1e10, density=700.0,  poisson=0.35),
    "soft":     dict(youngs=5.0e8,  density=600.0,  poisson=0.30),  # scene default
}

CARGO_MATERIALS = ["rigid", "fem_rigid", "fem", "abd"]

# Shelf slab geometry (matches scenes/reduced_shelf.py defaults).
SHELF_L, SHELF_W, SHELF_T = 0.8, 0.3, 0.03


def eb_f1(youngs, density, poisson, L=SHELF_L, t=SHELF_T):
    """Fundamental simply-supported Euler-Bernoulli bending frequency [Hz] —
    exactly the synthetic shelf basis's lowest oscillator."""
    D = youngs * t ** 3 / (12.0 * (1.0 - poisson ** 2))
    mu = density * t
    return (np.pi / L) ** 2 * np.sqrt(D / mu) / (2.0 * np.pi)


# --------------------------------------------------------------------------- #
# Fine-timestep modal ring-frequency measurement                              #
# --------------------------------------------------------------------------- #
def measure_ring_freq(mat, solver, *, iterations=16, substeps=4, hz=None,
                      settle_s=0.30, window_s=0.5):
    """Drop the impactor and FFT the fundamental modal coordinate q0(t) over a
    post-impact window, sampled at `hz` (must beat 2*f to avoid aliasing).
    Returns (measured_f1_Hz, hz_used)."""
    f1 = eb_f1(**mat)
    if hz is None:
        hz = max(600.0, 24.0 * f1)         # >= ~12 samples per period
    h = 1.0 / hz
    H = build_reduced_shelf(device="cpu", iterations=int(iterations),
                            avbd_substeps=int(substeps), solver=solver,
                            h=h, **mat)
    w = H.world
    sol = w._solver
    sol._modal_symplectic = True   # user default: symplectic modal step (NOT BE)
    if solver == "avbd":
        getq = lambda: np.asarray(sol._q_modal_host, dtype=np.float64)
    else:
        getq = lambda: np.asarray(sol._q, dtype=np.float64)
    for _ in range(int(settle_s * hz)):
        w.step()
    n = int(window_s * hz)
    q0 = np.empty(n)
    for i in range(n):
        w.step()
        q0[i] = getq()[0]
    q0 = q0 - q0.mean()
    spec = np.abs(np.fft.rfft(q0 * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, d=h)
    f_meas = float(freqs[1 + int(np.argmax(spec[1:]))]) if n > 4 else 0.0
    return f_meas, hz


# --------------------------------------------------------------------------- #
# Two-way ratio + energy metrics (reuses the committed probe, read-only)      #
# --------------------------------------------------------------------------- #
def coupling_metrics(build_fn, solver, *, build_kw, iterations=16, substeps=4,
                     n_frames=200):
    """Two-way ratio (object KE peak two-way / one-way) + slab ring + impactor
    KE + passivity, via the committed energy-loop probe (read-only)."""
    rec2 = probe_run(build_fn, solver, iterations=iterations, substeps=substeps,
                     n_frames=n_frames, freeze_qdot=False, build_kw=build_kw)
    rec1 = probe_run(build_fn, solver, iterations=iterations, substeps=substeps,
                     n_frames=n_frames, freeze_qdot=True, build_kw=build_kw)
    m2, m1 = loop_metrics(rec2), loop_metrics(rec1)
    ratio = (m2["ErestKE_peak"] / m1["ErestKE_peak"]
             if m1["ErestKE_peak"] > 1e-12 else float("inf"))
    return dict(
        twoway_ratio=ratio,
        Eimp_peak=m2["Eimp_peak"],
        Eslab_peak=m2["Eslab_peak"],
        ErestKE_peak=m2["ErestKE_peak"],
        slab_rings=m2["slab_rings"],
        bounces=m2["bounces"],
        # passivity: modal ring energy injected vs impactor KE available.
        passivity=(m2["Eslab_peak"] / m2["Eimp_peak"]
                   if m2["Eimp_peak"] > 1e-12 else 0.0),
        finite=m2["finite"],
    )
