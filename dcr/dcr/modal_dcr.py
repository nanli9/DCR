"""Modal-path distant collision response (paper §4, Eqs. 9–13).

Couples the IIR modal stepper (Stage 4) with the rigid body solver (Stage 1)
to propagate impact vibrations across an elastic body and wake up distant
resting contacts.

Flow per rigid-body step:
    1. PGS solve → λ_N for new contacts on the elastic body
    2. Map impulse to modal forcing: r_c = U^T H_c^T n_c λ_N   (Eq. 9)
    3. Reset IIR, step h/T sub-steps with forcing at k=1        (Eq. 10)
    4. At resting contacts, compute max normal displacement      (Eq. 11)
    5. Convert to velocity change: Δv = d_max / h               (Eq. 12)
    6. Apply Δv to resting rigid bodies                          (Eq. 13)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..geom.mesh import TriMesh
from ..modal.modal_analysis import ModalAnalysis
from ..modal.iir_stepper import IIRModalStepper
from ..rigid.collision import Contact


@dataclass
class ModalDCRCoupler:
    """Couples one elastic body's modal response with the rigid body world.

    Attributes:
        modal: Modal analysis results for the elastic body.
        elastic_body_idx: Index of the elastic body in world.bodies
                          (should be a static body used for collision).
        impulse_threshold: Skip DCR if λ_N < this fraction of typical body weight.
    """

    modal: ModalAnalysis
    elastic_body_idx: int
    impulse_threshold: float = 1e-3

    # Internals (built on init).
    _stepper: IIRModalStepper = field(init=False, repr=False)
    _surface: TriMesh = field(init=False, repr=False)
    _vert_to_surf_idx: NDArray[np.int32] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._stepper = IIRModalStepper(modal=self.modal)
        self._surface = self.modal.fem.mesh.extract_surface()
        # Build mapping: global mesh vertex → index in surface_vertex_indices.
        max_vert = self.modal.fem.mesh.num_vertices
        self._vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
        for si, vi in enumerate(self.modal.surface_vertex_indices):
            self._vert_to_surf_idx[vi] = si

    # ------------------------------------------------------------------
    # Surface queries
    # ------------------------------------------------------------------
    def _closest_surface_point(
        self, world_point: NDArray[np.float64],
    ) -> tuple[int, NDArray[np.float64]]:
        """Find the closest surface triangle and barycentric coordinates.

        Args:
            world_point: (3,) point in world frame (assumed = mesh rest frame).

        Returns:
            tri_idx: Index into surface.faces.
            bary: (3,) barycentric coordinates (w0, w1, w2).
        """
        verts = self._surface.vertices
        faces = self._surface.faces

        # Brute-force closest triangle. Fine for ~500 faces.
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

    # ------------------------------------------------------------------
    # Eq. 9: Map contact impulse to modal forcing
    # ------------------------------------------------------------------
    def compute_modal_forcing(
        self,
        contact_point: NDArray[np.float64],
        normal: NDArray[np.float64],
        lambda_N: float,
    ) -> NDArray[np.float64]:
        """Compute reduced impulse r_c = U_surf^T H_c^T n_c λ_N (Eq. 9).

        Args:
            contact_point: (3,) world-space contact point on elastic body.
            normal: (3,) contact normal.
            lambda_N: Normal impulse magnitude from PGS solve.

        Returns:
            r_c: (m,) modal forcing vector.
        """
        tri_idx, bary = self._closest_surface_point(contact_point)
        face = self._surface.faces[tri_idx]  # 3 global vertex indices

        m = self.modal.num_modes
        r = np.zeros(m, dtype=np.float64)

        for k in range(3):
            vert_global = face[k]
            surf_idx = self._vert_to_surf_idx[vert_global]
            if surf_idx < 0:
                continue  # Fixed node, not in U_surf
            # U_i ∈ R^{3 × m} for this surface vertex.
            row_start = 3 * surf_idx
            U_i = self.modal.U_surf[row_start:row_start + 3, :]  # (3, m)
            # Contribution: bary[k] * U_i^T @ n * λ_N
            r += bary[k] * (U_i.T @ normal) * lambda_N

        return r

    # ------------------------------------------------------------------
    # Eq. 11: Max displacement at a distant contact
    # ------------------------------------------------------------------
    def compute_max_displacement(
        self,
        contact_point: NDArray[np.float64],
        normal: NDArray[np.float64],
        q_history: NDArray[np.float64],
    ) -> float:
        """Compute d_{i,max} = max_k |n^T U_i q^(k)| (Eq. 11).

        Args:
            contact_point: (3,) world-space resting contact point.
            normal: (3,) contact normal at resting contact.
            q_history: (n_steps, m) modal amplitudes over sub-steps.

        Returns:
            d_max: Maximum normal displacement magnitude.
        """
        tri_idx, bary = self._closest_surface_point(contact_point)
        face = self._surface.faces[tri_idx]

        # Interpolated displacement at contact point: sum bary[k] * U_i @ q
        # Then project onto normal: n^T * displacement
        m = self.modal.num_modes
        n_steps = q_history.shape[0]

        # Precompute the weighted mode-to-normal-disp vector:
        #   v = sum_k bary[k] * (n^T U_k)   shape: (m,)
        nU = np.zeros(m, dtype=np.float64)
        for k in range(3):
            vert_global = face[k]
            surf_idx = self._vert_to_surf_idx[vert_global]
            if surf_idx < 0:
                continue
            row_start = 3 * surf_idx
            U_i = self.modal.U_surf[row_start:row_start + 3, :]
            nU += bary[k] * (normal @ U_i)  # (m,)

        # d(k) = nU @ q(k); d_max = max |d(k)|
        d_all = q_history @ nU  # (n_steps,)
        return float(np.max(np.abs(d_all)))

    # ------------------------------------------------------------------
    # Full DCR pipeline for one rigid-body step
    # ------------------------------------------------------------------
    def process_step(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        h: float,
    ) -> dict[int, float]:
        """Run the full DCR pipeline for one rigid-body step.

        Args:
            contacts: All contacts this step.
            lam: Solved constraint impulse vector (3 rows per contact:
                 normal, friction1, friction2).
            h: Rigid-body timestep.

        Returns:
            dcr_velocities: Dict mapping body index → separation velocity Δv
                            for bodies at resting contacts on the elastic body.
        """
        # Identify new and resting contacts involving the elastic body.
        new_contacts: list[tuple[Contact, float]] = []  # (contact, lambda_N)
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

        if not new_contacts:
            return {}

        # Eq. 9: Sum modal forcing from all new contacts.
        m = self.modal.num_modes
        r_total = np.zeros(m, dtype=np.float64)
        for contact, lambda_N in new_contacts:
            r_c = self.compute_modal_forcing(
                contact.point, contact.normal, lambda_N)
            r_total += r_c

        # Eq. 10: Reset IIR (paper §4.5 simplification) and step h/T sub-steps.
        self._stepper.reset()
        n_substeps = max(1, int(np.ceil(h / self._stepper.T)))
        q_history = self._stepper.step_n(n_substeps, r=r_total)

        # Eqs. 11-12: For each resting contact, compute Δv.
        dcr_velocities: dict[int, float] = {}
        for contact in resting_contacts:
            # Identify the OTHER body (not the elastic one).
            other_body = contact.body_a if contact.body_b == self.elastic_body_idx \
                         else contact.body_b

            d_max = self.compute_max_displacement(
                contact.point, contact.normal, q_history)

            # Eq. 12: Δv = d_max / h
            dv = d_max / h

            # Accumulate: multiple resting contacts on same body → take max.
            if other_body in dcr_velocities:
                dcr_velocities[other_body] = max(dcr_velocities[other_body], dv)
            else:
                dcr_velocities[other_body] = dv

        return dcr_velocities


# ---------- Geometry utilities ----------

def _closest_point_on_triangle(
    p: NDArray[np.float64],
    v0: NDArray[np.float64],
    v1: NDArray[np.float64],
    v2: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Closest point on triangle (v0, v1, v2) to point p.

    Returns (closest_point, barycentric_coords).
    Uses the Voronoi region method (Real-Time Collision Detection, §5.1.5).
    """
    ab = v1 - v0
    ac = v2 - v0
    ap = p - v0

    d1 = np.dot(ab, ap)
    d2 = np.dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return v0.copy(), np.array([1.0, 0.0, 0.0])

    bp = p - v1
    d3 = np.dot(ab, bp)
    d4 = np.dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return v1.copy(), np.array([0.0, 1.0, 0.0])

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return v0 + v * ab, np.array([1.0 - v, v, 0.0])

    cp = p - v2
    d5 = np.dot(ab, cp)
    d6 = np.dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return v2.copy(), np.array([0.0, 0.0, 1.0])

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return v0 + w * ac, np.array([1.0 - w, 0.0, w])

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return v1 + w * (v2 - v1), np.array([0.0, 1.0 - w, w])

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return v0 + v * ab + w * ac, np.array([1.0 - v - w, v, w])
