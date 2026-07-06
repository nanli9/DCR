"""Multi-body full-FEM ground truth: EVERY body is FEM, not just the support.

The all-FEM generalization of `CoupledFEMRigidSim` (the X3 GT arm): each body
is its own linear-FEM `FEMModel` integrated by implicit Newmark (paper Eq. 5,
trapezoidal beta=0.25 / gamma=0.5 — `NewmarkIntegrator`), and bodies couple
through penalty contact between one body's surface vertices and another's
deformed top surface. A support (slab/table) is simply a body with Dirichlet
BCs (fixed corner columns); free bodies have none — their `K_eff = K + c0·M +
c1·D` stays SPD through the mass term, and rigid translation lives exactly in
the FEM space (translations are zero-energy modes of linear FEM), so a free
body falls, lands, and deforms with NO separate rigid state.

Contact model — deliberately the SAME class as the single-slab GT so the
all-FEM arm inherits its documented fidelity limits (validation plan §6.1):

# DEVIATION (contact, vs a full collision solve): contact is a one-sided
# penalty height-field — the UPPER body's candidate vertices vs the LOWER
# body's deformed top surface, vertical (y) normal, frictionless, forces
# applied explicitly. This is exactly `CoupledFEMRigidSim`'s scheme
# generalized from one predefined (x,z) point to every candidate vertex and
# from FEM-vs-rigid to FEM-vs-FEM. It resolves stiff impacts as a ~2 kHz
# penalty oscillator (the known X3 bystander-launch caveat): score deflection
# FIELDS, not launch KE.
#
# DEVIATION (per-vertex penalty stiffness, vs X3's single constant): X3's
# k=5e7 acts at ONE point on a 0.3 kg rigid body — a 2.05 kHz oscillator.
# Here the penalty acts per FEM NODE, and the lightest bottom-face node of a
# 0.06 kg fork would ring far above the explicit-coupling stability limit at
# X3's constant. So the per-vertex stiffness pins the per-NODE penalty
# oscillator on the lightest participating node:
#     k_v = min(k_penalty / P,  m_node_min * (2π f_c)²),   f_c = 1.5 kHz,
# (P = bottom-face vertex count) — the same stiff-contact class as X3 at the
# node level, X3's constant (face-split) as the cap for heavy bodies. Keep
# h_fine * 2π f_c ≲ 0.5 (default h_fine 5e-5 ⇒ 0.47).
#
# DEVIATION (contact dashpot, vs X3's pure spring): a pure penalty spring is
# conservative (restitution ≈ 1) — a multi-body stack chatters forever and
# never reaches static equilibrium. X3 never noticed because its rigid side
# integrates the penalty SEMI-IMPLICITLY (numerical dissipation for free);
# both FEM sides here are trapezoidal (energy-conserving), so the dissipation
# must be explicit: a standard contact dashpot at fraction `contact_zeta`
# (default 0.2) of the per-vertex penalty oscillator's critical damping,
# active only in contact, total force clamped ≥ 0 (no adhesion). Set
# contact_zeta=0 to recover the pure-spring X3 class.

# DEVIATION (kinematics, vs a corotational/nonlinear FEM): linear FEM is not
# rotation-invariant, so this GT is valid in the SMALL-ROTATION regime —
# settle/drop/ring scenes. Large rigid rotations (the ledge topple phase)
# accrue linearization ghost forces; score the pre-topple ring there.

The X-suite comparison contract (X3 pattern) still holds per body: the native
arm's modal basis must be the eigenbasis of the SAME `FEMModel` this GT
integrates, so the only differences are mode truncation and the contact model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.fem.newmark import NewmarkIntegrator
from dcr.geom.tet_mesh import make_beam_tet_mesh

_SURF_TOL = 1e-6


@dataclass
class FEMBody:
    """One deformable body: a body-local `FEMModel` (mesh centered at the
    origin) + implicit Newmark state + a constant world `origin`. World vertex
    position = origin + rest + u; all rigid motion accumulates in u."""

    name: str
    fem: FEMModel
    origin: NDArray[np.float64]              # (3,) world position of mesh center
    h_fine: float = 5e-5

    newmark: NewmarkIntegrator = field(init=False, repr=False)
    gravity_load: NDArray[np.float64] = field(init=False, repr=False)
    # full-DOF -> free-DOF index map (-1 where fixed): vectorized scatter
    _free_map: NDArray[np.int64] = field(init=False, repr=False)
    # candidate contact vertices (local y ≈ y_min): the face that lands on things
    bottom_verts: NDArray[np.int64] = field(init=False, repr=False)
    # receiving surface (local y ≈ y_max): the face things land on
    top_verts: NDArray[np.int64] = field(init=False, repr=False)
    top_tris: NDArray[np.int64] = field(init=False, repr=False)
    surf_verts: NDArray[np.int64] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.origin = np.asarray(self.origin, dtype=np.float64).reshape(3)
        self.newmark = NewmarkIntegrator(fem=self.fem, h=self.h_fine)
        self.gravity_load = self.fem.gravity_load(g=-9.81)
        self.total_mass = float(self.fem.M_full.diagonal()[0::3].sum())
        n_full = self.fem.n_full_dofs
        self._free_map = np.full(n_full, -1, dtype=np.int64)
        self._free_map[self.fem.free_dofs] = np.arange(self.fem.free_dofs.size)

        verts = self.fem.mesh.vertices
        y_min, y_max = verts[:, 1].min(), verts[:, 1].max()
        self.bottom_verts = np.where(
            np.abs(verts[:, 1] - y_min) < _SURF_TOL)[0].astype(np.int64)
        m_node = self.fem.M_full.diagonal()[0::3]
        self.bottom_mass_min = float(m_node[self.bottom_verts].min())
        self.top_verts = np.where(
            np.abs(verts[:, 1] - y_max) < _SURF_TOL)[0].astype(np.int64)
        surface = self.fem.mesh.extract_surface()
        self.surf_verts = np.unique(surface.faces.ravel()).astype(np.int64)
        top_set = set(self.top_verts.tolist())
        tris = [f for f in surface.faces
                if f[0] in top_set and f[1] in top_set and f[2] in top_set]
        self.top_tris = (np.array(tris, dtype=np.int64)
                         if tris else np.empty((0, 3), dtype=np.int64))

    # -- state ---------------------------------------------------------
    def u_full(self) -> NDArray[np.float64]:
        return self.newmark.full_displacement()

    def v_full(self) -> NDArray[np.float64]:
        v = np.zeros(self.fem.n_full_dofs, dtype=np.float64)
        v[self.fem.free_dofs] = self.newmark.v
        return v

    def world_vertices(self, u_full: NDArray[np.float64] | None = None
                       ) -> NDArray[np.float64]:
        u = self.u_full() if u_full is None else u_full
        return self.origin + self.fem.mesh.vertices + u.reshape(-1, 3)

    def com(self) -> NDArray[np.float64]:
        """Mass-weighted world center of mass (lumped nodal masses)."""
        m = self.fem.M_full.diagonal()[0::3]
        w = self.world_vertices()
        return (m[:, None] * w).sum(axis=0) / m.sum()

    def com_y(self) -> float:
        return float(self.com()[1])

    def set_velocity(self, v: tuple[float, float, float]) -> None:
        """Uniform rigid velocity on every free DOF (launch/drop kick)."""
        v3 = np.tile(np.asarray(v, dtype=np.float64),
                     self.fem.n_full_dofs // 3)
        self.newmark.v[:] = v3[self.fem.free_dofs]

    def translate(self, d: tuple[float, float, float]) -> None:
        """Rigid re-placement (zero elastic energy: translations are exact
        null modes of linear FEM) — the X3 'park the impactor away, then move
        it into place' trick, without touching v or a."""
        d3 = np.tile(np.asarray(d, dtype=np.float64),
                     self.fem.n_full_dofs // 3)
        self.newmark.u[:] += d3[self.fem.free_dofs]

    def elastic_energy(self) -> float:
        return 0.5 * float(self.newmark.u @ (self.fem.K @ self.newmark.u))

    def kinetic_energy(self) -> float:
        return 0.5 * float(self.newmark.v @ (self.fem.M @ self.newmark.v))

    def top_uy(self) -> NDArray[np.float64]:
        """Deflection field u_y at the top-surface vertices — the convergent
        GT signal (validation plan §6.1: score u_y, not launch KE)."""
        return self.u_full().reshape(-1, 3)[self.top_verts, 1]


def make_box_fem_body(
    name: str,
    half_extents,
    center,
    material: Material,
    resolution: int | tuple[int, int, int] = 3,
    h_fine: float = 5e-5,
    alpha0: float = 0.0,
    alpha1: float = 1e-5,
    fixed_nodes=None,
) -> FEMBody:
    """Axis-aligned (hx,hy,hz) box FEM body centered at `center` (world).
    `resolution`: int ⇒ cells on the longest axis, aspect-scaled with a floor
    of 2; tuple ⇒ explicit (nx,ny,nz). Mirrors the cargo-side box builder so
    both arms can share the operator.

    NOTE alpha0 (mass-proportional Rayleigh damping) drags RIGID motion too —
    physical for a Dirichlet-fixed support (the X3 slab's alpha0=2), an
    unphysical air-drag on a FREE body (it slows free fall). Default 0 here;
    give supports their alpha0 explicitly and let free bodies settle through
    the contact dashpot + alpha1."""
    half = np.asarray(half_extents, dtype=np.float64).reshape(3)
    if isinstance(resolution, (int, np.integer)):
        longest = float(half.max())
        nxyz = tuple(max(2, int(round(int(resolution) * float(e) / longest)))
                     for e in half)
    else:
        nxyz = tuple(int(n) for n in resolution)
    mesh = make_beam_tet_mesh(
        length=2.0 * half[0], width=2.0 * half[1], height=2.0 * half[2],
        nx=nxyz[0], ny=nxyz[1], nz=nxyz[2])
    fem = FEMModel(mesh=mesh, material=material,
                   fixed_nodes=[] if fixed_nodes is None else fixed_nodes,
                   alpha0=alpha0, alpha1=alpha1)
    return FEMBody(name=name, fem=fem,
                   origin=np.asarray(center, dtype=np.float64), h_fine=h_fine)


def corner_column_nodes(mesh) -> NDArray[np.int64]:
    """Vertex ids of the four (x,z)-extreme corner columns (all y) — the X3
    slab's Dirichlet set (`fix_corners`, corner-fixed support)."""
    v = mesh.vertices
    tol = 1e-9
    on_x = (np.abs(v[:, 0] - v[:, 0].min()) < tol) | \
           (np.abs(v[:, 0] - v[:, 0].max()) < tol)
    on_z = (np.abs(v[:, 2] - v[:, 2].min()) < tol) | \
           (np.abs(v[:, 2] - v[:, 2].max()) < tol)
    return np.where(on_x & on_z)[0].astype(np.int64)


# ---------------------------------------------------------------------------
# vectorized deformed-top-surface height query
# ---------------------------------------------------------------------------
def _top_height_batch(
    lower: FEMBody,
    u_full: NDArray[np.float64],
    pts_xz: NDArray[np.float64],
    margin: float = 0.0,
):
    """Deformed top-surface height of `lower` at P query points (world XZ).

    Vectorized barycentric interpolation over the T top tris (rest XZ; lateral
    surface displacement ignored, as in `CoupledFEMRigidSim`). Returns
    (height (P,), tri_vertex_ids (P,3), bary (P,3), inside (P,) bool); points
    outside every triangle have inside=False.
    """
    T = lower.top_tris.shape[0]
    P = pts_xz.shape[0]
    if T == 0 or P == 0:
        return (np.zeros(P), np.zeros((P, 3), dtype=np.int64),
                np.zeros((P, 3)), np.zeros(P, dtype=bool))
    verts = lower.fem.mesh.vertices
    uy = u_full.reshape(-1, 3)[:, 1]
    tri = lower.top_tris                                    # (T,3)
    ax, az = (lower.origin[0] + verts[tri[:, 0], 0],
              lower.origin[2] + verts[tri[:, 0], 2])
    bx, bz = (lower.origin[0] + verts[tri[:, 1], 0],
              lower.origin[2] + verts[tri[:, 1], 2])
    cx, cz = (lower.origin[0] + verts[tri[:, 2], 0],
              lower.origin[2] + verts[tri[:, 2], 2])
    y0 = lower.origin[1] + verts[tri[:, 0], 1] + uy[tri[:, 0]]
    y1 = lower.origin[1] + verts[tri[:, 1], 1] + uy[tri[:, 1]]
    y2 = lower.origin[1] + verts[tri[:, 2], 1] + uy[tri[:, 2]]

    x = pts_xz[:, 0][:, None]                               # (P,1)
    z = pts_xz[:, 1][:, None]
    denom = ((bz - cz) * (ax - cx) + (cx - bx) * (az - cz))[None, :]  # (1,T)
    ok = np.abs(denom) > 1e-15
    denom = np.where(ok, denom, 1.0)
    w0 = ((bz - cz)[None, :] * (x - cx[None, :])
          + (cx - bx)[None, :] * (z - cz[None, :])) / denom
    w1 = ((cz - az)[None, :] * (x - cx[None, :])
          + (ax - cx)[None, :] * (z - cz[None, :])) / denom
    w2 = 1.0 - w0 - w1
    inside = ok & (w0 >= -margin) & (w1 >= -margin) & (w2 >= -margin)  # (P,T)

    has = inside.any(axis=1)
    pick = np.argmax(inside, axis=1)                        # first containing tri
    rows = np.arange(P)
    W = np.stack([w0[rows, pick], w1[rows, pick], w2[rows, pick]], axis=1)
    H = (W[:, 0] * y0[pick] + W[:, 1] * y1[pick] + W[:, 2] * y2[pick])
    return H, tri[pick], W, has


@dataclass
class MultiFEMSim:
    """N deformable FEM bodies + penalty contact (see module docstring).

    Per fine step: (1) auto-detect candidate pairs by world-AABB overlap in
    XZ, upper = higher COM; (2) penalty forces upper-bottom-verts vs
    lower-top-surface and every body vs the optional floor halfspace;
    (3) one Newmark step per body with gravity + contact. Explicit force
    coupling at h_fine (the X3 GT's own semi-implicit penalty scheme).
    """

    h_fine: float = 5e-5
    k_penalty: float = 5e7
    penalty_fc: float = 1500.0       # penalty-oscillator pin [Hz], see DEVIATION
    contact_zeta: float = 0.2        # contact dashpot / critical, see DEVIATION
    floor_y: float | None = None
    floor_friction_c: float = 0.0    # optional viscous tangential damping
                                     # (0 = frictionless, the X3 GT class)

    bodies: list[FEMBody] = field(default_factory=list)
    # per-step contact-force ledger {(upper, lower): Σ f_n} and
    # {(body, "floor"): Σ f_n}, refreshed each step — read after step()
    ledger: dict = field(default_factory=dict)
    t: float = 0.0

    def add_body(self, body: FEMBody) -> FEMBody:
        if body.h_fine != self.h_fine:
            raise ValueError(
                f"body {body.name!r} h_fine={body.h_fine} != sim {self.h_fine}")
        self.bodies.append(body)
        return body

    def body(self, name: str) -> FEMBody:
        return next(b for b in self.bodies if b.name == name)

    def _k_v(self, upper: FEMBody) -> float:
        """Per-vertex penalty stiffness (see module DEVIATION): pin the
        per-node penalty oscillator at `penalty_fc` on the lightest
        participating node; X3's face-split constant is the heavy-body cap.
        The oscillator is additionally capped at hω ≤ 0.35 — the explicit
        force coupling between the two implicit Newmark bodies is the ONLY
        conditionally-stable piece, and past hω ≈ 0.9 the rectified dashpot
        pumps energy (measured: a 1 kg book bounce-amplifies at hω = 0.94)."""
        w_c = min(2.0 * np.pi * self.penalty_fc, 0.35 / self.h_fine)
        P = max(len(upper.bottom_verts), 1)
        return float(min(self.k_penalty / P,
                         upper.bottom_mass_min * w_c * w_c))

    # -- pair candidates ------------------------------------------------
    def _pairs(self, world_verts: dict) -> list[tuple[FEMBody, FEMBody]]:
        """(upper, lower) candidates: XZ AABB overlap + upper COM above the
        lower's top. Fixed-support bodies are always eligible lowers."""
        out = []
        n = len(self.bodies)
        aabb = {}
        for b in self.bodies:
            w = world_verts[b.name][b.surf_verts]
            aabb[b.name] = (w[:, 0].min(), w[:, 0].max(),
                            w[:, 2].min(), w[:, 2].max())
        for i in range(n):
            for j in range(i + 1, n):
                bi, bj = self.bodies[i], self.bodies[j]
                x0i, x1i, z0i, z1i = aabb[bi.name]
                x0j, x1j, z0j, z1j = aabb[bj.name]
                if x0i > x1j or x0j > x1i or z0i > z1j or z0j > z1i:
                    continue
                yi = world_verts[bi.name][:, 1].mean()
                yj = world_verts[bj.name][:, 1].mean()
                upper, low = (bi, bj) if yi >= yj else (bj, bi)
                out.append((upper, low))
        return out

    def _c_v(self, k_v: float, upper: FEMBody) -> float:
        """Per-vertex contact dashpot: contact_zeta × critical for the
        lightest participating node's penalty oscillator."""
        return 2.0 * self.contact_zeta * float(
            np.sqrt(k_v * upper.bottom_mass_min))

    # -- one fine step ----------------------------------------------------
    def step(self) -> None:
        f_contact = {b.name: np.zeros(b.fem.free_dofs.size) for b in self.bodies}
        u_fulls = {b.name: b.u_full() for b in self.bodies}
        v_fulls = {b.name: b.v_full() for b in self.bodies}
        world_verts = {b.name: b.world_vertices(u_fulls[b.name])
                       for b in self.bodies}
        self.ledger = {}

        # body-vs-body penalty (upper bottom verts vs lower deformed top)
        for upper, lower in self._pairs(world_verts):
            pts = world_verts[upper.name][upper.bottom_verts]       # (P,3)
            H, tri_ids, W, has = _top_height_batch(
                lower, u_fulls[lower.name], pts[:, [0, 2]])
            pen = H - pts[:, 1]
            act = has & (pen > 0.0)
            if not act.any():
                continue
            # per-vertex share of the pair stiffness (constant divisor P so
            # the joint stiffness does not chatter with the active count)
            k_v = self._k_v(upper)
            # spring + dashpot on the penetration rate, no adhesion
            v_up = v_fulls[upper.name].reshape(-1, 3)[
                upper.bottom_verts[act], 1]
            vy_low = v_fulls[lower.name].reshape(-1, 3)[:, 1]
            v_surf = (W[act] * vy_low[tri_ids[act]]).sum(axis=1)
            pen_rate = v_surf - v_up
            f_n = np.maximum(
                0.0, k_v * pen[act] + self._c_v(k_v, upper) * pen_rate)
            # upward on the upper body's vertices (its own FEM nodes)
            up_dofs = 3 * upper.bottom_verts[act] + 1
            up_free = upper._free_map[up_dofs]
            valid = up_free >= 0
            np.add.at(f_contact[upper.name], up_free[valid], f_n[valid])
            # equal-and-opposite scattered to the lower's top triangle
            low_dofs = 3 * tri_ids[act] + 1                          # (A,3)
            low_free = lower._free_map[low_dofs]
            fw = -W[act] * f_n[:, None]                              # (A,3)
            ok = low_free >= 0
            np.add.at(f_contact[lower.name], low_free[ok], fw[ok])
            self.ledger[(upper.name, lower.name)] = float(f_n.sum())

        # floor halfspace (vertex-vs-halfspace penalty)
        if self.floor_y is not None:
            for b in self.bodies:
                w = world_verts[b.name][b.surf_verts]
                pen = self.floor_y - w[:, 1]
                act = pen > 0.0
                if not act.any():
                    continue
                k_v = self._k_v(b)
                vy = v_fulls[b.name].reshape(-1, 3)[b.surf_verts[act], 1]
                f_n = np.maximum(
                    0.0, k_v * pen[act] - self._c_v(k_v, b) * vy)
                dofs = 3 * b.surf_verts[act] + 1
                fr = b._free_map[dofs]
                valid = fr >= 0
                np.add.at(f_contact[b.name], fr[valid], f_n[valid])
                if self.floor_friction_c > 0.0:
                    # viscous tangential damping at floor contacts (optional;
                    # OFF by default to stay in the frictionless GT class)
                    for c in (0, 2):
                        dofs_t = 3 * b.surf_verts[act] + c
                        fr_t = b._free_map[dofs_t]
                        vt = np.zeros(act.sum())
                        ok = fr_t >= 0
                        vt[ok] = b.newmark.v[fr_t[ok]]
                        np.add.at(f_contact[b.name], fr_t[ok],
                                  -self.floor_friction_c * vt[ok])
                self.ledger[(b.name, "floor")] = float(f_n.sum())

        for b in self.bodies:
            b.newmark.step(b.gravity_load + f_contact[b.name])
        self.t += self.h_fine

    def run(self, t_total: float, record_every: int = 200,
            probes: dict | None = None) -> dict:
        """Advance `t_total` seconds; record per-frame body top-surface u_y
        fields, COM heights, energies, and the contact ledger. `probes` maps
        a label to a callable(sim) evaluated per recorded frame.

        The recorded `ledger` is the per-key mean force over each recording
        INTERVAL (Σ f·h / T_interval), not an instant sample — under penalty
        contact the instantaneous force chatters, but its time average is the
        momentum-balance force (= supported weight when settled)."""
        n_steps = int(round(t_total / self.h_fine))
        rec: dict = {"times": [], "com_y": {b.name: [] for b in self.bodies},
                     "top_uy": {b.name: [] for b in self.bodies},
                     "elastic_E": {b.name: [] for b in self.bodies},
                     "kinetic_E": {b.name: [] for b in self.bodies},
                     "ledger": [], "probes": {k: [] for k in (probes or {})}}
        acc: dict = {}
        n_acc = 0
        for i in range(n_steps):
            self.step()
            for k, v in self.ledger.items():
                acc[k] = acc.get(k, 0.0) + v
            n_acc += 1
            if i % record_every == 0:
                rec["times"].append(self.t)
                rec["ledger"].append({k: v / n_acc for k, v in acc.items()})
                acc, n_acc = {}, 0
                for b in self.bodies:
                    rec["com_y"][b.name].append(b.com_y())
                    rec["top_uy"][b.name].append(b.top_uy().copy())
                    rec["elastic_E"][b.name].append(b.elastic_energy())
                    rec["kinetic_E"][b.name].append(b.kinetic_energy())
                for k, fn in (probes or {}).items():
                    rec["probes"][k].append(fn(self))
        rec["times"] = np.asarray(rec["times"])
        return rec
