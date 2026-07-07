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
import time
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
    "dinner": SupportSpec(2.2, 1.1, 0.04, 0.03, 1.1e9, 770.0),
    "cargo":  SupportSpec(0.8, 0.4, 0.02, 0.0, 1.0e10, 500.0),
}


# Refinement ladder (benchmark plan §3). Per rung:
#   support: (cells per metre in plan, layers through thickness)
#   bodies:  (cells on the longest axis, floor on the thin axes)
# R0 is the X3-density rule the production runs used; R1/R2 exist because
# 2 layers of CST tets lock in bending (support sag + ring biased stiff).
REFINE_RULES = {
    0: dict(support_per_m=10.0, support_thick=2, body_base=3, body_floor=2),
    1: dict(support_per_m=20.0, support_thick=3, body_base=4, body_floor=3),
    2: dict(support_per_m=30.0, support_thick=4, body_base=6, body_floor=3),
}


def _slab_resolution(spec: SupportSpec, refine: int = 0) -> tuple[int, int, int]:
    """Support slab mesh per the §3 ladder (R0 = X3-density: 10/m, 2 thick)."""
    r = REFINE_RULES[refine]
    per_m, thick = r["support_per_m"], r["support_thick"]
    return (max(6, int(round(per_m * spec.length))),
            max(4, int(round(per_m * spec.width))), thick)


def _body_resolution(half, refine: int = 0) -> tuple[int, int, int]:
    """Body box mesh per the §3 ladder: `body_base` cells on the longest axis,
    aspect-scaled with a `body_floor` floor (R0 floor 2 = the rule
    `make_box_fem_body` applies to an int resolution; R1/R2 raise the floor to
    3 so thin dims — 10 mm plates, 5 mm forks — get a bending-capable layer
    count)."""
    r = REFINE_RULES[refine]
    h = np.asarray(half, dtype=np.float64).reshape(3)
    longest = float(h.max())
    return tuple(max(r["body_floor"],
                     int(round(r["body_base"] * float(e) / longest)))
                 for e in h)


def _ring_metrics(mid_uy, dt: float) -> tuple[float, float]:
    """(peak |u_y|, dominant ring frequency in Hz) of the release-phase
    mid-span trace — the two §3 acceptance quantities. Frequency = Hann-
    windowed rFFT peak above 5 Hz (skip DC/settling drift) with parabolic
    interpolation for sub-bin accuracy (the 1.2 s window alone gives only
    ~0.8 Hz bins vs the <2 % criterion)."""
    u = np.asarray(mid_uy, dtype=np.float64)
    peak = float(np.max(np.abs(u))) if u.size else 0.0
    if u.size < 16:
        return peak, 0.0
    x = (u - u.mean()) * np.hanning(u.size)
    X = np.abs(np.fft.rfft(x))
    f = np.fft.rfftfreq(u.size, dt)
    lo = max(1, int(np.searchsorted(f, 5.0)))
    if lo >= X.size:
        return peak, 0.0
    k = lo + int(np.argmax(X[lo:]))
    if 0 < k < X.size - 1:
        a, b, c = X[k - 1], X[k], X[k + 1]
        denom = a - 2.0 * b + c
        delta = 0.5 * (a - c) / denom if abs(denom) > 1e-30 else 0.0
        return peak, float((k + delta) * (f[1] - f[0]))
    return peak, float(f[k])


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


def build_support_body(spec: SupportSpec, h_fine: float,
                       refine: int = 0) -> FEMBody:
    nx, ny, nz = _slab_resolution(spec, refine)
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
                       refine: int = 0) -> MultiFEMSim:
    """Mirror a native scene handle into an all-FEM `MultiFEMSim`."""
    sim = MultiFEMSim(h_fine=h_fine, floor_y=-2.0)   # safety floor only
    sim.add_body(build_support_body(spec, h_fine, refine))
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
            b.name, half, pos, mat,
            resolution=_body_resolution(half, refine),
            h_fine=h_fine, alpha0=0.0, alpha1=1e-5))
    return sim


def run_scene_gt(scene: str, handle, impactor_name: str, *,
                 h_fine: float = 5e-5, t_settle: float = 0.4,
                 t_run: float = 1.2, record_every: int = 50,
                 body_youngs: float = 1.0e6, refine: int = 0,
                 out_dir: Path | None = None) -> dict:
    """Two-phase all-FEM GT run for one scene; writes CSV + manifest and
    returns the recording dict (see MultiFEMSim.run).

    `record_every` default 50 (not 200): the ring-frequency metric needs the
    mid-span probe sampled well above the ~80 Hz supports ring — 50 fine
    steps at h=5e-5 is 400 Hz sampling (Nyquist 200 Hz); 200 steps (100 Hz)
    would alias it. Output files are suffixed `_r{refine}` for refine > 0 so
    the ladder rungs coexist (R0 keeps the original unsuffixed names)."""
    spec = SUPPORTS[scene]
    sim = gt_sim_from_handle(handle, spec, h_fine=h_fine,
                             body_youngs=body_youngs, refine=refine)
    support = sim.body("support")
    # support-mid deflection probe (the X3 mid-span u_y signal)
    verts = support.fem.mesh.vertices[support.top_verts]
    mid_idx = int(np.argmin(verts[:, 0] ** 2 + verts[:, 2] ** 2))
    probes = {"support_mid_uy": lambda s: float(
        s.body("support").top_uy()[mid_idx])}

    imp = sim.body(impactor_name)
    com0 = imp.com()
    imp.translate((100.0, 0.0, 0.0))            # park (X3 settle phase)
    wall0 = time.perf_counter()
    sim.run(t_settle, record_every=record_every)
    # Release = restore the EXACT pre-park state. The parked body free-falls
    # during settle (there is no support at x+100), so translating back by
    # -100 alone would release it at the wrong height (or inside the slab)
    # with accumulated velocity — restore the full COM and rest velocity.
    imp.translate(tuple(com0 - imp.com()))
    imp.set_velocity((0.0, 0.0, 0.0))
    rec = sim.run(t_run, record_every=record_every, probes=probes)
    wall = time.perf_counter() - wall0

    peak_uy, ring_hz = _ring_metrics(rec["probes"]["support_mid_uy"],
                                     record_every * h_fine)
    suffix = f"_r{refine}" if refine else ""
    out_dir = Path(out_dir) if out_dir is not None else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    _dump_csv(out_dir / f"{scene}_gt{suffix}.csv", sim, rec)
    manifest = dict(
        scene=scene, refine=refine, h_fine=h_fine, t_settle=t_settle,
        t_run=t_run, record_every=record_every,
        body_youngs=body_youngs, k_penalty=sim.k_penalty,
        penalty_fc=sim.penalty_fc, contact_zeta=sim.contact_zeta,
        support=vars(spec) | {"resolution": _slab_resolution(spec, refine)},
        bodies={b.name: dict(mass=b.total_mass,
                             n_nodes=b.fem.mesh.num_vertices)
                for b in sim.bodies},
        impactor=impactor_name, wall_s=round(wall, 1),
        peak_mid_uy=peak_uy, ring_hz=ring_hz,
        signal="support_mid_uy + top_uy fields (plan §6.1); ledger averaged",
    )
    (out_dir / f"{scene}_gt{suffix}.json").write_text(
        json.dumps(manifest, indent=2))
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
