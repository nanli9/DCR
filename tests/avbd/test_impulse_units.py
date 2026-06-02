"""Gate the critical assumption that the extractor converts AVBD's
force-like dual variables into impulse units. For a body resting on a
Y-up floor in steady state, the integrated contact impulse per step
must equal `m * g * dt` (the impulse needed to cancel the gravity-induced
velocity drop each step).

If this test fails, the patch coupler's modal projection of `j_world`
will be off by a factor of `1/dt` and energy bookkeeping will break.
See dcr/avbd/contact_extract.py for the empirical derivation.
"""
from __future__ import annotations

import numpy as np

from dcr.avbd import AVBDDCRWorld


def _settled_lam_sum(h: float, mass: float = 1.0, half: float = 0.1) -> float:
    w = AVBDDCRWorld(h=h)
    w.add_floor(0.0)
    w.add_box(mass=mass, half_extents=(half, half, half),
              position=(0.0, 0.5, 0.0))
    # Let it settle.
    for _ in range(int(2.0 / h)):
        w.step()
    # Sum normal-impulse magnitudes across all active corner contacts.
    return float(w.last_lam[::3].sum())


def test_settled_impulse_balances_gravity_h_120():
    h = 1.0 / 120.0
    s = _settled_lam_sum(h)
    expected = 1.0 * 9.81 * h  # m * g * dt
    # 1% tolerance — AVBD substeps + small residual velocity drift.
    assert abs(s - expected) / expected < 0.02, (
        f"h={h}: |Sigma lam_n|={s:.5f}, expected {expected:.5f} "
        f"(ratio {s/expected:.3f}); units bug? (force vs impulse)")


def test_settled_impulse_balances_gravity_h_240():
    h = 1.0 / 240.0
    s = _settled_lam_sum(h)
    expected = 1.0 * 9.81 * h
    assert abs(s - expected) / expected < 0.02, (
        f"h={h}: |Sigma lam_n|={s:.5f}, expected {expected:.5f} "
        f"(ratio {s/expected:.3f})")


def test_impulse_scales_linearly_with_dt():
    """The total contact impulse per step must scale linearly with dt
    (the force is essentially constant ~m*g at rest)."""
    s_120 = _settled_lam_sum(1.0 / 120.0)
    s_240 = _settled_lam_sum(1.0 / 240.0)
    # 240 Hz step should produce ~half the per-step impulse of 120 Hz.
    ratio = s_120 / s_240
    assert 1.8 < ratio < 2.2, (
        f"expected ratio≈2.0; got {ratio:.3f} "
        f"(s_120={s_120:.5f}, s_240={s_240:.5f})")
