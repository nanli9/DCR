#!/usr/bin/env python3
"""V1 demo — the reservoir-exact governor closes the η<1 per-prefix slack.

A controlled sequence of velocity-band impulses (each summarised by its §15
modal quadratic `a_m=‖s‖², b_m=q̇·s` and its rigid-loss quadratic `L(α)=l1 α+
l2 α²`) is fed through TWO governors at η<1:

  • per_impulse — the V0 cap: budget `E_max = η·L(α=1)` sized at the FULL
    impulse, then scale by α. When it clamps, the realized loss `L(α) < L(1)`,
    so the cumulative §15 margin `η Σ L − Σ ΔE_modal` can dip NEGATIVE.
  • reservoir   — V1 (`reservoir_alpha`): a persistent `R ≥ 0` and the net draw
    `D(α)=ΔE_modal(α) − η L(α) ≤ R`. The margin IS the reservoir, so it never
    goes negative — the per-prefix bound is exact for any η.

Output: docs/impulse_port_v1_reservoir.png (foundation §1/§6/§15).

    uv run python scripts/run_impulse_port_v1.py
"""
from __future__ import annotations

import numpy as np

from dcr.modal.passive_inject import reservoir_alpha, reservoir_draw


def _per_impulse_alpha(a_m, b_m, l1, l2, eta):
    """V0 per-impulse cap: ΔE_modal(α) ≤ η·L(α=1)."""
    E_max = eta * max(0.0, l1 + l2)
    if a_m < 1e-18:
        return 0.0
    if b_m + 0.5 * a_m <= E_max:
        return 1.0
    disc = b_m * b_m + 2.0 * a_m * E_max
    return float(np.clip((-b_m + np.sqrt(max(0.0, disc))) / a_m, 0.0, 1.0))


def _sequence(n=120, seed=7):
    """A body resting on an excited ring (the regime that exposes the slack):
    mostly small-loss INJECTING impulses (the ring pumps energy into the body
    with little rigid loss to fund it), with the occasional real impact that
    banks loss. With injecting impulses leading, the per-impulse cap's realized
    loss `L(α)` falls short of its `L(1)` budget, so its cumulative margin
    ratchets negative; the reservoir refuses to spend budget it hasn't banked."""
    rng = np.random.default_rng(seed)
    seq = []
    for k in range(n):
        impact = (k % 25 == 0 and k > 0)            # rare, banks real loss
        if impact:
            lam0 = rng.uniform(0.6, 1.2)
            v_c = -rng.uniform(1.0, 2.0)            # strong closing → big loss
            b_m = rng.uniform(-0.1, 0.1)
        else:
            lam0 = rng.uniform(0.05, 0.22)          # light resting contact
            v_c = rng.uniform(-0.03, 0.0)           # ~ zero closing → tiny loss
            b_m = rng.uniform(0.05, 0.40)           # injecting (ring pumps in)
        Uy2 = rng.uniform(0.3, 0.9)
        a_m = lam0 * lam0 * Uy2
        w_r = 1.0
        l1 = -v_c * lam0
        l2 = -0.5 * w_r * lam0 * lam0
        seq.append((a_m, b_m, l1, l2))
    return seq


def _ledger(seq, eta, mode):
    """Run a governor over the sequence; return per-prefix margin + reservoir."""
    cumL = 0.0
    cum_modal = 0.0
    R = 0.0
    margins = []
    reservoirs = []
    for (a_m, b_m, l1, l2) in seq:
        if mode == "reservoir":
            alpha = reservoir_alpha(a_m, b_m, l1, l2, R, eta)
            R -= reservoir_draw(a_m, b_m, l1, l2, alpha, eta)
        else:
            alpha = _per_impulse_alpha(a_m, b_m, l1, l2, eta)
        dE_modal = b_m * alpha + 0.5 * a_m * alpha * alpha
        L = l1 * alpha + l2 * alpha * alpha
        cumL += L
        cum_modal += dE_modal
        margins.append(eta * cumL - cum_modal)
        reservoirs.append(R)
    return np.array(margins), np.array(reservoirs)


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    eta = 0.3
    seq = _sequence()
    m_pi, _ = _ledger(seq, eta, "per_impulse")
    m_rv, R_rv = _ledger(seq, eta, "reservoir")
    x = np.arange(len(seq))

    fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    ax[0].axhline(0.0, color="k", lw=0.8)
    ax[0].plot(x, m_pi, color="#c0392b", lw=1.6,
               label="per_impulse (V0) — DIPS < 0 (slack)")
    ax[0].plot(x, m_rv, color="#27ae60", lw=1.6,
               label="reservoir (V1) — stays ≥ 0 (exact)")
    ax[0].fill_between(x, m_pi, 0.0, where=(m_pi < 0), color="#c0392b", alpha=0.18)
    ax[0].set_ylabel("per-prefix §15 margin\nη·Σ L − Σ ΔE_modal")
    ax[0].set_title(f"V1 reservoir-exact governor closes the η<1 slack  (η = {eta})")
    ax[0].legend(loc="upper right", fontsize=9)
    ax[0].grid(alpha=0.25)

    ax[1].axhline(0.0, color="k", lw=0.8)
    ax[1].plot(x, R_rv, color="#2980b9", lw=1.6, label="reservoir R (V1)")
    ax[1].set_ylabel("reservoir R  (= V1 margin)")
    ax[1].set_xlabel("impulse #")
    ax[1].legend(loc="upper right", fontsize=9)
    ax[1].grid(alpha=0.25)

    out = "docs/impulse_port_v1_reservoir.png"
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f"min per-prefix margin: per_impulse = {m_pi.min():.4e}  "
          f"reservoir = {m_rv.min():.4e}")
    print(f"reservoir R min = {R_rv.min():.4e}  (must be ≥ 0)")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
