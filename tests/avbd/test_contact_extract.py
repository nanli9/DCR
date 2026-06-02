"""Verify the contact + impulse extractor produces sane DCR-side records."""
from __future__ import annotations

import numpy as np

from dcr.avbd import AVBDDCRWorld
from dcr.avbd.contact_extract import extract_contacts


def test_floor_contact_normals_are_into_box():
    """For a box settled on a Y-up floor, every Contact.normal should
    point from the floor INTO the box (= -y in our convention) and
    each contact should be tagged with body_b = floor_idx."""
    w = AVBDDCRWorld(h=1.0 / 120.0)
    fidx = w.add_floor(0.0)
    w.add_box(mass=1.0, half_extents=(0.1, 0.1, 0.1),
              position=(0.0, 0.5, 0.0))
    for _ in range(150):
        w.step()
    contacts = w.last_contacts
    assert len(contacts) >= 1, "expected at least one floor contact"
    for c in contacts:
        # Floor is body B (the world's floor synthesizing body_b).
        assert c.body_b == fidx, f"expected body_b={fidx} got {c.body_b}"
        # DCR convention "A into B" + Y-up floor => normal ≈ -ŷ.
        assert c.normal[1] < -0.99, (
            f"expected normal pointing -y, got {c.normal}")


def test_contacts_count_matches_4_corners():
    """A flat box at rest on the floor should have exactly 4 corner contacts.
    (FLOOR_CONTACT_6DOF emits 8 rows but only the 4 bottom-corner rows
    will have non-zero λ once settled.)"""
    w = AVBDDCRWorld(h=1.0 / 120.0)
    w.add_floor(0.0)
    w.add_box(mass=1.0, half_extents=(0.1, 0.1, 0.1),
              position=(0.0, 0.5, 0.0))
    for _ in range(200):
        w.step()
    n = len(w.last_contacts)
    assert n == 4, f"expected exactly 4 corner contacts, got {n}"


def test_lam_triples_have_right_shape():
    w = AVBDDCRWorld(h=1.0 / 120.0)
    w.add_floor(0.0)
    w.add_box(mass=1.0, half_extents=(0.1, 0.1, 0.1),
              position=(0.0, 0.5, 0.0))
    for _ in range(150):
        w.step()
    n = len(w.last_contacts)
    assert w.last_lam.shape == (3 * n,), (
        f"expected shape (3*{n},)={3*n} got {w.last_lam.shape}")
