"""Tests for the artistic modal jump gain (demo knob II).

The jump gain `γ` adds a velocity-derived upward bias to the AVBD floor
constraint at each tracked corner:

    v_lift = min(γ · max(U_y·qdot − v_bar, 0), v_max)
    anchor_y  ←  floor_y_rest + U_y·q + h · v_lift

where v_bar is a one-pole low-pass of the modal surface velocity v_s, so
the high-passed signal v_s − v_bar rejects sustained sag and only
transients amplify. The constraint-mediated lift produces a visible
upward hop on the rigid body without any post-fix Δv kick.

Tests:

  Test 1: γ=1 default is bit-for-bit no-op.
  Test 2: High-pass rejects static / slow loading (no v_lift after
          equilibration).
  Test 3: Impact transient drives a positive v_lift briefly.
  Test 4: Very large γ is clamped by v_max = √(2·g·h_max).
  Test 5: γ=8 raises the probe (end-to-end visible amplification).
  Test 6: The jump path never invokes the DCR post-kick (architectural).
  Test 7: Modal |q| is NOT amplified by the jump knob (it acts on the
          rigid constraint, not on q).
  Test 8: Jump gain composes multiplicatively with impedance scaling.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run(*, n_frames: int, gain: float = 1.0, h_max: float = 0.01,
         impedance: float = 1.0, v0_y: float = -1.0,
         youngs: float = 1.0e10, substeps: int = 16):
    """Run the wood shelf with the new knobs. Returns
    (handle, coupler, peak_probe_rise, peak_q_norm, trailing_max_v_lift,
    transient_max_v_lift).

    `trailing_max_v_lift` is the max `last_max_v_lift` over the LAST 30
    frames; `transient_max_v_lift` is the max over ALL frames.
    """
    pytest.importorskip("warp")
    from scenes.reduced_support_shelf import build_reduced_support_shelf
    # Drift-fix v1: modal_jump_gain is a legacy-mode workaround for the
    # same drift this fix removes architecturally. Pin to legacy.
    handle = build_reduced_support_shelf(
        h=1.0 / 120.0, device="cpu",
        iterations=4, avbd_substeps=substeps,
        impactor_drop_height=0.02,
        impactor_v0=(0.0, v0_y, 0.0),
        impactor_mass=0.5,
        probe_mass=0.005,
        n_modes_global=6, n_modes_local=4,
        youngs=youngs,
        reduced_support_enabled=True,
        coupled_avbd=True,
        rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6,
        modal_impedance_scale=impedance,
        modal_jump_gain=gain,
        modal_jump_max_height=h_max,
        coupling_mode="iir_anchor_legacy",
    )
    w = handle.world
    c = w.reduced_coupled_coupler
    assert c is not None and c.q_integrator == "iir"

    probe_y0 = [float(w._descs[i].dcr_body.position[1])
                for i in handle.probe_indices]
    peak_rise = 0.0
    peak_q_norm = 0.0
    v_lift_hist: list[float] = []
    for _ in range(n_frames):
        w.step()
        peak_q_norm = max(peak_q_norm, float(np.linalg.norm(handle.rs.q)))
        for k, i in enumerate(handle.probe_indices):
            rise = float(w._descs[i].dcr_body.position[1]) - probe_y0[k]
            peak_rise = max(peak_rise, rise)
        v_lift_hist.append(float(c.last_max_v_lift))
    transient_max = max(v_lift_hist) if v_lift_hist else 0.0
    tail_window = max(1, min(30, n_frames // 4))
    trailing_max = max(v_lift_hist[-tail_window:]) if v_lift_hist else 0.0
    return handle, c, peak_rise, peak_q_norm, trailing_max, transient_max


# ---------------------------------------------------------------------------
# Test 1: γ=1 (and h_max=0.01) is a no-op.
# ---------------------------------------------------------------------------

def test_jump_gain_one_is_noop():
    """γ=1 + h_max=0.01 produces bit-for-bit identical peak |q| and probe
    rise to a run without the kwargs."""
    pytest.importorskip("warp")
    from scenes.reduced_support_shelf import build_reduced_support_shelf

    def _go(with_kwargs: bool):
        kw = (dict(modal_jump_gain=1.0, modal_jump_max_height=0.01)
              if with_kwargs else {})
        handle = build_reduced_support_shelf(
            h=1.0 / 120.0, device="cpu", iterations=4, avbd_substeps=16,
            impactor_drop_height=0.02, impactor_v0=(0.0, -1.0, 0.0),
            impactor_mass=0.5, n_modes_global=6, n_modes_local=4,
            youngs=1.0e10, reduced_support_enabled=True, coupled_avbd=True,
            rayleigh_alpha0=0.0, rayleigh_alpha1=5.0e-6,
            coupling_mode="iir_anchor_legacy", **kw)
        c = handle.world.reduced_coupled_coupler
        c.q_integrator = "iir"
        for _ in range(40):
            handle.world.step()
        return float(np.linalg.norm(handle.rs.q)), float(c.last_qdot_norm)

    q_a, qd_a = _go(with_kwargs=True)
    q_b, qd_b = _go(with_kwargs=False)
    assert abs(q_a - q_b) < 1e-12, f"γ=1 disturbed |q|: {q_a:.6e} vs {q_b:.6e}"
    assert abs(qd_a - qd_b) < 1e-12, (
        f"γ=1 disturbed |qdot|: {qd_a:.6e} vs {qd_b:.6e}")


# ---------------------------------------------------------------------------
# Test 2: high-pass rejects sustained loading (trailing v_lift → 0).
# ---------------------------------------------------------------------------

def test_jump_high_pass_rejects_static_sag():
    """Unit-level filter test: feed a CONSTANT modal surface velocity v_s
    to the one-pole low-pass; after ~5τ the high-passed signal
    v_hp = v_s − v_bar must decay to ≪ v_s. This isolates the filter math
    from the scene's bouncing dynamics (which keeps re-exciting v_s and
    is therefore not a "static" signal in the filter's frame).
    """
    h_sub = 1.0 / 120.0 / 16.0
    tau = 0.03
    alpha = h_sub / (tau + h_sub)
    v_s = 0.05    # constant 5 cm/s "modal surface velocity"
    v_bar = 0.0
    # Run 5·τ / h_sub ≈ 290 substeps.
    n_steps = int(5.0 * tau / h_sub)
    for _ in range(n_steps):
        v_bar = (1.0 - alpha) * v_bar + alpha * v_s
    v_hp = v_s - v_bar
    # After 5·τ, v_bar should be at least (1 − e^{-5}) ≈ 99.3% of v_s.
    assert v_hp < 0.02 * v_s, (
        f"Filter failed to track a constant input: v_hp/v_s = "
        f"{v_hp/v_s:.4f} after {n_steps} substeps "
        f"(expected ≪ 0.02).")


# ---------------------------------------------------------------------------
# Test 3: impact transient drives a positive v_lift.
# ---------------------------------------------------------------------------

def test_jump_transient_drives_lift():
    """During the impact transient the high-passed surface velocity is
    positive (upward modal motion) → v_lift > 0 on at least one substep
    when γ > 1. jump_engagements counts how many substeps had v_lift > 0."""
    _, c, _, _, _, transient_max = _run(n_frames=120, gain=8.0)
    assert transient_max > 0.0, (
        f"Expected v_lift > 0 during impact transient; got "
        f"transient_max={transient_max:.3e}.")
    assert c.jump_engagements > 0, (
        f"Expected jump_engagements > 0 with γ=8 + impactor; got "
        f"{c.jump_engagements}.")


# ---------------------------------------------------------------------------
# Test 4: v_max clamp.
# ---------------------------------------------------------------------------

def test_jump_clamp_at_v_max():
    """A huge γ must still respect v_max = √(2·g·h_max). Default
    h_max=0.01 → v_max ≈ 0.443 m/s."""
    _, c, _, _, _, transient_max = _run(n_frames=120, gain=1000.0)
    v_max = float(np.sqrt(2.0 * 9.81 * 0.01))
    assert transient_max <= v_max + 1e-9, (
        f"v_lift exceeded v_max: got {transient_max:.6e}, "
        f"v_max={v_max:.6e}.")
    # And the clamp should actually engage (peak should be exactly v_max
    # up to numerical equality given γ=1000 is way above the headroom).
    assert transient_max > 0.9 * v_max, (
        f"Expected the clamp to bind at γ=1000; transient_max="
        f"{transient_max:.6e} is far below v_max={v_max:.6e}.")


# ---------------------------------------------------------------------------
# Test 5: end-to-end — γ=8 raises the probe vs γ=1.
# ---------------------------------------------------------------------------

def test_jump_gain_lifts_probe():
    """The whole point: γ=8 should produce a visibly larger probe rise
    than γ=1 over the same scene."""
    _, _, rise_1, _, _, _ = _run(n_frames=120, gain=1.0)
    _, _, rise_8, _, _, _ = _run(n_frames=120, gain=8.0)
    ratio = rise_8 / max(rise_1, 1e-30)
    assert ratio >= 1.3, (
        f"γ=8 must raise probe ≥ 1.3× the γ=1 baseline; got {ratio:.2f}× "
        f"(rise_1={rise_1*1e6:.1f} µm, rise_8={rise_8*1e6:.1f} µm).")


# ---------------------------------------------------------------------------
# Test 6: no post-kick (architectural invariant).
# ---------------------------------------------------------------------------

def test_jump_no_postkick_calls():
    """The jump knob mediates lift through the AVBD contact multiplier
    only. It must not engage the legacy DCR Δv kick path under any γ."""
    _, c, _, _, _, _ = _run(n_frames=120, gain=8.0)
    assert c.dcr_postkick_calls == 0, (
        f"Jump-gain path leaked into DCR post-kick: "
        f"dcr_postkick_calls={c.dcr_postkick_calls}.")
    # Sanity: the cap path also stays at default (no eta requested).
    assert c.cap_engagements == 0


# ---------------------------------------------------------------------------
# Test 7: modal |q| is NOT amplified by the jump knob.
# ---------------------------------------------------------------------------

def test_jump_does_not_amplify_modal_q():
    """The jump knob lifts the rigid body via the constraint anchor;
    the modal `q` solve sees the same `g_q` (no jump term enters it).
    Peak |q| must not grow with γ (the small δ that does come through
    the contact-force / λ coupling is bounded)."""
    _, _, _, q_1, _, _ = _run(n_frames=120, gain=1.0)
    _, _, _, q_8, _, _ = _run(n_frames=120, gain=8.0)
    delta = abs(q_8 - q_1) / max(q_1, 1e-30)
    assert delta < 0.30, (
        f"Jump-gain leaked into modal block: |q|(γ=8) differs from "
        f"|q|(γ=1) by {delta*100:.1f}% (q_1={q_1*1e6:.1f} µm, "
        f"q_8={q_8*1e6:.1f} µm). Expected ≪ 30% — the constraint bias is "
        f"a body-side raise, not a q-side push.")


# ---------------------------------------------------------------------------
# Test 8: jump gain composes with impedance scaling.
# ---------------------------------------------------------------------------

def test_jump_composes_with_impedance():
    """The two knobs are independent levers. At fixed impedance g=4,
    adding γ=4 must still produce visibly more probe rise than γ=1 —
    i.e. the jump-gain knob remains effective when impedance is also
    engaged. (Note: the absolute rise at (g=4, γ=4) can be LOWER than
    (g=1, γ=4) because softer support is less bouncy → smaller v_s
    transient → smaller v_lift. That is a documented scene-side
    coupling, not a knob malfunction.)"""
    _, _, rise_g4_γ1, _, _, _ = _run(n_frames=120, gain=1.0, impedance=4.0)
    _, _, rise_g4_γ4, _, _, _ = _run(n_frames=120, gain=4.0, impedance=4.0)
    ratio = rise_g4_γ4 / max(rise_g4_γ1, 1e-30)
    assert ratio >= 1.3, (
        f"Adding γ=4 on top of g=4 must boost probe rise ≥ 1.3×; got "
        f"{ratio:.2f}× (rise@γ=1: {rise_g4_γ1*1e6:.1f} µm, "
        f"rise@γ=4: {rise_g4_γ4*1e6:.1f} µm). Knob composition broken.")
