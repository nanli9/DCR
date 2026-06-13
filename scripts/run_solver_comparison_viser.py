#!/usr/bin/env python3
"""Viser: GT vs AVBD vs XPBD on the dynamic modal contact constraint, in lockstep.

Three copies of the SAME side-by-side scene (resting bystander cubes + a dropped
impactor on a FEM-modal slab) are stepped together by three solvers of the
unified-dynamic-constraint potential (`two_band_coupling.html`, Approach B):

  * GT   (grey,  z = 0.0) — `MultiBodySystem`: dense Newton + penalty contact.
  * AVBD (orange,z = 0.8) — augmented-Lagrangian, fixed iteration budget.
  * XPBD (green, z = 1.6) — compliant constraints, Gauss–Seidel.

Watch the impactor ring the slab and the ring kick the bystander cubes — the same
two-way loop in all three, with no velocity band and no energy governor. The HUD
shows per-row slab modal energy, cube KE and total energy live.

    uv run python scripts/run_solver_comparison_viser.py     # open http://localhost:8198
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.twobody.multibody import build_side_by_side
from dcr.twobody.position_based import AVBDDynamicSystem, XPBDDynamicSystem

_REST = (0.45, 0.60, 0.78)
_IMP = (0.88, 0.28, 0.24)
_SLAB = {"GT": (0.55, 0.50, 0.42), "AVBD": (0.62, 0.45, 0.28),
         "XPBD": (0.30, 0.52, 0.40)}
_ZOFF = {"GT": 0.0, "AVBD": 0.85, "XPBD": 1.70}


class ComparisonViewer:
    def __init__(self, args):
        import viser
        self.args = args
        self._lock = threading.Lock()
        self._h = args.h
        self._build()
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._init_gui()
        self._init_scene()
        threading.Thread(target=self._loop, daemon=True).start()

    def _build(self):
        p = dict(n_rest=self.args.n_rest, impactor_drop=self.args.impactor_drop,
                 impactor_rho=self.args.impactor_rho, damping=self.args.damping,
                 k_c=self.args.k_c)
        base, self.info = build_side_by_side("fem", **p)
        self.solvers = {
            "GT": base,
            "AVBD": AVBDDynamicSystem(base, n_outer=6, n_inner=3),
            "XPBD": XPBDDynamicSystem(base, n_iters=25),
        }
        self.states = {k: s.initial_state() for k, s in self.solvers.items()}
        self.energies = {k: s.energy_breakdown(self.states[k])
                         for k, s in self.solvers.items()}
        self._t = 0.0

    def _body_mesh(self, sv, st, bi, exa_s, exa_c):
        b = sv.bodies[bi]
        z = sv.body_z(st, bi)
        if bi == 0:
            return (b.deformed_surface(z, exaggerate=exa_s).astype(np.float32),
                    np.asarray(b.surf_faces, dtype=np.uint32))
        return (b.deformed_surface(z, exaggerate=exa_c).astype(np.float32),
                np.asarray(b.surf_faces, dtype=np.uint32))

    def _init_gui(self):
        s = self.server
        s.gui.add_markdown(
            "## Dynamic modal contact constraint\n"
            "GT (grey) · AVBD (orange) · XPBD (green) — same scene, lockstep.")
        self._play = s.gui.add_checkbox("play", initial_value=True)
        self._reset = s.gui.add_button("re-drop impactor")
        self._exa_c = s.gui.add_slider("cube deform exaggerate", min=1.0,
                                       max=3000.0, step=10.0, initial_value=300.0)
        self._exa_s = s.gui.add_slider("slab deform exaggerate", min=1.0,
                                       max=400.0, step=5.0, initial_value=40.0)
        self._readout = s.gui.add_markdown("")
        self._reset.on_click(lambda _: self._rebuild())

    def _rebuild(self):
        with self._lock:
            self._build()
        self._update_scene()

    def _init_scene(self):
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass
        self.server.scene.add_grid("grid", width=2.0, height=2.4, plane="xz")
        self._update_scene()

    def _update_scene(self):
        exa_c, exa_s = float(self._exa_c.value), float(self._exa_s.value)
        imp = self.info["impactor_body"]
        for name, sv in self.solvers.items():
            st = self.states[name]
            dz = _ZOFF[name]
            svv, sf = self._body_mesh(sv, st, 0, exa_s, exa_c)
            svv = svv.copy(); svv[:, 2] += dz
            self.server.scene.add_mesh_simple(
                f"/{name}/slab", svv, sf, color=_SLAB[name],
                flat_shading=False, opacity=0.9)
            for bi in range(1, len(sv.bodies)):
                cv, cf = self._body_mesh(sv, st, bi, exa_s, exa_c)
                cv = cv.copy(); cv[:, 2] += dz
                color = _IMP if bi == imp else _REST
                self.server.scene.add_mesh_simple(
                    f"/{name}/cube{bi}", cv, cf, color=color, flat_shading=True)
        self._update_readout()

    def _update_readout(self):
        lines = [f"**t = {self._t:.3f}s**", ""]
        for name in self.solvers:
            e = self.energies[name]
            nb = len(self.solvers[name].bodies)
            modal = e["KE_body0"] + e["PEel_body0"]
            ke_c = sum(e[f"KE_body{i}"] for i in range(1, nb))
            lines.append(f"**{name}** modal={modal:.3g}  cubeKE={ke_c:.3g}  "
                         f"total={e['total']:.4g}  pen={e['max_penetration']*1e3:.2f}mm")
        self._readout.content = "\n\n".join(lines)

    def _loop(self):
        dt = 1.0 / 60.0
        while True:
            t0 = time.time()
            if self._play.value:
                with self._lock:
                    for _ in range(self.args.substeps):
                        for name, sv in self.solvers.items():
                            self.states[name] = sv.step(self.states[name], self._h)
                        self._t += self._h
                    for name, sv in self.solvers.items():
                        self.energies[name] = sv.energy_breakdown(self.states[name])
                self._update_scene()
            time.sleep(max(0.0, dt - (time.time() - t0)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8198)
    ap.add_argument("--n-rest", dest="n_rest", type=int, default=3)
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--substeps", type=int, default=6)
    ap.add_argument("--impactor-drop", dest="impactor_drop", type=float, default=0.35)
    ap.add_argument("--impactor-rho", dest="impactor_rho", type=float, default=2500.0)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--k-c", dest="k_c", type=float, default=4.0e5)
    args = ap.parse_args()
    ComparisonViewer(args)
    print(f"viser up at http://localhost:{args.port}  (Ctrl-C to quit)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
