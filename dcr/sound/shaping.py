"""Excitation shaping (Stage E6 demo): Hertzian contact-duration mapping and
fractional-delay half-sine impulse kernels.

The single biggest audio-quality lever: a raw delta excites all modes equally
(white click); a real impact delivers its impulse over a finite Hertzian
contact time τ, low-passing the excitation. Hertz theory gives τ ∝ v^(−1/5)
(Hertz 1882; Johnson, *Contact Mechanics* §11.4) — faster/harder impacts are
shorter, hence brighter.

# DEVIATION (Hertz): the full Hertz constant depends on E*, R, m of the pair;
# we lump it into a per-render reference (τ_ref at v_ref) and keep only the
# v^(−1/5) exponent. Render-side plausibility choice, disclosed in docs/stageE6.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def hertz_tau(
    v_impact: float,
    *,
    tau_ref: float = 8.0e-4,
    v_ref: float = 1.0,
    exponent: float = 0.2,
    tau_min: float = 1.5e-4,
    tau_max: float = 4.0e-3,
) -> float:
    """Contact duration τ(v) = clip(τ_ref · (v_ref / |v|)^exponent).

    exponent = 0.2 is the Hertz v^(−1/5) law; τ_ref is the lumped material/
    geometry constant (see module DEVIATION).
    """
    v = max(abs(float(v_impact)), 1e-3)
    tau = float(tau_ref) * (float(v_ref) / v) ** float(exponent)
    return float(np.clip(tau, tau_min, tau_max))


def half_sine_spectrum(
    omega: NDArray[np.float64],
    tau: float,
) -> NDArray[np.float64]:
    """Magnitude response |Ĥ(ω)| of the unit-impulse half-sine burst of
    duration τ (normalized so |Ĥ(0)| = 1):

        |Ĥ(ω)| = π² |cos(ωτ/2)| / |π² − (ωτ)²|,   |Ĥ| → π/4 at ωτ = π.

    This is the shaping's physical low-pass: a mode with period ≪ τ receives
    almost none of the kick (within-burst cancellation). The E6 ledger uses it
    so the admitted energy equals what the bank actually realizes — admitting
    the raw ½‖g‖² would overcount energy the shaped pulse never delivers.
    """
    x = np.asarray(omega, dtype=np.float64) * float(tau)
    denom = np.pi ** 2 - x ** 2
    near = np.abs(denom) < 1e-6
    safe = np.where(near, 1.0, denom)
    h = np.where(near, np.pi / 4.0,
                 np.pi ** 2 * np.abs(np.cos(x / 2.0)) / np.abs(safe))
    return np.clip(h, 0.0, 1.0)


def impulse_kernel(
    t_event: float,
    tau: float,
    fs: float,
) -> tuple[int, NDArray[np.float64]]:
    """Distribute a unit impulse as a half-sine force burst of duration τ
    starting at continuous time `t_event`, sampled at `fs`.

    Returns (start_sample, weights) with Σ weights = 1 exactly (the impulse
    magnitude is conserved; tests assert this), placed with fractional delay —
    the burst starts at the true continuous event time, not snapped to the
    sample grid (kills the substep-grid comb in dense rattles).

    Degenerate τ·fs < 1 falls back to a two-sample linear split (the standard
    fractional-delay delta).
    """
    p = float(t_event) * float(fs)          # continuous sample position
    k0 = int(np.floor(p))
    frac = p - k0
    span = float(tau) * float(fs)
    if span < 1.0:
        w = np.array([1.0 - frac, frac], dtype=np.float64)
        return k0, w
    n = int(np.ceil(span)) + 1
    # Sample s = k0 + j sits at phase u_j = (k0 + j − p) / span ∈ [0, 1].
    j = np.arange(n + 1, dtype=np.float64)
    u = (j - frac) / span
    w = np.where((u >= 0.0) & (u <= 1.0), np.sin(np.pi * np.clip(u, 0, 1)), 0.0)
    total = float(np.sum(w))
    if total <= 0.0:                        # pathological: fall back to delta
        w = np.zeros(2, dtype=np.float64)
        w[0], w[1] = 1.0 - frac, frac
        return k0, w
    return k0, w / total
