"""Homogeneous (free) damped SDOF modal stepper (Stage E3).

# DEVIATION: Replaces the forced-IIR injection of Stage 4/5 with
# initial-condition perturbation to qdot (foundation §15).
# The injection enters as a velocity kick to qdot before stepping,
# not as an impulse forcing term inside Eq. 10.

Option A (preferred): exact exponential integrator for a damped harmonic
oscillator. For each mode j with (omega_j, zeta_j), the 2x2 state-transition
matrix over sub-step T is closed-form:

    [q(T)   ]     [q(0)   ]
    [qdot(T)] = A [qdot(0)]

where A = exp(-zeta*omega*T) * rotation-like matrix in (q, qdot) space.

See passive_energy_injection_implementation_prompt.md E3.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class HomogeneousStepper:
    """Exact exponential integrator for decoupled damped SDOF modes.

    Maintains explicit (q, qdot) state per mode. Each sub-step applies
    the closed-form solution of q'' + 2*zeta*omega*q' + omega^2*q = 0.

    Attributes:
        omega: (n_modes,) natural frequencies in rad/s.
        zeta: (n_modes,) damping ratios (per-mode Rayleigh damping).
        T: Sub-step size (= pi / (2 * omega_max), same as IIR convention).
        gamma: End-of-rigid-step modal-state attenuation in [0, 1].
            Caller invokes apply_rigid_step_decay() after each rigid step's
            step_n() to multiply (q, qdot) by gamma. gamma=1.0 (default) is
            persistent state (the §15 main method). gamma=0.0 is the original
            DCR-style per-step reset (paper §4.5), as the limiting case of
            our framework. Intermediate gamma is opt-in explicit dissipation.
            # DEVIATION from foundation §15: gamma < 1 introduces explicit
            # numerical dissipation outside the Rayleigh-damping model.
            # Energy removed by this operator is dissipation, NOT a refund
            # to the §15 reservoir (would let one rigid impact fund
            # unlimited future kicks; see CONTRIBUTIONS.md §6).
        q: (n_modes,) modal displacement.
        qdot: (n_modes,) modal velocity.
    """

    omega: NDArray[np.float64]
    zeta: NDArray[np.float64]
    T: float
    gamma: float = 1.0

    q: NDArray[np.float64] = field(init=False, repr=False)
    qdot: NDArray[np.float64] = field(init=False, repr=False)

    # Precomputed per-mode 2x2 state transition matrix entries.
    _A00: NDArray[np.float64] = field(init=False, repr=False)
    _A01: NDArray[np.float64] = field(init=False, repr=False)
    _A10: NDArray[np.float64] = field(init=False, repr=False)
    _A11: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0.0 <= self.gamma <= 1.0:
            raise ValueError(f"gamma must be in [0, 1]; got {self.gamma}")
        m = len(self.omega)
        self.q = np.zeros(m, dtype=np.float64)
        self.qdot = np.zeros(m, dtype=np.float64)
        self._precompute_transition()

    def _precompute_transition(self) -> None:
        """Precompute the 2x2 state transition matrix per mode.

        For underdamped mode j (zeta_j < 1):
            omega_d = omega_j * sqrt(1 - zeta_j^2)
            e = exp(-zeta_j * omega_j * T)

            A = e * [ cos(wd*T) + (zeta*omega/wd)*sin(wd*T),    sin(wd*T)/wd       ]
                    [ -(omega^2/wd)*sin(wd*T),                    cos(wd*T) - (zeta*omega/wd)*sin(wd*T) ]
        """
        m = len(self.omega)
        self._A00 = np.zeros(m)
        self._A01 = np.zeros(m)
        self._A10 = np.zeros(m)
        self._A11 = np.zeros(m)
        T = self.T

        for j in range(m):
            wj = self.omega[j]
            xj = self.zeta[j]

            if wj < 1e-12:
                # Near-zero frequency: q(T) = q(0) + T*qdot(0), qdot unchanged
                self._A00[j] = 1.0
                self._A01[j] = T
                self._A10[j] = 0.0
                self._A11[j] = 1.0
                continue

            xj = min(xj, 0.9999)  # clamp to underdamped
            wd = wj * np.sqrt(1.0 - xj**2)
            e = np.exp(-xj * wj * T)
            cos_wd = np.cos(wd * T)
            sin_wd = np.sin(wd * T)
            xw = xj * wj  # zeta * omega

            self._A00[j] = e * (cos_wd + xw / wd * sin_wd)
            self._A01[j] = e * sin_wd / wd
            self._A10[j] = e * (-(wj**2) / wd * sin_wd)
            self._A11[j] = e * (cos_wd - xw / wd * sin_wd)

    def reset(self) -> None:
        """Reset modal state to zero."""
        self.q[:] = 0.0
        self.qdot[:] = 0.0

    def apply_rigid_step_decay(self) -> float:
        """Apply (q, qdot) *= gamma at the end of a rigid step. Returns the
        modal energy dissipated by the operator (foundation §16; #DEVIATION
        from §15 for gamma < 1).

        With mass-normalized modes, E_modal = ½ q̇ᵀq̇ + ½ qᵀΩ²q scales by
        gamma² under the (q, qdot) *= gamma operator, so the dissipation is
        (1 − gamma²) · E_modal_pre. Returned for energy logging — must NOT
        be refunded to the §15 reservoir.

        Caller (passive_dcr.py) invokes this ONCE per rigid step, AFTER
        step_n() and AFTER the DCR response has been computed from the
        transient q_history (the displacement work must happen before
        the attenuation).
        """
        if self.gamma == 1.0:
            return 0.0
        E_pre = 0.5 * float(np.dot(self.qdot, self.qdot)) + \
            0.5 * float(np.dot(self.q, self.omega ** 2 * self.q))
        self.q *= self.gamma
        self.qdot *= self.gamma
        return (1.0 - self.gamma ** 2) * E_pre

    def step(self) -> None:
        """Advance one sub-step T using the exact state transition.

        [q_new]     [A00 A01] [q_old]
        [qdot_new] = [A10 A11] [qdot_old]
        """
        q_old = self.q.copy()
        qdot_old = self.qdot.copy()
        self.q = self._A00 * q_old + self._A01 * qdot_old
        self.qdot = self._A10 * q_old + self._A11 * qdot_old

    def step_n(self, n_steps: int) -> NDArray[np.float64]:
        """Step n_steps sub-steps. Returns (n_steps, n_modes) displacement history.

        # DEVIATION from Stage 4 IIR: no forcing term. Injection enters via
        # qdot kick before calling step_n (foundation §15).
        """
        m = len(self.omega)
        q_history = np.zeros((n_steps, m), dtype=np.float64)

        for k in range(n_steps):
            self.step()
            q_history[k] = self.q

        return q_history

    def transient_step_n(
        self, qdot_kick: NDArray[np.float64], n_steps: int,
    ) -> NDArray[np.float64]:
        """Step from (q=0, qdot=qdot_kick) for n_steps. Pure — no side effects.

        Computes the transient response to a single velocity kick, using the
        same precomputed transition matrices as the persistent stepper.
        Does NOT modify self.q or self.qdot.

        This separates the displacement response (transient, for DCR Eqs. 11-13)
        from the persistent energy state (for the passivity bound, foundation §15).

        Args:
            qdot_kick: (n_modes,) initial velocity (typically alpha * s_total).
            n_steps: Number of sub-steps.

        Returns:
            q_history: (n_steps, n_modes) transient displacement history.
        """
        m = len(self.omega)
        q_history = np.zeros((n_steps, m), dtype=np.float64)
        q = np.zeros(m, dtype=np.float64)
        qdot = qdot_kick.copy()

        for k in range(n_steps):
            q_new = self._A00 * q + self._A01 * qdot
            qdot_new = self._A10 * q + self._A11 * qdot
            q = q_new
            qdot = qdot_new
            q_history[k] = q

        return q_history

    @classmethod
    def from_modal_analysis(cls, modal, gamma: float = 1.0) -> "HomogeneousStepper":
        """Construct from a ModalAnalysis instance, matching IIR stepper conventions.

        See the class docstring for `gamma` semantics (default 1.0 = persistent
        state, the §15 main method).
        """
        omega = modal.frequencies.copy()
        alpha0 = modal.fem.alpha0
        alpha1 = modal.fem.alpha1

        m = modal.num_modes
        zeta = np.zeros(m, dtype=np.float64)
        for j in range(m):
            if omega[j] > 0:
                zeta[j] = (alpha0 / omega[j] + alpha1 * omega[j]) / 2.0
        zeta = np.clip(zeta, 0.0, 0.9999)

        omega_max = omega[-1] if omega[-1] > 0 else 1.0
        T = np.pi / (2.0 * omega_max)

        return cls(omega=omega, zeta=zeta, T=T, gamma=gamma)
