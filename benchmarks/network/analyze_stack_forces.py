#!/usr/bin/env python3
"""§N2 deep analysis — corner contact force + the ring climbing the tower.

Two experiments:

A) The full demo scene (`scenes/reduced_cargo_network.py`, 5 cubes) run network
   ON and OFF, logging per rigid step
     * the corner CONTACT-FORCE ledger — `c_lambda` per active row, which is a
       force in Newtons (Σ over a body's corners = the weight it supports).
       Support rows hold the slab-resting cubes; box-box rows hold each stacked
       joint, so we read directly how much weight each joint carries.
     * the modal-amplitude CASCADE — |q|(t) for the slab and |a|(t) for base ▸
       mid ▸ upper, to watch the ring climb the tower through the two box-box
       hops. OFF, mid & upper are structurally uncoupled ⇒ a ≡ 0 (discriminator).

B) A CONTROLLED 2-cube pair (lower on the slab, upper box-box only) run with the
   lower cube's ring free vs frozen (ȧ_lower ≡ 0). This isolates the feed: if the
   upper's ring is genuinely fed by the lower's ring, freezing the lower starves
   it. (Matches tests/avbd_native/test_modal_contact_network.py::
   test_freeze_lower_ring_reduces_upper_response.) The 5-cube scene is a poor
   place to test this — there the base is hammered by the impactor's slab ring,
   and a frozen (non-recoiling) base is a STIFFER driver, so the sign flips; the
   controlled gentle-settle pair is the honest counterfactual.

Emits:
  docs/network/network_force_analysis.png   4-panel dark figure (for the HTML)
  docs/network/network_force_analysis.json  the quantitative summary (HTML table)

Run: .venv/bin/python benchmarks/network/analyze_stack_forces.py
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
from dcr.avbd._solver.solver_6dof import Solver6DOF, BOX_BOX_CONTACT_6DOF
from dcr.avbd.cargo.fem_rigid import build_fem_rigid_cube
from dcr.fem.fem_model import Material

OUT_PNG = os.path.join(_ROOT, "docs", "network", "network_force_analysis.png")
OUT_JSON = os.path.join(_ROOT, "docs", "network", "network_force_analysis.json")

G = 9.81
N_STEPS = 360          # 3.0 s at h = 1/120
DT = 1.0 / 120.0
NAMES = ["resting", "impactor", "base", "mid", "upper"]


# ---------------------------------------------------------------------------
# A) full 5-cube scene: force ledger + cascade
# ---------------------------------------------------------------------------
def _read_forces(s, name_of):
    """Per-step contact-force ledger (Σ|λ| in N, since c_lambda sums to weight):
       support[name]   over that body's active support corners
       boxbox[(lo,hi)] over the active box-box rows of that joint."""
    lam = s.lambdas()
    act = s.active()
    ctype = s.c_type.numpy()
    ba = s.c_body_a.numpy()
    bb = s.c_body_b.numpy()
    n_static = s._gpu_pool_n_static
    n_active = min(int(s.n_active_rows.numpy()[0]), s._gpu_pool_n_capacity)

    support: dict[str, float] = {}
    for cidx in s._support_row_cidx:
        if act[cidx] == 0:
            continue
        nm = name_of[int(s._rows[cidx].body_a)]
        support[nm] = support.get(nm, 0.0) + abs(float(lam[cidx]))

    boxbox: dict[tuple, float] = {}
    for cidx in range(n_static, n_active):
        if act[cidx] == 0 or int(ctype[cidx]) != BOX_BOX_CONTACT_6DOF:
            continue
        a, b = name_of[int(ba[cidx])], name_of[int(bb[cidx])]
        key = tuple(sorted((a, b)))
        boxbox[key] = boxbox.get(key, 0.0) + abs(float(lam[cidx]))
    return support, boxbox


def simulate_scene(network):
    h = build_cargo_network_scene(network=network)
    s = h.world._solver
    idx = h.avbd_idx
    name_of = {v: k for k, v in idx.items()}
    log = dict(
        t=np.arange(N_STEPS) * DT,
        a={nm: np.zeros(N_STEPS) for nm in NAMES},
        q_slab=np.zeros(N_STEPS),
        F_support={nm: np.zeros(N_STEPS) for nm in NAMES},
        F_box={("base", "mid"): np.zeros(N_STEPS),
               ("mid", "upper"): np.zeros(N_STEPS)},
    )
    for n in range(N_STEPS):
        s.step()
        for nm in NAMES:
            log["a"][nm][n] = float(np.linalg.norm(s.cargo_a(idx[nm])))
        log["q_slab"][n] = float(np.linalg.norm(s.modal_q))
        sup, box = _read_forces(s, name_of)
        for nm in NAMES:
            log["F_support"][nm][n] = sup.get(nm, 0.0)
        for key in log["F_box"]:
            log["F_box"][key][n] = box.get(key, 0.0)
    log["mass"] = {nm: float(h.cubes[nm].mass) for nm in NAMES}
    log["yfinal"] = {nm: float(s.positions()[idx[nm]][1]) for nm in NAMES}
    log["finite"] = bool(np.all(np.isfinite(s.positions())))
    log["net_rows"] = len(s._net_rows)
    return log


# ---------------------------------------------------------------------------
# B) controlled 2-cube pair: freeze the lower ring, starve the upper
# ---------------------------------------------------------------------------
def controlled_pair(freeze_lower, n=300, E=3.0e5, drop=0.02):
    """Lower cube L on the modal slab (support); upper cube U on L (box-box only,
    NO support). U's modes are reachable ONLY through the network, so |a_U|(t) is
    a clean readout of the feed. Mirrors the test's `_stack`."""
    s = Solver6DOF(dt=DT, iterations=12, substeps=4, device="cpu",
                   gravity=(0.0, -9.81, 0.0))
    s.enable_self_collision(True, default_friction=0.0)
    s._modal_contact_network = True
    size = 0.1
    half = 0.5 * size
    L = build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0,
                             material=Material(E=E, nu=0.3, rho=600.0))
    U = build_fem_rigid_cube(size=size, n_elastic=3, drop_y=0.0,
                             material=Material(E=E, nu=0.3, rho=600.0))
    Lb = s.add_box(position=(0.0, half + drop, 0.0), half_extents=(half,) * 3,
                   mass=float(L.mass), friction=0.0)
    Ub = s.add_box(position=(0.0, 3.0 * half + drop, 0.0),
                   half_extents=(half,) * 3, mass=float(U.mass), friction=0.0)
    Mq = np.eye(2); Kq = np.diag(np.array([60.0, 180.0]) ** 2)
    Dq = 0.02 * Mq + 2.0e-5 * Kq
    s.set_modal_support(Mq, Kq, Dq)
    U_y = np.array([1.0, 0.4])
    rows = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                off = (sx * half, sy * half, sz * half)
                rows.append((s.add_support_contact_corner(
                    Lb, off_a=off, y_rest=0.0, U_y_row=U_y), off))
    cb = L.corner_body
    support_rows = [(slot, int(np.argmin(np.linalg.norm(cb - np.array(off), axis=1))))
                    for slot, off in rows]
    s.add_cargo_native(Lb, L, support_rows)
    s.add_cargo_native(Ub, U, [])
    if freeze_lower:
        s._freeze_adot = {Lb.index}
    aU = np.zeros(n)
    for i in range(n):
        s.step()
        aU[i] = float(np.linalg.norm(s.cargo_a(Ub.index)))
    return np.arange(n) * DT, aU


