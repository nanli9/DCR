#!/usr/bin/env python3
"""Viser visualization of the impulse-port V0 prototype.

A single rigid body (cube) on a modal membrane. The membrane deflection is the
ring q_d (fabricated spatial mode shapes for display; the contact-point value
equals U_y·q_d, exactly the 1-DOF sim). Watch the load-bearing bet live:

  coupling = velocity  → body hops then SETTLES; ring decays (passive).
  coupling = position  → body ratchets to a STUCK offset; ring is pumped
                         (never decays) — the pathology the velocity band kills.

The sim (dcr/dcr/impulse_port_v0.py) is cheap, so the viewer RE-RUNS it on any
knob change and loops the recorded trajectory. V0 is a 1-DOF prototype — wiring
the velocity band into the real multi-body shelf scene is the later V2 step.

    uv run python scripts/run_impulse_port_v0_viser.py
    # open http://localhost:8191
"""
from __future__ import annotations

import argparse
import threading
import time

import numpy as np

from dcr.dcr.impulse_port_v0 import V0Config, run

GRID = 21          # membrane resolution per side
L = 0.12           # membrane half-width [m] → spans [-L, L]
PRE = np.array([0.5, 0.4, 0.3, 0.2])   # ring pre-excitation kick


def _membrane_faces(n: int) -> np.ndarray:
    f = []
    for i in range(n - 1):
        for j in range(n - 1):
            a, b, c, d = i*n+j, i*n+j+1, (i+1)*n+j, (i+1)*n+j+1
            f.append([a, b, d]); f.append([a, d, c])
    return np.array(f, dtype=np.uint32)


def _spatial_shapes(xs: np.ndarray, zs: np.ndarray, r: int,
                    U_y: np.ndarray) -> np.ndarray:
    """Fabricated per-mode spatial shapes φ_a(x,z) for DISPLAY, normalized so the
    membrane CENTER (the contact point) equals U_y[a]. Then Σ_a φ_a·q_d at the
    center = U_y·q_d, matching the 1-DOF sim's surface deflection exactly.
    Returns (n_verts, r)."""
    X, Z = np.meshgrid(xs / L, zs / L, indexing="ij")
    phi = np.empty((X.size, r))
    for a in range(r):
        shape = np.cos(0.5 * np.pi * (a + 1) * X) * np.cos(0.5 * np.pi * (a + 1) * Z)
        phi[:, a] = (U_y[a] * shape).ravel()   # center (X=Z=0): cos0·cos0=1 → U_y[a]
    return phi


