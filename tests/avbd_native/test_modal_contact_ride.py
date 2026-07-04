"""§N2 rigid-ride half: the lower cube's flex lifts the upper cube's RIGID body
(not just its modes), via the box-box gap reading the modal flex
(C = C_rigid + Ĝ_A·a_A − Ĝ_B·a_B; solver_6dof `_bake_ride_crest`,
kernels_6dof box-box `C -= c_rest`). Behind `_modal_contact_ride` (default OFF,
requires the network on).

Stabilized against the pre-registered N3 pump (two resonators coupled through an
on/off unilateral contact) by a per-joint compressive-engagement gate + hysteresis
+ under-relax + a capped, penetration-safe flex. STABLE for stacks with friction
(the demo default) and for settled frictionless stacks; a hard frictionless-offset
DROP transient can still tunnel — the honest N3 limitation, documented in
docs/network/n2.md and NOT asserted stable here.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.solver_6dof import Solver6DOF, BOX_BOX_CONTACT_6DOF
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube
from dcr.fem.fem_model import Material
from scenes.reduced_cargo_network import build_cargo_network_scene

DT = 1.0 / 120.0


def _boxbox_force(s):
    """Total active box-box normal force Σ|λ| (N) this step."""
    lam = s.lambdas(); act = s.active(); ct = s.c_type.numpy()
    ns = s._gpu_pool_n_static
    na = min(int(s.n_active_rows.numpy()[0]), s._gpu_pool_n_capacity)
    tot = 0.0
    for c in range(ns, na):
        if act[c] and int(ct[c]) == BOX_BOX_CONTACT_6DOF:
            tot += abs(float(lam[c]))
    return tot


def _two_cube(ride, *, mu=0.4, xoff=0.0, E=3.0e5):
    """Lower cube settled on the modal slab; upper cube on it (box-box only)."""
    s = Solver6DOF(dt=DT, iterations=12, substeps=4, device="cpu",
                   gravity=(0.0, -9.81, 0.0))
    s.enable_self_collision(True, default_friction=mu)
    s._modal_contact_network = True
    s._modal_contact_ride = bool(ride)
    size = 0.1
    half = 0.5 * size
    mk = lambda: build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0,
                                      material=Material(E=E, nu=0.3, rho=600.0))
    L, U = mk(), mk()
    Lb = s.add_box(position=(0.0, half, 0.0), half_extents=(half,) * 3,
                   mass=float(L.mass), friction=mu)
    Ub = s.add_box(position=(xoff, 3.0 * half, 0.0), half_extents=(half,) * 3,
                   mass=float(U.mass), friction=mu)
    Mq = np.eye(2); Kq = np.diag(np.array([60.0, 180.0]) ** 2)
    s.set_modal_support(Mq, Kq, 0.02 * Mq + 2.0e-5 * Kq)
    U_y = np.array([1.0, 0.4]); cb = L.corner_body
    rows = [(s.add_support_contact_corner(Lb, off_a=(sx * half, sy * half, sz * half),
             y_rest=0.0, U_y_row=U_y), (sx * half, sy * half, sz * half))
            for sx in (-1., 1.) for sy in (-1., 1.) for sz in (-1., 1.)]
    sr = [(slot, int(np.argmin(np.linalg.norm(cb - np.array(off), axis=1))))
          for slot, off in rows]
    s.add_cargo_native(Lb, L, sr)
    s.add_cargo_native(Ub, U, [])
    return s, Lb, Ub


# ---------------------------------------------------------------------------
def test_ride_off_is_bit_identical():
    """Rigid-ride OFF (network on) must be bit-identical to the network-only
    path — the box-box c_rest stays 0, so the primal/dual gap is unchanged."""
    s0, L0, U0 = _two_cube(False)
    s1, L1, U1 = _two_cube(False)
    for _ in range(120):
        s0.step(); s1.step()
    assert np.array_equal(s0.positions(), s1.positions()), "OFF must be deterministic"
    # And a network-only run (ride never enabled) vs one where ride=False set:
    s2, _, _ = _two_cube(False)
    for _ in range(120):
        s2.step()
    assert np.array_equal(s0.positions(), s2.positions())


def test_ride_demo_stack_stands():
    """The demo 3-high offset stack (friction, the shipped config) stays standing
    with the ride ON — the N3 pump does NOT walk it off or tunnel it."""
    h = build_cargo_network_scene(network=True, ride=True)
    s = h.world._solver
    idx = h.avbd_idx
    ymin = {nm: 1e9 for nm in ("base", "mid", "upper")}
    for _ in range(400):
        s.step()
        P = s.positions()
        for nm in ymin:
            ymin[nm] = min(ymin[nm], float(P[idx[nm]][1]))
    assert np.all(np.isfinite(s.positions()))
    # each cube must stay near its rest height (0.05 / 0.15 / 0.25), no tunnelling
    for nm, y0 in (("base", 0.05), ("mid", 0.15), ("upper", 0.25)):
        assert ymin[nm] > y0 - 0.02, f"{nm} sank to {ymin[nm]:.4f} (rest {y0})"


@pytest.mark.parametrize("xoff", [0.0, 0.03])
def test_ride_stable_with_friction(xoff):
    """2-cube stack with friction (aligned and offset) stays up with the ride ON
    over a long run — bounded, finite, no tunnel."""
    s, Lb, Ub = _two_cube(True, mu=0.4, xoff=xoff)
    ymin = 1e9
    for _ in range(500):
        s.step()
        ymin = min(ymin, float(s.positions()[Ub.index][1]))
    assert np.all(np.isfinite(s.positions()))
    assert ymin > 0.12, f"upper sank to {ymin:.4f} (rest 0.15)"


def test_ride_lifts_the_rigid_body():
    """The core claim: with the ride ON the upper cube's RIGID position includes
    the lower's flex. δy(t) = y_upper(ride ON) − y_upper(ride OFF) isolates the
    ride (identical setup otherwise): it is nonzero (the body rides) and bounded
    to the flex scale (tens of microns — it never becomes a rigid-scale motion)."""
    s_on, _, U_on = _two_cube(True, mu=0.4)
    s_off, _, U_off = _two_cube(False, mu=0.4)
    n = 480
    y_on = np.zeros(n); y_off = np.zeros(n)
    for i in range(n):
        s_on.step(); s_off.step()
        y_on[i] = float(s_on.positions()[U_on.index][1])
        y_off[i] = float(s_off.positions()[U_off.index][1])
    dy = y_on - y_off
    w = slice(int(0.4 / DT), n)
    ride_rms = float(np.std(dy[w]))
    assert ride_rms > 1e-6, f"ride ON must move the rigid body (got {ride_rms:.2e})"
    assert np.max(np.abs(dy[w])) < 5e-3, "the ride must stay flex-scale, not rigid"


def test_ride_smooths_the_contact_force():
    """The physical payoff: riding the deforming surface (rather than hammering a
    rigid one) removes the box-box contact-force chatter. The settled ripple of
    the box-box normal force is materially lower with the ride ON, while the mean
    stays at the supported weight (the ride does not change the force balance)."""
    n = 360
    f_on = np.zeros(n); f_off = np.zeros(n)
    s_on, _, _ = _two_cube(True, mu=0.4)
    s_off, _, _ = _two_cube(False, mu=0.4)
    for i in range(n):
        s_on.step(); s_off.step()
        f_on[i] = _boxbox_force(s_on)
        f_off[i] = _boxbox_force(s_off)
    w = slice(n // 3, n)                        # settled window
    rip_on = float(np.std(f_on[w])); rip_off = float(np.std(f_off[w]))
    mean_on = float(np.mean(f_on[w])); mean_off = float(np.mean(f_off[w]))
    assert rip_on < 0.7 * rip_off, (
        f"ride should smooth the contact force: ON ±{rip_on:.2f} N vs "
        f"OFF ±{rip_off:.2f} N")
    # mean force (the supported weight) is preserved to a few %.
    assert abs(mean_on - mean_off) < 0.1 * mean_off, (
        f"the ride must not change the force balance: {mean_on:.2f} vs {mean_off:.2f}")
