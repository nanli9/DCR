"""Passive energy-bounded DCR coupler (Stage E3).

# DEVIATION from paper Eq. 10: injection enters as a velocity kick to qdot
# followed by free damped oscillation, not as an impulse forcing term inside
# the IIR (foundation §15).

Replaces ModalDCRCoupler's forced-IIR path with:
1. Project full contact impulse j onto modal basis → s (E1, foundation §4)
2. Passive scaling alpha so dE_modal <= eta * E_loss (E2, foundation §6)
3. Kick qdot += alpha * s (foundation §7)
4. Homogeneous stepper for h/T sub-steps (E3.1)
5. Same Eq. 11-13 distant response as Stage 5

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
from ..rigid.collision import Contact
from ..rigid.solver import _pick_friction_dirs


@dataclass
class PassiveDCRCoupler:
    """Energy-bounded modal-path DCR coupler (Stage E3, foundation §15).

    Like ModalDCRCoupler but uses passive injection instead of forced IIR.

    Attributes:
        modal: Modal analysis results for the elastic body.
        elastic_body_idx: Index of the elastic body in world.bodies.
        impulse_threshold: Skip DCR if total impulse magnitude < this.
    """

    modal: ModalAnalysis
    elastic_body_idx: int
    impulse_threshold: float = 1e-3

    # Internals.
    _stepper: HomogeneousStepper = field(init=False, repr=False)
    _surface: TriMesh = field(init=False, repr=False)
    _vert_to_surf_idx: NDArray[np.int32] = field(init=False, repr=False)

    # Energy diagnostics per step.
    last_E_modal_pre_kick: float = 0.0
    last_E_modal_post_kick: float = 0.0
    last_alpha: float = 0.0

    def __post_init__(self) -> None:
        self._stepper = HomogeneousStepper.from_modal_analysis(self.modal)
        self._surface = self.modal.fem.mesh.extract_surface()
        max_vert = self.modal.fem.mesh.num_vertices
        self._vert_to_surf_idx = np.full(max_vert, -1, dtype=np.int32)
        for si, vi in enumerate(self.modal.surface_vertex_indices):
            self._vert_to_surf_idx[vi] = si

    def process_step(
        self,
        contacts: list[Contact],
        lam: NDArray[np.float64],
        h: float,
        E_max: float,
    ) -> dict[int, float]:
        """Run the passive DCR pipeline for one rigid-body step.

        Args:
            contacts: All contacts this step.
            lam: Solved constraint impulse vector (3 rows per contact).
            h: Rigid-body timestep.
            E_max: Energy budget = eta * E_loss from the rigid solver.

        Returns:
            dcr_velocities: Dict mapping body index → separation velocity Δv.
        """
        omega = self.modal.frequencies
        n_modes = self.modal.num_modes

        # --- Identify new and resting contacts on the elastic body ---
        new_contacts_data: list[tuple[Contact, int]] = []  # (contact, ci)
        resting_contacts: list[Contact] = []
        # Track which bodies are involved in new impacts so we can exclude
        # them from distant response — they are at the impact site, not
        # "distant" resting contacts (matches original DCR Stage 5 intent).
        impacting_body_ids: set[int] = set()

        for ci, contact in enumerate(contacts):
            if contact.body_a != self.elastic_body_idx and \
               contact.body_b != self.elastic_body_idx:
                continue
            if contact.is_new:
                new_contacts_data.append((contact, ci))
                other = contact.body_a if contact.body_b == self.elastic_body_idx \
                    else contact.body_b
                impacting_body_ids.add(other)
            else:
                resting_contacts.append(contact)

        # Filter resting contacts: exclude bodies that caused new impacts
        # this step. They are at the impact site, not distant.
        resting_contacts = [
            c for c in resting_contacts
            if (c.body_a if c.body_b == self.elastic_body_idx else c.body_b)
            not in impacting_body_ids
        ]

        # --- Project new contact impulses → s_total (E1, foundation §4, §8) ---
        kicks: list[NDArray[np.float64]] = []
        for contact, ci in new_contacts_data:
            if 3 * ci + 2 >= len(lam):
                continue
            lambda_N = lam[3 * ci]
            lambda_T1 = lam[3 * ci + 1]
            lambda_T2 = lam[3 * ci + 2]

            # Reconstruct full impulse vector in world frame.
            t1, t2 = _pick_friction_dirs(contact.normal)
            j_world = contact.normal * lambda_N + t1 * lambda_T1 + t2 * lambda_T2

            if np.linalg.norm(j_world) < self.impulse_threshold:
                continue

            Phi_x = eval_basis_at_point(
                contact.point, self._surface, self.modal.U_surf,
                self.modal.surface_vertex_indices, self._vert_to_surf_idx,
            )
            s_c = project_impulse(Phi_x, j_world)
            kicks.append(s_c)

        if not kicks:
            # No new impulses — step the homogeneous stepper for free decay,
            # but do NOT produce distant responses (matches Stage 5 behavior:
            # no new impact → no DCR velocity corrections).
            n_substeps = max(1, int(np.ceil(h / self._stepper.T)))
            self.last_alpha = 0.0
            self.last_E_modal_pre_kick = modal_energy(
                self._stepper.q, self._stepper.qdot, omega)
            self.last_E_modal_post_kick = self.last_E_modal_pre_kick
            self._stepper.step_n(n_substeps)
            return {}

        s_total = aggregate_kicks(kicks)

        # --- Passive scaling (E2, foundation §6) ---
        self.last_E_modal_pre_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)
        alpha = passive_alpha(s_total, self._stepper.qdot, E_max)
        self.last_alpha = alpha

        # --- Velocity kick (foundation §7): qdot += alpha * s_total ---
        self._stepper.qdot += alpha * s_total

        self.last_E_modal_post_kick = modal_energy(
            self._stepper.q, self._stepper.qdot, omega)

        # --- Homogeneous stepping for h/T sub-steps (E3.1) ---
        n_substeps = max(1, int(np.ceil(h / self._stepper.T)))
        q_history = self._stepper.step_n(n_substeps)

        # --- Distant contact response (Eqs. 11-13, unchanged from Stage 5) ---
        return self._compute_distant_response(
            resting_contacts, q_history, h)

    def _compute_distant_response(
        self,
        resting_contacts: list[Contact],
        q_history: NDArray[np.float64],
        h: float,
    ) -> dict[int, float]:
        """Compute Δv at resting contacts from modal displacement history.

        Reuses Stage 5 Eqs. 11-12: d_max = max_k |n^T U_i q^(k)|, Δv = d_max / h.
        """
        dcr_velocities: dict[int, float] = {}

        for contact in resting_contacts:
            other_body = contact.body_a if contact.body_b == self.elastic_body_idx \
                else contact.body_b

            d_max = self._compute_max_displacement(
                contact.point, contact.normal, q_history)
            dv = d_max / h

            if other_body in dcr_velocities:
                dcr_velocities[other_body] = max(dcr_velocities[other_body], dv)
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
        # d(k) = n^T Phi_x q(k)
        nPhi = normal @ Phi_x  # (n_modes,)
        d_all = q_history @ nPhi
        return float(np.max(np.abs(d_all)))
