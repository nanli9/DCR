"""Spatial-attenuation path for distant collision response (Eqs. 14–16, 19).

For large objects where traveling waves dominate over standing modes.
Uses geodesic distance-based attenuation instead of full modal propagation.

Flow per rigid-body step:
    1. PGS solve → λ_N for new contacts on the elastic body
    2. Local displacement at impact: Δx_c = q̂^T h_c λ_N        (Eq. 15)
    3. Attenuation factor: s = C r^{-β}                          (Eq. 14)
    4. Response: Δv_p = s · Δx_c / h                             (Eq. 16)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh
from ..modal.modal_analysis import ModalAnalysis
from ..modal.iir_stepper import IIRModalStepper
from ..rigid.collision import Contact
from .geodesic import heat_geodesic_cached
from .modal_dcr import _closest_point_on_triangle


@dataclass
class SpatialDCRCoupler:
    """Spatial-attenuation DCR for large elastic bodies (Eqs. 14–16, 19).

    Attributes:
        modal: Modal analysis results for the elastic body.
        elastic_body_idx: Index of the elastic body in world.bodies.
        C: Attenuation constant (paper §4.5: 0.4–2.0).
        beta: Attenuation exponent (0.5 for shells, 1 for volumes).
        r0: Minimum distance cutoff (≈ element size).
        impulse_threshold: Skip DCR if λ_N < this.
    """

    modal: ModalAnalysis
    elastic_body_idx: int
    C: float = 1.0
    beta: float = 0.5
    r0: float = 0.0  # 0 → auto-compute from mean edge length
    impulse_threshold: float = 1e-3

    # Internals.
    _surface: TriMesh = field(init=False, repr=False)
    _self_amplitudes: NDArray[np.float64] = field(init=False, repr=False)
    _vert_to_surf_idx: NDArray[np.int32] = field(init=False, repr=False)
    _geodesic_cache: dict[int, NDArray[np.float64]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._surface = self.modal.fem.mesh.extract_surface()
        self._geodesic_cache = {}

        # Build vertex mapping.
        max_vert = self.modal.fem.mesh.num_vertices
        self._vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
        for si, vi in enumerate(self.modal.surface_vertex_indices):
            self._vert_to_surf_idx[vi] = si

        # Auto-compute r0 from mean edge length if not set.
        if self.r0 <= 0.0:
            V = self._surface.vertices
            F = self._surface.faces
            edges = np.concatenate([
                V[F[:, 1]] - V[F[:, 0]],
                V[F[:, 2]] - V[F[:, 1]],
                V[F[:, 0]] - V[F[:, 2]],
            ])
            self.r0 = float(np.mean(np.linalg.norm(edges, axis=1)))

        self._precompute_self_amplitudes()

    # ------------------------------------------------------------------
    # §6.1: Precompute self-impulse displacement per surface vertex
    # ------------------------------------------------------------------
    def _precompute_self_amplitudes(self) -> None:
        """For each surface vertex, apply a unit Y-normal impulse at that vertex
        and record max displacement using the modal IIR (§6.1).

        Stores q̂ ∈ R^{n_surf}: one scalar per surface vertex.
        """
        m = self.modal.num_modes
        n_surf = len(self.modal.surface_vertex_indices)
        self._self_amplitudes = np.zeros(n_surf, dtype=np.float64)

        stepper = IIRModalStepper(modal=self.modal)
        normal = np.array([0.0, 1.0, 0.0])  # default up-normal

        for si in range(n_surf):
            row_start = 3 * si
            U_i = self.modal.U_surf[row_start:row_start + 3, :]  # (3, m)
            # Modal forcing for unit impulse at this vertex: r = U_i^T n * 1.0
            r = U_i.T @ normal  # (m,)

            stepper.reset()
            # Run enough sub-steps to capture the peak.
            n_sub = max(10, int(np.ceil(0.01 / stepper.T)))
            q_hist = stepper.step_n(n_sub, r=r)

            # Displacement at the same vertex: d(k) = n^T U_i q(k)
            nU = normal @ U_i  # (m,)
            d_all = q_hist @ nU
            self._self_amplitudes[si] = float(np.max(np.abs(d_all)))

    # ------------------------------------------------------------------
    # Surface query
    # ------------------------------------------------------------------
    def _closest_surface_point(
        self, world_point: NDArray[np.float64],
    ) -> tuple[int, NDArray[np.float64]]:
        """Find closest surface triangle and barycentric coordinates."""
        verts = self._surface.vertices
        faces = self._surface.faces
        best_dist = np.inf
        best_tri = 0
        best_bary = np.array([1.0 / 3, 1.0 / 3, 1.0 / 3])

        for fi in range(faces.shape[0]):
            v0, v1, v2 = verts[faces[fi, 0]], verts[faces[fi, 1]], verts[faces[fi, 2]]
            cp, bary = _closest_point_on_triangle(world_point, v0, v1, v2)
            d = np.linalg.norm(world_point - cp)
            if d < best_dist:
                best_dist = d
                best_tri = fi
                best_bary = bary
        return best_tri, best_bary

    def _closest_vertex(self, world_point: NDArray[np.float64]) -> int:
        """Find the closest surface vertex (global index)."""
        dists = np.linalg.norm(
            self._surface.vertices[self.modal.surface_vertex_indices] - world_point, axis=1)
        return int(self.modal.surface_vertex_indices[np.argmin(dists)])

    # ------------------------------------------------------------------
    # Eq. 14: Attenuation factor
    # ------------------------------------------------------------------
    def attenuation(self, geodesic_dist: float) -> float:
        """Compute spatial attenuation s = C * (r / r0)^{-β} (Eq. 14, simplified)."""
        r = max(geodesic_dist, self.r0)
        return self.C * (r / self.r0) ** (-self.beta)

    # ------------------------------------------------------------------
    # Eq. 15: Local displacement at impact
    # ------------------------------------------------------------------
    def local_displacement(
        self,
        contact_point: NDArray[np.float64],
        lambda_N: float,
    ) -> float:
        """Compute Δx_c = q̂^T h_c λ_N (Eq. 15).

        Interpolates self-amplitude at the contact point using barycentric coords.
        """
        tri_idx, bary = self._closest_surface_point(contact_point)
        face = self._surface.faces[tri_idx]

        dx = 0.0
        for k in range(3):
            vert_global = face[k]
            surf_idx = self._vert_to_surf_idx[vert_global]
            if surf_idx < 0:
                continue
            dx += bary[k] * self._self_amplitudes[surf_idx] * lambda_N

        return dx

    # ------------------------------------------------------------------
    # Full spatial DCR pipeline
    # ------------------------------------------------------------------
    def process_step(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        h: float,
    ) -> dict[int, float]:
        """Run the spatial-attenuation DCR pipeline for one step.

        Returns:
            dcr_velocities: Dict mapping body index → separation velocity Δv.
        """
        new_contacts: list[tuple[Contact, float]] = []
        resting_contacts: list[Contact] = []

        for ci, contact in enumerate(contacts):
            if contact.body_a != self.elastic_body_idx and \
               contact.body_b != self.elastic_body_idx:
                continue

            lambda_N = lam[3 * ci] if 3 * ci < len(lam) else 0.0

            if contact.is_new:
                if abs(lambda_N) > self.impulse_threshold:
                    new_contacts.append((contact, lambda_N))
            else:
                resting_contacts.append(contact)

        if not new_contacts or not resting_contacts:
            return {}

        dcr_velocities: dict[int, float] = {}

        for new_contact, lambda_N in new_contacts:
            # Eq. 15: local displacement.
            dx_c = self.local_displacement(new_contact.point, lambda_N)

            # Closest vertex to impact (for geodesic source).
            impact_vert = self._closest_vertex(new_contact.point)

            # Geodesic distances from impact.
            geo_dist = heat_geodesic_cached(
                self._surface, self._geodesic_cache, impact_vert)

            for rest_contact in resting_contacts:
                other_body = rest_contact.body_a if rest_contact.body_b == self.elastic_body_idx \
                             else rest_contact.body_b

                # Closest vertex to resting contact.
                rest_vert = self._closest_vertex(rest_contact.point)

                # Geodesic distance → attenuation (Eq. 14).
                r = geo_dist[rest_vert]
                s = self.attenuation(r)

                # Eq. 16: Δv = s · Δx_c / h
                dv = s * dx_c / h

                if other_body in dcr_velocities:
                    dcr_velocities[other_body] = max(dcr_velocities[other_body], dv)
                else:
                    dcr_velocities[other_body] = dv

        return dcr_velocities
