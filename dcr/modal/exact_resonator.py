"""Exact one-step damped-oscillator response (paper Eq. 10 in state-space form).

Two equivalent precompute routines are provided:

  1. `exact_modal_step_precompute(q, qdot, omega, zeta, mass, h)`
     Per-mode closed form. Assumes the reduced (Mq, Kq, Dq) matrices are
     diagonal in the active basis (i.e. the basis IS the eigenbasis). Used
     by isolated-oscillator unit tests and any future single-mode work.

  2. `dynamic_compliance_step_precompute(q, qdot, Mq, Kq, Dq, h)`
     Full r×r dynamic compliance via a (3r × 3r) augmented matrix
     exponential. Handles non-diagonal Mq, Kq, Dq natively. Used by the
     coupled AVBD IIR branch (`ReducedCoupledAVBDCoupler`) because the
     synthetic plate basis is NOT in the eigenbasis (off-diagonal Mq
     ~30% of the full norm), so the per-mode formulas would alias modes.

Mathematics (foundation: state-space form of Eq. 8 with constant F over h):

    [q̇; q̈] = A · [q; q̇] + B · F
        A = [[0, I], [-M⁻¹K, -M⁻¹D]]   (2r × 2r)
        B = [[0], [M⁻¹]]               (2r × r)

For F constant over [0, h]:

    [q(h); q̇(h)] = exp(A·h) · [q(0); q̇(0)] + Φ_h · B · F
    Φ_h           = ∫₀ʰ exp(A·s) ds                              (2r × 2r)

The augmented exp trick (Van Loan 1978) computes this in one shot:

    Aug = [[A, B], [0, 0]]                                       (3r × 3r)
    exp(Aug·h) = [[exp(A·h), Φ_h·B], [0, I_r]]

so

    A_d = exp(Aug·h)[:2r, :2r]   (state transition)
    M_d = exp(Aug·h)[:2r, 2r:]   (force compliance, 2r × r)
        = [S_h ; T_h]  stacked vertically (each r × r)

The split:
    q(h)   = A_d[:r, :r]·q  + A_d[:r, r:]·q̇   +  S_h · F   ≡ q_free + S_h·F
    q̇(h)  = A_d[r:, :r]·q  + A_d[r:, r:]·q̇   +  T_h · F   ≡ q̇_free + T_h·F

The AVBD modal cost is then

    ½ (q − q_free)ᵀ · S_h⁻¹ · (q − q_free)

with gradient `S_h⁻¹·(q − q_free)` and Hessian `S_h⁻¹` — both dense r × r
matrices (when modes are coupled inertially). After AVBD converges,

    F        = S_h⁻¹ · (q_{n+1} − q_free)
    q̇_{n+1} = q̇_free + T_h · F

is the exact analytical response to the implied per-substep force.

For underdamped modes in the per-mode form, the closed form is:

    a_i      = ζ_i · ω_i
    ω_d_i    = ω_i · √(1 − ζ_i²)
    E_i      = exp(−a_i · h)
    c_i      = cos(ω_d_i · h)
    s_i      = sin(ω_d_i · h)
    k_i      = m_i · ω_i²

    q_free_i    = E_i · [ (c_i + (a_i/ω_d_i)·s_i)·q_n + (s_i/ω_d_i)·q̇_n ]
    q̇_free_i   = E_i · [ −(ω_i²/ω_d_i)·s_i·q_n + (c_i − (a_i/ω_d_i)·s_i)·q̇_n ]
    S_i(h)      = (1 − E_i·(c_i + (a_i/ω_d_i)·s_i)) / k_i
    T_i(h)      = E_i · s_i / (m_i · ω_d_i)

Defensive branches handle critical-damped (ζ ≈ 1), overdamped (ζ > 1),
and the rigid limit (ω·h → 0). For this repo's Rayleigh damping the
underdamped branch covers all relevant modes/substeps.
"""
from __future__ import annotations

import warnings

import numpy as np
from numpy.typing import NDArray


