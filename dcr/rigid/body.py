"""Rigid body data structures.

Conventions (paper §3, CLAUDE.md):
  - Generalized velocity: v = [v_lin (3); omega (3)]
  - Quaternion: (w, x, y, z)
  - Units: SI (m, kg, s, N)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np
from numpy.typing import NDArray


class ShapeType(Enum):
    BOX = auto()
    SPHERE = auto()
    PLANE = auto()


@dataclass
class Shape:
    """Collision shape attached to a rigid body."""
    kind: ShapeType
    # BOX: half_extents (3,)
    # SPHERE: half_extents[0] = radius
    # PLANE: normal (3,) stored in half_extents[:3], offset in half_extents[3] (unused — plane uses body pos)
    half_extents: NDArray[np.float64] = field(default_factory=lambda: np.zeros(3))


def box_shape(hx: float, hy: float, hz: float) -> Shape:
    return Shape(kind=ShapeType.BOX, half_extents=np.array([hx, hy, hz]))


def sphere_shape(radius: float) -> Shape:
    return Shape(kind=ShapeType.SPHERE, half_extents=np.array([radius, 0.0, 0.0]))


def plane_shape(normal: tuple[float, float, float] = (0.0, 1.0, 0.0)) -> Shape:
    """Infinite plane. Position of the body gives the point on the plane."""
    n = np.array(normal, dtype=np.float64)
    n /= np.linalg.norm(n)
    return Shape(kind=ShapeType.PLANE, half_extents=n)


# ---------- Quaternion helpers ----------

def quat_identity() -> NDArray[np.float64]:
    """Return identity quaternion (w, x, y, z)."""
    return np.array([1.0, 0.0, 0.0, 0.0])


def quat_to_rot(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert unit quaternion (w,x,y,z) to 3x3 rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - z*w),     2*(x*z + y*w)],
        [    2*(x*y + z*w), 1 - 2*(x*x + z*z),     2*(y*z - x*w)],
        [    2*(x*z - y*w),     2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


def quat_multiply(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Hamilton product of two quaternions (w,x,y,z)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return np.array([
        aw*bw - ax*bx - ay*by - az*bz,
        aw*bx + ax*bw + ay*bz - az*by,
        aw*by - ax*bz + ay*bw + az*bx,
        aw*bz + ax*by - ay*bx + az*bw,
    ])


def quat_integrate(q: NDArray[np.float64], omega: NDArray[np.float64],
                   dt: float) -> NDArray[np.float64]:
    """Symplectic Euler quaternion update: q+ = normalize(q + 0.5*dt * Omega(omega) * q).

    Omega(omega) * q is the quaternion product [0, omega] * q.
    """
    omega_quat = np.array([0.0, omega[0], omega[1], omega[2]])
    dq = 0.5 * dt * quat_multiply(omega_quat, q)
    q_new = q + dq
    norm = np.linalg.norm(q_new)
    if norm > 1e-12:
        q_new /= norm
    return q_new


# ---------- Rigid body ----------

@dataclass
class RigidBody:
    """A single rigid body in the simulation.

    Attributes:
        mass: scalar mass (inf for static bodies).
        inertia_body: (3,) principal moments of inertia in body frame.
        position: (3,) center of mass in world frame.
        orientation: (4,) unit quaternion (w, x, y, z).
        velocity: (6,) generalized velocity [v_lin (3); omega (3)].
        force: (6,) accumulated generalized force [f_lin (3); tau (3)].
        shape: collision shape.
        is_static: if True, body has infinite mass and does not move.
        restitution: coefficient of restitution (eps_r). Paper default 0.15.
        friction: coefficient of friction (mu). Default 0.5.
    """
    mass: float = 1.0
    inertia_body: NDArray[np.float64] = field(
        default_factory=lambda: np.ones(3))
    position: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(3))
    orientation: NDArray[np.float64] = field(
        default_factory=quat_identity)
    velocity: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(6))
    force: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(6))
    shape: Shape = field(default_factory=lambda: box_shape(0.5, 0.5, 0.5))
    is_static: bool = False
    restitution: float = 0.15
    friction: float = 0.5
    collision_bounds: tuple[float, float] | None = None
    """Optional (half_x, half_z) for plane shapes. Contacts outside are rejected."""

    def rotation_matrix(self) -> NDArray[np.float64]:
        """Current 3x3 rotation matrix (body → world)."""
        return quat_to_rot(self.orientation)

    def inertia_world(self) -> NDArray[np.float64]:
        """3x3 inertia tensor in world frame: R * diag(I_body) * R^T."""
        R = self.rotation_matrix()
        return R @ np.diag(self.inertia_body) @ R.T

    def inertia_world_inv(self) -> NDArray[np.float64]:
        """Inverse of world-frame inertia tensor."""
        R = self.rotation_matrix()
        return R @ np.diag(1.0 / self.inertia_body) @ R.T

    def mass_matrix_inv(self) -> NDArray[np.float64]:
        """6x6 inverse mass matrix: diag(1/m * I_3, I_world_inv)."""
        M_inv = np.zeros((6, 6))
        M_inv[0:3, 0:3] = (1.0 / self.mass) * np.eye(3)
        M_inv[3:6, 3:6] = self.inertia_world_inv()
        return M_inv

    def mass_matrix(self) -> NDArray[np.float64]:
        """6x6 mass matrix: diag(m * I_3, I_world)."""
        M = np.zeros((6, 6))
        M[0:3, 0:3] = self.mass * np.eye(3)
        M[3:6, 3:6] = self.inertia_world()
        return M


def compute_box_inertia(mass: float, hx: float, hy: float, hz: float) -> NDArray[np.float64]:
    """Principal moments for a solid box with half-extents (hx, hy, hz)."""
    sx, sy, sz = (2*hx)**2, (2*hy)**2, (2*hz)**2
    return np.array([
        mass / 12.0 * (sy + sz),
        mass / 12.0 * (sx + sz),
        mass / 12.0 * (sx + sy),
    ])


def compute_sphere_inertia(mass: float, radius: float) -> NDArray[np.float64]:
    """Principal moments for a solid sphere."""
    I = 0.4 * mass * radius**2
    return np.array([I, I, I])


def make_dynamic_box(mass: float, hx: float, hy: float, hz: float,
                     position: tuple[float, float, float] = (0, 0, 0),
                     restitution: float = 0.15,
                     friction: float = 0.5) -> RigidBody:
    """Convenience: create a dynamic box rigid body."""
    return RigidBody(
        mass=mass,
        inertia_body=compute_box_inertia(mass, hx, hy, hz),
        position=np.array(position, dtype=np.float64),
        orientation=quat_identity(),
        velocity=np.zeros(6),
        force=np.zeros(6),
        shape=box_shape(hx, hy, hz),
        is_static=False,
        restitution=restitution,
        friction=friction,
    )


def make_dynamic_sphere(mass: float, radius: float,
                        position: tuple[float, float, float] = (0, 0, 0),
                        restitution: float = 0.15,
                        friction: float = 0.5) -> RigidBody:
    """Convenience: create a dynamic sphere rigid body."""
    return RigidBody(
        mass=mass,
        inertia_body=compute_sphere_inertia(mass, radius),
        position=np.array(position, dtype=np.float64),
        orientation=quat_identity(),
        velocity=np.zeros(6),
        force=np.zeros(6),
        shape=sphere_shape(radius),
        is_static=False,
        restitution=restitution,
        friction=friction,
    )


def make_static_plane(normal: tuple[float, float, float] = (0, 1, 0),
                      point: tuple[float, float, float] = (0, 0, 0),
                      friction: float = 0.5,
                      bounds: tuple[float, float] | None = None) -> RigidBody:
    """Convenience: create a static plane.

    Args:
        bounds: Optional (half_x, half_z) finite extent centered at *point*.
    """
    return RigidBody(
        mass=1e30,  # effectively infinite
        inertia_body=np.array([1e30, 1e30, 1e30]),
        position=np.array(point, dtype=np.float64),
        orientation=quat_identity(),
        velocity=np.zeros(6),
        force=np.zeros(6),
        shape=plane_shape(normal),
        is_static=True,
        restitution=0.0,
        friction=friction,
        collision_bounds=bounds,
    )
