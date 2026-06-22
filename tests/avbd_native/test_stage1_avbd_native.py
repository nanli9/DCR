"""Stage 1 — AVBD ported onto the shared interface, behaviour-neutral.

solver="avbd" now selects the NATIVE AVBD solver (the in-solver (z, q) modal +
cargo q-block), NOT the external reduced coupler. This test pins the Stage-1
acceptance from prompts/native_dual_solver_build_plan.md:

* the 4 production scenes + the cargo scene build & step on solver="avbd" with
  world.reduced_coupled_coupler is None and no NaN;
* the deformable cargo deforms on the native AVBD path;
* the repoint is behaviour-neutral: solver="avbd" reproduces solver="native"
  bit-for-bit (they are the same code path), so the validated M1/M2 native
  trajectories are preserved exactly.

The AVBD *coupler* (now "avbd_coupler") keeps its own coverage in
test_production_scenes / test_dynamic_coupling until Stage 6 deletes it.
CPU-only here; the device-resident native path is covered by
test_native_production_cargo (cuda) and test_native_qblock_device.
"""
from __future__ import annotations

import numpy as np
import pytest

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table
from scenes.reduced_fem_rigid_cargo import build_cargo_scene

_PROD = {
    "truck": build_reduced_truck,
    "ledge": build_reduced_ledge,
    "shelf": build_reduced_shelf,
    "dinner": build_reduced_dinner_table,
}


def _build_prod(scene: str, solver: str, material: str | None):
    kw = dict(device="cpu", solver=solver, cargo_material=material,
              iterations=8, avbd_substeps=4)
    if scene != "dinner":
        kw["impactor_drop_height"] = 0.05
    return _PROD[scene](**kw)


@pytest.mark.parametrize("scene", ["truck", "ledge", "shelf", "dinner"])
def test_production_scene_avbd_is_native_no_coupler(scene):
    """Each production scene builds on solver="avbd" with NO coupler, steps
    without NaN, and the fem_rigid cargo cube deforms (native a-block loaded)."""
    h = _build_prod(scene, "avbd", "fem_rigid")
    assert h.world.reduced_coupled_coupler is None, "solver='avbd' must be native (no coupler)"
    s = h.world._solver
    for _ in range(60):
        h.world.step()
    assert np.all(np.isfinite(s.positions())), "no NaN over the run"
    cidx = getattr(h, "cargo_avbd_idx", None)
    if cidx is None:
        cidx = getattr(h.rs, "_native_cargo_avbd_idx", None)
    assert cidx is not None, "cargo registered on the native AVBD path"
    assert np.linalg.norm(s.cargo_a(cidx)) > 1e-12, "the cargo cube must deform"


def test_cargo_scene_avbd_is_native_no_coupler():
    """The single-cube cargo scene builds on solver="avbd" with no coupler and
    the cube flexes."""
    h = build_cargo_scene("fem_rigid", solver="avbd", device="cpu",
                          drop_height=0.03)
    assert h.coupler is None, "solver='avbd' must be native (no coupler)"
    s = h.world._solver
    for _ in range(80):
        h.world.step()
    assert np.all(np.isfinite(s.positions()))
    assert np.linalg.norm(s.cargo_a(h.avbd_idx)) > 1e-12, "the cube must flex"


def test_avbd_repoint_is_behaviour_neutral_vs_native():
    """The Stage-1 repoint is behaviour-neutral: solver="avbd" and the legacy
    solver="native" alias drive the IDENTICAL native code path, so their
    trajectories are bit-for-bit equal."""
    def run(solver):
        h = build_reduced_truck(device="cpu", solver=solver,
                                cargo_material="fem_rigid",
                                impactor_drop_height=0.05,
                                iterations=8, avbd_substeps=4)
        s = h.world._solver
        for _ in range(40):
            h.world.step()
        return s.positions().copy(), s.orientations().copy(), np.asarray(h.rs.q).copy()

    Pa, Qa, qa = run("avbd")
    Pn, Qn, qn = run("native")
    assert np.array_equal(Pa, Pn), "positions diverged: repoint is not behaviour-neutral"
    assert np.array_equal(Qa, Qn), "orientations diverged"
    assert np.array_equal(qa, qn), "modal q diverged"


def test_unknown_solver_string_rejected():
    with pytest.raises(ValueError, match="unknown solver"):
        build_reduced_truck(device="cpu", solver="pgs")
