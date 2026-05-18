"""Stage 2 acceptance tests — Linear FEM sanity.

Criteria from dcr_implementation_prompt.md §2.5:
1. Cantilever beam tip deflection within 5% of Euler–Bernoulli analytical.
2. Mass matrix row sums equal total mass (to float precision).
3. Stiffness matrix symmetric and PSD; 6 near-zero rigid-body modes when
   no BCs applied.
"""
import numpy as np
import scipy.sparse.linalg as spla

from dcr.geom import make_beam_tet_mesh
from dcr.fem import Material, FEMModel, assemble_global_matrices


# ---------------------------------------------------------------------------
# Test 1: Cantilever beam tip deflection
# ---------------------------------------------------------------------------
def test_cantilever_tip_deflection():
    """Cantilever beam under uniform gravity; compare tip deflection to
    Euler–Bernoulli analytical solution  δ = w L^4 / (8 E I)  for a
    uniformly loaded cantilever.

    We use a slender beam so the E-B approximation is accurate.
    """
    L = 1.0       # beam length [m]
    W = 0.05      # beam width (Y) [m]
    H = 0.05      # beam height (Z) [m]
    E = 1.1e9     # Young's modulus [Pa]
    nu = 0.3
    rho = 600.0   # density [kg/m^3]

    # Linear tets need many elements to capture bending strain.
    # 5-tet alternating decomposition converges faster than Freudenthal.
    mesh = make_beam_tet_mesh(length=L, width=W, height=H, nx=110, ny=10, nz=10)
    mat = Material(E=E, nu=nu, rho=rho)

    # Fix the -X end: nodes with x ≈ -L/2.
    tol = 1e-8
    fixed = np.where(mesh.vertices[:, 0] < -L / 2 + tol)[0].astype(np.int32)
    assert fixed.size > 0, "No fixed nodes found"

    model = FEMModel(mesh=mesh, material=mat, fixed_nodes=fixed)
    f = model.gravity_load(g=-9.81)
    u = model.static_solve(f)

    # Tip nodes: x ≈ +L/2.
    tip_mask = mesh.vertices[:, 0] > L / 2 - tol
    # Tip deflection in Y (gravity direction).
    tip_y = u[1::3][tip_mask]
    tip_deflection = np.mean(tip_y)

    # Euler–Bernoulli analytical: δ = w L^4 / (8 E I)
    # w = distributed load per unit length = ρ * A * g
    A = W * H
    I = W * H**3 / 12.0  # second moment of area about the bending axis
    w = rho * A * 9.81    # load intensity [N/m], positive downward
    delta_analytical = w * L**4 / (8.0 * E * I)

    # FEM deflection is negative (downward); analytical formula gives magnitude.
    fem_mag = abs(tip_deflection)
    rel_err = abs(fem_mag - delta_analytical) / delta_analytical
    print(f"  Tip deflection: FEM={fem_mag:.6e}, analytical={delta_analytical:.6e}, "
          f"rel err={rel_err:.2%}")
    assert rel_err < 0.05, f"Tip deflection error {rel_err:.2%} exceeds 5%"


# ---------------------------------------------------------------------------
# Test 2: Mass matrix row sums
# ---------------------------------------------------------------------------
def test_mass_row_sums():
    """Row sums of the global lumped mass matrix must equal total mass.

    For lumped mass, each node gets mass contributions from its tets.
    Summing all diagonal entries and dividing by 3 (three identical DOFs
    per node) must equal ρ * total_volume.
    """
    mesh = make_beam_tet_mesh(length=1.0, width=0.1, height=0.1, nx=5, ny=2, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=600.0)
    M, K = assemble_global_matrices(mesh, mat)

    # Expected total mass.
    # Volume = L * W * H for a box mesh.
    expected_mass = mat.rho * 1.0 * 0.1 * 0.1

    diag_sum = M.diagonal().sum()
    # Each node has 3 identical diagonal entries, so total mass = diag_sum / 3.
    computed_mass = diag_sum / 3.0
    rel_err = abs(computed_mass - expected_mass) / expected_mass
    print(f"  Mass: computed={computed_mass:.6e}, expected={expected_mass:.6e}, "
          f"rel err={rel_err:.2e}")
    assert rel_err < 1e-12, f"Mass mismatch: {rel_err:.2e}"


# ---------------------------------------------------------------------------
# Test 3: Stiffness matrix symmetry and PSD; 6 near-zero rigid-body modes
# ---------------------------------------------------------------------------
def test_stiffness_symmetric_psd():
    """K must be symmetric and positive semi-definite.

    With no BCs, there are exactly 6 near-zero eigenvalues corresponding
    to rigid-body translation (3) and rotation (3).
    """
    mesh = make_beam_tet_mesh(length=0.5, width=0.1, height=0.1, nx=5, ny=2, nz=2)
    mat = Material(E=1.1e9, nu=0.3, rho=600.0)
    M, K = assemble_global_matrices(mesh, mat)

    # Symmetry check.
    diff = K - K.T
    sym_err = abs(diff).max()
    print(f"  Symmetry error: {sym_err:.2e}")
    assert sym_err < 1e-10, f"K not symmetric: max diff {sym_err:.2e}"

    # PSD check via smallest eigenvalues.
    # We ask for the 10 smallest eigenvalues.
    n_dofs = K.shape[0]
    k_eig = min(10, n_dofs - 2)
    # Use shift-invert near zero for smallest eigenvalues.
    eigenvalues = spla.eigsh(
        K, k=k_eig, M=M, sigma=0.0, which="LM", return_eigenvectors=False,
    )
    eigenvalues = np.sort(eigenvalues)
    print(f"  10 smallest eigenvalues: {eigenvalues}")

    # First 6 should be near zero (rigid-body modes).
    rb_eigs = eigenvalues[:6]
    assert np.all(rb_eigs < 1.0), (
        f"Expected 6 near-zero rigid-body modes, got {rb_eigs}"
    )

    # The 7th eigenvalue should be well above zero (first elastic mode).
    first_elastic = eigenvalues[6]
    print(f"  First elastic eigenvalue: {first_elastic:.4e}")
    assert first_elastic > 1.0, (
        f"7th eigenvalue too small: {first_elastic:.4e}"
    )
