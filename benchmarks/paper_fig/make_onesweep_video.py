#!/usr/bin/env python3
"""One-sweep row-danger-index video: predict the energy-sign boundary before the solve.

A five-beat diagnostic built ENTIRELY from a frozen trajectory bundle produced by
the data agent (onesweep_video_traj.npz + video_data_summary.json). Every frame of
motion is a real logged solver step; every on-screen scalar (rho, energies, ratios,
omega*h) is read from the bundle, never hand-typed.

Beats (target ~52 s):
  0. 0--5 s   SETUP: rigid impactor / unilateral contact row / restorative surface;
              define the row danger index rho = L/(w_m + 2*alpha_tilde) and the rule
              "predict before you solve". Scope in small text.
  1. 5--18 s  PREDICT + PLAY, mass-only weight + backward-Euler reconstruction:
              rho = 2.64 > 1 predicts injection; the logged impact plays; the energy
              ledger crosses the incident-KE budget and the corner over-penetrates.
  2. 18--30 s FIX, implicit weight + backward-Euler: price the row at the effective
              mass m_eff; rho_impl < 1; the SAME incident state replays and the ledger
              stays below the budget (passive, one sweep, backward-Euler recon.).
  3. 30--45 s TWIST, implicit weight + the SHIPPED symplectic reconstruction
              (q_dot = 2*dq/h, 4x modal KE): the corrected index rho_mid > 1; the same
              implicit weight no longer saves it -- the ledger climbs and stays above
              the budget.
  4. 45--52 s CODA: the three ledgers overlaid + the takeaway rule, then a short
              "no modes required" thumbnail of a plain scalar mass-spring row injecting
              above its own energy-sign boundary.

The injection PHENOMENON (finite-iteration coupling depositing spurious energy) is a
known effect and is conceded on screen; the contribution shown here is the per-row
ENERGY-SIGN predictor rho, read from the contact row before the solve.

Run (needs ffmpeg on PATH):
  .venv/bin/python benchmarks/paper_fig/make_onesweep_video.py
  .venv/bin/python benchmarks/paper_fig/make_onesweep_video.py --quick   # fast iterate
  .venv/bin/python benchmarks/paper_fig/make_onesweep_video.py --fps 24
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

# ---- writable matplotlib cache BEFORE importing matplotlib (binding rule) ---- #
os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mplcache_onesweep_")

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrowPatch, Circle

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Reuse the paper-figure palette so the arm colours read as the same system.
from benchmarks.paper_fig.figstyle import PALETTE          # noqa: E402

# ----------------------------- dark-theme constants (match the video look) --- #
FPS_DEFAULT = 30
W_IN, H_IN, DPI = 16.0, 9.0, 120                # 1920 x 1080 (even dims)
BG = "#0f1116"
FG = "#e8e8ea"
DIM = "#9aa0a8"
PANEL = "#161a22"
GRID = "#2a2f3a"

# Arm colours: injecting arms are warm, the passive arm is green.
C_MASS = PALETTE["clamp_off"]     # vermillion  -- mass-only / injects
C_IMPL = "#4ea36b"                # green       -- implicit weight / passive (BE)
C_SYMP = PALETTE["dcr"]           # orange      -- implicit weight / injects (symplectic)
INCIDENT_C = "#c8ccd2"
INJECT_FILL = "#D55E00"
BOARD_C = "#3a4152"

DATA_DIR = os.path.join(_ROOT, "benchmarks", "paper_fig", "out", "onesweep_data")
NPZ_PATH = os.path.join(DATA_DIR, "onesweep_video_traj.npz")
OUT_MP4 = os.path.join(_ROOT, "benchmarks", "paper_fig", "out", "onesweep_video.mp4")

ARMS = ("MASS_BE", "IMPL_BE", "IMPL_SYMP")
ARM_C = {"MASS_BE": C_MASS, "IMPL_BE": C_IMPL, "IMPL_SYMP": C_SYMP}

FOOTER = ("Finite-iteration coupling can inject energy: a known effect.  "
          r"$\rho$ is a per-row energy-sign predictor, read before the solve.")


# --------------------------------------------------------------------------- #
# data bundle                                                                 #
# --------------------------------------------------------------------------- #
class Bundle:
    """Thin accessor over the frozen npz; scalars as float/bool, series as arrays."""

    def __init__(self, path):
        self.d = np.load(path, allow_pickle=True)
        self.nsub = int(self.d["nsub"])
        self.step = np.asarray(self.d["t_substep"], dtype=float)   # 1..nsub
        self.h = float(self.d["h"])

    def s(self, key):                       # scalar float
        return float(self.d[key])

    def a(self, key):                       # 1-D series
        return np.asarray(self.d[key], dtype=float)


# --------------------------------------------------------------------------- #
# frame writer + ffmpeg (anonymous, even dims, yuv420p)                        #
# --------------------------------------------------------------------------- #
class Writer:
    def __init__(self, d):
        self.d = d
        self.n = 0

    def add(self, fig, times=1):
        p = os.path.join(self.d, f"f{self.n:05d}.png")
        fig.savefig(p, dpi=DPI, facecolor=BG)
        for _ in range(times - 1):
            self.n += 1
            shutil.copyfile(p, os.path.join(self.d, f"f{self.n:05d}.png"))
        self.n += 1


def new_fig():
    fig = plt.figure(figsize=(W_IN, H_IN), facecolor=BG)
    return fig


def _style_axes(ax):
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_color(GRID)
        sp.set_linewidth(1.0)
    ax.tick_params(colors=DIM, labelsize=11, length=3)
    ax.grid(True, color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)


def header(fig, title, subtitle=None, beat_tag=None):
    fig.text(0.5, 0.957, title, ha="center", va="center", fontsize=27,
             color=FG, fontweight="bold")
    if subtitle:
        fig.text(0.5, 0.910, subtitle, ha="center", va="center", fontsize=15,
                 color=DIM)
    if beat_tag:
        fig.text(0.032, 0.965, beat_tag, ha="left", va="center", fontsize=13,
                 color=DIM, fontweight="bold")


def footer(fig):
    fig.text(0.5, 0.032, FOOTER, ha="center", va="center", fontsize=12.5,
             color=DIM)


def _fade(t, t0, dur):
    if t <= t0:
        return 0.0
    if t >= t0 + dur:
        return 1.0
    return (t - t0) / dur


def _eng(v):
    """Signed, three-sig-fig joules for callouts."""
    return f"{v:+.2f}"


# --------------------------------------------------------------------------- #
# reusable schematic pieces                                                   #
# --------------------------------------------------------------------------- #
def _impactor_poly(cx, corner_y, half=0.34, tilt=0.06, top_extra=0.0):
    """Square impactor whose lowest corner sits at (cx, corner_y)."""
    pts = np.array([[-half, -half], [half, -half], [half, half], [-half, half]])
    c, s = np.cos(tilt), np.sin(tilt)
    R = np.array([[c, -s], [s, c]])
    r = pts @ R.T
    lo = r[:, 1].min()
    r[:, 0] += cx
    r[:, 1] += corner_y - lo + top_extra
    return r


def draw_sideview(ax, B, arm, k, color, active_c):
    """Real-data side view: corner_y over-penetration + surf_disp modal ringing."""
    ax.clear()
    _style_axes(ax)
    ax.grid(False)
    corner = B.a(f"{arm}_corner_y")
    surf = B.a(f"{arm}_surf_disp")
    nact = B.a(f"{arm}_n_active")
    ki = min(k, B.nsub) - 1
    cy = corner[ki]
    sd = surf[ki]

    xg = np.linspace(-1.15, 1.15, 160)
    shape = np.cos(np.pi * xg / 2.4)          # fixed mode shape, real amplitude sd
    ysurf = sd * shape
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.02, 0.42)

    # rest reference
    ax.axhline(0.0, color=DIM, lw=1.2, ls=(0, (5, 3)), alpha=0.8)
    ax.text(1.12, 0.02, "rest", ha="right", va="bottom", color=DIM, fontsize=11)

    # deflected restorative (modal) surface -- the board fills below it
    ax.fill_between(xg, ysurf, -1.02, color=BOARD_C, alpha=0.55, zorder=1)
    ax.plot(xg, ysurf, color="#8ea0bf", lw=2.0, zorder=2)

    # impactor
    poly = _impactor_poly(0.0, cy, half=0.34, tilt=0.06)
    ax.add_patch(Polygon(poly, closed=True, facecolor=color, alpha=0.85,
                         edgecolor=FG, lw=1.4, zorder=4))

    # contact-row indicator at the leading corner (bright when the row is active)
    is_active = nact[ki] > 0.5
    cc = active_c if is_active else GRID
    ax.add_patch(Circle((0.0, cy), 0.05, facecolor=cc, edgecolor=FG,
                        lw=1.2, zorder=6))
    ax.text(0.5, -0.94,
            "contact row active  (" r"$\lambda > 0$" ")" if is_active
            else "contact row inactive",
            ha="center", va="center", fontsize=12,
            color=active_c if is_active else DIM, zorder=6)

    # penetration depth callout (real corner_y), fixed top-left so the moving
    # impactor never overlaps the readout
    ax.annotate("", xy=(-0.92, cy), xytext=(-0.92, 0.0),
                arrowprops=dict(arrowstyle="<->", color=FG, lw=1.3))
    ax.text(-1.05, -0.90, f"corner_y = {cy:+.2f} m", color=FG, fontsize=12.5,
            ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc=BG, ec=GRID))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("side view:  corner over-penetration  +  surface ring-up",
                 color=FG, fontsize=13, pad=8)


def draw_modal_panel(ax, B, arm, k, color, show_ratio=True, note=None):
    """Modal energy (KE+PE) rising, with the incident-rigid-KE line for scale.

    Context panel only.  A large modal ring does NOT by itself mean energy was
    created: the passive arm rings up to the same peak ratio (2.71x here),
    funded by rigid kinetic-energy loss.  The injection verdict is the sign of
    the cumulative ledger (draw_ledger_panel), never the ring height -- so the
    incident line is drawn as a scale reference, not a threshold.
    """
    ax.clear()
    _style_axes(ax)
    ax.tick_params(labelbottom=False)          # x-axis shared with ledger below
    x = B.step
    y = B.a(f"{arm}_modal_tot")
    inc = B.s("E_incident_rowvisible")
    ax.set_xlim(0, B.nsub)
    ax.set_ylim(0, 46)
    ax.axhline(inc, color=INCIDENT_C, lw=1.6, ls=(0, (6, 3)))
    ax.text(B.nsub * 0.985, inc + 1.0,
            f"incident rigid-KE seen by row = {inc:.2f} J  (scale, not a threshold)",
            ha="right", va="bottom", color=INCIDENT_C, fontsize=10.5)
    kk = max(1, min(k, B.nsub))
    ax.plot(x[:kk], y[:kk], color=color, lw=2.3)
    ax.plot(x[kk - 1], y[kk - 1], "o", color=color, ms=6)
    ax.set_ylabel("modal energy (J)", color=FG, fontsize=12)
    ax.set_title("modal ring-up  (context, not the verdict)",
                 color=FG, fontsize=13, pad=6)
    if show_ratio:
        pr = B.s(f"{arm}_peak_ratio_max")
        ax.text(0.03, 0.90, f"ring peak = {pr:.2f}x incident",
                transform=ax.transAxes, color=color, fontsize=12.5,
                fontweight="bold", va="top")
    if note:
        ax.text(0.03, 0.72, note, transform=ax.transAxes, color=DIM,
                fontsize=11, va="top")


def draw_ledger_panel(ax, B, arm, k, color, ylim=(-8.5, 20.5), title=True):
    """Energy ledger dE_cum: injection iff the trace rises above the 0 budget."""
    ax.clear()
    _style_axes(ax)
    x = B.step
    y = B.a(f"{arm}_dE_cum")
    ax.set_xlim(0, B.nsub)
    ax.set_ylim(*ylim)
    ax.axhline(0.0, color=INCIDENT_C, lw=1.8)
    ax.text(B.nsub * 0.985, 0.7, "incident-KE budget  (passivity bound)",
            ha="right", va="bottom", color=INCIDENT_C, fontsize=11)
    kk = max(1, min(k, B.nsub))
    xv, yv = x[:kk], y[:kk]
    ax.fill_between(xv, 0.0, yv, where=(yv > 0.0), color=INJECT_FILL,
                    alpha=0.22, interpolate=True)
    ax.plot(xv, yv, color=color, lw=2.6)
    ax.plot(xv[-1], yv[-1], "o", color=color, ms=7)
    ax.set_xlabel("solver step", color=FG, fontsize=12)
    ax.set_ylabel(r"energy ledger  $\Delta E_{\rm cum}$  (J)", color=FG, fontsize=12)
    if title:
        ax.set_title(r"the verdict:  ledger sign  "
                     r"(rises above the 0 budget $\Rightarrow$ injection)",
                     color=FG, fontsize=13, pad=6)


# --------------------------------------------------------------------------- #
# BEAT 0 -- setup schematic                                                    #
# --------------------------------------------------------------------------- #
def beat0(wr, B, fps):
    dur = 5.0
    n = max(1, int(round(dur * fps)))
    for i in range(n):
        t = i / fps
        fig = new_fig()
        header(fig, "Read the contact row before you solve it",
               beat_tag="SETUP")
        footer(fig)
        ax = fig.add_axes([0.055, 0.14, 0.52, 0.70])
        _style_axes(ax)
        ax.grid(False)
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.05, 1.15)
        ax.set_xticks([]); ax.set_yticks([])

        a_imp = _fade(t, 0.0, 0.7)
        a_row = _fade(t, 0.8, 0.7)
        a_spr = _fade(t, 1.7, 0.7)

        # restorative (modal) surface + board
        xg = np.linspace(-1.2, 1.2, 160)
        ysurf = -0.05 * np.cos(np.pi * xg / 2.5)
        ax.fill_between(xg, ysurf, -1.05, color=BOARD_C, alpha=0.5 * a_imp)
        ax.plot(xg, ysurf, color="#8ea0bf", lw=2.0, alpha=a_imp)
        if a_spr > 0:
            # a coil hinting the restorative DOF under the surface
            yy = np.linspace(-0.08, -0.6, 80)
            xx = 0.55 + 0.07 * np.sin(np.linspace(0, 7 * np.pi, 80))
            ax.plot(xx, yy, color="#7f8794", lw=1.8, alpha=a_spr)
            ax.text(0.66, -0.34, "restorative\n(modal) DOF  q", color=DIM,
                    fontsize=12, va="center", alpha=a_spr)

        # impactor
        if a_imp > 0:
            poly = _impactor_poly(-0.15, 0.06, half=0.30, tilt=0.06,
                                  top_extra=0.0)
            ax.add_patch(Polygon(poly, closed=True, facecolor=C_MASS,
                                 alpha=0.85 * a_imp, edgecolor=FG, lw=1.4))
            ax.text(-0.15, 0.72, "rigid impactor  M", color=FG, fontsize=12.5,
                    ha="center", alpha=a_imp)

        # unilateral contact row
        if a_row > 0:
            ax.add_patch(Circle((-0.15, 0.02), 0.045, facecolor=C_MASS,
                                edgecolor=FG, lw=1.0, alpha=a_row))
            ax.add_patch(FancyArrowPatch((-0.15, 0.42), (-0.15, 0.10),
                                         arrowstyle="-|>", mutation_scale=14,
                                         color=C_MASS, lw=2.0, alpha=a_row))
            ax.text(-0.02, 0.28,
                    "unilateral row\n" + r"$C = z - q \geq 0,\ \ \lambda \geq 0$",
                    color=FG, fontsize=12, va="center", alpha=a_row)

        # right-hand definition column
        a_rho = _fade(t, 2.6, 0.8)
        a_rule = _fade(t, 3.6, 0.7)
        fig.text(0.62, 0.78, "row danger index", color=FG, fontsize=17,
                 fontweight="bold", alpha=a_rho)
        fig.text(0.62, 0.70,
                 r"$\rho \;=\; \dfrac{L}{\,w_m + 2\,\tilde\alpha\,}$"
                 r"$\qquad L = h^2\,J M^{-1} K M^{-1} J^{\!\top}$",
                 color=FG, fontsize=17, alpha=a_rho)
        fig.text(0.62, 0.615,
                 r"inject $\Leftrightarrow \rho > 1$"
                 "     (an energy-sign boundary)",
                 color=INCIDENT_C, fontsize=15, alpha=a_rho)
        fig.text(0.62, 0.50, "predict before you solve", color=C_SYMP,
                 fontsize=22, fontweight="bold", alpha=a_rule)
        fig.text(0.62, 0.42,
                 r"$w_m$ = row mobility     $\tilde\alpha$ = contact compliance",
                 color=DIM, fontsize=12.5, alpha=a_rule)
        fig.text(0.62, 0.30,
                 "scope:  one sweep  ·  cold start  ·  e = 0  ·  hard contact"
                 "\nsingle contact row  ·  isolated impact",
                 color=DIM, fontsize=12.5, alpha=a_rule, va="top")
        wr.add(fig)
        plt.close(fig)


# --------------------------------------------------------------------------- #
# predict card (shared by beats 1-3)                                           #
# --------------------------------------------------------------------------- #
def _predict_lines(B, arm):
    subtitle = None
    if arm == "MASS_BE":
        title = "Arm 1  —  mass-only weight,  backward-Euler reconstruction"
        idx = B.s("rho")
        rows = [
            (r"weight  $w_q = 1/M_q$   (shipped mass-only)", FG),
            (fr"$L = {B.s('L'):.3f}$      $w_m = {B.s('w_m'):.3f}$"
             fr"      $\tilde\alpha = {B.s('a_tilde'):.2e}$", DIM),
            (r"$\rho = L/(w_m + 2\tilde\alpha) = "
             fr"{idx:.2f}\ \ >\ 1$", C_MASS),
        ]
        verdict = "prediction:  INJECTS"
        vc = C_MASS
    elif arm == "IMPL_BE":
        title = "Arm 2  —  implicit weight,  backward-Euler reconstruction"
        idx = B.s("rho_impl")
        rows = [
            (r"price the row at  $m_{\rm eff}=m\,(1+2\zeta\omega h+(\omega h)^2)$",
             FG),
            (fr"$w_m = {B.s('w_m'):.3f}\ \rightarrow\ "
             fr"w_{{\rm eff}} = {B.s('w_eff'):.3f}$", DIM),
            (fr"$\rho_{{\rm impl}} = {idx:.2f}\ \ <\ 1$", C_IMPL),
        ]
        verdict = "prediction:  PASSIVE"
        vc = C_IMPL
    else:
        # Shorter title so the centered header no longer occludes the "TWIST"
        # beat tag; the "same implicit weight" point moves to the subtitle.
        title = "Arm 3  —  the shipped symplectic reconstruction"
        subtitle = (r"same implicit weight as arm 2  ·  host reconstructs  "
                    r"$\dot q^+ = 2\,\Delta q/h$")
        idx = B.s("rho_mid")
        rows = [
            (r"the host reconstructs  $\dot q^+ = 2\,\Delta q/h$"
             r"   (4$\times$ modal KE)", FG),
            (r"midpoint index:  $\sum a_i b_i + 2\sum a_i > w_r + 2\tilde\alpha$",
             DIM),
            (fr"$\rho_{{\rm mid}} = {idx:.2f}\ \ >\ 1$", C_SYMP),
        ]
        verdict = "prediction:  INJECTS (again)"
        vc = C_SYMP
    return title, subtitle, rows, verdict, vc


def predict_card(wr, B, arm, seconds, fps, beat_tag):
    title, subtitle, rows, verdict, vc = _predict_lines(B, arm)
    fig = new_fig()
    header(fig, title, subtitle, beat_tag=beat_tag)
    footer(fig)
    y = 0.66
    for txt, col in rows:
        fig.text(0.5, y, txt, ha="center", va="center", fontsize=21, color=col)
        y -= 0.10
    fig.text(0.5, 0.30, verdict, ha="center", va="center", fontsize=30,
             color=vc, fontweight="bold")
    wr.add(fig, times=max(1, int(round(seconds * fps))))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# play segment (shared by beats 1-3)                                           #
# --------------------------------------------------------------------------- #
def _play_axes(fig):
    """Modal (context) panel on top, ledger (verdict) panel below, sharing the
    x-axis; a caption band sits in the gap between them."""
    ax_mod = fig.add_axes([0.075, 0.615, 0.45, 0.215])
    ax_led = fig.add_axes([0.075, 0.125, 0.45, 0.36])
    ax_side = fig.add_axes([0.60, 0.155, 0.365, 0.62])
    return ax_mod, ax_led, ax_side


def _play_caption(fig, caption):
    """Honest framing band between the ring (context) and the ledger (verdict):
    a large ring is not injection; the cumulative-ledger sign is the verdict."""
    if caption:
        fig.text(0.30, 0.556, caption, ha="center", va="center", fontsize=11,
                 color=FG, linespacing=1.4,
                 bbox=dict(boxstyle="round,pad=0.45", fc=PANEL, ec=GRID))


def play(wr, B, arm, seconds, fps, beat_tag, title, subtitle,
         modal_note=None, verdict=None, hold_end=0.0, caption=None):
    color = ARM_C[arm]
    P = max(2, int(round(seconds * fps)))
    for i in range(P):
        k = 1 + int(round(i / (P - 1) * (B.nsub - 1)))
        fig = new_fig()
        header(fig, title, subtitle, beat_tag=beat_tag)
        footer(fig)
        ax_mod, ax_led, ax_side = _play_axes(fig)
        draw_modal_panel(ax_mod, B, arm, k, color, show_ratio=True,
                         note=modal_note)
        draw_ledger_panel(ax_led, B, arm, k, color)
        draw_sideview(ax_side, B, arm, k, color, color)
        _play_caption(fig, caption)

        # live stat callouts on the ledger
        dEmax = B.s(f"{arm}_dE_cum_max")
        dEfin = B.s(f"{arm}_dE_cum_final")
        cur = B.a(f"{arm}_dE_cum")[min(k, B.nsub) - 1]
        stat = (fr"$\Delta E$ now = {_eng(cur)} J"
                f"\npeak = {_eng(dEmax)} J   final = {_eng(dEfin)} J")
        ax_led.text(0.03, 0.05, stat, transform=ax_led.transAxes, color=FG,
                    fontsize=12, va="bottom",
                    bbox=dict(boxstyle="round,pad=0.35", fc=BG, ec=GRID))
        if verdict:
            vtxt, vc = verdict
            fig.text(0.782, 0.115, vtxt, ha="center", va="center", fontsize=20,
                     color=vc, fontweight="bold")
        wr.add(fig)
        plt.close(fig)
    if hold_end > 0:
        # re-render the final frame and hold it
        k = B.nsub
        fig = new_fig()
        header(fig, title, subtitle, beat_tag=beat_tag)
        footer(fig)
        ax_mod, ax_led, ax_side = _play_axes(fig)
        draw_modal_panel(ax_mod, B, arm, k, color, show_ratio=True,
                         note=modal_note)
        draw_ledger_panel(ax_led, B, arm, k, color)
        draw_sideview(ax_side, B, arm, k, color, color)
        _play_caption(fig, caption)
        dEmax = B.s(f"{arm}_dE_cum_max")
        dEfin = B.s(f"{arm}_dE_cum_final")
        stat = (fr"$\Delta E$ final = {_eng(dEfin)} J"
                f"\npeak = {_eng(dEmax)} J")
        ax_led.text(0.03, 0.05, stat, transform=ax_led.transAxes, color=FG,
                    fontsize=12, va="bottom",
                    bbox=dict(boxstyle="round,pad=0.35", fc=BG, ec=GRID))
        if verdict:
            vtxt, vc = verdict
            fig.text(0.782, 0.115, vtxt, ha="center", va="center", fontsize=20,
                     color=vc, fontweight="bold")
        wr.add(fig, times=max(1, int(round(hold_end * fps))))
        plt.close(fig)


# --------------------------------------------------------------------------- #
# BEAT 4 -- coda: overlay + nonmodal thumbnail                                 #
# --------------------------------------------------------------------------- #
def coda_overlay(wr, B, seconds, fps):
    P = max(2, int(round(seconds * fps)))
    for i in range(P):
        k = 1 + int(round(i / (P - 1) * (B.nsub - 1)))
        fig = new_fig()
        header(fig, "One rule for all three arms",
               "read " r"$\rho$ from the contact row, with the host's "
               "reconstruction, before the solve", beat_tag="CODA")
        footer(fig)
        ax = fig.add_axes([0.09, 0.16, 0.60, 0.64])
        _style_axes(ax)
        x = B.step
        ax.set_xlim(0, B.nsub)
        ax.set_ylim(-8.5, 20.5)
        ax.axhline(0.0, color=INCIDENT_C, lw=1.8)
        ax.text(B.nsub * 0.985, 0.7, "incident-KE budget",
                ha="right", va="bottom", color=INCIDENT_C, fontsize=11)
        labels = {
            "MASS_BE": (r"mass-only, BE:  $\rho=%.2f$" % B.s("rho"), C_MASS),
            "IMPL_BE": (r"implicit, BE:  $\rho_{\rm impl}=%.2f$" % B.s("rho_impl"),
                        C_IMPL),
            "IMPL_SYMP": (r"implicit, symplectic:  $\rho_{\rm mid}=%.1f$"
                          % B.s("rho_mid"), C_SYMP),
        }
        for arm in ARMS:
            y = B.a(f"{arm}_dE_cum")
            kk = max(1, min(k, B.nsub))
            lab, col = labels[arm]
            ax.plot(x[:kk], y[:kk], color=col, lw=2.6, label=lab)
            ax.plot(x[kk - 1], y[kk - 1], "o", color=col, ms=6)

        # The two backward-Euler ledgers coincide after the impact substep and
        # both end net-negative; the inject-vs-passive split for them lives in
        # the impact-substep sign (mass crosses the budget, implicit stays
        # under), not in the coincident tails.  Mark it honestly.
        xt0 = x[0]
        mpost = B.s("MASS_BE_dE_post")
        ipost = B.s("IMPL_BE_dE_post")
        ax.plot([xt0], [mpost], "o", color=C_MASS, ms=8, zorder=6)
        ax.plot([xt0], [ipost], "o", color=C_IMPL, ms=8, zorder=6)
        ax.annotate(f"{mpost:+.2f} J  (crosses)", (xt0, mpost),
                    textcoords="offset points", xytext=(11, 3),
                    color=C_MASS, fontsize=10.5, fontweight="bold", va="bottom")
        ax.annotate(f"{ipost:+.2f} J  (stays under)", (xt0, ipost),
                    textcoords="offset points", xytext=(11, -3),
                    color=C_IMPL, fontsize=10.5, fontweight="bold", va="top")
        ax.set_xlabel("solver step", color=FG, fontsize=13)
        ax.set_ylabel(r"energy ledger  $\Delta E_{\rm cum}$  (J)", color=FG,
                      fontsize=13)
        leg = ax.legend(loc="upper left", fontsize=12, facecolor=PANEL,
                        edgecolor=GRID, labelcolor=FG)
        leg.get_frame().set_alpha(0.9)

        # takeaway column
        fig.text(0.725, 0.72, "the takeaway", color=FG, fontsize=17,
                 fontweight="bold")
        fig.text(0.725, 0.575,
                 "the weight that saves the\nbackward-Euler step (arm 2)\n"
                 "does not save the shipped\nsymplectic step (arm 3):\n"
                 "the index must use the\nhost's reconstruction.",
                 color=DIM, fontsize=13.5, va="top")
        fig.text(0.725, 0.30,
                 "mass-only:  injects\nimplicit + BE:  passive\n"
                 "implicit + symplectic:  injects",
                 color=FG, fontsize=13.5, va="top")
        fig.text(0.725, 0.175,
                 "(the two BE ledgers coincide over\n"
                 "the full sweep; their split is the\n"
                 fr"impact-substep sign: {mpost:+.2f} vs {ipost:+.2f} J)",
                 color=DIM, fontsize=11.5, va="top")
        wr.add(fig)
        plt.close(fig)


def coda_nonmodal(wr, B, seconds, fps):
    fig = new_fig()
    header(fig, "No modes required",
           "the same energy-sign boundary in a plain scalar mass-spring row",
           beat_tag="CODA")
    footer(fig)
    ax = fig.add_axes([0.13, 0.17, 0.74, 0.60])
    _style_axes(ax)
    b = B.a("nonmodal_b")
    dm = B.a("nonmodal_dE_mass")
    di = B.a("nonmodal_dE_impl")
    bnd = B.s("nonmodal_boundary_b")
    ax.set_xscale("log")
    ax.axhline(0.0, color=INCIDENT_C, lw=1.6)
    ax.axvline(bnd, color=DIM, lw=1.4, ls=(0, (5, 3)))
    ax.text(bnd * 1.05, ax.get_ylim()[1], "", color=DIM)
    ax.fill_between(b, 0.0, dm, where=(dm > 0.0), color=INJECT_FILL, alpha=0.20,
                    interpolate=True)
    ax.plot(b, dm, color=C_MASS, lw=2.6, label="mass-only weight")
    ax.plot(b, di, color=C_IMPL, lw=2.6, label="implicit weight")
    ax.set_xlabel(r"$(\omega h)^2$", color=FG, fontsize=14)
    ax.set_ylabel(r"one-sweep  $\Delta E$  (J)", color=FG, fontsize=13)
    ax.text(bnd * 1.08, 0.62 * ax.get_ylim()[1],
            r"boundary  $(\omega h)^2 = 1 + m/M = %.0f$" % bnd,
            color=DIM, fontsize=13)
    leg = ax.legend(loc="upper left", fontsize=13, facecolor=PANEL,
                    edgecolor=GRID, labelcolor=FG)
    leg.get_frame().set_alpha(0.9)
    fig.text(0.5, 0.10,
             "scalar M = m = 1;  mass-weight injects above the boundary,  "
             "implicit weight stays passive everywhere.  No eigenmodes anywhere.",
             ha="center", va="center", color=DIM, fontsize=13)
    wr.add(fig, times=max(1, int(round(seconds * fps))))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #
def build(wr, B, fps, quick):
    sc = 0.45 if quick else 1.0        # time compression for --quick

    beat0(wr, B, fps)

    # Beat 1 -- mass-only / BE: predict then play
    predict_card(wr, B, "MASS_BE", 3.0 * sc, fps, "PREDICT")
    play(wr, B, "MASS_BE", 10.0 * sc, fps, "PLAY  ·  arm 1",
         "mass-only weight  ·  backward-Euler reconstruction",
         r"$\rho = %.2f > 1$   ->   the ledger crosses the 0 budget at the "
         r"impact substep (injection)" % B.s("rho"),
         modal_note="ring size alone does not decide the sign",
         verdict=("INJECTS", C_MASS),
         caption=(
             "A large modal ring is not injection: the implicit-weight arm "
             "rings up the\nsame %.2fx too, funded by rigid-KE loss.  The "
             "verdict is the ledger sign\n-- at the impact substep this arm "
             "reads %+.2f J (crosses) vs %+.2f J implicit."
             % (B.s("IMPL_BE_peak_ratio_max"), B.s("MASS_BE_dE_post"),
                B.s("IMPL_BE_dE_post"))))

    # Beat 2 -- implicit / BE: fix
    predict_card(wr, B, "IMPL_BE", 2.5 * sc, fps, "FIX")
    play(wr, B, "IMPL_BE", 9.5 * sc, fps, "PLAY  ·  arm 2",
         "implicit weight  ·  backward-Euler reconstruction",
         r"$\rho_{\rm impl} = %.2f < 1$   ->   same incident state, ledger "
         r"stays under the budget" % B.s("rho_impl"),
         modal_note="same-size ring, funded by rigid-KE loss",
         verdict=("PASSIVE", C_IMPL),
         caption=(
             "Same %.2fx ring as arm 1 (funded by rigid-KE loss), but the "
             "ledger never\ncrosses the 0 budget: passive by the ledger sign, "
             "not by a smaller ring." % B.s("IMPL_BE_peak_ratio_max")))

    # Beat 3 -- implicit / symplectic: twist
    predict_card(wr, B, "IMPL_SYMP", 4.0 * sc, fps, "TWIST")
    play(wr, B, "IMPL_SYMP", 10.0 * sc, fps, "PLAY  ·  arm 3",
         "implicit weight  ·  the shipped symplectic reconstruction",
         r"$\rho_{\rm mid} = %.1f > 1$   ->   same weight, the ledger climbs "
         r"and stays above the budget" % B.s("rho_mid"),
         modal_note=r"$\dot q^+ = 2\,\Delta q/h$  ->  4$\times$ modal KE",
         verdict=("INJECTS", C_SYMP), hold_end=1.0 * sc,
         caption=(
             "Here the ledger climbs above the 0 budget and stays there: the "
             "same implicit\nweight no longer saves the sign under the shipped "
             "symplectic reconstruction."))

    # Beat 4 -- coda
    coda_overlay(wr, B, 4.0 * sc, fps)
    coda_nonmodal(wr, B, 3.0 * sc, fps)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="fewer frames / shorter holds for fast iteration")
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--out", default=OUT_MP4)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    fps = args.fps if args.fps else (12 if args.quick else FPS_DEFAULT)
    B = Bundle(NPZ_PATH)

    tmp = tempfile.mkdtemp(prefix="onesweep_frames_")
    try:
        wr = Writer(tmp)
        build(wr, B, fps, args.quick)
        dur = wr.n / fps
        print(f"rendered {wr.n} frames ({dur:.1f} s at {fps} fps)")
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        cmd = ["ffmpeg", "-y", "-framerate", str(fps),
               "-i", os.path.join(tmp, "f%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
               "-map_metadata", "-1",
               "-movflags", "+faststart", args.out]
        subprocess.run(cmd, check=True, capture_output=True)
        mb = os.path.getsize(args.out) / 1e6
        print(f"wrote {args.out}  ({mb:.1f} MB, {dur:.1f} s, {fps} fps)")
    finally:
        if args.keep_frames:
            print(f"frames kept in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
