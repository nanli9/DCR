#!/usr/bin/env python3
"""Reduced-modal demo scenes driven by the NEW velocity-band impulse port.

Same four scenes and the same knobs as `run_reduced_scene_viser.py` — but the
resting bodies react to the modal ring through the **velocity-band passive
impulse** (`dcr/dcr/impulse_port.py`, proposal §3.2, validated at V0), not the
position anchor. This is the "just this new method" test rig.

Substrate: XPBD with the coupler's NUMPY hooks (so the per-corner caches and the
ring velocity `q̇_d` are host-resident for the per-step band). XPBD's `q_s` is the
FAITHFUL sub-micron static sag, so with the band OFF the bodies sit still (the
honest baseline); with it ON they hop/jostle on the ring and settle — a passive,
energy-bounded (§15) exchange, not the position-glue ratchet.

    uv run python scripts/run_impulse_port_scene_viser.py --scene shelf
    # open http://localhost:8192 ; toggle "enable body↔ring impulse"

NOTE: runs the coupler on the host numpy path (device-resident GPU coupler does
not expose q̇_d / caches to the host), so it is slower than the AVBD demo — watch
in slow motion (lower "speed"). Folding the band into the device substep loop is
the V2 follow-up.
"""
from __future__ import annotations

import argparse
import time

from scripts.run_reduced_scene_viser import (
    ReducedSceneViewer, SCENES, _MATERIAL, main as _reduced_main,
)
from dcr.dcr.impulse_port import apply_velocity_band, apply_contact_friction


