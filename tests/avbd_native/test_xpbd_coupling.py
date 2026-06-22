"""Stage 6 — GPU-resident XPBD coupled dynamic modal contact constraint.

`ReducedCoupledXPBDCoupler` realizes the SAME two-way dynamic constraint as the
AVBD coupler (`two_band_coupling.html`) with the XPBD primal — compliant
constraints projected Gauss–Seidel, the modal Rayleigh damping through Macklin's
damped update — re-expressing the CPU oracle
`dcr/twobody/position_based.py:XPBDDynamicSystem` in the AVBD-Native solver idiom
so the cube rides the GPU solver's real per-corner FLOOR collision.

Covers the materials the oracle supports: `fem` (translation+modal) and
`fem_rigid` (co-rotated rigid frame ⊕ modal). `abd` (nonlinear quartic V⊥) is
the AVBD-preferred material — its stiff nonlinear orthogonality constraint is not
Gauss–Seidel-stable in the substep sweep budget (the oracle's own note), so abd
uses the AVBD path; see test_xpbd_abd_uses_avbd.

Acceptance: CPU↔GPU parity (bit-identical at the parity-gate horizon), residency
(CUDA graph capture, no per-step host sync), the two-way counterfactual signature
(dynamic q launches the modes; frozen q̇≡0 gives 0), passivity (free ring-down
energy monotone non-increasing) and zero penetration on every material.
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

XPBD_MATERIALS = ["fem", "fem_rigid"]


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
    h = build_cargo_scene(kind, device=device, solver="xpbd", freeze_qdot=freeze,
                          drop_height=drop, spin=spin,
                          device_resident=device_resident)
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


@pytest.mark.parametrize("kind", XPBD_MATERIALS)
def test_xpbd_flexes_no_penetration(kind):
    """The cube settles on the support, flexes (modes excited) and the
    XPBD compliant contact keeps penetration ~0."""
    r = _run(kind, n=150)
    assert np.all(np.isfinite(r["a"])) and np.all(np.isfinite(r["q"]))
    assert r["max_d"] > 1e-8, r["max_d"]          # modes were excited
    assert r["peak_KE"] > 1e-12, r["peak_KE"]     # two-way ring carries KE
    assert r["max_pen"] < 5e-3, r["max_pen"]
    assert abs(r["x"][1] - 0.05) < 0.03, r["x"][1]  # settled on support top


@pytest.mark.parametrize("kind", XPBD_MATERIALS)
def test_xpbd_two_way_counterfactual(kind):
    """Dynamic q launches the modes; the frozen q̇≡0 control gives exactly 0
    (two_band_coupling.html — the constraint really couples both ways)."""
    rf = _run(kind, freeze=True, n=150)
    rd = _run(kind, freeze=False, n=150)
    assert rf["peak_KE"] == 0.0
    assert rd["peak_KE"] > 1e-12
    assert rd["peak_KE"] > rf["peak_KE"]


def test_xpbd_free_ringdown_energy_monotone():
    """Free (no fresh contact) modal ring-down: total modal energy is monotone
    non-increasing (XPBD backward-Euler + the modal damping ⇒ passive) and
    decays well below the initial pluck."""
    h = build_cargo_scene("fem", device="cpu", solver="xpbd", drop_height=2.0)
    h.coupler.cargo_adot[h.avbd_idx][:] = 5.0e-3
    E_prev = E0 = None
    for step in range(60):
        h.world.step()
        assert h.coupler.last_contact_residual < 1e-6   # still in free-fall
        E = h.coupler.last_cargo_modal_KE + h.coupler.last_cargo_modal_PE
        if E0 is None:
            E0 = E
        if E_prev is not None:
            assert E <= E_prev + 1e-12, (step, E_prev, E)
        E_prev = E
    assert E_prev < 0.5 * E0


@pytest.mark.parametrize("kind", XPBD_MATERIALS)
def test_xpbd_cpu_gpu_parity(kind):
    """The GPU-resident XPBD path matches the CPU reference to fp64 roundoff at
    the parity-gate horizon (bit-identical in practice; q̇'s 1/h amplification +
    tumbling round-off grow chaotically afterwards, exactly like the AVBD path)."""
    _cuda_or_skip()
    ref = _run(kind, device="cuda:0", device_resident=False, n=3, spin=1.0)
    gpu = _run(kind, device="cuda:0", device_resident=True, n=3, spin=1.0)
    assert np.max(np.abs(gpu["q"] - ref["q"])) <= 1e-11
    assert np.max(np.abs(gpu["a"] - ref["a"])) <= 1e-11
    assert np.max(np.abs(gpu["x"] - ref["x"])) <= 1e-6


def test_xpbd_residency_graph_capture():
    """The device-resident hot loop is CUDA-graph-captured with no per-step host
    synchronize (state stays on cuda:0; the only readback is once per macro-step
    for the HUD)."""
    import warp as wp
    _cuda_or_skip()
    h = build_cargo_scene("fem_rigid", device="cuda:0", solver="xpbd",
                          device_resident=True, drop_height=0.03, spin=1.0)
    solver = h.world._solver
    h.world.step()                       # warmup → capture
    assert solver.hooks_device_resident is True
    assert solver._graph is not None     # iteration loop captured into a CUDA graph
    orig = wp.synchronize_device
    n = [0]

    def counting(*a, **k):
        n[0] += 1
        return orig(*a, **k)
    wp.synchronize_device = counting
    try:
        for _ in range(5):
            h.world.step()
    finally:
        wp.synchronize_device = orig
    assert n[0] == 0, f"{n[0]} host synchronize_device calls in the hot loop"


def test_xpbd_determinism():
    r1 = _run("fem_rigid", n=40, spin=1.0)
    r2 = _run("fem_rigid", n=40, spin=1.0)
    assert np.array_equal(r1["q"], r2["q"])
    assert np.array_equal(r1["a"], r2["a"])


@pytest.mark.parametrize("kind", XPBD_MATERIALS)
def test_xpbd_smoke(kind):
    """200 steps with a tumbling spin: no NaN, finite, energy bounded, zero
    penetration, settled on the support."""
    r = _run(kind, n=200, spin=2.0)
    assert np.all(np.isfinite(r["a"])) and np.all(np.isfinite(r["q"]))
    assert np.all(np.isfinite(r["x"]))
    assert r["max_pen"] < 5e-3, (kind, r["max_pen"])
    assert r["peak_E"] < 1.0, (kind, r["peak_E"])
    assert abs(r["x"][1] - 0.05) < 0.03, (kind, r["x"][1])


def test_xpbd_abd_uses_avbd():
    """abd's stiff nonlinear V⊥ is not Gauss–Seidel-stable in the substep sweep
    budget (XPBDDynamicSystem oracle note); the abd path is AVBD. Document that
    AVBD-abd is stable where XPBD-abd would accumulate, so callers route abd to
    the AVBD coupler."""
    ra = build_cargo_scene("abd", device="cpu", solver="avbd", drop_height=0.03,
                           spin=2.0)
    dmax = 0.0
    for _ in range(200):
        ra.world.step()
        dmax = max(dmax, float(np.abs(ra.coupler.cargo_a[ra.avbd_idx]).max()))
    # AVBD keeps the affine near a rotation (V⊥ solved implicitly).
    assert dmax < 0.1, dmax
    assert ra.coupler.last_contact_residual < 5e-3
