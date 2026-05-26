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
from .distant_velocity import (
    LinearKick,
    PointImpulseKick,
    contact_point_friction_correction,
)
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

    # Energy bookkeeping log (foundation §15 invariant + plotting).
    # When True, append one EnergyLogEntry per step to `self.energy_log`.
    # OFF by default to keep step() overhead-free for regression runs.
    enable_energy_logging: bool = False
    energy_log: "EnergyLog" = field(default_factory=lambda: None)  # noqa: F821

    # B2 per-contact impulse log (`benchmark/BENCHMARK_PROMPT.md` §2.4).
    # When True, the step appends one `ImpulseLogEntry` per active contact
    # this step (i.e. those whose `lam` block has nonzero impulses) to
    # `self.impulse_log`. `body_name_map` is body-index → body-name and
    # must be populated by the caller before `step()` if it wants the
    # CSV's `body_name` column filled (otherwise it falls back to
    # `body_<idx>`). OFF by default — only B2 sets it.
    enable_impulse_logging: bool = False
    impulse_log: "ImpulseLog" = field(default_factory=lambda: None)  # noqa: F821
    body_name_map: dict[int, str] = field(default_factory=dict)

    # B6 per-step wall-clock log (`benchmark/BENCHMARK_PROMPT.md` §2.5).
    # Same on/off discipline. OFF by default; only B6 sets it.
    enable_timing_log: bool = False
    timing_log: "TimingLog" = field(default_factory=lambda: None)  # noqa: F821

    def __post_init__(self) -> None:
        self.solver.h = self.h
        # Lazy import to avoid circular dep with dcr.benchmark at module-load
        if self.enable_energy_logging and self.energy_log is None:
            from dcr.benchmark.energy_log import EnergyLog
            self.energy_log = EnergyLog()

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
        # B6 timing log: monotonic step-start timestamp.
        if self.enable_timing_log:
            import time as _time
            _step_t0 = _time.perf_counter_ns()
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
        if self.enable_timing_log:
            import time as _time
            _rigid_t0 = _time.perf_counter_ns()
        lam = self.solver.solve(self.bodies, contacts, self.joints)
        if self.enable_timing_log:
            _rigid_solve_ms = (_time.perf_counter_ns() - _rigid_t0) * 1e-6
        else:
            _rigid_solve_ms = 0.0

        # B2 impulse log: snapshot of (J_n, J_t1, J_t2) + rest normal per
        # contact for the §2.4 CSV. Deformed normals come from the
        # coupler in step 4 — we record both here using whatever it
        # stashed last step (or fall back to n_rest). For the FIRST step
        # there's no prior coupler state, so this is informational only.
        # Reading post-step (after the coupler has run) was considered
        # but loses the contact list at that point (contacts mutate).
        self._impulse_log_capture_pending = (
            contacts, lam, list(self.bodies)
        ) if self.enable_impulse_logging else None

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
        # Timing-log defaults for the case where dcr is disabled or no
        # contacts (the timed blocks below don't fire then).
        _distant_response_ms = 0.0
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
            if self.enable_timing_log:
                import time as _time
                _dr_t0 = _time.perf_counter_ns()
            for coupler in self.passive_couplers:
                dcr_velocities = coupler.process_step(
                    contacts, lam, self.h, self.last_E_max,
                    bodies=self.bodies)
                if (getattr(coupler, "last_patch_kicks", None)
                        is not None):
                    # Patch-based reformulation (prompt §9): full 3-vector
                    # impulse at the patch centroid. The coupler has
                    # already applied §9.5 (cone) and §9.6 (passivity);
                    # the world just applies the impulse to the receiver.
                    self._apply_patch_impulse_dcr_velocities(
                        coupler.last_patch_kicks)
                elif coupler.last_point_impulse_kicks is not None:
                    # Version B: deformed normal + true point impulse.
                    kicks_b, s = self._bound_point_impulse_dcr_velocities(
                        coupler.last_point_impulse_kicks)
                    if s < clip_eps:
                        self.last_dcr_clipped = True
                    # The world's apply pass returns the number of
                    # contact-point friction corrections that actually
                    # fired this step (only when the coupler tagged the
                    # kicks with n_rest/mu; zero otherwise).
                    n_friction_fired = (
                        self._apply_point_impulse_dcr_velocities(
                            kicks_b, scale=s))
                    coupler.last_friction_clip_fired = n_friction_fired
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

            if self.enable_timing_log:
                _distant_response_ms = (
                    _time.perf_counter_ns() - _dr_t0) * 1e-6
            else:
                _distant_response_ms = 0.0

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

        # 5.4 B6 timing log: one row per step. The per-mode breakdown
        # (`t_modal_step_ms`, `t_deformed_normal_ms`) reads the first
        # passive coupler's accumulators (single-elastic-body scenes —
        # same convention as energy logging).
        if (self.enable_timing_log and self.timing_log is not None):
            from dcr.benchmark.timing_log import TimingLogEntry
            import time as _time
            _total_ms = (_time.perf_counter_ns() - _step_t0) * 1e-6
            _modal_ms = 0.0
            _dn_ms = 0.0
            for _c in self.passive_couplers:
                _modal_ms = float(getattr(_c, "last_timing_modal_ms", 0.0))
                _dn_ms = float(getattr(
                    _c, "last_timing_deformed_normal_ms", 0.0))
                break  # first coupler only — matches energy log convention
            step_idx = (len(self.energy_log)
                        if self.energy_log is not None else 0)
            self.timing_log.append(TimingLogEntry(
                step=step_idx, t=self.time,
                t_rigid_solve_ms=_rigid_solve_ms,
                t_modal_step_ms=_modal_ms,
                t_deformed_normal_ms=_dn_ms,
                t_distant_response_ms=_distant_response_ms,
                t_total_step_ms=_total_ms,
            ))

        # 5.5 B2 impulse log: flush per-active-contact rows for this step.
        # Reads the coupler's `last_deformed_normals` (keyed by id(contact))
        # populated during step 4 above; contacts the coupler didn't touch
        # fall back to n_rest. Skipped when no impulse logging is on.
        if (self.enable_impulse_logging and self.impulse_log is not None
                and self._impulse_log_capture_pending is not None):
            from dcr.benchmark.impulse_log import ImpulseLogEntry
            from dcr.rigid.solver import _pick_friction_dirs
            cap_contacts, cap_lam, _ = self._impulse_log_capture_pending
            step_idx = (len(self.energy_log)
                        if self.energy_log is not None else 0)
            # Collect deformed-normal stashes across all passive couplers.
            stash: dict[int, NDArray[np.float64]] = {}
            for c in self.passive_couplers:
                stash.update(getattr(c, "last_deformed_normals", {}) or {})
            for ci, contact in enumerate(cap_contacts):
                if 3 * ci + 2 >= len(cap_lam):
                    continue
                J_n = float(cap_lam[3 * ci])
                J_t1 = float(cap_lam[3 * ci + 1])
                J_t2 = float(cap_lam[3 * ci + 2])
                # Filter to "active" rows: at least one of J_n, J_t1, J_t2
                # is meaningfully non-zero. Avoids a row per inactive
                # resting contact (lots of zeros for the boulder-on-shelf
                # static stack).
                if max(abs(J_n), abs(J_t1), abs(J_t2)) < 1e-9:
                    continue
                # Body to attribute to: the non-elastic / non-static body.
                # If both are non-elastic, default to body_a. Names come
                # from `body_name_map` (run_one.py populates this).
                body_idx_for_name = contact.body_b
                if (self.bodies[contact.body_b].is_static
                        and not self.bodies[contact.body_a].is_static):
                    body_idx_for_name = contact.body_a
                body_name = self.body_name_map.get(
                    body_idx_for_name, f"body_{body_idx_for_name}")
                n_rest = np.asarray(contact.normal, dtype=np.float64)
                n_def = stash.get(id(contact), n_rest).copy()
                self.impulse_log.append(ImpulseLogEntry(
                    step=step_idx, t=self.time,
                    body_name=body_name,
                    contact_x=float(contact.point[0]),
                    contact_y=float(contact.point[1]),
                    contact_z=float(contact.point[2]),
                    J_normal=J_n,
                    J_tangential_u=J_t1,
                    J_tangential_v=J_t2,
                    n_rest=n_rest,
                    n_deformed=n_def,
                ))
            self._impulse_log_capture_pending = None

        # 6. Energy log (one entry per step when enabled). Pulls from
        # both rigid (E_KE, E_loss) and modal (E_modal pre/post kick,
        # alpha) state. Foundation §15 invariant is checked offline by
        # EnergyLog.invariant_violation().
        if self.enable_energy_logging and self.energy_log is not None:
            from dcr.benchmark.energy_log import EnergyLogEntry
            E_rigid_post = rigid_kinetic_energy(self.bodies)
            E_modal_post = 0.0
            dE_modal = 0.0
            alpha_used = 0.0
            beta_used = 0.0
            n_active_kicks = 0
            for coupler in self.passive_couplers:
                E_modal_post = float(getattr(
                    coupler, "last_E_modal_post_kick", 0.0))
                E_pre_kick = float(getattr(
                    coupler, "last_E_modal_pre_kick", 0.0))
                dE_modal = E_modal_post - E_pre_kick
                alpha_used = float(getattr(coupler, "last_alpha", 0.0))
                beta_used = float(getattr(
                    coupler, "energy_response_beta", 0.0))
                # `n_active_kicks` reflects whichever code-path the
                # coupler dispatched on this step. Each branch sets
                # exactly one of these to non-None on the coupler.
                if getattr(coupler, "last_patch_kicks", None):
                    n_active_kicks += sum(
                        1 for k in coupler.last_patch_kicks
                        if k is not None
                    )
                elif getattr(coupler, "last_point_impulse_kicks", None):
                    n_active_kicks += len(coupler.last_point_impulse_kicks)
                elif getattr(coupler, "last_linear_kicks", None):
                    n_active_kicks += len(coupler.last_linear_kicks)
                else:
                    # Scalar-Δv path (coevoet): count non-zero entries
                    # in last_dcr_velocities if exposed by the coupler.
                    dv = getattr(coupler, "last_dcr_velocities", None) or {}
                    n_active_kicks += sum(1 for v in dv.values() if v != 0.0)
                # Only the first passive coupler is logged (single-
                # elastic-body scenes — covers all spec scenes).
                break
            # Paper-baseline mode logs α as NaN per spec §2.1.
            is_paper_baseline = any(
                getattr(c, "paper_baseline_mode", False)
                for c in self.passive_couplers
            )
            alpha_field = float("nan") if is_paper_baseline else alpha_used
            self.energy_log.append(EnergyLogEntry(
                step=len(self.energy_log),
                t=self.time,
                E_rigid_KE_post=E_rigid_post,
                E_modal_post=E_modal_post,
                dE_rigid_loss=self.last_E_loss,
                dE_modal_injected=max(0.0, dE_modal),
                dE_modal_extracted=max(0.0, -dE_modal),
                alpha=alpha_field,
                eta=self.eta,
                beta=beta_used,
                n_active_kicks=n_active_kicks,
                n_active_contacts=len(contacts),
            ))

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

        # NOTE (2026-05): after the distant-velocity γ*_B fix
        # (foundation §16) every kick's realized per-body ΔKE equals
        # E_target exactly, so this cap binds only for genuine multi-body
        # / passivity reasons (sum of per-body E_targets > budget), not
        # to mask a per-body bookkeeping drift.
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

        # NOTE (2026-05): after the distant-velocity γ*_A fix
        # (foundation §16) every kick's realized per-body ΔKE equals
        # E_target exactly (the cross-term m·(v·u)·γ that this cap
        # accounts for is now consumed by γ*_A itself). This cap
        # therefore binds only for genuine multi-body / passivity reasons
        # (sum of per-body E_targets > budget), not to mask a per-body
        # bookkeeping drift.
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
    ) -> int:
        """Apply true point impulses (linear + angular). Version B kick path.

        For each kick on body p with impulse magnitude J along u at lever
        arm r = contact_point - body.position:

            v_lin_p += scale · (J/m_p) · u
            ω_p     += scale · J · I_world_inv_p @ cross(r, u)

        Realized ΔKE = ½ (scale·J)² · k where k = 1/m + (r×u)·I_inv·(r×u),
        which equals scale² · E_target by construction of J in the coupler.

        If `kk.n_rest` and `kk.mu` are populated (coupler set
        friction_cone_clip_enabled=True), apply a closed-form Coulomb
        friction correction at the contact point r AFTER the main kick:
            J_f, t̂ = contact_point_friction_correction(...)
            body.v_lin -= (J_f / m) · t̂
            body.ω     -= J_f · I_inv · (r × t̂)
        This dissipates the tangential contact-point velocity (which
        otherwise leaks past the PGS friction cone — the cone was closed
        pre-kick and cannot oppose the post-kick Δω × r contribution).

        Returns the number of friction corrections that actually fired
        across the kick list (for the coupler's diagnostic counter).
        Energy bookkeeping (`last_dcr_ke_injected`) is measured around
        the full sequence (main kick + correction), so dissipation from
        the correction shows up as a negative addend automatically.
        """
        n_friction_fired = 0
        for kk in kicks:
            body = self.bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0:
                continue
            J = scale * kk.J_mag
            ke_before = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_before += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            I_inv = body.inertia_world_inv()
            body.velocity[0:3] += (J / body.mass) * kk.u
            body.velocity[3:6] += J * (I_inv @ np.cross(kk.r, kk.u))

            # Contact-point Coulomb friction correction (replaces the
            # earlier on-u clip). See distant_velocity.py for the algebra.
            if kk.n_rest is not None and kk.mu is not None and J != 0.0:
                J_f, t_hat = contact_point_friction_correction(
                    J=J, u=kk.u, r=kk.r,
                    n_rest=kk.n_rest, mu=kk.mu,
                    mass=body.mass, I_world_inv=I_inv,
                )
                if J_f > 0.0:
                    n_friction_fired += 1
                    body.velocity[0:3] -= (J_f / body.mass) * t_hat
                    body.velocity[3:6] -= J_f * (
                        I_inv @ np.cross(kk.r, t_hat))

            ke_after = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_after += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            self.last_dcr_ke_injected += ke_after - ke_before
        return n_friction_fired

    def _apply_patch_impulse_dcr_velocities(
        self,
        kicks: "list",
    ) -> None:
        """Apply patch-based impulses (prompt §9). `kicks` is a
        `list[PatchKick]`; the type hint is loose to avoid an import
        cycle with `passive_dcr → distant_velocity → dcr_world`.

        Each kick is a full 3-vector impulse `kk.lam` applied at the
        patch centroid `kk.x_bar` on the receiving body, with lever arm
        `kk.r_bar = x_bar - body.position`. The coupler has already
        performed §9.5 (Coulomb cone projection) and §9.6 (passivity
        scaling), so there is no world-level rescale: just apply
        `lam` and account for it in `last_dcr_ke_injected`.

            v_lin += (1/m) · lam
            ω     += I⁻¹ · (r̄ × lam)
        """
        for kk in kicks:
            body = self.bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0:
                continue
            ke_before = 0.5 * body.mass * float(
                body.velocity[:3] @ body.velocity[:3])
            ke_before += 0.5 * float(
                body.velocity[3:6] @ (body.inertia_world() @ body.velocity[3:6]))
            I_inv = body.inertia_world_inv()
            body.velocity[0:3] += kk.lam / body.mass
            body.velocity[3:6] += I_inv @ np.cross(kk.r_bar, kk.lam)
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
