"""Stage E6 sound-render demo tests.

Covers: the resonator bank (frequency, decay, lfilter↔reference parity),
Hertzian shaping (impulse conservation, brightness monotonicity), the E6
audio ledger (cumulative inequality, quadratic cap), the free-free box basis,
and an end-to-end smoke on the real dinner scene + real logger.
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
from dcr.sound.render import AudioLedger


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
