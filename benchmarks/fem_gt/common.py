"""All-FEM ground truth for the production scenes (G1, every body FEM).

Builds a `MultiFEMSim` (dcr/fem/multibody_gt.py) whose geometry is mirrored
DIRECTLY from a live native scene handle — body half-extents and initial
orientations from the handle metadata, initial positions from the solver
state at t=0, masses from the world descriptors — so the GT arm cannot drift
from the native scenes. The support slab is a corner-fixed FEM body (the X3
`fix_corners` pattern); every other body is a free FEM box.

Two-phase X3 protocol: park the impactor +100 m away (rigid translation is a
zero-energy move), settle the resting bodies, teleport it back, run.

Scoring contract (validation plan §6.1): the convergent GT signal is the
support DEFLECTION FIELD u_y (recorded per frame at the support's top
surface), plus the interval-averaged contact-force ledger. Launch KE is
contact-model-limited — report it only as a secondary.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dcr.fem.fem_model import FEMModel
from dcr.fem.material import Material
from dcr.fem.multibody_gt import (
    FEMBody,
    MultiFEMSim,
    corner_column_nodes,
    make_box_fem_body,
)
from dcr.geom.tet_mesh import make_slab_tet_mesh

OUT_DIR = Path(__file__).resolve().parent / "out"


@dataclass(frozen=True)
class SupportSpec:
    """The scene's support slab (dims/material mirrored from the builder)."""
    length: float
    width: float
    thickness: float
    top: float
    youngs: float
    density: float


# Mirrored verbatim from the scene builders' defaults.
SUPPORTS = {
    "truck":  SupportSpec(2.5, 1.5, 0.06, 0.03, 1.0e10, 500.0),
    "ledge":  SupportSpec(1.2, 0.8, 0.08, 0.04, 1.0e10, 500.0),
    "shelf":  SupportSpec(0.8, 0.3, 0.03, 0.015, 0.5e9, 600.0),
    "dinner": SupportSpec(1.2, 1.0, 0.03, 0.03, 1.0e10, 500.0),
    "cargo":  SupportSpec(0.8, 0.4, 0.02, 0.0, 1.0e10, 500.0),
}


def _slab_resolution(spec: SupportSpec) -> tuple[int, int, int]:
    """X3-density mesh (10 cells/m in plan, 2 through thickness)."""
    return (max(6, int(round(10.0 * spec.length))),
            max(4, int(round(10.0 * spec.width))), 2)


def _oriented_half(half, quat_wxyz) -> tuple[float, float, float]:
    """Axis-aligned half-extents after the body's initial orientation. Only
    identity and ±90° about +Y are representable by an axis-aligned GT box
    (the dinner cutlery); anything else is a scene we don't build yet."""
    w, x, y, z = (float(v) for v in quat_wxyz)
    hx, hy, hz = (float(v) for v in half)
    if abs(w - 1.0) < 1e-9 or abs(w + 1.0) < 1e-9:
        return (hx, hy, hz)
    if abs(x) < 1e-9 and abs(z) < 1e-9 and abs(abs(y) - abs(w)) < 1e-6:
        return (hz, hy, hx)                      # ±90° about +Y: swap x/z
    raise ValueError(f"GT box cannot represent orientation {quat_wxyz}")


def build_support_body(spec: SupportSpec, h_fine: float) -> FEMBody:
    nx, ny, nz = _slab_resolution(spec)
    mesh = make_slab_tet_mesh(length=spec.length, width=spec.width,
                              height=spec.thickness, nx=nx, ny=ny, nz=nz)
    fem = FEMModel(mesh=mesh,
                   material=Material(E=spec.youngs, nu=0.3, rho=spec.density),
                   fixed_nodes=corner_column_nodes(mesh),
                   alpha0=2.0, alpha1=1e-5)      # the X3 slab damping
    return FEMBody(name="support", fem=fem,
                   origin=np.array([0.0, spec.top - 0.5 * spec.thickness, 0.0]),
                   h_fine=h_fine)


