"""Acceptance: the unified dynamic modal constraint in AVBD and XPBD.

`two_band_coupling.html` (Approach B) carries the support's FULL dynamic modal
state `q` inside the contact solve. `multibody.MultiBodySystem` integrates that
incremental potential with dense Newton + penalty contact = the ground truth
(GT). `position_based.{AVBDDynamicSystem, XPBDDynamicSystem}` realize the SAME
potential inside the two real-time position-based solvers. These tests assert:

  1. settle      — both solvers damp to rest (‖v‖ → 0) with total energy monotone
                   non-increasing (passive for free — no governor);
  2. GT parity   — both converge to the GT's rest state (same static sag);
  3. two-way loop— a dropped impactor rings the slab and the ring KICKS a resting
                   bystander cube (slab → cube, structural — no velocity band);
  4. AL contact  — AVBD's augmented Lagrangian drives penetration ≤ the penalty GT.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.twobody.multibody import (build_side_by_side, build_stack,
                                    build_stack_impact)
from dcr.twobody.position_based import (AVBDDynamicSystem, SplitOneWaySystem,
                                        XPBDDynamicSystem)

_H = 5.0e-4


def _make(base, name, kind):
    if name == "AVBD":
        return AVBDDynamicSystem(base, n_outer=6, n_inner=3)
    return XPBDDynamicSystem(base, n_iters=25)


# solver name × cube kind (XPBD path is wired for FEM-modal bodies)
_CASES = [("AVBD", "fem"), ("AVBD", "abd"), ("XPBD", "fem")]


@pytest.mark.parametrize("solver,kind", _CASES)
def test_settle_and_passive(solver, kind):
    base = build_stack(kind, n_cubes=1, damping=0.6, k_c=4.0e5, gap=0.01)
    sys = _make(base, solver, kind)
    st = sys.initial_state()
    totals = [sys.energy_breakdown(st)["total"]]
    for _ in range(2500):
        st = sys.step(st, _H)
        totals.append(sys.energy_breakdown(st)["total"])
    totals = np.asarray(totals)
    assert np.linalg.norm(st.v) < 5.0e-3, f"{solver}/{kind} did not settle"
    # passive: total mechanical energy never increases (round-off tolerance)
    assert np.diff(totals).max() < 1.0e-6, f"{solver}/{kind} not passive"


@pytest.mark.parametrize("solver,kind", _CASES)
def test_matches_gt_rest_state(solver, kind):
    base = build_stack(kind, n_cubes=1, damping=0.6, k_c=4.0e5, gap=0.01)
    sys = _make(base, solver, kind)
    # GT
    gt = base.initial_state()
    for _ in range(2500):
        gt = base.step(gt, _H)
    # position-based solver
    st = sys.initial_state()
    for _ in range(2500):
        st = sys.step(st, _H)
    # same static sag (rest configuration) as the monolithic ground truth
    assert np.linalg.norm(st.z - gt.z) < 1.0e-3, \
        f"{solver}/{kind} rest state diverged from GT"


@pytest.mark.parametrize("solver,kind", _CASES)
def test_two_way_bystander_kick(solver, kind):
    base, info = build_side_by_side(kind, n_rest=3, impactor_drop=0.35,
                                    impactor_rho=2500.0, damping=0.6, k_c=4.0e5)
    sys = _make(base, solver, kind)
    st = sys.initial_state()
    mid = info["rest_bodies"][len(info["rest_bodies"]) // 2]
    imp = info["impactor_body"]
    ke_mid, imp_y, modal = [], [], []
    for _ in range(2500):
        st = sys.step(st, _H)
        e = sys.energy_breakdown(st)
        ke_mid.append(e[f"KE_body{mid}"])
        modal.append(e["KE_body0"] + e["PEel_body0"])
        b = sys.bodies[imp]
        z = sys.body_z(st, imp)
        imp_y.append(z[1] if b.ndof == 12 else b.corner_rest[0, 1] + 0.05 + z[1])
    ke_mid = np.asarray(ke_mid)
    imp_y = np.asarray(imp_y)
    it = int(np.argmax(imp_y < 0.085))            # impact step
    quiet = ke_mid[max(0, it - 60):it].max()
    kick = ke_mid[it:it + 400].max()
    assert quiet < 1.0e-3, f"{solver}/{kind} bystander not quiet pre-impact"
    assert kick > 100.0 * quiet, f"{solver}/{kind} weak two-way kick"
    assert max(modal) > 0.2, f"{solver}/{kind} slab barely rang"


def test_split_is_one_way_dynamic_is_two_way():
    """The two-way signature is the slab's modal KINETIC energy: structurally 0
    for the one-way split (quasi-static slab — it cannot ring), and clearly
    nonzero for the dynamic constraint (the slab rings and feeds energy back).
    This is the answer to the PI's one-way-vs-two-way question."""
    base, info = build_side_by_side("fem", n_rest=3, impactor_drop=0.35,
                                    impactor_rho=2500.0, damping=0.6, k_c=4.0e5)
    split = SplitOneWaySystem(base)
    dyn = AVBDDynamicSystem(base, n_outer=6, n_inner=3)
    sp_slab_ke = dyn_slab_ke = 0.0
    sp, dy = split.initial_state(), dyn.initial_state()
    for _ in range(2000):
        sp = split.step(sp, _H)
        dy = dyn.step(dy, _H)
        sp_slab_ke = max(sp_slab_ke, split.energy_breakdown(sp)["KE_body0"])
        dyn_slab_ke = max(dyn_slab_ke, dyn.energy_breakdown(dy)["KE_body0"])
    assert sp_slab_ke < 1.0e-9, f"split slab ringing (KE={sp_slab_ke:.2e})"
    assert dyn_slab_ke > 0.1, f"dynamic slab did not ring (KE={dyn_slab_ke:.2e})"


