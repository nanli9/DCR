"""DCR-enabled simulation world.

Extends the rigid body World (Stage 1) with modal-path distant collision
response (Eqs. 9–13). After the PGS solve, new impact impulses on elastic
bodies are propagated via the IIR modal stepper, and the resulting surface
displacement is converted to separation velocities at resting contacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..rigid.body import RigidBody, quat_integrate
from ..rigid.collision import Contact, detect_contacts
from ..rigid.energy import rigid_kinetic_energy
from ..rigid.joint import DistanceJoint
from ..rigid.solver import ConstraintSolver
from .distant_velocity import PointImpulseKick
from .modal_dcr import ModalDCRCoupler
from .passive_dcr import PassiveDCRCoupler
from .spatial_dcr import SpatialDCRCoupler
from .tilt_dcr import TiltDCRCoupler, TiltResult, apply_tilt_bounds, compute_tilt_lateral_velocity


@dataclass
class DCRWorld:
    """Rigid body world with modal-path DCR coupling.

    Usage is identical to rigid.World, but with added DCR couplers
    that process elastic body vibrations after each PGS solve.

    Supports both original forced-IIR couplers (Stage 5) and passive
    energy-bounded couplers (Stage E3). Use one or the other per body.

    Attributes:
        dcr_couplers: List of ModalDCRCoupler, one per elastic body.
        passive_couplers: List of PassiveDCRCoupler for energy-bounded injection.
        eta: Transfer efficiency for passive couplers (foundation §1).
        dcr_enabled: Toggle DCR on/off (for A/B comparison).
    """

    bodies: list[RigidBody] = field(default_factory=list)
    joints: list[DistanceJoint] = field(default_factory=list)
    gravity: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -9.81, 0.0]))
    h: float = 1e-2
    solver: ConstraintSolver = field(default_factory=lambda: ConstraintSolver())
    time: float = 0.0
    prev_contacts: list[Contact] = field(default_factory=list)

    dcr_couplers: list[ModalDCRCoupler] = field(default_factory=list)
    passive_couplers: list[PassiveDCRCoupler] = field(default_factory=list)
    spatial_couplers: list[SpatialDCRCoupler] = field(default_factory=list)
    tilt_couplers: list[TiltDCRCoupler] = field(default_factory=list)
    tilt_mode: str = "tilt-coupled"  # "tilt" (lateral only) or "tilt-coupled" (capped vert + lat)
    dcr_enabled: bool = True
    eta: float = 0.3  # Transfer efficiency η ∈ [0, 1] (foundation §1)
    # Hard rigid-energy bound on DCR distant kicks (this follow-up).
    # When True, _bound_dcr_velocities scales the proposed Δv so the
    # injected rigid KE stays ≤ this step's rigid-loss budget. Default
    # OFF preserves bit-for-bit the pre-follow-up "coevoet" behavior.
    enforce_rigid_energy_bound: bool = False

    # Diagnostics.
    last_dcr_ke_injected: float = 0.0
    last_E_loss: float = 0.0
    last_E_max: float = 0.0
    # New diagnostics for the energy-prescribed velocity modes:
    last_E_rigid_out_before_cap: float = 0.0
    last_E_rigid_out_after_cap: float = 0.0
    last_dcr_clipped: bool = False

    def __post_init__(self) -> None:
        self.solver.h = self.h

    @property
    def tilt_only(self) -> bool:
        """Backward-compat: tilt_only=True ↔ tilt_mode='tilt'."""
        return self.tilt_mode == "tilt"

    @tilt_only.setter
    def tilt_only(self, value: bool) -> None:
        self.tilt_mode = "tilt" if value else "tilt-coupled"

    def add_body(self, body: RigidBody) -> int:
        self.bodies.append(body)
        return len(self.bodies) - 1

    def add_joint(self, joint: DistanceJoint) -> None:
        self.joints.append(joint)

    def add_dcr_coupler(self, coupler: ModalDCRCoupler) -> None:
        self.dcr_couplers.append(coupler)

    def add_passive_coupler(self, coupler: PassiveDCRCoupler) -> None:
        self.passive_couplers.append(coupler)

    def add_spatial_coupler(self, coupler: SpatialDCRCoupler) -> None:
        self.spatial_couplers.append(coupler)

    def add_tilt_coupler(self, coupler: TiltDCRCoupler) -> None:
        self.tilt_couplers.append(coupler)

    def step(self) -> list[Contact]:
        """Advance simulation by one time step h with DCR.

        Flow:
            1. Apply gravity
            2. Detect contacts
            3. PGS solve → λ
            4. DCR: map new impacts → IIR → Δv at resting contacts (Eqs. 9–13)
            5. Apply DCR velocity corrections (Path B, Eqs. 12–13)
            6. Symplectic Euler position integration

        Returns the contact list for this step.
        """
        # 1. Apply gravity.
        for body in self.bodies:
            body.force = np.zeros(6)
            if not body.is_static:
                body.force[0:3] = body.mass * self.gravity

        # 2. Detect contacts.
        contacts = detect_contacts(self.bodies, self.prev_contacts)

        # E0.3: sample rigid KE before solve (foundation §1).
        E_pre = rigid_kinetic_energy(self.bodies)

        # 3. Solve constraints → velocities updated, get λ.
        lam = self.solver.solve(self.bodies, contacts, self.joints)

        # E0.3: sample rigid KE after solve, compute E_loss (foundation §1).
        E_post = rigid_kinetic_energy(self.bodies)
        self.last_E_loss = max(0.0, E_pre - E_post)
        self.last_E_max = self.eta * self.last_E_loss

        # 4. DCR pipeline (Path B: apply velocity corrections post-solve).
        self.last_dcr_ke_injected = 0.0
        self.last_E_rigid_out_before_cap = 0.0
        self.last_E_rigid_out_after_cap = 0.0
        self.last_dcr_clipped = False
        clip_eps = 1.0 - 1e-9  # treat s < this as "scaling fired"
        if self.dcr_enabled and len(lam) > 0:
            # Original modal-path couplers (Stage 5, forced IIR).
            for coupler in self.dcr_couplers:
                dcr_velocities = coupler.process_step(contacts, lam, self.h)
                dcr_velocities, s = self._bound_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)
                if s < clip_eps:
                    self.last_dcr_clipped = True
                self._apply_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)

            # Passive energy-bounded couplers (Stage E3) +
            # this follow-up's energy_prescribed* modes.
            for coupler in self.passive_couplers:
                dcr_velocities = coupler.process_step(
                    contacts, lam, self.h, self.last_E_max,
                    bodies=self.bodies)
                if coupler.last_point_impulse_kicks is not None:
                    # Version B: point-impulse path with its own cap.
                    kicks, s = self._bound_point_impulse_dcr_velocities(
                        coupler.last_point_impulse_kicks)
                    if s < clip_eps:
                        self.last_dcr_clipped = True
                    self._apply_point_impulse_dcr_velocities(kicks, scale=s)
                else:
                    # Scalar-dv path (coevoet / bounded_coevoet / Version A).
                    dcr_velocities, s = self._bound_dcr_velocities(
                        dcr_velocities, contacts, coupler.elastic_body_idx)
                    if s < clip_eps:
                        self.last_dcr_clipped = True
                    self._apply_dcr_velocities(
                        dcr_velocities, contacts, coupler.elastic_body_idx)

            # Spatial-attenuation couplers (Stage 6).
            for coupler in self.spatial_couplers:
                dcr_velocities = coupler.process_step(contacts, lam, self.h)
                dcr_velocities, s = self._bound_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)
                if s < clip_eps:
                    self.last_dcr_clipped = True
                self._apply_dcr_velocities(
                    dcr_velocities, contacts, coupler.elastic_body_idx)

            # Tilt-DCR couplers (contact frame extension).
            # The tilt coupler replaces the normal DCR kick: the full
            # impulse goes along n' (tilted normal), not n + extra J_t.
            # For contacts without tilt (theta ~ 0), apply the standard
            # normal kick as fallback.
            for coupler in self.tilt_couplers:
                tilt_results = coupler.process_step(
                    contacts, lam, self.h, self.last_E_max)
                # Bodies that got tilt results — their kick is fully
                # handled by _apply_tilt_dcr_velocities along n'.
                tilted_bodies = {r.body_idx for r in tilt_results}
                # For bodies with no tilt (theta ~ 0), fall back to
                # the standard normal kick (unless tilt_only mode).
                if self.tilt_mode == "tilt-coupled":
                    fallback = {k: v for k, v in coupler.last_dcr_velocities.items()
                                if k not in tilted_bodies}
                    if fallback:
                        self._apply_dcr_velocities(
                            fallback, contacts, coupler.elastic_body_idx)
                self._apply_tilt_dcr_velocities(tilt_results, coupler)

        # 5. Integrate positions.
        for body in self.bodies:
            if body.is_static:
                continue
            body.position += self.h * body.velocity[:3]
            body.orientation = quat_integrate(
                body.orientation, body.velocity[3:6], self.h)

        self.time += self.h
        self.prev_contacts = contacts
        return contacts

    def _resting_push_dir(
        self, body_idx: int, contacts: list[Contact], elastic_idx: int,
    ) -> NDArray[np.float64] | None:
        """Unit push direction for body_idx's distant contact, or None.

        Mirrors the per-body normal-orientation logic in
        _apply_dcr_velocities: a contact (elastic A, body B) pushes B along
        +c.normal; (elastic B, body A) pushes A along -c.normal.
        """
        for c in contacts:
            if c.is_new:
                continue
            if (c.body_a == elastic_idx and c.body_b == body_idx):
                return -c.normal
            if (c.body_b == elastic_idx and c.body_a == body_idx):
                return c.normal
        return None

    def _bound_dcr_velocities(
        self,
        dcr_velocities: dict[int, float],
        contacts: list[Contact],
        elastic_idx: int,
    ) -> tuple[dict[int, float], float]:
        """Hard rigid-energy bound for SCALAR-Δv DCR kicks (this follow-up).

        Returns (scaled_dcr_velocities, scale_s). scale_s ∈ [0, 1] is 1.0
        when no scaling was needed; <1.0 means the proposed injection was
        clipped.

        Vector form of the scaling rule (foundation §15, this follow-up):
            ΔE_p = m_p (v_p⁻ · Δv_p) + ½ m_p ‖Δv_p‖²
        Scaling all Δv_p by a common s ∈ [0, 1] gives
            E_inj(s) = s·A + s²·B
        with
            A = Σ m_p (v_p⁻ · Δv_p)              (linear / cross term)
            B = Σ ½ m_p ‖Δv_p‖²                  (quadratic term)
        and the largest s ∈ [0, 1] solving s²B + sA ≤ ΔE_loss is
            s = (−A + √(A² + 4 B · ΔE_loss)) / (2B)             (B > 0)

        Scalar reduction: each Δv_p = dv * push_dir_p (unit), so
        ‖Δv_p‖² = dv², (v_p⁻ · Δv_p) = dv · (v_body · push_dir_p).

        No-op (s = 1.0) when self.enforce_rigid_energy_bound is False.
        Pre/post-cap injected energies are stored in
        last_E_rigid_out_before_cap / last_E_rigid_out_after_cap.
        """
        if not dcr_velocities:
            return dcr_velocities, 1.0
        # 0.1% safety margin so the realized injection stays strictly
        # below the rigid loss (avoids numerical equality).
        budget = 0.999 * self.last_E_loss

        A_lin = 0.0
        B_quad = 0.0
        for body_idx, dv in dcr_velocities.items():
            body = self.bodies[body_idx]
            if body.is_static:
                continue
            push_dir = self._resting_push_dir(body_idx, contacts, elastic_idx)
            if push_dir is None:
                continue
            v_minus_n = float(np.dot(body.velocity[:3], push_dir))
            A_lin += body.mass * dv * v_minus_n
            B_quad += 0.5 * body.mass * dv * dv

        E_full = A_lin + B_quad  # injected at s = 1
        self.last_E_rigid_out_before_cap += float(E_full)
        if not self.enforce_rigid_energy_bound:
            self.last_E_rigid_out_after_cap += float(E_full)
            return dcr_velocities, 1.0
        if B_quad <= 0.0 or E_full <= budget:
            self.last_E_rigid_out_after_cap += float(E_full)
            return dcr_velocities, 1.0
        disc = A_lin * A_lin + 4.0 * B_quad * budget
        s = (-A_lin + np.sqrt(max(0.0, disc))) / (2.0 * B_quad)
        s = float(np.clip(s, 0.0, 1.0))
        self.last_E_rigid_out_after_cap += float(s * A_lin + s * s * B_quad)
        return {k: v * s for k, v in dcr_velocities.items()}, s

    def _bound_point_impulse_dcr_velocities(
        self,
        kicks: list[PointImpulseKick],
    ) -> tuple[list[PointImpulseKick], float]:
        """Hard rigid-energy bound for point-impulse kicks (Version B).

        Same scaling idea as _bound_dcr_velocities, but the per-body ΔE has
        both linear and rotational parts. Scaling all impulses by s gives
            E_inj(s) = s · A + s² · B
        with
            A = Σ (m_p (v_lin⁻ · Δv_lin) + ω⁻ · I · Δω)
            B = Σ (½ m_p ‖Δv_lin‖² + ½ Δω · I · Δω)
        where for each kick on body p:
            Δv_lin = (J/m_p) · u
            Δω     = J · I_inv_p @ (r × u)

        No-op (s = 1.0) when self.enforce_rigid_energy_bound is False.
        """
        if not kicks:
            return kicks, 1.0
        budget = 0.999 * self.last_E_loss
        A_lin = 0.0
        B_quad = 0.0
        for kk in kicks:
            body = self.bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0:
                continue
            J = kk.J_mag
            dv = (J / body.mass) * kk.u
            I_inv = body.inertia_world_inv()
            I_world = body.inertia_world()
            dom = J * (I_inv @ np.cross(kk.r, kk.u))
            v_minus = body.velocity[0:3]
            w_minus = body.velocity[3:6]
            A_lin += body.mass * float(v_minus @ dv) + float(
                w_minus @ (I_world @ dom))
            B_quad += 0.5 * body.mass * float(dv @ dv) + 0.5 * float(
                dom @ (I_world @ dom))
        E_full = A_lin + B_quad
        self.last_E_rigid_out_before_cap += float(E_full)
        if not self.enforce_rigid_energy_bound:
            self.last_E_rigid_out_after_cap += float(E_full)
            return kicks, 1.0
        if B_quad <= 0.0 or E_full <= budget:
            self.last_E_rigid_out_after_cap += float(E_full)
            return kicks, 1.0
        disc = A_lin * A_lin + 4.0 * B_quad * budget
        s = (-A_lin + np.sqrt(max(0.0, disc))) / (2.0 * B_quad)
        s = float(np.clip(s, 0.0, 1.0))
        self.last_E_rigid_out_after_cap += float(s * A_lin + s * s * B_quad)
        return kicks, s

    def _apply_point_impulse_dcr_velocities(
        self,
        kicks: list[PointImpulseKick],
        scale: float = 1.0,
    ) -> None:
        """Apply true point impulses (linear + angular). Version B kick path.

        For each kick on body p with impulse magnitude J along u at lever
        arm r = contact_point - body.position:

            v_lin_p += scale · (J/m_p) · u
            ω_p     += scale · J · I_world_inv_p @ cross(r, u)

        Realized ΔKE = ½ (scale·J)² · k where k = 1/m + (r×u)·I_inv·(r×u),
        which equals scale² · E_target by construction of J in the coupler.
        """
        for kk in kicks:
            body = self.bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0:
                continue
            J = scale * kk.J_mag
            ke_before = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_before += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            body.velocity[0:3] += (J / body.mass) * kk.u
            body.velocity[3:6] += J * (
                body.inertia_world_inv() @ np.cross(kk.r, kk.u))
            ke_after = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_after += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            self.last_dcr_ke_injected += ke_after - ke_before

    def _apply_dcr_velocities(
        self,
        dcr_velocities: dict[int, float],
        contacts: list[Contact],
        elastic_idx: int,
    ) -> None:
        """Apply DCR separation velocities to resting bodies (Eq. 13/19)."""
        for body_idx, dv in dcr_velocities.items():
            body = self.bodies[body_idx]
            if body.is_static:
                continue

            for c in contacts:
                if c.is_new:
                    continue
                if (c.body_a == elastic_idx and c.body_b == body_idx) or \
                   (c.body_b == elastic_idx and c.body_a == body_idx):
                    # DEVIATION: solver normals point from B toward A.
                    normal = c.normal
                    if c.body_b == elastic_idx:
                        push_dir = normal   # push A away from elastic B
                    else:
                        push_dir = -normal  # push B away from elastic A

                    ke_before = 0.5 * body.mass * np.dot(
                        body.velocity[:3], body.velocity[:3])
                    body.velocity[:3] += dv * push_dir
                    ke_after = 0.5 * body.mass * np.dot(
                        body.velocity[:3], body.velocity[:3])
                    self.last_dcr_ke_injected += ke_after - ke_before
                    break

    def _apply_tilt_dcr_velocities(
        self,
        tilt_results: list[TiltResult],
        coupler: TiltDCRCoupler,
    ) -> None:
        """Apply amplified, bounded lateral velocity from tilt + optional capped normal.

        # DEVIATION: the paper applies DCR impulses along the original
        # contact normal. This extension derives a lateral direction from
        # the modal displacement gradient and applies an amplified tangential
        # correction. The tilted normal is NOT used to replace the solver
        # contact normal or to apply v += dv * n_tilt.

        In 'tilt' mode: only the lateral component is applied.
        In 'tilt-coupled' mode: capped normal + lateral are both applied.

        Angular response emerges from friction constraints in subsequent
        solver steps — no direct angular velocity injection.
        """
        for r in tilt_results:
            body = self.bodies[r.body_idx]
            if body.is_static:
                continue

            dv_t, t_dir, _dbg = compute_tilt_lateral_velocity(
                delta_v=r.dv,
                mass=body.mass,
                n=r.push_dir,
                n_tilt=r.n_tilt,
                lateral_fraction=coupler.lateral_fraction,
                dv_t_max=coupler.dv_t_max,
                eta_t=coupler.eta_t,
                mu_dcr=coupler.mu_dcr,
            )

            ke_before = 0.5 * body.mass * np.dot(
                body.velocity[:3], body.velocity[:3])

            # Lateral component (both tilt modes)
            if dv_t > 0.0 and t_dir is not None:
                body.velocity[:3] += dv_t * t_dir

            # Capped normal component (tilt-coupled only)
            if self.tilt_mode == "tilt-coupled":
                dv_n = min(abs(r.dv), coupler.dv_n_max)
                body.velocity[:3] += dv_n * r.push_dir

            ke_after = 0.5 * body.mass * np.dot(
                body.velocity[:3], body.velocity[:3])
            self.last_dcr_ke_injected += ke_after - ke_before

    def kinetic_energy(self) -> float:
        ke = 0.0
        for body in self.bodies:
            if body.is_static:
                continue
            v = body.velocity
            M = body.mass_matrix()
            ke += 0.5 * v @ M @ v
        return ke

    def potential_energy(self, ref_height: float = 0.0) -> float:
        pe = 0.0
        for body in self.bodies:
            if body.is_static:
                continue
            pe += body.mass * (-self.gravity[1]) * (body.position[1] - ref_height)
        return pe

    def total_energy(self, ref_height: float = 0.0) -> float:
        return self.kinetic_energy() + self.potential_energy(ref_height)
