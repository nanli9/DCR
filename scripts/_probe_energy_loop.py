#!/usr/bin/env python3
"""Probe: verify the bounce hypothesis + measure the slab<->cargo energy loop.

For avbd-fem and xpbd-fem (lumber stack, 80 mm) record per step:
  - slab RING energy   = KE_body0 + PEel_body0   (modal kinetic + elastic strain)
  - cargo KE           = Σ KE over lumber bodies 2,3,4
  - base-cube height   z[1]  (carrier y-translation from rest; >0 = lifted/airborne)
  - min base gap       min over the 4 base contacts (>0 = SEPARATED, i.e. airborne)
  - bed->base force    Σ over the 4 base contacts [N]
Then: count contact episodes (bounces) = gap crossings 0+→0-, and emit a 3-panel
diagram (energy loop / height+gap / force) per solver.
"""
from __future__ import annotations

import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from dcr.twobody.multibody import build_truck_bed
from dcr.twobody.position_based import AVBDDynamicSystem, XPBDDynamicSystem

OUT = "docs/twobody/contact_force_sweep"
THK, H, NSTEP = 0.08, 5.0e-4, 1000
LUMBER_BODIES = [2, 3, 4]
BASE_CONTACTS = [4, 5, 6, 7]      # bed->base-cube of pile 1


G = 9.81


def run(solver_name):
    base, info = build_truck_bed("fem", slab_height=THK)
    sys = (AVBDDynamicSystem(base, n_outer=8, n_inner=4) if solver_name == "avbd"
           else XPBDDynamicSystem(base, n_iters=30))
    st = sys.initial_state()
    m_lumber = [base.bodies[b].carrier_mass for b in LUMBER_BODIES]
    rec = {k: np.zeros(NSTEP) for k in
           ("t", "Eslab", "Ecargo", "EcargoKE", "ybase", "gap", "force", "Eimp")}
    for k in range(NSTEP):
        st = sys.step(st, H)
        e = sys.energy_breakdown(st)
        gaps = base._gaps(st.z)[0]
        rec["t"][k] = (k + 1) * H
        rec["Eslab"][k] = e["KE_body0"] + e["PEel_body0"]
        # cargo TOTAL mechanical energy: KE + elastic + gravitational (rise) PE,
        # so the slab→cargo launch energy is visible even while airborne.
        ke = sum(e[f"KE_body{b}"] for b in LUMBER_BODIES)
        pe_el = sum(e[f"PEel_body{b}"] for b in LUMBER_BODIES)
        pe_g = sum(m * G * base.body_z(st, b)[1]
                   for m, b in zip(m_lumber, LUMBER_BODIES))
        rec["EcargoKE"][k] = ke
        rec["Ecargo"][k] = ke + pe_el + pe_g
        rec["ybase"][k] = base.body_z(st, 2)[1]
        rec["gap"][k] = gaps[BASE_CONTACTS].min()
        rec["force"][k] = sys.last_contact_force[BASE_CONTACTS].sum()
        imp = info["impactor_body"]
        rec["Eimp"][k] = e[f"KE_body{imp}"]
    return rec


def count_bounces(gap, force, thresh=1e-4):
    """A bounce = a contact episode: the base goes airborne (gap>thresh) and
    re-lands (gap<=0 with a force spike). Count rising edges into contact."""
    airborne = gap > thresh
    # contact episode starts when we transition airborne -> in-contact
    landings = np.sum((airborne[:-1]) & (~airborne[1:]))
    max_air = gap.max()
    frac_airborne = airborne.mean()
    return int(landings), float(max_air), float(frac_airborne)


rows = [["solver", "step", "t_s", "slab_ring_E_J", "cargo_mech_E_J", "cargo_KE_J",
         "base_cube_y_m", "min_base_gap_m", "bed_base_force_N"]]