def test_impactor_lands_on_bare_slab_not_through_cube():
    """Regression: the side-by-side impactor must land in a gap on the slab, not
    share a resting cube's x (no cube↔cube contacts ⇒ it would penetrate)."""
    base, info = build_side_by_side("fem", n_rest=3)
    imp = base.bodies[info["impactor_body"]]
    imp_x = float(imp.corner_rest[:, 0].mean())
    half = 0.05
    for bi in info["rest_bodies"]:
        cube_x = float(base.bodies[bi].corner_rest[:, 0].mean())
        assert abs(imp_x - cube_x) >= 2 * half, \
            f"impactor x={imp_x} overlaps resting cube x={cube_x}"
    # and placing it on a cube is now rejected loudly
    with pytest.raises(ValueError, match="penetrate"):
        build_side_by_side("fem", n_rest=3, impactor_x=0.0)


def test_stack_impact_heavy_box_is_stable_and_two_way():
    """A heavy fast box on a 3-cube stack: the box's initial velocity is applied,
    the dynamic solver stays stable (bounded penetration, finite energy), the slab
    rings hard (two-way), and the impact is absorbed (the system settles)."""
    base, info = build_stack_impact("fem", n_stack=3, impactor_rho=5000.0,
                                    impactor_v0=5.0, k_c=1.0e6, damping=0.6)
    imp = info["impactor_body"]
    st0 = base.initial_state()
    assert st0.v[base.offsets[imp] + 1] < -1.0, "box initial velocity not applied"

    dyn = AVBDDynamicSystem(base, n_outer=8, n_inner=4)
    st = dyn.initial_state()
    slab_ke = max_pen = 0.0
    for _ in range(1600):
        st = dyn.step(st, 5.0e-4)
        e = dyn.energy_breakdown(st)
        slab_ke = max(slab_ke, e["KE_body0"])
        max_pen = max(max_pen, e["max_penetration"])
        assert np.isfinite(e["total"])
    assert slab_ke > 1.0, f"slab barely rang under heavy impact (KE={slab_ke:.2e})"
    assert max_pen < 5.0e-3, f"contact unstable (pen={max_pen*1e3:.2f}mm)"
    assert np.linalg.norm(st.v) < 0.5, "impact not absorbed (still moving fast)"


def test_stack_impact_split_cannot_absorb():
    """One-way contrast: under the same heavy impact the split's quasi-static slab
    rings not at all (slab modal KE ≡ 0) — it cannot absorb the impact."""
    base, info = build_stack_impact("fem", n_stack=3, impactor_rho=5000.0,
                                    impactor_v0=5.0, k_c=1.0e6, damping=0.6)
    split = SplitOneWaySystem(base)
    st = split.initial_state()
    slab_ke = 0.0
    for _ in range(1600):
        st = split.step(st, 5.0e-4)
        slab_ke = max(slab_ke, split.energy_breakdown(st)["KE_body0"])
    assert slab_ke < 1.0e-9, f"quasi-static slab should not ring (KE={slab_ke:.2e})"


@pytest.mark.parametrize("kind", ["fem", "abd"])
def test_avbd_nonpenetration_beats_penalty(kind):
    """AVBD's augmented Lagrangian holds the load with λ, so its penetration is
    ≤ the penalty GT's (which holds it with gap = −f/k_c)."""
    base = build_stack(kind, n_cubes=2, damping=0.6, k_c=4.0e5, gap=0.01)
    avbd = AVBDDynamicSystem(base, n_outer=6, n_inner=3)
    gt_st, av_st = base.initial_state(), avbd.initial_state()
    gt_pen = av_pen = 0.0
    for _ in range(2500):
        gt_st = base.step(gt_st, _H)
        av_st = avbd.step(av_st, _H)
        gt_pen = max(gt_pen, base.energy_breakdown(gt_st)["max_penetration"])
        av_pen = max(av_pen, avbd.energy_breakdown(av_st)["max_penetration"])
    assert av_pen <= gt_pen + 1.0e-6, \
        f"AVBD penetration {av_pen:.2e} worse than GT {gt_pen:.2e}"
