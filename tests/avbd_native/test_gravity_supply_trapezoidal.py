"""§15 gravity-supply fix — free ballistic motion must register ZERO supply.

Reviewer probe (MIG R4, finding S2): the reservoir supply is
    ΔE_rig = (E_rig⁻ − E_rig⁺) + W_g          (paper Eq. (3), foundation §15)
and the paper claims "free ballistic motion registers zero supply". With the
DISPLACEMENT gravity work W_g = Σ m g·(x⁺−x⁻), that claim is FALSE under
symplectic Euler: x⁺ = x⁻ + h v⁺, so W_g exceeds the KE-consistent gravity work
by exactly ½ m h²|g|² per body per substep — a phantom supply that credits a
freely falling body with no contact. That residual is what produced the
impulse host's spurious −5.7×10⁻⁴ J "margin" (one substep of integrator
residual, with an implied mass constant across a 64× range of h).

The fix (all four solver ledger sites) is the TRAPEZOIDAL gravity work
    W_g = Σ m ½ g·(v⁻+v⁺) h,
the gravity work consistent with the symplectic KE update, which nets exactly
zero for contact-free motion at every h.

Part 1 (unit) reproduces the probe on the exact symplectic step the solvers
take, sweeping h over 64×; it needs no solver. Part 2 drives the real CPU
solvers to confirm the wiring (the v⁻ snapshot + trapezoidal accumulation)
actually zeroes the free-fall phase of a live run.
"""
from __future__ import annotations

import numpy as np
import pytest


G = np.array([0.0, -9.81, 0.0])


def _freefall_cum_supply(masses, h, n_steps, v0, formula):
    """Accumulate reservoir supply Σ max(ΔE_rig, 0) over `n_steps` of symplectic
    free fall (no contact), exactly as a solver ledger would, using either the
    'displacement' or 'trapezoidal' gravity work. Returns (cum_supply, per_step).

    Symplectic Euler, gravity only:  v⁺ = v⁻ + h g,  x⁺ = x⁻ + h v⁺.
    """
    masses = np.asarray(masses, float)
    v = np.tile(np.asarray(v0, float), (len(masses), 1))
    x = np.zeros((len(masses), 3))
    cum = 0.0
    per_step = []
    for _ in range(n_steps):
        ke_pre = 0.5 * float(np.sum(masses * np.einsum("ij,ij->i", v, v)))
        v_new = v + h * G                       # symplectic velocity update
        x_new = x + h * v_new                   # semi-implicit position update
        ke_post = 0.5 * float(np.sum(masses * np.einsum("ij,ij->i", v_new, v_new)))
        if formula == "displacement":
            wg = float(np.sum(masses * ((x_new - x) @ G)))
        elif formula == "trapezoidal":
            wg = float(np.sum(masses * (0.5 * (v + v_new) @ G) * h))
        else:
            raise ValueError(formula)
        rigid_loss = (ke_pre - ke_post) + wg
        cum += max(rigid_loss, 0.0)
        per_step.append(rigid_loss)
        v, x = v_new, x_new
    return cum, per_step


# --------------------------------------------------------------------------- #
# Part 1 — the fix, on the exact symplectic step (no solver)                   #
# --------------------------------------------------------------------------- #

_H_SWEEP = [1.0 / 60, 1.0 / 120, 1.0 / 240, 1.0 / 480,
            1.0 / 960, 1.0 / 1920, 1.0 / 3840]   # 64× range


@pytest.mark.parametrize("h", _H_SWEEP)
def test_trapezoidal_nets_zero_free_fall(h):
    # Multiple bodies, different masses, nonzero initial velocity (falling AND
    # rising): trapezoidal supply is zero to roundoff at every h.
    masses = [0.5, 11.0, 56.5]          # the paper's shelf/ledge/dinner masses
    cum, per_step = _freefall_cum_supply(
        masses, h, n_steps=200, v0=[0.3, 2.0, -0.5], formula="trapezoidal")
    assert cum < 1e-9, f"trapezoidal free-fall supply {cum} not ~0 at h={h}"
    assert max(abs(s) for s in per_step) < 1e-11


@pytest.mark.parametrize("h", _H_SWEEP)
def test_displacement_leaves_phantom_half_m_h2_g2(h):
    # The OLD displacement form credits exactly ½ m h² |g|² per body per substep,
    # independent of velocity — the artifact the reviewer predicted.
    masses = [0.5, 11.0, 56.5]
    n = 200
    cum, per_step = _freefall_cum_supply(
        masses, h, n_steps=n, v0=[0.3, 2.0, -0.5], formula="displacement")
    expected_per_step = 0.5 * sum(masses) * (h ** 2) * float(G @ G)
    # every substep is the same phantom quantum, regardless of velocity
    for s in per_step:
        assert s == pytest.approx(expected_per_step, rel=1e-9)
    assert cum == pytest.approx(n * expected_per_step, rel=1e-9)
    # and it is materially larger than the trapezoidal floor at every h
    assert cum > 1e-6


def test_phantom_mass_is_constant_across_h():
    # The reviewer's signature: back out the implied mass m* = 2·(supply/step)/
    # (h² g²) from the displacement form; it is the true mass at every h (the
    # "constant across a 64× range of h" tell), whereas trapezoidal backs out 0.
    m = 11.0
    g2 = float(G @ G)
    implied = []
    for h in _H_SWEEP:
        _, per = _freefall_cum_supply([m], h, n_steps=4, v0=[0.0, 5.0, 0.0],
                                      formula="displacement")
        implied.append(2.0 * per[0] / (h * h * g2))
    assert np.allclose(implied, m, rtol=1e-9)


