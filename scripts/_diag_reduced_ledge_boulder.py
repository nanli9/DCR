#!/usr/bin/env python3
"""WHERE does the boulder's small vibration come from in the *reduced-coupled*
ledge viser scene?  (build_reduced_ledge → ReducedCoupledAVBDCoupler)

Both pre-existing ledge diags (`_diag_ledge.py`, `_diag_ledge_boulder_jitter.py`)
probe the STALE patch `PassiveDCRCoupler` ledge (`build_ledge_scene`). The viser
scene the user is watching uses the q_s+q_d coupled coupler, where bodies are
anchored to q_s ONLY (q_d is render-only). So re-measure on the real path.

Discriminators (all CPU = numpy reference, deterministic, viewer iters=4/sub=4):
  FULL        : scene exactly as the viewer runs it
  COUPLER_OFF : null the 3 solver hooks  → boulder on a STATIC rigid floor
                (no modal deflection feeds back into any body)
  ITERS=16    : full coupler, 4× the AVBD iterations
  ITERS=24    : full coupler, 6× iterations

If COUPLER_OFF is dead-still and FULL jitters → the vibration is the q_s
coupling feedback. If FULL jitters and ITERS=16/24 shrinks it → it is an
AVBD under-convergence (low-iteration resting) artifact, not physical ring-down.
Report boulder vy/ω jitter + q_s norm + support deflection in a LATE window.
"""
from __future__ import annotations

import numpy as np

from scenes.reduced_ledge import build_reduced_ledge


def run(label, *, iters=4, substeps=4, coupler_off=False, n=720,
        late0=480):
    handle = build_reduced_ledge(
        device="cpu", iterations=iters, avbd_substeps=substeps,
        youngs=1.0e10, density=600.0)        # match viewer "wood" material
    world = handle.world
    cp = world.reduced_coupled_coupler

    if coupler_off:
        # Null the hooks the solver holds → AVBD bodies rest on the static
        # floor; the modal support never deflects, never feeds any body.
        world._solver.substep_begin_hook = None
        world._solver.iteration_hook = None
        world._solver.substep_end_hook = None
        world._solver.hooks_device_resident = False

    b = handle.impactor_idx                  # the boulder
    pillars = handle.probe_indices
    bod = world.bodies

    vy = np.zeros(n); wy = np.zeros(n); ypos = np.zeros(n)
    qs = np.zeros(n); defl = np.zeros(n)
    pil_v = np.zeros(n)
    for k in range(n):
        world.step()
        vy[k] = float(bod[b].velocity[1])
        wy[k] = float(np.linalg.norm(bod[b].velocity[3:]))   # ang speed
        ypos[k] = float(bod[b].position[1])
        qs[k] = float(np.linalg.norm(cp.rs.q_s)) if not coupler_off else 0.0
        defl[k] = float(cp.last_max_support_deflection) if not coupler_off else 0.0
        if pillars:
            pil_v[k] = max(float(np.linalg.norm(bod[p].velocity[:3]))
                           for p in pillars)

    L = slice(late0, n)
    vL = vy[L]
    flips = int(np.sum(np.diff(np.sign(vL[np.abs(vL) > 1e-9])) != 0))
    return dict(
        label=label,
        vy_std=float(np.std(vL)),
        vy_max=float(np.max(np.abs(vL))),
        flips=flips,
        wy_max=float(np.max(np.abs(wy[L]))),
        y_ptp_mm=float((ypos[L].max() - ypos[L].min()) * 1e3),
        y_settle_mm=float(ypos[L].mean() * 1e3),
        qs_mean=float(qs[L].mean()),
        qs_ptp=float(qs[L].max() - qs[L].min()),
        defl_mean_mm=float(defl[L].mean() * 1e3),
        defl_ptp_mm=float((defl[L].max() - defl[L].min()) * 1e3),
        pil_v_max=float(np.max(pil_v[L])),
    )


def main():
    configs = [
        ("FULL (iters=4,sub=4)   ", dict()),
        ("COUPLER_OFF (rigid)    ", dict(coupler_off=True)),
        ("ITERS=16               ", dict(iters=16)),
        ("ITERS=24               ", dict(iters=24)),
    ]
    print("Reduced-coupled LEDGE — boulder jitter in LATE window (steps 480-720,"
          " ~2-6 s). vy_std/max in m/s, flips = vy sign changes (oscillation).\n")
    hdr = (f"{'config':<24}{'vy_std':>10}{'vy_max':>10}{'flips':>7}"
           f"{'wy_max':>9}{'y_ptp_mm':>9}{'qs_ptp':>9}{'defl_ptp':>9}"
           f"{'pilV_max':>9}")
    print(hdr)
    rows = {}
    for label, kw in configs:
        r = run(label.strip(), **kw)
        rows[label.strip()] = r
        print(f"{label:<24}{r['vy_std']:>10.2e}{r['vy_max']:>10.2e}"
              f"{r['flips']:>7d}{r['wy_max']:>9.2e}{r['y_ptp_mm']:>9.3f}"
              f"{r['qs_ptp']:>9.2e}{r['defl_ptp_mm']:>9.3f}"
              f"{r['pil_v_max']:>9.2e}")

    full = rows["FULL (iters=4,sub=4)"]
    off = rows["COUPLER_OFF (rigid)"]
    i16 = rows["ITERS=16"]
    i24 = rows["ITERS=24"]
    print("\n" + "=" * 78)
    fr = off["vy_std"] / full["vy_std"] if full["vy_std"] else 0.0
    print(f"COUPLER_OFF vy_std is {fr*100:.1f}% of FULL → "
          f"{'coupling is the source' if fr < 0.3 else 'NOT (mostly) the coupling'}")
    ir = i16["vy_std"] / full["vy_std"] if full["vy_std"] else 0.0
    ir24 = i24["vy_std"] / full["vy_std"] if full["vy_std"] else 0.0
    print(f"ITERS=16 vy_std is {ir*100:.1f}% of FULL, ITERS=24 is "
          f"{ir24*100:.1f}% → "
          f"{'under-convergence (iters cure it)' if ir < 0.6 else 'NOT iteration-limited'}")
    print("=" * 78)


if __name__ == "__main__":
    main()
