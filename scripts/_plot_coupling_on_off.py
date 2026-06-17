#!/usr/bin/env python3
"""The convincing coupling test is NOT 'how many joules' — it is the COUNTERFACTUAL:
freeze the slab and the cargo doesn't move; let it ring and the cargo flies.
Same scene, same contacts, same forces — the ONLY change is whether the slab
carries modal inertia (can ring). Plots base-cube height + cargo energy for
AVBD (slab rings, two-way) vs Split (slab frozen quasi-static, one-way) at 50 mm.
"""
from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from dcr.twobody.multibody import build_truck_bed
from dcr.twobody.position_based import AVBDDynamicSystem, SplitOneWaySystem

OUT = "docs/twobody/contact_force_sweep"
G, THK, H, N = 9.81, 0.05, 5.0e-4, 1000
LUM = [2, 3, 4]


def run(which):
    base, info = build_truck_bed("fem", slab_height=THK)
    sys = (AVBDDynamicSystem(base, n_outer=8, n_inner=4) if which == "avbd"
           else SplitOneWaySystem(base, newton_iters=30))
    st = sys.initial_state()
    m = [base.bodies[b].carrier_mass for b in LUM]
    t = np.zeros(N); y = np.zeros(N); E = np.zeros(N)
    for k in range(N):
        st = sys.step(st, H)
        e = sys.energy_breakdown(st)
        t[k] = (k + 1) * H
        y[k] = base.body_z(st, 2)[1] * 1e3
        E[k] = (sum(e[f"KE_body{b}"] for b in LUM)
                + sum(mm * G * base.body_z(st, b)[1] for mm, b in zip(m, LUM)))
    return t, y, E


ta, ya, Ea = run("avbd")
ts, ys, Es = run("split")

fig, axs = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
axs[0].plot(ta, ya, "C0", lw=1.3, label="slab ALLOWED to ring (AVBD, two-way)")
axs[0].plot(ts, ys, "C3", lw=1.6, label="slab FROZEN quasi-static (Split, one-way)")
axs[0].axhline(0, color="k", lw=0.6)
axs[0].set_ylabel("lumber-stack height [mm]")
axs[0].set_title("Why the coupling is convincing: it is the COUNTERFACTUAL, not the joules\n"
                 "(truck bed, 50 mm — identical scene/contacts/forces; only the slab's "
                 "modal inertia differs)")
axs[0].legend(loc="upper right"); axs[0].grid(alpha=0.3)
axs[0].annotate(f"flies {ya.max():.0f} mm", xy=(ta[np.argmax(ya)], ya.max()),
                xytext=(0.18, 70), color="C0",
                arrowprops=dict(arrowstyle="->", color="C0"))
axs[0].annotate(f"never leaves the bed ({ys.max():.1f} mm)", xy=(0.25, 0),
                xytext=(0.25, 25), color="C3",
                arrowprops=dict(arrowstyle="->", color="C3"))

axs[1].plot(ta, Ea, "C0", lw=1.3, label="cargo energy, slab ringing")
axs[1].plot(ts, Es, "C3", lw=1.6, label="cargo energy, slab frozen")
axs[1].set_ylabel("cargo mech energy [J]")
axs[1].set_xlabel("sim time [s]")
axs[1].legend(loc="upper right"); axs[1].grid(alpha=0.3)
axs[1].annotate(f"peak {Ea.max():.2f} J → enough to lift 2.1 kg by {Ea.max()/(2.1*G)*1e3:.0f} mm",
                xy=(ta[np.argmax(Ea)], Ea.max()), xytext=(0.15, Ea.max()*0.7),
                color="C0", arrowprops=dict(arrowstyle="->", color="C0"))
fig.tight_layout()
fig.savefig(f"{OUT}/12_coupling_on_vs_off.png", dpi=130)
plt.close(fig)
print(f"avbd : max lift {ya.max():.1f} mm, peak cargo E {Ea.max():.3f} J")
print(f"split: max lift {ys.max():.1f} mm, peak cargo E {Es.max():.3f} J")
print(f"wrote 12_coupling_on_vs_off.png to {OUT}/")
