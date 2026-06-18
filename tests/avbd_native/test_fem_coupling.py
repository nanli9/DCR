"""Stage 5 — fem cube material (translation+modal, NO co-rotation).

The fem material is a restriction of fem_rigid (reference
`dcr/twobody/reduced_body.py:FEMModalBody`): the elastic modes are world-fixed
(the modal contact gradient is n̂ᵀ·Φ_c, not the co-rotated n̂ᵀ·R·Φ_c), so the
cube translates + flexes without the modes riding a tumbling frame. It reuses
the entire augmented-modal coupling (the only difference is `corotate=False`).

Plus the 3-material smoke (fem_rigid / abd / fem on the cargo scene, 200 steps:
no NaN, finite, energy bounded) — the Stage-5 acceptance matrix on one scene
(the full 4-scene × 3-material matrix is exercised by the Stage-7 viser wiring).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_fem_rigid_cargo import build_cargo_scene


def _cuda_or_skip():
    import warp as wp
    try:
        if wp.get_cuda_device_count() < 1:
            pytest.skip("no CUDA device")
    except Exception:
        pytest.skip("warp CUDA unavailable")
    return "cuda:0"


def _run(kind, *, device="cpu", device_resident=False, freeze=False,
         n=150, drop=0.03, spin=0.0, pluck=0.0):
    h = build_cargo_scene(kind, device=device, freeze_qdot=freeze, drop_height=drop,
                          spin=spin, device_resident=device_resident)
    if pluck != 0.0:
        h.coupler.cargo_adot[h.avbd_idx][:] = pluck
    solver = h.world._solver
    peak_KE, peak_E, max_pen, max_d = 0.0, 0.0, 0.0, 0.0
    for _ in range(n):
        h.world.step()
        peak_KE = max(peak_KE, h.coupler.last_cargo_modal_KE)
        peak_E = max(peak_E, h.coupler.last_cargo_modal_KE
                     + h.coupler.last_cargo_modal_PE)
        max_pen = max(max_pen, h.coupler.last_contact_residual)
        max_d = max(max_d, float(np.abs(h.coupler.cargo_a[h.avbd_idx]).max()))
    return dict(handle=h, peak_KE=peak_KE, peak_E=peak_E, max_pen=max_pen,
                max_d=max_d, a=h.coupler.cargo_a[h.avbd_idx].copy(),
                q=h.rs.q.copy(), x=solver.positions()[h.avbd_idx].copy())


def test_fem_flexes_no_corotation():
    """The fem cube flexes (modes excited) and is NOT co-rotated."""
    h = build_cargo_scene("fem", device="cpu")
    assert h.coupler.cargo[h.avbd_idx].corotate is False
    r = _run("fem", n=150)
    assert np.all(np.isfinite(r["a"]))
    assert r["max_d"] > 1e-8, r["max_d"]
    assert r["peak_KE"] > 1e-12, r["peak_KE"]
    assert r["max_pen"] < 5e-3, r["max_pen"]


def test_fem_free_ringdown_energy_monotone():
    h = build_cargo_scene("fem", device="cpu", drop_height=2.0)
    h.coupler.cargo_adot[h.avbd_idx][:] = 5.0e-3
    om2 = h.coupler.cargo[h.avbd_idx].omega2
    E_prev = E0 = None
    for step in range(60):
        h.world.step()
        assert h.coupler.last_contact_residual < 1e-6
        E = h.coupler.last_cargo_modal_KE + h.coupler.last_cargo_modal_PE
        if E0 is None:
            E0 = E
        if E_prev is not None:
            assert E <= E_prev + 1e-12, (step, E_prev, E)
        E_prev = E
    assert E_prev < 0.5 * E0


def test_fem_cpu_gpu_parity():
    _cuda_or_skip()
    ref = _run("fem", device="cuda:0", device_resident=False, n=3)
    gpu = _run("fem", device="cuda:0", device_resident=True, n=3)
    assert np.max(np.abs(gpu["q"] - ref["q"])) <= 1e-11
    assert np.max(np.abs(gpu["a"] - ref["a"])) <= 1e-11
    assert np.max(np.abs(gpu["x"] - ref["x"])) <= 1e-6


def test_fem_two_way_counterfactual():
    rf = _run("fem", freeze=True, n=150)
    rd = _run("fem", freeze=False, n=150)
    assert rf["peak_KE"] == 0.0
    assert rd["peak_KE"] > 1e-12
    assert rd["peak_KE"] > rf["peak_KE"]


@pytest.mark.parametrize("kind", ["fem_rigid", "abd", "fem"])
def test_three_material_smoke(kind):
    """Each cube material runs 200 steps with no NaN, stays finite + bounded,
    zero penetration, energy bounded (the Stage-5 matrix on the cargo scene)."""
    r = _run(kind, n=200, spin=2.0)
    assert np.all(np.isfinite(r["a"])) and np.all(np.isfinite(r["q"]))
    assert np.all(np.isfinite(r["x"]))
    assert r["max_pen"] < 5e-3, (kind, r["max_pen"])
    assert r["peak_E"] < 1.0, (kind, r["peak_E"])     # bounded (no blow-up)
    assert abs(r["x"][1] - 0.05) < 0.03, (kind, r["x"][1])   # settled on support
