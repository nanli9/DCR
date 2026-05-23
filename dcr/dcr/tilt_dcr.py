"""Deformation-aware contact frame extension for DCR.

Computes a tilted contact normal from the local modal displacement
gradient at each resting contact, then redirects the DCR impulse
along the tilted normal. This produces a lateral/rocking component
that can topple tall, thin objects from distant impacts.

The extension wraps PassiveDCRCoupler — it reuses the same modal
state, energy bookkeeping, and scalar Dv computation. The tilt
decomposition sits on top as a post-processing layer.

# DEVIATION from paper: the paper injects DCR impulses purely along
# the original contact normal. This extension redirects part of the
# impulse along a tilted normal derived from the modal displacement
# gradient, producing lateral forces not present in the original method.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..modal.passive_inject import _closest_point_on_triangle, eval_basis_at_point
from ..rigid.collision import Contact
from .deformed_normal import (
    compute_patch_fit_slopes,
    compute_tilted_normal,
    compute_triangle_tangent_frame,
)
from .passive_dcr import PassiveDCRCoupler

# Re-export the deformed-normal pure helpers for backwards compatibility
# with tests/test_tilt_dcr.py (which imports them from this module).
__all__ = [
    "compute_triangle_tangent_frame",
    "compute_patch_fit_slopes",
    "compute_tilted_normal",
    "apply_tilt_bounds",
    "compute_tilt_lateral_velocity",
    "TiltResult",
    "TiltDCRCoupler",
]


# ======================================================================
# Data structures
# ======================================================================

@dataclass
class TiltResult:
    """Per-contact tilt response result.

    Stores the tilt direction and scalar DCR velocity. The world's
    _apply_tilt_dcr_velocities uses body mass to compute actual impulses.

    Attributes:
        body_idx: Index of the resting body receiving the impulse.
        dv: Scalar DCR separation velocity (from PassiveDCRCoupler).
        n_tilt: (3,) tilted normal direction (unit vector).
        contact_point: (3,) world-space contact point.
        push_dir: (3,) original push direction (un-tilted).
        theta: Tilt angle in radians (diagnostic).
    """
    body_idx: int
    dv: float
    n_tilt: NDArray[np.float64]
    contact_point: NDArray[np.float64]
    push_dir: NDArray[np.float64]
    theta: float


# ======================================================================
# Tilt math — pure functions
# ======================================================================
#
# The three triangle-frame / slope-fit / tilt primitives
# (compute_triangle_tangent_frame, compute_patch_fit_slopes,
# compute_tilted_normal) live in .deformed_normal and are re-exported above
# for backwards compatibility with tests/test_tilt_dcr.py.


def apply_tilt_bounds(
    J_n: float,
    J_t: NDArray[np.float64],
    mass: float,
    dv: float,
    mu_dcr: float,
    eta_t: float,
) -> NDArray[np.float64]:
    """Apply safety bounds to the tangential impulse.

    Bound 1 (theta_max) is already enforced in compute_tilted_normal.

    Bound 2: Coulomb-like lateral cap: ||J_t|| <= mu_dcr * |J_n|
    Bound 3: Energy budget: ||J_t|| <= sqrt(2 * mass * eta_t * E_DCR)
             where E_DCR = 0.5 * mass * dv^2

    Args:
        J_n: Normal impulse magnitude.
        J_t: (3,) tangential impulse vector.
        mass: Body mass.
        dv: Scalar DCR separation velocity.
        mu_dcr: Coulomb-like friction coefficient.
        eta_t: Fraction of DCR energy for tangential impulse.

    Returns:
        J_t_clamped: (3,) clamped tangential impulse.
    """
    J_t_mag = float(np.linalg.norm(J_t))
    if J_t_mag < 1e-18:
        return J_t.copy()

    # Bound 2: Coulomb cap
    coulomb_cap = mu_dcr * abs(J_n)

    # Bound 3: Energy cap
    E_DCR = 0.5 * mass * dv * dv
    energy_cap = np.sqrt(max(0.0, 2.0 * mass * eta_t * E_DCR))

    # Take the minimum of all caps
    cap = min(coulomb_cap, energy_cap)

    if J_t_mag > cap:
        J_t = J_t * (cap / J_t_mag)

    return J_t


def compute_tilt_lateral_velocity(
    delta_v: float,
    mass: float,
    n: NDArray[np.float64],
    n_tilt: NDArray[np.float64],
    lateral_fraction: float,
    dv_t_max: float,
    eta_t: float,
    mu_dcr: float,
    eps: float = 1e-8,
) -> tuple[float, NDArray[np.float64] | None, dict]:
    """Compute bounded lateral velocity from slope-derived tilt direction.

    The tilted normal determines the lateral *direction*. The magnitude
    is a fixed fraction of |delta_v|, independent of the tilt angle.
    This makes the lateral response scene-independent — the same
    lateral_fraction works for soft shelves and stiff ground alike.

    # DEVIATION: the paper applies DCR impulses along the original
    # normal. This extension derives a lateral direction from the modal
    # displacement gradient and applies a proportional tangential correction.
    # The tilted normal is NOT used to replace the solver contact normal.

    Args:
        delta_v: Scalar DCR separation velocity from passive coupler.
        mass: Body mass.
        n: (3,) original push direction (unit normal).
        n_tilt: (3,) tilted normal direction (unit vector).
        lateral_fraction: Fraction of |delta_v| applied laterally.
        dv_t_max: Absolute velocity cap on lateral correction.
        eta_t: Energy fraction cap: 0.5*m*dv_t² <= eta_t * E_dcr.
        mu_dcr: Coulomb-like cap: dv_t <= mu_dcr * |delta_v|.
        eps: Tolerance for near-zero tangent direction.

    Returns:
        (dv_t, t_dir, debug): Lateral velocity magnitude, unit tangent
        direction (or None if no tilt), and debug dictionary.
    """
    debug: dict = {}

    # Lateral direction: tangential projection of tilted normal
    t = n_tilt - float(np.dot(n_tilt, n)) * n
    t_mag = float(np.linalg.norm(t))

    if t_mag < eps:
        debug["reason"] = "no_tilt"
        debug["theta_deg"] = 0.0
        debug["dv_t_applied"] = 0.0
        return 0.0, None, debug

    t_dir = t / t_mag

    # Tilt angle (diagnostic only — not used for magnitude)
    cos_theta = float(np.clip(np.dot(n, n_tilt), -1.0, 1.0))
    theta = float(np.arccos(cos_theta))

    # Lateral magnitude: fixed fraction of DCR kick, direction from tilt
    dv_t_uncapped = lateral_fraction * abs(delta_v)

    # Three caps
    dv_t_velocity_cap = dv_t_max
    dv_t_energy_cap = np.sqrt(eta_t) * abs(delta_v)
    dv_t_coulomb_cap = mu_dcr * abs(delta_v)

    dv_t = min(dv_t_uncapped, dv_t_velocity_cap,
               dv_t_energy_cap, dv_t_coulomb_cap)

    # Build debug dict
    debug["theta_deg"] = float(np.degrees(theta))
    debug["lateral_fraction"] = lateral_fraction
    debug["dv_t_uncapped"] = dv_t_uncapped
    debug["dv_t_energy_cap"] = dv_t_energy_cap
    debug["dv_t_coulomb_cap"] = dv_t_coulomb_cap
    debug["dv_t_velocity_cap"] = dv_t_velocity_cap
    debug["dv_t_applied"] = dv_t

    return dv_t, t_dir, debug


# ======================================================================
# TiltDCRCoupler
# ======================================================================

@dataclass
class TiltDCRCoupler:
    """Deformation-aware contact frame coupler.

    Wraps a PassiveDCRCoupler. Uses the same modal state and energy
    bookkeeping, but extends the distant response by computing a tilted
    normal from the local modal displacement gradient (patch-fit fallback).

    The tilted normal determines the lateral *direction* and slope-based
    raw magnitude. It is NOT used to apply the full impulse along n_tilt.

    Attributes:
        passive: The underlying PassiveDCRCoupler (handles modal state).
        theta_max: Maximum tilt angle in radians (default: 3 degrees).
        mu_dcr: Coulomb-like cap: dv_t <= mu_dcr * |delta_v|.
        eta_t: Energy cap: 0.5*m*dv_t^2 <= eta_t * E_dcr.
        lateral_fraction: Fraction of |delta_v| applied laterally (direction from tilt).
        dv_t_max: Absolute velocity cap on lateral correction (m/s).
        dv_n_max: Cap on vertical DCR velocity in coupled mode (m/s).
    """
    passive: PassiveDCRCoupler
    theta_max: float = np.radians(3.0)
    mu_dcr: float = 0.2
    eta_t: float = 0.3
    lateral_fraction: float = 0.3
    dv_t_max: float = 1.5
    dv_n_max: float = 0.3

    # Precomputed per-triangle data.
    _tri_normals: NDArray[np.float64] = field(init=False, repr=False)
    _tri_tangent_t1: NDArray[np.float64] = field(init=False, repr=False)
    _tri_tangent_t2: NDArray[np.float64] = field(init=False, repr=False)

    # Stored per step for the world to apply normal DCR kick.
    last_dcr_velocities: dict[int, float] = field(default_factory=dict)

    # Diagnostics.
    last_tilt_results: list[TiltResult] = field(default_factory=list)

    @property
    def elastic_body_idx(self) -> int:
        return self.passive.elastic_body_idx

    def __post_init__(self) -> None:
        self._precompute_triangle_data()

    def _precompute_triangle_data(self) -> None:
        """Precompute tangent frames for each surface triangle."""
        surface = self.passive._surface
        verts = surface.vertices
        faces = surface.faces
        n_faces = faces.shape[0]

        self._tri_normals = np.zeros((n_faces, 3), dtype=np.float64)
        self._tri_tangent_t1 = np.zeros((n_faces, 3), dtype=np.float64)
        self._tri_tangent_t2 = np.zeros((n_faces, 3), dtype=np.float64)

        for fi in range(n_faces):
            v0, v1, v2 = verts[faces[fi, 0]], verts[faces[fi, 1]], verts[faces[fi, 2]]
            e1 = v1 - v0
            e2 = v2 - v0
            cross = np.cross(e1, e2)
            length = np.linalg.norm(cross)
            if length < 1e-14:
                self._tri_normals[fi] = np.array([0.0, 1.0, 0.0])
            else:
                self._tri_normals[fi] = cross / length

            t1, t2 = compute_triangle_tangent_frame(
                v0, v1, v2, self._tri_normals[fi])
            self._tri_tangent_t1[fi] = t1
            self._tri_tangent_t2[fi] = t2

    def process_step(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        h: float,
        E_max: float,
    ) -> list[TiltResult]:
        """Run passive DCR + tilt extension.

        1. Delegates to self.passive.process_step() for modal state
           update and base scalar Dv computation.
        2. Uses the transient q_history to compute tilted normals at
           each resting contact.
        3. Decomposes the DCR impulse into normal + tangential components.
        4. Applies safety bounds.

        Args:
            contacts: All contacts this step.
            lam: Solved constraint impulse vector.
            h: Rigid-body timestep.
            E_max: Energy budget = eta * E_loss.

        Returns:
            List of TiltResult for each resting contact with nonzero response.
        """
        # Step 1: Run the underlying passive coupler
        dcr_velocities = self.passive.process_step(contacts, lam, h, E_max)
        self.last_dcr_velocities = dcr_velocities

        q_history = self.passive.last_q_history_transient
        if q_history is None or len(dcr_velocities) == 0:
            self.last_tilt_results = []
            return []

        # Step 2: Identify resting contacts on the elastic body
        elastic_idx = self.elastic_body_idx
        resting_contacts: list[Contact] = []
        for contact in contacts:
            if contact.is_new:
                continue
            if contact.body_a == elastic_idx or contact.body_b == elastic_idx:
                resting_contacts.append(contact)

        surface = self.passive._surface
        verts = surface.vertices
        faces = surface.faces
        U_surf = self.passive.modal.U_surf
        surf_indices = self.passive.modal.surface_vertex_indices
        vert_to_surf = self.passive._vert_to_surf_idx

        results: list[TiltResult] = []

        for contact in resting_contacts:
            # Determine which body gets the kick
            if contact.body_a == elastic_idx:
                other_body = contact.body_b
                push_dir = -contact.normal  # push B away from elastic A
            else:
                other_body = contact.body_a
                push_dir = contact.normal   # push A away from elastic B

            if other_body not in dcr_velocities:
                continue
            dv = dcr_velocities[other_body]
            if dv < 1e-15:
                continue

            # Step 3: Find closest triangle and compute tilt
            best_dist = np.inf
            best_tri = 0
            for fi in range(faces.shape[0]):
                v0 = verts[faces[fi, 0]]
                v1 = verts[faces[fi, 1]]
                v2 = verts[faces[fi, 2]]
                cp, _ = _closest_point_on_triangle(contact.point, v0, v1, v2)
                d = np.linalg.norm(contact.point - cp)
                if d < best_dist:
                    best_dist = d
                    best_tri = fi

            face = faces[best_tri]
            v0 = verts[face[0]]
            v1 = verts[face[1]]
            v2 = verts[face[2]]
            tri_n = self._tri_normals[best_tri]
            t1 = self._tri_tangent_t1[best_tri]
            t2 = self._tri_tangent_t2[best_tri]

            # Step 4: Find the peak substep in q_history
            # Evaluate modal basis at contact point for displacement projection
            Phi_x = eval_basis_at_point(
                contact.point, surface, U_surf, surf_indices, vert_to_surf)
            nPhi = push_dir @ Phi_x  # (n_modes,) — projection along push direction
            d_all = q_history @ nPhi  # (n_substeps,)
            k_peak = int(np.argmax(np.abs(d_all)))
            q_peak = q_history[k_peak]

            # Step 5: Sample normal displacement at triangle vertices
            w_vals = []
            for k in range(3):
                vert_global = face[k]
                surf_idx = vert_to_surf[vert_global]
                if surf_idx < 0:
                    # Fixed boundary vertex — zero displacement
                    w_vals.append(0.0)
                else:
                    row_start = 3 * surf_idx
                    U_i = U_surf[row_start:row_start + 3, :]  # (3, n_modes)
                    u_vertex = U_i @ q_peak  # (3,) displacement
                    w_vals.append(float(np.dot(tri_n, u_vertex)))

            # Step 6: Compute slopes via patch fit
            s1, s2 = compute_patch_fit_slopes(
                w_vals[0], w_vals[1], w_vals[2], v0, v1, v2, t1, t2)

            # Step 7: Tilted normal (with theta_max clamp)
            n_tilt, theta = compute_tilted_normal(
                push_dir, s1, s2, t1, t2, self.theta_max)

            if theta < 1e-8:
                # No tilt — skip (the normal kick is handled by the
                # fallback path in dcr_world when tilt_only is False).
                continue

            results.append(TiltResult(
                body_idx=other_body,
                dv=dv,
                n_tilt=n_tilt.copy(),
                contact_point=contact.point.copy(),
                push_dir=push_dir.copy(),
                theta=theta,
            ))

        # Remove duplicates per body — keep the one with largest tilt
        seen: dict[int, int] = {}
        for i, r in enumerate(results):
            if r.body_idx not in seen or results[seen[r.body_idx]].theta < r.theta:
                seen[r.body_idx] = i
        results = [results[i] for i in seen.values()]

        self.last_tilt_results = results
        return results