# ---------------------------------------------------------------------------
def _style(ax):
    ax.set_facecolor("#0c0f15")
    for sp in ax.spines.values():
        sp.set_color("#272c38")
    ax.tick_params(colors="#9aa1ad", labelsize=8)
    ax.grid(alpha=0.18, color="#3a4150")
    ax.title.set_color("#e7eaf0")
    ax.xaxis.label.set_color("#9aa1ad")
    ax.yaxis.label.set_color("#9aa1ad")


COL = {"q_slab": "#7aa2ff", "base": "#34d399", "mid": "#f5c451", "upper": "#fb923c",
       "resting": "#5b6373", "impactor": "#e0635a"}


def _smooth(y, w=15):
    """Centered moving average — the box-box normal force chatters per substep
    (frictionless offset stack rocking); the running mean is the physical
    supported weight (the settled tail mean is quoted exactly in the table)."""
    k = np.ones(w) / w
    return np.convolve(np.pad(y, (w // 2, w // 2), mode="edge"), k, mode="valid")[:len(y)]


def _cascade_panel(ax, log, title, ymax_cube):
    """Cube |a| on the left axis; slab |q| on a twin right axis (it is ~20× the
    cube amplitude — a different modal coordinate — so it gets its own scale)."""
    _style(ax)
    t = log["t"]
    for nm in ("base", "mid", "upper"):
        ax.plot(t, log["a"][nm] * 1e6, color=COL[nm], lw=1.9, label=f"{nm}  |a|")
    ax.set_ylim(0, ymax_cube)
    ax.set_title(title, fontsize=10.5)
    ax.set_xlabel("time [s]")
    ax.set_ylabel(r"cube modal $|a|$  [$\times10^{-6}$]")
    axr = ax.twinx()
    axr.plot(t, log["q_slab"] * 1e6, color=COL["q_slab"], lw=1.6, alpha=0.9,
             label="slab q (support ring)")
    axr.set_ylabel(r"slab $|q|$  [$\times10^{-6}$]", color=COL["q_slab"])
    axr.tick_params(colors=COL["q_slab"], labelsize=8)
    axr.spines["right"].set_color(COL["q_slab"])
    axr.set_ylim(0, max(log["q_slab"].max(), 1e-9) * 1e6 * 1.15)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = axr.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, facecolor="#161922",
              edgecolor="#272c38", labelcolor="#d3d8e1", loc="upper right")


def make_figure(on, off, t2, aU_free, aU_frz):
    fig = plt.figure(figsize=(12.8, 8.6), facecolor="#0e1014")
    fig.suptitle("Modal contact network — the ring climbs the tower "
                 "(slab ▸ base ▸ mid ▸ upper), and each joint carries exactly "
                 "the weight above it", color="#e7eaf0", fontsize=12.5, y=0.985)

    ymax = max(on["a"]["base"].max(), off["a"]["base"].max()) * 1e6 * 1.12
    _cascade_panel(fig.add_subplot(2, 2, 1), on,
                   "network ON — impactor ▸ slab ▸ base ▸ mid ▸ upper", ymax)
    _cascade_panel(fig.add_subplot(2, 2, 2), off,
                   "network OFF — mid & upper structurally dead (a ≡ 0)", ymax)

    # force ledger -----------------------------------------------------------
    ax = fig.add_subplot(2, 2, 3); _style(ax)
    t = on["t"]; mg = on["mass"]["upper"] * G
    series = [("impactor", on["F_support"]["impactor"], "impactor support Σ|λ|  (→ m·g)"),
              ("base", on["F_support"]["base"], "base support Σ|λ|  (→ 3 m·g)"),
              ("mid", on["F_box"][("base", "mid")], "base↔mid box-box  (→ 2 m·g)"),
              ("upper", on["F_box"][("mid", "upper")], "mid↔upper box-box  (→ m·g)")]
    for c, y, lab in series:                       # raw chatter, faint
        ax.plot(t, y, color=COL[c], lw=0.6, alpha=0.16)
    for c, y, lab in series:                       # 0.125 s running mean, solid
        ax.plot(t, _smooth(y), color=COL[c], lw=2.0, label=lab)
    for k, lab in ((1, "m·g"), (2, "2 m·g"), (3, "3 m·g")):
        ax.axhline(k * mg, color="#6b7486", ls="--", lw=1.0)
        ax.text(t[-1] * 0.995, k * mg + 0.28, lab, color="#8a93a5", fontsize=7.5, ha="right")
    ax.set_title("corner contact-force ledger — running mean = supported weight",
                 fontsize=10.5)
    ax.set_xlabel("time [s]"); ax.set_ylabel("normal contact force  [N]")
    ax.set_ylim(0, 3.4 * mg)
    ax.legend(fontsize=7.6, facecolor="#161922", edgecolor="#272c38",
              labelcolor="#d3d8e1", loc="upper right")

    # controlled freeze counterfactual --------------------------------------
    ax = fig.add_subplot(2, 2, 4); _style(ax)
    ax.plot(t2, aU_free * 1e6, color=COL["upper"], lw=1.9, label="upper |a| — lower ring FREE")
    ax.plot(t2, aU_frz * 1e6, color="#8a6a3a", lw=1.6, ls="--", label="upper |a| — lower ring FROZEN")
    ax.fill_between(t2, aU_frz * 1e6, aU_free * 1e6, where=aU_free >= aU_frz,
                    color=COL["upper"], alpha=0.12)
    ax.set_title("controlled 2-cube: freeze the lower ring ⇒ the upper starves",
                 fontsize=10.5)
    ax.set_xlabel("time [s]"); ax.set_ylabel(r"upper modal $|a|$  [$\times10^{-6}$]")
    ax.legend(fontsize=8, facecolor="#161922", edgecolor="#272c38", labelcolor="#d3d8e1")

    fig.tight_layout(rect=(0, 0, 1, 0.955))
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    fig.savefig(OUT_PNG, dpi=125, facecolor="#0e1014")
    plt.close(fig)


def _settle(arr, tail=60):
    return float(np.mean(arr[-tail:]))


def summary(on, off, t2, aU_free, aU_frz):
    mg = on["mass"]["upper"] * G
    peak = lambda d, nm: float(np.max(d["a"][nm]))
    S = {
        "net_rows": on["net_rows"], "finite": on["finite"], "mg": mg,
        "ledger": {
            "impactor_support": _settle(on["F_support"]["impactor"]),
            "base_support": _settle(on["F_support"]["base"]),
            "base_mid_box": _settle(on["F_box"][("base", "mid")]),
            "mid_upper_box": _settle(on["F_box"][("mid", "upper")]),
            "expect": {"impactor_support": mg, "base_support": 3 * mg,
                       "base_mid_box": 2 * mg, "mid_upper_box": mg},
        },
        "cascade_peak": {"q_slab": float(np.max(on["q_slab"])),
                         "base": peak(on, "base"), "mid": peak(on, "mid"),
                         "upper": peak(on, "upper")},
        "off_peak": {"base": peak(off, "base"), "mid": peak(off, "mid"),
                     "upper": peak(off, "upper")},
        "controlled_freeze": {"upper_free": float(np.max(aU_free)),
                              "upper_frozen": float(np.max(aU_frz))},
        "yfinal": on["yfinal"],
    }
    S["attenuation"] = {
        "base_to_mid": S["cascade_peak"]["mid"] / S["cascade_peak"]["base"],
        "mid_to_upper": S["cascade_peak"]["upper"] / S["cascade_peak"]["mid"],
    }
    S["freeze_ratio_upper"] = (S["controlled_freeze"]["upper_frozen"]
                               / S["controlled_freeze"]["upper_free"])
    return S


def main():
    print("### §N2 stacked-cube force analysis ###", flush=True)
    print("[sim] scene ON  …", flush=True);  on = simulate_scene(True)
    print("[sim] scene OFF …", flush=True);  off = simulate_scene(False)
    print("[sim] controlled pair — lower free …", flush=True)
    t2, aU_free = controlled_pair(freeze_lower=False)
    print("[sim] controlled pair — lower frozen …", flush=True)
    _, aU_frz = controlled_pair(freeze_lower=True)

    make_figure(on, off, t2, aU_free, aU_frz)
    print(f"wrote {OUT_PNG}", flush=True)
    S = summary(on, off, t2, aU_free, aU_frz)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(S, f, indent=2)
    print(f"wrote {OUT_JSON}", flush=True)

    mg = S["mg"]; L, E = S["ledger"], S["ledger"]["expect"]
    print(f"\n=== CORNER FORCE LEDGER (settled tail mean) — m·g = {mg:.3f} N ===")
    for k in ("impactor_support", "base_support", "base_mid_box", "mid_upper_box"):
        print(f"  {k:18s} {L[k]:8.3f} N   expect {E[k]:8.3f} N   "
              f"err {abs(L[k]-E[k])/E[k]*100:5.2f}%")
    C = S["cascade_peak"]; A = S["attenuation"]
    print(f"\n=== RING CASCADE (peak |a|, network ON) ===")
    print(f"  slab-q {C['q_slab']:.3e} → base {C['base']:.3e} → mid {C['mid']:.3e} → upper {C['upper']:.3e}")
    print(f"  attenuation:  base→mid {A['base_to_mid']:.3f}   mid→upper {A['mid_to_upper']:.3f}")
    print(f"\n=== ON vs OFF (peak |a|) — the discriminator ===")
    for nm in ("base", "mid", "upper"):
        print(f"  {nm:6s} ON {C[nm]:.3e}   OFF {S['off_peak'][nm]:.3e}")
    F = S["controlled_freeze"]
    print(f"\n=== CONTROLLED freeze (peak |a_upper|) ===")
    print(f"  free {F['upper_free']:.3e}   frozen {F['upper_frozen']:.3e}   "
          f"ratio {S['freeze_ratio_upper']:.3f}  (<1 ⇒ freezing the lower starves the upper)")
    print(f"\nnet_rows={S['net_rows']}  finite={S['finite']}  "
          f"tower y = " + " ".join(f"{nm}={S['yfinal'][nm]:.3f}" for nm in ("base", "mid", "upper")))


if __name__ == "__main__":
    main()
