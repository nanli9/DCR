"""Stage 3 acceptance tests — Modal analysis.

Criteria from dcr_implementation_prompt.md §3.7:
1. Eigenfrequencies of a fixed-bottom slab match paper Fig. 2 (same order of magnitude).
2. Visualize first 4 modes (tested by generating displacement fields).
3. M_q ≈ I to 1e-8 (mass-normalization check).
"""
import numpy as np

from dcr.geom import make_slab_tet_mesh
from dcr.fem import Material, FEMModel
from dcr.modal import ModalAnalysis


def _make_paper_table_model(nx: int = 10, ny: int = 6, nz: int = 2) -> FEMModel:
    """Build a slab matching the paper's table: E=1.1 GPa, ν=0.3, ρ=770 kg/m³.

    The table is supported at four corner columns (all Y-layers at each XZ
    corner), simulating table legs pinned at the four corners.
    """
    length, width, height = 1.0, 0.6, 0.05
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=nx, ny=ny, nz=nz)
    mat = Material(E=1.1e9, nu=0.3, rho=770.0)

    # Fix corner columns (all Y-layers at the four XZ corners).
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
    assert fixed.size > 0, "No corner nodes found"

    return FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed)


# ---------------------------------------------------------------------------
# Test 1: Eigenfrequencies within order of magnitude of paper Fig. 2
# ---------------------------------------------------------------------------
def test_eigenfrequencies_order_of_magnitude():
    """Paper Fig. 2 reports ω ≈ 393, 512, 677, 758 rad/s for the first 4 modes.

    We allow same order of magnitude since eigenfrequencies are mesh-dependent.
    """
    model = _make_paper_table_model(nx=12, ny=8, nz=2)
    ma = ModalAnalysis(fem=model, num_modes=10)

    paper_freqs = np.array([393.0, 512.0, 677.0, 758.0])
    computed = ma.frequencies[:4]

    print(f"  Paper ω:    {paper_freqs}")
    print(f"  Computed ω: {computed}")

    # Same order of magnitude: ratio between 0.1 and 10.
    for i in range(4):
        ratio = computed[i] / paper_freqs[i]
        print(f"    Mode {i}: ratio = {ratio:.3f}")
        assert 0.1 < ratio < 10.0, (
            f"Mode {i}: ω={computed[i]:.1f} vs paper {paper_freqs[i]:.1f}, "
            f"ratio {ratio:.3f} out of [0.1, 10] range"
        )


# ---------------------------------------------------------------------------
# Test 2: Mode displacement fields are non-trivial
# ---------------------------------------------------------------------------
def test_mode_displacements_nontrivial():
    """Each of the first 4 mode shapes should have non-zero displacement."""
    model = _make_paper_table_model()
    ma = ModalAnalysis(fem=model, num_modes=10)

    for i in range(4):
        u = ma.mode_displacement(i)
        mag = np.sqrt(u[0::3]**2 + u[1::3]**2 + u[2::3]**2)
        max_mag = mag.max()
        print(f"  Mode {i}: max displacement magnitude = {max_mag:.6e}")
        assert max_mag > 1e-12, f"Mode {i} displacement is essentially zero"


# ---------------------------------------------------------------------------
# Test 3: Mass-normalization — M_q ≈ I
# ---------------------------------------------------------------------------
def test_mass_normalization():
    """M_q = U^T M U should be identity (to 1e-8) for mass-normalized eigenvectors."""
    model = _make_paper_table_model()
    ma = ModalAnalysis(fem=model, num_modes=10)

    I = np.eye(ma.num_modes)
    err = np.max(np.abs(ma.M_q - I))
    print(f"  max |M_q - I| = {err:.2e}")
    assert err < 1e-8, f"M_q not identity: max deviation {err:.2e}"


# ---------------------------------------------------------------------------
# Test 4: K_q ≈ diag(ω_i²) for mass-normalized modes
# ---------------------------------------------------------------------------
def test_stiffness_diagonal():
    """K_q should be approximately diag(ω_i²) for mass-normalized eigenvectors."""
    model = _make_paper_table_model()
    ma = ModalAnalysis(fem=model, num_modes=10)

    expected_diag = ma.eigenvalues
    actual_diag = np.diag(ma.K_q)

    # Off-diagonal should be near zero.
    off_diag = ma.K_q - np.diag(actual_diag)
    off_diag_err = np.max(np.abs(off_diag))
    print(f"  max off-diagonal |K_q| = {off_diag_err:.2e}")
    assert off_diag_err < 1e-4, f"K_q not diagonal: {off_diag_err:.2e}"

    # Diagonal should match eigenvalues.
    diag_err = np.max(np.abs(actual_diag - expected_diag) / (expected_diag + 1e-12))
    print(f"  max relative diagonal error = {diag_err:.2e}")
    assert diag_err < 1e-6, f"K_q diagonal mismatch: {diag_err:.2e}"


# ---------------------------------------------------------------------------
# Test 5: Surface reduction preserves shape
# ---------------------------------------------------------------------------
def test_surface_reduction():
    """U_surf should have shape (3 * n_surf_free, num_modes) and be non-empty."""
    model = _make_paper_table_model()
    ma = ModalAnalysis(fem=model, num_modes=10)

    n_surf = len(ma.surface_vertex_indices)
    print(f"  Surface vertices: {n_surf}")
    print(f"  U_surf shape: {ma.U_surf.shape}")

    assert n_surf > 0, "No surface vertices found"
    assert ma.U_surf.shape == (3 * n_surf, ma.num_modes)
    assert np.any(ma.U_surf != 0), "U_surf is all zeros"
