"""V1 — reservoir-exact governor (foundation §1 reservoir, §6 α, §15 core).

The V0 per-impulse governor (`passive_alpha`) sizes its budget from the rigid
loss at the FULL impulse (α=1); when it clamps (α<1) the realized loss no longer
matches that budget, so the cumulative §15 bound `Σ ΔE_modal ≤ η Σ L` can dip
negative on a prefix at η<1 (the "funding circularity" slack). The reservoir
governor (`reservoir_alpha` + `reservoir_draw`) removes the slack: a persistent
reservoir `R ≥ 0` makes the per-prefix bound exact for ANY η.

These tests assert (1) the construction guarantee `D(α) ≤ R` / `R ≥ 0`, (2) that
the governor provably never clamps at η=1, (3) the headline contrast — a case
where the old per-impulse cap dips the per-prefix margin negative while the
reservoir governor does not — and (4) the bound holding in the V0 sim and the
real scene band.
"""
from __future__ import annotations

import numpy as np

from dcr.modal.passive_inject import reservoir_alpha, reservoir_draw
from dcr.dcr.impulse_port_v0 import V0Config, run

_TOL = 1e-9


# ----------------------------------------------------------------------
# 1. Construction guarantee: D(α) ≤ R and α ∈ [0, 1].
# ----------------------------------------------------------------------
def test_reservoir_draw_within_budget():
    rng = np.random.default_rng(0)
    for _ in range(2000):
        lam0 = rng.uniform(0.0, 3.0)
        Uy2 = rng.uniform(0.0, 2.0)             # ‖U_y‖²
        a_m = lam0 * lam0 * Uy2                 # ‖s‖² ≥ 0
        b_m = rng.uniform(-2.0, 2.0)            # q̇·s (any sign)
        w_r = rng.uniform(0.1, 5.0)             # rigid eff inverse mass > 0
        v_c = rng.uniform(-3.0, 3.0)
        l1 = -v_c * lam0
        l2 = -0.5 * w_r * lam0 * lam0           # ≤ 0
        R = rng.uniform(0.0, 5.0)
        eta = rng.uniform(0.0, 1.0)
        alpha = reservoir_alpha(a_m, b_m, l1, l2, R, eta)
        assert -1e-12 <= alpha <= 1.0 + 1e-12
        draw = reservoir_draw(a_m, b_m, l1, l2, alpha, eta)
        # The whole point: the realized draw never exceeds the reservoir.
        assert draw <= R + 1e-9, (alpha, draw, R)


def test_reservoir_stays_nonnegative_over_sequence():
    """Feed a random sequence of impulses, debiting R each time — R must stay ≥0
    (so the per-prefix bound η Σ L − Σ ΔE_modal = R ≥ 0 holds at every prefix)."""
    rng = np.random.default_rng(1)
    for eta in (0.0, 0.1, 0.3, 0.5, 0.9, 1.0):
        R = 0.0
        for _ in range(500):
            lam0 = rng.uniform(0.0, 2.0)
            Uy2 = rng.uniform(0.0, 1.5)
            a_m = lam0 * lam0 * Uy2
            b_m = rng.uniform(-1.5, 1.5)
            w_r = rng.uniform(0.2, 3.0)
            v_c = rng.uniform(-2.0, 2.0)
            l1 = -v_c * lam0
            l2 = -0.5 * w_r * lam0 * lam0
            alpha = reservoir_alpha(a_m, b_m, l1, l2, R, eta)
            R -= reservoir_draw(a_m, b_m, l1, l2, alpha, eta)
            assert R >= -_TOL, (eta, R)


# ----------------------------------------------------------------------
# 2. Never clamps at η=1 (design rule 1): a contact-resolving impulse has
#    D(1) = −½ ġ⁻²/w_eff < 0, so α=1 is always feasible.
# ----------------------------------------------------------------------
def test_reservoir_never_clamps_at_eta1():
    rng = np.random.default_rng(2)
    for _ in range(1000):
        Uy = rng.uniform(-1.0, 1.0, size=4)
        Uy2 = float(Uy @ Uy)
        w_r = rng.uniform(0.1, 4.0)
        w_eff = w_r + Uy2
        # closing contact: ġ⁻ < 0, λ₀ = −ġ⁻/w_eff > 0
        g_dot = -rng.uniform(0.05, 3.0)
        lam0 = -g_dot / w_eff
        qd = rng.uniform(-2.0, 2.0, size=4)
        s = -Uy * lam0
        a_m = float(s @ s)
        b_m = float(qd @ s)
        v_c = g_dot + float(Uy @ qd)            # v_corner·n = ġ⁻ + U_y·q̇
        l1 = -v_c * lam0
        l2 = -0.5 * w_r * lam0 * lam0
        # At η=1 with any R≥0, the governor must return α=1.
        for R in (0.0, 0.01, 1.0):
            alpha = reservoir_alpha(a_m, b_m, l1, l2, R, 1.0)
            assert alpha >= 1.0 - 1e-9, (alpha, R)


