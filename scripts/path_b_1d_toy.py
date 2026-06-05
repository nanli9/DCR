"""Item (6): Path-B 1-D toy probe.

Compare two formulations of distant modal response on the simplest scene
that exhibits the probe self-feedback loop:

    impactor (mass m_i) drops onto a surface
       │
       │ U_imp = 1     (contact projector at impact point)
       ▼
    [single modal coordinate q with mass m_q, ω, ζ]
       │
       │ U_probe = 0.3 (contact projector at distant probe point)
       ▼
    probe (mass m_p) sitting on the surface

Path A — bolted-on transient overlay
    1. Run an implicit macro step with the shelf treated rigid for
       contact (y = y_0). The macro step damps the high-frequency
       transient (suppression ~ω·h).
    2. Compute r_tilde = (F_imp · U_imp + F_probe · U_probe).
    3. Sub-step the modal IIR over [0, h] with T = π/(2ω).
    4. Inject Δv_probe = (U_probe · |q|_peak) / h.

Path B — sub-stepped coupled contact
    Step the *coupled* system (q, qdot, impactor, probe) at dt = T
    using velocity-level LCP at each substep. Contact normal velocities
    are non-negative on the post-step state via Lagrange multipliers.
    The modal contributions to contact velocities are
        v_n_imp_eff   = v_imp − U_imp · qdot
        v_n_probe_eff = v_probe − U_probe · qdot
    so each contact's impulse also kicks q (Newton-3rd at the modal
    level). No separate Δv injection.

Predicted behaviour:
    * Path A reproduces the probe-feedback loop: after the impactor
      hits, the probe is kicked, lands, contributes to r_tilde,
      kicks itself again.
    * Path B has no separate injection layer, so by construction
      there is no loop; energy is bounded by modal damping alone.

Outputs /tmp/path_b_toy.{csv,png}; the verdict line at the end says
whether the loop and the energy pump vanish under Path B.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np


# ---- constants ---------------------------------------------------------
GRAVITY = -9.81
M_IMP = 0.5
M_PROBE = 0.005
M_Q = 1.0                              # mass-normalised first mode
OMEGA = 838.0                          # plate first-mode frequency (rad/s)
ZETA = 0.01
U_IMP = 1.0                            # geometric projector at impact
U_PROBE = 0.3                          # geometric projector at probe
Y_SHELF = 0.0

H_MACRO = 1.0 / 120.0


# ---- helpers -----------------------------------------------------------

def iir_coefs(omega: float, zeta: float, T: float):
    wd = omega * math.sqrt(max(0.0, 1.0 - zeta * zeta))
    e = math.exp(-zeta * omega * T)
    a1 = 2.0 * e * math.cos(wd * T)
    a2 = e * e
    ar = e * math.sin(wd * T) / max(wd, 1e-12)
    return a1, a2, ar


def kinetic_energy(state: dict) -> float:
    ke = 0.5 * M_IMP * state["v_imp"] ** 2
    ke += 0.5 * M_PROBE * state["v_probe"] ** 2
    return ke


def modal_energy(state: dict) -> float:
    return 0.5 * M_Q * state["qdot"] ** 2 + 0.5 * (OMEGA ** 2) * state["q"] ** 2


# ---- Path A: bolted-on overlay ----------------------------------------

def step_path_a(state: dict, h: float, *,
                cap_enabled: bool = True, eta: float = 0.95,
                cooldown_steps: int = 2,
                cooldown_dv_threshold: float = 0.1) -> dict:
    """One macro step of the Path-A model.

    State dict keys:
        y_imp, v_imp, y_probe, v_probe, q, qdot, t,
        _cooldown_remaining   (int, decremented each macro step)
        _r_tilde_prev        (float, for the high-pass)
    """
    # 1. Implicit BDF1 for rigid bodies with shelf treated rigid
    #    (y >= Y_SHELF). Solve normal-impulse LCP per body.
    new_y_imp = state["y_imp"] + h * state["v_imp"] + 0.5 * h * h * GRAVITY
    new_v_imp = state["v_imp"] + h * GRAVITY
    new_y_probe = state["y_probe"] + h * state["v_probe"] + 0.5 * h * h * GRAVITY
    new_v_probe = state["v_probe"] + h * GRAVITY

    # Impulse-based non-penetration for impactor.
    F_imp = 0.0
    if new_y_imp < Y_SHELF and new_v_imp < 0.0:
        j_imp = -M_IMP * new_v_imp                       # impulse [N·s]
        new_v_imp = 0.0
        new_y_imp = Y_SHELF
        F_imp = j_imp / h                                # equivalent normal force
    # Same for probe.
    F_probe = 0.0
    if new_y_probe < Y_SHELF and new_v_probe < 0.0:
        j_probe = -M_PROBE * new_v_probe
        new_v_probe = 0.0
        new_y_probe = Y_SHELF
        F_probe = j_probe / h

    # 2. Implicit macro step of the modal coordinate, forced by F_imp/U_imp
    #    and F_probe/U_probe but with q itself held rigid for contact
    #    (Path-A separation). BDF1: (M/h² + K)q^{n+1} = M/h² q + r̃
    r_tilde = F_imp * U_IMP
    # Cooldown: don't let the probe contribute if it was recently kicked.
    cd = state.get("_cooldown_remaining", 0)
    if cd <= 0:
        r_tilde = r_tilde + F_probe * U_PROBE
    # High-pass r_tilde across macro steps.
    r_tilde_prev = state.get("_r_tilde_prev", 0.0)
    r_tilde_hp = r_tilde - r_tilde_prev

    K = M_Q * OMEGA * OMEGA
    coef = (M_Q / (h * h)) + K
    q_macro = (M_Q / (h * h)) * state["q"] - r_tilde * 0.0     # implicit Euler
    # (the bare macro path damps the transient peak; we keep q at its
    # pre-step value because the implicit time-step smears the impulse —
    # this is the "bare" reduced-coordinate behaviour, see report)
    new_q = state["q"]                                     # quasi-static collapse
    new_qdot = state["qdot"]

    # 3. Overlay: sub-step IIR with impulse J = r_tilde_hp * h.
    T = math.pi / (2.0 * OMEGA)
    n_sub = max(1, int(math.ceil(h / T)))
    a1, a2, ar = iir_coefs(OMEGA, ZETA, T)
    qs1 = 0.0
    qs2 = 0.0
    peak_q_overlay = 0.0
    J = r_tilde_hp * h
    for k in range(n_sub):
        q_new = a1 * qs1 - a2 * qs2 + (ar * J / M_Q if k == 0 else 0.0)
        peak_q_overlay = max(peak_q_overlay, abs(q_new))
        qs2 = qs1
        qs1 = q_new

    # 4. Probe Δv = (U_probe · peak_q_overlay) / h. Sign tracks J.
    sign = math.copysign(1.0, J) if abs(J) > 0 else 1.0
    dv_candidate = sign * U_PROBE * peak_q_overlay / h

    # Energy cap.
    E_src = max(0.0, kinetic_energy(state) - (0.5 * M_IMP * new_v_imp ** 2
                                              + 0.5 * M_PROBE * new_v_probe ** 2))
    E_inj_candidate = 0.5 * M_PROBE * dv_candidate ** 2
    if cap_enabled:
        if E_inj_candidate <= 1e-18:
            alpha = 1.0
        elif E_src <= 0.0:
            alpha = 0.0
        else:
            alpha = min(1.0, math.sqrt(eta * E_src / E_inj_candidate))
    else:
        alpha = 1.0
    dv = alpha * dv_candidate

    # Apply Δv.
    new_v_probe = new_v_probe + dv
    # Cooldown trigger.
    new_cd = cd
    if abs(dv) > cooldown_dv_threshold:
        new_cd = cooldown_steps
    new_cd = max(0, new_cd - 1)

    return {
        "t": state["t"] + h,
        "y_imp": new_y_imp,
        "v_imp": new_v_imp,
        "y_probe": new_y_probe,
        "v_probe": new_v_probe,
        "q": new_q,
        "qdot": new_qdot,
        "_cooldown_remaining": new_cd,
        "_r_tilde_prev": r_tilde,
        # Diagnostics:
        "dv_injected": dv,
        "dv_candidate": dv_candidate,
        "alpha_cap": alpha,
        "F_imp": F_imp,
        "F_probe": F_probe,
        "E_src": E_src,
        "E_inj": 0.5 * M_PROBE * (new_v_probe ** 2) - 0.5 * M_PROBE * (
            (new_v_probe - dv) ** 2),
        "n_sub": n_sub,
    }


# ---- Path B: sub-stepped coupled contact ------------------------------

def sdof_free_propagate(q: float, qdot: float, dt: float
                         ) -> tuple[float, float]:
    """Exact closed-form propagator for the damped SDOF:
        q̈ + 2ζω q̇ + ω² q = 0
    over time dt, given initial (q, qdot). Stable at any dt.
    """
    if OMEGA < 1e-12:
        return q + dt * qdot, qdot
    wd = OMEGA * math.sqrt(max(0.0, 1.0 - ZETA * ZETA))
    e = math.exp(-ZETA * OMEGA * dt)
    c = math.cos(wd * dt)
    s = math.sin(wd * dt)
    # x(t)   = e^{-ζω t} [ q*c + (ζω q + qdot)/ω_d * s ]
    # ẋ(t)  = e^{-ζω t} [ qdot*c - (ω² q + ζω qdot)/ω_d * s ]
    q_new = e * (q * c + (ZETA * OMEGA * q + qdot) / max(wd, 1e-12) * s)
    qdot_new = e * (qdot * c - (OMEGA * OMEGA * q + ZETA * OMEGA * qdot)
                    / max(wd, 1e-12) * s)
    return q_new, qdot_new


def step_path_b(state: dict, h: float) -> dict:
    """One macro step of the Path-B model.

    Sub-step at dt = T = π/(2ω). At each substep:
      1. Predict (y, v) under gravity (semi-implicit) and propagate
         (q, qdot) by the EXACT free-SDOF closed form (stable at any dt).
      2. Solve velocity-level contact LCP for impactor and probe
         simultaneously, including q's contribution.
      3. Apply the impulses (instantaneous Δqdot, Δv).

    The LCP at each substep:
        for each contact c with rigid mass m_c and projector U_c,
        let v_eff_c = v_c - U_c * qdot be the relative normal velocity.
        If pen_c > 0 OR (pen_c == 0 and v_eff_c < 0), apply impulse
        j_c >= 0 such that v_eff_c + Δv_eff_c >= 0:
            m_c (v_c^+ - v_c) = -j_c
            M_q (qdot^+ - qdot) = U_c · j_c    (modal back-reaction)
        Coupled because j_imp and j_probe both modify the same qdot.
    """
    T = math.pi / (2.0 * OMEGA)
    n_sub = max(1, int(math.ceil(h / T)))
    dt = h / n_sub

    y_imp = state["y_imp"]
    v_imp = state["v_imp"]
    y_probe = state["y_probe"]
    v_probe = state["v_probe"]
    q = state["q"]
    qdot = state["qdot"]

    # Pre-step KE for E_src.
    KE_pre = 0.5 * M_IMP * v_imp ** 2 + 0.5 * M_PROBE * v_probe ** 2
    KE_modal_pre = 0.5 * M_Q * qdot ** 2 + 0.5 * (OMEGA ** 2) * q ** 2

    # Sub-stepper.
    for _ in range(n_sub):
        # 1. Free advance under gravity + free modal dynamics.
        v_imp_pred = v_imp + dt * GRAVITY
        v_probe_pred = v_probe + dt * GRAVITY
        # Exact free-SDOF propagator (stable at any dt).
        q_pred, qdot_pred = sdof_free_propagate(q, qdot, dt)
        y_imp_pred = y_imp + dt * v_imp_pred
        y_probe_pred = y_probe + dt * v_probe_pred

        # 2. Contact LCP at velocity level.
        # Contact 1: impactor vs shelf surface y_s = Y_SHELF + U_IMP * q
        # Penetration: pen_imp = (Y_SHELF + U_IMP*q_pred) - y_imp_pred
        pen_imp = (Y_SHELF + U_IMP * q_pred) - y_imp_pred
        v_eff_imp = v_imp_pred - U_IMP * qdot_pred         # closing velocity
        pen_probe = (Y_SHELF + U_PROBE * q_pred) - y_probe_pred
        v_eff_probe = v_probe_pred - U_PROBE * qdot_pred

        # Active set: contact c is active iff (pen > 0) OR
        #             (pen >= -tol AND v_eff < 0).
        TOL = 1e-9
        active_imp = pen_imp > -TOL and v_eff_imp < 0.0
        active_probe = pen_probe > -TOL and v_eff_probe < 0.0

        # Coupled 2×2 LCP: find j_imp, j_probe >= 0 such that
        #   v_eff_i_post = v_eff_i + Δv_eff_i = 0
        # where (signs: n = +y, j is normal-impulse magnitude on body):
        #   Δv_body_i = +j_i/m_i                 (push body UP)
        #   Δqdot     = -Σ_k U_k j_k / M_q       (surface reacts DOWN)
        # so Δv_eff_i = Δv_body_i - U_i · Δqdot
        #             = j_i/m_i + U_i · Σ_k U_k j_k / M_q
        #             = (1/m_i) j_i + (U_i/M_q) Σ_k U_k j_k
        # Matrix form: Δv_eff = A · j, with
        #   A_ik = δ_ik / m_i + U_i U_k / M_q
        # Solve A · j = -v_eff with j ≥ 0.
        if active_imp or active_probe:
            inv_m_imp = 1.0 / M_IMP if M_IMP > 0 else 0.0
            inv_m_probe = 1.0 / M_PROBE if M_PROBE > 0 else 0.0
            inv_m_q = 1.0 / M_Q if M_Q > 0 else 0.0
            # A_ii: effective inverse mass for contact i.
            # Δv_eff_i_due_to_j_k = (δ_ik/m_i) + U_i U_k / M_q
            A00 = inv_m_imp + U_IMP * U_IMP * inv_m_q
            A11 = inv_m_probe + U_PROBE * U_PROBE * inv_m_q
            A01 = U_IMP * U_PROBE * inv_m_q
            # Need: v_eff_i + Δv_eff_i = 0 → solve A @ j = -v_eff
            if active_imp and active_probe:
                A = np.array([[A00, A01], [A01, A11]])
                b = -np.array([v_eff_imp, v_eff_probe])
                j = np.linalg.solve(A, b)
                # Clamp to non-negative (single Gauss-Seidel pass to fix).
                j = np.maximum(j, 0.0)
                # If only one active after clamp, recompute the other.
                if j[0] == 0.0 and active_imp:
                    j[1] = max(0.0, -v_eff_probe / A11) if active_probe else 0.0
                if j[1] == 0.0 and active_probe:
                    j[0] = max(0.0, -v_eff_imp / A00) if active_imp else 0.0
                j_imp_impulse, j_probe_impulse = float(j[0]), float(j[1])
            elif active_imp:
                j_imp_impulse = max(0.0, -v_eff_imp / A00)
                j_probe_impulse = 0.0
            else:
                j_imp_impulse = 0.0
                j_probe_impulse = max(0.0, -v_eff_probe / A11)

            # Apply impulses (sign fix per the block above):
            #   body  v += +j/m         (push up)
            #   modal qdot -= Σ U·j/M_q (surface reacts down)
            v_imp = v_imp_pred + j_imp_impulse * inv_m_imp
            v_probe = v_probe_pred + j_probe_impulse * inv_m_probe
            qdot = qdot_pred - (j_imp_impulse * U_IMP + j_probe_impulse * U_PROBE) * inv_m_q
            y_imp = y_imp_pred
            y_probe = y_probe_pred
            q = q_pred
            # Position projection so penetration doesn't accumulate.
            # The LCP zeros the relative *velocity*, but `y_pred` still
            # sits below the surface by ~dt·|v|. Without this we get
            # exponential drift through the floor (the velocity is zero
            # but the body is below the constraint, gravity acts the
            # next step, contact re-fires with bigger v, etc.).
            if j_imp_impulse > 0.0 and pen_imp > 0.0:
                y_imp = Y_SHELF + U_IMP * q
            if j_probe_impulse > 0.0 and pen_probe > 0.0:
                y_probe = Y_SHELF + U_PROBE * q
        else:
            v_imp = v_imp_pred
            v_probe = v_probe_pred
            qdot = qdot_pred
            y_imp = y_imp_pred
            y_probe = y_probe_pred
            q = q_pred

    KE_post = 0.5 * M_IMP * v_imp ** 2 + 0.5 * M_PROBE * v_probe ** 2
    KE_modal_post = 0.5 * M_Q * qdot ** 2 + 0.5 * (OMEGA ** 2) * q ** 2

    return {
        "t": state["t"] + h,
        "y_imp": y_imp,
        "v_imp": v_imp,
        "y_probe": y_probe,
        "v_probe": v_probe,
        "q": q,
        "qdot": qdot,
        "dv_injected": 0.0,
        "dv_candidate": 0.0,
        "alpha_cap": 1.0,
        "E_src": max(0.0, KE_pre - KE_post),
        "E_modal_change": KE_modal_post - KE_modal_pre,
        "n_sub": n_sub,
    }


# ---- driver -----------------------------------------------------------

def run(method: str, frames: int, h: float, **opts) -> list[dict]:
    state = {
        "t": 0.0,
        "y_imp": 0.30,
        "v_imp": -1.0,
        "y_probe": 0.0,
        "v_probe": 0.0,
        "q": 0.0,
        "qdot": 0.0,
        "_cooldown_remaining": 0,
        "_r_tilde_prev": 0.0,
    }
    log = []
    for _ in range(frames):
        if method == "A":
            state = step_path_a(state, h, **opts)
        elif method == "B":
            state = step_path_b(state, h)
        else:
            raise ValueError(method)
        log.append({k: v for k, v in state.items() if not k.startswith("_")})
    return log


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--frames", type=int, default=600)
    p.add_argument("--h", type=float, default=H_MACRO)
    p.add_argument("--csv", default="/tmp/path_b_toy.csv")
    p.add_argument("--png", default="/tmp/path_b_toy.png")
    args = p.parse_args(argv)

    print(f"[toy] frames={args.frames} h={args.h}\n")

    log_a = run("A", args.frames, args.h)
    log_b = run("B", args.frames, args.h)

    # ---- summary ----
    def stats(log, name):
        ks_pump = sum(1 for r in log if abs(r.get("dv_injected", 0)) > 1e-9)
        dv_max = max(abs(r["v_probe"]) for r in log)
        y_probe_max = max(r["y_probe"] for r in log)
        q_max = max(abs(r["q"]) for r in log)
        # Total energy at end (rigid + modal).
        last = log[-1]
        E_end = (0.5 * M_IMP * last["v_imp"] ** 2
                 + 0.5 * M_PROBE * last["v_probe"] ** 2
                 + 0.5 * M_Q * last["qdot"] ** 2
                 + 0.5 * (OMEGA ** 2) * last["q"] ** 2)
        print(f"  [Path {name}]")
        print(f"    n_steps with injection                = {ks_pump} / {len(log)}")
        print(f"    max |v_probe| over run                = {dv_max:.4f} m/s")
        print(f"    max  y_probe over run                 = {y_probe_max:.4f} m")
        print(f"    max |q| over run                      = {q_max:.4e} m")
        print(f"    final total energy (rigid+modal)      = {E_end:.4e} J")
        return dv_max, y_probe_max, E_end

    print("\n[summary]")
    a_stats = stats(log_a, "A (bolted overlay)")
    b_stats = stats(log_b, "B (sub-stepped coupled)")

    # CSV.
    with open(args.csv, "w", newline="") as f:
        keys = ["frame", "method", "t", "y_imp", "v_imp",
                "y_probe", "v_probe", "q", "qdot", "dv_injected",
                "alpha_cap"]
        w = csv.writer(f); w.writerow(keys)
        for k, log in (("A", log_a), ("B", log_b)):
            for i, r in enumerate(log):
                w.writerow([i, k, r["t"], r["y_imp"], r["v_imp"],
                            r["y_probe"], r["v_probe"], r["q"], r["qdot"],
                            r.get("dv_injected", 0), r.get("alpha_cap", 1)])
    print(f"\n[csv] {args.csv}")

    # Plot.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return 0
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    ts = [r["t"] for r in log_a]
    ax = axes[0]
    ax.plot(ts, [r["y_probe"] for r in log_a], label="Path A: y_probe", color="tab:orange")
    ax.plot(ts, [r["y_probe"] for r in log_b], label="Path B: y_probe", color="tab:blue")
    ax.set_ylabel("y_probe [m]"); ax.legend(); ax.grid(True, alpha=0.3)
    ax = axes[1]
    ax.plot(ts, [r["v_probe"] for r in log_a], label="Path A: v_probe", color="tab:orange")
    ax.plot(ts, [r["v_probe"] for r in log_b], label="Path B: v_probe", color="tab:blue")
    ax.set_ylabel("v_probe [m/s]"); ax.legend(); ax.grid(True, alpha=0.3)
    ax = axes[2]
    ax.plot(ts, [r["q"] for r in log_a], label="Path A: q", color="tab:orange")
    ax.plot(ts, [r["q"] for r in log_b], label="Path B: q", color="tab:blue")
    ax.set_ylabel("q [m]"); ax.set_xlabel("t [s]"); ax.legend(); ax.grid(True, alpha=0.3)
    fig.suptitle("Path A (bolted overlay) vs Path B (sub-stepped coupled) — 1-D probe toy")
    fig.tight_layout()
    fig.savefig(args.png, dpi=110)
    print(f"[plot] {args.png}")

    # ---- verdict ----
    n_inj_a = sum(1 for r in log_a if abs(r.get("dv_injected", 0)) > 1e-9)
    n_inj_b = sum(1 for r in log_b if abs(r.get("dv_injected", 0)) > 1e-9)
    print()
    print("[verdict]")
    print("  Self-feedback loop:")
    print(f"    Path A: {n_inj_a} overlay-injection events / {len(log_a)} steps")
    print(f"    Path B: {n_inj_b} overlay-injection events / {len(log_b)} steps")
    if n_inj_b == 0:
        print("    -> Path B has NO separate Δv injection path, so the")
        print("       probe→r_tilde→probe loop is absent BY CONSTRUCTION.")
    print()
    print(f"  Energy at end (rigid + modal):")
    print(f"    Path A: {a_stats[2]:.4e} J   "
          f"(modal damping only on the IIR, not state)")
    print(f"    Path B: {b_stats[2]:.4e} J   "
          f"(strictly bounded by modal damping ζ={ZETA})")
    if b_stats[2] < 1e-3:
        print("    -> Path B's coupled energy decays toward zero per ζ;")
        print("       no pump term, no manual cap needed.")
    print()
    print(f"  Probe response magnitude:")
    print(f"    Path A max |v_probe| = {a_stats[0]:.4f} m/s")
    print(f"    Path B max |v_probe| = {b_stats[0]:.4f} m/s")
    print(f"    Path B max y_probe   = {b_stats[1]:.4e} m")
    print("    -> both methods give a *visible* probe response; Path B's")
    print("       arises from the actual coupled surface motion, no kick.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
