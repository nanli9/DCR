"""SolverXPBD — standalone XPBD (compliant position-based) 6-DOF solver.

The XPBD projection backend of the shared constraint interface
(`dcr/avbd/_solver/constraints.py`). It is a GENUINELY INDEPENDENT solver — it
does NOT route any rigid integration / box-box / floor contact through
`SolverAVBD`, and there is no coupler. It owns:

* its OWN Macklin "Small Steps" substep integrator — per substep predict
  x̂ = x + h v + h²g (and the quaternion analogue for ω), then `iterations`
  Gauss-Seidel sweeps of compliant constraints, then v = (x − x_prev)/h,
  ω = log(q ⊗ q_prevᵀ)/h;
* its OWN box↔box + box↔floor contact as compliant unilateral constraints with
  positional Coulomb friction (Müller et al. 2020, "Detailed Rigid Body
  Simulation with XPBD"; Macklin et al. 2016 §3.5);
* (Stage 3) the reduced-modal support and (Stage 4) deformable cargo as native
  XPBD constraints.

Build status (`prompts/native_dual_solver_build_plan.md`):
* Stage 2 — THIS file: the standalone XPBD rigid core. CPU reference (the
  obviously-correct numpy path, CLAUDE.md rule 6) lands first; the device +
  CUDA-graph path follows in `xpbd_kernels.py`, parity-tested against this CPU
  reference.
* Stage 3 — `set_modal_support` / `add_support_contact_corner` (raise until then).
* Stage 4 — `add_cargo` (raises until then).

Conventions (shared with SolverAVBD): generalized velocity v = [v_lin; ω];
quaternions XYZW (Warp wp.quat); contact normal points from B out toward A;
λ_N ≥ 0; SI units. The contact GEOMETRY (SAT 15-axis + face-clip manifold) is
re-expressed here in numpy for the CPU reference; the device path reuses the
shared warp manifold from `kernels_6dof.py`.

Spec: Macklin et al. 2016 (XPBD) + §3.5 damping; Müller et al. 2020 (rigid XPBD);
`two_band_coupling.html` (Approach B). XPBD modal math to re-express in Stage 3:
`dcr/avbd/reduced_coupled_xpbd.py` (now native, no host).
"""
from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

import warp as wp

from .solver_6dof import RigidBody, box_inv_inertia_local
from . import xpbd_kernels as XK
from ...modal.symplectic_stepper import (
    modal_midpoint_coeffs,
    modal_midpoint_commit,
)

__all__ = ["SolverXPBD"]

# Corner order shared with the numpy reference (_CORNER_SIGNS) so the device SAT
# emits contacts in the exact same order — required for fp64 GS parity.
_CORNER_SIGNS_NP = np.array(
    [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
     [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], dtype=np.float64)

_STAGE3 = ("SolverXPBD reduced-modal support lands in Stage 3 of "
           "prompts/native_dual_solver_build_plan.md.")
_STAGE4 = ("SolverXPBD cargo materials land in Stage 4 of "
           "prompts/native_dual_solver_build_plan.md.")


# ---------------------------------------------------------------------------
# Local numpy quaternion helpers (XYZW). Self-contained so the standalone solver
# carries no dependency on the coupler modules (deleted in Stage 6).
# ---------------------------------------------------------------------------

def _cross3(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Explicit 3-vector cross product a × b.

    Drop-in for ``np.cross`` on length-3 vectors. ``np.cross`` carries large
    per-call Python overhead (moveaxis/normalize_axis_tuple) that dominates the
    host solve loop; the closed form is ~12× faster for tiny vectors and is
    numerically identical. Pure performance — no math change.
    """
    return np.array([a[1] * b[2] - a[2] * b[1],
                     a[2] * b[0] - a[0] * b[2],
                     a[0] * b[1] - a[1] * b[0]], dtype=np.float64)


def _norm(v: NDArray[np.float64]) -> float:
    """Euclidean norm of a small 1-D vector.

    Drop-in for ``float(np.linalg.norm(v))`` on length-3/4 vectors.
    ``np.linalg.norm`` dispatches through ravel/isComplexType/dot machinery that
    dominates for tiny vectors; ``math.sqrt(v.dot(v))`` is ~2.7× faster and
    numerically identical. Pure performance — no math change.
    """
    return math.sqrt(v.dot(v))


# Support / floor normal e_y. Shared read-only constant — never mutated by the
# callers (used only as `vp @ _EY` and `(...) * _EY`), so a single module-level
# array avoids re-allocating `np.array([0,1,0])` once per support row per sweep.
_EY = np.array([0.0, 1.0, 0.0], dtype=np.float64)


def _quat_to_R(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotation matrix from an XYZW quaternion."""
    # Unpack to Python floats first: scalar arithmetic then a single flat
    # np.array(...).reshape are ~2× faster than nested-list construction over
    # numpy scalars (this is the most-called helper in the host solve loop).
    x = float(q[0]); y = float(q[1]); z = float(q[2]); w = float(q[3])
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array([
        1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy),
        2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx),
        2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy),
    ], dtype=np.float64).reshape(3, 3)


