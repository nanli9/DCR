"""Stage 6 acceptance tests — Spatial attenuation DCR (Eqs. 14–16, 19).

Criteria from dcr_implementation_prompt.md §6.6:
1. Impact at one end, resting bodies at other end receive attenuated impulse.
2. Attenuation vs distance: log-log slope matches -β.
3. Sweep β ∈ {0.5, 1, 2} and C ∈ {0.4, 1, 2}.
"""
import numpy as np

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis
from dcr.dcr.geodesic import heat_geodesic, cotan_laplacian
from dcr.dcr.spatial_dcr import SpatialDCRCoupler
from dcr.rigid import make_dynamic_box, make_static_plane, ConstraintSolver
from dcr.dcr import DCRWorld


def _make_long_slab_model():
    """Long slab (scaffold-like) for spatial attenuation tests."""
    length, width, height = 2.0, 0.3, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=20, ny=3, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    tol = 1e-8
    x_min, x_max = mesh.vertices[:, 0].min(), mesh.vertices[:, 0].max()
    z_min, z_max = mesh.vertices[:, 2].min(), mesh.vertices[:, 2].max()
    on_xmin = np.abs(mesh.vertices[:, 0] - x_min) < tol
    on_xmax = np.abs(mesh.vertices[:, 0] - x_max) < tol
    on_zmin = np.abs(mesh.vertices[:, 2] - z_min) < tol
    on_zmax = np.abs(mesh.vertices[:, 2] - z_max) < tol
    corner_mask = ((on_xmin & on_zmin) | (on_xmin & on_zmax) |
                   (on_xmax & on_zmin) | (on_xmax & on_zmax))
    fixed = np.where(corner_mask)[0].astype(np.int32)

    model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed,
                     alpha0=2.0, alpha1=1e-5)
    return ModalAnalysis(fem=model, num_modes=10)


# ---------------------------------------------------------------------------
# Test 1: Geodesic distance is correct (heat method)
# ---------------------------------------------------------------------------
def test_geodesic_distance():
    """Geodesic on a flat slab should approximate Euclidean distance."""
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=10, ny=6, nz=2)
    surface = mesh.extract_surface()

    # Pick a corner vertex.
    verts = surface.vertices
    corner_idx = np.argmin(np.linalg.norm(
        verts - np.array([verts[:, 0].min(), verts[:, 1].max(), verts[:, 2].min()]),
        axis=1,
    ))

    dist = heat_geodesic(surface, corner_idx)

    # Farthest vertex should be the opposite corner.
    opposite = np.array([verts[:, 0].max(), verts[:, 1].max(), verts[:, 2].max()])
    farthest_idx = np.argmin(np.linalg.norm(verts - opposite, axis=1))

    euclidean = np.linalg.norm(verts[farthest_idx] - verts[corner_idx])
    geodesic_far = dist[farthest_idx]

    # On a near-flat surface, geodesic ≈ euclidean (within 20%).
    rel_err = abs(geodesic_far - euclidean) / euclidean
    print(f"  Geodesic: {geodesic_far:.4f}, Euclidean: {euclidean:.4f}, "
          f"rel err: {rel_err:.2%}")
    assert rel_err < 0.20, f"Geodesic too far from Euclidean: {rel_err:.2%}"

    # Source should have distance ≈ 0.
    assert dist[corner_idx] < 0.01, f"Source distance not zero: {dist[corner_idx]:.4f}"


# ---------------------------------------------------------------------------
# Test 2: Attenuation decays with distance at correct rate
# ---------------------------------------------------------------------------
def test_attenuation_decay():
    """s = C * (r/r0)^{-β} should give slope -β on log-log plot."""
    ma = _make_long_slab_model()

    for beta in [0.5, 1.0, 2.0]:
        coupler = SpatialDCRCoupler(
            modal=ma, elastic_body_idx=0,
            C=1.0, beta=beta, r0=0.05,
        )

        # Test a range of distances.
        distances = np.array([0.1, 0.2, 0.5, 1.0, 2.0])
        attenuations = np.array([coupler.attenuation(r) for r in distances])

        # Fit log-log slope.
        log_r = np.log(distances / coupler.r0)
        log_s = np.log(attenuations)
        slope = np.polyfit(log_r, log_s, 1)[0]

        print(f"  β={beta}: measured slope = {slope:.3f}")
        assert abs(slope + beta) < 0.01, (
            f"β={beta}: expected slope {-beta}, got {slope:.3f}")


