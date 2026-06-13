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
    # optional stacked initial generalized velocity (e.g. a fast-dropping
    # impactor); None ⇒ start at rest. Respected by every solver through
    # initial_state(), so GT / AVBD / XPBD / split all see the same kick.
    v0: NDArray[np.float64] | None = None

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
        v = np.zeros(self.n) if self.v0 is None else self.v0.copy()
        return MultiBodyState(z=z, v=v)

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


def build_stack_impact(kind: str, n_stack: int = 3, *, size: float = 0.1,
                       slab_E: float = 5.0e7, cube_E: float = 5.0e6,
                       kappa_v: float = 2.0e3, damping: float = 0.5,
                       k_c: float = 1.0e6, material_rho: float = 600.0,
                       impactor_rho: float = 5000.0, impactor_size: float | None = None,
                       impactor_v0: float = 5.0, impactor_x: float = 0.22,
                       impactor_drop: float | None = None, stack_x: float = 0.0):
    """A resting tower of `n_stack` cubes on the slab + a HEAVY box dropped fast
    onto the slab BESIDE the stack, so the box rings the slab and the ring kicks
    the tower (the stack reacts — it jolts / rocks). The box does NOT touch the
    stack: it lands on BARE slab in a gap at `impactor_x`, away from the tower at
    `stack_x`.

    Contacts: cube0↔slab + cube_i↔cube_{i-1} (the stack) and box↔slab (beside) —
    no box↔stack. The box starts at height `impactor_drop` (default ≈ stack-top
    height, so it falls alongside the tower) with a downward initial velocity
    `impactor_v0` (m/s); it is `impactor_rho/material_rho`× as dense as the tower.
    Returns (system, info) with the impactor index and the stack indices.

    bodies[0] = slab; bodies[1..n_stack] = stack (bottom→top); bodies[-1] = box.
    """
    from dcr.fem.material import Material
    from dcr.twobody.reduced_body import (build_abd_cube, build_fem_cube,
                                          build_fem_slab)

    half = 0.5 * size
    slab_top = 0.025
    imp_size = impactor_size if impactor_size is not None else size
    imp_half = 0.5 * imp_size
    if abs(impactor_x - stack_x) < 0.5 * (size + imp_size):
        raise ValueError(
            f"impactor_x={impactor_x:.3f} overlaps the stack at x={stack_x:.3f} "
            f"(box should land BESIDE the tower on bare slab — increase impactor_x).")
    if impactor_drop is None:                 # start beside the tower, ≈ its top
        impactor_drop = slab_top + 2 * n_stack * half

    # slab tracks two footprints: the stack base (pids 0–3) and the box (pids 4–7)
    corner_xz = []
    for cx in (stack_x, impactor_x):
        for sx, sz in ((half, half), (half, -half), (-half, half), (-half, -half)):
            corner_xz.append((cx + sx, sz))
    slab = build_fem_slab(material=Material(E=slab_E, nu=0.3, rho=material_rho),
                          num_modes=16, alpha0=2.0 * damping, alpha1=1.0e-4 * damping,
                          nx=20, ny=12, cube_corners_xz=np.array(corner_xz))

    def make_cube(rho_, drop_y_, sz_, cx_):
        mat = Material(E=cube_E, nu=0.3, rho=rho_)
        if kind == "abd":
            return build_abd_cube(size=sz_, material=mat, kappa_v=kappa_v,
                                  drop_y=drop_y_, alpha0=damping, cx=cx_)
        return build_fem_cube(size=sz_, material=mat, drop_y=drop_y_,
                              alpha0=damping, alpha1=5.0e-4 * damping, cx=cx_)

    # tower cubes resting exactly on each other (centroid i = slab_top+(2i+1)·half)
    cubes = [make_cube(material_rho, slab_top + (2 * i + 1) * half, size, stack_x)
             for i in range(n_stack)]
    # heavy box dropped beside the tower, onto bare slab
    impactor = make_cube(impactor_rho, impactor_drop, imp_size, impactor_x)

    bodies = [slab] + cubes + [impactor]
    imp_idx = 1 + n_stack
    contacts: list[Contact] = []
    for j in range(4):                        # cube0 ↔ slab (stack footprint, 0–3)
        contacts.append(Contact(upper=1, pid_upper=j, lower=0, pid_lower=j))
    for i in range(1, n_stack):               # cube_i ↔ cube_{i-1}
        for j in range(4):
            contacts.append(Contact(upper=1 + i, pid_upper=j,
                                    lower=i, pid_lower=4 + j))
    for j in range(4):                        # box ↔ slab (box footprint, 4–7)
        contacts.append(Contact(upper=imp_idx, pid_upper=j,
                                lower=0, pid_lower=4 + j))

    sysm = MultiBodySystem(bodies=bodies, contacts=contacts, k_c=k_c)
    # fast downward initial velocity on the box's translation carrier (y = dof 1)
    v0 = np.zeros(sysm.n)
    v0[sysm.offsets[imp_idx] + 1] = -abs(impactor_v0)
    sysm.v0 = v0
    info = {"impactor_body": imp_idx, "stack_bodies": list(range(1, n_stack + 1))}
    return sysm, info


