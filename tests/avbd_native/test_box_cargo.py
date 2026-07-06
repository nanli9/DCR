"""Rect-box cargo bodies (all-cargo scenes): `build_fem_rigid_box` and
`box_corner_ids` generalize the cube-only builders to (hx,hy,hz) boxes so
plates / planks / cutlery carry real modal shapes instead of being collapsed
to a min-extent cube. The cube builders are exact-equivalence wrappers, so
the existing cube parity tests double as the no-regression check."""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.cargo.fem_rigid import (
    FEMRigidModalBody,
    _box_resolution,
    box_corner_ids,
    build_fem_rigid_box,
    build_fem_rigid_cube,
    build_rigid_box,
)
from dcr.avbd.cargo.abd import build_abd_box
from dcr.fem.material import Material

# fork-ish thin bar, plate-ish thin slab (the dinner scene's worst aspect ratios)
FORK_HALF = (0.10, 0.005, 0.012)
PLATE_HALF = (0.085, 0.010, 0.085)


def test_box_resolution_aspect_scaled():
    # longest axis gets the base count, every axis floors at 2 (midside node)
    assert _box_resolution((0.1, 0.1, 0.1), base=3) == (3, 3, 3)
    nx, ny, nz = _box_resolution(FORK_HALF, base=3)
    assert nx == 3 and ny == 2 and nz == 2


def test_box_corner_ids_order_and_position():
    body = build_fem_rigid_box(PLATE_HALF, n_elastic=3)
    half = np.asarray(PLATE_HALF)
    signs = np.array([[sx, sy, sz]
                      for sx in (-1.0, 1.0)
                      for sy in (-1.0, 1.0)
                      for sz in (-1.0, 1.0)])
    # corner order must match the (x-major) sign table; corners sit at ±half
    assert np.allclose(body.corner_body, signs * half, atol=1e-12)


def test_cube_wrapper_equivalence():
    """build_fem_rigid_cube must be the (size/2)³ box — same modes, corners."""
    cube = build_fem_rigid_cube(size=0.1, nx=3, n_elastic=4)
    box = build_fem_rigid_box((0.05,) * 3, resolution=(3, 3, 3), n_elastic=4)
    assert np.allclose(cube.omega2, box.omega2)
    assert np.allclose(cube.corner_body, box.corner_body)
    assert np.allclose(np.abs(cube.corner_modal), np.abs(box.corner_modal))
    assert cube.half_extent == box.half_extent == 0.05
    assert cube.half_extents == (0.05, 0.05, 0.05)


def test_box_body_invariants():
    mat = Material(E=1.0e6, nu=0.3, rho=600.0)
    body = build_fem_rigid_box(FORK_HALF, material=mat, n_elastic=3)
    assert isinstance(body, FEMRigidModalBody)
    assert body.k == 3
    # elastic eigenvalues positive and ascending
    assert np.all(body.omega2 > 0.0)
    assert np.all(np.diff(body.omega2) >= -1e-9)
    # total mass = rho * volume (lumped FEM mass is exact for the box)
    vol = 8.0 * np.prod(FORK_HALF)
    assert body.mass == pytest.approx(600.0 * vol, rel=1e-9)
    # anisotropic inertia: the long (x) axis has the SMALLEST moment
    I = np.diag(body.inertia0)
    assert I[0] < I[1] and I[0] < I[2]
    assert body.half_extents == FORK_HALF
    assert body.half_extent == pytest.approx(min(FORK_HALF))
    # skinning stays finite with a modal excitation
    z = body.rest_state()
    z[7:] = 1e-3
    assert np.all(np.isfinite(body.deformed_surface(z)))


def test_thin_plate_softer_than_compact_cube():
    """A thin plate's first bending mode must be softer (lower ω²) than a
    compact cube of the same material and footprint — the physical reason
    min-extent cube collapse misrepresented plates."""
    mat = Material(E=1.0e6, nu=0.3, rho=600.0)
    plate = build_fem_rigid_box(PLATE_HALF, material=mat, n_elastic=1)
    cube = build_fem_rigid_box((0.085,) * 3, material=mat, n_elastic=1)
    assert plate.omega2[0] < cube.omega2[0]


def test_rigid_box_k0():
    body = build_rigid_box(half_extents=PLATE_HALF)
    assert body.k == 0
    assert body.corner_modal.shape == (8, 3, 0)
    assert body.mass > 0.0


def test_abd_box_builds():
    body = build_abd_box(FORK_HALF)
    assert body.k == 9
    assert body.half_extents == FORK_HALF
    # affine mass core Q = Σ m x̄x̄ᵀ must be anisotropic for a thin bar
    Q = np.diag(body.affine_inertia)
    assert Q[0] > Q[1] and Q[0] > Q[2]


def test_box_corner_ids_matches_mesh():
    from dcr.geom.tet_mesh import make_beam_tet_mesh
    mesh = make_beam_tet_mesh(length=0.2, width=0.01, height=0.024,
                              nx=3, ny=2, nz=2)
    ids, coords = box_corner_ids(mesh, (0.1, 0.005, 0.012))
    assert len(np.unique(ids)) == 8
    assert np.allclose(np.abs(coords), (0.1, 0.005, 0.012), atol=1e-12)
