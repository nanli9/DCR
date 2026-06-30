"""Shared helpers for the material sweeps. ISOLATED benchmark code.

Self-contained run/record loop (imports scenes + rigid KE READ-ONLY, sets solver
config at RUNTIME — never modifies original code). Both solvers use the
**symplectic** modal step and modal relaxation **0.7** (the solver-source defaults
are BE and relax 0.1/0.25, which under-relax the modal block and suppress the
ring — set explicitly here per the project default).

Solver relaxation knobs:
  AVBD (Solver6DOF): sol._modal_relax
  XPBD (SolverXPBD): sol.modal_relax  (and sol._support_block_relax mirrors it)
"""
from __future__ import annotations

import numpy as np

from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_dinner_table import build_reduced_dinner_table
from dcr.rigid.energy import rigid_kinetic_energy

G = 9.81
RELAX = 0.7   # modal relaxation for BOTH solvers (NOT the 0.1/0.25 source default)

# Non-cargo scenes + their reduced-support plate geometry (length L, width W,
# thickness t) for the Euler-Bernoulli / full-FEM ground truth.
SCENES = {
    "shelf":  dict(build=build_reduced_shelf,         L=0.8, W=0.3, t=0.03),
    "ledge":  dict(build=build_reduced_ledge,         L=1.2, W=0.8, t=0.08),
    "dinner": dict(build=build_reduced_dinner_table,  L=1.2, W=1.0, t=0.03),
}

# Slab materials: (E [Pa], rho, nu). sqrt(E/rho) = bending sound speed (steel and
# aluminium are nearly equal -> near-equal bending frequency for fixed geometry).
SLAB_MATERIALS = {
    "steel":    dict(youngs=2.0e11, density=7850.0, poisson=0.30),
    "aluminum": dict(youngs=6.9e10, density=2700.0, poisson=0.33),
    "glass":    dict(youngs=7.0e10, density=2500.0, poisson=0.22),
    "oak":      dict(youngs=1.1e10, density=700.0,  poisson=0.35),
    "soft":     dict(youngs=5.0e8,  density=600.0,  poisson=0.30),
}


def eb_f1(youngs, density, poisson, L, t):
    """Fundamental simply-supported Euler-Bernoulli bending frequency [Hz] —
    exactly the synthetic basis's lowest oscillator for that scene's geometry."""
    D = youngs * t ** 3 / (12.0 * (1.0 - poisson ** 2))
    mu = density * t
    return (np.pi / L) ** 2 * np.sqrt(D / mu) / (2.0 * np.pi)


def _set_relax(sol, solver, relax):
    if solver == "avbd":
        sol._modal_relax = float(relax)
    else:
        sol.modal_relax = float(relax)
        sol._support_block_relax = float(relax)


def _build(build_fn, solver, build_kw, h, *, relax, freeze, symplectic=True,
           iters=16, substeps=4):
    """Build a scene and configure the solver at runtime. Returns (handle, sol)."""
    kw = dict(device="cpu", iterations=int(iters), avbd_substeps=int(substeps),
              solver=solver, h=h)
    if build_kw:
        kw.update(build_kw)
    H = build_fn(**kw)
    sol = H.world._solver
    # frozen control runs BE (q̇≡0 ⇒ symplectic and BE coincide; avoids the
    # symplectic-predict None-deref the committed probe also sidesteps).
    sol._modal_symplectic = bool(symplectic) and not bool(freeze)
    _set_relax(sol, solver, relax)
    fz = "_modal_freeze_qdot" if solver == "avbd" else "_freeze_qdot"
    if hasattr(sol, fz):
        setattr(sol, fz, bool(freeze))
    return H, sol


def _getq(sol, solver):
    return (np.asarray(sol._q_modal_host, dtype=np.float64) if solver == "avbd"
            else np.asarray(sol._q, dtype=np.float64))


