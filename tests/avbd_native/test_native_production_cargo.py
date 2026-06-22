"""M2 — native deformable cargo in the 4 production scenes (no coupler).

The truck / ledge / shelf / dinner scenes accept solver="native" + a deformable
cargo material (fem_rigid | fem | abd): the impactor cube's elastic DOFs join the
augmented native modal vector via `world.add_native_cargo` (two_band_coupling.html).
This is a build/step matrix smoke + a cuda-residency check — the per-material
physics + parity live in test_native_cargo.py. The avbd/xpbd couplers are not
touched (the same scenes still build with solver="avbd"/"xpbd").
"""
from __future__ import annotations

import numpy as np
import pytest
import warp as wp

from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table


def _has_cuda() -> bool:
    try:
        wp.init()
        return wp.get_cuda_device_count() > 0
    except Exception:
        return False


_SCENES = {
    "truck": build_reduced_truck,
    "ledge": build_reduced_ledge,
    "shelf": build_reduced_shelf,
    "dinner": build_reduced_dinner_table,
}


def _build(scene: str, material: str, device: str = "cpu"):
    kw = dict(device=device, solver="native", cargo_material=material,
              iterations=8, avbd_substeps=4)
    if scene != "dinner":
        kw["impactor_drop_height"] = 0.05
    return _SCENES[scene](**kw)


@pytest.mark.parametrize("scene", ["truck", "ledge", "shelf", "dinner"])
@pytest.mark.parametrize("material", ["fem_rigid", "fem", "abd"])
def test_native_cargo_production_scene_cpu(scene, material):
    """Every (scene × material) combination builds with no coupler, steps without
    NaN, and the impactor cube deforms (its modal block is loaded)."""
    h = _build(scene, material)
    assert h.world.reduced_coupled_coupler is None, "native path attaches no coupler"
    s = h.world._solver
    for _ in range(60):
        h.world.step()
    assert np.all(np.isfinite(s.positions())), "no NaN over the run"
    cidx = getattr(h, "cargo_avbd_idx", None)
    if cidx is None:
        cidx = getattr(h.rs, "_native_cargo_avbd_idx", None)
    assert cidx is not None, "cargo should be registered on the native path"
    assert np.linalg.norm(s.cargo_a(cidx)) > 1e-12, "the cargo cube must deform"


@pytest.mark.parametrize("scene", ["truck", "ledge", "shelf", "dinner"])
def test_native_rigid_cargo_production_scene_cpu(scene):
    """The "rigid" (k=0) cargo material in every production scene: it builds with
    no coupler and steps without NaN, but — carrying no elastic modes — it does
    NOT deform (empty a-block). It is the no-deformation baseline alongside the
    fem_rigid/fem/abd materials above."""
    h = _build(scene, "rigid")
    assert h.world.reduced_coupled_coupler is None, "native path attaches no coupler"
    s = h.world._solver
    for _ in range(60):
        h.world.step()
    assert np.all(np.isfinite(s.positions())), "no NaN over the run"
    cidx = getattr(h, "cargo_avbd_idx", None)
    if cidx is None:
        cidx = getattr(h.rs, "_native_cargo_avbd_idx", None)
    assert cidx is not None, "cargo should be registered on the native path"
    assert s.cargo_a(cidx).size == 0, "the rigid cargo cube carries no modes"


@pytest.mark.skipif(not _has_cuda(), reason="no CUDA device")
@pytest.mark.parametrize("scene", ["truck", "shelf"])
@pytest.mark.parametrize("material", ["fem_rigid", "abd"])
def test_native_cargo_production_scene_cuda_resident(scene, material):
    """On cuda the production-scene native cargo path is device-resident (linear
    via the constant block, abd via the V⊥ device kernel) and finite."""
    h = _build(scene, material, device="cuda:0")
    s = h.world._solver
    for _ in range(40):
        h.world.step()
    assert s._modal_resident is True, "native cargo should be device-resident on cuda"
    assert np.all(np.isfinite(s.positions()))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
