"""Tests for the Python-side monolithic coupled reduced-coordinate AVBD
coupler (`ReducedCoupledAVBDCoupler`).

This is the "true coupled" extension: every AVBD iteration's primal+dual
is followed by a hook that solves the full Schur-eliminated [Δx; Δq]
system including the cross-coupling ρ·J_x·J_q^T. No overlay, no probe
Δv injection, no high-pass, no cooldown, no F_n cap.

Acceptance criteria the tests pin (from the plan):

  T1. Quasi-static box settles to the analytic K_q⁻¹·F equilibrium.
  T2. No overlay invocation across the entire run.
  T3. Distant probe responds to impactor through the shelf geometry
      alone (its FLOOR anchor moves; no Δv kick).
  T4. Schur complement is well-conditioned (cond(S) < 1e8).
  T5. rho_clip is never triggered on a normal scene.
  T6. Δq norm decreases monotonically within the iteration loop.
  T7. Double-update consistency: the hook is at its own fixed point
      after one pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_toy(iterations: int = 8, mass: float = 0.05,
               avbd_substeps: int = 16):
    pytest.importorskip("warp")
    from scenes.reduced_coupled_toy_minimum import build_toy_scene_1
    return build_toy_scene_1(
        iterations=iterations,
        mass=mass,
        avbd_substeps=avbd_substeps,
    )


def _analytic_static_q(rs, mass: float, half_extent: float) -> np.ndarray:
    """Analytic K_q⁻¹·F at static equilibrium for a box of `mass` sitting
    at center with corners at (±half_extent, ±half_extent).
    """
    from dcr.avbd.reduced_support import evaluate_basis_at_point
    F_per = mass * 9.81 / 4.0
    he = half_extent
    corner_xz = [(he, he), (he, -he), (-he, he), (-he, -he)]
    U_y_sum = np.zeros(rs.r, dtype=np.float64)
    for (xx, zz) in corner_xz:
        U_pt = evaluate_basis_at_point(
            rs, (xx, zz),
            length=0.30, width=0.15, n_grid_x=21, n_grid_z=11)
        U_y_sum += U_pt[1]
    rhs = -F_per * U_y_sum
    return np.linalg.solve(rs.Kq, rhs)


def _settle(world, n_frames: int) -> None:
    for _ in range(n_frames):
        world.step()


# ---------------------------------------------------------------------------
# T1. Static settling to K_q⁻¹·F
# ---------------------------------------------------------------------------

def test_quasi_static_box_settles_to_K_q_inverse():
    """Toy scene 1 — at static equilibrium the algebraic static-sag part
    `rs.q_s` matches the analytic `K_q⁻¹·F_corners` prediction within 5 %
    relative. The dynamic part `q_d` rings briefly on impact and decays
    to numerical noise after ~40 frames, but isn't strictly zero — so
    we assert on q_s.
    """
    handle = _build_toy(iterations=8, mass=0.05, avbd_substeps=16)
    c = handle.coupler

    _settle(handle.world, n_frames=40)

    # Analytic prediction.
    q_analytic = _analytic_static_q(handle.rs, mass=0.05, half_extent=0.02)
    norm_analytic = float(np.linalg.norm(q_analytic))
    norm_actual = float(c.last_q_s_norm)

    assert norm_analytic > 0.0
    rel_err = abs(norm_actual - norm_analytic) / norm_analytic
    assert rel_err < 0.05, (
        f"|q_s| settled to {norm_actual:.4e}, expected {norm_analytic:.4e} "
        f"(rel err {100*rel_err:.2f}% > 5%)")

    # Penetration should be at numerical noise.
    assert c.last_contact_residual < 1.0e-6, (
        f"penetration {c.last_contact_residual:.3e} > 1 µm at steady state")

    # No overlay event must have fired.
    assert c.cum_overlay_events_fired == 0


# ---------------------------------------------------------------------------
# T2. No overlay invocation
# ---------------------------------------------------------------------------

def test_no_overlay_invocation():
    """Across 60 macro steps, the cumulative overlay event count stays 0
    AND the world's reduced_support_energy_log stays empty (the
    overlay-only log is for the legacy coupler).
    """
    handle = _build_toy(iterations=8, mass=0.05, avbd_substeps=8)
    c = handle.coupler

    _settle(handle.world, n_frames=60)

    assert c.cum_overlay_events_fired == 0
    assert c.last_overlay_events_fired == 0
    # The legacy overlay coupler's log MUST be empty (we use the coupled
    # log instead).
    assert handle.world.reduced_support_energy_log == []
    assert len(handle.world.reduced_coupled_log) == 60
    for entry in handle.world.reduced_coupled_log:
        assert entry["cum_overlay_events_fired"] == 0
        assert entry["overlay_events_fired"] == 0


# ---------------------------------------------------------------------------
# T3. Distant probe responds through shelf geometry alone
# ---------------------------------------------------------------------------

def test_distant_probe_responds_to_impactor():
    """Shelf scene (impactor at center + probe at +0.4 L). When the
    impactor lands, q shifts; the probe's FLOOR anchor moves with q;
    the probe must register the deformation in its position OR (in the
    static-equilibrium limit) at least show a deformed anchor.

    No overlay → no Δv kick → probe motion is exclusively from
    gravity + anchor-shift.
    """
    pytest.importorskip("warp")
    from scenes.reduced_support_shelf import build_reduced_support_shelf
    handle = build_reduced_support_shelf(
        h=1.0 / 120.0, device="cpu", iterations=8,
        impactor_drop_height=0.02,
        impactor_v0=(0.0, -0.5, 0.0),
        impactor_mass=0.5,
        probe_mass=0.005,
        n_modes_global=6, n_modes_local=4,
        reduced_support_enabled=True,
        coupled_avbd=True,
        rayleigh_alpha0=0.0,
        rayleigh_alpha1=0.0,
    )
    w = handle.world
    c = w.reduced_coupled_coupler
    assert c is not None
    assert c.cum_overlay_events_fired == 0

    # Probe initial y.
    probe_idx = handle.probe_indices[0]
    probe_y0 = float(w._descs[probe_idx].dcr_body.position[1])

    # Run impact + settle.
    for _ in range(40):
        w.step()

    # Probe must NOT have been kicked into orbit (v1 overlay bug
    # symptom). 0.1 m/s max is a generous bound — gravity + a sub-µm
    # anchor shift produces ~mm/s at most.
    probe_vy_max = 0.0
    for desc_i in handle.probe_indices:
        b = w._descs[desc_i].dcr_body
        probe_vy_max = max(probe_vy_max, abs(float(b.velocity[1])))
    assert probe_vy_max < 0.1, (
        f"probe vy {probe_vy_max:.3e} > 0.1 m/s — suspicious of an "
        f"injection event.")

    # The deformed anchor at the probe location must shift from rest.
    rs = handle.rs
    # The first probe in probe_U is the first row of rs.probe_U.
    U_y_at_probe = rs.probe_U[0, 1, :]
    anchor_shift = abs(float(U_y_at_probe @ rs.q))
    # Tiny but nonzero — the probe's anchor has been moved by the
    # impactor's effect on q.
    assert anchor_shift > 1.0e-12, (
        f"Probe anchor never moved ({anchor_shift:.3e}); q didn't "
        f"propagate to probe location.")

    assert c.cum_overlay_events_fired == 0


# ---------------------------------------------------------------------------
# T4. Schur complement well-conditioned
# ---------------------------------------------------------------------------

def test_schur_well_conditioned():
    handle = _build_toy(iterations=8, mass=0.05, avbd_substeps=16)
    c = handle.coupler
    # Cond(S) is now gated behind `diagnostic_mode` so production runs
    # don't pay the O(r³) cost. Tests opt in explicitly.
    c.diagnostic_mode = True

    cond_max = 0.0
    for _ in range(30):
        handle.world.step()
        cond_max = max(cond_max, c.last_Schur_condition_estimate)

    assert cond_max < 1.0e8, (
        f"max cond(S) = {cond_max:.3e} — Schur complement is "
        f"ill-conditioned; auto-ε regulariser may need tuning.")


# ---------------------------------------------------------------------------
# T5. rho_clip never triggered on normal scene
# ---------------------------------------------------------------------------

def test_rho_clip_never_triggered():
    """In a static-rest scene, AVBD's penalty ρ should escalate only
    while |C| > 0; once we drive penetration to numerical noise, ρ
    stays moderate. Assert no row's effective ρ hits the clip
    (`rho_clip = 1e6` default).
    """
    handle = _build_toy(iterations=8, mass=0.05, avbd_substeps=16)
    c = handle.coupler

    total_hits = 0
    for _ in range(60):
        handle.world.step()
        total_hits += c.last_rho_clip_hits
    assert total_hits == 0, (
        f"rho_clip was hit {total_hits} times across the run — "
        f"AVBD's ρ has escalated to PENALTY_MAX-territory.")


# ---------------------------------------------------------------------------
# T6. Δq norm decreases inside iteration loop
# ---------------------------------------------------------------------------

def test_dq_decreases_within_iter_loop():
    """Single substep, N=16 iterations. Δq from successive iterations
    should be quasi-quadratic on the AL primal — the ratio
    `||Δq[k+1]|| / ||Δq[k]||` should shrink (geometric on the way to
    fixed point).
    """
    handle = _build_toy(iterations=16, mass=0.05, avbd_substeps=1)
    c = handle.coupler

    # Run 5 steps to get the system to a state where the inner loop
    # actually has work to do.
    for _ in range(5):
        handle.world.step()

    # Run one more step; the iter_dq_history is captured by the
    # iteration_hook during the last substep of that step.
    handle.world.step()
    history = list(c.last_iter_dq_norms)
    assert len(history) >= 4, (
        f"expected at least 4 iters of dq history, got {len(history)}")

    # The norms should decrease over the loop (allow up to one
    # temporary plateau; the trend is the assertion).
    decreasing = sum(history[k+1] < history[k] for k in range(len(history)-1))
    assert decreasing >= len(history) - 2, (
        f"dq norms not generally decreasing: {history}")


# ---------------------------------------------------------------------------
# T7. Double-update consistency (hook is at its own fixed point)
# ---------------------------------------------------------------------------

def test_double_update_consistency():
    """After a step's normal iteration_hook calls, force a second hook
    invocation on the algebraic static-sag coordinate q_s. At a converged
    fixed point the additional Δq_s must be at numerical-noise scale —
    proving the hook is at its own fixed point and AVBD's primal in the
    next iteration won't undo our work meaningfully.

    Threshold: |q_s_after - q_s_before| < 10⁻⁹ m. (q_d is the dynamic
    component and is not solved in iteration_hook, so this test does NOT
    probe it.)
    """
    handle = _build_toy(iterations=12, mass=0.05, avbd_substeps=4)
    c = handle.coupler
    w = handle.world

    # Settle.
    for _ in range(40):
        w.step()

    # Snapshot.
    q_s_before = handle.rs.q_s.copy()
    # Call iteration_hook once more on the current converged state.
    c.iteration_hook(w._solver, iter_idx=999)
    delta = float(np.linalg.norm(handle.rs.q_s - q_s_before))

    assert delta < 1.0e-9, (
        f"extra hook call shifted q_s by {delta:.3e} m — hook is not at "
        f"its own fixed point (q_s_norm={c.last_q_s_norm:.3e}).")


# ---------------------------------------------------------------------------
# T9 (drift-fix v1). Canonical drift scenario settles to < 1 mm.
# ---------------------------------------------------------------------------

def test_static_dynamic_split_no_drift():
    """The canonical drift case (steel × 5 kg × iter=4 × sub=4 × 5 s)
    pinned the +108 mm probe ratchet of the legacy IIR-anchor path. In
    the static_dynamic_split default the same scene must settle with
    |drift| < 1 mm (target: ~0.12 mm sub-mm settling).
    """
    pytest.importorskip("warp")
    from scenes.reduced_support_shelf import build_reduced_support_shelf

    handle = build_reduced_support_shelf(
        h=1.0/120.0, iterations=4, avbd_substeps=4,
        impactor_drop_height=0.30, impactor_v0=(0.0, -1.0, 0.0),
        impactor_mass=5.0, probe_mass=0.005,
        n_modes_global=8, n_modes_local=8,
        youngs=2.0e11, density=7850.0,
        reduced_support_enabled=True, coupled_avbd=True,
        rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6,
        to_eigenbasis=False,
    )
    w = handle.world
    probe_y0 = [float(w._descs[i].dcr_body.position[1])
                for i in handle.probe_indices]
    for _ in range(600):   # 5 s
        w.step()
    for k, idx in enumerate(handle.probe_indices):
        drift = float(w._descs[idx].dcr_body.position[1]) - probe_y0[k]
        assert abs(drift) < 1e-3, (
            f"probe[{k}] drifted {drift*1e3:+.2f} mm under "
            f"static_dynamic_split — legacy was +108 mm, target is < 1 mm.")


# ---------------------------------------------------------------------------
# T10 (drift-fix v1). q_d rings on impact (transient visibility).
# ---------------------------------------------------------------------------

def test_q_d_rings_on_impact_under_split():
    """Drop a 5 kg impactor; q_d (the dynamic modal part) must spike
    during the first 0.5 s impact transient and then decay through
    Rayleigh damping. If `peak |q_d|` ≪ steady |q_d|, the high-pass
    isn't producing transient excitation — q_d would be a silent
    visual hack instead of carrying real vibration."""
    pytest.importorskip("warp")
    from scenes.reduced_support_shelf import build_reduced_support_shelf

    handle = build_reduced_support_shelf(
        h=1.0/120.0, iterations=4, avbd_substeps=4,
        impactor_drop_height=0.30, impactor_v0=(0.0, -1.0, 0.0),
        impactor_mass=5.0, probe_mass=0.005,
        n_modes_global=8, n_modes_local=8,
        youngs=2.0e11, density=7850.0,
        reduced_support_enabled=True, coupled_avbd=True,
        rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6,
        to_eigenbasis=False,
    )
    w = handle.world
    c = w.reduced_coupled_coupler
    transient_peak = 0.0
    for k in range(60):                # ~0.5 s
        w.step()
        transient_peak = max(transient_peak, c.last_q_d_norm)
    # Then settle out to steady state.
    for _ in range(540):
        w.step()
    steady_q_d = c.last_q_d_norm
    # q_d must have rung non-trivially during the impact transient.
    assert transient_peak > 1.0e-4, (
        f"q_d did not ring during impact (peak={transient_peak:.2e}). "
        f"Either the high-pass is over-attenuating F_q_dyn or the IIR "
        f"step isn't being driven.")
    # And the transient must clearly exceed the steady-state residue.
    assert transient_peak > 5.0 * max(steady_q_d, 1.0e-12), (
        f"q_d transient {transient_peak:.2e} not ≫ steady {steady_q_d:.2e} "
        f"— the impact ring should dominate the steady residual by 5×+.")
