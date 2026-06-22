"""Floating-frame rigid + modal cube ("fem_rigid" cargo).

A full 6-DOF rigid body (translation p + orientation quaternion q) carrying the
cube's FEM elastic eigenmodes `a ∈ R^k` as small linear vibrations IN THE BODY
FRAME — the classic floating-frame-of-reference (FFR) reduced body, and the body
model the DCR paper itself couples (rigid body ⊕ reduced modal subspace).

World map of a material point (body-frame rest coord x̄, modal block Φ):

    x(z) = p + R(q) · (x̄ + Φ · a)                                   (FFR Eq.)

with config z = [p(3), q(4 wxyz), a(k)] and tangent v = [v_lin(3), ω_world(3),
ȧ(k)]. In the AVBD-Native dynamic-constraint port the cube's rigid p/q is an
ordinary 6-DOF body in the GPU solver (real SAT collision, tumbling), and the
elastic `a` is coupled at the cube's contact corners through the SAME dynamic
modal block as the support (`two_band_coupling.html`):
the corner moves with the modes by `R·Φ_c·a`, so a contact's gradient w.r.t.
`a` is the co-rotated `n̂ᵀ·R·Φ_c` (the modal analogue of the support's `U_y`).

This module ports the twobody `dcr/twobody/rigid_modal.py` body model + builder
to the AVBD-Native branch (no `dcr.twobody` dependency). The `FEMRigidModalBody`
methods (`point_jac_tan`, `mass_tan`, `predict`, `retract`, `velocity`, the
internal grad/hess) are the per-cube parity oracle for the GPU coupling.

# DEVIATION (FFR inertial coupling): a uniform cube's rest inertia is isotropic
# (I₀ ≈ I·diag), so the world inertia R I₀ Rᵀ is orientation-independent and the
# gyroscopic torque ω×I₀ω ≈ 0 — both dropped. The rotation↔modal convective
# (Coriolis/centrifugal) coupling is O(‖a‖) for the small modal amplitudes used
# and is likewise dropped. Standard linearized / mean-axis FFR simplifications;
# cite Shabana, *Dynamics of Multibody Systems*, §5 (floating frame of reference).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from scipy.linalg import eigh

from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.geom.tet_mesh import make_block_tet_mesh

_GRAVITY = 9.81  # m/s^2, acting in -Y


# ======================================================================
# Quaternion helpers (Hamilton convention, layout (w, x, y, z))
# ======================================================================
def quat_mul(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Hamilton product a ⊗ b (both (w, x, y, z))."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ])


def quat_conj(q: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.array([q[0], -q[1], -q[2], -q[3]])


def quat_normalize(q: NDArray[np.float64]) -> NDArray[np.float64]:
    n = np.linalg.norm(q)
    return q / n if n > 0.0 else np.array([1.0, 0.0, 0.0, 0.0])


def rotvec_to_quat(phi: NDArray[np.float64]) -> NDArray[np.float64]:
    """Exponential map R^3 → unit quaternion: φ (axis·angle) ↦ [cos, sin·axis]."""
    theta = float(np.linalg.norm(phi))
    if theta < 1.0e-12:
        return np.array([1.0, 0.5 * phi[0], 0.5 * phi[1], 0.5 * phi[2]])
    axis = phi / theta
    s = np.sin(0.5 * theta)
    return np.array([np.cos(0.5 * theta), s * axis[0], s * axis[1], s * axis[2]])


def quat_to_rotvec(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Logarithmic map unit quaternion → R^3 rotation vector (shortest arc)."""
    q = q if q[0] >= 0.0 else -q          # force w ≥ 0 → angle ∈ [0, π]
    v = q[1:4]
    vn = float(np.linalg.norm(v))
    if vn < 1.0e-12:
        return 2.0 * v
    theta = 2.0 * np.arctan2(vn, q[0])
    return (theta / vn) * v


def quat_to_matrix(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Body→world rotation matrix R(q)."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z),     2 * (x * z + w * y)],
        [2 * (x * y + w * z),     1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y),     2 * (y * z + w * x),     1 - 2 * (x * x + y * y)],
    ])


