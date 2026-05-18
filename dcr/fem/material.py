"""Material properties and constitutive matrix for isotropic linear elasticity."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class Material:
    """Isotropic linear elastic material.

    Attributes:
        E: Young's modulus [Pa].  Paper uses ~1.1 GPa for wood-like.
        nu: Poisson ratio.  Paper uses 0.3.
        rho: Mass density [kg/m^3].  ~600 for wood.
    """

    E: float = 1.1e9
    nu: float = 0.3
    rho: float = 600.0

    @property
    def lame_lambda(self) -> float:
        """First Lamé constant: λ = E ν / ((1+ν)(1-2ν))."""
        return self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))

    @property
    def lame_mu(self) -> float:
        """Second Lamé constant (shear modulus): μ = E / (2(1+ν))."""
        return self.E / (2.0 * (1.0 + self.nu))

    def constitutive_matrix(self) -> NDArray[np.float64]:
        """6x6 isotropic elasticity matrix D in Voigt notation.

        Stress-strain: σ = D ε, with Voigt ordering
        [σ_xx, σ_yy, σ_zz, τ_xy, τ_yz, τ_xz].

        Uses engineering strain (γ = 2ε for shear), so D has μ (not 2μ)
        on the shear diagonal.
        """
        lam = self.lame_lambda
        mu = self.lame_mu
        D = np.array([
            [lam + 2 * mu, lam,           lam,           0,  0,  0],
            [lam,           lam + 2 * mu, lam,           0,  0,  0],
            [lam,           lam,           lam + 2 * mu, 0,  0,  0],
            [0,             0,             0,             mu, 0,  0],
            [0,             0,             0,             0,  mu, 0],
            [0,             0,             0,             0,  0,  mu],
        ], dtype=np.float64)
        return D