summary = {}
recs = {}
for solver in ("avbd", "xpbd"):
    r = run(solver)
    recs[solver] = r
    n_land, max_air, frac_air = count_bounces(r["gap"], r["force"])
    summary[solver] = (n_land, max_air, frac_air)
    for k in range(NSTEP):
        rows.append([solver, k, f"{r['t'][k]:.5f}", f"{r['Eslab'][k]:.6g}",
                     f"{r['Ecargo'][k]:.6g}", f"{r['EcargoKE'][k]:.6g}",
                     f"{r['ybase'][k]:.6g}", f"{r['gap'][k]:.6g}",
                     f"{r['force'][k]:.4f}"])

    # measured loop transfers: cargo energy gained at each launch (slab→cargo)
    cargo_launch = r["Ecargo"].max()
    slab_peak = r["Eslab"].max()
    summary[solver] = (n_land, max_air, frac_air, slab_peak, cargo_launch)

    # ---- 3-panel diagram ----
    fig, axs = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    # panel 1: the slab<->cargo energy LOOP
    axs[0].plot(r["t"], r["Eslab"], "C0", lw=1.1, label="slab ring energy (KE+PE_elastic)")
    axs[0].plot(r["t"], r["Ecargo"], "C3", lw=1.3,
                label="cargo TOTAL mech energy (KE+grav PE)")
    axs[0].plot(r["t"], r["EcargoKE"], "C3", lw=0.7, ls=":", alpha=0.7,
                label="cargo KE only (≈0 at flight apex)")
    axs[0].set_ylabel("energy [J]")
    axs[0].set_title(f"{solver}-fem, 80 mm — slab↔cargo energy loop  "
                     f"(slab peak {slab_peak:.0f} J → cargo launch {cargo_launch:.1f} J/cycle)")
    axs[0].legend(loc="upper right", fontsize=8); axs[0].grid(alpha=0.3)
    # panel 2: base-cube height + airborne shading (the bounces)
    axs[1].plot(r["t"], r["ybase"] * 1e3, "C2", lw=1.1, label="base-cube height z[1] [mm]")
    axs[1].axhline(0, color="k", lw=0.6)
    airborne = r["gap"] > 1e-4
    axs[1].fill_between(r["t"], axs[1].get_ylim()[0], axs[1].get_ylim()[1],
                        where=airborne, color="orange", alpha=0.15,
                        label="airborne (gap>0, separated)")
    axs[1].set_ylabel("height [mm]")
    axs[1].set_title(f"bounces = {summary[solver][0]} landings  "
                     f"(max lift {summary[solver][1]*1e3:.1f} mm, "
                     f"airborne {summary[solver][2]*100:.0f}% of the time)")
    axs[1].legend(loc="upper right"); axs[1].grid(alpha=0.3)
    # panel 3: bed->base contact force (the spikes)
    axs[2].plot(r["t"], r["force"], "C1", lw=1.0, label="bed→base contact force [N]")
    axs[2].set_ylabel("force [N]"); axs[2].set_xlabel("sim time [s]")
    axs[2].set_title("each force spike = one landing of that bounce")
    axs[2].legend(loc="upper right"); axs[2].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f"{OUT}/9_energy_loop_{solver}.png", dpi=130)
    plt.close(fig)
    print(f"{solver}: landings(bounces)={n_land}  max_lift={max_air*1e3:.2f}mm  "
          f"airborne_frac={frac_air:.2f}  slab_peak={summary[solver][3]:.1f}J  "
          f"cargo_launch={summary[solver][4]:.2f}J")

# ---- schematic LOOP diagram (box-and-arrow, annotated with measured AVBD J) ----
_, _, _, slab_peak, cargo_launch = summary["avbd"]
imp_peak = 0.5 * 6.0 * 6.4 ** 2   # ≈ impactor KE at impact (6 kg, ~6.4 m/s)
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
boxes = {
    "imp": (1.4, 4.2, "Impactor\n(drops on bare bed)\nKE ≈ {:.0f} J".format(imp_peak)),
    "slab": (5.0, 4.2, "SLAB modal ring\n(reduced coord q)\npeak ≈ {:.0f} J".format(slab_peak)),
    "cargo": (8.4, 4.2, "CARGO stack\n(bounces ballistically)\n≈ {:.1f} J / launch".format(cargo_launch)),
}
for x, y, txt in boxes.values():
    ax.add_patch(plt.Rectangle((x - 1.1, y - 0.7), 2.2, 1.4, fc="#eef", ec="k"))
    ax.text(x, y, txt, ha="center", va="center", fontsize=9)
# impact (one-way): impactor -> slab
ax.annotate("", xy=(3.9, 4.2), xytext=(2.5, 4.2),
            arrowprops=dict(arrowstyle="-|>", lw=2.2, color="C0"))
ax.text(3.2, 4.6, "impact\n(one-way)", ha="center", fontsize=8, color="C0")
# THE TWO-WAY LOOP: slab <-> cargo (one arrow each direction)
ax.annotate("", xy=(7.3, 4.5), xytext=(6.1, 4.5),
            arrowprops=dict(arrowstyle="-|>", lw=2.2, color="C2"))
