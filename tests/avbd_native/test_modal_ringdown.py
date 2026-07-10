"""Modal ring-down ("settle") — unit + integration acceptance.

Acceptance criteria (brainstorm 2026-07-10, settle re-open):
  * velocity-only: q is NEVER mutated (position continuity ⇒ engaged-safe);
  * kill removes exactly the kinetic energy it zeroes, at q̄-crossings only;
  * the latch arms `delay` after the last excitation and re-arms on new ones;
  * the delivered kick (resting-object KE response) is preserved — removal
    starts only after the launch half-cycle;
  * ring energy after arming dies to a small fraction of the no-settle run;
  * removed energy is logged (cum_ringdown_dissipated), and the §15 ledger
    stays passive with the ring-down active (no misattribution).
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.modal.ringdown import ModalRingdown, RingdownConfig

H = 1.0 / 240.0


def _free_oscillator_run(rd, w, n_steps, q0=0.0, qd0=1.0):
    """Symplectic-Euler free SDOF ring feeding the operator each step.
    Returns (t_hist, q_hist, qd_hist, D_hist)."""
    q = np.array([q0], dtype=np.float64)
    qd = np.array([qd0], dtype=np.float64)
    hist = []
    for k in range(n_steps):
        qd -= (w ** 2) * q * H
        q += qd * H
        q_before = q.copy()
        D = rd.apply(q, qd, H)
        assert np.array_equal(q, q_before), "ring-down mutated q (position!)"
        hist.append((k * H, float(q[0]), float(qd[0]), D))
    t, qh, qdh, Dh = map(np.array, zip(*hist))
    return t, qh, qdh, Dh


def test_kill_exact_energy_at_crossing_and_delay():
    w = 2.0 * np.pi * 10.0
    cfg = RingdownConfig(mode="kill", delay=0.05, qbar_tau=1e9,
                         rearm_threshold=1e-12)
    rd = ModalRingdown(np.ones(1), np.array([w ** 2]), np.zeros(1), cfg)
    t, qh, qdh, Dh = _free_oscillator_run(rd, w, n_steps=200)

    kills = np.where(Dh > 0.0)[0]
    assert kills.size >= 1
    k0 = int(kills[0])
    # 1. Latch: nothing removed inside the arm delay.
    assert t[k0] >= cfg.delay
    # 2. The kill zeroed the velocity and D equals the removed KE exactly.
    assert qdh[k0] == 0.0
    qd_pre = qdh[k0 - 1] - (w ** 2) * qh[k0 - 1] * H   # velocity before apply
    assert Dh[k0] == pytest.approx(0.5 * qd_pre ** 2, rel=1e-12)
    # 3. It fired at a reference crossing: |q| there is O(qd·h) of the peak.
    assert abs(qh[k0]) < 1.5 * abs(qd_pre) * H
    # 4. The mode dies geometrically: one kill leaves only the residual PE at
    #    the crossing offset (≤ ½(ω·q̇·h)² ≈ 3% of E0 at ωh=0.26), and each
    #    subsequent crossing kill shrinks it by ~(ωh)² again.
    E_tail = 0.5 * qdh[k0:] ** 2 + 0.5 * w ** 2 * qh[k0:] ** 2
    assert E_tail.max() < 0.1 * 0.5            # E0 = ½·q̇0² = ½
    assert E_tail[-24:].max() < 1e-3 * 0.5     # dead by the end (0.1 s)
    assert rd.cum_dissipated == pytest.approx(Dh.sum(), rel=1e-12)


def test_rearm_on_reexcitation():
    w = 2.0 * np.pi * 10.0
    cfg = RingdownConfig(mode="kill", delay=0.05, qbar_tau=1e9,
                         rearm_threshold=1e-6)
    rd = ModalRingdown(np.ones(1), np.array([w ** 2]), np.zeros(1), cfg)
    _free_oscillator_run(rd, w, n_steps=200)          # ring → killed

    # Re-excite: energy jump re-arms the latch → no kill inside the delay.
    q = np.array([0.0])
    qd = np.array([1.0])
    n_delay = int(cfg.delay / H)
    removed_early = 0.0
    for k in range(n_delay - 1):
        qd -= (w ** 2) * q * H
        q += qd * H
        removed_early += rd.apply(q, qd, H)
    assert removed_early == 0.0
    # ...and after the window it kills again. For a CONSERVED ring the latch
    # keeps re-arming until the energy EMA catches up (worst case ≈ delay +
    # ~1.5·e_ema_tau — it errs toward preserving response), so give it 0.35 s.
    removed_late = 0.0
    for k in range(int(0.35 / H)):
        qd -= (w ** 2) * q * H
        q += qd * H
        removed_late += rd.apply(q, qd, H)
    assert removed_late > 0.0


def test_damp_factor_and_bookkeeping():
    w = 2.0 * np.pi * 20.0
    zeta_phys = 0.02
    cfg = RingdownConfig(mode="damp", delay=0.0, qbar_tau=1e9,
                         rearm_threshold=1e30,      # never re-arm: always armed
                         zeta_target=1.0)
    rd = ModalRingdown(np.ones(1), np.array([w ** 2]),
                       np.array([2.0 * zeta_phys * w]), cfg)
    q = np.array([0.0])
    qd = np.array([3.0])
    s = np.exp(-(1.0 - zeta_phys) * w * H)
    D = rd.apply(q, qd, H)
    assert qd[0] == pytest.approx(3.0 * s, rel=1e-12)
    assert D == pytest.approx(0.5 * 9.0 * (1.0 - s * s), rel=1e-12)


def test_rejects_non_diagonal_basis():
    M = np.array([[1.0, 0.3], [0.3, 1.0]])
    with pytest.raises(ValueError, match="diagonal"):
        ModalRingdown(M, np.eye(2), np.eye(2), RingdownConfig())


# --------------------------------------------------------------------------- #
# Integration: native dinner scene (the canonical rubbery-table repro)        #
# --------------------------------------------------------------------------- #
def _dinner_run(solver, ringdown, n_frames=200, enforce_passivity=False):
    from scenes.reduced_dinner_table import build_reduced_dinner_table
    handle = build_reduced_dinner_table(
        device="cpu", iterations=6, avbd_substeps=2, solver=solver,
        support_basis="fem", pot_drop_height=0.15)
    world = handle.world
    sol = world._solver
    if solver == "avbd" and hasattr(sol, "_modal_symplectic"):
        sol._modal_symplectic = True      # viewer default
    if enforce_passivity:
        sol._enforce_modal_passivity = True
        if getattr(sol, "_psv_ledger", None) is not None:
            sol._psv_ledger.eta = sol._modal_eta = 1.0
    if ringdown != "off":
        world.set_modal_ringdown(ringdown)     # default delay (0.15 s)
    # NOTE: native-thin path never syncs desc.dcr_body — read SOLVER state.
    sidx = [int(world._descs[i].avbd_body.index)
            for i in handle.probe_indices]
    ke = np.zeros(n_frames)
    lift = np.zeros(n_frames)
    y0 = None
    for f in range(n_frames):
        world.step()
        ke[f] = float(sol.last_modal_KE)
        ys = np.asarray(sol.positions(), dtype=np.float64)[sidx, 1]
        if f == 8:
            y0 = ys.copy()
        if y0 is not None:
            lift[f] = float(np.max(ys - y0))
    assert np.all(np.isfinite(ke))
    return sol, ke, lift


def test_avbd_dinner_kill_settles_ring_preserves_hop_and_logs():
    sol_off, ke_off, lift_off = _dinner_run("avbd", "off")
    sol_on, ke_on, lift_on = _dinner_run("avbd", "kill")
    tail = slice(-30, None)                    # last 0.25 s
    assert sol_on.cum_ringdown_dissipated > 0.0
    assert sol_off.cum_ringdown_dissipated == 0.0
    # ring KE in the tail collapses vs the no-settle run
    assert ke_on[tail].mean() < 0.05 * max(ke_off[tail].mean(), 1e-12)
    # the distant response (plate hop apex) is preserved: the default delay
    # covers the full delivery window of the ring-carried kick
    assert lift_off.max() > 1e-4, "no plate hop in the baseline run"
    assert lift_on.max() > 0.9 * lift_off.max()


def test_xpbd_dinner_kill_ledger_stays_passive():
    sol, ke, _ = _dinner_run("xpbd", "kill", enforce_passivity=True)
    assert sol.cum_ringdown_dissipated > 0.0
    assert sol._psv_ledger is not None and sol._psv_ledger.passive()
    assert ke[-20:].mean() < 1e-4              # ring is gone


# --------------------------------------------------------------------------- #
# Integration: kick preservation (the launch scene)                           #
# --------------------------------------------------------------------------- #
def _shelf_kick_run(ringdown, n_frames=120):
    # NOTE: on the native-thin path world.step() never syncs the DCR body
    # mirrors (world.py "Rendering reads world._solver.positions() directly"),
    # so the kick must be read from SOLVER state, not desc.dcr_body.
    from scenes.reduced_shelf import build_reduced_shelf
    handle = build_reduced_shelf(device="cpu", iterations=8,
                                 avbd_substeps=4, solver="avbd")
    world = handle.world
    sol = world._solver
    if ringdown != "off":
        world.set_modal_ringdown(ringdown, delay=0.025)
    imp = handle.impactor_idx
    sidx = [int(world._descs[i].avbd_body.index)
            for i in handle.probe_indices if i != imp]
    mass = np.asarray(sol._mass, dtype=np.float64)[sidx]
    ke_peak = 0.0
    for _ in range(n_frames):
        world.step()
        V = np.asarray(sol.velocities(), dtype=np.float64)[sidx]
        ke_peak = max(ke_peak, float(0.5 * (mass * (V * V).sum(axis=1)).sum()))
    return ke_peak


def test_kick_preserved_within_5pct():
    ke_off = _shelf_kick_run("off")
    ke_on = _shelf_kick_run("kill")
    assert ke_off > 1e-8, "shelf scene produced no kick at all"
    assert ke_on == pytest.approx(ke_off, rel=0.05)
