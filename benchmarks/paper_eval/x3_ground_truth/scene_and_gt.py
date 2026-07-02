#!/usr/bin/env python3
"""X3 — matched shelf-drop scene for the native-vs-FEM ground-truth comparison.

ONE slab operator, TWO arms:
  * `build_fem_modal_scene(...)` — the NATIVE arm: an `AVBDDCRWorld` with an
    impactor + bystander(s) resting on a modal support whose basis is the TRUE
    FEM eigenmodes of the slab (`make_fem_modal_support`). Returns a
    `ReducedSceneHandle` so `scripts/probe_native_energy_loop.run` drives it with
    the same protocol as X0/X4 (settle → drop → per-frame ring/bystander KE).
  * `run_ground_truth(...)` — the GROUND-TRUTH arm: the SAME slab
    (`FEMModel`, same corner-fixed BCs, same E/ν/ρ/thickness) integrated as a
    full deformable body by `CoupledFEMRigidSim` (Newmark trapezoidal at
    h_fine=1e-4, penalty contact), with 1D-vertical rigid impactor + bystander.

Both arms build their `FEMModel` from the SAME `SLAB` constants and the same
`fix_corners` BCs, so the native modes are a modal reduction of the very
operator the GT integrates — the only differences are (a) k-mode truncation and
(b) the host contact model. That is exactly what X3 measures.

Scene geometry rationale: the impactor drops OFF-CENTRE (over +x) and the
bystander rests at -x, so there is a genuine impact→bystander DISTANCE for the
response-vs-distance / falloff study (plan X3 step 4b). The bystander is light
enough to be launched by the slab ring (true two-way), heavy impactor to excite
it. GT rigid bodies are vertical-only (mass, y, vy) — acceptable because this
scene's response is vertical-dominant; stated as an up-front limitation.
"""
from __future__ import annotations

import os
import sys
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

from scenes.reduced_scene_common import (
    BodyAdder, ReducedSceneBody, ReducedSceneHandle,
)
from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z
from dcr.avbd.reduced_support import evaluate_basis_at_point
from dcr.rigid.energy import rigid_kinetic_energy

from benchmarks.paper_eval.x3_ground_truth.fem_modal_support import (
    make_fem_modal_support, fix_corners,
)
from benchmarks.paper_eval.paper_config import (
    PAPER_CONFIG, apply_relax, apply_passivity,
)

G = 9.81


# --------------------------------------------------------------------------- #
# Shared slab + scene spec (single source of truth for BOTH arms)             #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SlabSpec:
    # Wood-like slab, identical to scripts/run_stage7.run_comparison's GT slab.
    length: float = 1.0
    width: float = 0.6
    thickness: float = 0.05
    E: float = 1.1e9
    nu: float = 0.3
    rho: float = 770.0
    # Mesh resolution (shared by GT integration AND modal extraction — so both
    # arms see the SAME operator). nz=2 keeps the Newmark GT tractable while
    # giving a real bending spectrum.
    nx: int = 10
    ny: int = 6
    nz: int = 2
    # Rayleigh damping (matches run_comparison: alpha0=2.0, alpha1=1e-5).
    alpha0: float = 2.0
    alpha1: float = 1.0e-5

    @property
    def support_top(self) -> float:
        return self.thickness / 2.0


@dataclass(frozen=True)
class SceneSpec:
    # Impactor (heavy, dropped OFF-CENTRE over +x).
    impactor_mass: float = 3.0
    impactor_half: tuple = (0.08, 0.08, 0.08)
    impactor_x: float = 0.28
    drop_height: float = 0.08
    # Bystander(s) resting at increasing distance on -x (probes the falloff).
    bystander_mass: float = 0.3
    bystander_half: tuple = (0.06, 0.02, 0.06)
    bystander_xs: tuple = (-0.28,)          # add more for the falloff sweep


SLAB = SlabSpec()
SCENE = SceneSpec()


def build_fem(slab: SlabSpec = SLAB) -> FEMModel:
    """The shared slab operator (both arms call this with identical args)."""
    mesh = make_slab_tet_mesh(length=slab.length, width=slab.width,
                              height=slab.thickness, nx=slab.nx, ny=slab.ny,
                              nz=slab.nz)
    return FEMModel(mesh=mesh, material=Material(E=slab.E, nu=slab.nu, rho=slab.rho),
                    fixed_nodes=fix_corners(mesh),
                    alpha0=slab.alpha0, alpha1=slab.alpha1)


