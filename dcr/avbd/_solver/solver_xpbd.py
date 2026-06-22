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

from .solver_6dof import RigidBody, box_inv_inertia_local

__all__ = ["SolverXPBD"]

_STAGE3 = ("SolverXPBD reduced-modal support lands in Stage 3 of "
           "prompts/native_dual_solver_build_plan.md.")
_STAGE4 = ("SolverXPBD cargo materials land in Stage 4 of "
           "prompts/native_dual_solver_build_plan.md.")


# ---------------------------------------------------------------------------
# Local numpy quaternion helpers (XYZW). Self-contained so the standalone solver
# carries no dependency on the coupler modules (deleted in Stage 6).
# ---------------------------------------------------------------------------

def _quat_to_R(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotation matrix from an XYZW quaternion."""
    x, y, z, w = q
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.array([
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ], dtype=np.float64)


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
    s = float(np.linalg.norm(v))
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
    n = float(np.linalg.norm(qn))
    return qn / n if n > 1e-12 else np.array([0.0, 0.0, 0.0, 1.0])


def _quat_apply_rotvec(q: NDArray[np.float64],
                       dphi: NDArray[np.float64]) -> NDArray[np.float64]:
    """Apply a small rotation-vector correction dφ to an XYZW orientation:
    q⁺ = normalize(q + ½ (dφ,0) ⊗ q)  (Müller 2020 applyRotation)."""
    wq = np.array([dphi[0], dphi[1], dphi[2], 0.0], dtype=np.float64)
    qn = q + 0.5 * _quat_mul(wq, q)
    n = float(np.linalg.norm(qn))
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
    def set_modal_support(self, *args, **kwargs) -> None:
        raise NotImplementedError(_STAGE3)

    def add_support_contact_corner(self, *args, **kwargs) -> int:
        raise NotImplementedError(_STAGE3)

    # -- cargo (Stage 4) ----------------------------------------------------
    def add_cargo(self, *args, **kwargs) -> None:
        raise NotImplementedError(_STAGE4)

    def add_cargo_native(self, *args, **kwargs) -> None:
        raise NotImplementedError(_STAGE4)

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
        """One frame = `substeps` Macklin small-steps (CPU reference path)."""
        self._ensure_arrays()
        h = self.dt / self.substeps
        for _ in range(self.substeps):
            self._substep_cpu(h)

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
        for _ in range(self.iterations):
            for c in contacts:
                self._project_normal(c, a_tilde)

        # ---- velocity update v = (x − x_prev)/h, ω = log(Δq)/h ----------
        for i in range(n):
            if invm[i] == 0.0:
                continue
            V[i] = (X[i] - x_prev[i]) / h
            dq = _quat_mul(Q[i], _quat_inv(q_prev[i]))
            W[i] = _quat_to_rotvec(dq) / h

        # ---- velocity solve (Müller 2020 §SolveVelocities) --------------
        # Per active contact: (1) inelastic normal restitution — null the
        # relative normal velocity (e=0), which removes the spurious "bounce"
        # the position projection injects into v=(x−x_prev)/h (left in, an upper
        # box launches off a lower one); (2) sequential-impulse Coulomb friction,
        # accumulated per contact and clamped to the cone |j_t| ≤ μ·λ_n/h.
        for c in contacts:
            c.jt = np.zeros(3, dtype=np.float64)
        for _ in range(self.iterations):
            for c in contacts:
                self._solve_velocity(c, h)

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
            L = np.linalg.norm(axis)
            if L < 1e-10:
                return np.inf
            axis = axis / L
            pa = sum(ha[k] * abs(axes_a[k] @ axis) for k in range(3))
            pb = sum(hb[k] * abs(axes_b[k] @ axis) for k in range(3))
            return pa + pb - abs(d @ axis)

        def orient(axis):
            nn = axis / np.linalg.norm(axis)
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
                ov = overlap(np.cross(a, b))
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
        rn = np.cross(r, n)
        return float(inv_m + rn @ (inv_I_w @ rn))

    def _penetration(self, c: _Contact) -> float:
        """Current penetration depth (positive = overlapping) along c.n."""
        X, Q = self._X, self._Q
        pa = X[c.a] + _quat_to_R(Q[c.a]) @ c.ra
        if c.b < 0:
            return max(0.0, c.floor_y - pa[1])
        pb = X[c.b] + _quat_to_R(Q[c.b]) @ c.rb
        return max(0.0, float((pb - pa) @ c.n))

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

    def _solve_velocity(self, c: _Contact, h: float) -> None:
        """One velocity-solve sweep for a contact (Müller 2020): inelastic normal
        restitution (null relative normal velocity, e=0) then sequential-impulse
        Coulomb friction (accumulated j_t clamped to |j_t| ≤ μ·λ_n/h)."""
        if c.lam_n <= 0.0:
            return
        X, Q, V, W, invm = self._X, self._Q, self._V, self._W, self._invm
        a, n = c.a, c.n
        Ra = _quat_to_R(Q[a])
        ra_w = Ra @ c.ra
        inv_Ia = self._inv_I_world(a, Ra)
        if c.b < 0:
            b, rb_w, inv_Ib = -1, None, None
        else:
            b = c.b
            Rb = _quat_to_R(Q[b])
            rb_w = Rb @ c.rb
            inv_Ib = self._inv_I_world(b, Rb)

        def v_rel():
            vp = V[a] + np.cross(W[a], ra_w)
            if b >= 0:
                vp = vp - (V[b] + np.cross(W[b], rb_w))
            return vp

        def apply(P):
            V[a][:] = V[a] + invm[a] * P
            W[a][:] = W[a] + inv_Ia @ np.cross(ra_w, P)
            if b >= 0:
                V[b][:] = V[b] - invm[b] * P
                W[b][:] = W[b] - inv_Ib @ np.cross(rb_w, P)

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
        mag = float(np.linalg.norm(v_t))
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
        njt = float(np.linalg.norm(new_jt))
        if njt > j_max:
            new_jt = new_jt * (j_max / njt)
        dP = new_jt - c.jt
        c.jt = new_jt
        apply(dP)

    def _apply(self, i, p, r_w, inv_I_w) -> None:
        """Apply impulse p at world offset r_w to body i: translation + rotation
        position correction (Müller 2020 applyCorrection). Mutates _X/_Q in
        place; static bodies (inv-mass 0) are immovable."""
        invm = self._invm[i]
        if invm == 0.0:
            return
        self._X[i] = self._X[i] + invm * p
        dphi = inv_I_w @ np.cross(r_w, p)
        self._Q[i] = _quat_apply_rotvec(self._Q[i], dphi)

    # -- state read-back ----------------------------------------------------
    def positions(self) -> np.ndarray:
        self._ensure_arrays()
        return np.asarray(self._X, dtype=np.float32).reshape(-1, 3)

    def orientations(self) -> np.ndarray:
        self._ensure_arrays()
        return np.asarray(self._Q, dtype=np.float32).reshape(-1, 4)

    def velocities(self) -> np.ndarray:
        self._ensure_arrays()
        return np.asarray(self._V, dtype=np.float32).reshape(-1, 3)

    def angular_velocities(self) -> np.ndarray:
        self._ensure_arrays()
        return np.asarray(self._W, dtype=np.float32).reshape(-1, 3)

    def cargo_a(self, body_idx: int) -> np.ndarray:
        return np.zeros(0, dtype=np.float64)

    def cargo_adot(self, body_idx: int) -> np.ndarray:
        return np.zeros(0, dtype=np.float64)

    @property
    def modal_q(self) -> np.ndarray | None:
        return None

    @property
    def modal_qdot(self) -> np.ndarray | None:
        return None

    @property
    def max_penetration(self) -> float:
        return self._last_max_penetration