# ----------------------------------------------------------------------
# 3. Headline contrast: the per-impulse cap dips the per-prefix margin
#    negative on the FIRST injecting impulse (no banked loss); the reservoir
#    governor refuses to over-spend, so its margin stays ≥ 0.
# ----------------------------------------------------------------------
def _per_impulse_alpha(a_m, b_m, l1, l2, eta):
    """Replicate the V0 per-impulse governor's α (E_max = η·L(α=1) cap)."""
    L1 = l1 + l2
    E_max = eta * max(0.0, L1)
    if a_m < 1e-18:
        return 0.0
    if b_m + 0.5 * a_m <= E_max:
        return 1.0
    disc = b_m * b_m + 2.0 * a_m * E_max
    return float(np.clip((-b_m + np.sqrt(max(0.0, disc))) / a_m, 0.0, 1.0))


def test_per_impulse_slack_reservoir_fixes_it():
    # An injecting impulse onto a small-loss contact at low η: ΔE_modal(1) ≫
    # η·L(1), so per-impulse clamps to E_max but the realized loss L(α) ≪ L(1).
    a_m, b_m, l1, l2, eta = 0.01, 2.0, 0.1, -0.001, 0.5

    # per-impulse: injects up to η·L(1); realized margin can go negative.
    ap = _per_impulse_alpha(a_m, b_m, l1, l2, eta)
    dE_modal_p = b_m * ap + 0.5 * a_m * ap * ap
    L_p = l1 * ap + l2 * ap * ap
    margin_per_impulse = eta * L_p - dE_modal_p
    assert margin_per_impulse < -1e-3, margin_per_impulse   # the slack/bug

    # reservoir (R=0): refuses to over-spend → margin (= R) stays ≥ 0.
    ar = reservoir_alpha(a_m, b_m, l1, l2, 0.0, eta)
    R_after = 0.0 - reservoir_draw(a_m, b_m, l1, l2, ar, eta)
    assert R_after >= -_TOL, R_after
    # and it injects strictly less than the (over-spending) per-impulse cap.
    dE_modal_r = b_m * ar + 0.5 * a_m * ar * ar
    assert dE_modal_r <= dE_modal_p + _TOL


# ----------------------------------------------------------------------
# 4. V0 integration: reservoir mode keeps the per-prefix margin ≥ 0 across η,
#    and never clamps at η=1.
# ----------------------------------------------------------------------
def _v0(mode, eta, **kw):
    return run(V0Config(coupling="velocity", ring_vel="sampled",
                        governor_mode=mode, eta=eta, N=400, **kw))


def test_v0_reservoir_per_prefix_bound_holds_all_eta():
    for eta in (0.1, 0.3, 0.5, 1.0):
        for kw in (dict(y0=0.05),
                   dict(y0=0.0, qddot0=np.array([0.8, 0.6, 0.4, 0.2])),
                   dict(y0=0.03, qddot0=np.array([1.5, 1.0, 0.5, 0.25]))):
            r = _v0("reservoir", eta, **kw)
            assert r.invariant_margin_min >= -1e-6, (eta, kw, r.invariant_margin_min)
            assert r.pull_violations == 0


def test_v0_reservoir_no_clamp_at_eta1():
    r = _v0("reservoir", 1.0, y0=0.0, qddot0=np.array([1.5, 1.0, 0.5, 0.25]))
    assert r.clamp_activations == 0


# ----------------------------------------------------------------------
# 5. Scene band integration: apply_velocity_band with the reservoir governor
#    keeps the reservoir ≥ 0 and the per-prefix margin ≥ 0 at η < 1.
# ----------------------------------------------------------------------
def test_scene_band_reservoir_per_prefix():
    import numpy as _np
    from scenes.reduced_shelf import build_reduced_shelf
    from scenes.reduced_scene_xpbd_mirror import mirror_to_xpbd
    from dcr.dcr.impulse_port import apply_velocity_band

    h = build_reduced_shelf(device="cpu")
    h.rs.reset_state()
    xh = mirror_to_xpbd(h, h=1.0 / 120.0, substeps=4, iterations=4, device="cpu")
    coupler = xh.coupler
    coupler.device_resident = False
    coupler.anchor_includes_q_d = False
    solver = xh.world.solver

    # The per-prefix §15 bound is GLOBAL (across all steps): η·Σ L − Σ ΔE_modal
    # ≥ 0. `st.invariant_margin_min` is only a per-STEP ledger (reset each call),
    # so a step that spends budget banked on earlier steps shows a negative
    # per-step value legitimately — that is exactly what the reservoir is for.
    # The global accumulator (and the reservoir itself) is what must stay ≥ 0.
    eta = 0.3
    global_L = 0.0
    global_modal = 0.0
    global_margin_min = _np.inf
    res_min = _np.inf
    for _ in range(150):
        xh.world.step()
        st = apply_velocity_band(coupler, solver, eta=eta)
        global_L += st.cum_rigid_loss
        global_modal += st.cum_modal_inj
        global_margin_min = min(global_margin_min, eta * global_L - global_modal)
        res_min = min(res_min, st.reservoir)
    assert res_min >= -1e-9, res_min                       # reservoir never negative
    assert global_margin_min >= -1e-6, global_margin_min   # per-prefix §15 bound holds