# --------------------------------------------------------------------------- #
# NATIVE arm — ReducedSceneHandle driven by probe_native_energy_loop.run      #
# --------------------------------------------------------------------------- #
def build_fem_modal_scene(
    *,
    h: float = 1.0 / 120.0,
    device: str = "cpu",
    iterations: int = 16,
    avbd_substeps: int = 4,
    solver: str = "xpbd",
    num_modes: int = 16,
    slab: SlabSpec = SLAB,
    scene: SceneSpec = SCENE,
    bystander_xs: tuple | None = None,
) -> ReducedSceneHandle:
    """Native arm: impactor + bystander(s) on a TRUE-FEM-mode modal support."""
    xs = tuple(scene.bystander_xs if bystander_xs is None else bystander_xs)
    top = slab.support_top
    world = AVBDDCRWorld(
        h=h, device=device,
        avbd_iterations=int(iterations), avbd_substeps=int(avbd_substeps),
        solver_kind="xpbd" if solver == "xpbd" else "avbd",
    )
    world.add_floor(floor_y=top, friction=0.5, name="slab")

    bodies: list[ReducedSceneBody] = []
    add = BodyAdder(world, bodies).add

    # Bystander(s) resting on the slab at increasing distance from the impact.
    resting_xz: list[tuple[float, float]] = []
    for i, bx in enumerate(xs):
        add(f"bystander_{i}", float(scene.bystander_mass), scene.bystander_half,
            (bx, top + scene.bystander_half[1] + 1e-3, 0.0),
            (0.2, 0.55, 0.25), "book", friction=0.3)
        resting_xz.append((float(bx), 0.0))

    # Impactor dropped off-centre over +x.
    ih = scene.impactor_half
    impactor_idx = add(
        "impactor", float(scene.impactor_mass), ih,
        (scene.impactor_x, top + ih[1] + float(scene.drop_height), 0.0),
        (0.45, 0.12, 0.12), "book", friction=0.5)

    # --- Build the FEM-modal support from the SHARED slab operator. ---
    fem = build_fem(slab)
    probe_xz = resting_xz + [(scene.impactor_x, 0.0)]
    rs, modal = make_fem_modal_support(
        fem, num_modes=int(num_modes), y_rest=top,
        n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z, probe_xz=probe_xz,
        length=slab.length, width=slab.width)

    # Map DCR→AVBD indices for every dynamic body and install (mirrors
    # scenes/reduced_scene_common.build_support_and_attach's install path).
    tracked: list[int] = []
    for b in bodies:
        desc = world._descs[b.dcr_idx]
        if desc.avbd_body is not None:
            tracked.append(int(desc.avbd_body.index))
    rs.probe_body_indices = list(tracked)

    world.enable_reduced_modal_support(
        rs, tracked_body_indices=tracked,
        shelf_length=slab.length, shelf_width=slab.width, shelf_y_rest=top,
        n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)

    handle = ReducedSceneHandle(
        world=world, rs=rs, impactor_idx=impactor_idx,
        probe_indices=[b.dcr_idx for b in bodies],
        bodies=bodies, name="X3 FEM-modal shelf drop",
        impactor_label="impactor")
    handle.modal = modal          # stash for f1 readout (extra attr, harmless)
    return handle


