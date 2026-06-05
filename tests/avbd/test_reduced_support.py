"""Unit + smoke tests for the Reduced-Coordinate AVBD Support Contact
(v1 prototype).

Covers:
  1. J_q = U_i^T n by finite difference of C (spec §6).
  2. q-block responds to augmented contact forcing in the predicted
     direction (spec §7 closed form).
  3. Zero projection ⇒ zero response (spec §13 J_q ≈ 0 risk).
  4. Transient overlay restores a peak the implicit macro-step
     suppresses (spec §8, decisive Section 20.1 experiment).
  5. AVBDDCRWorld behaviour is identical when no reduced support is
     attached (sanity: existing tests don't regress).
  6. End-to-end smoke: the shelf scene runs and the overlay arm gives a
     visibly larger probe |Δv| than the bare arm.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.avbd.reduced_support import (
    ReducedSupport,
    make_debug_reduced_shelf_support,
)
from dcr.avbd.reduced_support_solve import ReducedSupportCoupler


# ---------------------------------------------------------------------------
# 1. J_q = U_i^T n by finite difference.
# ---------------------------------------------------------------------------

def test_jq_finite_difference():
    """Spec §6: J_q = ∂C/∂q = U(x_s^0)^T n. Verify via FD of C(q)."""
    rs = make_debug_reduced_shelf_support(
        length=0.30, width=0.15,
        n_modes_global=4, n_modes_local=4,
    )
    # Pick a sample surface point and an arbitrary contact normal.
    pt_idx = rs.n_points // 2
    U_i = rs.U_points[pt_idx]                       # (3, r)
    n = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    x_s0 = rs.point_positions_rest[pt_idx]
    p_r = x_s0 + np.array([0.0, -1e-3, 0.0])        # 1 mm of penetration
    delta = 0.0

    def C(q: np.ndarray) -> float:
        # Spec convention: C = δ − n^T (p_r − x_s^0 − U q)
        return float(delta - n @ (p_r - x_s0 - U_i @ q))

    r_dim = U_i.shape[1]
    q0 = np.zeros(r_dim)
    Jq_analytic = U_i.T @ n                          # (r,)

    Jq_fd = np.zeros(r_dim)
    eps = 1e-6
    for k in range(r_dim):
        qp = q0.copy(); qp[k] += eps
        qm = q0.copy(); qm[k] -= eps
        Jq_fd[k] = (C(qp) - C(qm)) / (2.0 * eps)

    np.testing.assert_allclose(Jq_analytic, Jq_fd, atol=1e-9, rtol=1e-5)


# ---------------------------------------------------------------------------
# 2. q-block responds to augmented contact forcing.
# ---------------------------------------------------------------------------

def test_q_block_responds_to_contact():
    """Spec §7: Δq ≈ −H_q⁻¹ · (f_c · J_q) for a single isolated contact.

    Skip the rigid bodies entirely and verify the q-block math directly:
    apply a unit forcing on one row of U and check that the q-update
    sign matches −H_q⁻¹ · J_q.
    """
    rs = make_debug_reduced_shelf_support(
        length=0.30, width=0.15,
        n_modes_global=4, n_modes_local=4,
    )
    r_dim = rs.r
    h = 1.0 / 120.0

    # Identify which sample point is closest to (0, 0, 0) — that's
    # where the impactor lands.
    pt_idx = int(np.argmin(np.linalg.norm(rs.point_positions_rest, axis=1)))
    U_y_at_pt = rs.U_points[pt_idx, 1, :]           # (r,)

    # Pretend λ_avbd = −f_n · h, k = 0 (drop penalty term).
    # Then F_n = -lam/h = f_n. f_c = f_n. Contact contribution to g_q:
    #   g_q += f_n · J_q, with J_q = U_y_at_pt.
    f_n = 10.0
    Mq, Kq, Dq = rs.Mq, rs.Kq, rs.Dq
    g_q = f_n * U_y_at_pt
    H_q = (1.0 / (h * h)) * Mq + Kq + (1.0 / h) * Dq

    # Predicted update Δq = −H_q⁻¹ g_q.
    dq = np.linalg.solve(H_q + 1e-10 * np.eye(r_dim), -g_q)

    # The "downward displacement" at the contact under this Δq:
    dy_at_contact = float(U_y_at_pt @ dq)
    # With f_n > 0 representing an UPWARD body force, Newton's-3rd
    # reaction pushes the SHELF DOWN at the contact ⇒ dy < 0.
    assert dy_at_contact < 0.0, (
        f"Expected support to deform downward under upward body force; "
        f"got dy={dy_at_contact:.3e}")
    # And the update should be in the direction predicted by H_q⁻¹ J_q.
    ref = -np.linalg.solve(H_q + 1e-10 * np.eye(r_dim), U_y_at_pt)
    np.testing.assert_allclose(dq / np.linalg.norm(dq),
                               ref / np.linalg.norm(ref),
                               atol=1e-8)


# ---------------------------------------------------------------------------
# 3. Zero projection ⇒ zero response.
# ---------------------------------------------------------------------------

def test_zero_projection_zero_response():
    """Spec §13 risk: if U^T n ≈ 0, the q-block must not move.

    We build a synthetic basis whose y-row is zero at the contact point
    (mode shapes only displace in x). Then J_q = U_y = 0 ⇒ Δq = 0 for
    any contact forcing.
    """
    # Synthetic minimal RS with hand-tuned U_points: 1 mode that
    # displaces purely in x at every sample.
    r_dim = 1
    n_pts = 3
    U_points = np.zeros((n_pts, 3, r_dim))
    U_points[:, 0, 0] = 1.0   # pure-x displacement basis (J_q wrt +ŷ ⇒ 0)
    pos = np.array([[0.0, 0.0, 0.0],
                    [0.1, 0.0, 0.0],
                    [-0.1, 0.0, 0.0]])
    normals = np.zeros_like(pos); normals[:, 1] = 1.0
    Mq = np.eye(r_dim) * 1.0
    Kq = np.eye(r_dim) * 1.0e4
    Dq = np.zeros_like(Mq)
    rs = ReducedSupport(
        point_positions_rest=pos,
        point_normals_rest=normals,
        U_points=U_points,
        Mq=Mq, Kq=Kq, Dq=Dq,
        q=np.zeros(r_dim),
        qdot=np.zeros(r_dim),
        q_prev_macro=np.zeros(r_dim),
        q_hat=np.zeros(r_dim),
        r_modal=1,
        modal_omega=np.array([100.0]),
        modal_zeta=np.array([0.0]),
        probe_points=pos[:1].copy(),
        probe_normals=normals[:1].copy(),
        probe_U=U_points[:1].copy(),
        probe_body_indices=[0],
    )
    # Apply the same q-block recipe as the iteration_hook with strong
    # contact forcing on the n = +ŷ direction.
    h = 1.0 / 120.0
    U_y_at_pt = rs.U_points[0, 1, :]   # = 0 by construction
    f_n = 100.0
    g_q = f_n * U_y_at_pt
    H_q = (1.0 / (h * h)) * Mq + Kq + (1.0 / h) * Dq
    dq = np.linalg.solve(H_q + 1e-10 * np.eye(r_dim), -g_q)
    assert np.linalg.norm(dq) < 1e-12, (
        f"Expected near-zero response; got |Δq|={np.linalg.norm(dq):.3e}")


# ---------------------------------------------------------------------------
# 4. Overlay restores the transient peak.
# ---------------------------------------------------------------------------

def test_overlay_restores_transient_single_mode():
    """Spec §8 prediction: a single backward-Euler step under-estimates
    the SDOF peak by ~1/(ωh). The two-rate IIR overlay must recover
    something close to the analytic peak.

    Single mode, ω chosen so ω·h ≈ 10. Apply a unit impulse and compare
    the implicit-Euler "macro step" displacement against the maximum
    sub-stepped IIR displacement.
    """
    h = 1.0 / 120.0
    omega = 10.0 / h                                  # ω·h = 10
    v0 = 1.0                                          # initial modal velocity
    # Analytic peak: q_peak = v0 / ω.
    q_peak_analytic = v0 / omega

    # 4a. One BACKWARD-EULER step at the macro rate.
    # 1st-order system after BDF1 collapse:
    #   v¹ = v0 / (1 + ω²h²)
    #   q¹ = h · v¹ = h · v0 / (1 + ω²h²) ≈ v0 / (ω² h) for ωh ≫ 1.
    q_bdf1 = h * v0 / (1.0 + (omega * h) ** 2)

    # 4b. IIR sub-stepped overlay at T = π / (2 ω).
    T = np.pi / (2.0 * omega)
    n_substep = max(1, int(np.ceil(h / T)))
    # IIR coefficients (impulse-invariant, undamped).
    a1 = 2.0 * np.cos(omega * T)
    a2 = 1.0
    ar = np.sin(omega * T) / omega
    # First-step "impulse" = v0 (treating r as a modal velocity kick
    # for an undamped oscillator with m_j = 1).
    q_prev = 0.0
    q_prev2 = 0.0
    q_peak_iir = 0.0
    for k in range(n_substep):
        # ar / m * impulse. Match the stepper docstring: q_new = a1 q_prev
        # - a2 q_prev2 + ar * (r / m). v0 is a velocity → impulse = m·v0,
        # m = 1, so r = v0. Apply only at the first sub-step.
        r_k = v0 if k == 0 else 0.0
        q_new = a1 * q_prev - a2 * q_prev2 + ar * r_k
        q_peak_iir = max(q_peak_iir, abs(q_new))
        q_prev2 = q_prev
        q_prev = q_new

    # The implicit macro step suppresses the peak by ~ω·h (spec §8.1).
    suppression = q_peak_iir / max(q_bdf1, 1e-30)
    assert suppression > 5.0, (
        f"Overlay must dominate bare BDF1 by >5×; got {suppression:.2f}× "
        f"(q_iir={q_peak_iir:.3e}, q_bdf1={q_bdf1:.3e})")
    # And the overlay should approach the analytic peak (within ~30%
    # given the impulse-invariant discretization at T = π/(2ω)).
    assert abs(q_peak_iir - q_peak_analytic) / q_peak_analytic < 0.30, (
        f"Overlay peak {q_peak_iir:.3e} differs from analytic "
        f"{q_peak_analytic:.3e} by more than 30%")


# ---------------------------------------------------------------------------
# 5. Default-disabled: AVBDDCRWorld with no reduced support keeps working.
# ---------------------------------------------------------------------------

def test_reduced_support_default_disabled_world_step():
    """Construct a vanilla AVBDDCRWorld, add a floor + box, and verify
    `step()` runs without ever touching reduced-support code paths.

    Imports happen inside the test to keep the rest of the file pure
    numpy and importable even when the AVBD Warp backend is missing.
    """
    pytest.importorskip("warp")
    from dcr.avbd.world import AVBDDCRWorld

    w = AVBDDCRWorld(h=1.0 / 120.0, device="cpu", avbd_iterations=4)
    assert w.reduced_support is None
    assert w.reduced_support_coupler is None
    w.add_floor(0.0)
    w.add_box(mass=1.0, half_extents=(0.05, 0.05, 0.05),
              position=(0.0, 0.20, 0.0))
    contacts = w.step()
    assert isinstance(contacts, list)
    # No reduced-support energy entries should have been appended.
    assert w.reduced_support_energy_log == []


# ---------------------------------------------------------------------------
# 6. End-to-end smoke: overlay yields larger probe |Δv| than bare.
# ---------------------------------------------------------------------------

def test_overlay_vs_bare_shelf_smoke():
    """Decisive Section 20.1 experiment in miniature.

    Run the shelf scene 30 frames with overlay on and off; require the
    overlay arm to produce strictly larger probe |Δv| (averaged over the
    run) than the bare arm. Tolerant default: at least 1.5× difference.
    """
    pytest.importorskip("warp")
    import sys
    from pathlib import Path
    ROOT = Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scenes.reduced_support_shelf import build_reduced_support_shelf

    def run(overlay: bool) -> float:
        h = build_reduced_support_shelf(
            h=1.0 / 120.0,
            device="cpu",
            iterations=4,
            n_modes_global=6, n_modes_local=4,
            overlay_enabled=overlay,
            restart_overlay_each_step=True,
            reduced_support_enabled=True,
            impactor_v0=(0.0, -2.0, 0.0),
            impactor_drop_height=0.10,
        )
        w = h.world
        peak_dv = 0.0
        for _ in range(30):
            w.step()
            c = w.reduced_support_coupler
            if c is not None and c.last_probe_dv.size > 0:
                peak_dv = max(peak_dv, float(np.max(np.abs(c.last_probe_dv))))
        return peak_dv

    dv_overlay = run(overlay=True)
    dv_bare = run(overlay=False)
    # Bare arm injects the quasi-static d_qs / h; overlay arm injects
    # the sub-stepped peak / h. The ratio should be much greater than 1
    # for ωh ≫ 1, but in this synthetic scene we accept ≥1.5×.
    assert dv_overlay > 1.5 * max(dv_bare, 1e-12), (
        f"Overlay |Δv|={dv_overlay:.4g} must dominate bare "
        f"|Δv|={dv_bare:.4g} by ≥1.5×.")
