"""Reduced bodies for the two-way coupling demonstrator.

Two reduced models share one duck-typed interface so the coupled step
(`coupled_step.py`) is generic over them. Every body owns generalized
coordinates `z`, a constant generalized mass `M`, a constant Rayleigh damping
`D`, an internal elastic potential `V_b(z)` (value/grad/Hess), a constant
generalized gravity force, and a tracked-contact-point map `point_world(z, pid)`
with a constant Jacobian `point_jac(pid)`.

Models:
  * `ABDAffineBody`  — affine body dynamics (Lan et al. 2022, `docs/ABD.pdf`),
    z = q = (p, a1, a2, a3) ∈ R^12, world map x = A x̄ + p (Eq. 1), mass M from
    Eq. 4, internal potential the stiff orthogonality potential V⊥ (Eq. 6–8).
  * `FEMModalBody`   — FEM eigen-reduced body. For the SLAB: pure modal coords
    q ∈ R^r of a supported plate. For the CUBE: a translation carrier p ∈ R^3
    plus k elastic eigenmodes a ∈ R^k (rigid modes projected out).

# DEVIATION (impl, ABD Eq. 9): the FEM cube uses a non-rotating translation
# carrier + elastic modes rather than co-rotating a floating frame. Rigid
# rotation is dropped (flat axis-aligned drop). This makes the ABD-vs-FEM
# comparison differ ONLY in the deformation basis (affine strain vs modal
# shapes), which is the intended apples-to-apples comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import eigh

from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.geom.tet_mesh import TetMesh, make_block_tet_mesh, make_slab_tet_mesh
from dcr.modal.modal_analysis import ModalAnalysis

_GRAVITY = 9.81  # m/s^2, acting in -Y


# ======================================================================
# ABD affine body (Lan et al. 2022, docs/ABD.pdf)
# ======================================================================
@dataclass
class ABDAffineBody:
    """12-DOF affine body. z = q = [p(3), a1(3), a2(3), a3(3)].

    World map (Eq. 1): x_k = A x̄_k + p, with A = [a1; a2; a3]^T (rows a_i),
    so x_k[i] = a_i · x̄_k + p[i]. The point Jacobian J(x̄) (3x12) is constant
    (orientation-independent — the ABD advantage).
    """

    rest_nodes: NDArray[np.float64]      # (N, 3) body-frame node coords (centroid-relative)
    node_mass: NDArray[np.float64]       # (N,) lumped nodal masses
    kappa_v: float                       # κ·v orthogonality stiffness (Eq. 7)
    corner_rest: NDArray[np.float64]     # (4, 3) body-frame contact-corner coords
    centroid_world0: NDArray[np.float64] # initial world centroid (sets initial p)

    ndof: int = field(init=False, default=12)
    M: NDArray[np.float64] = field(init=False, repr=False)
    D: NDArray[np.float64] = field(init=False, repr=False)
    f_grav: NDArray[np.float64] = field(init=False, repr=False)
    _corner_J: NDArray[np.float64] = field(init=False, repr=False)  # (4, 3, 12)

    def __post_init__(self) -> None:
        N = self.rest_nodes.shape[0]
        # Mass matrix M = Σ_n m_n J(x̄_n)^T J(x̄_n)  (ABD Eq. 4).
        M = np.zeros((12, 12))
        f_grav = np.zeros(12)
        for n in range(N):
            J = self._point_jac_bodyframe(self.rest_nodes[n])
            M += self.node_mass[n] * (J.T @ J)
            # Gravity generalized force = Σ J^T (0, -m g, 0).
            f_grav += J.T @ np.array([0.0, -self.node_mass[n] * _GRAVITY, 0.0])
        self.M = M
        self.f_grav = f_grav
        # ABD has no intrinsic material damping in V⊥; add a light mass-Rayleigh
        # term so the rigid-ish modes ring down (the slab carries the real
        # elastic damping). alpha0 set by the caller via set_damping().
        self.D = np.zeros((12, 12))
        # Precompute constant contact-corner Jacobians.
        self._corner_J = np.stack(
            [self._point_jac_bodyframe(c) for c in self.corner_rest]
        )

    # -- coordinates --------------------------------------------------
    def rest_state(self) -> NDArray[np.float64]:
        """q with A = I and p = initial world centroid."""
        q = np.zeros(12)
        q[0:3] = self.centroid_world0
        q[3:6] = (1.0, 0.0, 0.0)  # a1
        q[6:9] = (0.0, 1.0, 0.0)  # a2
        q[9:12] = (0.0, 0.0, 1.0)  # a3
        return q

    @staticmethod
    def _point_jac_bodyframe(xbar: NDArray[np.float64]) -> NDArray[np.float64]:
        """J(x̄) (3x12) with x = J q, q = [p, a1, a2, a3]."""
        J = np.zeros((3, 12))
        J[0, 0] = J[1, 1] = J[2, 2] = 1.0
        J[0, 3:6] = xbar
        J[1, 6:9] = xbar
        J[2, 9:12] = xbar
        return J

    def point_world(self, q: NDArray[np.float64], pid: int) -> NDArray[np.float64]:
        return self._corner_J[pid] @ q

    def point_jac(self, pid: int) -> NDArray[np.float64]:
        return self._corner_J[pid]

    def n_corners(self) -> int:
        return self.corner_rest.shape[0]

    def set_damping(self, alpha0: float) -> None:
        """Mass-proportional Rayleigh damping D = alpha0 * M."""
        self.D = alpha0 * self.M

    # -- internal orthogonality potential V⊥ (Eq. 6–8) ----------------
    def _A_rows(self, q: NDArray[np.float64]):
        return q[3:6], q[6:9], q[9:12]

    def internal_energy(self, q: NDArray[np.float64]) -> float:
        a = self._A_rows(q)
        e = 0.0
        for i in range(3):
            e += (a[i] @ a[i] - 1.0) ** 2
            for j in range(3):
                if j != i:
                    e += (a[i] @ a[j]) ** 2
        return self.kappa_v * e

    def internal_grad(self, q: NDArray[np.float64]) -> NDArray[np.float64]:
        a = self._A_rows(q)
        g = np.zeros(12)
        for i in range(3):
            gi = 4.0 * self.kappa_v * (a[i] @ a[i] - 1.0) * a[i]
            for j in range(3):
                if j != i:
                    gi += 4.0 * self.kappa_v * (a[i] @ a[j]) * a[j]
            g[3 + 3 * i: 6 + 3 * i] = gi
        return g

    def internal_hess(self, q: NDArray[np.float64]) -> NDArray[np.float64]:
        a = self._A_rows(q)
        H = np.zeros((12, 12))
        for i in range(3):
            # diagonal block ii (ABD Eq. 8)
            Hii = (8.0 * self.kappa_v * np.outer(a[i], a[i])
                   + 4.0 * self.kappa_v * (a[i] @ a[i] - 1.0) * np.eye(3))
            for j in range(3):
                if j != i:
                    Hii += 4.0 * self.kappa_v * np.outer(a[j], a[j])
            bi = 3 + 3 * i
            H[bi:bi + 3, bi:bi + 3] = Hii
            # off-diagonal block ij from the (a_i·a_j)^2 cross term
            for j in range(3):
                if j != i:
                    Hij = 4.0 * self.kappa_v * (np.outer(a[j], a[i])
                                                + (a[i] @ a[j]) * np.eye(3))
                    bj = 3 + 3 * j
                    H[bi:bi + 3, bj:bj + 3] = Hij
        return H

    # -- elastic constraints for XPBD (compliant-constraint form) -----
    def elastic_constraints(self, q: NDArray[np.float64]):
        """V⊥ as XPBD compliant constraints (Macklin 2016 §3, ABD Eq. 6–7).

        V⊥ = κ_v Σ_i[(‖a_i‖²−1)² + Σ_{j≠i}(a_i·a_j)²] is a sum of squared
        scalar constraints C with energy ½ k C². Six constraints: 3 diagonal
        C_ii = ‖a_i‖²−1 (each appears ONCE ⇒ k = 2κ_v) and 3 off-diagonal
        C_ij = a_i·a_j (i<j; each appears TWICE in the j≠i double sum ⇒
        k = 4κ_v). Returns ``(C, grad(ndof,), compliance, damp_coeff)`` tuples.

        # DEVIATION (ABD Eq. 8): the affine internal is genuinely nonlinear,
        # so each XPBD projection re-linearizes ∇C at the current q — exactly
        # the standard PBD treatment of a nonlinear constraint.
        """
        a = (q[3:6], q[6:9], q[9:12])
        alpha_diag = 1.0 / (2.0 * self.kappa_v)   # diagonal term once
        alpha_off = 1.0 / (4.0 * self.kappa_v)    # off-diagonal counted twice
        # mass-proportional Rayleigh damping D = α0 M ⇒ per-constraint damp
        # coefficient handled at the velocity level (see XPBDDynamicSystem);
        # report 0 here and let the solver apply the body-level D.
        out = []
        for i in range(3):
            g = np.zeros(12)
            g[3 + 3 * i:6 + 3 * i] = 2.0 * a[i]
            out.append((float(a[i] @ a[i] - 1.0), g, alpha_diag, 0.0))
        for i in range(3):
            for j in range(i + 1, 3):
                g = np.zeros(12)
                g[3 + 3 * i:6 + 3 * i] = a[j]
                g[3 + 3 * j:6 + 3 * j] = a[i]
                out.append((float(a[i] @ a[j]), g, alpha_off, 0.0))
        return out

    # -- skinning for the viewer --------------------------------------
    def deformed_nodes(self, q: NDArray[np.float64],
                       exaggerate: float = 1.0) -> NDArray[np.float64]:
        """All mesh nodes mapped to world (N, 3).

        `exaggerate` scales only the *deformation* (A − I)x̄, leaving the rigid
        translation p untouched, so the display amplifies squish without moving
        the body off the slab.
        """
        p = q[0:3]
        A = np.stack([q[3:6], q[6:9], q[9:12]])  # rows a_i
        defo = self.rest_nodes @ (A - np.eye(3)).T
        return self.rest_nodes + exaggerate * defo + p


# ======================================================================
# FEM modal body  (slab: pure modal; cube: translation carrier + elastic modes)
# ======================================================================
@dataclass
class FEMModalBody:
    """Generalized coords z = [carrier(nc), modal(k)].

    For the SLAB: nc = 0, modal coords q ∈ R^r (supported-plate eigenmodes).
    For the CUBE: nc = 3 translation, modal a ∈ R^k elastic eigenmodes.
    """

    nc: int                                  # carrier (translation) DOFs: 0 or 3
    omega2: NDArray[np.float64]              # (k,) modal stiffness eigenvalues ω²
    carrier_mass: float                      # total mass for translation carrier (cube)
    f_grav: NDArray[np.float64]              # (nc+k,) generalized gravity force
    corner_rest: NDArray[np.float64]        # (P, 3) rest world positions of tracked points
    corner_modal: NDArray[np.float64]       # (P, 3, k) modal surface rows at tracked points
    D_modal: NDArray[np.float64]            # (k, k) modal Rayleigh damping
    # viewer skinning data
    surf_rest: NDArray[np.float64]          # (Ns, 3) rest surface vertex positions
    surf_modal: NDArray[np.float64]         # (Ns, 3, k) modal surface rows
    surf_faces: NDArray[np.int32]           # (F, 3) surface triangle indices into surf_rest

    ndof: int = field(init=False)
    M: NDArray[np.float64] = field(init=False, repr=False)
    D: NDArray[np.float64] = field(init=False, repr=False)
    K_modal: NDArray[np.float64] = field(init=False, repr=False)
    _corner_J: NDArray[np.float64] = field(init=False, repr=False)  # (P, 3, ndof)

    def __post_init__(self) -> None:
        k = self.omega2.shape[0]
        self.ndof = self.nc + k
        # mass: block diag(carrier_mass*I3, I_k)  (modes mass-normalized)
        M = np.eye(self.ndof)
        if self.nc == 3:
            M[0:3, 0:3] = self.carrier_mass * np.eye(3)
        self.M = M
        self.K_modal = np.diag(self.omega2)
        D = np.zeros((self.ndof, self.ndof))
        D[self.nc:, self.nc:] = self.D_modal
        self.D = D
        # constant point Jacobians: [I3(carrier) | modal rows]
        P = self.corner_rest.shape[0]
        Jc = np.zeros((P, 3, self.ndof))
        if self.nc == 3:
            Jc[:, 0, 0] = Jc[:, 1, 1] = Jc[:, 2, 2] = 1.0
        Jc[:, :, self.nc:] = self.corner_modal
        self._corner_J = Jc

    def rest_state(self) -> NDArray[np.float64]:
        return np.zeros(self.ndof)

    def point_world(self, z: NDArray[np.float64], pid: int) -> NDArray[np.float64]:
        return self.corner_rest[pid] + self._corner_J[pid] @ z

    def point_jac(self, pid: int) -> NDArray[np.float64]:
        return self._corner_J[pid]

    def n_corners(self) -> int:
        return self.corner_rest.shape[0]

    def internal_energy(self, z: NDArray[np.float64]) -> float:
        a = z[self.nc:]
        return 0.5 * float(a @ (self.omega2 * a))

    def internal_grad(self, z: NDArray[np.float64]) -> NDArray[np.float64]:
        g = np.zeros(self.ndof)
        g[self.nc:] = self.omega2 * z[self.nc:]
        return g

    def internal_hess(self, z: NDArray[np.float64]) -> NDArray[np.float64]:
        H = np.zeros((self.ndof, self.ndof))
        H[self.nc:, self.nc:] = self.K_modal
        return H

    def elastic_constraints(self, z: NDArray[np.float64]):
        """Modal stiffness as XPBD compliant constraints (Macklin 2016 §3).

        ½ qᵀK_q q = Σ_i ½ ω²_i a_i² is a sum of 1-DOF linear constraints
        C_i = a_i (the i-th modal amplitude) with stiffness ω²_i ⇒ compliance
        α_i = 1/ω²_i. The carrier translation (dofs 0..nc) is free (no elastic
        constraint — inertia + gravity only). Returns
        ``(C, grad(ndof,), compliance, damp_coeff)`` per mode, with the modal
        Rayleigh damping D_modal[i,i] as the per-constraint damp coefficient.
        """
        out = []
        for i in range(self.omega2.shape[0]):
            dof = self.nc + i
            g = np.zeros(self.ndof)
            g[dof] = 1.0
            alpha = 1.0 / float(self.omega2[i]) if self.omega2[i] > 0.0 else 0.0
            out.append((float(z[dof]), g, alpha, float(self.D_modal[i, i])))
        return out

    def deformed_surface(self, z: NDArray[np.float64],
                         exaggerate: float = 1.0) -> NDArray[np.float64]:
        """World surface vertices (Ns, 3) for the viewer.

        `exaggerate` scales only the modal deformation, not the rigid carrier.
        """
        a = z[self.nc:]
        out = self.surf_rest + exaggerate * (self.surf_modal @ a)
        if self.nc == 3:
            out = out + z[0:3]
        return out


# ======================================================================
# Builders
# ======================================================================
def _surface_blocks(modal: ModalAnalysis):
    """Return (surf_vertex_ids, surf_rest, surf_modal (Ns,3,m)) for a body."""
    sv = modal.surface_vertex_indices
    rest = modal.fem.mesh.vertices[sv]
    m = modal.U.shape[1]
    # U_surf is (3*Ns, m) row-ordered [x0,y0,z0, x1,y1,z1, ...]
    surf_modal = modal.U_surf.reshape(len(sv), 3, m)
    return sv, rest, surf_modal


def _modal_gravity(fem: FEMModel, U: NDArray[np.float64]) -> NDArray[np.float64]:
    """Generalized modal gravity force U^T f_grav_free (paper Eq. 7 projection)."""
    return U.T @ fem.gravity_load(g=-_GRAVITY)


def build_fem_slab(
    material: Material | None = None,
    num_modes: int = 16,
    alpha0: float = 2.0,
    alpha1: float = 1.0e-4,
    length: float = 1.0,
    width: float = 0.6,
    height: float = 0.05,
    nx: int = 12,
    ny: int = 8,
    cube_corners_xz: NDArray[np.float64] | None = None,
) -> FEMModalBody:
    """Supported slab (clamped at the two short ends) as a FEM-modal body.

    Tracked contact points are the slab top-surface vertices nearest the cube's
    contact-corner (x, z) locations (passed in `cube_corners_xz`).
    """
    material = material or Material(E=3.0e9, nu=0.3, rho=600.0)  # wood-like
    mesh = make_slab_tet_mesh(length=length, width=width, height=height,
                              nx=nx, ny=ny, nz=1)
    # Clamp the two short ends (x ≈ ±length/2): a doubly-supported plate.
    xs = mesh.vertices[:, 0]
    edge = 0.5 * length - 1.0e-6
    fixed = np.where(np.abs(xs) >= edge)[0].astype(np.int32)
    fem = FEMModel(mesh=mesh, material=material, fixed_nodes=fixed,
                   alpha0=alpha0, alpha1=alpha1)
    modal = ModalAnalysis(fem=fem, num_modes=num_modes)

    sv, surf_rest, surf_modal = _surface_blocks(modal)
    # Top-surface vertices (max y).
    ytop = surf_rest[:, 1].max()
    top_mask = surf_rest[:, 1] >= ytop - 1.0e-4

    # Map each cube corner (x, z) to the nearest top-surface tracked vertex.
    if cube_corners_xz is None:
        cube_corners_xz = np.array([[0.05, 0.05], [0.05, -0.05],
                                    [-0.05, 0.05], [-0.05, -0.05]])
    top_ids = np.where(top_mask)[0]
    corner_ids = []
    for cx, cz in cube_corners_xz:
        d = ((surf_rest[top_ids, 0] - cx) ** 2
             + (surf_rest[top_ids, 2] - cz) ** 2)
        corner_ids.append(top_ids[int(np.argmin(d))])
    corner_ids = np.array(corner_ids, dtype=np.int32)

    f_grav = _modal_gravity(fem, modal.U)
    return FEMModalBody(
        nc=0,
        omega2=modal.eigenvalues.copy(),
        carrier_mass=0.0,
        f_grav=f_grav,
        corner_rest=surf_rest[corner_ids].copy(),
        corner_modal=surf_modal[corner_ids].copy(),
        D_modal=np.asarray(modal.D_q),
        surf_rest=surf_rest,
        surf_modal=surf_modal,
        surf_faces=_reindex_surface(modal),
    )


def _reindex_surface(modal: ModalAnalysis) -> NDArray[np.int32]:
    """Surface faces reindexed into the surface_vertex_indices ordering."""
    surface = modal.fem.mesh.extract_surface()
    sv = modal.surface_vertex_indices
    remap = np.full(modal.fem.mesh.num_vertices, -1, dtype=np.int64)
    remap[sv] = np.arange(len(sv))
    faces = remap[surface.faces]
    # keep only faces whose 3 verts are all tracked surface verts
    good = np.all(faces >= 0, axis=1)
    return faces[good].astype(np.int32)


def _cube_corner_ids(mesh: TetMesh, half: float):
    """Nearest mesh vertices to the 8 corners: bottom 4 (pids 0-3, y=-half)
    then top 4 (pids 4-7, y=+half), each pair sharing the same (x, z) so a
    stacked cube's bottom corner i pairs with the cube-below's top corner i+4."""
    xz = np.array([[half, half], [half, -half], [-half, half], [-half, -half]])
    bottom = np.column_stack([xz[:, 0], np.full(4, -half), xz[:, 1]])
    top = np.column_stack([xz[:, 0], np.full(4, half), xz[:, 1]])
    corners = np.vstack([bottom, top])
    ids = []
    for c in corners:
        d = np.sum((mesh.vertices - c) ** 2, axis=1)
        ids.append(int(np.argmin(d)))
    return np.array(ids, dtype=np.int32), corners


def build_abd_cube(
    size: float = 0.1,
    nx: int = 3,
    material: Material | None = None,
    kappa_v: float = 5.0e3,
    drop_y: float = 0.12,
    alpha0: float = 1.0,
    cx: float = 0.0,
    cz: float = 0.0,
) -> ABDAffineBody:
    """ABD affine cube of edge `size`, centroid at (cx, drop_y, cz)."""
    material = material or Material(E=1.0e9, nu=0.3, rho=600.0)
    mesh = make_block_tet_mesh(size=size, nx=nx, ny=nx, nz=nx)
    half = 0.5 * size
    # lumped nodal masses from the FEM mass diagonal (exact, reuses the mesh)
    fem = FEMModel(mesh=mesh, material=material)
    m_node = fem.M_full.diagonal()[0::3]  # x-diagonal == nodal mass (lumped)
    centroid = mesh.vertices.mean(axis=0)
    rest_nodes = mesh.vertices - centroid
    _, corners = _cube_corner_ids(mesh, half)
    corner_rest = corners - centroid
    body = ABDAffineBody(
        rest_nodes=rest_nodes,
        node_mass=m_node,
        kappa_v=kappa_v,
        corner_rest=corner_rest,
        centroid_world0=np.array([cx, drop_y, cz]),
    )
    body.set_damping(alpha0)
    # stash mesh surface for the viewer
    body.mesh = mesh                                    # type: ignore[attr-defined]
    body.surf_faces = mesh.extract_surface().faces      # type: ignore[attr-defined]
    return body


def build_fem_cube(
    size: float = 0.1,
    nx: int = 3,
    material: Material | None = None,
    n_elastic: int = 6,
    drop_y: float = 0.12,
    alpha0: float = 1.0,
    alpha1: float = 5.0e-4,
    cx: float = 0.0,
    cz: float = 0.0,
) -> FEMModalBody:
    """FEM-modal cube: translation carrier + `n_elastic` elastic eigenmodes."""
    material = material or Material(E=1.0e9, nu=0.3, rho=600.0)
    mesh = make_block_tet_mesh(size=size, nx=nx, ny=nx, nz=nx)
    half = 0.5 * size
    fem = FEMModel(mesh=mesh, material=material, alpha0=alpha0, alpha1=alpha1)
    # Free-body generalized eigenproblem (dense — cube is small). The first 6
    # modes are rigid (ω≈0); keep the next n_elastic elastic modes.
    K = fem.K.toarray()
    M = fem.M.toarray()
    w2, V = eigh(K, M)  # ascending, V^T M V = I
    w2 = np.maximum(w2, 0.0)
    n_rigid = 6
    if not (w2[n_rigid - 1] < 1.0e-3 * max(w2[n_rigid], 1.0)):
        # rigid/elastic split not clean — proceed but it's worth knowing
        pass
    sel = slice(n_rigid, n_rigid + n_elastic)
    omega2 = w2[sel].copy()
    Phi = V[:, sel].copy()  # (3N, k) full-DOF (cube has no fixed DOFs)

    centroid = mesh.vertices.mean(axis=0)
    # tracked corners
    corner_ids, corners = _cube_corner_ids(mesh, half)
    corner_rest_world = corners - centroid + np.array([cx, drop_y, cz])
    # modal rows at each corner node: (P, 3, k)
    corner_modal = np.stack([Phi[3 * cid: 3 * cid + 3, :] for cid in corner_ids])

    # surface skinning
    surface = mesh.extract_surface()
    sv = np.unique(surface.faces.ravel())
    remap = np.full(mesh.num_vertices, -1, dtype=np.int64)
    remap[sv] = np.arange(len(sv))
    surf_rest = mesh.vertices[sv] - centroid + np.array([cx, drop_y, cz])
    surf_modal = np.stack([Phi[3 * v: 3 * v + 3, :] for v in sv])
    surf_faces = remap[surface.faces].astype(np.int32)

    # gravity: carrier carries total weight; elastic modes get modal projection
    m_total = fem.total_mass()
    f_grav = np.zeros(3 + n_elastic)
    f_grav[1] = -m_total * _GRAVITY
    f_grav[3:] = Phi.T @ fem.gravity_load(g=-_GRAVITY)

    # modal Rayleigh damping for the elastic modes
    omega = np.sqrt(omega2)
    D_modal = np.diag(alpha0 + alpha1 * omega2)  # 2 ζ ω form folded into D_q

    return FEMModalBody(
        nc=3,
        omega2=omega2,
        carrier_mass=m_total,
        f_grav=f_grav,
        corner_rest=corner_rest_world,
        corner_modal=corner_modal,
        D_modal=D_modal,
        surf_rest=surf_rest,
        surf_modal=surf_modal,
        surf_faces=surf_faces,
    )