# --------------------------------------------------------------------------- #
# GROUND-TRUTH arm — full-FEM slab via CoupledFEMRigidSim                      #
# --------------------------------------------------------------------------- #
def run_ground_truth(
    *,
    slab: SlabSpec = SLAB,
    scene: SceneSpec = SCENE,
    bystander_xs: tuple | None = None,
    h_fine: float = 1.0e-4,
    k_penalty: float = 5.0e7,
    settle_t: float = 0.25,
    record_every: int = 10,
    probe_defl_xz: list[tuple[float, float]] | None = None,
) -> dict:
    """Ground truth: same slab, integrated as a full deformable body.

    Two-phase (mirrors run_comparison): settle the bystander(s) onto the
    deformable slab with the impactor parked far away, snapshot settled y and
    zero velocities, then release the impactor from the drop height. Returns a
    dict with times, impactor y(t), bystander y(t)/vy(t), settled baselines,
    the impactor contact-entry velocity, and a mid-span slab deflection trace.
    """
    xs = tuple(scene.bystander_xs if bystander_xs is None else bystander_xs)
    top = slab.support_top
    ih = scene.impactor_half
    bh = scene.bystander_half
    pot_xz = (scene.impactor_x, 0.0)
    plate_xz = [(float(bx), 0.0) for bx in xs]

    # ---- Settle phase: impactor parked high & far, bystanders drop lightly. ----
    fem_settle = build_fem(slab)
    settle_sim = CoupledFEMRigidSim(fem=fem_settle, h_fine=h_fine,
                                    k_penalty=k_penalty, gravity=-G)
    pot_park = SimpleRigidBody(
        mass=scene.impactor_mass, y=top + ih[1] + scene.drop_height + 100.0,
        half_height=ih[1], half_width_x=ih[0], half_width_z=ih[2])
    plates0 = [SimpleRigidBody(
        mass=scene.bystander_mass, y=top + bh[1] + 5e-3,
        half_height=bh[1], half_width_x=bh[0], half_width_z=bh[2]) for _ in xs]
    settle_sim.run(pot=pot_park, plates=plates0, plate_xz=plate_xz,
                   pot_xz=pot_xz, t_total=settle_t, record_every=1000)
    settled_y = [float(p.y) for p in plates0]

    # ---- Drop phase: fresh slab, impactor released, bystanders at settled y. ----
    fem_drop = build_fem(slab)
    gt = CoupledFEMRigidSim(fem=fem_drop, h_fine=h_fine, k_penalty=k_penalty,
                            gravity=-G)
    pot = SimpleRigidBody(
        mass=scene.impactor_mass, y=top + ih[1] + scene.drop_height,
        half_height=ih[1], half_width_x=ih[0], half_width_z=ih[2])
    plates = [SimpleRigidBody(
        mass=scene.bystander_mass, y=sy, half_height=bh[1],
        half_width_x=bh[0], half_width_z=bh[2]) for sy in settled_y]

    # mid-span top-surface vertex, for the slab deflection trace.
    V = gt.fem.mesh.vertices
    top_mask = np.abs(V[:, 1] - V[:, 1].max()) < 1e-6
    top_idx = np.where(top_mask)[0]
    mid_vidx = int(top_idx[np.argmin(V[top_idx, 0] ** 2 + V[top_idx, 2] ** 2)])
    rest_top = float(V[:, 1].max())

    # Surface-deflection probe points (a distance sweep from the impact point):
    # the CONVERGENT ground-truth signal — u_y(x,t) at increasing distance. The
    # native arm's Φ(x)·q(t) is compared against exactly these.
    if probe_defl_xz is None:
        probe_defl_xz = [(scene.impactor_x, 0.0)] + plate_xz
    probe_defl_xz = [(float(x), float(z)) for (x, z) in probe_defl_xz]

    # contact-entry velocity: free-fall over drop_height.
    v_entry = float(np.sqrt(2.0 * G * scene.drop_height))

    # Drive the coupled sim step-by-step. This replicates CoupledFEMRigidSim.run's
    # inline contact+Newmark loop EXACTLY (same helper calls, same penalty force),
    # adding only a mid-span deflection recorder — the class exposes no per-step
    # method, so faithful replication is the honest way to sample it.
    t_total = v_entry / G + 0.6            # fall time + ring window
    n_steps = int(t_total / h_fine)
    hf = h_fine
    grav_load = gt.fem.gravity_load(g=gt.gravity)
    free = gt.fem.free_dofs
    nm = gt._newmark
    times, pot_y = [], []
    plate_ys = [[] for _ in xs]
    plate_vys = [[] for _ in xs]
    mid_defl = []
    probe_defl = []            # (n_frames, n_probe) surface u_y at the sweep pts

    def _scatter(px, pz, f):
        tri_idx, bary = gt._find_closest_tri(px, pz)
        if tri_idx < gt._top_surface_tris.shape[0]:
            tri = gt._top_surface_tris[tri_idx]
            for k in range(3):
                dof_y = 3 * tri[k] + 1
                loc = np.searchsorted(free, dof_y)
                if loc < free.size and free[loc] == dof_y:
                    f_contact[loc] -= bary[k] * f

    for step in range(n_steps):
        u_full = nm.full_displacement()
        f_contact = np.zeros(free.size, dtype=np.float64)
        # impactor → slab
        surf_y_pot = gt._deformed_surface_y(pot_xz[0], pot_xz[1], u_full)
        pen = surf_y_pot - pot.bottom_y()
        if pen > 0:
            f_pot = gt.k_penalty * pen
            pot.vy += hf * (gt.gravity + f_pot / pot.mass)
            _scatter(pot_xz[0], pot_xz[1], f_pot)
        else:
            pot.vy += hf * gt.gravity
        pot.y += hf * pot.vy
        # bystander(s) → slab
        for i, p in enumerate(plates):
            px, pz = plate_xz[i]
            surf_y = gt._deformed_surface_y(px, pz, u_full)
            pen = surf_y - p.bottom_y()
            if pen > 0:
                f_pl = gt.k_penalty * pen
                p.vy += hf * (gt.gravity + f_pl / p.mass)
                _scatter(px, pz, f_pl)
            else:
                p.vy += hf * gt.gravity
            p.y += hf * p.vy
        nm.step(grav_load + f_contact)
        if step % record_every == 0:
            u_full_rec = nm.full_displacement()
            times.append(step * hf)
            pot_y.append(float(pot.y))
            for i, p in enumerate(plates):
                plate_ys[i].append(float(p.y))
                plate_vys[i].append(float(p.vy))
            mid_defl.append(float(u_full_rec[3 * mid_vidx + 1]))
            # surface deflection at each sweep point (absolute deformed y − rest).
            probe_defl.append([
                gt._deformed_surface_y(px, pz, u_full_rec) - rest_top
                for (px, pz) in probe_defl_xz])

    return dict(
        times=np.array(times), pot_y=np.array(pot_y),
        plate_ys=np.array(plate_ys).T, plate_vys=np.array(plate_vys).T,
        mid_defl=np.array(mid_defl), settled_y=np.array(settled_y),
        probe_defl=np.array(probe_defl), probe_defl_xz=probe_defl_xz,
        v_entry=v_entry, plate_xz=plate_xz, pot_xz=pot_xz)


