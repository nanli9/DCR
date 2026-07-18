"""Shared constraint API for the two native solvers (AVBD + XPBD).

This module defines the ONE symmetric interface that both `SolverAVBD`
(Augmented-Lagrangian) and `SolverXPBD` (compliant position-based) consume, so
scenes are solver-agnostic and there is **no coupler**. Each physical
interaction is described once, solver-agnostically, and projected by whichever
backend the scene selected:

    description           AVBD backend (AL, §3.3)        XPBD backend (Macklin 2016)
    -----------           ----------------------         ---------------------------
    BoxBody               rigid DOF + box inertia        same rigid DOF
    FloorContact          AL contact f=clamp(cC+λ,..)    compliant unilateral α=c/h²
    SelfCollision         colored box-box AL primal      compliant box-box GS
    ModalSupport          augmented q-block              per-mode α_i = 1/K_q[i,i]
    SupportContactCorner  SUPPORT_CONTACT row            unilateral row y_rest+U_y·q
    Cargo                 augmented a-block              per-mode / abd compliant

The contact GEOMETRY (the SAT 15-axis + Sutherland-Hodgman face-clip manifold
in `kernels_6dof.py`) is shared between the two solvers; only the per-constraint
*projection* differs. Geometry produces contact points / normals / tangents
independent of how they are solved.

Spec
----
* `two_band_coupling.html` (Approach B) — the reduced-modal support / cargo
  contact constraint both backends realize.
* Macklin et al. 2016, "XPBD: Position-Based Simulation of Compliant Constrained
  Dynamics" (+ §3.5 damping) — the XPBD backend.
* AVBD §3.3 (Augmented Lagrangian) — the AVBD backend.
* Plan: `prompts/native_dual_solver_build_plan.md` (Stage 0 — this interface).

The constraint descriptions below are the solver-agnostic records; the `Solver`
Protocol is the common solver surface scenes call. `make_solver` resolves a
selection string to a concrete native solver. A `Solver` is structurally
checkable: a class satisfies it by having the listed methods/attributes — no
inheritance is required, so the validated `Solver6DOF` implementation is reused
verbatim (it already exposes this surface).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np

from .solver_6dof import RigidBody

__all__ = [
    "BoxBody",
    "FloorContact",
    "SelfCollision",
    "ModalSupport",
    "SupportContactCorner",
    "Cargo",
    "Solver",
    "make_solver",
]


# ---------------------------------------------------------------------------
# Solver-agnostic constraint / scene-element descriptions
# ---------------------------------------------------------------------------
# Each dataclass mirrors one `Solver` method's arguments so a scene can be
# expressed as a list of descriptions and replayed onto EITHER backend. The
# field names match the `Solver` method parameters one-to-one.


@dataclass
class BoxBody:
    """A rigid box body. `mass <= 0` marks a static body (both backends skip its
    inertial predictor). `orientation` is a quaternion in XYZW order
    (Warp's wp.quat convention); identity = (0, 0, 0, 1)."""

    position: tuple[float, float, float]
    half_extents: tuple[float, float, float]
    mass: float
    orientation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    friction: float = 0.0


@dataclass
class FloorContact:
    """Box↔floor contact: the 8 corners of `body` rest on the plane y = floor_y
    with Coulomb friction μ. AVBD: 8 unilateral AL rows + tangent friction rows
    (f = clamp(c·C + λ, ±μ|λ_n|)). XPBD: 8 compliant unilateral constraints
    (α = compliance/h², λ ≥ 0) with positional Coulomb friction."""

    body: int  # RigidBody.index
    floor_y: float = 0.0
    friction: float | None = None  # None ⇒ use the body's own μ
    stiffness: float = math.inf


@dataclass
class SelfCollision:
    """Enable body↔body OBB-OBB contact. The SAT/face-clip manifold geometry is
    shared; AVBD projects each manifold point as a colored AL contact, XPBD as a
    compliant unilateral constraint in the same GS sweep."""

    enabled: bool = True
    default_friction: float = 0.0


@dataclass
class ModalSupport:
    """The reduced-modal support amplitude q ∈ ℝ^r as native solver DOF
    (two_band_coupling.html — "The two kinds of unknowns"). Mass-normalized modes
    give M_q = I, K_q = diag(ω²); D_q is the Rayleigh modal damping. AVBD solves
    q in the augmented q-block of the same implicit step; XPBD projects each mode
    as a compliant constraint with compliance α_i = 1/K_q[i,i] and the Macklin
    §3.5 damped update using D_q[i,i]."""

    Mq: np.ndarray
    Kq: np.ndarray
    Dq: np.ndarray
    q0: np.ndarray | None = None
    qdot0: np.ndarray | None = None
    f_q_grav: np.ndarray | None = None


@dataclass
class SupportContactCorner:
    """A unilateral support-contact row: body corner `off_a` rests on the LIVE
    modal surface y_rest + U_y·q (foundation "Contact as a constraint on (z, q)").
    `U_y_row` is the (r,) mode shape sampled where the corner touches; the surface
    height is evaluated against the live q in-solve (no pre-baked anchor)."""

    body: int  # RigidBody.index
    off_a: tuple[float, float, float]
    y_rest: float
    U_y_row: np.ndarray
    stiffness: float = 1.0e9


@dataclass
class Cargo:
    """A deformable cargo cube whose elastic block joins the augmented modal
    vector Q = [q_support; …; a_cargo] (two_band_coupling.html — M2). `cargo_body`
    exposes the uniform cargo interface (Mq_block/Kq_block/Dq_block k×k,
    corner_modal (P,3,k) = Φ_c, corotate). `support_rows` maps each of the cube's
    SUPPORT_CONTACT slots to its corner pid `(slot, pid)`. Material k=0 (rigid) /
    fem_rigid / fem / abd. AVBD: augmented a-block. XPBD: per-mode compliant
    (or, for abd's nonlinear V⊥, re-linearized compliant constraints)."""

    body: int  # RigidBody.index
    cargo_body: object  # FEMRigidModalBody | ABDAffineBody
    support_rows: list[tuple[int, int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The common solver interface
# ---------------------------------------------------------------------------


@runtime_checkable
class Solver(Protocol):
    """The scene-facing surface both native solvers expose. A scene builds a
    solver via `make_solver`, adds bodies/floor/modal-support/cargo through these
    methods, and reads state back — identically for AVBD and XPBD, with no
    coupler indirection.

    Method signatures mirror the validated `Solver6DOF` AVBD implementation so it
    satisfies this Protocol verbatim; `SolverXPBD` re-implements the same surface
    with the XPBD projection backend. `runtime_checkable` checks member presence
    (not signatures), which is enough for the scene-selection seam.
    """

    # -- scene building -----------------------------------------------------
    def add_box(
        self,
        position: tuple[float, float, float],
        half_extents: tuple[float, float, float],
        mass: float,
        orientation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
        velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
        angular_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
        friction: float = 0.0,
    ) -> RigidBody: ...

    def add_floor_contact_box(
        self,
        body: RigidBody,
        floor_y: float = 0.0,
        friction: float | None = None,
        stiffness: float = math.inf,
    ) -> list[int]: ...

    def enable_self_collision(
        self, enabled: bool = True, default_friction: float = 0.0
    ) -> None: ...

    # -- reduced-modal support ---------------------------------------------
    def set_modal_support(
        self,
        Mq: np.ndarray,
        Kq: np.ndarray,
        Dq: np.ndarray,
        *,
        q0: np.ndarray | None = None,
        qdot0: np.ndarray | None = None,
        f_q_grav: np.ndarray | None = None,
    ) -> None: ...

    def add_support_contact_corner(
        self,
        body: RigidBody,
        off_a: tuple[float, float, float],
        y_rest: float,
        U_y_row: np.ndarray,
        stiffness: float = 1.0e9,
    ) -> int: ...

    # -- cargo --------------------------------------------------------------
    def add_cargo(
        self, body, cargo_body, support_rows: list[tuple[int, int]]
    ) -> None: ...

    # -- stepping -----------------------------------------------------------
    def step(self) -> None: ...

    # -- state read-back ----------------------------------------------------
    def positions(self) -> np.ndarray: ...
    def orientations(self) -> np.ndarray: ...
    def velocities(self) -> np.ndarray: ...
    def angular_velocities(self) -> np.ndarray: ...
    def cargo_a(self, body_idx: int) -> np.ndarray: ...
    def cargo_adot(self, body_idx: int) -> np.ndarray: ...

    @property
    def modal_q(self) -> np.ndarray | None: ...
    @property
    def modal_qdot(self) -> np.ndarray | None: ...


# ---------------------------------------------------------------------------
# Solver selection
# ---------------------------------------------------------------------------

_SOLVER_KINDS = ("avbd", "xpbd", "impulse")


def make_solver(kind: str, /, **kwargs) -> Solver:
    """Resolve a solver-selection string to a native solver instance. Scenes use
    this so the SAME scene runs on either backend with no coupler:

        solver = make_solver("avbd", device="cuda:0", iterations=8, substeps=4)
        solver = make_solver("xpbd", device="cuda:0", iterations=8, substeps=4)

    `kwargs` are forwarded to the solver constructor. Imports are deferred to
    avoid an import cycle (the solver modules import this one)."""
    k = str(kind).lower()
    if k == "avbd":
        from .solver_avbd import SolverAVBD

        return SolverAVBD(**kwargs)
    if k == "xpbd":
        from .solver_xpbd import SolverXPBD

        return SolverXPBD(**kwargs)
    if k == "impulse":
        from .solver_impulse import SolverImpulse

        return SolverImpulse(**kwargs)
    raise ValueError(
        f"unknown solver kind {kind!r} (expected one of {_SOLVER_KINDS})"
    )
