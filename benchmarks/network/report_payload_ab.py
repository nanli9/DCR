#!/usr/bin/env python3
"""Payload mass-loading A/B — evidence figure for docs/07_17_report/.

Runs the two payload-plate worlds (scenes/payload_plate.py) exactly as the
viser `--scene payload` demo does — same builder defaults, same symplectic
modal step — and plots what the live demo shows, so the meeting has a static
backup if the live run isn't possible:

  (a) plate deflection at the payload point: pre-impact sag, then the ring —
      detuned + damped on the two-way side, free on the one-way side;
  (b) payload height: the two-way payload rides/rattles, the one-way payload
      never moves (its plate never learns it exists).

Analysis only — no solver code touched. Writes payload_ab.png + prints the
headline numbers. Run: .venv/bin/python benchmarks/network/report_payload_ab.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "benchmarks", "paper_fig"))

from figstyle import PALETTE, apply_style          # repo-wide Okabe-Ito arms
import matplotlib.pyplot as plt

from scenes.payload_plate import build_payload_plate_scene

OUT = os.path.join(_ROOT, "docs", "07_17_report")
FS = 120.0
T_END = 4.0
N = int(T_END * FS)

C_TWO = PALETTE["native"]   # blue  — two-way (the native constraint arm)
C_ONE = PALETTE["dcr"]      # orange — one-way (the readout arm)


def run(coupled: bool):
    h = build_payload_plate_scene(coupled=coupled)
    s = h.world._solver
    # the viser demo's default modal integrator (symplectic host q-block)
    if hasattr(s, "_modal_device_resident"):
        s._modal_device_resident = False
    if hasattr(s, "_modal_symplectic"):
        s._modal_symplectic = True
    ip, ii = h.avbd_idx["payload"], h.avbd_idx["impactor"]
    d = np.zeros(N); yp = np.zeros(N); yi = np.zeros(N)
    for t in range(N):
        h.world.step()
        mq = s.modal_q
        if mq is not None:
            h.rs.q[:] = mq
        d[t] = h.rs.probe_U[0, 1, :] @ h.rs.q       # plate defl @ payload pt
        P = s.positions()
        yp[t] = P[ip][1]
        yi[t] = P[ii][1]
    return h, d, yp, yi


def main():
    apply_style()
    hL, dL, ypL, yiL = run(True)
    hR, dR, ypR, yiR = run(False)
    t = np.arange(N) / FS
    t_imp = float(np.argmax(yiL < hL.impactor_half + 2e-3) / FS)
    sag = dL[int((t_imp - 0.05) * FS)] * 1e3
    rat = (ypL.max() - ypL.min()) * 1e3
    rat_R = (ypR.max() - ypR.min()) * 1e3
    y0 = hL.payload_half

    fig, (ax_a, ax_b) = plt.subplots(
        2, 1, figsize=(7.4, 4.4), sharex=True,
        gridspec_kw=dict(height_ratios=[1.5, 1.0], hspace=0.12))

    ax_a.plot(t, dR * 1e3, color=C_ONE, lw=1.4,
              label="one-way — plate never sees the payload")
    ax_a.plot(t, dL * 1e3, color=C_TWO, lw=1.4,
              label="two-way — payload in the contact rows")
    ax_a.axvline(t_imp, color="#888888", lw=0.8, ls=(0, (4, 3)))
    ax_a.text(t_imp + 0.04, ax_a.get_ylim()[0] * 0.0 + 12.5, "impact",
              color="#666666", fontsize=7)
    ax_a.annotate(f"static sag {sag:+.1f} mm", xy=(t_imp - 0.07, sag),
                  xytext=(0.42, -16.5), fontsize=7, color=C_TWO,
                  arrowprops=dict(arrowstyle="-", color=C_TWO, lw=0.7))
    ax_a.text(0.62, 12.0, "free ring 4.9 Hz", color=C_ONE, fontsize=7)
    ax_a.text(1.45, -12.3, "mass-loaded: detuned to 1.6 Hz, damped",
              color=C_TWO, fontsize=7)
    ax_a.set_ylabel("plate deflection at\npayload point [mm]")
    ax_a.set_ylim(-19, 17)
    ax_a.legend(loc="upper right", framealpha=0.9)

    ax_b.plot(t, (ypR - y0) * 1e3, color=C_ONE, lw=1.4)
    ax_b.plot(t, (ypL - y0) * 1e3, color=C_TWO, lw=1.4)
    ax_b.axvline(t_imp, color="#888888", lw=0.8, ls=(0, (4, 3)))
    ax_b.text(1.5, -13.6, f"rides the plate it sagged and calmed — "
              f"{rat:.0f} mm", color=C_TWO, fontsize=7)
    ax_b.text(1.5, 6.0, f"tossed {rat_R:.0f} mm by a ring its own mass "
              f"never damped", color=C_ONE, fontsize=7)
    ax_b.set_ylabel("payload height\n− rest [mm]")
    ax_b.set_ylim(-18, 13)
    ax_b.set_xlabel("time [s]")
    ax_b.set_xlim(0, T_END)

    out = os.path.join(OUT, "payload_ab.png")
    fig.savefig(out, dpi=200)
    print(f"wrote {out}")
    print(f"impact {t_imp:.3f} s | sag {sag:+.2f} mm | "
          f"payload motion two-way {rat:.1f} mm vs one-way "
          f"{(ypR.max() - ypR.min()) * 1e3:.4f} mm")


if __name__ == "__main__":
    main()
