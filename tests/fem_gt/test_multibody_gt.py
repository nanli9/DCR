"""Multi-body all-FEM ground truth (`dcr/fem/multibody_gt.py`) acceptance:

1. Static contact ledger vs the analytic baseline (validation plan baseline
   A): a settled two-box stack must carry Σf = (mass above)·g per joint.
2. A corner-fixed slab sags under a resting box (deflection field u_y < 0).
3. Rigid translation is a zero-energy mode: free fall accrues no elastic
   energy and tracks the ballistic COM.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.fem.material import Material
from dcr.fem.multibody_gt import (
    FEMBody,
    MultiFEMSim,
    corner_column_nodes,
    make_box_fem_body,
)
from dcr.geom.tet_mesh import make_slab_tet_mesh
from dcr.fem.fem_model import FEMModel

G = 9.81
# stiff, well-damped test material so penalty transients settle quickly
MAT = Material(E=1.0e9, nu=0.3, rho=600.0)


def _settled_ledger(rec, key, frac=0.5):
    """Mean ledger force over the trailing `frac` of recorded frames."""
    frames = rec["ledger"][int(len(rec["ledger"]) * (1.0 - frac)):]
    vals = [f[key] for f in frames if key in f]
    assert vals, f"ledger key {key} never active in the settle window"
    return float(np.mean(vals))


def test_two_box_stack_static_ledger():
    h = 5e-5
    sim = MultiFEMSim(h_fine=h, floor_y=0.0)
    lower = sim.add_body(make_box_fem_body(
        "lower", (0.05, 0.05, 0.05), (0.0, 0.05 + 5e-5, 0.0), MAT,
        h_fine=h, alpha0=8.0))
    upper = sim.add_body(make_box_fem_body(
        "upper", (0.04, 0.04, 0.04), (0.0, 0.10 + 0.04 + 1e-4, 0.0), MAT,
        h_fine=h, alpha0=8.0))
    # 1 s settle: the penalty joint force carries a slow (~0.15 s) beat, so
    # the ledger check needs a half-second averaging window
    rec = sim.run(1.0, record_every=200)

    m_low, m_up = lower.total_mass, upper.total_mass
    f_joint = _settled_ledger(rec, ("upper", "lower"))
    f_floor = _settled_ledger(rec, ("lower", "floor"))
    # per-joint Σf = (stack-above)·mg within 2% (the plan's ledger acceptance)
    assert f_joint == pytest.approx(m_up * G, rel=0.02)
    assert f_floor == pytest.approx((m_low + m_up) * G, rel=0.02)
    # nothing blew up; bodies are where a settled stack should be
    assert np.all(np.isfinite(rec["com_y"]["upper"]))
    assert rec["com_y"]["upper"][-1] == pytest.approx(0.14, abs=5e-3)


def test_slab_sags_under_resting_box():
    h = 5e-5
    mesh = make_slab_tet_mesh(length=1.0, width=0.6, height=0.05,
                              nx=10, ny=6, nz=2)
    slab_fem = FEMModel(mesh=mesh, material=Material(E=1.1e9, nu=0.3, rho=770.0),
                        fixed_nodes=corner_column_nodes(mesh),
                        alpha0=2.0, alpha1=1e-5)
    sim = MultiFEMSim(h_fine=h)
    slab = sim.add_body(FEMBody(name="slab", fem=slab_fem,
                                origin=np.array([0.0, 0.0, 0.0]), h_fine=h))
    sim.add_body(make_box_fem_body(
        "box", (0.06, 0.04, 0.06), (0.0, 0.025 + 0.04 + 1e-4, 0.0), MAT,
        h_fine=h, alpha0=8.0))
    rec = sim.run(0.4, record_every=100)

    uy = rec["top_uy"]["slab"][-1]
    assert np.all(np.isfinite(uy))
    # mid-span sags downward; the fixed corners hold
    assert uy.min() < -1e-7
    # energies bounded (no penalty blow-up)
    for name in ("slab", "box"):
        assert rec["elastic_E"][name][-1] < 10.0
        assert rec["kinetic_E"][name][-1] < 10.0


def test_free_fall_is_zero_energy_translation():
    h = 5e-5
    sim = MultiFEMSim(h_fine=h, floor_y=-10.0)
    body = sim.add_body(make_box_fem_body(
        "faller", (0.05, 0.05, 0.05), (0.0, 1.0, 0.0), MAT, h_fine=h,
        alpha0=0.0))    # alpha0 would drag the free fall (see builder NOTE)
    y0 = body.com_y()
    t = 0.1
    sim.run(t, record_every=10_000)
    # ballistic COM (implicit Newmark of a pure translation is exact here)
    assert body.com_y() - y0 == pytest.approx(-0.5 * G * t * t, rel=1e-3)
    # translation must cost no elastic energy (linear-FEM null mode); the
    # residual ~3e-10 J is lumped-mass gravity self-strain, 9 orders below
    # the mgh problem scale (~0.3 J)
    assert body.elastic_energy() < 1e-8
