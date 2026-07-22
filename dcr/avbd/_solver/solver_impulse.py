"""Velocity-impulse native solver: the main-branch Schur+PGS rigid solver
(paper Eq. 2/3) with the native dynamic modal constraint as EXTRA COLUMNS.

This is the THIRD backend behind `make_solver` ("impulse"), next to SolverAVBD
(augmented Lagrangian) and SolverXPBD (compliant position-based). Both existing
backends realize the two-way row of docs/07_17_report/contact_forces.html inside
formulations that descend from deformable simulation. This backend realizes the
SAME row — same formulation, same gap function — inside the classical
velocity-level impulse solver of the DCR paper (dcr/rigid/solver.py, Eq. 2/3),
the way ABD adds affine DOFs: the modal amplitudes are extra solver unknowns.

The row (report, "The method in three lines"):

    1)  p = x + R (r + Φ·a)                       # deformed contact point
    2)  0 ≤ C_rigid + Ĝ_A·a_A − Ĝ_B·a_B  ⊥  λ ≥ 0 # one shared unilateral row
    3)  rigid: ±Jᵀλ    modes: +Ĝ_Aᵀλ, −Ĝ_Bᵀλ      # same λ routed to every DOF

with Ĝ_X = n̂ᵀ R_X Φ_X — one number per mode. At the velocity level this means
the contact Jacobian row gains modal columns and the Schur complement (paper
Eq. 2) gains the modal block:

    A = (1/h²)·cfm·I + J M⁻¹ Jᵀ + Ĝ W_eff Ĝᵀ
    b = −(erp/h)·φ − (J·v_free + Ĝ·ȧ_free)
    φ = φ_rigid + Ĝ_A·a_A − Ĝ_B·a_B               # the deformed-surface gap

solved by the SAME Projected Gauss-Seidel with λ_N ≥ 0 (paper Eq. 3, BLCP with
boxed friction), and the solved impulse distributed to every DOF the row touches:
Δv = M⁻¹Jᵀλ (rigid), Δȧ = W_eff·Ĝᵀλ (modes).

W_eff is the per-mode effective inverse inertia of the IMPLICITLY integrated
oscillator. Backward Euler on  M ä + D ȧ + K a = f  with an impulse P gives

    (M + h·D + h²·K) ȧ⁺ = M ȧ − h·K a + h·f + P
    ⇒  W_eff = (M + h·D + h²·K)⁻¹                # diag; the "M + hD + h²K" form

— the same effective mass the AVBD q-block assembles as H_q·h² (solver_6dof
`_solve_q_block`) and the reason stiff audio-adjacent modes cannot destabilize
the co-solve: for h²ω² ≫ 1, W_eff → 0 and the mode simply refuses impulse.

Design rules carried over from the two production backends (see the exploration
of solver_6dof.py / solver_xpbd.py):

  * Friction rows are RIGID-ONLY — the modal columns live on the normal row
    exclusively, matching both existing backends (the slab's q̇ motion is normal).
  * The support slab does not co-rotate and its basis has only a y-component, so
    Ĝ_support ≡ U_y sampled at the corner (∂C/∂q = −U_y on the body's row).
  * Cargo Ĝ_a = n̂ᵀ·R·Φ_c[pid] is frozen once per substep (like AVBD's
    `_cargo_freeze_and_W`), with pid by nearest-rest-corner snap.
  * The §15 passivity ledger (passivity.py) is shared verbatim and applied
    GLOBALLY across support + all cargo blocks, per substep.
  * SUPPORT rows carry the FULL native columns (gap + velocity map + Delassus)
    — the report's two-way headline (sag, detune, damping), stable here.
    BOX-BOX rows default to the SHIPPED AVBD semantics (`_modal_contact_ride`
    off): the row solves rigid-only and the shared λ drives both cubes' modes
    open-loop (+Ĝ_Aᵀλ / −Ĝ_Bᵀλ). The full monolithic box-box row (columns in
    the rigid gap too) is `_modal_contact_ride = True`, opt-in because the
    λ ≥ 0 clamp rectifies the ringing-surface oscillation into net torque on
    off-center stacks (measured here: the §N2 zig-zag tower ratchets ω_z and
    topples; AVBD gates + caps the same feature — `_bake_ride_crest`, N3).

# DEVIATION (paper Eq. 4): restitution is not applied (e = 0, perfectly
# inelastic) — both native backends resolve contacts inelastically and every
# native scene sets restitution 0; the Eq. 4 term would be the only consumer of
# contact `is_new` tracking, so it is omitted rather than carried dead.
# DEVIATION (report row): contact DETECTION (which rows are active) uses the
# rigid SAT/plane proximity with a small margin; the modal deformation enters
# the row's GAP φ and Jacobian, not the broad/narrow phase. The AVBD backend
# makes the same choice (SAT geometry is rigid; the q/a terms bias the gap).

CPU/numpy only — this is a reference formulation study (CLAUDE.md rule 6);
there is no device path and `device` other than "cpu" falls back with a warning.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .solver_6dof import RigidBody

__all__ = ["SolverImpulse"]


# ---------------------------------------------------------------------------
# Small math helpers (XYZW quaternions — the solver-side convention shared with
# SolverAVBD/SolverXPBD; the world converts from the DCR-facing WXYZ).
# ---------------------------------------------------------------------------


def _quat_to_R(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """XYZW unit quaternion → 3×3 rotation matrix."""
    x, y, z, w = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    n = w * w + x * x + y * y + z * z
    if n < 1e-30:
        return np.eye(3)
    s = 2.0 / n
    return np.array([
        [1.0 - s * (y * y + z * z), s * (x * y - w * z),       s * (x * z + w * y)],
        [s * (x * y + w * z),       1.0 - s * (x * x + z * z), s * (y * z - w * x)],
        [s * (x * z - w * y),       s * (y * z + w * x),       1.0 - s * (x * x + y * y)],
    ])


def _quat_integrate_xyzw(q: NDArray[np.float64], omega: NDArray[np.float64],
                         h: float) -> NDArray[np.float64]:
    """Symplectic Euler quaternion update q⁺ = normalize(q + h/2·[ω,0]·q)
    (same update as dcr/rigid/body.py:quat_integrate, XYZW storage)."""
    ox, oy, oz = float(omega[0]), float(omega[1]), float(omega[2])
    x, y, z, w = q
    # Hamilton product [ω,0] ⊗ q in XYZW components.
    dx = 0.5 * h * (ox * w + oy * z - oz * y)
    dy = 0.5 * h * (-ox * z + oy * w + oz * x)
    dz = 0.5 * h * (ox * y - oy * x + oz * w)
    dw = 0.5 * h * (-ox * x - oy * y - oz * z)
    out = np.array([x + dx, y + dy, z + dz, w + dw])
    nrm = float(np.linalg.norm(out))
    if nrm > 1e-12:
        out /= nrm
    return out


def _box_inv_inertia_local(mass: float, hx: float, hy: float,
                           hz: float) -> NDArray[np.float64]:
    """Inverse body-local inertia of a solid box (paper convention m/12·diag)."""
    if mass <= 0.0:
        return np.zeros((3, 3))
    sx, sy, sz = (2 * hx) ** 2, (2 * hy) ** 2, (2 * hz) ** 2
    I = np.array([mass / 12.0 * (sy + sz),
                  mass / 12.0 * (sx + sz),
                  mass / 12.0 * (sx + sy)])
    return np.diag(1.0 / I)


_CORNER_SIGNS = np.array([
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
], dtype=np.float64)


# ---------------------------------------------------------------------------
# Row records
# ---------------------------------------------------------------------------

# DOF-block keys: int i → rigid body i (6 dofs); "q" → the support modal block;
# ("a", bi) → cargo body bi's modal block. Each constraint row is a list of
# (block_key, jacobian_vector) pairs — the generalized-coordinate version of
# main's per-row (body_a, J_a, body_b, J_b) blocks (dcr/rigid/solver.py).


@dataclass
class _Row:
    blocks: list[tuple[object, NDArray[np.float64]]]
    phi: float                     # signed gap (negative = penetrating)
    lo: float = 0.0
    hi: float = math.inf
    friction_of: int = -1          # index of my normal row (friction rows only)
    mu: float = 0.0
    key: tuple = ()                # warm-start key
    # Open-loop modal kicks (box-box network default): blocks that receive
    # W_eff·g·λ at distribution but do NOT enter A/b — the velocity-level
    # translation of the AVBD default where the primal box-box row is rigid
    # and the shared multiplier drives the modes in the q-block.
    kick_blocks: list[tuple[object, NDArray[np.float64]]] = field(
        default_factory=list)


class _SupportContact:
    """One registered support-corner row (mirrors SolverXPBD._SupportContact so
    AVBDDCRWorld's xpbd-style wiring branch works unchanged for this backend):
    body corner `off` (body-local) rests on the live surface y_rest + U_y·q."""

    __slots__ = ("bi", "off", "y_rest", "U_y", "mu", "cargo_bi", "pid")

    def __init__(self, bi, off, y_rest, U_y, mu=0.0):
        self.bi = int(bi)
        self.off = np.asarray(off, dtype=np.float64)
        self.y_rest = float(y_rest)
        self.U_y = np.asarray(U_y, dtype=np.float64).reshape(-1)
        self.mu = float(mu)
        self.cargo_bi = -1
        self.pid = -1


class SolverImpulse:
    """Velocity-impulse (Schur+PGS) backend implementing the shared
    `constraints.Solver` surface. See the module docstring for the math."""

    def __init__(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 10,
        gravity: tuple[float, float, float] = (0.0, -9.81, 0.0),
        substeps: int = 1,
        device: str = "cpu",
        cfm: float = 1.0e-6,
        erp: float = 0.2,
        contact_margin: float = 1.0e-3,
        **_ignored,
    ) -> None:
        # _ignored swallows backend-specific kwargs (AVBD's AL schedule, XPBD's
        # compliance, post_stabilize, …) so make_solver("impulse", **kwargs) is
        # a drop-in for either.
        self.dt = float(dt)
        self.iterations = int(iterations)       # PGS iterations per substep
        self.substeps = max(1, int(substeps))
        self.gravity = np.asarray(gravity, dtype=np.float64)
        if str(device) != "cpu":
            import warnings
            warnings.warn("SolverImpulse is CPU-only; ignoring device="
                          f"{device!r} (reference formulation study)")
        self.device = "cpu"
        # DEVIATION (paper Eq. 2): the paper's (1/h²)·cfm is timestep-dependent;
        # like dcr/rigid/solver.py we store cfm at h_ref = 1e-2 and scale so the
        # effective regularization is timestep-invariant.
        self._cfm_ref = float(cfm)
        self._h_ref = 1e-2
        self.erp = float(erp)
        self.contact_margin = float(contact_margin)

        # Host accumulation (add_box); finalized into numpy state on first step.
        self._pos: list[list[float]] = []
        self._ori: list[list[float]] = []
        self._vel: list[list[float]] = []
        self._ang: list[list[float]] = []
        self._mass: list[float] = []
        self._he: list[tuple[float, float, float]] = []
        self._mu: list[float] = []
        self._dirty = True

        # Live numpy state (built by _ensure_arrays).
        self._X: NDArray[np.float64] | None = None   # (n,3) positions
        self._Q: NDArray[np.float64] | None = None   # (n,4) XYZW orientations
        self._V: NDArray[np.float64] | None = None   # (n,3) linear velocity
        self._W: NDArray[np.float64] | None = None   # (n,3) angular velocity
        self._invm: NDArray[np.float64] | None = None    # (n,)
        self._invIl: NDArray[np.float64] | None = None   # (n,3,3) local I⁻¹
        self._hE: NDArray[np.float64] | None = None      # (n,3)

        # Floor registrations: (body_idx, floor_y, mu) — name-compatible with
        # SolverXPBD so AVBDDCRWorld.enable_reduced_modal_support can strip the
        # tracked bodies' floors identically.
        self._floors: list[tuple[int, float, float]] = []
        self._self_collide = False
        self._self_friction = 0.0
        self._last_max_penetration = 0.0

        # Reduced-modal support: q ∈ R^r as native solver DOF.
        self._modal = False
        self._modal_enabled = False      # AVBD-name alias, kept in sync
        self._r = 0
        self._mq = self._kq = self._dq = None    # (r,) diagonals
        self._q = self._qdot = None
        self._modal_grav_force = None            # (r,) f_q^grav
        self._freeze_qdot = False
        self._support: list[_SupportContact] = []
        self.last_modal_KE = 0.0
        self.last_modal_PE = 0.0

        # Cargo: per-body modal blocks a ∈ R^k (uniform cargo interface).
        self._cargo: dict = {}          # body_idx -> cargo body model
        self._cargo_a: dict = {}        # body_idx -> (k,) amplitudes
        self._cargo_adot: dict = {}     # body_idx -> (k,) rates
        self._cargo_mq: dict = {}       # body_idx -> (k,) diag M
        self._cargo_kq: dict = {}       # body_idx -> (k,) diag K
        self._cargo_dq: dict = {}       # body_idx -> (k,) diag D
        self._modal_contact_network = False   # box-box rows carry Ĝ columns
        self._modal_contact_ride = False      # accepted, no-op (AVBD N3 feature)

        # §15 passivity (passivity.py — shared with both native backends).
        self._enforce_modal_passivity = False   # behaviour-neutral default
        self._psv_monitor_only = False
        # Gap-preserving projection (opt-in; see SolverXPBD for the rationale).
        self._psv_gap_preserving = False
        self._psv_gap_margin = 0.0
        self._psv_gap_info: dict | None = None
        self._modal_eta = 1.0
        self._psv_ledger = None
        self._psv_Il = None

        # Warm-start cache: row key -> λ (paper Eq. 3 PGS warm start, same idea
        # as dcr/rigid/solver.py `_prev_lambda`).
        self._lam_cache: dict[tuple, float] = {}

        # Interface-parity attributes read by AVBDDCRWorld / the viser script.
        self.x = None                    # warp-array slot: None ⇒ CPU backend
        self._graph = None
        # Optional demo hook called at each substep start (payload A/B one-way
        # ride uses it to move the uncoupled payload's floor to the live
        # surface). Never used by the solver itself.
        self.substep_begin_hook = None
        self.hooks_device_resident = False
        self.modal_relax = 1.0           # implicit W_eff needs no under-relaxation
        self._support_block_relax = 1.0
        self._modal_symplectic = False
        self._modal_device_resident = False

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
    ) -> RigidBody:
        """Add a rigid box. `mass ≤ 0` marks a static body (inverse mass 0)."""
        idx = len(self._pos)
        self._pos.append([float(v) for v in position])
        self._ori.append([float(v) for v in orientation])
        self._vel.append([float(v) for v in velocity])
        self._ang.append([float(v) for v in angular_velocity])
        self._mass.append(float(mass))
        hx, hy, hz = (float(half_extents[0]), float(half_extents[1]),
                      float(half_extents[2]))
        self._he.append((hx, hy, hz))
        self._mu.append(max(0.0, float(friction)))
        self._dirty = True
        return RigidBody(index=idx, half_extents=(hx, hy, hz))

    def add_floor_contact_box(
        self,
        body: RigidBody,
        floor_y: float = 0.0,
        friction: float | None = None,
        stiffness: float = math.inf,   # interface parity (impulse: exact rows)
    ) -> list[int]:
        """Register the box's 8 corners against the plane y = floor_y (paper
        box-plane contact; unilateral rows with boxed Coulomb friction)."""
        bi = int(body.index)
        mu = float(friction) if friction is not None else self._mu[bi]
        self._floors.append((bi, float(floor_y), mu))
        return [bi]

    def enable_self_collision(self, enabled: bool = True,
                              default_friction: float = 0.0) -> None:
        """Enable box↔box contact (main-branch SAT, dcr/rigid/collision.py)."""
        self._self_collide = bool(enabled)
        self._self_friction = float(default_friction)

    # -- reduced-modal support ----------------------------------------------

    def set_modal_support(
        self,
        Mq: np.ndarray,
        Kq: np.ndarray,
        Dq: np.ndarray,
        *,
        q0: np.ndarray | None = None,
        qdot0: np.ndarray | None = None,
        f_q_grav: np.ndarray | None = None,
    ) -> None:
        """Install the support's modal amplitude q ∈ ℝ^r as a native solver DOF.
        Mass-normalized modes ⇒ M_q = I, K_q = diag(ω²), D_q Rayleigh. The
        contact rows read/write q through the −U_y columns (report §1); q itself
        integrates implicitly (module docstring W_eff derivation)."""
        Mq = np.asarray(Mq, dtype=np.float64)
        Kq = np.asarray(Kq, dtype=np.float64)
        Dq = np.asarray(Dq, dtype=np.float64)
        r = int(Mq.shape[0])
        self._r = r
        self._mq = np.diag(Mq).copy() if Mq.ndim == 2 else Mq.copy()
        self._kq = np.diag(Kq).copy() if Kq.ndim == 2 else Kq.copy()
        self._dq = np.diag(Dq).copy() if Dq.ndim == 2 else Dq.copy()
        self._q = (np.zeros(r) if q0 is None
                   else np.asarray(q0, dtype=np.float64).copy())
        self._qdot = (np.zeros(r) if qdot0 is None
                      else np.asarray(qdot0, dtype=np.float64).copy())
        self._modal_grav_force = (np.zeros(r) if f_q_grav is None
                                  else np.asarray(f_q_grav, dtype=np.float64).copy())
        self._modal = True
        self._modal_enabled = True
        from .passivity import PassivityLedger
        self._psv_ledger = PassivityLedger(eta=float(self._modal_eta))

    def add_support_contact_corner(
        self,
        body: RigidBody,
        off_a: tuple[float, float, float],
        y_rest: float,
        U_y_row: np.ndarray,
        stiffness: float = 1.0e9,     # interface parity (impulse: exact rows)
        friction: float = 0.0,
    ) -> int:
        """Register one unilateral support-contact row: body corner `off_a`
        rests on the live modal surface y_rest + U_y·q; the row's gap and
        Jacobian carry ∂C/∂q = −U_y (report §1). Returns the slot index."""
        idx = len(self._support)
        self._support.append(_SupportContact(
            int(body.index) if hasattr(body, "index") else int(body),
            off_a, y_rest, U_y_row, mu=friction))
        return idx

    # -- cargo ---------------------------------------------------------------

    def add_cargo(self, body, cargo_body,
                  support_rows: list[tuple[int, int]]) -> None:
        """Register a deformable cargo body: its elastic a ∈ R^k becomes a
        native DOF block whose columns Ĝ_a = n̂ᵀ·R·Φ_c[pid] join every contact
        row the body participates in (support rows via `support_rows`
        (slot, pid) mapping; box-box rows via the modal contact network)."""
        if not self._modal:
            raise RuntimeError("add_cargo requires set_modal_support first")
        if getattr(cargo_body, "has_nonlinear_internal", False):
            raise NotImplementedError(
                "SolverImpulse does not support abd cargo (nonlinear V⊥); "
                "use the avbd backend for abd cubes.")
        bi = int(body.index) if hasattr(body, "index") else int(body)
        Mq = np.asarray(cargo_body.Mq_block, dtype=np.float64)
        Kq = np.asarray(cargo_body.Kq_block, dtype=np.float64)
        Dq = np.asarray(cargo_body.Dq_block, dtype=np.float64)
        k = int(Mq.shape[0])
        self._cargo[bi] = cargo_body
        self._cargo_a[bi] = np.zeros(k)
        self._cargo_adot[bi] = np.zeros(k)
        self._cargo_mq[bi] = np.diag(Mq).copy() if Mq.ndim == 2 else Mq.copy()
        self._cargo_kq[bi] = np.diag(Kq).copy() if Kq.ndim == 2 else Kq.copy()
        self._cargo_dq[bi] = np.diag(Dq).copy() if Dq.ndim == 2 else Dq.copy()
        for slot, pid in support_rows:
            self._support[slot].cargo_bi = bi
            self._support[slot].pid = int(pid)

    # AVBD-name alias (the AVBD backend exposes add_cargo_native); accept both.
    def add_cargo_native(self, body, cargo_body, support_rows) -> None:
        self.add_cargo(body, cargo_body, support_rows)

    # -- state finalization ---------------------------------------------------

    def _ensure_arrays(self) -> None:
        if not self._dirty:
            return
        n = len(self._pos)
        self._X = np.asarray(self._pos, dtype=np.float64).reshape(n, 3)
        self._Q = np.asarray(self._ori, dtype=np.float64).reshape(n, 4)
        self._V = np.asarray(self._vel, dtype=np.float64).reshape(n, 3)
        self._W = np.asarray(self._ang, dtype=np.float64).reshape(n, 3)
        invm = np.zeros(n)
        invIl = np.zeros((n, 3, 3))
        for i in range(n):
            m = self._mass[i]
            hx, hy, hz = self._he[i]
            invm[i] = 0.0 if m <= 0.0 else 1.0 / m
            invIl[i] = _box_inv_inertia_local(m, hx, hy, hz)
        self._invm = invm
        self._invIl = invIl
        self._hE = np.asarray(self._he, dtype=np.float64).reshape(n, 3)
        self._dirty = False

    # -- state read-back ------------------------------------------------------

    def positions(self) -> np.ndarray:
        self._ensure_arrays()
        return self._X.copy()

    def orientations(self) -> np.ndarray:
        self._ensure_arrays()
        return self._Q.copy()

    def velocities(self) -> np.ndarray:
        self._ensure_arrays()
        return self._V.copy()

    def angular_velocities(self) -> np.ndarray:
        self._ensure_arrays()
        return self._W.copy()

    def cargo_a(self, body_idx: int) -> np.ndarray:
        return self._cargo_a.get(int(body_idx), np.zeros(0)).copy()

    def cargo_adot(self, body_idx: int) -> np.ndarray:
        return self._cargo_adot.get(int(body_idx), np.zeros(0)).copy()

    @property
    def modal_q(self) -> np.ndarray | None:
        return None if self._q is None else self._q.copy()

    @property
    def modal_qdot(self) -> np.ndarray | None:
        return None if self._qdot is None else self._qdot.copy()

    @property
    def max_penetration(self) -> float:
        return self._last_max_penetration

    @property
    def _cargo_enabled(self) -> bool:
        return len(self._cargo) > 0

    # -- restore (viser reset) ------------------------------------------------

    def restore_from_descs(self, descs) -> None:
        """Write body poses/velocities back from the world's DCR-side mirror
        (AVBDDCRWorld.restore CPU branch) and rewind the modal state to rest.
        The DCR mirror stores WXYZ quaternions; we store XYZW."""
        self._ensure_arrays()
        for d in descs:
            if d.avbd_body is None:
                continue
            i = int(d.avbd_body.index)
            db = d.dcr_body
            self._X[i] = db.position
            w, qx, qy, qz = db.orientation
            self._Q[i] = (qx, qy, qz, w)
            self._V[i] = db.velocity[0:3]
            self._W[i] = db.velocity[3:6]
        if self._modal:
            self._q[:] = 0.0
            self._qdot[:] = 0.0
        for bi in self._cargo:
            self._cargo_a[bi][:] = 0.0
            self._cargo_adot[bi][:] = 0.0
        self._lam_cache.clear()
        if self._psv_ledger is not None:
            self._psv_ledger.reset()

    # -- stepping -------------------------------------------------------------

    def step(self) -> None:
        """One frame = `substeps` velocity-impulse solves at h = dt/substeps."""
        self._ensure_arrays()
        h = self.dt / self.substeps
        for _ in range(self.substeps):
            self._substep(h)

    # ---- contact collection --------------------------------------------------

    def _corners_world(self, i: int) -> NDArray[np.float64]:
        R = _quat_to_R(self._Q[i])
        return self._X[i] + (_CORNER_SIGNS * self._hE[i]) @ R.T

    def _box_box(self, i: int, j: int) -> list[tuple]:
        """Box-box SAT with face-normal bias — a direct port of the main-branch
        `dcr/rigid/collision.py:_detect_box_box` onto the solver's arrays.
        Returns (point, normal, penetration) tuples; the normal points from
        body j (B) toward body i (A), so J_A = +d convention holds."""
        margin = self.contact_margin
        Ra, Rb = _quat_to_R(self._Q[i]), _quat_to_R(self._Q[j])
        ha, hb = self._hE[i], self._hE[j]
        xa, xb = self._X[i], self._X[j]
        d = xb - xa
        axes_a = [Ra[:, k] for k in range(3)]
        axes_b = [Rb[:, k] for k in range(3)]

        def _overlap(axis):
            length = np.linalg.norm(axis)
            if length < 1e-10:
                return np.inf
            ax = axis / length
            pa = sum(ha[k] * abs(axes_a[k] @ ax) for k in range(3))
            pb = sum(hb[k] * abs(axes_b[k] @ ax) for k in range(3))
            return pa + pb - abs(d @ ax)

        def _orient(axis):
            n = axis / np.linalg.norm(axis)
            return -n if d @ n > 0 else n

        min_face, best_axis = np.inf, np.zeros(3)
        for ax in axes_a + axes_b:
            ov = _overlap(ax)
            if ov < -margin:
                return []
            if ov < min_face:
                min_face, best_axis = ov, _orient(ax)
        min_edge = np.inf
        for ka in range(3):
            for kb in range(3):
                ov = _overlap(np.cross(axes_a[ka], axes_b[kb]))
                if ov < -margin:
                    return []
                min_edge = min(min_edge, ov)
        normal = best_axis
        pen = max(0.0, min(min_face, min_edge))

        def _sd_to_face(p, x0, R, he, fn):
            local = R.T @ (p - x0)
            for ax in range(3):
                if abs(R[:, ax] @ fn) > 0.9:
                    continue
                if abs(local[ax]) > he[ax] + margin:
                    return np.inf
            return (p - x0) @ fn - sum(he[k] * abs(R[:, k] @ fn)
                                       for k in range(3))

        out = []
        for corner in self._corners_world(j):
            sd = _sd_to_face(corner, xa, Ra, ha, -normal)
            if sd < margin:
                cp = corner - normal * (sd * 0.5) if sd < 0 else corner
                out.append((cp, normal.copy(), pen))
        for corner in self._corners_world(i):
            sd = _sd_to_face(corner, xb, Rb, hb, normal)
            if sd < margin:
                cp = corner + normal * (sd * 0.5) if sd < 0 else corner
                out.append((cp, normal.copy(), pen))
        if not out:
            out.append((0.5 * (xa + xb), normal.copy(), pen))
        return out[:4]

    # ---- row assembly --------------------------------------------------------

    @staticmethod
    def _tangent_dirs(n: NDArray[np.float64]):
        if abs(n[1]) < 0.9:
            t1 = np.cross(n, [0.0, 1.0, 0.0])
        else:
            t1 = np.cross(n, [1.0, 0.0, 0.0])
        t1 /= np.linalg.norm(t1)
        t2 = np.cross(n, t1)
        return t1, t2 / np.linalg.norm(t2)

    def _rigid_jac(self, i: int, point: NDArray[np.float64],
                   direction: NDArray[np.float64], sign: float
                   ) -> NDArray[np.float64]:
        """1×6 rigid Jacobian block [±d; ±(r×d)] (dcr/rigid/solver.py
        `build_contact_jacobian_row`)."""
        J = np.zeros(6)
        J[0:3] = sign * direction
        J[3:6] = sign * np.cross(point - self._X[i], direction)
        return J

    def _cargo_G(self, bi: int, point: NDArray[np.float64],
                 normal: NDArray[np.float64],
                 R: NDArray[np.float64]) -> NDArray[np.float64] | None:
        """Ĝ_a = n̂ᵀ·R·Φ_c[pid] with pid by nearest-rest-corner snap (report §1;
        the AVBD `_build_net_rows` expression). None if bi carries no modes."""
        cb = self._cargo.get(bi)
        if cb is None:
            return None
        Phi = np.asarray(cb.corner_modal, dtype=np.float64)   # (P,3,k)
        if Phi.shape[2] == 0:
            return None
        local = R.T @ (point - self._X[bi])
        rest = np.asarray(cb.corner_body, dtype=np.float64)   # (P,3)
        pid = int(np.argmin(np.linalg.norm(rest - local, axis=1)))
        if getattr(cb, "corotate", True):
            return normal @ (R @ Phi[pid])                    # n̂ᵀ·R·Φ_c
        return normal @ Phi[pid]                              # fem: world-fixed

    def _collect_rows(self, h: float) -> list[_Row]:
        rows: list[_Row] = []
        margin = self.contact_margin
        n = self._X.shape[0]
        Rcache = [_quat_to_R(self._Q[i]) for i in range(n)]

        def _add_contact(blocks_n, phi, mu, key, point, dirs_bodies,
                         kicks=None):
            """One normal row + (if μ>0) two boxed friction rows (paper Eq. 3).
            `dirs_bodies` = [(body, sign), ...] for the rigid friction blocks;
            friction rows are RIGID-ONLY (no modal columns — see module doc).
            `kicks` = open-loop modal kick blocks on the normal row."""
            n_idx = len(rows)
            rows.append(_Row(blocks=blocks_n, phi=phi, lo=0.0, hi=math.inf,
                             key=key + (0,), kick_blocks=kicks or []))
            if mu > 0.0:
                nrm = blocks_n[0][1][0:3] if isinstance(blocks_n[0][0], int) else None
                # normal direction is the first rigid block's linear part
                for bkey, J in blocks_n:
                    if isinstance(bkey, int):
                        nrm = J[0:3] / max(np.linalg.norm(J[0:3]), 1e-12)
                        break
                t1, t2 = self._tangent_dirs(nrm)
                for ti, t in enumerate((t1, t2)):
                    fb = [(b, self._rigid_jac(b, point, t, s))
                          for b, s in dirs_bodies if self._invm[b] > 0.0]
                    if fb:
                        rows.append(_Row(blocks=fb, phi=0.0,
                                         lo=-math.inf, hi=math.inf,
                                         friction_of=n_idx, mu=mu,
                                         key=key + (1 + ti,)))

        # ---- floor rows (rigid-only; paper box-plane contact) ----------------
        for bi, floor_y, mu in self._floors:
            if self._invm[bi] == 0.0:
                continue
            corners = self._corners_world(bi)
            for ci, cw in enumerate(corners):
                gap = float(cw[1]) - floor_y
                if gap >= margin:
                    continue
                J = self._rigid_jac(bi, cw, np.array([0.0, 1.0, 0.0]), +1.0)
                _add_contact([(bi, J)], gap, mu, ("f", bi, ci), cw,
                             [(bi, +1.0)])

        # ---- support rows (the report's one-sided case: B = the slab) --------
        ey = np.array([0.0, 1.0, 0.0])
        for slot, sc in enumerate(self._support):
            bi = sc.bi
            R = Rcache[bi]
            off = sc.off.copy()
            a_flex_y = 0.0
            g_a = None
            if sc.cargo_bi >= 0 and sc.pid >= 0:
                cb = self._cargo[sc.cargo_bi]
                Phi = np.asarray(cb.corner_modal, dtype=np.float64)
                if Phi.shape[2] > 0:
                    a = self._cargo_a[sc.cargo_bi]
                    if getattr(cb, "corotate", True):
                        RPhi = R @ Phi[sc.pid]
                    else:
                        RPhi = Phi[sc.pid]
                    g_a = RPhi[1, :].copy()           # Ĝ_a = ŷᵀ·R·Φ_c[pid]
                    a_flex_y = float(g_a @ a)         # corner flex along ŷ
            cw = self._X[bi] + R @ off
            corner_y = float(cw[1]) + a_flex_y        # p = x + R(r + Φ·a), ŷ part
            surf = sc.y_rest + float(sc.U_y @ self._q)
            phi = corner_y - surf                     # C = C_rigid + Ĝ_A·a − U_y·q
            if phi >= margin:
                continue
            Jb = self._rigid_jac(bi, cw, ey, +1.0)
            blocks: list[tuple[object, NDArray[np.float64]]] = [(bi, Jb)]
            blocks.append(("q", -sc.U_y))             # ∂C/∂q = −U_y (slab side)
            if g_a is not None:
                blocks.append((("a", sc.cargo_bi), g_a))   # ∂C/∂a = +Ĝ_A
            _add_contact(blocks, phi, sc.mu, ("s", slot), cw, [(bi, +1.0)])

        # ---- box-box rows (the symmetric case; SAT geometry) -----------------
        if self._self_collide:
            support_bodies = {sc.bi for sc in self._support}
            for i in range(n):
                for j in range(i + 1, n):
                    if self._invm[i] == 0.0 and self._invm[j] == 0.0:
                        continue
                    for pk, (point, normal, pen) in enumerate(
                            self._box_box(i, j)):
                        mu = min(self._mu[i], self._mu[j]) \
                            if (self._mu[i] > 0 and self._mu[j] > 0) \
                            else self._self_friction
                        phi = -pen
                        Ja = self._rigid_jac(i, point, normal, +1.0)
                        Jb = self._rigid_jac(j, point, normal, -1.0)
                        blocks = [(i, Ja), (j, Jb)]
                        kicks: list = []
                        if self._modal_contact_network:
                            gA = self._cargo_G(i, point, normal, Rcache[i])
                            gB = self._cargo_G(j, point, normal, Rcache[j])
                            if self._modal_contact_ride:
                                # Full monolithic row: Ĝ columns in the gap,
                                # velocity map, and Delassus (report §1
                                # verbatim). φ = C_rigid + Ĝ_A·a_A − Ĝ_B·a_B.
                                # KNOWN LIMIT (why this is opt-in): letting the
                                # rigid row kinematically ride the ringing cube
                                # surfaces rectifies the ±Ĝ·ȧ oscillation
                                # through the λ ≥ 0 clamp into net torque on
                                # off-center stacks (measured: the §N2 zig-zag
                                # tower ratchets ω_z and topples at ~1 s). The
                                # AVBD backend hit the same instability and
                                # ships the ride engagement-gated + capped
                                # (`_bake_ride_crest`, N3); route-a-stacked-
                                # cosolve records the coupler-era rocking.
                                if gA is not None:
                                    blocks.append((("a", i), gA))
                                    phi += float(gA @ self._cargo_a[i])
                                if gB is not None:
                                    blocks.append((("a", j), -gB))
                                    phi -= float(gB @ self._cargo_a[j])
                            else:
                                # DEVIATION (report §1 one-row ideal): default
                                # box-box semantics MIRROR the shipped AVBD
                                # default (ride off): the row solves rigid-only
                                # and the SHARED multiplier λ drives both
                                # cubes' modes open-loop, +Ĝ_Aᵀλ / −Ĝ_Bᵀλ —
                                # Newton's third law in force, no kinematic
                                # ride of the rigid gap on the ringing
                                # surface. The support (slab) rows keep the
                                # full native columns — they are the stable,
                                # validated two-way headline.
                                if gA is not None:
                                    kicks.append((("a", i), gA))
                                if gB is not None:
                                    kicks.append((("a", j), -gB))
                        loc = np.round(Rcache[i].T @ (point - self._X[i]), 3)
                        _add_contact(blocks, phi, mu,
                                     ("bb", i, j, tuple(loc)), point,
                                     [(i, +1.0), (j, -1.0)], kicks=kicks)
        return rows

    # ---- the substep ---------------------------------------------------------

    def _modal_free_rate(self, mdiag, kdiag, ddiag, a, adot, f, h,
                         drop_inertia: bool = False):
        """Free implicit-Euler rate of one modal block (module docstring):
            (M + h·D + h²·K) ȧ⁺ = M ȧ − h·K a + h·f  (+ impulse P at solve)
        Returns (ȧ_free, W_eff diag)."""
        denom = mdiag + h * ddiag + (h * h) * kdiag
        W = np.where(denom > 0.0, 1.0 / np.maximum(denom, 1e-300), 0.0)
        Ma = np.zeros_like(adot) if drop_inertia else mdiag * adot
        return W * (Ma - h * kdiag * a + h * f), W

    def _substep(self, h: float) -> None:
        if self.substep_begin_hook is not None:
            self.substep_begin_hook(self)
        X, Q, V, W_ang = self._X, self._Q, self._V, self._W
        n = X.shape[0]
        x_prev = X.copy()
        v_prev = V.copy()   # §15 trapezoidal gravity work (see _psv_commit)

        # ---- §15 energy snapshot (pre-solve) ---------------------------------
        if self._modal and self._psv_ledger is None:
            # the viser passivity toggle nulls the ledger for a fresh start;
            # recreate lazily (same contract as the other backends)
            from .passivity import PassivityLedger
            self._psv_ledger = PassivityLedger(eta=float(self._modal_eta))
        _psv = self._modal and self._psv_ledger is not None
        if _psv:
            from .passivity import (rigid_mechanical_energy,
                                    local_inertia_from_invIl)
            if self._psv_Il is None or self._psv_Il.shape[0] != n:
                self._psv_Il = local_inertia_from_invIl(self._invIl)
            E_rig_pre = rigid_mechanical_energy(
                V, W_ang, self._Q[:, [3, 0, 1, 2]], self._mass, self._invIl,
                Il=self._psv_Il)
            E_modal_pre = self._modal_energy_total()

        # ---- free velocities (rigid explicit, modal implicit) ----------------
        v_free = V.copy()
        for i in range(n):
            if self._invm[i] > 0.0:
                v_free[i] += h * self.gravity
        w_free = W_ang.copy()   # no gyroscopic torque (main-branch behaviour)

        qdot_free = None
        Wq = None
        if self._modal:
            qdot_free, Wq = self._modal_free_rate(
                self._mq, self._kq, self._dq, self._q, self._qdot,
                self._modal_grav_force, h, drop_inertia=self._freeze_qdot)
        adot_free: dict = {}
        Wa: dict = {}
        for bi in self._cargo:
            adot_free[bi], Wa[bi] = self._modal_free_rate(
                self._cargo_mq[bi], self._cargo_kq[bi], self._cargo_dq[bi],
                self._cargo_a[bi], self._cargo_adot[bi],
                np.zeros_like(self._cargo_a[bi]), h,
                drop_inertia=self._freeze_qdot)

        # ---- rows at the current pose ---------------------------------------
        rows = self._collect_rows(h)
        self._last_max_penetration = max(
            (max(0.0, -r.phi) for r in rows if r.friction_of < 0), default=0.0)
        if not rows:
            self._commit_free(h, v_free, w_free, qdot_free, adot_free)
            if _psv:
                self._psv_commit(h, x_prev, v_prev, E_rig_pre, E_modal_pre)
            return

        m = len(rows)

        def _block_vfree(bk):
            if isinstance(bk, int):
                return np.concatenate([v_free[bk], w_free[bk]])
            if bk == "q":
                return qdot_free
            return adot_free[bk[1]]

        def _block_Winv_apply(bk, J):
            if isinstance(bk, int):
                out = np.empty(6)
                out[0:3] = self._invm[bk] * J[0:3]
                R = _quat_to_R(Q[bk])
                out[3:6] = (R @ self._invIl[bk] @ R.T) @ J[3:6]
                return out
            if bk == "q":
                return Wq * J
            return Wa[bk[1]] * J

        # ---- A, b (paper Eq. 2, extended DOFs) -------------------------------
        block_rows: dict = {}
        for ri, row in enumerate(rows):
            for bk, J in row.blocks:
                if isinstance(bk, int) and self._invm[bk] == 0.0:
                    continue
                block_rows.setdefault(bk, []).append((ri, J))

        A = np.zeros((m, m))
        b = np.zeros(m)
        for bk, entries in block_rows.items():
            WJ = [_block_Winv_apply(bk, J) for (_, J) in entries]
            vf = _block_vfree(bk)
            for ei, (ri, Ji) in enumerate(entries):
                b[ri] -= float(Ji @ vf)
                for ej in range(ei, len(entries)):
                    rj, Jj = entries[ej]
                    val = float(Ji @ WJ[ej])
                    A[ri, rj] += val
                    if ri != rj:
                        A[rj, ri] += val
        cfm_eff = self._cfm_ref * (h / self._h_ref) ** 2
        A[np.diag_indices(m)] += (1.0 / h ** 2) * cfm_eff
        for ri, row in enumerate(rows):
            if row.friction_of < 0:
                b[ri] -= (self.erp / h) * row.phi

        # ---- PGS (paper Eq. 3) with warm start -------------------------------
        lam = np.zeros(m)
        for ri, row in enumerate(rows):
            lam[ri] = self._lam_cache.get(row.key, 0.0)
        lo = np.array([r.lo for r in rows])
        hi = np.array([r.hi for r in rows])
        fnm = np.array([r.friction_of for r in rows], dtype=np.int64)
        fmu = np.array([r.mu for r in rows])
        diag = A.diagonal().copy()
        diag_inv = np.where(np.abs(diag) > 1e-30, 1.0 / diag, 0.0)
        for _ in range(self.iterations):
            for ri in range(m):
                if fnm[ri] >= 0:
                    lam_n = lam[fnm[ri]]
                    lo[ri] = -fmu[ri] * lam_n
                    hi[ri] = fmu[ri] * lam_n
                resid = b[ri] - float(A[ri] @ lam) + diag[ri] * lam[ri]
                lam[ri] = min(max(resid * diag_inv[ri], lo[ri]), hi[ri])
        self._lam_cache = {row.key: float(lam[ri])
                           for ri, row in enumerate(rows)}
        self._last_lambda = lam
        self._last_rows = rows

        # ---- distribute impulses (report §1: same λ routed to every DOF) -----
        jt: dict = {}
        for ri, row in enumerate(rows):
            li = float(lam[ri])
            if li == 0.0:
                continue
            for bk, J in row.blocks:
                if isinstance(bk, int) and self._invm[bk] == 0.0:
                    continue
                acc = jt.setdefault(bk, np.zeros_like(J))
                acc += J * li
            for bk, g in row.kick_blocks:
                # box-box network default: the shared λ drives the modes
                # open-loop (+Ĝ_Aᵀλ / −Ĝ_Bᵀλ), same W_eff response.
                acc = jt.setdefault(bk, np.zeros_like(g))
                acc += g * li
        for bk, P in jt.items():
            dv = _block_Winv_apply(bk, P)
            if isinstance(bk, int):
                v_free[bk] += dv[0:3]
                w_free[bk] += dv[3:6]
            elif bk == "q":
                qdot_free = qdot_free + dv
            else:
                adot_free[bk[1]] = adot_free[bk[1]] + dv

        self._commit_free(h, v_free, w_free, qdot_free, adot_free)
        if _psv:
            self._psv_commit(h, x_prev, v_prev, E_rig_pre, E_modal_pre)

    def _commit_free(self, h, v_new, w_new, qdot_new, adot_new) -> None:
        """Velocity commit + symplectic-Euler position integration (paper Eq. 1;
        modal blocks integrate a ← a + h·ȧ⁺, the backward-Euler position row)."""
        n = self._X.shape[0]
        for i in range(n):
            if self._invm[i] == 0.0:
                continue
            self._V[i] = v_new[i]
            self._W[i] = w_new[i]
            self._X[i] += h * self._V[i]
            self._Q[i] = _quat_integrate_xyzw(self._Q[i], self._W[i], h)
        if self._modal:
            self._qdot = qdot_new
            self._q = self._q + h * self._qdot
            if self._freeze_qdot:
                self._qdot = np.zeros_like(self._qdot)
            self.last_modal_KE = 0.5 * float(self._qdot @ (self._mq * self._qdot))
            self.last_modal_PE = 0.5 * float(self._q @ (self._kq * self._q))
        for bi in self._cargo:
            self._cargo_adot[bi] = adot_new[bi]
            self._cargo_a[bi] = self._cargo_a[bi] + h * self._cargo_adot[bi]
            if self._freeze_qdot:
                self._cargo_adot[bi] = np.zeros_like(self._cargo_adot[bi])

    # ---- §15 passivity -------------------------------------------------------

    def _active_support_rows(self):
        """((m,r) U_y, (m,) priority) for the load-bearing support rows, by the
        same solver-agnostic gap criterion the other hosts use
        (passivity.active_rows_from_gaps)."""
        from .passivity import active_rows_from_gaps
        q = np.asarray(self._q, dtype=np.float64)
        if not self._support or q.size == 0:
            return np.zeros((0, q.size)), np.zeros(0)
        U = np.empty((len(self._support), q.size), dtype=np.float64)
        gaps = np.empty(len(self._support), dtype=np.float64)
        for i, sc in enumerate(self._support):
            R = _quat_to_R(self._Q[sc.bi])
            corner_y = float(self._X[sc.bi][1]) + float((R @ sc.off)[1])
            U[i] = sc.U_y
            gaps[i] = corner_y - (sc.y_rest + float(sc.U_y @ q))
        return active_rows_from_gaps(U, gaps,
                                     getattr(self, "_psv_gap_margin", 0.0))

    def _modal_energy_total(self) -> float:
        """Modal mechanical energy over support + ALL cargo blocks (the ledger
        is global across the network, report §2)."""
        from .passivity import modal_mech_energy
        ke, pe = modal_mech_energy(self._qdot, self._q, self._mq, self._kq)
        E = ke + pe
        for bi in self._cargo:
            ka, pa = modal_mech_energy(self._cargo_adot[bi], self._cargo_a[bi],
                                       self._cargo_mq[bi], self._cargo_kq[bi])
            E += ka + pa
        return E

    def _psv_commit(self, h, x_prev, v_prev, E_rig_pre, E_modal_pre) -> None:
        """§15 ledger update, mirroring SolverXPBD._substep_cpu: the reservoir's
        only funding is contact-dissipated rigid energy = gravity work − ΔKE."""
        from .passivity import rigid_mechanical_energy, passivity_gamma
        E_rig_post = rigid_mechanical_energy(
            self._V, self._W, self._Q[:, [3, 0, 1, 2]], self._mass,
            self._invIl, Il=self._psv_Il)
        # DEVIATION (paper Eq. (3); foundation §15): trapezoidal gravity work
        # ½ m g·(v⁻+v⁺) h, NOT the displacement form m g·(x⁺−x⁻). Under
        # symplectic Euler x⁺=x⁻+h v⁺, so the displacement form exceeds the
        # KE-consistent gravity work by ½ m h²|g|² per body per substep — a
        # phantom supply that credits free ballistic motion. The velocity-
        # trapezoidal form is the gravity work consistent with the symplectic
        # KE update and nets exactly zero for contact-free motion (asserted in
        # tests/avbd_native/test_gravity_supply_trapezoidal.py).
        grav_work = 0.0
        for i in range(self._X.shape[0]):
            if self._invm[i] == 0.0:
                continue
            grav_work += self._mass[i] * 0.5 * float(
                self.gravity @ (v_prev[i] + self._V[i])) * h
        rigid_loss = (E_rig_pre - E_rig_post) + grav_work
        e_modal_new = self._modal_energy_total()
        budget = self._psv_ledger.deposit(rigid_loss)
        gamma = 1.0
        if self._enforce_modal_passivity and not self._psv_monitor_only:
            if getattr(self, "_psv_gap_preserving", False):
                # Gap-preserving projection: same bound, admissible point chosen
                # to hold the load-bearing surface fixed (passivity.py). The
                # ledger's E_mod spans support + every cargo block, so the
                # projection must see the same STACKED state; cargo amplitudes
                # carry no support-row column, so they land in the
                # contact-invisible remainder and are scaled, never pinned.
                from .passivity import (gap_preserving_projection,
                                        modal_mech_energy)
                U_s, pri = self._active_support_rows()
                r = int(np.asarray(self._q).size)
                bis = list(self._cargo)
                qs = [self._q] + [self._cargo_a[bi] for bi in bis]
                qds = [self._qdot] + [self._cargo_adot[bi] for bi in bis]
                kqs = [self._kq] + [self._cargo_kq[bi] for bi in bis]
                mqs = [self._mq] + [self._cargo_mq[bi] for bi in bis]
                q_st, qd_st = np.concatenate(qs), np.concatenate(qds)
                kq_st, mq_st = np.concatenate(kqs), np.concatenate(mqs)
                U_st = np.zeros((U_s.shape[0], q_st.size), dtype=np.float64)
                if U_s.shape[0]:
                    U_st[:, :r] = U_s
                q_n, qd_n, gamma, info = gap_preserving_projection(
                    q_st, qd_st, kq_st, mq_st, U_st,
                    E_modal_pre, budget, tol=self._psv_ledger.tol,
                    row_priority=pri)
                self._psv_gap_info = info
                if gamma < 1.0:
                    self._q, self._qdot = q_n[:r].copy(), qd_n[:r].copy()
                    o = r
                    for bi in bis:
                        k = self._cargo_a[bi].size
                        self._cargo_a[bi] = q_n[o:o + k].copy()
                        self._cargo_adot[bi] = qd_n[o:o + k].copy()
                        o += k
                    self.last_modal_KE, self.last_modal_PE = modal_mech_energy(
                        self._qdot, self._q, self._mq, self._kq)
                    e_modal_new = self._modal_energy_total()
            else:
                gamma = passivity_gamma(e_modal_new, E_modal_pre, budget,
                                        tol=self._psv_ledger.tol)
                if gamma < 1.0:
                    self._q *= gamma
                    self._qdot *= gamma
                    for bi in self._cargo:
                        self._cargo_a[bi] *= gamma
                        self._cargo_adot[bi] *= gamma
                    e_modal_new *= gamma * gamma
                    self.last_modal_KE *= gamma * gamma
                    self.last_modal_PE *= gamma * gamma
        self._psv_ledger.commit(e_modal_new - E_modal_pre, budget, gamma,
                                e_modal_now=e_modal_new)