# --------------------------------------------------------------------------- #
# Modal ring-frequency measurement (fine timestep, detrended)                 #
# --------------------------------------------------------------------------- #
def measure_ring_freq(build_fn, solver, *, L, t, build_kw=None, relax=RELAX,
                      f_hint=None, settle_s=0.30, window_s=0.6,
                      iters=16, substeps=4):
    """FFT the fundamental modal coordinate q0(t) over a post-impact window. The
    slow contact-settling envelope is removed by a moving-average high-pass
    (window ~1.5 ring periods) so the FFT resolves the RING, not the drift."""
    f1 = f_hint if f_hint else 50.0
    hz = max(600.0, 24.0 * f1)
    h = 1.0 / hz
    H, sol = _build(build_fn, solver, build_kw, h, relax=relax, freeze=False,
                    iters=iters, substeps=substeps)
    w = H.world
    for _ in range(int(settle_s * hz)):
        w.step()
    n = int(window_s * hz)
    q0 = np.empty(n)
    for i in range(n):
        w.step()
        q0[i] = _getq(sol, solver)[0]
    if not np.all(np.isfinite(q0)):
        return float("nan"), hz
    win = max(3, int(hz / max(f1, 1.0) * 1.5))
    if 2 * win < n:
        trend = np.convolve(q0, np.ones(win) / win, mode="same")
        qc = (q0 - trend)[win:-win]
    else:
        qc = q0 - q0.mean()
    if qc.size < 8:
        return float("nan"), hz
    spec = np.abs(np.fft.rfft(qc * np.hanning(qc.size)))
    freqs = np.fft.rfftfreq(qc.size, d=h)
    return float(freqs[1 + int(np.argmax(spec[1:]))]), hz


# --------------------------------------------------------------------------- #
# Two-way coupling + energy (own freeze control, relax-aware)                 #
# --------------------------------------------------------------------------- #
def _run_energy(build_fn, solver, *, build_kw, relax, freeze, n_frames, settle=8,
                iters=16, substeps=4):
    h = 1.0 / 120.0
    H, sol = _build(build_fn, solver, build_kw, h, relax=relax, freeze=freeze,
                    iters=iters, substeps=substeps)
    w = H.world
    imp = H.impactor_idx
    books = [i for i in H.probe_indices if i != imp]
    imp_body = w._descs[imp].dcr_body
    book_bodies = [w._descs[b].dcr_body for b in books]
    for _ in range(settle):
        w.step()
    Eimp_pk = 0.0
    Eslab_pk = 0.0
    obj_ke = np.zeros(len(books))
    for _ in range(n_frames):
        w.step()
        Eimp_pk = max(Eimp_pk, rigid_kinetic_energy([imp_body]))
        Eslab_pk = max(Eslab_pk, float(getattr(sol, "last_modal_KE", 0.0))
                       + float(getattr(sol, "last_modal_PE", 0.0)))
        for j, b in enumerate(book_bodies):
            obj_ke[j] = max(obj_ke[j], rigid_kinetic_energy([b]))
    finite = (np.isfinite(Eimp_pk) and np.isfinite(Eslab_pk)
              and np.all(np.isfinite(obj_ke)))
    return dict(Eimp=Eimp_pk, Eslab=Eslab_pk,
                objKE=float(obj_ke.max() if obj_ke.size else 0.0),
                finite=bool(finite))


def coupling_metrics(build_fn, solver, *, build_kw=None, relax=RELAX, n_frames=200,
                     iters=16, substeps=4):
    """Two-way ratio (object KE peak two-way / one-way) + slab ring + passivity,
    at symplectic + the given modal relaxation."""
    two = _run_energy(build_fn, solver, build_kw=build_kw, relax=relax,
                      freeze=False, n_frames=n_frames, iters=iters, substeps=substeps)
    one = _run_energy(build_fn, solver, build_kw=build_kw, relax=relax,
                      freeze=True, n_frames=n_frames, iters=iters, substeps=substeps)
    ratio = (two["objKE"] / one["objKE"] if one["objKE"] > 1e-12 else float("inf"))
    return dict(
        twoway_ratio=ratio,
        Eimp_peak=two["Eimp"], Eslab_peak=two["Eslab"], ErestKE_peak=two["objKE"],
        passivity=(two["Eslab"] / two["Eimp"] if two["Eimp"] > 1e-12 else 0.0),
        finite=two["finite"] and one["finite"],
    )
