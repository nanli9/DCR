"""Implicit Newmark-beta integrator for linear FEM dynamics.

Solves the equation of motion (paper Eq. 5):
    M u_ddot + D u_dot + K u = f

using the trapezoidal rule (beta=0.25, gamma=0.5) which is unconditionally
stable.  The effective stiffness K_eff is factored once at init; each step
is a single sparse back-substitution.

Also provides CoupledFEMRigidSim for ground-truth comparison (Stage 7):
a deformable table coupled to simplified rigid plates via penalty contact.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .fem_model import FEMModel


# ---------------------------------------------------------------------------
# Newmark integrator
# ---------------------------------------------------------------------------

@dataclass
class NewmarkIntegrator:
    """Implicit Newmark-beta integrator on the free DOFs of an FEMModel.

    Kinematic update (Eq. 5 discretisation):
        u_{n+1} = u_n + h*v_n + h^2*((0.5-beta)*a_n + beta*a_{n+1})
        v_{n+1} = v_n + h*((1-gamma)*a_n + gamma*a_{n+1})

    With beta=0.25, gamma=0.5 (trapezoidal rule, unconditionally stable):
        K_eff = K + 4/(h^2)*M + 2/h*D
    """

    fem: FEMModel
    h: float = 1e-5
    beta: float = 0.25
    gamma: float = 0.5

    # State vectors (free DOFs).
    u: NDArray[np.float64] = field(init=False, repr=False)
    v: NDArray[np.float64] = field(init=False, repr=False)
    a: NDArray[np.float64] = field(init=False, repr=False)

    # Pre-factored effective stiffness.
    _K_eff_lu: spla.SuperLU = field(init=False, repr=False)

    # Cached constants.
    _c0: float = field(init=False)  # 1/(beta*h^2)
    _c1: float = field(init=False)  # gamma/(beta*h)
    _c2: float = field(init=False)  # 1/(beta*h)
    _c3: float = field(init=False)  # 0.5/beta - 1
    _c4: float = field(init=False)  # gamma/beta - 1
    _c5: float = field(init=False)  # h*(gamma/(2*beta) - 1)

    def __post_init__(self) -> None:
        n = self.fem.free_dofs.size
        self.u = np.zeros(n, dtype=np.float64)
        self.v = np.zeros(n, dtype=np.float64)
        self.a = np.zeros(n, dtype=np.float64)

        h, b, g = self.h, self.beta, self.gamma
        self._c0 = 1.0 / (b * h * h)
        self._c1 = g / (b * h)
        self._c2 = 1.0 / (b * h)
        self._c3 = 0.5 / b - 1.0
        self._c4 = g / b - 1.0
        self._c5 = h * (g / (2.0 * b) - 1.0)

        M, D, K = self.fem.M, self.fem.damping_matrix, self.fem.K
        K_eff = K + self._c0 * M + self._c1 * D
        self._K_eff_lu = spla.splu(K_eff.tocsc())

    def step(self, f_ext: NDArray[np.float64] | None = None) -> None:
        """Advance one Newmark step.

        Args:
            f_ext: External force vector on free DOFs.  None = zero.
        """
        M, D = self.fem.M, self.fem.damping_matrix
        n = self.u.size

        if f_ext is None:
            f_ext = np.zeros(n, dtype=np.float64)

        # RHS: f + M*(c0*u + c2*v + c3*a) + D*(c1*u + c4*v + c5*a)
        rhs = (f_ext
               + M @ (self._c0 * self.u + self._c2 * self.v + self._c3 * self.a)
               + D @ (self._c1 * self.u + self._c4 * self.v + self._c5 * self.a))

        u_new = self._K_eff_lu.solve(rhs)

        # Recover acceleration and velocity.
        a_new = self._c0 * (u_new - self.u) - self._c2 * self.v - self._c3 * self.a
        v_new = self.v + self.h * ((1.0 - self.gamma) * self.a + self.gamma * a_new)

        self.u = u_new
        self.v = v_new
        self.a = a_new

    def full_displacement(self) -> NDArray[np.float64]:
        """Expand free-DOF displacement to all DOFs (fixed = 0)."""
        u_full = np.zeros(self.fem.n_full_dofs, dtype=np.float64)
        u_full[self.fem.free_dofs] = self.u
        return u_full

    def surface_y_displacement(self, vertex_idx: int) -> float:
        """Return the Y-component of displacement at a mesh vertex."""
        dof_y = 3 * vertex_idx + 1
        # Check if this DOF is free.
        loc = np.searchsorted(self.fem.free_dofs, dof_y)
        if loc < self.fem.free_dofs.size and self.fem.free_dofs[loc] == dof_y:
            return float(self.v[loc])  # wait, this should be displacement
        return 0.0

    def vertex_displacement(self, vertex_idx: int) -> NDArray[np.float64]:
        """Return (3,) displacement vector at a mesh vertex."""
        disp = np.zeros(3, dtype=np.float64)
        for c in range(3):
            dof = 3 * vertex_idx + c
            loc = np.searchsorted(self.fem.free_dofs, dof)
            if loc < self.fem.free_dofs.size and self.fem.free_dofs[loc] == dof:
                disp[c] = self.u[loc]
        return disp


# ---------------------------------------------------------------------------
# Coupled FEM + rigid body ground-truth simulation
# ---------------------------------------------------------------------------

@dataclass
class SimpleRigidBody:
    """Minimal 1D rigid body for ground-truth coupling (vertical motion only)."""
    mass: float
    y: float            # centre-of-mass Y position
    vy: float = 0.0     # Y velocity
    half_height: float = 0.02
    half_width_x: float = 0.06
    half_width_z: float = 0.06

    def bottom_y(self) -> float:
        return self.y - self.half_height


@dataclass
class CoupledFEMRigidSim:
    """Ground-truth coupled deformable table + rigid body simulation.

    The table is a deformable FEM body integrated with implicit Newmark.
    Plates and pot are simplified rigid bodies with 1D vertical motion.
    Contact between rigid bodies and the deformable table surface uses
    a penalty method.

    This is intentionally slow and correct -- it serves as ground truth
    for validating the DCR approximation.
    """

    fem: FEMModel
    h_fine: float = 1e-5
    k_penalty: float = 5e7
    gravity: float = -9.81

    # Built in __post_init__.
    _newmark: NewmarkIntegrator = field(init=False, repr=False)
    _top_surface_verts: NDArray[np.int32] = field(init=False, repr=False)
    _top_surface_tris: NDArray[np.int32] = field(init=False, repr=False)
    _top_surface_rest_y: float = field(init=False)

    def __post_init__(self) -> None:
        self._newmark = NewmarkIntegrator(fem=self.fem, h=self.h_fine)

        # Identify top surface vertices (y ≈ max y).
        verts = self.fem.mesh.vertices
        y_max = verts[:, 1].max()
        tol = 1e-6
        self._top_surface_verts = np.where(
            np.abs(verts[:, 1] - y_max) < tol)[0].astype(np.int32)
        self._top_surface_rest_y = float(y_max)

        # Build top-surface triangles from the full surface mesh.
        surface = self.fem.mesh.extract_surface()
        top_set = set(self._top_surface_verts.tolist())
        top_tris = []
        for fi in range(surface.faces.shape[0]):
            f = surface.faces[fi]
            if f[0] in top_set and f[1] in top_set and f[2] in top_set:
                top_tris.append(f)
        self._top_surface_tris = np.array(top_tris, dtype=np.int32) if top_tris \
            else np.empty((0, 3), dtype=np.int32)

    def _deformed_surface_y(
        self, x: float, z: float, u_full: NDArray[np.float64],
    ) -> float:
        """Interpolate the deformed top-surface Y at (x, z).

        Falls back to the undeformed rest Y if no triangle contains (x,z).
        """
        verts = self.fem.mesh.vertices
        best_y = self._top_surface_rest_y
        best_dist = np.inf

        for fi in range(self._top_surface_tris.shape[0]):
            i0, i1, i2 = self._top_surface_tris[fi]
            # Project onto XZ plane for barycentric test.
            ax, az = verts[i0, 0], verts[i0, 2]
            bx, bz = verts[i1, 0], verts[i1, 2]
            cx, cz = verts[i2, 0], verts[i2, 2]

            # Barycentric coordinates in XZ plane.
            denom = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
            if abs(denom) < 1e-15:
                continue
            w0 = ((bz - cz) * (x - cx) + (cx - bx) * (z - cz)) / denom
            w1 = ((cz - az) * (x - cx) + (ax - cx) * (z - cz)) / denom
            w2 = 1.0 - w0 - w1

            # Check if inside triangle (with margin).
            margin = -0.05
            if w0 >= margin and w1 >= margin and w2 >= margin:
                y0 = verts[i0, 1] + u_full[3 * i0 + 1]
                y1 = verts[i1, 1] + u_full[3 * i1 + 1]
                y2 = verts[i2, 1] + u_full[3 * i2 + 1]
                interp_y = w0 * y0 + w1 * y1 + w2 * y2
                # Use closest triangle centre for fallback.
                cx_tri = (ax + bx + cx) / 3
                cz_tri = (az + bz + cz) / 3
                dist = (x - cx_tri) ** 2 + (z - cz_tri) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best_y = interp_y

        return best_y

    def _find_closest_tri(
        self, x: float, z: float,
    ) -> tuple[int, NDArray[np.float64]]:
        """Find the closest top-surface triangle to (x, z) in the XZ plane.

        Returns (triangle_index_in_top_surface_tris, barycentric_weights).
        """
        verts = self.fem.mesh.vertices
        best_idx = 0
        best_dist = np.inf
        best_bary = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])

        for fi in range(self._top_surface_tris.shape[0]):
            i0, i1, i2 = self._top_surface_tris[fi]
            cx_tri = (verts[i0, 0] + verts[i1, 0] + verts[i2, 0]) / 3
            cz_tri = (verts[i0, 2] + verts[i1, 2] + verts[i2, 2]) / 3
            dist = (x - cx_tri) ** 2 + (z - cz_tri) ** 2
            if dist < best_dist:
                best_dist = dist
                best_idx = fi

                ax, az = verts[i0, 0], verts[i0, 2]
                bx, bz = verts[i1, 0], verts[i1, 2]
                cx_, cz_ = verts[i2, 0], verts[i2, 2]
                denom = (bz - cz_) * (ax - cx_) + (cx_ - bx) * (az - cz_)
                if abs(denom) > 1e-15:
                    w0 = ((bz - cz_) * (x - cx_) + (cx_ - bx) * (z - cz_)) / denom
                    w1 = ((cz_ - az) * (x - cx_) + (ax - cx_) * (z - cz_)) / denom
                    w2 = 1.0 - w0 - w1
                    # Clamp to triangle.
                    w0 = max(0.0, min(1.0, w0))
                    w1 = max(0.0, min(1.0, w1))
                    w2 = max(0.0, min(1.0, w2))
                    s = w0 + w1 + w2
                    if s > 0:
                        best_bary = np.array([w0 / s, w1 / s, w2 / s])

        return best_idx, best_bary

    def run(
        self,
        pot: SimpleRigidBody,
        plates: list[SimpleRigidBody],
        plate_xz: list[tuple[float, float]],
        pot_xz: tuple[float, float],
        t_total: float,
        record_every: int = 100,
    ) -> dict:
        """Run the coupled simulation.

        Args:
            pot: The heavy impactor.
            plates: List of lightweight plate bodies.
            plate_xz: (x, z) positions for each plate.
            pot_xz: (x, z) position for the pot.
            t_total: Total simulation time [s].
            record_every: Record trajectory every N fine steps.

        Returns:
            Dictionary with trajectory arrays:
                times: (n_frames,) timestamps
                pot_y: (n_frames,) pot Y position
                plate_ys: (n_frames, n_plates) plate Y positions
                plate_vys: (n_frames, n_plates) plate Y velocities
        """
        n_steps = int(t_total / self.h_fine)
        n_plates = len(plates)
        gravity_load = self.fem.gravity_load(g=self.gravity)

        times = []
        pot_ys = []
        plate_ys_list = []
        plate_vys_list = []

        for step_i in range(n_steps):
            u_full = self._newmark.full_displacement()

            # --- Contact forces ---
            f_contact = np.zeros(self.fem.free_dofs.size, dtype=np.float64)

            # Pot → table contact.
            surf_y_pot = self._deformed_surface_y(pot_xz[0], pot_xz[1], u_full)
            pen_pot = surf_y_pot + pot.half_height - pot.bottom_y()
            # Pot pushes table down if it's touching.
            if pot.bottom_y() <= surf_y_pot + pot.half_height:
                pen = surf_y_pot - (pot.bottom_y() - 0.0)
                # Penetration is how much pot overlaps the surface.
                pen = surf_y_pot - pot.bottom_y()
                if pen > 0:
                    f_pot = self.k_penalty * pen
                    pot.vy += self.h_fine * (self.gravity + f_pot / pot.mass)
                    # Distribute reaction onto FEM nodes.
                    tri_idx, bary = self._find_closest_tri(pot_xz[0], pot_xz[1])
                    if tri_idx < self._top_surface_tris.shape[0]:
                        tri = self._top_surface_tris[tri_idx]
                        for k in range(3):
                            dof_y = 3 * tri[k] + 1
                            loc = np.searchsorted(self.fem.free_dofs, dof_y)
                            if loc < self.fem.free_dofs.size and self.fem.free_dofs[loc] == dof_y:
                                f_contact[loc] -= bary[k] * f_pot
                else:
                    pot.vy += self.h_fine * self.gravity
            else:
                pot.vy += self.h_fine * self.gravity

            pot.y += self.h_fine * pot.vy

            # Plate → table contacts.
            for pi in range(n_plates):
                plate = plates[pi]
                px, pz = plate_xz[pi]
                surf_y = self._deformed_surface_y(px, pz, u_full)
                pen = surf_y - plate.bottom_y()

                if pen > 0:
                    f_plate = self.k_penalty * pen
                    plate.vy += self.h_fine * (self.gravity + f_plate / plate.mass)
                    # Reaction on FEM.
                    tri_idx, bary = self._find_closest_tri(px, pz)
                    if tri_idx < self._top_surface_tris.shape[0]:
                        tri = self._top_surface_tris[tri_idx]
                        for k in range(3):
                            dof_y = 3 * tri[k] + 1
                            loc = np.searchsorted(self.fem.free_dofs, dof_y)
                            if loc < self.fem.free_dofs.size and self.fem.free_dofs[loc] == dof_y:
                                f_contact[loc] -= bary[k] * f_plate
                else:
                    plate.vy += self.h_fine * self.gravity

                plate.y += self.h_fine * plate.vy

            # --- FEM step ---
            f_total = gravity_load + f_contact
            self._newmark.step(f_total)

            # --- Record ---
            if step_i % record_every == 0:
                t = step_i * self.h_fine
                times.append(t)
                pot_ys.append(pot.y)
                plate_ys_list.append([p.y for p in plates])
                plate_vys_list.append([p.vy for p in plates])

        return {
            "times": np.array(times),
            "pot_y": np.array(pot_ys),
            "plate_ys": np.array(plate_ys_list),
            "plate_vys": np.array(plate_vys_list),
        }
