#!/usr/bin/env python3
"""X3 — build a native modal support from TRUE FEM eigenmodes.

ISOLATED benchmark code (imports `dcr` READ-ONLY; adds nothing to the library
default path). The paper-eval scenes normally install a SYNTHETIC analytic
basis (`dcr/avbd/reduced_support.py:make_synthetic_modal_basis_for_shelf` —
sine bending modes + Gaussian contact bumps). That basis's spatial falloff is
partly bump-PLACEMENT-shaped, so it cannot by itself prove the native
constraint's distant response is PHYSICAL. Stage X3 rebuilds the same
`ReducedSupport` container from the true FEM eigenmodes of the slab
(`dcr/modal/modal_analysis.ModalAnalysis`, paper Eq. 6 `Kψ = ω²Mψ`), so the
native arm is literally a MODAL REDUCTION of the very FEM operator the
`CoupledFEMRigidSim` ground truth integrates. Compared head-to-head, the only
differences are (a) modal truncation to k modes and (b) the host contact model
— exactly the two things X3 measures.

Key facts used (verified against the source):
  * `ModalAnalysis` mass-normalizes its eigenvectors, so `M_q = Uᵀ M U = I`,
    `K_q = Uᵀ K U = diag(ω²)`, `D_q = Uᵀ D U = diag(α₀ + α₁ω²)` (Rayleigh) —
    all diagonal, which is exactly what the native q-block wants (XPBD reads
    only the diagonals; AVBD keeps the dense matrices, here ≈ diagonal).
  * The contact model reads the LIVE surface height `y_rest + U_y·q` at each
    corner, using ONLY the vertical (y) component of the mode shape. So the
    support's `U_points[k, 1, :]` must be Φ_y sampled on the SAME
    `n_grid_x × n_grid_z` grid that `evaluate_basis_at_point` interpolates on
    (index `i*n_grid_z + k`), and the value at an arbitrary contact (x,z) is
    the bilinear interpolation of that grid.
  * Both arms share ONE `FEMModel` (same mesh, same corner-fixed BCs), so the
    modes are consistent with the GT operator to machine precision.

DEVIATION (CLAUDE.md rule 3): the native support carries NO slab self-weight
sag (no `f_q_grav`) — it is a zero-rest support, matching the synthetic path
(`world.py:434` passes only q0/qdot0). The GT full-FEM slab DOES sag under its
own weight; that is a constant static offset removed by baselining both arms to
their settled rest before comparing dynamic response. Cited where consumed.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dcr.fem.fem_model import FEMModel
from dcr.modal.modal_analysis import ModalAnalysis
from dcr.modal.passive_inject import eval_basis_at_point
from dcr.avbd.reduced_support import ReducedSupport


def fix_corners(mesh) -> NDArray[np.int32]:
    """Corner nodes (x-min/max AND z-min/max), all DOFs — IDENTICAL BCs to the
    Stage-7 ground truth (`scripts/run_stage7.py:_fix_corners`), so the modes
    extracted here match the slab the `CoupledFEMRigidSim` integrates."""
    v = mesh.vertices
    tol = 1e-8
    xmin, xmax = v[:, 0].min(), v[:, 0].max()
    zmin, zmax = v[:, 2].min(), v[:, 2].max()
    mask = (((np.abs(v[:, 0] - xmin) < tol) | (np.abs(v[:, 0] - xmax) < tol)) &
            ((np.abs(v[:, 2] - zmin) < tol) | (np.abs(v[:, 2] - zmax) < tol)))
    return np.where(mask)[0].astype(np.int32)


def make_fem_modal_support(
    fem: FEMModel,
    *,
    num_modes: int,
    y_rest: float,
    n_grid_x: int,
    n_grid_z: int,
    probe_xz: list[tuple[float, float]] | None = None,
    length: float | None = None,
    width: float | None = None,
) -> tuple[ReducedSupport, ModalAnalysis]:
    """Build a `ReducedSupport` whose basis IS the true FEM eigenmodes of `fem`.

    Returns `(rs, modal)` where `rs` is installable by
    `world.enable_reduced_modal_support(rs, ..., n_grid_x, n_grid_z)` exactly
    like the synthetic support, and `modal` is the `ModalAnalysis` (kept so the
    caller can read ω, the full mode shapes, and validate f₁).

    The reduced matrices come straight from `ModalAnalysis` (paper Eq. 7):
        Mq = Uᵀ M U ≈ I,  Kq = Uᵀ K U ≈ diag(ω²),  Dq = Uᵀ D U (Rayleigh).
    The grid displacement `U_points[:,1,:] = Φ_y(grid)` is sampled from the
    surface-restricted mode basis by barycentric interpolation
    (`eval_basis_at_point`, foundation §4).
    """
    modal = ModalAnalysis(fem=fem, num_modes=int(num_modes))
    r = int(modal.num_modes)

    mesh = fem.mesh
    V = mesh.vertices
    xmin, xmax = float(V[:, 0].min()), float(V[:, 0].max())
    zmin, zmax = float(V[:, 2].min()), float(V[:, 2].max())
    mesh_top_y = float(V[:, 1].max())          # top surface (slab is Y-thin)
    L = float(length) if length is not None else (xmax - xmin)
    W = float(width) if width is not None else (zmax - zmin)

    # Barycentric surface eval scaffolding (same pattern as ModalDCRCoupler).
    surface = mesh.extract_surface()
    vert_to_surf = np.full(mesh.num_vertices, -1, dtype=np.int32)
    for si, vi in enumerate(modal.surface_vertex_indices):
        vert_to_surf[int(vi)] = si

    def phi_y_at(x: float, z: float) -> NDArray[np.float64]:
        """Φ(x,z) at the top surface → (3, r). Only the y-row is used by the
        contact, but we keep all 3 components for completeness/diagnostics."""
        p = np.array([x, mesh_top_y, z], dtype=np.float64)
        return eval_basis_at_point(
            p, surface, modal.U_surf, modal.surface_vertex_indices, vert_to_surf)

    # --- Sample Φ on the SAME grid evaluate_basis_at_point interpolates on. ---
    # index(i, k) = i*n_grid_z + k, x = xmin + i*L/(nx-1), z = zmin + k*W/(nz-1).
    xs = np.linspace(xmin, xmax, n_grid_x)
    zs = np.linspace(zmin, zmax, n_grid_z)
    n_pts = n_grid_x * n_grid_z
    pos = np.zeros((n_pts, 3), dtype=np.float64)
    normals = np.zeros((n_pts, 3), dtype=np.float64)
    normals[:, 1] = 1.0
    U_points = np.zeros((n_pts, 3, r), dtype=np.float64)
    for i, x in enumerate(xs):
        for k, z in enumerate(zs):
            idx = i * n_grid_z + k
            pos[idx] = (x, y_rest, z)
            U_points[idx] = phi_y_at(float(x), float(z))

    # --- Reduced matrices (Eq. 7). Mass-normalized ⇒ diagonal. ---
    Mq = np.asarray(modal.M_q, dtype=np.float64)
    Kq = np.asarray(modal.K_q, dtype=np.float64)
    Dq = np.asarray(modal.D_q, dtype=np.float64)
    omega = np.sqrt(np.maximum(np.asarray(modal.eigenvalues, np.float64), 0.0))
    zeta = np.diag(Dq) / (2.0 * np.maximum(omega, 1e-12))

    # --- Probe points (distant-response observation), same barycentric eval. ---
    probe_xz = probe_xz or []
    probe_points = np.zeros((len(probe_xz), 3), dtype=np.float64)
    probe_normals = np.zeros((len(probe_xz), 3), dtype=np.float64)
    probe_normals[:, 1] = 1.0
    probe_U = np.zeros((len(probe_xz), 3, r), dtype=np.float64)
    for i, (xp, zp) in enumerate(probe_xz):
        probe_points[i] = (xp, y_rest, zp)
        probe_U[i] = phi_y_at(float(xp), float(zp))

    rs = ReducedSupport(
        point_positions_rest=pos,
        point_normals_rest=normals,
        U_points=U_points,
        Mq=Mq, Kq=Kq, Dq=Dq,
        q=np.zeros(r), qdot=np.zeros(r),
        q_prev_macro=np.zeros(r), q_hat=np.zeros(r),
        r_modal=r, modal_omega=omega, modal_zeta=zeta,
        probe_points=probe_points, probe_normals=probe_normals, probe_U=probe_U,
        probe_body_indices=[],
        is_eigenbasis=True,
        eigen_V=np.eye(r), eigen_omegas=omega, eigen_zetas=zeta,
        overlay_enabled=False, restart_overlay_each_step=False,
    )
    return rs, modal


if __name__ == "__main__":
    # Self-test: FEM-modal support of a wood slab (matches run_comparison's GT
    # material). f₁ from the support == ModalAnalysis f₁, and both land near the
    # simply-supported Euler-Bernoulli estimate (order-of-magnitude; corner-fix
    # ≠ SS BCs, so exact agreement is not expected — this just sanity-checks the
    # basis is a real bending spectrum, not noise).
    import sys, os
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from dcr.geom.tet_mesh import make_slab_tet_mesh
    from dcr.fem.material import Material

    L, W, t = 1.0, 0.6, 0.05
    E, nu, rho = 1.1e9, 0.3, 770.0
    mesh = make_slab_tet_mesh(length=L, width=W, height=t, nx=10, ny=6, nz=2)
    fem = FEMModel(mesh=mesh, material=Material(E=E, nu=nu, rho=rho),
                   fixed_nodes=fix_corners(mesh), alpha0=2.0, alpha1=1e-5)
    rs, modal = make_fem_modal_support(
        fem, num_modes=12, y_rest=t / 2.0, n_grid_x=21, n_grid_z=11,
        probe_xz=[(-0.3, 0.0), (0.3, 0.0)])
    f_hz = modal.frequencies / (2.0 * np.pi)
    print(f"slab {L}x{W}x{t} m, E={E:.2e} nu={nu} rho={rho}  ({mesh.num_vertices} nodes)")
    print("first 12 FEM modal f [Hz]:", np.round(f_hz, 2))
    print("Mq diag (≈1):", np.round(np.diag(rs.Mq)[:4], 6))
    print("Kq diag / omega^2 (≈1):",
          np.round(np.diag(rs.Kq)[:4] / np.maximum(rs.modal_omega[:4] ** 2, 1e-9), 6))
    print("U_points shape:", rs.U_points.shape, " probe_U shape:", rs.probe_U.shape)
    print("max |Phi_y| on grid:", float(np.max(np.abs(rs.U_points[:, 1, :]))))
