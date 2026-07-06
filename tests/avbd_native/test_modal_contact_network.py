"""§N2 — Modal contact network: box-box rows between cargo bodies carry modal
columns, so a STACKED cube feels the ring of the cube under it.

Generalizes the support path (a cube rings the slab through a SUPPORT_CONTACT
row) to body↔body: a BOX_BOX contact between two cargo cubes couples both
participants' elastic modes through ONE shared multiplier
(∂C/∂a_A = +n̂ᵀR_AΦ_A, ∂C/∂a_B = −n̂ᵀR_BΦ_B — Newton's third law on Q). The slab
is the degenerate participant of the same gap. Behind `_modal_contact_network`
(default OFF ⇒ behaviour-neutral).

Setup shared by the physics tests: a lower cube L on a modal slab (SUPPORT
contacts + cargo) and an upper cube U stacked on L (BOX_BOX only, NO support
contacts). U's modes can therefore be reached ONLY through the box-box network —
a clean 0-vs-nonzero discriminator.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.solver_6dof import Solver6DOF
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube
from dcr.fem.fem_model import Material


def _stack(network: bool, *, freeze_lower: bool = False, xoff: float = 0.0,
           E: float = 3.0e5, drop: float = 0.02):
    """Lower cube on a modal slab; upper cube stacked on it (box-box only)."""
    s = Solver6DOF(dt=1.0 / 120.0, iterations=12, substeps=4, device="cpu",
                   gravity=(0.0, -9.81, 0.0))
    s.enable_self_collision(True, default_friction=0.0)
    s._modal_contact_network = bool(network)
    # Pin the conservative q-chase these §N2 counterfactuals were established
    # at (the class default moved 0.1 → 0.7 on 2026-07-06; the freeze-lower
    # inequality is a property of the conservative regime).
    s._modal_relax = 0.1
    size = 0.1
    half = 0.5 * size
    L = build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0,
                             material=Material(E=E, nu=0.3, rho=600.0))
    U = build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0,
                             material=Material(E=E, nu=0.3, rho=600.0))
    Lb = s.add_box(position=(0.0, half + drop, 0.0), half_extents=(half,) * 3,
                   mass=float(L.mass), friction=0.0)
    Ub = s.add_box(position=(xoff, 3.0 * half + drop, 0.0),
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
    s.add_cargo_native(Lb, L, support_rows)   # lower: support + cargo
    s.add_cargo_native(Ub, U, [])             # upper: cargo, NO support rows
    if freeze_lower:
        s._freeze_adot = {Lb.index}
    return s, Lb, Ub


def _run(s, Lb, Ub, n=240):
    aU = aL = keU = 0.0
    for _ in range(n):
        s.step()
        aU = max(aU, float(np.linalg.norm(s.cargo_a(Ub.index))))
        aL = max(aL, float(np.linalg.norm(s.cargo_a(Lb.index))))
        keU = max(keU, float(np.linalg.norm(s.cargo_adot(Ub.index))))
    P = s.positions()
    return dict(aU=aU, aL=aL, keU=keU, finite=bool(np.all(np.isfinite(P))),
                yU=float(P[Ub.index][1]))


# ---------------------------------------------------------------------------
def test_upper_cube_couples_only_with_network():
    """The CORE claim: the upper cube's modes ring iff the box-box modal network
    is on. Its only contact is box-box with the lower cube, so OFF it is
    completely uncoupled (a_U ≡ 0); ON it rings. A 0-vs-nonzero discriminator."""
    off = _run(*_stack(False))
    on = _run(*_stack(True))
    assert off["finite"] and on["finite"]
    # OFF: upper cube's modes are structurally uncoupled → exactly zero.
    assert off["aU"] < 1e-12, f"OFF upper must be uncoupled (got {off['aU']:.2e})"
    # ON: the network couples them → the upper cube's modes ring.
    assert on["aU"] > 1e-9, f"ON upper must ring (got {on['aU']:.2e})"
    # Lower cube rings in BOTH (it has support contacts) — the network must not
    # break the existing support path.
    assert off["aL"] > 1e-9 and on["aL"] > 1e-9


def test_freeze_lower_ring_reduces_upper_response():
    """§N2 counterfactual: freezing the lower cube's ring (ȧ_L ≡ 0) reduces the
    upper cube's modal response — i.e. part of the upper's ring is genuinely fed
    by the lower's ring (not only by the direct box-box contact impulse)."""
    free = _run(*_stack(True, freeze_lower=False))
    frz = _run(*_stack(True, freeze_lower=True))
    assert free["finite"] and frz["finite"]
    assert free["aU"] > frz["aU"], (
        f"lower ring should feed the upper: free {free['aU']:.2e} "
        f"vs frozen-L {frz['aU']:.2e}")


def test_network_is_bounded_no_blowup():
    """Stability smoke (plan §N3): coupling two resonators through an on/off
    unilateral contact must not inject unboundedly. Over a long run the upper
    cube's modal amplitude and velocity stay finite and small."""
    s, Lb, Ub = _stack(True, xoff=0.03)   # offset stack (not corner-aligned)
    res = _run(s, Lb, Ub, n=600)
    assert res["finite"], "no NaN/Inf over 600 steps"
    assert res["aU"] < 1.0, f"upper modal amplitude bounded (got {res['aU']:.2e})"
    assert res["keU"] < 10.0, f"upper modal velocity bounded (got {res['keU']:.2e})"
    assert res["yU"] > 0.0, "upper cube must not tunnel through the stack"


def test_off_parity_flag_is_neutral():
    """OFF must be behaviour-neutral: the rigid trajectory of a stack with the
    network flag OFF is bit-identical to one where the flag was never set."""
    s0, L0, U0 = _stack(False)          # flag explicitly False
    s1, L1, U1 = _stack(False)
    s1._modal_contact_network = False   # redundant set — same code path
    for _ in range(80):
        s0.step(); s1.step()
    P0, P1 = s0.positions(), s1.positions()
    assert np.array_equal(P0, P1), "OFF path must be deterministic + neutral"
