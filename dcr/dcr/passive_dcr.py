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
    prescribed_alpha,
)
from ..modal.energy import modal_energy
from ..rigid.body import RigidBody
from ..rigid.collision import Contact
from ..rigid.solver import _pick_friction_dirs
from .contact_patch import (
    ContactPatch,
    build_patch,
    cluster_contacts_by_body_pair,
    cone_project_impulse,
    patch_effective_mass_matrix,
    patch_passive_scaling,
    solve_patch_impulse,
)
from .contact_projection import (
    project_du_contact_compatible,
    project_patch_impulse_contact_compatible,  # kept for ablation only
    should_project_patch,
)
from .deformed_normal import SurfaceTangentFrames, compute_deformed_normal
from .deformed_normal_bj import (
    BarbicJamesCache,
    build_barbic_james_cache,
    compute_deformed_normal_barbic_james,
)
from .distant_velocity import (
    LinearKick,
    PatchKick,
    PointImpulseKick,
    friction_cone_clip,
    gamma_from_energy_linear,
    impulse_from_energy_point,
)
from .impact_bank import ImpactBank, ImpactKey
from .geodesic import heat_geodesic_cached


_EPS_TINY = 1e-12


# ImpactKey is now defined in impact_bank.py (the coherent-bank module is the
# more fundamental owner of the per-impact identity) and imported above. The
# impact-window reservoir reuses the same (rigid partner, support) key.