# --------------------------------------------------------------------------- #
# NATIVE driver — records q(t) so we can form Φ(x)·q(t) at any surface point   #
# --------------------------------------------------------------------------- #
def run_native(
    *,
    solver: str = "xpbd",
    num_modes: int = 16,
    slab: SlabSpec = SLAB,
    scene: SceneSpec = SCENE,
    bystander_xs: tuple | None = None,
    probe_defl_xz: list[tuple[float, float]] | None = None,
    n_frames: int = 200,
    settle: int = 8,
    relax: float | None = None,
    passivity: bool = True,
    h: float = 1.0 / 120.0,
) -> dict:
    """Native arm at PAPER_CONFIG. Returns q(t), the surface deflection field
    u_y(x,t)=Φ(x)·q(t) at the sweep points (directly comparable to the GT
    `probe_defl`), bystander lift/KE, modal ring energy, and wall-clock.

    The X1 passive-energy clamp is ON by default (the paper config) — it is
    inert in this safe region, so it does not perturb the response."""
    import time as _time
    cfg = PAPER_CONFIG
    build = build_fem_modal_scene(
        h=h, iterations=cfg["iterations"], avbd_substeps=cfg["substeps"],
        solver=solver, num_modes=int(num_modes), slab=slab, scene=scene,
        bystander_xs=bystander_xs)
    world = build.world
    sol = world._solver
    sol._modal_symplectic = True
    apply_relax(sol, solver, relax)
    if passivity:
        apply_passivity(sol, solver, enable=True, eta=1.0)

    xs = tuple(scene.bystander_xs if bystander_xs is None else bystander_xs)
    plate_xz = [(float(bx), 0.0) for bx in xs]
    if probe_defl_xz is None:
        probe_defl_xz = [(scene.impactor_x, 0.0)] + plate_xz
    probe_defl_xz = [(float(x), float(z)) for (x, z) in probe_defl_xz]
    # Φ_y at each sweep point (bilinear on the FEM-mode grid), (n_probe, r).
    Phi_y = np.array([
        evaluate_basis_at_point(build.rs, (x, z), length=slab.length,
                                width=slab.width, n_grid_x=N_GRID_X,
                                n_grid_z=N_GRID_Z)[1, :]
        for (x, z) in probe_defl_xz])

    bystanders = [world._descs[b.dcr_idx].dcr_body for b in build.bodies
                  if b.name.startswith("bystander")]
    m_by = [b.mass for b in bystanders]

    def _q_now():
        q = getattr(sol, "modal_q", None)
        if q is None:
            q = getattr(sol, "_q", None)
        return np.asarray(q, dtype=np.float64).copy()

    for _ in range(settle):
        world.step()
    y0 = [float(b.position[1]) for b in bystanders]
    q0 = _q_now()

    t0 = _time.time()
    q_series, Eslab = [], []
    by_ke = np.zeros(len(bystanders))
    by_lift = np.zeros(len(bystanders))
    for _ in range(n_frames):
        world.step()
        q_series.append(_q_now())
        Eslab.append(float(getattr(sol, "last_modal_KE", 0.0))
                     + float(getattr(sol, "last_modal_PE", 0.0)))
        for i, b in enumerate(bystanders):
            by_ke[i] = max(by_ke[i], rigid_kinetic_energy([b]))
            by_lift[i] = max(by_lift[i], float(b.position[1]) - y0[i])
    wall = _time.time() - t0

    q_series = np.array(q_series)                    # (n_frames, r)
    # surface deflection field relative to settled rest: (Φ·q)(t) − (Φ·q0).
    u_field = q_series @ Phi_y.T - (q0 @ Phi_y.T)    # (n_frames, n_probe)
    return dict(
        q=q_series, u_field=u_field, probe_defl_xz=probe_defl_xz,
        Eslab=np.array(Eslab), by_ke=by_ke, by_lift=by_lift, m_by=m_by,
        num_modes=int(num_modes), solver=solver, wall_s=wall,
        sim_s=n_frames * h, dt=h, rs=build.rs, modal=build.modal)
