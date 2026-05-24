#!/usr/bin/env python3
"""A/B harness for the post-solver friction-cone clip and Coevoet kinematic
cap on the shelf scene. Headless (no polyscope). Compares trajectories
across {clip x cap} on/off at two timesteps (h=1e-3 and h=1e-2).

Metrics reported per run:
  - clip_fires / clip_attempts          (counter sums over all sim steps)
  - cap_fires / cap_attempts            (counter sums over all sim steps)
  - max_book_slide_x                    (max |x - x_initial| over all books
                                         after impact — smaller = less sliding)
  - min_book_penetration_y              (min (y - shelf_top - book_hy) over
                                         books — negative = penetrated)
  - max_drop_velocity_at_impact         (max |drop.velocity| during step
                                         after first contact — sanity check)

Usage:
    uv run python scripts/ab_shelf_clip_cap.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `import scripts.run_scenes` when invoked from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from scripts.run_scenes import build_shelf_scene


SHELF_TOP = 0.015
BOOK_HY = 0.04
SIM_DURATION_S = 1.5


def run_one(h: float, friction_cone_clip: bool, kinematic_cap: str,
            theta_max_deg: float = 3.0) -> dict:
    """Run one shelf simulation; return diagnostic dict."""
    world, coupler, body_info, _, _ = build_shelf_scene(
        velocity_mode="energy_prescribed_point_impulse",
        beta=0.25,
        budget_source="min_rigid_loss_modal",
        enforce_bound=True,
        deformed_normal_method="barbic_james",
        friction_cone_clip=friction_cone_clip,
        kinematic_cap=kinematic_cap,
    )
    # build_shelf_scene uses the module-level H constant — override the
    # world/solver timestep for the A/B comparison. (Body positions,
    # masses, etc. are h-independent so this is safe.)
    world.h = h
    world.solver.h = h
    # Override the deformed-normal clamp post-construction so we can sweep
    # theta_max without rebuilding the scene. Safe because the coupler's
    # __post_init__ only reads this field at kick time, not at build time.
    coupler.theta_max_deformed = float(np.radians(theta_max_deg))

    # Replicate scripts/run_scenes.py:simulate settle stage (impactor static).
    impactor_idxs = [body_info["drop"][0]]
    for idx in impactor_idxs:
        world.bodies[idx].is_static = True
    world.dcr_enabled = False
    for _ in range(200):
        world.step()
    for idx_b in range(len(world.bodies)):
        if idx_b not in impactor_idxs and not world.bodies[idx_b].is_static:
            world.bodies[idx_b].velocity[:] = 0.0
    for idx in impactor_idxs:
        world.bodies[idx].is_static = False
    world.dcr_enabled = True
    world.time = 0.0

    # Snapshot initial book x-positions.
    book_names = [n for n in body_info if n.startswith("book_")]
    init_x = {n: world.bodies[body_info[n][0]].position[0] for n in book_names}

    n_steps = max(1, int(round(SIM_DURATION_S / h)))
    clip_fires = 0
    clip_attempts = 0
    cap_fires = 0
    cap_attempts = 0
    max_slide_x = 0.0
    min_penetration_y = float("inf")  # min (book.y - shelf_top - BOOK_HY)
    max_drop_v = 0.0

    drop_idx = body_info["drop"][0]
    for _ in range(n_steps):
        world.step()
        clip_fires += coupler.last_friction_clip_fired
        clip_attempts += coupler.last_friction_clip_attempted
        cap_fires += coupler.last_kinematic_cap_fired
        cap_attempts += coupler.last_kinematic_cap_attempted
        for n in book_names:
            b = world.bodies[body_info[n][0]]
            slide = abs(b.position[0] - init_x[n])
            if slide > max_slide_x:
                max_slide_x = slide
            pen = float(b.position[1] - SHELF_TOP - BOOK_HY)
            if pen < min_penetration_y:
                min_penetration_y = pen
        v_drop = float(np.linalg.norm(world.bodies[drop_idx].velocity[:3]))
        if v_drop > max_drop_v:
            max_drop_v = v_drop

    return {
        "clip_fires": clip_fires,
        "clip_attempts": clip_attempts,
        "cap_fires": cap_fires,
        "cap_attempts": cap_attempts,
        "max_book_slide_x": max_slide_x,
        "min_book_penetration_y": min_penetration_y,
        "max_drop_velocity": max_drop_v,
    }


def main():
    # Focus on the clip question: does raising theta_max_deformed make the
    # clip actually fire and reduce slide? Cap is set to "none" throughout
    # so the clip is the only post-solver intervention.
    print(f"{'h':>6}  {'θ_max':>6}  {'clip':<5}  "
          f"{'clip f/a':>13}  {'slide_x[m]':>10}  {'pen_y[m]':>10}")
    print("-" * 70)
    for h in (1e-3, 1e-2):
        for theta_max_deg in (3.0, 30.0, 60.0):
            for clip in (False, True):
                r = run_one(
                    h=h, friction_cone_clip=clip, kinematic_cap="none",
                    theta_max_deg=theta_max_deg,
                )
                tag = "on " if clip else "off"
                print(
                    f"{h:>6.0e}  {theta_max_deg:>5.0f}°  {tag:<5}  "
                    f"{r['clip_fires']:>6}/{r['clip_attempts']:<6}  "
                    f"{r['max_book_slide_x']:>10.4f}  "
                    f"{r['min_book_penetration_y']:>10.4f}"
                )


if __name__ == "__main__":
    main()
