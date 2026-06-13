#!/usr/bin/env python3
"""Viser scene: a STACK of cubes on a FEM-modal slab, ABD vs FEM side by side.

    LEFT  — stack of ABD affine cubes      RIGHT — stack of FEM-modal cubes

Both stacks rest on identical supported FEM-modal slabs and are stepped in
lockstep by the N-body monolithic implicit step (dcr/twobody/multibody.py). Drop
the stack, watch the impact energy ring through every cube into the slab and back
and the whole tower settle to its static sag. Per-body energy + the static-
equilibrium residual are shown live (residual → 0 ⇒ true static rest).

    uv run python scripts/run_stacked_cubes_viser.py --n-cubes 3
    # open http://localhost:8196

See docs/two_way_modal_coupling_impl_sketch.md.
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.twobody.multibody import build_stack

_X_OFFSET = 1.4
_CUBE_COLORS = [(0.85, 0.45, 0.30), (0.90, 0.65, 0.25), (0.80, 0.35, 0.45),
                (0.45, 0.70, 0.40), (0.40, 0.55, 0.80)]


class _Column:
    def __init__(self, kind: str, n_cubes: int, params: dict, x0: float):
        self.kind = kind
        self.n_cubes = n_cubes
        self.params = params
        self.x0 = x0
        self.rebuild()

    def rebuild(self) -> None:
        self.sys = build_stack(self.kind, self.n_cubes, **self.params)
        self.state = self.sys.initial_state()
        self.e = self.sys.energy_breakdown(self.state)

    def step(self, h: float) -> None:
        self.state = self.sys.step(self.state, h)
        self.e = self.sys.energy_breakdown(self.state)

    def cube_mesh(self, ci: int, exa: float):
        body = self.sys.bodies[1 + ci]
        z = self.sys.body_z(self.state, 1 + ci)
        if self.kind == "abd":
            v = body.deformed_nodes(z, exaggerate=exa)
            f = body.surf_faces            # type: ignore[attr-defined]
        else:
            v = body.deformed_surface(z, exaggerate=exa)
            f = body.surf_faces
        v = v.copy(); v[:, 0] += self.x0
        return v.astype(np.float32), np.asarray(f, dtype=np.uint32)

    def slab_mesh(self, exa: float):
        s = self.sys.bodies[0]
        v = s.deformed_surface(self.sys.body_z(self.state, 0), exaggerate=exa).copy()
        v[:, 0] += self.x0
        return v.astype(np.float32), np.asarray(s.surf_faces, dtype=np.uint32)


class StackViewer:
    def __init__(self, args):
        import viser
        self.args = args
        self._lock = threading.Lock()
        self._h = args.h
        self._params = dict(slab_E=args.slab_E, cube_E=args.cube_E,
                            kappa_v=args.kappa_v, damping=args.damping,
                            k_c=args.k_c, gap=args.gap)
        self.left = _Column("abd", args.n_cubes, dict(self._params), 0.0)
        self.right = _Column("fem", args.n_cubes, dict(self._params), _X_OFFSET)
        self._t = 0.0
        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._init_gui()
        self._init_scene()
        threading.Thread(target=self._loop, daemon=True).start()

    def _init_gui(self) -> None:
        s = self.server
        s.gui.add_markdown(
            f"## Stack of {self.args.n_cubes}: ABD (left) vs FEM-modal (right)\n"
            "on a supported FEM-modal slab. N-body monolithic implicit step.")
        self._play = s.gui.add_checkbox("play", initial_value=True)
        self._reset = s.gui.add_button("reset")
        self._exa_cube = s.gui.add_slider("cube deform exaggerate", min=1.0,
                                          max=3000.0, step=10.0, initial_value=300.0)
        self._exa_slab = s.gui.add_slider("slab deform exaggerate", min=1.0,
                                          max=400.0, step=5.0, initial_value=40.0)
        self._damp = s.gui.add_slider("damping scale", min=0.05, max=5.0,
                                      step=0.05, initial_value=self._params["damping"])
        self._readout = s.gui.add_markdown("")
        self._reset.on_click(lambda _: self._rebuild())
        self._damp.on_update(lambda _: self._rebuild())

    def _rebuild(self) -> None:
        with self._lock:
            self._params["damping"] = self._damp.value
            self.left.params = dict(self._params)
            self.right.params = dict(self._params)
            self.left.rebuild(); self.right.rebuild()
            self._t = 0.0
        self._update_scene()

    def _init_scene(self) -> None:
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass
        g = self.server.scene.add_grid("grid", width=4.0, height=2.0, plane="xz")
        g.position = (0.7, 0.0, 0.0)
        self._update_scene()

    def _update_scene(self) -> None:
        exa_c = float(self._exa_cube.value)
        exa_s = float(self._exa_slab.value)
        for col, label in ((self.left, "abd"), (self.right, "fem")):
            sv, sf = col.slab_mesh(exa_s)
            self.server.scene.add_mesh_simple(
                f"/{label}/slab", sv, sf, color=(0.55, 0.50, 0.42),
                flat_shading=False, opacity=0.9)
            for ci in range(col.n_cubes):
                cv, cf = col.cube_mesh(ci, exa_c)
                self.server.scene.add_mesh_simple(
                    f"/{label}/cube{ci}", cv, cf,
                    color=_CUBE_COLORS[ci % len(_CUBE_COLORS)], flat_shading=True)
        self._update_readout()

    def _update_readout(self) -> None:
        def fmt(col):
            e = col.e
            res = col.sys.static_residual(col.state)
            cube_ke = sum(e[f"KE_body{b}"] for b in range(1, col.n_cubes + 1))
            return (f"cube ΣKE={cube_ke:.3g}  slab KE={e['KE_body0']:.3g}  "
                    f"slab elastic={e['PEel_body0']:.3g}  **total={e['total']:.4g}**  "
                    f"resid={res:.2g}  pen={e['max_penetration']*1e3:.2f}mm")
        self._readout.content = (f"**t = {self._t:.3f}s**\n\n"
                                 f"ABD : {fmt(self.left)}\n\nFEM : {fmt(self.right)}")

    def _loop(self) -> None:
        dt = 1.0 / 60.0
        while True:
            t0 = time.time()
            if self._play.value:
                with self._lock:
                    for _ in range(self.args.substeps):
                        self.left.step(self._h); self.right.step(self._h)
                        self._t += self._h
                self._update_scene()
            time.sleep(max(0.0, dt - (time.time() - t0)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8196)
    ap.add_argument("--n-cubes", dest="n_cubes", type=int, default=3)
    ap.add_argument("--h", type=float, default=5.0e-4)
    ap.add_argument("--substeps", type=int, default=8)
    ap.add_argument("--slab-E", dest="slab_E", type=float, default=5.0e7)
    ap.add_argument("--cube-E", dest="cube_E", type=float, default=5.0e6)
    ap.add_argument("--kappa-v", dest="kappa_v", type=float, default=2.0e3)
    ap.add_argument("--damping", type=float, default=0.6)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e5)
    ap.add_argument("--gap", type=float, default=0.02)
    args = ap.parse_args()
    StackViewer(args)
    print(f"viser up at http://localhost:{args.port}  (Ctrl-C to quit)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
