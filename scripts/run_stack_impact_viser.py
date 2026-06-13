#!/usr/bin/env python3
"""Viser: a HEAVY box dropped fast onto a 3-cube STACK — watch the stack react.

A tower of `n_stack` cubes rests on the FEM-modal slab. A heavy, fast box is
dropped onto the TOP of the stack (cube↔cube contacts all the way down, so it
lands ON the tower, not through it). The impact propagates down the stack,
compresses it, and rings the slab — the dynamic modal contact constraint
(Approach B) makes the slab ring AND push back, two-way.

The HUD shows each cube's kinetic energy live, so you can watch the impact wave
travel top → bottom through the stack and the slab ring.

    uv run python scripts/run_stack_impact_viser.py                 # AVBD, http://localhost:8199
    uv run python scripts/run_stack_impact_viser.py --solver gt
    uv run python scripts/run_stack_impact_viser.py --impactor-rho 8000 --impactor-v0 8 --k-c 4e6 --h 2e-4
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.twobody.multibody import build_stack_impact
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem,
                                        XPBDDynamicSystem)

_STACK_COLORS = [(0.40, 0.58, 0.80), (0.36, 0.66, 0.62), (0.50, 0.55, 0.78),
                 (0.42, 0.60, 0.72), (0.46, 0.52, 0.74)]
_BOX = (0.86, 0.24, 0.20)


def _make_solver(name, base):
    if name == "gt":
        return base
    if name == "avbd":
        return AVBDDynamicSystem(base, n_outer=8, n_inner=4)
    if name == "xpbd":
        return XPBDDynamicSystem(base, n_iters=30)
    if name == "split":
        return SplitOneWaySystem(base)
    raise ValueError(name)


class StackImpactViewer:
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
        self.base, self.info = build_stack_impact(
            self.args.kind, n_stack=self.args.n_stack,
            impactor_rho=self._imp_rho if hasattr(self, "_imp_rho")
            else self.args.impactor_rho,
            impactor_v0=self._imp_v0 if hasattr(self, "_imp_v0")
            else self.args.impactor_v0,
            impactor_size=self.args.impactor_size, k_c=self.args.k_c,
            damping=self.args.damping)
        self.sys = _make_solver(self.args.solver, self.base)
        self.state = self.sys.initial_state()
        self.e = self.sys.energy_breakdown(self.state)
        self._t = 0.0

    def _body_mesh(self, bi, exa_s, exa_c):
        b = self.sys.bodies[bi]
        z = self.sys.body_z(self.state, bi)
        if bi == 0:
            return (b.deformed_surface(z, exaggerate=exa_s).astype(np.float32),
                    np.asarray(b.surf_faces, dtype=np.uint32))
        if self.args.kind == "abd":
            return (b.deformed_nodes(z, exaggerate=exa_c).astype(np.float32),
                    np.asarray(b.surf_faces, dtype=np.uint32))
        return (b.deformed_surface(z, exaggerate=exa_c).astype(np.float32),
                np.asarray(b.surf_faces, dtype=np.uint32))

    def _init_gui(self):
        s = self.server
        s.gui.add_markdown(
            f"## Heavy box → {self.args.n_stack}-cube stack  (`{self.args.solver}`)\n"
            "Watch the impact wave travel top→bottom and the slab ring.")
        self._play = s.gui.add_checkbox("play", initial_value=True)
        self._reset = s.gui.add_button("re-drop box")
        self._rho = s.gui.add_slider("box density [kg/m³]", min=600.0, max=12000.0,
                                     step=200.0, initial_value=self.args.impactor_rho)
        self._v0 = s.gui.add_slider("box drop speed [m/s]", min=0.0, max=15.0,
                                    step=0.5, initial_value=self.args.impactor_v0)
        self._exa_c = s.gui.add_slider("cube deform exaggerate", min=1.0,
                                       max=3000.0, step=10.0, initial_value=200.0)
        self._exa_s = s.gui.add_slider("slab deform exaggerate", min=1.0,
                                       max=400.0, step=5.0, initial_value=40.0)
        self._readout = s.gui.add_markdown("")
        self._reset.on_click(lambda _: self._rebuild())
        for w in (self._rho, self._v0):
            w.on_update(lambda _: self._rebuild())

    def _rebuild(self):
        with self._lock:
            self._imp_rho = float(self._rho.value)
            self._imp_v0 = float(self._v0.value)
            self._build()
        self._update_scene()

    def _init_scene(self):
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass
        self.server.scene.add_grid("grid", width=1.4, height=1.0, plane="xz")
        self._update_scene()

    def _update_scene(self):
        exa_c, exa_s = float(self._exa_c.value), float(self._exa_s.value)
        imp = self.info["impactor_body"]
        sv, sf = self._body_mesh(0, exa_s, exa_c)
        self.server.scene.add_mesh_simple("/slab", sv, sf, color=(0.55, 0.50, 0.42),
                                          flat_shading=False, opacity=0.9)
        for bi in range(1, len(self.sys.bodies)):
            cv, cf = self._body_mesh(bi, exa_s, exa_c)
            if bi == imp:
                color = _BOX
            else:
                color = _STACK_COLORS[(bi - 1) % len(_STACK_COLORS)]
            self.server.scene.add_mesh_simple(f"/cube{bi}", cv, cf, color=color,
                                              flat_shading=True)
        self._update_readout()

    def _update_readout(self):
        e = self.e
        imp = self.info["impactor_body"]
        lines = [f"**t = {self._t:.3f}s**  total={e['total']:.4g}  "
                 f"pen={e['max_penetration']*1e3:.2f}mm", "",
                 f"**slab** modal KE = {e['KE_body0']:.3g}  "
                 f"PE = {e['PEel_body0']:.3g}", ""]
        for k, bi in enumerate(self.info["stack_bodies"]):
            tag = "top" if bi == self.info["stack_bodies"][-1] else f"#{k}"
            lines.append(f"stack {tag}: KE = {e[f'KE_body{bi}']:.3g}")
        lines.append(f"**box**: KE = {e[f'KE_body{imp}']:.3g}")
        self._readout.content = "\n\n".join(lines)

    def _loop(self):
        dt = 1.0 / 60.0
        while True:
            t0 = time.time()
            if self._play.value:
                with self._lock:
                    for _ in range(self.args.substeps):
                        self.state = self.sys.step(self.state, self._h)
                        self._t += self._h
                    self.e = self.sys.energy_breakdown(self.state)
                self._update_scene()
            time.sleep(max(0.0, dt - (time.time() - t0)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8199)
    ap.add_argument("--solver", choices=["avbd", "gt", "xpbd", "split"],
                    default="avbd")
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--n-stack", dest="n_stack", type=int, default=3)
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--substeps", type=int, default=6)
    ap.add_argument("--impactor-rho", dest="impactor_rho", type=float, default=5000.0)
    ap.add_argument("--impactor-v0", dest="impactor_v0", type=float, default=5.0)
    ap.add_argument("--impactor-size", dest="impactor_size", type=float, default=None)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e6)
    ap.add_argument("--damping", type=float, default=0.6)
    args = ap.parse_args()
    StackImpactViewer(args)
    print(f"viser up at http://localhost:{args.port}  (Ctrl-C to quit)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
