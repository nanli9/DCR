"""Reduced-support legacy DCR post-kick coupler (--mode old_dcr_postkick).

Implements the LEGACY architecture the user explicitly rejected: a
post-step Δv kick applied to rigid bodies in response to modal
deflection caused by the contact impulse. Kept solely for ablation
against the new coupled IIR mode (`--mode coupled_iir_modal`).

Architecture (mirrors `dcr/dcr/modal_dcr.py::ModalDCRCoupler` but on
the reduced-support basis):

  1. After AVBD step completes, read normal-direction contact impulse
     on each tracked body (impactor + probes).
  2. Project each impulse to the modal r vector:
         r_mode = Σ_j Φ_y(p_j) · n_j · |λ_j|·h_sub
  3. Drive the linear modal ODE forward for `n_substeps` substeps with
     `r` as initial-velocity kick (qdot_kick = M_q^{-1}·r), using the
     exact damped-oscillator response from `exact_resonator`.
  4. For each tracked body's contact corner, compute the peak modal
     displacement at the contact point:
         d_max_i = max_k |Φ_y(p_i) · q^(k)|
  5. Apply Δv_i = d_max_i / h_macro along the contact normal to the
     body's velocity (the body separates from the support; resting
     contacts get the impulse).

# DEVIATION (vs --mode coupled_iir_modal): this IS the post-fix kick
# the new architecture deliberately avoids. Rigid bodies should feel
# modal response through coupled contact, not via after-the-fact
# velocity injection. This file exists solely for the ablation table.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .reduced_support import ReducedSupport, evaluate_basis_at_point
from .reduced_support_solve import _quat_rotate_xyzw


FLOOR_CONTACT_6DOF = 0


@dataclass
class ReducedSupportDCRPostkickCoupler:
    """Legacy DCR post-step Δv kick coupler driven by the reduced
    support basis. Single coupler instance per scene.

    The IIR transient is computed PER MACRO STEP from the previous
    step's contact impulses; the kick is applied at the start of the
    NEXT step (or equivalently, at the end of the current step on the
    body velocity).
    """

    rs: ReducedSupport
    tracked_body_indices: list[int]

    # Shelf metadata for U-eval at arbitrary contact corner positions.
    shelf_length: float
    shelf_width: float
    shelf_y_rest: float
    n_grid_x: int
    n_grid_z: int

    # Macro step and IIR sub-step (Nyquist criterion).
    h_macro:   float = 1.0 / 120.0
    n_substeps: int  = 32

    # Cached body mass (for impulse → velocity conversion).
    body_mass: dict[int, float] = field(default_factory=dict)

    # Diagnostics.
    last_r_modal_norm: float = 0.0
    last_q_peak_norm:  float = 0.0
    last_dv_applied:   dict[int, float] = field(default_factory=dict)
    cum_kick_events:   int = 0

    # Internal: cache U_y at each tracked corner rest-projection. The
    # AVBD floor-contact rows live at fixed body offsets, so we can
    # precompute once at attach-time given the bodies' rest positions.
    _U_y_at_corners: dict[int, NDArray[np.float64]] = field(default_factory=dict)
    _corner_rest_xz: dict[int, tuple[float, float]] = field(default_factory=dict)

    def cache_corner_basis(self, world) -> None:
        """Walk the solver's rows and cache U_y at the rest-position
        projection of each tracked body's floor-contact corners. Call
        once after the scene is built (the bodies' rest positions don't
        change for the shelf scene).
        """
        sol = world._solver
        anchor_np = sol.c_world_anchor.numpy().copy()
        body_a_np = sol.c_body_a.numpy()
        off_a_np  = sol.c_off_a.numpy().copy()
        type_np   = sol.c_type.numpy()
        positions = sol.positions()
        orientations = sol.orientations()

        self._U_y_at_corners.clear()
        self._corner_rest_xz.clear()
        rows_by_body: dict[int, list[int]] = {}
        for i, row in enumerate(sol._rows):
            if row.type != FLOOR_CONTACT_6DOF:
                continue
            ba = int(body_a_np[i])
            if ba not in self.tracked_body_indices:
                continue
            rows_by_body.setdefault(ba, []).append(i)

        for ba, row_ids in rows_by_body.items():
            # Average U_y over all this body's floor-contact corners.
            # For the shelf scene each body has 4 bottom corners; the
            # mean Φ at the centroid is a good proxy for the body's
            # interaction with the modes.
            U_y_avg = np.zeros(self.rs.r, dtype=np.float64)
            n_used = 0
            for row_idx in row_ids:
                off = off_a_np[row_idx]
                q_xyzw = orientations[ba]
                r_world = _quat_rotate_xyzw(q_xyzw, off)
                corner = positions[ba] + r_world
                U_pt = evaluate_basis_at_point(
                    self.rs,
                    (float(corner[0]), float(corner[2])),
                    length=self.shelf_length,
                    width=self.shelf_width,
                    n_grid_x=self.n_grid_x,
                    n_grid_z=self.n_grid_z,
                )
                U_y_avg += U_pt[1]
                n_used += 1
            if n_used > 0:
                self._U_y_at_corners[ba] = U_y_avg / n_used
                # Cache centroid xz for diagnostics.
                cent_x = float(np.mean([
                    positions[ba, 0]
                    + _quat_rotate_xyzw(orientations[ba], off_a_np[r])[0]
                    for r in row_ids]))
                cent_z = float(np.mean([
                    positions[ba, 2]
                    + _quat_rotate_xyzw(orientations[ba], off_a_np[r])[2]
                    for r in row_ids]))
                self._corner_rest_xz[ba] = (cent_x, cent_z)

    def apply(self, world) -> None:
        """Post-step Δv kick. Called from `AVBDDCRWorld.step()` after the
        AVBD solver completes and post-step bookkeeping is done.

        Reads the AVBD-solver lambda for FLOOR rows on tracked bodies as
        a proxy for the time-integrated contact force, drives the modal
        IIR forward for n_substeps, computes peak deflection at each
        body's contact corner, and applies Δv = d_max / h_macro along
        +y to that body's velocity.
        """
        if not self._U_y_at_corners:
            self.cache_corner_basis(world)
            if not self._U_y_at_corners:
                return
        sol = world._solver
        body_a_np = sol.c_body_a.numpy()
        type_np   = sol.c_type.numpy()
        lam_np    = sol.c_lambda.numpy()

        # Aggregate modal forcing from each tracked body's contact rows.
        # The AVBD c_lambda is the AL Lagrange multiplier at the end of
        # the macro step — it scales like the time-integrated contact
        # force (units of N for FLOOR rows in the kernel convention).
        # For the post-kick:
        #   r_modal = Σ_body Φ_y(body_centroid) · Σ_rows |λ_row|·h_macro
        # Treat λ as proxy for force, then multiply by h_macro to get
        # impulse-like units (Ns). Per-mode initial velocity kick:
        #   qdot_kick = M_q⁻¹·r_modal
        impulse_modal = np.zeros(self.rs.r, dtype=np.float64)
        for body_idx in self.tracked_body_indices:
            U_y = self._U_y_at_corners.get(body_idx)
            if U_y is None:
                continue
            lam_body = 0.0
            for i, row in enumerate(sol._rows):
                if row.type != FLOOR_CONTACT_6DOF:
                    continue
                if int(body_a_np[i]) != body_idx:
                    continue
                # FLOOR rows have f ≤ 0 (compressive); |λ| is the impulse.
                lam_body += abs(float(lam_np[i]))
            if lam_body == 0.0:
                continue
            # Modal generalised force from this body, treated as an
            # impulsive kick over the macro step.
            impulse_modal += U_y * (lam_body * self.h_macro)

        self.last_r_modal_norm = float(np.linalg.norm(impulse_modal))
        if self.last_r_modal_norm == 0.0:
            self.last_dv_applied = {}
            return

        # Step the modal IIR forward `n_substeps` times with an initial
        # qdot kick from the impulse. Track q^(k) along the way for
        # peak displacement sampling.
        from ..modal.exact_resonator import (
            dynamic_compliance_step_precompute)
        q_local    = np.zeros(self.rs.r, dtype=np.float64)
        qdot_local = np.linalg.solve(self.rs.Mq, impulse_modal)
        h_sub = self.h_macro / float(self.n_substeps)

        # Track per-body peak displacement at its centroid.
        peak_displacement: dict[int, float] = {
            i: 0.0 for i in self.tracked_body_indices}

        for _ in range(int(self.n_substeps)):
            q_free, qdot_free, _S, _T = dynamic_compliance_step_precompute(
                q_local, qdot_local, self.rs.Mq, self.rs.Kq, self.rs.Dq, h_sub)
            q_local = q_free
            qdot_local = qdot_free
            for body_idx, U_y in self._U_y_at_corners.items():
                d = abs(float(U_y @ q_local))
                if d > peak_displacement[body_idx]:
                    peak_displacement[body_idx] = d

        self.last_q_peak_norm = float(np.linalg.norm(q_local))

        # Apply Δv = d_max / h_macro along +y to each tracked body.
        v_np = sol.v.numpy().copy()
        self.last_dv_applied = {}
        any_kick = False
        for body_idx, d_max in peak_displacement.items():
            if d_max == 0.0:
                continue
            dv = d_max / self.h_macro
            v_np[body_idx, 1] += dv
            self.last_dv_applied[body_idx] = dv
            any_kick = True
        if any_kick:
            sol.v.assign(v_np)
            self.cum_kick_events += 1
