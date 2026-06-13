"""Monolithic implicit-Euler coupled step for two reduced bodies.

One step = one Newton minimization of the incremental potential (Affine Body
Dynamics, `docs/ABD.pdf` Eq. 9), with a PENALTY contact in place of the IPC log
barrier:

    E(z) = Σ_b 1/(2h²) (z_b − z̃_b)^T M_b (z_b − z̃_b)     # inertia (gravity in z̃)
         + Σ_b V_b(z_b)                                    # internal elastic
         + Σ_i ½ k_c [gap_i(z)]_−²                         # penalty contact
    z̃_b = z_b^n + h ż_b^n + h² M_b⁻¹ f_grav,b

with gap_i(z) = y_corner_i(z_cube) − y_slab_i(z_slab) (normal = +y), plus an
implicit Rayleigh damping force D ż.

# DEVIATION (ABD Eq. 10–11): penalty contact, not the log barrier. The
# demonstrator targets the *settling / passivity* question, not guaranteed
# non-penetration; penalty is the minimal model that exhibits the descent.

Passivity: each step descends a bounded-below E; with D ⪰ 0 and ∇gap doing
equal-and-opposite work on the two bodies, total mechanical energy is monotone
non-increasing and the run converges to argmin E = the static sag. This is the
discrete form of `docs/two_way_modal_coupling_investigation.md` §3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class ContactPair:
    """A cube contact corner paired with a slab tracked point (normal = +y)."""
    cube_pid: int
    slab_pid: int


@dataclass
class TwoBodyState:
    zc: NDArray[np.float64]   # cube generalized coords
    zs: NDArray[np.float64]   # slab generalized coords
    vc: NDArray[np.float64]   # cube generalized velocity
    vs: NDArray[np.float64]   # slab generalized velocity


@dataclass
class TwoBodySystem:
    cube: object               # ABDAffineBody or FEMModalBody
    slab: object               # FEMModalBody
    pairs: list[ContactPair]
    k_c: float = 1.0e6         # contact penalty stiffness [N/m]
    newton_iters: int = 20
    newton_tol: float = 1.0e-10

    nA: int = field(init=False)
    nB: int = field(init=False)
    _M: NDArray[np.float64] = field(init=False, repr=False)
    _D: NDArray[np.float64] = field(init=False, repr=False)
    _Minv: NDArray[np.float64] = field(init=False, repr=False)
    _fgrav: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.nA = self.cube.ndof
        self.nB = self.slab.ndof
        n = self.nA + self.nB
        M = np.zeros((n, n))
        D = np.zeros((n, n))
        M[:self.nA, :self.nA] = self.cube.M
        M[self.nA:, self.nA:] = self.slab.M
        D[:self.nA, :self.nA] = self.cube.D
        D[self.nA:, self.nA:] = self.slab.D
        self._M = M
        self._D = D
        self._Minv = np.linalg.inv(M)
        self._fgrav = np.concatenate([self.cube.f_grav, self.slab.f_grav])

    # -- initial state -------------------------------------------------
    def initial_state(self) -> TwoBodyState:
        return TwoBodyState(
            zc=self.cube.rest_state(),
            zs=self.slab.rest_state(),
            vc=np.zeros(self.nA),
            vs=np.zeros(self.nB),
        )

    # -- contact gap geometry -----------------------------------------
    def _gaps(self, zc, zs):
        """Return (gaps (P,), grads (P, n)) for all contact pairs."""
        n = self.nA + self.nB
        gaps = np.zeros(len(self.pairs))
        grads = np.zeros((len(self.pairs), n))
        for p, pair in enumerate(self.pairs):
            yc = self.cube.point_world(zc, pair.cube_pid)[1]
            ys = self.slab.point_world(zs, pair.slab_pid)[1]
            gaps[p] = yc - ys
            grads[p, :self.nA] = self.cube.point_jac(pair.cube_pid)[1, :]
            grads[p, self.nA:] = -self.slab.point_jac(pair.slab_pid)[1, :]
        return gaps, grads

    # -- internal grad / hess assembled into the stacked system -------
    def _internal(self, zc, zs):
        n = self.nA + self.nB
        g = np.zeros(n)
        H = np.zeros((n, n))
        g[:self.nA] = self.cube.internal_grad(zc)
        g[self.nA:] = self.slab.internal_grad(zs)
        H[:self.nA, :self.nA] = self.cube.internal_hess(zc)
        H[self.nA:, self.nA:] = self.slab.internal_hess(zs)
        return g, H

    # -- one implicit-Euler step --------------------------------------
    def step(self, state: TwoBodyState, h: float) -> TwoBodyState:
        n = self.nA + self.nB
        z_n = np.concatenate([state.zc, state.zs])
        v_n = np.concatenate([state.vc, state.vs])
        # inertial predictor (gravity folded in)
        z_tilde = z_n + h * v_n + (h * h) * (self._Minv @ self._fgrav)

        z = z_n.copy()
        for _ in range(self.newton_iters):
            zc, zs = z[:self.nA], z[self.nA:]
            g_int, H_int = self._internal(zc, zs)
            gaps, grads = self._gaps(zc, zs)

            g = (self._M @ (z - z_tilde)) / (h * h) + g_int
            g += (self._D @ (z - z_n)) / h
            H = self._M / (h * h) + H_int + self._D / h
            for p in range(len(self.pairs)):
                if gaps[p] < 0.0:
                    g += self.k_c * gaps[p] * grads[p]
                    H += self.k_c * np.outer(grads[p], grads[p])

            delta = np.linalg.solve(H, -g)
            z += delta
            if np.linalg.norm(delta) < self.newton_tol:
                break

        v = (z - z_n) / h
        return TwoBodyState(zc=z[:self.nA], zs=z[self.nA:],
                            vc=v[:self.nA], vs=v[self.nA:])

    # -- diagnostics ---------------------------------------------------
    def energy(self, state: TwoBodyState) -> dict[str, float]:
        z = np.concatenate([state.zc, state.zs])
        v = np.concatenate([state.vc, state.vs])
        KE = 0.5 * float(v @ (self._M @ v))
        PE_el = (self.cube.internal_energy(state.zc)
                 + self.slab.internal_energy(state.zs))
        PE_grav = -float(self._fgrav @ z)
        gaps, _ = self._gaps(state.zc, state.zs)
        PE_c = 0.5 * self.k_c * float(np.sum(np.minimum(gaps, 0.0) ** 2))
        total = KE + PE_el + PE_grav + PE_c
        return {"KE": KE, "PE_elastic": PE_el, "PE_grav": PE_grav,
                "PE_contact": PE_c, "total": total,
                "max_penetration": float(max(0.0, -gaps.min()))}

    # -- reference static equilibrium (ż = 0) -------------------------
    def static_solve(self, state0: TwoBodyState | None = None,
                     iters: int = 200, tol: float = 1.0e-12) -> TwoBodyState:
        """Newton on ∇V_elastic + ∇V_contact − f_grav = 0 (the static minimizer)."""
        st = state0 or self.initial_state()
        z = np.concatenate([st.zc, st.zs])
        for _ in range(iters):
            zc, zs = z[:self.nA], z[self.nA:]
            g_int, H_int = self._internal(zc, zs)
            gaps, grads = self._gaps(zc, zs)
            g = g_int - self._fgrav
            H = H_int.copy()
            for p in range(len(self.pairs)):
                if gaps[p] < 0.0:
                    g += self.k_c * gaps[p] * grads[p]
                    H += self.k_c * np.outer(grads[p], grads[p])
            # mild regularization for the unconstrained rigid directions
            H += 1.0e-9 * np.eye(H.shape[0])
            delta = np.linalg.solve(H, -g)
            z += delta
            if np.linalg.norm(delta) < tol:
                break
        return TwoBodyState(zc=z[:self.nA], zs=z[self.nA:],
                            vc=np.zeros(self.nA), vs=np.zeros(self.nB))
