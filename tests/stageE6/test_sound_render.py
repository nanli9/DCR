"""Stage E6 sound-render demo tests.

Covers: the resonator bank (frequency, decay, lfilter↔reference parity),
Hertzian shaping (impulse conservation, brightness monotonicity), the E6
audio ledger (cumulative inequality, quadratic cap), the free-free box basis,
the radiation-weight heuristic, the contact-load gate + choked phasor render
(incl. exact parity with the LTI path when unchoked), and an end-to-end smoke
on the real dinner scene + real logger.
"""
from __future__ import annotations

import numpy as np
import pytest

from dcr.sound import (
    AudioBasis,
    Voice,
    build_box_audio_basis,
    extract_impulses,
    hertz_tau,
    impulse_kernel,
    render_modes_lfilter,
    render_modes_reference,
    render_soundtrack,
)
from dcr.sound.audio_basis import radiation_weight
from dcr.sound.events import LoadedTracker
from dcr.sound.render import AudioLedger, _render_voice, _render_voice_phasor


# ---------------------------------------------------------------------------
# Bank
# ---------------------------------------------------------------------------

def test_resonator_frequency_and_decay():
    fs = 44100.0
    f0, zeta = 440.0, 0.01
    omega = np.array([2 * np.pi * f0])
    n = int(fs)
    u = np.zeros((1, n)); u[0, 0] = 1.0
    y = render_modes_lfilter(u, omega, np.array([zeta]), fs)[0]

    # Spectral peak at the damped frequency f_d = f0·sqrt(1-ζ²).
    spec = np.abs(np.fft.rfft(y))
    f_peak = np.fft.rfftfreq(n, 1 / fs)[int(np.argmax(spec))]
    f_d = f0 * np.sqrt(1 - zeta ** 2)
    assert abs(f_peak - f_d) < 2.0

    # Envelope decays as e^(−ζω t) (Eq. 8 homogeneous solution).
    def rms(t0):
        i = int(t0 * fs)
        return float(np.sqrt(np.mean(y[i:i + 2205] ** 2)))
    ratio = rms(0.4) / rms(0.2)
    expected = np.exp(-zeta * 2 * np.pi * f0 * 0.2)
    assert abs(ratio / expected - 1.0) < 0.1


def test_lfilter_matches_reference():
    rng = np.random.default_rng(0)
    fs = 44100.0
    omega = 2 * np.pi * np.array([220.0, 1234.5, 7999.0])
    zeta = np.array([1e-3, 5e-3, 2e-2])
    u = np.zeros((3, 2000))
    idx = rng.integers(0, 2000, size=20)
    u[rng.integers(0, 3, size=20), idx] = rng.normal(size=20)
    y_fast = render_modes_lfilter(u, omega, zeta, fs)
    y_ref = render_modes_reference(u, omega, zeta, fs)
    assert np.allclose(y_fast, y_ref, atol=1e-10, rtol=1e-9)


# ---------------------------------------------------------------------------
# Shaping
# ---------------------------------------------------------------------------

def test_impulse_kernel_conserves_impulse():
    fs = 44100.0
    for t_event in (0.0, 0.123456, 1.0 / 3.0):
        for tau in (1e-5, 3e-4, 2e-3):     # incl. sub-sample degenerate
            _, w = impulse_kernel(t_event, tau, fs)
            assert abs(float(np.sum(w)) - 1.0) < 1e-12
            assert np.all(w >= 0.0)


def test_hertz_tau_monotone_brightness():
    taus = [hertz_tau(v) for v in (0.05, 0.5, 1.0, 3.0, 8.0)]
    assert all(a >= b for a, b in zip(taus, taus[1:]))   # faster ⇒ shorter
    assert taus[0] <= 4.0e-3 + 1e-12 and taus[-1] >= 1.5e-4 - 1e-12


# ---------------------------------------------------------------------------
# E6 ledger
# ---------------------------------------------------------------------------

def test_audio_ledger_quadratic_cap_and_inequality():
    led = AudioLedger(eta_audio=1.0)
    led.deposit(1.0)
    assert led.admit(0.4) == 1.0                     # fits, inert
    g = led.admit(0.9)                               # reservoir 0.6 < 0.9
    assert 0.0 < g < 1.0
    assert abs(g - np.sqrt(0.6 / 0.9)) < 1e-12       # §6 quadratic root
    assert led.admit(0.5) == 0.0                     # empty reservoir
    assert led.holds()                               # §15 cumulative form
    assert led.cum_kick_energy <= led.eta_audio * led.cum_rigid_loss + led.tol
    assert led.n_capped == 2 and led.min_gamma == 0.0


