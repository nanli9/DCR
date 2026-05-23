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
from .distant_velocity import LinearKick, PointImpulseKick
from .modal_dcr import ModalDCRCoupler
from .passive_dcr import PassiveDCRCoupler
from .spatial_dcr import SpatialDCRCoupler


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
                    # Version B: deformed normal + true point impulse.
                    kicks_b, s = self._bound_point_impulse_dcr_velocities(
                        coupler.last_point_impulse_kicks)
                    if s < clip_eps:
                        self.last_dcr_clipped = True
                    self._apply_point_impulse_dcr_velocities(kicks_b, scale=s)
                elif coupler.last_linear_kicks is not None:
                    # Version A: deformed normal + linear COM kick.
                    kicks_a, s = self._bound_linear_kick_dcr_velocities(
                        coupler.last_linear_kicks)
                    if s < clip_eps:
                        self.last_dcr_clipped = True
                    self._apply_linear_kick_dcr_velocities(kicks_a, scale=s)
                else:
                    # Scalar-dv path (coevoet / bounded_coevoet).
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

    def _bound_linear_kick_dcr_velocities(
        self,
        kicks: list[LinearKick],
    ) -> tuple[list[LinearKick], float]:
        """Hard rigid-energy bound for Version-A linear-only kicks at the
        deformed contact normal.

        Same scaling idea as _bound_dcr_velocities, but Δv is a true 3D
        vector `speed · u` (u = deformed normal, not necessarily the
        un-deformed contact normal). Per-body ΔE per kick on body p:
            Δv_p = scale · speed · u
            ΔE_p = m_p (v_p⁻ · Δv_p) + ½ m_p ‖Δv_p‖²
                 = scale · m_p · speed · (v_p⁻ · u)
                   + scale² · ½ m_p · speed²
        Sum over kicks and scale-search for s ∈ [0, 1].

        No-op when self.enforce_rigid_energy_bound is False.
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
            v_minus = body.velocity[0:3]
            v_dot_u = float(v_minus @ kk.u)
            A_lin += body.mass * kk.speed * v_dot_u
            B_quad += 0.5 * body.mass * kk.speed * kk.speed
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

    def _apply_linear_kick_dcr_velocities(
        self,
        kicks: list[LinearKick],
        scale: float = 1.0,
    ) -> None:
        """Apply linear COM kicks along the deformed contact normal.
        Version A kick path.

        For each kick on body p with speed magnitude `speed` along u:
            body.velocity[0:3] += scale · speed · u
        Realized ΔKE = ½ m (scale·speed)² = scale² · E_target.
        """
        for kk in kicks:
            body = self.bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0:
                continue
            dv = scale * kk.speed
            ke_before = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            body.velocity[0:3] += dv * kk.u
            ke_after = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            self.last_dcr_ke_injected += ke_after - ke_before

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
