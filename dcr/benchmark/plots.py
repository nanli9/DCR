"""Matplotlib plotters for energy time series.

All public functions save a PNG to disk and return the path. No
interactive `plt.show()` calls — these are meant for batch use from the
analyze harness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import matplotlib
matplotlib.use("Agg")   # headless backend; safe to import in CI / shells
import matplotlib.pyplot as plt

from dcr.benchmark.energy_log import EnergyLog


# ----------------------------------------------------------------------
# Single-run energy plot
# ----------------------------------------------------------------------

def plot_energy_timeseries(
    log: EnergyLog,
    title: str,
    out_path: str | Path,
) -> Path:
    """4-panel figure for one run.

    Panels:
        (a) E_rigid_KE(t) and E_modal(t) — current energies in each system
        (b) cumulative dE_rigid_loss(t) and eta * cumulative dE_rigid_loss
            (the budget cap for injection) overlaid with cumulative
            dE_modal_injected(t) — visually shows the §15 bound holding
        (c) per-step dE_modal_injected(t) — sign tells you injection
            (positive, A/B modes) vs extraction (negative, patch mode)
        (d) alpha(t) — passive-scaling coefficient over time

    The cumulative-injected ≤ eta * cumulative-loss line is the
    foundation §15 invariant; if it ever crosses we have a bug.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if len(log) == 0:
        # Empty log — write a single-message figure so callers don't crash.
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "(empty energy log)", ha="center", va="center")
        ax.axis("off")
        fig.suptitle(title)
        fig.savefig(out_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return out_path

    t = log.times()
    E_rigid = log.E_rigid()
    E_modal = log.E_modal()
    cum_loss = log.cumulative_rigid_loss()
    cum_inj = log.cumulative_modal_injected()
    cum_ext = log.cumulative_modal_extracted()
    dE_inj = log.dE_modal_injected()
    alpha = log.alpha()
    eta = log.entries[0].eta
    bound = eta * cum_loss

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    (ax_e, ax_cum), (ax_inj, ax_alpha) = axes

    # (a) Energies.
    ax_e.plot(t, E_rigid, label="E_rigid_KE", color="#1f77b4")
    ax_e.plot(t, E_modal, label="E_modal", color="#d62728")
    ax_e.set_ylabel("Energy [J]")
    ax_e.set_title("(a) Energy state")
    ax_e.legend(loc="best", fontsize=8)
    ax_e.grid(alpha=0.3)

    # (b) Cumulative budget + injection.
    ax_cum.plot(t, cum_loss, label="∑ ΔE_rigid_loss", color="#1f77b4",
                linestyle="--")
    ax_cum.plot(t, bound, label=f"η·∑ ΔE_loss  (η={eta:.2f})",
                color="#2ca02c", linewidth=2)
    ax_cum.plot(t, cum_inj, label="∑ ΔE_modal_injected", color="#d62728")
    if cum_ext.max() > 1e-12:
        ax_cum.plot(t, cum_ext, label="∑ ΔE_modal_extracted",
                    color="#9467bd", linestyle=":")
    ax_cum.set_ylabel("Energy [J]")
    ax_cum.set_title("(b) Cumulative energy — §15 bound is the green line")
    ax_cum.legend(loc="best", fontsize=8)
    ax_cum.grid(alpha=0.3)

    # (c) Per-step modal delta (sign matters).
    ax_inj.bar(t, np.maximum(0.0, dE_inj), width=t[1]-t[0] if len(t) > 1 else 1,
               color="#d62728", label="injection (+)")
    ax_inj.bar(t, np.minimum(0.0, dE_inj), width=t[1]-t[0] if len(t) > 1 else 1,
               color="#9467bd", label="extraction (−)")
    ax_inj.axhline(0, color="black", linewidth=0.5)
    ax_inj.set_ylabel("ΔE_modal per step [J]")
    ax_inj.set_xlabel("time [s]")
    ax_inj.set_title("(c) Per-step modal energy delta")
    ax_inj.legend(loc="best", fontsize=8)
    ax_inj.grid(alpha=0.3)

    # (d) alpha.
    ax_alpha.plot(t, alpha, color="#ff7f0e")
    ax_alpha.axhline(1.0, color="gray", linestyle=":", linewidth=0.5)
    ax_alpha.set_ylim(-0.05, 1.1)
    ax_alpha.set_ylabel("α (passive scaling)")
    ax_alpha.set_xlabel("time [s]")
    ax_alpha.set_title("(d) α — 1 = unscaled, <1 = scaled to honor bound")
    ax_alpha.grid(alpha=0.3)

    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ----------------------------------------------------------------------
# Parameter-sweep overlay
# ----------------------------------------------------------------------

def plot_param_sweep(
    logs_by_param: Mapping[float, EnergyLog],
    param_name: str,
    scene: str,
    mode: str,
    out_path: str | Path,
) -> Path:
    """Overlay cumulative-injected curves for one (scene, mode) across
    parameter values. Useful for visualising β / η scans.

    Each subplot is one quantity; lines are colored by parameter value
    and labeled in the legend.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_items = sorted(logs_by_param.items(), key=lambda kv: kv[0])
    cmap = plt.get_cmap("viridis")
    colors = [cmap(i / max(1, len(sorted_items) - 1))
              for i in range(len(sorted_items))]

    fig, (ax_modal, ax_cum) = plt.subplots(1, 2, figsize=(12, 4.5))
    for (val, log), color in zip(sorted_items, colors):
        if len(log) == 0:
            continue
        t = log.times()
        ax_modal.plot(t, log.E_modal(), color=color,
                      label=f"{param_name}={val:g}")
        ax_cum.plot(t, log.cumulative_modal_injected(), color=color,
                    label=f"{param_name}={val:g}")

    ax_modal.set_xlabel("time [s]")
    ax_modal.set_ylabel("E_modal [J]")
    ax_modal.set_title(f"E_modal vs t  —  {scene}/{mode}")
    ax_modal.legend(fontsize=8)
    ax_modal.grid(alpha=0.3)

    ax_cum.set_xlabel("time [s]")
    ax_cum.set_ylabel("∑ ΔE_modal_injected [J]")
    ax_cum.set_title(f"cumulative injection  —  {scene}/{mode}")
    ax_cum.legend(fontsize=8)
    ax_cum.grid(alpha=0.3)

    fig.suptitle(f"{param_name} sweep:  {scene}/{mode}", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ----------------------------------------------------------------------
# BJ-vs-rest-normal comparison (one scene/mode, two methods overlaid)
# ----------------------------------------------------------------------

def plot_bj_vs_rest_comparison(
    log_patch_fit: EnergyLog,    # rest-normal (our patch_fit method)
    log_barbic_james: EnergyLog,  # Barbič-James deformed normal
    scene: str,
    mode: str,
    out_path: str | Path,
) -> Path:
    """Side-by-side energy curves for the two deformed-normal methods.

    `patch_fit` in our codebase is the rest-normal-style method (it uses
    the averaged rest normal as the kick direction); `barbic_james` is
    the full deformed-normal method (Barbič & James 2008 §4.1). The
    plot shows whether the deformed normal injects/extracts measurably
    different modal energy.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    ax_e, ax_cum, ax_alpha = axes

    for log, color, label in [
        (log_patch_fit, "#1f77b4", "patch_fit (rest normal)"),
        (log_barbic_james, "#d62728", "barbic_james (deformed normal)"),
    ]:
        if len(log) == 0:
            continue
        t = log.times()
        ax_e.plot(t, log.E_modal(), color=color, label=label)
        ax_cum.plot(t, log.cumulative_modal_injected(), color=color,
                    label=label)
        ax_alpha.plot(t, log.alpha(), color=color, label=label)

    ax_e.set_xlabel("time [s]")
    ax_e.set_ylabel("E_modal [J]")
    ax_e.set_title("E_modal(t)")
    ax_e.legend(fontsize=8)
    ax_e.grid(alpha=0.3)

    ax_cum.set_xlabel("time [s]")
    ax_cum.set_ylabel("∑ ΔE_modal_injected [J]")
    ax_cum.set_title("Cumulative injection")
    ax_cum.legend(fontsize=8)
    ax_cum.grid(alpha=0.3)

    ax_alpha.set_xlabel("time [s]")
    ax_alpha.set_ylabel("α")
    ax_alpha.set_ylim(-0.05, 1.1)
    ax_alpha.set_title("α (passive scaling)")
    ax_alpha.legend(fontsize=8)
    ax_alpha.grid(alpha=0.3)

    fig.suptitle(f"deformed-normal method:  {scene}/{mode}", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path