ax.text(6.7, 4.95, "slab → cargo\n(ring LAUNCHES stack)", ha="center",
        fontsize=8, color="C2")
ax.annotate("", xy=(6.1, 3.9), xytext=(7.3, 3.9),
            arrowprops=dict(arrowstyle="-|>", lw=2.2, color="C3"))
ax.text(6.7, 3.35, "cargo → slab\n(landing RE-RINGS bed)", ha="center",
        fontsize=8, color="C3")
# dissipation arrows
for x, lab in [(5.0, "modal + contact\ndamping"), (8.4, "contact\ndamping")]:
    ax.annotate("", xy=(x, 2.2), xytext=(x, 3.4),
                arrowprops=dict(arrowstyle="-|>", lw=1.5, color="gray"))
    ax.text(x + 0.1, 2.5, lab, ha="left", va="center", fontsize=7.5, color="gray")
ax.text(5.0, 1.6, "dissipated (heat)", ha="center", fontsize=8, color="gray")
ax.text(7.0, 1.6, "ground", ha="center", fontsize=8, color="gray")
ax.set_title("Two-way energy LOOP (slab ⇄ cargo), AVBD-fem 80 mm\n"
             "the green+red pair IS the loop: the single shared contact "
             "multiplier carries both directions", fontsize=11)
fig.tight_layout()
fig.savefig(f"{OUT}/10_loop_schematic.png", dpi=130)
plt.close(fig)
print(f"wrote 10_loop_schematic.png to {OUT}/")

# ---- EXPLAINER: zoom on the first bounce cycle, twin axis (xpbd) ----
r = recs["xpbd"]
m = r["t"] <= 0.33
fig, axL = plt.subplots(figsize=(11, 5.5))
axR = axL.twinx()
l1, = axL.plot(r["t"][m], r["Eslab"][m], "C0", lw=1.6,
               label="SLAB ring energy (left axis)")
l2, = axR.plot(r["t"][m], r["Ecargo"][m], "C3", lw=1.6,
               label="CARGO mech energy (right axis)")
axL.set_xlabel("sim time [s]")
axL.set_ylabel("slab ring energy [J]", color="C0")
axR.set_ylabel("cargo mechanical energy [J]", color="C3")
axL.tick_params(axis="y", colors="C0"); axR.tick_params(axis="y", colors="C3")
axR.set_ylim(0, 2.0)
# phase markers
axL.axvspan(0.04, 0.10, color="C2", alpha=0.10)
axL.axvspan(0.28, 0.31, color="C3", alpha=0.10)
axL.annotate("① impact charges the SLAB\n   to ~46 J (it rings)",
             xy=(0.05, 46), xytext=(0.045, 33), fontsize=9, color="C0")
axL.annotate("② SLAB → CARGO\n   ring launches the stack\n   (cargo gains ~1.3 J)",
             xy=(0.10, 7.5), xytext=(0.115, 30), fontsize=9, color="C2",
             arrowprops=dict(arrowstyle="->", color="C2"))
axR.annotate("ballistic flight:\ncargo energy CONSTANT ~1.3 J\n(this is the 1.3 J/cycle)",
             xy=(0.18, 1.27), xytext=(0.135, 1.55), fontsize=9, color="C3")
axL.annotate("③ CARGO → SLAB\n   landing re-rings the bed\n   (slab bumps +1.7 J)",
             xy=(0.305, 3.86), xytext=(0.20, 18), fontsize=9, color="C3",
             arrowprops=dict(arrowstyle="->", color="C3"))
axL.legend(handles=[l1, l2], loc="upper right")
axL.set_title("How to read the energy-loop panel (xpbd-fem, 80 mm, first bounce)\n"
              "left axis = slab (big); right axis = cargo (small) — note the "
              "DIFFERENT scales. The loop = ② then ③.")
axL.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(f"{OUT}/11_energy_loop_explained.png", dpi=130)
plt.close(fig)
print(f"wrote 11_energy_loop_explained.png to {OUT}/")

with open(f"{OUT}/energy_loop_probe.csv", "w", newline="") as fh:
    csv.writer(fh).writerows(rows)
print(f"wrote 9_energy_loop_avbd.png, 9_energy_loop_xpbd.png, energy_loop_probe.csv to {OUT}/")
