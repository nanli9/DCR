#!/usr/bin/env python3
"""Verify TWO-WAY coupling + the slab⇄object energy loop for the NATIVE solvers.

Port of the twobody `scripts/_probe_energy_loop.py` to the current native AVBD
(`Solver6DOF`) / XPBD (`SolverXPBD`) reduced-modal-support scenes (NON-cargo).
The "slab" is the reduced-modal support surface (shelf / ledge / table); an
impactor drops onto it and a resting object sits on it. We log, per step:

  - Eimp     : impactor rigid KE                          [J]
  - Eslab    : slab modal ring energy = last_modal_KE+PE  [J]
  - Erest    : resting object TOTAL mech energy KE+gravPE [J] (launch visible airborne)
  - ErestKE  : resting object KE only                     [J]
  - y_rest   : resting object lift above its settled rest [m]
  - gap      : min resting-object support-corner gap      [m] (>0 ⇒ airborne)
  - Fimp[4]  : impactor's 4 active support-corner forces  [N]
  - Frest[4] : resting object's 4 active corner forces    [N]

Per-corner force (validated against supported weight in /tmp/calib_probe.py):
  XPBD : F_c = sc.lam / h_sub²              (compliant multiplier, Macklin)
  AVBD : F_c = max(0, -(λ_c + ρ_c·gap_c))   (augmented-Lagrangian normal force)
Both apply the SAME multiplier to the rigid body and the modal q (∂C/∂q = -U_y),
so the loop's two directions are carried by one shared contact constraint.

One-way control: `_freeze_qdot=True` deletes the modal inertia (q̇≡0) so the slab
becomes a quasi-static spring that deflects but cannot RING or feed energy back —
the discriminating probe for "is the object launch slab-ring-driven (two-way)?".

See: docs/twobody/contact_force_sweep/README.md (the reference verification).
"""
from __future__ import annotations

import numpy as np

from dcr.rigid.energy import rigid_kinetic_energy
from dcr.avbd.modal_qblock import _quat_to_R as _qR

G = 9.81


# --------------------------------------------------------------------------- #
# Per-corner contact-force extraction (per solver)                            #
# --------------------------------------------------------------------------- #
def _xpbd_corner_forces(sol, body_idx):
    """XPBD support-corner normal forces [N] for one body: F = λ/h_sub²."""
    h = sol.dt / sol.substeps
    inv_h2 = 1.0 / (h * h)
    return np.array([sc.lam * inv_h2 for sc in sol._support if sc.bi == body_idx])


def _xpbd_corner_gaps(sol, body_idx):
    """XPBD support-corner gap C = corner_y - (y_rest + U_y·q); >0 ⇒ separated."""
    q = sol._q
    X, Q = sol._X, sol._Q
    out = []
    for sc in sol._support:
        if sc.bi != body_idx:
            continue
        R = _qR(np.asarray(Q[sc.bi], dtype=np.float64))
        corner_y = float(X[sc.bi][1]) + float((R @ sc.off)[1])
        out.append(corner_y - (sc.y_rest + float(sc.U_y @ q)))
    return np.array(out)


def _avbd_corner_forces_and_gaps(sol, body_idx):
    """AVBD support-corner (force [N], gap [m]) for one body.
    F = max(0,-(ρ·C + λ_eff)); soft rows ⇒ λ_eff=0 (matches the q-block & primal)."""
    r = sol._n_modes
    q = np.asarray(sol._q_modal_host, dtype=np.float64)
    x = sol.x.numpy(); quat = sol.q.numpy()
    pen = sol.c_penalty.numpy(); lam = sol.c_lambda.numpy()
    stiff = sol.c_stiffness.numpy(); act = sol.c_active.numpy()
    forces, gaps = [], []
    for s, cidx in enumerate(sol._support_row_cidx):
        row = sol._rows[cidx]
        if row.body_a != body_idx:
            continue
        if act[cidx] == 0:
            forces.append(0.0); gaps.append(np.nan); continue
        R = _qR(np.asarray(quat[row.body_a], dtype=np.float64))
        corner_y = float(x[row.body_a][1]) + float((R @ np.asarray(row.off_a))[1])
        U = sol._support_U_y_rows[s][:r]
        C = corner_y - (float(row.world_anchor[1]) + float(U @ q))
        lam_eff = float(lam[cidx]) if np.isinf(stiff[cidx]) else 0.0
        forces.append(max(0.0, -(float(pen[cidx]) * C + lam_eff)))
        gaps.append(C)
    return np.array(forces), np.array(gaps)


def _corner_forces_gaps(sol, solver, body_idx):
    if solver == "xpbd":
        return _xpbd_corner_forces(sol, body_idx), _xpbd_corner_gaps(sol, body_idx)
    return _avbd_corner_forces_and_gaps(sol, body_idx)


def _active4(arr):
    """The 4 load-bearing (bottom) corners: largest by |force|. Pads to 4."""
    a = np.asarray(arr, dtype=np.float64)
    if a.size <= 4:
        return np.pad(a, (0, 4 - a.size))
    idx = np.argsort(-np.abs(a))[:4]
    return a[np.sort(idx)]


