#!/usr/bin/env python3
"""Viser: the TRUCK-BED road impact — heavy box dropped on a loaded bed.

A flexible bed slab (the FEM-modal support) carries a mixed cargo load — a light
crate, a 3-cube lumber stack, a heavy crate, and a 2-crate stack — and a heavy,
fast box is dropped onto BARE BED between them (box↔bed contact only — it never
touches the cargo). The box rings the bed, and the dynamic modal contact
constraint (Approach B) carries that ring back into every resting pile, so the
whole load ROCKS in a staggered wave. Two-way, no velocity band.

The HUD shows each pile's kinetic energy live. Try `--solver split`: its
quasi-static bed can't ring, so the cargo barely reacts (one-way) and the box
keeps bouncing.

    uv run python scripts/run_truck_bed_viser.py                  # AVBD, http://localhost:8200
    uv run python scripts/run_truck_bed_viser.py --solver gt
    uv run python scripts/run_truck_bed_viser.py --solver split   # one-way contrast
    uv run python scripts/run_truck_bed_viser.py --impactor-rho 9000 --impactor-v0 8
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.twobody.multibody import build_truck_bed
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem,
                                        XPBDDynamicSystem)

# one base color per cargo pile (cycled), impactor box in red
_PILE_COLORS = [(0.55, 0.40, 0.22), (0.62, 0.42, 0.20), (0.45, 0.32, 0.18),
                (0.40, 0.58, 0.80), (0.36, 0.66, 0.62)]
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


class TruckBedViewer:
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
        self.base, self.info = build_truck_bed(
            self.args.kind,
            impactor_rho=self._imp_rho if hasattr(self, "_imp_rho")
            else self.args.impactor_rho,
            impactor_v0=self._imp_v0 if hasattr(self, "_imp_v0")
            else self.args.impactor_v0,
            k_c=self.args.k_c, damping=self.args.damping)
        # which pile each cargo body belongs to (for coloring)
        self._pile_of = {}
        for p, idxs in enumerate(self.info["pile_bodies"]):
            for bi in idxs:
                self._pile_of[bi] = p
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
            f"## Truck-bed road impact  (`{self.args.solver}`)\n"
            "Heavy box dropped on bare bed → the bed rings → the ring rocks "
            "every cargo pile. Watch the staggered wave.")
        self._play = s.gui.add_checkbox("play", initial_value=True)
        self._reset = s.gui.add_button("re-drop box")
        self._rho = s.gui.add_slider("box density [kg/m³]", min=600.0, max=14000.0,
                                     step=200.0, initial_value=self.args.impactor_rho)
        self._v0 = s.gui.add_slider("box drop speed [m/s]", min=0.0, max=15.0,
                                    step=0.5, initial_value=self.args.impactor_v0)
        self._exa_c = s.gui.add_slider("cargo deform exaggerate", min=1.0,
                                       max=3000.0, step=10.0, initial_value=200.0)
        self._exa_s = s.gui.add_slider("bed deform exaggerate", min=1.0,
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
        self.server.scene.add_grid("grid", width=2.0, height=1.2, plane="xz")
        self._update_scene()

    def _update_scene(self):
        exa_c, exa_s = float(self._exa_c.value), float(self._exa_s.value)
        imp = self.info["impactor_body"]
        sv, sf = self._body_mesh(0, exa_s, exa_c)
        self.server.scene.add_mesh_simple("/bed", sv, sf, color=(0.55, 0.50, 0.42),
                                          flat_shading=False, opacity=0.9)
        for bi in range(1, len(self.sys.bodies)):
            cv, cf = self._body_mesh(bi, exa_s, exa_c)
            color = _BOX if bi == imp else \
                _PILE_COLORS[self._pile_of.get(bi, 0) % len(_PILE_COLORS)]
            self.server.scene.add_mesh_simple(f"/cargo{bi}", cv, cf, color=color,
                                              flat_shading=True)
        self._update_readout()

    def _update_readout(self):
        e = self.e
        imp = self.info["impactor_body"]
        lines = [f"**t = {self._t:.3f}s**  total={e['total']:.4g}  "
                 f"pen={e['max_penetration']*1e3:.2f}mm", "",
                 f"**bed** modal KE = {e['KE_body0']:.3g}  "
                 f"PE = {e['PEel_body0']:.3g}", ""]
        for p, (idxs, lab) in enumerate(zip(self.info["pile_bodies"],
                                            self.info["labels"])):
            ke = sum(e[f"KE_body{bi}"] for bi in idxs)
            lines.append(f"{lab}: KE = {ke:.3g}")
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
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--solver", choices=["avbd", "gt", "xpbd", "split"],
                    default="avbd")
    ap.add_argument("--kind", choices=["fem", "abd"], default="fem")
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--substeps", type=int, default=6)
    ap.add_argument("--impactor-rho", dest="impactor_rho", type=float, default=6000.0)
    ap.add_argument("--impactor-v0", dest="impactor_v0", type=float, default=6.0)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e6)
    ap.add_argument("--damping", type=float, default=0.6)
    args = ap.parse_args()
    TruckBedViewer(args)
    print(f"viser up at http://localhost:{args.port}  (Ctrl-C to quit)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
