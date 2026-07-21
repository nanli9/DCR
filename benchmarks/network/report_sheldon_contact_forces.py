#!/usr/bin/env python3
"""Contact-force report for the two-way modal-contact network (§N2).

Standalone ANALYSIS script (no solver code touched) that answers three questions
for the write-up to Sheldon:

  1. What are the actual contact forces at the corners of a plain RESTING cube
     (the control — one-way support ring only) vs. a cube inside a STACK
     (two-way: it feels the ring of the cube under it through box-box contact)?
  2. Is the coupling genuinely two-way and momentum-consistent? -> the corner /
     joint force ledger must sum to the weight above each joint (static
     correctness), and the ring modulation on those forces must vanish when the
     modal network is switched OFF (dynamic two-way signature).
  3. Would ABD help? -> re-run the identical scene with an ABD (affine 9-DOF)
     cargo cube and a purely-rigid (0-mode) cube; the affine body rings through
     the SAME network as the modal cube, the rigid one cannot ring at all, and
     the static ledger is identical for all three (contact balance is
     basis-independent).

Emits (docs/07_17_report/):
  contact_forces.png        4-panel: ledger, resting corners, base corners, ON/OFF
  abd_comparison.png        ring + settled-ledger across rigid | fem_rigid | abd
  contact_forces.json       the quantitative summary

Run: .venv/bin/python benchmarks/network/report_sheldon_contact_forces.py
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
from dcr.avbd._solver.solver_6dof import BOX_BOX_CONTACT_6DOF

OUT_DIR = os.path.join(_ROOT, "docs", "07_17_report")
G = 9.81
DT = 1.0 / 120.0
N_STEPS = 360                      # 3.0 s at h = 1/120
NAMES = ["resting", "impactor", "base", "mid", "upper"]


# ---------------------------------------------------------------------------
# force extraction (read-only solver introspection, same API as analyze_*)
# ---------------------------------------------------------------------------
def _corner_label(off):
    """A stacked cube rests on its 4 BOTTOM corners (off_a[1] < 0); label by the
    (x,z) quadrant so the same physical corner is comparable across cubes."""
    sx = "+x" if off[0] > 0 else "-x"
    sz = "+z" if off[2] > 0 else "-z"
    return f"{sx} {sz}"


def _bottom_corner_rows(s, body_idx):
    """(cidx, label) for the 4 load-bearing bottom corners of a support cube."""
    out = []
    for cidx in s._support_row_cidx:
        r = s._rows[cidx]
        if int(r.body_a) == body_idx and r.off_a[1] < 0.0:
            out.append((cidx, _corner_label(r.off_a)))
    out.sort(key=lambda t: t[1])
    return out


def _box_joint_forces(s, name_of):
    """Per box-box joint: total normal force Sum|lambda| over its active rows."""
    lam = s.lambdas(); act = s.active(); ct = s.c_type.numpy()
    ba = s.c_body_a.numpy(); bb = s.c_body_b.numpy()
    ns = s._gpu_pool_n_static
    na = min(int(s.n_active_rows.numpy()[0]), s._gpu_pool_n_capacity)
    box = {}
    for c in range(ns, na):
        if act[c] == 0 or int(ct[c]) != BOX_BOX_CONTACT_6DOF:
            continue
        key = tuple(sorted((name_of[int(ba[c])], name_of[int(bb[c])])))
        box[key] = box.get(key, 0.0) + abs(float(lam[c]))
    return box


def simulate(network, kind="fem_rigid"):
    h = build_cargo_network_scene(network=network, kind=kind)
    s = h.world._solver
    idx = h.avbd_idx
    name_of = {v: k for k, v in idx.items()}
    lam = s.lambdas()

    corner_rows = {nm: _bottom_corner_rows(s, idx[nm]) for nm in ("resting", "base")}
    log = dict(
        t=np.arange(N_STEPS) * DT,
        # per-corner force for the control cube and the stack foot
        corners={nm: {lab: np.zeros(N_STEPS) for _, lab in rows}
                 for nm, rows in corner_rows.items()},
        # aggregate support force per slab-resting cube
        F_support={nm: np.zeros(N_STEPS) for nm in ("resting", "impactor", "base")},
        # per box-box joint total
        F_box={("base", "mid"): np.zeros(N_STEPS),
               ("mid", "upper"): np.zeros(N_STEPS)},
        # ring amplitudes
        a={nm: np.zeros(N_STEPS) for nm in ("base", "mid", "upper")},
        q_slab=np.zeros(N_STEPS),
    )
    for n in range(N_STEPS):
        s.step()
        lam = s.lambdas(); act = s.active()
        for nm, rows in corner_rows.items():
            for cidx, lab in rows:
                log["corners"][nm][lab][n] = abs(float(lam[cidx])) if act[cidx] else 0.0
        for nm in ("resting", "impactor", "base"):
            tot = 0.0
            for cidx in s._support_row_cidx:
                if int(s._rows[cidx].body_a) == idx[nm] and act[cidx]:
                    tot += abs(float(lam[cidx]))
            log["F_support"][nm][n] = tot
        box = _box_joint_forces(s, name_of)
        for key in log["F_box"]:
            log["F_box"][key][n] = box.get(key, 0.0)
        for nm in ("base", "mid", "upper"):
            log["a"][nm][n] = float(np.linalg.norm(s.cargo_a(idx[nm])))
        log["q_slab"][n] = float(np.linalg.norm(s.modal_q))
    log["mg"] = float(h.cubes["upper"].mass) * G
    log["finite"] = bool(np.all(np.isfinite(s.positions())))
    return log


# ---------------------------------------------------------------------------
# plotting (light theme for the report)
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "font.size": 10, "axes.titlesize": 11, "axes.grid": True,
    "grid.alpha": 0.25, "axes.edgecolor": "#444", "savefig.facecolor": "white",
})
CORNER_COL = {"-x -z": "#1b6ca8", "-x +z": "#5aa9e6",
              "+x -z": "#c9452b", "+x +z": "#f08a5d"}
JOINT_COL = {"resting": "#555", "base": "#1b6ca8",
             ("base", "mid"): "#e08e0b", ("mid", "upper"): "#c9452b"}


def _mean(y, w=15):
    k = np.ones(w) / w
    return np.convolve(np.pad(y, (w // 2, w // 2), mode="edge"), k, mode="valid")[:len(y)]


def _settle(y, tail=60):
    return float(np.mean(y[-tail:]))


def figure_contact_forces(on, off):
    mg = on["mg"]; t = on["t"]
    fig, ax = plt.subplots(2, 2, figsize=(12.5, 8.4))
    fig.suptitle("Two-way modal contact — corner/joint contact forces vs time "
                 "(3-high stack + a plain resting control cube)", fontsize=12.5)

    # (a) the ledger -- each joint carries the weight above it -------------
    a0 = ax[0, 0]
    series = [("resting", on["F_support"]["resting"], JOINT_COL["resting"],
               "resting cube -> slab   (-> m·g)"),
              ("base", on["F_support"]["base"], JOINT_COL["base"],
               "base cube -> slab   (-> 3 m·g)"),
              (("base", "mid"), on["F_box"][("base", "mid")], JOINT_COL[("base", "mid")],
               "base <-> mid  box-box   (-> 2 m·g)"),
              (("mid", "upper"), on["F_box"][("mid", "upper")], JOINT_COL[("mid", "upper")],
               "mid <-> upper  box-box   (-> m·g)")]
    for _, y, c, _l in series:
        a0.plot(t, y, color=c, lw=0.5, alpha=0.18)
    for _, y, c, lab in series:
        a0.plot(t, _mean(y), color=c, lw=2.1, label=lab)
    for k, lab in ((1, "m·g"), (2, "2 m·g"), (3, "3 m·g")):
        a0.axhline(k * mg, color="#888", ls="--", lw=0.9)
        a0.text(t[0], k * mg + 0.25, lab, color="#666", fontsize=8, ha="left")
    a0.set_title("(a) contact-force ledger — running mean = supported weight")
    a0.set_xlabel("time [s]"); a0.set_ylabel("normal contact force [N]")
    a0.set_ylim(0, 3.7 * mg); a0.legend(fontsize=8.5, loc="upper right")

    # (b) resting control cube -- 4 corners --------------------------------
    a1 = ax[0, 1]
    for lab, y in on["corners"]["resting"].items():
        a1.plot(t, y, color=CORNER_COL[lab], lw=1.4, label=f"corner {lab}")
    a1.axhline(mg / 4, color="#888", ls="--", lw=0.9)
    a1.text(t[0], mg / 4 + 0.05, "m·g / 4", color="#666", fontsize=8, ha="left")
    a1.set_title("(b) RESTING control cube — 4 corners share m·g/4 evenly")
    a1.set_xlabel("time [s]"); a1.set_ylabel("corner normal force [N]")
    a1.set_ylim(0, 2.6)
    a1.annotate("impactor lands (slab ring)\n— transient clipped", xy=(0.22, 2.55),
                xytext=(0.55, 2.15), fontsize=7.5, color="#666",
                arrowprops=dict(arrowstyle="->", color="#999", lw=0.8))
    a1.legend(fontsize=8.5, loc="lower right")

    # (c) base cube in the stack -- 4 corners (raw + running mean) ----------
    a2 = ax[1, 0]
    for lab, y in on["corners"]["base"].items():
        a2.plot(t, y, color=CORNER_COL[lab], lw=0.5, alpha=0.22)
    for lab, y in on["corners"]["base"].items():
        a2.plot(t, _mean(y), color=CORNER_COL[lab], lw=2.0, label=f"corner {lab}")
    a2.axhline(3 * mg / 4, color="#888", ls="--", lw=0.9)
    a2.text(t[0], 3 * mg / 4 + 0.1, "3 m·g / 4", color="#666", fontsize=8, ha="left")
    a2.set_title("(c) BASE cube (stack foot) — 4 corners, 3 m·g total, "
                 "uneven (zig-zag lean)")
    a2.set_xlabel("time [s]"); a2.set_ylabel("corner normal force [N]")
    a2.set_ylim(0, 2.2 * mg); a2.legend(fontsize=8.5, loc="upper right")

    # (d) two-way discriminator: the upper cube only rings when coupled -----
    a3 = ax[1, 1]
    a3.plot(t, on["a"]["upper"] * 1e6, color="#1b6ca8", lw=1.6,
            label=f"network ON — rings (peak {on['a']['upper'].max():.1e})")
    a3.plot(t, off["a"]["upper"] * 1e6, color="#c9452b", lw=1.6,
            label="network OFF — |a| ≡ 0 (structurally dead)")
    a3.set_title("(d) two-way check: the TOP cube only vibrates when coupled "
                 "(2 box-box hops up)")
    a3.set_xlabel("time [s]"); a3.set_ylabel(r"upper cube ring $|a|$  [$\times10^{-6}$]")
    a3.legend(fontsize=8.5, loc="upper right")
    txt = ("bonus: the modal compliance also SMOOTHS the contact —\n"
           f"mid<->upper joint force ripple  {np.std(off['F_box'][('mid','upper')][120:]):.2f} N (OFF) "
           f"-> {np.std(on['F_box'][('mid','upper')][120:]):.2f} N (ON)")
    a3.text(0.03, 0.05, txt, transform=a3.transAxes, fontsize=8, color="#333",
            va="bottom")

    fig.tight_layout(rect=(0, 0, 1, 0.965))
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "contact_forces.png")
    fig.savefig(p, dpi=140); plt.close(fig)
    print(f"wrote {p}", flush=True)


def figure_abd(runs):
    """runs: dict kind -> log (network ON)."""
    mg = runs["fem_rigid"]["mg"]; t = runs["fem_rigid"]["t"]
    fig, ax = plt.subplots(1, 2, figsize=(13.0, 4.6))
    fig.suptitle("Would ABD help?  The affine body rings through the SAME two-way "
                 "network; the static ledger is basis-independent", fontsize=12)

    KIND_COL = {"rigid": "#888", "fem_rigid": "#1b6ca8", "abd": "#c9452b"}
    peak = {k: runs[k]["a"]["upper"].max() for k in ("rigid", "fem_rigid", "abd")}
    KIND_LAB = {"rigid": "rigid (0 modes) — cannot ring (|a|≡0)",
                "fem_rigid": f"fem_rigid (modal Φ)  peak |a|={peak['fem_rigid']:.1e}",
                "abd": f"abd (affine 9-DOF)  peak |d|={peak['abd']:.1e}"}
    # left: upper-cube ring amplitude through 2 box-box hops. Normalize each to
    # its own peak — the affine DOF d=vec(F−I) and the mass-normalized modal a
    # are different metrics; the point is the SHAPE (both ring + decay through
    # the network) vs. rigid staying flat zero, not the absolute magnitude.
    a0 = ax[0]
    for kind in ("rigid", "fem_rigid", "abd"):
        y = runs[kind]["a"]["upper"]
        yn = y / peak[kind] if peak[kind] > 0 else y
        a0.plot(t, yn, color=KIND_COL[kind], lw=1.6, label=KIND_LAB[kind])
    a0.set_title("(a) upper-cube ring (normalized to own peak) — fed only "
                 "through 2 box-box hops")
    a0.set_xlabel("time [s]"); a0.set_ylabel("normalized ring amplitude")
    a0.legend(fontsize=8.5, loc="upper right")

    # right: settled ledger bars vs expected multiples
    a1 = ax[1]
    joints = [("resting -> slab", "F_support", "resting", 1),
              ("base -> slab", "F_support", "base", 3),
              ("base<->mid", "F_box", ("base", "mid"), 2),
              ("mid<->upper", "F_box", ("mid", "upper"), 1)]
    x = np.arange(len(joints)); w = 0.24
    for i, kind in enumerate(("rigid", "fem_rigid", "abd")):
        vals = [_settle(runs[kind][fld][key]) for _, fld, key, _m in joints]
        a1.bar(x + (i - 1) * w, vals, w, color=KIND_COL[kind], label=kind)
    for j, (_lab, _f, _k, m) in enumerate(joints):
        a1.plot([x[j] - 1.6 * w, x[j] + 1.6 * w], [m * mg, m * mg],
                color="#333", ls="--", lw=1.1)
    a1.set_xticks(x); a1.set_xticklabels([j[0] for j in joints], fontsize=8.5)
    a1.set_title("(b) settled contact-force ledger (dashed = expected m·g multiple)")
    a1.set_ylabel("normal force [N]"); a1.legend(fontsize=9)

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    os.makedirs(OUT_DIR, exist_ok=True)
    p = os.path.join(OUT_DIR, "abd_comparison.png")
    fig.savefig(p, dpi=140); plt.close(fig)
    print(f"wrote {p}", flush=True)


def main():
    print("### contact-force report — two-way network ###", flush=True)
    print("[sim] fem_rigid  network ON  …", flush=True); on = simulate(True, "fem_rigid")
    print("[sim] fem_rigid  network OFF …", flush=True); off = simulate(False, "fem_rigid")
    print("[sim] abd        network ON  …", flush=True); abd = simulate(True, "abd")
    print("[sim] rigid      network ON  …", flush=True); rig = simulate(True, "rigid")

    figure_contact_forces(on, off)
    figure_abd({"fem_rigid": on, "abd": abd, "rigid": rig})

    mg = on["mg"]
    ledger = {
        "resting_support": (_settle(on["F_support"]["resting"]), mg),
        "base_support": (_settle(on["F_support"]["base"]), 3 * mg),
        "base_mid_box": (_settle(on["F_box"][("base", "mid")]), 2 * mg),
        "mid_upper_box": (_settle(on["F_box"][("mid", "upper")]), mg),
    }
    S = dict(mg=mg, finite=on["finite"],
             ledger={k: {"measured": v[0], "expect": v[1],
                         "err_pct": abs(v[0] - v[1]) / v[1] * 100.0}
                     for k, v in ledger.items()},
             resting_corners={lab: _settle(y) for lab, y in on["corners"]["resting"].items()},
             base_corners={lab: _settle(y) for lab, y in on["corners"]["base"].items()},
             ring_upper={"fem_rigid": float(on["a"]["upper"].max()),
                         "abd": float(abd["a"]["upper"].max()),
                         "rigid": float(rig["a"]["upper"].max()),
                         "off": float(off["a"]["upper"].max())},
             joint_ripple_mid_upper={"on": float(np.std(on["F_box"][("mid", "upper")][120:])),
                                     "off": float(np.std(off["F_box"][("mid", "upper")][120:]))})
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "contact_forces.json"), "w") as f:
        json.dump(S, f, indent=2)

    print(f"\n=== LEDGER (settled tail mean) — m·g = {mg:.3f} N ===")
    for k, d in S["ledger"].items():
        print(f"  {k:16s} {d['measured']:8.3f} N   expect {d['expect']:8.3f} N   "
              f"err {d['err_pct']:5.2f}%")
    print("\n=== RESTING control cube corners (settled, N) ===")
    for lab, v in S["resting_corners"].items():
        print(f"  {lab:6s} {v:7.3f}   (m·g/4 = {mg/4:.3f})")
    print("=== BASE stack-foot corners (settled, N) ===")
    for lab, v in S["base_corners"].items():
        print(f"  {lab:6s} {v:7.3f}   (3·m·g/4 = {3*mg/4:.3f})")
    print(f"\n=== upper-cube ring |a| peak (network feeds it) ===")
    for k, v in S["ring_upper"].items():
        print(f"  {k:10s} {v:.3e}")
    print(f"\nmid<->upper joint force ripple:  ON +-{S['joint_ripple_mid_upper']['on']:.3f} N   "
          f"OFF +-{S['joint_ripple_mid_upper']['off']:.3f} N")
    print(f"finite={S['finite']}")


if __name__ == "__main__":
    main()
