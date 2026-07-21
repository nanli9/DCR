"""§N2 / Stage X1 — the passive-energy bound GENERALIZED across the body-body
modal contact network (Contribution 3, foundation §15).

The support-path clamp (`_modal_commit`, tests/…/test_passivity_clamp.py) bounds
ΔE_modal ≤ η·ΔE_rigid_loss for a cube ringing the slab through a SUPPORT row.
This suite extends the guarantee to the AUGMENTED q-block: the network state
Q = [q_support; a_lower; a_upper] is capped as ONE global reservoir, so the ring
that reaches a cube touching only another cube (the box-box network) is inside the
same bound. `_modal_commit_cargo` scales the full Q, Q̇ by a single γ.

Verifies:
  1. default OFF is behaviour-neutral (existing network tests already cover the
     bit-identical OFF path; here: enforce+monitor is inert at the good config);
  2. the closed-system invariant E_modal(t) ≤ η·Σloss(t) holds over a full run
     for the network at a well-converged config — AND the upper (network-only)
     cube rings inside that bound;
  3. an over-relaxed / stiff-impact network INJECTS without the clamp (monitor
     records passive()=False) and is bounded WITH it (active clamp bites,
     n_clamped>0, passive()=True) — the clamp bites where the solver misbehaves;
  4. the clamp is INERT in the safe region (network coupling unchanged).
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("warp")

from dcr.avbd._solver.solver_6dof import Solver6DOF          # noqa: E402
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube    # noqa: E402
from dcr.fem.fem_model import Material                        # noqa: E402


def _net_stack(*, iters=12, subs=4, enforce=False, monitor=True,
               relax=0.7, drop=0.02, E=3.0e5):
    """Lower cube on a modal slab; upper cube stacked on it (BOX_BOX only, so its
    modes are reachable ONLY through the network). Mirrors
    test_modal_contact_network._stack, with the passivity knobs exposed."""
    s = Solver6DOF(dt=1.0 / 120.0, iterations=iters, substeps=subs, device="cpu",
                   gravity=(0.0, -9.81, 0.0))
    s.enable_self_collision(True, default_friction=0.0)
    s._modal_contact_network = True
    s._enforce_modal_passivity = bool(enforce)
    s._psv_monitor_only = bool(monitor)
    s._modal_relax = relax
    size = 0.1
    half = 0.5 * size
    mat = Material(E=E, nu=0.3, rho=600.0)
    L = build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0, material=mat)
    U = build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0, material=mat)
    Lb = s.add_box(position=(0.0, half + drop, 0.0), half_extents=(half,) * 3,
                   mass=float(L.mass), friction=0.0)
    Ub = s.add_box(position=(0.0, 3.0 * half + drop, 0.0),
                   half_extents=(half,) * 3, mass=float(U.mass), friction=0.0)
    r = 2
    omegas = np.array([60.0, 180.0])
    Mq = np.eye(r); Kq = np.diag(omegas ** 2); Dq = 0.02 * Mq + 2.0e-5 * Kq
    s.set_modal_support(Mq, Kq, Dq)
    U_y = np.array([1.0, 0.4])
    rows = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                off = (sx * half, sy * half, sz * half)
                rows.append((s.add_support_contact_corner(
                    Lb, off_a=off, y_rest=0.0, U_y_row=U_y), off))
    cb = L.corner_body
    support_rows = [(slot, int(np.argmin(np.linalg.norm(cb - np.array(off), axis=1))))
                    for slot, off in rows]
    s.add_cargo_native(Lb, L, support_rows)
    s.add_cargo_native(Ub, U, [])
    return s, Lb, Ub


def _run(s, Lb, Ub, n=200):
    aU = aL = 0.0
    for _ in range(n):
        s.step()
        aU = max(aU, float(np.linalg.norm(s.cargo_a(Ub.index))))
        aL = max(aL, float(np.linalg.norm(s.cargo_a(Lb.index))))
    P = s.positions()
    return s._psv_ledger, dict(aU=aU, aL=aL,
                               finite=bool(np.all(np.isfinite(P))))


# --------------------------------------------------------------------------- #
# 2. closed-system invariant holds for the network at a good config           #
# --------------------------------------------------------------------------- #
def test_network_invariant_holds_and_upper_rings():
    L, m = _run(*_net_stack(iters=12, subs=4, enforce=True, monitor=True))
    assert L is not None
    assert m["finite"]
    # the invariant holds across the whole network...
    assert L.passive(), (
        f"max_net_excess={L.max_net_excess:.3e} > max_deposit={L.max_deposit:.3e}")
    # ...and the network-only upper cube DOES ring inside that bound (the ring
    # reaching it through the box-box network is what the bound governs).
    assert m["aU"] > 1e-9, f"upper cube must ring (got {m['aU']:.2e})"
    # inert at this well-converged config
    assert L.n_clamped == 0


# --------------------------------------------------------------------------- #
# 3. over-relaxed / stiff network injects without the clamp; bounded with it   #
# --------------------------------------------------------------------------- #
# Retuned for the trapezoidal-W_g supply (foundation §15; the free-fall phantom
# fix): the previous marginal config (drop=0.02, E=3e6) injected only ~2×10⁻⁵ J
# above budget, which was the displacement-form gravity artifact rather than a
# real over-injection — the corrected accounting absorbs it (max_net_excess<0).
# A genuinely harder stiff impact still over-injects through the truncation
# artifact (max_net_excess≈1.2 J ≫ max_deposit≈0.25 J), so the clamp still has
# something to bite. See tests/avbd_native/test_gravity_supply_trapezoidal.py.
_INJECT = dict(iters=2, subs=1, relax=1.0, drop=0.05, E=1.0e7)


def test_network_injects_without_clamp():
    # monitor-mode records the UNCLAMPED ledger — the network over-injects: peak
    # network modal energy exceeds the rigid loss reservoir (passive() False).
    L, m = _run(*_net_stack(enforce=True, monitor=True, **_INJECT))
    assert m["finite"]
    assert not L.passive(), (
        f"expected injection: max_net_excess={L.max_net_excess:.3e} "
        f"vs max_deposit={L.max_deposit:.3e}")


def test_network_clamp_bounds_injection():
    # active clamp (monitor=False) scales the augmented Q,Q̇ back onto the passive
    # manifold — the guarantee bites where the solver misbehaves.
    L, m = _run(*_net_stack(enforce=True, monitor=False, **_INJECT))
    assert m["finite"]
    assert L.passive(), (
        f"clamp failed: max_net_excess={L.max_net_excess:.3e} "
        f"vs max_deposit={L.max_deposit:.3e}")
    assert L.n_clamped > 0, "the network clamp never actually fired"


# --------------------------------------------------------------------------- #
# 4. inert in the safe region (network coupling unchanged clamp on vs off)     #
# --------------------------------------------------------------------------- #
def test_network_monitor_is_behaviour_neutral():
    # monitor-mode (the AVBD default) records the ledger to CONFIRM passivity but
    # never scales Q — so the physics is bit-identical to clamp-off, at zero cost
    # to the two-way ring. You can always run the ledger as a free witness.
    _, off = _run(*_net_stack(iters=12, subs=4, enforce=False))
    Lon, on = _run(*_net_stack(iters=12, subs=4, enforce=True, monitor=True))
    assert Lon.n_clamped == 0
    assert on["aU"] == pytest.approx(off["aU"], rel=1e-9)
    assert on["aL"] == pytest.approx(off["aL"], rel=1e-9)
    assert Lon.passive()          # and it witnesses the safe-region run is passive


def test_network_active_clamp_preserves_safe_ring():
    # the ACTIVE clamp at a well-converged config bites at most on the sharp
    # impact transient (the documented one-substep PE-leads-KE lag — the reason
    # AVBD defaults to monitor-only) and preserves the two-way ring: it does NOT
    # damp the safe-region response.
    _, off = _run(*_net_stack(iters=12, subs=4, enforce=False))
    Lon, on = _run(*_net_stack(iters=12, subs=4, enforce=True, monitor=False))
    assert Lon.n_clamped <= 2, f"clamp over-fired in the safe region ({Lon.n_clamped})"
    assert on["aU"] == pytest.approx(off["aU"], rel=1e-2)
    assert on["aL"] == pytest.approx(off["aL"], rel=1e-2)


# --------------------------------------------------------------------------- #
# 1. default OFF behaviour-neutral (no ledger, no snapshot)                    #
# --------------------------------------------------------------------------- #
def test_network_default_off_is_neutral():
    s, Lb, Ub = _net_stack(enforce=False)
    assert s._enforce_modal_passivity is False
    for _ in range(30):
        s.step()
    assert s._psv_ledger is None      # snapshot/ledger never created when OFF
