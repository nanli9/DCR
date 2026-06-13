#!/usr/bin/env python3
"""Viser scene: cubes RESTING side-by-side on a slab + a dropped impactor.

Three (default) cubes sit at rest across a supported FEM-modal slab. A heavy
impactor is dropped onto the slab between them. The impact rings the slab, and
the ring **kicks the resting bystander cubes** — slab → cube momentum transfer
through the monolithic implicit penalty contact, with NO velocity-impulse band.
Then everything damps back to rest.

Each resting cube's kinetic energy is shown live: it sits at ~0, spikes when the
ring arrives (~2000× in the headless check), then decays. The center cube (mid-
span, where the slab's bending ring is largest) gets kicked hardest.

    uv run python scripts/run_side_by_side_viser.py            # ABD cubes
    uv run python scripts/run_side_by_side_viser.py --kind fem
    # open http://localhost:8197

See docs/two_way_modal_coupling_impl_sketch.md.
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.twobody.multibody import build_side_by_side

_REST_COLOR = (0.45, 0.60, 0.78)
_IMPACT_COLOR = (0.88, 0.28, 0.24)


class SideBySideViewer:
    def __init__(self, args):
        import viser
        self.args = args
        self._lock = threading.Lock()
        self._h = args.h
        self._params = dict(n_rest=args.n_rest, impactor_drop=args.impactor_drop,
                            impactor_rho=args.impactor_rho, damping=args.damping,
                            k_c=args.k_c, slab_E=args.slab_E, cube_E=args.cube_E,
                            kappa_v=args.kappa_v)
        self._build()
        self._t = 0.0
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._init_gui()
        self._init_scene()
        threading.Thread(target=self._loop, daemon=True).start()

    def _build(self) -> None:
        self.sys, self.info = build_side_by_side(self.args.kind, **self._params)
        self.state = self.sys.initial_state()
        self.e = self.sys.energy_breakdown(self.state)

    # ---- meshes -------------------------------------------------------
    def _body_mesh(self, bi: int, exa: float):
        b = self.sys.bodies[bi]
        z = self.sys.body_z(self.state, bi)
        if bi == 0:                                   # slab
            return b.deformed_surface(z, exaggerate=exa).astype(np.float32), \
                np.asarray(b.surf_faces, dtype=np.uint32)
        if self.args.kind == "abd":
            v = b.deformed_nodes(z, exaggerate=exa)
            f = b.surf_faces                          # type: ignore[attr-defined]
        else:
            v = b.deformed_surface(z, exaggerate=exa)
            f = b.surf_faces
        return v.astype(np.float32), np.asarray(f, dtype=np.uint32)

    # ---- GUI ----------------------------------------------------------
    def _init_gui(self) -> None:
        s = self.server
        s.gui.add_markdown(
            f"## Bystander kick ({self.args.kind.upper()} cubes)\n"
            "Heavy impactor (red) dropped on the slab; the ring kicks the resting "
            "cubes (blue). No velocity band — momentum flows through the implicit "
            "contact.")
        self._play = s.gui.add_checkbox("play", initial_value=True)
        self._reset = s.gui.add_button("re-drop impactor")
        self._exa_cube = s.gui.add_slider("cube deform exaggerate", min=1.0,
                                          max=3000.0, step=10.0, initial_value=300.0)
        self._exa_slab = s.gui.add_slider("slab deform exaggerate", min=1.0,
                                          max=400.0, step=5.0, initial_value=40.0)
        self._drop = s.gui.add_slider("impactor drop [m]", min=0.15, max=0.7,
                                      step=0.01, initial_value=self._params["impactor_drop"])
        self._rho = s.gui.add_slider("impactor density", min=600.0, max=6000.0,
                                     step=100.0, initial_value=self._params["impactor_rho"])
        self._readout = s.gui.add_markdown("")
        self._reset.on_click(lambda _: self._rebuild())
        for w in (self._drop, self._rho):
            w.on_update(lambda _: self._rebuild())

    def _rebuild(self) -> None:
        with self._lock:
            self._params["impactor_drop"] = self._drop.value
            self._params["impactor_rho"] = self._rho.value
            self._build()
            self._t = 0.0
        self._update_scene()

    # ---- scene --------------------------------------------------------
    def _init_scene(self) -> None:
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass
        g = self.server.scene.add_grid("grid", width=2.0, height=1.2, plane="xz")
        g.position = (0.0, 0.0, 0.0)
        self._update_scene()

    def _update_scene(self) -> None:
        exa_c = float(self._exa_cube.value)
        exa_s = float(self._exa_slab.value)
        sv, sf = self._body_mesh(0, exa_s)
        self.server.scene.add_mesh_simple("/slab", sv, sf, color=(0.55, 0.50, 0.42),
                                          flat_shading=False, opacity=0.9)
        imp = self.info["impactor_body"]
        for bi in range(1, len(self.sys.bodies)):
            cv, cf = self._body_mesh(bi, exa_c)
            color = _IMPACT_COLOR if bi == imp else _REST_COLOR
            self.server.scene.add_mesh_simple(f"/cube{bi}", cv, cf, color=color,
                                              flat_shading=True)
        self._update_readout()

    def _update_readout(self) -> None:
        e = self.e
        lines = [f"**t = {self._t:.3f}s**  total={e['total']:.4g}  "
                 f"slab elastic={e['PEel_body0']:.3g}  "
                 f"pen={e['max_penetration']*1e3:.2f}mm", ""]
        for k, bi in enumerate(self.info["rest_bodies"]):
            lines.append(f"rest cube {k}: KE = {e[f'KE_body{bi}']:.3g}")
        imp = self.info["impactor_body"]
        lines.append(f"impactor : KE = {e[f'KE_body{imp}']:.3g}")
        self._readout.content = "\n\n".join(lines)

    # ---- loop ---------------------------------------------------------
    def _loop(self) -> None:
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8197)
    ap.add_argument("--kind", choices=["abd", "fem"], default="abd")
    ap.add_argument("--n-rest", dest="n_rest", type=int, default=3)
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--substeps", type=int, default=8)
    ap.add_argument("--impactor-drop", dest="impactor_drop", type=float, default=0.35)
    ap.add_argument("--impactor-rho", dest="impactor_rho", type=float, default=2500.0)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--k-c", dest="k_c", type=float, default=4.0e5)
    ap.add_argument("--slab-E", dest="slab_E", type=float, default=5.0e7)
    ap.add_argument("--cube-E", dest="cube_E", type=float, default=5.0e6)
    ap.add_argument("--kappa-v", dest="kappa_v", type=float, default=2.0e3)
    args = ap.parse_args()
    SideBySideViewer(args)
    print(f"viser up at http://localhost:{args.port}  (Ctrl-C to quit)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
