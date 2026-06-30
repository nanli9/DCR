"""Full-FEM (3D solid) plate reference for the slab-material physics check.

ISOLATED benchmark code: imports the dcr FEM/mesh library READ-ONLY and modifies
nothing in the original tree (per the "benchmark stays in its own folder" rule).

Truth model
-----------
The shelf/ledge/dinner reduced-modal support is a SYNTHETIC analytic basis
(`dcr/avbd/reduced_support.py:make_synthetic_modal_basis_for_shelf`): sine
bending modes phi_n(x)=sin(n*pi*(x+L/2)/L) (simply-supported / pinned-pinned)
with Euler-Bernoulli frequencies

    omega_n = (n*pi/L)^2 * sqrt(D/mu),   D = E t^3/(12(1-nu^2)),  mu = rho t.

To check whether that analytic model is physically faithful we mesh the SAME
slab as a 3D tetrahedral SOLID, assemble linear-elastic K/M with the dcr FEM
code, impose simply-supported BCs (pin transverse y on the two x-end edges plus
a minimal in-plane anchor set), and solve the generalized eigenproblem for the
true natural frequencies. The ratio f_FEM / f_EB is the modeling error of the
thin-plate Euler-Bernoulli assumption the scenes rely on.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse.linalg import eigsh, spsolve

from dcr.geom.tet_mesh import make_slab_tet_mesh
from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material


def euler_bernoulli_ss_freqs(L, t, E, nu, rho, n=4):
    """Simply-supported Euler-Bernoulli plate-strip bending frequencies [Hz].

    This is EXACTLY the formula the synthetic shelf basis uses for its bending
    oscillators, so it is the analytic model under test."""
    D = E * t ** 3 / (12.0 * (1.0 - nu * nu))
    mu = rho * t
    ns = np.arange(1, n + 1)
    omega = (ns * np.pi / L) ** 2 * np.sqrt(D / mu)
    return omega / (2.0 * np.pi)


def fem_plate_ss(L, W, t, E, nu, rho, *, nx=64, ny=12, nz=5, n_modes=4):
    """3D solid-FEM simply-supported plate: natural frequencies [Hz] + static
    self-weight mid deflection [m]. Returns (freqs, delta_mid, n_vertices).

    Own per-DOF reduction (the dcr FEMModel only fixes whole nodes; simply-
    supported needs to pin the transverse y DOF alone), built from the
    unconstrained K_full/M_full it exposes. Default mesh (nz=5 through the
    thickness) is chosen at the converged end of the locking study in __main__
    — linear tets shear-lock and OVERestimate bending stiffness on coarse
    through-thickness meshes; nz>=5 brings f_1 within ~4% of Euler-Bernoulli."""
    mesh = make_slab_tet_mesh(length=L, width=W, height=t, nx=nx, ny=ny, nz=nz)
    fem = FEMModel(mesh=mesh, material=Material(E=E, nu=nu, rho=rho))
    K = fem.K_full.tocsc()
    M = fem.M_full.tocsc()
    V = mesh.vertices
    x, z = V[:, 0], V[:, 2]
    nverts = mesh.num_vertices
    tol = 1e-6 * L
    xmin, xmax = x.min(), x.max()
    end = np.where((np.abs(x - xmin) < tol) | (np.abs(x - xmax) < tol))[0]

    fixed = set(int(3 * n + 1) for n in end)        # pin y on both end edges (SS)
    emin = end[np.abs(x[end] - xmin) < tol]          # one end edge
    a = int(emin[np.argmin(z[emin])])                # min-z node on that edge
    b = int(emin[np.argmax(z[emin])])                # max-z node on that edge
    fixed |= {3 * a + 0, 3 * a + 2, 3 * b + 0}       # kill x-/z-trans + y-rotation
    fixed_arr = np.array(sorted(fixed), dtype=np.int64)
    free = np.setdiff1d(np.arange(3 * nverts), fixed_arr)

    Kf = K[free][:, free].tocsc()
    Mf = M[free][:, free].tocsc()
    w2 = eigsh(Kf, k=n_modes, M=Mf, sigma=0.0, which="LM",
               return_eigenvectors=False)
    w2 = np.sort(np.maximum(w2, 0.0))
    freqs = np.sqrt(w2) / (2.0 * np.pi)

    # static self-weight deflection (most negative y near mid-span x~0).
    g = 9.81
    f_full = np.zeros(3 * nverts)
    f_full[1::3] = -g * M.diagonal()[1::3]
    uf = spsolve(Kf, f_full[free])
    u = np.zeros(3 * nverts)
    u[free] = uf
    mid = np.where(np.abs(x) < 0.1 * L)[0]
    delta_mid = float(np.min(u[1::3][mid])) if mid.size else float(np.min(u[1::3]))
    return freqs[:n_modes], delta_mid, nverts


def euler_bernoulli_ss_selfweight_deflection(L, t, E, nu, rho, g=9.81):
    """Analytic SS uniform-load (self-weight) mid deflection [m]:
    delta = 5 (mu g) L^4 / (384 D), per-unit-width strip (D, mu as above)."""
    D = E * t ** 3 / (12.0 * (1.0 - nu * nu))
    mu = rho * t
    return -5.0 * (mu * g) * L ** 4 / (384.0 * D)


def _convergence(L, W, t, E, nu, rho):
    f1_eb = euler_bernoulli_ss_freqs(L, t, E, nu, rho, n=1)[0]
    print(f"  EB f_1 = {f1_eb:.2f} Hz   (linear-tet shear-locking study)")
    for nx, ny, nz in [(24, 8, 2), (32, 8, 3), (48, 10, 4), (64, 12, 5)]:
        fr, _, nv = fem_plate_ss(L, W, t, E, nu, rho, nx=nx, ny=ny, nz=nz, n_modes=1)
        print(f"    nz={nz} ({nv:5d} nodes): f_1={fr[0]:7.2f} Hz  "
              f"f_FEM/f_EB={fr[0] / f1_eb:.3f}")


if __name__ == "__main__":
    # Self-test: steel shelf slab. Analytic f_1 ~112 Hz; the 3D FEM simply-
    # supported plate converges to it as the through-thickness mesh refines.
    L, W, t = 0.8, 0.3, 0.03
    E, nu, rho = 2.0e11, 0.30, 7850.0
    print(f"steel slab {L}x{W}x{t} m")
    _convergence(L, W, t, E, nu, rho)
    fb = euler_bernoulli_ss_freqs(L, t, E, nu, rho, n=4)
    ff, dmid, nv = fem_plate_ss(L, W, t, E, nu, rho)
    d_eb = euler_bernoulli_ss_selfweight_deflection(L, t, E, nu, rho)
    print(f"  converged ({nv} nodes):")
    print("    Euler-Bernoulli SS f[Hz]:", np.round(fb, 1))
    print("    3D-FEM SS         f[Hz]:", np.round(ff, 1),
          "(higher modes mix torsion/width — absent from the 1D strip)")
    print(f"    self-weight mid deflection [mm]: FEM {dmid * 1e3:.4f}  "
          f"EB {d_eb * 1e3:.4f}  ratio {dmid / d_eb:.2f}")
