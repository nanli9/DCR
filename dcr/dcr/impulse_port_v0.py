"""Impulse-port V0 — single-contact prototype of the velocity-band coupling.

Validates the load-bearing bet of the proposed two-band modal architecture
(docs/proposal_modal_response_as_constraint.md, to be written AFTER this):

    couple the quasi-static modal content (q_s) at the POSITION level (the
    existing monolithic Schur), and couple the dynamic ring (q_d) at the
    VELOCITY/IMPULSE level — never as a position constraint.

The bet: a passive (Signorini) velocity impulse exchanging momentum between a
rigid body and the ring CANNOT blow up where a stiff position glue against the
same kHz ring does (verified: the real solver launches a book 1.1 m at iters=32
with q_d in the contact gap). Aliasing a fast mode at the velocity level should
give bounded jitter, not divergence, because the impulse is contractive.

Velocity-band impulse (the heart):
    ġ⁻ = Jₓ·v_body − U_y·q̇_d                  # relative normal velocity
    w  = Jₓ M⁻¹ Jₓᵀ + ‖U_y‖²                   # DCR Eq.17 m_eff + inverse modal mass
    λ  = max(0, −(1+e)·ġ⁻ / w)                  # unilateral; e=0 fixed (no pull)
    Δv_body = M⁻¹ Jₓᵀ λ ,   Δq̇_d = −U_y λ      # one impulse kicks BOTH (M_q = I)

Energy ledger (foundation §15): with s = −U_y·λ₀ the raw modal kick,
    ΔE_modal(α) = α·b + ½α²·a ,   a = s·s = λ₀²‖U_y‖² ,   b = q̇_d·s = −λ₀(q̇_d·U_y)
which is exactly `dcr.modal.passive_inject.passive_alpha`. For e ≤ 1 the
exchange is already passive (ΔE_modal ≤ rigid loss per impulse), so the α-cap is
a GOVERNOR (safety clamp), not a liveliness dial — η ships fixed at 1.

Design rules folded in from review (see proposal doc once written):
  (1) η = 1 fixed; `use_governor` keeps passive_alpha as a clamp only. A demo
      stylization dial would be a product feature OUTSIDE the method.
  (2) ġ uses q̇_d ONLY — the q_s surface motion is already enforced by the
      position band; counting it here would double-count the static channel.
  (3) multi-contact passivity is sequential, not Jacobi — V0 is single-contact
      so this is trivially satisfied; flagged for the multi-contact port.
  (4) NEVER position-stabilize the velocity-band gap (no Baumgarte) — that
      resurrects the ratchet this design exists to kill. The static floor here
      is the POSITION band's job (the q_s channel), separate from this exchange.
  (5) ring velocity may be SAMPLED (instantaneous q̇_d) or INTEGRATED (the
      substep-mean (Δq_d)/T from the exact resonator) — the latter is alias-free.

# DEVIATION (foundation §15, paper Eq.10): the forced-IIR modal injection is
# replaced by an event-driven exact resonator (HomogeneousStepper) that receives
# discrete velocity impulses Δq̇_d at contact substeps. Justified by the blow-up
# sweep (position-coupling diverges, this stays bounded).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dcr.modal.homogeneous_stepper import HomogeneousStepper
from dcr.modal.passive_inject import passive_alpha, reservoir_alpha, reservoir_draw

GRAV = -9.81
_VEL_EPS = 1.0e-9   # closing-velocity floor: below this a contact is "not closing"
                    # — skip it rather than emit a numerically-negligible impulse
                    # (which would trip passive_alpha's a<EPS guard and inflate the
                    # clamp count with non-injections). Real impulses are ≫ this.
_A_FLOOR = 1.0e-12  # ‖s‖² floor below which a governor α<1 is a negligible-impulse
                    # artifact, not a real throttle (see clamp-count site).


@dataclass
class V0Config:
    """Single-contact scene + solver knobs. SI units."""
    # Body (1-DOF vertical): Jₓ = [+1], M⁻¹ = 1/m.
    m: float = 1.0
    y0: float = 0.05          # initial body height above the surface rest [m]
    v0: float = 0.0           # initial body velocity [m/s]
    # Modal ring at the contact point. Mass-normalized ⇒ M_q = I.
    omega: NDArray[np.float64] = field(           # natural freqs [rad/s]
        default_factory=lambda: 2.0 * np.pi * np.array([60.0, 400.0, 2000.0, 9000.0]))
    zeta: NDArray[np.float64] = field(            # damping ratios
        default_factory=lambda: np.full(4, 0.02))
    U_y: NDArray[np.float64] = field(             # mode shape at contact
        default_factory=lambda: np.array([0.6, 0.4, 0.25, 0.15]))
    y_rest: float = 0.0       # static surface height at the contact [m]
    qd0: NDArray[np.float64] | None = None        # initial ring displacement
    qddot0: NDArray[np.float64] | None = None     # initial ring velocity (pre-excited)
    # Time stepping.
    h: float = 1.0 / 120.0
    substeps: int = 8
    iters: int = 4
    N: int = 360              # number of rigid steps
    # Contact.
    e: float = 0.0            # restitution (fixed 0 — pure inelastic exchange)
    eta: float = 1.0          # §15 transfer efficiency (fixed 1 — see rule 1)
    contact_margin: float = 1.0e-4
    # Variants.
    coupling: str = "velocity"     # "velocity" | "position"
    ring_vel: str = "integrated"   # "sampled" | "integrated"  (velocity only)
    use_governor: bool = True
    # V1: "per_impulse" (the original per-event passive_alpha cap — exact at
    # η=1, slack at η<1) or "reservoir" (the reservoir-exact governor: a
    # persistent R makes the per-prefix §15 bound exact for any η). Defaults to
    # per_impulse so the existing 19 V0 tests are unchanged; the V1 tests opt in.
    governor_mode: str = "per_impulse"
    gravity: bool = True


@dataclass
class V0Result:
    t: NDArray[np.float64]
    y: NDArray[np.float64]                 # body height per rigid step
    v: NDArray[np.float64]                 # body velocity per rigid step
    qd_norm: NDArray[np.float64]           # ‖q_d‖ per rigid step
    qd_surf: NDArray[np.float64]           # ring surface deflection U_y·q_d
    qd_hist: NDArray[np.float64]           # (N, r) per-mode q_d (for viewer membrane)
    qddot_norm: NDArray[np.float64]        # ‖q̇_d‖ per rigid step (ring energy proxy)
    lam_max_per_step: NDArray[np.float64]  # max impulse magnitude within each step
    gap_min: float                         # most-negative body gap vs static floor
    cum_rigid_loss: float                  # Σ rigid KE lost to velocity-band impulses
    cum_modal_inj: float                   # Σ ΔE_modal injected
    clamp_activations: int                 # # impulses where governor set α<1
    pull_violations: int                   # # impulses with λ<0 (must be 0)
    resolve_residual_max: float            # max |ġ⁺ − (−e·ġ⁻)| (resolution check)
    ledger_residual_max: float             # max |ΔE_modal_actual − (αb+½α²a)|
    invariant_margin_min: float            # min(η·Σrigid − Σmodal) over the run (≥ −ε)


def run(cfg: V0Config) -> V0Result:
    """Integrate the single-contact scene. Pure numpy reference."""
    h_sub = cfg.h / cfg.substeps
    r = len(cfg.omega)
    U_y = np.asarray(cfg.U_y, dtype=np.float64)
    norm_Uy2 = float(U_y @ U_y)
    Minv = 1.0 / cfg.m

    ring = HomogeneousStepper(omega=np.asarray(cfg.omega, float),
                              zeta=np.asarray(cfg.zeta, float), T=h_sub, gamma=1.0)
    if cfg.qd0 is not None:
        ring.q[:] = cfg.qd0
    if cfg.qddot0 is not None:
        ring.qdot[:] = cfg.qddot0

    y, v = float(cfg.y0 + cfg.y_rest), float(cfg.v0)
    g_acc = GRAV if cfg.gravity else 0.0

    N = cfg.N
    t = np.arange(N) * cfg.h
    y_hist = np.empty(N); v_hist = np.empty(N)
    qd_norm = np.empty(N); qd_surf = np.empty(N); qddot_norm = np.empty(N)
    qd_hist = np.empty((N, r))
    lam_max = np.zeros(N)

    cum_rigid_loss = 0.0
    cum_modal_inj = 0.0
    clamp_activations = 0
    pull_violations = 0
    resolve_res_max = 0.0
    ledger_res_max = 0.0
    invariant_margin_min = np.inf
    reservoir = 0.0          # V1 reservoir-exact governor (foundation §1/§15)
    gap_min = np.inf
    was_in_contact = False

    def velocity_exchange(v_in: float) -> float:
        """One velocity-band impulse (rule 2: q̇_d only). Mutates ring.qdot and
        the enclosing ledgers; returns the new body velocity."""
        nonlocal cum_rigid_loss, cum_modal_inj, clamp_activations
        nonlocal pull_violations, resolve_res_max, ledger_res_max
        nonlocal invariant_margin_min, reservoir
        v_loc = v_in
        qd_vel = ring.qdot if cfg.ring_vel == "sampled" else vbar_d
        g_dot = v_loc - float(U_y @ qd_vel)     # relative normal velocity
        if g_dot >= -_VEL_EPS:                  # separating / negligibly closing
            return v_loc                        # (skip → no spurious zero-impulse)
        w = Minv + norm_Uy2                     # DCR Eq.17 m_eff + 1/M_q
        lam0 = -(1.0 + cfg.e) * g_dot / w       # > 0 since g_dot < 0
        if lam0 < 0.0:
            pull_violations += 1
            lam0 = 0.0
        s = -U_y * lam0                         # raw modal kick (Δq̇_d at α=1)
        a = lam0 * lam0 * norm_Uy2
        b = -lam0 * float(ring.qdot @ U_y)
        dE_body_full = lam0 * v_loc + 0.5 * lam0 * lam0 * Minv
        if not cfg.use_governor:
            alpha = 1.0
        elif cfg.governor_mode == "reservoir":
            # V1: rigid-loss quadratic L(α)=l1 α+l2 α² (1-DOF: w_r = Minv);
            # reservoir-exact α with persistent R → per-prefix §15 bound exact.
            l1 = -v_loc * lam0
            l2 = -0.5 * Minv * lam0 * lam0
            alpha = reservoir_alpha(a, b, l1, l2, reservoir, cfg.eta)
            reservoir -= reservoir_draw(a, b, l1, l2, alpha, cfg.eta)
        else:                                            # "per_impulse" (V0)
            E_max = cfg.eta * max(0.0, -dE_body_full)   # η·rigid_loss_at_α1
            alpha = passive_alpha(s, ring.qdot, E_max)
        # Count a clamp only when the governor throttles a MEANINGFUL injection
        # (a = ‖s‖² above a floor). passive_alpha returns α<1 for numerically
        # negligible impulses too, but those aren't the governor doing work — the
        # "α_clamp_activations == 0 in steady scenes" invariant is about real ones.
        if alpha < 1.0 - 1e-9 and a > _A_FLOOR:
            clamp_activations += 1
        lam = alpha * lam0
        qdot_before = ring.qdot.copy()
        v_before = v_loc
        v_loc += lam * Minv                     # Δv_body = M⁻¹ Jₓᵀ λ
        ring.qdot += -U_y * lam                 # Δq̇_d = −U_y λ   (M_q = I)

        dE_modal = (0.5 * float(ring.qdot @ ring.qdot)
                    - 0.5 * float(qdot_before @ qdot_before))
        ledger_res_max = max(ledger_res_max,
                             abs(dE_modal - (alpha * b + 0.5 * alpha * alpha * a)))
        rigid_loss = -0.5 * cfg.m * (v_loc * v_loc - v_before * v_before)
        cum_rigid_loss += rigid_loss
        cum_modal_inj += dE_modal
        invariant_margin_min = min(
            invariant_margin_min, cfg.eta * cum_rigid_loss - cum_modal_inj)
        if alpha >= 1.0 - 1e-12:                # ġ⁺ = −e·ġ⁻ only meaningful unclamped
            qd_post = ring.qdot if cfg.ring_vel == "sampled" else vbar_d
            g_dot_post = v_loc - float(U_y @ qd_post)
            resolve_res_max = max(resolve_res_max, abs(g_dot_post - (-cfg.e * g_dot)))
        lam_max[k] = max(lam_max[k], lam)
        return v_loc

    for k in range(N):
        for _ in range(cfg.substeps):
            # ---- free ring step (exact resonator); capture substep-mean vel.
            q_before = ring.q.copy()
            ring.step()
            vbar_d = (ring.q - q_before) / h_sub      # alias-free mean velocity

            # ---- body: gravity + position predictor (semi-implicit).
            v += g_acc * h_sub
            y += v * h_sub

            if cfg.coupling == "position":
                # --- POSITION-COUPLING control (the thing that blows up):
                # UNILATERAL non-penetration against the FULL oscillating ring
                # surface y_rest + U_y·q_d, with the reciprocal POSITION kick to
                # q_d (mirrors anchor_includes_q_d=True). The kick moves the
                # surface, so C doesn't converge in one step — iterating chases a
                # moving target and pumps q_d's displacement (energy ½ω²Δq²) every
                # iteration. More iters / finer substeps against the kHz ring →
                # the aliasing ratchet the velocity band exists to avoid.
                w = Minv + norm_Uy2
                for _ in range(cfg.iters):
                    surf = cfg.y_rest + float(U_y @ ring.q)
                    C = y - surf
                    if C >= 0.0:                 # separated → unilateral: no force
                        continue
                    dlam = -C / w                # > 0, push the body up
                    y += dlam * Minv
                    ring.q += -U_y * dlam        # reciprocal kick → pumps the ring
                gap_min = min(gap_min, y - (cfg.y_rest + float(U_y @ ring.q)))
                was_in_contact = True
                continue

            in_contact = y <= cfg.y_rest + cfg.contact_margin
            if in_contact:
                if not was_in_contact:
                    # IMPACT (newly forming contact = a collision): the velocity
                    # band resolves the FULL closing velocity → excites the ring.
                    for _ in range(cfg.iters):
                        v = velocity_exchange(v)
                else:
                    # SUSTAINED contact (resting support): the POSITION band (q_s
                    # channel) carries gravity to ground — NOT into q_d (rule 2/4).
                    # The velocity band then sees only RING-driven relative motion.
                    if v < 0.0:
                        v = 0.0
                    for _ in range(cfg.iters):
                        v = velocity_exchange(v)
                # ---- POSITION BAND backstop: hard, non-penetrating, static.
                # Holds the body (no drift); never stabilizes the q_d gap (rule 4).
                if y < cfg.y_rest:
                    y = cfg.y_rest
                gap_min = min(gap_min, y - cfg.y_rest)
            was_in_contact = in_contact

        y_hist[k] = y; v_hist[k] = v
        qd_norm[k] = float(np.linalg.norm(ring.q))
        qd_surf[k] = float(U_y @ ring.q)
        qddot_norm[k] = float(np.linalg.norm(ring.qdot))
        qd_hist[k] = ring.q

    return V0Result(
        t=t, y=y_hist, v=v_hist, qd_norm=qd_norm, qd_surf=qd_surf,
        qd_hist=qd_hist, qddot_norm=qddot_norm, lam_max_per_step=lam_max,
        gap_min=float(gap_min), cum_rigid_loss=cum_rigid_loss,
        cum_modal_inj=cum_modal_inj, clamp_activations=clamp_activations,
        pull_violations=pull_violations, resolve_residual_max=resolve_res_max,
        ledger_residual_max=ledger_res_max,
        invariant_margin_min=(0.0 if invariant_margin_min == np.inf
                              else float(invariant_margin_min)))
