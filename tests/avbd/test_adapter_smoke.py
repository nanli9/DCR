"""Phase A smoke test: AVBDDCRWorld constructs, registers bodies, steps."""
from __future__ import annotations

import numpy as np

from dcr.avbd import AVBDDCRWorld


def test_world_constructs():
    w = AVBDDCRWorld(h=1.0 / 120.0)
    assert w.h == 1.0 / 120.0
    assert w._solver is not None


def test_add_floor_and_box():
    w = AVBDDCRWorld(h=1.0 / 120.0)
    fidx = w.add_floor(floor_y=0.0)
    bidx = w.add_box(mass=1.0, half_extents=(0.1, 0.1, 0.1),
                     position=(0.0, 0.5, 0.0))
    assert fidx == 0
    assert bidx == 1
    assert w._descs[fidx].dcr_body.is_static
    assert not w._descs[bidx].dcr_body.is_static


def test_runs_n_steps_without_error():
    w = AVBDDCRWorld(h=1.0 / 120.0)
    w.add_floor(0.0)
    w.add_box(mass=1.0, half_extents=(0.1, 0.1, 0.1),
              position=(0.0, 0.5, 0.0))
    for _ in range(10):
        w.step()
    assert w.time > 0.0


def test_box_falls_and_settles():
    """A free box dropped above the floor should settle on it."""
    w = AVBDDCRWorld(h=1.0 / 120.0)
    w.add_floor(0.0)
    bidx = w.add_box(mass=1.0, half_extents=(0.1, 0.1, 0.1),
                     position=(0.0, 0.5, 0.0))
    for _ in range(150):
        w.step()
    body = w._descs[bidx].dcr_body
    # Box should rest with bottom face on floor (center at y ≈ half_extent).
    assert body.position[1] == np.float32(0.1) or abs(body.position[1] - 0.1) < 1e-3, (
        f"settled y={body.position[1]} (expected ~0.1)")
    # Velocity should be near zero.
    assert np.linalg.norm(body.velocity[:3]) < 0.05