# ---------------------------------------------------------------------------
# Free-free box basis
# ---------------------------------------------------------------------------

def test_box_basis_free_free_plate():
    basis = build_box_audio_basis(
        half_extents=(0.085, 0.010, 0.085), mass=0.5,
        youngs=70.0e9, poisson=0.22, zeta_const=1.5e-3,
        num_modes=8, cells=(8, 2, 8), name="plate")
    assert basis.kind == "corners"
    assert 1 <= basis.n_modes <= 8
    f = basis.freqs_hz()
    assert np.all(f >= 60.0)                 # 6 rigid modes dropped
    assert np.all(np.diff(f) >= -1e-9)       # ascending
    assert 300.0 <= f[0] <= 8000.0           # plausible ceramic-plate f1
    assert basis.phi_corners.shape == (8, basis.n_modes)
    assert np.all(np.isfinite(basis.phi_corners))
    assert np.all(basis.weight > 0.0)


# ---------------------------------------------------------------------------
# Radiation weight heuristic
# ---------------------------------------------------------------------------

def test_radiation_weight_scaling():
    # Acoustic short-circuit: a small source radiates lows poorly — for a
    # 0.01 m² radiator the 100 Hz weight must sit far below the 5 kHz one.
    w = radiation_weight(np.ones(2), 2 * np.pi * np.array([100.0, 5000.0]),
                         area=0.01)
    assert w[0] < 0.15 * w[1]
    # Large-source, high-frequency limit: σ → 1 and w → √S · rms.
    w_hi = radiation_weight(np.ones(1), np.array([2 * np.pi * 8000.0]), 4.0)
    assert abs(w_hi[0] - 2.0) < 0.01
    # Area scaling: 4× the area → 2× the weight (σ≈1 regime).
    w1 = radiation_weight(np.ones(1), np.array([2 * np.pi * 8000.0]), 1.0)
    assert abs(w_hi[0] / w1[0] - 2.0) < 0.02
    # rms scaling stays linear.
    assert np.allclose(
        radiation_weight(np.full(1, 3.0), np.array([500.0]), 0.5),
        3.0 * radiation_weight(np.ones(1), np.array([500.0]), 0.5))


# ---------------------------------------------------------------------------
# Contact-load gate + choked phasor render
# ---------------------------------------------------------------------------

def test_loaded_tracker_hysteresis():
    trk = LoadedTracker(row_body=np.array([0, 0, 1]),
                        body_mass=np.array([2.0, 1.0]), g_mag=10.0,
                        on_frac=0.25, off_frac=0.10)
    # body 0: on at Σ ≥ 5 N, off below 2 N; body 1: on 2.5, off 1.0
    assert trk.update(np.array([3.0, 1.0, 0.0])) == []          # 4 < 5
    assert trk.update(np.array([4.0, 2.0, 0.0])) == [(0, True)]  # 6 ≥ 5
    assert trk.update(np.array([2.0, 1.0, 0.0])) == []          # 3 > 2 holds
    assert trk.update(np.array([1.0, 0.5, 0.0])) == [(0, False)]  # 1.5 < 2
    assert trk.update(np.array([0.0, 0.0, 2.6])) == [(1, True)]
    assert trk.loaded.tolist() == [False, True]


def _corner_basis(omega_hz, zeta, weight=None):
    omega_hz = np.asarray(omega_hz, dtype=np.float64)
    r = omega_hz.shape[0]
    return AudioBasis(
        name="mini", kind="corners",
        omega=2 * np.pi * omega_hz,
        zeta=np.asarray(zeta, dtype=np.float64),
        weight=(np.ones(r) if weight is None
                else np.asarray(weight, dtype=np.float64)),
        phi_corners=np.ones((8, r)), corner_signs=np.zeros((8, 3)))