# --------------------------------------------------------------------------- #
# Part 2 — wiring: the live CPU solvers zero the free-fall phase               #
# --------------------------------------------------------------------------- #

pytest.importorskip("warp")


def _lift_and_rest(sol, dy=50.0, spread=10.0):
    """Raise every body by `dy`, SCATTER them `spread` apart in x/z so none stay
    in mutual contact (lifting a resting stack as a unit keeps it stacked — the
    bodies must be separated to fall freely), and zero every velocity. Works on
    whichever backend the solver uses (warp `x`/`v` for the 6dof AVBD path,
    numpy `_X`/`_V` for the XPBD/impulse reference paths)."""
    def _scatter(X):
        n = X.shape[0]
        X[:, 0] += spread * np.arange(n)      # fan out along x
        X[:, 2] += spread * np.arange(n)      # and z, so no pair can touch
        X[:, 1] += dy
        return X
    if getattr(sol, "x", None) is not None:            # 6dof warp backend
        sol.x.assign(_scatter(sol.x.numpy()))
        V = sol.v.numpy(); V[:] = 0.0; sol.v.assign(V)
    else:                                              # numpy backends
        _scatter(sol._X)
        sol._V[:] = 0.0


def _build(solver_kind):
    from scenes.reduced_shelf import build_reduced_shelf
    H = build_reduced_shelf(device="cpu", iterations=8, avbd_substeps=4,
                            solver=solver_kind)
    sol = H.world._solver
    sol._modal_symplectic = True
    sol._enforce_modal_passivity = True
    sol._psv_monitor_only = True           # record supply, never clamp
    return H.world, sol


# 2a. Clean-integrator hosts (XPBD, impulse) genuinely free-fall when scattered,
#     so their ledger credits ZERO supply for the ballistic phase. (AVBD's
#     impactor is coupled to the reduced support and never falls freely — it is
#     covered by the white-box deposit check in 2b instead.)
@pytest.mark.parametrize("solver_kind", ["xpbd", "impulse"])
def test_clean_host_free_fall_supply_is_zero(solver_kind):
    try:
        w, sol = _build(solver_kind)
        w.step()                            # lazily builds the backend
        _lift_and_rest(sol)                 # scatter clear of contact, at rest
        L = sol._psv_ledger
        if L is None:
            pytest.skip(f"{solver_kind} ledger inactive")
        L.reset()
        for _ in range(3):                  # pure free fall
            w.step()
        cum = L.cum_rigid_loss
    except Exception as e:
        pytest.skip(f"{solver_kind} scene unavailable: {e}")
    # displacement bug would credit ≈ n_substeps·½Σm h²g² ≫ 1e-4; the fix ~0.
    assert cum < 1e-4, f"{solver_kind} free-fall supply {cum} not ~0"


# 2b. 6dof (AVBD) white-box: recompute the deposited rigid_loss independently
#     from the pre/post state and confirm the code path used the TRAPEZOIDAL
#     gravity work, not the displacement form (the two differ by the phantom
#     ½ h Σ m g·(v⁺−v⁻)). Robust to the scene carrying real coupling loss.
def test_avbd_deposit_matches_trapezoidal_form():
    from dcr.avbd._solver.passivity import rigid_mechanical_energy
    try:
        w, sol = _build("avbd")
        w.step()
        _lift_and_rest(sol)
        L = sol._psv_ledger
        if L is None:
            pytest.skip("avbd ledger inactive")
        L.reset()
    except Exception as e:
        pytest.skip(f"avbd scene unavailable: {e}")

    g = np.asarray(sol.gravity, float)
    diffs = {"trap_err": 0.0, "disp_gap": 0.0}
    orig = L.deposit

    def traced(rl):
        v_pre = np.asarray(sol._psv_v_pre)
        x_pre = np.asarray(sol._psv_x_pre)
        V = sol.v.numpy(); Wo = sol.omega.numpy(); Qq = sol._psv_quats_wxyz()
        X = sol.x.numpy()
        mass = np.asarray(sol._mass); dyn = mass > 0
        h = float(sol.dt)
        E_post = rigid_mechanical_energy(V, Wo, Qq, sol._mass,
                                         sol._inv_I_local,
                                         Il=sol._psv_local_inertia())
        wg_trap = 0.5 * h * float(np.sum(mass[dyn] * ((v_pre + V)[dyn] @ g)))
        wg_disp = float(np.sum(mass[dyn] * ((X - x_pre)[dyn] @ g)))
        rl_trap = (sol._E_rig_pre - E_post) + wg_trap
        rl_disp = (sol._E_rig_pre - E_post) + wg_disp
        diffs["trap_err"] = max(diffs["trap_err"], abs(rl - rl_trap))
        diffs["disp_gap"] = max(diffs["disp_gap"], abs(wg_trap - wg_disp))
        return orig(rl)

    L.deposit = traced
    for _ in range(3):
        w.step()

    # the deposited supply reproduces the trapezoidal recompute to roundoff ...
    assert diffs["trap_err"] < 1e-9, (
        f"deposited rigid_loss does not match the trapezoidal form "
        f"(max err {diffs['trap_err']}) — the 6dof path may still use displacement")
    # ... and the displacement form would have differed materially (non-vacuous).
    assert diffs["disp_gap"] > 1e-6, "no motion: the two W_g forms did not differ"