def build_side_by_side(kind: str, n_rest: int = 3, *, size: float = 0.1,
                       spacing: float = 0.28, impactor_x: float | None = None,
                       impactor_drop: float = 0.45, impactor_rho: float = 3000.0,
                       slab_E: float = 5.0e7, cube_E: float = 5.0e6,
                       kappa_v: float = 2.0e3, damping: float = 0.5,
                       k_c: float = 1.0e5, rest_gap: float = 0.002):
    """Slab + `n_rest` cubes RESTING side by side + one heavy impactor dropped on
    the slab. The impactor rings the slab; the ring kicks the bystander cubes
    (slab → cube momentum transfer through the monolithic implicit contact, no
    velocity-impulse band). Returns (system, info) where info marks which body is
    the impactor and the resting-cube indices.

    bodies[0] = slab; bodies[1..n_rest] = resting cubes (left→right);
    bodies[n_rest+1] = impactor.

    The impactor lands on BARE SLAB in a gap between resting cubes. There are no
    cube↔cube contacts (only cube→slab), so an impactor placed at a resting cube's
    x would fall straight THROUGH it; `impactor_x=None` (default) drops it into the
    gap between the two centre cubes (½·spacing) to avoid that.
    """
    from dcr.fem.material import Material
    from dcr.twobody.reduced_body import (build_abd_cube, build_fem_cube,
                                          build_fem_slab)

    half = 0.5 * size
    slab_top = 0.025
    rest_centroid = slab_top + half
    # resting-cube x positions, centered
    xs = (np.arange(n_rest) - (n_rest - 1) / 2.0) * spacing
    # Default: land the impactor in the gap between the two centre cubes so it
    # hits bare slab, never overlapping a resting cube's x (no cube↔cube contact).
    if impactor_x is None:
        impactor_x = 0.5 * spacing if n_rest > 1 else 0.5 * (size + spacing)
    # Guard: an impactor sharing a resting cube's x-span would interpenetrate it.
    if any(abs(impactor_x - x) < size for x in xs):
        nearest = min(xs, key=lambda x: abs(impactor_x - x))
        raise ValueError(
            f"impactor_x={impactor_x:.3f} overlaps a resting cube at x={nearest:.3f} "
            f"(|Δx|<{size}); with no cube↔cube contacts it would penetrate. "
            f"Place it in a gap (e.g. ½·spacing={0.5*spacing:.3f}).")

    def make_cube(cube_E_, rho_, drop_y_, cx_):
        mat = Material(E=cube_E_, nu=0.3, rho=rho_)
        if kind == "abd":
            return build_abd_cube(size=size, material=mat, kappa_v=kappa_v,
                                  drop_y=drop_y_, alpha0=damping, cx=cx_)
        return build_fem_cube(size=size, material=mat, drop_y=drop_y_,
                              alpha0=damping, alpha1=5.0e-4 * damping, cx=cx_)

    cubes = [make_cube(cube_E, 600.0, rest_centroid + rest_gap, float(x)) for x in xs]
    impactor = make_cube(cube_E, impactor_rho, impactor_drop, float(impactor_x))
    all_cubes = cubes + [impactor]

    # slab must track 4 contact points under every cube's bottom corners
    corner_xz = []
    for cx in list(xs) + [impactor_x]:
        for sx, sz in ((half, half), (half, -half), (-half, half), (-half, -half)):
            corner_xz.append((cx + sx, sz))
    slab = build_fem_slab(material=Material(E=slab_E, nu=0.3, rho=600.0),
                          num_modes=16, alpha0=2.0 * damping, alpha1=1.0e-4 * damping,
                          nx=20, ny=12, cube_corners_xz=np.array(corner_xz))

    bodies = [slab] + all_cubes
    contacts: list[Contact] = []
    for c in range(len(all_cubes)):
        for j in range(4):
            contacts.append(Contact(upper=1 + c, pid_upper=j,
                                    lower=0, pid_lower=4 * c + j))
    sysm = MultiBodySystem(bodies=bodies, contacts=contacts, k_c=k_c)
    info = {"impactor_body": 1 + n_rest, "rest_bodies": list(range(1, n_rest + 1))}
    return sysm, info