def _quat_mul(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Hamilton product a ⊗ b for XYZW quaternions."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ], dtype=np.float64)


def _quat_inv(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Inverse of a (near-)unit XYZW quaternion (conjugate / ‖q‖²)."""
    x, y, z, w = q
    n2 = x * x + y * y + z * z + w * w
    if n2 < 1e-300:
        return np.array([0.0, 0.0, 0.0, 1.0])
    return np.array([-x, -y, -z, w], dtype=np.float64) / n2


def _quat_to_rotvec(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotation vector (axis·angle) of an XYZW quaternion. Used for ω = Δθ/h."""
    x, y, z, w = q
    if w < 0.0:  # shortest arc
        x, y, z, w = -x, -y, -z, -w
    v = np.array([x, y, z], dtype=np.float64)
    s = _norm(v)
    if s < 1e-12:
        return 2.0 * v  # small-angle: θ ≈ 2·(vector part)
    angle = 2.0 * math.atan2(s, w)
    return (angle / s) * v


def _quat_integrate(q: NDArray[np.float64], omega: NDArray[np.float64],
                    h: float) -> NDArray[np.float64]:
    """Advance an XYZW orientation by angular velocity ω over h:
    q⁺ = normalize(q + ½ h (ω,0) ⊗ q)  (first-order, as in XPBD predict)."""
    wq = np.array([omega[0], omega[1], omega[2], 0.0], dtype=np.float64)
    qn = q + 0.5 * h * _quat_mul(wq, q)
    n = _norm(qn)
    return qn / n if n > 1e-12 else np.array([0.0, 0.0, 0.0, 1.0])


def _quat_apply_rotvec(q: NDArray[np.float64],
                       dphi: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply a small rotation-vector correction dφ to an XYZW orientation:
    q⁺ = normalize(q + ½ (dφ,0) ⊗ q)  (Müller 2020 applyRotation)."""
    wq = np.array([dphi[0], dphi[1], dphi[2], 0.0], dtype=np.float64)
    qn = q + 0.5 * _quat_mul(wq, q)
    n = _norm(qn)
    return qn / n if n > 1e-12 else q


_CORNER_SIGNS = np.array(
    [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
     [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], dtype=np.float64)


class _Contact:
    """One contact point. Stores body-local anchors so the gap is re-evaluated
    against the live pose every Gauss-Seidel iteration (Müller 2020); the contact
    normal is fixed from detection. Normal points from B toward A (push-out for
    A); b < 0 marks the static floor. `lam_n` accumulates the normal multiplier
    (≥ 0) in the position solve; `jt` is the tangential friction impulse vector
    accumulated in the velocity solve (Coulomb-clamped to μ·λ_n/h)."""

    __slots__ = ("a", "b", "ra", "rb", "n", "floor_y", "mu", "lam_n", "jt")

    def __init__(self, a, b, ra, rb, n, mu, floor_y=0.0):
        self.a = int(a)
        self.b = int(b)
        self.ra = ra
        self.rb = rb
        self.n = n
        self.floor_y = float(floor_y)
        self.mu = float(mu)
        self.lam_n = 0.0
        self.jt = np.zeros(3, dtype=np.float64)


class _SupportContact:
    """A unilateral support-contact row (Stage 3): body corner `off` (body-local)
    rests on the LIVE reduced-modal surface y_rest + U_y·q (two_band_coupling.html
    — "Contact as a constraint on (z, q)"). The contact normal is +e_y (the
    support top is horizontal). Couples the rigid 6-DOF and the modal q
    (∂C/∂q = −U_y). `cargo_g`/`cargo_bi` carry the cargo co-rotated gradient G_a
    (Stage 4); None until then."""

    __slots__ = ("bi", "off", "y_rest", "U_y", "lam", "cargo_bi", "pid",
                 "mu", "jt")

    def __init__(self, bi, off, y_rest, U_y, mu=0.0):
        self.bi = int(bi)
        self.off = np.asarray(off, dtype=np.float64)
        self.y_rest = float(y_rest)
        self.U_y = np.asarray(U_y, dtype=np.float64).reshape(-1)
        self.lam = 0.0
        self.cargo_bi = -1    # cargo body index whose a-block this row reads (Stage 4)
        self.pid = -1         # cargo corner pid for the co-rotated G_a (Stage 4)
        # Coulomb friction on the support's tangent plane (normal = e_y). Without
        # it the support row is normal-only, so its torque arm cross(r_w, e_y) has
        # a structurally-zero yaw component — a resting body's vertical-axis spin
        # is never resisted and it rotates forever. mu mirrors the cube's floor
        # friction (the retyped-floor AVBD path keeps it; the native re-expression
        # dropped it). jt accumulates the per-step tangential impulse (cone-clamped).
        self.mu = float(mu)
        self.jt = np.zeros(3, dtype=np.float64)


class SolverXPBD:
    """Standalone XPBD rigid solver (Stage 2 — CPU reference; device path next).

    Implements the shared `constraints.Solver` surface for rigid bodies + box-box
    + floor contact. Modal support (Stage 3) and cargo (Stage 4) raise until
    implemented. The numpy arrays `_X/_Q/_V/_W` are the single source of truth;
    every projection helper mutates them in place.
    """

    def __init__(
        self,
        dt: float = 1.0 / 60.0,
        iterations: int = 10,
        gravity: tuple[float, float, float] = (0.0, -9.81, 0.0),
        substeps: int = 1,
        device: str = "cpu",
        contact_compliance: float = 0.0,
        contact_margin: float = 1.0e-3,
        friction_static_mult: float = 1.0,
        **_ignored,
    ) -> None:
        # _ignored swallows AVBD-only kwargs (alpha/beta/gamma/post_stabilize/
        # coloring/gpu_resident/…) so make_solver("xpbd", **avbd_kwargs) is a
        # drop-in. XPBD's knobs are the compliance, the substep/iteration budget,
        # and the contact margin — there is no AL penalty schedule.
        self.dt = float(dt)
        self.iterations = int(iterations)
        self.substeps = max(1, int(substeps))
        self.gravity = np.asarray(gravity, dtype=np.float64)
        self.device = str(device)
        self.contact_compliance = float(contact_compliance)  # α (m/N); 0 ⇒ rigid
        self.contact_margin = float(contact_margin)
        self.friction_static_mult = float(friction_static_mult)
        # A small compliance on the reduced-modal support contact (vs hard for
        # rigid box-box/floor): the real eigenbasis support has extremely stiff
        # modes (K_q up to ~3e11), and a hard support contact over-loads q in the
        # GS sweep and can blow it up on multi-body scenes. Softening the
        # contact→modal load (Macklin-style compliant unilateral) tames it; the
        # XPBD coupler used the same trick (xpbd_contact_compliance≈1e-8).
        self.support_compliance = 1.0e-8
        # Conservative under-relaxation of the support→modal load. The reduced
        # q-block coupled to many support contacts is a stiff linear system;
        # AVBD solves it implicitly (unconditionally stable), but XPBD's
        # Gauss-Seidel over (q ↔ many contacts) DIVERGES on stiff multi-body
        # scenes (q → ∞). Under-relaxing the per-contact q increment (the
        # cross-coupling term) damps the GS to convergence — the XPBD analogue
        # of the AVBD native path's conservative block-GS relaxation (memory
        # truck-stack-collapse-is-host-boxbox). 1.0 = no relaxation.
        self.modal_relax = 0.25

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
        self._X: NDArray[np.float64] | None = None    # (n,3) positions
        self._Q: NDArray[np.float64] | None = None    # (n,4) XYZW
        self._V: NDArray[np.float64] | None = None    # (n,3) lin vel
        self._W: NDArray[np.float64] | None = None    # (n,3) ang vel
        self._invm: NDArray[np.float64] | None = None  # (n,)
        self._invIl: NDArray[np.float64] | None = None  # (n,3,3) body-local I⁻¹
        self._hE: NDArray[np.float64] | None = None    # (n,3) half-extents

        # Floor registrations: (body_idx, floor_y, mu).
        self._floors: list[tuple[int, float, float]] = []
        self._floor_of: dict[int, tuple[float, float]] = {}
        self._self_collide = False
        self._self_friction = 0.0
        self._last_max_penetration = 0.0

        # Reduced-modal support (Stage 3): q ∈ R^r as a native solver DOF.
        self._modal = False
        self._r = 0
        self._mq = self._kq = self._dq = self._wq = None  # (r,) diagonals
        self._q = self._qdot = None
        self._modal_grav_acc = None
        self._freeze_qdot = False
        # Energy-conserving (implicit-midpoint) modal step. When True the modal
        # restoring constraint (_project_modal_elastic) pulls q toward the
        # midpoint free solution q_star = rhs/H_diag with compliance
        # α̃ₑ = 1/(H_diag·h² − 1), while the support contact keeps the TRUE modal
        # inverse mass 1/M_q (so it excites the mode like BE). Their GS fixed
        # point is exactly the midpoint+contact response q = q_star + F/H_diag
        # (no factor-2). This rings at the PHYSICAL rate. See
        # dcr/modal/symplectic_stepper.py and memory
        # symplectic-modal-ring-coupled-solver-findings. BE stays the default +
        # parity reference. Host path only for now.
        # DEVIATION: an earlier "fold" (support contact inverse mass = 1/H_diag)
        # was WRONG — 1/H_diag is a compliance, not an inverse mass; XPBD's
        # impulse contact needs 1/M, so the fold left the mode dead.
        self._modal_symplectic = False
        self._q_star = None       # (r,) midpoint free solution (elastic target)
        self._alpha_e = None      # (r,) elastic compliance 1/(H_diag·h² − 1)
        self._support: list[_SupportContact] = []
        self.last_modal_KE = 0.0
        self.last_modal_PE = 0.0
        # Cargo (Stage 4): augmented modal vector Q = [q_support; a_cargo…].
        self._cargo: dict = {}        # body_idx -> cargo body model
        self._cargo_a: dict = {}      # body_idx -> (k,) amplitude
        self._cargo_adot: dict = {}   # body_idx -> (k,) velocity
        self._cargo_Minv: dict = {}   # body_idx -> (k,k) M_a⁻¹ (dense; eye for fem)
        self._cargo_lam: dict = {}    # body_idx -> (k,) elastic multipliers

        # ---- device-resident warp path (Stage 2b) ------------------------
        # The numpy `_substep_cpu` stays the correctness reference (CLAUDE.md
        # rule 6); the warp path re-expresses it on resident `wp.array` state
        # (`xpbd_kernels.py`). Used when the solver runs on a CUDA device (or
        # `_force_warp` is set, for warp-on-CPU parity/benchmarking). abd cargo
        # (nonlinear V⊥) and the rare >1-cargo case fall back to numpy.
        self._force_warp = False           # run warp kernels even on device="cpu"
        self._on_device = False            # last step ran the warp path
        self._device_built = False         # device arrays uploaded
        self._d: dict = {}                 # name -> wp.array device-state pool
        self._graph = None                 # captured CUDA graph (None ⇒ recapture)
        self._graph_sig: tuple | None = None
        self._cargo_dev_bi = -1            # the single cargo body on device (-1 none)
        self._diag_host = np.zeros(4, dtype=np.float64)
        # Parallel device path (Stage 2c): per-constraint kernels + averaged
        # Jacobi instead of the dim=1 single-thread serial-GS port. None = AUTO:
        # parallel on CUDA (the GPU needs the per-constraint parallelism), serial
        # dim=1 on warp-CPU (where the parallel path's ~hundreds of tiny launches
        # per frame — no graph capture there — cost more than they save; the
        # single-thread kernel with 2 launches/substep is far faster on a CPU).
        # Set True/False to force. `_jacobi_relax` is the SOR factor on the
        # averaged correction (tuned in the optimize loop).
        self._parallel_device = None
        self._jacobi_relax = 1.0
        # Support/modal coupling schedule. The support rows share ONE reduced
        # modal block z=[q; a] (a dense hub: every row reads/writes all of q), so
        # serial GS is stable but unparallelizable and averaged Jacobi over-drives
        # the stiff shared q. `_support_block` instead condenses all rows onto the
        # small dense modal block and solves it exactly each iteration (Woodbury),
        # which is parallel AND stable — see `_project_support_block`. False keeps
        # the serial-GS reference (`_project_support`) as the parity baseline.
        self._support_block = False
        # SOR factor on the block correction (≤1, damped descent). Defaults to
        # modal_relax so the block matches the serial-GS gentleness.
        self._support_block_relax = self.modal_relax

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
        """Add a rigid box. `mass ≤ 0` marks a static body (inv-mass 0)."""
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
        stiffness: float = math.inf,  # accepted for interface parity (XPBD: compliance)
    ) -> list[int]:
        """Register the box's 8 corners against the plane y = floor_y with
        Coulomb friction μ (compliant unilateral contact). Returns [body index]
        for interface parity with SolverAVBD (which returns per-corner rows)."""
        bi = int(body.index)
        mu = float(friction) if friction is not None else self._mu[bi]
        self._floors.append((bi, float(floor_y), mu))
        self._floor_of[bi] = (float(floor_y), mu)
        return [bi]

    def enable_self_collision(self, enabled: bool = True,
                              default_friction: float = 0.0) -> None:
        """Enable box↔box contact (SAT manifold + compliant projection)."""
        self._self_collide = bool(enabled)
        self._self_friction = float(default_friction)

    # -- reduced-modal support (Stage 3) -----------------------------------
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
        """Install the support's modal amplitude q ∈ ℝ^r as native XPBD DOF
        (two_band_coupling.html — "the two kinds of unknowns"). Mass-normalized
        modes ⇒ M_q = I, K_q = diag(ω²), D_q the Rayleigh modal damping. q is
        carried with q̇ and projected per-mode (compliant α_i = 1/K_q[i,i],
        Macklin §3.5 damped) in the same GS sweep as the rigid contacts; the
        support-contact rows read the live surface y_rest + U_y·q. No coupler."""
        Mq = np.asarray(Mq, dtype=np.float64)
        Kq = np.asarray(Kq, dtype=np.float64)
        Dq = np.asarray(Dq, dtype=np.float64)
        r = int(Mq.shape[0])
        self._r = r
        self._mq = np.diag(Mq).copy()
        self._kq = np.diag(Kq).copy()
        self._dq = np.diag(Dq).copy()
        self._wq = np.where(self._mq > 0.0, 1.0 / np.maximum(self._mq, 1e-300), 0.0)
        self._q = (np.zeros(r) if q0 is None
                   else np.asarray(q0, dtype=np.float64).copy())
        self._qdot = (np.zeros(r) if qdot0 is None
                      else np.asarray(qdot0, dtype=np.float64).copy())
        # constant modal gravity acceleration M_q⁻¹ f_q^grav (added in predict)
        if f_q_grav is None:
            self._modal_grav_acc = np.zeros(r)
        else:
            self._modal_grav_acc = self._wq * np.asarray(f_q_grav, dtype=np.float64)
        self._modal = True

    def add_support_contact_corner(
        self,
        body: RigidBody,
        off_a: tuple[float, float, float],
        y_rest: float,
        U_y_row: np.ndarray,
        stiffness: float = 1.0e9,  # accepted for interface parity (XPBD: compliance)
        friction: float = 0.0,
    ) -> int:
        """Add one unilateral support-contact row: body corner `off_a` rests on
        the live modal surface y_rest + U_y·q (foundation "Contact as a constraint
        on (z, q)"). `friction` is the Coulomb μ on the support tangent plane
        (resists sliding/spin like the floor contacts; 0 = frictionless).
        Returns the row index in `self._support`."""
        idx = len(self._support)
        self._support.append(_SupportContact(
            int(body.index) if hasattr(body, "index") else int(body),
            off_a, y_rest, U_y_row, mu=friction))
        return idx

    # -- cargo (Stage 4) ----------------------------------------------------
    def add_cargo(self, body, cargo_body,
                  support_rows: list[tuple[int, int]]) -> None:
        """Register a deformable cargo cube as native XPBD modal DOFs (M2,
        two_band_coupling.html). The cube's elastic a ∈ R^k joins the augmented
        modal vector Q = [q_support; …; a_cube] as its own block. `cargo_body`
        exposes the uniform interface (Mq_block/Kq_block/Dq_block k×k,
        corner_modal (P,3,k) = Φ_c, has_nonlinear_internal, and — for abd —
        elastic_constraints(a)). `support_rows` maps each of the cube's
        support-contact rows to its corner pid `(slot, pid)`, so each row's gap
        reads the cube's deformed corner (R·Φ_c[pid]·a)_y and loads a via
        G_a = (R·Φ_c[pid])_y. Requires set_modal_support first."""
        if not self._modal:
            raise RuntimeError("add_cargo requires set_modal_support first")
        bi = int(body.index) if hasattr(body, "index") else int(body)
        Mq = np.asarray(cargo_body.Mq_block, dtype=np.float64)
        k = int(Mq.shape[0])
        self._cargo[bi] = cargo_body
        self._cargo_a[bi] = np.zeros(k)
        self._cargo_adot[bi] = np.zeros(k)
        # multipliers: one per linear mode, or per nonlinear V⊥ constraint (abd)
        if getattr(cargo_body, "has_nonlinear_internal", False):
            n_lam = len(list(cargo_body.elastic_constraints(np.zeros(k))))
        else:
            n_lam = k
        self._cargo_lam[bi] = np.zeros(max(n_lam, 1))
        # M_a⁻¹ (dense; eye for the mass-normalized fem_rigid/fem blocks).
        if k > 0:
            self._cargo_Minv[bi] = np.linalg.inv(Mq + 1e-12 * np.eye(k))
        else:
            self._cargo_Minv[bi] = np.zeros((0, 0))
        for slot, pid in support_rows:
            self._support[slot].cargo_bi = bi
            self._support[slot].pid = int(pid)

    # AVBD-name alias (the AVBD backend exposes add_cargo_native); accept both.
    def add_cargo_native(self, body, cargo_body, support_rows) -> None:
        self.add_cargo(body, cargo_body, support_rows)

    # -- state finalization -------------------------------------------------
    def _ensure_arrays(self) -> None:
        if not self._dirty:
            return
        n = len(self._pos)
        self._X = np.asarray(self._pos, dtype=np.float64).reshape(n, 3)
        self._Q = np.asarray(self._ori, dtype=np.float64).reshape(n, 4)
        self._V = np.asarray(self._vel, dtype=np.float64).reshape(n, 3)
        self._W = np.asarray(self._ang, dtype=np.float64).reshape(n, 3)
        invm = np.zeros(n, dtype=np.float64)
        invIl = np.zeros((n, 3, 3), dtype=np.float64)
        for i in range(n):
            m = self._mass[i]
            hx, hy, hz = self._he[i]
            invm[i] = 0.0 if m <= 0.0 else 1.0 / m
            invIl[i] = np.asarray(box_inv_inertia_local(m, hx, hy, hz),
                                  dtype=np.float64)
        self._invm = invm
        self._invIl = invIl
        self._hE = np.asarray(self._he, dtype=np.float64).reshape(n, 3)
        self._dirty = False

    # -- stepping -----------------------------------------------------------
    def step(self) -> None:
        """One frame = `substeps` Macklin small-steps. Dispatches to the
        device-resident warp path on a CUDA device (or when `_force_warp` is
        set); otherwise the numpy reference (`_substep_cpu`). abd cargo / the
        rare >1-cargo case force the numpy path even on CUDA (see
        `_device_compatible`)."""
        self._ensure_arrays()
        dev = self._warp_device()
        if dev is not None and self._device_compatible():
            self._step_device(dev)
            return
        self._on_device = False
        h = self.dt / self.substeps
        for _ in range(self.substeps):
            self._substep_cpu(h)

    # -- device-resident warp path (Stage 2b) -------------------------------
    def _warp_device(self) -> str | None:
        """The warp device to run on, or None ⇒ use the numpy reference. CUDA
        always uses warp; `_force_warp` runs warp on CPU (parity/benchmark)."""
        if str(self.device).startswith("cuda"):
            return self.device
        if self._force_warp:
            return "cpu"
        return None

    def _device_compatible(self) -> bool:
        """The device path handles ≤1 cargo block and linear materials only;
        abd (nonlinear V⊥) and multi-cargo fall back to the numpy reference."""
        if self._modal_symplectic:
            return False        # symplectic modal step is host-only for now
        if len(self._cargo) > 1:
            return False
        for cb in self._cargo.values():
            if getattr(cb, "has_nonlinear_internal", False):
                return False
        return True

    def _current_sig(self) -> tuple:
        """Python scalars baked into the captured launch sequence; a change
        invalidates the cached CUDA graph."""
        return (int(self.iterations), int(self.substeps),
                int(bool(self._freeze_qdot)), float(self.dt),
                float(self.contact_compliance), float(self.support_compliance),
                float(self.modal_relax), float(self.friction_static_mult))

    def _build_device(self, dev: str) -> None:
        """Upload all solver state to resident `wp.array`s once. After this the
        hot loop (`_launch_substep`) issues only `wp.launch` — no host readback,
        no reallocation — so the fixed sequence is CUDA-graph-capturable."""
        d = self._d
        n = self._X.shape[0]
        f64 = np.float64

        d["n"] = n
        d["X"] = wp.array(self._X.astype(f64), dtype=wp.vec3d, device=dev)
        d["Q"] = wp.array(self._Q.astype(f64), dtype=wp.quatd, device=dev)
        d["V"] = wp.array(self._V.astype(f64), dtype=wp.vec3d, device=dev)
        d["W"] = wp.array(self._W.astype(f64), dtype=wp.vec3d, device=dev)
        d["x_prev"] = wp.zeros(n, dtype=wp.vec3d, device=dev)
        d["q_prev"] = wp.zeros(n, dtype=wp.quatd, device=dev)
        d["invm"] = wp.array(self._invm.astype(f64), dtype=wp.float64, device=dev)
        d["invIl"] = wp.array(self._invIl.astype(f64), dtype=wp.mat33d, device=dev)
        d["hE"] = wp.array(self._hE.astype(f64), dtype=wp.vec3d, device=dev)
        d["signs"] = wp.array(_CORNER_SIGNS_NP, dtype=wp.vec3d, device=dev)

        # floor registrations
        nf = len(self._floors)
        if nf:
            fb = np.array([f[0] for f in self._floors], dtype=np.int32)
            fy = np.array([f[1] for f in self._floors], dtype=f64)
            fm = np.array([f[2] for f in self._floors], dtype=f64)
        else:
            fb = np.zeros(1, np.int32); fy = np.zeros(1, f64); fm = np.zeros(1, f64)
        d["n_floor"] = nf
        d["fl_bi"] = wp.array(fb, dtype=wp.int32, device=dev)
        d["fl_y"] = wp.array(fy, dtype=wp.float64, device=dev)
        d["fl_mu"] = wp.array(fm, dtype=wp.float64, device=dev)
        d["self_collide"] = 1 if self._self_collide else 0
        d["self_mu"] = float(self._self_friction)

        # contact pool (fixed capacity): floor corners + box-box pairs
        n_pairs = (n * (n - 1)) // 2 if self._self_collide else 0
        cap = nf * 8 + n_pairs * 4 + 16
        d["cap"] = cap
        d["cur"] = wp.zeros(1, dtype=wp.int32, device=dev)
        d["c_a"] = wp.zeros(cap, dtype=wp.int32, device=dev)
        d["c_b"] = wp.zeros(cap, dtype=wp.int32, device=dev)
        d["c_ra"] = wp.zeros(cap, dtype=wp.vec3d, device=dev)
        d["c_rb"] = wp.zeros(cap, dtype=wp.vec3d, device=dev)
        d["c_n"] = wp.zeros(cap, dtype=wp.vec3d, device=dev)
        d["c_floory"] = wp.zeros(cap, dtype=wp.float64, device=dev)
        d["c_mu"] = wp.zeros(cap, dtype=wp.float64, device=dev)
        d["c_lam"] = wp.zeros(cap, dtype=wp.float64, device=dev)
        d["c_jt"] = wp.zeros(cap, dtype=wp.vec3d, device=dev)

        # modal block (dummies of size 1 when no support, so signatures hold)
        r = self._r if self._modal else 1
        d["r"] = r

        def _f64arr(a, size):
            out = np.zeros(size, dtype=f64)
            if a is not None:
                out[:len(a)] = np.asarray(a, dtype=f64).reshape(-1)[:size]
            return out
        d["q"] = wp.array(_f64arr(self._q, r), dtype=wp.float64, device=dev)
        d["qdot"] = wp.array(_f64arr(self._qdot, r), dtype=wp.float64, device=dev)
        d["q_n"] = wp.zeros(r, dtype=wp.float64, device=dev)
        d["kq"] = wp.array(_f64arr(self._kq, r), dtype=wp.float64, device=dev)
        d["mq"] = wp.array(_f64arr(self._mq, r), dtype=wp.float64, device=dev)
        d["dq"] = wp.array(_f64arr(self._dq, r), dtype=wp.float64, device=dev)
        d["wq"] = wp.array(_f64arr(self._wq, r), dtype=wp.float64, device=dev)
        d["lam_q"] = wp.zeros(r, dtype=wp.float64, device=dev)
        d["grav"] = wp.array(_f64arr(self._modal_grav_acc, r), dtype=wp.float64,
                             device=dev)

        # single linear cargo block (rigid k=0 / fem_rigid / fem)
        self._cargo_dev_bi = -1
        ck = 0
        if len(self._cargo) == 1:
            bi0 = next(iter(self._cargo))
            cube = self._cargo[bi0]
            ck = int(self._cargo_a[bi0].shape[0])
            if ck > 0 and not getattr(cube, "has_nonlinear_internal", False):
                self._cargo_dev_bi = bi0
        if self._cargo_dev_bi >= 0:
            bi0 = self._cargo_dev_bi
            cube = self._cargo[bi0]
            kqd = np.diag(np.asarray(cube.Kq_block, dtype=f64))
            mqd = np.diag(np.asarray(cube.Mq_block, dtype=f64))
            dqd = np.diag(np.asarray(cube.Dq_block, dtype=f64))
            phi = np.asarray(cube.corner_modal, dtype=f64)   # (P,3,k)
            lam = self._cargo_lam[bi0]
            d["has_cargo"] = 1
            d["ck"] = ck
            d["n_lam"] = int(lam.shape[0])
            d["cg_a"] = wp.array(self._cargo_a[bi0].astype(f64),
                                 dtype=wp.float64, device=dev)
            d["cg_adot"] = wp.array(self._cargo_adot[bi0].astype(f64),
                                    dtype=wp.float64, device=dev)
            d["cg_an"] = wp.zeros(ck, dtype=wp.float64, device=dev)
            d["cg_kq"] = wp.array(kqd, dtype=wp.float64, device=dev)
            d["cg_mq"] = wp.array(mqd, dtype=wp.float64, device=dev)
            d["cg_dq"] = wp.array(dqd, dtype=wp.float64, device=dev)
            d["cg_lam"] = wp.array(lam.astype(f64), dtype=wp.float64, device=dev)
            d["cg_phi"] = wp.array(phi, dtype=wp.float64, device=dev)
        else:
            d["has_cargo"] = 0
            d["ck"] = 0
            d["n_lam"] = 1
            for nm in ("cg_a", "cg_adot", "cg_an", "cg_kq", "cg_mq", "cg_dq",
                       "cg_lam"):
                d[nm] = wp.zeros(1, dtype=wp.float64, device=dev)
            d["cg_phi"] = wp.zeros((1, 3, 1), dtype=wp.float64, device=dev)

        # support rows
        ns = len(self._support)
        d["ns"] = ns
        if ns:
            sbi = np.array([sc.bi for sc in self._support], dtype=np.int32)
            soff = np.array([sc.off for sc in self._support], dtype=f64)
            syr = np.array([sc.y_rest for sc in self._support], dtype=f64)
            sUy = np.zeros((ns, r), dtype=f64)
            for s, sc in enumerate(self._support):
                u = np.asarray(sc.U_y, dtype=f64).reshape(-1)
                sUy[s, :min(r, u.shape[0])] = u[:r]
            spid = np.array(
                [sc.pid if (sc.cargo_bi == self._cargo_dev_bi
                            and self._cargo_dev_bi >= 0) else -1
                 for sc in self._support], dtype=np.int32)
            smu = np.array([sc.mu for sc in self._support], dtype=f64)
        else:
            sbi = np.zeros(1, np.int32); soff = np.zeros((1, 3), f64)
            syr = np.zeros(1, f64); sUy = np.zeros((1, r), f64)
            spid = -np.ones(1, np.int32); smu = np.zeros(1, f64)
        d["sup_bi"] = wp.array(sbi, dtype=wp.int32, device=dev)
        d["sup_off"] = wp.array(soff, dtype=wp.vec3d, device=dev)
        d["sup_yrest"] = wp.array(syr, dtype=wp.float64, device=dev)
        d["sup_Uy"] = wp.array(sUy, dtype=wp.float64, device=dev)
        d["sup_lam"] = wp.zeros(max(ns, 1), dtype=wp.float64, device=dev)
        d["sup_pid"] = wp.array(spid, dtype=wp.int32, device=dev)
        d["sup_mu"] = wp.array(smu, dtype=wp.float64, device=dev)
        d["sup_jt"] = wp.zeros(max(ns, 1), dtype=wp.vec3d, device=dev)

        # parallel-path Jacobi accumulators (flat float64 → scalar fp64 atomics).
        # acc_dp/acc_dr double as the velocity Δv/Δω scratch (phases disjoint).
        d["acc_dp"] = wp.zeros(3 * n, dtype=wp.float64, device=dev)
        d["acc_dr"] = wp.zeros(3 * n, dtype=wp.float64, device=dev)
        d["deg"] = wp.zeros(n, dtype=wp.float64, device=dev)
        d["acc_dq"] = wp.zeros(r, dtype=wp.float64, device=dev)
        d["acc_da"] = wp.zeros(max(ck, 1), dtype=wp.float64, device=dev)

        # support/modal BLOCK-SOLVE scratch (parallel path). The support rows
        # condense onto the shared reduced block z=[q; a] (size kk = r + ck): a
        # heavy impactor coherently driving the stiff modal q diverges under
        # averaged Jacobi, so all rows are gathered into the small dense Hessian
        # H = Mz + Σ_s (1/D_s)·G_sG_sᵀ and solved exactly each iteration (AVBD's
        # gather-and-solve, see modal_qblock_kernels). Per-row G_s/D_s/b_s assemble
        # in parallel; only the kk×kk solve is dim=1. Δq/Δa land in acc_dq/acc_da.
        kk = r + ck
        d["kk"] = kk
        # cooperative tile-Cholesky solve (pk_support_solve_tiled) when the block
        # fits SUPPORT_TILE; else fall back to single-thread GE (pk_support_solve).
        tile = XK.SUPPORT_TILE
        use_tiled = kk <= tile
        d["use_tiled_solve"] = use_tiled
        d["sup_G"] = wp.zeros((max(ns, 1), kk), dtype=wp.float64, device=dev)
        d["sup_w"] = wp.zeros(max(ns, 1), dtype=wp.float64, device=dev)
        d["sup_b"] = wp.zeros(max(ns, 1), dtype=wp.float64, device=dev)
        d["sup_D"] = wp.zeros(max(ns, 1), dtype=wp.float64, device=dev)
        d["sup_act"] = wp.zeros(max(ns, 1), dtype=wp.float64, device=dev)
        d["sup_deg"] = wp.zeros(n, dtype=wp.float64, device=dev)   # support-friction divisor
        # blkH padded to tile×tile with an IDENTITY block (set once) when tiled, so
        # the padded system stays SPD and the padded u ≈ 0; pk_support_hq overwrites
        # only the real [0:kk,0:kk] block, leaving the identity padding intact.
        bh = tile if use_tiled else kk
        H0 = np.eye(bh, dtype=f64) if use_tiled else np.zeros((kk, kk), dtype=f64)
        d["blkH"] = wp.array(H0, dtype=wp.float64, device=dev)
        d["blkR"] = wp.zeros(bh, dtype=wp.float64, device=dev)
        d["blkU"] = wp.zeros(bh, dtype=wp.float64, device=dev)

        d["diag"] = wp.zeros(4, dtype=wp.float64, device=dev)
        self._device_built = True

    def _launch_substep(self, h: float, dev: str) -> None:
        """Issue one Macklin small-step as TWO fused `wp.launch`es on the
        resident pool (position phase + velocity phase) — the unit captured
        into the CUDA graph. Fusing the ~10 granular kernels into 2 cuts the
        per-substep launch-overhead floor that dominates small CUDA scenes."""
        d = self._d
        n = d["n"]
        hh = wp.float64(h)
        inv_h2 = wp.float64(1.0 / (h * h))
        a_tilde = wp.float64(self.contact_compliance / (h * h)
                             if self.contact_compliance > 0.0 else 0.0)
        freeze = 1 if self._freeze_qdot else 0
        modal = 1 if self._modal else 0
        g = wp.vec3d(float(self.gravity[0]), float(self.gravity[1]),
                     float(self.gravity[2]))
        r = d["r"]; ns = d["ns"]; ck = d["ck"]; has_cargo = d["has_cargo"]

        wp.launch(XK.k_pos_phase, dim=1,
                  inputs=[n, modal, has_cargo,
                          d["X"], d["Q"], d["V"], d["W"], d["x_prev"],
                          d["q_prev"], d["invm"], d["invIl"], d["hE"], g, hh,
                          r, d["q"], d["qdot"], d["q_n"], d["grav"], d["kq"],
                          d["wq"], d["dq"], d["lam_q"],
                          ck, d["n_lam"], d["cg_a"], d["cg_adot"], d["cg_an"],
                          d["cg_kq"], d["cg_mq"], d["cg_dq"], d["cg_lam"],
                          d["cg_phi"],
                          d["signs"], d["fl_bi"], d["fl_y"], d["fl_mu"],
                          d["n_floor"], d["self_collide"],
                          wp.float64(d["self_mu"]),
                          wp.float64(self.contact_margin), d["cap"], d["cur"],
                          d["c_a"], d["c_b"], d["c_ra"], d["c_rb"], d["c_n"],
                          d["c_floory"], d["c_mu"], d["c_lam"], d["c_jt"],
                          ns, d["sup_bi"], d["sup_off"], d["sup_yrest"],
                          d["sup_Uy"], d["sup_lam"], d["sup_pid"],
                          freeze, int(self.iterations), a_tilde, inv_h2,
                          wp.float64(self.support_compliance),
                          wp.float64(self.modal_relax)], device=dev)
        wp.launch(XK.k_vel_phase, dim=1,
                  inputs=[n, modal, has_cargo,
                          d["X"], d["Q"], d["V"], d["W"], d["x_prev"],
                          d["q_prev"], d["invm"], d["invIl"], hh,
                          r, d["q"], d["q_n"], d["qdot"], d["mq"], d["kq"],
                          ck, d["cg_a"], d["cg_an"], d["cg_adot"],
                          d["cur"], d["c_a"], d["c_b"], d["c_ra"], d["c_rb"],
                          d["c_n"], d["c_floory"], d["c_mu"], d["c_lam"],
                          d["c_jt"],
                          ns, d["sup_bi"], d["sup_off"], d["sup_lam"],
                          d["sup_mu"], d["sup_jt"],
                          freeze, int(self.iterations),
                          wp.float64(self.friction_static_mult), d["diag"]],
                  device=dev)

    def _launch_substep_parallel(self, h: float, dev: str) -> None:
        """Issue one Macklin small-step as PER-CONSTRAINT parallel launches +
        averaged Jacobi (Stage 2c) instead of the dim=1 serial-GS port. Prep
        (predict + sequential contact gen + degree count) is two dim=1 launches;
        every iteration of the position and velocity solves fans out over the
        contact pool / support rows / modes. All dims are static (pool
        capacities, early-out past the live count) so the substep captures into
        one CUDA graph. Same constraints/forces as the serial path — only the
        schedule (serial GS → averaged Jacobi) differs."""
        d = self._d
        n = d["n"]; r = d["r"]; ns = d["ns"]; ck = d["ck"]; cap = d["cap"]
        has_cargo = d["has_cargo"]
        hh = wp.float64(h)
        inv_h2 = wp.float64(1.0 / (h * h))
        a_tilde = wp.float64(self.contact_compliance / (h * h)
                             if self.contact_compliance > 0.0 else 0.0)
        at_sup = wp.float64(self.support_compliance / (h * h))
        relax = wp.float64(self._jacobi_relax)
        srelax = wp.float64(self._support_block_relax)   # block-solve SOR factor
        beps = wp.float64(1.0e-10)                        # block-solve diag pad
        kk = d["kk"]
        fric = wp.float64(self.friction_static_mult)
        margin = wp.float64(self.contact_margin)
        freeze = 1 if self._freeze_qdot else 0
        modal = 1 if self._modal else 0
        iters = int(self.iterations)
        g = wp.vec3d(float(self.gravity[0]), float(self.gravity[1]),
                     float(self.gravity[2]))
        ns1 = max(ns, 1)

        # ---- prep: predict + contact gen + degree count (dim=1) ----
        wp.launch(XK.pk_prep, dim=1,
                  inputs=[n, modal, has_cargo, d["X"], d["Q"], d["V"], d["W"],
                          d["x_prev"], d["q_prev"], d["invm"], d["hE"], g, hh,
                          r, d["q"], d["qdot"], d["q_n"], d["grav"], d["lam_q"],
                          ck, d["n_lam"], d["cg_a"], d["cg_adot"], d["cg_an"],
                          d["cg_lam"], d["signs"], d["fl_bi"], d["fl_y"],
                          d["fl_mu"], d["n_floor"], d["self_collide"],
                          wp.float64(d["self_mu"]), margin, cap, d["cur"],
                          d["c_a"], d["c_b"], d["c_ra"], d["c_rb"], d["c_n"],
                          d["c_floory"], d["c_mu"], d["c_lam"], d["c_jt"],
                          ns, d["sup_lam"], freeze], device=dev)
        # parallel contact generation (one thread per floor reg / body pair) —
        # the O(nb²) SAT was the dominant dim=1 fixed cost per step.
        if d["n_floor"] > 0:
            wp.launch(XK.pk_gen_floor, dim=d["n_floor"],
                      inputs=[d["X"], d["Q"], d["hE"], d["signs"], d["fl_bi"],
                              d["fl_y"], d["fl_mu"], d["n_floor"], margin, cap,
                              d["cur"], d["c_a"], d["c_b"], d["c_ra"], d["c_rb"],
                              d["c_n"], d["c_floory"], d["c_mu"], d["c_lam"],
                              d["c_jt"]], device=dev)
        if d["self_collide"]:
            wp.launch(XK.pk_gen_boxbox, dim=n * n,
                      inputs=[d["X"], d["Q"], d["invm"], d["hE"], d["signs"], n,
                              wp.float64(d["self_mu"]), margin, cap, d["cur"],
                              d["c_a"], d["c_b"], d["c_ra"], d["c_rb"], d["c_n"],
                              d["c_floory"], d["c_mu"], d["c_lam"], d["c_jt"]],
                      device=dev)
        wp.launch(XK.pk_zero_deg, dim=n, inputs=[n, d["deg"]], device=dev)
        wp.launch(XK.pk_deg_contacts, dim=cap,
                  inputs=[d["cur"], d["c_a"], d["c_b"], d["deg"]], device=dev)
        # deg counts CONTACTS ONLY — the support/modal coupling is routed through
        # its own block solve (pk_support_* below), not the contact averaged-Jacobi
        # accumulator, so support rows must NOT inflate the contact divisor.

        # ---- position solve: PARALLEL box-box/floor contacts + PARALLEL block
        # solve for the modal support. The stiff shared modal q diverges under
        # averaged Jacobi (a heavy impactor coherently driving mode 0 rings it up),
        # so the support rows are CONDENSED onto the small dense modal block H and
        # solved exactly each iteration (AVBD's gather-and-solve, SOR-damped) — the
        # per-row work fans out, only the kk×kk solve is dim=1 — while the expensive
        # O(nb²) box-box SAT stays parallel (the real perf win). ----
        rk = max(r, ck)
        for _ in range(iters):
            # elastic FIRST (writes q/a directly, exact) → contacts (parallel
            # Jacobi, applied) → support GS reads the updated q/a AND post-contact
            # bodies (GS order contacts→support, as in the serial reference).
            if modal:
                wp.launch(XK.pk_modes_elastic, dim=rk,
                          inputs=[r, ck, has_cargo, d["q"], d["q_n"], d["kq"],
                                  d["wq"], d["dq"], d["lam_q"], d["cg_a"],
                                  d["cg_an"], d["cg_kq"], d["cg_mq"], d["cg_dq"],
                                  d["cg_lam"], inv_h2, hh, d["acc_dq"],
                                  d["acc_da"]], device=dev)
            wp.launch(XK.pk_contact_jacobi, dim=cap,
                      inputs=[d["X"], d["Q"], d["invm"], d["invIl"], d["cur"],
                              d["c_a"], d["c_b"], d["c_ra"], d["c_rb"], d["c_n"],
                              d["c_floory"], d["c_lam"], a_tilde, d["acc_dp"],
                              d["acc_dr"]], device=dev)
            wp.launch(XK.pk_apply_body, dim=n,
                      inputs=[n, d["X"], d["Q"], d["invm"], d["deg"], relax,
                              d["acc_dp"], d["acc_dr"]], device=dev)
            if modal and ns:
                # support/modal coupling = PARALLEL block solve (Woodbury onto the
                # shared reduced block). assemble (rows) → H (k×k) → rhs → solve
                # (dim=1, kk small) → apply (rows, scatter) → apply body (full).
                wp.launch(XK.pk_support_assemble, dim=ns,
                          inputs=[d["X"], d["Q"], d["invm"], d["invIl"], ns,
                                  d["sup_bi"], d["sup_off"], d["sup_yrest"],
                                  d["sup_Uy"], d["sup_lam"], d["sup_pid"], r,
                                  d["q"], has_cargo, ck, d["cg_a"], d["cg_phi"],
                                  at_sup, d["sup_G"], d["sup_w"], d["sup_b"],
                                  d["sup_D"], d["sup_act"]], device=dev)
                wp.launch(XK.pk_support_hq, dim=(kk, kk),
                          inputs=[kk, ns, r, beps, d["wq"], d["cg_mq"],
                                  d["sup_G"], d["sup_w"], d["blkH"]], device=dev)
                wp.launch(XK.pk_support_rhs, dim=kk,
                          inputs=[kk, ns, d["sup_G"], d["sup_w"], d["sup_b"],
                                  d["blkR"]], device=dev)
                if d["use_tiled_solve"]:        # cooperative block Cholesky
                    wp.launch_tiled(XK.pk_support_solve_tiled, dim=[1, 1],
                                    inputs=[d["blkH"], d["blkR"], d["blkU"]],
                                    block_dim=128, device=dev)
                else:                            # single-thread GE fallback
                    wp.launch(XK.pk_support_solve, dim=1,
                              inputs=[kk, d["blkH"], d["blkR"], d["blkU"]],
                              device=dev)
                wp.launch(XK.pk_support_apply, dim=ns,
                          inputs=[d["X"], d["Q"], d["invm"], d["invIl"], ns,
                                  d["sup_bi"], d["sup_off"], d["sup_lam"], r, kk,
                                  d["sup_G"], d["sup_b"], d["sup_D"], d["sup_act"],
                                  d["wq"], has_cargo, ck, d["cg_mq"], d["blkU"],
                                  srelax, d["acc_dp"], d["acc_dr"], d["acc_dq"],
                                  d["acc_da"]], device=dev)
                wp.launch(XK.pk_support_apply_body, dim=n,
                          inputs=[n, d["X"], d["Q"], d["invm"], d["acc_dp"],
                                  d["acc_dr"]], device=dev)
                wp.launch(XK.pk_apply_q, dim=r,
                          inputs=[r, d["q"], d["acc_dq"]], device=dev)
                if has_cargo:
                    wp.launch(XK.pk_apply_a, dim=ck,
                              inputs=[ck, d["cg_a"], d["acc_da"]], device=dev)

        # ---- velocity prep (parallel) + averaged Jacobi velocity solve ----
        wp.launch(XK.pk_velupd, dim=n,
                  inputs=[n, d["X"], d["Q"], d["x_prev"], d["q_prev"], d["V"],
                          d["W"], d["invm"], hh], device=dev)
        wp.launch(XK.pk_commit, dim=1,
                  inputs=[modal, has_cargo, r, d["q"], d["q_n"], d["qdot"],
                          d["mq"], d["kq"], ck, d["cg_a"], d["cg_an"],
                          d["cg_adot"], freeze, hh, d["diag"]], device=dev)
        wp.launch(XK.pk_zero_jt, dim=cap, inputs=[cap, d["c_jt"]], device=dev)
        if modal and ns:
            wp.launch(XK.pk_zero_supjt, dim=ns1,
                      inputs=[ns, d["sup_jt"]], device=dev)
            # support-friction deg (per body) — constant through the velocity loop
            # (sup_lam is fixed after the position solve), so computed once here.
            wp.launch(XK.pk_zero_deg, dim=n, inputs=[n, d["sup_deg"]], device=dev)
            wp.launch(XK.pk_support_fric_deg, dim=ns,
                      inputs=[ns, d["sup_bi"], d["sup_lam"], d["sup_mu"],
                              d["invm"], d["sup_deg"]], device=dev)
        for _ in range(iters):
            wp.launch(XK.pk_contact_velsolve, dim=cap,
                      inputs=[d["Q"], d["V"], d["W"], d["invm"], d["invIl"],
                              d["cur"], d["c_a"], d["c_b"], d["c_ra"], d["c_rb"],
                              d["c_n"], d["c_mu"], d["c_lam"], d["c_jt"], fric,
                              hh, d["acc_dp"], d["acc_dr"]], device=dev)
            wp.launch(XK.pk_apply_vel, dim=n,
                      inputs=[n, d["V"], d["W"], d["invm"], d["deg"], relax,
                              d["acc_dp"], d["acc_dr"]], device=dev)
            # support friction = PARALLEL averaged Jacobi (body-local, no hub):
            # scatter Δv/Δω → apply ÷ sup_deg (own divisor, support not in `deg`).
            if modal and ns:
                wp.launch(XK.pk_support_velsolve_jacobi, dim=ns,
                          inputs=[d["Q"], d["V"], d["W"], d["invm"], d["invIl"],
                                  ns, d["sup_bi"], d["sup_off"], d["sup_lam"],
                                  d["sup_mu"], d["sup_jt"], fric, hh, d["acc_dp"],
                                  d["acc_dr"]], device=dev)
                wp.launch(XK.pk_apply_vel, dim=n,
                          inputs=[n, d["V"], d["W"], d["invm"], d["sup_deg"],
                                  relax, d["acc_dp"], d["acc_dr"]], device=dev)

        wp.launch(XK.pk_maxpen, dim=1,
                  inputs=[d["cur"], d["X"], d["Q"], d["c_a"], d["c_b"],
                          d["c_ra"], d["c_rb"], d["c_n"], d["c_floory"],
                          d["diag"]], device=dev)

    def _step_device(self, dev: str) -> None:
        """Run one frame on-device (capture+replay the substep sequence on
        CUDA; eager launch on CPU-warp where graph capture is unsupported)."""
        if not self._device_built:
            self._build_device(dev)
        h = self.dt / self.substeps
        sig = self._current_sig()
        if sig != self._graph_sig:
            self._graph = None
            self._graph_sig = sig
        parallel = (self._parallel_device if self._parallel_device is not None
                    else str(dev).startswith("cuda"))
        launch = (self._launch_substep_parallel if parallel
                  else self._launch_substep)
        use_graph = (str(dev).startswith("cuda")
                     and hasattr(wp, "ScopedCapture")
                     and hasattr(wp, "capture_launch"))
        ran = False
        if use_graph:
            if self._graph is None:
                try:
                    with wp.ScopedCapture(device=dev) as cap:
                        for _ in range(self.substeps):
                            launch(h, dev)
                    self._graph = cap.graph
                except Exception:
                    self._graph = None
                    use_graph = False
            if self._graph is not None:
                wp.capture_launch(self._graph)
                ran = True
        if not ran:
            for _ in range(self.substeps):
                launch(h, dev)
        # one tiny diagnostic readback per FRAME (outside the captured hot loop)
        self._diag_host = self._d["diag"].numpy()
        self._last_max_penetration = float(self._diag_host[0])
        if self._modal:
            self.last_modal_KE = float(self._diag_host[1])
            self.last_modal_PE = float(self._diag_host[2])
        self._on_device = True

    def _substep_cpu(self, h: float) -> None:
        X, Q, V, W, invm = self._X, self._Q, self._V, self._W, self._invm
        n = X.shape[0]
        x_prev = X.copy()
        q_prev = Q.copy()

        # ---- predict (inertial) -----------------------------------------
        for i in range(n):
            if invm[i] == 0.0:
                continue
            V[i] += h * self.gravity
            X[i] += h * V[i]
            Q[i] = _quat_integrate(Q[i], W[i], h)

        # ---- modal predict (two_band_coupling.html, Approach B) ---------
        # q̃ = qⁿ + h·q̇ⁿ + h²·M_q⁻¹f_q^grav. freeze_qdot deletes the inertial
        # advance (h_pred=0) — the counterfactual that removes the modal inertia
        # term, so q cannot ring (KE ≈ 0). The per-mode elastic constraint pulls
        # q̃ back in the GS sweep.
        modal_qn = None
        modal_qdotn = None
        cargo_an: dict = {}
        if self._modal:
            modal_qn = self._q.copy()
            modal_qdotn = self._qdot.copy()
            h_pred = 0.0 if self._freeze_qdot else h
            if self._modal_symplectic and not self._freeze_qdot:
                # Implicit-midpoint modal step (dcr/modal/symplectic_stepper).
                # Predictor = q_star (the free midpoint solution); the elastic
                # restoring (_project_modal_elastic_symplectic) pulls q→q_star
                # with compliance α̃ₑ = 1/(H_diag·h² − 1) so that, with the support
                # contact using the TRUE inverse mass 1/M, the GS fixed point is
                # q = q_star + F/H_diag (exact midpoint+contact, no factor-2).
                f_grav = self._modal_grav_acc * self._mq     # M_q⁻¹f→f (force)
                Hd, _, q_star, _ = modal_midpoint_coeffs(
                    self._q, self._qdot, self._mq, self._kq, self._dq, h,
                    f_grav=f_grav)
                self._q = q_star.copy()
                self._q_star = q_star
                Hh2 = Hd * (h * h)
                self._alpha_e = np.where(
                    Hh2 > 1.0, 1.0 / np.maximum(Hh2 - 1.0, 1e-300), 0.0)
            else:
                self._q = (self._q + h_pred * self._qdot
                           + (h * h) * self._modal_grav_acc)
            self._lam_q = np.zeros(self._r)
            for sc in self._support:
                sc.lam = 0.0
            for bi in self._cargo:                      # cargo predict (Stage 4)
                cargo_an[bi] = self._cargo_a[bi].copy()
                self._cargo_a[bi] = (self._cargo_a[bi]
                                     + h_pred * self._cargo_adot[bi])
                self._cargo_lam[bi][:] = 0.0

        # ---- generate contacts at the predicted pose --------------------
        contacts = self._collect_contacts()

        # ---- position solve: compliant unilateral NORMAL contact --------
        # Gauss-Seidel sweeps; the gap is re-evaluated against the live pose
        # each sweep (Müller 2020). Friction is a velocity-pass below (keyed off
        # actual tangential VELOCITY, ~0 at rest, so it never injects energy —
        # purely-positional friction drifts on a resting multi-corner box
        # because the solver's own rotational transients pollute the position
        # delta it keys off).
        a_tilde = (self.contact_compliance / (h * h)
                   if self.contact_compliance > 0.0 else 0.0)
        inv_h2 = 1.0 / (h * h)
        for _ in range(self.iterations):
            for c in contacts:
                self._project_normal(c, a_tilde)
            if self._modal:
                if self._modal_symplectic:
                    self._project_modal_elastic_symplectic()
                else:
                    self._project_modal_elastic(modal_qn, h, inv_h2)
                for bi in self._cargo:
                    self._project_cargo_elastic(bi, cargo_an[bi], h, inv_h2)
                at_sup = self.support_compliance * inv_h2   # soften the support contact
                if self._support_block:
                    self._project_support_block(at_sup)
                else:
                    for sc in self._support:
                        self._project_support(sc, at_sup)

        # ---- velocity update v = (x − x_prev)/h, ω = log(Δq)/h ----------
        for i in range(n):
            if invm[i] == 0.0:
                continue
            V[i] = (X[i] - x_prev[i]) / h
            dq = _quat_mul(Q[i], _quat_inv(q_prev[i]))
            W[i] = _quat_to_rotvec(dq) / h

        # ---- modal velocity q̇ = (q − qⁿ)/h + diagnostics ---------------
        if self._modal:
            if self._freeze_qdot:
                # Counterfactual: q̇ ≡ 0 (the modal inertia term is deleted), so
                # q responds only quasi-statically and carries NO modal KE. q
                # still deflects under load (it sags) but cannot ring.
                self._qdot = np.zeros(self._r)
                self.last_modal_KE = 0.0
            else:
                if self._modal_symplectic:
                    # midpoint commit q̇ⁿ⁺¹ = 2(qⁿ⁺¹−qⁿ)/h − q̇ⁿ
                    # (dcr/modal/symplectic_stepper.modal_midpoint_commit)
                    self._qdot = modal_midpoint_commit(
                        self._q, modal_qn, modal_qdotn, h)
                else:
                    self._qdot = (self._q - modal_qn) / h
                self.last_modal_KE = 0.5 * float(
                    self._qdot @ (self._mq * self._qdot))
            self.last_modal_PE = 0.5 * float(self._q @ (self._kq * self._q))
            for bi in self._cargo:                      # cargo ȧ = (a − aⁿ)/h
                if self._freeze_qdot:
                    self._cargo_adot[bi] = np.zeros_like(self._cargo_a[bi])
                else:
                    self._cargo_adot[bi] = (self._cargo_a[bi] - cargo_an[bi]) / h

        # ---- velocity solve (Müller 2020 §SolveVelocities) --------------
        # Per active contact: (1) inelastic normal restitution — null the
        # relative normal velocity (e=0), which removes the spurious "bounce"
        # the position projection injects into v=(x−x_prev)/h (left in, an upper
        # box launches off a lower one); (2) sequential-impulse Coulomb friction,
        # accumulated per contact and clamped to the cone |j_t| ≤ μ·λ_n/h.
        for c in contacts:
            c.jt = np.zeros(3, dtype=np.float64)
        for sc in self._support:
            sc.jt = np.zeros(3, dtype=np.float64)
        # Velocity-solve geometry (R / r_w / inv_I_world) is loop-invariant: the
        # passes mutate only V/W, never X/Q, so precompute it once per row instead
        # of 16× inside the sweep. None entries are the rows that would early-out.
        vc_geom = [self._velocity_contact_geom(c) for c in contacts]
        vs_geom = [self._velocity_support_geom(sc) for sc in self._support]
        for _ in range(self.iterations):
            for c, g in zip(contacts, vc_geom):
                if g is not None:
                    self._solve_velocity(c, h, g)
            for sc, g in zip(self._support, vs_geom):   # (3) support Coulomb friction
                if g is not None:
                    self._solve_velocity_support(sc, h, g)

        self._last_max_penetration = max(
            (self._penetration(c) for c in contacts), default=0.0)

    # -- contact generation -------------------------------------------------
    def _collect_contacts(self) -> list[_Contact]:
        X, Q, invm = self._X, self._Q, self._invm
        contacts: list[_Contact] = []
        for (bi, floor_y, mu) in self._floors:
            R = _quat_to_R(Q[bi])
            he = self._hE[bi]
            n = np.array([0.0, 1.0, 0.0])
            for s in _CORNER_SIGNS:
                off = s * he
                if (X[bi] + R @ off)[1] - floor_y < self.contact_margin:
                    contacts.append(_Contact(bi, -1, off.copy(), None, n, mu,
                                             floor_y=floor_y))
        if self._self_collide:
            nb = X.shape[0]
            for i in range(nb):
                for j in range(i + 1, nb):
                    if invm[i] == 0.0 and invm[j] == 0.0:
                        continue
                    contacts.extend(self._box_box(i, j))
        return contacts

    def _box_box(self, i, j) -> list[_Contact]:
        """SAT 15-axis + corner-clip manifold (numpy; the algorithm of
        dcr/rigid/collision._detect_box_box adapted to this solver's layout).
        Normal oriented from j (B) toward i (A)."""
        X, Q = self._X, self._Q
        margin = self.contact_margin
        Ra, Rb = _quat_to_R(Q[i]), _quat_to_R(Q[j])
        ha, hb = self._hE[i], self._hE[j]
        d = X[j] - X[i]
        axes_a = [Ra[:, k] for k in range(3)]
        axes_b = [Rb[:, k] for k in range(3)]

        def overlap(axis):
            L = _norm(axis)
            if L < 1e-10:
                return np.inf
            axis = axis / L
            pa = sum(ha[k] * abs(axes_a[k] @ axis) for k in range(3))
            pb = sum(hb[k] * abs(axes_b[k] @ axis) for k in range(3))
            return pa + pb - abs(d @ axis)

        def orient(axis):
            nn = axis / _norm(axis)
            return -nn if (d @ nn) > 0 else nn  # from B toward A

        min_face, best = np.inf, np.zeros(3)
        for ax in axes_a + axes_b:
            ov = overlap(ax)
            if ov < -margin:
                return []
            if ov < min_face:
                min_face, best = ov, orient(ax)
        min_edge = np.inf
        for a in axes_a:
            for b in axes_b:
                ov = overlap(_cross3(a, b))
                if ov < -margin:
                    return []
                min_edge = min(min_edge, ov)
        normal = best                                   # points from B toward A
        pen = max(0.0, min(min_face, min_edge))         # SAT penetration depth
        mu = self._self_friction
        out: list[_Contact] = []

        def corners(R, he, c):
            return c + (R @ (_CORNER_SIGNS * he).T).T

        def sd_to_face(p, R, he, c, fn):
            local = R.T @ (p - c)
            for k in range(3):
                if abs(R[:, k] @ fn) > 0.9:
                    continue
                if abs(local[k]) > he[k] + margin:
                    return np.inf
            return (p - c) @ fn - sum(he[k] * abs(R[:, k] @ fn) for k in range(3))

        def emit(cw, pen_c):
            # Split-the-penetration anchoring with the PER-CORNER depth `pen_c`:
            # the contact materializes as two distinct material points — one on A
            # pushed +half·pen_c into B, one on B pushed −half·pen_c into A
            # (n: B→A). So the live gap C = (p_a − p_b)·n equals −pen_c at
            # detection (C<0 ⇒ overlap) and tracks the true separation as the
            # bodies move (Müller 2020). Per-corner (not global) depth is what
            # makes the manifold RESTORING: when a box tilts, its deeper corner
            # carries more penetration and is pushed back harder, so the contact
            # supplies the torque that keeps a stack upright (a global depth
            # corrects all corners equally and lets a symmetric stack slowly tip).
            pen_c = max(0.0, pen_c)
            pa_w = cw - 0.5 * pen_c * normal
            pb_w = cw + 0.5 * pen_c * normal
            out.append(_Contact(i, j, Ra.T @ (pa_w - X[i]),
                                Rb.T @ (pb_w - X[j]), normal.copy(), mu))

        for cw in corners(Rb, hb, X[j]):  # B-corners under A
            sd = sd_to_face(cw, Ra, ha, X[i], -normal)
            if sd < margin:
                emit(cw, -sd)             # -sd = depth below A's contact face
        for cw in corners(Ra, ha, X[i]):  # A-corners under B
            sd = sd_to_face(cw, Rb, hb, X[j], normal)
            if sd < margin:
                emit(cw, -sd)
        if not out:
            emit(0.5 * (X[i] + X[j]), pen)
        return out[:4]

    # -- contact projection (Müller 2020 + Macklin XPBD) --------------------
    def _inv_I_world(self, i, R) -> NDArray[np.float64]:
        return R @ self._invIl[i] @ R.T

    @staticmethod
    def _gen_inv_mass(inv_m, inv_I_w, r, n) -> float:
        rn = _cross3(r, n)
        return float(inv_m + rn @ (inv_I_w @ rn))

    def _penetration(self, c: _Contact) -> float:
        """Current penetration depth (positive = overlapping) along c.n."""
        X, Q = self._X, self._Q
        pa = X[c.a] + _quat_to_R(Q[c.a]) @ c.ra
        if c.b < 0:
            return max(0.0, c.floor_y - pa[1])
        pb = X[c.b] + _quat_to_R(Q[c.b]) @ c.rb
        return max(0.0, float((pb - pa) @ c.n))

    # -- reduced-modal projection (Stage 3; re-expressed from the XPBD coupler)
    def _project_modal_elastic(self, qn, h: float, inv_h2: float) -> None:
        """Per-mode compliant modal-elastic constraint C_i = q_i with compliance
        α_i = 1/K_q[i,i] and the Macklin §3.5 damped update (modal Rayleigh
        D_q[i,i]) — re-expressed from reduced_coupled_xpbd_kernels.k_xpbd_elastic,
        now native. Drives q̃ toward the elastic equilibrium each sweep; the
        M_q/h² term (via w) gives q its inertia, so it RINGS (two-way coupling)."""
        q, kq, wq, dq, lam = self._q, self._kq, self._wq, self._dq, self._lam_q
        for i in range(self._r):
            ki = kq[i]
            if ki <= 0.0:
                continue
            alpha = 1.0 / ki
            at = alpha * inv_h2
            w = wq[i]
            damp = dq[i]
            gamma = at * (damp * alpha) * h if damp > 0.0 else 0.0
            Cdot = q[i] - qn[i]
            denom = (1.0 + gamma) * w + at
            dlam = (-q[i] - at * lam[i] - gamma * Cdot) / denom
            lam[i] += dlam
            q[i] += w * dlam

    def _project_modal_elastic_symplectic(self) -> None:
        """Energy-conserving (implicit-midpoint) modal restoring: pull q toward
        the midpoint free solution q_star (set in predict) with compliance
        α̃ₑ = 1/(H_diag·h² − 1) and the TRUE modal inverse mass w = 1/M_q. With
        the support contact also using 1/M_q, the GS fixed point is exactly the
        midpoint+contact response q = q_star + F/H_diag (the contact force factor
        is correct — no factor-2). Damping/gravity are already in q_star, so no
        separate damping term here. See dcr/modal/symplectic_stepper.py.

        # DEVIATION (paper Eq. 10 → in-constraint implicit midpoint): the modal q
        # is co-solved in the support constraint and the restoring is integrated
        # with implicit midpoint (energy-faithful) instead of backward Euler.
        """
        q, qstar, alpha_e, wq, lam = (self._q, self._q_star, self._alpha_e,
                                      self._wq, self._lam_q)
        for i in range(self._r):
            w = wq[i]
            at = alpha_e[i]
            if w <= 0.0 or at <= 0.0:
                continue
            C = q[i] - qstar[i]
            dlam = (-C - at * lam[i]) / (w + at)
            lam[i] += dlam
            q[i] += w * dlam

    def _project_support(self, sc: _SupportContact, a_tilde: float) -> None:
        """Unilateral support-contact row: body corner rests on the live modal
        surface y_rest + U_y·q (+ cargo flex G_a·a, Stage 4). Couples the rigid
        6-DOF (n = e_y) and the support modal q (∂C/∂q = −U_y). Re-expressed from
        reduced_coupled_xpbd.iteration_hook's FLOOR-contact block, now native."""
        X, Q, invm, q, wq = self._X, self._Q, self._invm, self._q, self._wq
        bi = sc.bi
        R = _quat_to_R(Q[bi])
        r_w = R @ sc.off
        corner_y = X[bi][1] + r_w[1]
        surf = sc.y_rest + float(sc.U_y @ q)
        # cargo flex (Stage 4): the cube's deformed corner adds (R·Φ_c·a)_y
        g_a = None
        if sc.cargo_bi >= 0:
            g_a, flex = self._cargo_support_grad(sc)
            surf += flex
        C = corner_y - surf
        if C >= 0.0 and sc.lam == 0.0:
            return
        j_ang = np.array([-r_w[2], 0.0, r_w[0]])   # cross(r_w, e_y)
        inv_Iw = self._inv_I_world(bi, R)
        w = invm[bi] + float(j_ang @ (inv_Iw @ j_ang))
        w += float((sc.U_y * sc.U_y) @ wq)   # = Σ U_y²·wq, dot avoids np.sum dispatch
        if g_a is not None:
            w += float(g_a[0] @ g_a[1])   # G_aᵀ M_a⁻¹ G_a
        dlam = (-C - a_tilde * sc.lam) / (w + a_tilde)
        new = max(0.0, sc.lam + dlam)
        dlam = new - sc.lam
        sc.lam = new
        if dlam == 0.0:
            return
        X[bi][1] += invm[bi] * dlam
        Q[bi] = _quat_apply_rotvec(Q[bi], (inv_Iw @ j_ang) * dlam)
        rel = self.modal_relax
        q += rel * (-sc.U_y * wq) * dlam               # under-relaxed (GS stability)
        if g_a is not None:
            self._cargo_a[sc.cargo_bi] += rel * g_a[1] * dlam   # ∂C/∂a = +G_a

    def _cargo_support_grad(self, sc: _SupportContact):
        """Co-rotated cargo gradient for a support-contact row reading the cube's
        deformed corner. Returns ((G_a, M_a⁻¹G_a), flex) with
        G_a = (R·Φ_c[pid])_y = ∂(corner_y)/∂a and flex = G_a·a."""
        bi = sc.cargo_bi
        body = self._cargo[bi]
        a = self._cargo_a[bi]
        R = _quat_to_R(self._Q[sc.bi])
        Phi = np.asarray(body.corner_modal[sc.pid], dtype=np.float64)  # (3,k)
        G_a = (R @ Phi)[1, :]                   # y-row
        flex = float(G_a @ a)
        MgG = self._cargo_Minv[bi] @ G_a
        return (G_a, MgG), flex

    def _project_support_block(self, a_tilde: float) -> None:
        """ONE block projection of ALL support rows at once — the parallel-safe
        replacement for the serial-GS per-row sweep `_project_support`.

        The support rows couple to a SHARED reduced block z = [q (modes); a
        (cargo)]: every row reads and writes all of q (∂C/∂q = −U_y). That makes
        them a dense hub — graph coloring degenerates to fully serial, and averaged
        Jacobi (each row sees only its OWN modal diagonal U_y²·wq) under-estimates
        the shared stiffness and over-drives the stiff q, so it rings up and
        diverges on an impact. Instead, condense all rows onto the small dense
        modal block and solve it EXACTLY via Woodbury (paper Eq. 2 Schur structure,
        specialized to the reduced support constraint):

            S Δλ = b,   S = D + G Mz⁻¹ Gᵀ,   D = diag(w_body,s + α̃)
            Δλ = D⁻¹b − D⁻¹G H⁻¹(Gᵀ D⁻¹b),   H = Mz + Gᵀ D⁻¹ G   (k×k)

        where row s contributes the shared-DOF Jacobian G_s = [−U_y[s]; −G_a[s]]
        (length k = #active modes + #cargo modes), Mz⁻¹ = diag([wq; 1/cg_mq]) is
        the reduced inverse mass, and b_s = −(C_s + α̃·λ_s). H is the (≈12-DOF)
        "block solve on the modal DOFs" the hub needs; it is SPD so a Cholesky
        suffices. The modal/cargo correction Δz = Mz⁻¹ Gᵀ Δλ is then EXACT — no
        `modal_relax` under-relaxation, because the cross-row coupling is already
        inside H.

        # DEVIATION (vs serial `_project_support`): the body block D is taken
        # DIAGONAL — same-body corner cross-coupling (a box's 8 corners share its
        # 6-DOF) is left to the outer GS iteration + contact deg-averaging, exactly
        # as the parallel contact path already does. This changes only the
        # convergence path, not the fixed point: at Δλ=0 every active row still
        # satisfies C_s = −α̃·λ_s (identical to the serial-GS fixed point).
        """
        sup = self._support
        if not sup:
            return
        X, Q, invm, q, wq = self._X, self._Q, self._invm, self._q, self._wq

        # shared-DOF layout: active modes (wq>0) followed by one cargo a-block
        midx = np.nonzero(wq > 0.0)[0]
        rm = midx.shape[0]
        cbi = self._cargo_dev_bi
        if cbi < 0:
            cset = {sc.cargo_bi for sc in sup if sc.cargo_bi >= 0}
            cbi = next(iter(cset)) if len(cset) == 1 else -1
        ck = 0
        cidx = None
        if cbi >= 0:
            cg_mq = np.diag(np.asarray(self._cargo[cbi].Mq_block, dtype=np.float64))
            cidx = np.nonzero(cg_mq > 0.0)[0]
            ck = cidx.shape[0]
        k = rm + ck
        if k == 0:
            return
        Mzinv = np.empty(k)                       # = diag([wq; 1/cg_mq])
        Mzinv[:rm] = wq[midx]
        if ck:
            Mzinv[rm:] = 1.0 / cg_mq[cidx]

        # --- parallel assemble: per active row build G_s, D_s, b_s; reduce H, rhs
        H = np.zeros((k, k))
        rhs = np.zeros(k)
        rows = []
        for sc in sup:
            bi = sc.bi
            R = _quat_to_R(Q[bi])
            r_w = R @ sc.off
            corner_y = X[bi][1] + r_w[1]
            surf = sc.y_rest + float(sc.U_y @ q)
            G_a_full = None
            if sc.cargo_bi == cbi and cbi >= 0:
                Phi = np.asarray(self._cargo[cbi].corner_modal[sc.pid],
                                 dtype=np.float64)        # (3, k_full)
                G_a_full = (R @ Phi)[1, :]
                surf += float(G_a_full @ self._cargo_a[cbi])
            C = corner_y - surf
            if C >= 0.0 and sc.lam == 0.0:               # inactive: skip
                continue
            j_ang = np.array([-r_w[2], 0.0, r_w[0]])      # cross(r_w, e_y)
            inv_Iw = self._inv_I_world(bi, R)
            wb = invm[bi] + float(j_ang @ (inv_Iw @ j_ang))
            Gs = np.zeros(k)
            Gs[:rm] = -sc.U_y[midx]
            if G_a_full is not None and ck:
                Gs[rm:] = -G_a_full[cidx]
            D = wb + a_tilde
            b = -(C + a_tilde * sc.lam)
            invD = 1.0 / D
            H += invD * np.outer(Gs, Gs)                 # Σ (1/D) Gs Gsᵀ
            rhs += (invD * b) * Gs                        # Σ (1/D) b Gs
            rows.append((sc, bi, j_ang, inv_Iw, Gs, D, b))
        if not rows:
            return

        # --- dim=1 dense solve of the modal block: u = H⁻¹ rhs, H = Mz + GᵀD⁻¹G
        H[np.diag_indices(k)] += 1.0 / Mzinv             # + Mz (= diag([mq; cg_mq]))
        u = np.linalg.solve(H, rhs)

        # --- apply: SOR-damped block correction (body push + Δz to q/a). The block
        # direction is the EXACT coupled solve, so any factor ≤ 1 is stable (damped
        # descent) and reaches the same fixed point; `relax` < 1 matches the serial
        # GS gentleness so the stiff surface does not snap-respond in one substep
        # (an exact, relax=1 q-jump becomes velocity v=(x−x_prev)/h and over-energizes
        # light bodies). Body and q share the SAME factor → self-consistent.
        relax = self._support_block_relax
        dz = np.zeros(k)
        for (sc, bi, j_ang, inv_Iw, Gs, D, b) in rows:
            dlam = relax * ((b - float(Gs @ u)) / D)
            new = max(0.0, sc.lam + dlam)
            dlam = new - sc.lam
            sc.lam = new
            if dlam == 0.0:
                continue
            X[bi][1] += invm[bi] * dlam
            Q[bi] = _quat_apply_rotvec(Q[bi], (inv_Iw @ j_ang) * dlam)
            dz += Gs * dlam                              # Σ Gs Δλ
        dz *= Mzinv                                     # Δz = Mz⁻¹ Gᵀ Δλ
        q[midx] += dz[:rm]
        if ck:
            self._cargo_a[cbi][cidx] += dz[rm:]

    def _project_cargo_elastic(self, bi: int, an, h: float,
                               inv_h2: float) -> None:
        """Compliant cargo elastic block (re-expressed from
        reduced_coupled_avbd.iteration_hook's per-cargo block). Linear materials
        (fem_rigid/fem): per-mode C_i = a_i, α_i = 1/K_q[i,i], Macklin §3.5
        damped. abd: the nonlinear quartic V⊥ as re-linearized compliant
        constraints from body.elastic_constraints(a)."""
        body = self._cargo[bi]
        a = self._cargo_a[bi]
        lam = self._cargo_lam[bi]
        if getattr(body, "has_nonlinear_internal", False):
            Minv = self._cargo_Minv[bi]
            for kc, (C, grad, alpha, damp) in enumerate(
                    body.elastic_constraints(a)):
                if alpha <= 0.0:
                    continue
                at = alpha * inv_h2
                Mg = Minv @ np.asarray(grad, dtype=np.float64)
                w = float(np.asarray(grad) @ Mg)
                gamma = at * (damp * alpha) * h if damp > 0.0 else 0.0
                Cdot = float(np.asarray(grad) @ (a - an))
                denom = (1.0 + gamma) * w + at
                dlam = (-C - at * lam[kc] - gamma * Cdot) / denom
                lam[kc] += dlam
                a += Mg * dlam
        else:
            kq = np.diag(np.asarray(body.Kq_block, dtype=np.float64))
            mq = np.diag(np.asarray(body.Mq_block, dtype=np.float64))
            dq = np.diag(np.asarray(body.Dq_block, dtype=np.float64))
            for i in range(a.shape[0]):
                ki = kq[i]
                if ki <= 0.0:
                    continue
                alpha = 1.0 / ki
                at = alpha * inv_h2
                w = 1.0 / mq[i] if mq[i] > 0.0 else 0.0
                gamma = at * (dq[i] * alpha) * h if dq[i] > 0.0 else 0.0
                Cdot = a[i] - an[i]
                denom = (1.0 + gamma) * w + at
                dlam = (-a[i] - at * lam[i] - gamma * Cdot) / denom
                lam[i] += dlam
                a[i] += w * dlam

    def _project_normal(self, c: _Contact, a_tilde: float) -> None:
        """One compliant projection of the NORMAL contact (unilateral, λ_n ≥ 0).
        Resolves penetration only (gap C < 0); friction is a velocity pass."""
        X, Q, invm = self._X, self._Q, self._invm
        a, n = c.a, c.n
        Ra = _quat_to_R(Q[a])
        ra_w = Ra @ c.ra
        pa = X[a] + ra_w
        inv_Ia = self._inv_I_world(a, Ra)

        if c.b < 0:                       # floor: B static (w_b = 0)
            C = float(pa[1] - c.floor_y)  # gap; C<0 ⇒ penetrating
            w = self._gen_inv_mass(invm[a], inv_Ia, ra_w, n)
            b, rb_w, inv_Ib = -1, None, None
        else:
            b = c.b
            Rb = _quat_to_R(Q[b])
            rb_w = Rb @ c.rb
            pb = X[b] + rb_w
            inv_Ib = self._inv_I_world(b, Rb)
            C = float((pa - pb) @ n)      # n: B→A, so C<0 ⇒ overlapping
            w = (self._gen_inv_mass(invm[a], inv_Ia, ra_w, n)
                 + self._gen_inv_mass(invm[b], inv_Ib, rb_w, n))

        if C >= 0.0 or w <= 0.0:
            return
        dlam = (-C - a_tilde * c.lam_n) / (w + a_tilde)
        new = max(0.0, c.lam_n + dlam)
        dlam = new - c.lam_n
        c.lam_n = new
        p = dlam * n
        self._apply(a, p, ra_w, inv_Ia)
        if b >= 0:
            self._apply(b, -p, rb_w, inv_Ib)

    def _velocity_contact_geom(self, c: _Contact):
        """Loop-invariant velocity-solve geometry for a contact:
        (ra_w, inv_Ia, rb_w, inv_Ib). None if the contact is inactive
        (mirrors `_solve_velocity`'s `c.lam_n <= 0` early-out)."""
        if c.lam_n <= 0.0:
            return None
        Q = self._Q
        Ra = _quat_to_R(Q[c.a])
        ra_w = Ra @ c.ra
        inv_Ia = self._inv_I_world(c.a, Ra)
        if c.b < 0:
            return (ra_w, inv_Ia, None, None)
        Rb = _quat_to_R(Q[c.b])
        rb_w = Rb @ c.rb
        return (ra_w, inv_Ia, rb_w, self._inv_I_world(c.b, Rb))

    def _velocity_support_geom(self, sc: _SupportContact):
        """Loop-invariant velocity-solve geometry for a support row: (r_w,
        inv_Iw). None if inactive (mirrors `_solve_velocity_support`'s
        mu/lam/inv-mass early-outs)."""
        if sc.mu <= 0.0 or sc.lam <= 0.0:
            return None
        bi = sc.bi
        if self._invm[bi] == 0.0:
            return None
        R = _quat_to_R(self._Q[bi])
        return (R @ sc.off, self._inv_I_world(bi, R))

    def _solve_velocity(self, c: _Contact, h: float, geom=None) -> None:
        """One velocity-solve sweep for a contact (Müller 2020): inelastic normal
        restitution (null relative normal velocity, e=0) then sequential-impulse
        Coulomb friction (accumulated j_t clamped to |j_t| ≤ μ·λ_n/h).

        ``geom`` = (ra_w, inv_Ia, rb_w, inv_Ib) precomputed by the caller. The
        velocity sweeps mutate only V/W (never X/Q), so this geometry is constant
        across the iteration loop; passing it avoids recomputing R / r_w /
        inv_I_world 16× per contact. None → compute here (warp-parity reference)."""
        if c.lam_n <= 0.0:
            return
        X, Q, V, W, invm = self._X, self._Q, self._V, self._W, self._invm
        a, n = c.a, c.n
        b = c.b
        if geom is not None:
            ra_w, inv_Ia, rb_w, inv_Ib = geom
        else:
            Ra = _quat_to_R(Q[a])
            ra_w = Ra @ c.ra
            inv_Ia = self._inv_I_world(a, Ra)
            if b < 0:
                rb_w, inv_Ib = None, None
            else:
                Rb = _quat_to_R(Q[b])
                rb_w = Rb @ c.rb
                inv_Ib = self._inv_I_world(b, Rb)

        def v_rel():
            vp = V[a] + _cross3(W[a], ra_w)
            if b >= 0:
                vp = vp - (V[b] + _cross3(W[b], rb_w))
            return vp

        def apply(P):
            V[a][:] = V[a] + invm[a] * P
            W[a][:] = W[a] + inv_Ia @ _cross3(ra_w, P)
            if b >= 0:
                V[b][:] = V[b] - invm[b] * P
                W[b][:] = W[b] - inv_Ib @ _cross3(rb_w, P)

        # --- (1) inelastic normal restitution: drive v_rel·n → 0 ----------
        vn = float(v_rel() @ n)
        wn = self._gen_inv_mass(invm[a], inv_Ia, ra_w, n)
        if b >= 0:
            wn += self._gen_inv_mass(invm[b], inv_Ib, rb_w, n)
        if wn > 0.0 and abs(vn) > 1e-12:
            apply((-vn / wn) * n)

        # --- (2) Coulomb friction: null v_t, |j_t| ≤ μ·λ_n/h -------------
        if c.mu <= 0.0:
            return
        vp = v_rel()
        v_t = vp - (vp @ n) * n
        mag = _norm(v_t)
        if mag < 1e-12:
            return
        t = v_t / mag
        wt = self._gen_inv_mass(invm[a], inv_Ia, ra_w, t)
        if b >= 0:
            wt += self._gen_inv_mass(invm[b], inv_Ib, rb_w, t)
        if wt <= 0.0:
            return
        new_jt = c.jt + (-mag / wt) * t
        j_max = c.mu * self.friction_static_mult * c.lam_n / h   # Coulomb cone
        njt = _norm(new_jt)
        if njt > j_max:
            new_jt = new_jt * (j_max / njt)
        dP = new_jt - c.jt
        c.jt = new_jt
        apply(dP)

    def _solve_velocity_support(self, sc: _SupportContact, h: float,
                                geom=None) -> None:
        """Coulomb-friction velocity pass for a support row (Müller 2020, the
        friction half of `_solve_velocity`). The support normal is e_y, so this
        nulls the corner's tangential velocity, clamped to the cone
        |j_t| ≤ μ·λ_n/h with λ_n = sc.lam (the accumulated normal impulse from the
        position solve). No normal-restitution pass: the support's normal is a
        soft modal-compliant contact and an e=0 kick would corrupt the q̇ coupling.
        Mirrors `_solve_velocity` exactly so the warp kernel stays at parity.

        ``geom`` = (r_w, inv_Iw) precomputed by the caller — constant across the
        velocity sweeps (they mutate only V/W). None → compute here (reference)."""
        if sc.mu <= 0.0 or sc.lam <= 0.0:
            return
        X, Q, V, W, invm = self._X, self._Q, self._V, self._W, self._invm
        bi = sc.bi
        if invm[bi] == 0.0:
            return
        if geom is not None:
            r_w, inv_Iw = geom
        else:
            R = _quat_to_R(Q[bi])
            r_w = R @ sc.off
            inv_Iw = self._inv_I_world(bi, R)
        n = _EY
        # corner tangential velocity (support surface treated static: the slab is
        # horizontal and its q̇/ȧ motion is along e_y, i.e. normal, not tangential)
        vp = V[bi] + _cross3(W[bi], r_w)
        v_t = vp - (vp @ n) * n
        mag = _norm(v_t)
        if mag < 1e-12:
            return
        t = v_t / mag
        wt = self._gen_inv_mass(invm[bi], inv_Iw, r_w, t)
        if wt <= 0.0:
            return
        new_jt = sc.jt + (-mag / wt) * t
        j_max = sc.mu * self.friction_static_mult * sc.lam / h   # Coulomb cone
        njt = _norm(new_jt)
        if njt > j_max:
            new_jt = new_jt * (j_max / njt)
        dP = new_jt - sc.jt
        sc.jt = new_jt
        V[bi][:] = V[bi] + invm[bi] * dP
        W[bi][:] = W[bi] + inv_Iw @ _cross3(r_w, dP)

    def _apply(self, i, p, r_w, inv_I_w) -> None:
        """Apply impulse p at world offset r_w to body i: translation + rotation
        position correction (Müller 2020 applyCorrection). Mutates _X/_Q in
        place; static bodies (inv-mass 0) are immovable."""
        invm = self._invm[i]
        if invm == 0.0:
            return
        self._X[i] = self._X[i] + invm * p
        dphi = inv_I_w @ _cross3(r_w, p)
        self._Q[i] = _quat_apply_rotvec(self._Q[i], dphi)

    # -- state read-back ----------------------------------------------------
    # In device mode the resident `wp.array`s are the source of truth; these
    # accessors copy them to host on demand (outside the hot loop). In numpy
    # mode they read the numpy state directly.
    def positions(self) -> np.ndarray:
        self._ensure_arrays()
        if self._on_device:
            return self._d["X"].numpy().astype(np.float32).reshape(-1, 3)
        return np.asarray(self._X, dtype=np.float32).reshape(-1, 3)

    def orientations(self) -> np.ndarray:
        self._ensure_arrays()
        if self._on_device:
            return self._d["Q"].numpy().astype(np.float32).reshape(-1, 4)
        return np.asarray(self._Q, dtype=np.float32).reshape(-1, 4)

    def velocities(self) -> np.ndarray:
        self._ensure_arrays()
        if self._on_device:
            return self._d["V"].numpy().astype(np.float32).reshape(-1, 3)
        return np.asarray(self._V, dtype=np.float32).reshape(-1, 3)

    def angular_velocities(self) -> np.ndarray:
        self._ensure_arrays()
        if self._on_device:
            return self._d["W"].numpy().astype(np.float32).reshape(-1, 3)
        return np.asarray(self._W, dtype=np.float32).reshape(-1, 3)

    def cargo_a(self, body_idx: int) -> np.ndarray:
        if self._on_device and int(body_idx) == self._cargo_dev_bi >= 0:
            return self._d["cg_a"].numpy().astype(np.float64).reshape(-1)
        a = self._cargo_a.get(int(body_idx))
        return np.zeros(0, dtype=np.float64) if a is None else a.copy()

    def cargo_adot(self, body_idx: int) -> np.ndarray:
        if self._on_device and int(body_idx) == self._cargo_dev_bi >= 0:
            return self._d["cg_adot"].numpy().astype(np.float64).reshape(-1)
        ad = self._cargo_adot.get(int(body_idx))
        return np.zeros(0, dtype=np.float64) if ad is None else ad.copy()

    @property
    def modal_q(self) -> np.ndarray | None:
        if not self._modal:
            return None
        if self._on_device:
            return self._d["q"].numpy().astype(np.float64).reshape(-1)
        return self._q.copy()

    @property
    def modal_qdot(self) -> np.ndarray | None:
        if not self._modal:
            return None
        if self._on_device:
            return self._d["qdot"].numpy().astype(np.float64).reshape(-1)
        return self._qdot.copy()

    @property
    def max_penetration(self) -> float:
        return self._last_max_penetration
