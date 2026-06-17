#!/usr/bin/env python3
"""Supplementary plots from the contact-force sweep CSVs (no re-sim).

The headline two-way metric is post-impact CARGO KINETIC ENERGY, not the bed-
force ring std (which is dominated by impulsive stack-landing spikes and is
non-monotonic). KE answers directly: how much energy did the bed's response put
into the cargo? Two-way solvers (AVBD/XPBD) should transmit far more than the
quasi-static one-way Split control.
"""
from __future__ import annotations

import csv
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = "docs/twobody/contact_force_sweep"
LUMBER = 1

# --- read summary.csv: per (solver,kind,thickness,pile) KE peak ---
rows = list(csv.DictReader(open(f"{OUT}/summary.csv")))
ke = defaultdict(dict)   # (solver,kind) -> {thickness: KE_peak} for the lumber pile
for r in rows:
    if int(r["pile"]) != LUMBER:
        continue
    key = (r["solver"], r["kind"])
    ke[key][float(r["thickness_m"])] = float(r["post_impact_pile_KE_peak_J"])

thks = sorted({float(r["thickness_m"]) for r in rows})
tmm = np.array(thks) * 1e3

# 6) TWO-WAY ENERGY: lumber-stack peak KE vs thickness (log-y), dynamic vs one-way
fig, ax = plt.subplots(figsize=(8.5, 5))
style = {("avbd", "fem"): ("C0", "o", "AVBD-fem (two-way)"),
         ("xpbd", "fem"): ("C1", "^", "XPBD-fem (two-way)"),
         ("avbd", "abd"): ("C2", "s", "AVBD-abd (two-way)"),
         ("split", "fem"): ("C3", "x", "Split-fem (ONE-way control)")}
for key, (c, m, lab) in style.items():
    if key not in ke:
        continue
    ys = [ke[key][t] for t in thks]
    ax.semilogy(tmm, ys, c + m + "-", ms=8, lw=1.4, label=lab,
                markerfacecolor=("none" if key == ("split", "fem") else c))
ax.set_xlabel("slab thickness [mm]")
ax.set_ylabel("post-impact lumber-stack peak KE  [J]  (log)")
ax.set_title("Two-way energy transfer: the bed's response drives the cargo\n"
             "dynamic AVBD/XPBD ≫ quasi-static Split (except the thin-bed anomaly)")
ax.grid(alpha=0.3, which="both")
ax.legend()
ax.annotate("thin-bed Split breaks down\n(over-soft quasi-static bed flings cargo)",
            xy=(30, ke[("split", "fem")][0.03]), xytext=(45, 4.5),
            fontsize=8, arrowprops=dict(arrowstyle="->", color="C3", alpha=0.7))
fig.tight_layout()
fig.savefig(f"{OUT}/6_twoway_energy_vs_thickness.png", dpi=130)
plt.close(fig)

# 7) THICKNESS TREND for the two-way solvers (linear, monotonic)
fig, ax = plt.subplots(figsize=(8.5, 5))
for key, (c, m, lab) in style.items():
    if key == ("split", "fem") or key not in ke:
        continue
    ys = [ke[key][t] for t in thks]
    ax.plot(tmm, ys, c + m + "-", ms=8, lw=1.4, label=lab.replace(" (two-way)", ""))
ax.set_xlabel("slab thickness [mm]")
ax.set_ylabel("post-impact lumber-stack peak KE  [J]")
ax.set_title("Thicker bed → stiffer (compliance ∝ 1/h³) → monotonically less\n"
             "kinetic energy delivered to the cargo (the two-way coupling weakens)")
ax.grid(alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig(f"{OUT}/7_thickness_trend_cargo_KE.png", dpi=130)
plt.close(fig)

# --- regenerate plot 4 with a correct right panel (cargo KE, not noisy ring std) ---
prows = list(csv.DictReader(open(f"{OUT}/pile_forces_long.csv")))
# avbd-fem lumber-stack (pile 1) bed-force trace per thickness
trace = defaultdict(lambda: ([], []))   # thickness -> (t, force)
for r in prows:
    if r["solver"] == "avbd" and r["kind"] == "fem" and int(r["pile"]) == LUMBER:
        t = float(r["thickness_m"])
        trace[t][0].append(float(r["t_s"]))
        trace[t][1].append(float(r["bed_support_force_N"]))
fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
cmap = plt.cm.viridis(np.linspace(0, 0.85, len(thks)))
for t, col in zip(thks, cmap):
    ts, fs = trace[t]
    axs[0].plot(ts, fs, color=col, lw=1.0, label=f"{t*1e3:.0f} mm")
axs[0].set_xlabel("sim time [s]")
axs[0].set_ylabel("slab→lumber bed force [N]")
axs[0].set_title("Lumber-stack bed force vs slab thickness (avbd-fem)")
axs[0].legend(title="thickness"); axs[0].grid(alpha=0.3)
for key, (c, m, lab) in style.items():
    if key == ("split", "fem") or key not in ke:
        continue
    axs[1].plot(tmm, [ke[key][t] for t in thks], c + m + "-", ms=7,
                label=lab.replace(" (two-way)", ""))
axs[1].set_xlabel("slab thickness [mm]")
axs[1].set_ylabel("post-impact lumber-stack peak KE [J]")
axs[1].set_title("Cargo energy delivered vs thickness\n(thicker → stiffer → less; monotonic)")
axs[1].legend(); axs[1].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{OUT}/4_thickness_sweep.png", dpi=130)
plt.close(fig)

print("KE peak [J] for the lumber stack (pile 1):")
print(f"  {'config':16s} " + " ".join(f"{t*1e3:5.0f}mm" for t in thks))
for key in [("avbd", "fem"), ("avbd", "abd"), ("xpbd", "fem"), ("split", "fem")]:
    if key not in ke:
        continue
    print(f"  {key[0]+'-'+key[1]:16s} " +
          " ".join(f"{ke[key][t]:7.3f}" for t in thks))
print(f"\nwrote 6_twoway_energy_vs_thickness.png, 7_thickness_trend_cargo_KE.png to {OUT}/")
