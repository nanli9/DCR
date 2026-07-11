"""Audio-rate modal IIR bank (Stage E6 demo).

Each audio mode is the paper's decoupled SDOF oscillator (Eq. 8):

    q̈_i + 2 ζ_i ω_i q̇_i + ω_i² q_i = r_i

driven by VELOCITY JUMPS (the modal impulse Φᵀj — foundation §4's projection,
here applied open-loop to the audio band). With mass-normalized modes a jump
of g adds g to q̇ directly (M_q = I). We listen to q̇ (surface velocity is the
radiating quantity), so per mode we need the discrete response of q̇ to a
q̇-jump train.

Exact (impulse-invariant) discretization at sample period T = 1/fs:
    r = e^(−ζωT),  θ = ω_d T,  ω_d = ω√(1−ζ²),  c = ζω/ω_d
    h_v[n] = rⁿ (cos nθ − c sin nθ)                (q̇ response to unit q̇-jump)
    H_v(z) = (1 − r(cosθ + c sinθ) z⁻¹) / (1 − 2r cosθ z⁻¹ + r² z⁻²)
via the standard damped-cosine/sine z-transforms. `render_modes_lfilter` runs
this biquad per mode; `render_modes_reference` propagates the exact 2×2 state
map per sample (the obviously-correct version, kept per CLAUDE.md rule 6) and
the two are parity-tested in tests/stageE6.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from scipy.signal import lfilter


def resonator_coeffs(
    omega: NDArray[np.float64],
    zeta: NDArray[np.float64],
    fs: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Per-mode biquad (b, a) for the q̇-response to a q̇-jump input track
    (derivation in the module docstring). Returns (b (r,2), a (r,3)).

    Modes must satisfy ω_d/(2π) < fs/2; callers band-limit at build time
    (audio_basis keeps f ≤ 0.45·fs) — asserted here as a hard guard.
    """
    omega = np.asarray(omega, dtype=np.float64)
    zeta = np.asarray(zeta, dtype=np.float64)
    T = 1.0 / float(fs)
    zc = np.clip(zeta, 0.0, 0.999999)
    omega_d = omega * np.sqrt(1.0 - zc ** 2)
    assert np.all(omega_d * T < np.pi), "audio mode above render Nyquist"
    r = np.exp(-zc * omega * T)
    theta = omega_d * T
    c = zc * omega / np.maximum(omega_d, 1e-30)
    b = np.stack([np.ones_like(r), -r * (np.cos(theta) + c * np.sin(theta))],
                 axis=1)
    a = np.stack([np.ones_like(r), -2.0 * r * np.cos(theta), r ** 2], axis=1)
    return b, a


def render_modes_lfilter(
    u: NDArray[np.float64],
    omega: NDArray[np.float64],
    zeta: NDArray[np.float64],
    fs: float,
) -> NDArray[np.float64]:
    """q̇ tracks (r, N) from q̇-jump input tracks u (r, N) — fast path."""
    u = np.asarray(u, dtype=np.float64)
    b, a = resonator_coeffs(omega, zeta, fs)
    out = np.empty_like(u)
    for i in range(u.shape[0]):
        out[i] = lfilter(b[i], a[i], u[i])
    return out


def render_modes_reference(
    u: NDArray[np.float64],
    omega: NDArray[np.float64],
    zeta: NDArray[np.float64],
    fs: float,
) -> NDArray[np.float64]:
    """Exact per-sample state propagation (reference for the lfilter path).

    State (q, q̇) per mode; each sample: q̇ += u[n]; emit q̇; free-decay one T
    via the exact damped-SDOF propagator
        A = r · [[cosθ + c sinθ,  sinθ/ω_d],
                 [−(ω²/ω_d) sinθ, cosθ − c sinθ]]
    (closed-form solution of Eq. 8 with r_i = 0 over one sample).
    """
    u = np.asarray(u, dtype=np.float64)
    omega = np.asarray(omega, dtype=np.float64)
    zc = np.clip(np.asarray(zeta, dtype=np.float64), 0.0, 0.999999)
    T = 1.0 / float(fs)
    omega_d = omega * np.sqrt(1.0 - zc ** 2)
    r = np.exp(-zc * omega * T)
    th = omega_d * T
    c = zc * omega / np.maximum(omega_d, 1e-30)
    a11 = r * (np.cos(th) + c * np.sin(th))
    a12 = r * np.sin(th) / np.maximum(omega_d, 1e-30)
    a21 = -r * (omega ** 2 / np.maximum(omega_d, 1e-30)) * np.sin(th)
    a22 = r * (np.cos(th) - c * np.sin(th))

    n_modes, n_samp = u.shape
    q = np.zeros(n_modes, dtype=np.float64)
    qd = np.zeros(n_modes, dtype=np.float64)
    out = np.empty_like(u)
    for n in range(n_samp):
        qd = qd + u[:, n]
        out[:, n] = qd
        q, qd = a11 * q + a12 * qd, a21 * q + a22 * qd
    return out


def mix_modes(
    qdot_tracks: NDArray[np.float64],
    weight: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Listening mix Σ_i w_i q̇_i(t) → (N,). Weights are the radiation
    heuristic from the basis (audio_basis DEVIATION note)."""
    return np.asarray(weight, dtype=np.float64) @ np.asarray(
        qdot_tracks, dtype=np.float64)
