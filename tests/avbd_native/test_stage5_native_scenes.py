"""Stage 5 — both native solvers in every scene, no coupler.

solver="avbd" → SolverAVBD, solver="xpbd" → SolverXPBD; the SAME scene runs on
either with reduced_coupled_coupler is None (the coupler is gone from the
production path — reachable only via the transitional "*_coupler" selectors
until Stage 6 deletes it). CPU matrix (the XPBD device-residency pass is
deferred); the AVBD-native cuda matrix stays covered by test_native_production_cargo.
"""
from __future__ import annotations

import numpy as np
import pytest

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_fem_rigid_cargo import build_cargo_scene

_PROD = {"truck": build_reduced_truck, "ledge": build_reduced_ledge,
         "shelf": build_reduced_shelf, "dinner": build_reduced_dinner_table}


def _iters(solver):
    return {"iterations": 16, "avbd_substeps": 6} if solver == "xpbd" else {
        "iterations": 8, "avbd_substeps": 4}


@pytest.mark.parametrize("solver", ["avbd", "xpbd"])
@pytest.mark.parametrize("scene", ["truck", "ledge", "shelf", "dinner"])
def test_production_scene_native_no_coupler(scene, solver):
    """Each production scene builds & steps on each native solver with NO coupler
    and no NaN; the fem_rigid cargo cube deforms (native a-block loaded)."""
    kw = dict(device="cpu", solver=solver, cargo_material="fem_rigid",
              **_iters(solver))
    if scene != "dinner":
        kw["impactor_drop_height"] = 0.05
    h = _PROD[scene](**kw)
    assert h.world.reduced_coupled_coupler is None, (scene, solver, "no coupler")
    s = h.world._solver
    cidx = getattr(h.rs, "_native_cargo_avbd_idx", None)
    if cidx is None:
        cidx = getattr(h, "cargo_avbd_idx", None)
    assert cidx is not None
    peak_def = 0.0
    for _ in range(40):
        h.world.step()
        peak_def = max(peak_def, float(np.linalg.norm(s.cargo_a(cidx))))
    assert np.all(np.isfinite(s.positions())), (scene, solver, "no NaN")
    # peak (not final) deformation: the cube flexes on impact then rings down.
    assert peak_def > 1e-12, (scene, solver, "cube deforms")


@pytest.mark.parametrize("solver", ["avbd", "xpbd"])
@pytest.mark.parametrize("material", ["rigid", "fem_rigid", "fem", "abd"])
def test_cargo_scene_native_matrix(material, solver):
    """The single-cube cargo scene builds & steps on each native solver × each
    material with no coupler and no NaN (rigid k=0 carries no modes)."""
    h = build_cargo_scene(material, solver=solver, device="cpu",
                          drop_height=0.03,
                          iterations=16 if solver == "xpbd" else 8,
                          avbd_substeps=6 if solver == "xpbd" else 4)
    assert h.coupler is None, (material, solver, "no coupler")
    s = h.world._solver
    peak_def = 0.0
    for _ in range(60):
        h.world.step()
        peak_def = max(peak_def, float(np.linalg.norm(s.cargo_a(h.avbd_idx)))
                       if s.cargo_a(h.avbd_idx).size else 0.0)
    assert np.all(np.isfinite(s.positions()))
    if material == "rigid":
        assert s.cargo_a(h.avbd_idx).size == 0
    else:
        assert peak_def > 1e-12, (material, solver, "cube flexes")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