def exact_modal_step_precompute(
    q:     NDArray[np.float64],
    qdot:  NDArray[np.float64],
    omega: NDArray[np.float64],
    zeta:  NDArray[np.float64],
    mass:  NDArray[np.float64],
    h:     float,
) -> tuple[NDArray[np.float64], NDArray[np.float64],
           NDArray[np.float64], NDArray[np.float64]]:
    """Precompute (q_free, qdot_free, S, T) per mode for one substep.

    Inputs (all shape (r,)):
        q, qdot     — state at t_n
        omega, zeta — modal frequency (rad/s) and damping ratio
        mass        — per-mode mass (= diag(M_q) in the modal eigenbasis)
    Input h: substep duration (s).

    Returns four (r,) arrays. The exact-resonator AVBD update then uses:
        q_{n+1}    = q_free + S · F
        qdot_{n+1} = qdot_free + T · F
    where F is the constant per-mode force over [0, h] (recovered from
    the AVBD-converged q_{n+1} at substep_end).
    """
    q     = np.asarray(q,     dtype=np.float64)
    qdot  = np.asarray(qdot,  dtype=np.float64)
    omega = np.asarray(omega, dtype=np.float64)
    zeta  = np.asarray(zeta,  dtype=np.float64)
    mass  = np.asarray(mass,  dtype=np.float64)
    h     = float(h)

    r = q.shape[0]
    if not (qdot.shape == omega.shape == zeta.shape == mass.shape == q.shape):
        raise ValueError(
            f"Shape mismatch: q={q.shape}, qdot={qdot.shape}, "
            f"omega={omega.shape}, zeta={zeta.shape}, mass={mass.shape}")
    if h <= 0.0:
        raise ValueError(f"h must be positive, got {h}")

    # P0 (perf): vectorized over modes. Five branches (frozen, rigid,
    # critical, over, under) are computed in parallel and selected via
    # np.where. Math is bit-identical to the per-mode loop in the normal
    # underdamped path; the only cost is that unused branches are also
    # computed then discarded. For r ≤ 20 this is much faster than the
    # Python for-loop because each np.exp/cos/sin call has ~1–3 µs of
    # dispatch overhead that doesn't amortize at small r.
    safe_mass  = np.where(mass > 0.0, mass, 1.0)
    safe_omega = np.where(omega > 1.0e-12, omega, 1.0)

    frozen = ~(np.isfinite(mass) & (mass > 0.0))
    rigid  = (~frozen) & ((omega * h < 1.0e-6) | (omega < 1.0e-12))
    crit   = (~frozen) & (~rigid) & (np.abs(zeta - 1.0) < 1.0e-6)
    over   = (~frozen) & (~rigid) & (~crit) & (zeta > 1.0)
    # under = remaining; not materialized — used only as fall-through.

    ai      = zeta * safe_omega
    ki      = safe_mass * safe_omega * safe_omega
    safe_ki = np.maximum(ki, 1.0e-40)
    E       = np.exp(-ai * h)

    # ---- Underdamped (hot path).  0 ≤ ζ < 1 − 1e-6 ----
    wd_u  = safe_omega * np.sqrt(np.maximum(1.0 - zeta * zeta, 1.0e-30))
    c_u   = np.cos(wd_u * h)
    s_u   = np.sin(wd_u * h)
    aow_u = ai / wd_u
    qf_u  = E * ((c_u + aow_u * s_u) * q + (s_u / wd_u) * qdot)
    qdf_u = E * (-(safe_omega * safe_omega / wd_u) * s_u * q
                  + (c_u - aow_u * s_u) * qdot)
    S_u   = (1.0 - E * (c_u + aow_u * s_u)) / safe_ki
    T_u   = E * s_u / (safe_mass * wd_u)

    # ---- Critical-damped: |ζ − 1| < 1e-6 ----
    wh    = safe_omega * h
    qf_c  = E * ((1.0 + wh) * q + h * qdot)
    qdf_c = E * (-(safe_omega * safe_omega) * h * q + (1.0 - wh) * qdot)
    S_c   = (1.0 - E * (1.0 + wh)) / safe_ki
    T_c   = E * h / safe_mass

    # ---- Overdamped: ζ > 1 ----
    wd_o  = safe_omega * np.sqrt(np.maximum(zeta * zeta - 1.0, 1.0e-30))
    ch_o  = np.cosh(wd_o * h)
    sh_o  = np.sinh(wd_o * h)
    aow_o = ai / wd_o
    qf_o  = E * ((ch_o + aow_o * sh_o) * q + (sh_o / wd_o) * qdot)
    qdf_o = E * (-(safe_omega * safe_omega / wd_o) * sh_o * q
                  + (ch_o - aow_o * sh_o) * qdot)
    S_o   = (1.0 - E * (ch_o + aow_o * sh_o)) / safe_ki
    T_o   = E * sh_o / (safe_mass * wd_o)

    # ---- Rigid limit: ω·h ≪ 1 ----
    # DEVIATION: damped-oscillator formulas are numerically unstable as
    # ω·h → 0; switch to pure-inertia integration with constant F.
    qf_r  = q + h * qdot
    qdf_r = qdot
    S_r   = np.full_like(omega, h * h) / (2.0 * safe_mass)
    T_r   = np.full_like(omega, h) / safe_mass

    # ---- Frozen: non-finite or non-positive mass ----
    S_fr  = np.full_like(omega, 1.0e-18)
    T_fr  = np.zeros_like(omega)

    # Branch select via stacked np.where (under = fall-through).
    q_free    = np.where(frozen, q,
                np.where(rigid, qf_r,
                np.where(crit,  qf_c,
                np.where(over,  qf_o, qf_u))))
    qdot_free = np.where(frozen, qdot,
                np.where(rigid, qdf_r,
                np.where(crit,  qdf_c,
                np.where(over,  qdf_o, qdf_u))))
    S         = np.where(frozen, S_fr,
                np.where(rigid, S_r,
                np.where(crit,  S_c,
                np.where(over,  S_o, S_u))))
    T         = np.where(frozen, T_fr,
                np.where(rigid, T_r,
                np.where(crit,  T_c,
                np.where(over,  T_o, T_u))))

    # ---- Floor S to avoid Hessian blow-up ----
    # # DEVIATION: 1/S enters H_qq's diagonal. If S_i underflows the
    # modal Hessian loses PSD-ness. Clamp at a machine-safe minimum and
    # warn. Triggers only on pathological (ω·h huge AND overdamped) modes.
    too_small = S < 1.0e-18
    if np.any(too_small):
        warnings.warn(
            f"exact_modal_step_precompute: {int(np.sum(too_small))} mode(s) "
            f"have S_i < 1e-18; clamping to 1e-18 to keep H_qq PSD.",
            stacklevel=2)
    S = np.maximum(S, 1.0e-18)

    return q_free, qdot_free, S, T


