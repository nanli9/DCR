#!/usr/bin/env python3
"""Impulse-port V0 validation suite + sweep figures.

Validates the load-bearing bet of the two-band modal architecture: a passive
velocity-band impulse exchanging momentum between a rigid body and the ring is
bounded and dissipative where stiff position-glue against the same kHz ring
rectifies / pumps (the real solver launched a book 1.1 m at iters=32).

Prints a PASS/FAIL report over the assert list and writes two figures to docs/:
  impulse_port_v0_sweep.png    — before/after: velocity bounded vs position
                                  pathology, over iters and substeps.
  impulse_port_v0_chatter.png  — sampled vs integrated ring velocity (corr. 5).

    uv run python scripts/run_impulse_port_v0.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from dcr.dcr.impulse_port_v0 import V0Config, run

DOCS = ROOT / "docs"
PRE = np.array([0.5, 0.4, 0.3, 0.2])     # ring pre-excitation (q̇_d kick)


def _ok(cond: bool) -> str:
    return "PASS" if cond else "**FAIL**"


def report() -> bool:
    """Core asserts on the rigorous (sampled) variant. Returns all-passed."""
    print("=" * 72)
    print("V0 core asserts — sampled variant (the rigorous coupled impulse)")
    print("=" * 72)
    allp = True
    cases = {
        "drop (gravity, impact excites ring)": dict(N=360),
        "pre-excited ring (body resting)": dict(N=360, y0=0.0, qddot0=PRE.copy()),
    }
    for tag, kw in cases.items():
        r = run(V0Config(coupling="velocity", ring_vel="sampled", **kw))
        checks = {
            "λ ≥ 0 never pulls (e=0)": r.pull_violations == 0,
            "ġ⁺ = −e·ġ⁻ resolution exact": r.resolve_residual_max < 1e-12,
            "ΔE_modal = αb+½α²a exact": r.ledger_residual_max < 1e-12,
            "§15 invariant ΣΔE_mod ≤ ηΣΔE_rig": r.invariant_margin_min > -1e-9,
            "governor never clamps (η=1)": r.clamp_activations == 0,
            "body settles (late std < 1µm)": r.y[-20:].std() < 1e-6,
            "impulses vanish post-transient": r.lam_max_per_step[-40:].max() < 1e-9,
        }
        print(f"\n  [{tag}]")
        for name, c in checks.items():
            allp &= c
            print(f"    {_ok(c):9s} {name}")
        print(f"    (peak body {r.y.max()*1e3:.3f} mm, ring decay "
              f"{r.qd_norm[-1]/max(r.qd_norm.max(),1e-30):.1e})")
    return allp


def sweep():
    """Before/after over iters and substeps. Returns arrays for the figure."""
    iters_list = [4, 8, 16, 32, 64]
    subs_list = [8, 16, 32, 64, 96]
    out = dict(iters=iters_list, subs=subs_list,
               vel_it_peak=[], vel_it_fin=[], pos_it_peak=[], pos_it_fin=[],
               pos_it_ring=[], vel_it_ring=[],
               vel_sb_peak=[], vel_sb_fin=[], pos_sb_peak=[], pos_sb_fin=[])
    for it in iters_list:
        rv = run(V0Config(coupling="velocity", ring_vel="sampled", iters=it,
                          substeps=8, N=300, y0=0.0, qddot0=PRE.copy()))
        rp = run(V0Config(coupling="position", iters=it, substeps=8, N=300,
                          y0=0.0, qddot0=PRE.copy()))
        out["vel_it_peak"].append(rv.y.max() * 1e3)
        out["vel_it_fin"].append(abs(rv.y[-1]) * 1e3)
        out["vel_it_ring"].append(rv.qd_norm[-1])
        out["pos_it_peak"].append(rp.y.max() * 1e3)
        out["pos_it_fin"].append(abs(rp.y[-1]) * 1e3)
        out["pos_it_ring"].append(rp.qd_norm[-1])
    for sb in subs_list:
        rv = run(V0Config(coupling="velocity", ring_vel="sampled", iters=4,
                          substeps=sb, N=300, y0=0.0, qddot0=PRE.copy()))
        rp = run(V0Config(coupling="position", iters=4, substeps=sb, N=300,
                          y0=0.0, qddot0=PRE.copy()))
        out["vel_sb_peak"].append(rv.y.max() * 1e3)
        out["vel_sb_fin"].append(abs(rv.y[-1]) * 1e3)
        out["pos_sb_peak"].append(rp.y.max() * 1e3)
        out["pos_sb_fin"].append(abs(rp.y[-1]) * 1e3)
    return out


def chatter():
    """Sampled vs integrated ring velocity, peak body hop vs substep rate
    (correction 5: integrated should be quieter). Also report §15 margin."""
    subs_list = [8, 16, 32, 64, 96, 192]
    rows = []
    for sb in subs_list:
        rec = {"sub": sb, "rate_hz": sb / (1.0 / 120.0)}
        for rv_mode in ("sampled", "integrated"):
            r = run(V0Config(coupling="velocity", ring_vel=rv_mode, iters=4,
                             substeps=sb, N=300, y0=0.0, qddot0=PRE.copy()))
            rec[f"{rv_mode}_peak"] = r.y.max() * 1e3
            rec[f"{rv_mode}_inv"] = r.invariant_margin_min
        rows.append(rec)
    return subs_list, rows


def make_figures(sw, subs_list, ch_rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"\n[plot] matplotlib unavailable ({e}); skipping figures.")
        return
    DOCS.mkdir(exist_ok=True)

    # Figure 1: before/after sweep.
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].plot(sw["iters"], sw["vel_it_fin"], "o-", label="velocity band (settle)")
    ax[0].plot(sw["iters"], sw["pos_it_fin"], "s--", label="position glue (stuck offset)")
    ax[0].set_xlabel("solver iterations"); ax[0].set_ylabel("body final |offset| [mm]")
    ax[0].set_title("Rectification vs iterations (sub=8)"); ax[0].legend()
    ax[0].grid(alpha=0.3)
    ax[1].plot(sw["subs"], sw["vel_sb_fin"], "o-", label="velocity band (settle)")
    ax[1].plot(sw["subs"], sw["pos_sb_fin"], "s--", label="position glue (stuck offset)")
    ax[1].set_xlabel("substeps / step"); ax[1].set_ylabel("body final |offset| [mm]")
    ax[1].set_title("Rectification vs substeps (iters=4)"); ax[1].legend()
    ax[1].grid(alpha=0.3)
    fig.suptitle("Impulse-port V0: velocity band settles to ~0; position glue "
                 "leaves a stuck, substep-dependent offset")
    fig.tight_layout()
    p1 = DOCS / "impulse_port_v0_sweep.png"
    fig.savefig(p1, dpi=110); plt.close(fig)

    # Figure 2: chatter (peak hop vs substep rate).
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    rates = [r["rate_hz"] for r in ch_rows]
    ax.plot(rates, [r["sampled_peak"] for r in ch_rows], "o-", label="sampled q̇_d")
    ax.plot(rates, [r["integrated_peak"] for r in ch_rows], "s-",
            label="integrated (substep-mean) q̇_d")
    ax.set_xlabel("contact sampling rate [Hz]  (substeps × 120)")
    ax.set_ylabel("peak body hop [mm]")
    ax.set_title("Chatter vs sampling rate (modes to 9 kHz; aliased)")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    p2 = DOCS / "impulse_port_v0_chatter.png"
    fig.savefig(p2, dpi=110); plt.close(fig)
    print(f"\n[plot] wrote {p1.relative_to(ROOT)} and {p2.relative_to(ROOT)}")


def main() -> int:
    allp = report()

    print("\n" + "=" * 72)
    print("Blow-up/rectification sweep mirror (pre-excited ring, body resting)")
    print("=" * 72)
    sw = sweep()
    print("  iters (sub=8) | velocity final/peak [mm] | position final/peak [mm] (ring_f)")
    for i, it in enumerate(sw["iters"]):
        print(f"    iters={it:3d}    | {sw['vel_it_fin'][i]:7.4f}/{sw['vel_it_peak'][i]:6.2f}"
              f"        | {sw['pos_it_fin'][i]:8.2f}/{sw['pos_it_peak'][i]:6.2f}  "
              f"(ring {sw['pos_it_ring'][i]:.1e} vs {sw['vel_it_ring'][i]:.0e})")
    print("  subs (iters=4)| velocity final/peak [mm] | position final/peak [mm]")
    for i, sb in enumerate(sw["subs"]):
        print(f"    sub={sb:3d}     | {sw['vel_sb_fin'][i]:7.4f}/{sw['vel_sb_peak'][i]:6.2f}"
              f"        | {sw['pos_sb_fin'][i]:8.2f}/{sw['pos_sb_peak'][i]:6.2f}")

    print("\n" + "=" * 72)
    print("Chatter: sampled vs integrated ring velocity (correction 5)")
    print("=" * 72)
    subs_list, ch_rows = chatter()
    print(f"  {'rate[Hz]':>9} {'sampled peak':>13} {'integ peak':>11} "
          f"{'sampled §15':>12} {'integ §15':>11}")
    for r in ch_rows:
        print(f"  {r['rate_hz']:9.0f} {r['sampled_peak']:13.3f} {r['integrated_peak']:11.3f} "
              f"{r['sampled_inv']:12.2e} {r['integrated_inv']:11.2e}")
    s_mean = np.mean([r["sampled_peak"] for r in ch_rows])
    i_mean = np.mean([r["integrated_peak"] for r in ch_rows])
    print(f"  → mean peak hop: sampled={s_mean:.3f} mm, integrated={i_mean:.3f} mm "
          f"→ quieter: {'integrated' if i_mean < s_mean else 'sampled'}")
    print(f"  → §15 margin: sampled always ≥0 (rigorous); integrated min="
          f"{min(r['integrated_inv'] for r in ch_rows):.2e} "
          f"(slack from past-mean vs present-instant mismatch — documented)")

    make_figures(sw, subs_list, ch_rows)

    print("\n" + "=" * 72)
    print(f"V0 CORE ASSERTS: {'ALL PASS' if allp else 'FAILURES PRESENT'}")
    print("=" * 72)
    return 0 if allp else 1


if __name__ == "__main__":
    raise SystemExit(main())
