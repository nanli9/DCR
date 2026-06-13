#!/usr/bin/env python3
"""Viser comparison: ABD affine cube vs FEM-modal cube, both on a FEM-modal slab.

Two systems run in lockstep, side by side:

    LEFT  — cube = ABD affine body (12 DOF, docs/ABD.pdf)
    RIGHT — cube = FEM-modal body (translation carrier + elastic eigenmodes)

Both couple to an identical supported FEM-modal slab through the same monolithic
incremental-potential step (dcr/twobody/coupled_step.py). Drop the cube, watch
energy flow cube → slab vibration → back, and both columns ring down to the SAME
static-sag rest state (the investigation's claim, made visible).

The display exaggerates *deformation only* (rigid drop is 1:1) so the ABD
homogeneous squish and the FEM modal shapes are visible on otherwise-stiff
bodies. Energy readouts under each column show KE / elastic PE / contact PE /
total — total is monotone non-increasing (passivity).

    uv run python scripts/run_two_body_coupling_viser.py
    # open http://localhost:8195

See docs/two_way_modal_coupling_impl_sketch.md.
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.fem.material import Material
from dcr.twobody import build_abd_cube, build_fem_cube, build_fem_slab
from dcr.twobody.coupled_step import ContactPair, TwoBodySystem

_X_OFFSET = 1.4   # horizontal separation between the two columns [m]
_PAIRS = [ContactPair(i, i) for i in range(4)]


def _build_system(kind: str, *, slab_E: float, cube_E: float, kappa_v: float,
                  drop_y: float, damping: float, k_c: float) -> TwoBodySystem:
    slab = build_fem_slab(
        material=Material(E=slab_E, nu=0.3, rho=600.0),
        num_modes=16, alpha0=2.0 * damping, alpha1=1.0e-4 * damping,
    )
    if kind == "abd":
        cube = build_abd_cube(material=Material(E=cube_E, nu=0.3, rho=600.0),
                              kappa_v=kappa_v, drop_y=drop_y, alpha0=damping)
    else:
        cube = build_fem_cube(material=Material(E=cube_E, nu=0.3, rho=600.0),
                              drop_y=drop_y, alpha0=damping, alpha1=5.0e-4 * damping)
    return TwoBodySystem(cube=cube, slab=slab, pairs=_PAIRS, k_c=k_c)


class _Column:
    """One coupled system + its live state and display meshes."""

    def __init__(self, kind: str, params: dict, x0: float):
        self.kind = kind
        self.x0 = x0
        self.params = params
        self.rebuild()

    def rebuild(self) -> None:
        self.sys = _build_system(self.kind, **self.params)
        self.state = self.sys.initial_state()
        self.e = self.sys.energy(self.state)

    def step(self, h: float) -> None:
        self.state = self.sys.step(self.state, h)
        self.e = self.sys.energy(self.state)

    def cube_mesh(self, exa: float):
        c = self.sys.cube
        if self.kind == "abd":
            verts = c.deformed_nodes(self.state.zc, exaggerate=exa)
            faces = c.surf_faces  # type: ignore[attr-defined]
        else:
            verts = c.deformed_surface(self.state.zc, exaggerate=exa)
            faces = c.surf_faces
        v = verts.copy()
        v[:, 0] += self.x0
        return v.astype(np.float32), np.asarray(faces, dtype=np.uint32)

    def slab_mesh(self, exa: float):
        s = self.sys.slab
        v = s.deformed_surface(self.state.zs, exaggerate=exa).copy()
        v[:, 0] += self.x0
        return v.astype(np.float32), np.asarray(s.surf_faces, dtype=np.uint32)


class TwoBodyViewer:
    def __init__(self, args):
        import viser
        self.args = args
        self._lock = threading.Lock()
        self._h = args.h
        self._exa = args.exaggerate
        self._params = dict(
            slab_E=args.slab_E, cube_E=args.cube_E, kappa_v=args.kappa_v,
            drop_y=args.drop_y, damping=args.damping, k_c=args.k_c,
        )
        self.left = _Column("abd", dict(self._params), x0=0.0)
        self.right = _Column("fem", dict(self._params), x0=_X_OFFSET)
        self._t = 0.0

        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._init_gui()
        self._init_scene()
        threading.Thread(target=self._loop, daemon=True).start()

    # ---- GUI ----------------------------------------------------------
    def _init_gui(self) -> None:
        s = self.server
        s.gui.add_markdown(
            "## ABD cube (left)  vs  FEM-modal cube (right)\n"
            "Both on a supported FEM-modal slab. Same coupled step.")
        self._play = s.gui.add_checkbox("play", initial_value=True)
        self._reset = s.gui.add_button("reset")
        self._exa_cube = s.gui.add_slider(
            "cube deform exaggerate", min=1.0, max=3000.0, step=10.0,
            initial_value=float(self._exa))
        self._exa_slab = s.gui.add_slider(
            "slab deform exaggerate", min=1.0, max=400.0, step=5.0,
            initial_value=max(1.0, float(self._exa) / 6.0))
        self._drop = s.gui.add_slider("drop height [m]", min=0.06, max=0.4,
                                      step=0.01, initial_value=self._params["drop_y"])
        self._slabE = s.gui.add_slider("slab log10(E)", min=6.0, max=10.0,
                                       step=0.25, initial_value=np.log10(self._params["slab_E"]))
        self._cubeE = s.gui.add_slider("cube log10(E)", min=5.0, max=9.0,
                                       step=0.25, initial_value=np.log10(self._params["cube_E"]))
        self._kappa = s.gui.add_slider("ABD log10(κv)", min=1.0, max=6.0,
                                       step=0.25, initial_value=np.log10(self._params["kappa_v"]))
        self._damp = s.gui.add_slider("damping scale", min=0.05, max=5.0,
                                      step=0.05, initial_value=self._params["damping"])
        self._readout = s.gui.add_markdown("")

        self._reset.on_click(lambda _: self._rebuild())
        for w in (self._drop, self._slabE, self._cubeE, self._kappa, self._damp):
            w.on_update(lambda _: self._rebuild())

    def _rebuild(self) -> None:
        with self._lock:
            self._params.update(
                drop_y=self._drop.value, slab_E=10 ** self._slabE.value,
                cube_E=10 ** self._cubeE.value, kappa_v=10 ** self._kappa.value,
                damping=self._damp.value)
            self.left.params = dict(self._params)
            self.right.params = dict(self._params)
            self.left.rebuild()
            self.right.rebuild()
            self._t = 0.0
        self._update_scene()

    # ---- scene --------------------------------------------------------
    def _init_scene(self) -> None:
        # y-up world (gravity in -Y); ground grid in the XZ plane.
        try:
            self.server.scene.set_up_direction("+y")
        except Exception:
            pass
        grid = self.server.scene.add_grid("grid", width=4.0, height=2.0,
                                          plane="xz")
        grid.position = (0.7, 0.0, 0.0)
        self._update_scene()

    def _update_scene(self) -> None:
        exa_c = float(self._exa_cube.value)
        exa_s = float(self._exa_slab.value)
        for col, cube_color, label in (
            (self.left, (0.85, 0.45, 0.30), "abd"),
            (self.right, (0.35, 0.55, 0.85), "fem"),
        ):
            cv, cf = col.cube_mesh(exa_c)
            sv, sf = col.slab_mesh(exa_s)
            self.server.scene.add_mesh_simple(
                f"/{label}/cube", cv, cf, color=cube_color, flat_shading=True)
            self.server.scene.add_mesh_simple(
                f"/{label}/slab", sv, sf, color=(0.55, 0.50, 0.42),
                flat_shading=False, opacity=0.9)
        self._update_readout()

    def _update_readout(self) -> None:
        def fmt(col):
            e = col.e
            return (f"KE={e['KE']:.4g}  PE_el={e['PE_elastic']:.4g}  "
                    f"PE_c={e['PE_contact']:.4g}  **total={e['total']:.4g}**  "
                    f"pen={e['max_penetration']*1e3:.2f}mm")
        self._readout.content = (
            f"**t = {self._t:.3f}s**\n\n"
            f"ABD : {fmt(self.left)}\n\n"
            f"FEM : {fmt(self.right)}")

    # ---- loop ---------------------------------------------------------
    def _loop(self) -> None:
        target_dt = 1.0 / 60.0
        while True:
            t0 = time.time()
            if self._play.value:
                with self._lock:
                    # a few sub-steps per frame for a smooth, faster-than-realtime ring-down
                    for _ in range(self.args.substeps):
                        self.left.step(self._h)
                        self.right.step(self._h)
                        self._t += self._h
                self._update_scene()
            time.sleep(max(0.0, target_dt - (time.time() - t0)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8195)
    ap.add_argument("--h", type=float, default=5.0e-4, help="time step [s]")
    ap.add_argument("--substeps", type=int, default=8, help="steps per render frame")
    ap.add_argument("--exaggerate", type=float, default=300.0)
    ap.add_argument("--drop-y", dest="drop_y", type=float, default=0.16)
    ap.add_argument("--slab-E", dest="slab_E", type=float, default=5.0e7)
    ap.add_argument("--cube-E", dest="cube_E", type=float, default=5.0e6)
    ap.add_argument("--kappa-v", dest="kappa_v", type=float, default=2.0e3)
    ap.add_argument("--damping", type=float, default=0.5)
    ap.add_argument("--k-c", dest="k_c", type=float, default=1.0e5)
    args = ap.parse_args()
    TwoBodyViewer(args)
    print(f"viser up at http://localhost:{args.port}  (Ctrl-C to quit)")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
