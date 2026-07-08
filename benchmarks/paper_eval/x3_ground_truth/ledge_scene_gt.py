#!/usr/bin/env python3
"""E2 — ledge scene: full-FEM ground truth vs the native modal method (G1).

The ledge (`scenes/reduced_ledge.py`) is a boulder dropped off-centre onto a
stiff stone SLAB that also carries a pedestal (+ 3 pillars balanced on it). The
deformable support is the slab, so the same shared-operator X3 setup applies:
ONE `FEMModel` of the slab drives BOTH arms, the native modal basis is that
operator's eigenmodes (`make_fem_modal_support`), and we compare the slab
DEFLECTION FIELD u_y (the convergent GT signal, per run_x3's honest scope).

Slab-contacting bodies: boulder (impactor at x=+0.30) and pedestal (responder at
centre) -- a natural distance pair for the falloff (E3). The 3 pillars ride the
pedestal, not the slab, so like the dinner candles they are not dynamically
simulated in the 1D-vertical GT (stated). Material softened to E=1.1 GPa (from
the scene's 1e10) so the sub-mm deflection is in the validated X3 linear regime;
the boulder impact is taken in the PRE-TOPPLE window (the linear-modes scope the
paper's Limitations already states for strong-coupling scenes).

Both arms baselined to settled rest before comparing dynamic response. GT bodies
are 1D-vertical (mass, y, vy); the response here is vertical-dominant.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

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

G = 9.81
# PAPER_CONFIG (inlined; server copy lacks paper_config.py)
ITERS, SUBSTEPS, RELAX = 16, 4, 0.7


@dataclass(frozen=True)
class LedgeSpec:
    length: float = 1.2
    width: float = 0.8
    thickness: float = 0.08
    E: float = 1.1e9            # softened from scene 1e10 -> validated linear regime
    nu: float = 0.3
    rho: float = 500.0
    nx: int = 12
    ny: int = 8
    nz: int = 2
    alpha0: float = 2.0
    alpha1: float = 1.0e-5
    # boulder (impactor) — linearized pre-topple impact (dinner-pot calibration)
    boulder_half: tuple = (0.08, 0.08, 0.08)
    boulder_mass: float = 16.0
    boulder_drop: float = 0.35
    boulder_xz: tuple = (0.30, 0.0)
    # pedestal (slab responder)
    ped_half: tuple = (0.09, 0.045, 0.09)
    ped_mass: float = 5.0
    ped_xz: tuple = (0.0, 0.0)

    @property
    def top(self) -> float:
        return self.thickness / 2.0


LEDGE = LedgeSpec()
# falloff probe line from impact (+0.30) across the pedestal to the far edge
PROBE_XZ = [(0.30, 0.0), (0.20, 0.0), (0.10, 0.0), (0.0, 0.0),
            (-0.15, 0.0), (-0.30, 0.0)]


def build_ledge_fem(spec: LedgeSpec = LEDGE) -> FEMModel:
    mesh = make_slab_tet_mesh(length=spec.length, width=spec.width,
                              height=spec.thickness, nx=spec.nx, ny=spec.ny,
                              nz=spec.nz)
    return FEMModel(mesh=mesh, material=Material(E=spec.E, nu=spec.nu, rho=spec.rho),
                    fixed_nodes=fix_corners(mesh), alpha0=spec.alpha0,
                    alpha1=spec.alpha1)


def surface_grid(spec: LedgeSpec = LEDGE):
    gx = np.linspace(-spec.length / 2, spec.length / 2, N_GRID_X)
    gz = np.linspace(-spec.width / 2, spec.width / 2, N_GRID_Z)
    return gx, gz


# --------------------------------------------------------------------------- #
# Ground truth — full-FEM slab + boulder + pedestal (1D-vertical)             #
# --------------------------------------------------------------------------- #
def run_ledge_gt(*, spec: LedgeSpec = LEDGE, h_fine: float = 5e-5,
                 k_penalty: float = 5e7, settle_t: float = 0.25,
                 record_every: int = 20) -> dict:
    top = spec.top
    bh, bm = spec.boulder_half, spec.boulder_mass
    ph, pm = spec.ped_half, spec.ped_mass
    ped_xz = (float(spec.ped_xz[0]), float(spec.ped_xz[1]))
    boulder_xz = (float(spec.boulder_xz[0]), float(spec.boulder_xz[1]))

    # settle the pedestal onto the slab, boulder parked far away.
    fem_s = build_ledge_fem(spec)
    ss = CoupledFEMRigidSim(fem=fem_s, h_fine=h_fine, k_penalty=k_penalty, gravity=-G)
    boulder_park = SimpleRigidBody(mass=bm, y=top + bh[1] + spec.boulder_drop + 100.0,
                                   half_height=bh[1], half_width_x=bh[0], half_width_z=bh[2])
    ped0 = SimpleRigidBody(mass=pm, y=top + ph[1] + 5e-3, half_height=ph[1],
                           half_width_x=ph[0], half_width_z=ph[2])
    ss.run(pot=boulder_park, plates=[ped0], plate_xz=[ped_xz], pot_xz=boulder_xz,
           t_total=settle_t, record_every=1000)
    settled_y = float(ped0.y)

    # drop phase.
    fem = build_ledge_fem(spec)
    gt = CoupledFEMRigidSim(fem=fem, h_fine=h_fine, k_penalty=k_penalty, gravity=-G)
    boulder = SimpleRigidBody(mass=bm, y=top + bh[1] + spec.boulder_drop,
                              half_height=bh[1], half_width_x=bh[0], half_width_z=bh[2])
    ped = SimpleRigidBody(mass=pm, y=settled_y, half_height=ph[1],
                          half_width_x=ph[0], half_width_z=ph[2])

    V = gt.fem.mesh.vertices
    rest_top = float(V[:, 1].max())
    gx, gz = surface_grid(spec)
    grid_xz = [(float(x), float(z)) for x in gx for z in gz]

    v_entry = float(np.sqrt(2.0 * G * spec.boulder_drop))
    t_total = v_entry / G + 0.6
    n_steps = int(t_total / h_fine)
    hf = h_fine
    grav = gt.fem.gravity_load(g=gt.gravity)
    free = gt.fem.free_dofs
    nm = gt._newmark

    times, boulder_y, ped_y, field, probe = [], [], [], [], []
    t0 = time.time()

    def _scatter(px, pz, f, fc):
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
        sb = gt._deformed_surface_y(boulder_xz[0], boulder_xz[1], u)
        pen = sb - boulder.bottom_y()
        if pen > 0:
            fp = k_penalty * pen; boulder.vy += hf * (gt.gravity + fp / boulder.mass)
            _scatter(boulder_xz[0], boulder_xz[1], fp, fc)
        else:
            boulder.vy += hf * gt.gravity
        boulder.y += hf * boulder.vy
        sp = gt._deformed_surface_y(ped_xz[0], ped_xz[1], u)
        pen = sp - ped.bottom_y()
        if pen > 0:
            fpl = k_penalty * pen; ped.vy += hf * (gt.gravity + fpl / ped.mass)
            _scatter(ped_xz[0], ped_xz[1], fpl, fc)
        else:
            ped.vy += hf * gt.gravity
        ped.y += hf * ped.vy
        nm.step(grav + fc)
        if step % record_every == 0:
            urec = nm.full_displacement()
            times.append(step * hf)
            boulder_y.append(float(boulder.y))
            ped_y.append(float(ped.y))
            field.append([gt._deformed_surface_y(px, pz, urec) - rest_top
                          for (px, pz) in grid_xz])
            probe.append([gt._deformed_surface_y(px, pz, urec) - rest_top
                          for (px, pz) in PROBE_XZ])
    wall = time.time() - t0
    return dict(times=np.array(times), boulder_y=np.array(boulder_y),
                ped_y=np.array(ped_y), field=np.array(field),
                probe=np.array(probe), gx=gx, gz=gz, v_entry=v_entry,
                wall_s=wall, sim_s=float(times[-1]) if times else 0.0)


# --------------------------------------------------------------------------- #
# Native — FEM-modal slab support + boulder + pedestal                        #
# --------------------------------------------------------------------------- #
def run_ledge_native(*, spec: LedgeSpec = LEDGE, solver: str = "avbd",
                     num_modes: int = 24, n_frames: int = 320, settle: int = 8,
                     h: float = 1.0 / 480.0, passivity: bool = True) -> dict:
    top = spec.top
    world = AVBDDCRWorld(h=h, device="cpu", avbd_iterations=ITERS,
                         avbd_substeps=SUBSTEPS,
                         solver_kind="xpbd" if solver == "xpbd" else "avbd")
    world.add_floor(floor_y=top, friction=0.5, name="ledge")
    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add

    ph = spec.ped_half
    ped_idx = add("pedestal", spec.ped_mass, ph,
                  (spec.ped_xz[0], top + ph[1] + 1e-3, spec.ped_xz[1]),
                  (0.55, 0.52, 0.47), "box", friction=0.4)
    bh = spec.boulder_half
    boulder_idx = add("boulder", spec.boulder_mass, bh,
                      (spec.boulder_xz[0], top + bh[1] + spec.boulder_drop, spec.boulder_xz[1]),
                      (0.42, 0.38, 0.32), "boulder", friction=0.5)

    fem = build_ledge_fem(spec)
    rs, modal = make_fem_modal_support(fem, num_modes=num_modes, y_rest=top,
                                       n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
                                       probe_xz=PROBE_XZ, length=spec.length,
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
    sol._modal_relax = float(RELAX)
    if passivity:
        sol._enforce_modal_passivity = True
        sol._modal_eta = 1.0
        if hasattr(sol, "_psv_monitor_only"):
            sol._psv_monitor_only = True

    gx, gz = surface_grid(spec)
    grid_xz = [(float(x), float(z)) for x in gx for z in gz]
    Phi = np.array([evaluate_basis_at_point(rs, (x, z), length=spec.length,
                    width=spec.width, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)[1, :]
                    for (x, z) in grid_xz])
    Phi_probe = np.array([evaluate_basis_at_point(rs, (x, z), length=spec.length,
                          width=spec.width, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)[1, :]
                          for (x, z) in PROBE_XZ])

    boulder_body = world._descs[boulder_idx].dcr_body
    ped_body = world._descs[ped_idx].dcr_body

    def _q():
        q = getattr(sol, "modal_q", None)
        if q is None:
            q = sol._q
        return np.asarray(q, float).copy()

    for _ in range(settle):
        world.step()
    q0 = _q()
    t0 = time.time()
    q_series, boulder_y, ped_y = [], [], []
    for _ in range(n_frames):
        world.step()
        q_series.append(_q())
        boulder_y.append(float(boulder_body.position[1]))
        ped_y.append(float(ped_body.position[1]))
    wall = time.time() - t0
    q_series = np.array(q_series)
    field = q_series @ Phi.T - (q0 @ Phi.T)
    probe = q_series @ Phi_probe.T - (q0 @ Phi_probe.T)
    f_hz = modal.frequencies / (2.0 * np.pi)
    return dict(field=field, probe=probe, gx=gx, gz=gz,
                boulder_y=np.array(boulder_y), ped_y=np.array(ped_y),
                num_modes=int(modal.num_modes), omega=np.asarray(modal.eigenvalues),
                f_hz=f_hz, wall_s=wall, sim_s=n_frames * h, dt=h)


if __name__ == "__main__":
    # smoke: shared-operator gate + a short both-arms comparison
    spec = LEDGE
    fem = build_ledge_fem(spec)
    rs, modal = make_fem_modal_support(fem, num_modes=24, y_rest=spec.top,
                                       n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z,
                                       probe_xz=PROBE_XZ, length=spec.length,
                                       width=spec.width)
    from dcr.modal.modal_analysis import ModalAnalysis
    ma = ModalAnalysis(fem=fem, num_modes=24)
    gate = float(np.max(np.abs(np.asarray(modal.eigenvalues) - np.asarray(ma.eigenvalues))))
    print(f"[gate] shared-operator eig match |Δλ|max = {gate:.3e} (want 0 to fp)")
    print(f"[gate] first 6 modal f [Hz]: {np.round(modal.frequencies[:6]/(2*np.pi), 2)}")
    nat = run_ledge_native(spec=spec, n_frames=200, h=1.0 / 240.0)
    peak_nat = float(np.max(np.abs(nat['field'])))
    print(f"[native] peak |u_y| = {peak_nat:.3e} m, modes={nat['num_modes']}, "
          f"wall={nat['wall_s']:.1f}s")
    gt = run_ledge_gt(spec=spec, h_fine=2e-4, record_every=40)   # coarse GT smoke
    peak_gt = float(np.max(np.abs(gt['field'])))
    print(f"[gt] peak |u_y| = {peak_gt:.3e} m, sim={gt['sim_s']:.3f}s, wall={gt['wall_s']:.1f}s")
    print(f"[ratio] native/GT peak deflection = {peak_nat/max(peak_gt,1e-12):.3f}")
