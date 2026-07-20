"""Minimal deterministic 3-D renderer for the teaser figure and video.

Painter's-algorithm polygon rendering into a matplotlib axes. Written rather
than pulled in because every panel of the teaser must share a bit-identical
camera, projection and scale: a comparison figure whose panels differ in
framing is not a comparison. Nothing here is a contribution -- it is flat
Lambert shading of convex boxes plus one deflected slab grid.

Conventions match the sim: y up, quaternions (x, y, z, w) as the solver
stores them, SI metres.
"""
from __future__ import annotations

import numpy as np
from matplotlib.collections import LineCollection, PolyCollection

# unit-cube corners, then the 6 faces as quads wound counter-clockwise when
# seen from outside (so the face normal points out of the box)
_CORNERS = np.array([[sx, sy, sz] for sx in (-1.0, 1.0)
                     for sy in (-1.0, 1.0) for sz in (-1.0, 1.0)])
_QUADS = np.array([
    [0, 1, 3, 2],   # -x
    [4, 6, 7, 5],   # +x
    [0, 4, 5, 1],   # -y
    [2, 3, 7, 6],   # +y
    [0, 2, 6, 4],   # -z
    [1, 5, 7, 3],   # +z
])
_EDGES = np.array([[0, 1], [1, 3], [3, 2], [2, 0], [4, 5], [5, 7], [7, 6],
                   [6, 4], [0, 4], [1, 5], [2, 6], [3, 7]])

# Draw layers, resolved BEFORE the depth sort (see `Renderer.draw`). A pure
# painter's algorithm cannot separate the support slab from a body resting on
# it: the body's base is coplanar with the slab top to within microns, so slab
# cells in front of the body beat the body's lower faces on centroid depth and
# paint over them -- a notch out of the box's base. Bodies rest ON the support
# and the camera is above its plane, so the slab can never legitimately occlude
# one; ordering it first is exact here, not a fudge. `assert_layering_valid`
# checks that premise against the data rather than trusting it.
LAYER_SUPPORT = 0
LAYER_BODY = 1


def assert_layering_valid(body_bottoms, slab_top, tol: float = 5e-3) -> None:
    """Guard the LAYER_SUPPORT < LAYER_BODY premise.

    A body may only be drawn unconditionally in front of the support if it
    sits on top of it. The comparison must be against the *deflected* surface,
    not the rest plane: the board sags several mm under load, so a body resting
    on it is legitimately below its own rest height. For each body we compare
    its lowest point with the slab sample nearest in (x, z).

    body_bottoms: (n, 3) world points, y = the body's lowest vertex.
    slab_top:     (m, 3) deflected support samples.
    """
    B = np.asarray(body_bottoms, float).reshape(-1, 3)
    S = np.asarray(slab_top, float).reshape(-1, 3)
    if not len(B) or not len(S):
        return
    d2 = ((B[:, None, 0] - S[None, :, 0]) ** 2
          + (B[:, None, 2] - S[None, :, 2]) ** 2)
    local = S[np.argmin(d2, axis=1), 1]
    slack = B[:, 1] - local
    k = int(np.argmin(slack))
    if slack[k] < -tol:
        raise ValueError(
            f"a body sits {1e3 * -slack[k]:.1f} mm below the deflected support "
            f"surface beneath it (> {tol * 1e3:.1f} mm): the "
            f"support-behind-bodies draw order is no longer exact")


