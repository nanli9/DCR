"""Refinement-ladder rules + ring metric (benchmark plan §3)."""
from __future__ import annotations

import numpy as np
import pytest

from benchmarks.fem_gt.common import (
    SUPPORTS, _body_resolution, _ring_metrics, _slab_resolution,
)


def test_slab_resolution_ladder_truck():
    spec = SUPPORTS["truck"]                      # 2.5 x 1.5 x 0.06
    assert _slab_resolution(spec, 0) == (25, 15, 2)
    assert _slab_resolution(spec, 1) == (50, 30, 3)
    assert _slab_resolution(spec, 2) == (75, 45, 4)


def test_slab_resolution_r0_matches_legacy_rule():
    """R0 must reproduce the pre-ladder rule exactly (10/m, 2 thick, floors
    6/4) so the R0 rung is the same mesh the production runs measured."""
    for spec in SUPPORTS.values():
        legacy = (max(6, int(round(10.0 * spec.length))),
                  max(4, int(round(10.0 * spec.width))), 2)
        assert _slab_resolution(spec, 0) == legacy


def test_body_resolution_thin_plate_gets_bending_layers():
    plate = (0.085, 0.010, 0.085)                 # dinner plate half-extents
    assert _body_resolution(plate, 0) == (3, 2, 3)   # legacy: floor 2
    assert _body_resolution(plate, 1) == (4, 3, 4)   # R1: floor 3 on thin dim
    assert _body_resolution(plate, 2) == (6, 3, 6)


def test_body_resolution_r0_matches_make_box_fem_body_int_rule():
    """R0 tuple must equal what make_box_fem_body computes from an int
    resolution=3 (the pre-ladder path), for every production body shape."""
    shapes = [(0.10, 0.07, 0.08), (0.03, 0.05, 0.03), (0.06, 0.025, 0.12),
              (0.085, 0.010, 0.085), (0.10, 0.005, 0.012), (0.13, 0.065, 0.082)]
    for half in shapes:
        h = np.asarray(half)
        longest = float(h.max())
        legacy = tuple(max(2, int(round(3 * float(e) / longest))) for e in h)
        assert _body_resolution(half, 0) == legacy, half


def test_ring_metrics_recovers_offbin_sine():
    fs, T = 400.0, 1.2
    t = np.arange(int(T * fs)) / fs
    f0, amp, sag = 81.3, 5e-4, -1e-3              # off-bin (df = 0.833 Hz)
    u = sag + amp * np.sin(2 * np.pi * f0 * t)
    peak, ring = _ring_metrics(u, 1.0 / fs)
    assert peak == pytest.approx(abs(sag) + amp, rel=1e-3)
    assert ring == pytest.approx(f0, rel=0.01)    # parabolic interp < 1 %


def test_ring_metrics_short_trace_is_safe():
    peak, ring = _ring_metrics([1e-3] * 4, 0.01)
    assert peak == pytest.approx(1e-3)
    assert ring == 0.0
