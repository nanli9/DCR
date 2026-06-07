"""AVBD-backed DCR world.

`AVBDDCRWorld` is a drop-in replacement for `dcr.dcr.DCRWorld` whose
rigid solve is delegated to the vendored AVBD `Solver6DOF`. The patch-
mode response math (`PassiveDCRCoupler`) is unchanged; this class is
the seam between AVBD's per-row constraint pool and the DCR coupler's
expectation of `(contacts, lam_triples)` per step.

Spec mapping:
  - prompts/avbd_native_dcr_followup_spec_v2.md §1   (AVBD-only framing)
  - prompts/avbd_native_dcr_followup_spec_v2.md §9   (patch reformulation)
  - prompts/avbd_native_dcr_followup_spec_v2.md §13  (transpose-consistent
                                                     modal back-reaction —
                                                     unchanged math, inherited
                                                     from passive_dcr.py)
  - prompts/avbd_native_dcr_followup_spec_v2.md §24 M1, M4, M8
                                                    (impulse exposure,
                                                     modal injection from
                                                     AVBD λ, back-reaction)

# DEVIATION (spec §7, §12, §15): Phase A does NOT add the moving-support
# AVBD constraint type, the passivity line search with γ rescale, nor the
# closed-system energy ledger. Those are deferred to a Phase B branch
# (see plan §"Out of scope").
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from dcr.rigid.body import (
    RigidBody, ShapeType, box_shape, plane_shape, quat_identity,
)
from dcr.rigid.collision import Contact
from dcr.rigid.energy import rigid_kinetic_energy
from dcr.dcr.passive_dcr import PassiveDCRCoupler
from dcr.dcr.distant_velocity import PatchKick

from ._solver import (
    Solver6DOF,
    RigidBody as AVBDRigidBody,
    FLOOR_CONTACT_6DOF,
)
from .contact_extract import extract_contacts
from .diagnostics import EnergyLedger
from .moving_support_solve import MovingSupportResult, solve_one_contact
from ..modal.passive_inject import eval_basis_at_point
from ..dcr.deformed_normal_bj import compute_deformed_normal_barbic_james

# Reduced-coordinate AVBD support (v1). The classes are pure-Python /
# numpy and free of GPU state; importing here is cheap.
from .reduced_support import ReducedSupport
from .reduced_support_solve import ReducedSupportCoupler
from .reduced_coupled_avbd import ReducedCoupledAVBDCoupler
from .reduced_dcr_postkick import ReducedSupportDCRPostkickCoupler


# ---------------------------------------------------------------------------
# Body descriptor
# ---------------------------------------------------------------------------

@dataclass
class AVBDBodyDescriptor:
    """Binding between a DCR-side RigidBody and an AVBD-side RigidBody.

    The DCR-side body is what `PassiveDCRCoupler` reads (mass, velocity,
    inertia, etc.). The AVBD-side handle is what `Solver6DOF` operates
    on. Each step we sync state from AVBD → DCR (after solve) and from
    DCR → AVBD (after patch kicks are applied).

    `avbd_body` is None for the synthetic "floor"/"elastic-ground" body
    — that body exists only on the DCR side; AVBD models the elastic
    surface as a Y-up floor plane and never gives it a kinematic body.
    """
    dcr_body: RigidBody
    avbd_body: AVBDRigidBody | None
    name: str = ""


# ---------------------------------------------------------------------------
# AVBDDCRWorld
# ---------------------------------------------------------------------------

@dataclass
class AVBDDCRWorld:
    """Replaces `DCRWorld` while keeping the same public surface.

    Differences from `DCRWorld`:
      * Rigid solve runs in AVBD's primal/dual loop (Solver6DOF).
      * Only `energy_prescribed_patch` is supported on the coupler side
        (see Phase A rip-out in `dcr/dcr/passive_dcr.py`).
      * Gravity is applied INSIDE the AVBD step (Solver6DOF takes a
        `gravity` constructor arg); the world does not re-apply it.
    """

    h: float = 1.0 / 60.0
    eta: float = 0.5
    gravity: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, -9.81, 0.0]))
    device: str = "cpu"
    avbd_iterations: int = 10
    avbd_substeps: int = 1
    enforce_rigid_energy_bound: bool = False

    # ---- Phase B: moving-support AVBD pass (spec §7 + §12) -----------------
    # When True, after the patch coupler returns, run a per-patch
    # moving-support AL solve via dcr.avbd.moving_support_solve. This
    # adds a BUDGET-BOUNDED residual response funded by the modal
    # reservoir, on top of whatever the patch coupler already applied.
    # The causal gates (§14) keep it inactive on first contact, so the
    # standard drop-and-settle dynamics behave like Phase A.
    enable_moving_support_pass: bool = False
    moving_support_beta: float = 0.1
    moving_support_max_attempts: int = 3
    moving_support_use_bj: bool = False
    moving_support_theta_max: float = float(np.radians(3.0))

    # Filled in by the user via add_body / add_passive_coupler.
    _descs: list[AVBDBodyDescriptor] = field(default_factory=list, init=False)
    passive_couplers: list[PassiveDCRCoupler] = field(
        default_factory=list, init=False)
    _solver: Solver6DOF | None = field(default=None, init=False, repr=False)
    _floor_y: float | None = field(default=None, init=False)
    _floor_body_idx: int | None = field(default=None, init=False)
    _prev_contact_keys: set = field(default_factory=set, init=False, repr=False)
    time: float = field(default=0.0, init=False)

    # Per-step diagnostics (mirror DCRWorld fields for run_scenes.py).
    last_E_loss: float = field(default=0.0, init=False)
    last_E_max: float = field(default=0.0, init=False)
    last_dcr_ke_injected: float = field(default=0.0, init=False)
    last_contacts: list[Contact] = field(default_factory=list, init=False, repr=False)
    last_lam: NDArray[np.float64] = field(
        default_factory=lambda: np.zeros(0), init=False, repr=False)
    last_step_ms: float = field(default=0.0, init=False)
    # Per-stage breakdown (ms). Helps profile where step time goes.
    last_solve_ms: float = field(default=0.0, init=False)
    last_extract_ms: float = field(default=0.0, init=False)
    last_coupler_ms: float = field(default=0.0, init=False)
    last_sync_ms: float = field(default=0.0, init=False)
    # Number of dynamic body velocities pushed back into AVBD this step.
    # Zero when no patch kicks fired (DCR didn't modify any velocity).
    last_sync_n: int = field(default=0, init=False)

    # ---- Phase B diagnostics (spec §21 subset) ---------------------------
    # All zero / empty when enable_moving_support_pass is False. When the
    # Phase B pass runs, each scalar is the aggregate over all patches
    # that fired this step.
    last_W_support: float = field(default=0.0, init=False)
    last_E_support_budget: float = field(default=0.0, init=False)
    last_gamma_support_min: float = field(default=1.0, init=False)
    last_n_moving_support: int = field(default=0, init=False)
    last_n_moving_support_gated: int = field(default=0, init=False)
    last_bj_angle_deg_max: float = field(default=0.0, init=False)
    last_bj_fallbacks: int = field(default=0, init=False)
    last_moving_support_ms: float = field(default=0.0, init=False)
    # Cumulative running max of E_modal for §14.3 modal cutoff gate.
    _E_modal_peak_running: float = field(default=0.0, init=False)

    # ---- Reduced-coordinate AVBD support (v1) ---------------------------
    # When attached via `attach_reduced_support`, the Solver6DOF runs in
    # uncaptured mode and the coupler interposes a CPU q-block solve
    # between every AVBD iteration. Off by default — `reduced_support` is
    # None and zero overhead. See
    # `prompts/reduced_coordinate_avbd_support_dcr_extension.md` and the
    # build plan at
    # `~/.claude/plans/you-are-working-inside-prancy-turtle.md`.
    reduced_support: ReducedSupport | None = field(
        default=None, init=False, repr=False)
    reduced_support_coupler: ReducedSupportCoupler | None = field(
        default=None, init=False, repr=False)
    reduced_support_energy_log: list[dict] = field(
        default_factory=list, init=False, repr=False)
    # ---- Coupled reduced AVBD (Python-side monolithic primal) ----------
    # When attached via `attach_reduced_coupled_avbd`, this coupler takes
    # over the per-iteration primal for tracked bodies: it solves the
    # full monolithic Newton block [x; q] including the cross-coupling
    # ρ·J_x·J_q^T inside iteration_hook. Mutually exclusive with the
    # static-support coupler (`reduced_support_coupler`).
    reduced_coupled_coupler: ReducedCoupledAVBDCoupler | None = field(
        default=None, init=False, repr=False)
    reduced_coupled_log: list[dict] = field(
        default_factory=list, init=False, repr=False)
    # ---- Legacy DCR post-step Δv kick (--mode old_dcr_postkick) -------
    # Attached only when the user explicitly asks for the legacy
    # ablation. The coupler reads contact impulses at end-of-step,
    # drives a modal IIR transient on the reduced-support basis, and
    # applies Δv = peak_deflection / h to tracked rigid bodies. This
    # is the architecturally-rejected approach; kept solely for
    # comparison against --mode coupled_iir_modal.
    reduced_dcr_postkick_coupler: ReducedSupportDCRPostkickCoupler | None = field(
        default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._solver = Solver6DOF(
            dt=self.h,
            iterations=self.avbd_iterations,
            substeps=self.avbd_substeps,
            gravity=tuple(float(g) for g in self.gravity),
            device=self.device,
            post_stabilize=True,
        )

    # ---- Body registration -------------------------------------------------

    @property
    def bodies(self) -> list[RigidBody]:
        """DCR-side body list. PassiveDCRCoupler reads this."""
        return [d.dcr_body for d in self._descs]

    def add_floor(
        self,
        floor_y: float,
        friction: float = 0.5,
        name: str = "floor",
    ) -> int:
        """Register a synthetic static floor at `y = floor_y`. Returns its
        DCR-side body index. AVBD does not get its own body for the
        floor — `add_floor_contact_box` later wires rigid bodies to it.
        """
        if self._floor_y is not None:
            raise RuntimeError("AVBDDCRWorld supports a single floor")
        self._floor_y = float(floor_y)
        # The synthetic floor body is treated as static / infinite-mass on
        # the DCR side so coupler bookkeeping degenerates gracefully.
        rb = RigidBody(
            mass=float("inf"),
            inertia_body=np.full(3, float("inf")),
            position=np.array([0.0, floor_y, 0.0]),
            orientation=quat_identity(),
            velocity=np.zeros(6),
            force=np.zeros(6),
            shape=plane_shape(normal=(0.0, 1.0, 0.0)),
            is_static=True,
            friction=friction,
        )
        idx = len(self._descs)
        self._descs.append(AVBDBodyDescriptor(
            dcr_body=rb, avbd_body=None, name=name))
        self._floor_body_idx = idx
        return idx

    def add_box(
        self,
        mass: float,
        half_extents: tuple[float, float, float],
        position: tuple[float, float, float],
        orientation_wxyz: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0),
        velocity_lin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        velocity_ang: tuple[float, float, float] = (0.0, 0.0, 0.0),
        friction: float = 0.5,
        restitution: float = 0.0,
        name: str = "",
        floor_contact: bool = True,
    ) -> int:
        """Add a dynamic rigid box. Wires `add_floor_contact_box` on the
        AVBD side iff a floor has been registered AND `floor_contact`.
        Returns the DCR-side index of the new body.
        """
        if self._solver is None:
            raise RuntimeError("AVBDDCRWorld._solver is not initialized")
        hx, hy, hz = half_extents
        # AVBD quaternion convention is XYZW; we expose WXYZ on the DCR
        # API for consistency with the rest of dcr/.
        w, x, y, z = orientation_wxyz
        avbd_q = (x, y, z, w)
        avbd_body = self._solver.add_box(
            position=position,
            half_extents=half_extents,
            mass=mass,
            orientation=avbd_q,
            velocity=velocity_lin,
            angular_velocity=velocity_ang,
            friction=friction,
        )
        if floor_contact and self._floor_y is not None:
            self._solver.add_floor_contact_box(
                avbd_body, floor_y=self._floor_y, friction=friction)
        # Body-body contact between boxes uses AVBD's self-collision pool.
        # Enable lazily on first box add.
        if not self._solver._self_collide:
            self._solver.enable_self_collision(True, default_friction=friction)

        # DCR-side mirror.
        # Inertia (paper convention for box): I = m/12 * diag(...). AVBD
        # uses m/3 with half-extents (equivalent); we use the canonical
        # DCR formula for the DCR-side body so coupler kinematics agree.
        I_diag = np.array([
            mass / 12.0 * ((2 * hy) ** 2 + (2 * hz) ** 2),
            mass / 12.0 * ((2 * hx) ** 2 + (2 * hz) ** 2),
            mass / 12.0 * ((2 * hx) ** 2 + (2 * hy) ** 2),
        ])
        rb = RigidBody(
            mass=float(mass),
            inertia_body=I_diag,
            position=np.array(position, dtype=np.float64),
            orientation=np.array(orientation_wxyz, dtype=np.float64),
            velocity=np.concatenate([velocity_lin, velocity_ang]).astype(np.float64),
            force=np.zeros(6),
            shape=box_shape(hx, hy, hz),
            is_static=(mass <= 0.0),
            restitution=float(restitution),
            friction=float(friction),
        )
        idx = len(self._descs)
        self._descs.append(AVBDBodyDescriptor(
            dcr_body=rb, avbd_body=avbd_body, name=name))
        return idx

    def attach_reduced_support(
        self,
        rs: ReducedSupport,
        *,
        tracked_body_indices: list[int],
        shelf_length: float,
        shelf_width: float,
        shelf_y_rest: float,
        n_grid_x: int,
        n_grid_z: int,
        static_only: bool = False,
    ) -> ReducedSupportCoupler:
        """Wire a ReducedSupport into the AVBD substep loop (v1).

        `tracked_body_indices` are the AVBD-side body indices whose
        FLOOR_CONTACT rows participate in the q-block (i.e. the bodies
        riding on the shelf). The remaining args describe the synthetic
        shelf basis grid so the coupler can bilinear-interpolate U at
        arbitrary contact points.

        Returns the bound coupler. Idempotent: attaching twice replaces.
        """
        if self._solver is None:
            raise RuntimeError("AVBDDCRWorld._solver is not initialized")
        # Pre-populate body_mass from the descriptor list so the
        # physical F_n cap (in _assemble_r_tilde) can clamp each row's
        # contribution by m·|v|/h + m·g. Mass is constant; safe to
        # cache once. Bodies absent from this dict get v_pre = 0 ⇒
        # F_max = 0 in the cap, which is intentional (means "we don't
        # know the body's mass, fall through without inflation").
        body_mass = {}
        for d in self._descs:
            if d.avbd_body is None:
                continue
            i = int(d.avbd_body.index)
            if i in tracked_body_indices:
                body_mass[i] = float(d.dcr_body.mass)
        coupler = ReducedSupportCoupler(
            rs=rs,
            tracked_body_indices=list(tracked_body_indices),
            shelf_length=float(shelf_length),
            shelf_width=float(shelf_width),
            shelf_y_rest=float(shelf_y_rest),
            n_grid_x=int(n_grid_x),
            n_grid_z=int(n_grid_z),
            h_macro=float(self.h),
            h_substep=float(self.h) / float(self.avbd_substeps),
            body_mass=body_mass,
            static_only=bool(static_only),
        )
        # When in static-only mode the legacy ReducedSupport overlay
        # flag is also forced off so any downstream code that peeks at
        # rs.overlay_enabled (viewer, scene printout, etc.) reflects the
        # real behaviour. This is the one place we touch rs.* from the
        # world layer.
        if static_only:
            rs.overlay_enabled = False
            rs.restart_overlay_each_step = False
        self.reduced_support = rs
        self.reduced_support_coupler = coupler
        # Wire solver hooks. These force the solver out of CUDA-graph
        # capture mode (see solver_6dof._step_one), so existing tests
        # that never call this method are unaffected.
        self._solver.substep_begin_hook = coupler.substep_begin_hook
        self._solver.iteration_hook = coupler.iteration_hook
        self._solver.substep_end_hook = coupler.substep_end_hook
        return coupler

    def attach_reduced_coupled_avbd(
        self,
        rs: ReducedSupport,
        *,
        tracked_body_indices: list[int],
        shelf_length: float,
        shelf_width: float,
        shelf_y_rest: float,
        n_grid_x: int,
        n_grid_z: int,
        rho_clip: float = 1.0e9,
    ) -> ReducedCoupledAVBDCoupler:
        """Wire a `ReducedCoupledAVBDCoupler` into the AVBD substep loop.

        This installs the Python-side monolithic primal coupler — every
        AVBD iteration's primal+dual is followed by a hook that solves
        the full [Δx_i; Δq] Newton block (Schur-eliminated) including the
        cross-coupling ρ·J_x·J_q^T, then writes both Δx_i and Δq back to
        solver state. This is the strongest coupling tier; it is mutually
        exclusive with `attach_reduced_support` (the BCD path).
        """
        if self._solver is None:
            raise RuntimeError("AVBDDCRWorld._solver is not initialized")
        if self.reduced_support_coupler is not None:
            raise RuntimeError(
                "Cannot attach reduced_coupled_avbd: "
                "reduced_support_coupler is already attached. The two "
                "modes are mutually exclusive.")
        if self.reduced_coupled_coupler is not None:
            raise RuntimeError("reduced_coupled_coupler already attached")
        body_mass = {}
        for d in self._descs:
            if d.avbd_body is None:
                continue
            i = int(d.avbd_body.index)
            if i in tracked_body_indices:
                body_mass[i] = float(d.dcr_body.mass)
        coupler = ReducedCoupledAVBDCoupler(
            rs=rs,
            tracked_body_indices=list(tracked_body_indices),
            shelf_length=float(shelf_length),
            shelf_width=float(shelf_width),
            shelf_y_rest=float(shelf_y_rest),
            n_grid_x=int(n_grid_x),
            n_grid_z=int(n_grid_z),
            h_macro=float(self.h),
            h_substep=float(self.h) / float(self.avbd_substeps),
            body_mass=body_mass,
            rho_clip=float(rho_clip),
        )
        # Force overlay-related flags off — this coupler never reads them
        # but downstream code (viewers, scene printouts) does.
        rs.overlay_enabled = False
        rs.restart_overlay_each_step = False
        self.reduced_support = rs
        self.reduced_coupled_coupler = coupler
        self._solver.substep_begin_hook = coupler.substep_begin_hook
        self._solver.iteration_hook = coupler.iteration_hook
        self._solver.substep_end_hook = coupler.substep_end_hook
        return coupler

    def attach_reduced_dcr_postkick(
        self,
        rs: ReducedSupport,
        *,
        tracked_body_indices: list[int],
        shelf_length: float,
        shelf_width: float,
        shelf_y_rest: float,
        n_grid_x: int,
        n_grid_z: int,
        n_substeps: int = 32,
    ) -> ReducedSupportDCRPostkickCoupler:
        """Attach the legacy DCR post-step Δv kick coupler.

        Used only by `--mode old_dcr_postkick` for ablation against
        `--mode coupled_iir_modal`. The post-kick is computed in
        `apply()`, called from `step()` after the AVBD solver finishes.

        Mutually exclusive with `attach_reduced_coupled_avbd` and
        `attach_reduced_support` (this is the rigid-floor + post-Δv
        path; the support is purely diagnostic).
        """
        if self.reduced_coupled_coupler is not None:
            raise RuntimeError(
                "Cannot attach reduced_dcr_postkick: "
                "reduced_coupled_coupler is already attached.")
        if self.reduced_support_coupler is not None:
            raise RuntimeError(
                "Cannot attach reduced_dcr_postkick: "
                "reduced_support_coupler is already attached.")
        if self.reduced_dcr_postkick_coupler is not None:
            raise RuntimeError("reduced_dcr_postkick already attached")
        body_mass: dict[int, float] = {}
        for d in self._descs:
            if d.avbd_body is None:
                continue
            i = int(d.avbd_body.index)
            if i in tracked_body_indices:
                body_mass[i] = float(d.dcr_body.mass)
        coupler = ReducedSupportDCRPostkickCoupler(
            rs=rs,
            tracked_body_indices=list(tracked_body_indices),
            shelf_length=float(shelf_length),
            shelf_width=float(shelf_width),
            shelf_y_rest=float(shelf_y_rest),
            n_grid_x=int(n_grid_x),
            n_grid_z=int(n_grid_z),
            h_macro=float(self.h),
            n_substeps=int(n_substeps),
            body_mass=body_mass,
        )
        rs.overlay_enabled = False
        self.reduced_support = rs
        self.reduced_dcr_postkick_coupler = coupler
        return coupler

    def add_passive_coupler(self, coupler: PassiveDCRCoupler) -> None:
        if coupler.dcr_velocity_mode != "energy_prescribed_patch":
            raise ValueError(
                "AVBDDCRWorld only supports dcr_velocity_mode="
                "'energy_prescribed_patch' in Phase A; got "
                f"{coupler.dcr_velocity_mode!r}")
        self.passive_couplers.append(coupler)

    # ---- Snapshot / restore (powers the viewer "reset" button) ----------

    def snapshot(self) -> dict:
        """Capture the current dynamic state of the world and every
        attached coupler. Returned dict can be passed to `restore()` at
        any later step to rewind. Static-floor descriptors are not
        snapshotted (they don't change).
        """
        # Make sure the parallel DCR list reflects the live AVBD state
        # before we copy out of it.
        try:
            self._sync_avbd_to_dcr()
        except Exception:
            pass
        bodies_snap = []
        for desc in self._descs:
            db = desc.dcr_body
            bodies_snap.append({
                "position": db.position.copy(),
                "orientation": db.orientation.copy(),
                "velocity": db.velocity.copy(),
            })
        couplers_snap = []
        for coupler in self.passive_couplers:
            couplers_snap.append({
                "q": coupler._stepper.q.copy(),
                "qdot": coupler._stepper.qdot.copy(),
                "last_E_modal_peak": float(coupler.last_E_modal_peak),
            })
        return {
            "time": float(self.time),
            "bodies": bodies_snap,
            "couplers": couplers_snap,
        }

    def restore(self, snap: dict) -> None:
        """Restore a snapshot. Resets time, per-step diagnostics, contact
        keys, and rewires both the DCR-side bodies AND the AVBD-side
        Warp arrays in one batched upload per state array.
        """
        import numpy as _np
        # 1. Restore DCR-side body state from the snapshot.
        for desc, b in zip(self._descs, snap["bodies"]):
            desc.dcr_body.position[:] = b["position"]
            desc.dcr_body.orientation[:] = b["orientation"]
            desc.dcr_body.velocity[:] = b["velocity"]
        # 2. Restore the coupler state (modal q, qdot, peak energy).
        for coupler, cs in zip(self.passive_couplers, snap["couplers"]):
            coupler._stepper.q[:] = cs["q"]
            coupler._stepper.qdot[:] = cs["qdot"]
            coupler.last_E_modal_peak = cs["last_E_modal_peak"]
            # Reset cumulative diagnostics so a fresh run looks fresh.
            coupler.last_alpha = 0.0
            coupler.last_E_modal_pre_kick = 0.0
            coupler.last_E_modal_post_kick = 0.0
            coupler.last_E_modal_attenuation_diss = 0.0
            coupler.last_patches = None
            coupler.last_patch_kicks = None
        # 3. Push every body's state back into the Warp arrays in one
        # batched upload per array (no per-body reallocation).
        sol = self._solver
        if sol.x is not None:
            x_np = sol.x.numpy().copy()
            q_np = sol.q.numpy().copy()
            v_np = sol.v.numpy().copy()
            w_np = sol.omega.numpy().copy()
            for desc in self._descs:
                if desc.avbd_body is None:
                    continue
                i = desc.avbd_body.index
                db = desc.dcr_body
                x_np[i] = (float(db.position[0]),
                           float(db.position[1]),
                           float(db.position[2]))
                # DCR WXYZ → AVBD XYZW.
                q_np[i] = (float(db.orientation[1]),
                           float(db.orientation[2]),
                           float(db.orientation[3]),
                           float(db.orientation[0]))
                v_np[i] = (float(db.velocity[0]),
                           float(db.velocity[1]),
                           float(db.velocity[2]))
                w_np[i] = (float(db.velocity[3]),
                           float(db.velocity[4]),
                           float(db.velocity[5]))
            sol.x.assign(x_np)
            sol.q.assign(q_np)
            sol.v.assign(v_np)
            sol.omega.assign(w_np)
            # prev_v / prev_omega feed the BDF1 inertial target; zero them
            # so the first post-reset step doesn't get a phantom v_inertia
            # carried over from the pre-reset trajectory.
            if sol.prev_v is not None:
                sol.prev_v.zero_()
            if sol.prev_omega is not None:
                sol.prev_omega.zero_()
            # Clear any cached CUDA-graph: the captured launches reference
            # array allocations that may have shifted on the next _flush.
            sol._graph = None
        # 4. World-level state.
        self.time = float(snap["time"])
        self._prev_contact_keys = set()
        self.last_contacts = []
        self.last_lam = _np.zeros(0)
        self.last_E_loss = 0.0
        self.last_E_max = 0.0
        self.last_dcr_ke_injected = 0.0
        self.last_step_ms = 0.0
        self.last_solve_ms = 0.0
        self.last_extract_ms = 0.0
        self.last_coupler_ms = 0.0
        self.last_sync_ms = 0.0
        self.last_sync_n = 0

    # ---- Step -------------------------------------------------------------

    def step(self) -> list[Contact]:
        """One rigid step. Flow:

            1. Snapshot pre-solve rigid KE.
            2. AVBD step (gravity inside).
            3. Sync AVBD → DCR body state.
            4. Extract contacts + lam triples.
            5. Compute E_loss, E_max.
            6. For each passive coupler: process_step → patch kicks.
            7. Apply patch kicks (Newton-3rd modal back-reaction is done
               inside coupler.process_step at the moment of the kick;
               here we just apply the impulse to the rigid body and
               push the corrected velocity back into AVBD).
            8. Bookkeeping + return contacts.
        """
        import time as _t
        t0 = _t.perf_counter()

        # (1) snapshot rigid KE + pre-solve linear velocities. The latter
        #     feeds the measured-Δp impulse source:
        #         dp = m·(v_post − v_pre) − h·m·g   (realtime-coupling-fix §2.3).
        E_rigid_pre = rigid_kinetic_energy([d.dcr_body for d in self._descs])
        v_pre_lin = [
            np.asarray(d.dcr_body.velocity[0:3], dtype=np.float64).copy()
            for d in self._descs
        ]

        # Stage pre-step y-velocities for the reduced-support coupler's
        # physical F_n cap BEFORE the solver runs — the iteration_hook
        # fires inside solver.step() and reads `_body_v_pre_y` when it
        # assembles the q-block's contact forcing.
        if self.reduced_support_coupler is not None:
            body_v_pre_y: dict[int, float] = {}
            for di, desc in enumerate(self._descs):
                if desc.avbd_body is None:
                    continue
                body_v_pre_y[int(desc.avbd_body.index)] = float(v_pre_lin[di][1])
            self.reduced_support_coupler.prepare_step(body_v_pre_y)

        # (2) AVBD solve.
        t_solve_0 = _t.perf_counter()
        self._solver.step()
        self.last_solve_ms = (_t.perf_counter() - t_solve_0) * 1000.0

        # (3) sync state AVBD → DCR (single batched readback per array).
        self._sync_avbd_to_dcr()

        # (4) extract contacts.
        t_extract_0 = _t.perf_counter()
        contacts, lam, k_normal, records, current_keys = extract_contacts(
            self._solver,
            floor_body_idx=self._floor_body_idx,
            prev_contact_keys=self._prev_contact_keys,
            dt=self.h,
            avbd_to_dcr=self._avbd_to_dcr_index_map(),
        )
        self.last_extract_ms = (_t.perf_counter() - t_extract_0) * 1000.0
        self._prev_contact_keys = current_keys
        self.last_contacts = contacts
        self.last_lam = lam
        self.last_k_normal = k_normal

        # (5) energy bookkeeping.
        E_rigid_post = rigid_kinetic_energy([d.dcr_body for d in self._descs])
        self.last_E_loss = max(0.0, E_rigid_pre - E_rigid_post)
        self.last_E_max = self.eta * self.last_E_loss
        self.last_dcr_ke_injected = 0.0

        # Measured per-body contact impulse Δp = m·(v_post−v_pre) − h·m·g
        # (realtime-coupling-fix §2.3). The gravity impulse over the full
        # rigid step is m·g·h regardless of substeps. This is the
        # iteration-insensitive impulse source; static / infinite-mass bodies
        # get no entry (the coupler falls back to λ for those).
        g = np.asarray(self.gravity, dtype=np.float64)
        body_dp: dict[int, NDArray[np.float64]] = {}
        for i, d in enumerate(self._descs):
            b = d.dcr_body
            if b.is_static or b.mass <= 0.0 or not np.isfinite(b.mass):
                continue
            v_post = np.asarray(b.velocity[0:3], dtype=np.float64)
            body_dp[i] = b.mass * (v_post - v_pre_lin[i]) - self.h * b.mass * g
        self.last_body_dp = body_dp

        # (6/7) coupler dispatch + apply patch impulses.
        t_coupler_0 = _t.perf_counter()
        bodies = [d.dcr_body for d in self._descs]
        kicked_any = False
        for coupler in self.passive_couplers:
            coupler.process_step(
                contacts, lam, self.h, self.last_E_max, bodies=bodies,
                k_normal=k_normal, body_dp=body_dp)
            patch_kicks = getattr(coupler, "last_patch_kicks", None)
            if patch_kicks:
                self._apply_patch_kicks(patch_kicks, bodies)
                kicked_any = True
        self.last_coupler_ms = (_t.perf_counter() - t_coupler_0) * 1000.0

        # (Phase B) Optional moving-support AVBD pass (spec §7 + §12).
        # Runs AFTER the patch coupler so the causal gates can see the
        # post-coupler state. Always a no-op when the flag is False.
        t_ms_0 = _t.perf_counter()
        ms_kicked_any = False
        if self.enable_moving_support_pass and self.passive_couplers:
            ms_kicked_any = self._run_moving_support_pass(bodies)
        self.last_moving_support_ms = (_t.perf_counter() - t_ms_0) * 1000.0

        # Sync DCR → AVBD only if a patch kick actually modified velocities.
        # Without this gate, even on steps where the coupler is a no-op we
        # were paying ~24 full-array CPU↔Warp roundtrips (every step).
        t_sync_0 = _t.perf_counter()
        if kicked_any or ms_kicked_any:
            self._sync_dcr_to_avbd_velocities_batched()
        else:
            self.last_sync_n = 0
        self.last_sync_ms = (_t.perf_counter() - t_sync_0) * 1000.0

        # Reduced-support post-step: assemble r_tilde, run two-rate
        # overlay (§9), inject Δv at probe rigid bodies, log energies.
        # No-op when not attached. Sourced from the AVBD-converged
        # augmented contact response, so the no-event-gate property of
        # the coupled solve is preserved (§9.2 / §11.2).
        if self.reduced_support_coupler is not None:
            # Item (3): pass the macro-step rigid KE loss as the source
            # budget for the overlay's energy cap. `last_E_loss` is
            # max(0, KE_pre − KE_post) — a slight underestimate of the
            # contact-dissipated energy when gravity is positive-working
            # (conservative in the safe direction: less injection budget).
            #
            # Pre-step y-velocities were already staged via prepare_step
            # before the solver ran (the iteration_hook needed them).
            # post_step re-passes the cached dict so the r_tilde
            # assembly uses the same values as the q-block did.
            self.reduced_support_coupler.post_step(
                self._solver,
                rigid_kinetic_energy_fn=rigid_kinetic_energy,
                descs=self._descs,
                E_src_step=float(self.last_E_loss),
                body_v_pre_y=self.reduced_support_coupler._body_v_pre_y,
            )
            # Mirror selected diagnostics into the world log so callers
            # can poll without reaching into the coupler.
            c = self.reduced_support_coupler
            self.reduced_support_energy_log.append({
                "t": float(self.time),
                "E_rigid_pre_overlay": float(c.last_E_rigid_pre_overlay),
                "E_rigid_post_overlay": float(c.last_E_rigid_post_overlay),
                "E_overlay_injected": float(c.last_E_overlay_injected),
                "E_q": float(c.last_E_q),
                "E_total": float(c.last_E_total),
                "q_max_disp": float(c.last_q_max_disp),
                "probe_d_max": c.last_probe_d_max.copy(),
                "probe_dv": c.last_probe_dv.copy(),
                "probe_dv_candidate": c.last_probe_dv_candidate.copy(),
                "n_tracked_rows": int(c.last_n_tracked_rows),
                "n_iter_solves": int(c.last_n_iter_solves),
                # Items (3)+(4) bookkeeping.
                "alpha_cap": float(c.last_alpha_cap),
                "E_src": float(c.last_E_src),
                "E_inj_candidate": float(c.last_E_inj_candidate),
                "E_inj_realised": float(c.last_E_inj_realised),
                "n_cooldown_active": int(c.last_n_cooldown_active),
                # Static-sag mode instrumentation.
                "static_only": bool(c.static_only),
                "q_norm": float(c.last_q_norm),
                "max_support_deflection": float(c.last_max_support_deflection),
                "overlay_events_fired": int(c.last_overlay_events_fired),
                "cum_overlay_events_fired": int(c.cum_overlay_events_fired),
            })

        # Legacy DCR post-step Δv kick (--mode old_dcr_postkick).
        # Mutually exclusive with reduced_coupled_coupler; invoked after
        # AVBD finishes the macro step, before time advances. Modifies
        # tracked-body velocities directly.
        if self.reduced_dcr_postkick_coupler is not None:
            self.reduced_dcr_postkick_coupler.apply(self)

        # Reduced-coupled-AVBD: mirror its instrumentation into a step log
        # (parallel to the reduced_support_energy_log).
        if self.reduced_coupled_coupler is not None:
            cc = self.reduced_coupled_coupler
            self.reduced_coupled_log.append({
                "t": float(self.time),
                "q_norm": float(cc.last_q_norm),
                "max_support_deflection": float(cc.last_max_support_deflection),
                "contact_residual": float(cc.last_contact_residual),
                "Schur_cond": float(cc.last_Schur_condition_estimate),
                "n_iter_solves": int(cc.last_n_iter_solves),
                "max_dx_norm": float(cc.last_max_dx_norm),
                "max_dtheta_norm": float(cc.last_max_dtheta_norm),
                "last_dq_norm": float(cc.last_dq_norm),
                "n_tracked_rows": int(cc.last_n_tracked_rows),
                "rho_clip_hits": int(cc.last_rho_clip_hits),
                "overlay_events_fired": int(cc.last_overlay_events_fired),
                "cum_overlay_events_fired": int(cc.cum_overlay_events_fired),
                "iter_dq_history": list(cc.last_iter_dq_norms),
            })

        self.time += self.h
        self.last_step_ms = (_t.perf_counter() - t0) * 1000.0
        return contacts

    # ---- internals --------------------------------------------------------

    def _sync_avbd_to_dcr(self) -> None:
        """Copy positions / orientations / velocities from Solver6DOF
        readbacks into the parallel DCR-side body list.

        Four `.numpy()` calls (one per state array) — each is a single
        device→host transfer that's then sliced cheaply in numpy. Per-
        body indexing happens on the host-side ndarrays, no further
        GPU traffic. Quaternion convention swap: AVBD = XYZW, DCR = WXYZ.
        """
        positions = self._solver.positions()        # (n_b, 3)
        orientations = self._solver.orientations()  # (n_b, 4) xyzw
        velocities = self._solver.velocities()      # (n_b, 3)
        omegas = self._solver.angular_velocities()  # (n_b, 3)
        for desc in self._descs:
            if desc.avbd_body is None:
                continue
            i = desc.avbd_body.index
            desc.dcr_body.position[:] = positions[i]
            # XYZW → WXYZ.
            desc.dcr_body.orientation[0] = orientations[i, 3]
            desc.dcr_body.orientation[1] = orientations[i, 0]
            desc.dcr_body.orientation[2] = orientations[i, 1]
            desc.dcr_body.orientation[3] = orientations[i, 2]
            desc.dcr_body.velocity[0:3] = velocities[i]
            desc.dcr_body.velocity[3:6] = omegas[i]

    def _sync_dcr_to_avbd_velocities_batched(self) -> None:
        """After patch kicks modify DCR-side velocities, push them back
        into AVBD in a SINGLE batched read/write per array.

        The naive `Solver6DOF.set_velocity(body, v)` does
        `wp.array(self.v.numpy().copy()...)` per call — for N bodies,
        that's 2N full-array CPU↔Warp roundtrips per step. Here we do
        one download + one in-place upload per array, even with N=12
        dynamic bodies as in the truck scene.

        Uses `wp.array.assign(numpy_arr)` for in-place upload (does NOT
        reallocate the warp buffer, so kernel array refs stay valid).
        """
        sol = self._solver
        # Snapshot once.
        v_np = sol.v.numpy().copy()
        w_np = sol.omega.numpy().copy()
        n = 0
        for desc in self._descs:
            if desc.avbd_body is None or desc.dcr_body.is_static:
                continue
            i = desc.avbd_body.index
            dv = desc.dcr_body.velocity
            v_np[i] = (float(dv[0]), float(dv[1]), float(dv[2]))
            w_np[i] = (float(dv[3]), float(dv[4]), float(dv[5]))
            n += 1
        sol.v.assign(v_np)
        sol.omega.assign(w_np)
        self.last_sync_n = n

    def _avbd_to_dcr_index_map(self) -> dict[int, int]:
        """Mapping AVBD body index → DCR body index.

        AVBD assigns body indices in the order `solver.add_box(...)` is
        called; DCR-side indices are positions in `self._descs`, which
        includes a static floor entry that AVBD doesn't see. Cached on
        first call (the mapping is fixed at world construction time
        after all add_* calls have finished — we don't currently support
        dynamic body add/remove, so the cache is safe).
        """
        cached = getattr(self, "_avbd_to_dcr_cache", None)
        if cached is not None:
            return cached
        mp: dict[int, int] = {}
        for dcr_idx, desc in enumerate(self._descs):
            if desc.avbd_body is None:
                continue
            mp[int(desc.avbd_body.index)] = dcr_idx
        self._avbd_to_dcr_cache = mp
        return mp

    def _run_moving_support_pass(
        self,
        bodies: list[RigidBody],
    ) -> bool:
        """Phase B (spec §7 + §12 + §13): per-patch moving-support AVBD pass.

        For each PassiveDCRCoupler's `last_patches` (built earlier in this
        step by the patch coupler), runs `solve_one_contact` against the
        modal support and applies the resulting impulse + back-reaction.

        The receiver body for each patch is the non-elastic body. The
        elastic body itself is static-floor-like — no kick is applied to
        it (the support's reaction is the modal back-reaction qdot ← qdot
        − Φᵀ J, which we apply directly to the coupler's stepper).

        Returns True iff any patch applied a non-zero impulse to a rigid
        body (the caller needs this to decide whether to re-sync DCR →
        AVBD velocities).

        Bookkeeping cumulated on `self.last_*` for the viewer:
          last_W_support, last_E_support_budget, last_gamma_support_min,
          last_n_moving_support (= active), last_n_moving_support_gated,
          last_bj_angle_deg_max, last_bj_fallbacks.
        """
        # Reset per-step accumulators.
        self.last_W_support = 0.0
        self.last_E_support_budget = 0.0
        self.last_gamma_support_min = 1.0
        self.last_n_moving_support = 0
        self.last_n_moving_support_gated = 0
        self.last_bj_angle_deg_max = 0.0
        self.last_bj_fallbacks = 0
        any_impulse = False

        contacts = self.last_contacts
        for coupler in self.passive_couplers:
            patches = getattr(coupler, "last_patches", None)
            if not patches:
                continue
            modal = coupler.modal
            U_surf = modal.U_surf
            surf = coupler._surface
            surf_vert_idx = modal.surface_vertex_indices
            vert_to_surf = coupler._vert_to_surf_idx
            omega2 = modal.frequencies ** 2

            # §14.3 modal peak (running max).
            from ..modal.energy import modal_energy as _me
            E_modal_now = float(_me(
                coupler._stepper.q, coupler._stepper.qdot,
                modal.frequencies))
            self._E_modal_peak_running = max(
                self._E_modal_peak_running, E_modal_now)

            # Spec §22 Inv 3 fast-path: empty modal reservoir ⇒ no support
            # contribution. Skip BEFORE we pay for Φ(x̄) and BJ-normal
            # computation on every patch — those dominate the per-step
            # cost on a busy scene (truck has ~7 patches × ~50µs each).
            if E_modal_now <= 1e-18:
                continue

            for patch in patches:
                # Receiver = the body in the pair that is NOT the elastic.
                if patch.body_a == coupler.elastic_body_idx:
                    receiver_idx = patch.body_b
                    r_bar = patch.r_bar_b
                    # n_rest_bar points A→B (i.e., elastic→receiver), which
                    # is the "push direction FROM elastic INTO receiver."
                    n_rest = np.asarray(patch.n_rest_bar, dtype=np.float64)
                elif patch.body_b == coupler.elastic_body_idx:
                    receiver_idx = patch.body_a
                    r_bar = patch.r_bar_a
                    # n_rest_bar points A→B (receiver→elastic); the push
                    # direction FROM elastic INTO receiver is its negation.
                    n_rest = -np.asarray(patch.n_rest_bar, dtype=np.float64)
                else:
                    # Patch doesn't touch the elastic body — skip.
                    continue

                body = bodies[receiver_idx]
                if body.is_static or not np.isfinite(body.mass):
                    continue

                # Φ(x̄) at the patch centroid (shared cache via cKDTree).
                Phi = eval_basis_at_point(
                    patch.x_bar, surf, U_surf,
                    surf_vert_idx, vert_to_surf)

                # Frozen contact-frame normal (BJ if enabled, else rest).
                n_frame = n_rest
                if self.moving_support_use_bj and coupler._bj_cache is not None:
                    try:
                        n_bj, theta, _ = compute_deformed_normal_barbic_james(
                            patch.x_bar, n_rest, coupler._stepper.q,
                            surf, coupler._bj_cache,
                            self.moving_support_theta_max,
                        )
                        bad = (not np.all(np.isfinite(n_bj))
                               or abs(float(np.linalg.norm(n_bj)) - 1.0) > 1e-6)
                        if bad:
                            self.last_bj_fallbacks += 1
                        else:
                            n_frame = n_bj
                            self.last_bj_angle_deg_max = max(
                                self.last_bj_angle_deg_max,
                                float(np.degrees(theta)))
                    except Exception:
                        self.last_bj_fallbacks += 1

                # Approximate gap from current geometry (patch lives on
                # the contact shell, so gap ≈ 0 if the patch is active).
                gap = 0.0

                res: MovingSupportResult = solve_one_contact(
                    body, r_bar, Phi, n_frame,
                    coupler._stepper.qdot.copy(),
                    coupler._stepper.q.copy(),
                    omega2,
                    beta=self.moving_support_beta,
                    mu=float(body.friction),
                    gap=gap,
                    max_attempts=self.moving_support_max_attempts,
                    causal_gating=bool(coupler.causal_gating),
                    contact_shell_delta=float(coupler.contact_shell_delta),
                    v_min_closing=float(coupler.v_min_closing),
                    e_modal_cutoff_frac=float(coupler.e_modal_cutoff_frac),
                    E_modal_peak=self._E_modal_peak_running,
                    restitution=float(getattr(body, "restitution", 0.0)),
                )

                if res.gated_out:
                    self.last_n_moving_support_gated += 1
                    continue
                if float(np.linalg.norm(res.J)) < 1e-12:
                    continue

                # Apply impulse to the receiver body AND back-react the
                # modal stepper (same Φ instance — Invariant 5).
                body.velocity[0:3] = res.v_after
                body.velocity[3:6] = res.omega_after
                coupler._stepper.qdot[:] = res.qdot_after

                # Aggregate diagnostics for the viewer.
                self.last_W_support += float(res.W_support_to_rigid)
                self.last_E_support_budget += float(res.E_support_budget)
                self.last_gamma_support_min = min(
                    self.last_gamma_support_min, float(res.gamma_final))
                self.last_n_moving_support += 1
                any_impulse = True

        return any_impulse

    def _apply_patch_kicks(
        self,
        kicks: list[PatchKick],
        bodies: list[RigidBody],
    ) -> None:
        """Apply patch-impulse kicks to the receiver bodies.

        Mirrors `DCRWorld._apply_patch_impulse_dcr_velocities` (dcr_world.py
        lines 539-572) — the math is identical; the coupler has already
        done §9.5 cone + §9.6 passivity scaling + the transpose-consistent
        modal back-reaction on `coupler._stepper.qdot`. We only translate
        the rigid impulse into rigid velocity here.

            v_lin += (1/m) · λ
            ω     += I_world^{-1} · (r̄ × λ)
        """
        for kk in kicks:
            body = bodies[kk.body_idx]
            if body.is_static or body.mass <= 0.0 or np.isinf(body.mass):
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

    # ---- Convenience: DCRWorld parity --------------------------------------

    def add_body(self, *_args, **_kwargs):  # pragma: no cover
        raise NotImplementedError(
            "AVBDDCRWorld does not accept generic RigidBody handles. Use "
            "add_box(...) or add_floor(...) instead so the AVBD side has "
            "the right constraint rows attached.")
