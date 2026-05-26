#!/usr/bin/env python3
"""Headline plot synthesis for the seven benchmarks.

Reads `benchmark/manifests/MANIFEST.json` + each per-benchmark manifest,
then writes one PNG per benchmark to `benchmark/plots/B<n>/`. Each plot
answers the headline question for that benchmark per
`benchmark/BENCHMARK_PROMPT.md` §5.

Run: `uv run python scripts/plot_benchmarks.py`
"""
from __future__ import annotations

import json
from pathlib import Path

import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Publication-quality defaults. Applied once at import so every plot
# below inherits them. Style chosen for readability on a white slide /
# paper; tweaked to match `matplotlib`'s rcParams documentation.
plt.style.use("seaborn-v0_8-whitegrid")
plt.rcParams.update({
    "figure.dpi": 110,                  # on-screen
    "savefig.dpi": 300,                 # publication
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "axes.titleweight": "semibold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "grid.linestyle": "-",
    "grid.linewidth": 0.6,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "legend.frameon": True,
    "legend.framealpha": 0.85,
    "legend.edgecolor": "0.8",
    "lines.linewidth": 2.2,
    "lines.markersize": 6.5,
})

# Consistent color cycle across plots so the same scene/mode always
# gets the same color. Picked from matplotlib's tab10 palette for
# colorblind-friendliness.
SCENE_COLORS = {
    "ledge": "#1f77b4",   # blue
    "truck": "#d62728",   # red
    "shelf": "#2ca02c",   # green
}
MODE_COLORS = {
    "coevoet":                          "#9467bd",  # purple
    "energy_prescribed":                "#1f77b4",  # blue
    "energy_prescribed_point_impulse":  "#2ca02c",  # green
    "energy_prescribed_patch":          "#d62728",  # red
}

REPO = Path(__file__).resolve().parents[1]
MANIFESTS = REPO / "benchmark/manifests"
PLOTS_DIR = REPO / "benchmark/plots"
SCENES = ["ledge", "truck", "shelf"]


