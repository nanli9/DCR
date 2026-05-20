"""Modal kinetic + potential energy observable (Stage E0).

Implements E_modal = 0.5 qdot^T qdot + 0.5 q^T Omega^2 q (foundation §2).
See passive_energy_injection_implementation_prompt.md E0.2.

With mass-normalized modes (M_q = I), no mass factor is needed.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def modal_energy(q: NDArray[np.float64], qdot: NDArray[np.float64],
                 omega: NDArray[np.float64]) -> float:
    """Total modal energy: kinetic + potential (foundation §2, core eq. §15).

    E_modal = 0.5 qdot^T qdot + 0.5 q^T Omega^2 q

    where Omega = diag(omega_1, ..., omega_m) are the natural frequencies.
    Assumes mass-normalized modes so M_q = I.

    Args:
        q: Modal displacement vector (n_modes,).
        qdot: Modal velocity vector (n_modes,).
        omega: Natural frequencies (n_modes,) in rad/s.

    Returns:
        Total modal energy (scalar >= 0).
    """
    kinetic = 0.5 * np.dot(qdot, qdot)
    potential = 0.5 * np.dot(q, omega**2 * q)
    return float(kinetic + potential)
