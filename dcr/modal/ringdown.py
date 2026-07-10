"""Reference-relative modal ring-down ("settle") operator.

Removes the *oscillatory* part of a reduced modal state (q, q̇) after the
contact response has been delivered, so a large support (table / shelf)
reads as visually rigid within a controllable time instead of ringing at
its physical decay rate. DCR gets this look for free because its vibration
is a per-impact ghost computation (paper §4.5 resets the IIR state every
excitation and never renders it); on the native path the modal state is the
live contact surface, so the equivalent must be an explicit, snap-free,
energy-audited dissipation channel.

Both mechanisms are VELOCITY-ONLY, hence position-continuous, hence
engaged-safe under unilateral contact (a surface whose motion stops can
only stop pushing — it cannot create penetration or extract work):

* ``kill``: per mode i, once armed, zero q̇_i at the first crossing of the
  slowly-tracked sag reference q̄_i. At the crossing the mode's oscillation
  energy is purely kinetic, so the removal is exactly ½ m_i q̇_i² and the
  mode is dead within half its own period of the arm instant.
* ``damp``: per mode i, once armed, apply the extra viscous decay factor
  exp(−ζ_extra,i ω_i h) per substep, sizing total damping to
  ``zeta_target`` (≈ critical). Smooth cousin of ``kill``; the position
  recovers to q̄ through the mode's own stiffness.

Arming (the "impact latch"): the operator engages only ``delay`` seconds
after the last *excitation* — a positive jump of the oscillation energy
about q̄ — and re-arms on every new excitation, so impacts and re-landings
each get their launch half-cycle delivered before removal begins. This is
the inverse of a wait-for-quiet gate: ring-induced contact chatter cannot
starve it.

The sag reference q̄ is a low-pass EMA of q (time constant ``qbar_tau``).
It must be SLOW: an instantaneous static solve spikes under impact forces
and would move the crossing targets mid-impact (the lesson of the old
coupler-era low-pass fix). Correctness never depends on q̄ accuracy — the
operator touches only velocities, so a converging q̄ merely shifts *when*
kills fire, never *what* they do.

Energy contract (identical to homogeneous_stepper.apply_rigid_step_decay):
every removed Joule is returned to the caller for logging as dissipation
(foundation §9: E_diss = E_before − E_after; §11: the E_internal_damping
channel) and must NOT be refunded to the §15 reservoir.

# DEVIATION: a scheduled ring-down appears in neither the DCR paper nor the
# foundation document. It is an artistic, strictly-dissipative operator —
# it only ever removes modal kinetic energy, so the §15 core inequality
# (ΔE_modal ≤ η·ΔE_rigid_loss) and §11's dE_modal/dt ≤ 0 (without input)
# are strengthened, never violated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


def _as_diag(M, name: str) -> NDArray[np.float64]:
    """Return the (r,) diagonal of M; reject non-diagonal reduced matrices.

    Per-mode ring-down semantics (per-mode ω, ζ, crossings) require the
    eigenbasis: M_q, K_q, D_q diagonal. Synthetic dense bases must be built
    with ``to_eigenbasis=True`` first.
    """
    M = np.asarray(M, dtype=np.float64)
    if M.ndim == 1:
        return M.copy()
    d = np.diag(M).copy()
    off = float(np.abs(M - np.diag(d)).max()) if M.size else 0.0
    if off > 1e-10 * max(1.0, float(np.abs(d).max())):
        raise ValueError(
            f"ModalRingdown requires a diagonal (eigenbasis) {name}; "
            f"max off-diagonal {off:.3e}. Build the support with "
            "to_eigenbasis=True.")
    return d


@dataclass
class RingdownConfig:
    mode: str = "kill"              # "kill" | "damp"
    # Arm delay after the last excitation. This is the DISTANT-RESPONSE
    # window: on the native path the ring is the carrier of the distant
    # kick, which builds over several carrier periods (dinner: plates
    # 0.4–0.8 m out reach full hop apex ~0.14 s after the pot impact, and
    # delay=0.15 preserves it exactly; 0.05 eats ~30%). Lower it for
    # snappier stillness at the price of range-of-effect. For a ring the
    # solver barely damps, worst-case arming adds ~1.5·e_ema_tau on top
    # (the latch waits for the energy EMA to catch up before going quiet).
    delay: float = 0.15             # [s]
    qbar_tau: float = 0.3           # [s] EMA time constant of the sag reference
    # Excitation = E_osc exceeding (1 + rearm_rel)·EMA(E_osc) + rearm_threshold.
    # The RELATIVE margin against a slow energy EMA is load-bearing: a plain
    # absolute jump detector re-arms on the conservative fluctuation of the
    # discrete energy (symplectic modal step ⇒ E_osc oscillates within a
    # period without any injection) and the operator then never engages —
    # the very failure mode ("not doing the work") of the rolled-back settle.
    rearm_threshold: float = 1e-7   # [J] absolute floor
    rearm_rel: float = 0.5          # relative exceedance over the energy EMA
    e_ema_tau: float = 0.1          # [s] time constant of the energy EMA
    zeta_target: float = 1.0        # "damp": total damping ratio aimed for


@dataclass
class ModalRingdown:
    """Stateful per-support ring-down operator. Mutates q̇ in place, never q.

    Call :meth:`apply` once per substep AFTER the modal commit (and after any
    §15 passivity clamp, so removed energy is never misattributed as an
    injection). Returns the energy removed that substep; the caller owns
    accumulating it into its dissipation ledger.
    """

    mq: NDArray[np.float64]
    kq: NDArray[np.float64]
    dq: NDArray[np.float64]
    cfg: RingdownConfig
    q0: NDArray[np.float64] | None = None

    # -- derived / state (built in __post_init__) --------------------------
    omega: NDArray[np.float64] = field(init=False)
    zeta: NDArray[np.float64] = field(init=False)
    qbar: NDArray[np.float64] = field(init=False)
    cum_dissipated: float = field(init=False, default=0.0)
    last_dissipated: float = field(init=False, default=0.0)
    n_kills: int = field(init=False, default=0)
    _prev_dev: NDArray[np.float64] | None = field(init=False, default=None)
    _E_ema: float | None = field(init=False, default=None)
    _E_env: float = field(init=False, default=0.0)
    _t_quiet: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.mq = _as_diag(self.mq, "M_q")
        self.kq = _as_diag(self.kq, "K_q")
        self.dq = _as_diag(self.dq, "D_q")
        if self.cfg.mode not in ("kill", "damp"):
            raise ValueError(f"unknown ring-down mode {self.cfg.mode!r}")
        m = np.maximum(self.mq, 1e-300)
        self.omega = np.sqrt(np.maximum(self.kq, 0.0) / m)
        w = np.maximum(self.omega, 1e-12)
        self.zeta = self.dq / (2.0 * m * w)
        r = self.mq.shape[0]
        self.qbar = (np.zeros(r) if self.q0 is None
                     else np.asarray(self.q0, dtype=np.float64).copy())

    # ------------------------------------------------------------------
    def energy_about_qbar(self, q, qdot) -> float:
        """Oscillation energy about the sag reference (mass-normalized modes:
        E_osc = ½ q̇ᵀM_q q̇ + ½ (q−q̄)ᵀK_q (q−q̄); foundation §9 measurement
        frame)."""
        dev = q - self.qbar
        return float(0.5 * (self.mq * qdot) @ qdot
                     + 0.5 * (self.kq * dev) @ dev)

    def apply(self, q: NDArray[np.float64], qdot: NDArray[np.float64],
              h: float) -> float:
        """Advance the latch and, when armed, remove oscillation velocity.

        Mutates ``qdot`` in place; ``q`` is read-only (position continuity by
        construction). Returns the modal energy removed this call [J].
        """
        # 1. Sag reference EMA (slow; see module docstring).
        a = 1.0 - np.exp(-h / max(self.cfg.qbar_tau, 1e-9))
        self.qbar += a * (q - self.qbar)
        dev = q - self.qbar

        # 2. Excitation latch. The delay window re-arms whenever E_osc
        # exceeds the fast-rise/slow-decay reference
        #     ref = max(EMA(E_osc), envelope)
        # by the relative margin (+ absolute floor); the envelope is then set
        # to E and decays with e_ema_tau. The envelope term is load-bearing
        # twice over: (a) it makes the trigger scale-aware — a J-scale impact
        # over a µJ-scale settling baseline always re-arms, even if the µJ
        # exceedance never cleared (a naive rising-edge detector latches on
        # the micro-regime and then misses the real impact, and the kill
        # fires mid-delivery of the distant response); (b) it prevents
        # re-arming on the same event's own decay or on the EMA catch-up, so
        # the post-impact latency is exactly `delay` from the end of the
        # impact's energy build-up.
        E = self.energy_about_qbar(q, qdot)
        if self._E_ema is None:
            self._E_ema = E
        ref = max(self._E_ema, self._E_env)
        tau = max(self.cfg.e_ema_tau, 1e-9)
        self._E_ema += (1.0 - np.exp(-h / tau)) * (E - self._E_ema)
        if E > (1.0 + self.cfg.rearm_rel) * ref + self.cfg.rearm_threshold:
            self._t_quiet = 0.0
            self._E_env = E
        else:
            self._t_quiet += h
            self._E_env *= np.exp(-h / tau)
        armed = self._t_quiet >= self.cfg.delay

        D = 0.0
        if armed:
            ke = 0.5 * self.mq * qdot * qdot
            if self.cfg.mode == "kill":
                if self._prev_dev is not None:
                    # q̄-crossing since the previous substep (sign change of
                    # the deviation) ⇒ the mode's oscillation energy is (to
                    # within one substep of phase) kinetic: zero q̇_i there.
                    crossed = (dev * self._prev_dev) < 0.0
                    if np.any(crossed):
                        D = float(ke[crossed].sum())
                        qdot[crossed] = 0.0
                        self.n_kills += int(np.count_nonzero(crossed))
            else:  # "damp"
                z_extra = np.maximum(self.cfg.zeta_target - self.zeta, 0.0)
                s = np.exp(-z_extra * self.omega * h)
                D = float((ke * (1.0 - s * s)).sum())
                qdot *= s

        self._prev_dev = dev
        if D > 0.0:                       # let the EMA see the removal too
            self._E_ema = min(self._E_ema, E - D)
        self.last_dissipated = D
        self.cum_dissipated += D
        return D
