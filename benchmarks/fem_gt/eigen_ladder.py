"""Operator-level convergence ladder for the scene SUPPORTS (no dynamics).

    python -m benchmarks.fem_gt.eigen_ladder [--scene all] [--max-dof 240000]

Why this exists: the §3 dynamic acceptance metrics (peak transient mid-span
u_y, dominant ring frequency of the full multi-body run) turned out to be
non-convergent by construction — the per-node contact pin softens as nodes
get lighter with refinement (mesh-coupled excitation) and the multi-body
trajectories diverge between rungs (different contact events per rung). This
script isolates the FEM OPERATOR instead: per rung, the corner-fixed
support's lowest eigenfrequencies (generalized eigsh on the reduced K, M —
shift-invert at sigma=0) and the static self-weight mid-span sag
(K u = f_g). Both are contact-free and deterministic, so the <2 % criterion
is meaningful. Rungs 3-4 are eigen-only extensions of the §3 ladder (no
dynamics run at those densities).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse.linalg as spla

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.fem_gt.common import SUPPORTS, SupportSpec  # noqa: E402
from dcr.fem.fem_model import FEMModel                      # noqa: E402
from dcr.fem.material import Material                       # noqa: E402
from dcr.fem.multibody_gt import corner_column_nodes        # noqa: E402
from dcr.geom.tet_mesh import make_slab_tet_mesh            # noqa: E402

# §3 ladder (rungs 0-2 = REFINE_RULES support rules) + eigen-only extensions.
LADDER = {
    0: (10.0, 2), 1: (20.0, 3), 2: (30.0, 4),
    3: (40.0, 5), 4: (50.0, 6),
}
TOL = 0.02


def _resolution(spec: SupportSpec, rung: int) -> tuple[int, int, int]:
    per_m, thick = LADDER[rung]
    return (max(6, int(round(per_m * spec.length))),
            max(4, int(round(per_m * spec.width))), thick)


def _support_metrics(spec: SupportSpec, rung: int, k: int = 3):
    """(n_nodes, f_1..f_k in Hz, static self-weight mid-span sag in m)."""
    nx, ny, nz = _resolution(spec, rung)
    mesh = make_slab_tet_mesh(length=spec.length, width=spec.width,
                              height=spec.thickness, nx=nx, ny=ny, nz=nz)
    fem = FEMModel(mesh=mesh,
                   material=Material(E=spec.youngs, nu=0.3, rho=spec.density),
                   fixed_nodes=corner_column_nodes(mesh))
    lam, _ = spla.eigsh(fem.K, k=k, M=fem.M, sigma=0, which="LM")
    freqs = np.sqrt(np.abs(np.sort(lam))) / (2.0 * np.pi)
    u = fem.static_solve(fem.gravity_load()).reshape(-1, 3)
    v = mesh.vertices
    top = np.where(np.abs(v[:, 1] - v[:, 1].max()) < 1e-9)[0]
    mid = top[int(np.argmin(v[top, 0] ** 2 + v[top, 2] ** 2))]
    return mesh.num_vertices, freqs, float(u[mid, 1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scene", default="all",
                    choices=tuple(SUPPORTS) + ("all",))
    ap.add_argument("--max-dof", type=int, default=240_000,
                    help="skip rungs whose free-DOF count would exceed this")
    args = ap.parse_args()
    scenes = tuple(SUPPORTS) if args.scene == "all" else (args.scene,)

    hdr = (f"{'scene':<8}{'rung':<6}{'mesh':<12}{'nodes':>8}"
           f"{'f1 Hz':>10}{'d%':>7}{'f2 Hz':>10}{'f3 Hz':>10}"
           f"{'sag mm':>10}{'d%':>7}{'s':>6}  verdict")
    print(hdr)
    print("-" * len(hdr))
    for scene in scenes:
        spec = SUPPORTS[scene]
        prev = None
        converged = None
        for rung in sorted(LADDER):
            nx, ny, nz = _resolution(spec, rung)
            n_dof = 3 * (nx + 1) * (ny + 1) * (nz + 1)
            if n_dof > args.max_dof:
                print(f"{scene:<8}R{rung:<5}"
                      f"{'x'.join(map(str, (nx, ny, nz))):<12}"
                      f"{'—':>8}  skipped ({n_dof} DOF > --max-dof)")
                continue
            t0 = time.perf_counter()
            nodes, freqs, sag = _support_metrics(spec, rung)
            wall = time.perf_counter() - t0
            if prev is None:
                d_f1 = d_sag = None
                verdict = ""
            else:
                d_f1 = abs(freqs[0] - prev[0]) / prev[0] * 100.0
                d_sag = abs(sag - prev[1]) / max(abs(prev[1]), 1e-30) * 100.0
                ok = d_f1 < TOL * 100 and d_sag < TOL * 100
                verdict = "CONVERGED" if ok else "not yet"
                if ok and converged is None:
                    converged = rung
            print(f"{scene:<8}R{rung:<5}"
                  f"{'x'.join(map(str, (nx, ny, nz))):<12}{nodes:>8}"
                  f"{freqs[0]:>10.2f}"
                  f"{'' if d_f1 is None else f'{d_f1:.1f}':>7}"
                  f"{freqs[1]:>10.2f}{freqs[2]:>10.2f}"
                  f"{sag * 1e3:>10.4f}"
                  f"{'' if d_sag is None else f'{d_sag:.1f}':>7}"
                  f"{wall:>6.0f}  {verdict}", flush=True)
            prev = (freqs[0], sag)
        if converged is not None:
            print(f"{'':8}-> {scene}: operator converged at R{converged}")
        print()


if __name__ == "__main__":
    main()
