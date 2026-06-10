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
    coupler._modal_reservoir = max(0.0, reservoir)
    st.reservoir = coupler._modal_reservoir
    if st.invariant_margin_min == float("inf"):
        st.invariant_margin_min = 0.0
    return st
