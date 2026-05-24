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
from .deformed_normal_bj import (
    BarbicJamesCache,
    build_barbic_james_cache,
    compute_deformed_normal_barbic_james,
)
from .distant_velocity import (
    LinearKick,
    PointImpulseKick,
    friction_cone_clip,
    gamma_from_energy_linear,
    impulse_from_energy_point,
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
        deformed_normal_method: How to compute the deformed contact normal n'
            for the energy_* distant-velocity modes.
            "patch_fit" (default) - heuristic: finite-difference (n·u) over the
                contact triangle's 3 surface vertices, tilt n_rest by the
                in-plane gradient, clamp to theta_max_deformed. Uses the peak
                q from q_history (paper Eq. 11 d_max heuristic).
            "barbic_james"        - F^{-T} push-forward (foundation §17;
                Barbič & James 2008 IEEE ToH §4.1, see
                reference/BarbicJames-2008-IEEE-TOH.pdf). Computes the FEM
                deformation gradient F = I + Σ_i u_i ⊗ ∇N_i at the contact
                point using analytical shape-function gradients of the owning
                tet (including the 4th interior vertex's modal contribution
                the surface patch fit cannot see), and returns
                normalize(F^{-T} · n_rest). Uses the *current* q (last
                substep), not a peak from q_history.
            Both methods return n_rest exactly at q = 0; for q ≠ 0
            their angular outputs differ at O(‖q‖) — the patch fit
            cannot see the modal displacement at the 4th (interior)
            tet vertex, while barbic_james includes its ∇N_D ⊗ u_D
            contribution to F. See tests/stageDV/
            test_deformed_normal_methods.py for the linear-scaling
            regression and foundation §17 for the derivation.
        friction_cone_clip_enabled: When True, the post-solver kick
            gets a Coulomb friction correction applied at the contact
            point after the main kick fires. Two paths, different
            algebra (both with mu = min(body_a.friction, body_b.friction),
            matching rigid/solver.py:206-207):
            * Version A (linear kick at COM): the kick speed*u itself
              is decomposed against n_rest and the tangential component
              is clipped to mu·max(0, normal) — see
              distant_velocity.friction_cone_clip. For Version A,
              Δv_c = Δv_lin, so this is mathematically equivalent to
              the contact-point clip with the correction applied at
              the COM.
            * Version B (point impulse at r): the kick generates both
              a linear AND an angular contact-point velocity change
              (Δv_c = (J/m)·u + (J·I_inv·(r×u))×r), and the angular
              part has a tangential contribution even when u = n_rest
              exactly. The clip therefore operates on Δv_c (not on u)
              and the corrective friction impulse is applied at the
              contact point r — see
              distant_velocity.contact_point_friction_correction. The
              correction generates an automatic counter-torque
              (because it acts at r, not the COM), damping the spin
              that was driving the visible sliding in scenes like
              shelf at h=1e-2.
            Default False (no behavior change).
        kinematic_cap: Upper-bound the per-step energy-mode kick
            magnitude by a kinematic ceiling, to recover the
            h-invariance Coevoet's recipe enjoys "for free" via
            its automatic /h cancellation.
            "none"    - no extra cap (default; energy formulation only).
            "coevoet" - per-contact cap γ ≤ d_max / h, equivalent to
                applying min(γ*_energy, Coevoet kinematic velocity).
                Useful when the rigid step h is too large for the
                energy-quadratic γ ∝ h scaling (gravity-loaded E_loss
                ∝ h² → γ* ∝ h per step) to remain visually stable.
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
    deformed_normal_method: str = "patch_fit"
    # See class docstring for the rationale on these two.
    friction_cone_clip_enabled: bool = False
    kinematic_cap: str = "none"

    # Internals.
    _stepper: HomogeneousStepper = field(init=False, repr=False)
    _surface: TriMesh = field(init=False, repr=False)
    _vert_to_surf_idx: NDArray[np.int32] = field(init=False, repr=False)
    # Lazy: created on first Version-B step.
    _tangent_frames: SurfaceTangentFrames | None = field(
        default=None, init=False, repr=False)
    # Populated in __post_init__ when deformed_normal_method == "barbic_james".
    _bj_cache: BarbicJamesCache | None = field(
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
    # Diagnostic speeds for Version A (the scalar magnitudes per kicked
    # body, before direction is applied). Populated alongside last_linear_kicks.
    last_dcr_velocities_energy_A: dict[int, float] = field(default_factory=dict)
    # Set when mode == "energy_prescribed":
    last_linear_kicks: list[LinearKick] | None = None
    # Set when mode == "energy_prescribed_point_impulse":
    last_point_impulse_kicks: list[PointImpulseKick] | None = None
    # Per-step counters for the post-solver clip / kinematic cap. Reset on
    # every process_step() call; useful for the A/B reports in run_scenes.
    last_friction_clip_fired: int = 0
    last_friction_clip_attempted: int = 0
    last_kinematic_cap_fired: int = 0
    last_kinematic_cap_attempted: int = 0

    def __post_init__(self) -> None:
        self._stepper = HomogeneousStepper.from_modal_analysis(self.modal)
        self._surface = self.modal.fem.mesh.extract_surface()
        max_vert = self.modal.fem.mesh.num_vertices
        self._vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
        for si, vi in enumerate(self.modal.surface_vertex_indices):
            self._vert_to_surf_idx[vi] = si

        # Build the Barbič-James cache up-front if that method is selected.
        # Lazy validation matches dcr_velocity_mode / energy_budget_source.
        if self.deformed_normal_method == "barbic_james":
            self._bj_cache = build_barbic_james_cache(
                self.modal, self._surface)
        elif self.deformed_normal_method != "patch_fit":
            raise ValueError(
                "unknown deformed_normal_method: "
                f"{self.deformed_normal_method!r} "
                "(expected 'patch_fit' or 'barbic_james')")

        if self.kinematic_cap not in ("none", "coevoet"):
            raise ValueError(
                "unknown kinematic_cap: "
                f"{self.kinematic_cap!r} (expected 'none' or 'coevoet')")

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
    # Deformed-normal dispatch (patch_fit vs barbic_james)
    # ------------------------------------------------------------------

    def _deformed_normal(
        self,
        contact_point: NDArray[np.float64],
        push_dir: NDArray[np.float64],
        q_history: NDArray[np.float64],
        frames: SurfaceTangentFrames,
    ) -> tuple[NDArray[np.float64], float, int]:
        """Dispatch on `deformed_normal_method`. Returns (n', theta, best_tri).

        Both backends compute the deformed contact normal n' along which
        the Version-A / Version-B energy-prescribed kicks are applied.
        See the class docstring for semantic differences. The
        patch_fit backend uses q_history (peak-snapshot rule); the
        barbic_james backend uses only the current substep q
        (q_history[-1]) consistent with Barbič & James 2008 §4.1.
        """
        if self.deformed_normal_method == "patch_fit":
            return compute_deformed_normal(
                contact_point=contact_point,
                push_dir=push_dir,
                q_history=q_history,
                modal_U_surf=self.modal.U_surf,
                surface_vertex_indices=self.modal.surface_vertex_indices,
                surface=self._surface,
                vert_to_surf_idx=self._vert_to_surf_idx,
                tangent_frames=frames,
                theta_max=self.theta_max_deformed,
            )
        # barbic_james: current configuration only.
        assert self._bj_cache is not None, (
            "BarbicJamesCache was not built; check __post_init__")
        q_current = q_history[-1] if q_history.size else np.zeros(
            self.modal.U.shape[1])
        return compute_deformed_normal_barbic_james(
            contact_point=contact_point,
            push_dir=push_dir,
            q=q_current,
            surface=self._surface,
            cache=self._bj_cache,
            theta_max=self.theta_max_deformed,
        )

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

        # --- Reset per-step clip/cap diagnostic counters --------------------
        self.last_friction_clip_fired = 0
        self.last_friction_clip_attempted = 0
        self.last_kinematic_cap_fired = 0
        self.last_kinematic_cap_attempted = 0

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

        # --- 3. Version A (deformed-normal, linear-only) ---------------
        # Computed in parallel even when not the active mode, so the
        # dv_ratio diagnostic / CSV columns are always populated.
        if bodies is not None:
            linear_kicks = self._compute_distant_response_energy_A(
                resting_contacts, q_history, bodies, E_target, h)
        else:
            linear_kicks = []
        # Backward-compatible diagnostic dict: speed-magnitudes by body.
        self.last_dcr_velocities_energy_A = {
            kk.body_idx: kk.speed for kk in linear_kicks}

        # --- 4. Dispatch on active mode --------------------------------
        mode = self.dcr_velocity_mode
        if mode == "coevoet":
            self.last_linear_kicks = None
            self.last_point_impulse_kicks = None
            return dv_coevoet
        if mode == "energy_prescribed":
            if bodies is None:
                raise ValueError(
                    "dcr_velocity_mode='energy_prescribed' requires `bodies` "
                    "to be passed to PassiveDCRCoupler.process_step(). "
                    "DCRWorld.step() supplies this automatically.")
            self.last_linear_kicks = linear_kicks
            self.last_point_impulse_kicks = None
            # The world inspects last_linear_kicks and dispatches to
            # _apply_linear_kick_dcr_velocities. Returning {} makes the
            # standard scalar-dv path a no-op for this coupler.
            return {}
        if mode == "energy_prescribed_point_impulse":
            if bodies is None:
                raise ValueError(
                    "dcr_velocity_mode='energy_prescribed_point_impulse' "
                    "requires `bodies` to be passed to "
                    "PassiveDCRCoupler.process_step(). "
                    "DCRWorld.step() supplies this automatically.")
            kicks = self._compute_distant_response_energy_B(
                resting_contacts, q_history, bodies, E_target, h)
            self.last_linear_kicks = None
            self.last_point_impulse_kicks = kicks
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
        q_history: NDArray[np.float64],
        bodies: list[RigidBody],
        E_target: float,
        h: float,
    ) -> list[LinearKick]:
        """Energy-prescribed distant velocity (Version A, linear-only).

        Direction = **deformed** contact normal n' (same primitive Version B
        uses — `compute_deformed_normal`). Magnitude from energy budget,
        solved as a quadratic in γ (foundation §16):

            ΔKE(γ) = m·(v·u)·γ + ½·m·γ² = E_target,
            γ*_A   = -(v·u) + √((v·u)² + 2·E_target / m).

        Applied via `_apply_linear_kick_dcr_velocities` (pure COM-linear
        kick, no angular component). Realized ΔKE = E_target exactly
        (within float tolerance) for every body, regardless of incoming v.

        # CORRECTION (2026-05, foundation §16): previous version used
        # γ = √(2·E_target / m), which ignored the cross-term m·(v·u)·γ.
        # The post-hoc cap in `_bound_linear_kick_dcr_velocities` masked
        # the discrepancy by clipping. The new γ*_A hits E_target exactly
        # so the cap binds only for genuine multi-body / passivity reasons.

        # DEVIATION (foundation §15, paper §5.4): the task spec proposed
        # k = 1/m + (r × u) · I_inv · (r × u). We drop the angular term in
        # Version A because the kick is COM-linear-only — including the
        # angular term would model energy not actually injected. Version B
        # keeps the full formula AND applies the angular kick.

        Multi-contact aggregation: largest-speed kick per body wins. (Same
        rule as Coevoet's `max` over contacts.) NOTE: the per-body max is
        taken over γ*_A values that each depend on the body's *current* v,
        not on a contact-independent magnitude — this is still a valid
        "largest energy contribution" rule because every kick along its own
        u realizes E_target by construction.
        """
        frames = self._get_tangent_frames()
        kicks_by_body: dict[int, LinearKick] = {}
        for contact in resting_contacts:
            # Push direction from elastic to body (matches _resting_push_dir
            # convention used by the cap and the coevoet apply path).
            if contact.body_b == self.elastic_body_idx:
                other_body = contact.body_a
                push_dir = -contact.normal
            else:
                other_body = contact.body_b
                push_dir = contact.normal
            body = bodies[other_body]
            if body.is_static or body.mass <= 0.0:
                continue
            # Rest normal — same axis the PGS friction cone was closed on.
            n_rest = push_dir
            # Deformed contact normal must be computed BEFORE the energy
            # helper, because γ*_A depends on the cross-term v·u.
            u, theta, _ = self._deformed_normal(
                contact_point=contact.point,
                push_dir=push_dir,
                q_history=q_history,
                frames=frames,
            )
            speed = gamma_from_energy_linear(body, u, E_target)
            if speed <= 0.0:
                continue

            # --- Optional kinematic cap (Coevoet's h-invariance) ---
            if self.kinematic_cap == "coevoet" and h > 0.0:
                self.last_kinematic_cap_attempted += 1
                d_max = self._compute_max_displacement(
                    contact.point, contact.normal, q_history)
                speed_cap = d_max / h
                if speed > speed_cap:
                    self.last_kinematic_cap_fired += 1
                    speed = speed_cap
                if speed <= 0.0:
                    continue

            # --- Optional friction-cone clip around the REST normal ---
            # For Version A the impulse and the COM velocity-change are
            # parallel (Δv = ΔJ / m), so the cone clip in velocity space
            # is algebraically identical to the impulse-space clip.
            if self.friction_cone_clip_enabled:
                self.last_friction_clip_attempted += 1
                mu = min(
                    bodies[contact.body_a].friction,
                    bodies[contact.body_b].friction,
                )
                dv_vec = speed * u
                dv_vec_clipped, s_t = friction_cone_clip(dv_vec, n_rest, mu)
                if s_t < 1.0:
                    self.last_friction_clip_fired += 1
                speed_eff = float(np.linalg.norm(dv_vec_clipped))
                if speed_eff < _EPS_TINY:
                    continue
                u = dv_vec_clipped / speed_eff
                speed = speed_eff

            kk = LinearKick(body_idx=other_body, speed=speed, u=u.copy(),
                            theta=theta)
            prev = kicks_by_body.get(other_body)
            if prev is None or kk.speed > prev.speed:
                kicks_by_body[other_body] = kk
        return list(kicks_by_body.values())

    # ------------------------------------------------------------------
    # Version B: energy-prescribed, full k, deformed normal, point impulse
    # ------------------------------------------------------------------

    def _compute_distant_response_energy_B(
        self,
        resting_contacts: list[Contact],
        q_history: NDArray[np.float64],
        bodies: list[RigidBody],
        E_target: float,
        h: float,
    ) -> list[PointImpulseKick]:
        """Energy-prescribed distant kicks as TRUE point impulses (Version B).

        For each resting contact:
            u    = compute_deformed_normal(...)                 (this follow-up)
            r    = contact.point - body.position
            v_c  = v + ω × r                                    (contact-pt vel)
            k    = 1/m + (r × u) · I_world_inv · (r × u)         (paper Eq. 17)
            a    = m² · k
            b    = m · (u · v_c)
            γ*_B = (-b + √(b² + 2·a·E_target)) / a              (foundation §16)
            J    = m · γ*_B
        Applied by the world's `_apply_point_impulse_dcr_velocities`:
            v_lin += (J/m) · u
            ω     += J · I_world_inv · (r × u)
        Realized linear+angular ΔKE = E_target exactly (within float
        tolerance) for every body, regardless of incoming v and ω.

        Two optional post-processing steps (see class docstring):
            * kinematic_cap="coevoet" caps J ≤ m·(d_max/h) per contact so
              the per-step kick speed inherits Coevoet's h-invariance.
            * friction_cone_clip_enabled=True projects the resulting J·u
              onto the Coulomb friction cone around the REST normal
              n_rest (= push_dir before deformation), preventing the
              tangential leak that the post-solver kick along n' would
              otherwise produce.

        # CORRECTION (2026-05, foundation §16): previous version used
        # J = √(2·E_target / k), which assumed v_c · u = 0 (dropped the
        # cross-term m·(u·v_c)·γ). The post-hoc cap masked the drift; the
        # new γ*_B hits E_target exactly so the cap binds only for genuine
        # multi-body / passivity reasons.

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
            # Rest normal — same axis the PGS friction cone was closed on.
            n_rest = push_dir
            # Deformed contact normal (patch_fit or barbic_james; see
            # deformed_normal_method docstring).
            u, theta, _ = self._deformed_normal(
                contact_point=contact.point,
                push_dir=push_dir,
                q_history=q_history,
                frames=frames,
            )
            r = contact.point - body.position
            J = impulse_from_energy_point(body, r, u, E_target)
            if J <= 0.0:
                continue

            # --- Optional kinematic cap (Coevoet's h-invariance) ---
            if self.kinematic_cap == "coevoet" and h > 0.0:
                self.last_kinematic_cap_attempted += 1
                d_max = self._compute_max_displacement(
                    contact.point, contact.normal, q_history)
                J_max = body.mass * (d_max / h)
                if J > J_max:
                    self.last_kinematic_cap_fired += 1
                    J = J_max
                if J <= 0.0:
                    continue

            # --- Optional contact-point Coulomb friction correction ----
            # Replaces the earlier on-u friction_cone_clip (which ignored
            # the angular contribution to Δv_c). The actual correction is
            # applied at the contact point by the world after the main
            # kick — see contact_point_friction_correction and
            # dcr_world's _apply_point_impulse_dcr_velocities. The kick
            # simply carries the cone parameters n_rest/mu through.
            kick_n_rest = None
            kick_mu = None
            if self.friction_cone_clip_enabled:
                self.last_friction_clip_attempted += 1
                kick_n_rest = n_rest.copy()
                kick_mu = float(min(
                    bodies[contact.body_a].friction,
                    bodies[contact.body_b].friction,
                ))

            kk = PointImpulseKick(
                body_idx=other_body, J_mag=J, u=u.copy(), r=r.copy(),
                theta=theta,
                n_rest=kick_n_rest, mu=kick_mu,
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
        self.last_linear_kicks = None
        self.last_point_impulse_kicks = None