def per_mode_params_from_diag(
    Mq: NDArray[np.float64],
    Kq: NDArray[np.float64],
    Dq: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Extract per-mode (mass, omega, zeta) from the diagonal of the
    reduced (Mq, Kq, Dq) matrices.

    Assumes the basis is in eigenbasis (so Mq, Kq, Dq are diagonal up to
    numerical noise — the caller is responsible for the diag-check). Uses
    the diagonal entries:
        m_i = Mq[i, i]
        ω_i = sqrt(Kq[i, i] / Mq[i, i])
        ζ_i = Dq[i, i] / (2 · m_i · ω_i)

    Returns (mass, omega, zeta) each shape (r,). ζ is clamped to
    [0, 0.9999] to keep the underdamped branch healthy by default.
    """
    Mq = np.asarray(Mq, dtype=np.float64)
    Kq = np.asarray(Kq, dtype=np.float64)
    Dq = np.asarray(Dq, dtype=np.float64)
    r = Mq.shape[0]
    if Mq.shape != (r, r) or Kq.shape != (r, r) or Dq.shape != (r, r):
        raise ValueError(f"Mq/Kq/Dq must be (r,r); got {Mq.shape}, "
                         f"{Kq.shape}, {Dq.shape}")

    mass  = np.diag(Mq).astype(np.float64).copy()
    kdiag = np.diag(Kq).astype(np.float64)
    ddiag = np.diag(Dq).astype(np.float64)
    # Safe division: zero-mass DoFs map to ω = 0, which the precompute
    # routes through the rigid limit anyway.
    mass_safe = np.where(mass > 1.0e-30, mass, 1.0e-30)
    omega2 = np.maximum(kdiag / mass_safe, 0.0)
    omega = np.sqrt(omega2)
    omega_safe = np.where(omega > 1.0e-12, omega, 1.0)
    zeta = ddiag / (2.0 * mass_safe * omega_safe)
    zeta = np.clip(zeta, 0.0, 0.9999)
    return mass, omega, zeta


# ---------------------------------------------------------------------------
# Full r × r dynamic compliance (matrix-exponential form)
# ---------------------------------------------------------------------------

def dynamic_compliance_step_precompute(
    q:    NDArray[np.float64],
    qdot: NDArray[np.float64],
    Mq:   NDArray[np.float64],
    Kq:   NDArray[np.float64],
    Dq:   NDArray[np.float64],
    h:    float,
) -> tuple[NDArray[np.float64], NDArray[np.float64],
           NDArray[np.float64], NDArray[np.float64]]:
    """Full r × r exact step via the augmented matrix exponential.

    Handles arbitrary (PSD) Mq, Kq, Dq — no diagonality assumption.
    Used by the coupled AVBD IIR branch when the basis is not in the
    eigenbasis (e.g. the synthetic plate-bending + Gaussian-bump basis,
    where the bump and bending modes have non-zero Mq cross-terms).

    Inputs:
        q, qdot    shape (r,)
        Mq, Kq, Dq shape (r, r); Mq must be invertible PD.
        h          substep duration (s), > 0.

    Returns (q_free, qdot_free, S_h, T_h):
        q_free    (r,)    free response position at t = h
        qdot_free (r,)    free response velocity at t = h
        S_h       (r, r)  displacement compliance: q = q_free + S_h · F
        T_h       (r, r)  velocity force gain:    q̇ = q̇_free + T_h · F
    """
    # scipy.linalg.expm is exposed lazily so the per-mode path stays
    # numpy-only (and importable from tests that skip scipy).
    from scipy.linalg import expm

    q   = np.asarray(q,   dtype=np.float64)
    qd  = np.asarray(qdot, dtype=np.float64)
    Mq  = np.asarray(Mq,  dtype=np.float64)
    Kq  = np.asarray(Kq,  dtype=np.float64)
    Dq  = np.asarray(Dq,  dtype=np.float64)
    h   = float(h)
    r   = q.shape[0]

    if not (Mq.shape == Kq.shape == Dq.shape == (r, r)):
        raise ValueError(
            f"Mq/Kq/Dq must be (r,r) with r={r}; got "
            f"{Mq.shape}, {Kq.shape}, {Dq.shape}")
    if h <= 0.0:
        raise ValueError(f"h must be positive, got {h}")

    # Solve once for M⁻¹·K, M⁻¹·D, M⁻¹.
    M_inv_K = np.linalg.solve(Mq, Kq)
    M_inv_D = np.linalg.solve(Mq, Dq)
    M_inv   = np.linalg.solve(Mq, np.eye(r, dtype=np.float64))

    # Augmented matrix:
    #   Aug = [[ 0,  I,  0   ],
    #          [-M⁻¹K, -M⁻¹D, M⁻¹],
    #          [ 0,  0,  0   ]]
    # Size (3r, 3r). exp(Aug·h) yields the state transition + compliance.
    Aug = np.zeros((3 * r, 3 * r), dtype=np.float64)
    Aug[:r, r:2 * r]      = np.eye(r, dtype=np.float64)
    Aug[r:2 * r, :r]      = -M_inv_K
    Aug[r:2 * r, r:2 * r] = -M_inv_D
    Aug[r:2 * r, 2 * r:]  = M_inv

    E = expm(Aug * h)                                              # (3r, 3r)

    A_d  = E[:2 * r, :2 * r]                                       # (2r, 2r)
    MB   = E[:2 * r, 2 * r:]                                       # (2r, r)
    S_h  = MB[:r, :]                                               # (r, r)
    T_h  = MB[r:, :]                                               # (r, r)

    q_free    = A_d[:r,    :r] @ q + A_d[:r,    r:] @ qd
    qdot_free = A_d[r:2*r, :r] @ q + A_d[r:2*r, r:] @ qd

    return q_free, qdot_free, S_h, T_h