def quat_xyzw_to_R(q) -> np.ndarray:
    x, y, z, w = (float(v) for v in q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def box_corners(half, pos, quat_xyzw) -> np.ndarray:
    R = quat_xyzw_to_R(quat_xyzw)
    return (_CORNERS * np.asarray(half, float)) @ R.T + np.asarray(pos, float)


class Camera:
    """Fixed perspective camera. Locked once and reused for every panel."""

    def __init__(self, eye, target, up=(0.0, 1.0, 0.0), fov_deg=32.0,
                 aspect=1.0):
        self.eye = np.asarray(eye, float)
        self.target = np.asarray(target, float)
        f = self.target - self.eye
        f = f / np.linalg.norm(f)
        s = np.cross(f, np.asarray(up, float))
        s = s / np.linalg.norm(s)
        u = np.cross(s, f)
        self.R = np.stack([s, u, -f])          # world -> camera rotation
        self.t = np.tan(np.radians(fov_deg) / 2.0)
        self.aspect = float(aspect)

    def project(self, P):
        """World points (..., 3) -> (screen (..., 2), depth (...,))."""
        P = np.asarray(P, float)
        C = (P - self.eye) @ self.R.T
        z = np.maximum(-C[..., 2], 1e-6)       # metres in front of the eye
        x = C[..., 0] / (z * self.t * self.aspect)
        y = C[..., 1] / (z * self.t)
        return np.stack([x, y], axis=-1), z


class Renderer:
    """Accumulate shaded quads, then draw them back-to-front into an axes."""

    def __init__(self, camera: Camera, light=(-0.45, 0.82, 0.36),
                 ambient=0.42, diffuse=0.58):
        self.cam = camera
        L = np.asarray(light, float)
        self.light = L / np.linalg.norm(L)
        self.ambient = float(ambient)
        self.diffuse = float(diffuse)
        self._quads: list[np.ndarray] = []     # each (4, 3) world verts
        self._colors: list[np.ndarray] = []
        self._alpha: list[float] = []
        self._edge: list = []
        self._layer: list[int] = []
        self._lines: list[np.ndarray] = []     # each (2, 3) world verts
        self._line_style: list[dict] = []

    # ---- geometry -----------------------------------------------------
    def add_quads(self, quads, color, alpha=1.0, shade=True, edge=None,
                  tint=0.0, layer=LAYER_BODY):
        """quads: (n, 4, 3) world-space. `tint` lightens toward white.

        `layer` orders primitives ahead of the depth sort -- see `draw`.
        """
        quads = np.asarray(quads, float).reshape(-1, 4, 3)
        base = np.asarray(color, float)
        if base.max() > 1.0:
            base = base / 255.0
        base = base + (1.0 - base) * float(tint)
        for qd in quads:
            self._quads.append(qd)
            self._colors.append(self._shade(qd, base) if shade else base)
            self._alpha.append(float(alpha))
            self._edge.append(edge)
            self._layer.append(int(layer))

    def add_box(self, half, pos, quat_xyzw, color, alpha=1.0, edge=None,
                tint=0.0, layer=LAYER_BODY):
        V = box_corners(half, pos, quat_xyzw)
        self.add_quads(V[_QUADS], color, alpha=alpha, edge=edge, tint=tint,
                       layer=layer)

    def add_box_wire(self, half, pos, quat_xyzw, color="0.55", lw=0.5,
                     ls=(0, (2, 1.6)), alpha=0.9):
        """Ghost outline of a pose -- used for the initial-position silhouette."""
        V = box_corners(half, pos, quat_xyzw)
        for a, b in _EDGES:
            self._lines.append(np.stack([V[a], V[b]]))
            self._line_style.append(dict(color=color, lw=lw, ls=ls,
                                         alpha=alpha))

    def add_slab(self, top, nx, nz, thickness, color, edge=None, alpha=1.0,
                 layer=LAYER_SUPPORT):
        """Deflected support board: top grid + the four side walls.

        `top` is (nx*nz, 3) in row-major (ix, iz) order -- the same layout the
        support's `point_positions_rest` uses. The bottom face is never
        visible from the teaser camera, so only the walls are extruded.
        """
        top = np.asarray(top, float).reshape(nx, nz, 3)
        bot = top.copy()
        bot[..., 1] -= float(thickness)
        quads = [np.stack([top[i, j], top[i + 1, j],
                           top[i + 1, j + 1], top[i, j + 1]])
                 for i in range(nx - 1) for j in range(nz - 1)]
        self.add_quads(np.array(quads), color, alpha=alpha, edge=edge,
                       layer=layer)
        walls = []
        for i in range(nx - 1):                                  # z = 0, z = max
            walls.append(np.stack([top[i, 0], bot[i, 0],
                                   bot[i + 1, 0], top[i + 1, 0]]))
            walls.append(np.stack([top[i + 1, -1], bot[i + 1, -1],
                                   bot[i, -1], top[i, -1]]))
        for j in range(nz - 1):                                  # x = 0, x = max
            walls.append(np.stack([top[0, j + 1], bot[0, j + 1],
                                   bot[0, j], top[0, j]]))
            walls.append(np.stack([top[-1, j], bot[-1, j],
                                   bot[-1, j + 1], top[-1, j + 1]]))
        # walls a touch darker so the board reads as a solid with thickness
        self.add_quads(np.array(walls), np.asarray(color, float) * 0.82
                       if np.max(color) <= 1.0 else np.asarray(color) * 0.82,
                       alpha=alpha, edge=edge, layer=layer)

    def add_slab_seamless(self, *a, **kw):
        """`add_slab` with each quad edged in its own face colour, which hides
        the antialiasing seams between adjacent coplanar grid cells."""
        kw.setdefault("edge", "face")
        return self.add_slab(*a, **kw)

    def add_ground_grid(self, y, x_range, z_range, step=0.1, color="0.86",
                        lw=0.4, alpha=0.9):
        x0, x1 = x_range
        z0, z1 = z_range
        for x in np.arange(x0, x1 + 1e-9, step):
            self._lines.append(np.array([[x, y, z0], [x, y, z1]]))
            self._line_style.append(dict(color=color, lw=lw, ls="-",
                                         alpha=alpha))
        for z in np.arange(z0, z1 + 1e-9, step):
            self._lines.append(np.array([[x0, y, z], [x1, y, z]]))
            self._line_style.append(dict(color=color, lw=lw, ls="-",
                                         alpha=alpha))

    # ---- shading + draw -----------------------------------------------
    def _shade(self, quad, base):
        n = np.cross(quad[1] - quad[0], quad[2] - quad[0])
        ln = np.linalg.norm(n)
        if ln < 1e-14:
            return base
        n = n / ln
        # two-sided: the teaser camera can see a slab wall from either side
        lam = abs(float(n @ self.light))
        return np.clip(base * (self.ambient + self.diffuse * lam), 0.0, 1.0)

    def draw(self, ax, xlim=(-1.0, 1.0), ylim=(-1.0, 1.0), lw=0.25):
        """Depth-sorted draw. Farthest first, so nearer faces overwrite."""
        if self._quads:
            Q = np.array(self._quads)                        # (n, 4, 3)
            xy, z = self.cam.project(Q)
            # layer first, then far -> near within a layer: lexsort's last key
            # is primary, so depth is the secondary sort
            order = np.lexsort((-z.mean(axis=1), np.array(self._layer)))
            cols = np.array(self._colors)[order]
            alph = np.array(self._alpha)[order]
            edges = [self._edge[i] for i in order]
            fc = [(c[0], c[1], c[2], a) for c, a in zip(cols, alph)]
            # "face" edges hide the antialiasing seams between coplanar cells;
            # they must be resolved per-face here, not left to the collection
            ec, lws = [], []
            for e, f in zip(edges, fc):
                if e is None:
                    ec.append((0, 0, 0, 0))
                    lws.append(0.0)
                elif e == "face":
                    ec.append(f)
                    lws.append(0.55)
                else:
                    ec.append(e)
                    lws.append(lw)
            pc = PolyCollection([xy[i] for i in order], facecolors=fc,
                                edgecolors=ec, linewidths=lws,
                                antialiased=True, zorder=2)
            ax.add_collection(pc)
        if self._lines:
            L = np.array(self._lines)
            xy, _ = self.cam.project(L)
            for seg, st in zip(xy, self._line_style):
                ax.add_collection(LineCollection([seg], zorder=3, **st))
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_aspect("equal")
        ax.set_axis_off()
        return ax


def slab_top(support_rest, Uy, q, exaggeration=1.0) -> np.ndarray:
    """Deflected support samples: rest + U_y q (the surface eq:row sees).

    `exaggeration` is 1.0 everywhere in the teaser -- true scale.
    """
    top = np.asarray(support_rest, float).copy()
    top[:, 1] += (np.asarray(Uy, float) @ np.asarray(q, float)) * exaggeration
    return top
