"""M1.1/M1.2 — native modal support DOF inside Solver6DOF.

The support's modal amplitude q is a native solver DOF (set_modal_support +
SUPPORT_CONTACT rows), co-solved with the rigid body in the same backward-Euler
step via the in-solver q-block. No coupler, no hook. Validates that the body
rides the LIVE modal surface y_rest + U_y·q and that the two-way energy loop /
passivity hold in-solver (foundation: two_band_coupling.html).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.solver_6dof import Solver6DOF


def _build(freeze: bool, drop_h: float = 0.03, mass: float = 1.0):
    """One unit cube hovering `drop_h` above a 2-mode support at y_rest=0."""
    s = Solver6DOF(dt=1.0 / 60.0, iterations=12, substeps=4, device="cpu",
                   gravity=(0.0, -9.81, 0.0))
    half = 0.05
    body = s.add_box(position=(0.0, half + drop_h, 0.0),
                     half_extents=(half, half, half), mass=mass)
    r = 2
    omegas = np.array([35.0, 110.0])
    Mq = np.eye(r)
    Kq = np.diag(omegas ** 2)
    Dq = 0.02 * Mq + 2.0e-5 * Kq
    s.set_modal_support(Mq, Kq, Dq)
    s._modal_freeze_qdot = freeze
    # support contacts on the 4 bottom corners; same U_y at the shared (x,z).
    U_y = np.array([1.0, 0.4])
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            s.add_support_contact_corner(
                body, off_a=(sx * half, -half, sz * half),
                y_rest=0.0, U_y_row=U_y)
    return s, body


def test_body_rides_live_modal_surface_no_tunnel():
    s, body = _build(freeze=False, drop_h=0.04)
    for _ in range(120):
        s.step()
    q = s.modal_q
    surf = 0.0 + float(np.array([1.0, 0.4]) @ q)
    corner_y = float(s.positions()[body.index][1]) - 0.05
    assert corner_y - surf > -3e-3, "cube must rest on the deformed surface"
    assert s.last_q_norm > 1e-5, "the drop must load the mode (two-way)"


def test_two_way_counterfactual_in_solver():
    """Dynamic q̇ predictor rings; frozen q̇ counterfactual is quasi-static."""
    peak = {}
    for name, frz in (("dyn", False), ("frz", True)):
        s, _ = _build(freeze=frz, drop_h=0.03)
        pk = 0.0
        for _ in range(200):
            s.step()
            pk = max(pk, s.last_modal_KE)
        peak[name] = pk
        if frz:
            assert np.allclose(s.modal_qdot, 0.0), "frozen keeps q̇ ≡ 0"
    assert peak["dyn"] > 1e-7, f"dynamic support should ring ({peak['dyn']:.2e})"
    assert peak["dyn"] > 10.0 * max(peak["frz"], 1e-30), (
        f"dynamic ring {peak['dyn']:.2e} should dwarf frozen {peak['frz']:.2e}")


def test_modal_only_passivity_in_solver():
    """A plucked support with the body held clear rings down monotonically."""
    s, _ = _build(freeze=False, drop_h=2.0, mass=0.0)  # static body → no contact load
    # pluck the mode directly
    s._qdot_modal_host[:] = np.array([0.6, 0.3])
    s._q_modal_host[:] = 0.0

    def E():
        q, qd = s.modal_q, s.modal_qdot
        return float(0.5 * qd @ s._Mq @ qd + 0.5 * q @ s._Kq @ q)

    s.step()  # prime
    E_prev = E()
    E0 = E_prev
    for _ in range(200):
        s.step()
        e = E()
        assert e <= E_prev + 1e-9, f"modal energy rose {E_prev:.3e} -> {e:.3e}"
        E_prev = e
    assert E_prev < 0.7 * E0, "free ring should decay"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
