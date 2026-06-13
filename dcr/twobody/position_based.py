"""Approach B — the unified *dynamic* modal constraint in a position-based solver.

`two_band_coupling.html` ("Modal Contact as a Dynamic Two-Way Constraint")
proposes carrying the support's FULL dynamic modal state `q` (its own inertia
`M_q`, stiffness `K_q`, damping `D_q`) *inside the same contact solve* as the
bodies, instead of the old static/dynamic split (static `q_s` in the constraint
+ a one-way, energy-governed velocity band for the ring `q_d`). The two-way loop
is then structural — the single contact multiplier that lifts a body is the very
reaction that loads the mode, and the mode's inertia pushes back — and the run is
passive *for free* (backward Euler on a bounded-below potential is dissipative),
so no η / reservoir governor is needed.

`multibody.MultiBodySystem` already integrates that exact incremental potential,
but with a **dense Newton-to-convergence + raw penalty** contact. That is the
in-solver GROUND TRUTH. This module realizes the *same* dynamic-constraint
potential inside the two **real-time position-based solvers** the project
targets:

  * `AVBDDynamicSystem` — Augmented Vertex Block Descent (Giles et al. 2025):
    augmented-Lagrangian contact (multiplier λ + penalty ρ, dual updates),
    a fixed, small iteration budget. Handles ABD and FEM cubes.
  * `XPBDDynamicSystem` — Extended Position-Based Dynamics (Macklin et al. 2016):
    compliant constraints solved Gauss–Seidel, internal elasticity *and* contact
    both as compliant constraints. Demonstrated on FEM-modal bodies (whose
    internal is the diagonal modal stiffness — exact compliant constraints).

Both subclass-by-composition over a `MultiBodySystem` so they share its stacked
DOF layout, mass / damping / gravity, contact geometry, per-body energy logging
(`energy_breakdown`) and the basin-free `static_residual` — the only thing that
changes is `step()`. That makes the GT-vs-AVBD-vs-XPBD comparison apples-to-apples.

# DEVIATION (paper Eq. 10 / foundation §15): the paper drives one modal `q`
# through a forced IIR resonator; the follow-up's split adds a passivity
# governor (ΔE_modal ≤ η·ΔE_rigid_loss). Approach B drops BOTH — the modal DOF
# is solved monolithically with the bodies, so momentum is conserved by a shared
# contact multiplier (Newton's third law) and energy is dissipated by the
# implicit integrator. The governor is unnecessary because nothing is *injected*.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from .multibody import MultiBodySystem, MultiBodyState


# ======================================================================
# AVBD — augmented-Lagrangian, fixed iteration budget
# ======================================================================
class AVBDDynamicSystem:
    """AVBD realization of the dynamic modal contact constraint.

    One step minimizes the implicit-Euler incremental potential

        E(z) = Σ_b 1/(2h²)‖z_b − z̃_b‖²_M_b   (inertia, gravity in z̃)
             + Σ_b V_b(z_b)                    (internal elastic, incl. K_q q)
             + Σ_c Φ_AL(gap_c(z))              (augmented-Lagrangian contact)

    over the STACKED rigid + modal coordinates z — the modal amplitudes carry
    their own M_q/h² inertia (already in the stacked mass) and D_q/h damping, so
    the support's dynamic `q` is a first-class unknown in the contact solve.

    Augmented Lagrangian (Giles et al. 2025): each contact holds a multiplier
    λ_c ≤ 0 (compressive) and penalty ρ_c; the active contact force is
    f_c = min(0, λ_c + ρ_c·gap_c). Outer loop updates λ_c ← min(0, λ_c+ρ_c·gap_c)
    and (optionally) escalates ρ_c; an inner Newton solves the primal for fixed
    (λ, ρ). With the multiplier carrying the load, a handful of iterations drive
    gap → 0 (vs the penalty GT's residual gap = −f/k_c).

    # DEVIATION (AVBD primal): AVBD proper minimizes the primal by per-vertex/
    # body block descent; this reference uses a dense Newton primal (the demo is
    # small) — same minimizer, simpler to read. The device-resident block / Schur
    # realization lives in `dcr/avbd/reduced_coupled_avbd.py`.
    """

    def __init__(self, base: MultiBodySystem, *, n_outer: int = 6,
                 n_inner: int = 3, rho0: float | None = None,
                 rho_escalation: float = 1.0, rho_max: float = 1.0e9):
        self.base = base
        self.n_outer = n_outer
        self.n_inner = n_inner
        self.rho0 = float(base.k_c if rho0 is None else rho0)
        self.rho_escalation = float(rho_escalation)
        self.rho_max = float(rho_max)
        # last-step diagnostics
        self.last_max_penetration = 0.0
        self.last_lambda_max = 0.0

    # -- pass-throughs so the comparison harness treats all solvers alike --
    def initial_state(self) -> MultiBodyState:
        return self.base.initial_state()

    def energy_breakdown(self, st: MultiBodyState) -> dict:
        return self.base.energy_breakdown(st)

    def static_residual(self, st: MultiBodyState) -> float:
        return self.base.static_residual(st)

    def body_z(self, st: MultiBodyState, i: int) -> NDArray[np.float64]:
        return self.base.body_z(st, i)

    @property
    def bodies(self):
        return self.base.bodies

    # -- one AVBD step -------------------------------------------------
    def step(self, state: MultiBodyState, h: float) -> MultiBodyState:
        b = self.base
        n = b.n
        z_n, v_n = state.z, state.v
        z_tilde = z_n + h * v_n + (h * h) * (b._Minv @ b._fgrav)
        z = z_n.copy()

        nC = len(b.contacts)
        lam = np.zeros(nC)
        rho = np.full(nC, self.rho0)

        M_term = b._M / (h * h)
        D_term = b._D / h
        for _ in range(self.n_outer):
            for _ in range(self.n_inner):
                g_int, H_int = b._internal(z)
                gaps, grads = b._gaps(z)
                g = (b._M @ (z - z_tilde)) / (h * h) + g_int \
                    + (b._D @ (z - z_n)) / h
                H = M_term + H_int + D_term
                for c in range(nC):
                    fc = lam[c] + rho[c] * gaps[c]      # AL contact force
                    if fc < 0.0:                        # active (compressive)
                        g += fc * grads[c]
                        H += rho[c] * np.outer(grads[c], grads[c])
                delta = np.linalg.solve(H, -g)
                z += delta
                if np.linalg.norm(delta) < 1.0e-12:
                    break
            # AL dual update + penalty escalation
            gaps, _ = b._gaps(z)
            lam = np.minimum(0.0, lam + rho * gaps)
            if self.rho_escalation > 1.0:
                rho = np.minimum(rho * self.rho_escalation, self.rho_max)

        gaps, _ = b._gaps(z)
        self.last_max_penetration = float(max(0.0, -gaps.min())) if nC else 0.0
        self.last_lambda_max = float(np.max(np.abs(lam))) if nC else 0.0
        v = (z - z_n) / h
        return MultiBodyState(z=z, v=v)


# ======================================================================
# XPBD — compliant constraints, Gauss–Seidel
# ======================================================================
class XPBDDynamicSystem:
    """XPBD realization of the dynamic modal contact constraint.

    Extended Position-Based Dynamics (Macklin et al. 2016): every force is a
    compliant constraint with compliance α = 1/stiffness and time-scaled
    α̃ = α/h². A substep predicts z̃ = z^n + h v^n + h² M⁻¹ f_grav, then
    Gauss–Seidel-projects all constraints a fixed number of iterations, then
    sets v = (z − z^n)/h.

    Constraints:
      * INTERNAL elastic — `body.elastic_constraints(z)`: for a FEM-modal body
        these are the per-mode amplitudes C_i = a_i with stiffness ω²_i, i.e. the
        modal stiffness K_q expressed exactly as diagonal compliant constraints,
        with the modal Rayleigh damping D_q[i,i] applied through Macklin's damped
        compliant-constraint update (§3.5) so the modes ring down.
      * CONTACT — unilateral C_c = gap_c ≥ 0 with compliance 1/k_c, projected
        only while penetrating (C < 0), multiplier clamped compressive (λ ≥ 0).

    Because the support's modal amplitudes ARE constraint DOFs advanced inside the
    same Gauss–Seidel sweep as the bodies, the dynamic two-way loop is structural
    — identical in spirit to AVBD and the GT, just a different primal solver.

    Demonstrated on FEM-modal bodies. (ABD cubes expose 6 nonlinear orthogonality
    constraints via `elastic_constraints`; they project fine, but ABD's
    mass-proportional damping is not wired through the per-constraint damp term
    here, so the AVBD path is the one exercised for ABD.)
    """

    def __init__(self, base: MultiBodySystem, *, n_iters: int = 20):
        self.base = base
        self.n_iters = n_iters
        # per-body generalized inverse mass (block-diagonal)
        self._Minv_b = [np.linalg.inv(bd.M) for bd in base.bodies]
        self.last_max_penetration = 0.0

    def initial_state(self) -> MultiBodyState:
        return self.base.initial_state()

    def energy_breakdown(self, st: MultiBodyState) -> dict:
        return self.base.energy_breakdown(st)

    def static_residual(self, st: MultiBodyState) -> float:
        return self.base.static_residual(st)

    def body_z(self, st: MultiBodyState, i: int) -> NDArray[np.float64]:
        return self.base.body_z(st, i)

    @property
    def bodies(self):
        return self.base.bodies

    def step(self, state: MultiBodyState, h: float) -> MultiBodyState:
        b = self.base
        z_n, v_n = state.z, state.v
        # predictor (gravity folded in via the projected generalized force)
        z = z_n + h * v_n + (h * h) * (b._Minv @ b._fgrav)
        h2 = h * h

        # multipliers reset each substep (XPBD)
        lam_el = [np.zeros(len(bd.elastic_constraints(z[b._slice(i)])))
                  for i, bd in enumerate(b.bodies)]
        lam_c = np.zeros(len(b.contacts))

        for _ in range(self.n_iters):
            # --- internal elastic constraints, per body ---
            for i, bd in enumerate(b.bodies):
                sl = b._slice(i)
                Minv = self._Minv_b[i]
                cons = bd.elastic_constraints(z[sl])
                for k, (C, grad, alpha, damp) in enumerate(cons):
                    if alpha <= 0.0:
                        continue
                    at = alpha / h2
                    w = float(grad @ (Minv @ grad))
                    # damped compliant constraint (Macklin 2016 §3.5):
                    #   γ = α̃·β·h, β = damp·α (so the damping force ≈ damp·Ċ)
                    gamma = at * (damp * alpha) * h if damp > 0.0 else 0.0
                    Cdot = float(grad @ (z[sl] - z_n[sl]))
                    denom = (1.0 + gamma) * w + at
                    dlam = (-C - at * lam_el[i][k] - gamma * Cdot) / denom
                    lam_el[i][k] += dlam
                    z[sl] += Minv @ grad * dlam
            # --- contact constraints (unilateral, two bodies each) ---
            gaps, grads = b._gaps(z)
            alpha_c = 1.0 / b.k_c
            at = alpha_c / h2
            for c, ct in enumerate(b.contacts):
                C = gaps[c]
                if C >= 0.0 and lam_c[c] == 0.0:
                    continue                       # separated, inactive
                grad = grads[c]
                w = float(grad @ (b._Minv @ grad))
                dlam = (-C - at * lam_c[c]) / (w + at)
                new = max(0.0, lam_c[c] + dlam)    # compressive only
                dlam = new - lam_c[c]
                lam_c[c] = new
                z += b._Minv @ grad * dlam

        gaps, _ = b._gaps(z)
        self.last_max_penetration = float(max(0.0, -gaps.min())) \
            if len(gaps) else 0.0
        v = (z - z_n) / h
        return MultiBodyState(z=z, v=v)
