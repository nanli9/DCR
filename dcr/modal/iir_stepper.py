"""IIR modal stepper (paper Eq. 10, James & Pai 2002).

Each retained mode j is advanced as a second-order IIR filter:

    q_j^(k) = a_{1,j} q_j^(k-1) - a_{2,j} q_j^(k-2)
              + a_{r,j} * (r_j^(k-1) / (m_j T))          (Eq. 10)

The sub-step size T = π / (2 ω_max) ensures the Nyquist criterion is
satisfied for the highest retained mode (§4.1).

Filter coefficients are derived from the per-mode SDOF system (Eq. 8):

    q̈_j + 2 ξ_j ω_j q̇_j + ω_j² q_j = r_j / m_j

Discretized via the exact z-transform of the damped oscillator impulse
response (James & Pai 2002, §3):

    a_{1,j} = 2 exp(-ξ_j ω_j T) cos(ω_{d,j} T)
    a_{2,j} = exp(-2 ξ_j ω_j T)
    a_{r,j} = exp(-ξ_j ω_j T) sin(ω_{d,j} T) / ω_{d,j}

where ω_{d,j} = ω_j √(1 - ξ_j²) is the damped frequency and the
damping ratio ξ_j comes from Rayleigh damping:

    ξ_j = (α₀ / ω_j + α₁ ω_j) / 2
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .modal_analysis import ModalAnalysis


@dataclass
class IIRModalStepper:
    """IIR filter stepper for decoupled modal ODEs (Eq. 10).

    Attributes:
        modal: Modal analysis results (frequencies, damping, etc.).
    """

    modal: ModalAnalysis

    # Cached per-mode IIR coefficients.
    a1: NDArray[np.float64] = field(init=False, repr=False)
    a2: NDArray[np.float64] = field(init=False, repr=False)
    ar: NDArray[np.float64] = field(init=False, repr=False)

    # Sub-step size (§4.1).
    T: float = field(init=False)

    # Per-mode diagonal mass and damping ratio.
    m_diag: NDArray[np.float64] = field(init=False, repr=False)
    xi: NDArray[np.float64] = field(init=False, repr=False)

    # State: two previous modal amplitudes per mode.
    q_prev: NDArray[np.float64] = field(init=False, repr=False)
    q_prev2: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._compute_coefficients()
        self.reset()

    def _compute_coefficients(self) -> None:
        """Derive IIR filter coefficients from per-mode SDOF parameters."""
        m = self.modal.num_modes
        omega = self.modal.frequencies                    # ω_j [rad/s]
        alpha0 = self.modal.fem.alpha0
        alpha1 = self.modal.fem.alpha1

        # Sub-step size: T = π / (2 ω_max)  (§4.1).
        omega_max = omega[-1] if omega[-1] > 0 else 1.0
        self.T = np.pi / (2.0 * omega_max)

        # Per-mode diagonal mass (mass-normalized → m_j = 1).
        self.m_diag = np.diag(self.modal.M_q).copy()

        # Rayleigh damping ratio per mode: ξ_j = (α₀/ω_j + α₁ ω_j) / 2.
        self.xi = np.zeros(m, dtype=np.float64)
        for j in range(m):
            if omega[j] > 0:
                self.xi[j] = (alpha0 / omega[j] + alpha1 * omega[j]) / 2.0

        # Clamp ξ to [0, 1) — critically/over-damped modes need special handling,
        # but for typical Rayleigh parameters they stay underdamped.
        self.xi = np.clip(self.xi, 0.0, 0.9999)

        T = self.T
        self.a1 = np.zeros(m, dtype=np.float64)
        self.a2 = np.zeros(m, dtype=np.float64)
        self.ar = np.zeros(m, dtype=np.float64)

        for j in range(m):
            wj = omega[j]
            xj = self.xi[j]

            if wj < 1e-12:
                # Near-zero frequency mode: no oscillation, no restoring force.
                self.a1[j] = 1.0
                self.a2[j] = 0.0
                self.ar[j] = T
                continue

            wd = wj * np.sqrt(1.0 - xj**2)      # damped frequency
            exp_term = np.exp(-xj * wj * T)

            self.a1[j] = 2.0 * exp_term * np.cos(wd * T)
            self.a2[j] = exp_term**2
            self.ar[j] = exp_term * np.sin(wd * T) / wd

    def reset(self) -> None:
        """Reset modal state to zero (no vibration)."""
        m = self.modal.num_modes
        self.q_prev = np.zeros(m, dtype=np.float64)
        self.q_prev2 = np.zeros(m, dtype=np.float64)

    def step(self, r: NDArray[np.float64] | None = None) -> NDArray[np.float64]:
        """Advance one IIR sub-step (Eq. 10).

        Args:
            r: Modal forcing vector (m,). Applied at this sub-step only.
               Pass None or zeros for free vibration sub-steps.

        Returns:
            q: New modal amplitudes (m,).
        """
        q_new = self.a1 * self.q_prev - self.a2 * self.q_prev2

        if r is not None:
            # r_j / (m_j T) scaled by a_r,j.
            q_new += self.ar * r / (self.m_diag * self.T)

        self.q_prev2 = self.q_prev
        self.q_prev = q_new
        return q_new.copy()

    def step_n(
        self, n_steps: int, r: NDArray[np.float64] | None = None
    ) -> NDArray[np.float64]:
        """Step n_steps sub-steps. Forcing r is applied at sub-step k=1 only (§4.3).

        Args:
            n_steps: Number of IIR sub-steps (typically h / T).
            r: Modal forcing vector, applied at the first sub-step.

        Returns:
            q_history: (n_steps, m) modal amplitudes at each sub-step.
        """
        m = self.modal.num_modes
        q_history = np.zeros((n_steps, m), dtype=np.float64)

        for k in range(n_steps):
            if k == 0:
                q_history[k] = self.step(r)
            else:
                q_history[k] = self.step(None)

        return q_history