@dataclass
class ImpactReservoirEntry:
    """Short-lived passive energy budget for one ImpactKey (reservoir-fix §2).
    Funded by η·E_loss, spent by modal injection, expired after W steps."""
    energy: float = 0.0
    age: int = 0       # steps since last deposit; expire when age > W


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
            "energy_prescribed_patch"          - Patch-based reformulation
                                                 (prompt §9, foundation §7).
                                                 Step 1 lands here: clusters
                                                 contacts by body pair and
                                                 builds a `ContactPatch` per
                                                 cluster (centroid, averaged
                                                 rest normal, clamped lever
                                                 arms). Emits no kicks yet;
                                                 observable through
                                                 `last_patches`. §9.2-9.6
                                                 (deformed normal at x̄,
                                                 K⁻¹ Δv_des, friction, passivity)
                                                 are upcoming plans.
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
    #
    # AVBD branch (Phase A): the only supported mode is
    # "energy_prescribed_patch". The legacy modes "coevoet",
    # "energy_prescribed", and "energy_prescribed_point_impulse" are
    # walled off by the validation in __post_init__ below — their code
    # paths (and the `last_linear_kicks` / `last_point_impulse_kicks`
    # fields they populate) are unreachable but retained for git
    # history. See `prompts/avbd_native_dcr_followup_spec_v2.md` §1.
    dcr_velocity_mode: str = "energy_prescribed_patch"
    energy_response_beta: float = 0.25
    energy_budget_source: str = "min_rigid_loss_modal"
    theta_max_deformed: float = float(np.radians(3.0))
    deformed_normal_method: str = "patch_fit"
    # See class docstring for the rationale on these two.
    friction_cone_clip_enabled: bool = False
    kinematic_cap: str = "none"

    # ----- Contact-causal passive coupling gates (opt-in) ---------------
    # See `prompts/passive_contact_causal_modal_coupling.md` for full
    # motivation. When `causal_gating == True`, the patch dispatch in
    # `_compute_distant_response_patch` short-circuits any patch where
    # (a) the slab is not within `contact_shell_delta` of the receiver,
    # (b) the slab is not moving INTO the receiver at >= `v_min_closing`
    #     along the rest-normal axis (same axis the cone closes on, §9.5),
    # or (c) the modal reservoir has dropped below
    #     `e_modal_cutoff_frac · last_E_modal_peak` (numerical cutoff).
    # All other patch-mode machinery (K_total solve, cone projection,
    # modal back-reaction, §15 invariant) is unchanged. With the flag
    # OFF (default), behaviour is bit-identical to the un-gated patch
    # mode that has been in regression for 263 tests.
    #
    # The proposal's `η ∈ [0.05, 0.2]` per-step transfer fraction is the
    # same dimensionless quantity as `energy_response_beta` above —
    # documentation choice, not code. Recommended range when gating is
    # on: `energy_response_beta ∈ [0.05, 0.2]`.
    causal_gating: bool = False
    contact_shell_delta: float = 1e-4         # m;   proposal §1
    v_min_closing: float = 0.044              # m/s; proposal §2, √(2·g·δ_slop) with δ_slop=1e-4
    e_modal_cutoff_frac: float = 1e-5         # frac; proposal §3

    # ----- New-contact modal-injection impulse source --------------------
    # Which contact impulse drives the E1 modal injection s = Φ(x)ᵀ J
    # (realtime-coupling-fix §2).
    #   "lambda_only": J = λ_N·n + λ_T·t            — DEFAULT (proven path).
    #   "augmented"  : J += h·k_N·max(0,pen)·n       — §2.2 effective impulse.
    #   "delta_p"    : J = −(rigid partner's measured contact Δp), split per
    #                  contact by |λ_N| — §2.3 measured momentum change.
    #
    # NOTE (decided by scripts/_diag_injection_iter_sensitivity.py): the
    # effective sources do NOT reduce iteration-sensitivity here. The stored λ
    # IS under-grown at low AVBD iters (max|λ_n| ≈ 0.16 @iters=4 vs 4.2 @iters=8),
    # but the injection is energy-capped by passive_alpha at E_max = η·E_loss
    # (α ≈ 0.3 < 1, always binding), so the kick MAGNITUDE never limits the
    # injected energy — the cap does. All three sources give identical capped
    # injection (CV ≈ 0.688). The real iteration-sensitivity is the is_new ×
    # E_max timing coincidence (total E_loss is ~constant across iters; the
    # fraction landing on an injecting step collapses at low iters). So the
    # default stays lambda_only (zero behaviour change); augmented/delta_p are
    # kept as opt-in ablations / the §16 record.
    impulse_source: str = "lambda_only"

    # ----- New-contact injection scaling (energy-prescribed option) ------
    # How the aggregated modal kick s = Σ Φ(x)ᵀ J is scaled before q̇ += α·s.
    #   "passive"    : α = passive_alpha (α ∈ [0,1], scale DOWN to fit budget) —
    #                  DEFAULT, the foundation-§15 bound. Starves at low AVBD
    #                  iters because ‖s‖ is tiny and α clamps at 1 (docs §9-§11).
    #   "prescribed" : α = prescribed_alpha — scale s UP or DOWN to DEPOSIT
    #                  μ·(available budget) of modal energy (foundation §15
    #                  inequality used as a TARGET, not a ceiling). The kick
    #                  DIRECTION still comes from Φ(x)ᵀ J (correct spectral
    #                  distribution); only the MAGNITUDE is set from the energy
    #                  budget, so it is iteration-insensitive. Pair with the
    #                  impact reservoir (timing) for the full low-iter fix.
    #                  DEVIATION: synthesizes modal energy the literal impulse
    #                  did not carry; still globally passive because the realized
    #                  ΔE is debited from the η·E_loss budget (docs §12).
    injection_scaling: str = "passive"
    prescribed_mu: float = 1.0           # fraction of available budget to deposit
    prescribed_alpha_max: float = 100.0  # guard vs amplifying a noisy direction

    # ----- Impact-window energy reservoir (avbd_dcr_impact_reservoir_fix) ----
    # The real fix for the low-iteration starvation (docs §9): decouple the
    # E1 injection's DEPOSIT timing (every E_loss step) from its SPEND timing
    # (any near-contact step within W frames), instead of the brittle
    # same-frame `is_new × E_max` gate. Deposits η·E_loss into per-(rigid,
    # support) reservoirs; the injection spends the accumulated budget when a
    # contact is still geometrically near. Global passivity is preserved:
    # Σ E_inj ≤ η·Σ E_loss (deposits bounded by η·E_loss, spend bounded by the
    # reservoir, passive_alpha cap retained). Default OFF → bit-identical to
    # the is_new path; flip on after the §12 diagnostic passes.
    use_impact_reservoir: bool = False
    reservoir_window_steps: int = 4       # W: expire entries with age > W
    reservoir_decay: float = 0.65         # rho_B: stored-budget decay per step
    reservoir_gate_delta: float = 1e-4    # delta_gate (m); gap=-penetration ≤ this
    reservoir_eps: float = 1e-10          # min energy to be eligible
    reservoir_max_factor: float = 1.0     # B_max = factor · recent_peak(E_max)

    # ----- Impact gate on the reservoir deposit (docs §13) ------------------
    # Without this, the reservoir deposits η·E_loss EVERY step, including the
    # tiny steady E_loss a resting contact leaks when its block-coordinate
    # (Gauss-Seidel) solve has not fully converged at low AVBD iterations.
    # With energy-PRESCRIBED scaling that resting trickle gets pumped back into
    # the foundation modes directly under the resting body and the patch kicks
    # it → the body never visually settles (the "boulder keeps vibrating on the
    # ledge" artifact; see docs §13 diagnosis). The gate funds the reservoir
    # ONLY from genuine impacts: a contact's deposit is admitted iff the partner
    # body's measured contact impulse exceeds its weight-support impulse by
    # `impact_gate_dp_factor` —
    #     ‖Δp_partner‖  >  impact_gate_dp_factor · h · m · g
    # A body merely resting has ‖Δp‖ ≈ h·m·g (ratio ≈ 1, gated out); a body
    # decelerating an impact has ratio ≫ 1 (admitted). This uses the same
    # iteration-insensitive measured-Δp signal as impulse_source="delta_p", so
    # genuine impacts still deposit at all iteration counts (the §12 prescribed
    # fix is preserved) while the resting self-loop is starved. Deposit can only
    # SHRINK, so global passivity Σ E_inj ≤ η·Σ E_loss is unaffected. Requires
    # body_dp (delta_p source); with body_dp None the gate is inert (deposits
    # as before). Default OFF → bit-identical to the un-gated path.
    use_impact_gate: bool = False
    impact_gate_dp_factor: float = 2.0    # ‖Δp‖ / (h·m·g) threshold (>1 = impact)
    gravity_magnitude: float = 9.81       # |g| for the weight-support impulse

    # ----- Coherent impact impulse bank (coherent_impact_impulse_bank_fix) ---
    # The reservoir fixed the low-iteration TIMING starvation but not the
    # MAGNITUDE: a soft solve smears one impact over many small per-frame
    # impulses, and per-frame injection keeps only Σ½‖s_i‖², discarding the
    # cross terms ½‖Σs_i‖² would recover (spec §3). The bank accumulates the
    # impulses of one physical impact over a short causal window and injects the
    # event-level ½‖Σs_i‖² once, capped by a passive budget funded by η·E_loss.
    #
    # The bank SUBSUMES the reservoir: when use_coherent_impulse_bank is True the
    # standalone reservoir deposit/spend is suppressed, so η·E_loss is deposited
    # exactly ONCE and global passivity Σ E_inj ≤ η·Σ E_loss is preserved (the
    # spec §15 config that turns both on would otherwise double-count). Default
    # OFF → bit-identical to the is_new / reservoir paths. See dcr/dcr/impact_bank.py.
    use_coherent_impulse_bank: bool = False
    impact_bank_mode: str = "impulse_reconstruct"   # | "modal_sum" (ablation)
    impact_bank_inject_policy: str = "end_of_window"  # | "every_frame"
    impact_bank_window: int = 4              # samples gathered before firing
    impact_bank_max_event_age: int = 8       # delete an event after this many steps
    impact_bank_decay: float = 0.65          # lambda_B: budget decay per step
    impact_bank_coherence_cos_min: float = 0.5    # §8.1 directional gate
    impact_bank_normal_cos_min: float = 0.7       # §8.2 normal gate
    impact_bank_patch_radius: float = 0.05        # §8.3 m; ‖x_i − x̄‖ ceiling
    impact_bank_tangential_dominance_max: float = 2.0  # §8.5b ‖J_t‖/(|J_n|+ε)
    impact_bank_max_factor: float = 1.0      # B_max = factor · recent_peak(E_max)

    # ----- Opt-in γ-decay stabilizer (foundation §16, #DEVIATION from §15) ---
    # End-of-rigid-step modal-state attenuation factor in [0, 1]. See
    # HomogeneousStepper.apply_rigid_step_decay() for semantics:
    #   gamma = 1.0   persistent state, main contribution (default)
    #   gamma ∈ (0,1) explicit dissipation, scene stabilizer (e.g. 0.95, 0.9)
    #   gamma = 0.0   original-DCR-style per-step reset as limiting case
    # Energy removed by the operator is LOGGED as dissipation
    # (last_E_modal_attenuation_diss) and never refunded to the reservoir.
    modal_decay_gamma: float = 1.0

    # Geodesic-distance attenuation (paper §4.5 / Eq. 14, dropped into the
    # patch-mode dispatch). When ON, the support's modal velocity reaching
    # each receiver patch is multiplied by
    #     α(d) = min(1, geodesic_C · (max(d, r0) / r0)^{-geodesic_beta})
    # where d is the heat-method geodesic distance from the most recent
    # impact's surface vertex to the receiver patch's surface vertex.
    # α ∈ [0, 1] strictly, so it cascades safely through K⁻¹/cone/§9.6/
    # dissipativity guard — passivity is preserved.
    #
    # Defaults match the paper's "shells" tuning (C=1, β=0.5); for thicker
    # volumes use β=1.0. r0=0 → auto-set to mean surface edge length in
    # __post_init__. Default OFF — bit-identical to today when not enabled.
    use_geodesic_attenuation: bool = False
    geodesic_C: float = 1.0
    geodesic_beta: float = 0.5
    geodesic_r0: float = 0.0   # 0 → auto from mean surface edge length

    # ----- Contact-compatible null-space projection ---------------------
    # See `prompts/dcr_patch_kick_nullspace_projection_fix.md` and
    # `dcr/dcr/contact_projection.py`. The §9 patch kick applies the
    # modal velocity as a single point impulse at the patch centroid;
    # for a thin body in flat resting contact the lever arm × tangential
    # impulse becomes torque the body cannot resist (visible as fork
    # roll/pitch on the dinner_table scene). The projection zeroes the
    # differential normal velocity across patch sample points before
    # the §9.6 passivity cascade runs, removing the contact-incompatible
    # component of the kick while preserving DCR energy transfer and
    # the foundation §15 passivity bound.
    # # DEVIATION (DCR paper §9): replaces the single-centroid kick with
    # # a null-space-projected version — see fix doc §6-9. Reduces to a
    # # no-op on thick / tall / non-resting bodies via the gate (§11).
    projection_enabled: bool = True
    projection_use_tangent_rows: bool = False
    projection_tangent_weight: float = 0.25
    projection_thin_ratio: float = 0.25
    projection_v_n_thresh: float = 0.05   # m/s
    projection_v_t_thresh: float = 0.10   # m/s
    projection_eps: float = 1e-7

    # ----- COM-shadow modal sampling (one Φ per body, kick at COM) -------
    # When True, replace the per-patch loop in `_compute_distant_response_patch`
    # with a per-body loop:
    #   * Φ ← eval_basis_at_point(body.position, …)   — one KD lookup / body
    #     instead of one / patch. The KD-tree's closest-triangle search
    #     finds the slab vertex closest to the body's COM, which IS the
    #     COM-shadow on the support for body-on-floor scenes.
    #   * v_p = body.v_lin   (no lever arm because the kick is at the COM)
    #   * λ = K_total⁻¹·(v_f − v_p) with K_body = (1/m)·I (the cross terms
    #     vanish at r̄ = 0).
    #   * Body: Δv_lin = λ/m, Δω = 0 — by construction the lever-arm
    #     Δω = I⁻¹·(r̄ × λ) the projection was built to clean up does not
    #     exist here. The projection becomes a no-op.
    # # DEVIATION (DCR paper §9, foundation §15): the paper samples Φ at the
    # # patch centroid. This mode collapses to one Φ per body. Valid when
    # # body extent ≪ modal wavelength (≈ all dinner_table bodies). The
    # # passivity scaling and modal back-reaction still use the same K_total
    # # and Φᵀ·λ machinery — only the sample location and application point
    # # change.
    com_shadow_mode: bool = False
    # Diagnostics (reset each call to _compute_distant_response_patch).
    last_com_shadow_kicks_fired: int = 0
    last_com_shadow_kd_lookups: int = 0

    # Internals.
    _stepper: HomogeneousStepper = field(init=False, repr=False)
    _surface: TriMesh = field(init=False, repr=False)
    _vert_to_surf_idx: NDArray[np.int32] = field(init=False, repr=False)
    # Geodesic state. _geodesic_cache: source-vertex-keyed distance fields,
    # lazily populated by heat_geodesic_cached. _last_impact_vert is the
    # source the next patch dispatch will read from; updated each step to
    # the largest admitted impact's closest surface vertex (and held across
    # quiet steps so the propagating vibration keeps its attribution).
    _geodesic_cache: dict = field(default_factory=dict, init=False, repr=False)
    _last_impact_vert: int | None = field(default=None, init=False, repr=False)
    # Viewer-facing — None until the first impact lands.
    last_geodesic_source_xyz: NDArray[np.float64] | None = None
    # Per-global-vertex attenuation α in [0, 1]; off-surface vertices = 0.
    # Recomputed when a new impact updates _last_impact_vert.
    last_attenuation_field: NDArray[np.float64] | None = None
    # Raw heat-method geodesic distance from the latest impact's source vertex
    # to every surface vertex (off-surface entries = +inf). Used by the viewer
    # to animate a traveling pulse along d (paper-style ripple visualization);
    # NOT consumed by the injection cascade itself (which uses α from above).
    last_geodesic_distance_field: NDArray[np.float64] | None = None
    # Lazy: created on first Version-B step.
    _tangent_frames: SurfaceTangentFrames | None = field(
        default=None, init=False, repr=False)
    # Populated in __post_init__ when deformed_normal_method == "barbic_james".
    _bj_cache: BarbicJamesCache | None = field(
        default=None, init=False, repr=False)

    # Energy diagnostics per step.
    last_E_modal_pre_kick: float = 0.0
    last_E_modal_post_kick: float = 0.0
    # Modal energy injected by THIS step's kick (post − pre) and its running
    # cumulative sum (realtime-coupling-fix §16 diagnostic). The cumulative
    # value is the iteration-sensitivity signal: ~flat across AVBD iters for a
    # good impulse source, rising with iters for the lagging λ-only source.
    last_E_modal_injected: float = 0.0
    cum_E_modal_injected: float = 0.0
    # Raw (pre-cap) kick magnitude and the uncapped injection it would deliver
    # at α=1. Used to test whether the impulse SOURCE is iteration-sensitive
    # separately from the passive_alpha cap (realtime-coupling-fix §16).
    last_s_total_norm: float = 0.0
    last_dE_full_uncapped: float = 0.0
    last_alpha: float = 0.0
    # Smallest passivity scale applied to a patch back-reaction this step
    # (foundation §15 extraction dual). 1.0 = every kick was already
    # dissipative; < 1.0 means the runaway-guard clamped at least one kick;
    # 0.0 = a kick was rejected (could not be funded without adding energy).
    last_backreaction_gamma_min: float = 1.0
    last_q_history_transient: NDArray[np.float64] | None = None
    # Modal energy removed by end-of-step γ-decay (foundation §16). Always
    # >= 0, exactly zero when modal_decay_gamma == 1.0. Logged as
    # dissipation; NEVER refunded to the §15 reservoir.
    last_E_modal_attenuation_diss: float = 0.0

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
    # How often prescribed-injection scaling hit its alpha_max guard this step
    # (a noisy/near-zero direction being amplified). Nonzero ⇒ raise
    # prescribed_alpha_max or tighten impulse_threshold.
    last_prescribed_alpha_cap_fired: int = 0

    # ----- Patch-based reformulation diagnostics (prompt §9) -------------
    # Populated when `dcr_velocity_mode == "energy_prescribed_patch"`.
    #   * last_patches    : the geometric patches built for this step
    #     (centroid, averaged rest normal, clamped lever arms).
    #   * last_patch_kicks: the resulting per-patch impulses after
    #     §9.4 K⁻¹ Δv_des, §9.5 Coulomb projection, §9.6 passivity.
    # Both are None on steps where no patch response fires (no new impulse
    # → no E_target → kicks skipped).
    last_patches: list[ContactPatch] | None = None
    last_patch_kicks: list[PatchKick] | None = None
    # Per-patch projection retention ratio rho = √(½·λ_projᵀKλ_proj / ½·λᵀKλ).
    # Populated only on patches that pass the §11 gate; empty list when the
    # projection is disabled or no patches qualified this step.
    last_projection_rho: list[float] = field(default_factory=list)
    last_projection_fired: int = 0
    last_projection_skipped: int = 0
    # Modal kinetic energy removed by the projection this step (joules).
    # Equal to Σ ½·(λ²·K)_raw − ½·(λ²·K)_proj over fired patches; ≥ 0 by
    # K-metric non-increase.
    last_E_projection_removed: float = 0.0

    # ----- Contact-causal gating diagnostics (proposal §1-§3) -----------
    # Per-step gate-fire counters (reset in process_step). Cumulative
    # running max of E_modal_post_kick is used by the numerical cutoff.
    last_E_modal_peak: float = 0.0
    last_patch_gated_no_contact: int = 0
    last_patch_gated_low_closing: int = 0
    last_patch_gated_numerical: int = 0

    # ----- Impact-window reservoir state + diagnostics -------------------
    impact_reservoirs: dict = field(default_factory=dict, init=False, repr=False)
    _recent_peak_E_max: float = field(default=0.0, init=False, repr=False)
    last_E_reservoir_deposit: float = 0.0
    last_E_reservoir_spent: float = 0.0
    last_E_reservoir_expired: float = 0.0
    last_E_reservoir_total: float = 0.0   # Σ energy across live entries
    last_n_eligible_reservoirs: int = 0
    cum_E_reservoir_deposit: float = 0.0
    cum_E_reservoir_spent: float = 0.0
    cum_E_reservoir_expired: float = 0.0

    # ----- Coherent impact bank state + diagnostics ----------------------
    # The ImpactBank instance (built in __post_init__ when the flag is on).
    # Cumulative deposit/spend/expired live on the bank; per-step values are
    # mirrored here to match the reservoir diagnostics pattern.
    _bank: ImpactBank | None = field(default=None, init=False, repr=False)
    last_E_bank_deposit: float = 0.0
    last_E_bank_spent: float = 0.0
    last_E_bank_expired: float = 0.0
    last_n_bank_events: int = 0
    last_R_coherence: float = 0.0   # mean ‖Σs_i‖²/Σ‖s_i‖² over fired windows

    def __post_init__(self) -> None:
        # AVBD Phase A: enforce single-mode operation. The legacy modes
        # remain in code as unreachable branches (kept for git history /
        # offline analysis); only "energy_prescribed_patch" is exercised.
        # See prompts/avbd_native_dcr_followup_spec_v2.md §1.
        if self.dcr_velocity_mode != "energy_prescribed_patch":
            raise ValueError(
                "AVBD branch supports only "
                "dcr_velocity_mode='energy_prescribed_patch'; "
                f"got {self.dcr_velocity_mode!r}. "
                "Legacy modes (coevoet, energy_prescribed, "
                "energy_prescribed_point_impulse) are walled off in this "
                "branch."
            )
        if not 0.0 <= self.modal_decay_gamma <= 1.0:
            raise ValueError(
                "modal_decay_gamma must be in [0, 1]; got "
                f"{self.modal_decay_gamma}")
        if self.impulse_source not in ("lambda_only", "augmented", "delta_p"):
            raise ValueError(
                "impulse_source must be one of "
                "{'lambda_only', 'augmented', 'delta_p'}; got "
                f"{self.impulse_source!r}")
        if self.injection_scaling not in ("passive", "prescribed"):
            raise ValueError(
                "injection_scaling must be 'passive' or 'prescribed'; got "
                f"{self.injection_scaling!r}")
        if not 0.0 <= self.prescribed_mu <= 1.0:
            raise ValueError(
                f"prescribed_mu must be in [0, 1]; got {self.prescribed_mu}")
        if self.prescribed_alpha_max <= 0.0:
            raise ValueError(
                "prescribed_alpha_max must be > 0; got "
                f"{self.prescribed_alpha_max}")
        self._stepper = HomogeneousStepper.from_modal_analysis(
            self.modal, gamma=self.modal_decay_gamma)
        # Snapshot of qdot just after this step's kick (before step_n
        # decays it). The patch mode's v_f driver reads this; other modes
        # ignore it. Initialized to zero for the first-step case where
        # no kick has fired yet.
        self._qdot_just_after_kick = np.zeros_like(self._stepper.qdot)
        self._surface = self.modal.fem.mesh.extract_surface()
        max_vert = self.modal.fem.mesh.num_vertices
        self._vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
        for si, vi in enumerate(self.modal.surface_vertex_indices):
            self._vert_to_surf_idx[vi] = si

        # Geodesic attenuation: auto-set r0 = mean surface edge length
        # (paper §4.5 — element size). Done unconditionally so toggling
        # use_geodesic_attenuation at runtime works without reinit.
        if self.geodesic_r0 <= 0.0:
            V = self._surface.vertices
            F = self._surface.faces
            if F.shape[0] > 0:
                edges = np.concatenate([
                    V[F[:, 1]] - V[F[:, 0]],
                    V[F[:, 2]] - V[F[:, 1]],
                    V[F[:, 0]] - V[F[:, 2]],
                ])
                self.geodesic_r0 = float(
                    np.mean(np.linalg.norm(edges, axis=1)))
            else:
                self.geodesic_r0 = 1e-3  # fallback, should never hit

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

        # Contact-causal gate knob validation (proposal §1-§3).
        if self.contact_shell_delta < 0.0:
            raise ValueError(
                "contact_shell_delta must be >= 0; got "
                f"{self.contact_shell_delta}")
        if self.v_min_closing < 0.0:
            raise ValueError(
                f"v_min_closing must be >= 0; got {self.v_min_closing}")
        if not 0.0 <= self.e_modal_cutoff_frac <= 1.0:
            raise ValueError(
                "e_modal_cutoff_frac must be in [0, 1]; got "
                f"{self.e_modal_cutoff_frac}")
        if self.reservoir_window_steps < 0:
            raise ValueError(
                "reservoir_window_steps must be >= 0; got "
                f"{self.reservoir_window_steps}")
        if not 0.0 <= self.reservoir_decay <= 1.0:
            raise ValueError(
                f"reservoir_decay must be in [0, 1]; got {self.reservoir_decay}")
        if self.impact_gate_dp_factor < 1.0:
            raise ValueError(
                "impact_gate_dp_factor must be >= 1 (1 = pure weight support); "
                f"got {self.impact_gate_dp_factor}")
        if self.gravity_magnitude <= 0.0:
            raise ValueError(
                f"gravity_magnitude must be > 0; got {self.gravity_magnitude}")

        # Coherent impact bank (coherent_impact_impulse_bank_fix). The bank
        # SUBSUMES the reservoir: if both flags are on, the bank wins and the
        # standalone reservoir is suppressed so η·E_loss is deposited exactly
        # once (the spec §15 config turns both on, which would double-count the
        # passivity budget). The ImpactBank validates its own config fields.
        if self.use_coherent_impulse_bank and self.use_impact_reservoir:
            self.use_impact_reservoir = False
        self._bank = ImpactBank(
            n_modes=len(self.modal.frequencies),
            mode=self.impact_bank_mode,
            inject_policy=self.impact_bank_inject_policy,
            window=self.impact_bank_window,
            max_event_age=self.impact_bank_max_event_age,
            decay=self.impact_bank_decay,
            coherence_cos_min=self.impact_bank_coherence_cos_min,
            normal_cos_min=self.impact_bank_normal_cos_min,
            patch_radius=self.impact_bank_patch_radius,
            tangential_dominance_max=self.impact_bank_tangential_dominance_max,
            b_max_factor=self.impact_bank_max_factor,
            eps=self.reservoir_eps,
        )

    # ------------------------------------------------------------------
    # Impact-window energy reservoir (avbd_dcr_impact_reservoir_fix §2-§7)
    # ------------------------------------------------------------------

    def _reservoir_key(self, contact: Contact) -> ImpactKey | None:
        """The (rigid partner, support) key for an elastic-body contact, or
        None if the contact does not touch the modal support."""
        e = self.elastic_body_idx
        if contact.body_a == e:
            partner = contact.body_b
        elif contact.body_b == e:
            partner = contact.body_a
        else:
            return None
        if partner == e:
            return None
        return ImpactKey(body_id=partner, support_id=e)

    def _reservoir_age_expire(self) -> None:
        """§7/§10.1: age every entry, apply ρ_B decay, expire entries past the
        window W. Runs at the top of each step (= end-of-prev-step expiry)."""
        self.last_E_reservoir_expired = 0.0
        W = int(self.reservoir_window_steps)
        dead: list[ImpactKey] = []
        for key, ent in self.impact_reservoirs.items():
            ent.age += 1
            ent.energy *= self.reservoir_decay   # ρ_B decay each step
            if ent.age > W:
                self.last_E_reservoir_expired += max(0.0, ent.energy)
                dead.append(key)
        for key in dead:
            del self.impact_reservoirs[key]
        self.cum_E_reservoir_expired += self.last_E_reservoir_expired

    def _is_impacting(
        self,
        body_id: int,
        bodies: list[RigidBody] | None,
        body_dp: dict[int, NDArray[np.float64]] | None,
        h: float,
    ) -> bool:
        """Impact gate (docs §13): True iff `body_id`'s measured contact impulse
        exceeds its weight-support impulse by `impact_gate_dp_factor`:
            ‖Δp‖ > impact_gate_dp_factor · h · m · g.
        A resting body has ‖Δp‖ ≈ h·m·g (Δp = m·(v_post−v_pre) − h·m·g with
        v_post≈v_pre≈0; see world.step §2.3) → ratio ≈ 1 → not impacting.
        Inert (admits) when the gate is off or Δp/bodies are unavailable."""
        if not self.use_impact_gate:
            return True
        if body_dp is None or bodies is None:
            return True
        dp = body_dp.get(body_id)
        if dp is None:
            return True       # static / infinite-mass partner: leave admitted
        m = float(bodies[body_id].mass)
        if not np.isfinite(m) or m <= 0.0:
            return True
        weight_impulse = h * m * self.gravity_magnitude
        if weight_impulse <= 0.0:
            return True
        return float(np.linalg.norm(dp)) > self.impact_gate_dp_factor * weight_impulse

    def _reservoir_deposit(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        E_max: float,
        bodies: list[RigidBody] | None = None,
        body_dp: dict[int, NDArray[np.float64]] | None = None,
        h: float = 0.0,
    ) -> None:
        """§4: deposit D^n = E_max (= η·E_loss) across current elastic-body
        contact keys, weighted by Σ|λ_N| over each key (fallback weight).
        ρ_B decay was already applied in _reservoir_age_expire, so here we add
        D on top: energy ← min(B_max, energy + D).

        Impact gate (docs §13): when `use_impact_gate`, a key is admitted only
        if its partner body is genuinely impacting (`_is_impacting`); resting
        contacts deposit nothing, so the reservoir under a parked body drains
        and the patch stops re-exciting it. Deposit can only shrink → passivity
        Σ E_inj ≤ η·Σ E_loss is unaffected."""
        self.last_E_reservoir_deposit = 0.0
        self.last_n_impact_gated_keys = 0
        if E_max <= 0.0 or not contacts:
            return
        # Decaying running peak of the per-step budget → B_max ceiling (§4).
        self._recent_peak_E_max = max(
            E_max, self.reservoir_decay * self._recent_peak_E_max)
        B_max = self.reservoir_max_factor * self._recent_peak_E_max
        # Σ|λ_N| per key (fallback impact weight, §4). Keys whose partner body
        # is not impacting are dropped by the gate (docs §13).
        key_w: dict[ImpactKey, float] = {}
        for ci, c in enumerate(contacts):
            key = self._reservoir_key(c)
            if key is None:
                continue
            if not self._is_impacting(key.body_id, bodies, body_dp, h):
                self.last_n_impact_gated_keys += 1
                continue
            lamN = abs(float(lam[3 * ci])) if 3 * ci < len(lam) else 0.0
            key_w[key] = key_w.get(key, 0.0) + lamN
        if not key_w:
            return
        wsum = sum(key_w.values())
        n = len(key_w)
        for key, w in key_w.items():
            frac = (w / wsum) if wsum > self.reservoir_eps else (1.0 / n)
            D = frac * E_max
            ent = self.impact_reservoirs.get(key)
            if ent is None:
                ent = ImpactReservoirEntry()
                self.impact_reservoirs[key] = ent
            ent.energy = min(B_max, ent.energy + D)
            ent.age = 0
            self.last_E_reservoir_deposit += D
        self.cum_E_reservoir_deposit += self.last_E_reservoir_deposit

    def _reservoir_eligible(
        self, contacts: list[Contact],
    ) -> tuple[list[tuple[Contact, int]], set]:
        """§5: elastic-body contacts whose key has energy, is within the
        window, and is still geometrically near (gap = -penetration ≤
        δ_gate). NO is_new requirement. Returns (eligible_data, eligible_keys).
        """
        W = int(self.reservoir_window_steps)
        eligible_data: list[tuple[Contact, int]] = []
        eligible_keys: set = set()
        for ci, c in enumerate(contacts):
            key = self._reservoir_key(c)
            if key is None:
                continue
            ent = self.impact_reservoirs.get(key)
            if ent is None or ent.energy <= self.reservoir_eps or ent.age > W:
                continue
            gap = -float(c.penetration)   # ≤0 overlapping, >0 separated
            if gap > self.reservoir_gate_delta:
                continue
            eligible_data.append((c, ci))
            eligible_keys.add(key)
        return eligible_data, eligible_keys

    def _reservoir_debit(self, eligible_keys: set, E_inj: float) -> None:
        """§7: drain the actual injected energy from eligible reservoirs,
        split by stored-energy share (fallback weight)."""
        self.last_E_reservoir_spent = 0.0
        if E_inj <= 0.0 or not eligible_keys:
            return
        total = sum(
            max(0.0, self.impact_reservoirs[k].energy)
            for k in eligible_keys if k in self.impact_reservoirs)
        if total <= self.reservoir_eps:
            return
        for k in eligible_keys:
            ent = self.impact_reservoirs.get(k)
            if ent is None:
                continue
            S = E_inj * (max(0.0, ent.energy) / total)
            ent.energy = max(0.0, ent.energy - S)
            self.last_E_reservoir_spent += S
        self.cum_E_reservoir_spent += self.last_E_reservoir_spent

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
    # Geodesic-distance attenuation (paper §4.5 / Eq. 14)
    # ------------------------------------------------------------------

    def _closest_surface_vertex(
        self, world_point: NDArray[np.float64]
    ) -> int:
        """Return the GLOBAL index of the surface vertex nearest `world_point`.

        Searches only the modal surface (so off-surface vertices in the
        full tet mesh are never returned — they have no defined geodesic).
        """
        surf_global = self.modal.surface_vertex_indices
        verts = self._surface.vertices[surf_global]
        d2 = np.sum((verts - world_point) ** 2, axis=1)
        return int(surf_global[int(np.argmin(d2))])

    def _geodesic_alpha(self, geodesic_dist: float) -> float:
        """Paper Eq. 14 with passivity clamp.

        α(d) = clip(C · (max(d, r0) / r0)^{-β}, 0, 1)
        """
        r0 = max(self.geodesic_r0, _EPS_TINY)
        r = max(float(geodesic_dist), r0)
        alpha = self.geodesic_C * (r / r0) ** (-self.geodesic_beta)
        if not np.isfinite(alpha) or alpha < 0.0:
            return 0.0
        return min(1.0, alpha)

    def _refresh_attenuation_field(self) -> None:
        """Rebuild `last_attenuation_field` from `_last_impact_vert`.

        Output is sized to the FULL FEM mesh's vertex count (so the viewer
        can index by global vertex id from `mesh.vertices`). Off-surface
        vertices get α = 0; the source vertex itself gets α = 1 (after the
        r0 clamp).
        """
        n_v = int(self.modal.fem.mesh.num_vertices)
        if self._last_impact_vert is None:
            self.last_attenuation_field = None
            self.last_geodesic_distance_field = None
            return
        geo = heat_geodesic_cached(
            self._surface, self._geodesic_cache,
            int(self._last_impact_vert))
        field = np.zeros(n_v, dtype=np.float64)
        dist_field = np.full(n_v, np.inf, dtype=np.float64)
        surf_global = self.modal.surface_vertex_indices
        for vi in surf_global:
            d = geo[vi]
            if not np.isfinite(d):
                continue
            field[vi] = self._geodesic_alpha(d)
            dist_field[vi] = float(d)
        self.last_attenuation_field = field
        self.last_geodesic_distance_field = dist_field

    def _update_impact_source(
        self,
        contact_point: NDArray[np.float64],
        impulse_norm: float,
        running_best: dict,
    ) -> None:
        """Track the largest impulse this step for the geodesic source.

        `running_best` is a step-scoped dict {"norm": float, "vert": int,
        "xyz": np.ndarray} that the injection loop seeds with `norm=-inf`;
        only the impact with the largest `‖j‖` wins. Called from the
        injection loop; final commit (cache update + field rebuild)
        happens after the loop in `_commit_impact_source`.
        """
        if not self.use_geodesic_attenuation:
            return
        if impulse_norm <= running_best.get("norm", -np.inf):
            return
        running_best["norm"] = float(impulse_norm)
        running_best["vert"] = self._closest_surface_vertex(contact_point)
        running_best["xyz"] = np.asarray(contact_point, dtype=np.float64).copy()

    def _commit_impact_source(self, running_best: dict) -> None:
        """Commit the step's winning impact source + refresh the field.

        No-op if no impact was admitted this step (the dominant impact
        from a prior step is retained so the propagating modal vibration
        keeps its attribution).
        """
        if not self.use_geodesic_attenuation:
            return
        if "vert" not in running_best:
            return
        self._last_impact_vert = int(running_best["vert"])
        self.last_geodesic_source_xyz = running_best["xyz"]
        self._refresh_attenuation_field()

    # ------------------------------------------------------------------
    # Contact-impulse source dispatch (realtime-coupling-fix §2)
    # ------------------------------------------------------------------

    def _impulse_for_contact(
        self,
        contact: Contact,
        ci: int,
        lam: NDArray[np.float64],
        h: float,
        k_normal: NDArray[np.float64] | None,
        body_dp: dict[int, NDArray[np.float64]] | None,
        partner_lamN_sum: dict[int, float],
    ) -> NDArray[np.float64] | None:
        """World-frame contact impulse j that drives the modal injection
        s = Φ(x)ᵀ j, dispatched on `impulse_source` (realtime-coupling-fix §2).
        Returns None if the contact has no λ rows. Shared by the is_new /
        reservoir per-frame path and the coherent impact bank, so all three
        sources compose with both injection structures.
        """
        if 3 * ci + 2 >= len(lam):
            return None
        lambda_N = lam[3 * ci]
        lambda_T1 = lam[3 * ci + 1]
        lambda_T2 = lam[3 * ci + 2]
        t1, t2 = _pick_friction_dirs(contact.normal)
        # Baseline λ-only impulse (foundation §4 / realtime §2.1).
        j_world = contact.normal * lambda_N + t1 * lambda_T1 + t2 * lambda_T2

        if (self.impulse_source == "augmented"
                and k_normal is not None and ci < len(k_normal)):
            # §2.2 effective augmented impulse — add the penalty term the lagging
            # AL dual under-represents at low AVBD iters. h-scaled to match the λ
            # triple's impulse units (the extractor multiplies λ by h).
            # DEVIATION (realtime-coupling-fix §2.2): raw penetration as C_N⁺; the
            # post-solve λ already folded in the final k·C, so this can
            # double-count — the §16 diagnostic validates it against delta_p.
            c_plus = max(0.0, float(contact.penetration))
            j_world = j_world + (
                h * float(k_normal[ci]) * c_plus) * contact.normal
        elif self.impulse_source == "delta_p" and body_dp is not None:
            # §2.3 measured contact momentum change: impulse INTO the elastic
            # body = −(net contact Δp of the rigid partner), split across the
            # partner's contacts by |λ_N| weight (iteration-insensitive). Falls
            # back to λ-only for a static partner or when no λ exists.
            partner = (contact.body_a
                       if contact.body_b == self.elastic_body_idx
                       else contact.body_b)
            dp = body_dp.get(partner)
            denom = partner_lamN_sum.get(partner, 0.0)
            if dp is not None and denom > 1e-30:
                w = abs(float(lambda_N)) / denom
                j_world = -w * np.asarray(dp, dtype=np.float64)
        return j_world

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
        *,
        k_normal: NDArray[np.float64] | None = None,
        body_dp: dict[int, NDArray[np.float64]] | None = None,
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
            k_normal: Per-contact normal-row penalty stiffness k_N, parallel
                to `contacts`. Used by impulse_source == "augmented"
                (realtime-coupling-fix §2.2). None falls back to λ-only.
            body_dp: Map body index → measured contact impulse Δp this step.
                Used by impulse_source == "delta_p" (§2.3). None falls back
                to λ-only.

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
        self.last_prescribed_alpha_cap_fired = 0
        self.last_patches = None
        self.last_patch_kicks = None
        # Contact-causal gate counters (proposal §1-§3).
        self.last_patch_gated_no_contact = 0
        self.last_patch_gated_low_closing = 0
        self.last_patch_gated_numerical = 0
        # Impact-gate diagnostic (docs §13): reservoir keys dropped this step
        # because their partner body was resting (not impacting).
        self.last_n_impact_gated_keys = 0
        # γ-decay dissipation accumulator (foundation §16). Reset each step.
        self.last_E_modal_attenuation_diss = 0.0

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

        # --- Coherent impact impulse bank (subsumes the reservoir) ----------
        # When on, the bank owns the new-contact injection: it banks per-frame
        # impulses over a short window and injects ½‖Σs_i‖² (coherent-bank-fix
        # §2/§3), then runs the same patch distant-response tail. Bit-identical
        # to below when off.
        if self.use_coherent_impulse_bank:
            return self._process_step_coherent_bank(
                contacts, lam, h, E_max, bodies, resting_contacts, omega,
                k_normal, body_dp)

        # --- Injection set + budget: impact-window reservoir or is_new ------
        # The reservoir (avbd_dcr_impact_reservoir_fix §2) replaces ONLY the
        # is_new gate + the η·E_loss cap of the E1 injection. `resting_contacts`
        # and the patch channel below are untouched. Deposit η·E_loss (= the
        # passed E_max) every step, then spend the accumulated per-key budget
        # whenever a contact is still near — decoupling deposit from spend
        # timing (the docs §9 root cause). With the flag OFF this is
        # bit-identical to the is_new path.
        eligible_keys: set = set()
        if self.use_impact_reservoir:
            self._reservoir_age_expire()
            self._reservoir_deposit(
                contacts, lam, E_max, bodies=bodies, body_dp=body_dp, h=h)
            injection_data, eligible_keys = self._reservoir_eligible(contacts)
            E_inj_budget = float(sum(
                self.impact_reservoirs[k].energy for k in eligible_keys))
            self.last_E_reservoir_spent = 0.0   # set by _reservoir_debit if it fires
            self.last_E_reservoir_total = float(sum(
                e.energy for e in self.impact_reservoirs.values()))
            self.last_n_eligible_reservoirs = len(eligible_keys)
        else:
            injection_data = new_contacts_data
            E_inj_budget = E_max
            self.last_E_reservoir_deposit = 0.0
            self.last_E_reservoir_spent = 0.0
            self.last_E_reservoir_expired = 0.0
            self.last_E_reservoir_total = 0.0
            self.last_n_eligible_reservoirs = 0

        # delta_p source pre-pass: per rigid partner, sum |λ_N| over its NEW
        # contacts so the body's net measured contact impulse can be split
        # across those contacts by weight (realtime-coupling-fix §2.3).
        partner_lamN_sum: dict[int, float] = {}
        if self.impulse_source == "delta_p" and body_dp is not None:
            for contact, ci in injection_data:
                if 3 * ci >= len(lam):
                    continue
                partner = (contact.body_a
                           if contact.body_b == self.elastic_body_idx
                           else contact.body_b)
                partner_lamN_sum[partner] = (
                    partner_lamN_sum.get(partner, 0.0)
                    + abs(float(lam[3 * ci])))

        # --- Project new contact impulses → s_total (E1, foundation §4, §8) ---
        kicks_modal: list[NDArray[np.float64]] = []
        # Geodesic source tracking (paper §4.5): pick the largest admitted
        # impact's surface vertex as the source for this step's attenuation
        # field. Held across quiet steps in _commit_impact_source.
        impact_best: dict = {}
        for contact, ci in injection_data:
            j_world = self._impulse_for_contact(
                contact, ci, lam, h, k_normal, body_dp, partner_lamN_sum)
            if j_world is None:
                continue
            j_norm = float(np.linalg.norm(j_world))
            if j_norm < self.impulse_threshold:
                continue
            Phi_x = eval_basis_at_point(
                contact.point, self._surface, self.modal.U_surf,
                self.modal.surface_vertex_indices, self._vert_to_surf_idx,
            )
            s_c = project_impulse(Phi_x, j_world)
            kicks_modal.append(s_c)
            self._update_impact_source(contact.point, j_norm, impact_best)
        self._commit_impact_source(impact_best)

        n_substeps = max(1, int(np.ceil(h / self._stepper.T)))

        if not kicks_modal:
            # No new impulses — step the persistent state for free decay.
            # For most modes this means "no DCR response this step" (their
            # magnitudes are tied to E_loss which is zero here). The patch
            # mode is the exception: the moving deformable support drives
            # the response (prompt §0), so as long as q̇ ≠ 0 the support is
            # still moving and the resting contacts should feel it. We let
            # the patch branch run during free decay; the modal-reservoir
            # budget (used by patch mode, see _compute_distant_response_patch)
            # naturally drains so kicks taper as the modes decay.
            self.last_alpha = 0.0
            self.last_E_modal_pre_kick = modal_energy(
                self._stepper.q, self._stepper.qdot, omega)
            self.last_E_modal_post_kick = self.last_E_modal_pre_kick
            self.last_E_modal_injected = 0.0  # no new-contact injection
            self.last_E_modal_peak = max(
                self.last_E_modal_peak, self.last_E_modal_post_kick)
            self._qdot_just_after_kick = self._stepper.qdot.copy()
            self._stepper.step_n(n_substeps)
            if self.dcr_velocity_mode == "energy_prescribed_patch":
                # Synthesise a single-snapshot q_history so the deformed-
                # normal helpers see the current persistent modal state
                # (they expect q_history of shape (n_steps+1, n_modes)).
                q_history = self._stepper.q.reshape(1, -1).copy()
                self.last_q_history_transient = q_history
                result = self._compute_distant_response(
                    resting_contacts, q_history, h, E_max, bodies)
                # γ-decay must run AFTER DCR reads modal state (§16).
                self.last_E_modal_attenuation_diss = \
                    self._stepper.apply_rigid_step_decay()
                return result
            self.last_q_history_transient = None
            self._reset_velocity_mode_diagnostics()
            # γ-decay end-of-step (no DCR work was done; safe to attenuate).
            self.last_E_modal_attenuation_diss = \
                self._stepper.apply_rigid_step_decay()
            return {}

        s_total = aggregate_kicks(kicks_modal)

        # --- Passive scaling (E2, foundation §6) ---
        self.last_E_modal_pre_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)
        # Raw (pre-cap) kick diagnostics (realtime-coupling-fix §16). These
        # expose whether the IMPULSE SOURCE is iteration-sensitive
        # independently of the passive_alpha cap that may mask it:
        #   last_s_total_norm    = ‖s‖ (raw aggregated modal kick)
        #   last_dE_full_uncapped = b + ½a (modal energy the kick WOULD inject
        #                           at α=1, before the E_max cap).
        a_raw = float(np.dot(s_total, s_total))
        b_raw = float(np.dot(self._stepper.qdot, s_total))
        self.last_s_total_norm = float(np.sqrt(max(0.0, a_raw)))
        self.last_dE_full_uncapped = b_raw + 0.5 * a_raw
        if self.injection_scaling == "prescribed":
            # Energy-PRESCRIBED: scale the ΦᵀJ direction to deposit μ·budget of
            # modal energy (scale UP or DOWN), instead of capping at the raw
            # kick (foundation §15 as a target; docs §12). Iteration-insensitive
            # because the magnitude comes from E_loss, not from ‖s‖.
            E_target = float(np.clip(self.prescribed_mu, 0.0, 1.0)) * E_inj_budget
            alpha = prescribed_alpha(
                s_total, self._stepper.qdot, E_target,
                self.prescribed_alpha_max)
            if alpha >= self.prescribed_alpha_max - 1e-12:
                self.last_prescribed_alpha_cap_fired += 1
        else:
            alpha = passive_alpha(s_total, self._stepper.qdot, E_inj_budget)
        self.last_alpha = alpha

        # The scaled kick applied to the persistent energy state.
        alpha_s = alpha * s_total

        # --- Velocity kick (foundation §7): qdot += alpha * s_total ---
        self._stepper.qdot += alpha_s

        self.last_E_modal_post_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)
        self.last_E_modal_peak = max(
            self.last_E_modal_peak, self.last_E_modal_post_kick)
        # Injected modal energy this step (realtime-coupling-fix §16 signal).
        self.last_E_modal_injected = (
            self.last_E_modal_post_kick - self.last_E_modal_pre_kick)
        self.cum_E_modal_injected += max(0.0, self.last_E_modal_injected)
        # §7: drain the actual injected energy from the spending reservoirs.
        if self.use_impact_reservoir:
            self._reservoir_debit(
                eligible_keys, max(0.0, self.last_E_modal_injected))

        # Snapshot qdot right after the kick, BEFORE step_n decays it
        # through h substeps. The patch mode's §9.2 modal velocity driver
        # (v_f = Φ(x̄)·q̇) reads this — physically the support is swinging
        # at the kick instant, not at the end of the step. Reading qdot
        # post-step_n drops v_f by the Rayleigh-damping factor over h,
        # which underestimates the support velocity that the impulse
        # should be matching.
        self._qdot_just_after_kick = self._stepper.qdot.copy()

        # --- Step persistent state for energy bookkeeping (E3.1) ---
        self._stepper.step_n(n_substeps)

        # --- Transient displacement for DCR response (Eqs. 11-13) ---
        # Use ONLY this step's kick for the displacement response, not
        # the full persistent state. This matches the original IIR behavior
        # (reset each step) while keeping the persistent state for energy.
        q_history_transient = self._stepper.transient_step_n(alpha_s, n_substeps)
        self.last_q_history_transient = q_history_transient

        result = self._compute_distant_response(
            resting_contacts, q_history_transient, h, E_max, bodies)
        # γ-decay must run AFTER DCR reads modal state (§16). transient_step_n
        # is pure (its output is independent of self.q/self.qdot), but
        # _compute_distant_response may read the persistent state for patch
        # mode / back-reaction; attenuate after it returns.
        self.last_E_modal_attenuation_diss = \
            self._stepper.apply_rigid_step_decay()
        return result

    # ------------------------------------------------------------------
    # Coherent impact impulse bank step (coherent_impact_impulse_bank_fix)
    # ------------------------------------------------------------------

    def _process_step_coherent_bank(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        h: float,
        E_max: float,
        bodies: list[RigidBody] | None,
        resting_contacts: list[Contact],
        omega: NDArray[np.float64],
        k_normal: NDArray[np.float64] | None,
        body_dp: dict[int, NDArray[np.float64]] | None,
    ) -> dict[int, float]:
        """Coherent impact impulse bank path (coherent_impact_impulse_bank_fix).

        Banks the per-frame contact impulses of one physical impact into a
        per-(rigid, support) event over a short causal window, then injects the
        event-level modal energy ½‖Σ s_i‖² — recovering the positive cross terms
        the per-frame path discards (spec §3). Subsumes the reservoir: η·E_loss
        is deposited once into the event budget, and each injection is capped by
        passive_alpha(S_event, q̇, B_event), so global passivity
        Σ E_inj ≤ η·Σ E_loss holds (spec §4). The patch distant-response tail
        mirrors process_step's (the AVBD branch only runs energy_prescribed_patch).
        """
        bank = self._bank
        assert bank is not None
        n_substeps = max(1, int(np.ceil(h / self._stepper.T)))

        # Reservoir diagnostics are inert here — the bank owns the budget.
        self.last_E_reservoir_deposit = 0.0
        self.last_E_reservoir_spent = 0.0
        self.last_E_reservoir_expired = 0.0
        self.last_E_reservoir_total = 0.0
        self.last_n_eligible_reservoirs = 0

        # 1. Age / λ_B-decay / expire, then deposit η·E_loss once (spec §4, §10).
        bank.begin_step()
        bank.deposit(contacts, lam, E_max, self._reservoir_key)

        # 2. Accumulate every engaged elastic-body contact's impulse, gated for
        #    coherence (spec §8). delta_p needs the per-partner |λ_N| prepass.
        elastic_data = [
            (c, ci) for ci, c in enumerate(contacts)
            if self._reservoir_key(c) is not None]
        partner_lamN_sum: dict[int, float] = {}
        if self.impulse_source == "delta_p" and body_dp is not None:
            for contact, ci in elastic_data:
                if 3 * ci >= len(lam):
                    continue
                partner = (contact.body_a
                           if contact.body_b == self.elastic_body_idx
                           else contact.body_b)
                partner_lamN_sum[partner] = (
                    partner_lamN_sum.get(partner, 0.0)
                    + abs(float(lam[3 * ci])))
        for contact, ci in elastic_data:
            key = self._reservoir_key(contact)
            if key is None:
                continue
            j_world = self._impulse_for_contact(
                contact, ci, lam, h, k_normal, body_dp, partner_lamN_sum)
            if j_world is None:
                continue
            if np.linalg.norm(j_world) < self.impulse_threshold:
                continue
            Phi_x = eval_basis_at_point(
                contact.point, self._surface, self.modal.U_surf,
                self.modal.surface_vertex_indices, self._vert_to_surf_idx,
            )
            s_i = project_impulse(Phi_x, j_world)
            n_i = np.asarray(contact.normal, dtype=np.float64)
            n_hat = n_i / max(float(np.linalg.norm(n_i)), 1e-30)
            jn = abs(float(np.dot(j_world, n_hat)))
            jt = float(np.linalg.norm(j_world - np.dot(j_world, n_hat) * n_hat))
            bank.accumulate(key, s_i, j_world, contact.point, n_i, jn, jt)

        # 3. Inject ready events (spec §10). Each event uses its own budget
        #    B_event with passive_alpha; the realized ΔE is measured on q̇ and
        #    debited back, so cum_E_modal_injected is the single global ledger.
        self.last_E_modal_pre_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)
        alpha_s_total = np.zeros_like(self._stepper.qdot)
        a_raw_sum = 0.0
        dE_full_sum = 0.0
        alpha_max = 0.0
        for key in bank.ready_keys():
            ev = bank.event(key)
            if self.impact_bank_mode == "modal_sum":
                S = ev.S_event
            else:  # impulse_reconstruct: project the summed impulse at x̄ once.
                if ev.Jmag_sum <= bank.eps:
                    bank.mark_spent(key, 0.0)
                    continue
                Phi_xbar = eval_basis_at_point(
                    ev.x_bar, self._surface, self.modal.U_surf,
                    self.modal.surface_vertex_indices, self._vert_to_surf_idx,
                )
                S = project_impulse(Phi_xbar, ev.J_event)
            a = float(np.dot(S, S))
            if a <= _EPS_TINY:
                bank.mark_spent(key, 0.0)
                continue
            b = float(np.dot(self._stepper.qdot, S))
            a_raw_sum += a
            dE_full_sum += b + 0.5 * a
            pre = modal_energy(self._stepper.q, self._stepper.qdot, omega)
            alpha = passive_alpha(S, self._stepper.qdot, ev.B_event)
            self._stepper.qdot += alpha * S
            post = modal_energy(self._stepper.q, self._stepper.qdot, omega)
            injected = post - pre
            self.cum_E_modal_injected += max(0.0, injected)
            alpha_s_total = alpha_s_total + alpha * S
            alpha_max = max(alpha_max, alpha)
            bank.mark_spent(key, max(0.0, injected))
        bank.end_step()

        # 4. Energy + bank diagnostics (mirror the reservoir/per-frame fields).
        self.last_E_modal_post_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)
        self.last_E_modal_injected = (
            self.last_E_modal_post_kick - self.last_E_modal_pre_kick)
        self.last_E_modal_peak = max(
            self.last_E_modal_peak, self.last_E_modal_post_kick)
        self.last_alpha = alpha_max
        self.last_s_total_norm = float(np.sqrt(max(0.0, a_raw_sum)))
        self.last_dE_full_uncapped = dE_full_sum
        self.last_E_bank_deposit = bank.last_E_deposit
        self.last_E_bank_spent = bank.last_E_spent
        self.last_E_bank_expired = bank.last_E_expired
        self.last_n_bank_events = bank.last_n_events
        self.last_R_coherence = bank.mean_R_coherence()

        # 5. Step persistent state, build the transient displacement for the
        #    patch distant response, then γ-decay (foundation §16) — mirrors
        #    process_step's tail. has_kick decides transient vs free-decay q.
        self._qdot_just_after_kick = self._stepper.qdot.copy()
        self._stepper.step_n(n_substeps)
        has_kick = float(np.dot(alpha_s_total, alpha_s_total)) > _EPS_TINY
        if has_kick:
            q_history = self._stepper.transient_step_n(alpha_s_total, n_substeps)
        else:
            # No injection this step — drive the patch response from the current
            # persistent modal state (same as process_step's no-kick patch
            # branch); the moving support still rings as q̇ decays.
            q_history = self._stepper.q.reshape(1, -1).copy()
        self.last_q_history_transient = q_history
        result = self._compute_distant_response(
            resting_contacts, q_history, h, E_max, bodies)
        self.last_E_modal_attenuation_diss = \
            self._stepper.apply_rigid_step_decay()
        return result

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

        In the AVBD branch only "energy_prescribed_patch" is reachable
        (the other branches are walled off in __post_init__). When the
        active mode is patch, we skip the always-on Coevoet + Version A
        diagnostic computations entirely — each does a brute-force
        closest-triangle scan over the slab mesh per contact and
        dominated the cost profile on CPU.
        """
        is_patch_only = (self.dcr_velocity_mode == "energy_prescribed_patch")

        # --- 1. Coevoet proposal (existing Eq. 12). Unchanged. ----------
        # Skipped in patch-only mode — Coevoet's dv is not consumed and
        # _compute_distant_response_coevoet calls _compute_max_displacement
        # which scans the surface mesh per contact.
        if is_patch_only:
            dv_coevoet = {}
        else:
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
        # Same skip — Version A also walks the surface per contact for
        # its deformed-normal lookup.
        if is_patch_only or bodies is None:
            linear_kicks = []
        else:
            linear_kicks = self._compute_distant_response_energy_A(
                resting_contacts, q_history, bodies, E_target, h)
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
        if mode == "energy_prescribed_patch":
            # Patch-based reformulation (prompt §9): cluster resting
            # contacts by body pair, build the geometric patch, then run
            # the full velocity-correction pipeline (§9.2-9.6).
            if bodies is None:
                raise ValueError(
                    "dcr_velocity_mode='energy_prescribed_patch' requires "
                    "`bodies` to be passed to "
                    "PassiveDCRCoupler.process_step(). "
                    "DCRWorld.step() supplies this automatically.")
            patches = self._build_patches_for_step(resting_contacts, bodies)
            self.last_patches = patches
            patch_kicks = self._compute_distant_response_patch(
                patches=patches,
                resting_contacts=resting_contacts,
                q_history=q_history,
                bodies=bodies,
                E_target=E_target,
                h=h,
            )
            self.last_linear_kicks = None
            self.last_point_impulse_kicks = None
            self.last_patch_kicks = patch_kicks
            return {}
        raise ValueError(f"unknown dcr_velocity_mode: {mode!r}")

    # ------------------------------------------------------------------
    # Patch-mode helper: cluster contacts and build geometric patches
    # (prompt §9.1 / foundation §7).
    # ------------------------------------------------------------------

    def _build_patches_for_step(
        self,
        resting_contacts: list[Contact],
        bodies: list[RigidBody],
    ) -> list[ContactPatch]:
        """Cluster `resting_contacts` by body pair and call `build_patch`.

        Static-static pairs are filtered out (they have no body to receive
        a kick). Single-contact "clusters" go through the same code path
        so the centroid degenerates to the contact point itself — the
        patch then has the same x̄ / n̄' as the original contact, with
        the only added effect being the lever-arm clamp.

        Weighting is uniform here (lambda_n=None) because the patch mode
        does not currently consume per-contact solver impulses — when
        §9.2-9.6 land they will, and this method will gain a `lam`
        argument plumbed in from `process_step`.
        """
        if not resting_contacts:
            return []
        clusters = cluster_contacts_by_body_pair(resting_contacts)
        patches: list[ContactPatch] = []
        for body_a, body_b, idxs in clusters:
            if bodies[body_a].is_static and bodies[body_b].is_static:
                continue
            patches.append(build_patch(
                body_a=body_a,
                body_b=body_b,
                contact_idxs=idxs,
                contacts=resting_contacts,
                bodies=bodies,
                weight_mode="uniform",
                lambda_n=None,
            ))
        return patches

    # ------------------------------------------------------------------
    # Patch response pipeline (prompt §9.2-9.6, foundation §15).
    # ------------------------------------------------------------------

    def _compute_distant_response_patch(
        self,
        patches: list[ContactPatch],
        resting_contacts: list[Contact],
        q_history: NDArray[np.float64],
        bodies: list[RigidBody],
        E_target: float,
        h: float,
    ) -> list[PatchKick]:
        """Compute one patch-based impulse per patch (prompt §9.2-9.6).

        Per patch:
          §9.2 v_f  = Φ(x̄) · q̇                          (modal velocity at x̄)
          §9.3 n̄'  = deformed_normal(x̄, n̄_rest)         (this follow-up's
                                                            patch_fit / BJ)
                Δv_des = v_f − v_p                       (prompt §2.3; no
                                                            extra clamp —
                                                            passivity bounds)
          §9.4 K   = (1/m) I + R · I⁻¹ · R^T            (3×3 contact-pt
                                                            effective mass)
                λ  = K⁻¹ · Δv_des                        (Δv = K λ → λ = K⁻¹ Δv)
          §9.5 λ ← cone_project(λ, n̄', μ)               (Coulomb projection)
          §9.6 s  = (-a + √(a² + 2 b E_cap)) / b          (passivity scaling)
                λ ← s · λ                                 (with E_cap per patch)

        Receiver body identification: the body that is NOT the elastic
        foundation. Patches between two non-elastic bodies (e.g., a
        rigid-rigid contact) are skipped — the DCR coupling is from the
        elastic foundation outward.

        Energy budget per patch: E_target is divided uniformly across
        patches that have a non-static receiver. Future work (foundation
        §8 / prompt §8) replaces this with mass-weighted allocation.

        # DEVIATION (prompt §2.3): the clamp `Δv_des ← clamp(..., Δv_max)`
        # is omitted — Δv_max is unspecified by the prompt, and the
        # passivity step (§9.6) already provides a principled magnitude
        # bound. If observed kicks are too large in practice, Δv_max can be
        # added as a knob (e.g., d_max/h to mirror Coevoet's ceiling).
        #
        # DEVIATION (prompt §2.3): the projection P_{n',t}(...) is omitted
        # — Δv_des is used directly as the 3-vector v_f − v_p, then
        # K⁻¹·Δv_des produces a 3-vector λ. The Coulomb projection in §9.5
        # operates on the same 3D representation, so the contact-frame
        # projection step is redundant.
        #
        # NOTE (prompt §2.1): v_f is evaluated using `qdot` snapshotted
        # right AFTER the kick (before step_n decays it through h). This
        # captures the support's "kick instant" velocity, which is what
        # physically the impulse should be matching. Reading post-step_n
        # qdot underestimates v_f by the Rayleigh-damping factor over h
        # — a noticeable difference when α₁·h is non-negligible.
        """
        # Reset per-step null-space projection diagnostics. Set at the top
        # so values always reflect the CURRENT call (incl. early-out paths).
        self.last_projection_rho = []
        self.last_projection_fired = 0
        self.last_projection_skipped = 0
        self.last_E_projection_removed = 0.0
        # COM-shadow diagnostics (no-op when com_shadow_mode is False).
        self.last_com_shadow_kicks_fired = 0
        self.last_com_shadow_kd_lookups = 0

        if not patches:
            return []

        # ---- Contact-causal numerical cutoff (proposal §3, opt-in) -------
        # Skip the entire patch dispatch when residual modal energy is
        # below `e_modal_cutoff_frac · last_E_modal_peak`. This is a
        # computation-only gate (no physical effect at the threshold
        # we use, default 1e-5 · E_peak ≈ 0.01 J for typical scenes).
        if self.causal_gating and self.last_E_modal_peak > 0.0:
            E_now = float(modal_energy(
                self._stepper.q, self._stepper.qdot, self.modal.frequencies))
            if E_now < self.e_modal_cutoff_frac * self.last_E_modal_peak:
                self.last_patch_gated_numerical = len(patches)
                return []

        # Filter patches that have a non-static receiver and identify it.
        valid: list[tuple[ContactPatch, int, NDArray[np.float64], NDArray[np.float64]]] = []
        for p in patches:
            if p.body_a == self.elastic_body_idx:
                recv_idx = p.body_b
                r_bar = p.r_bar_b
                # n_rest_bar is oriented A→B = elastic→receiver, so push_dir
                # (elastic onto receiver) is n_rest_bar itself.
                push_dir = p.n_rest_bar
            elif p.body_b == self.elastic_body_idx:
                recv_idx = p.body_a
                r_bar = p.r_bar_a
                # n_rest_bar is A→B = receiver→elastic; push_dir
                # (elastic onto receiver) is −n_rest_bar.
                push_dir = -p.n_rest_bar
            else:
                # Neither body is the elastic foundation — no DCR coupling.
                continue
            recv = bodies[recv_idx]
            if recv.is_static or recv.mass <= 0.0:
                continue
            valid.append((p, recv_idx, r_bar, push_dir))
        if not valid:
            return []

        # Per-patch energy budget for the §9.6 passivity scaling.
        #
        # # DEVIATION (foundation §1, §6, §15): the patch mode passivity
        # # budget comes from the MODAL RESERVOIR (current modal kinetic +
        # # elastic energy), not from `β · E_loss`. Rationale: this is the
        # # EXTRACTION direction (modal → rigid via the moving support);
        # # the constraint is "don't take out more than is in the reservoir
        # # right now". β · E_loss is the right budget for the INJECTION
        # # direction (used by the alpha-scaling step in process_step, and
        # # by Versions A/B for their kick magnitude).
        # # Equal split across patches — foundation §8 / prompt §8 would
        # # weight by effective mass / spatial attenuation; uniform is the
        # # smallest defensible choice.
        E_reservoir = float(modal_energy(
            self._stepper.q, self._stepper.qdot, self.modal.frequencies))
        beta_clip = float(np.clip(self.energy_response_beta, 0.0, 1.0))
        E_target_patch = beta_clip * max(0.0, E_reservoir)
        E_per_patch = E_target_patch / len(valid) if E_target_patch > 0.0 else 0.0

        frames = self._get_tangent_frames()
        # §9.2 driver: support velocity at the IMPACT INSTANT, not at
        # end-of-step. See _qdot_just_after_kick — snapshotted before
        # step_n decays the modal state through h substeps.
        qdot_drive = self._qdot_just_after_kick

        # Geodesic field for this step's source (paper §4.5). Computed
        # once outside the loop and shared across all patches.
        geo_field = None
        if (self.use_geodesic_attenuation
                and self._last_impact_vert is not None):
            geo_field = heat_geodesic_cached(
                self._surface, self._geodesic_cache,
                int(self._last_impact_vert))

        # COM-shadow mode: collapse to one kick per receiver body at its
        # COM, with Φ sampled once at the COM-shadow on the support. See
        # the dataclass field's DEVIATION block.
        if self.com_shadow_mode:
            return self._dispatch_com_shadow_kicks(
                valid=valid,
                bodies=bodies,
                resting_contacts=resting_contacts,
                qdot_drive=qdot_drive,
                geo_field=geo_field,
                E_target_patch=E_target_patch,
            )

        kicks: list[PatchKick] = []
        gamma_min = 1.0  # smallest dissipativity-guard scale this step
        for patch, recv_idx, r_bar, push_dir in valid:
            recv = bodies[recv_idx]
            # §9.3 — deformed normal at the patch centroid x̄. Reuses
            # patch_fit / barbic_james depending on deformed_normal_method.
            n_def, theta, _ = self._deformed_normal(
                contact_point=patch.x_bar,
                push_dir=push_dir,
                q_history=q_history,
                frames=frames,
            )
            # §9.2 — modal velocity at the patch centroid.
            # eval_basis_at_point returns Φ(x̄) ∈ R^{3 × n_modes}; the
            # support's contact-point velocity is Φ(x̄)·q̇.
            Phi_x = eval_basis_at_point(
                patch.x_bar, self._surface, self.modal.U_surf,
                self.modal.surface_vertex_indices, self._vert_to_surf_idx,
            )
            v_f = Phi_x @ qdot_drive

            # ---- Geodesic-distance attenuation (paper §4.5, Eq. 14) -----
            # Scale the SUPPORT-driven velocity v_f by α ∈ [0, 1]; leave v_p
            # (receiver's own motion) intact. α cascades safely through K⁻¹
            # (linear), cone projection (direction-preserving), §9.6 scaling
            # (positive scalar) and the §9.7 dissipativity guard — passivity
            # is preserved because α ≤ 1.
            if geo_field is not None:
                rv = self._closest_surface_vertex(patch.x_bar)
                d_geo = float(geo_field[rv])
                if np.isfinite(d_geo):
                    v_f = self._geodesic_alpha(d_geo) * v_f

            # Receiver contact-point velocity v_p = v + ω × r̄.
            v_lin = recv.velocity[0:3]
            omega = recv.velocity[3:6]
            v_p = v_lin + np.cross(omega, r_bar)

            # ---- Contact-causal gates (proposal §1, §2; opt-in) ---------
            # Both gates close the cone on the SAME axis the §9.5 cone
            # uses — push_dir (rest normal). Using n_def here would
            # defeat its purpose as a tilt direction (lateral leak would
            # show up as 'closing'). See plan §design-rationale-2.
            if self.causal_gating:
                # §1 contact-shell gate: admit when ANY contact in the
                # patch is within delta of the slab. Min-gap is the
                # conservative-admit rule. `gap = -penetration` because
                # Contact.penetration is signed positive when overlapping.
                min_gap = min(
                    -resting_contacts[ci].penetration
                    for ci in patch.contact_indices
                )
                if min_gap > self.contact_shell_delta:
                    self.last_patch_gated_no_contact += 1
                    continue
                # §2 closing-velocity gate: skip if the slab is not
                # moving INTO the receiver above the contact-slop
                # deadband. v_min ≈ √(2·g·δ_slop) is the speed at which
                # the surface could lift the body above contact slop.
                n_axis = push_dir / max(
                    float(np.linalg.norm(push_dir)), 1e-30)
                closing = float((v_f - v_p) @ n_axis)
                if closing <= self.v_min_closing:
                    self.last_patch_gated_low_closing += 1
                    continue

            # Δv_des = v_f − v_p (prompt §2.3, no clamp; see DEVIATION).
            dv_des = v_f - v_p

            # §9.4 — solve K_total λ = Δv_des with the BILATERAL
            # contact effective mass:
            #     K_total = K_body + Φ·Φᵀ
            # where K_body is the rigid body's 3×3 contact-point
            # effective mass and Φ·Φᵀ is the modal system's effective
            # mass at x̄ (mass-normalized modes, so each mode's
            # contribution is its 3-vector at x̄ outer-producted with
            # itself).
            #
            # Why K_body alone is WRONG: that formulation assumes the
            # modal system is infinitely massive (a rigid wall) — the
            # impulse changes only the body's velocity, not the support's.
            # Then the modal back-reaction -Φᵀλ over-extracts: for large
            # λ, ΔE_modal turns POSITIVE (modal energy GROWS from each
            # kick → runaway positive feedback). Empirically observed:
            # books launched to >1 m on the shelf scene.
            #
            # With K_total, λ satisfies the matched-velocity constraint
            #   (v_p + K_body·λ) - (v_f - Φ·Φᵀ·λ) = 0
            # after both body and modal velocity changes. Energy
            # accounting: ΔE_total = -½ λᵀ·K_total·λ < 0 (passive —
            # the constraint dissipates kinetic energy, as a perfectly
            # inelastic collision would).
            K_body = patch_effective_mass_matrix(recv, r_bar)
            K_modal_eff = Phi_x @ Phi_x.T  # (3, 3) symmetric PSD
            K_total = K_body + K_modal_eff
            lam = solve_patch_impulse(K_total, dv_des)
            # Use K_total for downstream passivity (a, b coefficients).
            K = K_total

            # §9.5 — Coulomb cone projection around the REST normal
            # (not n_def). The whole point of n_def in this formulation
            # is to generate a tilt of the kick into the lateral direction;
            # the cone must reject that lateral leak. Projecting around
            # n_def would treat the tilt-induced lateral component as
            # "normal", defeating its purpose. Mirrors Version B's
            # `contact_point_friction_correction` which also uses n_rest.
            # μ matches the rigid solver rule: min over the pair
            # (dcr/rigid/solver.py:206-207).
            mu = float(min(
                bodies[patch.body_a].friction,
                bodies[patch.body_b].friction,
            ))
            # push_dir is the canonical-A→B rest normal already oriented
            # foundation→receiver; that's the right cone axis.
            n_cone = push_dir / max(float(np.linalg.norm(push_dir)), 1e-30)
            lam_proj, cone_clipped = cone_project_impulse(lam, n_cone, mu)

            # §9.6 — passivity scaling. E_cap is this patch's share of
            # E_target; the global energy_response_beta is already folded
            # into E_target upstream.
            s, _a_pass, _b_pass = patch_passive_scaling(
                lam_proj, v_p, K, E_per_patch)
            lam_final = s * lam_proj

            # ----------------------------------------------------------
            # DISSIPATIVITY GUARD (foundation §15 extraction dual; one-shot
            # γ per prompts/avbd_dcr_realtime_coupling_fix.md §9).
            #
            # The §9.4 identity ΔE_total = −½ λᵀ K_total λ ≤ 0 holds ONLY for
            # the raw λ = K_total⁻¹·Δv_des; the §9.5 cone projection and §9.6
            # scaling change the impulse, so the back-reaction below can ADD
            # modal energy (its self-term +½‖Φᵀλ‖²) → the runaway leak (see
            # docs/avbd_dcr_coupling_findings §5/§6). Bound the back-reaction's
            # OWN modal-energy change, measured on the ACTUAL q̇ it mutates
            # (= the post-step_n self._stepper.qdot, NOT Δv_des / v_f which are
            # built from the pre-step_n _qdot_just_after_kick):
            #     ΔE_modal(γ) = −γ·c_m + ½ γ² a_m,
            #     j = Φ(x̄)ᵀ·lam_final,  c_m = q̇ᵀj = (Φq̇)·lam_final,
            #                            a_m = ‖j‖² = lam_finalᵀ ΦΦᵀ lam_final ≥ 0.
            # Largest γ∈[0,1] with ΔE_modal(γ) ≤ 0, applied to BOTH the rigid
            # kick and the back-reaction (transpose-consistent). γ=1 when the
            # kick already drains (a_m ≤ 2c_m) → well-behaved scenes unchanged;
            # γ<1 clamps the runaway; γ=0 rejects a kick that can only add
            # modal energy. Guarantees the reservoir can only drain.
            j_back = Phi_x.T @ lam_final
            c_m = float(self._stepper.qdot @ j_back)
            a_m = float(j_back @ j_back)
            if c_m <= 0.0:
                gamma_br = 0.0
            elif a_m <= 1e-30:
                gamma_br = 1.0
            else:
                gamma_br = min(1.0, 2.0 * c_m / a_m)
            lam_final = gamma_br * lam_final
            gamma_min = min(gamma_min, gamma_br)

            # ----------------------------------------------------------
            # CONTACT-COMPATIBLE NULL-SPACE PROJECTION (fix-doc §6-8,
            # 6D Δu form — preserves yaw).
            #
            # # DEVIATION (DCR paper §9 single-centroid patch kick): the
            # # §9 formulation applies a single point impulse at the
            # # patch centroid; for a thin body in flat resting contact
            # # the lever × tangential impulse becomes torque the body
            # # cannot resist (visible as fork roll/pitch on the
            # # dinner_table scene). We zero the DIFFERENTIAL normal
            # # velocity across patch sample points in 6D velocity-
            # # increment space — the constraint depends only on Δω, so
            # # Δv stays unchanged and the body still receives a full
            # # linear push from the kick; only the angular component
            # # is constrained. Yaw (Δω ∥ n) lies in the constraint
            # # null-space and is allowed; only roll/pitch (Δω in the
            # # contact plane) gets suppressed. The §15 passivity bound
            # # is preserved because M-metric projection is energy-
            # # non-increasing and the modal back-reaction continues to
            # # use the original lam_final (the "intended" impulse).
            # # See prompts/dcr_patch_kick_nullspace_projection_fix.md.
            du_override = None
            if self.projection_enabled:
                project, use_t = should_project_patch(
                    body_shape=recv.shape,
                    rotation_matrix=recv.rotation_matrix(),
                    n_contact_points=len(patch.contact_indices),
                    v_p_at_centroid=v_p,
                    normal=n_cone,
                    thin_ratio=self.projection_thin_ratio,
                    v_n_thresh=self.projection_v_n_thresh,
                    v_t_thresh=self.projection_v_t_thresh,
                    use_tangent_rows=self.projection_use_tangent_rows,
                )
                if project:
                    pts = np.stack(
                        [resting_contacts[ci].point
                         for ci in patch.contact_indices],
                        axis=0,
                    )
                    tangents = (
                        _pick_friction_dirs(n_cone) if use_t else None
                    )
                    # Δu_raw = L · lam_final (centroid-impulse → body
                    # velocity increment if applied via §9).
                    inv_m = 1.0 / recv.mass
                    omega_raw = recv.inertia_world_inv() @ np.cross(
                        r_bar, lam_final)
                    du_raw = np.empty(6, dtype=np.float64)
                    du_raw[0:3] = inv_m * lam_final
                    du_raw[3:6] = omega_raw
                    du_proj, rho = project_du_contact_compatible(
                        du_raw=du_raw,
                        patch_points=pts,
                        com_world=recv.position,
                        normal=n_cone,
                        tangents=tangents,
                        mass=recv.mass,
                        inertia_world=recv.inertia_world(),
                        tangent_weight=self.projection_tangent_weight,
                        eps=self.projection_eps,
                    )
                    du_override = du_proj
                    # Energy bookkeeping: ½·Δuᵀ·M·Δu is the body's
                    # kinetic-energy increment under Δu.
                    m_body = recv.mass
                    I_w = recv.inertia_world()
                    e_pre = 0.5 * (
                        m_body * float(du_raw[0:3] @ du_raw[0:3])
                        + float(du_raw[3:6] @ I_w @ du_raw[3:6]))
                    e_post = 0.5 * (
                        m_body * float(du_proj[0:3] @ du_proj[0:3])
                        + float(du_proj[3:6] @ I_w @ du_proj[3:6]))
                    self.last_projection_rho.append(rho)
                    self.last_projection_fired += 1
                    self.last_E_projection_removed += max(
                        0.0, e_pre - e_post)
                else:
                    self.last_projection_skipped += 1

            kicks.append(PatchKick(
                body_idx=recv_idx,
                lam=lam_final,
                x_bar=patch.x_bar.copy(),
                r_bar=r_bar.copy(),
                n_def=n_def.copy(),
                v_f=v_f.copy(),
                v_p_pre=v_p.copy(),
                s_passivity=s,
                cone_clipped=cone_clipped,
                du_override=du_override,
            ))

            # ----------------------------------------------------------
            # MODAL BACK-REACTION (Newton's third law / energy
            # conservation). The impulse λ delivered to the rigid body
            # at x̄ must come FROM the modal reservoir; equivalently, the
            # modal system receives -Φ(x̄)ᵀ·λ at the same point.
            #
            # Without this step, modal energy never depletes from patch
            # kicks (only Rayleigh damping drains it slowly), so the
            # E_reservoir → E_per_patch budget stays high step after
            # step and accumulated kicks tip thin bodies over hundreds
            # of steps. With this back-reaction, each kick directly
            # reduces q̇ → reduces v_f next step → kicks taper as the
            # modal reservoir drains. This is the passivity-as-driver
            # mechanism the prompt §0 calls for.
            #
            # Foundation §15 (the core passivity inequality) bounds
            # ΔE_modal ≤ η · ΔE_rigid_loss for the INJECTION direction;
            # the EXTRACTION direction (modal → rigid via patch kick)
            # is its dual: |ΔE_modal_lost| ≥ ΔE_rigid_gain. The back-
            # reaction together with the §9.6 passivity scaling
            # enforces both directions.
            self._stepper.qdot -= Phi_x.T @ lam_final
        self.last_backreaction_gamma_min = gamma_min
        return kicks

    # ------------------------------------------------------------------
    # COM-shadow modal sampling — per-body collapse of the patch loop.
    # See `com_shadow_mode` dataclass field for the DEVIATION block.
    # ------------------------------------------------------------------

    def _dispatch_com_shadow_kicks(
        self,
        valid: list[
            tuple[ContactPatch, int, NDArray[np.float64], NDArray[np.float64]]
        ],
        bodies: list[RigidBody],
        resting_contacts: list[Contact],
        qdot_drive: NDArray[np.float64],
        geo_field: NDArray[np.float64] | None,
        E_target_patch: float,
    ) -> list[PatchKick]:
        """One kick per receiver body at its COM; Φ sampled once at the
        body's COM-shadow on the support.

        Mirrors `_compute_distant_response_patch`'s inner loop with three
        structural simplifications:
            1. r̄ = 0  →  K_body collapses to (1/m)·I; the lever-arm
               Δω = I⁻¹·(r̄ × λ) is identically zero, so the projection
               step is a no-op and we skip it entirely.
            2. One Φ evaluation per body (KD lookup at body.position)
               instead of one per patch — reduces KD calls from
               O(N_patches) to O(N_bodies).
            3. E_target split across receivers instead of patches.
               Receivers, not patches, are the per-step demand unit.

        Per receiver: aggregate the body's patches (union contact_indices
        for the contact-shell gate; pick push_dir from the first patch —
        for a body resting on the slab they are all world-up).
        """
        # Group valid entries by receiver body.
        by_body: dict[
            int, list[tuple[ContactPatch, NDArray[np.float64]]]
        ] = {}
        push_dirs: dict[int, NDArray[np.float64]] = {}
        for patch, recv_idx, _r_bar_unused, push_dir in valid:
            by_body.setdefault(recv_idx, []).append((patch, push_dir))
            push_dirs.setdefault(recv_idx, push_dir)

        n_receivers = len(by_body)
        E_per_receiver = (
            E_target_patch / n_receivers if E_target_patch > 0.0 else 0.0
        )

        kicks: list[PatchKick] = []
        gamma_min = 1.0
        for recv_idx, patch_list in by_body.items():
            recv = bodies[recv_idx]
            push_dir = push_dirs[recv_idx]
            n_axis = push_dir / max(float(np.linalg.norm(push_dir)), 1e-30)

            # ---- Φ at body's COM-shadow (one KD lookup per body) ------
            # eval_basis_at_point's KD-tree closest-triangle search picks
            # the slab surface point closest to body.position; for a body
            # resting on the slab that IS the COM-shadow. The location's
            # name `x_shadow` records the geometric meaning.
            x_shadow = recv.position
            Phi_x = eval_basis_at_point(
                x_shadow, self._surface, self.modal.U_surf,
                self.modal.surface_vertex_indices, self._vert_to_surf_idx,
            )
            self.last_com_shadow_kd_lookups += 1
            v_f = Phi_x @ qdot_drive

            # §4.5 geodesic-distance attenuation (matches per-patch path).
            if geo_field is not None:
                rv = self._closest_surface_vertex(x_shadow)
                d_geo = float(geo_field[rv])
                if np.isfinite(d_geo):
                    v_f = self._geodesic_alpha(d_geo) * v_f

            # r̄ = 0 ⇒ v_p = v_lin (no ω × r̄ term).
            v_p = recv.velocity[0:3].copy()

            # ---- Contact-causal gates (aggregated over the body's
            # patches). The shell gate uses min over the union of
            # contact indices; the closing gate uses (v_f - v_p)·n̂.
            if self.causal_gating:
                all_ci = []
                for patch, _pd in patch_list:
                    all_ci.extend(patch.contact_indices)
                min_gap = min(
                    -resting_contacts[ci].penetration for ci in all_ci
                )
                if min_gap > self.contact_shell_delta:
                    self.last_patch_gated_no_contact += len(patch_list)
                    continue
                closing = float((v_f - v_p) @ n_axis)
                if closing <= self.v_min_closing:
                    self.last_patch_gated_low_closing += len(patch_list)
                    continue

            dv_des = v_f - v_p

            # §9.4 — K_total = K_body + Φ·Φᵀ with K_body = (1/m)·I.
            # The cross terms in patch_effective_mass_matrix vanish at
            # r̄ = 0; the closed form is (1/m)·I exactly. We construct
            # it directly to avoid a wasted call.
            inv_m = 1.0 / recv.mass
            K_body = inv_m * np.eye(3)
            K_modal_eff = Phi_x @ Phi_x.T
            K_total = K_body + K_modal_eff
            lam = solve_patch_impulse(K_total, dv_des)
            K = K_total

            # §9.5 Coulomb cone projection around the rest normal.
            mu = float(min(
                bodies[patch_list[0][0].body_a].friction,
                bodies[patch_list[0][0].body_b].friction,
            ))
            lam_proj, cone_clipped = cone_project_impulse(lam, n_axis, mu)

            # §9.6 passivity scaling (per-receiver E budget).
            s, _a_pass, _b_pass = patch_passive_scaling(
                lam_proj, v_p, K, E_per_receiver)
            lam_final = s * lam_proj

            # Dissipativity guard (same logic as per-patch path).
            j_back = Phi_x.T @ lam_final
            c_m = float(self._stepper.qdot @ j_back)
            a_m = float(j_back @ j_back)
            if c_m <= 0.0:
                gamma_br = 0.0
            elif a_m <= 1e-30:
                gamma_br = 1.0
            else:
                gamma_br = min(1.0, 2.0 * c_m / a_m)
            lam_final = gamma_br * lam_final
            gamma_min = min(gamma_min, gamma_br)

            # PatchKick with r̄ = 0 — the existing apply path computes
            # Δω = I⁻¹·(r̄ × λ) = 0 from this without further changes.
            # x_bar is recorded as x_shadow for diagnostics; no kinematic
            # role because the impulse acts at the COM, not at x_shadow.
            kicks.append(PatchKick(
                body_idx=recv_idx,
                lam=lam_final,
                x_bar=x_shadow.copy(),
                r_bar=np.zeros(3, dtype=np.float64),
                n_def=n_axis.copy(),
                v_f=v_f.copy(),
                v_p_pre=v_p.copy(),
                s_passivity=s,
                cone_clipped=cone_clipped,
                du_override=None,
            ))
            self.last_com_shadow_kicks_fired += 1

            # Modal back-reaction at the same sample location.
            self._stepper.qdot -= Phi_x.T @ lam_final

        self.last_backreaction_gamma_min = gamma_min
        return kicks

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
        self.last_patches = None
        self.last_patch_kicks = None
