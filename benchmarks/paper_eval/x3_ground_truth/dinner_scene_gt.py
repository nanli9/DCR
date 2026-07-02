#!/usr/bin/env python3
"""X3 — dinner-table scene: full-FEM ground truth vs the native modal method.

The recognizable "dinner is served" arrangement (pot dropped on a table set with
plates + candles), built for BOTH arms from ONE shared `FEMModel` of the table so
the native modal basis is a reduction of the very operator the GT integrates
(same X3 correctness setup as the shelf drop, now on the production scene).

Layout mirrors `scenes/reduced_dinner_table.py` (pot at centre, 4 plates at
(±0.32,±0.28), 4 candles at (±0.50,±0.45)) on a 1.2×1.0×0.03 m table. Material is
softened to E=1.1 GPa (from the scene's stiff 1e10) so the sub-mm deflection is
in the same regime as the validated X3 shelf and visibly rings the plates; stated
where it matters. Candles are decoration that ride the surface (not dynamically
simulated in the GT); the pot (impactor) and 4 plates (responders) are the
physics compared.

Both drivers record the table surface-deflection field on a grid + every body's
world position per frame, so the renderer can pose the production glTF meshes.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dcr.geom.tet_mesh import make_slab_tet_mesh
from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.fem.newmark import CoupledFEMRigidSim, SimpleRigidBody
from dcr.avbd.world import AVBDDCRWorld
from dcr.avbd.reduced_support import evaluate_basis_at_point

from scenes.reduced_scene_common import BodyAdder, ReducedSceneBody
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z

from benchmarks.paper_eval.x3_ground_truth.fem_modal_support import (
    make_fem_modal_support, fix_corners,
)
from benchmarks.paper_eval.paper_config import PAPER_CONFIG, apply_relax, apply_passivity

G = 9.81


@dataclass(frozen=True)
class DinnerSpec:
    length: float = 1.2
    width: float = 1.0
    thickness: float = 0.03
    E: float = 1.1e9            # softened from the scene's 1e10 (visible ring)
    nu: float = 0.3
    rho: float = 600.0
    nx: int = 12
    ny: int = 10
    nz: int = 2
    alpha0: float = 2.0
    alpha1: float = 1.0e-5
    # objects (x, z), half-extents (hx,hy,hz), mass — mirror reduced_dinner_table
    pot_half: tuple = (0.13, 0.065, 0.082)
    pot_mass: float = 16.0        # heavier impactor (was 8) — bigger kick
    pot_drop: float = 0.45        # faster impact (was 0.20; v_entry≈3.0 m/s)
    plate_xz: tuple = ((-0.32, -0.28), (-0.32, 0.28), (0.32, -0.28), (0.32, 0.28))
    plate_half: tuple = (0.085, 0.010, 0.085)
    plate_mass: float = 0.4
    plate_colors: tuple = ((0.95, 0.92, 0.85), (0.85, 0.65, 0.55),
                           (0.55, 0.70, 0.85), (0.80, 0.80, 0.70))
    candle_xz: tuple = ((-0.50, -0.45), (-0.50, 0.45), (0.50, -0.45), (0.50, 0.45))
    candle_half: tuple = (0.015, 0.045, 0.015)
    candle_colors: tuple = ((0.94, 0.88, 0.74), (0.78, 0.20, 0.18),
                            (0.92, 0.86, 0.50), (0.30, 0.45, 0.55))

    @property
    def top(self) -> float:
        return self.thickness / 2.0


DINNER = DinnerSpec()


def build_dinner_fem(spec: DinnerSpec = DINNER) -> FEMModel:
    mesh = make_slab_tet_mesh(length=spec.length, width=spec.width,
                              height=spec.thickness, nx=spec.nx, ny=spec.ny,
                              nz=spec.nz)
    return FEMModel(mesh=mesh, material=Material(E=spec.E, nu=spec.nu, rho=spec.rho),
                    fixed_nodes=fix_corners(mesh), alpha0=spec.alpha0,
                    alpha1=spec.alpha1)


def surface_grid(spec: DinnerSpec = DINNER):
    """The (x,z) grid the surface field is sampled on (matches N_GRID_X/Z)."""
    gx = np.linspace(-spec.length / 2, spec.length / 2, N_GRID_X)
    gz = np.linspace(-spec.width / 2, spec.width / 2, N_GRID_Z)
    return gx, gz


# --------------------------------------------------------------------------- #
# Ground truth — full-FEM table + pot + 4 plates (1D-vertical)                 #
# --------------------------------------------------------------------------- #
def run_dinner_gt(*, spec: DinnerSpec = DINNER, h_fine: float = 5e-5,
                  k_penalty: float = 5e7, settle_t: float = 0.25,
                  record_every: int = 20) -> dict:
    top = spec.top
    ph, pm = spec.pot_half, spec.pot_mass
    bh, bm = spec.plate_half, spec.plate_mass
    plate_xz = [(float(x), float(z)) for (x, z) in spec.plate_xz]
    pot_xz = (0.0, 0.0)

    # settle plates onto the table, pot parked far away.
    fem_s = build_dinner_fem(spec)
    ss = CoupledFEMRigidSim(fem=fem_s, h_fine=h_fine, k_penalty=k_penalty, gravity=-G)
    pot_park = SimpleRigidBody(mass=pm, y=top + ph[1] + spec.pot_drop + 100.0,
                               half_height=ph[1], half_width_x=ph[0], half_width_z=ph[2])
    plates0 = [SimpleRigidBody(mass=bm, y=top + bh[1] + 5e-3, half_height=bh[1],
                               half_width_x=bh[0], half_width_z=bh[2])
               for _ in plate_xz]
    ss.run(pot=pot_park, plates=plates0, plate_xz=plate_xz, pot_xz=pot_xz,
           t_total=settle_t, record_every=1000)
    settled_y = [float(p.y) for p in plates0]

    # drop phase — driven step-by-step (record surface grid + bodies).
    fem = build_dinner_fem(spec)
    gt = CoupledFEMRigidSim(fem=fem, h_fine=h_fine, k_penalty=k_penalty, gravity=-G)
    pot = SimpleRigidBody(mass=pm, y=top + ph[1] + spec.pot_drop, half_height=ph[1],
                          half_width_x=ph[0], half_width_z=ph[2])
    plates = [SimpleRigidBody(mass=bm, y=sy, half_height=bh[1], half_width_x=bh[0],
                              half_width_z=bh[2]) for sy in settled_y]

    V = gt.fem.mesh.vertices
    rest_top = float(V[:, 1].max())
    gx, gz = surface_grid(spec)
    grid_xz = [(float(x), float(z)) for x in gx for z in gz]   # x outer

    v_entry = float(np.sqrt(2.0 * G * spec.pot_drop))
    t_total = v_entry / G + 0.6
    n_steps = int(t_total / h_fine)
    hf = h_fine
    grav = gt.fem.gravity_load(g=gt.gravity)
    free = gt.fem.free_dofs
    nm = gt._newmark

    times, pot_y = [], []
    plate_ys = [[] for _ in plate_xz]
    field = []
    t0 = time.time()

    def _scatter(px, pz, f):
        ti, bary = gt._find_closest_tri(px, pz)
        if ti < gt._top_surface_tris.shape[0]:
            tri = gt._top_surface_tris[ti]
            for k in range(3):
                dof = 3 * tri[k] + 1
                loc = np.searchsorted(free, dof)
                if loc < free.size and free[loc] == dof:
                    fc[loc] -= bary[k] * f

    for step in range(n_steps):
        u = nm.full_displacement()
        fc = np.zeros(free.size)
        sp = gt._deformed_surface_y(pot_xz[0], pot_xz[1], u)
        pen = sp - pot.bottom_y()
        if pen > 0:
            fp = k_penalty * pen; pot.vy += hf * (gt.gravity + fp / pot.mass)
            _scatter(pot_xz[0], pot_xz[1], fp)
        else:
            pot.vy += hf * gt.gravity
        pot.y += hf * pot.vy
        for i, p in enumerate(plates):
            px, pz = plate_xz[i]
            sy = gt._deformed_surface_y(px, pz, u)
            pen = sy - p.bottom_y()
            if pen > 0:
                fpl = k_penalty * pen; p.vy += hf * (gt.gravity + fpl / p.mass)
                _scatter(px, pz, fpl)
            else:
                p.vy += hf * gt.gravity
            p.y += hf * p.vy
        nm.step(grav + fc)
        if step % record_every == 0:
            urec = nm.full_displacement()
            times.append(step * hf)
            pot_y.append(float(pot.y))
            for i, p in enumerate(plates):
                plate_ys[i].append(float(p.y))
            field.append([gt._deformed_surface_y(px, pz, urec) - rest_top
                          for (px, pz) in grid_xz])
    wall = time.time() - t0
    return dict(times=np.array(times), pot_y=np.array(pot_y),
                plate_ys=np.array(plate_ys).T, settled_y=np.array(settled_y),
                field=np.array(field), gx=gx, gz=gz, plate_xz=plate_xz,
                pot_xz=pot_xz, v_entry=v_entry, wall_s=wall,
                sim_s=float(times[-1]) if times else 0.0)


# --------------------------------------------------------------------------- #
# Native — FEM-modal table support + pot + 4 plates                           #
# --------------------------------------------------------------------------- #
def run_dinner_native(*, spec: DinnerSpec = DINNER, solver: str = "avbd",
                      num_modes: int = 20, n_frames: int = 260, settle: int = 8,
                      relax: float = 1.0, h: float = 1.0 / 480.0,
                      passivity: bool = True) -> dict:
    top = spec.top
    cfg = PAPER_CONFIG
    world = AVBDDCRWorld(h=h, device="cpu", avbd_iterations=cfg["iterations"],
                         avbd_substeps=cfg["substeps"],
                         solver_kind="xpbd" if solver == "xpbd" else "avbd")
    world.add_floor(floor_y=top, friction=0.5, name="table")
    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add

    plate_xz = [(float(x), float(z)) for (x, z) in spec.plate_xz]
    for i, (px, pz) in enumerate(plate_xz):
        add(f"plate_{i}", spec.plate_mass, spec.plate_half,
            (px, top + spec.plate_half[1] + 1e-3, pz),
            spec.plate_colors[i], "plate", friction=0.4)
    ph = spec.pot_half
    pot_idx = add("pot", spec.pot_mass, ph,
                  (0.0, top + ph[1] + spec.pot_drop, 0.0),
                  (0.2, 0.18, 0.16), "pot", friction=0.5)

    fem = build_dinner_fem(spec)
    probe_xz = plate_xz + [(0.0, 0.0)]
    rs, modal = make_fem_modal_support(fem, num_modes=num_modes, y_rest=top,
                                       n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
                                       probe_xz=probe_xz, length=spec.length,
                                       width=spec.width)
    tracked = [int(world._descs[b.dcr_idx].avbd_body.index) for b in bodies
               if world._descs[b.dcr_idx].avbd_body is not None]
    rs.probe_body_indices = list(tracked)
    world.enable_reduced_modal_support(rs, tracked_body_indices=tracked,
                                       shelf_length=spec.length,
                                       shelf_width=spec.width, shelf_y_rest=top,
                                       n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)
    sol = world._solver
    sol._modal_symplectic = True
    apply_relax(sol, solver, relax)
    if passivity:
        apply_passivity(sol, solver, enable=True, eta=1.0)

    # Φ_y on the render grid, for u_field = Φ·q.
    gx, gz = surface_grid(spec)
    grid_xz = [(float(x), float(z)) for x in gx for z in gz]
    Phi = np.array([evaluate_basis_at_point(rs, (x, z), length=spec.length,
                    width=spec.width, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)[1, :]
                    for (x, z) in grid_xz])

    pot_body = world._descs[pot_idx].dcr_body
    plate_bodies = [world._descs[b.dcr_idx].dcr_body for b in bodies
                    if b.name.startswith("plate")]

    def _q():
        q = getattr(sol, "modal_q", None)
        if q is None:
            q = sol._q
        return np.asarray(q, float).copy()

    for _ in range(settle):
        world.step()
    q0 = _q()
    t0 = time.time()
    q_series, pot_y, plate_ys = [], [], []
    for _ in range(n_frames):
        world.step()
        q_series.append(_q())
        pot_y.append(float(pot_body.position[1]))
        plate_ys.append([float(b.position[1]) for b in plate_bodies])
    wall = time.time() - t0
    q_series = np.array(q_series)
    field = q_series @ Phi.T - (q0 @ Phi.T)     # (n_frames, n_grid)
    return dict(field=field, gx=gx, gz=gz, plate_xz=plate_xz,
                pot_y=np.array(pot_y), plate_ys=np.array(plate_ys),
                num_modes=num_modes, solver=solver, wall_s=wall,
                sim_s=n_frames * h, dt=h)
