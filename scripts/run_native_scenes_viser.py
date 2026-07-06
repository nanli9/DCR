"""Unified viser: scene × solver × material × device, two NATIVE solvers, NO coupler.

One viewer over the full matrix (native dual-solver build):

  * scene    — cargo (§N2 modal-network stack: FIVE deformable cubes on the
               support — a resting cube, a dropped impactor, and an offset
               3-high stack where the ring climbs the tower cube-to-cube through
               the box-box modal network; live ON/OFF toggle) | the four
               production scenes truck / ledge / shelf / dinner (a deformable
               impactor + rigid bystanders on the reduced-modal support).
  * solver   — avbd (SolverAVBD, Augmented-Lagrangian) | xpbd (SolverXPBD,
               compliant Gauss–Seidel). BOTH are genuinely independent NATIVE
               solvers: each solves rigid + box-box/floor + the reduced-modal
               support + cargo in its own formulation, with NO coupler and NO
               shared solver segment. Flip live to compare the two realizations
               of the SAME dynamic two-way constraint (two_band_coupling.html).
               Both carry full cargo (rigid/fem_rigid/fem/abd) in every scene.
  * material — rigid | fem_rigid | abd | fem (the impactor's body model; "rigid"
               is the plain 6-DOF k=0 baseline that carries no deformation).
  * device   — cpu | cuda:0. AVBD is GPU-resident on CUDA; SolverXPBD is CPU
               only for now (its device/CUDA-graph pass is deferred).

Knobs mirror `scripts/run_reduced_scene_viser.py` (the decorated-asset viewer):
Sim (speed), Scene (support material, support thickness, impactor mass / drop /
launch velocity),
Reduced-modal solver (iterations, substeps, modal impedance, modal damping),
Visualization (cube-flex + slab-deflection exaggeration, support render
thickness, full vs static modal view, impactor-as-collision-proxy), and a
Diagnostics readout block. Scene-dependent knobs reset to that scene's preset on
a scene change (rebuild); same-scene "reset / rebuild" reads the live knobs.

Rendering: the support is a SOLID slab of its true thickness (the deflected top
grid extruded down a constant thickness), the deformable impactor's skinned
surface (modal flex / affine shear), and the rigid bystanders as boxes. The two
"deformation exaggeration" sliders (cube flex, slab deflection) default to 1.0
(TRUE SCALE); real flex is ~1e-5 m, so raise them (~300) to see the modal motion.

Notes:
  * abd + xpbd auto-routes to AVBD: abd's stiff nonlinear V⊥ is not Gauss–Seidel-
    stable in the substep sweep budget (the XPBDDynamicSystem oracle note); the
    HUD shows the effective solver.
  * This renders simple boxes, not the decorated `model/<kind>/` assets — those
    stay in scripts/run_reduced_scene_viser.py (rigid cargo, no solver/material
    switching).

Run:
    .venv/bin/python scripts/run_native_scenes_viser.py --scene ledge --device cuda:0
then open http://localhost:8192
"""
from __future__ import annotations

import argparse
import inspect
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scenes.reduced_cargo_network import build_cargo_network_scene
from scenes.reduced_truck import build_reduced_truck
from scenes.reduced_ledge import build_reduced_ledge
from scenes.reduced_shelf import build_reduced_shelf
from scenes.reduced_dinner_table import build_reduced_dinner_table

N_GRID_X, N_GRID_Z = 21, 11
KINDS = ("rigid", "fem_rigid", "abd", "fem")
SOLVERS = ("avbd", "xpbd")
SCENES = ("cargo", "truck", "ledge", "shelf", "dinner")
_PROD = {"truck": build_reduced_truck, "ledge": build_reduced_ledge,
         "shelf": build_reduced_shelf, "dinner": build_reduced_dinner_table}
# "rigid" (k=0) is the plain 6-DOF rigid cube — the no-deformation baseline; a
# neutral gray distinguishes it from the deformable materials.
_CUBE_COLOR = {"rigid": (150, 155, 165), "fem_rigid": (77, 140, 217),
               "abd": (217, 120, 77), "fem": (120, 200, 120)}
_EXAG_MAX = 2000.0


@dataclass(frozen=True)
class SupportMaterial:
    """Physically representative (E, ρ) for the deformable support slab, plus a
    render appearance so the slab LOOKS like the chosen material. Stiffer
    materials deflect less — honest: at exaggeration=1 steel/glass barely move,
    softer ones flex visibly. `flat` is a faceted(matte)-vs-smooth(metal) cue."""
    youngs: float       # Young's modulus E [Pa]
    density: float      # [kg/m³]
    color: tuple        # render RGB in [0, 1]
    flat: bool = True


# Ordered stiff → soft. E / ρ are textbook values; colors evoke the material.
# Mirrors scripts/run_reduced_scene_viser.py so the two viewers agree.
_MATERIAL: dict[str, SupportMaterial] = {
    "steel":    SupportMaterial(2.00e11, 7850.0, (0.60, 0.63, 0.67), flat=False),
    "titanium": SupportMaterial(1.16e11, 4500.0, (0.52, 0.53, 0.57), flat=False),
    "glass":    SupportMaterial(7.00e10, 2500.0, (0.66, 0.85, 0.88), flat=False),
    "aluminum": SupportMaterial(6.90e10, 2700.0, (0.84, 0.86, 0.89), flat=False),
    "concrete": SupportMaterial(3.00e10, 2400.0, (0.64, 0.62, 0.58), flat=True),
    "wood":     SupportMaterial(1.00e10,  600.0, (0.55, 0.36, 0.20), flat=True),
    "plastic":  SupportMaterial(1.00e9,  1200.0, (0.20, 0.38, 0.72), flat=True),
    "soft":     SupportMaterial(1.00e8,  1000.0, (0.86, 0.46, 0.55), flat=True),
    "rubber":   SupportMaterial(5.00e7,  1100.0, (0.13, 0.13, 0.15), flat=True),
}


def _mat_color_u8(material: str) -> tuple:
    c = _MATERIAL.get(material, _MATERIAL["wood"]).color
    return tuple(int(np.clip(round(v * 255), 0, 255)) for v in c)

