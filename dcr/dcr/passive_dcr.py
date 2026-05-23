"""Passive energy-bounded DCR coupler (Stage E3) + energy-prescribed
distant-velocity modes (this follow-up).

# DEVIATION from paper Eq. 10: injection enters as a velocity kick to qdot
# followed by free damped oscillation, not as an impulse forcing term inside
# the IIR (foundation §15).

Pipeline (per rigid step):
1. Project full contact impulse j onto modal basis → s (E1, foundation §4)
2. Passive scaling alpha so dE_modal <= eta * E_loss (E2, foundation §6)
3. Kick qdot += alpha * s (foundation §7)
4. Homogeneous stepper for h/T sub-steps (E3.1)
5. Distant response at resting contacts — dispatched on `dcr_velocity_mode`:
   - "coevoet"                           : Δv = d_max / h (Coevoet 2020 Eq. 12).
   - "energy_prescribed"                 : (Version A) dv from energy budget,
                                          linear COM kick.
   - "energy_prescribed_point_impulse"   : (Version B) impulse J at the
                                          deformed contact normal as a true
                                          point impulse (linear + angular).

The energy bound applies only to the modal-path injection.
The spatial-attenuation path (Stage 6) is empirical and is NOT
energy-budgeted in this follow-up.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh
from ..modal.modal_analysis import ModalAnalysis
from ..modal.homogeneous_stepper import HomogeneousStepper
from ..modal.passive_inject import (
    eval_basis_at_point, project_impulse, aggregate_kicks, passive_alpha,
)
from ..modal.energy import modal_energy
from ..rigid.body import RigidBody
from ..rigid.collision import Contact
from ..rigid.solver import _pick_friction_dirs
from .deformed_normal import SurfaceTangentFrames, compute_deformed_normal
from .distant_velocity import (
    PointImpulseKick,
    impulse_from_energy_point,
    speed_from_energy_linear,
)


_EPS_TINY = 1e-12


@dataclass
class PassiveDCRCoupler:
    """Energy-bounded modal-path DCR coupler (Stage E3, foundation §15).

    Like ModalDCRCoupler but uses passive injection instead of forced IIR.

    Attributes:
        modal: Modal analysis results for the elastic body.
        elastic_body_idx: Index of the elastic body in world.bodies.
        impulse_threshold: Skip DCR if total impulse magnitude < this.
        dcr_velocity_mode: Distant velocity prescription (this follow-up).
            "coevoet"                          - existing Eq. 12 Δv = d_max / h.
            "energy_prescribed"                - Version A: linear k=1/m,
                                                 COM-linear kick.
            "energy_prescribed_point_impulse"  - Version B: full k, deformed
                                                 contact normal, true point
                                                 impulse (linear + angular).
            Independent of world.enforce_rigid_energy_bound; for passivity
            pair the energy_* modes with enforce_rigid_energy_bound=True.
        energy_response_beta: Fraction of E_available used by energy_* modes.
            Dimensionless, clamped to [0, 1]. NOT a drop-in replacement for
            d_max (which has units of length); this is an energy-budget knob.
        energy_budget_source: Source of E_available for energy_* modes.
            "rigid_loss"            - eta * world.last_E_loss
            "modal_reservoir"       - modal_energy(q, qdot, omega)
            "min_rigid_loss_modal"  - min of the two (conservative; default)
        theta_max_deformed: Clamp on the deformed-normal tilt angle (radians)
            for Version B. Mirrors TiltDCRCoupler.theta_max default.
    """

    modal: ModalAnalysis
    elastic_body_idx: int
    impulse_threshold: float = 1e-3

    # ----- New: distant velocity mode -----------------------------------
    # See class docstring above for semantics.
    dcr_velocity_mode: str = "coevoet"
    energy_response_beta: float = 0.25
    energy_budget_source: str = "min_rigid_loss_modal"
    theta_max_deformed: float = float(np.radians(3.0))

    # Internals.
    _stepper: HomogeneousStepper = field(init=False, repr=False)
    _surface: TriMesh = field(init=False, repr=False)
    _vert_to_surf_idx: NDArray[np.int32] = field(init=False, repr=False)
    # Lazy: created on first Version-B step.
    _tangent_frames: SurfaceTangentFrames | None = field(
        default=None, init=False, repr=False)

    # Energy diagnostics per step.
    last_E_modal_pre_kick: float = 0.0
    last_E_modal_post_kick: float = 0.0
    last_alpha: float = 0.0
    last_q_history_transient: NDArray[np.float64] | None = None

    # ----- New: per-step diagnostics for the velocity-mode follow-up ----
    # Always populated when bodies is passed to process_step():
    last_E_available: float = 0.0
    last_E_target: float = 0.0
    last_dcr_velocities_coevoet: dict[int, float] = field(default_factory=dict)
    last_dcr_velocities_energy_A: dict[int, float] = field(default_factory=dict)
    # Set when mode == "energy_prescribed_point_impulse":
    last_point_impulse_kicks: list[PointImpulseKick] | None = None

    def __post_init__(self) -> None:
        self._stepper = HomogeneousStepper.from_modal_analysis(self.modal)
        self._surface = self.modal.fem.mesh.extract_surface()
        max_vert = self.modal.fem.mesh.num_vertices
        self._vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
        for si, vi in enumerate(self.modal.surface_vertex_indices):
            self._vert_to_surf_idx[vi] = si

    # ------------------------------------------------------------------
    # Energy budget source dispatch (foundation §1 / §2)
    # ------------------------------------------------------------------

    def _E_available(self, E_max_from_world: float) -> float:
        """Return E_available for the active `energy_budget_source`.

        `E_max_from_world` is `eta * world.last_E_loss`, computed by the
        world and passed into `process_step()` (foundation §1).
        """
        src = self.energy_budget_source
        E_rigid = max(0.0, float(E_max_from_world))
        if src == "rigid_loss":
            return E_rigid
        omega = self.modal.frequencies
        E_modal = modal_energy(self._stepper.q, self._stepper.qdot, omega)
        if src == "modal_reservoir":
            return float(E_modal)
        if src == "min_rigid_loss_modal":
            return float(min(E_rigid, E_modal))
        raise ValueError(
            f"unknown energy_budget_source: {self.energy_budget_source!r}")

    # ------------------------------------------------------------------
    # Lazy tangent-frame cache for Version B (deformed-normal lookup)
    # ------------------------------------------------------------------

    def _get_tangent_frames(self) -> SurfaceTangentFrames:
        if self._tangent_frames is None:
            self._tangent_frames = SurfaceTangentFrames(surface=self._surface)
        return self._tangent_frames

    # ------------------------------------------------------------------
    # Main entry point — process one rigid-body step
    # ------------------------------------------------------------------

    def process_step(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        h: float,
        E_max: float,
        bodies: list[RigidBody] | None = None,
    ) -> dict[int, float]:
        """Run the passive DCR pipeline for one rigid-body step.

        Args:
            contacts: All contacts this step.
            lam: Solved constraint impulse vector (3 rows per contact).
            h: Rigid-body timestep.
            E_max: Energy budget = eta * E_loss from the rigid solver.
            bodies: List of all rigid bodies (needed for energy_* modes to
                read masses and inertias). Optional for backwards
                compatibility with the legacy "coevoet" path; required for
                the energy_prescribed* modes (a clear ValueError is raised
                otherwise).

        Returns:
            dcr_velocities: Dict mapping body index → separation velocity Δv
            (scalar, along contact normal). For the point-impulse mode,
            returns an empty dict and stores kicks in
            `self.last_point_impulse_kicks` for the world to apply.
        """
        omega = self.modal.frequencies

        # --- Identify new and resting contacts on the elastic body ---
        new_contacts_data: list[tuple[Contact, int]] = []  # (contact, ci)
        resting_contacts: list[Contact] = []

        for ci, contact in enumerate(contacts):
            if contact.body_a != self.elastic_body_idx and \
               contact.body_b != self.elastic_body_idx:
                continue
            if contact.is_new:
                new_contacts_data.append((contact, ci))
            else:
                resting_contacts.append(contact)

        # --- Project new contact impulses → s_total (E1, foundation §4, §8) ---
        kicks_modal: list[NDArray[np.float64]] = []
        for contact, ci in new_contacts_data:
            if 3 * ci + 2 >= len(lam):
                continue
            lambda_N = lam[3 * ci]
            lambda_T1 = lam[3 * ci + 1]
            lambda_T2 = lam[3 * ci + 2]
            t1, t2 = _pick_friction_dirs(contact.normal)
            j_world = (
                contact.normal * lambda_N + t1 * lambda_T1 + t2 * lambda_T2)
            if np.linalg.norm(j_world) < self.impulse_threshold:
                continue
            Phi_x = eval_basis_at_point(
                contact.point, self._surface, self.modal.U_surf,
                self.modal.surface_vertex_indices, self._vert_to_surf_idx,
            )
            s_c = project_impulse(Phi_x, j_world)
            kicks_modal.append(s_c)

        n_substeps = max(1, int(np.ceil(h / self._stepper.T)))

        if not kicks_modal:
            # No new impulses — step the persistent state for free decay,
            # but produce no distant responses (no new impact → no DCR).
            self.last_alpha = 0.0
            self.last_q_history_transient = None
            self.last_E_modal_pre_kick = modal_energy(
                self._stepper.q, self._stepper.qdot, omega)
            self.last_E_modal_post_kick = self.last_E_modal_pre_kick
            self._stepper.step_n(n_substeps)
            self._reset_velocity_mode_diagnostics()
            return {}

        s_total = aggregate_kicks(kicks_modal)

        # --- Passive scaling (E2, foundation §6) ---
        self.last_E_modal_pre_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)
        alpha = passive_alpha(s_total, self._stepper.qdot, E_max)
        self.last_alpha = alpha

        # The scaled kick applied to the persistent energy state.
        alpha_s = alpha * s_total

        # --- Velocity kick (foundation §7): qdot += alpha * s_total ---
        self._stepper.qdot += alpha_s

        self.last_E_modal_post_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)

        # --- Step persistent state for energy bookkeeping (E3.1) ---
        self._stepper.step_n(n_substeps)

        # --- Transient displacement for DCR response (Eqs. 11-13) ---
        # Use ONLY this step's kick for the displacement response, not
        # the full persistent state. This matches the original IIR behavior
        # (reset each step) while keeping the persistent state for energy.
        q_history_transient = self._stepper.transient_step_n(alpha_s, n_substeps)
        self.last_q_history_transient = q_history_transient

        return self._compute_distant_response(
            resting_contacts, q_history_transient, h, E_max, bodies)

    # ------------------------------------------------------------------
    # Distant response dispatch (this follow-up)
    # ------------------------------------------------------------------

    def _compute_distant_response(
        self,
        resting_contacts: list[Contact],
        q_history: NDArray[np.float64],
        h: float,
        E_max: float,
        bodies: list[RigidBody] | None,
    ) -> dict[int, float]:
        """Dispatch on `dcr_velocity_mode`.

        Always computes the Coevoet proposal for direction reference and
        diagnostics. Also computes Version A in parallel for the dv_ratio
        diagnostic (so a paper-grade comparison is available regardless of
        which mode is active).
        """
        # --- 1. Coevoet proposal (existing Eq. 12). Unchanged. ----------
        dv_coevoet = self._compute_distant_response_coevoet(
            resting_contacts, q_history, h)
        self.last_dcr_velocities_coevoet = dict(dv_coevoet)

        # --- 2. Energy budget for this step ----------------------------
        E_available = self._E_available(E_max)
        beta = float(np.clip(self.energy_response_beta, 0.0, 1.0))
        E_target = beta * max(0.0, E_available)
        self.last_E_available = E_available
        self.last_E_target = E_target

        # --- 3. Version A (diagnostic when not active) -----------------
        if bodies is not None:
            dv_A = self._compute_distant_response_energy_A(
                resting_contacts, dv_coevoet, bodies, E_target)
        else:
            dv_A = {}
        self.last_dcr_velocities_energy_A = dict(dv_A)

        # --- 4. Dispatch on active mode --------------------------------
        mode = self.dcr_velocity_mode
        if mode == "coevoet":
            self.last_point_impulse_kicks = None
            return dv_coevoet
        if mode == "energy_prescribed":
            if bodies is None:
                raise ValueError(
                    "dcr_velocity_mode='energy_prescribed' requires `bodies` "
                    "to be passed to PassiveDCRCoupler.process_step(). "
                    "DCRWorld.step() supplies this automatically.")
            self.last_point_impulse_kicks = None
            return dv_A
        if mode == "energy_prescribed_point_impulse":
            if bodies is None:
                raise ValueError(
                    "dcr_velocity_mode='energy_prescribed_point_impulse' "
                    "requires `bodies` to be passed to "
                    "PassiveDCRCoupler.process_step(). "
                    "DCRWorld.step() supplies this automatically.")
            kicks = self._compute_distant_response_energy_B(
                resting_contacts, q_history, bodies, E_target)
            self.last_point_impulse_kicks = kicks
            # The world inspects last_point_impulse_kicks and dispatches to
            # _apply_point_impulse_dcr_velocities. Returning {} makes the
            # standard scalar-dv path a no-op for this coupler.
            return {}
        raise ValueError(f"unknown dcr_velocity_mode: {mode!r}")

    # ------------------------------------------------------------------
    # Existing Coevoet proposal — unchanged from before this follow-up.
    # Renamed from _compute_distant_response so the dispatcher can wrap it.
    # ------------------------------------------------------------------

    def _compute_distant_response_coevoet(
        self,
        resting_contacts: list[Contact],
        q_history: NDArray[np.float64],
        h: float,
    ) -> dict[int, float]:
        """Coevoet et al. 2020 Eqs. 11-12 distant velocity proposal.

        d_max = max_k |n^T U_i q^(k)|     (Eq. 11)
        Δv    = d_max / h                  (Eq. 12)
        """
        dcr_velocities: dict[int, float] = {}
        for contact in resting_contacts:
            other_body = (contact.body_a
                          if contact.body_b == self.elastic_body_idx
                          else contact.body_b)
            d_max = self._compute_max_displacement(
                contact.point, contact.normal, q_history)
            dv = d_max / h
            if other_body in dcr_velocities:
                dcr_velocities[other_body] = max(
                    dcr_velocities[other_body], dv)
            else:
                dcr_velocities[other_body] = dv
        return dcr_velocities

    def _compute_max_displacement(
        self,
        contact_point: NDArray[np.float64],
        normal: NDArray[np.float64],
        q_history: NDArray[np.float64],
    ) -> float:
        """Compute d_{i,max} = max_k |n^T U_i q^(k)| (Eq. 11)."""
        Phi_x = eval_basis_at_point(
            contact_point, self._surface, self.modal.U_surf,
            self.modal.surface_vertex_indices, self._vert_to_surf_idx,
        )
        nPhi = normal @ Phi_x  # (n_modes,)
        d_all = q_history @ nPhi
        return float(np.max(np.abs(d_all)))

    # ------------------------------------------------------------------
    # Version A: energy-prescribed, linear k, COM-linear kick (this follow-up)
    # ------------------------------------------------------------------

    def _compute_distant_response_energy_A(
        self,
        resting_contacts: list[Contact],
        dv_coevoet: dict[int, float],
        bodies: list[RigidBody],
        E_target: float,
    ) -> dict[int, float]:
        """Energy-prescribed distant velocity (Version A, linear-only).

        Direction = contact normal (Coevoet style, encoded by sign of
        push_dir at apply time). Magnitude from energy budget:

            dv = sqrt(2 * (1/m) * E_target)

        Applied via the existing _apply_dcr_velocities (COM-linear kick),
        so the realized ΔKE = ½ m dv² = E_target exactly.

        # DEVIATION (foundation §15, paper §5.4): the task spec proposed
        # k = 1/m + (r x u) . I_world_inv . (r x u). We drop the angular
        # term because _apply_dcr_velocities updates only body.velocity[:3]
        # — the angular term would represent energy not actually injected,
        # causing realized ΔKE to exceed E_target. The point_impulse mode
        # below uses the full formula AND the angular kick, restoring
        # physical consistency.
        """
        eps = _EPS_TINY
        out: dict[int, float] = {}
        for contact in resting_contacts:
            other_body = (contact.body_a
                          if contact.body_b == self.elastic_body_idx
                          else contact.body_b)
            body = bodies[other_body]
            sc = dv_coevoet.get(other_body, 0.0)
            if sc <= eps:
                speed_energy = 0.0
            else:
                speed_energy = speed_from_energy_linear(body, E_target)
            if other_body in out:
                out[other_body] = max(out[other_body], speed_energy)
            else:
                out[other_body] = speed_energy
        return out

    # ------------------------------------------------------------------
    # Version B: energy-prescribed, full k, deformed normal, point impulse
    # ------------------------------------------------------------------

    def _compute_distant_response_energy_B(
        self,
        resting_contacts: list[Contact],
        q_history: NDArray[np.float64],
        bodies: list[RigidBody],
        E_target: float,
    ) -> list[PointImpulseKick]:
        """Energy-prescribed distant kicks as TRUE point impulses (Version B).

        For each resting contact:
            u   = compute_deformed_normal(...)                  (this follow-up)
            r   = contact.point - body.position
            k   = 1/m + (r × u) · I_world_inv · (r × u)
            J   = sqrt(2 · E_target / k)
        Applied by the world's `_apply_point_impulse_dcr_velocities`:
            v_lin += (J/m) · u
            ω     += J · I_world_inv · (r × u)
        Realized ΔKE = ½ J² k = E_target exactly (foundation §15).

        Multi-contact aggregation: if the same body has multiple resting
        contacts, the largest-J kick is kept. (Summing kicks pre-cap could
        double-count; the world's _bound_point_impulse_dcr_velocities then
        caps the global ΔE.)
        """
        frames = self._get_tangent_frames()
        kicks_by_body: dict[int, PointImpulseKick] = {}
        for contact in resting_contacts:
            # Push direction from elastic to body (matches _resting_push_dir).
            if contact.body_b == self.elastic_body_idx:
                other_body = contact.body_a
                push_dir = -contact.normal
            else:
                other_body = contact.body_b
                push_dir = contact.normal
            body = bodies[other_body]
            if body.is_static or body.mass <= 0.0:
                continue
            # Deformed contact normal (extracted from the tilt pipeline).
            u, theta, _ = compute_deformed_normal(
                contact_point=contact.point,
                push_dir=push_dir,
                q_history=q_history,
                modal_U_surf=self.modal.U_surf,
                surface_vertex_indices=self.modal.surface_vertex_indices,
                surface=self._surface,
                vert_to_surf_idx=self._vert_to_surf_idx,
                tangent_frames=frames,
                theta_max=self.theta_max_deformed,
            )
            r = contact.point - body.position
            J = impulse_from_energy_point(body, r, u, E_target)
            if J <= 0.0:
                continue
            kk = PointImpulseKick(
                body_idx=other_body, J_mag=J, u=u.copy(), r=r.copy(),
                theta=theta,
            )
            # Keep largest-J per body across multiple contacts.
            prev = kicks_by_body.get(other_body)
            if prev is None or kk.J_mag > prev.J_mag:
                kicks_by_body[other_body] = kk
        return list(kicks_by_body.values())

    # ------------------------------------------------------------------
    # Reset helpers
    # ------------------------------------------------------------------

    def _reset_velocity_mode_diagnostics(self) -> None:
        """Clear per-step caches (used when no kicks fired this step)."""
        self.last_E_available = 0.0
        self.last_E_target = 0.0
        self.last_dcr_velocities_coevoet = {}
        self.last_dcr_velocities_energy_A = {}
        self.last_point_impulse_kicks = None
