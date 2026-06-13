"""N-body reduced coupling: same monolithic implicit step, arbitrary contacts.

Generalizes `coupled_step.TwoBodySystem` to a list of reduced bodies and a list
of vertical (normal = +y) penalty contacts, so we can stack cubes on the slab
(slab ← cube1 ← cube2 ...). Each body still implements the duck-typed
`ReducedBody` interface from `reduced_body.py`; the global step is one Newton
minimization of the stacked incremental potential (ABD `docs/ABD.pdf` Eq. 9,
penalty contact — same DEVIATION as `coupled_step.py`).

Per-body energy logging (`energy_breakdown`) is the verification hook the
benchmark uses to track cube vs slab energy separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray


@dataclass
class Contact:
    """A vertical penalty contact: `upper` body's point sits above `lower`'s.

    gap = y(upper.point) − y(lower.point); penalty force when gap < 0.
    """
    upper: int    # index into bodies (the body whose point is on top)
    pid_upper: int
    lower: int
    pid_lower: int


@dataclass
class MultiBodyState:
    z: NDArray[np.float64]      # stacked generalized coords
    v: NDArray[np.float64]      # stacked generalized velocity


@dataclass
class MultiBodySystem:
    bodies: list                # ReducedBody-like
    contacts: list[Contact]
    k_c: float = 1.0e5
    newton_iters: int = 30
    newton_tol: float = 1.0e-10

    offsets: list[int] = field(init=False)        # start index of each body in z
    n: int = field(init=False)
    _M: NDArray[np.float64] = field(init=False, repr=False)
    _D: NDArray[np.float64] = field(init=False, repr=False)
    _Minv: NDArray[np.float64] = field(init=False, repr=False)
    _fgrav: NDArray[np.float64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        off, s = [], 0
        for b in self.bodies:
            off.append(s)
            s += b.ndof
        self.offsets = off
        self.n = s
        M = np.zeros((s, s))
        D = np.zeros((s, s))
        fg = np.zeros(s)
        for b, o in zip(self.bodies, self.offsets):
            M[o:o + b.ndof, o:o + b.ndof] = b.M
            D[o:o + b.ndof, o:o + b.ndof] = b.D
            fg[o:o + b.ndof] = b.f_grav
        self._M, self._D, self._fgrav = M, D, fg
        self._Minv = np.linalg.inv(M)

    # -- slicing -------------------------------------------------------
    def _slice(self, i: int) -> slice:
        o = self.offsets[i]
        return slice(o, o + self.bodies[i].ndof)

    def body_z(self, state: MultiBodyState, i: int) -> NDArray[np.float64]:
        return state.z[self._slice(i)]

    def initial_state(self) -> MultiBodyState:
        z = np.concatenate([b.rest_state() for b in self.bodies])
        return MultiBodyState(z=z, v=np.zeros(self.n))

    # -- contact geometry ---------------------------------------------
    def _gaps(self, z):
        gaps = np.zeros(len(self.contacts))
        grads = np.zeros((len(self.contacts), self.n))
        for c, ct in enumerate(self.contacts):
            bu, bl = self.bodies[ct.upper], self.bodies[ct.lower]
            zu, zl = z[self._slice(ct.upper)], z[self._slice(ct.lower)]
            yu = bu.point_world(zu, ct.pid_upper)[1]
            yl = bl.point_world(zl, ct.pid_lower)[1]
            gaps[c] = yu - yl
            grads[c, self._slice(ct.upper)] += bu.point_jac(ct.pid_upper)[1, :]
            grads[c, self._slice(ct.lower)] -= bl.point_jac(ct.pid_lower)[1, :]
        return gaps, grads

    def _internal(self, z):
        g = np.zeros(self.n)
        H = np.zeros((self.n, self.n))
        for i, b in enumerate(self.bodies):
            sl = self._slice(i)
            zi = z[sl]
            g[sl] = b.internal_grad(zi)
            H[sl, sl] = b.internal_hess(zi)
        return g, H

    # -- one implicit-Euler step --------------------------------------
    def step(self, state: MultiBodyState, h: float) -> MultiBodyState:
        z_n, v_n = state.z, state.v
        z_tilde = z_n + h * v_n + (h * h) * (self._Minv @ self._fgrav)
        z = z_n.copy()
        for _ in range(self.newton_iters):
            g_int, H_int = self._internal(z)
            gaps, grads = self._gaps(z)
            g = (self._M @ (z - z_tilde)) / (h * h) + g_int + (self._D @ (z - z_n)) / h
            H = self._M / (h * h) + H_int + self._D / h
            for c in range(len(self.contacts)):
                if gaps[c] < 0.0:
                    g += self.k_c * gaps[c] * grads[c]
                    H += self.k_c * np.outer(grads[c], grads[c])
            delta = np.linalg.solve(H, -g)
            z += delta
            if np.linalg.norm(delta) < self.newton_tol:
                break
        v = (z - z_n) / h
        return MultiBodyState(z=z, v=v)

    # -- energy --------------------------------------------------------
    def energy_breakdown(self, state: MultiBodyState) -> dict:
        """Per-body KE + elastic PE, plus global gravity / contact / total."""
        z, v = state.z, state.v
        out: dict[str, float] = {}
        ke_total = 0.0
        pe_el_total = 0.0
        for i, b in enumerate(self.bodies):
            sl = self._slice(i)
            ke = 0.5 * float(v[sl] @ (b.M @ v[sl]))
            pe = float(b.internal_energy(z[sl]))
            out[f"KE_body{i}"] = ke
            out[f"PEel_body{i}"] = pe
            ke_total += ke
            pe_el_total += pe
        gaps, _ = self._gaps(z)
        out["KE"] = ke_total
        out["PE_elastic"] = pe_el_total
        out["PE_grav"] = -float(self._fgrav @ z)
        out["PE_contact"] = 0.5 * self.k_c * float(np.sum(np.minimum(gaps, 0.0) ** 2))
        out["total"] = out["KE"] + out["PE_elastic"] + out["PE_grav"] + out["PE_contact"]
        out["max_penetration"] = float(max(0.0, -gaps.min())) if len(gaps) else 0.0
        return out

    # -- verification: static-equilibrium residual --------------------
    def static_residual(self, state: MultiBodyState) -> float:
        """‖∇E_static(z)‖ at the given state: ∇V_elastic + ∇V_contact − f_grav.

        At a true static rest (the static sag) this is ~0. This is a basin-free
        verification that the *dynamic* rest state is a genuine static
        equilibrium — robust where `static_solve`'s Newton can jump to a spurious
        (reflected-affine) minimum for tall ABD stacks.
        """
        z = state.z
        g_int, _ = self._internal(z)
        gaps, grads = self._gaps(z)
        g = g_int - self._fgrav
        for c in range(len(self.contacts)):
            if gaps[c] < 0.0:
                g += self.k_c * gaps[c] * grads[c]
        return float(np.linalg.norm(g))

    # -- reference static equilibrium ---------------------------------
    def static_solve(self, iters: int = 400, tol: float = 1.0e-12) -> MultiBodyState:
        z = np.concatenate([b.rest_state() for b in self.bodies])
        for _ in range(iters):
            g_int, H_int = self._internal(z)
            gaps, grads = self._gaps(z)
            g = g_int - self._fgrav
            H = H_int.copy()
            for c in range(len(self.contacts)):
                if gaps[c] < 0.0:
                    g += self.k_c * gaps[c] * grads[c]
                    H += self.k_c * np.outer(grads[c], grads[c])
            H += 1.0e-9 * np.eye(self.n)
            delta = np.linalg.solve(H, -g)
            z += delta
            if np.linalg.norm(delta) < tol:
                break
        return MultiBodyState(z=z, v=np.zeros(self.n))


# ----------------------------------------------------------------------
# Scene builders
# ----------------------------------------------------------------------
def build_stack(kind: str, n_cubes: int, *, size: float = 0.1,
                slab_E: float = 5.0e7, cube_E: float = 5.0e6,
                kappa_v: float = 2.0e3, damping: float = 0.5,
                k_c: float = 1.0e5, gap: float = 0.01,
                material_rho: float = 600.0):
    """Slab + a vertical stack of `n_cubes` cubes (kind in {'abd','fem'}).

    Cube i centroid rest height = slab_top + (2i+1)·half; each is dropped from a
    small `gap` above its resting height so the stack settles under gravity.
    Returns a configured MultiBodySystem (bodies[0] = slab, bodies[1:] = cubes
    bottom→top).
    """
    from dcr.fem.material import Material
    from dcr.twobody.reduced_body import (build_abd_cube, build_fem_cube,
                                          build_fem_slab)

    half = 0.5 * size
    slab_top = 0.025  # slab half-height (height=0.05)
    slab = build_fem_slab(material=Material(E=slab_E, nu=0.3, rho=material_rho),
                          num_modes=16, alpha0=2.0 * damping, alpha1=1.0e-4 * damping)

    cubes = []
    for i in range(n_cubes):
        rest_centroid = slab_top + (2 * i + 1) * half
        drop_y = rest_centroid + gap
        if kind == "abd":
            cube = build_abd_cube(size=size,
                                  material=Material(E=cube_E, nu=0.3, rho=material_rho),
                                  kappa_v=kappa_v, drop_y=drop_y, alpha0=damping)
        else:
            cube = build_fem_cube(size=size,
                                  material=Material(E=cube_E, nu=0.3, rho=material_rho),
                                  drop_y=drop_y, alpha0=damping, alpha1=5.0e-4 * damping)
        cubes.append(cube)

    bodies = [slab] + cubes
    contacts: list[Contact] = []
    # cube0 (body index 1) bottom corners 0-3 ↔ slab tracked points 0-3
    for j in range(4):
        contacts.append(Contact(upper=1, pid_upper=j, lower=0, pid_lower=j))
    # cube i bottom corners 0-3 ↔ cube (i-1) top corners 4-7
    for i in range(1, n_cubes):
        upper_idx = 1 + i
        lower_idx = i
        for j in range(4):
            contacts.append(Contact(upper=upper_idx, pid_upper=j,
                                    lower=lower_idx, pid_lower=4 + j))
    return MultiBodySystem(bodies=bodies, contacts=contacts, k_c=k_c)
