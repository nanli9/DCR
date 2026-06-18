"""Stage 7 fusion — the four production scenes × solver × deformable material.

The reduced-modal production scenes (truck / ledge / shelf / dinner) carry a
deformable impactor (fem_rigid / abd / fem) coupled at its contact corners
through the dynamic two-way modal constraint, on either the AVBD (Schur–Newton)
or XPBD (compliant Gauss–Seidel, Stage 6) primal, while the bystanders rest on
the same reduced-modal support. This exercises the full
scene × solver × material matrix on the real scenes (not just the single-cube
cargo scene).

XPBD needs a higher iteration budget than AVBD on the many-body scenes (its
Gauss–Seidel has no ρ-escalation; the `XPBDDynamicSystem` oracle uses ~20 iters
vs AVBD's 6–10) — `_iters_for` bumps it, matching how the unified viser drives
the scenes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table

BUILD = {"truck": build_reduced_truck, "ledge": build_reduced_ledge,
         "shelf": build_reduced_shelf, "dinner": build_reduced_dinner_table}
SCENES = ["truck", "ledge", "shelf", "dinner"]


def _iters_for(solver: str) -> dict:
    # XPBD GS needs more sweeps than AVBD AL for the many-body scenes.
    return {"iterations": 16, "avbd_substeps": 4} if solver == "xpbd" else {}


def _avbd_idx(world, dcr):
    return int(world._descs[dcr].avbd_body.index)


@pytest.mark.parametrize("scene", SCENES)
def test_xpbd_resting_bystanders_stay_at_rest(scene):
    """Pre-impact, the bystanders rest quasi-statically under XPBD — they must
    NOT fly off before the impactor lands.

    Regression for the resting-contact blow-up: the XPBD coupler (a) froze the
    contact corner geometry r_self_w/j_ang at substep-begin, so the rotational
    correction never fed back into the gap and serial Gauss–Seidel pumped a
    resting box up to |ω|≈185 rad/s; and (b) overwrote EVERY tracked body's pose
    with the free-flight predictor, clobbering the solver's box-box resolution
    for stacked bystanders. Both are fixed (live geometry + active-body-only
    write-back, mirroring the AVBD coupler). The old finite/penetration test
    missed this — a 6.5 m fly-off is still finite and the floor never penetrates.
    """
    h = BUILD[scene](device="cpu", solver="xpbd", cargo_material="fem_rigid",
                     **_iters_for("xpbd"))
    w = h.world
    S = w._solver
    imp = _avbd_idx(w, h.impactor_idx)
    idxs = [_avbd_idx(w, b.dcr_idx) for b in h.bodies
            if _avbd_idx(w, b.dcr_idx) != imp]
    P0 = S.positions().copy()
    drift = 0.0
    for _ in range(12):                       # 0.1 s — well before any drop lands
        w.step()
        P = S.positions()
        for i in idxs:
            drift = max(drift, float(np.linalg.norm(P[i] - P0[i])))
    # quasi-static settle is ~1–5 mm (matches AVBD); the old bug was metres.
    assert drift < 1.0e-2, (scene, drift)


def _run(scene, solver, material, n=80):
    h = BUILD[scene](device="cpu", solver=solver, cargo_material=material,
                     **_iters_for(solver))
    coupler = h.world.reduced_coupled_coupler
    solver_obj = h.world._solver
    max_pen = 0.0
    for _ in range(n):
        h.world.step()
        max_pen = max(max_pen, coupler.last_contact_residual)
    P = solver_obj.positions()
    a = (coupler.cargo_a[h.cargo_avbd_idx].copy()
         if h.cargo_avbd_idx is not None else None)
    return dict(h=h, max_pen=max_pen, P=P, q=h.rs.q.copy(), a=a)


@pytest.mark.parametrize("scene", SCENES)
def test_xpbd_production_scene_fem_rigid(scene):
    """Each production scene runs with an XPBD-coupled fem_rigid impactor:
    finite, bounded penetration, the impactor flexes, the support rings."""
    r = _run(scene, "xpbd", "fem_rigid", n=80)
    assert np.all(np.isfinite(r["P"])) and np.all(np.isfinite(r["q"]))
    assert np.all(np.isfinite(r["a"]))
    assert r["max_pen"] < 5e-3, (scene, r["max_pen"])
    assert np.abs(r["a"]).max() > 1e-8, (scene, np.abs(r["a"]).max())   # flexed
    assert np.abs(r["q"]).max() > 1e-9                                   # support rang


@pytest.mark.parametrize("scene", SCENES)
def test_avbd_production_scene_fem_rigid(scene):
    """The AVBD path on the same scenes stays the robust baseline (sub-mm
    penetration) — a regression guard for the shared cargo wiring."""
    r = _run(scene, "avbd", "fem_rigid", n=80)
    assert np.all(np.isfinite(r["P"])) and np.all(np.isfinite(r["q"]))
    assert r["max_pen"] < 5e-3, (scene, r["max_pen"])
    assert np.abs(r["a"]).max() > 1e-9


def test_production_scene_rigid_default_unchanged():
    """cargo_material=None keeps the impactor rigid (no cargo registered) on
    both solvers — the legacy behavior is the default."""
    for solver in ("avbd", "xpbd"):
        h = BUILD["truck"](device="cpu", solver=solver, cargo_material=None,
                           **_iters_for(solver))
        assert not h.world.reduced_coupled_coupler.cargo   # no cargo bodies
        assert h.cargo_cube is None
        for _ in range(30):
            h.world.step()
        assert np.all(np.isfinite(h.world._solver.positions()))


def test_fem_material_on_one_scene():
    """The fem material (world-fixed modes) also couples on a production scene."""
    r = _run("shelf", "xpbd", "fem", n=80)
    assert np.all(np.isfinite(r["a"]))
    assert r["max_pen"] < 5e-3, r["max_pen"]
    assert np.abs(r["a"]).max() > 1e-8