# ---------------------------------------------------------------------------
# Test 3: Distant bodies receive attenuated impulse
# ---------------------------------------------------------------------------
def test_spatial_dcr_scene():
    """Impact at one end of a long slab; boxes at varying distances respond
    with decreasing velocity."""
    ma = _make_long_slab_model()

    h = 1e-3
    world = DCRWorld(
        h=h,
        solver=ConstraintSolver(h=h, cfm=1e-6, erp=0.2, pgs_iterations=80),
        dcr_enabled=True,
    )

    table = make_static_plane(normal=(0, 1, 0), point=(0, 0, 0), friction=0.5)
    table_idx = world.add_body(table)

    coupler = SpatialDCRCoupler(
        modal=ma, elastic_body_idx=table_idx,
        C=1.0, beta=0.5,
    )
    world.add_spatial_coupler(coupler)

    # Boxes at different distances from the impact point (x=-0.8).
    box_xs = [-0.3, 0.0, 0.3, 0.6]
    box_idxs = []
    for x in box_xs:
        box = make_dynamic_box(
            0.2, 0.04, 0.02, 0.04,
            position=(x, 0.025, 0.0),
            restitution=0.0, friction=0.5,
        )
        box_idxs.append(world.add_body(box))

    # Heavy impactor at x=-0.8.
    impactor = make_dynamic_box(
        5.0, 0.06, 0.06, 0.06,
        position=(-0.8, 0.8, 0.0),
        restitution=0.1, friction=0.5,
    )
    imp_idx = world.add_body(impactor)

    # Settle.
    world.bodies[imp_idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx in box_idxs:
        world.bodies[idx].velocity[:] = 0
    world.bodies[imp_idx].is_static = False
    world.dcr_enabled = True

    # Simulate.
    max_vys = [0.0] * len(box_idxs)
    for _ in range(500):
        world.step()
        for i, idx in enumerate(box_idxs):
            vy = world.bodies[idx].velocity[1]
            if vy > max_vys[i]:
                max_vys[i] = vy

    print("  Box responses (max upward vy):")
    for i, x in enumerate(box_xs):
        print(f"    x={x:.1f}: vy = {max_vys[i]:.6f} m/s")

    # Closer boxes should respond more strongly.
    assert max_vys[0] > max_vys[-1], (
        f"Closer box didn't respond more: {max_vys[0]:.4e} vs {max_vys[-1]:.4e}")

    # All should have some response.
    assert all(v > 1e-6 for v in max_vys), (
        f"Some boxes didn't respond: {max_vys}")


# ---------------------------------------------------------------------------
# Test 4: Cotan Laplacian is symmetric and negative semi-definite
# ---------------------------------------------------------------------------
def test_cotan_laplacian():
    """L should be symmetric and have zero row sums."""
    mesh = make_slab_tet_mesh(0.5, 0.3, 0.05, nx=5, ny=3, nz=1)
    surface = mesh.extract_surface()
    L, M = cotan_laplacian(surface)

    # Symmetry.
    sym_err = abs(L - L.T).max()
    print(f"  Symmetry error: {sym_err:.2e}")
    assert sym_err < 1e-12, f"L not symmetric: {sym_err:.2e}"

    # Row sums ≈ 0 (L @ ones = 0 for a closed mesh; for open mesh, boundary
    # rows may not sum to exactly zero, but interior rows should).
    row_sums = np.abs(np.array(L.sum(axis=1)).ravel())
    max_row_sum = row_sums.max()
    print(f"  Max |row sum|: {max_row_sum:.2e}")
    assert max_row_sum < 1e-10, f"L row sums not zero: {max_row_sum:.2e}"

    # Mass should be positive.
    m_diag = M.diagonal()
    assert np.all(m_diag >= 0), "Negative mass entries"
    print(f"  Total surface area: {m_diag.sum():.4f}")
