"""Stage X3 — the FEM-modal native support builder.

Validates `benchmarks/paper_eval/x3_ground_truth/fem_modal_support.py`: the
support's reduced matrices ARE the true FEM eigenmodes (mass-normalized ⇒
Mq = I, Kq = diag(ω²)), its grid basis reproduces the FEM mode shapes, and it
installs into both native solvers exactly like the synthetic support. This is
the correctness anchor for X3 (paper Eq. 6/7): the native arm is a modal
reduction of the same operator the CoupledFEMRigidSim ground truth integrates.
"""
import numpy as np
import pytest

from dcr.geom.tet_mesh import make_slab_tet_mesh
from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.modal.modal_analysis import ModalAnalysis
from dcr.avbd.reduced_support import evaluate_basis_at_point

from benchmarks.paper_eval.x3_ground_truth.fem_modal_support import (
    make_fem_modal_support, fix_corners,
)

L, W, T = 1.0, 0.6, 0.05
E, NU, RHO = 1.1e9, 0.3, 770.0
NX, NZ = 21, 11


def _fem():
    mesh = make_slab_tet_mesh(length=L, width=W, height=T, nx=10, ny=6, nz=2)
    return FEMModel(mesh=mesh, material=Material(E=E, nu=NU, rho=RHO),
                    fixed_nodes=fix_corners(mesh), alpha0=2.0, alpha1=1e-5)


@pytest.fixture(scope="module")
def support():
    fem = _fem()
    rs, modal = make_fem_modal_support(
        fem, num_modes=12, y_rest=T / 2.0, n_grid_x=NX, n_grid_z=NZ,
        probe_xz=[(-0.3, 0.0), (0.3, 0.0)], length=L, width=W)
    return rs, modal


def test_mass_normalized_identity(support):
    """Mq = Uᵀ M U = I to machine precision (mass-normalized eigenvectors)."""
    rs, _ = support
    r = rs.Mq.shape[0]
    assert np.allclose(rs.Mq, np.eye(r), atol=1e-8)


def test_stiffness_is_omega_squared(support):
    """Kq = diag(ω²): diagonal, off-diagonals ~0, diag == modal_omega²."""
    rs, modal = support
    d = np.diag(rs.Kq)
    off = rs.Kq - np.diag(d)
    assert np.max(np.abs(off)) < 1e-3 * max(1.0, np.max(np.abs(d)))
    assert np.allclose(d, rs.modal_omega ** 2, rtol=1e-6, atol=1e-6)
    assert np.allclose(d, modal.eigenvalues, rtol=1e-8)


def test_frequencies_match_modal_analysis(support):
    """The support's ω match ModalAnalysis; f₁ is a physical bending mode."""
    rs, modal = support
    assert np.allclose(rs.modal_omega, modal.frequencies, rtol=1e-10)
    f1_hz = modal.frequencies[0] / (2.0 * np.pi)
    assert 10.0 < f1_hz < 1000.0            # a real slab bending fundamental


def test_grid_matches_barycentric_eval(support):
    """U_points on the grid reproduces the FEM mode shape: evaluating at a grid
    node returns that node's stored Φ_y (the install path reads it this way)."""
    rs, _ = support
    xs = np.linspace(-L / 2, L / 2, NX)
    zs = np.linspace(-W / 2, W / 2, NZ)
    for (i, k) in [(5, 5), (10, 3), (15, 8)]:
        x, z = float(xs[i]), float(zs[k])
        got = evaluate_basis_at_point(rs, (x, z), length=L, width=W,
                                      n_grid_x=NX, n_grid_z=NZ)[1, :]
        stored = rs.U_points[i * NZ + k, 1, :]
        assert np.allclose(got, stored, atol=1e-10)


def test_probe_shapes_and_eigenbasis_flags(support):
    rs, _ = support
    r = rs.Mq.shape[0]
    assert rs.U_points.shape == (NX * NZ, 3, r)
    assert rs.probe_U.shape == (2, 3, r)
    assert rs.is_eigenbasis and np.allclose(rs.eigen_V, np.eye(r))
    # non-trivial vertical mode shape (the support actually deflects).
    assert np.max(np.abs(rs.U_points[:, 1, :])) > 1e-3


@pytest.mark.parametrize("solver", ["xpbd", "avbd"])
def test_installs_into_native_scene(solver):
    """The FEM-modal support drives a full native step in both solvers with a
    finite modal state — end-to-end wiring parity with the synthetic support."""
    from benchmarks.paper_eval.x3_ground_truth.scene_and_gt import (
        build_fem_modal_scene,
    )
    H = build_fem_modal_scene(solver=solver, num_modes=8, iterations=8,
                              avbd_substeps=2)
    sol = H.world._solver
    sol._modal_symplectic = True
    for _ in range(20):
        H.world.step()
    q = getattr(sol, "modal_q", None)
    if q is None:
        q = sol._q
    q = np.asarray(q)
    assert q.shape[0] == 8
    assert np.all(np.isfinite(q))
    assert np.isfinite(float(getattr(sol, "last_modal_KE", 0.0)))