# --------------------------------------------------------------------------- #
# One run                                                                     #
# --------------------------------------------------------------------------- #
def run(build_fn, solver, *, iterations, substeps, n_frames=220,
        freeze_qdot=False, symplectic=True, settle=8, build_kw=None):
    """Drive one scene and return the per-step record dict."""
    kw = dict(device="cpu", iterations=int(iterations),
              avbd_substeps=int(substeps), solver=solver)
    if build_kw:
        kw.update(build_kw)
    handle = build_fn(**kw)
    world = handle.world
    sol = world._solver
    # One-way control freezes q̇ (no modal inertia ⇒ no ring ⇒ no feedback). With
    # q̇≡0 there is no modal velocity to integrate, so symplectic and BE coincide;
    # we use BE under freeze (XPBD's symplectic predict only sets _alpha_e when not
    # frozen, so symplectic+freeze would dereference a None — a pre-existing
    # incompatibility, sidestepped here without touching the solver).
    sol._modal_symplectic = bool(symplectic) and not bool(freeze_qdot)
    fz = "_modal_freeze_qdot" if solver == "avbd" else "_freeze_qdot"
    if hasattr(sol, fz):
        setattr(sol, fz, bool(freeze_qdot))

    imp = handle.impactor_idx
    books = [i for i in handle.probe_indices if i != imp]
    imp_body = world._descs[imp].dcr_body
    book_bodies = [world._descs[b].dcr_body for b in books]
    m_books = [b.mass for b in book_bodies]
    h = 1.0 / 120.0

    # settle a few frames, then snapshot each book's rest height for grav PE.
    for _ in range(settle):
        world.step()
    y0 = [float(b.position[1]) for b in book_bodies]

    rec = {k: [] for k in ("t", "Eimp", "Eslab", "Erest", "ErestKE",
                           "ylift", "gap", "Fimp", "Frest")}
    # pick the resting object that ends up most disturbed (max KE over the run).
    ke_track = np.zeros(len(books))
    series_per_book = []  # (Erest, ErestKE, ylift, gap, Frest) per book per frame

    for f in range(n_frames):
        world.step()
        frame = []
        for bi_local, (b, m, yb) in enumerate(zip(book_bodies, m_books, y0)):
            ke = rigid_kinetic_energy([b])
            ke_track[bi_local] = max(ke_track[bi_local], ke)
            lift = float(b.position[1]) - yb
            ff, gg = _corner_forces_gaps(sol, solver, books[bi_local])
            f4 = _active4(ff)
            gmin = np.nanmin(gg) if np.any(np.isfinite(gg)) else 0.0
            frame.append((ke + m * G * lift, ke, lift, gmin, f4))
        series_per_book.append(frame)

        fi, _gi = _corner_forces_gaps(sol, solver, imp)
        rec["t"].append(f * h)
        rec["Eimp"].append(rigid_kinetic_energy([imp_body]))
        rec["Eslab"].append(float(getattr(sol, "last_modal_KE", 0.0))
                            + float(getattr(sol, "last_modal_PE", 0.0)))
        rec["Fimp"].append(_active4(fi))

    track = int(np.argmax(ke_track))           # the launched resting object
    for f in range(n_frames):
        Erest, ErestKE, ylift, gap, Frest = series_per_book[f][track]
        rec["Erest"].append(Erest); rec["ErestKE"].append(ErestKE)
        rec["ylift"].append(ylift); rec["gap"].append(gap)
        rec["Frest"].append(Frest)

    for k in rec:
        rec[k] = np.array(rec[k])
    rec["tracked_book"] = books[track]
    rec["impactor"] = imp
    rec["finite"] = bool(np.all(np.isfinite(rec["Eslab"]))
                        and np.all(np.isfinite(rec["Erest"])))
    return rec


def loop_metrics(rec):
    """Quantify the energy loop from a run record."""
    t = rec["t"]
    Eimp, Eslab, Erest = rec["Eimp"], rec["Eslab"], rec["Erest"]
    # impact frame: impactor KE peak (just before it dumps into the slab).
    impact_f = int(np.argmax(Eimp))
    post = slice(impact_f, None)
    # slab ring count (local maxima of slab energy after impact, > 2% of peak).
    s = Eslab[post]
    rings = _count_peaks(s)
    # resting object launch: peak mech energy above its post-impact baseline.
    base = np.median(Erest[post][:5]) if Erest[post].size >= 5 else 0.0
    launch = float(Erest[post].max() - base)
    # bounces: airborne (gap>1e-4) → landing transitions.
    gap = rec["gap"]
    airborne = gap > 1e-4
    landings = int(np.sum(airborne[:-1] & ~airborne[1:]))
    return dict(
        impact_f=impact_f,
        Eimp_peak=float(Eimp.max()),
        Eslab_peak=float(Eslab.max()),
        Erest_launch=launch,
        ErestKE_peak=float(rec["ErestKE"][post].max()),
        slab_rings=rings,
        bounces=landings,
        max_lift_mm=float(rec["ylift"][post].max() * 1e3),
        Frest_peak=float(rec["Frest"][post].max()) if rec["Frest"].size else 0.0,
        Fimp_peak=float(rec["Fimp"][post].max()) if rec["Fimp"].size else 0.0,
        finite=rec["finite"],
    )


def _count_peaks(sig, rel=0.02):
    sig = np.asarray(sig, dtype=np.float64)
    if sig.size < 3 or sig.max() <= 0:
        return 0
    thr = rel * sig.max()
    pk = (sig[1:-1] > sig[:-2]) & (sig[1:-1] >= sig[2:]) & (sig[1:-1] > thr)
    return int(np.count_nonzero(pk))
