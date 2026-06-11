"""Velocity-band passive impulse port for the real reduced-modal scenes (V2-lite).

The position band (the existing reduced-coupled coupler) deforms the support and
carries the static sag `q_s`. This module adds the **dynamic band**: a per-step
host pass that lets resting bodies feel the modal ring `q̇_d` through a **passive
momentum exchange**, not a position anchor — the architecture of
`docs/proposal_modal_response_as_constraint.md` §3.2, validated at V0
(`dcr/dcr/impulse_port_v0.py`).

For each tracked body and each in-contact corner (support normal `n = +ŷ`,
body-frame offset → world `r`, modal column `U_y`):

    ġ = (v_lin + ω×r)·n − U_yᵀ q̇_d                       # relative normal velocity
    w = nᵀM⁻¹n + (r×n)ᵀ I⁻¹ (r×n) + ‖U_y‖²                # DCR Eq.17 m_eff + 1/M_q
    λ = max(0, −(1+e)·ġ / w)                              # unilateral; e fixed 0
    Δv_lin = λ n/m ,  Δω = I⁻¹(r×n)λ ,  Δq̇_d = −U_y λ      # one impulse, both sides

`passive_alpha` (foundation §15) governs injection; ships at η=1 (a clamp, not a
dial — V0 shows it never fires at η=1). Corners are applied **sequentially**
(rule 3: per-impulse passivity assumes one-at-a-time; Jacobi can over-extract).

Substrate note: use the FAITHFUL position band (XPBD, whose `q_s` is the true
sub-micron sag) so the velocity band is the SOLE body↔ring channel. On AVBD the
penalty-inflated `q_s` launches resting bodies airborne (a documented artifact),
so the band has no in-contact corners to act on — wrong substrate for this test.

Solver-agnostic: reads `inv_mass`/`inv_I` (XPBD, diagonal body-frame) or
`mass`/`inertia_local` (AVBD, mat33), and writes the shared `self.v`/`self.omega`.

# DEVIATION (foundation §15 / paper Eq.10): the body↔ring coupling is an
# event-driven passive impulse, not the forced one-way IIR. Host reference; the
# device-resident per-substep version is the V2 follow-up.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dcr.avbd.reduced_coupled_avbd import _quat_xyzw_to_R
from dcr.modal.passive_inject import reservoir_alpha, reservoir_draw

_N = np.array([0.0, 1.0, 0.0])     # support normal (scenes are ~horizontal slabs)
_VEL_EPS = 1.0e-9                  # closing-velocity floor (skip non-injections)
_A_FLOOR = 1.0e-12                 # ‖s‖² floor for counting a real governor clamp


@dataclass
class VelocityBandStats:
    n_impulses: int = 0
    clamp_activations: int = 0
    max_lambda: float = 0.0
    cum_modal_inj: float = 0.0
    cum_rigid_loss: float = 0.0
    invariant_margin_min: float = float("inf")
    reservoir: float = 0.0          # V1: banked-but-unspent budget η Σ L − Σ ΔE_modal


def _body_dynamics(solver):
    """Per-body (mass, R, pos, v_lin, omega, I_world, Iinv_world), solver-agnostic.
    XPBD stores inv_mass + diagonal body-frame inv_I; AVBD stores mass +
    full body-frame inertia_local. Both expose self.x, self.q (xyzw), v, omega."""
    pos = solver.x.numpy().astype(np.float64).reshape(-1, 3)
    quat = solver.q.numpy().astype(np.float64).reshape(-1, 4)   # xyzw
    v = solver.v.numpy().astype(np.float64).reshape(-1, 3)
    om = solver.omega.numpy().astype(np.float64).reshape(-1, 3)
    n_b = pos.shape[0]
    R = np.stack([_quat_xyzw_to_R(quat[i]) for i in range(n_b)])
    if getattr(solver, "inv_mass", None) is not None:           # XPBD
        inv_m = solver.inv_mass.numpy().astype(np.float64).reshape(-1)
        inv_I = solver.inv_I.numpy().astype(np.float64).reshape(-1, 3)  # diag, body
        mass = np.where(inv_m > 0, 1.0 / np.where(inv_m > 0, inv_m, 1.0), 0.0)
        Iinv_w = np.empty((n_b, 3, 3)); I_w = np.empty((n_b, 3, 3))
        for i in range(n_b):
            Iinv_w[i] = R[i] @ np.diag(inv_I[i]) @ R[i].T
            I_diag = np.where(inv_I[i] > 0, 1.0 / np.where(inv_I[i] > 0, inv_I[i], 1.0), 0.0)
            I_w[i] = R[i] @ np.diag(I_diag) @ R[i].T
    else:                                                        # AVBD
        mass = solver.mass.numpy().astype(np.float64).reshape(-1)
        I_loc = solver.inertia_local.numpy().astype(np.float64).reshape(-1, 3, 3)
        I_w = np.einsum("bij,bjk,blk->bil", R, I_loc, R)
        Iinv_w = np.array([np.linalg.inv(I_w[i]) if mass[i] > 0 else np.zeros((3, 3))
                           for i in range(n_b)])
    return mass, R, pos, v, om, I_w, Iinv_w


def apply_velocity_band(coupler, solver, *, eta: float = 1.0, e: float = 0.0,
                        margin: float = 5.0e-3, governor: bool = True,
                        ) -> VelocityBandStats:
    """Apply one per-step velocity-band impulse exchange between the tracked
    bodies and the modal ring `q̇_d`. Mutates `solver.v`, `solver.omega`, and
    `coupler.rs.qdot_d` in place. Returns per-step diagnostics. Call AFTER
    `world.step()` (the coupler's per-corner caches reflect the last substep).

    V1 governor (foundation §1/§6/§15): a persistent reservoir `R ≥ 0` (banked
    on `coupler._modal_reservoir`) holds unspent budget `η Σ L − Σ ΔE_modal`.
    Each impulse may draw at most `R` via `reservoir_alpha`; debit `R ← R − D(α)`
    keeps it ≥0, so `Σ ΔE_modal ≤ η Σ L` holds at EVERY prefix for any η — the
    per-prefix rigor the old per-impulse `passive_alpha` lacked at η<1. The
    reservoir is the shared support's (one modal field; all bodies couple to it),
    so it is a single scalar, debited sequentially per corner (design rule 3)."""
    rs = coupler.rs
    st = VelocityBandStats()
    tracked = getattr(coupler, "tracked_body_indices", None)
    if not tracked or rs.qdot_d is None:
        st.invariant_margin_min = 0.0
        st.reservoir = float(getattr(coupler, "_modal_reservoir", 0.0))
        return st
    reservoir = float(getattr(coupler, "_modal_reservoir", 0.0))

    qd = np.asarray(rs.qdot_d, dtype=np.float64).copy()
    q_s = np.asarray(rs.q_s, dtype=np.float64)
    # Support contact reference: shelf_y_rest + U_y·q_s (both couplers expose
    # shelf_y_rest; only AVBD populates rs.floor_y_rest, so don't rely on it).
    shelf_y_rest = float(getattr(coupler, "shelf_y_rest", 0.0))
    mass, R, pos, v_np, w_np, I_w, Iinv_w = _body_dynamics(solver)

    for b in tracked:
        idx = coupler._row_idx_by_body.get(b)
        if idx is None or len(idx) == 0 or mass[b] <= 0.0:
            continue
        off_arr = coupler._row_off_by_body[b]      # (nc, 3) body frame
        U_arr = coupler._row_U_y_by_body[b]        # (nc, r)
        m = float(mass[b]); Iinv = Iinv_w[b]; Iw = I_w[b]

        for j in range(off_arr.shape[0]):
            r_w = R[b] @ off_arr[j]
            surf_y = shelf_y_rest + float(U_arr[j] @ q_s)
            if float(pos[b][1] + r_w[1]) - surf_y > margin:      # separated
                continue
            U_y = U_arr[j]
            rxn = np.cross(r_w, _N)                              # (−r_z, 0, r_x)
            v_corner_y = float(v_np[b][1] + np.cross(w_np[b], r_w)[1])
            g_dot = v_corner_y - float(U_y @ qd)
            if g_dot >= -_VEL_EPS:                               # not closing
                continue
            w_eff = (1.0 / m) + float(rxn @ Iinv @ rxn) + float(U_y @ U_y)
            lam0 = max(0.0, -(1.0 + e) * g_dot / w_eff)
            if lam0 <= 0.0:
                continue

            s = -U_y * lam0
            a = float(s @ s)                         # a_m = ‖s‖²  (§15)
            b_m = float(qd @ s)                      # q̇·s        (§15)
            # Rigid-loss quadratic L(α) = l1·α + l2·α²  (foundation §15):
            #   ΔE_rigid(α) = v_corner_y·(α λ₀) + ½ w_r (α λ₀)²,  L = −ΔE_rigid
            #   w_r = rigid effective inverse mass = w_eff − ‖U_y‖² (≥0).
            w_r = w_eff - float(U_y @ U_y)
            l1 = -v_corner_y * lam0
            l2 = -0.5 * w_r * lam0 * lam0            # ≤ 0
            if governor:
                # Reservoir-exact governor (V1): largest α with the net draw
                # D(α)=ΔE_modal(α)−η·L(α) ≤ reservoir. Debit below keeps R≥0.
                alpha = reservoir_alpha(a, b_m, l1, l2, reservoir, eta)
            else:
                alpha = 1.0
            if alpha < 1.0 - 1e-9 and a > _A_FLOOR:
                st.clamp_activations += 1
            lam = alpha * lam0
            if governor:
                reservoir -= reservoir_draw(a, b_m, l1, l2, alpha, eta)

            qd_before = qd.copy(); v0 = v_np[b].copy(); w0 = w_np[b].copy()
            v_np[b][1] += lam / m
            w_np[b] += Iinv @ rxn * lam
            qd += -U_y * lam

            dE_modal = 0.5 * float(qd @ qd) - 0.5 * float(qd_before @ qd_before)
            dE_body = (0.5 * m * float(v_np[b] @ v_np[b] - v0 @ v0)
                       + 0.5 * float(w_np[b] @ Iw @ w_np[b] - w0 @ Iw @ w0))
            st.cum_modal_inj += dE_modal
            st.cum_rigid_loss += -dE_body
            st.invariant_margin_min = min(st.invariant_margin_min,
                                          eta * st.cum_rigid_loss - st.cum_modal_inj)
            st.n_impulses += 1
            st.max_lambda = max(st.max_lambda, lam)

    if st.n_impulses > 0:
        # assign() copies into the existing arrays in place, so a captured CUDA
        # graph still binds them and replays against the updated contents.
        solver.v.assign(v_np.astype(np.float32))
        solver.omega.assign(w_np.astype(np.float32))
        rs.qdot_d[:] = qd
    # Persist the reservoir across steps (V1): it carries banked-but-unspent
    # budget so the per-prefix §15 bound holds globally, not just per step.
    # NOT floored — `reservoir_alpha` guarantees D(α) ≤ R, so R stays ≥ 0 by
    # construction; leaving it unfloored lets a real violation surface (the
    # parity/per-prefix tests assert R ≥ −ε).
    coupler._modal_reservoir = reservoir
    st.reservoir = reservoir
    if st.invariant_margin_min == float("inf"):
        st.invariant_margin_min = 0.0
    return st


@dataclass
class FrictionStats:
    n_corners: int = 0          # in-contact corners that saw a friction impulse
    max_impulse: float = 0.0    # ‖p_t‖ max over corners this step
    tang_mom_removed: float = 0.0   # Σ ‖Δ(m v_t)‖ — diagnostic only


_G = 9.81                       # support normal force per body ≈ m·g (resting)


def _mu_of(solver, b: int) -> float:
    """Per-body Coulomb μ, solver-agnostic. XPBD stores a scalar `friction`;
    AVBD exposes per-body `friction` (else a scalar). Reuses the SAME μ the
    solver's own floor/box friction uses — no new knob."""
    mu = getattr(solver, "friction", None)
    if mu is not None:
        return float(mu)
    bodies = getattr(solver, "bodies", None)
    if bodies is not None and b < len(bodies):
        return float(getattr(bodies[b], "friction", 0.5))
    return 0.5


def apply_contact_friction(coupler, solver, *, mu: float | None = None,
                           margin: float = 5.0e-3, h: float = 1.0 / 120.0,
                           ) -> FrictionStats:
    """Dynamic Coulomb friction at the tracked bodies' shelf-contact corners.

    Tracked bodies are `floor_disabled` (the coupler owns their per-corner
    anchor), so the solver's own floor friction never touches them and the
    anchor is normal-only (`reduced_coupled_xpbd.py` J_x = [ŷ; r×ŷ]). With no
    tangential resistance, lateral momentum → constant slide and angular
    momentum about ŷ → constant yaw spin (the velocity band amplifies the spin
    ~600× by injecting per-corner angular impulses with no frictional sink).

    This restores the missing tangential channel as a STANDALONE velocity-level
    pass (runs band-on AND band-off). Per in-contact corner, in the SAME impulse
    formulation as `apply_velocity_band` (effective inverse mass `w_t`, impulse
    `λ_t`), it removes the tangential corner velocity, clamped to the Coulomb
    cone (Müller 2020 Eq. 30 — dynamic friction):

        v_c = v + ω×r ,  v_t = v_c − ŷ(ŷ·v_c)            # tangential corner vel
        t   = v_t/‖v_t‖ ,  w_t = 1/m + (r×t)·I⁻¹(r×t)    # band's m_eff, no modal
        λ_remove = ‖v_t‖ / w_t                           # impulse to fully cancel
        λ_n      = (m·g/n_c)·h                            # normal support share·h
        λ_t = min(λ_remove, μ·λ_n)                        # cone clamp
        Δv = −t λ_t/m ,  Δω = I⁻¹(r × −t λ_t)            # body-only reaction

    No modal term (U_y is normal-only, so friction is orthogonal to the ring) —
    the §15 energy bound and the band's passivity are untouched. λ_t ≤ λ_remove
    always, so friction never reverses v_t: it cannot add tangential energy.
    Mutates `solver.v`/`solver.omega` in place. Call AFTER `world.step()` (and
    after the band, if enabled). Zero new knobs: μ defaults to the solver's own.

    # DEVIATION (paper Eq.10 / foundation §15): friction is a body-side contact
    # term, not part of the modal coupling; it is orthogonal to the ring and so
    # does not enter the energy ledger. Device-resident fold mirrors the V2-B
    # band kernel (same per-corner structure).
    """
    st = FrictionStats()
    tracked = getattr(coupler, "tracked_body_indices", None)
    if not tracked:
        return st
    q_s = np.asarray(coupler.rs.q_s, dtype=np.float64)
    shelf_y_rest = float(getattr(coupler, "shelf_y_rest", 0.0))
    mass, R, pos, v_np, w_np, I_w, Iinv_w = _body_dynamics(solver)
    touched = False

    for b in tracked:
        idx = coupler._row_idx_by_body.get(b)
        if idx is None or len(idx) == 0 or mass[b] <= 0.0:
            continue
        off_arr = coupler._row_off_by_body[b]
        U_arr = coupler._row_U_y_by_body[b]
        m = float(mass[b]); Iinv = Iinv_w[b]
        mu_b = float(mu) if mu is not None else _mu_of(solver, b)
        if mu_b <= 0.0:
            continue

        # First pass: which corners are in contact (to split the normal load).
        in_contact = []
        for j in range(off_arr.shape[0]):
            r_w = R[b] @ off_arr[j]
            surf_y = shelf_y_rest + float(U_arr[j] @ q_s)
            if float(pos[b][1] + r_w[1]) - surf_y <= margin:
                in_contact.append((j, r_w))
        n_c = len(in_contact)
        if n_c == 0:
            continue
        lam_n = (m * _G / n_c) * h          # normal support impulse per corner
        lam_cap = mu_b * lam_n

        for j, r_w in in_contact:           # sequential (Gauss–Seidel, like band)
            v_c = v_np[b] + np.cross(w_np[b], r_w)
            v_t = v_c - _N * float(v_c @ _N)
            ltan = float(np.linalg.norm(v_t))
            if ltan <= _VEL_EPS:
                continue
            t = v_t / ltan
            rxt = np.cross(r_w, t)
            w_t = (1.0 / m) + float(rxt @ Iinv @ rxt)
            lam_remove = ltan / w_t
            lam_t = min(lam_remove, lam_cap)
            if lam_t <= 0.0:
                continue
            p = -t * lam_t
            v_np[b] += p / m
            w_np[b] += Iinv @ np.cross(r_w, p)
            st.n_corners += 1
            st.max_impulse = max(st.max_impulse, lam_t)
            st.tang_mom_removed += lam_t
            touched = True

    if touched:
        solver.v.assign(v_np.astype(np.float32))
        solver.omega.assign(w_np.astype(np.float32))
    return st


def _solver_of(world):
    return getattr(world, "solver", None) or getattr(world, "_solver", None)


def enable_substep_band(world, coupler, *, eta: float = 1.0, e: float = 0.0,
                        margin: float = 5.0e-3):
    """V2-A: fold the velocity band into the PER-SUBSTEP loop (numpy reference).

    The post-step `apply_velocity_band` samples the kHz ring at the step rate
    (≈120 Hz) — the source of the coarse per-step settle offset. This wraps the
    coupler's `substep_end_hook` so the band runs once per SUBSTEP, right after
    the coupler advances the free IIR, at the substep velocities. It also makes
    the band the SOLE body↔ring channel:
      * `band_owns_excitation = True` → the coupler zeroes the legacy `F_q_dyn`
        forcing, so the ring is excited only by the band's Δq̇_d impulses;
      * `anchor_includes_q_d = False` → the contact anchor carries only the
        static sag, so the ring's push on the body comes only through the band.
    One momentum-conserving impulse now does both excitation and reaction
    (proposal §3.3). Solver-agnostic (XPBD `world.solver`, AVBD `world._solver`).

    Numpy reference only: forces `device_resident = False` (the band reads/writes
    host arrays per substep). The device-resident fold is V2-B. Returns the
    wrapped solver. Idempotent — wraps at most once per coupler.
    """
    coupler.device_resident = False
    coupler.band_owns_excitation = True
    if hasattr(coupler, "anchor_includes_q_d"):
        coupler.anchor_includes_q_d = False
    coupler._modal_reservoir = 0.0          # fresh reservoir for this run
    solver = _solver_of(world)
    if solver is None:
        raise RuntimeError("world exposes no solver / _solver")
    if getattr(coupler, "_band_substep_wrapped", False):
        return solver                        # already folded in
    inner = solver.substep_end_hook          # the coupler's own per-substep hook
    last = {"stats": None}
    # Run-level accumulators (the band fires per SUBSTEP, so per-call stats reset
    # each substep; these carry the whole-run totals the parity test asserts on).
    run = {"impulses": 0, "clamps": 0, "substeps": 0,
           "reservoir_min": float("inf"), "max_lambda": 0.0}

    def _wrapped(s):
        if inner is not None:
            inner(s)                         # coupler advances q_s-solve + free IIR
        st = apply_velocity_band(coupler, s, eta=eta, e=e, margin=margin)
        last["stats"] = st
        run["impulses"] += st.n_impulses
        run["clamps"] += st.clamp_activations
        run["substeps"] += 1
        run["max_lambda"] = max(run["max_lambda"], st.max_lambda)
        # st.reservoir is the UNFLOORED global margin η Σ L − Σ ΔE_modal; its
        # running minimum is the per-prefix §15 bound witness for the run.
        run["reservoir_min"] = min(run["reservoir_min"], st.reservoir)

    solver.substep_end_hook = _wrapped
    coupler._band_substep_wrapped = True
    coupler._band_last_stats = last          # latest VelocityBandStats (per substep)
    coupler._band_run = run                  # whole-run accumulators
    return solver


def enable_device_band(world, coupler, *, eta: float = 1.0, e: float = 0.0,
                       margin: float = 5.0e-3):
    """V2-B: run the velocity band FULLY ON-DEVICE (CUDA-resident).

    The V2-A `enable_substep_band` keeps the band on the numpy host — every
    substep round-trips body v/ω and q̇_d device→host→device, draining the GPU
    pipeline. V2-B folds the band into the coupler's own device `substep_end`
    as a single warp kernel (`k_velocity_band`), so nothing leaves the GPU mid
    step. The band is the SOLE body↔ring channel (same as V2-A):
      * `band_owns_excitation = True` → the device IIR gates F_q_dyn to 0,
      * `anchor_includes_q_d = False` → the anchor carries only the static sag.

    No hook wrapping: the coupler's substep_end hook (already the solver's hook)
    dispatches to `_substep_end_device`, which launches the band kernel when
    `band_owns_excitation`. Requires a CUDA solver (device_resident path); on
    CPU use `enable_substep_band` (the numpy reference). Returns the solver.
    """
    coupler.device_resident = True
    coupler.band_owns_excitation = True
    if hasattr(coupler, "anchor_includes_q_d"):
        coupler.anchor_includes_q_d = False
    coupler._band_eta = float(eta)
    coupler._band_e = float(e)
    coupler._band_margin = float(margin)
    coupler._modal_reservoir = 0.0
    solver = _solver_of(world)
    if solver is None:
        raise RuntimeError("world exposes no solver / _solver")
    return solver
