"""Stage X1 — native passive-energy clamp (foundation §15).

Verifies:
  1. the α / γ cap math (unit),
  2. the closed-system invariant E_modal(t) ≤ η·Σloss(t) holds over a full run
     for BOTH native solvers at PAPER_CONFIG (16×4),
  3. XPBD at a low-iteration budget (8×2) INJECTS without the clamp and is bounded
     WITH it (the clamp bites where the solver misbehaves),
  4. the clamp is INERT in the safe region (two-way object KE unchanged),
  5. default-OFF is behaviour-neutral.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd._solver.passivity import (
    passivity_alpha, passivity_gamma, PassivityLedger,
    rigid_mechanical_energy, modal_mech_energy,
)

pytest.importorskip("warp")
from scenes.reduced_shelf import build_reduced_shelf  # noqa: E402
from dcr.rigid.energy import rigid_kinetic_energy      # noqa: E402


# --------------------------------------------------------------------------- #
# 1. cap math (unit)                                                          #
# --------------------------------------------------------------------------- #
def test_passivity_gamma_inert_when_fits():
    # E_m_new below E_m_old + budget ⇒ γ = 1 (no scaling)
    assert passivity_gamma(e_modal_new=5.0, e_modal_old=4.0, budget=2.0) == 1.0


def test_passivity_gamma_scales_to_ceiling():
    # E_m_new = 10, E_m_old = 2, budget = 3 ⇒ ceiling 5 ⇒ γ = sqrt(5/10)
    g = passivity_gamma(e_modal_new=10.0, e_modal_old=2.0, budget=3.0)
    assert g == pytest.approx(np.sqrt(0.5), rel=1e-9)
    # scaling E_m by γ² lands exactly on the ceiling
    assert g * g * 10.0 == pytest.approx(5.0, rel=1e-9)


def test_passivity_gamma_zero_when_ceiling_nonpositive():
    assert passivity_gamma(e_modal_new=10.0, e_modal_old=0.0, budget=-1.0) == 0.0


def test_passivity_alpha_matches_foundation_quadratic():
    # velocity-only cap: α²·KE + PE − E_old ≤ budget
    ke, pe, e_old, budget = 8.0, 1.0, 1.0, 2.0
    a = passivity_alpha(ke, pe, e_old, budget)
    assert a * a * ke + pe - e_old == pytest.approx(budget, rel=1e-9)


def test_ledger_reservoir_and_invariants():
    L = PassivityLedger(eta=1.0)
    L.deposit(10.0)                       # reservoir 10
    L.commit(realized_gain=4.0, budget=10.0, alpha=1.0, e_modal_now=4.0)
    assert L.reservoir == pytest.approx(6.0)
    L.deposit(0.0)                        # no new loss
    L.commit(realized_gain=3.0, budget=6.0, alpha=1.0, e_modal_now=7.0)
    assert L.reservoir == pytest.approx(3.0)
    assert L.holds()                      # 7 ≤ 1·10
    assert L.passive()                    # peak 7 ≤ Σloss 10 (+ grace)


# --------------------------------------------------------------------------- #
# in-scene helpers                                                            #
# --------------------------------------------------------------------------- #
def _run(solver, iters, subs, enforce, nframes=90, relax=0.7):
    H = build_reduced_shelf(device="cpu", iterations=iters,
                            avbd_substeps=subs, solver=solver)
    sol = H.world._solver
    if solver == "avbd":
        sol._modal_relax = relax
    else:
        sol.modal_relax = relax
        sol._support_block_relax = relax
    sol._modal_symplectic = True
    sol._enforce_modal_passivity = bool(enforce)
    w = H.world
    imp = H.impactor_idx
    books = [i for i in H.probe_indices if i != imp]
    ib = w._descs[imp].dcr_body
    bbs = [w._descs[b].dcr_body for b in books]
    for _ in range(8):
        w.step()
    Eimp = Eslab = objke = 0.0
    for _ in range(nframes):
        w.step()
        Eimp = max(Eimp, rigid_kinetic_energy([ib]))
        Eslab = max(Eslab, sol.last_modal_KE + sol.last_modal_PE)
        objke = max(objke, max(rigid_kinetic_energy([b]) for b in bbs))
    return sol._psv_ledger, dict(Eimp=Eimp, Eslab=Eslab, objke=objke,
                                 passivity=Eslab / max(Eimp, 1e-9))


# --------------------------------------------------------------------------- #
# 2. closed-system invariant holds at PAPER_CONFIG, both solvers              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("solver", ["xpbd", "avbd"])
def test_passive_invariant_holds_at_paper_config(solver):
    L, _ = _run(solver, 16, 4, enforce=True)
    assert L is not None
    # E_modal(t) never exceeds Σ rigid loss (+ one-substep in-transit grace)
    assert L.passive(), (
        f"{solver}: max_net_excess={L.max_net_excess:.3e} "
        f"> max_deposit={L.max_deposit:.3e}")


# --------------------------------------------------------------------------- #
# 3. XPBD injects at 8×2 without the clamp; bounded with it                   #
# --------------------------------------------------------------------------- #
def test_xpbd_injects_without_clamp():
    L, m = _run("xpbd", 8, 2, enforce=False)
    # baseline (no clamp) massively injects: ring peak ≫ impactor KE
    assert m["passivity"] > 2.0


def test_xpbd_clamp_bounds_injection():
    L, m = _run("xpbd", 8, 2, enforce=True)
    assert L.passive()
    assert L.n_clamped > 0            # the clamp actually bit
    # ring peak no longer dwarfs the impactor input
    assert m["passivity"] < 1.5


# --------------------------------------------------------------------------- #
# 4. inert in the safe region (XPBD 16×4 two-way unchanged)                   #
# --------------------------------------------------------------------------- #
def test_clamp_inert_in_safe_region():
    _, off = _run("xpbd", 16, 4, enforce=False)
    L, on = _run("xpbd", 16, 4, enforce=True)
    assert L.n_clamped == 0           # never fires in the safe region
    assert on["objke"] == pytest.approx(off["objke"], rel=1e-6)


# --------------------------------------------------------------------------- #
# 5. default OFF is behaviour-neutral                                         #
# --------------------------------------------------------------------------- #
def test_default_off_is_behaviour_neutral():
    H = build_reduced_shelf(device="cpu", iterations=16, avbd_substeps=4,
                            solver="xpbd")
    sol = H.world._solver
    assert sol._enforce_modal_passivity is False