class ImpulsePortSceneViewer(ReducedSceneViewer):
    """Reduced-scene viewer + per-step velocity-band impulse port on XPBD."""

    def __init__(self, args):
        self._band_last = None          # last VelocityBandStats (for readout)
        super().__init__(args)

    # Force the host caches the band needs — on EITHER solver. The velocity
    # band (apply_velocity_band) is solver-agnostic; both the XPBD and AVBD
    # couplers expose the same _row_*_by_body caches + rs.qdot_d, but only the
    # numpy hooks (device_resident=False) populate them host-side per step.
    def _build_world(self):
        super()._build_world()
        self.coupler.device_resident = False
        if self._solver_name == "xpbd":
            # Faithful baseline: bodies ride only the static sag (now ~1mm
            # after the contact_stiffness fix — see reduced_coupled_xpbd.py).
            # q_d stays render-only so the visible reaction is the band alone.
            self.coupler.anchor_includes_q_d = False

    # Extra GUI: the band toggle, η, and its diagnostics.
    def _init_gui(self):
        super()._init_gui()
        g = self.server.gui
        with g.add_folder("Impulse port (NEW method)"):
            self.gui_band_on = g.add_checkbox(
                "enable body↔ring impulse", initial_value=True,
                hint="ON: resting bodies feel the ring through a passive "
                     "velocity impulse (proposal §3.2). OFF: faithful baseline "
                     "(bodies ride only the sub-micron static sag → look rigid).")
            self.gui_band_eta = g.add_slider(
                "eta (η) — §15 transfer", 0.0, 1.0, 0.05, 1.0,
                hint="Ships at 1.0 (governor is a safety clamp, not a dial). "
                     "<1 throttles injection (clamp count rises). The reservoir-"
                     "exact governor (V1) keeps the per-prefix §15 bound exact at "
                     "ANY η — watch 'reservoir R' stay ≥ 0.")
            self.gui_fric_on = g.add_checkbox(
                "contact friction (Coulomb)", initial_value=True,
                hint="ON: dynamic Coulomb friction at the shelf-contact corners "
                     "(reuses the solver's μ; no new knob) — kills the "
                     "frictionless slide AND the band-injected yaw spin. OFF: "
                     "the normal-only anchor lets resting bodies slide/spin.")
            self.gui_band_imp = g.add_text("impulses / step", initial_value="0")
            self.gui_band_clamp = g.add_text("governor clamps", initial_value="0")
            self.gui_band_res = g.add_text("reservoir R (≥0)", initial_value="0")
            self.gui_band_inv = g.add_text("§15 margin / step", initial_value="0")
            self.gui_band_lam = g.add_text("max impulse λ", initial_value="0")

    # Copy of the base loop with the velocity-band pass injected post-step.
    def _loop(self):
        last = time.perf_counter()
        last_tick = last
        fps_ema = 0.0
        sps_ema = 0.0
        accum = 0.0
        while not self._stop.is_set():
            now = time.perf_counter()
            dt = now - last
            last = now
            if self.gui_pause.value:
                time.sleep(1.0 / 60.0)
                continue
            accum += dt * float(self.gui_speed.value)
            n = 0
            t_step = 0.0
            while accum >= self.h and n < 4:
                t0 = time.perf_counter()
                with self._world_lock:
                    self.world.step()
                    self._apply_band()
                t_step = (time.perf_counter() - t0) * 1e3
                accum -= self.h
                n += 1
            tnow = time.perf_counter()
            d_tick = tnow - last_tick
            last_tick = tnow
            if d_tick > 1e-6:
                a = 0.12
                inst_fps = 1.0 / d_tick
                inst_sps = n / d_tick
                fps_ema = inst_fps if fps_ema == 0 else (1 - a) * fps_ema + a * inst_fps
                sps_ema = inst_sps if sps_ema == 0 else (1 - a) * sps_ema + a * inst_sps
            self._render_tick(t_step, fps_ema, sps_ema)
            spare = 1.0 / self._FPS_CAP - (time.perf_counter() - now)
            if spare > 0:
                time.sleep(spare)

    def _apply_band(self):
        """Velocity-band impulse port (called inside the world lock, post-step).

        Solver-agnostic: runs on BOTH XPBD (world.solver) and AVBD
        (world._solver). The band reads only q̇_d + the per-corner caches, so
        the SAME code path drives the body↔ring reaction on either backend."""
        solver = getattr(self.world, "solver", None)
        if solver is None:
            solver = getattr(self.world, "_solver", None)   # AVBD world
        if solver is None:
            return
        if bool(self.gui_band_on.value):
            self._band_last = apply_velocity_band(
                self.coupler, solver, eta=float(self.gui_band_eta.value))
        else:
            self._band_last = None
        # Friction is a STANDALONE pass: runs band-on AND band-off (band-off
        # also drifts). Applied after the band so it damps the band's kick.
        if bool(self.gui_fric_on.value):
            apply_contact_friction(self.coupler, solver, h=self.h)

    def _render_tick(self, step_ms, fps=0.0, sps=0.0):
        super()._render_tick(step_ms, fps, sps)
        st = self._band_last
        try:
            if st is None:
                self.gui_band_imp.value = "—"
            else:
                self.gui_band_imp.value = str(st.n_impulses)
                self.gui_band_clamp.value = str(st.clamp_activations)
                self.gui_band_res.value = f"{st.reservoir:.3e}"
                self.gui_band_inv.value = f"{st.invariant_margin_min:.2e}"
                self.gui_band_lam.value = f"{st.max_lambda:.3e}"
        except RuntimeError:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", default="shelf", choices=tuple(SCENES.keys()))
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda:0"],
                    help="cpu (default) or cuda:0; either runs the coupler on "
                         "the host numpy path so the band has q̇_d + caches.")
    ap.add_argument("--port", type=int, default=8192)
    ap.add_argument("--h", type=float, default=1.0 / 120.0)
    ap.add_argument("--iters", type=int, default=None)
    ap.add_argument("--substeps", type=int, default=None)
    ap.add_argument("--material", default=None, choices=tuple(_MATERIAL.keys()))
    ap.add_argument("--thickness", type=float, default=None)
    ap.add_argument("--impactor-mass", type=float, default=None, dest="impactor_mass")
    ap.add_argument("--drop-height", type=float, default=None, dest="drop_height")
    ap.add_argument("--impactor-v0", type=float, default=None, dest="impactor_v0")
    ap.add_argument("--impedance", type=float, default=1.0)
    ap.add_argument("--damping", type=float, default=1.0)
    ap.add_argument("--exaggerate", type=float, default=None)
    ap.add_argument("--render-thickness", type=float, default=0.02)
    ap.add_argument("--solver", default="xpbd", choices=("xpbd", "avbd"),
                    help="backend; the velocity band runs on BOTH. xpbd "
                         "(default) has the now-faithful + gentle static sag; "
                         "avbd is faithful at rest but its impact transient "
                         "over-drives q_s (book-launch — a position-band issue, "
                         "see docs §3.3). Switchable at runtime via the dropdown.")
    args = ap.parse_args(argv)

    sp = SCENES[args.scene]
    if args.iters is None: args.iters = sp.iters
    if args.substeps is None: args.substeps = sp.substeps
    if args.material is None: args.material = sp.material
    if args.thickness is None: args.thickness = sp.thickness
    if args.impactor_mass is None: args.impactor_mass = sp.impactor_mass
    if args.drop_height is None: args.drop_height = sp.drop_height
    if args.impactor_v0 is None: args.impactor_v0 = sp.impactor_v0
    if args.exaggerate is None: args.exaggerate = sp.exaggerate

    viewer = ImpulsePortSceneViewer(args)
    print(f"\n  {viewer.handle.name}  (velocity-band impulse port, "
          f"{args.solver.upper()}/{args.device})")
    print(f"  bodies={len(viewer.handle.bodies)}  modes r={viewer.rs.r}")
    print(f"  viser: http://localhost:{args.port}  — toggle 'enable body↔ring impulse'\n")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
