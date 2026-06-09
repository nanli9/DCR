#!/usr/bin/env python3
"""Where does the visible 'book penetration' come from? Distinguish:
  (1) real rigid penetration — book corners below the floor plane, or
      adjacent books overlapping (AVBD contact under-resolution), vs
  (2) visual only — the FEM slab overlay (rest + Φ·q) poking up through
      books that actually rest on the flat collision plane.
Shelf scene, post-fix, default params."""
from __future__ import annotations
import numpy as np
from scripts.run_scenes_avbd import build_shelf_scene


def quat_to_R(wxyz):
    w, x, y, z = wxyz
    return np.array([
        [1 - 2*(y*y+z*z), 2*(x*y-z*w),     2*(x*z+y*w)],
        [2*(x*y+z*w),     1 - 2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w),     2*(y*z+x*w),     1 - 2*(x*x+y*y)]], dtype=float)


def corners(pos, wxyz, he):
    R = quat_to_R(wxyz)
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                local = np.array([sx*he[0], sy*he[1], sz*he[2]])
                out.append(pos + R @ local)
    return np.array(out)


def main(n_steps=240):
    world, coupler, boxes, mesh, _ = build_shelf_scene(
        device="cpu", h=1.0/120.0, eta=0.5, beta=0.25,
        causal_gating=False, modal_decay_gamma=1.0)
    floor_y = float(world._floor_y)
    U = coupler.modal.U_surf
    stp = coupler._stepper
    surf = coupler._surface
    book = [(b.body_idx, b.half_extents) for b in boxes
            if b.name.startswith("book_")]

    max_floor_pen = 0.0
    max_bookbook = 0.0
    max_overlay_up = 0.0
    max_tilt_deg = 0.0
    for _ in range(n_steps):
        world.step()
        # (1a) rigid floor penetration: lowest corner below floor_y.
        boxes_xz = []
        for idx, he in book:
            d = world._descs[idx].dcr_body
            cs = corners(np.array(d.position, float),
                         tuple(d.orientation), he)
            max_floor_pen = max(max_floor_pen, float(floor_y - cs[:, 1].min()))
            # tilt of local-up from world-up
            R = quat_to_R(tuple(d.orientation))
            tilt = np.degrees(np.arccos(np.clip(R[1, 1], -1, 1)))
            max_tilt_deg = max(max_tilt_deg, tilt)
            boxes_xz.append((cs[:, 0].min(), cs[:, 0].max()))
        # (1b) adjacent-book x-overlap (books are spaced along x).
        boxes_xz.sort()
        for a, b in zip(boxes_xz, boxes_xz[1:]):
            max_bookbook = max(max_bookbook, float(a[1] - b[0]))  # >0 = overlap
        # (2) FEM overlay vertical rise vs the flat plane the books rest on.
        disp = (U @ stp.q).reshape(-1, 3)
        max_overlay_up = max(max_overlay_up, float(disp[:, 1].max()))

    print(f"floor plane y = {floor_y:.4f} m, books 8cm tall x 1cm thick, "
          f"3cm gaps")
    print(f"(1a) max rigid floor penetration : {max_floor_pen*1000:8.3f} mm")
    print(f"(1b) max adjacent book overlap   : {max_bookbook*1000:8.3f} mm")
    print(f"(2)  max FEM-overlay upward rise : {max_overlay_up*1000:8.3f} mm "
          f"(visual only — books rest on the flat plane)")
    print(f"     max book tilt from upright  : {max_tilt_deg:8.3f} deg")


if __name__ == "__main__":
    main()
