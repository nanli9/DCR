#!/usr/bin/env python3
"""§N2 rigid-ride analysis — the lower cube's flex lifts the upper's RIGID body.

Three panels (dark, for two_band_coupling.html):
  A) Stability — the demo 3-high offset stack (friction, the shipped config) with
     the ride ON: every cube holds its rest height, the pre-registered N3 pump
     does NOT walk it off.
  B) Contact-force smoothing (the headline) — the box-box normal force at a
     stacked joint. Ride OFF the ring hammers a RIGID contact ⇒ the force
     chatters (±~2 N); ride ON the stacked body RIDES the deforming surface ⇒ the
     chatter collapses (3–7×) while the mean stays at the supported weight. The
     ride does not change the force balance — it removes the impact chatter.
  C) The ride is real — a controlled 2-cube stack, δy(t) = y_upper(ride ON) −
     (ride OFF) isolates the ride: a bounded, flex-scale (~15 µm) rigid response
     that is exactly zero with the ride off.

Emits docs/network/network_ride.png + docs/network/network_ride.json.
Run: .venv/bin/python benchmarks/network/analyze_ride.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from scenes.reduced_cargo_network import build_cargo_network_scene
from dcr.avbd._solver.solver_6dof import (
    Solver6DOF, BOX_BOX_CONTACT_6DOF)
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube
from dcr.fem.fem_model import Material

OUT_PNG = os.path.join(_ROOT, "docs", "network", "network_ride.png")
OUT_JSON = os.path.join(_ROOT, "docs", "network", "network_ride.json")
DT = 1.0 / 120.0
G = 9.81
N = 360


def _box_forces(s, name_of):
    """Per-joint box-box normal force Σ|λ| (N)."""
    lam = s.lambdas(); act = s.active(); ct = s.c_type.numpy()
    ba = s.c_body_a.numpy(); bb = s.c_body_b.numpy()
    ns = s._gpu_pool_n_static
    na = min(int(s.n_active_rows.numpy()[0]), s._gpu_pool_n_capacity)
    box = {}
    for c in range(ns, na):
        if act[c] == 0 or int(ct[c]) != BOX_BOX_CONTACT_6DOF:
            continue
        k = tuple(sorted((name_of[int(ba[c])], name_of[int(bb[c])])))
        box[k] = box.get(k, 0.0) + abs(float(lam[c]))
    return box


def simulate_demo(ride):
    """Demo 3-high stack: cube heights (stability) + box-box joint forces."""
    h = build_cargo_network_scene(network=True, ride=ride)
    s = h.world._solver
    idx = h.avbd_idx
    name_of = {v: k for k, v in idx.items()}
    y = {nm: np.zeros(N) for nm in ("base", "mid", "upper")}
    F = {("base", "mid"): np.zeros(N), ("mid", "upper"): np.zeros(N)}
    for i in range(N):
        s.step()
        P = s.positions()
        for nm in y:
            y[nm][i] = float(P[idx[nm]][1])
        box = _box_forces(s, name_of)
        for k in F:
            F[k][i] = box.get(k, 0.0)
    return dict(t=np.arange(N) * DT, y=y, F=F,
                mg=float(h.cubes["upper"].mass) * G,
                finite=bool(np.all(np.isfinite(s.positions()))),
                ymin={nm: float(y[nm].min()) for nm in y})


def _two_cube(ride, mu=0.4, drop=0.05):
    s = Solver6DOF(dt=DT, iterations=12, substeps=4, device="cpu",
                   gravity=(0.0, -9.81, 0.0))
    s.enable_self_collision(True, default_friction=mu)
    s._modal_contact_network = True
    s._modal_contact_ride = bool(ride)
    size = 0.1; half = 0.5 * size
    mk = lambda: build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0,
                                      material=Material(E=3e5, nu=0.3, rho=600.0))
    L, U = mk(), mk()
    Lb = s.add_box(position=(0.0, half, 0.0), half_extents=(half,) * 3,
                   mass=float(L.mass), friction=mu)
    Ub = s.add_box(position=(0.0, 3.0 * half + drop, 0.0), half_extents=(half,) * 3,
                   mass=float(U.mass), friction=mu)
    Mq = np.eye(2); Kq = np.diag(np.array([60.0, 180.0]) ** 2)
    s.set_modal_support(Mq, Kq, 0.02 * Mq + 2.0e-5 * Kq)
    U_y = np.array([1.0, 0.4]); cb = L.corner_body
    rows = [(s.add_support_contact_corner(Lb, off_a=(sx * half, sy * half, sz * half),
             y_rest=0.0, U_y_row=U_y), (sx * half, sy * half, sz * half))
            for sx in (-1., 1.) for sy in (-1., 1.) for sz in (-1., 1.)]
    sr = [(slot, int(np.argmin(np.linalg.norm(cb - np.array(off), axis=1))))
          for slot, off in rows]
    s.add_cargo_native(Lb, L, sr)
    s.add_cargo_native(Ub, U, [])
    return s, Lb, Ub


def ride_signal(n=480):
    s_on, _, U_on = _two_cube(True)
    s_off, _, U_off = _two_cube(False)
    y_on = np.zeros(n); y_off = np.zeros(n)
    for i in range(n):
        s_on.step(); s_off.step()
        y_on[i] = float(s_on.positions()[U_on.index][1])
        y_off[i] = float(s_off.positions()[U_off.index][1])
    return np.arange(n) * DT, (y_on - y_off)


def _smooth(y, w=40):
    k = np.ones(w) / w
    return np.convolve(np.pad(y, (w // 2, w // 2), mode="edge"), k, mode="valid")[:len(y)]


def _style(ax):
    ax.set_facecolor("#0c0f15")
    for sp in ax.spines.values():
        sp.set_color("#272c38")
    ax.tick_params(colors="#9aa1ad", labelsize=8)
    ax.grid(alpha=0.18, color="#3a4150")
    ax.title.set_color("#e7eaf0")
    ax.xaxis.label.set_color("#9aa1ad"); ax.yaxis.label.set_color("#9aa1ad")


def main():
    print("### §N2 rigid-ride analysis ###", flush=True)
    print("[sim] demo ride OFF …", flush=True); doff = simulate_demo(False)
    print("[sim] demo ride ON  …", flush=True); don = simulate_demo(True)
    print("[sim] controlled δy …", flush=True); t2, dy = ride_signal()

    w = slice(N // 3, N)
    mg = don["mg"]
    joint = ("mid", "upper")                       # the top box-box joint
    rip_off = float(np.std(doff["F"][joint][w]))
    rip_on = float(np.std(don["F"][joint][w]))
    dy_hp = dy - _smooth(dy, 40)
    wv = slice(int(0.4 / DT), len(t2))
    ride_rms = float(np.std(dy_hp[wv])); drift_peak = float(np.max(np.abs(dy[wv])))

    fig = plt.figure(figsize=(15.0, 4.4), facecolor="#0e1014")
    fig.suptitle("Rigid-ride half — implemented + stable with friction: the "
                 "stacked body rides the deforming surface (contact chatter "
                 f"↓ {rip_off/max(rip_on,1e-9):.0f}×)", color="#e7eaf0",
                 fontsize=12, y=0.99)
    COL = {"base": "#34d399", "mid": "#f5c451", "upper": "#fb923c"}

    # A: stability -----------------------------------------------------------
    axA = fig.add_subplot(1, 3, 1); _style(axA)
    for nm in ("base", "mid", "upper"):
        axA.plot(don["t"], don["y"][nm], color=COL[nm], lw=1.8, label=f"{nm}  y")
    axA.set_title("demo 3-high stack (μ=0.4), ride ON — it stands", fontsize=10)
    axA.set_xlabel("time [s]"); axA.set_ylabel("cube height y [m]")
    axA.set_ylim(0, 0.32)
    axA.legend(fontsize=8, facecolor="#161922", edgecolor="#272c38", labelcolor="#d3d8e1")

    # B: contact-force smoothing (headline) ----------------------------------
    axB = fig.add_subplot(1, 3, 2); _style(axB)
    t = don["t"]
    axB.plot(t, doff["F"][joint], color="#e0635a", lw=1.0, alpha=0.9,
             label=f"ride OFF — chatters (±{rip_off:.1f} N)")
    axB.plot(t, don["F"][joint], color="#34d399", lw=1.3,
             label=f"ride ON — rides, smooth (±{rip_on:.1f} N)")
    axB.axhline(mg, color="#6b7486", ls="--", lw=1.0)
    axB.text(t[-1] * 0.99, mg + 0.35, "m·g", color="#8a93a5", fontsize=8, ha="right")
    axB.set_title("mid↔upper box-box force — the ride removes the chatter",
                  fontsize=10)
    axB.set_xlabel("time [s]"); axB.set_ylabel("normal force Σ|λ| [N]")
    axB.set_ylim(0, 2.6 * mg)
    axB.legend(fontsize=8, facecolor="#161922", edgecolor="#272c38", labelcolor="#d3d8e1")

    # C: the rigid response --------------------------------------------------
    axC = fig.add_subplot(1, 3, 3); _style(axC)
    axC.axhline(0.0, color="#3a4150", lw=1.0)
    axC.plot(t2, dy * 1e6, color="#fb923c", lw=1.3,
             label=r"$\delta y=y_{\rm up}$(ON) − (OFF)")
    axC.plot(t2, dy_hp * 1e6, color="#7aa2ff", lw=0.9, alpha=0.85,
             label=r"ring-band (drift removed)")
    axC.set_title("controlled 2-cube: the rigid body responds  (OFF ⇒ δy ≡ 0)",
                  fontsize=10)
    axC.set_xlabel("time [s]"); axC.set_ylabel(r"rigid response δy [µm]")
    axC.legend(fontsize=7.8, facecolor="#161922", edgecolor="#272c38", labelcolor="#d3d8e1")
    axC.text(0.03, 0.05, f"bounded flex-scale: {ride_rms*1e6:.0f} µm rms, ≤ {drift_peak*1e6:.0f} µm",
             transform=axC.transAxes, color="#9aa1ad", fontsize=7.6, va="bottom")

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    fig.savefig(OUT_PNG, dpi=125, facecolor="#0e1014")
    plt.close(fig)
    print(f"wrote {OUT_PNG}", flush=True)

    ledger = {}
    for k, exp in ((("base", "mid"), 2), (("mid", "upper"), 1)):
        ledger["_".join(k)] = dict(
            expect=exp * mg,
            off_mean=float(doff["F"][k][w].mean()), off_ripple=float(doff["F"][k][w].std()),
            on_mean=float(don["F"][k][w].mean()), on_ripple=float(don["F"][k][w].std()))
    S = dict(demo_finite=don["finite"], demo_ymin=don["ymin"], mg=mg,
             chatter_reduction=rip_off / max(rip_on, 1e-9),
             ride_rms=ride_rms, drift_peak=drift_peak, ledger=ledger)
    with open(OUT_JSON, "w") as f:
        json.dump(S, f, indent=2)
    print(f"wrote {OUT_JSON}", flush=True)

    print(f"\ndemo stands: {S['demo_ymin']}  finite={don['finite']}")
    print(f"m·g = {mg:.3f} N")
    print(f"{'joint':11s} {'expect':>7s} | {'OFF mean':>8s} {'OFF ±':>7s} | {'ON mean':>8s} {'ON ±':>7s} | reduction")
    for name, d in ledger.items():
        print(f"{name:11s} {d['expect']:7.2f} | {d['off_mean']:8.2f} {d['off_ripple']:7.2f} | "
              f"{d['on_mean']:8.2f} {d['on_ripple']:7.2f} | {d['off_ripple']/max(d['on_ripple'],1e-9):.1f}×")
    print(f"rigid response δy: {ride_rms*1e6:.0f} µm rms (ring band), ≤ {drift_peak*1e6:.0f} µm total")


if __name__ == "__main__":
    main()