class V0Viewer:
    def __init__(self, args):
        import viser
        self.args = args
        self._lock = threading.Lock()
        # geometry
        gx = np.linspace(-L, L, GRID)
        self._xs, self._zs = gx, gx
        X, Z = np.meshgrid(gx, gx, indexing="ij")
        self._base = np.stack([X.ravel(), np.zeros(X.size), Z.ravel()], axis=1)
        self._faces = _membrane_faces(GRID)
        U_y = np.array([0.6, 0.4, 0.25, 0.15])
        self._phi = _spatial_shapes(gx, gx, len(U_y), U_y)
        # body cube (5 cm) base verts centered at origin
        s = 0.025
        c = np.array([[x, y, z] for x in (-s, s) for y in (-s, s) for z in (-s, s)],
                     dtype=np.float32)
        self._cube_v = c
        self._cube_f = np.array([
            [0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
            [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]], dtype=np.uint32)

        self.server = viser.ViserServer(host="0.0.0.0", port=args.port)
        self._init_gui()
        self._rebuild()
        self._init_scene()
        self._frame = 0
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    # ---- sim ----------------------------------------------------------
    def _cfg(self) -> V0Config:
        excite = bool(self.gui_excite.value)
        return V0Config(
            coupling=str(self.gui_coupling.value),
            ring_vel=str(self.gui_ringvel.value),
            iters=int(self.gui_iters.value),
            substeps=int(self.gui_sub.value),
            eta=float(self.gui_eta.value),
            gravity=bool(self.gui_grav.value),
            y0=0.0 if excite else 0.05,
            qddot0=PRE.copy() if excite else None,
            N=360)

    def _rebuild(self):
        with self._lock:
            self.res = run(self._cfg())
            self._frame = 0

    # ---- scene --------------------------------------------------------
    def _init_scene(self):
        self.membrane = self.server.scene.add_mesh_simple(
            "/membrane", vertices=self._membrane_verts(0).astype(np.float32),
            faces=self._faces, color=(0.45, 0.55, 0.85), side="double",
            flat_shading=False)
        self.body = self.server.scene.add_mesh_simple(
            "/body", vertices=self._body_verts(0).astype(np.float32),
            faces=self._cube_f, color=(0.90, 0.55, 0.20), flat_shading=True)

    def _exagg(self) -> float:
        return float(self.gui_exagg.value)

    def _membrane_verts(self, k: int) -> np.ndarray:
        defl = self._phi @ self.res.qd_hist[k]      # (n_verts,) surface deflection
        v = self._base.copy()
        v[:, 1] = self._exagg() * defl
        return v

    def _body_verts(self, k: int) -> np.ndarray:
        y = self.res.y[k]
        return self._cube_v + np.array([0.0, self._exagg() * y + 0.03, 0.0])

    # ---- gui ----------------------------------------------------------
    def _init_gui(self):
        g = self.server.gui
        with g.add_folder("Coupling"):
            self.gui_coupling = g.add_dropdown(
                "coupling", ("velocity", "position"), initial_value="velocity",
                hint="velocity = passive impulse band (settles); position = "
                     "stiff glue against the ring (ratchets/pumps).")
            self.gui_ringvel = g.add_dropdown(
                "ring velocity", ("sampled", "integrated"),
                initial_value="sampled",
                hint="sampled = instantaneous q̇_d (rigorous, quieter); "
                     "integrated = substep-mean (louder here — see V0 sweep).")
            self.gui_eta = g.add_slider("eta (η)", 0.0, 1.0, 0.05, 1.0,
                                        hint="§15 transfer efficiency. Ships at "
                                             "1.0; <1 makes the governor clamp.")
        with g.add_folder("Scene"):
            self.gui_excite = g.add_checkbox(
                "pre-excite ring (else drop)", initial_value=False,
                hint="On: body rests, ring kicked (watch it react). "
                     "Off: body drops and the impact excites the ring.")
            self.gui_grav = g.add_checkbox("gravity", initial_value=True)
            self.gui_iters = g.add_slider("iterations", 1, 64, 1, 4)
            self.gui_sub = g.add_slider("substeps", 1, 96, 1, 8)
        with g.add_folder("Playback"):
            self.gui_speed = g.add_slider("speed", 0.1, 3.0, 0.1, 1.0)
            self.gui_exagg = g.add_slider("vertical exaggeration", 1.0, 50.0,
                                          1.0, 8.0)
            self.gui_restart = g.add_button("restart / apply")
        with g.add_folder("Readout"):
            self.gui_t = g.add_text("t [s]", initial_value="0.000")
            self.gui_by = g.add_text("body y [mm]", initial_value="0")
            self.gui_qd = g.add_text("ring |q_d|", initial_value="0")
            self.gui_clamp = g.add_text("governor clamps", initial_value="0")
            self.gui_inv = g.add_text("§15 margin", initial_value="0")
            self.gui_verdict = g.add_text("outcome", initial_value="")

        for w in (self.gui_coupling, self.gui_ringvel, self.gui_eta,
                  self.gui_excite, self.gui_grav, self.gui_iters, self.gui_sub):
            w.on_update(lambda _e: self._rebuild())
        self.gui_restart.on_click(lambda _e: self._rebuild())

    # ---- loop ---------------------------------------------------------
    def _loop(self):
        h = 1.0 / 120.0
        while not self._stop.is_set():
            t0 = time.perf_counter()
            with self._lock:
                k = self._frame
                N = len(self.res.y)
                try:
                    self.membrane.vertices = self._membrane_verts(k).astype(np.float32)
                    self.body.vertices = self._body_verts(k).astype(np.float32)
                except Exception:
                    pass
                r = self.res
                self.gui_t.value = f"{r.t[k]:.3f}"
                self.gui_by.value = f"{r.y[k]*1e3:.3f}"
                self.gui_qd.value = f"{r.qd_norm[k]:.3e}"
                self.gui_clamp.value = str(r.clamp_activations)
                self.gui_inv.value = f"{r.invariant_margin_min:.2e}"
                settled = r.y[-20:].std() < 1e-6 and r.qd_norm[-1] < 1e-3*max(r.qd_norm.max(),1e-30)
                self.gui_verdict.value = ("SETTLES (ring decays)" if settled
                                          else f"NOT settled (offset {r.y[-1]*1e3:.1f}mm, "
                                               f"ring {r.qd_norm[-1]:.1e})")
                self._frame = (k + 1) % N
            dt = h / max(float(self.gui_speed.value), 1e-3)
            time.sleep(max(0.0, dt - (time.perf_counter() - t0)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8191)
    args = ap.parse_args(argv)
    V0Viewer(args)
    print(f"\n  impulse-port V0 viewer  →  http://localhost:{args.port}")
    print("  toggle coupling velocity↔position to see settle vs ratchet.\n")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
