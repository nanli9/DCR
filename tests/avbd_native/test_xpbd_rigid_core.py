"""Stage 2 — standalone XPBD rigid core (CPU reference).

SolverXPBD is a genuinely independent solver: its own Macklin small-steps
integrator + its own box-box/floor contact as compliant unilateral constraints
with positional Coulomb friction. NO coupler, NO AVBD host. These tests pin the
CPU-reference acceptance from prompts/native_dual_solver_build_plan.md Stage 2:

* free fall integrates gravity;
* a dropped box settles on the floor (no tunnel, comes to rest at y≈half);
* a 4-high box stack at rest HOLDS (the user's original stacking concern, now in
  the XPBD solver) — small tilt/sink over 400 steps;
* a tumbling (spinning) box collides via real SAT with no tunneling.

The device + CUDA-graph parity is in test_xpbd_rigid_device.py (Stage 2b).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.solver_xpbd import SolverXPBD


def _tilt_deg(quat_xyzw) -> float:
    """Angle of the body frame away from upright, from |q_w|."""
    w = abs(float(quat_xyzw[3]))
    return float(np.degrees(2.0 * np.arccos(min(1.0, w))))


def test_free_fall_integrates_gravity():
    """With no contacts, a body falls ½gt² (XPBD predict = symplectic Euler)."""
    s = SolverXPBD(dt=1.0 / 60.0, iterations=1, substeps=1, device="cpu")
    b = s.add_box(position=(0, 5, 0), half_extents=(0.1, 0.1, 0.1), mass=1.0)
    y0 = s.positions()[b.index][1]
    n = 30
    for _ in range(n):
        s.step()
    t = n * s.dt
    y = s.positions()[b.index][1]
    # symplectic Euler drop after n steps of size h: Σ accumulates to ≈ ½ g t²
    # (within one step of the closed form). Just check it fell the right order.
    assert y < y0
    drop = y0 - y
    assert abs(drop - 0.5 * 9.81 * t * t) < 0.5 * 9.81 * s.dt * t, (drop,)


def test_box_settles_on_floor_no_tunnel():
    """A box dropped onto y=0 settles at y≈half, never tunnels, and comes to
    rest (low residual velocity)."""
    half = 0.1
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=4, device="cpu")
    b = s.add_box(position=(0, 0.6, 0), half_extents=(half, half, half),
                  mass=1.0, friction=0.5)
    s.add_floor_contact_box(b, floor_y=0.0)
    min_y = np.inf
    for _ in range(240):
        s.step()
        P = s.positions()
        assert np.all(np.isfinite(P))
        min_y = min(min_y, float(P[b.index][1]))
    y = float(s.positions()[b.index][1])
    speed = float(np.linalg.norm(s.velocities()[b.index]))
    assert abs(y - half) < 5e-3, f"did not settle at y≈half ({y:.4f})"
    assert min_y > half - 5e-3, f"tunneled below the floor (min_y={min_y:.4f})"
    assert speed < 1e-2, f"did not come to rest (|v|={speed:.4f})"
    assert s.max_penetration < 1e-3


def test_four_high_stack_holds():
    """A 4-high box stack at rest holds — small tilt and sink over 400 steps.
    This is the user's original stacking concern, now validated on the XPBD
    solver's OWN box-box contact (it does not inherit the AVBD box-box bug)."""
    half = 0.1
    # A 4-high stack needs a real GS budget to converge (it=20/sub=4 is
    # marginal — the top, least-constrained box slowly tips); it=30/sub=8 holds
    # it flat. (The AVBD box-box path topples this same stack outright — the
    # pre-existing symmetric-stack bug, Decision #1 — which is exactly why the
    # XPBD solver gets its own contact.)
    s = SolverXPBD(dt=1.0 / 60.0, iterations=30, substeps=8, device="cpu",
                   friction_static_mult=1.0)
    s.enable_self_collision(True, default_friction=0.6)
    boxes = []
    # Stack centres at y = half, 3half, 5half, 7half (faces just touching),
    # seeded with a tiny gap so they settle into contact.
    for k in range(4):
        b = s.add_box(position=(0.0, half + 2 * half * k + 1e-3, 0.0),
                      half_extents=(half, half, half), mass=1.0, friction=0.6)
        s.add_floor_contact_box(b, floor_y=0.0)
        boxes.append(b)
    P0 = s.positions().copy()
    for _ in range(400):
        s.step()
        assert np.all(np.isfinite(s.positions())), "stack blew up"
    P = s.positions()
    Q = s.orientations()
    tilt = max(_tilt_deg(Q[b.index]) for b in boxes)
    sink = float(P0[boxes[0].index][1] - P[boxes[0].index][1])
    top_drift_xz = float(np.linalg.norm(
        P[boxes[3].index][[0, 2]] - P0[boxes[3].index][[0, 2]]))
    assert tilt < 2.0, f"stack toppled ({tilt:.2f}° tilt)"
    assert abs(sink) < 5e-3, f"stack sank/penetrated ({sink*1e3:.2f} mm)"
    assert top_drift_xz < 1e-2, f"stack slid apart ({top_drift_xz*1e3:.2f} mm)"


def test_tumbling_box_collides_no_tunnel():
    """A spinning box dropped on the floor collides via real SAT, stays finite,
    and never tunnels through the floor over the whole run."""
    half = 0.12
    s = SolverXPBD(dt=1.0 / 60.0, iterations=20, substeps=8, device="cpu")
    b = s.add_box(position=(0, 0.8, 0), half_extents=(half, half, half),
                  mass=1.0, angular_velocity=(3.0, 1.0, 2.0), friction=0.4)
    s.add_floor_contact_box(b, floor_y=0.0)
    min_corner_y = np.inf
    for _ in range(300):
        s.step()
        P = s.positions()[b.index]
        Q = s.orientations()[b.index]
        assert np.all(np.isfinite(P)) and np.all(np.isfinite(Q))
        # lowest corner above the floor (allow the contact margin)
        from dcr.avbd._solver.solver_xpbd import _quat_to_R, _CORNER_SIGNS
        R = _quat_to_R(np.asarray(Q, dtype=np.float64))
        corners = P + (R @ (_CORNER_SIGNS * half).T).T
        min_corner_y = min(min_corner_y, float(corners[:, 1].min()))
    assert min_corner_y > -5e-3, f"tunneled (min corner y={min_corner_y:.4f})"
    speed = float(np.linalg.norm(s.velocities()[b.index]))
    assert speed < 0.5, f"did not settle ({speed:.3f})"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