# Per-scene presets (defaults + the slider ranges scene-dependent knobs reset to
# on a scene change). `mass`/`drop`/`v0` map onto whichever kwarg the builder
# exposes (impactor_* / pot_* / drop_height) — filtered by signature at build.
SCENE_SPEC = {
    "cargo":  dict(label="impactor", thickness=0.020, mass=None, mass_rng=(0.1, 5.0),
                   drop=0.22, drop_rng=(0.0, 0.8), v0=0.0,  iters=12, subs=4,
                   material="wood"),
    "truck":  dict(label="crate",   thickness=0.060, mass=40.0, mass_rng=(1.0, 120.0),
                   drop=0.70, drop_rng=(0.0, 2.0), v0=0.0,  iters=8, subs=4,
                   material="wood"),
    "ledge":  dict(label="boulder", thickness=0.080, mass=50.0, mass_rng=(1.0, 150.0),
                   drop=0.80, drop_rng=(0.0, 2.0), v0=0.0,  iters=8, subs=4,
                   material="wood"),
    "shelf":  dict(label="box",     thickness=0.030, mass=6.0,  mass_rng=(0.5, 40.0),
                   drop=0.50, drop_rng=(0.0, 1.5), v0=0.0,  iters=8, subs=4,
                   material="plastic"),
    "dinner": dict(label="pot",     thickness=0.020, mass=8.0,  mass_rng=(1.0, 40.0),
                   drop=0.50, drop_rng=(0.0, 1.5), v0=0.0,  iters=6, subs=2,
                   material="wood"),
}

# unit-box corner table (x,y,z bits) + 12-triangle faces for that ordering.
_BOX_CORNERS = np.array(
    [[sx, sy, sz] for sx in (-1.0, 1.0) for sy in (-1.0, 1.0)
     for sz in (-1.0, 1.0)], dtype=np.float64)
_BOX_FACES = np.array([
    (0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
    (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3),
], dtype=np.int32)


def _effective_solver(solver: str, kind: str) -> str:
    """abd routes to AVBD (its stiff V⊥ is not GS-stable; oracle note)."""
    return "avbd" if (solver == "xpbd" and kind == "abd") else solver


def _xpbd_iter_floor(solver: str, spec: dict) -> tuple[int, int]:
    """XPBD GS has no ρ-escalation, so the many-body scenes want more sweeps
    than AVBD's AL — start it at ≥16 iters / ≥4 substeps (the user can lower
    it). AVBD uses the scene preset."""
    if solver == "xpbd":
        return max(16, spec["iters"]), max(4, spec["subs"])
    return spec["iters"], spec["subs"]


# --- support slab geometry (top grid + extruded bottom + side walls) ---------
def _grid_faces(nx: int, nz: int) -> np.ndarray:
    faces = []
    for ix in range(nx - 1):
        for iz in range(nz - 1):
            a = ix * nz + iz
            b = (ix + 1) * nz + iz
            c = (ix + 1) * nz + (iz + 1)
            d = ix * nz + (iz + 1)
            faces.append((a, b, c))
            faces.append((a, c, d))
    return np.array(faces, dtype=np.int32)


def _slab_faces(nx: int, nz: int) -> np.ndarray:
    """Closed slab: deflected top grid (verts 0..N-1) + flat-offset bottom grid
    (verts N..2N-1) + the four perimeter side walls. Bottom + sides are wound so
    their normals point outward."""
    n = nx * nz
    top = _grid_faces(nx, nz)
    bot = top[:, ::-1] + n                      # reverse winding, offset to bottom
    sides = []

    def quad(a, b):                              # top edge a->b, drop to bottom
        sides.append((a, b, b + n))
        sides.append((a, b + n, a + n))
    for ix in range(nx - 1):                     # iz = 0 and iz = nz-1 edges
        quad((ix + 1) * nz + 0, ix * nz + 0)
        quad(ix * nz + (nz - 1), (ix + 1) * nz + (nz - 1))
    for iz in range(nz - 1):                     # ix = 0 and ix = nx-1 edges
        quad(0 * nz + iz, 0 * nz + (iz + 1))
        quad((nx - 1) * nz + (iz + 1), (nx - 1) * nz + iz)
    return np.vstack([top, bot, np.array(sides, dtype=np.int32)]).astype(np.int32)


def _slab_verts(rs, q, exag: float, thickness: float) -> np.ndarray:
    """2N verts: the deflected top grid then the bottom grid a constant
    `thickness` below it (the slab bends as a solid unit)."""
    top = rs.point_positions_rest.copy().astype(np.float64)
    top[:, 1] += (rs.U_points[:, 1, :] @ q) * exag
    bot = top.copy()
    bot[:, 1] -= float(thickness)
    return np.vstack([top, bot]).astype(np.float32)


def _quat_wxyz_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def _box_verts(half, p, q_xyzw) -> np.ndarray:
    q_wxyz = (q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2])
    R = _quat_wxyz_to_R(q_wxyz)
    return ((_BOX_CORNERS * np.asarray(half)) @ R.T + p).astype(np.float32)