def _savefig(fig, out: Path) -> None:
    """Write a PNG at 300 dpi *and* an SVG at the same logical size.

    PNG is the headline artifact (renders everywhere); the SVG is for
    embedding in LaTeX / slides at any zoom level.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300)
    fig.savefig(out.with_suffix(".svg"))
    plt.close(fig)


def _load_manifest(bid: str) -> dict:
    return json.load(open(MANIFESTS / f"{bid}_manifest.json"))


def _read_csv(rel: str) -> dict[str, np.ndarray]:
    """Return CSV as a dict of column-name -> 1-D numpy array."""
    path = REPO / rel
    with open(path) as f:
        rdr = csv.reader(f)
        header = next(rdr)
        cols: list[list[str]] = [[] for _ in header]
        for row in rdr:
            for i, v in enumerate(row):
                cols[i].append(v)
    out: dict[str, np.ndarray] = {}
    for name, vals in zip(header, cols):
        try:
            out[name] = np.array([float(v) for v in vals], dtype=np.float64)
        except ValueError:
            out[name] = np.array(vals, dtype=object)
    return out


def _summary(rel: str) -> dict:
    return json.load(open(REPO / rel))


# ---------------------------------------------------------------------------
# B1 — Energy conservation: paper baseline vs passive follow-up.
# ---------------------------------------------------------------------------

def plot_b1():
    m = _load_manifest("B1")
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6), sharey=False,
                             constrained_layout=True)
    for ax, scene in zip(axes, SCENES):
        runs = {r["run_id"]: r for r in m["runs"]}
        paper = runs[f"B1-paper-{scene}"]
        passive = runs[f"B1-passive-{scene}"]
        dp = _read_csv(paper["files"]["energy_csv"])
        dq = _read_csv(passive["files"]["energy_csv"])
        ax.plot(dp["t"], dp["cum_E_injected"], color="#d62728",
                lw=2.5, label="paper (coevoet, uncapped)")
        ax.plot(dq["t"], dq["cum_E_injected"], color="#1f77b4",
                lw=2.5, label="passive (patch + BJ)")
        ax.plot(dp["t"], dp["cum_E_budget_eta"], color="#d62728",
                lw=1.2, ls="--", alpha=0.7,
                label=r"η · cum_E_loss  (paper)")
        ax.plot(dq["t"], dq["cum_E_budget_eta"], color="#1f77b4",
                lw=1.2, ls="--", alpha=0.7,
                label=r"η · cum_E_loss  (passive)")
        # Shade the §15-violation region (where paper injection sits
        # above its own budget) so the headline reads at a glance.
        ax.fill_between(
            dp["t"], dp["cum_E_budget_eta"], dp["cum_E_injected"],
            where=(dp["cum_E_injected"] > dp["cum_E_budget_eta"]),
            color="#d62728", alpha=0.10, label="§15 violation",
        )
        ax.set_title(scene, pad=6)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("cumulative energy (J)")
        if scene == SCENES[0]:
            ax.legend(loc="upper left", fontsize=8.5)
    fig.suptitle(
        "B1 — Energy conservation:  paper baseline violates §15;  "
        "passive follow-up holds it",
        fontsize=14, fontweight="semibold",
    )
    out = PLOTS_DIR / "B1_energy_conservation" / "B1_headline.png"
    _savefig(fig, out)
    print(f"[B1] {out.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# B2 — Deformed normal: tangential-leak fraction comparison.
# ---------------------------------------------------------------------------

def plot_b2():
    m = _load_manifest("B2")
    # data[scene][cell] -> {tan_over_normal, mean_angle_deg}
    data: dict[str, dict[str, dict[str, float]]] = {s: {} for s in SCENES}
    for r in m["runs"]:
        if "impulse_csv" not in r["files"]:
            continue
        df = _read_csv(r["files"]["impulse_csv"])
        if df["J_normal"].size == 0:
            continue
        Jn = np.abs(df["J_normal"]).sum()
        Jt = np.hypot(df["J_tangential_u"], df["J_tangential_v"]).sum()
        n_rest = np.column_stack([df["n_rest_x"], df["n_rest_y"], df["n_rest_z"]])
        n_def = np.column_stack([df["n_deformed_x"], df["n_deformed_y"],
                                  df["n_deformed_z"]])
        nr_norm = np.linalg.norm(n_rest, axis=1, keepdims=True).clip(1e-9)
        nd_norm = np.linalg.norm(n_def, axis=1, keepdims=True).clip(1e-9)
        cos = np.clip(np.einsum("ij,ij->i", n_rest / nr_norm,
                                 n_def / nd_norm), -1, 1)
        ang = np.degrees(np.arccos(cos))
        cell = f"{r['mode']}/{r['flavor']}"
        data[r["scene"]][cell] = dict(
            tan_over_normal=float(Jt / max(Jn, 1e-12)),
            mean_angle_deg=float(ang.mean()),
        )
    cell_order = [
        "coevoet/rest",
        "energy_prescribed_point_impulse/rest",
        "energy_prescribed_point_impulse/patch_fit",
        "energy_prescribed_point_impulse/barbic_james",
        "energy_prescribed_patch/barbic_james",
    ]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.2),
                                    constrained_layout=True)
    width = 0.25
    for i, scene in enumerate(SCENES):
        tan = [data[scene].get(c, {}).get("tan_over_normal", 0.0)
               for c in cell_order]
        ang = [data[scene].get(c, {}).get("mean_angle_deg", 0.0)
               for c in cell_order]
        x = np.arange(len(cell_order)) + width * (i - 1)
        ax1.bar(x, tan, width=width, color=SCENE_COLORS[scene],
                edgecolor="white", linewidth=0.5, label=scene)
        ax2.bar(x, ang, width=width, color=SCENE_COLORS[scene],
                edgecolor="white", linewidth=0.5, label=scene)
    for ax, ylab, title in [
        (ax1, r"$\Sigma|J_t|\ /\ \Sigma|J_n|$",
         "Tangential-impulse leak per (mode, flavor)"),
        (ax2, r"mean $\angle(n_{\rm rest}, n_{\rm deformed})$  (deg)",
         "Rest-vs-deformed normal angle"),
    ]:
        ax.set_xticks(np.arange(len(cell_order)))
        ax.set_xticklabels(
            [c.replace("energy_prescribed_", "EP-") for c in cell_order],
            rotation=22, ha="right", fontsize=9,
        )
        ax.set_ylabel(ylab)
        ax.set_title(title, pad=6)
        ax.legend(title="scene", loc="upper left")
    fig.suptitle("B2 — Deformed-normal flavor comparison across scenes",
                 fontsize=14, fontweight="semibold")
    out = PLOTS_DIR / "B2_deformed_normal" / "B2_headline.png"
    _savefig(fig, out)
    print(f"[B2] {out.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# B3 — β sweep: ratio_injected_over_budget per (scene, mode) vs β.
# ---------------------------------------------------------------------------

def plot_b3():
    m = _load_manifest("B3")
    # data[scene][mode] -> list of (beta, ratio, inv_viol)
    data: dict[str, dict[str, list]] = {s: {} for s in SCENES}
    modes_seen: set[str] = set()
    for r in m["runs"]:
        s = _summary(r["files"]["summary_json"])
        scene, mode = r["scene"], r["mode"]
        data[scene].setdefault(mode, []).append((
            s["params"]["beta"],
            s["energy_totals"]["ratio_injected_over_budget"],
            s["invariant_max_violation_J"],
        ))
        modes_seen.add(mode)
    modes = sorted(modes_seen)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.0), sharey=True,
                              constrained_layout=True)
    for ax, scene in zip(axes, SCENES):
        for mode in modes:
            pts = sorted(data[scene].get(mode, []))
            if not pts:
                continue
            betas = [p[0] for p in pts]
            ratios = [p[1] for p in pts]
            label = (mode
                     .replace("energy_prescribed_point_impulse", "EP-point-impulse")
                     .replace("energy_prescribed_patch", "EP-patch")
                     .replace("energy_prescribed", "EP-A"))
            ax.plot(betas, ratios, "-o", color=MODE_COLORS[mode],
                    markeredgecolor="white", markeredgewidth=0.8,
                    label=label)
        ax.axhline(1.0, color="0.25", ls=":", lw=1.2,
                   label=r"§15 ceiling")
        # Shade the violation zone (above 1.0) faintly — visually
        # nobody can step over the dashed line in a passive run.
        ax.axhspan(1.0, ax.get_ylim()[1] if False else 1.4,
                   color="#d62728", alpha=0.06)
        ax.set_xlabel(r"$\beta$")
        ax.set_ylabel(r"cum_E_injected $/\ (\eta\,\cdot\,$cum_E_loss$)$")
        ax.set_title(scene, pad=6)
        ax.set_ylim(0.0, 1.15)
        if scene == SCENES[0]:
            ax.legend(loc="lower right", fontsize=8.5)
    fig.suptitle(
        r"B3 — $\beta$ sweep: passive paths stay $\leq$ 1; patch mode is "
        r"$\beta$-insensitive",
        fontsize=14, fontweight="semibold",
    )
    out = PLOTS_DIR / "B3_beta_sweep" / "B3_headline.png"
    _savefig(fig, out)
    print(f"[B3] {out.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# B4 — η sweep: cum_E_injected_final vs η.
# ---------------------------------------------------------------------------

def plot_b4():
    m = _load_manifest("B4")
    rows = []
    for r in m["runs"]:
        s = _summary(r["files"]["summary_json"])
        rows.append((
            s["params"]["eta"],
            s["energy_totals"]["cum_E_injected_final_J"],
            s["energy_totals"]["cum_E_budget_eta_final_J"],
            s["energy_totals"]["ratio_injected_over_budget"],
        ))
    rows.sort()
    etas = np.array([r[0] for r in rows])
    cum_inj = np.array([r[1] for r in rows])
    cum_budget = np.array([r[2] for r in rows])
    ratios = np.array([r[3] for r in rows])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8),
                                    constrained_layout=True)
    ax1.plot(etas, cum_inj, "-o", color="#1f77b4",
             markeredgecolor="white", markeredgewidth=0.8,
             label="cum_E_injected (actual)")
    ax1.plot(etas, cum_budget, "--s", color="#d62728",
             markeredgecolor="white", markeredgewidth=0.8,
             label=r"$\eta\,\cdot\,$cum_E_loss  (§15 ceiling)")
    ax1.set_xlabel(r"$\eta$")
    ax1.set_ylabel("cumulative energy (J)")
    ax1.set_title("Injection vs §15 ceiling across η", pad=6)
    ax1.legend()

    ax2.plot(etas, ratios, "-o", color="#2ca02c",
             markeredgecolor="white", markeredgewidth=0.8)
    ax2.axhline(1.0, color="0.25", ls=":", lw=1.2, label=r"§15 ceiling")
    ax2.axhspan(1.0, 1.15, color="#d62728", alpha=0.06)
    ax2.set_xlabel(r"$\eta$")
    ax2.set_ylabel(r"cum_E_injected $/\ (\eta\,\cdot\,$cum_E_loss$)$")
    ax2.set_title(r"Ratio remains $\leq 1$ for every η", pad=6)
    ax2.set_ylim(0.0, 1.15)
    ax2.legend()
    fig.suptitle(
        "B4 — η sweep: the §15 ceiling tracks η linearly; the passive "
        "ratio stays below it",
        fontsize=14, fontweight="semibold",
    )
    out = PLOTS_DIR / "B4_eta_sweep" / "B4_headline.png"
    _savefig(fig, out)
    print(f"[B4] {out.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# B5 — Material sensitivity (wood vs steel).
# ---------------------------------------------------------------------------

def plot_b5():
    m = _load_manifest("B5")
    # data[material][body] = (y_range_mm, n_bumps)
    data: dict[str, dict[str, tuple[float, int]]] = {}
    body_set: set[str] = set()
    for r in m["runs"]:
        s = _summary(r["files"]["summary_json"])
        mat = s["params"]["material"]
        d_mat = data.setdefault(mat, {})
        for b in s["bodies"]:
            lp = b.get("late_phase", {})
            d_mat[b["name"]] = (
                float(lp.get("y_range_last_3s_mm", 0.0)),
                int(lp.get("n_bumps_last_3s", 0)),
            )
            body_set.add(b["name"])
    bodies = sorted(body_set)
    MAT_COLORS = {"wood": "#b8732c", "steel": "#6c7780"}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.2),
                                    constrained_layout=True)
    width = 0.38
    for i, mat in enumerate(["wood", "steel"]):
        d_mat = data.get(mat, {})
        y_range = [d_mat.get(b, (0.0, 0))[0] for b in bodies]
        n_bumps = [d_mat.get(b, (0.0, 0))[1] for b in bodies]
        x = np.arange(len(bodies)) + width * (i - 0.5)
        ax1.bar(x, y_range, width=width, color=MAT_COLORS[mat],
                edgecolor="white", linewidth=0.5, label=mat)
        ax2.bar(x, n_bumps, width=width, color=MAT_COLORS[mat],
                edgecolor="white", linewidth=0.5, label=mat)
    for ax, ylab, title in [
        (ax1, r"y range over last 3 s (mm)",
         "Late-phase y excursion (amplitude)"),
        (ax2, r"$v_y$ zero-crossings over last 3 s",
         "Late-phase bumps (frequency proxy)"),
    ]:
        ax.set_xticks(np.arange(len(bodies)))
        ax.set_xticklabels(bodies, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel(ylab)
        ax.set_title(title, pad=6)
        ax.legend(title="material", loc="upper left")
    fig.suptitle(
        "B5 — Wood vs steel late-phase activity (truck patch+BJ, "
        "β=0.7, gated, 8 s)",
        fontsize=14, fontweight="semibold",
    )
    out = PLOTS_DIR / "B5_material" / "B5_headline.png"
    _savefig(fig, out)
    print(f"[B5] {out.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# B6 — Runtime breakdown per mode.
# ---------------------------------------------------------------------------

def plot_b6():
    m = _load_manifest("B6")
    # data[scene][mode] = p50_ms
    data: dict[str, dict[str, float]] = {s: {} for s in SCENES}
    for r in m["runs"]:
        s = _summary(r["files"]["summary_json"])
        data[r["scene"]][r["mode"]] = float(s["wall_time_ms_per_step"]["p50"])
    modes = ["coevoet", "energy_prescribed",
             "energy_prescribed_point_impulse", "energy_prescribed_patch"]
    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    width = 0.25
    for i, scene in enumerate(SCENES):
        ys = [data[scene].get(mode, 0.0) for mode in modes]
        x = np.arange(len(modes)) + (i - 1) * width
        bars = ax.bar(x, ys, width=width, color=SCENE_COLORS[scene],
                      edgecolor="white", linewidth=0.5, label=scene)
        # Numeric labels above each bar so the read-at-a-glance value
        # is exact, not eyeballed.
        for rect, val in zip(bars, ys):
            ax.text(rect.get_x() + rect.get_width() / 2,
                    rect.get_height() + 1.5,
                    f"{val:.1f}", ha="center", va="bottom",
                    fontsize=8, color="0.3")
    ax.set_xticks(np.arange(len(modes)))
    ax.set_xticklabels([
        m_.replace("energy_prescribed_point_impulse", "EP-point-impulse")
          .replace("energy_prescribed_patch", "EP-patch")
          .replace("energy_prescribed", "EP-A")
        for m_ in modes
    ], rotation=20, ha="right")
    ax.set_ylabel("median wall time per step (ms)")
    ax.set_title("B6 — Per-step cost by (scene, mode)", pad=8)
    ax.legend(title="scene", loc="upper left")
    out = PLOTS_DIR / "B6_runtime" / "B6_headline.png"
    _savefig(fig, out)
    print(f"[B6] {out.relative_to(REPO)}")


# ---------------------------------------------------------------------------
# B7 — h sweep (extension).
# ---------------------------------------------------------------------------

def plot_b7():
    m = _load_manifest("B7")
    # data[(scene, mode)] -> list of (h, ratio, wall_per_step_ms)
    data: dict[tuple[str, str], list] = {}
    for r in m["runs"]:
        s = _summary(r["files"]["summary_json"])
        key = (r["scene"], r["mode"])
        wall_per_step = 1000.0 * s["wall_time_total_s"] / max(s["n_steps"], 1)
        data.setdefault(key, []).append((
            s["params"]["h"],
            s["energy_totals"]["ratio_injected_over_budget"],
            wall_per_step,
        ))
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.2),
                              constrained_layout=True)
    line_styles = {"coevoet": "-", "energy_prescribed_patch": "--"}
    markers = {"coevoet": "o", "energy_prescribed_patch": "s"}
    for (scene, mode), pts in sorted(data.items()):
        pts.sort()
        hs = [p[0] for p in pts]
        ratios = [p[1] for p in pts]
        walls = [p[2] for p in pts]
        label = (f"{scene} / "
                 f"{mode.replace('energy_prescribed_patch', 'EP-patch')}")
        axes[0].plot(hs, ratios,
                     linestyle=line_styles.get(mode, "-"),
                     marker=markers.get(mode, "o"),
                     color=SCENE_COLORS[scene],
                     markeredgecolor="white", markeredgewidth=0.6,
                     label=label)
        axes[1].plot(hs, walls,
                     linestyle=line_styles.get(mode, "-"),
                     marker=markers.get(mode, "s"),
                     color=SCENE_COLORS[scene],
                     markeredgecolor="white", markeredgewidth=0.6,
                     label=label)
    axes[0].axhline(1.0, color="0.25", ls=":", lw=1.2,
                    label=r"§15 ceiling")
    axes[0].axhspan(1.0, 1.15, color="#d62728", alpha=0.06)
    axes[0].set_xscale("log")
    axes[0].set_ylim(0.0, 1.15)
    axes[0].set_xlabel(r"$h$  (s)")
    axes[0].set_ylabel(r"cum_E_injected $/\ (\eta\,\cdot\,$cum_E_loss$)$")
    axes[0].set_title(r"Injection ratio vs timestep $h$", pad=6)
    axes[0].legend(loc="lower right", fontsize=8.5)
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel(r"$h$  (s)")
    axes[1].set_ylabel("wall time per step (ms)")
    axes[1].set_title(r"Per-step wall time vs $h$  (log–log)", pad=6)
    axes[1].legend(loc="upper left", fontsize=8.5)
    fig.suptitle(
        r"B7 — Timestep $h$ sweep: §15 still holds at every $h$ tested",
        fontsize=14, fontweight="semibold",
    )
    out = PLOTS_DIR / "B7_h_sweep" / "B7_headline.png"
    _savefig(fig, out)
    print(f"[B7] {out.relative_to(REPO)}")


def main():
    plot_b1()
    plot_b2()
    plot_b3()
    plot_b4()
    plot_b5()
    plot_b6()
    plot_b7()


if __name__ == "__main__":
    main()
