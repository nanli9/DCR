"""Headless analysis harness for the shelf scene across modes.

Records rigid-body trajectories for each --mode, then reports per-body:
  * min y (penetration check — shelf_top = 0.015)
  * max y
  * max tilt angle (degrees off-upright, from quaternion)
  * total x drift (sliding)
  * max body velocity magnitude

Used to verify the patch mode actually produces sane behavior before
shipping. Run with: uv run python scripts/analyze_patch_mode.py
"""
from __future__ import annotations

import numpy as np

from dcr.rigid.body import quat_to_rot
from scripts.run_scenes import (
    build_ledge_scene,
    build_shelf_scene,
    build_truck_scene,
    simulate,
)


SCENE_BUILDERS = {
    "shelf": build_shelf_scene,
    "truck": build_truck_scene,
    "ledge": build_ledge_scene,
}


SHELF_TOP = 0.015  # mirrors build_shelf_scene


def quat_to_tilt_deg(q: np.ndarray) -> float:
    """Angle in degrees between the body-frame +y axis (book up axis) and
    the world-frame +y axis. 0° = upright, 90° = on its side."""
    R = quat_to_rot(q)
    up_world = R @ np.array([0.0, 1.0, 0.0])
    cos_theta = float(np.clip(up_world[1], -1.0, 1.0))
    return float(np.degrees(np.arccos(abs(cos_theta))))


def analyze_run(scene: str, mode: str, beta: float = 0.25, n_steps: int = 1500):
    import sys
    print(f"\n========== scene={scene}  mode={mode}  beta={beta}  "
          f"steps={n_steps} ==========", flush=True)
    builder = SCENE_BUILDERS[scene]
    world, coupler, body_info, _mesh, _title = builder(
        velocity_mode=mode, beta=beta)
    print(f"  built scene ({len(world.bodies)} bodies), "
          f"simulating {n_steps} steps...", flush=True)
    times, positions, orientations = simulate(
        world, coupler, body_info, n_steps=n_steps)
    sys.stdout.flush()

    # Per-body stats. Books are book_0..book_4 (hy=0.04, so book bottom
    # is at center_y - 0.04; should never go below SHELF_TOP=0.015 →
    # center_y >= 0.055).
    print(f"{'body':<10} {'min_y':>9} {'max_y':>9} {'penetration':>12}  "
          f"{'max_tilt°':>10} {'x_drift':>9}  {'z_drift':>9}")
    for name, (idx, _hx, hy, _hz, _color) in body_info.items():
        pos = np.array(positions[name])
        orient = np.array(orientations[name])
        ys = pos[:, 1]
        xs = pos[:, 0]
        zs = pos[:, 2]
        body_bottom = ys - hy  # bottom of box
        pen = float(SHELF_TOP - body_bottom.min())  # +ve = below shelf
        tilts = [quat_to_tilt_deg(q) for q in orient]
        x_drift = float(xs[-1] - xs[0])
        z_drift = float(zs[-1] - zs[0])
        print(f"{name:<10} {ys.min():>9.4f} {ys.max():>9.4f} {pen:>12.4f}  "
              f"{max(tilts):>10.2f} {x_drift:>+9.4f} {z_drift:>+9.4f}")
    return body_info, positions, orientations


def main():
    n_steps = 1500
    beta = 0.25
    # All three scenes × {coevoet (baseline), point_impulse (Version B), patch}.
    # Lets us see which scene actually exercises the patch machinery.
    for scene in ["shelf", "truck", "ledge"]:
        for mode in ["coevoet", "energy_prescribed_point_impulse",
                     "energy_prescribed_patch"]:
            try:
                analyze_run(scene, mode, beta=beta, n_steps=n_steps)
            except Exception as e:
                print(f"  FAILED: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