class UnifiedViser:
    def __init__(self, args):
        import viser
        self.args = args
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self.scene = args.scene
        self.kind = args.kind
        self.solver = args.solver
        self.device = args.device
        self.paused = False
        self.speed = 0.5
        self.cube_exag = float(args.cube_exag)
        self.support_exag = float(args.support_exag)
        # Modal contact network (§N2): the cargo scene is a 4-cube stack demo
        # (resting cube | impactor | offset stack) where the stacked cube feels
        # the ring of the cube under it through the box-box modal network. ON by
        # default; toggle live to see the upper cube's flex appear/vanish.
        self.network = not bool(getattr(args, "no_network", False))
        # §N2 rigid ride: the lower cube's flex also lifts the upper cube's RIGID
        # body (not just its modes). Default OFF (requires the network + friction;
        # frictionless-offset drops can tunnel — the N3 gate).
        self.ride = bool(getattr(args, "ride", False))
        self.show_proxy = False
        self.static_view = False
        self._pending_rebuild = False
        # scene-dependent knobs (seeded from the scene preset; reset on rebuild)
        sp = SCENE_SPEC[self.scene]
        self.material = args.material or sp["material"]
        self.knob_thickness = sp["thickness"]
        self.knob_mass = sp["mass"]
        self.knob_drop = sp["drop"]
        self.knob_v0 = sp["v0"]
        self.knob_iters, self.knob_subs = _xpbd_iter_floor(self.solver, sp)
        self.knob_impedance = 1.0
        self.knob_damping = 1.0
        # modal under-relax: None ⇒ adopt the solver's own default (AVBD 0.10,
        # XPBD 0.25); a CLI/GUI value overrides it on both solvers.
        self.knob_modal_relax = args.modal_relax
        self._eff_modal_relax = 0.25
        # Energy-conserving (implicit-midpoint) modal step vs backward Euler.
        # NOTE: only delivers a clean ring when the q-block is solved enough
        # (modal under-relax ≳ 0.5); at low relax the under-solve re-dissipates
        # it. See memory symplectic-modal-ring-coupled-solver-findings.
        # Symplectic (implicit-midpoint) modal step is the DEFAULT here; --be
        # opts back to the dissipative backward-Euler reference. (The solver
        # CLASS default stays BE for parity tests / CLAUDE.md; this is the viser
        # default only.) --symplectic is kept for explicitness (no-op vs default).
        self.symplectic = not bool(getattr(args, "be", False))
        # Symplectic implies --no-cargo (the symplectic modal path is host
        # non-cargo only; the augmented cargo q-block stays BE).
        self.no_cargo = bool(getattr(args, "no_cargo", False)) or self.symplectic
        # §N2/X1 network passivity clamp. OFF ⇒ the ledger runs in MONITOR mode
        # (records the injection, bit-identical physics); ON ⇒ the active clamp
        # scales the augmented modal state [q_support; a_cargo…] back onto the
        # passive manifold (ΔE_modal ≤ η·ΔE_rigid_loss). Cargo scene only.
        self.passivity = bool(getattr(args, "passivity", False))
        # --inject: the over-injecting preset (see the arg help). Runs on the BE
        # cargo path (the network lives in the augmented q-block) at the STARVED
        # real-time budget — 2 iterations × 1 substep — where the fixed-low-
        # iteration local solver under-converges and injects (~20× over the
        # rigid-loss budget). This is the honest failure mode (relax stays ≤ 1,
        # the valid under-relaxation range): the real-time regime creates the
        # energy injection the convergent offline solver never had.
        if bool(getattr(args, "inject", False)):
            self.symplectic = False
            self.no_cargo = False
            self.network = True
            self.knob_iters, self.knob_subs = 2, 1
            self.knob_modal_relax = 1.0
        self.render_thick = sp["thickness"]
        self._slab_faces = _slab_faces(N_GRID_X, N_GRID_Z)
        self._q_static = None        # EMA of rs.q for the "static" modal view
        self._build()
        self._init_gui()

    # ---- scene + render setup ---------------------------------------
    def _build(self):
        # Both "avbd" and "xpbd" are NATIVE solvers (no coupler); each carries
        # full cargo (rigid/fem_rigid/fem/abd) in every scene. The only routing
        # is the documented abd → AVBD fallback (abd's stiff nonlinear V⊥ is the
        # XPBD caveat; _effective_solver handles it).
        eff = _effective_solver(self.solver, self.kind)
        if self.scene == "cargo":
            eff = "avbd"     # the box-box modal network is AVBD-native (XPBD = N5)
        self._eff_solver = eff
        rd = self.device.startswith("cuda")
        mat = _MATERIAL.get(self.material, _MATERIAL["wood"])
        # Candidate kwargs; mass/drop map onto whatever name the builder exposes.
        # Support material → (E, ρ): production scenes take youngs/density, the
        # cargo builder takes support_youngs/support_density — pass both, the
        # signature filter below keeps whichever the chosen builder accepts.
        # --no-cargo: rigid impactor (cargo_material=None) → the prompt's
        # acceptance shelf (non-cargo). Required for the symplectic modal path,
        # which is host non-cargo only (the augmented cargo q-block is BE), so
        # symplectic forces non-cargo on every (re)build → it persists across
        # scene/solver switches.
        cargo_kind = None if (self.no_cargo or self.symplectic) else self.kind
        cand = dict(
            device=self.device, solver=eff, cargo_material=cargo_kind,
            iterations=int(self.knob_iters), avbd_substeps=int(self.knob_subs),
            support_thickness=float(self.knob_thickness),
            youngs=float(mat.youngs), density=float(mat.density),
            support_youngs=float(mat.youngs), support_density=float(mat.density),
            impactor_drop_height=float(self.knob_drop),
            pot_drop_height=float(self.knob_drop),
            drop_height=float(self.knob_drop),
            impactor_v0=float(self.knob_v0),
            modal_impedance_scale=float(self.knob_impedance),
            modal_damping_scale=float(self.knob_damping),
            device_resident=rd,
        )
        if self.knob_mass is not None:
            cand["impactor_mass"] = float(self.knob_mass)
            cand["pot_mass"] = float(self.knob_mass)
        if self.scene == "cargo":
            # The cargo scene is the §N2 modal-network stack: 4 deformable cubes
            # (resting | impactor | offset stack) on the slab, the stacked cube
            # fed by the ring of the cube under it. AVBD-only (network is native
            # to Solver6DOF); its own kwarg names, so build it directly.
            self.handle = build_cargo_network_scene(
                network=self.network, ride=self.ride, kind=self.kind,
                device=self.device,
                solver="avbd", iterations=int(self.knob_iters),
                substeps=int(self.knob_subs),
                support_thickness=float(self.knob_thickness),
                support_youngs=float(mat.youngs),
                support_density=float(mat.density),
                impactor_drop=float(self.knob_drop), device_resident=rd)
        else:
            builder = _PROD[self.scene]
            params = inspect.signature(builder).parameters
            # filter to what each (heterogeneous) builder actually accepts: the
            # production scenes take cargo_material, dinner has no
            # support_thickness / impactor_v0, etc.
            kwargs = {k: v for k, v in cand.items() if k in params}
            self.handle = builder(**kwargs)
        self.rs = self.handle.rs
        self.world = self.handle.world
        # No coupler: both solvers are native. The deformable cube state and all
        # HUD diagnostics come from self.world._solver directly.
        # HUD cargo index: the STACKED (upper) cube for the network cargo scene —
        # the one whose |a| the network makes ring; the impactor's cargo idx
        # otherwise.
        if self.scene == "cargo":
            self._cargo_idx = self.handle.avbd_idx["upper"]
        else:
            self._cargo_idx = getattr(self.handle, "cargo_avbd_idx", None)
        if self._cargo_idx is None:
            self._cargo_idx = getattr(self.rs, "_native_cargo_avbd_idx", None)
        self._q_static = self.rs.q.copy()
        # modal under-relax: apply the CLI/GUI override if set, else read back
        # the new solver's own default so the slider/HUD reflect the truth.
        if self.knob_modal_relax is not None:
            self._set_solver_modal_relax(self.knob_modal_relax)
        self._eff_modal_relax = self._solver_modal_relax(self.world._solver)
        self._set_solver_symplectic(self.symplectic)
        self._apply_passivity()
        self._collect_render()
        self._make_meshes()

    def _collect_render(self):
        """Build the rigid-box list + the LIST of deformable cargo cubes. The
        cargo scene has FOUR deformables (the modal-network stack); the
        production scenes have one (the impactor) + rigid bystanders."""
        self._boxes = []      # (avbd_idx, half, color_u8)
        self._deforms = []    # list of {name, cube, idx, col, half}
        if self.scene == "cargo":
            # colour the two STACKED (box-box-only) cubes warm (the eye tracks
            # the ring climbing the tower), the slab-resting cubes by material.
            hl = {"mid": (240, 165, 60), "upper": (232, 113, 10)}
            for name, cube in self.handle.cubes.items():
                h = cube.half_extent
                self._deforms.append(dict(
                    name=name, cube=cube, idx=self.handle.avbd_idx[name],
                    col=hl.get(name, _CUBE_COLOR[self.kind]), half=(h, h, h)))
            return
        imp_dcr = self.handle.impactor_idx
        cargo_idx = self.handle.cargo_avbd_idx
        for b in self.handle.bodies:
            if b.dcr_idx == imp_dcr:
                continue                      # the impactor is the deformable
            desc = self.world._descs[b.dcr_idx]
            if desc.avbd_body is None:
                continue
            col = tuple(int(255 * c) for c in b.color)
            self._boxes.append((int(desc.avbd_body.index), b.half_extents, col))
        if self.handle.cargo_cube is not None and cargo_idx is not None:
            imp = next(b for b in self.handle.bodies if b.dcr_idx == imp_dcr)
            self._deforms.append(dict(
                name="impactor", cube=self.handle.cargo_cube, idx=cargo_idx,
                col=_CUBE_COLOR[self.kind], half=imp.half_extents))
        else:
            # rigid impactor (cargo_material=None): render it as a box too.
            for b in self.handle.bodies:
                if b.dcr_idx == imp_dcr:
                    desc = self.world._descs[b.dcr_idx]
                    col = tuple(int(255 * c) for c in b.color)
                    self._boxes.append(
                        (int(desc.avbd_body.index), b.half_extents, col))

    def _make_meshes(self):
        # Skin the slab to the selected support material (color + flat/smooth
        # shading), so steel looks like steel and wood like wood.
        mat = _MATERIAL.get(self.material, _MATERIAL["wood"])
        self.support = self.server.scene.add_mesh_simple(
            "/support",
            vertices=_slab_verts(self.rs, self._render_q(), self.support_exag,
                                 self.render_thick),
            faces=self._slab_faces, color=_mat_color_u8(self.material),
            flat_shading=mat.flat, side="double")
        P, Q = self.world._solver.positions(), self.world._solver.orientations()
        self._box_meshes = []
        for i, (idx, half, col) in enumerate(self._boxes):
            m = self.server.scene.add_mesh_simple(
                f"/box_{i}", vertices=_box_verts(half, P[idx], Q[idx]),
                faces=_BOX_FACES, color=col, flat_shading=True, side="double")
            self._box_meshes.append(m)
        self._deform_meshes = []
        for k, d in enumerate(self._deforms):
            self._deform_meshes.append(self.server.scene.add_mesh_simple(
                f"/deform_{k}", vertices=self._deform_verts(d),
                faces=self._deform_faces(d), color=d["col"],
                flat_shading=True, side="double"))

    def _render_q(self):
        return self._q_static if self.static_view else self.rs.q

    def _deform_faces(self, d) -> np.ndarray:
        if self.show_proxy:
            return _BOX_FACES
        return d["cube"].surf_faces.astype(np.int32)

    def _deform_verts(self, d) -> np.ndarray:
        cube, idx = d["cube"], d["idx"]
        P, Q = self.world._solver.positions(), self.world._solver.orientations()
        if self.show_proxy:                      # the rigid collision box
            return _box_verts(d["half"], P[idx], Q[idx])
        qx = Q[idx]
        z = np.zeros(7 + cube.k)
        z[0:3] = P[idx].astype(np.float64)
        z[3:7] = (qx[3], qx[0], qx[1], qx[2])           # xyzw -> wxyz
        z[7:] = self.world._solver.cargo_a(idx)          # native: cube state from the solver
        return cube.deformed_surface(z, self.cube_exag).astype(np.float32)

    def _rebuild(self):
        names = (["/support"]
                 + [f"/deform_{k}" for k in range(len(self._deforms))]
                 + [f"/box_{i}" for i in range(len(self._boxes))])
        for n in names:
            try:
                self.server.scene.remove_by_name(n)
            except Exception:
                pass
        self._build()

    # ---- GUI ---------------------------------------------------------
    def _init_gui(self):
        g = self.server.gui
        sp = SCENE_SPEC[self.scene]
        imp = sp["label"]
        with g.add_folder("scene × solver × material × device"):
            self.gui_scene = g.add_dropdown("scene", SCENES,
                                            initial_value=self.scene)
            self.gui_solver = g.add_dropdown("solver", SOLVERS,
                                             initial_value=self.solver)
            self.gui_kind = g.add_dropdown("material", KINDS,
                                           initial_value=self.kind)
            self.gui_device = g.add_dropdown("device", ("cpu", "cuda:0"),
                                             initial_value=self.device)
        with g.add_folder("Sim"):
            self.gui_pause = g.add_checkbox("pause", initial_value=self.paused)
            self.gui_speed = g.add_slider("speed", 0.05, 2.0, 0.05, self.speed)
            self.gui_reset = g.add_button("reset / rebuild")
        with g.add_folder("Scene (press reset / rebuild to apply)"):
            self.gui_material = g.add_dropdown(
                "support material", tuple(_MATERIAL.keys()),
                initial_value=self.material,
                hint="slab Young's modulus + density (+ render look). Stiffer = "
                     "less deflection. Press reset / rebuild to apply.")
            self.gui_thickness = g.add_slider(
                "support thickness [mm]", 5.0, 120.0, 1.0,
                float(self.knob_thickness) * 1e3)
            self.gui_mass = g.add_slider(
                f"{imp} mass [kg]", sp["mass_rng"][0], sp["mass_rng"][1], 0.1,
                float(self.knob_mass if self.knob_mass is not None else 1.0))
            self.gui_drop = g.add_slider(
                f"{imp} drop height [m]", sp["drop_rng"][0], sp["drop_rng"][1],
                0.01, float(self.knob_drop))
            self.gui_v0 = g.add_slider(
                f"{imp} launch velocity vy [m/s]", -5.0, 0.0, 0.1,
                float(self.knob_v0),
                hint="extra downward velocity on top of the drop (0 = rest)")
        with g.add_folder("Reduced-modal solver (press reset / rebuild)"):
            self.gui_iters = g.add_slider("iterations", 2, 32, 1,
                                          int(self.knob_iters))
            self.gui_iters.on_update(self._iters_changed)   # live
            self.gui_subs = g.add_slider("substeps (rebuild)", 1, 16, 1,
                                         int(self.knob_subs))
            self.gui_impedance = g.add_slider("modal impedance gain", 0.25, 16.0,
                                              0.25, float(self.knob_impedance))
            self.gui_damping = g.add_slider("modal damping scale", 0.1, 8.0, 0.1,
                                            float(self.knob_damping))
            self.gui_modal_relax = g.add_slider(
                "modal under-relax", 0.02, 1.0, 0.01,
                float(min(max(self._eff_modal_relax, 0.02), 1.0)),
                hint="modal q chase per iteration (live). Higher = more visible "
                     "modal flex/ring; lower = damped. AVBD default 0.10, "
                     "XPBD 0.25 — this is the dominant knob behind AVBD looking "
                     "stiffer than XPBD in the same scene.")
            self.gui_modal_relax.on_update(self._modal_relax_changed)   # live
            self.gui_symplectic = g.add_checkbox(
                "symplectic modal step", initial_value=self.symplectic,
                hint="energy-conserving implicit-midpoint modal integrator vs "
                     "backward Euler (live, AVBD + XPBD). Forces non-cargo + "
                     "host q-block. AVBD needs modal under-relax ≳ 0.5 to ring; "
                     "XPBD rings at its 0.25 default.")
            self.gui_symplectic.on_update(self._symplectic_changed)      # live
            if self.scene == "cargo":
                self.gui_network = g.add_checkbox(
                    "modal contact network (stacked coupling)",
                    initial_value=self.network,
                    hint="§N2 (live, cargo scene, AVBD): box-box contacts between "
                         "cargo cubes carry modal columns, so the STACKED cube "
                         "(orange, right) rings from the cube under it. OFF ⇒ its "
                         "only contact (box-box) carries no modal column ⇒ inert. "
                         "Raise 'cube flex ×' to ~250 to see it.")
                self.gui_network.on_update(self._network_changed)         # live
                self.gui_ride = g.add_checkbox(
                    "rigid ride (flex lifts the stacked body)",
                    initial_value=self.ride,
                    hint="§N2 rigid-ride (live, cargo scene, AVBD): the box-box "
                         "gap also reads the flex, so the stacked cube's RIGID "
                         "body responds to the ring beneath it (not just its "
                         "modes). Stable with friction; needs the network on. "
                         "NOTE: the effect is ~15µm, BELOW the contact jitter — "
                         "sub-visible live; verify it via the ON−OFF difference "
                         "in docs/network/network_ride.png.")
                self.gui_ride.on_update(self._ride_changed)               # live
                self.gui_passivity = g.add_checkbox(
                    "enforce passivity bound (clamp modal E)",
                    initial_value=self.passivity,
                    hint="§N2/X1 (live, cargo scene, AVBD): cap the network's "
                         "modal energy at η·(rigid energy lost) — foundation §15, "
                         "generalized across the body-body network. OFF = monitor "
                         "(watch |a| / support modal KE inject at low iters + high "
                         "modal-relax — try --inject); ON = the clamp scales the "
                         "augmented modal state back onto the passive manifold. "
                         "Read the 'modal E vs loss budget' HUD line.")
                self.gui_passivity.on_update(self._passivity_changed)     # live
        with g.add_folder("Visualization"):
            self.gui_cube_exag = g.add_slider(
                "cube flex ×", 1.0, _EXAG_MAX, 1.0, self.cube_exag,
                hint="render-only; true flex is ~1e-5 m, raise to ~300 to see it")
            self.gui_support_exag = g.add_slider(
                "slab deflection ×", 1.0, _EXAG_MAX, 1.0, self.support_exag,
                hint="render-only exaggeration of the modal slab deflection")
            self.gui_render_thick = g.add_slider(
                "slab render thickness [mm]", 0.0, 150.0, 1.0,
                float(self.render_thick) * 1e3)
            self.gui_view = g.add_dropdown(
                "modal view", ("full (q)", "static (low-pass)"),
                initial_value="static (low-pass)" if self.static_view
                else "full (q)",
                hint="full = the live modal state incl. the dynamic ring; "
                     "static = a render-side low-pass (the resting sag only)")
            self.gui_proxy = g.add_checkbox(
                "impactor as collision proxy", initial_value=self.show_proxy,
                hint="draw the deformable impactor as the rigid box the solver "
                     "collides (no flex) instead of its skinned surface")
        with g.add_folder("two-way HUD / diagnostics"):
            self.hud_eff = g.add_text("effective solver", initial_value="—")
            self.hud_ms = g.add_text("step [ms]", initial_value="—")
            self.hud_back = g.add_text("backend", initial_value="—")
            self.hud_q = g.add_text("|q| modal", initial_value="—")
            self.hud_defl = g.add_text("max slab deflection [mm]",
                                       initial_value="—")
            self.hud_cube = g.add_text("cube deform E [J]", initial_value="—")
            self.hud_supp = g.add_text("support modal KE [J]", initial_value="—")
            self.hud_pen = g.add_text("max penetration [mm]", initial_value="—")
            self.hud_psv = g.add_text("modal E vs loss budget",
                                      initial_value="—")
            self.hud_clamp = g.add_text("passivity clamp", initial_value="—")

        # handlers
        for w in (self.gui_scene, self.gui_solver, self.gui_kind,
                  self.gui_device):
            w.on_update(lambda _=None: setattr(self, "_pending_rebuild", True))
        self.gui_reset.on_click(
            lambda _=None: setattr(self, "_pending_rebuild", True))
        self.gui_pause.on_update(
            lambda _: setattr(self, "paused", self.gui_pause.value))
        self.gui_speed.on_update(
            lambda _: setattr(self, "speed", float(self.gui_speed.value)))
        self.gui_cube_exag.on_update(
            lambda _: setattr(self, "cube_exag", float(self.gui_cube_exag.value)))
        self.gui_support_exag.on_update(
            lambda _: setattr(self, "support_exag",
                              float(self.gui_support_exag.value)))
        self.gui_render_thick.on_update(self._render_thick_changed)
        self.gui_view.on_update(
            lambda _: setattr(self, "static_view",
                              self.gui_view.value.startswith("static")))
        self.gui_proxy.on_update(self._proxy_changed)

    def _iters_changed(self, _evt):
        n = int(self.gui_iters.value)
        self.knob_iters = n
        self.world.avbd_iterations = n
        self.world._solver.iterations = n
        self.world._solver._graph = None          # force CUDA-graph recapture

    @staticmethod
    def _solver_modal_relax(sol) -> float:
        """Effective modal under-relaxation for either native solver (AVBD
        stores it in `_modal_relax`, XPBD in `modal_relax`)."""
        if hasattr(sol, "_modal_relax"):
            return float(sol._modal_relax)
        return float(getattr(sol, "modal_relax", 0.25))

    def _set_solver_modal_relax(self, val: float) -> None:
        """Apply the modal under-relaxation to whichever native solver is live.
        AVBD: `_modal_relax`. XPBD: `modal_relax` + the support-block SOR factor
        `_support_block_relax`. Nulls the captured CUDA graph so the change
        takes effect on the next step (the relax scalar is otherwise baked in
        at capture time)."""
        sol = self.world._solver
        if hasattr(sol, "_modal_relax"):
            sol._modal_relax = float(val)
        if hasattr(sol, "modal_relax"):
            sol.modal_relax = float(val)
        if hasattr(sol, "_support_block_relax"):
            sol._support_block_relax = float(val)
        sol._graph = None                         # force CUDA-graph recapture

    def _modal_relax_changed(self, _evt):
        self.knob_modal_relax = float(self.gui_modal_relax.value)
        self._set_solver_modal_relax(self.knob_modal_relax)
        self._eff_modal_relax = self.knob_modal_relax

    def _set_solver_symplectic(self, val: bool) -> None:
        """Toggle the energy-conserving (implicit-midpoint) modal step on the
        live native solver (both AVBD and XPBD expose `_modal_symplectic`).
        Forces the host q-block (AVBD `_modal_device_resident=False`; XPBD's
        `_device_compatible` already declines under symplectic) since the device
        q-block is BE-only for now. Nulls the captured CUDA graph so the change
        takes effect next step. Cargo scenes are rebuilt non-cargo by the caller
        (`cargo_kind` honors `self.symplectic`), so this only runs once the path
        supports it; it still declines if cargo is somehow live."""
        sol = self.world._solver
        if val and self._solver_has_cargo(sol):
            return                                 # rebuild (non-cargo) is pending
        if val and hasattr(sol, "_modal_device_resident"):
            sol._modal_device_resident = False     # AVBD: force host q-block
        if hasattr(sol, "_modal_symplectic"):
            sol._modal_symplectic = bool(val)
        sol._graph = None                          # force CUDA-graph recapture

    @staticmethod
    def _solver_has_cargo(sol) -> bool:
        """True if the live solver has a cargo block (AVBD `_cargo_enabled`;
        XPBD a non-empty `_cargo` dict). The symplectic modal path is non-cargo
        only, so it falls back to BE on cargo scenes."""
        return (bool(getattr(sol, "_cargo_enabled", False))
                or bool(getattr(sol, "_cargo", None)))

    def _symplectic_changed(self, _evt):
        self.symplectic = bool(self.gui_symplectic.value)
        sol = self.world._solver
        # Enabling on a live cargo scene needs a non-cargo rebuild (the augmented
        # cargo q-block is BE-only); cargo_kind now honors self.symplectic.
        if self.symplectic and self._solver_has_cargo(sol):
            self._pending_rebuild = True
        else:
            self._set_solver_symplectic(self.symplectic)

    def _network_changed(self, _evt):
        """Toggle the §N2 box-box modal network live. The flag is read each
        substep (`_build_net_rows`), so no rebuild is needed — the stacked cube
        starts/stops ringing on the next step."""
        self.network = bool(self.gui_network.value)
        sol = self.world._solver
        if hasattr(sol, "_modal_contact_network"):
            sol._modal_contact_network = self.network
            sol._graph = None                       # force CUDA-graph recapture

    def _ride_changed(self, _evt):
        """Toggle the §N2 rigid ride live (the box-box gap reads the flex, so the
        stacked body responds to the ring). Read each q-block sweep
        (`_bake_ride_crest`), so no rebuild is needed."""
        self.ride = bool(self.gui_ride.value)
        sol = self.world._solver
        if hasattr(sol, "_modal_contact_ride"):
            sol._modal_contact_ride = self.ride
            sol._graph = None                       # force CUDA-graph recapture

    def _apply_passivity(self) -> None:
        """Wire the §N2/X1 network passivity bound onto the live solver. Cargo
        scene only: enable the ledger (so the HUD reads the live modal-vs-loss
        ledger) and route the checkbox to monitor (measure the injection,
        physics-neutral) vs active (clamp the augmented modal state). Non-cargo
        or symplectic ⇒ disabled (the network bound lives in the BE cargo
        q-block, `_modal_commit_cargo`)."""
        sol = self.world._solver
        if not hasattr(sol, "_enforce_modal_passivity"):
            return
        on = (self.scene == "cargo") and bool(getattr(sol, "_cargo_enabled", False))
        sol._enforce_modal_passivity = bool(on)
        if on:
            sol._psv_monitor_only = not self.passivity
            sol._psv_ledger = None                  # fresh ledger for this build
        sol._graph = None

    def _passivity_changed(self, _evt):
        """Toggle the §N2/X1 network passivity clamp live: monitor (measure the
        injection) ↔ active (clamp the augmented modal state). Read each substep
        in `_modal_commit_cargo`, so no rebuild — the ledger keeps accumulating;
        the clamp starts biting on the next step."""
        self.passivity = bool(self.gui_passivity.value)
        sol = self.world._solver
        if hasattr(sol, "_psv_monitor_only"):
            sol._psv_monitor_only = not self.passivity
            sol._graph = None                       # force CUDA-graph recapture

    def _render_thick_changed(self, _evt):
        self.render_thick = max(0.0, float(self.gui_render_thick.value) / 1e3)

    def _proxy_changed(self, _evt):
        self.show_proxy = bool(self.gui_proxy.value)
        # face topology changes (skinned surface ↔ collision box) → recreate all
        for k in range(len(self._deform_meshes)):
            try:
                self.server.scene.remove_by_name(f"/deform_{k}")
            except Exception:
                pass
        self._deform_meshes = []
        for k, d in enumerate(self._deforms):
            self._deform_meshes.append(self.server.scene.add_mesh_simple(
                f"/deform_{k}", vertices=self._deform_verts(d),
                faces=self._deform_faces(d), color=d["col"],
                flat_shading=True, side="double"))

    def _apply_knobs_from_gui(self):
        self.material = self.gui_material.value
        self.knob_thickness = float(self.gui_thickness.value) / 1e3
        self.knob_mass = (None if self.scene == "cargo"
                          else float(self.gui_mass.value))
        self.knob_drop = float(self.gui_drop.value)
        self.knob_v0 = float(self.gui_v0.value)
        self.knob_iters = int(self.gui_iters.value)
        self.knob_subs = int(self.gui_subs.value)
        self.knob_impedance = float(self.gui_impedance.value)
        self.knob_damping = float(self.gui_damping.value)
        self.knob_modal_relax = float(self.gui_modal_relax.value)
        self.symplectic = bool(self.gui_symplectic.value)

    def _reset_knobs_to_scene(self):
        sp = SCENE_SPEC[self.scene]
        self.material = sp["material"]
        self.knob_thickness = sp["thickness"]
        self.knob_mass = sp["mass"]
        self.knob_drop = sp["drop"]
        self.knob_v0 = sp["v0"]
        self.knob_iters, self.knob_subs = _xpbd_iter_floor(self.solver, sp)
        self.knob_impedance = 1.0
        self.knob_damping = 1.0
        # follow the new solver's own default after a scene/solver switch
        self.knob_modal_relax = None
        self.render_thick = sp["thickness"]

    # ---- loop --------------------------------------------------------
    def run(self):
        print(f"\n  unified viser: http://localhost:{self.args.port}")
        print(f"  scene={self.scene} solver={self.solver} material={self.kind} "
              f"device={self.device}\n")
        while True:
            if self._pending_rebuild:
                self._pending_rebuild = False
                new_scene = self.gui_scene.value
                new_solver = self.gui_solver.value
                scene_changed = (new_scene != self.scene
                                 or new_solver != self.solver)
                self.scene = new_scene
                self.solver = new_solver
                self.kind = self.gui_kind.value
                self.device = self.gui_device.value
                if scene_changed:
                    # new scene/solver → load its presets + rebuild the GUI so
                    # the slider ranges + impactor label match (template parity).
                    self._reset_knobs_to_scene()
                    self._rebuild()
                    self.server.gui.reset()
                    self._init_gui()
                else:
                    self._apply_knobs_from_gui()
                    self._rebuild()
            if not self.paused:
                t0 = time.perf_counter()
                self.world.step()
                ms = (time.perf_counter() - t0) * 1e3
                # Both solvers are native: q lives on the solver (no coupler).
                # Mirror it into rs.q so the rs.q-based slab render + HUD work.
                mq = self.world._solver.modal_q
                if mq is not None:
                    self.rs.q[:] = mq
                # static modal view = a low-pass EMA of q (resting sag only)
                self._q_static += 0.05 * (self.rs.q - self._q_static)
                P, Q = (self.world._solver.positions(),
                        self.world._solver.orientations())
                for m, (idx, half, _) in zip(self._box_meshes, self._boxes):
                    m.vertices = _box_verts(half, P[idx], Q[idx])
                for m, d in zip(self._deform_meshes, self._deforms):
                    m.vertices = self._deform_verts(d)
                self.support.vertices = _slab_verts(
                    self.rs, self._render_q(), self.support_exag,
                    self.render_thick)
                q = self.rs.q
                defl = float(np.abs(self.rs.U_points[:, 1, :] @ q).max()) * 1e3
                eff = self._eff_solver
                self.hud_eff.value = (
                    eff if eff == self.solver
                    else f"{eff}  (abd→avbd: V⊥ not GS-stable)")
                self.hud_ms.value = f"{ms:.2f}"
                resident = getattr(self.world._solver,
                                   "hooks_device_resident", False)
                self.hud_back.value = (
                    f"{self.device} {'(GPU-resident)' if resident else ''}")
                self.hud_q.value = f"{np.linalg.norm(q):.3e}"
                self.hud_defl.value = f"{defl:.4f}"
                # HUD from the native solver (no coupler). Cube deform = ‖a‖ of
                # the cargo block; support modal KE = ½q̇ᵀM_q q̇; max penetration
                # if the solver exposes it (SolverXPBD does).
                sv = self.world._solver
                if self._cargo_idx is not None:
                    a = sv.cargo_a(self._cargo_idx)
                    self.hud_cube.value = (f"{np.linalg.norm(a):.3e}"
                                           if a.size else "rigid (k=0)")
                else:
                    self.hud_cube.value = "n/a"
                self.hud_supp.value = f"{getattr(sv, 'last_modal_KE', 0.0):.3e}"
                pen = getattr(sv, "max_penetration", None)
                self.hud_pen.value = f"{pen * 1e3:.4f}" if pen is not None else "—"
                # §N2/X1 network passivity ledger: is the modal contact network
                # injecting energy, and is the bound holding it? (foundation §15)
                L = getattr(sv, "_psv_ledger", None)
                if L is not None and getattr(sv, "_enforce_modal_passivity", False):
                    inj = not L.passive()
                    self.hud_psv.value = (
                        f"{'INJECTING ✗' if inj else 'PASSIVE ✓'}  "
                        f"excess {L.max_net_excess:+.2e} / budget "
                        f"{L.max_deposit:.2e} J")
                    mode = ("monitor" if getattr(sv, "_psv_monitor_only", True)
                            else "ACTIVE")
                    self.hud_clamp.value = f"{mode}   clamps={L.n_clamped}/{L.n_steps}"
                else:
                    self.hud_psv.value = "— (cargo + --be only)"
                    self.hud_clamp.value = "—"
            time.sleep(max(0.0, (1.0 / 120.0) / max(self.speed, 1e-3)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="cargo", choices=SCENES)
    ap.add_argument("--solver", default="xpbd", choices=SOLVERS)
    ap.add_argument("--kind", default="fem_rigid", choices=KINDS)
    ap.add_argument("--material", default=None, choices=tuple(_MATERIAL.keys()),
                    help="initial support-slab material → Young's modulus + "
                         "density (default: per-scene preset)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--modal-relax", type=float, default=0.7,
                    help="modal under-relaxation (q chase per iteration), "
                         "applied to BOTH solvers. Higher = more visible modal "
                         "flex/ring. Default 0.7 (the symplectic ring needs the "
                         "q-block solved enough; AVBD's 0.10 / XPBD's 0.25 "
                         "class defaults under-solve it). Tunable live in the "
                         "GUI.")
    ap.add_argument("--symplectic", action="store_true",
                    help="(default ON) energy-conserving implicit-midpoint "
                         "modal step. Kept for explicitness; use --be to opt "
                         "out. Toggle live in the GUI; AVBD + XPBD. Forces the "
                         "host q-block and implies --no-cargo.")
    ap.add_argument("--be", action="store_true",
                    help="use backward-Euler modal integration instead of the "
                         "(default) symplectic step. Restores the dissipative "
                         "reference path and re-enables cargo.")
    ap.add_argument("--no-cargo", action="store_true",
                    help="rigid impactor (cargo_material=None) — the prompt's "
                         "non-cargo acceptance shelf. Required for the "
                         "symplectic modal path (host non-cargo only).")
    ap.add_argument("--spin", type=float, default=4.0)
    ap.add_argument("--no-network", action="store_true",
                    help="cargo scene only: start with the §N2 box-box modal "
                         "network OFF (the stacked cube inert). Default ON. "
                         "Toggle live in the GUI.")
    ap.add_argument("--ride", action="store_true",
                    help="cargo scene only: start with the §N2 rigid ride ON "
                         "(the lower cube's flex also lifts the stacked cube's "
                         "RIGID body). Default OFF; needs the network + friction. "
                         "Toggle live in the GUI.")
    ap.add_argument("--passivity", action="store_true",
                    help="cargo scene only: start with the §N2/X1 network "
                         "passivity clamp ACTIVE (bound modal E ≤ η·rigid loss, "
                         "foundation §15). Default OFF = monitor (measure the "
                         "injection, physics-neutral). Toggle live in the GUI.")
    ap.add_argument("--inject", action="store_true",
                    help="cargo scene: a preset that makes the modal contact "
                         "network violate the passivity bound. Forces the BE cargo "
                         "path, network on, and the STARVED real-time budget (iters "
                         "2×1, modal-relax 1.0): the fixed-low-iteration local "
                         "solver under-converges and injects ~20× the rigid-loss "
                         "budget (no over-relaxation — the honest real-time "
                         "failure). The 'modal E vs loss budget' HUD reads "
                         "INJECTING ✗ with the clamp OFF; tick 'enforce passivity "
                         "bound' to flip it PASSIVE ✓. NOTE: on AVBD the injection "
                         "is a BOUNDED ledger violation (a transient that damps), "
                         "not a visual blowup — the sim stays stable either way; "
                         "the HUD, not the cubes, is where you see it.")
    ap.add_argument("--cube-exag", type=float, default=1.0,
                    help="initial cube-flex render exaggeration (1 = true scale)")
    ap.add_argument("--support-exag", type=float, default=1.0,
                    help="initial slab-deflection render exaggeration (1 = true scale)")
    ap.add_argument("--port", type=int, default=8192)
    UnifiedViser(ap.parse_args()).run()


if __name__ == "__main__":
    main()