def test_phasor_voice_matches_lfilter_unchoked():
    """No choke toggles → the segmented-phasor path must equal the LTI
    lfilter path to float precision (same impulse-invariant discretization)."""
    fs = 44100.0
    rng = np.random.default_rng(4)
    basis = _corner_basis([220.0, 1234.5, 6543.0], [1e-3, 5e-3, 2e-2],
                          weight=rng.uniform(0.5, 1.5, 3))
    voice = Voice(name="v", basis=basis)
    n = 8000
    for t_event, tau in ((0.0123, 8e-4), (0.0731, 2e-3), (0.0999, 1e-5)):
        k0, w = impulse_kernel(t_event, tau, fs)
        voice._splats.append((k0, w, rng.normal(size=3)))
    y_lti = _render_voice(voice, n, fs)
    y_ph = _render_voice_phasor(voice, n, fs, 0.08, toggles=[])
    assert np.allclose(y_ph, y_lti, atol=1e-9, rtol=1e-8)


def test_choke_shortens_ring_and_unchoke_resumes():
    fs = 44100.0
    basis = _corner_basis([1000.0], [1e-3])
    zeta_c = 0.02

    def _render(toggles):
        v = Voice(name="v", basis=basis)
        v._splats.append((0, np.array([1.0]), np.array([1.0])))
        return _render_voice_phasor(v, int(0.15 * fs), fs, zeta_c, toggles)

    def rms(y, t0, t1):
        return float(np.sqrt(np.mean(y[int(t0 * fs):int(t1 * fs)] ** 2)))

    y_free = _render([])
    y_choked = _render([(0, True)])
    y_resume = _render([(0, True), (int(0.05 * fs), False)])

    # Choked decay e^{-ζ_c ω t} ≪ free decay by 40–60 ms.
    assert rms(y_choked, 0.04, 0.06) < 0.05 * rms(y_free, 0.04, 0.06)
    # Energy only ever leaves faster: choked never exceeds free.
    assert np.max(np.abs(y_choked)) <= np.max(np.abs(y_free)) + 1e-12
    # Un-choking resumes the slow free-air decay from the surviving state.
    assert rms(y_resume, 0.09, 0.10) > 10.0 * rms(y_choked, 0.09, 0.10)
    assert rms(y_resume, 0.09, 0.10) < rms(y_free, 0.09, 0.10)


# ---------------------------------------------------------------------------
# End-to-end smoke: real dinner scene + real logger → WAV samples
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dinner_log():
    from scenes.reduced_dinner_table import build_reduced_dinner_table
    from dcr.sound.logger import attach_sound_logger

    handle = build_reduced_dinner_table(
        h=1.0 / 120.0, device="cpu", iterations=6, avbd_substeps=2,
        pot_drop_xz=(0.0, 0.0), solver="avbd", support_basis="debug")
    logger = attach_sound_logger(handle.world)
    for _ in range(108):                      # 0.9 s: drop at ~0.32 s + rattle
        handle.world.step()
    log = logger.finalize()
    logger.detach()
    return log


def test_end_to_end_dinner_impact(dinner_log):
    log = dinner_log
    assert log.n_substeps == 216
    assert float(log.F.max()) > 0.0           # contacts engaged

    events = extract_impulses(log)
    assert events.n_events >= 1
    assert float(events.impulse.max()) > 0.5  # the 5 kg pot at ~3 m/s

    # Rigid mechanical energy must have dropped somewhere (impact dissipation)
    # — that drop is the E6 budget.
    assert float(np.sum(log.rigid_loss_series())) > 0.0

    # Synthetic grid basis (no FEM build in the smoke test).
    from scenes.reduced_support_shelf import N_GRID_X, N_GRID_Z
    rng = np.random.default_rng(0)
    r = 6
    basis = AudioBasis(
        name="synthetic", kind="grid",
        omega=2 * np.pi * np.linspace(200.0, 2000.0, r),
        zeta=np.full(r, 5e-3), weight=np.full(r, 1.0),
        phi_grid=0.05 * rng.standard_normal((N_GRID_X * N_GRID_Z, r)),
        length=2.2, width=1.1, n_grid_x=N_GRID_X, n_grid_z=N_GRID_Z)

    audio, diag = render_soundtrack(
        log, table_voice=Voice(name="table", basis=basis),
        body_voices={}, fs=22050.0, eta_audio=1.0, tail=0.5, events=events)
    assert np.all(np.isfinite(audio))
    assert diag["raw_peak"] > 0.0             # non-silent
    assert diag["e6_holds"]                   # Σ kicks ≤ η·Σ rigid loss
    assert diag["n_admitted"] == events.n_events