def gt_sim_from_handle(handle, spec: SupportSpec, *,
                       h_fine: float = 5e-5,
                       body_youngs: float = 1.0e6,
                       resolution: int = 3) -> MultiFEMSim:
    """Mirror a native scene handle into an all-FEM `MultiFEMSim`."""
    sim = MultiFEMSim(h_fine=h_fine, floor_y=-2.0)   # safety floor only
    sim.add_body(build_support_body(spec, h_fine))
    sol = handle.world._solver
    P = sol.positions()
    for b in handle.bodies:
        desc = handle.world._descs[b.dcr_idx]
        pos = np.asarray(P[int(desc.avbd_body.index)], dtype=np.float64)
        half = _oriented_half(b.half_extents, b.orientation_wxyz)
        mass = float(desc.dcr_body.mass)
        vol = 8.0 * half[0] * half[1] * half[2]
        mat = Material(E=body_youngs, nu=0.3,
                       rho=max(1.0, mass / max(vol, 1e-12)))
        sim.add_body(make_box_fem_body(
            b.name, half, pos, mat, resolution=resolution,
            h_fine=h_fine, alpha0=0.0, alpha1=1e-5))
    return sim


def run_scene_gt(scene: str, handle, impactor_name: str, *,
                 h_fine: float = 5e-5, t_settle: float = 0.4,
                 t_run: float = 1.2, record_every: int = 200,
                 body_youngs: float = 1.0e6,
                 out_dir: Path | None = None) -> dict:
    """Two-phase all-FEM GT run for one scene; writes CSV + manifest and
    returns the recording dict (see MultiFEMSim.run)."""
    spec = SUPPORTS[scene]
    sim = gt_sim_from_handle(handle, spec, h_fine=h_fine,
                             body_youngs=body_youngs)
    support = sim.body("support")
    # support-mid deflection probe (the X3 mid-span u_y signal)
    verts = support.fem.mesh.vertices[support.top_verts]
    mid_idx = int(np.argmin(verts[:, 0] ** 2 + verts[:, 2] ** 2))
    probes = {"support_mid_uy": lambda s: float(
        s.body("support").top_uy()[mid_idx])}

    imp = sim.body(impactor_name)
    com0 = imp.com()
    imp.translate((100.0, 0.0, 0.0))            # park (X3 settle phase)
    sim.run(t_settle, record_every=record_every)
    # Release = restore the EXACT pre-park state. The parked body free-falls
    # during settle (there is no support at x+100), so translating back by
    # -100 alone would release it at the wrong height (or inside the slab)
    # with accumulated velocity — restore the full COM and rest velocity.
    imp.translate(tuple(com0 - imp.com()))
    imp.set_velocity((0.0, 0.0, 0.0))
    rec = sim.run(t_run, record_every=record_every, probes=probes)

    out_dir = Path(out_dir) if out_dir is not None else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    _dump_csv(out_dir / f"{scene}_gt.csv", sim, rec)
    manifest = dict(
        scene=scene, h_fine=h_fine, t_settle=t_settle, t_run=t_run,
        body_youngs=body_youngs, k_penalty=sim.k_penalty,
        penalty_fc=sim.penalty_fc, contact_zeta=sim.contact_zeta,
        support=vars(spec) | {"resolution": _slab_resolution(spec)},
        bodies={b.name: dict(mass=b.total_mass,
                             n_nodes=b.fem.mesh.num_vertices)
                for b in sim.bodies},
        impactor=impactor_name,
        signal="support_mid_uy + top_uy fields (plan §6.1); ledger averaged",
    )
    (out_dir / f"{scene}_gt.json").write_text(json.dumps(manifest, indent=2))
    return rec


def _dump_csv(path: Path, sim: MultiFEMSim, rec: dict) -> None:
    ledger_keys = sorted({k for frame in rec["ledger"] for k in frame})
    cols = (["t"] + [f"com_y:{b.name}" for b in sim.bodies]
            + [f"E_el:{b.name}" for b in sim.bodies]
            + [f"F:{a}->{b}" for a, b in ledger_keys]
            + (["support_mid_uy"] if rec["probes"].get("support_mid_uy")
               else []))
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for i, t in enumerate(rec["times"]):
            row = [f"{t:.6f}"]
            row += [f"{rec['com_y'][b.name][i]:.9f}" for b in sim.bodies]
            row += [f"{rec['elastic_E'][b.name][i]:.6e}" for b in sim.bodies]
            row += [f"{rec['ledger'][i].get(k, 0.0):.6f}"
                    for k in ledger_keys]
            if rec["probes"].get("support_mid_uy"):
                row.append(f"{rec['probes']['support_mid_uy'][i]:.9e}")
            w.writerow(row)
