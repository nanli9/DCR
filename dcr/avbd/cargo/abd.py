"""Co-rotated affine-body-dynamics (ABD) cube ("abd" cargo).

A full 6-DOF rigid frame (translation p + orientation quaternion R, carried by
the AVBD-Native rigid solver with real SAT collision) PLUS a 9-DOF *body-frame*
affine deformation F ∈ R^{3×3} (the cube shears/stretches in its own frame).
World map of a material point (body-frame rest coord x̄, COM-relative):

    x(z) = p + R · (F · x̄)                                   (co-rotated ABD)

with the affine deformation DOF vector  d = vec(F − I) ∈ R^9 (row-major,
d[3i+j] = (F−I)[i,j]); d = 0 ⇒ F = I ⇒ undeformed. The deformation is governed
by the stiff quartic orthogonality potential V⊥ (Lan et al. 2022, ABD Eq. 6–8)
that pulls F back toward a rotation, so the cube behaves as a near-rigid affine
solid that shears under impact and rings back.

This is the AVBD-Native cube analogue of the twobody `ABDAffineBody`
(`dcr/twobody/reduced_body.py`), re-expressed to RIDE the rigid solver's frame:

# DEVIATION (co-rotated affine vs reference global affine, ABD Eq. 1): the
# reference body is a GLOBAL 12-DOF affine A with NO rigid frame (a flat
# axis-aligned drop — see its own Eq. 9 deviation). Here the rigid rotation is
# the AVBD solver's tumbling 6-DOF body and F is the body-frame affine on top,
# so the cube tumbles (real SAT collision) AND shears. The two coincide for a
# non-rotating drop (R = I). Approved design decision (the Stage-4 acceptance
# requires "tumbles + shears"); reuses the Stage-3 augmented-modal coupling
# verbatim because the affine corner Jacobian B_c plays the role of Φ_c.

# DEVIATION (collision on the rigid frame): SAT collision uses the rigid box
# (p, R); the affine flex F couples into the contact only through the corner
# gradient n̂ᵀ·R·B_c (the same staggered corner-flex anchor as fem_rigid's
# modal coupling), not by deforming the SAT box. V⊥ keeps F near a rotation so
# the box barely deviates — a good approximation, identical in spirit to the
# fem_rigid modal-corner coupling.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.geom.tet_mesh import make_beam_tet_mesh

from .fem_rigid import _box_resolution, box_corner_ids, quat_to_matrix

_GRAVITY = 9.81  # m/s^2, acting in -Y


@dataclass
class ABDAffineBody:
    """Co-rotated affine cube. Deformation DOF d = vec(F − I) ∈ R^9.

    Exposes the uniform cargo-coupling interface (shared with FEMRigidModalBody):
    constant deformation blocks `Mq_block/Kq_block/Dq_block` (9×9), per-corner
    co-rotation shape `corner_modal` (P,3,9) = the affine corner Jacobian B_c
    (so the contact gradient is n̂ᵀ·R·B_c), and the NONLINEAR quartic V⊥
    internal grad/Hess (recomputed per iteration).
    """

    mass: float                              # total rigid mass (rigid solver)
    inertia0: NDArray[np.float64]            # (3,3) body-frame rest inertia (rigid solver)
    affine_inertia: NDArray[np.float64]      # (3,3) Q = Σ m_n x̄_n x̄_nᵀ (affine mass core)
    kappa_v: float                           # κ_v orthogonality stiffness (ABD Eq. 7)
    alpha0: float                            # mass-proportional Rayleigh damping
    corner_body: NDArray[np.float64]         # (P,3) body-frame rest corner coords (COM-rel)
    p0: NDArray[np.float64]                  # (3,) initial COM world position
    surf_body: NDArray[np.float64]           # (Ns,3) body-frame rest surface coords
    surf_faces: NDArray[np.int32]            # (F,3) surface triangles
    half_extent: float = 0.05                # collision-box half-size (min axis)
    # Full per-axis half-extents (hx, hy, hz). None ⇒ a cube of `half_extent`.
    half_extents: tuple[float, float, float] | None = None

    is_manifold: bool = field(init=False, default=True)
    has_nonlinear_internal: bool = field(init=False, default=True)
    k: int = field(init=False, default=9)
    ndof: int = field(init=False)            # CONFIG dim (7 + 9 affine)
    tdim: int = field(init=False)            # TANGENT dim (6 + 9)
    corner_modal: NDArray[np.float64] = field(init=False)   # (P,3,9) B_c
    _Mq: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.k = 9
        self.ndof = 7 + 9
        self.tdim = 6 + 9
        if self.half_extents is None:
            self.half_extents = (self.half_extent,) * 3
        # Per-corner affine Jacobian B_c (3×9): u_body = (F−I)·x̄_c ⇒
        # B_c[m, 3m:3m+3] = x̄_c (row m couples d-block m). This is the affine
        # analogue of the modal Φ_c — the coupler treats it identically.
        P = self.corner_body.shape[0]
        Bc = np.zeros((P, 3, 9), dtype=np.float64)
        for c in range(P):
            xc = self.corner_body[c]
            for m in range(3):
                Bc[c, m, 3 * m:3 * m + 3] = xc
        self.corner_modal = Bc
        # Affine deformation mass M_F = blockdiag(Q, Q, Q) (ABD Eq. 4 with
        # COM-relative nodes ⇒ the p↔F cross-mass vanishes, so the F-block
        # decouples from the rigid translation handled by the solver).
        Q = self.affine_inertia
        M = np.zeros((9, 9), dtype=np.float64)
        for i in range(3):
            M[3 * i:3 * i + 3, 3 * i:3 * i + 3] = Q
        self._Mq = M

    # -- coordinates ---------------------------------------------------
    def rest_state(self) -> NDArray[np.float64]:
        z = np.zeros(self.ndof)
        z[0:3] = self.p0
        z[3:7] = (1.0, 0.0, 0.0, 0.0)
        # z[7:] = vec(F−I) = 0 (F = I).
        return z

    def n_corners(self) -> int:
        return self.corner_body.shape[0]

    # -- uniform cargo-coupling interface ------------------------------
    @property
    def Mq_block(self) -> NDArray[np.float64]:
        return self._Mq

    @property
    def Kq_block(self) -> NDArray[np.float64]:
        # Elastic energy is the NONLINEAR V⊥ ⇒ no constant linear block.
        return np.zeros((9, 9), dtype=np.float64)

    @property
    def Dq_block(self) -> NDArray[np.float64]:
        # Mass-proportional Rayleigh damping D = α₀·M_F (ABD set_damping).
        return self.alpha0 * self._Mq

    @property
    def omega2(self) -> NDArray[np.float64]:
        # For the substep_end modal-energy log: a "stiffness" proxy. The real
        # elastic energy is V⊥ (internal_energy); this 0 vector means the logged
        # PE uses ½dᵀ·0·d = 0 for the linear term — the coupler adds V⊥ via
        # internal_energy separately if needed. Kept for interface uniformity.
        return np.zeros(9, dtype=np.float64)

    def _A_rows(self, d: NDArray[np.float64]):
        """The three affine rows a_i = e_i + (F−I)[i,:] = e_i + d[3i:3i+3]."""
        return (np.array([1.0, 0.0, 0.0]) + d[0:3],
                np.array([0.0, 1.0, 0.0]) + d[3:6],
                np.array([0.0, 0.0, 1.0]) + d[6:9])

    def internal_energy(self, d: NDArray[np.float64]) -> float:
        """V⊥ = κ Σ_i[(‖a_i‖²−1)² + Σ_{j≠i}(a_i·a_j)²] (ABD Eq. 6)."""
        a = self._A_rows(d)
        e = 0.0
        for i in range(3):
            e += (a[i] @ a[i] - 1.0) ** 2
            for j in range(3):
                if j != i:
                    e += (a[i] @ a[j]) ** 2
        return self.kappa_v * e

    def internal_grad_d(self, d: NDArray[np.float64]) -> NDArray[np.float64]:
        """∂V⊥/∂d (ABD Eq. 6 gradient; same as ∂/∂a_i since a_i = e_i + d_i)."""
        a = self._A_rows(d)
        g = np.zeros(9)
        for i in range(3):
            gi = 4.0 * self.kappa_v * (a[i] @ a[i] - 1.0) * a[i]
            for j in range(3):
                if j != i:
                    gi += 4.0 * self.kappa_v * (a[i] @ a[j]) * a[j]
            g[3 * i:3 * i + 3] = gi
        return g

    def internal_hess_d(self, d: NDArray[np.float64]) -> NDArray[np.float64]:
        """∂²V⊥/∂d² (ABD Eq. 8), the 9×9 affine block."""
        a = self._A_rows(d)
        H = np.zeros((9, 9))
        for i in range(3):
            Hii = (8.0 * self.kappa_v * np.outer(a[i], a[i])
                   + 4.0 * self.kappa_v * (a[i] @ a[i] - 1.0) * np.eye(3))
            for j in range(3):
                if j != i:
                    Hii += 4.0 * self.kappa_v * np.outer(a[j], a[j])
            bi = 3 * i
            H[bi:bi + 3, bi:bi + 3] = Hii
            for j in range(3):
                if j != i:
                    Hij = 4.0 * self.kappa_v * (np.outer(a[j], a[i])
                                                + (a[i] @ a[j]) * np.eye(3))
                    bj = 3 * j
                    H[bi:bi + 3, bj:bj + 3] = Hij
        return H

    # -- elastic constraints for XPBD (compliant-constraint form) -----
    def elastic_constraints(self, d: NDArray[np.float64]):
        """V⊥ as XPBD compliant constraints (Macklin 2016 §3, ABD Eq. 6–7).

        Ports `dcr/twobody/reduced_body.py:ABDAffineBody.elastic_constraints`
        to the 9-DOF body-frame deformation `d = vec(F−I)` (the reference uses
        the 12-DOF global affine; here ∂/∂a_i = ∂/∂d[3i:3i+3] since
        a_i = e_i + d[3i:3i+3]). V⊥ = κ Σ_i[(‖a_i‖²−1)² + Σ_{j≠i}(a_i·a_j)²] is a
        sum of squared scalar constraints with energy ½ k C²: 3 diagonal
        C_ii = ‖a_i‖²−1 (each appears ONCE ⇒ k = 2κ ⇒ α = 1/(2κ)) and 3
        off-diagonal C_ij = a_i·a_j (i<j; each appears TWICE in the j≠i double
        sum ⇒ k = 4κ ⇒ α = 1/(4κ)). Returns ``(C, grad(9,), compliance,
        damp_coeff)`` tuples; grad is re-linearized each XPBD projection (V⊥ is
        genuinely nonlinear — standard PBD treatment).

        # DEVIATION (XPBDDynamicSystem oracle): ABD's mass-proportional damping
        # D = α₀ M_F is NOT wired through the per-constraint damp term (reported
        # 0 here), exactly as the reference — so the AVBD path is the damped one
        # for abd; XPBD-abd projects V⊥ without per-constraint ring-down.
        """
        a = self._A_rows(d)
        alpha_diag = 1.0 / (2.0 * self.kappa_v)   # diagonal term once
        alpha_off = 1.0 / (4.0 * self.kappa_v)    # off-diagonal counted twice
        out = []
        for i in range(3):
            g = np.zeros(9)
            g[3 * i:3 * i + 3] = 2.0 * a[i]
            out.append((float(a[i] @ a[i] - 1.0), g, alpha_diag, 0.0))
        for i in range(3):
            for j in range(i + 1, 3):
                g = np.zeros(9)
                g[3 * i:3 * i + 3] = a[j]
                g[3 * j:3 * j + 3] = a[i]
                out.append((float(a[i] @ a[j]), g, alpha_off, 0.0))
        return out

    # -- viewer skinning ----------------------------------------------
    def deformed_surface(self, z: NDArray[np.float64],
                         exaggerate: float = 1.0) -> NDArray[np.float64]:
        """World surface vertices (Ns,3); `exaggerate` scales only the affine
        flex (F−I)·x̄, leaving rigid p/R untouched."""
        p, q = z[0:3], z[3:7]
        d = z[7:]
        F_minus_I = d.reshape(3, 3)
        R = quat_to_matrix(q)
        u = self.surf_body + exaggerate * (self.surf_body @ F_minus_I.T)
        return (u @ R.T) + p


def build_abd_box(
    half_extents,
    resolution: int | tuple[int, int, int] = 3,
    material: Material | None = None,
    kappa_v: float = 5.0e3,
    alpha0: float = 1.0,
    drop_y: float = 0.12,
    cx: float = 0.0,
    cz: float = 0.0,
) -> ABDAffineBody:
    """Co-rotated ABD affine (hx,hy,hz) box, centroid at (cx, drop_y, cz).
    The affine basis is geometry-driven (Q = Σ m x̄x̄ᵀ from the mesh), so
    anisotropic boxes need no formulation change — only the mesh + corners."""
    material = material or Material(E=1.0e9, nu=0.3, rho=600.0)
    half = np.asarray(half_extents, dtype=np.float64).reshape(3)
    if isinstance(resolution, (int, np.integer)):
        nxyz = _box_resolution(half, base=int(resolution))
    else:
        nxyz = tuple(int(n) for n in resolution)
    mesh = make_beam_tet_mesh(
        length=2.0 * half[0], width=2.0 * half[1], height=2.0 * half[2],
        nx=nxyz[0], ny=nxyz[1], nz=nxyz[2])
    fem = FEMModel(mesh=mesh, material=material)
    m_node = fem.M_full.diagonal()[0::3]       # lumped nodal mass
    centroid = mesh.vertices.mean(axis=0)
    r = mesh.vertices - centroid               # COM-relative node coords

    # Affine mass core Q = Σ m_n x̄_n x̄_nᵀ (ABD Eq. 4, COM-relative).
    Q = np.zeros((3, 3))
    for n in range(r.shape[0]):
        Q += m_node[n] * np.outer(r[n], r[n])

    # Rigid inertia (body frame, about COM) for the solver's rigid block.
    inertia0 = np.zeros((3, 3))
    for n in range(r.shape[0]):
        rn = r[n]
        inertia0 += m_node[n] * (float(rn @ rn) * np.eye(3) - np.outer(rn, rn))

    corner_ids, corners = box_corner_ids(mesh, half)
    corner_body = corners - centroid

    surface = mesh.extract_surface()
    sv = np.unique(surface.faces.ravel())
    remap = np.full(mesh.num_vertices, -1, dtype=np.int64)
    remap[sv] = np.arange(len(sv))
    surf_body = mesh.vertices[sv] - centroid
    surf_faces = remap[surface.faces].astype(np.int32)

    return ABDAffineBody(
        mass=float(fem.total_mass()),
        inertia0=inertia0,
        affine_inertia=Q,
        kappa_v=float(kappa_v),
        alpha0=float(alpha0),
        corner_body=corner_body,
        p0=np.array([cx, drop_y, cz]),
        surf_body=surf_body,
        surf_faces=surf_faces,
        half_extent=float(half.min()),
        half_extents=(float(half[0]), float(half[1]), float(half[2])),
    )


def build_abd_cube(
    size: float = 0.1,
    nx: int = 3,
    material: Material | None = None,
    kappa_v: float = 5.0e3,
    alpha0: float = 1.0,
    drop_y: float = 0.12,
    cx: float = 0.0,
    cz: float = 0.0,
) -> ABDAffineBody:
    """Co-rotated ABD affine cube — exact-equivalence wrapper over
    `build_abd_box` with a (size/2)³ box and an (nx,nx,nx) grid (mesh and all
    derived quantities bit-identical to the pre-box cube builder)."""
    return build_abd_box(
        half_extents=(0.5 * size,) * 3, resolution=(nx, nx, nx),
        material=material, kappa_v=kappa_v, alpha0=alpha0,
        drop_y=drop_y, cx=cx, cz=cz)