def _skew(u: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.array([[0.0, -u[2], u[1]],
                     [u[2], 0.0, -u[0]],
                     [-u[1], u[0], 0.0]])


def cube_corner_ids(mesh, half: float):
    """The 8 cube-corner vertex ids (nearest mesh vertex to each (±half)³),
    and their world rest coords. Ported from twobody `_cube_corner_ids`."""
    signs = np.array([[sx, sy, sz]
                      for sx in (-1.0, 1.0)
                      for sy in (-1.0, 1.0)
                      for sz in (-1.0, 1.0)])
    centroid = mesh.vertices.mean(axis=0)
    targets = centroid + half * signs
    ids = []
    for t in targets:
        d = np.linalg.norm(mesh.vertices - t, axis=1)
        ids.append(int(np.argmin(d)))
    return np.array(ids, dtype=np.int64), mesh.vertices[ids]


# ======================================================================
# Floating-frame rigid + modal body
# ======================================================================
@dataclass
class FEMRigidModalBody:
    """6-DOF rigid frame ⊕ k elastic modes. z = [p(3), q(4 wxyz), a(k)].

    Config dim = 7 + k; tangent dim = 6 + k (rotation lives on SO(3)).
    """

    mass: float                              # total rigid mass
    inertia0: NDArray[np.float64]            # (3,3) body-frame rest inertia about COM
    omega2: NDArray[np.float64]              # (k,) elastic eigenvalues ω²
    D_modal: NDArray[np.float64]             # (k,k) modal Rayleigh damping
    g_modal_cols: NDArray[np.float64]        # (k,3) Φᵀ(m_n ê_d): co-rotated modal gravity
    corner_body: NDArray[np.float64]         # (P,3) body-frame rest corner coords (COM-rel)
    corner_modal: NDArray[np.float64]        # (P,3,k) modal blocks at corners
    p0: NDArray[np.float64]                  # (3,) initial COM world position
    surf_body: NDArray[np.float64]           # (Ns,3) body-frame rest surface coords
    surf_modal: NDArray[np.float64]          # (Ns,3,k) modal blocks at surface verts
    surf_faces: NDArray[np.int32]            # (F,3) surface triangles
    half_extent: float = 0.05                # collision-box half-size
    # Co-rotation of the modal contact gradient. True (fem_rigid): the modes
    # ride the tumbling body, G_a = n̂ᵀ·R·Φ_c. False (fem material, Stage 5):
    # world-fixed modes (a restriction of fem_rigid), G_a = n̂ᵀ·Φ_c — the
    # reference FEMModalBody's rotation-dropped translation+modal body.
    corotate: bool = True

    is_manifold: bool = field(init=False, default=True)
    k: int = field(init=False)
    ndof: int = field(init=False)            # CONFIG dim (7 + k)
    tdim: int = field(init=False)            # TANGENT dim (6 + k)

    def __post_init__(self) -> None:
        self.k = int(self.omega2.shape[0])
        self.ndof = 7 + self.k
        self.tdim = 6 + self.k

    # -- coordinates ---------------------------------------------------
    def rest_state(self) -> NDArray[np.float64]:
        z = np.zeros(self.ndof)
        z[0:3] = self.p0
        z[3:7] = (1.0, 0.0, 0.0, 0.0)
        return z

    def _unpack(self, z: NDArray[np.float64]):
        return z[0:3], z[3:7], z[7:]          # p, q, a

    def n_corners(self) -> int:
        return self.corner_body.shape[0]

    # -- world kinematics ---------------------------------------------
    def point_world(self, z: NDArray[np.float64], pid: int) -> NDArray[np.float64]:
        p, q, a = self._unpack(z)
        R = quat_to_matrix(q)
        u = self.corner_body[pid] + self.corner_modal[pid] @ a
        return p + R @ u

    def point_jac_tan(self, z: NDArray[np.float64], pid: int) -> NDArray[np.float64]:
        """∂x/∂[δp, δθ_world, δa]  (3 × tdim).

        LEFT-multiplied world rotation increment q ← exp(δθ_world)⊗q gives
        ∂x/∂δp = I₃, ∂x/∂δθ = −[R u]_×, ∂x/∂δa = R Φ_c (the co-rotated modal
        contact Jacobian — the per-cube analogue of the support's U_y).
        """
        p, q, a = self._unpack(z)
        R = quat_to_matrix(q)
        u = self.corner_body[pid] + self.corner_modal[pid] @ a
        Ru = R @ u
        J = np.zeros((3, self.tdim))
        J[:, 0:3] = np.eye(3)
        J[:, 3:6] = -_skew(Ru)
        J[:, 6:] = R @ self.corner_modal[pid]
        return J

    # -- inertial / internal in tangent space -------------------------
    def mass_tan(self, z: NDArray[np.float64]) -> NDArray[np.float64]:
        """Tangent-space mass: blockdiag(m I₃, R I₀ Rᵀ, I_k)."""
        _, q, _ = self._unpack(z)
        R = quat_to_matrix(q)
        M = np.zeros((self.tdim, self.tdim))
        M[0:3, 0:3] = self.mass * np.eye(3)
        M[3:6, 3:6] = R @ self.inertia0 @ R.T
        M[6:, 6:] = np.eye(self.k)            # mass-normalized elastic modes
        return M

    def damping_tan(self) -> NDArray[np.float64]:
        D = np.zeros((self.tdim, self.tdim))
        D[6:, 6:] = self.D_modal
        return D

    # -- uniform cargo-coupling interface (shared with ABDAffineBody) -------
    # The dynamic coupler (`ReducedCoupledAVBDCoupler`) consumes any cargo body
    # through this interface: a constant deformation mass/stiffness/damping
    # block (k×k), per-corner co-rotation shape `corner_modal` (P,3,k) so the
    # contact gradient is n̂ᵀ·R·corner_modal, and (for nonlinear bodies) an
    # internal grad/Hess. The fem_rigid modes are LINEAR ⇒ the elastic block is
    # the constant K_q = diag(ω²) and there is no nonlinear internal.
    has_nonlinear_internal: bool = field(init=False, default=False)

    @property
    def Mq_block(self) -> NDArray[np.float64]:
        return np.eye(self.k)                       # mass-normalized modes

    @property
    def Kq_block(self) -> NDArray[np.float64]:
        return np.diag(self.omega2)                 # linear modal stiffness

    @property
    def Dq_block(self) -> NDArray[np.float64]:
        return self.D_modal

    def internal_grad_d(self, d: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.zeros(self.k)                     # linear ⇒ folded into K_q

    def internal_hess_d(self, d: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.zeros((self.k, self.k))

    def internal_grad_tan(self, z: NDArray[np.float64]) -> NDArray[np.float64]:
        g = np.zeros(self.tdim)
        g[6:] = self.omega2 * z[7:]
        return g

    def internal_hess_tan(self, z: NDArray[np.float64]) -> NDArray[np.float64]:
        H = np.zeros((self.tdim, self.tdim))
        H[6:, 6:] = np.diag(self.omega2)
        return H

    def internal_energy(self, z: NDArray[np.float64]) -> float:
        a = z[7:]
        return 0.5 * float(a @ (self.omega2 * a))

    # -- predictor / retraction / velocity ----------------------------
    def predict(self, z: NDArray[np.float64], v: NDArray[np.float64],
                h: float) -> NDArray[np.float64]:
        """Free-flight inertial predictor z̃ (gravity folded in, no torque)."""
        p, q, a = self._unpack(z)
        vlin, omega, adot = v[0:3], v[3:6], v[6:]
        p_t = p + h * vlin + (h * h) * np.array([0.0, -_GRAVITY, 0.0])
        q_t = quat_normalize(quat_mul(rotvec_to_quat(h * omega), q))
        R = quat_to_matrix(q)
        g_modal = self.g_modal_cols @ (R.T @ np.array([0.0, -_GRAVITY, 0.0]))
        a_t = a + h * adot + (h * h) * g_modal
        out = np.zeros(self.ndof)
        out[0:3], out[3:7], out[7:] = p_t, q_t, a_t
        return out

    def tangent_residual(self, z: NDArray[np.float64],
                         z_ref: NDArray[np.float64]) -> NDArray[np.float64]:
        """z ⊖ z_ref in tangent space: [p−p_ref, log(q ⊗ q_ref⁻¹), a−a_ref]."""
        p, q, a = self._unpack(z)
        pr, qr, ar = self._unpack(z_ref)
        r = np.zeros(self.tdim)
        r[0:3] = p - pr
        r[3:6] = quat_to_rotvec(quat_mul(q, quat_conj(qr)))
        r[6:] = a - ar
        return r

    def retract(self, z: NDArray[np.float64],
                delta: NDArray[np.float64]) -> NDArray[np.float64]:
        """Apply a tangent increment: p += δp, q ← exp(δθ)⊗q, a += δa."""
        p, q, a = self._unpack(z)
        dp, dth, da = delta[0:3], delta[3:6], delta[6:]
        out = np.zeros(self.ndof)
        out[0:3] = p + dp
        out[3:7] = quat_normalize(quat_mul(rotvec_to_quat(dth), q))
        out[7:] = a + da
        return out

    def velocity(self, z_n: NDArray[np.float64], z: NDArray[np.float64],
                 h: float) -> NDArray[np.float64]:
        """Tangent velocity from a finite step: v_lin, ω_world, ȧ."""
        p, q, a = self._unpack(z)
        pn, qn, an = self._unpack(z_n)
        v = np.zeros(self.tdim)
        v[0:3] = (p - pn) / h
        v[3:6] = quat_to_rotvec(quat_mul(q, quat_conj(qn))) / h
        v[6:] = (a - an) / h
        return v

    def grav_pe(self, z: NDArray[np.float64]) -> float:
        return self.mass * _GRAVITY * float(z[1])

    # -- viewer skinning ----------------------------------------------
    def deformed_surface(self, z: NDArray[np.float64],
                         exaggerate: float = 1.0) -> NDArray[np.float64]:
        """World surface vertices (Ns,3); `exaggerate` scales only the modal flex."""
        p, q, a = self._unpack(z)
        R = quat_to_matrix(q)
        u = self.surf_body + exaggerate * (self.surf_modal @ a)
        return (u @ R.T) + p


# ======================================================================
# Builder
# ======================================================================
def build_fem_rigid_cube(
    size: float = 0.1,
    nx: int = 3,
    material: Material | None = None,
    n_elastic: int = 6,
    drop_y: float = 0.12,
    alpha0: float = 1.0,
    alpha1: float = 5.0e-4,
    cx: float = 0.0,
    cz: float = 0.0,
    corotate: bool = True,
) -> FEMRigidModalBody:
    """6-DOF rigid frame + `n_elastic` FEM elastic eigenmodes (the FFR cube).

    The free-body generalized eigenproblem's 6 rigid modes are discarded and the
    next `n_elastic` ELASTIC modes kept; the rigid motion is restored as a true
    6-DOF rigid body (p + quaternion) so the cube can tumble.
    """
    material = material or Material(E=1.0e9, nu=0.3, rho=600.0)
    mesh = make_block_tet_mesh(size=size, nx=nx, ny=nx, nz=nx)
    half = 0.5 * size
    fem = FEMModel(mesh=mesh, material=material, alpha0=alpha0, alpha1=alpha1)

    # Free-body generalized eigenproblem (no fixed nodes ⇒ K/M are the full
    # unconstrained matrices); keep the elastic modes (skip 6 rigid).
    K = fem.K_full.toarray()
    M = fem.M_full.toarray()
    w2, V = eigh(K, M)                         # ascending, Vᵀ M V = I
    w2 = np.maximum(w2, 0.0)
    n_rigid = 6
    sel = slice(n_rigid, n_rigid + n_elastic)
    omega2 = w2[sel].copy()
    Phi = V[:, sel].copy()                     # (3N, k)

    centroid = mesh.vertices.mean(axis=0)
    r = mesh.vertices - centroid               # (N,3) body-frame node coords

    # Body-frame rest inertia about COM from lumped nodal masses (≈ isotropic).
    m_node = fem.M_full.diagonal()[0::3]       # x-diagonal == lumped nodal mass
    inertia0 = np.zeros((3, 3))
    for n in range(r.shape[0]):
        rn = r[n]
        inertia0 += m_node[n] * (float(rn @ rn) * np.eye(3) - np.outer(rn, rn))

    # tracked corners (body frame, COM-relative)
    corner_ids, corners = cube_corner_ids(mesh, half)
    corner_body = corners - centroid
    corner_modal = np.stack([Phi[3 * cid: 3 * cid + 3, :] for cid in corner_ids])

    # surface skinning (body frame)
    surface = mesh.extract_surface()
    sv = np.unique(surface.faces.ravel())
    remap = np.full(mesh.num_vertices, -1, dtype=np.int64)
    remap[sv] = np.arange(len(sv))
    surf_body = mesh.vertices[sv] - centroid
    surf_modal = np.stack([Phi[3 * v: 3 * v + 3, :] for v in sv])
    surf_faces = remap[surface.faces].astype(np.int32)

    # co-rotated modal gravity: g_modal(q) = g_modal_cols @ (Rᵀ·(0,−g,0)).
    g_modal_cols = np.zeros((omega2.shape[0], 3))
    for d in range(3):
        f = np.zeros(3 * mesh.num_vertices)
        f[d::3] = m_node
        g_modal_cols[:, d] = Phi.T @ f

    # modal Rayleigh damping for the elastic modes.
    D_modal = np.diag(alpha0 + alpha1 * omega2)

    return FEMRigidModalBody(
        mass=float(fem.total_mass()),
        inertia0=inertia0,
        omega2=omega2,
        D_modal=D_modal,
        g_modal_cols=g_modal_cols,
        corner_body=corner_body,
        corner_modal=corner_modal,
        p0=np.array([cx, drop_y, cz]),
        surf_body=surf_body,
        surf_modal=surf_modal,
        surf_faces=surf_faces,
        half_extent=half,
        corotate=corotate,
    )


def build_fem_cube(**kwargs) -> FEMRigidModalBody:
    """The "fem" cube material (Stage 5): translation(3)+modal, NO co-rotation
    — a restriction of fem_rigid (reference `reduced_body.py:FEMModalBody`). The
    modal contact gradient is the world-fixed n̂ᵀ·Φ_c (the rigid frame may still
    translate under the solver, but the modal subspace does not co-rotate)."""
    kwargs.pop("corotate", None)
    return build_fem_rigid_cube(corotate=False, **kwargs)


def build_rigid_cube(**kwargs) -> FEMRigidModalBody:
    """The "rigid" cargo material — a pure 6-DOF rigid cube with ZERO elastic
    modes (the k=0 limit of `build_fem_rigid_cube`). It is the baseline/control
    alongside fem_rigid/fem/abd: the cube tumbles and collides as an ordinary
    rigid body (real SAT) and rides the support's modal ring through its contact
    corners, but carries NO internal deformation. With k=0 the augmented modal
    vector Q gains no a-block (R_tot = r), `corner_modal` is (P,3,0) ⇒ the
    co-rotated modal gradient G_a is empty, and `cargo_a` returns an empty array
    — so the native cargo path reduces exactly to the support-only modal solve
    (M1) while still exposing the uniform cargo interface."""
    kwargs.pop("corotate", None)
    kwargs.pop("n_elastic", None)
    # corotate is irrelevant with no modes; keep the default. The small FEM
    # eigensolve still runs (on a 3×3×3 cube) but its elastic columns are dropped
    # — it yields the correct rigid mass, inertia, corners, and skinning surface.
    return build_fem_rigid_cube(n_elastic=0, **kwargs)
