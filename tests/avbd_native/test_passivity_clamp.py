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
# 1b. E8 — energy-GAINING rigid solve (ΔE_rigid < 0) edge cases               #
#     (paper §3.3/§4.5: the budget is max(loss, 0); a gaining substep funds   #
#     nothing and the cap formulas degrade to full rejection, never to a      #
#     negative square root.)                                                  #
# --------------------------------------------------------------------------- #
def test_deposit_negative_loss_credits_nothing():
    # A position-based solve can GAIN rigid energy in a substep (ΔE_rigid < 0).
    # The ledger credits zero — never a negative budget (foundation §15: only
    # irreversible loss funds the ring).
    L = PassivityLedger(eta=1.0)
    L.deposit(-5.0)
    assert L.reservoir == 0.0
    assert L.cum_rigid_loss == 0.0


def test_gain_step_starves_modal_funding():
    # Gaining solve (deposit clamps to 0) + attempted injection from rest:
    # ceiling = E_m_old + budget = 0 ⇒ γ = 0 — the kick is fully rejected and
    # the ledger invariants still hold.
    L = PassivityLedger(eta=1.0)
    budget = L.deposit(-3.0)
    assert budget == 0.0
    g = passivity_gamma(e_modal_new=2.0, e_modal_old=0.0, budget=budget)
    assert g == 0.0
    L.commit(realized_gain=0.0, budget=budget, alpha=g, e_modal_now=0.0)
    assert L.passive() and L.holds()
    assert L.n_clamped == 1


def test_alpha_zero_when_pe_alone_overshoots():
    # allowed_ke = budget + E_m_old − PE_new ≤ 0 ⇒ α = 0: the negative-
    # discriminant branch of the α* closed form (paper Eq. alphastar) resolves
    # to full rejection, not an imaginary root.
    assert passivity_alpha(ke_new=1.0, pe_new=5.0, e_modal_old=1.0,
                           budget=2.0) == 0.0


def test_reservoir_floor_never_negative():
    # Debiting more than the reservoir holds clamps at zero (no borrowing
    # against future losses) and the leak is recorded in max_violation.
    L = PassivityLedger(eta=1.0)
    L.deposit(1.0)
    L.commit(realized_gain=2.5, budget=1.0, alpha=1.0, e_modal_now=2.5)
    assert L.reservoir == 0.0
    assert L.max_violation == pytest.approx(1.5)


def test_rigid_energy_angular_ke_anisotropic_analytic():
    # Anisotropic inertia + 90° rotation about z: angular KE must equal
    # ½ ω_localᵀ I_l ω_local with ω_local = Rᵀω. Guards the (w,x,y,z) quat
    # convention at the solver boundary: warp / the XPBD reference store
    # XYZW, and feeding that layout unconverted builds a wrong rotation
    # (the pre-fix behaviour, asserted different below).
    Il = np.diag([1.0, 2.0, 3.0])
    invIl = np.linalg.inv(Il)[None, :, :]
    c, s = np.cos(np.pi / 4.0), np.sin(np.pi / 4.0)
    q_wxyz = np.array([[c, 0.0, 0.0, s]])        # 90° about z, project order
    w_world = np.array([[1.0, 0.0, 0.0]])
    E = rigid_mechanical_energy(np.zeros((1, 3)), w_world, q_wxyz,
                                [1.0], invIl)
    # R = Rz(90°) ⇒ ω_local = Rᵀω = (0,−1,0) ⇒ KE = ½·I_yy = 1.0
    assert E == pytest.approx(1.0, rel=1e-9)
    # the misread (XYZW fed where WXYZ is expected) gives a different energy
    E_bad = rigid_mechanical_energy(np.zeros((1, 3)), w_world,
                                    q_wxyz[:, [1, 2, 3, 0]], [1.0], invIl)
    assert abs(E_bad - 1.0) > 0.1


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
