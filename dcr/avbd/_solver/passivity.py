"""Native-path passive-energy clamp (Stage X1).

Enforces the follow-up's core inequality (foundation §15) on the NATIVE modal
constraint, per rigid substep and globally:

    ΔE_modal(substep)  ≤  η · ΔE_rigid_loss(substep)          (η = 1 ⇒ passive)
    Σ ΔE_modal_injected ≤ η · Σ ΔE_rigid_loss + ε_tol         (cumulative)

where ΔE_modal is the change in modal MECHANICAL energy E_m = ½q̇ᵀM_qq̇ + ½qᵀK_qq
this substep, and ΔE_rigid_loss is the drop in total rigid kinetic energy over the
same substep. The support can only ring on energy the rigid bodies actually lost —
the "moving support can only transfer work explicitly present in its reservoir"
invariant (`avbd_native_dcr_followup_spec_v2.md` §27).

Enforcement (foundation §6 quadratic α-cap, mirroring the reference
`dcr/dcr/dcr_world.py:_bound_dcr_velocities`): the modal velocity q̇ⁿ⁺¹ committed by
the stepper is scaled by α ∈ [0,1] so the substep's modal-energy gain fits the
budget. It is INERT (α = 1) whenever the step does not inject — i.e. whenever the
real ring gain already fits under η·(rigid loss) — so the safe-region ring
(PAPER_CONFIG, 16×4) is untouched and the clamp only bites where the un-clamped
solver injects (e.g. XPBD at 8×2).

# DEVIATION (foundation §15 is velocity-level): only q̇ is scaled, not the position
# q (which was co-solved inside the constraint and would need a re-solve to rescale).
# The elastic PE ½qᵀK_qq is therefore not re-clamped; the ledger tracks the FULL
# E_m = KE+PE and the accompanying test asserts the total inequality still holds
# (the injection pathology is a q̇ blow-up, so the velocity clamp addresses it — but
# see PassivityLedger.max_violation for the residual PE contribution).

CPU host path only: the symplectic modal step this rides on is itself host-only
(`solver_6dof.py` guards device+symplectic), so no device kernel is touched.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def _quat_to_R(qwxyz: np.ndarray) -> np.ndarray:
    """Rotation matrix from a (w,x,y,z) quaternion (project convention)."""
    w, x, y, z = (float(qwxyz[0]), float(qwxyz[1]),
                  float(qwxyz[2]), float(qwxyz[3]))
    n = w * w + x * x + y * y + z * z
    if n < 1e-30:
        return np.eye(3, dtype=np.float64)
    s = 2.0 / n
    return np.array([
        [1.0 - s * (y * y + z * z), s * (x * y - w * z),       s * (x * z + w * y)],
        [s * (x * y + w * z),       1.0 - s * (x * x + z * z), s * (y * z - w * x)],
        [s * (x * z - w * y),       s * (y * z + w * x),       1.0 - s * (x * x + y * y)],
    ], dtype=np.float64)


def _quat_to_R_batch(Q: np.ndarray) -> np.ndarray:
    """Batched (m,4) wxyz → (m,3,3) rotation, matching `_quat_to_R` elementwise
    (including the n<1e-30 degenerate-quat → identity guard: s=0 ⇒ R=I)."""
    w, x, y, z = Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3]
    nrm = w * w + x * x + y * y + z * z
    ok = nrm >= 1e-30
    s = np.where(ok, 2.0 / np.where(ok, nrm, 1.0), 0.0)
    R = np.empty((Q.shape[0], 3, 3), dtype=np.float64)
    R[:, 0, 0] = 1.0 - s * (y * y + z * z); R[:, 0, 1] = s * (x * y - w * z);       R[:, 0, 2] = s * (x * z + w * y)  # noqa: E702
    R[:, 1, 0] = s * (x * y + w * z);       R[:, 1, 1] = 1.0 - s * (x * x + z * z); R[:, 1, 2] = s * (y * z - w * x)  # noqa: E702
    R[:, 2, 0] = s * (x * z - w * y);       R[:, 2, 1] = s * (y * z + w * x);       R[:, 2, 2] = 1.0 - s * (x * x + y * y)  # noqa: E702
    return R


def local_inertia_from_invIl(invIl) -> np.ndarray:
    """Body-LOCAL inertia I_local = inv(invIl), stacked (n,3,3). A singular row
    (a static body, whose invIl is zero) maps to a zero matrix — so the caller's
    angular term drops that body, exactly as the reference loop's try/except skip.

    invIl is CONSTANT for a rigid body, so a caller stepping many substeps should
    precompute this ONCE and pass it to `rigid_mechanical_energy(..., Il=)`, which
    then skips the per-call 3×3 inversion (part of the §15 clamp's energy
    accounting cost — see docs/avbd_native/passivity_cap_cost.md).
    """
    A = np.asarray(invIl, dtype=np.float64)
    if A.ndim != 3 or A.shape[0] == 0:
        return np.zeros((0, 3, 3), dtype=np.float64)
    Il = np.zeros_like(A)
    for i in range(A.shape[0]):
        try:
            Il[i] = np.linalg.inv(A[i])
        except np.linalg.LinAlgError:
            pass   # singular ⇒ leave zero (angular contribution dropped)
    return Il


def rigid_mechanical_energy(V, W, Q_wxyz, mass, invIl, X=None, gravity=None,
                            Il=None) -> float:
    """Total rigid MECHANICAL energy Σ_b [½m‖v‖² + ½ωᵀI_worldω − m·(g·x)].

    V,W: (n,3) world linear/angular velocity. Q_wxyz: (n,4) quats in the
    PROJECT order (w,x,y,z) — warp arrays and the XPBD reference store
    (x,y,z,w) and MUST be reordered `[:, [3,0,1,2]]` at the call site
    (solver helpers `_psv_quats_wxyz`); a raw pass silently builds a wrong
    rotation and mis-weights the angular KE of rotated anisotropic bodies.
    mass: (n,) or list. invIl: (n,3,3) body-LOCAL inverse inertia
    (I_local = inv(invIl)); static bodies (m≤0) are skipped. Angular part
    uses ω_local = Rᵀω.

    Il: optional precomputed (n,3,3) LOCAL inertia = inv(invIl). Since invIl is
    constant, a caller stepping many substeps should precompute it once (via
    `local_inertia_from_invIl`) and pass it here to skip the per-call inversion.
    When None it is computed from invIl (the reference path).

    When X (n,3 positions) and gravity (3-vec accel, e.g. (0,-9.81,0)) are given,
    the gravitational potential −m·(g·x) is included, so a body settling onto the
    support (grav PE → elastic modal PE) registers as a mechanical LOSS that funds
    the modal gain. Omitting them recovers the pure-KE energy.

    Vectorized over bodies (batched Rᵀω and the quadratic forms); parity with the
    scalar reference `_rigid_mechanical_energy_loop` is asserted in
    tests/avbd_native/test_passivity_energy_vectorized.py.
    """
    mass = np.asarray(mass, dtype=np.float64)
    if mass.shape[0] == 0:
        return 0.0
    dyn = mass > 0.0
    if not np.any(dyn):
        return 0.0
    V = np.asarray(V, dtype=np.float64)[dyn]
    W = np.asarray(W, dtype=np.float64)[dyn]
    Q = np.asarray(Q_wxyz, dtype=np.float64)[dyn]
    m = mass[dyn]

    # linear KE  Σ ½ m‖v‖²
    E = 0.5 * float(np.einsum("i,ij,ij->", m, V, V))

    # angular KE  Σ ½ ω_localᵀ I_local ω_local,  ω_local = Rᵀω
    if Il is None:
        Il = local_inertia_from_invIl(invIl)
    Il = np.asarray(Il, dtype=np.float64)[dyn]
    R = _quat_to_R_batch(Q)
    wl = np.einsum("mji,mj->mi", R, W)                 # Rᵀω
    E += 0.5 * float(np.einsum("mi,mij,mj->", wl, Il, wl))

    # gravitational PE  Σ −m(g·x)
    if X is not None and gravity is not None:
        X = np.asarray(X, dtype=np.float64)[dyn]
        gravity = np.asarray(gravity, dtype=np.float64)
        E += -float(np.einsum("i,ij,j->", m, X, gravity))
    return E


def _rigid_mechanical_energy_loop(V, W, Q_wxyz, mass, invIl, X=None,
                                  gravity=None) -> float:
    """Scalar reference for `rigid_mechanical_energy` (CLAUDE.md rule 6: keep the
    obvious-correct version). Retained as the parity oracle for the vectorized
    path; not used on the hot path. Q_wxyz: project order (w,x,y,z)."""
    V = np.asarray(V, dtype=np.float64)
    W = np.asarray(W, dtype=np.float64)
    Q = np.asarray(Q_wxyz, dtype=np.float64)
    use_grav = X is not None and gravity is not None
    if use_grav:
        X = np.asarray(X, dtype=np.float64)
        gravity = np.asarray(gravity, dtype=np.float64)
    E = 0.0
    for i in range(len(mass)):
        m = float(mass[i])
        if m <= 0.0:
            continue
        E += 0.5 * m * float(V[i] @ V[i])
        Ii = np.asarray(invIl[i], dtype=np.float64)
        try:
            Il = np.linalg.inv(Ii)
        except np.linalg.LinAlgError:
            Il = None
        if Il is not None:
            wl = _quat_to_R(Q[i]).T @ W[i]
            E += 0.5 * float(wl @ (Il @ wl))
        if use_grav:
            E += -m * float(gravity @ X[i])
    return E


# backward-compatible alias (pure kinetic when X/gravity omitted)
rigid_kinetic_energy = rigid_mechanical_energy


def modal_mech_energy(qdot, q, Mq, Kq) -> tuple[float, float]:
    """(KE, PE) for the modal state. Mq/Kq may be (r,) diagonals or (r,r) matrices."""
    qdot = np.asarray(qdot, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    Mq = np.asarray(Mq, dtype=np.float64)
    Kq = np.asarray(Kq, dtype=np.float64)
    ke = 0.5 * float(qdot @ (Mq * qdot)) if Mq.ndim == 1 else 0.5 * float(qdot @ (Mq @ qdot))
    pe = 0.5 * float(q @ (Kq * q)) if Kq.ndim == 1 else 0.5 * float(q @ (Kq @ q))
    return ke, pe


def passivity_alpha(ke_new: float, pe_new: float, e_modal_old: float,
                    budget: float, tol: float = 1e-12) -> float:
    """Largest α ∈ [0,1] with α²·KE_new + PE_new − E_m_old ≤ budget (foundation §6).

    Velocity-only cap: scaling q̇ by α scales KE_new by α². Returns 1.0 (inert)
    when the unscaled step already fits, 0.0 when even α=0 cannot fit (PE alone
    overshoots). Retained for the unit test; the solver uses `passivity_gamma`,
    which also bounds the PE term.
    """
    allowed_ke = budget + e_modal_old - pe_new
    if ke_new <= allowed_ke + tol:
        return 1.0
    if allowed_ke <= 0.0:
        return 0.0
    return float(np.sqrt(max(0.0, allowed_ke / max(ke_new, 1e-300))))


def passivity_gamma(e_modal_new: float, e_modal_old: float,
                    budget: float, tol: float = 1e-12) -> float:
    """Largest γ ∈ [0,1] scaling the FULL modal state (q, q̇) so the substep's
    modal-energy gain fits the budget (foundation §15):

        γ²·E_m_new − E_m_old ≤ budget      ⇒   γ = √((E_m_old + budget)/E_m_new)

    Scaling both q and q̇ by γ scales E_m = ½q̇ᵀMq̇ + ½qᵀKq by γ² (both terms are
    quadratic), so this bounds KE AND PE — unlike the velocity-only α. Returns 1.0
    (inert) when the step already fits; when it binds, it is a projection of the
    over-shot modal state onto the passive manifold (the support cannot store more
    energy than the contact delivered). γ=1 whenever the solver is well-converged
    and the ring is already passive, so the safe region is untouched.
    """
    ceiling = e_modal_old + budget
    if e_modal_new <= ceiling + tol:
        return 1.0
    if ceiling <= 0.0:
        return 0.0
    return float(np.sqrt(max(0.0, ceiling / max(e_modal_new, 1e-300))))


@dataclass
class PassivityLedger:
    """RESERVOIR energy ledger for the closed-system invariant (foundation §15).

    A per-substep budget is too tight — free modal oscillation and delayed
    re-excitation would trip it spuriously and damp the safe-region ring. Instead
    a reservoir accumulates the rigid energy lost (× η) and is debited by realized
    modal gains; the clamp fires only when the reservoir is empty. This makes the
    guarantee CUMULATIVE (Σ modal_gain ≤ η·Σ rigid_loss) while staying inert
    whenever slack remains — exactly the "reservoir" passivity the spec calls for.
    """
    eta: float = 1.0
    tol: float = 1e-9
    reservoir: float = 0.0          # available budget [J] (never negative)
    cum_modal_gain: float = 0.0     # Σ realized positive modal-energy gains (post-clamp)
    cum_rigid_loss: float = 0.0     # Σ max(rigid KE lost, 0)
    e_modal_0: float = 0.0          # modal energy at run start (rest ⇒ 0)
    max_net_excess: float = -1e300  # max over t of E_modal(t) − E_modal(0) − η·Σloss(t)
    max_deposit: float = 0.0        # largest single-substep η·loss (accounting granularity)
    n_steps: int = 0
    n_clamped: int = 0
    max_violation: float = 0.0      # worst per-step (realized gain − budget), >0 = leak
    alphas: list = field(default_factory=list)

    def deposit(self, rigid_loss: float) -> float:
        """Credit η·max(rigid_loss,0) into the reservoir; return the new budget."""
        dep = self.eta * max(rigid_loss, 0.0)
        self.cum_rigid_loss += max(rigid_loss, 0.0)
        self.reservoir += dep
        self.max_deposit = max(self.max_deposit, dep)
        return self.reservoir

    def commit(self, realized_gain: float, budget: float, alpha: float,
               e_modal_now: float = None) -> None:
        """Debit realized positive modal gain; update both invariants.

        realized_gain = ΔE_m this substep (post-clamp). e_modal_now = absolute modal
        mechanical energy after this substep, used for the NET invariant
        E_modal(t) − E_modal(0) ≤ η·Σloss(t) (robust to KE↔PE oscillation and
        re-excitation double-counting, unlike the cumulative-gain metric).
        """
        self.n_steps += 1
        if alpha < 1.0:
            self.n_clamped += 1
        g = max(realized_gain, 0.0)
        self.reservoir = max(self.reservoir - g, 0.0)
        self.cum_modal_gain += g
        self.max_violation = max(self.max_violation, realized_gain - budget)
        if e_modal_now is not None:
            excess = (e_modal_now - self.e_modal_0
                      - self.eta * self.cum_rigid_loss)
            self.max_net_excess = max(self.max_net_excess, excess)
        self.alphas.append(float(alpha))

    def passive(self) -> bool:
        """Physical invariant: peak modal energy never exceeds its initial value
        plus η·cumulative rigid loss (foundation §15), allowing a one-substep
        in-transit lead (the accounting granularity — modal PE can spike in the
        same substep the rigid body is still delivering KE). Works for monitor-mode.
        """
        return self.max_net_excess <= self.max_deposit + self.tol

    def holds(self) -> bool:
        """Cumulative Σ realized modal gain ≤ η·Σ rigid_loss + tol (reservoir form)."""
        return self.cum_modal_gain <= self.eta * self.cum_rigid_loss + self.tol

    def reset(self) -> None:
        self.reservoir = self.cum_modal_gain = self.cum_rigid_loss = 0.0
        self.max_net_excess = -1e300
        self.n_steps = self.n_clamped = 0
        self.max_violation = 0.0
        self.alphas.clear()
